"""Flask server for the cartographer visual tagging UI."""
from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from cartographer.data import get_osm_path, load_courses_geo, save_courses_geo
from cartographer.osm import parse_osm_file, fetch_osm_features

_STATIC_DIR = Path(__file__).parent / "static"


def run_tagger(course_name: str) -> None:
    """Start the Flask tagging server for a course and open the browser."""
    osm_path = get_osm_path(course_name)

    # Resolve OSM data
    if osm_path.exists():
        print(f"  Loading cached .osm file: {osm_path}")
        features = parse_osm_file(osm_path)
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

    # Load existing geo data for this course (for re-tagging)
    existing_geo = load_courses_geo().get(course_name, {})

    app = Flask(__name__, static_folder=str(_STATIC_DIR))
    shutdown_event = threading.Event()

    @app.route("/")
    def index():
        return send_from_directory(_STATIC_DIR, "index.html")

    @app.route("/api/features")
    def get_features():
        """Return parsed OSM features as GeoJSON for Leaflet."""
        geojson_features = []
        for f in features:
            if f["is_point"]:
                geojson_features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [f["geometry"][1], f["geometry"][0]]},
                    "properties": {"osm_id": f["osm_id"], "type": f["type"], "tags": f["tags"]},
                })
            else:
                coords = [[pt[1], pt[0]] for pt in f["geometry"]]
                geojson_features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                    "properties": {"osm_id": f["osm_id"], "type": f["type"], "tags": f["tags"]},
                })
        return jsonify({
            "type": "FeatureCollection",
            "features": geojson_features,
            "course_name": course_name,
            "existing": existing_geo,
        })

    @app.route("/api/save", methods=["POST"])
    def save():
        """Receive tagged data from the UI and write courses_geo.json."""
        data = request.get_json()
        all_geo = load_courses_geo()
        all_geo[course_name] = data
        save_courses_geo(all_geo)
        shutdown_event.set()
        return jsonify({"status": "ok"})

    @app.route("/api/shutdown", methods=["POST"])
    def shutdown():
        shutdown_event.set()
        return jsonify({"status": "shutting down"})

    port = 5173
    print(f"\n  Opening cartographer tagger at http://localhost:{port}")
    print("  Press Save in the browser when done, or Ctrl+C to cancel.\n")

    threading.Timer(0.8, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    server_thread = threading.Thread(
        target=lambda: app.run(port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server_thread.start()

    shutdown_event.wait()
    print(f"\n  Saved geometry for '{course_name}'.")
    print(f"  Geometry written to: data/plugins/cartographer/courses_geo.json")
