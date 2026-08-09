# 17 — AI Developer Handoff

## Context for the Inheriting AI

This document is written specifically for the next AI coding agent (Claude Code, Gemini CLI, Codex, Cursor, etc.) that will continue development on AttendanceDash Pro. Read this document **first**, before reading any source file.

---

## Architectural Invariants — Never Violate These

These are not preferences. These are locked decisions made through multiple architectural review cycles. Violating any of these will be rejected.

### 1. Calendar Engine Is the Single Temporal Authority

All date math — working days, holidays, quiz windows, attendance windows, event priority resolution — lives in `calendar-engine.js`. No other module performs its own date calculations.

If you need to know "is August 15th a working day?", call `getAcademicDay('2026-08-15')`. Do not compute it yourself.

### 2. Attendance Engine Is the Single Attendance Mathematics Authority

All percentage calculations, optimization (must-attend, safe-skip), and count aggregation live in `attendance-engine.js`. No other module recalculates attendance.

If you need to know "how many more classes does this student need?", call `optimizeLive()`. Do not write a new formula.

### 3. Quiz Engine Evaluates Rules Only — Never Calculates

`quiz-engine.js` calls `getSubjectQuizOptimization()` from the Attendance Engine and applies the result against the policy threshold. It does not calculate attendance independently.

### 4. UI Is a Pure Consumer

`ui.js` builds HTML from engine outputs. It does not contain business logic. It does not directly mutate `AppState`. The only exception: `logAttendance()` and `logExperiment()` route through `dateContext.logClassState()` and `saveLaboratoryStates()` — they do not bypass the state layer.

### 5. Controllers Own All Mutations

Academic Event mutations go through `events-controller.js`. Attendance mutations go through `dateContext.logClassState()`. Laboratory mutations go through `saveLaboratoryStates()`. No module bypasses these.

### 6. No Duplicate Logic

There must be exactly ONE implementation of any given algorithm. If you find yourself writing a formula that looks like something that already exists in an engine, you are doing it wrong. Find the engine function and use it.

### 7. No Fifth Bottom Nav Tab

The bottom navigation has four tabs: Dashboard, Subjects, History, Profile. It will always have exactly four. New management features go in Academic Tools (accessible from Profile). Never add a fifth tab.

### 8. Soft Delete Is the Lifecycle

Academic Events are disabled, then archived. They are never permanently deleted in normal user flows. `archived: true` is the terminal state. Do not add hard-delete UI.

---

## Current State Summary

> **Start here**: `docs/S3.10_CURRENT_SEMESTER_BASELINE.md` is the frozen, authoritative snapshot of the current-semester codebase (version, architecture, engines, persistence, PWA, test baseline, deployment facts). Read it after this document, before touching source.

### What Is Complete and Production-Stable

| Component | File | Status |
|---|---|---|
| Calendar Engine (core) | `calendar-engine.js` | ✅ Stable |
| Attendance Engine (core) | `attendance-engine.js` | ✅ Stable |
| Quiz Engine | `quiz-engine.js` | ✅ Stable |
| Laboratory Engine | `laboratory-engine.js` | ✅ Stable (DEBT-002 lab lookup fixed) |
| Academic Event System (backend) | `calendar-engine.js`, `events-controller.js` | ✅ Stable |
| Authentication | `auth.js`, `firebase.js` | ✅ Stable |
| Storage + Cloud Sync | `storage.js` | ✅ Stable (BUG-001 rules fixed; P0/P1/P2 persistence fixes from S3.6) |
| Date Context / Simulation Mode | `dateContext.js` | ✅ Stable |
| PWA / Service Worker | `service-worker.js`, `pwa.js` | ✅ Stable (BUG-002 cache fixed) |
| UI — Dashboard | `ui.js` | ✅ Stable |
| UI — Academic Events | `ui.js`, `app.js` | ✅ Stable (browser-validated in S3.5/S3.6) |

### What Needs Immediate Attention (Before New Features)

The three historically flagged blockers — BUG-001 (Firestore rules), BUG-002 (service worker cache), DEBT-002 (lab attendance key) — are **already fixed** and must not be re-opened. Remaining work:

1. **Re-scan the debt register**: `docs/15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md` still lists legacy entries; compare against the S3.10 baseline to confirm which remain live (e.g. DEBT-001 dual-write divergence risk in `events-controller.js`).
2. **Confirm Phase F1.3 browser validation**: recorded as verified in the S3.x audits; re-confirm against the current baseline before feature work.
3. **Update the S3.10 baseline**: whenever the semester, `timetable.json`, or architecture changes, refresh `docs/S3.10_CURRENT_SEMESTER_BASELINE.md` per its maintenance section.

---

## How to Read the Codebase

Start with these files in order:

