# Phase 9.1 — Laboratory Attendance & Event Integration (Implementation Report)

Status: **IMPLEMENTED 2026-08-15** — verification 28/28 + all frozen regressions
green except one documented baseline-drift failure (see §9). Not committed.

## 1. Executive summary

Phase 9.1 makes **Mid-Sem Practical** and **Lab Cancelled** first-class
**Academic Events** that the canonical `EventSessionSynchronizer` resolves
into the existing `ClassSession` pipeline. There is **no separate laboratory
attendance system** — the canonical chain is unchanged:

```
AcademicEvent
    → EventSessionSynchronizer
    → ClassSession
    → AttendanceRecord
    → existing Attendance Engine
    → Track / History / Subject Attendance / Dashboard / Analytics / Eligibility
```

A student creates a `MID_SEM_PRACTICAL` event for an enrolled practical
subject on a date; the synchronizer resolves the deterministic practical
occurrence for that subject/date (reusing the timetable session when one
exists, or materializing exactly one extra on a non-lab day), marks it with
the existing `ClassSession.designation = MID_SEM_PRACTICAL`, and the student
marks Present/Absent through the existing attendance mutation — flowing
through every existing calculation with no special formula.

A `LAB_CANCELLED` event cancels the matching practical occurrence using the
canonical `is_cancelled` semantics (identical session behavior to
`CLASS_CANCELLED`, restricted to practical subjects). Cancelled occurrences
reject attendance (409), are excluded from denominators, and Track shows them
as disabled.

Nothing else was built: no experiment curriculum, no experiment progress, no
`experiments ≥ 5 ⇒ mid-sem` rule, no FACULTY role, no grading/viva, no new
attendance engine, no lab attendance tables, no new endpoints.

## 2. Product decision — LOCKED (event-driven model)

The Phase 9.1 brief locked the model: lab events are **Academic Events that
modify the canonical attendance schedule**, not a parallel system. This
supersedes the Phase 9.0 audit's additive read-model proposal for 9.1; the
experiment-management domain remains a future concern (Phase 9.2+).

## 3. Event semantics

| Event type | Subject scope | Class type | Student-creatable | Session effect |
|---|---|---|---|---|
| `MID_SEM_PRACTICAL` | enrolled practical subject | `P` (PRACTICAL only) | Yes | Resolves/designates the practical occurrence as mid-sem |
| `LAB_CANCELLED` | enrolled practical subject | `P` (PRACTICAL only) | Yes | Cancels the matching practical occurrence |

- Both are **subject-scoped, per-occurrence events** in the same priority tier
  (30) as cancellations/extras in the frozen calendar engine — they never
  affect the day's working/teaching state (not closures, not working-day
  overrides, not quiz-schedule events).
- Both carry an optional `note` (e.g. cancellation reason / mid-sem remark).
  The `note` column is purely additive metadata — never read by any
  calculation.
- Students may create/update/deactivate them **only for subjects they are
  enrolled in** (`EventService.assert_mutation_allowed` → 403 otherwise);
  admins may do anything. Duplicate creation returns 409 via the existing
  duplicate guard.
- No new endpoints: `POST/PATCH/DELETE/GET /events` and the existing
  attendance mutation path are the entire API surface.

## 4. Session synchronization semantics

`EventSessionSynchronizer` (Phase 6.6, state-based reconciliation) extended
additively:

- **`LAB_CANCELLED`** joins `CANCELLATION_TYPES` (with `CLASS_CANCELLED`):
  removes ONE matching practical occurrence from the desired schedule, exactly
  like the legacy splice semantics. The registry restricts it to PRACTICAL so
  it can never cancel a lecture/tutorial.
