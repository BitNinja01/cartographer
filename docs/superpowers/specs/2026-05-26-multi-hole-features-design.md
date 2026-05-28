# Multi-Hole Feature Support — Design Spec

**Date**: 2026-05-26
**Status**: Draft
**Target version**: v1.3.0

## Problem

Some golf courses (especially links-style) have features shared between holes — double greens, overlapping fairways. The current system cannot handle this:

1. **Tagging**: `featureAssignments` is strictly one-to-one (`osm_id → hole_number`). No way to mark a feature as belonging to multiple holes.
2. **Fitting**: Even if multi-hole assignment existed, `fit_hole()` uses the entire feature's geometry for rotation/scaling/centering — there's no mechanism to use only the relevant portion for each hole.

## Approach

**Geometry-level split before tagging.** The user draws a split line across a shared feature in the tagger, which physically clips the polygon using shapely. The clipped sub-features become independent items that slot into the existing one-to-one tagging flow. Zero changes to `fit_hole()`, `render_hole()`, `project_course()`, `smooth_hole_geometry()`, `pdf.py`, or `layout.py`.

## Behavior by Feature Type

| Feature | Split visual? | Split for fitting? |
|---------|:---:|:---:|
| Green | Yes — clipped to each hole's side | Yes — each half drives its own `fit_hole()` rotation/scale/centering |
| Fairway | Yes — clipped to each hole's side | Yes |
| Bunkers | Yes — can be split if shared | Yes |
| Rough boundary | Yes — can be split if shared | Yes |
| Water / Waterways / Paths | No — course-wide, already auto-distributed | No |

## Data Model

### `courses_geo.json` — New `"splits"` key

```json
{
  "Course Name": {
    "scale": {"pixels_per_yard": 1.0},
    "splits": {
      "1": [[lat1, lon1], [lat2, lon2]],
      "2": [[lat3, lon3], [lat4, lon4]]
    },
    "holes": {
      "7": {
        "green": [
          {"id": "way/501234__0", "rings": [[[lat,lon], ...]]},
          {"id": "way/502345",     "rings": [[[lat,lon], ...]]}
        ]
      }
    }
  }
}
```

- **`splits`**: Split lines stored as WGS84 lat/lon endpoint pairs, keyed by sequential integer ID. Removed lines trigger re-merge on save.
- **`holes.*.*`** format change: each feature entry gains an `"id"` key and wraps rings in a `"rings"` key. Old format (bare `[[[lat,lon]]]`) is detected at load time and given `id: null`.

### Sub-feature Synthetic IDs

Split features produce children with `__N` suffix:
```
way/501234     →  way/501234__0, way/501234__1
relation/88901 →  relation/88901__0, relation/88901__1
```

A `split_group` property on the GeoJSON feature links children back to their parent for merge/delete operations.

## Server-Side (`tagger/server.py`)

### New Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/splits` | GET | Return split lines as GeoJSON LineStrings |
| `/api/splits` | POST | Add a split line: body `[[lat1,lon1],[lat2,lon2]]`, returns `split_id` + list of affected `osm_id`s |
| `/api/splits/<id>` | DELETE | Remove a split line, re-merge, drop sub-feature assignments |

### Clipping Algorithm (POST handler)

1. Build `shapely.LineString` from the two endpoints
2. For each non-course-wide OSM feature (`water`, `waterway`, `path` excluded):
   - Convert to shapely geometry
   - `shapely.ops.split(geom, line)` → GeometryCollection
   - Discard pieces with area < 1% of original (sliver guard)
   - Store pieces in `feature["_split_pieces"]`
   - Record feature as affected
3. Return `split_id` and affected feature list

### Feature Serving with Splits

When `GET /api/features` is called with active splits, split features are expanded: each piece becomes a separate GeoJSON Feature with synthetic ID and `split_group` property. Unsplit features are served as before.

### In-Memory State

```python
app.config["split_lines"] = {split_id: ((lat1, lon1), (lat2, lon2))}
```

Loaded from `courses_geo.json` on startup. Split pieces computed on-demand from fresh OSM data using stored split lines.

## Tagger UI (`tagger/static/index.html`)

### Split Mode Toggle

A button in the existing top toolbar toggles split mode on/off. While active:
- Button turns red with "✕ Exit Split" label
- Map cursor changes to crosshair
- Hole navigation and sidebar are read-only

