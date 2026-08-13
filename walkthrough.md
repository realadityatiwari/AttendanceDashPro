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