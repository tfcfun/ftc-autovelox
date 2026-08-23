# Screen recording for App Review — item 1 of the Guideline 2.1 request

Submission `9c3d94e1-7a73-41c1-987f-781cb3798dd0`, app version 1.0, build 2.
State as of 23 Aug 2026: version `REJECTED`, submission `UNRESOLVED_ISSUES`.

This is the shot list. Every shot exists to prove one specific claim made in
`review-reply-2.1.md` — if a claim is asserted there and not shown here, it is an
invitation to another round.

**Recorded in Italy**, which is the point: the reviewer's difficulty was that the app
looks empty from California. Shots marked ⭐ are ones they could not produce themselves.

---

## Before you press record

1. **Delete the app, reinstall from TestFlight.** The location permission prompt must
   appear on camera. If permission is already granted, that shot is impossible and the
   reviewer cannot see how location is requested.
2. Do Not Disturb on. Portrait. **Do not rotate** at any point.
3. Screen Recording with the **microphone OFF** — iOS captures the app's own audio, which
   is what the voice-alert shot needs. Ambient noise or Italian narration will not help an
   English-speaking reviewer.
4. Target **3–5 minutes**. Reviewers watch the opening.
5. **Hold on every screen with text for a slow count of three.** They read.

---

## Part A — at a desk. This alone answers the request.

### 1 · Cold launch
Open from fully closed.
**Proves:** no account, no login, no setup, no sample data — the claim in answer 4.

### 2 · REGIONE → Lombardia
Go here **first**, before anything else.
**Proves:** real published data for the current week, with no location involved. The reply
calls this "the fastest way to see that the app works". It is the shot that dissolves the
reviewer's confusion, so it goes at the top.

### 3 · Offline ⭐
Airplane mode ON → force-quit → relaunch → REGIONE again. Still populated. Airplane mode OFF.
**Proves:** "works immediately on first launch, including offline, because a copy of the
dataset ships inside the app."

### 4 · PERCORSO, typed
Type `Milano` → `Bologna`. Tap **Calcola**. Show the list, then the map.
**Proves:** the core feature works from typed input with no location at all — exactly the
path the reply told them to use.

### 5 · PERCORSO, "Usa la mia posizione" ⭐
Tap it. Let it fill your real Italian departure. Calculate a route to somewhere real.
**Proves:** the button the reply told them *not* to use from abroad, working as designed.
They were told it would be useless in California; here it is being useful in Italy.

### 6 · A route with nothing published
Pick a pair that returns no checks. **Hold on the wording.**
**Proves:** the app says *"no Polizia Stradale checks published for this date"* and never
*"road clear"*. This is the single most important shot for Guideline 1.4.4 — it shows the
app does not claim enforcement-free roads.

### 7 · MODALITÀ VIAGGIO — permission
From the route results, start it. **Let the permission prompt appear. Grant it on camera.**
Show it running. Then **end it explicitly.**
**Proves:** location is requested only on an explicit tap, used only while running, and
stops when the user stops it.

### 8 · MODALITÀ LIVE, no route
Back to PERCORSO, start Modalità live without calculating a route.
**Proves:** the claim that live mode does not require a route.

### 9 · MULTA
Type `Autovelox`. Show results from the Ministry register.
**Proves:** answer 4's description of the fourth tab, no location involved.

### 10 · INFO
Scroll slowly through sources and coverage limits. Then tap **Prova avviso vocale** and
**hold still until the spoken alert finishes.**
**Proves:** attribution is inside the app, the coverage limitation is stated plainly, and
the audio behaviour can be verified without driving. Check the take — the voice must be
audible.

---

## Part B — in the car. Optional. Do not delay the reply for it.

Modalità live running while actually moving, ideally approaching a published stretch so a
real proximity alert fires. ⭐⭐

No reviewer in Cupertino can produce this shot. It is the difference between *"we assert it
works"* and *"here it is working"*. But Part A is complete on its own.

**Do not film yourself exceeding a limit.** The framing is road safety end to end; a video
that reads as fine-evasion earns a worse rejection than the one you already have.

---

## Do not

- Rotate the device mid-recording.
- Show any other app, notification, or personal data.
- Show a screen the reply does not mention.
- Narrate in Italian, or leave the microphone on.
- Film while driving yourself. Passenger, mount, or don't shoot Part B.

---

## After recording

Send **one** reply in the Resolution Center containing all of it — the video plus answers
2–7. The submission has been sitting at `UNRESOLVED_ISSUES` for eight days because item 1
was never attached; a partial reply is what got us here.

Paste this index into the message so the reviewer can jump to what they doubted:

```
0:00  Cold launch — no account or setup required
0:xx  REGIONE > Lombardia — real published data, no location used
0:xx  Airplane mode — the dataset ships inside the app, works offline
0:xx  PERCORSO — Milano to Bologna typed, no location used
0:xx  PERCORSO — "Usa la mia posizione" from a device in Italy
0:xx  A route with no published checks — note the wording
0:xx  Modalità viaggio — location permission requested, then stopped
0:xx  Modalità live — works without a route
0:xx  MULTA — Ministry device register search
0:xx  INFO — sources, coverage limits, sample spoken alert
```

Fill the timestamps once the take is final.

**No new build is required.** Build 2 is `VALID` and unexpired; the 2.1 request is
informational, not a defect. Reply against the existing build.
