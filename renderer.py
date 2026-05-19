# plugins/cartographer/renderer.py
"""SVG diagram generation for Cartographer.

Takes fitted hole geometry (pixel coordinates) and produces SVG strings
for hole layout diagrams and green detail views.
"""
from __future__ import annotations

import svgwrite

from cartographer.data import load_courses_geo
from cartographer.geometry import project_course, fit_hole, get_green_centroid

# Feature render colours
_COLOURS = {
    "rough_boundary": ("#228B22", "#E8F5E9"),  # (stroke, fill)
    "fairway":        ("#4CAF50", "#90EE90"),
    "water":          ("#1565C0", "#87CEEB"),
    "bunkers":        ("#8D6E63", "#F5DEB3"),
    "green":          ("#00796B", "#48D1CC"),
}

# Hole layout canvas size (SVG user units = points at 72dpi, 4.25" wide)
HOLE_CANVAS_W = 306.0   # 4.25 * 72
HOLE_CANVAS_H = 504.0   # 7" for hole diagram section


def _draw_polygons(
    dwg: svgwrite.Drawing,
    group: svgwrite.container.Group,
    rings: list[list],
    stroke: str,
    fill: str,
    stroke_width: float = 0.5,
) -> None:
    """Draw a list of polygon rings onto a svgwrite group."""
    for ring in rings:
        if len(ring) < 3:
            continue
        points = [(float(x), float(y)) for x, y in ring]
        group.add(dwg.polygon(
            points=points,
            stroke=stroke,
            fill=fill,
            stroke_width=stroke_width,
        ))


def render_hole(
    hole_geom: dict,
    tee_yardages: dict | None = None,
    settings: dict | None = None,
    canvas_w: float = HOLE_CANVAS_W,
    canvas_h: float = HOLE_CANVAS_H,
) -> str:
    """Render a fitted hole geometry dict to an SVG string.

    hole_geom: output of geometry.fit_hole() — pixel coordinates.
    tee_yardages: dict of {tee_name: yardage} e.g. {"blue": 377, "white": 362}
    settings: plugin settings dict; uses 'cartographer.yardage_arcs' and
              'cartographer.yardage_arc_distances' keys.
    """
    if settings is None:
        settings = {}
    if tee_yardages is None:
        tee_yardages = {}

    dwg = svgwrite.Drawing(size=(f"{canvas_w}pt", f"{canvas_h}pt"),
                           viewBox=f"0 0 {canvas_w} {canvas_h}")

    # Background
    dwg.add(dwg.rect(insert=(0, 0), size=(canvas_w, canvas_h), fill="white"))

    # Render order: rough → fairway → water → bunkers → green → tees → arcs
    for feature_type in ("rough_boundary", "fairway", "water", "bunkers", "green"):
        stroke_col, fill_col = _COLOURS.get(feature_type, ("#000", "#fff"))
        rings = hole_geom.get(feature_type, [])
        g = dwg.g()
        _draw_polygons(dwg, g, rings, stroke=stroke_col, fill=fill_col)
        dwg.add(g)

    # Tee box markers (small circles)
    tee_colours = {
        "blue": "#1565C0", "white": "#F5F5F5", "red": "#C62828",
        "gold": "#F9A825", "black": "#212121", "green": "#2E7D32",
    }
    for tee_name, (tx, ty) in hole_geom.get("tee_boxes", {}).items():
        colour = tee_colours.get(tee_name.lower(), "#888")
        dwg.add(dwg.circle(
            center=(float(tx), float(ty)),
            r=4,
            fill=colour,
            stroke="#000",
            stroke_width=0.5,
        ))

    # Yardage arcs
    if settings.get("cartographer.yardage_arcs", True):
        for arc_data in hole_geom.get("_arcs", []):
            cx, cy, r = arc_data
            dwg.add(dwg.circle(
                center=(float(cx), float(cy)),
                r=float(r),
                fill="none",
                stroke="#666",
                stroke_width=0.25,
                stroke_dasharray="3,3",
            ))

    return dwg.tostring()


def render_green(green_geom: dict, canvas_size: float = 200.0) -> str:
    """Render a green detail SVG with a grid overlay.

    green_geom: a hole geometry dict (only 'green' key is used).
    canvas_size: the width and height of the square SVG canvas in points.
    """
    dwg = svgwrite.Drawing(
        size=(f"{canvas_size}pt", f"{canvas_size}pt"),
        viewBox=f"0 0 {canvas_size} {canvas_size}",
    )
    dwg.add(dwg.rect(insert=(0, 0), size=(canvas_size, canvas_size), fill="white"))

    # Fit the green into the canvas
    fitted, _, _ = fit_hole(
        {"green": green_geom.get("green", []),
         "fairway": [], "bunkers": [], "water": [], "rough_boundary": [], "tee_boxes": {}},
        canvas_size, canvas_size, padding=15.0,
    )

    stroke_col, fill_col = _COLOURS["green"]
    g = dwg.g()
    _draw_polygons(dwg, g, fitted.get("green", []), stroke=stroke_col, fill=fill_col)
    dwg.add(g)

    # Grid overlay
    grid_step = canvas_size / 6
    for i in range(1, 6):
        dwg.add(dwg.line(
            start=(i * grid_step, 0), end=(i * grid_step, canvas_size),
            stroke="#ccc", stroke_width=0.3,
        ))
        dwg.add(dwg.line(
            start=(0, i * grid_step), end=(canvas_size, i * grid_step),
            stroke="#ccc", stroke_width=0.3,
        ))

    return dwg.tostring()


def render_hole_svg(course_name: str, hole_number: int, settings: dict | None = None) -> str:
    """Public convenience function for PinSheet screens.

    Loads courses_geo.json, projects and fits the specified hole,
    and returns an SVG string. Returns an empty string if geometry
    is not available for the course.
    """
    courses_geo = load_courses_geo()
    course_data = courses_geo.get(course_name)
    if not course_data:
        return ""

    holes = course_data.get("holes", {})
    scale_data = course_data.get("scale", {})
    hole_key = str(hole_number)

    if hole_key not in holes:
        return ""

    projected = project_course(holes, scale_data)
    hole_geom = projected.get(hole_key, {})

    fitted, _, _ = fit_hole(hole_geom, HOLE_CANVAS_W, HOLE_CANVAS_H)

    # Attach arc data to fitted geom using pixels_per_yard from scale_data
    ppy = float(scale_data.get("pixels_per_yard", 1.0))
    if settings is None:
        settings = {}
    if settings.get("cartographer.yardage_arcs", True):
        distances = settings.get("cartographer.yardage_arc_distances", [100, 125, 150, 175, 200])
        green_rings = fitted.get("green", [])
        if green_rings:
            all_pts = [pt for ring in green_rings for pt in ring]
            if all_pts:
                gcx = sum(p[0] for p in all_pts) / len(all_pts)
                gcy = sum(p[1] for p in all_pts) / len(all_pts)
                fitted["_arcs"] = [(gcx, gcy, d * ppy) for d in distances]

    return render_hole(fitted, settings=settings)
