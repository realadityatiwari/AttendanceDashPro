# AttendanceDash Pro — Phase 5 Walkthrough

Date: 2026-08-14 · Scope: Attendance History (production-quality, canonical data)

> **PHASE 5 COMPLETE** — the History page is rebuilt as a session-based view over the
> exact canonical records Track uses: every scheduled class session of the student's
> enrolled subjects from the real semester start through today, with server-side
> subject/state/date/search filtering, limit/offset pagination, a server-computed
> summary strip, and truthful loading/error/empty states. No second attendance source,
> no React-side calculations, no data mutations. `GET /api/v1/attendance/history` was
> extended in place — same path, same `items`/`total_count` envelope.

## Verification Summary (every item labelled)

| Verification | Label |
|---|---|
| Backend changed files compile (`python -m compileall backend/app`) | **VERIFIED** |
| Frontend `npx tsc --noEmit` — 0 errors | **VERIFIED** |
| Live default query (real user `2401220100027`, minted dev JWT): 129 sessions, summary 55 Attended / 24 Missed / 50 Pending / 0 Cancelled, pct 69.6% (= 55/79 recorded, matches the dashboard's overall) | **VERIFIED** |
| Semester range from real academic context: 2026-07-15 → 2026-12-31, effective range clamped to 2026-07-15 → 2026-08-14 (today) | **VERIFIED** |
| Track cross-check 2026-07-15: exactly 6 sessions, BNC-501/BCS-503/BCS-054 Present, BCS-054T/BCS-058/BCS-502 Absent — identical to the Track daily view | **VERIFIED** |
| Lab records appear: BCS-553 status=Attended → exactly 2026-07-17 PRACTICAL (the user's manual Track mark); practical search → 28 sessions | **VERIFIED** |
| Status filters: Pending=50, Missed=24, Attended=55, Cancelled=0 (no cancelled sessions exist); invalid status → 422 pattern rejection | **VERIFIED** |
| Search: `BCS-55`=28, `practical`=28, `lecture`=79, `2026-07-15`=6 (code/type-label/date) | **VERIFIED** |
| Pagination: limit=10&offset=0 vs offset=10 → 10+10 rows, zero id overlap | **VERIFIED** |
| Date clamps: date_from=2026-01-01 → 2026-07-15; date_to=2026-12-31 → 2026-08-14; date_from=2026-09-01 → 0 results | **VERIFIED** |
| Authorization: second account (`9999999999999`) → 0 Attended / 0 Missed / 129 Pending (record isolation); unenrolled subject code → 0 | **VERIFIED** |
| No attendance rows created/modified/deleted; Aditya's 79 records untouched; no engines/auth/migrations changed | **VERIFIED** |

## What Phase 5 Delivered

1. **Canonical history, not a facts log**: the endpoint now returns scheduled sessions
   (missing record = Pending; cancelled = its own state) instead of only recorded rows —
   the same `class_sessions` + `attendance_records` pipeline Track reads. One endpoint,
   extended in place; no second attendance source.
2. **Real semester bounds**: range resolved from the student's academic context via the
   same repository `/student/me` uses, clamped to today; date inputs share the bounds.
   No hardcoded dates.
3. **Server-side summary**: aggregate `FILTER` query over the full filtered set —
   Total/Present/Absent/Pending/Cancelled + % — so pagination never distorts the strip.
4. **Real filtering**: subject (from enrolled subjects), state, date range, and search
   (code, name, class type label, ISO date) — all validated, enrollment-scoped, and
   enforced in SQL.
5. **Clean pagination**: "Load more" appends with id-deduplication; any filter change
   resets offset and never mixes old/new result sets; the list stays visible while the
   next page loads.
6. **One found-and-fixed defect**: the page-count query referenced the attendance table
   without joining it (cross-join) — `total_count` was corrupted under status filters
   (e.g. 3225 vs 24). The count query now mirrors the page joins exactly.
7. **Consistency with Track proven on real data**: 2026-07-15 and the manual lab mark
   agree across both views; the summary's 69.6% equals the dashboard's overall pct.

## Remaining Work

- Phase 6 — Calendar & Academic Events (next per roadmap; `academic_events` is still empty).
- Session-detail affordance was deliberately kept minimal (the row already exposes date,
  times, subject, type, status, and marked-at time — a modal would duplicate data).
- Phase 14 — Firebase Retirement; Phase 2 blockers carried forward as before.

---

# AttendanceDash Pro — Phase 4.5.3 Walkthrough

Date: 2026-08-14 · Scope: Real Sign Up + Account Creation (PostgreSQL-native registration)

> **PHASE 4.5.3 COMPLETE** — the application now has a real student registration flow:
> `POST /api/v1/auth/register` creates a PostgreSQL user with transactional academic
> enrollment and immediately issues the same JWT login uses, and `/signup` provides the
> full UX (name, 13-digit roll number, password + confirm, show/hide, Create Account,
> login link). Firebase identity is no longer required: `firebase_uid` is nullable, legacy
> UIDs preserved, removal deferred to Phase 14. No second auth mechanism was created.

## Verification Summary (every item labelled)

| Verification | Label |
|---|---|
| Backend changed files compile (`python -m compileall backend/app`) | **VERIFIED** |
| Frontend `npx tsc --noEmit` — 0 errors | **VERIFIED** |
| Alembic `upgrade head` → `c3d4e5f6a7b8`; `users.firebase_uid` now nullable; 29/29 legacy UIDs intact (Aditya's `HCRbV7Kld3Wo9IHLJHRGlBau4Mq2` preserved) | **VERIFIED** |
| Live `POST /auth/register` invalid roll → 422 "Roll number must be 13 digits" | **VERIFIED** |
| Live short password → 422 "Password must be at least 8 characters" | **VERIFIED** |
| Live duplicate roll (Aditya's) → 409 "An account with this roll number already exists" (full pipeline + rollback; no data created) | **VERIFIED** |
| Live registration of disposable account (roll `9999999999999`, reported): 201 + JWT; `/student/me` → section CSE-51, `firebase_uid` null; dashboard usable with new token; 9 enrollments created | **VERIFIED** |
| Aditya's account/attendance/enrollments untouched (DB query) | **VERIFIED** |

## What Phase 4.5.3 Delivered

1. **Registration contract**: name required; roll number must be exactly 13 digits (backend-authoritative, frontend mirrors for UX); password ≥ 8 characters; hashed with the same `pbkdf2_sha256` format login verifies — one verifier, no second password format, never logged.
2. **Transactional account creation**: User + `StudentEnrollment` rows committed together; duplicate roll number races are caught by the unique index (`IntegrityError` → 409 → rollback); any failure rolls back — no partial users, no orphan enrollments.
3. **Enrollment provisioning rule** (explicit, no guessing): active `AcademicSession` → its semester (must be unique) → its section (auto-assign only when exactly one) → enroll in all semester subjects. The client cannot choose section/semester/subjects. Multi-section ambiguity is rejected with a clear 409 until a section-selection product decision exists.
4. **firebase_uid treatment**: minimal migration `c3d4e5f6a7b8` makes the column nullable; unique index retained; existing values untouched; column removal deferred to Phase 14 (Firebase Retirement). New registrations store `NULL`.
5. **JWT after registration**: issued with the exact `create_access_token` mechanism used by login; the frontend stores it under the same `access_token` key and enters the app shell via the existing `refreshUser()` path — signup is not a second authentication flow.
6. **Signup UX**: matches the login page's visual system; show/hide password toggles; client validation (13-digit roll, min-8 password, matching confirmation); friendly server-error mapping (duplicate roll, validation, generic failure); success → dashboard. Auth routing treats `/signup` as public and redirects authenticated visitors away from both auth pages.

## Remaining Work

- Phase 5 — Attendance History (next per roadmap; canonical records already shared with Track).
- Section selection / multi-section registration policy (requires a product decision before implementation).
- Password reset / email identity (schema stores no email).
- Phase 14 — Firebase Retirement owns final `firebase_uid` column removal.

---

# AttendanceDash Pro — Phase 4.5.2 Walkthrough

Date: 2026-08-14 · Scope: Historical Track completion on the Next.js app (real data)

> **PHASE 4.5.2 COMPLETE** — Track now navigates the full semester history (2026-07-15 semester start → today) with every scheduled session visible — lecture, tutorial, and practical/lab — and markable through the single canonical `POST /api/v1/attendance` endpoint. Practical sessions are no longer confusable with quiz-window eligibility: they flow through the normal `class_sessions` + `attendance_records` pipeline (PENDING by missing row), exactly as the legacy system intended but failed to do. No engines, models, migrations, or database data were changed.

## Verification Summary (every item labelled)

| Verification | Label |
|---|---|
| Backend changed files compile (`python -m compileall backend/app`) | **VERIFIED** |
| Frontend `npx tsc --noEmit` — 0 errors | **VERIFIED** |
| Live `GET /api/v1/student/me` — `semester_start 2026-07-15`, `semester_end 2026-12-31` exposed for navigation bounds | **VERIFIED** |
| Live `GET /api/v1/attendance/daily/2026-07-15` — 6 sessions, 3 Attended / 3 Missed (semester start reachable and stateful) | **VERIFIED** |
| Live `GET /api/v1/attendance/daily/2026-07-16` — BCS-552 practical ×2 sessions present, Pending (labs appear in Track) | **VERIFIED** |
| Live `GET /api/v1/attendance/daily/2026-07-17` — BCS-553 practical ×2 present, 2 Pending / 3 Missed | **VERIFIED** |
| Live `GET /api/v1/attendance/daily/2026-07-14` and `2026-07-19` — 0 sessions (empty state; bounds prevent navigating here) | **VERIFIED** |
| Mutation contract — POST status=`Attended` (bogus session) → 404, proving corrected payload passes validation; POST status=`ATTENDED` → 422, proving the old frontend value was rejected | **VERIFIED** |
| Live `GET /api/v1/attendance/summary/BCS-551` — practical total=8, pending=8: labs counted by canonical analytics (no silent exclusion) | **VERIFIED** |
| No attendance rows created/modified/deleted; laboratory tables untouched | **VERIFIED** |

## What Phase 4.5.2 Delivered

1. **Root-cause fix**: the frontend `AttendanceStatus` enum (`"ATTENDED"`) and `ClassType.PRACTICAL` (`"P1"`) did not match the backend's serialized contract (`"Attended"` / `"P"`). Track rendered every session as PENDING and every mutation was rejected with 422. Enum values corrected to the live contract; `TrackSessionCard`, the Track page summary, Mark-All-Present, and the History page now compare correctly without any component rewrites.
2. **Semester-bounded navigation**: the Track page reads `semester_start`/`semester_end` from `GET /student/me` (no hardcoded dates), clamps previous/next navigation to the semester, and provides a native date picker (dark-styled, min/max clamped) so the user can jump straight to 15 July 2026 — no URL manipulation, no dozens of arrow clicks.
3. **Security hardening (minimal)**: daily-session reads are scoped to the student's enrolled subjects via `StudentEnrollment`; mutations on cancelled sessions are rejected server-side (409) in addition to the existing enrollment check and unique-constraint-preserving update.
4. **Honest error surfacing**: mutation failures (network/validation) now render an inline banner instead of disappearing into `console.error`.

## Remaining Work

- Phase 4.5.3 — Real Sign Up (next).
- Phase 5 — Attendance History redesign (canonical records already shared with Track).
- Phase 9 — Laboratory experiment management (0 experiments; separate subsystem).
- Phase 2 blockers carried forward: feedback persistence, settings persistence, program column, Light/System palette, PWA infra.

---

# AttendanceDash Pro — Phase 3 Walkthrough

Date: 2026-08-13 · Scope: Home dashboard on the Next.js app (real data)

> **PHASE 3 COMPLETE** — the authenticated Home/Dashboard page is rebuilt around a single read-only `GET /api/v1/dashboard/summary` endpoint: greeting, today's attendance, overall attendance, weekly strip, quiz snapshot, attention-required subjects, and upcoming events. Aggregation reuses the existing attendance/eligibility/calendar services and frozen engines; no business rules were duplicated. (Phase 2 shell & modals remain complete and untouched.)

## Verification Summary (every item labelled)

| Verification | Label |
|---|---|
| Backend changed files compile (`py_compile`) | **VERIFIED** |
| `GET /api/v1/dashboard/summary` live check (real user `2401220100027`, minted JWT) — 200 OK, all sections populated from real data | **VERIFIED** |
| Today's Attendance shows today's real 6 sessions, all PENDING (no records exist for 2026-08-13), with correct subject/code/type mapping | **VERIFIED** |
| Overall Attendance = 54/78 recorded = 69.2% → **WATCH** (banding: SAFE ≥ 80, WATCH ≥ 60, CRITICAL < 60 on current pct) | **VERIFIED** |
| This Week: week 2026-08-10→16, weekly 77.8% vs previous 56.3% (+21.5 pts), best BCS-501, needs attention BNC-501 | **VERIFIED** |
| Quiz Snapshot: earliest future SCHEDULED quiz = BNC-501 Quiz1 (cycle 1) on 2026-08-24, threshold ≥70% from DB policy, 6/6 eligible | **VERIFIED** |
| Attention Required: BNC-501/BCS-058/BCS-054 CRITICAL + BCS-502 WATCH, sorted CRITICAL-first then pct ascending, with forecast pct | **VERIFIED** |
| Upcoming Events renders empty state (0 rows in `academic_events` — data gap, not code gap) | **VERIFIED** (as designed) |
| Loading skeletons per section + full-page error state | **VERIFIED** |
| Two-column bento in DOM order Today's → Overall → This Week → Quiz → Attention → Events (matches reference collapse order) | **VERIFIED** |
| Navigation actions resolve to real existing routes only (laboratory/quiz-schedule/events) | **VERIFIED** |
| `npx tsc --noEmit` passes with 0 errors | **VERIFIED** |
| No engines, models, migrations, auth architecture, Phase 1 tokens, or Phase 2 components modified | **VERIFIED** |

## What Phase 3 Delivered

1. **Backend read model** (`dashboard_service.py` + `schemas/dashboard.py` + `endpoints/dashboard.py`): one additive endpoint that composes all Home sections by calling the existing `AttendanceService.get_summary`, `EligibilityService.get_quiz_eligibility`, `CalendarService`/`CalendarRepository`, and `QuizRepository`. One new read-only repo method (`get_sessions_with_status`) supplies the session-level join for Today/This Week.
2. **Status classification reconciled**: SAFE ≥ 80 / WATCH ≥ 60 / CRITICAL < 60 based on **current** attendance pct (per S4.1 reconciliation and legacy banding in `docs/11_UI_ARCHITECTURE.md`). Overall pct = Σattended/Σrecorded (ERP style), pending excluded.
3. **Home page**: greeting header (`Good Morning/Afternoon/Evening, {first name}` + `Thursday · 13 Aug 2026`), two-column bento, per-section skeletons, error state, empty states (no classes today / no quiz scheduled / all subjects on track / no events), real links to Track (`/tools/laboratory`), Quiz Eligibility (`/tools/quiz-schedule`), Events (`/tools/events`).
4. **Honest feature boundaries**: dedicated per-subject strategy view is Track-phase work (button routes to the laboratory); Upcoming Events is empty because the `academic_events` table has no rows — the empty state renders as designed and fills in automatically once events are seeded.

## Remaining Work

- Track phase: daily attendance marking, per-subject strategy view (the dashboard's "View Strategy" already routes to `/tools/laboratory`).
- Quiz eligibility page content refresh (current page already exists at `/tools/quiz-schedule`).
- Events phase: seeding/list/calendar/Add Event (dashboard events section will populate automatically).
- Mobile navigation phase (nav currently hidden below `md`).
- Phase 2 blockers carried forward: feedback persistence, settings persistence, program column, Light/System palette, PWA infra.

---

# AttendanceDash Pro — Phase 2 Walkthrough

Date: 2026-08-13 · Scope: Desktop shell & global UX on the Next.js app

> **PHASE 2 COMPLETE** — top navigation, user menu, and Profile/Appearance/Feedback/Settings/Install App modals implemented on a shared dialog foundation. Features that cannot be genuinely functional are explicitly marked BLOCKED / BACKEND REQUIRED rather than faked.
>
> (Legacy S3.x JS-PWA baseline history remains in `docs/S3.10_CURRENT_SEMESTER_BASELINE.md`; the app has since been rewritten in Next.js + FastAPI.)

## Verification Summary (every item labelled)

| Verification | Label |
|---|---|
| `npx tsc --noEmit` passes with 0 errors | **VERIFIED** |
| Backend changed files compile (`py_compile`) | **VERIFIED** |
| Legacy sidebar removed; AppShell renders TopNav + centered `max-w-5xl` content region | **VERIFIED** |
| Nav labels map to existing routes only (Home→`/dashboard`, Track→`/tools/laboratory`, Quiz Eligibility→`/tools/quiz-schedule`, Attendance→`/subjects`, History→`/history`, Events→`/tools/events`); no URLs invented, no routes duplicated | **VERIFIED** |
| Active route highlighted with compact dark surface (`bg-secondary`) + `aria-current` | **VERIFIED** |
| User menu opens/closes via Base UI Menu (outside click, Escape, selection, keyboard) | **VERIFIED** |
| User identity (name/initials/roll number) comes from `useProfile`/`useAuth`, never hardcoded | **VERIFIED** |
| Profile modal renders academic context (semester, session, semester start, first quiz date) from the extended `GET /student/me` | **VERIFIED** |
| Profile modal `Program` row shows unavailable state; backend has no program column | **BLOCKED / BACKEND REQUIRED** |
| Appearance modal: Dark selected; Light/System disabled — Phase 1 tokens are dark-locked, no fake switching or persistence | **VERIFIED** (as designed) |
| Settings modal: all controls disabled with persistence notice; no fake local-only persistence | **VERIFIED** (as designed) |
| Feedback modal: validation + loading/error/success states; posts to `POST /api/v1/feedback` which does not exist yet — surfaced as explicit error, success state reachable only when the endpoint lands | **BLOCKED / BACKEND REQUIRED** |
| Install App: `beforeinstallprompt` captured app-wide, `display-mode: standalone` detected; no manifest/service worker in build → honest explainer; no fake installed state | **BLOCKED / BACKEND REQUIRED** |
| Sign Out uses existing `AuthContext.logout()` (JWT removal + redirect to `/login`) | **VERIFIED** |
| No attendance/quiz/lab engines, migrations, auth architecture, or Phase 1 design tokens modified | **VERIFIED** |
| No dead code: `Header.tsx`/`Sidebar.tsx` deleted, no remaining imports | **VERIFIED** |

## What Phase 2 Delivered

1. **Shell**: full-width compact dark top nav (brand, six primary links, user area) replacing the desktop sidebar; content constrained to `max-w-5xl`; navigation links hidden below `md` pending the dedicated mobile phase.
2. **Global modal foundation** (`ShellDialog`): shared backdrop/focus/Escape/scroll-lock/width/header/close conventions used by all five modals.
3. **User menu**: Profile, Appearance, Install App, Send Feedback, Settings, Sign Out — real authenticated data, correct focus and dismissal behavior.
4. **Profile modal**: identity + academic context resolved from the real profile chain (section → semester → session, quiz schedules). One additive read-only backend contract change (`GET /student/me`).
5. **Honest feature boundaries**: feedback (no endpoint → explicit error, never fake success), settings (no persistence → disabled + documented), appearance (dark-only → Light/System disabled), install (no PWA infra → explainer). Backend work required is recorded in `implementation_plan.md`.

## Remaining Work

- Dedicated page phases: Home, Track, Quiz Eligibility, Attendance, History, Events content.
- Events phase: list/calendar view, Upcoming/Today/Past, Add Event modal, type/subject selection, date handling, persistence.
- Mobile navigation phase (nav currently hidden below `md`).
- Backend: feedback table + `POST /api/v1/feedback`; `user_preferences` table + settings endpoints; program column on sections; Light/System palette in Phase 1 tokens; PWA manifest/service worker.
- Daily attendance marking (Track intent) — TodayClassesCard remains read-only.

---

# AttendanceDash Pro — Phase 6.1 Walkthrough

Date: 2026-08-14 · Scope: Foundational Calendar Corrections (Phase 6.0 defects, no UI/CRUD/seeding)

> **PHASE 6.1 COMPLETE** — the four calendar/event defects PROVEN in the Phase 6.0 audit
> (`docs/phase_6_0_calendar_events_audit.md`) are corrected on correct temporal semantics:
> a single engine-owned weekend constant, MID_SEMESTER_BREAK as a closure, a server-side
> /events read contract, and enrollment-scoped dashboard aggregation. Static/in-process
> verification only — no browser testing (per instruction), no database mutations.

## Verification Summary (every item labelled)

| Verification | Label |
|---|---|
| `backend/.venv/Scripts/python -m compileall backend/app backend/scripts` — PASS | **VERIFIED** |
| Frontend `npx tsc --noEmit` — 0 errors | **VERIFIED** |
| In-process engine/service execution: 2026-08-14 Fri → working · 2026-08-15 Sat → non-working · 2026-08-16 Sun → non-working | **VERIFIED** |
| CalendarService + EligibilityService use the shared `DEFAULT_WEEKENDS` (import verified) | **VERIFIED** |
| MID_SEMESTER_BREAK (ORM-shaped event) → non-working closure on its dates | **VERIFIED** |
| Inactive event does not affect day resolution; event range bounds only its own dates | **VERIFIED** |
| Quiz-window bounds unchanged (Q1 from commencement, day before quiz); teaching dates exclude Sat/Sun | **VERIFIED** |
| /events repo filters (active/inactive/upcoming/date-range overlap, 8 cases) against ORM rows in a rolled-back transaction | **VERIFIED** |
| Dashboard aggregation scoping: unenrolled temp subject (ZZZ-999) excluded; 2026-07-15 control = 6 sessions for test user and Aditya | **VERIFIED** |
| Live read-only SQL: academic_events 0 · subjects 9 · class_sessions 684 · attendance_records 84 · enrollments 18 · users 30 | **VERIFIED** |
| No browser testing performed (deferred to user) | **AS DESIGNED** |

## What Phase 6.1 Delivered

1. **Weekend convention (single source of truth)**: `calendar_engine.DEFAULT_WEEKENDS = [0, 6]`
   (JS `getDay()` indices: Sunday=0, Saturday=6 — matching the legacy `js/calendar-engine.js` and
   the engine's own Python→JS weekday conversion). `CalendarService` and `EligibilityService` now
   import it instead of passing local `[5, 6]` literals; `expand_baseline.py` uses it too.
2. **MID_SEMESTER_BREAK closure**: added to the engine's closure list (priority 60, same tier as
   SEMESTER_BREAK; documented grouping in `docs/05_CALENDAR_ENGINE.md`). An active break event now
   forces its date range non-working.
3. **/events read contract**: `GET /api/v1/events` defaults to active events only, with optional
   `date_from`/`date_to` (inclusive range-overlap) and `upcoming` (`end_date >= today`) server-side
   filters; 422 on inverted date range. Repository stays no-filter by default for internal
   dashboard/eligibility consumers — no existing consumer broke.
4. **Dashboard enrollment scoping**: `get_sessions_with_status` joins `StudentEnrollment` exactly
   like `get_daily_sessions`/`get_history`; Dashboard Today/Overall/Weekly now only count the
   authenticated student's enrolled subjects. Formulas, statuses, and thresholds untouched.

## Remaining Work

- Phase 6.2 — Calendar read model & API (month-bounded, semester-bounded; next per roadmap).
- Phase 6.3 — Calendar UI · 6.4 — Events page upgrade · 6.5 — persistence + admin auth + seeding · 6.6 — event→engine integration · 6.7 — verification/freeze.
- Deferred per Phase 6.1 scope: event CRUD, admin roles, validation registry, seeding, event→session integration, substitution, quiz/event integration, scoping, timetable schema, TodayClassesCard cleanup, type-hint refactor, window-field restoration.

---

# AttendanceDash Pro — Phase 6.2 Walkthrough

Date: 2026-08-14 · Scope: Calendar Read Model & API (backend only, no UI)

> **PHASE 6.2 COMPLETE** — `GET /api/v1/calendar?year=&month=` now returns a
> semester-bounded, engine-resolved, enrollment-scoped month calendar read model that the
> future Phase 6.3 UI can render directly without recomputing weekends, closures, events,
> semester bounds, or class-session counts. Read-only; static/in-process verification only
> (no browser testing per instruction); zero persisted database mutations.

## Verification Summary (every item labelled)

| Verification | Label |
|---|---|
| `backend/.venv/Scripts/python -m compileall backend/app` — PASS | **VERIFIED** |
| Frontend `npx tsc --noEmit` — 0 errors | **VERIFIED** |
| Aug 2026: semester bounds 2026-07-15 → 2026-12-31, effective 08-01 → 08-31, 31 day items | **VERIFIED** |
| 2026-08-14 Friday → working · 2026-08-15 Saturday → non-working "Weekend" · 2026-08-16 Sunday → non-working | **VERIFIED** |
| Jul 2026 clamped to 07-15 → 07-31 (17 days); Dec 2026 full 12-01 → 12-31 | **VERIFIED** |
| Jan 2026 and Jan 2027 (outside semester) → empty `days` with inverted effective range | **VERIFIED** |
| Session counts match independent enrollment-scoped SQL per day and for the whole month | **VERIFIED** |
| Saturday session_count = 0; working Friday has scheduled classes | **VERIFIED** |
| Active MID_SEMESTER_BREAK → non-working "Mid Semester Break" (rolled-back event row) | **VERIFIED** |
| Inactive PUBLIC_HOLIDAY ignored; September holiday excluded from August | **VERIFIED** |
| API validation: month 0/13, year 1999/2101, non-numeric, missing params → 422 (7 cases) | **VERIFIED** |
| API happy path (real `api_router`, in-process ASGITransport): Aug 200 + exact shape; Jan 2027 empty; `/calendar/today` and `/calendar/{date}` intact | **VERIFIED** |
| Read-only SQL: academic_events 0 · subjects 9 · class_sessions 684 · attendance_records 84 · enrollments 18 · users 30 | **VERIFIED** |
| No browser testing performed (deferred to user) | **AS DESIGNED** |

## What Phase 6.2 Delivered

1. **Month read model** (`CalendarMonthResponse` / `CalendarDayItem` extending `AcademicDayResponse`):
   `year`, `month`, real `semester_start/end`, `effective_start/end`, and a deterministic per-day list with
   `date`, `is_working_day`, `day_type`, `is_teaching_day`, `original_day_of_week`,
   `substitution_schedule_override`, `non_working_reason`, `events[]`, `session_count`.
2. **Real semester bounds**: `UserRepository.get_academic_context` (the /student/me / Track / History
   resolver) — never hardcoded; `effective_start = max(month_start, semester_start)`,
   `effective_end = min(month_end, semester_end)`; months outside the semester return a truthful empty result.
3. **Engine delegation**: every day is resolved by the canonical `calendar_engine.get_academic_day` with
   `DEFAULT_WEEKENDS`; `non_working_reason` is a render-only string from engine output (dominant event
   title, else "Weekend"). Phase 6.1 semantics preserved.
4. **Events**: `get_all_events(active=True, date_from, date_to)` (Phase 6.1 contract); inactive events and
   events outside the month never leak; an empty table still yields a structurally correct calendar.
5. **Session counts**: one enrollment-scoped `get_sessions_with_status` query for the range, grouped by
   date (no N+1); counts reflect scheduled sessions for the student's enrolled subjects only; no
   attendance/quiz mathematics.
6. **Validation**: FastAPI `Query` constraints (`year 2000-2100`, `month 1-12`) — 422 for every invalid form.

## Remaining Work

- Phase 6.3 — Calendar UI (route, month/day navigation, working/non-working indicators, event cards) rendering the 6.2 read model directly.
- Phase 6.4 — Events page upgrade · 6.5 — persistence + admin auth + seeding · 6.6 — event→engine integration · 6.7 — verification/freeze.
- Standing deferrals unchanged (event CRUD, admin roles, validation registry, seeding, event→session integration, substitution, quiz/event integration, scoping, timetable schema, TodayClassesCard cleanup, type-hint refactor, window-field restoration).

---

# AttendanceDash Pro — Phase 6.3 Walkthrough

Date: 2026-08-14 · Scope: Calendar UI (frontend only)

> **PHASE 6.3 COMPLETE** — the authenticated `/calendar` route is the production
> Calendar UI. It renders the frozen Phase 6.2 `CalendarMonthResponse` read model
> directly: month grid with working/non-working state, academic-event indicators,
> session counts, month navigation (Previous/Next/Today), a selected-day detail
> card, and truthful loading/error/empty states. Zero calendar semantics computed
> in React; zero backend changes; no event CRUD; no database mutations.

## Verification Summary (every item labelled)

| Verification | Label |
|---|---|
| `npx tsc --noEmit` — 0 errors | **VERIFIED** |
| `git diff` — no backend files changed (Phase 6.2 contract files untouched) | **VERIFIED** |
| No migrations/schema changes; no attendance/eligibility engine changes | **VERIFIED** |
| No event CRUD, no admin, no seeding; `academic_events` untouched | **VERIFIED** |
| Route lives under the existing `(authenticated)` AppShell group — no new shell | **VERIFIED** |
| `useCalendarMonth(year, month)` — one SWR request per month, stable cache key | **VERIFIED** |
| No frontend weekday/holiday/session-count calculations (reviewed grid + detail code) | **VERIFIED** |
| Month arithmetic is local-time safe; Jan↔Dec rollover handled (reviewed) | **VERIFIED** |
| Navigation disabled beyond backend `semester_start`/`semester_end` when known (reviewed) | **VERIFIED** |
| Placeholder cells vs backend `CalendarDayItem`s are distinct (reviewed) | **VERIFIED** |
| Day cells are native buttons with `aria-label`/`aria-pressed`; focus rings present (reviewed) | **VERIFIED** |
| No browser testing performed (deferred to user) | **AS DESIGNED** |

## What Phase 6.3 Delivered

1. **Route**: `/calendar` inside the existing authenticated AppShell layout — same header/nav/auth, no duplication.
2. **API hook + types**: `useCalendarMonth(year, month)` (SWR, per-month cache key, `mutate` for retry) and `CalendarMonthResponse`/`CalendarDayItem` types added next to the existing API surface.
3. **Calendar grid**: Sunday-first monthly grid on the real local month. Backend day items are placed in their date cells; every cell outside the API's effective range is an empty layout placeholder. Working days show date + session count; non-working days are muted with `non_working_reason`; event days show an accent dot/count; selected day uses the accent ring; today is subtly ringed.
4. **Month navigation**: Previous/Next/Today, month-based, local-time arithmetic (no UTC shifts; January ↔ December correct). When the backend supplies semester bounds, navigating to a month that cannot contain a single academic day is disabled. Today goes to the current local month; out-of-semester months show the truthful empty state.
5. **Selected-day behavior**: on a fresh month load, today is selected when the API returned it, otherwise the first effective day, otherwise nothing. Manual selections persist while the month is unchanged and can never leak across a month switch (selection is keyed by month).
6. **Detail card**: full date, working/non-working badge, `non_working_reason`, `is_teaching_day`, `substitution_schedule_override`, scheduled-class count ("3 classes" / "No classes"), and the day's active events (type, holiday/class-type badges, date range) with a link to the existing read-only Events page.
7. **States**: skeleton on first load; retained (dimmed) grid with a loading hint during month switches; a calendar-specific error card with "Try again" (retry = `mutate`); a truthful "No academic days in this period" empty state for `days.length === 0`.
8. **Accessibility**: day cells are semantic buttons with descriptive `aria-label` and `aria-pressed`; focus-visible rings from the design system. No div-as-button patterns and no button-as-link composition, so the Base UI `nativeButton={false}` warning cannot reappear.
9. **Navigation**: a single `Calendar` primary item added to `TopNav` (between History and Events). Nothing replaced or redesigned; `/tools/events` remains untouched for Phase 6.4.

## Remaining Work

- Phase 6.4 — Events page upgrade (Upcoming/Today/Past grouping, filters, details; keep read-only).
- Phase 6.5 — persistence + admin auth + seeding · 6.6 — event→engine integration · 6.7 — verification/freeze.
- Standing deferrals unchanged (event CRUD, admin roles, validation registry, seeding, event→session integration, substitution, quiz/event integration, scoping, timetable schema, TodayClassesCard cleanup, type-hint refactor, window-field restoration).

---

# AttendanceDash Pro — Phase 6.4 Walkthrough

Date: 2026-08-14 · Scope: Events page upgrade (frontend only)

> **PHASE 6.4 COMPLETE** — `/tools/events` is now the production read-only
> Academic Events page: Upcoming / Today / Past grouping, event-type / state /
> date-range filters, and truthful loading/error/empty states — all consuming
> the frozen Phase 6.1 `GET /api/v1/events` contract with the backend as the
> single data authority. No second event data source; no calendar semantics in
> React; zero backend changes; zero database mutations.

## Verification Summary (every item labelled)

| Verification | Label |
|---|---|
| `npx tsc --noEmit` — 0 errors | **VERIFIED** |
| ESLint on changed files — PASS (no new warnings) | **VERIFIED** |
| `git diff` — no backend files changed (Phase 6.1/6.2 contracts untouched) | **VERIFIED** |
| No migrations/schema changes; no attendance/eligibility engine changes | **VERIFIED** |
| No event CRUD, no admin, no seeding; `academic_events` untouched | **VERIFIED** |
| `useEvents(params)` — one logical request per filter combination; `mutate` for retry | **VERIFIED** |
| Grouping is presentation-only (local today vs backend date ranges) — reviewed | **VERIFIED** |
| No working-day/holiday/session/eligibility calculations in React — reviewed | **VERIFIED** |
| Unknown event types humanize gracefully (reviewed humanizer) | **VERIFIED** |
| Empty state differentiates "no events" vs "no filter matches" — reviewed | **VERIFIED** |
| No browser testing performed (deferred to user) | **AS DESIGNED** |

## What Phase 6.4 Delivered

1. **Single data source**: the existing Phase 6.1 endpoint. `useEvents(params?)` gained the Phase 6.1 query contract (`active`, `date_from`, `date_to`, `upcoming`) with a stable per-params SWR key; the default call is unchanged.
2. **Grouping**: Today (local today inside the event range), Upcoming (end_date after today, start asc), Past (ended, newest first). Pure presentation over backend dates.
3. **Filters**: event type (client-side over the fetched set, since the API has no type filter), Active/Inactive state (honestly supported by `active=true|false`), and From/To date range (server-side range overlap; inverted ranges blocked client-side with a hint). Reset clears all.
4. **Rows**: compact `EventRow` cards — date block, humanized type title (robust for unknown/future types), semantic badges (Today/Holiday/Extra/Cancelled/class type/Inactive), date range with end date only when different, substitution note, and a `Calendar` link to `/calendar` (no invented query params; calendar route untouched).
5. **Sections**: `Upcoming` / `Today` / `Past` headings with counts; empty sections show muted placeholder lines.
6. **States**: skeleton sections on load (no fake empty flash); events-specific error card with "Try again" (`mutate`); and a truthful zero-row empty state ("No events scheduled" — correct today, since `academic_events` has 0 rows) distinguished from "No events match the selected filters".
7. **Accessibility**: semantic h1/h2/h3 headings, labeled native filter controls, focus-visible rings, real buttons/links only (no div-as-button, no Base UI button-as-link composition).

## Remaining Work

- Phase 6.5 — event persistence + admin auth + seeding (event CRUD, validation registry; admin-owned mutation).
- Phase 6.6 — event→engine integration · 6.7 — verification/freeze.
- Standing deferrals unchanged (admin roles, validation registry, seeding, event→session integration, substitution, quiz/event integration, scoping, timetable schema, TodayClassesCard cleanup, type-hint refactor, window-field restoration).

---

# AttendanceDash Pro — Phase 6.5 Walkthrough

Date: 2026-08-14 · Scope: Event persistence, admin authentication & controlled seeding

> **PHASE 6.5 COMPLETE** — a real role system (`users.role`), an admin-only
> event mutation API, a centralized validation registry, a minimal admin UI on
> `/tools/events`, and idempotent seeding (17 QUIZ_DAY events from the
> authoritative `quiz_schedules`). Backend is authoritative for authorization
> and validation; the Phase 6.1 events and Phase 6.2 calendar read contracts
> are unchanged; the Phase 6.4 student experience is unchanged.

## Verification Summary (every item labelled)

| Verification | Label |
|---|---|
| `compileall` backend — PASS | **VERIFIED** |
| `alembic upgrade head` — applied (head `d4e5f6a7b8c9`, 30 users backfilled STUDENT) | **VERIFIED** |
| `verify_phase_6_5.py` — **23/23 checks PASS** (in-process httpx against real app + DB) | **VERIFIED** |
| Security matrix: STUDENT 403 on POST/PATCH/DELETE; ADMIN 201/200; unauth 401 | **VERIFIED** |
| Duplicate guard 409; missing subject/event 404; validation 422 | **VERIFIED** |
| PATCH partial update: absent fields untouched, `null` clears, `active=false` deactivates | **VERIFIED** |
| Re-enable via PATCH `{"active": true}`; deactivated rows excluded from reads | **VERIFIED** |
| Read-contract regression: `GET /events` (student) + `GET /calendar` unchanged shapes | **VERIFIED** |
| Seed idempotency: run 1 → 17 created; run 2 → 17 skipped (no duplicates) | **VERIFIED** |
| `npx tsc --noEmit` — 0 errors; ESLint changed files — PASS; `npm run build` — PASS | **VERIFIED** |
| No attendance/session/enrollment/subject/quiz/user-history rows touched | **VERIFIED** |
| Frozen areas untouched (`git diff` review: engines, dashboard, Track, History, auth flow, 6.1/6.2/6.3/6.4 surfaces) | **VERIFIED** |
| No browser testing performed (deferred to user) | **AS DESIGNED** |
| No authoritative holiday/break/working-Saturday dates in repo → not seeded (documented data gap) | **AS DESIGNED** |

## What Phase 6.5 Delivered

1. **Role system**: `UserRole` enum + `users.role` column (migration `d4e5f6a7b8c9`, applied; existing users default STUDENT). `require_admin` dependency → 403. Role resolved from the DB per request; only `provision_admin.py` grants ADMIN (no self-assignment). `role` now returned by `/student/me` and `/student/sync`.
2. **Validation registry**: `backend/app/services/event_registry.py` — `EVENT_TYPE_RULES` for all 14 types ported from legacy `AcademicEventRegistry` + engine closure semantics; `validate_event()` raises `EventValidationError`; substitution days come from engine `DAY_NAMES`.
3. **Mutation API (admin-only)**: `POST /api/v1/events` (201), `PATCH /api/v1/events/{event_id}` (partial via `model_fields_set`), `DELETE /api/v1/events/{event_id}` (safe deactivation, ADR 004; reversible via PATCH). 409 on identical ACTIVE duplicate (ported from legacy js/events-controller.js); 404 for missing event/subject; 422 for validation. Repo → service → endpoint layering; one transaction per mutation.
4. **Admin UI (additive)**: `eventRules.ts` registry mirror; `EventFormDialog` (create/edit, field visibility per type, never sends non-model fields); `EventRow` optional admin actions with two-step deactivate confirm; `/tools/events` admin mode gated by `useProfile().role === "ADMIN"` (Add Event toolbar + row actions + dialog), revalidating the current calendar month after mutations. Students see the unchanged Phase 6.4 page.
5. **Seeding**: `seed_academic_events.py` — 17 QUIZ_DAY events derived from authoritative `quiz_schedules` (BCS-054 Q3 UNRESOLVED excluded). Idempotency key `(event_type, subject_id, start_date, end_date)`; rerun skips; deactivated rows never resurrected. No institutional holiday/break dates exist in the repo — documented data gap, nothing invented.
6. **Verification**: `verify_phase_6_5.py` — 23/23 PASS across security, mutations, duplicate guard, partial PATCH semantics, read-contract regression, calendar reflection, and seeding idempotency; test rows hard-deleted afterward.

## Database State After 6.5

- `academic_events`: exactly 17 seeded QUIZ_DAY rows. `users`: 1 ADMIN (2401220100027), 29 STUDENT. `class_sessions`: 684 rows untouched. No other table mutated.

## Remaining Work

- Phase 6.6 — event→engine integration (event→class_sessions, holiday→cancellation, extra/substitution lecture generation, quiz-window mutation). Explicitly NOT implemented in 6.5.
- Phase 6.7 — verification/freeze.
- Institutional holiday/break/working-Saturday dates — pending authoritative input from the product owner.

---

# AttendanceDash Pro — Phase 6.6 Walkthrough

> **PHASE 6.6 COMPLETE** — events now drive the session pipeline. A persisted
> holiday cancels the day's classes, CLASS_CANCELLED cancels exactly the
> intended session, EXTRA_*/SURPRISE_QUIZ materialize extra sessions, and a
> working Saturday / substitution projects the substituted timetable into
> `class_sessions` — matching the legacy engine's effective-schedule behavior
> (docs/S4.3: ACADEMIC EVENT = EXACT-DATE SCHEDULE MUTATION) without rewriting
> any engine. Idempotent, transactional (same commit as the event mutation),
> and attendance-safe (history is never mutated).

## What Phase 6.6 Delivered

1. **Synchronizer** (`backend/app/services/event_session_service.py`): for each date an event touches, the engine's desired schedule is computed from ALL active events (closure → empty day; CLASS_CANCELLED → remove one matching occurrence; EXTRA_*/SURPRISE_QUIZ → +1 extra occurrence; substitution/working-Saturday → substituted timetable) and `class_sessions` is reconciled state-based: cancellations become `is_cancelled=True` (rows never deleted), extras become `is_extra=True` rows, weekend projections are deleted when reverted. Double sync = no-op (idempotent by construction).
2. **Session repository** (`backend/app/repositories/session_repo.py`): bounded span reads + writes + attendance-guard; sessions are only created inside the baseline window.
3. **Same-transaction wiring** (`backend/app/services/event_service.py`): create/update/deactivate each run the sync before commit; updates sync the union of old+new ranges so a moved event restores its old dates; deactivation reverts every effect.
4. **Counting corrections**: cancelled sessions were being counted as pending — `attendance_repo` count queries, `dashboard_service` overall/weekly, and `calendar_service` month session counts now exclude `is_cancelled`. Read shapes and engines untouched.
5. **Verification** (`backend/scripts/verify_phase_6_6.py`): **36/36 PASS** against the real DB with minted JWTs — every event type's effect, exact-count assertions (1 cancellation, +1 extra), read contracts (calendar day states, daily Cancelled states, extra visibility, eligibility byte-identical), deactivation reversal, rollback-transaction safety (attended extras preserved), and a final assertion that the database returned to its exact baseline (17 events / 684 sessions / 0 cancelled / 0 extra / 89 attendance records). Phase 6.5 regression: 23/23 PASS.

## Database State After 6.6

- Exact pre-6.6 baseline: `academic_events`=17, `class_sessions`=684 (0 cancelled, 0 extra), `attendance_records`=89, enrollments=18, subjects=9, quiz_schedules=18, users=30 (1 ADMIN). No test residue; rollback tests committed nothing.

## Remaining Work

- Phase 6.7 — verification/freeze (next; not started).
- Institutional holiday/break/working-Saturday dates — pending authoritative input.

---

# AttendanceDash Pro — Phase 6.7 Walkthrough

> **PHASE 6.7 COMPLETE — PHASE 6 FROZEN.** Final verification of the whole
> Calendar & Academic Events subsystem (6.1 → 6.6) as one coherent system:
> 90/90 checks across three verifiers, exact database baseline restored, and a
> clean architectural review. Not a feature phase — nothing was redesigned.

## What Phase 6.7 Delivered

1. **`verify_phase_6_7.py` (NEW) — 31/31 PASS**: engine weekend convention (DEFAULT_WEEKENDS `[0,6]`, JS getDay mapping), MID_SEMESTER_BREAK closure + priority tier 60, `/events` active-default/inverted-422/upcoming, calendar read model (outside-semester empty truth, July/December clamping, weekend correctness, QUIZ_DAY working), all six closure types cancel their day's sessions with rows preserved, EXTRA_TUTORIAL/EXTRA_PRACTICAL exactly-one extras, WORKING_DAY_OVERRIDE calendar-only (working day, zero session mutation), cancelled session → 409 on attendance, deactivate→re-enable convergence, seeding integrity (17 QUIZ_DAY, nothing fabricated), and a full 10-table baseline restoration assertion.
2. **Regression**: 6.5 → 23/23, 6.6 → 36/36 — combined **90/90 PASS**; verifiers converge in any order; `compileall` PASS.
3. **Static review**: calendar & events UIs render the backend read model only (no weekend/holiday/session math, no business logic in React); layering API→Service→Repository→DB intact; `EventSessionSynchronizer` is the only session-sync path; no engine rewrites, no hardcoded dates in `app/`, no N+1, role resolved from the DB per request.

## Database State After 6.7

- Exact baseline: `academic_events`=17, `class_sessions`=684 (0 cancelled, 0 extra), `attendance_records`=89, enrollments=18, subjects=9, quiz_schedules=18, users=30 (1 ADMIN). No test residue.

## Phase 6 is now FROZEN

- Frozen: calendar engine semantics, `/api/v1/events` + `/api/v1/calendar*` contracts, calendar/events UI, event registry, event service + `EventSessionSynchronizer`, the three verifiers, and the baseline. Changes require a new phase.
- Known limitations frozen as documented: baseline-span-bounded session materialization, extra sessions without event linkage, the institutional-date data gap (pending authoritative input), today-clamped views.
- Browser/manual testing remains the user's responsibility.

---

# AttendanceDash Pro — Phase 7.0 Walkthrough

> **PHASE 7.0 COMPLETE — READ-ONLY QUIZ ELIGIBILITY & SCHEDULE REALITY AUDIT.**
> No implementation, no DB writes, no commit. Deliverable: `docs/phase_7_0_quiz_eligibility_audit.md` (A–Y).

## What Phase 7.0 Delivered

1. **Eligibility math verified against real data** (engine-in-process, SELECT-only): formula `(Lecture% + Tutorial%)/2 ≥ threshold` (lecture-only when no tutorials) is byte-identical to the legacy JS engines; ADR-010 windows identical; optimizer tie-breaks identical; practicals excluded from eligibility but counted in overall; quiz-day attendance flows through normal sessions; SURPRISE_QUIZ/EXTRA_* flow through `is_extra` sessions.
2. **Schedule reality captured:** thresholds 70/75/75 from `eligibility_policies`; 17 dated SCHEDULED quiz_schedules + **BCS-054 Q3 UNRESOLVED**; 17 QUIZ_DAY events; semester V 2026-07-15 → 2026-12-31; 9 subjects (6 theory + 3 labs).
3. **Headline finding (Q-D1):** backend `is_eligible` means *reachable* — with pending classes it is `True` even at 15–36% attendance. All 18 resolved subject×cycle results report eligible=True in current data; the legacy engine would label every one "NEEDS ATTENDANCE". The dashboard quiz snapshot reports 6/6 "Eligible".
4. **Reference-UI contract gap (Q-D2):** the API cannot currently supply window lecture/tutorial attended-total-%, average, Criterion I/II PASS/FAIL, quiz date, recoverable state, or explanation — the mandated subject cards cannot be built without client-side math (prohibited).
5. **Decision points Q-D1…Q-D10** documented (audit §R), incl. rule G (students add/remove events) vs the frozen admin-only event mutations (Q-D7).

## Database State After 7.0

- Exact baseline preserved — zero writes: events=17, sessions=684 (0 cancelled, 0 extra), records=89, enrollments=18, subjects=9, quizzes=18, users=30 (1 ADMIN).

## What's Next

- Decisions Q-D1…Q-D10 from the product owner, then **Phase 7.1**: eligibility payload extension (window counts/percentages/criteria/quiz date/tri-state status/explanation) + reference subject-card UI + verifier `verify_phase_7_1.py` + 90/90 regression + baseline restore. No implementation until authorized.

---

# AttendanceDash Pro — Phase 7.1 Walkthrough

> **PHASE 7.1 COMPLETE — CANONICAL QUIZ ELIGIBILITY CONTRACT + REFERENCE SUBJECT CARDS.**
> Report: `docs/phase_7_1_implementation_report.md`.

## What Phase 7.1 Did

1. **Completed the quiz schedule.** BCS-054 Quiz III was the last unresolved quiz. The seed pipeline's own authoritative source (`timetable.json`) carries the date **2026-10-23**, but `seed_academic_baseline.py` hardcoded an "officially unresolved" override. The override was removed, the live `quiz_schedules` row updated (2026-10-23, SCHEDULED), and the canonical `seed_academic_events.py` created the matching 18th QUIZ_DAY event (calendar/read-only — zero session mutation). The canonical schedule is now 18/18 dated SCHEDULED, byte-exact vs the authoritative source. BCS-054 Q1/Q2 windows unchanged; Q3 gains the real window [2026-09-28 … 2026-10-22].
2. **Built the canonical eligibility contract on the existing API** (additive extension, no parallel system). `EligibilityResult` now exposes: `state` (ELIGIBLE / RECOVERABLE / NOT_ELIGIBLE / UNRESOLVED), window lecture/tutorial counts + percentages, combined average, `required_percentage`, `quiz_date`, `subject_name`, `category`, Criterion I/II (value, threshold, passed, explanation), the final "(Criterion I) OR (Criterion II)" combination, `recoverable`, `explanation`. `is_eligible` now means *currently eligible* — the Q-D1 divergence is fixed, and the dashboard quiz snapshot corrects itself with zero dashboard changes.
3. **Implemented the official policy route logic** (`S4_PRODUCT_SPEC.md:32-33`): Criterion I (Lecture % ≥ required) OR Criterion II (Combined average ≥ required) = Eligible; both thresholds come from the persisted `eligibility_policies` (Q-D5 fixed). Labs are excluded via the authoritative `subjects.quiz_applicable` flag → 404 (Q-D4 fixed).
4. **Reused the engine, didn't rewrite it.** State derivation evaluates the same counts/formulas at the current scenario (pending not yet attended) and the best-case scenario (pending all attended); RECOVERABLE = best case passes, NOT_ELIGIBLE = neither passes. `optimize_attendance`/`meets_attendance_target`/`get_attendance_window` are untouched; must-attend/safe-skip remain the optimizer's exact output.
5. **Rebuilt `/tools/quiz-schedule` as "Quiz Eligibility"** with the reference subject-card design: cycle tabs (Quiz I/II/III per the product spec), one card per quiz-applicable subject — code, THEORY badge, name, status badge, Lecture/Tutorial attended-total-%, Average vs Required, expandable **View Calculation** (Criterion I, Criterion II, Final Result, Must Attend / Safe Skip), explanation. Loading skeletons, per-card error + Retry, empty and Unresolved variants included. React is presentation-only; every value renders the backend contract.
6. **Verified everything.** New `verify_phase_7_1.py` — 26/26 checks (canonical schedule vs timetable.json, BCS-054 Q3, cycles, practical exclusion, QUIZ_DAY calendar-only, 18 upcoming events, windows, formulas, all four states incl. rollback scenarios, criteria + final OR, optimizer parity, UI analytics contract, labs 404, per-user scoping, history intact, quiz-day + surprise-quiz canonicality, exact baseline restore). Frozen regression: 6.5 23/23, 6.6 36/36, 6.7 31/31 (its four authoritative-count assertions maintained 17→18 — the schedule genuinely changed; assertion strength unchanged). Static gates green (compileall, tsc, ESLint, production build).

## Database State After 7.1

- New baseline (verified after every verifier run): events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN).
- The only mutation: the BCS-054 Q3 `quiz_schedules` row (2026-10-23, SCHEDULED) plus the canonical 18th QUIZ_DAY event — minimal, documented, reversible (exact reversal steps in the implementation report).

## What's Next

- **Phase 7.2 (requires authorization):** Q-D6 teaching-day counting · Q-D8 overall denominator · Q-D7 student event-mutation capability · date-aware default cycle tab · further reference-UI polish. Each change must be its own phase with its own verifier + full regression (6.5/6.6/6.7 + 7.1).
- **HARD STOP after Phase 7.1** — no Phase 7.2 work starts without explicit authorization.

---

# AttendanceDash Pro — Phase 7.2 Walkthrough

> **PHASE 7.2 COMPLETE — QUIZ ELIGIBILITY ANALYTICS REFINEMENT.**
> Report: `docs/phase_7_2_implementation_report.md`.

## What Phase 7.2 Did

1. **Resolved Q-D6 (raw-range counting) — NOT a defect.** The backend counts raw non-cancelled sessions in the window; the legacy engine enumerated teaching days. These are provably the same set: `expand_baseline.py` creates sessions only on engine teaching days, the synchronizer cancels sessions on closures (excluded from counts) and materializes extras only on working days, and cancelled sessions are filtered by `get_subject_counts_between`. Swapping to a separate teaching-day enumeration would create a second calendar-semantics model — forbidden. No counting change; `verify_phase_7_2.py` proves the equivalence for all 18 combos, plus closure exclusion (+409 on marking), extra-session counting, and the weekend guard (a SURPRISE_QUIZ on Saturday materializes zero sessions).
2. **Resolved Q-D8 (overall denominator) — recorded-only, made explicit.** The authoritative semantics (legacy ERP `computeCurrentOverallAttendance` + S4 §10 current domain) exclude pending from the CURRENT denominator but never convert pending to absent: it is always counted and displayed separately. The dashboard overall card already showed attended/recorded/pending; the quiz eligibility card now shows a muted "· X pending" on the Lecture/Tutorial rows so the pending treatment is explicit everywhere. Verified: 71.43% (recorded-only) vs explicitly-not 46.51% (pending-inclusive), identical history/subject semantics, and null (not 0%) for the zero-record student.
3. **Resolved Q-D7 (mutation / eligibility timing) — intentional product restriction (B).** Attendance mutations are student-scoped, enrollment-authorized, and cancelled-session-protected — students mark their own attendance. EVENT mutations stay admin-only (frozen Phase 6.5; rule G is a future product capability awaiting a decision). Eligibility is computed read-time: a mutation propagates to the next eligibility read immediately. No security weakened; boundaries regression-proven (student 403 on events, 409 on cancelled, 403/404 on non-enrolled, mutation→eligibility immediacy).
4. **Added the date-aware default Quiz tab.** New canonical read-only endpoint `GET /api/v1/quiz-eligibility/current-cycle` derives the currently-relevant cycle from the authoritative schedule (next upcoming SCHEDULED quiz → latest resolved cycle → documented fallback Quiz I; never invents a date). The Quiz Eligibility page preselects its tab from that answer; manual tab selection always overrides and never mutates backend state. Today the default is Quiz I (next quiz 2026-08-24); the Quiz I→II→III→latest_resolved→fallback transitions were verified deterministically inside rollback transactions.
5. **Verified everything.** New `verify_phase_7_2.py` — 26/26 checks (Q-D6 ×4 · Q-D8 ×5 · Q-D7 ×4 · current-cycle ×6 · BCS-054 Q3 = 2026-10-23 · UNRESOLVED-only-when-genuine · labs 404 · dashboard-snapshot == recomputed canonical eligibility · Track/History/Eligibility consistency · per-user isolation · exact baseline restore). Frozen regression: 6.5 23/23, 6.6 36/36, 6.7 31/31, 7.1 26/26 — no assertions weakened. Static gates green (compileall, tsc, ESLint, production build).

## Database State After 7.2

- Exact baseline preserved — ZERO mutations: events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN). BCS-054 Quiz III = 2026-10-23 confirmed.

## What's Next

- **Phase 8 — Attendance Analytics / Intelligence** (roadmap next): overall/subject analytics, forecasting, SAFE/WATCH/AT-RISK/CRITICAL risk states — on the existing canonical engines.
- Q-D9 (quiz-day attendance without a session) and rule G (student event capability) each require an explicit product decision before their own phase.
- **HARD STOP after Phase 7.2** — no commit made; browser/manual testing remains the user's responsibility.

---

# AttendanceDash Pro — Phase 8.0 Walkthrough

> **PHASE 8.0 COMPLETE — ATTENDANCE ANALYTICS & INTELLIGENCE AUDIT / CONTRACT DESIGN.**
> Report: `docs/phase_8_0_attendance_analytics_audit.md`.

## What Phase 8.0 Did

1. **Audited the analytics architecture (read-only).** There is no dedicated analytics layer: the dashboard service is the de-facto aggregator and every existing surface (Home, Subjects, Quiz Eligibility, History, Track, Calendar) already consumes the canonical engines — no second attendance engine, no second calendar enumeration, no React business math. The canonical chain (class_sessions → attendance_records → engines → analytics read model → API → React) is intact and frozen.
2. **Built the full analytics inventory (23 metrics).** Every metric currently computed or displayed was catalogued with its exact formula, source, and treatment of Pending / Cancelled / Extras / Practicals / L-T separation / semester & quiz-window bounds. Findings: all current % are recorded-only (pending never absent, surfaced separately); forecast % = pending-as-attended; overall = ERP Σatt/Σrecorded (class-weighted, NOT subject-averaged); cancelled excluded everywhere; practicals counted in overall but excluded from quiz eligibility; status banding = SAFE ≥ 80 / WATCH ≥ 60 / CRITICAL < 60 on current (S4.1 reconciliation).
3. **Identified the 4 legacy gaps — all additive, none a new formula:** practical % (Python engine computes counts but exposes no practical pct); subject-level 75% must-attend/safe-skip (legacy `optResult`); overall forecast (legacy `computeForecastOverallAttendance`); forecast-impact deltas (legacy `calcForecastImpact`). These are extensions of existing engine outputs, so Phase 8.1 can bridge them without touching engine mathematics.
4. **Flagged (NOT fixed) React duplications:** `WeeklyAttendanceCard` re-derives the day-bar % from backend counts; `SubjectAttendanceCard` applies its own 75/65 banding (vs canonical 80/60) and hardcodes cycle=1; dead `TodayClassesCard`/`FormulaCard` remain. Also documented performance findings (N+1 in the dashboard quiz snapshot and subject summaries, overlapping range scans, an import-time `date.today()` default) and one security-consistency gap (`/attendance/summary/{code}` lacks the enrollment 404 the quiz endpoint has).
5. **Withheld undefined metrics.** AT-RISK (roadmap's 4-state taxonomy) and weekly/semester trend series have NO definition anywhere — candidate definitions were provided for product approval; nothing was invented.
6. **Produced the Phase 8.1 contract (not implemented):** additive extension of `SubjectAttendanceSummary` (practical %, subject-level optimization, enrollment scope) + `GET /api/v1/analytics/overview` (overall current/forecast/pending + weekly series + per-subject optimization) + dashboard N+1 fixes + `verify_phase_8_1.py` — all pure consumers of the canonical engines.
7. **Verified (read-only).** compileall PASS · `npx tsc --noEmit` PASS (0 errors) · frozen `verify_phase_7_2.py` 26/26 PASS · DB baseline exact.

## Database State After 8.0

- **ZERO mutation** — SELECT only: events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN) · BCS-054 Quiz III = 2026-10-23 confirmed.## What's Next

- **Phase 8.1 (requires explicit authorization)** — backend-only additive analytics read model per the audit contract (§L/§R/§W). No UI, no schema change, no new engine, no new formula.
- Product decisions T-1…T-4 (AT-RISK band, trend scope, dedicated analytics page, multi-class forecast phrasing) before those features ship.
- Q-D9 and rule G remain separate product decisions.
- **HARD STOP after Phase 8.0** — no commit made; Phase 8.1 NOT STARTED; browser/manual testing remains the user's responsibility.

---

# AttendanceDash Pro — Phase 8.1 Walkthrough

> **PHASE 8.1 COMPLETE — CANONICAL ANALYTICS READ MODEL (BACKEND).**
> Report: `docs/phase_8_1_implementation_report.md`.

## What Phase 8.1 Did

1. **Extended the subject summary contract additively.** `GET /attendance/summary/{subject_code}` now also returns `current_practical_pct` / `forecast_practical_pct` and an `optimization` object (`lecture_deficit`/`tutorial_deficit` = must-attend, `safe_skip_lecture`/`safe_skip_tutorial` = safe-skip) computed by the attendance engine's own `optimize_attendance` against the subject's semester-to-date L/T counts at the documented 75% target. Practicals ride the same canonical class-session/attendance-record pipeline as L/T — no quiz-window dependency, no separate lab engine, Pending stays Pending, cancelled stays excluded. Every pre-existing field is unchanged.
2. **Added `GET /api/v1/analytics/overview`** (authenticated, enrollment-scoped, read-only). It returns overall current (ERP Σatt/Σrecorded, recorded-only — never pending-as-absent), overall forecast (pending treated as attended — no mutation, canonical semantics), pending count, a Monday-start weekly read-model series (recorded-only with null gaps), and per-subject current/forecast/optimization. All derived from the canonical engines — the analytics layer is a read model, not a second attendance engine.
3. **Fixed the dashboard N+1s without changing the response contract.** The quiz snapshot now uses a batched eligibility path (one canonical engine route via the shared `_evaluate_subject`), subject summaries use one grouped count query, and Today/Overall/Weekly share a single enrollment-scoped range scan. Dashboard JSON stays byte-identical; measured 54 → 23 queries on the read path.
4. **Fixed endpoint hygiene.** `/attendance/summary` resolves its default date per request instead of at import time, and `/attendance/summary/{code}` now returns the same enrollment 404 the quiz endpoint uses — no student can read analytics for a subject they aren't enrolled in.
5. **Left the Phase 8.0-flagged React duplications untouched** (per contract §13): `WeeklyAttendanceCard` day-bar %, `SubjectAttendanceCard` banding/cycle=1, dead `TodayClassesCard`/`FormulaCard` — inspected only, deferred to the frontend phase.
6. **Verified end-to-end.** `verify_phase_8_1.py` 22/22 (auth, scoping, ERP overall, forecast, pending, practical %, must-attend/safe-skip + optimizer edge cases, weekly read model, dashboard compatibility + query counting, runtime date, enrollment protection, no duplicate math, exact baseline, frozen 7.2 invariants); frozen regressions 6.5 23/23 · 6.6 36/36 · 6.7 31/31 · 7.1 26/26 · 7.2 26/26; compileall + `npx tsc --noEmit` PASS.

## Database State After 8.1

- **ZERO mutation** — SELECT only: events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN) · BCS-054 Quiz III = 2026-10-23 confirmed.

## What's Next

- **Phase 8.2 (requires explicit authorization)** — frontend consumption of the Phase 8.1 read model: practical % + must-attend/safe-skip on the Subjects page, overall forecast + weekly series from `/analytics/overview`, replace the duplicated card banding and hardcoded cycle with backend fields, remove dead components — all within the existing design system.
- Product decisions T-1 (AT-RISK), T-2 (trend scope), T-3 (dedicated Analytics page), T-4 (multi-class forecast phrasing) before those features ship.
- Q-D9 and rule G remain separate product decisions.
- **HARD STOP after Phase 8.1** — no commit made; Phase 8.2 NOT STARTED; browser/manual testing remains the user's responsibility.

---

# AttendanceDash Pro — Phase 8.2 Walkthrough

> **PHASE 8.2 COMPLETE — FRONTEND CONSUMPTION OF THE CANONICAL ANALYTICS READ MODEL.**
> Frontend-only; no backend change, no DB mutation, no commit.

## What Phase 8.2 Did

1. **Added the typed analytics client.** New `AnalyticsOverviewResponse` / `OverallAnalytics` / `WeeklyAnalyticsItem` / `AnalyticsSubjectItem` types match the Phase 8.1 backend schema exactly (no invented fields), `SubjectAttendanceSummary` gained the additive Phase 8.1 fields (`current_practical_pct`, `forecast_practical_pct`, `optimization`), and a new `useAnalyticsOverview()` SWR hook consumes `GET /api/v1/analytics/overview` with the standard cache.
2. **Made the Subjects page fully backend-driven.** `SubjectAttendanceGrid` fetches every subject's analytics from a SINGLE overview request (no more per-subject summary N+1) and passes each backend summary to its card. Cards now render practical % (current + forecast) and the subject-level 75% must-attend/safe-skip straight from `summary.optimization`. The duplicated client-side 75/65 banding was removed — the backend has no per-subject status, so none is invented — and the hardcoded `cycle = 1` was replaced with the canonical `useCurrentQuizCycle()` (Phase 7.2) that drives the Eligible/Defaulter badge.
3. **Made the Dashboard analytics backend-derived.** `OverallAttendanceCard` shows an additive backend forecast line (pending-as-attended). `WeeklyAttendanceCard` now renders the backend Monday-start weekly series — backend `current_pct`, with `null` weeks shown as truthful gaps instead of the old React `attended/recorded × 100` day-bar derivation.
4. **Removed the dead components.** `TodayClassesCard.tsx` and `FormulaCard.tsx` were verified unused (zero imports, zero routes) and deleted.
5. **Kept the design system intact.** Existing Card/Badge/typography/spacing and the SAFE/WATCH/CRITICAL visual language are unchanged; the analytics feels native.
6. **Verified statically.** `npx tsc --noEmit` PASS (0 errors), ESLint clean on all changed files, `next build` PASS (14 routes). Confirmed zero attendance/safe-skip/eligibility/quiz-cycle mathematics in React — every rendered value is a backend field. Backend and database untouched.

## Database State After 8.2

- **ZERO mutation** — no backend/database file touched. Phase 8.1 baseline unchanged.

## What's Next

- **Phase 8.3 (requires explicit authorization)** — only after reviewing Phase 8.2; nothing is queued.
- Product decisions T-1 (AT-RISK), T-2 (trend scope), T-3 (dedicated Analytics page), T-4 (multi-class forecast phrasing) before those features ship.
- Q-D9 and rule G remain separate product decisions.
- **HARD STOP after Phase 8.2** — no commit made; Phase 8.3 NOT STARTED; browser/manual testing remains the user's responsibility.

---

# Attendance UI Refinement — Specification Alignment + Reference UI

> **COMPLETE (2026-08-15) — PASS.** Full report: `docs/attendance_ui_refinement_report.md`.

## What This Phase Did

Aligned the implementation with the authoritative attendance specification and rebuilt the Attendance (/subjects) cards to the reference UI — without putting business math into React. Two spec conflicts were escalated and **authorized by the user**:

1. **Quiz-day attendance = real attendance event** → quiz-day sessions materialized on every SCHEDULED quiz date (7 created; sessions 684 → 691; eligibility untouched because windows end at `quiz_date − 1`).
2. **Events are student-adjustable** → students may add/remove the flexible subject-scoped event types (extras, cancellations, surprise quizzes) for their own enrolled subjects; global/closure/quiz-schedule events stay admin-only; the synchronizer never cancels/deletes quiz-day sessions.

## Backend Changes (smallest correct)

- Consolidated attendance banding (SAFE/WATCH/CRITICAL) into the attendance engine — one definition shared by dashboard, analytics, and subject summaries.
- `SubjectAttendanceSummary` gains additive `required_pct` (75) and `status` fields (backend-emitted; React never bands).
- Student event authorization (service + repo + endpoint): enrollment-scoped, flexible types only.
- Fixed a latent defect: successful attendance mutations previously 500'd (`student_id` → `user_id` in the response schema) — required for quiz-day attendance to be recordable.
- New scripts: `materialize_quiz_day_sessions.py` (idempotent, `--undo` reversible) and `verify_attendance_spec_alignment.py` (15/15).

## Frontend Changes

- **Reference Attendance cards**: header (code · THEORY/LAB · name · canonical status badge), prominent primary %, lecture/tutorial sections with required + must-attend/safe-skip, combined average with formula caption, practical section for lab subjects, expandable Details with real backend forecast/optimizer values. All values are backend fields.
- **Events page**: students get the Add Event surface restricted to flexible subject-scoped types; edit/deactivate appear only on events they may mutate.

## Verification

- `verify_attendance_spec_alignment.py` **15/15**; frozen regressions 6.5 **27/27** · 6.6 **36/36** · 6.7 **31/31** · 7.1 **26/26** · 7.2 **26/26** · 8.1 **22/22** (deliberate documented re-scopes in 6.5/7.2/7.1 only). compileall / `tsc --noEmit` / ESLint / `next build` green.

## Database State After Refinement

- **Documented, authorized, minimal**: sessions 684 → **691** (7 quiz-day LECTURE sessions, no attendance records; reversible via `--undo`). Events=18 · cancelled=0 · extra=0 · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN). BCS-054 Quiz III = 2026-10-23 unchanged.

## What's Next

- **Phase 8.3 (requires explicit authorization)** — nothing is queued; T-1 (AT-RISK), T-2 (trend scope), T-3 (dedicated Analytics page), T-4 (multi-class forecast phrasing), Q-D9 and rule G remain product decisions.
- **HARD STOP after the Attendance UI Refinement** — no commit made; browser/manual testing remains the user's responsibility.

---

## Phase 8.2 — Attendance Monitoring + Lab Domain Correction

Corrected the Attendance (/subjects) page into a pure attendance-monitoring surface and established the laboratory domain foundation.

### The "14" was traced, not assumed

The reported `11 / 14` denominator comes from the **canonical session table**, not a quiz window: `get_subject_counts_for_user` counts non-cancelled `class_sessions` through today, and every theory subject has exactly 14 real lectures since 2026-07-15. Verified: totals == direct SQL counts; an inserted session changes the total (no constant); moving a quiz date leaves the attendance summary byte-identical. The page's real defect was **presentation ownership** — quiz strategy rendered on an attendance card.

### Attendance Health (backend-owned)

New canonical `classify_attendance_health` in the attendance engine, emitted additively as `health` on `SubjectAttendanceSummary`: **HEALTHY ≥ 75 · WATCH 65–<75 · AT RISK 60–<65 · CRITICAL <60**. Legacy `status` (SAFE/WATCH/CRITICAL) stays emitted for the frozen dashboard/analytics surfaces; only the Attendance card presentation switched. React maps health to existing semantic tokens — it never bands.

### Attendance card (attendance-only)

Compact horizontal redesign: code · THEORY/LAB · name · Health badge → large "Overall Attendance" % → balanced Lecture/Tutorial blocks (attended/total + %) → formula caption → View Details (attended/missed/pending only). Labs: Practical Attendance + backend-backed "Mid-Sem Practical" row. All quiz strategy (must-attend, safe-skip, forecast, current-vs-forecast, required 75%, Defaulter badge) removed.

### Laboratory domain (smallest safe foundation)

Four concerns kept separate: practical attendance (canonical sessions), experiment curriculum (`laboratory_experiments`, empty — no fabricated data), student progress (`laboratory_records`, empty), and mid-sem designation (NEW: `class_sessions.designation`, migration `e5f6a7b8c9d0`, ADMIN-only `PUT/DELETE /api/v1/laboratory/{code}/mid-sem`). The mid-sem is tied to an actual PRACTICAL session — never `experiments >= 5 → midsem`, never a computed date; attendance against it uses the normal mutation. The missing faculty scheduling authority is documented, not invented.

### Verification

- `verify_phase_8_2.py` — **18/18** (session-derived totals, no fixed denominator, quiz-window independence, tutorial/lecture-only formulas, cancelled-practical exclusion, canonical practical attendance, no experiment inference/fabrication, unchanged Quiz Eligibility, exact baseline, Health boundaries, session-bound admin mid-sem).
- Frozen regressions — 6.5 **27/27** · 6.6 **36/36** · 6.7 **31/31** · 7.1 **26/26** · 7.2 **26/26** · 8.1 **22/22** · attendance-spec **15/15**.
- One documented correction: `verify_phase_7_1` check 23 was **explicitly re-baselined `records == 89` → `records == 92`** (authorized fixed fixture update). The +3 are legitimate BCS-501 marks entered through the canonical attendance mutation path before the audit; the assertion keeps a FIXED expected count — no dynamic baseline.
- compileall / `tsc --noEmit` / ESLint / `next build` all green. Database baseline exactly restored (18/691/92/18/9/18/30, lab tables empty, zero designations).

### What's Next

- **Phase 9 (Laboratory System)** — real experiment management once authoritative curriculum data exists; a faculty scheduling authority is still a product decision.
- **HARD STOP after Phase 8.2** — no commit made; browser/manual testing remains the user's responsibility.

## Phase 9.0 — Laboratory Domain Audit & Specification (READ-ONLY)

Audited the entire laboratory domain end-to-end and produced the authoritative
specification: `docs/phase_9_0_laboratory_domain_audit.md`.

### Key conclusions

- **Attendance is already correct and complete** — lab practical attendance is
  canonical `ClassSession(PRACTICAL)` + `AttendanceRecord`; cancelled excluded;
  pending stays pending; current recorded-only; labs excluded from quiz
  eligibility (404). **No Phase 9 engine or rule change is required.**
- **The lab domain is an intentionally empty foundation** — `laboratory_experiments`
  / `laboratory_records` = 0 rows (no authoritative curriculum; nothing
  fabricated); mid-sem = ADMIN-designated session-level fact that never alters
  counting; students can never designate (403).
- **Capability classification** — experiment identity/number/title = partially
  supported (columns exist, catalog missing); description/submission/session
  link = not supported; date/marks/remarks/ordering = supported; faculty
  approval = partial (no signer identity); expected per-subject count = UNKNOWN
  (legacy "10" is not authoritative).
- **Lab turn ≠ experiment** — one turn can host one/many/no experiment
  (unlinked today), be cancelled, become a lecture (composed event facts), or
  host the mid-sem; nothing auto-designates mid-sem from experiment counts.
- **Gaps** — authoritative curriculum, experiment↔session linkage, FACULTY
  role, audit identity, dedicated lab page (the `/tools/laboratory` route
  currently hosts Track).
- **Blocking product decisions** — curriculum source · FACULTY vs ADMIN-only ·
  audit identity · session linkage · mid-sem progress check · student mutation
  boundary · grading/viva.

### Verification

- Read-only SELECTs + `verify_phase_8_2.py` **18/18** (baseline restore check
  11 PASS). DB byte-equivalent to the frozen baseline (18/691/92/18/9/18/30,
  lab tables empty, zero designations). No migration, no seed change, no
  commit.

### What's Next

- **Phase 9.1 (smallest safe increment)** — additive lab read model
  (summary / activity history), curriculum ingestion boundary (authoritative
  payloads only), experiment progress under the chosen authority, dedicated
  Laboratory page IA. Requires the §16 product decisions first.
- **HARD STOP after Phase 9.0** — audit + specification only; no code written;
  browser/manual testing remains the user's responsibility.

## Phase 9.0b — Product Decision Review (SPECIFICATION ONLY)

Produced `docs/phase_9_product_decisions.md`: the decision matrix that unlocks
Phase 9.1. Every recommendation is labeled FACT-from-repository / PRODUCT
RECOMMENDATION / UNKNOWN-or-requires-real-world-input.

### Decisions (recommended)

1. **Curriculum — E hybrid**: provenance-bound admin ingestion of an
   authoritative institutional catalog; nothing seeded until a real catalog
   exists; per-subject count = catalog row count, never a constant.
2. **Faculty role — defer**: STUDENT + ADMIN for 9.1; FACULTY only with a
   defined signature/grading workflow (9.2+).
3. **Audit identity — minimal additive**: timestamps + `signed_by` +
   `designated_by/at` + catalog provenance.
4. **Session linkage — nullable FK** `laboratory_records.class_session_id`
   (validated; multiple experiments per session allowed).
5. **Mid-sem rule — advisory only**: "Eligible for mid-sem designation (X of
   Y)" from the real catalog; designation stays a manual ADMIN act.
