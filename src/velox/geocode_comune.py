"""Place a fixed camera from its comune and road class.

The fixed-installation PDFs give comune, province, kilometre and direction, but
name the road descriptively ("Milano - Napoli") rather than by reference. Matching
those denominations against OSM route relations does not work: the A1 relation is
not named after its endpoints, and two ["name"~...] filters on one key do not AND.

What does work is the comune. A comune is a few kilometres across, so the ways of
a given class crossing it are a short stretch of one road. Verified 2026-08-13:
Noventa di Piave contains 18 motorway ways, all tagged ref=A4, whose centroid sits
about 1.2 km from the real camera. That yields BOTH the missing reference and a
starting coordinate.

The result is deliberately marked low confidence. It is a good enough starting
point for the one-off human review, and never good enough to fire an 800 m
proximity alert - that gate lives in the app and keys on `verified`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

CACHE_DIR = Path("cache/comuni")

# Which OSM highway classes to look for, by the network the PDF came from.
_HIGHWAY_CLASSES = {
    "autostrada": ["motorway"],
    "ordinaria": ["trunk", "primary"],
}


def cache_key(comune: str, province: str, network: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]", "", comune)
    return f"{safe}_{province}_{network}"


def _build_query(comune: str, network: str) -> str:
    classes = "|".join(_HIGHWAY_CLASSES.get(network, ["trunk", "primary"]))
    escaped = comune.replace('"', '\\"')
    return (
        "[out:json][timeout:90];"
        f'area["boundary"="administrative"]["admin_level"="8"]["name"="{escaped}"]->.c;'
        f'(way["highway"~"^({classes})$"](area.c););'
        "out geom;"
    )


def _consensus_ref(elements: list[dict]) -> str | None:
    """Return the reference only when every matching way agrees.

    Two different refs inside one comune means the comune contains two roads of
    that class, so the row cannot be attributed without guessing.
    """
    refs = set()
    for element in elements:
        raw = (element.get("tags") or {}).get("ref", "").strip()
        if raw:
            refs.add(re.sub(r"\s+", "", raw.split(";")[0].upper()))
    return refs.pop() if len(refs) == 1 else None


def _centroid(elements: list[dict]) -> tuple[float, float] | None:
    points = [
        (node["lon"], node["lat"])
        for element in elements
        for node in (element.get("geometry") or [])
    ]
    if not points:
        return None
    return (
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
    )


def locate(
    comune: str,
    province: str,
    network: str,
    *,
    cache_dir: Path = CACHE_DIR,
    client: Callable[[str], dict] | None = None,
) -> dict | None:
    """Return {"ref": str|None, "lon": float, "lat": float} or None.

    None means OSM had nothing to say; the camera stays unplaced rather than
    being pinned somewhere plausible.
    """
    if not comune or comune == "?" or not province:
        return None

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{cache_key(comune, province, network)}.json"
    if path.exists():
        stored = json.loads(path.read_text())
        return stored or None

    if client is None:
        from velox.overpass import _default_client

        client = _default_client

    elements = client(_build_query(comune, network)).get("elements", [])
    centre = _centroid(elements)
    if centre is None:
        # Do NOT cache a miss: it may be a transient rate-limit dressed as
        # an empty result, and caching it would blind us to this comune forever.
        return None

    result = {"ref": _consensus_ref(elements), "lon": centre[0], "lat": centre[1]}
    path.write_text(json.dumps(result))
    return result
