# Phase 9.2.0 — Laboratory Experiment Management
## Read-Only Audit + Implementation Specification

> **Scope**: READ-ONLY AUDIT + SPECIFICATION ONLY.
> No code, schema, migration, seed, API, UI, or data mutation was performed.
> The database was accessed SELECT-only.
> **Date**: 2026-08-15. **Status**: AUDIT COMPLETE.
> Phase 9.1 is complete and frozen (28/28). Phase 9.2 implementation NOT started.

---

## 1. Executive Summary

Phase 9.1 delivered Mid-Sem Practical and Lab Cancelled as first-class Academic Events fully integrated with the canonical `ClassSession → AttendanceRecord` pipeline. Attendance for lab subjects is now architecturally correct and verified (28/28).

**What Phase 9.2 concerns**: the experiment curriculum + student experiment-progress tracking layer that sits *above and alongside* the attendance pipeline — never replacing or duplicating it.

This audit establishes:

1. **The attendance pipeline is the permanent source of truth for lab attendance.** Phase 9.2 adds nothing to it.
2. **The `laboratory_experiments` and `laboratory_records` tables exist but are empty.** No authoritative curriculum exists anywhere in the repository.
3. **`laboratory_records` has no `class_session_id` FK.** Decision 4 (nullable FK) remains a confirmed schema requirement.
4. **The `LaboratoryRecord` model lacks audit identity columns.** Decision 3 (timestamps + signed_by) has not been implemented yet.
5. **`LaboratoryExperiment` has no `UniqueConstraint(subject_id, experiment_number)`.** Intentionally deferred until catalog is authoritative.
6. **The `/tools/laboratory` route currently renders the Track Attendance page**, not a laboratory dashboard. Phase 9.2 must introduce a dedicated `/laboratory` route.
7. **Curriculum blocker**: no authoritative experiment catalog exists. The system must show an honest "curriculum not yet available" state.

---

## 2. Current Laboratory Architecture (PROVEN)

**Canonical attendance chain** (frozen, Phase 9.2 does not change this):

```
AcademicEvent → EventSessionSynchronizer → ClassSession → AttendanceRecord
    → AttendanceEngine / AnalyticsEngine / EligibilityEngine
    → Track / History / Dashboard / Subjects / Analytics / Quiz Eligibility
```

**Laboratory domain today**:

| Layer | What exists |
|---|---|
| `ClassSession(PRACTICAL)` | 146 sessions across 3 lab subjects (48+50+48) |
| `ClassSession.designation` | Nullable `MID_SEM_PRACTICAL` enum; Phase 8.2 |
| `AcademicEvent` (MID_SEM_PRACTICAL / LAB_CANCELLED) | Phase 9.1 event types; student-creatable |
| `LaboratoryExperiment` | Schema exists; **0 rows** |
| `LaboratoryRecord` | Schema exists; **0 rows** |
| Lab API | GET /experiments, GET /records, GET/PUT/DELETE /mid-sem |
| Frontend lab hooks | `useLabExperiments`, `useLabRecords` — defined but unused |
| Frontend lab page | `/tools/laboratory` renders **Track Attendance**, not a lab dashboard |

---

## 3. Existing Database Schema

### `laboratory_experiments` — 0 rows

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `subject_id` | UUID FK → `subjects.id` | NOT NULL |
| `experiment_number` | int | NOT NULL; no UniqueConstraint(subject_id, number) yet |
| `title` | String | nullable; authoritative titles unavailable |

**Missing**: description, is_active/active flag, provenance fields, UniqueConstraint.

### `laboratory_records` — 0 rows

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `user_id` | UUID FK → `users.id` | NOT NULL |
| `experiment_id` | UUID FK → `laboratory_experiments.id` | NOT NULL |
| `date_conducted` | Date | nullable; **bare date, no session FK** |
| `signature_status` | enum `pending`/`signed` | NOT NULL, default pending |
| `signed_on` | DateTime(tz) | nullable; no signer identity |
| `marks` | Float | nullable; dormant (Decision 7) |
| `remarks` | String | nullable |
| `UniqueConstraint(user_id, experiment_id)` | — | One record per student/experiment |

**Missing**: class_session_id FK (Decision 4), signed_by, created_by, updated_by, created_at, updated_at.

