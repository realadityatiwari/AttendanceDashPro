# Events Backend — Post-Remediation Integrity Review

**Date:** 2026-10-03
**Scope:** The complete Events + Notifications backend after the completion of remediation through EVT-005 (Phases 1–5 of `docs/EVENTS_BACKEND_DEEP_AUDIT_REPORT.md` remediation). This is a dedicated integrity review: it re-validated every Phase 1–5 implementation against the actual code, the actual database, and actual end-to-end flows — **not** against the phase reports' claims.
**Source of truth:** `docs/EVENTS_BACKEND_DEEP_AUDIT_REPORT.md`, the Phase 1/2 reports, current repository state (`main @ 10b7036` + working tree), and the live dev PostgreSQL database (PG 16.15, `b9c0d1e2f3a4` applied).
**Mode:** Forensic audit first (read-only), then targeted fixes for confirmed issues, then full regression testing, then exact dev-DB restoration. Nothing is committed.

---

## 1. Executive Summary

The remediation work itself is **substantively correct**: the EVT-003 quiz-manager guard is properly enforced at the domain layer, the EVT-001/002 notification reconciliation is precisely keyed and transactional, and the EVT-004 natural-key indexes encode exactly the identities the application maintains (verified predicate-by-predicate against every legitimate `class_sessions` creation path). All committed test suites pass.

However, the review found **six confirmed issues** that the phase reports did not surface — because two of the three "completed" later phases were never actually finished, and because the pytest sandbox masked a production-only failure mode:

1. **EVT-005 was a phantom implementation** (P1): configuration flags claiming "runs as a background asyncio task in the FastAPI lifespan" were committed, but the scheduler file, the test file, and even the Phase 4 report are all **0-byte empty files**, and `main.py` has no lifespan at all. CLASS_REMINDER remained unreachable in production exactly as the deep audit found it. **Implemented now** per the committed config contract.
2. **A real production 500** (P2): any `PATCH /api/v1/events/{id}` whose *final* state collides with a managed QUIZ_DAY (or any EVT-004 unique identity) returned a raw `IntegrityError` → HTTP 500 instead of the designed 409/403/422. The mutation-then-guard ordering in `update_event` plus SQLAlchemy's default **autoflush** flushed the mutated row into the new unique indexes *during the guards' own queries*. The pytest suite never caught this because its sandbox sets `session.autoflush = False`; production `get_db` does not. Caught by a live end-to-end flow run; **fixed** by suspending autoflush across the guard phase.
3. **Three verifier breakages** introduced by the EVT-004 migration (Phase 3) — `verify_phase_11a.py`/`verify_phase_11b.py` (fixtures model an impossible production state), `verify_phase_11b.py`'s frozen alembic-head pin, and `verify_phase_2_quiz_events.py`'s dedup fixture. **All repaired.**
4. **Verifier residue in the dev DB** left by the remediation-day validation runs (their cleanup crashed): one attended quiz-day-shaped session for BCS-503 @ 2026-07-31 with an attendance record, plus four derived notification rows. **Removed** in Phase H with exact captured ids.

Two additional empty files committed by the remediation (`docs/EVENTS_BACKEND_REMEDIATION_PHASE_3_REPORT.md`, `..._PHASE_4_REPORT.md`) remain empty placeholders; this review's report documents what Phases 3–4 actually shipped.

**Final state: 206 pytest passed / 2 documented pre-existing failures; all green verifier suites fully green; the three verifiers with documented pre-existing failures reproduce their exact documented baselines; the new 27-check end-to-end flow verifier passes 27/27; the dev DB is restored to its exact pristine baseline (18 events / 702 sessions / 54 records / 482 notifications / 7 users; the 452 legacy orphan notifications untouched).**

---

## 2. Issues Discovered (final inventory)

