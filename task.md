# AttendanceDash Pro — Task Brief

## PHASE 2 — DESKTOP SHELL & GLOBAL UX

Status: **COMPLETE** (13 Aug 2026) — see BLOCKED markers in `implementation_plan.md`

## Objective

Reproduce the desktop reference interface (compact top navigation, profile dropdown, Profile/Appearance/Feedback/Settings/Install modals) on the Next.js app using real application data — without faking functionality.

## Delivered

- [x] Desktop top navigation (TopNav) replacing the legacy sidebar; active route highlighted; route labels mapped to existing routes only
- [x] Authenticated user area (avatar + name) + Profile dropdown with Profile / Appearance / Install App / Send Feedback / Settings / Sign Out
- [x] Shared modal foundation (`ShellDialog`) — backdrop, focus, Escape, scroll lock, responsive width, dialog semantics, consistent header/close/spacing
- [x] Profile modal from real `/student/me` data (identity + academic context)
- [x] Appearance modal — Dark selected; Light/System explicitly disabled (BLOCKED: Phase 1 tokens are dark-locked)
- [x] Feedback modal — validation, loading, success, error, duplicate-submission guard; posts to `POST /api/v1/feedback` (BLOCKED: endpoint not implemented; error surfaced honestly, no fake success)
- [x] Settings modal — controls disabled + persistence notice (BLOCKED: no user-preferences backend)
- [x] Install App — beforeinstallprompt capture + standalone detection; explains missing PWA infra (BLOCKED: no manifest/service worker); no fake installed state
- [x] Sign Out via existing `AuthContext.logout()` (JWT removal + redirect), auth architecture untouched
- [x] Backend: `GET /student/me` extended with read-only academic context (additive contract change; no schema/DB/engine changes)

## Not in this phase

- Home / Track / Quiz Eligibility / Attendance / History / Events page content redesigns (dedicated phases)
- Events functionality (list/calendar, Upcoming/Today/Past, Add Event, persistence) — dedicated Events phase
- Mobile navigation — dedicated later phase (nav hidden below `md`)
- Program field, feedback persistence, settings persistence, Light/System themes, PWA infra — see BLOCKED markers in `implementation_plan.md`

## Validation

- `npx tsc --noEmit` — PASS
- Backend `py_compile` on changed files — PASS

## Do Not Touch Again

- Phase 0 audit · Phase 1 design tokens · Card · Badge · Progress
- backend architecture · database architecture · attendance engine · quiz engine
- authentication architecture · Firebase migration boundary

---

## PHASE 3 — HOME DASHBOARD

Status: **COMPLETE** (13 Aug 2026) — see BLOCKED markers in `implementation_plan.md`

## Objective

