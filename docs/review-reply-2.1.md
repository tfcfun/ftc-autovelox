# Reply to App Review — Guideline 2.1, Information Needed

Submission ID 9c3d94e1-7a73-41c1-987f-781cb3798dd0.

**PASTE EVERYTHING BELOW THE RULE INTO THE RESOLUTION CENTER.** Attach the screen
recording to the same reply. Do not send answers 2–7 without the video, and do not
send the video without answers 2–7 — a partial reply is what left this submission
at Unresolved Issues from 16 to 23 August.

---

1. SCREEN RECORDING

Attached: a screen recording captured on a physical iPhone 17 Pro Max running
iOS 26.5, from a TestFlight install of build 0.1(2). It begins with launching the
app and follows the typical user flow through every core feature.

Of the four categories listed in your request, only one applies to this app:

- Account registration, login, account deletion — **not applicable.** The app has
  no accounts and no login of any kind.
- Paid content, purchases, subscriptions — **not applicable.** The app is free and
  contains no purchases or subscriptions.
- User-generated content — **not applicable.** Users cannot submit, report or
  block content. All data comes from official publications; there is no user
  contribution mechanism, by design.
- **Prompts requesting access to sensitive data or device capabilities —
  included, with one limitation we want to flag honestly.** The app was deleted
  and reinstalled from TestFlight immediately before recording, so this is a
  genuine first launch with no prior permission granted. At **0:16** the
  recording shows the app requesting location: the screen dims and the control
  shows its loading state while the system alert is presented, and immediately
  afterwards the departure field is populated from the device's position, which
  is only possible once the request was granted.

  **The system alert itself does not appear in the video because iOS does not
  include system permission dialogs in screen recordings** — they are rendered
  outside the app's window. This is a platform limitation, not an omission. If a
  recording of the dialog itself is required, we can film the device screen with
  a second camera and send that; please just ask.

  For completeness, the location purpose string presented in that alert is quoted
  at the end of this item.

The recording was made in Italy, so it also shows the app doing what it cannot
demonstrate from a review location outside Italy: resolving a real current
position, and reporting the distance to the next published speed check ahead on
the road. Please see the note under item 3 on evaluating the app from outside
Italy — we believe that is why the app was difficult to assess.

Index of the recording (1:57 total):

    0:00  Launch from a closed state, fresh TestFlight install — no account,
          no login, no setup, no credentials, no sample files
    0:16  Location requested on first use (see the note above)
    0:20  PERCORSO — departure filled from the device's real position in Italy
    0:52  REGIONE (Liguria) — the week's published checks, and a region with no
          fixed installations stated explicitly as such
    1:08  MULTA — search of the Ministry register of approved devices
    1:20  INFO — sources, coverage limits, current data week (2026-W34), and the
          sample spoken alert (audible)

The app's location purpose string, shown in the prompt, reads:

    "Serve a segnalarti i controlli di velocità pubblicati dalla Polizia
     Stradale lungo il percorso, solo mentre la modalità viaggio è attiva."