### Line Drawing

- **First click**: pins a draggable marker
- **Second click**: pins second marker, draws dashed line, POSTs to `/api/splits`
- **Both markers are draggable** — re-POSTs on drag end for fine-tuning
- **Right-click marker**: removes it, resetting the line
- Split lines rendered on the map as dashed red polylines (`interactive: false`)
- After successful split, feature list and map layers refresh

### Sidebar

Sub-features appear with `(A)`/`(B)` suffixes derived from the `__0`/`__1` ID suffix. They are standard clickable items — clicking assigns to the current hole.

### Save Flow

The existing `featureAssignments` object handles sub-feature IDs directly:
```javascript
featureAssignments["way/501234__0"] = 7;
featureAssignments["way/501234__1"] = 11;
```

Sub-feature geometry is already available client-side from the `/api/features` response. The save handler pushes it into per-hole geometry dicts exactly as today — sub-feature IDs are treated as opaque feature IDs.

## Backward Compatibility

### Old `courses_geo.json` (v1.2.0 and earlier)

**Detection**: If the first element in a feature array is a bare list (not a dict with `"rings"`), it's old format.

**Loading**: Old-format rings are wrapped as `{"id": null, "rings": [...]}`. No split reconstruction possible (no splits existed in old data). Works identically to today.

**Saving**: Always writes new format. Old data gets upgraded on first re-save.

### Two load paths

`data.py` provides two load functions:

- **`load_courses_geo()`** — normalized form for geometry/render/PDF consumers. Extracts bare ring lists, discards IDs. Return type is identical to today — zero changes to `geometry.py`, `renderer.py`, `pdf.py`, `layout.py`, or `plugin.py` screens.
- **`load_courses_geo_raw()`** — raw form with IDs and splits preserved. Used only by the tagger server for assignment reconstruction.

```python
def load_courses_geo():
    """Normalized: bare ring lists. For geometry/render/PDF consumers."""
    raw = _read_json()
    return _normalize(raw)  # extracts rings, discards IDs

def load_courses_geo_raw():
    """Raw: includes feature IDs and splits. For the tagger server."""
    return _read_json()
```

### Tagger assignment reconstruction

On page load, the Flask server:
1. Calls `load_courses_geo_raw()` to get IDs and splits
2. Applies stored split lines to fresh OSM data
3. Derives `featureAssignments` from hole data IDs (e.g., `"way/501234__0"` → hole 7)
4. Embeds assignments directly in the page template as a JS variable

The frontend initializes `featureAssignments` from the embedded data — no inference needed.

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Split line grazes polygon edge (no full split) | `ops.split` returns 1 piece → ignored |
| Split line endpoint inside feature | Shapely extends line to polygon boundary internally |
| Feature is a MultiPolygon | `ops.split` handles each component polygon |
| Split line crosses polygon hole (bunker in fairway) | Holes preserved in clipped result |
| Sliver < 1% area on one side | Discarded, logged as warning |
| Deleting a split line with assigned sub-features | Confirm dialog; assignments dropped on merge |
| Server restart loses in-memory split cache | Split lines persisted in JSON; re-run split on fresh OSM data |
| Split line too short (< 20px) | Frontend enforces minimum distance before POST |

## Files Changed

| File | Change |
|------|--------|
| `tagger/server.py` | 3 new endpoints, split algorithm, feature expansion, backward-compat save/load |
| `tagger/static/index.html` | Split mode toggle, line drawing, split feature display, save adaptation |
| `data.py` | `load_courses_geo_raw()` (new), `save_courses_geo()` writes new format, `load_courses_geo()` unchanged |
| `geometry.py` | No changes |
| `renderer.py` | No changes |
| `pdf.py` | No changes |
| `layout.py` | No changes |
| `plugin.py` | No changes |
| `osm.py` | No changes |
| `tests/test_osm.py` | Sub-feature ID generation tests |
| `tests/test_geometry.py` | Shapely split tests (normal, grazing, sliver, MultiPolygon) |
| `tests/test_data.py` | Old/new format load, round-trip save/load with splits, backward compat |

## Out of Scope (deferred)

- Three-way or N-way splits (e.g., fairway shared by holes 1, 9, and 10). User can draw multiple split lines to achieve this — each line splits the current sub-feature further.
