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
PAGE_CONTENT_H = PAGE_H / 2 - MARGIN  # 486pt — single page content height within a sheet
SLOT_H = 243.0       # half of bottom half

# Hole number circle (adjustable)
HOLE_NUMBER_CIRCLE_RADIUS = 16.0  # Experiment with this value

TEE_DISPLAY_ORDER = ["red", "gold", "white", "blue", "black", "green"]
TEE_COLOUR_MAP = {
    "blue": "#1565C0", "white": "#555", "red": "#C62828",
    "gold": "#F9A825", "black": "#212121", "green": "#2E7D32",
}

_CORNER_ARM = 8.0  # length of each chevron arm in points


def _text_width(text: str, font_size: int) -> float:
    """Estimate rendered width of text in points for JetBrainsMono at font_size."""
    return len(text) * font_size * 0.65


def _wrap_text(text: str, font_size: int, max_width: float) -> list[str]:
    """Split text into lines that each fit within max_width at the given font size.

    Uses a conservative character-width estimate (0.65 × font_size for
    JetBrainsMono) rather than font-file measurement, to match SVG rendering.
    """
    char_w = font_size * 0.65
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        test = " ".join(current + [word])
        if len(test) * char_w <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines if lines else [text]


def _draw_corner_marks(
    dwg: svgwrite.Drawing,
    x: float,
    y: float,
    w: float,
    h: float,
    arm: float | None = None,
) -> None:
    """Draw L-shaped corner marks at the four corners of a rectangle."""
    if arm is None:
        arm = _CORNER_ARM
    s = {"stroke": "#000000", "stroke_width": 0.5, "stroke_linecap": "square"}
    # top-left
    dwg.add(dwg.line(start=(x, y), end=(x + arm, y), **s))
    dwg.add(dwg.line(start=(x, y), end=(x, y + arm), **s))
    # top-right
    dwg.add(dwg.line(start=(x + w, y), end=(x + w - arm, y), **s))
    dwg.add(dwg.line(start=(x + w, y), end=(x + w, y + arm), **s))
    # bottom-left
    dwg.add(dwg.line(start=(x, y + h), end=(x + arm, y + h), **s))
    dwg.add(dwg.line(start=(x, y + h), end=(x, y + h - arm), **s))
    # bottom-right
    dwg.add(dwg.line(start=(x + w, y + h), end=(x + w - arm, y + h), **s))
    dwg.add(dwg.line(start=(x + w, y + h), end=(x + w, y + h - arm), **s))


def flip_page_svg(svg_str: str, w: float, h: float) -> str:
    """Return a new SVG that displays svg_str rotated 180° around its centre."""
    dwg = svgwrite.Drawing(size=(f"{w}pt", f"{h}pt"), viewBox=f"0 0 {w} {h}")
    g = dwg.g(transform=f"rotate(180, {w / 2}, {h / 2})")
    g.add(dwg.image(
        href="data:image/svg+xml," + svg_str.replace("#", "%23"),
        insert=(0, 0),
        size=(w, h),
    ))
    dwg.add(g)
    return dwg.tostring()


def compose_sheet(top_svg: str, bottom_svg: str) -> str:
    """Combine two PAGE_CONTENT_H SVGs into one PAGE_H sheet with corner marks."""
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{PAGE_H}pt"),
        viewBox=f"0 0 {PAGE_W} {PAGE_H}",
    )

    dwg.add(dwg.rect(insert=(0, 0), size=(PAGE_W, PAGE_H), fill="white"))

    dwg.add(dwg.image(
        href="data:image/svg+xml," + top_svg.replace("#", "%23"),
        insert=(0, MARGIN),
        size=(PAGE_W, PAGE_CONTENT_H),
    ))

    dwg.add(dwg.image(
        href="data:image/svg+xml," + bottom_svg.replace("#", "%23"),
        insert=(0, PAGE_H / 2),
        size=(PAGE_W, PAGE_CONTENT_H),
    ))

    _draw_corner_marks(dwg, MARGIN, MARGIN, PRINTABLE_W, PAGE_CONTENT_H)
    _draw_corner_marks(dwg, MARGIN, PAGE_H / 2, PRINTABLE_W, PAGE_CONTENT_H)

    return dwg.tostring()


