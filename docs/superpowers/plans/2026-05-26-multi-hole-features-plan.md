# Multi-Hole Feature Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to split shared greens and fairways across multiple holes via a split-line tool in the tagger, with zero changes to the geometry/render/PDF pipeline.

**Architecture:** Add a split-line drawing tool to the tagger UI that clips OSM polygons server-side using shapely. Split sub-features get synthetic IDs and slot into the existing one-to-one assignment flow. `data.py` gains raw vs. normalized load paths to preserve feature IDs in the saved JSON while keeping downstream consumers unchanged.

**Tech Stack:** Python 3.11+, Flask, shapely, Leaflet.js, GeoJSON

---

### Task 1: data.py — add `load_courses_geo_raw()` and normalize `load_courses_geo()`

**Files:**
- Modify: `data.py:36-41`

**Goal:** Split the current `load_courses_geo()` into two paths: raw (for the tagger's save/load cycle, preserves `{"id":...,"rings":...}` wrappers) and normalized (bare ring lists for geometry/render/PDF consumers).

- [ ] **Step 1: Rename current `load_courses_geo` to `_read_raw` and add `load_courses_geo_raw`**

Replace `load_courses_geo()` (lines 36-41) with:

```python
def _read_raw() -> dict:
    """Read courses_geo.json as-is. Returns empty dict if file doesn't exist."""
    path = _get_plugin_data_dir() / "courses_geo.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def load_courses_geo_raw() -> dict:
    """Read courses_geo.json with all metadata preserved (IDs, splits).
    
    Used by the tagger server for assignment reconstruction and
    the save/load cycle. Returns the raw JSON dict including feature
    IDs and split lines.
    """
    return _read_raw()
```

- [ ] **Step 2: Add `_normalize_hole_features()` and new `load_courses_geo()`**

Add after `load_courses_geo_raw()`:

```python
def _normalize_hole_features(hole_data: dict) -> dict:
    """Normalize per-hole feature data to bare ring lists.

    Handles both old format (bare [[[lat,lon],...]] rings) and new
    format ([{"id":"...", "rings":[[...]]}, ...]).
    """
    feature_types = ("fairway", "green", "bunkers", "water",
                     "waterways", "paths", "rough_boundary")
    normalized = {}
    for ftype in feature_types:
        items = hole_data.get(ftype, [])
        if not items:
            normalized[ftype] = []
            continue
        if isinstance(items[0], dict) and "rings" in items[0]:
            normalized[ftype] = [item["rings"] for item in items]
        else:
            normalized[ftype] = items
    normalized["tee_boxes"] = hole_data.get("tee_boxes", {})
    return normalized


def load_courses_geo() -> dict:
    """Load courses_geo.json, normalized to bare ring lists.

    Old-format data (bare [[[lat,lon]]] rings) passes through unchanged.
    New-format data ([{"id":"...","rings":[[...]]}]) has rings extracted
    and IDs discarded. Returns a dict suitable for geometry/render/PDF.
    """
    raw = _read_raw()
    normalized = {}
    for course_name, course_data in raw.items():
        norm = dict(course_data)
        if "holes" in norm:
            norm["holes"] = {
                hk: _normalize_hole_features(hd)
                for hk, hd in norm["holes"].items()
            }
        normalized[course_name] = norm
    return normalized
```

- [ ] **Step 3: Verify compile**

```bash
python -m py_compile data.py
```

- [ ] **Step 4: Commit**

```bash
git add data.py
git commit -m "feat: add load_courses_geo_raw and normalize load_courses_geo"
```

---

### Task 2: test_data.py — add tests for old/new format loading

**Files:**
- Modify: `tests/test_data.py`

**Goal:** Verify `load_courses_geo_normalized` handles old (bare rings) and new (id-wrapped rings) formats, and that `load_courses_geo_raw` preserves IDs.

- [ ] **Step 1: Add imports and test classes**

Append to `tests/test_data.py`:

```python
class TestLoadCoursesGeoNormalized:
    """load_courses_geo — returns bare ring lists."""

    def test_old_format_passthrough(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cartographer.data._get_plugin_data_dir", lambda: tmp_path)
        data = {
            "Course": {
                "holes": {
                    "1": {"green": [[[0, 0], [10, 0], [10, 10]]]},
                    "2": {"fairway": [[[0, 0], [20, 0], [20, 20]]]},
                }
            }
        }
        (tmp_path / "courses_geo.json").write_text(json.dumps(data))
        result = load_courses_geo()
        assert result["Course"]["holes"]["1"]["green"] == [[[0, 0], [10, 0], [10, 10]]]

    def test_new_format_extracts_rings(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cartographer.data._get_plugin_data_dir", lambda: tmp_path)
        data = {
            "Course": {
                "splits": {"1": [[0, 0], [1, 1]]},
                "holes": {
                    "7": {
                        "green": [
                            {"id": "way/501234__0", "rings": [[[0, 0], [10, 0], [10, 10]]]},
                            {"id": "way/502345", "rings": [[[5, 5], [15, 5], [15, 15]]]},
                        ]
                    }
                }
            }
        }
        (tmp_path / "courses_geo.json").write_text(json.dumps(data))
        result = load_courses_geo()
        green = result["Course"]["holes"]["7"]["green"]
        assert green == [[[0, 0], [10, 0], [10, 10]], [[5, 5], [15, 5], [15, 15]]]

    def test_load_courses_geo_preserves_tee_boxes(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cartographer.data._get_plugin_data_dir", lambda: tmp_path)
        data = {
            "Course": {
                "holes": {
                    "1": {"tee_boxes": {"white": [0, 0], "blue": [1, 1]}}
                }
            }
        }
        (tmp_path / "courses_geo.json").write_text(json.dumps(data))
        result = load_courses_geo()
        assert result["Course"]["holes"]["1"]["tee_boxes"] == {"white": [0, 0], "blue": [1, 1]}

    def test_handles_empty_hole(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cartographer.data._get_plugin_data_dir", lambda: tmp_path)
        data = {"Course": {"holes": {"1": {}}}}
        (tmp_path / "courses_geo.json").write_text(json.dumps(data))
        result = load_courses_geo()
        hole = result["Course"]["holes"]["1"]
        assert hole["fairway"] == []
        assert hole["green"] == []
        assert hole["tee_boxes"] == {}


class TestLoadCoursesGeoRaw:
    """load_courses_geo_raw — preserves IDs and splits."""

    def test_preserves_ids(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cartographer.data._get_plugin_data_dir", lambda: tmp_path)
        data = {
            "Course": {
                "splits": {"1": [[0, 0], [1, 1]]},
                "holes": {
                    "7": {
                        "green": [
                            {"id": "way/501234__0", "rings": [[[0, 0], [10, 0], [10, 10]]]},
                        ]
                    }
                }
            }
        }
        (tmp_path / "courses_geo.json").write_text(json.dumps(data))
        result = load_courses_geo_raw()
        assert result["Course"]["splits"] == {"1": [[0, 0], [1, 1]]}
        green = result["Course"]["holes"]["7"]["green"]
        assert green[0]["id"] == "way/501234__0"
        assert green[0]["rings"] == [[[0, 0], [10, 0], [10, 10]]]
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
PYTHONPATH=source:plugins pytest plugins/cartographer/tests/test_data.py -v
```
Expected: 5 new tests pass + existing tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_data.py
git commit -m "test: add normalized/raw load tests for new courses_geo format"
```

---

### Task 3: server.py — `_apply_splits()` pure function

**Files:**
- Modify: `tagger/server.py`

**Goal:** Add a pure function that clips OSM features using shapely split lines. This is testable in isolation (no Flask state needed).

- [ ] **Step 1: Add the function**

Add after the imports (around line 12):

```python
from shapely.geometry import LineString, Polygon, MultiPolygon, Point
from shapely.ops import split as shapely_split


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


def _feature_to_shapely(feature: dict):
    """Convert an OSM feature dict to a shapely geometry (lon,lat coords)."""
    coords = [(pt[1], pt[0]) for pt in feature["geometry"]]
    if feature["is_point"]:
        return Point(coords[0])
    if len(coords) < 3:
        return Point(coords[0])
    if feature["type"] in ("path", "waterway"):
        from shapely.geometry import LineString as LS
        return LS(coords)
    first = coords[0]
    last = coords[-1]
    if abs(first[0] - last[0]) > 1e-9 or abs(first[1] - last[1]) > 1e-9:
        return Polygon(coords)
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
```

- [ ] **Step 2: Verify compile**

```bash
python -m py_compile tagger/server.py
```

- [ ] **Step 3: Commit**

```bash
git add tagger/server.py
git commit -m "feat: add _apply_splits for server-side polygon clipping"
```

---

### Task 4: test_geometry.py — shapely split tests

**Files:**
- Modify: `tests/test_geometry.py`

**Goal:** Test `_apply_splits` in isolation — normal split, grazing line, sliver discard, MultiPolygon, course-wide feature exclusion.

- [ ] **Step 1: Add test class**

Append to `tests/test_geometry.py`:

```python
from cartographer.tagger.server import _apply_splits


class TestApplySplits:
    """_apply_splits — server-side polygon clipping."""

    def _make_feature(self, osm_id, ftype, coords):
        return {
            "osm_id": osm_id,
            "type": ftype,
            "geometry": coords,
            "is_point": False,
            "tags": {},
        }

    def test_splits_simple_polygon(self):
        features = [
            self._make_feature("way/1", "fairway", [
                [0, 0], [0, 10], [10, 10], [10, 0], [0, 0]
            ]),
        ]
        split_lines = {"1": ((5, -1), (5, 11))}
        result = _apply_splits(features, split_lines)
        assert "_split_pieces" in result[0]
        assert len(result[0]["_split_pieces"]) == 2

    def test_grazing_line_does_not_split(self):
        features = [
            self._make_feature("way/1", "fairway", [
                [0, 0], [0, 10], [10, 10], [10, 0], [0, 0]
            ]),
        ]
        split_lines = {"1": ((10, 0), (10, 1))}  # touches edge only
        result = _apply_splits(features, split_lines)
        assert "_split_pieces" not in result[0]

    def test_course_wide_features_excluded(self):
        features = [
            self._make_feature("way/1", "water", [
                [0, 0], [0, 10], [10, 10], [10, 0], [0, 0]
            ]),
        ]
        split_lines = {"1": ((5, -1), (5, 11))}
        result = _apply_splits(features, split_lines)
        assert "_split_pieces" not in result[0]

    def test_discards_slivers(self):
        features = [
            self._make_feature("way/1", "fairway", [
                [0, 0], [0, 10], [10, 10], [10, 0], [0, 0]
            ]),
        ]
        # Split line near the edge should produce one tiny and one large piece
        split_lines = {"1": ((0.02, 0), (0.02, 10))}
        result = _apply_splits(features, split_lines)
        pieces = result[0].get("_split_pieces", [])
        assert len(pieces) <= 1  # sliver discarded

    def test_no_splits_returns_unchanged(self):
        features = [
            self._make_feature("way/1", "fairway", [
                [0, 0], [0, 10], [10, 10], [10, 0], [0, 0]
            ]),
        ]
        result = _apply_splits(features, {})
        assert "_split_pieces" not in result[0]
```

- [ ] **Step 2: Run tests**

```bash
PYTHONPATH=source:plugins pytest plugins/cartographer/tests/test_geometry.py::TestApplySplits -v
```
Expected: 5 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_geometry.py
git commit -m "test: add shapely split tests for _apply_splits"
```

---

### Task 5: server.py — `_expand_split_features()` pure function

**Files:**
- Modify: `tagger/server.py`

**Goal:** Add a function that expands split features into sub-feature dicts with synthetic IDs (`way/123__0`, `way/123__1`).

- [ ] **Step 1: Add the function**

Add after `_apply_splits()`:

```python
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
```

- [ ] **Step 2: Verify compile**

```bash
python -m py_compile tagger/server.py
```

- [ ] **Step 3: Commit**

```bash
git add tagger/server.py
git commit -m "feat: add _expand_split_features for synthetic ID generation"
```

---

### Task 6: test_osm.py — sub-feature ID generation tests

**Files:**
- Modify: `tests/test_osm.py`

**Goal:** Test `_expand_split_features` — split expansion with single and multiple pieces, unchanged pass-through.

- [ ] **Step 1: Add test class**

Append to `tests/test_osm.py`:

```python
from cartographer.tagger.server import _expand_split_features


class TestExpandSplitFeatures:
    """_expand_split_features — synthetic ID generation."""

    def _make_feature(self, osm_id, ftype, coords, split_pieces=None):
        feat = {
            "osm_id": osm_id,
            "type": ftype,
            "geometry": coords,
            "is_point": False,
            "tags": {},
        }
        if split_pieces:
            feat["_split_pieces"] = split_pieces
        return feat

    def test_no_splits_passthrough(self):
        features = [
            self._make_feature("way/1", "fairway", [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]),
        ]
        result = _expand_split_features(features)
        assert len(result) == 1
        assert result[0]["osm_id"] == "way/1"

    def test_split_produces_two_sub_features(self):
        features = [
            self._make_feature("way/1", "green", [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
                               split_pieces=[
                                   [[[0, 0], [5, 0], [5, 10], [0, 10], [0, 0]]],
                                   [[[5, 0], [10, 0], [10, 10], [5, 10], [5, 0]]],
                               ]),
        ]
        result = _expand_split_features(features)
        assert len(result) == 2
        assert result[0]["osm_id"] == "way/1__0"
        assert result[1]["osm_id"] == "way/1__1"
        assert result[0]["split_group"] == "way/1"
        assert result[1]["split_group"] == "way/1"
        assert "_split_pieces" not in result[0]

    def test_mixed_split_and_unsplit(self):
        features = [
            self._make_feature("way/1", "fairway", [[0, 0], [10, 0], [10, 10]]),
            self._make_feature("way/2", "green", [[20, 20], [30, 20], [30, 30]],
                               split_pieces=[
                                   [[[20, 20], [25, 20], [25, 30]]],
                                   [[[25, 20], [30, 20], [30, 30]]],
                               ]),
        ]
        result = _expand_split_features(features)
        assert len(result) == 3
        ids = {f["osm_id"] for f in result}
        assert ids == {"way/1", "way/2__0", "way/2__1"}

    def test_preserves_feature_type(self):
        features = [
            self._make_feature("way/1", "bunker", [[0, 0], [10, 10]],
                               split_pieces=[
                                   [[[0, 0], [5, 5]]],
                                   [[[5, 5], [10, 10]]],
                               ]),
        ]
        result = _expand_split_features(features)
        assert result[0]["type"] == "bunker"
        assert result[1]["type"] == "bunker"
```

- [ ] **Step 2: Run tests**

```bash
PYTHONPATH=source:plugins pytest plugins/cartographer/tests/test_osm.py::TestExpandSplitFeatures -v
```
Expected: 4 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_osm.py
git commit -m "test: add sub-feature ID generation tests for _expand_split_features"
```

---

### Task 7: server.py — split endpoints (GET/POST/DELETE /api/splits)

**Files:**
- Modify: `tagger/server.py`

**Goal:** Add API endpoints for managing split lines. In-memory state stored in `app.config["split_lines"]`.

- [ ] **Step 1: Initialize split state and add endpoints**

In `start_tagger()`, after `app = Flask(...)` (after line 45), add:

```python
    split_lines = existing_geo.get("splits", {})
    # Convert from JSON-stored [[lat,lon],[lat,lon]] to ((lat,lon),(lat,lon))
    app.config["split_lines"] = {
        int(sid): ((pts[0][0], pts[0][1]), (pts[1][0], pts[1][1]))
        for sid, pts in split_lines.items()
    }
    # Apply splits to features on startup
    _apply_splits(features, app.config["split_lines"])
```

Add endpoints after `shutdown()` (after line 98, before the `port = 5173` line):

```python
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

        # Clear existing split pieces and re-apply all splits
        for f in features:
            f.pop("_split_pieces", None)

        max_id = max(app.config["split_lines"].keys()) if app.config["split_lines"] else 0
        new_id = max_id + 1
        app.config["split_lines"][new_id] = (p1, p2)
        affected = _apply_splits(features, app.config["split_lines"])

        # Collect affected feature IDs
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

        # Re-apply remaining splits
        for f in features:
            f.pop("_split_pieces", None)
        _apply_splits(features, app.config["split_lines"])

        return jsonify({"status": "ok", "removed": split_id})
```

- [ ] **Step 2: Update `get_features()` to use expanded features**

Replace the `allFeatures` assignment in... wait, this is in JS. The server needs to return expanded features. Modify `get_features()`:

Replace the existing `get_features()` body (lines 55-83) with:

```python
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
```

- [ ] **Step 3: Update save handler to persist splits**

Modify the `save()` handler (lines 85-93):

```python
    @app.route("/api/save", methods=["POST"])
    def save():
        """Receive tagged data from the UI and write courses_geo.json."""
        data = request.get_json()
        all_geo = load_courses_geo_raw()
        course_data = data

        # Include current splits in saved course data
        course_data["splits"] = {
            str(sid): [[p1[0], p1[1]], [p2[0], p2[1]]]
            for sid, (p1, p2) in app.config["split_lines"].items()
        }

        all_geo[course_name] = course_data
        save_courses_geo(all_geo)
        shutdown_event.set()
        return jsonify({"status": "ok"})
```

Also update the import line to include `load_courses_geo_raw`:

Replace line 10:
```python
from cartographer.data import get_osm_path, load_courses_geo, save_courses_geo
```
With:
```python
from cartographer.data import get_osm_path, load_courses_geo_raw, save_courses_geo
```

- [ ] **Step 4: Verify compile**

```bash
python -m py_compile tagger/server.py
```

- [ ] **Step 5: Commit**

```bash
git add tagger/server.py
git commit -m "feat: add split API endpoints and update get_features/save handlers"
```

---

### Task 7b: server.py — assignment reconstruction on page load

**Files:**
- Modify: `tagger/server.py`

**Goal:** After applying splits to OSM data at startup, derive the `featureAssignments` map from stored hole data IDs and embed it in the page template. This fixes the current behavior where assignments are lost on page reload.

- [ ] **Step 1: Add `_derive_assignments()` helper**

Add after `_expand_split_features()`:

```python
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
```

- [ ] **Step 2: Add `/api/assignments` endpoint**

Add after the split endpoints (after `delete_split`, before `port = 5173`):

```python
    @app.route("/api/assignments")
    def get_assignments():
        """Return existing feature assignments derived from saved hole data."""
        existing = load_courses_geo_raw().get(course_name, {})
        holes = existing.get("holes", {})
        expanded = _expand_split_features(features)
        return jsonify(_derive_assignments(holes, expanded))
```

- [ ] **Step 3: Verify compile**

```bash
python -m py_compile tagger/server.py
```

- [ ] **Step 4: Commit**

```bash
git add tagger/server.py
git commit -m "feat: add assignment reconstruction endpoint for page reload"
```

---

### Task 8: index.html — split mode toggle button and CSS

**Files:**
- Modify: `tagger/static/index.html`

**Goal:** Add a split mode toggle button to the toolbar and the CSS styles for split mode.

- [ ] **Step 1: Add CSS for split mode**

Add after the existing button styles (after `.hidden` block, around line 332):

```css
    #btn-split-mode {
      background: var(--surface-elevated);
      color: var(--muted);
      border: 1px solid var(--border);
      border-radius: 6px;
      cursor: pointer;
      font-family: var(--font-mono);
      font-size: 12px;
      font-weight: 600;
      padding: 8px 14px;
      transition: all 0.15s;
    }

    #btn-split-mode:hover {
      background: var(--border);
      color: var(--fg);
    }

    #btn-split-mode.active {
      background: var(--danger);
      color: white;
      border-color: var(--danger);
    }

    .split-line {
      stroke-dasharray: 8 4;
    }
