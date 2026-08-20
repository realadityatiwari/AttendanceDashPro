# Phase 12 — Mobile / Responsive Experience
## Architecture & Implementation Readiness Audit

> **READ-ONLY AUDIT (2026-08-21).** Phase 11 COMPLETE & FROZEN; Phase 12 NOT STARTED. No source code, backend, database, migration, verifier, or governance file was modified. The only file created is this report.

---

## 1. Current Project Position

- **Phases 0–10:** COMPLETE & FROZEN.
- **Phase 11:** COMPLETE & FROZEN (2026-08-21, `phase_11f_verification_report.md`): 11A read contracts ✅ · 11B persistence ✅ · 11D notification center ✅ · 11E preference wiring ✅ · 11F final verification ✅ — 11A verifier 19/19, 11B verifier 23/23. **11C (delivery model) remains decision-gated/deferred, NOT implemented.**
- **Phase 12:** NOT STARTED — next authorized phase (`MASTER_ROADMAP.md:722`, table row 12).
- **Phase 13+:** NOT STARTED. Phase 13 = PWA / Installability.
- **Governance inconsistency discovered (to fix when Phase 12 work begins — NOT fixed in this audit):** `MASTER_ROADMAP.md:9` ("Next phase: Phase 12 — PWA & Offline") and `walkthrough.md:1069` label Phase 12 as "PWA & Offline", but the roadmap's own Phase 12 section (`MASTER_ROADMAP.md:722`) is **Mobile / Responsive Experience** and Phase 13 owns PWA. The header labels are wrong; the Phase 12 section title is authoritative.

## 2. Authoritative Phase 12 Scope

The roadmap's Phase 12 section (`MASTER_ROADMAP.md:722-740`) is the scope source of truth. It requires a **genuine mobile experience, not a shrunken desktop**, including: mobile navigation, responsive top bar, bottom navigation *where appropriate*, responsive cards, touch targets, mobile date navigation, mobile Track workflow, mobile profile menu, responsive quiz cards, responsive analytics.

Supporting authoritative prior art (legacy spec era, still referenced by the live repo):

- `docs/S4_PRODUCT_SPEC.md:69-74` (§13 Responsive Principles): **Mobile (360–412px)** — thumb-reach optimized, **bottom navigation**, vertical stacking; **Tablet (768–1024px)** — transitional, split views/dense grids; **Desktop (1280–1920px)** — top navigation. Rules: **no horizontal overflow, no clipped content, adequate touch target sizing**.
- `docs/17_AI_HANDOFF.md:41-43` (§7): legacy bottom-nav contract — **exactly four tabs (Dashboard, Subjects, History, Profile); management features live in "Academic Tools" reachable from Profile; never a fifth tab**.
- `docs/16_ROADMAP.md:150`: same "no fifth bottom navigation tab; Academic Tools workspace from Profile" rule.
- `css/responsive.css` (legacy app stylesheet, **not imported by the Next.js app** — dead code, but evidence of prior intent): 5-breakpoint system (320 / 480 / 768 / 1024 / 1440), 44px minimum touch targets on action buttons (`.action-btn { min-height: 44px }`), desktop subject cards hidden on mobile with dedicated mobile cards, a Mark-All-Present **FAB** (`fab-mark`) floating above the bottom nav.
- `implementation_plan.md:39`: "Mobile navigation — nav links hidden below `md`; the mobile navigation pattern is a dedicated later phase (**bottom nav per S4 spec**)." — the live plan already commits to the bottom-nav direction.
- `task.md:28` and `walkthrough.md:177/223`: "Mobile navigation phase (nav currently hidden below `md`)" — flagged as a dedicated later phase.

**Phase 12 is NOT:** a new backend feature, attendance/eligibility/analytics engine work, PWA implementation, offline functionality, push notifications (11C), Firebase retirement (Phase 14), or production deployment.

## 3. Existing Responsive Infrastructure

