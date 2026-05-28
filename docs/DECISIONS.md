# Decisions

Durable architectural and design decisions for Cartographer. Appended chronologically; each entry records the *why*.

---

## 2026-05-18 — Cartographer is a nested git repo

The Cartographer plugin at `plugins/cartographer/` is its own standalone git repository (remote: `BitNinja01/pinsheet-cartographer.git`). The parent PinSheet repo's `.gitignore` excludes `plugins/` so the nested repo is invisible to it.

**Why**: Keeps plugin development independent — commits, branches, and history are isolated. Prevents accidental coupling between plugin and main PinSheet repo.

---

## 2026-05-18 — Inkscape replaced with shapely/svgwrite/cairosvg

The original golf-cartographer used Inkscape CLI for SVG rendering. Cartographer replaces this with pure Python libraries:
- **shapely** for geometry operations (centroids, unions)
- **svgwrite** for SVG generation
- **cairosvg** for SVG → PDF/PNG conversion

**Why**: Eliminates the Inkscape system dependency. Everything runs in-process, enabling the TUI to render hole diagrams as terminal images and generate PDFs programmatically.

---

## 2026-05-18 — Equirectangular projection with course-centroid origin

Geographic coordinates (WGS84 lat/lon) are projected to pixel space using an equirectangular projection centred on the course's centroid:

```
dx = (lon - origin_lon) * yards_per_degree_lon * pixels_per_yard
dy = -(lat - origin_lat) * yards_per_degree_lat * pixels_per_yard
```

`yards_per_degree_lon` varies with latitude via `cos(latitude)`.

**Why**: Simple, fast, and accurate enough for golf-course scale (a few hundred yards across). The centroid origin minimises distortion. Y-axis is flipped so north is up in SVG space.

---

## 2026-05-18 — Chaikin smoothing for OSM polygon quality

Raw OSM polygon data produces jagged SVG paths. Chaikin's corner-cutting algorithm (3 iterations) smooths all polygon rings without external dependencies:

```
q = 0.75 * p0 + 0.25 * p1
r = 0.25 * p0 + 0.75 * p1
```

**Why**: Zero-dependency, converges to a cubic B-spline, and the `rendering` cost is negligible. Paths (LineStrings) are excluded from smoothing since they don't form closed loops.

---

## 2026-05-18 — OSM multipolygon relations parsed

Most fairways on real-world courses are stored as `<relation type="multipolygon">` elements in OSM. A two-pass parser handles: collect all ways first, then process relations (outer members only), then standalone ways. Inner-role members are consumed but ring geometry not yet supported.

**Why**: Without relation parsing, 16 of 18 fairways are invisible on typical courses (tested: Bellevue/West Seattle).

---

## 2026-05-18 — Two-phase OSM classification: exclude-first, then match

`_classify_tags()` follows:
1. **Exclude phase**: filter out non-golf infrastructure (`highway`, `building`, `amenity`, `bridge`, `tunnel`, `railway`, `power`, `man_made`). Exception: `golf=cartpath` bypasses `highway=path` exclusion.
2. **Match phase**: `golf=*` tags first, then `natural=water`, `waterway=*`, `water=*`, `landuse=grass` (→ fairway), `barrier=*`.

**Why**: Exclude-first prevents false positives from stadium buildings, maintenance sheds, and footpaths. The two-phase approach reduced unclassified features from 500 to 0 for test data (589 total → 110 relevant).

---

## 2026-05-19 — Water and paths auto-distributed to all 18 holes

Water hazards and cart paths often span multiple holes or lie between them. Rather than requiring manual per-hole assignment, the tagger UI marks these as course-wide ("CW") and distributes them to all 18 holes on save.

**Why**: Eliminates tedious per-hole manual assignment for features that are inherently multi-hole. Prevents water/paths from disappearing from individual hole diagrams.

---

## 2026-05-19 — 20-page cross-paired PDF with saddle-stitch booklets

The yardage book uses a cross-paired layout: top of each sheet shows hole N, bottom shows data for the complementary hole (18-N). 20 sheets combine into 5 saddle-stitch booklets (8.5"×14"). Front/back covers, club distance chart, notes page, and course overview included.

**Why**: Cross-pairing ensures complementary hole data appears on the same physical sheet. Saddle-stitch assembly matches traditional yardage book printing. Named terminology: Booklet > Sheet > Page.

---

## 2026-05-19 — Fonts installed to system on plugin init

JetBrainsMono Nerd Font (5 variants) is copied to `~/.local/share/fonts/pinsheet/` on plugin `__init__` with `fc-cache` refresh.

**Why**: SVG text rendering via cairosvg/Pango requires fonts available at the system level, not bundled in the plugin directory. The copy-on-first-load pattern avoids re-copying if fonts are already present.

---

## 2026-05-20 — Session memory framework

