# Phase 6.0 — Calendar & Academic Events Audit

**Date:** 2026-08-14 · **Mode:** READ-ONLY audit · **Status:** COMPLETE — no implementation performed

> **Follow-up status (2026-08-14, Phase 6.1 COMPLETE):** the defects PROVEN in this audit were
> corrected in Phase 6.1 — (1) weekend mapping now uses a single engine-owned constant
> `DEFAULT_WEEKENDS = [0, 6]` (JS getDay indices) in `backend/app/engines/calendar_engine.py`,
> consumed by `CalendarService` and `EligibilityService`; (2) `MID_SEMESTER_BREAK` added to the
> engine's closure list; (3) `GET /api/v1/events` gained a server-side `active` (default true),
> `date_from`/`date_to` (range-overlap), and `upcoming` filter contract; (4) dashboard aggregation
> (`get_sessions_with_status`) is now enrollment-scoped. See `task.md` / `implementation_plan.md` /
> `walkthrough.md` Phase 6.1 sections. Audit findings 5–10 (timetable section scoping, engine
> type-hint mismatch, legacy window-field restoration, TodayClassesCard cleanup, `active` DB
> default, uniqueness constraint) remain open by design and are tracked in §18/§15.

**Evidence labels used throughout:**
- **PROVEN** — verified by code inspection, live read-only SQL, or direct execution of the actual engine code.
- **INFERRED** — strongly implied by code/docs but not executed or not exercised with real data.
- **UNKNOWN** — no evidence exists in the repository.

**Verification performed (all read-only):**
- Read `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md`, and the calendar/event docs (`docs/05_CALENDAR_ENGINE.md`, `docs/09_ACADEMIC_EVENT_SYSTEM.md`, `docs/S4.3_ACADEMIC_EVENTS_ENGINE.md`, `docs/18_ARCHITECTURE_DECISION_RECORDS.md`, `docs/20_DATA_DICTIONARY.md`, `backend/MIGRATION_AUDIT.md`, `backend/MIGRATION_NOTES.md`, `backend/DATABASE_DESIGN.md`, `docs/phase_4_5_data_audit.md`).
- Inspected all backend models, engines, services, repositories, schemas, endpoints, and all three Alembic migrations.
- Inspected all frontend routes, hooks, types, and dashboard components.
- Inspected the legacy JS implementation (`js/calendar-engine.js`, `js/events-controller.js`) and its tests (`js/test-calendar-engine.js`, `js/test-calendar-window.js`, `js/test-events-controller.js`).
- Queried the live PostgreSQL database with read-only SQL (container `attendancedashpro_db` was started — no data touched).
- Executed the actual Python calendar engine with ORM-shaped objects to confirm behavior (no files changed).

---

## 1. Executive Summary

Phase 6 (Calendar & Academic Events) is the **next phase** per `MASTER_ROADMAP.md`, and the repository already contains a **read-only calendar/event skeleton** built in the early commits (`ffd53f6`, `a429bae`, `6c8a80e`) and **never completed**.

What exists today:

- A Python calendar engine (`backend/app/engines/calendar_engine.py`) ported from the legacy `js/calendar-engine.js`, with day resolution, event priority, teaching-day iteration, and quiz attendance windows.
- An `academic_events` table (`backend/app/models/event.py` + migration `7117a007a0da`) with 14 event types, date range, optional subject/class-type scoping, `is_working_day`, `substitution_schedule_override`, and `active`.
- Three read-only endpoints: `GET /api/v1/calendar/today`, `GET /api/v1/calendar/{date}`, `GET /api/v1/events`.
- Dashboard integration: `Today` section consumes the calendar day (`is_working_day`, `is_teaching_day`, `day_note`), and `Upcoming Events` consumes the events table (empty-state only today).
- Quiz eligibility consumes the engine's `get_attendance_window` (the window bounds only).
- A frontend `/tools/events` page (read-only list, real API) and a **dead** `TodayClassesCard` component.
- Legacy (JS) engine logic with **proven, documented behavior** (event deltas, effective day schedule, soft-delete lifecycle, single-authority event ownership) and passing tests.

What is broken (PROVEN):

1. **Weekend-mapping defect:** `CalendarService` and `EligibilityService` pass `default_weekends=[5, 6]` (Python weekday indices) but the engine converts the date to JS day-of-week indices before checking. **Friday resolves as non-working and Sunday resolves as working.** Verified by executing the real engine. This corrupts `is_working_day`/`is_teaching_day` in every calendar response and in the dashboard Today section.
2. `GET /api/v1/events` returns **inactive and past events** with no filtering.
3. The dashboard aggregation query `get_sessions_with_status` is **not enrollment-scoped** (benign today only because every user is enrolled in all 9 semester subjects).
4. `TimetableRepository.get_weekly_entries_for_section` **ignores `section_id`** and `timetable_entries` has no section column — section-scoped schedules are impossible with the current schema.
5. The engine's annotations claim Pydantic schema objects while runtime objects are ORM (`subject_code` vs `subject_id` split); it works only because the engine touches overlapping fields. Fragile.
6. The Python `get_attendance_window` dropped legacy window fields (`holidayCount`, `weekendCount`, `workingDays`, `activeMilestones`).
7. `MID_SEMESTER_BREAK` has closure priority (60) but is **not** in the engine's closure list — it will not flip a day non-working unless `is_working_day=false` is set manually.

What is missing (the real Phase 6 work):

- **No calendar UI** (no month/day grid, no navigation, no Today shortcut, no date picker).
- **No event mutation endpoints** (no POST/PUT/DELETE `/events`; the endpoint docstring says "Mutation is explicitly out of scope for students").
- **No admin/role authorization** anywhere (User has no role column; `get_current_user` returns any authenticated user).
- **No event validation registry** (legacy `AcademicEventRegistry` was never ported; 4 of the 14 enum values have no metadata/UI anywhere).
- **Events do not feed the attendance/eligibility engines.** Attendance and quiz counts read pre-generated `class_sessions` rows; an event only changes the calendar-day status, never the session set. The roadmap's "event system must feed the existing engines" is **not implemented**.
- No event seeding (table is empty: **0 rows**).
- Events are **global** — no session/semester/section scoping exists in the schema.