| Layer | Current state | Evidence |
|---|---|---|
| CSS engine | Tailwind CSS v4 (CSS-first config; `@import "tailwindcss"` in `globals.css`; **no `tailwind.config.*`**; default breakpoints sm=640 / md=768 / lg=1024 / xl=1280) | `globals.css:1-43`; repo has no tailwind config file |
| Media queries | **Zero** `@media` rules in the live app; the only media query anywhere is `(display-mode: standalone)` in `useInstallPrompt.ts:18-30` (PWA-detect, Phase 10D-era) | grep across `src/` |
| Viewport | Next.js App Router injects a default viewport meta (`width=device-width, initial-scale=1`) — no explicit `viewport` export, none needed for correctness | `app/layout.tsx` (no viewport export) |
| App shell | `AppShell`: `h-screen flex-col overflow-hidden`; `<main class="flex-1 overflow-y-auto">`; inner container `max-w-5xl p-4 md:p-6 lg:p-8`. **Note: `overflow-hidden` on the shell clips horizontal overflow silently — nothing scrolls, wide content is cut off** | `components/layout/AppShell.tsx:10-16` |
| Top bar | `TopNav` `h-14`, brand + 8-item nav + bell + user menu; **nav links `hidden md:flex`** — below 768px there is **no navigation at all**; comment: "the mobile navigation pattern is a dedicated later phase" | `components/layout/TopNav.tsx:55,68-71,39-44` |
| Page containers | All authenticated pages use `px-4 ... sm:px-6 lg:px-8` + `mx-auto w-full max-w-*` — consistent, mobile-safe padding | dashboard/calendar/events/history/subjects/profile/laboratory pages |
| Grids | Dashboard `grid-cols-1 lg:grid-cols-2`; Subjects `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`; Calendar `grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px]`; Laboratory `grid gap-4 lg:grid-cols-2` — **single-column on mobile everywhere at the page level** | page sources |
| Rows | Widespread `flex-col sm:flex-row` stacking (history rows, EventRow, SubjectLaboratoryView, PageHeader) | `history/page.tsx:55`, `events/EventRow.tsx:73`, etc. |
| Text overflow | `truncate`, `min-w-0`, `line-clamp-2`, `break-all` used correctly in most list rows | `history/page.tsx:80`, `TrackSessionCard.tsx:177`, `profile/page.tsx:129` |
| Dialogs | Base `DialogContent`: `w-full max-w-[calc(100%-2rem)]` mobile width, footer `flex-col-reverse ... sm:flex-row` (stacks on mobile); `EventFormDialog` adds `max-h-[90vh] overflow-y-auto`; **`ShellDialog` (all six shell modals) has NO max-height/scroll** | `ui/dialog.tsx:56,105`; `events/EventFormDialog.tsx:337`; `shell/ShellDialog.tsx:48` |
| Bottom sheet primitive | `ui/sheet.tsx` exists (side/bottom variants) — currently **unused by any page** — a ready-made mobile primitive for bottom-nav "More" panels | `ui/sheet.tsx:56` |
| Design tokens | Dark-only theme in `globals.css:46-81`; locked primary blue; `--radius` 0.5rem; Geist fonts; no responsive tokens (no fluid type/spacing scale) | `globals.css` |
| Touch targets | **All button sizes < 40px**: default `h-8` (32px), `sm`/`icon-sm` `h-7` (28px), `xs`/`icon-xs` `h-6` (24px), `icon` `size-8` (32px); base buttons `whitespace-nowrap shrink-0` (labels cannot wrap — overflow contributor) | `ui/button.tsx:7-33` |
| PWA hooks | `useInstallPrompt` + `InstallAppModal` exist (beforeinstallprompt capture, honest standalone/userChoice reporting); **no manifest, no service worker, no `next-pwa`** (documented at `implementation_plan.md:37`) — modal is inert until Phase 13 | `hooks/useInstallPrompt.ts`, `shell/InstallAppModal.tsx` |

**Bottom line:** the live app was built mobile-first at the *container level* (single-column grids, stacking rows, consistent padding) but mobile-*specific* UI (navigation, touch sizing, dialogs, dense-data layouts) is almost entirely absent. The legacy `css/responsive.css` from the superseded app documents the intended breakpoints/touch minimums and is not imported.

## 4. Phase 12 Feature Matrix

