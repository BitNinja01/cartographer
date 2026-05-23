import math

import pytest

from cartographer.geometry import (
    _haversine_yards, compute_pixels_per_yard, _latlon_to_xy,
    project_ring, project_course, get_hole_bounds, get_green_centroid,
    get_green_rotation, fit_hole, compute_yardage_arcs,
    chaikin_smooth, chaikin_smooth_open, smooth_hole_geometry,
    compute_pixels_per_yard_from_geometry, find_overview_rotation,
)

# ---------------------------------------------------------------------------
# _haversine_yards
# ---------------------------------------------------------------------------

def test_haversine_yards_normal():
    # ~1 degree latitude at equator ≈ 111 km ≈ 121,000 yards
    d = _haversine_yards(0, 0, 1, 0)
    assert d == pytest.approx(121000, rel=1e-2)
    assert d > 0


def test_haversine_yards_same_point():
    assert _haversine_yards(0, 0, 0, 0) == 0.0


def test_haversine_yards_antipodal():
    # (0,0) to (0,180) — half the equator ≈ 20,015 km ≈ 21.9M yards
    d = _haversine_yards(0, 0, 0, 180)
    assert d == pytest.approx(21900000, rel=1e-2)
    assert d > 0


def test_haversine_yards_small_distance():
    # Very close points should give a small positive distance
    d = _haversine_yards(47.6, -122.3, 47.6001, -122.3)
    assert d == pytest.approx(11.0, abs=2.0)
    assert d > 0


# ---------------------------------------------------------------------------
# compute_pixels_per_yard
# ---------------------------------------------------------------------------

def test_ppy_normal():
    actual = _haversine_yards(0, 0, 1, 0)
    ppy = compute_pixels_per_yard([0, 0], [1, 0], actual)
    assert ppy == pytest.approx(1.0, rel=1e-6)
    assert ppy > 0


def test_ppy_same_point():
    assert compute_pixels_per_yard([0, 0], [0, 0], 100.0) == 1.0


def test_ppy_scales_linearly():
    actual = _haversine_yards(0, 0, 1, 0)
    ppy = compute_pixels_per_yard([0, 0], [1, 0], actual * 2)
    assert ppy == pytest.approx(2.0, rel=1e-6)


# ---------------------------------------------------------------------------
# _latlon_to_xy
# ---------------------------------------------------------------------------

def test_latlon_to_xy_origin():
    x, y = _latlon_to_xy(47.6, -122.3, 47.6, -122.3, 121000, 80000, 5.0)
    assert x == pytest.approx(0.0)
    assert y == pytest.approx(0.0)


def test_latlon_to_xy_north_flips_y():
    # Point north of origin → positive dy → negative y (flipped so north is up)
    x, y = _latlon_to_xy(48.0, -122.3, 47.6, -122.3, 121000, 80000, 1.0)
    assert x == pytest.approx(0.0)
    assert y == pytest.approx(-48400.0)


def test_latlon_to_xy_south():
    # Point south of origin → negative dy → positive y
    x, y = _latlon_to_xy(47.0, -122.3, 47.6, -122.3, 121000, 80000, 1.0)
    assert x == pytest.approx(0.0)
    assert y == pytest.approx(72600.0)


def test_latlon_to_xy_east():
    # Point east of origin → positive dx
    x, y = _latlon_to_xy(47.6, -122.0, 47.6, -122.3, 121000, 80000, 2.0)
    assert x == pytest.approx(48000.0)
    assert y == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# project_ring
# ---------------------------------------------------------------------------

def test_project_ring_normal():
    ring = [[47.6, -122.3], [47.601, -122.3], [47.601, -122.299], [47.6, -122.299]]
    projected = project_ring(ring, 47.6, -122.3, 121000, 80000, 5.0)
    assert len(projected) == 4
    assert all(isinstance(x, float) for x, y in projected)
    assert all(isinstance(y, float) for x, y in projected)


def test_project_ring_empty():
    assert project_ring([], 47.6, -122.3, 121000, 80000, 5.0) == []


# ---------------------------------------------------------------------------
# project_course
# ---------------------------------------------------------------------------

