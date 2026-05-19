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
from cartographer.geometry import project_course, fit_hole, smooth_hole_geometry
from cartographer.renderer import render_hole, render_green
from cartographer.layout import compose_page, PAGE_W, HOLE_H, SLOT_H

HOLE_CANVAS_W = 306.0   # 4.25 * 72
HOLE_CANVAS_H = 504.0   # 7" for hole diagram section


def _svg_to_pdf_bytes(svg_string: str) -> bytes:
    """Convert an SVG string to PDF bytes via cairosvg."""
    return cairosvg.svg2pdf(bytestring=svg_string.encode("utf-8"))


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

    # Generate 20 narrow PDFs (one per hole + front/back covers)
    output_dir.mkdir(parents=True, exist_ok=True)
    narrow_pdfs: list[bytes] = []

    for page_idx in range(1, 21):
        if progress_callback:
            progress_callback(page_idx, 20)
        
        if page_idx == 20:
            # Back cover (blank page)
            import svgwrite as svg
            dwg = svg.Drawing(size=("306pt", "1008pt"), viewBox="0 0 306 1008")
            dwg.add(dwg.rect(insert=(0, 0), size=(306, 1008), fill="white"))
            svg_str = dwg.tostring()
        else:
            hole_num = page_idx
            hole_key = str(hole_num)
            hole_geom = projected.get(hole_key, {})
            
            if not hole_geom:
                # Blank page for missing hole
                import svgwrite as svg
                dwg = svg.Drawing(size=("306pt", "1008pt"), viewBox="0 0 306 1008")
                dwg.add(dwg.rect(insert=(0, 0), size=(306, 1008), fill="white"))
                svg_str = dwg.tostring()
            else:
                # Apply smoothing
                hole_geom = smooth_hole_geometry(hole_geom)
                
                # Fit and render hole diagram
                fitted, _, _, scale = fit_hole(hole_geom, HOLE_CANVAS_W, HOLE_CANVAS_H)
                
                # Attach arcs
                ppy = float(scale_data.get("pixels_per_yard", 1.0))
                if settings.get("cartographer.yardage_arcs", True):
                    distances = settings.get("cartographer.yardage_arc_distances", [100, 125, 150])
                    green_rings = fitted.get("green", [])
                    if green_rings:
                        all_pts = [pt for ring in green_rings for pt in ring]
                        if all_pts:
                            gcx = sum(p[0] for p in all_pts) / len(all_pts)
                            gcy = sum(p[1] for p in all_pts) / len(all_pts)
                            fitted["_arcs"] = [(gcx, gcy, d * ppy * scale) for d in distances]
                
                hole_svg = render_hole(fitted, settings=settings)
                
                # Get tee yardages and par
                hole_ps_data = course_ps.get("holes", {}).get(hole_key, {})
                tee_yardages = {t: int(y) for t, y in hole_ps_data.get("tees", {}).items()}
                par = int(hole_ps_data.get("par", 4))
                
                # Render green SVG for slot (if needed)
                slot1_svg = ""
                slot2_svg = ""
                if slot1_mode == "green_grid":
                    green_fitted, _, _, _ = fit_hole(hole_geom, SLOT_H, SLOT_H, padding=10.0)
                    slot1_svg = render_green({"green": green_fitted.get("green", [])})
                if slot2_mode == "green_grid":
                    green_fitted, _, _, _ = fit_hole(hole_geom, SLOT_H, SLOT_H, padding=10.0)
                    slot2_svg = render_green({"green": green_fitted.get("green", [])})
                
                # Compose page
                svg_str = compose_page(
                    hole_svg=hole_svg,
                    hole_num=hole_num,
                    par=par,
                    tee_yardages=tee_yardages,
                    slot1_content=slot1_mode,
                    slot2_content=slot2_mode,
                    slot1_svg=slot1_svg,
                    slot2_svg=slot2_svg,
                    stats_data=stats_data,
                )
        
        pdf_bytes = _svg_to_pdf_bytes(svg_str)
        narrow_pdfs.append(pdf_bytes)
        narrow_path = output_dir / f"yardage_book_{page_idx:02d}.pdf"
        narrow_path.write_bytes(pdf_bytes)

    # Combine into 10 saddle-stitch booklets (pairs of narrow pages)
    for booklet_idx in range(1, 11):
        left_idx = (booklet_idx - 1) * 2
        right_idx = left_idx + 1
        
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
