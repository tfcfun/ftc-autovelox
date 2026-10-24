"""Pipeline orchestration.

Run: python -m velox.cli ingest --root data
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from velox.constants import REGIONS
from velox.fetch import fetch, utc_now
from velox.geocode_fixed import geocode, geocode_stub
from velox.mit import MIRROR as MIT_MIRROR
from velox.mit import fetch_devices, read_mirror, write_mirror
from velox.overpass import cache_key, query_road_geometry
from velox.parse_fixed import parse_fixed
from velox.parse_mobile import MobileCheck, parse_mobile, pdf_to_text
from velox.publish import decide_region_status, region_statuses_to_dict, write_snapshot
from velox.sources import resolve_sources

SOURCE_PAGE = "https://www.poliziadistato.it/articolo/autovelox-e-tutor-dove-sono"
CACHE_DIR = Path("cache/segments")


def iso_week(iso_date: str) -> str:
    year, week, _ = date.fromisoformat(iso_date).isocalendar()
    return f"{year}-W{week:02d}"


def deduplicate_cameras(cameras: list[dict]) -> tuple[list[dict], int]:
    """Collapse records that describe the same physical installation.

    The official ordinary-roads PDF really does print the Potenza-Melfi km 2+600
    row twice: once unlabelled inside the Campania block and once under
    Basilicata (verified 2026-08-13, lines 82 and 99 of the extracted text). The
    parser is right to emit both — it reports what the source says — but two
    records that geocode to one point would produce two identical pins, two
    identical alerts, and a duplicate `id`, which breaks SwiftUI's Identifiable
    lists in the app.

    Identity is the physical installation: network, road, kilometre, direction,
    comune, province. Region is deliberately NOT part of the key, because the
    duplicate rows differ only by the region the PDF filed them under.
    """
    seen: dict[tuple, dict] = {}
    dropped = 0
    for camera in cameras:
        key = (
            camera["network"], camera["road_name"], camera["km_raw"],
            camera["direction_raw"], camera["comune"], camera["province"],
        )
        if key in seen:
            dropped += 1
            continue
        seen[key] = camera
    return list(seen.values()), dropped


def _road_slug(check: MobileCheck) -> str:
    """A stable, filesystem-safe token identifying the road of a check.

    Falls back to the descriptive name when no reference parsed. Two checks in
    one province on one day with no reference and no name would otherwise share
    an id - which is exactly what happened in Reggio Emilia on 2026-08-12.
    """
    source = check.road_ref or check.road_name or "NA"
    slug = re.sub(r"[^A-Za-z0-9]", "", source)[:16]
    return slug or "NA"


def build_mobile_records(
    checks: list[MobileCheck], *, week: str, segment_ids: set[str]
) -> list[dict]:
    records = []
    used: dict[str, int] = {}
    for check in checks:
        key = cache_key(check.road_ref, check.province) if check.road_ref else None
        base = (f"mb-{week.replace('-', '')}-{check.province}-"
                f"{_road_slug(check)}-{check.date}")
        # Last-resort de-collision. Two genuinely identical rows can appear in one
        # regional PDF; they still need distinct ids or the app's list breaks.
        # An ordinal suffix is used rather than '#', which reads as a fragment.
        used[base] = used.get(base, 0) + 1
        identifier = base if used[base] == 1 else f"{base}-{used[base]}"
        records.append(
            {
                "id": identifier,
                "date": check.date,
                "week": week,
                "region": check.region,
                "road_type": check.road_type,
                "road_ref": check.road_ref,
                "road_name": check.road_name,
                "province": check.province,
                "segment_id": f"seg-{check.road_ref}-{check.province}"
                if key and key in segment_ids else None,
            }
        )
    return records


def _previous_regions(root: Path) -> dict:
    index = root / "latest" / "index.json"
    if not index.exists():
        return {}
    return json.loads(index.read_text()).get("regions", {})


def _published_mit(root: Path) -> tuple[list[dict], dict] | None:
    latest = root / "latest"
    try:
        devices = json.loads((latest / "mit_devices.json").read_text(encoding="utf-8"))
        source = json.loads((latest / "index.json").read_text(encoding="utf-8"))
        source = dict(source["sources"]["mit"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not devices or not source.get("fetched_at"):
        return None
    source["count"] = len(devices)
    return devices, source


def mit_devices_or_previous(
    root: Path, *, fetcher=fetch_devices, mirror: Path = MIT_MIRROR
) -> tuple[list[dict], dict]:
    """The MIT register, or the freshest copy we hold when it cannot be read.

    The register only feeds the fine check, and it changes slowly; failing to
    read velox.mit.gov.it must not throw away a run that already holds the
    Polizia programme (2026-10-24 died exactly so). Since that day the MIT
    answers Italian addresses only, so the runner relies on the copy a machine
    in Italy mirrors into the repo, or else on the last published one. Either
    keeps the date the register was really read. With neither, the failure stands.
    """
    try:
        devices = fetcher()
    except Exception as exc:  # noqa: BLE001 - degrade to a held copy, or re-raise
        candidates = []
        published = _published_mit(root)
        if published:
            candidates.append(published)
        mirrored = read_mirror(mirror)
        if mirrored:
            candidates.append((mirrored[0], {"fetched_at": mirrored[1],
                                             "count": len(mirrored[0]), "via": "mirror"}))
        if not candidates:
            raise
        # ISO-8601 UTC stamps sort as text; on a tie the published copy wins,
        # so a run that read nothing new rewrites nothing.
        devices, source = max(candidates, key=lambda c: c[1]["fetched_at"])
        print(f"MIT register FAILED ({exc}); using the copy read at "
              f"{source['fetched_at']}{' (mirror)' if source.get('via') else ''}",
              file=sys.stderr)
        return devices, source
    return devices, {"fetched_at": utc_now(), "count": len(devices)}


def mirror_mit(path: Path) -> int:
    """Run on a machine in Italy: refresh the committed copy of the register."""
    devices = fetch_devices()
    changed = write_mirror(path, devices, utc_now())
    print(f"{path}: {len(devices)} devices, {'changed' if changed else 'unchanged'}",
          file=sys.stderr)
    return 0


def ingest(root: Path) -> int:
    root = Path(root)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    previous = _previous_regions(root)

    page = fetch(SOURCE_PAGE)
    links = resolve_sources(page.content.decode("utf-8", errors="replace"))
    print(f"resolved {len(links.regional)} regional PDFs", file=sys.stderr)

    all_checks: list[MobileCheck] = []
    quarantine: list[dict] = []
    statuses = []
    valid_from = valid_to = None

    for region in REGIONS:
        try:
            document = fetch(links.regional[region])
            parsed = parse_mobile(region, pdf_to_text(document.content))
        except Exception as exc:  # noqa: BLE001 - one region must not sink the run
            print(f"{region}: FAILED {exc}", file=sys.stderr)
            statuses.append(decide_region_status(region, 0, previous.get(region)))
            continue

        valid_from = valid_from or parsed.valid_from
        valid_to = valid_to or parsed.valid_to
        quarantine.extend(parsed.quarantine)
        statuses.append(
            decide_region_status(region, len(parsed.checks), previous.get(region),
                                 quarantined=len(parsed.quarantine),
                                 confirmed_empty=parsed.confirmed_empty)
        )
        if parsed.checks:
            all_checks.extend(parsed.checks)
        print(f"{region}: {len(parsed.checks)} checks, "
              f"{len(parsed.quarantine)} quarantined", file=sys.stderr)

    cameras: list[dict] = []
    for network, url in (("autostrada", links.fixed_auto), ("ordinaria", links.fixed_ord)):
        document = fetch(url)
        parsed = parse_fixed(network, pdf_to_text(document.content))
        quarantine.extend(parsed.quarantine)
        # The fixed PDFs print denominations ("Milano - Napoli"), never refs.
        # Resolve each denomination to an OSM ref before geocoding, or the whole
        # precise layer of the map stays empty.
        for camera in parsed.cameras:
            # One unlucky road must not sink the whole weekly run. A camera that
            # cannot be geocoded is still published, simply without coordinates.
            try:
                cameras.append(geocode(camera, cache_dir=CACHE_DIR))
            except Exception as exc:  # noqa: BLE001 - degrade, do not abort
                print(f"geocode failed for {camera.comune} {camera.province}: {exc}",
                      file=sys.stderr)
                cameras.append(geocode_stub(camera))
        print(f"fixed/{network}: {len(parsed.cameras)} cameras", file=sys.stderr)

    cameras, duplicates = deduplicate_cameras(cameras)
    if duplicates:
        print(f"collapsed {duplicates} duplicate camera row(s)", file=sys.stderr)

    segments: list[dict] = []
    segment_ids: set[str] = set()
    pairs = {(c.road_ref, c.province) for c in all_checks if c.road_ref}
    for ref, province in sorted(pairs):
        try:
            geometry = query_road_geometry(ref, province, cache_dir=CACHE_DIR)
        except Exception as exc:  # noqa: BLE001 - degrade, do not abort
            print(f"geometry lookup failed for {ref} {province}: {exc}", file=sys.stderr)
            geometry = None
        if not geometry:
            print(f"no geometry for {ref} {province}", file=sys.stderr)
            continue
        segment_ids.add(cache_key(ref, province))
        segments.append(
            {"id": f"seg-{ref}-{province}", "road_ref": ref, "province": province,
             "geometry": geometry, "source": "overpass", "fetched_at": utc_now()}
        )

    devices, mit_source = mit_devices_or_previous(root)
    week = iso_week(valid_from or date.today().isoformat())

    payload = {
        "fixed_cameras": cameras,
        "mobile_checks": build_mobile_records(all_checks, week=week,
                                              segment_ids=segment_ids),
        "road_segments": segments,
        "mit_devices": devices,
        "quarantine": quarantine,
        "regions": region_statuses_to_dict(statuses),
        "sources": {
            "polizia_mobile": {"fetched_at": utc_now(), "valid_from": valid_from,
                               "valid_to": valid_to},
            "polizia_fixed_auto": {"url": links.fixed_auto, "fetched_at": utc_now()},
            "polizia_fixed_ord": {"url": links.fixed_ord, "fetched_at": utc_now()},
            "mit": mit_source,
        },
    }

    result = write_snapshot(root, week, payload)
    if result.changed:
        print(f"wrote {result.path}", file=sys.stderr)
    else:
        # Say so plainly: a silent "wrote" on a run that changed nothing is how
        # nine identical commits looked like nine publications.
        print(f"{result.path} already current, nothing rewritten", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="velox")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest_cmd = sub.add_parser("ingest")
    ingest_cmd.add_argument("--root", default="data")
    mirror_cmd = sub.add_parser("mirror-mit")
    mirror_cmd.add_argument("--path", default=str(MIT_MIRROR))
    args = parser.parse_args()
    if args.command == "ingest":
        return ingest(Path(args.root))
    if args.command == "mirror-mit":
        return mirror_mit(Path(args.path))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
