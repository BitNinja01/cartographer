# plugins/cartographer/geometry.py
"""Geometry operations for Cartographer.

All input coordinates are WGS84 [lat, lon] pairs.
Output coordinates are in pixels, using an equirectangular projection
centred on the course bounding box scaled by pixels_per_yard.
"""
from __future__ import annotations

import math
from typing import Any

from shapely.geometry import Polygon


def _haversine_yards(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the distance in yards between two lat/lon points."""
    R = 6371000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    metres = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return metres * 1.09361  # metres to yards


def compute_pixels_per_yard(
    point_a: list[float],
    point_b: list[float],
    distance_yards: float,
) -> float:
    """Compute pixels_per_yard from two reference points and a known distance.

    NOTE: Not currently called by cartographer — the tagger UI computes
    pixels_per_yard directly in JavaScript from screen pixel distance.
    Retained as a utility for future headless/scripted scale calibration.

    point_a and point_b are [lat, lon] pairs.
    distance_yards is the real-world distance between them in yards.
    """
    actual_yards = _haversine_yards(point_a[0], point_a[1], point_b[0], point_b[1])
    return distance_yards / actual_yards if actual_yards > 0 else 1.0


def _latlon_to_xy(
    lat: float,
    lon: float,
    origin_lat: float,
    origin_lon: float,
    yards_per_degree_lat: float,
    yards_per_degree_lon: float,
    pixels_per_yard: float,
) -> tuple[float, float]:
    """Project a lat/lon point to pixel coordinates relative to an origin."""
    dy = (lat - origin_lat) * yards_per_degree_lat * pixels_per_yard
    dx = (lon - origin_lon) * yards_per_degree_lon * pixels_per_yard
    return dx, -dy  # flip Y so north is up


def project_ring(
    ring: list[list[float]],
    origin_lat: float,
    origin_lon: float,
    yards_per_degree_lat: float,
    yards_per_degree_lon: float,
    pixels_per_yard: float,
) -> list[tuple[float, float]]:
    """Project a polygon ring from lat/lon to pixel coordinates."""
    return [
        _latlon_to_xy(pt[0], pt[1], origin_lat, origin_lon,
                      yards_per_degree_lat, yards_per_degree_lon, pixels_per_yard)
        for pt in ring
    ]


def project_course(holes: dict, scale_data: dict) -> dict:
    """Project all hole geometry from lat/lon to pixel coordinates.

    Returns a new dict with the same structure as holes but with pixel
    coordinates instead of lat/lon.

    scale_data must contain 'pixels_per_yard'.
    """
    pixels_per_yard = float(scale_data["pixels_per_yard"])

    # Collect all lat/lon points to find course centroid for projection origin
    all_lats, all_lons = [], []
    for hole_data in holes.values():
        for feature_type in ("fairway", "green", "bunkers", "water", "rough_boundary"):
            for ring in hole_data.get(feature_type, []):
                for pt in ring:
                    all_lats.append(pt[0])
                    all_lons.append(pt[1])
        for pt in hole_data.get("tee_boxes", {}).values():
            all_lats.append(pt[0])
            all_lons.append(pt[1])

    if not all_lats:
        return holes

    origin_lat = sum(all_lats) / len(all_lats)
    origin_lon = sum(all_lons) / len(all_lons)

    # Compute metres per degree at this latitude
    metres_per_degree_lat = 111132.0
    metres_per_degree_lon = 111320.0 * math.cos(math.radians(origin_lat))
    yards_per_degree_lat = metres_per_degree_lat * 1.09361
    yards_per_degree_lon = metres_per_degree_lon * 1.09361

    projected = {}
    for hole_num, hole_data in holes.items():
        ph: dict[str, Any] = {}

        for feature_type in ("fairway", "green", "bunkers", "water", "rough_boundary"):
            rings = hole_data.get(feature_type, [])
            ph[feature_type] = [
                project_ring(ring, origin_lat, origin_lon,
                             yards_per_degree_lat, yards_per_degree_lon, pixels_per_yard)
                for ring in rings
            ]

        tee_boxes = {}
        for tee_name, pt in hole_data.get("tee_boxes", {}).items():
            tee_boxes[tee_name] = _latlon_to_xy(
                pt[0], pt[1], origin_lat, origin_lon,
                yards_per_degree_lat, yards_per_degree_lon, pixels_per_yard
            )
        ph["tee_boxes"] = tee_boxes

        projected[hole_num] = ph

    return projected


def get_hole_bounds(hole_geom: dict) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) bounding box for a projected hole."""
    all_x, all_y = [], []
    for feature_type in ("fairway", "green", "bunkers", "water", "rough_boundary"):
        for ring in hole_geom.get(feature_type, []):
            for x, y in ring:
                all_x.append(x)
                all_y.append(y)
    for x, y in hole_geom.get("tee_boxes", {}).values():
        all_x.append(x)
        all_y.append(y)
    if not all_x:
        return 0.0, 0.0, 100.0, 100.0
    return min(all_x), min(all_y), max(all_x), max(all_y)


def get_green_centroid(hole_geom: dict) -> tuple[float, float]:
    """Return the centroid (cx, cy) of the green polygon(s) in pixel coordinates."""
    rings = hole_geom.get("green", [])
    if not rings:
        min_x, min_y, max_x, max_y = get_hole_bounds(hole_geom)
        return (min_x + max_x) / 2, (min_y + max_y) / 2

    polys = []
    for ring in rings:
        if len(ring) >= 3:
            try:
                polys.append(Polygon(ring))
            except Exception:
                pass

    if not polys:
        min_x, min_y, max_x, max_y = get_hole_bounds(hole_geom)
        return (min_x + max_x) / 2, (min_y + max_y) / 2

    union = polys[0]
    for p in polys[1:]:
        union = union.union(p)
    c = union.centroid
    return c.x, c.y


def fit_hole(
    hole_geom: dict,
    canvas_width: float,
    canvas_height: float,
    padding: float = 20.0,
) -> tuple[dict, float, float, float]:
    """Rotate hole so green faces top, then scale and centre within canvas bounds.

    Returns (transformed_hole_geom, offset_x, offset_y, scale_factor).
    The returned geom has coordinates ready for SVG rendering.
    scale_factor is the ratio applied to project_course coordinates to fit
    the canvas — needed by callers that compute distances in canvas space.
    """
    green_cx, green_cy = get_green_centroid(hole_geom)
    min_x, min_y, max_x, max_y = get_hole_bounds(hole_geom)
    hole_cx = (min_x + max_x) / 2
    hole_cy = (min_y + max_y) / 2

    dx = green_cx - hole_cx
    dy = green_cy - hole_cy
    angle_to_green = math.degrees(math.atan2(dy, dx))
    # We want green at top = -90 degrees in SVG coords
    rotation_deg = -90.0 - angle_to_green

    def rotate_point(px: float, py: float) -> tuple[float, float]:
        rad = math.radians(rotation_deg)
        rx = (px - hole_cx) * math.cos(rad) - (py - hole_cy) * math.sin(rad) + hole_cx
        ry = (px - hole_cx) * math.sin(rad) + (py - hole_cy) * math.cos(rad) + hole_cy
        return rx, ry

    def rotate_ring(ring: list) -> list:
        return [list(rotate_point(x, y)) for x, y in ring]

    rotated: dict[str, Any] = {}
    for feature_type in ("fairway", "green", "bunkers", "water", "rough_boundary"):
        rotated[feature_type] = [rotate_ring(r) for r in hole_geom.get(feature_type, [])]
    rotated["tee_boxes"] = {
        name: list(rotate_point(x, y))
        for name, (x, y) in hole_geom.get("tee_boxes", {}).items()
    }

    min_x, min_y, max_x, max_y = get_hole_bounds(rotated)
    geom_w = max_x - min_x or 1.0
    geom_h = max_y - min_y or 1.0
    avail_w = canvas_width - 2 * padding
    avail_h = canvas_height - 2 * padding
    scale_factor = min(avail_w / geom_w, avail_h / geom_h)

    offset_x = padding + (avail_w - geom_w * scale_factor) / 2 - min_x * scale_factor
    offset_y = padding + (avail_h - geom_h * scale_factor) / 2 - min_y * scale_factor

    def transform_point(px: float, py: float) -> tuple[float, float]:
        return px * scale_factor + offset_x, py * scale_factor + offset_y

    def transform_ring(ring: list) -> list:
        return [list(transform_point(x, y)) for x, y in ring]

    fitted: dict[str, Any] = {}
    for feature_type in ("fairway", "green", "bunkers", "water", "rough_boundary"):
        fitted[feature_type] = [transform_ring(r) for r in rotated.get(feature_type, [])]
    fitted["tee_boxes"] = {
        name: list(transform_point(x, y))
        for name, (x, y) in rotated.get("tee_boxes", {}).items()
    }

    return fitted, offset_x, offset_y, scale_factor


def compute_yardage_arcs(
    green_centroid: tuple[float, float],
    distances_yards: list[int],
    pixels_per_yard: float,
    scale_factor: float = 1.0,
) -> list[tuple[float, float, float]]:
    """Return list of (cx, cy, radius_px) for yardage arc circles.

    green_centroid: pixel coords of green centre after fit_hole transform.
    distances_yards: e.g. [100, 125, 150, 175, 200].
    pixels_per_yard: from scale_data, already applied during project_course.
    scale_factor: the scale factor applied during fit_hole.
    """
    cx, cy = green_centroid
    return [
        (cx, cy, dist * pixels_per_yard * scale_factor)
        for dist in distances_yards
    ]