| # | Issue | Severity | Root cause | Introduced by | Fixed? |
|---|-------|----------|-----------|---------------|--------|
| R1 | **EVT-005 phantom implementation.** `config.py` gained `CLASS_REMINDER_SWEEP_*` flags with a comment claiming "Runs as a background asyncio task in the FastAPI lifespan"; `notification_scheduler.py` (0 bytes), `test_evt005_class_reminders.py` (0 bytes), Phase 3/4 reports (0 bytes); `main.py` has no lifespan; no production caller of `regenerate_user_notifications`. CLASS_REMINDER stayed dead; operators reading the config would believe the sweep runs every 60 min. | **P1** | Phase 4/EVT-005 committed configuration + placeholders without the implementation | Phases 1–5 (EVT-005) | **Yes** — scheduler implemented (`app/services/notification_scheduler.py` + lifespan in `app/main.py` + preference query + 5 tests) |
| R2 | **HTTP 500 on final-state event conflicts.** `update_event` mutated the event row in memory *before* the final-state guards; with default autoflush, the guards' own queries flushed the mutated row into `uq_academic_events_quiz_day_identity` (and friends) → raw `IntegrityError` → 500, instead of the EVT-003 final-state 409 / duplicate 409 / 422. | **P2** | Phase 3's DB indexes × Phase 1's mutate-then-guard ordering × production autoflush; pytest sandbox hid it (`autoflush = False`) | Phases 1–5 (interaction) | **Yes** — guard phase wrapped in `with self.db.no_autoflush:`; proven fixed by live flow 5 (was crash → now 409) |
| R3 | `verify_phase_11a.py` / `verify_phase_11b.py` crash at fixture insert: two same-(subject, date) LECTURE, non-extra, entry-NULL sessions (one cancelled) violate `uq_class_sessions_quiz_day_subject_date`. Production code never creates that shape (only quiz-day sessions are entry-NULL non-extra LECTURE, and they are never cancelled). | **P3** | EVT-004 migration vs. Phase-11-era fixture assumptions | Phase 3 (EVT-004) | **Yes** — cancelled fixture session changed to TUTORIAL (checks key on session id; semantics preserved; both scripts run to completion) |
| R4 | `verify_phase_11b.py` check 1 asserts the alembic head is frozen at `e1f2a3b4c5d6` (Phase 14D) — fails since the EVT-004 migration `b9c0d1e2f3a4` landed. | **P3** | Phase 3 migration did not update the frozen head pin (house pattern from commit `34dcaff` requires it) | Phase 3 (EVT-004) | **Yes** — pin updated to `b9c0d1e2f3a4` |
| R5 | `verify_phase_2_quiz_events.py` check 7 **crashed** (was 12/15 in Phases 1–2): it fabricates a same-identity partial duplicate (BCS-501, start 09-17, wider range) that `uq_academic_events_quiz_day_identity` now (correctly) rejects. | **P3** | EVT-004 index vs. the old eligibility-layer dedup fixture | Phase 3 (EVT-004) | **Yes** — check rewritten to assert the new DB-authoritative contract (insert rejected in a savepoint; effective dates unchanged); script back to its documented **12/15** pre-existing baseline |
| R6 | **Remediation-day verifier residue in the dev DB**: one attended quiz-day-shaped session (BCS-503 @ 2026-07-31, created 2026-10-02 11:29 UTC by `verify_events_correction.py` check 17) + its ATTENDED record + four derived `MUST_ATTEND`/`SAFE_SKIP` rows created the same minute for BCS-502/BCS-503. The phase reports' "no session/source-event residue" check missed it because quiz-day-shaped sessions carry **no** `source_event_id`. | **P3** | The verifiers' documented cleanup crash (pre-existing class) during remediation validation, plus an incomplete residue check | Remediation validation runs | **Yes** — removed in Phase H with exact captured ids (`scripts/restore_dev_baseline.py`) |

Pre-existing failures that were **reproduced and deliberately left unchanged** (see §13 for the causality evidence): the 2 `test_ui_formula_text.py` failures; `verify_phase_2_quiz_events.py` checks 3/4/5 (dev-data drift); `verify_events_correction.py` cleanup crash; `verify_event_cancellation_propagation.py` check 0b + cleanup crash; `verify_phase_11a.py` checks 8/15/16/17 and `verify_phase_11b.py` checks 3/6 + `StopIteration` (stale Phase-11-era "GET generates projections" expectations vs. the Phase 11C-P4 read-only inbox, plus data drift — **proven pre-existing**, §13).