| Requirement | Current State | Evidence | Gap | Phase 12 Action |
|---|---|---|---|---|
| 1. Mobile navigation | **ABSENT** | `TopNav.tsx:68-71`: nav `hidden md:flex`; no mobile nav exists; below 768px zero destinations reachable except via address bar | No navigation surface below `md` at all | 12A: bottom navigation per S4 (4-tab pattern adapted to current IA) + tools access point |
| 2. Responsive top bar | **PARTIALLY IMPLEMENTED** | `TopNav.tsx:55-66,93-96`: `h-14`, responsive padding, brand + bell + avatar always visible; name hidden `<lg` (`UserMenu.tsx:63`) | Fits 320px today but bell hit area ~32px and avatar 32px; brand text + bell + avatar is the full bar | 12A: compact top bar pass (touch sizing, spacing) |
| 3. Bottom navigation where appropriate | **ABSENT** (live app) | No bottom-nav component exists; legacy contract = exactly 4 tabs (Dashboard/Subjects/History/Profile) + Academic Tools from Profile (`17_AI_HANDOFF.md:41-43`) | Whole pattern missing; current IA has 8 primary destinations (Home, Track, Laboratory, Quiz, Attendance, History, Calendar, Events) | 12A: 4-tab bottom nav (Home, Attendance, History, Profile-anchor) + "More" sheet for secondary destinations; desktop nav untouched |
| 4. Responsive cards | **PARTIALLY IMPLEMENTED** | Cards stack single-column (dashboard/subjects grids `grid-cols-1`); inner fixed grids: history summary `grid-cols-3` (`history:214`), lab stats `grid-cols-4` (`laboratory:167`), subject breakdown `grid-cols-2` (`SubjectAttendanceCard:134`), quiz opt `grid-cols-2` (`QuizEligibilityCard:230`), Track summary `grid-cols-3` (`tools/laboratory:234`), QuizSnapshot `grid-cols-3` (`QuizSnapshotCard:66`); WeeklyAttendanceCard fixed `w-16/w-14` spans | Inner grids cramp at 320px; dense `text-[10px]`/`text-[11px]` labels; Weekly row borderline | 12B/12C: density pass on fixed inner grids (2-col → stack or flexible), spacing/type scale |
| 5. Touch targets | **DEFECTIVE** | Every interactive control < 40px (button.tsx sizes above); calendar day cells ~36px (`CalendarGrid.tsx:121`); bell ~32px (`NotificationBell.tsx:34-40`); notification Read/Dismiss 28px (`NotificationCenter.tsx:242-268`); Quiz "Retry" 24px (`QuizEligibilityCard:113`); Reset buttons `h-7` (history/events); S4 requires "adequate touch target sizing" (`S4_PRODUCT_SPEC.md:74`); legacy used 44px minimums | Systematic below-target sizing | 12A: touch-target sizing pass (mobile-friendly base sizes + `sm:` desktop restore so desktop visuals are untouched) |
| 6. Mobile date navigation | **PARTIALLY IMPLEMENTED** | Track: prev/next `size-8` (32px) + date input `w-40 text-xs` + Today `h-8` (`tools/laboratory:142-168`); Calendar: month nav `icon-sm` (28px) + fixed `w-36` label (`calendar:101-121`); History/Events: date `<Input type="date">` at `h-8 text-sm` | 28-32px arrows; `text-xs`/`text-sm` date inputs → iOS focus zoom; calendar nav crowded | 12B: larger arrows, iOS-safe input font size, calendar nav layout |
| 7. Mobile Track workflow | **PARTIALLY IMPLEMENTED** | `TrackSessionCard`: Present/Absent = two full-width `h-8` halves in `grid-cols-2`, Change `h-7`; Mark All Present full-width `h-8`; summary `grid-cols-3` `text-2xl`; subject `line-clamp-2`; date nav row ≈ 236px fits 288px | Functionally usable; 28-32px targets; 3-col summary cramped; no sticky primary action | 12B: touch sizing + layout polish of mutation controls and summary |
| 8. Mobile profile menu | **PARTIALLY IMPLEMENTED** | UserMenu avatar always visible in top bar; dropdown `w-60` fits 320px; Profile page exists (`/profile`) but is not reachable from mobile nav; ProfileModal/Settings/Feedback use `ShellDialog` **without scroll** | Profile modal + Settings (3 sections + footer) and Feedback (with keyboard) risk clipped content on ≤568px viewports | 12D: ShellDialog max-height + scroll; profile reachability via bottom nav anchor |
| 9. Responsive quiz cards | **PARTIALLY IMPLEMENTED** | `QuizEligibilityCard`: stacks single-column; cycle tabs wrap (`quiz-schedule:60-77`, tabs `h-8`); optimization grid `grid-cols-2`; heavy `text-[10px]` density; "Retry" 24px | Optimization 2-col cramped at 320px; tiny type; tiny retry target | 12C: quiz card density + touch pass |
| 10. Responsive analytics | **PARTIALLY IMPLEMENTED** | Analytics surfaces = dashboard cards (Overall `text-3xl`, Weekly fixed spans, QuizSnapshot 3-col), subject cards (2-col breakdown, `text-3xl` headline), lab stats 4-col; all single-column at page level | Weekly row borderline at 320px; lab 4-col stats cramped; no charts (bars only) — no chart overflow risk | 12B/12C: analytics-card density pass |

## 5. Page-by-Page Mobile Audit

### Dashboard (`app/(authenticated)/dashboard/page.tsx` + `components/dashboard/home/*`)
- **Structure:** greeting + 6 cards in `grid-cols-1 lg:grid-cols-2` — single column on mobile. ✅
- **Failure points:** QuizSnapshotCard 3-col grid (`text-xl` numbers, 10px labels) and WeeklyAttendanceCard fixed `w-16/w-14` spans (progress bar shrinks to ~64px at 320px); AttentionRequired "View Strategy" `h-7`.
- **Overflow risk:** none hard; Weekly row borderline. **Viewport:** OK at 320px. **Navigation:** none on mobile (below `md`). **Cards/grids:** stack fine. **Modals:** none. **Typography:** headline `text-3xl` fine; 10px labels too small. **Touch targets:** footer links `h-7`. **Date nav:** n/a. **Adapt:** in-place class adaptation; no new composition.

### Track — `app/(authenticated)/tools/laboratory/page.tsx` + `components/dashboard/TrackSessionCard.tsx`
- **Structure:** `max-w-2xl` column; date nav row; summary card; session cards stack. ✅
- **Failure points:** date row = 32px arrows + `w-40 text-xs` date input + `h-8` Today (≈236px, fits but cramped at 320px); Present/Absent `h-8`, Change `h-7`; bottom summary `grid-cols-3 divide-x` with `text-2xl` numbers + 10px labels.
- **Overflow risk:** none. **Viewport:** 320px OK. **Navigation:** n/a (reached only via desktop nav today). **Date nav:** small targets; `text-xs` date input → iOS zoom. **Action accessibility:** Mark All Present full-width (good); per-session Change 28px (small). **Adapt:** in-place; possibly sticky Mark-All on scroll.

