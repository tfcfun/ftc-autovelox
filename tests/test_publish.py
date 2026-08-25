import json
from pathlib import Path

import pytest

from velox.publish import (
    PublicationBlocked,
    decide_region_status,
    write_snapshot,
)


def test_zero_rows_never_publishes_and_retains_last_good():
    previous = {"status": "ok", "updated_at": "2026-08-06T06:00:00Z", "rows": 5,
                "quarantined": 0}
    status = decide_region_status("Sicilia", parsed_rows=0, previous=previous)
    assert status.status == "stale"
    assert status.updated_at == "2026-08-06T06:00:00Z"
    assert status.rows == 5


def test_zero_rows_with_no_history_is_failed_not_ok():
    status = decide_region_status("Molise", parsed_rows=0, previous=None)
    assert status.status == "failed"
    assert status.rows == 0


def test_rows_present_publishes_ok():
    status = decide_region_status("Lombardia", parsed_rows=3, previous=None,
                                  quarantined=0, now="2026-08-13T06:00:00Z")
    assert status.status == "ok"
    assert status.rows == 3
    assert status.updated_at == "2026-08-13T06:00:00Z"


def test_snapshot_refuses_to_publish_with_no_fixed_cameras():
    payload = {"fixed_cameras": [], "mobile_checks": [{"x": 1}], "road_segments": [],
               "mit_devices": [{"id": 1}], "quarantine": [], "regions": {}}
    with pytest.raises(PublicationBlocked, match="fixed_cameras"):
        write_snapshot(Path("/tmp/velox-test-a"), "2026-W33", payload)


def test_snapshot_refuses_to_publish_with_no_mit_devices():
    payload = {"fixed_cameras": [{"id": "a"}], "mobile_checks": [], "road_segments": [],
               "mit_devices": [], "quarantine": [], "regions": {}}
    with pytest.raises(PublicationBlocked, match="mit_devices"):
        write_snapshot(Path("/tmp/velox-test-b"), "2026-W33", payload)


def test_snapshot_refuses_duplicate_ids():
    payload = {
        "fixed_cameras": [{"id": "fx-1"}, {"id": "fx-1"}],
        "mobile_checks": [], "road_segments": [], "mit_devices": [{"id": 1}],
        "quarantine": [], "regions": {},
    }
    with pytest.raises(PublicationBlocked, match="duplicate ids"):
        write_snapshot(Path("/tmp/velox-test-c"), "2026-W33", payload)


def test_snapshot_writes_files_index_and_latest(tmp_path):
    payload = {
        "fixed_cameras": [{"id": "fx-1", "lat": 45.0, "lon": 9.0}],
        "mobile_checks": [{"id": "mb-1"}],
        "road_segments": [{"id": "seg-1"}],
        "mit_devices": [{"id": 1}],
        "quarantine": [],
        "regions": {"Lombardia": {"status": "ok", "updated_at": "2026-08-13T06:00:00Z",
                                  "rows": 3, "quarantined": 0}},
        "sources": {},
    }
    written = write_snapshot(tmp_path, "2026-W33", payload)
    assert written.changed is True

    index = json.loads((written.path / "index.json").read_text())
    assert index["schema_version"] == 1
    assert index["week"] == "2026-W33"
    assert index["files"]["fixed_cameras.json"]["count"] == 1
    assert len(index["files"]["fixed_cameras.json"]["sha256"]) == 64

    latest = tmp_path / "latest"
    assert json.loads((latest / "index.json").read_text())["week"] == "2026-W33"
    assert (latest / "mit_devices.json").exists()


def test_latest_is_replaced_not_merged(tmp_path):
    base = {"fixed_cameras": [{"id": "fx-1"}], "mobile_checks": [], "road_segments": [],
            "mit_devices": [{"id": 1}], "quarantine": [], "regions": {}, "sources": {}}
    write_snapshot(tmp_path, "2026-W33", base)
    stale_marker = tmp_path / "latest" / "stale_marker.json"
    stale_marker.write_text("{}")
    write_snapshot(tmp_path, "2026-W34", base)
    assert not stale_marker.exists()


def test_a_region_that_publishes_a_zero_is_empty_not_failed():
    """Molise publishes 'Servizi di controllo velocita non programmati nella
    settimana'. That is information, not a failure to read."""
    status = decide_region_status("Molise", parsed_rows=0, previous=None,
                                  confirmed_empty=True, now="2026-08-13T06:00:00Z")
    assert status.status == "empty"
    assert status.rows == 0


def test_an_unreadable_region_with_no_history_is_still_failed():
    status = decide_region_status("Sicilia", parsed_rows=0, previous=None,
                                  confirmed_empty=False)
    assert status.status == "failed"