---

## 3. Phase A/B — What Was Audited (forensic coverage)

Every file in the review's mandated list was read in full and cross-checked against the DB:

- **Events:** `models/event.py`, `services/event_service.py`, `admin_event_service.py`, `admin_quiz_service.py`, `event_registry.py`, `event_session_service.py` (synchronizer), `repositories/event_repo.py`, `calendar_repo.py`, `session_repo.py`, `admin_quiz_repo.py` (`find_quiz_day_event`), `quiz_repo.py` (effective dates), endpoints `events.py`, `admin.py` (events + quiz sections), `notifications.py`, `deps.py` (`get_db`), `engines/practical_occurrence.py`, `engines/calendar_engine.py` (via registry/synchronizer).
- **Notifications:** `notification_service.py` (predicate, `reconcile_event_notification`, `emit`, sweep, `_class_reminders`), `notification_repo.py` (`delete_event_projection` precision, read filters), `preference_repo.py`, model + enums, push dispatch seam.
- **Database (live, read-only):** alembic version = `b9c0d1e2f3a4`; all five `uq_*` indexes present; duplicate probes for every new identity — all empty; orphan/stale/dangling probes — clean except the findings in §2; PG 16.15 (supports `NULLS NOT DISTINCT`).
- **Tests:** all three committed EVT suites read and re-run; `test_extra_lifecycle_foundation` / `quiz_cycle_order` conventions checked for the pinned multi-extra contract.
- **Deployment:** `render.yaml`, `backend/Dockerfile`, `docker-compose.yml`, `start-dev.ps1`. Production = single uvicorn web process, no worker, no cron. This drives the R1 fix's design (see §9).

---

## 4. Phase C — Challenges to the Previous Implementations (results)

