"""Flask server for the cartographer visual tagging UI."""
from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from cartographer.data import get_osm_path, load_courses_geo_raw, save_courses_geo
from cartographer.osm import parse_osm_file, fetch_osm_features

from shapely.geometry import LineString, Polygon, MultiPolygon, Point
from shapely.ops import split as shapely_split


def _feature_to_shapely(feature: dict):
    """Convert an OSM feature dict to a shapely geometry (lon,lat coords)."""
    if feature["is_point"]:
        return Point(feature["geometry"][1], feature["geometry"][0])
    coords = [(pt[1], pt[0]) for pt in feature["geometry"]]
    if len(coords) < 3:
        return Point(coords[0])
    if feature["type"] in ("path", "waterway"):
        from shapely.geometry import LineString as LS
        return LS(coords)
    return Polygon(coords)


def _shapely_to_geojson_rings(geom) -> list[list[list[float]]]:
    """Convert a shapely Polygon or MultiPolygon to GeoJSON ring coords.

    Returns rings in [lat, lon] order (matching OSM convention).
    """
    if isinstance(geom, Polygon):
        return [[[lat, lon] for lon, lat in geom.exterior.coords]]
    if isinstance(geom, MultiPolygon):
        rings = []
        for poly in geom.geoms:
            rings.append([[lat, lon] for lon, lat in poly.exterior.coords])
        return rings
    return []


def _apply_splits(features: list[dict], split_lines: dict) -> list[dict]:
    """Apply split lines to features.

    For each split line, clips any intersecting non-course-wide feature.
    Clipped pieces are stored in `_split_pieces` as GeoJSON-ready
    coordinate lists. Pieces with area < 1% of original are discarded.

    Args:
        features: list of OSM feature dicts with osm_id, type, geometry, is_point, tags.
        split_lines: {split_id: ((lat1, lon1), (lat2, lon2))}

    Returns:
        The same features list, mutated in-place with _split_pieces added
        to intersected features.
    """
    course_wide = {"water", "waterway", "path"}

    for split_id, (p1, p2) in split_lines.items():
        split_line = LineString([(p1[1], p1[0]), (p2[1], p2[0])])  # lon,lat

        for feature in features:
            if feature["type"] in course_wide or feature["is_point"]:
                continue

            geom = _feature_to_shapely(feature)
            if isinstance(geom, Point):
                continue

            if not split_line.intersects(geom):
                continue

            pieces = list(shapely_split(geom, split_line).geoms)
            if len(pieces) < 2:
                continue

            total_area = geom.area
            min_area = total_area * 0.01 if total_area > 0 else 0

            feature["_split_pieces"] = []
            for piece in pieces:
                if isinstance(piece, (Polygon, MultiPolygon)) and piece.area >= min_area:
                    feature["_split_pieces"].append(_shapely_to_geojson_rings(piece))

    return features


def _expand_split_features(features: list[dict]) -> list[dict]:
    """Expand split features into sub-features with synthetic IDs.

    Features without _split_pieces pass through unchanged.
    Features with _split_pieces produce one sub-feature per piece,
    with osm_id like 'way/123__0', 'way/123__1' and a 'split_group'
    property linking back to the original osm_id.

    Returns a new flat list (does not mutate input).
    """
    result = []
    for feature in features:
        pieces = feature.get("_split_pieces")
        if not pieces:
            result.append(feature)
            continue

        for i, piece_coords in enumerate(pieces):
            sub = dict(feature)
            sub["osm_id"] = f"{feature['osm_id']}__{i}"
            sub["geometry"] = piece_coords[0] if len(piece_coords) == 1 else piece_coords[0]
            sub["split_group"] = feature["osm_id"]
            sub.pop("_split_pieces", None)
            result.append(sub)

    return result


