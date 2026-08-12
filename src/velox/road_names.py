"""Resolve the descriptive road names used by the Polizia PDFs to OSM refs.

The fixed-installation PDFs never print a road reference. They print the official
denomination: "Milano - Napoli", "Torino - Trieste", "Appia", "Del Vesuvio".
Geocoding needs a ref ("A1", "A4", "SS7", "SS268"), because that is what OSM tags
the ways with and what `overpass.query_road_geometry` selects on.

The mapping is NOT hardcoded from memory. A wrong name-to-ref pairing would place
a camera on the wrong motorway - a confidently wrong pin, which is worse than no
pin at all. Instead each name is resolved by asking OSM for the route relation
that carries it, and the answer is cached in a committed JSON file that a human
can read and correct.

Unresolved names stay unresolved. The camera is still published; it simply has no
coordinates and is excluded from proximity alerts.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Callable

CACHE_PATH = Path("cache/road_names.json")

# Words that carry no discriminating power when matching a denomination.
_NOISE = {"raccordo", "autostradale", "autostrada", "strada", "statale", "tangenziale",
          "traforo", "del", "della", "dei", "delle", "di", "da", "il", "la", "e"}


def normalise_name(raw: str) -> str:
    """Fold a denomination to a comparable form.

    "Bologna – Taranto" and "Bologna - Taranto" are the same road printed with
    different dashes; the PDFs use both, sometimes on the same page.
    """
    # Apostrophes must become separators BEFORE the ASCII fold. Folding first
    # deletes them, turning "Val d'Esino" into the token "desino", which matches
    # nothing in OSM - the discriminating token is "esino".
    text = re.sub(r"[’'`´]", " ", raw or "")
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    folded = folded.lower()
    folded = re.sub(r"[‐-―]", "-", folded)
    folded = re.sub(r"[^a-z0-9]+", " ", folded)
    return " ".join(folded.split())


def name_tokens(raw: str) -> list[str]:
    """Discriminating tokens of a denomination, longest first."""
    tokens = [t for t in normalise_name(raw).split() if t not in _NOISE and len(t) > 2]
    return sorted(set(tokens), key=len, reverse=True)


def _build_query(tokens: list[str]) -> str:
    """Ask for road route relations whose name contains every discriminating token."""
    filters = "".join(f'["name"~"{re.escape(t)}",i]' for t in tokens[:3])
    return (
        '[out:json][timeout:90];'
        f'relation["type"="route"]["route"="road"]{filters};'
        "out tags;"
    )


def _pick_ref(elements: list[dict]) -> str | None:
    """Choose a ref only when the candidates agree.

    Two different refs matching one denomination means the query was ambiguous.
    Ambiguity resolves to None, never to a coin flip.
    """
    refs = set()
    for element in elements:
        ref = (element.get("tags") or {}).get("ref", "").strip()
        if ref:
            refs.add(re.sub(r"\s+", "", ref.split(";")[0].upper()))
    if len(refs) == 1:
        return refs.pop()
    return None


def load_cache(path: Path = CACHE_PATH) -> dict[str, str | None]:
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(mapping: dict[str, str | None], path: Path = CACHE_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
    )


def resolve_ref(
    road_name: str,
    *,
    cache: dict[str, str | None],
    client: Callable[[str], dict] | None = None,
) -> str | None:
    """Return the OSM ref for a denomination, consulting and filling the cache.

    A cached None means "asked OSM, got no unambiguous answer" and is honoured
    rather than re-queried, so a run does not repeatedly hammer the API for a
    road that has no route relation.
    """
    key = normalise_name(road_name)
    if not key or key == "?":
        return None
    if key in cache:
        return cache[key]

    tokens = name_tokens(road_name)
    if not tokens:
        cache[key] = None
        return None

    if client is None:
        from velox.overpass import _default_client

        client = _default_client

    payload = client(_build_query(tokens))
    ref = _pick_ref(payload.get("elements", []))
    cache[key] = ref
    return ref
