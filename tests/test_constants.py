from velox.constants import PROVINCE_CODES, REGIONS, DIRECTION_BEARINGS, SCHEMA_VERSION


def test_province_codes_are_complete_and_well_formed():
    assert len(PROVINCE_CODES) == 107
    assert all(len(c) == 2 and c.isupper() for c in PROVINCE_CODES)
    # Codes seen in the real fixtures must be present.
    for code in ("LO", "PV", "VE", "PT", "AR", "FI", "PR", "PU", "MC", "FM", "TO", "VA", "LI"):
        assert code in PROVINCE_CODES


def test_regions_match_the_source_page():
    assert len(REGIONS) == 20
    assert "Lombardia" in REGIONS
    assert "Valle d'Aosta" in REGIONS


def test_direction_bearings_cover_the_cardinals():
    assert DIRECTION_BEARINGS["nord"] == 0
    assert DIRECTION_BEARINGS["ovest"] == 270
    assert len(DIRECTION_BEARINGS) == 8


def test_schema_version_is_one():
    assert SCHEMA_VERSION == 1
