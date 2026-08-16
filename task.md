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

---

## PHASE 6.4 — EVENTS PAGE UPGRADE

Status: **COMPLETE** (2026-08-14). Production read-only Academic Events page at `/tools/events` (Upcoming/Today/Past grouping + filters). Frontend-only; no backend changes; no event CRUD, admin, or seeding.

## Route & architecture

- `/tools/events` rebuilt inside the existing AppShell/TopNav structure; the backend `GET /api/v1/events` endpoint remains the single data authority (event existence, dates, types, holiday/class metadata, active state).
- Presentation-only grouping: browser-local today (`getLocalDateString`) vs the backend-provided `[start_date, end_date]` — today inside range → **Today**; `end_date` after today → **Upcoming** (start asc); else → **Past** (newest first). No working-day/holiday/closure semantics computed in React.

## Filters

- Event type — client-side over the already-fetched set (the API has no type filter).
- State — Active / Inactive, honestly supported by the Phase 6.1 `active=true|false` contract (no "all" option, since the contract cannot express it in one request).
- From / To — server-side inclusive range-overlap via `date_from`/`date_to`; inverted ranges are blocked client-side with a hint (never sent as a 422).
- Reset button clears everything. One logical request per filter combination.

## Event rendering

- `EventRow` card: date block (day/month), humanized type title (robust for unknown/future types), semantic badges (Today/Holiday/Extra/Cancelled/class type/Inactive), date range (end only when different), substitution-schedule note, and a `Calendar` link affordance to `/calendar` (no query params invented; calendar route untouched).
- Section headings with counts; empty sections show muted placeholder lines.

## Loading / error / empty

- Loading: skeleton sections (no fake empty state before the response resolves).
- Error: events-specific error card with **Try again** via SWR `mutate`; an API failure never renders "No events".
- Empty: "No events scheduled" (truthful zero-row state — `academic_events` has 0 rows) vs "No events match the selected filters".

## Files changed

| File | Change |
|---|---|
| `frontend/src/app/(authenticated)/tools/events/page.tsx` | Rebuilt page (filters, grouping, sections, states) |
| `frontend/src/components/events/EventRow.tsx` | New compact read-only event row |
| `frontend/src/hooks/useApi.ts` | `useEvents(params)` — Phase 6.1 query contract |
| `frontend/src/types/api.ts` | `EventsParams` |

## Verification (static only; no browser testing)

- `npx tsc --noEmit` — PASS (0 errors); ESLint on changed files — PASS.
- `git diff` — backend: no changes; no migrations/schema changes; no attendance/eligibility engine changes; no event CRUD; no fake events.

## Database mutation status

- **ZERO INSERT/UPDATE/DELETE persisted.** No seeding, no test data, no schema changes.

## Do Not Touch Again (from this phase)

- The rebuilt `/tools/events` page + `useEvents(params)` + `EventsParams` are the Phase 6.4 UI surface; the Phase 6.1 `/events` contract and Phase 6.2/6.3 calendar surface remain frozen.

## Deferred (intentionally NOT done here)

- Event persistence/admin auth/seeding — Phase 6.5. Also deferred: event CRUD, admin roles, validation registry, seeding, event→class_sessions integration, substitution, quiz/event integration, scoping, timetable schema, TodayClassesCard cleanup, type-hint refactor, window-field restoration.

---

## PHASE 6.5 — EVENT PERSISTENCE, ADMIN AUTHENTICATION & SEEDING

Status: **COMPLETE** (2026-08-14). Admin role system (`users.role`), admin-only event mutation API, centralized validation registry, minimal admin UI on `/tools/events`, controlled idempotent seeding (17 QUIZ_DAY events). Read contracts (Phase 6.1 events, Phase 6.2 calendar) unchanged; Phase 6.4 student experience unchanged.

## Admin authorization

- `UserRole` (`STUDENT`/`ADMIN`) enum in `backend/app/models/enums.py`; `users.role` column (`backend/app/models/user.py`, default + `server_default` STUDENT); migration `d4e5f6a7b8c9_add_user_role.py` **applied** — 30 existing users backfilled STUDENT.
- `require_admin` in `backend/app/api/dependencies/deps.py` → 403 for non-ADMIN. Role resolved from DB per request (never JWT/body/query/hardcoded); no self-assignment — `backend/scripts/provision_admin.py` only (run for 2401220100027).
- `/student/me` + `/student/sync` now include `role` (`StudentProfile.role`).

## Validation registry & service layer

- `backend/app/services/event_registry.py` — `EVENT_TYPE_RULES` for all 14 types (requiresSubject/requiresClassType/allowedClassTypes/isClosure/isGlobal) ported from legacy `AcademicEventRegistry` + engine closure semantics; `validate_event()`; `EventValidationError`; `VALID_SUBSTITUTION_DAYS` from engine `DAY_NAMES`.
- `backend/app/repositories/event_repo.py` — `EventRepository` (get_by_id, subject_exists, exists_active_duplicate), `EventNotFound`, `EventConflict`.
- `backend/app/services/event_service.py` — create/update (partial via `model_fields_set`)/deactivate; one transaction per mutation.
- Admin-only endpoints in `backend/app/api/v1/endpoints/events.py`: POST (201), PATCH `/{event_id}`, DELETE `/{event_id}` (safe deactivation `active=false`, ADR 004; re-enable via PATCH). Errors: 422 validation, 404 missing event/subject, 409 identical ACTIVE duplicate (ported from legacy js/events-controller.js). `GET` read contract unchanged (list-only).

## Admin UI (additive to Phase 6.4)

- `frontend/src/components/events/eventRules.ts` (NEW) — registry mirror for form field visibility; backend registry authoritative.
- `frontend/src/components/events/EventFormDialog.tsx` (NEW) — create/edit dialog; only model-real fields; client-side checks; handles loading + 403/404/409/422.
- `frontend/src/components/events/EventRow.tsx` — optional `onEdit`/`onDeactivate` admin actions (two-step inline deactivate confirm).
- `frontend/src/app/(authenticated)/tools/events/page.tsx` — admin mode gated by `useProfile().role === "ADMIN"`: Add Event toolbar, row actions, dialog; after save/deactivate → `mutate()` + current-month calendar revalidation. Students: unchanged Phase 6.4 page.
- `frontend/src/hooks/useApi.ts` — `useEventMutations()`; `frontend/src/types/api.ts` — `AcademicEventPayload`, `StudentProfile.role`.

## Seeding

- **Data gap (documented):** no authoritative institutional holiday/break/working-Saturday dates exist anywhere in the repo — nothing seeded for them.
- `backend/scripts/seed_academic_events.py` — 17 QUIZ_DAY events derived from the authoritative `quiz_schedules` (17 SCHEDULED; BCS-054 Q3 UNRESOLVED skipped as unscheduled). Idempotency key `(event_type, subject_id, start_date, end_date)`; rerun verified 17→17 skipped; deactivated rows never resurrected.

## Verification