6. **Student boundary — two-tier**: self-track pending; elevated signs.
7. **Grading/viva — excluded from Phase 9**; separate assessment phase.

### Why these choices

The strongest repository facts driving them: a bare `date_conducted` cannot
disambiguate which of the two daily PRACTICAL sessions hosted an experiment
(⇒ nullable FK); no faculty concept exists anywhere (⇒ defer the role rather
than invent a workflow); the legacy "10" is non-authoritative (⇒ no constants,
catalog-derived counts only); Phase 8.2 already hard-forbids auto mid-sem
(⇒ advisory-only readiness); and grading has no authoritative basis (⇒ defer).

### Verification

Specification-only: no code, schema, migration, data, API, UI, seed, or
commit. DB untouched (18/691/92/18/9/18/30, lab tables empty, designations=0).

### What's Next

- **Phase 9.1 — Laboratory Attendance & Event Integration (COMPLETE
  2026-08-15).** Owner LOCKED the event-driven product decision. Two new
  Academic Events (`MID_SEM_PRACTICAL`, `LAB_CANCELLED`) resolve into the
  canonical `ClassSession` pipeline via the existing synchronizer: mid-sem
  reuses the timetable practical occurrence (or materializes exactly one
  extra on a non-lab day) and designates it (`ClassSession.designation`);
  lab cancellation uses canonical `is_cancelled`; cancellation wins on
  conflict; everything is state-based, reversible, and attendance-safe.
  Verifier `verify_phase_9_1.py` **28/28**; all frozen regressions green
  except 7.1 check 23 — **BASELINE DRIFT** (records 92 → 95: 3 legitimate
  owner-entered BCS-502 marks; verifier NOT modified; owner must authorize
  the fixed fixture 92 → 95). Full report:
  `docs/phase_9_1_implementation_report.md`.
