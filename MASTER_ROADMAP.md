# AttendanceDash Pro — Master Roadmap

> **Project Source of Truth**
>
> This document defines the direction, phase structure, priorities, architectural boundaries, and production path for AttendanceDash Pro.
>
> **Current position:** Phase 6 (Calendar & Academic Events) **COMPLETE & FROZEN** ✅. Phase 7 (Quiz Eligibility & Schedule Reality) **COMPLETE & FROZEN** ✅ — full math verified, canonical contract, 7.1/7.2 analytics, and final hardening (backend reachability consistency, frontend safety/fallback rendering, cleanup, and pycache removal) verified passing 100% of verifiers. Phase 8 (Attendance Analytics & Intelligence) **COMPLETE & FROZEN** ✅ — backend read model, dashboard analytics, and laboratory domain separation delivered without duplicate math. Phase 9 (Laboratory System) **COMPLETE & FROZEN** ✅ — 9.0 audit, 9.1 event integration, 9.2.0 audit, and 9.2.1 experiment management all complete, plus focused corrections (Track lab attendance, History filters, Quiz Day recovery, and local development infrastructure). Phase 10 (Settings, Feedback & Account Management) **COMPLETE & FROZEN** ✅ — 10.0 audit ✅ · 10A settings UI ✅ · 10B program + profile completion ✅ · 10C real feedback system ✅ · 10D user preferences API + UI ✅ · 10E freeze corrections, verification & governance reconciliation ✅. Phase 11 (Notifications & Reminders) **COMPLETE & FROZEN** ✅. Phase 12 (Mobile / Responsive Experience) **COMPLETE & FROZEN** ✅. Phase 13 (PWA / Installability) **COMPLETE & FROZEN** ✅. **Phase 14 (Firebase Retirement) COMPLETE & FROZEN ✅** — 14.0 audit, 14A frontend removal, 14B backend removal, 14C deployment/config cleanup, 14D `firebase_uid` removal, 14E regression verification, 14F freeze & governance reconciliation all complete. Active architecture: **PostgreSQL + FastAPI + JWT + Next.js**; Firebase fully retired.
> 
> **Next phase:** Phase 21 — Production Launch **NOT STARTED** (subject to Phase 18D infrastructure resolution AND user completion of the Phase 20 manual browser QA checklist). Phase 20 (Production QA) **COMPLETE & FROZEN** — automated/in-process QA passed across all surfaces; cross-surface consistency verified; frozen verifiers green; manual browser QA checklist delivered to user; production blockers preserved. Phase 19 (CI/CD) **COMPLETE & FROZEN**; Phase 18 **IN PROGRESS / PARTIAL** — 18.0–18C ✅, 18D ⚠️ PARTIAL (production deployment BLOCKED on missing infrastructure). Phase 17 **COMPLETE & FROZEN**; Phase 16 **COMPLETE & FROZEN**; Phase 15 **COMPLETE & FROZEN**; Firebase retirement (14.0–14F) **COMPLETE & FROZEN**; active application = `frontend/` + `backend/` (PostgreSQL + FastAPI + JWT + Next.js).
>
> **Authorized bugfixes executed (2026-08-22):**
> • **Bugfix 1 — CLASS_CANCELLED propagation:** active cancellation events now cancel matching recorded sessions via the canonical synchronizer; consumers aligned on one applicability predicate (`occurrence_is_cancelled`). Verified 26/26 + full regression set.
> • **Bugfix 2 (Phase 12C) — cancellation reversal + counting consistency:** root-caused the stale-cancelled-after-event-removal defect (stale backend process executing pre-fix code + genuine `deactivate_event` early-return gap that skipped reconciliation for already-inactive events). `deactivate_event` now ALWAYS reconciles — state-based synchronization re-derives `is_cancelled` from the complete active event set, making removal/reactivation/moves self-healing and idempotent in BOTH directions. One canonical applicability rule excludes cancelled occurrences from every denominator/numerator/count (Track/History/Subjects/Dashboard/Eligibility/Notifications) while attendance records remain byte-preserved. NEW lifecycle verifier **35/35** + prior verifier **26/26** + frozen-phase regressions green. Live BCS-058 restored through the application path (07-29 Attended / 07-30 Missed originals back; applicable lectures 79 = N). Details: `docs/bugfix/cancellation_state_and_counting_consistency_report.md`. ⚠ Owner must restart the dev backend (runs without --reload) to load fixed modules. No commit made.

---

## 🧭 Project Direction

AttendanceDash Pro is being developed as a real, production-ready attendance intelligence platform — not merely a polished frontend.

The standard for completion is:

```text
UI
 ↓
API
 ↓
Service
 ↓
Repository
 ↓
Database
 ↓
Engine
 ↓
Calculated Result
```

Every layer must agree.

A page appearing to work is **not** sufficient evidence that the feature works.

---

# 📍 Current Status

| Phase | Area | Status |
|---|---|---|
| 0 | Architecture & Reality Audit | 🟢 Complete / Frozen |
| 1 | Design System Foundation | 🟢 Complete / Frozen |
| 2 | Desktop Shell & Global UX | 🟢 Complete / Frozen |
| 3 | Home Dashboard | 🟢 Complete / Frozen |
| 4 | Track Attendance | 🟢 Complete / Frozen |
| 4.5 | Data Integrity & Account Foundation | 🟢 Complete / Frozen |
| 5 | Attendance History | 🟢 Complete / Frozen |
| **6** | **Calendar & Academic Events** | ✅ **COMPLETE & FROZEN** — 6.0 audit ✅ · 6.1 foundational corrections ✅ · 6.2 calendar read model & API ✅ · 6.3 calendar UI ✅ · 6.4 events page upgrade ✅ · 6.5 persistence/admin/seeding ✅ · 6.6 event→engine integration ✅ · 6.7 verification/freeze ✅ |
| 7 | Quiz Eligibility & Schedule UX | ✅ **COMPLETE & FROZEN** — 7.0 audit ✅ · 7.1 contract/UI ✅ · 7.2 analytics refinement ✅ · **Hardening** ✅ (backend reachability consistency, frontend degradation safety, pycache removal, dead code cleanup, exact math restored and verified). |
| 8 | Attendance Analytics / Intelligence | ✅ **COMPLETE & FROZEN** — 8.0 audit ✅ · 8.1 canonical analytics read model ✅ · 8.2 frontend consumption ✅ · Attendance UI refinement ✅ · Lab domain correction (practical attendance separation) ✅. |
| 9 | Laboratory System | ✅ **COMPLETE & FROZEN** — 9.0 audit ✅ · 9.1 event integration (Mid-Sem/Lab Cancelled) ✅ · 9.2.0 audit ✅ · 9.2.1 experiment management (curriculum/records/UI/API) ✅ · Focused corrections (Track lab, History filters, Quiz Day recovery) ✅. |
| 10 | Settings, Feedback & Account Management | ✅ **COMPLETE & FROZEN** — 10.0 audit ✅ · 10A settings UI ✅ · 10B program + profile completion ✅ · 10C real feedback system ✅ · 10D user preferences API + UI ✅ · 10E freeze corrections, verification & governance reconciliation ✅. |
| **11** | **Notifications & Reminders** | ✅ **COMPLETE & FROZEN** — 11.0 architecture audit ✅ · 11A backend notification read model & contracts ✅ · 11B notification persistence + read-state ✅ · 11D notification center UX ✅ · 11E preference wiring verified (no additional implementation required) ✅ · 11F final verification & freeze ✅ · 11C delivery model decision-gated/deferred (not implemented) |
| 12 | Mobile / Responsive Experience | 🟡 **IN PROGRESS** — 12.0 architecture & implementation-readiness audit ✅ · **12A responsive foundation + mobile navigation ✅** (S4 4-tab bottom nav + More sheet, shell/dialog scroll safety, touch-target foundation; desktop unchanged) · **12B Track/Dashboard/Calendar responsiveness ✅** (month-nav overflow fixed, grid cells enlarged at 320, Track date nav fluid + ≥40px controls, session-card collisions fixed, dashboard wrap fixes; desktop byte-identical) · **12C ✅ COMPLETE (2026-08-22)** — page responsiveness across Laboratory / Subjects / Quiz / Events (`docs/phase_12/phase_12c_implementation_report.md`, commit `31f75ca`) + the authorized cancellation-lifecycle & counting-consistency correctness fix (`docs/bugfix/cancellation_state_and_counting_consistency_report.md`) |
| 13 | PWA / Installability | ✅ **COMPLETE & FROZEN** — manifest, service worker, SVG icons, install prompt, standalone detection, online/offline state; zero backend/DB/migration changes; `tsc`/`build`/`diff --check` PASS |
| 14 | Firebase Retirement | ✅ **COMPLETE & FROZEN** — 14.0 audit ✅ · **14A frontend Firebase removal ✅** · **14B backend Firebase removal ✅** · **14C deployment/config cleanup ✅** · **14D firebase_uid cleanup ✅** (column dropped, migration `e1f2a3b4c5d6`) · **14E regression verification ✅** · **14F freeze & governance reconciliation ✅**. Firebase is fully retired from the active application (PostgreSQL + FastAPI + JWT + Next.js). |
| 15 | Legacy Web App + Legacy PWA Retirement | ✅ **COMPLETE & FROZEN** — legacy runtime removed (root `index.html`, `js/`, `css/`, `assets/`, `offline.html`, root `manifest.json`, root `service-worker.js`, legacy test scripts, legacy-only root package files); `timetable.json` preserved (active backend data dependency); docs/prompts marked as historical; active application = `frontend/` + `backend/` |
| 16 | Production Security Hardening | ✅ **COMPLETE & FROZEN** — JWT expiry bounded (8h env-configurable), password policy strengthened (8–128, letter+digit), in-process rate limiting (login 10/15min, register 5/h, 429 + Retry-After), security headers (nosniff/DENY/no-referrer/permissions; HSTS env-gated), global 500 handler + error-leak fixes, login timing equalization, structured logging, CORS env-driven; `verify_phase_16.py` 34/34 PASS; frozen verifiers green (6.5/10C/10D/11A); zero DB mutations |
| 17 | Data Integrity & Migration Hardening | ✅ **COMPLETE & FROZEN** — JWT production-secret guard ✅ (APP_ENV; `verify_phase_17_jwt_guard.py` 6/6) · integrity audit ✅ (zero orphans/duplicates/FK violations) · **NO MIGRATION REQUIRED** (single linear Alembic head `e1f2a3b4c5d6`) · backup/restore ✅ verified (isolated container) · retention policy ✅ documented (7 daily / 4 weekly / 3 monthly) · seed audit ✅ · semester-transition analysis ✅ · cleanup: NONE REQUIRED · working-DB mutations ZERO |
| 18 | Production Infrastructure | 🟡 **IN PROGRESS / PARTIAL** — **18.0 audit ✅ COMPLETE** · **18A containerization ✅ COMPLETE** · **18B env & secrets ✅ COMPLETE** · **18C backup automation ✅ COMPLETE** · **18D deployment & verification ⚠️ PARTIAL** — rehearsal deployment verified end-to-end (5 services healthy, real backup executed + verified, isolated restore PASS, scheduler + retention + locking verified, no secrets); **production deployment BLOCKED** on missing infrastructure (no host/domain/credentials/off-host destination); 2 deployment defects fixed (PyJWT dep, Caddy /health route); `docs/phase_18/phase_18d_deployment.md` |
| 19 | CI/CD | ✅ **COMPLETE & FROZEN** — GitHub Actions quality gate (`.github/workflows/ci.yml`): integrity, backend, frontend, docker, compose, migrations, config-contract, backup-infra jobs; deployment gate disabled (`if: false`); all checks verified locally; migration validated on disposable postgres:16 to head `e1f2a3b4c5d6`; no deployment, no secrets |
| 20 | Production QA | ✅ **COMPLETE & FROZEN** — in-process/API QA across all surfaces PASS (auth, dashboard, track, history, calendar, events, quiz, lab, profile, security); cross-surface consistency verified (summary 50.0% = DB 12/12/24); frozen verifiers green (6.5 27/27, 6.6 36/36, 6.7 30/31 known, 12E 8/8, 16 34/34, 17 8/8); no critical defects; manual browser QA checklist provided for user; QA temp-user artifact removed; 5 attendance + 62 notification QA-window deltas reported for user review |
| 21 | Production Launch | 🔴 **BLOCKED** — pre-flight gates unsatisfied: (A) Phase 20 manual browser QA NOT CONFIRMED by user · (B) Phase 20 QA-window deltas (5 attendance + 62 notifications) UNRESOLVED · (C) production infrastructure absent (no VPS/host, no credentials, no domain/DNS/TLS, no off-host backup). Launch report: `docs/phase_21/phase_21_production_launch.md`. No deployment attempted; CI deploy gate remains disabled. |
| 22 | Post-Launch | 🔵 Ongoing |

---

# 🟢 Phase 0 — Architecture & Reality Audit

**Status: COMPLETE / FROZEN**

Established the actual baseline:

- Frontend/backend architecture
- PostgreSQL state
- API surface
- Existing engines
- Firebase retirement status
- Existing pages/components
- Database relationships
- Existing data gaps
- Technical debt

### Freeze rule

Do not repeat this audit unless a later discovery directly contradicts the baseline.

---

# 🟢 Phase 1 — Design System Foundation

**Status: COMPLETE / FROZEN**

Implemented the visual foundation:

- Dark visual system
- Typography
- Color system
- Cards
- Badges
- Progress indicators
- Semantic status variants
- High-density layouts

Primary accent:

```text
#3B82F6
```

Legacy purple/magenta styling is not part of the target design system.

### Freeze rule

Do not redesign or rewrite these primitives merely for preference. Reopen only for a genuine defect or a deliberate product decision.

---

# 🟢 Phase 2 — Desktop Shell & Global UX

**Status: COMPLETE / FROZEN**

Implemented:

- Desktop top navigation
- User/profile menu
- Profile modal
- Appearance modal
- Settings modal
- Feedback modal foundation
- Install-app foundation
- Global dialog behavior
- Active navigation
- Authentication-aware shell
- Logout

Firebase-specific shell dependencies were removed.

### Freeze rule

Do not revisit the shell unless a real bug or explicit product requirement requires it.

---

# 🟢 Phase 3 — Home Dashboard

**Status: COMPLETE / FROZEN**

Implemented:

- Greeting
- Today's Attendance
- Weekly attendance
- Overall attendance
- Quiz snapshot
- Attention items
- Upcoming events
- Loading states
- Error states
- Empty states
- Dashboard aggregation endpoint

The dashboard consumes real backend data.

### Freeze rule

Do not repeatedly rebuild the dashboard because of visual preferences. Reopen only for real defects or later feature integration.

---

# 🟢 Phase 4 — Track Attendance

**Status: COMPLETE / FROZEN**

Implemented:

- Daily attendance view
- Date navigation
- Session cards
- Present / Absent
- Attendance changes
- Cancelled-session handling
- Mark All Present
- Cache/optimistic update behavior
- Enrollment authorization
- Backend daily-session endpoint

