# plugins/cartographer/pdf.py
"""PDF export for Cartographer yardage books.

Generates 20 narrow PDFs (4.25" x 14") in cross-paired order and
combines them into 5 saddle-stitch booklet PDFs (8.5" x 14") using pypdf.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import cairosvg
from pypdf import PdfWriter, PdfReader, Transformation

from cartographer.data import load_courses_geo
from cartographer.geometry import (
    project_course, fit_hole, smooth_hole_geometry,
    get_green_centroid, compute_yardage_arcs,
)
from cartographer.renderer import render_hole, render_green
from cartographer.layout import (
    compose_page, compose_front_page, compose_back_page, compose_chart_page,
    compose_notes_page, compose_stacked_page, compose_hole_top_page,
    compose_hole_bottom_page, PAGE_W, SLOT_H
)

HOLE_CANVAS_W = 306.0   # 4.25 * 72
HOLE_CANVAS_H = 504.0   # 7" for hole diagram section


def _svg_to_pdf_bytes(svg_string: str) -> bytes:
    """Convert an SVG string to PDF bytes via cairosvg."""
    return cairosvg.svg2pdf(bytestring=svg_string.encode("utf-8"))


def _get_hole_render_data(
    hole_num: int,
    projected: dict,
    scale_data: dict,
    settings: dict,
    course_ps: dict,
    slot1_mode: str,
    slot2_mode: str,
) -> dict | None:
    """Render a single hole and return raw data for page composition.

    Returns dict with keys: hole_svg, par, tee_yardages, slot1_svg, slot2_svg
    or None if hole geometry is missing.
    """
    hole_key = str(hole_num)
    hole_geom = projected.get(hole_key, {})
    if not hole_geom:
        return None

    hole_geom = smooth_hole_geometry(hole_geom)
    fitted, _, _, scale = fit_hole(hole_geom, HOLE_CANVAS_W, HOLE_CANVAS_H)

    ppy = float(scale_data.get("pixels_per_yard", 1.0))
    if settings.get("cartographer.yardage_arcs", True):
        distances = settings.get("cartographer.yardage_arc_distances", [100, 125, 150])
        gcx, gcy = get_green_centroid(fitted)
        fitted["_arcs"] = compute_yardage_arcs((gcx, gcy), distances, ppy, scale)

    hole_svg = render_hole(fitted, settings=settings)

    hole_ps_data = course_ps.get("holes", {}).get(hole_key, {})
    tee_yardages = {t: int(y) for t, y in hole_ps_data.get("tees", {}).items()}
    par = int(hole_ps_data.get("par", 4))

    slot1_svg = ""
    slot2_svg = ""
    if slot1_mode == "green_grid":
        green_fitted, _, _, _ = fit_hole(hole_geom, SLOT_H, SLOT_H, padding=10.0)
        slot1_svg = render_green({"green": green_fitted.get("green", [])})
    if slot2_mode == "green_grid":
        green_fitted, _, _, _ = fit_hole(hole_geom, SLOT_H, SLOT_H, padding=10.0)
        slot2_svg = render_green({"green": green_fitted.get("green", [])})

    return {
        "hole_svg": hole_svg,
        "par": par,
        "tee_yardages": tee_yardages,
        "slot1_svg": slot1_svg,
        "slot2_svg": slot2_svg,
    }


def generate_book(
    course_name: str,
    output_dir: Path,
    slot1_mode: str = "green_grid",
    slot2_mode: str = "stats_panel",
    show_calculated_stats: bool = True,
    settings: dict | None = None,
    progress_callback: callable = None,
) -> None:
    """Generate a complete yardage book for a course.

    course_name: must match a key in courses_geo.json and courses.json.
    output_dir: directory where booklet PDFs will be written.
    slot1_mode: "green_grid", "stats_panel", or "notes"
    slot2_mode: "green_grid", "stats_panel", or "notes"
    show_calculated_stats: if False, stat boxes render as blank (labels + underlines)
    settings: plugin settings dict.
    progress_callback: optional function(current_page, total_pages) for progress updates
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

    # Compute course-level metadata for front/back pages
    total_par = 0
    tee_totals: dict[str, int] = {}
    for hk, hd in course_ps.get("holes", {}).items():
        total_par += int(hd.get("par", 4))
        for tee, yrd in hd.get("tees", {}).items():
            tee_totals[tee] = tee_totals.get(tee, 0) + int(yrd)

    # Load rounds data for stats (if needed)
    rounds_by_hole = {}
    stats_data = None
    if "stats_panel" in [slot1_mode, slot2_mode] and show_calculated_stats:
        from cartographer import stats as stats_module
        
        # Load all rounds for this course
        all_rounds = []
        rounds_dir = courses_json.parent / "rounds"
        if rounds_dir.exists():
            for year_file in rounds_dir.glob("*.json"):
                year_rounds = json.loads(year_file.read_text())
                for date_str, date_rounds in year_rounds.items():
                    for idx_str, rnd in date_rounds.items():
                        if rnd.get("course") == course_name:
                            all_rounds.append(rnd)
        
        # Group by hole number
        for hole_num in range(1, 19):
            rounds_by_hole[hole_num] = [
                r for r in all_rounds
                if str(hole_num) in r.get("holes", {})
            ]
        
        # Compute stats for each hole
        stats_data = {}
        for hole_num in range(1, 19):
            hole_key = str(hole_num)
            hole_ps_data = course_ps.get("holes", {}).get(hole_key, {})
            par = int(hole_ps_data.get("par", 4))
            hole_hcp = int(hole_ps_data.get("handicap", hole_num))
            
            # Get current handicap index (use most recent round's handicap)
            handicap_index = 15.0  # default
            if all_rounds:
                most_recent = max(all_rounds, key=lambda r: r.get("date", ""))
                hi_str = most_recent.get("handicap_index", "15.0")
                try:
                    handicap_index = float(hi_str)
                except ValueError:
                    pass
            
            hole_rounds = rounds_by_hole.get(hole_num, [])
            stats_data[hole_num] = {
                "fairway_misses": stats_module.calc_fairway_misses(hole_rounds, hole_num, par),
                "gir_misses": stats_module.calc_gir_misses(hole_rounds, hole_num),
                "benchmark": stats_module.calc_benchmark(hole_rounds, hole_num, par, handicap_index, hole_hcp),
                "penalties": stats_module.calc_penalties(hole_rounds, hole_num),
            }

    holes_geo = course_geo.get("holes", {})
    scale_data = course_geo.get("scale", {})
    projected = project_course(holes_geo, scale_data)

    # Generate 20 narrow PDFs in cross-paired order
    output_dir.mkdir(parents=True, exist_ok=True)
    narrow_pdfs: list[bytes] = []

    for page_idx in range(0, 20):
        if progress_callback:
            progress_callback(page_idx + 1, 20)

        if page_idx <= 8:
            hole_num = 9 - page_idx
            hd = _get_hole_render_data(
                hole_num, projected, scale_data, settings, course_ps,
                slot1_mode, slot2_mode,
            )
            if hd:
                svg_str = compose_page(
                    hole_svg=hd["hole_svg"], hole_num=hole_num, par=hd["par"],
                    tee_yardages=hd["tee_yardages"],
                    slot1_content=slot1_mode, slot2_content=slot2_mode,
                    slot1_svg=hd["slot1_svg"], slot2_svg=hd["slot2_svg"],
                    stats_data=stats_data,
                )
            else:
                import svgwrite as svg
                dwg = svg.Drawing(size=("306pt", "1008pt"), viewBox="0 0 306 1008")
                dwg.add(dwg.rect(insert=(0, 0), size=(306, 1008), fill="white"))
                svg_str = dwg.tostring()

        elif page_idx == 9:
            chart_svg = compose_chart_page()
            hd = _get_hole_render_data(
                18, projected, scale_data, settings, course_ps,
                slot1_mode, slot2_mode,
            )
            if hd:
                bottom_svg = compose_hole_bottom_page(
                    hole_num=18, slot1_content=slot1_mode, slot2_content=slot2_mode,
                    slot1_svg=hd["slot1_svg"], slot2_svg=hd["slot2_svg"],
                    stats_data=stats_data,
                )
            else:
                import svgwrite as svg
                dwg = svg.Drawing(size=("306pt", "504pt"), viewBox="0 0 306 504")
                dwg.add(dwg.rect(insert=(0, 0), size=(306, 504), fill="white"))
                bottom_svg = dwg.tostring()
            svg_str = compose_stacked_page(chart_svg, bottom_svg)

        elif page_idx <= 17:
            hole_num = page_idx
            hd = _get_hole_render_data(
                hole_num, projected, scale_data, settings, course_ps,
                slot1_mode, slot2_mode,
            )
            if hd:
                svg_str = compose_page(
                    hole_svg=hd["hole_svg"], hole_num=hole_num, par=hd["par"],
                    tee_yardages=hd["tee_yardages"],
                    slot1_content=slot1_mode, slot2_content=slot2_mode,
                    slot1_svg=hd["slot1_svg"], slot2_svg=hd["slot2_svg"],
                    stats_data=stats_data,
                )
            else:
                import svgwrite as svg
                dwg = svg.Drawing(size=("306pt", "1008pt"), viewBox="0 0 306 1008")
                dwg.add(dwg.rect(insert=(0, 0), size=(306, 1008), fill="white"))
                svg_str = dwg.tostring()

        elif page_idx == 18:
            hd = _get_hole_render_data(
                18, projected, scale_data, settings, course_ps,
                slot1_mode, slot2_mode,
            )
            if hd:
                top_svg = compose_hole_top_page(
                    hole_svg=hd["hole_svg"], hole_num=18, par=hd["par"],
                    tee_yardages=hd["tee_yardages"],
                )
            else:
                import svgwrite as svg
                dwg = svg.Drawing(size=("306pt", "504pt"), viewBox="0 0 306 504")
                dwg.add(dwg.rect(insert=(0, 0), size=(306, 504), fill="white"))
                top_svg = dwg.tostring()
            notes_svg = compose_notes_page()
            svg_str = compose_stacked_page(top_svg, notes_svg)

        elif page_idx == 19:
            back_svg = compose_back_page()
            front_svg = compose_front_page(
                course_name=course_name,
                location=course_ps.get("location"),
                total_par=total_par,
                tee_totals=tee_totals,
            )
            svg_str = compose_stacked_page(back_svg, front_svg)

        pdf_bytes = _svg_to_pdf_bytes(svg_str)
        narrow_pdfs.append(pdf_bytes)
        narrow_path = output_dir / f"yardage_book_{page_idx:02d}.pdf"
        narrow_path.write_bytes(pdf_bytes)

    # Combine into 5 saddle-stitch booklets, each with two 8.5"x14" pages
    # Each page has two narrow PDFs merged side-by-side
    booklet_pages = [
        ([0, 19], [1, 18]),
        ([2, 17], [3, 16]),
        ([4, 15], [5, 14]),
        ([6, 13], [7, 12]),
        ([8, 11], [9, 10]),
    ]

    for booklet_idx, (left_pair, right_pair) in enumerate(booklet_pages, start=1):
        writer = PdfWriter()

        for pair in (left_pair, right_pair):
            page = writer.add_blank_page(612, 1008)  # 8.5" x 14"
            left_pdf = PdfReader(io.BytesIO(narrow_pdfs[pair[0]])).pages[0]
            right_pdf = PdfReader(io.BytesIO(narrow_pdfs[pair[1]])).pages[0]
            page.merge_transformed_page(left_pdf, Transformation().translate(0, 0))
            page.merge_transformed_page(right_pdf, Transformation().translate(PAGE_W, 0))

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
