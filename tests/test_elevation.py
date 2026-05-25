"""Tests for elevation data and contour computation."""
from pathlib import Path

import numpy as np
from cartographer.elevation import (
    compute_contours, load_contours_cache, sample_green_elevation, _gaussian_blur,
)


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


def test_adaptive_contour_small_range():
    """Small elevation range (0.5m) produces 2 contour levels."""
    from unittest.mock import patch, MagicMock
    from pathlib import Path
    import numpy as np
    from affine import Affine
    from rasterio.crs import CRS
    from cartographer.elevation import compute_green_contours

    green_ring = [[47.0, -122.3], [47.0, -122.29], [47.01, -122.29], [47.01, -122.3]]

    ny, nx = 30, 30
    x = np.arange(nx, dtype=float)
    y = np.arange(ny, dtype=float)
    x_2d, y_2d = np.meshgrid(x, y, indexing="xy")
    z = 100.0 + np.tile(np.linspace(0, 0.5, nx), (ny, 1))

    win_transform = Affine(1.0, 0.0, 0.0, 0.0, 1.0, 0.0)

    with (
        patch("cartographer.elevation.sample_green_elevation", return_value=(x_2d, y_2d, z, win_transform)),
        patch("rasterio.open") as mock_rio,
        patch("cartographer.elevation._contour_paths_to_wgs84", side_effect=lambda paths, _: paths),
    ):
        mock_src = MagicMock()
        mock_src.crs = CRS.from_epsg(4326)
        mock_rio.return_value.__enter__.return_value = mock_src
        result = compute_green_contours(green_ring, Path("/fake.tif"))

        assert "contours" in result
        all_z = set()
        for e in result["contours"]:
            all_z.add(e["z"])
        # 0.5m/0.2m = 2.5 -> int=2 -> max(2, min(8, 2)) = 2 contours
        assert len(all_z) == 2, f"Expected 2 contour levels, got {len(all_z)}: {sorted(all_z)}"


def test_adaptive_contour_large_range():
    """Large elevation range (5.0m) uses max contour levels (8)."""
    from unittest.mock import patch, MagicMock
    from pathlib import Path
    import numpy as np
    from affine import Affine
    from rasterio.crs import CRS
    from cartographer.elevation import compute_green_contours

    green_ring = [[47.0, -122.3], [47.0, -122.29], [47.01, -122.29], [47.01, -122.3]]

    ny, nx = 30, 30
    x = np.arange(nx, dtype=float)
    y = np.arange(ny, dtype=float)
    x_2d, y_2d = np.meshgrid(x, y, indexing="xy")
    z = 100.0 + np.tile(np.linspace(0, 5.0, nx), (ny, 1))

    win_transform = Affine(1.0, 0.0, 0.0, 0.0, 1.0, 0.0)

    with (
        patch("cartographer.elevation.sample_green_elevation", return_value=(x_2d, y_2d, z, win_transform)),
        patch("rasterio.open") as mock_rio,
        patch("cartographer.elevation._contour_paths_to_wgs84", side_effect=lambda paths, _: paths),
    ):
        mock_src = MagicMock()
        mock_src.crs = CRS.from_epsg(4326)
        mock_rio.return_value.__enter__.return_value = mock_src
        result = compute_green_contours(green_ring, Path("/fake.tif"))

        assert "contours" in result
        all_z = set()
        for e in result["contours"]:
            all_z.add(e["z"])
        # 5.0m/0.2 = 25 -> int=25 -> max(2, min(8, 25)) = 8 contours
        assert len(all_z) == 8, f"Expected 8 contour levels, got {len(all_z)}: {sorted(all_z)}"


