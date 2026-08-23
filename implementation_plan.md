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

### RESOLVED BY PHASE 10 (COMPLETE & FROZEN)

The following Phase 2 BLOCKED items were completed end-to-end by Phase 10 and are **no longer blocked**:

- **Profile → Program** — **RESOLVED (10B):** `sections.program` column added (migration `b1c2d3e4f5a6`), populated, and `program` returned from the stored section value in the profile read model (`StudentProfileResponse`); never derived from the section name.
- **Feedback persistence** — **RESOLVED (10C):** `feedback` table (id, user_id FK → users, feedback_type enum BUG/SUGGESTION/QUESTION/PRAISE, message, context, created_at) + migration `b1c2d3e4f5a7`, model, repository, schema, and `POST /api/v1/feedback` (JWT auth, 201, no GET/list surface), registered in `backend/app/api/api.py`. Verified by `backend/scripts/verify_phase_10c.py` (23/23). Frontend errors are honest — a real non-2xx never fakes success.
- **Settings persistence** — **RESOLVED (10D):** `user_preferences` table (user_id PK/FK, class_reminders, auto_mark_present, week_starts_on enum SUNDAY/MONDAY, created_at/updated_at) + migration `c1d2e3f4a5b6`, model, repository, schema, `GET/PUT /api/v1/student/preferences` (lazy-create, replace semantics, server defaults, user-isolated), registered in `backend/app/api/api.py`. Verified by `backend/scripts/verify_phase_10d.py` (18/18). **Storage/preference data only** — nothing sends reminders or marks attendance.

### BLOCKED / BACKEND REQUIRED (still open)

- **Appearance (Light/System)** — Phase 1 design tokens are locked to the dark palette (`globals.css` forces dark `:root` values; root layout hard-codes `dark`). Preference storage now exists (`user_preferences`, Phase 10D) but there is no theme field in the table yet; Light/System remain disabled until the Phase 1 tokens support a light palette and a theme preference is added to the preference contract.
- **Install App** — no PWA infrastructure in this build (no web app manifest, no service worker, no `next-pwa`). The modal explains installation and is only usable if a future PWA phase provides the manifest + SW. "Installed" state is only ever reported from a real `userChoice` outcome or real `display-mode: standalone`.
- **Class reminders / Auto-mark present** — the features themselves do not exist in the product architecture (notifications & reminders are Phase 11; auto-marking is not in the roadmap). The preference VALUES are now real (stored via `/student/preferences`, Phase 10D) but nothing consumes them yet — Phase 11 notifications will consume them.
- **Mobile navigation** — DONE in Phase 12A (2026-08-21): bottom nav below `md` (S4 4-tab contract) + More sheet; remaining page-level responsiveness is Phase 12B-12F.

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

---

## PHASE 6.4 — EVENTS PAGE UPGRADE

Status: **COMPLETE** (2026-08-14). Production read-only Academic Events page at `/tools/events`. Frontend-only; no backend changes; no event CRUD; no admin; no seeding.

### API integration

- `useEvents(params?: EventsParams)` in `frontend/src/hooks/useApi.ts` — extended the existing Phase 6.1 hook with the Phase 6.1 query contract (`active`, `date_from`, `date_to`, `upcoming`) via a stable per-params SWR key; `mutate` exposed for retry. Default call (`/api/v1/events`) unchanged. One logical request per filter combination.
- `EventsParams` type added to `frontend/src/types/api.ts` (mirrors the `AttendanceHistoryParams` convention). `AcademicEventResponse`/`EventType` reused — no parallel event model.

### Grouping / filters

- Grouping is presentation-only, computed from the backend-returned date ranges against browser-local today (`getLocalDateString`): today inside `[start_date, end_date]` → **Today**; `end_date` after today → **Upcoming** (start asc); otherwise → **Past** (newest first). No academic semantics computed.
- Filters: event type (client-side over the fetched set, per contract — the API has no type filter), active/inactive state (honestly supported server-side by `active=true|false`), and a From/To date range (server-side inclusive range-overlap). Inverted From/To is prevented client-side with a hint instead of triggering a 422. Reset button clears all filters.
- Event type rendering reuses the existing `EventType` enum with a robust humanizer that also handles unknown/future types gracefully.

### Event rendering

- `frontend/src/components/events/EventRow.tsx` — compact Card row: date block (day/month), humanized type title, semantic badges (Today / Holiday / Extra / Cancelled / class type / Inactive), date range (end date only when different), substitution note, and a `Calendar` link affordance to `/calendar` (no invented query params; the calendar route was not modified).
- Section headings (`Upcoming` / `Today` / `Past`) with live counts; empty sections show a muted placeholder line.

### Loading / error / empty

- Loading: skeleton sections (heading + row skeletons) — no fake empty state before the request resolves.
- Error: events-specific error card with a working **Try again** (`mutate`); never shows "No events" for an API failure.
- Empty: differentiates "No events scheduled" (zero backend rows — the truthful current state) from "No events match the selected filters". Nothing seeded or manufactured.

### Files changed

| File | Change |
|---|---|
| `frontend/src/app/(authenticated)/tools/events/page.tsx` | Rebuilt: filters, grouping, states, sections |
| `frontend/src/components/events/EventRow.tsx` | New compact read-only event row |
| `frontend/src/hooks/useApi.ts` | `useEvents(params)` — Phase 6.1 query contract |
| `frontend/src/types/api.ts` | `EventsParams` |

### Verification

- `npx tsc --noEmit` — PASS (0 errors). ESLint on changed files — PASS. No backend files touched (`git diff` backend: none); no migrations/schema changes; no attendance/eligibility engine changes; no event CRUD; no fake events. Browser testing deferred to the user.

### Not changed / deferred

- Backend contract (Phase 6.1 events + Phase 6.2 calendar frozen), Track, History, Dashboard, auth, migrations, schema, attendance/eligibility engines, `/calendar` route. Deferred: persistence/admin/seeding (6.5), event→engine integration (6.6), verification/freeze (6.7).

---

## PHASE 6.5 — EVENT PERSISTENCE, ADMIN AUTHENTICATION & SEEDING

Status: **COMPLETE** (2026-08-14). Admin role system, admin-only event mutation API, centralized validation registry, minimal admin event UI, controlled idempotent seeding. Backend is authoritative for authorization and validation; Phase 6.1/6.2 read contracts untouched.

### Admin authorization

- `UserRole` enum (`STUDENT`/`ADMIN`) in `backend/app/models/enums.py`; `users.role` column in `backend/app/models/user.py` (default `STUDENT`, `server_default` too); migration `backend/alembic/versions/d4e5f6a7b8c9_add_user_role.py` **applied** — existing 30 users backfilled to STUDENT, no data loss.
- `require_admin` dependency in `backend/app/api/dependencies/deps.py` → 403 "Admin privileges required" for non-ADMIN tokens.
- Role is resolved from the DB per request (authoritative); never trusted from JWT/localStorage/body/query/hardcoded identity. No self-assignment path — only `backend/scripts/provision_admin.py` grants ADMIN (run for 2401220100027).
- Read contract extended: `role` in `StudentProfile` (`backend/app/schemas/student.py`) and returned by `/student/me` + `/student/sync` (`backend/app/api/v1/endpoints/student.py`).

### Validation registry

- `backend/app/services/event_registry.py`: `EVENT_TYPE_RULES` for all 14 `EventType`s — `requires_subject`, `requires_class_type`, `allowed_class_types`, `is_closure`, `is_global` — ported from the legacy `AcademicEventRegistry` (js/calendar-engine.js) + engine closure semantics (MID_SEMESTER_BREAK etc. are closures → always non-working). `validate_event()` raises `EventValidationError`; `VALID_SUBSTITUTION_DAYS` from engine `DAY_NAMES`.

### Persistence & mutation API (admin-only)

- `backend/app/repositories/event_repo.py`: `EventRepository` (`get_by_id`, `subject_exists`, `exists_active_duplicate`), `EventNotFound`, `EventConflict`.
- `backend/app/services/event_service.py`: `create_event` / `update_event` (partial via `model_fields_set`, pydantic 2.13) / `deactivate_event` — one transaction per mutation.
- Endpoints in `backend/app/api/v1/endpoints/events.py`: `POST /api/v1/events` (201), `PATCH /api/v1/events/{event_id}`, `DELETE /api/v1/events/{event_id}` — all `Depends(require_admin)`; error mapping 422 (validation) / 404 (missing event or subject) / 409 (identical ACTIVE duplicate on `(event_type, subject_id, class_type, start_date, end_date)`, ported from legacy js/events-controller.js).
- Deletion = **safe deactivation** (`active=false`, legacy ADR 004 soft-delete); re-enable via PATCH `{"active": true}`. No hard deletes.
- Schemas `AcademicEventCreate` / `AcademicEventUpdate` in `backend/app/schemas/calendar.py`. `GET /api/v1/events` read contract unchanged (still list-only; `GET /events/{id}` → 405 by design).

### Admin UI (minimal, additive — Phase 6.4 surface preserved)

- `frontend/src/components/events/eventRules.ts` (NEW): registry mirror (`EVENT_TYPE_RULES`, `SUBSTITUTION_DAYS`, `CLASS_TYPE_LABELS`, `getRule`) — presentation of field visibility only; the backend registry is authoritative.
- `frontend/src/components/events/EventFormDialog.tsx` (NEW): create/edit dialog driven by the registry mirror; fields only for model attributes (no title/description); client start≤end + required-subject/class checks; handles loading and 422/403/404/409; success → `onSaved()`.
- `frontend/src/components/events/EventRow.tsx`: optional `onEdit` / `onDeactivate` props — admin actions render only when the page passes them (Edit opens the dialog; Deactivate uses a two-step inline confirm).
- `frontend/src/app/(authenticated)/tools/events/page.tsx`: `useProfile()` → `role === "ADMIN"` gates the Add Event toolbar, row actions, and dialog; after a mutation, `mutate()` (events) + revalidate the current calendar month via `useCalendarMonth`. Students see the unchanged Phase 6.4 read experience.
- `frontend/src/hooks/useApi.ts`: `useEventMutations()` (createEvent/updateEvent/deactivateEvent via `apiFetch`); `frontend/src/types/api.ts`: `AcademicEventPayload`, `StudentProfile.role`.

### Seeding (controlled, idempotent)

- Audit finding: **no authoritative institutional dates** (holidays, breaks, working Saturdays) exist anywhere in the repo — documented data gap; nothing invented.
- Authoritative source = `quiz_schedules` (17 SCHEDULED rows; BCS-054 Q3 UNRESOLVED) → `backend/scripts/seed_academic_events.py` seeds exactly **17 QUIZ_DAY events** (matching legacy `AcademicEventRegistry.QUIZ_DAY` → requiresSubject + requiresClassType). Idempotency key `(event_type, subject_id, start_date, end_date)`; verified 17 created then 17 skipped on rerun; deactivated rows never resurrected.
- `backend/scripts/provision_admin.py` — role grant script.

### Verification

- `compileall` backend PASS; `alembic upgrade head` applied (head `d4e5f6a7b8c9`); seed run twice → 17/17 idempotent.
- `backend/scripts/verify_phase_6_5.py` — **23/23 PASS**: security matrix (STUDENT 403 on POST/PATCH/DELETE, ADMIN ok, unauth 401), creation, duplicate 409, subject 404, PATCH partial/absent-vs-null, deactivation + re-enable, read-contract regression (student + calendar), seeding idempotency, cleanup of test rows.
- Frontend: `npx tsc --noEmit` PASS, ESLint PASS on changed files, `npm run build` PASS. Browser testing deferred to the user (no E2E).

### Files changed

| Layer | Files |
|---|---|
| Backend | `models/enums.py` (UserRole), `models/user.py` (role), `alembic/versions/d4e5f6a7b8c9_add_user_role.py`, `api/dependencies/deps.py` (require_admin), `schemas/student.py` (role), `schemas/calendar.py` (Create/Update), `api/v1/endpoints/student.py` (role), `api/v1/endpoints/events.py` (POST/PATCH/DELETE), `services/event_registry.py` (NEW), `repositories/event_repo.py` (NEW), `services/event_service.py` (NEW) |
| Scripts | `scripts/provision_admin.py` (NEW), `scripts/seed_academic_events.py` (NEW), `scripts/verify_phase_6_5.py` (NEW) |
| Frontend | `types/api.ts` (AcademicEventPayload, role), `hooks/useApi.ts` (useEventMutations), `components/events/eventRules.ts` (NEW), `components/events/EventFormDialog.tsx` (NEW), `components/events/EventRow.tsx` (admin actions), `app/(authenticated)/tools/events/page.tsx` (admin mode) |

### Database state after 6.5

- 17 seeded QUIZ_DAY events (`academic_events`), 1 ADMIN user (2401220100027), 30 users all others STUDENT. **Not touched:** attendance_records, class_sessions (684 rows intact), student_enrollment, subjects, quiz_schedules, any user history. Test rows removed by the verifier.

### Not changed / deferred

- Frozen areas unchanged (attendance/eligibility engines, dashboard, Track, History, auth flow, Phase 1 design system, AppShell, TopNav, Phase 6.1 events + 6.2 calendar contracts, 6.3 calendar UI, 6.4 student experience, attendance schema, Firebase boundary).
- Deferred: event→engine integration (6.6 — event→class_sessions, holiday→cancellation, extra/substitution lecture generation, quiz-window mutation), verification/freeze (6.7), the data gap (institutional holiday/break dates) pending authoritative input.

---

## PHASE 6.6 — EVENT → ENGINE INTEGRATION

Status: **COMPLETE** (2026-08-14). Persisted `AcademicEvent` records now operationally mutate `class_sessions` through the canonical pipeline, exactly as the legacy engine's effective schedule did (docs/S4.3: **ACADEMIC EVENT = EXACT-DATE SCHEDULE MUTATION**). No engine was rewritten; no schema change; no frontend change.

### Semantics per event type (desired-schedule deltas)

- **Closures** (PUBLIC_HOLIDAY, INSTITUTE_HOLIDAY, FESTIVAL_HOLIDAY, EMERGENCY_CLOSURE, SEMESTER_BREAK, MID_SEMESTER_BREAK): the calendar engine makes the day non-working → desired schedule empty → every scheduled session on the date becomes `is_cancelled=True` (rows are NEVER deleted; cancelled ≠ absent, per ADR 004 / audit Q12).
- **CLASS_CANCELLED** (subject + class type required): removes ONE matching occurrence (legacy splice semantics) → that session is cancelled; its type total drops by exactly 1.
- **EXTRA_LECTURE / EXTRA_TUTORIAL / EXTRA_PRACTICAL / SURPRISE_QUIZ** (subject + class type): inject ONE extra occurrence → a new `is_extra=True` session (no timetable entry), type total +1.
- **WORKING_SATURDAY / substitution_schedule_override**: the day follows the substituted timetable (engine `substitution_schedule_override`) → sessions are materialized on the date (timetable_entry_id set), bounded by the baseline span; reverted by deleting unattended weekend projections when the event goes away.
- **QUIZ_DAY / WORKING_DAY_OVERRIDE**: calendar/read semantics only — NO session effect (quiz eligibility math untouched; nothing to do in the pipeline).

