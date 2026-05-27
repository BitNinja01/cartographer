# Session Log

## 2026-05-20 14:30 UTC

**What was done**:
- Established session memory framework (HANDOFF / SESSION_LOG / DECISIONS / RUNBOOK) matching parent PinSheet repo
- Created comprehensive `.gitignore` with Python, AI artifacts, venv, and test coverage patterns
- Created `AGENTS.md` with cartographer-specific guidance (architecture, commands, test patterns)
- Set up pytest test suite: `tests/conftest.py` with synthetic geometry/round fixtures, `tests/test_geometry.py`, `tests/test_osm.py`, `tests/test_stats.py`, `tests/test_data.py`
- Created `.opencode/` with session-end slash command

**Files touched**:
- `.gitignore` — replaced 4-line stub with comprehensive 130+ line policy
- `AGENTS.md` — new: cartographer guidance for OpenCode
- `docs/HANDOFF.md` — new: current state and next actions
- `docs/SESSION_LOG.md` — this file
- `docs/DECISIONS.md` — new: durable architectural decisions
- `docs/RUNBOOK.md` — new: operational commands and workflows
- `tests/__init__.py` — new
- `tests/conftest.py` — new: synthetic geometry/round fixtures
- `tests/test_geometry.py` — new: haversine, projection, Chaikin, bounds, centroids
- `tests/test_osm.py` — new: tag classification, node-ring conversion
- `tests/test_stats.py` — new: stat computation functions
- `tests/test_data.py` — new: JSON persistence with tmp_path
- `.opencode/commands/cartographer-session-end.md` — new

**Next**: Continue PDF formatting polish; expand test coverage for SVG-producing functions

## 2026-05-20 17:00 UTC

**What was done**:
- Established CI/CD pipeline: CI workflow (checkout parent + install deps + compile + 109 tests + secrets check), release workflow (tag-triggered source zip + GitHub Release with manual dispatch)
- Created `dev` branch and synced with `main` post-release
- Released v1.0.1 via full pipeline: bump → release notes → push dev → PR → merge → tag → GitHub Actions auto-release
- Added MIT LICENSE matching parent repo
- Added README badges (release, downloads, CI, platform, Python)
- Wrote detailed installation guide in README (prerequisites, release zip and git clone options, quick start with 4-step flow)
- Created three slash commands: `cartographer-session-start`, `cartographer-session-end`, `cartographer-release` (with Step 6 dev sync)
- Added Step 6 (dev merge main sync) to parent pinsheet-release command as well
- Updated RUNBOOK with correct test invocation path from parent repo root

**Files touched**:
- `.github/workflows/ci.yml` — new: CI pipeline matching parent pattern
- `.github/workflows/release.yml` — new: tag + manual dispatch release pipeline
- `LICENSE` — new: MIT license
- `README.md` — badges, detailed installation guide, quick start
- `plugin.py` — version bump 1.0.0 → 1.0.1
- `dist/cartographer_1.0.1.txt` — release notes
- `.opencode/commands/cartographer-release.md` — new: release pipeline command
- `.opencode/commands/cartographer-session-start.md` — new: session start command
- `docs/RUNBOOK.md` — fixed test command path
- `~/.config/opencode/commands/pinsheet-release.md` — added Step 6 dev sync

**Next**: PDF formatting polish; OSM tagger improvements; linting configuration

## 2026-05-20 18:30 UTC

**What was done**:
- README intro copy updated: "A PinSheet plugin" → "A plugin for [PinSheet](...), the golf stats and round tracking app" to correctly describe PinSheet as the core application (not a plugin system)
- Tagger UI (`tagger/static/index.html`) underwent a full visual redesign: OKLCH CSS design system, CSS custom properties, JetBrains Mono font face declarations, styled hole/course-wide badges, pill-shaped type filter chips, `.hidden` class replacing inline display toggling
- Fixed three hardcoded color leaks that survived the redesign: `setCurrentHole` JS color mutation replaced with CSS class toggle (`invalid`), scale marker hardcoded `#1565C0` replaced with `accentColor` from computed style, save confirmation inline `monospace`/`#4CAF50` replaced with `var(--font-body)`/`var(--accent)`
- `.od-skills/` added to `.gitignore` alongside other AI tooling artifacts

**Files touched**:
- `README.md` — corrected PinSheet description and link
- `tagger/static/index.html` — full visual redesign + hardcoded color fixes
- `.gitignore` — added `.od-skills/`

**Next**: PDF formatting polish; OSM tagger improvements; linting configuration

## 2026-05-21 17:00 UTC

