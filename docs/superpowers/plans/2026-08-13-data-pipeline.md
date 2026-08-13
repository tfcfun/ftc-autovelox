# Velox Italia — Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the scheduled ingest pipeline that turns Polizia di Stato PDFs and the MIT device register into a validated, versioned, static JSON snapshot served from GitHub Pages.

**Architecture:** A pure-Python package run by GitHub Actions on a cron. It resolves source URLs from the live page (they move), downloads, parses deterministically with `pdftotext -layout`, normalises, geocodes via the Overpass API with a permanent on-disk cache, then validates and writes an immutable weekly snapshot plus a `latest` pointer. No runtime server, no database, no language model in the extraction path.

**Tech Stack:** Python 3.12, `uv` for dependency management, `pytest`, `ruff`, `requests`, `poppler-utils` (`pdftotext` CLI), Overpass API, GitHub Actions, GitHub Pages.

## Global Constraints

- **Python 3.12.** Local interpreter is `/opt/homebrew/bin/python3.12`; CI pins `3.12`. The system `python3` is 3.9.6 and must not be used.
- **No language model anywhere in the extraction path.** Parsing is deterministic. A model may only be used to describe failures after the fact.
- **A missing row is never an all-clear.** Any parse producing zero rows for a region must abort publication of that region and retain last-good.
- **Quarantine, never guess.** A row that does not match its expected shape is recorded in a quarantine list with the raw text and a reason. Never infer a date, road, or kilometre from a malformed line.
- **Never hardcode a source URL.** All source URLs are resolved from the live page every run. If resolution fails, the run fails.
- **All timestamps are UTC ISO-8601 with a `Z` suffix.**
- **Province codes are validated against a closed set.** An unknown code quarantines the row.
- **Snapshots are immutable.** Each run writes a new `data/<year>-W<week>/`; `data/latest/` is a copy, never an edit in place.
- **Schema version is `1`** and appears in every published file.

---

## Snapshot Schema (the contract with the iOS app)

Published under `data/<year>-W<week>/` and copied to `data/latest/`.

