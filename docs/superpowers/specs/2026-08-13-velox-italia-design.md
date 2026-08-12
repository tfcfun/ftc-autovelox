# Velox Italia — Design

**Date:** 2026-08-13
**Status:** Approved design, ready for implementation planning
**Working name:** `velox-italia` (public App Store name decided at launch; nothing in this design depends on it)

---

## 1. Purpose

The Polizia di Stato publishes, every Monday, where its mobile speed checks will run that
week, plus a national list of fixed installations. The data is public but awkward: twenty
regional PDFs plus two national ones, re-published to URLs that move. Nobody consults it
before driving because consulting it is a chore.

This app answers one question: **"I am driving from A to B on day D — what speed enforcement
is published for my route?"** It then optionally warns during the drive.

Framing is deliberate and load-bearing: this is a road-safety and transparency tool built on
data the police publish precisely so drivers slow down. It is not a fine-avoidance tool. That
framing satisfies App Store Review Guideline 1.4.4 and should govern all user-facing copy.

## 2. Data sources

### 2.1 Weekly mobile checks — Polizia di Stato

Twenty regional PDFs linked from
`https://www.poliziadistato.it/articolo/autovelox-e-tutor-dove-sono`, under the `Documenti`
block, at paths of the form `/statics/<NN>/<regione>.pdf`. Refreshed Mondays.

Verified content (Lombardia, week 10–16 August 2026, complete):

```
Validità da lunedì 10 agosto 2026 a domenica 16 agosto 2026
Giorno        Tratto stradale                  Provincia
14/08/2026    Strada Statale  SS / 9 via Emilia    LO
15/08/2026    Autostrada      A / 07 Milano-Genova PV
16/08/2026    Strada Statale  SS / 9 via Emilia    LO
```

Fields: **date, road type, road reference, road name, province.** No kilometre, no direction,
no comune. Volume is very low — single-digit rows per region per week is normal.

Precision ceiling: a road within one province. Typically tens of kilometres, not a point.

### 2.2 Fixed installations — Polizia di Stato

Two national PDFs, same `Documenti` block:
`mvpostazionefissaaut_*.pdf` (motorways, ~60 rows) and `mvpostazionefissaord_*.pdf`
(ordinary roads, ~100 rows). Updated every few years, not weekly.

Verified content:

```
Regione   Autostrade e Trafori   Chilometro  Direzione  Comune                Prov
Veneto    Torino – Trieste       423+850     Ovest      Noventa di Piave      VE
Toscana   Firenze - Pisa Nord    35,500      Ovest      Serravalle Pistoiese  PT
Piemonte  Traforo del Frejus     Interno gal. FRANCIA   Bardonecchia          TO
```

Fields: **region, road, kilometre, direction, comune, province.** Kilometre formatting is
inconsistent across rows (`423+850`, `35,500`, free text such as `Interno galleria`).

Precision ceiling: a point, once geocoded. Good enough for proximity alerts.

### 2.3 MIT device register

`https://velox.mit.gov.it/dispositivi` is a DataTables front end over an unauthenticated JSON
endpoint `https://velox.mit.gov.it/dispositivi/data` (standard DataTables server-side
parameters: `draw`, `start`, `length`). **4,110 rows** as of 2026-08-13.

Fields: `codice_accertatore`, `denominazione_accertatore`, `codice_catastale_accertatore`,
`n_decreto`, `data_decreto`, `tipo_dispositivo`, `marca_dispositivo`, `modello_dispositivo`,
`versione_dispositivo`, `matricola_dispositivo`, `note`, `created_at`,
`data_primo_inserimento`.

**This register contains no location data.** There is no road, kilometre, or coordinate
field. The only geography is `codice_catastale_accertatore`, the Belfiore code of the
*authority owning the device* — 1,595 comuni across 1,567 enti. Four rows contain a location
typed by hand into `tipo_dispositivo`; these are anomalies, not a schema.

`tipo_dispositivo` is free text with over 500 distinct spellings of what are essentially two
categories (`FISSO`, `fisso`, `Fisso `, `FISSO7MOBILE`, `Molbile`, `NESSUN VELOX`,
`//////////////////////////////////`, and several rows containing dates). Any use of this
field requires a normalisation table.

**Consequence:** MIT cannot contribute to the map. It powers a separate fine-validity lookup
(§6.5), which is genuinely useful because since 28 November 2025 only registered devices can
issue a valid fine.

### 2.4 Coverage limit — must be surfaced in the UI

