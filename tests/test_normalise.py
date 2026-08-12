from velox.normalise import (
    normalise_direction,
    normalise_km,
    normalise_province,
    normalise_road_ref,
    parse_it_date,
)


def test_road_ref_strips_leading_zero_and_separator():
    assert normalise_road_ref("Autostrada", "A / 07 Milano-Genova") == ("A7", "Milano-Genova")
    assert normalise_road_ref("Strada Statale", "SS / 9 via Emilia") == ("SS9", "via Emilia")
    assert normalise_road_ref("Strada Statale", "SS / 016 Adriatica") == ("SS16", "Adriatica")


def test_road_ref_handles_spacing_and_dots():
    assert normalise_road_ref("Strada Statale", "S.S. 16 Adriatica") == ("SS16", "Adriatica")
    assert normalise_road_ref("Strada Statale", "SS16")[0] == "SS16"


def test_road_ref_returns_none_when_unrecognisable():
    ref, name = normalise_road_ref("Strada Statale", "Tangenziale Nord")
    assert ref is None
    assert name == "Tangenziale Nord"


def test_km_accepts_the_three_observed_formats():
    assert normalise_km("423+850") == 423.85
    assert normalise_km("08+250") == 8.25
    assert normalise_km("35,500") == 35.5
    assert normalise_km("53+000") == 53.0


def test_km_rejects_free_text_rather_than_guessing():
    assert normalise_km("Interno galleria") is None
    assert normalise_km("") is None
    assert normalise_km("galleria") is None


def test_direction_maps_compass_words_case_insensitively():
    assert normalise_direction("Ovest") == 270
    assert normalise_direction("nord") == 0
    assert normalise_direction("Nord-Est") == 45
    assert normalise_direction("FRANCIA") is None
    assert normalise_direction("ITALIA") is None


def test_province_validated_against_closed_set():
    assert normalise_province("LO") == "LO"
    assert normalise_province(" ve ") == "VE"
    assert normalise_province("XX") is None
    assert normalise_province("") is None


def test_italian_date_conversion():
    assert parse_it_date("14/08/2026") == "2026-08-14"
    assert parse_it_date("1/8/2026") == "2026-08-01"
    assert parse_it_date("not a date") is None
    assert parse_it_date("32/08/2026") is None
