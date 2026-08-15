# Phase 9.2.1 — Laboratory Experiment Management (Implementation Report)

Status: **IMPLEMENTED 2026-08-16** — verification 29/29 + all frozen regressions
green except two documented pre-existing baseline-drift failures (see §10).
Not committed.

## 1. Executive summary

Phase 9.2.1 delivers the laboratory **experiment-management layer** on top of
the canonical attendance pipeline, exactly per the LOCKED Phase 9.2.0 audit
(`docs/phase_9_2_0_laboratory_experiment_audit.md`). Attendance stays
canonical — there is still no second lab attendance engine, and no
attendance/eligibility formula was touched. What was added:

```
Admin catalog (laboratory_experiments)          ← migrations A + B
        ↓
Student self-tracking (laboratory_records, forced PENDING)
        ↓
Admin signing (signed_by + signed_on)           ← only elevated signature
        ↓
Summary / Curriculum / Records / Activity API   ← /api/v1/laboratory/{code}
        ↓
/laboratory frontend route (3 tabs)             ← honest empty state
```

The core product rules (audit §16) are enforced server-side: students can only
create/edit/delete their own **PENDING** records (signature_status in payload
→ 403); only ADMIN can set SIGNED (which stamps `signed_by` + `signed_on`);
duplicate `(user_id, experiment_id)` → 409; an experiment must belong to the
subject and be ACTIVE; a linked session must exist, be PRACTICAL, belong to
the same subject, and not be cancelled (400/404); unenrolled students get 404
on reads and 403 on writes; admins bypass enrollment.

**No fabricated curriculum**: `laboratory_experiments` and
`laboratory_records` are 0 rows in the final DB state — the verifier restored
its temporary data exactly, and the frontend renders an honest "Experiment
curriculum not yet available" empty state when the catalog is empty.

## 2. Product decisions — LOCKED (audit §19–§21)

| Decision | Implemented as |
|---|---|
| Curriculum = provenance-bound admin ingestion | `POST/PATCH/DELETE /experiments` admin-only; nothing seeded |
| Per-subject count = catalog row count | `UNIQUE(subject_id, experiment_number)`; summary `total` = ACTIVE catalog count |
| No FACULTY role (Decision 2) | STUDENT + ADMIN only, capability matrix in `_guard_read`/`_guard_write` |
| Minimal additive audit identity (Decision 3) | `signed_by`, `created_by`, `updated_by`, `signed_on`; timestamps already existed (Base mixin) |
| Nullable session FK (Decision 4) | `laboratory_records.class_session_id` nullable; validated at write time |
| Mid-sem advisory only (Decision 5) | Advisory string in summary; NEVER gates designation (verified §10 check 13) |
| Two-tier student boundary (Decision 6) | PENDING (student) → SIGNED (admin only) |
| No grading/viva (Decision 7) | Not implemented |

## 3. Migrations (applied, additive, reversible)

| Rev | File | Changes |
|---|---|---|
| `f1a2b3c4d5e6f` | `f1a2b3c4d5e6f_add_lab_experiment_catalog.py` | `laboratory_experiments.description` (nullable), `is_active` (NOT NULL, server_default `true`), `UNIQUE(subject_id, experiment_number)` (`uq_subject_experiment`) |
| `f6a5b4c3d2e1f` | `f6a5b4c3d2e1f_add_lab_record_audit.py` | `laboratory_records.class_session_id` (FK → class_sessions), `signed_by`, `created_by`, `updated_by` (FK → users) |

- Chain: `… → a1b2c3d4e5f6 → f1a2b3c4d5e6f → f6a5b4c3d2e1f`; alembic head
  confirmed `f6a5b4c3d2e1f`.
- `created_at`/`updated_at` already existed on both tables (Base mixin) —
  deliberately NOT re-added. **Zero existing data rows changed.**

## 4. Models, schemas, repository, service, API

**Models** (`backend/app/models/`)
- `laboratory.py` — `LaboratoryExperiment`: `description`, `is_active`
  (default True), `__table_args__` unique constraint `uq_subject_experiment`.
  `LaboratoryRecord`: `class_session_id`, `signed_by`, `created_by`,
  `updated_by`, `class_session` relationship. Explicit `foreign_keys` on the
  `user` relationship (the record now has 4 FKs to users).
