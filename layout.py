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

# Half-page dimensions (7" tall, used for special pages)
HALF_PAGE_H = 504.0  # 7 * 72
HALF_PAGE_PRINTABLE_H = HALF_PAGE_H - 2 * MARGIN  # 468pt

TOP_HALF_H = 486.0   # 6.75 * 72
BOTTOM_HALF_H = 486.0
SLOT_H = 243.0       # half of bottom half

# Hole number circle (adjustable)
HOLE_NUMBER_CIRCLE_RADIUS = 16.0  # Experiment with this value

TEE_DISPLAY_ORDER = ["red", "gold", "white", "blue", "black", "green"]
TEE_COLOUR_MAP = {
    "blue": "#1565C0", "white": "#555", "red": "#C62828",
    "gold": "#F9A825", "black": "#212121", "green": "#2E7D32",
}


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
    # Position: 0.125" inset from printable area edges (0.375" from page edge)
    inset = 9.0  # 0.125 * 72
    circle_cx = PAGE_W - MARGIN - inset
    circle_cy = MARGIN + inset
    
    # Circle with hole number inside
    dwg.add(dwg.circle(
        center=(circle_cx, circle_cy),
        r=HOLE_NUMBER_CIRCLE_RADIUS,
        fill="white",
        stroke="#000000",
        stroke_width=1.0,
    ))
    dwg.add(dwg.text(
        str(hole_num),
        insert=(circle_cx, circle_cy + 8),  # +8 for vertical centering
        font_size="24pt",
        font_family="JetBrainsMono, monospace",
        fill="#212121",
        text_anchor="middle",
    ))
    
    # Par number centered below circle
    par_y = circle_cy + HOLE_NUMBER_CIRCLE_RADIUS + 14  # 14pt below circle edge
    dwg.add(dwg.text(
        f"Par {par}",
        insert=(circle_cx, par_y),
        font_size="9pt",
        font_family="JetBrainsMono, monospace",
        fill="#555",
        text_anchor="middle",
    ))

    # Overlay: tee yardages (bottom-right, sorted shortest to longest)
    sorted_tees = sorted(
        [(name, tee_yardages[name]) for name in TEE_DISPLAY_ORDER if name in tee_yardages],
        key=lambda x: x[1]
    )

    bg_width = 80
    bg_height = 11
    y_tee = MARGIN + TOP_HALF_H - 15 - (len(sorted_tees) * 13)
    for tee_name, yardage in sorted_tees:
        col = TEE_COLOUR_MAP.get(tee_name, "#333")
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


def compose_front_page(
    course_name: str,
    location: dict[str, str] | None = None,
    total_par: int = 0,
    tee_totals: dict[str, int] | None = None,
) -> str:
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{HALF_PAGE_H}pt"),
        viewBox=f"0 0 {PAGE_W} {HALF_PAGE_H}",
    )

    dwg.add(dwg.rect(insert=(0, 0), size=(PAGE_W, HALF_PAGE_H), fill="white"))

    name_y = HALF_PAGE_H / 3
    dwg.add(dwg.text(
        course_name,
        insert=(PAGE_W / 2, name_y),
        font_size="24pt",
        font_weight="bold",
        font_family="JetBrainsMono, monospace",
        fill="#212121",
        text_anchor="middle",
    ))

    loc_str = ""
    if location:
        city = location.get("city", "")
        state = location.get("state") or location.get("state/province", "")
        country = location.get("country", "")
        parts = [p for p in [city, state, country] if p]
        loc_str = ", ".join(parts)
    if loc_str:
        dwg.add(dwg.text(
            loc_str,
            insert=(PAGE_W / 2, name_y + 36),
            font_size="11pt",
            font_family="JetBrainsMono, monospace",
            fill="#555",
            text_anchor="middle",
        ))

    par_y = name_y + (36 if loc_str else 0) + 30
    dwg.add(dwg.text(
        f"Par {total_par}",
        insert=(PAGE_W / 2, par_y),
        font_size="14pt",
        font_family="JetBrainsMono, monospace",
        fill="#212121",
        text_anchor="middle",
    ))

    if tee_totals:
        sorted_tees = sorted(
            [(n, tee_totals[n]) for n in TEE_DISPLAY_ORDER if n in tee_totals],
            key=lambda x: x[1],
        )
        table_y = par_y + 40
        for tee_name, yardage in sorted_tees:
            col = TEE_COLOUR_MAP.get(tee_name, "#333")
            dwg.add(dwg.rect(
                insert=(PAGE_W / 2 - 60, table_y - 7),
                size=(8, 8),
                fill=col,
                stroke="none",
            ))
            dwg.add(dwg.text(
                f"{tee_name.upper()} : {yardage}",
                insert=(PAGE_W / 2, table_y),
                font_size="11pt",
                font_family="JetBrainsMono, monospace",
                fill="#212121",
                text_anchor="middle",
            ))
            table_y += 18

    return dwg.tostring()