```

- [ ] **Step 2: Add split mode button HTML**

Add in the `<div id="controls">` section, before the Save button (after line 374):

```html
  <div id="controls">
    <button id="btn-split-mode">Split Mode</button>
    <button id="btn-save">Save &amp; Close</button>
  </div>
```

- [ ] **Step 3: Add split mode JS state and toggle logic**

Add after the existing JS variable declarations (after `let allFeatures = [];` on line 394):

```javascript
  let splitModeActive = false;
  const splitMarkers = [];
  const splitLineLayers = [];
```

Add the toggle handler after `setCurrentHole(1);` (after line 427):

```javascript
  document.getElementById('btn-split-mode').onclick = () => {
    splitModeActive = !splitModeActive;
    const btn = document.getElementById('btn-split-mode');
    if (splitModeActive) {
      btn.textContent = '\u2715 Exit Split';
      btn.className = 'active';
      map.getContainer().style.cursor = 'crosshair';
    } else {
      btn.textContent = 'Split Mode';
      btn.className = '';
      map.getContainer().style.cursor = '';
      clearSplitMarkers();
    }
  };

  // Load existing assignments from saved data (survives page reload)
  fetch('/api/assignments')
    .then(r => r.json())
    .then(assignments => {
      Object.assign(featureAssignments, assignments);
      // Re-render feature list with loaded assignments
      renderFeatureList(allFeatures);
    });