- **`MID_SEM_PRACTICAL`** is **not an extra**: the mid-sem plan in
  `_desired_schedule` is computed from the ORIGINAL timetable snapshot (before
  cancellation removal) so:
  - a timetable practical for the subject/date is **REUSED** — the same
    session becomes the mid-sem (never duplicated: no "Normal Practical +
    Mid-Sem Practical" double opportunity);
  - when no timetable practical exists that day (non-lab day), **exactly one
    extra** practical occurrence is materialized so attendance can be marked;
  - the designation step (`_designate_mid_sem`) marks the **deterministic
    occurrence** — the FIRST practical session ordered by timetable start time
    (then id). When a lab day has two P slots for the same subject, the
    earliest slot wins deterministically; no period selector is needed in the
    UI because the model resolves it canonically. One mid-sem per subject:
    any other designated session for the subject is cleared (mirrors the
    Phase 8.2 admin service's replace semantics).
- Designation is **context, never attendance**: `_designate_mid_sem` /
  `_clear_mid_sem` never touch `attendance_records`. Designations are managed
  **only when the triggering event is itself `MID_SEM_PRACTICAL`** — other
  event syncs never touch `ClassSession.designation`, so the Phase 8.2 admin
  endpoint's designation survives unrelated event reconciliation.
- Reconciliation stays **state-based and idempotent**: re-running it twice
  converges (no duplicates), because each date's desired schedule is computed
  from ALL active events every time.
- **Attendance safety preserved**: sessions with attendance records are never
  cancelled, un-cancelled, or deleted (attended extras are kept; attended
  mid-sem sessions are never cancelled by a later `LAB_CANCELLED`; the
  "cancelled ≠ absent" 409 rule is preserved end to end).

## 5. Conflict resolution (scenarios A–J, verified)

| # | Scenario | Behavior |
|---|---|---|
| A | Normal practical + Mid-Sem | Reused: the existing timetable practical becomes the designated mid-sem — ONE attendance opportunity |
| B | Normal practical + Lab Cancelled | Matching occurrence cancelled (`is_cancelled`); not markable (409) |
| C | Mid-Sem + Lab Cancelled, same date | **Cancellation wins**: occurrence cancelled, no designation — never two conflicting sessions |
| D | Deactivate Mid-Sem | Designation cleared on that date; attendance records preserved |
| E | Deactivate Lab Cancelled | Occurrences un-cancelled (state-based reconciliation restores them) |
| F | Move Mid-Sem to another date | Old date designation cleared, new date designated (span-union reconciliation) |
| G | Move Lab Cancelled to another date | Old date restored, new date cancelled |
| H | Mid-Sem attended, then event deactivated | Attendance record preserved (safety), designation cleared, session retained |
| I | Lab cancellation after attendance exists | Attended sessions never cancelled — cancellation affects only unattended occurrences |
| J | Duplicate event creation | 409 via existing duplicate guard (deterministic) |

This follows the existing event priority/reconciliation semantics; no new
precedence was invented beyond the documented "cancellation wins" default for
the two new types.

## 6. Reversibility

Events remain reversible through the existing architecture (Phase 6.6
state-based reconciliation, soft-delete `active` lifecycle). `update_event`
reconciles the **union of the old and new spans**, so moving a mid-sem or lab
cancellation restores the old date and applies the new one in one transaction.
Deactivation restores exactly what the remaining active events imply. No
one-off destructive mutations; no duplicated session-generation logic.

## 7. Attendance propagation

- Mid-sem Present → canonical `AttendanceRecord` (Attended) on the designated
  session; counts in practical attendance.
- Mid-sem Absent → canonical `AttendanceRecord` (Missed); counts as recorded
  absence.
- Lab cancelled → `is_cancelled=True`; excluded from every denominator;
  pending stays pending; rejected for marking (409).
- All existing dashboard/analytics/subject/history surfaces react
  automatically because they read the canonical pipeline.
- **Quiz eligibility unchanged**: practicals remain excluded (verified
  byte-identical eligibility payload before/after all Phase 9.1 activity).
- The only read-model additions are additive presentation fields:
  `designation` on `AttendanceHistoryItem` and `DailySessionResponse` (NULL
  for regular sessions; never used in any calculation).

## 8. Authorization

- **STUDENT** (enrolled only): create/update/deactivate `MID_SEM_PRACTICAL`
  and `LAB_CANCELLED` for their own practical subjects; mark Present/Absent
  against the resulting sessions through the existing attendance mutation.
- **ADMIN**: everything (including the Phase 8.2 session-designation
  endpoint, still admin-only — verified 403 for students).
- **No FACULTY role** introduced (per Phase 9.0b decision D2).
- Students still cannot create global/closure/quiz-schedule events (frozen
  Phase 6.5 policy untouched; verified by existing frozen verifiers).

## 9. Database mutation / baseline status

- Migration applied: `a1b2c3d4e5f6_add_lab_event_types.py` —
  `ALTER TYPE eventtype ADD VALUE 'MID_SEM_PRACTICAL'` and `'LAB_CANCELLED'`
  (native PG enum) + nullable `academic_events.note` column. **Zero existing
  data rows changed** (the 18 QUIZ_DAY events untouched; note NULL for all).
- The Phase 9.1 verifier snapshots the baseline at start and restores it
  exactly (check 22): no test events, sessions, records, or designations left
  behind (verified by the final counts below).
- **Frozen-baseline drift discovered this phase**: the live DB now has
  **95 attendance records** (was 92). The +3 are legitimate owner-entered
  marks on **BCS-502 (Web Technology) LECTURE sessions — 08-04, 08-05, 08-12
  MISSED**, created 2026-08-15 16:19–16:20 UTC through the canonical
  attendance mutation path. They belong to the owner's admin account
  (`2401220100027`, Aditya Tiwari), are unrelated to Phase 9.1 (which only
  touches BCS-553 practicals for a temp user), and are **not verifier/test
  residue**. Per policy, **`verify_phase_7_1.py` was NOT modified** — its
  frozen fixed assertion `records == 92` (check 23) now fails at 95. This is
  BASELINE/TEST-FIXTURE DRIFT, not a code regression. The owner must decide:
  authorize the fixed fixture 92 → 95 (as was done 89 → 92), or accept check
  23 as a documented known-failing baseline assertion.

Final DB state after all verification (Phase 9.1 verifier restores its own
snapshot; owner's 3 marks preserved):
`events=18 · sessions=691 (0 cancelled, 0 extra) · records=95 ·
enrollments=18 · subjects=9 · quiz_schedules=18 · users=30 (1 ADMIN) ·
laboratory_experiments=0 · laboratory_records=0 · designations=0`.

## 10. Verification results

### Phase 9.1 verifier — `backend/scripts/verify_phase_9_1.py` — 28/28 PASS

1. student creates MID_SEM_PRACTICAL for enrolled practical subject → 201 (note persisted)
2. student MID_SEM_PRACTICAL for UNENROLLED subject → 403
3. student creates LAB_CANCELLED for enrolled practical subject → 201
4. student LAB_CANCELLED for UNENROLLED subject → 403
5. mid-sem produces exactly ONE practical attendance occurrence (no duplicate; designation visible on daily read model)
6. no duplicate session on repeated synchronization (note PATCH re-sync keeps one occurrence, one designation)
7. existing practical occurrence reused/overridden, not duplicated (designated session is the pre-existing timetable session)
8. lab cancellation makes the matching practical occurrence cancelled (canonical is_cancelled; visible in Track)
9. cancelled occurrence rejects attendance marking (409, cancelled != absent)
10. mid-sem Present becomes an AttendanceRecord (canonical mutation)
11. mid-sem Absent becomes an AttendanceRecord (canonical mutation)
12. practical percentage changes correctly through the canonical summary (recorded-only: 1/2 = 50%)
13. overall analytics follow canonical rules (cancelled excluded, pending stays pending, current recorded-only: 1/2 = 50%)
14. quiz eligibility does NOT include practical attendance (labs 404; theory eligibility byte-identical before/after)
15a. deactivating MID_SEM_PRACTICAL clears the designation (attendance records preserved)
15b. deactivating LAB_CANCELLED events un-cancels the occurrences (reversible state-based reconciliation)
15c. mid-sem on a non-lab day materializes exactly ONE extra practical occurrence (designated, available for attendance)
15d. deactivating the non-lab-day mid-sem removes the unattended extra (state-based reconciliation, no residue)
16. event date movement reconciles old and new dates (old designation cleared, new date designated)
16b. after move: no designation on old date, exactly one on new date
17a. duplicate event creation → 409 (deterministic duplicate guard)
17b. MID_SEM + LAB_CANCELLED on the same date resolved deterministically (cancellation wins: cancelled, no designation)
18. attended sessions are protected (attendance never deleted; attended mid-sem session not cancelled by later LAB_CANCELLED)
19. no fabricated experiment data (laboratory tables empty before and after)
20. existing event types remain functional (admin EXTRA_LECTURE creates exactly one extra lecture)
21a. Phase 8.2 mid-sem endpoint remains admin-only (student PUT → 403)
21b. Phase 8.2 admin mid-sem designation + summary fields still work (health + mid-sem exposure intact)
22. database restored to the exact baseline (events/sessions/cancelled/extra/records/enrollments/subjects/quizzes/users/admins/lab tables/designations)

### Frozen regressions (run WITHOUT modification; none weakened)

| Verifier | Result |
|---|---|
| verify_phase_6_5.py | 27/27 PASS |
| verify_phase_6_6.py | 36/36 PASS |
| verify_phase_6_7.py | 31/31 PASS |
| verify_phase_7_1.py | **25/26** — check 23 `records == 92` fails at **95** (BASELINE DRIFT, §9; verifier untouched) |
| verify_phase_7_2.py | 26/26 PASS |
| verify_phase_8_1.py | 22/22 PASS |
| verify_attendance_spec_alignment.py | 15/15 PASS |
| verify_phase_8_2.py | 18/18 PASS |

### Static verification

- `python -m compileall app scripts` — PASS
- `npx tsc --noEmit` — PASS
- ESLint on changed frontend files — PASS
- `next build` — PASS (14 routes)

No browser/E2E verification was performed (manual testing remains the user's
responsibility).

## 11. Exact files changed

**Backend**
- `backend/app/models/enums.py` — `EventType.MID_SEM_PRACTICAL`,
  `EventType.LAB_CANCELLED`.
- `backend/app/models/event.py` — nullable `note` column on `AcademicEvent`.
- `backend/alembic/versions/a1b2c3d4e5f6_add_lab_event_types.py` — NEW
  migration (eventtype enum + `note` column; applied; zero data rows changed).
- `backend/app/services/event_registry.py` — rules for both types
  (subject-scoped, PRACTICAL-only).
- `backend/app/services/event_service.py` — both types added to
  `STUDENT_CREATABLE_EVENT_TYPES`.
- `backend/app/engines/calendar_engine.py` — priority 30 for both types
  (per-occurrence tier).
- `backend/app/services/event_session_service.py` — LAB_CANCELLED joins
  `CANCELLATION_TYPES`; mid-sem desired-schedule plan; `_designate_mid_sem` /
  `_clear_mid_sem`; cancellation-wins conflict; reuse-or-materialize-one-extra;
  mid-sem management gated to the triggering event type.
- `backend/app/schemas/attendance.py` — additive `designation` on
  `AttendanceHistoryItem` and `DailySessionResponse`.
- `backend/app/repositories/attendance_repo.py` — `designation` added to the
  two read-model queries.
- `backend/app/services/attendance_service.py` — maps `designation` into the
  history and daily responses.
- `backend/app/schemas/calendar.py` — `note` on
  `AcademicEventResponse/Create/Update`.
- `backend/scripts/verify_phase_9_1.py` — NEW verifier (28 checks).

**Frontend**
- `frontend/src/types/api.ts` — `EventType` values, `designation` on session
  types, `note` on event payloads.
- `frontend/src/components/events/eventRules.ts` — LAB_CANCELLED /
  MID_SEM_PRACTICAL form rules.
- `frontend/src/components/events/EventFormDialog.tsx` — auto-fills class
  type P for lab types; optional note/reason field.
- `frontend/src/components/events/EventRow.tsx` — display names/labels for
  the new types.
- `frontend/src/components/dashboard/TrackSessionCard.tsx` — "Mid-Sem
  Practical" label for designated sessions; cancelled "Lab" state disabled
  from marking.

**No other files changed.** (`.freebuff/*` and regenerated `__pycache__`
files are environment artifacts present before this phase.)

## 12. Deliberately NOT implemented (per scope)

- No experiment curriculum / names / numbers / titles / counts (laboratory
  tables stay empty — nothing fabricated).
- No experiment-progress tracking, no `experiments ≥ 5 ⇒ mid-sem` rule, no
  auto-designation, no experiment prerequisites for attendance.
- No FACULTY role; no grading/viva/marks workflow.
- No second lab attendance engine, no lab attendance tables, no new
  mid-sem/lab-cancellation endpoints (reuses `/events` + the canonical
  mutation path).
- No changes to the frozen attendance engine, quiz eligibility formulas,
  overall attendance formulas, event authorization policy, or Phase 6
  calendar architecture.
- No period selector in the UI: the backend deterministically resolves the
  occurrence (first P slot by timetable start time, then id) — the frontend
  never asks the student to pick a lab turn.

## 13. Known limitations

- **Baseline drift (§9)**: 7.1 check 23 fails until the owner authorizes the
  fixture 92 → 95. Phase 9.1's own verifier and all other frozen verifiers
  are green.
- A mid-sem on a date where the subject's practical occurrence is already
  attended cannot be re-designated away by events (attendance safety) — the
  designation clears but the session and record remain; this is the intended
  historical-truth behavior.
- Two same-day P slots for one subject resolve to the earliest slot; the
  choice is deterministic but not user-visible (documented in §4).
- `MID_SEM_PRACTICAL` events do not require the subject to be a lab subject
  at creation time beyond the PRACTICAL class type; enrollment is checked,
  and the synchronizer resolves whatever practical occurrence exists.
- Experiment management remains entirely absent by design (future phase).

## 14. Manual browser checklist (for the user)

A. `/tools/events` — Add Event: select BCS-553 (practical), Event Type shows
   **Mid-Sem Practical** and **Lab Cancelled**; class type auto-fills P; note
   field optional. Create each for an enrolled date → 201. Verify an
   unenrolled subject isn't selectable/rejected with 403.
B. Track / Attendance page (daily view):
   - Mid-sem day → the practical session is labeled **Mid-Sem Practical**;
     mark Present and Absent; both flow into the subject's practical
     percentage.
   - Lab-cancelled day → the practical occurrence shows **Cancelled** and is
     disabled from marking.
   - Non-lab day + mid-sem event → exactly one extra practical appears,
     designated; deactivating the event removes it.
C. `/subjects` — lab subject card practical attendance updates after
   Present/Absent; mid-sem designation appears naturally in the practical
   counts (no quiz-strategy clutter).
D. `/tools/quiz-schedule` — unchanged: must-attend/safe-skip/forecast still
   present; labs remain excluded from eligibility.
E. Reversibility — deactivate or move a Mid-Sem/Lab-Cancelled event and
   confirm Track returns to the canonical timetable state and attendance
   records are never deleted.
F. Conflict — create Mid-Sem and Lab Cancelled on the same date: the
   occurrence is cancelled (cancellation wins), no designation.

## 15. Is Phase 9.1 genuinely FREEZABLE?

**Code-wise: YES** — the Phase 9.1 verifier is 28/28, every frozen regression
is green, static gates pass, and the canonical pipeline is untouched. The
**one blocking item is the baseline-policy decision** on `verify_phase_7_1`
check 23 (records 92 → 95, §9), which is owner-authorized fixture drift — not
a Phase 9.1 code issue. Until the owner decides, Phase 9.1 freezes with 7.1 at
25/26 as a documented known-failing baseline assertion.

---

**HARD STOP — Phase 9.1 implementation complete. Phase 9.2 (experiment
management) NOT started. No commit made.**