def test_a_confirmed_zero_does_not_resurrect_last_week_as_stale():
    """A region that says 'none this week' must show this week's zero, not
    last week's rows dressed up as current."""
    previous = {"status": "ok", "updated_at": "2026-08-06T06:00:00Z", "rows": 5,
                "quarantined": 0}
    status = decide_region_status("Molise", parsed_rows=0, previous=previous,
                                  confirmed_empty=True, now="2026-08-13T06:00:00Z")
    assert status.status == "empty"
    assert status.rows == 0
    assert status.updated_at == "2026-08-13T06:00:00Z"


def _steady_payload(fetched_at: str, updated_at: str, checks=None) -> dict:
    """A snapshot where only the clocks differ between runs."""
    return {
        "fixed_cameras": [{"id": "fx-1", "lat": 45.0, "lon": 9.0}],
        "mobile_checks": checks if checks is not None else [{"id": "mb-1", "day": "2026-08-26"}],
        "road_segments": [{"id": "seg-1", "road_ref": "A7", "fetched_at": fetched_at}],
        "mit_devices": [{"id": 1}],
        "quarantine": [],
        "regions": {"Lombardia": {"status": "ok", "updated_at": updated_at,
                                  "rows": 1, "quarantined": 0}},
        "sources": {"polizia_mobile": {"fetched_at": fetched_at,
                                       "valid_from": "2026-08-24",
                                       "valid_to": "2026-08-30"}},
    }


def _tree(folder: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(folder.iterdir())}


def test_rerun_with_the_same_programme_rewrites_nothing(tmp_path):
    """A rerun that reads the same programme must leave the bytes alone.

    Every run stamps generated_at / updated_at / fetched_at, and those feed the
    sha256 digests in index.json, so an unchanged week still produced a diff and
    the workflow's `no change to publish` guard could never fire. Monday
    2026-08-24 committed nine times with identical content.
    """
    first = write_snapshot(tmp_path, "2026-W35",
                           _steady_payload("2026-08-24T06:00:00Z", "2026-08-24T06:00:00Z"))
    assert first.changed is True
    before = _tree(tmp_path / "2026-W35")

    later = write_snapshot(tmp_path, "2026-W35",
                           _steady_payload("2026-08-24T16:00:00Z", "2026-08-24T16:00:00Z"))

    assert later.changed is False, "only the clocks moved; there is nothing to publish"
    assert _tree(tmp_path / "2026-W35") == before, "rewrote bytes with no new information"
    assert _tree(tmp_path / "latest") == before


def test_publication_date_is_not_advanced_by_a_rerun(tmp_path, monkeypatch):
    """generated_at reaches the user as 'Elenco pubblicato il ...'.

    Restamping it on a run that republished nothing would claim a publication
    that never happened. The clock is driven explicitly here: utc_now() has
    second resolution, so two writes in the same test would otherwise agree by
    accident and the test would pass without proving anything.
    """
    monkeypatch.setattr("velox.publish.utc_now", lambda: "2026-08-24T06:42:00Z")
    write_snapshot(tmp_path, "2026-W35",
                   _steady_payload("2026-08-24T06:00:00Z", "2026-08-24T06:00:00Z"))
    published = json.loads((tmp_path / "2026-W35" / "index.json").read_text())["generated_at"]
    assert published == "2026-08-24T06:42:00Z"

    monkeypatch.setattr("velox.publish.utc_now", lambda: "2026-08-25T07:44:00Z")
    write_snapshot(tmp_path, "2026-W35",
                   _steady_payload("2026-08-25T07:00:00Z", "2026-08-25T07:00:00Z"))
    after = json.loads((tmp_path / "2026-W35" / "index.json").read_text())["generated_at"]

    assert after == published, "claimed a publication date for a run that published nothing"


def test_a_real_change_still_publishes(tmp_path):
    """The guard must not swallow an actual change to the programme."""
    write_snapshot(tmp_path, "2026-W35",
                   _steady_payload("2026-08-24T06:00:00Z", "2026-08-24T06:00:00Z"))

    result = write_snapshot(
        tmp_path, "2026-W35",
        _steady_payload("2026-08-25T07:00:00Z", "2026-08-25T07:00:00Z",
                        checks=[{"id": "mb-1", "day": "2026-08-26"},
                                {"id": "mb-2", "day": "2026-08-27"}]),
    )

    assert result.changed is True
    index = json.loads((tmp_path / "2026-W35" / "index.json").read_text())
    assert index["files"]["mobile_checks.json"]["count"] == 2
    assert json.loads((tmp_path / "latest" / "index.json").read_text())[
        "files"]["mobile_checks.json"]["count"] == 2


def test_a_new_week_always_publishes(tmp_path):
    write_snapshot(tmp_path, "2026-W35",
                   _steady_payload("2026-08-24T06:00:00Z", "2026-08-24T06:00:00Z"))
    result = write_snapshot(tmp_path, "2026-W36",
                            _steady_payload("2026-08-31T06:00:00Z", "2026-08-31T06:00:00Z"))
    assert result.changed is True
    assert json.loads((tmp_path / "latest" / "index.json").read_text())["week"] == "2026-W36"
