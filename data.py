"""Data access layer for pinsheet-cartographer.

All files read/written by cartographer live under data/plugins/cartographer/.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def _get_plugin_data_dir() -> Path:
    """Resolve data/plugins/cartographer/, creating it if needed."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent / "data"
    else:
        base = Path(__file__).parent.parent.parent / "data"
    d = base / "plugins" / "cartographer"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_plugin_data_dir() -> Path:
    """Return the cartographer data directory, creating it if needed."""
    return _get_plugin_data_dir()


def get_osm_path(course_name: str) -> Path:
    """Return the path to the cached .osm file for a course."""
    osm_dir = _get_plugin_data_dir() / "osm"
    osm_dir.mkdir(exist_ok=True)
    return osm_dir / f"{course_name}.osm"


def load_courses_geo() -> dict:
    """Load courses_geo.json. Returns empty dict if file doesn't exist."""
    path = _get_plugin_data_dir() / "courses_geo.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_courses_geo(data: dict) -> None:
    """Write courses_geo.json."""
    path = _get_plugin_data_dir() / "courses_geo.json"
    path.write_text(json.dumps(data, indent=2))


def get_dem_path(course_name: str) -> Path:
    """Return path to cached course DEM GeoTIFF."""
    dem_dir = _get_plugin_data_dir() / "dem"
    dem_dir.mkdir(exist_ok=True)
    return dem_dir / f"{_course_hash(course_name)}.tif"


def get_contours_cache_path(course_name: str) -> Path:
    """Return path to cached contour data JSON."""
    dem_dir = _get_plugin_data_dir() / "dem"
    dem_dir.mkdir(exist_ok=True)
    return dem_dir / f"{_course_hash(course_name)}_contours.json"


def _course_hash(course_name: str) -> str:
    return hashlib.sha256(course_name.encode()).hexdigest()[:16]