### History — `app/(authenticated)/history/page.tsx`
- **Structure:** filter grid `grid-cols-1 sm:grid-cols-2 lg:grid-cols-5` (single col mobile ✅); session rows `flex-col sm:flex-row`; summary strip `grid-cols-3 sm:grid-cols-5`.
- **Failure points:** 3-col summary with `text-xl` + 10px labels cramped at ≤360px; filters `h-8` selects/date inputs at `text-sm` (iOS zoom); Reset `h-7`; Load more `h-8`; badges `h-4 text-[10px]`.
- **Overflow risk:** none (`truncate max-w-md` on subject). **Viewport:** OK. **Navigation:** n/a. **Date controls:** `text-sm` date inputs → iOS zoom. **Dense data:** acceptable; strip needs 2×3 arrangement. **Adapt:** in-place.

### Calendar — `app/(authenticated)/calendar/page.tsx` + `components/calendar/CalendarGrid.tsx` + `DayDetail.tsx`
- **Structure:** `grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px]` — grid above detail on mobile ✅; `DayDetail` wraps.
- **Failure points:** **fixed `grid-cols-7` + `aspect-square`** cells ≈ 36px at 320px (< 40px target); in-cell text 9–10px; weekday headers 10px; month nav arrows `icon-sm` (28px); fixed `w-36` month label; "Today" `h-7`.
- **Overflow risk:** none (grid squeezes, `truncate` on cell labels). **Viewport:** 320px usable but dense. **Date navigation:** 28px arrows. **Session density:** per-cell counts at 9px — the densest surface. **Adapt:** in-place; consider slightly larger cells (reduce gap/padding) + ≥40px arrows.

### Events — `app/(authenticated)/tools/events/page.tsx` + `components/events/EventRow.tsx` + `EventFormDialog.tsx`
- **Structure:** filter grid stacks; EventRow stacks (`flex-col sm:flex-row`); manage row keeps button beside text (`min-w-0` protects). ✅
- **Failure points:** admin action row (confirm/cancel/edit/deactivate, all `h-7 px-2 text-xs`) ≈ 212–220px — fits 288px but tight; filters `h-8 text-sm` (iOS zoom); count badge `h-4`.
- **Dialog:** `max-h-[90vh] overflow-y-auto sm:max-w-lg` — **the only dialog with correct mobile scroll** ✅; footer stacks ✅.
- **Overflow risk:** low. **Adapt:** in-place + touch sizing.

### Quiz Eligibility — `app/(authenticated)/tools/quiz-schedule/page.tsx` + `components/quiz/QuizEligibilityCard.tsx`
- **Structure:** cycle tabs `flex-wrap` (✅); subject cards stacked.
- **Failure points:** optimization `grid-cols-2` (Must Attend/Safe Skip ~136px each at 320px); 10px-heavy density (criterion meta, guidance, counts); "Retry" `xs` 24px; "View Calculation" `h-7`.
- **Overflow risk:** low (`min-w-0` + wraps). **Adapt:** in-place density pass.

### Attendance / Subjects — `app/(authenticated)/subjects/page.tsx` + `SubjectAttendanceGrid`/`Card`
- **Structure:** `grid-cols-1 md:grid-cols-2 lg:grid-cols-3` — single column mobile ✅.
- **Failure points:** breakdown `grid-cols-2` blocks (`px-3 py-2.5`, 10px labels); badges `h-5`/`h-4`; DetailRow counts can crowd (`shrink-0` pct); "View Details" `h-7 w-full`.
- **Overflow risk:** low. **Adapt:** in-place.

### Laboratory — `app/(authenticated)/laboratory/page.tsx` (+ `SubjectLaboratoryView.tsx`; `tools/laboratory` is Track)
- **Structure:** stats `grid-cols-4`; experiment list rows stack; ingest form stacks.
- **Failure point — HIGHEST OVERFLOW RISK IN APP:** tab bar `laboratory/page.tsx:93` is `flex` **nowrap** (Practical Attendance / Experiments / Activity ≈ 380px) — at 320px the shell's `overflow-hidden` **clips it with no scrollbar**: tabs unreachable. Must become `overflow-x-auto` (scrollable) or wrapping on mobile.
- **Also:** 4-col stats (`text-xl` numbers) cramped at 320px; trash icon buttons `size-7`; Track/Sign `h-7`.
- **Adapt:** tab bar needs a mobile-safe pattern (horizontal scroll strip or icon tabs); stats 2×2 on mobile.