---

## 4. Existing Laboratory Data (SELECT-Only Audit)

**DB baseline at audit start — 2026-08-15**:

| Table | Count |
|---|---|
| `academic_events` | **22** (18 QUIZ_DAY + 3 EXTRA_LECTURE + 1 MID_SEM_PRACTICAL) |
| `class_sessions` | **691** (0 cancelled, 0 extra, 0 designated) |
| `attendance_records` | **95** |
| `student_enrollments` | **18** |
| `subjects` | **9** |
| `quiz_schedules` | **18** |
| `users` | **30** (29 STUDENT, 1 ADMIN) |
| `laboratory_experiments` | **0** |
| `laboratory_records` | **0** |

**Lab subjects and practical sessions**:

| Code | Name | PRACTICAL sessions | Cancelled | Extra | Designated |
|---|---|---|---|---|---|
| BCS-551 | Database Management System Lab | 48 | 0 | 0 | 0 |
| BCS-552 | Web Technology Lab | 50 | 0 | 0 | 0 |
| BCS-553 | Design & Analysis of Algorithm Lab | 48 | 0 | 0 | 0 |

Each lab day materializes **two separate PRACTICAL sessions** (P1 + P2 slots kept distinct per timetable). Every lab subject has `quiz_applicable = False` (excluded from eligibility; labs return 404 on the quiz eligibility endpoint).

---

## 5. Curriculum-Source Finding

**PROVEN**: No authoritative experiment catalog exists anywhere in the repository.

| Location | Finding |
|---|---|
| `laboratory_experiments` table | 0 rows |
| `backend/scripts/` | No lab curriculum seeder |
| `timetable.json` | No experiment data |
| Phase 4.5 forensic docs | Legacy `LAB_RULES.totalExperiments = 10` — NOT authoritative; retired vanilla-JS only |
| `phase_9_0_laboratory_domain_audit.md` | Explicitly states 0 rows; "10" was non-authoritative |
| `phase_9_product_decisions.md` | Decision 1: no catalog seeded until authoritative source supplied |

> [!CAUTION]
> Any implementation that invents experiments (e.g., "Experiment 1 of 10") without a verified institutional source violates the explicit Phase 8.2/9.0 architecture decision. The "10 experiments" concept is permanently rejected as a default.

---

## 6. Experiment Lifecycle

**States** (AUTHORIZED, Decision 6):

| Status | Writable by | Meaning |
|---|---|---|
| `PENDING` (default) | Student (own record) | Self-tracked / unconfirmed |
| `SIGNED` | ADMIN only (FACULTY deferred) | Official; records `signed_by` + `signed_on` |

**Lifecycle**:
```
[no rows] → Admin ingests catalog → LaboratoryExperiment rows exist
                                           ↓
                    Student creates self-tracked row → LaboratoryRecord(status=PENDING)
                                           ↓
                    Admin marks official completion → LaboratoryRecord(status=SIGNED)
```

**Why no IN_PROGRESS status**: the system already disambiguates "no record" (not started) vs "PENDING" (self-tracked) vs "SIGNED" (official). Three entities is sufficient.

**Experiment status is NOT an attendance state.** It never enters the `AttendanceRecord` pipeline.

---

## 7. Session ↔ Experiment Relationship

**Current gap**: `date_conducted` is a bare date. A lab day has two P slots — the date cannot identify which session hosted the experiment.

**Decided architecture** (Decision 4, AUTHORIZED):
```
LaboratoryRecord.class_session_id → nullable FK → class_sessions.id
```

**Validation on write**:
1. Referenced session must belong to the experiment's subject
2. `class_type` must be `PRACTICAL` (mid-sem designated sessions qualify)
3. `is_cancelled = False` — a cancelled session hosted nothing
4. Session must exist and student must be enrolled in subject

**Cardinalities**:
- Multiple experiments per session: **ALLOWED** (no unique constraint on `class_session_id`)
- One record per student/experiment: **ENFORCED** (existing `UniqueConstraint(user_id, experiment_id)`)
- Sessions without experiments: **ALLOWED** (session exists, no records referencing it)
- Experiments without sessions: **ALLOWED** (`class_session_id` is nullable)
- Multi-session experiments: **DEFERRED** (primary hosting session is the link; junction table deferred)
- Mid-sem practical sessions: **ALLOWED** as target (they are real PRACTICAL sessions)
- Cancelled sessions: **REJECTED at write time**

