#!/usr/bin/env python3
"""Generate hole 16 green grid SVG for inspection."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cartographer.data import load_courses_geo, get_dem_path
from cartographer.geometry import (
    project_course, fit_hole, chaikin_smooth, get_green_rotation,
    compute_pixels_per_yard_from_geometry,
)
from cartographer.layout import SLOT_H, PAGE_W
from cartographer.renderer import render_green
from cartographer.elevation import compute_elevation_shading
from PIL import Image
import io

def main():
    all_geo = load_courses_geo()
    geo = None
    for name, data in all_geo.items():
        if name.lower().replace(" ", "_") == "maplewood":
            geo = data
            break
    
    holes_geo = geo.get("holes", {})
    scale_data = geo.get("scale", {})
    
    for hole_num in [4, 14, 16]:
        hole_key = str(hole_num)
        if hole_key not in holes_geo:
            continue
        
        ppy = compute_pixels_per_yard_from_geometry(
            {hole_key: holes_geo[hole_key]}, canvas_h=504.0
        )
        effective_scale = {**scale_data, "pixels_per_yard": ppy}
        projected = project_course(holes_geo, effective_scale)
        hole_geom = projected.get(hole_key, {})
        
        green_rot = get_green_rotation(hole_geom)
        
        proj_green = hole_geom.get("green", [])
        if not proj_green:
            continue
        
        slot_geom = {"green": hole_geom.get("green", [])}
        slot_fitted, off_x, off_y, slot_scale = fit_hole(
            {
                **slot_geom,
                "fairway": [], "bunkers": [], "water": [],
                "rough_boundary": [], "tee_boxes": {},
            },
            SLOT_H, SLOT_H, padding=15.0, rotation=green_rot,
        )
        slot_fitted["green"] = [chaikin_smooth(r) for r in slot_fitted.get("green", [])]
        
        dem_path = get_dem_path("Maplewood")
        shading_data = None
        if dem_path.exists():
            orig_greens = holes_geo[hole_key].get("green", [])
            if orig_greens:
                shading_img = compute_elevation_shading(orig_greens[0], dem_path)
                if shading_img is not None:
                    px = [p[0] for p in proj_green[0]]
                    py = [p[1] for p in proj_green[0]]
                    pmin_x, pmax_x = min(px), max(px)
                    pmin_y, pmax_y = min(py), max(py)
                    pw, ph = pmax_x - pmin_x, pmax_y - pmin_y
                    
                    svg_bx = pmin_x * slot_scale + off_x
                    svg_by = pmin_y * slot_scale + off_y
                    svg_bw = pw * slot_scale
                    svg_bh = ph * slot_scale
                    
                    # Rotation centre must match fit_hole() which rotates
                    # around the projected green bbox centre.
                    gcx = svg_bx + svg_bw / 2
                    gcy = svg_by + svg_bh / 2
                    
                    img_resized = shading_img.resize(
                        (max(1, int(svg_bw)), max(1, int(svg_bh))), Image.LANCZOS
                    )
                    buf = io.BytesIO()
                    img_resized.save(buf, format="PNG")
                    shading_data = {
                        "png_bytes": buf.getvalue(),
                        "bbox": (svg_bx, svg_by, svg_bx + svg_bw, svg_by + svg_bh),
                        "rotate_angle": green_rot,
                        "rotate_cx": gcx,
                        "rotate_cy": gcy,
                    }
                    
                    print(f"Hole {hole_num}:")
                    print(f"  green_rot: {green_rot:.2f}°")
                    print(f"  slot_scale: {slot_scale:.4f}")
                    print(f"  svg_bx,sby: ({svg_bx:.2f},{svg_by:.2f})")
                    print(f"  svg_bw,bh: ({svg_bw:.2f},{svg_bh:.2f})")
                    print(f"  int_bw,bh: ({int(svg_bw)},{int(svg_bh)})")
                    print(f"  rot_center: ({gcx:.2f},{gcy:.2f})")
                    print(f"  orig_img_size: {shading_img.size}")
                    print(f"  resized_img_size: {img_resized.size}")
        
        svg = render_green(
            slot_fitted, canvas_w=PAGE_W, canvas_h=SLOT_H,
            fitted=True, shading_data=shading_data,
        )
        
        out_path = Path(f"/tmp/green_hole{hole_num}_diag.svg")
        out_path.write_text(svg)
        print(f"  Written to {out_path}")
        print()

if __name__ == "__main__":
    main()