- Backend: `compileall` PASS; `alembic upgrade head` applied (head `d4e5f6a7b8c9`); `verify_phase_6_5.py` **23/23 PASS** (security matrix STUDENT/ADMIN/unauth, create, 409 duplicate, 404 subject, partial PATCH absent-vs-null, deactivate + re-enable, read-contract regression student+calendar, seed idempotency, cleanup).
- Frontend: `npx tsc --noEmit` PASS; ESLint PASS on changed files; `npm run build` PASS. Browser testing deferred to the user.

## Database mutation status

- **Schema:** `users.role` added + backfilled (migration `d4e5f6a7b8c9`). **Data:** 17 seeded QUIZ_DAY events inserted (`academic_events`); 1 user set ADMIN (2401220100027); verifier test rows created then deleted. **Untouched:** attendance_records, class_sessions (684), student_enrollment, subjects, quiz_schedules, all user history.

## Do Not Touch Again (from this phase)

- Backend is the single authority for roles, event validation, and mutations; the frontend admin surface is UX only. `GET /api/v1/events` remains list-only. DELETE = deactivation (reversible), never a hard delete.

## Deferred (intentionally NOT done here)

- Phase 6.6 — event→engine integration (event→class_sessions generation, holiday→cancellation, extra/substitution lecture generation, quiz-window mutation) — explicit next phase, NOT implemented here.
- Phase 6.7 — verification/freeze. Institutional holiday/break/working-Saturday dates pending authoritative input.

---

# PHASE 6.6 — EVENT → ENGINE INTEGRATION

Status: **COMPLETE** (2026-08-14). Persisted events now mutate the canonical session pipeline — closures cancel, CLASS_CANCELLED cancels exactly one occurrence, EXTRA_*/SURPRISE_QUIZ materialize `is_extra` sessions, substitution/working-Saturday project the substituted timetable — exactly as the legacy engine's effective schedule dictated. Idempotent, transactional, attendance-safe. No engine rewrites, no schema change, no frontend change.

## What was done

1. **Session synchronizer** (`backend/app/services/event_session_service.py`): `EventSessionSynchronizer.sync_event()` — per-date desired schedule from the frozen calendar engine + legacy `getEffectiveDaySchedule` port (base timetable − one per CLASS_CANCELLED + one per EXTRA_*/SURPRISE_QUIZ, deterministic priority→id order), reconciled against `class_sessions`:
   - Closures & CLASS_CANCELLED → `is_cancelled=True` (rows never deleted; cancelled ≠ absent).
   - Extras → `is_extra=True` rows without timetable entries.
   - Working Saturday / substitution → timetable-materialized rows (weekend projections deleted when reverted; attended rows never touched).
   - State-based ⇒ idempotent (double sync converges); date-scoped ⇒ deactivation/move automatically reverts old effects.
   - Sessions only created within the baseline span (2026-07-15 → 2026-12-31).
2. **Session repository** (`backend/app/repositories/session_repo.py`): timetable/span/range reads + attendance-guard + `add_session` / `delete_session`.
3. **Service wiring** (`backend/app/services/event_service.py`): sync runs in the same transaction as create/update/deactivate; updates sync the union of old+new ranges so moved events revert the old dates.
4. **Counting corrections** (cancelled ≠ pending): `attendance_repo` (both count queries), `dashboard_service` (`_build_overall`, `_build_weekly`), `calendar_service` (`get_month_view` session_count) now exclude `is_cancelled`. Shapes/engines unchanged.
5. **Verification** (`backend/scripts/verify_phase_6_6.py`): **36/36 PASS** — closure→5 cancelled (none deleted), attended-guard (07-15 untouched), CLASS_CANCELLED→exactly 1 + total −1, extra→+1 & restored, double-sync idempotency, SURPRISE_QUIZ, QUIZ_DAY no-op, working-Saturday (5 materialized), PATCH move reverts old date, calendar/daily/eligibility read contracts, deactivation reversal for all types, rollback-tx checks (attended extra preserved; 3-day range → 3 extras; deactivation no-op on 2nd sync), final exact baseline (17/684/0/0/89). 6.5 regression 23/23 PASS.

## Database state after 6.6

- Exactly the pre-6.6 baseline: events=17, sessions=684 (0 cancelled, 0 extra), attendance_records=89, enrollments=18, subjects=9, quiz_schedules=18, users=30 (1 ADMIN). Test rows hard-deleted; rollback tests committed nothing.

## Do Not Touch Again (from this phase)

- Event↔session semantics live ONLY in `EventSessionSynchronizer`; consumers must not re-derive them. Cancelled sessions are never deleted and never receive attendance (409). Engine mathematics remain frozen.

## Deferred (intentionally NOT done here)

- Phase 6.7 — verification/freeze (explicit next phase, requires go-ahead). Institutional holiday/break/working-Saturday dates pending authoritative input.

---

# PHASE 6.7 — CALENDAR & ACADEMIC EVENTS VERIFICATION / FREEZE

Status: **COMPLETE / FROZEN** (2026-08-15). Phase 6 is verified end-to-end and frozen. This was NOT a feature phase — no engine rewrites, no schema redesign, no frontend changes, no new business logic.

## What was done

1. **`backend/scripts/verify_phase_6_7.py` (NEW) — 31/31 PASS**, closing every gap not covered by the 6.5/6.6 verifiers:
   - **6.1 contracts:** `DEFAULT_WEEKENDS=[0,6]` (JS convention Sunday=0, Saturday=6); MID_SEMESTER_BREAK is a closure sharing SEMESTER_BREAK's tier 60; `/events` active-default, inverted range → 422, `upcoming=true`.
   - **6.2 read model:** truthful empty month outside semester (Jan 2026); July clamps to 2026-07-15; December respects 2026-12-31; weekends correct; QUIZ_DAY stays a working day.
   - **6.5:** seeding integrity (17/17 QUIZ_DAY, all active, nothing fabricated, matches SCHEDULED quiz_schedules); deactivate → PATCH re-enable converges.
   - **6.6:** all five additional closure types cancel every session on their date (rows preserved, day non-working); EXTRA_TUTORIAL/EXTRA_PRACTICAL → exactly one `is_extra` each; WORKING_DAY_OVERRIDE → working day, zero session mutation; cancelled session → **409** on attendance.
   - **Baseline:** 10-table exact restoration (17/684/0/0/89/18/9/18/30/1).
2. **Regression:** 6.5 → 23/23, 6.6 → 36/36, 6.7 → 31/31 = **90/90**; `compileall` PASS; verifiers converge in any order.
3. **Static review:** calendar + events UIs are presentation-only; layering API→Service→Repository→DB intact; `EventSessionSynchronizer` sole sync path; no engine rewrites; no hardcoded dates in `app/`; no N+1; role from DB per request; no schema change beyond the 6.5 migration.

## Database state after 6.7

- Exact baseline: events=17, sessions=684 (0 cancelled, 0 extra), records=89, enrollments=18, subjects=9, quizzes=18, users=30 (1 ADMIN). No test residue.

## Do Not Touch Again (from this phase)

