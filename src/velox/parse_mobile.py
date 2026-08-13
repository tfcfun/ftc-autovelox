"""Parse a regional weekly PDF into dated mobile-check rows.

Layout (verified against the real Lombardia file):

    Validità da lunedì 10 agosto 2026 a domenica 16 agosto 2026
    Giorno       Tratto stradale                      Provincia
    14/08/2026
        Strada Statale     SS / 9 via Emilia              LO

A bare date line opens a group; indented rows below it belong to that date.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field

from velox.normalise import normalise_province, normalise_road_ref, parse_it_date

_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
_VALIDITY = re.compile(
    r"Validità\s+da\s+\w+\s+(\d{1,2})\s+(\w+)\s+(\d{4})\s+a\s+\w+\s+(\d{1,2})\s+(\w+)\s+(\d{4})",
    re.IGNORECASE,
)
_BARE_DATE = re.compile(r"^\s*(\d{2}/\d{2}/\d{4})\s*$")
_ROAD_TYPES = ("Strada Statale", "Autostrada", "Strada Provinciale",
               "Strada Regionale", "Raccordo Autostradale", "Tangenziale")


@dataclass(frozen=True)
class MobileCheck:
    date: str
    region: str
    road_type: str
    road_ref: str | None
    road_name: str | None
    province: str


# Some regions publish an explicit "nothing scheduled" page instead of a table.
# Verified 2026-08-13: the Molise PDF reads "Servizi di controllo velocità non
# programmati nella settimana".
_EXPLICIT_EMPTY = re.compile(r"non\s+programmat[io]\s+nella\s+settimana", re.IGNORECASE)


@dataclass
class MobileParseResult:
    region: str
    valid_from: str | None = None
    valid_to: str | None = None
    checks: list[MobileCheck] = field(default_factory=list)
    quarantine: list[dict] = field(default_factory=list)
    confirmed_empty: bool = False
    """True when the document was read successfully and says there are no checks.

    This is NOT the same as parsing nothing. 'We could not read it' and 'the
    police published a zero' must never render the same way to a driver: the
    first is missing data, the second is information."""


def pdf_to_text(pdf_bytes: bytes) -> str:
    completed = subprocess.run(
        ["pdftotext", "-layout", "-", "-"],
        input=pdf_bytes, capture_output=True, check=True,
    )
    return completed.stdout.decode("utf-8", errors="replace")


def _validity(text: str) -> tuple[str | None, str | None]:
    match = _VALIDITY.search(text)
    if not match:
        return None, None
    d1, m1, y1, d2, m2, y2 = match.groups()
    try:
        start = f"{int(y1):04d}-{_MONTHS[m1.lower()]:02d}-{int(d1):02d}"
        end = f"{int(y2):04d}-{_MONTHS[m2.lower()]:02d}-{int(d2):02d}"
    except KeyError:
        return None, None
    return start, end


def parse_mobile(region: str, text: str) -> MobileParseResult:
    result = MobileParseResult(region=region)
    result.valid_from, result.valid_to = _validity(text)
    # A readable validity header, or an explicit statement, both confirm a zero.
    result.confirmed_empty = bool(
        _EXPLICIT_EMPTY.search(text) or result.valid_from is not None
    )

    current_date: str | None = None
    for line in text.splitlines():
        if not line.strip():
            continue

        if bare := _BARE_DATE.match(line):
            iso = parse_it_date(bare.group(1))
            if iso is None:
                result.quarantine.append(
                    {"source": "mobile", "region": region, "raw": line.strip(),
                     "reason": "unparseable date line"}
                )
                current_date = None
            else:
                current_date = iso
            continue

        road_type = next((t for t in _ROAD_TYPES if line.strip().startswith(t)), None)
        if road_type is None:
            continue  # headers, titles, footers

        remainder = line.strip()[len(road_type):].strip()
        parts = remainder.rsplit(None, 1)
        if len(parts) != 2:
            result.quarantine.append(
                {"source": "mobile", "region": region, "raw": line.strip(),
                 "reason": "row has no trailing province token"}
            )
            continue

        road_raw, province_raw = parts
        province = normalise_province(province_raw)
        if province is None:
            result.quarantine.append(
                {"source": "mobile", "region": region, "raw": line.strip(),
                 "reason": f"unknown province code {province_raw!r}"}
            )
            continue

        if current_date is None:
            result.quarantine.append(
                {"source": "mobile", "region": region, "raw": line.strip(),
                 "reason": "row has no preceding date line"}
            )
            continue

        ref, name = normalise_road_ref(road_type, road_raw)
        result.checks.append(
            MobileCheck(
                date=current_date, region=region, road_type=road_type,
                road_ref=ref, road_name=name, province=province,
            )
        )
    return result
