# Phase 22.4 — Departmental Elective Resolution Across All Engines & Surfaces

**Date:** 2026-08-26  
**Status:** Implementation COMPLETE (dev DB verified); production migration pending operator  
**Migration:** `b7c8d9e0f1a2` (down_revision `a3b4c5d6e7f8`)

---

## Objective

Departmental Elective-I and Elective-II are LOGICAL SLOTS. The system must
treat them as two logical slots and resolve each slot to the concrete subject
selected by the individual student. The selected concrete subject must be
reflected consistently everywhere that subject identity is applicable — quiz
schedule, academic events, event-created sessions, dashboard, notifications,
calendar, analytics, history — while the existing shared schedule, dates,
quiz cycles, class sessions, event dates, and attendance/eligibility formulas
remain untouched.

---

## Authoritative Catalog

### Elective-I
- BCS-052 — Data Analytics
- BCS-053 — Computer Graphics
- BCS-054 — OOS Design with C++

### Elective-II
- BCS-055 — Machine Learning Techniques
- BCS-056 — Application of Soft Computing
- BCS-058 — Data Warehousing & Data Mining

These are hard constraints. No other subjects are allowed. No cross-slot
selection is permitted.

---

## Core Semantic Model

- Departmental Elective-I and Elective-II are LOGICAL SLOTS. They are not
  user-facing subject names. The student's selected concrete subject is the
  effective subject.
- The shared institutional schedule (timetable, class sessions, quiz schedules,
  academic events) keeps concrete anchor subjects (BCS-054 for Elective-I,
  BCS-058 for Elective-II) and marks the slot via an `elective_slot` column.
- Per-student resolution: `StudentElectiveChoice` → slot-specific resolver →
  effective concrete subject. Missing choice → shared anchor (no fabrication;
  ADMIN keeps anchors).

---

## Architecture

### Authoritative Resolver

`backend/app/services/elective_resolver.py` — the single source of truth.

**Catalog constants:**
- `ELECTIVE_I_CODES`, `ELECTIVE_II_CODES`, `ALL_ELECTIVE_CODES`
- `ANCHOR_CODES` (BCS-054 → ELECTIVE_I, BCS-058 → ELECTIVE_II)
- `validate_selection(code_i, code_ii) → error | None`
- `slot_for_code(code) → ElectiveSlot | None`

**`ElectiveResolver` class:**
- `load_choices(user_id) → Dict[ElectiveSlot, StudentElectiveChoice]` — one
  query with selectinload(Subject).
- `chosen_elective_map(user_id) → Dict[UUID, ElectiveSlot]` — subject_id → slot.
- `anchor_subjects() → Dict[ElectiveSlot, Subject]` — the two shared anchors.
- `resolve_subject(choice_map, slot, fallback) → Subject` — in-memory.
- `resolve_events(events, choice_map) → list` — resolve `resolved_subject_*`
  on event ORM rows (2 queries: choices + subjects).

### Database Changes

Three nullable `elective_slot` columns added (ENUM `ELECTIVE_I` / `ELECTIVE_II`,
reusing the existing `electiveslot` type from Phase 22.3):

1. **`quiz_schedules.elective_slot`** — marks which quiz schedule entries
   belong to a logical slot. Backfilled from the subject's tag.
2. **`academic_events.elective_slot`** — marks events scoped to a logical
   slot. The shared anchor subject stays in `subject_id`; `elective_slot` is
   the resolution key. ADMIN-only on creation; mutually exclusive with
   `subject_id`; lab-only event types rejected.
3. **`class_sessions.elective_slot`** — marks sessions materialized for a
   slot (event-created extras, quiz-day with no timetable link). Backfilled
   from the subject's tag. Enables the attendance repo's COALESCE join
   predicate.

### Attendance Repo Predicates

- `_elective_choice_on(user_id)`: ON clause joins `StudentElectiveChoice` on
  `COALESCE(TimetableEntry.elective_slot, ClassSession.elective_slot)`.
- `_resolved_subject_match(subject_id)`: WHERE clause matches sessions whose
  `COALESCE` slot is non-null AND the student's choice for that slot equals
  the requested subject, OR the session's concrete subject matches directly.

### Quiz Dates

