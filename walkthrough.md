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