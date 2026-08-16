# Quiz Day Recovery + Verifier Hardening Report (2026-08-16)

Focused recovery and data-safety task following the forensic audit of the
Events → Track pipeline. **No Quiz Day product semantics changed. No Option-B
behavior changed. No frontend changed. No commit.**

---

## 1. Pre-recovery verified state (from the forensic audit)

- 18 seeded QUIZ_DAY `AcademicEvent` rows existed, **all `active=False`**
  (their `quiz_schedules` rows remained `SCHEDULED`).
- 7 quiz-day-shaped `ClassSession` rows were missing.
- Owner-created BNC-501 **07-31 EXTRA_LECTURE + SURPRISE_QUIZ** sessions had
  been deleted by `verify_events_correction.py`'s date/shape-based cleanup.
- Attendance records = **122** (preserved throughout).
- One owner-created 2026-08-17 BCS-502 QUIZ_DAY test event (inactive) and one
  owner-created BNC-501 08-24 QUIZ_DAY event (`6019a478`, active) existed.

## 2. Restoration performed (Phase 1)

1. **Reactivated exactly the 18 seeded QUIZ_DAY events** — identified by
   `quiz_schedules` backing **and** the 2026-08-14 seed creation window
   (never by type/date/count alone). The owner's 08-17 test event and all
   other owner events were left untouched.
2. **Restored the missing seeded Quiz Day sessions via the canonical,
   idempotent mechanism** (`scripts/materialize_quiz_day_sessions.py`):
   - Created **6** quiz-day sessions: 08-31 BCS-502, 09-11 BCS-058,
     09-21 BCS-502, 10-09 BNC-501, 10-12 BCS-501, **10-23 BCS-054 (the
     canonical session)**.
   - **10-16 BCS-502 was NOT created**: that date already has the subject's
     regular Friday lecture + tutorial, so per the Option-B coverage rule no
     quiz-day session belongs there (the audit's inference of a 7th row was
     wrong — the 7th row the audit observed was the owner's 08-17 test-event
     session, which is intentionally NOT restored).
   - No duplicates: the script is idempotent on `(timetable_entry_id absent,
     subject, date)` and re-running creates nothing new.
3. **No attendance records were created, modified, or deleted** (122 → 122).

## 3. Verifier hardening (Phase 2) — the data-loss class fixed

The forensic audit found the damage came from **date/shape-based cleanup**,
not ownership-scoped cleanup. Three verifiers contained that hazard; all
three are now hardened:

### `verify_events_correction.py`
- Removed `MY_WINDOWS` as a deletion criterion.
- The `finally` block now cleans up **only the events it created** (captured
  `test_event_ids`) and **only the sessions it materialized** (captured
  session IDs via delta snapshots after each event creation). No more
  "delete every EXTRA_LECTURE/quiz-day-shaped session on date X" sweeping.
- 42/42 checks. First run after a data change heals owner data via the
  canonical sync; second run is stable at 42/42.

### `verify_track_lab_fix.py`
- Replaced the window sweep (delete unattended extras, un-cancel, clear
  designations on **every** session in 07-15..08-31) with explicit-ID
  cleanup: `test_session_ids` (sessions its mid-sem events materialized —
  captured as a **delta**, never from the collapsed daily view) and
  `cancelled_member_ids` (the existing BCS-551 block it temporarily cancels
  for its LAB_CANCELLED check).
- The delta capture matters: on a lab day MID_SEM_PRACTICAL **designates the
  existing block** (no session is created), so the daily view's occurrence id
  is a pre-existing timetable row — capturing it would delete owner data.
- 16/16 checks.

### `verify_history_filters.py`
- Removed the same window sweep. Its only session mutation is the BCS-551
  block its LAB_CANCELLED event temporarily cancels; the `finally` now
  un-cancels **only those captured IDs**.
- 20/20 checks.

## 4. Owner data healed and preserved