def render_hole_page(
    hole_svg: str,
    hole_num: int,
    par: int,
    tee_yardages: dict,
) -> str:
    """Content-only PAGE_CONTENT_H SVG: hole layout with overlays."""
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{PAGE_CONTENT_H}pt"),
        viewBox=f"0 0 {PAGE_W} {PAGE_CONTENT_H}",
    )

    dwg.add(dwg.image(
        href="data:image/svg+xml," + hole_svg.replace("#", "%23"),
        insert=(MARGIN, 0),
        size=(PRINTABLE_W, PAGE_CONTENT_H),
    ))

    # --- Block 1: Hole number / Par (top-right corner) ---
    # Content dimensions
    par_label = f"Par {par}"
    hn_content_w = max(2 * HOLE_NUMBER_CIRCLE_RADIUS, _text_width(par_label, 9))
    hn_content_h = 2 * HOLE_NUMBER_CIRCLE_RADIUS + 6 + 9  # circle + gap + par ascender

    # Rect: anchored to printable top-right corner
    hn_rect_w = hn_content_w + 2 * MARGIN
    hn_rect_h = hn_content_h + 2 * MARGIN
    hn_rect_x = PAGE_W - MARGIN - hn_rect_w
    hn_rect_y = MARGIN

    dwg.add(dwg.rect(
        insert=(hn_rect_x, hn_rect_y),
        size=(hn_rect_w, hn_rect_h),
        fill="white",
        stroke="none",
        rx=4, ry=4,
    ))

    # Circle: centred horizontally, MARGIN from rect top
    hn_cx = hn_rect_x + hn_rect_w / 2
    hn_cy = hn_rect_y + MARGIN + HOLE_NUMBER_CIRCLE_RADIUS
    dwg.add(dwg.circle(
        center=(hn_cx, hn_cy),
        r=HOLE_NUMBER_CIRCLE_RADIUS,
        fill="white",
        stroke="#000000",
        stroke_width=1.0,
    ))
    dwg.add(dwg.text(
        str(hole_num),
        insert=(hn_cx, hn_cy),
        font_size="14pt",
        font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
        fill="#212121",
        text_anchor="middle",
        dominant_baseline="central",
    ))

    # Par text: 6pt gap below circle bottom, 9pt ascender
    par_y = hn_cy + HOLE_NUMBER_CIRCLE_RADIUS + 6 + 9
    dwg.add(dwg.text(
        par_label,
        insert=(hn_cx, par_y),
        font_size="9pt",
        font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
        fill="#212121",
        text_anchor="middle",
    ))

    sorted_tees = sorted(
        [(name, tee_yardages[name]) for name in TEE_DISPLAY_ORDER if name in tee_yardages],
        key=lambda x: x[1]
    )

    if sorted_tees:
        # Content dimensions
        line_h = 16.0
        n = len(sorted_tees)
        line_texts = [f"{tee_name.upper()} : {yardage}" for tee_name, yardage in sorted_tees]
        yd_content_w = max(_text_width(t, 12) for t in line_texts)
        yd_content_h = (n - 1) * line_h + 12  # baseline span + 12pt descender allowance

        # Rect: anchored to printable bottom-right corner
        yd_rect_w = yd_content_w + 2 * MARGIN
        yd_rect_h = yd_content_h + 2 * MARGIN
        yd_rect_x = PAGE_W - MARGIN - yd_rect_w
        yd_rect_y = PAGE_CONTENT_H - MARGIN - yd_rect_h

        dwg.add(dwg.rect(
            insert=(yd_rect_x, yd_rect_y),
            size=(yd_rect_w, yd_rect_h),
            fill="white",
            stroke="none",
            rx=4, ry=4,
        ))

        # Text: right-aligned, first baseline MARGIN + 12pt ascender from rect top
        yd_text_right = yd_rect_x + yd_rect_w - MARGIN
        y_tee = yd_rect_y + MARGIN + 12
        for tee_name, yardage in sorted_tees:
            dwg.add(dwg.text(
                f"{tee_name.upper()} : {yardage}",
                insert=(yd_text_right, y_tee),
                font_size="12pt",
                font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
                fill="#000000",
                text_anchor="end",
            ))
            y_tee += line_h

    return dwg.tostring()


