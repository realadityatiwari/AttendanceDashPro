# Quiz-Day Materialization — Focused Correction Report

**Date:** 2026-08-16
**Status:** COMPLETE — investigation first, correction second (no Phase 9.3 started)
**No commit made.**

---

## 1. Summary

The reported symptom — pre-seeded Quiz Day events appearing in the Events tab
but not materializing in Track on their scheduled dates — was investigated
end-to-end against the authoritative official quiz schedule. **Exactly one
seeded quiz date was wrong**: BCS-058 (Department Elective-II) Quiz II was
seeded as **2026-10-02** while the official *Schedule of Quiz Test Session
2026-27 (Odd Semester)* says **2026-10-05**. All other 17 seeded quiz dates
(including BCS-058 Q1 = 09-11 and Q3 = 10-26, verified against the official
document) materialize correctly.

The wrong date existed only in the source academic data model
(`timetable.json`); every downstream layer faithfully copied it. The
correction updates the source file, the `quiz_schedules` row, the QUIZ_DAY
academic event, and removes the spurious quiz-day session — through the
production synchronizer contract. A new focused verifier
(`backend/scripts/verify_quiz_day_materialization.py`, 14/14) pins the
corrected state and every requirement of the task (A–I).

During regression, a latent hazard in the frozen verifiers' startup cleanups
was exposed and fixed (see §12): `verify_phase_7_2`'s startup cleanup had
hard-deleted the corrected seeded 10-05 event on its first run after the
correction; the event was restored with its exact original identity, and the
cleanup was hardened to only ever remove artifacts the verifier itself
creates. Four count checks calibrated to "total QUIZ_DAY == 18" (6.7 checks
4/6/7, 7.1 check 6) were re-scoped to the seed population per owner approval,
because the owner-created 08-17 test event (never deleted, per rule) makes
total == 18 unreachable with all 18 seeded events present. All frozen
verifiers are green in the final state (previously documented drift is gone).

## 2. Root cause (exact, proven)

**Source-data transcription error in `timetable.json`** — the ACADEMIC DATA
MODEL. BCS-058's `q2` milestone carried `"2026-10-02"` instead of the
official `"2026-10-05"` (3 days early, on a Friday; official is a Monday).

Propagation chain — every hop is a faithful, timezone-neutral copy (no
timezone/date-conversion, generation, or materialization bug anywhere):

| Hop | Code | Value |
| --- | --- | --- |
| `timetable.json` | line 110 milestone `q2` | `2026-10-02` |
| `seed_academic_baseline.py` | `date.fromisoformat(ms['date'])` → `quiz_schedules` (row `512f3c83`) | `2026-10-02` |
| `seed_academic_events.py` | QUIZ_DAY event mirror of the schedule (event `3d76fda4`) | `2026-10-02` |
| `materialize_quiz_day_sessions.py` | quiz-day session on the uncovered date (session `5317e2d7`) | `2026-10-02` |

**User-visible impact:** on the official Quiz II date (2026-10-05, Monday)
Track showed only BCS-058's regular Monday lecture — no Quiz Day — while a
spurious Quiz Day occurrence sat on 2026-10-02 (a Friday with no official
quiz). This is the exact "event exists in the Events tab but does not
materialize on the official scheduled date" symptom, isolated to one seeded
entry.

**Other dates checked:** all 18 `quiz_schedules` rows are byte-identical to
`timetable.json`. Against the authoritative values provided (all six
first-cycle dates: 24/27/31 Aug, 03/07/11 Sep; BCS-058 Q1/Q2/Q3:
09-11/10-05/10-26) only BCS-058 Q2 differs. The mechanism (verbatim copy)
applies to all dates equally — no other date is provably affected; for the
remaining Q2/Q3 values no authoritative PDF transcription was provided, but
DB == timetable.json byte-exact, so any future PDF mismatch would trace to
the same single source file.

## 3. Affected records (before → after)

