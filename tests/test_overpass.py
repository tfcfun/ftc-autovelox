import json

from velox.overpass import cache_key, query_road_geometry, simplify


def test_cache_key_is_stable_and_filesystem_safe():
    assert cache_key("SS9", "LO") == "SS9_LO"
    assert cache_key("A7", "PV") == "A7_PV"


def test_simplify_keeps_endpoints_and_drops_collinear_points():
    straight = [[9.0, 45.0], [9.001, 45.0], [9.002, 45.0], [9.003, 45.0]]
    result = simplify(straight, tolerance_m=20.0)
    assert result[0] == [9.0, 45.0]
    assert result[-1] == [9.003, 45.0]
    assert len(result) == 2


def test_simplify_preserves_a_genuine_bend():
    bent = [[9.0, 45.0], [9.01, 45.02], [9.02, 45.0]]
    assert len(simplify(bent, tolerance_m=20.0)) == 3


def test_cache_hit_avoids_the_network(tmp_path):
    (tmp_path / "SS9_LO.json").write_text(json.dumps([[9.5, 45.3], [9.6, 45.31]]))

    def _explode(*a, **k):
        raise AssertionError("network must not be touched on a cache hit")

    geometry = query_road_geometry("SS9", "LO", cache_dir=tmp_path, client=_explode)
    assert geometry == [[9.5, 45.3], [9.6, 45.31]]


def test_cache_miss_queries_and_writes(tmp_path):
    payload = {
        "elements": [
            {"type": "way", "geometry": [
                {"lon": 9.50, "lat": 45.30},
                {"lon": 9.51, "lat": 45.31},
            ]}
        ]
    }
    geometry = query_road_geometry("SS9", "LO", cache_dir=tmp_path, client=lambda q: payload)
    assert geometry[0] == [9.50, 45.30]
    assert (tmp_path / "SS9_LO.json").exists()


def test_no_result_returns_none_and_does_not_poison_the_cache(tmp_path):
    geometry = query_road_geometry("SS999", "LO", cache_dir=tmp_path,
                                   client=lambda q: {"elements": []})
    assert geometry is None
    assert not (tmp_path / "SS999_LO.json").exists()