- Phase 6 is **FROZEN**: calendar engine semantics, events/calendar API contracts, calendar/events UI, event registry, event service + synchronizer wiring, the three verifiers, and the documented baseline. Any change requires a new phase with its own verification.

---

# PHASE 7.0 — QUIZ ELIGIBILITY & SCHEDULE REALITY AUDIT

Status: **COMPLETE** (2026-08-15) — READ-ONLY audit, **PASS** (no defects to fix; discrepancies reported for decision). No implementation, no DB mutation, no commit.

## What was audited

1. **Eligibility path:** `GET /api/v1/quiz-eligibility/{code}/{cycle}` → `EligibilityService` → `calendar_engine.get_attendance_window` → `attendance_repo.get_subject_counts_between` → `eligibility_engine.evaluate_quiz_eligibility` → `meets_attendance_target`/`optimize_attendance`.
2. **Schedule reality:** quiz_cycles/eligibility_policies (70/75/75), 18 quiz_schedules (17 dated SCHEDULED; **BCS-054 Q3 UNRESOLVED**), 17 QUIZ_DAY events, semester V (2026-07-15 → 2026-12-31), 9 subjects (6 theory + 3 labs).
3. **Legacy parity:** `js/quiz-engine.js`, `attendance-engine.js`, `calendar-engine.js`, `ui.js`, docs 05/06/07/15, `S4_PRODUCT_SPEC`, ADR-010.
4. **Live math trace:** engine-in-process against the real DB for student `9999999999999` (0 records) and admin `2401220100027` (84 records, overall 71.43% recorded-only / 46.51% incl. pending).

## Verification summary

- Formula + window + optimizer parity with legacy: **PASS** (byte-equivalent rules; identical ADR-010 window bounds).
- Practical exclusion from eligibility, inclusion in overall: **PASS**.
- Quiz-day attendance via normal sessions; SURPRISE_QUIZ/EXTRA_* via `is_extra` sessions: **PASS** (architecture-level).
- DB baseline re-confirmed: 17/684/0/0/89/18/9/18/30/1. **DB mutation status: NONE.**
- Discrepancies (reported, NOT fixed): Q-D1 eligible-vs-reachable semantics (all 18 subject×cycle results say eligible=True today; legacy says "NEEDS ATTENDANCE"); Q-D2 reference-UI data contract unavailable from the API; Q-D3 single-rule vs "(Criterion 1) OR (Criterion 2)"; Q-D4 hardcoded `quiz_applicable=True`; Q-D5 `combined_threshold` never read; Q-D6 raw-range counting (latent); **Q-D7 rule G students-add/remove-events vs frozen admin-only mutations**; Q-D8 overall denominator; Q-D9 quiz-day attendance without a session; Q-D10 BCS-054 Q3 date.

## Database state after 7.0

- Exact baseline preserved (no writes): events=17, sessions=684 (0 cancelled, 0 extra), records=89, enrollments=18, subjects=9, quizzes=18, users=30 (1 ADMIN).

## Do Not Touch Again (from this phase)

- Same as Phase 6.7 (frozen list) plus: **the audit is documentation-only** — the eligibility engine, eligibility API contract, and the frozen Phase 6 event system remain untouched until Q-D1…Q-D10 are decided and Phase 7.1 is authorized.

## Deferred (intentionally NOT done here)

- Institutional holiday/break/working-Saturday dates — pending authoritative product input (documented data gap).
- Browser/manual testing — the user's responsibility (no automation run).

---

# PHASE 7.1 — CANONICAL QUIZ ELIGIBILITY CONTRACT + REFERENCE SUBJECT CARDS

Status: **COMPLETE (2026-08-15) — PASS** (26/26 verification + full regression). Report: `docs/phase_7_1_implementation_report.md`.

## What was implemented

1. **Schedule:** BCS-054 Q3 → 2026-10-23 SCHEDULED (from `timetable.json`; seed-script override removed). `seed_academic_events.py` created the 18th QUIZ_DAY event (calendar-only). Canonical schedule = 18/18 dated SCHEDULED, byte-exact vs timetable.json. Q1/Q2 windows unchanged; Q3 window [09-28 … 10-22].
2. **Contract (`EligibilityResult` extended additively):** `state` (ELIGIBLE/RECOVERABLE/NOT_ELIGIBLE/UNRESOLVED), `subject_name`, `category`, `quiz_date`, `lecture`/`tutorial` counts + `lecture_pct`/`tutorial_pct`/`average_pct`, `required_percentage`, `criterion_i`/`criterion_ii` (value/threshold/passed/explanation), `final_criterion` ("Criterion I OR Criterion II"), `recoverable`, `explanation`. `is_eligible` = currently eligible (Q-D1 fixed). Thresholds from `eligibility_policies` for both routes (Q-D5 fixed). Labs → 404 via `subjects.quiz_applicable` (Q-D4 fixed). Optimization fields byte-identical to the attendance engine.
3. **Engine:** additive extension at the documented extension point (no rewrite, no second math model): criteria + state from the same counts at current and best-case scenarios; `optimize_attendance`/`meets_attendance_target`/`get_attendance_window` untouched.
4. **UI:** `/tools/quiz-schedule` → "Quiz Eligibility": cycle tabs (Quiz I/II/III, default Quiz I), reference subject cards (code, THEORY badge, name, status badge, attended/total/%, average vs required, expandable View Calculation incl. must-attend/safe-skip), loading skeletons, error+Retry, empty/unresolved states. React presentation-only (no business math). Old `SubjectQuizSchedule.tsx` removed.
5. **Dashboard:** no changes (frozen) — snapshot becomes truthful via corrected `is_eligible`.

## Verification summary

- `verify_phase_7_1.py`: **26/26 PASS** (canonical schedule vs timetable.json; BCS-054 Q3; cycles; practical exclusion; QUIZ_DAY calendar-only; 18 upcoming; Q1/Q2/Q3 windows; lecture-only + L+T formulas; RECOVERABLE real data; ELIGIBLE/NOT_ELIGIBLE/UNRESOLVED rollback scenarios; Criterion I/II + final OR; optimizer parity; UI analytics contract; labs 404; per-user scoping; history intact 89 records; quiz-day + surprise-quiz canonical; exact baseline restore).
- Frozen regression: 6.5 **23/23** · 6.6 **36/36** · 6.7 **31/31** (Phase 6.7 count assertions maintained 17→18 for the new authoritative schedule — documented, not weakened).
- Static: compileall clean · tsc clean · ESLint 0 errors · `next build` exit 0.

## Database state after 7.1

- New baseline (verified post-run): events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN).
- Mutation (minimal, reversible): BCS-054 Q3 `quiz_schedules` row → 2026-10-23 SCHEDULED; one QUIZ_DAY event seeded by the canonical script. Reversal documented in the implementation report.

## Do Not Touch Again (from this phase)

- Same as Phase 6.7 (frozen list), plus: Phase 7.1 eligibility state derivation, criteria contract, and the reference-card API fields are now the canonical contract — changes require a new phase with its own verifier. The Phase 6.7 verifier's authoritative counts (18) are maintained, not weakened.

## Deferred (intentionally NOT done here)

