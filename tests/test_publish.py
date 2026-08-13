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

    index = json.loads((written / "index.json").read_text())
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
