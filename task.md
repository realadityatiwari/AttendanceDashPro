# AttendanceDash Pro â€” Task Brief

## PHASE 2 â€” DESKTOP SHELL & GLOBAL UX

Status: **COMPLETE** (13 Aug 2026) â€” all BLOCKED markers resolved by **Phase 10** (COMPLETE & FROZEN, see below); remaining non-Phase-2 items are future-phase work.

## Objective

Reproduce the desktop reference interface (compact top navigation, profile dropdown, Profile/Appearance/Feedback/Settings/Install modals) on the Next.js app using real application data â€” without faking functionality.

## Delivered

- [x] Desktop top navigation (TopNav) replacing the legacy sidebar; active route highlighted; route labels mapped to existing routes only
- [x] Authenticated user area (avatar + name) + Profile dropdown with Profile / Appearance / Install App / Send Feedback / Settings / Sign Out
- [x] Shared modal foundation (`ShellDialog`) â€” backdrop, focus, Escape, scroll lock, responsive width, dialog semantics, consistent header/close/spacing
- [x] Profile modal from real `/student/me` data (identity + academic context)
- [x] Appearance modal â€” Dark selected; Light/System explicitly disabled (BLOCKED: Phase 1 tokens are dark-locked)
- [x] Feedback modal â€” validation, loading, success, error, duplicate-submission guard; posts to `POST /api/v1/feedback` â€” **RESOLVED (Phase 10C):** endpoint live, verified 23/23; errors are honest, never fake success
- [x] Settings modal â€” controls disabled + persistence notice â€” **RESOLVED (Phase 10D):** real `GET/PUT /student/preferences`, verified 18/18; storage-only until Phase 11 consumers
- [x] Install App â€” beforeinstallprompt capture + standalone detection; explains missing PWA infra (BLOCKED: no manifest/service worker); no fake installed state
- [x] Sign Out via existing `AuthContext.logout()` (JWT removal + redirect), auth architecture untouched
- [x] Backend: `GET /student/me` extended with read-only academic context (additive contract change; no schema/DB/engine changes)

## Not in this phase

- Home / Track / Quiz Eligibility / Attendance / History / Events page content redesigns (dedicated phases)
- Events functionality (list/calendar, Upcoming/Today/Past, Add Event, persistence) â€” dedicated Events phase
- Mobile navigation â€” **resolved by Phase 12A** (bottom nav below `md` per S4 spec, 2026-08-21); page-level mobile responsiveness is Phase 12B-12F
- Program field, feedback persistence, settings persistence â€” **resolved by Phase 10** (see implementation_plan.md "RESOLVED BY PHASE 10"); Light/System themes, PWA infra, reminders/auto-mark consumption â€” still future-phase work (see implementation_plan.md "BLOCKED / BACKEND REQUIRED")

## Validation

- `npx tsc --noEmit` â€” PASS
- Backend `py_compile` on changed files â€” PASS

## Do Not Touch Again

- Phase 0 audit Â· Phase 1 design tokens Â· Card Â· Badge Â· Progress
- backend architecture Â· database architecture Â· attendance engine Â· quiz engine
- authentication architecture Â· Firebase migration boundary

---

## PHASE 3 â€” HOME DASHBOARD

Status: **COMPLETE** (13 Aug 2026) â€” see BLOCKED markers in `implementation_plan.md`

## Objective