def _derive_assignments(holes: dict, expanded_features: list[dict]) -> dict:
    """Derive featureAssignments from stored hole data.

    Matches feature IDs in the stored per-hole geometry dicts against
    the expanded feature list (which includes synthetic sub-feature IDs).

    Returns: {osm_id: hole_number} suitable for the frontend.
    """
    assignments = {}
    id_to_feature = {f["osm_id"]: f for f in expanded_features}

    for hole_key, hole_data in holes.items():
        hole_num = int(hole_key)
        for ftype in ("fairway", "green", "bunkers", "water",
                      "waterways", "paths", "rough_boundary"):
            items = hole_data.get(ftype, [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and "id" in item:
                        fid = item["id"]
                        if fid in id_to_feature:
                            assignments[fid] = hole_num

    return assignments


_STATIC_DIR = Path(__file__).parent / "static"


def start_tagger(course_name: str, osm_path: Path) -> threading.Event:
    """Start the tagger with a pre-resolved .osm file. No input().

    Returns a threading.Event that is set when the tagger saves or shuts down.
    The caller can poll this event to detect completion.
    """
    features = parse_osm_file(osm_path)
    existing_geo = load_courses_geo_raw().get(course_name, {})

    # Compute map bounds from golf features only (fairway, green, bunker, tee).
    # Excludes water and paths which may be huge (rivers, long cart paths) and
    # would unnecessarily zoom the view out.
    golf_types = {"fairway", "green", "bunker", "tee"}
    lats, lons = [], []
    for f in features:
        if f["type"] not in golf_types:
            continue
        if f["is_point"]:
            lats.append(f["geometry"][0])
            lons.append(f["geometry"][1])
        else:
            for pt in f["geometry"]:
                lats.append(pt[0])
                lons.append(pt[1])
    bounds = (
        {"minlat": min(lats), "minlon": min(lons), "maxlat": max(lats), "maxlon": max(lons)}
        if lats else None
    )

    app = Flask(__name__, static_folder=str(_STATIC_DIR))
    shutdown_event = threading.Event()

    split_lines = existing_geo.get("splits", {})
    app.config["split_lines"] = {
        int(sid): ((pts[0][0], pts[0][1]), (pts[1][0], pts[1][1]))
        for sid, pts in split_lines.items()
    }
    _apply_splits(features, app.config["split_lines"])

    @app.route("/")
    def index():
        return send_from_directory(_STATIC_DIR, "index.html")

    @app.route("/api/features")
    def get_features():
        """Return parsed OSM features as GeoJSON for Leaflet.

        Split features are expanded into sub-features with synthetic IDs
        and split_group property. Course-wide features are tagged."""
        expanded = _expand_split_features(features)
        geojson_features = []
        for f in expanded:
            props = {
                "osm_id": f["osm_id"],
                "type": f["type"],
                "tags": f.get("tags", {}),
            }
            if f.get("split_group"):
                props["split_group"] = f["split_group"]

            if f["is_point"]:
                geojson_features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [f["geometry"][1], f["geometry"][0]],
                    },
                    "properties": props,
                })
            else:
                coords = [[pt[1], pt[0]] for pt in f["geometry"]]
                if f["type"] in ("path", "waterway"):
                    geojson_features.append({
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": coords},
                        "properties": props,
                    })
                else:
                    geojson_features.append({
                        "type": "Feature",
                        "geometry": {"type": "Polygon", "coordinates": [coords]},
                        "properties": props,
                    })
        return jsonify({
            "type": "FeatureCollection",
            "features": geojson_features,
            "course_name": course_name,
            "bounds": bounds,
        })

    @app.route("/api/save", methods=["POST"])
    def save():
        """Receive tagged data from the UI and write courses_geo.json."""
        data = request.get_json()
        all_geo = load_courses_geo_raw()
        course_data = data

        course_data["splits"] = {
            str(sid): [[p1[0], p1[1]], [p2[0], p2[1]]]
            for sid, (p1, p2) in app.config["split_lines"].items()
        }

        all_geo[course_name] = course_data
        save_courses_geo(all_geo)
        shutdown_event.set()
        return jsonify({"status": "ok"})

    @app.route("/api/shutdown", methods=["POST"])
    def shutdown():
        shutdown_event.set()
        return jsonify({"status": "shutting down"})

    @app.route("/api/splits", methods=["GET"])
    def get_splits():
        """Return split lines as GeoJSON FeatureCollection."""
        split_features = []
        for split_id, (p1, p2) in app.config["split_lines"].items():
            split_features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[p1[1], p1[0]], [p2[1], p2[0]]],
                },
                "properties": {"split_id": split_id},
            })
        return jsonify({"type": "FeatureCollection", "features": split_features})

    @app.route("/api/splits", methods=["POST"])
    def add_split():
        """Add a split line. Body: [[lat1,lon1],[lat2,lon2]]."""
        data = request.get_json()
        p1 = (data[0][0], data[0][1])
        p2 = (data[1][0], data[1][1])

        for f in features:
            f.pop("_split_pieces", None)

        max_id = max(app.config["split_lines"].keys()) if app.config["split_lines"] else 0
        new_id = max_id + 1
        app.config["split_lines"][new_id] = (p1, p2)
        affected = _apply_splits(features, app.config["split_lines"])

        affected_ids = [
            f["osm_id"] for f in affected if "_split_pieces" in f
        ]
        return jsonify({"split_id": new_id, "affected": affected_ids})

    @app.route("/api/splits/<int:split_id>", methods=["DELETE"])
    def delete_split(split_id):
        """Remove a split line and re-merge sub-features."""
        if split_id not in app.config["split_lines"]:
            return jsonify({"error": "not found"}), 404

        del app.config["split_lines"][split_id]

        for f in features:
            f.pop("_split_pieces", None)
        _apply_splits(features, app.config["split_lines"])

        return jsonify({"status": "ok", "removed": split_id})

    @app.route("/api/assignments")
    def get_assignments():
        """Return existing feature assignments derived from saved hole data."""
        existing = load_courses_geo_raw().get(course_name, {})
        holes = existing.get("holes", {})
        expanded = _expand_split_features(features)
        return jsonify(_derive_assignments(holes, expanded))

    port = 5173
    threading.Timer(0.8, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    server_thread = threading.Thread(
        target=lambda: app.run(port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server_thread.start()

    return shutdown_event


def run_tagger(course_name: str) -> None:
    """CLI entry point. Resolves .osm file (with prompt/API fallback) then starts tagger.

    Blocks until the tagger saves or shuts down.
    """
    osm_path = get_osm_path(course_name)

    if osm_path.exists():
        print(f"  Loading cached .osm file: {osm_path}")
    else:
        answer = input(f"  No .osm file found for '{course_name}'. Fetch from OSM API? (y/n): ").strip().lower()
        if answer != "y":
            print("  To tag manually, download the .osm file from openstreetmap.org")
            print(f"  and place it at: {osm_path}")
            return
        print("  Fetching from OSM API...")
        try:
            features = fetch_osm_features(course_name, osm_path)
        except RuntimeError as e:
            print(f"  Error: {e}")
            return

    print(f"\n  Opening cartographer tagger at http://localhost:5173")
    print("  Press Save in the browser when done, or Ctrl+C to cancel.\n")

    shutdown_event = start_tagger(course_name, osm_path)
    shutdown_event.wait()
    print(f"\n  Saved geometry for '{course_name}'.")
    print(f"  Geometry written to: data/plugins/cartographer/courses_geo.json")
