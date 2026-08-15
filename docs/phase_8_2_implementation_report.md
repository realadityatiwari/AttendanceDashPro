# Phase 8.2 — Attendance Page Correction + Laboratory Domain

**Result:** PASS (18/18 new checks; full frozen regression green; no commit made)

This phase corrected the Attendance (/subjects) surface so it is a pure
attendance-monitoring page (no quiz strategy), introduced a canonical
backend-owned **Attendance Health** classification, and established the
**laboratory domain foundation** (practical attendance / experiment progress /
mid-sem designation kept as separate facts, with the smallest safe, session-
bound mid-sem designation supported by the current ADMIN-only authority model).

---

## 1. Root-cause trace of the "14" (the reported defect)

The defect report claimed the Attendance cards showed a "legacy quiz-window
denominator" (`11 / 14`). The source was traced end-to-end:

- The card's `attended / total` values come from `GET /api/v1/analytics/overview`
  → `AnalyticsService.get_overview` → `AttendanceService.get_subject_summaries`
  → `AttendanceRepository.get_subject_counts_for_user`, which counts **canonical
  `class_sessions` rows** filtered to `date <= today` and `is_cancelled = false`.
- **The "14" is the real number of lecture sessions that have happened through
  today** (2026-08-15) for every theory subject (3 lectures/week since
  2026-07-15 → 14 sessions; verified by direct SQL). It is NOT a quiz window,
  a hardcoded constant, or a legacy field — there is no fixed "14" anywhere in
  the backend, and the summary provably ignores `quiz_schedules`.
- The *real* defects were **presentation ownership**: the Attendance card was
  rendering quiz-strategy concepts (must-attend, safe-skip, forecast, current-vs-
  forecast, required 75%, the quiz "Eligible/Defaulter" badge) on an
  attendance-monitoring page, and the legacy SAFE/WATCH/CRITICAL banding (80/60)
  was shown instead of an Attendance Health classification.

**Fix:** the canonical denominator stays (it was already correct); the UI no
longer displays quiz strategy, and the backend now emits an additive Attendance
Health classification. Verified (checks 1–3): summary totals == session-table
counts through today; an inserted session changes the total (no constant); a
quiz-window change leaves the attendance summary byte-identical.

---

## 2. Attendance Health (canonical, backend-owned)

New canonical engine classification in `app/engines/attendance_engine.py`
(`classify_attendance_health`) — the single definition; React never bands:

| Band | Range (current, recorded-only %) |
|---|---|
| `HEALTHY` | ≥ 75% |
| `WATCH` | 65% – < 75% |
| `AT_RISK` | 60% – < 65% |
| `CRITICAL` | < 60% |
| (none) | nothing recorded → `null` |

- Emitted additively on `SubjectAttendanceSummary.health` (and therefore on
  every `AnalyticsSubjectItem`). Threshold mapping documented here and in the
  engine; chosen per the product requirement (75% academic target, explicit
  AT_RISK band below it).
- The legacy `status` (SAFE/WATCH/CRITICAL) field remains emitted untouched —
  the dashboard/analytics/verifiers consume it (frozen behavior preserved);
  only the Attendance card presentation switched to `health`.
- UI mapping uses existing semantic tokens only (success/warning/danger) —
  no new color system: HEALTHY → success, WATCH → warning, AT_RISK → soft
  danger, CRITICAL → solid danger.

---

## 3. Attendance card redesign (Part A)

`SubjectAttendanceCard.tsx` rewritten — attendance monitoring only:

- **Header**: code · THEORY/LAB badge · subject name · Attendance Health badge
  (backend `health`). Removed the quiz "Eligible/Defaulter" badge.
- **Main**: large overall percentage ("Overall Attendance" — theory: combined
  average; lab: practical %) + status-colored progress bar.
- **Breakdown**: two balanced Lecture / Tutorial blocks (ATTENDED / TOTAL +
  percentage). No "Required 75%", no must-attend, no safe-skip.
