# Cartographer

[![Release](https://img.shields.io/github/v/release/BitNinja01/cartographer.svg?style=for-the-badge&color=green)](https://github.com/BitNinja01/cartographer/releases)
[![Downloads](https://img.shields.io/github/downloads/BitNinja01/cartographer/total.svg?style=for-the-badge&color=green)](https://github.com/BitNinja01/cartographer/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/BitNinja01/cartographer/ci.yml?branch=main&style=for-the-badge&label=CI)](https://github.com/BitNinja01/cartographer/actions)
[![Platform](https://img.shields.io/badge/Platforms-Linux%20|%20macOS%20|%20Windows-white.svg?style=for-the-badge&color=green)](https://github.com/BitNinja01/cartographer)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg?style=for-the-badge&color=green)](https://www.python.org/downloads/)

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

---

## PDF Structure

Each exported PDF is 4.25" × 14" (306pt × 1008pt), containing **two pages** vertically stacked:
- **Top page**: 4.25" × 7" (306pt × 504pt)
- **Bottom page**: 4.25" × 7" (306pt × 504pt)
- **Margin**: 0.25" (18pt) on all sides of each page

### 20-Page Layout (Cross-Paired)

The yardage book consists of 20 narrow PDFs with strategic cross-pairing:

| Page | Top | Bottom | Page | Top | Bottom |
|------|-----|--------|------|-----|--------|
| 1 | Hole 9 | Hole 9 data | 11 | Hole 10 | Hole 8 data |
| 2 | Hole 8 | Hole 10 data | 12 | Hole 11 | Hole 7 data |
| 3 | Hole 7 | Hole 11 data | 13 | Hole 12 | Hole 6 data |
| 4 | Hole 6 | Hole 12 data | 14 | Hole 13 | Hole 5 data |
| 5 | Hole 5 | Hole 13 data | 15 | Hole 14 | Hole 4 data |
| 6 | Hole 4 | Hole 14 data | 16 | Hole 15 | Hole 3 data |
| 7 | Hole 3 | Hole 15 data | 17 | Hole 16 | Hole 2 data |
| 8 | Hole 2 | Hole 16 data | 18 | Hole 17 | Hole 1 data |
| 9 | Hole 1 | Hole 17 data | 19 | Hole 18 | Notes |
| 10 | Chart | Hole 18 data | 20 | Back Page | Front Page |

**"Hole data"** refers to the configurable bottom slot content (green grid, stats panel, or notes based on user export settings).

### Booklet Assembly

The 20 narrow PDFs are combined into 5 saddle-stitch booklets (8.5" × 14" each):
- **Booklet 1**: Pages 1-2 + 11-12
- **Booklet 2**: Pages 3-4 + 13-14
- **Booklet 3**: Pages 5-6 + 15-16
- **Booklet 4**: Pages 7-8 + 17-18
- **Booklet 5**: Pages 9-10 + 19-20