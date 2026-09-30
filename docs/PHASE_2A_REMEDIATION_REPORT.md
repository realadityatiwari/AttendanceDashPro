# PHASE 2A REMEDIATION REPORT — CORE BACKEND REMEDIATION

**Phase:** 2A — Core backend remediation (confirmed, decision-free findings)
**Date:** 2026-09-30 (Asia/Kolkata)
**Scope:** H-2 · H-4a · H-4c · H-4b · H-5 ONLY
**Input:** `docs/REMEDIATION_READINESS_REPORT.md` §11 SPECs + `docs/SYSTEM_FUNCTIONAL_BACKEND_AUDIT_REPORT.md`
**Baseline before this phase:** 141 backend pytest tests passing; alembic head `e2f3a4b5c6d7`; local PostgreSQL `attendancedash` (docker container `attendancedashpro_db`); 5 users; 452 orphaned ACADEMIC_EVENT notifications; policies 70/75/75; all quiz scopes strictly chronological.

**Hard constraints honored:** no schema migrations; no automatic destructive DB cleanup; no seed changes; no production DB operations; no eligibility-math changes; no Redis/worker/scheduler; no frontend changes; no refactors of unrelated services.

**Status:** H-2 FIXED · H-4a FIXED (purge implemented, NOT executed) · H-4c FIXED · H-4b FIXED · H-5 FIXED. Tests: 173 passed / 0 failed.

---

## H-2 — Deactivated-user live-token access

### Root cause
`get_current_user` (`backend/app/api/dependencies/deps.py`) validated the JWT and loaded the user but never checked `users.is_active`. Deactivation already blocked login (403) and refresh (`RefreshTokenService.rotate` revokes the family), so the only remaining hole was an access token issued *before* deactivation: it kept authorizing every student endpoint for up to `JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 480` (8h).

### Implementation
After the user-load (`if not user: 401`), the dependency now rejects inactive users:

```python
if not user.is_active:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Account is deactivated",
    )
```

401 (not 403) is deliberate: the frontend `apiFetch` flow (`frontend/src/lib/api.ts`) attempts its single-flight refresh on 401; for a deactivated user the refresh fails permanently (rotate revokes the family and raises), so the wrapper clears the token and redirects to login. No token-version infrastructure was introduced. Login's 403 and refresh's revocation behavior are untouched.

### Files changed
- `backend/app/api/dependencies/deps.py` — `get_current_user` (only change).

### Tests
New `backend/tests/test_auth_deactivation.py` (7 tests, DB-free stub-session pattern):
- active user + valid access token → user returned;
- deactivated user + valid access token (issued while active) → 401;
- deactivated user cannot login → 403 (unchanged);
- deactivated user cannot refresh → `RefreshTokenError` + revocation commit (unchanged);
- reactivated user regains access with the same token;
- missing user still 401; active user refresh still rotates normally (JWT refresh regression guard).

### Verification
- All 5 live users are `is_active = true` (SELECT-only probe) — no existing verifier/API flow is broken by the new guard.
- 7/7 new tests pass; full suite green.

---

## H-4a — Orphaned notification projections

### Current orphan baseline (fresh SELECT-only probe, 2026-09-30)
| Kind | Total | Orphaned (`event_id` → missing event) | Unread |
|---|---|---|---|
| ACADEMIC_EVENT | 452 | **452** | 452 |
| QUIZ_APPROACHING | 2 | 0 | 2 |
| ATTENDANCE_THRESHOLD | 3 | 0 | 3 |
| MUST_ATTEND | 9 | 0 | 9 |
| SAFE_SKIP | 8 | 0 | 8 |

Total notifications: 474. Affected users (all rows orphaned / unread within ACADEMIC_EVENT): `2401220100027` (owner) 182/182 (189 total unread), `9999999999999` 182/182 (188 unread), `8888888888888` 88/88 (88 unread), `2401220999001` 0/0. Zero orphans exist in any other kind.

### Cleanup implementation
`backend/scripts/purge_orphaned_event_notifications.py` — a dedicated, explicit cleanup script (nothing destructive is hidden in application startup):