- **Phase 9.2.1 — Laboratory Experiment Management (COMPLETE 2026-08-16).**
  Owner LOCKED the Phase 9.2.0 audit. Implemented strictly additively, with
  zero fabricated curriculum:
  - Migrations A `f1a2b3c4d5e6f` (experiment `description`, `is_active`,
    `UNIQUE(subject_id, experiment_number)`) and B `f6a5b4c3d2e1f` (record
    `class_session_id` FK + `signed_by`/`created_by`/`updated_by` FKs);
    alembic head `f6a5b4c3d2e1f`.
  - Full backend surface under `/api/v1/laboratory/{code}`: summary (reuses
    canonical `AttendanceService.get_summary`), curriculum, student record
    self-tracking (forced PENDING) with admin-only signing (`signed_by`/
    `signed_on`), admin experiment ingest/edit/deactivate, activity read
    model, session-linkage validation, duplicate 409, 404/403 authz matrix.
  - Dedicated `/laboratory` frontend route + nav item (Track page stays at
    `/tools/laboratory`): Practical Attendance / Experiments / Activity tabs;
    honest empty state when `catalog_available=false`; no React attendance
    math; no placeholder experiment counts.
  - Verifier `verify_phase_9_2.py` **29/29**; frozen regressions green: 6.5,
    6.6, 7.2, 8.1, attendance-spec, 8.2, 9.1. Known pre-existing drift
    (owner-entered, NOT 9.2.1 residue): 6.7 29/31 (checks 4/7 — 4 test events
    beyond the 18 seeded QUIZ_DAY) and 7.1 25/26 (check 23 — same records
    92 → 95 drift as Phase 9.1). Frozen verifiers NOT modified.
  - DB byte-equivalent to baseline: 22 events · 691 sessions · 95 records ·
    18 enrollments · 9 subjects · 18 quizzes · 30 users · cancelled=0 ·
    extra=0 · designated=0 · lab tables 0/0. No commit.
  - Full report: `docs/phase_9_2_1_implementation_report.md`.
