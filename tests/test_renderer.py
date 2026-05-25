"""Tests for SVG renderer."""
import svgwrite
from cartographer.renderer import render_green


def test_render_green_with_shading():
    """Shading data produces SVG with <image> element and clipPath."""
    green_geom = {"green": [[[0, 0], [100, 0], [100, 100], [0, 100]]]}
    shading_data = {
        "png_bytes": b"fake_png_bytes",
        "bbox": (0, 0, 100, 100),
    }
    svg = render_green(green_geom, canvas_size=200, shading_data=shading_data)
    assert "clipPath" in svg or "clip-path" in svg or "clip_path" in svg


def test_render_green_without_shading():
    """No shading data shows green fill with outline."""
    green_geom = {"green": [[[0, 0], [100, 0], [100, 100], [0, 100]]]}
    svg = render_green(green_geom, canvas_size=200, shading_data=None)
    # Should have green polygon fill
    assert "#87debd" in svg
