"""Tests for elevation data and contour computation."""
from pathlib import Path

import numpy as np
from cartographer.elevation import compute_contours, load_contours_cache, sample_green_elevation


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


def test_dem_cached():
    """When DEM is cached, no network request is made."""
    from unittest.mock import MagicMock, patch
    from pathlib import Path
    from cartographer.elevation import get_course_dem

    holes = {"1": {"green": [[[-122.3, 47.6], [-122.3, 47.61], [-122.29, 47.61], [-122.29, 47.6]]]}}
    with patch("cartographer.data.get_dem_path") as mock_path:
        mock_path.return_value = MagicMock(spec=Path)
        mock_path.return_value.exists.return_value = True
        with patch("cartographer.elevation.requests.get") as mock_get:
            result = get_course_dem("test", holes)
            assert result is not None
            mock_get.assert_not_called()


def test_dem_no_greens():
    """No greens -> no DEM needed, returns None."""
    from unittest.mock import patch
    from cartographer.elevation import get_course_dem

    with patch("cartographer.elevation.requests.get") as mock_get:
        assert get_course_dem("test", {}) is None
        mock_get.assert_not_called()


def test_sample_missing_dem():
    """Non-existent DEM returns None."""
    ring = [[-122.3, 47.6], [-122.3, 47.61], [-122.29, 47.61], [-122.29, 47.6]]
    assert sample_green_elevation(ring, Path("/nonexistent/dem.tif")) is None


def test_load_contours_cache_miss():
    """Non-existent cache returns empty dict."""
    assert load_contours_cache("nonexistent") == {}