The map covers **Polizia Stradale enforcement only**. The majority of Italian fixed cameras
belong to comuni and local police and appear in no official geolocated dataset. The app must
never imply full coverage. See §7.

### 2.5 Licensing

The Polizia di Stato site carries a Creative Commons BY-NC-ND notice. The app is free, and
raw facts are not themselves protected, but the licence should be reviewed before publishing
under a named developer account.

## 3. Scope

**In scope for v1**

- Route A→B with a day picker; ordered list of published checks along the route.
- Map: route, fixed cameras as pins, scheduled roads highlighted.
- Trip mode: opt-in, explicit, in-drive voice and banner alerts.
- Browse by region for the current week.
- MIT fine-validity lookup.
- iOS only.

**Out of scope for v1**

User reports or crowdsourcing (would forfeit the Guideline 1.4.4 exemption), accounts,
CarPlay and Android Auto, always-on background monitoring, Android.

## 4. Architecture

No runtime server. A scheduled job produces a static dataset; the app consumes it and works
offline.

```
GitHub Actions cron (Mon 06:00 UTC + daily retry)
  ├─ scrape poliziadistato.it, resolve current PDF hrefs
  ├─ download 20 regional + 2 fixed PDFs
  ├─ download velox.mit.gov.it/dispositivi/data
  ├─ parse → normalise → geocode → validate
  └─ commit data/<year>-W<week>/*.json and data/latest.json
        ↓
    GitHub Pages (static CDN)
        ↓
    iOS app: fetch, cache, operate offline
```

**Compute:** GitHub-hosted runners. Nothing runs on the developer's machine or any VPS. The
job downloads ~5 MB and completes in a few minutes. Free at this volume on both public repos
and the private-repo allowance.

**Audit trail:** each week is a commit, so week-over-week change is a readable diff and a
parser regression shows up as an implausible diff before it reaches any phone. Failed
workflows email the owner — this is the alerting mechanism §5 depends on.

**Repository:** a standalone GitHub organisation, not tied to existing personal or company
repos. Note separately that the App Store listing publishes the seller name — an individual
developer account shows a legal name, an organization account (requiring D-U-N-S) shows a
company name. That is a launch decision independent of the repo.

### 4.1 Two datasets built once, reused thereafter

**Fixed-camera coordinates.** Converting `A4, km 423+850, dir Ovest` to a coordinate is the
hardest transformation in the system: automatic interpolation along OSM road geometry drifts,
because Italian kilometre posts count from historical origins rather than from the way's
start. The mitigating fact is size — roughly 160 points in files updated every few years.

Procedure: geocode automatically, **verify by hand once**, commit the result as curated
GeoJSON. Re-verification is triggered only when a source PDF's content hash changes. The
verification is reviewed as a pull request.

**Road-by-province polylines.** For each `(road reference, province)` pair, a simplified
polyline derived from OpenStreetMap. This is what makes "SS9, provincia di Lodi" intersectable
with a route.

Built once from the Italy OSM extract (~2 GB) on a local machine; the simplified output (a
few MB) is committed. This is **not** part of the weekly cycle and does not run on a GitHub
runner.

### 4.2 Client-side routing

`MKDirections` supplies the route polyline: on-device, no API key, no third-party account, no
per-request cost. Matching is then pure geometry against the cached dataset:

- **Fixed camera** — point within ~500 m of the route polyline, ordered by distance along it.
- **Mobile check** — the `(reference, province)` polyline overlaps the route, and the
  scheduled date matches the selected day.

Because both sides are geometry, road-name vocabulary (`S.S. 16` vs `SS16` vs
`SS / 16 Adriatica`) is reconciled once during ingest and never at runtime.

## 5. Ingest rules and failure modes

**Governing principle: a missing row is not an all-clear.** An empty parse and a genuinely
quiet week are indistinguishable downstream, so the pipeline must be structurally incapable of
letting absence render as safety.

| Failure | Handling |
|---|---|
| PDF href moved (`/statics/<NN>/` renumbers on republish) | Resolve from the page every run. If the `Documenti` block is not found, **fail the run**. Never fall back to a hardcoded path. |
| A region parses to zero rows | Do not publish. Retain last-good for that region, mark it stale, alert. Single-digit row counts are normal, so zero looks plausible and is therefore dangerous. |
| Individual row unparseable | **Quarantine** it, publish the rest, record the count in the snapshot. Never infer a date or road from a malformed line. |
| Kilometre in an unrecognised format | Quarantine. Never interpolate from a value that was not understood. |
| Snapshot older than 8 days | App shows a persistent *dati non aggiornati* banner. |
| MIT endpoint shape changes | Lookup degrades to unavailable; map and routing are unaffected. |