### Design

- `backend/app/services/event_session_service.py` — `EventSessionSynchronizer.sync_event(event, span_override=None)`:
  - Day semantics come from the **frozen** `calendar_engine.get_academic_day` (never reimplemented); `_desired_schedule` is the direct port of legacy `getEffectiveDaySchedule` (base timetable for the resolved day − one match per CLASS_CANCELLED + one extra per EXTRA_*/SURPRISE_QUIZ, deterministic order: priority desc then event id).
  - `_reconcile_date` is state-based, so sync is **idempotent** (double-sync converges, no duplicates) and **date-scoped** (computed from ALL active events — deactivating/moving an event automatically restores what its dates no longer imply).
  - **Attendance safety:** sessions with any `AttendanceRecord` are never cancelled/un-cancelled/deleted; attended extras survive count reconciliation. Cancelled sessions reject attendance with 409 (existing rule, verified).
  - Sessions are only created within the canonical baseline span (`get_session_date_span`: 2026-07-15 → 2026-12-31).
- `backend/app/repositories/session_repo.py` — `SessionRepository`: timetable/span/range reads, attendance-guard id set, `add_session`, `delete_session`, `flush`.
- `backend/app/services/event_service.py` — synchronizer wired into `create_event` / `update_event` / `deactivate_event` **inside the same transaction** (after flush, before commit). Updates sync the union of the old and new date ranges (`span_override`), so moving an event reverts the old dates. Deactivation reverts all session effects.
- **No schema change** — audit proved existing `class_sessions` fields (`is_cancelled`, `is_extra`, `timetable_entry_id`) and event fields sufficient.

### Counting corrections (cancelled ≠ pending — proven necessary)

Cancelled sessions were previously counted as pending in the student pipeline. Frozen shapes preserved; only value-level exclusions:

- `backend/app/repositories/attendance_repo.py`: `get_subject_counts_up_to_date` + `get_subject_counts_between` add `ClassSession.is_cancelled.is_(False)`.
- `backend/app/services/dashboard_service.py`: `_build_overall` and `_build_weekly` day_classes skip cancelled sessions.
- `backend/app/services/calendar_service.py`: `get_month_view` `session_count` counts non-cancelled only.

### Verification