**What was done**:
- Renamed GitHub remote from `cartographer` → `pinsheet-cartographer`; updated README badges, install URLs, clone command, DECISIONS.md reference, and `.opencode/commands/cartographer-release.md`
- Waterway linestring fix (7-task plan, subagent-driven): added `"waterway"` type distinct from `"water"` in OSM classifier; pre-checked waterway/water before exclude gate so bridged/culverted streams survive; updated tagger API serialiser (LineString not Polygon), save handler (`waterways` key), geometry pipeline (`project_course`, `fit_hole`, `smooth_hole_geometry`), and renderer (`_draw_lines` for waterways)
- OSM classification hardened: `boundary` and `place` added to `_EXCLUDE_TAGS` (fixes large grey census boundary shapes in tagger); closed `waterway=*` ways reclassified to `"water"`; `min_nodes` leniency extended to open waterways
- Tagger UX: water/waterway/path made non-taggable (no filter chips, hidden from feature list, `interactive: false` on Leaflet map, course-wide click guard); unclassified features not rendered; OSM tile layer greyscaled; `"other"` label removed
- Auto-scale (4-task plan, subagent-driven): added `compute_pixels_per_yard_from_geometry()` to `geometry.py`; updated `renderer.py` and `pdf.py` to derive `ppy` per-hole at render time; removed "Set Scale" two-point UI from tagger entirely (186 lines deleted)
- Yardage arc fix: found `pdf.py` was projecting with `scale_data["pixels_per_yard"]` but computing arcs with a separately derived `ppy`, breaking the `ppy × scale_factor` cancellation. Fixed `_get_hole_render_data` to project per-hole with its own `ppy`. Unified green centroid to Shapely `get_green_centroid` in both TUI and PDF paths.

**Files touched**:
- `README.md` — repo rename URL updates
- `osm.py` — `"waterway"` type, pre-check before exclude gate, closed-way reclassification, `boundary`/`place` in `_EXCLUDE_TAGS`
- `tagger/server.py` — `"waterway"` serialised as LineString
- `tagger/static/index.html` — waterways save handler, course-wide UX, scale UI removal, greyscale tile layer
- `geometry.py` — `chaikin_smooth_open()`, `smooth_hole_geometry()` update, pipeline tuple updates, `compute_pixels_per_yard_from_geometry()`
- `renderer.py` — waterways rendering, auto-scale, Shapely centroid
- `pdf.py` — auto-scale, per-hole projection fix
- `tests/test_osm.py` — waterway classification tests, bridged stream tests
- `tests/test_geometry.py` — `TestChaikinSmoothOpen`, `TestComputePixelsPerYardFromGeometry`
- `docs/DECISIONS.md`, `docs/HANDOFF.md`, `docs/SESSION_LOG.md` — session memory

**Next**: Verify yardage arc accuracy with a fresh PDF export; cut v1.0.2 release; linting config

## 2026-05-21 18:00 UTC

**What was done**:
- Fixed `name 'projected' is not defined` crash in PDF cover page generation (`pdf.py:319-326`)
- Reordered booklet assembly pairs to new layout: 1/chart+18/cover, 3/2+16/17, 5/4+14/15, 7/6+12/13, 9/8+10/11
- Evaluated and cut **v1.1.0** release (minor bump — auto-scale, waterway linestrings, tagger UX, booklet reorder)
- Updated README: launcher auto-install promoted to recommended method; removed outdated Set Scale and filter chip references from Quick Start; bumped minimum PinSheet to v2.1.0+

**Files touched**:
- `pdf.py` — cover page projection fix, booklet assembly reorder
- `plugin.py` — version bump 1.0.1 → 1.1.0
- `dist/cartographer_1.1.0.txt` — release notes
- `README.md` — auto-install recommendation, Quick Start cleanup, version requirement
- `docs/HANDOFF.md`, `docs/SESSION_LOG.md` — session memory

**Next**: Linting config; verify PDF output with new booklet layout; fix standalone test runner

## 2026-05-22 00:00 UTC

**What was done**:
- Fixed "big grey box" on tagger map: switched `_classify_tags()` from blocklist to whitelist. `admin_level`, `barrier=jersey_barrier`, and other non-golf tags are silently dropped — no more `"unclassified"` features rendered as Polygon on the Leaflet map.
- Tagger auto-framing: map uses computed bounds from golf features (fairway, green, bunker, tee) to set initial view instead of default world view. Removed stale `geojsonLayer.getBounds().pad(0.1)` that was overriding it.
- Fairway morphological opening: added `opening_ring()` using shapely buffer-based erode/dilate in yard-space. Removes narrow walkway protrusions from fairway polygons during rendering. Applied before Chaikin smoothing, only to fairways, with a 3-yard structuring element.
- Released **v1.1.1**: tagger cleanup, auto-framing, fairway cleanup.

**Files touched**:
- `osm.py` — whitelist `_classify_tags()`, removed `_EXCLUDE_TAGS` and `"unclassified"` return
- `geometry.py` — `opening_ring()`, `_angle_between()`, `_dedupe_adjacent()`, `smooth_hole_geometry()` accepts `pixels_per_yard`
- `renderer.py` — passes `ppy` to `smooth_hole_geometry()`
- `tagger/server.py` — golf-feature bounds computation in `start_tagger()`
- `tagger/static/index.html` — initial `fitBounds` from data.bounds, removed stale GeoJSON fitBounds
- `tests/test_osm.py` — updated "unclassified" assertions to `None`
- `plugin.py` — version bump 1.1.0 → 1.1.1

