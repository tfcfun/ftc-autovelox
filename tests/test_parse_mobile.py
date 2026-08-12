from pathlib import Path

from velox.parse_mobile import parse_mobile, pdf_to_text

FIXTURE = Path(__file__).parent.parent / "fixtures" / "2026-W33" / "lombardia.pdf"


def test_parses_the_real_lombardia_week_exactly():
    result = parse_mobile("Lombardia", pdf_to_text(FIXTURE.read_bytes()))

    assert result.region == "Lombardia"
    assert result.valid_from == "2026-08-10"
    assert result.valid_to == "2026-08-16"
    assert result.quarantine == []
    assert len(result.checks) == 3

    first, second, third = result.checks
    assert (first.date, first.road_ref, first.province) == ("2026-08-14", "SS9", "LO")
    assert first.road_type == "Strada Statale"
    assert first.road_name == "via Emilia"
    assert (second.date, second.road_ref, second.province) == ("2026-08-15", "A7", "PV")
    assert second.road_name == "Milano-Genova"
    assert (third.date, third.road_ref, third.province) == ("2026-08-16", "SS9", "LO")


def test_unknown_province_is_quarantined_not_dropped():
    text = """Lombardia
Validità da lunedì 10 agosto 2026 a domenica 16 agosto 2026
Giorno   Tratto stradale   Provincia
14/08/2026
    Strada Statale    SS / 9 via Emilia    XX
"""
    result = parse_mobile("Lombardia", text)
    assert result.checks == []
    assert len(result.quarantine) == 1
    assert "province" in result.quarantine[0]["reason"]
    assert "XX" in result.quarantine[0]["raw"]


def test_row_without_a_preceding_date_is_quarantined():
    text = """Lombardia
Validità da lunedì 10 agosto 2026 a domenica 16 agosto 2026
Giorno   Tratto stradale   Provincia
    Strada Statale    SS / 9 via Emilia    LO
"""
    result = parse_mobile("Lombardia", text)
    assert result.checks == []
    assert len(result.quarantine) == 1
    assert "date" in result.quarantine[0]["reason"]


def test_empty_document_yields_no_checks_and_no_crash():
    result = parse_mobile("Molise", "")
    assert result.checks == []
    assert result.valid_from is None
