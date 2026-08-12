"""MIT device register.

The register carries no location data at all — the only geography is the Belfiore
code of the authority that owns the device. It therefore never contributes to the
map; it backs the fine-validity lookup only.

`tipo_dispositivo` is free text with over 500 observed spellings, so it is
classified through ordered substring rules and falls back to "sconosciuto"
rather than to a guess.
"""

from __future__ import annotations

import html
import json
import re

from velox.fetch import fetch

ENDPOINT = "https://velox.mit.gov.it/dispositivi/data"

_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def classify_tipo(raw: str) -> str:
    text = html.unescape(raw or "").strip().lower()
    if not text:
        return "sconosciuto"
    has_fisso = "fiss" in text
    has_mobile = "mobil" in text or "portatil" in text
    if "media" in text:
        return "media"
    if has_fisso and has_mobile:
        return "fisso_mobile"
    if has_fisso:
        return "fisso"
    if has_mobile:
        return "mobile"
    return "sconosciuto"


def _iso_date(raw: str) -> str | None:
    match = _DATE.match((raw or "").strip())
    if not match:
        return None
    day, month, year = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _clean(value) -> str:
    return html.unescape(str(value or "")).strip()


def normalise_device(row: dict) -> dict:
    tipo_raw = _clean(row.get("tipo_dispositivo"))
    return {
        "id": int(row["id"]),
        "ente": _clean(row.get("denominazione_accertatore")),
        "codice_accertatore": _clean(row.get("codice_accertatore")),
        "codice_catastale": _clean(row.get("codice_catastale_accertatore")),
        "tipo_raw": tipo_raw,
        "tipo": classify_tipo(tipo_raw),
        "marca": _clean(row.get("marca_dispositivo")),
        "modello": _clean(row.get("modello_dispositivo")),
        "versione": _clean(row.get("versione_dispositivo")),
        "matricola": _clean(row.get("matricola_dispositivo")),
        "n_decreto": _clean(row.get("n_decreto")),
        "data_decreto": _iso_date(_clean(row.get("data_decreto"))),
        "note": _clean(row.get("note")),
    }


def fetch_devices(*, page_size: int = 5000) -> list[dict]:
    result = fetch(f"{ENDPOINT}?draw=1&start=0&length={page_size}")
    payload = json.loads(result.content.decode("utf-8", errors="replace"))
    rows = payload.get("data", [])
    total = int(payload.get("recordsTotal", 0))
    if not rows:
        raise ValueError("MIT register returned zero rows")
    if total and len(rows) < total:
        raise ValueError(f"MIT register truncated: got {len(rows)} of {total}")
    return [normalise_device(row) for row in rows]