- Q-D6 teaching-day counting · Q-D8 overall denominator · Q-D7 student event-mutation capability (product/security decision) · date-aware default cycle tab.
- Browser/manual testing — the user's responsibility (see MANUAL TESTING CHECKLIST in the implementation report).

---

# PHASE 7.2 — QUIZ ELIGIBILITY ANALYTICS REFINEMENT

Status: **COMPLETE (2026-08-15) — PASS** (26/26 verification + full regression). Report: `docs/phase_7_2_implementation_report.md`.

## What was decided & implemented

1. **Q-D6 (raw-range counting) — NOT a defect under the locked spec.** The `class_sessions` table IS the teaching-day-resolved effective schedule (baseline expands only teaching days; closures cancel; extras only on working days; cancelled excluded from counts). No counting change. Regression-proven: all 18 subject/cycle combos equal a teaching-day enumeration with no off-teaching-day session counted; closure cancels → excluded + 409; EXTRA_LECTURE on a working day counted; SURPRISE_QUIZ on a non-working day materializes ZERO sessions (no divergence possible via the canonical event path).
2. **Q-D8 (overall denominator) — recorded-only, ERP/legacy semantics.** Pending excluded from the CURRENT denominator (legacy `computeCurrentOverallAttendance`, S4 §10) but never converted to absent — always counted and shown separately. Dashboard overall card already showed pending; the quiz eligibility card now shows a muted "· X pending" on Lecture/Tutorial rows (reference visual language otherwise untouched). Verified: 71.43% recorded-only vs explicitly-not 46.51%; history + subject current/forecast identical semantics; zero-record student overall = null.
3. **Q-D7 (mutation / eligibility timing) — intentional product restriction (B).** Attendance mutations are student-scoped + enrollment-authorized (403) + cancelled-protected (409); EVENT mutations stay admin-only (frozen 6.5 — rule G is a future product capability). Eligibility is computed read-time — a mutation propagates to the next read immediately (verified).
4. **Date-aware default Quiz tab.** New canonical read-only `GET /api/v1/quiz-eligibility/current-cycle`: next upcoming SCHEDULED quiz → latest resolved cycle → fallback Quiz I (never invents dates). The Quiz Eligibility page preselects the tab from it (`useCurrentQuizCycle`); manual tab selection overrides; tab state is client-only. Today → Quiz I (next quiz 2026-08-24); Quiz I→II→III→latest_resolved→fallback transitions verified in rollback transactions.

## Verification summary

- `verify_phase_7_2.py`: **26/26 PASS** (Q-D6 ×4 · Q-D8 ×5 · Q-D7 ×4 · current-cycle ×6 · BCS-054 Q3 · UNRESOLVED · labs 404 · dashboard-snapshot==canonical · Track/History/Eligibility consistency · per-user isolation · exact baseline restore).
- Frozen regression: 6.5 **23/23** · 6.6 **36/36** · 6.7 **31/31** · 7.1 **26/26** — no assertions weakened.
- Static: compileall clean · `npx tsc --noEmit` clean · ESLint 0 errors · `next build` exit 0.

## Database state after 7.2

- Exact baseline preserved (ZERO mutations): events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN) · max record date 2026-08-14. BCS-054 Quiz III = 2026-10-23 confirmed.

## Do Not Touch Again (from this phase)

- Same as Phase 6.7 + 7.1 (frozen lists), plus: the current-cycle endpoint contract, the Q-D6/Q-D8/Q-D7 documented decisions, and the quiz-card pending indicator are now canonical — changes require a new phase with its own verifier. No commit was made.

## Deferred (intentionally NOT done here)

- Q-D9 quiz-day attendance without a session (product decision) · rule G student event capability (product/security decision) · Phase 8 Attendance Analytics/Intelligence (roadmap next).
- Browser/manual testing — the user's responsibility.

---

# PHASE 8.0 — ATTENDANCE ANALYTICS & INTELLIGENCE: AUDIT / CONTRACT DESIGN

Status: **COMPLETE (2026-08-15) — PASS** (read-only audit; zero code, zero DB change).
Report: `docs/phase_8_0_attendance_analytics_audit.md`.

## Objective

Establish the exact architectural and mathematical contract for Phase 8 (Attendance Analytics / Intelligence) BEFORE any implementation. No analytics API, no analytics UI, no migrations, no new engines, no attendance/eligibility math changes, no DB mutation.

## Findings

- [x] **Architecture:** no analytics layer exists; `dashboard_service` is the de-facto aggregator and already consumes the canonical engines (no second engine). React performs no business math today.
- [x] **Inventory (23 metrics):** overall/weekly/today %, subject current/forecast %, quiz-window %, eligibility states, optimizer deficits, history summary, banding — each with pending/cancelled/extra/practical/semester/quiz-window treatment. All current % recorded-only; pending never absent; cancelled excluded; extras included; ERP overall class-weighted; labs excluded from eligibility.
- [x] **4 legacy gaps (additive, NOT new formulas):** practical % not exposed · subject-level 75% must-attend/safe-skip not exposed · overall forecast not exposed · forecast-impact deltas not exposed.
- [x] **React duplications flagged (NOT fixed):** `WeeklyAttendanceCard` re-derives day-bar %; `SubjectAttendanceCard` 75/65 banding vs canonical 80/60 + hardcoded cycle=1; dead `TodayClassesCard`/`FormulaCard`.
- [x] **Performance (latent, NOT fixed):** N+1 dashboard quiz snapshot + subject summaries; overlapping range scans; import-time `date.today()` default.
- [x] **Security:** all reads authenticated + user/enrollment-scoped; one gap flagged (`/attendance/summary/{code}` lacks enrollment 404 — consistency only, no leak).
- [x] **Withheld (no definition):** AT-RISK state; weekly/semester trend series — candidate definitions in audit §J/§T for product approval.
- [x] **Proposed 8.1 contract (not implemented):** extend `SubjectAttendanceSummary` (practical %, subject-level optimization, enrollment scope) + new `GET /api/v1/analytics/overview` (overall current/forecast/pending + weekly series + per-subject optimization) + dashboard N+1 fixes + `verify_phase_8_1.py`.

## Verification

- `python -m compileall app scripts` — PASS · `npx tsc --noEmit` — PASS (0 errors) · `verify_phase_7_2.py` — 26/26 PASS (frozen verifier).
- DB baseline (read-only SELECT): events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN) · BCS-054 Q3 = 2026-10-23. **DB mutation status: ZERO.**

## Do Not Touch Again (from this phase)

- Same frozen lists as 6.7/7.1/7.2, plus: the Phase 8.0 audit decisions (recorded-only current, ERP overall, AT-RISK + trends withheld, legacy gaps additive-only) are the contract for Phase 8.1.

## Deferred (intentionally NOT done here)

- Phase 8.1 implementation (requires explicit product authorization after review of the audit). Q-D9 and rule G remain separate product decisions.
- Browser/manual testing — the user's responsibility.

---

# PHASE 8.1 — CANONICAL ANALYTICS READ MODEL