Rebuild the authenticated Home/Dashboard page to match the desktop reference composition (Greeting → Today's Attendance → Overall Attendance → This Week → Quiz Snapshot → Attention Required → Upcoming Events), driven by real authenticated data, with loading/error/empty states and no duplication of business logic.

## Delivered

- [x] Backend: single additive read-only endpoint `GET /api/v1/dashboard/summary` (dashboard.py endpoint + schema + service) reusing `AttendanceService`, `EligibilityService`, `CalendarService`, `QuizRepository`; engines untouched
- [x] Backend: additive `AttendanceRepository.get_sessions_with_status()` only new repo method
- [x] Status classification reconciled: SAFE ≥ 80 / WATCH ≥ 60 / CRITICAL < 60 on **current** pct (S4.1 + legacy banding)
- [x] Today's Attendance — per-session status (Attended/Missed/Pending/Cancelled), attendance/pending footer
- [x] Overall Attendance — big pct, status badge, attended/recorded/pending counts, weekly delta, progress bar
- [x] This Week — Mon–Fri strip with per-day pct bars, week pct + delta vs previous week, best/needs-attention subjects
- [x] Quiz Snapshot — next quiz cycle label + date + threshold, eligible/attention/not-eligible counts, link to `/tools/quiz-schedule`; empty state when none scheduled
- [x] Attention Required — WATCH/CRITICAL subjects (CRITICAL first, pct ascending) with current + forecast pct; link to `/tools/laboratory`; empty state when on track
- [x] Upcoming Events — date chips + type badges, subject-scoped to enrolled subjects; empty state (table currently has 0 rows); link to `/tools/events`
- [x] Greeting header — time-of-day greeting + first name (real profile) + `Thursday · 13 Aug 2026` local date
- [x] Loading skeletons per section; full-page error state; two-column bento with collapse order Today's → Overall → This Week → Quiz → Attention → Events

## Not in this phase

- Dedicated per-subject strategy view (View Strategy → `/tools/laboratory`; Track-phase work)
- Events seeding — `academic_events` is empty, section shows its empty state until real events exist

## Validation

- Backend `py_compile` on changed files — PASS
- Live `GET /api/v1/dashboard/summary` (real user `2401220100027`) — PASS: 6 today's classes (all PENDING), overall 69.2% WATCH, weekly delta +21.5 pts, Quiz1 (cycle 1, ≥70%) 6/6 eligible, 4 attention items (BNC-501/BCS-058/BCS-054 CRITICAL, BCS-502 WATCH), 0 events
- `npx tsc --noEmit` — PASS (0 errors)

## Do Not Touch Again

- All Phase 2 items above, plus: `backend/app/engines/*` · `backend/app/models/*` · migrations
- `frontend/src/components/ui/*` primitives · `TopNav` · `UserMenu` · `AppShell` · `TodayClassesCard` · `FormulaCard` · `SubjectAttendanceGrid` (other pages use them)
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

Correct the calendar/event defects PROVEN in the Phase 6.0 audit (`docs/phase_6_0_calendar_events_audit.md`) so later Calendar/Event work is built on correct temporal semantics. No calendar UI, no event CRUD, no admin system, no seeding, no event→session integration in this phase.

## Root causes

1. **Weekend mapping**: `CalendarService` and `EligibilityService` passed `default_weekends=[5, 6]` (Python weekday indices) but `calendar_engine.get_academic_day` converts dates to JS `getDay()` indices before testing membership — Friday resolved non-working, Sunday working.
2. **MID_SEMESTER_BREAK**: absent from the engine's closure list despite priority 60 (same tier as SEMESTER_BREAK) — it did not flip days non-working.
3. **/events read contract**: `GET /api/v1/events` → `CalendarRepository.get_all_events()` returned every row (inactive + fully past included) with no filtering.
4. **Dashboard aggregation scope**: `AttendanceRepository.get_sessions_with_status` had no `StudentEnrollment` join — Dashboard Today/Overall/Weekly aggregated all class sessions, not just the student's enrolled subjects.

## Exact fixes

- `backend/app/engines/calendar_engine.py` — new canonical constant `DEFAULT_WEEKENDS = [0, 6]` (JS `getDay()`: Sunday=0, Saturday=6; matches legacy `js/calendar-engine.js` and the engine's own conversion), used as the parameter default of `get_academic_day`; `MID_SEMESTER_BREAK` added to the closure-event list.
- `backend/app/services/calendar_service.py` — `get_day_schedule` now passes the shared `DEFAULT_WEEKENDS` (removed the local `[5, 6]`).
- `backend/app/services/eligibility_service.py` — same shared constant for `get_attendance_window` / `evaluate_quiz_eligibility` (window bounds math unchanged; teaching-day counts now use the corrected convention).
- `backend/app/repositories/calendar_repo.py` — `get_all_events(active=None, date_from=None, date_to=None, upcoming=False)` optional server-side filters (repo default remains no-filter for internal dashboard/eligibility callers).
- `backend/app/api/v1/endpoints/events.py` — `GET /api/v1/events` query params: `active` (default `true`), `date_from`, `date_to` (inclusive range-overlap), `upcoming` (default `false`, `end_date >= today`); 422 when `date_from > date_to`.
- `backend/app/repositories/attendance_repo.py` — `get_sessions_with_status` now joins `StudentEnrollment` (mirrors `get_daily_sessions` / `get_history`).
- `backend/scripts/expand_baseline.py` — uses the shared `DEFAULT_WEEKENDS` constant (was an inline `[0, 6]`).

## Final GET /api/v1/events contract

- Default: **active events only** (`active=true`); pass `active=false` for inactive events only.
- `date_from` / `date_to` (YYYY-MM-DD): inclusive range-overlap on the event's `[start_date, end_date]` (`event.start_date <= date_to AND event.end_date >= date_from`).
- `upcoming=true`: `end_date >= today` (date-only; combine with `active` for "current/upcoming active" events).
- `date_from > date_to` → 422. Still read-only; mutation remains out of scope for students.
- Backwards compatibility: internal consumers (dashboard `_build_upcoming_events`, eligibility service) call the repository directly with no filters and are unchanged; the only HTTP consumer (Events page) keeps working and now receives only active events.

## Weekend behavior (before vs after)

| Date | Before ([5,6] interpreted as JS) | After (DEFAULT_WEEKENDS [0,6]) |
|---|---|---|
| 2026-08-13 Thu | working | working |
| 2026-08-14 Fri | **non-working** | **working** ✅ |
| 2026-08-15 Sat | non-working | non-working |
| 2026-08-16 Sun | **working** | **non-working** ✅ |

## MID_SEMESTER_BREAK behavior

Now a closure (same tier as SEMESTER_BREAK, priority 60): an active MID_SEMESTER_BREAK event spanning a date forces that date non-working regardless of `is_working_day`, consistent with the documented break/closure family (`docs/05_CALENDAR_ENGINE.md` priority table groups SEMESTER_BREAK/MID_SEMESTER_BREAK at 60). No new semantics invented.

## Verification (static / in-process only; no browser testing)

- `backend/.venv/Scripts/python -m compileall backend/app backend/scripts` — **PASS**
- `npx tsc --noEmit` (frontend) — **PASS** (0 errors)
- In-process engine/service execution (real `calendar_engine.py` + `CalendarService` with stubbed repo + `get_attendance_window`) — **17/17 PASS**: Fri working, Sat/Sun non-working; CalendarService + EligibilityService import the shared constant; MID_SEMESTER_BREAK closure; inactive event ignored; date-range bounding; quiz-window bounds unchanged (Q1 from commencement, day before quiz) with corrected teaching-day dates.
- Read-only DB checks (representative ORM rows inside a rolled-back transaction): /events filters (active/inactive/upcoming/date-range, 8 cases) and dashboard enrollment scoping (temp unenrolled subject ZZZ-999 excluded; 2026-07-15 control still exactly 6 sessions for both test user and Aditya). All transactions rolled back.
- Live read-only SQL confirms DB untouched: academic_events 0 · subjects 9 · class_sessions 684 · attendance_records 84 · enrollments 18 · users 30.

## Database mutation status

- **No INSERT/UPDATE/DELETE persisted.** `academic_events`, `class_sessions`, `attendance_records`, `subjects`, `users`, `student_enrollments` all unchanged. Test rows existed only inside rolled-back transactions. The `attendancedashpro_db` container was started (no data change) for read-only checks.

## Do Not Touch Again (from this phase)

- The weekend convention (`DEFAULT_WEEKENDS` in `calendar_engine.py`) — single source of truth; services must import it, never re-invent literals.
- The /events read contract (active default true, range-overlap dates, upcoming) and the repo's filter semantics.
- The enrollment-scoped dashboard aggregation join.

## Deferred (intentionally NOT done here)

- Calendar UI / month-day calendar / calendar route · Events CRUD · admin role system · event validation registry · event seeding · event→class_sessions integration · EXTRA/CLASS_CANCELLED session mutation · substitution schedule implementation · quiz/event integration · semester/section event scoping · timetable section schema redesign · TodayClassesCard cleanup · engine type-hint refactor · legacy attendance-window field restoration.

---

## PHASE 6.2 - CALENDAR READ MODEL & API

Status: **COMPLETE** (2026-08-14). Backend-only calendar read model for the future Phase 6.3 calendar UI. No UI, no event CRUD, no admin, no seeding, no event→session integration.

## Endpoint contract

- `GET /api/v1/calendar?year=YYYY&month=M` (JWT) — month-bounded calendar read model.
- `year` Query `ge=2000 le=2100`; `month` Query `ge=1 le=12` — FastAPI/Pydantic validation, malformed/out-of-range input → 422 (no custom error semantics).
- Read-only. Returns `CalendarMonthResponse` (never raw ORM).
- Existing endpoints unchanged: `GET /calendar/today`, `GET /calendar/{date}`.

## Read-model structure (CalendarMonthResponse → CalendarDayItem[])

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
- Month entirely outside the semester → `days: []` with inverted `effective_start > effective_end` (truthful empty result, never invented dates).
- No academic context (no section/semester) → `days: []` with null bounds.

## Semester bounding

- Resolved through the same `UserRepository.get_academic_context` used by /student/me, Track and History — no hardcoded dates.
- `effective_start = max(month_start, semester_start)`; `effective_end = min(month_end, semester_end)`; month bounds computed server-side (Dec 12-31 handled).

## Calendar-engine reuse

- Day resolution (`is_working_day`, `is_teaching_day`, `day_type`, `events`, `substitution_schedule_override`) delegates entirely to `calendar_engine.get_academic_day` with the canonical `DEFAULT_WEEKENDS`; no second weekday/closure algorithm. `non_working_reason` is a render-only string derived from the engine's `AcademicDay` output (dominant event title, else "Weekend").
- Phase 6.1 semantics preserved: Fri 2026-08-14 working; Sat/Sun non-working; MID_SEMESTER_BREAK is a closure; inactive events never affect resolution.

## Event handling

- `CalendarRepository.get_all_events(active=True, date_from=effective_start, date_to=effective_end)` — Phase 6.1 /events semantics (active only, date-range overlap). Inactive/past events outside the month never leak into the read model. Empty table → structurally correct calendar with empty `events` arrays.

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

- `compileall backend/app` — PASS; `npx tsc --noEmit` — PASS (0 errors).
- Service-level (live DB, read-only): Aug 2026 semester bounds + effective range + 31 days; Fri 08-14 working, Sat 08-15 / Sun 08-16 non-working with "Weekend" reason; session counts cross-checked against independent enrollment-scoped SQL; Jul 2026 clamp to 07-15; Dec 2026 full month; Jan 2026 / Jan 2027 empty; MID_SEMESTER_BREAK → non-working "Mid Semester Break"; inactive holiday ignored; September holiday excluded from August — 24/24 PASS.
- API contract (in-process httpx ASGITransport on the real `api_router`): 7 validation cases (month 0/13, year 1999/2101, non-numeric, missing params) → 422; valid Aug 2026 → 200 with exact structure; Jan 2027 → 200 empty; `/calendar/today` and `/calendar/{date}` still work — 21/21 PASS.
- Read-only SQL: academic_events 0 · subjects 9 · class_sessions 684 · attendance_records 84 · enrollments 18 · users 30 (unchanged).

## Database mutation status

- **ZERO INSERT/UPDATE/DELETE persisted.** Event rows existed only inside a rolled-back transaction; no test sessions, no attendance, no user/enrollment changes.

## Do Not Touch Again (from this phase)

- The `GET /api/v1/calendar?year=&month=` contract and `CalendarMonthResponse` shape (Phase 6.3 renders it directly).
- `CalendarService.get_month_view` semantics (semester clamp, engine delegation, single-query session counts).

## Deferred (intentionally NOT done here)

- Calendar UI/route, month navigation, date selection, event forms, Upcoming/Today/Past redesign, admin interface — Phase 6.3+. Also deferred: event CRUD, admin roles, validation registry, seeding, event→class_sessions integration, substitution, quiz/event integration, scoping, timetable schema, TodayClassesCard cleanup, type-hint refactor, window-field restoration.

---

## PHASE 6.3 — CALENDAR UI

Status: **COMPLETE** (2026-08-14). Production Calendar UI at `/calendar`, rendering the frozen Phase 6.2 read model directly. Frontend-only; no backend changes; no event CRUD, admin roles, seeding, or event→session integration.

## Route & shell

- `frontend/src/app/(authenticated)/calendar/page.tsx` — authenticated route inside the existing AppShell route group (no second shell, no duplicated auth).
- `TopNav` gains a single `Calendar` item (`CalendarRange`, `/calendar`, between History and Events). Nothing replaced/redesigned; `/tools/events` untouched (Phase 6.4 owns it).

## API integration

- `useCalendarMonth(year, month)` in `frontend/src/hooks/useApi.ts` — SWR hook with stable per-month cache key `GET /api/v1/calendar?year=&month=`; standard cache settings; exposes `mutate` for the retry action. One logical request per month (no per-day requests).
- Types in `frontend/src/types/api.ts`: `CalendarMonthResponse` (year, month, semester_start/end, effective_start/end, days) and `CalendarDayItem` (extends existing `AcademicDayResponse`, adds `non_working_reason`, `session_count`).

## Calendar grid

- `frontend/src/components/calendar/CalendarGrid.tsx` — presentation-only grid. Backend day items are placed on the real local month (Sunday-first alignment matching the backend `getDay()` convention). Cells outside the API's effective range are empty layout placeholders, clearly not academic days.
- Day cells are native buttons: date number, session count when > 0 (working days), event dot/count, non-working reason text; selected state uses the accent ring; today uses a restrained primary ring.
- Zero calendar semantics computed client-side — the UI renders `is_working_day`, `non_working_reason`, `events`, `session_count` exactly as returned. No weekday checks, no holiday inference, no `MID_SEMESTER_BREAK` special-casing, no session counting.

## Month navigation

- Previous/Next/Today, all month-based and timezone-safe (explicit local year/month state; Jan ↔ Dec rollover correct). Navigation beyond backend `semester_start`/`semester_end` is disabled when bounds are known — no hardcoded dates.
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

- `npx tsc --noEmit` — PASS (0 errors).
- `git diff` — backend: no changes (Phase 6.2 contract files untouched); no migrations/schema changes; no attendance/eligibility engine changes; no event CRUD; no fake database events.

## Database mutation status

- **ZERO INSERT/UPDATE/DELETE persisted.** No seeding, no test data, no schema changes.

## Do Not Touch Again (from this phase)

- The `/calendar` route + grid + detail + `useCalendarMonth` hook are the Phase 6.3 UI surface; the Phase 6.2 backend contract remains frozen. `/tools/events` is untouched and owned by Phase 6.4.

## Deferred (intentionally NOT done here)

- Events page upgrade (Upcoming/Today/Past, filters, details) — Phase 6.4. Also deferred: event CRUD, admin roles, validation registry, seeding, event→class_sessions integration, substitution, quiz/event integration, scoping, timetable schema, TodayClassesCard cleanup, type-hint refactor, window-field restoration.
