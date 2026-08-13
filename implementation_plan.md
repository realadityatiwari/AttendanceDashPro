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