def compose_back_page(
    full_course_svg: str | None = None,
) -> str:
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{HALF_PAGE_H}pt"),
        viewBox=f"0 0 {PAGE_W} {HALF_PAGE_H}",
    )

    dwg.add(dwg.rect(insert=(0, 0), size=(PAGE_W, HALF_PAGE_H), fill="white"))

    if full_course_svg:
        dwg.add(dwg.image(
            href="data:image/svg+xml," + full_course_svg.replace("#", "%23"),
            insert=(MARGIN, MARGIN),
            size=(PRINTABLE_W, HALF_PAGE_H - 3 * MARGIN),
        ))

    dwg.add(dwg.text(
        "PinSheet",
        insert=(PAGE_W / 2, HALF_PAGE_H - MARGIN - 20),
        font_size="18pt",
        font_family="JetBrainsMono, monospace",
        fill="#212121",
        text_anchor="middle",
    ))

    return dwg.tostring()


def compose_chart_page(
    title: str = "Club Distances",
) -> str:
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{HALF_PAGE_H}pt"),
        viewBox=f"0 0 {PAGE_W} {HALF_PAGE_H}",
    )

    dwg.add(dwg.rect(insert=(0, 0), size=(PAGE_W, HALF_PAGE_H), fill="white"))

    dwg.add(dwg.text(
        title,
        insert=(PAGE_W / 2, MARGIN + 35),
        font_size="14pt",
        font_weight="bold",
        font_family="JetBrainsMono, monospace",
        fill="#212121",
        text_anchor="middle",
    ))

    cols = 4
    rows = 15
    headers = ["Club", "Carry", "Total", "Notes"]
    grid_top = MARGIN + 55
    grid_bottom = HALF_PAGE_H - MARGIN
    grid_left = MARGIN
    grid_right = PAGE_W - MARGIN
    gw = grid_right - grid_left
    gh = grid_bottom - grid_top
    cw = gw / cols
    rh = gh / rows

    for row in range(rows):
        for col in range(cols):
            x = grid_left + col * cw
            y = grid_top + row * rh
            dwg.add(dwg.rect(
                insert=(x, y),
                size=(cw, rh),
                fill="white",
                stroke="#ccc",
                stroke_width=0.5,
            ))
            if row == 0:
                dwg.add(dwg.text(
                    headers[col],
                    insert=(x + cw / 2, y + rh / 2 + 4),
                    font_size="11pt",
                    font_family="JetBrainsMono, monospace",
                    fill="#555",
                    text_anchor="middle",
                ))

    return dwg.tostring()


def compose_notes_page() -> str:
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{HALF_PAGE_H}pt"),
        viewBox=f"0 0 {PAGE_W} {HALF_PAGE_H}",
    )

    dwg.add(dwg.rect(insert=(0, 0), size=(PAGE_W, HALF_PAGE_H), fill="white"))

    line_spacing = 18.0
    margin_x = 12.0
    line_y = MARGIN + margin_x
    while line_y < HALF_PAGE_H - MARGIN - 6:
        dwg.add(dwg.line(
            start=(MARGIN + margin_x, line_y),
            end=(PAGE_W - MARGIN - margin_x, line_y),
            stroke="#ddd",
            stroke_width=0.5,
        ))
        line_y += line_spacing

    return dwg.tostring()


