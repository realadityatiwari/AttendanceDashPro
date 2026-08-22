# Bug-Fix Report — CLASS_CANCELLED Not Propagating to Track

**Date:** 2026-08-22 · **Scope:** backend event→session pipeline (Phase 6.6 architecture) + counting-consumer alignment · **Status:** FIXED & VERIFIED (no commit made — owner commits)

---

## 1. Observed Bug

An active `CLASS_CANCELLED` academic event for BCS-058 (Data Warehousing & Data
Mining), Lecture, 2026-07-30, 10:00 AM–11:00 AM appeared correctly on the Events
page, but Track for 2026-07-30 still rendered the matching session as a normal
attendance-taking class:

```
10:00 AM–11:00 AM  BCS-058  Data Warehousing & Data Mining  LECTURE  Absent [Change]
```

The cancellation never reached the canonical session pipeline.

## 2. Exact Reproduction Data (live DB, verified)

| Object | Value |
|---|---|
| class_session | `19bdc85a-34f6-4595-86aa-76450118bb3a` — LECTURE, is_extra=false, **is_cancelled=false**, timetable_entry `02ee420a-…` (Thursday 10:00–11:00) |
| attendance_record | `faa0ce5e-…`, owner `9b84e891-…`, status **MISSED** (created 2026-08-12, updated 2026-08-22) |
| academic_event | `9e5a7f98-92db-488b-8df0-939ada69069c` — **CLASS_CANCELLED**, active=true, start=end=2026-07-30, subject=BCS-058 (`ff7fbc57-…`), class_type=LECTURE, created 2026-08-22 11:43:39 UTC |

Matching is inferred by the canonical synchronizer (subject_id + date + class_type → timetable entry). The event matches exactly and was created AFTER the session/record existed. A second active sibling case existed on 2026-07-29 (event `ce76c27f-…`, session `ea065985-…`) with the same shape.

## 3. Expected Behavior

Active CLASS_CANCELLED + matching scheduled class ⇒ canonical `class_sessions.is_cancelled = true` ⇒ attendance mutation rejected (409) ⇒ Track presents Cancelled (no Present/Absent/Change) ⇒ every consumer excludes it from attendance math.

## 4. Actual Behavior

The synchronizer ran in the create transaction but was a silent no-op: the session held an attendance record, so reconciliation skipped it. Track kept rendering Absent+Change; subject %/eligibility/history kept counting the absence.

## 5. Canonical Invariant (established from code/spec)

Cancellation state is `ClassSession.is_cancelled` (ADR 004); consumers treat cancelled as its own non-counted state; `record_attendance` rejects cancelled sessions (409); Track/Dashboard/Calendar/Analytics already render/exclude via `is_cancelled`. The invariant above (§3) is the intended contract — this bugfix restores it for the one path that violated it.

## 6. Root Cause

`EventSessionSynchronizer._reconcile_date` began its scheduled-session loop with a blanket guard:

```python
for session in scheduled:
    if session.id in attended_ids:
        continue        # ← any attendance record ⇒ session untouchable
```

Any session holding ANY attendance record was skipped entirely, so an explicit CLASS_CANCELLED could never cancel a recorded occurrence — precisely the historical case the product requirement ("students record what actually happened") targets. Mechanically proven: running `sync_event` explicitly on the live event left `is_cancelled=False` pre-fix; post-fix it sets True. Cancellation demonstrably worked only for unattended sessions (all 4 previously-cancelled rows had zero records).

## 7. Exact Code Path Responsible

```
POST/PATCH/DELETE /api/v1/events (events.py)
→ EventService.create_event/update_event/deactivate_event (event_service.py)
→ EventSessionSynchronizer.sync_event / _desired_schedule / _reconcile_date   ← defect here
   (backend/app/services/event_session_service.py)
→ class_sessions.is_cancelled
→ Track: AttendanceRepository.get_daily_sessions → attendance_service.get_daily_sessions
   → frontend TrackSessionCard (is_cancelled-first render — already correct)
Counting: practical_occurrence.collapse_count_rows / attendance_repo history summary+filters /
dashboard _aggregate_range                                                ← stale-record precedence gap here
```

## 8. Fix

