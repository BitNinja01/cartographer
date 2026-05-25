"""Elevation data access and green contour computation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from affine import Affine
from PIL import Image
import rasterio
from rasterio.crs import CRS
from rasterio.warp import transform as warp_transform
import requests


def compute_contours(
    z: np.ndarray,
    levels: list[float],
    merge_dist: float = 20.0,
) -> dict[float, list[np.ndarray]]:
    """Marching squares: extract contour polylines from a 2D elevation grid.

    Args:
        z: 2D array (ny, nx) of elevation values.
        levels: Contour z-values to extract.
        merge_dist: Max distance (in grid cells) for polyline endpoint merging.

    Returns:
        {level: [polyline, ...]} where each polyline is an (N, 2) array
        of (x, y) coordinates in grid-cell space.
    """
    result: dict[float, list[np.ndarray]] = {}
    for level in levels:
        polylines = _marching_squares_level(z, level, merge_dist)
        if polylines:
            result[level] = polylines
    return result


def _marching_squares_level(z: np.ndarray, level: float, merge_dist: float = 20.0) -> list[np.ndarray]:
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

    return _connect_segments(segments, merge_dist)


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
    merge_dist: float = 20.0,
) -> list[np.ndarray]:
    if not segments:
        return []

    _EPSILON = 1e-6

    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}

    def _grid_cell(pt: tuple[float, float]) -> tuple[int, int]:
        return (int(pt[0] / _EPSILON), int(pt[1] / _EPSILON))

    def _canonical(pt: tuple[float, float]) -> tuple[float, float]:
        gx, gy = _grid_cell(pt)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for candidate in grid.get((gx + dx, gy + dy), []):
                    if abs(candidate[0] - pt[0]) < _EPSILON and abs(candidate[1] - pt[1]) < _EPSILON:
                        return candidate
        grid.setdefault((gx, gy), []).append(pt)
        return pt

    adj: dict[tuple[float, float], list[tuple[float, float]]] = {}
    for a, b in segments:
        ca, cb = _canonical(a), _canonical(b)
        if ca == cb:
            continue
        adj.setdefault(ca, []).append(cb)
        adj.setdefault(cb, []).append(ca)

    walked: set[frozenset[tuple[float, float]]] = set()
    polylines: list[np.ndarray] = []

    def _edge(a: tuple[float, float], b: tuple[float, float]) -> frozenset[tuple[float, float]]:
        return frozenset({a, b})

    def trace_from(start: tuple[float, float]) -> list[tuple[float, float]]:
        path = [start]
        current = start
        while True:
            candidates = [
                n for n in adj.get(current, [])
                if _edge(current, n) not in walked
            ]
            if not candidates:
                break
            next_pt = candidates[0]
            walked.add(_edge(current, next_pt))
            path.append(next_pt)
            current = next_pt
        return path

    all_vertices = set(adj.keys())

    endpoints = sorted(v for v in all_vertices if len(adj.get(v, [])) == 1)
    for ep in endpoints:
        if any(_edge(ep, n) not in walked for n in adj.get(ep, [])):
            line = trace_from(ep)
            if len(line) >= 2:
                polylines.append(np.array(line))

    for v in sorted(all_vertices):
        if any(_edge(v, n) not in walked for n in adj.get(v, [])):
            line = trace_from(v)
            if len(line) >= 2:
                polylines.append(np.array(line))

    return _merge_nearby_polylines(polylines, merge_dist)


def _merge_nearby_polylines(
    polylines: list[np.ndarray],
    merge_dist: float = 20.0,
) -> list[np.ndarray]:
    """Merge polylines whose endpoints are within merge_dist pixels.

    Connects fragments across small image gaps — consolidates without
    discarding any contour data.
    """
    if len(polylines) <= 1 or merge_dist <= 0.0:
        return polylines

    working = [pl.copy() for pl in polylines]

    changed = True
    while changed:
        changed = False
        n = len(working)

        ep_grid: dict[tuple[int, int], list[tuple[int, int]]] = {}
        for pi, pl in enumerate(working):
            for ei in (0, -1):
                pt = pl[ei]
                cell = (int(pt[0] / merge_dist), int(pt[1] / merge_dist))
                ep_grid.setdefault(cell, []).append((pi, ei))

        best_dist = merge_dist
        best_pair = None
        for pi, pl in enumerate(working):
            for ei in (0, -1):
                pt = pl[ei]
                gx, gy = int(pt[0] / merge_dist), int(pt[1] / merge_dist)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for pj, ej in ep_grid.get((gx + dx, gy + dy), []):
                            if pj <= pi:
                                continue
                            other = working[pj][ej]
                            d = float(np.sqrt(
                                (pt[0] - other[0]) ** 2 + (pt[1] - other[1]) ** 2
                            ))
                            if d < best_dist:
                                best_dist = d
                                best_pair = (pi, ei, pj, ej)

        if best_pair is not None:
            pi, ei, pj, ej = best_pair
            pla = working[pi]
            plb = working[pj]

            if ei == -1 and ej == 0:
                merged_pts = np.concatenate([pla, plb])
            elif ei == 0 and ej == -1:
                merged_pts = np.concatenate([plb, pla])
            elif ei == 0 and ej == 0:
                merged_pts = np.concatenate([pla[::-1], plb])
            else:
                merged_pts = np.concatenate([pla, plb[::-1]])

            working[pi] = merged_pts
            working.pop(pj)
            changed = True

    return working


def _gaussian_blur(z: np.ndarray, sigma: float = 0.7) -> np.ndarray:
    """Apply Gaussian blur to a 2D array using separable convolution.
    
    NaN values are filled with the array mean before blurring and
    restored afterward. Small sigma values (0.5–1.0) reduce 1‑cell
    DEM noise while preserving real elevation features.
    """
    if sigma <= 0 or z.size == 0:
        return z
    radius = int(3 * sigma + 0.5)
    if radius < 1:
        return z

    x = np.arange(-radius, radius + 1, dtype=float)
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel /= kernel.sum()

    mask = np.isnan(z)
    if mask.any():
        fill = np.nanmean(z)
        work = np.where(mask, fill, z)
    else:
        work = z

    # Pad with edge values, convolve, crop back to original shape
    padded = np.pad(work, pad_width=radius, mode="edge")
    blurred = np.apply_along_axis(
        lambda v: np.convolve(v, kernel, mode="valid"), axis=1,
        arr=padded,
    )
    blurred = np.apply_along_axis(
        lambda v: np.convolve(v, kernel, mode="valid"), axis=0,
        arr=blurred,
    )
    return np.where(mask, np.nan, blurred)


def _upsample_dem(
    z: np.ndarray,
    transform: Affine,
    factor: int = 4,
) -> tuple[np.ndarray, Affine]:
    """Upsample DEM grid by *factor* (bilinear) and return adjusted transform."""
    if factor <= 1:
        return z, transform
    ny, nx = z.shape
    fill = np.nanmean(z) if np.isnan(z).any() else 0.0
    z_filled = np.where(np.isnan(z), fill, z)
    z_filled = np.ascontiguousarray(z_filled.astype(np.float32))
    img = Image.fromarray(z_filled, mode="F")
    img_big = img.resize((nx * factor, ny * factor), Image.BILINEAR)
    z_big = np.array(img_big, dtype=np.float64).reshape(ny * factor, nx * factor)
    transform_big = Affine(
        transform.a / factor, transform.b / factor, transform.c,
        transform.d / factor, transform.e / factor, transform.f,
    )
    return z_big, transform_big


def _upsample_mask(mask: np.ndarray, factor: int = 4) -> np.ndarray:
    """Upsample boolean mask by *factor* (nearest‑neighbour)."""
    if factor <= 1:
        return mask
    ny, nx = mask.shape
    img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    img_big = img.resize((nx * factor, ny * factor), Image.NEAREST)
    return np.array(img_big, dtype=bool)


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
    """(min_lon, min_lat, max_lon, max_lat) across all green polygons.
    
    Data is stored as [lat, lon] per OSM convention.
    """
    min_lat, max_lat = 90.0, -90.0
    min_lon, max_lon = 180.0, -180.0
    found = False
    for geom in holes_geo.values():
        for ring in geom.get("green", []):
            for pt in ring:
                lat, lon = pt[0], pt[1]
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
        "bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}",
        "prodFormats": "GeoTIFF",
        "max": 200,
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
            if "1 Meter" not in item.get("title", ""):
                continue
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


def sample_green_elevation(
    green_ring: list[list[float]],
    dem_path: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, Any] | None:
    """Extract elevation grid within a green polygon.

    Args:
        green_ring: List of [lon, lat] vertices.
        dem_path: Path to cached 1m GeoTIFF.

    Returns:
        (x_2d, y_2d, z_2d, win_transform) where x/y are 2D meshgrid arrays
        in DEM CRS coordinates, z is elevation, win_transform is the
        rasterio Affine for the window. Returns None on failure.
    """
    try:
        with rasterio.open(dem_path) as src:
            xs, ys = _ring_to_crs(green_ring, src.crs)
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)

            window = rasterio.windows.from_bounds(
                min_x, min_y, max_x, max_y, src.transform
            )
            z = src.read(1, window=window, masked=True)
            z_data = z.filled(np.nan)

            win_transform = src.window_transform(window)
            nx, ny = z_data.shape[1], z_data.shape[0]

            x_1d = np.linspace(
                win_transform.c,
                win_transform.c + win_transform.a * nx,
                nx,
            )
            y_1d = np.linspace(
                win_transform.f,
                win_transform.f + win_transform.e * ny,
                ny,
            )
            x_2d, y_2d = np.meshgrid(x_1d, y_1d, indexing="xy")
            return x_2d, y_2d, z_data, win_transform
    except Exception:
        return None


def _ring_to_crs(
    ring: list[list[float]], target_crs: CRS,
) -> tuple[list[float], list[float]]:
    """Convert ring from [lat, lon] (OSM convention) to target CRS coordinates.

    rasterio.warp.transform expects source coords as (xs, ys) = (lon, lat).
    """
    lats = [pt[0] for pt in ring]
    lons = [pt[1] for pt in ring]
    xs, ys = warp_transform(CRS.from_epsg(4326), target_crs, lons, lats)
    return list(xs), list(ys)


def _grid_paths_to_crs(
    paths: list[np.ndarray],
    transform: Any,
) -> list[np.ndarray]:
    """Convert contour paths from grid-cell indices to DEM CRS coordinates."""
    a, b, c, d, e, f = (transform.a, transform.b, transform.c,
                         transform.d, transform.e, transform.f)
    result = []
    for path in paths:
        if len(path) == 0:
            continue
        xs = c + path[:, 0] * a + path[:, 1] * b
        ys = f + path[:, 0] * d + path[:, 1] * e
        result.append(np.column_stack([xs, ys]))
    return result


def _contour_paths_to_wgs84(
    paths: list[np.ndarray],
    src_crs: CRS,
) -> list[np.ndarray]:
    """Transform contour paths from DEM CRS to WGS84 [lat, lon] (OSM convention).

    rasterio.warp.transform returns (xs, ys) = (lon, lat) for EPSG:4326.
    """
    if not paths:
        return []
    try:
        result = []
        for path in paths:
            if len(path) == 0:
                continue
            xs, ys = warp_transform(
                src_crs, CRS.from_epsg(4326),
                path[:, 0].tolist(), path[:, 1].tolist(),
            )
            result.append(np.column_stack([np.array(ys), np.array(xs)]))
        return result
    except Exception:
        return paths


def _in_green_mask(
    x_2d: np.ndarray, y_2d: np.ndarray,
    z: np.ndarray,
    green_ring: list[list[float]],
    src_crs: CRS,
) -> np.ndarray | None:
    """Return boolean mask of DEM cells whose centres fall inside the green polygon."""
    from shapely import contains_xy
    from shapely.geometry import Polygon

    xs, ys = _ring_to_crs(green_ring, src_crs)
    green_poly = Polygon(list(zip(xs, ys)))

    valid = ~np.isnan(z)
    if not valid.any():
        return None

    x_flat = x_2d[valid]
    y_flat = y_2d[valid]
    contained = contains_xy(green_poly, x_flat, y_flat)

    mask = np.zeros_like(z, dtype=bool)
    mask[valid] = contained
    return mask if mask.any() else None


def compute_green_contours(
    green_ring: list[list[float]],
    dem_path: Path,
    max_contours: int = 8,
) -> dict:
    """Compute contour paths for a single green.

    Only the green's own elevation range is used for normalisation (auto‑levels),
    so subtle topography on flat greens gets the full 0‑1 contour space.
    Contour paths are smoothed downstream via Chaikin smoothing.

    Args:
        green_ring: [lat, lon] vertices of the green polygon.
        dem_path: Path to cached 1m GeoTIFF.
        max_contours: Maximum contour levels (default 8).

    Returns {"contours": [{"path": [[lat, lon], ...], "z": float}, ...]}
    or {"contours": []} if DEM data is insufficient.
    """
    sampled = sample_green_elevation(green_ring, dem_path)
    if sampled is None:
        return {"contours": []}

    x_2d, y_2d, z, win_transform = sampled

    if np.all(np.isnan(z)):
        return {"contours": []}

    # Get DEM CRS
    with rasterio.open(dem_path) as src:
        src_crs = src.crs

    # Auto-levels: compute z_min/z_max from in-green cells only
    # Falls back to full-window range if no cells intersect (test data edge case).
    green_mask = _in_green_mask(x_2d, y_2d, z, green_ring, src_crs)
    if green_mask is not None:
        z_green = z[green_mask]
        z_min, z_max = np.nanmin(z_green), np.nanmax(z_green)
    else:
        z_min, z_max = np.nanmin(z), np.nanmax(z)
    if z_max - z_min < 0.10:
        return {"contours": []}

    elevation_range = z_max - z_min
    num_contours = max(2, min(max_contours, int(elevation_range / 0.2)))

    # Upsample DEM (4x) for smoother contour paths, then blur to suppress
    # interpolation faceting that marching squares would trace as noise.
    z, win_transform = _upsample_dem(z, win_transform, factor=4)
    if green_mask is not None:
        green_mask_big = _upsample_mask(green_mask, factor=4)
    else:
        green_mask_big = None
    z = _gaussian_blur(z, sigma=1.5)

    if green_mask_big is not None:
        z_green_big = z[green_mask_big]
        z_min, z_max = np.nanmin(z_green_big), np.nanmax(z_green_big)

    z_norm = np.clip((z - z_min) / (z_max - z_min), 0.0, 1.0)

    levels = [i / (num_contours + 1) for i in range(1, num_contours + 1)]

    raw = compute_contours(z_norm, levels, merge_dist=1.0)
    if not raw:
        return {"contours": []}

    result: list[dict] = []
    z_min_f, z_max_f = float(z_min), float(z_max)
    for norm_level, grid_paths in raw.items():
        actual_z = z_min_f + float(norm_level) * (z_max_f - z_min_f)
        crs_paths = _grid_paths_to_crs(grid_paths, win_transform)
        wgs84_paths = _contour_paths_to_wgs84(crs_paths, src_crs)
        for path_array in wgs84_paths:
            if len(path_array) >= 2:
                result.append({
                    "path": [[float(x), float(y)] for x, y in path_array],
                    "z": round(actual_z, 1),
                })

    return {"contours": result}


def compute_elevation_shading(
    green_ring: list[list[float]],
    dem_path: Path,
) -> Image.Image | None:
    """Compute a grayscale elevation-shading image for a green.

    Returns a PIL.Image (mode='L', uint8, 4x upscaled + blurred)
    or None if DEM data is insufficient or range < 0.25m.
    White = highest elevation, black = lowest.
    """
    sampled = sample_green_elevation(green_ring, dem_path)
    if sampled is None:
        return None

    x_2d, y_2d, z, win_transform = sampled

    if np.all(np.isnan(z)):
        return None

    with rasterio.open(dem_path) as src:
        src_crs = src.crs

    green_mask = _in_green_mask(x_2d, y_2d, z, green_ring, src_crs)
    if green_mask is not None:
        z_green = z[green_mask]
        z_min, z_max = np.nanmin(z_green), np.nanmax(z_green)
    else:
        return None

    if z_max - z_min < 0.10:
        return None

    z, _ = _upsample_dem(z, win_transform, factor=4)
    if green_mask is not None:
        green_mask_big = _upsample_mask(green_mask, factor=4)
    else:
        green_mask_big = None
    z = _gaussian_blur(z, sigma=1.5)

    if green_mask_big is not None:
        z_green_big = z[green_mask_big]
        z_min, z_max = np.nanmin(z_green_big), np.nanmax(z_green_big)

    z_norm = np.clip((z - z_min) / (z_max - z_min), 0.0, 1.0)
    z_uint8 = (z_norm * 255).astype(np.uint8)

    return Image.fromarray(z_uint8, mode="L")


def compute_all_green_contours(course_name: str, holes_geo: dict) -> dict:
    """Compute and cache green contours for all holes in a course.

    Returns {hole_num: {"contours": [{"path": [[lat, lon], ...], "z": ...}, ...]}}
    or empty dict if DEM is unavailable.
    """
    from cartographer.data import get_contours_cache_path
    import json

    cache_path = get_contours_cache_path(course_name)
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    dem_path = get_course_dem(course_name, holes_geo)
    if dem_path is None:
        return {}

    result: dict[str, dict] = {}
    for hole_key, geom in holes_geo.items():
        greens = geom.get("green", [])
        if not greens:
            continue
        contours = compute_green_contours(greens[0], dem_path)
        if contours.get("contours"):
            result[hole_key] = contours

    cache_path.write_text(json.dumps(result))
    return result


def load_contours_cache(course_name: str) -> dict:
    """Load cached contours. Returns {} on cache miss."""
    from cartographer.data import get_contours_cache_path
    import json

    path = get_contours_cache_path(course_name)
    if path.exists():
        return json.loads(path.read_text())
    return {}