**Recommendation:** proceed with Phase 6 in sub-phases (6.1 → 6.7, see §18). The first sub-phase must fix the weekend-mapping defect and define the event-read contract before any calendar UI is built on top of it.

---

## 2. Current Architecture

### Data flow today (read side)

```
PostgreSQL
  academic_events (EMPTY) ──► CalendarRepository.get_all_events()
                                  │
        ┌─────────────────────────┴──────────────────────────┐
        ▼                                                    ▼
  CalendarService.get_day_schedule              EligibilityService (window bounds)
        │  default_weekends=[5,6]                            │  default_weekends=[5,6]
        ▼                                                    ▼
  calendar_engine.get_academic_day                calendar_engine.get_attendance_window
        │                                                    │
        ▼                                                    ▼
  GET /api/v1/calendar/today · /{date}            GET /api/v1/quiz-eligibility/{code}/{cycle}
        │
        ▼
  DashboardService._build_today (is_working_day / is_teaching_day / day_note)
  DashboardService._build_upcoming_events (Upcoming Events card — subject-scoped)
```

- **Calendar read path:** `CalendarRepository.get_all_events()` → ORM `AcademicEvent` rows → `CalendarService.get_day_schedule(date)` → `calendar_engine.get_academic_day(date, events, default_weekends)` → `AcademicDayResponse`. PROVEN (`backend/app/services/calendar_service.py:13-17`, `backend/app/repositories/calendar_repo.py:9-12`, `backend/app/engines/calendar_engine.py:49-91`).
- **Event read path:** `GET /api/v1/events` → `CalendarRepository.get_all_events()` → `List[AcademicEventResponse]`. PROVEN (`backend/app/api/v1/endpoints/events.py:15-22`).
- **Quiz window path:** `EligibilityService.get_quiz_eligibility` builds a Pydantic domain `Subject` (with `Timeline` from `QuizSchedule` rows), calls `calendar_engine.get_attendance_window(domain_subject, milestone_id, events, default_weekends)` to get `window_start`/`window_end`, then counts attendance via `AttendanceRepository.get_subject_counts_between`. PROVEN (`backend/app/services/eligibility_service.py:69-81`, `backend/app/engines/eligibility_engine.py:52`).

### What the roadmap requires (Phase 6, `MASTER_ROADMAP.md`)

- Calendar: month/day navigation, working days, weekends, holidays, academic events, class schedule, selected date, event indicators.
- Events: Upcoming / Today / Past, event details, event types, holiday indicators, substitution schedules.
- Event persistence: `Admin → Create Event → Academic Events → Calendar Engine → Track / Dashboard / Quiz Eligibility` — "The event system must feed the existing engines instead of creating parallel rules."

### Legacy architecture (reference, `js/`)

- `js/calendar-engine.js` (736 lines per `docs/05_CALENDAR_ENGINE.md`): single temporal authority — `getAcademicDay`, `getEffectiveDaySchedule`, `getSubjectEventDeltas`, `getAttendanceWindow`, `AcademicEventRegistry`, `validateAcademicEvent`, soft-delete lifecycle (`active`/`archived`), priority system (EMERGENCY_CLOSURE 100 … default 10).
- `js/events-controller.js`: exclusive mutation pipeline (`validate → normalize → mutate AppState → persist → syncRuntimeEvents → cloud sync → recalculate → render`) with rollback snapshot (ADR 011).
- Proven legacy behavior tests: `js/test-calendar-engine.js`, `js/test-calendar-window.js`, `js/test-events-controller.js` (12+ S4.3 assertions: exact-date extra lecture/tutorial/practical, subject/class-type-scoped cancellation, holiday removes all opportunities, events never create attendance records directly — they change schedule counts).

---

## 3. Database Schema