**`index.json`**

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-13T06:00:00Z",
  "week": "2026-W33",
  "files": {
    "fixed_cameras.json": {"sha256": "…", "count": 160},
    "mobile_checks.json": {"sha256": "…", "count": 47},
    "road_segments.json": {"sha256": "…", "count": 31},
    "mit_devices.json": {"sha256": "…", "count": 4110}
  },
  "regions": {
    "Lombardia": {"status": "ok", "updated_at": "2026-08-13T06:00:00Z", "rows": 3, "quarantined": 0},
    "Sicilia": {"status": "stale", "updated_at": "2026-08-06T06:00:00Z", "rows": 5, "quarantined": 0}
  },
  "sources": {
    "polizia_mobile": {"fetched_at": "…", "valid_from": "2026-08-10", "valid_to": "2026-08-16"},
    "polizia_fixed_auto": {"fetched_at": "…", "url": "…", "sha256": "…"},
    "polizia_fixed_ord": {"fetched_at": "…", "url": "…", "sha256": "…"},
    "mit": {"fetched_at": "…", "count": 4110}
  },
  "quarantine_count": 0
}
```

`status` is one of `ok`, `stale`, `failed`.

**`fixed_cameras.json`** — array of:

```json
{
  "id": "fx-auto-A4-423850-ovest",
  "network": "autostrada",
  "region": "Veneto",
  "road_name": "Torino – Trieste",
  "road_ref": "A4",
  "km_raw": "423+850",
  "km": 423.85,
  "direction_raw": "Ovest",
  "bearing_deg": 270,
  "comune": "Noventa di Piave",
  "province": "VE",
  "lat": 45.6612, "lon": 12.5341,
  "geocode_method": "overpass_milestone",
  "geocode_confidence": "high",
  "verified": false
}
```

`road_ref`, `km`, `bearing_deg`, `lat`, `lon` may be `null`. A camera with a null `lat` is published (it is real and browsable) but is excluded from proximity alerts by the app.

**`mobile_checks.json`** — array of:

```json
{
  "id": "mb-2026W33-LO-SS9-2026-08-14",
  "date": "2026-08-14",
  "week": "2026-W33",
  "region": "Lombardia",
  "road_type": "Strada Statale",
  "road_ref": "SS9",
  "road_name": "via Emilia",
  "province": "LO",
  "segment_id": "seg-SS9-LO"
}
```

`segment_id` is `null` when geometry could not be fetched.

**`road_segments.json`** — array of:

```json
{
  "id": "seg-SS9-LO",
  "road_ref": "SS9",
  "province": "LO",
  "geometry": [[9.5012, 45.3141], [9.5033, 45.3128]],
  "source": "overpass",
  "fetched_at": "2026-08-13T06:00:00Z"
}
```

Geometry is `[lon, lat]` pairs, Douglas-Peucker simplified to ~20 m tolerance.

**`mit_devices.json`** — array of:

```json
{
  "id": 2,
  "ente": "Servizio Intercomunale P.L. \"Colline Moreniche del Garda\"",
  "codice_accertatore": "CMBSP252",
  "codice_catastale": "B436",
  "tipo_raw": "Mobile",
  "tipo": "mobile",
  "marca": "Elltraff",
  "modello": "Telelaser",
  "versione": "Trucam HD",
  "matricola": "TC010198",
  "n_decreto": "3248",
  "data_decreto": "2011-06-13",
  "note": "Estensione di approvazione 0000242 del 05/07/2018"
}
```

`tipo` is the normalised classification: `fisso`, `mobile`, `fisso_mobile`, `media`, or `sconosciuto`.

**`quarantine.json`** — array of `{"source": "…", "region": "…", "raw": "…", "reason": "…"}`.

---

## File Structure

```
velox-italia/
├── pyproject.toml                  uv project, deps, ruff + pytest config
├── src/velox/
│   ├── __init__.py
│   ├── constants.py                province codes, region list, schema version
│   ├── normalise.py                road refs, km, direction, dates, provinces
│   ├── sources.py                  resolve live source URLs from the page
│   ├── fetch.py                    HTTP with retries, hashing, on-disk cache
│   ├── parse_mobile.py             regional weekly PDF → MobileCheck rows
│   ├── parse_fixed.py              fixed-installation PDFs → FixedCamera rows
│   ├── mit.py                      MIT register fetch + tipo classification
│   ├── overpass.py                 Overpass client + permanent geometry cache
│   ├── geocode_segments.py         (ref, province) → simplified polyline
│   ├── geocode_fixed.py            road + km + direction → coordinate
│   ├── publish.py                  validation gates + snapshot writer
│   └── cli.py                      `python -m velox.cli ingest`
├── tests/                          mirrors src/, one test module per source module
├── fixtures/2026-W33/              real source files, committed (already present)
├── cache/segments/                 committed Overpass geometry cache
├── data/<year>-W<week>/            published snapshots
├── data/latest/                    copy of the most recent good snapshot
├── review/index.html               fixed-camera coordinate review page
└── .github/workflows/ingest.yml    cron + manual dispatch
```

---

### Task 1: Project scaffold and CI test job

**Files:**
- Create: `pyproject.toml`, `src/velox/__init__.py`, `src/velox/constants.py`, `tests/test_constants.py`, `.github/workflows/test.yml`, `.gitignore`
- Copy: `fixtures/2026-W33/poliziadistato.html` (from the scratchpad copy of the live page)

**Interfaces:**
- Consumes: nothing
- Produces: `velox.constants.SCHEMA_VERSION: int`, `velox.constants.PROVINCE_CODES: frozenset[str]`, `velox.constants.REGIONS: tuple[str, ...]`

- [ ] **Step 1: Create the uv project**

```bash
cd .
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
```

Create `pyproject.toml`:

```toml
[project]
name = "velox"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["requests>=2.32"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.6"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/velox"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

Create `.gitignore`:

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
work/
```

- [ ] **Step 2: Write `src/velox/constants.py`**

```python
"""Closed value sets. An unknown value quarantines a row rather than passing through."""

SCHEMA_VERSION = 1

# The 107 Italian province codes. Unknown codes are quarantined, never accepted,
# so an omission here surfaces loudly instead of corrupting a row.
PROVINCE_CODES = frozenset("""
AG AL AN AO AP AQ AR AT AV BA BG BI BL BN BO BR BS BT BZ
CA CB CE CH CL CN CO CR CS CT CZ EN FC FE FG FI FM FR GE
GO GR IM IS KR LC LE LI LO LT LU MB MC ME MI MN MO MS MT
NA NO NU OR PA PC PD PE PG PI PN PO PR PT PU PV PZ RA RC
RE RG RI RM RN RO SA SI SO SP SR SS SU SV TA TE TN TO TP
TR TS TV UD VA VB VC VE VI VR VT VV
""".split())

# Region names as they appear in the Documenti block of the source page.
REGIONS = (
    "Abruzzo", "Basilicata", "Calabria", "Campania", "Emilia", "Friuli",
    "Lazio", "Liguria", "Lombardia", "Marche", "Molise", "Piemonte",
    "Puglia", "Sardegna", "Sicilia", "Toscana", "Trentino", "Umbria",
    "Valle d'Aosta", "Veneto",
)

# Compass words used in the fixed-installation PDFs, mapped to bearings in degrees.
DIRECTION_BEARINGS = {
    "nord": 0, "nord-est": 45, "est": 90, "sud-est": 135,
    "sud": 180, "sud-ovest": 225, "ovest": 270, "nord-ovest": 315,
}
```

- [ ] **Step 3: Write the failing test**

`tests/test_constants.py`:

```python
from velox.constants import PROVINCE_CODES, REGIONS, DIRECTION_BEARINGS, SCHEMA_VERSION


def test_province_codes_are_complete_and_well_formed():
    assert len(PROVINCE_CODES) == 107
    assert all(len(c) == 2 and c.isupper() for c in PROVINCE_CODES)
    # Codes seen in the real fixtures must be present.
    for code in ("LO", "PV", "VE", "PT", "AR", "FI", "PR", "PU", "MC", "FM", "TO", "VA", "LI"):
        assert code in PROVINCE_CODES


def test_regions_match_the_source_page():
    assert len(REGIONS) == 20
    assert "Lombardia" in REGIONS
    assert "Valle d'Aosta" in REGIONS


def test_direction_bearings_cover_the_cardinals():
    assert DIRECTION_BEARINGS["nord"] == 0
    assert DIRECTION_BEARINGS["ovest"] == 270
    assert len(DIRECTION_BEARINGS) == 8


def test_schema_version_is_one():
    assert SCHEMA_VERSION == 1
```

- [ ] **Step 4: Run the test**

```bash
cd . && .venv/bin/python -m pytest tests/test_constants.py -v
```

Expected: PASS, 4 tests. If the province count assertion fails, fix `PROVINCE_CODES` — do not relax the assertion.

- [ ] **Step 5: Commit the source page fixture**

The live page is needed as a fixture for Task 2. Fetch and commit it:

```bash
cd .
curl -sL --max-time 60 -A "Mozilla/5.0" \
  "https://www.poliziadistato.it/articolo/autovelox-e-tutor-dove-sono" \
  -o fixtures/2026-W33/poliziadistato.html
test -s fixtures/2026-W33/poliziadistato.html && grep -c "statics" fixtures/2026-W33/poliziadistato.html
```

Expected: a non-zero count of `statics` occurrences.

- [ ] **Step 6: Add the CI test workflow**

`.github/workflows/test.yml`:

```yaml
name: test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: sudo apt-get update && sudo apt-get install -y poppler-utils
      - run: pip install -e ".[dev]"
      - run: ruff check src tests
      - run: pytest -v
```

- [ ] **Step 7: Commit**

```bash
cd .
git add pyproject.toml .gitignore src tests .github fixtures
git commit -m "feat: project scaffold, closed value sets, CI test job"
```

---

### Task 2: Resolve source URLs from the live page

The `/statics/<NN>/` folder number changes when the Polizia republishes a file. Resolution happens every run; failure to resolve fails the run.

**Files:**
- Create: `src/velox/sources.py`, `tests/test_sources.py`

**Interfaces:**
- Consumes: `velox.constants.REGIONS`
- Produces:
  - `velox.sources.SourceLinks` — dataclass with fields `regional: dict[str, str]`, `fixed_auto: str`, `fixed_ord: str`
  - `velox.sources.resolve_sources(html: str, base_url: str = "https://www.poliziadistato.it") -> SourceLinks`
  - `velox.sources.SourceResolutionError` — raised when the Documenti block is absent or incomplete

- [ ] **Step 1: Write the failing test**

`tests/test_sources.py`:

```python
from pathlib import Path

import pytest

from velox.sources import SourceResolutionError, resolve_sources

FIXTURE = Path(__file__).parent.parent / "fixtures" / "2026-W33" / "poliziadistato.html"


def test_resolves_all_twenty_regions_and_both_fixed_lists():
    links = resolve_sources(FIXTURE.read_text(encoding="utf-8", errors="replace"))
    assert len(links.regional) == 20
    assert links.regional["Lombardia"].endswith("/lombardia.pdf")
    assert links.regional["Lombardia"].startswith("https://www.poliziadistato.it/statics/")
    assert "mvpostazionefissaaut" in links.fixed_auto
    assert "mvpostazionefissaord" in links.fixed_ord


def test_urls_are_absolute():
    links = resolve_sources(FIXTURE.read_text(encoding="utf-8", errors="replace"))
    for url in [*links.regional.values(), links.fixed_auto, links.fixed_ord]:
        assert url.startswith("https://")


def test_missing_documenti_block_raises_rather_than_falling_back():
    with pytest.raises(SourceResolutionError):
        resolve_sources("<html><body>nothing here</body></html>")


def test_partial_region_list_raises():
    html = "<a href='/statics/04/abruzzo.pdf'>Abruzzo</a>"
    with pytest.raises(SourceResolutionError):
        resolve_sources(html)
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd . && .venv/bin/python -m pytest tests/test_sources.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'velox.sources'`.

- [ ] **Step 3: Implement `src/velox/sources.py`**

Note: the page uses **single-quoted** `href` attributes. Matching only double quotes silently finds nothing.

```python
"""Resolve current source URLs from the live page.

The /statics/<NN>/ folder number changes whenever a file is republished, so URLs
are never hardcoded. If the Documenti block cannot be read, the run fails rather
than falling back to a stale path.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from velox.constants import REGIONS

BASE_URL = "https://www.poliziadistato.it"

# The page writes hrefs with single quotes: href='/statics/04/abruzzo.pdf'
_PDF_HREF = re.compile(r"""href=['"](/statics/\d+/[^'"]+\.pdf)['"]""", re.IGNORECASE)


class SourceResolutionError(RuntimeError):
    """The Documenti block was missing or did not contain the expected files."""


@dataclass(frozen=True)
class SourceLinks:
    regional: dict[str, str]
    fixed_auto: str
    fixed_ord: str


def _slug(text: str) -> str:
    """Fold a region name to its filename form: "Valle d'Aosta" -> "valledaosta"."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", folded.lower())


def resolve_sources(html: str, base_url: str = BASE_URL) -> SourceLinks:
    paths = _PDF_HREF.findall(html)
    if not paths:
        raise SourceResolutionError("no /statics/*.pdf links found on the page")

    by_slug: dict[str, str] = {}
    fixed_auto = fixed_ord = None
    for path in paths:
        filename = path.rsplit("/", 1)[-1]
        stem = filename[:-4]
        if stem.startswith("mvpostazionefissaaut"):
            fixed_auto = base_url + path
        elif stem.startswith("mvpostazionefissaord"):
            fixed_ord = base_url + path
        else:
            by_slug[_slug(stem)] = base_url + path

    regional: dict[str, str] = {}
    missing: list[str] = []
    for region in REGIONS:
        url = by_slug.get(_slug(region))
        if url is None:
            missing.append(region)
        else:
            regional[region] = url

    if missing:
        raise SourceResolutionError(f"regional PDFs not found for: {', '.join(missing)}")
    if fixed_auto is None:
        raise SourceResolutionError("motorway fixed-installation PDF not found")
    if fixed_ord is None:
        raise SourceResolutionError("ordinary-road fixed-installation PDF not found")

    return SourceLinks(regional=regional, fixed_auto=fixed_auto, fixed_ord=fixed_ord)
