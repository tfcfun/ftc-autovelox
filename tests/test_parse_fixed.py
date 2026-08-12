from pathlib import Path

from velox.parse_fixed import parse_fixed
from velox.parse_mobile import pdf_to_text

FIXTURES = Path(__file__).parent.parent / "fixtures" / "2026-W33"


def _cameras(name: str, network: str):
    return parse_fixed(network, pdf_to_text((FIXTURES / name).read_bytes()))


def test_motorway_list_finds_the_known_veneto_row():
    result = _cameras("fisse_auto.pdf", "autostrada")
    assert len(result.cameras) >= 20
    match = [
        c for c in result.cameras
        if c.comune == "Noventa di Piave" and c.km_raw == "423+850"
    ]
    assert len(match) == 1
    camera = match[0]
    assert camera.province == "VE"
    assert camera.km == 423.85
    assert camera.direction_raw == "Ovest"
    assert camera.bearing_deg == 270
    assert camera.network == "autostrada"


def test_decimal_kilometre_format_is_accepted():
    result = _cameras("fisse_auto.pdf", "autostrada")
    match = [c for c in result.cameras if c.comune == "Serravalle Pistoiese"]
    assert match and match[0].km == 35.5


def test_free_text_kilometre_is_quarantined_not_invented():
    result = _cameras("fisse_auto.pdf", "autostrada")
    assert all(c.km is not None for c in result.cameras)
    galleria = [q for q in result.quarantine if "galleria" in q["raw"].lower()]
    assert galleria, "the Frejus tunnel row must be quarantined, not silently dropped"


def test_ordinary_roads_list_parses():
    result = _cameras("fisse_ord.pdf", "ordinaria")
    assert len(result.cameras) >= 20
    assert all(c.network == "ordinaria" for c in result.cameras)
    assert all(c.province is not None for c in result.cameras)


def test_every_camera_carries_a_region():
    for name, network in (("fisse_auto.pdf", "autostrada"), ("fisse_ord.pdf", "ordinaria")):
        result = _cameras(name, network)
        assert all(c.region for c in result.cameras), f"{name} lost region state"