Rebuild the authenticated Home/Dashboard page to match the desktop reference composition (Greeting â†’ Today's Attendance â†’ Overall Attendance â†’ This Week â†’ Quiz Snapshot â†’ Attention Required â†’ Upcoming Events), driven by real authenticated data, with loading/error/empty states and no duplication of business logic.

## Delivered

- [x] Backend: single additive read-only endpoint `GET /api/v1/dashboard/summary` (dashboard.py endpoint + schema + service) reusing `AttendanceService`, `EligibilityService`, `CalendarService`, `QuizRepository`; engines untouched
- [x] Backend: additive `AttendanceRepository.get_sessions_with_status()` only new repo method
- [x] Status classification reconciled: SAFE â‰¥ 80 / WATCH â‰¥ 60 / CRITICAL < 60 on **current** pct (S4.1 + legacy banding)
- [x] Today's Attendance â€” per-session status (Attended/Missed/Pending/Cancelled), attendance/pending footer
- [x] Overall Attendance â€” big pct, status badge, attended/recorded/pending counts, weekly delta, progress bar
- [x] This Week â€” Monâ€“Fri strip with per-day pct bars, week pct + delta vs previous week, best/needs-attention subjects
- [x] Quiz Snapshot â€” next quiz cycle label + date + threshold, eligible/attention/not-eligible counts, link to `/tools/quiz-schedule`; empty state when none scheduled
- [x] Attention Required â€” WATCH/CRITICAL subjects (CRITICAL first, pct ascending) with current + forecast pct; link to `/tools/laboratory`; empty state when on track
- [x] Upcoming Events â€” date chips + type badges, subject-scoped to enrolled subjects; empty state (table currently has 0 rows); link to `/tools/events`
- [x] Greeting header â€” time-of-day greeting + first name (real profile) + `Thursday Â· 13 Aug 2026` local date
- [x] Loading skeletons per section; full-page error state; two-column bento with collapse order Today's â†’ Overall â†’ This Week â†’ Quiz â†’ Attention â†’ Events

## Not in this phase

- Dedicated per-subject strategy view (View Strategy â†’ `/tools/laboratory`; Track-phase work)
- Events seeding â€” `academic_events` is empty, section shows its empty state until real events exist

## Validation

- Backend `py_compile` on changed files â€” PASS
- Live `GET /api/v1/dashboard/summary` (real user `2401220100027`) â€” PASS: 6 today's classes (all PENDING), overall 69.2% WATCH, weekly delta +21.5 pts, Quiz1 (cycle 1, â‰¥70%) 6/6 eligible, 4 attention items (BNC-501/BCS-058/BCS-054 CRITICAL, BCS-502 WATCH), 0 events
- `npx tsc --noEmit` â€” PASS (0 errors)

## Do Not Touch Again

- All Phase 2 items above, plus: `backend/app/engines/*` Â· `backend/app/models/*` Â· migrations
- `frontend/src/components/ui/*` primitives Â· `TopNav` Â· `UserMenu` Â· `AppShell` Â· `TodayClassesCard` Â· `FormulaCard` Â· `SubjectAttendanceGrid` (other pages use them)
## PHASE 4.5.2 - HISTORICAL TRACK COMPLETION

## Objective

Finish the Track Attendance experience so the student can navigate the entire semester attendance history from 2026-07-15 (semester start) through the current date, with every scheduled class session visible - lecture, tutorial, practical/lab, pending, attended, missed, cancelled - and markable through the existing canonical attendance mutation endpoint.

## Delivered

- [x] Frontend enum contract fix: `AttendanceStatus` = `Attended`/`Missed`/`Pending` and `ClassType.PRACTICAL = "P"` now match the live backend serialization (previously the Track UI compared against `ATTENDED`/`P1` - every session rendered as PENDING and every mutation was rejected with 422)
- [x] Backend: `StudentProfile` + `get_academic_context` now expose `semester_end` (alongside existing `semester_start`) so the UI can bound navigation without hardcoding dates
- [x] Backend: `record_attendance` rejects mutations on cancelled class sessions (409)
- [x] Backend: `get_daily_sessions` read scoped to the authenticated student's enrolled subjects
- [x] Track page: previous/next navigation clamped to `[semester_start, semester_end]`; native date picker (dark-styled) for direct date jumps; Today button preserved; semester-start indicator
- [x] Track page: mutation errors surfaced inline (previously only console.error - failures were silent)
- [x] Practical/lab sessions (BCS-551/552/553, class_type P) verified present in Track and counted as PENDING by analytics (no quiz-window dependency - the legacy bug is not repeated)
- [x] PENDING requires no attendance_records row (sessions LEFT JOIN records, None = Pending); cancelled sessions protected client-side and server-side; unique (user, session) constraint preserved via get-then-update mutation

## Not in this phase

- Real Sign Up (Phase 4.5.3)
- Lab experiment management (Phase 9) - no laboratory_experiments/laboratory_records rows created
- History redesign (Phase 5)
- Visual polish beyond Track usability requirements

## Validation

- Backend `python -m compileall backend/app` - PASS
- Frontend `npx tsc --noEmit` - PASS (0 errors)
- Live `GET /api/v1/student/me` - PASS: `semester_start 2026-07-15` / `semester_end 2026-12-31`
- Live `GET /api/v1/attendance/daily` - PASS: 07-15 (6 sessions, Attended/Missed), 07-16 (BCS-552 P x2 Pending), 07-17 (BCS-553 P x2 Pending), 07-14/07-19 (empty)
- Live mutation contract - PASS: POST status=`Attended` + bogus session -> 404 (validation OK, no data touched); POST status=`ATTENDED` -> 422 (old broken contract proven)
- Live `GET /api/v1/attendance/summary/BCS-551` - PASS: practical total=8, pending=8 (labs flow through canonical analytics)
- No database rows created, modified, or deleted during implementation

## Do Not Touch Again

- Track navigation, date bounds, and marking behavior from this phase (reopen only for a genuine defect)
- The attendance engines remain frozen - analytics integrity verified, not modified

## PHASE 4.5.3 - REAL SIGN UP + ACCOUNT CREATION

## Objective

Implement a legitimate student registration flow: frontend `/signup` + backend `POST /api/v1/auth/register` creating a PostgreSQL-backed user who immediately authenticates through the existing JWT system.

## Delivered

- [x] `POST /api/v1/auth/register` - validates name, 13-digit numeric roll number, password (min 8); hashes with the same `pbkdf2_sha256` verifier login uses; creates User + enrollments in ONE transaction; duplicate roll -> 409 (IntegrityError race guard); ambiguous academic config -> explicit 409/503; any failure -> full rollback (no partial user, no orphan enrollment)
- [x] Academic context resolved from authoritative configuration only: active `AcademicSession` -> its `Semester` -> its `Section` -> semester `Subject` rows. Client never submits section/semester/session/subject IDs
- [x] `firebase_uid` made NULLABLE (migration `c3d4e5f6a7b8`) for PostgreSQL-native identity; all 29 legacy UIDs preserved; column kept (removal belongs to Phase 14)
- [x] JWT issued immediately after registration via the exact `create_access_token` used by login (no second auth flow)
- [x] `/signup` page matching the visual system: Full Name, Roll Number, Password + Confirm (show/hide), Create Account, link to Login; idle/submitting/validation/server-error/success states; friendly messages ("An account with this roll number already exists.", "Roll number must be 13 digits.", "Passwords do not match.", "Unable to create account. Please try again.")
- [x] Auth routing: `/login` and `/signup` public; authenticated users redirected from both into the app shell
- [x] Login page now links to `/signup`
- [x] `firebase_uid` surfaced as nullable in `StudentProfile` schema + frontend types; profile page already falls back to the user id

## Not in this phase

- Section selection UI (single-section semesters auto-assign; multi-section semesters are rejected explicitly until a product decision exists)
- Firebase retirement (Phase 14) - column intentionally retained
- Password reset / email identity (no email storage exists in the schema)

## Validation

- Backend `python -m compileall backend/app` - PASS
- Frontend `npx tsc --noEmit` - PASS (0 errors)
- Alembic upgrade to `c3d4e5f6a7b8` - PASS; `firebase_uid` now nullable; 29/29 legacy UIDs intact (Aditya's preserved)
- Live API - PASS: invalid roll -> 422; short password -> 422; duplicate roll -> 409 (full pipeline exercised, rolled back, no data created)
- Live registration of ONE disposable verification account (roll 9999999999999, reported explicitly, consistent with existing test-user convention): 201 + JWT; /student/me returns section CSE-51, firebase_uid null; dashboard works with the new token; 9 enrollments created in the DB
- Aditya's account, attendance, enrollments, and password untouched (verified by query)

## Do Not Touch Again

- Registration flow and provisioning rule from this phase (reopen only for a genuine defect or a section-selection product decision)
- The enrollment auto-provisioning rule is documented; multi-section handling requires a roadmap decision before implementation

## PHASE 5 - ATTENDANCE HISTORY

## Objective

Turn the existing /history page into a production-quality Attendance History experience: the student's real attendance history from semester start through the current date, consuming the SAME canonical attendance data as Track - no second attendance source, no React-side calculations.

## Delivered

- [x] Single endpoint `GET /api/v1/attendance/history` extended in place (no second data system): session-based items (date, times, subject code+name, class type, status, cancelled/extra flags, marked_at), effective semester range, and a server-side summary over the full filtered set
- [x] Semester bounds from the authenticated student's real academic context (semester_start -> min(date_to, semester_end, today)); no hardcoded dates; date inputs bounded by the same contract
- [x] Pending = no attendance row (same semantics as Track); Cancelled is a session state, never counted absent; summary matches Track's daily counting convention
- [x] Server-side filters: enrolled-subject select, state select (Present/Absent/Pending/Cancelled), date-from/to, debounced search across code/name/class type/date - all validated and enrollment-scoped
- [x] Pagination: existing limit/offset/total_count contract; "Load more" with id-deduplicated append; filters reset offset and never mix result sets; list stays visible while the next page loads
- [x] Summary strip: Total/Present/Absent/Pending/Cancelled + overall % (aggregate query, truthful when filters are active)
- [x] Semantic Badge mapping: Present -> success, Absent -> danger, Pending -> warning, Cancelled -> neutral (existing system, no new visual language)
- [x] Distinct states: loading skeletons, API error, "no classes in semester" vs "no sessions match your filters"
- [x] Authorization: reads scoped to the authenticated user + enrollments (repository join + user_id filter); unenrolled subject codes return 0; cross-user records isolated (verified with a second account)
- [x] SQL: single query + aggregate FILTER summary, no N+1; no new indexes needed at current scale
- [x] No attendance rows created/modified/deleted; no engines/track/auth/signup/migrations touched

## Validation

- Backend `python -m compileall backend/app` - PASS
- Frontend `npx tsc --noEmit` - PASS (0 errors)
- Live (real user 2401220100027, minted dev JWT): default query -> 129 sessions (55 Attended / 24 Missed / 50 Pending, pct 69.6% = 55/79 recorded, consistent with the dashboard); range clamped 2026-07-15 -> 2026-08-14
- Track cross-check 2026-07-15 -> exactly 6 sessions, 3 Present / 3 Absent, identical to the Track daily view; Aditya's manual BCS-553 2026-07-17 practical mark shows Attended in both
- Filters: Pending=50, Missed=24, Attended=55 (pct 100 of filtered set), Cancelled=0 (none exist), invalid status -> 422; search BCS-55=28, practical=28, lecture=79, 2026-07-15=6
- Pagination: limit=10&offset=0 and offset=10 -> 10+10, zero id overlap
- Clamps: date_from=2026-01-01 -> range_start 2026-07-15; date_to=2026-12-31 -> range_end 2026-08-14; date_from=2026-09-01 -> 0 results
- Authorization: second account (9999999999999) sees 0 attended/0 missed/129 pending (record isolation); bogus subject -> 0

## Do Not Touch Again

- The history endpoint contract, filtering/pagination behavior, and summary semantics from this phase (reopen only for a genuine defect)
- The canonical attendance pipeline remains frozen; History is a presentation/query feature, not an analytics engine

---

## PHASE 6.1 - FOUNDATIONAL CALENDAR CORRECTIONS

Status: **COMPLETE** (2026-08-14)

## Objective

Correct the calendar/event defects PROVEN in the Phase 6.0 audit (`docs/phase_6_0_calendar_events_audit.md`) so later Calendar/Event work is built on correct temporal semantics. No calendar UI, no event CRUD, no admin system, no seeding, no eventâ†’session integration in this phase.

## Root causes

1. **Weekend mapping**: `CalendarService` and `EligibilityService` passed `default_weekends=[5, 6]` (Python weekday indices) but `calendar_engine.get_academic_day` converts dates to JS `getDay()` indices before testing membership â€” Friday resolved non-working, Sunday working.
2. **MID_SEMESTER_BREAK**: absent from the engine's closure list despite priority 60 (same tier as SEMESTER_BREAK) â€” it did not flip days non-working.
3. **/events read contract**: `GET /api/v1/events` â†’ `CalendarRepository.get_all_events()` returned every row (inactive + fully past included) with no filtering.
4. **Dashboard aggregation scope**: `AttendanceRepository.get_sessions_with_status` had no `StudentEnrollment` join â€” Dashboard Today/Overall/Weekly aggregated all class sessions, not just the student's enrolled subjects.

## Exact fixes

- `backend/app/engines/calendar_engine.py` â€” new canonical constant `DEFAULT_WEEKENDS = [0, 6]` (JS `getDay()`: Sunday=0, Saturday=6; matches legacy `js/calendar-engine.js` and the engine's own conversion), used as the parameter default of `get_academic_day`; `MID_SEMESTER_BREAK` added to the closure-event list.
- `backend/app/services/calendar_service.py` â€” `get_day_schedule` now passes the shared `DEFAULT_WEEKENDS` (removed the local `[5, 6]`).
- `backend/app/services/eligibility_service.py` â€” same shared constant for `get_attendance_window` / `evaluate_quiz_eligibility` (window bounds math unchanged; teaching-day counts now use the corrected convention).
- `backend/app/repositories/calendar_repo.py` â€” `get_all_events(active=None, date_from=None, date_to=None, upcoming=False)` optional server-side filters (repo default remains no-filter for internal dashboard/eligibility callers).
- `backend/app/api/v1/endpoints/events.py` â€” `GET /api/v1/events` query params: `active` (default `true`), `date_from`, `date_to` (inclusive range-overlap), `upcoming` (default `false`, `end_date >= today`); 422 when `date_from > date_to`.
- `backend/app/repositories/attendance_repo.py` â€” `get_sessions_with_status` now joins `StudentEnrollment` (mirrors `get_daily_sessions` / `get_history`).
- `backend/scripts/expand_baseline.py` â€” uses the shared `DEFAULT_WEEKENDS` constant (was an inline `[0, 6]`).

## Final GET /api/v1/events contract

- Default: **active events only** (`active=true`); pass `active=false` for inactive events only.
- `date_from` / `date_to` (YYYY-MM-DD): inclusive range-overlap on the event's `[start_date, end_date]` (`event.start_date <= date_to AND event.end_date >= date_from`).
- `upcoming=true`: `end_date >= today` (date-only; combine with `active` for "current/upcoming active" events).
- `date_from > date_to` â†’ 422. Still read-only; mutation remains out of scope for students.
- Backwards compatibility: internal consumers (dashboard `_build_upcoming_events`, eligibility service) call the repository directly with no filters and are unchanged; the only HTTP consumer (Events page) keeps working and now receives only active events.

## Weekend behavior (before vs after)

| Date | Before ([5,6] interpreted as JS) | After (DEFAULT_WEEKENDS [0,6]) |
|---|---|---|
| 2026-08-13 Thu | working | working |
| 2026-08-14 Fri | **non-working** | **working** âœ… |
| 2026-08-15 Sat | non-working | non-working |
| 2026-08-16 Sun | **working** | **non-working** âœ… |

## MID_SEMESTER_BREAK behavior

Now a closure (same tier as SEMESTER_BREAK, priority 60): an active MID_SEMESTER_BREAK event spanning a date forces that date non-working regardless of `is_working_day`, consistent with the documented break/closure family (`docs/05_CALENDAR_ENGINE.md` priority table groups SEMESTER_BREAK/MID_SEMESTER_BREAK at 60). No new semantics invented.

## Verification (static / in-process only; no browser testing)

- `backend/.venv/Scripts/python -m compileall backend/app backend/scripts` â€” **PASS**
- `npx tsc --noEmit` (frontend) â€” **PASS** (0 errors)
- In-process engine/service execution (real `calendar_engine.py` + `CalendarService` with stubbed repo + `get_attendance_window`) â€” **17/17 PASS**: Fri working, Sat/Sun non-working; CalendarService + EligibilityService import the shared constant; MID_SEMESTER_BREAK closure; inactive event ignored; date-range bounding; quiz-window bounds unchanged (Q1 from commencement, day before quiz) with corrected teaching-day dates.
- Read-only DB checks (representative ORM rows inside a rolled-back transaction): /events filters (active/inactive/upcoming/date-range, 8 cases) and dashboard enrollment scoping (temp unenrolled subject ZZZ-999 excluded; 2026-07-15 control still exactly 6 sessions for both test user and Aditya). All transactions rolled back.
- Live read-only SQL confirms DB untouched: academic_events 0 Â· subjects 9 Â· class_sessions 684 Â· attendance_records 84 Â· enrollments 18 Â· users 30.

## Database mutation status

- **No INSERT/UPDATE/DELETE persisted.** `academic_events`, `class_sessions`, `attendance_records`, `subjects`, `users`, `student_enrollments` all unchanged. Test rows existed only inside rolled-back transactions. The `attendancedashpro_db` container was started (no data change) for read-only checks.

## Do Not Touch Again (from this phase)

- The weekend convention (`DEFAULT_WEEKENDS` in `calendar_engine.py`) â€” single source of truth; services must import it, never re-invent literals.
- The /events read contract (active default true, range-overlap dates, upcoming) and the repo's filter semantics.
- The enrollment-scoped dashboard aggregation join.

## Deferred (intentionally NOT done here)

- Calendar UI / month-day calendar / calendar route Â· Events CRUD Â· admin role system Â· event validation registry Â· event seeding Â· eventâ†’class_sessions integration Â· EXTRA/CLASS_CANCELLED session mutation Â· substitution schedule implementation Â· quiz/event integration Â· semester/section event scoping Â· timetable section schema redesign Â· TodayClassesCard cleanup Â· engine type-hint refactor Â· legacy attendance-window field restoration.

---

## PHASE 6.2 - CALENDAR READ MODEL & API

Status: **COMPLETE** (2026-08-14). Backend-only calendar read model for the future Phase 6.3 calendar UI. No UI, no event CRUD, no admin, no seeding, no eventâ†’session integration.

## Endpoint contract

- `GET /api/v1/calendar?year=YYYY&month=M` (JWT) â€” month-bounded calendar read model.
- `year` Query `ge=2000 le=2100`; `month` Query `ge=1 le=12` â€” FastAPI/Pydantic validation, malformed/out-of-range input â†’ 422 (no custom error semantics).
- Read-only. Returns `CalendarMonthResponse` (never raw ORM).
- Existing endpoints unchanged: `GET /calendar/today`, `GET /calendar/{date}`.

## Read-model structure (CalendarMonthResponse â†’ CalendarDayItem[])

```
{
  year, month,
  semester_start, semester_end,          // student's real academic bounds (None when no context)
  effective_start, effective_end,        // intersection of month and semester
  days: [ {
    date, is_working_day, day_type, is_teaching_day,
    original_day_of_week, substitution_schedule_override,
    non_working_reason,                   // dominant event title or 'Weekend'; None when working
    events: [AcademicEventResponse],      // active events only
    session_count,                        // scheduled sessions for the student's enrolled subjects
  } ]
}
```

- `CalendarDayItem` extends the existing `AcademicDayResponse` (reuse of the established day shape).
- Month entirely outside the semester â†’ `days: []` with inverted `effective_start > effective_end` (truthful empty result, never invented dates).
- No academic context (no section/semester) â†’ `days: []` with null bounds.

## Semester bounding

- Resolved through the same `UserRepository.get_academic_context` used by /student/me, Track and History â€” no hardcoded dates.
- `effective_start = max(month_start, semester_start)`; `effective_end = min(month_end, semester_end)`; month bounds computed server-side (Dec 12-31 handled).

## Calendar-engine reuse

- Day resolution (`is_working_day`, `is_teaching_day`, `day_type`, `events`, `substitution_schedule_override`) delegates entirely to `calendar_engine.get_academic_day` with the canonical `DEFAULT_WEEKENDS`; no second weekday/closure algorithm. `non_working_reason` is a render-only string derived from the engine's `AcademicDay` output (dominant event title, else "Weekend").
- Phase 6.1 semantics preserved: Fri 2026-08-14 working; Sat/Sun non-working; MID_SEMESTER_BREAK is a closure; inactive events never affect resolution.

## Event handling

- `CalendarRepository.get_all_events(active=True, date_from=effective_start, date_to=effective_end)` â€” Phase 6.1 /events semantics (active only, date-range overlap). Inactive/past events outside the month never leak into the read model. Empty table â†’ structurally correct calendar with empty `events` arrays.

## Session-count implementation

- One `AttendanceRepository.get_sessions_with_status(user.id, effective_start, effective_end)` query for the whole range (no N+1), grouped by date in memory; the method is the Phase 6.1 enrollment-scoped canonical aggregation source.
- `session_count` = scheduled `class_sessions` rows for the authenticated student's enrolled subjects on that date (cancelled sessions are still scheduled rows and are included). No attendance percentages, quiz, forecast, or safe-skip mathematics.

## Files changed

| File | Change |
|---|---|
| `backend/app/schemas/calendar.py` | `CalendarDayItem` (extends `AcademicDayResponse`, adds `non_working_reason`, `session_count`) + `CalendarMonthResponse` |
| `backend/app/services/calendar_service.py` | `get_month_view(user, year, month)` (+ `_month_bounds`, `_non_working_reason`); service now composes `UserRepository` + `AttendanceRepository` |
| `backend/app/api/v1/endpoints/calendar.py` | `GET ""` with `year`/`month` Query validation |

## Verification (static / in-process / read-only; no browser testing)

- `compileall backend/app` â€” PASS; `npx tsc --noEmit` â€” PASS (0 errors).
- Service-level (live DB, read-only): Aug 2026 semester bounds + effective range + 31 days; Fri 08-14 working, Sat 08-15 / Sun 08-16 non-working with "Weekend" reason; session counts cross-checked against independent enrollment-scoped SQL; Jul 2026 clamp to 07-15; Dec 2026 full month; Jan 2026 / Jan 2027 empty; MID_SEMESTER_BREAK â†’ non-working "Mid Semester Break"; inactive holiday ignored; September holiday excluded from August â€” 24/24 PASS.
- API contract (in-process httpx ASGITransport on the real `api_router`): 7 validation cases (month 0/13, year 1999/2101, non-numeric, missing params) â†’ 422; valid Aug 2026 â†’ 200 with exact structure; Jan 2027 â†’ 200 empty; `/calendar/today` and `/calendar/{date}` still work â€” 21/21 PASS.
- Read-only SQL: academic_events 0 Â· subjects 9 Â· class_sessions 684 Â· attendance_records 84 Â· enrollments 18 Â· users 30 (unchanged).

## Database mutation status

- **ZERO INSERT/UPDATE/DELETE persisted.** Event rows existed only inside a rolled-back transaction; no test sessions, no attendance, no user/enrollment changes.

## Do Not Touch Again (from this phase)

- The `GET /api/v1/calendar?year=&month=` contract and `CalendarMonthResponse` shape (Phase 6.3 renders it directly).
- `CalendarService.get_month_view` semantics (semester clamp, engine delegation, single-query session counts).

## Deferred (intentionally NOT done here)

- Calendar UI/route, month navigation, date selection, event forms, Upcoming/Today/Past redesign, admin interface â€” Phase 6.3+. Also deferred: event CRUD, admin roles, validation registry, seeding, eventâ†’class_sessions integration, substitution, quiz/event integration, scoping, timetable schema, TodayClassesCard cleanup, type-hint refactor, window-field restoration.

---

## PHASE 6.3 â€” CALENDAR UI

Status: **COMPLETE** (2026-08-14). Production Calendar UI at `/calendar`, rendering the frozen Phase 6.2 read model directly. Frontend-only; no backend changes; no event CRUD, admin roles, seeding, or eventâ†’session integration.

## Route & shell

- `frontend/src/app/(authenticated)/calendar/page.tsx` â€” authenticated route inside the existing AppShell route group (no second shell, no duplicated auth).
- `TopNav` gains a single `Calendar` item (`CalendarRange`, `/calendar`, between History and Events). Nothing replaced/redesigned; `/tools/events` untouched (Phase 6.4 owns it).

## API integration

- `useCalendarMonth(year, month)` in `frontend/src/hooks/useApi.ts` â€” SWR hook with stable per-month cache key `GET /api/v1/calendar?year=&month=`; standard cache settings; exposes `mutate` for the retry action. One logical request per month (no per-day requests).
- Types in `frontend/src/types/api.ts`: `CalendarMonthResponse` (year, month, semester_start/end, effective_start/end, days) and `CalendarDayItem` (extends existing `AcademicDayResponse`, adds `non_working_reason`, `session_count`).

## Calendar grid

- `frontend/src/components/calendar/CalendarGrid.tsx` â€” presentation-only grid. Backend day items are placed on the real local month (Sunday-first alignment matching the backend `getDay()` convention). Cells outside the API's effective range are empty layout placeholders, clearly not academic days.
- Day cells are native buttons: date number, session count when > 0 (working days), event dot/count, non-working reason text; selected state uses the accent ring; today uses a restrained primary ring.
- Zero calendar semantics computed client-side â€” the UI renders `is_working_day`, `non_working_reason`, `events`, `session_count` exactly as returned. No weekday checks, no holiday inference, no `MID_SEMESTER_BREAK` special-casing, no session counting.

## Month navigation

- Previous/Next/Today, all month-based and timezone-safe (explicit local year/month state; Jan â†” Dec rollover correct). Navigation beyond backend `semester_start`/`semester_end` is disabled when bounds are known â€” no hardcoded dates.
- Today navigates to the current local month. Months outside the semester render the truthful empty state using the backend-provided bounds.
- While a month fetches, the last successful month stays visible (dimmed, `Loading <month>` hint) instead of blanking the page.

## Selected-day behavior

- Fresh month: select today if the backend returned it, else the first effective day, else nothing. Manual selections are tracked per month key and never overridden while the month is unchanged.

## Loading / error / empty states

- First load: skeleton grid + skeleton detail. Month switch: retained grid + hint. API failure: calendar-specific error card with retry (`mutate`). `days.length === 0`: truthful "No academic days in this period" empty state (not an API failure, no fake days).

## Accessibility

- Day cells are real buttons with descriptive `aria-label` and `aria-pressed`; focus-visible rings provided by the design system. No button-as-link composition, so no `nativeButton={false}` requirement arises. Reuses existing `lib/date.ts` helpers (`getLocalDateString`, `parseLocalDate`, `formatLongDate`).

## Files changed

| File | Change |
|---|---|
| `frontend/src/app/(authenticated)/calendar/page.tsx` | New `/calendar` route (nav controls, month state, selection, states) |
| `frontend/src/components/calendar/CalendarGrid.tsx` | New presentation-only monthly grid |
| `frontend/src/components/calendar/DayDetail.tsx` | New selected-day detail card |
| `frontend/src/hooks/useApi.ts` | `useCalendarMonth(year, month)` |
| `frontend/src/types/api.ts` | `CalendarMonthResponse`, `CalendarDayItem` |
| `frontend/src/components/layout/TopNav.tsx` | Minimal `Calendar` nav item |

## Verification (static only; no browser testing)

- `npx tsc --noEmit` â€” PASS (0 errors).
- `git diff` â€” backend: no changes (Phase 6.2 contract files untouched); no migrations/schema changes; no attendance/eligibility engine changes; no event CRUD; no fake database events.

## Database mutation status

- **ZERO INSERT/UPDATE/DELETE persisted.** No seeding, no test data, no schema changes.

## Do Not Touch Again (from this phase)

- The `/calendar` route + grid + detail + `useCalendarMonth` hook are the Phase 6.3 UI surface; the Phase 6.2 backend contract remains frozen. `/tools/events` is untouched and owned by Phase 6.4.

## Deferred (intentionally NOT done here)

- Events page upgrade (Upcoming/Today/Past, filters, details) â€” Phase 6.4. Also deferred: event CRUD, admin roles, validation registry, seeding, eventâ†’class_sessions integration, substitution, quiz/event integration, scoping, timetable schema, TodayClassesCard cleanup, type-hint refactor, window-field restoration.

---

## PHASE 6.4 â€” EVENTS PAGE UPGRADE

Status: **COMPLETE** (2026-08-14). Production read-only Academic Events page at `/tools/events` (Upcoming/Today/Past grouping + filters). Frontend-only; no backend changes; no event CRUD, admin, or seeding.

## Route & architecture

- `/tools/events` rebuilt inside the existing AppShell/TopNav structure; the backend `GET /api/v1/events` endpoint remains the single data authority (event existence, dates, types, holiday/class metadata, active state).
- Presentation-only grouping: browser-local today (`getLocalDateString`) vs the backend-provided `[start_date, end_date]` â€” today inside range â†’ **Today**; `end_date` after today â†’ **Upcoming** (start asc); else â†’ **Past** (newest first). No working-day/holiday/closure semantics computed in React.

## Filters

- Event type â€” client-side over the already-fetched set (the API has no type filter).
- State â€” Active / Inactive, honestly supported by the Phase 6.1 `active=true|false` contract (no "all" option, since the contract cannot express it in one request).
- From / To â€” server-side inclusive range-overlap via `date_from`/`date_to`; inverted ranges are blocked client-side with a hint (never sent as a 422).
- Reset button clears everything. One logical request per filter combination.

## Event rendering

- `EventRow` card: date block (day/month), humanized type title (robust for unknown/future types), semantic badges (Today/Holiday/Extra/Cancelled/class type/Inactive), date range (end only when different), substitution-schedule note, and a `Calendar` link affordance to `/calendar` (no query params invented; calendar route untouched).
- Section headings with counts; empty sections show muted placeholder lines.

## Loading / error / empty

- Loading: skeleton sections (no fake empty state before the response resolves).
- Error: events-specific error card with **Try again** via SWR `mutate`; an API failure never renders "No events".
- Empty: "No events scheduled" (truthful zero-row state â€” `academic_events` has 0 rows) vs "No events match the selected filters".

## Files changed

| File | Change |
|---|---|
| `frontend/src/app/(authenticated)/tools/events/page.tsx` | Rebuilt page (filters, grouping, sections, states) |
| `frontend/src/components/events/EventRow.tsx` | New compact read-only event row |
| `frontend/src/hooks/useApi.ts` | `useEvents(params)` â€” Phase 6.1 query contract |
| `frontend/src/types/api.ts` | `EventsParams` |

## Verification (static only; no browser testing)

- `npx tsc --noEmit` â€” PASS (0 errors); ESLint on changed files â€” PASS.
- `git diff` â€” backend: no changes; no migrations/schema changes; no attendance/eligibility engine changes; no event CRUD; no fake events.

## Database mutation status

- **ZERO INSERT/UPDATE/DELETE persisted.** No seeding, no test data, no schema changes.

## Do Not Touch Again (from this phase)

- The rebuilt `/tools/events` page + `useEvents(params)` + `EventsParams` are the Phase 6.4 UI surface; the Phase 6.1 `/events` contract and Phase 6.2/6.3 calendar surface remain frozen.

## Deferred (intentionally NOT done here)

- Event persistence/admin auth/seeding â€” Phase 6.5. Also deferred: event CRUD, admin roles, validation registry, seeding, eventâ†’class_sessions integration, substitution, quiz/event integration, scoping, timetable schema, TodayClassesCard cleanup, type-hint refactor, window-field restoration.

---

## PHASE 6.5 â€” EVENT PERSISTENCE, ADMIN AUTHENTICATION & SEEDING

Status: **COMPLETE** (2026-08-14). Admin role system (`users.role`), admin-only event mutation API, centralized validation registry, minimal admin UI on `/tools/events`, controlled idempotent seeding (17 QUIZ_DAY events). Read contracts (Phase 6.1 events, Phase 6.2 calendar) unchanged; Phase 6.4 student experience unchanged.

## Admin authorization

- `UserRole` (`STUDENT`/`ADMIN`) enum in `backend/app/models/enums.py`; `users.role` column (`backend/app/models/user.py`, default + `server_default` STUDENT); migration `d4e5f6a7b8c9_add_user_role.py` **applied** â€” 30 existing users backfilled STUDENT.
- `require_admin` in `backend/app/api/dependencies/deps.py` â†’ 403 for non-ADMIN. Role resolved from DB per request (never JWT/body/query/hardcoded); no self-assignment â€” `backend/scripts/provision_admin.py` only (run for 2401220100027).
- `/student/me` + `/student/sync` now include `role` (`StudentProfile.role`).

## Validation registry & service layer

- `backend/app/services/event_registry.py` â€” `EVENT_TYPE_RULES` for all 14 types (requiresSubject/requiresClassType/allowedClassTypes/isClosure/isGlobal) ported from legacy `AcademicEventRegistry` + engine closure semantics; `validate_event()`; `EventValidationError`; `VALID_SUBSTITUTION_DAYS` from engine `DAY_NAMES`.
- `backend/app/repositories/event_repo.py` â€” `EventRepository` (get_by_id, subject_exists, exists_active_duplicate), `EventNotFound`, `EventConflict`.
- `backend/app/services/event_service.py` â€” create/update (partial via `model_fields_set`)/deactivate; one transaction per mutation.
- Admin-only endpoints in `backend/app/api/v1/endpoints/events.py`: POST (201), PATCH `/{event_id}`, DELETE `/{event_id}` (safe deactivation `active=false`, ADR 004; re-enable via PATCH). Errors: 422 validation, 404 missing event/subject, 409 identical ACTIVE duplicate (ported from legacy js/events-controller.js). `GET` read contract unchanged (list-only).

## Admin UI (additive to Phase 6.4)

- `frontend/src/components/events/eventRules.ts` (NEW) â€” registry mirror for form field visibility; backend registry authoritative.
- `frontend/src/components/events/EventFormDialog.tsx` (NEW) â€” create/edit dialog; only model-real fields; client-side checks; handles loading + 403/404/409/422.
- `frontend/src/components/events/EventRow.tsx` â€” optional `onEdit`/`onDeactivate` admin actions (two-step inline deactivate confirm).
- `frontend/src/app/(authenticated)/tools/events/page.tsx` â€” admin mode gated by `useProfile().role === "ADMIN"`: Add Event toolbar, row actions, dialog; after save/deactivate â†’ `mutate()` + current-month calendar revalidation. Students: unchanged Phase 6.4 page.
- `frontend/src/hooks/useApi.ts` â€” `useEventMutations()`; `frontend/src/types/api.ts` â€” `AcademicEventPayload`, `StudentProfile.role`.

## Seeding

- **Data gap (documented):** no authoritative institutional holiday/break/working-Saturday dates exist anywhere in the repo â€” nothing seeded for them.
- `backend/scripts/seed_academic_events.py` â€” 17 QUIZ_DAY events derived from the authoritative `quiz_schedules` (17 SCHEDULED; BCS-054 Q3 UNRESOLVED skipped as unscheduled). Idempotency key `(event_type, subject_id, start_date, end_date)`; rerun verified 17â†’17 skipped; deactivated rows never resurrected.

## Verification

- Backend: `compileall` PASS; `alembic upgrade head` applied (head `d4e5f6a7b8c9`); `verify_phase_6_5.py` **23/23 PASS** (security matrix STUDENT/ADMIN/unauth, create, 409 duplicate, 404 subject, partial PATCH absent-vs-null, deactivate + re-enable, read-contract regression student+calendar, seed idempotency, cleanup).
- Frontend: `npx tsc --noEmit` PASS; ESLint PASS on changed files; `npm run build` PASS. Browser testing deferred to the user.

## Database mutation status

- **Schema:** `users.role` added + backfilled (migration `d4e5f6a7b8c9`). **Data:** 17 seeded QUIZ_DAY events inserted (`academic_events`); 1 user set ADMIN (2401220100027); verifier test rows created then deleted. **Untouched:** attendance_records, class_sessions (684), student_enrollment, subjects, quiz_schedules, all user history.

## Do Not Touch Again (from this phase)

- Backend is the single authority for roles, event validation, and mutations; the frontend admin surface is UX only. `GET /api/v1/events` remains list-only. DELETE = deactivation (reversible), never a hard delete.

## Deferred (intentionally NOT done here)

- Phase 6.6 â€” eventâ†’engine integration (eventâ†’class_sessions generation, holidayâ†’cancellation, extra/substitution lecture generation, quiz-window mutation) â€” explicit next phase, NOT implemented here.
- Phase 6.7 â€” verification/freeze. Institutional holiday/break/working-Saturday dates pending authoritative input.

---

# PHASE 6.6 â€” EVENT â†’ ENGINE INTEGRATION

Status: **COMPLETE** (2026-08-14). Persisted events now mutate the canonical session pipeline â€” closures cancel, CLASS_CANCELLED cancels exactly one occurrence, EXTRA_*/SURPRISE_QUIZ materialize `is_extra` sessions, substitution/working-Saturday project the substituted timetable â€” exactly as the legacy engine's effective schedule dictated. Idempotent, transactional, attendance-safe. No engine rewrites, no schema change, no frontend change.

## What was done

1. **Session synchronizer** (`backend/app/services/event_session_service.py`): `EventSessionSynchronizer.sync_event()` â€” per-date desired schedule from the frozen calendar engine + legacy `getEffectiveDaySchedule` port (base timetable âˆ’ one per CLASS_CANCELLED + one per EXTRA_*/SURPRISE_QUIZ, deterministic priorityâ†’id order), reconciled against `class_sessions`:
   - Closures & CLASS_CANCELLED â†’ `is_cancelled=True` (rows never deleted; cancelled â‰  absent).
   - Extras â†’ `is_extra=True` rows without timetable entries.
   - Working Saturday / substitution â†’ timetable-materialized rows (weekend projections deleted when reverted; attended rows never touched).
   - State-based â‡’ idempotent (double sync converges); date-scoped â‡’ deactivation/move automatically reverts old effects.
   - Sessions only created within the baseline span (2026-07-15 â†’ 2026-12-31).
2. **Session repository** (`backend/app/repositories/session_repo.py`): timetable/span/range reads + attendance-guard + `add_session` / `delete_session`.
3. **Service wiring** (`backend/app/services/event_service.py`): sync runs in the same transaction as create/update/deactivate; updates sync the union of old+new ranges so moved events revert the old dates.
4. **Counting corrections** (cancelled â‰  pending): `attendance_repo` (both count queries), `dashboard_service` (`_build_overall`, `_build_weekly`), `calendar_service` (`get_month_view` session_count) now exclude `is_cancelled`. Shapes/engines unchanged.
5. **Verification** (`backend/scripts/verify_phase_6_6.py`): **36/36 PASS** â€” closureâ†’5 cancelled (none deleted), attended-guard (07-15 untouched), CLASS_CANCELLEDâ†’exactly 1 + total âˆ’1, extraâ†’+1 & restored, double-sync idempotency, SURPRISE_QUIZ, QUIZ_DAY no-op, working-Saturday (5 materialized), PATCH move reverts old date, calendar/daily/eligibility read contracts, deactivation reversal for all types, rollback-tx checks (attended extra preserved; 3-day range â†’ 3 extras; deactivation no-op on 2nd sync), final exact baseline (17/684/0/0/89). 6.5 regression 23/23 PASS.

## Database state after 6.6

- Exactly the pre-6.6 baseline: events=17, sessions=684 (0 cancelled, 0 extra), attendance_records=89, enrollments=18, subjects=9, quiz_schedules=18, users=30 (1 ADMIN). Test rows hard-deleted; rollback tests committed nothing.

## Do Not Touch Again (from this phase)

- Eventâ†”session semantics live ONLY in `EventSessionSynchronizer`; consumers must not re-derive them. Cancelled sessions are never deleted and never receive attendance (409). Engine mathematics remain frozen.

## Deferred (intentionally NOT done here)

- Phase 6.7 â€” verification/freeze (explicit next phase, requires go-ahead). Institutional holiday/break/working-Saturday dates pending authoritative input.

---

# PHASE 6.7 â€” CALENDAR & ACADEMIC EVENTS VERIFICATION / FREEZE

Status: **COMPLETE / FROZEN** (2026-08-15). Phase 6 is verified end-to-end and frozen. This was NOT a feature phase â€” no engine rewrites, no schema redesign, no frontend changes, no new business logic.

## What was done

1. **`backend/scripts/verify_phase_6_7.py` (NEW) â€” 31/31 PASS**, closing every gap not covered by the 6.5/6.6 verifiers:
   - **6.1 contracts:** `DEFAULT_WEEKENDS=[0,6]` (JS convention Sunday=0, Saturday=6); MID_SEMESTER_BREAK is a closure sharing SEMESTER_BREAK's tier 60; `/events` active-default, inverted range â†’ 422, `upcoming=true`.
   - **6.2 read model:** truthful empty month outside semester (Jan 2026); July clamps to 2026-07-15; December respects 2026-12-31; weekends correct; QUIZ_DAY stays a working day.
   - **6.5:** seeding integrity (17/17 QUIZ_DAY, all active, nothing fabricated, matches SCHEDULED quiz_schedules); deactivate â†’ PATCH re-enable converges.
   - **6.6:** all five additional closure types cancel every session on their date (rows preserved, day non-working); EXTRA_TUTORIAL/EXTRA_PRACTICAL â†’ exactly one `is_extra` each; WORKING_DAY_OVERRIDE â†’ working day, zero session mutation; cancelled session â†’ **409** on attendance.
   - **Baseline:** 10-table exact restoration (17/684/0/0/89/18/9/18/30/1).
2. **Regression:** 6.5 â†’ 23/23, 6.6 â†’ 36/36, 6.7 â†’ 31/31 = **90/90**; `compileall` PASS; verifiers converge in any order.
3. **Static review:** calendar + events UIs are presentation-only; layering APIâ†’Serviceâ†’Repositoryâ†’DB intact; `EventSessionSynchronizer` sole sync path; no engine rewrites; no hardcoded dates in `app/`; no N+1; role from DB per request; no schema change beyond the 6.5 migration.

## Database state after 6.7

- Exact baseline: events=17, sessions=684 (0 cancelled, 0 extra), records=89, enrollments=18, subjects=9, quizzes=18, users=30 (1 ADMIN). No test residue.

## Do Not Touch Again (from this phase)

- Phase 6 is **FROZEN**: calendar engine semantics, events/calendar API contracts, calendar/events UI, event registry, event service + synchronizer wiring, the three verifiers, and the documented baseline. Any change requires a new phase with its own verification.

---

# PHASE 7.0 â€” QUIZ ELIGIBILITY & SCHEDULE REALITY AUDIT

Status: **COMPLETE** (2026-08-15) â€” READ-ONLY audit, **PASS** (no defects to fix; discrepancies reported for decision). No implementation, no DB mutation, no commit.

## What was audited

1. **Eligibility path:** `GET /api/v1/quiz-eligibility/{code}/{cycle}` â†’ `EligibilityService` â†’ `calendar_engine.get_attendance_window` â†’ `attendance_repo.get_subject_counts_between` â†’ `eligibility_engine.evaluate_quiz_eligibility` â†’ `meets_attendance_target`/`optimize_attendance`.
2. **Schedule reality:** quiz_cycles/eligibility_policies (70/75/75), 18 quiz_schedules (17 dated SCHEDULED; **BCS-054 Q3 UNRESOLVED**), 17 QUIZ_DAY events, semester V (2026-07-15 â†’ 2026-12-31), 9 subjects (6 theory + 3 labs).
3. **Legacy parity:** `js/quiz-engine.js`, `attendance-engine.js`, `calendar-engine.js`, `ui.js`, docs 05/06/07/15, `S4_PRODUCT_SPEC`, ADR-010.
4. **Live math trace:** engine-in-process against the real DB for student `9999999999999` (0 records) and admin `2401220100027` (84 records, overall 71.43% recorded-only / 46.51% incl. pending).

## Verification summary

- Formula + window + optimizer parity with legacy: **PASS** (byte-equivalent rules; identical ADR-010 window bounds).
- Practical exclusion from eligibility, inclusion in overall: **PASS**.
- Quiz-day attendance via normal sessions; SURPRISE_QUIZ/EXTRA_* via `is_extra` sessions: **PASS** (architecture-level).
- DB baseline re-confirmed: 17/684/0/0/89/18/9/18/30/1. **DB mutation status: NONE.**
- Discrepancies (reported, NOT fixed): Q-D1 eligible-vs-reachable semantics (all 18 subjectÃ—cycle results say eligible=True today; legacy says "NEEDS ATTENDANCE"); Q-D2 reference-UI data contract unavailable from the API; Q-D3 single-rule vs "(Criterion 1) OR (Criterion 2)"; Q-D4 hardcoded `quiz_applicable=True`; Q-D5 `combined_threshold` never read; Q-D6 raw-range counting (latent); **Q-D7 rule G students-add/remove-events vs frozen admin-only mutations**; Q-D8 overall denominator; Q-D9 quiz-day attendance without a session; Q-D10 BCS-054 Q3 date.

## Database state after 7.0

- Exact baseline preserved (no writes): events=17, sessions=684 (0 cancelled, 0 extra), records=89, enrollments=18, subjects=9, quizzes=18, users=30 (1 ADMIN).

## Do Not Touch Again (from this phase)

- Same as Phase 6.7 (frozen list) plus: **the audit is documentation-only** â€” the eligibility engine, eligibility API contract, and the frozen Phase 6 event system remain untouched until Q-D1â€¦Q-D10 are decided and Phase 7.1 is authorized.

## Deferred (intentionally NOT done here)

- Institutional holiday/break/working-Saturday dates â€” pending authoritative product input (documented data gap).
- Browser/manual testing â€” the user's responsibility (no automation run).

---

# PHASE 7.1 â€” CANONICAL QUIZ ELIGIBILITY CONTRACT + REFERENCE SUBJECT CARDS

Status: **COMPLETE (2026-08-15) â€” PASS** (26/26 verification + full regression). Report: `docs/phase_7_1_implementation_report.md`.

## What was implemented

1. **Schedule:** BCS-054 Q3 â†’ 2026-10-23 SCHEDULED (from `timetable.json`; seed-script override removed). `seed_academic_events.py` created the 18th QUIZ_DAY event (calendar-only). Canonical schedule = 18/18 dated SCHEDULED, byte-exact vs timetable.json. Q1/Q2 windows unchanged; Q3 window [09-28 â€¦ 10-22].
2. **Contract (`EligibilityResult` extended additively):** `state` (ELIGIBLE/RECOVERABLE/NOT_ELIGIBLE/UNRESOLVED), `subject_name`, `category`, `quiz_date`, `lecture`/`tutorial` counts + `lecture_pct`/`tutorial_pct`/`average_pct`, `required_percentage`, `criterion_i`/`criterion_ii` (value/threshold/passed/explanation), `final_criterion` ("Criterion I OR Criterion II"), `recoverable`, `explanation`. `is_eligible` = currently eligible (Q-D1 fixed). Thresholds from `eligibility_policies` for both routes (Q-D5 fixed). Labs â†’ 404 via `subjects.quiz_applicable` (Q-D4 fixed). Optimization fields byte-identical to the attendance engine.
3. **Engine:** additive extension at the documented extension point (no rewrite, no second math model): criteria + state from the same counts at current and best-case scenarios; `optimize_attendance`/`meets_attendance_target`/`get_attendance_window` untouched.
4. **UI:** `/tools/quiz-schedule` â†’ "Quiz Eligibility": cycle tabs (Quiz I/II/III, default Quiz I), reference subject cards (code, THEORY badge, name, status badge, attended/total/%, average vs required, expandable View Calculation incl. must-attend/safe-skip), loading skeletons, error+Retry, empty/unresolved states. React presentation-only (no business math). Old `SubjectQuizSchedule.tsx` removed.
5. **Dashboard:** no changes (frozen) â€” snapshot becomes truthful via corrected `is_eligible`.

## Verification summary

- `verify_phase_7_1.py`: **26/26 PASS** (canonical schedule vs timetable.json; BCS-054 Q3; cycles; practical exclusion; QUIZ_DAY calendar-only; 18 upcoming; Q1/Q2/Q3 windows; lecture-only + L+T formulas; RECOVERABLE real data; ELIGIBLE/NOT_ELIGIBLE/UNRESOLVED rollback scenarios; Criterion I/II + final OR; optimizer parity; UI analytics contract; labs 404; per-user scoping; history intact 89 records; quiz-day + surprise-quiz canonical; exact baseline restore).
- Frozen regression: 6.5 **23/23** Â· 6.6 **36/36** Â· 6.7 **31/31** (Phase 6.7 count assertions maintained 17â†’18 for the new authoritative schedule â€” documented, not weakened).
- Static: compileall clean Â· tsc clean Â· ESLint 0 errors Â· `next build` exit 0.

## Database state after 7.1

- New baseline (verified post-run): events=18 Â· sessions=684 (0 cancelled, 0 extra) Â· records=89 Â· enrollments=18 Â· subjects=9 Â· quizzes=18 (18 SCHEDULED) Â· users=30 (1 ADMIN).
- Mutation (minimal, reversible): BCS-054 Q3 `quiz_schedules` row â†’ 2026-10-23 SCHEDULED; one QUIZ_DAY event seeded by the canonical script. Reversal documented in the implementation report.

## Do Not Touch Again (from this phase)

- Same as Phase 6.7 (frozen list), plus: Phase 7.1 eligibility state derivation, criteria contract, and the reference-card API fields are now the canonical contract â€” changes require a new phase with its own verifier. The Phase 6.7 verifier's authoritative counts (18) are maintained, not weakened.

## Deferred (intentionally NOT done here)

- Q-D6 teaching-day counting Â· Q-D8 overall denominator Â· Q-D7 student event-mutation capability (product/security decision) Â· date-aware default cycle tab.
- Browser/manual testing â€” the user's responsibility (see MANUAL TESTING CHECKLIST in the implementation report).

---

# PHASE 7.2 â€” QUIZ ELIGIBILITY ANALYTICS REFINEMENT

Status: **COMPLETE (2026-08-15) â€” PASS** (26/26 verification + full regression). Report: `docs/phase_7_2_implementation_report.md`.

## What was decided & implemented

1. **Q-D6 (raw-range counting) â€” NOT a defect under the locked spec.** The `class_sessions` table IS the teaching-day-resolved effective schedule (baseline expands only teaching days; closures cancel; extras only on working days; cancelled excluded from counts). No counting change. Regression-proven: all 18 subject/cycle combos equal a teaching-day enumeration with no off-teaching-day session counted; closure cancels â†’ excluded + 409; EXTRA_LECTURE on a working day counted; SURPRISE_QUIZ on a non-working day materializes ZERO sessions (no divergence possible via the canonical event path).
2. **Q-D8 (overall denominator) â€” recorded-only, ERP/legacy semantics.** Pending excluded from the CURRENT denominator (legacy `computeCurrentOverallAttendance`, S4 Â§10) but never converted to absent â€” always counted and shown separately. Dashboard overall card already showed pending; the quiz eligibility card now shows a muted "Â· X pending" on Lecture/Tutorial rows (reference visual language otherwise untouched). Verified: 71.43% recorded-only vs explicitly-not 46.51%; history + subject current/forecast identical semantics; zero-record student overall = null.
3. **Q-D7 (mutation / eligibility timing) â€” intentional product restriction (B).** Attendance mutations are student-scoped + enrollment-authorized (403) + cancelled-protected (409); EVENT mutations stay admin-only (frozen 6.5 â€” rule G is a future product capability). Eligibility is computed read-time â€” a mutation propagates to the next read immediately (verified).
4. **Date-aware default Quiz tab.** New canonical read-only `GET /api/v1/quiz-eligibility/current-cycle`: next upcoming SCHEDULED quiz â†’ latest resolved cycle â†’ fallback Quiz I (never invents dates). The Quiz Eligibility page preselects the tab from it (`useCurrentQuizCycle`); manual tab selection overrides; tab state is client-only. Today â†’ Quiz I (next quiz 2026-08-24); Quiz Iâ†’IIâ†’IIIâ†’latest_resolvedâ†’fallback transitions verified in rollback transactions.

## Verification summary

- `verify_phase_7_2.py`: **26/26 PASS** (Q-D6 Ã—4 Â· Q-D8 Ã—5 Â· Q-D7 Ã—4 Â· current-cycle Ã—6 Â· BCS-054 Q3 Â· UNRESOLVED Â· labs 404 Â· dashboard-snapshot==canonical Â· Track/History/Eligibility consistency Â· per-user isolation Â· exact baseline restore).
- Frozen regression: 6.5 **23/23** Â· 6.6 **36/36** Â· 6.7 **31/31** Â· 7.1 **26/26** â€” no assertions weakened.
- Static: compileall clean Â· `npx tsc --noEmit` clean Â· ESLint 0 errors Â· `next build` exit 0.

## Database state after 7.2

- Exact baseline preserved (ZERO mutations): events=18 Â· sessions=684 (0 cancelled, 0 extra) Â· records=89 Â· enrollments=18 Â· subjects=9 Â· quizzes=18 (18 SCHEDULED) Â· users=30 (1 ADMIN) Â· max record date 2026-08-14. BCS-054 Quiz III = 2026-10-23 confirmed.

## Do Not Touch Again (from this phase)

- Same as Phase 6.7 + 7.1 (frozen lists), plus: the current-cycle endpoint contract, the Q-D6/Q-D8/Q-D7 documented decisions, and the quiz-card pending indicator are now canonical â€” changes require a new phase with its own verifier. No commit was made.

## Deferred (intentionally NOT done here)

- Q-D9 quiz-day attendance without a session (product decision) Â· rule G student event capability (product/security decision) Â· Phase 8 Attendance Analytics/Intelligence (roadmap next).
- Browser/manual testing â€” the user's responsibility.

---

# PHASE 8.0 â€” ATTENDANCE ANALYTICS & INTELLIGENCE: AUDIT / CONTRACT DESIGN

Status: **COMPLETE (2026-08-15) â€” PASS** (read-only audit; zero code, zero DB change).
Report: `docs/phase_8_0_attendance_analytics_audit.md`.

## Objective

Establish the exact architectural and mathematical contract for Phase 8 (Attendance Analytics / Intelligence) BEFORE any implementation. No analytics API, no analytics UI, no migrations, no new engines, no attendance/eligibility math changes, no DB mutation.

## Findings

- [x] **Architecture:** no analytics layer exists; `dashboard_service` is the de-facto aggregator and already consumes the canonical engines (no second engine). React performs no business math today.
- [x] **Inventory (23 metrics):** overall/weekly/today %, subject current/forecast %, quiz-window %, eligibility states, optimizer deficits, history summary, banding â€” each with pending/cancelled/extra/practical/semester/quiz-window treatment. All current % recorded-only; pending never absent; cancelled excluded; extras included; ERP overall class-weighted; labs excluded from eligibility.
- [x] **4 legacy gaps (additive, NOT new formulas):** practical % not exposed Â· subject-level 75% must-attend/safe-skip not exposed Â· overall forecast not exposed Â· forecast-impact deltas not exposed.
- [x] **React duplications flagged (NOT fixed):** `WeeklyAttendanceCard` re-derives day-bar %; `SubjectAttendanceCard` 75/65 banding vs canonical 80/60 + hardcoded cycle=1; dead `TodayClassesCard`/`FormulaCard`.
- [x] **Performance (latent, NOT fixed):** N+1 dashboard quiz snapshot + subject summaries; overlapping range scans; import-time `date.today()` default.
- [x] **Security:** all reads authenticated + user/enrollment-scoped; one gap flagged (`/attendance/summary/{code}` lacks enrollment 404 â€” consistency only, no leak).
- [x] **Withheld (no definition):** AT-RISK state; weekly/semester trend series â€” candidate definitions in audit Â§J/Â§T for product approval.
- [x] **Proposed 8.1 contract (not implemented):** extend `SubjectAttendanceSummary` (practical %, subject-level optimization, enrollment scope) + new `GET /api/v1/analytics/overview` (overall current/forecast/pending + weekly series + per-subject optimization) + dashboard N+1 fixes + `verify_phase_8_1.py`.

## Verification

- `python -m compileall app scripts` â€” PASS Â· `npx tsc --noEmit` â€” PASS (0 errors) Â· `verify_phase_7_2.py` â€” 26/26 PASS (frozen verifier).
- DB baseline (read-only SELECT): events=18 Â· sessions=684 (0 cancelled, 0 extra) Â· records=89 Â· enrollments=18 Â· subjects=9 Â· quizzes=18 (18 SCHEDULED) Â· users=30 (1 ADMIN) Â· BCS-054 Q3 = 2026-10-23. **DB mutation status: ZERO.**

## Do Not Touch Again (from this phase)

- Same frozen lists as 6.7/7.1/7.2, plus: the Phase 8.0 audit decisions (recorded-only current, ERP overall, AT-RISK + trends withheld, legacy gaps additive-only) are the contract for Phase 8.1.

## Deferred (intentionally NOT done here)

- Phase 8.1 implementation (requires explicit product authorization after review of the audit). Q-D9 and rule G remain separate product decisions.
- Browser/manual testing â€” the user's responsibility.

---

# PHASE 8.1 â€” CANONICAL ANALYTICS READ MODEL

Status: **COMPLETE (2026-08-15) â€” PASS** (backend-only additive read model; zero DB mutation, zero schema change, zero commit).
Report: `docs/phase_8_1_implementation_report.md`.

## Objective

Implement ONLY the backend analytics read-model contract from Phase 8.0: extend `SubjectAttendanceSummary` (practical %, subject-level 75% must-attend/safe-skip, enrollment scope), add `GET /api/v1/analytics/overview` (overall current/forecast/pending + weekly series + per-subject analytics), fix dashboard N+1s, fix the import-time date default, close the enrollment-scope gap. No UI, no AT-RISK, no trend semantics, no new formulas, no new engines.

## Implemented

- [x] **Subject analytics (additive):** `SubjectAttendanceSummary` + `current_practical_pct`, `forecast_practical_pct`, `optimization` (`lecture_deficit`/`tutorial_deficit` = must-attend, `safe_skip_lecture`/`safe_skip_tutorial` = safe-skip) via the canonical engine's `optimize_attendance`; practicals use the canonical session/record pipeline (no quiz-window dependency, no lab engine); Pending stays Pending; cancelled excluded. Existing fields unchanged.
- [x] **`GET /api/v1/analytics/overview`** (authenticated, enrollment-scoped, read-only, deterministic, no raw ORM): overall current = ERP Î£att/Î£recorded (recorded-only); overall forecast = pending-as-attended; pending count; Monday-start weekly read-model series (recorded-only, null gaps); per-subject current/forecast/optimization. AT-RISK / trend semantics / forecast-impact deltas NOT implemented (documented non-goals).
- [x] **Dashboard N+1 fixes (contract-identical):** batched `get_quiz_eligibility_for_subjects` (single canonical engine path), grouped `get_subject_counts_for_user`, one shared range scan for Today/Overall/Weekly; dashboard JSON byte-identical; measured 54 â†’ 23 queries.
- [x] **Endpoint hygiene:** `/attendance/summary` default date resolved per-request; `/attendance/summary/{code}` enrollment 404 (quiz-endpoint pattern).

## Files changed

- Backend: `schemas/attendance.py` Â· NEW `schemas/analytics.py` Â· `services/attendance_service.py` Â· NEW `services/analytics_service.py` Â· `services/eligibility_service.py` Â· `services/dashboard_service.py` Â· `repositories/attendance_repo.py` Â· `repositories/quiz_repo.py` Â· NEW `api/v1/endpoints/analytics.py` Â· `api/v1/endpoints/attendance.py` Â· `api/api.py`.
- Scripts: NEW `scripts/verify_phase_8_1.py`.
- Docs: NEW `docs/phase_8_1_implementation_report.md`; `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md`.
- DB: **NONE**.

## Verification

- `verify_phase_8_1.py` **22/22** (auth; enrollment scoping; ERP overall; forecast; pending; subject summaries; practical %; must-attend/safe-skip + optimizer edge cases; weekly read model; dashboard compatibility + N+1 correctness with query counting; runtime-date behavior; enrollment protection; no duplicate attendance math; exact baseline; frozen 7.2 invariants).
- Frozen regression: 6.5 **23/23** Â· 6.6 **36/36** Â· 6.7 **31/31** Â· 7.1 **26/26** Â· 7.2 **26/26** â€” no assertion weakened.
- Static: `python -m compileall app scripts` PASS Â· `npx tsc --noEmit` PASS (0 errors).

## Database state after 8.1

- Exact baseline preserved (ZERO mutations): events=18 Â· sessions=684 (0 cancelled, 0 extra) Â· records=89 Â· enrollments=18 Â· subjects=9 Â· quizzes=18 (18 SCHEDULED) Â· users=30 (1 ADMIN). BCS-054 Quiz III = 2026-10-23 confirmed.

## Do Not Touch Again (from this phase)

- Same frozen lists as 6.7/7.1/7.2/8.0, plus: the extended `SubjectAttendanceSummary` fields, the `/analytics/overview` contract, the batched dashboard paths, and the runtime-date/enrollment-scope fixes are now canonical â€” changes require a new phase with its own verifier. No commit was made.

## Deferred (intentionally NOT done here)

- Frontend consumption of the read model (Phase 8.2) Â· AT-RISK (T-1) Â· trend product semantics (T-2) Â· dedicated Analytics page (T-3) Â· multi-class forecast phrasing (T-4) Â· Q-D9 Â· rule G.
- Browser/manual testing â€” the user's responsibility.

---

# PHASE 8.2 â€” FRONTEND CONSUMPTION OF THE CANONICAL ANALYTICS READ MODEL

Status: **COMPLETE (2026-08-15) â€” PASS** (frontend-only; zero backend change, zero DB mutation, zero commit).

## Objective

Consume the Phase 8.1 backend read model in the existing Next.js frontend: typed analytics client, backend practical % + subject 75% must-attend/safe-skip on Subjects, overall forecast + weekly series on Dashboard, remove duplicated React banding/percentage math and the hardcoded quiz cycle, delete dead components. No new analytics engine, no React business math, no AT-RISK, no trend semantics, no redesign.

## Implemented

- [x] **Typed analytics client:** `AnalyticsOverviewResponse`/`OverallAnalytics`/`WeeklyAnalyticsItem`/`AnalyticsSubjectItem` (exact backend match) + extended `SubjectAttendanceSummary` (`current_practical_pct`, `forecast_practical_pct`, `optimization`) + `useAnalyticsOverview()` hook.
- [x] **Subjects page:** one overview request feeds all cards (N+1 removed); cards render backend practical %/forecast and must-attend/safe-skip from `summary.optimization`; duplicated 75/65 banding removed (no backend subject status exists â€” none invented); `cycle = 1` replaced by canonical `useCurrentQuizCycle()`.
- [x] **Dashboard:** additive backend forecast line on `OverallAttendanceCard`; `WeeklyAttendanceCard` renders the backend weekly series (null = truthful gap, never 0%) â€” no React percentage derivation.
- [x] **Dead components removed:** `TodayClassesCard.tsx`, `FormulaCard.tsx` (verified zero imports/routes).

## Files changed

- Frontend: `src/types/api.ts` Â· `src/hooks/useApi.ts` Â· `src/components/dashboard/SubjectAttendanceCard.tsx` Â· `src/components/dashboard/SubjectAttendanceGrid.tsx` Â· `src/components/dashboard/home/OverallAttendanceCard.tsx` Â· `src/components/dashboard/home/WeeklyAttendanceCard.tsx` Â· `src/app/(authenticated)/dashboard/page.tsx` Â· DELETED `TodayClassesCard.tsx` Â· DELETED `FormulaCard.tsx`.
- Docs: `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md`.
- Backend: **NONE**. DB: **NONE**.

## Verification

- `npx tsc --noEmit` PASS (0 errors) Â· ESLint clean on all changed files Â· `next build` PASS (14 routes).
- Static inspection confirms: no attendance formulas, no safe-skip math, no eligibility math, no quiz-cycle logic in React; all rendered values are backend fields.

## Database state after 8.2

- **ZERO mutation** â€” no backend/database files touched. Phase 8.1 baseline unchanged.

## Do Not Touch Again (from this phase)

- Same frozen lists as 6.7/7.1/7.2/8.0/8.1, plus: the analytics overview consumption pattern (single overview request for per-subject analytics), the backend-driven subject/overall/weekly rendering, and the canonical-cycle eligibility badge are now canonical â€” changes require a new phase. No commit was made.

## Deferred (intentionally NOT done here)

- AT-RISK (T-1) Â· trend product semantics (T-2) Â· dedicated Analytics page (T-3) Â· multi-class forecast wording (T-4) Â· Q-D9 Â· rule G.
- Browser/manual testing â€” the user's responsibility.

---

# ATTENDANCE UI REFINEMENT â€” SPECIFICATION ALIGNMENT + REFERENCE UI

Status: **COMPLETE (2026-08-15) â€” PASS.** Full report: `docs/attendance_ui_refinement_report.md`. Two spec conflicts were escalated and **authorized by the user**.

## Objective

Align the implementation with the authoritative attendance specification (lecture/tutorial daily marking; (L%+T%)/2 average with L%-only fallback; practicals counted in attendance + overall but excluded from quiz eligibility; event-weighted overall; quiz-day attendance as a real event; student-adjustable events; calendar day = whole schedule) and implement the reference Attendance UI without introducing React business math.

## Authorized decisions (user)

1. **Quiz-day attendance â†’ materialize sessions** on every SCHEDULED quiz date (7 created; 684 â†’ 691; eligibility untouched since windows end at quiz_date âˆ’ 1).
2. **Events â†’ shared schedule, subject-scoped**: students may add/remove flexible subject-scoped events for their own enrollments; global/closure events remain admin-only.

## Implemented

- [x] Quiz-day sessions materialized (`scripts/materialize_quiz_day_sessions.py`, idempotent + `--undo`); all 18 quiz dates recordable; subject + overall attendance include them.
- [x] Student event authorization (backend): `STUDENT_CREATABLE_EVENT_TYPES` + enrollment check; global/closure/quiz-schedule events stay 403; synchronizer guard protects quiz-day sessions from event reconciliation.
- [x] Reference Attendance cards: header (code Â· THEORY/LAB Â· name Â· canonical status), primary %, lecture/tutorial sections (required 75 Â· must-attend Â· safe-skip), combined average with formula caption, practical section for labs, expandable Details with backend forecast/optimizer values. Backend emits `required_pct` + `status` additively; banding consolidated in the attendance engine.
- [x] Student event UI (Events page + form restricted to flexible subject-scoped types).
- [x] Latent fix: `AttendanceMutationResponse.student_id` â†’ `user_id` (successful attendance mutations previously 500'd).

## Files changed

- Backend: `engines/attendance_engine.py` Â· `schemas/attendance.py` Â· `services/attendance_service.py` Â· `services/event_service.py` Â· `services/event_session_service.py` Â· `services/dashboard_service.py` Â· `services/analytics_service.py` Â· `repositories/event_repo.py` Â· `api/v1/endpoints/events.py` Â· `api/v1/endpoints/attendance.py`.
- Scripts: NEW `materialize_quiz_day_sessions.py` Â· NEW `verify_attendance_spec_alignment.py` Â· `verify_phase_6_5.py` Â· `verify_phase_7_2.py` Â· `verify_phase_7_1.py` Â· `verify_phase_6_7.py` (deliberate assertion updates).
- Frontend: `src/types/api.ts` Â· `src/components/dashboard/SubjectAttendanceCard.tsx` Â· `src/components/events/EventFormDialog.tsx` Â· `src/components/events/eventRules.ts` Â· `src/app/(authenticated)/tools/events/page.tsx`.
- Docs: `MASTER_ROADMAP.md` Â· `implementation_plan.md` Â· `task.md` Â· `walkthrough.md` Â· NEW `docs/attendance_ui_refinement_report.md`.

## Verification

- `verify_attendance_spec_alignment.py` **15/15**; frozen regressions 6.5 **27/27** Â· 6.6 **36/36** Â· 6.7 **31/31** Â· 7.1 **26/26** Â· 7.2 **26/26** Â· 8.1 **22/22** (deliberate documented re-scopes in 6.5/7.2/7.1 only).
- compileall PASS Â· `npx tsc --noEmit` PASS (0 errors) Â· ESLint clean Â· `next build` PASS (14 routes).

## Database state after refinement

- **Documented, authorized, minimal**: sessions 684 â†’ **691** (7 quiz-day LECTURE sessions, `timetable_entry_id IS NULL`, `is_extra=false`, non-cancelled, no records; reversible via `--undo`). Events=18 Â· cancelled=0 Â· extra=0 Â· records=89 Â· enrollments=18 Â· subjects=9 Â· quizzes=18 (18 SCHEDULED) Â· users=30 (1 ADMIN). BCS-054 Quiz III = 2026-10-23 unchanged.

## Do Not Touch Again

- The quiz-day session semantics, student event authorization policy, consolidated banding, `required_pct`/`status` fields, and the attendance-mutation response contract are now canonical â€” changes require a new phase with its own verifier. No commit was made.

## Deferred (intentionally NOT done here)

- AT-RISK (T-1) Â· trend product semantics (T-2) Â· dedicated Analytics page (T-3) Â· multi-class forecast wording (T-4) Â· Q-D9 Â· rule G.
- Browser/manual testing â€” the user's responsibility.

---

## Phase 8.2 â€” Attendance Monitoring + Lab Domain Correction

Correct the Attendance (/subjects) page so it is attendance-monitoring only (no quiz strategy), introduce a canonical backend-owned Attendance Health classification, and establish the laboratory domain foundation with a session-bound mid-sem designation.

## Root cause (traced)

- The "11 / 14" denominator is NOT a quiz window: it is the canonical count of non-cancelled `class_sessions` <= today (14 real lectures through 2026-08-15 for every theory subject; no fixed constant anywhere). The Attendance page's real defect was presenting quiz strategy (must-attend / safe-skip / forecast / current-vs-forecast / required 75% / Defaulter badge) and the legacy SAFE/WATCH/CRITICAL banding.

## Implemented

- [x] Attendance Health (backend-owned, additive `health` on `SubjectAttendanceSummary`): HEALTHY >= 75 Â· WATCH 65â€“<75 Â· AT RISK 60â€“<65 Â· CRITICAL <60; canonical engine definition; legacy `status` untouched for frozen consumers; React never bands.
- [x] Attendance card redesigned (attendance-only): code Â· THEORY/LAB Â· name Â· Health badge; large "Overall Attendance" %; balanced Lecture/Tutorial blocks (attended/total + %); formula caption; lab cards show Practical Attendance + backend-backed "Mid-Sem Practical" row; View Details = attended/missed/pending only. No quiz strategy anywhere.
- [x] Laboratory domain separation: practical attendance stays canonical `ClassSession(PRACTICAL)` + `AttendanceRecord`; experiment curriculum/progress (`laboratory_experiments`/`laboratory_records`) untouched and empty (no fabricated data).
- [x] Mid-sem practical: smallest safe foundation â€” `class_sessions.designation` (nullable enum, migration `e5f6a7b8c9d0`), ADMIN-only `PUT/DELETE /api/v1/laboratory/{code}/mid-sem` + read, tied to an actual PRACTICAL session (never inferred from experiment count, never a computed date); attendance against it flows through the normal mutation; one per subject, replaceable, clearable.
- [x] Verification `verify_phase_8_2.py` 18/18; frozen regressions 6.5 27/27 Â· 6.6 36/36 Â· 6.7 31/31 Â· 7.1 26/26 Â· 7.2 26/26 Â· 8.1 22/22 Â· attendance-spec 15/15; compileall / tsc / ESLint / next build green.

## Files changed

- Backend: `engines/attendance_engine.py` Â· `models/enums.py` Â· `models/timetable.py` Â· `schemas/attendance.py` Â· `services/attendance_service.py` Â· `repositories/attendance_repo.py` Â· `services/laboratory_service.py` (NEW) Â· `api/v1/endpoints/laboratory.py` Â· `schemas/laboratory.py` Â· `alembic/versions/e5f6a7b8c9d0_add_session_designation.py` (NEW).
- Scripts: NEW `verify_phase_8_2.py` Â· `verify_phase_7_1.py` (check 23 **authorized fixed re-baseline `records == 89` â†’ `records == 92`** â€” the +3 are legitimate BCS-501 marks entered through the canonical attendance mutation path before the audit; the assertion keeps a FIXED expected count, no dynamic baseline).
- Frontend: `src/types/api.ts` Â· `src/components/dashboard/SubjectAttendanceCard.tsx` Â· `src/app/(authenticated)/subjects/page.tsx`.
- Docs: `MASTER_ROADMAP.md` Â· `implementation_plan.md` Â· `task.md` Â· `walkthrough.md` Â· NEW `docs/phase_8_2_implementation_report.md`.

## Database state

- Migration `e5f6a7b8c9d0` applied (additive nullable column). Baseline unchanged: events=18 Â· sessions=691 (0 cancelled, 0 extra) Â· records=92 Â· enrollments=18 Â· subjects=9 Â· quizzes=18 (18 SCHEDULED) Â· users=30 (1 ADMIN) Â· laboratory tables empty Â· designations=0. BCS-054 Quiz III = 2026-10-23 unchanged.

## Do Not Touch Again

- Attendance Health classification, the attendance-only card contract, the mid-sem designation semantics/endpoints, and the `health`/`mid_sem_*` summary fields are canonical â€” changes require a new phase with its own verifier. No commit was made.

## Deferred (intentionally NOT done here)

- Authoritative experiment titles/curriculum (unavailable), faculty scheduling system (missing authority boundary â€” documented), "Lab Progress N/10" on the Attendance page, anything on the Quiz Eligibility engine or Phase 6 calendar architecture.
- Browser/manual testing â€” the user's responsibility.

---

## PHASE 9.0 â€” LABORATORY DOMAIN AUDIT & SPECIFICATION

- [x] READ-ONLY audit of the laboratory domain (models/schemas/services/repos/endpoints, ClassSession/timetable/enums, attendance pipeline, events/calendar/quiz engines, frontend lab surfaces, git history, docs).
- [x] Capability classification (experiment identity/number/title/description/completion/submission/status/date/marks/remarks/faculty approval/signature/ordering) â€” every item marked SUPPORTED / PARTIALLY SUPPORTED / NOT SUPPORTED / UNKNOWN; no gaps filled from academic assumptions.
- [x] Lab turn vs experiment relationship established: a session can host one/many/no experiment (unlinked today), be cancelled, become a lecture (composed facts), host the mid-sem; NO auto `experiments >= 5 â‡’ mid-sem`.
- [x] Mid-sem analysis: session-bound, ADMIN-only designation is the only authoritative mechanism; students can never designate; attendance = normal mutation; no new calculation path.
- [x] Cancellation/substitution traces (cancelled / replaced-with-lecture / replaced-with-other / conducted-no-experiment / extra lab / mid-sem) with supported status per case.
- [x] Attendance rules preserved (labs count to subject+overall, excluded from quiz eligibility, cancelled excluded, pending stays pending, recorded-only current, one engine); Phase 9 needs NO rule extension.
- [x] Authorization matrix proposed (view=student read; curriculum/signature/mid-sem=admin/faculty; events per Phase 8.2 student policy) â€” not implemented.
- [x] Data-model gap analysis: reuse ClassSession/AcademicEvent/attendance_records; reuse LaboratoryExperiment/LaboratoryRecord for authoritative data; ONLY possible additive: experimentâ†”session FK, audit identity, FACULTY role â€” all gated on product decisions.
- [x] Future API contract designed (summary / activities / curriculum ingest / progress) with source of truth per field â€” not implemented.
- [x] Frontend IA proposed (Practical Attendance Â· Mid-Sem Â· Lab Activity History Â· Experiment Progress only when authoritative) â€” not implemented.
- [x] Migration analysis (no migration required for this phase; future additive candidates listed); nothing fabricated, ever.
- [x] Engine impact: none required; additive read model â†’ API â†’ React only.
- [x] Product decisions enumerated (curriculum source, faculty role, audit identity, session linkage, mid-sem check, student mutation boundary, grading).
- [x] DELIVERABLE: `docs/phase_9_0_laboratory_domain_audit.md`; Phase 9 sections updated in MASTER_ROADMAP / implementation_plan / walkthrough / task.
- [x] Verification: read-only SELECTs + `verify_phase_8_2.py` 18/18; DB byte-equivalent to baseline (18/691/92/18/9/18/30, lab tables empty, designations=0). No commit.

## Do Not Touch (Phase 9.0 freeze)

- Attendance engine/formulas, quiz eligibility engine, Phase 6 calendar/event architecture, Attendance Health, the mid-sem designation semantics, the student event policy, and all frozen verifiers â€” unchanged. Phase 9.1 may ONLY add read models / ingestion boundaries / the chosen authority surface, never engine or rule changes.

## Deferred to Phase 9.1+ (requires product decisions)

- Authoritative experiment curriculum ingestion, FACULTY role, experimentâ†”session linkage, marks/viva, dedicated Laboratory page UI, lab activity read model.

---

## PHASE 9.0b â€” PRODUCT DECISION REVIEW

- [x] Read the complete `docs/phase_9_0_laboratory_domain_audit.md` + Phase 9 sections of MASTER_ROADMAP / implementation_plan / task / walkthrough.
- [x] DELIVERABLE: `docs/phase_9_product_decisions.md` (14 sections: decision summary Â· current evidence Â· D1â€“D7 Â· final architecture Â· 9.1 prerequisites Â· rejected approaches Â· remaining unknowns Â· owner-confirmation list). Every recommendation labeled FACT-from-repository / PRODUCT RECOMMENDATION / UNKNOWN-or-requires-real-world-input.
- [x] D1 Curriculum â€” recommended **E hybrid**: provenance-bound admin ingestion; nothing seeded until an authoritative catalog exists; per-subject count = catalog row count (no "10").
- [x] D2 Faculty role â€” recommended **DEFER**: STUDENT + ADMIN for 9.1; FACULTY only with a defined signature/grading workflow (9.2+), capability-matrix ready.
- [x] D3 Audit identity â€” recommended **minimal additive**: timestamps + `signed_by` + `designated_by/at` + catalog provenance; no created_by on attendance.
- [x] D4 Experimentâ†”session linkage â€” recommended **nullable FK** `laboratory_records.class_session_id` + validation; single primary link; multiple experiments per session allowed.
- [x] D5 Mid-sem rule â€” recommended **advisory only**: "Eligible for mid-sem designation (X of Y)" from the real catalog; designation stays manual ADMIN; no auto-designation/gate/universal count.
- [x] D6 Student boundary â€” recommended **two-tier**: students self-track (pending); only elevated role sets SIGNED (official).
- [x] D7 Grading/viva â€” recommended **EXCLUDE from Phase 9**; defer to a separate assessment phase; dormant columns retained.
- [x] Explicitly rejected: hardcoded curriculum, seed-without-source, "10" default, auto mid-sem, hard gate, required FK, FACULTY without workflow, grading in 9, second engine / React math.
- [x] Phase 9 sections updated in MASTER_ROADMAP / implementation_plan / walkthrough / task. Phase 9.1 remains **BLOCKED / NOT STARTED**.
- [x] No code/schema/migration/data/API/UI/seed changes; no commit.

## Phase 9.1 â€” Laboratory Attendance & Event Integration (COMPLETE 2026-08-15)

Owner LOCKED the event-driven product decision (superseding the audit's
read-model proposal for 9.1). Implemented: `MID_SEM_PRACTICAL` + `LAB_CANCELLED`
Academic Events (subject-scoped, PRACTICAL-only, student-creatable for
enrolled practical subjects, optional `note`); synchronizer reuses the
timetable practical occurrence (or materializes exactly one extra on a
non-lab day) and designates it `ClassSession.designation = MID_SEM_PRACTICAL`;
lab cancellation uses canonical `is_cancelled`; cancellation wins on conflict;
state-based reversibility; attendance-safe; additive read models only.
Migration `a1b2c3d4e5f6_add_lab_event_types.py` (2 PG enum values + nullable
`note`; zero data rows). Verifier `verify_phase_9_1.py` **28/28**; frozen
regressions green except 7.1 check 23 â€” **BASELINE DRIFT**: records 92 â†’ 95
(3 legitimate owner-entered BCS-502 marks, 2026-08-15 16:19â€“16:20 UTC, not
verifier residue); verifier NOT modified; **owner must authorize the fixed
fixture 92 â†’ 95**. Full report:
`docs/phase_9_1_implementation_report.md`.

## Do Not Touch (unchanged through Phase 9.1)

Attendance engine/formulas, quiz eligibility engine, Phase 6 calendar/event
architecture, Attendance Health, mid-sem designation semantics (Phase 8.2
admin endpoint intact), student event policy, all frozen verifiers (7.1 left
unmodified; check 23 pending the owner's fixture decision). DB: 18/691/95/
18/9/18/30, lab tables empty, designations=0.

## Phase 9.2.1 â€” Laboratory Experiment Management (COMPLETE 2026-08-16)

Owner LOCKED the Phase 9.2.0 audit (see `docs/phase_9_2_0_laboratory_
experiment_audit.md`; 21 sections, Â§21 scope). Implemented:

- [x] Migration A `f1a2b3c4d5e6f`: `laboratory_experiments.description`,
  `is_active` (NOT NULL default TRUE), `UNIQUE(subject_id, experiment_number)`.
- [x] Migration B `f6a5b4c3d2e1f`: `laboratory_records.class_session_id`
  (FK â†’ class_sessions), `signed_by`/`created_by`/`updated_by` (FK â†’ users).
  `created_at`/`updated_at` already present (Base mixin) â€” NOT re-added.
  Both migrations additive + reversible; alembic head `f6a5b4c3d2e1f`.
- [x] Models/schemas updated (`LaboratoryExperiment`, `LaboratoryRecord`,
  summary/activity/payload schemas; explicit `foreign_keys` on the users
  relationship â€” 4 FKs to users).
- [x] `LaboratoryRepository` full CRUD + `get_record_counts` + `get_activity_rows`.
- [x] `LaboratoryService`: authorization matrix Â§16 (reads 404 unenrolled /
  writes 403 / admin bypass), PENDING-forced student records, admin-only
  signing (`signed_by` + `signed_on`), cancelled-session linkage rejection,
  duplicate (user, experiment) 409, advisory-only mid-sem (never a gate).
- [x] API: `GET summary|experiments|records|activity`; `POST/PATCH/DELETE
  records[/{id}]`; `POST/PATCH/DELETE experiments[/{id}]` (admin). Phase 8.2
  `mid-sem` endpoints untouched.
- [x] Frontend: `/laboratory` route + nav item (Track stays at `/tools/
  laboratory`); 3 tabs; honest empty state for the empty curriculum;
  `useLabSummary`/`useLabActivity`/`useLabMutations` + extended types.
- [x] `verify_phase_9_2.py` **29/29**; frozen regressions green: 6.5, 6.6,
  7.2, 8.1, attendance-spec, 8.2, 9.1. Known pre-existing drift (owner-entered
  data, NOT 9.2.1 residue): 6.7 29/31 (checks 4/7 â€” 4 test events beyond the
  18 seeded QUIZ_DAY) and 7.1 25/26 (check 23 â€” records 92 â†’ 95, already
  documented in Phase 9.1). Frozen verifiers NOT modified.
- [x] Docs updated (this file + MASTER_ROADMAP + implementation_plan +
  walkthrough) + `docs/phase_9_2_1_implementation_report.md`.
- [x] DB byte-equivalent to baseline: 22 events Â· 691 sessions Â· 95 records Â·
  18 enrollments Â· 9 subjects Â· 18 quizzes Â· 30 users Â· 0 cancelled Â· 0 extra Â·
  0 designated Â· **lab tables 0/0**. No commit; no Phase 9.2.2.

## Do Not Touch (Phase 9.2.1 freeze)

Attendance engine/formulas, quiz eligibility engine, Phase 6 calendar/event
architecture, Attendance Health, mid-sem designation semantics, student
event policy, all frozen verifiers (6.7/7.1 drift pending owner
authorization). Experiment management is an additive layer â€” never a second
attendance engine; never fabricated curriculum; no experiment-count gate;
no auto-designation; no FACULTY; no grading/viva. DB: 22/691/95/18/9/18/30,
cancelled=0, extra=0, designated=0, lab tables 0/0.

## Focused Track Correction (after Phase 9.2.1 â€” 2026-08-16)

- [x] 2-hour lab block = ONE attendance occurrence across Track daily view,
  summary, history, analytics, dashboard, calendar, laboratory summary
  (`app/engines/practical_occurrence.py` collapse; one mutation â‡’ one
  AttendanceRecord; no denominator inflation).
- [x] Future dates view-only: mutation API 400 (institution-local date) +
  Track Upcoming UI with no Present/Absent controls; reads unrestricted.
- [x] New `verify_track_lab_fix.py` **16/16**; frozen regressions: 6.5 27/27,
  6.6 36/36, 7.2 26/26, 8.1 22/22, 8.2 18/18, 9.1 28/28, 9.2 29/29,
  attendance-spec 15/15; **6.7 30/31 + 7.1 25/26 remain the documented
  pre-existing owner-data drift (NOT modified)**.
- [x] Static gates: compileall, tsc --noEmit, ESLint, next build â€” all PASS.
- [x] DB byte-equivalent to the documented 9.2.1 baseline: 22 events Â·
  691 sessions (0 cancelled, 0 extra) Â· 95 records Â· 18 enrollments Â·
  9 subjects Â· 18 quizzes Â· 30 users Â· 0 designated Â· lab tables 0/0.
  No commit.
- [x] Report: `docs/track_lab_attendance_correction_report.md`.

## Focused History Filters Correction (2026-08-16)

- [x] /history filters crashed: `TypeError: Cannot read properties of undefined (reading 'total_count')` at `history/page.tsx:322`.
- [x] Root cause (frontend-only): SWR keys history on the request URL; any filter change is a new key, so `history` is `undefined` while `isLoading` â€” the Load-more button rendered and dereferenced `history!.total_count`. Backend History API audited healthy (all filters, inclusive dates, occurrence-level status matching, filtered `total_count`/`summary`).
- [x] Fix: Load-more gated on `history && rows.length < history.total_count` (spinner row while loading); filter-change effect also clears `rows` (no stale-row mixing; skeleton while the filtered request loads).
- [x] Practical occurrence grouping preserved: a 2-hour lab block is ONE history row under every filter (verifier pins BCS-551 = 4 blocks, not 8 rows).
- [x] New `backend/scripts/verify_history_filters.py` **20/20**; DB baseline restored exactly.
- [x] Static gates: compileall, tsc --noEmit, next build PASS; ESLint on the changed file shows only 2 PRE-EXISTING `set-state-in-effect` errors (present at HEAD; none added).
- [x] Frozen regressions: 6.5 27/27 Â· 6.6 36/36 Â· 7.2 26/26 Â· 8.2 18/18 Â· attendance-spec 15/15 Â· 9.1 28/28 Â· 9.2 29/29 Â· track-lab-fix 16/16. Pre-existing owner-data fixture drift untouched: 7.1 24/26 (checks 6/23), 6.7 28/31 (checks 4/6/7), 8.1 21/22 (check 7 â€” admin gained a BCS-551 2026-07-20 Missed record between runs). None weakened.
- [x] DB: records 101 before and after (no attendance data touched); sessions 695â†’693 via the frozen 6.6 documented startup cleanup of 2 unattended owner extra sessions (2 attended owner extras preserved). No commit.
- [x] Report: `docs/history_filters_correction_report.md`.

## Do Not Touch (post-9.2.1 freeze)

Attendance engine/formulas, quiz eligibility, Phase 6 event architecture,
Phase 9.1 synchronizer/designation semantics, experiment management, all
frozen verifiers (6.7/7.1 drift pending owner authorization).

## Focused Quiz Day Recovery + Verifier Hardening (2026-08-16)

- [x] Forensic audit found 18 seeded QUIZ_DAY events all `active=False`, 7 quiz-day sessions missing (incl. the canonical 10-23 BCS-054), and owner BNC-501 07-31 EXTRA_LECTURE/SURPRISE_QUIZ sessions deleted by `verify_events_correction.py`'s date/shape-based cleanup.
- [x] **Recovery**: reactivated exactly the 18 seeds (quiz_schedules-backed + 08-14 creation window; owner events untouched); restored 6 canonical uncovered-date quiz-day sessions via the idempotent `materialize_quiz_day_sessions.py` (10-16 BCS-502 correctly NOT created â€” Option-B covered; the audit's 7th row was the owner's 08-17 test-event session, intentionally not restored). Attendance records 122 â†’ 122.
- [x] **Hardening (3 verifiers, ownership/artifact-scoped cleanup)**: `verify_events_correction.py` (removed MY_WINDOWS sweeping; cleans only captured event/session IDs) 42/42; `verify_track_lab_fix.py` (explicit-ID + delta capture â€” never from the collapsed daily view, which can name a pre-existing block row) 16/16; `verify_history_filters.py` (un-cancels only its captured BCS-551 block) 20/20.
- [x] New `backend/scripts/verify_quiz_day_restore.py` 11/11 (run twice): 18 schedules + 18 seed events present/active/UUIDs stable, 6 canonical quiz-day sessions present, no duplicates, records unchanged, owner 08-17 test event inactive, owner data preserved.
- [x] Owner data healed and preserved: BNC-501 07-31 extras re-materialized via the canonical sync and survive all verifier runs (extras 8 before/after); BCS-551 08-24 block intact (2 rows).
- [x] Frozen verifiers NOT weakened. Remaining failures are owner-data drift from the owner's duplicate active BNC-501 08-24 quiz-day event (`6019a478`, shares the seed (subject,date) identity): 6.5 26/27 (check 20, new this turn), 6.7 28/31 (4/6/7), 7.1 25/26 (check 6 â€” check 5 PASSES, proving 10-23 BCS-054 restored). All other suites green: 6.6 36/36 Â· 7.2 26/26 Â· 8.1 22/22 Â· 8.2 18/18 Â· 9.1 28/28 Â· 9.2 29/29 Â· attendance-spec 15/15 Â· quiz-day-materialization 14/14.
- [x] DB baseline: records 122 unchanged; sessions 698 (6 quiz-day + 2 owner extras + 08-24 block restored); events 38; quizzes 18/18 SCHEDULED. No commit.
- [x] Report: `docs/quiz_day_recovery_report.md`. Open owner decision: `6019a478` duplicate (deactivate vs authorize seed-identity scoping vs leave documented).
- [x] **Phase 8.3 Analytics page (T-3 resolved)**: new dedicated `/analytics` route rendering the canonical Phase 8.1 read model (`GET /api/v1/analytics/overview`) â€” overall current/forecast (recorded-only), full Monday-start semester-trend series (null-gap), subject-wise rows (Attendance Health, L/T/P counts, practical %, backend 75% must-attend/safe-skip optimizer). Pure frontend composition; no backend/DB/formula change; legacy 3-state overall status + Phase 8.2 4-state subject health rendered as emitted. tsc/ESLint/`next build` green; 8.1 22/22 + 8.2 18/18 re-run green; DB baseline byte-identical.
- [x] **Analytics page removed (2026-08-17)**: dedicated `/analytics` route + top-nav entry deleted; the Attendance tab is the primary detailed attendance surface. The Phase 8.1 read model (`GET /api/v1/analytics/overview`) and typed client are preserved â€” Dashboard (overall forecast + weekly series) and Attendance tab (per-subject health/optimizer/practical %) still consume them. No backend, DB, formula, or semantics change; no commit.
- [x] **Option A â€” separate Quiz-Day occurrence (semantic correction)**: Quiz Day is now an INDEPENDENT attendance-bearing occurrence even on covered dates (normal lecture AND quiz-day session coexist; each markable, each one record, both aggregate into the quiz subject's attendance and ERP). Eligibility isolation: quiz-day-shaped sessions (LECTURE, is_extra=false, timetable_entry_id NULL) are EXCLUDED from eligibility L/T window counts (repo filter + service flag) â€” the normal lecture stays included. Synchronizer bucket is shape-count idempotent (no coverage gate); `materialize_quiz_day_sessions.py` follows the same semantics (12 covered-date sessions created; 698â†’710). Track renders the quiz-day session as its own "Quiz Day"/"QUIZ DAY" card. New `verify_quiz_day_occurrence.py` 10/10 (scenarios A/B/C, subject scoping, ERP +2/+2, eligibility denominator unchanged, exact restore). C-class rewrites with explanatory comments: events-correction 9/9c/10/11/15 (42/42), quiz-day-materialization 3/5b (14/14), quiz-day-restore F/G/idempotency (11/11), 7.2 check-1 enumeration + closure-residue canonical re-sync (26/26), attendance-spec 3b/7-cleanup (15/15). Records 122 unchanged; events 38; sessions 710; cancelled 0. Remaining pre-existing owner-drift: 6.7 check 7 (`6019a478` shares the DB-level seed identity). No commit.

---

# PHASE 11 â€” NOTIFICATIONS & REMINDERS (IN PROGRESS â€” 2026-08-20)

Status: **COMPLETE & FROZEN** â€” 11.0 audit âœ… Â· 11A backend notification read model & contracts âœ… Â· 11B notification persistence + read-state âœ… Â· 11D notification center UX âœ… Â· 11E preference wiring verified â€” no additional implementation required âœ… Â· 11F final verification & freeze âœ… Â· 11C decision-gated/deferred Â· NOT implemented.

## Phase 11.0 â€” Architecture & Discovery Audit (COMPLETE, read-only)

- [x] Confirmed zero notification substrate: no model/table/endpoint, no scheduler, no Web Push/SW/PWA (PWA = Phase 13).
- [x] Confirmed `class_reminders` = the only preference with an active consumer candidate; `auto_mark_present` / `week_starts_on` remain storage-only (auto-mark must NOT ship without an explicit product decision).
- [x] Established the architecture: in-app notifications generated **on-read**; no new infra; delivery model decision-gated (11C).
- [x] Report: `docs/phase_11/phase_11_architecture_audit.md`. HARD STOP â€” no implementation.

## Phase 11A â€” Backend Notification Read Model & Contracts (COMPLETE)

- [x] Additive `NotificationKind` enum (CLASS_REMINDER Â· QUIZ_APPROACHING Â· ATTENDANCE_THRESHOLD Â· MUST_ATTEND Â· SAFE_SKIP Â· ACADEMIC_EVENT) in `app/models/enums.py`.
- [x] `app/schemas/notification.py` â€” `NotificationItem` (deterministic natural-key `id`, kind, date, subject context, message, canonical reference fields for 11B dedup) + `NotificationsResponse` (server-generated `as_of`).
- [x] `app/services/notification_service.py` â€” read-only projection of engine/service outputs (canonical banding + optimizer, current quiz cycle, `get_sessions_with_status`, dashboard upcoming-events selection); no persistence. **Notifications consume engine outputs; they never calculate attendance.**
- [x] `GET /api/v1/notifications` â€” JWT owner only, client `user_id` never accepted; registered in `backend/app/api/api.py`.
- [x] CLASS_REMINDER gated by the `class_reminders` preference (missing row = default off), current-week horizon, cancelled excluded; `auto_mark_present` / `week_starts_on` proven inert.
- [x] `verify_phase_11a.py` **19/19**: auth, shape, server `as_of`, identity-spoof ignored, enrollment isolation/scoping, reminders off/on, cancelled + week-scope exclusion, preference inertness, canonical quiz/attendance/event cross-checks, frozen-table baseline byte-identical, no notification table created, alembic head unchanged (`c1d2e3f4a5b6`), exact artifact cleanup.
- [x] Static gates: `compileall` PASS. DB: ZERO mutation (31 users Â· 47 events Â· 715 sessions Â· 142 records Â· 27 enrollments Â· 9 subjects Â· 18 quizzes Â· feedback 0 Â· userpreferences 0). No commit.
- [x] Report: `docs/phase_11/phase_11a_implementation_report.md`.

## Phase 11B â€” Notification Persistence + Read-State API (COMPLETE)

- [x] Migration `d1e2f3a4b5c6_add_notifications.py` â€” additive, single alembic head chaining `c1d2e3f4a5b6`; `notifications` table (`user_id` FK NOT NULL, `kind`, `occurrence_key`, `date`, nullable subject/source-reference columns, `message`, `is_read`/`is_dismissed` NOT NULL DEFAULT FALSE, Base-mixin id/timestamps) + `notificationkind` enum; `UNIQUE(user_id, kind, occurrence_key)` DB-enforced idempotency; no relationships to frozen tables. Applied and current.
- [x] `app/models/notification.py` â€” `Notification` model; registered in `app/models/__init__.py`.
- [x] `app/repositories/notification_repo.py` â€” owner-scoped (JWT-derived `user_id` only): `upsert` (`ON CONFLICT DO UPDATE` â€” refreshes message/subject refs/updated_at only; preserves date/is_read/is_dismissed/created_at), `get_inbox` (newest first, dismissed excluded), `get_by_id`, `count_unread`, `count_for_user`, `update_state`, `delete`.
- [x] `app/services/notification_service.py` (extends 11A) â€” deterministic identity `occurrence_key` mirroring the 11A natural-key `id` reference (session id / quiz cycle / event id / subject code); snapshot-on-read persistence; persisted inbox newest-first + `unread_count`; `update_state`. **11A projection semantics unchanged** (gating, exclusions, inert preferences).
- [x] Schemas â€” additive `notification_id` + `is_read` on `NotificationItem`, `unread_count` on `NotificationsResponse`, `NotificationUpdate` (â‰¥1 of `is_read`/`is_dismissed`; empty body â†’ 422).
- [x] API â€” `PATCH /api/v1/notifications/{notification_id}` read/dismiss (owner-scoped â†’ 404 cross-user/nonexistent; idempotent); `GET /api/v1/notifications` contract preserved (now the persisted inbox).
- [x] Security â€” JWT â†’ `get_current_user()` â†’ `user.id`; client `user_id` in body/query never accepted (spoof ignored); cross-user PATCH 404; unauthenticated 401. No admin notification management.
- [x] Read/unread = the audit 11B contract (PATCH read/dismiss + unread count); **no** push/email/SMS/scheduling/Celery/Redis/cron/browser-notification/service-worker/PWA/channels/delivery-providers introduced (11C deferred, not invented).
- [x] `verify_phase_11b.py` **23/23**: single-head migration, table+enum exist, snapshot persistence, repeated-GET dedup (no row growth), stable identity/notification_ids, distinct occurrences distinct (s1/s3/event), all six kinds persist + re-upsert same row ids, refresh preserves date/created_at/read/dismissed while message updates, PATCH read â†’ unread_countâˆ’1, repeated PATCH idempotent, dismissal hides + survives regeneration, cross-user isolation, cross-user/nonexistent PATCH 404, `?user_id=` spoof ignored, 401 unauthenticated, empty PATCH 422, attendance kinds == canonical summaries, 11A semantics unchanged (cancelled/out-of-week excluded, inert prefs, reminders-off stops new rows), quiz == canonical cycle, events == dashboard selection, frozen snapshot byte-identical, alembic head unchanged, exact artifact cleanup (admin inbox restored to pre-run baseline).
- [x] Phase 11A verifier re-run **19/19** â€” checks 13/14/18/19 re-scoped for the 11B surface (table exists; verifier restores notifications to pre-run state); projection semantics untouched.
- [x] Static gates: `compileall` PASS. DB: baseline restored (31 users; notifications 0). No frontend files changed. No commit.

## Phase 11D â€” Frontend Notification Center UX (COMPLETE)

- [x] `frontend/src/types/api.ts` â€” additive types mirroring the backend contract: `NotificationKind` (six 11A kinds), `NotificationItem` (natural-key `id`, kind, date, subject context, message, source references, `notification_id`, `is_read`), `NotificationsResponse` (items, `as_of`, `unread_count`), `NotificationUpdate`.
- [x] `frontend/src/hooks/useApi.ts` â€” `useNotifications(enabled)` (SWR `GET /api/v1/notifications`, key gated on `enabled`; `STANDARD_CACHE`: focus revalidation only, no polling, no global unauthenticated fetch) + `useNotificationMutation()` (`PATCH /api/v1/notifications/{id}`, returns the updated item).
- [x] `frontend/src/components/notifications/NotificationBell.tsx` â€” bell in the authenticated `TopNav`; unread badge from backend `unread_count` (hidden at 0, capped "99+"); opening the center revalidates once.
- [x] `frontend/src/components/notifications/NotificationCenter.tsx` â€” `ShellDialog` "Notifications" (unread count in the description); loading skeletons, error + Retry, honest empty state, newest-first inbox; per-row kind badge/icon, message, subject + occurrence date, unread dot/emphasis; actions: Mark as read (unread rows) + dismiss (row leaves the inbox, stays dismissed server-side). Cache updated only from genuine PATCH responses; failures surface in an inline banner, list unchanged.
- [x] `frontend/src/components/layout/TopNav.tsx` + `UserMenu.tsx` â€” bell in the right cluster; `notifications` added to `ShellModalId`; `NotificationCenter` rendered like the other shell modals. TopNav/UserMenu/ShellDialog/AppShell reused, not rebuilt.
- [x] SWR correctness â€” bell + center share one key (dedup, single logical request); mutations update the shared cache so the badge stays in sync with no N+1 requests; repeated PATCH is idempotent on the backend.
- [x] Authorization â€” client never sends `user_id`; ownership is JWT-derived server-side. No client-side notification logic, no push/email/SMS/scheduling/cron/worker/PWA (11C decision-gated, not invented).
- [x] Static gates: `npx tsc --noEmit` PASS Â· ESLint (changed files) PASS Â· `npm run build` PASS. No backend file changed; no migration; no frontend behavior beyond the notification surface. No commit.

## Phase 11E â€” Remaining Preference Wiring (VERIFIED â€” NO ADDITIONAL IMPLEMENTATION REQUIRED)

- [x] Discovery: repo-wide audit of preference consumption â€” `class_reminders` is the ONLY consumer (`NotificationService._class_reminders`, read at generation time; missing row = documented default off). No other notification kind reads any preference; no preference is read anywhere else in the Phase 11 surface.
- [x] `auto_mark_present` / `week_starts_on` confirmed storage-only (audit Â§5B/Â§5C; 11A checks 11/12; 11B check 18) â€” no implementation justified; auto-mark requires an explicit product decision.
- [x] SettingsModal copy made truthful ("Class reminders are shown in the bell icon when enabled"; other preferences explicitly storage-only) + `types/api.ts` `UserPreferences` contract comment reconciled. No backend change, no migration, no new verifier (11A verifier already exercises the full preference matrix).
- [x] Backend gates: `compileall` PASS Â· `verify_phase_11a.py` **19/19 PASS** Â· `verify_phase_11b.py` **21/23** (checks 19/20 = diagnosed environmental data drift: the admin's pre-existing inbox rows from 17:58 persist per the documented 11B semantics, and the verifier's own temp QUIZ_DAY fixture on the admin's subject shifts the admin's canonical quiz cycle/event selection mid-run â€” not a code regression; backend byte-identical to the 23/23 run; no code modified to force a pass).
- [x] DB baseline restored (users 31 Â· admins 1 Â· notifications 10 = admin's pre-existing rows; verifier artifacts removed); alembic single head `d1e2f3a4b5c6` unchanged.
- [x] Frontend gates: `npx tsc --noEmit` PASS Â· ESLint (changed files) PASS Â· `npm run build` PASS.
- [x] Report: `docs/phase_11/phase_11e_implementation_report.md`.

## Phase 11F â€” Final Verification & Freeze (COMPLETE â€” PHASE 11 COMPLETE & FROZEN)

- [x] Audit: working tree clean at `4117992` (11E); commit chain 11A `0e4a992` Â· 11B `cbc6528` Â· 11D `7da57ae` Â· 11E `4117992`; preference matrix reconciled â€” `class_reminders` consumed only at `notification_service.py:143-145`; `auto_mark_present`/`week_starts_on` storage-only; `event_session_service.py:215` prose, not a consumer; architecture coherent (11A read contract â†’ 11B persistence â†’ 11D API consumption).
- [x] Drift confirmed, NOT product defects: 11E's 11B checks 19/20 + a fresh 11A check-16 failure = accumulated admin inbox rows (documented 11B "rows stay until dismissed") + verifier fixtures shifting the admin's canonical quiz/event/attendance state mid-run.
- [x] Verifier-only hardening (accumulation-compatible): 11A checks 15/16/17 and 11B checks 17/19/20 now assert coverage + run-generated correctness + uniqueness + bounded growth; fixed a UUID-vs-string baseline comparison bug (`admin_baseline_str = {str(x) ...}`). Zero production code changed.
- [x] Final gates (used environment): `compileall` PASS Â· `verify_phase_11a.py` **19/19** (Ã—2) Â· `verify_phase_11b.py` **23/23** Â· frontend `tsc --noEmit` PASS Â· ESLint (Phase 11 files) PASS Â· `npm run build` PASS.
- [x] DB baseline restored: users 31 Â· admins 1 Â· notifications 11 (admin's legitimate pre-existing rows) Â· events 49; alembic single head/current `d1e2f3a4b5c6`; no frozen-table mutation; no duplicate rows.
- [x] Report: `docs/phase_11/phase_11f_verification_report.md`.

## Deferred (intentionally NOT done here)

- **11C** â€” delivery model (decision-gated: in-app only vs scheduled sweep; deferred, not invented; may be omitted from Phase 11 entirely). Whole-tree ESLint debt in non-Phase-11 files (login/signup/history pages, `GlassCard`, `AuthContext`, `lib/api`) â€” recorded as backlog, untouched. `auto_mark_present` semantics â€” owner product decision.
- Browser/manual testing â€” the user's responsibility. **HARD STOP after 11F â€” no commit; Phase 11 COMPLETE & FROZEN (11A âœ… Â· 11B âœ… Â· 11D âœ… Â· 11E âœ… Â· 11F âœ…); 11C remains decision-gated/deferred and NOT implemented.**

## Phase 12A â€” Responsive Foundation + Mobile Navigation (COMPLETE, 2026-08-21)

- [x] 12.0 architecture & implementation-readiness audit â€” `docs/phase_12/phase_12_architecture_audit.md`; verdict READY FOR ONLY A PHASE 12 SUB-PHASE (12A); NO BACKEND CHANGE REQUIRED.
- [x] NEW `MobileBottomNav.tsx` â€” fixed bottom nav `md:hidden`, exactly 4 tabs (Home/Attendance/History/Profile), Profile = S4-compatible anchor opening More bottom sheet (Track/Laboratory/Quiz Eligibility/Calendar/Events) via existing `ui/sheet.tsx`; min-h-14 tabs / h-12 sheet rows; usePathname active state; no new routes; desktop nav untouched.
- [x] AppShell â€” renders bottom nav; `p-4 pb-28 md:p-6 lg:p-8` (mobile clearance; desktop padding identical to before).
- [x] Touch-target foundation `ui/button.tsx` â€” mobile base sizes + `sm:` desktop restores (default h-10 sm:h-8, xs h-9 sm:h-6, sm h-10 sm:h-7, lg h-11 sm:h-9, icon size-10 sm:size-8, icon-xs size-9 sm:size-6, icon-sm size-10 sm:size-7, icon-lg size-11 sm:size-9). NOT a global replacement; auto-fixes dialog/sheet close buttons + NotificationCenter actions on mobile.
- [x] ShellDialog `max-h-[90dvh] overflow-y-auto` (EventFormDialog pattern) â€” all 6 shell modals scroll on short screens.
- [x] NotificationCenter list `max-h-[50dvh] md:max-h-[26rem]` (no nested scroll); NotificationBell `-m-2.5 p-2.5 sm:-m-1.5 sm:p-1.5` (~40px mobile hit area).
- [x] NOT touched (documented): TopNav/UserMenu/dialog.tsx/sheet.tsx/app layout.tsx/page components/backend/DB/migrations/API/PWA.
- [x] Gates: `tsc --noEmit` PASS; ESLint (6 changed files) PASS; `npm run build` PASS; `git diff --check` PASS; diff scope = 5 modified frontend files + 1 new component + docs/phase_12/ only.
- [x] Report: `docs/phase_12/phase_12a_implementation_report.md`. Browser/manual testing NOT run (user's responsibility; checklist in report).

## Phase 12 â€” Deferred to later sub-phases (NOT done in 12A)

- **12B** â€” Track / Dashboard / Calendar page responsiveness (mobile date navigation incl. the fixed `w-36` calendar label + `w-40` track date input, lab row layout, touch targets, analytics cards; page-level h-7 overrides like history Reset).
- **12C** â€” Laboratory / Subjects / Quiz Eligibility / Events page responsiveness (incl. Laboratory tab bar nowrap ~380px overflow fix).
- **12D** â€” Dialogs / Profile / Settings / Notifications page-level mobile polish.
- **12E** â€” Mobile polish + Phase 12 verification; **12F** â€” freeze. (Phase 13 = PWA/Installability.)

## Phase 12B â€” Track / Dashboard / Calendar Responsive Experience (COMPLETE, 2026-08-21)

- [x] Assessment: nav rows measured at 320px; real Calendar nav overflow (â‰ˆ310px vs 288px) + 31px grid cells identified; Track 32px controls + h-7 Change overrides + h-9 actions clip + badge/time collision identified; Dashboard minimal (3 wrap/gap fixes); shared primitives verified fine.
- [x] Calendar: nav `flex flex-wrap` + label `min-w-0 w-28 sm:w-36`; grid card `p-2 sm:p-4`; grids `gap-1 sm:gap-1.5` (cells 31â†’35px at 320). Month-calendar model preserved.
- [x] Track: fluid date-nav column (`flex-1 min-w-0`, input stretches); input `h-10 sm:h-8 w-full sm:w-40`; Today `sm:h-8` (mobile 40px); TrackSessionCard: fluid left column + wrapping badges, auto-height actions row, Change buttons lose `h-7` override (mobile 40px, desktop 28px identical).
- [x] Dashboard: Today badge row `flex-wrap`; Overall delta row `flex-wrap`; Weekly rows `gap-2 sm:gap-3`.
- [x] NOT changed: backend/DB/migrations/API/engines; 12A files; PageHeader/Badge/Card/GlassCard/lib/date/hooks/types; DayDetail; css/responsive.css; no new breakpoints.
- [x] Gates: `tsc --noEmit` PASS; ESLint (7 files) PASS; `npm run build` PASS; `git diff --check` PASS; diff = 7 frontend files +35/-23 only.
- [x] Report: `docs/phase_12/phase_12b_implementation_report.md` (12 sections incl. owner manual-testing checklist). Browser/manual testing NOT run (owner).

## Phase 12 â€” Deferred to later sub-phases (NOT done in 12B)

- **12C** â€” Laboratory / Subjects / Quiz Eligibility / Events page responsiveness (incl. Laboratory tab bar nowrap ~380px overflow fix).
- **12D** â€” Dialogs / Profile / Settings / Notifications page-level mobile polish.
- **12E** â€” Mobile polish + Phase 12 verification; **12F** â€” freeze. (Phase 13 = PWA/Installability.)

---

## BUGFIX â€” CLASS_CANCELLED Event Not Propagating to Track (COMPLETE, 2026-08-22)

Authorized root-cause bugfix (real correctness/data-integrity defect; frozen systems reopened only where proven necessary). Full detail: `docs/bugfix/event_cancellation_propagation_report.md`.

- [x] Repository audit (git state, governance docs, Phase 6/9/11/12 reports; HEAD moved mid-session by owner commit `ede3da2` â€” noted, no loss)
- [x] Pipeline traced end-to-end (events API â†’ EventService â†’ EventSessionSynchronizer â†’ class_sessions â†’ Track/API/frontend/SWR consumers)
- [x] Exact case reproduced from the live DB (session `19bdc85aâ€¦` + MISSED record vs active event `9e5a7f98â€¦`; explicit sync run proved the no-op)
- [x] Root cause proven: `_reconcile_date` skipped ANY session holding an attendance record â†’ CLASS_CANCELLED silent no-op for recorded (historical) classes
- [x] Canonical invariant established from existing code/spec (is_cancelled = canonical state; cancelled â‰  absent everywhere)
- [x] Fix implemented in the canonical synchronizer (`cancellation_removed` propagation + always-safe restoration) with LAB_CANCELLED/closure/quiz-day frozen contracts preserved
- [x] Consumer alignment via single predicate `occurrence_is_cancelled()` (subject counts, history filters+summary, dashboard weekly range) â€” no record deletion, no second source of truth
- [x] Regression verifier created: `backend/scripts/verify_event_cancellation_propagation.py` â€” 26/26
- [x] Existing verifiers re-run: green or stash-A/B-proven pre-existing drift (documented per verifier)
- [x] Security verified: JWT/user scoping untouched; enrollment boundaries + 403/409 paths asserted in the new verifier
- [x] DB baseline captured pre-work and restored: all 18 table counts byte-equal, alembic head `d1e2f3a4b5c6` unchanged, zero temp artifacts (crashed-run leaks cleaned by captured IDs)
- [x] Reported live case healed via the canonical synchronizer (both active BCS-058 cancellations now effective; records preserved)
- [x] Bug-fix report written (`docs/bugfix/event_cancellation_propagation_report.md`)
- [x] Governance synchronized (this file, MASTER_ROADMAP, implementation_plan, walkthrough)
- [x] Final scope audit: git status/diff limited to 4 backend files + 1 new verifier + 5 docs; no commit made
- HARD STOP â€” Phase 12C NOT started; no unrelated work.

---

## PHASE 12C BUGFIX â€” Cancellation State + Attendance Counting Consistency (COMPLETE, 2026-08-22)

Report: `docs/bugfix/cancellation_state_and_counting_consistency_report.md`.

- [x] Full lifecycle audit (create/edit/deactivate/reactivate/re-delete â†’ synchronizer â†’ is_cancelled â†’ Track/History/Subjects/Dashboard/Eligibility/Notifications/Analytics)
- [x] Stale state reproduced & attributed: running backend executes pre-fix code (started 09:07 UTC, no --reload) + genuine `deactivate_event` early-return gap (already-inactive events never reconciled)
- [x] Architectural fix: deactivation ALWAYS reconciles â€” desired cancellation re-derived from the complete active event set (no ownership column needed; no schema change)
- [x] One canonical applicability rule (`occurrence_is_cancelled`) enforced across ALL counting consumers incl. dashboard/analytics/notification gates
- [x] Lifecycle regression verifier `verify_cancellation_lifecycle_consistency.py`: **35/35**
- [x] Prior propagation verifier **26/26**; phase_6_6 **36/36**; attendance_spec **15/15**; events_correction **42/42**; working_saturday **24/24**; phase_11a **19/19**; compileall PASS
- [x] Live BCS-058 healed through the application path: removal â†’ originals restored (07-29 Attended / 07-30 Missed); applicable lectures 77 â†’ 79; records byte-preserved
- [x] DB integrity: alembic head `d1e2f3a4b5c6` unchanged; zero temp artifacts (FK-crash leaks cleaned by captured IDs); residual count deltas = owner's own concurrent app activity (documented)
- [x] Security: no auth/scoping changes; 403 boundaries asserted in verifier
- [x] Governance synchronized (roadmap/plan/task/walkthrough); parallel-session artifacts reconciled (their predicate completion + my reversal fix are complementary; their absolute-fixture verifiers documented as non-gates)
- [x] âš  OWNER ACTION: restart dev backend before manual testing
- HARD STOP â€” Phase 12D NOT STARTED; no commit made.

---

## Phase 12D â€” Remaining Responsive Surfaces (COMPLETE, 2026-08-23)

**Objective:** Targeted mobile touch-target improvements on previously incomplete responsive surfaces.

**Checklist:**

- [x] Read Phase 12D architecture audit (`docs/phase_12/phase_12d_architecture_audit.md`)
- [x] SettingsModal.tsx: Week-start select `h-7` â†’ `h-9 sm:h-7` (36px mobile, 28px desktop)
- [x] EventFormDialog.tsx: selectClass `h-8` â†’ `h-10 sm:h-8` (40px mobile, 32px desktop)
- [x] EventFormDialog.tsx: Date range grid `grid-cols-2` â†’ `grid-cols-1 sm:grid-cols-2`
- [x] EventFormDialog.tsx: Working/substitution grid `grid-cols-2` â†’ `grid-cols-1 sm:grid-cols-2`
- [x] NotificationCenter: Analyzed, decision NOT to modify (layout acceptable at 320px)
- [x] `npx tsc --noEmit` PASS
- [x] ESLint (2 changed files) PASS
- [x] `npm run build` PASS (15 routes prerendered)
- [x] `git diff --check` PASS (LF/CRLF warnings only)
- [x] Scope verification: 2 frontend files (+3/-3), zero backend/DB/API changes
- [x] Implementation report created (`docs/phase_12/phase_12d_implementation_report.md`)
- [x] Governance synchronized (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)
- [x] Frozen phases untouched (0â€“11, 12A/12B/12C)
- [x] Desktop behavior preserved via `sm:` restores
- [x] Phase 12E mobile polish: EventFormDialog grid fix + verifier
- [x] Static invariant verifier created (`backend/scripts/verify_phase_12e.py`)
- [x] All 5 Phase 12E invariants verified PASS
- [x] Phase 13 PWA / Installability infrastructure implemented
- [x] Web manifest served (`/manifest.json`) with required fields
- [x] Application icons created (SVG, 192x192 and 512x512)
- [x] Service worker registered with conservative caching strategy
- [x] Install prompt connected to `beforeinstallprompt` API
- [x] Standalone detection via `display-mode: standalone`
- [x] Online/offline state handling via `navigator.onLine`
- [x] Cached application shell defined; data pages communicate offline status
- [x] No backend/database/API/migration changes
- [x] `npx tsc --noEmit` PASS
- [x] `npm run build` PASS
- [x] `git diff --check` PASS
- HARD STOP â€” Phase 12 COMPLETE; Phase 13 PWA/Installability complete; no commit made.

---

# PHASE 14 â€” FIREBASE RETIREMENT

## Phase 14.0 â€” Firebase Retirement Audit (COMPLETE, read-only, 2026-08-23)

Status: **COMPLETE** â€” read-only audit; zero code, zero DB change, zero commits.
Report: `docs/phase_14/phase_14_architecture_audit.md`.

- [x] Repository-wide Firebase reference sweep (source, config, manifests, scripts, docs, tests, deployment files)
- [x] Every reference classified (live/dead/legacy/docs/test/config/false-positive)
- [x] Runtime dependency tracing: frontend (package.json, imports, auth providers, env) and backend (requirements, imports, startup)
- [x] `firebase_uid` audit: schema, model, Alembic history, schemas, repos, services, API responses, scripts â€” verdict: nullable legacy, safe to remove in 14D after script updates
- [x] Authentication flow proven: JWT â†’ `get_current_user()` â†’ PostgreSQL User; no Firebase path reachable
- [x] Firestore/data dependency audit: PostgreSQL-only proven for all domains
- [x] Deployment audit: `firebase.json`, `.firebaserc`, `firestore.rules`, `firestore.indexes.json` all obsolete
- [x] Dependency manifest audit: `firebase` (frontend) + `firebase-admin` (backend) â€” neither used for runtime functionality
- [x] Test/verifier audit: zero verifiers reference Firebase; legacy/scratch test files only
- [x] Documentation audit: stale Firebase claims catalogued for Phase 14F reconciliation
- [x] Governance updated for audit-only phase
- HARD STOP â€” audit only; no implementation begun.

## Phase 14A â€” Frontend Firebase Removal (COMPLETE, 2026-08-23)

Status: **COMPLETE** â€” implementation verified; zero backend/DB changes; no commit.

- [x] Verified audit findings against current working tree (frontend/src Firebase search)
- [x] Removed dead `import { auth } from "./firebase"` from `frontend/src/lib/api.ts` (no other api.ts change)
- [x] Deleted `frontend/src/lib/firebase.ts`
- [x] Removed `firebase` from `frontend/package.json`
- [x] Reconciled `frontend/package-lock.json` via `npm install` (77 packages pruned; `firebase`/`@firebase/*` absent)
- [x] Removed `NEXT_PUBLIC_FIREBASE_*` from `frontend/.env.example`
- [x] Removed `NEXT_PUBLIC_FIREBASE_*` from `frontend/.env.local` (no values exposed)
- [x] `npx tsc --noEmit` PASS
- [x] `npm run build` PASS (15/15 routes)
- [x] `git diff --check` PASS
- [x] Frontend Firebase search clean â€” only `firebase_uid` data-field strings (Phase 14D scope) and stale message/comment strings remain
- [x] `npm ls firebase` empty; lockfile consistent
- [x] Zero backend/database/migration changes confirmed via git diff
- [x] Frozen systems untouched (auth, JWT, engines, PWA, Phase 12, legacy root app)
- [x] Governance synchronized (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)
- HARD STOP â€” Phase 14B NOT STARTED; no commit made.

## Phase 14B â€” Backend Firebase Removal (COMPLETE, 2026-08-23)

Status: **COMPLETE** â€” implementation verified; zero DB/migration changes; no commit.

- [x] Deleted `backend/app/core/firebase.py`
- [x] Removed `initialize_firebase()` import/call from `backend/app/main.py` (nothing else touched)
- [x] Removed `firebase-admin>=6.5.0` from `backend/requirements.txt`
- [x] Uninstalled `firebase-admin` 7.5.0 + 13 Firebase transitive packages from venv; `pip check` clean; zero remnants
- [x] `python -m compileall backend/app backend/alembic` PASS
- [x] `app.main` imports clean without Firebase (32 API paths)
- [x] Auth endpoints verified in OpenAPI: `/api/v1/auth/login`, `/api/v1/auth/register`, `/student/me`, `/student/sync` PRESENT
- [x] JWT path structurally intact: `get_current_user`/`require_admin`/`HTTPBearer` (deps.py), `create_access_token`/`verify_password`/`hash_password` (security.py)
- [x] `git diff --check` PASS; diff limited to 3 backend files (36 deletions)
- [x] `firebase_uid` column/model/schema/API references intentionally preserved (Phase 14D scope)
- [x] Legacy migration scripts' `firebase_admin` imports left intact (historical tools, graceful blocked-exit)
- [x] Zero database mutations; zero Alembic commands
- [x] Frontend untouched (no frontend files in diff)
- [x] Frozen systems untouched (auth, JWT, engines, PWA, Phase 12)
- [x] Governance synchronized (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)
- HARD STOP â€” Phase 14C NOT STARTED; no commit made.

## Phase 14C â€” Deployment / Configuration Cleanup (COMPLETE, 2026-08-23)

Status: **COMPLETE** â€” implementation verified; zero DB/migration changes; no commit.

- [x] Deleted `firebase.json`, `.firebaserc`, `firestore.rules`, `firestore.indexes.json` (all 4 confirmed absent)
- [x] Removed Firebase-specific entries from `.gitignore` (firebase-debug logs, .firebase/ cache, .firebaserc config block)
- [x] Deleted entirely-Firebase prompts: `14_FIREBASE_BACKEND_PROMPT.md`, `19_DEPLOYMENT_PROMPT.md`
- [x] Removed Firestore/Firebase-Hosting sections from `prompts/11_RELEASE_CHECKLIST.md` (sections 5 + 8)
- [x] Removed Firestore-rules references from `prompts/01`, `prompts/03`, `prompts/04`, `prompts/16`
- [x] Updated `prompts/README.md` â€” removed index rows for deleted prompts, updated 11/16 descriptions, removed 19 from Release Workflow
- [x] Removed Firebase deploy/init instructions from `README.md` (Configure Firebase, Deploy Firestore Rules, Firebase Project/CLI, structure entries for deleted files)
- [x] `git diff --check` PASS
- [x] Diff limited to 13 files (8 deletions, 5 edits); zero backend/frontend source code changes
- [x] `firebase_uid` model/schema/API/scripts intentionally preserved (Phase 14D scope)
- [x] Legacy migration scripts (`migrate_extract.py`, `migrate_execute.py`, `diagnose_failures.py`) preserved
- [x] Legacy root app preserved
- [x] Historical `docs/` preserved (Phase 14F reconciliation)
- [x] Zero database mutations; zero Alembic commands
- [x] Frozen systems untouched
- [x] Governance synchronized
- HARD STOP â€” Phase 14D NOT STARTED; no commit made.

## Phase 14D â€” firebase_uid / Data Cleanup (COMPLETE, 2026-08-23)

Status: **COMPLETE** â€” implementation verified; migration applied; no commit.

- [x] Repository audit â€” every `firebase_uid` occurrence classified (runtime vs historical vs docs)
- [x] `backend/scripts/set_initial_password.py` â€” lookup switched to canonical `roll_number` (`2401220100027`)
- [x] `backend/scripts/setup_single_user.py` â€” lookup switched to canonical `roll_number` (`2401220100027`)
- [x] `backend/app/models/user.py` â€” `firebase_uid` column mapping removed
- [x] `backend/app/schemas/student.py` â€” `firebase_uid` removed from `StudentProfile`
- [x] `backend/app/api/v1/endpoints/student.py` â€” `/me` + `/sync` no longer serialize `firebase_uid`
- [x] `backend/app/api/v1/endpoints/auth.py` â€” register no longer writes `firebase_uid=None`
- [x] `backend/app/repositories/user_repo.py` â€” dead `get_by_firebase_uid()` + unused `selectinload` import removed
- [x] `frontend/src/types/api.ts` â€” `firebase_uid` removed from `StudentProfile` type
- [x] `frontend/src/contexts/AuthContext.tsx` â€” `firebase_uid` removed from `User` type
- [x] `frontend/src/app/(authenticated)/profile/page.tsx` â€” displays `user.id`; stale Firebase error message replaced
- [x] Migration `e1f2a3b4c5d6_drop_firebase_uid.py` created (down_revision `d1e2f3a4b5c6`; drop index + column; reversible)
- [x] Migration applied via `alembic upgrade head` â†’ alembic head `e1f2a3b4c5d6`
- [x] DB before/after verified: users 31=31, admin 1=1, students 30=30, enrollments 27=27, attendance 159=159, sessions 720=720, events 60=60, all other counts identical; column + index gone; Aditya's row untouched
- [x] `python -m compileall backend/app backend/scripts backend/alembic` PASS
- [x] `npx tsc --noEmit` PASS
- [x] `git diff --check` PASS
- [x] App imports clean; 32 paths; `/auth/login`, `/auth/register`, `/student/me`, `/student/sync` present
- [x] JWT chain intact (`get_current_user`, `require_admin`, `HTTPBearer`, `create_access_token`)
- [x] Zero `firebase_uid` references in `backend/app` + `frontend/src`; only historical docs/migrations remain (Phase 14F)
- [x] Historical migration files + completed `migrate_execute.py` preserved
- [x] Frozen systems untouched (auth, JWT, engines, PWA, Phase 12, 14A/14B/14C)
- [x] Governance synchronized
- HARD STOP â€” Phase 14E NOT STARTED; no commit made.

## Phase 14E â€” Regression Verification (COMPLETE, 2026-08-23)

Status: **COMPLETE** â€” all regression checks pass; zero feature work; no commit.

- [x] In-process regression suite: 66/67 PASS (1 harness artifact â€” not a regression)
- [x] DB baseline: alembic `e1f2a3b4c5d6`, column+index gone, users 31, admin 1, students 30
- [x] Password round-trip: format, correct, wrong, empty, salted
- [x] Login: valid->token, wrong password 401, nonexistent roll 401
- [x] JWT: `create_access_token`, `get_current_user` valid/invalid, `require_admin` ADMIN/STUDENT
- [x] `/student/me`: full contract; NO `firebase_uid`
- [x] `/student/sync`: returns correctly; NO `firebase_uid`
- [x] 16 core read paths: dashboard, attendance (history/daily/summary), calendar (month/today/date), events, quiz (cycle/eligibility), subjects, timetable, analytics, preferences, notifications, lab summary
- [x] Mutation contract: Attended/Missed/Pending accepted; cancelled 409; future 400; non-enrolled 403
- [x] Admin mutation wired to `require_admin` (signature verification)
- [x] Frozen-phase verifiers: 6.5 27/27, 6.6 36/36, 6.7 30/31 (check 7 pre-existing data), 7.1 26/26, 10C 23/23, 10D 18/18, 11A 19/19, 11B 23/23, 12E 5/5
- [x] Verifier compatibility fix: `verify_phase_11b.py` head assertion updated to `e1f2a3b4c5d6`
- [x] Persistent-mutation audit: 2 leaked test artifacts detected and removed; final DB byte-identical
- [x] `python -m compileall backend/app backend/scripts backend/alembic` PASS
- [x] `npx tsc --noEmit` PASS
- [x] `npm run build` PASS (15/15 routes)
- [x] Firebase search: zero `firebase`/`firestore`/`firebase_uid` in `backend/app` + `frontend/src`; only 3 stale comments remain (14F)
- [x] `git diff --check` PASS
- [x] Zero feature work; zero auth/JWT/engine changes; browser/manual testing deferred
- [x] Governance synchronized
- HARD STOP â€” Phase 14F NOT STARTED; no commit made.

## Phase 14F â€” Freeze & Governance Reconciliation (COMPLETE, 2026-08-23)

Status: **COMPLETE** â€” reconciliation finished; zero code/DB changes; no commit.

- [x] Repository audit: every Firebase reference classified (active/current-doc/historical/migration/legacy-artifact/false-positive)
- [x] Active-runtime Firebase check: zero in `frontend/src`, `backend/app`, manifests, config
- [x] `README.md` rewritten â€” current architecture (PostgreSQL â†’ FastAPI â†’ JWT â†’ Next.js), Firebase RETIRED, legacy app noted as preserved/pending separate retirement
- [x] Historical banners added: `backend/API_DESIGN.md`, `backend/DATABASE_DESIGN.md`, `backend/MIGRATION_NOTES.md`, `backend/MIGRATION_AUDIT.md`
- [x] `docs/README.md` boundary banner â€” docs/ series documented as legacy-app documentation
- [x] `MASTER_ROADMAP.md` â€” Phase 14 COMPLETE & FROZEN; Phase 15 (Legacy Web App + Legacy PWA Retirement) inserted; phases renumbered 15â†’16 â€¦ 21â†’22; status blocks synchronized
- [x] `migrate_extract.py`/`migrate_execute.py`/`diagnose_failures.py` confirmed historical one-shot tooling, preserved
- [x] Historical migrations + migration reports preserved
- [x] Legacy root app + legacy PWA preserved in full (NOT retired in 14F)
- [x] `git diff --check` PASS
- [x] `npx tsc --noEmit` PASS; `npm run build` PASS
- [x] `python -m compileall backend/app` PASS
- [x] Alembic single head `e1f2a3b4c5d6` unchanged
- [x] Zero DB mutations; zero schema/migration changes; zero application code changes
- [x] Frozen systems untouched
- [x] Governance synchronized (roadmap, plan, task, walkthrough)
- HARD STOP â€” Phase 15 NOT STARTED; no commit made.

## Phase 15 â€” Legacy Web App + Legacy PWA Retirement (COMPLETE, 2026-08-23)

Status: **COMPLETE** â€” retirement finished; zero DB changes; no commit.

- [x] Repository audit â€” every legacy file classified; no ambiguous file deleted
- [x] Removed legacy runtime: root `index.html`, `js/` (21), `css/` (3), `assets/icons/` (3), `offline.html`, root `manifest.json`, root `service-worker.js`, `screenshot.png`
- [x] Removed legacy test/tooling: `test-e2e.js`, `scratch_pwa_*` (4)
- [x] Removed legacy-only root package files: `package.json`, `package-lock.json`, `node_modules/` (frontend deps untouched)
- [x] Preserved `timetable.json` (active backend data dependency â€” verified via 5 scripts)
- [x] Preserved historical provenance: docs/, walkthroughs, migration tooling, Alembic history, root reports, prompts/
- [x] No feature porting; no compatibility wrappers; no legacy route recreation
- [x] Documentation reconciled: README.md, docs/README.md, prompts/README.md (retired boundary notes)
- [x] `npx tsc --noEmit` PASS
- [x] `npm run build` PASS (15/15; multi-lockfile warning resolved)
- [x] `python -m compileall backend/app` PASS
- [x] `git diff --check` PASS
- [x] Zero active references to retired files; frontend `/manifest.json` + `/service-worker.js` = active Phase 13 PWA
- [x] Alembic single head `e1f2a3b4c5d6` unchanged; zero DB mutations
- [x] Frozen systems untouched (incl. current Next.js PWA)
- [x] Governance synchronized
- HARD STOP â€” Phase 16 NOT STARTED; no commit made.

## Phase 16 â€” Production Security Hardening (COMPLETE, 2026-08-23)

Status: **COMPLETE** â€” security audit + hardening; zero DB mutations; no commit.

- [x] Security audit: config, security.py, deps.py, auth endpoints, CORS, main.py, all endpoints, IDOR, error handling, logging, secrets, frontend, dependencies
- [x] JWT: expiry default 480 min (env-configurable, was 30 days); `iat` claim; `type=="access"` enforced at decode
- [x] Password policy: 8â€“128 chars, â‰¥1 letter, â‰¥1 digit (Pydantic + frontend signup synced)
- [x] Rate limiting: in-process sliding window â€” login 10/15min, register 5/h, per-IP, 429 + Retry-After
- [x] Login timing equalization: dummy PBKDF2 hash when roll_number not found
- [x] Security headers: X-Content-Type-Options, X-Frame-Options DENY, Referrer-Policy no-referrer, Permissions-Policy; HSTS env-gated
- [x] Global 500 exception handler (logs server-side, generic client response)
- [x] Error-leak fix: attendance mutation returns generic 400 (internals logged)
- [x] Logging setup: auth failures + unhandled errors; no passwords/tokens/secrets
- [x] `backend/.env.example` updated with all security env vars (placeholders only)
- [x] CORS env-driven explicit origins (no wildcard with credentials)
- [x] `verify_phase_16.py` created â€” 34/34 PASS (auth matrix, admin, cross-user isolation, rate limiting, password policy, headers, CORS, error non-leak)
- [x] Frozen verifiers re-run: 6.5 27/27, 10C 23/23, 10D 18/18, 11A 19/19 â€” all PASS
- [x] `python -m compileall backend/app` PASS
- [x] `npx tsc --noEmit` PASS
- [x] `npm run build` PASS (15/15)
- [x] `git diff --check` PASS
- [x] Alembic single head `e1f2a3b4c5d6` unchanged; zero DB mutations
- [x] Frozen systems untouched (engines, PWA, auth architecture, legacy retirement)
- [x] Governance synchronized
- HARD STOP â€” Phase 17 NOT STARTED; no commit made.

## Phase 17 â€” Data Integrity & Migration Hardening (COMPLETE & FROZEN, 2026-08-23)

Status: **COMPLETE & FROZEN** â€” all authorized Phase 17 work done; zero working-DB mutations; no commit.

- [x] P0 â€” JWT production-secret guard: `APP_ENV` config; production rejects dev/short secrets at startup; no secret in errors; dev behavior preserved
- [x] `verify_phase_17_jwt_guard.py` â€” 6/6 PASS (dev loads; prod+default rejected; prod+short rejected; prod+valid loads; no leak; empty APP_ENV=dev)
- [x] Alembic audit â€” single head `e1f2a3b4c5d6`, 14 migrations, linear chain, no gaps
- [x] Integrity audit â€” zero orphans (all FK relationships), zero duplicate keys, zero out-of-bounds records
- [x] Session "duplicates" â€” 85 groups proven legitimate (2-hour lab blocks); 2 NULL-entry extra sessions benign (no attendance)
- [x] Legacy state â€” 28 users without password/section documented (Firebase-era; not defects)
- [x] **NO MIGRATION REQUIRED** â€” documented with evidence
- [x] `backup_database.ps1` created + verified (pg_dump -Fc, gitignored backups/)
- [x] `restore_database.ps1` created (`-TestSwitch` = isolated container)
- [x] Restore test executed â€” isolated postgres:16 container, counts verified, container removed, working DB untouched
- [x] Seed audit â€” event seed idempotent (semantic skip, no resurrection); baseline deterministic from timetable.json
- [x] Semester-transition analysis â€” session-scoped vs global mapped; hardcoded span documented as current-semester config; no schema change needed
- [x] Cleanup â€” none required (no invalid rows); preserved 2 extra sessions + legacy accounts
- [x] `.gitignore` â€” `backups/` added
- [x] `backend/.env.example` â€” `APP_ENV` documented
- [x] Retention policy documented â€” daily 7 / weekly 4 / monthly 3; backups gitignored; isolated restore for verification; rotation deferred to Phase 18
- [x] Zero database mutations during audit (read-only SQL + isolated-container restore only)
- [x] Long-term academic model (multi-semester support) â€” future architectural work (documented, not Phase 17 blocker)
- HARD STOP â€” Phase 17 COMPLETE & FROZEN; Phase 18 NOT STARTED; no commit made.

## Phase 18 â€” Production Infrastructure (IN PROGRESS)

### Phase 18.0 â€” Infrastructure Audit (COMPLETE, read-only)

- [x] Read-only production infrastructure audit (report: `docs/phase_18/phase_18_0_infrastructure_audit.md`)
- [x] Frontend audit (Next.js 16 SSR â€” Node runtime required; PWA preserved)
- [x] Backend audit (uvicorn workers, proxy headers, health endpoints)
- [x] PostgreSQL privacy audit + Alembic head `e1f2a3b4c5d6` confirmed
- [x] Backup/retention + security-sensitive env audit
- [x] Docker/container audit (no Dockerfiles existed)
- [x] Hosting options comparison (recommended: single VPS + Docker Compose)
- [x] Environment contract + deployment topology documented
- [x] Zero DB mutations; zero commits

### Phase 18A â€” Production Containerization & Orchestration (COMPLETE)

- [x] `frontend/Dockerfile` â€” multi-stage Next.js 16 SSR, standalone output, non-root, PWA preserved
- [x] `backend/Dockerfile` â€” python:3.13-slim FastAPI, non-root, uvicorn workers, `--proxy-headers`, healthcheck
- [x] `docker-compose.prod.yml` â€” caddy + frontend + backend + postgres:16
- [x] PostgreSQL private (internal `data-net`, no host port)
- [x] Private networks: `proxy-net` + `data-net` (internal)
- [x] `deploy/caddy/Caddyfile` â€” HTTP routing `/api/*` â†’ backend, `*` â†’ frontend; X-Forwarded-For preserved
- [x] `deploy/.env.prod.example` â€” env contract (no real secrets; `.env.prod` gitignored)
- [x] `frontend/next.config.ts` â€” `output: "standalone"` (justified, build verified)
- [x] `frontend/package-lock.json` â€” regenerated on Linux for deterministic `npm ci` (@emnapi resolution)
- [x] Healthchecks (postgres pg_isready, backend /health, frontend wget /, caddy wget /)
- [x] Restart policies (`unless-stopped`) + `depends_on` postgres healthy condition
- [x] Docs: `docs/phase_18/phase_18a_containerization.md`
- [x] `docker compose config` valid â€” only proxy port 80 exposed
- [x] Backend image build PASS; frontend image build PASS
- [x] `npm ci` + `npm run build` PASS (15/15); `compileall` PASS; `git diff --check` PASS
- [x] Zero DB mutations; zero cloud resources; dev compose untouched
- HARD STOP â€” Phase 18B NOT STARTED; no commit made.

### Phase 18B â€” Environment & Secret Management (COMPLETE, 2026-08-23)

- [x] Production guard extended: `_validate_production_config` rejects dev DATABASE_URI (localhost/127.0.0.1/host.docker.internal) and localhost CORS in production â€” errors never print secrets
- [x] Compose `${VAR:?}` required syntax for POSTGRES_USER, POSTGRES_PASSWORD, JWT_SECRET_KEY, BACKEND_CORS_ORIGINS, NEXT_PUBLIC_API_URL
- [x] DATABASE_URI built at runtime from POSTGRES_* (overridable via DATABASE_URI env)
- [x] Proxy-net subnet pinned (172.28.0.0/24) + FORWARDED_ALLOW_IPS env on backend
- [x] Backend Dockerfile CMD â€” `--forwarded-allow-ips` for explicit proxy trust (Caddy only)
- [x] Caddyfile + Dockerfile comments document trust boundary (XFF spoofing outside subnet ignored)
- [x] `deploy/.env.prod.example` â€” required/optional split, public/secret markers, placeholders only
- [x] `backend/.env.example` â€” DEVELOPMENT ONLY header + dev credentials warning
- [x] `frontend/.env.example` â€” public-var note
- [x] `docs/phase_18/phase_18b_secrets.md` â€” full env contract documentation
- [x] `verify_phase_17_jwt_guard.py` â€” 8/8 PASS (JWT guard + DB/CORS production rejections)
- [x] `docker compose config` fails fast without required vars; renders correctly with them
- [x] `compileall` PASS; `tsc` PASS; `git diff --check` PASS
- [x] Secret audit: only example env files tracked; no real secrets in any committed file
- [x] Zero DB mutations; zero deployment; zero cloud resources; no real secrets added
- HARD STOP â€” Phase 18C NOT STARTED; no commit made.

### Phase 18C â€” Backup Automation + Retention + Off-Host Protection (COMPLETE, 2026-08-23)

- [x] `deploy/backup/Dockerfile` â€” postgres:16-based backup container
- [x] `deploy/backup/run.sh` â€” scheduler: locking, pg_isready wait, ordered orchestration, fail-fast required env
- [x] `deploy/backup/backup.sh` â€” pg_dump -Fc + verification (exists, â‰¥1KB, pg_restore --list); PGPASSWORD env only
- [x] `deploy/backup/offhost.sh` â€” off-host copy contract (none/mount/sftp/s3/custom), fails loudly
- [x] `deploy/backup/retention.sh` â€” keep latest 14 (BACKUP_RETENTION_COUNT), only matching files, after successful backup+off-host
- [x] `docker-compose.prod.yml` â€” backup service on data-net, backup_data volume, healthy-depends, unless-stopped, healthcheck
- [x] `deploy/.env.prod.example` â€” backup variables (BACKUP_INTERVAL, BACKUP_RETENTION_COUNT, OFFHOST_*)
- [x] `docs/phase_18/phase_18c_backup.md` â€” architecture, config contract, retention, restore runbook, failure handling
- [x] Bash syntax validation (postgres:16 container) â€” all scripts PASS
- [x] Backup image build PASS
- [x] `docker compose config` valid with backup service
- [x] Isolated smoke test: seed disposable DB â†’ backup.sh verified dump â†’ retention pruned â†’ pg_restore into 2nd disposable DB â†’ data verified â†’ resources removed
- [x] Working application DB untouched (INSERT/UPDATE/DELETE = 0)
- [x] No real secrets/credentials; no deployment; no cloud resources
- [x] Governance synchronized
- HARD STOP â€” Phase 18D NOT STARTED; no commit made.

### Phase 18D â€” Deployment & Verification (PARTIAL, 2026-08-23)

Status: **PARTIAL** â€” rehearsal deployment + full verification PASS; production deployment BLOCKED on missing infrastructure (no host/credentials/domain/off-host destination).

- [x] Repository + governance review before implementation
- [x] Deployment boundary assessment â€” production infra unavailable, documented
- [x] Compose config + env resolution validated (full env set, `${VAR:?}` fail-fast)
- [x] Production images built (backend, frontend, backup)
- [x] **Defect fixed**: `pyjwt>=2.10.0` added to `backend/requirements.txt` (missing dep, backend crashed at import)
- [x] **Defect fixed**: Caddy `handle /health` route added (`deploy/caddy/Caddyfile`)
- [x] Rehearsal deployment (disposable): 5 services up, all healthy
- [x] Health checks: postgres/backend/frontend/backup/caddy + proxy routing PASS
- [x] Backup executed (real `backup.sh`): 2972 bytes, pg_restore --list verified
- [x] Retention + scheduler lock + off-host contract (none) verified
- [x] Isolated restore PASS (disposable container, data verified, removed)
- [x] Security: no secrets in logs/argv; PostgreSQL private; only port 80 exposed
- [x] Application DB untouched (INSERT/UPDATE/DELETE = 0)
- [x] Rehearsal/restore containers + volumes cleaned (0 remaining)
- [x] `docs/phase_18/phase_18d_deployment.md` created (report + runbook + blockers)
- [x] Governance synchronized (roadmap, plan, task, walkthrough)
- [ ] **BLOCKED**: production deployment requires operator to provision VPS/host + credentials + domain + optional off-host destination
- HARD STOP â€” no commit made.

### Phase 19 â€” CI/CD (COMPLETE & FROZEN, 2026-08-23)

- [x] `.github/workflows/ci.yml` created (PR + push to main, concurrency cancel-in-progress)
- [x] JOB integrity â€” secret/env-file/Firebase-artifact scan + required-file validation
- [x] JOB backend â€” compileall, app import, JWT guard verifier (8/8), static invariants (12E)
- [x] JOB frontend â€” npm ci (npm 11), tsc, lint (informational), production build
- [x] JOB docker â€” backend + frontend + backup image builds (no registry push)
- [x] JOB compose â€” `docker compose config --quiet` with CI placeholders + hardcoded-secret scan
- [x] JOB migrations â€” disposable postgres:16, single-head check, `alembic upgrade head`, revision match
- [x] JOB config-contract â€” env example required vars, no dev creds in prod example
- [x] JOB backup-infra â€” `bash -n` all backup scripts + backup image build
- [x] JOB deploy â€” disabled (`if: ${{ false }}`), environment: production, needs all quality jobs
- [x] Lint made informational (6 pre-existing frozen-system ESLint errors; documented, not fixed)
- [x] YAML validation PASS (triggers, 9 jobs, deploy disabled)
- [x] Local verification of every job: backend/frontend/docker/compose/migrations/config/backup PASS
- [x] Migration validated on disposable postgres:16 to head `e1f2a3b4c5d6`; disposable DB cleaned
- [x] `docs/phase_19/phase_19_cicd.md` created
- [x] `git diff --check` PASS
- [x] No deployment; no secrets; no cloud resources; working application DB untouched
- [x] Governance synchronized
- HARD STOP â€” Phase 20 NOT STARTED; no commit made.

### Phase 20 â€” Production QA (COMPLETE & FROZEN, 2026-08-24)

- [x] Governance review (roadmap, plan, task, walkthrough, Phase 19/18D docs)
- [x] In-process QA: authentication (password, login 401s, register policy, JWT, require_admin)
- [x] In-process QA: profile contract (11 fields, no firebase_uid)
- [x] In-process QA: dashboard summary (attendance, quiz snapshot, attention, events)
- [x] In-process QA: Track daily sessions + cancelled-session 409 protection
- [x] In-process QA: History (100 items, semester-bounded, item contract)
- [x] In-process QA: Calendar month/today/date + DB session count
- [x] In-process QA: Events list + admin dependency
- [x] In-process QA: Quiz eligibility full contract + threshold-vs-policy consistency
- [x] In-process QA: Laboratory BCS-551 + admin-only mutation 403
- [x] In-process QA: Preferences, notifications, security isolation
- [x] Cross-surface consistency (20/20): summary==DB, quiz thresholds==policy, calendar==DB, history==canonical
- [x] Frozen verifier regression: 6.5 27/27, 6.6 36/36, 6.7 30/31 (known), 12E 8/8, 16 34/34, 17 8/8
- [x] QA temp-user artifact removed; DB hygiene verified (users 31, alembic e1f2a3b4c5d6)
- [x] 5 attendance + 62 notification QA-window deltas documented for user review (attendance protected)
- [x] `docs/phase_20/phase_20_production_qa.md` created (incl. 42-item manual browser QA checklist)
- [x] Governance synchronized (roadmap, plan, task, walkthrough)
- [ ] USER TASK: manual browser QA checklist (Â§19) â€” NOT PERFORMED BY AGENT (user responsibility)
- [ ] USER TASK: confirm attendance/notification QA-window deltas (Â§16) â€” user review
- HARD STOP â€” Phase 21 NOT STARTED; no commit made.

### Phase 21 â€” Production Launch (COMPLETE & FROZEN, 2026-08-26)

Status: **COMPLETE & FROZEN** â€” production LIVE (Vercel + Render + Supabase),
operator-verified end-to-end; all launch gates RESOLVED. Closure:
`docs/phase_21/phase_21d4_production_closure.md`.

- [x] Governance review (roadmap, plan, task, walkthrough, Phase 20/18D/19 docs)
- [x] Pre-flight gate assessment: A (browser QA) / B (QA-window data) / C (infrastructure)
- [x] Static launch-readiness inspection (read-only: CI gate disabled, env contract, Caddy, alembic head, infra evidence)
- [x] `docs/phase_21/phase_21_production_launch.md` created (full launch assessment + blockers + sequence + rollback)
- [x] Working database untouched (INSERT/UPDATE/DELETE/ALTER/DROP = 0)

### Phase 21A â€” Account Audit & Cleanup (COMPLETE & FROZEN, 2026-08-24)

- [x] Governance review + database identification (dev `attendancedash`, PostgreSQL 16; no production DB)
- [x] Account schema inspection (users table columns, roles, hashed_password)
- [x] Complete account inventory â€” 31 accounts, actual DB values
- [x] Owner verification â€” 2401220100027 Aditya Tiwari ADMIN PROTECTED
- [x] Dependent-data audit per user (enrollments, attendance, notifications, preferences, feedback, lab)
- [x] QA-window delta association (5 attendance â†’ owner; 62 notifications â†’ owner/9999999999999/1234567890124)
- [x] Feedback association (0 records)
- [x] Auth model check (login by roll_number, PBKDF2, JWT, DB role; no delete implementation; FKs NO ACTION)
- [x] Classification (1 PROTECTED OWNER, 1 LIKELY REAL USER, 29 LIKELY TEST)
- [x] Proposed cleanup plan (24 delete-after-approval, 6 review, 1 protected)
- [x] `docs/phase_21/phase_21a_account_audit.md` created
- [x] Zero database mutations (INSERT/UPDATE/DELETE/ALTER/DROP = 0); git diff --check PASS
- [x] Governance synchronized
- [x] USER TASK: approve/reject the 24-account deletion set â€” RESOLVED (21A.1 authorization: delete all except owner)
- [x] USER TASK: classify 1234567890124 (real user vs test); disposition 6 REVIEW accounts â€” RESOLVED (21A.1: deleted per authorization)
- [x] GATE A: user completes Phase 20 manual browser QA (42-item checklist) â€” RESOLVED (operator completed browser QA; production browser/mobile/PWA validation passed 2026-08-26)
- [x] GATE B: user dispositions Phase 20 QA-window deltas â€” RESOLVED (21A.1 + 21C: owner-owned records preserved; non-owner removed)
- [x] GATE C: operator provisions VPS/cloud host, production credentials, domain/DNS, TLS/HTTPS, off-host backup â€” RESOLVED via free-beta architecture (21D.2: Vercel + Render + Supabase provisioned; HTTPS automatic; backup limitation documented)
- [x] Production DB migration (`alembic upgrade head`) â€” EXECUTED (21D.2 schema init + 21D.3 data migration, head e1f2a3b4c5d6)
- [x] Production academic config initialization â€” EXECUTED (21D.3: full academic baseline migrated)
- [x] Backend deploy + health â€” EXECUTED (Render Free, /health 200)
- [x] Frontend deploy + health â€” EXECUTED (Vercel Hobby)
- [x] Caddy/HTTPS/domain verification â€” EXECUTED (provider automatic HTTPS; Caddy path preserved for future paid infra)
- [x] Production backup execution + verification â€” EXECUTED (21D.3 localhost pre-migration backup; Supabase Free auto-backup limitation documented)
- [x] Smoke tests (auth, student, attendance, calendar, quiz, lab, settings, security) â€” EXECUTED (operator: production login, ADMIN, dashboard, desktop, mobile, PWA verified)
- [x] Rollback plan documented + monitoring verified â€” EXECUTED (21D.2 migration audit rollback strategy; provider monitoring dashboards)
- HARD STOP â€” Phase 21 COMPLETE & FROZEN; no commit made.

### Phase 21A.1 â€” Approved Account Cleanup (COMPLETE & FROZEN, 2026-08-24)

- [x] User authorization confirmed (delete all except 2401220100027)
- [x] Governance review + DB identification (dev `attendancedash`, no production)
- [x] Pre-mutation safety check: 31 users, owner ADMIN present, deletion set = 30 (owner excluded)
- [x] Admin baseline captured (enrollments 9, attendance 159, notifications 39, prefs 1, feedback 0)
- [x] Dependency graph via dynamic FK inspection (all NO ACTION; children first)
- [x] Transactional execution: dependents (59 rows) â†’ 30 users â†’ in-transaction verification â†’ COMMIT
- [x] Post-delete verification: 1 user (owner ADMIN, password intact)
- [x] Admin invariants preserved (enrollments 9, attendance 159 incl. QA-window 5, notifications 39, prefs 1, feedback 0)
- [x] Orphan check: 0 rows across all 9 user FK columns
- [x] Academic/system data untouched (subjects 9, sessions 720, quiz 18, events 60)
- [x] Alembic head `e1f2a3b4c5d6` unchanged
- [x] Application integrity: backend import, ORM lookup, JWT, require_admin, login-401 PASS
- [x] `docs/phase_21/phase_21a1_account_cleanup.md` created
- [x] Governance synchronized
- HARD STOP â€” Phase 21B NOT STARTED; no commit made.

### Phase 21B â€” Feedback Admin System (COMPLETE & FROZEN, 2026-08-25)

- [x] Audit existing feedback model/schema/API/frontend (Phase 10C exists; no admin contract/UI)
- [x] Backend: `GET /api/v1/feedback/admin` (paginated, feedback_type filter) + `GET /api/v1/feedback/admin/{id}` â€” require_admin
- [x] Backend: Feedback.user relationship + repo list_all/get_by_id + service list_admin/get_admin
- [x] Backend: schemas (FeedbackListItem, FeedbackListResponse) â€” no credentials serialized
- [x] Frontend: types (FeedbackType, FeedbackAdminItem, FeedbackAdminListResponse, AdminFeedbackParams)
- [x] Frontend: `useAdminFeedback()` hook
- [x] Frontend: `/tools/feedback` admin page (loading/error/empty/list + filter + pagination)
- [x] Navigation: Feedback link in TopNav + MobileBottomNav â€” ADMIN-only at UX layer
- [x] Student submission flow preserved (POST /api/v1/feedback, JWT-derived user_id, server validation)
- [x] Auth matrix verified: unauthenticated 401, STUDENT 403, ADMIN 200, 404, filters, pagination (17/17 PASS)
- [x] Harness rows (2 feedback + 1 temp user) cleaned; feedback back to 0; users back to 1
- [x] `npx tsc --noEmit` PASS; `npm run build` PASS (incl. /tools/feedback); compileall PASS; git diff --check PASS
- [x] No migration needed (existing table reused); alembic head unchanged
- [x] Protected admin data intact (enrollments 9, preferences 1, feedback 0); user-activity deltas preserved
- [x] `docs/phase_21/phase_21b_feedback_admin.md` created
- [x] Governance synchronized (roadmap, plan, task, walkthrough)
- [ ] USER TASK: browser/manual verification of the admin feedback page â€” NOT PERFORMED (user responsibility)
- HARD STOP â€” Phase 21C next; no commit made.

### Phase 21C â€” Production Launch Pre-flight / Gate Closure (COMPLETE & FROZEN, 2026-08-25)

Status: **COMPLETE** (assessment) â€” Phase 21 was BLOCKED at the time of the 21C assessment; subsequently resolved and COMPLETE (see 21D.4); read-only; no deployment.

- [x] Governance review + repo state inspection (read-only)
- [x] Gate A assessment: browser QA confirmation â€” BLOCKED / USER RESPONSIBILITY at assessment time; RESOLVED by operator browser QA (2026-08-26)
- [x] Gate B assessment: QA-window data disposition â€” RESOLVED (owner-owned records preserved; non-owner removed by 21A.1)
- [x] Gate C assessment: production infrastructure â€” BLOCKED at assessment time; RESOLVED by 21D.2 free-beta provisioning (Vercel + Render + Supabase)
- [x] `docs/phase_21/phase_21c_readiness.md` created
- [x] Zero database mutations (INSERT/UPDATE/DELETE/ALTER/DROP = 0)
- [x] Governance synchronized (roadmap, plan, task, walkthrough)
- [x] USER TASK: complete + report Phase 20 manual browser QA checklist (Gate A) â€” COMPLETED by operator (2026-08-26)
- [x] USER/OPERATOR TASK: provision production infrastructure (Gate C) â€” COMPLETED by operator (21D.2: Vercel + Render + Supabase)
- HARD STOP â€” Phase 21 COMPLETE & FROZEN; no commit made.

### Phase 21D â€” Free Public Beta Deployment (COMPLETE, 2026-08-26)

#### 21D.0 â€” Architecture & Provider Selection (COMPLETE & FROZEN, 2026-08-25)

- [x] Governance review + repo architecture inspection (Next.js SSR, FastAPI Docker, PostgreSQL 9.1 MB)
- [x] Free-tier research (official docs 2026-08-25): Vercel, Cloudflare Pages, Render, Supabase, Railway, Fly, Oracle, Workers
- [x] DB size analysis: current 9.1 MB; 300-user estimate < 50 MB (Supabase 500 MB quota = 10Ã— headroom)
- [x] Provider decision matrix produced
- [x] Recommended architecture selected: Vercel (frontend) + Render (backend) + Supabase (DB), â‚¹0
- [x] Cloudflare Pages rejected (static-only; SSR incompatible without code change)
- [x] Render Postgres Free rejected (30-day expiration)
- [x] Capacity analysis for 100â€“300 normal beta users
- [x] Security requirements mapped (HTTPS, secrets, CORS, admin auth preserved)
- [x] Backup strategy documented (Supabase Free has NO auto backups â€” beta limitation)
- [x] HTTPS/domain: all providers supply HTTPS on subdomains â€” no paid domain needed
- [x] CI/CD note: existing quality gate reused; deployment gate stays disabled
- [x] Future scaling path documented (provider upgrades, portable code)
- [x] Legacy deployment artifacts preserved (Dockerfiles, compose, Caddy, backup container)
- [x] `docs/phase_21/phase_21d0_free_beta_architecture.md` created
- [x] Governance synchronized (roadmap, plan, task, walkthrough)
- [x] Zero database mutations; zero cloud resources; no deployment
- HARD STOP â€” Phase 21D.1 NOT STARTED; no commit made.

#### 21D.1 â€” Production Configuration Hardening (COMPLETE & FROZEN, 2026-08-25)

- [x] Read-only baseline inspection (env vars, config.py, Dockerfile, alembic, health, gitignore)
- [x] Production environment contract documented (frontend public / backend secret / backend config)
- [x] Frontend production URL guard: `NEXT_PUBLIC_API_URL` missing or localhost â†’ fail loudly (no silent dev fallback)
- [x] Backend Dockerfile: `--port ${PORT:-8000}` + healthcheck reads PORT (Render compatible)
- [x] Runtime PORT verification (PORT=18080 â†’ /health 200)
- [x] `render.yaml` blueprint created (docker build, healthCheckPath, env placeholders, secret markers)
- [x] `FORWARDED_ALLOW_IPS` kept at secure default (coarse rate limiter behind Render proxy; no spoofable XFF)
- [x] Env examples hardened (frontend + backend: Supabase DATABASE_URI, CORS, PORT, HSTS contract)
- [x] Migration-on-deploy contract documented (one-shot pre-deploy, not in container CMD)
- [x] Health endpoint reused (`GET /health`, no auth/DB) â€” no duplicate health system
- [x] CORS/security review confirmed (env-driven exact origins; localhost rejected in production; no `*`)
- [x] Secret-pattern scan clean (only legit: config default, examples, CI integrity grep)
- [x] Gitignore verified (`.env`, `.env.local`, `deploy/.env.prod` ignored)
- [x] Frozen areas untouched (engines, auth, JWT, require_admin, schema, migrations, PWA, routes)
- [x] `npx tsc --noEmit` PASS; `compileall` PASS; `docker build` PASS; `git diff --check` PASS
- [x] `docs/phase_21/phase_21d1_config_hardening.md` created
- [x] Governance synchronized
- [x] Zero DB mutations; zero cloud resources; no deployment; no production secrets
- HARD STOP â€” 21D.1 complete; 21D.2 audit next; no commit made.

#### 21D.2 â€” Database Connection Compatibility Audit (COMPLETE, 2026-08-25)

- [x] Inspect connection architecture (config.py, db/session.py, alembic env.py, requirements, Dockerfile, render.yaml)
- [x] Verify installed versions: SQLAlchemy 2.0.52, asyncpg 0.31.0
- [x] Confirm asyncpg.connect() accepts `ssl=` but NOT `sslmode=`
- [x] Confirm SQLAlchemy asyncpg dialect passes URL query params verbatim (`opts.update(url.query)`)
- [x] Defect found: `?sslmode=require` would raise TypeError at connect
- [x] Corrected documentation to asyncpg-native `?ssl=require` (backend/.env.example, 21D.1 doc, 21D.2 runbook; port 6543 â†’ 5432)
- [x] Verified full Session Pooler URL parse (host/port/user/db/ssl=require)
- [x] Verified session-mode PgBouncer supports prepared statements (no cache tuning needed)
- [x] Verified Alembic uses same settings.DATABASE_URI (single head e1f2a3b4c5d6)
- [x] Verified Render can supply DATABASE_URI as secret (sync: false)
- [x] No code change required (URL is env-driven; only docs corrected)
- [x] No production DB accessed/mutated; no secrets accessed/generated
- [x] `docs/phase_21/phase_21d2_database_connection_audit.md` created
- [x] Zero DB mutations (dev + production); git diff --check PASS
- [x] Governance synchronized
- HARD STOP â€” 21D.2 connection audit complete (provisioning was BLOCKED at that time; subsequently COMPLETE 2026-08-26); no commit made.

#### 21D.2 â€” Alembic URL Interpolation Defect Fix (COMPLETE, 2026-08-25)

- [x] Reproduced `ValueError: invalid interpolation syntax` with `%23` in URL (default ConfigParser)
- [x] Confirmed Alembic 1.19.1 `file_config` memoized; `config_args` passes as defaults (interpolation= not injectable)
- [x] Confirmed `Interpolation()` no-op fixes both `set()` and `get()` (same as interpolation=None)
- [x] Applied fix in `backend/alembic/env.py`: `config.file_config._interpolation = Interpolation()` (+12 lines)
- [x] `alembic heads` with `%23` URL â†’ `e1f2a3b4c5d6 (head)`, exit 0
- [x] `alembic upgrade head --sql` (offline; executes env.py; NO DB connection) â†’ exit 0, 289 lines SQL, upgrade to head present
- [x] `python -m compileall alembic app` PASS
- [x] `git diff --check` PASS
- [x] No migration files/models/app code changed; no migration created
- [x] Failed migration attempt never connected to or mutated Supabase (error was local, pre-connection)
- [x] `docs/phase_21/phase_21d2_alembic_url_fix.md` created
- [x] Governance synchronized
- [x] Development DB: 0 mutations Â· Production DB: NOT ACCESSED/NOT MIGRATED/NOT MUTATED
- HARD STOP â€” 21D.2 Alembic fix complete (provisioning was BLOCKED at that time; subsequently COMPLETE 2026-08-26); no commit made.

#### 21D.2 â€” Vercel/Next.js 16.3 Deployment Compatibility Fix (COMPLETE, 2026-08-25)

- [x] Reproduced/understood `ENOENT: /vercel/path0/frontend/.next/next-server.js.nft.json` (unconditional standalone + Vercel adapter)
- [x] Verified installed Next.js 16.3 `output` docs (standalone + default behavior)
- [x] Applied fix in `frontend/next.config.ts`: `output: process.env.VERCEL ? undefined : "standalone"`
- [x] Non-Vercel build (Docker/local path) exit 0 â€” `.next/standalone/server.js` present
- [x] Vercel-mode build (`VERCEL=1`) exit 0 â€” `.next/standalone` absent, `.next/next-server.js.nft.json` present
- [x] `npx tsc --noEmit` PASS
- [x] `git diff --check` PASS
- [x] No API URLs, auth, backend, or Docker config changed; SSR + PWA preserved
- [x] Governance synchronized (roadmap, plan, task, walkthrough)
- [x] COMMIT + PUSH to `main` (so Vercel can auto-redeploy)
- HARD STOP â€” 21D.2 Vercel fix complete (provisioning was BLOCKED at that time; subsequently COMPLETE 2026-08-26).

#### 21D.2 â€” Provider Project Provisioning & Environment Wiring (COMPLETE, 2026-08-26)

Status: **COMPLETE** â€” operator provisioned all three providers and wired the
environment; production is LIVE.

- [x] Governance review (roadmap, plan, task, walkthrough, 21D.0/21D.1 reports)
- [x] Provider access check: vercel/render/supabase/gh CLIs â€” none installed (agent environment)
- [x] Provider tokens in environment â€” none found (agent environment)
- [x] Provider state dirs (`.vercel`, `.render`, `supabase/`) â€” none exist (agent environment)
- [x] No fabricated project IDs/URLs/credentials (none created, none claimed by agent)
- [x] `docs/phase_21/phase_21d2_provisioning_runbook.md` created (8-step operator runbook + guardrails)
- [x] Zero DB mutations; zero cloud resources created by agent; zero code changes
- [x] Governance synchronized
- [x] OPERATOR: create Supabase Free project (region near India) + note reference â€” COMPLETED
- [x] OPERATOR: run `alembic upgrade head` against the NEW Supabase DB (head `e1f2a3b4c5d6`) â€” COMPLETED
- [x] OPERATOR: create Render Free web service from `render.yaml` / Dockerfile â€” COMPLETED
- [x] OPERATOR: set Render env vars (DATABASE_URI, new JWT_SECRET_KEY, CORS, APP_ENV=production) â€” COMPLETED
- [x] OPERATOR: verify `GET https://<service>.onrender.com/health` â†’ 200 â€” COMPLETED
- [x] OPERATOR: create Vercel Hobby project (root `frontend/`), set `NEXT_PUBLIC_API_URL` to real Render URL â€” COMPLETED
- [x] OPERATOR: update Render `BACKEND_CORS_ORIGINS` to exact Vercel URL; restart Render â€” COMPLETED
- [x] OPERATOR: minimal connectivity verification (health 200, invalid-login 401, no localhost fallback) â€” COMPLETED

#### 21D.2 â€” Production Auth Discrepancy Audit (COMPLETE, read-only, 2026-08-25)

- [x] Traced full auth flow (login endpoint, security.py PBKDF2, deps, user model)
- [x] Verified dev DB read-only: 1 user (owner, ADMIN, PBKDF2 hash) â€” localhost succeeds
- [x] Audited migration scripts (migrate_extract/execute â€” no password hash transfer; set_initial_password, provision_admin)
- [x] Verified no Alembic migration seeds user rows
- [x] Verified 21D.2 runbook: production init = schema only ("No application data")
- [x] Determined production Supabase has ZERO user rows â†’ login returns 401 (anti-enumeration)
- [x] Confirmed same auth code both environments â€” not a code defect; data-state gap
- [x] Fix plan documented (Approach A: direct copy w/ hash preservation; supersedes earlier registration sketch) â€” NOT implemented
- [x] `docs/phase_21/phase_21d2_auth_discrepancy_audit.md` created
- [x] Zero mutations; no production DB accessed; no account/data/auth logic changed
- [x] OPERATOR: confirm Render log shows "roll_number not found or no password set" branch â€” RESOLVED (operator verified production 401; root cause = zero user rows)
- [x] OPERATOR/AUTH: authorize fix plan (Approach A direct migration) â€” RESOLVED (migration executed in 21D.3)
- HARD STOP â€” 21D.2 audit complete; migration executed in 21D.3; no commit made.

#### 21D.2 â€” Full Localhostâ†’Production Migration Audit (COMPLETE, read-only, 2026-08-26)

- [x] Enumerated all 18 application tables (models + migrations)
- [x] Captured localhost row counts + owner-specific counts (read-only)
- [x] Mapped all FK relationships + unique constraints (dependency graph)
- [x] Verified academic baseline state (session, semester, section, subjects, sessions, events, quiz, timetable)
- [x] Confirmed production has zero application rows (prior audit; row-level inspection NOT performed â€” no repo credentials)
- [x] Determined UUID preservation is safe (production empty â†’ no conflicts, no remap)
- [x] Determined PBKDF2 password hash is portable â†’ **Approach A** recommended (direct copy; password stays valid)
- [x] Compared Approach A vs B (direct copy vs registration+remap) â€” A is safer for exact equivalence
- [x] Assessed existing tooling (seeders regenerate; migrate_* is Firebase-era; new dedicated tool planned)
- [x] Defined 18-table dependency order + idempotency (`ON CONFLICT DO NOTHING`)
- [x] Defined validation plan (counts, identity, role, login, attendance breakdown, dashboard)
- [x] Defined rollback strategy (TRUNCATE reverse order; localhost untouched)
- [x] `docs/phase_21/phase_21d2_full_state_migration_audit.md` created
- [x] Zero mutations; no production DB accessed; no app logic changed
- [x] OPERATOR/AUTH: authorize creation of `migrate_localhost_to_supabase.py` + execution â€” RESOLVED (created + executed in 21D.3)
- HARD STOP â€” 21D.2 audit complete; migration executed in 21D.3; no commit made.

#### 21D.3 â€” Controlled Localhostâ†’Supabase Production Migration (COMPLETE, 2026-08-26)

- [x] Created `backend/scripts/migrate_localhost_to_supabase.py` (299 lines, `--verify-only`/`--execute`)
- [x] Tool design: single transaction; no ON CONFLICT DO NOTHING; UUID/hash/timestamp preservation; read-only source
- [x] Tool compile PASS
- [x] FK order validated against actual schema (parents before children â€” VALID)
- [x] Source snapshot matches 21D.2 audit (all 18 tables; owner 2401220100027 ADMIN hash present; attendance 165 108/57; alembic e1f2a3b4c5d6)
- [x] Localhost backup created (88 KB)
- [x] `docs/phase_21/phase_21d3_production_migration_report.md` created
- [x] OPERATOR: run `python scripts/migrate_localhost_to_supabase.py --verify-only` (confirm 18 empty tables) â€” COMPLETED
- [x] OPERATOR: run `python scripts/migrate_localhost_to_supabase.py --execute` â€” COMPLETED
- [x] OPERATOR: manual production login test (2401220100027) at https://attendance-dash-pro.vercel.app â€” COMPLETED (login works; ADMIN; dashboard; desktop; mobile; PWA verified)
- [x] Post-run: reconcile counts/UUID/content verification â€” COMPLETED (18 tables, counts/UUID/content/FK all match; ADMIN identity/UUID/PBKDF2 hash preserved; 165 attendance 108/57; academic state preserved)
- HARD STOP â€” 21D.3 COMPLETE; 21D.4 closure next; no commit made.

#### 21D.4 â€” Production Closure & Governance Reconciliation (COMPLETE, 2026-08-26)

Status: **COMPLETE** â€” Phase 21 closed & frozen; Phase 22 activated.

- [x] `docs/phase_21/phase_21d4_production_closure.md` created
- [x] Phase status reconciled: 21D.2 provisioning COMPLETE Â· 21D.3 migration COMPLETE Â· production validation COMPLETE Â· Phase 21 COMPLETE & FROZEN
- [x] Production architecture recorded (Vercel frontend + Render backend + Supabase PostgreSQL)
- [x] Production verification recorded (login Â· ADMIN Â· dashboard Â· desktop Â· mobile Â· PWA â€” operator-performed)
- [x] Migration verification recorded (18 tables Â· counts Â· UUID equality Â· content equality Â· FK integrity Â· attendance 165 108/57 Â· academic state)
- [x] Existing-account preservation recorded (ADMIN identity Â· UUID Â· PBKDF2 hash Â· attendance state)
- [x] Launch gates recorded RESOLVED (A browser QA Â· B QA-window data Â· C infrastructure)
- [x] Known beta operational limitations documented (Supabase Free no auto backups; Render cold-start/keep-warm) â€” not launch failures
- [x] Phase 21 closure stated (complete & frozen based on verified evidence)
- [x] Phase 22 transition stated (next project phase)
- [x] Governance synchronized (roadmap, plan, task, walkthrough); no contradictory BLOCKED status remains in active/current sections
- [x] No application code, database, Supabase/Render/Vercel config, auth logic, or API contracts changed; no migration; no browser/PWA tests; no commit/push
- HARD STOP — Phase 21 COMPLETE & FROZEN; Phase 22 next; no commit made.

### Phase 22 — Post-Launch (ACTIVE — next project phase, 2026-08-26)

Phase 21 production launch is **COMPLETE & FROZEN**. The production system is
live on Vercel Hobby + Render Free + Supabase Free PostgreSQL, verified by the
operator (login, ADMIN, dashboard, desktop, mobile, PWA, migrated data).

Phase 22 is the **next active phase**. Phase 22 work is NOT implemented in
this closure slice — only the authoritative starting point is established.

- [x] Phase 22.0 — read-only audit + prioritization (no implementation)
- [ ] Monitor errors, collect feedback, production bug fixes, semester rollover

#### Phase 22.1 — Timetable Data-Scope Correction (COMPLETE — implementation; production migration pending operator)

Status: **COMPLETE** (implementation + local verification, 2026-08-26). The
P0 defect (timetable query ignored section_id; no Section linkage on
TimetableEntry) is fixed. Production migration is a separate operator step.

- [x] Governance review (roadmap, plan, task, walkthrough, Phase 22.0 audit)
- [x] Readiness inspection of all TimetableEntry consumers (model, seed, expand, synchronizer, attendance joins, verifiers)
- [x] Model: TimetableEntry.section_id FK -> sections.id + Section relationship (NOT NULL after migration)
- [x] Migration f2e3d4c5b6a7: add column + FK, backfill from existing DB state (no hardcoded UUID, no new Section), guarded NOT NULL, downgrade drops column
- [x] Migration SQL validated offline (upgrade head --sql / downgrade --sql, exit 0)
- [x] Dev DB migration applied + backfill verified (28 rows, 0 NULL)
- [x] Dev DB downgrade -> upgrade round-trip verified (28 rows preserved)
- [x] Repository: get_weekly_entries_for_section filters by section_id
- [x] Seed pipeline: seed_academic_baseline.py resolves/creates the section (CSE-51, idempotent) and assigns section_id
- [x] API contract: response shape unchanged; section_id not serialized
- [x] Synchronizer: no change required (additive column; verified via joins)
- [x] Verifier backend/scripts/verify_phase_22_1.py created — 19/19 PASS on dev DB
- [x] Static: compileall PASS · git diff --check PASS · no browser/PWA tests
- [x] Alembic driver blocker (operator's `alembic upgrade head` failed: `ModuleNotFoundError: No module named 'psycopg2'`) — RESOLVED in `backend/alembic/env.py`: bare `postgresql://`/`postgres://` scheme normalized to `postgresql+asyncpg://` (asyncpg is the project's installed async driver; no .env change, no extra driver). Verified against localhost dev DB with the bare URL form: `alembic current` → `f2e3d4c5b6a7 (head)`.
- [x] OPERATOR: retry `alembic upgrade head` (revision f2e3d4c5b6a7) on production Supabase (1 section, 28 entries backfilled) — COMPLETED AND VERIFIED (2026-08-26, read-only: head f2e3d4c5b6a7, 28 rows, 0 NULL, 1 section CSE-51, UUID/core parity with dev, 0 duplicates)
- HARD STOP — Phase 22.1 COMPLETE & VERIFIED IN PRODUCTION; Phase 22.2 not started; no commit made.

#### Phase 22.2 — Production Parity & Mutation Reliability (COMPLETE, 2026-08-26)

Status: **COMPLETE** — production-parity audit + confirmed fixes. Trigger:
operator-reported "event created on localhost didn't appear in deployed app"
and "event creation from deployed app fails with 'Failed to fetch'".

- [x] Governance review (roadmap, plan, task, walkthrough, Phase 21/22 docs)
- [x] Event mutation path traced (frontend EventFormDialog → apiFetch → POST /api/v1/events → EventService → registry → synchronizer → repo)
- [x] Deployed production stack probed (read-only): backend /health 200 · CORS preflight + actual responses correct for the exact Vercel origin · deployed bundles carry correct API URL (no localhost fallback) · deployed OpenAPI has current event endpoints/HOLIDAY/note · dev-secret JWT correctly rejected 401
- [x] Production Supabase inspected (read-only): operator's "localhost-created" Holiday event (Eid-e-Milad) IS in production DB — because backend/.env points DATABASE_URI at the production pooler (localhost writes to production; no sync defect; no sync built)
- [x] All 18 mutation endpoints audited (matrix): login/register were the ONLY raw-fetch/localhost-fallback paths; all others use guarded apiFetch
- [x] FIX: api.ts — export API_BASE_URL; translate network-level "Failed to fetch" to an actionable message (cause preserved); HTTP-error details unchanged
- [x] FIX: login/page.tsx — use guarded API_BASE_URL (removes NEXT_PUBLIC_API_URL || localhost fallback); network-error translation
- [x] FIX: signup/page.tsx — same
- [x] FIX: events/page.tsx — deactivation alert uses translated message
- [x] FIX: ErrorState.tsx — removed dev-era copy
- [x] Verification: tsc --noEmit PASS · git diff --check PASS · no backend/schema/DB/production config changed
- [ ] OPERATOR (deferred): decide on local .env → production pooler targeting; verify deployed-app event creation from a fresh browser session (clear cache) and report the result
- HARD STOP — Phase 22.2 COMPLETE; no commit made; Phase 22.3 not started.

#### Phase 22.3 — Student Elective Selection & Timetable Resolution (COMPLETE — implementation; production migration pending operator)

Status: **COMPLETE** (implementation + local verification, 2026-08-26). The
production migration (revision `a3b4c5d6e7f8`) is a separate operator step.

- [x] Governance review (roadmap, plan, task, walkthrough, Phase 22.0 audit)
- [x] Step 0 read-only audit: 15 audit questions answered from repo evidence (no elective representation; enrollments cannot represent choices; timetable uses concrete BCS-054/BCS-058 slots; ClassSession has concrete subject_id; migration IS necessary; existing admin has no choices)
- [x] Model: ElectiveSlot enum + TimetableEntry.elective_slot + StudentElectiveChoice table (UNIQUE user+slot)
- [x] Migration `a3b4c5d6e7f8`: elective_slot column + backfill from tags · student_elective_choices table · insert BCS-052/053/055/056 subjects · downgrade drops all
- [x] Migration validated: offline SQL generation PASS · dev DB applied + backfill (8 slots, 6 elective subjects) · downgrade → upgrade round-trip PASS
- [x] Registration: RegisterRequest requires elective_i / elective_ii (validated vs CTT options); enrolls non-elective subjects + chosen electives only; creates StudentElectiveChoice rows
- [x] Timetable endpoint: resolves elective slots to the student's selection (anchor if no choice)
- [x] Attendance read paths (6 queries): elective slot sessions resolve to the student's chosen subject via coalesced effective-subject join
- [x] Attendance mutation: record_attendance resolves effective subject for enrollment check on elective slots
- [x] Seed pipeline: timetable.json full elective catalog + seed sets elective_slot from tag
- [x] Signup UI: Department Elective-I / Elective-II selectors (CTT options)
- [x] Verification: py_compile PASS · tsc --noEmit PASS · verify_phase_22_3.py 16/16 PASS (dev DB, rolled-back txn) · git diff --check PASS · no attendance/eligibility/calendar engine changed
- [ ] OPERATOR: apply `alembic upgrade head` (revision `a3b4c5d6e7f8`) to production Supabase (adds elective_slot + student_elective_choices + 4 elective subjects) — NOT YET DONE
- HARD STOP — Phase 22.3 implementation COMPLETE; production migration is the operator's action; no commit made.

#### Phase 22.4 — Departmental Elective Resolution Across All Engines & Surfaces (COMPLETE — implementation; production migration pending operator)

Status: **COMPLETE** (implementation + local verification, 2026-08-26). The
production migration (revision `b7c8d9e0f1a2`) is a separate operator step.

- [x] Read-only audit: Phase 22.3 solved slot enum/choice/timetable/attendance; gaps = quiz schedules (no slot marking), academic events (no slot marking; skipped for non-anchor-enrolled students), event-created sessions (extras/quiz-day), ADMIN slot-event creation, single authoritative resolver
- [x] Data classification: quiz_schedules BCS-054×3→EI, BCS-058×3→EII; all 14 BCS-054/058 events → slot events; all BCS-054/058 sessions slot-marked — dates/cycles/sessions preserved
- [x] Authoritative resolver: `app/services/elective_resolver.py` (catalog constants + ElectiveResolver; no fabrication; missing choice → shared anchor)
- [x] Models: `QuizSchedule.elective_slot`, `AcademicEvent.elective_slot`, `ClassSession.elective_slot` (nullable)
- [x] Migration `b7c8d9e0f1a2`: 3 columns + tag-based backfill; downgrade drops columns; round-trip PASS on dev DB
- [x] Quiz: slot-aware `get_effective_quiz_dates_for_subjects` (one query, elective scope); EligibilityService single/batch/current-cycle resolve chosen electives to slot dates; existing dates/cycles unchanged
- [x] Events backend: create/update accept `elective_slot` (ADMIN-only, mutually exclusive with subject_id, lab types rejected); service stores shared anchor; registry extended; synchronizer slot-marks extra/quiz-day sessions
- [x] Events/calendar reads: list/create/update/deactivate + calendar month/day resolve `resolved_subject_*` per user
- [x] Attendance: `_elective_choice_on`/`_resolved_subject_match` → COALESCE(timetable, class_session).elective_slot; record_attendance resolves session marker; formulas frozen
- [x] Dashboard/notifications: upcoming events + academic-event notifications include slot events resolved per student; quiz snapshot resolves chosen electives
- [x] Frontend: `types/api.ts` ElectiveSlot + elective_slot + resolved_subject_*; EventFormDialog admin slot options; EventRow + DayDetail resolved-subject display
- [x] Seeds: seed_academic_events.py + materialize_quiz_day_sessions.py carry quiz_schedules.elective_slot
- [x] Verification: py_compile PASS · tsc --noEmit PASS · alembic offline SQL PASS · dev DB migration + backfill PASS · downgrade→upgrade round-trip PASS · verify_phase_22_4.py 71/71 PASS · git diff --check PASS · no attendance/eligibility/calendar formula changed
- [ ] OPERATOR: apply `alembic upgrade head` (revision `b7c8d9e0f1a2`) to production Supabase AFTER Phase 22.3 (`a3b4c5d6e7f8`) — NOT YET DONE
- HARD STOP — Phase 22.4 implementation COMPLETE; production migration is the operator's action; no commit made.

---

## PHASE 23.0 - ARCHITECTURE DISCOVERY & IMPLEMENTATION BLUEPRINT (RECONCILED)

Status: **COMPLETE - DISCOVERY PHASE + BLUEPRINT RECONCILIATION (2026-08-27) - READ-ONLY.** No code, no schema, no migration, no seed, no UI, no auth, no production data touched. No commit, no push, no PR. Authoritative report: `docs/phase_23/phase_23_0_architecture_discovery.md`.

## Objective

Eliminate architectural ambiguity BEFORE implementation. The system must evolve from its current single-section model to the real academic structure - the **TARGET** hierarchy Branch -> Semester -> Section (<=60) -> Subsection (~30) - with the full B.Tech CSE elective catalog, subsection-variable timetables, per-cohort outcomes/overrides, and the eventual Admin Portal as the authoritative control plane. **Branch parentage is a 23.1 DECISION GATE, NOT finalized** - the CURRENT model is AcademicSession -> Semester -> Section(program), with no Branch entity.

## Reconciliation (10 corrections applied, 2026-08-27)

The core findings were accepted. Ten corrections were applied to the blueprint. Key constraints:

- **23.1 is schema/data-model foundation ONLY** - no admin-authorization schema (23.9), no consumer wiring (timetable/synchronizer/attendance/Track/History/Dashboard/quiz/events/registration/UI/admin auth).
- Each schema-changing phase ships its own operator-bound migration lifecycle. 23.10 is final reconciliation/closure, NOT the first production migration point.
- Three-layer model: EXPECTED TIMETABLE -> CLASS SESSION/OCCURRENCE -> COHORT/SUBJECT-SPECIFIC OUTCOME OR OVERRIDE. `occurrence_outcomes` is a candidate (NOT finalized until 23.4).
- No `CLASS` event scope. Scope enumeration deferred until 23.1 defines semantics.
- Branch parentage is UNRESOLVED (CURRENT: `Section.program` string only; AcademicSession -> Semester -> Section(program)). A 23.1 DECISION GATE - TARGET/FKs NOT finalized.
- `AcademicSession` / Academic Year (Correction 6): repository evidence strongly establishes `AcademicSession` as the existing academic-year/session entity (`name`, start/end, is_active), `Semester.session_id` referencing it. No second entity proposed. 23.1 must confirm; absent contradictory evidence it remains canonical.
- `student_enrollments` uniqueness is a 23.1 gate. No blind constraint.
- Legacy unknown state preserved. No fabrication; no automatic subsection creation/assignment; `subsection_id` stays NULL (UNKNOWN/UNASSIGNED).
- Subsection examples (CS-5A -> 51/52) are conceptual only.

## Delivered (discovery only - no implementation)

- [x] Read-only repository audit: models, alembic chain (head `b7c8d9e0f1a2`), services, engines, repositories, endpoints, frontend, PWA, seed scripts, governance docs
- [x] Established the critical three-layer model: EXPECTED TIMETABLE -> CLASS SESSION/OCCURRENCE -> COHORT/SUBJECT-SPECIFIC OUTCOME OR OVERRIDE - the last is NOT representable today (report section 25)
- [x] Catalogued every single-semester/section/subsection/elective/scheduling/quiz-event assumption (report sections 14-18)
- [x] Engine-by-engine impact matrix across 21 surfaces (report section 19)
- [x] Recommended additive, migration-safe database model, reconciled per corrections (report section 21)
- [x] Recommended authorization model (HEAD/SECTION/SUBSECTION/ELECTIVE admin; report section 22 - 23.9 scope)
- [x] Recommended student-context read model (report section 23 - 23.2 scope)
- [x] Recommended timetable/occurrence/outcome/event/quiz/attendance models (report sections 24-28)
- [x] Recommended Admin Portal + Student App boundaries (report sections 29-30)
- [x] Migration + production safety strategy, per-phase migration lifecycle (report sections 31-32)
- [x] Reconciled Phase 23.x breakdown (23.1 schema-only -> 23.10 closure) + dependency graph (report sections 33-34)
- [x] Risks, open questions (incl. 4 gates), explicit non-goals, final recommendation (report sections 35-38)
- [x] Correction matrix (report section 0) documenting all 10 corrections

## Not in this phase (HARD STOP)

- No Phase 23.1 implementation (no code, no migration, no schema change)
- No new quiz dates invented; no quiz-cycle redesign
- No Admin Portal UI
- No self-service elective change; no student-facing "Departmental Elective-I/II" labels
- No per-student schedule/occurrence duplication; no engine formula changes
- No destructive migration; no production access/mutation
- No commit, no push, no PR

## Validation

- Repository inspection only; zero application/schema/seed/frontend files modified
- DB baseline untouched; git working tree clean before and after
- New files: `docs/phase_23/phase_23_0_architecture_discovery.md` (authoritative report, incl. section 0 correction matrix)
- Governance: this file, MASTER_ROADMAP.md, implementation_plan.md, walkthrough.md - Phase 23.0 recorded as discovery + reconciliation (no future phase marked COMPLETE)

## Do Not Touch Again

- All frozen phases 0-22 (engines, contracts, verifiers, baselines)
- Phase 22.3/22.4 elective resolution semantics (until Phase 23.5 re-bases the catalog onto DB config)
- Phase 23.0 discovery report + correction matrix is authoritative for Phase 23.1+ execution prompts

---

## PHASE 23.1 � ACADEMIC HIERARCHY & ENROLLMENT SCHEMA FOUNDATION (COMPLETE, 2026-08-27)

Status: **COMPLETE � schema/data-model foundation only.** Migration `c8d9e0f1a2b3`. No consumer/engine/registration/UI/admin wiring. No commit, no push, no PR.

## Objective

Establish the minimum correct database/domain foundation required for later Phase 23 work: `subsections` entity, nullable `users.subsection_id`, `sections` composite-unique name, `student_enrollments` uniqueness constraint. Resolve the four decision gates (AcademicSession, Branch parentage, enrollment uniqueness, subsection semantics) from repository evidence. Schema/data-model foundation ONLY � no behavioral wiring.

## Delivered

- [x] Decision gate: AcademicSession = academic-year entity � **CONFIRMED** (name "2026-27", start/end, is_active; `Semester.session_id` FK). No second entity.
- [x] Decision gate: Branch parentage � **REMAINS UNRESOLVED** (no Branch entity; `Section.program` string only). No `branches` table created. Gate preserved.
- [x] Decision gate: Section/program semantics � **CONFIRMED** (preserved; names now unique per semester, not globally).
- [x] Decision gate: Enrollment uniqueness � **CONFIRMED** `UNIQUE(user_id, subject_id)` (subject_id is semester-scoped, so multi-semester history coexists).
- [x] Decision gate: Subsection semantics � **CONFIRMED NULL-preserving** (no fabrication, no auto-assignment; `subsection_id` NULL = UNKNOWN/UNASSIGNED).
- [x] `Subsection` model + `subsections` table (id, name, section_id FK, max_strength nullable, `UNIQUE(section_id, name)`) � no rows created.
- [x] `users.subsection_id` (nullable FK, no backfill)
- [x] `sections.name` global-unique ? composite `UNIQUE(semester_id, name)` (guarded)
- [x] `student_enrollments` `UNIQUE(user_id, subject_id)` (guarded)
- [x] Migration `c8d9e0f1a2b3` (chain: `b7c8d9e0f1a2` ? `c8d9e0f1a2b3`); offline SQL upgrade/downgrade verified
- [x] Governance documents updated (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)

## Not in this phase (HARD STOP � 23.1 boundary)

- [ ] NO `timetable_entries.subsection_id` / `class_sessions.subsection_id` (23.3)
- [ ] NO occurrence/outcome model / event-scope enum (23.4/23.7)
- [ ] NO `admin_scopes` / SECTION_ADMIN role (23.9)
- [ ] NO Branch entity (gate preserved)
- [ ] NO AcademicSession duplicate
- [ ] NO subsection fabrication/backfill
- [ ] NO attendance/timetable/registration/frontend/auth behavior changes
- [ ] NO production rollout
- [ ] NO commit, no push, no PR

## Validation

- `compileall` PASS (backend/app + migration)
- `alembic heads` ? single head `c8d9e0f1a2b3`
- Offline `upgrade head --sql` + `downgrade` SQL PASS (correct DDL, guarded constraints)
- Model imports PASS (Subsection, Section, User, StudentEnrollment all load correctly)
- Migration `c8d9e0f1a2b3` NOT applied to any DB by the agent (backend/.env -> production Supabase pooler; Docker daemon down); dev-DB application is an OPERATOR action; production DB NOT touched
- Git: clean working tree; no commit, no push, no PR

## Do Not Touch Again

- Phase 23.1 schema foundation is complete. Do not reopen for behavioral wiring.
- Phase 23.0 discovery report + correction matrix is authoritative for Phase 23.2+ execution prompts.

---

## PHASE 23.2 � CURRICULUM MODEL DISCOVERY (COMPLETE � READ-ONLY, 2026-08-27)

Status: **DISCOVERY COMPLETE � READ-ONLY.** No code, no schema, no migration, no seed, no frontend, no auth, no database changes. No commit, no push, no PR. Authoritative report: `docs/phase_23/phase_23_2_curriculum_discovery.md`.

> **Note (governance reconciliation):** per operator directive 2026-08-27, Phase
> 23.2 is scoped to the **curriculum/subject model**. This supersedes the earlier
> Phase 23.0 blueprint label "23.2 � Student academic context" (that work is
> re-scoped as later Phase 23 work). The authoritative Phase 23 sequence is
> otherwise unchanged.

## Objective

Establish the authoritative curriculum/subject model required for the later Phase 23 architecture � before any implementation is authorized.

## Delivered (discovery only � no implementation)

- [x] Read-only audit of Subject model (columns, types, FKs, relationships, indexes, constraints, enums)
- [x] Subject type audit: `SubjectCategory` = THEORY/LAB only; no NON_CREDIT/ELECTIVE/CORE values
- [x] Elective model audit: catalog hardcoded in `elective_resolver.py`; duplicated in `subjects.tag` + `elective_slot` markers
- [x] Semester/curriculum relationship audit: Subject tied to exactly one semester; curriculum is semester-level (not section-level)
- [x] Student enrollment audit: `UNIQUE(user_id, subject_id)` confirmed correct (Phase 23.1); subject_id is semester-scoped
- [x] Subject consumer dependency map (timetable, class sessions, attendance, quiz, events, lab, notifications, dashboard, analytics, calendar, registration, resolver, seeds)
- [x] Historical data analysis: old sessions/attendance/quiz/events preserved; no curriculum versioning; no cross-semester subject identity
- [x] CTT cross-check: 13/13 subjects present; minor name discrepancies (BCS-501 "System" vs "Systems", BCS-503 "Algorithm" vs "Algorithms"); no non-credit distinction for BNC-501
- [x] All 18 hard questions answered (report section J)
- [x] Governance docs updated: MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md

## Key findings

1. `Subject.code` is indexed but NOT unique. `UNIQUE(code, semester_id)` is missing � accidental duplicate insertion within a semester is possible (seed-script guard only).
2. Elective catalog is duplicated across code constants, `subjects.tag`, and `elective_slot` markers � they agree today but could diverge (Phase 23.5 concern).
3. No non-credit distinction: BNC-501 (non-credit in CTT) is identical to every other theory subject.
4. `get_by_code(code)` returns the first match regardless of semester � latent defect that activates with multi-semester data.
5. Historical data safety is largely provided by the current schema (permanent FK chains), but no curriculum versioning / cross-semester subject identity exists.

## Not in this phase (HARD STOP)

- [ ] NO implementation of `UNIQUE(code, semester_id)` (pending authorization)
- [ ] NO `elective_catalog` config table (Phase 23.5)
- [ ] NO non-credit flag for BNC-501 (requires operator decision)
- [ ] NO changes to Subject model, SubjectCategory enum, tags, flags, or consumers
- [ ] NO frontend/auth/database/production changes
- [ ] NO commit, no push, no PR

## Validation

- Read-only repository inspection only; zero application/schema/seed/frontend files modified
- DB untouched; git working tree clean before and after
- New file: `docs/phase_23/phase_23_2_curriculum_discovery.md`
- Governance: this file, MASTER_ROADMAP.md, implementation_plan.md, walkthrough.md � Phase 23.2 recorded as discovery only (implementation NOT started; not marked COMPLETE)

## Do Not Touch Again

- Phase 23.2 discovery report is authoritative for the curriculum-model implementation prompt (when authorized)
- Phase 23.0 discovery report + correction matrix remains authoritative for the overall Phase 23 sequence
- All frozen phases 0-22 unchanged

---

## PHASE 23.2 - CURRICULUM MODEL IMPLEMENTATION (COMPLETE, 2026-08-27)

Status: **COMPLETE - schema-hardening change only.** Migration `d0e1f2a3b4c5`. The ONLY authorized schema change implemented: `UNIQUE(code, semester_id)` on `subjects`. No commit, no push, no PR.

## Objective

Implement the single confirmed REQUIRED change from the Phase 23.2 discovery: add `UNIQUE(code, semester_id)` on the Subject model/table, enforced at the DATABASE level. Invariant: a subject code may appear in different semesters, but the same code may not occur twice within the same semester.

## Delivered

- [x] `Subject` model (`app/models/academic.py`) gains `__table_args__` `UniqueConstraint("code", "semester_id", name="uq_subjects_code_semester")`
- [x] Existing `ix_subjects_code` single-column index PRESERVED (independent consumer: `SubjectRepository.get_by_code`)
- [x] Migration `d0e1f2a3b4c5` (parent `c8d9e0f1a2b3`): preflight duplicate check + `CREATE UNIQUE CONSTRAINT uq_subjects_code_semester UNIQUE (code, semester_id)`; downgrade drops it
- [x] Offline `upgrade --sql` + `downgrade` SQL verified (single ALTER each direction)
- [x] `alembic heads` -> single head `d0e1f2a3b4c5`; compileall PASS; frontend tsc PASS (no-op)
- [x] Regression inspection: only `seed_academic_baseline.py` (idempotent per-code) and Phase 22.3 migration (idempotent per-code) create Subjects; neither depends on duplicates; no application code constructs Subject directly
- [x] Governance docs updated (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)

## Not in this phase (HARD SCOPE)

- [ ] NO non-credit flag for BNC-501 (undecided - operator decision)
- [ ] NO elective catalog redesign (Phase 23.5)
- [ ] NO elective resolver redesign
- [ ] NO cross-semester subject identity
- [ ] NO curriculum versioning
- [ ] NO enrollment redesign / attendance / quiz / event / timetable / registration / frontend changes
- [ ] NO production mutation

## Validation

- `compileall` PASS (backend/app + migrations); `alembic heads` -> single head `d0e1f2a3b4c5`
- Offline `upgrade c8d9e0f1a2b3:d0e1f2a3b4c5 --sql` + `downgrade d0e1f2a3b4c5:c8d9e0f1a2b3 --sql` PASS (correct DDL)
- **Migration NOT applied to any DB by the agent** - `backend/.env` -> production Supabase pooler, Docker daemon down (same constraint as Phase 23.1). Operator applies on dev DB; migration's guarded preflight re-checks duplicates at apply time. Production DB NOT touched.
- Preflight duplicate check: not executable against a live DB by the agent; repository evidence (idempotent seed/migration, Phase 17/21D.3 audits) indicates zero duplicates
- Git: clean working tree; no commit, no push, no PR

## Do Not Touch Again

- Phase 23.2 schema hardening is complete. Do not reopen for further curriculum changes.
- Phase 23.2 discovery report + correction matrix remains authoritative for the curriculum context.
- Phase 23.3 (Student Academic Assignment) is COMPLETE (2026-08-28) � see below. Timetable + subsection scheduling (the slice the 23.0 blueprint had labeled "23.3") is re-scoped to later Phase 23 timetable redesign.

## PHASE 23.3 - STUDENT ACADEMIC ASSIGNMENT (COMPLETE, 2026-08-28)

Status: **COMPLETE - consolidation/normalization, NOT a redesign.** Migration `e3f4a5b6c7d8` (parent `d0e1f2a3b4c5`). Makes the student's academic placement / compulsory enrollment / elective selection explicit and authoritative around the existing Phase 22.3/22.4 elective architecture. No commit, no push, no PR.

> **Scope note:** this execution prompt re-scopes Phase 23.3 as Student Academic Assignment. The timetable/subsection-scheduling slice formerly labeled "23.3" is re-scoped to later Phase 23 timetable redesign and DEFERRED.

## Objective

Make the relationship between a student and their academic placement / enrollment / elective choices explicit and authoritative with the minimum additive normalization, without re-opening 23.1/23.2 and without recreating the 22.3/22.4 elective system.

## Delivered

- [x] `app/models/enums.py`: added `EnrollmentType(COMPULSORY, ELECTIVE)`
- [x] `app/models/academic.py`: `StudentEnrollment` gains `enrollment_type` (native enum `enrollmenttype`, default/server_default COMPULSORY)
- [x] Migration `e3f4a5b6c7d8` (parent `d0e1f2a3b4c5`): `CREATE TYPE enrollmenttype` + `ADD COLUMN` (default COMPULSORY) + deterministic backfill (ELECTIVE where a matching `StudentElectiveChoice` for an Elective-I/II subject exists) + `SET NOT NULL`; downgrade reverses
- [x] Registration (`auth.py`): new enrollments tagged COMPULSORY (non-elective) / ELECTIVE (chosen DE-I/DE-II)
- [x] `UserRepository.get_elective_codes(user_id)`: the student's own concrete elective codes per slot (never fabricated/borrowed)
- [x] `/student/me` + `StudentProfile`: additive optional `subsection_name`, `elective_i`, `elective_ii` (backward compatible; no second endpoint)
- [x] Frontend `types/api.ts`: `StudentProfile` additive optional `subsection_name`, `elective_i`, `elective_ii`
- [x] `alembic heads` -> single head `e3f4a5b6c7d8`; compileall PASS; frontend tsc PASS
- [x] Logic-level verification matrix (no DB): catalog separation, cross-slot rejection, concrete->slot mapping, explicit compulsory/elective distinction, slot-not-an-enrollment - ALL PASS
- [x] Governance docs updated (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)

## Not in this phase (HARD SCOPE)

- [ ] NO Phase 23.4 authoritative student-context service
- [ ] NO timetable / session / occurrence / event / quiz / attendance redesign
- [ ] NO admin portal / frontend redesign
- [ ] NO student elective switching, no semester rollover
- [ ] NO elective catalog redesign (Phase 23.5), no `branches` table (Branch gate open)
- [ ] NO subsection / elective fabrication for unassigned legacy users (admin-controlled remediation deferred)
- [ ] NO production mutation

## Validation

- `compileall` (full backend) PASS; `alembic heads` -> single head `e3f4a5b6c7d8`
- Offline `upgrade d0e1f2a3b4c5:e3f4a5b6c7d8 --sql` + `downgrade` SQL PASS (correct DDL + deterministic backfill)
- Frontend `npx tsc --noEmit` PASS
- **Migration NOT applied to any DB by the agent** - `backend/.env` -> production Supabase pooler, Docker daemon down. Operator applies on dev DB; production only when separately authorized. Production DB NOT touched.
- Git: working tree contains 23.3 changes; no commit, no push, no PR

## Do Not Touch Again

- Phase 23.3 assignment consolidation is complete. Do not reopen for further assignment schema changes.
- Phase 22.3/22.4 elective resolver + catalog remain the single authoritative elective system (do not recreate).

## PHASE 23.4 - AUTHORITATIVE STUDENT CONTEXT SERVICE (COMPLETE, 2026-08-28)

Status: **COMPLETE - service-layer consolidation; NO schema/migration change.** Alembic head unchanged (`e3f4a5b6c7d8`). One reusable read-only authority for student academic context (placement / enrollments / elective choices). No commit, no push, no PR.

> Scope note: this execution prompt scopes Phase 23.4 as the authoritative student-context service (the blueprint label for 23.2 was re-scoped earlier; the roadmap's 23.4 is this service layer).

## Objective

Create one reusable backend authority for resolving a student's current academic context so downstream services do not independently reconstruct the `User -> Section -> Semester -> AcademicSession` chain. Migrate only the consumers that genuinely duplicated context resolution; keep every external response contract identical.

## Delivered

- [x] `app/schemas/student_context.py`: `StudentContext` + `ContextSubject` read models (stable service-level representation, not ORM objects)
- [x] `app/services/student_context_service.py`: `StudentContextService` with `get_placement(user)` (4 fixed lookups) + `get_context(user)` (adds exactly 3 queries: enrollments, elective choices, first quiz date) - no N+1
- [x] Consumes the authoritative `StudentElectiveChoice` + `ElectiveResolver` catalog (no second resolver); validates stored elective choices against the catalog (records `inconsistencies`, never repairs)
- [x] `/student/me` migrated to `get_context` (contract unchanged: section_name, subsection_name, program, semester_name, academic_session, semester_start/end, first_quiz_date, elective_i/ii, role)
- [x] Dashboard migrated to `get_placement` (removes inline `Section->Semester` duplication)
- [x] Quiz eligibility endpoint migrated to `get_placement` (removes inline `Section->Semester` duplication; same `today` fallback)
- [x] Calendar migrated to `get_placement` (same semester bounds)
- [x] Analytics migrated to `get_placement` (same semester bounds)
- [x] Attendance History migrated to `get_placement` (same semester bounds)
- [x] Timetable + Registration intentionally NOT migrated (documented: trivial placement / provisioning is a different concern)
- [x] Equivalence verified (code-path: identical chain, NULL handling, fallbacks)
- [x] Backend `compileall` PASS; frontend `npx tsc --noEmit` PASS; alembic head unchanged
- [x] Governance docs updated (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)

## Not in this phase (HARD SCOPE)

- [ ] NO Phase 23.5 elective/catalog redesign
- [ ] NO timetable / session / occurrence / event / quiz / attendance redesign
- [ ] NO admin portal / frontend redesign / new context-fetching endpoint
- [ ] NO schema migration (Phase 23.4 requires none; `e3f4a5b6c7d8` untouched)
- [ ] NO student assignment mutations (no subsection/elective/enrollment creation or repair)
- [ ] NO production mutation

## Validation

- `compileall` (full backend) PASS; alembic head unchanged (`e3f4a5b6c7d8`)
- Frontend `npx tsc --noEmit` PASS (no frontend change)
- Logic-level checks (no DB, temp script removed): three concepts distinct; cross-slot/non-catalog elective detection; Context A/B isolation; bounded query design - ALL PASS
- Failure-state matrix (code review): valid placement / missing subsection / missing elective / invalid elective / missing section / missing enrollment - explicit honest states, no fabrication
- **Production DB not touched.** No migration applied.
- Git: working tree contains 23.4 changes; no commit, no push, no PR

## Do Not Touch Again

- Phase 23.4 context service is the authoritative read-only resolver for the migrated consumers. Do not revert to inline reconstruction.
- Phase 22.3/22.4 elective resolver + catalog remain the single authoritative elective system (the context service consumes them).

## PHASE 23.5 - ELECTIVE/CATALOG REDESIGN (COMPLETE, 2026-08-28)

Status: **COMPLETE - catalog normalized into the database.** Migration `f5a6b7c8d9e0` (parent `e3f4a5b6c7d8`). Offline SQL verified; DB application is an operator action. No commit, no push, no PR.

> Scope note: this execution prompt normalizes the elective catalog into the DB (subjects.elective_slot); the resolver becomes DB-driven. Timetable/session/event/quiz/attendance systems unchanged.

## Objective

Normalize the elective/catalog domain only � make the catalog the authoritative source of what can be selected � without redesigning downstream systems, reopening 23.4, or creating a second elective resolver.

## Delivered

- [x] `app/models/academic.py`: `Subject.elective_slot` (nullable `electiveslot` enum) � the authoritative DB-backed catalog marker
- [x] Migration `f5a6b7c8d9e0` (parent `e3f4a5b6c7d8`): `ADD COLUMN` + deterministic backfill from `tag` ('Elective-I'?ELECTIVE_I, 'Elective-II'?ELECTIVE_II); downgrade `DROP COLUMN`
- [x] `app/services/elective_resolver.py`: DB-driven catalog (`catalog_codes()`, `slot_for_code()`, `validate_selection()` async); removed hardcoded `ELECTIVE_I_CODES`/`ELECTIVE_II_CODES`/`SLOT_CODES`/`ALL_ELECTIVE_CODES` and module-level sync functions; `ANCHOR_CODES` retained (schedule anchors); per-student API unchanged
- [x] Registration (`auth.py`): elective validation moved from Pydantic validators to async endpoint against the DB catalog (422 preserved); enrollment loop uses `subject.elective_slot` (not `tag`)
- [x] `StudentContextService`: elective-choice validation uses async `ElectiveResolver.slot_for_code`
- [x] `SubjectResponse` + frontend `SubjectResponse` type: additive optional `elective_slot`
- [x] `seed_academic_baseline.py`: sets `elective_slot` from tag
- [x] `verify_phase_22_4.py`: catalog section verifies the DB-backed catalog (was the removed constants)
- [x] Backend `compileall` PASS; frontend `npx tsc --noEmit` PASS; alembic single head `f5a6b7c8d9e0`
- [x] Backfill outcome verified: DE-I={BCS-052,053,054}, DE-II={BCS-055,056,058}, disjoint, practicals never elective
- [x] Two-context matrix (A: BCS-054/BCS-058; B: BCS-052/BCS-055): no cross-slot, no leakage
- [x] Governance docs updated (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)

## Not in this phase (HARD SCOPE)

- [ ] NO student elective switching / semester rollover / subsection/elective remediation
- [ ] NO timetable / session / occurrence / event / quiz / attendance redesign
- [ ] NO admin portal / frontend redesign
- [ ] NO `branches` table / BNC-501 non-credit modeling
- [ ] NO production mutation

## Validation

- `compileall` (app + alembic + scripts) PASS; alembic head `f5a6b7c8d9e0` (single head)
- Offline upgrade/downgrade SQL PASS; `ADD COLUMN` + deterministic `UPDATE` backfill; downgrade `DROP COLUMN`
- Frontend `npx tsc --noEmit` PASS
- Logic verification: no stale references to removed constants; backfill outcome deterministic; three catalog concepts distinct
- **Migration NOT applied to any DB by the agent** - production pooler, Docker down. Operator applies on dev DB; production only when separately authorized. Production DB NOT touched.
- Git: working tree contains 23.5 changes; no commit, no push, no PR

## Do Not Touch Again

- Phase 23.5 catalog redesign is complete. Do not reopen.
- `ElectiveResolver` is the single authoritative resolver (DB-driven, never recreated as code constants).

## PHASE 23.6 - ACTUAL OCCURRENCE ARCHITECTURE (COMPLETE, 2026-08-28)

Status: **COMPLETE - per-subject occurrence outcomes.** Migration `f6a7b8c9d0e1` (parent `f5a6b7c8d9e0`). Offline SQL verified; DB application is an operator action. No commit, no push, no PR.

> Scope note: this execution prompt establishes subject-specific occurrence outcomes so one shared elective-slot session can have different effective types per concrete subject (BCS-058?quiz, BCS-055?normal, BCS-056?cancelled) with no leakage.

## Objective

Separate EXPECTED schedule (`timetable_entries`) from ACTUAL occurrence (`class_sessions`) and let one occurrence have different effective types per concrete elective subject - without duplicating infrastructure per student, without a second resolver, without redesigning attendance/eligibility/calendar/quiz.

## Delivered

- [x] `app/models/occurrence.py`: `OccurrenceOutcome` (class_session_id FK, subject_id FK, outcome_type; UNIQUE(session, subject))
- [x] `app/models/enums.py`: `OccurrenceOutcomeType` (EXTRA_LECTURE/EXTRA_TUTORIAL/EXTRA_PRACTICAL/SURPRISE_QUIZ/CANCELLED)
- [x] Migration `f6a7b8c9d0e1` (parent `f5a6b7c8d9e0`): CREATE TYPE + CREATE TABLE + index; downgrade drops all
- [x] `EventSessionSynchronizer` extended (NOT replaced): subject-specific elective events produce `desired_outcomes`; `_reconcile_outcomes` state-based create/update/remove (idempotent)
- [x] `session_repo.py`: `add_outcome` / `delete_outcome`
- [x] `attendance_repo.py`: `_outcome_join_on` + `_apply_outcome_to_row`; outcome LEFT JOIN added to all 6 read/counting queries (student-resolved-subject key)
- [x] `practical_occurrence.py`: outcome-cancelled rows documented in `occurrence_is_cancelled`
- [x] Fallback: no slot session that date -> extra fallback (subject-scoped) / cancellation no-op
- [x] Backend `compileall` PASS; frontend `npx tsc --noEmit` PASS (no frontend change); alembic single head `f6a7b8c9d0e1`
- [x] `_desired_schedule` branch simulations PASS (outcome path / fallback / legacy non-elective)
- [x] Per-subject override logic PASS (A?quiz, B?normal, C?cancelled; no leakage)
- [x] Governance docs updated (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)

## Not in this phase (HARD SCOPE)

- [ ] NO Phase 23.7 event-scope redesign / MODIFIED outcome
- [ ] NO Phase 23.8 quiz architecture integration
- [ ] NO Phase 23.9 attendance-mutation integration (read path only; outcome-cancelled marking rejection deferred)
- [ ] NO Phase 23.10 read-model / 23.11 API-scope / Phase 24 Admin Portal
- [ ] NO attendance/eligibility/calendar/quiz/timetable engine changes
- [ ] NO production mutation

## Validation

- `compileall` (app + alembic + scripts) PASS; alembic head `f6a7b8c9d0e1` (single head)
- Offline upgrade/downgrade SQL PASS
- Frontend `npx tsc --noEmit` PASS (no frontend change)
- Simulations: subject-specific SURPRISE_QUIZ(BCS-058)?outcome; CLASS_CANCELLED(BCS-056)?outcome (anchor kept); fallback extras; non-elective legacy path - PASS
- Per-subject override: A?extra(quiz), B?anchor(normal), C?cancelled - no leakage (per-subject join key)
- Query-build + import checks PASS (no circular imports)
- **Migration NOT applied to any DB by the agent** - production pooler, Docker down. Operator applies on dev DB; production only when separately authorized. Production DB NOT touched.
- Git: working tree contains 23.6 changes; no commit, no push, no PR

## Do Not Touch Again

- Phase 23.6 occurrence architecture is complete. Do not reopen.
- `EventSessionSynchronizer` remains the ONE event?session synchronizer (extended, never duplicated).

## PHASE 23.7 - EVENT-SCOPE REDESIGN + MODIFIED (COMPLETE, 2026-08-28)

Status: **COMPLETE.** Migration `f7a8b9c0d1e2` (parent `f6a7b8c9d0e1`; ALTER TYPE ADD VALUE 'MODIFIED'). Offline SQL verified; DB application is an operator action. No commit, no push, no PR.

> Scope note: this execution prompt adds `EventType.CLASS_MODIFIED` (subject-scoped "class was modified" event) + `OccurrenceOutcomeType.MODIFIED` (outcome on the shared anchor session for the targeted concrete subject). The event-scope redesign formalizes how a subject-scoped event identifies its concrete subject within a shared elective slot. No attendance/eligibility/calendar/quiz engine changes.

## Objective

Represent event scope correctly when an event applies to a concrete subject within a shared elective occurrence, and introduce MODIFIED as an event-scope-level occurrence outcome (deferred from 23.6). Preserve the EVENT ? event scope ? occurrence effect ? attendance identity distinction.

## Delivered

- [x] `app/models/enums.py`: `EventType.CLASS_MODIFIED` + `OccurrenceOutcomeType.MODIFIED`
- [x] Migration `f7a8b9c0d1e2` (parent `f6a7b8c9d0e1`): `ALTER TYPE occurrenceoutcometype ADD VALUE 'MODIFIED'`; downgrade documented no-op (PG cannot remove enum values)
- [x] `event_registry.py`: rule for CLASS_MODIFIED (requires subject + class type L/T/P); CLASS_MODIFIED + elective_slot rejected (subject-scoped only)
- [x] `event_service.py`: CLASS_MODIFIED in STUDENT_CREATABLE_EVENT_TYPES
- [x] `event_session_service.py`: CLASS_MODIFIED ? MODIFIED outcome on anchor session (elective ? slot anchor; non-elective ? subject's own session); no session ? no-op; `_reconcile_outcomes` generalized for non-elective subject anchors
- [x] `attendance_repo.py`: `_apply_outcome_to_row` only sets is_extra for EXTRA_*/SURPRISE_QUIZ; MODIFIED changes no flag
- [x] Frontend `types/api.ts` + `eventRules.ts`: additive CLASS_MODIFIED contract sync
- [x] Backend `compileall` PASS; frontend `npx tsc --noEmit` PASS; alembic single head `f7a8b9c0d1e2`
- [x] In-process simulations: CLASS_MODIFIED elective/non-elective with session ? MODIFIED outcome; no session ? no-op; 23.6 SURPRISE_QUIZ unchanged; EVENT_TO_OUTCOME_TYPE mapping; row flag behavior � ALL PASS
- [x] Governance docs updated (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)

## Not in this phase (HARD SCOPE)

- [ ] NO Phase 23.8 quiz architecture integration
- [ ] NO Phase 23.9 attendance mutation gate
- [ ] NO Phase 23.10 read models / 23.11 API scope / Phase 24 Admin Portal
- [ ] NO attendance/eligibility/calendar/quiz engine changes
- [ ] NO whole-slot "modified" event (subject-scoped only)
- [ ] NO production mutation

## Validation

- `compileall` (app + alembic + scripts) PASS; alembic head `f7a8b9c0d1e2` (single head)
- Offline upgrade SQL PASS (ALTER TYPE ADD VALUE)
- Frontend `npx tsc --noEmit` PASS
- Simulations: CLASS_MODIFIED elective + non-elective ? MODIFIED outcome; no session ? no-op; 23.6 intact; row flag behavior � ALL PASS
- **Migration NOT applied to any DB by the agent** - production pooler, Docker down. Operator applies on dev DB; production only when separately authorized. Production DB NOT touched.
- Git: working tree contains 23.7 changes; no commit, no push, no PR

## Do Not Touch Again

- Phase 23.7 event-scope + MODIFIED is complete. Do not reopen.
- `EventSessionSynchronizer` remains the ONE event?session synchronizer (extended, never duplicated).

## PHASE 23.8 - QUIZ INTEGRATION (MODIFIED + SUBJECT-SCOPED QUIZ REALITY) (COMPLETE, 2026-08-28)

Status: **COMPLETE - MODIFIED is occurrence metadata for the quiz pipeline.** No migration (discovery proved none necessary). Alembic head unchanged (`f7a8b9c0d1e2`). No commit, no push, no PR.

> Scope note: this execution prompt integrated the Phase 23.7 MODIFIED architecture with the quiz pipeline. Discovery proved the quiz pipeline is already outcome-aware (Phase 23.6 read path): a modified class is a conducted class (counted in every denominator); quiz dates/identity/windows/eligibility unchanged; subject isolation via the outcome join key. One genuine defect was fixed (cancellation wins over modification).

## Objective

Keep quiz reality correct when a concrete subject's scheduled occurrence is modified � no quiz rebuild, no eligibility-engine change, no leakage to other subjects, no frontend quiz calculations.

## Delivered

- [x] Discovery: quiz pipeline traced (quiz_schedules projection + QUIZ_DAY-event dates + outcome-aware eligibility counts + elective scope)
- [x] Semantic decision: MODIFIED = occurrence metadata for the quiz pipeline (conducted class; quiz dates/identity/windows/eligibility unchanged)
- [x] Integration fix: `event_session_service.py` CLASS_MODIFIED branch no longer overwrites a CANCELLED desired outcome (cancellation wins over modification)
- [x] `verify_phase_23_8.py` (NEW, DB-based, self-cleaning, operator-run): outcome isolation (BCS-058 vs BCS-055/056), read-path isolation per student, eligibility invariance, no-op without a session, idempotency, CANCELLED-wins, deactivation reversal, attendance safety
- [x] Backend `compileall` PASS; frontend `npx tsc --noEmit` PASS (no frontend change); alembic head unchanged `f7a8b9c0d1e2`
- [x] In-process checks: CANCELLED-wins fix; MODIFIED alone ? MODIFIED; no leakage; MODIFIED counts as conducted; SURPRISE_QUIZ/EXTRA/CANCELLED regression; QUIZ_DAY source uncoupled from outcomes � ALL PASS
- [x] Governance docs updated (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)

## Not in this phase (HARD SCOPE)

- [ ] NO Phase 23.9 attendance mutation gate
- [ ] NO Phase 23.10 read models / 23.11 API scope / Phase 24 Admin Portal
- [ ] NO quiz admin UI / frontend redesign / React quiz calculations
- [ ] NO migration (none required)
- [ ] NO production mutation

## Validation

- `compileall` (app + alembic + scripts) PASS; alembic head `f7a8b9c0d1e2` (single head, no new migration)
- Frontend `npx tsc --noEmit` PASS
- In-process logic checks � ALL PASS (see Delivered)
- `verify_phase_23_8.py` written for the operator to run on the dev DB (self-cleaning)
- **Production DB NOT touched.** No migration applied.
- Git: working tree contains 23.8 changes; no commit, no push, no PR

## Do Not Touch Again

- Phase 23.8 quiz integration is complete. Do not reopen.
- MODIFIED is occurrence metadata; the eligibility engine remains authoritative and unchanged.
- Phase 23.9 (attendance mutation gate) requires a fresh execution prompt.

## PHASE 23.9 - ATTENDANCE MUTATION GATE (COMPLETE / VERIFIED, 2026-08-29)

Status: **COMPLETE / VERIFIED - outcome-aware attendance mutation safety.** No Phase 23.9 migration (discovery proved none necessary). Alembic head `f8a9b0c1d2e3` (the corrective Phase 23.7 migration `f8a9b0c1d2e3` adds `eventtype.CLASS_MODIFIED`; applied to the local dev DB only). **Git state (corrected after independent review):** committed and pushed � commit `d705034` on `main`, up to date with `origin/main`. The Phase 23.8 content (the `event_session_service.py` CANCELLED-wins fix and `verify_phase_23_8.py`) was committed/pushed together with the Phase 23.9 work in the same commit `d705034`; it is Phase 23.8 content, not 23.9 implementation, and history was not rewritten. **Live `verify_phase_23_9.py` PASS 26/26** against `127.0.0.1:55432/attendancedash` (2026-08-29).

> Scope note: this execution prompt hardens the canonical attendance mutation path so attendance records cannot be created/modified in a way that contradicts the canonical session/occurrence outcome. It is NOT a change to attendance mathematics, quiz eligibility, calendar, or event-session synchronization semantics. Phase 23.9 was re-scoped by operator directive from the original blueprint label "Admin authorization foundation" to the attendance mutation gate.

## Objective

Ensure the mutation endpoint (`POST /api/v1/attendance`) respects the canonical occurrence state for the student's RESOLVED concrete subject:
- NORMAL -> mutation allowed
- MODIFIED -> mutation allowed (conducted class)
- CANCELLED -> mutation rejected (409, existing cancelled-session convention)
- elective isolation: a CANCELLED/MODIFIED outcome for BCS-058 never affects BCS-055/BCS-056
- enrollment authorization preserved; backend authoritative; no React authorization

## Discovery findings

- Mutation authority before this phase: session existence (404) -> anchor `session.is_cancelled` (409) -> elective-slot resolution -> enrollment (403) -> future date (400) -> upsert. The per-subject `occurrence_outcomes` row was NOT consulted: if the anchor session was normal but a student's subject had a CANCELLED outcome, mutation was incorrectly allowed. This was the genuine gap.
- Outcome visibility: the canonical `occurrence_outcomes` table is resolved by the read path via `_outcome_join_on(resolved_subject_id)` keyed on `(class_session_id, COALESCE(choice.subject_id, ClassSession.subject_id))`. The mutation path already computes the same `effective_subject_id`, so reusing the same table/key is a direct lookup, NOT a second resolver.
- Session identity: `attendance_record.class_session_id -> class_sessions.id -> outcome` resolved by `(class_session_id, effective_subject_id)` (the established key).
- Historical attendance: unchanged. The invariant "historical attendance is never silently mutated by event synchronization" is preserved; sync never deletes/rewrites records.
- Concurrency/TOCTOU: the outcome check and the insert happen in the same request transaction against the same DB connection; the canonical `uq_user_class_session` unique constraint already guards duplicate rows. No separate locking added (documented limitation).

## Delivered

- [x] `attendance_repo.py`: additive `get_occurrence_outcome_type(class_session_id, subject_id)` - canonical read of `occurrence_outcomes` for the resolved subject
- [x] `attendance_service.py`: Phase 23.9 outcome-aware mutation gate in `record_attendance` (after enrollment 403, before future-date 400): CANCELLED outcome -> 409 "Cannot mark attendance for a cancelled class session" (same convention as the anchor flag)
- [x] `verify_phase_23_9.py` (NEW, DB-based, self-cleaning, operator-run): normal mutation, MODIFIED allowed, CANCELLED rejected, elective isolation (CANCELLED BCS-058 vs BCS-055/056), MODIFIED isolation, duplicate-mutation single record, historical attendance safety, deactivation/reversal, idempotency, authorization regression (401/403/200), attendance safety assertions
- [x] Backend `compileall` PASS; frontend `npx tsc --noEmit` PASS (no frontend change); alembic head unchanged `f7a8b9c0d1e2`
- [x] Governance docs updated (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)

## Not in this phase (HARD SCOPE)

- [ ] NO Phase 23.10 read models / 23.11 API scope / Phase 24 Admin Portal
- [ ] NO attendance UI / history redesign, quiz, calendar, event-registry redesign, event-session architecture redesign
- [ ] NO new roles / notifications / analytics redesign / production deployment / production migration
- [ ] NO migration (none required)
- [ ] NO production mutation

## Validation

- `compileall` (app + scripts) PASS; alembic head `f8a9b0c1d2e3` (single head; corrective Phase 23.7 migration applied locally)
- Frontend `npx tsc --noEmit` PASS (no frontend change)
- In-process import + logic checks PASS (gate branch, elective isolation key, error semantics 409/403/404/400 preserved)
- `verify_phase_23_9.py` **PASS 26/26** against `127.0.0.1:55432/attendancedash` (2026-08-29) � normal / MODIFIED / CANCELLED / elective isolation / MODIFIED isolation / duplicate-single-record / historical attendance safety / deactivation-reversal / idempotency / authorization / attendance safety
- **Production DB NOT touched.** No production migration applied. Local/dev DB mutation limited to verifier fixtures (cleaned by the verifier's finally block).
- Independent review: **PASS (safe to freeze); live DB verifier PASS 26/26.** Non-blocking coverage observations: EXTRA-outcome-allowed and future-date-400 are not explicitly exercised by the verifier (code paths trivially correct / unchanged); the verifier also has a pre-existing `check()` argument-order bug (name/ok swapped) that makes the section-9 admin check always report PASS � the Phase 23.9 gate is independently verified by sections 1-8. No verifier changes made.
- Git (corrected after review): Phase 23.9 work committed + pushed � `d705034` on `main`, up to date with `origin/main`; Phase 23.8 content (CANCELLED-wins fix + `verify_phase_23_8.py`) is inside the same commit.

## Do Not Touch Again

- Phase 23.9 attendance mutation gate is complete. Do not reopen.
- The canonical `occurrence_outcomes` table + `_outcome_join_on` remain the ONE outcome resolution path (mutation and read now share it).

## PHASE 23.10 - STUDENT-FACING READ MODELS (COMPLETE, 2026-08-29)

Status: **COMPLETE.** No migration. Alembic head unchanged (`f8a9b0c1d2e3`). No commit, no push, no PR.

> Scope note: this phase makes the student-facing read layer expose the effective occurrence state consistently, consuming the canonical architecture (StudentContextService + ElectiveResolver + outcome-aware read path). It does NOT create a new resolver/context service, change any attendance/eligibility/calendar mathematics, or start the Admin Portal.

## Objective

Provide the backend a coherent student-specific interpretation of schedule reality so clients can display the effective state (including MODIFIED) without reconstructing it client-side.

## Delivered

- [x] Discovery audit of all student-facing surfaces (/student/me, timetable, subjects, Track, history, calendar, events, quiz schedule, quiz eligibility, dashboard, notifications, analytics) � all confirmed on the canonical architecture
- [x] `attendance_repo.py`: `ClassSession.elective_slot` added to SELECT of `get_sessions_with_status`, `get_daily_sessions`, `_fetch_history_occurrences`
- [x] `schemas/attendance.py`: `outcome_type` + `elective_slot` (additive optional) on `DailySessionResponse` and `AttendanceHistoryItem`
- [x] `attendance_service.py`: pass-through in `get_daily_sessions` and `get_history`
- [x] Frontend `types/api.ts`: `OccurrenceOutcomeType` enum + additive fields on the two session types
- [x] `verify_phase_23_10.py` (NEW, DB-based, self-cleaning): PASS 26/26 (isolation matrix A/B, effective state, CANCELLED/MODIFIED isolation, common/practical, historical attendance safety)
- [x] Backend `compileall` PASS; frontend `npx tsc --noEmit` PASS; alembic head `f8a9b0c1d2e3` (no migration)
- [x] Baseline restored after verifier (users 3, events 62, outcomes 0, records 165)
- [x] Governance docs updated (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)

## Not in this phase (HARD SCOPE)

- [ ] NO Admin Portal (admin hierarchy, admin UI, admin schedule/event editors)
- [ ] NO Phase 23.11 API scope/authorization
- [ ] NO attendance/eligibility/calendar/quiz/timetable mathematics changes
- [ ] NO new resolver/context service (canonical path reused)
- [ ] NO subsection-scoped scheduling (deferred: needs `timetable_entries.subsection_id` decision)
- [ ] NO production mutation

## Validation

- `compileall` PASS; `npx tsc --noEmit` PASS; alembic head `f8a9b0c1d2e3` (single head, no migration)
- `verify_phase_23_10.py` PASS 26/26 against `127.0.0.1:55432/attendancedash` (A?BCS-058, B?BCS-055; outcome_type/elective_slot exposed; CANCELLED/MODIFIED isolation; history effective state; common/practical identical; attendance untouched; baseline restored)
- Pre-existing `check()` argument-order bug noted (one BCS-501 assertion artifact; not a code defect; no verifier changes)
- **Production DB NOT touched.** No migration applied.
- Git: working tree contains 23.10 changes; no commit, no push, no PR

## Do Not Touch Again

- Phase 23.10 read-model layer is complete. Do not reopen.
- The canonical path (StudentContextService + ElectiveResolver + outcome-aware attendance_repo) is the ONE student-facing resolution authority.

## PHASE 23.11 - API SCOPE & AUTHORIZATION (COMPLETE, 2026-08-29)

Status: **COMPLETE - backend-authoritative scoped-admin authorization.** Migration `f9a0b1c2d3e4` (parent `f8a9b0c1d2e3`; `adminrole` enum + `admin_scopes` table). Applied to local dev DB only. No commit, no push, no PR.

> Scope note: this phase establishes the authorization/scope foundation Phase 24 depends on. Role/scope resolved from DB per request (never JWT/body/query/frontend). No Admin Portal UI, no admin management, no attendance/eligibility/calendar/event/occurrence math changes.

## Delivered

- [x] Discovery: full current-state authorization matrix (authn JWT?DB, roles {STUDENT,ADMIN}, admin gates, student surfaces, subsection limitation)
- [x] `AdminRole` enum (HEAD_ADMIN/CLASS_ADMIN/SUBSECTION_ADMIN/ELECTIVE_ADMIN) in `enums.py`
- [x] `AdminScope` model (`admin_scope.py`) + User relationship + models export
- [x] Migration `f9a0b1c2d3e4`: `adminrole` enum + `admin_scopes` table (FKs, role-scope CHECK, active flag)
- [x] `AuthorizationService`: effective_admin_roles (legacy ADMIN?HEAD_ADMIN + active scopes), is_head_admin, can_access_section/subsection/subject, can_mutate_event
- [x] deps.py: `require_head_admin` + `require_class_scope` / `require_subsection_scope` / `require_elective_subject_scope` factories
- [x] laboratory.py + feedback.py admin endpoints: `require_admin` ? `require_head_admin`
- [x] event_service.py admin gates via AuthorizationService (scoped subject check; elective-slot HEAD_ADMIN)
- [x] `verify_phase_23_11.py` (NEW, self-cleaning): PASS 23/23
- [x] Backend `compileall` PASS; alembic single head `f9a0b1c2d3e4`; offline SQL validated; applied local-only
- [x] Baseline restored after verifier (users 3, admin_scopes 0, records 165, events 62)
- [x] Governance docs updated (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)

## Not in this phase (HARD SCOPE)

- [ ] NO Phase 24 Admin Portal (UI, admin hierarchy UI, admin management UI)
- [ ] NO admin-scope provisioning API/UI (Phase 24)
- [ ] NO attendance/eligibility/calendar/event/occurrence math changes
- [ ] NO subsection data fabrication (SUBSECTION_ADMIN conservative/inert)
- [ ] NO production mutation

## Validation

- `compileall` PASS; alembic head `f9a0b1c2d3e4` (single head)
- Offline upgrade/downgrade SQL PASS; applied to `127.0.0.1:55432/attendancedash` only
- `verify_phase_23_11.py` PASS 23/23 (A unauthenticated, O/G HEAD_ADMIN legacy+scope, H/I CLASS_ADMIN, J/K SUBSECTION_ADMIN conservative+FK, L/M ELECTIVE_ADMIN, N inactive revoked, P no client role/scope, S student elective isolation, U attendance unchanged)
- **Production DB NOT touched.** No production migration.
- Git: working tree contains 23.11 changes; no commit, no push, no PR

## Do Not Touch Again

- Phase 23.11 authorization infrastructure is complete. Do not reopen.
- `AuthorizationService` is the ONE backend authorization authority (roles + scopes from DB).

## PHASE 23.12 - MIGRATION GATE (COMPLETE, 2026-08-29)

Status: **COMPLETE - Phase 23 schema/migration safety gate passed.** No new migration. Alembic head unchanged (`f9a0b1c2d3e4`). No commit, no push, no PR.

## Objective

Prove the Phase 23 migration chain is coherent, reproducible, reversible where appropriate, and safe to carry into Phase 24 (Admin Portal).

## Delivered

- [x] Read-only migration discovery: alembic.ini/env.py/all version files/DB/model metadata audited
- [x] Migration graph: 25 migrations, single linear chain, exactly ONE head `f9a0b1c2d3e4`, no branches
- [x] Model-vs-migration-vs-DB drift audit: no unclassified drift (only the documented legacy timestamp-nullable convention; classified B, not silently fixed)
- [x] Phase 23 migration safety audit (8 migrations: upgrade/downgrade symmetry, enum ordering, FKs/CHECK/indexes, backfills, transaction safety)
- [x] Offline SQL: upgrade base->head (617 lines, no unexpected destructive ops); downgrade head->f8a9b0c1d2e3 (dependency-safe order)
- [x] Fresh disposable DB (`attendancedash_migtest`, local container only, dropped after): 25/25 migrations to HEAD; tables/enums/FKs/CHECK/index verified; CHECK+FK rejection semantics proven; downgrade cycle (admin_scopes data intentionally destroyed - documented) + re-upgrade + idempotency (second `upgrade head` = no-op)
- [x] Existing dev DB verified AT HEAD; read-only baseline captured; counts unchanged by verification
- [x] Application compatibility: compileall PASS; app + AuthorizationService import; metadata loads; `verify_phase_23_11.py` re-run PASS 23/23
- [x] Production operator migration procedure documented (NOT executed)
- [x] `verify_phase_23_12.py` (NEW, self-cleaning): PASS 52/52
- [x] Governance docs updated (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)

## Not in this phase (HARD SCOPE)

- [ ] NO production migration/contact/mutation
- [ ] NO new migration files
- [ ] NO migration rewrites (correct migrations untouched)
- [ ] NO Phase 24 Admin Portal work
- [ ] NO engine/service/logic changes

## Validation

- `verify_phase_23_12.py` PASS 52/52 against `127.0.0.1:55432/attendancedash` (local target asserted; fixtures rolled back; counts unchanged; no residue)
- Fresh-DB reproducibility: 25/25 migrations applied; downgrade/rollback cycle + idempotency validated on disposable DB (dropped after)
- `verify_phase_23_11.py` PASS 23/23 (regression)
- `compileall` PASS; alembic single head `f9a0b1c2d3e4`
- **Production DB NOT touched.** No migration created or applied.

## Do Not Touch Again

- The Phase 23 migration chain is validated and frozen. Do not rewrite migrations.
- `verify_phase_23_12.py` is the migration-gate verifier for future schema work.
- Phase 24 (Admin Portal) requires a fresh execution prompt.

---

## PHASE 24.0 - ADMIN PORTAL DISCOVERY & ARCHITECTURE (DISCOVERY COMPLETE, 2026-08-29)

Status: **DISCOVERY COMPLETE - discovery only.** No implementation, no code/schema/
migration/data changes, migration head unchanged (`f9a0b1c2d3e4`). No commit, no push,
no PR during discovery. Implementation sub-phases followed thereafter:
24.1–24.6 COMPLETE (2026-08-29); Phase 24.7 (timetable management) NOT STARTED —
requires a fresh execution prompt.

## Objective

Discovery-only design of the dedicated Admin Portal (master control surface) on top of
the frozen Phase 23 Academic Core and the Phase 23.11 authorization foundation.

## Delivered

- [x] Authoritative discovery report: `docs/phase_24/phase_24_0_admin_portal_discovery.md` (28 sections + evidence appendices)
- [x] A. Frontend architecture audit (routing, layout, auth/session, API client, SWR, UI primitives, modals, PWA, existing admin surfaces)
- [x] B. Phase 23.11 authorization trace end-to-end (AdminRole, AdminScope, AuthorizationService, dependency factories, EventService gate, laboratory/feedback gates, DB constraints)
- [x] C. Backend admin API inventory: all 41 endpoints with method/purpose/auth/scope/portal-safety
- [x] D. Admin capability matrix (44 capabilities x HEAD/CLASS/SUBSECTION/ELECTIVE, each CONFIRMED/PROPOSED/DEFERRED/UNKNOWN)
- [x] E-H. Information architectures: HEAD_ADMIN control surface, CLASS_ADMIN (section-scoped), SUBSECTION_ADMIN (inert boundaries), ELECTIVE_ADMIN (six concrete-subject scopes; BCS-058 vs BCS-055 vs BCS-056 isolation verified against code paths)
- [x] I. Student management architecture (create/edit/move/subsection/electives/deactivation-gate/audit/safety)
- [x] J. Timetable design (current-model sufficiency assessed; deferred fields recorded, none invented)
- [x] K. Elective occurrence control (event-driven outcome design; no direct outcome API; no per-student sessions)
- [x] L/M. Quiz + event management mapping over the frozen engines
- [x] N. API gap analysis (reusable / additive / genuinely new / must-NOT-create)
- [x] O. Data safety & auditability standards (audit-log architecture as a gated decision)
- [x] P/Q. Main-app-vs-portal boundary; desktop-first responsive strategy (no separate admin PWA)
- [x] R. Proposed Phase 24 sequence: 24.1-24.14 with objectives/dependencies/verification/production boundary
- [x] S. Blockers/decision gates: 12 explicit gates recorded (no guesses)
- [x] Migration head verified: 25 revisions, single linear chain, one head `f9a0b1c2d3e4`
- [x] Governance docs updated (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md)

## Not in this phase (HARD SCOPE)

- [ ] NO portal screen/endpoint implementation
- [ ] NO new role/scope/permission/resolver system
- [ ] NO schema migrations, NO fabricated subsection data, NO admin fixtures
- [ ] NO destructive DB operations, NO production contact
- [ ] NO browser/E2E/test-suite runs (lightweight static inspection only)
- [ ] NO commit/push/merge/PR

## Validation

- Read-only repository inspection + route inventory + model/service tracing + migration chain walk
- Static consistency checks (matrix vs authorization code)
- No DB connection required; production untouched

## Do Not Touch Again

- Phase 23 Academic Core (23.0-23.12) is frozen; Phase 23.11 authorization semantics are final
- The event pipeline is the canonical occurrence-control path - no direct session/outcome writes
- Phase 24 implementation requires fresh execution prompts per sub-phase, after decision-gate review

---

## PHASE 24.1 - ADMIN PORTAL IDENTITY + SHELL (COMPLETE, 2026-08-29)

Status: **COMPLETE - local development only.** No migration, no schema change
(head unchanged `f9a0b1c2d3e4`), no production contact. No commit, no push, no PR.

## Objective

Foundational authenticated admin experience on the Phase 23.11 authorization
architecture: admin authentication -> DB-authoritative identity -> roles +
scopes -> authorization-aware shell -> scope-aware navigation. No feature domains.

## Delivered

### Backend (additive)
- [x] `app/schemas/admin.py` (NEW): `AdminIdentity` + `AdminScopeDescriptor` read-only presentation contracts
- [x] `AuthorizationService.get_admin_identity()` (additive method): DB-resolved effective roles + active scope descriptors; existing authorization methods untouched
- [x] `deps.require_any_admin` (additive composable dependency): 403 when no effective admin role; legacy `require_admin` untouched/unused
- [x] `GET /api/v1/admin/me` (`app/api/v1/endpoints/admin.py`, NEW): read-only; 401/403 handled by the dependency chain; no write behavior; no direct DB access from the endpoint
- [x] `api/api.py`: `/admin` router wired (live router; legacy `api/v1/router.py` untouched)

### Frontend (additive)
- [x] `lib/api.ts`: HTTP status preserved on thrown errors (additive; 401 redirect behavior unchanged)
- [x] `types/api.ts`: `AdminIdentity` / `AdminScopeDescriptor`
- [x] `hooks/useApi.ts`: `useAdminMe()` SWR hook
- [x] `(admin)` route group layout: loading / unauthenticated (existing AuthContext redirect) / unauthorized (403) / API-failure (retry) / shell states; no admin content before backend confirmation
- [x] `components/admin/AdminShell.tsx`: dedicated shell reusing tokens, Button/Badge/Avatar/Skeleton, existing logout, existing responsive conventions; no separate mobile architecture
- [x] `/admin` overview page: identity card, scope descriptors, truthful availability (Feedback Review for global admins), planned areas marked unavailable, SUBSECTION_ADMIN inert notice
- [x] Student shell/routes/frozen primitives: UNCHANGED

## Hard scope (respected)
- [x] NO schema change / migration / production interaction
- [x] NO second authorization system, no frontend-only authorization boundary, no localStorage role authority, no JWT-claim trust
- [x] NO hardcoded admin identity; no provisioning UI; no role/scope editing
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)
- [x] NO fabricated subsection semantics; scoped admins not presented as global

## Validation
- `python -m compileall backend/app` PASS; backend app imports cleanly; admin router registered (endpoint `/me`)
- `npx tsc --noEmit` PASS (0 errors); ESLint clean on all changed frontend files
- No browser/E2E/regression runs (operator tests manually, per phase boundary)

## Do Not Touch Again
- Phase 24.1 is the portal foundation; Phase 24.2+ requires a fresh execution prompt
- `/admin/me` + `require_any_admin` are additive Phase 23.11 consumers - extend, never replace, `AuthorizationService`

---

## PHASE 24.2 - HEAD_ADMIN OPERATIONAL DASHBOARD (COMPLETE, 2026-08-29)

Status: **COMPLETE - local development only.** No migration, no schema change
(head unchanged `f9a0b1c2d3e4`), no production contact. No commit, no push, no PR.

## Objective

First real Admin Portal feature domain: an operational overview for the
HEAD_ADMIN only, built on the Phase 23.11 authorization architecture and the
Phase 24.1 portal foundation. No 24.3+ feature domains.

## Delivered

### Backend (additive)
- [x] `app/repositories/admin_dashboard_repo.py` (NEW): bounded read-only COUNT/aggregate queries over the authoritative tables
- [x] `app/services/admin_dashboard_service.py` (NEW): read-model composition + factual data-quality warnings; no attendance/eligibility/elective math re-implemented; quiz dates from active QUIZ_DAY events
- [x] `app/schemas/admin_dashboard.py` (NEW): stable Pydantic contract (academic/curriculum/students/schedule/events/quizzes/attendance/warnings)
- [x] `GET /api/v1/admin/dashboard` (`app/api/v1/endpoints/admin.py`): read-only, `require_head_admin` (STUDENT/scoped -> 403, no elevation), no client scope params
- [x] No direct DB access from the endpoint; no N+1; no caching added

### Frontend (additive)
- [x] `types/api.ts`: `AdminDashboardResponse` + section types
- [x] `hooks/useApi.ts`: `useAdminDashboard()` SWR hook
- [x] `components/admin/dashboard/` (NEW): MetricCard, AdminSectionCard, AdminWarningsCard, AdminEventsCard
- [x] `/admin` page: real HEAD dashboard inside the existing AdminShell (header + identity badges, warnings card, 8-metric grid, six section cards, events card, honest Available now / Planned portal areas, loading/403/error/empty states)
- [x] Scoped admins: honest "global administrators only" card on 403 (never elevated)
- [x] Student shell/routes/frozen primitives: UNCHANGED

## Hard scope (respected)
- [x] NO schema change / migration / production interaction
- [x] NO second authorization system; backend remains the boundary; no client scope params
- [x] NO speculative data model (no subsection/branch/deactivation/audit/room-faculty inventions)
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)
- [x] NO fabricated subsection semantics; NULL subsection labeled UNKNOWN/UNASSIGNED
- [x] NO fake future-domain pages (planned areas are badges with phase labels only)

## Validation
- `python -m compileall backend/app` PASS; new modules import cleanly
- `npx tsc --noEmit` PASS (0 errors); ESLint clean on changed files
- In-process read-only check against the LOCAL dev DB (`localhost:55432/attendancedash`, locality asserted before execution): `get_dashboard()` end-to-end + Pydantic serialization + 18/18 invariants PASS; no writes; script deleted after run
- No browser/E2E/regression runs (operator tests manually, per phase boundary)

## Do Not Touch Again
- Phase 24.2 is the HEAD dashboard foundation; Phase 24.3+ requires a fresh execution prompt
- `AdminDashboardService/Repository` are read-only consumers - never mutate schedule/session/event/quiz state from them

## PHASE 24.3 - STUDENT MANAGEMENT (READ) (COMPLETE, 2026-08-29)

Status: **COMPLETE - local development only.** No migration, no schema change
(head unchanged `f9a0b1c2d3e4`), no production contact. No commit, no push, no PR.

## Objective

First SCOPED Admin Portal feature domain: read-only student list/search/detail
whose visibility follows the acting admin's active Phase 23.11 scopes (HEAD
all, CLASS assigned sections, ELECTIVE choice-roster, SUBSECTION inert-empty).
Authoritative scope per Phase 24.0 report §24 row 24.3: scoped student
list/search/detail via `StudentContextService`. No attendance/analytics
(24.13), no student writes (24.4), no decision-gate resolution.

## Delivered

### Backend (additive)
- [x] `app/schemas/admin_students.py` (NEW): `AdminStudentSummary`, `AdminStudentListResponse`, `AdminStudentEnrollment`, `AdminStudentDetail`
- [x] `app/repositories/admin_student_repo.py` (NEW): bounded, read-only, scope-filtered list/count (q ILIKE roll/name, LIMIT/OFFSET, outer joins; no N+1); `StudentScopeFilter` data class; elective-roster membership check
- [x] `app/services/admin_student_service.py` (NEW): server-side scope resolution from `AuthorizationService` active scopes (DB per request, UNION for multi-scope admins); 404 for out-of-scope detail (no existence leak); detail via `StudentContextService` (single context authority)
- [x] `GET /api/v1/admin/students` (q, page, page_size): `require_any_admin` + scope resolution; no client scope params
- [x] `GET /api/v1/admin/students/{student_id}`: `require_any_admin` + per-student scope check; 404 for out-of-scope/nonexistent
- [x] No direct DB access from the endpoint; no N+1; no caching added

### Frontend (additive, inside existing AdminShell)
- [x] `types/api.ts`: `AdminStudentSummary`, `AdminStudentListResponse`, `AdminStudentParams`, `AdminStudentDetail`, enrollment types
- [x] `hooks/useApi.ts`: `useAdminStudents()`, `useAdminStudentDetail()` SWR hooks
- [x] `app/(admin)/admin/students/page.tsx` (NEW): scoped list + search (submit-driven) + pagination; loading/403/error/empty states
- [x] `app/(admin)/admin/students/[student_id]/page.tsx` (NEW): detail with placement / electives / compulsory / elective-subject cards + data-quality inconsistencies; 404/403/error/loading states
- [x] `components/admin/AdminShell.tsx`: "Students" nav entry (visible to all admins; scope filtering stays server-side)
- [x] `app/(admin)/admin/page.tsx`: Students moved from "Planned portal areas" to "Available now"

## Hard scope (respected)
- [x] NO schema change / migration / production interaction
- [x] NO attendance snapshot (Phase 24.13); detail is academic context only
- [x] NO student writes (Phase 24.4); create/edit/move/subsection/elective changes deferred
- [x] NO client scope parameters; no second authorization system
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)
- [x] NO fabricated subsection semantics; SUBSECTION_ADMIN inert-empty (structural limitation)
- [x] NO fake feature domains; no student-surface changes

## Validation
- [x] `python -m compileall backend/app` PASS; new modules import cleanly
- [x] `npx tsc --noEmit` PASS (0 errors); ESLint clean on changed files
- [x] `verify_phase_24_3.py` (NEW, self-cleaning, locality guard forces+asserts local dev URI) PASS 40/40: 401/403 matrix, HEAD all + search/pagination, HEAD detail + 404, CLASS section-only + out-of-section 404, ELECTIVE roster + exact-subject isolation (BCS-058 vs BCS-055), SUBSECTION inert/empty code path, no client scope params, CLASS+ELECTIVE UNION, counts unchanged after cleanup (users 3, enrollments 35, admin_scopes 0)
- [x] No browser/E2E/regression runs (operator tests manually, per phase boundary)

## PHASE 24.4 - STUDENT MANAGEMENT (WRITE) (COMPLETE, 2026-08-29)

Status: **COMPLETE - local development only.** Schema change + Alembic migration `eb880e108f19_add_user_is_active.py` (`users.is_active`), applied to the local dev DB only; production untouched. Git state: committed + pushed as `84fae06` on `main` (in repository history).

## Objective

Core student record modifications from the admin student detail view: status toggle (active/deactivate), subsection assignment, and elective corrections.

## Delivered

### Backend (additive)
- [x] `AdminStudentService` mutation methods: `set_student_status`, `assign_subsection`, `correct_elective` (transactional single-commit)
- [x] `app/api/v1/endpoints/admin.py` PATCH mutation routes: `/admin/students/{id}/status`, `/admin/students/{id}/subsection`, `/admin/students/{id}/electives` + dropdown helpers `/admin/sections/{id}/subsections`, `/admin/semesters/{id}/electives`
- [x] Migration `eb880e108f19` (additive `users.is_active`, server default true); login gate rejects deactivated accounts (403)

### Frontend (additive)
- [x] `AssignSubsectionDialog`, `CorrectElectiveDialog`, `SetStudentStatusDialog` integrated into the student detail page
- [x] SWR cache invalidation after mutations

## Hard scope (respected)
- [x] NO batch student management / CSV uploads (deferred to a later explicit phase — NOT Phase 24.5)
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)

## Validation
- [x] Migration applied to local dev DB; existing data preserved (additive column with server default)
- [x] Manual/browser testing remains the operator's responsibility

## Do Not Touch Again
- Phase 24.4 student-write surfaces and the `users.is_active` migration gate

## PHASE 24.5 - ACADEMIC STRUCTURE MANAGEMENT (COMPLETE, 2026-08-29, after independent review + correction pass)

Status: **COMPLETE - local development only.** No schema change, NO new migration (alembic single linear head `eb880e108f19` unchanged). Git state: committed + pushed as `5cae6fb` on `main`; the independent-review correction pass is currently uncommitted (no commit made during the correction pass, per operator instruction).

## Objective

Administrative management of Academic Sessions, Semesters, Sections, and Subsections (list/create/patch; no destructive deletes). Batch student management / CSV import is explicitly NOT part of this phase and remains deferred.

## Delivered

### Backend (additive)
- [x] `app/schemas/admin_structure.py` (NEW): session/semester/section/subsection read + create + patch schemas; `SessionActivationResponse`; `RegistrationWarning`
- [x] `app/repositories/admin_structure_repo.py` (NEW): bounded hierarchy queries + duplicate-name guards
- [x] `app/services/admin_structure_service.py` (NEW): single-active-session invariant (409), duplicate 409, invalid dates 400, registration-ambiguity warnings, no destructive deletes
- [x] `app/api/v1/endpoints/admin.py`: 14 additive structure endpoints, ALL `require_head_admin` (401 unauth / 403 non-HEAD)

### Frontend (additive, inside existing AdminShell)
- [x] `types/api.ts` + `hooks/useApi.ts`: structure types + `useAdminSessions()` / `useAdminSemesters()` / `useAdminSections()` / `useAdminSubsectionsStructure()` / `useAdminStructureMutations()`
- [x] `app/(admin)/admin/structure/page.tsx` (NEW): sessions list + activation controls
- [x] `app/(admin)/admin/structure/[session_id]/page.tsx` (NEW): hierarchy view (Semesters > Sections > Subsections) + create dialogs
- [x] `components/admin/AdminShell.tsx`: "Structure" nav entry (globalOnly); `app/(admin)/admin/page.tsx`: moved from "Planned portal areas" to "Available now"

### Correction pass (independent review, 2026-08-29)
- [x] Stray duplicate root `page.tsx` deleted (real `/admin/structure/[session_id]` route intact)
- [x] Undocumented "OPERATOR DECISION Q2" citations replaced with factual "Phase 24.5 documented invariant" language (`admin_structure_service.py`, `admin.py`)
- [x] Structure pages render explicit 403 ("Global administrator required") and API-error-with-retry states (no misleading empty state on failure)
- [x] Trailing whitespace removed; unused `Settings` import removed
- [x] `backend/scripts/verify_phase_24_5.py` (NEW, authoritative verifier)

## Hard scope (respected)
- [x] NO migration/schema change; NO destructive deletes (Gate 7 unresolved)
- [x] NO curriculum/timetable/sessions/quizzes/admin-scope/attendance domains
- [x] NO subsection scheduling (Gate 1); SUBSECTION_ADMIN remains inert
- [x] NO batch/CSV; NO decision gate resolved (all 12 Phase 24.0 gates remain open)
- [x] NO client scope parameters; backend authorization is the only boundary

## Validation
- [x] `verify_phase_24_5.py` (NEW, self-cleaning, hard locality guard forces+asserts `127.0.0.1:55432/attendancedash`) PASS **46/46** (×2 runs, idempotent): 401/403 auth matrix (STUDENT/CLASS/ELECTIVE/SUBSECTION all 403, SUBSECTION scope creation rejected by FK), HEAD reads, session create/duplicate-409/invalid-date-400/activation-409 + deactivate→activate cycle with restoration, semester/section/subsection CRUD + duplicate-409 + validation-422 + invalid-parent-404, PATCH semantics (is_active extra ignored), no client scope elevation, arbitrary-UUID non-bypass, MULTI_SEMESTER warning, all 14 baseline table counts restored after fixture cleanup
- [x] Regression: `verify_phase_24_3.py` PASS 40/40
- [x] `python -m compileall backend/app backend/scripts` PASS; `npx tsc --noEmit` PASS; ESLint (changed files) PASS; `git diff --check` clean; `next build` PASS (with inline production API URL; plain build fails only on the pre-existing Phase 21D.1 `NEXT_PUBLIC_API_URL` guard)
- [x] No browser/E2E run (operator responsibility); production untouched; `.env` unchanged (local dev target)

## Do Not Touch Again
- Phase 24.5 structure endpoints/UI are HEAD_ADMIN-only; the 14 endpoints and the single-active-session invariant are reviewed and frozen behavior
- `verify_phase_24_5.py` is the authoritative Phase 24.5 verifier

## PHASE 24.6 - CURRICULUM & SUBJECT MANAGEMENT (COMPLETE, 2026-08-29)

Status: **COMPLETE - local development only.** No schema change, NO migration (alembic single linear head `eb880e108f19` unchanged). Git state: implemented but NOT committed (no commit made during implementation, per operator instruction).

## Objective

Administrative management of subjects (curriculum): subject CRUD, elective catalog management (`subjects.elective_slot`), and reuse of the existing experiment catalog (laboratory endpoints unchanged). NOT timetable (24.7) or quiz management (24.10).

## Delivered

### Backend (additive)
- [x] `app/schemas/admin_subjects.py` (NEW): admin subject contracts + create/update requests (PATCH rejects `code`/`semester_id`; `elective_slot` explicit-PATCH semantics)
- [x] `app/repositories/admin_subject_repo.py` (NEW): bounded list/detail + batch dependent counts (enrollments, choices, timetable, class sessions, quiz schedules, lab experiments, attendance records)
- [x] `app/services/admin_subject_service.py` (NEW): duplicate 409, invalid semester 404, code immutable 409, semester immutable 409, anchor protection 409, slot-change-with-choice 409, no DELETE, active-session warning
- [x] `app/api/v1/endpoints/admin.py` (additive): `GET/POST/PATCH /api/v1/admin/subjects` — reads `require_any_admin`, writes `require_head_admin`, no DELETE route (405), no client scope params

### Frontend (additive, inside existing AdminShell)
- [x] `types/api.ts` + `hooks/useApi.ts`: admin subject types + `useAdminSubjects()` / `useAdminSubjectDetail()` / `useAdminSubjectMutations()`
- [x] `app/(admin)/admin/curriculum/page.tsx` (NEW): scoped subject list with loading/403/error-retry/empty/populated states; anchors visibly "frozen"
- [x] `app/(admin)/admin/curriculum/components/CreateSubjectDialog.tsx` + `EditSubjectDialog.tsx` (NEW): HEAD-only create/edit flows; code+semester immutable; anchor slot disabled; backend warnings surfaced
- [x] `components/admin/AdminShell.tsx`: "Curriculum" nav entry (all admins — scoped reads exist; writes HEAD-only server-side)
- [x] `app/(admin)/admin/page.tsx`: Curriculum moved from "Planned portal areas" to "Available now"

### Verifier
- [x] `backend/scripts/verify_phase_24_6.py` (NEW): hard locality guard, real app via ASGITransport, isolated fixtures, cleanup in `finally`, pre/post baseline counts, idempotent

## Hard scope (respected)
- [x] NO migration/schema change; NO subject delete/deactivate
- [x] NO anchor code/slot changes (BCS-054/BCS-058 frozen)
- [x] NO `StudentElectiveChoice` mutation; NO enrollment/attendance/quiz mutation
- [x] NO experiment-catalog endpoint changes (reuse existing lab endpoints)
- [x] NO quiz/timetable/session management (24.7/24.8/24.10)
- [x] NO client scope parameters; backend authorization is the only boundary
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)

## Validation
- [x] `verify_phase_24_6.py` PASS **46/46** (×2 runs, idempotent): auth matrix (401/403, scoped reads, HEAD writes), create/duplicate-409/invalid-semester-404/invalid-payload-422, PATCH metadata success / code-409 / semester-409 / anchor-code-409 / anchor-slot-409 / slot-with-choice-409 / normal slot change + explicit-null clear, ELECTIVE_ADMIN exact-subject isolation, CLASS_ADMIN own-semester isolation, no client scope elevation, arbitrary-UUID 404, DELETE → 405, active-session warning, baseline counts restored
- [x] Regression: `verify_phase_24_3.py` PASS 40/40; `verify_phase_24_5.py` PASS 46/46
- [x] `python -m compileall backend/app backend/scripts` PASS; `npx tsc --noEmit` PASS; ESLint (changed files) PASS; `git diff --check` clean; alembic single head `eb880e108f19` unchanged
- [x] No browser/E2E run (operator responsibility); production untouched; `.env` unchanged (local dev target)

## Do Not Touch Again
- Phase 24.6 subject endpoints are HEAD-only writes; code/semester immutable; anchors frozen; slot changes guarded by choice-dependents
- `verify_phase_24_6.py` is the authoritative Phase 24.6 verifier
- Phase 24.7-B+ requires a fresh execution prompt

## PHASE 24.7-A - TIMETABLE DOMAIN FOUNDATION (IN PROGRESS - 24.7-A COMPLETE, 2026-08-29)

Status: **24.7 IN PROGRESS: 24.7-A COMPLETE; 24.7-B (CRUD API) NOT STARTED.**
Local development only. Schema change + Alembic migration `c4d5e6f7a8b9`
(applied to local dev DB; production untouched). Git state: implemented but
NOT committed (no commit made during implementation, per operator
instruction).

## Objective

Extend the existing `timetable_entries` table (the EXPECTED academic schedule,
per Section/Subsection — distinct from actual `class_sessions` occurrences)
with the Phase 24.7 admin timetable domain contract. No CRUD endpoints, no
frontend timetable UI, no student timetable integration.

## Delivered

### Model (additive)
- [x] `models/timetable.py` — `TimetableEntry` + `subsection_id` (nullable, composite FK), `room`, `is_active` (NOT NULL server default true), `sort_order`, CHECK `end_time > start_time`, CHECK `day_of_week` 0..6, composite FK `(section_id, subsection_id)` -> subsections, `subsection` relationship (explicit foreign_keys)
- [x] `models/user.py` — `Subsection` + `uq_subsections_section_id` unique, `timetable_entries` relationship (explicit foreign_keys)

### Migration
- [x] `alembic/versions/c4d5e6f7a8b9_add_timetable_domain_foundation.py` — single additive migration; preserves all 28 existing rows; upgrade + downgrade verified locally; single linear head

### Schemas
- [x] `schemas/admin_timetable.py` (NEW) — `TimetableEntryAdminResponse` (full Phase 24.7 contract) + `TimetableEntryAdminListResponse`

### Verifier
- [x] `scripts/verify_phase_24_7a.py` (NEW) — static/DB verifier: columns, constraints, 28 rows preserved, no fabricated data, upgrade/downgrade cycle

## Hard scope (respected)
- [x] NO CRUD API / endpoints (24.7-B)
- [x] NO frontend timetable UI / admin timetable page
- [x] NO student timetable integration changes
- [x] NO duplication of timetable data per student
- [x] NO unrelated tables/schema changed
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)

## Validation
- [x] `verify_phase_24_7a.py` PASS (columns, constraints, 28 rows, no backfill of invented data)
- [x] Regression: `verify_phase_24_3.py` PASS 40/40; `verify_phase_24_5.py` PASS 46/46; `verify_phase_24_6.py` PASS 46/46
- [x] `python -m compileall backend/app backend/scripts` PASS; `git diff --check` clean; alembic single head `c4d5e6f7a8b9`
- [x] Student-facing `GET /api/v1/timetable` endpoint unchanged (response keys verified: `{'id','day_of_week','class_type','subject','elective_slot'}`)
- [x] Schema serialization: `TimetableEntryAdminResponse` from ORM rows + list response valid
- [x] Downgrade `c4d5e6f7a8b9 -> eb880e108f19` and upgrade `eb880e108f19 -> c4d5e6f7a8b9` clean; rows preserved
- [x] No browser/E2E run (operator responsibility); production untouched; `.env` unchanged (local dev target)

## Do Not Touch Again
- Phase 24.7-A schema/model changes are reviewed and frozen (additive columns + integrity guards + migration `c4d5e6f7a8b9`)
- `verify_phase_24_7a.py` is the Phase 24.7-A verifier
- Phase 24.7-C (HTTP CRUD API) and Phase 24.8+ require fresh execution prompts

## PHASE 24.7-B - TIMETABLE REPOSITORY, SERVICE & CONFLICT VALIDATION (IN PROGRESS - 24.7-B COMPLETE, 2026-08-29)

Status: **24.7 IN PROGRESS: 24.7-B COMPLETE; 24.7-C (HTTP CRUD API) NOT
STARTED.** Local development only. No schema change, NO new migration (alembic
head `c4d5e6f7a8b9` unchanged). Git state: implemented but NOT committed (no
commit made during implementation, per operator instruction).

## Objective

The authoritative backend timetable management layer — repository, service,
and deterministic conflict detection. The backend owns ALL timetable
validation and conflict detection (never the frontend). No HTTP CRUD
endpoints, no frontend.

## Delivered

### Backend (additive)
- [x] `repositories/admin_timetable_repo.py` (NEW): scope-aware `list_entries` (deterministic ordering day → sort_order NULLS LAST → start_time → id), `get_entry`, `list_active_conflict_candidates` (bounded: active same-section/same-day), counts, academic-context lookups
- [x] `services/admin_timetable_service.py` (NEW): academic-context validation (subject belongs to the section's semester), subsection validation (belongs to the entry's section), elective-slot validation (marker matches subject's catalog slot), time validation (end > start), deterministic conflict detection, active/inactive semantics (inactive never blocks; scheduling edits on inactive entries require reactivation), server-side scope resolution via AuthorizationService (no client trust), domain-error hierarchy
- [x] `schemas/admin_timetable.py` (extended): create/update request schemas + mutation response

### Verifier
- [x] `scripts/verify_phase_24_7b.py` (NEW): PASS 29/29 (×2, idempotent); locality-guarded; isolated fixtures (fixture session/semester/sections/subsections/subjects + scoped admins); cleanup in `finally`; baseline counts restored

## Conflict semantics (recorded verbatim)
- [x] Both active required (inactive entries never block)
- [x] Same day + same section + time overlap (`existing.start < new.end AND existing.end > new.start`; adjacent allowed)
- [x] Section-wide × section-wide → conflict; section-wide × subsection → conflict; same subsection × same subsection → conflict
- [x] Different subsections → parallel allowed; different sections → never conflict
- [x] Elective rule: same elective_slot (both ELECTIVE_I or both ELECTIVE_II) → no auto-conflict (per-student resolution); different slots or elective × regular → conflict

## Hard scope (respected)
- [x] NO HTTP CRUD endpoints / admin timetable editor (24.7-C)
- [x] NO frontend changes
- [x] NO schema change / migration (24.7-A migration `c4d5e6f7a8b9` reused)
- [x] NO duplicate timetable data per student; NO student-specific timetable rows
- [x] NO attendance/quiz/elective engine changes; existing elective architecture (ElectiveResolver) untouched
- [x] NO client-supplied role/scope trusted — AuthorizationService is the only scope authority
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)

## Validation
- [x] `verify_phase_24_7b.py` PASS **29/29** (×2 runs, idempotent): non-overlapping allowed; adjacent allowed; overlapping same-subsection rejected; section-wide×subsection rejected; different sections allowed; different subsections allowed; inactive does not block new active; invalid time range rejected; incompatible subject rejected; mismatched elective slot rejected; non-elective + elective marker rejected; valid elective + matching slot allowed; same-slot overlap allowed; ELECTIVE_I×ELECTIVE_II rejected; elective×regular rejected; CLASS_ADMIN own-section; ELECTIVE_ADMIN own-subject; SUBSECTION_ADMIN own-section; STUDENT nothing; CLASS_ADMIN cross-section create → INVALID_SCOPE; not-found → NOT_FOUND; out-of-scope detail → INVALID_SCOPE; inactive scheduling edit → INACTIVE_PARENT; reactivation re-runs conflict detection; reactivation allowed once slot free; reactivated entry blocks overlap; repository scoped list; baseline restored; original active session unchanged
- [x] Regression: `verify_phase_24_3.py` PASS 40/40; `verify_phase_24_5.py` PASS 46/46; `verify_phase_24_6.py` PASS 46/46; `verify_phase_24_7a.py` PASS
- [x] `python -m compileall backend/app backend/scripts` PASS; `git diff --check` clean; alembic single head `c4d5e6f7a8b9` unchanged (no new migration)
- [x] No browser/E2E run (operator responsibility); production untouched; `.env` unchanged (local dev target)

## Do Not Touch Again
- Phase 24.7-B repository/service/conflict logic is reviewed and frozen
- `verify_phase_24_7b.py` is the Phase 24.7-B verifier
- Phase 24.7-D (frontend editor) and Phase 24.8+ require fresh execution prompts

## PHASE 24.7-C - ADMIN TIMETABLE CRUD API (IN PROGRESS - 24.7-C COMPLETE, 2026-08-29)

Status: **24.7 IN PROGRESS: 24.7-C COMPLETE; 24.7-D (frontend timetable editor)
NOT STARTED.** Local development only. No schema change, NO new migration
(alembic head `c4d5e6f7a8b9` unchanged). Git state: implemented but NOT
committed (no commit made during implementation, per operator instruction).

## Objective

Expose the timetable management functionality through a secure Admin API.
Security is backend-enforced (frontend hiding is not authorization). No
hard-delete of timetable history — deactivation (`is_active=false`) preserves
history per Gate 7.

## Delivered

### Backend (additive)
- [x] `schemas/admin_timetable.py` (extended): `DuplicateTimetableEntryRequest` (absent overrides copied from source)
- [x] `repositories/admin_timetable_repo.py` (extended): list filters — `subsection_ids`, `semester_ids`, `session_ids`, `elective_slot`, `is_active` (bounded EXISTS joins)
- [x] `services/admin_timetable_service.py` (extended): filter intersection (never expand scope), `_assert_write_scope` STRICT write gate (HEAD + CLASS only), `duplicate_entry`
- [x] `endpoints/admin.py` (additive): six `/api/v1/admin/timetable` endpoints + `_raise_timetable_error` mapping (401/403/404/409/422)

### Verifier
- [x] `scripts/verify_phase_24_7c.py` (NEW): PASS 30/30 (×2, idempotent); in-process HTTP testing (ASGITransport) against the LOCAL DB; locality-guarded; isolated fixtures; cleanup in `finally`; baseline restored

## API contract (recorded)
- [x] `GET /api/v1/admin/timetable` — scoped list; query filters session/semester/section/subsection/day/active/subject/elective; filters only NARROW the scope-derived set
- [x] `GET /api/v1/admin/timetable/{entry_id}` — scoped detail; out-of-scope/nonexistent -> 404
- [x] `POST /api/v1/admin/timetable` — create; write gate HEAD + CLASS only; conflict -> 409
- [x] `PATCH /api/v1/admin/timetable/{entry_id}` — partial update; resulting complete entry revalidated; conflict detection ignores the row being updated
- [x] `POST /api/v1/admin/timetable/{entry_id}/deactivate` — soft deactivate (idempotent)
- [x] `POST /api/v1/admin/timetable/{entry_id}/duplicate` — server-side duplication; full validation + conflict detection; never silently overwrites

## Authorization matrix (authoritative Phase 24.0 §7)
- [x] HEAD_ADMIN: global timetable access (read + write)
- [x] CLASS_ADMIN: assigned section(s) only (read + write)
- [x] SUBSECTION_ADMIN: assigned subsections' sections (read, inert — write NO)
- [x] ELECTIVE_ADMIN: exact concrete subject (read own-subject entries only — write NO; event path is their write surface)
- [x] No client-supplied role/scope trusted; no hidden-frontend authorization

## Hard scope (respected)
- [x] NO hard-delete of timetable entries (deactivation only; Gate 7 unresolved)
- [x] NO frontend / UI (24.7-D)
- [x] NO schema change / migration
- [x] NO attendance/quiz/event/session mutation
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)

## Validation
- [x] `verify_phase_24_7c.py` PASS **30/30** (×2 runs, idempotent): unauth 401; STUDENT 403; HEAD read/create; conflict 409; adjacent allowed; detail; PATCH room; deactivate + reactivate; duplicate (day override); CLASS own-section 201 + other-section 403; ELECTIVE create 403; SUBSECTION create 403; CLASS list own-section; ELECTIVE list own-subject; SUBSECTION list own-section; filtered list; nonexistent 404s (GET/PATCH/deactivate/duplicate); baseline restored; active session unchanged
- [x] Regression: 24.3 40/40 · 24.5 46/46 · 24.6 46/46 · 24.7a PASS · 24.7b 29/29
- [x] `python -m compileall backend/app backend/scripts` PASS; `git diff --check` clean; alembic single head `c4d5e6f7a8b9` unchanged
- [x] No browser/E2E run (operator responsibility); production untouched; `.env` unchanged (local dev target)

## Do Not Touch Again
- Phase 24.7-C endpoints are the frozen timetable CRUD surface; write gate HEAD + CLASS only
- `verify_phase_24_7c.py` is the Phase 24.7-C verifier
- Phase 24.7-E (refinements) and Phase 24.8+ require fresh execution prompts

## PHASE 24.7-D - ADMIN TIMETABLE BUILDER UI (IN PROGRESS - 24.7-D COMPLETE, 2026-08-30)

Status: **24.7 IN PROGRESS: 24.7-D COMPLETE; 24.7-E (refinements) NOT
STARTED.** Local development only. No schema change, NO new migration (alembic
head `c4d5e6f7a8b9` unchanged). Git state: implemented but NOT committed.

## Objective

Build the Admin Portal timetable management surface — a real CRUD interface
(not a mockup) inside the existing AdminShell. The UI is NOT the security
boundary: reads are scoped server-side; writes are gated by the backend to
HEAD_ADMIN + CLASS_ADMIN (assigned section); the frontend only hides controls
for presentation.

## Delivered (additive, inside existing AdminShell)

- [x] `types/api.ts` + `hooks/useApi.ts`: timetable contracts (response, create/update/duplicate requests, mutation response) + `useAdminTimetableEntries(params)`, `useAdminTimetableEntryDetail`, `useAdminTimetableMutations`
- [x] `app/(admin)/admin/timetable/page.tsx` (NEW): scoped weekly grid grouped by day with per-entry cards; filters session/semester/section/day/active/subject/elective; loading/403/error/empty states; create/edit/deactivate/duplicate actions; SWR revalidation after successful mutations (never optimistic on failure)
- [x] `components/timetable/TimetableEntryForm.tsx` (NEW): reusable form (section, subsection, day, start/end, subject, class type, room, elective slot, active, sort order); light UX validation only (server authoritative)
- [x] Four dialogs (NEW): Create, Edit, Deactivate (explicit confirmation), Duplicate (server-side with overrides)
- [x] `components/admin/AdminShell.tsx`: "Timetable" nav entry (all admins)
- [x] `app/(admin)/admin/page.tsx`: Timetable moved from "Planned portal areas" to "Available now"

## Hard scope (respected)
- [x] NO backend/schema/DB changes (alembic head unchanged)
- [x] NO frozen student surfaces rewritten
- [x] NO browser testing performed (operator responsibility)
- [x] NO business conflicts computed independently in React (backend authoritative via 409)
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)

## Validation
- [x] `npx tsc --noEmit` PASS (0 errors)
- [x] ESLint on all changed files PASS (0 warnings after fixing: unused `setSubsectionId`, pointless filter)
- [x] `git diff --check` clean
- [x] No browser/E2E run (operator responsibility); production untouched; `.env` unchanged (local dev target)

## Do Not Touch Again
- Phase 24.7-D timetable UI is the frozen builder surface; the backend is the security boundary
- Phase 24.7-F (student-facing integration) and Phase 24.8+ require fresh execution prompts

## PHASE 24.7-E - MUTATION WORKFLOW COMPLETION (IN PROGRESS - 24.7-E COMPLETE, 2026-08-30)

Status: **24.7 IN PROGRESS: 24.7-E COMPLETE; 24.7-F (student-facing
integration) NOT STARTED.** No schema change, no new migration, no backend
changes. Git state: implemented but NOT committed.

## Objective

Finish the timetable builder's mutation workflows so there are no obvious
CRUD leftovers. Audit the existing 24.7-D implementation and complete any
missing implementation for create, edit, duplicate, and deactivate.

## Delivered (edits to existing 24.7-D components, no new files)

- [x] `CreateTimetableEntryDialog` — closes on success (after backend accept +
  revalidation); remounts fresh per open via `key` (no stale form state)
- [x] `EditTimetableEntryDialog` — sends ONLY CHANGED fields (diff against
  loaded persisted entry); PATCH preserve-omitted semantics: non-scheduling
  edits (room) on INACTIVE entries no longer trip INACTIVE_PARENT; subsection
  never silently cleared; closes on success
- [x] `DeactivateTimetableEntryDialog` — error handling (try/catch + error
  display); no silent failure, no fake success
- [x] `DuplicateTimetableEntryDialog` — description states exactly which fields
  are copied vs overridable; preserves source is_active; 409 conflict rendered
  with a styled warning banner showing only the backend detail
- [x] `TimetableEntryForm` — error state carries HTTP status; 409 renders a
  distinct warning banner with backend detail (day/time/subject as returned)
- [x] Page — all mutation dialogs keyed per entry id; filters preserved across
  mutations; revalidation decides row visibility

## Hard scope (respected)
- [x] NO backend/schema/DB changes
- [x] NO student attendance/session behavior touched
- [x] NO browser testing performed (operator responsibility)
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)

## Validation
- [x] `npx tsc --noEmit` PASS (0 errors)
- [x] ESLint on all changed files PASS (0 warnings/errors; one unescaped-entity fix)
- [x] `git diff --check` clean
- [x] No browser/E2E run (operator responsibility); production untouched; `.env` unchanged (local dev target)

## Do Not Touch Again
- Phase 24.7-F conflict contract (structured 409 `detail.message` + `detail.conflicts`) and the `apiFetch` body attachment are frozen behavior
- Phase 24.7-G (student-facing integration) and Phase 24.8+ require fresh execution prompts

## PHASE 24.7-F - CONFLICT-AWARE UX (IN PROGRESS - 24.7-F COMPLETE, 2026-08-30)

Status: **24.7 IN PROGRESS: 24.7-F COMPLETE; 24.7-G (student-facing
integration) NOT STARTED.** No schema/migration changes; no new endpoints.
Git state: implemented but NOT committed.

## Objective

Make timetable conflicts understandable and prevent avoidable administrative
mistakes without moving business logic into React. Backend remains
authoritative.

## Delivered

### Backend (additive, 24.7-C contract extended)
- [x] 409 responses carry structured `{"detail": {"message", "conflicts"}}` with the backend-resolved conflicting-entry list (id, subject_code, subject_name, section_name, subsection_name, day_of_week, start/end_time, subsection_id, elective_slot; UUIDs stringified, JSON-serializable)
- [x] `_format_conflicts` — human-readable message with scope context (day label + section/subsection)
- [x] Conflict candidates eager-load subject + section + subsection
- [x] Other error codes keep the string `detail` convention

### Frontend (additive)
- [x] `apiFetch` attaches the parsed response body (`error.body`) and handles string/object/absent detail; HTTP status preserved
- [x] Form + duplicate dialogs render the backend `conflicts` list verbatim inside the 409 warning banner
- [x] 409 keeps form values, keeps dialog open, never shows success
- [x] Entry cards render a time-position bar (08:00–18:00 window) making overlapping entries visually obvious

### Concurrency (recorded)
- [x] Every mutation re-reads the current DB state and re-runs conflict detection against it — a stale frontend cannot bypass validation after another admin changes the timetable
- [x] No optimistic UI state; after success the page revalidates the authoritative query

## Hard scope (respected)
- [x] NO second conflict engine in React (backend authoritative)
- [x] NO schema/migration/DB changes
- [x] NO student attendance/session behavior touched
- [x] NO browser testing performed (operator responsibility)
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)

## Validation
- [x] `verify_phase_24_7c.py` PASS **30/30** (409 assertions unchanged — status code only)
- [x] `compileall` PASS; `npx tsc --noEmit` PASS; ESLint PASS (one pre-existing `window.location.href` warning in api.ts, unrelated); `git diff --check` clean
- [x] Live 409 body verified (message with scope context + structured `conflicts` list)
- [x] No browser/E2E run (operator responsibility); production untouched; `.env` unchanged (local dev target)

## Do Not Touch Again
- Phase 24.7-G student resolution (`get_weekly_entries_for_student` + no-anchor-leakage endpoint) is frozen behavior
- Phase 24.7-H (materialization alignment) and Phase 24.8+ require fresh execution prompts

## PHASE 24.7-G - STUDENT TIMETABLE RESOLUTION (IN PROGRESS - 24.7-G COMPLETE, 2026-08-30)

Status: **24.7 IN PROGRESS: 24.7-G COMPLETE; 24.7-H (materialization
alignment) NOT STARTED.** No schema/migration changes. Git state: implemented
but NOT committed.

## Objective

Derive the student timetable from the student's academic context (section +
subsection), their LOCKED elective choices, and the authoritative timetable
— no hardcoded current-semester assumptions, no anchor leakage, no subsection
leakage, no cross-student elective leakage.