- `get_effective_quiz_dates_for_subjects(subject_ids, elective_scope)`: one
  query fetches active QUIZ_DAY events for both regular subjects (by
  subject_id) and slot subjects (by elective_slot). A subject in the elective
  scope resolves its dates from the slot's events; every other subject uses
  its own events. Dates/cycles are the existing authoritative schedule.

### Events

- `AcademicEventCreate` / `AcademicEventUpdate` accept `elective_slot`
  (mutually exclusive with `subject_id`; ADMIN-only; lab-only types rejected).
- The service resolves the shared anchor subject (BCS-054/058) and stores
  both `subject_id`=anchor and `elective_slot`=slot.
- Read endpoints (list, create, update, deactivate, calendar month/day) resolve
  `resolved_subject_id/code/name` per authenticated user.
- `EventSessionSynchronizer` tracks slot markers for extras and quiz-days,
  sets `ClassSession.elective_slot` on created sessions.

---

## Records Classified as Elective Slots

### quiz_schedules (6 rows)
- BCS-054 ×3 (09-07, 09-28, 10-23) → ELECTIVE_I
- BCS-058 ×3 (09-11, 10-05, 10-26) → ELECTIVE_II

### academic_events (14 rows on BCS-054/058)
- BCS-054 QUIZ_DAY ×3 (09-07, 09-28, 10-23) → ELECTIVE_I
- BCS-058 EXTRA_LECTURE 07-17 (active) → ELECTIVE_II
- BCS-058 CLASS_CANCELLED 07-29 ×3 (1 active, 2 inactive) → ELECTIVE_II
- BCS-058 CLASS_CANCELLED 07-30 ×2 (1 active, 1 inactive) → ELECTIVE_II
- BCS-058 SURPRISE_QUIZ 08-06 (active) → ELECTIVE_II
- BCS-058 EXTRA_LECTURE 08-17 (inactive) → ELECTIVE_II
- BCS-058 QUIZ_DAY ×3 (09-11, 10-05, 10-26) → ELECTIVE_II

### class_sessions (205 rows)
- BCS-054: 102 sessions (including 3 quiz-day with no timetable link)
- BCS-058: 103 sessions (including 5 extras/quiz-day with no timetable link)

All existing dates, cycles, and session occurrences are preserved.

---

## Verification

71/71 checks PASS on the dev DB:

1. **Schema + backfill** — 3 columns exist; 6 quiz schedules, 14 events, 205
   sessions marked; zero unmarked anchor sessions.
2. **Catalog** — exactly 3 EI + 3 EII codes; cross-slot rejection.
3. **Fixture students** — A (BCS-052/BCS-056) and B (BCS-053/BCS-055) created,
   committed, exercised, then removed.
4. **Resolver** — same slot → different subjects per student; no-choice user
   falls back to anchor.
5. **Timetable** — same entry, different resolved subject.
6. **Quiz** — same slot dates, different subject per student; eligibility
   computed with correct subject_name; dates/cycles unchanged.
7. **Attendance** — slot sessions count toward chosen subject; same logical
   occurrences for both students; no leakage; admin keeps anchor.
8. **Daily/History** — concrete subject displayed; no cross-student leakage.
9. **Dashboard scan** — resolved subjects propagated.
10. **Events** — same event resolves to different subjects per student.
11. **Admin slot-event creation** — Extra Lecture + Quiz Day against slots
    (201); synchronizer slot-marks created sessions; student slot rejection
    (403); API GET resolves anchors.
12. **Regular subjects** — BCS-501 counts identical for both students.
13. **Cleanup** — baseline restored (fixtures + artifacts removed).

---

## Production / Operator Boundary

- **No production writes were performed.** The migration was applied to the
  local dev DB only (docker `attendancedashpro_db`, port 55432).
- **Operator action (sequential):** first apply Phase 22.3
  (`a3b4c5d6e7f8`), then Phase 22.4 (`b7c8d9e0f1a2`). Downgrade (Phase 22.4):
  `alembic downgrade a3b4c5d6e7f8`.
- **Existing users:** the only existing account (admin) has no choices and
  keeps anchors. No fabrication, no silent assignment. Any future legacy
  student without choices also keeps the anchor representation (documented
  remediation path: operator assigns choices via direct insertion or the
  student re-registers).
- **Frozen contracts preserved:** attendance/eligibility/calendar formulas
  unchanged; no per-student schedule/event/session duplication; no auth/JWT
  changes; no Phase 22.1/22.2/22.3 work reopened.