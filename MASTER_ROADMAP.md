# AttendanceDash Pro — Master Roadmap

> **Project Source of Truth**
>
> This document defines the direction, phase structure, priorities, architectural boundaries, and production path for AttendanceDash Pro.
>
> **Current position:** Phase 6 (Calendar & Academic Events) **COMPLETE & FROZEN** ✅ — 6.0–6.7 all verified. Phase 7.0 (Quiz Eligibility & Schedule Reality) **AUDIT COMPLETE** ✅ — read-only audit delivered (`docs/phase_7_0_quiz_eligibility_audit.md`). Phase 7.1 (Canonical Quiz Eligibility Contract + Reference Subject Cards) **COMPLETE** ✅ — 26/26 verification + full regression; see `docs/phase_7_1_implementation_report.md`. Phase 7.2 (Quiz Eligibility Analytics Refinement) **COMPLETE** ✅ — 26/26 verification + full regression (6.5/6.6/6.7/7.1 all green); see `docs/phase_7_2_implementation_report.md`. Phase 8.0 (Attendance Analytics & Intelligence Audit / Contract Design) **COMPLETE / FROZEN** ✅ — read-only audit + contract design delivered (`docs/phase_8_0_attendance_analytics_audit.md`); zero code, zero DB change. Phase 8.1 (Canonical Analytics Read Model) **COMPLETE** ✅ — 22/22 verification + full regression (6.5/6.6/6.7/7.1/7.2 all green); see `docs/phase_8_1_implementation_report.md`. Phase 8.2 (Frontend Consumption of the Canonical Analytics Read Model) **COMPLETE** ✅ — typed analytics client + backend-derived subject/overall/weekly analytics; tsc/ESLint/`next build` green; zero backend/DB change. **Attendance UI Refinement (spec alignment + reference UI) COMPLETE** ✅ — authoritative attendance spec aligned (student-adjustable subject-scoped events, quiz-day attendance sessions, event sync guard, attendance-mutation 500 fix) + reference Attendance cards; 15/15 spec verifier + full frozen regression (6.5/6.6/6.7/7.1/7.2/8.1 all green); see `docs/attendance_ui_refinement_report.md`. **Phase 8.2 (Attendance Monitoring + Lab Domain Correction) COMPLETE** ✅ — Attendance page corrected to attendance-only (quiz strategy removed; the "14" traced to the canonical session table — real 14 lectures through today, not a quiz window); canonical backend-owned Attendance Health (HEALTHY ≥75 / WATCH 65–<75 / AT_RISK 60–<65 / CRITICAL <60) added; compact card redesign; lab domain separation with the smallest safe session-bound mid-sem designation (admin-only `ClassSession.designation`, migration applied, no fabricated experiment data); 18/18 Phase 8.2 verifier + full frozen regression (6.5/6.6/6.7/7.1/7.2/8.1/attendance-spec all green); see `docs/phase_8_2_implementation_report.md`.

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
| 7 | Quiz Eligibility & Schedule UX | 🟡 **7.0 AUDIT COMPLETE (2026-08-15)** — read-only audit: eligibility math verified against legacy engines & real DB data; schedule reality captured (BCS-054 Q3 UNRESOLVED); 10 decision points (Q-D1…Q-D10) documented for Aditya. Implementation blocked on decisions. |
| 8 | Attendance Analytics / Intelligence | ✅ **8.0 AUDIT COMPLETE / FROZEN (2026-08-15)** — read-only audit + contract design (`docs/phase_8_0_attendance_analytics_audit.md`). **8.1 CANONICAL ANALYTICS READ MODEL COMPLETE (2026-08-15)** — 22/22 verification + full regression (6.5/6.6/6.7/7.1/7.2 all green); see `docs/phase_8_1_implementation_report.md`. **8.2 FRONTEND CONSUMPTION COMPLETE (2026-08-15)** — typed `useAnalyticsOverview`, backend practical % + 75% must-attend/safe-skip on Subjects, forecast + weekly series on Dashboard, dead components removed; no backend/DB change. **ATTENDANCE UI REFINEMENT COMPLETE (2026-08-15)** — spec alignment: student-adjustable subject-scoped events (shared schedule; global/closure admin-only), quiz-day attendance sessions materialized (sessions 684→691, eligibility untouched), synchronizer guard, attendance-mutation 500 fix; reference Attendance cards; 15/15 spec verifier + 6.5/6.6/6.7/7.1/7.2/8.1 regressions all green; see `docs/attendance_ui_refinement_report.md`. **8.2 ATTENDANCE MONITORING + LAB DOMAIN CORRECTION COMPLETE (2026-08-15)** — Attendance page corrected to attendance-only (quiz strategy removed; "14" traced to canonical session table — real, not quiz-window); canonical backend-owned Attendance Health (HEALTHY ≥75 / WATCH 65–<75 / AT_RISK 60–<65 / CRITICAL <60); compact card redesign; lab domain separation + smallest safe session-bound mid-sem designation (admin-only `class_sessions.designation`, migration `e5f6a7b8c9d0`, no fabricated experiment data); 18/18 verifier + 6.5/6.6/6.7/7.1/7.2/8.1/attendance-spec regressions all green; see `docs/phase_8_2_implementation_report.md`. |
| 9 | Laboratory System | 🟡 **9.0 AUDIT COMPLETE (2026-08-15)** — read-only audit: lab domain, `laboratory_experiments`/`laboratory_records` (0 rows each), 3 lab subjects (BCS-551/552/553), 146 PRACTICAL sessions, curriculum source confirmed unavailable; 7 product decisions documented. **9.1 COMPLETE (2026-08-15)** — Mid-Sem Practical + Lab Cancelled as canonical Academic Events through the canonical ClassSession pipeline (no separate lab attendance system); migration `a1b2c3d4e5f6`; 28/28 verifier + all frozen regressions green; see `docs/phase_9_1_implementation_report.md`. **9.2.0 AUDIT COMPLETE (2026-08-15)** — read-only audit of experiment management domain; DB baseline (22 events · 691 sessions · 95 records · 0 lab experiments · 0 lab records); schema gaps identified (no class_session_id FK, no audit columns); proposed migrations A+B; API + UI/IA designed; **curriculum blocker confirmed**: no authoritative experiment catalog exists; Phase 9.2.1 scope defined; see `docs/phase_9_2_0_laboratory_experiment_audit.md`. **9.2.1 COMPLETE (2026-08-16)** — laboratory experiment management: migrations `f1a2b3c4d5e6f` + `f6a5b4c3d2e1f` (experiment `description`/`is_active`/UNIQUE(subject_id, experiment_number); record `class_session_id`/`signed_by`/`created_by`/`updated_by`); full repository/service/API surface (summary, curriculum, records POST/PATCH/DELETE, activity, admin catalog POST/PATCH/DELETE, admin signing); dedicated `/laboratory` frontend route (Practical Attendance / Experiments / Activity tabs); empty curriculum stays an honest empty state — **no fabricated experiment data, attendance engine untouched**; 29/29 verifier + 6.5/6.6/7.2/8.1/attendance-spec/8.2/9.1 frozen regressions green (6.7/7.1 drift-only failures documented); see `docs/phase_9_2_1_implementation_report.md`. **FOCUSED TRACK CORRECTION (2026-08-16)** — a 2-hour lab block (two contiguous timetable periods) is now ONE attendance occurrence (read-model collapse in `app/engines/practical_occurrence.py`; Track/summary/history/analytics/dashboard/calendar all count the lab once; one mutation ⇒ one AttendanceRecord) and future dates are view-only (mutation API 400 + Upcoming UI, no mark-all); no schema change, no ClassSession merge, attendance engine untouched; new `verify_track_lab_fix.py` 16/16; frozen verifiers updated only where they encoded the old per-period counts (6.6 22/23/24, 8.1, 8.2 1/6/7, 9.1 12/13, 7.2 5/6, attendance-spec 3); 7.1/6.7 drift unchanged; see `docs/track_lab_attendance_correction_report.md`. **FOCUSED HISTORY FILTERS CORRECTION (2026-08-16)** — /history filters crashed with `Cannot read properties of undefined (reading 'total_count')`; backend History API audited healthy (subject/state/inclusive-date/search filters, occurrence-level status matching, filtered total_count + summary), root cause was frontend Load-more rendering while SWR returns history=undefined for the new filter key; Load-more now gated on `history` + stale rows dropped on filter change (skeleton while loading, no row mixing); frontend-only fix, practical occurrence grouping untouched; new `verify_history_filters.py` 20/20; frozen regressions green except pre-existing owner-data drift (7.1 24/26, 6.7 28/31, 8.1 21/22 — all fixture drift, none weakened); see `docs/history_filters_correction_report.md`. **FOCUSED QUIZ DAY RECOVERY + VERIFIER HARDENING (2026-08-16)** — forensic audit found all 18 seeded QUIZ_DAY events inactive, 7 quiz-day sessions missing (incl. the canonical 10-23 BCS-054), and owner BNC-501 07-31 extras deleted by date/shape-based verifier cleanup; reactivated exactly the 18 seeds (quiz_schedules-backed + 08-14 creation window; owner events untouched), restored the 6 canonical uncovered-date quiz-day sessions via the idempotent `materialize_quiz_day_sessions.py` (10-16 BCS-502 correctly absent — Option-B covered; the audit's 7th row was the owner's 08-17 test-event session, intentionally not restored); hardened 3 verifiers to ownership/artifact-scoped cleanup (events-correction 42/42, track-lab-fix 16/16, history-filters 20/20 — explicit captured IDs, never date/shape windows; track-lab captures only session deltas, never the collapsed daily view's pre-existing block row); new `verify_quiz_day_restore.py` 11/11 ×2; owner 07-31 extras healed via the canonical sync and preserved; records 122 unchanged, sessions 698, events 38, quizzes 18/18; frozen verifiers NOT weakened — remaining reds are owner-data drift from the owner's duplicate active BNC-501 08-24 quiz-day event `6019a478` (6.5 check 20, 6.7 checks 4/6/7, 7.1 check 6; 7.1 check 5 PASSES proving the 10-23 canonical session restored); see `docs/quiz_day_recovery_report.md`. |
| 10 | Settings, Feedback & Account Management | ⚪ Planned |
| 11 | Notifications & Reminders | ⚪ Planned |
| 12 | Mobile / Responsive Experience | ⚪ Planned |
| 13 | PWA / Installability | ⚪ Planned |
| 14 | Firebase Retirement | 🔴 Later |
| 15 | Production Security Hardening | 🔴 Later |
| 16 | Data Integrity & Migration Hardening | 🔴 Later |
| 17 | Production Infrastructure | 🔴 Later |
| 18 | CI/CD | 🔴 Later |
| 19 | Production QA | 🔴 Later |
| 20 | Production Launch | 🔴 Later |
| 21 | Post-Launch | 🔵 Ongoing |

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

**7.0 AUDIT COMPLETE (2026-08-15)** — see `docs/phase_7_0_quiz_eligibility_audit.md`. Read-only audit; no code changed. Headline finding: the backend's `is_eligible` (reachability) diverges from the legacy "currently-meets-threshold" definition (Q-D1), and the reference-UI data contract (window lecture/tutorial %, Criterion I/II, recoverable state, quiz date, explanation) is not yet exposed by the API (Q-D2). Implementation (Phase 7.1+) requires decisions Q-D1…Q-D10 from the product owner.

**7.1 IMPLEMENTATION COMPLETE (2026-08-15) — PASS** — see `docs/phase_7_1_implementation_report.md`. BCS-054 Q3 resolved to 2026-10-23 (canonical 18/18 schedule); canonical eligibility states (ELIGIBLE/RECOVERABLE/NOT_ELIGIBLE/UNRESOLVED) with the official "(Criterion I) OR (Criterion II)" policy; extended eligibility API (no parallel system); reference subject-card UI on `/tools/quiz-schedule` (cycle tabs, View Calculation); `verify_phase_7_1.py` 26/26; regression 6.5 23/23, 6.6 36/36, 6.7 31/31. DB mutation: BCS-054 Q3 schedule row + the canonical 18th QUIZ_DAY event (minimal, reversible). Dashboard snapshot corrected automatically via the new `is_eligible` semantics (dashboard code untouched).

**7.2 IMPLEMENTATION COMPLETE (2026-08-15) — PASS** — see `docs/phase_7_2_implementation_report.md`. Q-D6 raw-range counting resolved as NOT a defect under the locked spec (session table IS the teaching-day-resolved schedule; closure/extra/weekend-guard regression-proven); Q-D8 overall denominator = recorded-only (ERP/legacy/S4 §10; pending never converted to absent, made explicit on the quiz card); Q-D7 = intentional product restriction (event mutations stay admin-only; eligibility is read-time; regression-proven); date-aware default Quiz tab via new canonical `GET /api/v1/quiz-eligibility/current-cycle` (next upcoming → latest resolved → fallback Quiz I; frontend preselects, manual tabs override, no invented dates). `verify_phase_7_2.py` 26/26; regression 6.5 23/23, 6.6 36/36, 6.7 31/31, 7.1 26/26. Zero DB mutations (exact baseline restored).

The backend eligibility architecture is already substantially implemented and audited.

Now complete the user-facing experience.

For every relevant subject:

- Quiz I
- Quiz II
- Quiz III
- Required percentage
- Quiz date
- Attendance window
- Current percentage
- Eligibility
- Must Attend
- Safe Skip
- Lecture/tutorial breakdown
- Unresolved state
- Policy ambiguity

### Critical rule

The existing eligibility engine remains authoritative.

Do not move quiz calculations into React.

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

# 🟡 Phase 10 — Settings, Feedback & Account Management

Turn the Phase 2 foundations into real functionality.

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

# 🟡 Phase 11 — Notifications & Reminders

Only after the academic/event architecture is stable.

Potential features:

- Upcoming class reminder
- Quiz approaching
- Attendance-below-threshold warning
- Must-attend warning
- Safe-skip information
- Academic event notification

### Architectural rule

Notifications consume engine outputs.

They do **not** independently calculate attendance.

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

---

# 🟡 Phase 13 — PWA / Installability

Implement genuine installability:

- Web manifest
- Service worker
- Icons
- Install prompt
- Standalone detection
- Offline strategy
- Cached application shell
- Correct online/offline states

Do not claim offline functionality unless the underlying data strategy actually supports it.

---

# 🔴 Phase 14 — Firebase Retirement

**Late-stage phase.**

Do not remove Firebase prematurely.

Before retirement, prove:

```text
Frontend
 ├── No Firebase Auth
 ├── No Firebase SDK dependency
 ├── No Firestore reads
 ├── No Firestore writes
 └── No Firebase-specific state

Backend
 ├── No firebase-admin
 └── No Firebase authentication dependency

Data
 └── PostgreSQL is authoritative
```

Then:

1. Remove frontend Firebase dependencies.
2. Remove Firebase configuration.
3. Remove legacy code.
4. Archive required legacy data if necessary.
5. Update deployment/configuration.
6. Remove Firebase dependencies.

---

# 🔴 Phase 15 — Production Security Hardening

## Authentication

- Password policy
- Secure password hashing
- JWT expiry
- Refresh strategy if required
- Token invalidation strategy
- Brute-force protection
- Login rate limiting

## Authorization

Verify every sensitive endpoint against cross-user access:

```text
Can User A access User B's data?
```

Especially:

- Attendance
- History
- Quiz eligibility
- Laboratory
- Profile
- Events
- Feedback
- Preferences

## Database

- Constraints
- Indexes
- Foreign keys
- Uniqueness
- Cascading behavior
- Transaction boundaries

## API

- Validation
- Error handling
- CORS
- Security headers
- Production logging

---

# 🔴 Phase 16 — Data Integrity & Migration Hardening

Before production:

- Database backup
- Restore test
- Migration test
- Rollback strategy
- Seed strategy
- Semester transition strategy
- Duplicate prevention
- Orphan detection
- Data cleanup procedures

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

# 🔴 Phase 17 — Production Infrastructure

Move from:

```text
Development PC
 ├── Next.js
 ├── FastAPI
 └── Docker PostgreSQL
```

to production infrastructure:

```text
                    Users
                      │
                 HTTPS / CDN
                      │
              ┌───────▼────────┐
              │ Next.js         │
              │ Frontend        │
              └───────┬────────┘
                      │ HTTPS
              ┌───────▼────────┐
              │ FastAPI         │
              │ Backend         │
              └───────┬────────┘
                      │
                Private network
                      │
              ┌───────▼────────┐
              │ PostgreSQL      │
              └────────────────┘
```

Exact hosting choices will be made later based on cost, reliability and requirements.

---

# 🔴 Phase 18 — CI/CD

Establish a production quality gate:

```text
GitHub
   ↓
Push
   ↓
CI
 ├── TypeScript check
 ├── Python checks
 ├── Frontend build
 └── Migration checks
   ↓
Deployment
```

Development workflows should remain quota-efficient, while production receives appropriate verification.

---

# 🔴 Phase 19 — Production QA

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

## Laboratories

- Subjects
- Experiments
- Records
- Statuses

## Profile

- Information
- Settings
- Logout

---

# 🔴 Phase 20 — Production Launch

Only after QA passes.

Deployment sequence:

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

# 🔵 Phase 21 — Post-Launch

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
PHASE 6
    ↓
PHASE 7
   ↓
PHASE 8
   ↓
PHASE 9
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
PHASE 7  ████████████████████  COMPLETE 🔒 (7.0 audit · 7.1 contract+UI · 7.2 analytics refinement)
...
PHASE 20 ░░░░░░░░░░░░░░░░░░░░  PLANNED
PHASE 21 ░░░░░░░░░░░░░░░░░░░░  ONGOING
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