```

- [ ] **Step 4: Run the tests**

```bash
cd . && .venv/bin/python -m pytest tests/test_sources.py -v
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add src/velox/sources.py tests/test_sources.py
git commit -m "feat: resolve source URLs from the live page, fail loudly on absence"
```

---

### Task 3: HTTP fetch with hashing and cache

**Files:**
- Create: `src/velox/fetch.py`, `tests/test_fetch.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `velox.fetch.Fetched` — dataclass with `url: str`, `content: bytes`, `sha256: str`, `fetched_at: str`
  - `velox.fetch.fetch(url: str, *, timeout: int = 60, retries: int = 3) -> Fetched`
  - `velox.fetch.utc_now() -> str` — ISO-8601 with `Z`

- [ ] **Step 1: Write the failing test**

`tests/test_fetch.py`:

```python
import hashlib

import pytest

from velox.fetch import Fetched, fetch, utc_now


class _FakeResponse:
    def __init__(self, content: bytes, status: int = 200):
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_utc_now_is_iso8601_zulu():
    stamp = utc_now()
    assert stamp.endswith("Z")
    assert "T" in stamp
    assert len(stamp) == 20


def test_fetch_hashes_content(monkeypatch):
    payload = b"hello autovelox"
    monkeypatch.setattr("velox.fetch.requests.get", lambda *a, **k: _FakeResponse(payload))
    result = fetch("https://example.invalid/x.pdf")
    assert isinstance(result, Fetched)
    assert result.content == payload
    assert result.sha256 == hashlib.sha256(payload).hexdigest()
    assert result.url == "https://example.invalid/x.pdf"


def test_fetch_retries_then_raises(monkeypatch):
    calls = {"n": 0}

    def _boom(*a, **k):
        calls["n"] += 1
        raise OSError("network down")

    monkeypatch.setattr("velox.fetch.requests.get", _boom)
    monkeypatch.setattr("velox.fetch.time.sleep", lambda _s: None)
    with pytest.raises(OSError):
        fetch("https://example.invalid/x.pdf", retries=3)
    assert calls["n"] == 3


def test_fetch_rejects_empty_body(monkeypatch):
    monkeypatch.setattr("velox.fetch.requests.get", lambda *a, **k: _FakeResponse(b""))
    monkeypatch.setattr("velox.fetch.time.sleep", lambda _s: None)
    with pytest.raises(ValueError):
        fetch("https://example.invalid/x.pdf")
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd . && .venv/bin/python -m pytest tests/test_fetch.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/velox/fetch.py`**

```python
"""HTTP fetching with retries, content hashing, and an explicit empty-body rejection.

An empty response is treated as a failure, not as "no data": the whole pipeline
depends on absence never being mistaken for emptiness.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

USER_AGENT = "velox-italia/0.1 (+https://github.com/tfcfun/ftc-autovelox)"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Fetched:
    url: str
    content: bytes
    sha256: str
    fetched_at: str


def fetch(url: str, *, timeout: int = 60, retries: int = 3) -> Fetched:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(
                url, timeout=timeout, headers={"User-Agent": USER_AGENT}
            )
            response.raise_for_status()
            content = response.content
            if not content:
                raise ValueError(f"empty body from {url}")
            return Fetched(
                url=url,
                content=content,
                sha256=hashlib.sha256(content).hexdigest(),
                fetched_at=utc_now(),
            )
        except Exception as exc:  # noqa: BLE001 - retried and re-raised below
            last = exc
            if attempt < retries - 1:
                time.sleep(2**attempt)
    assert last is not None
    raise last
```

- [ ] **Step 4: Run the tests**

```bash
cd . && .venv/bin/python -m pytest tests/test_fetch.py -v
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add src/velox/fetch.py tests/test_fetch.py
git commit -m "feat: fetching with retries, hashing, empty-body rejection"
```

---

### Task 4: Normalisation primitives

Both parsers depend on these. Road references in the weekly PDFs carry a leading zero (`A / 07`) that must be stripped, and kilometres appear in at least three formats.

**Files:**
- Create: `src/velox/normalise.py`, `tests/test_normalise.py`

**Interfaces:**
- Consumes: `velox.constants.PROVINCE_CODES`, `velox.constants.DIRECTION_BEARINGS`
- Produces:
  - `normalise_road_ref(road_type: str, raw: str) -> tuple[str | None, str | None]` returning `(ref, name)`
  - `normalise_km(raw: str) -> float | None`
  - `normalise_direction(raw: str) -> int | None`
  - `normalise_province(raw: str) -> str | None`
  - `parse_it_date(raw: str) -> str | None` — `dd/mm/yyyy` to `yyyy-mm-dd`

- [ ] **Step 1: Write the failing test**

`tests/test_normalise.py`:

```python
from velox.normalise import (
    normalise_direction,
    normalise_km,
    normalise_province,
    normalise_road_ref,
    parse_it_date,
)


def test_road_ref_strips_leading_zero_and_separator():
    assert normalise_road_ref("Autostrada", "A / 07 Milano-Genova") == ("A7", "Milano-Genova")
    assert normalise_road_ref("Strada Statale", "SS / 9 via Emilia") == ("SS9", "via Emilia")
    assert normalise_road_ref("Strada Statale", "SS / 016 Adriatica") == ("SS16", "Adriatica")


def test_road_ref_handles_spacing_and_dots():
    assert normalise_road_ref("Strada Statale", "S.S. 16 Adriatica") == ("SS16", "Adriatica")
    assert normalise_road_ref("Strada Statale", "SS16")[0] == "SS16"


def test_road_ref_returns_none_when_unrecognisable():
    ref, name = normalise_road_ref("Strada Statale", "Tangenziale Nord")
    assert ref is None
    assert name == "Tangenziale Nord"


def test_km_accepts_the_three_observed_formats():
    assert normalise_km("423+850") == 423.85
    assert normalise_km("08+250") == 8.25
    assert normalise_km("35,500") == 35.5
    assert normalise_km("53+000") == 53.0


def test_km_rejects_free_text_rather_than_guessing():
    assert normalise_km("Interno galleria") is None
    assert normalise_km("") is None
    assert normalise_km("galleria") is None


def test_direction_maps_compass_words_case_insensitively():
    assert normalise_direction("Ovest") == 270
    assert normalise_direction("nord") == 0
    assert normalise_direction("Nord-Est") == 45
    assert normalise_direction("FRANCIA") is None
    assert normalise_direction("ITALIA") is None


def test_province_validated_against_closed_set():
    assert normalise_province("LO") == "LO"
    assert normalise_province(" ve ") == "VE"
    assert normalise_province("XX") is None
    assert normalise_province("") is None


def test_italian_date_conversion():
    assert parse_it_date("14/08/2026") == "2026-08-14"
    assert parse_it_date("1/8/2026") == "2026-08-01"
    assert parse_it_date("not a date") is None
    assert parse_it_date("32/08/2026") is None
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd . && .venv/bin/python -m pytest tests/test_normalise.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/velox/normalise.py`**

```python
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
```

- [ ] **Step 4: Run the tests**

```bash
cd . && .venv/bin/python -m pytest tests/test_normalise.py -v
```

Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add src/velox/normalise.py tests/test_normalise.py
git commit -m "feat: normalisation primitives returning None instead of guesses"
```

---

### Task 5: Parse the weekly regional PDFs

**Files:**
- Create: `src/velox/parse_mobile.py`, `tests/test_parse_mobile.py`

**Interfaces:**
- Consumes: `velox.normalise.*`
- Produces:
  - `velox.parse_mobile.MobileCheck` — dataclass matching the `mobile_checks.json` record, minus `id`/`segment_id`
  - `velox.parse_mobile.MobileParseResult` — dataclass with `region`, `valid_from: str | None`, `valid_to: str | None`, `checks: list[MobileCheck]`, `quarantine: list[dict]`
  - `velox.parse_mobile.pdf_to_text(pdf_bytes: bytes) -> str` — shells out to `pdftotext -layout -`
  - `velox.parse_mobile.parse_mobile(region: str, text: str) -> MobileParseResult`

- [ ] **Step 1: Write the failing test against the real fixture**

`tests/test_parse_mobile.py`:

```python
from pathlib import Path