**Next**: Linting config; verify PDF output with new booklet layout; fix standalone test runner

## 2026-05-22 01:00 UTC

**What was done**:
- Fixed release workflow: replaced `dist/*.txt` file-based release notes with `gh pr list --state merged --base main --limit 1 --json body --jq '.[0].body'` to fetch the PR body, matching the parent PinSheet repo strategy.
- Manually updated v1.1.1 release notes on GitHub for the current release.
- Merged workflow fix to `main` and synced `dev`.

**Files touched**:
- `.github/workflows/release.yml` — replaced Read release notes step with Fetch release notes from merged PR step

**Next**: Linting config; verify PDF output with new booklet layout; fix standalone test runner

## 2026-05-22 03:00 UTC

**What was done**:
- **Course overview rotation**: added `find_overview_rotation()` to geometry.py — brute-force search (-90° to 90°, 2° steps) finds the angle maximising the uniform scale factor for the course bounding box on the back-page canvas. Applied in `render_course_overview()` with auto-rotation when `rotation=None`.
- **Course overview fairway opening**: added `pixels_per_yard` parameter to `render_course_overview()`. Morphological opening (3-yard buffer via `opening_ring`) removes narrow protrusions from fairway polygons at overview scale. Wired through from `pdf.py` with `pixels_per_yard=overview_ppy`.
- **Tests**: added `TestFindOverviewRotation` class (7 test cases) to `test_geometry.py`.

**Files touched**:
- `geometry.py` — new `find_overview_rotation()`
- `renderer.py` — `render_course_overview()` accepts `rotation` and `pixels_per_yard` params; applies rotation + morphological opening
- `pdf.py` — passes `pixels_per_yard=overview_ppy` to overview render call
- `tests/test_geometry.py` — `TestFindOverviewRotation` test class

**Next**: Linting config; verify PDF output with new layout/rotation/opening; fix standalone test runner

## 2026-05-23 04:30 UTC

**What was done**:
- **Released v1.1.2**: patch bump for course overview rotation + fairway morphological opening. PR merged, tag pushed, release workflow triggered, dev synced.

**Files touched**:
- `plugin.py` — version 1.1.1 → 1.1.2

**Next**: Verify PDF output with new rotation/opening; fix standalone test runner; linting config

## 2026-05-22 22:30 UTC

**What was done**:
- Club chart: changed columns to Club/Carry/Half/Max, made all text and grid lines black
- Hole number/par label block: added black rounded-rect stroke, later removed stroke entirely; made background opaque
- Tee yardage label block: made background opaque, added black rounded-rect stroke
- Green grid: changed grid lines from #999 to black
- Notes sections: changed ruled lines from #ddd to black
- Stats panel: replaced _____ placeholders with labelled entry points (L:, R:, S:, LO:, etc.) using · separator; changed VS EXPECTED to SCORE; penalties fallback changed from "Total:" to "Avg:"; redesigned from 2×2 loose text to per-quadrant mini-tables with header row, label column, and ruled writing area
- Fixed missing `pixels_per_yard=ppy` argument in `pdf.py:_get_hole_render_data()` — morphological opening was silently skipped in PDF per-hole rendering

**Files touched**:
- `layout.py` — chart columns/colors, label block styling, notes lines black, stats panel table redesign
- `stats.py` — placeholder text changed to labelled entry points
- `renderer.py` — green grid lines black
- `pdf.py` — pass `pixels_per_yard=ppy` to `smooth_hole_geometry`
- `tests/test_stats.py` — updated fallback expectations

**Next**: Verify PDF output; standalone test fix; linting config

## 2026-05-24 23:00 UTC

**What was done**:
- Designed and implemented green contour lines feature: marching squares (pure numpy), USGS TNM DEM acquisition + caching, green elevation sampling via rasterio, CRS coordinate transforms, SVG contour rendering in `render_green()`, full PDF pipeline integration
- Fixed coordinate order bugs: data is `[lat, lon]` (OSM convention) but `_course_green_bounds()` and `_ring_to_crs()` read them as `[lon, lat]`, causing wrong bounding box sent to TNM API
- Fixed `project_course()`: missing `"contours"` in feature type lists — contour paths were silently dropped before projection
- Fixed TNM API parameters: `datasets` filter returned 0 items; replaced with `prodFormats=GeoTIFF` + `"1 Meter"` title filter
- Added `status_callback` to `generate_book()` for "Downloading elevation data..." UI message
- Contour data verified correct at computation stage (marching squares produces paths) but **not yet rendering in final PDF** — likely a coordinate transform or path format issue in the DEM CRS → WGS84 → pixel → fitted canvas chain

