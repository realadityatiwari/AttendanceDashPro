# Events Backend Remediation — Phase 1 Report (EVT-003)

**Date:** 2026-10-02
**Scope:** EVT-003 ONLY — "Quiz-schedule-managed QUIZ_DAY guard is endpoint-scoped and bypassable" (the sole Confirmed High finding of `docs/EVENTS_BACKEND_DEEP_AUDIT_REPORT.md`).
**Source of truth:** the deep audit report + repository `main @ 13a4795`.
**Mode:** Backend-only remediation. No migrations, no schema changes, no frontend changes, no notification-behavior changes, no attendance/eligibility-calculation changes.

---

## 1. Objective

Enforce the quiz-manager ownership invariant **at the domain/service layer** so every mutation path inherits it:

> A QUIZ_DAY event backed by a SCHEDULED QuizSchedule MUST NOT be manually created, edited, re-dated, type-changed, or deactivated through generic event mutation paths.

Concretely: `POST /api/v1/events`, `PATCH /api/v1/events/{id}`, `DELETE /api/v1/events/{id}` (which call `EventService` directly) must enforce the same guard the admin portal enforced, and a type-change **into** a managed configuration must be checked against the FINAL prospective state, not only the old state. The Quiz Schedule Manager must retain its full create/update/retire capability.

## 2. Original EVT-003 Defect

The Phase 24.9 guard (`_is_quiz_schedule_managed` + two assert helpers) lived only in `AdminEventService`, i.e. only on `/api/v1/admin/events`. The canonical `/api/v1/events` endpoints called `EventService` directly with no guard, so any effective admin could:

- `DELETE /api/v1/events/{id}` a schedule-backed QUIZ_DAY → the quiz date silently disappeared from every eligibility computation (active QUIZ_DAY events are the authoritative quiz-date source — `QuizRepository.get_effective_quiz_dates_for_subjects`);
- `PATCH /api/v1/events/{id}` a standalone event's `event_type` → `QUIZ_DAY` (or re-date/re-scope a QUIZ_DAY) onto a schedule-backed identity → duplicate/shifted chronological cycle numbering → eligibility window corruption.

A secondary gap: even on the admin portal, the prospective PATCH check ran only when the **old** type was already QUIZ_DAY, so a type-change INTO a managed configuration was not prospectively blocked.

## 3. Root Cause

The invariant was implemented as a **route-consumer concern** instead of a **domain rule**. `AdminEventService` (one consumer of `EventService`) protected its own endpoints, but the domain service — the single funnel every generic mutation passes through — had no knowledge of quiz-manager ownership. The ownership query itself (a `QuizSchedule` lookup by `(subject_id, elective_slot, date)` with `schedule_status = SCHEDULED`) existed only as a private method of that consumer.

## 4. Exact Implementation

### 4.1 `backend/app/services/event_service.py` (the domain guard)

- New module constant `MANAGED_QUIZ_DAY_CONFLICT` — the canonical 409 message (wording mirrors the Phase 24.9 messages it replaces, so the admin UI keeps surfacing the same guidance).
- New imports: `datetime.date`, `sqlalchemy.select`, `app.models.quiz.QuizSchedule/ScheduleStatus` (read-only model usage; no schema change).
- **`EventService.is_quiz_schedule_managed(*, event_type, subject_id, elective_slot, quiz_date) -> bool`** — the single canonical ownership resolver: `True` iff `event_type == QUIZ_DAY`, `subject_id` and `quiz_date` are set, and a `QuizSchedule` row exists with the same `subject_id`, `date`, `schedule_status = SCHEDULED`, and matching `elective_slot` (`NULL` matches `NULL`). Semantics are identical to the former `AdminEventService` implementation (same identity the seed script and `AdminQuizRepository.find_quiz_day_event` use).
- **`EventService._assert_not_quiz_schedule_managed(...)`** — raises `EventConflict` (→ 409) when the resolver fires. Runs **before any flush, session synchronization, commit, or notification side effect**.
- Guard call sites:
  - **`create_event`** — after authorization, before registry validation/duplicate check: rejects generic creation of a managed QUIZ_DAY (prospective identity check).
  - **`update_event`** — twice: (a) **old state**, immediately after the first `assert_mutation_allowed`: an existing managed QUIZ_DAY may not be edited at all through generic paths (note edits, re-dates, type changes away, active-flag flips); (b) **final state**, after fields are applied and final re-authorization: the PROPOSED state must not become a managed QUIZ_DAY — this closes the type-change bypass. (The old-state check makes the final-state check reachable only for non-managed events; both are cheap indexed-by-PK lookups on `quiz_schedules`.)
  - **`deactivate_event`** — after authorization: rejects generic deactivation of a managed QUIZ_DAY. (Retirement remains exclusively `AdminQuizService._retire_quiz_event`, which flips the row directly and never routes through `EventService`.)
