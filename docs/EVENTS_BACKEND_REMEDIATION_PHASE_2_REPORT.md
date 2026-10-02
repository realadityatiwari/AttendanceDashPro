# Events Backend Remediation — Phase 2 Report (EVT-001 + EVT-002)

**Date:** 2026-10-02
**Scope:** EVT-001 + EVT-002 ONLY — the ACADEMIC_EVENT notification lifecycle defects from `docs/EVENTS_BACKEND_DEEP_AUDIT_REPORT.md`. EVT-003 (Phase 1, uncommitted in the working tree) is preserved untouched.
**Mode:** Backend-only. No migrations, no schema changes, no frontend changes, no attendance/eligibility/calendar/session-sync changes, no retention policy, no orphan purge.

---

## 1. Objective

Make ACADEMIC_EVENT notifications accurately follow the lifecycle of their source AcademicEvent:

1. Active future event → its eligible projection may exist.
2. Deactivated event → its projection must no longer be live.
3. Future → past transition → the previously generated future-event notification must no longer be live.
4. Repeated deactivation/update is idempotent.
5. Unrelated notification kinds are untouched.
6. Attendance, eligibility, calendar, event-session synchronization, and event-ownership logic unchanged.

## 2. Original Defects and Root Cause

- **EVT-001** — `EventService.deactivate_event()` set `active = False` and never touched the notification layer (create/update call the post-commit trigger; deactivation called nothing). Soft-deleted events still EXIST as rows, so the inbox read filter (`_live_event_ref_clause` — "event row must exist") kept every recipient's "… on \<date\>" row live forever. Root cause: the notification lifecycle had an emission path but **no reconciliation path**.
- **EVT-002** — `update_event()`'s post-commit trigger `after_event_mutation` early-returns when the event is stale (`not event.active or event.end_date < institution_today()`). A future→past update therefore skipped emission AND left the previously generated future-event row live with its old date. Root cause: the same missing reconciliation path, plus the stale condition existing only as an inline early-return inside the emission trigger (no shared lifecycle predicate).

The read-filter mitigation (Phase 2A, H-4a) was structurally incapable of fixing either case: it excludes rows whose event row is GONE, not rows whose event is deactivated or past.

## 3. Exact Implementation

### 3.1 `backend/app/services/notification_service.py`

- **New module-level predicate `event_is_stale_for_notification(event, as_of) -> bool`** — `(not event.active) or (event.end_date < as_of)`. The single definition of "this event's projection is stale"; the emission trigger's early-return and the reconciliation both use it, so the emit side and the reconcile side can never diverge.
- `after_event_mutation` now uses that predicate for its early-return — **behavior-identical** (verified: the existing trigger/sweep verifiers stay green).
- **New `NotificationService.reconcile_event_notification(event) -> int`** — the in-transaction counterpart of the trigger:
  - no-op (returns 0) while the event is still active and future — legitimate future-event updates keep the existing post-commit refresh behavior;
  - when stale: removes EVERY recipient's ACADEMIC_EVENT row for the event via the new repository method, then invalidates the affected users' inbox TTL caches (the delete is by the projection's idempotency key `(kind=ACADEMIC_EVENT, occurrence_key=str(event.id))` — other events' rows and other kinds are never touched; no replacement notification is created);
  - **never commits** — it participates in the caller's transaction, so the event change and its notification reconciliation commit or roll back together (requirement D). Read-state is intentionally not preserved for removed rows: the projection only exists while its source condition holds, so a reactivated future event legitimately re-notifies through the normal trigger.

### 3.2 `backend/app/repositories/notification_repo.py`

- **`get_event_projection_user_ids(event_id) -> List[UUID]`** — owners of the event's projection rows (for cache invalidation).
- **`delete_event_projection(event_id) -> int`** — bulk `DELETE` of the event's ACADEMIC_EVENT rows across all users; **deliberately no commit** (caller-owned transaction). Uses the existing SQLAlchemy `delete()` abstraction — no raw SQL.

### 3.3 `backend/app/services/event_service.py`

- **`deactivate_event` (EVT-001):** inside the existing mutation `try` block (after `repo.flush()`, before the synchronizer and the single `commit()`), calls `reconcile_event_notification(event)`. Idempotent by construction (second call deletes zero rows); a no-op when the event has no projection; a rejection (EVT-003 guard) still precedes everything and reconciles nothing.
- **`update_event` (EVT-002):** the same call inside the mutation `try` block. The method's shared predicate decides: a future→future update is a no-op here (its projection is still refreshed by the unchanged post-commit trigger below the commit), while any update whose FINAL state is stale (future→past, active→inactive via PATCH, or further edits of an already-inactive event) reconciles in-transaction. The post-commit trigger remains for the future→future refresh — nothing about it changed except the shared predicate.
- `create_event` untouched (a created event has no projection to reconcile; the trigger skips stale finals exactly as before).

