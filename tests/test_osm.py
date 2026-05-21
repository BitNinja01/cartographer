"""Tests for cartographer/osm.py — OSM tag classification and node-ring conversion."""
from cartographer.osm import _classify_tags, _nodes_to_ring


# ---------------------------------------------------------------------------
# _classify_tags
# ---------------------------------------------------------------------------

class TestClassifyGolfTags:
    """Direct golf= tag mappings and known golf values."""

    def test_classify_golf_fairway(self):
        assert _classify_tags({"golf": "fairway"}) == "fairway"

    def test_classify_golf_green(self):
        assert _classify_tags({"golf": "green"}) == "green"

    def test_classify_golf_bunker(self):
        assert _classify_tags({"golf": "bunker"}) == "bunker"

    def test_classify_golf_water_hazard(self):
        assert _classify_tags({"golf": "water_hazard"}) == "water"

    def test_classify_golf_tee(self):
        assert _classify_tags({"golf": "tee"}) == "tee"

    def test_classify_golf_cartpath(self):
        assert _classify_tags({"golf": "cartpath"}) == "path"

    def test_classify_golf_hole(self):
        """Hole boundary markers — not renderable, should be excluded."""
        assert _classify_tags({"golf": "hole"}) is None

    def test_classify_golf_rough(self):
        """'rough' is not in _GOLF_TAG_MAP but has a golf tag — unclassified."""
        assert _classify_tags({"golf": "rough"}) == "unclassified"


class TestClassifyCartpathBypass:
    """Cart paths bypass the infrastructure-exclude check (golf=cartpath wins)."""

    def test_classify_cartpath_with_highway(self):
        """golf=cartpath must return 'path' even when highway=path is present."""
        assert _classify_tags({"golf": "cartpath", "highway": "path"}) == "path"


class TestClassifyWaterTags:
    """Open waterways (linestring) vs closed water bodies (polygon)."""

    def test_classify_waterway_stream_is_waterway(self):
        """Open waterway=stream must classify as 'waterway', not 'water'."""
        assert _classify_tags({"waterway": "stream"}) == "waterway"

    def test_classify_waterway_river_is_waterway(self):
        assert _classify_tags({"waterway": "river"}) == "waterway"

    def test_classify_waterway_ditch_is_waterway(self):
        assert _classify_tags({"waterway": "ditch"}) == "waterway"

    def test_classify_waterway_canal_is_waterway(self):
        assert _classify_tags({"waterway": "canal"}) == "waterway"

    def test_classify_waterway_drain_is_waterway(self):
        assert _classify_tags({"waterway": "drain"}) == "waterway"

    def test_classify_natural_water_still_water(self):
        """Closed pond (natural=water) must remain 'water'."""
        assert _classify_tags({"natural": "water"}) == "water"

    def test_classify_water_key_still_water(self):
        """Closed pond (water=pond) must remain 'water'."""
        assert _classify_tags({"water": "pond"}) == "water"

    def test_classify_golf_water_hazard_still_water(self):
        """golf=water_hazard is always a closed polygon — must remain 'water'."""
        assert _classify_tags({"golf": "water_hazard"}) == "water"


class TestClassifyLanduseGrass:
    """Bare landuse=grass (no golf tag) becomes 'fairway'."""

    def test_classify_landuse_grass_no_golf(self):
        assert _classify_tags({"landuse": "grass"}) == "fairway"

    def test_classify_landuse_grass_with_golf(self):
        """When landuse=grass also has a golf=fairway tag, the golf tag match
        in _GOLF_TAG_MAP fires first and returns 'fairway'."""
        assert _classify_tags({"landuse": "grass", "golf": "fairway"}) == "fairway"


class TestClassifyExcluded:
    """Features that should be filtered out entirely (return None)."""

    def test_classify_highway_excluded(self):
        assert _classify_tags({"highway": "path"}) is None

    def test_classify_building_excluded(self):
        assert _classify_tags({"building": "yes"}) is None

    def test_classify_amenity_excluded(self):
        assert _classify_tags({"amenity": "parking"}) is None

    def test_classify_landuse_forest_excluded(self):
        assert _classify_tags({"landuse": "forest"}) is None

    def test_classify_natural_wood_excluded(self):
        assert _classify_tags({"natural": "wood"}) is None

    def test_classify_landuse_residential_excluded(self):
        assert _classify_tags({"landuse": "residential"}) is None

    def test_classify_barrier_fence_excluded(self):
        assert _classify_tags({"barrier": "fence"}) is None

    def test_classify_barrier_wall_excluded(self):
        assert _classify_tags({"barrier": "wall"}) is None

    def test_classify_empty_tags(self):
        assert _classify_tags({}) is None


class TestClassifyUnclassified:
    """Tags that aren't excluded and don't match any known category."""

    def test_classify_unknown_tags(self):
        assert _classify_tags({"foo": "bar"}) == "unclassified"


# ---------------------------------------------------------------------------
# _nodes_to_ring
# ---------------------------------------------------------------------------

class TestNodesToRing:

    def test_all_nodes_present(self):
        coords = {
            "n1": (47.6, -122.3),
            "n2": (47.7, -122.4),
            "n3": (47.8, -122.5),
        }
        result = _nodes_to_ring(["n1", "n2", "n3"], coords)
        assert result == [[47.6, -122.3], [47.7, -122.4], [47.8, -122.5]]

    def test_some_nodes_missing(self):
        coords = {
            "n1": (47.6, -122.3),
            "n3": (47.8, -122.5),
        }
        result = _nodes_to_ring(["n1", "n2", "n3", "n4"], coords)
        assert result == [[47.6, -122.3], [47.8, -122.5]]

    def test_no_node_ids(self):
        assert _nodes_to_ring([], {"n1": (47.6, -122.3)}) == []

    def test_empty_coords_dict(self):
        assert _nodes_to_ring(["n1", "n2"], {}) == []
