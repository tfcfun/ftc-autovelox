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
) -> RegionStatus:
    stamp = now or utc_now()
    if parsed_rows > 0:
        return RegionStatus(region, "ok", stamp, parsed_rows, quarantined)
    if previous:
        return RegionStatus(
            region, "stale", previous["updated_at"], int(previous.get("rows", 0)),
            int(previous.get("quarantined", 0)),
        )
    return RegionStatus(region, "failed", stamp, 0, quarantined)


def _write_json(path: Path, value) -> tuple[str, int]:
    body = json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True)
    path.write_text(body, encoding="utf-8")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    count = len(value) if isinstance(value, list) else 1
    return digest, count


def write_snapshot(root: Path, week: str, payload: dict) -> Path:
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
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    files: dict[str, dict] = {}
    for key in _PAYLOAD_FILES:
        digest, count = _write_json(target / f"{key}.json", payload.get(key, []))
        files[f"{key}.json"] = {"sha256": digest, "count": count}

    index = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "week": week,
        "files": files,
        "regions": payload.get("regions", {}),
        "sources": payload.get("sources", {}),
        "quarantine_count": len(payload.get("quarantine", [])),
    }
    (target / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
    )

    latest = root / "latest"
    if latest.exists():
        shutil.rmtree(latest)
    shutil.copytree(target, latest)
    return target


def region_statuses_to_dict(statuses: list[RegionStatus]) -> dict:
    return {
        s.region: {k: v for k, v in asdict(s).items() if k != "region"}
        for s in statuses
    }