### Critical product requirement

> **15 July 2026 → current date**

Track must expose the student's complete semester attendance history.

**✅ SATISFIED in Phase 4.5.2** — Track navigates the full semester range (bounds from
`/student/me`, no hardcoded dates), shows every session type including practicals, and
supports manual historical re-entry through the canonical mutation endpoint. The 26
historical lab sessions remain unmarked pending the user's manual reconstruction.

If the historical data cannot be reliably recovered, manual re-entry is acceptable.

**Rebuilding the architecture is not acceptable.**

### Freeze rule

The attendance architecture is considered foundational. Do not rewrite it to solve a data problem.

---

# 🟢 Phase 4.5 — Data Integrity & Account Foundation

**Status: COMPLETE / FROZEN** — 4.5.1 audit ✅ · 4.5.2 historical Track ✅ · 4.5.3 Real Sign Up ✅.

## 4.5.1 — Historical Attendance Audit

**Status: COMPLETE** (read-only, 2026-08-13 → report `docs/phase_4_5_data_audit.md`).

Verdict: **B — PRESERVE WITH MANUAL CORRECTION**.

- Database structure healthy, zero structural corruption.
- 78 records exist (54 ATTENDED / 24 MISSED), 124 sessions in semester range, 46 unmarked (20 theory + 26 lab).
- Labs (BCS-551 ×8, BCS-552 ×10, BCS-553 ×8) never marked; laboratory tables empty.
- 4.5.1-B forensic investigation (report `docs/phase_4_5_1B_lab_attendance_forensics.md`) PROVED the legacy
  PWA silently skipped lab subjects in analytics (`getAttendanceData` required a QUIZ milestone and returned on
  error) — lab marking worked mechanically but counted nowhere. The PostgreSQL architecture does not repeat this
  defect.

### Possible verdicts

#### A — PRESERVE

Existing data is sufficiently complete and trustworthy.

#### B — PRESERVE WITH MANUAL CORRECTION

Most data is usable, but some manual correction/re-entry is required.

#### C — RESET DEVELOPMENT DATA

The data itself is sufficiently unreliable that a clean development baseline is safer.

### Critical rule

**Do not delete or reset anything during the audit.**

---

## 4.5.2 — Historical Track Coverage

**Status: COMPLETE** (2026-08-14).

- Track navigates the full semester history **2026-07-15 → current date**, bounded by the real
  `semester_start`/`semester_end` from `/student/me` (no hardcoded dates); date picker + Today + clamped arrows.
- Every scheduled session is visible: LECTURE, TUTORIAL, PRACTICAL/LAB, Pending, Attended, Missed, Cancelled.
- Practical sessions (BCS-551/552/553) appear as normal attendance sessions — the legacy
  quiz-window/attendance confusion is not repeated.
- Missing record = PENDING (no database row is created for pending).
- One canonical mutation endpoint (`POST /api/v1/attendance`) handles historical marking and Present↔Absent
  corrections; cancelled sessions rejected (409); reads scoped to the student's enrolled subjects; unique
  constraint preserved.
- Root-cause fix landed: frontend `AttendanceStatus`/`ClassType` enums corrected to the live backend contract
  (`Attended`/`Missed`/`Pending`, `P`), which had silently broken Track marking and history state rendering.
- Analytics engines untouched; verified labs flow through the canonical pipeline (`GET /attendance/summary/BCS-551`
  → practical 8/8 PENDING).
- The 26 historical lab sessions remain unmarked by design — the user establishes historical truth manually
  through Track. No invented attendance, no laboratory experiment rows.

---

## 4.5.3 — Real Sign Up

**Status: COMPLETE** (2026-08-14).

- `POST /api/v1/auth/register` + `/signup` page (Full Name, 13-digit Roll Number, Password,
  Confirm Password, show/hide, Create Account, link to Login).
- **Enrollment provisioning**: academic context resolved from authoritative configuration only —
  active `AcademicSession` → its `Semester` → its `Section` → all semester `Subject` rows — created
  transactionally with the user. The client cannot submit section/semester/session/subject IDs.
  Single-section semesters auto-assign; ambiguous configurations are rejected explicitly.
- **firebase_uid**: made NULLABLE (migration `c3d4e5f6a7b8`) for PostgreSQL-native identity;
  all 29 legacy UIDs preserved; column retained for Phase 14 (Firebase Retirement).
- **Passwords**: same `pbkdf2_sha256` format/verifier as login (`hash_password` added to
  `app/core/security.py`); never logged or echoed.
- **JWT**: issued immediately after registration through the exact `create_access_token` used by
  login (no second auth flow); student enters the app shell directly.
- Duplicate roll number → 409 (`IntegrityError` race guard); validation 422; ambiguous academic
  config 409/503; all failures roll back — no partial accounts, no orphan enrollments.

**Firebase must not return.**

---

# 🟢 Phase 5 — Attendance History

**Status: COMPLETE / FROZEN** (2026-08-14).

The History page is now a production-quality, session-based view of the
student's real attendance history:

- **Canonical data**: `GET /api/v1/attendance/history` (single endpoint, reused and
  extended in place) returns every scheduled class session of the student's enrolled
  subjects from the real semester start through today — the same `class_sessions` +
  `attendance_records` pipeline Track consumes. Missing record = **Pending**; cancelled
  sessions are their own state (never absent). No duplicate attendance source; no
  React-side calculation.
- **Semester bounds**: range resolved from the authenticated student's academic context
  (`/student/me` semantics via the same repository), clamped to `semester_start` and today
  (never the future), date inputs bounded the same way. No hardcoded dates.
- **Summary strip**: Total / Present / Absent / Pending / Cancelled / % computed
  server-side over the full filtered result set (aggregate FILTER query), not per page.
- **Filters (server-side)**: enrolled-subject select, attendance-state select
  (Attended/Missed/Pending/Cancelled), date-from/to (timezone-safe YYYY-MM-DD), and
  debounced search across subject code, subject name, class type, and date.
- **Pagination**: existing `limit`/`offset`/`total_count` contract extended with the new
  filters; "Load more" appends pages with id-based deduplication; filters reset offset and
  never mix result sets.
- **States**: loading skeletons, full error state, and truthful empty states
  (no classes in semester vs no matches for filters).
- **Authorization**: reads scoped to the authenticated user's enrollments end-to-end
  (`user_id` filter + `StudentEnrollment` join + subject filter on enrollments).
- **Consistency verified**: 2026-07-15 history (6 sessions, 3 Present / 3 Absent) matches
  Track's daily view exactly; Aditya's manual 07-17 BCS-553 practical mark appears
  Attended in both; summary pct 69.6% = 55/79 recorded (matches the dashboard).

### Architectural rule

History and Track consume the **same canonical attendance records** — satisfied, with
the `GET /attendance/history` endpoint being the single session-history source.

---

# 🟡 Phase 6 — Calendar & Academic Events

**Status: COMPLETE & FROZEN (2026-08-15)** — 6.0 audit (docs/phase_6_0_calendar_events_audit.md) ✅ · 6.1 foundational corrections ✅ (weekend convention, MID_SEMESTER_BREAK closure, /events read contract, dashboard enrollment scoping) · 6.2 calendar read model & API ✅ (`GET /api/v1/calendar?year=&month=`) · 6.3 calendar UI ✅ (`/calendar` route rendering the read model directly) · 6.4 events page upgrade ✅ (Upcoming/Today/Past grouping + filters on `/tools/events`) · 6.5 persistence + admin auth + seeding ✅ (role system, admin mutation API, validation registry, 17 quiz-event seeds) · 6.6 event→engine integration ✅ (session synchronizer: closures cancel, CLASS_CANCELLED cancels, EXTRA_*/SURPRISE_QUIZ materialize, substitution/working-Saturday project, idempotent + transactional + attendance-safe) · 6.7 verification/freeze ✅ (90/90 combined checks, exact baseline restored, architectural review clean).

Build the complete calendar/event experience.

## Calendar

- Month/day navigation
- Working days
- Weekends
- Holidays
- Academic events
- Class schedule
- Selected date
- Event indicators

## Events

- Upcoming
- Today
- Past
- Event details
- Event types
- Holiday indicators
- Substitution schedules

## Event persistence

Eventually support controlled event mutation:

```text
Admin
  ↓
Create Event
  ↓
Academic Events
  ↓
Calendar Engine
  ↓
Track / Dashboard / Quiz Eligibility
```

The event system must feed the existing engines instead of creating parallel rules.

---

# 🟡 Phase 7 — Quiz Eligibility & Schedule UX

## Phase 7.3 — Quiz Eligibility Hardening

Phase 7.3 is **COMPLETE & FROZEN**. This incorporates the final hardening passes originally requested/tracked outside the main roadmap structure (historically tracked as Phase 4A/4B/4C logic):

- **Backend reachability consistency:** Fixed zero-pending optimization reachability semantics. Top-level optimization now prefers reachable routes before minimizing attendance deficit, preserving Criterion I tie-breaking where appropriate. Dashboard attention classification now receives consistent reachability information.
- **Frontend safety:** Unreachable NOT_ELIGIBLE states no longer display misleading actionable Must Attend/Safe Skip guidance. Unknown/future eligibility states now degrade safely to a neutral "Unknown" badge instead of crashing. `SubjectCategory` TypeScript contract corrected to match backend values.
- **Cleanup & Infrastructure:** Removed dead `combined_threshold` plumbing from the service. Purged stale `__pycache__` files from tracking and local environments (which previously masked canonical math). Normalized Quiz I/II/III presentation labels without changing the persisted API contract. Added missing trailing newline to `eligibility_engine.py`. Added SUPERSEDED notice to the stale Phase 7.1 historical implementation report.
- **Verification:** Phase 1 eligibility verifier: 18/18. Phase 7.1 verifier: 26/26. Phase 3 propagation verifier: 26/26. TypeScript, ESLint, and production build all green. Database baseline restored exactly.

### 🔒 The Authoritative Quiz Eligibility Contract

The following semantics are fully verified, implemented, and frozen:
- Both Criterion I and Criterion II use: `(Lecture % + Tutorial %) / 2`
- No-tutorial subjects collapse naturally to lecture percentage.
- Quiz thresholds: Quiz I = 70%, Quiz II = 75%, Quiz III = 75%.
- Criterion I uses the cycle-specific attendance window.
- Criterion II uses the cumulative attendance window from semester commencement.
- Final eligibility uses **Criterion I OR Criterion II**.
- Must Attend / Safe Skip is calculated per criterion using that criterion's own window.
- Top-level optimization selects the best reachable route.
- Active `QUIZ_DAY` AcademicEvents are authoritative for quiz dates.
- Option-A quiz-day occurrences are independent attendance-bearing sessions but excluded from L/T eligibility counts.
- Subject isolation is preserved. Event lifecycle changes propagate through eligibility automatically.
- **The backend remains the authoritative source of eligibility mathematics and verdicts.**

The existing eligibility engine remains authoritative. Do not move quiz calculations into React.

---

# 🟡 Phase 8 — Attendance Analytics / Intelligence

**8.0 AUDIT COMPLETE (2026-08-15) — PASS** — read-only audit + contract design
(`docs/phase_8_0_attendance_analytics_audit.md`). No code, no DB change.
Headline findings: the current system has no analytics layer but every existing
surface already consumes the canonical engines (no second engine); the dashboard
service is the de-facto aggregator; **4 legacy gaps** must be bridged additively
(practical %, subject-level 75% must-attend/safe-skip, overall forecast,
forecast-impact deltas — all extensions of existing engine outputs); 2 React
display duplications + a hardcoded cycle=1 flagged for removal; N+1s in the
dashboard quiz snapshot and subject summaries documented; AT-RISK state and
trend series are roadmap intent with **no definition** — withheld pending
product decisions. Recommended 8.1 scope: backend-only additive analytics read
model (`/analytics/overview` + extended `SubjectAttendanceSummary`) + N+1 fixes,
consuming the canonical engines; no UI, no schema change, no new formula.

Turn the existing calculations into a strong intelligence experience.

## Overall analytics

- Current percentage
- Lecture/tutorial breakdown
- Subject-wise percentage
- Weekly trend
- Semester trend

## Forecasting

Examples:

> If you attend the next 3 classes…

> You can safely skip 2 lectures…

> You need 5 consecutive classes to reach 75%…

## Risk states

```text
SAFE
WATCH
AT RISK
CRITICAL
```

### Architectural rule

Dashboard, Track, History and Quiz Eligibility must remain consistent because they derive from the same canonical calculations.

This phase improves **analytics presentation and intelligence**, not by repeatedly rebuilding the core engines.

**8.3 ANALYTICS PAGE COMPLETE (2026-08-16)** — the roadmap's T-3 product decision
(dedicated Analytics page) is resolved: new `/analytics` route rendering the
canonical Phase 8.1 read model (`GET /api/v1/analytics/overview`) — overall
current/forecast + recorded-only semantics, the full Monday-start weekly
semester-trend series (null-gap, never 0%), and subject-wise rows with
Attendance Health, L/T/P counts, practical %, and the backend 75% optimizer
(must-attend / safe-skip / unreachable). Pure frontend composition — no backend
change, no DB change, no new formula, no React math; the legacy 3-state
SAFE/WATCH/CRITICAL overall status and the Phase 8.2 4-state subject health are
rendered exactly as emitted. `npx tsc --noEmit` · ESLint · `next build` green;
Phase 8.1 verifier 22/22 + Phase 8.2 verifier 18/18 re-run green; DB baseline
byte-identical. **PAGE REMOVED (2026-08-17)** — the dedicated `/analytics` route
and its nav entry were removed; the Phase 8.1 read model remains and is consumed
by the Dashboard (overall forecast + weekly series) and the Attendance tab
(per-subject health/optimizer/practical %). No backend/DB change.

## Phase 8.2 — Attendance Monitoring + Lab Domain Correction (COMPLETE 2026-08-15)

Attendance (/subjects) is now a pure attendance-monitoring page: quiz strategy
(must-attend / safe-skip / forecast / current-vs-forecast / quiz-window
denominator / required 75% / Defaulter badge) was removed from the UI — those
concepts remain only on the Quiz Eligibility surface. The reported "11 / 14"
denominator was traced to the canonical session table (14 real lectures through
today per theory subject) — not a quiz window — and is verified as such.
Attendance Health (backend-owned, additive `health` field, never banded in
React): **HEALTHY ≥ 75% · WATCH 65–<75% · AT RISK 60–<65% · CRITICAL <60%**
(supersedes the legacy SAFE/WATCH/CRITICAL presentation on the Attendance card;
`status` stays emitted for the frozen dashboard/analytics surfaces).

