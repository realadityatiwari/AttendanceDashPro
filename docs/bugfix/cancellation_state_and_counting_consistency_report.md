# Bug-Fix Report — Cancellation State Lifecycle & Attendance Counting Consistency

**Date:** 2026-08-22 · **Scope (owner-labelled Phase 12C bugfix):** canonical cancellation reversal + global applicability rule · **Status:** FIXED & VERIFIED · **No commit made**

---

## 1. Observed Bugs

1. Owner deactivated/removed the BCS-058 `CLASS_CANCELLED` events (15:49 UTC) — Track/History still showed both lectures CANCELLED (reverse transition missing).
2. Lecture counts in History / Attendance-Subjects did not consistently exclude cancelled occurrences from applicable denominators while cancellations were active.

## 2. Root Causes

**(a) Stale execution environment (trigger).** The dev backend (`uvicorn app.main:app --port 8080`, PID 21992/22360) started **09:07 UTC without `--reload`** — i.e., BEFORE the earlier propagation bugfix (~13:00 UTC) — so the owner's 15:49 deactivations ran pre-fix code whose `_reconcile_date` guard skipped ANY recorded session (including restoration). Proof: live-server fingerprint vs in-process on identical DB — BCS-058 lecture `{79, 6, 13}` (cancelled counted) vs `{77, 5, 12}` (excluded).

**(b) Genuine architectural gap (fixed here).** `EventService.deactivate_event` early-returned when the event was already inactive — reconciliation NEVER ran, so once state went stale there was NO application-path way to repair it ("event deleted ⇒ nothing to do"). **Fix:** deactivation now ALWAYS reconciles; since reconciliation is state-based (desired schedule derived from the COMPLETE active event set per date), re-running converges idempotently and self-heals stale rows. No schema change required: cancellation ownership is deterministically derivable from active events (closures/working-Saturday/LAB_CANCELLED/quiz-day protections untouched) — `is_cancelled` remains a synchronized materialization, not an independent flag.

**(c) Counting.** Not a new defect: every counting consumer already routes through the canonical pipeline (`collapse_count_rows` → `occurrence_is_cancelled`, or documented raw-`is_cancelled` skips). The wrong numbers the owner saw were produced by the same stale-code server executing pre-fix `collapse_count_rows`.

## 3. Consumer Matrix (Part 12)

| Consumer | Source | Rule | Canonical |
|---|---|---|---|
| Track daily | occurrence-grouped session read | `is_cancelled` field; UI renders Cancelled-first | ✅ |
| Subject summaries / Subjects view | `get_subject_counts_up_to_date` → `collapse_count_rows` | `occurrence_is_cancelled` | ✅ |
| Batched dashboard/analytics counts | `get_subject_counts_for_user` → same | same | ✅ |
| Quiz-eligibility windows | `get_subject_counts_between` → same | same | ✅ |
| History items / filters / summary | grouped occurrences + predicate | visible as CANCELLED; excluded from att/missed/pending/pct | ✅ |
| Dashboard Today/Overall/Weekly-days; Calendar counts; Analytics | grouped occurrences | raw `is_cancelled` skip | ✅ |
| Dashboard weekly % (`_aggregate_range`) | grouped occurrences | predicate (aligned previous round) | ✅ |
| Notifications CLASS_REMINDER | daily scan | skips cancelled OR recorded | ✅ |
| Attendance mutation | `session.is_cancelled` | 409 | ✅ |

One definition of *applicable occurrence* lives in `app/engines/practical_occurrence.py::occurrence_is_cancelled`; no service invents its own rule.

## 4. State Lifecycle (now guaranteed)

create / PATCH-move / deactivate / re-deactivate / reactivate — every transition triggers `sync_event` over the affected span; desired state recomputed from ALL active events; restoration fires whenever an entry becomes desired again regardless of records; weekend-artifact deletions never touch attended projections; quiz-day sessions protected; LAB_CANCELLED keeps frozen attended-lab safety; closures keep Phase 6.6 checks 5/31 behavior. Idempotent under repeated synchronization.