---

## 8. Student Tracking Model (AUTHORIZED, Decision 6)

| Action | Actor | Backend enforcement |
|---|---|---|
| View curriculum | Student (enrolled) | Enrollment guard |
| View own progress | Student (own user_id) | Enrollment + user_id match |
| Create self-tracked row | Student (own) | `status` forced to `PENDING`; SIGNED not allowed |
| Edit own PENDING record | Student (own) | Same enrollment + user_id + status=PENDING |
| Delete own PENDING record | Student (own) | Same checks |
| Mark SIGNED | ADMIN only | `require_admin` |
| Edit SIGNED record | ADMIN only | `require_admin` |

---

## 9. Official Verification Model

**SIGNED state** requires elevated actor (ADMIN for Phase 9.2; FACULTY deferred).

**What SIGNED captures** (Decision 3, AUTHORIZED):
- `signature_status = SIGNED` (existing column, reused)
- `signed_by` — UUID FK to `users.id` (new column)
- `signed_on` — existing `DateTime(timezone=True)` column, reused

**Admin signing flow**: `PATCH /api/v1/laboratory/{code}/records/{record_id}` with `{"signature_status": "signed"}`. Backend sets `signed_by = current_user.id`, `signed_on = now()`. Student cannot set SIGNED regardless of request body.

---

## 10. Mid-Sem Practical Relationship (FROZEN, Phase 8.2 + 9.1)

**Architecture** (frozen):
```
AcademicEvent(MID_SEM_PRACTICAL) → EventSessionSynchronizer
    → ClassSession.designation = MID_SEM_PRACTICAL (one session per subject)
    → AttendanceRecord → canonical attendance pipeline
```

This is attendance context, not experiment context. The mid-sem practical session IS a ClassSession. Attendance against it is a normal AttendanceRecord.

**Advisory mid-sem readiness** (Decision 5, AUTHORIZED):
When catalog exists → read-only `"X of Y experiments officially completed"`.
- Hidden when Y = 0 (no catalog)
- **Never a gate** on designation
- **Never automatic** — designation stays a human act
- **Never 5-experiment-threshold** — permanently rejected

---

## 11. Lab Cancellation Relationship (FROZEN, Phase 9.1)

`LAB_CANCELLED` → `is_cancelled = True` on the matching PRACTICAL session.

**Impact on experiments**:
- `class_session_id` FK validation **rejects cancelled sessions at write time** — a cancelled session cannot be the host of a new experiment record
- Experiment progress does NOT increment due to a cancelled session
- If a session is cancelled *after* a lab record links to it, the record is NOT automatically deleted (same safety invariant as attendance records)
- Cancelling a session never implies experiment completion

---

## 12. Progress Semantics

**When catalog exists**:
```
signed_count       = COUNT(records WHERE user_id=X AND subject_id=Y AND signature_status='signed')
total_count        = COUNT(experiments WHERE subject_id=Y AND is_active=True)
self_tracked_count = COUNT(records WHERE user_id=X AND subject_id=Y AND signature_status='pending')
```

**When no catalog exists**: honest empty state — no "0/10", no fabricated N.

**Cancelled sessions have no effect on progress.** Progress is experiment-indexed, not session-indexed.

---

## 13. Proposed Data Model

### 13.1 Additive changes to `laboratory_experiments`

| Column | Type | Nullable | Rationale |
|---|---|---|---|
| `description` | String | YES | Optional per-experiment note |
| `is_active` | Boolean | NO, default True | Allows corrections without deleting rows |
| `UniqueConstraint(subject_id, experiment_number)` | — | — | Deferred until catalog is authoritative |

**Migration impact**: additive; 0 rows → no backfill. Rollback: DROP COLUMN × 2 + DROP CONSTRAINT.

### 13.2 Required changes to `laboratory_records`