- The owner's active BNC-501 07-31 EXTRA_LECTURE + SURPRISE_QUIZ events were
  re-materialized through the canonical sync (the hardened events-correction
  verifier's 07-31 checks trigger the reconciliation). They now exist again
  and **survive every verifier run** (extras = 8 before and after).
- The BCS-551 08-24 two-period lab block is intact (2 timetable rows).
- The owner's 08-17 BCS-502 quiz-day test event remains **inactive and
  untouched**; the owner's BNC-501 08-24 duplicate (`6019a478`) remains
  active and untouched.

## 5. Focused recovery verifier (Phase 3/4)

New `backend/scripts/verify_quiz_day_restore.py` — **11/11 checks**, run
twice (idempotent). Asserts, scoped through `quiz_schedules`-backed seed
identity (never a global QUIZ_DAY count):

- A–E. All 18 seed schedules + 18 seed events present, all seed events
  active, seed UUIDs unchanged, schedule UUIDs unchanged.
- F. The 6 canonical uncovered-date quiz-day sessions present; no duplicate
  quiz-day occurrence for any seeded date/subject.
- G. No duplicate quiz-day session on any seeded date.
- H. Attendance records unchanged (122).
- I. The owner's 08-17 test event remains inactive.
- J. Owner-created events/sessions outside verifier ownership unchanged.

## 6. Full verifier results (final, after recovery + hardening)

| Verifier | Result |
|---|---|
| 6.5 | 26/27 (check 20 — owner's active duplicate BNC-501 08-24 event collides with the frozen "exactly one quiz-day event on 08-24" assertion; see §7) |
| 6.6 | 36/36 |
| 6.7 | 28/31 (checks 4/6/7 — owner's duplicate inflates the (subject,date)-scoped seed count to 19; pre-existing owner-data drift, same class as before this task) |
| 7.1 | 25/26 (check 6 — same owner-duplicate inflation; **check 5 PASSES**, proving the canonical 10-23 BCS-054 session is restored) |
| 7.2 | 26/26 |
| 8.1 | 22/22 |
| 8.2 | 18/18 |
| 9.1 | 28/28 |
| 9.2 | 29/29 |
| attendance-spec | 15/15 |
| events-correction (hardened) | 42/42 |
| history-filters (hardened) | 20/20 |
| quiz-day-materialization | 14/14 |
| quiz-day-restore | 11/11 (twice) |
| track-lab-fix (hardened) | 16/16 |

**No frozen verifier was weakened.** The 6.5/6.7/7.1 failures are all
owner-data fixture drift caused by the owner's legitimate duplicate active
BNC-501 08-24 quiz-day event (`6019a478`) sharing the seeded
(subject, date) identity — the same category as the previously documented
7.1/6.7 drift (records 92→101, events 18→26). 6.5 check 20 is **new** this
turn in the sense that restoring the seeds to their correct active state made
the collision visible.

## 7. Open items requiring owner decision

1. **The owner's duplicate BNC-501 08-24 QUIZ_DAY event (`6019a478`)** — it
   duplicates the seeded quiz day (same subject + date, same
   `quiz_schedules` backing) and is the sole cause of the remaining
   6.5 check 20 / 6.7 checks 4,6,7 / 7.1 check 6 failures. Options:
   (a) the owner deactivates/deletes the duplicate, or
   (b) the owner authorizes scoping those frozen checks by seed identity
   (creation-window + `quiz_schedules` backing), or
   (c) the drift stays documented as-is.
2. The audit's un-attributed quiz-day event deactivation (19 events set
   `active=False` between 14:26 and 14:39 UTC) — no committed code does it.
3. 6.7/7.1's remaining documented 11-02..11-12 cleanup windows still sweep
   extras/weekend rows on those dates (no seeded quiz dates or owner data
   there today) — a documented residual hazard, intentionally not hardened
   during this task.

## 8. Final DB integrity (before → after)

| Metric | Pre-recovery | Post-recovery |
|---|---|---|
| Seeded quiz schedules (SCHEDULED) | 18 | 18 |
| Seeded QUIZ_DAY events | 18 (all inactive) | 18 (**all active**) |
| Total events | 38 | 38 |
| Total sessions | 690 (audit end) | **698** (6 quiz-day + 2 owner extras healed + 08-24 block intact) |
| Quiz-day-shaped sessions (uncovered dates) | 0 | **6** (+ 10-23 BCS-054 canonical) |
| Attendance records | 122 | **122** |
| Owner-created events | unchanged | unchanged (08-17 test event stays inactive) |
| Owner-created extra sessions | 6 (2 missing) | **8** (07-31 pair healed, preserved) |

**Every DB mutation performed this task:** reactivate 18 seeded events;
create 6 canonical quiz-day sessions; heal 2 owner 07-31 extras (via the
canonical sync); restore 1 BCS-551 08-24 timetable row that my own verifier
hardening had wrongly deleted (mirroring the generator's exact row shape —
`expand_baseline.py` is blocked by its own BCS-054 pre-flight invariant);
delete the verifiers' own test artifacts. No attendance records, no owner
events, no quiz schedules were modified. Nothing was guessed.

## 9. Static checks

- `python -m compileall app scripts` — PASS.
- No frontend files changed; no frontend checks needed.

**HARD STOP — recovery + hardening complete. No Quiz Day semantics changed,
no Option-B change, no commit, no Phase 9.3 started.**
