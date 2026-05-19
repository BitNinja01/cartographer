# plugins/cartographer/pdf.py
"""PDF export for Cartographer yardage books.

Generates 20 narrow PDFs (4.25" x 14") and combines them into
5 saddle-stitch booklet PDFs (8.5" x 14") using pypdf.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import cairosvg
from pypdf import PdfWriter, PdfReader

from cartographer.data import load_courses_geo
from cartographer.geometry import project_course, fit_hole
from cartographer.renderer import render_hole, render_green
from cartographer.layout import compose_page, CROSS_PAIRS, PAGE_W, HOLE_H, GREEN_H


def _svg_to_pdf_bytes(svg_string: str) -> bytes:
    """Convert an SVG string to PDF bytes via cairosvg."""
    return cairosvg.svg2pdf(bytestring=svg_string.encode("utf-8"))


def generate_book(
    course_name: str,
    output_dir: Path,
    settings: dict | None = None,
) -> None:
    """Generate a complete yardage book for a course.

    course_name: must match a key in courses_geo.json and courses.json.
    output_dir: directory where booklet PDFs will be written.
    settings: plugin settings dict.
    """
    if settings is None:
        settings = {}

    # Load geometry
    courses_geo = load_courses_geo()
    course_geo = courses_geo.get(course_name)
    if not course_geo:
        raise ValueError(f"No geometry found for course '{course_name}'. Run: python -m cartographer.tagger \"{course_name}\"")

    # Load course data from PinSheet's courses.json for tee yardages
    if getattr(sys, "frozen", False):
        courses_json = Path(sys.executable).parent / "data" / "courses.json"
    else:
        courses_json = Path(__file__).parent.parent.parent / "data" / "courses.json"

    import json
    pinsheet_courses = json.loads(courses_json.read_text()) if courses_json.exists() else {}
    course_ps = pinsheet_courses.get(course_name, {})

    holes_geo = course_geo.get("holes", {})
    scale_data = course_geo.get("scale", {})
    projected = project_course(holes_geo, scale_data)

    # Generate SVG for each hole (layout + green)
    hole_svgs: dict[int, str] = {}
    green_svgs: dict[int, str] = {}

    for hole_num in range(1, 19):
        hole_key = str(hole_num)
        hole_geom = projected.get(hole_key, {})

        # Get tee yardages for this hole
        hole_ps_data = course_ps.get("holes", {}).get(hole_key, {})
        tee_yardages = {
            t: int(y) for t, y in hole_ps_data.get("tees", {}).items()
        }

        # Fit and render
        fitted, _, _ = fit_hole(hole_geom, PAGE_W, HOLE_H)

        # Attach arcs
        ppy = float(scale_data.get("pixels_per_yard", 1.0))
        if settings.get("cartographer.yardage_arcs", True):
            distances = settings.get("cartographer.yardage_arc_distances", [100, 125, 150, 175, 200])
            green_rings = fitted.get("green", [])
            if green_rings:
                all_pts = [pt for ring in green_rings for pt in ring]
                if all_pts:
                    gcx = sum(p[0] for p in all_pts) / len(all_pts)
                    gcy = sum(p[1] for p in all_pts) / len(all_pts)
                    fitted["_arcs"] = [(gcx, gcy, d * ppy) for d in distances]

        par = int(hole_ps_data.get("par", 4))
        hole_svgs[hole_num] = render_hole(fitted, settings=settings)

        green_fitted, _, _ = fit_hole(hole_geom, GREEN_H, GREEN_H, padding=10.0)
        green_svgs[hole_num] = render_green({"green": green_fitted.get("green", [])})

    # Compose and export 20 narrow PDFs
    output_dir.mkdir(parents=True, exist_ok=True)
    narrow_pdfs: list[bytes] = []

    for page_idx, (layout_hole, green_hole) in enumerate(CROSS_PAIRS, start=1):
        if layout_hole == 0 or layout_hole not in hole_svgs:
            import svgwrite
            dwg = svgwrite.Drawing(size=("306pt", "1008pt"), viewBox="0 0 306 1008")
            dwg.add(dwg.rect(insert=(0, 0), size=(306, 1008), fill="white"))
            svg = dwg.tostring()
        else:
            hole_ps_data = course_ps.get("holes", {}).get(str(layout_hole), {})
            tee_yardages = {t: int(y) for t, y in hole_ps_data.get("tees", {}).items()}
            par = int(hole_ps_data.get("par", 4))
            green_h = green_hole if green_hole in green_svgs else layout_hole
            svg = compose_page(
                hole_svg=hole_svgs[layout_hole],
                green_svg=green_svgs.get(green_h, green_svgs.get(layout_hole, "")),
                hole_num=layout_hole,
                par=par,
                tee_yardages=tee_yardages,
            )

        pdf_bytes = _svg_to_pdf_bytes(svg)
        narrow_pdfs.append(pdf_bytes)
        narrow_path = output_dir / f"yardage_book_{page_idx:02d}.pdf"
        narrow_path.write_bytes(pdf_bytes)

    # Combine into 5 saddle-stitch booklets (pairs of narrow pages side by side)
    booklet_pairs = [
        (0, 1), (2, 3), (4, 5), (6, 7), (8, 9),
        (10, 11), (12, 13), (14, 15), (16, 17), (18, 19),
    ]
    for booklet_idx, (left_idx, right_idx) in enumerate(booklet_pairs, start=1):
        writer = PdfWriter()
        left_reader = PdfReader(io.BytesIO(narrow_pdfs[left_idx]))
        right_reader = PdfReader(io.BytesIO(narrow_pdfs[right_idx]))
        writer.add_page(left_reader.pages[0])
        writer.add_page(right_reader.pages[0])
        booklet_path = output_dir / f"yardage_book_booklet_{booklet_idx:02d}.pdf"
        with open(booklet_path, "wb") as f:
            writer.write(f)

    print(f"Yardage book generated: {output_dir}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate a PinSheet yardage book PDF")
    parser.add_argument("course_name", help="Course name (must match courses.json)")
    parser.add_argument("--output", default=".", help="Output directory")
    args = parser.parse_args()
    generate_book(args.course_name, Path(args.output).expanduser())
