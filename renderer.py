# plugins/cartographer/renderer.py
"""SVG diagram generation for Cartographer.

Takes fitted hole geometry (pixel coordinates) and produces SVG strings
for hole layout diagrams and green detail views.
"""
from __future__ import annotations

import svgwrite

from cartographer.data import load_courses_geo
from cartographer.geometry import project_course, fit_hole, smooth_hole_geometry, chaikin_smooth

# Feature render colours — (stroke, fill)
_COLOURS = {
    "rough_boundary": ("#000000", "#a8d1de"),
    "fairway":        ("#000000", "#ccebb0"),
    "water":          ("#000000", "#a8d1de"),
    "bunkers":        ("#000000", "#f5e8c5"),
    "green":          ("#000000", "#87debd"),
}

_STROKE_WIDTH = 0.644586

# Hole layout canvas size (SVG user units = points at 72dpi, 4.25" wide)
HOLE_CANVAS_W = 306.0   # 4.25 * 72
HOLE_CANVAS_H = 504.0   # 7" for hole diagram section


def _draw_polygons(
    dwg: svgwrite.Drawing,
    group: svgwrite.container.Group,
    rings: list[list],
    stroke: str,
    fill: str,
    stroke_width: float | None = None,
) -> None:
    """Draw a list of polygon rings onto a svgwrite group."""
    if stroke_width is None:
        stroke_width = _STROKE_WIDTH
    for ring in rings:
        if len(ring) < 3:
            continue
        points = [(float(x), float(y)) for x, y in ring]
        group.add(dwg.polygon(
            points=points,
            stroke=stroke,
            fill=fill,
            stroke_width=stroke_width,
            fill_rule="evenodd",
        ))


def render_hole(
    hole_geom: dict,
    settings: dict | None = None,
    canvas_w: float = HOLE_CANVAS_W,
    canvas_h: float = HOLE_CANVAS_H,
) -> str:
    """Render a fitted hole geometry dict to an SVG string.

    hole_geom: output of geometry.fit_hole() — pixel coordinates.
    settings: plugin settings dict; uses 'cartographer.yardage_arcs' and
              'cartographer.yardage_arc_distances' keys.
    """
    if settings is None:
        settings = {}

    dwg = svgwrite.Drawing(size=(f"{canvas_w}pt", f"{canvas_h}pt"),
                           viewBox=f"0 0 {canvas_w} {canvas_h}")

    # Render order: rough → fairway → water → bunkers → green → tees → arcs
    for feature_type in ("rough_boundary", "fairway", "water", "bunkers", "green"):
        stroke_col, fill_col = _COLOURS[feature_type]
        rings = hole_geom.get(feature_type, [])
        g = dwg.g()
        _draw_polygons(dwg, g, rings, stroke=stroke_col, fill=fill_col)
        dwg.add(g)

    # Tee box markers — same fill/stroke as rough/water
    for tee_name, (tx, ty) in hole_geom.get("tee_boxes", {}).items():
        dwg.add(dwg.circle(
            center=(float(tx), float(ty)),
            r=4,
            fill=_COLOURS["rough_boundary"][1],
            stroke=_COLOURS["rough_boundary"][0],
            stroke_width=_STROKE_WIDTH,
        ))

    # Yardage arcs
    if settings.get("cartographer.yardage_arcs", True):
        arcs = hole_geom.get("_arcs", [])
        for cx, cy, r in arcs:
            dwg.add(dwg.circle(
                center=(float(cx), float(cy)),
                r=float(r),
                fill="none",
                stroke="#000000",
                stroke_width=0.25,
                stroke_dasharray="3,3",
            ))
        if arcs:
            cx, cy = arcs[0][0], arcs[0][1]
            dwg.add(dwg.circle(
                center=(float(cx), float(cy)),
                r=1.5,
                fill="#000000",
                stroke="none",
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

    # Fit the green into the canvas
    fitted, _, _, _ = fit_hole(
        {"green": green_geom.get("green", []),
         "fairway": [], "bunkers": [], "water": [], "rough_boundary": [], "tee_boxes": {}},
        canvas_size, canvas_size, padding=15.0,
    )
    fitted["green"] = [chaikin_smooth(r) for r in fitted.get("green", [])]

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
    hole_geom = smooth_hole_geometry(hole_geom)

    fitted, _, _, scale = fit_hole(hole_geom, HOLE_CANVAS_W, HOLE_CANVAS_H)

    # Attach arc data to fitted geom using pixels_per_yard from scale_data.
    # ppy is in raw projected-pixel space; scale is fit_hole's shrink factor.
    ppy = float(scale_data.get("pixels_per_yard", 1.0))
    if settings is None:
        settings = {}
    if settings.get("cartographer.yardage_arcs", True):
        distances = settings.get("cartographer.yardage_arc_distances", [100, 125, 150])
        green_rings = fitted.get("green", [])
        if green_rings:
            all_pts = [pt for ring in green_rings for pt in ring]
            if all_pts:
                gcx = sum(p[0] for p in all_pts) / len(all_pts)
                gcy = sum(p[1] for p in all_pts) / len(all_pts)
                fitted["_arcs"] = [(gcx, gcy, d * ppy * scale) for d in distances]

    return render_hole(fitted, settings=settings)


def svg_to_png(svg: str, target_w: int, target_h: int) -> bytes:
    """Convert SVG string to PNG bytes, scaled to fill terminal dimensions
    while preserving the content's natural aspect ratio."""
    import io, cairosvg
    from PIL import Image

    png_bytes = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=2000)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        m = 40
        bbox = (max(0, bbox[0] - m), max(0, bbox[1] - m),
                min(img.width, bbox[2] + m), min(img.height, bbox[3] + m))
        img = img.crop(bbox)

    img_w, img_h = img.size
    if img_w < 1 or img_h < 1:
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()

    img_aspect = img_w / img_h
    target_aspect = target_w / target_h

    if img_aspect > target_aspect:
        # Image is wider than terminal — fit to target width
        final_w = target_w
        final_h = max(1, int(target_w / img_aspect))
    else:
        # Image is taller than terminal — fit to target height
        final_h = target_h
        final_w = max(1, int(target_h * img_aspect))

    img = img.resize((final_w, final_h), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()