| Column | Type | Nullable | Decision |
|---|---|---|---|
| `class_session_id` | UUID FK → `class_sessions.id` | YES | D4 |
| `signed_by` | UUID FK → `users.id` | YES | D3 |
| `created_by` | UUID FK → `users.id` | YES | D3 |
| `updated_by` | UUID FK → `users.id` | YES | D3 |
| `created_at` | DateTime(tz) | NO, default now() | D3 |
| `updated_at` | DateTime(tz) | NO, default now() | D3 |

**Migration impact**: 6 additive nullable/default columns; 0 rows → no backfill. Rollback: DROP COLUMN × 6.

### 13.3 Changes to `class_sessions` — NONE

The `designation` column (Phase 8.2) is already sufficient. No Phase 9.2 schema change to ClassSession.

---

## 14. Proposed API

All endpoints enforce enrollment scope. None are implemented in Phase 9.2.0.

### Read endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `GET /api/v1/laboratory/{code}/summary` | Student (enrolled) | Practical attendance + mid-sem + experiment advisory |
| `GET /api/v1/laboratory/{code}/experiments` | Student (enrolled) | Curriculum (empty array when no catalog) |
| `GET /api/v1/laboratory/{code}/records` | Student (enrolled) | Own progress records |
| `GET /api/v1/laboratory/{code}/activity` | Student (enrolled) | Session-scoped history (sessions + events + records) |

**Proposed `GET .../summary` response shape**:
```json
{
  "subject_code": "BCS-551",
  "practical_attendance": {
    "attended": 6, "missed": 2, "pending": 40, "total": 48,
    "current_practical_pct": 75.0
  },
  "mid_sem": {
    "designated": true, "session_id": "...", "session_date": "2026-10-15",
    "attendance_status": "Attended"
  },
  "experiment_progress": {
    "catalog_available": false, "total": 0,
    "signed": 0, "pending_self_tracked": 0, "advisory": null
  }
}
```

### Write endpoints (student)

| Endpoint | Auth | Description |
|---|---|---|
| `POST /api/v1/laboratory/{code}/records` | Student (enrolled) | Create self-tracked row; status forced to PENDING |
| `PATCH /api/v1/laboratory/{code}/records/{record_id}` | Student (own PENDING) | Edit date_conducted, remarks |
| `DELETE /api/v1/laboratory/{code}/records/{record_id}` | Student (own PENDING) | Delete own PENDING row |

### Write endpoints (admin)

| Endpoint | Auth | Description |
|---|---|---|
| `PATCH /api/v1/laboratory/{code}/records/{record_id}` | ADMIN | Set SIGNED; records signed_by + signed_on |
| `POST /api/v1/laboratory/{code}/experiments` | ADMIN | Ingest one experiment (provenance-bound) |
| `PATCH /api/v1/laboratory/{code}/experiments/{exp_id}` | ADMIN | Correct title/description |
| `DELETE /api/v1/laboratory/{code}/experiments/{exp_id}` | ADMIN | Deactivate experiment (is_active=False) |

### Existing endpoints (Phase 8.2, UNCHANGED)

`GET/PUT/DELETE /api/v1/laboratory/{code}/mid-sem` — admin-only PUT/DELETE, student-read GET.

---

## 15. Proposed UI / Information Architecture

**Current state**: `/tools/laboratory` renders Track Attendance — no lab dashboard exists.

**Phase 9.2 target IA** (minimal, consistent with design system):

```
/laboratory
├── Practical Attendance (default tab)
│     └── Practical attendance summary (canonical SubjectAttendanceSummary)
│           + Mid-Sem Practical status card
├── Experiments
│     └── When catalog_available=false: honest empty state
│           "Experiment curriculum not yet available"
│     └── When catalog available: ordered list with PENDING/SIGNED indicators
│           + self-track toggle button
└── Activity
      └── Chronological list of lab sessions (date, class_type, attendance state,
            experiment linked if any, designation badge if MID_SEM_PRACTICAL)
```