```

- [ ] **Step 4: Commit**

```bash
git add tagger/static/index.html
git commit -m "feat: add split mode toggle button and CSS"
```

---

### Task 9: index.html — line drawing interaction

**Files:**
- Modify: `tagger/static/index.html`

**Goal:** Implement the two-click split line drawing with draggable markers.

- [ ] **Step 1: Add line drawing functions**

Add after the split mode toggle handler from Task 8:

```javascript
  function clearSplitMarkers() {
    splitMarkers.forEach(m => map.removeLayer(m));
    splitMarkers.length = 0;
    splitLineLayers.forEach(l => map.removeLayer(l));
    splitLineLayers.length = 0;
  }

  function addSplitLine(p1, p2) {
    fetch('/api/splits', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify([[p1.lat, p1.lng], [p2.lat, p2.lng]]),
    }).then(r => r.json()).then(data => {
      if (data.split_id) {
        const line = L.polyline([p1, p2], {
          color: '#e53935', weight: 2, dashArray: '8 4',
          interactive: false,
        }).addTo(map);
        splitLineLayers.push(line);

        // Clear assignments for affected (now-split) features
        (data.affected || []).forEach(orig_id => {
          Object.keys(featureAssignments).forEach(k => {
            if (k.startsWith(orig_id)) delete featureAssignments[k];
          });
        });
        refreshFeatures();
      }
    });
  }

  function refreshFeatures() {
    fetch('/api/features')
      .then(r => r.json())
      .then(data => {
        // Remove old layers from map
        Object.values(layers).forEach(l => map.removeLayer(l));
        Object.keys(layers).forEach(k => delete layers[k]);
        // Re-render from fresh feature data
        const geojsonLayer = L.geoJSON(data, {
          style: feature => {
            const ftype = feature.properties.type;
            const courseWide = ftype === 'water' || ftype === 'waterway' || ftype === 'path';
            return {
              color: typeColours[ftype] || '#888',
              fillColor: typeColours[ftype] || '#888',
              fillOpacity: 0.4,
              weight: 2,
              interactive: !courseWide && !splitModeActive,
            };
          },
          pointToLayer: (feature, latlng) => L.circleMarker(latlng, {
            radius: 6,
            fillColor: typeColours[feature.properties.type] || '#888',
            color: '#000', weight: 1, fillOpacity: 0.8,
          }),
          onEachFeature: (feature, layer) => {
            const id = feature.properties.osm_id;
            const ftype = feature.properties.type;
            if (ftype === 'unclassified') return;
            layers[id] = layer;
            layer.on('click', e => {
              if (splitModeActive) return;
              if (ftype === 'water' || ftype === 'waterway' || ftype === 'path') return;
              if (featureAssignments[id]) {
                delete featureAssignments[id];
                map.addLayer(layer);
                renderFeatureList(allFeatures);
                return;
              }
              if (currentHole >= 1 && currentHole <= 18) {
                featureAssignments[id] = currentHole;
                map.removeLayer(layer);
                renderFeatureList(allFeatures);
              }
            });
          },
        }).addTo(map);
        allFeatures = data.features;
        renderFeatureList(allFeatures);
        // Reload split lines
        fetch('/api/splits')
          .then(r => r.json())
          .then(data => {
            clearSplitMarkers();
            (data.features || []).forEach(f => {
              const coords = f.geometry.coordinates;
              const line = L.polyline([[coords[0][1], coords[0][0]], [coords[1][1], coords[1][0]]], {
                color: '#e53935', weight: 2, dashArray: '8 4',
                interactive: false,
              }).addTo(map);
              splitLineLayers.push(line);
            });
          });
      });
  }
