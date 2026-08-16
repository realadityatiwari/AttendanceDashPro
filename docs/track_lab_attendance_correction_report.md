# Track Lab Attendance Correction — Implementation Report

**Focused correction after Phase 9.2.1** (no new phase started; no commit).

Two Track attendance defects were fixed without disturbing the canonical
attendance architecture:

1. **A two-hour laboratory block must be ONE attendance occurrence** (one
   Present/Absent decision, one canonical `AttendanceRecord`, counted once in
   every denominator — no denominator inflation).
2. **Future dates must be view-only** (schedule stays visible as Upcoming; no
   attendance mutation before the institution-local date, enforced at both the
   UI and the mutation API).

---

## 1. The defect and its root cause

BCS-551 (Mon), BCS-552 (Thu) and BCS-553 (Fri) are two-hour laboratory
subjects. Their timetable represents each two-hour lab as **TWO contiguous
one-hour `TimetableEntry` rows** (e.g. BCS-551 Mon 13:00–14:00 + 14:00–15:00),
and the baseline expansion therefore materializes **TWO `ClassSession` rows
per lab block**. Track rendered both rows as separate markable cards:

```
01:00 PM — BCS-551 — Practical — Present / Absent
02:00 PM — BCS-551 — Practical — Present / Absent
```

This is **case A: genuinely two `ClassSession` rows that are intentionally
periodized timetable facts**. The fix is therefore a **read-model/occurrence
grouping solution** — the two rows stay in `class_sessions` (timetable
fidelity, zero schema change), but every practical-attendance consumer treats
the block as ONE logical occurrence.

## 2. Architecture: the canonical occurrence collapse

New pure module `backend/app/engines/practical_occurrence.py` is the single
source of occurrence semantics:

- **Members of one occurrence**: PRACTICAL sessions of the same subject on
  the same date whose timetable periods are contiguous (member `end_time ==
  next.start_time`, both timetable-bound). Sessions without timetable times
  (event-created extras) are standalone. Non-contiguous practicals, different
  subjects, and different dates are never merged.
- **Block status precedence** (records are historical truth):
  `ATTENDED` (any member) > `MISSED` (any member) > `CANCELLED` (any member
  cancelled, no records) > `PENDING`.
- **Counting**: each occurrence contributes exactly ONE row with its block
  status; a cancelled occurrence (no records) is excluded — never Pending,
  never Absent. This removes the per-period denominator inflation.
- **Representative session id** (what one mutation targets): first member
  WITH a record (so "Change" updates that record), else the first CANCELLED
  member (a cancelled block rejects marking with the existing 409), else the
  first member. One mutation ⇒ one `AttendanceRecord`.

Applied at every practical-attendance surface so Track, mutation, summary,
history, analytics, dashboard, and calendar never disagree:

| Consumer | Change |
|---|---|
| `AttendanceRepository.get_daily_sessions` (Track) | collapse → one card per lab block (`01:00 PM – 03:00 PM`) |
| `AttendanceRepository.get_subject_counts_up_to_date / for_user / between` | SELECT extended with date/cancelled/times; collapse → `(class_type, status)` tuples (same shapes the engine consumes) |
| `AttendanceRepository.get_sessions_with_status` (dashboard/analytics/calendar) | collapse → occurrences (weekly analytics + calendar session counts count the lab once) |
| `AttendanceRepository.get_history` + `get_history_summary` | collapse + occurrence-level status filtering (History represents the lab once) |
| `AttendanceService.record_attendance` | unchanged semantics (still session-id + one record) |
| `LaboratoryService` summary / activity | summary reuses `AttendanceService.get_summary` (collapsed, consistent); activity stays a session-level chronology by design |

The attendance engine formulas, quiz eligibility, event synchronizer, and
Phase 9 mid-sem/lab-cancelled event semantics are untouched.

## 3. Future-date view-only rule

- **Backend** (`AttendanceService.record_attendance`): after the existing
  404/409/403 guards, a session dated after the institution-local date is
  rejected with **400 "Cannot mark attendance for a future date"**. The local
  date comes from the canonical `settings.INSTITUTION_TIMEZONE`
  (Asia/Kolkata) via a new `institution_today()` helper — no scattered
  `date.today()`/UTC comparisons, no hard-coded offsets. Reads are never
  restricted.
- **Frontend** (`TrackSessionCard` + Track page): a future date renders
  Pending sessions with an **Upcoming** badge and no mutation controls
  (Change buttons are also suppressed defensively); the page hides "Mark all
  present" and shows a "View-only — attendance unlocks on <date>" note. The
  comparison uses the canonical `getLocalDateString()` local-date utility
  (ISO string comparison). Event-created sessions (e.g. a future
  MID_SEM_PRACTICAL) stay visible but unmarkable.

