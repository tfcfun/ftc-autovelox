"""Comune-based placement must never pin a camera it cannot justify."""

import json

from velox.geocode_comune import _build_query, _centroid, _consensus_ref, cache_key, locate

# Shape of a real Overpass reply, trimmed: two motorway ways both tagged A4.
_A4_REPLY = {
    "elements": [
        {"type": "way", "tags": {"highway": "motorway", "ref": "A4"},
         "geometry": [{"lon": 12.530, "lat": 45.670}, {"lon": 12.532, "lat": 45.672}]},
        {"type": "way", "tags": {"highway": "motorway", "ref": "A4"},
         "geometry": [{"lon": 12.531, "lat": 45.671}, {"lon": 12.533, "lat": 45.673}]},
    ]
}


def test_cache_key_is_filesystem_safe():
    assert cache_key("Noventa di Piave", "VE", "autostrada") == "NoventadiPiave_VE_autostrada"
    assert cache_key("Sant'Anastasia", "NA", "ordinaria") == "SantAnastasia_NA_ordinaria"


def test_query_selects_motorway_for_autostrada_and_trunk_for_ordinaria():
    assert "motorway" in _build_query("Noventa di Piave", "autostrada")
    ordinary = _build_query("Todi", "ordinaria")
    assert "trunk" in ordinary and "primary" in ordinary
    assert "motorway" not in ordinary


def test_query_escapes_a_quote_in_a_comune_name():
    assert '\\"' in _build_query('Comune "strano"', "ordinaria")


def test_consensus_ref_requires_unanimity():
    assert _consensus_ref(_A4_REPLY["elements"]) == "A4"


def test_consensus_ref_refuses_when_two_roads_cross_the_comune():
    mixed = [{"tags": {"ref": "A4"}}, {"tags": {"ref": "A57"}}]
    assert _consensus_ref(mixed) is None, "two roads means the row cannot be attributed"


def test_consensus_ref_tolerates_missing_refs_and_lists():
    assert _consensus_ref([{"tags": {}}]) is None
    assert _consensus_ref([{"tags": {"ref": "A4;E70"}}]) == "A4"
    assert _consensus_ref([{"tags": {"ref": "A 4"}}]) == "A4"


def test_centroid_averages_every_node():
    lon, lat = _centroid(_A4_REPLY["elements"])
    assert abs(lon - 12.5315) < 1e-6
    assert abs(lat - 45.6715) < 1e-6


def test_centroid_of_nothing_is_none():
    assert _centroid([]) is None
    assert _centroid([{"type": "way", "tags": {}}]) is None


def test_locate_returns_ref_and_point(tmp_path):
    result = locate("Noventa di Piave", "VE", "autostrada",
                    cache_dir=tmp_path, client=lambda _q: _A4_REPLY)
    assert result["ref"] == "A4"
    assert abs(result["lat"] - 45.6715) < 1e-6
    assert (tmp_path / "NoventadiPiave_VE_autostrada.json").exists()


def test_locate_uses_the_cache_without_the_network(tmp_path):
    (tmp_path / "NoventadiPiave_VE_autostrada.json").write_text(
        json.dumps({"ref": "A4", "lon": 12.5, "lat": 45.6})
    )

    def _explode(_q):
        raise AssertionError("a cache hit must not query OSM")

    assert locate("Noventa di Piave", "VE", "autostrada",
                  cache_dir=tmp_path, client=_explode)["ref"] == "A4"


def test_an_empty_reply_is_not_cached(tmp_path):
    """An empty reply may be a rate-limit in disguise; caching it would blind
    us to that comune permanently."""
    result = locate("Nowhere", "VE", "autostrada",
                    cache_dir=tmp_path, client=lambda _q: {"elements": []})
    assert result is None
    assert list(tmp_path.iterdir()) == []


def test_missing_comune_never_queries(tmp_path):
    def _explode(_q):
        raise AssertionError("'?' is not a comune")

    assert locate("?", "VE", "autostrada", cache_dir=tmp_path, client=_explode) is None
    assert locate("", "VE", "autostrada", cache_dir=tmp_path, client=_explode) is None
    assert locate("Todi", "", "ordinaria", cache_dir=tmp_path, client=_explode) is None
