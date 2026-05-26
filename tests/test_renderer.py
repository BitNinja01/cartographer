"""Tests for SVG renderer."""
import io

import numpy as np
import svgwrite
from PIL import Image

from cartographer.renderer import _compute_arrows, render_green


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


def test_compute_arrows_gradient_ridge():
    """Arrows point downhill from a vertical gradient image."""
    w, h = 50, 40
    y_ramp = np.linspace(0, 255, h, dtype=np.uint8).reshape(h, 1)
    arr = np.broadcast_to(y_ramp, (h, w))
    img = Image.fromarray(arr, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    bbox = (10.0, 50.0, 110.0, 130.0)
    contour = [[[10.0, 90.0], [50.0, 90.0], [110.0, 90.0]]]

    arrows = _compute_arrows(png_bytes, bbox, contour, spacing=10.0)
    assert len(arrows) > 0
    for (cx, cy), (dx, dy) in arrows:
        assert abs(dx) < 0.2, f"Expected near-vertical, got dx={dx:.3f}"
        assert dy < 0, f"Expected downhill (negative dy), got dy={dy:.3f}"


def test_compute_arrows_empty_contours():
    """Empty contour list returns empty arrow list."""
    png_bytes = b"fake_png"
    bbox = (0, 0, 10, 10)
    arrows = _compute_arrows(png_bytes, bbox, [])
    assert arrows == []


def test_compute_arrows_short_contour():
    """Contour too short for even one arrow."""
    img = Image.fromarray(np.zeros((20, 20), dtype=np.uint8), mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    bbox = (0, 0, 100, 100)
    contour = [[[1.0, 1.0], [3.0, 3.0]]]
    arrows = _compute_arrows(png_bytes, bbox, contour, spacing=5.0)
    assert arrows == []


def test_compute_arrows_zero_bbox():
    """Zero-area bbox returns empty."""
    img = Image.fromarray(np.zeros((20, 20), dtype=np.uint8), mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    bbox = (0, 0, 0, 0)
    contour = [[[0.0, 0.0], [10.0, 10.0], [20.0, 0.0]]]
    arrows = _compute_arrows(png_bytes, bbox, contour)
    assert arrows == []


def test_compute_arrows_flat_image():
    """Flat (zero-gradient) image produces no arrows."""
    img = Image.fromarray(np.full((20, 20), 128, dtype=np.uint8), mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    bbox = (0, 0, 100, 100)
    contour = [[[10.0, 10.0], [50.0, 10.0], [50.0, 50.0], [10.0, 50.0]]]
    arrows = _compute_arrows(png_bytes, bbox, contour, spacing=10.0)
    assert arrows == []
