# App Store metadata — FTC Autovelox

Copy here is public-facing and load-bearing for review. Guideline 1.4.4 permits
only law-enforcement-published data and prohibits encouraging excessive speed, so
every line names the source and speaks about the limit, never about avoiding a
fine.

## Name

```
FTC Autovelox
```

Home-screen name (`CFBundleDisplayName`) is the same and fits without truncation
— verified on an iPhone 17 home screen, see `docs/screenshots/homescreen.png`.

## Subtitle (max 30 characters)

```
Autovelox - dati PDS
```

20 characters, used as the SUBTITLE behind the app name "FTC Autovelox".

"dati PDS" states the app USES their data rather than claiming to be theirs.
That framing is what keeps it clear of the affiliation problem: a police
abbreviation in the app NAME would imply the app is the force's own, which
Apple rejects; naming them as the source is normal and expected.

Alternatives, if the abbreviation proves too opaque for users:

| | chars |
|---|---|
| Autovelox - dati Polizia | 24 |
| Controlli Polizia Stradale | 26 |
| Dati della Polizia Stradale | 27 |

## Description

```
FTC Autovelox scarica e legge automaticamente le pubblicazioni della Polizia
di Stato, così non devi più andare a cercarle sul sito e aprire i PDF.

Ogni lunedì la Polizia Stradale pubblica dove saranno attivi i controlli di
velocità con apparecchiature mobili, regione per regione, e mantiene l'elenco
delle postazioni fisse su autostrade e strade ordinarie. FTC Autovelox legge
queste pubblicazioni e te le mostra sul percorso che stai per fare.

• Inserisci partenza e arrivo e scegli il giorno: vedi i controlli pubblicati
  lungo la tua strada, in ordine di percorrenza.
• Consulta la settimana regione per regione.
• Modalità viaggio opzionale: un avviso vocale quando entri in un tratto
  controllato. È spenta finché non la attivi tu.
• Verifica se il dispositivo indicato su un verbale è presente nell'elenco
  dei dispositivi censiti dal MIT.

DOVE SI TROVA ESATTAMENTE
Le fonti ufficiali indicano la strada, il comune, il chilometro e la direzione,
ma non pubblicano coordinate. L'app disegna quindi il TRATTO lungo il quale si
trova la postazione, non un punto inventato. Quando l'informazione non c'è, l'app
lo dice.

COSA NON C'È
Sono inclusi solo i controlli pubblicati dalla Polizia Stradale. Gli autovelox
gestiti dai comuni e dalle polizie locali non compaiono in nessun elenco
ufficiale con le posizioni, quindi non sono nell'app. L'assenza di una
segnalazione non significa che una strada non sia controllata.

Nessuna segnalazione inserita dagli utenti: i dati vengono esclusivamente dalle
pubblicazioni ufficiali.

Rispettare i limiti di velocità non è solo un obbligo: è la misura più efficace
per ridurre gli incidenti.
```

## Fonti citate nella scheda

- Polizia di Stato — https://www.poliziadistato.it/articolo/autovelox-e-tutor-dove-sono
- MIT — https://velox.mit.gov.it/dispositivi

## Review notes (for App Review, not public)

Entered verbatim in App Store Connect. Covers the two questions a reviewer will
actually have: where the data comes from, and why the app uses background
location.

```
DATA SOURCE
All speed-check data in this app is published by Italian law enforcement: the
Polizia di Stato (Polizia Stradale) weekly programme of mobile speed checks and
its national lists of fixed installations, plus the Ministry of Infrastructure
and Transport register of approved devices. The app contains NO user-submitted
reports of any kind and has no mechanism to add them.
https://www.poliziadistato.it/articolo/autovelox-e-tutor-dove-sono
https://velox.mit.gov.it/dispositivi

LOCATION USE
The app requests When In Use location only. It never requests Always. Background
location is used solely while the user has explicitly started "Modalita viaggio"
(trip mode) from the results screen, so that a spoken warning can be given when
entering a road stretch where a check is published. Trip mode is off by default
and stops when the user ends it.

NO ACCOUNT
The app has no sign-in, no accounts and no server backend. It reads a static
JSON dataset published at https://tfcfun.github.io/ftc-autovelox/data/latest/
and works offline from a bundled copy.

FRAMING
All in-app wording refers to respecting the speed limit. The app cannot and does
not state that a road is clear: the sources cover Polizia Stradale enforcement
only, and this limitation is stated in the app's Info screen and in the App
Store description.
```

"Sign-in required" must stay UNCHECKED - the app has no accounts, and leaving
the default ticked with blank credentials stalls review.

## App Store Connect record

| | |
|---|---|
| Apple ID | 6801183288 |
| Bundle ID | com.tfcfun.autovelox |
| SKU | ftc-autovelox-001 |
| Primary language | Italian |
| Category | Navigation |
| Support URL | https://github.com/tfcfun/ftc-autovelox |
| Copyright | 2026 FTC |
| Keywords | autovelox,tutor,polizia stradale,controlli velocita,multa,limiti,percorso,statali,viaggio |

Screenshots: `docs/store-screenshots/65/` at 1284x2778. Captured on an iPhone 17
Pro Max (1320x2868, the 6.9" size) then scaled to width and cropped 12px, since
App Store Connect's slot on this record wants the 6.5" dimensions.

## Still to decide

- Developer account type. An individual account publishes your legal name as the
  seller; an organization account (requires D-U-N-S) publishes a company name.
- Whether to review the CC BY-NC-ND notice on the Polizia di Stato site before
  publishing.