```

- [ ] **Step 2: Add map click handler for split mode**

Add after `clearSplitMarkers` and `refreshFeatures`. Place after the `map.on('click', ...)` block... actually, there isn't one yet. Add a map click handler:

After `setCurrentHole(1);` line (or after the toggle handler), add:

```javascript
  map.on('click', e => {
    if (!splitModeActive) return;

    if (splitMarkers.length >= 2) {
      clearSplitMarkers();
    }

    const marker = L.marker(e.latlng, {
      draggable: true,
      icon: L.divIcon({
        className: '',
        html: '<div style="background:#e53935;width:12px;height:12px;border-radius:50%;border:2px solid white;cursor:pointer;"></div>',
        iconSize: [12, 12],
        iconAnchor: [6, 6],
      }),
    }).addTo(map);

    marker.on('dragend', () => {
      if (splitMarkers.length === 2) {
        clearSplitMarkers();
        const p1 = splitMarkers[0];
        const p2 = splitMarkers[1];
        splitMarkers[0] = p1;
        splitMarkers[1] = p2;
        if (p1 && p2) {
          addSplitLine(p1.getLatLng(), p2.getLatLng());
        }
      }
    });

    marker.on('contextmenu', e => {
      L.DomEvent.stopPropagation(e);
      clearSplitMarkers();
    });

    splitMarkers.push(marker);

    if (splitMarkers.length === 2) {
      addSplitLine(splitMarkers[0].getLatLng(), splitMarkers[1].getLatLng());
    }
  });