1. **EVT-003 QUIZ_DAY ownership guard — VALIDATED.** `EventService` enforces it prospectively on create, on the OLD state and FINAL state of update, and on deactivate — before any flush, sync, commit, or notification side effect. `AdminEventService` delegates to the single resolver; the Quiz Manager never routes through `EventService` (full ownership preserved — verifier `phase_24_10` 35/35). Live flows: generic create/re-date/deactivate of a managed QUIZ_DAY all → 409; type-change INTO a managed identity → 409 (after the R2 fix); Quiz Manager create/retire unaffected. The schedule-backed identity (`is_quiz_schedule_managed`) matches `find_quiz_day_event` and the seed contract. No legitimate Quiz Manager operation is blocked (its paths bypass `EventService` entirely).
2. **EVT-001/002 notification reconciliation — VALIDATED.** Deletion is keyed exactly `(kind=ACADEMIC_EVENT, occurrence_key=str(event.id))` across ALL users — other events and other kinds are never touched; other events' rows proven untouched by tests T3/T9; future→future keeps and refreshes (flow 10b); future→past / deactivation removes in-transaction (flows 8/9); reactivation re-emits through the unchanged post-commit trigger (flow 11); quiz-manager retirement reconciles adopted standalone projections (test T12); repeated reconciliation is idempotent; `occurrence_key` semantics are consistent across trigger (`str(event.id)`), sweep (`str(item.event_id)`), and reconcile. Read-state is intentionally not preserved for removed projections (documented product semantics). Cache invalidation precedes commit; the tiny invalidate-before-commit window can only serve a ≤60 s TTL-stale snapshot — benign.
3. **EVT-004 database constraints — VALIDATED, predicate #5 challenged explicitly.** Every legitimate `class_sessions` creation path was traced: baseline expansion (entry-bound), synchronizer scheduled creations (entry-bound), extras (`is_extra=true`, excluded), quiz-day bucket + `materialize_quiz_day_sessions.py` (the intended shape), mid-sem designation (updates only), laboratory service (read/designate only). **No production path can match `timetable_entry_id IS NULL AND is_extra = false AND class_type = 'LECTURE'` except quiz-day occurrences** — the only rows that ever violated the predicate were Phase-11-era *verifier fixtures* (R3). `NULLS NOT DISTINCT` matches the app guard's NULL-equality for `elective_slot`; the partial `WHERE active` makes deactivation free the identity; global-range and (entry, date) / (source_event, date) identities mirror the application guards exactly. The known multi-day-QUIZ_DAY edge is documented in §11 (no silent corruption possible).
4. **EVT-004 IntegrityError handling — VALIDATED (one narrowing fix).** `is_evt004_unique_violation` requires SQLSTATE 23505 **and** an EVT-004 index name in the message — unrelated unique violations and all other integrity failures propagate untouched (mapped 500s, as before). asyncpg's `pgcode` propagation was verified in the SQLAlchemy 2.x asyncpg dialect (it aliases `sqlstate` → `pgcode`) and proven live (T2/T7 assert it on real races). Rollback happens before the session is reused (T3 asserts post-rollback usability); the rollback undoes event + session + notification-reconcile atomically. **Fix applied (part of R2's area):** session-index violations now translate to a distinct, truthful conflict message ("class sessions changed concurrently; retry") instead of the misleading "identical active event" wording; `AdminQuizService` keeps its own consistent translation.
5. **EVT-005 — FAILED the challenge; now implemented (R1).** Before this review, "scheduler code exists" was false: no scheduler existed anywhere, and the deployment could not execute one. See §9.
6. **EventSessionSynchronizer — VALIDATED.** Repeated synchronization is idempotent (flow 13; T9/T10 deactivate/reactivate cycles under the constraints produce exactly one provenance row each; attendance rides along untouched). Under the new indexes, single-writer reconciliation behaves exactly as before; **only true concurrent races** hit the indexes, and those are explicitly translated to 409 (the EVT-004 design trade-off — duplicate canonical rows were the alternative). Attended-extra preservation/restoration is constraint-safe (T9/T10).
7. **Transaction boundaries — VALIDATED.** Mapped: request → service (guards, no flush) → explicit flush → notification reconcile (in-transaction) → synchronizer (in-transaction, flush-only) → single commit → post-commit trigger (best-effort, isolated). No nested commits on the mutation paths; `emit()`'s per-row commit is only reachable post-commit; notification reconciliation is rolled back with the event on failure; cache invalidation before rollback is benign (TTL-bounded). `AdminQuizService` commits exactly once per mutation; its `_ensure_quiz_event` rollback-on-race aborts the whole quiz mutation atomically (correct).

---

## 5. Phase D — Database Integrity Results

Read-only probes (before any cleanup):

| Check | Result |
|---|---|
| Duplicate active QUIZ_DAY identity / global range identity | none |
| Duplicate `class_sessions` (entry, date) / (source_event, date) / quiz-day shape | none |
| Orphan `notifications.event_id` | 452 (the documented legacy set — untouched throughout) |
| Live ACADEMIC_EVENT rows pointing at inactive or past events | **0** (EVT-001/002 fix effective at the data level) |
| Orphan `class_sessions.source_event_id` / `timetable_entry_id` | 0 |
| Active QUIZ_DAY events missing their quiz-day session | none |
| Quiz-day-shaped session with **no** active QUIZ_DAY event backing | **1** — BCS-503 @ 2026-07-31, attended, created 2026-10-02 11:29 UTC → R6 (remediation-day verifier residue, not seeded data, not pre-existing) |
| Notifications created during remediation day | 4 (`MUST_ATTEND`/`SAFE_SKIP` for BCS-502/BCS-503, derived from that residue run) → R6 |

Post-restoration (Phase H): every count matches the pristine baseline exactly — `academic_events` 18, `class_sessions` 702, `attendance_records` 54, `notifications` 482, `users` 7, `subjects` 13, `quiz_schedules` 18, `quiz_cycles` 3, **452 legacy orphans untouched**, 0 temp chains. The restoration tooling is reproducible: `backend/scripts/restore_dev_baseline.py` (prints before/after against the pristine baseline and refuses "COMPLETE" on any drift).

No pre-existing corruption was found, so no seeded data was modified. The only rows removed were (a) verifier residue created during the remediation/review runs themselves, scoped by exact captured ids / temp-chain ownership / a strict created-at window, and (b) nothing else.

