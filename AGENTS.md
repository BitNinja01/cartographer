# AGENTS.md

This file provides guidance to OpenCode when working with code in this repository.

## What Cartographer Is

A PinSheet plugin that generates yardage book PDFs from OpenStreetMap course geometry. Takes `.osm` XML files (downloaded via Overpass API or manually), projects geographic coordinates to pixel space, renders SVG hole diagrams, and combines them into saddle-stitch printable booklets. Includes a browser-based visual tagger (Flask + Leaflet.js) for assigning OSM features to holes.

## Before you start

- All relevant project documentation can be found in `docs/`
- **Always read `docs/RUNBOOK.md`** before running commands — it covers install, test, tagger, and PDF generation workflows
- **Always read `docs/DECISIONS.md`** before making architectural changes — it records the *why* behind projection choices, OSM parsing strategy, PDF layout, and font handling
- Reference the parent PinSheet repo (`/mnt/Claude/repositories/pinsheet/`) for plugin API conventions (`source/plugin.py`, `source/plugin_loader.py`)

### Claude memory files (ignore)
This project may contain Claude Code artifacts (`CLAUDE.md`, `.claude/`). These are managed by a different tool. OpenCode must never read, write, or modify them — they do not exist as far as this agent is concerned.

### Nested repo isolation
**CRITICAL:** Cartographer is a standalone git repository nested inside the parent PinSheet repo at `plugins/cartographer/`. The parent's `.gitignore` excludes `plugins/`. NEVER commit cartographer files from the parent repo — they must only be committed within this nested repository. Conversely, never modify parent repo files from within this repository.

## Git workflow

**CRITICAL:** NEVER push changes or create pull requests without explicit user consent. Always ask before running `git push` or `gh pr create`.

Cartographer uses a simple **main + feature branch** workflow:
1. Start from `main`: `git checkout main && git pull origin main && git checkout -b feature/my-feature`
2. Work, commit, push: `git push origin feature/my-feature`
3. Open PR to `main`
4. Merge when ready

No `dev` branch — cartographer is a single-repo plugin with simpler release cadence than the parent app.

## Process rules

### Edit discipline
Every `oldString` in an edit call must include at least 2–3 lines of surrounding context — never match on a bare function name, single-line property, or lone closing brace. If a match has any chance of being ambiguous, use `grep` or `read` first to confirm uniqueness.

### Pre-edit read
Re-read the target file section before every edit, even if it was just written. Never assume the file's current state from memory.

### Post-change verification
After writing any `.py` file, run `python -m py_compile` on it:
```bash
python -m py_compile cartographer/geometry.py
```
After editing CSS (`cartographer.tcss`), verify all new selectors have matching widgets in the source.

## Commands

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run the test suite:**
```bash
PYTHONPATH=source:plugins pytest plugins/cartographer/tests/ -v
```
(Run from the parent PinSheet repo root. Needs both `source/` for plugin base class and `plugins/` for cartographer package.)

**Run the tagger (standalone):**
```bash
python -m cartographer.tagger "Course Name"
```

**Generate a yardage book (standalone):**
```bash
PYTHONPATH=. python -m cartographer.pdf "Course Name" --output /path/to/output
```

**Compile a single file:**
```bash
python -m py_compile cartographer/geometry.py
```

## Test suite