## Delivered

### Backend
- [x] `repositories/timetable_repo.py` — `get_weekly_entries_for_student()`:
  active-only; section-wide + own-subsection entries; other subsections
  excluded
- [x] `api/v1/endpoints/timetable.py` — student-scoped query; DE-I/DE-II
  slots resolve to locked choices; slots with NO locked choice are omitted
  (no anchor exposure); common subjects unchanged

### Verifier
- [x] `scripts/verify_phase_24_7g.py` (NEW): PASS **25/25**

## Hard scope (respected)
- [x] NO collapsed `class_sessions` — timetable remains expected schedule
- [x] NO schema/migration/DB changes
- [x] NO frontend changes (response shape unchanged; existing consumers
  automatically benefit)
- [x] NO student attendance/session/quiz/event behavior mutated
- [x] NO hardcoded current-semester timetable assumptions
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)

## Validation
- [x] `verify_phase_24_7g.py` PASS **25/25**: Student A (DE-I→BCS-054,
  DE-II→BCS-058) resolved set matches; Student B (DE-I→BCS-052,
  DE-II→BCS-055) resolved set matches; Student C (no choices) sees no
  elective entries (no anchor leakage); all three have exactly one
  own-subsection day-2 entry (subsection isolation); no cross-student
  leakage (A sees no BCS-052/055, B sees no BCS-054/058); inactive entry
  excluded; baseline restored; active session unchanged