**Design constraints**:
- Dark minimal interface (design system tokens: #0a0a0a background, #171717 cards, #3B82F6 accent)
- Compact cards — no attendance duplication
- Backend-owned attendance math — frontend renders, never computes
- "Experiments" tab: honest empty state when `catalog_available = false`
- No "10 experiments" placeholder, no "0/10" with fabricated N

---

## 16. Authorization Matrix

| Action | Student (enrolled) | Student (not enrolled) | ADMIN |
|---|---|---|---|
| View curriculum | ✅ | ❌ 404 | ✅ |
| View own progress | ✅ | ❌ 404 | ✅ |
| Create PENDING record | ✅ | ❌ 403 | ✅ |
| Edit own PENDING record | ✅ | ❌ 403 | ✅ |
| Delete own PENDING record | ✅ | ❌ 403 | ✅ |
| Set SIGNED | ❌ 403 | ❌ 403 | ✅ |
| Edit SIGNED record | ❌ 403 | ❌ 403 | ✅ |
| Ingest / correct / deactivate experiments | ❌ 403 | ❌ 403 | ✅ |
| Designate mid-sem session | ❌ 403 | ❌ 403 | ✅ |
| Mark attendance (canonical mutation) | ✅ | ❌ | ✅ |

**FACULTY role**: deferred. Model designed as capability matrix — FACULTY can be added additively later.

---

## 17. Migration Requirements

### Migration A — Extend `laboratory_experiments`
```sql
ALTER TABLE laboratory_experiments
    ADD COLUMN description VARCHAR,
    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE laboratory_experiments
    ADD CONSTRAINT uq_subject_experiment UNIQUE (subject_id, experiment_number);
```
Additive. 0 rows. Rollback: DROP COLUMN × 2 + DROP CONSTRAINT.

### Migration B — Extend `laboratory_records`
```sql
ALTER TABLE laboratory_records
    ADD COLUMN class_session_id UUID REFERENCES class_sessions(id),
    ADD COLUMN signed_by UUID REFERENCES users(id),
    ADD COLUMN created_by UUID REFERENCES users(id),
    ADD COLUMN updated_by UUID REFERENCES users(id),
    ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
```
Additive. 0 rows. Rollback: DROP COLUMN × 6.

Both migrations: zero existing-data impact, fully reversible, Phase 9.2.1 deliverables.

---

## 18. Verification Strategy (`verify_phase_9_2.py`)

To be created in Phase 9.2.1 — not now. Required 20 checks:

1. Baseline snapshot recorded
2. Admin ingests experiment → row created
3. Duplicate `(subject_id, experiment_number)` → rejected
4. Student cannot ingest experiments (403)
5. Student creates PENDING record for enrolled subject
6. PENDING record class_session_id = valid PRACTICAL session of that subject
7. PENDING record cannot reference cancelled session
8. Student cannot set SIGNED (403/422)
9. Admin sets SIGNED → signed_by + signed_on populated
10. `UniqueConstraint(user_id, experiment_id)` enforced
11. Enrollment guard: unenrolled → 403/404
12. Advisory shows X/Y when catalog exists; null when no catalog
13. Advisory does NOT gate mid-sem designation
14. Cancelled session attendance is NOT in lab records
15. `laboratory_experiments` = 0 when no ingestion
16. Practical attendance formulas unchanged after adding records
17. Quiz eligibility unchanged (labs still 404)
18. No fabricated experiment data
19. Baseline restored exactly
20. Frozen regressions: 6.5/6.6/6.7/7.1/7.2/8.1/8.2/9.1 all PASS

---

## 19. Explicitly Rejected Approaches

| Approach | Rejection reason |
|---|---|
| Hardcode "10 experiments" per subject | Legacy-only, non-authoritative |
| Seed experiments without authoritative catalog | Seed becomes fabricator |
| Auto-designate mid-sem when N experiments signed | Frozen hard stop (Phase 8.2 + Decision 5-B) |
| Hard eligibility gate on mid-sem | Requires universal count; violates product rules |
| Non-nullable class_session_id FK | Impossible for unlinked/historical records |
| IN_PROGRESS experiment status | No product benefit; three-state model is sufficient |
| Marks/viva/grading in Phase 9.2 | Decision 7 deferred |
| FACULTY role in Phase 9.2 | No defined workflow; Decision 2 deferred |
| Second lab attendance engine | Permanently rejected |
| React-side attendance math | Permanently rejected |
| "Experiment 1 = Lab Turn 1" assumption | Not supported |
| Automatic experiment completion on attendance | Attendance and experiments are independent facts |

---

## 20. Unknowns Requiring Real-World Input

1. **Authoritative curriculum source** — syllabus, LMS export, faculty CSV?
2. **Per-subject experiment counts** — BCS-551/552/553 may differ
3. **Mid-sem readiness threshold** — any institutional required N-of-Y?
4. **Does mid-sem practical host its own experiment?** — affects advisory counting
5. **Student self-tracking vs faculty-only entry**
6. **Institutional experiment-to-session mapping** — by order/date only, or formally mapped?
7. **Viva/grading policy** — if ever, who grades, rubric?
8. **Multi-faculty administration** per subject?
9. **Designation audit history** — current fact vs who/when log?
10. **Curriculum revision mid-semester** — correction protocol?

---

## 21. Phase 9.2.1 Implementation Scope

**Prerequisites** (all resolved):

| Prerequisite | Status |
|---|---|
| Phase 9.1 verified (28/28) | ✅ |
| DB baseline documented | ✅ This audit |
| Migrations A + B designed | ✅ |
| Authorization matrix | ✅ Decision 6 |
| Mid-sem advisory-only | ✅ Decision 5 |
| No FACULTY role | ✅ Decision 2 |
| No grading/marks | ✅ Decision 7 |
| UI/IA structure | ✅ §15 above |

**Phase 9.2.1 ordered deliverables**:

1. Migration A: extend `laboratory_experiments`
2. Migration B: extend `laboratory_records` (session FK + audit columns)
3. Updated `LaboratoryExperiment` + `LaboratoryRecord` SQLAlchemy models
4. `LaboratoryRepository` — add `create_experiment`, `create_record`, `update_record`, `sign_record`
5. `LaboratoryService` — student self-tracking + admin signing + catalog ingestion
6. `GET /laboratory/{code}/summary` endpoint
7. Write endpoints: records (POST/PATCH/DELETE) + experiments admin (POST/PATCH/DELETE)
8. Frontend: `/laboratory` dedicated page (3 tabs: Practical Attendance / Experiments / Activity)
9. Frontend: `LaboratoryExperimentResponse` + `LaboratoryRecordResponse` updated API types
10. Frontend: `useLabSummary` + `useLabActivity` hooks
11. Frontend: `ExperimentCard` component (PENDING / SIGNED states + honest empty state)
12. `verify_phase_9_2.py` (20-point checklist)
13. `docs/phase_9_2_1_implementation_report.md`

**Phase 9.2.1 must NOT deliver**:
- FACULTY role
- Marks/viva/grading
- Fabricated experiment data
- Auto-designation
- Experiment-count gate on anything
- Attendance engine changes

---

## 22. Hard Stop

**Phase 9.2.0 ends here.** No code, schema, migration, seed, API, UI, or data was changed.

**DB baseline — before and after audit (byte-equivalent)**:

| Table | Before | After |
|---|---|---|
| `academic_events` | 22 | 22 ✅ |
| `class_sessions` | 691 (0 canc, 0 extra, 0 desig) | 691 ✅ |
| `attendance_records` | 95 | 95 ✅ |
| `student_enrollments` | 18 | 18 ✅ |
| `subjects` | 9 | 9 ✅ |
| `quiz_schedules` | 18 | 18 ✅ |
| `users` | 30 | 30 ✅ |
| `laboratory_experiments` | 0 | 0 ✅ |
| `laboratory_records` | 0 | 0 ✅ |

**Implementation blocker status**:

| Blocker | Status |
|---|---|
| No authoritative experiment catalog | ❌ UNRESOLVED — requires institution/owner input |
| Required migrations (A + B) | ✅ Designed and ready |
| Authorization surface | ✅ Fully specified |
| UI/IA structure | ✅ Designed |
| API design | ✅ Candidate endpoints specified |
| Verifier design | ✅ 20-point checklist ready |

> [!CAUTION]
> Phase 9.2.1 must not fabricate experiment data. Even when migrations, API, and UI are implemented, the Experiments tab must show an honest "curriculum not yet available" empty state until the owner supplies an authoritative catalog. The curriculum blocker is the only open item before 9.2.1 can show meaningful experiment data.

---

*Phase 9.2.0 COMPLETE. Companion documents: `docs/phase_9_0_laboratory_domain_audit.md`, `docs/phase_9_product_decisions.md`, `docs/phase_9_1_implementation_report.md`.*
