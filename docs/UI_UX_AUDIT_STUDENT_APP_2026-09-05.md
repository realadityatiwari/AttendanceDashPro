# AttendanceDashPro — UI/UX Audit Report (Next.js Student App)

**Date:** 2026-09-05
**Scope:** Student-facing surfaces of the current Next.js 16 / React 19 / Tailwind v4 application (`frontend/src`).
**Method:** Static code inspection only (AUDIT / DISCOVERY — no code was modified). Manual browser testing is deliberately left to the user; findings that cannot be settled statically are marked "Needs manual verification".
**Note:** `docs/S3.5_UI_UX_AUDIT.md` documents the legacy pre-rewrite V1 app and is retained as history; this document covers the current Next.js application only.

---

## 1. Executive Summary

| Metric | Count |
|---|---|
| Total findings | 40 |
| P0 (critical usability/visual defect) | 2 |
| P1 (major UX problem) | 7 |
| P2 (significant inconsistency/friction) | 17 |
| P3 (minor polish) | 11 |
| P4 (nice-to-have) | 3 |

**Systemic issues (root patterns appearing across many surfaces):**

1. **Dead design tokens** — `bg-surface`, `bg-surface2`, `text-text2` are used in 25+ places but are defined in no stylesheet (verified: 0 occurrences in the compiled production CSS). Skeletons and loading states referencing them render invisible/transparent because `tailwind-merge` strips the valid `bg-muted` fallback from `Skeleton`.
2. **`--accent` misused as a visible brand/semantic color** — the token is `#262626` (a dark hover-surface gray, near-identical to the card background `#171717`), yet it drives calendar event dots, the calendar selection ring, links, and highlights. These elements are effectively invisible.
3. **Duplicated component implementations** — at least 6 inline error-state variants, 5 empty-state variants, 3 page-header patterns, 4 select-height systems, and duplicated helpers (`humanizeEventType`, `classTypeLabel`, date chips) instead of the shared primitives that already exist.
4. **Terminology drift** — Attended/Missed vs Present/Absent; "State" vs "Status"; nav label "Attendance" → page title "Subjects Overview"; "Track" → "Track Attendance" at a URL named `/tools/laboratory`; locale-dependent vs hard-coded date formats; rounded vs 1-decimal percentages.

**Most important UX risks:**
- Invisible loading states and calendar indicators (P0 pair) undermine trust in a data-heavy academic tool.
- Error recovery is inconsistent: the primary surfaces (Dashboard, History, Subjects, Track) render an error with **no Retry**, while secondary surfaces do have one.
- Bulk "Mark all present" performs many irreversible mutations in one tap with no confirmation.
- No 404/global error UI exists; users falling out of the route graph hit unstyled default white pages inside a forced-dark PWA.

---

## 2. Route / Surface Inventory (discovered)

| Route | Title | Notes |
|---|---|---|
| `/login`, `/signup` | "Student Portal" / "Create Account" | Raw HTML inputs/buttons, not the app design system |
| `/dashboard` | Greeting header | 6 cards; combined summary + analytics read model |
| `/subjects` | "Subjects Overview" | Nav label is "Attendance"; subject attendance cards |
| `/tools/laboratory` | "Track Attendance" | Daily attendance marking; nav label "Track" |
| `/laboratory` | "Laboratory" | Practical attendance / experiments / activity tabs |
| `/tools/quiz-schedule` | "Quiz Eligibility" | Cycle tabs; per-subject eligibility cards |
| `/tools/events` | "Academic Events" | Student/admin event management + filters |
| `/calendar` | "Calendar" | Month grid + day detail panel |
| `/history` | "Attendance History" | Filters, summary, paginated rows |
| `/tools/feedback` | "Feedback" | Admin-only review surface (role-gated link) |
| `/profile` | "Profile Settings" | Read-only; also Profile modal in shell |
| Shell modals | Profile, Appearance, Settings, Feedback, Install App, Notifications | Global dialogs via user menu / bell |

There is **no** dedicated `/analytics`, `/timetable`, `/quizzes`, or `/eligibility` route: analytics live in dashboard cards, timetable only surfaces through Track/Calendar, quizzes through Quiz Eligibility. `not-found.tsx`, `error.tsx`, and `loading.tsx` do **not** exist anywhere in `frontend/src` (verified by file search).

---

## 3. Findings by Severity

### P0 — Critical