---

## 6. Phase E — End-to-End Flow Results (20 flows, 27 checks)

New verifier `backend/scripts/verify_post_remediation_flows.py` (HTTP-level via the real app + real DB, synthetic `TXIR-*` chain, FK-safe cleanup, baseline assertion). Final run: **27/27 PASS**. Representative records (HTTP / session / notification mutations):

| Flow | Result | Side effects verified |
|---|---|---|
| 1. Create normal event | 201 | 1 extra session materialized; 1 ACADEMIC_EVENT projection for the enrolled student |
| 2. Managed QUIZ_DAY via generic path | 409 | no event row created |
| 3. Managed QUIZ_DAY via Quiz Manager | created | exactly one quiz-day session (Option A) |
| 5. Convert normal event → managed | **409** (was 500 — R2) | no mutation persisted |
| 6./7. Re-date / deactivate managed via generic path | 409 / 409 | state unchanged |
| 4./10. Edit; future→future re-date | 200 / 200 | projection kept exactly once, message refreshed to the new date |
| 13. Repeated synchronization | idempotent | still exactly one extra |
| 18. Cancellation propagation | 201 | timetable occurrence cancelled; extra unaffected; deactivation restores exactly |
| 9. Future→past update | 200 | projection removed in-transaction |
| 11. Reactivation | 200 | projection re-emitted |
| 8. Deactivate future event | 200 | projection removed for ALL users; unattended extra deleted |
| 14. Concurrent duplicate event creation | loser 409 | exactly one committed row (race winner removed by the script) |
| 15. Concurrent duplicate session materialization | loser rejected by DB | exactly one canonical row |
| 19. Quiz eligibility propagation | effective date == managed QUIZ_DAY date | retire via Quiz Manager drops it, deactivates the event, removes the unattended quiz-day session |
| 16./17. CLASS_REMINDER sweep (scheduler) | generated for the opted-in student's uncancelled in-window session; cancelled excluded; repeated sweep adds no rows and no pushes | — |
| 20. Inbox | 200 with unread metadata, persisted rows only | — |

---

## 7. Fixes Applied (exact files, minimal rationale)

