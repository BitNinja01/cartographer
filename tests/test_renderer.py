"""Tests for SVG renderer."""
import svgwrite
from cartographer.renderer import render_green, _draw_contours, _draw_green_grid


def test_render_green_with_contours():
    """Contour data produces SVG with path elements and elevation labels."""
    green_geom = {"green": [[[0, 0], [100, 0], [100, 100], [0, 100]]]}
    contour_data = {
        "index": [
            {"path": [[10, 10], [50, 10], [50, 50], [10, 50]], "z": 100.0},
        ],
        "intermediate": [
            {"path": [[20, 20], [40, 20], [40, 40], [20, 40]], "z": 99.0},
        ],
    }
    svg = render_green(green_geom, canvas_size=200, contour_data=contour_data)
    assert "<path " in svg
    assert "100" in svg  # elevation label
    assert "fill=\"none\"" in svg


def test_render_green_without_contours():
    """No contour data produces ruled grid lines."""
    green_geom = {"green": [[[0, 0], [100, 0], [100, 100], [0, 100]]]}
    svg = render_green(green_geom, canvas_size=200, contour_data=None)
    assert "x1=" in svg
    assert "y1=" in svg


def test_render_green_empty_contours():
    """Empty contour dict produces valid SVG with no paths."""
    green_geom = {"green": [[[0, 0], [100, 0], [100, 100], [0, 100]]]}
    svg = render_green(green_geom, canvas_size=200, contour_data={"index": [], "intermediate": []})
    assert "svg" in svg


def test_draw_contours_empty():
    """_draw_contours handles empty data without error."""
    dwg = svgwrite.Drawing(size=("200pt", "200pt"), viewBox="0 0 200 200")
    _draw_contours(dwg, {"index": [], "intermediate": []}, x_offset=0)
    assert True


def test_draw_green_grid():
    """_draw_green_grid produces horizontal and vertical lines."""
    dwg = svgwrite.Drawing(size=("200pt", "200pt"), viewBox="0 0 200 200")
    _draw_green_grid(dwg, 200, 200, 0)
    svg = dwg.tostring()
    assert "x1=" in svg
    assert "y1=" in svg
