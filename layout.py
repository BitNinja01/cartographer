# plugins/cartographer/layout.py
"""Page layout composition for Cartographer yardage books.

Produces a single 4.25" x 14" SVG page containing:
  - Top half: hole layout diagram with hole number, par, and tee yardages
  - Bottom half: two configurable content slots (green grid, stats panel, or notes)
"""
from __future__ import annotations

import svgwrite

# Page dimensions in SVG points (72 points per inch)
PAGE_W = 306.0    # 4.25 * 72
PAGE_H = 1008.0   # 14 * 72
MARGIN = 18.0     # 0.25 * 72
PRINTABLE_W = PAGE_W - 2 * MARGIN  # 270pt
PRINTABLE_H = PAGE_H - 2 * MARGIN  # 972pt

TOP_HALF_H = 486.0   # 6.75 * 72
BOTTOM_HALF_H = 486.0
SLOT_H = 243.0       # half of bottom half


def compose_page(
    hole_svg: str,
    hole_num: int,
    par: int,
    tee_yardages: dict,
    slot1_content: str,  # "green_grid", "stats_panel", or "notes"
    slot2_content: str,
    slot1_svg: str = "",  # pre-rendered SVG for slot 1 (if applicable)
    slot2_svg: str = "",  # pre-rendered SVG for slot 2 (if applicable)
    stats_data: dict | None = None,  # {hole_num: {stat_name: value}}
) -> str:
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{PAGE_H}pt"),
        viewBox=f"0 0 {PAGE_W} {PAGE_H}",
    )

    # White background
    dwg.add(dwg.rect(insert=(0, 0), size=(PAGE_W, PAGE_H), fill="white"))

    # --- Top half: hole diagram with overlays ---
    # Embed hole SVG
    dwg.add(dwg.image(
        href="data:image/svg+xml," + hole_svg.replace("#", "%23"),
        insert=(MARGIN, MARGIN),
        size=(PRINTABLE_W, TOP_HALF_H),
    ))

    # Overlay: hole number + par (upper-right)
    dwg.add(dwg.text(
        str(hole_num),
        insert=(PAGE_W - MARGIN - 10, MARGIN + 35),
        font_size="32pt",
        font_weight="bold",
        font_family="JetBrainsMono, monospace",
        fill="#212121",
        text_anchor="end",
    ))
    dwg.add(dwg.text(
        f"Par {par}",
        insert=(PAGE_W - MARGIN - 10, MARGIN + 52),
        font_size="9pt",
        font_family="JetBrainsMono, monospace",
        fill="#555",
        text_anchor="end",
    ))

    # Overlay: tee yardages (bottom-right, sorted shortest to longest)
    tee_display_order = ["red", "gold", "white", "blue", "black", "green"]
    tee_colour_map = {
        "blue": "#1565C0", "white": "#555", "red": "#C62828",
        "gold": "#F9A825", "black": "#212121", "green": "#2E7D32",
    }

    # Sort tees by yardage (shortest first)
    sorted_tees = sorted(
        [(name, tee_yardages[name]) for name in tee_display_order if name in tee_yardages],
        key=lambda x: x[1]
    )

    bg_width = 80
    bg_height = 11
    y_tee = MARGIN + TOP_HALF_H - 15 - (len(sorted_tees) * 13)
    for tee_name, yardage in sorted_tees:
        col = tee_colour_map.get(tee_name, "#333")
        dwg.add(dwg.rect(
            insert=(PAGE_W - MARGIN - 10 - bg_width, y_tee - 9),
            size=(bg_width, bg_height),
            fill="white",
            stroke="none",
        ))
        dwg.add(dwg.text(
            f"{tee_name.upper()} : {yardage}",
            insert=(PAGE_W - MARGIN - 10, y_tee),
            font_size="9pt",
            font_family="JetBrainsMono, monospace",
            fill=col,
            text_anchor="end",
        ))
        y_tee += 13.0

    # --- Bottom half: two slots ---
    slot1_y = MARGIN + TOP_HALF_H
    slot2_y = slot1_y + SLOT_H

    # Render slot 1
    _render_slot(dwg, slot1_content, slot1_svg, stats_data, hole_num,
                 MARGIN, slot1_y, PRINTABLE_W, SLOT_H)

    # Render slot 2
    _render_slot(dwg, slot2_content, slot2_svg, stats_data, hole_num,
                 MARGIN, slot2_y, PRINTABLE_W, SLOT_H)

    return dwg.tostring()


def _render_slot(
    dwg: svgwrite.Drawing,
    content_type: str,
    svg_content: str,
    stats_data: dict | None,
    hole_num: int,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """Render a single slot (green grid, stats panel, or notes)."""
    if content_type == "green_grid":
        # Embed pre-rendered green SVG
        if svg_content:
            dwg.add(dwg.image(
                href="data:image/svg+xml," + svg_content.replace("#", "%23"),
                insert=(x + width / 2 - height / 2, y),
                size=(height, height),  # square, centered
            ))

    elif content_type == "stats_panel":
        # 2x2 grid of stat boxes
        box_w = width / 2
        box_h = height / 2

        stats = []
        if stats_data and hole_num in stats_data:
            hole_stats = stats_data[hole_num]
            stats = [
                ("FAIRWAY MISSES", hole_stats.get("fairway_misses", "_____________")),
                ("GIR MISSES", hole_stats.get("gir_misses", "_____________")),
                ("VS EXPECTED", hole_stats.get("benchmark", "_____________")),
                ("PENALTIES", hole_stats.get("penalties", "_____________")),
            ]
        else:
            stats = [
                ("FAIRWAY MISSES", "_____________"),
                ("GIR MISSES", "_____________"),
                ("VS EXPECTED", "_____________"),
                ("PENALTIES", "_____________"),
            ]

        positions = [
            (x, y),                          # top-left
            (x + box_w, y),                  # top-right
            (x, y + box_h),                  # bottom-left
            (x + box_w, y + box_h),          # bottom-right
        ]

        for (bx, by), (label, value) in zip(positions, stats):
            # Border
            dwg.add(dwg.rect(
                insert=(bx, by),
                size=(box_w, box_h),
                fill="white",
                stroke="#ccc",
                stroke_width=0.5,
            ))

            # Label (small caps, top)
            dwg.add(dwg.text(
                label,
                insert=(bx + box_w / 2, by + 20),
                font_size="9pt",
                font_family="monospace",
                fill="#555",
                text_anchor="middle",
            ))

            # Value (centered)
            dwg.add(dwg.text(
                value,
                insert=(bx + box_w / 2, by + box_h / 2 + 5),
                font_size="11pt",
                font_family="monospace",
                fill="#212121",
                text_anchor="middle",
            ))

    elif content_type == "notes":
        # Ruled lines
        line_spacing = 18.0
        margin_x = 12.0
        line_y = y + line_spacing
        while line_y < y + height - 6:
            dwg.add(dwg.line(
                start=(x + margin_x, line_y),
                end=(x + width - margin_x, line_y),
                stroke="#ddd",
                stroke_width=0.5,
            ))
            line_y += line_spacing