from velox.parse_mobile import parse_mobile, pdf_to_text

FIXTURE = Path(__file__).parent.parent / "fixtures" / "2026-W33" / "lombardia.pdf"


def test_parses_the_real_lombardia_week_exactly():
    result = parse_mobile("Lombardia", pdf_to_text(FIXTURE.read_bytes()))

    assert result.region == "Lombardia"
    assert result.valid_from == "2026-08-10"
    assert result.valid_to == "2026-08-16"
    assert result.quarantine == []
    assert len(result.checks) == 3

    first, second, third = result.checks
    assert (first.date, first.road_ref, first.province) == ("2026-08-14", "SS9", "LO")
    assert first.road_type == "Strada Statale"
    assert first.road_name == "via Emilia"
    assert (second.date, second.road_ref, second.province) == ("2026-08-15", "A7", "PV")
    assert second.road_name == "Milano-Genova"
    assert (third.date, third.road_ref, third.province) == ("2026-08-16", "SS9", "LO")


def test_unknown_province_is_quarantined_not_dropped():
    text = """Lombardia
Validità da lunedì 10 agosto 2026 a domenica 16 agosto 2026
Giorno   Tratto stradale   Provincia
14/08/2026
    Strada Statale    SS / 9 via Emilia    XX
"""
    result = parse_mobile("Lombardia", text)
    assert result.checks == []
    assert len(result.quarantine) == 1
    assert "province" in result.quarantine[0]["reason"]
    assert "XX" in result.quarantine[0]["raw"]


def test_row_without_a_preceding_date_is_quarantined():
    text = """Lombardia
Validità da lunedì 10 agosto 2026 a domenica 16 agosto 2026
Giorno   Tratto stradale   Provincia
    Strada Statale    SS / 9 via Emilia    LO
"""
    result = parse_mobile("Lombardia", text)
    assert result.checks == []
    assert len(result.quarantine) == 1
    assert "date" in result.quarantine[0]["reason"]


def test_empty_document_yields_no_checks_and_no_crash():
    result = parse_mobile("Molise", "")
    assert result.checks == []
    assert result.valid_from is None
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd . && .venv/bin/python -m pytest tests/test_parse_mobile.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/velox/parse_mobile.py`**

The layout places a bare date on its own line, followed by one or more indented rows belonging to that date. The trailing token of a row is the province; the leading words are the road type.

```python
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


@dataclass
class MobileParseResult:
    region: str
    valid_from: str | None = None
    valid_to: str | None = None
    checks: list[MobileCheck] = field(default_factory=list)
    quarantine: list[dict] = field(default_factory=list)


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
```

- [ ] **Step 4: Run the tests**

```bash
cd . && .venv/bin/python -m pytest tests/test_parse_mobile.py -v
```

Expected: PASS, 4 tests. If the real-fixture test fails, print the extracted text with
`.venv/bin/python -c "from velox.parse_mobile import pdf_to_text;import pathlib;print(pdf_to_text(pathlib.Path('fixtures/2026-W33/lombardia.pdf').read_bytes()))"`
and adjust the parser to the observed layout — never adjust the expected values.

- [ ] **Step 5: Commit**

```bash
git add src/velox/parse_mobile.py tests/test_parse_mobile.py
git commit -m "feat: weekly regional PDF parser with quarantine, golden-tested"
```

---

### Task 6: Parse the fixed-installation PDFs

These are multi-column tables where the region and road names span several rows and are left blank on continuation lines. State must carry forward.

**Files:**
- Create: `src/velox/parse_fixed.py`, `tests/test_parse_fixed.py`

**Interfaces:**
- Consumes: `velox.normalise.*`, `velox.parse_mobile.pdf_to_text`
- Produces:
  - `velox.parse_fixed.FixedCamera` — dataclass: `network`, `region`, `road_name`, `road_ref`, `km_raw`, `km`, `direction_raw`, `bearing_deg`, `comune`, `province`
  - `velox.parse_fixed.FixedParseResult` — `cameras: list[FixedCamera]`, `quarantine: list[dict]`
  - `velox.parse_fixed.parse_fixed(network: str, text: str) -> FixedParseResult`

- [ ] **Step 1: Inspect the real layout before writing the parser**

```bash
cd .
pdftotext -layout fixtures/2026-W33/fisse_auto.pdf - | head -60
pdftotext -layout fixtures/2026-W33/fisse_ord.pdf - | head -60
```

Record the observed column positions. The parser keys off a row containing a kilometre-shaped
token plus a trailing two-letter province, carrying region and road forward from earlier lines.

- [ ] **Step 2: Write the failing test**

`tests/test_parse_fixed.py`:

```python
from pathlib import Path

from velox.parse_fixed import parse_fixed
from velox.parse_mobile import pdf_to_text

FIXTURES = Path(__file__).parent.parent / "fixtures" / "2026-W33"


def _cameras(name: str, network: str):
    return parse_fixed(network, pdf_to_text((FIXTURES / name).read_bytes()))


def test_motorway_list_finds_the_known_veneto_row():
    result = _cameras("fisse_auto.pdf", "autostrada")
    assert len(result.cameras) >= 20
    match = [
        c for c in result.cameras
        if c.comune == "Noventa di Piave" and c.km_raw == "423+850"
    ]
    assert len(match) == 1
    camera = match[0]
    assert camera.province == "VE"
    assert camera.km == 423.85
    assert camera.direction_raw == "Ovest"
    assert camera.bearing_deg == 270
    assert camera.network == "autostrada"


def test_decimal_kilometre_format_is_accepted():
    result = _cameras("fisse_auto.pdf", "autostrada")
    match = [c for c in result.cameras if c.comune == "Serravalle Pistoiese"]
    assert match and match[0].km == 35.5


def test_free_text_kilometre_is_quarantined_not_invented():
    result = _cameras("fisse_auto.pdf", "autostrada")
    assert all(c.km is not None for c in result.cameras)
    galleria = [q for q in result.quarantine if "galleria" in q["raw"].lower()]
    assert galleria, "the Frejus tunnel row must be quarantined, not silently dropped"


def test_ordinary_roads_list_parses():
    result = _cameras("fisse_ord.pdf", "ordinaria")
    assert len(result.cameras) >= 20
    assert all(c.network == "ordinaria" for c in result.cameras)
    assert all(c.province is not None for c in result.cameras)


def test_every_camera_carries_a_region():
    for name, network in (("fisse_auto.pdf", "autostrada"), ("fisse_ord.pdf", "ordinaria")):
        result = _cameras(name, network)
        assert all(c.region for c in result.cameras), f"{name} lost region state"
```

- [ ] **Step 3: Run it to confirm it fails**

```bash
cd . && .venv/bin/python -m pytest tests/test_parse_fixed.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement `src/velox/parse_fixed.py`**