| File | Change | Why |
|---|---|---|
| `backend/app/services/event_service.py` | `update_event`: field application + slot invariants + final authorization + EVT-003 final-state guard + validation + duplicate pre-check wrapped in `with self.db.no_autoflush:` (R2). `create_event`/`update_event`: session-index violations translate to a truthful "class sessions changed concurrently" conflict message (§4.4). | Guards must observe DB state without flushing the in-memory mutation; the only flush remains the explicit one inside the transactional try where races are translated. |
| `backend/app/services/notification_scheduler.py` | **Implemented** (was 0 bytes): `run_class_reminder_sweep_once` (opt-in audience via `PreferenceRepository`, per-user session + per-user error isolation, push-seam and session-factory and audience seams, overlap guard, idempotent by `emit`'s ON CONFLICT) + `_class_reminder_loop` + idempotent `start_/stop_class_reminder_scheduler` honoring `CLASS_REMINDER_SWEEP_ENABLED` / `_INTERVAL_MINUTES` / `_STARTUP_DELAY_SECONDS` (R1). | The committed config contract declared exactly this; the audit's remediation order required EVT-005. |
| `backend/app/main.py` | FastAPI **lifespan** that starts the scheduler on startup and stops it on shutdown (R1). | Production runs `uvicorn app.main:app` with no other scheduler/worker; without the lifespan, CLASS_REMINDER stays unreachable. |
| `backend/app/repositories/preference_repo.py` | `get_class_reminder_user_ids()` (read-only). | The sweep's audience = users opted into class reminders (preference row absent = documented default off). |
| `backend/app/repositories/event_repo.py` | `EVT004_SESSION_CONSTRAINTS` + `is_evt004_session_violation()`. | Lets the 409 translation tell a reconciliation race from a duplicate event truthfully. |
| `backend/tests/test_evt005_class_reminders.py` | **Implemented** (was 0 bytes): 5 tests — opt-in generation + non-opt-in silence + push exactly once; repeat-sweep idempotency (no new rows, no re-push); cancelled/marked-session exclusion; start/stop lifecycle (single start, flag-gated, clean stop); **real app lifespan wiring** test. | The committed-but-empty test file; covers the R1 fix at the same level as the other EVT suites. |
| `backend/scripts/verify_phase_11a.py`, `verify_phase_11b.py` | Cancelled fixture session LECTURE → TUTORIAL with explanatory note (R3). | The former fixture models a state production can never produce; the checks key on session id, so semantics are unchanged. |
| `backend/scripts/verify_phase_11b.py` | Alembic head pin `e1f2a3b4c5d6` → `b9c0d1e2f3a4` (R4). | House pattern (commit `34dcaff`) — each migration updates the pin. |
| `backend/scripts/verify_phase_2_quiz_events.py` | Check 7 rewritten: the partial duplicate is now asserted to be **rejected** by the identity index inside a savepoint, with effective dates unchanged (R5) + `IntegrityError` import. | The old fixture fabricates a state the DB now forbids; the new contract is strictly stronger. |
| `backend/scripts/verify_post_remediation_flows.py` | **New** (27 checks) — the Phase E evidence. | — |
| `backend/scripts/restore_dev_baseline.py` | **New** — reproducible Phase H restoration (temp-chain purge + captured remediation-day residue removal + review-window purge + baseline assertion). | — |

No frontend, attendance-calculation, eligibility-calculation, or notification-architecture changes were made. No historical migration was modified.

---

## 8. Transaction Implications

- The R2 fix changes **when** the mutated event row first reaches the database (explicit flush inside the try instead of an uncontrolled autoflush mid-guard). Guard failures (403/404/409/422) now persist nothing *by construction* rather than by luck; successful updates commit exactly as before (single commit; reconcile + synchronizer inside it).
- The scheduler runs entirely outside request transactions: one session per user per pass, committed per user — a failing user rolls back alone and never blocks the pass or the task.
- No other transaction boundaries moved.

## 9. Scheduler / Deployment Implications

- The CLASS_REMINDER scheduler now **actually runs in the deployed process**: `uvicorn app.main:app` executes the lifespan (Dockerfile CMD; Render web service; default `UVICORN_WORKERS=1`). There is no separate worker to deploy and no cron to configure; `CLASS_REMINDER_SWEEP_ENABLED=false` starts the app without it.
- Duplicate reminders remain impossible under any worker count: emission is `INSERT … ON CONFLICT DO NOTHING` keyed `(user_id, kind, occurrence_key)`; losers take the refresh path which never re-pushes. Overrunning passes skip the next tick via an in-process guard.
- Timezone and lead time are unchanged: the sweep calls the existing `_class_reminders` builder (`institution_today()`, Asia/Kolkata; window = current day → institutional week end; unmarked, non-cancelled sessions only; deactivated extras always carry records and are therefore excluded; past sessions are outside the window).
- **EVT-004 migration deployment note:** `b9c0d1e2f3a4` uses `NULLS NOT DISTINCT` → **PostgreSQL ≥ 15 required**. Dev runs 16.15; production (Supabase/Render) must be confirmed ≥ 15 before applying, and the migration self-audits duplicates and refuses to apply over violating data.

## 10. Tests (Phase G)

| Suite | Result |
|---|---|
| Full backend pytest | **206 passed / 2 failed** — both `test_ui_formula_text.py` frontend-text assertions, documented pre-existing since before the remediation (fail on the pristine tree; frontend files untouched by Phases 1–5) |
| EVT-003 suite (`test_evt003_quiz_managed_guard.py`) | 8/8 |
| EVT-001/002 suite (`test_evt001_002_notification_lifecycle.py`) | 12/12 |
| EVT-004 suite (`test_evt004_uniqueness_constraints.py`, incl. real two-connection races) | 11/11 |
| EVT-005 suite (`test_evt005_class_reminders.py` — new) | 5/5 |
| `py_compile` on all changed files + full `import app.main` | clean |

## 11. Verifier Results (Phase G, live DB)

| Verifier | Result | vs. documented baseline |
|---|---|---|
| `verify_phase_24_10.py` (admin guard) | **35/35** | green |
| `verify_phase_6_5.py` (event security matrix) | **27/27** | green |
| `verify_phase_6_6.py` (event→engine sessions) | **36/36** | green |
| `verify_phase_6_7.py` (calendar/events freeze) | **31/31** | green |
| `verify_cancellation_lifecycle_consistency.py` | **35/35** | green |
| `verify_phase_3_quiz_eligibility_propagation.py` | **26/26** | green |
| `verify_phase_11c_p4.py` (triggers + explicit sweep) | **38/38** | green |
| `verify_phase_2_quiz_events.py` | **12/15** (was crashing) | exactly the documented 3 pre-existing data-drift failures (checks 3/4/5: 10 theory subjects vs 6 seeded; stale current-cycle expectation) |
| `verify_events_correction.py` | **39 checks PASS**, then its own cleanup crash | pre-existing crash class (fixture events vs `class_sessions.source_event_id` FK), documented in Phase 1; residue removed afterwards |
| `verify_event_cancellation_propagation.py` | checks 1–22 area PASS, 0b data-drift FAIL + own cleanup crash | pre-existing (documented); residue removed afterwards |
| `verify_phase_11a.py` | **15/19** (was crashing) | the 4 failing checks are **proven pre-existing** (§13) |
| `verify_phase_11b.py` | check 1 fixed (head pin); remaining fails + `StopIteration` **proven pre-existing** (§13) | — |
| `verify_post_remediation_flows.py` (new) | **27/27** | — |

**Alembic validation:** single head `b9c0d1e2f3a4`; DB at head; a full `downgrade e2f3a4b5c6d7` → `upgrade head` cycle was executed during this review (for the §13 causality experiment) and completed cleanly, recreating all five indexes.

---

## 12. Phase H — Database Restoration

Final verified state (reproducible via `backend/scripts/restore_dev_baseline.py`):

| Table | Pristine baseline | Restored |
|---|---|---|
| academic_events | 18 | 18 |
| class_sessions | 702 | 702 |
| attendance_records | 54 | 54 |
| notifications | 482 | 482 |
| users | 7 | 7 |
| subjects | 13 | 13 |
| quiz_schedules | 18 | 18 |
| quiz_cycles | 3 | 3 |
| legacy orphan notifications | 452 | **452 (untouched)** |

Removed during restoration: the R6 remediation-day residue (exact captured ids) and the review's own verifier-run residue (temp `TXIR*`/`ECF*` chains and window-scoped rows) — no seeded data, no pre-existing rows, and no legacy orphans were touched. A pre-review `pg_dump` snapshot is kept at `backend/scripts/_work/integrity_review/baseline_pre_integrity_review.dump`.

## 13. Causality Proofs for "Pre-existing" Classifications

- **`verify_phase_11a` (4 failures) / `verify_phase_11b` (3 failures + `StopIteration`)** — Definitive experiment: the EVT-004 migration was downgraded (`alembic downgrade e2f3a4b5c6d7`), the working tree stashed so the ORIGINAL Phase-14E-era scripts ran, and both verifiers executed against the un-constrained database. They produced the **identical failures** (11a: checks 8/15/16/17 — 15/19; 11b: checks 3/6 + the same `StopIteration` at the same line). Root cause: the scripts encode Phase-11-era semantics ("GET /notifications generates projections") that were replaced by the Phase 11C-P4 read-only inbox, plus dev-data drift. The only remediation-introduced 11b failure was the frozen head pin (R4, fixed); the only 11a/11b crash was the R3 fixture collision (fixed). Database was re-upgraded to head afterwards and verified.
- **`test_ui_formula_text.py` (2 failures)** — Static assertions on frontend copy; the frontend files they read were last changed in commit `f8ccb69`, *before* the remediation commit; Phases 1–5 touched no frontend files. Phase 1 additionally recorded both failures reproducing on the pristine tree.
- **`verify_phase_2_quiz_events` checks 3/4/5** — Identical failure set (12/15) to the one recorded in the Phase 1 and Phase 2 reports, which proved it on a stashed pristine tree; this review's diff does not touch attendance/eligibility reads.

## 14. Remaining Known Audit Findings (unchanged, deliberately not implemented)

- EVT-006 (`academic_events` secondary indexes; bounded synchronizer fetch), EVT-007 (events list pagination/deterministic tiebreak), EVT-008 (452-orphan purge — **still deliberately untouched**), EVT-009 (resolved in practice by the EVT-004 identity index), EVT-010 (input limits / client-settable `active` on create), EVT-011 (out-of-span QUIZ_DAY), EVT-012 (per-row notification commits / partial broadcast), EVT-013 (same-priority tiebreak unification), EVT-014 (student reactivation of admin-withdrawn events).
- Product decisions D1–D7 unchanged.
- Pre-existing verifier-infrastructure defects (harness cleanup vs `source_event_id` FK; stale Phase-11 expectations in 11a/11b; data-drift-dependent expectations) — documented here and in Phases 1–2, not repaired (out of scope).

## 15. Documented Limitations of the Current Implementation (no fix — product-scope)

1. **Multi-day QUIZ_DAY.** The registry does not force `start_date == end_date` for QUIZ_DAY, while the EVT-004 identity and the quiz-manager contract key on the start date. Consequences (all bounded, none silent): a *generic* multi-day QUIZ_DAY *starting* on a schedule-backed date is already rejected by the EVT-003 guard (start == schedule date); a multi-day standalone QUIZ_DAY created *before* a schedule later claims the same start makes the quiz manager's `_ensure_quiz_event` fail with a 409 whose "concurrent mutation" wording is imprecise (it is really a stale wider-range event); eligibility dedupes per (subject, date) and the session bucket is set-based, so no eligibility shift can occur. Tightening the registry would be a new product rule (out of scope).
2. **Recipient-set changes on live events.** Moving an event's `subject_id` refreshes the projection for the *new* recipients but does not remove the row from *former* recipients (pre-existing gap noted in the deep audit's update-flow analysis; the reconcile handles stale *events*, not stale *recipients*). Unchanged by Phases 1–5 and by this review.

