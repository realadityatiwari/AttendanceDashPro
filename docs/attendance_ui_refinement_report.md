# Attendance UI Refinement — Specification Alignment + Reference UI

**Result:** PASS (all verification green; no commit made)

This phase aligned the AttendanceDash Pro implementation with the authoritative
attendance specification and implemented the reference attendance UI on the
existing Attendance (/subjects) surface. Two product decisions were escalated
to the user and explicitly authorized before implementation (see §4); nothing
else crossed a hard boundary.

---

## 1. Specification rules inspected

| Rule | Verdict |
|---|---|
| Daily attendance marked for lectures and tutorials | Already satisfied — attendance_records on L/T class sessions |
| Avg Attendance = (Lecture % + Tutorial %) / 2; no tutorials → Lecture % only | Already satisfied — `current_avg_pct` / `forecast_avg_pct` (attendance engine `_combined` semantics) |
| Practicals: one attendance event; count in attendance marking + overall; excluded from quiz eligibility | Already satisfied — practical sessions markable, included in the overall scan, `quiz_applicable=false` |
| Overall = Σ attended events / Σ total events × 100 (class-weighted, incl. practicals) | Already satisfied — analytics `_overall` (ERP semantics); pending stays pending (recorded-only current + pending-as-attended forecast, per "do not invent pending behavior") |
| **Quiz-day attendance is a real attendance event** (recorded for the subject, contributes to subject + overall) | **CONFLICT → resolved**: 6 of 18 scheduled quiz dates had zero sessions; quiz-day sessions materialized (§4-A) |
| Surprise quizzes can happen any day (flexible events) | Already supported by the SURPRISE_QUIZ event type (injects a session on any day) |
| **Events are student-adjustable** (add/remove per what actually happened) | **CONFLICT → resolved**: admin-only mutations relaxed to student subject-scoped control (§4-B) |
| Calendar day view shows the complete schedule (classes + labs + events) | Already satisfied — calendar read model + DayDetail |
| React must not calculate attendance/eligibility/optimization | Respected — all rendered values are backend fields; React formats/expands only |

## 2. Reference UI features implemented

The Attendance page (nav "Attendance" → `/subjects`) subject cards now follow
the reference structure (same visual language as the approved Quiz Eligibility
cards — Card/Badge/Progress/tabular-nums, no new color system):

- **Header** — subject code (mono), THEORY/LAB badge, subject name, canonical
  current status badge (SAFE/WATCH/CRITICAL, backend-emitted), quiz
  eligibility badge (unchanged, existing behavior).
- **Primary attendance** — prominent percentage (combined average for theory,
  practical % for lab-only), attended/total, status-colored progress bar.
- **Lecture section** — lecture %, attended/total, current %, required (75%,
  backend-emitted), must-attend + safe-skip (backend optimizer).