### 3.4 `backend/app/services/admin_quiz_service.py` (section E inspection)

- `_retire_quiz_event` now calls the same reconciliation right after `event.active = False` — inside `update_quiz_schedule`'s transaction (that method owns the single commit). Quiz-manager-created events carry no projection (Phase 11C behavior: the quiz manager never emits ACADEMIC_EVENT rows), so this is a no-op for them; it matters only for the adopted-standalone edge (a generically created QUIZ_DAY with a live projection whose identity a schedule later backs) — exactly the case required to preserve the EVT-001 invariant. No Quiz Manager redesign; the EVT-003 guard and the dedicated create/retire paths are untouched.

### 3.5 Not changed

- `GET /notifications` read endpoint and `_live_event_ref_clause` (the fix is at the projection layer, not the read layer — per the design constraint).
- The 452 legacy orphan rows (EVT-008), retention policy (D5), `emit`/`try_create`/`upsert` commit behavior (all still post-commit best-effort for the EMISSION path), CLASS_REMINDER/QUIZ/THRESHOLD kinds, push dispatch, cache TTL semantics (only invalidation added).

## 4. Notification Lifecycle — Before / After

| Event transition | Before | After |
|---|---|---|
| create (future, active) | trigger emits rows (post-commit) | unchanged |
| update future → future | trigger refreshes rows in place (post-commit) | unchanged |
| update future → past | trigger early-returns; **stale row stays live** | rows removed in-transaction |
| update active → inactive (PATCH) | trigger early-returns; **stale rows stay live** | rows removed in-transaction |
| deactivate | **no notification call at all; stale rows stay live** | rows removed in-transaction |
| update past → past | trigger early-returns; old rows (none) | reconcile no-op; still none |
| inactive event edited | trigger early-returns; nothing regains life | reconcile no-op; still nothing |
| reactivate (inactive → active future) | nothing (row stayed dismissed/live — broken) | post-commit trigger re-emits fresh rows (correct lifecycle correspondence) |
| quiz-manager retire | nothing; adopted standalone events left stale rows | reconciled in-transaction |

**Transaction behavior:** reconciliation runs inside the event mutation's existing transaction — flush → reconcile → synchronizer → single `commit()` (rollback on any failure). There is no "commit event, then commit notification" window. The EMISSION trigger remains post-commit best-effort by design (Phase 11C-P4) — only the RECONCILIATION is transactional, exactly as scoped.

## 5. Tests Added

`backend/tests/test_evt001_002_notification_lifecycle.py` — 12 tests, repo savepoint-sandbox conventions (`_RollbackSession`, synthetic `TX-*` chain with an enrolled recipient so no real push fires; dates derived from the live institutional clock):

| Test | Assertion focus |
|---|---|
| T1 | deactivate future event → its projection row removed; event inactive |
| T2 | deactivate an event with no projection (past-dated) → safe; deactivating an already-inactive event again → idempotent |
| T3 | double deactivation → idempotent; the other event's row and the recipient's total ACADEMIC_EVENT count unchanged |
| T4 | future → past update → row removed; dates updated; event stays active |
| T5 | future → future update → row kept (exactly one) and message refreshed with the new date |
| T6 | past → past update → no row created; fields updated |
| T7 | deactivated event edited (note + dates) → no live projection regains |
| T8 | same user's MUST_ATTEND / QUIZ_APPROACHING rows untouched by the reconcile |
| T9 | another event's ACADEMIC_EVENT row untouched |
| T10 | reconciliation visible in the SAME transaction pre-commit; post-rollback check proves nothing leaked past the transaction (single-commit property) |
| T11 | EVT-003 guard intact with the Phase 2 hook present; rejected create/deactivate mutate zero notifications/events/sessions |
| T12 | Quiz Manager ensure/idempotent/retire lifecycle works; retirement of an adopted standalone event reconciles its projection; retire of a projection-less managed event is a no-op |

**Result: 12/12 pass.** Phase 1's EVT-003 suite re-run: **8/8 pass** (T11/T12 above double as the cross-phase regression).

## 6. Validation Results