def test_project_course_normal():
    holes = {
        "1": {
            "fairway": [
                [[47.6, -122.3], [47.601, -122.3], [47.601, -122.299], [47.6, -122.299]]
            ],
            "green": [
                [[47.602, -122.298], [47.603, -122.298], [47.603, -122.297], [47.602, -122.297]]
            ],
            "bunkers": [],
            "water": [],
            "rough_boundary": [],
            "paths": [],
            "tee_boxes": {"white": [47.59, -122.31]},
        }
    }
    projected = project_course(holes, {"pixels_per_yard": 5.0})
    assert "1" in projected
    h = projected["1"]
    assert len(h["fairway"]) == 1
    assert len(h["fairway"][0]) == 4
    assert len(h["green"]) == 1
    assert "white" in h["tee_boxes"]
    assert all(isinstance(v, (list, tuple)) for v in h["tee_boxes"].values())

    # Verify multiple holes get projected independently
    holes["2"] = {
        "fairway": [[[48.0, -122.0], [48.001, -122.0], [48.001, -121.999], [48.0, -121.999]]],
        "green": [],
        "bunkers": [],
        "water": [],
        "rough_boundary": [],
        "paths": [],
        "tee_boxes": {},
    }
    projected = project_course(holes, {"pixels_per_yard": 5.0})
    assert "2" in projected


def test_project_course_no_coordinates():
    holes = {
        "1": {
            "fairway": [], "green": [], "bunkers": [],
            "water": [], "rough_boundary": [], "paths": [],
            "tee_boxes": {},
        }
    }
    result = project_course(holes, {"pixels_per_yard": 5.0})
    assert result is holes


# ---------------------------------------------------------------------------
# get_hole_bounds
# ---------------------------------------------------------------------------

def test_get_hole_bounds_normal(make_course_geo):
    course = make_course_geo(num_holes=1)
    min_x, min_y, max_x, max_y = get_hole_bounds(course["1"])
    assert min_x < max_x
    assert min_y < max_y
    assert isinstance(min_x, float)
    assert isinstance(min_y, float)


def test_get_hole_bounds_empty():
    hole = {
        "fairway": [], "green": [], "bunkers": [],
        "rough_boundary": [], "water": [], "paths": [],
        "tee_boxes": {},
    }
    assert get_hole_bounds(hole) == (0.0, 0.0, 100.0, 100.0)


# ---------------------------------------------------------------------------
# get_green_centroid
# ---------------------------------------------------------------------------

def test_get_green_centroid_normal(make_course_geo):
    course = make_course_geo(num_holes=1)
    cx, cy = get_green_centroid(course["1"])
    # Green is a 16-sided polygon centered at (110, 25) with r=10
    assert cx == pytest.approx(110.0, abs=1.0)
    assert cy == pytest.approx(25.0, abs=1.0)


def test_get_green_centroid_no_green():
    hole = {
        "fairway": [[[0.0, 0.0], [100.0, 0.0], [100.0, 40.0], [0.0, 40.0]]],
        "green": [],
        "bunkers": [],
        "rough_boundary": [],
        "water": [], "paths": [],
        "tee_boxes": {"white": (50.0, 20.0)},
    }
    cx, cy = get_green_centroid(hole)
    # bounds: x[0,100], y[0,40] → centre (50, 20)
    assert cx == pytest.approx(50.0)
    assert cy == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# get_green_rotation
# ---------------------------------------------------------------------------

def test_get_green_rotation_normal(make_course_geo):
    course = make_course_geo(num_holes=1)
    angle = get_green_rotation(course["1"])
    assert isinstance(angle, float)


def test_get_green_rotation_no_green():
    hole = {
        "fairway": [[[50.0, 50.0], [150.0, 50.0], [150.0, 100.0], [50.0, 100.0]]],
        "green": [],
        "bunkers": [],
        "rough_boundary": [],
        "water": [], "paths": [],
        "tee_boxes": {"white": (100.0, 75.0)},
    }
    # No green → centroid falls back to hole centre → dx=dy=0 → -90 - 0 = -90.0
    assert get_green_rotation(hole) == -90.0


# ---------------------------------------------------------------------------
# fit_hole
# ---------------------------------------------------------------------------

def test_fit_hole_normal(make_course_geo):
    course = make_course_geo(num_holes=1)
    fitted, ox, oy, scale = fit_hole(course["1"], 400.0, 300.0)
    assert scale > 0
    assert isinstance(ox, float)
    assert isinstance(oy, float)
    for key in ("fairway", "green", "bunkers", "water", "rough_boundary", "paths"):
        assert key in fitted
    assert "tee_boxes" in fitted