**Files touched**:
- `elevation.py` — new (marching squares, DEM acquisition, green sampling, CRS transforms, caching)
- `geometry.py` — `"contours"` in `project_course()` and `fit_hole()` feature type lists
- `renderer.py` — `_draw_contours()`, `_draw_green_grid()` extracted as fallback
- `pdf.py` — contour computation + injection, `status_callback` parameter
- `screens/pdf_export.py` — `status_callback` wired to `_update_status`
- `data.py` — `get_dem_path()`, `get_contours_cache_path()`
- `requirements.txt` — added `rasterio`
- `tests/test_elevation.py` — new (10 tests)
- `tests/test_renderer.py` — new (5 tests)
- `docs/superpowers/specs/2026-05-24-green-contours-design.md` — spec
- `docs/superpowers/plans/2026-05-24-green-contours-plan.md` — plan

**Next**: Debug contour line rendering; verify PDF output; standalone test fix

---

## 2026-05-25 00:20 UTC — cont'd (extended to 01:20)


**What was done**:
- Fixed Bug 1 (empty cache): `compute_all_green_contours` now passes `greens[0]` (single ring) instead of `greens` (list of rings) to `compute_green_contours`. `sample_green_elevation` was silently returning None due to downstream type error.
- Fixed Bug 2 (coordinate space mismatch): Contour paths were fitted to HOLE_CANVAS_H (504pt) but `render_green` fits the green to SLOT_H (243pt). Fixed by pre-fitting green+contours together to the slot canvas in `_get_hole_render_data()`, passing `fitted=True` to `render_green`.
- Fixed circular import: `__init__.py` changed from `from cartographer.plugin import CartographerPlugin` to lazy `__getattr__`.
- Normalized contour levels: `compute_green_contours` now normalises the DEM window to 0-1 before running marching squares. Default 8 contour bands at equal intervals. Labels show actual elevation in metres.
- Added white background rect to `render_green()` SVG.
- Added Chaikin smoothing (`chaikin_smooth_open`, 5 iterations) to contour paths in the rendering pipeline.
- Tested DEM upsampling (PIL bilinear, 8x) — produced noisy fragments, reverted.
- Rendered `maplewood_h9_green.png` and `maplewood_h9_elevation.png` for debugging.

**Files touched**:
- `elevation.py` — fixed ring param, normalized contours 0-1, removed upsampling code
- `pdf.py` — pre-fit green+contours to slot canvas, added `chaikin_smooth_open` import
- `renderer.py` — added white background rect to `render_green()`
- `__init__.py` — lazy `__getattr__` for `CartographerPlugin`

**Next**: Debug why normalized contours still produce poor visual results on flat greens. Consider alternative rendering (hillshade/heatmap).

---

## 2026-05-25 01:20 UTC

**What was done**:
- Fixed fragmented contour paths: added adaptive contour level count (`elevation.py`, one level per ~0.2m, clamp 2..8), Gaussian blur (sigma=0.3), and 4x bilinear upscale with sigma=1.5 blur before marching squares
- Fixed off-green noise: added `_clip_contour_to_green()` in `pdf.py` — Shapely intersection of each contour path with the green polygon, plus ≥15px arc length filter
- Removed elevation labels from contour rendering (`renderer.py:_draw_contours`)
- Added auto-levels: z_min/z_max computed from in-green DEM cells only (`elevation.py:_in_green_mask`), so the green's own 0.48m range gets full 0-1 normalisation instead of being compressed by outside terrain
- Reverted 0.5m threshold back to 0.25m after user feedback
- Added `_gaussian_blur()`, `_upsample_dem()`, `_upsample_mask()` helper functions in `elevation.py`
- Added 5 tests for gaussian blur, 4 adaptive contour tests (now 155 total)
- Diagnostic pipeline trace (`/tmp/contour_diagnostic.py`) tracks contour data through all stages
- Rendered debug images to repo root: `dem_*.png`, `h9_*.png/svg`

**Files touched**:
- `elevation.py` — adaptive levels, gaussian blur, upscale+blur, auto-levels mask
- `pdf.py` — `_clip_contour_to_green()`, minimum length filter, math import
- `renderer.py` — removed elevation labels
- `tests/test_elevation.py` — 9 new tests (blur + adaptive contours)
- `tests/test_renderer.py` — removed label assertion from contour test
- Root debug artifacts: `dem_full_window.png`, `dem_auto_levels.png`, `dem_upscaled.png`, `h9_full_hole.svg/png`, `h9_green_slot.svg/png`

**Next**: The user wants to try alternative green rendering strategies in order: hillshade → curvature map → combo → forced contour levels. See HANDOFF.md for details.

---

## 2026-05-25 05:45 UTC

