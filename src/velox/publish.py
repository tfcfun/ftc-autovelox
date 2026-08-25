"""Publication gates and the snapshot writer.

The governing rule of this pipeline lives here: a region that parses to zero
rows does not publish. An empty parse and a genuinely quiet week are
indistinguishable downstream, so emptiness is never allowed to reach a phone as
an all-clear. A region with history goes stale; a region without history fails.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import NamedTuple

from velox.constants import SCHEMA_VERSION
from velox.fetch import utc_now

_REQUIRED_NON_EMPTY = ("fixed_cameras", "mit_devices")
_PAYLOAD_FILES = ("fixed_cameras", "mobile_checks", "road_segments", "mit_devices",
                  "quarantine")


class PublicationBlocked(RuntimeError):
    """A whole-snapshot invariant failed; nothing is written."""


@dataclass(frozen=True)
class RegionStatus:
    region: str
    status: str
    updated_at: str
    rows: int
    quarantined: int


def decide_region_status(
    region: str,
    parsed_rows: int,
    previous: dict | None,
    quarantined: int = 0,
    now: str | None = None,
    confirmed_empty: bool = False,
) -> RegionStatus:
    """Four outcomes, and the difference between the last two is the point.

    ok      - rows were published
    empty   - the document was read and states there are no checks this week
    stale   - nothing parsed, but a previous good week is being retained
    failed  - nothing parsed and nothing to fall back on: we do not know

    'empty' is information the police published. 'failed' is our ignorance.
    Collapsing them would let a broken feed look like a quiet week.
    """
    stamp = now or utc_now()
    if parsed_rows > 0:
        return RegionStatus(region, "ok", stamp, parsed_rows, quarantined)
    if confirmed_empty:
        return RegionStatus(region, "empty", stamp, 0, quarantined)
    if previous:
        return RegionStatus(
            region, "stale", previous["updated_at"], int(previous.get("rows", 0)),
            int(previous.get("quarantined", 0)),
        )
    return RegionStatus(region, "failed", stamp, 0, quarantined)


class SnapshotResult(NamedTuple):
    """Where the snapshot lives, and whether this run actually changed it."""

    path: Path
    changed: bool


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True)


def _substance(index: dict, bodies: dict) -> str:
    """What this snapshot SAYS, with the clocks taken out.

    generated_at, a region's updated_at and every fetched_at move on each run
    even when the Polizia republished nothing, and they feed the sha256 digests
    in index.json - so comparing raw bytes always reports a change. Monday
    2026-08-24 committed nine times with byte-different, word-identical content.
    """
    trimmed = json.loads(_dump(index))
    trimmed.pop("generated_at", None)
    # Digests are derived from the bodies, which are compared here directly.
    trimmed.pop("files", None)
    for region in trimmed.get("regions", {}).values():
        if isinstance(region, dict):
            region.pop("updated_at", None)
    for source in trimmed.get("sources", {}).values():
        if isinstance(source, dict):
            source.pop("fetched_at", None)

    def without_clocks(rows):
        if not isinstance(rows, list):
            return rows
        return [{k: v for k, v in row.items() if k != "fetched_at"}
                if isinstance(row, dict) else row for row in rows]

    return _dump({"index": trimmed,
                  "files": {k: without_clocks(v) for k, v in bodies.items()}})


def _substance_on_disk(folder: Path) -> str | None:
    """The same reading, taken from an already-published snapshot.

    Anything missing or unreadable returns None, which never compares equal, so
    a damaged snapshot is republished rather than silently kept.
    """
    index_path = folder / "index.json"
    if not index_path.exists():
        return None
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        bodies = {}
        for key in _PAYLOAD_FILES:
            path = folder / f"{key}.json"
            if not path.exists():
                return None
            bodies[key] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return _substance(index, bodies)


def write_snapshot(root: Path, week: str, payload: dict) -> SnapshotResult:
    for key in _REQUIRED_NON_EMPTY:
        if not payload.get(key):
            raise PublicationBlocked(f"refusing to publish: {key} is empty")

    # Duplicate ids break Identifiable lists in the app and would show the same
    # camera twice on the map. The ordinary-roads PDF really does contain a
    # duplicated row, so this is a live risk, not a theoretical one.
    for key in ("fixed_cameras", "mobile_checks", "road_segments"):
        ids = [row["id"] for row in payload.get(key, []) if "id" in row]
        if len(ids) != len(set(ids)):
            duplicates = sorted({i for i in ids if ids.count(i) > 1})
            raise PublicationBlocked(
                f"refusing to publish: duplicate ids in {key}: {duplicates[:5]}"
            )

    root = Path(root)
    target = root / week
    latest = root / "latest"

    bodies = {key: payload.get(key, []) for key in _PAYLOAD_FILES}
    index = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "week": week,
        "files": {},
        "regions": payload.get("regions", {}),
        "sources": payload.get("sources", {}),
        "quarantine_count": len(payload.get("quarantine", [])),
    }

    # A run that read the same programme has nothing to publish. Rewriting it
    # would only restamp the clocks - and generated_at reaches the user as
    # "Elenco pubblicato il ...", so advancing it would claim a publication
    # that never happened. Both copies must already agree, or latest could be
    # left pointing at another week.
    substance = _substance(index, bodies)
    if (_substance_on_disk(target) == substance
            and _substance_on_disk(latest) == substance):
        return SnapshotResult(target, False)

    rendered = {key: _dump(body) for key, body in bodies.items()}
    index["files"] = {
        f"{key}.json": {
            "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "count": len(bodies[key]) if isinstance(bodies[key], list) else 1,
        }
        for key, body in rendered.items()
    }

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for key, body in rendered.items():
        (target / f"{key}.json").write_text(body, encoding="utf-8")
    (target / "index.json").write_text(_dump(index), encoding="utf-8")

    if latest.exists():
        shutil.rmtree(latest)
    shutil.copytree(target, latest)
    return SnapshotResult(target, True)


def region_statuses_to_dict(statuses: list[RegionStatus]) -> dict:
    return {
        s.region: {k: v for k, v in asdict(s).items() if k != "region"}
        for s in statuses
    }
