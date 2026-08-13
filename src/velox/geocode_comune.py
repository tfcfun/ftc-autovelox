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

# Widening steps, tried in order until one returns ways.
_CLASS_LADDER = {
    "autostrada": (["motorway"], ["motorway", "trunk"]),
    "ordinaria": (["trunk", "primary"], ["secondary", "tertiary"]),
}


def _class_ladder(network: str) -> tuple[list[str], ...]:
    return _CLASS_LADDER.get(network, (["trunk", "primary"], ["secondary", "tertiary"]))


def cache_key(comune: str, province: str, network: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]", "", comune)
    return f"{safe}_{province}_{network}"


def _name_pattern(comune: str) -> str:
    """A PREFIX regex matching the comune name as OSM actually spells it.

    Two real failures shaped this, both verified live on 2026-08-13:

    * Apostrophes. The PDFs print U+2019 ("Quarto d'Altino", "Sant'Anastasia");
      OSM uses the straight quote. An exact match returned nothing.
    * Bilingual names. OSM calls Claut "Claut / Cjolt" - Italian and Friulian in
      one name tag. An ANCHORED match therefore finds nothing across all of
      Friuli, Alto Adige (German) and Valle d'Aosta (French). This is systematic,
      not a handful of odd comuni.

    Anchoring only at the start keeps the match cheap and tolerates the
    "Italian / local" form. It is scoped to one province by the caller, so a
    prefix is specific enough.
    """
    escaped = re.escape(comune)
    # re.escape may or may not escape these depending on version; handle both.
    for variant in ("\\’", "’", "\\'", "'", "\\´", "´"):
        escaped = escaped.replace(variant, "APOSTROPHE")
    escaped = escaped.replace("APOSTROPHE", "['’´]")
    return f"^{escaped}"


def _build_query(comune: str, province: str, network: str) -> str:
    return _build_query_for(
        comune, province, _HIGHWAY_CLASSES.get(network, ["trunk", "primary"])
    )


def _build_query_for(comune: str, province: str, highway_classes: list[str]) -> str:
    """Find the comune INSIDE its province, then the roads inside the comune.

    Searching comune names globally is not an option: an unanchored name regex
    over every Italian comune times out with HTTP 504. Scoping to the province
    - which every camera row carries - makes the lookup indexed, fast, and
    immune to two comuni sharing a name in different provinces.
    """
    classes = "|".join(highway_classes)
    pattern = _name_pattern(comune).replace('"', '\\"')
    return (
        "[out:json][timeout:90];"
        f'area["ISO3166-2"="IT-{province}"]["admin_level"="6"]->.prov;'
        f'rel(area.prov)["boundary"="administrative"]["admin_level"="8"]'
        f'["name"~"{pattern}",i];'
        "map_to_area->.c;"
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


def _ways(elements: list[dict], max_points: int = 400) -> list[list[list[float]]]:
    """The road stretches themselves, as [lon, lat] polylines.

    This is the honest representation of what we know. The PDFs give a road, a
    comune and usually a direction, but never a coordinate - so the camera is
    somewhere along these stretches, not at any one point. Keeping the shape
    lets the app show the area of uncertainty instead of a pin that claims a
    precision the source does not contain.
    """
    lines: list[list[list[float]]] = []
    budget = max_points
    for element in elements:
        nodes = element.get("geometry") or []
        if len(nodes) < 2:
            continue
        # Thin long ways rather than dropping them; the shape matters, not every vertex.
        step = max(1, len(nodes) // 40)
        line = [[n["lon"], n["lat"]] for n in nodes[::step]]
        if len(line) < 2:
            continue
        lines.append(line)
        budget -= len(line)
        if budget <= 0:
            break
    return lines


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
    """Return {"ref", "lon", "lat", "ways"} or None.

    "ways" holds the road stretches inside the comune - the area within which the
    camera actually sits. "lon"/"lat" remain as a coarse centre for map framing
    only, never as a claim about where the camera is.

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

    # Try the expected road classes first, then widen. Small comuni carry roads
    # that OSM tags below trunk/primary even when the PDF calls them statali -
    # San Vito al Tagliamento, Spilimbergo, Claut and Erto e Casso all returned
    # nothing on the narrow filter. Widening trades reference precision (more
    # roads means less consensus) for a coordinate, which is the thing we need.
    elements: list[dict] = []
    for classes in _class_ladder(network):
        elements = client(_build_query_for(comune, province, classes)).get("elements", [])
        if elements:
            break

    centre = _centroid(elements)
    if centre is None:
        # Do NOT cache a miss: it may be a transient rate-limit dressed as
        # an empty result, and caching it would blind us to this comune forever.
        return None

    result = {
        "ref": _consensus_ref(elements),
        "lon": centre[0],
        "lat": centre[1],
        "ways": _ways(elements),
    }
    path.write_text(json.dumps(result))
    return result