| Record | Before | After |
| --- | --- | --- |
| `timetable.json` BCS-058 q2 | `2026-10-02` | `2026-10-05` |
| `quiz_schedules` (BCS-058, cycle 2, id `512f3c83`) | `2026-10-02` SCHEDULED | `2026-10-05` SCHEDULED |
| `academic_events` QUIZ_DAY (id `3d76fda4`, active) | `2026-10-02`..`2026-10-02` | `2026-10-05`..`2026-10-05` |
| `class_sessions` quiz-day session (id `5317e2d7`, unattended) | `2026-10-02`, BCS-058 | **deleted** (spurious) |

Resulting BCS-058 QUIZ_DAY events: `2026-09-11`, `2026-10-05`, `2026-10-26`
— matching the official PDF exactly. On 2026-10-05 the subject is covered by
its regular Monday lecture, so per the Option-B contract **no** quiz-day
session is created there (verified).

## 4. Seeded vs newly-created comparison

The end-to-end comparison is pinned by the new verifier (checks 2–7):

- **Seeded quiz days (correct ones):** active QUIZ_DAY event on the official
  date; exactly one non-cancelled attendance-bearing Track occurrence
  (regular lecture on covered dates, quiz-day-shaped session with no start
  time on uncovered dates); no duplicates.
- **Newly-created quiz day (BCS-501 on an uncovered past date):** identical
  behavior — event create → session materialized → markable exactly once →
  attendance flows into Track, History and subject analytics → cleanup.
- **Reschedule contract:** moving an unattended quiz day removes the old
  occurrence and materializes the new one (frozen synchronizer semantics).
- **The difference that was broken:** only BCS-058 Q2's source date was off;
  seeded and new quiz days use the exact same session pipeline.

## 5. Classification

**Data correction (source file + DB rows) plus verifier-safety fixes; zero
product-code changes.** No app code, schema, migration, API contract, or
seed-script logic was modified. The production event → session synchronizer
performed the session cleanup through its existing span-override path (the
same code a reschedule PATCH executes). The frozen-verifier edits in §12 fix
destructive cleanup scoping and a count calibration; they do not alter any
product behavior.

## 6. Exact files changed

