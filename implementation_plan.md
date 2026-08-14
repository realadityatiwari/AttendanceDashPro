# AttendanceDash Pro — Implementation Plan

Tracked phases and implementation status for the Next.js rewrite of AttendanceDash Pro.

---

## PHASE 2 — DESKTOP SHELL & GLOBAL UX

Status: **IMPLEMENTED** (see individual BLOCKED markers below)

### Completed

- **Desktop top navigation** — full-width compact (`h-14`) dark bar with thin bottom border, replacing the legacy sidebar. Brand on the left, primary navigation, authenticated user area on the right. (frontend `src/components/layout/TopNav.tsx`, `AppShell.tsx`)
- **Active route state** — the current route is rendered with a compact dark highlighted surface (`bg-secondary`), `aria-current="page"`.
- **Authenticated user area** — avatar with initials + display name, driven by `useProfile()`/`useAuth()` with real authenticated data. No hardcoded identity.
- **Profile dropdown** — Base UI Menu: opens reliably, closes on outside click, Escape, and after selection; keyboard accessible; contains Profile, Appearance, Install App, Send Feedback, Settings, Sign Out. (frontend `src/components/layout/UserMenu.tsx`)
- **Profile modal** — avatar/initials, name, roll number, program, semester, academic session, semester start, first quiz date. All values resolved from the real user profile and academic configuration; no screenshot values hardcoded. (frontend `src/components/shell/ProfileModal.tsx`)
- **Appearance modal** — Dark (current, selected), Light and System in an explicit disabled "Coming soon" state. No fake theme switching, no fake persistence. (frontend `src/components/shell/AppearanceModal.tsx`)
- **Feedback modal** — type (Bug/Suggestion/Question/Praise) + message; validation, loading, success, error, duplicate-submission prevention. Wired to the documented contract `POST /api/v1/feedback`. (frontend `src/components/shell/FeedbackModal.tsx`)
- **Settings modal** — Notifications / Attendance / Calendar sections rendered with disabled controls and an honest persistence notice. (frontend `src/components/shell/SettingsModal.tsx`)
- **Install App behavior** — app-wide `beforeinstallprompt` capture + `display-mode: standalone` detection; triggers the browser prompt when available, explains installation otherwise, never fakes an installed state. (frontend `src/components/shell/InstallAppModal.tsx`, `src/hooks/useInstallPrompt.ts`)
- **Sign Out integration** — uses the existing auth mechanism (`AuthContext.logout()`: removes the JWT, clears user state, redirects to `/login`). No replacement of the auth architecture.
- **Shared dialog behavior** — `ShellDialog` foundation: backdrop, focus management, Escape, body scroll lock, responsive width, accessible dialog semantics, consistent header, close button, consistent spacing, restrained animation. All global modals share it. (frontend `src/components/shell/ShellDialog.tsx`)
- **Route mapping** — visual labels mapped to existing routes without inventing URLs: Home → `/dashboard`, Track → `/tools/laboratory`, Quiz Eligibility → `/tools/quiz-schedule`, Attendance → `/subjects`, History → `/history`, Events → `/tools/events`.

### BLOCKED / BACKEND REQUIRED

- **Profile → Program** — the backend model has no program/branch column (only section names like "CSE-51" exist). The modal shows "—" and documents the gap. Requires a `program` column on `sections` (or equivalent) + seed data.
- **Feedback persistence** — no feedback table/endpoint exists in the backend. The frontend submits to `POST /api/v1/feedback` and surfaces an explicit "service unavailable" error — it never fakes success. Backend work for a later phase:
  - New table `feedback` (id, user_id FK → users, feedback_type enum BUG/SUGGESTION/QUESTION/PRAISE, message text, created_at).
  - Alembic migration, model, repository, Pydantic schema, `POST /api/v1/feedback` endpoint (JWT auth), registration in `backend/app/api/api.py`.
- **Settings persistence** — no user-preferences table/endpoint exists anywhere. Controls are disabled with an explicit notice; no fake local-only persistence. Backend work for a later phase:
  - New table `user_preferences` (user_id PK/FK, class_reminders bool, auto_mark_present bool, week_starts_on enum SUNDAY/MONDAY, updated_at).
  - Alembic migration, model, repository, `GET/PUT /api/v1/settings` (or `/student/preferences`) endpoints, registration in `backend/app/api/api.py`.
