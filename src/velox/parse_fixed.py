"""Parse the two fixed-installation PDFs.

These tables use merged cells rendered by ``pdftotext -layout`` as text placed
at the vertical centre of the span it covers: a region name, road name, comune
or province may sit on a line of its own, several lines away from the kilometre
rows it belongs to. Reading line-by-line therefore cannot work; instead:

1. Column positions are taken from the header lines ("Regione … Comune Prov"
   and "Chilometro Direzione"), re-read on every page.
2. Every field on a line is assigned to the column whose header centre is
   horizontally nearest.
3. A camera is anchored on a kilometre-shaped cell; missing cells are filled
   from the nearest cell of the right column within the same region block.
4. Region blocks are contiguous runs of table rows. Each region label is
   printed at the vertical centre of its own run, so the partition is chosen
   to minimise the squared distance between every label and the centre of the
   run assigned to it (naive nearest-label assignment misplaces rows next to
   short blocks: "Umbria" printed one line from a Campania row would steal it).

Rows whose kilometre column holds free text (for example the Frejus tunnel's
"Interno galleria") are quarantined. A camera without a kilometre cannot be
placed, and inventing one would put a false pin on a motorway.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from velox.normalise import (
    normalise_direction,
    normalise_km,
    normalise_province,
    normalise_road_ref,
)

_REGIONS_IN_PDF = (
    "Piemonte", "Valle d'Aosta", "Lombardia", "Trentino", "Veneto", "Friuli",
    "Liguria", "Emilia", "Toscana", "Umbria", "Marche", "Lazio", "Abruzzo",
    "Molise", "Campania", "Puglia", "Basilicata", "Calabria", "Sicilia", "Sardegna",
)

# Which region every province belongs to, keyed by the short region names above.
# Used only to keep the block partition honest: a row whose printed province
# contradicts a candidate region label cannot belong to that label's block.
_PROVINCES_BY_REGION = {
    "Piemonte": "TO VC NO CN AT AL BI VB",
    "Valle d'Aosta": "AO",
    "Lombardia": "VA CO SO MI BG BS PV CR MN LC LO MB",
    "Trentino": "BZ TN",
    "Veneto": "VR VI BL TV VE PD RO",
    "Friuli": "UD GO TS PN",
    "Liguria": "IM SV GE SP",
    "Emilia": "PC PR RE MO BO FE RA FC RN",
    "Toscana": "MS LU PT FI LI PI AR SI GR PO",
    "Umbria": "PG TR",
    "Marche": "PU AN MC AP FM",
    "Lazio": "VT RI RM LT FR",
    "Abruzzo": "AQ TE PE CH",
    "Molise": "CB IS",
    "Campania": "CE BN NA AV SA",
    "Puglia": "FG BA TA BR LE BT",
    "Basilicata": "PZ MT",
    "Calabria": "CS CZ RC KR VV",
    "Sicilia": "TP PA ME AG CL EN CT RG SR",
    "Sardegna": "SS NU CA OR SU",
}
_REGION_OF_PROVINCE = {
    code: region
    for region, codes in _PROVINCES_BY_REGION.items()
    for code in codes.split()
}
# A field is a run of non-space characters that may contain single spaces.
_FIELD = re.compile(r"\S+(?: \S+)*")
_NOISE = re.compile(r"Ministero dell|Elenco delle postazioni|Fonte:|Aggiornato al")


@dataclass(frozen=True)
class FixedCamera:
    network: str
    region: str
    road_name: str
    road_ref: str | None
    km_raw: str
    km: float | None
    direction_raw: str | None
    bearing_deg: int | None
    comune: str
    province: str


@dataclass
class FixedParseResult:
    cameras: list[FixedCamera] = field(default_factory=list)
    quarantine: list[dict] = field(default_factory=list)


def _spans(line: str) -> list[tuple[float, str]]:
    """Fields on a line as (horizontal centre, text)."""
    return [((m.start() + m.end() - 1) / 2, m.group()) for m in _FIELD.finditer(line)]


def _match_region(cell: str) -> str | None:
    for region in _REGIONS_IN_PDF:
        if cell.startswith(region):
            return region
    return None


def _split_segments(text: str) -> list[tuple[dict[str, float], list[tuple[int, str]]]]:
    """Split into (column centres, data lines) per page, keyed off header lines.

    Line numbers are the physical ones from the document so that vertical
    distances include blank lines, matching what the eye sees on the page.
    """
    segments: list[tuple[dict[str, float], list[tuple[int, str]]]] = []
    centres: dict[str, float] | None = None
    rows: list[tuple[int, str]] = []

    for idx, line in enumerate(text.replace("\f", " ").splitlines()):
        if not line.strip() or _NOISE.search(line) or line.strip() == "Località":
            continue
        if "Regione" in line and "Prov" in line:
            if centres is not None and rows:
                segments.append((centres, rows))
            centres, rows = {}, []
            for centre, cell in _spans(line):
                key = {"Regione": "region", "Comune": "comune", "Prov": "prov"}.get(cell, "road")
                centres[key] = centre
            continue
        if "Chilometro" in line and "Direzione" in line:
            if centres is not None:
                for centre, cell in _spans(line):
                    if cell == "Chilometro":
                        centres["km"] = centre
                    elif cell == "Direzione":
                        centres["direction"] = centre
            continue
        if centres is None or len(centres) < 6:
            continue  # preamble before the table header
        rows.append((idx, line))

    if centres is not None and rows:
        segments.append((centres, rows))
    return segments


def _cells(line: str, centres: dict[str, float]) -> dict[str, str]:
    cells: dict[str, str] = {}
    for centre, cell in _spans(line):
        column = min(centres, key=lambda k: abs(centre - centres[k]))
        cells[column] = f"{cells[column]} {cell}" if column in cells else cell
    return cells


def _nearest(idx: int, candidates: list[tuple[int, str]]) -> str | None:
    """Nearest candidate by physical line distance; ties prefer the one above."""
    if not candidates:
        return None
    return min(candidates, key=lambda c: (abs(c[0] - idx), c[0] > idx))[1]


_EMPTY_RUN_PENALTY = 10_000.0
_PROVINCE_MISMATCH_PENALTY = 50.0


def _region_intervals(
    table_rows: list[tuple[int, str | None]], labels: list[tuple[int, str]]
) -> list[tuple[float, float, tuple[int, str]]]:
    """Partition table rows into one contiguous run per region label.

    Chosen to minimise the squared distance between each label's line and the
    centre of the run assigned to it, since the label is printed at the centre
    of the block it covers. Evenly spaced rows make that metric alone ambiguous
    (shifting every boundary by one row can cost nothing), so a row whose
    printed province contradicts the label's region is heavily penalised.
    Returns (start, end] line intervals per label.
    """
    rows = sorted(table_rows)
    n, m = len(rows), len(labels)

    def cost(j: int, a: int, b: int) -> float:
        if a == b:
            return _EMPTY_RUN_PENALTY
        # A merged cell spans its run, so the label sits at the extent midpoint.
        region = labels[j][1]
        fit = ((rows[a][0] + rows[b - 1][0]) / 2 - labels[j][0]) ** 2
        mismatches = sum(
            1 for _idx, prov in rows[a:b]
            if prov is not None and _REGION_OF_PROVINCE.get(prov) != region
        )
        return fit + mismatches * _PROVINCE_MISMATCH_PENALTY

    infinity = float("inf")
    best = [[infinity] * (n + 1) for _ in range(m + 1)]
    best[0][0] = 0.0
    cut_before = [[0] * (n + 1) for _ in range(m + 1)]
    for j in range(1, m + 1):
        for k in range(n + 1):
            for a in range(k + 1):
                value = best[j - 1][a] + cost(j - 1, a, k)
                if value < best[j][k]:
                    best[j][k] = value
                    cut_before[j][k] = a

    cuts = [n]
    for j in range(m, 0, -1):
        cuts.append(cut_before[j][cuts[-1]])
    cuts.reverse()  # cuts[j]..cuts[j+1] is label j's run

    runs = [([r[0] for r in rows[cuts[j]:cuts[j + 1]]], labels[j])
            for j in range(m) if cuts[j] < cuts[j + 1]]
    intervals: list[tuple[float, float, tuple[int, str]]] = []
    for i, (run, label) in enumerate(runs):
        start = float("-inf") if i == 0 else (runs[i - 1][0][-1] + run[0]) / 2
        end = float("inf") if i == len(runs) - 1 else (run[-1] + runs[i + 1][0][0]) / 2
        intervals.append((start, end, label))
    return intervals


def parse_fixed(network: str, text: str) -> FixedParseResult:
    result = FixedParseResult()
    for centres, raw_rows in _split_segments(text):
        _parse_segment(network, centres, raw_rows, result)
    return result


def _parse_segment(
    network: str,
    centres: dict[str, float],
    raw_rows: list[tuple[int, str]],
    result: FixedParseResult,
) -> None:
    rows = [(idx, line, _cells(line, centres)) for idx, line in raw_rows]

    labels = [(idx, name) for idx, _line, c in rows
              if "region" in c and (name := _match_region(c["region"]))]
    # Anchor the partition on kilometre-shaped rows only. A free-text kilometre
    # cell ("Interno" / "galleria") may be several fragments of ONE visual row,
    # and counting fragments as rows would skew every run centre.
    table_rows = [(idx, normalise_province(c.get("prov", ""))) for idx, _line, c in rows
                  if "km" in c and normalise_km(re.sub(r"\s+", "", c["km"])) is not None]
    intervals = _region_intervals(table_rows, labels) if labels and table_rows else []

    def block(idx: int) -> tuple[int, str] | None:
        for start, end, label in intervals:
            if start < idx <= end:
                return label
        return None

    # Road labels may span consecutive physical lines ("dell' Aeroporto" / "di Malpensa").
    road_groups: list[tuple[int, str]] = []
    for idx, _line, c in rows:
        if "road" in c:
            if road_groups and idx == road_groups[-1][0] + 1:
                prev_idx, prev_text = road_groups[-1]
                road_groups[-1] = (idx, f"{prev_text} {c['road']}")
            else:
                road_groups.append((idx, c["road"]))

    has_km = {idx for idx, _line, c in rows if "km" in c}
    free_comuni = [(idx, c["comune"]) for idx, _line, c in rows
                   if "comune" in c and idx not in has_km]
    attached_comuni = [(idx, c["comune"]) for idx, _line, c in rows
                       if "comune" in c and idx in has_km]
    free_directions = [(idx, c["direction"]) for idx, _line, c in rows
                       if "direction" in c and idx not in has_km]
    provinces = [(idx, p) for idx, _line, c in rows
                 if "prov" in c and (p := normalise_province(c["prov"]))]

    def quarantined(idx: int, line: str, reason: str) -> None:
        blk = block(idx)
        result.quarantine.append(
            {"source": f"fixed:{network}", "region": blk[1] if blk else "",
             "raw": line.strip(), "reason": reason}
        )

    for idx, line, c in rows:
        if "km" not in c:
            continue
        km_raw = re.sub(r"\s+", "", c["km"])
        km = normalise_km(km_raw)
        if km is None:
            quarantined(idx, line, f"kilometre column contains free text {c['km']!r}")
            continue

        blk = block(idx)
        if blk is None:
            quarantined(idx, line, "no region label anywhere on the page")
            continue
        region = blk[1]

        province = normalise_province(c.get("prov", ""))
        if province is None:
            if "prov" in c:
                quarantined(idx, line, f"unknown province code {c['prov']!r}")
                continue
            province = _nearest(idx, [(i, p) for i, p in provinces if block(i) == blk])
            if province is None:
                quarantined(idx, line, "no province on the row or in its region block")
                continue

        comune = c.get("comune")
        if comune is None:
            for distance in (1, 2, 3):
                frags = {i: t for i, t in free_comuni
                         if abs(i - idx) == distance and block(i) == blk}
                if frags:
                    comune = " ".join(frags[i] for i in sorted(frags))
                    break
            else:
                comune = _nearest(idx, [(i, t) for i, t in attached_comuni
                                        if i != idx and abs(i - idx) <= 3 and block(i) == blk])
        if comune is None:
            quarantined(idx, line, "no comune on the row or on the lines around it")
            continue

        direction_raw = c.get("direction")
        if direction_raw is None:
            nearby = {t for i, t in free_directions if abs(i - idx) <= 2}
            if len(nearby) == 1:  # two distinct words means both carriageways: unknown
                direction_raw = nearby.pop()

        road_name = c.get("road")
        if road_name is None:
            road_name = _nearest(idx, [(i, t) for i, t in road_groups if block(i) == blk])
        road_name = road_name or "?"
        ref, _name = normalise_road_ref("", road_name)

        result.cameras.append(
            FixedCamera(
                network=network, region=region, road_name=road_name, road_ref=ref,
                km_raw=km_raw, km=km, direction_raw=direction_raw,
                bearing_deg=normalise_direction(direction_raw or ""),
                comune=comune, province=province,
            )
        )
