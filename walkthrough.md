# S3.6 Persistence & Sync Completion Walkthrough

Date: 2026-08-09 · Browser: Chrome 151 headless via Puppeteer 25.4.0 · Target: http://localhost:8080
Test account: roll `9000000000002`, uid `Od675BhQ8KSvPv8DAIi140tAJdT2`, real Firebase project `attendancedashpro`.

## Final Status

> **S3.6 COMPLETE WITH KNOWN LIMITATIONS**

---

## Verification Summary (every item labelled)

| Verification | Label |
|---|---|
| Cross-device round-trip: attendance (2 keys) Session A → Session B | **VERIFIED** |
| Cross-device round-trip: laboratory (BCS-551 exp1) Session A → Session B | **VERIFIED** |
| Cross-device round-trip: academicEvents (3 dates, rendered in events list) Session A → Session B | **VERIFIED** |
| Lab local → Firestore after mutation (`isDirty` → `false`, cloud populated) | **VERIFIED** |
| P0 fix: no `undefined` field values in any sync payload | **VERIFIED** |
| P1 fix: dirty-local flush happens BEFORE cloud download (`set` before `get`) | **VERIFIED** |
| P1 fix: reload-before-debounce offline mutation survives re-hydration | **VERIFIED** |
| Offline → reconnect (debounce elapsed): write queued + auto-flushed by Firestore | **VERIFIED** |
| P2 fix: un-signing clears stale `signedOn` locally and in Firestore | **VERIFIED** |
| Simulation mode writes never reach Firestore (in-memory only) | **VERIFIED** |
| Profile + settings (theme) sync to Firestore and hydrate | **VERIFIED** |
| `js/test-persistence-sync.js` (new) — 17 assertions | **VERIFIED** |
| Engine baselines — 67 assertions (unchanged) | **VERIFIED** |
| Browser sweep 375 px — shell, 9 mobile cards, 3 lab cards, 0 console errors | **VERIFIED** |
| Browser sweep 768 px — desktop layout, all state, 0 console errors | **VERIFIED** |
| Browser sweep 1440 px — full dashboard, all state, 0 console errors | **VERIFIED** |

No verification is labelled PARTIALLY VERIFIED or NOT VERIFIED in this walkthrough; every S3.6-in-scope claim was either observed in a live browser, read directly from Firestore, or covered by a passing regression assertion.

---

## Defects Found & Fixed

1. **P0 — Lab experiments blocked ALL cloud syncs.** Experiments created by `logExperiment` carry `undefined` `title/marks/remarks`. Firestore rejects any `undefined` field and rejects the **entire** `set()` — so attendance, events, and lab all silently stopped syncing and `isDirty` stuck `true`. Fixed in `js/storage.js`: (a) `saveLaboratoryStates` omits undefined keys; (b) `performCloudSync` recursively strips `undefined` before `set()`. Proven: lab sync completes, `isDirty:false`, cloud populated.
2. **P1 — Unsynced local mutation silently overwritten by stale cloud.** A mutation made offline (or whose 400 ms debounce never fired before reload) existed only in localStorage; the next online hydration merged cloud-wins and reverted it. Fixed: `initLocalState` restores `isDirty`; `fetchCloudStates` flushes dirty local to cloud **before** downloading. Proven: event toggle pre-fix lost (`active` reverted), post-fix preserved locally + propagated to cloud.
3. **P2 — Stale `signedOn` after un-signing.** `toggleLabSignature` flipped to `pending` but left `signedOn`. Fixed in `js/ui.js`: `delete exp.signedOn`. Proven through the real UI: signed → pending clears the timestamp locally and in Firestore.

---

## Offline & Atomicity Findings

- Firestore client-side offline persistence (compat SDK) queues `set()` while offline; the write resolves and is auto-flushed on reconnect — **no app-level reconnect listener needed** for debounce-elapsed writes (better than the S3.4 note). No `online` listener exists in app code; `pwa.js` only toggles the banner.
- The only data-loss window (reload before the 400 ms debounce fires while offline) is now **closed** by the dirty-flush-before-download in `fetchCloudStates`.
- Event mutations remain atomic (snapshot → mutate → sync runtime → persist local → cloud sync best-effort → render; revert on persist failure) — unchanged, verified by round-trip.

---

## Regression Baseline

- `node js/test-attendance-engine.js` - PASS (30)
- `node js/test-calendar-engine.js` - PASS (20)
- `node js/test-calendar-window.js` - PASS (17)
- `node js/test-persistence-sync.js` - PASS (17, new)
- **Total: 84 assertions, 0 failures.**

---

## Known Limitations (out of scope for S3.6)

- **No multi-device conflict resolution** — `fetchCloudStates` is a naive per-key cloud-wins merge (no timestamps). Concurrent two-device edits can clobber each other. Single-device-primary assumption.
- **`AppState.settings.simulationMode` stored but unused** (date mode is derived from the selected date); `AppState.history` is a dead field never written by any caller.
- **No app-level reconnect flush listener** — an in-tab (no reload) mutation whose debounce never fired is flushed on the next mutation or the next hydration reload (the reload case is safe via dirty-flush).
- **No offline mutation queue was built** — not required; Firestore's built-in offline queue plus the hydration dirty-flush covers the behavior. Building a queue would be a new architecture project (out of scope, per task brief).
- BCS-054 Q3 academic resolution remains open (not invented).