- **Theory without tutorials**: lecture block + "No tutorials — average equals
  Lecture %" caption; no fabricated Tutorial 0/0.
- **Lab**: "Practical Attendance" (percentage + attended/total) and a
  "Mid-Sem Practical: Not scheduled / {date}" row that comes only from the
  backend designation (never fabricated). No "Lab Progress 4/10" — the
  authoritative experiment curriculum does not exist yet.
- **Footer**: formula caption ("Average = (Lecture % + Tutorial %) / 2" —
  presentation only; the backend computes) + expandable "View Details"
  (attended/missed/pending per type — no forecast, no optimizer).
- Layout is compact/horizontal (side-by-side blocks, tight header) to reduce
  vertical elongation; cards remain responsive (1/2/3 columns).

`/subjects` page copy updated to "how your attendance is going…" (attendance-
only; no quiz-eligibility claim).

---

## 4. Laboratory domain (Part B)

### 4.1 Domain separation (verified, not re-engineered)

| Concern | Mechanism | Status |
|---|---|---|
| Practical attendance | `ClassSession(PRACTICAL)` + `AttendanceRecord` (canonical pipeline) | Already canonical; verified (checks 6–7) |
| Experiment curriculum | `LaboratoryExperiment` | Exists; empty; authoritative titles unavailable → **nothing fabricated** |
| Student experiment progress | `LaboratoryRecord` | Exists; empty |
| Mid-sem scheduling/designation | **NEW** `ClassSession.designation` (session-level, ADMIN-controlled) | Smallest safe foundation |

- Cancelled practical sessions never become Pending/Absent (excluded from the
  denominator — verified in check 6 via a rollback-transaction cancellation).
- Attendance is never derived from experiment counts: with
  `laboratory_experiments` empty, lab attendance totals equal the session table
  exactly (checks 7–9).

### 4.2 Mid-sem practical designation (smallest safe foundation)

The product workflow requires the mid-sem practical to be tied to an **actual
scheduled practical session** — never `experiments_completed >= 5 →
next_practical_is_midsem`. The current architecture has an ADMIN role (Phase
6.5) but no faculty scheduling system, so the boundary is documented and the
smallest safe foundation implemented:

- **Schema**: `class_sessions.designation` (nullable enum
  `sessiondesignation`: `MID_SEM_PRACTICAL`). Migration
  `e5f6a7b8c9d0_add_session_designation.py` — additive, nullable, zero data
  change (all 691 sessions untouched, NULL = regular).
- **Authority**: ADMIN-only (existing `require_admin`; no new faculty role, no
  self-assignment). Endpoints:
  - `PUT /api/v1/laboratory/{code}/mid-sem` `{class_session_id}` — designates a
    real PRACTICAL session of that subject (400 for LECTURE/foreign-subject
    sessions, 404 for missing); replaces any prior designation (one per
    subject); the date comes from the real session — never computed.
  - `DELETE /api/v1/laboratory/{code}/mid-sem` — clears the designation.
  - `GET /api/v1/laboratory/{code}/mid-sem` — read (enrolled students).
- **Attendance is unaffected**: designation does not gate or alter counting —
  the normal `POST /api/v1/attendance` mutation records attendance against the
  designated session (verified 13e); clearing the designation never touches
  attendance records.
- **Read exposure**: `SubjectAttendanceSummary.mid_sem_session_id` /
  `mid_sem_session_date` (additive) — the lab card shows "Not scheduled" until
  an admin designates a real session.

### 4.3 What was deliberately NOT implemented

- No invented experiment titles, no seeded 1–10 experiment metadata, no fake
  mid-sem date (`laboratory_experiments`/`laboratory_records` stay empty).
- No `experiments >= 5 → midsem` rule (faculty controls scheduling; documented
  missing authority boundary — a faculty/full lab-management system is Phase 9
  product work).
- No "Lab Progress N/10" on the attendance page (no authoritative data).
- No changes to the frozen calendar/event architecture, quiz eligibility
  engine, or attendance engines (Phase 8.2 is additive + presentation).