### Test location and structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures (synthetic geometry/round factories)
├── test_geometry.py         # Haversine, projection, Chaikin smoothing, bounds, centroids
├── test_osm.py              # Tag classification, node-ring conversion
├── test_stats.py            # Per-hole stat computation functions
└── test_data.py             # JSON persistence with tmp_path fixtures
```

**Running:** `PYTHONPATH=. pytest tests/ -v`
**Requires:** `pytest` (install with `pip install pytest`)

### Fixture system

`tests/conftest.py` provides synthetic factories:

- **`make_round`** — factory fixture; `make_round(gross=85, fir_hits=8, gir_hits=6, ...)` returns a round dict matching PinSheet's JSON shape (string-valued numbers, `"H"` for hits, `""` for unrecorded). Standard par layout: 3s on holes 4/8/12/16, 5s on 2/6/10/14/18.
- **`make_course_geo`** — factory fixture; creates projected hole geometry dicts with pixel-coordinate polygon rings for fairway, green, bunkers, water, rough_boundary, and tee_boxes.
- **`make_osm_feature`** — factory fixture; creates OSM-like feature dicts with `osm_id`, `type`, `geometry`, `is_point`, and `tags`.

### Test patterns

Every pure function gets at minimum three cases:
1. **Normal** — realistic data, returns expected value or valid range
2. **Empty/None** — no data or missing fields, returns safe default
3. **Edge** — boundary conditions (single point, same coordinates, zero-distance)

### Adding new tests

1. For a new function in `geometry.py`: add test to `test_geometry.py`
2. For a new tag classification: add test to `test_osm.py`
3. For a new stat function: add test to `test_stats.py`
4. Always add an empty-data test
5. Run: `PYTHONPATH=. pytest tests/ -v`

## Architecture

### Source layout
- `plugin.py` — `CartographerPlugin(PinSheetPlugin)` adapter class
- `geometry.py` — Haversine distance, lat/lon → pixel projection, hole fitting/rotation, Chaikin smoothing
- `renderer.py` — SVG diagram generation (hole layouts, green grids, course overview, SVG→PNG conversion)
- `layout.py` — SVG page composition (hole pages, stats/notes slots, front/back covers, chart, corner marks)
- `pdf.py` — PDF generation pipeline (20 narrow PDFs → 5 saddle-stitch booklets)
- `osm.py` — OSM XML parser, tag classifier (`_classify_tags`), Overpass API fetcher
- `stats.py` — Per-hole stat computation (fairway misses, GIR misses, benchmark vs handicap, penalties)
- `data.py` — JSON persistence (`courses_geo.json` read/write, OSM cache paths)
- `tagger/server.py` — Flask web server for browser-based feature tagging
- `tagger/static/index.html` — Leaflet.js tagging UI
- `screens/` — PinSheet TUI screens (hole_view, course_gallery, geometry_setup, pdf_export)

### Coordinate pipeline
1. **OSM data** → `osm.py` parses `.osm` XML → list of feature dicts with `[lat, lon]` rings
2. **Tagger** → user assigns features to holes, sets scale → `courses_geo.json` saved
3. **Projection** → `geometry.project_course()` → pixel coordinates via equirectangular projection
4. **Smoothing** → `geometry.smooth_hole_geometry()` → Chaikin corner-cutting (3 iterations)
5. **Fitting** → `geometry.fit_hole()` → rotates green-to-top, scales to canvas, returns transformed coords
6. **Rendering** → `renderer.render_hole()` → SVG string with polygons, tees, yardage arcs
7. **Layout** → `layout.render_hole_page()` → SVG page with hole number, par, tee yardages
8. **PDF** → `pdf.generate_book()` → 20 cross-paired SVGs → cairosvg → 20 narrow PDFs → pypdf → 5 booklets

### OSM classification (`osm._classify_tags`)
Two-phase approach:
1. **Exclude**: `highway`, `building`, `amenity`, `bridge`, `tunnel`, `railway`, `power`, `man_made` → `None`
   - Exception: `golf=cartpath` with `highway=path` → `"path"`
2. **Match**: `golf=*` tags → mapped type; `natural=water`/`waterway=*`/`water=*` → `"water"`; `landuse=grass` (no golf tag) → `"fairway"`; bare `barrier=*` → `None`

### Font handling
JetBrainsMono Nerd Font (5 variants) is bundled in `fonts/JetBrainsMono/`. On plugin init, `CartographerPlugin._install_fonts()` copies TTFs to `~/.local/share/fonts/pinsheet/` and runs `fc-cache -f`. SVG text rendering relies on system font availability (cairosvg/Pango constraint).

### Settings schema
```python
{
    "cartographer.yardage_arcs": True,
    "cartographer.yardage_arc_distances": [100, 125, 150, 175, 200],
}
```
