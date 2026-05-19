# Cartographer

A PinSheet plugin that generates yardage book PDFs from OpenStreetMap course geometry.

- **Hole View** — per-hole layout diagrams in-app, showing fairways, greens, bunkers, water, and yardage arcs
- **Course Gallery** — browse all 18 holes with j/k navigation
- **Yardage Book** — export a saddle-stitch printable PDF booklet (4.25" × 14" pages)
- **Tagger UI** — browser-based visual tool for assigning OSM features to holes and setting scale

### Setup

```bash
pip install -r requirements.txt
python -m cartographer.tagger "Course Name"   # tag a course
```

Requires the PinSheet plugin system (v1.9.7+).