- `timetable.py` — `ClassSession.laboratory_records` back-reference.
- `user.py` — `lab_records` relationship with
  `foreign_keys=[LaboratoryRecord.user_id]` (fixes AmbiguousForeignKeysError
  from the multi-FK users relationship).

**Schemas** (`backend/app/schemas/laboratory.py`) — experiment
create/update/response (+`description`, `is_active`); record
create/update/response (+`class_session_id`, `signed_by`, `signed_on`,
`created_by`, `updated_by`; create payload has NO `signature_status` field);
`LaboratorySummaryResponse` (PracticalAttendanceSummary +
`ExperimentProgressSummary` + `MidSemStatusSummary`); `LaboratoryActivityResponse`
/ `LaboratoryActivityItem` (experiments: `List[LaboratoryRecordResponse]`).
Phase 8.2 mid-sem schemas preserved.

**Repository** (`backend/app/repositories/laboratory_repo.py`) —
`get_experiments_for_subject` (active_only), `get_experiment_by_id`,
`get_record_for_user_and_experiment`, `get_student_records`, `get_record_by_id`
(with `selectinload(LaboratoryRecord.experiment)` — required for the async
session; lazy loading would raise MissingGreenlet), `get_record_counts`
(signed/pending), `get_activity_rows` (outer-join of attendance + lab records,
PRACTICAL sessions only, date desc).

**Service** (`backend/app/services/laboratory_service.py`) — guards
(`_get_subject`, `_guard_read` → 404 unenrolled, `_guard_write` → 403
unenrolled, `_validate_session_link` → session must exist / same subject /
PRACTICAL / not cancelled); `get_summary` (reuses
`AttendanceService.get_summary` — backend-owned attendance math, zero React
math; advisory `"X of Y experiments officially completed"` only when the
catalog exists, else `null`); `get_curriculum`, `get_records`, `get_activity`,
`create_record` (PENDING forced; duplicate → 409; inactive experiment → 400),
`update_record` (student: own PENDING only, `signature_status` in payload →
403; admin: PENDING→SIGNED stamps `signed_by`/`signed_on`, PENDING→PENDING
400), `delete_record`, `create_experiment` (duplicate number → 409),
`update_experiment`, `deactivate_experiment` (soft, records keep FK).
Phase 8.2 mid-sem service methods preserved unchanged.

**API** (`backend/app/api/v1/endpoints/laboratory.py`) — all under
`/api/v1/laboratory/{code}`:

| Method/Path | Role | Notes |
|---|---|---|
| `GET /summary` | student (enrolled) / admin | practical block from canonical summary + experiment progress + mid-sem status |
| `GET /experiments` | student (enrolled) / admin | ACTIVE catalog only |
| `GET /records` | student (enrolled) / admin | student's own records |
| `GET /activity` | student (enrolled) / admin | chronological PRACTICAL sessions + linked experiment records |
| `POST /records` | student (enrolled) / admin | 201; PENDING forced |
| `PATCH /records/{id}` | student (own, PENDING) / admin | admin may also edit SIGNED; sign → `signed_by`/`signed_on` |
| `DELETE /records/{id}` | student (own, PENDING) / admin | 204 |
| `POST /experiments` | admin | 201 |
| `PATCH /experiments/{id}` | admin | correct title/description |
| `DELETE /experiments/{id}` | admin | 204; deactivates (`is_active=False`) |
| `GET/PUT/DELETE /mid-sem` | admin (PUT) | Phase 8.2 — UNCHANGED |

## 5. Frontend