### Profile / Settings / Feedback / Appearance / Install (`app/(authenticated)/profile/page.tsx` + `components/shell/*`)
- **Page:** stacks cleanly; avatar 96px; `break-all` UID ✅.
- **Modals:** **`ShellDialog` has no `max-h`/`overflow-y-auto`** — Settings (3 sections + footer) and Feedback (textarea + footer, with keyboard) exceed ≤568px viewports and get clipped with no scroll. Feedback textarea `text-sm` (iOS zoom); Settings week-start select `h-7`; buttons `h-8`; close button 28px.
- **Adapt:** shared ShellDialog scroll fix (one place, six modals) + input/control sizing.

### Notifications — `components/notifications/NotificationBell.tsx` + `NotificationCenter.tsx`
- **Bell:** icon 20px + padding ≈ 32px hit area; badge `h-4` 10px — small. **Center:** `ShellDialog width="md"`, list wrapper `max-h-[26rem] overflow-y-auto` (✅ inner scroll) but the dialog body has no scroll — header+list+footer can exceed short viewports; rows `p-3` stack well; Read `h-7` / Dismiss `icon-sm` 28px targets; icon `size-9`.
- **Adapt:** dialog scroll fix (shared), action sizing.

### Auth pages (`(auth)/login`, `(auth)/signup`) — outside AppShell; standard stacked forms; no audit blockers found; not a Phase 12 priority (roadmap scope is the product experience; auth forms already single-column).

## 6. Mobile Navigation Recommendation

**Recommendation: D — hybrid approach: 4-tab bottom navigation on mobile (< `md`) + the existing compact top bar retained above, + a "More" tools surface for secondary destinations. Desktop navigation remains byte-identical.**

Why:

1. **Prior art is explicit and authoritative.** The S4-era contract (`17_AI_HANDOFF.md:41-43`, `16_ROADMAP.md:150`) mandates exactly four bottom tabs — Dashboard, Subjects, History, Profile — with management tools in an "Academic Tools" space reachable from Profile. `implementation_plan.md:39` already commits to "bottom nav per S4 spec".
2. **The current IA maps onto the S4 pattern with one adaptation.** Live destinations: Home (`/dashboard`), Attendance (`/subjects`), History (`/history`) map 1:1 to three S4 tabs. The fourth S4 tab, Profile, is today both a page (`/profile`) and the avatar/user menu — the user menu already hosts Profile, Appearance, Install, Feedback, Settings, Sign Out, Notifications.
3. **Secondary destinations (Track, Laboratory, Quiz Eligibility, Calendar, Events) must not become additional tabs** (S4: never a fifth tab). They belong in a "More" surface — a bottom sheet (`ui/sheet.tsx` already exists, unused) opened from the Profile tab or a compact "More" affordance — mirroring S4's "Academic Tools from Profile" concept. This preserves thumb-reach (4 fixed primary tabs) while keeping all 8 destinations one tap away.
4. **Desktop must not change:** `TopNav`'s `hidden md:flex` already gates the desktop nav; the bottom nav component would be `md:hidden`. The existing top bar stays on mobile as a compact brand + bell + avatar strip.

**Primary mobile destinations (bottom nav):** Home, Attendance, History, Profile/menu anchor (4 tabs, S4 rule).
**Secondary mobile destinations ("More" sheet):** Track, Laboratory, Quiz Eligibility, Calendar, Events, plus the shell modal shortcuts.
**Desktop:** unchanged 8-item top nav + bell + user menu.

## 7. Responsive Architecture Recommendation

**Recommendation: D — hybrid: (1) CSS/responsive adaptation of existing components as the primary mechanism, (2) a small set of mobile-specific shared compositions, (3) no separate mobile page implementations.**

Evidence:

- **Adaptation is sufficient for the majority of surfaces.** Every page already stacks to a single column below `md`; the audit found no page whose information architecture requires a separate mobile page. The failures are class-level (touch targets, fixed inner grids, tab-bar nowrap, dialog scroll, iOS-zoom inputs) — all fixable in place.
- **Mobile-specific compositions needed (new components):** a bottom nav bar + "More" bottom sheet (navigation is genuinely absent today), and possibly a sticky Mark-All-Present action for Track. These are additive components, not page rewrites.
- **Shared primitives to change once:** `ui/button.tsx` size tokens (mobile base sizes + `sm:` desktop restores), `ShellDialog` scroll fix, `ui/dialog.tsx` max-height safety, input font sizing policy (iOS zoom).
- **Protected by design:** backend contracts, attendance/eligibility/calendar/analytics engines, notification backend, DB, and frozen desktop behavior are untouched. Phase 12 is a **frontend presentation/responsive phase**; the audit found no repository evidence requiring backend work (§9).

## 8. Design System Compatibility

The frozen Phase 1 visual language (dark-only, locked primary blue, `--radius` tokens, Geist) can fully support mobile **without redesign**:

- **Breakpoints:** Tailwind v4 defaults (sm 640 / md 768 / lg 1024 / xl 1280) align with the S4 splits at 768/1024. The S4 480px "large phone" tier is approximated by `sm` (640) — acceptable; a single custom `max-[480px]` variant can cover the 320–479 tier if density fixes need it. Do **not** recreate the legacy 5-breakpoint CSS system.
- **Spacing:** existing `p-4 / md:p-6 / lg:p-8` rhythm is already responsive; keep it.
- **Typography:** no fluid type system exists; 10px/11px labels are the main mobile problem — Phase 12 should set a mobile minimum (≥11–12px) for informational text in dense surfaces, and 16px on all inputs/selects (iOS zoom rule: `text-base` on mobile, `md:text-sm` desktop — the base `Input` already does this correctly at `input.tsx:12`; the violations are the call-site `text-sm`/`text-xs` overrides listed in §4/§5).
- **Card density:** inner fixed grids (2-col/3-col/4-col) get flexible or stacked variants below `sm`; card padding stays token-based.
- **Button sizing / touch minimums:** adopt the S4/legacy minimum (44px legacy, 40px practical floor). Implement as base sizes (mobile) with `sm:` variants restoring today's exact desktop sizes — **zero desktop visual change**, no new design tokens invented.
- **Modal behavior:** base dialog gains a safe `max-h` + `overflow-y-auto` policy; bottom sheets remain the primitive for "More".
- **Navigation behavior:** bottom nav only below `md`; hidden on tablet+ per S4 (768+ uses top nav / transitional layouts).
- **Overflow strategy:** the shell's silent clip (`overflow-hidden`) stays, but every content surface must be made overflow-safe (tab bar scroll, wrapping rows, flexible grids) — the S4 rule "no horizontal overflow, no clipped content".

## 9. Backend / Database Dependency Audit

**NO BACKEND CHANGE REQUIRED.** Evidence per surface:

| Surface | Backend contract consumed | Mobile UI need | Backend gap? |
|---|---|---|---|
| Dashboard | `GET /api/v1/dashboard/summary` + analytics overview (8.1 read model) | single-column cards | None |
| Track | session/attendance CRUD + mutation endpoints (canonical attendance path) | date nav + mutation buttons | None |
| History | history read model + filters/search/pagination query params | stacked rows + filters | None |
| Calendar | calendar read model (month + day) | month nav + day cells | None |
| Quiz Eligibility | eligibility read model (7.x contract, extended payload) | card density | None |
| Analytics | analytics overview (8.1) | cards | None |
| Notifications | `GET /api/v1/notifications`, `PATCH` (11A/11B contracts) | rows + actions | None |
| Profile/Settings/Feedback | `/student/profile`, `/student/preferences` GET/PUT, feedback POST | modal scroll | None |

The mobile UI is a pure client-side presentation concern over existing REST contracts. No schema, engine, read-model, or contract change is required; **no migration, no verifier change, no backend code change.**

## 10. Phase 13 Boundary

**Phase 13 (PWA / Installability) owns:** web manifest, service worker, icons, install prompt, standalone detection, offline strategy, cached app shell, online/offline states (`MASTER_ROADMAP.md:743-756`).

**Phase 12 must NOT implement:** manifest, service worker, offline caching, install prompts, standalone-mode behavior, or offline data architecture. The repo's existing `useInstallPrompt` hook and `InstallAppModal` (Phase 10D-era, honest modal that reports real `userChoice`/`display-mode` states; `implementation_plan.md:37` documents that no PWA substrate exists) are **kept as-is and not extended**. Phase 12's media-query needs are purely viewport/breakpoint CSS; the single existing `display-mode` query belongs to the PWA surface and is untouched.

## 11. Proposed Phase 12 Sub-Phases

Evidence-based sequence (each sub-phase is additive, desktop-visible output unchanged, backend untouched):

### 12A — Responsive foundation + mobile navigation (first, smallest)
- **Objective:** restore navigation below `md`; make the shared shell mobile-safe; establish the touch-target policy.
- **Files/components:** new `components/layout/MobileBottomNav.tsx` (+ "More" bottom sheet, reusing `ui/sheet.tsx`); `AppShell.tsx` (render bottom nav, safe-area padding); `TopNav.tsx` (compact mobile strip polish); `ui/button.tsx` (mobile base sizes + `sm:` desktop restores); `ui/dialog.tsx` + `ShellDialog.tsx` (max-height + scroll safety); `app/layout.tsx` (explicit `viewport` export if desired).
- **Dependencies:** none. **Must remain untouched:** all page components, backend, DB, `TopNav` nav items/desktop markup.
- **Verification:** `tsc --noEmit`, ESLint (changed files), `npm run build`; manual: all 8 destinations reachable at 360px; desktop nav visually byte-identical ≥768px.
- **Backend/DB:** none.

### 12B — Core page responsiveness (Track, Dashboard, Calendar)
- **Objective:** mobile Track workflow, date navigation, dashboard/analytics cards, calendar usability.
- **Files:** `tools/laboratory/page.tsx`, `TrackSessionCard.tsx`, `dashboard/home/*` (QuizSnapshot, WeeklyAttendance), `calendar/page.tsx`, `CalendarGrid.tsx`, `DayDetail.tsx`; date-input font-size fixes.
- **Dependencies:** 12A (button/dialog policy). **Untouched:** all backend; frozen engines.
- **Verification:** static gates + manual: mark present/absent/mark-all at 360px; month nav; no iOS zoom on date inputs.
- **Backend/DB:** none.