### `academic_events` (PROVEN — `backend/alembic/versions/7117a007a0da_initial_schema.py:93-107` + live `\d academic_events`)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | UUID | NOT NULL | PK, no default at DB level |
| `event_type` | enum `eventtype` | NOT NULL | 14 values (see §12) |
| `start_date` | DATE | NOT NULL | |
| `end_date` | DATE | NOT NULL | |
| `subject_id` | UUID | NULL | FK → `subjects.id`; NULL = global event |
| `class_type` | enum `classtype` | NULL | L/T/P; only meaningful with `subject_id` |
| `is_working_day` | BOOLEAN | NULL | Explicit override for the dominant event |
| `substitution_schedule_override` | VARCHAR | NULL | Day-name string (e.g. `'MONDAY'`) |
| `active` | BOOLEAN | NOT NULL | **No DB default** — ORM model default `True` only (`backend/app/models/event.py:20`); raw-SQL inserts without `active` would fail |
| `created_at` / `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Indexes:** PK only (`academic_events_pkey`). No index on `(start_date, end_date)`, `event_type`, or `active` — acceptable at current scale (PROVEN via live `pg_indexes`).

**Constraints:** single FK (`subject_id → subjects.id`). **No unique constraint** on `(event_type, start_date, subject_id, class_type)` — the legacy duplicate check (`js/events-controller.js:63-72`) has no DB or API equivalent in the current architecture. INFERRED risk, not a defect while no mutation path exists.

**No relationship declarations** exist between `AcademicEvent` and `Subject` in `backend/app/models/event.py` — `subject_id` is a bare FK column; no `subject` relationship/`selectinload`. PROVEN.

### Related tables (PROVEN via live SQL)

- `class_sessions`: 684 rows, `2026-07-15 → 2026-12-31`; 417 LECTURE / 121 TUTORIAL / 146 PRACTICAL; **0 cancelled, 0 extra**. Generated Mon–Fri only by `backend/scripts/expand_baseline.py` (timetable days 0–4).
- `timetable_entries`: 28 rows; `day_of_week` ∈ {0,1,2,3,4}; **no section/semester column**.
- `quiz_schedules`: 18 rows (17 SCHEDULED, 1 UNRESOLVED = BCS-054 Q3, `date NULL`).
- `subjects`: 9 · `users`: 30 · `student_enrollments`: 18 · `attendance_records`: 84.
- Alembic at head `c3d4e5f6a7b8` (all three migrations applied).

### Event scoping (PROVEN)

Events are **global** by schema: the only optional scoping is `subject_id` (+ `class_type`). There is **no** `session_id`, `semester_id`, `section_id`, `class_session_id`, or `user_id` column. Section-specific or semester-specific events are impossible without a schema change.

---

## 4. Current Database State

Read-only queries executed against the live `attendancedash` DB (2026-08-14):

| Metric | Value | Label |
|---|---|---|
| `academic_events` total | **0** | PROVEN |
| active / inactive | 0 / 0 | PROVEN |
| events with `subject_id` | 0 | PROVEN |
| events with `substitution_schedule_override` | 0 | PROVEN |
| events with `is_working_day` set | 0 | PROVEN |
| holiday events (any type) | 0 | PROVEN |
| `class_sessions` | 684 (2026-07-15 → 2026-12-31) | PROVEN |
| cancelled / extra sessions | 0 / 0 | PROVEN |
| `timetable_entries` | 28 (days 0–4) | PROVEN |
| `attendance_records` | 84 | PROVEN |
| `quiz_schedules` | 18 (17 SCHEDULED, 1 UNRESOLVED) | PROVEN |

**Conclusion:** the `academic_events` table is empty, matching the Phase 3/5 documentation ("Upcoming Events renders empty state … 0 rows … data gap, not code gap"). The dashboard's Upcoming Events section and the Events page render their empty states because of **absent data, not absent code**. PROVEN.

---

## 5. Calendar Engine

File: `backend/app/engines/calendar_engine.py` (port of `js/calendar-engine.js`).

### Behavior verified (PROVEN by code inspection + direct execution)

- `get_academic_day(target_date, events, default_weekends)`:
  - Converts Python weekday → JS `getDay()` index: `js_dow = (target_date.weekday() + 1) % 7` (line 59).
  - Base working day: `js_dow not in default_weekends` (line 60).
  - Filters events to `start_date <= date <= end_date and active` (line 68).
  - Sorts by `get_event_priority` descending (line 69); dominant event wins.
  - Closure types force non-working: `PUBLIC_HOLIDAY, INSTITUTE_HOLIDAY, FESTIVAL_HOLIDAY, EMERGENCY_CLOSURE, SEMESTER_BREAK` (lines 72-74). **`MID_SEMESTER_BREAK` is absent** (line 72 list) even though it has priority 60 — PROVEN defect (mirrors a legacy gap in `js/calendar-engine.js`).
  - `is_working_day` honored when set on the dominant event (line 76); `substitution_schedule_override` propagated (lines 78-80).
  - `is_teaching_day = is_working_day` (line 88).
- `get_teaching_days_between` (line 93): iterates and collects teaching days.
- `get_attendance_window(subject, milestone_id, events, default_weekends)` (line 111): requires Pydantic `subject.timeline` (domain object, **not** ORM); returns `{subject_code, window_start, window_end, teaching_days, effective_teaching_dates}`.

### PROVEN defect — weekend mapping

- `CalendarService.get_day_schedule` passes `default_weekends = [5, 6]  # Saturday, Sunday` (`backend/app/services/calendar_service.py:15`) — **Python** weekday indices.
- `EligibilityService` passes the same `[5, 6]` (`backend/app/services/eligibility_service.py:74`).
- The engine converts to JS indices **before** the check. Executing the real engine:

```
default_weekends=[5,6]:  Thu 2026-08-13 working=True · Fri 2026-08-14 working=False · Sat 2026-08-15 working=False · Sun 2026-08-16 working=True
default_weekends=[0,6]:  Thu True · Fri True · Sat False · Sun False   ← correct Sun/Sat convention
```

- Friday is wrongly non-working; Sunday is wrongly working. The correct convention (JS `[0, 6]`) is what the legacy engine used and what `backend/scripts/expand_baseline.py:31` used to generate the 684 sessions.
- Impact: every `GET /api/v1/calendar/*` response and the dashboard Today section's `is_working_day`/`is_teaching_day` are wrong for Fridays (shows "non-working") and Sundays (shows "working"). Quiz window `teaching_days` counts are also wrong, though the eligibility **counts** do not depend on them (§6).

### Engine/ORM protocol mismatch (PROVEN)

- Annotations use Pydantic schemas (`app.schemas.academic.AcademicEvent` with `subject_code`; `app.schemas.academic.Subject` with `timeline`) but the runtime event objects are ORM `AcademicEvent` (with `subject_id`, no `subject_code`, no `version`/`metadata`). It works for `get_academic_day` only because the engine touches overlapping fields (`start_date`, `end_date`, `active`, `event_type`, `is_working_day`, `substitution_schedule_override`) — verified by executing the engine with ORM-shaped objects.
- `get_attendance_window` **requires** the Pydantic `Subject`; it would crash on an ORM `Subject` (no `.timeline`). PROVEN by code inspection.

### Legacy divergence (PROVEN by comparison)

Python `get_attendance_window` returns `teaching_days`/`effective_teaching_dates` but drops the legacy `holidayCount`, `weekendCount`, `workingDays`, `activeMilestones` fields (`js/calendar-engine.js` `getAttendanceWindow`). The Python engine also has **no** `getEffectiveDaySchedule`, **no** `getSubjectEventDeltas`, and **no** `validateAcademicEvent`/`AcademicEventRegistry` — the legacy mechanisms by which events actually mutated schedules.

### What the engine handles / does not handle