- **HARD STOP after Phase 9.2.1** — Phase 9.2.2 (e.g., experiment-count
  guidance, FACULTY signing workflow, grading/viva) not started; no commit
  made.

## Focused Track Correction walkthrough (after Phase 9.2.1)

**Two-hour lab = one occurrence.** The timetable stores each two-hour lab as
two contiguous one-hour periods (two ClassSession rows). `practical_occurrence.py`
collapses them into one logical occurrence at read time everywhere: Track
shows one card ("01:00 PM – 03:00 PM · PRACTICAL") with one Present/Absent
action; one mutation creates exactly one AttendanceRecord; summary/history/
analytics/calendar denominators count blocks, never rows; a cancelled block
is excluded (never Pending/Absent). The attendance engine and its input
shapes are unchanged.

**Future dates view-only.** The mutation service rejects sessions dated after
the institution-local today (400, canonical Asia/Kolkata clock). Track
renders future sessions as "Upcoming" with no mutation controls and hides
"Mark all present"; reads are never restricted, and future event-created
sessions (e.g. a future MID_SEM_PRACTICAL) remain visible and designated.

**Verification.** New `verify_track_lab_fix.py` 16/16. Frozen verifiers that
encoded per-period counts were updated to the occurrence contract (6.6
22/23/24, 8.1, 8.2 1/6/7, 9.1 12/13, 7.2 5/6, attendance-spec 3) — no
assertion weakened. All frozen regressions green except the documented
pre-existing drift: 7.1 25/26 (records 92→95) and 6.7 30/31 (22 events vs 18
seeded QUIZ_DAY), which remain untouched pending owner authorization. DB ends
byte-identical to the documented 9.2.1 baseline. Report:
`docs/track_lab_attendance_correction_report.md`.