- **Appearance (Light/System)** — Phase 1 design tokens are locked to the dark palette (`globals.css` forces dark `:root` values; root layout hard-codes `dark`). Light/System are disabled until the Phase 1 tokens support a light palette; theme preference persistence requires `user_preferences`.
- **Install App** — no PWA infrastructure in this build (no web app manifest, no service worker, no `next-pwa`). The modal explains installation and is only usable if a future PWA phase provides the manifest + SW. "Installed" state is only ever reported from a real `userChoice` outcome or real `display-mode: standalone`.
- **Class reminders / Auto-mark present** — features do not exist in the product architecture (no notifications, no auto-marking). Disabled in Settings.
- **Mobile navigation** — nav links hidden below `md`; the mobile navigation pattern is a dedicated later phase (bottom nav per S4 spec).

### Backend change made (explicitly justified API integration)

`GET /api/v1/student/me` now returns read-only academic context (`program`, `semester_name`, `academic_session`, `semester_start`, `first_quiz_date`) resolved from existing tables (`sections → semesters → academic_sessions`, `quiz_schedules` via enrollments). Additive optional fields, no schema/DB changes, no business-logic changes. (`backend/app/schemas/student.py`, `backend/app/repositories/user_repo.py`, `backend/app/api/v1/endpoints/student.py`)

### Files changed (Phase 2)

| File | Change |
|---|---|
| `frontend/src/components/layout/AppShell.tsx` | Sidebar+header shell replaced with TopNav + centered content (`max-w-5xl`) |
| `frontend/src/components/layout/TopNav.tsx` | New: brand, primary nav, modal orchestration |
| `frontend/src/components/layout/UserMenu.tsx` | New: authenticated user dropdown |
| `frontend/src/components/layout/Header.tsx`, `Sidebar.tsx` | Deleted (replaced by TopNav/UserMenu) |
| `frontend/src/components/shell/ShellDialog.tsx` | New: shared modal foundation + ShellField |
| `frontend/src/components/shell/ProfileModal.tsx` | New |
| `frontend/src/components/shell/AppearanceModal.tsx` | New |
| `frontend/src/components/shell/SettingsModal.tsx` | New |
| `frontend/src/components/shell/FeedbackModal.tsx` | New |
| `frontend/src/components/shell/InstallAppModal.tsx` | New |
| `frontend/src/hooks/useInstallPrompt.ts` | New |
| `frontend/src/types/api.ts` | `StudentProfile` extended (optional academic fields) |
| `backend/app/schemas/student.py` | `StudentProfile` extended (optional academic fields) |
| `backend/app/repositories/user_repo.py` | `get_academic_context()` added |
| `backend/app/api/v1/endpoints/student.py` | `/me` enriches profile with academic context |
| `implementation_plan.md` | This file |
| `task.md` | Phase 2 status |
| `walkthrough.md` | Phase 2 walkthrough |

### Verification

- `npx tsc --noEmit` — **PASS** (0 errors)
- Backend files compile (`py_compile`) — **PASS**
- No attendance/quiz/lab engines, migrations, auth architecture, or Phase 1 tokens modified.

---

## PHASE 3 — HOME DASHBOARD

Status: **IMPLEMENTED** (see individual BLOCKED markers below)

### Completed