### 12C — Data-heavy pages (Laboratory, Subjects, Quiz, Events)
- **Objective:** fix the tab-bar overflow risk, dense grids, admin actions.
- **Files:** `laboratory/page.tsx` (tab bar overflow-safe), `SubjectAttendanceCard.tsx`, `QuizEligibilityCard.tsx`, `events/page.tsx`, `EventRow.tsx`.
- **Dependencies:** 12A/12B. **Untouched:** all backend.
- **Verification:** static gates + manual at 320px: no horizontal overflow anywhere; tabs reachable.
- **Backend/DB:** none.

### 12D — Dialogs / profile / settings / notifications
- **Objective:** mobile profile menu reachability (bottom nav anchor), shell-modal scroll, notification actions.
- **Files:** `ShellDialog.tsx` (if not fully covered in 12A), `SettingsModal.tsx`, `FeedbackModal.tsx`, `NotificationCenter.tsx`/`NotificationBell.tsx`, `UserMenu.tsx`.
- **Dependencies:** 12A. **Untouched:** notification API contracts.
- **Verification:** static gates + manual: Settings/Feedback scroll fully with keyboard open at 360×640.
- **Backend/DB:** none.

### 12E — Mobile polish + verification
- **Objective:** type/density sweep (10px-text minimums), touch-target sweep, overflow audit, verifier.
- **Files:** residual call sites; a static-invariant verifier (e.g., `backend/scripts/verify_phase_12*.py` mirroring the established phase-verifier pattern) asserting the Phase 12 invariants that are checkable without a browser (viewport export present, bottom nav gated below `md`, no new fixed-width grids / tiny interactive sizes introduced in Phase 12 files).
- **Dependencies:** 12A–12D. **Untouched:** all backend contracts; frozen engines.
- **Verification:** full static gate set + manual matrix (below).
- **Backend/DB:** none.

### 12F — Freeze
- **Objective:** final verification + freeze; governance reconciliation (four docs + phase 12 report), mirroring the 11F pattern (verifier re-run, DB untouched, HARD STOP, user commits).
- **Backend/DB:** none.

## 12. Smallest Safe First Slice

**Proposed first slice: 12A-slice — "Restore mobile navigation + make the shell mobile-safe".**

Scope (minimum viable, visible improvement):

1. New `MobileBottomNav` component (`md:hidden`): Home, Attendance, History + Profile-anchor (4 tabs per S4), plus a "More" bottom sheet (reusing the existing, unused `ui/sheet.tsx`) exposing Track, Laboratory, Quiz Eligibility, Calendar, Events.
2. `AppShell` renders it with safe-area bottom padding.
3. `ShellDialog` + base dialog gain `max-h` / `overflow-y-auto` (clipped-modal fix, six modals at once).
4. Touch-target policy applied to the shell's own controls (bell, avatar, bottom-nav items ≥40px hit area) — scoped so desktop sizes are restored via `sm:` variants.

Why it is the safest first slice:

- **Additive, not corrective:** a new component plus two shared-primitive fixes; no page logic, data flow, hook signature, or API contract changes. Zero backend, zero DB, zero migration, zero verifier change.
- **Fixes the worst real defect first:** below `md` the app is currently *unnavigable* (TopNav nav is `hidden md:flex`) and shell modals can clip — both are structural, affect every surface, and are independent of the per-page density work.
- **Desktop risk ≈ 0:** the bottom nav is `md:hidden`; desktop nav markup is untouched; `sm:`-restored button sizes keep today's desktop visuals byte-identical; the dialog change only adds a scroll when content exceeds the viewport (EventFormDialog already proves the pattern).
- **Immediately testable:** one manual pass at 360px (all 8 destinations reachable, modals scroll) validates the entire foundation before any page-level work.
- **Everything else genuinely depends on it:** 12B–12D touch-sizing and reachability work assumes navigation exists and the touch policy is established.

## 13. Verification Strategy

**STATIC VERIFICATION (agent-run; mirrors established Phase 11 gates):**

- `npx tsc --noEmit` — 0 errors.
- ESLint on Phase 12 changed files — 0 errors/warnings (whole-tree ESLint debt in non-Phase-12 files stays backlog, untouched).
- `npm run build` — all routes prerendered.
- A Phase 12 static-invariant verifier (12E) asserting what is checkable without a browser: viewport export present in `app/layout.tsx`; bottom-nav component gated `md:hidden`; no new `grid-cols-[234]` fixed counts or `h-[6-7]`/`size-[6-7]` interactive sizes introduced in Phase 12-changed files; `text-xs`/`text-sm` absent from `type="date"` inputs in Phase 12-changed files.

**RESPONSIVE VERIFICATION (manual — the USER performs browser testing; the agent only defines the checklist):**