("Used to alert you to the speed checks published by the Polizia Stradale along
your route, only while trip mode is active.")

2. DEVICE MODELS AND OPERATING SYSTEMS TESTED

iPhone 17 Pro Max running iOS 26.5 (physical device, via TestFlight build 0.1(2)).
Additional verification on the iOS 26.5 Simulator (iPhone 17, iPhone 17 Pro Max).
Deployment target is iOS 17.0; the app is iPhone-only (no iPad support declared).

3. WHAT THE APP DOES, WHO IT IS FOR, AND WHAT PROBLEM IT SOLVES

The Italian State Police (Polizia di Stato / Polizia Stradale) publish, every
Monday, a programme of where speed checks will operate that week, as twenty
separate regional PDF documents, plus two national PDF lists of fixed
installations. They publish this specifically so that drivers moderate their
speed. The Ministry of Infrastructure and Transport separately publishes a
register of approved speed-measurement devices.

The information is public but impractical: a driver would have to visit the
website, find the correct regional PDF, and read it before every journey.

FTC Autovelox downloads those publications automatically, reads them, and
answers one question: "I am driving from A to B on this day — what speed
enforcement has the Polizia Stradale published for my route?"

Target audience: drivers in Italy. The app is in Italian.

The framing throughout is road safety. Every alert refers to respecting the
speed limit, never to avoiding a fine.

IMPORTANT — HOW TO EVALUATE THIS APP FROM OUTSIDE ITALY

The app's content covers Italian roads only, because the source publications are
issued by the Italian State Police. When the app is opened from outside Italy —
for example from a review location in the United States — any feature that
depends on the device's current position will correctly show that there is
nothing nearby. That is the expected and intended behaviour, not a fault, and we
suspect it is why the app was difficult to evaluate.

Every feature can be exercised fully from anywhere in the world without being in
Italy, as follows:

- REGIONE tab: choose "Lombardia". This shows the real published data for the
  current week with no location involved. This is the fastest way to see that
  the app works.
- PERCORSO tab: TYPE two Italian towns, for example "Milano" and "Bologna", and
  tap "Calcola". The route and any published checks along it are computed for
  those places regardless of where the device is. Do not use the "Usa la mia
  posizione" button when outside Italy, as it will correctly fill in your actual
  location.
- MULTA tab: type "Autovelox" to search the Ministry device register. No
  location involved.
- INFO tab: "Prova avviso vocale" plays a sample spoken alert so the audio
  behaviour can be verified anywhere.
- The location permission prompt appears when "Modalità viaggio" or "Modalità
  live" is started, from any location.

4. HOW TO SET UP AND USE THE MAIN FEATURES

No account, no login, no credentials, no sample files are required. The app
works immediately on first launch, including offline, because a copy of the
dataset ships inside the app.

There are four tabs:

- PERCORSO: enter a departure and arrival place, choose a day, tap "Calcola".
  The app shows the published checks along that route, in order of travel, on a
  map and as a list. "Usa la mia posizione" fills the departure field from the
  device's location; it is an explicit tap and is the only place the app asks
  for location outside trip mode.

- REGIONE: browse the current week region by region. Choose "Lombardia" to see
  populated data. This is the quickest way to see the app's real content without
  entering a route.

- MULTA: search the Ministry register of approved devices by authority, brand,
  model or serial number. Type "Autovelox" to see results.

- INFO: sources, coverage limits, and a "Prova avviso vocale" button that plays a
  sample spoken alert so the audio behaviour can be checked without driving.

Two optional driving features, both off by default and both started only by an
explicit tap:

- MODALITÀ VIAGGIO, from the results screen after calculating a route.
- MODALITÀ LIVE, from the Percorso tab, which does not require a route.

Both use location only while running and stop when the user ends them.

5. EXTERNAL SERVICES, TOOLS AND PLATFORMS

- A static JSON dataset hosted on GitHub Pages at
  https://tfcfun.github.io/ftc-autovelox/data/latest/
  The app performs a plain HTTP GET to download it and sends no information
  about the user. This file is produced by an automated job that reads the
  official publications listed below.
- Apple MapKit and CoreLocation for the map and positioning, on device.
- AVSpeechSynthesizer for spoken alerts, on device.

There are no third-party SDKs of any kind: no analytics, no advertising, no
authentication service, no payment processor, no AI service, no crash reporting.
The app has no server backend and no account system. Its App Privacy declaration
is "Data Not Collected", which reflects that the app transmits nothing.

6. REGIONAL DIFFERENCES

The app functions identically in all regions. Its content, however, covers Italy
only, because the source publications cover Italian roads. It is offered
worldwide so that people travelling to Italy can consult it before a journey.
The interface is in Italian.

7. REGULATED INDUSTRY / PROTECTED THIRD-PARTY MATERIAL

The app does not operate in a regulated industry and requires no licence or
authorisation to operate.

All content originates from official publications of Italian public
authorities, published openly and without restriction on their institutional
websites:

- Polizia di Stato — weekly mobile speed-check programme and the national lists
  of fixed installations:
  https://www.poliziadistato.it/articolo/autovelox-e-tutor-dove-sono
- Ministry of Infrastructure and Transport — register of approved speed
  measurement devices:
  https://velox.mit.gov.it/dispositivi

No credentials or permissions are needed to access either. Both are public web
pages intended for public consultation; the Polizia di Stato states that it
publishes this information precisely to encourage drivers to moderate their
speed.

The app reproduces facts (a road, a date, a province, a kilometre marker), not
the documents themselves, and attributes the source both inside the app (Info
tab) and on the App Store product page. Under Italian and EU law on the reuse of
public sector information, this material is freely reusable.

The app contains NO user-submitted reports of any kind and provides no mechanism
to add them. All data comes exclusively from the two official sources above.
This is relevant to Guideline 1.4.4: the app displays only what law enforcement
itself publishes.

---

ADDITIONAL NOTE ON LOCATION USE (Guideline 5.1.1)

The app requests "When In Use" authorisation only and never requests "Always".
The location background mode is used solely while the user has explicitly
started Modalità viaggio or Modalità live, so that a spoken warning can be given
when entering a stretch of road where a check is published. Both modes are off
by default, are visible on screen while running, and stop when the user ends
them. Location is processed entirely on the device and is never transmitted,
stored, or shared.