def test_adaptive_contour_min_clamp():
    """Very small range (0.3m) clamps to minimum 2 contour levels."""
    from unittest.mock import patch, MagicMock
    from pathlib import Path
    import numpy as np
    from affine import Affine
    from rasterio.crs import CRS
    from cartographer.elevation import compute_green_contours

    green_ring = [[47.0, -122.3], [47.0, -122.29], [47.01, -122.29], [47.01, -122.3]]

    ny, nx = 30, 30
    x = np.arange(nx, dtype=float)
    y = np.arange(ny, dtype=float)
    x_2d, y_2d = np.meshgrid(x, y, indexing="xy")
    z = 100.0 + np.tile(np.linspace(0, 0.3, nx), (ny, 1))

    win_transform = Affine(1.0, 0.0, 0.0, 0.0, 1.0, 0.0)

    with (
        patch("cartographer.elevation.sample_green_elevation", return_value=(x_2d, y_2d, z, win_transform)),
        patch("rasterio.open") as mock_rio,
        patch("cartographer.elevation._contour_paths_to_wgs84", side_effect=lambda paths, _: paths),
    ):
        mock_src = MagicMock()
        mock_src.crs = CRS.from_epsg(4326)
        mock_rio.return_value.__enter__.return_value = mock_src
        result = compute_green_contours(green_ring, Path("/fake.tif"))

        assert "contours" in result
        all_z = set()
        for e in result["contours"]:
            all_z.add(e["z"])
        # 0.3m/0.2 = 1.5 -> int=1 -> max(2, min(8, 1)) = 2 contours (minimum)
        assert len(all_z) == 2, f"Expected 2 contour levels, got {len(all_z)}: {sorted(all_z)}"


def test_adaptive_contour_flat():
    """Flat elevation (<0.10m range) returns None."""
    from unittest.mock import patch, MagicMock
    from pathlib import Path
    import numpy as np
    from affine import Affine
    from rasterio.crs import CRS
    from cartographer.elevation import compute_green_contours

    green_ring = [[47.0, -122.3], [47.0, -122.29], [47.01, -122.29], [47.01, -122.3]]

    ny, nx = 30, 30
    x = np.arange(nx, dtype=float)
    y = np.arange(ny, dtype=float)
    x_2d, y_2d = np.meshgrid(x, y, indexing="xy")
    z = 100.0 + np.tile(np.linspace(0, 0.09, nx), (ny, 1))

    win_transform = Affine(1.0, 0.0, 0.0, 0.0, 1.0, 0.0)

    with (
        patch("cartographer.elevation.sample_green_elevation", return_value=(x_2d, y_2d, z, win_transform)),
        patch("rasterio.open") as mock_rio,
    ):
        mock_src = MagicMock()
        mock_src.crs = CRS.from_epsg(4326)
        mock_rio.return_value.__enter__.return_value = mock_src
        result = compute_green_contours(green_ring, Path("/fake.tif"))
        assert result == {"contours": []}


def test_gaussian_blur_preserves_mean():
    """Blur preserves the mean of a constant array."""
    z = np.ones((10, 10)) * 5.0
    blurred = _gaussian_blur(z, sigma=1.0)
    assert np.allclose(blurred, 5.0, atol=0.01)


def test_gaussian_blur_reduces_noise():
    """Blur reduces high-frequency variation."""
    np.random.seed(42)
    z = 100.0 + np.random.randn(20, 20) * 2.0
    original_std = np.std(z)
    blurred = _gaussian_blur(z, sigma=1.0)
    assert np.std(blurred) < original_std


def test_gaussian_blur_nan_handling():
    """NaN values are preserved after blur."""
    z = np.ones((10, 10))
    z[3, 3] = np.nan
    blurred = _gaussian_blur(z, sigma=1.0)
    assert np.isnan(blurred[3, 3])
    assert not np.isnan(blurred[0, 0])


def test_gaussian_blur_zero_sigma():
    """sigma <= 0 returns the array unchanged."""
    z = np.random.randn(10, 10)
    assert np.array_equal(_gaussian_blur(z, 0.0), z)


def test_gaussian_blur_large_array_smoke():
    """Large array does not error."""
    z = np.random.randn(100, 100)
    _gaussian_blur(z, sigma=2.0)