```

- [ ] **Step 3: Commit**

```bash
git add tagger/static/index.html
git commit -m "feat: add split line drawing interaction"
```

---

### Task 10: index.html — sidebar updates for sub-features

**Files:**
- Modify: `tagger/static/index.html`

**Goal:** Update `renderFeatureList()` to show sub-features with `(A)`/`(B)` suffix indicators.

- [ ] **Step 1: Update renderFeatureList**

Replace the existing `renderFeatureList` function (lines 502-542) with:

```javascript
  function renderFeatureList(features) {
    const list = document.getElementById('feature-list');
    list.innerHTML = '';
    features.forEach(f => {
      const id = f.properties.osm_id;
      const type = f.properties.type;
      if (!activeFilters.has(type)) return;
      const hole = featureAssignments[id];
      const div = document.createElement('div');
      const isCourseWide = (type === 'water' || type === 'waterway' || type === 'path');
      if (isCourseWide) return;

      div.className = 'feature-item' + (hole ? ' assigned' : '');

      let label = type;
      if (f.properties.split_group) {
        const idx = id.split('__')[1];
        if (idx !== undefined) {
          label = type + ' (' + String.fromCharCode(65 + parseInt(idx)) + ')';
        }
      }

      const holeBadge = hole ? `<span class="hole-badge">H${hole}</span>` : '';

      div.innerHTML = `
        ${holeBadge}
        <span class="type-badge type-${type}">${label}</span>
        <span class="feature-meta">#${id}</span>
      `;

      div.onclick = () => {
          if (hole) {
            delete featureAssignments[id];
            if (layers[id]) map.addLayer(layers[id]);
            renderFeatureList(allFeatures);
          } else {
            if (currentHole >= 1 && currentHole <= 18) {
              featureAssignments[id] = currentHole;
              if (layers[id]) map.removeLayer(layers[id]);
              renderFeatureList(allFeatures);
            }
            if (layers[id]) {
              map.setView(layers[id].getBounds ? layers[id].getBounds().getCenter() : layers[id].getLatLng(), 18);
            }
          }
        };
      list.appendChild(div);
    });
  }