| Concern | Status |
|---|---|
| Weekdays/weekends | PROVEN broken (see above) |
| Active/inactive events | Handled (`e.active` filter, line 68) — PROVEN |
| Date ranges / overlapping events | Handled — priority + range filter; ties resolved by `start_date` sort order (repo) — PROVEN (INFERRED determinism for equal priorities) |
| Working Saturday/Sunday | Modeled (`WORKING_SATURDAY`, `WORKING_DAY_OVERRIDE` priorities 80/90) but **unreachable in practice** — events table empty; requires `is_working_day` set by creator with no validation layer — PROVEN |
| `substitution_schedule_override` | Propagated to `AcademicDay` — PROVEN; consumed by the **dead** `TodayClassesCard` and by `expand_baseline.py`; nothing else renders a substituted schedule |
| Extra lectures / cancelled classes | **Not applied to any schedule** — no engine path modifies `class_sessions`; only day-type status — PROVEN |
| Event precedence | `get_event_priority` table — PROVEN (legacy `docs/05_CALENDAR_ENGINE.md` §Event Priority System) |
| Semester bounding | Engine does **not** bound dates to the semester — a caller can request any date — PROVEN |

---

## 6. Calendar Service / Repository

### Trace: API → service → repository → engine → serialization

1. `GET /api/v1/calendar/{target_date}` → `CalendarService.get_day_schedule(date)` → `CalendarRepository.get_all_events()` → `calendar_engine.get_academic_day(date, events, [5,6])` → `AcademicDayResponse` with `[AcademicEventResponse.model_validate(e) for e in day.events]`. PROVEN (`backend/app/api/v1/endpoints/calendar.py:15-49`).
2. `GET /api/v1/events` → `CalendarRepository.get_all_events()` → all ORM rows serialized. PROVEN.

### Findings

- **Filters applied:** none in the repository; `get_all_events` returns every row ordered by `start_date` (no `active` filter). PROVEN.
- **Inactive events:** ignored by the engine day-resolution but **returned by `GET /api/v1/events`** (and the frontend Events page shows them with an "Inactive" label). PROVEN.
- **Date-bounding:** none server-side — `/events` returns past + future; `/calendar/{date}` accepts any date. PROVEN.
- **Subject relationships:** never loaded (`subject_id` FK not joined; no `subject` relationship on the ORM model). The dashboard resolves subject code/name itself by mapping `subject_id → enrolled subjects` (`dashboard_service.py:_build_upcoming_events`). PROVEN.
- **Authorization:** endpoints require any authenticated user (`get_current_user`); **no role check, no admin concept** — events are visible to all authenticated students. PROVEN.
- **Engine input:** ORM objects (see §5 protocol note). PROVEN.
- **Latent bugs:**
  - Weekend mapping (PROVEN, §5).
  - `get_all_events` ordering by `start_date` only — multi-event same-day ordering is stable but arbitrary (INFERRED).
  - `EligibilityService` counts attendance over the **raw** `[window_start, window_end]` range (`get_subject_counts_between`), not over teaching days — so events (holidays/extra/cancelled) currently have **zero effect on quiz eligibility counts**, and the engine's `teaching_days` number is computed but unused by the eligibility math. PROVEN.

---

## 7. Existing API Contracts

All endpoints are JWT-authenticated (`get_current_user`, `HTTPBearer`). No role scoping anywhere. Registered in `backend/app/api/api.py`.

### Calendar & events (Phase 6 surface)

| Method | Path | Auth | Params | Response | Behavior / Limitations |
|---|---|---|---|---|---|
| GET | `/api/v1/calendar/today` | JWT | — | `AcademicDayResponse` | Resolved academic day for server-local today. PROVEN |
| GET | `/api/v1/calendar/{target_date}` | JWT | date path | `AcademicDayResponse` | Same for any date; no bounds. PROVEN |
| GET | `/api/v1/events` | JWT | — | `List[AcademicEventResponse]` | All events, **including inactive and past**; no filters, no pagination. Mutation explicitly out of scope (docstring). PROVEN |

`AcademicEventResponse` = `{id, event_type, start_date, end_date, subject_id, class_type, is_working_day, substitution_schedule_override, active}` (`backend/app/schemas/calendar.py:6-17`).
`AcademicDayResponse` = `{date, is_working_day, day_type, is_teaching_day, original_day_of_week, substitution_schedule_override, events[]}` (`backend/app/schemas/calendar.py:20-28`).