Status: **COMPLETE (2026-08-15) — PASS** (backend-only additive read model; zero DB mutation, zero schema change, zero commit).
Report: `docs/phase_8_1_implementation_report.md`.

## Objective

Implement ONLY the backend analytics read-model contract from Phase 8.0: extend `SubjectAttendanceSummary` (practical %, subject-level 75% must-attend/safe-skip, enrollment scope), add `GET /api/v1/analytics/overview` (overall current/forecast/pending + weekly series + per-subject analytics), fix dashboard N+1s, fix the import-time date default, close the enrollment-scope gap. No UI, no AT-RISK, no trend semantics, no new formulas, no new engines.

## Implemented

- [x] **Subject analytics (additive):** `SubjectAttendanceSummary` + `current_practical_pct`, `forecast_practical_pct`, `optimization` (`lecture_deficit`/`tutorial_deficit` = must-attend, `safe_skip_lecture`/`safe_skip_tutorial` = safe-skip) via the canonical engine's `optimize_attendance`; practicals use the canonical session/record pipeline (no quiz-window dependency, no lab engine); Pending stays Pending; cancelled excluded. Existing fields unchanged.
- [x] **`GET /api/v1/analytics/overview`** (authenticated, enrollment-scoped, read-only, deterministic, no raw ORM): overall current = ERP Σatt/Σrecorded (recorded-only); overall forecast = pending-as-attended; pending count; Monday-start weekly read-model series (recorded-only, null gaps); per-subject current/forecast/optimization. AT-RISK / trend semantics / forecast-impact deltas NOT implemented (documented non-goals).
- [x] **Dashboard N+1 fixes (contract-identical):** batched `get_quiz_eligibility_for_subjects` (single canonical engine path), grouped `get_subject_counts_for_user`, one shared range scan for Today/Overall/Weekly; dashboard JSON byte-identical; measured 54 → 23 queries.
- [x] **Endpoint hygiene:** `/attendance/summary` default date resolved per-request; `/attendance/summary/{code}` enrollment 404 (quiz-endpoint pattern).

## Files changed

- Backend: `schemas/attendance.py` · NEW `schemas/analytics.py` · `services/attendance_service.py` · NEW `services/analytics_service.py` · `services/eligibility_service.py` · `services/dashboard_service.py` · `repositories/attendance_repo.py` · `repositories/quiz_repo.py` · NEW `api/v1/endpoints/analytics.py` · `api/v1/endpoints/attendance.py` · `api/api.py`.
- Scripts: NEW `scripts/verify_phase_8_1.py`.
- Docs: NEW `docs/phase_8_1_implementation_report.md`; `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md`.
- DB: **NONE**.

## Verification

- `verify_phase_8_1.py` **22/22** (auth; enrollment scoping; ERP overall; forecast; pending; subject summaries; practical %; must-attend/safe-skip + optimizer edge cases; weekly read model; dashboard compatibility + N+1 correctness with query counting; runtime-date behavior; enrollment protection; no duplicate attendance math; exact baseline; frozen 7.2 invariants).
- Frozen regression: 6.5 **23/23** · 6.6 **36/36** · 6.7 **31/31** · 7.1 **26/26** · 7.2 **26/26** — no assertion weakened.
- Static: `python -m compileall app scripts` PASS · `npx tsc --noEmit` PASS (0 errors).

## Database state after 8.1

- Exact baseline preserved (ZERO mutations): events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN). BCS-054 Quiz III = 2026-10-23 confirmed.

## Do Not Touch Again (from this phase)

- Same frozen lists as 6.7/7.1/7.2/8.0, plus: the extended `SubjectAttendanceSummary` fields, the `/analytics/overview` contract, the batched dashboard paths, and the runtime-date/enrollment-scope fixes are now canonical — changes require a new phase with its own verifier. No commit was made.

## Deferred (intentionally NOT done here)

- Frontend consumption of the read model (Phase 8.2) · AT-RISK (T-1) · trend product semantics (T-2) · dedicated Analytics page (T-3) · multi-class forecast phrasing (T-4) · Q-D9 · rule G.
- Browser/manual testing — the user's responsibility.

---

# PHASE 8.2 — FRONTEND CONSUMPTION OF THE CANONICAL ANALYTICS READ MODEL

Status: **COMPLETE (2026-08-15) — PASS** (frontend-only; zero backend change, zero DB mutation, zero commit).

## Objective

Consume the Phase 8.1 backend read model in the existing Next.js frontend: typed analytics client, backend practical % + subject 75% must-attend/safe-skip on Subjects, overall forecast + weekly series on Dashboard, remove duplicated React banding/percentage math and the hardcoded quiz cycle, delete dead components. No new analytics engine, no React business math, no AT-RISK, no trend semantics, no redesign.

## Implemented

- [x] **Typed analytics client:** `AnalyticsOverviewResponse`/`OverallAnalytics`/`WeeklyAnalyticsItem`/`AnalyticsSubjectItem` (exact backend match) + extended `SubjectAttendanceSummary` (`current_practical_pct`, `forecast_practical_pct`, `optimization`) + `useAnalyticsOverview()` hook.
- [x] **Subjects page:** one overview request feeds all cards (N+1 removed); cards render backend practical %/forecast and must-attend/safe-skip from `summary.optimization`; duplicated 75/65 banding removed (no backend subject status exists — none invented); `cycle = 1` replaced by canonical `useCurrentQuizCycle()`.
- [x] **Dashboard:** additive backend forecast line on `OverallAttendanceCard`; `WeeklyAttendanceCard` renders the backend weekly series (null = truthful gap, never 0%) — no React percentage derivation.
- [x] **Dead components removed:** `TodayClassesCard.tsx`, `FormulaCard.tsx` (verified zero imports/routes).

## Files changed

- Frontend: `src/types/api.ts` · `src/hooks/useApi.ts` · `src/components/dashboard/SubjectAttendanceCard.tsx` · `src/components/dashboard/SubjectAttendanceGrid.tsx` · `src/components/dashboard/home/OverallAttendanceCard.tsx` · `src/components/dashboard/home/WeeklyAttendanceCard.tsx` · `src/app/(authenticated)/dashboard/page.tsx` · DELETED `TodayClassesCard.tsx` · DELETED `FormulaCard.tsx`.
- Docs: `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md`.
- Backend: **NONE**. DB: **NONE**.

## Verification

- `npx tsc --noEmit` PASS (0 errors) · ESLint clean on all changed files · `next build` PASS (14 routes).
- Static inspection confirms: no attendance formulas, no safe-skip math, no eligibility math, no quiz-cycle logic in React; all rendered values are backend fields.

## Database state after 8.2

- **ZERO mutation** — no backend/database files touched. Phase 8.1 baseline unchanged.

## Do Not Touch Again (from this phase)

- Same frozen lists as 6.7/7.1/7.2/8.0/8.1, plus: the analytics overview consumption pattern (single overview request for per-subject analytics), the backend-driven subject/overall/weekly rendering, and the canonical-cycle eligibility badge are now canonical — changes require a new phase. No commit was made.