---

## 5. API / schema changes

- `SubjectAttendanceSummary` (and `AnalyticsSubjectItem`): **additive**
  `health`, `mid_sem_session_id`, `mid_sem_session_date`. All pre-existing
  fields (incl. `status`, `required_pct`, optimization, forecasts) unchanged —
  backwards compatible; consumers audited (dashboard/analytics/quiz surfaces
  untouched; `status` still emitted for frozen consumers).
- Laboratory: `MidSemDesignationPayload` / `MidSemDesignationResponse` (new);
  three mid-sem endpoints added (one read + two admin mutations).

## 6. Migration / database changes

- One migration: `e5f6a7b8c9d0` — `class_sessions.designation` (nullable,
  enum `sessiondesignation`, `MID_SEM_PRACTICAL`). Applied (`alembic upgrade
  head`). **Zero data rows changed**: events=18 · sessions=691 (0 cancelled,
  0 extra) · records=92 · enrollments=18 · subjects=9 · quizzes=18 · users=30
  (1 ADMIN) · laboratory tables empty · designations=0 — exact baseline
  verified before/after every run.

---

## 7. Files changed

**Backend**
- `app/engines/attendance_engine.py` — `classify_attendance_health` + documented
  threshold constants (legacy `classify_attendance_status` untouched).
- `app/models/enums.py` — `SessionDesignation` enum.
- `app/models/timetable.py` — `ClassSession.designation` column.
- `app/schemas/attendance.py` — additive `health`, `mid_sem_session_id`,
  `mid_sem_session_date`.
- `app/services/attendance_service.py` — emits health + mid-sem fields.
- `app/repositories/attendance_repo.py` — `get_mid_sem_sessions` (batched).
- `app/services/laboratory_service.py` — **NEW**: mid-sem designation service.
- `app/api/v1/endpoints/laboratory.py` — GET/PUT/DELETE mid-sem endpoints.
- `app/schemas/laboratory.py` — mid-sem payload/response schemas.
- `alembic/versions/e5f6a7b8c9d0_add_session_designation.py` — **NEW** migration.
- `scripts/verify_phase_8_2.py` — **NEW** verifier (18 checks).
- `scripts/verify_phase_7_1.py` — check 23 **authorized fixed re-baseline
  89 → 92** (see "Baseline/fixture change" below). The assertion keeps a
  FIXED expected count (92); no dynamic baseline was introduced.

**Frontend**
- `src/types/api.ts` — additive `health`, `mid_sem_session_id`,
  `mid_sem_session_date`.
- `src/components/dashboard/SubjectAttendanceCard.tsx` — attendance-only
  redesign (health badge, overall %, Lecture/Tutorial blocks, lab practical +
  mid-sem row, formula caption, details without forecast/optimizer).
- `src/app/(authenticated)/subjects/page.tsx` — attendance-only copy.

**Docs**
- `docs/phase_8_2_implementation_report.md` (this file) · `MASTER_ROADMAP.md` ·
  `implementation_plan.md` · `task.md` · `walkthrough.md`.

---

## 8. Verification results

`python scripts/verify_phase_8_2.py` — **18/18 PASS**:

1. Summary totals == actual current-to-date session counts (per subject/type).
2. No fixed 14-lecture denominator (rollback-transaction inserted session
   changes the total — derived, not constant).
3. Quiz-window changes do NOT change Attendance page totals.
4. Tutorial formula: Overall = (Lecture % + Tutorial %) / 2 == engine.
5. Lecture-only fallback: Overall = Lecture %; no Tutorial 0/0.
6. Cancelled practical sessions excluded from the denominator (never
   Pending/Absent).
7. Practical attendance remains canonical class-session attendance.
8. Experiment completion NOT inferred from attendance; nothing auto-designates.
9. No fabricated experiment data (laboratory tables empty).
10. Quiz Eligibility results unchanged (labs 404, BCS-054 Q3 = 2026-10-23,
    current-cycle invariants, payload shape).