The laboratory domain is now explicitly separated: practical attendance =
canonical `ClassSession(PRACTICAL)` + `AttendanceRecord`; experiment
curriculum/progress = `laboratory_experiments`/`laboratory_records` (empty — no
fabricated data); mid-sem = an ADMIN-designated **session-level fact**
(`class_sessions.designation`, migration `e5f6a7b8c9d0`) tied to an actual
scheduled practical — never inferred from experiment counts and never given a
computed date. The missing faculty scheduling authority is documented (no
faculty system invented). See `docs/phase_8_2_implementation_report.md`;
verification 18/18 + full frozen regression.

**Authorized baseline/fixture change (final freeze, 2026-08-15):** the frozen
`verify_phase_7_1.py` check-23 fixture moved from `records == 89` to
`records == 92` (a FIXED expected value — no dynamic baseline). The +3 are
legitimate BCS-501 attendance marks (2026-08-04 LECTURE/TUTORIAL ATTENDED,
2026-08-13 LECTURE MISSED) entered through the canonical student attendance
mutation path BEFORE this audit; they are not verifier/test residue and must
never be deleted to satisfy the old fixture. This is an authorized
baseline/fixture change only — no product or attendance-engine change.

---

# 🟡 Phase 9 — Laboratory System

## Phase 9.0 — Laboratory Domain Audit & Specification (COMPLETE 2026-08-15)

READ-ONLY audit + specification only (no code/schema/API/UI). The laboratory
domain is a clean, intentionally empty foundation: practical attendance is
canonical `ClassSession(PRACTICAL)` + `AttendanceRecord` (verified 18/18),
experiment curriculum/progress tables (`laboratory_experiments` /
`laboratory_records`) are empty by design (no authoritative data — nothing
fabricated), and the mid-sem practical is an ADMIN-designated session-level
fact (`class_sessions.designation`, Phase 8.2) that never alters attendance
counting.

Key audit findings:

- **No engine/attendance-rule change required** — labs already flow through
  the canonical pipeline; cancelled excluded; pending stays pending; labs
  excluded from quiz eligibility.
- **Gaps**: (1) authoritative experiment curriculum (identity/titles/count)
  is UNKNOWN — legacy `LAB_RULES` "10 experiments" is not authoritative;
  (2) no experiment↔session linkage (`LaboratoryRecord.date_conducted` is a
  bare date); (3) no FACULTY role — only ADMIN; (4) no audit identity on
  designation/signature; (5) `/tools/laboratory` hosts the Track page (naming
  artifact).
- **Hard boundaries kept**: no `experiments >= 5 ⇒ mid-sem` rule, no fake
  mid-sem dates, no fabricated curriculum, students can never designate
  mid-sem, Quiz Eligibility and Phase 6 calendar architecture untouched.
- **Blocking product decisions** (before Phase 9.1): authoritative curriculum
  source · FACULTY role vs ADMIN-only · audit identity · experiment↔session
  linkage · mid-sem progress check vs free choice · student mutation boundary
  · grading/viva.

Full audit: `docs/phase_9_0_laboratory_domain_audit.md` (20 sections +
verification). **Phase 9.1 not started.**

## Phase 9.0b — Product Decision Review (COMPLETE 2026-08-15)

Decision matrix produced in `docs/phase_9_product_decisions.md` — one
recommendation per blocking decision, each labeled FACT-from-repository vs
PRODUCT RECOMMENDATION vs UNKNOWN/REQUIRES-REAL-WORLD-INPUT:

1. **Curriculum — E (hybrid)**: provenance-bound admin ingestion of an
   authoritative institutional catalog; NOTHING seeded until a real catalog
   exists; per-subject count = catalog row count (never a constant).
2. **Faculty role — DEFER**: keep STUDENT + ADMIN for 9.1; introduce FACULTY
   only with a defined signature/grading workflow (9.2+), as a narrower
   elevation via a capability matrix.
3. **Audit identity — minimal additive**: record timestamps + `signed_by` +
   `designated_by/at` + catalog provenance; no created_by on attendance.
4. **Experiment↔session linkage — nullable FK** `laboratory_records.
   class_session_id` + validation (PRACTICAL/mid-sem of same subject, not
   cancelled); single primary link; multiple experiments per session allowed.
5. **Mid-sem rule — advisory only**: "Eligible for mid-sem designation (X of
   Y)" derived from the real catalog; designation stays a manual ADMIN act;
   no auto-designation, no gate, no universal count.
6. **Student boundary — two-tier**: students self-track (status pending);
   only ADMIN/FACULTY sets SIGNED (official).
7. **Grading/viva — EXCLUDE from Phase 9**: defer to a separate
   academic-assessment phase; dormant `marks`/`remarks` columns retained.

## Phase 9.1 — Laboratory Attendance & Event Integration (COMPLETE 2026-08-15)

PRODUCT DECISION LOCKED: **Mid-Sem Practical and Lab Cancelled are NOT
separate laboratory attendance systems — they are Academic Events that modify
the canonical attendance schedule** (`AcademicEvent →
EventSessionSynchronizer → ClassSession → AttendanceRecord → existing
engines`). This supersedes the Phase 9.0 audit's additive read-model proposal
for 9.1; experiment management remains a future concern.

Implemented: two new event types (`MID_SEM_PRACTICAL`, `LAB_CANCELLED`,
subject-scoped, PRACTICAL-only, student-creatable for enrolled practical
subjects, optional `note`); the synchronizer resolves the deterministic
practical occurrence (reuses the timetable session — never duplicates — or
materializes exactly one extra on a non-lab day) and marks it with the
existing `ClassSession.designation = MID_SEM_PRACTICAL`; `LAB_CANCELLED`
cancels the matching occurrence via canonical `is_cancelled`. Attendance
flows through the normal mutation; cancelled rejects 409 and is excluded;
mid-sem Present/Absent are ordinary practical records; quiz eligibility
unchanged; state-based reconciliation keeps everything reversible and
idempotent; cancellation wins on a mid-sem + lab-cancelled conflict; attended
sessions are never deleted/cancelled. Additive read-model fields only
(`designation` on history/daily; `note` on events). No new tables beyond a
nullable `note` column and two PG enum values (migration
`a1b2c3d4e5f6_add_lab_event_types.py`); no new endpoints; no experiment
curriculum/progress; no FACULTY role; no grading/viva.

Verification: `verify_phase_9_1.py` **28/28**; frozen regressions 6.5 27/27 ·
6.6 36/36 · 6.7 31/31 · 7.2 26/26 · 8.1 22/22 · attendance-spec 15/15 ·
8.2 18/18 · compileall / tsc / ESLint / next build PASS.

⚠ **BASELINE DRIFT (owner decision required before final freeze):** the live
DB now has **95 attendance records** (was 92). The +3 are legitimate
owner-entered marks on BCS-502 LECTURE sessions (08-04, 08-05, 08-12 MISSED,
created 2026-08-15 16:19–16:20 UTC via the canonical mutation path) — not
verifier residue, not Phase 9.1 code. Per policy `verify_phase_7_1.py` was
NOT modified; its fixed `records == 92` (check 23) now fails at 95
(7.1 = 25/26). Authorize the fixed fixture 92 → 95 (as was done 89 → 92), or
accept check 23 as a documented known-failing baseline assertion.

Full details: `docs/phase_9_1_implementation_report.md`. Phase 9.1 code is
otherwise freezable; Phase 9.2 (experiment management) NOT started.

---

# ✅ Phase 10 — Settings, Feedback & Account Management

**COMPLETE & FROZEN** (10.0 · 10A · 10B · 10C · 10D · 10E). The Phase 2 foundations became real functionality end-to-end (UI → API → service → repository → database):

- **Settings (10A):** `SettingsModal` surface with the three preference toggles.
- **Profile (10B):** `sections.program` column + migration, `program` resolved from the stored section value in the profile read model, `StudentProfileResponse` completed (program/section/semester/session/academic dates), ProfileModal edits persisted via the real API.
- **Feedback (10C):** real `POST /api/v1/feedback` (feedback type, message 10–1000 trimmed, optional context, server timestamp, server-side user association); never fakes a successful submission; no GET/list/admin surface in this phase; verified by `backend/scripts/verify_phase_10c.py` (23/23).
- **Preferences (10D):** `user_preferences` table + GET/PUT `/api/v1/student/preferences` (lazy-create, replace semantics, server defaults false/false/MONDAY, user-isolated, no client identity); **storage/preference data only** — nothing sends reminders, marks attendance, or alters calendar/analytics; verified by `backend/scripts/verify_phase_10d.py` (18/18).
- **Freeze (10E):** audit report `docs/phase_10_completion_audit_report.md`, corrections (stale feedback copy removed, stale profile comment updated, Phase 10C verifier added), full regression + DB baseline proof + governance reconciliation in `docs/phase_10e_implementation_report.md`. All verifiers green, DB restored exactly, migration chain linear at head `c1d2e3f4a5b6`.

Original scope for reference:

## Settings

Potentially:

- Notification preferences
- Default landing page
- Attendance display preferences
- Reminder preferences
- Account preferences

Likely requires:

```text
user_preferences
```

plus GET/PUT API endpoints.

## Feedback

Implement a real feedback system:

```text
POST /feedback
```

with:

- Feedback type
- Message
- Optional context
- Timestamp
- User association

Never fake a successful submission.

## Profile

Complete:

- Name
- Roll number
- Section
- Program
- Semester
- Session
- Academic dates

---

# ✅ Phase 11 — Notifications & Reminders (COMPLETE & FROZEN)

Only after the academic/event architecture is stable.

**Status: COMPLETE & FROZEN (2026-08-21) — 11.0 architecture audit ✅ · 11A backend notification read model & contracts ✅ · 11B notification persistence + read-state ✅ · 11D notification center UX ✅ · 11E preference wiring verified — no additional implementation required ✅ · 11F final verification & freeze ✅ · 11C delivery model decision-gated/deferred (not implemented).**

Potential features:

- Upcoming class reminder ✅ (11A — CLASS_REMINDER, gated by the `class_reminders` preference)
- Quiz approaching ✅ (11A — QUIZ_APPROACHING, canonical next-upcoming quiz cycle)
- Attendance-below-threshold warning ✅ (11A — ATTENDANCE_THRESHOLD, engine banding)
- Must-attend warning ✅ (11A — MUST_ATTEND, engine optimizer deficit)
- Safe-skip information ✅ (11A — SAFE_SKIP, engine optimizer safe-skip)
- Academic event notification ✅ (11A — ACADEMIC_EVENT, dashboard upcoming-events selection)

### Architectural rule

Notifications consume engine outputs.

They do **not** independently calculate attendance.

### Sub-phase status

- **11.0** Architecture & Discovery Audit — ✅ COMPLETE (`docs/phase_11/phase_11_architecture_audit.md`).
- **11A** Backend notification read model & contracts (`GET /api/v1/notifications`, additive `NotificationKind`, on-read generation, `verify_phase_11a.py` 19/19) — ✅ COMPLETE (`docs/phase_11/phase_11a_implementation_report.md`). Zero DB change; no migration; no frontend; no scheduler.
- **11B** Notification persistence + read-state — ✅ COMPLETE (`docs/phase_11/phase_11b_implementation_report.md`). What 11B delivered:
  - Additive migration `d1e2f3a4b5c6` (single alembic head) creating the `notifications` table + `notificationkind` enum; chains linearly to `c1d2e3f4a5b6`.
  - Deterministic identity/idempotency: `UNIQUE(user_id, kind, occurrence_key)` where `occurrence_key` mirrors the Phase 11A natural-key reference (session id for CLASS_REMINDER, quiz cycle for QUIZ_APPROACHING, event id for ACADEMIC_EVENT, subject code for ATTENDANCE_THRESHOLD / MUST_ATTEND / SAFE_SKIP). Repeated generation of the same logical occurrence upserts in place (never duplicates); genuinely distinct occurrences stay distinct. Refresh preserves `date`, `is_read`, `is_dismissed`, `created_at`.
  - `Notification` model + `NotificationRepository` (owner-scoped, JWT-only) + `NotificationService` extended (snapshot-on-read generation, persisted inbox newest-first, unread count, `update_state`).
  - API: `GET /api/v1/notifications` now serves the persisted inbox with `unread_count`; `PATCH /api/v1/notifications/{notification_id}` for read/dismiss state (owner-scoped → 404 cross-user; idempotent; empty body → 422). 11A projection semantics unchanged.
  - `verify_phase_11b.py` 23/23 PASS; Phase 11A verifier re-run 19/19 PASS; DB baseline restored; no frozen system touched; no commit made.
- **11C** Delivery model — ⚪ NOT STARTED (decision-gated: in-app only vs scheduled sweep; deferred out of 11B, not invented).
- **11D** Frontend notification center UX — ✅ COMPLETE (`docs/phase_11/phase_11d_implementation_report.md`). What 11D delivered:
  - Notification bell in the authenticated `TopNav` with a backend `unread_count` badge (hidden at zero, capped at "99+").
  - Notification center (shell `ShellDialog`) listing the persisted inbox newest-first: kind badge/icon per `NotificationKind`, readable message, subject context + occurrence date, unread rows visually emphasized.
  - Actions via the existing 11B API: per-item "Mark as read" (unread rows only) and dismiss (removes from the inbox; stays dismissed server-side across regeneration). Cache is updated from the genuine PATCH response — success is never faked, failures surface in an inline banner with the list unchanged.
  - SWR integration: `useNotifications()` (key gated, one logical request; bell + center share the key so they dedupe and stay in sync) + `useNotificationMutation()`; `STANDARD_CACHE` revalidation only (no polling). Types mirror the backend `NotificationItem` / `NotificationsResponse` / `NotificationUpdate` contract in `types/api.ts`.
  - No push/email/SMS/scheduling/cron/worker/PWA behavior, no client-side notification logic, no backend change. `tsc --noEmit` PASS · ESLint PASS · `npm run build` PASS. No commit made.
