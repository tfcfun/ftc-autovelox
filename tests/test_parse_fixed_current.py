"""Golden tests against the CURRENT edition of the motorway fixed-installation list.

The fixtures in fixtures/2026-W33/ are the 26/08/2021 edition, which is what was
captured when the project started. On 2026-08-13 the live page was found to serve
mvpostazionefissaaut_07102025.pdf instead — a newer edition that adds one camera
(Lucca, km 71+000) and shifts the merged-cell centring.

Testing only the old edition would leave the parser unguarded against exactly the
thing most likely to break it: a change in the file it actually downloads. Both
editions are therefore kept and both are asserted.

The ordinary-roads list is byte-identical to the 2026-W33 fixture and is not
duplicated here.
"""

from pathlib import Path

from velox.parse_fixed import parse_fixed
from velox.parse_mobile import pdf_to_text

CURRENT = Path(__file__).parent.parent / "fixtures" / "current"
LEGACY = Path(__file__).parent.parent / "fixtures" / "2026-W33"


def _cameras(path: Path):
    return parse_fixed("autostrada", pdf_to_text(path.read_bytes()))


def test_current_edition_yields_every_kilometre_row():
    result = _cameras(CURRENT / "mvpostazionefissaaut_07102025.pdf")
    assert len(result.cameras) == 26
    # The Frejus tunnel row still has free text where its kilometre should be.
    assert any("galleria" in q["raw"].lower() for q in result.quarantine)


def test_current_edition_contains_the_row_added_since_2021():
    result = _cameras(CURRENT / "mvpostazionefissaaut_07102025.pdf")
    lucca = [c for c in result.cameras if c.comune == "Lucca"]
    assert len(lucca) == 1, "the 07/10/2025 edition adds a camera at Lucca"
    camera = lucca[0]
    assert camera.km_raw == "71+000"
    assert camera.km == 71.0
    assert camera.province == "LU"
    assert camera.direction_raw == "Est"
    assert camera.bearing_deg == 90


def test_rows_common_to_both_editions_parse_identically():
    current = {
        (c.km_raw, c.comune, c.province, c.direction_raw)
        for c in _cameras(CURRENT / "mvpostazionefissaaut_07102025.pdf").cameras
    }
    legacy = {
        (c.km_raw, c.comune, c.province, c.direction_raw)
        for c in _cameras(LEGACY / "fisse_auto.pdf").cameras
    }
    # The newer edition is a superset: nothing was removed, one row was added.
    assert legacy - current == set(), f"rows lost in the newer edition: {legacy - current}"
    assert len(current - legacy) == 1


def test_no_duplicate_physical_installations_in_either_edition():
    for path in (CURRENT / "mvpostazionefissaaut_07102025.pdf", LEGACY / "fisse_auto.pdf"):
        keys = [
            (c.road_name, c.km_raw, c.direction_raw, c.comune, c.province)
            for c in _cameras(path).cameras
        ]
        assert len(keys) == len(set(keys)), f"duplicate rows in {path.name}"
