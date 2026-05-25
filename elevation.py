"""Elevation data access and green contour computation."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import requests


def compute_contours(
    z: np.ndarray,
    levels: list[float],
) -> dict[float, list[np.ndarray]]:
    """Marching squares: extract contour polylines from a 2D elevation grid.

    Args:
        z: 2D array (ny, nx) of elevation values.
        levels: Contour z-values to extract.

    Returns:
        {level: [polyline, ...]} where each polyline is an (N, 2) array
        of (x, y) coordinates in grid-cell space.
    """
    result: dict[float, list[np.ndarray]] = {}
    for level in levels:
        polylines = _marching_squares_level(z, level)
        if polylines:
            result[level] = polylines
    return result


def _marching_squares_level(z: np.ndarray, level: float) -> list[np.ndarray]:
    ny, nx = z.shape
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []

    for j in range(ny - 1):
        for i in range(nx - 1):
            tl, tr = z[j, i], z[j, i + 1]
            br, bl = z[j + 1, i + 1], z[j + 1, i]

            mask = 0
            if not np.isnan(tl) and tl >= level:
                mask |= 1
            if not np.isnan(tr) and tr >= level:
                mask |= 2
            if not np.isnan(br) and br >= level:
                mask |= 4
            if not np.isnan(bl) and bl >= level:
                mask |= 8

            if mask == 0 or mask == 15:
                continue

            edges = _CELL_EDGES[mask]
            if edges is None:
                continue
            pts = _edge_intersections(i, j, tl, tr, br, bl, level, edges)
            if len(pts) >= 2:
                segments.append((pts[0], pts[1]))

    return _connect_segments(segments)


def _edge_intersections(
    i: int, j: int,
    tl: float, tr: float, br: float, bl: float,
    level: float,
    edges: tuple[int, int],
) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for edge in edges:
        if edge == 0:
            t = (level - tl) / (tr - tl) if tr != tl else 0.5
            out.append((i + t, j))
        elif edge == 1:
            t = (level - tr) / (br - tr) if br != tr else 0.5
            out.append((i + 1, j + t))
        elif edge == 2:
            t = (level - bl) / (br - bl) if br != bl else 0.5
            out.append((i + t, j + 1))
        elif edge == 3:
            t = (level - tl) / (bl - tl) if bl != tl else 0.5
            out.append((i, j + t))
    return out


_CELL_EDGES: list[tuple[int, int] | None] = [
    None,       # 0
    (3, 0),     # 1: tl
    (0, 1),     # 2: tr
    (3, 1),     # 3: tl+tr
    (1, 2),     # 4: br
    (1, 3),     # 5: tl+br (saddle)
    (0, 2),     # 6: tr+br
    (3, 2),     # 7: tl+tr+br
    (2, 3),     # 8: bl
    (2, 0),     # 9: tl+bl
    (2, 0),     # 10: tr+bl (saddle)
    (2, 1),     # 11: tl+tr+bl
    (3, 2),     # 12: br+bl
    (1, 2),     # 13: tl+br+bl
    (0, 1),     # 14: tr+br+bl
    None,       # 15
]


def _connect_segments(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
) -> list[np.ndarray]:
    if not segments:
        return []
    adj: dict[tuple[float, float], list[tuple[float, float]]] = {}
    for a, b in segments:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    used: set[tuple[float, float]] = set()
    polylines: list[np.ndarray] = []
    for start, _ in segments:
        if start in used:
            continue
        line = [start]
        used.add(start)
        current = start
        while True:
            neighbors = [n for n in adj.get(current, []) if n not in used]
            if not neighbors:
                break
            next_pt = neighbors[0]
            line.append(next_pt)
            used.add(next_pt)
            current = next_pt
        if len(line) >= 2:
            polylines.append(np.array(line))
    return polylines


def get_course_dem(course_name: str, holes_geo: dict) -> Path | None:
    """Download/cache the 1m DEM covering all green bounding boxes.
    Returns path to cached GeoTIFF or None if unavailable."""
    from cartographer.data import get_dem_path

    cache_path = get_dem_path(course_name)
    if cache_path.exists():
        return cache_path

    bounds = _course_green_bounds(holes_geo)
    if bounds is None:
        return None

    url = _search_tnm(bounds)
    if url is None:
        return None

    _download_file(url, cache_path)
    return cache_path if cache_path.exists() else None


def _course_green_bounds(holes_geo: dict) -> tuple[float, float, float, float] | None:
    """(min_lon, min_lat, max_lon, max_lat) across all green polygons."""
    min_lat, max_lat = 90.0, -90.0
    min_lon, max_lon = 180.0, -180.0
    found = False
    for geom in holes_geo.values():
        for ring in geom.get("green", []):
            for pt in ring:
                lon, lat = pt[0], pt[1]
                min_lat = min(min_lat, lat)
                max_lat = max(max_lat, lat)
                min_lon = min(min_lon, lon)
                max_lon = max(max_lon, lon)
                found = True
    return (min_lon, min_lat, max_lon, max_lat) if found else None


def _search_tnm(bounds: tuple[float, float, float, float]) -> str | None:
    """Query USGS TNM API for 1m DEM download URL covering the bounds."""
    min_lon, min_lat, max_lon, max_lat = bounds
    params = {
        "datasets": "Elevation 3DEP 1m",
        "bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}",
        "prodExtents": "1m DEM",
        "returnGeometry": "false",
        "outputFormat": "JSON",
    }
    try:
        resp = requests.get(
            "https://tnmaccess.nationalmap.gov/api/v1/products",
            params=params, timeout=30,
        )
        resp.raise_for_status()
        for item in resp.json().get("items", []):
            for key in ("downloadURL", "url", "URL"):
                url = item.get(key)
                if url and url.lower().endswith(".tif"):
                    return url
        return None
    except requests.RequestException:
        return None


def _download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
    except requests.RequestException:
        if dest.exists():
            dest.unlink()