- [x] Regressions: 24.3 40/40 · 24.5 46/46 · 24.6 46/46 · 24.7c 30/30
- [x] `compileall` PASS; `git diff --check` clean; alembic head `c4d5e6f7a8b9`
  unchanged
- [x] No browser/E2E run (operator responsibility); production untouched;
  `.env` unchanged (local dev target)

## Phase 24.7-H - COMPLETION GATE (COMPLETE, 2026-08-30)

**Status: Phase 24.7 ✅ COMPLETE — FROZEN.** All 8 slices implemented and
verified. Next: Phase 24.8 — Quiz Schedule Manager.

## Completion gate verification

- [x] Leftover search: no TODO/FIXME/mock/hardcoded/dead-code found in Phase
  24.7 files. One dead hook (`useAdminTimetableEntryDetail`) was identified
  and removed. The `verify_phase_22_1.py` response-fields failure is
  PRE-EXISTING (predates Phase 22.3 `elective_slot`), not a 24.7 defect.
- [x] Conflict matrix verified: exact/partial/containing/contained overlap
  rejected (9/9), adjacent allowed, different day, different section,
  inactive conflicting row allowed, self-edit conflict-free.
- [x] Security matrix verified via direct API: HEAD global read/write, CLASS
  own-section read/write + cross-section 403, SUBSECTION own-section read +
  write 403, ELECTIVE own-subject read + write 403, STUDENT 403.