def test_elevation_shading_normal():
    """DEM with elevation ramp produces a non-None shading result."""
    from unittest.mock import patch, MagicMock
    from pathlib import Path
    import numpy as np
    from affine import Affine
    from rasterio.crs import CRS
    from cartographer.elevation import compute_elevation_shading

    green_ring = [[47.0, -122.3], [47.0, -122.29], [47.01, -122.29], [47.01, -122.3]]

    ny, nx = 30, 30
    x = np.arange(nx, dtype=float)
    y = np.arange(ny, dtype=float)
    x_2d, y_2d = np.meshgrid(x, y, indexing="xy")
    z = 100.0 + np.tile(np.linspace(0, 2.0, nx), (ny, 1))

    win_transform = Affine(1.0, 0.0, 0.0, 0.0, -1.0, 30.0)

    with (
        patch("cartographer.elevation.sample_green_elevation", return_value=(x_2d, y_2d, z, win_transform)),
        patch("rasterio.open") as mock_rio,
        patch("cartographer.elevation._in_green_mask") as mock_mask,
    ):
        mock_src = MagicMock()
        mock_src.crs = CRS.from_epsg(4326)
        mock_rio.return_value.__enter__.return_value = mock_src
        mock_mask.return_value = np.ones_like(z, dtype=bool)

        img = compute_elevation_shading(green_ring, Path("/fake.tif"))

        assert img is not None
        assert img.mode == "L"
        assert img.size == (120, 120)
        pixels = list(img.getdata())
        assert max(pixels) >= 250
        assert min(pixels) <= 10


def test_elevation_shading_flat():
    """Flat elevation (<0.25m range) returns None."""
    from unittest.mock import patch, MagicMock
    from pathlib import Path
    import numpy as np
    from affine import Affine
    from rasterio.crs import CRS
    from cartographer.elevation import compute_elevation_shading

    green_ring = [[47.0, -122.3], [47.0, -122.29], [47.01, -122.29], [47.01, -122.3]]

    ny, nx = 5, 5
    x = np.arange(nx, dtype=float)
    y = np.arange(ny, dtype=float)
    x_2d, y_2d = np.meshgrid(x, y, indexing="xy")
    z = 100.0 * np.ones((ny, nx))

    win_transform = Affine(1.0, 0.0, 0.0, 0.0, -1.0, 5.0)

    with (
        patch("cartographer.elevation.sample_green_elevation", return_value=(x_2d, y_2d, z, win_transform)),
        patch("rasterio.open") as mock_rio,
        patch("cartographer.elevation._in_green_mask") as mock_mask,
    ):
        mock_src = MagicMock()
        mock_src.crs = CRS.from_epsg(4326)
        mock_rio.return_value.__enter__.return_value = mock_src
        mock_mask.return_value = np.ones_like(z, dtype=bool)

        result = compute_elevation_shading(green_ring, Path("/fake.tif"))
        assert result is None


def test_elevation_shading_upscaled_dimensions():
    """4x upscale produces 4x dimensions."""
    from unittest.mock import patch, MagicMock
    from pathlib import Path
    import numpy as np
    from affine import Affine
    from rasterio.crs import CRS
    from cartographer.elevation import compute_elevation_shading

    green_ring = [[47.0, -122.3], [47.0, -122.29], [47.01, -122.29], [47.01, -122.3]]

    z = np.ones((10, 15)) * 100.0
    z[5, 7] = 102.0  # Single peak (range = 2.0)
    x = np.arange(15, dtype=float)
    y = np.arange(10, dtype=float)
    x_2d, y_2d = np.meshgrid(x, y, indexing="xy")

    win_transform = Affine(1.0, 0.0, 0.0, 0.0, -1.0, 10.0)

    with (
        patch("cartographer.elevation.sample_green_elevation", return_value=(x_2d, y_2d, z, win_transform)),
        patch("rasterio.open") as mock_rio,
        patch("cartographer.elevation._in_green_mask") as mock_mask,
    ):
        mock_src = MagicMock()
        mock_src.crs = CRS.from_epsg(4326)
        mock_rio.return_value.__enter__.return_value = mock_src
        mock_mask.return_value = np.ones_like(z, dtype=bool)

        img = compute_elevation_shading(green_ring, Path("/fake.tif"))
        assert img is not None
        assert img.size == (60, 40)