**What was done**:
- Replaced contour lines with grayscale elevation shading on greens (step 1: hillshade)
- Implemented `compute_elevation_shading()` — normalizes in-green DEM to uint8 PIL Image (4x upscale + blur)
- Implemented `_draw_elevation_shading()` — renders PNG as SVG `<image>` with green-polygon `<clipPath>`
- Modified `render_green()` to accept `shading_data` instead of `contour_data`
- Simplified PDF pipeline: `get_course_dem()` in `generate_book()`, shading computed in `_get_hole_render_data()` after fitting
- Removed `compute_all_green_shading()` and corner-injection pipeline (was overcomplicated)
- Restored `_draw_green_grid` as fallback when no shading data

**Bugs encountered**:
1. Float subscriptable: corners not wrapped in list-of-rings structure
2. Blank bottom slot (unresolved): `render_green()` + chain work in isolation, but PDF output shows white bottom slot. Suspect data flow in `_get_hole_render_data()` or DEM availability.

**Files touched**:
- `elevation.py` — `compute_elevation_shading()`, removed `compute_all_green_shading()`
- `renderer.py` — `_draw_elevation_shading()`, modified `render_green()`
- `pdf.py` — simplified pipeline, removed contour threading
- `tests/test_elevation.py` — 3 new shading tests
- `tests/test_renderer.py` — 2 updated tests for shading/fallback

**Next**: Diagnose blank bottom slot in PDF output for Maplewood.

## 2026-05-25 07:15 UTC

**What was done:**

**Fix 1 — Blank bottom pages in PDF output:**
- Diagnosed root cause: `cairosvg.svg2pdf` silently drops `<image>` elements with `data:image/svg+xml` data URIs (works fine in `svg2png`). All bottom-sheet content was embedded this way.
- Added `_svg_to_png_data_uri()` helper in `layout.py:57` — converts SVG→PNG via `cairosvg.svg2png`, wraps as `data:image/png;base64,...`
- Replaced all 5 `data:image/svg+xml` instances in `compose_sheet` (×2), `render_hole_page`, `_render_slot` (green_grid), `flip_page_svg`, `compose_back_page`

**Fix 2 — Elevation shading rotation alignment:**
- Diagnosed: `compute_elevation_shading()` produces north-up image from geographic green, but `fit_hole` rotates the green by `green_rot` degrees. Shading placed without rotation → misaligned.
- First attempt: PIL `Image.rotate(green_rot, expand=True)` then resize to fitted polygon bbox → caused rectangular masking artifacts due to aspect-ratio mismatch between geographic bbox and fitted polygon bbox after rotation
- Replaced with SVG transform approach: shading image covers the projected geographic bbox (computed from projected `hole_geom["green"]`, scaled by same `slot_scale + offset` as `fit_hole`). Image placed unrotated, then `<g transform="rotate(green_rot, cx, cy)">` rotates around green centroid — same transform chain as `fit_hole`. Clip-path uses fitted green polygon in global SVG coordinates.
- `pdf.py`: captures `off_x, off_y, slot_scale` from `fit_hole` (was discarded); passes `rotate_angle/rotate_cx/rotate_cy` in `shading_data`
- `renderer.py`: `_draw_elevation_shading` accepts rotation params, uses nested `<g clip-path>` + `<g transform="rotate(...)">` structure; `render_green` forwards params

**Verification:**
- 155 tests pass
- Verified with Maplewood hole 1: SVG contains `rotate(-35.07°, 115.70, 125.23)`, 254 unique gray levels in bottom half confirming elevation variation
- User reports improvement but says "still more to debug" on shading alignment

**Files modified:** `layout.py`, `pdf.py`, `renderer.py` (7 total including prior session changes: `__init__.py`, `elevation.py`, `tests/test_elevation.py`, `tests/test_renderer.py`)

## 2026-05-25 08:30 UTC

**What was done:**

Resolved the remaining elevation shading rotation misalignment (Fix 2, Part B):

- **Root cause**: The shading image rotation center was computed as the centroid of the fitted+smoothed green polygon. But `fit_hole()` rotates geometry around the projected green bbox center — a different point when the green is asymmetric. For hole 16 (Maplewood, 78° rotation, pointed green shape), this caused ~11% of green vertices to fall outside the rotated shading image, producing visible "cut-off corners."

- **Diagnosis**: Wrote `tools/diag_rotation.py` and `tools/diag_svg.py` to trace the full coordinate pipeline (geographic → projected → fitted → SVG) and measure vertex coverage against the rotated image. Key findings:
  - Hole 14 (4.66° rotation): 0 vertices out — looked perfect ✓
  - Hole 4 (55° rotation): 242/3136 vertices out — small overhang, acceptable
  - Hole 16 (78° rotation): 225/2048 vertices out — visible cut-off corners ✗

- **Fix**: Replaced rotation center computation in `pdf.py:160-163` from fitted green centroid to image center (which equals projected bbox center in SVG space):
  ```python
  gcx = svg_bx + svg_bw / 2
  gcy = svg_by + svg_bh / 2
  ```

