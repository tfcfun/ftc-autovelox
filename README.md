# Velox Italia

A scheduled data pipeline that turns the official Polizia di Stato speed-check
publications and the MIT approved-device register into a validated, versioned,
static JSON snapshot, consumed by the Velox Italia iOS app.

## Data sources

- **Polizia di Stato** — the weekly regional PDFs of planned mobile speed
  checks and the two fixed-installation lists (motorways and ordinary roads),
  resolved from the live page on every run because the published URLs move:
  <https://www.poliziadistato.it/articolo/autovelox-e-tutor-dove-sono>
- **MIT** — the register of approved speed-measurement devices:
  <https://velox.mit.gov.it/>

**Coverage is Polizia Stradale only.** Municipal and provincial police
installations are not in these sources and are therefore not in this data.
An absent entry is never an all-clear.

## How it works

`python -m velox.cli ingest` resolves the source URLs, downloads the PDFs,
parses them deterministically with `pdftotext -layout` (no language model in
the extraction path), normalises road refs / kilometres / provinces against
closed value sets, geocodes via the Overpass API with a permanent committed
cache (`cache/segments/`), and writes an immutable weekly snapshot under
`data/<year>-W<week>/` plus a copy in `data/latest/`.

Rows that do not match their expected shape are quarantined with the raw text
and a reason — never guessed. A region that parses to zero rows is published
as `stale` (retaining last-good) or `failed`, never as an empty all-clear.

GitHub Actions runs the pipeline every Monday at 06:00 UTC with a daily retry
(`.github/workflows/ingest.yml`). Tests run before ingest so a parser
regression blocks publication.

## Running locally

Requires Python 3.12 and `poppler-utils` (`pdftotext`).

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m velox.cli ingest --root data
```

## Tests

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
```

## Coordinate review

`review/index.html` plots every fixed camera on an OpenStreetMap layer so the
interpolated coordinates can be verified by hand. Cameras that could not be
placed are listed with a red background and are excluded from proximity alerts
by the app.