- [x] Academic matrix verified: Student A (DE-I BCS-054, DE-II BCS-058) and
  Student B (DE-I BCS-052, DE-II BCS-055) get exact resolved sets; no anchor
  leakage, no cross-student leakage, subsection isolation, inactive excluded.
- [x] Data integrity: baseline counts restored, attendance/class_sessions/
  quiz_schedules/academic_events/student_elective_choices unchanged.
- [x] No DELETE route (405), no per-student timetable rows, no accidental hard
  deletes, no attendance/quiz/event/elective/student mutation.
- [x] All regressions green: 24.3 40/40 · 24.5 46/46 · 24.6 46/46 · 24.7a PASS
  · 24.7b 29/29 · 24.7c 30/30 · 24.7g 25/25 · 24.7h 27/27.
- [x] `compileall` PASS; `tsc --noEmit` PASS; ESLint PASS (one pre-existing
  `window.location.href` warning in api.ts, unrelated); `git diff --check`
  clean; alembic single head `c4d5e6f7a8b9` unchanged.
- [x] No browser/E2E run (operator responsibility); production untouched;
  `.env` unchanged (local dev target).

## Do Not Touch Again
- **Phase 24.7 is FROZEN.** No further changes to the timetable domain,
  conflict detection, admin CRUD API, admin UI, student resolution, or scope
  enforcement without a new explicit phase.