**Per-region status.** Each region carries its own `updated_at` and row count. One region
failing must never blank another.

**Idempotent and versioned.** Every run writes a new immutable snapshot; the app pins one and
can roll back. Per-region, per-week row counts are logged so a source format change appears as
a step change rather than as silence.

**Parser implementation is deterministic, not model-based.** `pdftotext -layout` plus explicit
rules: exact, free, and testable against committed fixtures. A language model asked to parse a
page it cannot read produces a well-formed invented row rather than an error, which is the
precise failure this section exists to prevent. A model may assist *after* extraction — triaging
the quarantine pile, describing a layout change so a failed run arrives with a diagnosis — but
is never the source of truth.

## 6. Application

### 6.1 Percorso

Origin, destination, day picker defaulting to today.

### 6.2 Risultato

Map (route drawn, fixed cameras pinned, scheduled roads highlighted) above an ordered list.
Each row shows type, road, kilometre and direction or province, the applicable day, and
distance along the route. A `Naviga` action hands off to Apple or Google Maps.

### 6.3 Modalità viaggio

Armed by explicit tap from the result screen; **off by default**. Displays the next check
ahead and its distance. Functions with the screen off.

- Permissions: `When In Use` plus the background-location mode. Never ambient, never `Always`.
- **Fixed camera:** alert at ~800 m, **only when heading matches the recorded direction** — a
  `dir Ovest` camera must stay silent for eastbound traffic. One alert per camera per trip.
- **Mobile check:** fires once on entering the `(road, province)` polyline, and only when the
  scheduled date is the current date.
- **Suppression:** require position within ~30 m of the road centreline (so a motorway does not
  fire for the road beneath it), require speed above a walking threshold, apply a cooldown.
- **Audio:** short spoken Italian, ducking music or podcast rather than interrupting it.
- **Copy:** *"Controllo velocità tra 800 metri — rispetta il limite."* The limit, never the fine.

### 6.4 Regione

Browse the current week by region. The dataset is small enough to read in full.

### 6.5 Controlla la multa

Search the MIT register by ente, marca, modello, or matricola, to check whether the device
named on a verbale is registered. No geocoding, no map.

### 6.6 Info

Source attribution, publication date of the loaded snapshot, and the coverage limit stated
plainly.

## 7. Language constraints

The UI may never state or imply:

- "nessun autovelox" — the app knows only Polizia Stradale enforcement
- "strada libera" or any equivalent all-clear
- that absence of a published check means a road is unmonitored

The only accurate empty state is *"nessun controllo della Polizia Stradale pubblicato per
questa data"*, shown alongside the snapshot's publication date.

## 8. Testing

- **Golden files.** Commit real source PDFs as fixtures; assert exact parser output. Any future
  format change surfaces as a failing test rather than a corrupted week of data.
- **Zero-row guard** gets a dedicated test: an empty region must publish nothing.
- **Geometry:** synthetic routes with known intersections *and* known near-misses — a parallel
  road 100 m away must not match.
- **Trip mode by GPX replay.** Recorded traces driven through the alert engine, asserting what
  fires and what stays silent, including a wrong-direction pass that must produce no alert. The
  driving feature is testable without driving.

## 9. Component boundaries

| Component | Responsibility | Depends on |
|---|---|---|
| `scraper` | Resolve current source URLs, download, hash | Polizia di Stato page, MIT endpoint |
| `parser` | PDF/JSON → normalised rows, quarantine bad rows | `scraper` output only |
| `geocoder` | Fixed rows → coordinates; road refs → polylines | `parser` output, OSM extract |
| `publisher` | Validate, version, write snapshot | `parser`, `geocoder` |
| `matcher` (app) | Route polyline × dataset → ordered findings | snapshot only |
| `alert engine` (app) | Position stream × findings → alerts | `matcher` output, CoreLocation |
| `mit lookup` (app) | Text search over device table | snapshot only |

Each is independently testable: the parser needs no network, the matcher needs no GPS, the
alert engine needs no map.

## 10. Open decisions

These do not block implementation planning:

- Public App Store name and icon.
- Developer account type (individual vs organization), which determines the published seller
  name.
- Whether to review the CC BY-NC-ND notice with a lawyer before launch.