```python
"""Parse the two fixed-installation PDFs.

Layout (verified): region and road names are written once and left blank on
continuation rows, so both are carried forward as state. A data row is
recognised by a kilometre-shaped token followed by a direction, a comune, and a
trailing two-letter province.

Rows whose kilometre is free text (for example the Frejus tunnel's "Interno
galleria") are quarantined. A camera without a kilometre cannot be placed, and
inventing one would put a false pin on a motorway.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from velox.constants import PROVINCE_CODES
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
_KM_TOKEN = re.compile(r"(\d{1,4}\s*\+\s*\d{1,3}|\d{1,4}\s*[,.]\s*\d{1,3})")
_TRAILING_PROVINCE = re.compile(r"\b([A-Z]{2})\s*$")
_DIRECTION_WORDS = ("nord-est", "nord-ovest", "sud-est", "sud-ovest",
                    "nord", "sud", "est", "ovest")


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


def _find_region(line: str) -> str | None:
    stripped = line.strip()
    for region in _REGIONS_IN_PDF:
        if stripped.startswith(region):
            return region
    return None


def _extract_direction(text: str) -> tuple[str | None, str]:
    lowered = text.lower()
    for word in _DIRECTION_WORDS:
        index = lowered.find(word)
        if index != -1:
            raw = text[index:index + len(word)]
            return raw, (text[:index] + text[index + len(word):])
    return None, text


def parse_fixed(network: str, text: str) -> FixedParseResult:
    result = FixedParseResult()
    region = ""
    road_name = ""

    for line in text.splitlines():
        if not line.strip():
            continue
        if any(h in line for h in ("Ministero dell'Interno", "Elenco delle postazioni",
                                   "Chilometro", "Località", "Regione")):
            continue

        if found := _find_region(line):
            region = found

        province_match = _TRAILING_PROVINCE.search(line.rstrip())
        km_match = _KM_TOKEN.search(line)

        if not province_match or province_match.group(1) not in PROVINCE_CODES:
            # A line carrying only a road name updates the carried-forward road.
            candidate = line.strip()
            if found := _find_region(line):
                candidate = candidate[len(found):].strip()
            if candidate and not _KM_TOKEN.search(candidate) and len(candidate) > 3:
                road_name = candidate
            continue

        province = normalise_province(province_match.group(1))
        body = line.rstrip()[: province_match.start()].strip()
        if found := _find_region(body):
            body = body[len(found):].strip()

        if km_match is None:
            result.quarantine.append(
                {"source": f"fixed:{network}", "region": region, "raw": line.strip(),
                 "reason": "no kilometre token on a row that has a province"}
            )
            continue

        km_raw = re.sub(r"\s+", "", km_match.group(1))
        body = (body[: km_match.start()] + " " + body[km_match.end():]).strip() \
            if km_match.start() < len(body) else body
        direction_raw, remainder = _extract_direction(body)
        comune = re.sub(r"\s{2,}", " ", remainder).strip(" -–") or "?"

        # A road name may be embedded on this very line rather than carried forward.
        if comune and len(comune.split()) > 4:
            comune = comune.split("  ")[-1].strip() or comune

        km = normalise_km(km_raw)
        if km is None:
            result.quarantine.append(
                {"source": f"fixed:{network}", "region": region, "raw": line.strip(),
                 "reason": f"unrecognised kilometre format {km_raw!r}"}
            )
            continue

        ref, parsed_name = normalise_road_ref("", road_name)
        result.cameras.append(
            FixedCamera(
                network=network, region=region, road_name=road_name or "?",
                road_ref=ref, km_raw=km_raw, km=km, direction_raw=direction_raw,
                bearing_deg=normalise_direction(direction_raw or ""),
                comune=comune, province=province,
            )
        )

    # Rows whose kilometre column held free text never reach the province branch,
    # so scan explicitly for them and record them.
    for line in text.splitlines():
        if "galleria" in line.lower() and not _KM_TOKEN.search(line):
            result.quarantine.append(
                {"source": f"fixed:{network}", "region": region, "raw": line.strip(),
                 "reason": "kilometre column contains free text"}
            )
    return result
```

- [ ] **Step 5: Run the tests and iterate against the real files**

```bash
cd . && .venv/bin/python -m pytest tests/test_parse_fixed.py -v
```

Expected: PASS, 5 tests. These two PDFs have irregular column layout; if a test fails, print the
extracted text and adjust the parser until the asserted real rows are produced. Do not weaken
the assertions — they name rows verified to exist in the source.

- [ ] **Step 6: Commit**

```bash
git add src/velox/parse_fixed.py tests/test_parse_fixed.py
git commit -m "feat: fixed-installation parser with carried-forward state and quarantine"
```

---

### Task 7: MIT device register

**Files:**
- Create: `src/velox/mit.py`, `tests/test_mit.py`

**Interfaces:**
- Consumes: `velox.fetch.fetch`
- Produces:
  - `velox.mit.classify_tipo(raw: str) -> str` — one of `fisso`, `mobile`, `fisso_mobile`, `media`, `sconosciuto`
  - `velox.mit.normalise_device(row: dict) -> dict` — a `mit_devices.json` record
  - `velox.mit.fetch_devices(*, page_size: int = 5000) -> list[dict]`

- [ ] **Step 1: Write the failing test**

`tests/test_mit.py`:

```python
import json
from pathlib import Path

from velox.mit import classify_tipo, normalise_device

SAMPLE = Path(__file__).parent.parent / "fixtures" / "2026-W33" / "mit_dispositivi_sample.json"


def test_classifies_the_common_spellings():
    assert classify_tipo("MOBILE") == "mobile"
    assert classify_tipo("mobile") == "mobile"
    assert classify_tipo("Mobile ") == "mobile"
    assert classify_tipo("FISSO") == "fisso"
    assert classify_tipo("fisso") == "fisso"
    assert classify_tipo("FISSO/MOBILE") == "fisso_mobile"
    assert classify_tipo("fisso-mobile") == "fisso_mobile"
    assert classify_tipo("FISSO - Velocità media") == "media"
    assert classify_tipo("Sistema rilevamento velocità media") == "media"


def test_free_text_descriptions_still_classify():
    assert classify_tipo("rilevatore di velocità in modalità istantanea") == "sconosciuto"
    assert classify_tipo("Dispositivo rilevamento velocità istantanea fisso") == "fisso"
    assert classify_tipo("Dispositivo rilevamento velocità istantanea mobile") == "mobile"


def test_junk_never_raises_and_never_guesses():
    for junk in ("//////////////////////////////////", "NESSUN VELOX", "13/06/2011", "", "-"):
        assert classify_tipo(junk) == "sconosciuto"


def test_normalise_device_decodes_entities_and_dates():
    row = json.loads(SAMPLE.read_text(encoding="utf-8"))[0]
    record = normalise_device(row)
    assert "&quot;" not in record["ente"]
    assert '"' in record["ente"]
    assert record["data_decreto"] == "2011-06-13"
    assert record["matricola"] == "TC010198"
    assert record["tipo"] == "mobile"
    assert record["codice_catastale"] == "B436"


def test_every_sample_row_normalises():
    rows = json.loads(SAMPLE.read_text(encoding="utf-8"))
    records = [normalise_device(r) for r in rows]
    assert len(records) == len(rows)
    assert all(isinstance(r["id"], int) for r in records)
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd . && .venv/bin/python -m pytest tests/test_mit.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/velox/mit.py`**

```python
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
```

- [ ] **Step 4: Run the tests**

```bash
cd . && .venv/bin/python -m pytest tests/test_mit.py -v
```

Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add src/velox/mit.py tests/test_mit.py
git commit -m "feat: MIT register fetch and free-text device classification"
```

---

### Task 8: Overpass client with a permanent cache

**Files:**
- Create: `src/velox/overpass.py`, `tests/test_overpass.py`, `cache/segments/.gitkeep`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `velox.overpass.cache_key(road_ref: str, province: str) -> str`
  - `velox.overpass.query_road_geometry(road_ref: str, province: str, *, cache_dir: Path, client=None) -> list[list[float]] | None`
  - `velox.overpass.simplify(points: list[list[float]], tolerance_m: float = 20.0) -> list[list[float]]`

- [ ] **Step 1: Write the failing test**

`tests/test_overpass.py`:

```python
import json

from velox.overpass import cache_key, query_road_geometry, simplify


def test_cache_key_is_stable_and_filesystem_safe():
    assert cache_key("SS9", "LO") == "SS9_LO"
    assert cache_key("A7", "PV") == "A7_PV"


def test_simplify_keeps_endpoints_and_drops_collinear_points():
    straight = [[9.0, 45.0], [9.001, 45.0], [9.002, 45.0], [9.003, 45.0]]
    result = simplify(straight, tolerance_m=20.0)
    assert result[0] == [9.0, 45.0]
    assert result[-1] == [9.003, 45.0]
    assert len(result) == 2


