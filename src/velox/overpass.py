"""Overpass client for (road ref, province) geometry, with a permanent on-disk cache.

The cache is committed to the repository, so a road is fetched once and never
again. This replaces processing a 2 GB OSM extract and keeps the whole pipeline
runnable on a CI runner.

An empty result returns None and writes nothing: a missing road must stay
missing so it is retried, never cached as "no geometry".
"""

from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Callable

import requests

ENDPOINT = "https://overpass-api.de/api/interpreter"
_SAFE = re.compile(r"[^A-Za-z0-9]")


def cache_key(road_ref: str, province: str) -> str:
    return f"{_SAFE.sub('', road_ref)}_{_SAFE.sub('', province)}"


def _build_query(road_ref: str, province: str) -> str:
    """Match OSM `ref` spellings ("SS 9", "SS9") inside the province boundary.

    Province selection uses an EXACT ISO3166-2 match. This was verified against the
    live API on 2026-08-13: the Provincia di Lodi relation carries
    ISO3166-2="IT-LO", short_name="LO", ref:ISTAT="098" and NO `ref` tag.

    Do not use a regex such as ["ISO3166-2"~"^IT-"] with additional tag filters:
    it forces a scan over every area and returns HTTP 504. The exact match is
    indexed and completes in 7-12 s (measured: SS9/LO 248 ways 7.5 s,
    A7/PV 73 ways 8.2 s, A4/VE 168 ways 12.4 s).
    Selecting by ["ref"="LO"] does NOT work - it returns zero ways.
    """
    prefix = re.match(r"^([A-Z]+)(\d+)$", road_ref)
    if not prefix:
        alternatives = re.escape(road_ref)
    else:
        letters, number = prefix.groups()
        alternatives = f"{letters}\\\\s*{number}"
    return f"""
[out:json][timeout:90];
area["ISO3166-2"="IT-{province}"]["admin_level"="6"]->.prov;
(
  way["highway"]["ref"~"^{alternatives}$"](area.prov);
);
out geom;
""".strip()


def _default_client(query: str, *, tries: int = 5) -> dict:
    """Overpass rate-limits hard. Observed on 2026-08-13: four queries in quick
    succession returned HTTP 429, and a slow query returned 504. Both are
    transient and must be backed off, not treated as "this road has no geometry" —
    caching an empty result would permanently blind the app to that road."""
    last: Exception | None = None
    for attempt in range(tries):
        try:
            response = requests.post(
                ENDPOINT, data={"data": query}, timeout=180,
                headers={"User-Agent": "velox-italia/0.1"},
            )
            if response.status_code in (429, 504):
                raise requests.HTTPError(f"transient {response.status_code}")
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001 - retried, re-raised below
            last = exc
            if attempt < tries - 1:
                time.sleep(25 * (attempt + 1))
    assert last is not None
    raise last


def _haversine_m(a: list[float], b: list[float]) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


def _perpendicular_m(point: list[float], start: list[float], end: list[float]) -> float:
    if start == end:
        return _haversine_m(point, start)
    base = _haversine_m(start, end)
    d1 = _haversine_m(start, point)
    d2 = _haversine_m(end, point)
    s = (base + d1 + d2) / 2
    area_sq = max(s * (s - base) * (s - d1) * (s - d2), 0.0)
    return 2 * math.sqrt(area_sq) / base if base else 0.0


def simplify(points: list[list[float]], tolerance_m: float = 20.0) -> list[list[float]]:
    """Douglas-Peucker with a metric tolerance."""
    if len(points) < 3:
        return list(points)
    worst_index, worst = 0, 0.0
    for i in range(1, len(points) - 1):
        distance = _perpendicular_m(points[i], points[0], points[-1])
        if distance > worst:
            worst_index, worst = i, distance
    if worst <= tolerance_m:
        return [points[0], points[-1]]
    left = simplify(points[: worst_index + 1], tolerance_m)
    right = simplify(points[worst_index:], tolerance_m)
    return left[:-1] + right


def query_road_geometry(
    road_ref: str,
    province: str,
    *,
    cache_dir: Path,
    client: Callable[[str], dict] | None = None,
    pause_s: float = 1.0,
) -> list[list[float]] | None:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{cache_key(road_ref, province)}.json"
    if path.exists():
        return json.loads(path.read_text())

    call = client or _default_client
    payload = call(_build_query(road_ref, province))
    points: list[list[float]] = []
    for element in payload.get("elements", []):
        for node in element.get("geometry") or []:
            points.append([node["lon"], node["lat"]])

    if not points:
        return None

    reduced = simplify(points, tolerance_m=20.0)
    path.write_text(json.dumps(reduced))
    if client is None:
        time.sleep(pause_s)  # be polite to the public Overpass instance
    return reduced