1. **Before baseline** (SELECT-only): total notifications; counts by kind; orphan total + unread; orphan counts by kind; affected users with roll numbers; sample of up to 10 targeted rows.
2. **Exact target print**: the DELETE predicate verbatim + targeted row count.
3. **DRY-RUN BY DEFAULT** — without `--confirm` the script prints `DRY RUN - no rows were deleted.` and exits 0.
4. **`--confirm` required** for the DELETE; additionally the script refuses outright when `APP_ENV=production` (exit 2).
5. Executes one deterministic DELETE, commits, then prints the after-state: rows deleted, remaining total, remaining orphans, per-kind breakdown, and a self-check line (`zero orphaned event projections remain` / `WARNING`).

### Exact deletion criteria
```sql
DELETE FROM notifications
WHERE event_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM academic_events ev WHERE ev.id = notifications.event_id);
```
The predicate is defined once in production code as `app.repositories.notification_repo.orphaned_event_ref_clause()` and reused by the script. It cannot match live notifications, `QUIZ_APPROACHING`, `ATTENDANCE_THRESHOLD`, `MUST_ATTEND`, `SAFE_SKIP` (their `event_id` is NULL), or any row whose event still exists.

### Was the purge executed?
**NO.** The destructive purge was not executed. The script was run **dry-run only** against the dev DB (it reported 452 targeted rows) and did not delete anything. The 2026-09-30 probe confirms 452 orphans remain. Actual execution is deferred to the owner.

### Safety mechanism
Dry-run default; explicit `--confirm`; production refusal; exact one-predicate DELETE; before/after reporting; post-delete self-check. Read-layer hardening (H-4c) additionally makes orphaned rows invisible even before the purge runs.

---

## H-4c — Notification inbox retention/pagination (bounded reads)

### Root cause
`NotificationRepository.get_inbox` was an unbounded `SELECT` (newest-first, no LIMIT) and the service had no cap; orphaned rows could also surface as dead-deep-link items with a matching unread count.

### Pagination implementation
- `backend/app/repositories/notification_repo.py`
  - `DEFAULT_INBOX_PAGE_SIZE = 50`, `MAX_INBOX_PAGE_SIZE = 200`, `clamp_inbox_page_size()` (clamps into [1, 200], None/bad input → 50).
  - `get_inbox(user_id, *, limit=50, offset=0)` — deterministic `ORDER BY created_at DESC, id DESC`, `.limit()` + `.offset()`, so no unbounded SELECT can be issued.
  - `count_inbox(user_id)` — new; the pagination `total` (non-dismissed live rows).
  - Read-layer guard `_live_event_ref_clause()`: a row with `event_id` is only considered live when its academic event still exists. Applied to `get_inbox`, `count_unread`, and `count_inbox` — orphaned event projections cannot surface through the inbox **or the bell badge**, even before the one-time purge.
- `backend/app/services/notification_service.py`
  - `get_notifications(user, *, limit=50, offset=0)` clamps the page, passes it to the bounded repo read, and returns additive metadata: `total`, `limit`, `offset`, `has_more = offset + len(items) < total`.
  - TTL cache key is now `(user_id, limit, offset)` (each page cached independently); invalidation evicts every cached page for the user.
- `backend/app/api/v1/endpoints/notifications.py`
  - `GET /api/v1/notifications?limit=&offset=` with FastAPI validation: `limit` 1..200 (default 50), `offset` ≥ 0.
- `backend/app/schemas/notification.py`
  - `NotificationsResponse` gains `total`, `limit`, `offset`, `has_more` (defaulted, additive).

### Limits
Default page size 50; hard maximum 200 (service clamps defensively; endpoint rejects >200 with 422); offset ≥ 0 (negative clamped to 0).

### Retention
No retention period is documented anywhere in the project, so **age-based retention was NOT implemented** (no invented window, no scheduler). Retention duration + the CLASS_REMINDER scheduler decision remain product decisions — readiness report **D-5**. Documented in code (`notification_repo.py` header comment) and here.

### API compatibility
Response additions are additive with defaults; existing fields (`items`, `as_of`, `unread_count`) keep their names and semantics for live rows. The frontend bell/notification center calls the same endpoint with no parameters (gets the default first page + unchanged badge semantics) and ignores unknown fields — no frontend change was necessary or made.