def render_bottom_slots(
    slot1_content: str,
    slot2_content: str,
    slot1_svg: str = "",
    slot2_svg: str = "",
    stats_data: dict | None = None,
    hole_num: int = 1,
) -> str:
    """Content-only PAGE_CONTENT_H SVG: two stacked slots with no gap."""
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{PAGE_CONTENT_H}pt"),
        viewBox=f"0 0 {PAGE_W} {PAGE_CONTENT_H}",
    )

    slot_h = PAGE_CONTENT_H / 2

    _render_slot(dwg, slot1_content, slot1_svg, stats_data, hole_num,
                 MARGIN, 0, PRINTABLE_W, slot_h)
    _render_slot(dwg, slot2_content, slot2_svg, stats_data, hole_num,
                 MARGIN, slot_h, PRINTABLE_W, slot_h)

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
                font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
                fill="#555",
                text_anchor="middle",
            ))

            # Value (centered)
            dwg.add(dwg.text(
                value,
                insert=(bx + box_w / 2, by + box_h / 2 + 5),
                font_size="11pt",
                font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
                fill="#212121",
                text_anchor="middle",
            ))

    elif content_type == "notes":
        # Ruled lines
        line_spacing = 24.0
        line_y = y + line_spacing
        while line_y < y + height - 6:
            dwg.add(dwg.line(
                start=(x, line_y),
                end=(x + width, line_y),
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
    # --- Compute phase ---
    title_max_w = PRINTABLE_W - 88
    title_lines = _wrap_text(course_name, 18, title_max_w)
    title_line_h = 26.0

    loc_str1 = ""
    loc_str2 = ""
    if location:
        city = location.get("city", "")
        state = location.get("state") or location.get("state/province", "")
        country = location.get("country", "")
        line1_parts = [p for p in [city, state] if p]
        if line1_parts:
            loc_str1 = ", ".join(line1_parts)
        if country:
            loc_str2 = country
    has_loc = bool(loc_str1 or loc_str2)

    sorted_tees: list[tuple[str, int]] = []
    if tee_totals:
        sorted_tees = sorted(
            [(n, tee_totals[n]) for n in TEE_DISPLAY_ORDER if n in tee_totals],
            key=lambda x: x[1],
        )

    # Bounding-box heights (ascender above first baseline + descender below last baseline)
    _ASC = lambda fs: fs       # ascender: font_size above baseline
    _DSC = lambda fs: fs * 0.25  # descender: 0.25 × font_size below baseline
    title_h = _ASC(18) + (len(title_lines) - 1) * title_line_h + _DSC(18)
    if has_loc:
        if loc_str2:
            loc_h = _ASC(11) + 16 + _DSC(10)  # two lines: asc1 + offset + desc2
        else:
            loc_h = _ASC(11) + _DSC(11)       # one line
    else:
        loc_h = 0
    par_h = _ASC(14) + _DSC(14)
    n_tees = len(sorted_tees)
    tee_h = (_ASC(11) + (n_tees - 1) * 18 + _DSC(11)) if n_tees else 0

    # Fixed gap between sections, block centred vertically
    gap = 36.0
    total_block_h = title_h + loc_h + par_h + tee_h + 3 * gap
    title_top = (PAGE_CONTENT_H - total_block_h) / 2
    loc_top = title_top + title_h + gap
    par_top = loc_top + loc_h + gap
    tee_top = par_top + par_h + gap

    # Text baselines from bbox tops
    name_y = title_top + _ASC(18)
    title_bottom = name_y + (len(title_lines) - 1) * title_line_h

    loc_offset = loc_top + _ASC(11)
    if loc_str2:
        loc2_y = loc_offset + 16 if loc_str1 else loc_offset
        loc_bottom = loc2_y + _DSC(10)
    elif loc_str1:
        loc_bottom = loc_offset + _DSC(11)
    else:
        loc_bottom = title_bottom + _DSC(18)

    par_y = par_top + _ASC(14)

    table_y = tee_top + _ASC(11) if n_tees else par_y

    # --- Draw phase ---
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{PAGE_CONTENT_H}pt"),
        viewBox=f"0 0 {PAGE_W} {PAGE_CONTENT_H}",
    )

    for i, line in enumerate(title_lines):
        dwg.add(dwg.text(
            line,
            insert=(PAGE_W / 2, name_y + i * title_line_h),
            font_size="18pt",
            font_weight="bold",
            font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
            fill="#212121",
            text_anchor="middle",
        ))

    if loc_str1:
        dwg.add(dwg.text(
            loc_str1,
            insert=(PAGE_W / 2, loc_offset),
            font_size="11pt",
            font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
            fill="#555",
            text_anchor="middle",
        ))
    if loc_str2:
        dwg.add(dwg.text(
            loc_str2,
            insert=(PAGE_W / 2, loc2_y),
            font_size="10pt",
            font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
            fill="#555",
            text_anchor="middle",
        ))

    dwg.add(dwg.text(
        f"Par {total_par}",
        insert=(PAGE_W / 2, par_y),
        font_size="14pt",
        font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
        fill="#212121",
        text_anchor="middle",
    ))

    if sorted_tees:
        col_gap = 4.0
        name_w = max(_text_width(f"{n.upper()} :", 11) for n, _ in sorted_tees)
        yardage_w = max(_text_width(str(y), 11) for _, y in sorted_tees)
        total_w = name_w + col_gap + yardage_w
        block_left = (PAGE_W - total_w) / 2
        col_x = block_left + name_w
        y = table_y
        for tee_name, yardage in sorted_tees:
            dwg.add(dwg.text(
                f"{tee_name.upper()} :",
                insert=(col_x, y),
                font_size="11pt",
                font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
                fill="#212121",
                text_anchor="end",
            ))
            dwg.add(dwg.text(
                str(yardage),
                insert=(col_x + col_gap, y),
                font_size="11pt",
                font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
                fill="#212121",
                text_anchor="start",
            ))
            y += 18

    # 3 dots at gap midpoints
    dot_cx = PAGE_W / 2
    dots = [
        (title_top + title_h + gap / 2),
        (loc_top + loc_h + gap / 2),
        (par_top + par_h + gap / 2),
    ]
    for dot_y in dots:
        dwg.add(dwg.circle(center=(dot_cx, dot_y), r=1.5, fill="#999"))

    return dwg.tostring()


def compose_back_page(
    full_course_svg: str | None = None,
) -> str:
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{PAGE_CONTENT_H}pt"),
        viewBox=f"0 0 {PAGE_W} {PAGE_CONTENT_H}",
    )

    if full_course_svg:
        overview_h = PAGE_CONTENT_H - 4 * MARGIN - 24
        dwg.add(dwg.image(
            href="data:image/svg+xml," + full_course_svg.replace("#", "%23"),
            insert=(MARGIN, MARGIN),
            size=(PRINTABLE_W, overview_h),
        ))

    dwg.add(dwg.text(
        "PinSheet",
        insert=(PAGE_W / 2, PAGE_CONTENT_H - MARGIN - 20),
        font_size="18pt",
        font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
        fill="#212121",
        text_anchor="middle",
    ))

    return dwg.tostring()