- Phase 24.8 (Quiz Schedule Manager) COMPLETE (2026-08-30).
Phase 24.9 (Event Manager) COMPLETE (2026-08-30).
Phase 24.10 (Subject-Specific Elective Events) requires a fresh execution prompt.

## PHASE 24.9 - EVENT MANAGER (COMPLETE, 2026-08-30)

## Objective

Admin Portal management of the existing AcademicEvent system through a
dedicated control-plane API. All mutations flow through the canonical
EventService / validation registry / EventSessionSynchronizer.

## Delivered

### Backend (additive)
- [x] `schemas/admin_events.py` (NEW): admin event read model with `quiz_schedule_managed` + `target_summary`
- [x] `services/admin_event_service.py` (NEW): scope-filtered reads; create/update/deactivate through EventService; QUIZ_DAY ownership guard (schedule-backed QUIZ_DAY -> 409)
- [x] `endpoints/admin.py` (additive): GET/POST/PATCH/DELETE /admin/events; DELETE = safe deactivation; reads require_any_admin + scope; writes per Phase 24.0 capability matrix

### Frontend (additive, inside AdminShell)
- [x] `/admin/events` page (NEW): table, event-type/state filters, quiz-managed badge, create/edit/deactivate dialogs
- [x] CreateEventDialog + EditEventDialog (NEW): field visibility per eventRules (shared frontend mirror; backend authoritative)
- [x] AdminShell nav (Events) + dashboard "Available now" promotion

