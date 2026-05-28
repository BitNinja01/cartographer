# Handoff

**Last updated**: 2026-05-28 22:00 UTC

## Current state

Tagger UX completely redesigned: many-to-many assignments with Add/Remove toggles, always-visible map features with red borders, Submit→Review→Confirm save flow with green-completeness warnings, ctrl-drag multi-select with Turf.js polygon intersection. v1.4.0 released and merged to main. dev is synced.

## Next actions

1. **Manual end-to-end test** — launch the tagger with Salish Cliffs, assign greens/features to all 18 holes, verify Submit→Review→Confirm flow, test ctrl-drag, test undo, save and verify courses_geo.json
2. **Run real PDF generation** — test the yardage book output with a fully tagged course to verify all hole diagrams render correctly
3. **Performance test** — test ctrl-drag with Turf.js on courses with 200+ features to ensure no lag

## Blockers

None.