- **Verification**: All 3 holes → 0 vertices outside. 155/155 tests pass.

**Files modified:** `pdf.py` (rotation center fix), `tools/diag_rotation.py` (new), `tools/diag_svg.py` (new)

**Status:** Elevation shading rotation now fully resolved. No blockers.

## 2026-05-25 10:30 UTC

**What was done**:

- Added topographical contour lines over hillshade on greens: 12 levels extracted from normalized grayscale image via marching squares, Chaikin-smoothed (3 iterations), rendered as black strokes at standard width
- Reduced hillshade opacity to 50% so contours are clearly visible over the underlying shading
- Lowered flat-green elevation threshold from 0.25m → 0.10m (hole 2 had 0.22m range)
- Rendered context features (fairway, water, bunkers, paths, rough_boundary) around green in bottom slots — using unsmoothed projected data with 1-iteration Chaikin to keep performance reasonable
- Cached contour computation per hole to avoid ~36 redundant marching-squares runs across 20 pages
- Halved contour extraction resolution (4× → 2× SVG scale) and reduced contour Chaikin iterations (5 → 3) for additional ~16× speedup
- Applied contour stroke matching standard `_STROKE_WIDTH` (0.645pt)
- Fixed pixelated contour edges via 2× extraction resolution + Chaikin smoothing
- Diagnosed and fixed performance regression from double-smoothing context features (removed redundant `chaikin_smooth`, switched to unsmoothed projected source)

**Files touched**:
- `pdf.py` — contour extraction, caching, context feature transform (unsmoothed + light Chaikin), lower threshold
- `renderer.py` — context feature rendering in green slot, 50% opacity, contour path rendering in `_draw_elevation_shading`
- `elevation.py` — flat threshold 0.25 → 0.10
- `tests/test_elevation.py` — updated flat test to match new threshold

**Commits**: `591dc0a` (contour lines), `7426dae` (perf: cache + reduce overhead)

**Next**: Curvature map (step 2 of hillshade plan). Commit and PR. Clean up diagnostic scripts.

## 2026-05-25 15:30 UTC

**What was done**:
- Root-caused "dashed" contour lines: marching squares on the 136×80 shading image produced 60 fragmented polylines; the old `_connect_segments` greedy walk abandoned branches at fork points
- Rewrote `_connect_segments` with two-phase welding: spatial-hash vertex deduplication (0.5px epsilon) + post-processing polyline merge (20px radius) — reduced 63 fragments to 22 connected polylines
- Removed decimation initially to diagnose welding; re-added at `[::33]` (3% density) with endpoint preservation once lines were connected
- Set `contour_render_scale` at 2 (not 4) to keep marching squares O(nx·ny) performant on small source images
- Added dual status lines to PDF export screen: `#status-widget` for page progress, `#status-detail` for granular pipeline stage ("Computing elevation shading for hole N...", "Extracting & connecting contour lines...")
- Threaded `status_callback` through `_get_hole_render_data` and all 6 call sites in `generate_book`

**Files touched**:
- `elevation.py` — `_connect_segments` rewrite + `_merge_nearby_polylines` post-processing pass
- `pdf.py` — decimation `[::33]`, status_callback threading, granular status messages
- `screens/pdf_export.py` — second Static widget (`#status-detail`), split callbacks
- `tools/diag_contours.py` — raw contour fragment diagnostic (untracked, not committed)

**Next**: Tune decimation vs smoothness, curvature map, commit and PR.

## 2026-05-25 17:30 UTC

**What was done**:
- Improved contour vertex dedup: `_EPSILON` tightened from 0.5 to 1e-6 in `_connect_segments` — produces cleaner, more consistent contour lines
- Removed dead code: `_draw_contours()` (never called) and index/intermediate contour classification (unused by active pipeline)
- Flattened `compute_green_contours` return format from `{"index": [...], "intermediate": [...]}` to `{"contours": [...]}` — always returns dict, never None
- Threaded `merge_dist` parameter through `compute_contours` → `_marching_squares_level` → `_connect_segments` → `_merge_nearby_polylines` with default 20.0 for backward compatibility
- Added zero-divide guard in `_merge_nearby_polylines` for `merge_dist <= 0.0`
- Explored WGS84 contour pipeline (`compute_all_green_contours` → `project_course`) as a faster alternative to on-the-fly extraction. Determined it produces incorrect render output due to: (a) coordinate round-trip through CRS→WGS84→equirectangular projection not matching the direct grid-to-SVG mapping, (b) DEM grid (120×80) having too few vertices for the `[::33]` decimation producing garbled results. Reverted to on-the-fly approach for rendering; WGS84 pipeline code retained in `compute_green_contours`/`compute_all_green_contours` for potential future use
- Cleaned up `elevation.py`: removed unused `import math`, fixed docstring comments (2x→4x)
- Cleaned up `pdf.py`: removed unused `import numpy` from previous revert