### Verifier
- [x] `scripts/verify_phase_24_9.py` (NEW): PASS **40/40**

## Hard scope (respected)
- [x] NO second event engine/registry/synchronizer (EventService reused)
- [x] NO direct class_sessions/occurrence_outcomes writes from API/UI
- [x] NO Phase 24.10 divergent elective-event editor
- [x] NO per-student event copies; NO anchor leakage; NO desync of QUIZ_DAY from Phase 24.8
- [x] NO schema/migration; NO hard event deletion; NO student events page redesign
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)

## Validation
- [x] `verify_phase_24_9.py` PASS **40/40** (auth, scope, registry validation, synchronizer, QUIZ_DAY guard, isolation, idle potency, baseline)
- [x] Regressions: 24.3 40/40 · 24.5 46/46 · 24.6 46/46 · 24.7a PASS · 24.7b 29/29 · 24.7c 30/30 · 24.7g 25/25 · 24.7h 27/27 · 24.8 34/34
- [x] `compileall` PASS; `tsc --noEmit` PASS; ESLint PASS; `git diff --check` clean; alembic head unchanged
- [x] No browser/E2E run (operator responsibility); production untouched; `.env` unchanged (local dev target)

## Do Not Touch Again
- Phase 24.9 event manager is frozen; the QUIZ_DAY ownership guard is the authoritative boundary between generic event management and quiz schedule management
- Phase 24.10 (Subject-Specific Elective Events) requires a fresh execution prompt