Following the parent PinSheet repo pattern, Cartographer now uses a four-file memory framework:
- `docs/HANDOFF.md` — current state and next actions
- `docs/SESSION_LOG.md` — chronological session history
- `docs/DECISIONS.md` — this file, durable decisions
- `docs/RUNBOOK.md` — operational commands

**Why**: Same reasoning as parent — splits state, history, decisions, and commands into separate authority files. Enables effective session handoff between OpenCode sessions.

---

## 2026-05-20 — Test suite design

Tests use synthetic factory fixtures that produce data matching the real JSON shapes:
- `make_round` — creates round dicts in PinSheet's string-valued format with "H" for hits
- `make_course_geo` — creates projected hole geometry dicts with pixel-coordinate features
- `make_osm_feature` — creates OSM-like feature dicts for classification testing

**Why**: Synthetic data enables precise assertions and edge-case testing without depending on real course data or OSM API access. Matches the parent PinSheet repo's two-layer fixture strategy (synthetic + real data), though cartographer currently uses only synthetic fixtures since OSM file fixtures would need real download data.

---

## 2026-05-21 — Waterway type split: "waterway" vs "water"

OSM `waterway=*` tags (stream, river, ditch, canal, drain) are open linestring features; `natural=water`, `water=*`, and `golf=water_hazard` are closed polygon features. These are classified as distinct types: `"waterway"` (open) and `"water"` (closed). Closed `waterway=*` ways (first node == last node) are reclassified back to `"water"` at parse time.

**Why**: Treating both as `"water"` caused S-curve streams to be serialised as GeoJSON Polygons, closing the tail back to the head and rendering as filled blobs. Splitting at classification time flows cleanly through the API serialiser (LineString vs Polygon), save handler, geometry pipeline, and renderer without needing a topology flag on every feature dict.

---

## 2026-05-21 — Waterway/water/path are course-wide and non-taggable

Water bodies, waterway linestrings, and cart paths are auto-distributed to all 18 holes on save. They are not shown in the feature list, have no click handler, are non-interactive on the Leaflet map (`interactive: false`), and have no filter toggle in the sidebar.

**Why**: These features span multiple holes or lie between them. Manual per-hole assignment is unnecessary friction and would produce incorrect results (e.g. a stream that crosses holes 7–10 silently missing from holes 8 and 9). Auto-distribution matches real course geometry.

---

## 2026-05-21 — Auto-scale: pixels_per_yard derived per-hole at render time

The manual two-point scale calibration step has been removed from the tagger. `pixels_per_yard` is now computed at render time by `compute_pixels_per_yard_from_geometry()` using the haversine diagonal of each hole's own lat/lon bounding box divided by the available canvas height.

**Why**: The old system derived `pixels_per_yard` from screen pixel distance at the Leaflet map's current zoom level — zoom-dependent and with no stable relationship to SVG canvas space. The key invariant for correct yardage arc radii is that `ppy × scale_factor` must cancel to `dim_fit` (the per-axis canvas fit ratio); this only holds when `project_course` and `compute_yardage_arcs` use the same `ppy`. Deriving `ppy` per-hole from raw lat/lon geometry guarantees this cancellation.

The tagger saves `pixels_per_yard: 1.0` as a nominal placeholder. Existing tagged courses need no re-tagging — scale is re-derived from the lat/lon coordinates already stored in `courses_geo.json`.

---

## 2026-05-22 — Release notes fetched from merged PR body via `gh`

The release workflow no longer reads from a `dist/cartographer_{version}.txt` file. Instead, it fetches the most recently merged PR body using `gh pr list --state merged --base main --limit 1 --json body --jq '.[0].body'`.

**Why**: The `.txt` file was error-prone — it was easy to forget to write it, falling back to a generic "Release X.Y.Z" message. The PR body is already written as part of the release pipeline, so fetching it directly ensures release notes are always correct without an extra file to maintain. Matches the parent PinSheet repo's approach.

---

## 2026-05-22 — Stats panel rendered as per-quadrant tables with ` · ` delimiter

The four bottom-slot stat boxes (FAIRWAY MISSES, GIR MISSES, SCORE, PENALTIES) now render as mini 2-column tables: a bold header row replaces the old centered label, and each entry point (L:, R:, S:, LO:, Avg:, Exp:) is a row with a right-aligned label cell and a blank left-aligned value cell for hand-writing. The stat fallback strings (previously `"_____________"`) use ` · ` as a delimiter matching the computed stat format, so both fallback and computed values split identically in the layout renderer.

**Why**: The old loose-text layout was hard to fill in by hand — no visual structure told the user where to write. The table format gives clear entry zones, aligns colons vertically, and makes the stat panel consistent with the chart page grid. Using ` · ` as a universal delimiter keeps the stat functions' return values simple while allowing the layout layer to stack lines vertically.

