# Handoff

**Last updated**: 2026-05-26 10:15 UTC

## Current state

Multi-hole feature support implemented on `dev` branch. Users can draw split lines across shared greens/fairways in the tagger to divide them between holes. Split sub-features get synthetic IDs (`way/123__0`/`__1`) and slot into the existing one-to-one assignment flow. Zero changes to `geometry.py`, `renderer.py`, `pdf.py`, or `layout.py`. 174 tests pass.

`courses_geo.json` format changed: feature rings now stored as `{"id": "...", "rings": [[...]]}` (backward-compatible — old format loads correctly). New `"splits"` key persists split lines.

## Next actions

1. **Manual tagger testing** — tag a course with shared features, split a feature, save, reload, verify assignments persist
2. **Run real PDF generation** — test with DEM data to verify arrow quality, density, and direction
3. **Revisit arc labels** — textPath approach tried but didn't render in cairosvg; simpler text approach also failed due to font availability

## Blockers

None.