| Check | Result |
|---|---|
| Focused EVT-001/002 tests | ✅ 12/12 |
| Phase 1 EVT-003 tests (regression) | ✅ 8/8 |
| Full backend pytest | ✅ **191 passed / 2 failed** — the 2 are the documented pre-existing `test_ui_formula_text.py` frontend-text assertions (fail identically at the pristine baseline; unrelated to Events) |
| `verify_phase_11c_p4.py` (notification sweep/triggers) | ✅ 38/38 |
| `verify_phase_24_10.py` | ✅ 35/35 |
| `verify_phase_6_5.py` | ✅ 27/27 |
| `verify_phase_6_6.py` | ✅ 36/36 |
| `verify_phase_6_7.py` | ✅ 31/31 |
| `verify_cancellation_lifecycle_consistency.py` | ✅ 35/35 |
| `verify_phase_3_quiz_eligibility_propagation.py` | ✅ 26/26 |
| `verify_phase_2_quiz_events.py` | 12/15 — **3 pre-existing** data-drift failures (10 theory subjects vs 6 seeded; stale hardcoded expectations) — proven pre-existing in Phase 1 by pristine-tree stash run; identical failures here |
| `verify_events_correction.py` | 38 PASS / 2 FAIL + its own cleanup crash — **all pre-existing**: the same 3c/17d attendance-count drift failures appear in the PHASE 1 captured run (`/tmp/vec_with.txt`, recorded before this phase's diff existed), and the cleanup FK crash (fixture events vs `class_sessions.source_event_id`) was proven pre-existing in Phase 1 on the pristine tree |
| `verify_event_cancellation_propagation.py` | 23 PASS / 1 FAIL (0b data drift) + its own cleanup crash — **pre-existing** (identical pristine-tree result recorded in Phase 1) |
| Static checks | none configured for the backend; `py_compile` + app import clean |
| Frontend | untouched (no shared types affected; not run) |

The 3c/17d clarification matters: Phase 1's report recorded these two checks as "38 PASS + cleanup crash" without enumerating the FAILs — the Phase 1 capture shows they were already failing before any Phase 2 change existed. Neither phase's diff touches the attendance-count paths those checks read.

## 7. Database Safety / Baseline Restoration

Both crashing verifiers left residue, removed after each run with FK-safe, ownership-scoped deletes (their own naming contracts):

- `VerifyEventsCorrection …` fixture events + their sessions/records/outcomes/notifications,
- `ECF_TMP%` temp users + their enrollments/records/notifications and the past-dated leftover CLASS_CANCELLED event.

**Final DB state verified equal to the pre-validation baseline:** 18 academic_events (18 active QUIZ_DAY), 0 temp users, 0 session/source-event residue, ACADEMIC_EVENT notifications back to exactly the 452 legacy orphans (EVT-008 — deliberately NOT purged), other kinds at their normal drifted projection counts (subject-keyed, refreshed in place by the verifiers' attendance mutations — not event-linked).

## 8. Boundary Verification

- `git status`: 7 modified backend files (4 from Phase 1 — byte-identical to their Phase 1 state — plus `notification_repo.py`, `notification_service.py`, `admin_quiz_service.py`), 3 untracked docs, 2 untracked test files. No frontend, no alembic, no schema files.
- EVT-003 intact: Phase 1 suite 8/8; T11/T12 assert the guard and quiz-manager paths with the Phase 2 hook present; `AdminEventService`/`events.py`/`admin.py` untouched by Phase 2.
- No behavior change for: emission recipients, message formats, `emit` idempotency, push, inbox read filters, pagination, CLASS_REMINDER/QUIZ/THRESHOLD kinds, retention.

## 9. Remaining Events Audit Findings (open)

- **EVT-004** missing DB unique constraints/locks (duplicate events/sessions race) — HIGH-value next step; the only finding requiring a migration.
- **EVT-005** CLASS_REMINDER unreachable (no scheduler; sweep has no production caller) — needs a product decision first.
- **EVT-006/007/008/009/010** (indexes, pagination, orphan purge, deterministic quiz-event lookup, input limits) — untouched.
- **EVT-011/013/014 potential risks**, EVT-012 partial-broadcast hazard — untouched.
- **D1–D7 product decisions** — untouched (D4's docstring and D6's quiz-manager emission asymmetry remain as documented).
- Pre-existing verifier-infrastructure issues (harness cleanup vs `source_event_id` FK; stale data-dependent expectations in `verify_phase_2_quiz_events` / `verify_events_correction` / `verify_event_cancellation_propagation`) — documented, not repaired.

The Events backend is NOT fully fixed. EVT-001, EVT-002, and EVT-003 are remediated; everything else remains open per the audit.

## 10. STOP

EVT-001 + EVT-002 implemented and validated. Nothing committed. No other findings implemented.
