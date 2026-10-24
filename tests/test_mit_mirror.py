"""The MIT register is reachable only from Italian addresses since 2026-10-24
(check-host: it2 OK, every de/us/fr/gb/es/nl node timed out), so the GitHub
runner can no longer read it. A machine in Italy mirrors it into the repo;
the ingest falls back to the freshest copy it has, never to a guess."""

import json

import pytest

from velox.cli import mit_devices_or_previous
from velox.mit import read_mirror, write_mirror


def _down():
    raise ConnectionError("connect timeout")


def _publish_previous(root, devices, fetched_at):
    latest = root / "latest"
    latest.mkdir(parents=True)
    (latest / "mit_devices.json").write_text(json.dumps(devices), encoding="utf-8")
    (latest / "index.json").write_text(json.dumps(
        {"sources": {"mit": {"fetched_at": fetched_at, "count": len(devices)}}}),
        encoding="utf-8")


def test_mirror_round_trips(tmp_path):
    path = tmp_path / "devices.json"
    assert write_mirror(path, [{"id": 1}], "2026-10-24T05:00:00Z") is True
    assert read_mirror(path) == ([{"id": 1}], "2026-10-24T05:00:00Z")


def test_rewriting_the_same_register_reports_no_change(tmp_path):
    path = tmp_path / "devices.json"
    write_mirror(path, [{"id": 1}], "2026-10-24T05:00:00Z")
    # Same devices, a later clock: nothing to commit, and the file keeps the
    # date it was first read, so a daily job does not commit 1.7 MB for nothing.
    assert write_mirror(path, [{"id": 1}], "2026-10-25T05:00:00Z") is False
    assert read_mirror(path)[1] == "2026-10-24T05:00:00Z"


def test_an_empty_register_is_never_mirrored(tmp_path):
    with pytest.raises(ValueError):
        write_mirror(tmp_path / "devices.json", [], "2026-10-24T05:00:00Z")


def test_missing_or_damaged_mirror_reads_as_absent(tmp_path):
    assert read_mirror(tmp_path / "nope.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert read_mirror(bad) is None
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"fetched_at": "x", "devices": []}), encoding="utf-8")
    assert read_mirror(empty) is None


def test_outage_prefers_a_newer_mirror_over_the_published_copy(tmp_path):
    _publish_previous(tmp_path / "data", [{"id": 1}], "2026-10-23T12:29:46Z")
    mirror = tmp_path / "devices.json"
    write_mirror(mirror, [{"id": 1}, {"id": 2}], "2026-10-25T04:30:00Z")
    devices, source = mit_devices_or_previous(tmp_path / "data", fetcher=_down, mirror=mirror)
    assert devices == [{"id": 1}, {"id": 2}]
    assert source == {"fetched_at": "2026-10-25T04:30:00Z", "count": 2, "via": "mirror"}


def test_outage_keeps_the_published_copy_when_the_mirror_is_older(tmp_path):
    _publish_previous(tmp_path / "data", [{"id": 1}], "2026-10-23T12:29:46Z")
    mirror = tmp_path / "devices.json"
    write_mirror(mirror, [{"id": 7}], "2026-10-01T04:30:00Z")
    devices, source = mit_devices_or_previous(tmp_path / "data", fetcher=_down, mirror=mirror)
    assert devices == [{"id": 1}]
    assert source["fetched_at"] == "2026-10-23T12:29:46Z"


def test_outage_with_only_a_mirror_uses_it(tmp_path):
    mirror = tmp_path / "devices.json"
    write_mirror(mirror, [{"id": 3}], "2026-10-25T04:30:00Z")
    devices, _ = mit_devices_or_previous(tmp_path / "data", fetcher=_down, mirror=mirror)
    assert devices == [{"id": 3}]