```

- [ ] **Step 2: Commit**

```bash
git add tagger/static/index.html
git commit -m "feat: show sub-features with A/B suffix in sidebar"
```

---

### Task 11: index.html — save adaptation for sub-feature IDs

**Files:**
- Modify: `tagger/static/index.html`

**Goal:** Update the save handler to include feature IDs in the POST body so the server writes the new format (`{"id":"...", "rings":[[...]]}`).

- [ ] **Step 1: Update save handler**

Replace the existing `btn-save.onclick` handler (lines 545-601) with:

```javascript
  document.getElementById('btn-save').onclick = () => {
    const holes = {};
    for (let h = 1; h <= 18; h++) {
      holes[String(h)] = {fairway:[], green:[], bunkers:[], tee_boxes:{}, water:[], waterways:[], paths:[], rough_boundary:[]};
    }
    fetch('/api/features').then(r => r.json()).then(data => {
      data.features.forEach(f => {
        const id = f.properties.osm_id;
        const geom = f.geometry;
        const type = f.properties.type;
        const hole = featureAssignments[id];

        // Water and paths are course-wide -- auto-distribute to all 18 holes
        if (type === 'water' || type === 'waterway' || type === 'path') {
          const targetHoles = Object.keys(holes);
          if (geom.type === 'Polygon' && type === 'water') {
            const ring = geom.coordinates[0].map(c => [c[1], c[0]]);
            targetHoles.forEach(hk => holes[hk].water.push({"id": id, "rings": ring}));
          } else if (geom.type === 'LineString' && type === 'waterway') {
            const line = geom.coordinates.map(c => [c[1], c[0]]);
            targetHoles.forEach(hk => holes[hk].waterways.push({"id": id, "rings": line}));
          } else if (geom.type === 'LineString' && type === 'path') {
            const line = geom.coordinates.map(c => [c[1], c[0]]);
            targetHoles.forEach(hk => holes[hk].paths.push({"id": id, "rings": line}));
          }
          return;
        }

        if (!hole) return;
        const hk = String(hole);
        if (geom.type === 'Point') {
          const teeColour = f.properties.tags?.colour || f.properties.tags?.color || 'white';
          holes[hk].tee_boxes[teeColour] = [geom.coordinates[1], geom.coordinates[0]];
        } else if (geom.type === 'Polygon') {
          const ring = geom.coordinates[0].map(c => [c[1], c[0]]);
          const item = {"id": id, "rings": ring};
          if (type === 'fairway') holes[hk].fairway.push(item);
          else if (type === 'green') holes[hk].green.push(item);
          else if (type === 'bunker') holes[hk].bunkers.push(item);
          else if (type === 'water') holes[hk].water.push(item);
          else if (type === 'rough') holes[hk].rough_boundary.push(item);
          else if (type === 'tee') holes[hk].rough_boundary.push(item);
        } else if (geom.type === 'LineString') {
          const line = geom.coordinates.map(c => [c[1], c[0]]);
          const item = {"id": id, "rings": line};
          if (type === 'path') holes[hk].paths.push(item);
          else if (type === 'waterway') holes[hk].waterways.push(item);
        }
      });

      fetch('/api/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({scale: {pixels_per_yard: 1.0}, holes}),
      }).then(() => {
        document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:var(--font-body);font-size:18px;color:var(--accent);">Saved! You can close this tab.</div>';
      });
    });
  };
