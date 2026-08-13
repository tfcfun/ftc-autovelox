# Velox Italia — Handover

Built overnight, 12–13 August 2026. This document says what works, what is
waiting for you, and what I got wrong along the way.

## What works, verified

**Data pipeline** — 87 Python tests, ruff clean. One command produces a
validated snapshot:

```bash
cd .
.venv/bin/python -m velox.cli ingest --root data
```

The published snapshot (`data/latest/`, week 2026-W33):

| | |
|---|---|
| Mobile checks | 134 nationally, 103 with route geometry |
| Fixed cameras | 55, of which 54 placed |
| MIT devices | 4,110 |
| Road segments | 45 |
| Region status | 16 `ok`, 4 `empty`, 0 `failed` |
| Quarantined rows | 2 |

**iOS app** — 43 Swift tests, builds clean for the iOS 26.5 simulator, runs
with the real data bundled offline. Screens in `docs/screenshots/`.

```bash
cd ios && xcodegen generate
xcodebuild -project VeloxItalia.xcodeproj -scheme VeloxItalia \
  -destination 'platform=iOS Simulator,name=iPhone 17' -derivedDataPath build build
cd VeloxKit && swift test
```

`-velox.tab route|region|multa|info` opens the app straight to a tab, which is
how the screenshots were captured without driving the UI.

## What is waiting for you

1. **Developer account type.** An individual account publishes your legal name
   on the App Store listing; an organization account (needs D-U-N-S) publishes a
   company name. For an app about speed enforcement that is worth a moment's
   thought. Nothing in the code depends on it.
2. **Signing, TestFlight, submission.** Needs your Apple ID interactively.
3. **The coordinate review pass.** 54 cameras are placed from their comune and
   are accurate to roughly 1–2 km. Open `review/index.html` against
   `data/latest/`, drag each pin onto the real installation, and set
   `verified: true`. **Until you do, none of them fire proximity alerts** — the
   app only warns on points a human confirmed. This is the single highest-value
   hour you can spend on the project.
4. **GitHub Pages.** Deliberately left OFF. The repo is private. Turning Pages
   on publishes the data at a public URL, which is your call, not mine. The app
   reads `https://tfcfun.github.io/velox-italia/data/latest/`, so the
   remote refresh does nothing until you enable it — the bundled seed covers the
   app in the meantime.
5. **CC BY-NC-ND.** The Polizia di Stato site carries that notice. A free app
   and raw facts are a comfortable position, but worth a look before you publish
   under your own name.

## What I got wrong, and what it cost

Recorded because the mistakes are more useful than the successes.

- **My own Overpass query was broken.** The plan specified a regex on
  `ISO3166-2` plus extra filters, which scans every area and returns 504. Caught
  before an agent implemented it. Exact `["ISO3166-2"="IT-LO"]` runs in 7.5 s.
- **I claimed the fixed-camera parser had lost a row.** It hadn't — my
  verification grep required three digits after the `+` and silently missed
  `609+00`. The parser was right and my check was wrong.
- **The name→ref approach was a dead end.** I built a resolver that matched PDF
  road denominations against OSM route relations, wrote 15 tests for it, then
  proved it could not work: the A1 relation is not named after its endpoints,
  and two `["name"~...]` filters on one key return zero instead of ANDing. I
  deleted it rather than leave code that looked like a solution.

## Things that were nearly shipped wrong

- **Every fixed camera had null coordinates.** The PDFs name roads
  descriptively — "Milano – Napoli", "Appia", "Del Vesuvio" — and never by
  reference, so `road_ref` was `None` for all 56 and geocoding returned early.
  The precise layer that justifies the whole trip-mode feature was going to ship
  empty. The comune turned out to carry both the missing reference and a usable
  point: Noventa di Piave contains 18 motorway ways, all tagged `A4`, centroid
  1.2 km from the real camera.
- **Comune lookup was blind to whole regions.** OSM names Claut
  `Claut / Cjolt` — Italian and Friulian in one tag — so an anchored name match
  found nothing across Friuli, Alto Adige and Valle d'Aosta. Also every
  `Sant'…` and `d'…` comune failed, because the PDFs use a curly apostrophe and
  OSM a straight one. Both failures were silent: an empty reply looks exactly
  like a comune with no roads.
- **Four regions were reported as `failed` when they had published a zero.**
  Molise's PDF literally reads *"Servizi di controllo velocità non programmati
  nella settimana"*. Treating that as a failure is the project's founding
  mistake pointed the other way: it lets a broken feed look like a quiet week.
  Region status is now `ok` / `empty` / `stale` / `failed`.
- **One bad road sank the entire run.** The Overpass calls were unguarded, so a
  single road exhausting its retries aborted the weekly ingest. For an
  unattended job that means one flaky road silently costs a week.

## Known imperfections, deliberately left

- **`Meseno` (MI) is unplaceable.** There is no such comune — the official PDF
  misprints `Mesero`. It is left unplaced rather than silently corrected;
  inventing a fix to official data is not the pipeline's job. It will show on
  the review page.
- **`SP656/CH` and `SS277/FR` have no OSM geometry.** Genuinely absent, not
  rate-limited. Those checks appear in the region browse but cannot match a
  route. Empty results are never cached, so they retry every run — if they stay
  absent, consider a TTL'd negative cache.
- **The official ordinary-roads PDF prints one camera twice** (Potenza–Melfi
  km 2+600, filed under both Campania and Basilicata). Collapsed on the physical
  installation, with opposite carriageways kept separate.
- **The Friuli block prints no road name**, so those rows carry `?`.
- **Two rows are quarantined** — the Frejus tunnel, whose kilometre column is
  free text. Refused rather than guessed.
- Test fixtures include both the 2021 and the current 07/10/2025 edition of the
  motorway list, because the live file had moved on and the tests were guarding
  a file we no longer download.

## The rule the whole thing is built on

A missing row is never an all-clear, and a published zero is never a failure.
The pipeline refuses to publish a region that parses to nothing, quarantines
rather than guesses, and blocks the snapshot outright on duplicate ids — it did
exactly that on the first real run, which is how the Reggio Emilia id collision
was found. The app cannot say "nessun autovelox" or "strada libera"; a test
asserts it. Coverage is Polizia Stradale only, and the UI says so.