## 4. Files changed

**Backend (code)**
- `backend/app/engines/practical_occurrence.py` — NEW: canonical occurrence
  collapse (pure functions).
- `backend/app/repositories/attendance_repo.py` — collapse in the counting
  queries, daily read model, sessions-with-status, and history/summary.
- `backend/app/services/attendance_service.py` — `institution_today()` +
  future-date mutation guard (400).

**Frontend**
- `frontend/src/components/dashboard/TrackSessionCard.tsx` — lab block card
  (`start – end` span), Upcoming view-only state for future dates.
- `frontend/src/app/(authenticated)/tools/laboratory/page.tsx` — Track page:
  hide "Mark all present" for future dates + view-only note.

**Verifiers (contract-driven updates — see §6)**
- `backend/scripts/verify_phase_6_6.py` (checks 22/23/24)
- `backend/scripts/verify_phase_8_1.py` (checks 3–5/7/11/16 expected values)
- `backend/scripts/verify_phase_8_2.py` (checks 1/6/7)
- `backend/scripts/verify_phase_9_1.py` (checks 12/13)
- `backend/scripts/verify_phase_7_2.py` (checks 5/6 expected values)
- `backend/scripts/verify_attendance_spec_alignment.py` (check 3)
- `backend/scripts/verify_track_lab_fix.py` — NEW focused verifier (16 checks)

**No schema change, no migration, no `ClassSession` row merged/deleted by
this work.**

## 5. What was deliberately NOT implemented

- No merging/deleting of `ClassSession` rows (timetable fidelity preserved).
- No second attendance engine, no formula changes (the engine still receives
  the same `(class_type, status)` counting shape — now occurrence-collapsed).
- No experiment/faculty/grading behavior; `laboratory_experiments` /
  `laboratory_records` stay empty (0/0).
- No quiz-eligibility change (practicals were already excluded; collapse is a
  no-op for theory subjects).
- No change to the Phase 9.1 event synchronizer or designation semantics.

## 6. Frozen-verifier assertion updates (contract-driven, NOT weakened)

