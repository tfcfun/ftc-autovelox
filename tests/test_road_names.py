"""The road-name resolver must never invent a mapping.

Placing a camera on the wrong motorway is worse than leaving it unplaced, so
every path that cannot produce an unambiguous answer must produce None.
"""

from velox.road_names import (
    _pick_ref,
    load_cache,
    name_tokens,
    normalise_name,
    resolve_ref,
    save_cache,
)


def test_normalise_folds_the_two_dash_characters_the_pdfs_mix():
    assert normalise_name("Bologna – Taranto") == normalise_name("Bologna - Taranto")
    assert normalise_name("Torino – Trieste") == "torino trieste"


def test_normalise_strips_accents_and_punctuation():
    assert normalise_name("Della Val d’Esino") == "della val d esino"
    assert normalise_name("( SS Tiberina Bis)") == "ss tiberina bis"


def test_tokens_drop_noise_words_and_keep_place_names():
    tokens = name_tokens("Autostrada Milano – Napoli")
    assert "milano" in tokens
    assert "napoli" in tokens
    assert "autostrada" not in tokens


def test_tokens_are_empty_for_an_unknown_road():
    assert name_tokens("?") == []
    assert name_tokens("") == []


def test_pick_ref_requires_agreement():
    agree = [{"tags": {"ref": "A1"}}, {"tags": {"ref": "A1"}}]
    assert _pick_ref(agree) == "A1"


def test_pick_ref_refuses_to_choose_between_conflicting_answers():
    conflict = [{"tags": {"ref": "A1"}}, {"tags": {"ref": "A14"}}]
    assert _pick_ref(conflict) is None, "ambiguity must not resolve to a coin flip"


def test_pick_ref_handles_missing_and_empty_refs():
    assert _pick_ref([]) is None
    assert _pick_ref([{"tags": {}}]) is None
    assert _pick_ref([{"tags": {"ref": "  "}}]) is None


def test_pick_ref_normalises_spacing_and_takes_the_first_of_a_list():
    assert _pick_ref([{"tags": {"ref": "SS 7"}}]) == "SS7"
    assert _pick_ref([{"tags": {"ref": "A1;E35"}}]) == "A1"


def test_resolve_consults_the_cache_without_touching_the_network():
    cache = {"milano napoli": "A1"}

    def _explode(_query):
        raise AssertionError("a cache hit must not query OSM")

    assert resolve_ref("Milano – Napoli", cache=cache, client=_explode) == "A1"


def test_a_cached_none_is_honoured_and_not_requeried():
    cache = {"appia": None}

    def _explode(_query):
        raise AssertionError("a cached negative must not be re-queried")

    assert resolve_ref("Appia", cache=cache, client=_explode) is None


def test_resolve_fills_the_cache_on_a_miss():
    cache: dict[str, str | None] = {}
    result = resolve_ref(
        "Torino – Trieste", cache=cache, client=lambda _q: {"elements": [{"tags": {"ref": "A4"}}]}
    )
    assert result == "A4"
    assert cache["torino trieste"] == "A4"


def test_an_ambiguous_answer_is_cached_as_none_not_as_a_guess():
    cache: dict[str, str | None] = {}
    resolve_ref(
        "Qualcosa", cache=cache,
        client=lambda _q: {"elements": [{"tags": {"ref": "A1"}}, {"tags": {"ref": "A7"}}]},
    )
    assert cache["qualcosa"] is None


def test_unknown_road_name_never_queries():
    def _explode(_query):
        raise AssertionError("'?' is not a road name and must not be queried")

    assert resolve_ref("?", cache={}, client=_explode) is None


def test_cache_round_trips(tmp_path):
    path = tmp_path / "road_names.json"
    save_cache({"milano napoli": "A1", "appia": None}, path)
    loaded = load_cache(path)
    assert loaded["milano napoli"] == "A1"
    assert loaded["appia"] is None


def test_missing_cache_file_loads_as_empty(tmp_path):
    assert load_cache(tmp_path / "nope.json") == {}