- Why raise `EventConflict`: both endpoint layers already mapped `EventConflict → 409` for create/update; the only new mapping needed was the DELETE path (below). This preserves the documented conflict status everywhere without adding route-layer logic.

### 4.2 `backend/app/services/admin_event_service.py` (delegation, no divergence)

- `_is_quiz_schedule_managed` now **delegates** to `EventService.is_quiz_schedule_managed` (it remains as a thin alias because the admin read model's `quiz_schedule_managed` field uses it) — one ownership query in the codebase.
- The two private assert helpers (`_assert_not_quiz_managed`, `_assert_prospective_not_quiz_managed`) and their call sites in `create_event`/`update_event`/`deactivate_event` were **removed** — the domain guard in `EventService` enforces the same invariant (including the old-state + final-state checks the admin portal previously lacked).
- `AdminEventQuizManagedError` (now unreachable) was deleted; `admin.py`'s dead import of it was removed.
- `deactivate_event` gained `except EventConflict → AdminEventDomainError(409)` — previously unnecessary because the old guard pre-checked; now required so the domain 409 maps correctly on the admin DELETE path.

**The old AdminEventService guard was DELEGATED (removed and replaced by the canonical domain guard), not retained as a duplicate.** Rationale: keeping two implementations of the same ownership query was the exact divergence risk the audit flagged; delegation preserves the admin portal's behavior (same 409 status, near-identical message text) while making `EventService` the single enforcement point. The read-model field retains a delegating alias rather than calling the resolver inline at each use site.

### 4.3 `backend/app/api/v1/endpoints/events.py` (exception mapping only)

- `delete_event` gained `except EventConflict → HTTPException(409)` — required because the domain guard can now raise `EventConflict` from `deactivate_event`, and this endpoint previously had no mapping for it (it would have surfaced as 500). **No guard logic was added at the route layer** — the route change is purely exception-to-status translation. `create_event`/`update_event` already mapped `EventConflict → 409`.

### 4.4 `backend/app/api/v1/endpoints/admin.py`

- Removed the now-dead `AdminEventQuizManagedError` import. No other change.

## 5. Service-Layer Invariant (after remediation)

For every generic event mutation path (`EventService.create_event / update_event / deactivate_event` — hence every current and future HTTP consumer):

| Mutation | Guard check | Result |
|---|---|---|
| Create `QUIZ_DAY` whose identity is schedule-backed | prospective | 409 `EventConflict` |
| Update an existing managed QUIZ_DAY (any field, any target state) | old state | 409 |
| Update any event so its FINAL state is a managed QUIZ_DAY (type-change, re-date, re-scope) | final state | 409 |
| Deactivate a managed QUIZ_DAY | old state | 409 |
| Create/update/deactivate of any unmanaged event (including standalone QUIZ_DAY and all flexible types) | — | unchanged behavior |
| Quiz-manager create/update/retire (`AdminQuizService._ensure_quiz_event` / `_retire_quiz_event`) | not routed through `EventService` | unchanged (full ownership) |

Rejections happen **before** any flush, `EventSessionSynchronizer` run, commit, or `after_event_mutation` call — a rejected mutation persists nothing and emits nothing.

## 6. Create / Update / Delete Behavior

- **Create:** authorization (403 for students on QUIZ_DAY — unchanged) → quiz-ownership check (409 if managed) → registry validation → duplicate check → persist. Precedence matches the former admin-portal behavior (ownership conflict outranks shape validation).
- **Update:** authorization on existing state → old-state ownership check → fields applied → slot invariants → final authorization → final-state ownership check → validation → duplicate check → span-union reconciliation → commit. Both check orders preserve the documented statuses: students still get 403 (they could never mutate global/quiz events), admins get 409 for managed events.
- **Delete/deactivate:** authorization → ownership check (409 if managed) → soft-deactivate → reconciliation. No reconciliation persists and no notification side effect occurs on rejection.

## 7. Prospective Type-Change Protection

`update_event` now validates the FINAL proposed state against the quiz-manager ownership resolver. `EXTRA_LECTURE → QUIZ_DAY` (with `class_type` nulled) re-dated onto a schedule-backed identity is rejected with 409 — verified by test T4. This closes the secondary gap that existed even on the admin portal (whose prospective check only ran when the old type was already QUIZ_DAY).

## 8. Quiz-Manager Path Preservation

`AdminQuizService` never routes through `EventService`: `_ensure_quiz_event` inserts the `AcademicEvent` row directly (`event_repo.add` + flush + synchronizer) and `_retire_quiz_event` flips `active = False` directly. The domain guard therefore cannot interfere with quiz-manager flows — verified by test T6 (create → idempotent re-ensure → retire → re-ensure) and by the existing out-of-band verifiers (`verify_phase_24_10.py` 35/35, `verify_phase_2_quiz_events.py` mutation checks, `test_quiz_cycle_order.py`).

## 9. Tests Added

`backend/tests/test_evt003_quiz_managed_guard.py` — 8 tests, following the repo's savepoint-sandbox convention (`_RollbackSession`: `commit()` becomes a flush inside an outer transaction; everything rolls back; synthetic `TX-*` fixtures isolate notification recipients so no real push can fire; one scenario uses the REAL seeded managed identity BCS-501 @ 2026-09-17):

| Test | Covers |
|---|---|
| T1 `test_t1_canonical_create_of_managed_quiz_day_rejected` | canonical POST equivalent → `EventConflict`; no event row, no session row materializes |
| T2 `test_t2_canonical_patch_of_managed_quiz_day_rejected` | canonical PATCH equivalent → note edit and re-date both rejected; state unchanged |
| T3 `test_t3_canonical_delete_of_managed_quiz_day_rejected` | canonical DELETE equivalent → rejected; event stays active |
| T4 `test_t4_type_change_into_managed_quiz_day_rejected` | `EXTRA_LECTURE → QUIZ_DAY` onto a managed identity → rejected on the FINAL state; original type/date intact |
| T5 `test_t5_admin_service_still_rejects_prohibited_mutations` | `AdminEventService` create/update/deactivate all surface `AdminEventDomainError` with the documented **409** (delegation regression) |
| T6 `test_t6_quiz_manager_path_preserved` | quiz-manager create / idempotent re-ensure / retire / re-create all still work through its dedicated path |
| T7 `test_t7_unmanaged_quiz_day_creation_unchanged` | standalone (unmanaged) QUIZ_DAY creation and editing unchanged |
| T8 `test_t8_rejection_has_no_side_effects_on_real_managed_identity` | on the real managed identity the DOMAIN guard fires (proving precedence over the duplicate guard) with zero side effects: no phantom event, no session reconciliation, no notification mutation |

All 8 pass. (Full HTTP-level coverage of the endpoints remains with the out-of-band verifiers noted below; the service-level tests exercise the exact code the routes call.)

## 10. Existing Tests / Verifiers Run

**pytest baseline (pre-edit):** 171 passed / 2 failed — the 2 failures (`tests/test_ui_formula_text.py`) are pre-existing static assertions on FRONTEND text (stale expectations vs. the Phase 4 P3 UI copy) and are unrelated to Events. They fail identically at `13a4795` with no backend changes.

**pytest (post-edit):** **179 passed / 2 failed** (171 + 8 new; same 2 pre-existing unrelated failures).

**Out-of-band verification scripts** (live DB, restore the frozen baseline by design; these are NOT pytest tests — documented per the task):

| Script | Result | Relevance |
|---|---|---|
| `verify_phase_24_10.py` | **35/35 PASS** | admin-portal guard regression incl. "schedule-managed QUIZ_DAY DELETE → 409 (guard intact)" — passes with delegation |
| `verify_phase_6_5.py` | **27/27 PASS** | full event security matrix over the real API (403/409/422/404) |
| `verify_phase_6_6.py` | **36/36 PASS** | event → engine session integration incl. QUIZ_DAY creation via canonical API |
| `verify_phase_6_7.py` | **31/31 PASS** | calendar/events freeze, seeded QUIZ_DAY authority, re-enable via PATCH |
| `verify_event_cancellation_propagation.py` | **23 PASS / 1 FAIL / crash in its own cleanup — PRE-EXISTING** (see below) | cancellation propagation incl. mutation-endpoint 409 |
| `verify_cancellation_lifecycle_consistency.py` | **35/35 PASS** | deactivation reconciliation self-healing |
| `verify_phase_3_quiz_eligibility_propagation.py` | **26/26 PASS** | events → quiz eligibility end-to-end |
| `verify_phase_2_quiz_events.py` | **12/15** — 3 failures **PRE-EXISTING** (see below) | quiz-event authority/dedup/reschedule/deactivate/reactivate |
| `verify_events_correction.py` | **38 checks PASS**, then crashes in its own cleanup — **PRE-EXISTING** (see below) | registry rules, admin-only QUIZ_DAY, student contracts |

**Pre-existing failures — evidence they are NOT caused by this change** (each reproduced on the PRISTINE tree by stashing the four remediation files and re-running):

1. `verify_phase_2_quiz_events.py` checks 3/4/5: dev-data drift — the DB now has 10 `quiz_applicable` theory subjects but only 6 are seeded with quiz cycles, and a "2nd Quiz @ 2026-10-05" exists that the script's hardcoded expectations predate. Identical 3 failures with and without the remediation. The script's own baseline-restoration check (15) passes.
2. `verify_events_correction.py`: all 38 behavioral checks pass (including QUIZ_DAY-creation, duplicate-409, and student-contract checks); the crash is in the script's own fixture cleanup — `_verifier_harness.cleanup_fixture_event_notifications` hard-deletes fixture events while preserved attended-extra sessions still reference them via `class_sessions.source_event_id` (FK added by migration `e2f3a4b5c6d7`, no `ondelete`). Identical crash on the pristine tree (same constraint, same referenced key). Not modified — the bug is in verifier infrastructure (adjacent to the audit's EVT-004/no-ondelete finding), not in EVT-003's scope.
3. `verify_event_cancellation_propagation.py`: check 0b ("fixture sessions hold pre-existing (owner) attendance") fails because the dev data no longer has owner attendance on those sessions (`src=0, tgt=0`) — read-only data drift; the subsequent crash is the script's own cleanup deleting its temp users while Phase 11C-P4 notification triggers emitted rows referencing them. Identical FAIL + crash on the pristine tree. Not modified.

