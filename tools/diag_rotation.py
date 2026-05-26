#!/usr/bin/env python3
"""Diagnose elevation shading rotation centre mismatch for Maplewood holes 4, 14, 16."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cartographer.data import load_courses_geo
from cartographer.geometry import (
    project_course, fit_hole, chaikin_smooth, get_green_rotation,
    compute_pixels_per_yard_from_geometry,
)

SLOT_H = 243.0

def main():
    all_geo = load_courses_geo()
    geo = all_geo.get("Maplewood")
    if not geo:
        print("ERROR: Maplewood course not found in courses_geo.json")
        print("Available courses:", list(all_geo.keys())[:10])
        return

    holes_geo = geo.get("holes", {})
    scale_data = geo.get("scale", {})

    for hole_num in [4, 14, 16]:
        hole_key = str(hole_num)
        if hole_key not in holes_geo:
            print(f"\nHole {hole_num}: NOT FOUND")
            continue

        ppy = compute_pixels_per_yard_from_geometry(
            {hole_key: holes_geo[hole_key]}, canvas_h=504.0
        )
        effective_scale = {**scale_data, "pixels_per_yard": ppy}
        projected = project_course(holes_geo, effective_scale)
        hole_geom = projected.get(hole_key, {})
        if not hole_geom:
            continue

        green_rot = get_green_rotation(hole_geom)

        proj_green = hole_geom.get("green", [])
        if not proj_green:
            continue

        px = [p[0] for p in proj_green[0]]
        py = [p[1] for p in proj_green[0]]
        hole_cx = (min(px) + max(px)) / 2
        hole_cy = (min(py) + max(py)) / 2

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

        # Correct rotation centre: projected bbox centre → SVG space
        svg_correct_cx = hole_cx * slot_scale + off_x
        svg_correct_cy = hole_cy * slot_scale + off_y

        # Actual rotation centre used: centroid of fitted+smoothed green
        fitted_green = slot_fitted["green"][0]
        gcx = sum(p[0] for p in fitted_green) / len(fitted_green)
        gcy = sum(p[1] for p in fitted_green) / len(fitted_green)

        offset_dx = gcx - svg_correct_cx
        offset_dy = gcy - svg_correct_cy
        offset_dist = math.sqrt(offset_dx**2 + offset_dy**2)

        # Also compute projected centroid vs bbox centre (unrotated)
        pcx = sum(p[0] for p in proj_green[0]) / len(proj_green[0])
        pcy = sum(p[1] for p in proj_green[0]) / len(proj_green[0])
        raw_cx_offset = pcx - hole_cx
        raw_cy_offset = pcy - hole_cy
        raw_offset_dist = math.sqrt(raw_cx_offset**2 + raw_cy_offset**2)

        print(f"\n{'='*50}")
        print(f"Hole {hole_num}")
        print(f"  green_rot = {green_rot:.2f}°")
        print(f"  slot_scale = {slot_scale:.4f}, off = ({off_x:.2f}, {off_y:.2f})")
        print(f"  Projected green bbox centre: ({hole_cx:.2f}, {hole_cy:.2f})")
        print(f"  Projected green centroid:    ({pcx:.2f}, {pcy:.2f})")
        print(f"  Unrotated centroid vs bbox centre offset: ({raw_cx_offset:.2f}, {raw_cy_offset:.2f}) dist={raw_offset_dist:.2f}")
        print(f"  SVG correct rotation centre:  ({svg_correct_cx:.2f}, {svg_correct_cy:.2f})")
        print(f"  SVG fitted green centroid:    ({gcx:.2f}, {gcy:.2f})")
        print(f"  ROTATION CENTRE MISMATCH:     ({offset_dx:.2f}, {offset_dy:.2f}) dist={offset_dist:.2f}")
        print(f"  Projected green bbox: ({min(px):.2f},{min(py):.2f}) → ({max(px):.2f},{max(py):.2f})")
        print(f"  SVG bbox: ({min(px)*slot_scale+off_x:.2f},{min(py)*slot_scale+off_y:.2f}) → ({max(px)*slot_scale+off_x:.2f},{max(py)*slot_scale+off_y:.2f})")


if __name__ == "__main__":
    main()