def test_simplify_preserves_a_genuine_bend():
    bent = [[9.0, 45.0], [9.01, 45.02], [9.02, 45.0]]
    assert len(simplify(bent, tolerance_m=20.0)) == 3


def test_cache_hit_avoids_the_network(tmp_path):
    (tmp_path / "SS9_LO.json").write_text(json.dumps([[9.5, 45.3], [9.6, 45.31]]))

    def _explode(*a, **k):
        raise AssertionError("network must not be touched on a cache hit")

    geometry = query_road_geometry("SS9", "LO", cache_dir=tmp_path, client=_explode)
    assert geometry == [[9.5, 45.3], [9.6, 45.31]]


def test_cache_miss_queries_and_writes(tmp_path):
    payload = {
        "elements": [
            {"type": "way", "geometry": [
                {"lon": 9.50, "lat": 45.30},
                {"lon": 9.51, "lat": 45.31},
            ]}
        ]
    }
    geometry = query_road_geometry("SS9", "LO", cache_dir=tmp_path, client=lambda q: payload)
    assert geometry[0] == [9.50, 45.30]
    assert (tmp_path / "SS9_LO.json").exists()


def test_no_result_returns_none_and_does_not_poison_the_cache(tmp_path):
    geometry = query_road_geometry("SS999", "LO", cache_dir=tmp_path,
                                   client=lambda q: {"elements": []})
    assert geometry is None
    assert not (tmp_path / "SS999_LO.json").exists()
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd . && .venv/bin/python -m pytest tests/test_overpass.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/velox/overpass.py`**

```python
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
```

- [ ] **Step 4: Run the tests**

```bash
cd . && .venv/bin/python -m pytest tests/test_overpass.py -v
```

Expected: PASS, 6 tests.

- [ ] **Step 5: Verify the query works against the live API for one real road**

```bash
cd .
.venv/bin/python -c "
from pathlib import Path
from velox.overpass import query_road_geometry
g = query_road_geometry('SS9','LO',cache_dir=Path('cache/segments'))
print('points:', len(g) if g else None)
"
```

Expected: a non-zero point count — this exact query was verified live on 2026-08-13 and returns
248 ways for SS9 in Lodi. If it returns `None`, do **not** start rewriting the selector: first
check whether you are being rate-limited (HTTP 429) or timed out (504), which is by far the more
likely cause and is handled by the backoff in `_default_client`. Space out your manual probes.

- [ ] **Step 6: Commit**

```bash
git add src/velox/overpass.py tests/test_overpass.py cache
git commit -m "feat: Overpass geometry client with committed permanent cache"
```

---

### Task 9: Geocode fixed cameras

**Files:**
- Create: `src/velox/geocode_fixed.py`, `tests/test_geocode_fixed.py`

**Interfaces:**
- Consumes: `velox.overpass.query_road_geometry`, `velox.parse_fixed.FixedCamera`
- Produces:
  - `velox.geocode_fixed.point_at_km(geometry: list[list[float]], km: float) -> list[float] | None`
  - `velox.geocode_fixed.geocode(camera: FixedCamera, *, cache_dir: Path) -> dict` — the camera as a `fixed_cameras.json` record, with `lat`/`lon`/`geocode_method`/`geocode_confidence`

- [ ] **Step 1: Write the failing test**

`tests/test_geocode_fixed.py`:

```python
from velox.geocode_fixed import point_at_km


def _straight_line_east(n=101):
    # ~1.1 km spacing per 0.01 degrees of longitude at this latitude.
    return [[9.0 + i * 0.01, 45.0] for i in range(n)]


def test_point_at_zero_km_is_the_start():
    assert point_at_km(_straight_line_east(), 0.0) == [9.0, 45.0]


def test_point_at_km_interpolates_along_the_line():
    geometry = _straight_line_east()
    point = point_at_km(geometry, 10.0)
    assert point is not None
    assert 9.0 < point[0] < 9.2
    assert abs(point[1] - 45.0) < 1e-9


def test_km_beyond_the_line_returns_none_rather_than_the_end():
    assert point_at_km(_straight_line_east(), 10_000.0) is None


def test_empty_geometry_returns_none():
    assert point_at_km([], 5.0) is None
    assert point_at_km([[9.0, 45.0]], 5.0) is None
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd . && .venv/bin/python -m pytest tests/test_geocode_fixed.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/velox/geocode_fixed.py`**

```python
"""Place a fixed camera from its road and kilometre.

Italian kilometre posts count from historical road origins, which do not always
coincide with the start of the OSM way. Interpolation is therefore marked
"medium" confidence and every point is reviewed by hand once (see review/index.html)
before being marked verified. A camera that cannot be placed keeps null
coordinates and is excluded from proximity alerts by the app.
"""

from __future__ import annotations

from pathlib import Path

from velox.overpass import _haversine_m, query_road_geometry
from velox.parse_fixed import FixedCamera


def point_at_km(geometry: list[list[float]], km: float) -> list[float] | None:
    if len(geometry) < 2 or km < 0:
        return None
    target_m = km * 1000.0
    travelled = 0.0
    for start, end in zip(geometry, geometry[1:]):
        span = _haversine_m(start, end)
        if travelled + span >= target_m:
            if span == 0:
                return list(start)
            ratio = (target_m - travelled) / span
            return [
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
            ]
        travelled += span
    return None


def geocode(camera: FixedCamera, *, cache_dir: Path) -> dict:
    identifier = "-".join(
        [
            "fx", camera.network[:4], (camera.road_ref or camera.comune or "x"),
            camera.km_raw.replace("+", "").replace(",", ""),
            (camera.direction_raw or "na").lower(),
        ]
    )
    record = {
        "id": identifier,
        "network": camera.network,
        "region": camera.region,
        "road_name": camera.road_name,
        "road_ref": camera.road_ref,
        "km_raw": camera.km_raw,
        "km": camera.km,
        "direction_raw": camera.direction_raw,
        "bearing_deg": camera.bearing_deg,
        "comune": camera.comune,
        "province": camera.province,
        "lat": None,
        "lon": None,
        "geocode_method": "none",
        "geocode_confidence": "none",
        "verified": False,
    }

    if not camera.road_ref or camera.km is None:
        return record

    geometry = query_road_geometry(camera.road_ref, camera.province, cache_dir=cache_dir)
    if not geometry:
        return record

    point = point_at_km(geometry, camera.km)
    if point is None:
        return record

    record["lon"], record["lat"] = point[0], point[1]
    record["geocode_method"] = "overpass_interpolated"
    record["geocode_confidence"] = "medium"
    return record
```

- [ ] **Step 4: Run the tests**

```bash
cd . && .venv/bin/python -m pytest tests/test_geocode_fixed.py -v
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add src/velox/geocode_fixed.py tests/test_geocode_fixed.py
git commit -m "feat: interpolate fixed-camera coordinates from road kilometre"
```

---

### Task 10: Publication gates and snapshot writer

This task implements the design's governing rule. It is the most important task in the plan.

**Files:**
- Create: `src/velox/publish.py`, `tests/test_publish.py`

**Interfaces:**
- Consumes: everything above
- Produces:
  - `velox.publish.RegionStatus` — dataclass `region`, `status`, `updated_at`, `rows`, `quarantined`
  - `velox.publish.decide_region_status(region, parsed_rows, previous) -> RegionStatus`
  - `velox.publish.write_snapshot(root: Path, week: str, payload: dict) -> Path`
  - `velox.publish.PublicationBlocked` — raised when a whole-snapshot invariant fails

- [ ] **Step 1: Write the failing test**

`tests/test_publish.py`:

```python
import json
from pathlib import Path

import pytest

from velox.publish import (
    PublicationBlocked,
    decide_region_status,
    write_snapshot,
)


def test_zero_rows_never_publishes_and_retains_last_good():
    previous = {"status": "ok", "updated_at": "2026-08-06T06:00:00Z", "rows": 5,
                "quarantined": 0}
    status = decide_region_status("Sicilia", parsed_rows=0, previous=previous)
    assert status.status == "stale"
    assert status.updated_at == "2026-08-06T06:00:00Z"
    assert status.rows == 5


