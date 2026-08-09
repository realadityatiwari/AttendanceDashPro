# 21 — Changelog

This document tracks the evolution of the AttendanceDash Pro architecture across major development phases.

---

## S3.10 — Current-Semester Baseline Freeze
*Status: Complete (documentation-only)*

**Purpose**: Freeze a single authoritative snapshot of the project as it exists today so a future AI agent or developer can resume work with zero context loss. No production code changed.

**Baseline Document**: `docs/S3.10_CURRENT_SEMESTER_BASELINE.md` — version stamp (`APP_VERSION 2.0.3`), current academic data (2026–27 odd semester, SRMCEM `timetable.json`), full architecture (every file + dependency rules), every engine API/domain model, persistence/sync layer, PWA/service worker facts, invariants, deployment facts, and rollback expectations.

**Corrections vs prior documentation**:
- Assertion baseline corrected: prior docs stated **84** (30/20/17/17); verified runtime count is **95** (28/29/21/17). The four test files are byte-identical to commit `e4d4470` — prior docs undercounted, no test was removed or changed.
- Bug status corrected: BUG-001 (Firestore rules for `laboratory`/`academicEvents`), BUG-002 (`events-controller.js` missing from `STATIC_ASSETS`), and DEBT-002 (lab attendance `:P` lookup) are **already fixed in the current code** and are recorded as resolved, not open.

**Verification**:
- Full regression suite re-run as final integrity check: `test-attendance-engine.js` (28), `test-calendar-engine.js` (29), `test-calendar-window.js` (21), `test-persistence-sync.js` (17) = **95 assertions, 0 failures**.
- Stale-bug claims verified against source: `firestore.rules:58-65` whitelists all five root fields; `service-worker.js:25` precaches `events-controller.js`; `laboratory-engine.js:109-134` matches normalized `P` (P1/P2).

**Known Limitations**:
- S3.10 is a snapshot; it must be updated whenever the semester, timetable, or architecture changes (see its own "Baseline Maintenance" section).
- No new features shipped; prior known limitations (no multi-device conflict resolution, `simulationMode`/`history` dead fields, BCS-054 Q3 unresolved) remain unchanged.

---

## S3.6 — Persistence & Sync Completion Audit
*Status: Complete (with known limitations)*

**Bug Fixes**:
- **P0 — Lab experiments poisoned ALL cloud syncs**: experiments created by `logExperiment` carry `undefined` `title/marks/remarks`, which Firestore rejects — the entire `set()` was dropped, silently blocking attendance, events, and lab sync and leaving `isDirty` stuck `true`. Fixed in `js/storage.js`: `saveLaboratoryStates` omits undefined keys; `performCloudSync` recursively strips `undefined` before `set()`.
- **P1 — Unsynced local mutation lost on hydration**: `initLocalState` now restores `isDirty`, and `fetchCloudStates` flushes dirty local state to cloud BEFORE downloading, so a mutation made offline (or whose 400 ms debounce never fired before reload) is no longer silently overwritten by stale cloud state.
- **P2 — Stale `signedOn` after un-signing**: `toggleLabSignature` now deletes `signedOn` when toggling back to `pending`.

**Verification**:
- New regression test `js/test-persistence-sync.js` (17 assertions); full suite = 84 assertions passing.
- Cross-device Firestore round-trips verified for attendance, laboratory, and academic events.
- Offline behavior characterized: Firestore offline queue auto-flushes debounce-elapsed writes on reconnect; the reload-before-debounce race is closed by the hydration dirty-flush.
- Browser sweep 375 / 768 / 1440 px with zero console errors; see `docs/S3.6_PERSISTENCE_SYNC_AUDIT.md`.

**Known Limitations**:
- No multi-device conflict resolution (naive per-key cloud-wins merge; single-device-primary assumption).
- `AppState.settings.simulationMode` stored but unused; `AppState.history` is dead.
- No app-level reconnect flush listener (covered by Firestore queue + hydration dirty-flush).

---

## S3.5 — UI/UX Completion Audit
*Status: Complete*