## Deferred (intentionally NOT done here)

- AT-RISK (T-1) · trend product semantics (T-2) · dedicated Analytics page (T-3) · multi-class forecast wording (T-4) · Q-D9 · rule G.
- Browser/manual testing — the user's responsibility.

---

# ATTENDANCE UI REFINEMENT — SPECIFICATION ALIGNMENT + REFERENCE UI

Status: **COMPLETE (2026-08-15) — PASS.** Full report: `docs/attendance_ui_refinement_report.md`. Two spec conflicts were escalated and **authorized by the user**.

## Objective

Align the implementation with the authoritative attendance specification (lecture/tutorial daily marking; (L%+T%)/2 average with L%-only fallback; practicals counted in attendance + overall but excluded from quiz eligibility; event-weighted overall; quiz-day attendance as a real event; student-adjustable events; calendar day = whole schedule) and implement the reference Attendance UI without introducing React business math.

## Authorized decisions (user)

1. **Quiz-day attendance → materialize sessions** on every SCHEDULED quiz date (7 created; 684 → 691; eligibility untouched since windows end at quiz_date − 1).
2. **Events → shared schedule, subject-scoped**: students may add/remove flexible subject-scoped events for their own enrollments; global/closure events remain admin-only.

## Implemented

- [x] Quiz-day sessions materialized (`scripts/materialize_quiz_day_sessions.py`, idempotent + `--undo`); all 18 quiz dates recordable; subject + overall attendance include them.
- [x] Student event authorization (backend): `STUDENT_CREATABLE_EVENT_TYPES` + enrollment check; global/closure/quiz-schedule events stay 403; synchronizer guard protects quiz-day sessions from event reconciliation.
- [x] Reference Attendance cards: header (code · THEORY/LAB · name · canonical status), primary %, lecture/tutorial sections (required 75 · must-attend · safe-skip), combined average with formula caption, practical section for labs, expandable Details with backend forecast/optimizer values. Backend emits `required_pct` + `status` additively; banding consolidated in the attendance engine.
- [x] Student event UI (Events page + form restricted to flexible subject-scoped types).
- [x] Latent fix: `AttendanceMutationResponse.student_id` → `user_id` (successful attendance mutations previously 500'd).

## Files changed

- Backend: `engines/attendance_engine.py` · `schemas/attendance.py` · `services/attendance_service.py` · `services/event_service.py` · `services/event_session_service.py` · `services/dashboard_service.py` · `services/analytics_service.py` · `repositories/event_repo.py` · `api/v1/endpoints/events.py` · `api/v1/endpoints/attendance.py`.
- Scripts: NEW `materialize_quiz_day_sessions.py` · NEW `verify_attendance_spec_alignment.py` · `verify_phase_6_5.py` · `verify_phase_7_2.py` · `verify_phase_7_1.py` · `verify_phase_6_7.py` (deliberate assertion updates).
- Frontend: `src/types/api.ts` · `src/components/dashboard/SubjectAttendanceCard.tsx` · `src/components/events/EventFormDialog.tsx` · `src/components/events/eventRules.ts` · `src/app/(authenticated)/tools/events/page.tsx`.
- Docs: `MASTER_ROADMAP.md` · `implementation_plan.md` · `task.md` · `walkthrough.md` · NEW `docs/attendance_ui_refinement_report.md`.

## Verification

- `verify_attendance_spec_alignment.py` **15/15**; frozen regressions 6.5 **27/27** · 6.6 **36/36** · 6.7 **31/31** · 7.1 **26/26** · 7.2 **26/26** · 8.1 **22/22** (deliberate documented re-scopes in 6.5/7.2/7.1 only).
- compileall PASS · `npx tsc --noEmit` PASS (0 errors) · ESLint clean · `next build` PASS (14 routes).

## Database state after refinement

- **Documented, authorized, minimal**: sessions 684 → **691** (7 quiz-day LECTURE sessions, `timetable_entry_id IS NULL`, `is_extra=false`, non-cancelled, no records; reversible via `--undo`). Events=18 · cancelled=0 · extra=0 · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN). BCS-054 Quiz III = 2026-10-23 unchanged.

## Do Not Touch Again

- The quiz-day session semantics, student event authorization policy, consolidated banding, `required_pct`/`status` fields, and the attendance-mutation response contract are now canonical — changes require a new phase with its own verifier. No commit was made.

## Deferred (intentionally NOT done here)

- AT-RISK (T-1) · trend product semantics (T-2) · dedicated Analytics page (T-3) · multi-class forecast wording (T-4) · Q-D9 · rule G.
- Browser/manual testing — the user's responsibility.

---

## Phase 8.2 — Attendance Monitoring + Lab Domain Correction

Correct the Attendance (/subjects) page so it is attendance-monitoring only (no quiz strategy), introduce a canonical backend-owned Attendance Health classification, and establish the laboratory domain foundation with a session-bound mid-sem designation.

## Root cause (traced)

- The "11 / 14" denominator is NOT a quiz window: it is the canonical count of non-cancelled `class_sessions` <= today (14 real lectures through 2026-08-15 for every theory subject; no fixed constant anywhere). The Attendance page's real defect was presenting quiz strategy (must-attend / safe-skip / forecast / current-vs-forecast / required 75% / Defaulter badge) and the legacy SAFE/WATCH/CRITICAL banding.

## Implemented

- [x] Attendance Health (backend-owned, additive `health` on `SubjectAttendanceSummary`): HEALTHY >= 75 · WATCH 65–<75 · AT RISK 60–<65 · CRITICAL <60; canonical engine definition; legacy `status` untouched for frozen consumers; React never bands.
- [x] Attendance card redesigned (attendance-only): code · THEORY/LAB · name · Health badge; large "Overall Attendance" %; balanced Lecture/Tutorial blocks (attended/total + %); formula caption; lab cards show Practical Attendance + backend-backed "Mid-Sem Practical" row; View Details = attended/missed/pending only. No quiz strategy anywhere.
- [x] Laboratory domain separation: practical attendance stays canonical `ClassSession(PRACTICAL)` + `AttendanceRecord`; experiment curriculum/progress (`laboratory_experiments`/`laboratory_records`) untouched and empty (no fabricated data).
- [x] Mid-sem practical: smallest safe foundation — `class_sessions.designation` (nullable enum, migration `e5f6a7b8c9d0`), ADMIN-only `PUT/DELETE /api/v1/laboratory/{code}/mid-sem` + read, tied to an actual PRACTICAL session (never inferred from experiment count, never a computed date); attendance against it flows through the normal mutation; one per subject, replaceable, clearable.
- [x] Verification `verify_phase_8_2.py` 18/18; frozen regressions 6.5 27/27 · 6.6 36/36 · 6.7 31/31 · 7.1 26/26 · 7.2 26/26 · 8.1 22/22 · attendance-spec 15/15; compileall / tsc / ESLint / next build green.

## Files changed