def test_fit_hole_scale_factor_positive(make_course_geo):
    for w, h in [(200, 100), (100, 200), (400, 300)]:
        _, _, _, scale = fit_hole(make_course_geo(num_holes=1)["1"], w, h)
        assert scale > 0


def test_fit_hole_with_explicit_rotation(make_course_geo):
    course = make_course_geo(num_holes=1)
    fitted, ox, oy, scale = fit_hole(course["1"], 400.0, 300.0, rotation=45.0)
    assert scale > 0
    assert "fairway" in fitted


def test_fit_hole_left_bias_shifts_geometry(make_course_geo):
    course = make_course_geo(num_holes=1)
    _, ox1, _, _ = fit_hole(course["1"], 400.0, 300.0)
    _, ox2, _, _ = fit_hole(course["1"], 400.0, 300.0, left_bias=30.0)
    assert ox2 < ox1


def test_fit_hole_preserves_padding(make_course_geo):
    course = make_course_geo(num_holes=1)
    fitted, ox, oy, scale = fit_hole(course["1"], 400.0, 300.0, padding=10.0)
    assert scale > 0


# ---------------------------------------------------------------------------
# compute_yardage_arcs
# ---------------------------------------------------------------------------

def test_yardage_arcs_normal():
    arcs = compute_yardage_arcs((100.0, 50.0), [100, 150, 200], 5.0, 1.0)
    assert len(arcs) == 3
    assert arcs[0] == (100.0, 50.0, 500.0)
    assert arcs[1] == (100.0, 50.0, 750.0)
    assert arcs[2] == (100.0, 50.0, 1000.0)


def test_yardage_arcs_with_scale_factor():
    arcs = compute_yardage_arcs((100.0, 50.0), [150], 5.0, 0.8)
    assert arcs[0] == (100.0, 50.0, 600.0)


def test_yardage_arcs_default_scale():
    arcs = compute_yardage_arcs((0.0, 0.0), [200], 2.0)
    assert arcs[0][2] == 400.0


def test_yardage_arcs_empty():
    assert compute_yardage_arcs((0.0, 0.0), [], 5.0) == []


# ---------------------------------------------------------------------------
# chaikin_smooth
# ---------------------------------------------------------------------------

def test_chaikin_smooth_normal():
    square = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    smoothed = chaikin_smooth(square, iterations=1)
    assert len(smoothed) > len(square)


def test_chaikin_smooth_two_points_unchanged():
    ring = [(0.0, 0.0), (100.0, 0.0)]
    assert chaikin_smooth(ring) is ring


def test_chaikin_smooth_empty():
    assert chaikin_smooth([]) == []


def test_chaikin_smooth_more_points_with_more_iterations():
    triangle = [(0.0, 0.0), (100.0, 0.0), (50.0, 100.0)]
    s1 = chaikin_smooth(triangle, iterations=1)
    s2 = chaikin_smooth(triangle, iterations=2)
    assert len(s2) > len(s1)


def test_chaikin_smooth_triangle_iteration_count():
    # 3 points → 6 points after 1 iteration, 12 after 2, 24 after 3
    triangle = [(0.0, 0.0), (100.0, 0.0), (50.0, 100.0)]
    s1 = chaikin_smooth(triangle, iterations=1)
    assert len(s1) == 6


def test_chaikin_smooth_default_iterations():
    triangle = [(0.0, 0.0), (100.0, 0.0), (50.0, 100.0)]
    s = chaikin_smooth(triangle)
    assert len(s) == 24  # 3 * 2^3 = 24


# ---------------------------------------------------------------------------
# chaikin_smooth_open — open polyline variant (no wrap-around)
# ---------------------------------------------------------------------------

