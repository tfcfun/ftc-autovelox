import json
from pathlib import Path

from velox.mit import classify_tipo, normalise_device

SAMPLE = Path(__file__).parent.parent / "fixtures" / "2026-W33" / "mit_dispositivi_sample.json"


def test_classifies_the_common_spellings():
    assert classify_tipo("MOBILE") == "mobile"
    assert classify_tipo("mobile") == "mobile"
    assert classify_tipo("Mobile ") == "mobile"
    assert classify_tipo("FISSO") == "fisso"
    assert classify_tipo("fisso") == "fisso"
    assert classify_tipo("FISSO/MOBILE") == "fisso_mobile"
    assert classify_tipo("fisso-mobile") == "fisso_mobile"
    assert classify_tipo("FISSO - Velocità media") == "media"
    assert classify_tipo("Sistema rilevamento velocità media") == "media"


def test_free_text_descriptions_still_classify():
    assert classify_tipo("rilevatore di velocità in modalità istantanea") == "sconosciuto"
    assert classify_tipo("Dispositivo rilevamento velocità istantanea fisso") == "fisso"
    assert classify_tipo("Dispositivo rilevamento velocità istantanea mobile") == "mobile"


def test_junk_never_raises_and_never_guesses():
    for junk in ("//////////////////////////////////", "NESSUN VELOX", "13/06/2011", "", "-"):
        assert classify_tipo(junk) == "sconosciuto"


def test_normalise_device_decodes_entities_and_dates():
    row = json.loads(SAMPLE.read_text(encoding="utf-8"))[0]
    record = normalise_device(row)
    assert "&quot;" not in record["ente"]
    assert '"' in record["ente"]
    assert record["data_decreto"] == "2011-06-13"
    assert record["matricola"] == "TC010198"
    assert record["tipo"] == "mobile"
    assert record["codice_catastale"] == "B436"


def test_every_sample_row_normalises():
    rows = json.loads(SAMPLE.read_text(encoding="utf-8"))
    records = [normalise_device(r) for r in rows]
    assert len(records) == len(rows)
    assert all(isinstance(r["id"], int) for r in records)