**Verifier residue handling:** because two verifiers crash in their own cleanups, each left fixture rows (14 titled events + temp students + dependents). After each run the residue was removed with FK-safe, ownership-scoped deletes (the scripts' own naming contracts: `VerifyEventsCorrection …` events, `ECF_TMP%` users, sessions/records/outcomes/notifications derived from them). Final DB state verified equal to the pre-validation baseline: **18 academic_events (18 active QUIZ_DAY), no temp users, no new orphans (452 legacy orphan notifications unchanged — that is EVT-008, untouched)**.

## 11. Validation Results

| Check | Result |
|---|---|
| Targeted EVT-003 tests | ✅ 8/8 passed |
| Full backend pytest | ✅ 179 passed / 2 failed (both pre-existing, frontend-text, unrelated) |
| Related existing tests (`extra_lifecycle_foundation`, `quiz_cycle_order`, `deactivated_attended_extra`, `notification_projection`) | ✅ 37 passed |
| Verifiers fully green | ✅ `phase_24_10` 35/35, `phase_6_5` 27/27, `phase_6_6` 36/36, `phase_6_7` 31/31, `cancellation_lifecycle` 35/35, `phase_3_eligibility_propagation` 26/26 |
| Verifiers with pre-existing failures (pristine-tree-reproduced) | `phase_2_quiz_events` 12/15, `events_correction` 38 PASS + cleanup crash, `event_cancellation_propagation` 23 PASS / 0b FAIL + cleanup crash |
| Static/type checks | none configured for the backend (no mypy/ruff/flake8 config in the repo); `py_compile` + full app import verified clean |
| Frontend tests | not run — no frontend or shared types touched (confirmed by `git status`) |
| `git diff` inspected | ✅ backend-only, 4 files + 1 new test file + this report |

**Boundary confirmations:** no migrations added; no schema/DDL change; no frontend change; no notification behavior change (the guard only *prevents* mutations; emission paths untouched); no attendance/eligibility calculation change (eligibility reads untouched; the guard only blocks illegitimate event mutations); no quiz-cycle numbering change; no EventType semantics change.

## 12. Files Changed

- `backend/app/services/event_service.py` — canonical resolver + domain guard + 3 call sites (+107/−0 net with comments)
- `backend/app/services/admin_event_service.py` — delegation, duplicate-guard removal, `EventConflict` mapping in deactivate (−80/+34 net)
- `backend/app/api/v1/endpoints/events.py` — DELETE: `EventConflict → 409` mapping (+4)
- `backend/app/api/v1/endpoints/admin.py` — dead import removed (−1)
- `backend/tests/test_evt003_quiz_managed_guard.py` — new (T1–T8)
- `docs/EVENTS_BACKEND_REMEDIATION_PHASE_1_REPORT.md` — this report

## 13. Remaining EVT-003 Limitations

1. **No HTTP-layer (TestClient) pytest coverage was added** — consistent with the repo's convention (HTTP verification lives in out-of-band live-DB verifiers; pytest is DB-free/savepoint). Service-level tests exercise the exact guard code the routes call, and `verify_phase_24_10.py`/`verify_phase_6_5.py` cover the HTTP stack. If HTTP-in-pytest coverage is wanted, it needs the repo to first gain a live-DB pytest harness convention.
2. **The guard is check-then-act** (single `SELECT` inside the mutation transaction, no `SELECT … FOR UPDATE`). A race against a concurrent quiz-manager mutation could still interleave — the residual risk is covered by the audit's EVT-004 (constraints/locks), which is explicitly out of scope here.
3. **`verify_events_correction.py` / `verify_event_cancellation_propagation.py` cleanup crashes and `verify_phase_2_quiz_events.py` stale expectations are pre-existing** and now documented; repairing verifier infrastructure (harness cleanup order vs. `source_event_id` FK; data-dependent expectations) remains out of scope.

The Events system is NOT "fully fixed": EVT-001/002 (stale notification lifecycle), EVT-004 (integrity constraints), EVT-005 (CLASS_REMINDER unreachable), and the remaining LOW findings/decisions from the audit remain open.

## 14. STOP

EVT-003 is implemented and validated. Nothing else was changed, nothing was committed, and no further audit findings were implemented.