11. Phase 6 frozen behavior unchanged — exact baseline restored
    (events/sessions/cancelled/extra/records/enrollments/subjects/quizzes/
    scheduled/users/admins/lab tables/designations).
12. Attendance Health == engine classification; boundary values (75/65/60)
    verified.
13. Mid-sem designation is session-bound and admin-only (403 for students,
    400 for LECTURE/foreign sessions, replace/one-per-subject, real session
    date on the summary, normal attendance mutation against the designated
    session, clear restores null).

Frozen regressions (all re-run, all green): 6.5 **27/27** · 6.6 **36/36** ·
6.7 **31/31** · 7.1 **26/26** (qualified: after the authorized 89 → 92 fixed
fixture re-baseline — see below) · 7.2 **26/26** · 8.1 **22/22** ·
attendance-spec **15/15**. Static: `compileall` PASS · `npx tsc --noEmit`
PASS · ESLint clean · `next build` PASS (14 routes).

---

## 8b. Baseline/fixture change (authorized, Phase 8.2 final freeze)

- **Previous frozen baseline:** 89 attendance records.
- **Current authorized baseline:** 92 attendance records.
- The **+3 records are legitimate BCS-501 attendance marks** entered through
  the canonical student attendance mutation path (Track full-semester
  historical re-entry per Phase 4.5.2): 2026-08-04 LECTURE ATTENDED,
  2026-08-13 LECTURE MISSED, 2026-08-04 TUTORIAL ATTENDED (created
  2026-08-15 19:06–19:09 IST).
- They are **NOT verifier/test residue** — no verifier persists BCS-501
  records (7.1's BCS-501 scenarios run in rollback transactions; 8.2's
  mutation check is BCS-553 and self-cleaning).
- They were **already present before this audit** and are **never deleted**
  merely to satisfy the historical fixture.
- The frozen `verify_phase_7_1.py` check 23 was therefore **explicitly
  re-baselined from `records == 89` to `records == 92`** — a fixed expected
  value, authorized by the product owner. No dynamic baseline, no skipped or
  weakened assertion.
- This is an **authorized baseline/fixture change, NOT a product or
  attendance-engine change** — attendance formulas, engines, eligibility,
  analytics, counting, pending semantics, event semantics, and laboratory
  architecture are untouched.

---

## 9. Manual browser checks for the user

1. **Attendance page (`/subjects`)** — each theory card shows: code · THEORY
   badge · name · Attendance Health badge (Healthy/Watch/At Risk/Critical);
   large "Overall Attendance" %; Lecture + Tutorial blocks (attended/total +
   %); formula caption; expandable View Details with attended/missed/pending
   only. Confirm **no** must-attend / safe-skip / forecast / current-vs-
   forecast / "Required 75%" / "Defaulter" / quiz badge anywhere.
2. **BNC-501 (no tutorials)** — single Lecture block; caption "No tutorials —
   subject average equals Lecture %"; no Tutorial 0/0 block.
3. **Lab cards (BCS-551/552/553)** — "Practical Attendance" with
   attended/total (e.g. BCS-553 3/10), "Mid-Sem Practical: Not scheduled",
   no experiment progress (no fabricated data).
4. **Health colors** — e.g. BCS-501 (HEALTHY, green), BCS-054/BNC-501
   (CRITICAL, red). Watch/At Risk appear only when real data lands in the
   65–75 / 60–65 bands.
5. **Cards are compact** — less vertical scrolling than before; grid is
   1/2/3 columns on mobile/tablet/desktop.
6. **Quiz Eligibility page (`/tools/quiz-schedule`)** — unchanged; must-attend/
   safe-skip/forecast still present there.
7. **Admin mid-sem designation** — `PUT
   /api/v1/laboratory/BCS-553/mid-sem` with a real practical session id
   (admin token) → the lab card then shows the session date; DELETE restores
   "Not scheduled". A student token gets 403.