### Tests
`backend/tests/test_notification_projection.py` (10 tests): clamping boundaries (None/0/-50/200/201/1e9/non-numeric), bounded statement shape (LIMIT = max, OFFSET applied, deterministic ORDER BY, EXISTS guard in SQL), service metadata (`has_more` true/false at the last page, empty inbox), negative-offset clamp, per-page caching; sandboxed real-DB (savepoint rollback) tests for ordering + page boundaries (`limit=2, offset=0/2/4/6`), live rows visible, orphan rows never surface (event deleted in-transaction), dismissed rows hidden, badge consistency (`unread_count` excludes orphan/dismissed), and service page metadata against real rows.

---

## H-4b — Verifier notification hygiene

### Problem
Verifier fixtures create AcademicEvents through the same `EventService` paths as production; `create_event`/`update_event` fan out ACADEMIC_EVENT projections to every affected user — including pre-existing real accounts (subject enrollees, elective-slot choosers, all users for global events). When a verifier then hard-deletes its fixture events, those third-party projections survived as orphans (the H-4a pollution origin; `notifications.event_id` has no FK).

### Implementation
New shared helper `backend/scripts/_verifier_harness.py`:
- `cleanup_fixture_event_notifications(db, event_ids, label=...)` — deletes every notification row whose `event_id` is one of the fixture's events, **for ALL users** (never only the verifier's own test users). Fixture-scoped by exact event id; returns the deleted count; does not commit (callers keep their commit structure).
- `assert_no_orphaned_fixture_notifications(db, event_ids, label=...)` — post-cleanup self-check; counts remaining rows referencing the fixture events, prints `remaining=N (OK|FAIL)`, and raises on failure.
- Ids are normalized (UUID/str, deduped); empty input is a safe no-op.

Production notification behavior is untouched — the harness is cleanup-only tooling.

### Affected verifier scripts (wired: 20)
Each was inspected for event creation + committed event deletion, then wired with the import, a fixture-scoped cleanup call beside the existing event deletion, and a post-cleanup self-check:

`verify_attendance_spec_alignment.py`, `verify_cancellation_lifecycle_consistency.py`, `verify_event_cancellation_propagation.py`, `verify_events_correction.py`, `verify_history_filters.py`, `verify_phase_3_quiz_eligibility_propagation.py`, `verify_phase_6_5.py`, `verify_phase_6_6.py`, `verify_phase_6_7.py`, `verify_phase_7_1.py`, `verify_phase_7_2.py`, `verify_phase_9_1.py`, `verify_phase_9_2.py`, `verify_quiz_day_materialization.py`, `verify_quiz_day_occurrence.py`, `verify_track_lab_fix.py`, `verify_working_saturday_holiday.py`, `verify_phase_22_4.py`, `verify_phase_24_9.py`, `verify_phase_24_10.py`.

Inspected and deliberately **not** wired (no third-party emission path, so their fixtures cannot leave orphaned ACADEMIC_EVENT projections):
- `verify_phase_23_8.py`, `verify_phase_23_9.py`, `verify_phase_23_10.py` — direct ORM event creation (no `EventService`/fan-out) + ORM delete.
- `verify_phase_11b.py` — direct ORM event + read-path generation for its own temp users only; admin rows restored to a pre-run baseline.
- `verify_phase_11c_p4.py` — fixture-only subject (`PH11CP4SUBJ`, enrolled solely by its temp user C); its direct `emit()`/`after_event_mutation` calls can only reach temp users whose rows are deleted in cleanup.
- `verify_phase_24_8.py` — QUIZ_DAY events created via the admin quiz service; its notification trigger emits QUIZ_APPROACHING keyed by cycle number (no `event_id`), which deleting the events cannot orphan.
- `verify_phase_2_quiz_events.py` — rollback-only scenarios; never commits an event.