### Consumers (existing)

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/api/v1/dashboard/summary` | Home read model | `today.*` derived from `CalendarService` + `AttendanceRepository.get_sessions_with_status`; `upcoming_events` from `CalendarRepository` (active, `end_date >= today`, subject-scoped to enrollments, sorted, max 4) — PROVEN (`dashboard_service.py:227-249`) |
| GET | `/api/v1/quiz-eligibility/{subject_code}/{quiz_cycle}` | Eligibility | Window bounds via `get_attendance_window` — PROVEN |
| GET | `/api/v1/attendance/daily/{date}` · `/api/v1/attendance/history` | Track / History | Session-based canonical pipeline; **no calendar/event inputs** — PROVEN |
| GET | `/api/v1/timetable` | Weekly schedule | `get_weekly_entries_for_section(section_id)` **ignores `section_id`** (`timetable_repo.py:15-19`); `timetable_entries` has no section column — PROVEN latent defect |

---

## 8. Existing Frontend

Routes (`frontend/src/app/(authenticated)/`): `dashboard/`, `history/`, `profile/`, `subjects/`, `tools/events/`, `tools/laboratory/` (Track), `tools/quiz-schedule/`. **There is no calendar route/UI.**

- **TopNav** (`components/layout/TopNav.tsx`): Events → `/tools/events` (CalendarDays icon). Quiz Eligibility → `/tools/quiz-schedule`. PROVEN.
- **Hooks** (`hooks/useApi.ts`): `useCalendarDay(date)` → `/api/v1/calendar/{date}` (used **only** by the dead `TodayClassesCard`); `useEvents()` → `/api/v1/events` (used by the Events page); `useDashboardSummary()`. PROVEN.
- **Types** (`types/api.ts`): `EventType` enum (14 values), `AcademicEventResponse`, `AcademicDayResponse`, `UpcomingEventItem`, `TodaySection` (with `is_working_day`, `is_teaching_day`, `day_note`) — all match the live backend contract. PROVEN.
- **Dashboard Today** (`components/dashboard/home/TodayAttendanceCard.tsx`): renders LIVE / TEACHING DAY badge from `today.is_teaching_day`/`is_working_day`; non-working-day empty-state copy. PROVEN.
- **Upcoming Events** (`components/dashboard/home/UpcomingEventsCard.tsx`): date chip, subject/type badge, `View All Events` → `/tools/events`; truthful empty state. PROVEN.
- **`TodayClassesCard`** (`components/dashboard/TodayClassesCard.tsx`): consumes `useCalendarDay` + `useTimetable`, substitution-aware; **defined but never imported anywhere** (dead code — code search found only its own definition). Uses `today.toISOString().split("T")[0]` (UTC date; can be off-by-one vs IST) — PROVEN latent issue.
- Track (`tools/laboratory/page.tsx`), History, Quiz Eligibility, Subjects pages consume attendance/history/quiz APIs only — **no calendar/event inputs**. PROVEN.
- `lib/date.ts` provides local-date helpers (`getLocalDateString`, `formatDayHeader`, `formatLongDate`, `addDays`) ready for calendar UI — PROVEN.

---

## 9. Events Page

File: `frontend/src/app/(authenticated)/tools/events/page.tsx` (client component).

- **Data:** real API via `useEvents()` → `GET /api/v1/events` (STANDARD_CACHE, 1-min revalidate). PROVEN.
- **UI:** PageHeader "Academic Events" + amber admin-restriction notice ("Event creation is currently restricted to administrators. This is a read-only view.") + list of event cards. PROVEN.
- **Per event:** humanized type (`EXTRA_LECTURE` → "Extra Lecture"), holiday Badge when type ends with `HOLIDAY`, "Follows X schedule" Badge when `substitution_schedule_override` set, date range (`start_date` … `end_date`), class-type Badge, or "Active/Inactive" text. PROVEN.
- **States:** loading skeletons (3 cards), full error state, empty state ("No events scheduled"). PROVEN.
- **Read/write behavior:** read-only. No filters, **no Upcoming/Today/Past grouping**, no date navigation, no add/edit/delete affordances. PROVEN.
- **Field expectations vs contract:** matches the live `AcademicEventResponse` exactly; nothing expected that doesn't exist. PROVEN.
- **Fake/static data:** none — fully backed by the real API. PROVEN.

---

## 10. Dashboard Integration

- **Upcoming Events card:** server-side in `dashboard_service._build_upcoming_events` (`dashboard_service.py:227-249`): fetches all events, filters `active and end_date >= today`, **excludes events whose `subject_id` is not in the student's enrollments** (subject-scoped; global events with `subject_id IS NULL` are shown to everyone), maps subject code/name from enrolled subjects, sorts by `(start_date, event_type)`, caps at 4. PROVEN.
  - Date range: end_date ≥ today (no upper bound). Ordering correct. Inactive excluded. Empty state when none. PROVEN.
  - Note: an event starting yesterday and ending tomorrow appears (correct for multi-day events); an event fully in the past is excluded. PROVEN.
- **Today section:** `_build_today` (`dashboard_service.py:132-157`) calls `CalendarService.get_day_schedule(today)` for `is_working_day`/`is_teaching_day`/`day_note` (day_note = dominant event type title-cased), and separately lists today's `class_sessions` with per-session status. PROVEN.
  - **Defect exposure:** because of the weekend bug (§5), on **Fridays** the card reports a non-working day (no LIVE badge) and on **Sundays** a working day — PROVEN by engine execution + code path.
- **Events ↔ calendar-day status:** an event changes `is_working_day`/`day_note` **only**. It does not add/remove `class_sessions`, so Track, History, and attendance percentages are unaffected by events today. PROVEN (§6).
- **`get_sessions_with_status` scope:** no `StudentEnrollment` join (`attendance_repo.py:120-143`) — the dashboard aggregates **all** class sessions in range for the user, not just enrolled subjects (unlike `get_daily_sessions`/`get_history`). Benign while all users are enrolled in all 9 subjects; a latent authorization gap. PROVEN by code inspection.

---

## 11. Legacy / Reference Behavior

**PROVEN LEGACY BEHAVIOR** (from `js/calendar-engine.js`, `js/events-controller.js`, `js/test-*.js`, `docs/05`, `docs/09`, `docs/S4.3`, ADR 001/003/004/010/011):

- **Event = exact-date schedule mutation** (S4.3 invariant): `EVENT → CALENDAR/SCHEDULE → CLASS OCCURRENCE → ATTENDANCE ENGINE → CURRENT/OVERALL/FORECAST`. Events never create attendance records; they change the schedule, and the attendance engine counts the resulting occurrences. (`docs/S4.3_ACADEMIC_EVENTS_ENGINE.md`)
- **`getEffectiveDaySchedule`** applies events natively: `CLASS_CANCELLED` removes one matching occurrence; `EXTRA_LECTURE/TUTORIAL/PRACTICAL`, `SURPRISE_QUIZ` inject an occurrence with a unique id (`L_extra_<eventId>`) so state doesn't collide; closures empty the day. Tested: `js/test-events-controller.js` (assertions 1,2,3,4,8,11,12,13,14,16,19,20).
- **Deltas** (`getSubjectEventDeltas`): +1 extra, −1 cancelled, 0 for closures/wrong subject/type. Tested: `js/test-calendar-engine.js` (lines 188-226).
- **Priority table** identical to Python (EMERGENCY_CLOSURE 100 → default 10). Tested in `js/test-calendar-engine.js`.
- **Working Saturday substitution:** `WORKING_SATURDAY` with `substitutionScheduleOverride: 'MONDAY'` makes the day working and swaps the schedule to Monday's. Tested: `js/test-calendar-engine.js` (lines 124-128).
- **Attendance windows** (ADR 010): Q1 from subject commencement; Q2/Q3 from the previous quiz milestone; window ends the day before the quiz; `holidayCount`/`weekendCount`/`workingDays`/`effectiveTeachingDates` computed. Tested: `js/test-calendar-window.js` (assertions 1-13 incl. working-Saturday inside window, emergency closure excluded).
- **Soft-delete lifecycle** (ADR 004): Active → Disabled (`active=false`) → Archived (`archived=true`); permanent deletion does not exist in normal flows.
- **Single persistent authority** (ADR 011): `AppState.academicEvents` is the sole store; the engine derives runtime state via `syncRuntimeEvents`; all mutations through `events-controller.js` with rollback snapshots.
- **Registry-driven validation** (ADR 001 / docs 05, 09): `AcademicEventRegistry` (10 types) drives form generation, rendering, and `validateAcademicEvent` (requiresSubject / requiresClassType / allowedClassTypes).
- **Known legacy limitations** (`docs/09`): Firestore rules blocked `academicEvents` field writes (critical sync bug); dual-state drift risk; event-form UI not fully browser-validated.

**Distinction:** the legacy system was **user-owned, per-student, client-side** events. The roadmap and migration audit replace that with **globally-defined events** (`backend/MIGRATION_AUDIT.md` §4: "Baseline replaces legacy student-created events, which are now globally defined"). The current Python architecture is the **global, admin-owned** model — but the persistence/authorization/admin layer does not exist yet. PROVEN (MIGRATION_AUDIT + empty events table + no mutation endpoints).

---

## 12. Event Types

Defined in `backend/app/models/enums.py` (EventType, 14 values) and mirrored in `frontend/src/types/api.ts`.

| Event type | Makes day non-working? | Changes scheduled classes? | Affects attendance/quiz? | Priority | Notes |
|---|---|---|---|---|---|
| `PUBLIC_HOLIDAY` | Yes (closure) | Yes (day empties) | Via schedule (legacy) — none today | 70 | Global |
| `INSTITUTE_HOLIDAY` | Yes (closure) | Yes | Same | 50 | Global |
| `FESTIVAL_HOLIDAY` | Yes (closure) | Yes | Same | 40 | Global |
| `EMERGENCY_CLOSURE` | Yes (closure) | Yes | Same | 100 | Global |
| `SEMESTER_BREAK` | Yes (closure) | Yes | Same | 60 | Global, multi-day typical |
| `MID_SEMESTER_BREAK` | **No** (missing from closure list) | No | No | 60 | **PROVEN gap** — priority 60 but not treated as closure; needs `is_working_day=false` manually |
| `WORKING_DAY_OVERRIDE` | Only via `is_working_day` | No | No | 90 | Requires creator-set `is_working_day` |
| `WORKING_SATURDAY` | Only via `is_working_day` (typically true) | Substitution | No | 80 | `substitution_schedule_override` pairs with this |
| `CLASS_CANCELLED` | No | Removes one occurrence (legacy) | Via schedule — none today | 30 | Requires subject + class type |
| `EXTRA_LECTURE` / `EXTRA_TUTORIAL` / `EXTRA_PRACTICAL` | No | Injects one occurrence (legacy) | Via schedule — none today | 30 | Requires subject + class type |
| `SURPRISE_QUIZ` | No | Injects occurrence (legacy) | Via schedule — none today | 30 | Requires subject + class type |
| `QUIZ_DAY` | No | No | Informational | 30 | Requires subject; no class type |

**Assessment:**
- Every type can span multiple days (`start_date`/`end_date`). PROVEN.
- Whether a type makes a day working/non-working depends on the closure list (§5) or a manually-set `is_working_day` — there is **no validation layer** forcing `is_working_day` for override types or subject/class-type requirements for extra/cancelled types. PROVEN (no registry in the Python codebase; `backend/MIGRATION_NOTES.md` maps legacy registry to enums only).
- Legacy registry covered only 10 of the 14 types; `WORKING_SATURDAY`, `FESTIVAL_HOLIDAY`, `SEMESTER_BREAK`, `MID_SEMESTER_BREAK` have **no UI/validation metadata anywhere**. PROVEN.
- **Gap report:** the enum is sufficient for the roadmap's listed features; the missing piece is the per-type *behavior registry* (requiresSubject / requiresClassType / allowedClassTypes / day-affecting / class-affecting), which must be rebuilt as the Python equivalent of `AcademicEventRegistry` when mutation lands. No new enum values are needed for Phase 6 as specified.

---

## 13. Authorization

**Current state (PROVEN):**
- `User` model (`backend/app/models/user.py`) has `firebase_uid`, `roll_number`, `name`, `hashed_password`, `section_id` — **no role/is_staff/is_admin column**.
- `get_current_user` (`backend/app/api/dependencies/deps.py`) returns any authenticated user; there is **no role check anywhere** in the backend.
- Events: `GET /events` open to any authenticated user. No create/update/delete endpoints exist at all. The endpoint docstring and the Events page notice both state mutation is "restricted to administrators" — **but no administrative mechanism exists** (no admin users, no admin endpoints, no seed admin).
- Legacy: events were per-student (`source: 'USER'`); the roadmap replaces this with **admin → create event → academic events** (global, admin-owned).

**Reported product/architecture gap (explicit, not solved here):** Phase 6 requires a minimal authorization model for event mutation — e.g. an `is_admin`/`role` column on `users` (or a dedicated admin credential), a dependency like `require_admin`, and admin-only create/update/delete endpoints. Reads can remain student-visible. This is a **product decision + small schema change** that must precede 6.5.

---

## 14. Confirmed Bugs

| # | Bug | Evidence | Severity |
|---|---|---|---|
| 1 | **Weekend mapping inverted:** services pass Python `[5,6]`; engine checks JS indices → Friday non-working, Sunday working | `calendar_service.py:15`, `eligibility_service.py:74`, `calendar_engine.py:59-60`; **executed** | HIGH — corrupts every calendar-day response + dashboard Today day-type |
| 2 | `GET /api/v1/events` returns inactive + past events | `calendar_repo.py:9-12` (no filter), `events.py:15-22` | MEDIUM — Events page shows stale/inactive rows |
| 3 | `MID_SEMESTER_BREAK` not in closure list despite priority 60 | `calendar_engine.py:72-74` | MEDIUM — surprise non-working behavior once events exist |
| 4 | Dashboard `get_sessions_with_status` not enrollment-scoped | `attendance_repo.py:120-143` (no `StudentEnrollment` join; contrast `get_daily_sessions`/`get_history`) | LOW today / MEDIUM later — latent cross-enrollment exposure |
| 5 | `TimetableRepository.get_weekly_entries_for_section` ignores `section_id`; no section column on `timetable_entries` | `timetable_repo.py:15-19`, migration `7117a007a0da` | MEDIUM — section-scoped schedules impossible; `/timetable` returns the same 28 entries to everyone |
| 6 | Engine annotations claim Pydantic schema objects; runtime objects are ORM (`subject_code` vs `subject_id` split) | `calendar_engine.py:3-8` imports `app.schemas.academic`; callers pass ORM | LOW — works by field overlap; fragile for future fields |
| 7 | Python `get_attendance_window` dropped legacy fields (`holidayCount`, `weekendCount`, `workingDays`, `activeMilestones`) | compare `calendar_engine.py:111-137` vs `js/calendar-engine.js` `getAttendanceWindow` | LOW — blocks future calendar/window UX |
| 8 | `TodayClassesCard` is dead code and uses UTC `toISOString()` for "today" | `frontend/src/components/dashboard/TodayClassesCard.tsx:10`; only match is its own definition | LOW |
| 9 | `active` has no DB default (ORM-only default `True`) | migration `7117a007a0da` (`nullable=False`, no `server_default`); `event.py:20` | LOW — raw-SQL inserts fail without `active` |
| 10 | No unique constraint on `(event_type, start_date, subject_id, class_type)` | migration `7117a007a0da`; no index besides PK | LOW — duplicate events possible once mutation exists |

---

## 15. Missing Functionality

- **Calendar UI:** no month/day view, no navigation (prev/next/today), no selected-date state, no date picker, no calendar route.
- **Events UX:** no Upcoming / Today / Past grouping, no filters, no event-detail view, no Add Event modal, no edit/delete/toggle, no holiday indicators beyond the current list badges.
- **Event persistence:** no POST/PUT/DELETE endpoints; no admin authorization (`require_admin`), no admin seed; no validation layer (Python `AcademicEventRegistry` equivalent with requiresSubject/requiresClassType/allowedClassTypes).
- **Event → engine integration (roadmap core):** events do **not** create/cancel `class_sessions`; no `is_extra`/`is_cancelled` generation from events; no `getEffectiveDaySchedule`/`getSubjectEventDeltas` Python equivalents; quiz eligibility ignores events entirely (counts over raw date range). The roadmap's `Admin → Event → Calendar Engine → Track/Dashboard/Quiz Eligibility` pipeline does not exist beyond day-status.
- **Event scoping:** no session/semester/section scoping (schema + queries); multi-semester rollover would mix calendars.
- **Seeding:** no institutional holidays/working-Saturday events (table empty).
- **Business-rule engine:** no decision logic for overlapping events beyond priority, none for multi-day vs quiz windows, none for event→quiz interplay.
- **Indexes:** none on `(start_date, end_date)`/`event_type` — fine now, add with calendar queries if needed.

---

## 16. Business-Rule Decisions Required

Only questions the current code/docs cannot answer (UNKNOWN / open):

1. **Who creates academic events?** (Admin role mechanism: new `role` column + seed admin, or dedicated admin auth?) — required before 6.5.
2. **Are events global or scoped?** (Global today. Per-section, per-semester, or per-session scope requires a schema change. The single-section reality (CSE-51) makes global acceptable short-term.)
3. **Can students create personal events?** (Legacy allowed per-student events; roadmap says admin. Decision: student events out of scope → keep global admin-only, or reintroduce user-owned events?)
4. **Does `PUBLIC_HOLIDAY`/`EMERGENCY_CLOSURE` override `WORKING_SATURDAY`?** (Priority says yes — EMERGENCY_CLOSURE 100 > WORKING_SATURDAY 80 — but is that the desired product outcome? Legacy tests imply yes; needs confirmation only if behavior feels wrong.)
5. **Overlapping events:** dominant-priority wins (PROVEN engine). Is that acceptable product behavior, or should overlapping same-priority events be rejected at creation?
6. **Event vs class session:** should creating `EXTRA_LECTURE`/`CLASS_CANCELLED` **generate/modify `class_sessions` rows** (so Track/History/analytics see them), or should events only annotate calendar days? This is the central Phase 6 design decision — the legacy behavior (schedule mutation) vs current (annotation only).
7. **`substitution_schedule_override` representation:** day-name string today (`'MONDAY'`); used by `TodayClassesCard` + `expand_baseline.py`. Confirmed representation; only needs a UI + engine path to render a substituted day's schedule.
8. **Should an event automatically alter attendance sessions?** (i.e., does a `PUBLIC_HOLIDAY` retroactively affect already-generated `class_sessions` on that date — cancel them — or only future reads?)
9. **Extra lectures:** auto-generate sessions, or require admin to also create a session?
10. **Multi-day events vs quiz windows:** `get_attendance_window` counts teaching days only (legacy); with events, should quiz-window teaching-day counts exclude holiday days (legacy behavior) — and should that number be surfaced in UI?
11. **Event lifecycle:** soft-delete (`active` flag) vs hard delete? (Legacy ADR 004: soft-delete + archive. Current table has only `active` — no `archived` column. Decision: keep `active`-only or add `archived`.)
12. **History preservation:** if events are allowed to cancel classes retroactively, how do already-recorded attendance records behave? (Recommend: never delete records; cancelled flag on sessions only.)

---

## 17. Frozen Areas (Phase 6 MUST NOT break)

Per `MASTER_ROADMAP.md` freeze rules and the Phase 2–5 walkthroughs:

- **Track attendance** — daily view, date navigation bounds, marking, Mark All Present, cancelled-session rejection (409), unique-constraint-preserving mutation (`POST /api/v1/attendance`).
- **Attendance History** — `GET /api/v1/attendance/history` contract, filters, pagination, summary semantics.
- **Dashboard attendance** — Today/Overall/Weekly aggregation, status banding (SAFE ≥ 80 / WATCH ≥ 60 / CRITICAL < 60), `GET /api/v1/dashboard/summary`.
- **Quiz eligibility** — `eligibility_engine.py`/`eligibility_service.py`, thresholds from `eligibility_policies`, BCS-054 Q3 UNRESOLVED invariant, window-bounded counts.
- **Historical attendance windows** — ADR 010 semantics (Q1 from commencement, Q2/Q3 from previous quiz).
- **Signup/login, JWT auth** — `POST /auth/register`, `POST /auth/login`, `get_current_user`, `firebase_uid` nullable, no Firebase dependency for identity.
- **Attendance/eligibility engines** — do not re-implement their math; events must feed them, not fork them.
- **Schema invariants:** `uq_user_class_session`, `uq_user_experiment`, `ix_users_roll_number`, BCS-054 `UNRESOLVED` row, `firebase_uid` unique index.
- Phase 6 work is additive: read-model endpoints, calendar UI, event endpoints (admin), event→session integration — all behind the same canonical data path. **Do not create parallel calculations.**

---

## 18. Proposed Phase 6 Sub-Phases

Derived from the actual findings (not a blind template):

- **6.0 Audit** — this report. ✅ DONE.
- **6.1 Foundational corrections (prerequisite, do first):**
  - Fix the weekend-mapping defect (align `default_weekends` convention between services and engine — single source of truth, e.g. engine-owned constant or JS-index convention used by both `CalendarService` and `EligibilityService`).
  - Define the event-read contract: `GET /api/v1/events` gains `active`, `date_from`/`date_to`, `upcoming`/`past` semantics (or a dedicated read endpoint with proper filtering, enrollment-scoped subject codes, date-bounded).
  - Add `MID_SEMESTER_BREAK` to the closure list (or document intentional deviation).
  - Optionally: enrollment-scope `get_sessions_with_status`; fix `/timetable` section scoping decision (schema question — decide whether `timetable_entries` needs a section column; single-section reality may defer).
- **6.2 Calendar read model & API:** month-bounded read endpoint (events + working-day resolution + per-day class-session counts) bounded to the real semester; validate with the fixed engine; server-side month view model so the client renders, not computes.
- **6.3 Calendar UI:** `/calendar` route — month/day navigation, Today shortcut, selected date, working/non-working indicators, event indicators/cards, substitution notice, class-schedule strip per day, loading/error/empty states; consume the 6.2 read model.
- **6.4 Events page upgrade:** Upcoming / Today / Past grouping, filters (type, subject, date), event details (subject, class type, range, substitution, active state); keep read-only.
- **6.5 Event persistence + authorization (product decision gate §16):** admin/role mechanism (e.g. `is_admin` on users + `require_admin` dependency + admin seed), Python event validation registry (port `AcademicEventRegistry` + `validateAcademicEvent`), `POST/PUT/DELETE /api/v1/events` (soft-delete via `active`; decide `archived`), uniqueness guard, event seeding (institutional holidays, working Saturdays for the semester).
- **6.6 Event → engine integration (roadmap core):** decide event↔session semantics (§16 Q6/Q8) — likely: closures cancel/flag matching `class_sessions` (`is_cancelled`), extras create `is_extra` sessions through the canonical pipeline, so Track/History/Dashboard/Quiz all reflect events automatically; wire substitution into daily-session resolution; verify quiz windows respect events (window bounds + teaching-day counts, ADR 010 semantics preserved).
- **6.7 Verification/freeze:** end-to-end consistency checks (calendar ↔ Track ↔ History ↔ dashboard ↔ quiz), read-only SQL audits, regression of all frozen areas (§17), update `MASTER_ROADMAP.md`/`implementation_plan.md`/`walkthrough.md`.

---

## 19. Verification Strategy

For each sub-phase, before freeze:

- **Static:** `python -m compileall backend/app`; `npx tsc --noEmit`; no engine/quiz/auth/migration changes outside the phase's scope.
- **Engine (unit, read-only execution):** weekend mapping (Fri working / Sat-Sun non-working), event priority/closure precedence, inactive-event exclusion, substitution propagation, multi-day ranges — extend the pattern used in §5 to a real test file.
- **API (live, minted dev JWT):** `/calendar/today`, `/calendar/{date}` (Fri vs Sun vs holiday), `/events` (after 6.1 filtering), `/dashboard/summary` (Today day-type + Upcoming Events populated after seeding), `/quiz-eligibility/{code}/{cycle}` (windows unchanged pre-6.6; event-aware post-6.6).
- **Data (read-only SQL):** `academic_events` counts/active/date ranges/subject refs; `class_sessions` cancelled/extra counts after 6.6; cross-check a seeded holiday date has no (or cancelled) sessions; confirm 0 rows modified in frozen tables.
- **Consistency:** calendar day-type vs class_sessions on the same date; dashboard Today vs `/attendance/daily/{date}`; History summary vs dashboard overall; eligibility vs attendance summary (as done in Phases 4.5/5).
- **Authorization:** second-account test — events visible to all authenticated users (read); mutation endpoints 403 for non-admins after 6.5; cross-user record isolation for any new user-scoped reads.
- **Regression:** Track marking, History filters/pagination, signup/login, BCS-054 UNRESOLVED — verified unchanged after each phase.

---

## 20. Final Recommendation

**Proceed with Phase 6.** The foundation is sound but dormant: a working day-resolution engine, an empty-but-correct `academic_events` table, read-only calendar/event endpoints, and real dashboard consumption already exist. The work is (a) fix the proven weekend defect, (b) complete the event read contract, (c) build the calendar UX, (d) add admin-owned persistence, and (e) — the essential roadmap requirement — make events feed the existing attendance/quiz engines through the canonical `class_sessions` pipeline rather than creating parallel rules.

Two decisions gate the largest chunk of work and should be resolved before 6.5/6.6:
1. The admin authorization mechanism (§16 Q1).
2. Event ↔ class-session semantics (§16 Q6/Q8) — this determines whether Track/History/analytics react to events automatically.

Everything else is additive and low-risk. The current database event state (0 rows) means the entire calendar experience will render empty until seeding (6.5) — per `MASTER_ROADMAP.md` Rule 5, empty states do not prove correctness, so seeding institutional events and verifying them end-to-end is mandatory, not optional.

---

*No project files other than this report were created or modified. No database rows were inserted, updated, or deleted. The `attendancedashpro_db` container was started (no data change) to run read-only SQL. The Python engine was executed in-process only.*