- **Tutorial section** — same (only when the subject has tutorials).
- **Combined average** — subject average per the spec formula with an explicit
  caption ("Average = (Lecture % + Tutorial %) / 2"; "No tutorials — average
  equals Lecture %").
- **Expandable "View Details"** — functional expand/collapse exposing real
  backend values: current vs forecast per class type with attended/total and
  pending, the optimizer must-attend/safe-skip breakdown with reachability,
  and the recorded-only/forecast note.
- **Practicals** — lab-only subjects present practical-specific information
  (current %, attended/total, pending, forecast in details); no lecture/
  tutorial calculations forced onto them.

## 3. Backend/engine changes

- **`attendance_engine.py`** — canonical banding relocated here (single
  definition): `ATTENDANCE_TARGET_PCT`, `WATCH_BAND_PCT`, `SAFE_BAND_PCT`,
  `classify_attendance_status`. Dashboard + analytics + subject summaries all
  consume this one definition (no duplication, no new formula).
- **`schemas/attendance.py`** — `SubjectAttendanceSummary` gains two additive
  fields: `required_pct` (75.0) and `status` (SAFE/WATCH/CRITICAL/None). No
  existing field renamed or removed.
- **`attendance_service.py`** — `_build_subject_summary` emits `required_pct`
  and `status` (banding on the canonical current average).
- **`event_service.py` / `event_repo.py` / `events.py`** — student event
  authorization: `STUDENT_CREATABLE_EVENT_TYPES` (EXTRA_LECTURE, EXTRA_
  TUTORIAL, EXTRA_PRACTICAL, CLASS_CANCELLED, SURPRISE_QUIZ); students may
  create/update/deactivate those for their **own enrolled subjects**;
  global/closure/quiz-schedule events remain admin-only (403). Enrollment
  check reuses the established repository pattern (`is_enrolled`).
- **`event_session_service.py`** — synchronizer guard: sessions with
  `timetable_entry_id IS NULL` and `is_extra = false` (quiz-day sessions) are
  never cancelled or deleted by event reconciliation (attendance-safety
  preserved; the existing attended-session protections are untouched).
- **`endpoints/attendance.py`** — fixed a latent defect found by inspection:
  `AttendanceMutationResponse.student_id` did not exist on the model
  (`user_id`), so every *successful* attendance mutation 500'd during response
  serialization (the frozen verifiers only exercised the 403/409 paths, so it
  was never caught). Renamed to `user_id`. Required for quiz-day attendance to
  be recordable.

## 4. Specification conflicts found + authorized decisions

**A. Quiz-day attendance (spec: "real attendance event").** 6 of 18 scheduled
quiz dates had no class session (incl. BCS-054 Quiz III = 2026-10-23), so
quiz-day attendance could not be recorded. **User decision: materialize
quiz-day sessions.** Implemented via `backend/scripts/materialize_quiz_day_
sessions.py` (idempotent, reversible with `--undo`, driven entirely by the
authoritative quiz_schedules — never invents dates): 7 LECTURE sessions
created on quiz dates that lacked one (`timetable_entry_id IS NULL`,
`is_extra = false`). Because eligibility windows end at `quiz_date − 1`,
these sessions sit **outside** every eligibility window — they affect only
subject + overall attendance, exactly per spec. Sessions: 684 → 691
(documented, deliberate baseline change; the frozen verifiers capture the
baseline dynamically).

**B. Event mutability (spec: "Events are intentionally student-adjustable").**
The frozen Phase 6.5 architecture was admin-only for all event mutations
(asserted in verify_phase_6_5 checks 3–5 and verify_phase_7_2 check 10).
**User decision: shared schedule, subject-scoped** — students may add/remove
flexible subject-scoped events for their own enrollments; global/closure
events stay admin-only; attendance-safety preserved. The frozen assertions
were updated **deliberately and documented** (see §8): the checks now assert
the new policy (student enrolled-subject extra → 201; global → 403;
non-enrolled subject → 403) rather than blanket 403s.

## 5. APIs reused

- `GET /api/v1/analytics/overview` (per-subject analytics feed, one request
  for the whole grid — no N+1)
- `GET /api/v1/attendance/summary/{code}` (extended summary with the additive
  fields)
- `GET /api/v1/quiz-eligibility/current-cycle` (canonical date-aware cycle —
  no hardcoded cycle)
- `GET /api/v1/quiz-eligibility/{code}/{cycle}` (eligibility badge, unchanged)
- `GET /api/v1/subjects` (enrollment-scoped subject list for the event form)
- `POST/PATCH/DELETE /api/v1/events` (now student-authorized for flexible
  subject-scoped types)
- `POST /api/v1/attendance` (now returns the record correctly)

## 6. Formulas reused (none invented)

- Combined average (L% + T%)/2 and L%-only fallback — attendance engine
- ERP overall Σatt/Σrecorded (recorded-only) and forecast (pending-as-attended)
- 75% subject optimizer (must-attend = deficit, safe-skip = safe_skip_*) —
  attendance engine `optimize_attendance`
- SAFE ≥ 80 / WATCH ≥ 60 / CRITICAL < 60 banding — relocated canonical
  definition (same thresholds as before)
- Eligibility criteria — untouched (quiz-day sessions are outside windows)

## 7. Files changed

Backend:
- `app/engines/attendance_engine.py`
- `app/schemas/attendance.py`
- `app/services/attendance_service.py`
- `app/services/event_service.py`
- `app/services/event_session_service.py`
- `app/services/dashboard_service.py` (imports the relocated banding)
- `app/services/analytics_service.py` (same)
- `app/repositories/event_repo.py`
- `app/api/v1/endpoints/events.py`
- `app/api/v1/endpoints/attendance.py`
- `scripts/materialize_quiz_day_sessions.py` (new)
- `scripts/verify_attendance_spec_alignment.py` (new)
- `scripts/verify_phase_6_5.py` (deliberate assertion update)
- `scripts/verify_phase_7_2.py` (deliberate assertion update)
- `scripts/verify_phase_7_1.py` (deliberate assertion update — check 5)
- `scripts/verify_phase_6_7.py` (baseline comment update)

Frontend:
- `src/types/api.ts` (additive `required_pct` / `status`)
- `src/components/dashboard/SubjectAttendanceCard.tsx` (reference redesign)
- `src/components/events/EventFormDialog.tsx` (student type restriction)
- `src/components/events/eventRules.ts` (student-creatable set mirror)
- `src/app/(authenticated)/tools/events/page.tsx` (student management surface)

## 8. Verification results

- `verify_attendance_spec_alignment.py` (new) — **15/15 PASS**
- Frozen regressions (re-run, all green):
  - `verify_phase_6_5.py` — **27/27** (student event checks deliberately
    re-scoped to the new policy)
  - `verify_phase_6_6.py` — **36/36**
  - `verify_phase_6_7.py` — **31/31**
  - `verify_phase_7_1.py` — **26/26** (check 5 deliberately updated: the
    QUIZ_DAY event remains calendar-only — no event-created sessions — while
    the schedule-materialized quiz-day session now legitimately exists)
  - `verify_phase_7_2.py` — **26/26** (check 10 deliberately re-scoped)
  - `verify_phase_8_1.py` — **22/22**
- `python -m compileall app scripts` — PASS
- `npx tsc --noEmit` — PASS (0 errors)
- ESLint on all changed frontend files — PASS
- `npm run build` — PASS (14 routes)
- No browser/E2E automation run (manual testing remains the user's task)

## 9. Database mutation status

**Documented, authorized, minimal data correction** (the user approved quiz-day
session materialization): `class_sessions` 684 → **691** (7 quiz-day sessions,
`timetable_entry_id IS NULL`, `is_extra = false`, `class_type = LECTURE`,
non-cancelled, no attendance records). Reversible via
`python scripts/materialize_quiz_day_sessions.py --undo`.

Final baseline: events=18 · sessions=691 (0 cancelled, 0 extra) · records=89 ·
enrollments=18 · subjects=9 · quiz_schedules=18 (18 SCHEDULED) · users=30
(1 ADMIN). BCS-054 Quiz III = 2026-10-23 unchanged. No other table touched.

## 10. Unresolved questions / notes

- **Quiz-day session class type**: materialized as LECTURE (every
  quiz-applicable subject is a theory subject with lectures). If a future
  product decision wants a distinct "quiz" class type, that requires a schema
  change and would be a separate decision.
- **Student events are shared**: a student's flexible event affects the shared
  schedule for everyone enrolled in that subject (per the authorized
  "shared schedule, subject-scoped" decision). Abuse potential exists by
  design (spec: deliberate product feature); global/closure events remain
  admin-only, and attendance-safety rules (attended sessions never cancelled/
  deleted) are preserved.
- The `AttendanceMutationResponse` rename (`student_id` → `user_id`) fixes a
  latent 500; no consumer depended on the old (never-successfully-serialized)
  shape.

## 11. Explicit non-goals (preserved)

No AT-RISK taxonomy, no trend product semantics (T-2), no dedicated Analytics
page (T-3), no multi-class forecast wording (T-4), no Q-D9, no rule G, no new
attendance/eligibility formulas, no schema/migration, no quiz-cycle hardcoding
in React, no frozen Phase 6/7 engine mathematics changed.