- `frontend/src/app/(authenticated)/laboratory/page.tsx` — NEW dedicated
  route `/laboratory` (static route, built). Subject selector (subjects
  filtered to `SubjectCategory.LAB`); three tabs — **Practical Attendance**
  (default; canonical summary stats + mid-sem card), **Experiments**
  (curriculum rows with Track / Pending / Signed states; admin ingest form +
  sign + deactivate; honest empty state "Experiment curriculum not yet
  available" when `catalog_available=false`), **Activity** (chronological
  session list with class type / cancelled / extra / attendance / designation
  badges; sessions without a record show "Practical session — no experiment
  recorded"; linked records show Signed/Pending badges).
- `frontend/src/hooks/useApi.ts` — `useLabSummary`, `useLabActivity`,
  `useLabMutations` (create/update/delete record + experiment); existing
  `useLabExperiments`/`useLabRecords` retained.
- `frontend/src/types/api.ts` — extended `LaboratoryExperimentResponse` /
  `LaboratoryRecordResponse`; `SignatureStatus` enum; record/experiment
  create/update payloads; `LaboratorySummary` / `LaboratoryActivityItem` /
  `LaboratoryActivityResponse`.
- `frontend/src/components/layout/TopNav.tsx` — added **Laboratory** →
  `/laboratory` (Track → `/tools/laboratory` unchanged; the Track page is NOT
  the lab page).

No React-side attendance math; no "10 experiments" placeholder anywhere.

## 6. Authorization matrix (audit §16, verified)

| Operation | STUDENT (enrolled) | STUDENT (unenrolled) | ADMIN |
|---|---|---|---|
| Read summary/experiments/records/activity | ✅ | 404 (no subject leak) | ✅ |
| Create record | ✅ forced PENDING | 403 | ✅ (also forced PENDING) |
| Edit/delete own PENDING record | ✅ | 403 | ✅ |
| Set SIGNED / edit SIGNED record | 403 | 403 | ✅ (stamps signed_by/signed_on) |
| Ingest/edit/deactivate experiments | 403 | 403 | ✅ |
| Mid-sem designation (Phase 8.2) | 403 | — | ✅ |

## 7. Record lifecycle rules (verified)

- Create: `experiment_id` must exist, be ACTIVE, and belong to the subject;
  `class_session_id` (optional) must be an existing PRACTICAL session of the
  same subject, not cancelled; duplicate `(user_id, experiment_id)` → 409.
- Student update: only own PENDING records; any `signature_status` → 403.
- Admin sign: PATCH `{"signature_status":"signed"}` on a PENDING record →
  `signed_by` = admin id, `signed_on` = now; PATCH to set PENDING back → 400;
  admin may edit SIGNED records (history truth) and delete any record.
- Deletion of the last PENDING record restores the pending count; deletion of
  a SIGNED record is admin-only (students get 403).

## 8. Mid-sem relationship (FROZEN, untouched)

Phase 8.2 `GET/PUT/DELETE /mid-sem` semantics, Phase 9.1 event-driven
designation, and the advisory-only rule are preserved. The advisory
(`"X of Y experiments officially completed"`) is presentation-only — it never
gates designation (verified: designation succeeds while the catalog is empty
and at 0 of 3).

## 9. Database mutation / baseline status

- Migrations A + B applied (alembic head `f6a5b4c3d2e1f`); strictly additive;
  zero pre-existing rows changed.
- The verifier snapshots the baseline at start and restores it exactly
  (check 19): temporary experiments, records, events, sessions, enrollments,
  and users are all removed; the 13-table counts return to the snapshot.
- Final DB state after all verification (identical to the Phase 9.2.0 audit
  baseline):
  `events=22 · sessions=691 (0 cancelled, 0 extra) · records=95 ·
  enrollments=18 · subjects=9 · quiz_schedules=18 · users=30 (1 ADMIN) ·
  laboratory_experiments=0 · laboratory_records=0 · designations=0`.

## 10. Verification results

### Phase 9.2.1 verifier — `backend/scripts/verify_phase_9_2.py` — 29/29 PASS

The 20-point audit checklist (§18) plus documented sub-checks:

1. baseline snapshot recorded (22 events / 691 sessions / 0 cancelled / 0
   extra / 95 records / 18 enrollments / 9 subjects / 18 quizzes / 30 users /
   0 lab rows)
2. admin ingests experiment → 201 (description persisted, `is_active` default
   true)
3. duplicate `(subject_id, experiment_number)` → 409
   3b. same number allowed on a DIFFERENT subject (per-subject numbering)
   3c. numbering resets per subject
4. student cannot ingest experiments → 403
5. student creates PENDING record for enrolled subject → 201 (forced PENDING)
6. PENDING record with valid PRACTICAL session of the same subject → accepted
   (class_session_id persisted)
7. PENDING record cannot reference a cancelled session → 400
8a. student record payload with `signature_status` → 403
8b. student cannot sign someone else's record → 403
9a. admin signs a PENDING record → SIGNED with `signed_by` + `signed_on`
    populated
9b. signed record remains visible in the student's record list
9c. admin editing a signed record works
9d. admin setting a record back to PENDING → 400
10. duplicate `(user_id, experiment_id)` → 409 (UniqueConstraint enforced)
11a. unenrolled student GET summary → 404
11b. unenrolled student POST record → 403
11c. unenrolled student GET experiments → 404
12a. summary advisory is `null` when the catalog is empty
    (`catalog_available=false`, total=0, signed=0, pending_self_tracked=0)
12b. advisory shows "0 of 3" after ingesting a 3-experiment catalog
12c. advisory shows "1 of 3" after one record is signed
13. advisory does NOT gate mid-sem designation (Phase 8.2 PUT succeeds at
    0/3)
14. cancelled-session attendance is NOT in the lab activity read model
15. `laboratory_experiments` returns to 0 after cleanup (no ingestion residue)
16. practical attendance percentages unchanged after adding/removing records
    (canonical formulas intact)
17. quiz eligibility unchanged — labs still 404; eligibility payload
    byte-identical before/after
18. no fabricated experiment data (both lab tables 0 before and after)
19. database restored to the exact baseline (all 13 counts + cancelled/extra/
    designations)
20. frozen regressions (below)

### Frozen regressions (run WITHOUT modification; none weakened)

| Verifier | Result |
|---|---|
| verify_phase_6_5.py | 27/27 PASS |
| verify_phase_6_6.py | 36/36 PASS |
| verify_phase_6_7.py | **29/31** — checks 4 & 7 fail on PRE-EXISTING drift (see below) |
| verify_phase_7_1.py | **25/26** — check 23 `records == 92` fails at **95** (same drift documented in the Phase 9.1 report) |
| verify_phase_7_2.py | 26/26 PASS |
| verify_phase_8_1.py | 22/22 PASS |
| verify_attendance_spec_alignment.py | 15/15 PASS |
| verify_phase_8_2.py | 18/18 PASS |
| verify_phase_9_1.py | 28/28 PASS |

**6.7 checks 4 & 7 — PRE-EXISTING baseline drift (NOT Phase 9.2.1 residue):**
the frozen verifier asserts the DB contains exactly the 18 seeded QUIZ_DAY
events, all ACTIVE. The live DB has **22 events**: 4 additional events
(3 EXTRA_LECTURE + 1 MID_SEM_PRACTICAL; 3 inactive, 1 active) created
2026-08-15 17:56–18:01 UTC — owner/manual testing between the Phase 9.1
report and the Phase 9.2.0 audit (the 9.2.0 audit's own baseline already
records events=22). Check 4 (`GET /events` default = active only; count 19 ≠
18) and check 7 (seeding integrity: `{'QUIZ_DAY': 18, 'EXTRA_LECTURE': 3,
'MID_SEM_PRACTICAL': 1}`, inactive=3) fail on this drift. Per policy the
verifier was NOT modified and the data was NOT deleted.

**7.1 check 23 — same drift as Phase 9.1:** records 92 → 95 (3 legitimate
owner-entered marks on BCS-502 lectures, 2026-08-15 13:36–16:20 UTC, through
the canonical attendance mutation path). Already documented in
`docs/phase_9_1_implementation_report.md` §9.

**Owner decision required (as before):** authorize fixture updates
(events 18 → 22 with 3 inactive; records 92 → 95) or accept these two
checks as documented known-failing baseline assertions.

### Static verification

- Backend: `python -m compileall app` — PASS; `from app.main import app` —
  PASS; `alembic current` → `f6a5b4c3d2e1f (head)`.
- Frontend: `npx tsc --noEmit` — PASS; ESLint on changed files — PASS
  (0 errors, 0 warnings); `next build` — PASS (15 static routes, `/laboratory`
  included).

No browser/E2E verification was performed (manual testing remains the user's
responsibility).

## 11. Exact files changed

**Backend**
- `backend/alembic/versions/f1a2b3c4d5e6f_add_lab_experiment_catalog.py` —
  NEW migration A (description, is_active, uq_subject_experiment; applied).
- `backend/alembic/versions/f6a5b4c3d2e1f_add_lab_record_audit.py` — NEW
  migration B (class_session_id + signed_by/created_by/updated_by; applied).
- `backend/app/models/laboratory.py` — experiment/record model changes
  (rewritten).
- `backend/app/models/timetable.py` — `ClassSession.laboratory_records`.
- `backend/app/models/user.py` — `lab_records` foreign_keys fix.
- `backend/app/schemas/laboratory.py` — rewritten (experiment/record schemas,
  summary, activity, payloads).
- `backend/app/repositories/laboratory_repo.py` — expanded CRUD + counts +
  activity.
- `backend/app/services/laboratory_service.py` — rewritten (guards, lifecycle,
  advisory, mid-sem preserved).
- `backend/app/api/v1/endpoints/laboratory.py` — rewritten (summary/
  experiments/records/activity + write endpoints; mid-sem preserved).
- `backend/scripts/verify_phase_9_2.py` — NEW verifier (29 checks).

**Frontend**
- `frontend/src/app/(authenticated)/laboratory/page.tsx` — NEW `/laboratory`
  route (3 tabs).
- `frontend/src/hooks/useApi.ts` — useLabSummary / useLabActivity /
  useLabMutations.
- `frontend/src/types/api.ts` — extended lab types + SignatureStatus.
- `frontend/src/components/layout/TopNav.tsx` — Laboratory nav item.

**No other files changed.** Frozen verifiers untouched. No commit made.

## 12. Deliberately NOT implemented (per scope)

- No fabricated experiment data (lab tables 0/0 in final state).
- No FACULTY role; no grading/viva/marks workflow (Decision 7).
- No auto-designation; no experiment-count gate on anything (Decision 5).
- No changes to the frozen attendance engine, quiz eligibility formulas,
  overall attendance formulas, event authorization policy, Phase 6 calendar
  architecture, or Phase 8.2 mid-sem semantics.
- No second lab attendance engine; no React-side attendance math.
- Phase 9.2.2 (anything beyond this scope) NOT started.

## 13. Known limitations

- **Baseline drift (§10)**: 6.7 checks 4/7 and 7.1 check 23 fail on
  pre-existing owner-entered data; frozen verifiers unmodified. Owner decision
  pending (same as Phase 9.1).
- Curriculum provenance: ingestion is admin-only and unvalidated against an
  external source until an authoritative catalog exists (audit §20 unknowns).
- Advisory wording is a derived string; catalog availability drives its
  presence (null vs "X of Y").
- Experiments are never deleted — `DELETE /experiments` deactivates; records
  keep their FK. This is intentional history truth.

## 14. Manual browser checklist (for the user)

A. `/laboratory` — pick a lab subject (BCS-551/552/553): Practical
   Attendance tab shows the canonical summary + mid-sem card; Experiments tab
   shows the honest empty state; Activity tab lists real PRACTICAL sessions.
B. As ADMIN: ingest an experiment (number/title/description) → appears in the
   catalog; sign a student's PENDING record → Signed badge + advisory updates.
   Deactivate an experiment → disappears from the catalog, records preserved.
C. As STUDENT: create a record (with optional session link) → Pending badge;
   attempt to set SIGNED or ingest experiments → rejected (403).
D. Activity tab: sessions with a linked experiment show its Signed/Pending
   status; sessions without one show "no experiment recorded".
E. `/tools/laboratory` (Track) — unchanged; `/laboratory` is the new page.
F. Mid-sem card unchanged; designation still admin-only via Phase 8.2.

## 15. Is Phase 9.2.1 genuinely FREEZABLE?

**Code-wise: YES** — the Phase 9.2.1 verifier is 29/29, every frozen
regression is green except the two documented pre-existing drift checks
(6.7 checks 4/7, 7.1 check 23), static gates pass, migrations are at head,
and the DB is byte-equivalent to the Phase 9.2.0 baseline. The **only open
item is the owner's baseline-policy decision** on those drift checks — same
decision already pending from Phase 9.1 (fixture update vs documented
known-failing). Until then, Phase 9.2.1 freezes with those two checks as
documented known-failing baseline assertions.

---

**HARD STOP — Phase 9.2.1 implementation complete. Phase 9.2.2 NOT started.
No commit made.**