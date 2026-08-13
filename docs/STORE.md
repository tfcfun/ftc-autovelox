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
Controlli Autovelox PDS
```

23 characters. Used as the SUBTITLE, with "FTC Autovelox" as the app name.

That distinction matters. A police abbreviation in the app NAME would imply the
app is the force's own, which Apple rejects; as a subtitle behind a distinct
brand name it simply describes what the app covers, which is the normal pattern.

Residual consideration is clarity, not compliance: "PDS" is not a common
abbreviation in everyday Italian - people say "Polizia" or "Polizia Stradale" -
and the subtitle is the one-line pitch on the store card.

Alternatives, same meaning, spelled out:

| | chars |
|---|---|
| Controlli Polizia Stradale | 26 |
| Dati della Polizia Stradale | 27 |
| Autovelox: fonti ufficiali | 26 |
| Pubblicazioni Polizia Stradale | 30 |
| Dove si controlla la velocità | 29 |

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

```
All camera and speed-check data in this app is published by Italian law
enforcement (Polizia di Stato) and by the Ministry of Infrastructure and
Transport. The app contains no user-submitted reports of any kind. Source URLs:
https://www.poliziadistato.it/articolo/autovelox-e-tutor-dove-sono and
https://velox.mit.gov.it/dispositivi
```

## Still to decide

- Developer account type. An individual account publishes your legal name as the
  seller; an organization account (requires D-U-N-S) publishes a company name.
- Whether to review the CC BY-NC-ND notice on the Polizia di Stato site before
  publishing.
