# Phase 9.0 — Laboratory Domain Audit & Specification

> **Scope**: READ-ONLY audit + specification only. No code, schema, migration,
> seed, API, or UI was implemented. The database was only read (SELECT) plus
> the existing self-cleaning Phase 8.2 verifier, which restores the exact
> baseline. **Phase 9.1 has NOT started.**
> **Date**: 2026-08-15. **Status**: AUDIT COMPLETE — awaiting product decisions
> in §16 before any Phase 9.1 implementation.

Confidence labels used throughout: **PROVEN** (directly evidenced by code/docs/
DB), **INFERRED** (strongly implied but not directly stated), **UNKNOWN** (no
evidence), **AUTHORIZED** (explicit product/owner decision recorded in an
earlier phase or this document's §16).

---

## 1. Executive summary

The Laboratory domain today is a **clean but intentionally empty foundation**.
Three lab subjects (BCS-551, BCS-552, BCS-553) have real PRACTICAL
`class_sessions` whose attendance flows through the **same canonical
attendance pipeline** as lectures and tutorials (verified 18/18 by
`verify_phase_8_2.py`), and are correctly excluded from quiz eligibility.
The experiment subsystem (`laboratory_experiments` / `laboratory_records`)
exists in the schema with **zero rows** — the authoritative curriculum was
never available and was never fabricated. The mid-semester practical is
represented as an **ADMIN-designated session-level fact**
(`class_sessions.designation = MID_SEM_PRACTICAL`) tied to an actual scheduled
PRACTICAL session; it never gates or alters attendance counting.

The audit's central findings:

1. **Attendance for labs is already correct and complete.** No Phase 9 change
   to attendance rules, formulas, or the engine is required. Practical
   attendance = canonical `ClassSession(PRACTICAL)` + `AttendanceRecord`, the
   denominator excludes cancelled sessions, pending stays pending, and current
   percentages are recorded-only.
2. **Experiment progress and attendance are and must remain separate facts.**
   Nothing in the current pipeline infers experiments from sessions, and the
   Phase 9 implementation must preserve that separation.
3. **The single biggest gap is authoritative curriculum data** — experiment
   identity/titles/numbers per subject. It does not exist anywhere in the
   repository (only a legacy, non-authoritative `LAB_RULES.totalExperiments =
   10` in the retired vanilla-JS engine). No schema can be populated until the
   product supplies it.
4. **The second gap is an experiment↔session linkage** — `LaboratoryRecord`
   references a bare `date_conducted` with no `class_session_id`. Whether this
   is required depends on a product decision (§16-D).
5. **The third gap is authority.** Only `ADMIN` exists (Phase 6.5); there is no
   faculty role. Every faculty-like action (signature, mid-sem designation,
   curriculum assignment) currently lands on ADMIN, and mid-sem designation is
   the only one implemented. Whether a FACULTY role is introduced is a product
   decision (§16-B).

**Phase 9.0 conclusion**: the architecture is ready to build on, but the first
implementation step (9.1) must be an **additive read model + ingestion boundary**
that consumes canonical data and waits for authoritative curriculum — never a
guessed experiment catalog, never `experiments >= 5 ⇒ next practical is mid-sem`.

---

## 2. Current architecture

PROVEN from code + DB:

- **Stack**: FastAPI + async SQLAlchemy + PostgreSQL; Next.js frontend.
- **Layers**: `endpoints → services → repositories → models`, with pure
  **engines** (`attendance_engine.py`, `calendar_engine.py`,
  `eligibility_engine.py`) owning all mathematics. React renders backend
  values; it never computes attendance (Phase 8.0/8.1/8.2 contract).
- **Canonical session pipeline**: `seed_academic_baseline.py` seeds subjects,
  timetable entries, quiz cycles/policies/schedules from `timetable.json`;
  `expand_baseline.py` materializes `class_sessions` over the semester for
  teaching days; `event_session_service.py` (Phase 6.6) reconciles
  `class_sessions` to the calendar engine's effective schedule when events
  change. Every attendance consumer (Track, History, Dashboard, Analytics,
  Attendance summary, Quiz Eligibility) reads `class_sessions` +
  `attendance_records`.
- **Laboratory surface today**:
  - `LaboratoryExperiment` / `LaboratoryRecord` models + tables (initial
    schema, commit `69f69ce`), **empty**.
  - `GET /api/v1/laboratory/{code}/experiments` and `/records` (enrollment-
    scoped reads; return `[]`).
  - `GET/PUT/DELETE /api/v1/laboratory/{code}/mid-sem` (Phase 8.2): read for
    enrolled students; PUT/DELETE ADMIN-only, session-bound.
  - `SubjectAttendanceSummary` (and `AnalyticsSubjectItem`) carries additive
    `health`, `mid_sem_session_id`, `mid_sem_session_date`; lab cards on
    `/subjects` show **Practical Attendance** + a **Mid-Sem Practical** row.
- **The `/tools/laboratory` route is a naming artifact**: it renders the
  **Track Attendance** page (`TrackAttendancePage`), not a laboratory
  dashboard. The nav label "Track" maps there; there is no experiment UI
  anywhere in the frontend (hooks `useLabExperiments` / `useLabRecords`
  exist but are unused by any page).

DB state at audit time (baseline, unchanged by this audit):
events=18 · sessions=691 (0 cancelled, 0 extra) · records=92 · enrollments=18 ·
subjects=9 (6 theory, 3 lab) · quizzes=18 · users=30 (1 ADMIN) ·
`laboratory_experiments`=0 · `laboratory_records`=0 · designated sessions=0.

---

## 3. Current laboratory data model

PROVEN from `backend/app/models/laboratory.py`, the initial migration
`7117a007a0da`, and DB counts.

### `LaboratoryExperiment` (`laboratory_experiments`)
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `subject_id` | UUID FK → `subjects.id` | lab subject |
| `experiment_number` | int, NOT NULL | ordering only; **no authoritative catalog** |
| `title` | String, nullable | authoritative titles unavailable |

No `UniqueConstraint(subject_id, experiment_number)`; no description, no
session link, no status, no marks (marks belong to the record).

### `LaboratoryRecord` (`laboratory_records`)
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `user_id` | UUID FK → `users.id` | — |
| `experiment_id` | UUID FK → `laboratory_experiments.id` | — |
| `date_conducted` | Date, nullable | **bare date — no session FK** |
| `signature_status` | enum `pending`/`signed` | the only progress state |
| `signed_on` | DateTime, nullable | no signer identity |
| `marks` | Float, nullable | grading disabled in legacy; no UI ever existed |
| `remarks` | String, nullable | — |

`UniqueConstraint(user_id, experiment_id)` — one progress row per
student/experiment.

### `ClassSession` (shared with all classes)
`subject_id`, `date`, `class_type` (L/T/P), `is_extra`, `is_cancelled`,
`timetable_entry_id`, plus Phase 8.2 `designation`
(enum `sessiondesignation`, only value `MID_SEM_PRACTICAL`; nullable; default
NULL = regular session).

### Live lab data
- BCS-551 DBMS Lab: 2 timetable entries (Mon 13:00, 14:00, both `P`) → 48 P
  sessions (2026-07-20 … 2026-12-28).
- BCS-552 Web Technology Lab: 2 entries (Thu 14:00, 15:00) → 50 P sessions
  (2026-07-16 … 2026-12-31).
- BCS-553 DAA Lab: 2 entries (Fri 13:00, 14:00) → 48 P sessions
  (2026-07-17 … 2026-12-25).

Each lab day materializes **two separate PRACTICAL sessions** (the P1/P2 slots
kept distinct), unlike the legacy app, which merged them into a single `P`
occurrence (documented in `docs/phase_4_5_1B_lab_attendance_forensics.md` §2).

---

## 4. Source-of-truth chain

PROVEN from `attendance_repo.py`, `attendance_service.py`, `analytics_service.py`,
`dashboard_service.py`.

```
/tools/laboratory (Track)  ──► GET /api/v1/attendance/daily
/subjects (Attendance)     ──► GET /api/v1/analytics/overview
        └► AnalyticsService.get_overview ──► AttendanceService.get_subject_summaries
                └► AttendanceRepository.get_subject_counts_for_user(user_id, today)
                        └► class_sessions (subject_id, class_type, status LEFT JOIN
                            attendance_records, date <= today, is_cancelled = false)
```

- The **authoritative attendance source** for labs is the same table pair used
  for theory: `class_sessions` + `attendance_records`. Cancelled sessions are
  excluded in the repository WHERE clause (never Pending/Absent); a missing
  record row is Pending via the outer join.
- **Mid-sem state** is a `class_sessions.designation` fact read by
  `AttendanceRepository.get_mid_sem_sessions` (batched) and the lab endpoint;
  never derived from counts.
- **Experiment curriculum/progress** has no source of truth today — tables are
  empty by design (Phase 4.5.1-B: the legacy lab module never worked in
  production; Phase 8.2: nothing fabricated).
- **Events** (cancellation/extra/substitution) are the authoritative schedule
  mutations; the Phase 6.6 synchronizer reconciles `class_sessions` to the
  calendar engine's effective schedule.

---

## 5. Lab session vs experiment distinction

### 5.1 What each concept is (PROVEN)

| Concept | Representation today | Evidence |
|---|---|---|
| Timetable lab turn | 2 `TimetableEntry` rows (P slots) per week per lab subject | timetable.json `day_schedule`; `seed_academic_baseline.py` |
| Actual class session | `ClassSession(date, subject, PRACTICAL, is_extra, is_cancelled, designation)` | `expand_baseline.py` + event synchronizer |
| Attendance | `AttendanceRecord(user_id, class_session_id, status)` | `attendance.py` model |
| Experiment (curriculum) | `LaboratoryExperiment(subject, experiment_number, title?)` — **empty** | model + DB count 0 |
| Experiment progress | `LaboratoryRecord(user_id, experiment, date_conducted, signature_status, …)` — **empty** | model + DB count 0 |
| Mid-sem practical | `ClassSession.designation = MID_SEM_PRACTICAL` on a real P session | Phase 8.2 migration |

### 5.2 Conceptual relationship

```
Timetable lab turn ──► ClassSession(PRACTICAL) ──► AttendanceRecord     (attendance)
      │                        │
      │                        └──► designation = MID_SEM_PRACTICAL     (mid-sem)
      └──► (what happened in the turn: experiment?)  ── NOT LINKED       (gap §10)
```

Established by evidence:
- **One session can contain one experiment**: conceivable, but there is **no
  mechanism** to say which experiment a session hosted (`LaboratoryRecord`
  has a bare `date_conducted`, no `class_session_id`). → **NOT SUPPORTED**
  as a linkable fact.
- **One session can contain multiple experiments**: same gap → **NOT
  SUPPORTED**.
- **One session can contain no experiment** (e.g. lab conducted for a
  demonstration): representable (session exists, no record) but **indistinct**
  — the system cannot tell "no experiment was done" from "experiment data
  wasn't entered". → **PARTIALLY SUPPORTED**.
- **A lab turn can be converted to a lecture**: representable as two facts —
  a `CLASS_CANCELLED` event (cancels the P session) plus an `EXTRA_LECTURE`
  event or a substitution day (creates an L session). There is **no atomic
  "replace" semantic**. → **SUPPORTED (as composed facts)**.
- **A lab can be cancelled**: `CLASS_CANCELLED` event → synchronizer sets
  `is_cancelled = True`; excluded from the attendance denominator. →
  **SUPPORTED** (verified by Phase 8.2 check 6).
- **A lab can host the mid-sem practical**: `designation`. → **SUPPORTED**
  (Phase 8.2 checks 13a–13f).

### 5.3 Explicitly NOT established (do not assume)

- **UNKNOWN** — the actual number of experiments per subject (10 is a legacy
  `LAB_RULES` assumption in the retired vanilla-JS engine; **not** carried
  into the modern architecture and never authoritative).
- **UNKNOWN** — whether experiments map 1:1 to lab turns.
- **UNKNOWN** — experiment titles, numbering, or ordering for any subject.
- **AUTHORIZED** (Phase 8.2) — do **not** implement `experiments >= 5 ⇒ next
  practical is mid-sem`; do **not** fabricate curriculum.

---

## 6. Mid-semester practical analysis

### 6.1 What can be represented today (PROVEN)

- **A real, scheduled, practical session of the subject designated as its
  mid-semester practical.** `PUT /api/v1/laboratory/{code}/mid-sem` (ADMIN,
  `require_admin`) with a `class_session_id`; validated to belong to the
  subject and be `PRACTICAL` (400 otherwise, 404 if missing); replaces any
  prior designation (one per subject); `DELETE` clears; `GET` reads for
  enrolled students. The date shown is the real session's date — **never
  computed**.
- **Attendance for the mid-sem practical** is a normal
  `AttendanceRecord` against that session via the standard mutation; the
  designation does **not** gate, duplicate, or alter counting (verified
  Phase 8.2 check 13e).
- **Subject-specific timing / lab-slot dependency**: the designated session IS
  a real lab slot of the subject, so timing is inherently subject-specific and
  slot-bound. There is no global mid-sem date anywhere (no such concept).

### 6.2 What cannot be represented today

- **Experiment-progress dependency**: nothing ties mid-sem designation to
  experiment completion. This is **deliberate** (Phase 8.2 documented the
  missing faculty scheduling authority) — mid-sem is a faculty/admin decision,
  not a threshold. Whether a progress *check* (not auto-designation) is
  desired is product decision §16-E.
- **Faculty identity on the designation**: the `designation` column stores
  only the enum value; there is no `designated_by` / timestamp. The admin
  action is authenticated but not recorded as a who/when audit fact (the
  existing `academic_events` model likewise has no created-by). This is a
  cleanup/audit candidate, not a Phase 9.1 blocker.

### 6.3 Is the current `SessionDesignation` architecture sufficient as a foundation?

**YES — PROVEN.** It is session-bound (tied to an actual `ClassSession`),
enumerable, nullable (NULL = regular), additive, does not touch attendance
math, and is admin-gated. It can be extended with new enum values
(e.g. `FINAL_PRACTICAL`) without schema surgery, and it does not preclude a
future faculty role or a future experiment→designation linkage. The only
caveat: designation is a per-subject **flag on one session**, so anything more
than "the mid-sem session" (e.g. a mid-sem *record* with marks) would be a
separate, additive concept (§10).

---

## 7. Cancellation / substitution analysis

Traced through `event_service.py`, `event_session_service.py`,
`event_registry.py`, `calendar_engine.py` (PROVEN):

| Scenario | Mechanism today | Result | Supported? |
|---|---|---|---|
| 1. Lab cancelled | `CLASS_CANCELLED` event (subject, PRACTICAL, date) | synchronizer sets `is_cancelled=True` on the matching P session; excluded from all attendance denominators; never Pending/Absent | **YES** (Phase 8.2 check 6; Phase 6.6) |
| 2. Lab replaced with lecture | `CLASS_CANCELLED` (P) + `EXTRA_LECTURE` (L) event — or a substitution day (`substitution_schedule_override`) | P session cancelled; new `is_extra` L session created on the date | **YES, as two composed facts** (no atomic "replace") |
| 3. Replaced with another academic activity | same pattern (cancel + extra of the relevant class type) | same as above | **YES, as composed facts** |
| 4. Lab conducted, no experiment completed | nothing to do — session exists, attendance recorded, no `LaboratoryRecord` | correct attendance; **no signal** of "experiment skipped" | **PARTIALLY** (attendance correct; intent invisible) |
| 5. Extra lab conducted | `EXTRA_PRACTICAL` event | synchronizer creates exactly one `is_extra` PRACTICAL session | **YES** (Phase 6.7 check 17–18) |
| 6. Mid-sem instead of a normal experiment | designate the P session `MID_SEM_PRACTICAL` | same session, same attendance mutation | **YES for attendance**; experiment-progress linkage missing (§5.2/§10) |

Safety invariants (PROVEN):
- Sessions with attendance records are **never cancelled/deleted** by the
  synchronizer (`attended_ids` guard).
- Quiz-day materialized sessions (no `timetable_entry_id`) are never cancelled
  or deleted by event reconciliation.
- Cancellation is `is_cancelled = True`, never row deletion (ADR 004).
- Extra-session reconciliation is count-based on `(subject_id, class_type)`,
  deterministic, and idempotent.

**Where the current model is insufficient**: only the "what happened in a lab
turn" question — scenario 4/6 need an experiment↔session link to be visible,
and scenario 2/3 lack an atomic replacement semantic (acceptable; composed
facts are the established event model).

---

## 8. Attendance implications

Frozen rules (AUTHORIZED, all verified by Phase 8.2 checks 1–12 and the
attendance-spec verifier):

1. **Practical attendance contributes to subject attendance** — labs report
   `practical` counts + `current_practical_pct`; theory subjects expose
   practical in the summary too.
2. **Practical attendance contributes to overall attendance** — the ERP
   overall (`analytics` + `dashboard`) includes P sessions in Σ attended /
   Σ recorded (labs included; Phase 4.5.1-B: modern DB counts all sessions
   incl. lab).
3. **Practicals are excluded from quiz eligibility** — `quiz_applicable =
   false` for all three labs; `GET /quiz-eligibility/{lab}/…` → 404; the
   eligibility engine consumes only L/T (verified check 10).
4. **Cancelled sessions excluded** from the denominator (repository WHERE
   clause; verified check 6).
5. **Pending stays pending** — missing record = PENDING via LEFT JOIN; pending
   is never converted to absent (verified formula + check 1).
6. **Current is recorded-only** — `current_pct = att / (att + miss)`;
   forecast = pending-as-attended (unchanged, frozen).
7. **One attendance engine** — `compute_subject_stats` /
   `classify_attendance_status` / `classify_attendance_health` /
   `optimize_attendance` in `attendance_engine.py`; no second lab engine.
8. **Mid-sem designation does not alter attendance counting** (verified 13e).

**Does Phase 9 require any extension to these rules? NO.** The audit found no
product requirement that conflicts with any of them. Phase 9.1 should extend
only the **read model** (lab activity/summary surface), never the rules or the
engine.

---

## 9. Authorization model

Current (PROVEN): `UserRole.STUDENT | ADMIN` (Phase 6.5). `require_admin`
guards the mid-sem PUT/DELETE; students can create/update/deactivate
**flexible subject-scoped events** (`EXTRA_LECTURE/TUTORIAL/PRACTICAL`,
`CLASS_CANCELLED`, `SURPRISE_QUIZ`) for their **own enrolled subjects**
(Phase 8.2 student-event policy, `STUDENT_CREATABLE_EVENT_TYPES`). Global /
closure / quiz-schedule events are ADMIN-only.

Proposed authority matrix for the future lab system (product decision §16-B
resolves ADMIN vs FACULTY; **not implemented**):

| Action | Student | Admin/Faculty | Notes |
|---|---|---|---|
| View lab progress (own) | ✔ read | ✔ read | enrollment-scoped |
| Record own practical attendance | ✔ | ✔ | existing mutation; session-bound |
| Create EXTRA_PRACTICAL / CLASS_CANCELLED for own enrolled lab | ✔ | ✔ | existing Phase 8.2 policy |
| Assign experiment identity (curriculum) | ✘ | ✔ only | requires authoritative data |
| Mark experiment complete / sign | ✘ | ✔ (faculty semantics) | needs signer identity (gap) |
| Designate / change mid-sem | ✘ (403 today) | ✔ | existing |
| Cancel a lab / replace with lecture / add extra | ✔ (own enrolled) | ✔ | existing event model |
| Edit historical lab/attendance info | ✘ | ✔ | audit-trailed (future) |

**Hard boundary (AUTHORIZED, keep)**: students may **never** create or change a
mid-sem designation, and may never fabricate experiment state. Designation is
a faculty/admin scheduling fact.

---

## 10. Data-model gap analysis

### Capability classification (Section B of the brief)

| Capability | Status | Evidence / gap |
|---|---|---|
| Experiment identity | **PARTIALLY SUPPORTED** | `LaboratoryExperiment.id` exists; no authoritative catalog to populate it |
| Experiment number | **PARTIALLY SUPPORTED** | `experiment_number` int, ordered read; no authoritative numbering/expected count |
| Experiment title | **PARTIALLY SUPPORTED** | nullable `title`; authoritative titles missing |
| Experiment description | **NOT SUPPORTED** | no column |
| Experiment completion | **PARTIALLY SUPPORTED** | derivable (`signed` + attended) in legacy; modern model has no completion flag/date; `signature_status` only |
| Assignment submission | **NOT SUPPORTED** | no field |
| Experiment status | **PARTIALLY SUPPORTED** | `signature_status` (pending/signed) only |
| Experiment date | **SUPPORTED** | `LaboratoryRecord.date_conducted` |
| Marks | **SUPPORTED** | `LaboratoryRecord.marks` (nullable; grading never enabled) |
| Remarks | **SUPPORTED** | `LaboratoryRecord.remarks` |
| Faculty approval / signature | **PARTIALLY SUPPORTED** | `signature_status` + `signed_on`; **no signer identity** |
| Practical file / signature artifact | **PARTIALLY SUPPORTED** | status only; no artifact storage |
| Experiment ordering | **SUPPORTED** | `experiment_number` ordering in `laboratory_repo` |
| Experiment ↔ session link | **NOT SUPPORTED** | `date_conducted` is a bare date; no `class_session_id` FK |
| Per-subject expected experiment count | **UNKNOWN** | no authoritative source; legacy "10" is not authoritative |

### What Phase 9 genuinely requires vs. what to reuse (no models created here)

| Concept | Verdict | Basis |
|---|---|---|
| Practical attendance | **REUSE** `ClassSession` + `AttendanceRecord` | already canonical; nothing to add |
| Cancellation / substitution / extra lab | **REUSE** `AcademicEvent` + synchronizer | already canonical |
| Mid-sem designation | **REUSE** `ClassSession.designation` | already canonical (Phase 8.2) |
| Experiment curriculum identity | **NEW DATA (rows), not new tables** — populate `LaboratoryExperiment` only from authoritative input | tables exist and fit |
| Student experiment progress | **REUSE** `LaboratoryRecord` (additive `class_session_id` only if §16-D requires session traceability) | fits today's model |
| Faculty approval identity | **ADDITIVE** — `signed_by` (user FK) + designation audit (`designated_by`, timestamps) | only if §16-B/C decide |
| Lab activity history read model | **NEW READ MODEL (no tables)** — derived from `class_sessions` + events + records | service-layer aggregation |
| Experiment→mid-sem rule | **MUST NOT be modeled** | Phase 8.2 hard stop |

### What must NOT be modeled
Fabricated experiment titles/numbers, invented per-subject counts, guessed
dates, faculty decisions, marks, or curriculum — none of it. Tables stay empty
until an authoritative source exists (§16-A).

---

## 11. API contract proposal (future — NOT implemented)

Design principle: **every field has a backend source of truth; additive and
backwards-compatible; labs stay 404 on quiz surfaces.**

| Endpoint | Method | Authority | Source of truth | Status |
|---|---|---|---|---|
| `/api/v1/laboratory/{code}/summary` | GET | student (enrolled) | attendance engine + `designation` + (future) records | **proposed** |
| `/api/v1/laboratory/{code}/experiments` | GET | student (enrolled) | `laboratory_experiments` | exists (returns `[]`) |
| `/api/v1/laboratory/{code}/records` | GET | student (own) | `laboratory_records` | exists (returns `[]`) |
| `/api/v1/laboratory/{code}/activities` | GET | student (enrolled) | `class_sessions` + events + records | **proposed** (session-scoped history) |
| `/api/v1/laboratory/{code}/mid-sem` | GET/PUT/DELETE | read: student; mutate: admin/faculty | `class_sessions.designation` | exists (Phase 8.2) |
| `/api/v1/laboratory/{code}/experiments` | PUT/POST (curriculum) | admin/faculty | authoritative input only | **proposed, gated on §16-A** |
| `/api/v1/laboratory/{code}/records` | POST/PATCH (progress) | faculty (sign); student? (see §16-F) | `laboratory_records` | **proposed, gated on §16-B/F** |

Suggested payload shapes (sketches, not contracts):

- **LabSummary**: `{ subject, practical_attendance: { attended, total, pct, cancelled }, mid_sem: { session_id, date } | null, experiment_progress: { completed, total } | null /* null until authoritative */ }`.
- **LabActivityItem**: `{ session_id, date, class_type, is_extra, is_cancelled, designation, status, experiment: { id, number, title } | null /* null when unlinked */ }`.

---

## 12. Frontend information architecture proposal (future — NOT implemented)

Current truth: `/tools/laboratory` renders the Track page; no experiment UI
exists; `/subjects` lab cards show practical attendance + mid-sem only
(Phase 8.2, correct).

Proposed truthful hierarchy for a future dedicated Laboratory page (only
sections whose data source exists; experiment sections render **only when
authoritative data is present**, otherwise an honest empty state):

1. **Practical Attendance** — canonical attendance summary for the subject
   (attended/total, %, cancelled count). Source: attendance pipeline. Always
   shown.
2. **Mid-Sem Practical** — designation state (session date or "Not scheduled").
   Source: `class_sessions.designation`. Always shown.
3. **Lab Activity History** — session-scoped list (date, turn, extra/
   cancelled/substitution markers, mid-sem badge). Source: `class_sessions` +
   events. Always shown.
4. **Experiment Progress** — completed/total, per-experiment status, marks,
   remarks. **Shown only when authoritative curriculum + records exist**;
   otherwise "experiment curriculum not yet available" — never a guessed
   1–10 list.

Constraints (frozen): dark theme, minimalism, existing tokens/badges, compact
cards, no React attendance math, attendance page stays attendance-only, and
**"10 lab turns = 10 experiments" must never be implied**.

---

## 13. Engine impact analysis

**No engine changes required.**

- `attendance_engine.py` — already correct for labs (L/T/P buckets,
  health/status banding, optimizer). Unchanged.
- `eligibility_engine.py` — labs excluded by `quiz_applicable`; unchanged.
- `calendar_engine.py` — event/working-day semantics; unchanged.
- The Phase 9 additions are **additive read models (service layer) → API →
  React**, per the preferred chain: canonical engine → additive read model →
  API → React. No second lab attendance engine, no duplicate calculations, no
  experiment/session conflation.

---

## 14. Migration analysis (future — NOT executed)

Likely Phase 9.x migrations (all additive, backwards-compatible), **only after
the corresponding product decisions**:

1. **Optional**: `laboratory_records.class_session_id` (UUID FK, nullable) —
   experiment↔session linkage (§16-D). Index on `(class_session_id)`.
2. **Optional**: `laboratory_records.signed_by` (UUID FK → users, nullable)
   and/or `class_sessions.designated_by` + `designated_at` — audit identity
   (§16-C).
3. **Optional**: `user_role` new value `FACULTY` (§16-B).
4. **No migration** is required for curriculum ingestion — `laboratory_experiments`
   / `laboratory_records` already exist. Possibly add
   `UniqueConstraint(subject_id, experiment_number)` for catalog integrity
   when the catalog becomes authoritative.
5. **Never** seeded: fabricated experiment rows, dates, marks, decisions.

Baseline safety: any future verifier pattern follows `verify_phase_8_2.py`
(exact-baseline restore, rollback transactions). This audit made **no schema
change**; the DB is byte-equivalent to the frozen baseline (§21).

---

## 15. Data fabrication risks

| Risk | Guard (AUTHORIZED / this audit) |
|---|---|
| Invented experiment titles/numbers | Tables stay empty until authoritative input (§16-A); verifier check 9 asserts 0 rows |
| "10 experiments" assumption | Legacy `LAB_RULES.totalExperiments = 10` is **not** authoritative for the modern architecture; a catalog source is required |
| `experiments >= 5 ⇒ mid-sem` | Hard-forbidden (Phase 8.2); designation is faculty/admin-only |
| Fake mid-sem date | Designation reads the real session date; no computed date anywhere |
| Lab sessions counted as experiments | Attendance never derives from experiment counts (Phase 8.2 check 8); experiment progress never derived from attendance |
| Marks/grades fabricated | `marks` nullable; no UI/API writes exist; grading stays disabled |
| Session counts inflated by cancellations | Cancelled excluded at the repository layer (check 6) |

---

## 16. Explicit product decisions required

Phase 9.1 is blocked on these (this audit does **not** decide them):

- **A. Curriculum source.** Who supplies authoritative experiment titles/
  numbers/expected-count per lab subject (department syllabus)? Until then,
  `laboratory_experiments` stays empty and the UI shows an honest empty state.
- **B. Faculty authority.** Introduce a `FACULTY` role (new enum value +
  migration), or keep ADMIN-only for all lab mutations? The current design
  has no faculty role; ADMIN is the only elevated role.
- **C. Audit identity.** Record `designated_by`/`signed_by` (who/when) on
  designations and signatures — or accept that the current model records the
  action but not the actor?
- **D. Experiment↔session linkage.** Is per-experiment session traceability
  (which lab turn hosted which experiment) required — i.e. add
  `laboratory_records.class_session_id`? (Affects mid-sem host evidence and
  activity history.)
- **E. Mid-sem eligibility check.** Should designation be **checked** (not
  auto-applied) against experiment progress — e.g. warn when <5 experiments —
  or remain a free faculty/admin choice? The current model is free choice.
- **F. Student mutation boundary for experiment progress.** May students
  record experiment completion, or is completion faculty-only (signature
  semantics)? The Phase 8.2 precedent (students adjust "what actually
  happened" events) suggests attendance = student; signature/completion =
  faculty.
- **G. Grading/viva.** Enable marks (and viva) per experiment — or keep
  grading off? Legacy `LAB_RULES.default.grading.enabled = false`.

---

## 17. Proposed Phase 9 implementation breakdown

**Phase 9.1 (smallest safe increment — after §16 decisions):**

1. **Lab read model** (service + endpoint): `GET /laboratory/{code}/summary`
   and `/activities` — pure aggregation of canonical `class_sessions` +
   events + `designation` + (when present) `laboratory_records`. No new math,
   no new tables.
2. **Curriculum ingestion boundary** (only if §16-A resolved): an admin/
   faculty endpoint that populates `laboratory_experiments` from an
   authoritative payload; rejects duplicate/out-of-range numbers; never
   guesses.
3. **Experiment progress surface** (only if §16-B/F resolved): sign/complete
   flow on `laboratory_records` with the chosen authority and audit fields.
4. **Frontend**: dedicated Laboratory page IA per §12; keep `/subjects`
   attendance cards as-is.
5. **Verification**: new read-only verifier (attendance-derived totals, no
   fabricated data, designation unchanged, eligibility unchanged, exact
   baseline) + frozen regressions.

**Phase 9.2+ (deferred, conditional)**: grading/viva, faculty approval
workflow, advanced analytics. **Do NOT start any of this in 9.1.**

---

## 18. Verification strategy (Phase 9.x)

Extend the established read-only pattern (`verify_phase_8_2.py`):

- summary totals == direct counts of non-cancelled `class_sessions` through
  today (per subject/type);
- no fixed denominator, no quiz-window coupling;
- cancelled practicals excluded; pending stays pending; current recorded-only;
- experiment progress **never** inferred from attendance; attendance **never**
  derived from experiments;
- no fabricated experiment data (0 rows unless an authorized ingest ran, then
  only the exact ingested rows);
- mid-sem designation remains session-bound, admin/faculty-gated, replaceable,
  clearable, and attendance-neutral;
- quiz eligibility results and Phase 6 frozen behavior byte-identical;
- exact baseline restored after every run (rollback transactions + cleanup).

---

## 19. Frozen boundaries (must never be violated by Phase 9)

- Phase 6 calendar/event architecture (working-day semantics, synchronizer,
  quiz-day session protection).
- Phase 7 quiz eligibility engine and semantics; no cycle hardcoding; labs
  stay 404.
- Phase 8.0/8.1 analytics formulas, `status` banding, weekly model.
- Phase 8.2: Attendance Health thresholds; the `/subjects` attendance-only
  surface; the session-bound mid-sem designation; the student event policy.
- Attendance formulas, pending semantics, forecast semantics, and the single
  canonical engine — unchanged.
- No business calculations in React; no second attendance engine; no
  experiment/session conflation.

---

## 20. Known limitations

1. **No authoritative curriculum** — the single largest blocker; nothing can
   populate `laboratory_experiments` until the product supplies it.
2. **No faculty role** — all elevated actions are ADMIN-only; a real faculty
   workflow is a product decision.
3. **No experiment↔session linkage** — `date_conducted` is a bare date;
   "which session hosted which experiment" is not representable.
4. **No audit identity** on designation/signature (no who/when).
5. **Marks/viva never implemented** (legacy grading disabled; no UI).
6. **`/tools/laboratory` naming artifact** — the route hosts the Track page;
   a dedicated lab page does not exist yet.
7. **Frontend type drift (cleanup candidate, untouched by this audit)** —
   `frontend/src/types/api.ts` declares `SubjectCategory` with legacy values
   (CORE/ELECTIVE/LAB/MANDATORY) that do not match the backend's
   `theory`/`lab`; the enum is **unused** by any component (the card detects
   labs via `!quiz_applicable`). Reported here rather than deleted, per the
   audit brief; safe to clean in a future phase.
8. **Legacy "10 experiments" is informational only** — it lives in
   `docs/08_LABORATORY_ENGINE.md` / `LAB_RULES` of the retired vanilla-JS
   engine and must not be treated as the modern contract.

---

## 21. Audit verification + mutation status

- **Read-only inspection** of every backend/frontend file listed in the brief
  (models, schemas, services, repositories, endpoints, engines, migrations,
  seed/verifier scripts, frontend pages/components/hooks/types) plus
  `timetable.json`, git history, and the tracking docs.
- **DB**: only SELECT queries + the existing self-cleaning
  `verify_phase_8_2.py` (18/18 PASS; check 11 asserts exact baseline restore).
- **Final counts (identical to baseline)**: events=18 · sessions=691 (0
  cancelled, 0 extra) · records=92 · enrollments=18 · subjects=9 · quizzes=18 ·
  users=30 (1 ADMIN) · `laboratory_experiments`=0 · `laboratory_records`=0 ·
  designations=0.
- **No files changed by this audit.** `git status` shows only the pre-existing
  Phase 8.2 freeze work (verifier re-baseline + docs, uncommitted by owner
  instruction) and the `.freebuff/*` environment files.
- **No migration, no seed change, no commit.**

**HARD STOP — Phase 9.0 audit complete. Phase 9.1 not started.**