- **Read-only dashboard aggregation endpoint** — `GET /api/v1/dashboard/summary` composes the full Home read model in one call: today's sessions with per-session status, overall semester attendance with status classification, current-week strip (Mon–Fri) with week-over-week delta, quiz snapshot (next upcoming quiz cycle, threshold, eligible/attention/not-eligible counts), attention-required subjects, and upcoming academic events. (backend `app/api/v1/endpoints/dashboard.py`, `app/services/dashboard_service.py`, `app/schemas/dashboard.py`)
- **Reuses existing logic — no engine/schema changes** — the service calls the existing `AttendanceService.get_summary` (which uses the frozen `compute_subject_stats`), `EligibilityService.get_quiz_eligibility` (frozen `determine_quiz_threshold`), `CalendarService`/`CalendarRepository`, and `QuizRepository`. Only one additive read-only repository method was needed: `AttendanceRepository.get_sessions_with_status` (date-range session + subject + record join). No business rules duplicated, no mutations.
- **Status classification (reconciled)** — SAFE ≥ 80, WATCH ≥ 60, CRITICAL < 60, based on **current** pct (not forecast), per S4.1 reconciliation and the legacy `pctColor`/`getSubjectStatus` banding in `docs/11_UI_ARCHITECTURE.md` (target 75: +5 and −15 bands).
- **Home page rebuilt** — two-column bento (left: Today's Attendance + This Week; right: Overall Attendance + Quiz Snapshot + Attention Required + Upcoming Events) inside the AppShell `max-w-5xl`, with greeting header (`Good Morning/Afternoon/Evening, {first name}` + `Thursday · 13 Aug 2026`), per-section loading skeletons, a full-page error state, and empty states for every section (no events today, no quiz scheduled, nothing needs attention, no upcoming events). (frontend `src/app/(authenticated)/dashboard/page.tsx`, `src/components/dashboard/home/*`)
- **Real navigation actions** — Open Tracker → `/tools/laboratory`; View Quiz Eligibility → `/tools/quiz-schedule`; View All Events → `/tools/events`; View Strategy (per attention item) → `/tools/laboratory`.
- **Date handling** — browser-local dates on the client (`src/lib/date.ts`), server-local `date.today()` on the backend (same convention as existing endpoints).

### BLOCKED / BACKEND REQUIRED

- **Dedicated strategy view** — "View Strategy" routes to `/tools/laboratory` because no per-subject strategy route exists yet; a dedicated strategy page is Track-phase work.
- **Upcoming Events** — the `academic_events` table currently has zero rows, so the section renders its empty state. It will populate automatically once real events are seeded; no code change required.
- **Quiz snapshot when no quiz scheduled** — if no future SCHEDULED quiz exists for the user's subjects, the snapshot renders an empty state (`has_snapshot: false`).

### Verification

- Backend `py_compile` — **PASS**; live `GET /api/v1/dashboard/summary` (minted JWT, real user `2401220100027`) — **PASS** (today 6 classes all PENDING, overall 69.2% WATCH, weekly +21.5 pts vs last week, Quiz1 snapshot cycle 1 ≥70% with 6/6 eligible, 4 attention items, events empty).
- `npx tsc --noEmit` — **PASS** (0 errors)
- No attendance/quiz/lab engines, migrations, auth architecture, frozen UI primitives (Card/Badge/Progress/Button/Skeleton), TopNav/UserMenu/AppShell, or Phase 1 tokens modified.

### Files changed (Phase 3)

| File | Change |
|---|---|
| `backend/app/repositories/attendance_repo.py` | Additive `get_sessions_with_status()` (read-only date-range join) |
| `backend/app/schemas/dashboard.py` | New dashboard read model |
| `backend/app/services/dashboard_service.py` | New aggregation service (reuses existing services/engines) |
| `backend/app/api/v1/endpoints/dashboard.py` | New `GET /summary` endpoint |
| `backend/app/api/api.py` | Dashboard router registered under `/api/v1/dashboard` |
| `frontend/src/types/api.ts` | Dashboard types added |
| `frontend/src/hooks/useApi.ts` | `useDashboardSummary()` added |
| `frontend/src/lib/date.ts` | New local-date/format/greeting utilities |
| `frontend/src/components/dashboard/home/*` | New: GreetingHeader, TodayAttendanceCard, OverallAttendanceCard, WeeklyAttendanceCard, QuizSnapshotCard, AttentionRequiredCard, UpcomingEventsCard (+ skeletons) |
| `frontend/src/app/(authenticated)/dashboard/page.tsx` | Rebuilt around the summary endpoint |
| `implementation_plan.md` | This file |
| `task.md` | Phase 3 status |
| `walkthrough.md` | Phase 3 walkthrough |

---

## DO NOT TOUCH AGAIN

- Phase 0 audit
- Phase 1 design tokens
- Card
- Badge
- Progress
- backend architecture
- database architecture
- attendance engine
- quiz engine
- authentication architecture
- Firebase migration boundary
## PHASE 4.5.2 - HISTORICAL TRACK COMPLETION

Backend (minimal, additive):

- `backend/app/schemas/student.py` - `StudentProfile.semester_end` added
- `backend/app/repositories/user_repo.py` - `get_academic_context` resolves and returns `semester_end`
- `backend/app/repositories/attendance_repo.py` - `get_daily_sessions` joined to `StudentEnrollment` so reads are scoped to the authenticated student's enrolled subjects
- `backend/app/services/attendance_service.py` - `record_attendance` rejects cancelled sessions (409) before enrollment check

Frontend:

- `frontend/src/types/api.ts` - `AttendanceStatus` values corrected to `Attended`/`Missed`/`Pending`; `ClassType.PRACTICAL = "P"` (was `"P1"` - backend never returns P1/P2); `StudentProfile.semester_end` added
- `frontend/src/app/(authenticated)/tools/laboratory/page.tsx` (Track page) - navigation clamped to semester bounds from `/student/me` (no hardcoded dates), native date picker with min/max, inline mutation error banner, semester-start indicator
- `frontend/src/components/dashboard/TrackSessionCard.tsx` - no change needed; corrected enums restored its status rendering (Present/Absent/Change vs Pending Present/Absent)

Not changed:

- `backend/app/engines/*` - attendance/eligibility/dashboard/forecast/safe-skip engines untouched (Step 9)
- `backend/app/models/*`, migrations, `attendance_records` schema - no schema change required (Step 6/11)
- No new endpoints - Track reuses `GET /api/v1/attendance/daily/{date}` and `POST /api/v1/attendance` (Step 5)
- No database data created/modified/deleted (Step 11); `laboratory_experiments`/`laboratory_records` untouched

## PHASE 4.5.3 - REAL SIGN UP + ACCOUNT CREATION

Backend:

- `backend/alembic/versions/c3d4e5f6a7b8_make_firebase_uid_nullable.py` - NEW migration: `users.firebase_uid` nullable; legacy values preserved; unique index retained (PostgreSQL allows multiple NULLs); column not dropped (Phase 14 owns removal)
- `backend/app/models/user.py` - `firebase_uid` mapped nullable
- `backend/app/core/security.py` - `hash_password` added, producing the exact `pbkdf2_sha256\\` format `verify_password` consumes (single verifier for register + login)
- `backend/app/api/v1/endpoints/auth.py` - `POST /auth/register`: validation -> academic context resolution -> transactional User + StudentEnrollment creation -> IntegrityError rollback (409) -> JWT via `create_access_token`
- `backend/app/schemas/student.py` - `firebase_uid` optional

Frontend:

- `frontend/src/app/(auth)/signup/page.tsx` - NEW: full signup form, show/hide password, client UX validation (13-digit roll, min 8 password, match confirm), friendly server-error mapping, success -> store token -> `refreshUser()` -> `/dashboard`
- `frontend/src/app/(auth)/login/page.tsx` - link to `/signup`
- `frontend/src/contexts/AuthContext.tsx` - `/signup` added to public routes; authenticated users redirected to dashboard from both auth pages
- `frontend/src/types/api.ts` - `firebase_uid: string | null`

Enrollment provisioning rule (documented decision):

- Resolve `academic_sessions WHERE is_active` (must exist, else 503)
- Resolve that session's semesters (must be exactly 1, else 409 ambiguity)
- Resolve the semester's sections (exactly 1 -> auto-assign; 0 -> 503; >1 -> 409 until a section-selection product decision exists)
- Enroll in ALL subjects of that semester (matches the `setup_single_user.py` convention); client submits no academic IDs; duplicates impossible for a fresh user

Not changed:

- `backend/app/engines/*`, attendance/quiz/dashboard/calendar engines, Track behavior, laboratory subsystem
- Login endpoint, token mechanism, protected-route enforcement
- Aditya's account/data (verified by query); no database reset; no automatic test-user creation in code (one manual disposable verification account created and reported)

## PHASE 5 - ATTENDANCE HISTORY

Backend (one endpoint, extended in place - no second data system):

- `backend/app/schemas/attendance.py` - `AttendanceHistoryItem` redefined session-based (session id, date, start/end time, subject code/name, class type, status, is_cancelled, is_extra, marked_at nullable); `HistorySummary` added (total/attended/missed/pending/cancelled/pct); `AttendanceHistoryResponse` extended (semester_start/end, effective range_start/end, items, total_count, summary)
- `backend/app/repositories/attendance_repo.py` - `get_history` rewritten: session-based query (ClassSession + Subject + StudentEnrollment scope + TimetableEntry times + outer AttendanceRecord), shared `_history_conditions` helper, `get_history_summary` aggregate (FILTER clauses) over the full filtered set; count query mirrors the page joins (fixes a cross-join when status filters reference AttendanceRecord)
- `backend/app/services/attendance_service.py` - `get_history(user, ...)` resolves semester bounds via the same academic-context repository used by `/student/me`; clamps to [semester_start, min(date_to, semester_end, today)]; builds items + full-set summary
- `backend/app/api/v1/endpoints/attendance.py` - `GET /attendance/history` gains query params: `subject_code`, `status` (regex-validated `Attended|Missed|Pending|Cancelled`), `date_from`/`date_to` (YYYY-MM-DD), `search` (subject code/name, class type label, date string); existing `limit`/`offset` contract preserved

Filtering semantics:

- Pending = no attendance row for that user (excludes cancelled); Cancelled = `is_cancelled` session state (never counted absent, mirrors Track)
- Search = case-insensitive match on subject code, subject name, class-type label (LECTURE/TUTORIAL/PRACTICAL), and ISO date
- Subject filter operates on the student's enrollments (bogus/unenrolled codes return 0)

Frontend:

- `frontend/src/types/api.ts` - history types updated to the new contract + `AttendanceHistoryParams`/`HistoryStatusFilter`
- `frontend/src/hooks/useApi.ts` - `useAttendanceHistory(params)` builds the SWR key from all filter params
- `frontend/src/app/(authenticated)/history/page.tsx` - rebuilt: header with semester/date context (from the real academic contract), server-side summary strip (5 counters + pct, labelled "filtered" when filters active), filter card (enrolled-subject select from `/api/v1/subjects`, state select, date-from/to bounded by semester, debounced search, reset), high-density rows (date chip, subject code + name, LECTURE/TUTORIAL/PRACTICAL + EXTRA badges, time, Present/Absent/Pending/Cancelled semantic badges), "Load more" pagination with id-deduplication and filter reset, distinct loading/error/empty states (no classes in semester vs no filter matches)

Not changed:

- `backend/app/engines/*`, attendance/eligibility/dashboard/calendar engines, Track behavior/mutation, auth architecture, signup, migrations, database schema
- No new attendance source: History and Track both read the canonical `class_sessions` + `attendance_records` pipeline; the summary is an aggregate of the same records (no analytics engine introduced)
- No attendance rows created/modified/deleted; Aditya's data untouched; no new indexes (existing PK/FK indexes suffice at this scale)

---

## PHASE 6.1 — FOUNDATIONAL CALENDAR CORRECTIONS

Status: **COMPLETE** (2026-08-14). Scope: the four defects PROVEN in `docs/phase_6_0_calendar_events_audit.md`. No calendar UI, no event CRUD, no admin system, no seeding, no event→session integration.

### Files changed

| File | Change |
|---|---|
| `backend/app/engines/calendar_engine.py` | New canonical `DEFAULT_WEEKENDS = [0, 6]` constant (JS getDay indices: Sun=0, Sat=6) used as the `get_academic_day` default; `MID_SEMESTER_BREAK` added to the closure list |
| `backend/app/services/calendar_service.py` | `get_day_schedule` passes shared `DEFAULT_WEEKENDS` (removed local `[5, 6]`) |
| `backend/app/services/eligibility_service.py` | Same shared constant for window/eligibility calls (eligibility math untouched) |
| `backend/app/repositories/calendar_repo.py` | `get_all_events(active=None, date_from=None, date_to=None, upcoming=False)` optional server-side filters; repo default stays no-filter for internal callers |
| `backend/app/api/v1/endpoints/events.py` | `GET /api/v1/events` query params: `active` (default true), `date_from`, `date_to` (inclusive range-overlap), `upcoming` (default false); 422 on `date_from > date_to` |
| `backend/app/repositories/attendance_repo.py` | `get_sessions_with_status` joins `StudentEnrollment` (dashboard aggregation now enrollment-scoped, mirroring `get_daily_sessions`/`get_history`) |
| `backend/scripts/expand_baseline.py` | Uses the shared `DEFAULT_WEEKENDS` constant (was inline `[0, 6]`) |

### Final /events contract

- Default **active only**; `active=false` for inactive only.
- `date_from`/`date_to` inclusive range-overlap on `[start_date, end_date]`; `upcoming=true` → `end_date >= today` (combine with `active` for current/upcoming active events); `date_from > date_to` → 422.
- Internal consumers (dashboard `_build_upcoming_events`, eligibility) use the repo directly with no filters — unchanged. Only HTTP consumer (Events page) now receives active events by default.

### Verification

- `compileall backend/app backend/scripts` — PASS; `npx tsc --noEmit` — PASS.
- In-process engine/service checks — 17/17 PASS (weekends, constant usage, MID_SEMESTER_BREAK closure, inactive ignored, date ranges, quiz-window bounds unchanged with corrected teaching dates).
- Read-only DB checks in rolled-back transactions — /events filter cases (8) and enrollment scoping (temp unenrolled subject excluded; 2026-07-15 control = 6 sessions for both users) PASS.
- No browser testing performed (per Phase 6.1 instruction).

### Not changed / deferred

- Attendance/eligibility engines, Track/History/Dashboard calculations, auth, migrations, schema. Deferred: calendar UI, event CRUD, admin roles, validation registry, seeding, event→session integration, substitution, quiz/event integration, scoping, timetable schema, TodayClassesCard cleanup, type-hint refactor, window-field restoration.

---

## PHASE 6.2 — CALENDAR READ MODEL & API

Status: **COMPLETE** (2026-08-14). Backend-only month-bounded calendar read model for the future Phase 6.3 calendar UI. Read-only; no UI/CRUD/admin/seeding/event→session integration.

### Endpoint

- `GET /api/v1/calendar?year=YYYY&month=M` (JWT): `year` Query `ge=2000 le=2100`, `month` Query `ge=1 le=12` — FastAPI validation (422 on malformed/out-of-range). Existing `/calendar/today` and `/calendar/{date}` unchanged.

### Files changed

| File | Change |
|---|---|
| `backend/app/schemas/calendar.py` | `CalendarDayItem(AcademicDayResponse)` + `non_working_reason` + `session_count`; `CalendarMonthResponse` (year, month, semester_start/end, effective_start/end, days) |
| `backend/app/services/calendar_service.py` | `get_month_view(user, year, month)` — semester clamp, engine delegation, one-scoped-query session counts; service now composes `UserRepository` + `AttendanceRepository` |
| `backend/app/api/v1/endpoints/calendar.py` | `GET ""` with `year`/`month` Query validation |

### Read model

- Semester bounds from `UserRepository.get_academic_context` (same as /student/me, Track, History); `effective_start = max(month_start, semester_start)`, `effective_end = min(month_end, semester_end)`; month outside semester → `days: []` (inverted effective range); no context → `days: []` with null bounds.
- Day resolution entirely via `calendar_engine.get_academic_day` + `DEFAULT_WEEKENDS` (no second algorithm); `non_working_reason` = dominant active event title, else "Weekend", None when working.
- Events via `get_all_events(active=True, date_from, date_to)` (Phase 6.1 semantics); empty table → correct calendar with empty `events` arrays.
- `session_count` from one enrollment-scoped `get_sessions_with_status` query grouped by date (no N+1; no attendance mathematics).

### Verification

- `compileall backend/app` — PASS; `npx tsc --noEmit` — PASS.
- Service tests (live DB, read-only) 24/24 PASS (bounds, clamps, weekends, reasons, MID_SEMESTER_BREAK closure, inactive ignored, cross-month exclusion, session counts vs independent SQL, rollback).
- API contract tests (in-process httpx ASGITransport on real `api_router`) 21/21 PASS (7 validation 422s, Aug 200 + exact structure, Jan 2027 empty, existing endpoints intact).
- No persisted DB mutations (read-only SQL: 0 events, 9 subjects, 684 sessions, 84 records, 18 enrollments, 30 users). No browser testing.

### Not changed / deferred

- Engines, Track/History/Dashboard math, auth, migrations, schema unchanged. Deferred: calendar UI (6.3), events page upgrade (6.4), persistence/admin/seeding (6.5), event→engine integration (6.6), verification/freeze (6.7), plus the standing 6.1 deferrals.

---

## PHASE 6.3 — CALENDAR UI

Status: **COMPLETE** (2026-08-14). Production `/calendar` route rendering the frozen Phase 6.2 read model. Frontend-only; no backend changes; no event CRUD; no admin; no seeding; no event→session integration.

### Route

- `frontend/src/app/(authenticated)/calendar/page.tsx` — authenticated route under the existing AppShell route group (no new shell, no duplicated auth).

### API integration

- `useCalendarMonth(year, month)` in `frontend/src/hooks/useApi.ts` — SWR hook with a stable per-month cache key (`/api/v1/calendar?year=&month=`), standard cache semantics, `mutate` exposed for retry. One logical request per month; no per-day requests.
- Types `CalendarMonthResponse` / `CalendarDayItem` (extends the existing `AcademicDayResponse`) added to `frontend/src/types/api.ts`.

### Calendar grid architecture

- `frontend/src/components/calendar/CalendarGrid.tsx` — presentation-only monthly grid. Backend `CalendarDayItem`s are placed on the real local calendar month (Sunday-first alignment matching the backend `getDay()` convention); cells outside the API's effective range are empty layout placeholders, never academic days. Grid renders only `is_working_day`, `non_working_reason`, `events`, `session_count` — zero calendar semantics computed client-side.
- `frontend/src/components/calendar/DayDetail.tsx` — selected-day detail card: full date, working/non-working badge, `non_working_reason`, `is_teaching_day`, `substitution_schedule_override`, session count, and the day's `events[]` (type, holiday badge, class-type badge, date range). Links to the existing read-only Events page.

### Month navigation

- Previous/Next month + Today, all month-based and timezone-safe (local `Date` arithmetic with explicit year/month state; `January ↔ December` rollover handled). Navigation beyond the backend-provided `semester_start`/`semester_end` is disabled when bounds are known; no hardcoded dates. Today → current local month; months outside the semester truthfully render the empty state using backend bounds.
- During a month switch the last successfully loaded month stays visible (dimmed, `Loading …` hint) until the new read model arrives — the page never blanks.

### Selected-day behavior

- Fresh month → select today when the backend returned it, else the first effective day, else nothing. Manual selection is never overridden while the month is unchanged (selection is tracked per month key so stale grids cannot leak selections forward).

### Loading / error / empty states

- First load → skeleton grid + skeleton detail card. Month switch → retained grid with loading hint. API failure → calendar-specific error card with a working retry action (`mutate`). `days.length === 0` → truthful "No academic days in this period" empty state (never treated as an API failure, never faked).

### Accessibility

- Day cells are native buttons (`Button` primitive, not divs) with descriptive `aria-label` and `aria-pressed`; focus-visible rings from the design system. No Base UI button-as-link composition, so no `nativeButton={false}` needed. No new date helpers — existing `lib/date.ts` utilities reused (`getLocalDateString`, `parseLocalDate`, `formatLongDate`).

### Navigation

- `Calendar` added to `TopNav` as a single primary item (`CalendarRange`, `/calendar`, between History and Events). Nothing replaced or redesigned; `/tools/events` untouched (belongs to Phase 6.4).

### Files changed

| File | Change |
|---|---|
| `frontend/src/app/(authenticated)/calendar/page.tsx` | New authenticated `/calendar` route: nav controls, month state, selection logic, loading/error/empty states |
| `frontend/src/components/calendar/CalendarGrid.tsx` | New presentation-only monthly grid |
| `frontend/src/components/calendar/DayDetail.tsx` | New selected-day detail card |
| `frontend/src/hooks/useApi.ts` | `useCalendarMonth(year, month)` SWR hook |
| `frontend/src/types/api.ts` | `CalendarMonthResponse`, `CalendarDayItem` types |
| `frontend/src/components/layout/TopNav.tsx` | Minimal `Calendar` nav item |

### Verification

- `npx tsc --noEmit` — PASS (0 errors). No backend files touched (`git diff` backend: none). No migrations/schema changes; no attendance/eligibility engine changes; no event CRUD; no fake events seeded. Browser testing deferred to the user.

### Not changed / deferred

- Backend (Phase 6.2 contract frozen), Track, History, auth, migrations, schema, attendance/eligibility engines, `/tools/events` page. Deferred: events page upgrade (6.4), persistence/admin/seeding (6.5), event→engine integration (6.6), verification/freeze (6.7).
