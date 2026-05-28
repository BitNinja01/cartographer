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
        """'rough' is not in the whitelist — excluded."""
        assert _classify_tags({"golf": "rough"}) is None


class TestClassifyCartpathBypass:
    """Cart paths bypass the infrastructure-exclude check (golf=cartpath wins)."""

    def test_classify_cartpath_with_highway(self):
        """golf=cartpath must return 'path' even when highway=path is present."""
        assert _classify_tags({"golf": "cartpath", "highway": "path"}) == "path"


class TestClassifyWaterTags:
    """Multiple OSM tagging schemes that map to 'water'."""

    def test_classify_natural_water(self):
        assert _classify_tags({"natural": "water"}) == "water"

    def test_classify_waterway_stream(self):
        assert _classify_tags({"waterway": "stream"}) == "waterway"

    def test_classify_waterway_river(self):
        assert _classify_tags({"waterway": "river"}) == "waterway"

    def test_classify_water_key(self):
        assert _classify_tags({"water": "pond"}) == "water"

    def test_classify_bridged_stream_survives(self):
        """waterway=stream + bridge=yes must not be excluded — bridge is co-tagged on the stream."""
        assert _classify_tags({"waterway": "stream", "bridge": "yes"}) == "waterway"

    def test_classify_culverted_stream_survives(self):
        """waterway=stream + tunnel=culvert must not be excluded."""
        assert _classify_tags({"waterway": "stream", "tunnel": "culvert"}) == "waterway"

    def test_classify_named_stream_survives(self):
        """waterway=stream + name=... is common in OSM and must classify correctly."""
        assert _classify_tags({"waterway": "stream", "name": "Covington Creek"}) == "waterway"

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
    """Tags that don't match any whitelist category are silently dropped."""

    def test_classify_unknown_tags(self):
        assert _classify_tags({"foo": "bar"}) is None


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


# ---------------------------------------------------------------------------
# _expand_split_features
# ---------------------------------------------------------------------------

from cartographer.tagger.server import _expand_split_features


class TestExpandSplitFeatures:
    """_expand_split_features — synthetic ID generation."""

    def _make_feature(self, osm_id, ftype, coords, split_pieces=None):
        feat = {
            "osm_id": osm_id,
            "type": ftype,
            "geometry": coords,
            "is_point": False,
            "tags": {},
        }
        if split_pieces:
            feat["_split_pieces"] = split_pieces
        return feat

    def test_no_splits_passthrough(self):
        features = [
            self._make_feature("way/1", "fairway", [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]),
        ]
        result = _expand_split_features(features)
        assert len(result) == 1
        assert result[0]["osm_id"] == "way/1"

    def test_split_produces_two_sub_features(self):
        features = [
            self._make_feature("way/1", "green", [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
                               split_pieces=[
                                   [[[0, 0], [5, 0], [5, 10], [0, 10], [0, 0]]],
                                   [[[5, 0], [10, 0], [10, 10], [5, 10], [5, 0]]],
                               ]),
        ]
        result = _expand_split_features(features)
        assert len(result) == 2
        assert result[0]["osm_id"] == "way/1__0"
        assert result[1]["osm_id"] == "way/1__1"
        assert result[0]["split_group"] == "way/1"
        assert result[1]["split_group"] == "way/1"
        assert "_split_pieces" not in result[0]

    def test_mixed_split_and_unsplit(self):
        features = [
            self._make_feature("way/1", "fairway", [[0, 0], [10, 0], [10, 10]]),
            self._make_feature("way/2", "green", [[20, 20], [30, 20], [30, 30]],
                               split_pieces=[
                                   [[[20, 20], [25, 20], [25, 30]]],
                                   [[[25, 20], [30, 20], [30, 30]]],
                               ]),
        ]
        result = _expand_split_features(features)
        assert len(result) == 3
        ids = {f["osm_id"] for f in result}
        assert ids == {"way/1", "way/2__0", "way/2__1"}

    def test_preserves_feature_type(self):
        features = [
            self._make_feature("way/1", "bunker", [[0, 0], [10, 10]],
                               split_pieces=[
                                   [[[0, 0], [5, 5]]],
                                   [[[5, 5], [10, 10]]],
                               ]),
        ]
        result = _expand_split_features(features)
        assert result[0]["type"] == "bunker"
        assert result[1]["type"] == "bunker"