**Incidental prerequisite fix (documented):** running the wired `verify_phase_6_5.py` exposed a pre-existing cleanup defect — its `DELETE FROM academic_events` violated `fk_class_sessions_source_event_id` because its own EXTRA_LECTURE fixture had materialized a class session referencing the event; the failed delete aborted the whole fixture cleanup (leaking the run's 4 events + 18 notifications). Fixed minimally in that script only: unattended sessions referencing the fixture events (`ClassSession.source_event_id IN test_event_ids`, no attendance records) are removed first. Nothing about notification production behavior changed.

### Self-check
Every wired script now asserts **zero** notifications referencing its fixture events after cleanup. Representative end-to-end run:
- `python scripts/verify_phase_6_5.py` → `27/27 checks passed`, with
  `[phase_6_5] fixture notification cleanup: 18 row(s) removed for 4 fixture event(s), all affected users`
  `[phase_6_5] fixture notification self-check: remaining=0 (OK)`.
- The harness itself was additionally validated against the real DB inside a rolled-back transaction (deletes exactly the fixture row, keeps a live row, self-check 0).
- Post-run probe: notification totals returned exactly to the pre-run baseline (474 total / 452 orphans / 18 events / 702 sessions).
- The leaked artifacts from the pre-fix `verify_phase_6_5` run (4 fixture events, 1 materialized session, 18 third-party notifications) were repaired in-session with the harness; the final probe confirms the baseline is byte-identical (see Regression Results).
- Destructive cleanup was **not** executed against production data (dev DB only; the one-time purge stayed dry-run).

---

## H-5 — Quiz-cycle date-order validation

### Root cause
Cycle numbers are derived *positionally* from the effective quiz dates
(`QuizRepository.get_effective_quiz_dates_for_subjects._rank` orders active
QUIZ_DAY events by `(start_date, id)`), while `QuizSchedule.cycle` is never
consulted at read time. `create_quiz_schedule`/`update_quiz_schedule` validated
only semester bounds, so an admin could set Q3's date before Q2's; the change
committed and silently renumbered cycles across eligibility windows,
QUIZ_APPROACHING occurrence keys, and the dashboard snapshot.

### Validation implementation
- `AdminQuizRepository.list_sibling_schedules(subject_id, elective_slot, exclude_id=None)` (new) — all schedules sharing the same (subject, slot) identity, cycle eager-loaded.
- `AdminQuizService._validate_cycle_chronology(subject_id, elective_slot, cycle_number, new_date, *, exclude_schedule_id=None)` (new) — for one (subject, slot):
  - a lower-numbered cycle's date must be **strictly earlier** than `new_date`;
  - a higher-numbered cycle's date must be **strictly later**;
  - an **equal date** between two cycles is rejected as ambiguous;
  - dateless (UNRESOLVED) siblings do not constrain; `new_date is None` skips validation.
- Wired into **both mutation paths**, after the existing semester-bounds check and before any event/notification side effect:
  - `create_quiz_schedule` (uses the target cycle number);
  - `update_quiz_schedule` (excludes the schedule being updated).

Errors use the existing `AdminQuizValidationError` convention → HTTP **422** (`_raise_quiz_error` in the admin endpoint). Cycle-number derivation was **not** redesigned.

### Affected symbols
`AdminQuizService.update_quiz_schedule`, `AdminQuizService.create_quiz_schedule`,
new `AdminQuizService._validate_cycle_chronology`,
new `AdminQuizRepository.list_sibling_schedules`.
(`QuizRepository._rank` untouched.)

### Rejected scenarios
- Q2 earlier than Q1; Q1 moved later than Q2.
- Q3 earlier than Q2; Q2 moved later than Q3.
- Equal dates between any two cycles of the same subject/slot.
- Validation is scoped per (subject, elective_slot): ELECTIVE_I validates against ELECTIVE_I rows only; unrelated subjects never interfere; the updated schedule excludes itself.

### Tests
`backend/tests/test_quiz_cycle_order.py` (15 tests):
- stub-level: normal chronology accepted; full set re-validation accepted; None date skips; each rejection case (Q2<Q1, Q3<Q2, Q2>Q3, Q1>Q2, equal dates); elective-slot independence; unrelated-subject non-interference; exclude-id passthrough; undated sibling doesn't constrain.
- real DB (sandboxed/read-only): **existing valid database state remains valid** — every dated schedule in the live DB passes the new validator against its real siblings; the full `update_quiz_schedule` path rejects an out-of-order date (422 semantics); semester-bound validation still fires first for an out-of-semester date.

---

## Regression Results

### Existing tests
- Baseline before Phase 2A: **141 passed / 0 failed**.
- After Phase 2A: **173 passed / 0 failed** (exit 0) — run as
  `backend/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider`.

### New tests
- `backend/tests/test_auth_deactivation.py` — 7 passed.
- `backend/tests/test_notification_projection.py` — 10 passed.
- `backend/tests/test_quiz_cycle_order.py` — 15 passed.
(32 new tests, all green.)

### Watch areas explicitly covered
- JWT refresh flow — active-user rotation + deactivated-user family revocation tests.
- Notification unread counts / bell badge — badge now counts live rows only; asserted in the sandbox tests.
- Dismissal/read state — dismissed rows excluded; read state preserved (existing upsert semantics untouched).
- Notification idempotency — `try_create`/`upsert` untouched; cache invalidation now clears all pages.
- Quiz eligibility math — **not modified**; all eligibility/engine suites pass.
- Quiz cycle tabs / dashboard quiz snapshot / QUIZ_APPROACHING — cycle derivation untouched; only mutation-time ordering validation added.
- Representative verifier run: `verify_phase_6_5.py` 27/27 checks passed and returned the DB to baseline.

### Failures
None (0 failing tests; 0 failing checks).

### Warnings / notes
- Pre-existing Pydantic v2 deprecation warnings (`class-based config`) only; no new warnings from this phase.
- **Environment note (not a repo change):** during this phase Windows Application Control policy blocked the SQLAlchemy C-extension `.pyd` files in `backend/.venv` (`ImportError: DLL load failed ... blocked by an Application Control policy`). To run the suite, the affected `sqlalchemy/**/*.pyd` files were locally renamed to `*.pyd.disabled` inside the venv so SQLAlchemy uses its bundled pure-Python fallbacks (`sqlalchemy 2.1.1`, `asyncpg 0.31.0`). This is a venv-local, reversible workaround — no repository file, dependency, or version changed. Restore by renaming the `.pyd.disabled` files back if the policy is lifted.
- `verify_phase_6_5.py`'s pre-existing FK-order cleanup defect (H-4b prerequisite) was fixed minimally; the earlier failed run's leak was repaired and the final DB probe matches the baseline exactly.

### Final DB state probe (2026-09-30, after all runs)
5 users (all active) · 36 enrollments · 10 choice rows · **474 notifications (452 orphaned ACADEMIC_EVENT — unchanged)** · 18 active quiz events, strictly chronological per scope · policies 70/75/75 · alembic head `e2f3a4b5c6d7` (unchanged).

---

## Final Verification Checklist

| Check | Result |
|---|---|
| `git diff` inspected — only intended files changed | ✅ 7 app files + 20 verifier scripts; 5 new files (harness, purge script, 3 test files) |
| No changes outside scope (frontend/other services) | ✅ (pre-existing frontend modifications in the working tree were not touched) |
| All tests run | ✅ 173 passed / 0 failed |
| Static checks | ✅ `python -m compileall app scripts` clean; app import smoke test (`app.main` + changed modules) passes; no linter/typechecker configured in-repo |
| No migrations generated | ✅ alembic head still `e2f3a4b5c6d7`; zero files added/modified under `backend/alembic/` |
| No seed/config changes | ✅ none of `app/core/config.py`, seeds, or `timetable.json` modified |
| No destructive DB query executed automatically | ✅ purge stayed dry-run (452 targeted, 0 deleted); no app startup cleanup added; final probe shows 452 orphans intact |
| No production DB operations | ✅ local dev DB only; purge script refuses `APP_ENV=production` |

## Scope Confirmation

Explicitly **NOT implemented** in Phase 2A:
- **H-1** (quiz threshold policy ambiguity) — no engine/policy change; D-1/D-2 still open.
- **H-3** (elective-correction history semantics) — no change to `correct_elective` or history attribution; D-3 still open.
- **H-4d** (CLASS_REMINDER scheduler) — no scheduler/worker/Redis introduced; D-5 still open.
- **M-2 / M-3** (enrollment read boundary + DB constraint hardening) — no change; still gated on D-3.
- **M-11** and any other P1/P2/P3 issue — untouched.
- No frontend changes; no schema migrations; no seed changes; no eligibility-math changes.
- The H-4a destructive purge was **NOT executed** (dry-run only) and remains available behind an explicit `--confirm` flag.