- **11E** Reminder preferences wiring — ✅ VERIFIED, NO ADDITIONAL IMPLEMENTATION REQUIRED (`docs/phase_11/phase_11e_implementation_report.md`). The `class_reminders` gate lives inside 11A (`notification_service.py`, read at generation time; verified by 11A checks 7/8); `auto_mark_present` and `week_starts_on` remain storage-only per audit §5B/5C. SettingsModal copy + `types/api.ts` contract comment made truthful ("Class reminders are shown in the bell icon when enabled"). 11A verifier 19/19 PASS; 11B verifier 21/23 — checks 19/20 fail on diagnosed environmental data drift (pre-existing admin inbox rows + the verifier's own fixture shifting the admin's canonical quiz/event selection mid-run), NOT a code regression; a clean admin inbox passes 23/23. Frontend tsc/ESLint/build PASS. No commit made.
- **11F** Final verification & freeze — ✅ **PHASE 11 COMPLETE & FROZEN** (`docs/phase_11/phase_11f_verification_report.md`). The 11E drift (11B checks 19/20) and an 11A check-16 failure were confirmed as verifier determinism issues on a used inbox, NOT production defects; both verifiers were hardened **verifier-only** (checks 15/16/17 in 11A; 17/19/20 in 11B) to accumulation-compatible assertions (coverage + run-generated correctness + uniqueness + bounded growth; string-form baseline comparison — a UUID-vs-string bug in the first hardening attempt was also fixed). **Zero production code changed in 11F.** Final gates on the used environment: `compileall` PASS · `verify_phase_11a.py` **19/19** (×2) · `verify_phase_11b.py` **23/23** · frontend `tsc`/ESLint(Phase 11 files)/`npm run build` PASS. DB baseline restored (users 31 · admins 1 · notifications 11 — the admin's legitimate pre-existing rows); alembic single head `d1e2f3a4b5c6` unchanged. No commit made.

---

# 🟡 Phase 12 — Mobile / Responsive Experience

Desktop is currently the primary visual reference.

Build a genuine mobile experience rather than simply shrinking desktop.

Include:

- Mobile navigation
- Responsive top bar
- Bottom navigation where appropriate
- Responsive cards
- Touch targets
- Mobile date navigation
- Mobile Track workflow
- Mobile profile menu
- Responsive quiz cards
- Responsive analytics

## Status: 12.0 + 12A + 12B + 12C + 12D + 12E COMPLETE (2026-08-23)

- **12.0 architecture & implementation-readiness audit ✅** — `docs/phase_12/phase_12_architecture_audit.md`. Verdict: READY FOR ONLY A PHASE 12 SUB-PHASE (12A). Key findings: mobile navigation ABSENT (TopNav nav `hidden md:flex`); touch targets all below 40px; ShellDialog dialogs cannot scroll; Laboratory tab bar ≈380px nowrap clipped by the shell; NO BACKEND CHANGE REQUIRED; S4 prior art (`17_AI_HANDOFF.md:41-43`) = exactly 4 bottom tabs (Dashboard/Subjects/History/Profile) + Academic Tools from Profile, never a 5th tab; legacy `css/responsive.css` (not imported) documents 5 breakpoints + 44px touch minimums + FAB.
- **12A responsive foundation + mobile navigation ✅** — `docs/phase_12/phase_12a_implementation_report.md`. Bottom nav below `md` (Home `/dashboard` · Attendance `/subjects` · History `/history` · Profile `/profile`), Profile as the S4-compatible anchor opening the More sheet (Track `/tools/laboratory` · Laboratory `/laboratory` · Quiz Eligibility `/tools/quiz-schedule` · Calendar `/calendar` · Events `/tools/events`) via the existing `ui/sheet.tsx`; AppShell bottom clearance + safe-area; ShellDialog capped at 90dvh with scroll; NotificationCenter list viewport-capped; touch-target foundation in `ui/button.tsx` (mobile base sizes, `sm:` desktop restores — dialogs/sheets/bell/notification actions inherit ≥40px on mobile); NotificationBell mobile hit area ≥40px. Desktop ≥768px behavior unchanged (verified by diff scope + static gates; browser/manual testing is the user's responsibility — checklist in the 12A report). Zero backend/DB/migration/API/PWA changes.
- **12B Track / Dashboard / Calendar responsiveness ✅** — `docs/phase_12/phase_12b_implementation_report.md`. Real overflow fixed (Calendar month nav ≈310px vs 288px content at 320; now flex-wrap + responsive label) and grid cells enlarged (31→35px at 320 via `p-2 sm:p-4` + `gap-1 sm:gap-1.5`); Track date nav fluid (`flex-1` center column, input stretches) with ≥40px mobile controls (input `h-10 sm:h-8`, Today `sm:h-8`, Change buttons lose their `h-7` override); session-card header collisions fixed (fluid left column + wrapping badges); actions row auto-height (no longer clips the 12A h-10 buttons); dashboard wrap fixes (Today badge row, Overall delta row, Weekly `gap-2 sm:gap-3`). All changes `sm:`-gated or overflow-inert — desktop byte-identical. Zero backend/DB/migration/API/PWA changes; 12A files untouched. Static gates VERIFIED; browser/manual testing = owner (checklist in the 12B report).
- **12C Laboratory / Subjects / Quiz Eligibility / Events responsiveness ✅** — `docs/phase_12/phase_12c_implementation_report.md`. Phase 12C is **COMPLETE**.
    - **Frontend fixes**: Fixed non-responsive tab bars in Laboratory page, hardcoded wrapping issues in SubjectAttendanceCard and EventRow, and minimum widths on QuizEligibilityCard to ensure grid components wrap and respond gracefully down to mobile viewports.
    - **Urgent Correctness Bugfix**: Fixed an issue in the analytics aggregation pipeline where explicitly `CLASS_CANCELLED` sessions (which were properly mapped in the database) were not dropped from the applicable attendance denominators. Updated `AnalyticsService`, `DashboardService`, and `NotificationService` to strictly enforce the canonical `occurrence_is_cancelled` predicate from `practical_occurrence.py`. Verified all Phase 6-9 regression tests pass and that the backend math is pristine and sound.
- **12D Remaining responsive surfaces ✅** — `docs/phase_12/phase_12d_implementation_report.md`. Phase 12D is **COMPLETE**.
    - **Frontend-only touch-target refinements**: SettingsModal select upgraded from h-7 (28px) to h-9 sm:h-7 (36px mobile). EventFormDialog controls upgraded from h-8 (32px) to h-10 sm:h-8 (40px mobile).
    - **Grid responsiveness**: EventFormDialog date range and working/substitution controls changed from grid-cols-2 to grid-cols-1 sm:grid-cols-2 (single column on mobile, two-column restored on desktop).
    - **NotificationCenter**: Analyzed but NOT modified — current layout acceptable at 320px.
    - Zero backend/DB/migration/API changes. All static gates PASS. Desktop byte-identical.
- **12E Mobile polish + verification ✅** — `backend/scripts/verify_phase_12e.py`. Static invariant verifier asserting Phase 12 invariants (viewport export, bottom nav gated `md:hidden`, no fixed grid counts, no sub-36px interactive sizes on date inputs). All 5 invariants verified PASS. Zero backend/DB/migration/API changes. Desktop byte-identical.

---

# 🟡 Phase 13 — PWA / Installability

**Phase 13 COMPLETE** (2026-08-23): PWA/installability infrastructure implemented.
- Web manifest served at `/manifest.json` with name, short_name, icons, theme_color, background_color.
- Service worker registered at `/service-worker.js` with conservative caching strategy:
  - Static application assets cached on install
  - Network-first for all API requests (never cache authenticated data)
  - Cache-first for navigation with offline fallback
  - Old cache cleanup on activate
- SVG icons added at 192x192 and 512x512 in `frontend/public/icons/`
- Install prompt connected to `beforeinstallprompt` API and `display-mode: standalone` detection
- Standalone detection via `navigator.standalone` and `window.matchMedia("(display-mode: standalone)")`
- Online/offline state via `navigator.onLine` with truthful messaging
- Cached application shell: shell resources cached, data pages communicate offline status
- Does NOT claim offline attendance/quiz/history data availability
- PWA infrastructure does not alter Phase 12 mobile or desktop behavior
- Zero backend/database/API/migration changes
- `npx tsc --noEmit` PASS; `npm run build` PASS; `git diff --check` PASS
- Frozen areas (Phases 0–12, attendance/eligibility/calendar/event engines, auth) preserved
- Phase 14 (Firebase Retirement) remains unchanged

---

# 🟡 Phase 14 — Firebase Retirement (COMPLETE & FROZEN)

**Status: COMPLETE & FROZEN — 14.0 audit ✅ · 14A ✅ · 14B ✅ · 14C ✅ · 14D ✅ · 14E ✅ · 14F ✅.**

## 14.0 — Firebase Retirement Audit (COMPLETE, read-only, 2026-08-23)

Read-only repository-wide audit; report: `docs/phase_14/phase_14_architecture_audit.md`.
Verdict: **Phase 14 ready to proceed** — runtime authentication is fully JWT + PostgreSQL;
no Firebase Auth path reachable; no Firestore reads/writes from the Next.js app; Firebase
exists only as inert frontend SDK initialization, inert backend Admin-SDK initialization,
legacy deployment/config files, legacy root app, stale docs, migration scripts, and the
nullable `users.firebase_uid` legacy column. Zero code changed, zero DB mutations, zero
commits during the audit.

## 14A — Frontend Firebase Removal (COMPLETE, 2026-08-23)

Removed the frontend Firebase dependency entirely (JWT auth unaffected):
- `frontend/src/lib/api.ts` — dead `import { auth } from "./firebase"` removed.
- `frontend/src/lib/firebase.ts` — obsolete Firebase initialization module deleted.
- `frontend/package.json` / `package-lock.json` — `firebase` dependency removed (77 packages pruned).
- `frontend/.env.example` / `.env.local` — `NEXT_PUBLIC_FIREBASE_*` variables removed.
- Verification: `npx tsc --noEmit` PASS · `npm run build` PASS (15/15 routes) · `git diff --check` PASS · frontend/src Firebase search clean (only `firebase_uid` data-field strings remain, Phase 14D scope).
- Zero backend/DB/migration changes. Zero commits.

## 14B — Backend Firebase Removal (COMPLETE, 2026-08-23)

Removed the backend Firebase Admin SDK dependency entirely (JWT + PostgreSQL auth unchanged):
- `backend/app/core/firebase.py` — obsolete Firebase Admin SDK initialization module deleted.
- `backend/app/main.py` — `initialize_firebase` import + call removed (nothing else touched).
- `backend/requirements.txt` — `firebase-admin>=6.5.0` removed.
- venv — `firebase-admin` 7.5.0 + 13 Firebase transitive packages (google-cloud-firestore/storage/core, google-api-core, google-auth, grpcio, protobuf, etc.) uninstalled; `pip check` clean.
- Verification: `compileall` PASS · `app.main` imports clean without Firebase · OpenAPI shows all 32 paths incl. `/api/v1/auth/login`, `/api/v1/auth/register`, `/student/me`, `/student/sync` · `get_current_user`/`require_admin`/`HTTPBearer` intact · `git diff --check` PASS · diff limited to 3 backend files.
- `firebase_uid` column/model/schema/API references intentionally preserved (Phase 14D scope).
- Legacy migration scripts (`migrate_extract.py`, `migrate_execute.py`, `diagnose_failures.py`) retain their `firebase_admin` imports — they are historical tools with their own graceful blocked-exit path, out of scope for 14B.
- Zero DB/migration changes. Zero commits.

## 14C — Deployment / Configuration Cleanup (COMPLETE, 2026-08-23)

Removed all Firebase deployment/configuration artifacts (auth, identity, and runtime
behavior untouched):
- Deleted `firebase.json`, `.firebaserc`, `firestore.rules`, `firestore.indexes.json`.
- Removed Firebase-specific `.gitignore` entries (firebase-debug logs, `.firebase/` cache, `.firebaserc` config block).
- Deleted entirely-Firebase prompts (`14_FIREBASE_BACKEND_PROMPT.md`, `19_DEPLOYMENT_PROMPT.md`); removed Firestore/Firebase-Hosting sections and references from prompts `01/03/04/11/16` and `prompts/README.md` (index rows + release workflow).
- README: removed Firebase init/configuration instructions (`## Configure Firebase`, `## Deploy Firestore Rules`), Firebase Project/CLI requirements, and structure entries for the deleted config files. Legacy-app feature/tech-stack claims remain for Phase 14F doc reconciliation.
- Verification: all 6 files absent · `git diff --check` PASS · prompts/ Firebase search clean · diff limited to 13 files (8 deletions, 5 edits) · zero backend/frontend source changes.
- Preserved: `firebase_uid` model/schema/API/scripts (Phase 14D scope), legacy migration scripts (`migrate_extract.py`, `migrate_execute.py`, `diagnose_failures.py`), legacy root app, historical `docs/` (Phase 14F reconciliation).
- Zero DB/migration changes. Zero commits.

## 14D — firebase_uid / Data Cleanup (COMPLETE, 2026-08-23)

Removed the final application-level Firebase identity residue (`users.firebase_uid`):
- **Legacy scripts**: `backend/scripts/set_initial_password.py` and
  `backend/scripts/setup_single_user.py` now look up the user by canonical
  `roll_number` (`2401220100027`) instead of `firebase_uid`.
- **Model**: `backend/app/models/user.py` — `firebase_uid` column mapping removed.
- **Schema/API**: `StudentProfile` (`backend/app/schemas/student.py`), `/student/me`,
  `/student/sync` (`backend/app/api/v1/endpoints/student.py`), register
  (`backend/app/api/v1/endpoints/auth.py`), and `get_by_firebase_uid()`
  (`backend/app/repositories/user_repo.py`, dead code) — all `firebase_uid`
  references removed; `selectinload` unused import removed.
- **Frontend**: `frontend/src/types/api.ts` + `frontend/src/contexts/AuthContext.tsx`
  — `firebase_uid` field removed; profile page now displays `user.id` and the stale
  "Firebase identity is active (501)" error message was replaced with truthful copy.
- **Migration**: NEW `backend/alembic/versions/e1f2a3b4c5d6_drop_firebase_uid.py`
  (down_revision `d1e2f3a4b5c6`) — `DROP INDEX ix_users_firebase_uid` +
  `DROP COLUMN users.firebase_uid`; reversible (downgrade re-creates the nullable
  column + unique index, no invented values). APPLIED via `alembic upgrade head`.
- **Verification**: alembic single head `e1f2a3b4c5d6` · `compileall` PASS ·
  `npx tsc --noEmit` PASS · `git diff --check` PASS · app imports clean (32 paths,
  `/auth/login`, `/auth/register`, `/student/me`, `/student/sync` present) ·
  `StudentProfile` contract free of `firebase_uid` · JWT chain
  (`get_current_user`/`require_admin`/`HTTPBearer`/`create_access_token`) intact.
- **Database before/after (SELECT-verified)**: users 31 = 31 · admin 1 = 1 ·
  students 30 = 30 · enrollments 27 = 27 · attendance 159 = 159 · sessions 720 = 720 ·
  events 60 = 60 · all other table counts byte-identical · Aditya's row
  (roll `2401220100027`) untouched. Column and `ix_users_firebase_uid` index gone.
- Preserved: historical migration files (`7117a007a0da`, `c3d4e5f6a7b8`),
  `migrate_execute.py` (completed one-shot historical tool), historical docs
  (Phase 14F reconciliation). Zero commits.

## 14E — Regression Verification (COMPLETE, 2026-08-23)

Full auth/data-path regression proving Phase 14D removed `firebase_uid` without
regressing the PostgreSQL + JWT application:
- **In-process regression suite (real DB, guaranteed-rollback)**: 66/67 PASS —
  alembic head `e1f2a3b4c5d6` single; column + index gone; users 31 / admin 1 /
  students 30 / distinct rolls 31; password round-trip (pbkdf2_sha256, salted,
  wrong/empty rejected); login valid → token, wrong password → 401, nonexistent
  roll → 401; JWT mint + `get_current_user` valid + invalid → 401; `require_admin`
  ADMIN ok / STUDENT → 403; `/student/me` full contract (id, name, roll, role,
  section, semester, session, dates, quiz date) with NO `firebase_uid`; 16 core
  read paths (dashboard, attendance history/daily/summary, calendar month/today/
  date, events, quiz cycle/eligibility, subjects, timetable, analytics,
  preferences, notifications, lab summary); mutation contract (Attended/Missed/
  Pending accepted, cancelled → 409, future → 400, non-enrolled → 403); admin
  mutation wired to `require_admin`; feedback POST + preferences PUT; `/student/sync`
  no `firebase_uid`. The single harness FAIL was a harness artifact (the chosen
  session's subject was one the student is enrolled in — 403 correctly not
  raised), not a regression.
- **Frozen-phase verifiers (real DB, self-cleanup)**: 6.5 security/auth matrix
  27/27 · 6.6 event/session lifecycle 36/36 (incl. exact baseline restore) ·
  6.7 calendar 30/31 (check 7 expects pristine 18/0 seed counts; the live DB has
  4 user-created inactive QUIZ_DAY events from 2026-08-16 — pre-existing live
  data, NOT a 14D regression; all other checks + exact baseline restore PASS) ·
  7.1 quiz eligibility 26/26 · 10C feedback 23/23 · 10D preferences 18/18 ·
  11A notifications 19/19 · 11B notifications persistence 23/23 (after a
  compatibility fix) · 12E static invariants 5/5.
- **Corrective change (verifier compatibility, minimal)**: `verify_phase_11b.py`
  hardcoded the Phase 11B-era alembic head (`d1e2f3a4b5c6`); the Phase 14D
  migration legitimately advanced the head to `e1f2a3b4c5d6`. Updated the
  assertion + docstring to the current head (4 lines). No other verifier needed
  changes.
- **Persistent-mutation check**: one leaked temp user from a crashed harness run
  was detected via the baseline re-read and removed (test artifact); the leaked
  lab-experiment row from an early flawed direct-call test was likewise detected
  and removed. Final DB state byte-identical to the pre-verification baseline
  (users 31, all counts unchanged, alembic `e1f2a3b4c5d6`).
- Frontend: `npx tsc --noEmit` PASS · `npm run build` PASS (15/15 routes) ·
  Firebase search clean (`firebase_uid`/`firebase`/`firestore` absent from
  `frontend/src` and `backend/app`; only 3 stale comments remain — Phase 14F).
- Backend: `python -m compileall backend/app backend/scripts backend/alembic` PASS.
- Browser/manual testing NOT performed (owner responsibility).

## 14F — Freeze & Governance Reconciliation (COMPLETE, 2026-08-23)

Final reconciliation of the Firebase retirement:
- **README.md** rewritten — describes the active architecture (PostgreSQL → FastAPI →
  JWT API → Next.js → React UI), marks Firebase as **RETIRED**, and documents the
  legacy root application as preserved/pending separate retirement.
- **Historical banners** added to `backend/API_DESIGN.md`, `backend/DATABASE_DESIGN.md`,
  `backend/MIGRATION_NOTES.md`, `backend/MIGRATION_AUDIT.md` — each now explicitly
  states it describes the pre-JWT/pre-retirement design and is superseded, without
  rewriting their content.
- **docs/README.md** boundary banner — the docs/ series is documented as describing
  the legacy application (still present, not the active app).
- Governance synchronized: Phase 14 marked **COMPLETE & FROZEN**; Phase 15 designated
  as the separate **Legacy Web App + Legacy PWA Retirement** phase (subsequent
  planned phases renumbered 15→16 … 21→22).
- Verification: active-runtime Firebase search clean (frontend/src + backend/app +
  manifests + config) · `git diff --check` PASS · `tsc`/`build` PASS ·
  `compileall` PASS · alembic head `e1f2a3b4c5d6` unchanged · zero DB mutations ·
  zero commits.

**Original late-stage guidance (historical):** Firebase must not be removed prematurely —
the audit above proved the retirement conditions before any removal.

---

# ✅ Phase 15 — Legacy Web App + Legacy PWA Retirement

**Status: COMPLETE & FROZEN (2026-08-23).**

Retired the entire legacy web application and legacy PWA (as a whole, NOT as
Firebase cleanup — Firebase retirement was Phase 14, COMPLETE & FROZEN):

- Removed legacy runtime surface: root `index.html`, `js/` (21 files), `css/`
  (3 files), `assets/icons/` (3 files), `offline.html`, root `manifest.json`,
  root `service-worker.js`, `screenshot.png`.
- Removed legacy test/tooling artifacts: `test-e2e.js`, `scratch_pwa_mock_test.js`,
  `scratch_pwa_mock_test2.js`, `scratch_pwa_test.js`, `scratch_pwa_test2.js`.
- Removed legacy-only root package files: `package.json`, `package-lock.json`,
  `node_modules/` (express/jsdom/puppeteer — legacy-only; frontend deps live in
  `frontend/` and were unaffected).
- **Preserved `timetable.json`** — active data dependency of backend seed/verify
  scripts (`seed_academic_baseline.py`, `expand_baseline.py`,
  `seed_academic_events.py`, `verify_phase_7_1.py`, `verify_quiz_day_materialization.py`).
- Preserved historical provenance: docs/ series, historical walkthroughs, migration
  tooling, Alembic history, `regression_report.md`, `verification_report.md`,
  `repomix-output.xml`, prompts/ (all marked as historical via banners/notes).
- Documentation reconciled: README.md, docs/README.md, prompts/README.md updated to
  state the legacy runtime is retired and the active application is `frontend/` +
  `backend/`.
- Verification: `tsc` PASS · `npm run build` PASS (15/15; workspace-root lockfile
  warning now resolved) · `compileall` PASS · `git diff --check` PASS · zero active
  references to retired files · alembic head `e1f2a3b4c5d6` unchanged · zero DB
  mutations · zero commits.

The **current Next.js PWA** (Phase 13) is part of the active frozen application and
was NOT affected.

---

# ✅ Phase 16 — Production Security Hardening

**Status: COMPLETE & FROZEN (2026-08-23).**

Security audit + hardening of the active PostgreSQL + FastAPI + JWT + Next.js
application (backend-authoritative security). Zero database mutations; zero
migrations; alembic head unchanged (`e1f2a3b4c5d6`).

## What was hardened

- **JWT expiry**: bounded to 8 hours (env `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`;
  previously 30 days). `iat` claim added; `type == "access"` claim now enforced
  at validation (defense in depth). HS256 + env-driven secret remain.
- **Password policy** (registration; existing accounts unaffected):
  8–128 characters, at least one letter and one digit — backend-authoritative
  (Pydantic), frontend signup validation synced. PBKDF2-SHA256 (100k iterations,
  salted, constant-time compare) unchanged.
- **Brute-force protection**: in-process sliding-window rate limiter
  (`app/core/rate_limit.py`) — login 10 attempts/15 min, register 5/hour,
  per-IP, 429 + `Retry-After`. Distributed limiter (Redis) = Phase 17 dependency.
- **Login timing**: dummy PBKDF2 hash when the roll_number does not exist —
  eliminates user enumeration via response time.
- **Security headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options:
  DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy` (restricted).
  HSTS env-gated (`SECURITY_HSTS_ENABLED`, default off — localhost/dev safe).
- **Error handling**: global 500 handler logs server-side, returns generic
  "Internal server error" (no tracebacks/SQL/paths leaked); attendance mutation
  no longer echoes internal exception text to clients.
- **Logging**: `app/core/logging.py` — auth failures, unhandled 500s logged;
  no passwords/tokens/secrets ever logged.
- **CORS**: env-driven explicit origins (default localhost:3100), credentials
  enabled, no wildcard — production origin configurable via
  `BACKEND_CORS_ORIGINS`.
- **Secrets**: `backend/.env.example` documents JWT/security/rate-limit env vars
  (no real secrets); dev JWT secret default remains env-overridable.
- **Authorization audit**: all sensitive endpoints verified — JWT-scoped user
  resolution, enrollment-scoped reads/mutations (attendance, quiz, lab, events,
  subjects, timetable), owner-scoped preferences/notifications/feedback,
  DB-authoritative ADMIN (STUDENT → 403). No IDOR found.

## Verification

- `verify_phase_16.py` (new): 34/34 PASS — auth matrix (no/malformed/tampered/
  expired/wrong-alg/no-type tokens → 401), admin (ADMIN ok / STUDENT 403),
  cross-user isolation (distinct identities, owner-scoped notifications 404,
  enrollment-scoped subjects), rate limiting (429 + Retry-After), password
  policy (4 invalid cases → 422), security headers, CORS (allowed origin OK /
  disallowed rejected), error non-leak.
- Frozen verifiers re-run: 6.5 27/27 · 10C 23/23 · 10D 18/18 · 11A 19/19 — all
  PASS. `compileall` PASS · `tsc --noEmit` PASS · `npm run build` PASS (15/15) ·
  `git diff --check` PASS.

## Known limitations / Phase 17 dependencies

- Rate limiter is in-process (per-process memory) — multi-process production
  needs a distributed limiter (Redis).
- JWT lives in localStorage (frontend) — documented limitation; HttpOnly-cookie
  strategy would be a larger architectural change.
- No refresh tokens: short-lived access token + re-login is the chosen strategy.

---

# ✅ Phase 17 — Data Integrity & Migration Hardening

**Status: COMPLETE & FROZEN (2026-08-23)** — JWT production-secret guard ✅ ·
integrity audit ✅ · backup/restore ✅ (verified) · retention policy ✅ · seed
idempotency ✅ · semester-transition analysis ✅ · **NO MIGRATION REQUIRED** ·
cleanup: NONE REQUIRED.

## 17.0 — JWT Production-Secret Guard (COMPLETE)

`backend/app/core/config.py`: `APP_ENV` ("development" | "production", default
development). When `APP_ENV=production`, startup fails if `JWT_SECRET_KEY` is the
known development default or shorter than 20 characters — the error explains what
is required without printing the secret. Development behavior unchanged.
`backend/.env.example` documents `APP_ENV`. Verification:
`backend/scripts/verify_phase_17_jwt_guard.py` — 6/6 PASS (dev loads; production +
default rejected; production + short rejected; production + valid loads; no secret
leak; empty APP_ENV = development).

## 17.1 — Read-only integrity audit (COMPLETE)

- **Alembic**: single head `e1f2a3b4c5d6`; 14 migrations, linear chain, no gaps.
- **Duplicates**: zero duplicate users (roll_number), enrollments, quiz_schedules,
  attendance records (user+session), laboratory records (user+experiment),
  preferences, feedback, notifications. The 85 class_sessions groups that share a
  (date, subject, type) signature are **legitimate** — they are 2-hour lab blocks
  materialized from two distinct timetable entries (BCS-551/552/553). Two extra
  sessions share a NULL-timetable-entry signature; they are event-created
  (quiz-day/extras), carry no attendance, and are consistent with the synchronizer.
- **Orphans**: zero orphan rows in every FK relationship audited (enrollments,
  sessions, attendance, quiz schedules, events, lab records, notifications,
  preferences, feedback).
- **Out-of-bounds**: zero attendance records or class_sessions outside the
  semester span (2026-07-15 → 2026-12-31).
- **Known legacy state (documented, not defects)**: 28 users have NULL
  `hashed_password` and NULL `section_id` — these are Firebase-era accounts whose
  passwords lived in Firebase Auth (retired in Phase 14); they cannot log in and
  are preserved for history. Exactly one active academic session is configured.
- **Conclusion**: **NO MIGRATION REQUIRED** — no schema defect, no orphan data,
  no duplicate data requiring cleanup.

## 17.2 — Backup / restore (COMPLETE, verified)

- `backend/scripts/backup_database.ps1` — full backup via `pg_dump -Fc` through
  Docker exec; writes `backups/attendancedash_full_<timestamp>.dump` (host dir,
  gitignored). Verified working.
- `backend/scripts/restore_database.ps1` — `-TestSwitch` restores into an isolated
  temporary container (never the working DB); without the switch it restores the
  live dev DB with confirmation prompt.
- **Restore test executed**: backup → isolated `postgres:16` container on port
  55433 → restore → counts verified (users 31, attendance 159, sessions 721,
  enrollments 27, events 60, quiz_schedules 18, alembic `e1f2a3b4c5d6`); container
  removed afterward. The working DB was never touched.
- Strategy: development = local dumps; production = same pg_dump with production
  credentials + off-host storage + periodic restore tests; schema-only via
  `pg_dump --schema-only`; data-only via `--data-only`.
- **Retention policy (documented in `backup_database.ps1` header):**
  - Location: `backups/` directory (gitignored); local/server filesystem.
  - Format: PostgreSQL custom format (`-Fc`), compressed, single file.
  - Daily: latest 7 · Weekly: latest 4 · Monthly: latest 3 — older backups may be
    removed once the window is satisfied.
  - Restore safety: isolated restore (`-TestSwitch`) for verification; live
    restore requires explicit confirmation; never overwrite the working DB casually.
  - Security: backups contain the full database — never committed to Git;
    production backups in protected/encrypted storage (infrastructure layer).
  - Verification cadence: periodic isolated restore tests.
  - Automated rotation: NOT built in Phase 17 (future infrastructure phase may
    add scheduled rotation).

## 17.3 — Seed strategy (COMPLETE, audit only)

- `seed_academic_events.py` — idempotent (skips existing semantic identities),
  authoritative source (quiz_schedules), no resurrection. ✅
- `seed_academic_baseline.py` / `expand_baseline.py` — deterministic from
  `timetable.json`, skip existing rows. ✅
- `provision_admin.py`, `set_initial_password.py`, `setup_single_user.py` —
  targeted operational tools, not bulk seeds.
- No seed overwrites user data or resurrects deactivated records.

## 17.4 — Semester transition (COMPLETE, analysis only — no change)

- Session-scoped: `academic_sessions`, `semesters`, `sections`, `subjects`,
  `student_enrollments`, `timetable_entries`, `class_sessions` (materialized span),
  `quiz_schedules`, `academic_events`.
- Global: `users`, `attendance_records` (referenced via sessions), `feedback`,
  `notifications`, `userpreferences`.
- Hardcoded current-semester assumptions (acceptable for the current semester,
  documented as future architectural work, NOT production blockers):
  - `2026-07-15`/`2026-12-31` semester span (calendar engine clamping, verifiers).
  - `timetable.json` weekday 0=Monday convention.
  - Registration auto-assigns the single active semester/section.
  - Quiz cycles 1–3 fixed policy thresholds.
- Transition to a new semester = new `academic_sessions` row + `is_active` switch;
  no schema change required for Phase 17.

## 17.5 — Duplicate / orphan / cleanup (COMPLETE)

- Dedicated read-only audit script executed; findings above. No cleanup performed
  — nothing invalid was found. The two NULL-timetable-entry extra sessions are
  event-created artifacts with no attendance and no impact; left untouched
  (consistent with frozen synchronizer semantics).

## Remaining Phase 17 work

None — Phase 17 is COMPLETE & FROZEN. Scheduled backup rotation and production
backup runbook are deferred to Phase 18 (Production Infrastructure).

## Long-term academic model

The architecture should not remain hardcoded around:

```text
15 July 2026
```

It should understand:

```text
Academic Year
    ↓
Semester
    ↓
Start Date
    ↓
End Date
    ↓
Subjects
    ↓
Enrollment
    ↓
Timetable
    ↓
Attendance
    ↓
Quiz Cycles
```

This is essential for a real multi-semester product.

---

# 🟡 Phase 18 — Production Infrastructure

**Status: IN PROGRESS / PARTIAL — 18.0 ✅ · 18A ✅ · 18B ✅ · 18C ✅ · 18D ⚠️ PARTIAL (production deployment BLOCKED on missing infrastructure).**

## 18.0 — Production Infrastructure Audit (COMPLETE, read-only)

Audit report: `docs/phase_18/phase_18_0_infrastructure_audit.md`. Established the
production topology (HTTPS/CDN → Next.js → FastAPI → private PostgreSQL), frontend
(Next.js 16 SSR — needs Node runtime, not static), backend (uvicorn + proxy-header
trust needed), PostgreSQL privacy requirement, env contract, hosting comparison
(recommended: single VPS + Docker Compose), and Phase 18 slice plan (18A–18D).
Zero DB mutations, zero commits.

## 18A — Production Containerization & Orchestration (COMPLETE, 2026-08-23)

Created the production container foundation:

- `frontend/Dockerfile` — multi-stage Next.js 16 SSR image (node:20-alpine,
  npm 11 aligned, standalone output, non-root `nodejs` user, PWA preserved).
- `backend/Dockerfile` — python:3.13-slim FastAPI image (deterministic pip,
  non-root `appuser`, Alembic included, uvicorn workers via `UVICORN_WORKERS`
  default 1, `--proxy-headers`, healthcheck on `GET /health`).
- `docker-compose.prod.yml` — production stack: caddy reverse proxy (HTTP
  routing `/api/*` → backend, `*` → frontend), frontend, backend, postgres:16.
  Private networks: `proxy-net` (caddy/frontend/backend) + `data-net`
  (`internal: true`; backend ↔ postgres). PostgreSQL publishes NO host port.
  Only proxy port 80 exposed. Healthchecks + `unless-stopped` restart on all
  services. `depends_on` uses postgres healthcheck condition.
- `deploy/caddy/Caddyfile` — Caddy 2 HTTP routing with automatic
  `X-Forwarded-For` (rate-limiter client IP preservation; backend trusts proxy
  only because it binds inside the private network). TLS-ready placeholder
  domain `app.example.com` (HTTPS in a later phase).
- `deploy/.env.prod.example` — production env contract (no real secrets).
- `frontend/next.config.ts` — `output: "standalone"` (smallest justified change
  for a minimal runtime image; SSR + PWA preserved).
- `frontend/package-lock.json` — regenerated on Linux (npm 11) to resolve
  platform-specific optional deps (`@emnapi/*`) that Windows npm left out,
  making `npm ci` deterministic in the container.
- Docs: `docs/phase_18/phase_18a_containerization.md`.

Verification: `docker compose config` valid · backend image build PASS ·
frontend image build PASS · `npm ci` + `npm run build` PASS (15/15) ·
`compileall` PASS · `git diff --check` PASS. No containers started, no DB
touched, no cloud resources.

## 18B — Environment & Secret Management (COMPLETE, 2026-08-23)

Established a clean, explicit, production-safe environment/secret contract for
the 18A container architecture:

- **Production guard extended** (`backend/app/core/config.py`): when
  `APP_ENV=production`, startup also rejects a `DATABASE_URI` referencing
  localhost/127.0.0.1/host.docker.internal and any localhost CORS origin
  (in addition to the Phase 17 JWT-secret guard). Errors never print secrets.
- **Compose fail-fast** (`docker-compose.prod.yml`): required secrets use
  `${VAR:?}` — `POSTGRES_USER`, `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`,
  `BACKEND_CORS_ORIGINS`, `NEXT_PUBLIC_API_URL` fail compose startup when
  missing instead of silently interpolating empty values. `DATABASE_URI` is
  built from `POSTGRES_*` at runtime (overridable via `DATABASE_URI`).
- **Proxy trust boundary** (`FORWARDED_ALLOW_IPS` + pinned `proxy-net` subnet
  `172.28.0.0/24`): Uvicorn `--forwarded-allow-ips` trusts `X-Forwarded-For`
  ONLY from the proxy network CIDR; Caddy is the only trusted proxy; the
  Phase 16 rate limiter sees the real client IP; spoofing outside the subnet
  is ignored.
- **Env examples synchronized**: `deploy/.env.prod.example` (placeholders,
  required/optional split, secret/public markers), `backend/.env.example`
  (marked DEVELOPMENT ONLY), `frontend/.env.example` (public-var note).
- **Secret audit**: only example env files are tracked; dev credentials exist
  only in the dev example/defaults; no secrets in Dockerfiles, compose, or
  docs; `deploy/.env.prod` and `backend/.env` gitignored.
- Verification: `verify_phase_17_jwt_guard.py` **8/8 PASS** (JWT guard + new
  DB/CORS production rejections + no-secret-leak) · compose `config` fails
  fast without required vars and renders correctly with them · `compileall`
  PASS · `tsc` PASS · `git diff --check` PASS. No real secrets added; no
  deployment; zero DB mutations.

## 18C — Backup Automation + Retention + Off-Host Protection (COMPLETE, 2026-08-23)

Production-grade scheduled PostgreSQL backup implemented and verified in
isolation:

- **Backup container** (`deploy/backup/`, postgres:16-based): `run.sh`
  (scheduler with locking + pg_isready wait), `backup.sh` (pg_dump -Fc +
  verification: exists, ≥1KB, `pg_restore --list`), `offhost.sh` (copy
  contract: none/mount/sftp/s3/custom), `retention.sh` (keep latest
  `BACKUP_RETENTION_COUNT`, default 14; only files matching the naming
  convention; runs only after successful backup+off-host).
- **Compose wiring**: `backup` service on `data-net` (private), persistent
  `backup_data` volume, healthy-depends on postgres, `unless-stopped`,
  healthcheck, env via `deploy/.env.prod` (`${VAR:?}` for required).
- **Retention policy**: latest 14 local backups, rolling window, timestamped
  naming `attendancedash_full_<utc>.dump`.
- **Off-host contract**: OFFHOST_TYPE none/mount/sftp/s3/custom with
  placeholders only — no real credentials, nothing connected (deferred to
  deployment).
- **Restore**: documented runbook; isolated restore smoke test PASS (backup →
  disposable postgres → `pg_restore` → data verified → resources removed).
- **Secrets**: no real credentials; PGPASSWORD env (never argv); nothing
  logged; `.gitignore` already covers `backups/` + `deploy/.env.prod`.
- Docs: `docs/phase_18/phase_18c_backup.md`.

## 18D — Deployment & Verification (PARTIAL, 2026-08-23)

Local rehearsal deployment proved the full production mechanism works, but
**actual production deployment is BLOCKED on missing infrastructure**:

- **No production host/VPS** — no cloud compute target provisioned.
- **No production credentials** — no real `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`,
  or `BACKEND_CORS_ORIGINS` for a real domain exist.
- **No domain/DNS/TLS** — no real hostname; Caddy config ready (placeholders).
- **No off-host backup destination** — no external storage (OFFHOST_TYPE=none).

### What was delivered / verified (rehearsal, disposable, torn down):

1. **Deployment defects fixed**:
   - `backend/requirements.txt` — added `pyjwt>=2.10.0` (missing from deps;
     backend crashed at import without it). Genuine deployment defect, minimal
     fix.
   - `deploy/caddy/Caddyfile` — added `handle /health` route (backend health
     endpoint was not proxied; external health checks would fail).
2. **Rehearsal deployment**: full production stack (5 services) deployed locally
   with placeholder env values (temp file, never committed, disposable volumes).
   All services healthy: postgres → backend → backup → frontend → caddy.
3. **Backup verification**: `backup.sh` executed on the real backup container
   after seeding the disposable rehearsal DB; artifact 2972 bytes, pg_restore
   --list passed (11 TOC entries). Retention and off-host contract verified.
4. **Isolated restore**: backup restored into a separate disposable postgres:16
   container; data verified; container removed.
5. **Security**: no secrets in logs/argv; PostgreSQL private; only proxy port 80
   exposed; FORWARDED_ALLOW_IPS trust boundary verified.
6. **Docs**: `docs/phase_18/phase_18d_deployment.md` (full deployment report,
   blockers, and runbook).
7. **Application DB untouched**: working dev database `attendancedashpro_db`
   unchanged (INSERT/UPDATE/DELETE = 0). All rehearsal/restore containers and
   volumes cleaned (0 remaining).

### Blockers (production deployment cannot proceed without these):

- Production VPS/host → operator must provision.
- Production credentials → operator must generate and supply.
- Domain/DNS/TLS → operator must register and configure.
- Off-host backup destination → operator must provision (or accept none).

## 19 — CI/CD (COMPLETE & FROZEN — 2026-08-23)

# ✅ Phase 19 — CI/CD

Production quality gate established (`.github/workflows/ci.yml`):

```text
GitHub (PR / push to main)
   ↓
CI
 ├── integrity        — tracked secrets, env files, Firebase artifacts
 ├── backend          — compileall, import, JWT guard (8/8), static invariants
 ├── frontend         — npm ci (npm 11), tsc, lint (informational), build
 ├── docker           — backend + frontend + backup image builds
 ├── compose          — docker-compose.prod.yml config (CI placeholders)
 ├── migrations       — disposable postgres:16, alembic upgrade head, head verify
 ├── config-contract  — env example vs compose contract
 ├── backup-infra     — shell syntax + backup image build
 └── deploy           — DISABLED (${{ false }}); requires production env
```

- Deployment gate is **permanently disabled** until Phase 18D blockers resolve
  (no VPS, no credentials, no domain, no off-host destination).
- Lint is informational (`continue-on-error`) — 6 pre-existing ESLint errors
  live in frozen systems (AuthContext, auth pages, history page,
  service-worker.js); fixing them is out of scope. Authoritative gate = tsc +
  build.
- Migrations validated on a disposable postgres:16: single head
  `e1f2a3b4c5d6`, upgrade to head clean, DB revision matches head.
- All checks verified locally; working application DB untouched; no secrets;
  no deployment. Full doc: `docs/phase_19/phase_19_cicd.md`.

Development workflows remain quota-efficient (caching, no matrix, no browser
automation).

---

# 🔴 Phase 20 — Production QA

Perform a complete real-user journey.

## Account

- Sign up
- Login
- Wrong password
- Logout
- Refresh
- Session expiration

## Dashboard

- Name
- Attendance
- Weekly data
- Overall data
- Quiz data
- Alerts
- Events

## Track

- 15 July history
- Today's classes
- Future classes
- Present
- Absent
- Corrections
- Mark All Present
- Cancelled sessions

## History

- Complete records
- Filters
- Search
- Dates
- States

## Calendar

- Dates
- Weekends
- Holidays
- Events
- Classes

## Quiz

- Q1
- Q2
- Q3
- Thresholds
- Windows
- Must Attend
- Safe Skip
- Unresolved cycles

---

# 🔴 Phase 21 — Production Launch

**Status: BLOCKED (2026-08-24)** — launch pending; **21A (Account Audit & Cleanup) ✅ COMPLETE & FROZEN**.

## 21A — Account Audit & Cleanup (COMPLETE & FROZEN, 2026-08-24)

Read-only account inventory audit: **31 accounts** found (1 PROTECTED owner
ADMIN `2401220100027`; 1 LIKELY REAL USER `1234567890124`; 29 LIKELY TEST).
**24 test accounts proposed for deletion** (zero dependent data) — pending
user approval; **no deletion performed**. 28 accounts cannot log in (NULL
password; Firebase-era legacy, Phase 14 boundary). All user FKs are
`ON DELETE NO ACTION` (no cascade; no delete implementation exists). QA-window
deltas (5 attendance under owner, 62 notifications) left intact. Report:
`docs/phase_21/phase_21a_account_audit.md`. Deletion requires explicit user
approval of the proposed set.

## Required prerequisites (unmet)

### Gate A — Phase 20 manual browser QA
The 42-item manual browser QA checklist was delivered in Phase 20
(`docs/phase_20/phase_20_production_qa.md` §19). The user must complete and
report it. Agent has NOT performed any browser testing.

### Gate B — Phase 20 QA-window data disposition
Phase 20 reported 5 attendance records + 62 notifications with uncertain
provenance. The user must review and explicitly disposition them (confirm,
authorize cleanup, or document residual uncertainty).

### Gate C — Production infrastructure
- VPS/cloud host: **NOT PROVISIONED**
- Production credentials (`deploy/.env.prod`): **NOT CREATED**
- Domain + DNS: **NOT CONFIGURED** (placeholder `app.example.com`)
- TLS/HTTPS: **NOT PROVISIONED** (Caddy config HTTP-only, ready for TLS)
- Off-host backup destination: **NOT CONFIGURED** (OFFHOST_TYPE=none;
  operator must either provision or explicitly accept the risk)

## What is ready (verified pre-launch, waiting on gates)

- Dockerfiles, production compose, Caddy config, backup container — **verified
  in Phase 18A/18C/18D rehearsal**
- Environment contract, secret guard, production config validation — **verified
  in Phase 18B/17**
- CI quality gate with disabled deploy job — **verified in Phase 19**
- In-process QA, cross-surface consistency, frozen verifier regression — **verified
  in Phase 20**
- Manual browser QA checklist — **delivered to user, awaiting completion**

## Deployment sequence (when gates pass)

```text
Production Database
        ↓
Database Migration
        ↓
Backend
        ↓
Frontend
        ↓
Domain
        ↓
HTTPS
```

Once all three gates pass, the operator can execute the Phase 21 launch
sequence (provision → configure → migrate → deploy backend → deploy frontend
→ Caddy/HTTPS → backup → smoke → monitor → rollback).

Production data setup:

- Semester configuration
- Subjects
- Timetable
- Quiz schedules
- Academic events
- Initial administrative configuration

Monitoring:

- Server errors
- Database health
- API latency
- Authentication failures
- Uptime
- Backups

---

# 🔵 Phase 22 — Post-Launch

After real users begin using the system:

- Monitor errors
- Collect feedback
- Identify calculation discrepancies
- Improve UX
- Fix production bugs
- Optimize expensive queries
- Improve mobile experience
- Handle semester rollover

Only after the core product is stable should ambitious new features be added.

---

# 🔗 Critical Dependency Path

```text
PHASE 0
   ↓
PHASE 1
   ↓
PHASE 2
   ↓
PHASE 3
    ↓
PHASE 4
    ↓
PHASE 4.5
    ↓
PHASE 5  ← COMPLETE
    ↓
PHASE 6  ← COMPLETE
    ↓
PHASE 7  ← COMPLETE
   ↓
PHASE 8  ← COMPLETE
   ↓
PHASE 9  ← IN PROGRESS
   ↓
PHASE 10
   ↓
PHASE 11
   ↓
PHASE 12
   ↓
PHASE 13
   ↓
PHASE 14
   ↓
PHASE 15
   ↓
PHASE 16
   ↓
PHASE 17
   ↓
PHASE 18
   ↓
PHASE 19
   ↓
PHASE 20
   ↓
PHASE 21
   ↓
PHASE 22
```

This is a dependency path, not a rule that every subtask must be executed serially. Independent work can be parallelized when it is safe.

---

# 🏛️ Core Architectural Rules

## Rule 1 — Data, business logic and presentation stay separate

```text
DATA
PostgreSQL
   ↓
BUSINESS LOGIC
Repositories
   ↓
Services
   ↓
Engines
   ↓
PRESENTATION
Next.js
   ↓
Components
   ↓
UI
```

Do not move business calculations into React simply because it is convenient.

---

## Rule 2 — One canonical source of truth

Attendance must have one authoritative data path.

```text
Attendance Records
        ↓
Services
        ↓
Engines
        ↓
Dashboard
Track
History
Quiz
Analytics
```

No feature-specific duplicate calculations.

---

## Rule 3 — Data problems do not justify architecture rewrites

If historical data is bad:

```text
BAD DATA
   ↓
repair / reset / re-enter
```

NOT:

```text
BAD DATA
   ↓
rewrite engines
   ↓
rewrite services
   ↓
rewrite architecture
```

Manual data entry is acceptable.

Repeatedly rebuilding complex architecture is not.

---

## Rule 4 — Completed phases are frozen

Once a phase passes implementation and manual verification:

> **Do not touch it again unless a genuine defect or explicit product requirement requires reopening it.**

This prevents endless refactoring and regressions.

---

## Rule 5 — Empty states do not prove correctness

An endpoint returning:

```json
[]
```

does not prove the endpoint works.

Every feature must eventually be checked against meaningful real data.

---

## Rule 6 — Backend contracts must match the database

Do not invent frontend/backend fields that don't exist.

ORM → Schema → API → TypeScript → UI

must remain aligned.

---

## Rule 7 — Security is part of correctness

A feature is not complete if:

```text
User A can access User B's data.
```

Authorization must be checked at the backend boundary.

---

# ✅ Definition of "Production Ready"

AttendanceDash Pro is not considered finished merely because the UI looks good.

A real student must be able to:

```text
Sign Up
   ↓
Login
   ↓
See actual subjects
   ↓
See semester timetable
   ↓
Mark attendance
   ↓
See historical attendance
   ↓
See accurate percentages
   ↓
Understand attendance risk
   ↓
See quiz eligibility
   ↓
Know exactly how many classes they must attend
   ↓
See calendar/events
   ↓
Track laboratories
   ↓
Manage profile/settings
   ↓
Use desktop/mobile
   ↓
Install the application if supported
   ↓
Use it securely in production
```

And the same underlying data must produce consistent answers everywhere.

---

# 🧠 Adaptive Project Governance

The roadmap is the **direction**, not a prison.

The user is responsible for:

- Manual browser testing
- Reporting bugs
- Reporting unexpected behavior
- Reporting missing features
- Reporting UX problems
- Providing real-world feedback

The project roadmap is responsible for:

- Maintaining priorities
- Deciding where discoveries belong
- Reordering phases when necessary
- Protecting completed architecture
- Deciding when a phase should reopen
- Creating execution prompts
- Tracking completed vs remaining work
- Preventing unnecessary rework
- Preserving architectural integrity

### Working principle

> **User reports reality. Roadmap adapts to reality.**

A newly discovered bug may:

- remain inside the current phase,
- become a targeted hotfix,
- create a new sub-phase,
- reorder upcoming work,
- or reopen a frozen phase if the defect is architectural.

But we do **not** restart the project because of every issue.

---

# 🚦 Current Operating State

```text
PHASE 0  ████████████████████  COMPLETE 🔒
PHASE 1  ████████████████████  COMPLETE 🔒
PHASE 2  ████████████████████  COMPLETE 🔒
PHASE 3  ████████████████████  COMPLETE 🔒
PHASE 4  ████████████████████  COMPLETE 🔒

PHASE 4.5 ████████████████████  COMPLETE 🔒 (audit · Track · Sign Up)
PHASE 5  ████████████████████  COMPLETE 🔒 (Attendance History)

PHASE 6  ████████████████████  COMPLETE 🔒
PHASE 7  ████████████████████  COMPLETE 🔒 (7.0 audit · 7.1 contract+UI · 7.2 analytics · 7.3 hardening)
PHASE 8  ████████████████████  COMPLETE 🔒 (8.0 audit · 8.1 read model · 8.2 UI/lab correction)
PHASE 9  ████████████████████  COMPLETE 🔒 (9.0 audit · 9.1 events · 9.2.1 experiments · corrections)
PHASE 10 ████████████████████  COMPLETE 🔒 (10.0 audit · 10A settings · 10B program/profile · 10C feedback · 10D preferences · 10E freeze)
...
Phase 20 ░░░░░░░░░░░░░░░░░░░░  COMPLETE & FROZEN
Phase 21 ░░░░░░░░░░░░░░░░░░░░  BLOCKED (pre-flight gates)
Phase 22 ░░░░░░░░░░░░░░░░░░░░  PLANNED

> **Next phase:** Phase 18D — Deployment & Verification **IN PROGRESS (2026-08-23)** — production deployment BLOCKED on missing infrastructure (no VPS/cloud host, no domain/DNS/TLS, no production credentials, no off-host destination exist); local rehearsal deployment + full backup/restore verification being performed to prove the deployment mechanism.
```## Phase 6.5 — Event persistence, admin authentication & seeding (historical)

Phase 6.5 is **COMPLETE** (2026-08-14):

- **Admin authorization:** `UserRole` (`STUDENT`/`ADMIN`) column on `users` (migration `d4e5f6a7b8c9`, applied), `require_admin` dependency, `role` exposed via `/student/me` + `/student/sync`. Backend is authoritative — role is resolved from the DB per request, never from the JWT/body/query. `provision_admin.py` grants admin (no self-assignment path).
- **Mutation API (admin-only):** `POST /api/v1/events` (201), `PATCH /api/v1/events/{event_id}` (partial update via `model_fields_set`), `DELETE /api/v1/events/{event_id}` (safe deactivation, `active=false`, per ADR 004; re-enable via PATCH). Error mapping 422/404/409 (409 = identical ACTIVE duplicate, ported from legacy js/events-controller.js).
- **Validation registry:** `backend/app/services/event_registry.py` — `EVENT_TYPE_RULES` for all 14 event types (requiresSubject / requiresClassType / allowedClassTypes / isClosure / isGlobal, derived from legacy `AcademicEventRegistry` + engine closure semantics), `validate_event()`, `EventValidationError`.
- **Layering:** repositories/event_repo.py (queries + duplicate guard) → services/event_service.py (business rules, transaction per mutation) → endpoints (auth + error mapping). Schemas `AcademicEventCreate`/`AcademicEventUpdate`.
- **Admin UI (minimal, additive):** `/tools/events` shows an "Add Event" toolbar + Edit/Deactivate per row only when the backend-provided role is ADMIN (frontend visibility is UX only; the backend enforces). `EventFormDialog` is registry-driven (field visibility per event type) and never sends fields the model doesn't have. Phase 6.4 read experience untouched for students.
- **Seeding:** `seed_academic_events.py` derives exactly 17 QUIZ_DAY events from the authoritative `quiz_schedules` table (idempotency key = event_type+subject_id+start_date+end_date; verified 17→17 on rerun; deactivated rows never resurrected). No holidays/breaks/working-Saturdays were seeded because **no authoritative institutional dates exist anywhere in the repo** — documented data gap.
- **Verification:** `verify_phase_6_5.py` — 23/23 in-process checks PASS (security matrix incl. STUDENT 403s, admin mutations, duplicate 409, deactivation, partial PATCH, read-contract regression, calendar reflection, idempotent seeding). DB state: 17 seeded QUIZ_DAY events, 1 ADMIN user (2401220100027), 30 users total. Test rows cleaned; no attendance/session/enrollment/subject/quiz data touched.

Next: **Phase 6.6 — event→engine integration** (events feeding class_sessions/cancellations through the canonical pipeline; explicitly out of scope until then).

## Phase 6.6 — Event → engine integration

Phase 6.6 is **COMPLETE** (2026-08-14):

- **Objective:** persisted `AcademicEvent` records now operationally affect the canonical `class_sessions` → attendance → eligibility pipeline, matching the legacy invariant **ACADEMIC EVENT = EXACT-DATE SCHEDULE MUTATION** (docs/S4.3, docs/09, js/calendar-engine.js `getEffectiveDaySchedule`) — without rewriting any engine.
- **Synchronizer:** `backend/app/services/event_session_service.py` — `EventSessionSynchronizer.sync_event()` runs inside the event mutation transaction (create/update/deactivate). For every date the event touches it computes the engine's desired schedule (calendar engine day resolution + substitution + cancel/extra deltas from ALL active events, deterministic by priority + id) and reconciles `class_sessions`: closures/CLASS_CANCELLED → `is_cancelled=True` (never deleted; cancelled ≠ absent), EXTRA_LECTURE/EXTRA_TUTORIAL/EXTRA_PRACTICAL/SURPRISE_QUIZ → `is_extra=True` rows, substitution/WORKING_SATURDAY → materialized schedule (weekend projections deleted when reverted, attended rows never touched). State-based reconciliation is inherently idempotent — no unique constraints needed, no schema change.
- **Session repository:** `backend/app/repositories/session_repo.py` — reads (`get_timetable_entries`, bounded `get_session_date_span`, `get_sessions_in_range`) + writes (`add_session`, `delete_session`) + attendance-guard (`get_session_ids_with_attendance`). Sessions are only ever created inside the canonical baseline span (2026-07-15 → 2026-12-31); events outside it affect the calendar engine only.
- **Counting corrections (proven necessary, shapes unchanged):** cancelled sessions were previously counted as pending in Track/Track eligibility — `attendance_repo.get_subject_counts_up_to_date` / `get_subject_counts_between`, `dashboard_service._build_overall` / `_build_weekly` day_classes, and `calendar_service.get_month_view` session_count now exclude `is_cancelled`. All engines/formulas byte-identical.
- **No frontend changes:** the Phase 6.5 admin UI already exposes every event type through the registry-driven dialog.
- **Verification:** `verify_phase_6_6.py` — **36/36 PASS** (API-level with real DB + minted JWTs; rollback-transaction checks; read contracts calendar/daily/history/eligibility; idempotent double-sync; deactivation reversal; attendance-bound protection; exact baseline assertion: events=17, sessions=684, cancelled=0, extra=0, records=89). Phase 6.5 verifier regression 23/23 PASS. DB returned to exact baseline; test rows hard-deleted.

Next: **Phase 6.7 — verification/freeze** (not started; requires explicit go-ahead).

## Phase 6.7 — Calendar & Academic Events verification / freeze

Phase 6.7 is **COMPLETE** (2026-08-15). Phase 6 (6.0 → 6.6) is now **FROZEN**:

- **Verification:** three in-process verifiers, all green against the real DB (httpx ASGITransport + minted JWTs; no browser automation):
  - `verify_phase_6_5.py` — **23/23** (authz matrix, mutations, duplicate 409, PATCH semantics, deactivation/re-enable, read contracts, seeding idempotency).
  - `verify_phase_6_6.py` — **36/36** (every event-type effect, idempotency, move/reversal, attendance safety, cross-surface reads, exact baseline).
  - `verify_phase_6_7.py` (NEW) — **31/31** (engine weekend convention `[0,6]` + JS mapping, MID_SEMESTER_BREAK closure + priority tier 60, /events active-default/422/upcoming, calendar read model: outside-semester empty truth, July/December clamping, weekends, QUIZ_DAY working, all six closure types cancel their day's sessions with rows preserved, EXTRA_TUTORIAL/EXTRA_PRACTICAL exactly-one extras, WORKING_DAY_OVERRIDE calendar-only with zero session mutation, cancelled session → 409 on attendance, deactivate→PATCH re-enable convergence, seeding integrity (17 QUIZ_DAY, all active, nothing fabricated), full 10-table baseline restoration).
  - `compileall` PASS; combined **90/90 checks**.
- **Baseline (exact, restored after every run):** academic_events=17 · class_sessions=684 (0 cancelled, 0 extra) · attendance_records=89 · enrollments=18 · subjects=9 · quiz_schedules=18 · users=30 (1 ADMIN). No test residue; no fabricated dates.
- **Architectural review (static):** layering API→Service→Repository→DB intact; `EventSessionSynchronizer` is the ONLY session-sync path (event_service.py create/update/deactivate); engines byte-identical (no rewrites); no schema change beyond the Phase 6.5 role migration; zero hardcoded dates in `app/`; no React business logic (calendar/events pages render the read model; getDay() used for layout only); role resolved from DB per request; no new direct DB access in Phase 6 endpoints; no N+1 in the calendar read model (one enrollment-scoped range query).
- **Known limitations (frozen as documented):** sessions materialize only within the baseline span (2026-07-15 → 2026-12-31); extras carry no event linkage (count-matched by subject+class_type); institutional holiday/break/working-Saturday dates remain a data gap pending authoritative input; today-based views clamp to today. Browser/manual testing remains the user's responsibility.

Phase 6 is now **FROZEN**. Do not modify its contracts, engines, synchronizer, or verifiers without a new phase.

## Phase 7.0 — Quiz Eligibility & Schedule Reality audit

Phase 7.0 is **COMPLETE** (2026-08-15). Read-only audit; **no implementation, no DB mutation, no commit**:

- **Audit doc:** `docs/phase_7_0_quiz_eligibility_audit.md` (sections A–Y).
- **Verified (PASS):** eligibility formula `(Lecture% + Tutorial%)/2 ≥ threshold` (lecture-only when no tutorials) matches the legacy engines byte-for-byte; practicals excluded from eligibility but included in overall; quiz-day attendance flows through normal sessions; SURPRISE_QUIZ/EXTRA_* sessions flow through the canonical pipeline; ADR-010 windows identical (Q1 from semester start, QN from previous quiz date, end = quiz − 1); thresholds 70/75/75 from `eligibility_policies` match legacy `policies.quiz`; DB baseline re-confirmed (17/684/0/0/89/18/9/18/30/1); student `9999999999999` has 0 attendance records, admin has 84 (records=89 total across 5 users).
- **Headline finding:** backend `is_eligible` = reachability (pending>0 ⇒ `is_reachable`), so **every resolved cycle reports eligible=True** in current data; legacy requires deficit 0 (all would show "NEEDS ATTENDANCE"). Dashboard snapshot consequently reports 6/6 Eligible. **Q-D1**.
- **Other decision points (Q-D2…Q-D10):** eligibility API payload lacks window counts/percentages/Criterion I|II/quiz date/recoverable/explanation (reference UI cannot render without client-side math); `S4_PRODUCT_SPEC` says "(Criterion 1 qualifies) OR (Criterion 2 qualifies)" but both engines implement a single combined rule; `quiz_applicable`/`category` hardcoded in the service (labs rely on having no schedules); DB `combined_threshold` never read; raw-range vs teaching-day counting is latent; **rule G (students add/remove events) conflicts with the frozen admin-only event mutations**; overall denominator = recorded (pending excluded); quiz-day attendance requires a session; BCS-054 Q3 date pending from Aditya.
- **Next:** decisions Q-D1…Q-D10, then Phase 7.1 implementation (eligibility payload extension §S + reference subject-card UI + tri-state status; verifier `verify_phase_7_1.py`; regression + baseline restore).

## Phase 7.1 — Canonical Quiz Eligibility Contract + Reference Subject Cards

Phase 7.1 is **COMPLETE (2026-08-15) — PASS**. Report: `docs/phase_7_1_implementation_report.md`.

- **Schedule:** BCS-054 Q3 resolved to 2026-10-23 (authoritative `timetable.json`); seed-script override removed; `quiz_schedules` row updated; canonical `seed_academic_events.py` created the 18th QUIZ_DAY event (calendar-only). Canonical schedule = 18/18 dated SCHEDULED, exact match with the authoritative source. Q1/Q2 unchanged; Q3 window [09-28 … 10-22].
- **Eligibility contract (extended API, no parallel system):** `state` ELIGIBLE / RECOVERABLE / NOT_ELIGIBLE / UNRESOLVED; `is_eligible` = currently eligible (Q-D1 fixed); Criterion I (Lecture %) OR Criterion II (Combined average) per `S4_PRODUCT_SPEC.md:32-33` (Q-D3 fixed); persisted `eligibility_policies` thresholds for both routes (Q-D5 fixed); `subjects.quiz_applicable` authoritative — labs 404 (Q-D4 fixed); UI analytics (counts, pcts, avg, required, quiz date, explanation) exposed (Q-D2 fixed). Engine extended additively at the documented extension point — no rewrite, no second math model.
- **Reference UI:** `/tools/quiz-schedule` → "Quiz Eligibility": cycle tabs (Quiz I/II/III), per-subject reference cards (code, THEORY badge, status, attended/total/%, average vs required, expandable View Calculation with criteria + final + must-attend/safe-skip), loading/error+Retry/empty/unresolved states. React presentation-only.
- **Verification:** `verify_phase_7_1.py` **26/26**; frozen regression 6.5 **23/23**, 6.6 **36/36**, 6.7 **31/31** (Phase 6.7 count assertions maintained 17→18 for the new authoritative schedule — documented, not weakened); compileall/tsc/ESLint/`next build` green.
- **Database:** new baseline events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN). Mutation minimal/reversible (documented).
- **Known limitations / next:** Q-D6 teaching-day counting, Q-D8 overall denominator, Q-D7 student event-mutation capability, date-aware default cycle tab → Phase 7.2 (requires authorization; **HARD STOP** after Phase 7.1).

## Phase 7.2 — Quiz Eligibility Analytics Refinement

Phase 7.2 is **COMPLETE (2026-08-15) — PASS**. Report: `docs/phase_7_2_implementation_report.md`.

- **Q-D6 (raw-range counting):** NOT a defect under the locked spec — the session table IS the teaching-day-resolved effective schedule (baseline expands only teaching days; closures cancel; extras only on working days; cancelled excluded from counts). No counting change; regression-proven equivalence (18/18 combos), closure exclusion, extra counted, weekend-guard zero-session (checks 1–4).
- **Q-D8 (overall denominator):** recorded-only is canonical (legacy ERP `computeCurrentOverallAttendance`, S4 §10 current domain). Pending never converted to absent; exposed separately everywhere (dashboard card already showed it; quiz eligibility card gained a muted pending indicator). Verified 71.43% recorded-only vs explicitly-not 46.51% (checks 5–9).
- **Q-D7 (mutation/timing):** intentional product restriction (B). Attendance mutations are student-scoped + enrollment-authorized + cancelled-protected; EVENT mutations stay admin-only (frozen 6.5). Eligibility is read-time; mutations propagate immediately. Regression-proven (checks 10–12).
- **Date-aware default tab:** new canonical `GET /api/v1/quiz-eligibility/current-cycle` (next upcoming SCHEDULED quiz → latest resolved → fallback Quiz I); frontend preselects from it, manual selection overrides, no state mutation, no invented dates. Today → Quiz I; verified Quiz I→II→III→latest_resolved→fallback transitions (checks 13–15).
- **Verification:** `verify_phase_7_2.py` **26/26**; frozen regression 6.5 **23/23**, 6.6 **36/36**, 6.7 **31/31**, 7.1 **26/26**; compileall/tsc/ESLint/`next build` green.
- **Database:** zero mutations — exact baseline restored (events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN)). BCS-054 Q3 = 2026-10-23 confirmed.
- **Next:** Phase 8 (Attendance Analytics / Intelligence) on the canonical engines; Q-D9 and rule G require explicit product decisions before their own phases. **HARD STOP after Phase 7.2 — no commit made.**

## Phase 8.0 — Attendance Analytics & Intelligence audit / contract design

Phase 8.0 is **COMPLETE (2026-08-15) — PASS**. Read-only audit; **no implementation, no DB mutation, no commit**:

- **Audit doc:** `docs/phase_8_0_attendance_analytics_audit.md` (sections A–W).
- **Architecture:** no analytics layer exists; the dashboard service is the de-facto aggregator and already consumes the canonical engines (no second engine, no React business math). Canonical chain intact: class_sessions → attendance_records → engines → (Phase 8 analytics read model) → API → React.
- **Inventory (23 items):** every existing analytics surface catalogued (overall/weekly/today %, subject current/forecast %, quiz-window %, states, optimizer deficits, history summary, banding) with pending/cancelled/extra/practical/semester/quiz-window treatment per metric — all recorded-only current, forecast-as-pending, ERP class-weighted overall, cancelled excluded, labs excluded from eligibility.
- **Legacy gaps (4, all additive — NOT new formulas):** practical % not exposed (Python engine computes counts only); subject-level 75% must-attend/safe-skip not exposed (legacy `optResult`); overall forecast not exposed (legacy `computeForecastOverallAttendance`); forecast-impact deltas not exposed (legacy `calcForecastImpact`).
- **React duplications flagged (NOT fixed):** `WeeklyAttendanceCard` re-derives the day bar %; `SubjectAttendanceCard` applies its own 75/65 banding vs the canonical 80/60 band and hardcodes cycle=1. Dead `TodayClassesCard`/`FormulaCard` documented.
- **Performance:** N+1s in the dashboard quiz snapshot (per-subject eligibility with repeated events fetch) and subject summaries (per-subject count query); overlapping range scans; one import-time `date.today()` default on `/attendance/summary`. No fixes in this phase.
- **Security:** all reads authenticated + user/enrollment-scoped; one gap flagged (`GET /attendance/summary/{subject_code}` lacks the enrollment 404 the quiz endpoint has). AT-RISK state and trend series withheld — roadmap intent with no definition (product decisions T-1…T-4).
- **Verification:** compileall PASS · tsc --noEmit PASS · `verify_phase_7_2.py` 26/26 PASS · DB baseline exact (events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN) · BCS-054 Q3 = 2026-10-23). **Zero DB mutation (SELECT only).**
- **Next:** Phase 8.1 (backend additive analytics read model only) after explicit authorization from the product owner. **HARD STOP after Phase 8.0 — no commit made, Phase 8.1 NOT STARTED.**

## Phase 8.1 — Canonical Analytics Read Model

Phase 8.1 is **COMPLETE (2026-08-15) — PASS**. Backend-only additive analytics read model implementing the Phase 8.0 contract exactly; **no UI, no DB mutation, no schema change, no commit**:

- **Report:** `docs/phase_8_1_implementation_report.md`.
- **Subject analytics (additive):** `SubjectAttendanceSummary` gains `current_practical_pct`, `forecast_practical_pct`, and `optimization` (subject-level 75% must-attend/safe-skip via the attendance engine's own `optimize_attendance` — `lecture_deficit`/`tutorial_deficit` = must-attend, `safe_skip_lecture`/`safe_skip_tutorial` = safe-skip). Practicals use the canonical class-session/attendance-record pipeline — no quiz-window dependency, no separate lab engine; Pending stays Pending, cancelled excluded. All pre-existing fields unchanged.
- **Analytics overview:** new authenticated, enrollment-scoped, read-only `GET /api/v1/analytics/overview` — overall current (ERP Σatt/Σrecorded, recorded-only), overall forecast (pending-as-attended), pending count, a Monday-start weekly read-model series (recorded-only, null gaps), and per-subject current/forecast/optimization. Pure consumer of the canonical engines; no AT-RISK, no trend product semantics, no forecast-impact deltas (documented non-goals).
- **Dashboard N+1 fixes (contract-identical):** quiz snapshot now uses batched `get_quiz_eligibility_for_subjects` (single canonical engine path); subject summaries use one grouped `get_subject_counts_for_user` query; Today/Overall/Weekly share one enrollment-scoped range scan. Dashboard JSON shape byte-identical; measured 54 → 23 queries on the dashboard read path.
- **Endpoint hygiene:** `/attendance/summary` default date now resolved per-request (no import-time `date.today()`); `/attendance/summary/{code}` now returns the quiz-endpoint-style enrollment 404 (no cross-user exposure).
- **Verification:** `verify_phase_8_1.py` **22/22** (auth, enrollment scoping, ERP overall, forecast, pending, subject summaries, practical %, must-attend/safe-skip + optimizer edge cases, weekly read model, dashboard compatibility + N+1 correctness with query counting, runtime-date behavior, enrollment protection, no duplicate attendance math, exact baseline, frozen 7.2 invariants). Frozen regression: 6.5 **23/23** · 6.6 **36/36** · 6.7 **31/31** · 7.1 **26/26** · 7.2 **26/26** — no assertion weakened. Static: compileall PASS · `npx tsc --noEmit` PASS.
- **Database:** zero mutation — exact baseline before/after (events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN)). BCS-054 Q3 = 2026-10-23 unchanged.
- **Next:** Phase 8.2 (frontend consumption of the read model: practical % + must-attend/safe-skip on Subjects, overall forecast + weekly series, remove duplicated card banding/cycle) after explicit authorization; T-1 AT-RISK and T-3 Analytics page remain product decisions. **HARD STOP after Phase 8.1 — no commit made, Phase 8.2 NOT STARTED.**

## Phase 8.2 — Frontend Consumption of the Canonical Analytics Read Model

Phase 8.2 is **COMPLETE (2026-08-15) — PASS**. Frontend-only consumption of the Phase 8.1 read model; **no backend change, no DB mutation, no commit**:

- **Typed analytics client:** `AnalyticsOverviewResponse`/`OverallAnalytics`/`WeeklyAnalyticsItem`/`AnalyticsSubjectItem` types (exact match to the backend schema) + extended `SubjectAttendanceSummary` (`current_practical_pct`, `forecast_practical_pct`, `optimization`) + `useAnalyticsOverview()` SWR hook (`/api/v1/analytics/overview`, standard cache).
- **Subjects page:** `SubjectAttendanceGrid` now loads every subject's backend summary from ONE overview request (no per-subject N+1); each card renders backend practical % (+forecast) and the 75% must-attend/safe-skip from `summary.optimization`. The duplicated 75/65 client banding was removed (no backend status field exists for subjects, so none is invented) and the hardcoded `cycle = 1` was replaced with the canonical `useCurrentQuizCycle()` (Phase 7.2 mechanism) driving the quiz eligibility badge.
- **Dashboard:** `OverallAttendanceCard` gains an additive backend forecast line (pending-as-attended); `WeeklyAttendanceCard` now renders the backend weekly series (Monday-start weeks, backend `current_pct`, null = truthful gap, never 0%) instead of re-deriving day-bar percentages in React.
- **Dead component cleanup:** `TodayClassesCard.tsx` and `FormulaCard.tsx` verified unused (zero imports/routes) and deleted.
- **No React business math:** all rendered percentages/forecasts/deficits/safe-skips come from backend fields; React only formats/clamps width for presentation.
- **Verification:** `npx tsc --noEmit` PASS (0 errors) · ESLint clean on all changed files · `next build` PASS. Backend untouched; frozen phases untouched.
- **Next:** Phase 8.3 (if any) after explicit authorization; T-1 (AT-RISK), T-2 (trend semantics), T-3 (dedicated Analytics page), T-4 (multi-class forecast wording) remain product decisions. **HARD STOP after Phase 8.2 — no commit made, Phase 8.3 NOT STARTED.**

## Attendance UI Refinement — Specification Alignment + Reference UI

**COMPLETE (2026-08-15) — PASS.** Aligned the implementation with the authoritative attendance specification and implemented the reference Attendance UI. Two spec conflicts were escalated to the user and authorized before implementation; full report: `docs/attendance_ui_refinement_report.md`.

- **Quiz-day attendance (user decision: materialize):** quiz-day attendance is a real attendance event. 7 LECTURE sessions materialized on the SCHEDULED quiz dates that lacked one (`scripts/materialize_quiz_day_sessions.py`, idempotent + `--undo`); all 18 quiz dates now recordable. Eligibility windows end at `quiz_date − 1`, so eligibility is untouched; subject + overall attendance now include quiz-day sessions. Sessions 684 → 691 (documented baseline change).
- **Student-adjustable events (user decision: shared schedule, subject-scoped):** students may create/update/deactivate the flexible subject-scoped event types (extras, cancellations, surprise quizzes) for their own enrolled subjects; global/closure/quiz-schedule events remain admin-only. Enrollment check mirrors the attendance path; the event synchronizer never cancels/deletes quiz-day sessions.
- **Reference Attendance cards:** header (code · THEORY/LAB · name · canonical status badge), prominent primary %, lecture/tutorial sections with required + must-attend/safe-skip, combined average with formula caption, practical section for labs, expandable Details with real backend forecast/optimizer values. Backend emits `required_pct` (75) and per-subject `status` (SAFE/WATCH/CRITICAL) additively; banding consolidated into the attendance engine (single definition).
- **Latent fix:** successful attendance mutations previously 500'd (`AttendanceMutationResponse.student_id` → `user_id`) — required for quiz-day attendance to be recordable.
- **Verification:** `verify_attendance_spec_alignment.py` 15/15; frozen regressions 6.5 (27/27), 6.6 (36/36), 6.7 (31/31), 7.1 (26/26), 7.2 (26/26), 8.1 (22/22) — the 6.5/7.2 student-event 403 assertions and 7.1 check 5 were deliberately re-scoped to the new policy (documented). compileall / `tsc --noEmit` / ESLint / `next build` green. No commit made.