**Features Introduced**:
- Quiz cycle tab strip (`#quizTabs`) populated from `timetable.quiz_dates`; dashboard, hero, and summary now switch between 1st/2nd/3rd Quiz periods (dynamic label + required average).
- Laboratory card action controls: "Log Exp N" (records `dateConducted`) and "Mark Signed" (toggles `signatureStatus`) — completes the previously display-only lab tracker.
- Mobile date navigation restored: `#mobileDateTrigger` no longer pinned `display:none` inline; date bottom sheet + picker now drive mobile date changes.
- Desktop accessibility: `#profileView` (Profile tools + Feedback form) now renders inline at ≥768 px like `#eventsView`.

**Bug Fixes**:
- Signup profile header race: header/profile now render the fresh account name immediately after signup (previously showed "Student" until reload).
- Theme/settings reload race: cloud-sync debounce reduced 1000 ms → 400 ms to shrink the "toggle then fast reload loses the change" window.

**Known Regressions / Limitations**:
- Laboratory completion still requires the subject's physical P-class attendance on `dateConducted` to be `Attended` (engine contract); a logged + signed experiment without that attendance counts as pending by design.
- BCS-054 Q3 academic resolution remains open (not invented).

---



## Phase F1.3 — Academic Event Management System (UI)
*Status: Code-complete, pending browser validation.*

**Features Introduced**:
- Event creation form (bottom sheet).
- Events list UI in the Academic Tools workspace.
- Active/Archived tab filtering for events.

**Architecture Changes**:
- Implemented `events-controller.js` as the strict mutation layer for academic events.
- Enforced soft-delete (archive) as the default event lifecycle.
- Shifted Academic Tools from a root navigation tab into a sub-workspace within Profile.

**Known Regressions**:
- Discovered BUG-001 (Firestore rules block event sync) and BUG-002 (Service worker cache omits controller). Both block full offline/sync functionality for the feature.

---

## Phase F1.2 — Academic Event System (Backend)
*Status: Complete*

**Features Introduced**:
- `AcademicEventRegistry` defining all valid event types (extra lectures, holidays, emergency closures).
- Event delta computation in the Calendar Engine.

**Architecture Changes**:
- Decided on date-indexed storage (`AppState.academicEvents["YYYY-MM-DD"] = [...]`) for O(1) rendering performance.
- Added event versioning and history trailing to the `AcademicEvent` schema.

---

## Phase F1.1 — Subject-Specific Timelines
*Status: Complete*

**Features Introduced**:
- Decoupled the attendance window start/end dates so they can be defined per subject.
- Mixed-timeline support (some subjects have custom timelines, others use global fallback).

**Architecture Changes**:
- Shifted timeline definitions into `timetable.json`.
- Modified `getAttendanceData` to query window boundaries per subject rather than globally.

---

## Phase S1.10 — Stabilization (Regression Incident)
*Status: Resolved*

**Incident**:
- A syntax error in `ui.js` (unclosed template literal and duplicate variable declaration) broke the entire application.
- Because of the PWA service worker, the broken JS was cached, causing a white screen / unclickable buttons even after fixes were deployed.

**Resolution**:
- Fixed the syntax errors.
- Incremented `APP_VERSION` to bust the cache.
- Instituted mandatory AST validation (`acorn`) for `ui.js` after major edits.

---

## Phase A2.4 — Quiz Engine Consolidation
*Status: Complete*

**Features Introduced**:
- Dashboard now displays exactly how many classes a student must attend to become eligible.

**Architecture Changes**:
- Removed all duplicate attendance math from `quiz-engine.js`.
- Refactored `quiz-engine.js` into a pure rules engine.
- Introduced `OptimizationResult` passing from Attendance Engine to Quiz Engine.
- Enforced the "UI is a pure consumer" rule (UI never orchestrates engines).

---

## Phase A2.3 — Calendar Engine Extraction
*Status: Complete*

**Features Introduced**:
- Unified handling of holidays, weekends, and working Saturdays.

**Architecture Changes**:
- Extracted all temporal logic from UI and Attendance Engine into `calendar-engine.js`.
- Established the strict Engine Layering rule (Calendar is the absolute bottom layer).

---

## Phase A1 — Foundation
*Status: Complete*

**Features Introduced**:
- Basic percentage calculation.
- LocalStorage persistence.
- Firebase Authentication.
- Static timetable parsing.
- Responsive CSS (Desktop/Mobile).

**Architecture Changes**:
- Decided on zero-build, Vanilla JS + ES Modules.
- Chose `AppState` singleton hydration strategy.
