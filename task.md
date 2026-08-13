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