- **UI-001** Dead design tokens (`bg-surface`, `bg-surface2`, `text-text2`) — invisible loading states and unstyled surfaces (systemic).
- **UI-002** `--accent` (#262626) used as a visible semantic/brand color — calendar event dots, selection ring, links and highlights are near-invisible.

### P1 — Major

- **UI-003** Desktop top navigation risks horizontal overflow at the `md`–`lg` band (8–9 labeled items + brand + controls in one `h-14` row with no shrink/truncate).
- **UI-004** Redundant, confusingly named Laboratory surfaces ("Track" at `/tools/laboratory` vs "Laboratory" at `/laboratory`), plus a dead-end "View Strategy" CTA.
- **UI-005** Error recovery is inconsistent: Dashboard/History/Subjects/Track error states offer no Retry.
- **UI-006** One-tap bulk "Mark all present" with no confirmation and terse partial-failure feedback.
- **UI-007** No `not-found.tsx` / `error.tsx` — default unstyled white 404/error pages inside a forced-dark app.
- **UI-008** Mobile: no active-route indication for secondary destinations and no page title in the mobile header.
- **UI-009** `window.alert` for event deactivation errors; confirmation patterns are inconsistent across surfaces.

### P2 — Significant

- **UI-010** Internal/dev copy leaks into student UI (multiple surfaces).
- **UI-011** Nested layout containers: page-level max-widths and padding fight the shell container.
- **UI-012** Status label/color systems are inconsistent across surfaces.
- **UI-013** Weekly bar color thresholds (80/60) are hard-coded and inconsistent with backend status bands.
- **UI-014** Notification center: one global pending lock, no "mark all read", no undo for dismiss.
- **UI-015** Destructive icon buttons (delete lab record / deactivate experiment) act immediately without confirmation.
- **UI-016** Four different select/input height systems across the app.
- **UI-017** Date formatting mixes device-locale and hard-coded formats.
- **UI-018** Percentage display mixes rounded and 1-decimal formats across analytics surfaces.
- **UI-019** Settings preferences (week start, auto-mark present) have no effect anywhere.
- **UI-020** Quiz cycle tabs misuse ARIA tab semantics (no panels, no keyboard support).
- **UI-021** Duplicated component implementations (errors, empties, headers, helpers) — systemic.
- **UI-022** Dashboard silently ignores analytics-overview failures (partial data rendered as if complete).
- **UI-023** Service-worker updates are announced only via `console.log` — users are never told to reload.
- **UI-024** Touch targets below 44px guidance on History filters, Settings switch, several dialogs.
- **UI-025** No global success-feedback layer (toasts); success is only inline text swaps.
- **UI-026** Session expiry redirects silently via `window.location.href = '/login'` with no message or context.

### P3 — Minor

- **UI-027** No first-use/onboarding guidance for a new/empty dataset.
- **UI-028** Signup hard-codes CSE-51 elective options; auth pages bypass the design system; password visibility toggle exists only in signup.
- **UI-029** Login page identity mismatch ("Student Portal", "Login securely", "AttendanceDash Pro V2").
- **UI-030** Track page duplicates the daily summary (top progress card + bottom stat card).
- **UI-031** Greeting renders "Good Morning, " with an empty name if the profile fails.
- **UI-032** Pervasive `text-[10px]` micro-labels hurt legibility.
- **UI-033** Laboratory section tabs use `aria-current="page"` on buttons (wrong ARIA).
- **UI-034** Modal height caps mix `90vh` (EventFormDialog) and `90dvh` (ShellDialog).
- **UI-035** Event form exposes engine jargon (working-day state, substitution schedule, duration mode) at students.
- **UI-036** Quiz Eligibility intro is a wall of formula text.
- **UI-037** PWA manifest `background_color` (#0F172A) mismatches the app background (#0a0a0a).

### P4 — Refinement

- **UI-038** Weekly list abbreviates pending as "Np" without explanation.
- **UI-039** Notification-center empty state uses a CalendarDays icon (a bell would match).
- **UI-040** Dashboard grid: only Today's card stretches (`h-full`), so two-column rows have ragged bottoms.

---

## 4. Complete Finding Registry

| ID | Severity | Category | Screen | Finding | User Impact | Evidence | Confidence |
|----|----------|----------|--------|---------|-------------|----------|------------|
| UI-001 | P0 | Visual Consistency / States | Laboratory, Quiz Eligibility, Subjects, Lab views, Quiz card | `bg-surface`, `bg-surface2`, `text-text2` are used in 25+ classNames but defined nowhere; compiled CSS contains zero such utilities | Loading skeletons are invisible/transparent; nested surfaces lose their intended tone; users see blank boxes instead of loading feedback | `app/globals.css` (no tokens); compiled `.next/static/chunks/*.css` (0 matches); `components/dashboard/SubjectAttendanceGrid.tsx:20,40`; `app/(authenticated)/laboratory/page.tsx:93,140,173,260,414,416,478`; `app/(authenticated)/tools/quiz-schedule/page.tsx:48,71,82`; `components/quiz/QuizEligibilityCard.tsx:102,216,231,238,249`; `components/dashboard/SubjectLaboratoryView.tsx:18,48,50,74,76,90`; `components/dashboard/home/OverallAttendanceCard.tsx:45`; `components/layout/UserMenu.tsx:60`; `components/shell/ProfileModal.tsx:42`; `components/ui/skeleton.tsx` (cn drops `bg-muted` when a later invalid `bg-*` is passed via tailwind-merge) | HIGH |
| UI-002 | P0 | Color/Contrast | Calendar, Events, Profile, DayDetail | `--accent` is `#262626` (hover-surface gray) but is used as event-dot color, selection ring, link color and section-icon color | Event dots, "Selected" legend swatch, selection ring, and accent links are nearly invisible against `#0a0a0a`/`#171717` backgrounds; calendar legend shows a dot students cannot see | `app/globals.css:64` (`--accent: #262626`); `components/calendar/CalendarGrid.tsx:76,86,131,146`; `components/calendar/DayDetail.tsx:54,112`; `components/events/EventRow.tsx:180`; `app/(authenticated)/profile/page.tsx:60,122`; `app/(authenticated)/tools/quiz-schedule/page.tsx:50` | HIGH |
| UI-003 | P1 | Navigation / Responsive | Desktop header (768–1023px) | 8 nav items (+1 admin) with text labels are shown from `md` up in one `h-14` header alongside brand and user controls; no truncation/shrinking | At 768–1023px the labeled items (~700px+) plus brand plus controls likely overflow the header, wrapping or clipping navigation | `components/layout/TopNav.tsx:30-41,64,82-110` | MEDIUM — needs manual verification at 768/1024px |
| UI-004 | P1 | Information Architecture | `/tools/laboratory` vs `/laboratory` | Two sibling lab surfaces with overlapping names: nav "Track" → "Track Attendance" (URL `/tools/laboratory`), nav "Laboratory" → `/laboratory`; "View Strategy" on the dashboard Attention card links to Track, which contains no strategy content | Students cannot predict what each nav item opens; the "View Strategy" promise is unfulfilled, breaking the dashboard's attention→action loop | `components/layout/TopNav.tsx:31-33`; `components/layout/MobileBottomNav.tsx:35-36`; `app/(authenticated)/tools/laboratory/page.tsx:134`; `components/dashboard/home/AttentionRequiredCard.tsx:69-71` | HIGH |
| UI-005 | P1 | Feedback/States | Dashboard, History, Subjects, Track | Shared `ErrorState` has no retry action; pages using it leave the user stuck on an error card (reload is the only recovery), while Events/Calendar/Notifications/QuizEligibility implement their own Retry buttons | Inconsistent failure recovery; the most-used surfaces are the least recoverable | `components/shared/ErrorState.tsx` (no action prop); `app/(authenticated)/dashboard/page.tsx:19-29`; `app/(authenticated)/history/page.tsx:306-308`; `app/(authenticated)/subjects/page.tsx` via `SubjectAttendanceGrid.tsx:26-35`; `app/(authenticated)/tools/laboratory/page.tsx:109-116`; contrast: `app/(authenticated)/calendar/page.tsx:143-146`, `app/(authenticated)/tools/events/page.tsx:257-260` | HIGH |
| UI-006 | P1 | Interaction / Destructive actions | Track Attendance | "Mark all present" fires N parallel attendance mutations on a single tap with no confirmation; partial failures produce only "N session(s) could not be marked." | An easily-tapped bulk action silently converts all pending classes to Present — a data-integrity risk with no undo and vague failure reporting | `app/(authenticated)/tools/laboratory/page.tsx:82-107,212-222` | HIGH |
| UI-007 | P1 | Error recovery / Navigation | Global | No `not-found.tsx`, `error.tsx`, or `loading.tsx` anywhere in the app | Unknown URLs and render crashes show Next.js default (unstyled white) pages inside a forced-dark PWA; jarring and off-brand | File search of `frontend/src` returns no such files; `app/` tree enumerated in discovery | HIGH (existence); rendering appearance needs manual verification |
| UI-008 | P1 | Navigation / Mobile | Mobile shell | Bottom nav highlights only the 3 primary tabs by exact path match; when a secondary destination (Track, Laboratory, Quiz, Calendar, Events) is open, no tab or More entry shows an active state after the sheet closes, and the mobile header shows no page title | Students lose wayfinding: the current location is not indicated anywhere on mobile for 5 of 8 destinations | `components/layout/MobileBottomNav.tsx:73-107` (active check only in PRIMARY_TABS; More highlighted only while `moreOpen`); `components/layout/TopNav.tsx` (no mobile title) | HIGH |
| UI-009 | P1 | Interaction / Feedback | Events | Deactivation failure is reported via blocking `window.alert`; confirmation patterns differ per surface (inline Confirm/Cancel swap in EventRow, dialog buttons elsewhere, none for lab deletes) | Inconsistent, jarring error and confirmation experiences for the same class of action | `app/(authenticated)/tools/events/page.tsx:88-99` (`window.alert`); `components/events/EventRow.tsx:141-172` (inline confirm); compare dialogs in `components/shell/*` | HIGH |
| UI-010 | P2 | Content/Microcopy | Profile, Install App, Settings, Feedback modal, Laboratory | Internal/dev language leaks into student-facing copy: "Student Identity (PostgreSQL)", stale duplicated PWA paragraphs ending "Tracked in task.md", "the server VAPID key is configured in a later phase", "instead of a fake confirmation", "Program is resolved from your section…", admin button "Ingest" | Students see engineering terminology and contradictory statements; the Install modal contains two conflicting paragraphs (PWA configured vs "Once PWA support lands…") | `app/(authenticated)/profile/page.tsx:61`; `components/shell/InstallAppModal.tsx:99-108`; `components/shell/SettingsModal.tsx:196-198`; `components/shell/FeedbackModal.tsx:178-185`; `components/shell/ProfileModal.tsx:85-88`; `app/(authenticated)/laboratory/page.tsx:340` | HIGH |
| UI-011 | P2 | Layout/Spacing | All pages | Pages add their own `max-w-*` (7xl/5xl/4xl/2xl) and `px-4 py-6/8` inside the shell's `max-w-5xl p-4 md:p-6 lg:p-8` container | Double horizontal padding on mobile (e.g. 32px), inconsistent content widths per page, inconsistent vertical rhythm (`py-6` vs `py-8`), and the 7xl/4xl max-widths are dead above the shell's 5xl | `components/layout/AppShell.tsx:35`; `app/(authenticated)/subjects/page.tsx:8` (max-w-7xl); `app/(authenticated)/laboratory/page.tsx:63` (max-w-7xl); `app/(authenticated)/tools/laboratory/page.tsx:130` (max-w-2xl, py-6); `app/(authenticated)/tools/quiz-schedule/page.tsx:42` (max-w-4xl, py-8); `app/(authenticated)/calendar/page.tsx:167` (max-w-5xl, py-6); `app/(authenticated)/history/page.tsx:193` (max-w-5xl, py-6) | HIGH |
| UI-012 | P2 | Visual Consistency / Content | OverallAttendanceCard, AttentionRequiredCard, SubjectAttendanceCard, History, Track | The same semantic states are labeled and colored differently: raw enums "SAFE"/"WATCH"/"CRITICAL" badges on dashboard vs mapped "Healthy/Watch/At Risk/Critical" on subject cards; "Attended/Missed" vs "Present/Absent" mixed across Today card, Track, and History; error styling uses 4 different raw-`red-*` treatments vs the `destructive` token | Identical concepts render with different words and colors, increasing cognitive load and eroding trust in the color language | `components/dashboard/home/OverallAttendanceCard.tsx:26-28` (raw status); `components/dashboard/home/AttentionRequiredCard.tsx:44-46` (raw status); `components/dashboard/SubjectAttendanceCard.tsx:18-23` (mapped labels); `components/dashboard/home/TodayAttendanceCard.tsx:18-29` (Attended/Missed) vs `components/dashboard/TrackSessionCard.tsx:62,85` (Present/Absent) vs `app/(authenticated)/history/page.tsx:25-31` (Present/Absent); raw reds: `components/shared/ErrorState.tsx:14-18`, `components/dashboard/SubjectAttendanceGrid.tsx:28-31`, `app/(authenticated)/laboratory/page.tsx:148-150`, `components/quiz/QuizEligibilityCard.tsx:107-111` | HIGH |
| UI-013 | P2 | Analytics / Color semantics | WeeklyAttendanceCard | Weekly bar colors hard-code 80/60 thresholds while every other surface uses backend status bands (SAFE/WATCH/CRITICAL) | The same percentage can be green on one card and amber on another; banding logic duplicated client-side contradicts the "backend derives, frontend renders" rule stated in the code's own comments | `components/dashboard/home/WeeklyAttendanceCard.tsx:81-89`; compare `components/dashboard/SubjectAttendanceCard.tsx:11-30` | HIGH |
| UI-014 | P2 | Notifications | Notification center | One global `pendingId` disables Read/Dismiss on every row while any single action is in flight; there is no "mark all read"; dismiss removes the row with no undo and no aggregate count control | Slow/multiple actions feel serialized and sluggish; mass-clearing N notifications requires N taps; a mis-tap dismiss is unrecoverable | `components/notifications/NotificationCenter.tsx:97,118-147,243-272` | HIGH |
| UI-015 | P2 | Interaction / Destructive actions | Laboratory (experiments) | Delete-record and deactivate-experiment are one-tap ghost icon buttons (Trash2) with no confirmation — unlike event deactivation which confirms | Accidental data loss with no guard or undo, inconsistent with the app's own event-deactivation pattern | `app/(authenticated)/laboratory/page.tsx:451-461` | HIGH |
| UI-016 | P2 | Forms / Component consistency | Settings, History, Events, EventFormDialog, Laboratory, Login/Signup | Four coexisting select/input height systems: `h-9 sm:h-7` (Settings), `h-8` fixed (History/Events filter classes), `h-10 sm:h-8` (EventFormDialog), `h-9` (Laboratory); login/signup use raw `h-10` inputs instead of the `Input` primitive (`h-8` default) | Visibly different control heights for identical concepts; native selects styled ad hoc instead of one shared select primitive | `components/shell/SettingsModal.tsx:302`; `app/(authenticated)/history/page.tsx:176-179`; `components/events/EventFormDialog.tsx:104-105`; `app/(authenticated)/laboratory/page.tsx:78`; `app/(auth)/login/page.tsx:91-99`; `app/(auth)/signup/page.tsx:140-141`; `components/ui/input.tsx:12` | HIGH |
| UI-017 | P2 | Content/Microcopy | Profile modal, History, Events, Subject cards, Dashboard | Date rendering mixes `toLocaleDateString(undefined)` (device locale) with hard-coded `en-GB`/`en-US` and a custom `WEEKDAY · D Mon YYYY` format | The same date appears as "5 Sep 2026", "Sep 5, 2026", or "Saturday · 5 Sep 2026" depending on surface and device; inconsistent and fragile | `components/shell/ProfileModal.tsx:13` (en-GB); `components/dashboard/SubjectAttendanceCard.tsx:44` (`undefined` locale); `components/quiz/QuizEligibilityCard.tsx:31` (en-US); `lib/date.ts:25-33` (custom); `app/(authenticated)/history/page.tsx:88` (en-US time) | HIGH |
| UI-038→ | | | | *(renumbered below)* | | | |

*(Registry continues in ID order — see UI-018 through UI-040 below.)*

| ID | Severity | Category | Screen | Finding | User Impact | Evidence | Confidence |
|----|----------|----------|--------|---------|-------------|----------|------------|
| UI-018 | P2 | Content/Microcopy | Dashboard, Quiz Eligibility, Subject cards | Percentages mix `Math.round` (`formatPct`) and `toFixed(1)` (`fmtPct`/`fmtIntPct`) across adjacent cards | The same attendance value shows "75%" on the dashboard and "75.0%" in eligibility; pseudo-precision inconsistency | `lib/date.ts:52-55` vs `components/quiz/QuizEligibilityCard.tsx:25-27` vs `components/dashboard/SubjectAttendanceCard.tsx:32-38` | HIGH |
| UI-019 | P2 | Interaction / Expectations | Settings ↔ Calendar | "Week starts on" and "Auto-mark present" preferences are stored but consumed by nothing; the calendar is hard-coded Sunday-first despite the setting (disclosed only in a small info box) | A labeled setting that visibly does nothing erodes trust in all settings; the calendar contradicts the stated preference | `components/shell/SettingsModal.tsx:313-321` (disclosure); `components/calendar/CalendarGrid.tsx:8-12` (Sunday-first hard-coded); `useApi.ts` (no consumer of `auto_mark_present`/`week_starts_on`) | HIGH |
| UI-020 | P2 | Accessibility | Quiz Eligibility | Cycle selector uses `role="tablist"`/`role="tab"` + `aria-selected` with no `tabpanel`, no `aria-controls`, and no arrow-key handling | Screen readers announce tabs that lead nowhere; keyboard users get no tab semantics that ARIA promises | `app/(authenticated)/tools/quiz-schedule/page.tsx:60-77` | HIGH (static) |
| UI-021 | P2 | Component consistency | App-wide | Duplicated implementations of shared concepts despite existing primitives: ≥6 inline error variants, ≥5 empty-state variants, 3 page-header patterns, 4 select styles, duplicated `humanizeEventType`/`classTypeLabel`/date-chip helpers, `QUIZ_LABELS` duplicating cycle labels | Every new surface drifts further from the design system; identical states look different page to page; maintenance cost compounds | `components/shared/EmptyState.tsx` vs inline empties in `TodayAttendanceCard.tsx:40-48`, `QuizSnapshotCard.tsx:33-42`, `UpcomingEventsCard.tsx:23-32`, `laboratory/page.tsx:113-116,495-501`; `components/shared/PageHeader.tsx` vs `GreetingHeader.tsx` vs inline headers (`tools/laboratory/page.tsx:132-139`); `components/events/EventRow.tsx:21-23` vs `components/calendar/DayDetail.tsx:16-18`; `components/quiz/QuizEligibilityCard.tsx` date chip vs `UpcomingEventsCard.tsx:37-44` vs `history/page.tsx:60-67` | HIGH |
| UI-022 | P2 | Feedback/States | Dashboard | `useAnalyticsOverview()` errors are never inspected; when it fails the dashboard renders without forecast/weekly series as if complete | Silent partial data: forecast line and weekly bars vanish with no explanation, indistinguishable from "no data" | `app/(authenticated)/dashboard/page.tsx:17,48-49` (`overview?.… ?? null`, no `isError` check) | HIGH |
| UI-023 | P2 | Notifications / PWA | Global (PWA) | New service-worker versions notify only via `console.log("New content available; reload page to apply update")` | PWA users can be stuck on a stale shell indefinitely with zero visible cue to reload | `components/pwa/useServiceWorker.ts:47-59` | HIGH |
| UI-024 | P3 | Accessibility / Touch | History, Settings, dialogs | Filter selects/date inputs are `h-8` (32px) on mobile; the Settings switch is 20px tall; several `size="sm"` controls are `h-6/h-7` on desktop but 40px only via the mobile override — many targets are below the 44px comfort guideline (above the 24px WCAG floor) | Small targets increase mis-taps on phones, especially in the dense History filter row | `app/(authenticated)/history/page.tsx:176-179` (h-8, no mobile override); `components/shell/SettingsModal.tsx:171-173` (h-5 switch); `components/ui/button.tsx:24-33` (sm/xs sizes) | HIGH (static); ergonomics need manual verification |
| UI-025 | P2 | Feedback | Global | There is no toast/notification surface; success feedback exists only as inline text swaps ("Saved" label, card state flips, dialog success screens) | Success and failure feedback are inconsistent across mutations; some successes (attendance marked) communicate only by the card changing, easy to miss | Absence of any toast implementation in `frontend/src`; `components/shell/SettingsModal.tsx:334-343`; `components/dashboard/TrackSessionCard.tsx:57-101` | HIGH |
| UI-026 | P2 | Error recovery / Session | Global | On hard 401 the app silently does `window.location.href = '/login'` mid-interaction | Users lose their current page/context with no "session expired, please sign in again" message | `lib/api.ts:174-180` | HIGH |
| UI-027 | P3 | Onboarding / Empty states | Dashboard, Quiz, Subjects | No first-use guidance: a brand-new account lands on a dashboard of empty cards; QuizSnapshot empty state says "Check the quiz schedule" without a link (its footer CTA disappears with the content) | New students must discover structure unaided; empty-state guidance is not actionable where it matters | `components/dashboard/home/QuizSnapshotCard.tsx:33-42,96-100` (footer only when snapshot exists) | HIGH |
| UI-028 | P3 | Forms / Content | Signup, Login | Elective options are hard-coded to CSE-51 V Semester in the client; auth pages use raw HTML inputs/buttons (not the design system); password show/hide exists only in signup | Signup data can silently go invalid for other sections/semesters; auth surfaces look and behave differently from the rest of the app; password entry on login lacks the toggle users see one screen earlier | `app/(auth)/signup/page.tsx:19-30,201-208`; `app/(auth)/login/page.tsx:91-114` (no toggle) | HIGH |
| UI-029 | P3 | Content/Microcopy | Login | Heading "Student Portal", subtitle "AttendanceDash Pro V2", submit "Login securely" | Product identity mismatch and odd microcopy ("securely" adds no meaning); version suffix is dev-facing | `app/(auth)/login/page.tsx:76-77,122` | HIGH |
| UI-030 | P3 | Cognitive load | Track Attendance | Present/Absent/Pending are shown twice (top progress card and bottom "Daily Attendance" stat card) | Redundant numbers on a small screen; vertical space consumed by duplication | `app/(authenticated)/tools/laboratory/page.tsx:197-251` | HIGH |
| UI-031 | P3 | Feedback/States | Dashboard greeting | If the profile request fails, greeting renders "Good Morning, " with an empty name (and no error state) | A visibly broken greeting undermines confidence at first glance | `components/dashboard/home/GreetingHeader.tsx:8,14-19` | HIGH |
| UI-032 | P3 | Typography | App-wide | Extensive `text-[10px]` labels for stat captions, badges and filters | Below comfortable reading size, especially on high-DPI phones; inconsistent with the otherwise token-based type scale | e.g. `QuizSnapshotCard.tsx:71-89`, `history/page.tsx:238-241`, `TrackSessionCard.tsx:169-175`, `SubjectAttendanceCard.tsx:109-114` | HIGH |
| UI-033 | P3 | Accessibility | Laboratory | Section tabs are `<button>`s using `aria-current="page"` (a link landmark attribute) instead of proper tablist/tab semantics | Screen readers get meaningless state; inconsistent with the Quiz page's (also imperfect) tab attempt | `app/(authenticated)/laboratory/page.tsx:94-109` | HIGH |
| UI-034 | P3 | Responsive | EventFormDialog vs ShellDialog | Event form caps at `max-h-[90vh]` while ShellDialog uses `90dvh` | On mobile browsers with dynamic toolbars the event form can leave its footer under the visible viewport | `components/events/EventFormDialog.tsx:352`; `components/shell/ShellDialog.tsx:66` | HIGH (static) |
| UI-035 | P3 | Cognitive load / Forms | EventFormDialog | Students are asked to choose engine-level fields: "Working day state" (Working/Non-working/Not specified), "Substitution schedule" (weekday names), Single day vs Date range radios | High-friction creation flow for "record what happened today"; jargon invites wrong submissions the backend then rejects | `components/events/EventFormDialog.tsx:386-442,531-571` | HIGH |
| UI-036 | P3 | Content clarity | Quiz Eligibility | The intro is a dense paragraph with Criterion I/II, two thresholds and the averaging formula | Students must parse institutional policy prose to understand the page; key facts (70 vs 75) are buried mid-sentence | `app/(authenticated)/tools/quiz-schedule/page.tsx:48-58` | HIGH |
| UI-037 | P3 | PWA / Visual | Install splash | Manifest `background_color` #0F172A differs from app background #0a0a0a | Visible flash/mismatch when launching the installed app | `frontend/public/manifest.json:9`; `app/globals.css:47` | HIGH |
| UI-038 | P4 | Content/Microcopy | WeeklyAttendanceCard | Pending count rendered as "· 3p" | Unexplained abbreviation; minor comprehension cost | `components/dashboard/home/WeeklyAttendanceCard.tsx:96-99` | HIGH |
| UI-039 | P4 | Content/Icons | Notification center | Empty-state icon is CalendarDays for a notifications surface | Small semantic mismatch; a bell would match the entry point | `components/notifications/NotificationCenter.tsx:188-194` | HIGH |
| UI-040 | P4 | Layout | Dashboard | Only Today's card uses `h-full`; two-column rows have uneven card bottoms | Minor ragged-grid aesthetic on desktop | `components/dashboard/home/TodayAttendanceCard.tsx:20`; siblings lack it | HIGH |

---

## 5. Detailed Explanations (key findings)

### UI-001 — Dead design tokens (P0, systemic)
`globals.css` defines `--background, --card, --popover, --primary, --secondary, --muted, --accent, --destructive, --success, --warning, --border, --input, --ring` — there is no `--surface`, `--surface2`, or `--text2`, and the imported `shadcn/dist/tailwind.css` (629 lines, inspected) defines no color tokens at all. A grep of the compiled production CSS (`​.next/static/chunks/1hpeeyal_orxx.css`) returns **zero** matches for `bg-surface`, `bg-surface2`, or `text-text2`. Consequences by class of use:
- **Skeletons**: `Skeleton` renders `cn("animate-pulse rounded-md bg-muted", className)`. `tailwind-merge` treats `bg-muted` and the passed `bg-surface/50` as one group and keeps the **last**, so the valid background is removed and the invalid one generates nothing → fully transparent skeleton. Affects Laboratory (3 tabs), Quiz Eligibility, `SubjectLaboratoryView`.
- **Raw divs**: `SubjectAttendanceGrid.tsx:20` renders three `bg-surface` pulse divs → invisible loading grid.
- **Nested surfaces**: `bg-surface2/30`, `bg-surface2/50` (quiz info bar, tabs, calculation rows, lab headers, avatars) silently fall back to the parent background — the intended elevation hierarchy is lost app-wide.
- **Text tone**: `OverallAttendanceCard.tsx:45` — "if all pending attended" loses its intended secondary tone.

### UI-002 — Accent used as a visible color (P0, systemic)
The token table pins `--accent: #262626` with comment "slightly lighter charcoal for elevated surfaces" — it is a *hover surface*, and `--accent-foreground` exists for contrast. But components consume `accent` directly as a brand/semantic color: calendar legend "Event" dot (`bg-accent`), non-today selection ring (`ring-accent`) and its legend swatch, DayDetail substitution highlight, EventRow "Calendar" link (`text-accent`), profile section icons, quiz info icon. On `#0a0a0a`/`#171717` these render at roughly 1.2–1.5:1 contrast — visually absent. The calendar's event affordance (a key academic signal) and its selection indicator are the highest-impact casualties.

### UI-004 — The two-laboratory problem (P1)
Desktop nav shows, adjacently: **Track** (`/tools/laboratory`, page title "Track Attendance") and **Laboratory** (`/laboratory`). Neither name nor URL communicates the split (daily attendance marking vs experiments/practical stats). Compounding it, the dashboard's "Attention Required" card — whose content is attendance risk — links via "View Strategy" to the Track page, which contains no strategy content (must-attend/safe-skip lives in Quiz Eligibility). The label set (Home/Track/Laboratory/Quiz Eligibility/Attendance/History/Calendar/Events) also mixes task verbs ("Track"), object nouns ("Laboratory"), and feature nouns ("Attendance"), and "Attendance" and "Track" are near-synonyms from a student's perspective.

### UI-005 / UI-022 — Failure handling asymmetry (P1/P2)
Three recovery tiers coexist: (a) Retry buttons (Events, Calendar, Notification center, QuizEligibilityCard, Settings), (b) error cards with no action (shared `ErrorState` used by Dashboard, History, Track, Profile), (c) silent partial rendering (Dashboard's analytics overview is dereferenced with `?.` and never checked for error — forecast and weekly series disappear without notice). The most-visited surfaces are in tiers (b) and (c).

### UI-011 — Container-in-container layout (P2)
`AppShell` already provides `mx-auto max-w-5xl p-4 pb-28 md:p-6 lg:p-8`. Every page then wraps itself again: `max-w-7xl px-4 py-8` (Subjects, Laboratory — 7xl is unreachable inside 5xl, so only the extra `px-4` and `py-8` apply), `max-w-4xl py-8` (Quiz, Profile, Feedback), `max-w-2xl py-6` (Track), `max-w-5xl py-6` (Calendar, History, Events). Net effect: mobile gutters vary 16px vs 32px, top padding varies 24px vs 32px, and page content widths are governed by an accident of which max-width happens to be smallest rather than by design.

### UI-012 — One concept, three vocabularies (P2)
- Backend status enums surface raw in dashboard badges (`overall.status ?? "N/A"`, `item.status`) while SubjectAttendanceCard maps the same family to friendly labels.
- Attendance verbs alternate between the enum pair (Attended/Missed — Today card, subject cards) and the colloquial pair (Present/Absent — Track actions, History filters/badges).
- Failure color: token-based `destructive` in dialogs vs raw `text-red-400`/`bg-red-950/20`/`border-red-900/50` in four page-level error treatments.

### UI-019 — Settings that do nothing (P2)
The Settings modal is honest in an 11px footnote: class reminders gate real notifications, but `auto_mark_present` and `week_starts_on` are write-only preferences. The Calendar grid hard-codes Sunday-first (`WEEKDAY_LABELS`), directly contradicting the visible "Week starts on" control. Students have no way to know which settings are real; the default assumption after discovering one inert setting is that all are.

---

## 6. Systemic Design Issues (summary)

| # | Root pattern | Affected surfaces | Likely source | UX consequence |
|---|---|---|---|---|
| S1 | Dead `surface`/`surface2`/`text2` tokens | Laboratory, Quiz Eligibility, Subjects, SubjectLaboratoryView, Quiz card, UserMenu, Profile modal, Overall card | Token set never created; classNames written against an imagined palette | Invisible loading/skeleton states; lost surface hierarchy |
| S2 | `accent` treated as brand color | Calendar (grid + legend), DayDetail, EventRow, Profile, Quiz intro | Token semantics (hover surface) vs usage (visible accent) mismatch | Key indicators/links near-invisible |
| S3 | Shared primitives bypassed | Errors, empties, headers, selects, inputs, date chips | Per-page hand-rolled variants | Cross-page inconsistency; drift compounding |
| S4 | No layout contract between shell and pages | All 11 student routes | AppShell container + per-page containers | Double padding, inconsistent gutters/rhythm |
| S5 | Vocabulary not centralized | Status labels, attendance verbs, filters, dates, percentages | Ad-hoc formatting per component | Same facts look different; translation of enums leaks |
| S6 | Feedback model improvised per feature | Retry patterns, confirmations, success feedback, alerts | No toast/state-feedback layer, no shared ErrorState API | Uneven recovery, unconfirmed destructive actions, silent partial data |

---

## 7. Quick Wins (small localized fixes — NOT implemented)

1. Add `--surface`/`--surface2` tokens (or replace `bg-surface*` classes with `bg-card`/`bg-muted`) — resolves most of UI-001 mechanically. *(UI-001)*
2. Repoint accent-as-color usages to `primary` (or define a real accent color) — resolves UI-002. *(UI-002)*
3. Add a Retry/onRetry prop to shared `ErrorState` and pass `mutate` at Dashboard/History/Track/Subjects. *(UI-005)*
4. Add `not-found.tsx` + `error.tsx` styled with app tokens. *(UI-007)*
5. Replace `window.alert` in events deactivation with the existing inline-banner pattern. *(UI-009)*
6. Add confirmation to "Mark all present" and to lab delete icon buttons. *(UI-006, UI-015)*
7. Copy edits: remove "(PostgreSQL)", "Tracked in task.md", "Ingest", VAPID phasing note; dedupe InstallAppModal paragraphs. *(UI-010)*
8. Route the "View Strategy" CTA to `/tools/quiz-schedule`. *(UI-004 partial)*
9. Show `overall.status`/`item.status` through the same label map SubjectAttendanceCard already uses. *(UI-012 partial)*
10. Add a loading indicator for SW updates (small banner/toast) instead of `console.log`. *(UI-023)*
11. Fix greeting fallback ("Good Morning" without trailing comma / skeleton+error). *(UI-031)*
12. Match manifest `background_color` to `#0a0a0a`. *(UI-037)*

## 8. Larger UX Problems (require design decisions)

1. **Navigation IA rework**: consolidating Track/Laboratory naming, desktop nav density at `md`, and mobile wayfinding (active secondary destinations, page titles) — a single navigation design pass. *(UI-003, UI-004, UI-008)*
2. **Layout contract**: decide per-page vs shell-owned max-width/padding; strip page-level containers. *(UI-011)*
3. **State-feedback architecture**: one toast/banner layer + one ErrorState/EmptyState API with actions; optimistic-vs-blocking policy for notifications. *(UI-005, UI-014, UI-025, UI-026, UI-022)*
4. **Destructive-action policy**: consistent confirmation/undo rules across attendance overrides, bulk marking, lab records, event deactivation. *(UI-006, UI-014, UI-015)*
5. **Design-system consolidation pass**: merge select/input heights into primitives; decide the canonical date/percent formatters; centralize status label maps. *(UI-016, UI-017, UI-018, UI-012, UI-021)*
6. **Settings honesty**: either wire `week_starts_on`/`auto_mark_present` to real behavior or visibly mark them as upcoming. *(UI-019)*
7. **Event form simplification for students**: student-mode form exposing only the essential fields. *(UI-035)*

## 9. Manual Verification Required

| Item | What to verify |
|---|---|
| UI-003 | TopNav at 768px and 1024px (and admin's 9th item): does the nav wrap, clip, or push the header wider than the viewport? |
| UI-001 | Actual rendering of affected skeletons/nested surfaces in a browser (static analysis is unambiguous, but confirm visual effect per surface). |
| UI-002 | Calendar event dots / selection ring / legend visibility on real screens. |
| UI-007 | What an unknown URL and a thrown render error actually display (default Next pages). |
| UI-024 | Ergonomics of 32px filter controls and the 20px switch on a physical phone. |
| UI-034 | EventFormDialog footer reachability on a phone with dynamic browser chrome. |
| AppShell `h-screen overflow-hidden` | iOS Safari address-bar behavior for the fixed shell + bottom nav (100vh vs dvh). |
| SettingsModal browser-notification row | Whether the long "Enable browser notifications" button wraps/overflows its row at ~360px. |
| Calendar at 320px | Grid cell density and DayDetail stacking. |
| Color contrast | Runtime measurement of `text-muted-foreground` (#94a3b8) on `bg-muted/40` chips and `text-[10px]` labels. |

## 10. Recommended Future Remediation Order (planning only — NOT executed)

- **Phase A — Critical correctness of the visual language**: UI-001, UI-002 (tokens), plus UI-007 (error/404 UI).
- **Phase B — Recovery & destructive safety**: UI-005, UI-006, UI-009, UI-015, UI-022, UI-023, UI-026.
- **Phase C — Navigation & mobile wayfinding**: UI-003, UI-004, UI-008 (single navigation design pass).
- **Phase D — Design-system consolidation**: UI-012, UI-016, UI-017, UI-018, UI-021, UI-011 (layout contract), UI-025 (feedback layer).
- **Phase E — Screen-specific UX**: UI-013, UI-014, UI-019, UI-020, UI-024, UI-027–UI-031, UI-033, UI-035, UI-036.
- **Phase F — Polish**: UI-010, UI-028, UI-029, UI-032, UI-034, UI-037–UI-040.

---

*Audit performed per the audit-only protocol: no application, styling, route, copy, backend, or infrastructure code was modified. This document is the sole artifact of this task.*