## 5. Live BCS-058 (real numbers)

| Phase | Track 07-29 | Track 07-30 | Applicable lectures (Subjects) |
|---|---|---|---|
| Both cancellations ACTIVE (earlier verified) | CANCELLED (record Attended kept) | CANCELLED (record Missed kept) | **77** = N−2 |
| Events removed — STALE (bug) | CANCELLED (wrong) | CANCELLED (wrong) | stuck at 77 |
| After canonical reconciliation (**now**) | **Attended** (original) | **Missed** (original) | **79** = N restored |

History after restore: rows show Attended/Missed (not Cancelled); window summary `total 24 · attended 10 · missed 14 · cancelled 0`. Records byte-preserved throughout (created_at unchanged; statuses never rewritten). Incidental proof of self-healing: a routine date-scoped reconciliation sweep over [07-29..07-31] at 16:54 UTC restored both stale rows via the normal restore branch before the explicit repair DELETEs (which then returned 200 idempotently).

⚠ **Owner action required:** restart the backend so the running process loads the fixed modules (current process still executes pre-fix code until restarted).

## 6. Regression Coverage

NEW `backend/scripts/verify_cancellation_lifecycle_consistency.py` — **35/35**: unmarked→cancelled→restored · MISSED→cancelled→MISSED · ATTENDED→cancelled→ATTENDED · multi-session range event · deactivate · soft-delete semantics + ALREADY-INACTIVE re-deletion self-heal (core regression) · reactivate cycle · PATCH-move between two RECORDED sessions (both directions) · repeated-sync idempotency · records byte-preserved · History visibility+filters both directions · Subjects denominator −1/−2/restored (77→76→75→77 measured live) · Dashboard deltas consistent · eligibility-consumed counting core unit assertions · notifications stable · enrollment/owner isolation (403s) · unrelated-session isolation · exact baseline restore.

Existing: `verify_event_cancellation_propagation` **26/26** · phase_6_6 **36/36** · attendance_spec **15/15** · events_correction **42/42** · working_saturday **24/24** · phase_11a **19/19** · compileall PASS. (Known pre-existing drift verifiers — history_filters, phase_9_1, track_lab_fix, 8_1, 8_2, phase_2, 7_2 — unchanged from stash-A/B-proven pre-fix behavior.)

## 7. Database Integrity & Security

Final state: alembic single head `d1e2f3a4b5c6`; zero temp users/artifacts (ECL_/ECF_/TRK_TMP patterns purged incl. FK-crash leaks cleaned by captured IDs); remaining count deltas vs snapshot (+2 events, +1 session, +1 record) are the OWNER'S own concurrent app activity (their EXTRA_LECTURE 07-17 + its materialized extra + their MISSED mark, created via their server 15:42–15:48 UTC) — not touched. Cancelled-set membership = exactly the four legacy rows each backed by an ACTIVE source event (no stale rows). No record deleted; no status rewritten; no client-supplied identity; authorization boundaries asserted (403 paths) in the verifier.

## 8. Frozen-System Impact

Reopened ONLY `EventService.deactivate_event`'s early-return (documented reason: made canonical repair impossible). All Phase 6.6 / 9.1 / 11 / 12A / 12B contracts preserved and re-verified. Phase 12D NOT started.

## 9. Manual Verification Checklist (after restarting backend)

1. Restart backend → Track 2026-07-29/30 show BCS-058 as Present/Absent originals (not Cancelled).
2. Create CLASS_CANCELLED for any past marked lecture → Track flips to greyed Cancelled; History row Cancelled; subject lecture-total −1; percentages consistent across Dashboard/Subjects/History.
3. Remove that event again → Track/History restore original state; lecture-total returns; percentages match step-2 baseline.
4. Toggle active off/on/off repeatedly → state follows the active flag every time, no drift.
5. Edit (move) a cancellation A→B with marks on both dates → old restored, new cancelled.
6. Confirm attendance Change buttons are absent while cancelled and functional again after removal; underlying history timestamps unchanged.

## 10. HARD STOP

No commit. No push. Phase 12D not started.