def compose_chart_page(
    title: str = "Club Distances",
) -> str:
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{PAGE_CONTENT_H}pt"),
        viewBox=f"0 0 {PAGE_W} {PAGE_CONTENT_H}",
    )

    dwg.add(dwg.text(
        title,
        insert=(PAGE_W / 2, 35),
        font_size="14pt",
        font_weight="bold",
        font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
        fill="#212121",
        text_anchor="middle",
    ))

    cols = 4
    rows = 15
    headers = ["Club", "Carry", "Total", "Notes"]
    grid_top = 55
    grid_bottom = PAGE_CONTENT_H
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
                    font_family="JetBrainsMonoNL NFM, JetBrainsMono, monospace",
                    fill="#555",
                    text_anchor="middle",
                ))

    return dwg.tostring()


def compose_notes_page() -> str:
    dwg = svgwrite.Drawing(
        size=(f"{PAGE_W}pt", f"{PAGE_CONTENT_H}pt"),
        viewBox=f"0 0 {PAGE_W} {PAGE_CONTENT_H}",
    )

    line_spacing = 24.0
    line_y = 0
    while line_y < PAGE_CONTENT_H - 6:
        dwg.add(dwg.line(
            start=(MARGIN, line_y),
            end=(PAGE_W - MARGIN, line_y),
            stroke="#ddd",
            stroke_width=0.5,
        ))
        line_y += line_spacing

    return dwg.tostring()