- Narrow mobile 320px: no horizontal scroll anywhere; no clipped content (esp. Laboratory tab bar); all 8 destinations reachable; modals fully scrollable.
- Mobile 360–412px: bottom nav thumb-reach; Track mark-present/absent/mark-all; date nav; calendar month nav; dense-card readability.
- Tablet 768–1023px: top nav reappears (S4 transitional layouts); two-column surfaces sane.
- Desktop regression 1024–1920px: **desktop visuals unchanged** (nav, cards, buttons, dialogs byte-identical); no `sm:`-restore leaks.

**FUNCTIONAL VERIFICATION (manual — user):** navigation (all destinations, back behavior, active state), Track (mutation + mark-all + date change), History (filters/search/load-more), Calendar (month/day/events), Quiz (cycle tabs, retry), Analytics cards, Notifications (read/dismiss/unread count), Profile/Settings (save flows, modal scroll with keyboard open).

## 14. Frozen-System Protection

Phase 12 must NOT modify:

- **Backend engines/services:** attendance engine, eligibility engine, calendar/event engine (`event_session_service.py`), analytics read models, notification backend (11A/11B/11D).
- **PostgreSQL schema / alembic:** no migration, no table, no index.
- **Phase 6–11 contracts:** API payloads, `frontend/src/types/api.ts` types, `hooks/useApi.ts` signatures, notification GET/PATCH semantics, preference GET/PUT semantics.
- **Authentication:** Firebase/JWT flow, `AuthContext`.
- **Canonical attendance mutation path:** the Track mutation flow's data path is untouched; only its presentation classes may change.
- **Frozen desktop behavior:** desktop nav, desktop button sizes (restored via `sm:` variants), desktop layouts.

"Responsive presentation change" vs "functional reopening" — the rule for Phase 12:

- **Allowed (responsive presentation change):** adding/altering Tailwind classes, responsive variants, new mobile-only components (bottom nav, More sheet), dialog scroll safety, spacing/type density, touch-target sizing, safe-area handling, viewport export. All purely presentational; no behavior/data semantics change.
- **Forbidden (functional reopening):** changing any mutation semantics (attendance marking, mark-all, dismissal, read state), re-ordering/re-scoping data payloads, adding endpoints or query params, altering SWR keys/cache semantics, changing auth behavior, or any desktop-visible layout/behavior change at ≥768px.

## 15. Governance Reconciliation Required Later

**NOT performed in this audit** (hard constraint). When Phase 12 implementation begins and at each sub-phase completion, update all four governance documents per the project rule (status, concise description, implementation state, verification state, next authorized slice), plus write `docs/phase_12/phase_12*_report.md` per sub-phase and the final freeze report:

- `MASTER_ROADMAP.md` — **fix line 9 "Next phase" label** (currently "PWA & Offline" — must read "Mobile / Responsive Experience"); table row 12 status; §Phase 12 section status + 12A–12F bullets; ensure Phase 13 header stays PWA-owned.
- `implementation_plan.md` — Phase 12 section (status header + sub-phase entries); update line 39 (mobile navigation note → delivered-by-12A); Phase 11C deferred note unchanged.
- `task.md` — Phase 12 section with checklist; update line 28 (mobile navigation → 12A); whole-tree ESLint backlog item unchanged.
- `walkthrough.md` — **fix line 1069 label** ("Phase 12 — PWA & Offline" → "Mobile / Responsive Experience"); add Phase 12 walkthrough sections; 11F-era status line updated.

## 16. Final Readiness Verdict

**READY FOR ONLY A PHASE 12 SUB-PHASE — specifically 12A (responsive foundation + mobile navigation).**

Rationale:

- **No blockers.** No backend dependency, no schema dependency, no PWA dependency, no product-decision blocker: the S4 4-tab bottom-nav precedent, the `implementation_plan.md:39` commitment, and the current IA jointly determine the navigation design. The only open choice (exact secondary-destination grouping in the "More" sheet) is an implementation detail, not a blocker.
- **Not uniformly ready for "Phase 12 as a whole" in one pass.** The audit found systematic, cross-cutting gaps (all touch targets < 40px; no mobile navigation; shell dialogs unscrollable; Laboratory tab-bar clipping; iOS-zoom inputs; fixed inner grids at 320px). These are deterministic, evidence-backed, and sequenced in §11 — hence the sub-phase structure with 12A first.
- **The smallest safe first slice (§12) is well-bounded, additive, desktop-risk-free, and produces an immediately visible improvement** (navigation restored, modals scrollable).

## 17. HARD STOP

This was a READ-ONLY audit. Nothing was implemented:

- No application source code modified (backend or frontend).
- No database access performed at all (no SELECT, no mutation).
- No migration created or modified; alembic untouched.
- No verifier modified.
- No governance document modified (`MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md` untouched).
- No commit made.
- No Phase 11C reopened; no Phase 13 started.
- The only file created: `docs/phase_12/phase_12_architecture_audit.md`.

**PHASE 12 ARCHITECTURE AUDIT COMPLETE — HARD STOP.**

No Phase 12 implementation performed.
No frozen phase functionally reopened.
No database mutation performed.
No migration created.
No governance files modified.
No commit made.