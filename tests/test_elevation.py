"""Tests for elevation data and contour computation."""
import numpy as np
from cartographer.elevation import compute_contours


def test_simple_ridge():
    """A peak in the center produces at least one contour ring."""
    z = np.array([
        [1.0, 1.0, 1.0],
        [1.0, 3.0, 1.0],
        [1.0, 1.0, 1.0],
    ])
    contours = compute_contours(z, levels=[2.0])
    assert 2.0 in contours
    assert len(contours[2.0]) >= 1
    assert len(contours[2.0][0]) >= 4


def test_flat_grid():
    """Flat grid produces no contours."""
    z = np.ones((5, 5))
    contours = compute_contours(z, levels=[2.0])
    assert len(contours.get(2.0, [])) == 0


def test_all_above():
    """All cells above the contour level -> no contours."""
    z = np.full((4, 4), 10.0)
    contours = compute_contours(z, levels=[5.0])
    assert len(contours.get(5.0, [])) == 0


def test_all_below():
    """All cells below the contour level -> no contours."""
    z = np.full((4, 4), 1.0)
    contours = compute_contours(z, levels=[5.0])
    assert len(contours.get(5.0, [])) == 0


def test_step_function():
    """A step function produces a straight vertical contour."""
    z = np.array([
        [1.0, 1.0, 2.0, 2.0],
        [1.0, 1.0, 2.0, 2.0],
        [1.0, 1.0, 2.0, 2.0],
    ])
    contours = compute_contours(z, levels=[1.5])
    assert 1.5 in contours
    assert len(contours[1.5]) == 1
    xs = contours[1.5][0][:, 0]
    assert np.allclose(xs, 1.5, atol=0.01)


def test_multiple_levels():
    """Multiple contour levels are all extracted."""
    z = np.tile(np.linspace(0, 10, 10), (10, 1))
    contours = compute_contours(z, levels=[2.0, 5.0, 8.0])
    assert 2.0 in contours
    assert 5.0 in contours
    assert 8.0 in contours