def compose_stacked_page(top_svg: str, bottom_svg: str) -> str:
    """Stack two 7" SVG pages into one 14" page."""
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{PAGE_H}pt"),
        viewBox=f"0 0 {PAGE_W} {PAGE_H}",
    )

    dwg.add(dwg.rect(insert=(0, 0), size=(PAGE_W, PAGE_H), fill="white"))

    dwg.add(dwg.image(
        href="data:image/svg+xml," + top_svg.replace("#", "%23"),
        insert=(0, 0),
        size=(PAGE_W, HALF_PAGE_H),
    ))

    dwg.add(dwg.image(
        href="data:image/svg+xml," + bottom_svg.replace("#", "%23"),
        insert=(0, HALF_PAGE_H),
        size=(PAGE_W, HALF_PAGE_H),
    ))

    return dwg.tostring()


def compose_hole_top_page(
    hole_svg: str,
    hole_num: int,
    par: int,
    tee_yardages: dict,
) -> str:
    """7" SVG: hole diagram with hole number, par, and tee yardages."""
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{HALF_PAGE_H}pt"),
        viewBox=f"0 0 {PAGE_W} {HALF_PAGE_H}",
    )

    dwg.add(dwg.rect(insert=(0, 0), size=(PAGE_W, HALF_PAGE_H), fill="white"))

    dwg.add(dwg.image(
        href="data:image/svg+xml," + hole_svg.replace("#", "%23"),
        insert=(MARGIN, MARGIN),
        size=(PRINTABLE_W, HALF_PAGE_H - 2 * MARGIN),
    ))

    inset = 9.0
    circle_cx = PAGE_W - MARGIN - inset
    circle_cy = MARGIN + inset

    dwg.add(dwg.circle(
        center=(circle_cx, circle_cy),
        r=HOLE_NUMBER_CIRCLE_RADIUS,
        fill="white",
        stroke="#000000",
        stroke_width=1.0,
    ))
    dwg.add(dwg.text(
        str(hole_num),
        insert=(circle_cx, circle_cy + 8),
        font_size="24pt",
        font_family="JetBrainsMono, monospace",
        fill="#212121",
        text_anchor="middle",
    ))

    par_y = circle_cy + HOLE_NUMBER_CIRCLE_RADIUS + 14
    dwg.add(dwg.text(
        f"Par {par}",
        insert=(circle_cx, par_y),
        font_size="9pt",
        font_family="JetBrainsMono, monospace",
        fill="#555",
        text_anchor="middle",
    ))

    sorted_tees = sorted(
        [(name, tee_yardages[name]) for name in TEE_DISPLAY_ORDER if name in tee_yardages],
        key=lambda x: x[1]
    )

    y_tee = MARGIN + HALF_PAGE_H - 2 * MARGIN - 15 - (len(sorted_tees) * 13)
    for tee_name, yardage in sorted_tees:
        col = TEE_COLOUR_MAP.get(tee_name, "#333")
        dwg.add(dwg.text(
            f"{tee_name.upper()} : {yardage}",
            insert=(PAGE_W - MARGIN - 10, y_tee),
            font_size="9pt",
            font_family="JetBrainsMono, monospace",
            fill=col,
            text_anchor="end",
        ))
        y_tee += 13.0

    return dwg.tostring()


def compose_hole_bottom_page(
    hole_num: int,
    slot1_content: str,
    slot2_content: str,
    slot1_svg: str = "",
    slot2_svg: str = "",
    stats_data: dict | None = None,
) -> str:
    """7" SVG: slot content for a single hole."""
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{HALF_PAGE_H}pt"),
        viewBox=f"0 0 {PAGE_W} {HALF_PAGE_H}",
    )

    dwg.add(dwg.rect(insert=(0, 0), size=(PAGE_W, HALF_PAGE_H), fill="white"))

    slot_height = (HALF_PAGE_H - 2 * MARGIN) / 2
    slot1_y = MARGIN
    slot2_y = MARGIN + slot_height

    _render_slot(dwg, slot1_content, slot1_svg, stats_data, hole_num,
                 MARGIN, slot1_y, PRINTABLE_W, slot_height)
    _render_slot(dwg, slot2_content, slot2_svg, stats_data, hole_num,
                 MARGIN, slot2_y, PRINTABLE_W, slot_height)

    return dwg.tostring()