```

- [ ] **Step 2: Commit**

```bash
git add tagger/static/index.html
git commit -m "feat: include feature IDs in save POST for new format"
```

---

### Task 12: Integration verification

**Files:**
- None (manual testing)

**Goal:** Verify the full end-to-end flow works.

- [ ] **Step 1: Run full test suite**

```bash
PYTHONPATH=source:plugins pytest plugins/cartographer/tests/ -v
```
Expected: all ~165+ tests pass (previous 160 + ~14 new).

- [ ] **Step 2: Sanity check — PDF generation with old-format data still works**

```bash
PYTHONPATH=. python -m cartographer.pdf "Test Course" --output /tmp/test_output
```

- [ ] **Step 3: Manual tagger test**

Start the tagger for a course with overlapping features:
```bash
python -m cartographer.tagger "Bellevue Golf Course"
```
1. Verify split mode toggle is visible
2. Click toggle, draw a split line, verify dashed red line appears
3. Verify sub-features appear in sidebar with (A)/(B) suffix
4. Assign sub-features to different holes
5. Save, reopen tagger — verify split lines and assignments persist
6. Generate PDF — verify each half renders on the correct hole's page

- [ ] **Step 4: Commit any final fixes**

---

### Task 13: Update HANDOFF and session log

**Files:**
- Modify: `docs/HANDOFF.md`
- Modify: `docs/SESSION_LOG.md`

- [ ] **Step 1: Update HANDOFF.md**

Update the `Last updated` timestamp, current state, next actions, and blockers.

- [ ] **Step 2: Append to SESSION_LOG.md**

Add a new dated entry summarizing what was done.

- [ ] **Step 3: Commit**

```bash
git add docs/HANDOFF.md docs/SESSION_LOG.md
git commit -m "docs: update session memory for multi-hole feature support"
```

---

### Task 14: Bump version to 1.3.0

**Files:**
- Modify: `plugin.py`

- [ ] **Step 1: Bump version**

In `plugin.py`, change `VERSION = "1.2.0"` to `VERSION = "1.3.0"`.

- [ ] **Step 2: Commit**

```bash
git add plugin.py
git commit -m "chore: bump version to 1.3.0"
```