## PHASE 24.8 - QUIZ SCHEDULE MANAGER (COMPLETE, 2026-08-30)

Status: **✅ COMPLETE.** No schema/migration (alembic head `c4d5e6f7a8b9`
unchanged). Git state: implemented but NOT committed.

## Objective

Admin can configure quiz cycles, dates, subjects, DE-I/DE-II, and relevant
eligibility settings via the canonical quiz architecture — no new quiz
engine, no eligibility rewrite, no duplicate schedule source, no per-student
quiz rows, existing current-semester data preserved.

## Delivered

### Backend (additive)
- [x] `schemas/admin_quizzes.py` (NEW): cycle/policy reads, schedule read model with `has_active_event` parity indicator, create/update/mutation responses
- [x] `repositories/admin_quiz_repo.py` (NEW): bounded queries, duplicate guard, QUIZ_DAY event identity lookup
- [x] `services/admin_quiz_service.py` (NEW): scope resolution (HEAD/CLASS/ELECTIVE/SUBSECTION), validation (subject quiz-applicable theory, date-in-semester, cycle, elective-slot relationship, duplicate), single-transaction atomic QUIZ_DAY sync (create/deactivate/date-move, idempotent)
- [x] `endpoints/admin.py` (additive): GET/POST/PATCH /quizzes, GET /quiz-cycles; reads `require_any_admin` + scope; writes `require_head_admin`; 401/403/404/409/422

### Frontend (additive, inside AdminShell)
- [x] `/admin/quizzes` page (NEW): table, cycle/session/semester filters, target/date/status/QUIZ_DAY badges
- [x] CreateQuizScheduleDialog + EditQuizScheduleDialog (NEW): PATCH semantics, no close on 409/422, no fake success
- [x] AdminShell nav (Quiz Schedules) + dashboard "Available now" promotion

### Verifier
- [x] `scripts/verify_phase_24_8.py` (NEW): PASS **34/34**

## Hard scope (respected)
- [x] NO eligibility mathematics rewritten; NO React-side eligibility
- [x] NO second quiz schedule source; NO duplicate quiz events
- [x] NO per-student quiz schedule rows; no anchor leakage
- [x] NO hardcoded subject/date lists; catalog from backend
- [x] NO DELETE endpoint (status/deactivation only)
- [x] NO schema/migration; NO attendance/choice/event/history mutation
- [x] NO decision gate resolved (all 12 Phase 24.0 gates remain open)

## Validation
- [x] `verify_phase_24_8.py` PASS **34/34** (auth, scope, CRUD, sync, isolation, idempotency, baseline)
- [x] Regressions: 24.3 40/40 · 24.5 46/46 · 24.6 46/46 · 24.7a PASS · 24.7b 29/29 · 24.7c 30/30 · 24.7g 25/25 · 24.7h 27/27
- [x] `compileall` PASS; `tsc --noEmit` PASS; ESLint PASS; `git diff --check` clean; alembic head unchanged
- [x] No browser/E2E run (operator responsibility); production untouched; `.env` unchanged (local dev target)

## Do Not Touch Again
- Phase 24.8 quiz schedule API + QUIZ_DAY sync is frozen behavior
- Phase 24.9 (Event Manager) requires a fresh execution prompt