def test_zero_rows_with_no_history_is_failed_not_ok():
    status = decide_region_status("Molise", parsed_rows=0, previous=None)
    assert status.status == "failed"
    assert status.rows == 0


def test_rows_present_publishes_ok():
    status = decide_region_status("Lombardia", parsed_rows=3, previous=None,
                                  quarantined=0, now="2026-08-13T06:00:00Z")
    assert status.status == "ok"
    assert status.rows == 3
    assert status.updated_at == "2026-08-13T06:00:00Z"


def test_snapshot_refuses_to_publish_with_no_fixed_cameras():
    payload = {"fixed_cameras": [], "mobile_checks": [{"x": 1}], "road_segments": [],
               "mit_devices": [{"id": 1}], "quarantine": [], "regions": {}}
    with pytest.raises(PublicationBlocked, match="fixed_cameras"):
        write_snapshot(Path("/tmp/velox-test-a"), "2026-W33", payload)


def test_snapshot_refuses_to_publish_with_no_mit_devices():
    payload = {"fixed_cameras": [{"id": "a"}], "mobile_checks": [], "road_segments": [],
               "mit_devices": [], "quarantine": [], "regions": {}}
    with pytest.raises(PublicationBlocked, match="mit_devices"):
        write_snapshot(Path("/tmp/velox-test-b"), "2026-W33", payload)


def test_snapshot_refuses_duplicate_ids():
    payload = {
        "fixed_cameras": [{"id": "fx-1"}, {"id": "fx-1"}],
        "mobile_checks": [], "road_segments": [], "mit_devices": [{"id": 1}],
        "quarantine": [], "regions": {},
    }
    with pytest.raises(PublicationBlocked, match="duplicate ids"):
        write_snapshot(Path("/tmp/velox-test-c"), "2026-W33", payload)


def test_snapshot_writes_files_index_and_latest(tmp_path):
    payload = {
        "fixed_cameras": [{"id": "fx-1", "lat": 45.0, "lon": 9.0}],
        "mobile_checks": [{"id": "mb-1"}],
        "road_segments": [{"id": "seg-1"}],
        "mit_devices": [{"id": 1}],
        "quarantine": [],
        "regions": {"Lombardia": {"status": "ok", "updated_at": "2026-08-13T06:00:00Z",
                                  "rows": 3, "quarantined": 0}},
        "sources": {},
    }
    written = write_snapshot(tmp_path, "2026-W33", payload)

    index = json.loads((written / "index.json").read_text())
    assert index["schema_version"] == 1
    assert index["week"] == "2026-W33"
    assert index["files"]["fixed_cameras.json"]["count"] == 1
    assert len(index["files"]["fixed_cameras.json"]["sha256"]) == 64

    latest = tmp_path / "latest"
    assert json.loads((latest / "index.json").read_text())["week"] == "2026-W33"
    assert (latest / "mit_devices.json").exists()


def test_latest_is_replaced_not_merged(tmp_path):
    base = {"fixed_cameras": [{"id": "fx-1"}], "mobile_checks": [], "road_segments": [],
            "mit_devices": [{"id": 1}], "quarantine": [], "regions": {}, "sources": {}}
    write_snapshot(tmp_path, "2026-W33", base)
    stale_marker = tmp_path / "latest" / "stale_marker.json"
    stale_marker.write_text("{}")
    write_snapshot(tmp_path, "2026-W34", base)
    assert not stale_marker.exists()
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd . && .venv/bin/python -m pytest tests/test_publish.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/velox/publish.py`**

```python
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
```

- [ ] **Step 4: Run the tests**

```bash
cd . && .venv/bin/python -m pytest tests/test_publish.py -v
```

Expected: PASS, 7 tests.

- [ ] **Step 5: Commit**

```bash
git add src/velox/publish.py tests/test_publish.py
git commit -m "feat: publication gates - zero rows never publishes as an all-clear"
```

---

### Task 11: CLI orchestration and first real run

**Files:**
- Create: `src/velox/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: every module above
- Produces: `python -m velox.cli ingest --root <dir>` writing a real snapshot

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:

```python
from velox.cli import build_mobile_records, deduplicate_cameras, iso_week


def test_deduplicate_collapses_the_same_physical_camera_filed_under_two_regions():
    # The real ordinary-roads PDF prints this row twice: once unlabelled inside
    # the Campania block, once under Basilicata.
    shared = {
        "network": "ordinaria", "road_name": "Potenza - Melfi", "km_raw": "2+600",
        "direction_raw": "Nord", "comune": "Potenza", "province": "PZ",
    }
    cameras = [
        {**shared, "region": "Campania", "id": "fx-ordi-Potenza-2600-nord"},
        {**shared, "region": "Basilicata", "id": "fx-ordi-Potenza-2600-nord"},
    ]
    kept, dropped = deduplicate_cameras(cameras)
    assert dropped == 1
    assert len(kept) == 1


def test_deduplicate_keeps_genuinely_different_cameras_on_the_same_road():
    base = {"network": "ordinaria", "road_name": "Del Vesuvio", "region": "Campania",
            "province": "NA"}
    cameras = [
        {**base, "km_raw": "11+500", "direction_raw": "Sud", "comune": "Nola", "id": "a"},
        {**base, "km_raw": "4+190", "direction_raw": "Nord", "comune": "Sant'Anastasia",
         "id": "b"},
    ]
    kept, dropped = deduplicate_cameras(cameras)
    assert dropped == 0
    assert len(kept) == 2


def test_deduplicate_keeps_both_carriageways_at_the_same_kilometre():
    base = {"network": "autostrada", "road_name": "Torino – Trieste", "region": "Veneto",
            "km_raw": "417+900", "comune": "Meolo", "province": "VE"}
    cameras = [
        {**base, "direction_raw": "Ovest", "id": "a"},
        {**base, "direction_raw": "Est", "id": "b"},
    ]
    kept, dropped = deduplicate_cameras(cameras)
    assert dropped == 0, "opposite carriageways are two separate installations"


def test_iso_week_formats_as_year_dash_w_week():
    assert iso_week("2026-08-13") == "2026-W33"
    assert iso_week("2026-01-01") == "2026-W01"


def test_build_mobile_records_assigns_ids_and_segment_links():
    from velox.parse_mobile import MobileCheck

    checks = [
        MobileCheck(date="2026-08-14", region="Lombardia", road_type="Strada Statale",
                    road_ref="SS9", road_name="via Emilia", province="LO"),
        MobileCheck(date="2026-08-15", region="Lombardia", road_type="Autostrada",
                    road_ref=None, road_name="Tangenziale", province="PV"),
    ]
    records = build_mobile_records(checks, week="2026-W33", segment_ids={"SS9_LO"})

    assert records[0]["id"] == "mb-2026W33-LO-SS9-2026-08-14"
    assert records[0]["segment_id"] == "seg-SS9-LO"
    assert records[1]["segment_id"] is None, "no ref means no geometry link"
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd . && .venv/bin/python -m pytest tests/test_cli.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/velox/cli.py`**