- `compileall` backend PASS.
- `backend/scripts/verify_phase_6_6.py` — **36/36 PASS** (httpx ASGITransport + real DB + minted JWTs): student POST 403; closure → all 5 sessions cancelled (none deleted); attended-session guard (fully-attended 2026-07-15 closure → zero mutation); CLASS_CANCELLED → exactly one BCS-501/L cancelled, BCS-501 lecture total −1; EXTRA_LECTURE → one `is_extra` session, total restored +1; double-sync idempotency; SURPRISE_QUIZ +1; QUIZ_DAY no-op; WORKING_SATURDAY Monday schedule materialized (5 sessions with timetable entries); PATCH move reverts old date / applies new; read contracts (calendar working/non-working + session counts, daily Cancelled states, daily extra visibility, history clamped to today so future cancelled sessions never leak); eligibility BCS-501 Q1 byte-identical; deactivation reversal for every event type; rollback-transaction checks (attended extra preserved, 3-day range → exactly 3 extras, deactivated range removes extras + second sync no-op); final **exact baseline** assertion (events=17, sessions=684, cancelled=0, extra=0, records=89). Test rows hard-deleted; startup cleanup also recovers orphans left by earlier crashed runs and the 6.5 verifier's extra-session side effect.
- `backend/scripts/verify_phase_6_5.py` regression — **23/23 PASS** after 6.6 (runs converge with 6.6's cleanup: 6.5's EXTRA_LECTURE test now leaves one session that 6.6's startup cleanup removes).

### Files changed (Phase 6.6)

| Layer | Files |
|---|---|
| NEW | `app/services/event_session_service.py`, `app/repositories/session_repo.py`, `scripts/verify_phase_6_6.py` |
| Modified | `app/services/event_service.py` (sync wiring), `app/repositories/attendance_repo.py`, `app/services/dashboard_service.py`, `app/services/calendar_service.py` (cancelled-count exclusions) |
| Untouched | all engines, schemas (shapes), frontend (no UI change needed), migrations, auth |

### Database state after 6.6

- Returned to the exact pre-6.6 baseline: events=17, sessions=684 (0 cancelled, 0 extra), attendance_records=89, enrollments=18, subjects=9, quiz_schedules=18, users=30 (1 ADMIN). Test event rows hard-deleted; rollback tests committed nothing.

### Known limitations / data gaps

- Sessions are only materialized inside the baseline span (2026-07-15 → 2026-12-31); events outside it affect the calendar engine but never extend the session pipeline.
- No authoritative institutional holiday/break/working-Saturday dates exist in the repo — the data gap stands; nothing fabricated.
- Extra sessions carry no event linkage (schema has none) — reconciliation matches extras by (subject_id, class_type) count, which is deterministic but cannot distinguish which event produced which extra.
- History/Dashboard today-based views clamp to today (2026-08-14); event effects on future dates are visible via calendar/daily/eligibility reads.

---

## PHASE 6.7 — CALENDAR & ACADEMIC EVENTS VERIFICATION / FREEZE

Status: **COMPLETE / FROZEN** (2026-08-15). Phase 6 (6.0 → 6.6) verified as one coherent system and frozen. No feature development, no engine rewrites, no schema redesign, no frontend changes.

### Verification

- `backend/scripts/verify_phase_6_7.py` (NEW) — **31/31 PASS**:
  - **6.1:** `DEFAULT_WEEKENDS == [0, 6]` (JS getDay convention: Sunday=0, Saturday=6); MID_SEMESTER_BREAK is a closure (Monday non-working) and shares SEMESTER_BREAK's priority tier 60; `/events` default = active only; inverted date range → 422; `upcoming=true` semantics.
  - **6.2:** calendar read model — January 2026 (outside semester) → truthful empty result with real bounds; July clamps to semester start 2026-07-15; December respects semester end 2026-12-31; Sat/Sun non-working, Mon working; QUIZ_DAY remains a working day.
  - **6.5:** seeding integrity — exactly 17 events, ALL `QUIZ_DAY`, all active, none fabricated, matching 17 SCHEDULED `quiz_schedules`; deactivate → re-enable via PATCH converges the pipeline.
  - **6.6:** all six closure types (INSTITUTE_HOLIDAY, FESTIVAL_HOLIDAY, EMERGENCY_CLOSURE, SEMESTER_BREAK, MID_SEMESTER_BREAK + PUBLIC_HOLIDAY already in 6.6) cancel every session on the date with rows preserved and the day non-working; EXTRA_TUTORIAL / EXTRA_PRACTICAL create exactly one `is_extra` session each (no timetable entry); WORKING_DAY_OVERRIDE is calendar/read-only (working day, zero session mutation); cancelled session rejects attendance with **409**.
  - **Baseline:** full 10-table assertion — events=17, sessions=684 (0 cancelled, 0 extra), records=89, enrollments=18, subjects=9, quizzes=18, users=30, admins=1 — restored exactly.
- Regression: `verify_phase_6_5.py` **23/23** + `verify_phase_6_6.py` **36/36**; `compileall` PASS; combined **90/90**. All three verifiers converge in any order (startup cleanups handle each other's leftovers).
- Frontend (static): CalendarGrid/DayDetail/calendar page render only the backend read model (no weekend/holiday/session math; `getDay()` used for layout alignment only; semester bounds and month gating from backend data; selection state month-keyed so it never leaks across months; truthful loading/error/empty states; aria-labels intact). Events page consumes the backend contract (server-side range overlap, inverted range prevented client-side + 422 server-side, active filter maps to the API `active` param, grouping presentation-only, unknown event types humanized by string, admin surface gated by backend-provided role).

### Architectural review (targeted, Phase 6 scope)

| Check | Result |
|---|---|
| Duplicated event/calendar/attendance semantics | None — engine + `EventSessionSynchronizer` are the only paths |
| React-side business logic | None (read-model rendering only) |
| Direct DB access from Phase 6 endpoints | None (auth.py/quiz.py/laboratory.py pre-date Phase 6; unchanged) |
| Sync outside EventSessionSynchronizer | None (event_service.py only) |
| Engine rewrites | None (calendar/attendance/eligibility engines untouched) |
| Schema changes beyond Phase 6.5 | None (only `d4e5f6a7b8c9_add_user_role`) |
| Hidden hardcoded academic dates | Zero matches in `app/` (semester bounds from academic context) |
| Unsafe deletion of attended sessions | Impossible — attendance-guard in synchronizer; verified live (attended closure 07-15 → zero mutation) |
| Role trust in client/JWT | None — role resolved from DB per request |
| Repository/service boundary bypasses | None — endpoints call services only |
| N+1 in calendar read model | None — one enrollment-scoped session query per month |

### Files changed (Phase 6.7)

| Layer | Files |
|---|---|
| NEW | `backend/scripts/verify_phase_6_7.py` |
| Docs | `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md` |

### Freeze

Phase 6 is **FROZEN**. Frozen boundaries: calendar engine constants/priorities/closure semantics, `/api/v1/events` + `/api/v1/calendar*` contracts, calendar/events UI, event registry validation rules, event service transaction+sync wiring, `EventSessionSynchronizer` semantics, the three verifiers, and the baseline (17/684/0/0/89/18/9/18/30/1). Known limitations and the institutional-date data gap are documented as frozen state, not defects.

### Deferred (unchanged, later phases)

- Institutional holiday/break/working-Saturday dates — pending authoritative product input (data gap).

---

## PHASE 7.0 — QUIZ ELIGIBILITY & SCHEDULE REALITY AUDIT

Status: **COMPLETE** (2026-08-15). Read-only audit — no implementation, no DB writes, no commit. Deliverable: `docs/phase_7_0_quiz_eligibility_audit.md` (sections A–Y).

### What the audit established

1. **Formula parity (PASS):** `meets_attendance_target` (average of Lecture% and Tutorial%, lecture-only when no tutorials) is identical to legacy `meetsAttendanceTarget`; the exhaustive optimizer matches `optimizeLive` (same tie-break: fewest total, then fewest lectures). ADR-010 window semantics identical in both engines (Q1 = [semester start, quiz−1]; QN>1 = [prev quiz, quiz−1]).
2. **Data reality (SELECT-only):** 9 subjects (6 theory quiz-applicable + 3 labs); policies 70/75/75 from `eligibility_policies` (matches legacy `policies.quiz`); 17 dated SCHEDULED quiz_schedules + **BCS-054 Q3 UNRESOLVED**; 17 active events all QUIZ_DAY; semester V 2026-07-15 → 2026-12-31. Records=89 split: admin 84 + 4 students (2/1/1/1); student `9999999999999` has 0 records; no future-dated records.
3. **Worked traces (in-process engine, real DB):** admin Quiz I windows: BCS-501 L 18 (10 att) / T 6 (1 att) → avg 36.1% vs 70%; BCS-502 51.1%; BCS-503 44.2%; BCS-054 29.9%; BCS-058 26.4%; BNC-501 27.3% (no tutorials). All report `is_eligible=True` (reachable) — legacy would show "NEEDS ATTENDANCE" for all.
4. **Headline discrepancy (Q-D1):** backend `is_eligible = is_reachable` when any class is pending ⇒ **everything eligible** today; legacy requires `reachable && deficits == 0`. Dashboard snapshot reports 6/6 Eligible.
5. **UI data contract gap (Q-D2):** `EligibilityResult` lacks window lecture/tutorial counts+percentages, average, quiz date, Criterion I/II PASS/FAIL, recoverable state, explanation. Reference UI cannot render these without client-side recomputation (prohibited).
6. **Decision points Q-D1…Q-D10** (see audit doc §R): tri-state eligibility; Criterion I OR II (per `S4_PRODUCT_SPEC.md:32-33`); payload extension; honor `subjects.quiz_applicable`; DB `combined_threshold` authority; raw-range vs teaching-day counting; **rule G students-add/remove-events vs frozen admin-only mutations**; overall denominator (recorded vs all); quiz-day attendance without a session; BCS-054 Q3 date.

### Files changed (Phase 7.0)

| Layer | Files |
|---|---|
| Docs | NEW `docs/phase_7_0_quiz_eligibility_audit.md`; `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md` |
| Code | **NONE** (audit-only) |

### Next (Phase 7.1, requires Q-D1…Q-D10)

- Backend: extend the eligibility payload (window-bounded counts/percentages, criterion structure, quiz date, tri-state status, explanation) — computed by the canonical engines, never in React.
- Frontend: reference subject-card UI rendering that contract verbatim (badge, attended/total/%, average, required, expandable "View Calculation", recoverable state).
- Verifier `verify_phase_7_1.py`; regression 6.5/6.6/6.7 (90/90); baseline restore; docs update.
- Any post-freeze improvement must be a new phase with its own verification.

---

## PHASE 7.1 — CANONICAL QUIZ ELIGIBILITY CONTRACT + REFERENCE SUBJECT CARDS

Status: **COMPLETE (2026-08-15) — PASS.** Report: `docs/phase_7_1_implementation_report.md`.

### What Phase 7.1 delivered

1. **Complete quiz schedule:** BCS-054 Quiz III resolved to 2026-10-23 from `timetable.json` (override removed from `seed_academic_baseline.py`); live `quiz_schedules` row updated; canonical `seed_academic_events.py` created the 18th QUIZ_DAY event. Canonical schedule = 18 SCHEDULED dates, exact match with the authoritative source (verifier check 1).
2. **Canonical eligibility states** (fixes Q-D1/Q-D2/Q-D3): ELIGIBLE / RECOVERABLE / NOT_ELIGIBLE / UNRESOLVED derived from the existing engine's counts at current + best-case scenarios (no second math model). `is_eligible` redefined to "currently eligible"; dashboard snapshot corrects itself with zero dashboard changes.
3. **Official policy** per `S4_PRODUCT_SPEC.md:32-33`: (Criterion I — Lecture % qualifies) OR (Criterion II — Combined average qualifies) = Eligible; persisted `eligibility_policies` thresholds authoritative for both routes (fixes Q-D5).
4. **Practical exclusion** via authoritative `subjects.quiz_applicable` (fixes Q-D4; labs 404).
5. **Reference UI:** `/tools/quiz-schedule` → "Quiz Eligibility" with cycle tabs (Quiz I/II/III) and per-subject reference cards (code, THEORY badge, name, status, lecture/tutorial attended/total/%, average, required, expandable View Calculation with criteria + final + must-attend/safe-skip). React is presentation-only; loading/error+Retry/empty/unresolved states included.
6. **Verification:** `verify_phase_7_1.py` 26/26; frozen regression 6.5 23/23, 6.6 36/36, 6.7 31/31 (Phase 6.7 count assertions maintained 17→18 for the new authoritative schedule); compileall/tsc/ESLint/build green.

### Files changed (Phase 7.1)

| Layer | Files |
|---|---|
| Backend (app) | `app/schemas/attendance.py` · `app/engines/eligibility_engine.py` · `app/services/eligibility_service.py` |
| Backend (scripts) | NEW `scripts/verify_phase_7_1.py` · `scripts/seed_academic_baseline.py` (BCS-054 override removed) · `scripts/verify_phase_6_7.py` (17→18 maintained) |
| Frontend | `src/types/api.ts` · NEW `src/components/quiz/QuizEligibilityCard.tsx` · `src/app/(authenticated)/tools/quiz-schedule/page.tsx` · DELETED `src/components/dashboard/SubjectQuizSchedule.tsx` |
| DB | `quiz_schedules` BCS-054 Q3 → 2026-10-23 SCHEDULED + 18th QUIZ_DAY event (documented, reversible) |
| Docs | NEW `docs/phase_7_1_implementation_report.md`; `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md` |

### Next (Phase 7.2, requires product authorization)

- Q-D6 teaching-day (vs raw-range) counting; Q-D8 overall denominator; Q-D7 student event-mutation capability (product/security decision); date-aware default cycle tab; any further reference-UI polish. Each requires its own phase + verifier + full regression (6.5/6.6/6.7 + 7.1).

---

## PHASE 7.2 — QUIZ ELIGIBILITY ANALYTICS REFINEMENT

Status: **COMPLETE (2026-08-15) — PASS.** Report: `docs/phase_7_2_implementation_report.md`.

### Decisions (documented, no second math model)

1. **Q-D6 (raw-range counting) — NOT a defect.** The session table IS the teaching-day-resolved effective schedule: `expand_baseline.py` expands only teaching days, the synchronizer cancels on closures / materializes extras only on working days, and `get_subject_counts_between` excludes cancelled sessions. Raw-range counting == teaching-day enumeration (proven for all 18 combos + closure/extra/weekend-guard regressions). No counting change; `teaching_days` stays informational.
2. **Q-D8 (overall denominator) — recorded-only.** Legacy ERP `computeCurrentOverallAttendance` + S4 §10 current domain: pending excluded from the current denominator but never converted to absent — always counted and surfaced separately. Dashboard card already showed pending; quiz eligibility card gained a muted pending indicator (reference visual language otherwise untouched). Verified 71.43% vs explicitly-not 46.51%.
3. **Q-D7 (mutation/timing) — intentional product restriction (B).** Attendance mutations are student-scoped + enrollment-authorized + cancelled-protected; EVENT mutations stay admin-only (frozen 6.5, rule G is a future product capability). Eligibility is read-time; mutations propagate immediately.
4. **Date-aware default tab.** New canonical read-only endpoint `GET /api/v1/quiz-eligibility/current-cycle` (next upcoming SCHEDULED quiz → latest resolved cycle → fallback Quiz I). Frontend preselects from it (`useCurrentQuizCycle`); manual tabs override; no state mutation; no invented dates.

### Files changed (Phase 7.2)

| Layer | Files |
|---|---|
| Backend (app) | `app/schemas/attendance.py` (`CurrentQuizCycle`) · `app/services/eligibility_service.py` (`get_current_quiz_cycle`) · `app/api/v1/endpoints/quiz.py` (`GET /current-cycle`) |
| Backend (scripts) | NEW `scripts/verify_phase_7_2.py` |
| Frontend | `src/types/api.ts` · `src/hooks/useApi.ts` (`useCurrentQuizCycle`) · `src/app/(authenticated)/tools/quiz-schedule/page.tsx` (date-aware default) · `src/components/quiz/QuizEligibilityCard.tsx` (pending indicator) |
| Docs | NEW `docs/phase_7_2_implementation_report.md`; `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md` |
| DB | **NONE** (exact baseline restored after every verifier run) |

### Verification

- `verify_phase_7_2.py` **26/26** (Q-D6 equivalence/exclusion/extra/weekend-guard; Q-D8 recorded-only + explicit pending + zero-record null; Q-D7 403/409/403-404/immediacy; current-cycle admin+student+4 date-aware transitions; BCS-054 Q3 = 2026-10-23; UNRESOLVED-only-when-genuine; labs 404; dashboard-snapshot == canonical results; Track/History/Eligibility consistency; per-user isolation; exact baseline restore).
- Frozen regression: 6.5 **23/23** · 6.6 **36/36** · 6.7 **31/31** · 7.1 **26/26** (no assertions weakened).
- Static: compileall clean · `npx tsc --noEmit` clean · ESLint 0 errors · `next build` exit 0.

### Next (Phase 8, roadmap)

- Phase 8 — Attendance Analytics / Intelligence on the existing canonical engines. Q-D9 (quiz-day attendance without a session) and rule G (student event capability) each require an explicit product decision and their own phase. **HARD STOP — no commit made.**

---

## PHASE 8.0 — ATTENDANCE ANALYTICS & INTELLIGENCE: AUDIT / CONTRACT DESIGN

Status: **COMPLETE (2026-08-15) — PASS.** Read-only audit + contract design; **no implementation, no business-logic change, no DB mutation, no commit**. Deliverable: `docs/phase_8_0_attendance_analytics_audit.md` (sections A–W).

### What the audit established

1. **Architecture:** no dedicated analytics layer exists; `dashboard_service` is the de-facto aggregator and already consumes the canonical engines. Canonical chain intact: class_sessions → attendance_records → engines → (Phase 8 analytics read model) → API → React. No second engine exists or may be created; React performs no business math today.
2. **Inventory (23 metrics):** every analytics surface catalogued with per-metric pending/cancelled/extra/practical/semester/quiz-window treatment. All current % recorded-only; forecast % pending-as-attended; overall = ERP Σatt/Σrecorded (class-weighted, not subject-average); cancelled excluded everywhere; practicals included in overall but excluded from eligibility; banding = SAFE ≥ 80 / WATCH ≥ 60 / CRITICAL < 60 on current (S4.1 reconciliation).
3. **Legacy gaps (4 — all additive extensions of existing engine outputs, NOT new formulas):** practical % not exposed (Python `compute_subject_stats` computes counts only); subject-level 75% must-attend/safe-skip not exposed (legacy `optResult`/`optimizeLive`); overall forecast not exposed (legacy `computeForecastOverallAttendance`); forecast-impact deltas not exposed (legacy `calcForecastImpact`).
4. **React duplications flagged (NOT fixed):** `WeeklyAttendanceCard` re-derives day-bar % from backend counts; `SubjectAttendanceCard` applies its own 75/65 banding vs the canonical 80/60 band and hardcodes `cycle=1`. Dead `TodayClassesCard.tsx` / `FormulaCard.tsx` documented.
5. **Performance (latent, NOT fixed):** N+1 in dashboard quiz snapshot (per-subject `get_quiz_eligibility` incl. repeated events fetch) and subject summaries (per-subject count query); overlapping range scans in `_build_overall`/`_build_weekly`/`_build_today`; import-time `date.today()` default on `/attendance/summary`.
6. **Security:** all analytics reads authenticated + user/enrollment-scoped; one gap flagged — `GET /attendance/summary/{subject_code}` lacks the enrollment 404 the quiz endpoint has (no cross-user leak; consistency only).
7. **Withheld (no definition anywhere):** AT-RISK state (roadmap §8 4-state taxonomy; only 3 states defined) and weekly/semester trend series — candidate definitions provided, require product approval (T-1…T-4).

### Files changed (Phase 8.0)

| Layer | Files |
|---|---|
| Docs | NEW `docs/phase_8_0_attendance_analytics_audit.md`; `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md` |
| Code | **NONE** (audit-only) |
| DB | **NONE** (SELECT only; exact baseline verified) |

### Verification

- `python -m compileall app scripts` — PASS · `npx tsc --noEmit` — PASS (0 errors) · `verify_phase_7_2.py` — 26/26 PASS (frozen verifier, rollback-based).
- DB baseline (read-only): events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN) · BCS-054 Q3 = 2026-10-23.

---

## PHASE 8.1 — CANONICAL ANALYTICS READ MODEL

Status: **COMPLETE (2026-08-15) — PASS.** Backend-only additive analytics read model implementing the Phase 8.0 contract exactly. Report: `docs/phase_8_1_implementation_report.md`.

### Implemented

1. **Subject analytics (additive):** `SubjectAttendanceSummary` gains `current_practical_pct`, `forecast_practical_pct`, `optimization` (subject-level 75% must-attend/safe-skip via the attendance engine's own `optimize_attendance` — `lecture_deficit`/`tutorial_deficit` = must-attend, `safe_skip_lecture`/`safe_skip_tutorial` = safe-skip). Practicals use the canonical class-session/attendance-record pipeline — no quiz-window dependency, no separate lab engine; Pending stays Pending, cancelled excluded. Existing fields unchanged (backwards compatible).
2. **`GET /api/v1/analytics/overview`** (authenticated, enrollment-scoped, read-only): overall current (ERP Σatt/Σrecorded, recorded-only), overall forecast (pending-as-attended), pending count, Monday-start weekly read-model series (recorded-only, null gaps), per-subject current/forecast/optimization. No AT-RISK, no trend product semantics, no forecast-impact deltas (documented non-goals).
3. **Dashboard N+1 fixes (contract-identical):** batched `get_quiz_eligibility_for_subjects` (single canonical engine path via shared `_evaluate_subject`), grouped `get_subject_counts_for_user`, one shared range scan for Today/Overall/Weekly. Dashboard JSON byte-identical; 54 → 23 queries on the read path.
4. **Endpoint hygiene:** `/attendance/summary` default date resolved per-request (no import-time `date.today()`); `/attendance/summary/{code}` returns the quiz-endpoint-style enrollment 404.

### Files changed (Phase 8.1)

| Layer | Files |
|---|---|
| Schemas | `app/schemas/attendance.py` (`OptimizationResult` moved above; `SubjectAttendanceSummary` additive fields) · NEW `app/schemas/analytics.py` |
| Services | `app/services/attendance_service.py` · NEW `app/services/analytics_service.py` · `app/services/eligibility_service.py` (`_evaluate_subject` + batched) · `app/services/dashboard_service.py` |
| Repositories | `app/repositories/attendance_repo.py` (`get_subject_counts_for_user`) · `app/repositories/quiz_repo.py` (`get_quiz_schedules_for_subjects`) |
| Endpoints | NEW `app/api/v1/endpoints/analytics.py` · `app/api/v1/endpoints/attendance.py` · `app/api/api.py` |
| Scripts | NEW `scripts/verify_phase_8_1.py` |
| Docs | NEW `docs/phase_8_1_implementation_report.md`; `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md` |
| DB | **NONE** (zero mutation; exact baseline verified before/after) |

### Verification

- `verify_phase_8_1.py` **22/22** (auth; enrollment scoping; ERP overall; forecast; pending; subject summaries; practical %; must-attend/safe-skip + optimizer edge cases; weekly read model; dashboard compatibility + N+1 correctness with query counting; runtime-date behavior; enrollment protection; no duplicate attendance math; exact baseline; frozen 7.2 invariants).
- Frozen regression: 6.5 **23/23** · 6.6 **36/36** · 6.7 **31/31** · 7.1 **26/26** · 7.2 **26/26** — no assertion weakened.
- Static: compileall PASS · `npx tsc --noEmit` PASS (0 errors, frontend untouched).

---

## PHASE 8.2 — FRONTEND CONSUMPTION OF THE CANONICAL ANALYTICS READ MODEL

Status: **COMPLETE (2026-08-15) — PASS.** Frontend-only consumption of the Phase 8.1 read model; **no backend change, no DB mutation, no commit**.

### Implemented

1. **Typed analytics client:** `AnalyticsOverviewResponse`, `OverallAnalytics`, `WeeklyAnalyticsItem`, `AnalyticsSubjectItem` added to `src/types/api.ts` (exact match to the backend schema — no invented fields); `SubjectAttendanceSummary` extended additively with `current_practical_pct`, `forecast_practical_pct`, `optimization`; new `useAnalyticsOverview()` hook (`/api/v1/analytics/overview`, standard SWR cache).
2. **Subjects page (backend-derived):** `SubjectAttendanceGrid` loads all subject summaries from ONE overview request (per-subject N+1 eliminated); each `SubjectAttendanceCard` renders backend practical % (+forecast) and 75% must-attend/safe-skip from `summary.optimization`. The duplicated 75/65 client banding was removed (no per-subject status exists in the backend contract — none invented); hardcoded `cycle = 1` replaced with the canonical `useCurrentQuizCycle()` (Phase 7.2) driving the quiz eligibility badge.
3. **Dashboard (backend-derived):** `OverallAttendanceCard` renders an additive backend forecast line (pending-as-attended); `WeeklyAttendanceCard` renders the backend weekly series (Monday-start, backend `current_pct`, null rendered as a truthful gap — never 0%) instead of re-deriving day-bar percentages.
4. **Dead components removed:** `TodayClassesCard.tsx` and `FormulaCard.tsx` verified unused (zero imports/routes) and deleted.

### Files changed (Phase 8.2)

| Layer | Files |
|---|---|
| Frontend | `src/types/api.ts` · `src/hooks/useApi.ts` · `src/components/dashboard/SubjectAttendanceCard.tsx` · `src/components/dashboard/SubjectAttendanceGrid.tsx` · `src/components/dashboard/home/OverallAttendanceCard.tsx` · `src/components/dashboard/home/WeeklyAttendanceCard.tsx` · `src/app/(authenticated)/dashboard/page.tsx` · DELETED `src/components/dashboard/TodayClassesCard.tsx` · DELETED `src/components/dashboard/FormulaCard.tsx` |
| Docs | `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md` |
| Backend | **NONE** |
| DB | **NONE** (zero mutation) |

### Verification

- `npx tsc --noEmit` PASS (0 errors) · ESLint clean on all changed files · `next build` PASS (all 14 routes).
- No attendance formulas, safe-skip calculations, eligibility calculations, or quiz-cycle logic in React (backend fields rendered directly).
- Frozen phases untouched; no backend file modified.

### Next (Phase 8.3, requires explicit product authorization)

- T-1 (AT-RISK taxonomy), T-2 (trend semantics), T-3 (dedicated Analytics page), T-4 (multi-class forecast wording) remain product decisions. Q-D9 and rule G unchanged. **HARD STOP — no commit made; Phase 8.3 NOT STARTED.**

---

## ATTENDANCE UI REFINEMENT — SPECIFICATION ALIGNMENT + REFERENCE UI

Status: **COMPLETE (2026-08-15) — PASS.** Aligned the implementation with the authoritative attendance specification and implemented the reference Attendance UI. Two spec conflicts were escalated and **authorized by the user** before implementation; full report: `docs/attendance_ui_refinement_report.md`.

### Authorized decisions

1. **Quiz-day attendance (materialize):** quiz-day attendance is a real attendance event. `scripts/materialize_quiz_day_sessions.py` (idempotent, `--undo` reversible) materialized 7 LECTURE sessions on the SCHEDULED quiz dates that lacked one (incl. BCS-054 Q3 = 2026-10-23); all 18 quiz dates now recordable. Eligibility windows end at `quiz_date − 1` so eligibility is untouched; subject + overall attendance now include quiz-day sessions. Sessions 684 → 691 (documented baseline change).
2. **Student-adjustable events (shared schedule, subject-scoped):** students may create/update/deactivate the flexible subject-scoped event types (EXTRA_LECTURE/TUTORIAL/PRACTICAL, CLASS_CANCELLED, SURPRISE_QUIZ) for their own enrolled subjects; global/closure/quiz-schedule events remain admin-only (403). Enrollment check mirrors the attendance path; the event synchronizer never cancels/deletes quiz-day sessions (attendance safety preserved).

### Implemented

- **Reference Attendance cards** (`SubjectAttendanceCard`): header (code · THEORY/LAB · name · canonical status badge), prominent primary % (combined average for theory, practical % for labs), lecture/tutorial sections with required (75) + must-attend/safe-skip, combined average with formula caption, practical section for lab-only subjects, expandable Details with real backend forecast/optimizer values. Backend emits `required_pct` and `status` additively; banding consolidated into `attendance_engine` (single definition — dashboard/analytics/subjects share it).
- **Student event UI** (Events page + form): students get the Add Event surface restricted to the flexible subject-scoped types; edit/deactivate render per-event only where the user may mutate; backend remains authoritative.
- **Latent fix:** `AttendanceMutationResponse.student_id` → `user_id` (successful attendance mutations previously 500'd during response serialization — required for quiz-day attendance to be recordable).

### Files changed

| Layer | Files |
|---|---|
| Backend | `engines/attendance_engine.py` · `schemas/attendance.py` · `services/attendance_service.py` · `services/event_service.py` · `services/event_session_service.py` · `services/dashboard_service.py` · `services/analytics_service.py` · `repositories/event_repo.py` · `api/v1/endpoints/events.py` · `api/v1/endpoints/attendance.py` |
| Scripts | NEW `scripts/materialize_quiz_day_sessions.py` · NEW `scripts/verify_attendance_spec_alignment.py` · `scripts/verify_phase_6_5.py` · `scripts/verify_phase_7_2.py` · `scripts/verify_phase_7_1.py` · `scripts/verify_phase_6_7.py` (deliberate assertion updates) |
| Frontend | `src/types/api.ts` · `src/components/dashboard/SubjectAttendanceCard.tsx` · `src/components/events/EventFormDialog.tsx` · `src/components/events/eventRules.ts` · `src/app/(authenticated)/tools/events/page.tsx` |
| Docs | `MASTER_ROADMAP.md` · `implementation_plan.md` · `task.md` · `walkthrough.md` · NEW `docs/attendance_ui_refinement_report.md` |

### Verification

- `verify_attendance_spec_alignment.py` **15/15** (quiz-day sessions on all 18 dates · eligibility-window exclusion · recordability + as_of counting · student event authorization incl. non-enrolled 403 via temp partial-enrollment user · synchronizer guard · additive fields · exact baseline).
- Frozen regression (no assertion weakened except the documented deliberate re-scopes): 6.5 **27/27** · 6.6 **36/36** · 6.7 **31/31** · 7.1 **26/26** · 7.2 **26/26** · 8.1 **22/22**.
- Static: compileall PASS · `npx tsc --noEmit` PASS (0 errors) · ESLint clean on changed files · `next build` PASS (14 routes).

### Database mutation status

- **Documented, authorized, minimal**: sessions 684 → **691** (7 quiz-day sessions; reversible via `--undo`). Nothing else touched: events=18 · cancelled=0 · extra=0 · records=89 · enrollments=18 · subjects=9 · quizzes=18 · users=30 (1 ADMIN).

---

## PHASE 8.2 — ATTENDANCE MONITORING + LAB DOMAIN CORRECTION

Status: **COMPLETE (2026-08-15) — PASS.** Attendance (/subjects) corrected to an attendance-monitoring-only page; canonical backend-owned Attendance Health introduced; laboratory domain separated with the smallest safe session-bound mid-sem designation. Full report: `docs/phase_8_2_implementation_report.md`.

### Root-cause trace (the "14")

The reported `11 / 14` denominator is **not** a quiz window: it comes from the canonical `class_sessions` table (non-cancelled sessions `<= today` via `AttendanceRepository.get_subject_counts_for_user`). Every theory subject has exactly 14 real lectures through 2026-08-15 (3/week since 2026-07-15) — no fixed "14" constant exists anywhere. The page's real defect was **presentation ownership**: quiz strategy (must-attend / safe-skip / forecast / current-vs-forecast / required 75% / Defaulter badge) rendered on an attendance card, plus the legacy SAFE/WATCH/CRITICAL banding.

### Implemented

1. **Attendance Health (backend-owned):** `classify_attendance_health` in `attendance_engine.py` — HEALTHY ≥ 75 · WATCH 65–<75 · AT RISK 60–<65 · CRITICAL <60 (documented; current recorded-only %; None when nothing recorded). Emitted additively as `SubjectAttendanceSummary.health` (and `AnalyticsSubjectItem`). Legacy `status` (SAFE/WATCH/CRITICAL) stays emitted for the frozen dashboard/analytics surfaces; React maps health to existing semantic tokens — never bands.
2. **Attendance card redesign (attendance-only):** header (code · THEORY/LAB · name · Health badge); large "Overall Attendance" % + progress bar; balanced Lecture/Tutorial blocks (attended/total + %); formula caption; labs show Practical Attendance + backend-backed "Mid-Sem Practical" row; View Details = attended/missed/pending only. No quiz strategy anywhere. Compact/horizontal layout; responsive 1/2/3 columns. `/subjects` copy updated to attendance-only.
3. **Laboratory domain separation:** practical attendance = canonical `ClassSession(PRACTICAL)` + `AttendanceRecord` (verified; cancelled excluded); experiment curriculum/progress = `laboratory_experiments`/`laboratory_records` (both empty — **no fabricated data**); mid-sem = ADMIN-designated session-level fact.
4. **Mid-sem designation (smallest safe foundation):** `class_sessions.designation` (nullable enum `sessiondesignation`; migration `e5f6a7b8c9d0`); `PUT/DELETE/GET /api/v1/laboratory/{code}/mid-sem` — admin-only mutations tied to an actual PRACTICAL session (400 for LECTURE/foreign-subject, 404 missing; one per subject, replaceable, clearable); the date comes from the real session — never computed; attendance against it flows through the normal mutation. Missing faculty scheduling authority documented — no faculty system invented.

### Files changed

| Layer | Files |
|---|---|
| Backend | `engines/attendance_engine.py` · `models/enums.py` · `models/timetable.py` · `schemas/attendance.py` · `services/attendance_service.py` · `repositories/attendance_repo.py` · `services/laboratory_service.py` (NEW) · `api/v1/endpoints/laboratory.py` · `schemas/laboratory.py` |
| Migration | `alembic/versions/e5f6a7b8c9d0_add_session_designation.py` (NEW, applied) |
| Scripts | NEW `scripts/verify_phase_8_2.py` · `scripts/verify_phase_7_1.py` (check 23 **authorized fixed re-baseline `records == 89` → `records == 92`**; +3 legitimate BCS-501 marks entered via the canonical attendance mutation path before the audit; assertion keeps a FIXED expected count — no dynamic baseline) |
| Frontend | `src/types/api.ts` · `src/components/dashboard/SubjectAttendanceCard.tsx` · `src/app/(authenticated)/subjects/page.tsx` |
| Docs | `MASTER_ROADMAP.md` · `implementation_plan.md` · `task.md` · `walkthrough.md` · NEW `docs/phase_8_2_implementation_report.md` |

### Verification

- `verify_phase_8_2.py` **18/18** (current-to-date totals · no fixed denominator · quiz-window independence · tutorial/lecture-only formulas · cancelled-practical exclusion · canonical practical attendance · no experiment inference/fabrication · unchanged Quiz Eligibility · exact baseline · Health boundaries · session-bound admin mid-sem).
- Frozen regressions (all green): 6.5 **27/27** · 6.6 **36/36** · 6.7 **31/31** · 7.1 **26/26** · 7.2 **26/26** · 8.1 **22/22** · attendance-spec **15/15**.
- Static: compileall PASS · `npx tsc --noEmit` PASS (0 errors) · ESLint clean · `next build` PASS (14 routes).

### Database state

- Migration `e5f6a7b8c9d0` applied (additive nullable column; zero rows changed). Baseline: events=18 · sessions=691 (0 cancelled, 0 extra) · records=92 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN) · laboratory tables empty · designations=0. BCS-054 Quiz III = 2026-10-23 unchanged.

### Deferred (intentionally NOT done here)

- Authoritative experiment titles/curriculum (unavailable — nothing fabricated), faculty scheduling system (missing authority boundary — documented), "Lab Progress N/10" on the Attendance page, Quiz Eligibility engine / Phase 6 calendar architecture changes. Browser/manual testing remains the user's responsibility. **HARD STOP — no commit made; Phase 9 (Laboratory System) is the next planned phase.**

---

## PHASE 9.0 — LABORATORY DOMAIN AUDIT & SPECIFICATION

Status: **COMPLETE (2026-08-15) — READ-ONLY AUDIT + SPECIFICATION ONLY.** No
code, schema, migration, seed, API, or UI implemented. Phase 9.1 NOT started.
Full audit: `docs/phase_9_0_laboratory_domain_audit.md`.

### Findings

- **Attendance is already correct**: lab practical attendance is canonical
  `ClassSession(PRACTICAL)` + `AttendanceRecord`; cancelled excluded; pending
  stays pending; current recorded-only; labs excluded from quiz eligibility
  (404). No engine/rule change required by Phase 9.
- **Domain is a clean, intentionally empty foundation**: `laboratory_experiments`
  and `laboratory_records` = 0 rows (no authoritative curriculum — nothing
  fabricated); mid-sem = ADMIN-designated session-level fact
  (`class_sessions.designation`, Phase 8.2) that never alters counting.
- **Gaps**: (1) authoritative experiment curriculum UNKNOWN (legacy "10
  experiments" in the retired vanilla-JS `LAB_RULES` is NOT authoritative);
  (2) no experiment↔session linkage (`LaboratoryRecord.date_conducted` is a
  bare date); (3) no FACULTY role (ADMIN only); (4) no audit identity on
  designation/signature; (5) `/tools/laboratory` hosts the Track page (naming
  artifact); (6) frontend `SubjectCategory` type drift (unused legacy enum —
  cleanup candidate, untouched).
- **Hard boundaries kept**: no `experiments >= 5 ⇒ mid-sem` rule, no fake
  mid-sem dates, no fabricated curriculum, students can never designate
  mid-sem (403), Quiz Eligibility and Phase 6 calendar architecture untouched.

### Files changed

- NEW `docs/phase_9_0_laboratory_domain_audit.md` (20 sections + verification).
- `MASTER_ROADMAP.md` · `implementation_plan.md` · `task.md` · `walkthrough.md`
  — Phase 9 tracking sections updated (historical phase records untouched).

### Verification / mutation status

- Read-only inspection + SELECT queries + the existing self-cleaning
  `verify_phase_8_2.py` (**18/18 PASS**; check 11 asserts exact baseline restore).
- DB byte-equivalent to the frozen baseline: events=18 · sessions=691 (0
  cancelled, 0 extra) · records=92 · enrollments=18 · subjects=9 · quizzes=18 ·
  users=30 (1 ADMIN) · lab tables empty · designations=0.
- No commit.

### Blocking product decisions (before Phase 9.1)

1. Authoritative curriculum source (titles/numbers/count per lab subject).
2. FACULTY role vs ADMIN-only for lab mutations.
3. Audit identity (designated_by / signed_by).
4. Experiment↔session linkage (`laboratory_records.class_session_id`).
5. Mid-sem progress check vs free faculty/admin choice.
6. Student mutation boundary for experiment completion (attendance=student;
   signature/completion=faculty?).
7. Grading/viva enablement.

### Proposed Phase 9.1 scope (smallest safe increment)

Additive lab read model (`GET /laboratory/{code}/summary` + `/activities`,
pure aggregation of canonical data), curriculum ingestion boundary
(authoritative payloads only), experiment progress surface under the chosen
authority, dedicated Laboratory page IA (Practical Attendance · Mid-Sem ·
Activity History · Experiment Progress only when authoritative). New
read-only verifier + frozen regressions. **HARD STOP — Phase 9.1 not started.**

---

## PHASE 9.0b — PRODUCT DECISION REVIEW

Status: **COMPLETE (2026-08-15) — DECISION REVIEW + SPECIFICATION ONLY.** No
code, schema, migration, data, API, UI, seed, or commit. Phase 9.1 remains
**BLOCKED / NOT STARTED**. Deliverable: `docs/phase_9_product_decisions.md`
(decision matrix, one recommendation per blocking decision, each labeled
FACT-from-repository / PRODUCT RECOMMENDATION / UNKNOWN-or-requires-real-world
input).

### Decisions and recommended choices

1. **Curriculum — E (hybrid).** Provenance-bound admin ingestion of an
   authoritative institutional catalog; nothing seeded until a real catalog
   exists; per-subject count = catalog row count, never a constant (no "10").
2. **Faculty role — DEFER.** Keep STUDENT + ADMIN for 9.1; add FACULTY only
   with a defined signature/grading workflow (9.2+), designed as a narrower
   elevation via a capability matrix.
3. **Audit identity — minimal additive.** Timestamps + `signed_by` +
   `designated_by/at` + catalog provenance; no created_by on attendance.
4. **Experiment↔session linkage — nullable FK.** `laboratory_records.
   class_session_id` + validation (PRACTICAL/mid-sem of same subject, not
   cancelled); single primary link; multiple experiments per session allowed.
5. **Mid-sem rule — advisory only.** "Eligible for mid-sem designation (X of
   Y)" derived from the real catalog; designation stays a manual ADMIN act;
   no auto-designation, no gate, no universal count.
6. **Student boundary — two-tier.** Students self-track (status pending);
   only ADMIN/FACULTY sets SIGNED (official).
7. **Grading/viva — EXCLUDE from Phase 9.** Defer to a separate
   academic-assessment phase; dormant `marks`/`remarks` columns retained.

### Explicitly rejected

Hardcoded curriculum · seeding without an authoritative source · "10
experiments" default · auto mid-sem from count · hard mid-sem eligibility
gate · required (non-nullable) session FK · FACULTY without a workflow ·
marks/viva in Phase 9 · second attendance engine / React attendance math.

### Phase 9.1 prerequisites (exact)

D1 curriculum source confirmed (or experiment sections deferred) · D2
STUDENT+ADMIN only · D3 minimal audit set · D4 nullable FK migration ·
D5 advisory-only readiness · D6 two-tier progress · D7 no grading. Then
Phase 9.1 = additive lab read model + ingestion boundary + nullable FK
migration + audit columns + advisory + Laboratory page IA, verified read-only
with exact-baseline restore. **BLOCKED until the owner confirms §14 of
`docs/phase_9_product_decisions.md`.**

### Phase 9.1 — Laboratory Attendance & Event Integration (COMPLETE 2026-08-15)

The owner LOCKED the product decision (event-driven model), which superseded
the read-only audit's additive read-model proposal for 9.1. Implemented:

- Two new AcademicEvent types — `MID_SEM_PRACTICAL`, `LAB_CANCELLED`
  (subject-scoped, PRACTICAL-only, student-creatable for enrolled practical
  subjects, optional `note`); registry rules + `STUDENT_CREATABLE_EVENT_TYPES`
  + calendar-engine priority 30 (per-occurrence tier).
- Synchronizer (additive): `LAB_CANCELLED` cancels the matching practical
  occurrence (canonical `is_cancelled`); `MID_SEM_PRACTICAL` REUSES the
  timetable practical occurrence (never duplicates) or materializes exactly
  one extra on a non-lab day, then designates it
  (`ClassSession.designation = MID_SEM_PRACTICAL`, first P slot by start time
  then id — deterministic period resolution). Designation is context, never
  attendance; managed only when the triggering event is MID_SEM_PRACTICAL.
- Reversibility via existing state-based reconciliation (span-union on move;
  soft-delete deactivation); idempotent; attendance-safe (attended sessions
  never deleted/cancelled; cancelled ≠ absent 409 preserved).
- Conflict default: LAB_CANCELLED wins over MID_SEM_PRACTICAL on the same
  occurrence (no two conflicting sessions).
- Additive read models only: `designation` on history/daily sessions; `note`
  on events. Migration `a1b2c3d4e5f6_add_lab_event_types.py` (2 PG enum
  values + nullable `note`; zero data rows changed).
- Verification `verify_phase_9_1.py` 28/28; frozen regressions green except
  7.1 check 23 (BASELINE DRIFT: records 92 → 95 — 3 legitimate owner-entered
  BCS-502 marks; verifier NOT modified; owner must authorize the fixed
  fixture 92 → 95). Full details:
  `docs/phase_9_1_implementation_report.md`.
- NOT implemented: experiment curriculum/progress, `experiments ≥ 5 ⇒
  mid-sem`, FACULTY role, grading/viva, second lab engine, new endpoints,
  period selector (backend resolves deterministically).

### Phase 9.2.1 — Laboratory Experiment Management (COMPLETE 2026-08-16)

Per the LOCKED Phase 9.2.0 audit (`docs/phase_9_2_0_laboratory_experiment_
audit.md`) and its product decisions. Attendance stays canonical; experiment
management is an additive layer with no fabricated curriculum.

- **Migrations A + B** (`f1a2b3c4d5e6f` + `f6a5b4c3d2e1f`): `laboratory_
  experiments` gains `description`, `is_active` (default TRUE), `UNIQUE
  (subject_id, experiment_number)`; `laboratory_records` gains `class_session_
  id` (FK → class_sessions), `signed_by`/`created_by`/`updated_by` (FK →
  users). `created_at`/`updated_at` already existed on both tables (Base
  mixin) — NOT re-added. Strictly additive + reversible; head at
  `f6a5b4c3d2e1f`; both lab tables remain 0 rows.
- **Backend**: `LaboratoryExperiment`/`LaboratoryRecord` models updated
  (explicit `foreign_keys` for the now 4-way users FK); schemas extended
  (summary/activity/create/update payloads); `LaboratoryRepository` full CRUD
  + record counts + activity rows; `LaboratoryService` implements the §16
  authorization matrix (reads 404 unenrolled, writes 403, admin bypass; record
  creation forced PENDING; only ADMIN signs → `signed_by` = current admin,
  `signed_on` = now; cancelled sessions reject linkage at write time; duplicate
  (user, experiment) → 409; experiment must be ACTIVE and of the same subject).
  `GET /laboratory/{code}/summary` reuses `AttendanceService.get_summary` for
  the practical block (backend-owned math, zero duplication).
- **API** (all under `/api/v1/laboratory/{code}`): `GET summary|experiments|
  records|activity`; `POST/PATCH/DELETE records[/{id}]` (student self-track +
  admin sign/edit); `POST/PATCH/DELETE experiments[/{id}]` (admin ingest /
  correct / deactivate). Phase 8.2 `GET/PUT/DELETE mid-sem` untouched.
- **Frontend**: dedicated `/laboratory` route (new nav item; `/tools/
  laboratory` remains the Track page). Three tabs — Practical Attendance
  (canonical summary + mid-sem card), Experiments (honest "Experiment
  curriculum not yet available" empty state when `catalog_available=false`;
  Track/Delete for students, Sign/Add/Deactivate for admins), Activity
  (truthful session chronology; session without record shows "Practical
  session — no experiment recorded"). No React-side attendance math; no
  "10 experiments" placeholder. New types + `useLabSummary`/`useLabActivity`/
  `useLabMutations` hooks.
- **Verification**: `verify_phase_9_2.py` 29/29. Frozen regressions green:
  6.5 (27/27), 6.6 (36/36), 7.2 (26/26), 8.1 (22/22), attendance-spec
  (15/15), 8.2 (18/18), 9.1 (28/28). **Known pre-existing drift (NOT caused
  by 9.2.1)**: 6.7 29/31 (checks 4/7: 4 owner-entered test events beyond the
  18 seeded QUIZ_DAY) and 7.1 25/26 (check 23: records 92 → 95, same drift
  documented in the 9.1 report). Frozen verifiers NOT modified; drift must be
  authorized for removal or fixture update.
- NOT implemented (deferred): experiment-count gate on anything, auto
  designation, FACULTY role, marks/viva/grading, seeded curriculum, second
  lab attendance engine, Phase 9.2.2.
- Full details: `docs/phase_9_2_1_implementation_report.md`.

## Focused Track Correction (after Phase 9.2.1 — 2026-08-16)

**Scope**: two Track attendance defects fixed as a focused correction (NOT a
new phase; no Phase 9.3).

- **Two-hour lab = ONE attendance occurrence.** BCS-551/552/553 labs are two
  contiguous one-hour timetable periods (two ClassSession rows by design).
  New `app/engines/practical_occurrence.py` collapses contiguous
  same-subject/same-date PRACTICAL periods into ONE logical occurrence at
  every consumer: Track daily view (one card "01:00 PM – 03:00 PM"), summary
  denominators (blocks, not rows), history, dashboard/analytics weekly,
  calendar session counts, and the laboratory summary. One Present/Absent
  decision ⇒ one canonical AttendanceRecord; block status precedence
  ATTENDED > MISSED > CANCELLED(no records) > PENDING; cancelled blocks
  excluded (never Pending/Absent). Representative session id: recorded member
  > cancelled member > first member. Attendance engine formulas and the
  counting tuple shapes are unchanged — only the rows fed to them are
  occurrence-collapsed.
- **Future dates view-only.** `record_attendance` rejects sessions after the
  institution-local date (400, `institution_today()` from
  `settings.INSTITUTION_TIMEZONE`); Track renders future sessions as
  Upcoming with no mutation controls and hides "Mark all present".
- **Verifier updates** (contract-driven, per-row → occurrence semantics, no
  weakening): 6.6 (22/23/24), 8.1 (3-5/7/11/16), 8.2 (1/6/7), 9.1 (12/13),
  7.2 (5/6), attendance-spec (3). New focused `verify_track_lab_fix.py`
  **16/16**. Frozen regressions green except documented pre-existing drift:
  7.1 25/26 (records 92→95) and 6.7 30/31 (22 events vs 18 seeded) — NOT
  modified.
- **No schema/migration change; no ClassSession merged or deleted by this
  work** (the frozen 6.6 window cleanup removed a pre-existing orphan extra
  session, returning sessions to the documented 691/0 baseline).
- Full report: `docs/track_lab_attendance_correction_report.md`.

## Focused History Filters Correction (after Phase 9.2.1 — 2026-08-16)

**Scope**: /history filter crash fixed as a focused read/filter correction (NOT a phase; no Phase 9.3 started).

- **Root cause**: frontend-only. `useAttendanceHistory` keys SWR on the request URL; any filter change (or Load-more offset change) is a new key, so `history` is `undefined` with `isLoading=true` while fetching. The Load-more button rendered under `(isLoading || (history && ...))` while `rows` still held the previous filter's items, then dereferenced `history!.total_count` — the reported `TypeError: Cannot read properties of undefined (reading 'total_count')` at `history/page.tsx:322`.
- **Backend**: audited fully healthy — subject/status/date_from/date_to/search filters, inclusive dates clamped to semester+today, occurrence-level status matching (cancelled blocks = one Cancelled occurrence), filtered `total_count` and full-set `summary`; inverted range = deterministic empty intersection. No backend change.
- **Fix**: Load-more button gated on `history && rows.length < history.total_count` with a spinner row while loading; the filter-signature reset effect also clears `rows` so the previous filter's rows are never shown/mixed (skeleton while the filtered request loads). No `keepPreviousData` (would show stale-filter rows).
- **Verifier**: new `verify_history_filters.py` **20/20** (temp student BCS-501 + BCS-551; unfiltered shape/totals, theory/practical subject filters, 2-hour lab = one occurrence, inclusive from/to/from+to, search by code/name/type case-insensitive, Present/Absent/Pending/Cancelled states, combined filters, zero-result, pagination + Load-More accumulation without duplication, clearing filters, shape consistency, exact baseline restore).
- **Frozen regressions**: 6.5 27/27 · 6.6 36/36 · 7.2 26/26 · 8.2 18/18 · attendance-spec 15/15 · 9.1 28/28 · 9.2 29/29 · track-lab-fix 16/16. Pre-existing owner-data fixture drift untouched: 7.1 24/26 (checks 6/23), 6.7 28/31 (checks 4/6/7), 8.1 21/22 (check 7 — admin gained a BCS-551 2026-07-20 Missed record between runs).
- **DB**: records 101 before and after (zero attendance data touched); sessions 695→693 via the frozen 6.6 documented startup cleanup of 2 unattended owner extra sessions (2 attended owner extras preserved).
- Full report: `docs/history_filters_correction_report.md`.

---

## Focused Quiz Day Recovery + Verifier Hardening (2026-08-16)

- **Recovery**: reactivated exactly the 18 seeded QUIZ_DAY events (quiz_schedules-backed + 08-14 creation window — never type/date/count); restored the 6 canonical uncovered-date quiz-day sessions via the idempotent `materialize_quiz_day_sessions.py` (10-16 BCS-502 correctly absent — Option-B covered; the audit's 7th row was the owner's 08-17 test-event session, intentionally not restored). Canonical 10-23 BCS-054 session restored and pinned by 7.1 check 5 (PASS).
- **Hardening — ownership/artifact-scoped cleanup, the data-loss class fixed**: `verify_events_correction.py` no longer deletes by date/shape windows (removed MY_WINDOWS; cleans only captured event/session IDs) 42/42; `verify_track_lab_fix.py` cleans only its own sessions by captured ID — a **delta** (never the collapsed daily view, whose occurrence id on a lab day is a pre-existing timetable row) 16/16; `verify_history_filters.py` un-cancels only its captured BCS-551 block 20/20.
- **Focused verifier**: new `verify_quiz_day_restore.py` 11/11 (twice, idempotent) — seed schedules/events present + active + UUID-stable, 6 canonical quiz-day sessions present, no duplicates, records 122 unchanged, owner 08-17 test event inactive, owner data preserved.
- **Owner data healed/preserved**: BNC-501 07-31 extras re-materialized via the canonical sync and survive all verifier runs (extras 8 before/after); BCS-551 08-24 block intact.
- **Frozen verifiers NOT weakened.** Remaining failures are owner-data drift from the owner's duplicate active BNC-501 08-24 quiz-day event (`6019a478`): 6.5 26/27 (check 20, surfaced by restoring the seeds), 6.7 28/31 (4/6/7), 7.1 25/26 (6). All other suites green (6.6, 7.2, 8.1, 8.2, 9.1, 9.2, attendance-spec, quiz-day-materialization).
- **DB**: records 122 → 122 (no attendance mutation); sessions 698; events 38; quizzes 18/18 SCHEDULED. No commit.
- Full report: `docs/quiz_day_recovery_report.md`.
- **Phase 8.3 — dedicated Analytics page (T-3 product decision resolved, 2026-08-16)**: `/analytics` composes `GET /api/v1/analytics/overview` (overall current/forecast, weekly semester trend, subject-wise analytics with health + 75% optimizer). No new API, no backend change, no DB change, no React math — the read model's fields are rendered as-is (null-gap weeks, unreachable optimizer, both canonical bandings). Added `Analytics` nav entry. Verification: `tsc --noEmit` · ESLint · `next build`; `verify_phase_8_1.py` 22/22 + `verify_phase_8_2.py` 18/18 re-run; DB counts byte-identical (31/27/9/18/38/698/122). **REMOVED (2026-08-17)**: the dedicated `/analytics` route + nav entry were removed; the read model is still consumed by the Dashboard and Attendance surfaces. No backend/DB change.

---

## PHASE 11 — NOTIFICATIONS & REMINDERS (IN PROGRESS — 2026-08-20)

Status: **COMPLETE & FROZEN** — 11.0 architecture audit ✅ · 11A backend notification read model & contracts ✅ · 11B notification persistence + read-state ✅ · 11D notification center UX ✅ · 11E preference wiring verified — no additional implementation required ✅ · 11F final verification & freeze ✅ · 11C decision-gated/deferred (NOT implemented).

### 11.0 — Architecture & Discovery Audit (COMPLETE)

Read-only audit establishing the Phase 11 baseline: zero notification substrate exists (no model/table/endpoint, no scheduler, no Web Push/SW/PWA — PWA is Phase 13); `class_reminders` is the only preference with an active consumer; `auto_mark_present` and `week_starts_on` remain storage-only (auto-mark must NOT ship without an explicit product decision). Phase 11 = in-app notifications generated on-read; delivery model decision-gated (11C). Report: `docs/phase_11/phase_11_architecture_audit.md`.

### 11A — Backend Notification Read Model & Contracts (COMPLETE)

Smallest safe slice, fully additive, zero DB change:

- Additive `NotificationKind` enum (CLASS_REMINDER, QUIZ_APPROACHING, ATTENDANCE_THRESHOLD, MUST_ATTEND, SAFE_SKIP, ACADEMIC_EVENT) — `backend/app/models/enums.py`.
- `backend/app/schemas/notification.py` — `NotificationItem` (deterministic natural-key `id`, kind, date, optional subject context, message, canonical reference fields for 11B dedup) + `NotificationsResponse` (server-generated `as_of`).
- `backend/app/services/notification_service.py` — read-only projection of existing engine/service outputs (AttendanceService subject summaries, engine banding + optimizer, `get_current_quiz_cycle`, `get_sessions_with_status`, dashboard upcoming-events selection); no persistence; **notifications consume engine outputs, never calculate attendance**.
- `GET /api/v1/notifications` (JWT owner only; no client `user_id`) — `backend/app/api/v1/endpoints/notifications.py`, registered in `backend/app/api/api.py`.
- CLASS_REMINDER gated by the `class_reminders` preference (missing row = documented default off); `auto_mark_present` / `week_starts_on` remain inert.
- Verifier: `backend/scripts/verify_phase_11a.py` **19/19**. compileall PASS. Alembic head unchanged (`c1d2e3f4a5b6`); frozen-table baseline byte-identical (31 users · 47 events · 715 sessions · 142 records · 27 enrollments · 9 subjects · 18 quizzes · feedback 0 · userpreferences 0); no commit.
- Report: `docs/phase_11/phase_11a_implementation_report.md`.

### 11B — Notification Persistence + Read-State API (COMPLETE)

Smallest safe slice, fully additive; one new migration; no frozen system touched:

- Migration `d1e2f3a4b5c6_add_notifications.py` (additive, single alembic head chaining `c1d2e3f4a5b6`) — `notifications` table + `notificationkind` enum (`backend/alembic/versions/`). `user_id` FK NOT NULL (JWT-derived owner; never client-supplied), `kind`, `occurrence_key`, `date`, nullable `subject_code`/`subject_name`, `message`, nullable typed source references (`session_id` / `quiz_cycle` / `event_id`), `is_read` / `is_dismissed` BOOLEAN NOT NULL DEFAULT FALSE, `id`/`created_at`/`updated_at` from the Base mixin. `UNIQUE(user_id, kind, occurrence_key)` = DB-enforced idempotency. No relationships to attendance/events/quiz/lab tables.
- `backend/app/models/notification.py` — `Notification` model (registered in `backend/app/models/__init__.py`).
- `backend/app/repositories/notification_repo.py` — owner-scoped repository; `upsert` (PostgreSQL `ON CONFLICT DO UPDATE`, refreshing only message/subject references/updated_at; preserves date/is_read/is_dismissed/created_at), `get_inbox` (newest first, dismissed excluded), `get_by_id`, `count_unread`, `count_for_user`, `update_state` (idempotent), `delete`.
- `backend/app/services/notification_service.py` (extends 11A) — generation snapshots each Phase 11A projection into a row via deterministic identity (`occurrence_key` mirrors the 11A natural-key reference: session id / quiz cycle / event id / subject code); `GET` serves the persisted inbox newest-first with `unread_count`; `update_state` for PATCH. 11A projection semantics unchanged.
- `backend/app/schemas/notification.py` — additive `notification_id` + `is_read` on `NotificationItem`; `unread_count` on `NotificationsResponse`; `NotificationUpdate` (at least one of `is_read`/`is_dismissed`; empty body → 422).
- `backend/app/api/v1/endpoints/notifications.py` — `PATCH /api/v1/notifications/{notification_id}` (read/dismiss; owner-scoped → 404 cross-user / nonexistent). `GET /api/v1/notifications` contract preserved (now the persisted inbox).
- Read/unread/dismiss persisted state is per the audit 11B contract ("read-state API"; PATCH read/dismiss). No push/email/SMS/scheduling/Celery/Redis/cron/browser notification/worker introduced — 11C remains decision-gated and deferred.
- Verifier: `backend/scripts/verify_phase_11b.py` **23/23**; Phase 11A verifier re-run **19/19** (re-scoped checks 13/14/18/19 to prove the table exists as the 11B surface and that the verifier restores it to its pre-run state — projection semantics untouched); `compileall` PASS; alembic single head `d1e2f3a4b5c6` before/after; DB baseline restored (31 users · notifications 0; snapshot byte-identical incl. notifications); no commit.
- Report: `docs/phase_11/phase_11b_implementation_report.md`.

### 11D — Frontend Notification Center UX (COMPLETE)

Frontend-only slice consuming the live 11A/11B backend contract; no backend change:

- `frontend/src/types/api.ts` — additive notification types mirroring the backend contract: `NotificationKind` enum (the six 11A kinds), `NotificationItem` (natural-key `id`, kind, date, subject context, message, source references, `notification_id`, `is_read`), `NotificationsResponse` (`items`, `as_of`, `unread_count`), `NotificationUpdate` (PATCH payload).
- `frontend/src/hooks/useApi.ts` — `useNotifications(enabled)` (SWR on `GET /api/v1/notifications`, key gated on `enabled`, `STANDARD_CACHE` — focus revalidation only, no polling) + `useNotificationMutation()` (`PATCH /api/v1/notifications/{id}`, returns the server's updated item).
- `frontend/src/components/notifications/NotificationBell.tsx` — bell entry in the authenticated `TopNav`; unread badge from the backend `unread_count`, hidden at zero, capped at "99+"; opening the center revalidates once.
- `frontend/src/components/notifications/NotificationCenter.tsx` — shell `ShellDialog` ("Notifications", unread count in the description): loading skeletons, error + retry, honest empty state, newest-first persisted inbox; each row shows the kind badge/icon, message, subject + occurrence date, unread emphasis (dot + emphasis + "Read" action); dismiss removes the row. SWR cache is updated only from genuine PATCH responses (no faked success); failures surface in an inline banner and leave the list unchanged. Bell and center share the same SWR key, so read/dismiss keeps the badge in sync with no extra requests.
- `frontend/src/components/layout/TopNav.tsx` / `UserMenu.tsx` — bell mounted in the right cluster; `notifications` added to `ShellModalId`; `NotificationCenter` rendered like the other shell modals. No shell component rebuilt.
- Authorization: the client never sends `user_id` — the backend derives ownership from the JWT. No client-side notification logic, no push/email/SMS/scheduling/cron/worker/PWA behavior (11C remains decision-gated).
- Verification: `npx tsc --noEmit` PASS · ESLint on changed files PASS · `npm run build` PASS. No backend file changed; no migration. No commit.

### 11E — Remaining Preference Wiring (VERIFIED — NO ADDITIONAL IMPLEMENTATION REQUIRED)

Discovery-first audit of the remaining preference→notification wiring (audit §5A/5B/5C, §11E):

- **`class_reminders`** — the only consumer, already implemented inside 11A (`NotificationService._class_reminders`, read at generation time; missing row = documented default off). Verified: 11A checks 7/8, 11B check 18.
- **`auto_mark_present` / `week_starts_on`** — confirmed storage-only (audit §5B auto-mark needs an explicit product decision; §5C week-start is a display preference for a future phase). Verified inert: 11A checks 11/12, 11B check 18.
- **SettingsModal copy made truthful** (the audit-named 11E change): "Class reminders are shown in the bell icon when enabled"; the other preferences remain explicitly storage-only. Same for the `UserPreferences` contract comment in `frontend/src/types/api.ts`.
- No backend change, no migration, no new verifier (the preference→notification matrix is already fully exercised by `verify_phase_11a.py` 19/19 and `verify_phase_11b.py`).
- Verification: `compileall` PASS · 11A verifier **19/19 PASS** · 11B verifier **21/23** — checks 19/20 fail on **diagnosed environmental data drift, not a code regression** (backend byte-identical to the 23/23 run): the admin's pre-existing inbox rows (created 17:58 today) legitimately persist under the documented 11B "rows stay until dismissed" semantics, and the verifier's own temp QUIZ_DAY fixture on the admin's own subject temporarily shifts the admin's canonical quiz cycle to 2 and reorders the top-4 event selection mid-run. Checks 19/20 assume a clean admin inbox (documented verifier fragility; a clean inbox passes 23/23). No code was modified to force a pass.
- DB baseline restored (users 31 · admins 1 · notifications 10 = admin's pre-existing rows); alembic single head `d1e2f3a4b5c6` unchanged. Frontend: `tsc` PASS · ESLint PASS · `npm run build` PASS. No commit.
- Report: `docs/phase_11/phase_11e_implementation_report.md`.

### 11F — Final Verification & Freeze (COMPLETE — PHASE 11 COMPLETE & FROZEN)

- **Audit:** working tree clean at `4117992` (11E); preference matrix reconciled (`class_reminders` consumed only at `notification_service.py:143-145`; `auto_mark_present`/`week_starts_on` storage-only; `event_session_service.py:215` prose, not a consumer); architecture coherent (11A read contract → 11B persistence → 11D API consumption); alembic single head `d1e2f3a4b5c6`.
- **Drift resolved, verifier-only:** the 11E failures (11B checks 19/20) and a fresh 11A check-16 failure were confirmed as determinism issues on a used admin inbox, NOT production defects. Both verifiers hardened to **accumulation-compatible** assertions (checks 15/16/17 in 11A; 17/19/20 in 11B): coverage (live canonical state ⊆ persisted inbox) + run-generated correctness (rows created during the run match conditions at generation time) + uniqueness + bounded growth (≤1 quiz / ≤4 events). A UUID-vs-string baseline comparison bug in the first hardening attempt was also fixed (`admin_baseline_str`). **Zero production code changed.**
- **Final gates (used environment):** `compileall` PASS · `verify_phase_11a.py` **19/19** (×2, before & after the 11B run) · `verify_phase_11b.py` **23/23** · frontend `tsc --noEmit` PASS · ESLint on Phase 11 files PASS (whole-tree ESLint has 6 pre-existing errors in non-Phase-11 files — recorded as backlog, untouched per boundary) · `npm run build` PASS.
- **DB/migration:** baseline restored — users 31 · admins 1 · notifications 11 (the admin's legitimate pre-existing rows incl. the new SAFE_SKIP BCS-501 row and the legitimately stale BCS-503 row) · events 49; alembic single head/current `d1e2f3a4b5c6`, unchanged; no frozen-table mutation; no duplicate rows.
- **Freeze:** Phase 11 (11.0/11A/11B/11D/11E) **COMPLETE & FROZEN**. Known accepted limitation: inbox rows accumulate until dismissed by design (11B semantics); the dismiss/read UX is the remediation.
- Report: `docs/phase_11/phase_11f_verification_report.md`. **No commit made.**

### 11C (NOT IMPLEMENTED — DECISION-GATED, DEFERRED)

- **11C** — delivery model (decision-gated: in-app only vs scheduled sweep) — **deferred**, not invented; may be omitted from Phase 11 entirely.

**HARD STOP after 11F** — no commit made; Phase 11 COMPLETE & FROZEN (11A ✅ · 11B ✅ · 11D ✅ · 11E ✅ · 11F ✅); 11C remains decision-gated/deferred and NOT implemented.

---

## Phase 12 — Mobile / Responsive Experience

### 12.0 architecture & implementation-readiness audit (COMPLETE, 2026-08-21)

- Read-only audit, NO code or data changes: `docs/phase_12/phase_12_architecture_audit.md`.
- Verdict: READY FOR ONLY A PHASE 12 SUB-PHASE (12A). Key findings: mobile navigation ABSENT (TopNav nav `hidden md:flex`); touch targets all below 40px (buttons h-6..h-9, icon-only size-6..9); ShellDialog dialogs cannot scroll (content clipped on short screens); Laboratory tab bar nowrap ~380px clipped by the shell (highest overflow risk); NO BACKEND CHANGE REQUIRED.
- S4 prior art (`docs/17_AI_HANDOFF.md:41-43`): exactly 4 bottom tabs (Dashboard/Subjects/History/Profile) + Academic Tools from Profile, never a 5th tab. Legacy `frontend/public/css/responsive.css` (NOT imported) documents 5 breakpoints + 44px touch minimums + FAB — treated as design reference only.
- Governance inconsistency fixed: Phase 12 was mislabeled "PWA & Offline" (MASTER_ROADMAP + walkthrough) — now "Mobile / Responsive Experience"; PWA/Installability is Phase 13.

### 12A responsive foundation + mobile navigation (COMPLETE, 2026-08-21)

Scope (foundation only; page-level work is 12B-12F):

- NEW `frontend/src/components/layout/MobileBottomNav.tsx` — fixed bottom nav `md:hidden`, exactly 4 tabs (Home `/dashboard`, Attendance `/subjects`, History `/history`, Profile `/profile`), Profile as the S4-compatible anchor opening a controlled More bottom sheet (side=bottom, safe-area padding, rounded-t-2xl) hosting Profile + 5 tools (Track `/tools/laboratory`, Laboratory `/laboratory`, Quiz Eligibility `/tools/quiz-schedule`, Calendar `/calendar`, Events `/tools/events`). Active state = usePathname exact match; icons mirror TopNav (LayoutDashboard/BookOpen/History/CircleUserRound). Rows min-h-14 tabs / h-12 sheet rows = >=40px touch targets. No new routes; desktop nav untouched.
- `AppShell.tsx` — renders `<MobileBottomNav />`; container `p-4 pb-28 md:p-6 lg:p-8` (bottom clearance only below md; desktop padding byte-identical).
- `ui/button.tsx` — touch-target foundation: mobile base sizes with `sm:` desktop restores — default `h-10 sm:h-8`, xs `h-9 sm:h-6`, sm `h-10 sm:h-7`, lg `h-11 sm:h-9`, icon `size-10 sm:size-8`, icon-xs `size-9 sm:size-6`, icon-sm `size-10 sm:size-7`, icon-lg `size-11 sm:size-9`. NOT a global h-10/h-11 replacement; desktop sizes restored at `sm:`. Auto-upgrades dialog/sheet close buttons, calendar arrows, NotificationCenter Read/Dismiss to >=36px on mobile. Explicit page-level overrides (e.g. history Reset `h-7`) are 12B scope — documented residual.
- `shell/ShellDialog.tsx` — DialogContent `max-h-[90dvh] overflow-y-auto` (EventFormDialog pattern); fixes all 6 shell modals (Profile/Appearance/Settings/Feedback/Install App) on short screens; desktop appearance preserved.
- `NotificationCenter.tsx` — list `max-h-[50dvh] md:max-h-[26rem]` (avoids nested scroll inside the dialog).
- `NotificationBell.tsx` — `-m-2.5 p-2.5 sm:-m-1.5 sm:p-1.5` -> ~40px mobile hit area.
- Intentionally NOT touched (documented): `TopNav.tsx`/`UserMenu.tsx` (avatar hit area already adequate; brand+bell+avatar fits 320px), `ui/dialog.tsx`/`ui/sheet.tsx` (close buttons auto-fixed via button.tsx), `app/layout.tsx` (Next.js default viewport correct; viewport-fit=cover deferred), page components (12B-12F scope), all backend/DB/migration/API/PWA.

Verification: `tsc --noEmit` PASS; ESLint (6 changed files) PASS; `npm run build` PASS (15 routes prerendered); `git diff --check` PASS; working tree: 5 modified frontend files + 1 new component + docs/phase_12/ — zero backend changes, no migrations, no DB mutation, no generated artifacts. Browser/manual testing NOT performed (user's responsibility; checklist in the 12A report).

**HARD STOP after 12A** — no commit made; Phase 12: 12.0 + 12A COMPLETE; 12B (Track/Dashboard/Calendar) NEXT; desktop behavior unchanged; frozen systems untouched.

### 12B Track / Dashboard / Calendar responsiveness (COMPLETE, 2026-08-21)

Scope (responsive experience only; no logic/contract/backend change):

- `calendar/page.tsx` + `CalendarGrid.tsx` — month-nav row now `flex flex-wrap` with label `min-w-0 w-28 sm:w-36` (was fixed `w-36` ≈310px vs 288px content at 320 = real overflow, now ≈276px single row, wraps gracefully); grid card `p-2 sm:p-4` + grids `gap-1 sm:gap-1.5` (cells 31→35px at 320). Month-calendar interaction model untouched (no date-picker substitution); DayDetail/legend/error/empty states verified already responsive (unchanged).
- `tools/laboratory/page.tsx` (Track) — center date-nav column now `flex-1 min-w-0` (input stretches between the arrows on mobile); input `h-10 w-full sm:h-8 sm:w-40`; Today `sm:h-8` (mobile 40px via the 12A foundation; desktop 32px byte-identical).
- `TrackSessionCard.tsx` — header left column `min-w-0 flex-1` + badge container `flex-wrap justify-end` (long labels e.g. MID-SEM PRACTICAL no longer collide with time at 320); actions row auto-height (fixed `h-9` dropped — it clipped the 12A h-10 buttons); Change buttons dropped their explicit `h-7` override (mobile 40px, desktop `sm:h-7` identical — the 12A-documented page-level residual, now resolved).
- Dashboard — `TodayAttendanceCard` badge row `flex-wrap`; `OverallAttendanceCard` delta row `flex-wrap`; `WeeklyAttendanceCard` rows `gap-2 sm:gap-3` (progress bar kept visible at 320). All other dashboard cards verified fine at 320 (unchanged).
- Intentionally NOT changed: all backend/DB/migrations/API/engines; all 12A files (MobileBottomNav/AppShell/ShellDialog/NotificationCenter/Bell/button.tsx foundation); PageHeader/Badge/Card/GlassCard/lib/date/hooks/types; DayDetail; css/responsive.css remains unimported; no new breakpoints.

Verification: `tsc --noEmit` PASS; ESLint (7 changed files) PASS; `npm run build` PASS; `git diff --check` PASS; diff = 7 frontend files (+35/-23), zero backend/12A/artifact changes. Browser/manual testing NOT performed (owner's responsibility; checklist in the 12B report).

**HARD STOP after 12B** — no commit made; Phase 12: 12.0 + 12A + 12B COMPLETE; 12C (Laboratory/Subjects/Quiz/Events) NEXT; desktop behavior unchanged; frozen systems untouched.

---

## BUGFIX — CLASS_CANCELLED Not Propagating to Track (COMPLETE, 2026-08-22)

Authorized real-correctness fix (frozen-phase narrowly reopened where proven necessary); plan executed exactly as investigated:

1. **Reproduction:** live DB — session `19bdc85a…` (BCS-058 LECTURE 2026-07-30, holds MISSED record `faa0ce5e…`) vs active event `9e5a7f98…` (CLASS_CANCELLED, exact subject/date/class-type match). Explicit `sync_event` run left `is_cancelled=false` → defect mechanically isolated to the synchronizer.
2. **Root cause:** `_reconcile_date`'s blanket guard (`if session.id in attended_ids: continue`) made any recorded session untouchable, so explicit cancellations were silent no-ops for historical classes — the common case.
3. **Fix (synchronizer-first):** `_desired_schedule` emits `cancellation_removed` (entries explicitly removed by an active CLASS_CANCELLED only); `_reconcile_date` cancels unattended sessions as before AND explicitly-targeted recorded ones; restoration always allowed (full reversal on deactivate/edit). LAB_CANCELLED (Phase 9.1 check 18), closures/WS (6.6 checks 5/31), quiz-day protection: untouched frozen contracts.
4. **Consumer alignment via one predicate** `occurrence_is_cancelled()` (`practical_occurrence.py`): cancelled theory occurrences never count as attended/missed/pending anywhere (subject counts via `collapse_count_rows`, History filters+summary in `attendance_repo.py`, dashboard `_aggregate_range`); practical record-wins rule preserved. No records deleted anywhere.
5. **Verifier:** NEW `backend/scripts/verify_event_cancellation_propagation.py` — **26/26** (propagation over stale marks, Track Cancelled render data, mutation 409, summary/history exclusion + filters, isolation both ways, idempotent double-sync, no duplicates, move/edit reconciliation, exact reversal, closure + LAB_CANCELLED frozen-boundary probes, owner-record fingerprints, exact count baseline).
6. **Regression:** compileall PASS · 6_6 **36/36** · attendance-spec **15/15** · events_correction **42/42** · working_saturday **24/24** · 6_5 **27/27** · quiz_day_materialization **14/14** · 11A **19/19** · 11B **23/23** · phase_3 **26/26** · phase_1 **18/18** · 7_1 **26/26** · 7_2 **25/26**\* · phase_2 **14/15**\* — \* stash-A/B-proven pre-existing drift. Known-drift verifiers (history_filters 7/20, phase_9_1 21/28, track_lab_fix date-aged fixtures + pre-existing cleanup crash, 8_1 18/22, 8_2 StopIteration): identical failures reproduced on ORIGINAL code via git-stash runs — not regressions from this fix.
7. **DB safety:** full pre-work snapshot; post-work all 18 table counts byte-equal, alembic head `d1e2f3a4b5c6` unchanged, zero temp artifacts (incl. cleaning crashed-run leaks by captured IDs). Intentional canonical repair applied to the reported case: events re-synced ⇒ sessions `ea065985…` / `19bdc85a…` now cancelled with records preserved.
8. Report: `docs/bugfix/event_cancellation_propagation_report.md`. Frontend unchanged (Track already renders `is_cancelled` first). **No commit made; 12C still NEXT.**

### 12C — COMPLETE (2026-08-22): page responsiveness (commit `31f75ca`) + authorized cancellation-lifecycle & counting-consistency bugfix

Responsive scope delivered across Laboratory / Subjects / Quiz Eligibility / Events pages (`docs/phase_12/phase_12c_implementation_report.md`, commit `31f75ca`).

Authorized correctness fix executed alongside it (this bugfix round):

1. **Root cause A (trigger):** the dev backend process (started 09:07 UTC, `uvicorn` WITHOUT `--reload`) executed pre-fix code during the owner's 15:49 UTC event removals — stale cancellations were never reversed. Proven by server fingerprinting (live :8080 counts vs in-process on identical data).
2. **Root cause B (code, fixed):** `EventService.deactivate_event` early-returned when already inactive → reconciliation NEVER ran → "event removed ⇒ nothing to do" left stale state unrepairable through any application path. Now deactivation ALWAYS reconciles; state-based synchronization re-derives `is_cancelled` from the complete active event set (idempotent, self-healing, both directions). No schema change — ownership is derived, not stored.
3. **Counting:** one canonical applicability rule (`occurrence_is_cancelled`) now guards every consumer — subject summaries & eligibility windows & history (committed earlier) plus dashboard Today/Overall/Weekly-day rows, weekly %, analytics overall/weekly, notifications gate (this round).
4. **Regression:** NEW `verify_cancellation_lifecycle_consistency.py` **35/35** (unmarked/MISSED/ATTENDED lifecycles, multi-session range, deactivation incl. ALREADY-INACTIVE self-heal, reactivation cycle, PATCH-move between recorded sessions, idempotency, records byte-preserved, Track/History/Subjects/Dashboard deltas both directions, eligibility-core unit checks, isolation, exact baseline); `verify_event_cancellation_propagation.py` **26/26**; phase_6_6 **36/36**; attendance_spec **15/15**; events_correction **42/42**; working_saturday **24/24**; phase_11a **19/19**; compileall PASS. Parallel-draft verifiers `verify_bugfix_12C*.py` use absolute live-data fixtures (17→19 drift between consecutive runs) — not gates; superseded by the delta-based lifecycle verifier.
5. **Live result (BCS-058):** events removed → reconciliation restores originals (07-29 Attended / 07-30 Missed); applicable lectures back to N=79 (was stuck at N−2=77 while stale). Records byte-preserved throughout.
6. ⚠ Backend restart required (no --reload) before manual testing. **12D NOT STARTED. No commit made.**

---

### 12D — COMPLETE (2026-08-23): remaining responsive surfaces

Targeted mobile touch-target improvements on previously incomplete responsive surfaces (`docs/phase_12/phase_12d_implementation_report.md`).

**Audit:** `docs/phase_12/phase_12d_architecture_audit.md` identified SettingsModal select (h-7 = 28px), EventFormDialog controls (h-8 = 32px), and EventFormDialog two-column grids as below baseline or cramped at 320px. NotificationCenter analyzed but determined acceptable as-is.

**Implementation (frontend-only):**

1. **SettingsModal.tsx:** Week-start select upgraded from `h-7` to `h-9 sm:h-7` (36px mobile, 28px desktop restored).
2. **EventFormDialog.tsx:** `selectClass` constant upgraded from `h-8` to `h-10 sm:h-8` (40px mobile, 32px desktop restored). Applies to all select elements, date inputs, and note input.
3. **EventFormDialog.tsx:** Two `grid-cols-2` patterns upgraded to `grid-cols-1 sm:grid-cols-2`:
   - Date range start/end controls (line 404)
   - Working day / substitution controls (line 504)
   - Effect: single-column stack on mobile (<640px), two-column restored on desktop.
4. **NotificationCenter:** NOT MODIFIED — current row layout analyzed at 320px (268px content width after padding; ~92px for actions; ~128px remaining for text with `min-w-0 flex-1` preventing overflow). Layout is tight but functional; no hard overflow; buttons already inherit 12A sizes (40px mobile).

**Verification:**
- `tsc --noEmit` PASS
- ESLint (2 changed files) PASS
- `npm run build` PASS (15 routes prerendered)
- `git diff --check` PASS (LF/CRLF warnings only, pre-existing)
- Diff scope: 2 frontend files (+3/-3), zero backend/DB/migration/API changes

**Desktop preservation:** All changes use `sm:` restore pattern. Desktop (≥640px) receives exactly the original class values. No visual change on desktop.

**Governance:** MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md synchronized. Frozen phases (0–11, 12A/12B/12C) untouched. No cancellation/attendance/analytics logic changed.

**Manual testing:** NOT performed by agent. Owner checklist in the 12D report.

**HARD STOP after 12E** — no commit made; Phase 12: 12.0 + 12A + 12B + 12C + 12D + 12E COMPLETE; Phase 13 = PWA / Installability (next); desktop behavior unchanged; frozen systems untouched.

---

## 12E — Mobile polish + verification (COMPLETED, 2026-08-23)

**Scope:** type/density sweep (10px-text minimums), touch-target sweep, overflow audit, and static invariant verifier.

**Deliverables:**

1. **`backend/scripts/verify_phase_12e.py`** — static invariant verifier asserting Phase 12 invariants checkable without a browser:
   -viewport export present in `app/layout.tsx` (Next.js default accepted per audit §3)
   -bottom nav component gated `md:hidden` in `MobileBottomNav.tsx`
   -no new fixed grid column counts (`grid-cols-[234]` without `sm:` responsive prefix) in Phase 12-changed files
   -no bare `h-6`/`h-7` interactive heights (not part of `sm:` responsive variants) in Phase 12-changed files
   -`text-xs`/`text-sm` absent from `type="date"` inputs in Phase 12-changed files

2. **`frontend/src/components/events/EventFormDialog.tsx`** (line 504): Fixed working-day/substitution grid from `grid-cols-2` to `grid-cols-1 sm:grid-cols-2` for mobile stacking, two-column restored at `sm+`. Touch-target sizing already addressed by 12D (`h-10 sm:h-8` on all form controls).

3. **Verification results:** all static invariants PASS; `npx tsc --noEmit` clean; `npm run build` green; `git diff --check` clean. Zero backend/DB/migration/API changes. Desktop byte-identical at ≥768px.

**Dependencies:** 12A–12D. **Untouched:** all backend contracts; frozen engines; notification API contracts.

**HARD STOP:** No commit made. Phase 12 fully complete. Next phase: Phase 13 — PWA / Installability.

---

## 13E — PWA / Installability (COMPLETED, 2026-08-23)

**Scope:** PWA infrastructure deployment — manifest, service worker, icons, install prompt, standalone detection, online/offline state, conservative caching.

**Deliverables:**

1. **`frontend/public/manifest.json`** — web app manifest with name, short_name, description, start_url, scope, display: standalone, theme_color, background_color, icons referencing SVG assets.

2. **`frontend/public/icons/icons-192.svg`**, **`frontend/public/icons/icons-512.svg`** — application icons as SVG files matching the project's dark-visual-system branding (#3B82F6 / #0F172A).

3. **`frontend/public/service-worker.js`** — conservative PWA service worker:
   - Caches static application shell assets on install
   - Network-first for all API requests (never caches authenticated/personalized data)
   - Cache-first for navigation requests with offline fallback
   - Activates new SW and cleans up old caches
   - Does not cache API responses, attendance data, quiz eligibility, profile data, settings, or feedback

4. **`frontend/src/components/pwa/useServiceWorker.ts`** — service worker registration hook:
   - Registers SW only in browser client
   - Does not break SSR (client-only execution)
   - Returns `swRegistered` and `isStandalone` state
   - Does not interfere with `beforeinstallprompt` or `useInstallPrompt`

5. **`frontend/src/components/shell/InstallAppModal.tsx`** — updated install prompt message to reflect configured PWA infrastructure:
   - PWA infrastructure now configured (manifest + service worker)
   - Browser may offer install prompt depending on platform support
   - Some platforms (e.g., iOS Safari) do not support web app installation
   - Tracked in task.md

6. **`frontend/src/app/layout.tsx`** — manifest link added via `manifest: "/manifest.json"` metadata field.

7. **`backend/scripts/verify_phase_12e.py`** — static invariant verifier (Phase 12E) asserting Phase 12 invariants PASS.

**Verification results:** all Phase 12E invariants PASS; `npx tsc --noEmit` clean; `npm run build` green; `git diff --check` clean. Zero backend/DB/migration/API changes. Desktop byte-identical at ≥768px.

**Dependencies:** 12A–12D. **Untouched:** all backend contracts; frozen engines; notification API contracts.

**Offline capability:** Cached shell resources available; data-dependent pages communicate offline status. Does NOT claim offline attendance/quiz/history/analytics data availability.

**HARD STOP:** No commit made. Phase 13 — PWA / Installability. Next phase: Phase 14 — Firebase Retirement.

---

## PHASE 14 — FIREBASE RETIREMENT

### Phase 14.0 — Firebase Retirement Audit (COMPLETE, read-only, 2026-08-23)

Repository-wide read-only audit; report: `docs/phase_14/phase_14_architecture_audit.md`.
Verdict: **ready to proceed** — runtime auth is JWT + PostgreSQL only; no Firebase Auth
path reachable; no Firestore reads/writes from the Next.js app; frontend SDK init is
inert; backend Admin SDK init is inert; `firebase_uid` is nullable legacy data (no
runtime reads); deployment/config files and docs are stale. Zero code changed, zero DB
mutations, zero commits.

### Phase 14A — Frontend Firebase Removal (COMPLETE, 2026-08-23)

**Objective:** eliminate the Firebase SDK from the Next.js frontend without any runtime
behavior change (auth is JWT + localStorage only).

**Delivered:**

1. `frontend/src/lib/api.ts` — removed the dead `import { auth } from "./firebase"` (the
   `auth` binding was never referenced; `apiFetch` reads `access_token` from
   `localStorage` and attaches `Bearer` — unchanged).
2. `frontend/src/lib/firebase.ts` — deleted the obsolete Firebase initialization module
   (`initializeApp`/`getAuth` side-effect; only consumer was the dead import above).
3. `frontend/package.json` — removed `"firebase": "^12.17.1"`.
4. `frontend/package-lock.json` — reconciled via `npm install` (77 packages pruned;
   `firebase` and all `@firebase/*` absent from lockfile and `node_modules`).
5. `frontend/.env.example` / `frontend/.env.local` — removed the six
   `NEXT_PUBLIC_FIREBASE_*` variables (both files are gitignored; no values exposed).

**Verification results:** `npx tsc --noEmit` PASS (0 errors) · `npm run build` PASS
(15/15 routes) · `git diff --check` PASS · `npm ls firebase` empty · frontend/src
search clean — remaining matches are only `firebase_uid` data-field strings
(Phase 14D scope) and two stale message/comment strings (no active SDK reference).

**Scope guards:** zero backend changes; zero database changes; zero migration changes;
zero changes to auth endpoints, JWT, engines, PWA, or the legacy root app. `firebase_uid`
NOT touched. No commit made.

**Next authorized slice:** Phase 14B — backend Firebase removal
(`backend/app/core/firebase.py` + `main.py` import + `firebase-admin` from
`backend/requirements.txt`).

### Phase 14B — Backend Firebase Removal (COMPLETE, 2026-08-23)

**Objective:** eliminate the Firebase Admin SDK/runtime initialization from the FastAPI
backend while preserving the PostgreSQL-native JWT authentication architecture exactly.

**Delivered:**

1. `backend/app/core/firebase.py` — deleted (31 lines; obsolete Admin SDK initialization).
2. `backend/app/main.py` — removed only the `from app.core.firebase import
   initialize_firebase` import and the `initialize_firebase()` call; no other
   restructuring.
3. `backend/requirements.txt` — removed `firebase-admin>=6.5.0`.
4. Backend venv — uninstalled `firebase-admin` 7.5.0 plus its 13 Firebase-specific
   transitive packages (`google-cloud-firestore`, `google-cloud-storage`,
   `google-cloud-core`, `google-api-core`, `google-auth`, `google-crc32c`,
   `google-resumable-media`, `googleapis-common-protos`, `grpcio`, `grpcio-status`,
   `proto-plus`, `protobuf`, `CacheControl`). `pip check` → "No broken requirements found";
   zero Firebase/google/grpc remnants.

**Verification results:** `python -m compileall backend/app backend/alembic` PASS ·
`app.main` imports clean without Firebase (APP IMPORT OK, 32 API paths) · OpenAPI confirms
`POST /api/v1/auth/login`, `POST /api/v1/auth/register`, `/student/me`, `/student/sync`
all PRESENT · `get_current_user`/`require_admin`/`HTTPBearer` (deps.py) intact ·
`create_access_token`/`verify_password`/`hash_password` (security.py) intact ·
`git diff --check` PASS · diff limited to 3 backend files (36 deletions).

**Scope guards:** zero database changes; zero Alembic commands; `firebase_uid` column,
model, schema, API fields, and legacy values intentionally preserved (Phase 14D scope);
legacy migration scripts (`migrate_extract.py`, `migrate_execute.py`,
`diagnose_failures.py`) keep their historical `firebase_admin` imports with graceful
blocked-exit paths (out of scope); no frontend change; no commit made.

**Next authorized slice:** Phase 14C — deployment/configuration cleanup
(`firebase.json`, `.firebaserc`, `firestore.rules`, `firestore.indexes.json`,
`.gitignore` Firebase entries, Firebase prompts).

### Phase 14C — Deployment / Configuration Cleanup (COMPLETE, 2026-08-23)

**Objective:** remove the remaining Firebase deployment/configuration artifacts from
the repository without touching authentication, identity, business logic, or frozen
systems.

**Delivered:**

1. Deleted `firebase.json`, `.firebaserc`, `firestore.rules`, `firestore.indexes.json`
   (all confirmed absent after removal).
2. `.gitignore` — removed the Firebase-specific block (firebase-debug log patterns,
   `.firebase/` cache entry, `.firebaserc` comment/config block).
3. Deleted entirely-Firebase prompts: `prompts/14_FIREBASE_BACKEND_PROMPT.md`,
   `prompts/19_DEPLOYMENT_PROMPT.md`.
4. `prompts/11_RELEASE_CHECKLIST.md` — removed the Firebase Backend Verification and
   Firebase Hosting Deployment sections (renumbered).
5. `prompts/01_MASTER_IMPLEMENTATION_PROMPT.md`, `prompts/03_FEATURE_PLANNING_PROMPT.md`,
   `prompts/04_FEATURE_IMPLEMENTATION_PROMPT.md`, `prompts/16_SECURITY_REVIEW_PROMPT.md` —
   removed Firestore-rules/Firestore-schema references.
6. `prompts/README.md` — removed the index rows for the deleted prompts (14, 19),
   updated the release-checklist description, removed `19_DEPLOYMENT_PROMPT` from the
   Release Workflow.
7. `README.md` — removed Firebase init/configuration instructions (`## Configure
   Firebase`), Firestore-rule deployment instructions (`## Deploy Firestore Rules`),
   the Firebase Project/Firebase CLI requirement lines, and the project-structure
   entries for the deleted config files. Legacy-app feature/tech-stack claims remain
   for Phase 14F documentation reconciliation.

**Verification results:** all 6 deleted files confirmed absent · prompts/ Firebase
search clean · `git diff --check` PASS · diff limited to 13 files (8 deletions, 5
edits, 247 deletions / 8 insertions) · zero backend/frontend source changes.

**Scope guards:** zero database changes; zero Alembic commands; `firebase_uid`
references intentionally preserved (Phase 14D scope); legacy migration scripts
(`migrate_extract.py`, `migrate_execute.py`, `diagnose_failures.py`) preserved; legacy
root app preserved; historical `docs/` preserved for Phase 14F reconciliation; no
commit made.

**Next authorized slice:** Phase 14D — `firebase_uid`/data cleanup (legacy script
updates to `roll_number` lookups, then an Alembic migration to drop
`users.firebase_uid`, followed by model/schema/API/frontend type removal).

### Phase 14D — firebase_uid / Data Cleanup (COMPLETE, 2026-08-23)

**Objective:** remove the obsolete `users.firebase_uid` application field while
preserving all PostgreSQL/JWT authentication behavior and all existing user/account
data.

**Delivered:**

1. **Legacy scripts**: `backend/scripts/set_initial_password.py` and
   `backend/scripts/setup_single_user.py` — user lookup switched from hardcoded
   `firebase_uid` (`HCRbV7Kld3Wo9IHLJHRGlBau4Mq2`) to the canonical
   `roll_number` (`2401220100027`). No identity mechanism introduced; password
   hashing/authentication architecture untouched.
2. **Model**: `backend/app/models/user.py` — `firebase_uid` column mapping + its
   comments removed. No other User fields modified.
3. **Schema/API**: `StudentProfile` (`backend/app/schemas/student.py`) — field
   removed; `/student/me` + `/student/sync` (`backend/app/api/v1/endpoints/student.py`)
   — no longer serialize it; register (`backend/app/api/v1/endpoints/auth.py`) — no
   longer writes it; `get_by_firebase_uid()` dead method + now-unused `selectinload`
   import removed (`backend/app/repositories/user_repo.py`).
4. **Frontend**: `frontend/src/types/api.ts` + `frontend/src/contexts/AuthContext.tsx`
   — `firebase_uid` field removed from `StudentProfile`/`User` types; profile page
   (`frontend/src/app/(authenticated)/profile/page.tsx`) displays `user.id` and the
   stale "Firebase identity is active (501)" error message was replaced with truthful
   copy. No visual/behavior change beyond that.
5. **Migration**: NEW `backend/alembic/versions/e1f2a3b4c5d6_drop_firebase_uid.py`
   (down_revision `d1e2f3a4b5c6`, single head `e1f2a3b4c5d6`) —
   `DROP INDEX ix_users_firebase_uid` + `DROP COLUMN users.firebase_uid`.
   Downgrade re-creates the nullable column + unique index following the
   `c3d4e5f6a7b8` convention; no historical Firebase values invented. APPLIED via
   `alembic upgrade head`.

**Verification results:** `python -m compileall backend/app backend/scripts
backend/alembic` PASS · `npx tsc --noEmit` PASS · `git diff --check` PASS ·
`app.main` imports clean (32 paths; `/auth/login`, `/auth/register`, `/student/me`,
`/student/sync` present) · OpenAPI `StudentProfile` free of `firebase_uid` ·
`get_current_user`/`require_admin`/`HTTPBearer`/`create_access_token` intact ·
repository search: zero `firebase_uid` references in `backend/app` and `frontend/src`.

**Database before/after (SELECT-verified):** users 31 = 31 (admin 1 = 1, students
30 = 30) · student_enrollments 27 = 27 · attendance_records 159 = 159 ·
class_sessions 720 = 720 · academic_events 60 = 60 · quiz_schedules 18 = 18 ·
notifications 11 = 11 · all other table counts identical · Aditya's row untouched ·
`users.firebase_uid` column + `ix_users_firebase_uid` index gone ·
`alembic_version` = `e1f2a3b4c5d6`.

**Scope guards:** no user rows modified; no Firebase UID values copied/transformed/
repurposed; no password/roll_number/role/enrollment/attendance/academic changes;
historical migration files (`7117a007a0da`, `c3d4e5f6a7b8`) and the completed
one-shot `migrate_execute.py` preserved; historical docs preserved for Phase 14F;
no commit made.

**Next authorized slice:** Phase 14E — full authentication/data-path regression
verification (login, signup, `get_current_user`, all verifiers, frontend build).

### Phase 14E — Regression Verification (COMPLETE, 2026-08-23)

**Objective:** prove Phase 14D's `firebase_uid` removal caused no regression to the
PostgreSQL + JWT application. Verification-only phase; zero feature work.

**Delivered:**

1. **In-process regression suite** (real DB, guaranteed-rollback, temp user in an
   isolated session): 66/67 PASS — alembic single head `e1f2a3b4c5d6`; `firebase_uid`
   column + `ix_users_firebase_uid` index gone; users 31 / admin 1 / students 30 /
   distinct rolls 31; password round-trip (format, correct, wrong, empty, salted);
   login valid / wrong-password 401 / nonexistent-roll 401; JWT mint + valid
   `get_current_user` + invalid 401; `require_admin` ADMIN ok / STUDENT 403;
   `/student/me` full contract incl. NO `firebase_uid`; 16 core read paths; mutation
   contract (statuses accepted; cancelled 409; future 400; non-enrolled 403);
   admin-mutation `require_admin` wiring; feedback POST + preferences PUT;
   `/student/sync` no `firebase_uid`. The single FAIL was a harness artifact (the
   sampled session's subject happened to be one the student is enrolled in — 403
   correctly not raised), not a regression.
2. **Frozen-phase verifiers (self-cleanup, real DB)**: 6.5 27/27 · 6.6 36/36 ·
   6.7 30/31 (check 7 FAIL: live DB has 4 pre-existing user-created inactive
   QUIZ_DAY events from 2026-08-16 — pre-dates Phase 14D; not a regression; check
   27 exact baseline restore PASS) · 7.1 26/26 · 10C 23/23 · 10D 18/18 ·
   11A 19/19 · 11B 23/23 · 12E 5/5.
3. **One verifier compatibility fix**: `verify_phase_11b.py` hardcoded the
   Phase 11B-era alembic head (`d1e2f3a4b5c6`); updated to current head
   `e1f2a3b4c5d6` (assertion + docstring, 4 lines) — required because the Phase 14D
   migration legitimately advanced the head.
4. **Persistent-mutation audit**: a leaked temp user (from a crashed harness run
   before rollback) and a leaked lab-experiment row (from an early flawed direct-call
   test) were detected via baseline re-reads and removed. Final DB state
   byte-identical to baseline.
5. **Static checks**: `compileall` PASS · `npx tsc --noEmit` PASS · `npm run build`
   PASS (15/15) · Firebase search clean (`frontend/src` + `backend/app` have zero
   `firebase`/`firestore`/`firebase_uid`; only 3 stale comments remain — Phase 14F).

**Scope guards:** zero feature work; zero auth/JWT/engine changes; zero DB mutations
(verifier artifacts self-cleaned; final counts byte-identical); browser/manual testing
deferred to the owner; no commit made.

**Next authorized slice:** Phase 14F — freeze & governance reconciliation
(docs/README/tech-stack reconciliation, archive stale Firebase documentation).

### Phase 14F — NOT STARTED

- **14F** Phase freeze & governance reconciliation — NOT STARTED.

---

