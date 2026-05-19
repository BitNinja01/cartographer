# plugins/cartographer/layout.py
"""Page layout composition for Cartographer yardage books.

Produces a single 4.25" x 14" SVG page containing:
  - Top section: hole layout diagram
  - Middle section: green detail with grid
  - Bottom section: notes lines
  - Header: hole number, par, tee yardages
"""
from __future__ import annotations

import svgwrite

# Page dimensions in SVG points (72 points per inch)
PAGE_W = 306.0    # 4.25 * 72
PAGE_H = 1008.0   # 14 * 72

HEADER_H = 60.0
HOLE_H = 480.0
GREEN_H = 280.0
NOTES_H = PAGE_H - HEADER_H - HOLE_H - GREEN_H  # remainder


def compose_page(
    hole_svg: str,
    green_svg: str,
    hole_num: int,
    par: int,
    tee_yardages: dict,
) -> str:
    """Compose a full yardage book page SVG.

    hole_svg: SVG string from renderer.render_hole()
    green_svg: SVG string from renderer.render_green()
    hole_num: 1-18
    par: hole par (3, 4, or 5)
    tee_yardages: {tee_name: yardage} e.g. {"blue": 377, "white": 362, "red": 337}

    Returns an SVG string representing the full page.
    """
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{PAGE_H}pt"),
        viewBox=f"0 0 {PAGE_W} {PAGE_H}",
    )

    # White background
    dwg.add(dwg.rect(insert=(0, 0), size=(PAGE_W, PAGE_H), fill="white"))

    # --- Header ---
    dwg.add(dwg.rect(
        insert=(0, 0), size=(PAGE_W, HEADER_H),
        fill="#F5F5F5", stroke="#ccc", stroke_width=0.5,
    ))

    # Hole number (large, left)
    dwg.add(dwg.text(
        str(hole_num),
        insert=(16, HEADER_H * 0.72),
        font_size="32pt",
        font_weight="bold",
        font_family="monospace",
        fill="#212121",
    ))

    # Par (smaller, below hole number label)
    dwg.add(dwg.text(
        f"Par {par}",
        insert=(16, HEADER_H * 0.95),
        font_size="9pt",
        font_family="monospace",
        fill="#555",
    ))

    # Tee yardages (right side)
    tee_display_order = ["blue", "white", "red", "gold", "black", "green"]
    tee_colour_map = {
        "blue": "#1565C0", "white": "#555", "red": "#C62828",
        "gold": "#F9A825", "black": "#212121", "green": "#2E7D32",
    }
    y_start = 18.0
    for tee_name in tee_display_order:
        if tee_name not in tee_yardages:
            continue
        yardage = tee_yardages[tee_name]
        col = tee_colour_map.get(tee_name, "#333")
        dwg.add(dwg.text(
            f"{tee_name.upper()}  {yardage}",
            insert=(PAGE_W - 90, y_start),
            font_size="9pt",
            font_family="monospace",
            fill=col,
        ))
        y_start += 13.0

    # --- Hole diagram (embed as nested SVG) ---
    dwg.add(dwg.image(
        href="data:image/svg+xml," + hole_svg.replace("#", "%23"),
        insert=(0, HEADER_H),
        size=(PAGE_W, HOLE_H),
    ))

    # --- Green detail (embed as nested SVG) ---
    green_y = HEADER_H + HOLE_H
    dwg.add(dwg.rect(
        insert=(0, green_y), size=(PAGE_W, GREEN_H),
        fill="white", stroke="#ccc", stroke_width=0.5,
    ))
    dwg.add(dwg.image(
        href="data:image/svg+xml," + green_svg.replace("#", "%23"),
        insert=(PAGE_W / 2 - GREEN_H / 2, green_y + 10),
        size=(GREEN_H - 20, GREEN_H - 20),
    ))

    # --- Notes lines ---
    notes_y = green_y + GREEN_H
    line_spacing = 18.0
    x_margin = 12.0
    y = notes_y + line_spacing
    while y < PAGE_H - 6:
        dwg.add(dwg.line(
            start=(x_margin, y),
            end=(PAGE_W - x_margin, y),
            stroke="#ddd",
            stroke_width=0.5,
        ))
        y += line_spacing

    return dwg.tostring()


# Cross-pairing strategy: maps hole index (0-based) to (layout_hole, green_hole)
# Pairs front-9 holes with back-9 greens for the saddle-stitch booklet layout
CROSS_PAIRS = [
    (9, 9), (8, 10), (7, 11), (6, 12), (5, 13), (4, 14),
    (3, 15), (2, 16), (1, 17), (0, 18), (10, 8), (11, 7),
    (12, 6), (13, 5), (14, 4), (15, 3), (16, 2), (17, 1),
    (18, 0), (0, 0),  # hole 18 + back cover placeholder
]