- Backend: `engines/attendance_engine.py` · `models/enums.py` · `models/timetable.py` · `schemas/attendance.py` · `services/attendance_service.py` · `repositories/attendance_repo.py` · `services/laboratory_service.py` (NEW) · `api/v1/endpoints/laboratory.py` · `schemas/laboratory.py` · `alembic/versions/e5f6a7b8c9d0_add_session_designation.py` (NEW).
- Scripts: NEW `verify_phase_8_2.py` · `verify_phase_7_1.py` (check 23 **authorized fixed re-baseline `records == 89` → `records == 92`** — the +3 are legitimate BCS-501 marks entered through the canonical attendance mutation path before the audit; the assertion keeps a FIXED expected count, no dynamic baseline).
- Frontend: `src/types/api.ts` · `src/components/dashboard/SubjectAttendanceCard.tsx` · `src/app/(authenticated)/subjects/page.tsx`.
- Docs: `MASTER_ROADMAP.md` · `implementation_plan.md` · `task.md` · `walkthrough.md` · NEW `docs/phase_8_2_implementation_report.md`.

## Database state

- Migration `e5f6a7b8c9d0` applied (additive nullable column). Baseline unchanged: events=18 · sessions=691 (0 cancelled, 0 extra) · records=92 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN) · laboratory tables empty · designations=0. BCS-054 Quiz III = 2026-10-23 unchanged.

## Do Not Touch Again

- Attendance Health classification, the attendance-only card contract, the mid-sem designation semantics/endpoints, and the `health`/`mid_sem_*` summary fields are canonical — changes require a new phase with its own verifier. No commit was made.

## Deferred (intentionally NOT done here)

- Authoritative experiment titles/curriculum (unavailable), faculty scheduling system (missing authority boundary — documented), "Lab Progress N/10" on the Attendance page, anything on the Quiz Eligibility engine or Phase 6 calendar architecture.
- Browser/manual testing — the user's responsibility.

---

## PHASE 9.0 — LABORATORY DOMAIN AUDIT & SPECIFICATION

- [x] READ-ONLY audit of the laboratory domain (models/schemas/services/repos/endpoints, ClassSession/timetable/enums, attendance pipeline, events/calendar/quiz engines, frontend lab surfaces, git history, docs).
- [x] Capability classification (experiment identity/number/title/description/completion/submission/status/date/marks/remarks/faculty approval/signature/ordering) — every item marked SUPPORTED / PARTIALLY SUPPORTED / NOT SUPPORTED / UNKNOWN; no gaps filled from academic assumptions.
- [x] Lab turn vs experiment relationship established: a session can host one/many/no experiment (unlinked today), be cancelled, become a lecture (composed facts), host the mid-sem; NO auto `experiments >= 5 ⇒ mid-sem`.
- [x] Mid-sem analysis: session-bound, ADMIN-only designation is the only authoritative mechanism; students can never designate; attendance = normal mutation; no new calculation path.
- [x] Cancellation/substitution traces (cancelled / replaced-with-lecture / replaced-with-other / conducted-no-experiment / extra lab / mid-sem) with supported status per case.
- [x] Attendance rules preserved (labs count to subject+overall, excluded from quiz eligibility, cancelled excluded, pending stays pending, recorded-only current, one engine); Phase 9 needs NO rule extension.
- [x] Authorization matrix proposed (view=student read; curriculum/signature/mid-sem=admin/faculty; events per Phase 8.2 student policy) — not implemented.
- [x] Data-model gap analysis: reuse ClassSession/AcademicEvent/attendance_records; reuse LaboratoryExperiment/LaboratoryRecord for authoritative data; ONLY possible additive: experiment↔session FK, audit identity, FACULTY role — all gated on product decisions.
- [x] Future API contract designed (summary / activities / curriculum ingest / progress) with source of truth per field — not implemented.
- [x] Frontend IA proposed (Practical Attendance · Mid-Sem · Lab Activity History · Experiment Progress only when authoritative) — not implemented.
- [x] Migration analysis (no migration required for this phase; future additive candidates listed); nothing fabricated, ever.
- [x] Engine impact: none required; additive read model → API → React only.
- [x] Product decisions enumerated (curriculum source, faculty role, audit identity, session linkage, mid-sem check, student mutation boundary, grading).
- [x] DELIVERABLE: `docs/phase_9_0_laboratory_domain_audit.md`; Phase 9 sections updated in MASTER_ROADMAP / implementation_plan / walkthrough / task.
- [x] Verification: read-only SELECTs + `verify_phase_8_2.py` 18/18; DB byte-equivalent to baseline (18/691/92/18/9/18/30, lab tables empty, designations=0). No commit.

## Do Not Touch (Phase 9.0 freeze)

- Attendance engine/formulas, quiz eligibility engine, Phase 6 calendar/event architecture, Attendance Health, the mid-sem designation semantics, the student event policy, and all frozen verifiers — unchanged. Phase 9.1 may ONLY add read models / ingestion boundaries / the chosen authority surface, never engine or rule changes.

## Deferred to Phase 9.1+ (requires product decisions)

- Authoritative experiment curriculum ingestion, FACULTY role, experiment↔session linkage, marks/viva, dedicated Laboratory page UI, lab activity read model.

---

## PHASE 9.0b — PRODUCT DECISION REVIEW

- [x] Read the complete `docs/phase_9_0_laboratory_domain_audit.md` + Phase 9 sections of MASTER_ROADMAP / implementation_plan / task / walkthrough.
- [x] DELIVERABLE: `docs/phase_9_product_decisions.md` (14 sections: decision summary · current evidence · D1–D7 · final architecture · 9.1 prerequisites · rejected approaches · remaining unknowns · owner-confirmation list). Every recommendation labeled FACT-from-repository / PRODUCT RECOMMENDATION / UNKNOWN-or-requires-real-world-input.
- [x] D1 Curriculum — recommended **E hybrid**: provenance-bound admin ingestion; nothing seeded until an authoritative catalog exists; per-subject count = catalog row count (no "10").
- [x] D2 Faculty role — recommended **DEFER**: STUDENT + ADMIN for 9.1; FACULTY only with a defined signature/grading workflow (9.2+), capability-matrix ready.
- [x] D3 Audit identity — recommended **minimal additive**: timestamps + `signed_by` + `designated_by/at` + catalog provenance; no created_by on attendance.
- [x] D4 Experiment↔session linkage — recommended **nullable FK** `laboratory_records.class_session_id` + validation; single primary link; multiple experiments per session allowed.
- [x] D5 Mid-sem rule — recommended **advisory only**: "Eligible for mid-sem designation (X of Y)" from the real catalog; designation stays manual ADMIN; no auto-designation/gate/universal count.
- [x] D6 Student boundary — recommended **two-tier**: students self-track (pending); only elevated role sets SIGNED (official).
- [x] D7 Grading/viva — recommended **EXCLUDE from Phase 9**; defer to a separate assessment phase; dormant columns retained.
- [x] Explicitly rejected: hardcoded curriculum, seed-without-source, "10" default, auto mid-sem, hard gate, required FK, FACULTY without workflow, grading in 9, second engine / React math.
- [x] Phase 9 sections updated in MASTER_ROADMAP / implementation_plan / walkthrough / task. Phase 9.1 remains **BLOCKED / NOT STARTED**.
- [x] No code/schema/migration/data/API/UI/seed changes; no commit.

