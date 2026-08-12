"""One bad road must not sink the weekly run.

The ingest is a scheduled job with no operator watching. If a single Overpass
lookup exhausting its retries aborts the whole run, one flaky road silently
costs a week of data - and the failure looks identical to "nothing was
published", which is the exact confusion this pipeline exists to avoid.
"""

from velox.cli import _road_slug, build_mobile_records
from velox.geocode_fixed import geocode_stub
from velox.parse_fixed import FixedCamera
from velox.parse_mobile import MobileCheck


def _camera(**overrides) -> FixedCamera:
    base = dict(
        network="ordinaria", region="Campania", road_name="Del Vesuvio", road_ref=None,
        km_raw="11+500", km=11.5, direction_raw="Sud", bearing_deg=180,
        comune="Nola", province="NA",
    )
    base.update(overrides)
    return FixedCamera(**base)


def _check(**overrides) -> MobileCheck:
    base = dict(
        date="2026-08-12", region="Emilia", road_type="Strada Statale",
        road_ref=None, road_name=None, province="RE",
    )
    base.update(overrides)
    return MobileCheck(**base)


def test_stub_publishes_the_camera_without_placing_it():
    record = geocode_stub(_camera())
    assert record["lat"] is None and record["lon"] is None
    assert record["geocode_method"] == "failed"
    assert record["geocode_confidence"] == "none"
    assert record["verified"] is False
    # It is still a real installation and must carry its identifying detail.
    assert record["comune"] == "Nola"
    assert record["km_raw"] == "11+500"


def test_two_unnamed_checks_in_one_province_on_one_day_get_distinct_ids():
    """The real Emilia PDF produced exactly this collision on 2026-08-12 and
    the publication gate correctly refused to publish."""
    records = build_mobile_records([_check(), _check()], week="2026-W33", segment_ids=set())
    ids = [r["id"] for r in records]
    assert len(set(ids)) == 2, f"ids collided: {ids}"
    assert ids[1].endswith("-2")


def test_road_name_disambiguates_before_an_ordinal_is_needed():
    records = build_mobile_records(
        [_check(road_name="Via Emilia"), _check(road_name="Tangenziale")],
        week="2026-W33", segment_ids=set(),
    )
    ids = [r["id"] for r in records]
    assert len(set(ids)) == 2
    assert not any(i.endswith("-2") for i in ids), "names should distinguish without an ordinal"


def test_slug_is_filesystem_safe_and_bounded():
    slug = _road_slug(_check(road_name="Strada  della/Val d'Esino (tratto lungo)"))
    assert slug.isalnum()
    assert len(slug) <= 16


def test_slug_falls_back_when_there_is_nothing_to_slug():
    assert _road_slug(_check(road_ref=None, road_name=None)) == "NA"
    assert _road_slug(_check(road_ref=None, road_name="///")) == "NA"


def test_ref_is_preferred_over_name_for_the_slug():
    assert _road_slug(_check(road_ref="SS9", road_name="via Emilia")) == "SS9"