---

## 2026-05-25 — Topographical contours extracted from normalized hillshade, not raw DEM

Contour lines overlaid on the hillshade are extracted from the auto-leveled, upscaled, blurred grayscale image at fixed intensity intervals (12 levels evenly spaced across 0–255), not from raw DEM z-values. The marching squares runs on a 2× SVG-space resolution image (upsampled from the hillshade PIL Image), coordinates are scaled back to SVG space and 3-iteration Chaikin-smoothed.

**Why**: Extracting from the normalized image means contours are auto-leveled to the green's own elevation range (white=high, black=low). No need to know absolute meter values. The 2× extraction resolution + Chaikin smoothing produces smooth paths without the performance cost of full-resolution extraction. Caching per hole avoids redundant marching-squares runs (~18 unique computations instead of ~36).

---

## 2026-05-25 — Context features in green slots use unsmoothed projected data

Fairway, water, bunkers, rough_boundary, and paths rendered around the green in bottom slots use the raw projected (unsmoothed) geometry with 1-iteration Chaikin. The smoothed geometry from `smooth_hole_geometry` has 8× vertex expansion (3 iterations of Chaikin), which is both unnecessary at the slot scale (~250×300pt canvas) and caused a severe performance regression when transformed per-page.

**Why**: 1 iteration of Chaikin on the unsmoothed projected rings smooths OSM jagged edges without the 8× vertex cost. Original OSM features have ~30–50 vertices per ring; even 2× from 1-iteration Chaikin is imperceptible at slot resolution while keeping SVG polygon generation and cairosvg rasterization fast.

---

## 2026-05-25 — Two-phase contour polyline welding in `_connect_segments`

The original `_connect_segments` used greedy vertex-based walking — at fork points (degree 3+ from marching squares saddle cases), it followed `neighbors[0]` and abandoned other branches, creating orphan polylines. Replaced with two-phase welding:

1. **Vertex deduplication** (spatial hash, 0.5px epsilon): before building the adjacency graph, each segment endpoint is snapped to a canonical coordinate if one exists within epsilon. Eliminates floating-point alias vertices that broke the graph.
2. **Polyline merging** (spatial hash, 20px radius): after extracting polylines, endpoints from different fragments within the merge radius are connected via a greedy closest-pair loop. Bridges genuine image gaps from the low-res shading image.

**Why**: The 136×80 source image produces dozens of disconnected contour fragments at marching-squares resolution. Vertex dedup alone fixes adjacency gaps; polyline merging bridges the remaining image-level discontinuities (pixel gaps caused by the uint8 intensity quantization). The two phases operate at different scales — 0.5px for floating-point aliases, 20px for genuine image gaps. Result: 63 fragments → 22 connected polylines.

Contour decimation at 3% density (`[::33]`) runs AFTER welding — with connected lines, decimation produces smooth curves via Chaikin (3 iterations) without destroying fragments.

---

## 2026-05-25 — On-the-fly contour extraction preferred over WGS84 pipeline for rendering

The WGS84 contour pipeline (`compute_green_contours` → lat/lon paths → `project_course` → SVG coords) was explored as a performance optimization (marching squares on small DEM grid, cached once). It was abandoned for PDF rendering after three root causes were identified:

1. **Coordinate mismatch**: the round-trip DEM grid → CRS → WGS84 → equirectangular projection introduces transform error relative to the direct grid → SVG mapping used by the on-the-fly approach
2. **Grid resolution**: the DEM grid (~120×80 after 4× upsampling) produces ~60 contour vertices per path; `[::33]` decimation reduces to 2 points, producing garbled straight segments. The on-the-fly grid (~600×400 after 2× SVG resize) produces ~300 vertices; decimation preserves ~10, producing smooth curves after Chaikin
3. **Merge distance**: the 20px polyline merge (needed for on-the-fly uint8 quantization gaps) is proportionally too large for the small DEM grid, connecting unrelated contour fragments

**Why**: The on-the-fly approach (marching squares on the positioned 2× hillshade image at render time) is the correct rendering path. Its per-hole cost is acceptable since the SVG-space result is cached after first computation. The WGS84 pipeline remains useful for TUI screens and diagnostics where the smaller coordinate space doesn't cause visible artifacts. The `compute_green_contours`/`compute_all_green_contours` functions and `merge_dist` parameter are retained for potential future use with an appropriate resolution and decimation strategy.

---

## 2026-05-26 — Hand-rolled marching squares replaced with `skimage.measure.find_contours`

The custom marching squares + segment dedup + adjacency graph tracing + polyline merge pipeline (~212 lines across 5 functions) was replaced with a single `skimage.measure.find_contours(z, level)` call (3 lines). Skimage handles saddle-point resolution, continuous contour tracing, and boundary termination correctly out of the box.