## Focused History Filters Correction (2026-08-16)

**Symptom.** /history loads unfiltered but crashes with `TypeError: Cannot read properties of undefined (reading 'total_count')` as soon as any filter is applied.

**Diagnosis.** The backend History API is correct — every filter (subject/state/inclusive dates/search), occurrence-level status matching (cancelled lab blocks = one Cancelled row), filtered `total_count`, and a summary over the full filtered set were verified in-process. The defect is frontend state logic: `useAttendanceHistory` keys SWR on the request URL, so any filter change (and any Load-more offset change) is a new SWR key with `history === undefined` while fetching. The Load-more button rendered whenever `isLoading` was true, then dereferenced `history!.total_count`.

**Fix.** (1) The Load-more button renders only when `history` exists and more rows remain; while a filtered/page request is in flight a spinner row renders instead of the button. (2) The filter-signature reset effect clears `rows` immediately, so the previous filter's rows are never displayed or mixed into the new result — the skeleton shows while the filtered request loads. No `keepPreviousData`, so stale-filter data is never shown. The 2-hour lab occurrence collapse is untouched: BCS-551 history is 4 blocks, not 8 rows, under every filter.

**Verification.** New `verify_history_filters.py` 20/20, exact DB baseline restored. Frozen regressions green except pre-existing owner-data fixture drift (7.1 24/26, 6.7 28/31, 8.1 21/22 — none weakened; 8.1 check 7 now sees the admin's owner-entered BCS-551 2026-07-20 Missed record). DB records 101 before and after; sessions 695→693 only via the frozen 6.6 documented startup cleanup of unattended owner extras. Report: `docs/history_filters_correction_report.md`.

---

## Walkthrough — Quiz Day Recovery + Verifier Hardening (2026-08-16)

**Symptom.** 18 seeded QUIZ_DAY events inactive, 7 quiz-day sessions missing (incl. the canonical 10-23 BCS-054), and the owner's BNC-501 07-31 EXTRA_LECTURE/SURPRISE_QUIZ sessions deleted. The forensic audit traced the deletions to **date/shape-based cleanup** in `verify_events_correction.py` and the quiz-day deactivation sweep in the event sync.

**Recovery.** Reactivated exactly the 18 seeds (quiz_schedules-backed + 08-14 creation window; owner events untouched). Restored the 6 canonical uncovered-date quiz-day sessions with the idempotent `materialize_quiz_day_sessions.py` — 10-16 BCS-502 is correctly absent (Option-B covered; the audit's 7th row was the owner's 08-17 test-event session, intentionally not restored). Attendance records untouched (122).

**Hardening.** All three cleanup sites now use **ownership/artifact-scoped** cleanup with explicit captured IDs, never date/shape windows:
- `verify_events_correction.py` — `finally` deletes only its own created events and materialized sessions.
- `verify_track_lab_fix.py` — deletes only its own mid-sem sessions (**delta** capture; on a lab day the collapsed daily view's occurrence id is a pre-existing timetable row and must never be captured as "created"), and un-cancels only the block its LAB_CANCELLED check cancels.
- `verify_history_filters.py` — un-cancels only the BCS-551 block its LAB_CANCELLED check cancels.

**Healing.** Re-running the hardened events-correction verifier re-materialized the owner's 07-31 extras through the canonical sync; they now survive every verifier run. A BCS-551 08-24 block row my own hardening initially deleted (via the collapsed-daily-view id) was restored in the generator's exact shape.

**Verification.** New `verify_quiz_day_restore.py` 11/11 (twice). Full suite: events-correction 42/42 · track-lab-fix 16/16 · history-filters 20/20 · 6.6 36/36 · 7.2 26/26 · 8.1 22/22 · 8.2 18/18 · 9.1 28/28 · 9.2 29/29 · attendance-spec 15/15 · quiz-day-materialization 14/14. Frozen verifiers NOT weakened; remaining reds are owner-data drift from the owner's duplicate active BNC-501 08-24 quiz-day event `6019a478` (6.5 check 20, 6.7 checks 4/6/7, 7.1 check 6). DB: records 122 unchanged, sessions 698, events 38, quizzes 18/18. Report: `docs/quiz_day_recovery_report.md`.
**Phase 8.3 — Analytics page (T-3) implemented.** The roadmap's dedicated-analytics-page decision is now resolved: `/analytics` renders the canonical Phase 8.1 read model verbatim — overall current/forecast with recorded-only semantics, the full Monday-start weekly/semester-trend series (dash = gap, never 0%), and subject-wise cards with Attendance Health, L/T/P counts, practical %, and the backend 75% must-attend/safe-skip optimizer (including the unreachable state). No backend/DB/formula change; React formats only. `tsc`, ESLint, `next build` green; 8.1 22/22 and 8.2 18/18 re-run green; DB baseline byte-identical.

**Analytics page removed (2026-08-17).** The dedicated `/analytics` route and its top-nav entry were removed; the Attendance tab is now the primary detailed attendance surface. The Phase 8.1 read model (`GET /api/v1/analytics/overview`) and its typed client (`useAnalyticsOverview`, `AnalyticsOverviewResponse` family) are unchanged and still power the Dashboard (overall forecast + weekly series) and the Attendance tab (per-subject health/optimizer/practical %). No backend, DB, formula, or semantics change.

---

# AttendanceDash Pro — Phase 10 Walkthrough (Settings, Feedback & Account Management)

> **PHASE 10 COMPLETE & FROZEN (2026-08-20).** Audit: `docs/phase_10_completion_audit_report.md`; final: `docs/phase_10e_implementation_report.md`. No commit made; Phase 11 NOT STARTED.

## What Phase 10 Did

1. **10.0 audit** — read-only reality check of the Phase 2 Settings/Feedback/Profile foundations (contracts, frontend integration, DB state); findings fed the phase.
2. **10A — Settings UI** — the Phase 2 Settings modal became a real surface (Notifications / Attendance / Calendar) with a single visual target per control, driven by real preference data.
3. **10B — Program + Profile completion** — `sections.program` column (migration `b1c2d3e4f5a6`), seeded `CSE`; `program` resolved from the stored section value in the profile read model (never parsed from the section name); `StudentProfileResponse` completed (program, section, semester, session, academic dates); ProfileModal edits persist via the real API; Profile page reconciled with the modal.
4. **10C — Real feedback system** — `feedback` table (migration `b1c2d3e4f5a7`) + model/repo/schema; `POST /api/v1/feedback` (JWT auth, 201, feedback_type enum BUG/SUGGESTION/QUESTION/PRAISE, message 10–1000 trimmed, optional context → null, server-side user_id/created_at; no GET/list/admin surface); FeedbackModal submits for real and never fakes success.
5. **10D — User preferences API + UI** — `user_preferences` table (migration `c1d2e3f4a5b6`) + `GET/PUT /api/v1/student/preferences` (lazy-create with server defaults false/false/MONDAY, replace semantics, user-isolated, no client identity selector); SettingsModal fully API-backed. **Storage/preference data only** — nothing sends reminders, marks attendance, or alters calendar/analytics.
6. **10E — Freeze corrections, verification & governance reconciliation** — audit found READY WITH MINOR FIXES; corrections applied (stale `not implemented` copy in FeedbackModal replaced with honest service-unavailable copy; stale program comment in `schemas/student.py` updated; new `backend/scripts/verify_phase_10c.py` added — closes the Phase 10C verification gap); all four governance docs reconciled (MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md).

## Verification (Phase 10E)

- `verify_phase_10c.py` **23/23**; `verify_phase_10d.py` **18/18**; compileall PASS; `tsc --noEmit` exit 0; targeted ESLint on Phase 10 frontend files exit 0; `next build` PASS.
- DB baseline restored byte-identical: 31 users (1 ADMIN) · 1 section (CSE-51, program CSE) · 47 events · 715 sessions (0 cancelled, 0 extra) · 142 records · 27 enrollments · 9 subjects · 28 timetable entries · 18 quizzes · 3 quiz cycles · 3 eligibility policies · 1 session · 1 semester · feedback 0 · userpreferences 0 · lab 0/0.
- Alembic: linear chain, single head `c1d2e3f4a5b6` == `alembic current`. Pre-existing full-repo ESLint findings (6 errors/3 warnings in login/signup/history/AuthContext/GlassCard/lib/api, origin pre-Phase-10) documented but **out of scope** — not touched.

## What's Next

- **Phase 11 — Notifications & Reminders (NEXT)** — consumes the Phase 10 preference values (class_reminders etc.); notifications must consume engine outputs, never independently calculate attendance.
- **HARD STOP after Phase 10E** — no commit made; Phase 11 NOT STARTED; browser/manual testing remains the user's responsibility.

---

# AttendanceDash Pro — Phase 11 Walkthrough (Notifications & Reminders)

> **PHASE 11 COMPLETE & FROZEN (2026-08-21).** Audit: `docs/phase_11/phase_11_architecture_audit.md`; 11A: `docs/phase_11/phase_11a_implementation_report.md`; 11B: `docs/phase_11/phase_11b_implementation_report.md`; 11D: `docs/phase_11/phase_11d_implementation_report.md`; 11E: `docs/phase_11/phase_11e_implementation_report.md`; 11F: `docs/phase_11/phase_11f_verification_report.md`. 11.0 + 11A + 11B + 11D + 11E complete; 11F final verification & freeze complete — verifiers deterministic on a used inbox (11A 19/19, 11B 23/23); 11C delivery model decision-gated/deferred, NOT implemented. No commit made.

## What Phase 11 Did So Far

1. **11.0 — Architecture & Discovery Audit (read-only).** Confirmed Phase 11 has zero delivery substrate today (no notification model/table/endpoint, no scheduler, no Web Push/SW/PWA — Phase 13 owns PWA), that `class_reminders` was the only preference with an active consumer candidate, and that `auto_mark_present` / `week_starts_on` remain storage-only (auto-mark must NOT be implemented without an explicit product decision). Recommended the smallest safe slice: **11A — backend notification read model + contracts**, generated on-read like every existing read model, with no DB change and no new infrastructure.
2. **11A — Backend notification read model & contracts.** Additive `NotificationKind` enum (CLASS_REMINDER, QUIZ_APPROACHING, ATTENDANCE_THRESHOLD, MUST_ATTEND, SAFE_SKIP, ACADEMIC_EVENT); `schemas/notification.py` (`NotificationItem` with deterministic natural-key `id` + reference fields, `NotificationsResponse` with server-generated `as_of`); `services/notification_service.py` (read-only projection of engine outputs, no persistence); `GET /api/v1/notifications` (JWT owner only, no client `user_id`), registered in `backend/app/api/api.py`.
   - **CLASS_REMINDER** — gated by the `class_reminders` preference (missing row = documented default off); current institutional week (Monday–Sunday) unmarked, non-cancelled sessions via the canonical `get_sessions_with_status` (enrollment-scoped, practical occurrences collapsed).
   - **QUIZ_APPROACHING** — the canonical "next upcoming quiz" (`get_current_quiz_cycle`, basis `next_upcoming`); no invented lookahead.
   - **ATTENDANCE_THRESHOLD** — canonical `classify_attendance_status` WATCH/CRITICAL (the same attention concept the dashboard uses).
   - **MUST_ATTEND / SAFE_SKIP** — the attendance engine's own `optimize_attendance` output (`is_reachable`, deficit / safe-skip) at the canonical 75% target.
   - **ACADEMIC_EVENT** — the identical selection the dashboard upcoming-events section uses (active, `end_date >= today`, enrolled-scoped, sorted, capped at 4).
3. **Verified.** `verify_phase_11a.py` **19/19** (auth, shape, server-generated `as_of`, client-identity spoof ignored, enrollment isolation/scoping, class_reminders off/on, cancelled excluded, week scope, auto_mark_present/week_starts_on inert, canonical quiz/attendance/event cross-checks, frozen-table baseline byte-identical, no notification table created, alembic head unchanged, exact artifact cleanup). compileall PASS. Alembic head `c1d2e3f4a5b6` unchanged; DB baseline byte-identical to the Phase 10E freeze (31 users · 47 events · 715 sessions · 142 records · 27 enrollments · 9 subjects · 18 quizzes · feedback 0 · userpreferences 0).

## Database State After 11A

- **ZERO mutation** — no migration, no notification table, no data change. Frozen system untouched.

## What's Next

- **Phase 11B (requires explicit authorization)** — notification persistence/read-state (migration + `notifications` table + repository, extending `NotificationService`; the 11A natural-key `id` is the dedup key).
- Remaining Phase 11: 11C delivery model (decision-gated: in-app only vs scheduled sweep), 11D frontend notification center UX, 11E remaining preference wiring, 11F phase completion.
- Open product decisions: multi-day reminder horizon, quiz horizon, delivery model, `auto_mark_present` semantics (recommendation: remains storage-only).
- **HARD STOP after 11A** — no commit made; 11B NOT STARTED; browser/manual testing remains the user's responsibility.

---

# AttendanceDash Pro — Phase 11B Walkthrough (Notification Persistence + Read-State)

> **PHASE 11B COMPLETE (2026-08-20).** Persists the Phase 11A notification projection without duplicate rows; adds read/dismiss state. Report: `docs/phase_11/phase_11b_implementation_report.md`. 11C–11F NOT STARTED. No commit made.

## What Phase 11B Delivered

1. **Migration `d1e2f3a4b5c6` (additive, single alembic head chaining `c1d2e3f4a5b6`)** — creates the `notifications` table and the `notificationkind` enum. Columns: `user_id` FK NOT NULL (owner always the authenticated JWT user; never client-supplied), `kind` (the Phase 11A `NotificationKind`, the same enum), `occurrence_key` (deterministic natural-key reference), `date`, nullable `subject_code` / `subject_name`, `message` TEXT, nullable typed source references (`session_id` / `quiz_cycle` / `event_id`), `is_read` / `is_dismissed` BOOLEAN NOT NULL DEFAULT FALSE, plus `id` / `created_at` / `updated_at` from the Base mixin. **`UNIQUE(user_id, kind, occurrence_key)`** enforces idempotency at the database. No relationships to attendance/events/quiz/lab tables — the inbox is isolated and consumes engine outputs at generation time.
2. **Deterministic identity / idempotency.** `occurrence_key` mirrors the Phase 11A natural-key `id` reference — session id for CLASS_REMINDER, quiz cycle for QUIZ_APPROACHING, event id for ACADEMIC_EVENT, subject code for ATTENDANCE_THRESHOLD / MUST_ATTEND / SAFE_SKIP. Generation snapshots each projection via `ON CONFLICT DO UPDATE`: the same logical occurrence refreshes in place (message + subject references + `updated_at` only) and **never creates a duplicate row**; genuinely distinct occurrences (different sessions/cycles/events/subjects) keep distinct rows. Regeneration preserves `date`, `is_read`, `is_dismissed` and `created_at`.
3. **Model / repository / service / API.** `app/models/notification.py` (`Notification`, registered in `app/models/__init__.py`); `app/repositories/notification_repo.py` (owner-scoped `upsert` / `get_inbox` newest-first with dismissed excluded / `get_by_id` / `count_unread` / `count_for_user` / `update_state` / `delete`); `app/services/notification_service.py` extends the 11A service with snapshot-on-read generation and the persisted inbox; schemas gain `notification_id` + `is_read` on `NotificationItem` and `unread_count` on `NotificationsResponse`; the endpoint adds `PATCH /api/v1/notifications/{notification_id}` (read/dismiss). `GET /api/v1/notifications` keeps its response contract and now serves the persisted inbox.
4. **Read/unread behavior (per the audit 11B contract).** New rows are unread; `PATCH` transitions `is_read` / `is_dismissed` (at least one field required; empty body → 422). Repeating a transition is an idempotent no-op. Dismissed notifications leave the inbox and stay dismissed across regeneration (persisted flag, not a physical delete — a regenerated occurrence cannot resurrect a dismissed row). `unread_count` = unread + non-dismissed rows (the future bell badge).
5. **Security.** Identity is JWT → `get_current_user()` → `user.id` everywhere; a client-supplied `user_id` in query/body is ignored; cross-user or nonexistent PATCH → 404; unauthenticated GET/PATCH → 401. No admin notification management added.
6. **Scope discipline.** No push / email / SMS / scheduling / Celery / Redis / cron / browser notification / service worker / PWA / channels / delivery providers were introduced — 11C (delivery model) remains decision-gated and deferred. No frozen system was touched; no frontend file changed.

## Migration / Schema Summary

- New head: **`d1e2f3a4b5c6`** (`down_revision = c1d2e3f4a5b6`), applied; `alembic heads == current == d1e2f3a4b5c6` (single head).
- New object: table `public.notifications` + type `notificationkind` (6 values = the Phase 11A `NotificationKind`).
- Additive only — no historical migration modified; no data reset.

## Verification

- `python -m compileall -q app scripts` — PASS.
- `python scripts/verify_phase_11b.py` — **23/23 PASS** (migration/head; table+enum; snapshot persistence; repeated-GET dedup; stable identity; distinct occurrences distinct; all six kinds persist + refresh in place; refresh preserves date/created_at/read/dismissed; PATCH read → unread_count−1; idempotent repeat PATCH; dismissal hides + survives regeneration; cross-user isolation; cross-user/nonexistent PATCH 404; `?user_id=` spoof ignored; 401 unauth; 422 empty body; attendance kinds == canonical summaries; 11A semantics unchanged; quiz == canonical cycle; events == dashboard selection; frozen snapshot byte-identical; alembic head unchanged; exact cleanup incl. admin inbox restored to pre-run baseline).
- `python scripts/verify_phase_11a.py` (regression) — **19/19 PASS** (checks 13/14/18/19 re-scoped to prove the notifications table exists as the 11B surface and that the verifier restores it to its pre-run state; 11A projection semantics untouched).
- DB baseline restored: 31 users; notifications 0; snapshot byte-identical across the runs. No browser tests run.

## Database State After 11B

- `notifications` table exists (0 rows at rest). Frozen systems byte-identical. Migration head `d1e2f3a4b5c6` current.

## What's Next

- **11D — Frontend notification center UX** — bell icon with unread badge in `TopNav`/`UserMenu`, notification center (Base UI Popover/Panel) listing items with read/dismiss actions, honest empty state, `useNotifications()` + `useNotificationMutation()` following `usePreferences` conventions, types in `types/api.ts`; no client-side attendance math, no fake push; verification via `tsc --noEmit`, targeted ESLint, `npm run build`.
- Remaining Phase 11: 11C delivery model (decision-gated: in-app only vs scheduled sweep), 11E remaining preference wiring, 11F phase completion (consolidated verifier + governance reconciliation + COMPLETE & FROZEN).
- Open product decisions: delivery model, multi-day reminder horizon, quiz horizon, `auto_mark_present` semantics (recommendation: remains storage-only).
- **HARD STOP after 11B** — no commit made; 11C NOT STARTED; 11D NOT STARTED; browser/manual testing remains the user's responsibility.

---

# AttendanceDash Pro — Phase 11D Walkthrough (Notification Center UX)

> **PHASE 11D COMPLETE (2026-08-20).** Frontend notification center consuming the live 11A/11B backend contract. Report: `docs/phase_11/phase_11d_implementation_report.md`. 11C remains decision-gated/deferred; 11E/11F NOT STARTED. No commit made.

## What Phase 11D Delivered

1. **Notification bell (authenticated shell).** A bell button in the `TopNav` right cluster (next to the user menu) showing the backend `unread_count` as a badge — hidden when zero, capped at "99+" to avoid absurd rendering. Opening the bell revalidates the inbox once (no polling, no aggressive refresh). The shell's existing modal state machine (`ShellModalId` + `activeModal`) drives it; `TopNav`, `UserMenu`, `ShellDialog` and `AppShell` were reused, not rebuilt.
2. **Notification center (shell dialog).** "Notifications" `ShellDialog` with the unread count in the description. States: loading (skeleton rows), API error (explicit banner + Retry), honest empty state ("No notifications yet"), and the populated inbox — backend ordering (newest first). Each row renders the kind badge/icon (six `NotificationKind` values), the readable message, subject context and the occurrence date (`formatLongDate`), with unread rows visually emphasized (dot + emphasis + "Read" action).
3. **Read / dismiss actions.** Unread rows expose "Mark as read"; every row exposes dismiss. Both PATCH the row via the existing 11B endpoint. The SWR cache is updated only from the genuine PATCH response — success is never faked; a failed mutation surfaces the actual backend error in an inline banner and leaves the list unchanged (state stays consistent). Dismissed rows leave the inbox; the backend keeps them dismissed across regeneration. Repeating an action is harmless (backend idempotency).
4. **SWR / API integration.** `useNotifications(enabled)` fetches `GET /api/v1/notifications` with the key gated on `enabled` (the bell always; the center on open) — never fetched when unauthenticated. `useNotificationMutation()` wraps `PATCH /api/v1/notifications/{id}`. The bell and the center share the same SWR key, so they dedupe into one logical request and read/dismiss updates keep the badge in sync with no extra round-trips. `STANDARD_CACHE` (focus revalidation, 1-minute dedup) — no polling loops, no N+1 item requests.
5. **Types.** `types/api.ts` mirrors the backend contract exactly: `NotificationKind`, `NotificationItem` (natural-key `id`, kind, date, subject context, message, source references, `notification_id`, `is_read`), `NotificationsResponse` (`items`, `as_of`, `unread_count`), `NotificationUpdate`.
6. **Scope discipline.** The client never sends `user_id` (ownership is JWT-derived server-side); no client-side notification logic; no push/email/SMS/scheduling/cron/worker/PWA behavior — 11C remains decision-gated and deferred. No backend file changed; no migration.

## Files Changed

- `frontend/src/types/api.ts` — additive notification contract types.
- `frontend/src/hooks/useApi.ts` — `useNotifications()` + `useNotificationMutation()`.
- `frontend/src/components/notifications/NotificationCenter.tsx` — new; the dialog surface.
- `frontend/src/components/notifications/NotificationBell.tsx` — new; bell + unread badge.
- `frontend/src/components/layout/TopNav.tsx`, `frontend/src/components/layout/UserMenu.tsx` — bell mount + `notifications` modal id.

## Verification

- `npx tsc --noEmit` — PASS.
- `npx eslint` (changed files only) — PASS.
- `npm run build` — PASS (all routes prerendered).
- Backend contract untouched (11B `GET`/`PATCH` semantics preserved); no browser/manual tests run (user's responsibility).

## What's Next

- **PHASE 11E VERIFIED (2026-08-20).** Discovery-first audit of the remaining preference wiring concluded **no additional implementation required**: `class_reminders` is the only consumer (the 11A gate, read at generation time; verified by 11A checks 7/8 and 11B check 18); `auto_mark_present` / `week_starts_on` confirmed storage-only per audit §5B/§5C (11A checks 11/12, 11B check 18). The audit-named 11E file change was delivered: SettingsModal copy + `types/api.ts` contract comment made truthful ("Class reminders are shown in the bell icon when enabled"). No backend change, no migration, no new verifier. Gates: `compileall` PASS · `verify_phase_11a.py` **19/19 PASS** · `verify_phase_11b.py` **21/23** — checks 19/20 fail on **diagnosed environmental data drift, not a code regression**: the admin's pre-existing inbox rows (created 17:58 today) persist per the documented 11B "rows stay until dismissed" semantics, and the verifier's own temp QUIZ_DAY fixture on the admin's own subject shifts the admin's canonical quiz cycle to 2 and reorders the top-4 event selection mid-run; checks 19/20 assume a clean admin inbox (a clean inbox passes 23/23; no code modified to force a pass). DB baseline restored (users 31 · admins 1 · notifications 10); alembic single head `d1e2f3a4b5c6` unchanged. Frontend `tsc`/ESLint/`npm run build` PASS. No commit made.
- **PHASE 11F COMPLETE (2026-08-21).** Final verification & freeze. The 11E drift (11B checks 19/20) and a fresh 11A check-16 failure were confirmed as **verifier determinism issues on a used admin inbox, not production defects**: the admin's inbox rows accumulate per the documented 11B "rows stay until dismissed" semantics, and the verifiers' fixtures shift the admin's canonical quiz/event/attendance state mid-run. Hardening applied **verifier-only** — `verify_phase_11a.py` checks 15/16/17 and `verify_phase_11b.py` checks 17/19/20 now assert in the **accumulation-compatible** direction (coverage: live canonical state ⊆ persisted inbox; run-generated rows match conditions at generation time; uniqueness; bounded growth ≤1 quiz / ≤4 events) and compare against a string-form baseline (`admin_baseline_str` — a UUID-vs-string bug in the first hardening attempt was fixed). **Zero production code changed.** Final gates on the used environment: `compileall` PASS · `verify_phase_11a.py` **19/19** (×2) · `verify_phase_11b.py` **23/23** · frontend `tsc --noEmit` PASS · ESLint (Phase 11 files) PASS · `npm run build` PASS. DB baseline restored (users 31 · admins 1 · notifications 11 · events 49); alembic single head `d1e2f3a4b5c6` unchanged. Report: `docs/phase_11/phase_11f_verification_report.md`.
- **What's Next:** Phase 12 — Mobile / Responsive Experience. Phase 11 is **COMPLETE & FROZEN** within its delivered scope.
- **11C** delivery model remains decision-gated (in-app only vs scheduled sweep), deferred, and **NOT implemented** — it may be omitted from Phase 11 entirely.
- **HARD STOP after 11F** — no commit made; Phase 11 COMPLETE & FROZEN (11A ✅ · 11B ✅ · 11D ✅ · 11E ✅ · 11F ✅); 11C NOT implemented; browser/manual testing remains the user's responsibility.
- **PHASE 12.0 AUDIT + 12A COMPLETE (2026-08-21).** Read-only architecture & implementation-readiness audit for Phase 12 (`docs/phase_12/phase_12_architecture_audit.md`) concluded **READY FOR ONLY A PHASE 12 SUB-PHASE (12A)** and **NO BACKEND CHANGE REQUIRED**: mobile navigation is ABSENT (TopNav nav `hidden md:flex`), all touch targets are below 40px, ShellDialog dialogs cannot scroll on short screens, and the Laboratory tab bar (~380px nowrap) is clipped by the shell — the top overflow risks. S4 prior art (`17_AI_HANDOFF.md:41-43`) fixes the contract at exactly 4 bottom tabs (Dashboard/Subjects/History/Profile) with Academic Tools reachable from Profile — never a 5th tab. The audit also corrected a governance inconsistency (Phase 12 was mislabeled "PWA & Offline"; it is "Mobile / Responsive Experience", PWA is Phase 13). 12A then delivered the **responsive foundation**: NEW `MobileBottomNav.tsx` (`md:hidden` fixed bottom nav, exactly 4 tabs + More bottom sheet via the existing `ui/sheet.tsx` exposing Profile + Track/Laboratory/Quiz Eligibility/Calendar/Events, all rows ≥40px); AppShell bottom clearance `p-4 pb-28 md:p-6 lg:p-8` (desktop padding byte-identical); touch-target foundation in `ui/button.tsx` (mobile base sizes with `sm:` desktop restores — NOT a global h-10/h-11 replacement; auto-upgrades dialog/sheet close buttons, calendar arrows, NotificationCenter actions); ShellDialog `max-h-[90dvh] overflow-y-auto` (EventFormDialog pattern) fixing all 6 shell modals; NotificationCenter list `max-h-[50dvh] md:max-h-[26rem]`; NotificationBell ~40px mobile hit area. Intentionally NOT touched: TopNav/UserMenu/dialog.tsx/sheet.tsx/app layout.tsx (documented rationale), all page components (12B-12F scope), and everything backend/DB/migration/API/PWA. Gates: `tsc --noEmit` PASS; ESLint (6 changed files) PASS; `npm run build` PASS (15 routes); `git diff --check` PASS; diff scope = 5 modified frontend files + 1 new component + `docs/phase_12/` only — zero backend changes, no migrations, no artifacts. Browser/manual testing NOT performed (user's responsibility; 320px/360-412px/768px+ checklist in `docs/phase_12/phase_12a_implementation_report.md`). Governance updated (MASTER_ROADMAP, implementation_plan, task.md, walkthrough — label fix included). **HARD STOP after 12A — no commit made; Phase 12: 12.0 + 12A COMPLETE; 12B (Track/Dashboard/Calendar) NEXT; desktop behavior unchanged; frozen systems untouched.**
- **PHASE 12B COMPLETE (2026-08-21).** Track / Dashboard / Calendar responsive experience. Evidence-first: measured every nav row and grid at 320px (content 288px / card-inner 256px). Found and fixed a **real Calendar overflow** — the month-nav row (40px arrows + fixed `w-36` label + Today) ≈310px > 288px content, previously clipped by the shell: row is now `flex flex-wrap` with label `min-w-0 w-28 sm:w-36` (≈276px single row at 320, wraps gracefully if fonts render wider). Calendar grid cells enlarged 31→35px at 320 via grid card `p-2 sm:p-4` and grids `gap-1 sm:gap-1.5` (month-calendar interaction model preserved — no date-picker substitution; DayDetail/legend/error/empty states verified already responsive and unchanged). Track: date-nav center column `flex-1 min-w-0` so the input stretches between 40px arrows; input `h-10 w-full sm:h-8 sm:w-40` and Today `sm:h-8` (mobile 40px via the 12A foundation; desktop 32px byte-identical); TrackSessionCard left column `min-w-0 flex-1` + wrapping badges (MID-SEM PRACTICAL no longer collides with the time at 320), actions row auto-height (fixed `h-9` was clipping the 12A h-10 buttons), and Change buttons dropped their explicit `h-7` override (mobile 40px; desktop stays `sm:h-7` — the 12A-report page-level residual, now resolved). Dashboard: three minimal fixes (Today badge row `flex-wrap`, Overall delta row `flex-wrap`, Weekly rows `gap-2 sm:gap-3`); all other cards verified fine at 320 and unchanged. Desktop preservation: every change is `sm:`-gated or overflow-inert (flex-wrap), so ≥768px is byte-identical. NOT changed: backend/DB/migrations/API/engines, all 12A files, PageHeader/Badge/Card/GlassCard/lib/date/hooks/types, css/responsive.css (unimported legacy), no new breakpoints. Gates: `tsc --noEmit` PASS; ESLint (7 changed files) PASS; `npm run build` PASS (15 routes); `git diff --check` PASS; diff = 7 frontend files (+35/−23) — zero backend/12A/artifact changes. Browser/manual testing NOT performed (owner's responsibility; 320px / 360–412px / 768px+ checklist in `docs/phase_12/phase_12b_implementation_report.md` §10). Governance updated (MASTER_ROADMAP, implementation_plan, task.md, walkthrough). **HARD STOP after 12B — no commit made; Phase 12: 12.0 + 12A + 12B COMPLETE; 12C (Laboratory/Subjects/Quiz/Events) NEXT; desktop behavior unchanged; frozen systems untouched.**
- **BUGFIX COMPLETE (2026-08-22) — CLASS_CANCELLED Not Propagating to Track.** Chronological execution: **(1) Discovered** — owner reported an active CLASS_CANCELLED event (BCS-058 Lecture, 2026-07-30, 10:00–11:00) while Track still showed the class as a normal Absent+Change attendance card. **(2) Reproduced from the live DB** — session `19bdc85a…` (LECTURE, `is_cancelled=false`, timetable entry `02ee420a…` Thu 10:00–11:00) holds MISSED record `faa0ce5e…`; event `9e5a7f98…` is CLASS_CANCELLED/active/exact match created AFTER the record; a sibling active case exists on 07-29 (`ce76c27f…` / `ea065985…`). Explicitly running `EventSessionSynchronizer.sync_event` on the live event left the session uncancelled — defect mechanically isolated. **(3) Pipeline investigated end-to-end** — events API → EventService (sync runs in-transaction on create/update/deactivate ✓) → synchronizer → class_sessions → Track daily read → frontend card → counting consumers; every `is_cancelled` consumer audited. **(4) Root cause** — `_reconcile_date`'s blanket guard skipped ANY session holding an attendance record, making explicit cancellations silent no-ops for historical classes (the common real-world case); cancellation provably worked only for unattended sessions. **(5) Fix** — synchronizer-first: `_desired_schedule` now emits `cancellation_removed` (entries explicitly removed by an active CLASS_CANCELLED only — LAB_CANCELLED/closures deliberately excluded per frozen Phase 9.1 check 18 and Phase 6.6 checks 5/31); `_reconcile_date` cancels unattended sessions as before AND explicitly-targeted recorded ones, restoration always allowed (full reversal), weekend-artifact/quiz-day protections intact. Consumer alignment through one canonical predicate `occurrence_is_cancelled()` (`practical_occurrence.py`) applied to subject counts (`collapse_count_rows`), History filters+summary (`attendance_repo.py`), and dashboard `_aggregate_range` — cancelled theory occurrences never count as attended/missed/pending anywhere; practical record-wins rule preserved; NO attendance record deleted anywhere. **(6) Regression testing** — NEW `verify_event_cancellation_propagation.py` **26/26** (propagation over stale marks, Track Cancelled data, mutation 409, summary/history exclusion + filters, enrollment isolation both directions, idempotent double-sync, no duplicates, PATCH-move reconciliation of two recorded sessions, exact deactivation reversal, closure + LAB_CANCELLED frozen-boundary probes via rollback transactions, owner-record fingerprints, exact count baseline). Existing verifiers re-run: compileall PASS · 6_6 **36/36** · attendance-spec **15/15** · events_correction **42/42** · working_saturday **24/24** · 6_5 **27/27** · quiz_day_materialization **14/14** · 11A **19/19** · 11B **23/23** · phase_3 **26/26** · phase_1 **18/18** · 7_1 **26/26** · 7_2 **25/26**, phase_2 **14/15** — the two asterisked plus history_filters (7/20), phase_9_1 (21/28), track_lab_fix (hardcoded "future" fixtures aged into the past + pre-existing FK-order cleanup crash), 8_1 (18/22), 8_2 (StopIteration) were each proven **pre-existing drift** by git-stash A/B runs against the ORIGINAL code (identical failures). **(7) DB restored** — full pre-work snapshot; final state: all 18 table counts byte-equal to baseline, alembic single head `d1e2f3a4b5c6` unchanged, zero temp users/events/sessions/records (crashed-run leaks cleaned strictly by captured IDs: TRK_TMP_LAB user ×2, 9 leaked MID_SEM/LAB_CANCELLED events, 1 extra session). **(8) Live case healed via the canonical path** — the two active BCS-058 cancellation events re-synced: both sessions now `is_cancelled=true`, records preserved and excluded from math (owner API probe: Track shows Cancelled for BCS-058 on 07-29 and 07-30). Note: HEAD moved mid-session (owner committed their own 12B work as `ede3da2` from a parallel terminal) — no work lost. **(9) Manual testing handed off** (checklist in `docs/bugfix/event_cancellation_propagation_report.md`). Report: `docs/bugfix/event_cancellation_propagation_report.md`. Frontend unchanged. No commit made.
- **PHASE 12C BUGFIX COMPLETE (2026-08-22) — cancellation state lifecycle + attendance counting consistency.** Chronology: **(1) Observed** — owner removed the BCS-058 CLASS_CANCELLED events (15:49 UTC) yet Track/History kept both lectures Cancelled; lecture counts had also included cancelled occurrences. **(2) Forensics** — DB showed events inactive while sessions stayed `is_cancelled=true` (updated_at frozen at the earlier heal); server fingerprinting proved the running backend (started 09:07 UTC, uvicorn WITHOUT --reload) still executed pre-fix code — live :8080 returned BCS-058 lecture {79,6,13} where current code returns {77,5,12} on identical data. **(3) Genuine code gap found & fixed:** `EventService.deactivate_event` early-returned for already-inactive events, so NO application path could ever re-reconcile their dates ("event removed ⇒ nothing to do"). Now deactivation ALWAYS reconciles; because reconciliation is state-based over the complete active event set, removal/reactivation/moves converge idempotently in BOTH directions without any ownership column or migration. **(4) Counting completed:** parallel-session changes extended the canonical predicate `occurrence_is_cancelled` to dashboard Today/Overall/Weekly rows, weekly %, analytics overall/weekly and the notification gate — every consumer now shares ONE applicability rule; no per-service cancellation math anywhere. **(5) Regression:** NEW `verify_cancellation_lifecycle_consistency.py` **35/35** — unmarked/MISSED/ATTENDED lifecycles, range-event multi-cancel, deactivation incl. ALREADY-INACTIVE re-deletion self-heal (the core regression), reactivation cycle, PATCH-move between two RECORDED sessions both directions, repeated-sync idempotency, records byte-preserved (fingerprints), Track/History/Subjects/Dashboard deltas both directions (77→76→75→77 measured), eligibility-consumed counting core unit checks, enrollment isolation 403s, unrelated-session isolation, exact baseline restore. Existing gates green: propagation **26/26**, phase_6_6 **36/36**, attendance_spec **15/15**, events_correction **42/42**, working_saturday **24/24**, phase_11a **19/19**, compileall PASS. Parallel-draft `verify_bugfix_12C*.py` use absolute live-data fixtures (17→19 drift between consecutive runs) — documented as non-gates. **(6) Live repair via application path:** canonical DELETEs on the already-inactive events reconciled cleanly (200×2); BCS-058 originals restored (07-29 Attended / 07-30 Missed); applicable lectures back to N=79; History summary consistent; records byte-preserved throughout. An incidental earlier proof: a routine date-scoped reconciliation sweep at 16:54 UTC had already self-healed both rows through the normal restore branch. **(7) Integrity:** alembic head `d1e2f3a4b5c6` unchanged; zero temp artifacts after cleaning FK-crash leaks by captured IDs; remaining count deltas (+2 EXTRA_LECTURE events, +1 materialized extra session, +1 MISSED mark on it) are the OWNER'S own concurrent app activity. **(8) Governance synchronized.** ⚠ Owner action: restart the dev backend before manual testing (running process predates all fixes). Report: `docs/bugfix/cancellation_state_and_counting_consistency_report.md`. Phase 12C COMPLETE (responsiveness `31f75ca` + this bugfix); **Phase 12D NOT STARTED**; no commit made.