## Phase 9.1 — Laboratory Attendance & Event Integration (COMPLETE 2026-08-15)

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
regressions green except 7.1 check 23 — **BASELINE DRIFT**: records 92 → 95
(3 legitimate owner-entered BCS-502 marks, 2026-08-15 16:19–16:20 UTC, not
verifier residue); verifier NOT modified; **owner must authorize the fixed
fixture 92 → 95**. Full report:
`docs/phase_9_1_implementation_report.md`.

## Do Not Touch (unchanged through Phase 9.1)

Attendance engine/formulas, quiz eligibility engine, Phase 6 calendar/event
architecture, Attendance Health, mid-sem designation semantics (Phase 8.2
admin endpoint intact), student event policy, all frozen verifiers (7.1 left
unmodified; check 23 pending the owner's fixture decision). DB: 18/691/95/
18/9/18/30, lab tables empty, designations=0.

## Phase 9.2.1 — Laboratory Experiment Management (COMPLETE 2026-08-16)

Owner LOCKED the Phase 9.2.0 audit (see `docs/phase_9_2_0_laboratory_
experiment_audit.md`; 21 sections, §21 scope). Implemented:

- [x] Migration A `f1a2b3c4d5e6f`: `laboratory_experiments.description`,
  `is_active` (NOT NULL default TRUE), `UNIQUE(subject_id, experiment_number)`.
- [x] Migration B `f6a5b4c3d2e1f`: `laboratory_records.class_session_id`
  (FK → class_sessions), `signed_by`/`created_by`/`updated_by` (FK → users).
  `created_at`/`updated_at` already present (Base mixin) — NOT re-added.
  Both migrations additive + reversible; alembic head `f6a5b4c3d2e1f`.
- [x] Models/schemas updated (`LaboratoryExperiment`, `LaboratoryRecord`,
  summary/activity/payload schemas; explicit `foreign_keys` on the users
  relationship — 4 FKs to users).
- [x] `LaboratoryRepository` full CRUD + `get_record_counts` + `get_activity_rows`.
- [x] `LaboratoryService`: authorization matrix §16 (reads 404 unenrolled /
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
  data, NOT 9.2.1 residue): 6.7 29/31 (checks 4/7 — 4 test events beyond the
  18 seeded QUIZ_DAY) and 7.1 25/26 (check 23 — records 92 → 95, already
  documented in Phase 9.1). Frozen verifiers NOT modified.
- [x] Docs updated (this file + MASTER_ROADMAP + implementation_plan +
  walkthrough) + `docs/phase_9_2_1_implementation_report.md`.
- [x] DB byte-equivalent to baseline: 22 events · 691 sessions · 95 records ·
  18 enrollments · 9 subjects · 18 quizzes · 30 users · 0 cancelled · 0 extra ·
  0 designated · **lab tables 0/0**. No commit; no Phase 9.2.2.

## Do Not Touch (Phase 9.2.1 freeze)

Attendance engine/formulas, quiz eligibility engine, Phase 6 calendar/event
architecture, Attendance Health, mid-sem designation semantics, student
event policy, all frozen verifiers (6.7/7.1 drift pending owner
authorization). Experiment management is an additive layer — never a second
attendance engine; never fabricated curriculum; no experiment-count gate;
no auto-designation; no FACULTY; no grading/viva. DB: 22/691/95/18/9/18/30,
cancelled=0, extra=0, designated=0, lab tables 0/0.

## Focused Track Correction (after Phase 9.2.1 — 2026-08-16)

- [x] 2-hour lab block = ONE attendance occurrence across Track daily view,
  summary, history, analytics, dashboard, calendar, laboratory summary
  (`app/engines/practical_occurrence.py` collapse; one mutation ⇒ one
  AttendanceRecord; no denominator inflation).
- [x] Future dates view-only: mutation API 400 (institution-local date) +
  Track Upcoming UI with no Present/Absent controls; reads unrestricted.
- [x] New `verify_track_lab_fix.py` **16/16**; frozen regressions: 6.5 27/27,
  6.6 36/36, 7.2 26/26, 8.1 22/22, 8.2 18/18, 9.1 28/28, 9.2 29/29,
  attendance-spec 15/15; **6.7 30/31 + 7.1 25/26 remain the documented
  pre-existing owner-data drift (NOT modified)**.
- [x] Static gates: compileall, tsc --noEmit, ESLint, next build — all PASS.
- [x] DB byte-equivalent to the documented 9.2.1 baseline: 22 events ·
  691 sessions (0 cancelled, 0 extra) · 95 records · 18 enrollments ·
  9 subjects · 18 quizzes · 30 users · 0 designated · lab tables 0/0.
  No commit.
- [x] Report: `docs/track_lab_attendance_correction_report.md`.

## Focused History Filters Correction (2026-08-16)

- [x] /history filters crashed: `TypeError: Cannot read properties of undefined (reading 'total_count')` at `history/page.tsx:322`.
- [x] Root cause (frontend-only): SWR keys history on the request URL; any filter change is a new key, so `history` is `undefined` while `isLoading` — the Load-more button rendered and dereferenced `history!.total_count`. Backend History API audited healthy (all filters, inclusive dates, occurrence-level status matching, filtered `total_count`/`summary`).
- [x] Fix: Load-more gated on `history && rows.length < history.total_count` (spinner row while loading); filter-change effect also clears `rows` (no stale-row mixing; skeleton while the filtered request loads).
- [x] Practical occurrence grouping preserved: a 2-hour lab block is ONE history row under every filter (verifier pins BCS-551 = 4 blocks, not 8 rows).
- [x] New `backend/scripts/verify_history_filters.py` **20/20**; DB baseline restored exactly.
- [x] Static gates: compileall, tsc --noEmit, next build PASS; ESLint on the changed file shows only 2 PRE-EXISTING `set-state-in-effect` errors (present at HEAD; none added).
- [x] Frozen regressions: 6.5 27/27 · 6.6 36/36 · 7.2 26/26 · 8.2 18/18 · attendance-spec 15/15 · 9.1 28/28 · 9.2 29/29 · track-lab-fix 16/16. Pre-existing owner-data fixture drift untouched: 7.1 24/26 (checks 6/23), 6.7 28/31 (checks 4/6/7), 8.1 21/22 (check 7 — admin gained a BCS-551 2026-07-20 Missed record between runs). None weakened.
- [x] DB: records 101 before and after (no attendance data touched); sessions 695→693 via the frozen 6.6 documented startup cleanup of 2 unattended owner extra sessions (2 attended owner extras preserved). No commit.
- [x] Report: `docs/history_filters_correction_report.md`.

## Do Not Touch (post-9.2.1 freeze)

Attendance engine/formulas, quiz eligibility, Phase 6 event architecture,
Phase 9.1 synchronizer/designation semantics, experiment management, all
frozen verifiers (6.7/7.1 drift pending owner authorization).