class TestChaikinSmoothOpen:

    def test_preserves_endpoints(self):
        """Start and end points must be preserved exactly."""
        line = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
        result = chaikin_smooth_open(line, iterations=1)
        assert result[0] == (0.0, 0.0)
        assert result[-1] == (10.0, 10.0)

    def test_increases_point_count(self):
        """Each iteration roughly doubles the point count (minus endpoints)."""
        line = [(0.0, 0.0), (10.0, 0.0), (20.0, 10.0), (30.0, 0.0)]
        result = chaikin_smooth_open(line, iterations=1)
        # 4 points → 1 iteration → 2*(n-1) interior points + 2 endpoints = 2*3 + 2 = 8
        assert len(result) == 8

    def test_single_segment_midpoints(self):
        """Single segment A=(0,0) → B=(4,0): after 1 iteration gives [A, q, r, B].
        q = 0.75*A + 0.25*B = (1.0, 0.0), r = 0.25*A + 0.75*B = (3.0, 0.0).
        """
        line = [(0.0, 0.0), (4.0, 0.0)]
        result = chaikin_smooth_open(line, iterations=1)
        assert result[0] == (0.0, 0.0)
        assert result[1] == (1.0, 0.0)
        assert result[2] == (3.0, 0.0)
        assert result[3] == (4.0, 0.0)

    def test_short_line_passthrough(self):
        """Lines with fewer than 2 points pass through unchanged."""
        assert chaikin_smooth_open([], iterations=3) == []
        assert chaikin_smooth_open([(1.0, 2.0)], iterations=3) == [(1.0, 2.0)]

    def test_two_point_line(self):
        """Two-point lines are valid open paths."""
        line = [(0.0, 0.0), (10.0, 0.0)]
        result = chaikin_smooth_open(line, iterations=1)
        assert result[0] == (0.0, 0.0)
        assert result[-1] == (10.0, 0.0)
        assert len(result) == 4

    def test_zero_iterations(self):
        """Zero iterations returns the line unchanged."""
        line = [(0.0, 0.0), (5.0, 3.0), (10.0, 0.0)]
        assert chaikin_smooth_open(line, iterations=0) == line


# ---------------------------------------------------------------------------
# smooth_hole_geometry
# ---------------------------------------------------------------------------

def test_smooth_hole_geometry_normal(make_course_geo):
    course = make_course_geo(num_holes=1)
    smoothed = smooth_hole_geometry(course["1"])
    for key in ("fairway", "green", "bunkers", "water", "rough_boundary", "paths"):
        assert key in smoothed
    assert "tee_boxes" in smoothed


def test_smooth_hole_geometry_tee_boxes_unchanged(make_course_geo):
    course = make_course_geo(num_holes=1)
    original = course["1"]["tee_boxes"]
    smoothed = smooth_hole_geometry(course["1"])
    assert smoothed["tee_boxes"] is original


def test_smooth_hole_geometry_paths_empty(make_course_geo):
    course = make_course_geo(num_holes=1)
    original = course["1"]["paths"]
    smoothed = smooth_hole_geometry(course["1"])
    assert smoothed["paths"] == original


def test_smooth_hole_geometry_increases_vertex_count(make_course_geo):
    course = make_course_geo(num_holes=1)
    hole = course["1"]
    original_len = len(hole["fairway"][0])
    smoothed = smooth_hole_geometry(hole)
    assert len(smoothed["fairway"][0]) > original_len


# ---------------------------------------------------------------------------
# compute_pixels_per_yard_from_geometry
# ---------------------------------------------------------------------------

class TestComputePixelsPerYardFromGeometry:
    """compute_pixels_per_yard_from_geometry derives ppy from course bounding box."""

    def test_normal_course(self, make_course_geo):
        """Returns a positive float for a course with geometry."""
        holes = make_course_geo(num_holes=18)
        ppy = compute_pixels_per_yard_from_geometry(holes, canvas_h=504.0, padding=20.0)
        assert isinstance(ppy, float)
        assert ppy > 0.0

    def test_single_hole(self, make_course_geo):
        """Works with a single hole."""
        holes = make_course_geo(num_holes=1)
        ppy = compute_pixels_per_yard_from_geometry(holes, canvas_h=504.0, padding=20.0)
        assert ppy > 0.0

    def test_empty_holes_returns_default(self):
        """Empty holes dict returns 1.0 (safe fallback)."""
        ppy = compute_pixels_per_yard_from_geometry({}, canvas_h=504.0, padding=20.0)
        assert ppy == 1.0

    def test_no_coordinates_returns_default(self):
        """Holes with no coordinate data returns 1.0."""
        holes = {"1": {"fairway": [], "green": [], "bunkers": [], "water": [],
                       "waterways": [], "paths": [], "rough_boundary": [], "tee_boxes": {}}}
        ppy = compute_pixels_per_yard_from_geometry(holes, canvas_h=504.0, padding=20.0)
        assert ppy == 1.0

    def test_realistic_latlon_range(self):
        """A course spanning ~0.01 degrees lat/lon (~600-1200 yards) gives a
        ppy in a reasonable range (0.1 to 10.0 px/yd for a 504px canvas)."""
        holes = {
            "1": {
                "fairway": [[[47.600, -122.300], [47.605, -122.305], [47.603, -122.308]]],
                "green": [], "bunkers": [], "water": [], "waterways": [],
                "paths": [], "rough_boundary": [], "tee_boxes": {},
            },
            "18": {
                "fairway": [[[47.610, -122.290], [47.612, -122.293], [47.608, -122.295]]],
                "green": [], "bunkers": [], "water": [], "waterways": [],
                "paths": [], "rough_boundary": [], "tee_boxes": {},
            },
        }
        ppy = compute_pixels_per_yard_from_geometry(holes, canvas_h=504.0, padding=20.0)
        assert 0.1 < ppy < 10.0