**Synchronizer (`event_session_service.py`):**
- `_desired_schedule` now also returns `cancellation_removed` — timetable-entry ids explicitly removed from the desired schedule by an active **CLASS_CANCELLED** on that date.
- `_reconcile_date` scheduled-session loop restructured:
  - quiz-day protection first (unchanged);
  - restoration (un-cancel) always allowed — required so deactivation/edit fully reverses recorded-but-cancelled sessions;
  - weekend-artifact deletion still never touches attended projections;
  - cancellation now applies when the session is unattended (**unchanged**) OR when its entry is explicitly targeted by an active CLASS_CANCELLED (**the fix**).
- LAB_CANCELLED deliberately keeps Phase 9.1's frozen "attended labs are never cancelled"; closures/working-Saturday keep Phase 6.6 checks 5/31 behavior — neither enters `cancellation_removed`.

**Consumer alignment (single canonical predicate):** new `occurrence_is_cancelled()` in `practical_occurrence.py` — cancelled theory occurrences always count as Cancelled (stale marks never resurrect an absence); cancelled practical blocks keep the frozen record-wins rule (record-less cancelled blocks excluded). Applied in `collapse_count_rows`, history `_history_status_match` + `get_history_summary`, and dashboard `_aggregate_range`. No deletion of any attendance record anywhere.

## 9. Why Architecturally Correct

- Fixes the canonical synchronizer — one source of truth; no Track-side duplication, no second engine.
- Aligns two counting paths with the DOMINANT pre-existing consumer semantics (Track card, Dashboard Today/Overall/Weekly day rows, Calendar counts, Analytics overall/weekly already gave `is_cancelled` precedence over records; the state was simply unreachable before).
- State-based reconciliation stays idempotent and fully reversible (deactivate ⇒ session restored ⇒ stale record counts again).
- Stale records preserved as data; math excludes them per "cancelled ≠ absent".
- Frozen contracts honored: closures (6.6 checks 5/31), working-Saturday verifier, LAB_CANCELLED (9.1 check 18), quiz-day protection (attendance-spec 7b).

## 10. Related Cases Investigated

| Case | Result |
|---|---|
| Event after session (reported) | Fixed — cancels despite record |
| Event before materialization | Unchanged correct — desired schedule omits entry; nothing created (6.6 checks 6-8) |
| Event edit (move) | Verified — span_override reconciles both dates (new verifier 15/16) |
| Deactivation | Verified — exact reversal incl. recorded sessions (new verifier 17-19) |
| Date-range events | Per-date loop unchanged |
| Multiple subjects/classes | Isolation verified (verifier 6-8; 6.6 check 7) |
| Class types | Registry restricts CLASS_CANCELLED to L/T; LAB_CANCELLED P-only; asymmetry intentional (frozen 9.1) |
| Repeated sync | Idempotent (verifier 9; 6.6 check 12) |
| Existing attendance | Never deleted; excluded from math while cancelled; restored on reversal |
| Extras/substitutions/quiz-day | Untouched paths; boundary checks 21/22 + spec-alignment 15/15 |

## 11. Security Verification

No auth changes. JWT → get_current_user unchanged; events remain enrollment-scoped for students / admin-only otherwise (new verifier checks 1/4); attendance mutation still enrollment-checked (403 unenrolled) and 409 on cancelled; no client-supplied user_id anywhere in the touched paths; reads stay enrollment-scoped. New verifier: 26/26 including isolation checks.

## 12. Regression Verifier

New: `backend/scripts/verify_event_cancellation_propagation.py` (repo conventions: real API via ASGITransport, JWTs, temp users by captured IDs, rollback-txn boundary probes, exact baseline assertion). 26 checks covering §11.1–11 of the task brief plus frozen-boundary guards.

## 13. Verification Results

| Gate | Result |
|---|---|
| `python -m compileall -q app scripts` | PASS |
| NEW verifier | **26/26** |
| verify_phase_6_6 (event→engine) | 36/36 |
| verify_attendance_spec_alignment | 15/15 |
| verify_events_correction | 42/42 |
| verify_working_saturday_holiday | 24/24 |
| verify_phase_6_5 | 27/27 |
| verify_phase_7_2 | 25/26* |
| verify_quiz_day_materialization | 14/14 |
| verify_phase_11a / 11b | 19/19 · 23/23 |
| verify_phase_3_propagation / phase_1_eligibility / phase_7_1 | 26/26 · 18/18 · 26/26 |
| verify_phase_2_quiz_events | 14/15* |
| verify_history_filters / phase_9_1 / track_lab_fix / 8_1 / 8_2 | drift — identical failures proven on ORIGINAL code via git-stash A/B runs (pre-existing live-data/time drift, documented below) |