1. `timetable.json` — The academic data model. Understand what subjects exist, what types they are, and how their timelines are structured.
2. `js/utils.js` — The `CLASS_TYPES` registry and fundamental helpers.
3. `js/calendar-engine.js` — Read the `AcademicCalendar`, `AcademicDay`, and `AttendanceWindow` domain models first. Then read `getAcademicDay()` and `getQuizWindow()`.
4. `js/attendance-engine.js` — Read `optimize()` and `optimizeLive()` to understand the core algorithm. Then read `getAttendanceData()` and `computeSubjectStats()`.
5. `js/quiz-engine.js` — Short file. Read all of it.
6. `js/storage.js` — Read `AppState` definition and `triggerCloudSync()`.
7. `js/app.js` — Read `bootstrap()` and the `auth.onAuthStateChanged()` handler.
8. `js/ui.js` — Read `recalculateAndRender()` (the master render loop).

---

## How to Add a New Feature

**Template for any new feature**:

1. **Does it need new temporal logic?** → Extend `calendar-engine.js`.
2. **Does it need new attendance math?** → Extend `attendance-engine.js`.
3. **Does it need new eligibility rules?** → Extend `quiz-engine.js`.
4. **Does it need a new data type that users create/delete?** → Create a new controller following the pattern in `events-controller.js`.
5. **Does it need UI?** → Add rendering functions to `ui.js`. Wire click handlers in `app.js` using event delegation.
6. **Does it need persistence?** → Add a field to `AppState` in `storage.js`, update `initLocalState()`, `fetchCloudStates()`, `triggerCloudSync()`, and update `firestore.rules`.

Never collapse these layers. Never add temporal logic to the UI.

---

## Common Pitfalls

### "I'll just put this calculation in the UI to keep it simple"

Don't. The UI renders from data — it never calculates. Put it in the correct engine. The UI will call the engine.

### "I'll use a Date object for the date"

The calendar system uses `YYYY-MM-DD` strings everywhere. `parseDateString()` converts to Date only when needed for arithmetic. Never store a Date object in state or pass it between engines. Always use strings.

### "I'll check if `new Date('YYYY-MM-DD') > startDate`"

`new Date('YYYY-MM-DD')` is UTC midnight. This can shift the date by one day in negative timezone offsets. Use `parseDateString()` from `utils.js` which creates a local noon date instead.

### "I'll add a new tab to the bottom nav for this feature"

No. Four tabs maximum. The feature goes in Academic Tools (Profile section). See `docs/16_ROADMAP.md`.

### "I'll delete the old event instead of archiving it"

No. Soft delete is the lifecycle. Set `archived: true`. See `docs/09_ACADEMIC_EVENT_SYSTEM.md`.

### "I need attendance data for my feature — I'll calculate it inline"

No. Call `getAttendanceData()` and `computeSubjectStats()` from `attendance-engine.js`. Never write a new formula.

---

## Firebase Notes

- The SDK is loaded via compat CDN scripts in `index.html` before the module entry point.
- `firebase.js` relies on `window.firebase` being defined. This is always true in the browser but never in Node.js.
- Do NOT switch to the modular Firebase SDK without also setting up a bundler (Vite, Rollup, etc.).
- Firestore writes use `{ merge: true }` — they never overwrite the entire document.
- The Firestore project is `attendancedashpro` in `asia-south2` (Mumbai).

---

## Development Workflow

1. Start local server: `npx serve . -p 8080`
2. Open `http://localhost:8080` in Chrome (not Firefox — PWA features are Chrome-only).
3. After editing `ui.js`, validate AST: `node -e "const acorn=require('acorn'),fs=require('fs');acorn.parse(fs.readFileSync('./js/ui.js','utf8'),{ecmaVersion:2022,sourceType:'module'});console.log('✅ OK')" `
4. After engine changes, run unit tests: `node --experimental-vm-modules js/test-calendar-engine.js`
5. To bust service worker cache: increment `APP_VERSION` in `utils.js`.
6. Hard refresh to bypass service worker: `Ctrl+Shift+R` or disable SW in DevTools → Application → Service Workers.

---

## Where to Find Things

| Question | Answer |
|---|---|
| What quiz dates exist? | `timetable.json` → `quiz_dates` |
| What subjects exist? | `timetable.json` → `subjects` |
| What class types exist? | `utils.js` → `CLASS_TYPES` |
| What event types exist? | `calendar-engine.js` → `AcademicEventRegistry` |
| What is the lab rules config? | `laboratory-engine.js` → `LAB_RULES` |
| What is the quiz policy? | `app.js` → `initCalendarEngine` → `policies.quiz` |
| Where is AppState defined? | `storage.js` → `export const AppState` |
| What does the Firestore document look like? | `docs/10_STORAGE_AND_SYNC.md` |
| What is the current codebase baseline? | `docs/S3.10_CURRENT_SEMESTER_BASELINE.md` |
| What bugs exist? | `docs/15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md` |
| What features are next? | `docs/16_ROADMAP.md` |

---

## Final Note

This is a real production application used by real students. The attendance calculations directly affect whether a student is allowed to sit for their university exams. Every calculation must be correct. Every architectural principle exists to prevent subtle bugs from slipping into the math layer.

When in doubt: check the engine first, ask what the engine already knows, and extend it rather than duplicating it.