# ---------------------------------------------------------------------------
# find_overview_rotation
# ---------------------------------------------------------------------------

class TestFindOverviewRotation:

    def _scale_at(self, points, angle_deg, avail_w=250.0, avail_h=370.0):
        """Helper: compute the uniform scale factor for the points at a given rotation."""
        r = math.radians(angle_deg)
        c, s = math.cos(r), math.sin(r)
        cx = sum(x for x, _ in points) / len(points)
        cy = sum(y for _, y in points) / len(points)
        mx = my = float("inf")
        Mx = My = float("-inf")
        for x, y in points:
            rx = (x - cx) * c - (y - cy) * s + cx
            ry = (x - cx) * s + (y - cy) * c + cy
            mx = min(mx, rx); Mx = max(Mx, rx)
            my = min(my, ry); My = max(My, ry)
        return min(avail_w / (Mx - mx or 1), avail_h / (My - my or 1))

    def test_empty_points_returns_zero(self):
        assert find_overview_rotation([], 270, 390) == 0.0

    def test_single_point_returns_zero(self):
        assert find_overview_rotation([(100.0, 100.0)], 270, 390) == 0.0

    def test_horizontal_strip_improves_scale(self):
        """A 400×30 strip should find a rotation that improves the scale
        factor over 0° for a portrait canvas (270×390)."""
        points = [(x, y) for x in range(0, 401, 10) for y in (0, 30)]
        angle = find_overview_rotation(points, 270, 390, padding=10.0)
        assert self._scale_at(points, angle) > self._scale_at(points, 0.0)
        assert -90 <= angle <= 90

    def test_vertical_strip_improves_scale(self):
        """A 30×400 strip — rotation can also help a vertical strip fit
        better if height exceeds available canvas."""
        points = [(x, y) for x in (0, 30) for y in range(0, 401, 10)]
        angle = find_overview_rotation(points, 270, 390, padding=10.0)
        assert self._scale_at(points, angle) > self._scale_at(points, 0.0)
        assert -90 <= angle <= 90

    def test_square_is_axis_aligned(self):
        """A 100×100 grid of points is symmetric — the optimal angle
        aligns with an axis (±90° or 0°)."""
        points = [(x, y) for x in range(0, 101, 10) for y in range(0, 101, 10)]
        angle = find_overview_rotation(points, 270, 390, padding=10.0)
        assert angle in (-90.0, 0.0, 90.0)

    def test_extreme_aspect_strip_improves_scale(self):
        """Points spanning 1000×20 benefit from rotation for a portrait canvas."""
        points = [(x, y) for x in range(0, 1001, 50) for y in (0, 20)]
        angle = find_overview_rotation(points, 270, 390, padding=10.0)
        assert self._scale_at(points, angle) > self._scale_at(points, 0.0)
        assert -90 <= angle <= 90

    def test_scale_is_never_worse(self):
        """The returned angle should never give a smaller scale than 0°,
        for any reasonable point set."""
        points = [(x, y) for x in range(0, 201, 20) for y in range(0, 51, 10)]
        angle = find_overview_rotation(points, 270, 390, padding=10.0)
        assert self._scale_at(points, angle) >= self._scale_at(points, 0.0)
