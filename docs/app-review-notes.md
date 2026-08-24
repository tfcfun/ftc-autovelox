# App Review Information — Notes field

Paste into App Store Connect: App Information → App Review Information → Notes.
Apple's 2.1 reply asked for this ("Include this information in the Notes field
of the App Review Information section for future submissions"). Keeping it here
so it survives a browser mishap and carries to future versions.

---

HOW TO EVALUATE THIS APP FROM OUTSIDE ITALY

Content covers Italian roads only, because the sources are Italian State Police publications. From a review location outside Italy, anything using current position correctly shows nothing nearby. That is intended, not a fault.

To exercise every feature from anywhere:
- REGIONE tab: choose "Lombardia" for real current-week data. No location needed. Fastest proof it works.
- PERCORSO tab: type "Milano" and "Bologna", tap Calcola. Do not use "Usa la mia posizione" outside Italy.
- MULTA tab: type "Autovelox" to search the Ministry device register.
- INFO tab: "Prova avviso vocale" plays a sample spoken alert.

WHAT IT DOES
Every Monday the Italian State Police publish where speed checks will run that week, across 20 regional PDFs. The app reads them automatically and shows what is published along a route. For drivers in Italy, in Italian.

SETUP
No account, login, credentials or sample files. Works on first launch and offline. Four tabs: PERCORSO, REGIONE, MULTA, INFO. Two driving modes, off by default, each started by an explicit tap: Modalita viaggio and Modalita live.

LOCATION
Requested only on an explicit tap. When In Use only, never Always. Background location is used solely while the user has explicitly started Modalita viaggio or Modalita live, and stops when the user ends them. Purpose string: "Serve a segnalarti i controlli di velocita pubblicati dalla Polizia Stradale lungo il percorso, solo mentre la modalita viaggio e attiva." Processed on device, never transmitted or stored. Note that iOS does not capture system permission dialogs in screen recordings.

EXTERNAL SERVICES
One static JSON file on GitHub Pages, https://tfcfun.github.io/ftc-autovelox/data/latest/ , fetched by plain GET, sending no user data. MapKit, CoreLocation, AVSpeechSynthesizer, all on device. No third-party SDKs, no backend, no accounts. App Privacy: Data Not Collected.

SOURCES AND FRAMING (GUIDELINE 1.4.4)
https://www.poliziadistato.it/articolo/autovelox-e-tutor-dove-sono
https://velox.mit.gov.it/dispositivi
Both public and open, no credentials. The app reproduces facts (road, date, province, km), not the documents, and credits both in-app and on the product page. It contains no user-submitted reports and no way to add any: it shows only what law enforcement itself publishes. All in-app wording refers to respecting the speed limit, never to avoiding a fine. The app cannot and does not state that a road is clear - it covers Polizia Stradale enforcement only, and says so in the Info screen and the App Store description.

TESTED ON
iPhone 17 Pro Max, iOS 26.5, physical device. Also iOS 26.5 Simulator. Deployment target iOS 17.0, iPhone only.