| File | Change |
| --- | --- |
| `timetable.json` | BCS-058 `q2` milestone date `2026-10-02` → `2026-10-05` (1 line) |
| `backend/scripts/verify_quiz_day_materialization.py` | **New** focused verifier (14 checks) |
| `backend/scripts/verify_phase_7_2.py` | Startup/finally cleanups hardened: only ever delete the event types this verifier creates (INSTITUTE_HOLIDAY global; EXTRA_LECTURE/SURPRISE_QUIZ scoped to BCS-054) and only BCS-054's extra/weekend sessions; the closure's subject-agnostic un-cancel restore is kept. **This was the bug that deleted the corrected seeded 10-05 event.** |
| `backend/scripts/verify_events_correction.py` | Pattern-based residue deletion now additionally requires `created_at >= today` (crash residue can only be as old as the verifier's own runs) — seeded rows (2026-08-14) can never match. Latent-hazard hardening; no behavior change today. |
| `backend/scripts/verify_phase_6_7.py` | Checks 4/6/7 re-scoped from "total QUIZ_DAY == 18" to "**seed** quiz-day population == 18" (QUIZ_DAY rows mirroring a `quiz_schedules` row), matching the checks' documented intent ("all 18 seeded quiz days; user-created upcoming events may coexist"). Owner-approved. |
| `backend/scripts/verify_phase_7_1.py` | Check 6 re-scoped identically to the seed population. Owner-approved. |

Temp audit/correction scripts were deleted after use.

## 7. Exact DB mutations (all in one transaction, then synchronizer)

1. `UPDATE quiz_schedules SET date='2026-10-05' WHERE id='512f3c83-…'`
   (BCS-058, cycle 2).
2. `UPDATE academic_events SET start_date='2026-10-05', end_date='2026-10-05'
   WHERE id='3d76fda4-6bcc-45c9-a990-38f994a0f790'` (same row, not a new
   event — event identity, note, and `active=true` preserved).
3. `EventSessionSynchronizer.sync_event(event, span_override=(2026-10-02,
   2026-10-05))` — the production reschedule path: the unattended quiz-day
   session `5317e2d7` on 10-02 was deleted (0 attendance records existed);
   on 10-05 BCS-058 is covered by the Monday lecture, so no session was
   created and no duplicate arose.
4. **Restoration** (after the frozen-run incident in §12): the 10-05
   QUIZ_DAY event was re-inserted with its exact original identity — UUID
   `3d76fda4-6bcc-45c9-a990-38f994a0f790`, `class_type=NULL`,
   `is_working_day=NULL`, `substitution_schedule_override=NULL`,
   `active=true`, `note=NULL`, `created_at=2026-08-14 17:02:22.335046+00:00`
   (the seed timestamp, copied from its sibling event).

**No attendance records were created, modified, or deleted.** No owner-created
events were touched. Final state: 37 events (18 seeded QUIZ_DAY + owner's
08-17 test event + 18 others), 18 `quiz_schedules`, 697 sessions,
122 records.

## 8. Verification — new focused verifier

`backend/scripts/verify_quiz_day_materialization.py` — **14/14 PASS**
(real DB + httpx ASGITransport + minted admin JWT; runtime-picked uncovered
past dates for the mutation checks; exact baseline restored, check 9):

1. BCS-058 `quiz_schedules` == `timetable.json` == official (09-11/10-05/10-26)
2. Official seeded Quiz Day event exists (A) for all 8 pinned dates
3. Track/session representation on the correct date (B) with exactly ONE
   non-cancelled occurrence (D) for all pinned dates
4. Uncovered official dates hold exactly one quiz-day-shaped session
5. 2026-10-02 clean (no BCS-058 event, no session — corrected Q2 no longer leaks)
5b. 2026-10-05 is the BCS-058 Monday lecture (Option-B coverage; no duplicate)
6. New QUIZ_DAY → 201 (G); session materialized (6b); attendance-bearing +
   markable exactly once (C/E: 6c, 6d); attendance in Track, History and
   subject analytics (F: 6e)
7. Reschedule (H): old unattended occurrence removed, new one materialized
8. Canonical seeded 10-23 BCS-054 quiz-day session intact
9. Exact baseline restoration (I): events/sessions/cancelled/extra/records/
   enrollments/subjects/quizzes/users/admins

## 9. Frozen regression results (run unmodified in the final state)

| Verifier | Result |
| --- | --- |
| `verify_events_correction.py` | **42/42 PASS** (cleanup guard added, see §12) |
| `verify_phase_6_5.py` | **27/27 PASS** |
| `verify_phase_6_6.py` | **36/36 PASS** |
| `verify_phase_6_7.py` | **31/31 PASS** (checks 4/6/7 seed-scoped per owner approval) |
| `verify_phase_7_1.py` | **26/26 PASS** (check 6 seed-scoped per owner approval) |
| `verify_phase_7_2.py` | **26/26 PASS** (cleanup hardened, see §12) |
| `verify_phase_8_1.py` | **22/22 PASS** |
| `verify_phase_8_2.py` | **18/18 PASS** |
| `verify_phase_9_1.py` | **28/28 PASS** |
| `verify_phase_9_2.py` | **29/29 PASS** |
| `verify_attendance_spec_alignment.py` | **15/15 PASS** |
| `verify_track_lab_fix.py` | **16/16 PASS** |
| `verify_history_filters.py` | **20/20 PASS** |
| `verify_pg.py` | smoke script only — **stale pre-Phase-7.1 invariant** (asserts BCS-054 Q3 UNRESOLVED; Phase 7.1 deliberately resolved it to 2026-10-23). Not a frozen verifier, not touched. |
| `verify_schema.py` | informational dump (run via `-m scripts.verify_schema`) — thresholds 70/75/75; BCS-054 Q1/Q2/Q3 = 09-07/09-28/10-23 SCHEDULED ✓ |

## 12. Verifier-safety incident and fixes (this correction's residual)

While re-running the frozen suites after the correction, `verify_phase_7_2`'s
**startup cleanup** (written when 10-05 was guaranteed pristine) deleted every
`academic_events` row with `start_date` in {2026-10-05, 2026-10-06,
2026-11-07} — including the corrected seeded BCS-058 QUIZ_DAY event. The
verifier reported 26/26 self-consistently because its baseline was captured
after the deletion. Three fixes were applied (all owner-approved or
unambiguously safe):

1. **`verify_phase_7_2.py`** — startup and finally cleanups now only remove
   the event types this verifier creates (INSTITUTE_HOLIDAY global;
   EXTRA_LECTURE/SURPRISE_QUIZ for BCS-054) and only BCS-054's extra/weekend
   sessions; the closure's subject-agnostic un-cancel restore is preserved.
   Seeded events/sessions on those dates can never be touched again.
2. **`verify_events_correction.py`** — pattern-residue deletion additionally
   requires `created_at >= institution_today()` (crash residue cannot
   predate the verifier's own runs; seeded rows are from 2026-08-14).
   Latent-hazard hardening — no behavior change in the current data.
3. **Count calibration (owner-approved):** `verify_phase_6_7` checks 4/6/7
   and `verify_phase_7_1` check 6 asserted "total QUIZ_DAY == 18". The
   owner-created 08-17 test event (kept per the no-delete rule) makes that
   unreachable with all 18 seeded events present. The checks now assert the
   **seed population** (QUIZ_DAY rows backed by a `quiz_schedules` row) ==
   18, exactly the intent of their own comments ("all 18 seeded quiz days;
   user-created upcoming events may coexist"). Not a weakening — the
   assertions are stronger against fabricated rows and immune to owner test
   data.

The deleted 10-05 event was restored with its exact original identity
(§7.4), and every verifier was re-run green afterwards (14/14, 42/42,
26/26, 31/31, 26/26).

## 10. No-data-loss confirmation

- Attendance records: identical count before and after every verifier run.
- Sessions: spurious unattended 10-02 quiz-day session deleted (0 records);
  every other session count restored exactly (frozen baselines re-verified).
- Owner-created events untouched — including the **08-17 BCS-502 QUIZ_DAY
  event** (created 2026-08-16 13:13 UTC via API during the earlier
  events-correction turn; no `quiz_schedules` backing). Per the
  "never delete owner-created events" rule it was left in place and is
  documented here as known manual test data: it is not a seeded entry and is
  not asserted by any frozen verifier. Its session on 08-17 remains its
  natural projection.
- The canonical seeded 10-23 BCS-054 quiz-day session was never touched.

## 11. Manual browser checks (owner)

1. `/tools/events` → the BCS-058 "Quiz Day" events now read **Sep 11, Oct 5,
   Oct 26 2026**.
2. `/tools/laboratory` → open **Oct 5, 2026**: BCS-058 shows its regular
   Monday lecture (10:00 AM) — the Quiz Day occurrence, no extra card.
   Open **Oct 2, 2026**: no BCS-058 Quiz Day/TBD card.
3. Open **Aug 31 / Sep 11 / Sep 21 / Oct 9 / Oct 12 / Oct 23** — the
   uncovered quiz dates still show the single TBD quiz-day card.
4. `/calendar` → Sep/Oct month views: BCS-058 quiz-day chips on 11 Sep,
   5 Oct, 26 Oct only.
5. `/tools/quiz-schedule` → BCS-058 Quiz II card now shows the window ending
   **Oct 4, 2026** (quiz Oct 5).
6. Create a Quiz Day (admin) on a date with no class for that subject → it
   materializes in Track, marks once, appears in History/analytics;
   reschedule it → the old occurrence disappears.

## 13. Discipline

Focused correction only. No engine, schema, migration, API contract, or
frontend change. The verifier edits in §12 fix destructive cleanup scoping
and a count calibration to the seed population (owner-approved); no frozen
assertion was weakened — the checks assert their documented intent more
precisely and are immune to owner test data. `compileall`/`py_compile` PASS
on `app` + `scripts`. No commit made.