```python
"""Pipeline orchestration.

Run: python -m velox.cli ingest --root data
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from velox.constants import REGIONS
from velox.fetch import fetch, utc_now
from velox.geocode_fixed import geocode
from velox.mit import fetch_devices
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


def build_mobile_records(
    checks: list[MobileCheck], *, week: str, segment_ids: set[str]
) -> list[dict]:
    records = []
    for check in checks:
        key = cache_key(check.road_ref, check.province) if check.road_ref else None
        records.append(
            {
                "id": f"mb-{week.replace('-', '')}-{check.province}-"
                      f"{check.road_ref or 'NA'}-{check.date}",
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
                                 quarantined=len(parsed.quarantine))
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
        for camera in parsed.cameras:
            cameras.append(geocode(camera, cache_dir=CACHE_DIR))
        print(f"fixed/{network}: {len(parsed.cameras)} cameras", file=sys.stderr)

    cameras, duplicates = deduplicate_cameras(cameras)
    if duplicates:
        print(f"collapsed {duplicates} duplicate camera row(s)", file=sys.stderr)

    segments: list[dict] = []
    segment_ids: set[str] = set()
    pairs = {(c.road_ref, c.province) for c in all_checks if c.road_ref}
    for ref, province in sorted(pairs):
        geometry = query_road_geometry(ref, province, cache_dir=CACHE_DIR)
        if not geometry:
            print(f"no geometry for {ref} {province}", file=sys.stderr)
            continue
        segment_ids.add(cache_key(ref, province))
        segments.append(
            {"id": f"seg-{ref}-{province}", "road_ref": ref, "province": province,
             "geometry": geometry, "source": "overpass", "fetched_at": utc_now()}
        )

    devices = fetch_devices()
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
            "mit": {"fetched_at": utc_now(), "count": len(devices)},
        },
    }

    written = write_snapshot(root, week, payload)
    print(f"wrote {written}", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="velox")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest_cmd = sub.add_parser("ingest")
    ingest_cmd.add_argument("--root", default="data")
    args = parser.parse_args()
    if args.command == "ingest":
        return ingest(Path(args.root))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the unit tests**

```bash
cd . && .venv/bin/python -m pytest tests/test_cli.py -v
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Run the real pipeline end to end**

```bash
cd . && .venv/bin/python -m velox.cli ingest --root data
```

Expected: all 20 regions reported, fixed cameras parsed, a snapshot written. This makes live
Overpass calls and may take several minutes on the first run while the cache fills. Inspect the
result:

```bash
.venv/bin/python -c "
import json,pathlib
i=json.loads(pathlib.Path('data/latest/index.json').read_text())
print('week',i['week'],'quarantine',i['quarantine_count'])
for r,s in i['regions'].items(): print(f\"{r:14} {s['status']:7} rows={s['rows']}\")
print({k:v['count'] for k,v in i['files'].items()})
"
```

Every region must be `ok` or `stale` — investigate any `failed`.

- [ ] **Step 6: Run the whole suite and lint**

```bash
cd . && .venv/bin/python -m pytest -v && .venv/bin/ruff check src tests
```

Expected: all tests pass, ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/velox/cli.py tests/test_cli.py data cache
git commit -m "feat: pipeline orchestration and first published snapshot"
```

---

### Task 12: Scheduled workflow, Pages, and the coordinate review page

**Files:**
- Create: `.github/workflows/ingest.yml`, `review/index.html`, `README.md`

**Interfaces:**
- Consumes: `python -m velox.cli ingest`
- Produces: a published snapshot on GitHub Pages; a static page for verifying camera coordinates

- [ ] **Step 1: Write the ingest workflow**

`.github/workflows/ingest.yml`:

```yaml
name: ingest
on:
  schedule:
    - cron: "0 6 * * 1"   # Mondays 06:00 UTC, when the weekly PDFs are republished
    - cron: "0 7 * * *"   # daily retry, so a Monday failure does not cost a week
  workflow_dispatch:

permissions:
  contents: write

jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: sudo apt-get update && sudo apt-get install -y poppler-utils
      - run: pip install -e ".[dev]"
      - run: pytest -q
      - run: python -m velox.cli ingest --root data
      - name: Commit snapshot
        run: |
          git config user.name "velox-bot"
          git config user.email "velox-bot@users.noreply.github.com"
          git add data cache
          git diff --staged --quiet || git commit -m "data: snapshot $(date -u +%Y-%m-%d)"
          git push
```

Note the order: `pytest` runs **before** ingest, so a parser regression blocks publication
rather than committing bad data.

- [ ] **Step 2: Write the coordinate review page**

`review/index.html` — a self-contained page that loads `../data/latest/fixed_cameras.json`,
plots each camera on an OpenStreetMap tile layer via Leaflet loaded from a CDN, and lists them
with their source row so a human can confirm or correct each point.

```html
<!doctype html>
<meta charset="utf-8">
<title>Velox Italia — verifica coordinate</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  body { font: 15px system-ui, sans-serif; margin: 0; display: flex; height: 100vh; }
  #list { width: 420px; overflow-y: auto; border-right: 1px solid #cbd5e1; }
  #map { flex: 1; }
  .row { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; cursor: pointer; }
  .row:hover { background: #f1f5f9; }
  .row.bad { background: #fef2f2; }
  .meta { color: #334155; font-size: 13px; }
</style>
<div id="list"></div>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map = L.map('map').setView([42.5, 12.5], 6);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  { attribution: '© OpenStreetMap' }).addTo(map);

fetch('../data/latest/fixed_cameras.json').then(r => r.json()).then(cameras => {
  const list = document.getElementById('list');
  cameras.forEach(camera => {
    const row = document.createElement('div');
    row.className = 'row' + (camera.lat == null ? ' bad' : '');
    row.innerHTML = `<b>${camera.road_name}</b> km ${camera.km_raw}
      <div class="meta">${camera.comune} (${camera.province}) ·
      ${camera.direction_raw ?? 'senza direzione'} ·
      ${camera.geocode_confidence}</div>`;
    if (camera.lat != null) {
      const marker = L.marker([camera.lat, camera.lon]).addTo(map)
        .bindPopup(`${camera.road_name} km ${camera.km_raw}<br>${camera.comune}`);
      row.onclick = () => { map.setView([camera.lat, camera.lon], 15); marker.openPopup(); };
    }
    list.appendChild(row);
  });
  document.title += ` — ${cameras.length} postazioni`;
});
</script>
```

- [ ] **Step 3: Write the README**

`README.md` must state: what the project is, that data comes from the Polizia di Stato and MIT,
that coverage is Polizia Stradale only, how to run the pipeline locally, and how to run the tests.

- [ ] **Step 4: Create the GitHub repository and push**

```bash
cd .
gh repo create velox-italia --private --source=. --remote=origin --push
gh api -X POST repos/:owner/velox-italia/pages -f "source[branch]=main" -f "source[path]=/" \
  2>/dev/null || echo "enable Pages manually in repo settings if this failed"
```

- [ ] **Step 5: Verify CI passes on the pushed repository**

```bash
cd .
gh run list --limit 5
gh run watch $(gh run list --limit 1 --json databaseId -q '.[0].databaseId')
```

Expected: the `test` workflow succeeds. Fix any failure before proceeding.

- [ ] **Step 6: Trigger a real scheduled run manually**

```bash
gh workflow run ingest.yml
sleep 30
gh run watch $(gh run list --workflow=ingest.yml --limit 1 --json databaseId -q '.[0].databaseId')
```

Expected: the run completes and commits a snapshot.

- [ ] **Step 7: Commit**

```bash
git add .github review README.md
git commit -m "feat: scheduled ingest workflow, coordinate review page, README"
git push
```

---

## Self-Review

**Spec coverage.** §2.1 → Tasks 2, 5. §2.2 → Tasks 2, 6. §2.3 → Task 7. §2.5 noted in README (Task 12). §4 → Tasks 3, 11, 12. §4.1 → Tasks 8, 9, 12 (review page). §4.2 is the iOS plan. §5 → Tasks 2, 5, 6, 10, 12 (test-before-ingest ordering). §6 and §7 are the iOS plan. §8 → golden-file tests in Tasks 5, 6; zero-row guard in Task 10. §9 boundaries → the module split throughout.

**Deviation from the spec, recorded deliberately:** §4.1 specifies a one-off local build of road geometry from a 2 GB OSM extract. Tasks 8 and 11 replace this with on-demand Overpass queries backed by a committed cache, which removes the only manual step and makes the pipeline fully CI-runnable. The published schema is unchanged.

**Placeholder scan:** none. Every step carries runnable code or an exact command.

**Type consistency:** `pdf_to_text` is defined in `parse_mobile` (Task 5) and imported by `parse_fixed` (Task 6) and `cli` (Task 11). `cache_key` is defined in `overpass` (Task 8) and used in `cli` (Task 11). `_haversine_m` is defined in `overpass` (Task 8) and imported by `geocode_fixed` (Task 9). `MobileCheck` fields match between Tasks 5 and 11. `RegionStatus` is produced in Task 10 and consumed via `region_statuses_to_dict` in Task 11.