## 16. Unresolved Product Decisions

None new. D1–D7 from the deep audit remain open and untouched.

## 17. Git Status

All changes are **uncommitted** (per the task boundary):

- Modified: `backend/app/main.py`, `backend/app/services/event_service.py`, `backend/app/services/notification_scheduler.py`, `backend/app/repositories/event_repo.py`, `backend/app/repositories/preference_repo.py`, `backend/scripts/verify_phase_11a.py`, `backend/scripts/verify_phase_11b.py`, `backend/scripts/verify_phase_2_quiz_events.py`, `backend/tests/test_evt005_class_reminders.py`
- New: `backend/scripts/verify_post_remediation_flows.py`, `backend/scripts/restore_dev_baseline.py`, `docs/EVENTS_BACKEND_POST_REMEDIATION_INTEGRITY_REVIEW.md` (this file), `backend/scripts/_work/integrity_review/` (pre-review DB snapshot)

---

## 18. Which Previous Phases Were Validated vs. Corrected

- **Phase 1 (EVT-003): VALIDATED unchanged.** The domain guard, delegation, exception mapping, and quiz-manager preservation all hold on live flows and both verifier suites. (The R2 500 was a *Phase 3×Phase 1 interaction*, fixed in this review without altering the guard's semantics.)
- **Phase 2 (EVT-001/002): VALIDATED unchanged.** The shared stale predicate, in-transaction reconciliation, precise keying, and cache behavior all hold on live flows and the full lifecycle matrix.
- **Phase 3 (EVT-004): VALIDATED with corrections.** The five constraints are correct and safe for every production path; the review fixed three verifier casualties (R3, R4, R5), the production-only autoflush 500 the migration exposed (R2), and the conflict-message accuracy.
- **Phase 4/5 (EVT-005): NOT ACTUALLY IMPLEMENTED — implemented by this review (R1).** The phase left only configuration and empty files; the scheduler, its wiring, and its tests now exist and are verified end-to-end (flows 16/17 + 5 unit tests + lifespan test).
