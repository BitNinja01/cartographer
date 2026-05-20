# Cartographer

[![Release](https://img.shields.io/github/v/release/BitNinja01/cartographer.svg?style=for-the-badge&color=green)](https://github.com/BitNinja01/cartographer/releases)
[![Downloads](https://img.shields.io/github/downloads/BitNinja01/cartographer/total.svg?style=for-the-badge&color=green)](https://github.com/BitNinja01/cartographer/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/BitNinja01/cartographer/ci.yml?branch=dev&style=for-the-badge&label=CI)](https://github.com/BitNinja01/cartographer/actions)
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

## Installation

### Prerequisites

- **Python 3.11+**
- **PinSheet v1.9.7+** — the parent app must be installed and its plugin system available
- **System libraries** — `cairosvg` needs libcairo2:

| Platform | Command |
|----------|---------|
| Ubuntu/Debian | `sudo apt install libcairo2-dev` |
| macOS (Homebrew) | `brew install cairo` |
| Windows | Bundled with `cairosvg` wheel; no extra steps |

### Option 1: Release zip (recommended)

Download the latest release from the [releases page](https://github.com/BitNinja01/cartographer/releases) and extract it into PinSheet's `plugins/` directory:

```bash
# From your PinSheet install directory
mkdir -p plugins
cd plugins
wget https://github.com/BitNinja01/cartographer/releases/latest/download/cartographer_1.0.1.zip
unzip cartographer_1.0.1.zip -d cartographer
cd cartographer
pip install -r requirements.txt
```

### Option 2: Git clone

```bash
# From your PinSheet install directory
mkdir -p plugins
cd plugins
git clone https://github.com/BitNinja01/cartographer.git
cd cartographer
pip install -r requirements.txt
```

### Verify installation

Launch PinSheet — if installed correctly, you'll see Cartographer screens listed under plugin bindings. Check for:
- **Hole View** (`h` on course/round detail screens)
- **Course Gallery** (`h` to browse all 18 holes with `j`/`k` navigation)
- **Geometry Setup** (`g` on course detail screens)
- **Export PDF** (`p` on course detail screens)

---

## Quick Start

### 1. Get course geometry

**Option A — via PinSheet TUI (easiest):**
1. Add your course in PinSheet (if not already added)
2. Open the course detail screen, press `g` for Geometry Setup
3. Enter your `.osm` file path (see below) or enter the course name to auto-fetch from OpenStreetMap
4. Click **Launch Tagger** to open the browser-based tagging UI

**Option B — via Overpass API (standalone):**
```bash
python -m cartographer.tagger "Bellevue Golf Course"
```
This fetches the course from OpenStreetMap automatically — no `.osm` file needed.

**Option C — manual .osm file:**
1. Go to [openstreetmap.org](https://www.openstreetmap.org) and search for your golf course
2. Click **Export** → download the `.osm` file
3. Run: `python -m cartographer.tagger "Course Name" /path/to/course.osm`

### 2. Tag course features

The tagger UI opens in your browser. For each hole:
1. Select the hole number (◀/▶ arrows)
2. Click features on the map to assign them (fairways, greens, bunkers, water)
3. Use the **Set Scale** tool to calibrate — click two points with a known distance
4. Click **Save** when done

Water hazards and cart paths are auto-distributed to all holes. Use the type filter checkboxes to toggle feature visibility.

### 3. Generate a yardage book

**In PinSheet:** Press `p` on the course detail screen to open the PDF Export screen, configure the bottom slot content (green grid / stats / notes), and click **Export**.

**Standalone:**
```bash
PYTHONPATH=. python -m cartographer.pdf "Course Name" --output ~/yardage_books
```

Output lands in `data/plugins/cartographer/yardage_books/{course_name}/`:
```
├── sheets/      # Individual 4.25"×14" narrow PDFs
└── booklets/    # 5 saddle-stitch booklet PDFs (8.5"×14")
```

### 4. Print and assemble

Print the 5 booklets double-sided on 8.5"×14" (legal) paper, fold each in half, and saddle-stitch to create a complete yardage book.

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