**Why**: The hand-rolled pipeline had persistent gap/merge issues at 1× resolution. Skimage's implementation is C/NumPy-optimized, produces clean continuous polylines (open at grid boundaries, closed internally), and eliminated the entire weld/dedup/gap complexity. Test suite runtime dropped from ~4.9s to ~1.9s. Added `scikit-image` as a project dependency.

---

## 2026-05-26 — Contour extraction kept at 2× hillshade image resolution

1× resolution contour extraction was explored as a speed optimization but produced gap artifacts in continuous lines that couldn't be resolved with merge distance / epsilon tuning. The 2× approach (resize shading image to 2× SVG bbox before extraction, divide coordinates by 2) was retained.

**Why**: At 1×, the coarser grid (~200×150) produced gaps that the skimage contour tracer correctly identified as separate segments (genuine pixel gaps in the uint8 image). At 2× (~400×300), these gaps are proportionally smaller and the contours come through as continuous. The 2× resize + extraction cost is small relative to the rest of the pipeline and produces reliable results.

---

## 2026-05-26 — Short contour segments filtered post-Chaikin

Contour polylines shorter than 30 SVG points (~0.42 inches at 72 DPI) after Chaikin smoothing are dropped from the output. Polylines with fewer than 66 raw vertices skip the `[::33]` decimation to avoid being dropped entirely.

**Why**: Small contour fragments (single-pixel marching squares artifacts, edge noise) are invisible at print scale and increase SVG rendering overhead. The 30-point threshold is below the resolution of ink on paper.

---

## 2026-05-26 — Multi-hole feature support via geometry-level split before tagging

Shared greens and fairways (common on links-style courses) are handled by drawing split lines across OSM polygons in the tagger UI *before* hole assignment. Shapely `ops.split()` physically clips the geometry into sub-features with synthetic IDs (`way/123__0`, `way/123__1`). The sub-features then slot into the existing one-to-one assignment flow.

**Why**: Splitting geometry before tagging means the entire downstream pipeline — `fit_hole()`, `render_hole()`, `project_course()`, `smooth_hole_geometry()`, `pdf.py`, `layout.py` — requires zero changes. Each sub-feature behaves like any other feature. Storing split lines as WGS84 lat/lon pairs in `"splits"` allows re-editing and re-clipping on tagger reload.

---

## 2026-05-26 — `courses_geo.json` format: feature rings wrapped with IDs

Feature geometry entries changed from bare `[[[lat,lon]]]` lists to `{"id": "way/123__0", "rings": [[[lat,lon]]]}` dicts. A new `"splits"` key stores split lines. `load_courses_geo()` normalizes to bare rings (for geometry/render/PDF consumers), while `load_courses_geo_raw()` preserves IDs (for the tagger's save/load cycle). Old-format detection at load time ensures backward compatibility.

**Why**: Feature IDs are needed for assignment reconstruction on page reload (the tagger must know which sub-feature belongs to which hole) and for the undo stack (to re-merge split features). The two-load-path design keeps consumer code unchanged while giving the tagger access to IDs.

---

## 2026-05-26 — Universal undo as a LIFO stack

The undo button reverses the last action of any type — feature assignment, unassignment, or split-line creation. Actions are pushed onto a stack and popped in reverse order. The button is always visible but disabled when the stack is empty.

**Why**: Users frequently make mistakes when tagging (wrong hole, accidentally split a feature). A stack-based undo is familiar, predictable, and handles all action types uniformly. No limit means the user can unwind any sequence of mistakes from a tagging session.

---

## 2026-05-28 — Style-based feature visibility replaces hide-on-assign

Assigned features are never removed from the Leaflet map. Instead, `refreshFeatureStyles()` iterates the `layers` dict and sets styles: red border (`color: var(--danger)`, weight 3) for features assigned to the current hole, default type color (weight 2) otherwise. No `map.removeLayer()` calls for assignment state.

**Why**: The old hide-on-assign model made it impossible to see what had been covered across the course. Users would accidentally unassign features because assigned ones were invisible. Style-based indication lets the user see everything at once while clearly distinguishing current-hole assignments. Switching holes updates all styles via a single `refreshFeatureStyles()` call — no layer rebuild needed.

---

## 2026-05-28 — Many-to-many assignments via Map-of-Sets

`featureAssignments` changed from `{osm_id: hole_number}` to `Map<osm_id, Set<hole_numbers>>`. Features can belong to multiple holes simultaneously. The save handler iterates the Set and distributes the feature into each hole's geometry bucket.

**Why**: Real courses share features between holes (a bunker between fairways, a green complex serving two holes). The old one-to-one model forced either arbitrary single-ownership or course-wide auto-distribution. Many-to-many lets the user decide which holes a feature belongs to, and the map shows red borders for ALL features assigned to the current hole — regardless of other affiliations.