The old per-period semantics were woven into several verifiers ("a Friday lab
day = 2 practical sessions", "BCS-551 = 8 P rows through today"). The owner's
product contract change (one lab = one occurrence) makes those assertions
encode the *defective* behavior, so each was updated to the new occurrence
semantics — the assertion's intent is preserved and its expected value is
now block-based:

- **6.6**: 11-07 session count 5→4 (Monday schedule: 3 lectures + one lab
  block), daily 11-02 5→4, daily 11-05 7→6.
- **8.1**: overall/weekly expected values computed via the canonical
  collapse; BCS-551 practical total 8→4 (blocks).
- **8.2**: check 1/7 expected totals = occurrence collapse of the session
  table; check 6 cancels a whole *block* with no records (total/pending −1).
- **9.1**: BCS-553 practical total 9→4, pending 7→2 (occurrence-based);
  row-level event checks unchanged.
- **7.2**: Q-D8 overall/history expected values computed via the canonical
  collapse.
- **attendance-spec**: check 3 now asserts the future-date rule — a future
  quiz-day session is view-only (mutation 400, still visible); the as_of
  counting check (3b) is unchanged.

No assertion was removed, skipped, or loosened; every change encodes the
owner-requested occurrence contract. **`verify_phase_7_1.py` and
`verify_phase_6_7.py` were NOT touched** (their failures are pre-existing
baseline drift, see §8).

## 7. Verification results

**New focused verifier** `verify_track_lab_fix.py` — **16/16**:
- A: daily = one BCS-551 block (`01:00 PM – 03:00 PM`); one mutation ⇒ one
  `AttendanceRecord`; Change updates the same record; summary total = 4
  blocks (not 8 rows); history = 4 items (one per block); overall analytics
  count the lab once (recorded=1, pending=3); non-lab-day mid-sem extra
  stays a standalone occurrence.
- B: future read OK; future mutation 400 + no record; past/today markable;
  future MID_SEM_PRACTICAL visible/designated but not markable (400), and
  deactivating it clears the designation.
- C: lab summary practical block == attendance summary; LAB_CANCELLED
  excludes the whole block (daily cancelled, marking 409, denominator −1,
  reversibility); no experiment data fabricated.
- D: exact baseline restored.

**Frozen regressions (run unmodified except the contract updates above):**

| Verifier | Result |
|---|---|
| `verify_phase_6_5.py` | **27/27** |
| `verify_phase_6_6.py` | **36/36** |
| `verify_phase_6_7.py` | **30/31** — check 7 red (pre-existing drift, §8) |
| `verify_phase_7_1.py` | **25/26** — check 23 red (pre-existing drift, §8) |
| `verify_phase_7_2.py` | **26/26** |
| `verify_phase_8_1.py` | **22/22** |
| `verify_phase_8_2.py` | **18/18** |
| `verify_phase_9_1.py` | **28/28** |
| `verify_phase_9_2.py` | **29/29** |
| `verify_attendance_spec_alignment.py` | **15/15** |

**Static gates**: `python -m compileall app scripts` PASS · `npx tsc
--noEmit` PASS · ESLint on changed frontend files PASS · `next build` PASS.

## 8. Database state and pre-existing drift

**Final counts** (identical to the documented 9.2.1 baseline):
`academic_events` 22 · `class_sessions` 691 (0 cancelled, 0 extra) ·
`attendance_records` 95 · `student_enrollments` 18 · `subjects` 9 ·
`quiz_schedules` 18 · `users` 30 (1 ADMIN) · `laboratory_experiments` 0 ·
`laboratory_records` 0 · designations 0.

- **No `AttendanceRecord` permanently changed by this work.** One record was
  accidentally deleted during a *smoke test* (a collapsed-block representative
  id pointed at the owner's existing BCS-553 08-14 13:00 record, which the
  test then removed); it was immediately restored (status ATTENDED, same
  session/user). Final count 95 = 89 authorized + 3 BCS-553 + 3 BCS-502 owner
  records — all three BCS-553 and all three BCS-502 marks verified present.
- **Pre-existing drift (NOT caused by this work; reported, not modified):**
  - `verify_phase_7_1` check 23 asserts the frozen fixture `records == 92`,
    but the DB legitimately holds **95** (3 owner-entered BCS-502 marks from
    Phase 9.2.1-era manual testing). Per policy the verifier was left
    untouched; this is the same drift already documented in the 9.1/9.2.1
    reports.
  - `verify_phase_6_7` check 7 asserts "18 events, ALL QUIZ_DAY, all active";
    the DB holds 22 events (18 QUIZ_DAY + 4 owner-entered inactive events:
    1 MID_SEM_PRACTICAL + 3 EXTRA_LECTURE). Also documented in 9.2.1 and not
    modified.
- **Orphan residue cleanup (by a FROZEN verifier, not this code):** at the
  start of this task the DB held an orphan extra session on 2026-11-02 (an
  extra BCS-501 LECTURE with no backing event). The frozen `verify_phase_6_6`
  verifier's documented window cleanup removes unattended extras on its test
  window (11-02…11-07), so running the frozen regression removed that orphan;
  the DB returned to the documented 691/0 baseline. No code change caused it.

## 9. Known limitations

- A LAB_CANCELLED synchronizes by cancelling ONE timetable period row; the
  read model treats the whole block as cancelled (one occurrence, not
  markable, excluded from denominators). The other period row remains
  physically non-cancelled in the DB — a direct-API mutation against it would
  be absorbed by the collapse (block counts once) but is not otherwise
  blocked. The Phase 9.1 event semantics were intentionally left untouched.
- The laboratory **Activity** tab remains a session-level chronology (it is
  explicitly "every PRACTICAL ClassSession" with experiment linkage); the
  *counts* surfaces (summary, Track, history, analytics) are occurrence-based.
- Today is Sunday 08-16 with no scheduled sessions, so the new verifier's
  "today markable" check dynamically confirms present-day sessions accept
  mutation when any exist (boundary pinned by past-accepted / future-rejected).

## 10. Manual browser checklist (user)

- **Track** (`/tools/laboratory`): open a past Monday (e.g. 07-20) — BCS-551
  appears as ONE card "01:00 PM – 03:00 PM · PRACTICAL" with one Present/Absent
  action; mark it, then check the day summary counts it once.
- **Track future date**: navigate to a future Monday (e.g. 08-17) — lectures
  and the lab block are visible with an "Upcoming" badge, no Present/Absent
  buttons; "Mark all present" is hidden; the view-only note is shown.
- **History**: BCS-551 shows one row per lab block (4 blocks through today).
- **Laboratory page**: Practical Attendance tab totals match Track
  (occurrence counts); Activity tab still lists each timetable period.
- **Dashboard / Analytics**: weekly + overall treat a lab block as one.
- **Quiz eligibility** (`/tools/quiz-schedule`): unchanged.