**Root cause of WGS84 pipeline failure**:
1. Coordinate mismatch: the round-trip DEM grid→CRS→WGS84→equirectangular projection→SVG introduces transform error vs the on-the-fly direct grid→SVG mapping
2. Grid resolution: DEM upsampled grid (~120×80) has ~60 contour points; `[::33]` decimation reduces to 2 points (garbled). On-the-fly grid (~600×400) has ~300 points; `[::33]` reduces to ~10 (smooth after Chaikin)
3. Merge distance: the 20px merge (necessary for on-the-fly uint8 quantization gaps) is too aggressive for the small DEM grid, connecting unrelated contour fragments

**Files touched**:
- `elevation.py` — `_EPSILON` dedup, `merge_dist` threading, `compute_green_contours` format, `_merge_nearby_polylines` guard, cleanup
- `renderer.py` — removed dead `_draw_contours()`
- `tests/test_elevation.py` — updated for new `compute_green_contours` return format
- `pdf.py` — explored WGS84 pipeline, reverted to on-the-fly (net no change from HEAD)

**Next**: Tune decimation vs smoothness, curvature map, commit and PR.


## 2026-05-26 01:42 UTC

**What was done**:
- 4 structural PDF pipeline optimizations: per-hole projection (`only_hole` on `project_course`), vectorized `_in_green_mask` (`shapely.contains_xy`), skip slot computation for top-hole-only diagrams (`compute_slots=False`), inline green `fit_hole` (direct rotation+scaling replacing second full-pipeline call)
- Contour extraction: explored 1x resolution + higher merge_dist/eps tuning to fix gap artifacts; reverted to 2x extraction as the clean solution for production
- Replaced entire hand-rolled marching squares pipeline (`_marching_squares_level`, `_edge_intersections`, `_CELL_EDGES`, `_connect_segments`, `_merge_nearby_polylines` — ~212 lines) with `skimage.measure.find_contours` (3-line call). Test suite time dropped from ~4.9s to ~1.9s.
- Added conditional decimation: polylines with < 66 vertices skip `[::33]` decimation to survive the filter
- Added post-Chaikin small segment filtering: contours < 30 SVG points (~0.42 inches) dropped before SVG output
- Added `scikit-image` to `requirements.txt`

**Files touched**:
- `elevation.py` — replaced `compute_contours` with skimage call; removed 5 dead hand-rolled functions; vectorized `_in_green_mask`
- `geometry.py` — added `only_hole` parameter to `project_course`
- `pdf.py` — per-hole projection, `compute_slots` guard, inline green fit, 2x contour extraction, conditional decimation, small segment filter
- `requirements.txt` — added `scikit-image`

**Next**: Run real PDF generation, curvature map, tune contour levels, commit and PR.

## 2026-05-26 06:00 UTC

**What was done**:
- Green slot size: expanded green diagram to fill full 270×243 slot (was centered 243×243 square)
- Green slot context features: white fill with 50% opacity dashed stroke
- Break arrows feature: `_compute_arrows()` computes downhill gradient vectors from elevation shading image along contour polylines
- Arrow rendering: acute chevron (30° half-angle) arrowhead + shaft, uniform 0.75pt stroke, ~12pt spacing, chevron at anchor with shaft extending 10pt forward
- Overlay toggles: three new settings (`cartographer.green_heightmap`, `cartographer.green_contours`, `cartographer.green_arrows`), checkboxes in PDF export UI, wired through `shading_data` dict to `_draw_elevation_shading` toggle gates
- DEM extraction gate fixed to include `show_heightmap` condition
- 5 unit tests for `_compute_arrows` (gradient ridge, empty contours, short contour, zero bbox, flat image)

**Files touched**:
- `plugin.py` — 3 new settings keys
- `pdf.py` — toggle flag plumbing, DEM gate fix, slot sizing fix
- `renderer.py` — `_compute_arrows()` function, chevron arrow rendering, toggle gates in `_draw_elevation_shading`, slot context white fill + dashed stroke, `_draw_polygons` extended with `stroke_opacity`/`stroke_dasharray`
- `layout.py` — slot image size change
- `screens/pdf_export.py` — 3 overlay checkboxes
- `tests/test_renderer.py` — 5 arrow tests

**Next**: Run real PDF generation with DEM data, merge to main

## 2026-05-26 08:00 UTC

**What was done**:
- Investigated hole geometry clipping on top pages: geometry appears cut off by a straight horizontal line ~0.25" inside the content region boundaries
- Traced through the full rendering pipeline: `fit_hole()` → `render_hole()` → `render_hole_page()` → `compose_sheet()` → PDF
- Root cause identified: `render_hole_page()` in `layout.py:202` embeds the hole SVG (306×504, aspect 0.607) as an `<image>` element at size (270×486, aspect 0.556) without setting `preserveAspectRatio`
- SVG default `preserveAspectRatio="xMidYMid meet"` causes uniform scale-to-fit-width, producing ~20.6pt transparent letterbox strips at top/bottom
- The transparent strips expose `compose_sheet`'s white background, creating the visual clip effect

