# AttendanceDash Pro - S3.6 Task Brief

Status: **COMPLETE WITH KNOWN LIMITATIONS**

## Objective
Complete S3.6 — Persistence & Sync Completion Audit. Perform a forensic audit of the full persistence lifecycle (UI → AppState → localStorage → Firestore → hydration → render), document it in `docs/S3.6_PERSISTENCE_SYNC_AUDIT.md`, verify Firestore round-trips and failure/offline/atomicity behavior, fix P0/P1/P2 persistence defects, run all `js/test-*.js`, browser-verify at 375 / 768 / 1440 px, and return one consolidated walkthrough with exactly one status line.

## Scope
- S3.5 is CLOSED (browser-verified 375/768/1440, 67 assertions). Do **not** reopen S3.5.
- Do **not** begin S3.7 (multi-semester / branch / college-wide architecture).
- If an offline mutation queue is genuinely required, STOP before building it and explain the architectural scope. A half-built offline queue must not be introduced.

## Architectural Invariants (never violated)
- Calendar Engine = sole temporal authority; Attendance Engine = sole attendance-math authority; Quiz Engine = quiz rules authority; Laboratory Engine = lab calculations authority; UI never becomes business-rule authority.
- `AppState.academicEvents` = persistent event authority; calendar-engine `runtimeEvents` = derived runtime state; `events-controller.js` = Academic Event mutation authority.
- `timetable.json` = current-semester config; Firestore rules must not be weakened; no duplicated business rules; no wholesale `ui.js` rewrite; no new framework; no unnecessary abstraction.
- Local is authoritative on refresh (dirty local state flushes before cloud download).
- Never invent university policy; BCS-054 Q3 remains academically unresolved.

## Deliverables
- [x] `docs/S3.6_PERSISTENCE_SYNC_AUDIT.md` - lifecycle state table (State / Owner / Local Storage / Firestore / Write Trigger / Hydration / Conflict Behavior / Verified / Problem), forensic trace, defects, verification matrix.
- [x] P0 fix: lab experiments with `undefined` optional fields no longer poison the entire Firestore payload (source fix in `saveLaboratoryStates` + recursive sanitizer in `performCloudSync`).
- [x] P1 fix: unsynced local mutations no longer silently lost on hydration (`initLocalState` restores `isDirty`; `fetchCloudStates` flushes dirty local before download).
- [x] P2 fix: `toggleLabSignature` clears stale `signedOn` when un-signing.
- [x] Offline behavior characterized empirically (Firestore offline queue covers debounce-elapsed writes; reload-before-debounce race closed by dirty-flush).
- [x] New regression test `js/test-persistence-sync.js` (17 assertions). Full suite = 84 assertions passing.
- [x] Browser verification at 375 / 768 / 1440 px + cross-device Firestore round-trip (attendance / lab / events).
- [x] `walkthrough.md` final walkthrough with exactly one status line (VERIFIED labels on every verification).
