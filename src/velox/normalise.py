"""Normalisation primitives shared by both parsers.

Every function returns None rather than a guess when the input is not understood.
The caller quarantines on None; nothing downstream ever sees an inferred value.
"""

from __future__ import annotations

import re
from datetime import date

from velox.constants import DIRECTION_BEARINGS, PROVINCE_CODES

# "A / 07 Milano-Genova", "SS / 9 via Emilia", "S.S. 16 Adriatica", "SS16"
_ROAD_REF = re.compile(
    r"^\s*(?P<prefix>S\.?\s?S\.?|S\.?\s?P\.?|S\.?\s?R\.?|R\.?\s?A\.?|A)\s*/?\s*"
    r"(?P<number>\d{1,3})\s*(?P<name>.*)$",
    re.IGNORECASE,
)
_KM_PLUS = re.compile(r"^\s*(\d{1,4})\s*\+\s*(\d{1,3})\s*$")
_KM_DECIMAL = re.compile(r"^\s*(\d{1,4})\s*[,.]\s*(\d{1,3})\s*$")
_KM_WHOLE = re.compile(r"^\s*(\d{1,4})\s*$")
_IT_DATE = re.compile(r"^\s*(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})\s*$")


def normalise_road_ref(road_type: str, raw: str) -> tuple[str | None, str | None]:
    """Return (ref, name). ref is None when no recognisable reference is present.

    The weekly PDFs zero-pad the number ("A / 07"); the fixed lists do not.
    Both must normalise to the same ref so geometry lookups agree.
    """
    text = (raw or "").strip()
    if not text:
        return None, None
    match = _ROAD_REF.match(text)
    if not match:
        return None, text
    prefix = re.sub(r"[^A-Z]", "", match.group("prefix").upper())
    number = str(int(match.group("number")))  # strips the leading zero
    name = match.group("name").strip() or None
    return f"{prefix}{number}", name


def normalise_km(raw: str) -> float | None:
    """Accept 423+850, 08+250, 35,500 and 53. Anything else is not a kilometre."""
    text = (raw or "").strip()
    if not text:
        return None
    if m := _KM_PLUS.match(text):
        metres = m.group(2).ljust(3, "0")
        return round(int(m.group(1)) + int(metres) / 1000, 3)
    if m := _KM_DECIMAL.match(text):
        fraction = m.group(2).ljust(3, "0")
        return round(int(m.group(1)) + int(fraction) / 1000, 3)
    if m := _KM_WHOLE.match(text):
        return float(m.group(1))
    return None


def normalise_direction(raw: str) -> int | None:
    key = (raw or "").strip().lower().replace(" ", "-")
    return DIRECTION_BEARINGS.get(key)


def normalise_province(raw: str) -> str | None:
    code = (raw or "").strip().upper()
    return code if code in PROVINCE_CODES else None


def parse_it_date(raw: str) -> str | None:
    match = _IT_DATE.match(raw or "")
    if not match:
        return None
    day, month, year = (int(g) for g in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None