**Two fix options documented** in `docs/HANDOFF.md`:
- **Option A** (minimal): add `preserveAspectRatio="none"` to the image at `layout.py:202`
- **Option B** (principled): match `HOLE_CANVAS_W`/`HOLE_CANVAS_H` (270×486) to display rect aspect ratio; adjust `HOLE_LEFT_BIAS` 50→44

**Files examined**:
- `geometry.py` — `fit_hole()`, `get_hole_bounds()`, `compute_pixels_per_yard_from_geometry()`, `compute_yardage_arcs()`
- `renderer.py` — `render_hole()`, `render_hole_svg()`, `HOLE_CANVAS_W`/`HOLE_CANVAS_H`
- `layout.py` — `render_hole_page()`, `compose_sheet()`, `_draw_corner_marks()`, constants
- `pdf.py` — `_get_hole_render_data()`, `generate_book()`, `HOLE_CANVAS_W`/`HOLE_CANVAS_H`/`HOLE_LEFT_BIAS`

**Next**: Await user's choice between Option A and Option B

## 2026-05-26 08:30 UTC

**What was done**:
- Chose Option B for hole-clipping fix: matched `HOLE_CANVAS_W`/`HOLE_CANVAS_H` to display rect (270×486), adjusted `HOLE_LEFT_BIAS`
- Fixed yardage arc visibility: stroke width 0.25→0.5 for visible black rendering
- Styled hole number/par rectangle: added matching 0.5pt black stroke and 3px corner radius
- Attempted yardage arc labels via textPath and plain text — abandoned after cairosvg font rendering issues
- Fixed missing `requests` dependency in requirements.txt after CI failure
- Added DEM download progress reporting (bytes/MB/percentage via status_callback threaded through get_course_dem → _download_file)
- Released v1.2.0: bumped version, created PR #13, merged to main, tagged, synced dev

**Files touched**:
- `renderer.py` — canvas constants, arc stroke, hole/par rect styling
- `layout.py` — hole/par rect stroke+corner radius
- `pdf.py` — canvas constants, left bias, removed redundant status message, threaded callback
- `elevation.py` — download progress tracking with Content-Length header
- `requirements.txt` — added requests
- `plugin.py` — version 1.1.2→1.2.0

**Next**: Run real PDF generation, revisit arc labels, consider explicit numpy/Pillow deps

## 2026-05-26 10:15 UTC

**What was done**:
- Designed and implemented multi-hole feature support on `dev` branch
- Added split-line tool to tagger UI: toggle button, two-click line drawing with draggable markers, right-click cancel
- Server-side shapely polygon clipping (`_apply_splits`) with 1% sliver discard, course-wide feature exclusion
- Synthetic sub-feature IDs (`way/123__0`/`__1`) with `split_group` linking for merge/delete
- Split endpoints: GET/POST/DELETE `/api/splits`, plus `/api/assignments` for page-reload reconstruction
- `data.py`: `load_courses_geo_raw()` (preserves IDs/splits) + normalized `load_courses_geo()` (bare rings for consumers)
- `courses_geo.json` format: rings now `{"id":"...", "rings":[[...]]}`, new `"splits"` key; backward-compatible
- Zero changes to geometry.py, renderer.py, pdf.py, layout.py
- 14 new tests, 174 total passing

**Files touched**:
- `data.py` — `load_courses_geo_raw()`, normalized `load_courses_geo()`, `_normalize_hole_features()`
- `tagger/server.py` — split endpoints, `_apply_splits()`, `_expand_split_features()`, `_derive_assignments()`, updated `get_features()`/`save()`
- `tagger/static/index.html` — split mode toggle, line drawing, sidebar updates, save format
- `tests/test_data.py` — old/new format load tests
- `tests/test_geometry.py` — shapely split tests
- `tests/test_osm.py` — sub-feature ID tests
- `docs/superpowers/specs/2026-05-26-multi-hole-features-design.md`
- `docs/superpowers/plans/2026-05-26-multi-hole-features-plan.md`

**Next**: Manual tagger testing, run real PDF generation, cleanup git history

## 2026-05-26 20:15 UTC

**What was done**:
- Built universal undo system: stack-based (LIFO), no limit, reverses splits/assignments/unassignments
- Fixed bug: re-render features when exiting split mode to restore click interactivity
- Undo button always visible, greyed out at 30% opacity when stack empty
- Fixed JS syntax errors from partial pattern matching in replaceAll edits
- Tested server endpoints (200 OK for /api/features and /api/assignments with 133 features)

**Files touched**:
- `tagger/static/index.html` — undo stack, refreshUndoButton handler, recording at 7 action points, CSS
- `docs/HANDOFF.md` — updated next actions

**Next**: Manual tagger testing, run real PDF generation, cleanup git history (squash f1cf2b5..0898a88)