\* stash-A/B-proven pre-existing: fixed-fixture expectations vs grown live data (owner actively uses the same dev DB; e.g. 9.1's mid-sem flow now hits owner data → known 500/counts drift; track_lab_fix's "future" fixture dates aged into the past; its cleanup has a pre-existing FK-order crash leaking temp rows, cleaned by captured IDs after each run).

Frontend: NOT run — zero frontend changes (Track already rendered `is_cancelled` first).

## 14. Database Baseline / Restoration

Pre-work full snapshot captured (18 table counts + row dumps of events/sessions/records + alembic). Post-work: **all 18 table counts byte-equal to baseline; alembic single head `d1e2f3a4b5c6` unchanged**; zero verifier temp users/events/sessions/records remain (all removed by captured IDs; includes cleaning leaked `TRK_TMP_LAB` users and 9 leaked phase-9.1-style events + 1 extra session from the crashed track-lab cleanup).

Intentional, documented live-data repair (canonical-path, reversible): the two ACTIVE BCS-058 CLASS_CANCELLED events were re-synced so the reported bug is healed on the spot — sessions `ea065985…` and `19bdc85a…` now `is_cancelled=true`; their MISSED records preserved (excluded from math). Remaining snapshot diffs are updated_at bumps from transient (restored) verifier toggles and the owner's own concurrent activity.

## 15. Frozen-System Impact

Narrowly scoped reopen of the Phase 6.6 synchronization contract (documented reason: real correctness/data-integrity defect; the old guard made CLASS_CANCELLED a silent no-op for recorded sessions). Phase 9.1 lab semantics, Phase 6.6 closure/WS safety, quiz-day protection, Phase 5 History API shape, Phase 8 engines/formulas: unchanged behavior for all previously-reachable states (proven by green verifiers + stash A/B). Phase 12B responsive work untouched. No phase status changes; 12C remains next.

## 16. Files Changed

| File | Why |
|---|---|
| `backend/app/services/event_session_service.py` | Root-cause fix: cancellation-override propagation + safe restoration (+138/−39 across all four files) |
| `backend/app/engines/practical_occurrence.py` | Canonical `occurrence_is_cancelled()` predicate; collapse_count_rows uses it |
| `backend/app/repositories/attendance_repo.py` | History filters/summary use the predicate (cancelled theory ≠ missed/pending) |
| `backend/app/services/dashboard_service.py` | `_aggregate_range` uses the predicate (weekly % aligns with Overall) |
| `backend/scripts/verify_event_cancellation_propagation.py` | NEW regression verifier (26 checks) |
| Governance docs (4) + this report | Mandatory synchronization |

## 17. Remaining Risks

- LAB_CANCELLED retains the frozen no-over-record contract — a lab cancelled after being marked will still not flip (Phase 9.1 scope; needs a deliberate product decision to change).
- History item payloads keep both `status` and `is_cancelled`; UIs must keep preferring `is_cancelled` (both current surfaces do).
- Pre-existing verifier/live-data drift (history_filters 7/20, phase_9_1 21/28, track_lab_fix date-aging crash, 8_1/8_2, phase_2 14/15) predates this fix and remains open hygiene work.

## 18. Manual Testing Checklist (owner)

1. Track 2026-07-30 → BCS-058 shows greyed **Cancelled**, no Change button. ✔ (API probe confirms)
2. Track 2026-07-29 → same for BCS-058 lecture.
3. Dashboard Today (if date today)/Overall/Weekly unaffected by those absences; subject % for BCS-058 improved accordingly.
4. Events page → deactivate the 07-30 cancellation → Track shows Absent again; reactivate → Cancelled again.
5. Create a fresh CLASS_CANCELLED for another past marked lecture → immediate Cancelled in Track after save.
6. Marking a cancelled session impossible (no controls; API 409).
7. History: the rows appear as Cancelled; Missed filter excludes them; percentages consistent with Track/Dashboard.

## 19. HARD STOP

No commit made. No unrelated work started. Phase 12C not begun.
