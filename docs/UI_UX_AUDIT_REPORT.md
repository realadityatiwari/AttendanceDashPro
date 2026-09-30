# AttendanceDash Pro — UI/UX Audit Report

**Date:** 2026-09-29
**Scope:** Student-facing Web/PWA experience (Next.js 16 / React 19 / Tailwind 4 / Base UI frontend) at `frontend/src`, audited at runtime against the live local stack (frontend `:3100`, backend `:8300`, PostgreSQL `:55432`).
**Mode:** READ-ONLY audit. No code, styling, or data files were modified. One throwaway runtime test account (`2401220999001` — "UI Audit Runner") was created through the app's own signup flow to exercise authenticated surfaces; existing data was untouched.
**Viewports tested:** 1440×900 (desktop), 768×1024 (tablet), 375×812 (mobile).
**Reference:** An older audit exists at `docs/S3.5_UI_UX_AUDIT.md`, but it describes the pre-Next.js (Firebase/Firestore) application and is not applicable to the current codebase.

**Legend:** ✔ = runtime-verified in the browser · ▤ = code-inspected only (state not reachable naturally at runtime) · ⚠ = unverified observation

---

## 0. ISSUE INVENTORY

Severity scale: **Critical** = breaks trust in core data or blocks a primary flow · **High** = significant usability/comprehension failure or visibly broken UI · **Medium** = real inconsistency/friction that degrades polish · **Low** = minor refinement.

Frequency: *isolated* (one surface) · *repeated* (same pattern on several surfaces) · *systemic* (design-system-level, many surfaces).

---

### CRITICAL

**UIA-001 — History headline "83% overall" is a recorded-only number presented as an overall percentage**
- **Page/route:** `/history` · **Component:** Semester sessions summary card (`frontend/src/app/(authenticated)/history/page.tsx:207`)
- **Category:** Information hierarchy / UX copy / Data comprehension
- **Problem:** The card shows a large "**83% overall**" directly beside stat tiles reading `286 TOTAL · 5 PRESENT · 1 ABSENT · 280 PENDING`. The 83% is `5/(5+1)` — a *recorded-only* percentage. No qualifier, tooltip, or explanation exists on this surface.
- **Why it is a problem:** A student scanning the page reads "83% overall" while having attended 5 of 286 sessions. On an attendance-tracker whose whole purpose is eligibility awareness, the most prominent number on the History page materially misrepresents the student's state. The app itself elsewhere insists "percentages are recorded-only — pending sessions are never treated as absent" (subjects detail view), so the semantics are intentional, but the *labeling* here hides it.
- **User impact:** Severe miscomprehension; false reassurance; erodes trust when the number conflicts with the Quiz Eligibility page (which shows 0.0% for the same data).
- **Severity:** Critical · **Frequency:** repeated (same semantics drive the dashboard "Overall Attendance" card — see UIA-014)
- **Evidence:** ✔ Runtime screenshot at 1440×900: "83% overall" + "286 TOTAL / 280 PENDING". Root cause confirmed in code.
- **Recommended direction:** Label it ("83% of recorded"), or add a sub-caption "of 6 recorded sessions", and/or show the pooled-with-pending figure as secondary. Solve globally: one shared "percentage basis" caption pattern used by History + Dashboard + Lab.
- **Related:** UIA-014, UIA-036.

**UIA-002 — Settings modal reports "You have unsaved changes" (with an enabled, no-op Save) the moment it opens**
- **Page/route:** Shell → user menu → Settings (all routes) · **Component:** `frontend/src/components/shell/SettingsModal.tsx:97-101, 364-374`
- **Category:** Interaction UX / Form state
- **Problem:** `dirty` is computed as `draft?.field !== preferences.field`. When no edit has been made, `draft` is `null`, so every comparison is `undefined !== value` → `dirty === true`. The footer therefore shows "You have unsaved changes" with **Discard** and **Save** enabled before the user touched anything. Clicking Save with `draft === null` returns early and does nothing — an enabled button that silently no-ops.
- **Why it is a problem:** A false dirty state on every open trains users to distrust the control and invites pointless saves; the enabled-but-inert Save is a broken affordance.
- **User impact:** Every user, every time the modal opens. Confusion, accidental discard anxiety, loss of confidence in the settings surface.
- **Severity:** Critical · **Frequency:** system-wide (single component, but universal exposure)
- **Evidence:** ✔ Runtime screenshot: footer shows "You have unsaved changes" immediately on open; ▤ code root cause at lines 97-101 (`draft?.` optional-chaining against a `null` draft).
- **Recommended direction:** `const dirty = !!draft && (...comparisons...)`. Local fix in one file; add a guard so Save is disabled when `!draft`.
- **Related:** UIA-020 (Settings row layout).

---

### HIGH

**UIA-003 — Internal/developer terminology exposed in student-facing page copy (systemic)**
- **Pages:** `/laboratory`, `/tools/quiz-schedule`, `/tools/events`, `/subjects`, `/profile`, Appearance & Settings modals, signup
- **Category:** UX copy
- **Problem (exact strings, all runtime-verified):**
  - `/laboratory` subtitle: "…all values are **backend-derived from the canonical attendance pipeline**."
  - `/tools/quiz-schedule` subtitle: "Eligibility per the institutional attendance criteria — **evaluated by the backend** from your actual attendance."
  - `/tools/events` Manage-events card: "Add extras, cancellations, or surprise quizzes for your subjects. **The server enforces enrollment and event rules.**"
  - Appearance modal info box: "Light and System themes need a light palette in the **Phase 1 design tokens** …; the preference will be **persisted once switching is implemented**."
  - Signup helper: "…the **server verifies your selection** against it."
  - Profile modal field tooltip (code): "**Not available in the backend data model**" (`ShellDialog.tsx:106`).
  - Settings save-failure path: "The **backend** did not accept the request." (`SettingsModal.tsx:122`)
  - `/profile`: raw auth UUID shown as "**Account Identifier**" (see UIA-007).
- **Why it is a problem:** These are architecture statements, not user value. Students don't know what a "backend", "server", or "design token" is; the copy reads unfinished and undermines confidence.
- **User impact:** Perception of an engineering tool rather than a product; increased cognitive load at exactly the moments users need orientation.
- **Severity:** High · **Frequency:** systemic (8+ surfaces)
- **Recommended direction:** Rewrite in outcome language ("Your attendance is calculated from recorded classes only"; "Only Dark mode is available right now"; "Not recorded yet"). Global copy pass with a banned-terms list (backend, server, pipeline, tokens, surface, enforce).

**UIA-004 — The raw pooled-attendance formula is printed on every subject card (three different phrasings across surfaces)**
- **Pages:** `/subjects` (every theory card + detail view), `/tools/quiz-schedule` (every subject card, uppercase, + inside View Calculation)
- **Category:** Visual consistency / Information hierarchy / UX copy
- **Problem:** `Combined attendance = (Lecture Present + Tutorial Present) / (Lecture Conducted + Tutorial Conducted) × 100` appears as body text on every theory card on `/subjects`; on `/tools/quiz-schedule` it appears **again** in UPPERCASE on every card header ("CRITERION I WINDOW COUNTS · COMBINED ATTENDANCE = …") and a third time inside each Criterion row ("Formula: …"). `/subjects` additionally uses two other phrasings ("No tutorials — subject average equals Lecture %", "Percentages are current and recorded-only — pending sessions are never treated as absent.").
- **Why it is a problem:** The same constant formula repeated 10+ times per page is noise, competes with actual per-subject data, wraps to 3 lines, and the uppercase variant is hard to read. Three phrasings for one concept is drift.
- **User impact:** Visual clutter; the formula becomes wallpaper; students who need the definition can't find it as a single authoritative explanation.
- **Severity:** High · **Frequency:** repeated
- **Evidence:** ✔ screenshots both pages; ▤ `SubjectAttendanceCard.tsx:143-147`, `QuizEligibilityCard.tsx` caption + `CriterionRow` formula row.
- **Recommended direction:** One sentence per page ("Combined = (L+T present) / (L+T conducted)"), or a single ⓘ help popover; never uppercase. Global (shared component/tooltip).
- **Related:** UIA-006 (status-vocabulary drift).

**UIA-005 — Mobile IA buries the core daily action: "Mark Attendance" is not in the bottom tab bar**
- **Page/route:** Mobile shell (all pages) · **Component:** `frontend/src/components/layout/navItems.ts:73` (`MOBILE_TAB_HREFS = ["/dashboard", "/subjects", "/history"]`), `MobileBottomNav.tsx`
- **Category:** Product UX / Navigation / Mobile-PWA
- **Problem:** The bottom bar is Home · Attendance (→ `/subjects`, a per-subject analytics page) · History · More. Marking today's attendance (`/tools/laboratory`) — the single most frequent action in the product — lives inside the **More** sheet. On desktop it is the second item in the top nav.
- **Why it is a problem:** The mobile mental model inverts priority: the analytics surface gets a permanent tab while the daily task needs More → two taps. The tab labeled "Attendance" also *sounds* like the marking action, so users will tap it expecting to mark.
- **User impact:** Extra friction on the highest-frequency flow, daily, for every mobile/PWA user.
- **Severity:** High · **Frequency:** system-wide (mobile/PWA)
- **Evidence:** ✔ 375×812 runtime; ▤ code confirmed.
- **Recommended direction:** Swap tabs to Home · Mark Attendance · History (+ More), or give `/subjects`-tab a prominent "Mark today" CTA. Local to `navItems.ts` + visual confirmation.

**UIA-006 — Attendance-status vocabulary drift (systemic)**
- **Pages:** Dashboard, `/subjects`, `/tools/quiz-schedule`, `/history`, Mark Attendance
- **Category:** Design-system drift / UX copy
- **Problem:** The same conceptual states render with different words per surface:
  - Overall status: **Healthy / Watch / Critical** (`statusLabels.ts`) on dashboard;
  - Per-subject health: **Healthy / Watch / At Risk / Critical** (`SubjectAttendanceCard.tsx:19-24`) — adds "At Risk", and both CRITICAL and AT_RISK map to red (solid vs soft — distinguished only by fill intensity);
  - Quiz states: **Eligible / Recoverable / Not Eligible / Unresolved** (`QuizEligibilityCard.tsx:14-19`);
  - Criterion rows: **PASS / FAIL**;
  - Dashboard quiz snapshot stat: **"Attention"** (amber);
  - History detail rows use "**N missed**" (`SubjectAttendanceCard.tsx:244`) while the canonical vocabulary is Present/Absent (`status.ts` D-07);
  - Unmarked sessions are labeled "**Pending**" forever, including weeks-old rows in History.
- **Why it is a problem:** Seven overlapping vocabularies for overlapping concepts. A student cannot build a stable mental model of "how am I doing?" when the same state is "Watch" on one page, "At Risk" on another, "Recoverable" on a third and "Attention" on a fourth.
- **Severity:** High · **Frequency:** systemic
- **Evidence:** ▤ code (all mappings quoted); ✔ runtime rendering of each variant.
- **Recommended direction:** One canonical status set with fixed labels, colors and icons at design-system level (e.g. `Healthy / At Risk / Critical` for health; `Eligible / Recoverable / Not eligible` only inside Quiz); delete per-component label maps.

**UIA-007 — Profile page exposes a raw internal UUID to students**
- **Page/route:** `/profile` · **Component:** `frontend/src/app/(authenticated)/profile/page.tsx:128-129`
- **Category:** UX copy / Information hierarchy
- **Problem:** "Authentication Identity" card renders `{user?.id}` (e.g. `fc9b5093-ff46-43b6-a6d7-329921913ca3`) under the label "ACCOUNT IDENTIFIER".
- **Why it is a problem:** A database key has zero meaning to a student; it reads as debug output and makes the page feel unfinished. The card itself ("Authentication Identity") is an internal concept.
- **Severity:** High (copy/IA) · **Frequency:** isolated
- **Evidence:** ✔ runtime screenshot; ▤ code line quoted.
- **Recommended direction:** Remove the card or replace with something meaningful (member since / section). Local.

**UIA-008 — Students can reach `/tools/feedback` and get a raw authorization error**
- **Page/route:** `/tools/feedback` · **Component:** page + `ErrorState` (`frontend/src/app/(authenticated)/tools/feedback/page.tsx`)
- **Category:** Product UX / Error states / IA
- **Problem:** `/tools/feedback` is the **admin** feedback-review surface placed inside the student `(authenticated)/tools` route group. Students (no nav link) who deep-link or browse history land on a page title "Feedback" with an error panel: "**Failed to load data** — You do not have access to the feedback admin surface."
- **Why it is a problem:** The message is misleading (nothing "failed to load" — access is denied) and uses internal vocabulary ("feedback admin surface"). The page shouldn't render for students at all; it should redirect or show a branded "not available" state. Code comments acknowledge the nav gate is "UX only".
- **Severity:** High · **Frequency:** isolated (deep-link only)
- **Evidence:** ✔ runtime screenshot as a student account; ▤ page code.
- **Recommended direction:** Route-level role check that redirects students to `/dashboard` (or a friendly 403); retitle. Local.
- **Related:** UIA-030 (role-gated nav pattern).

**UIA-009 — Greeting truncates the display name to its first word ("Good Morning, UI")**
- **Page/route:** `/dashboard` (all viewports) · **Component:** `frontend/src/components/dashboard/home/GreetingHeader.tsx:12`
- **Category:** UX copy / Data handling
- **Problem:** `display_name.split(" ")[0]` renders "Good Morning, UI" for the name "UI Audit Runner"; for real students with multi-part names whose first token is an initial or family name (common in the target population), the greeting addresses them wrongly.
- **Severity:** High (visible on the product's most personal surface) · **Frequency:** repeated (every login, every viewport)
- **Evidence:** ✔ runtime (desktop, tablet, mobile); ▤ code line.
- **Recommended direction:** Use the full display name, or let profile data carry a preferred first name. Local.

**UIA-010 — Settings "Browser notifications" row is visibly broken at default modal width**
- **Page/route:** Shell → Settings · **Component:** `SettingsModal.tsx:180-261`
- **Category:** Layout / Visual consistency
- **Problem:** The row pairs a long body-copy column (`min-w-0`) with a `shrink-0` action button labeled "Enable push notifications" inside a `max-w-sm` dialog. The text column collapses to ~8 characters wide, wrapping one word per line, with the button crowding the icon.
- **Severity:** High (a primary settings row renders broken) · **Frequency:** isolated (default permission state)
- **Evidence:** ✔ runtime screenshot; ▤ code (row structure quoted).
- **Recommended direction:** Stack the action under the text (or shorten the label to "Enable"); give the row `flex-wrap`. Local.

**UIA-011 — Raw ISO date ranges and mixed date formats across surfaces**
- **Pages:** Dashboard (This Week card), `/tools/laboratory` (view-only banner), `/history` + `/calendar` subtitles
- **Category:** UX copy / Visual consistency
- **Problem:**
  - This Week header renders `{week_start} → {week_end}` = "**2026-09-28 → 2026-10-04**" while every other date on the same screen reads "29 Sep 2026" (`WeeklyAttendanceCard.tsx:34`; the codebase already defines canonical `formatDateMedium` D-09).
  - Mark Attendance future-date banner: "View-only — attendance unlocks on **2026-09-30**" directly under a header reading "Wednesday · 30 Sep 2026" (`tools/laboratory/page.tsx:247`).
  - History/Calendar subtitles use a different pattern again ("Semester **Wednesday 15 Jul 2026 – Thursday 31 Dec 2026**" — weekday glued to date, no separator) vs the "Tuesday · 29 Sep 2026" greeting pattern.
- **Severity:** High (dates are the app's primary axis; three formats coexist on single screens) · **Frequency:** repeated
- **Evidence:** ✔ runtime all three; ▤ code lines.
- **Recommended direction:** Route every displayed date through `lib/date.ts` helpers; add an ISO→medium helper for backend ranges. Global sweep.

**UIA-012 — Quiz Eligibility "Must attend / Safe skip" numbers contradict the visible pending count**
- **Page/route:** `/tools/quiz-schedule` → View Calculation · **Component:** `QuizEligibilityCard.tsx` CriterionRow
- **Category:** Product UX / Comprehension
- **Problem:** Card header reads "Lecture · 0/6 attended · **6 pending**", yet the expanded calculation shows "**Must attend: 13 lectures** · Safe skip: 4 lectures" (Criterion II counts from semester start). Two adjacent stat boxes then pair "MUST ATTEND — CRITERION I: 5" with "SAFE SKIP — CRITERION II: 4" — different windows in parallel, with no single "what do I do?" number.
- **Why it is a problem:** 6 pending but "must attend 13" is arithmetically coherent (different denominators) but experientially contradictory; the actionable minimum across criteria is never surfaced.
- **Severity:** High · **Frequency:** repeated (every below-threshold subject)
- **Evidence:** ✔ runtime screenshot.
- **Recommended direction:** Lead with one number ("Attend your next 5 lectures to reach 75%"), and label each box with its window. Local to the card.

---

### MEDIUM

**UIA-013 — Unauthenticated visit to a protected route flashes the full authenticated shell before redirecting**
- **Route:** `/dashboard` (any protected route) · **Component:** `(authenticated)/layout.tsx` (no auth gate), `AuthContext` effect-driven redirect
- **Category:** Perceived performance / Privacy polish
- **Problem:** ✔ Observed: navigating to `/` rendered the entire dashboard chrome (nav, greeting skeleton, user chip) for ~1s before the guard pushed `/login`. The layout renders children unconditionally; the redirect happens in a post-hydration effect.
- **Recommended direction:** Gate the shell on `auth.loading`/`tokenStatus` with a spinner, or server-redirect. Local to the layout.

**UIA-014 — "Overall Attendance" N/A state is an under-designed dead card (and silently uses the danger variant)**
- **Page/route:** `/dashboard` · **Component:** `OverallAttendanceCard.tsx:67-77`
- **Category:** Empty states / Information hierarchy
- **Problem:** With no recorded sessions, the card shows "—", an "N/A" badge, a 0-width progress bar that is **invisible** (track `bg-muted` #171717 equals card background #171717), and stretches to match the tall Today's Attendance card, leaving a ~340px void. The progress variant falls through to `danger` (red) when status is null — semantically wrong (invisible at 0 width, but wrong if data ever arrives).
- **Severity:** Medium · **Frequency:** repeated (same for zero-record and early-semester students)
- **Evidence:** ✔ runtime; ▤ code + tokens (`globals.css`: `--muted` = `--card` = `#171717`).
- **Recommended direction:** A designed "Not enough data yet — mark your first classes" empty state; neutral progress variant; don't stretch to match. Local card + token fix for track contrast (global).
- **Related:** UIA-001 (same recorded-only semantics), UIA-024 (card voids).

**UIA-015 — Login and signup error banners are not announced to screen readers**
- **Pages:** `/login`, `/signup` · **Components:** the two `page.tsx` error `<div>`s
- **Category:** Accessibility
- **Problem:** The inline error banner ("Incorrect roll number or password") has neither `role="alert"` nor `aria-live`; page errors won't be announced. (Other mutation errors in the app *do* announce — the Mark Attendance inline error uses `aria-live="polite"`, toasts use proper roles — so this is drift, not a system gap.)
- **Severity:** Medium · **Frequency:** repeated (2 forms)
- **Evidence:** ✔ runtime DOM query found no alert role; ▤ code.
- **Recommended direction:** Add `role="alert"` to both banners; consider `aria-live` for field-level validation summaries. Local ×2.

**UIA-016 — Confirmation-dialog action color contradicts the page CTA for the same action**
- **Page/route:** `/tools/laboratory` → "Mark all present" · **Components:** `tools/laboratory/page.tsx` (green `bg-success` CTA) vs `ConfirmDialog.tsx` (default blue primary confirm)
- **Category:** Visual consistency / Interaction UX
- **Problem:** The bulk CTA is green on the page; its confirmation button is blue in the dialog. Same action, two colors — weakening the color semantics the app otherwise maintains (success = green).
- **Severity:** Medium · **Frequency:** repeated (all ConfirmDialog confirmations, e.g. event cancellation)
- **Evidence:** ✔ runtime screenshots of both; ▤ code.
- **Recommended direction:** Add a `success` variant to ConfirmDialog or style destructive/positive confirms consistently. Local to ConfirmDialog + call sites.

**UIA-017 — Quiz Eligibility error card bypasses semantic tokens (raw palette)**
- **Page/route:** `/tools/quiz-schedule` · **Component:** `QuizEligibilityCard.tsx:108` — `border-red-900/50 bg-red-950/20 text-red-400`
- **Category:** Design-system drift
- **Problem:** Uses raw Tailwind reds instead of `destructive` tokens; will diverge from the app's destructive color if tokens change.
- **Severity:** Medium · **Frequency:** isolated
- **Evidence:** ▤ code.
- **Recommended direction:** Swap to `border-destructive/40 bg-destructive/10 text-destructive`. Local.
- **Related:** UIA-023 (token drift inventory).

**UIA-018 — Three different progress-bar implementations with different heights**
- **Pages:** Dashboard, `/subjects`, `/history`, `/tools/laboratory` · **Components:** `ui/progress.tsx` (Base UI, `h-1` = 4px), `SubjectAttendanceCard.tsx:106` (custom div, `h-1.5` = 6px), `WeeklyAttendanceCard.tsx:81` (custom div, `h-1.5`)
- **Category:** Design-system drift
- **Problem:** Three implementations (one primitive + two hand-rolled) with two track heights and inconsistent fill/track color handling; the shared track color is invisible on cards (see UIA-014).
- **Severity:** Medium · **Frequency:** systemic
- **Recommended direction:** One Progress primitive with `size` variants; track color token that contrasts with card. Global.

**UIA-019 — "LIVE" badge on Today's Attendance doesn't mean live**
- **Page/route:** `/dashboard` · **Component:** `TodayAttendanceCard.tsx:30-35` — `is_working_day ? "LIVE" : "TEACHING DAY"`
- **Category:** UX copy
- **Problem:** "LIVE" is shown for any working teaching day (even at 3 AM with all classes pending); it suggests real-time state. Also inconsistent with the Calendar page's "Teaching day"/"Working day" chips for the same data.
- **Severity:** Medium · **Frequency:** repeated (every teaching day)
- **Evidence:** ✔ runtime; ▤ code.
- **Recommended direction:** Drop "LIVE" (title already says "Today") or use "Teaching day" everywhere. Local.

**UIA-020 — Settings modal bottom info-box re-explains controls in implementation terms**
- **Page/route:** Shell → Settings · **Component:** `SettingsModal.tsx:323-330`
- **Category:** UX copy / Redundancy
- **Problem:** "Class reminders are shown in the bell icon when enabled. Week start controls the calendar layout. Auto-mark present is saved with your account but does not mark attendance yet." — a third restatement of facts already in each row's helper text, in half-implemented language.
- **Severity:** Medium (merged into the copy pass) · **Frequency:** isolated
- **Recommended direction:** Delete the box; keep per-row helpers only. Local.

**UIA-021 — Mark Attendance page shows the same date three times stacked (and the page title twice on mobile)**
- **Page/route:** `/tools/laboratory` · **Component:** page header + date nav (`page.tsx:162-203`)
- **Category:** Information hierarchy / Redundancy
- **Problem:** "Tuesday · 29 Sep 2026" (subtitle) + native "09/29/2026" input + "29 SEP" (formatShortDate caption) all visible at once; on mobile the fixed header additionally shows "Mark Attendance" above the in-page h1 "Mark Attendance".
- **Severity:** Medium · **Frequency:** repeated (every visit)
- **Evidence:** ✔ runtime desktop + mobile.
- **Recommended direction:** One date display (the input) + one title. Keep the mobile header OR the h1. Local.

**UIA-022 — Dashboard "Getting started" dismiss affordance is bottom-left and orphaned**
- **Page/route:** `/dashboard` · **Component:** `AttentionRequiredCard`/hint banner (getting-started card)
- **Category:** Interaction UX
- **Problem:** The dismiss ✕ sits below the text at the card's bottom-left, far from the usual top-right corner; at first glance it reads as stray decoration.
- **Severity:** Medium (low) · **Frequency:** isolated
- **Evidence:** ✔ runtime.
- **Recommended direction:** Move to card top-right. Local.

**UIA-023 — Two parallel card components (`Card` + `GlassCard`) and mixed border/ring treatments**
- **Components:** `ui/card.tsx` (ring-1, rounded-xl, `--card-spacing`) vs `shared/GlassCard.tsx` (adds only `bg-card border-border shadow-none` — a no-op wrapper) vs `SubjectAttendanceCard` (passes redundant `bg-card border-border` overriding ring with border utilities)
- **Category:** Design-system drift
- **Problem:** Same conceptual component, three authoring styles; `GlassCard` is used by Profile, Quiz pages, feedback page — its class list suggests a glassmorphism history that no longer exists.
- **Severity:** Medium · **Frequency:** systemic
- **Recommended direction:** Keep one Card; delete GlassCard (mechanical replacement). Global refactor (mechanical).

**UIA-024 — Dashboard cards stretch to row height, leaving large dead voids**
- **Page/route:** `/dashboard` · **Components:** `OverallAttendanceCard`, `QuizSnapshotCard`, `AttentionRequiredCard` (all `h-full`)
- **Category:** Layout / Visual density
- **Problem:** Quiz Snapshot has ~170px of empty space between its stats and footer; Attention Required ~300px when there are no alerts (its empty state floats in a void); Overall Attendance void covered in UIA-014. caused by `h-full` height-matching without content scaling.
- **Severity:** Medium · **Frequency:** repeated (data-dependent)
- **Evidence:** ✔ runtime desktop.
- **Recommended direction:** Design matched-height *with* content growth (e.g. Upcoming Events list fills), or don't force equal heights. Local per card.

**UIA-025 — Native date inputs force US `mm/dd/yyyy` entry**
- **Pages:** `/history` filters, `/tools/events` filters, `/tools/laboratory` date nav, Add Event dialog
- **Category:** Interaction UX / Localization consistency
- **Problem:** `<input type="date">` renders the browser's US-style format and calendar glyph; the app's own copy is "29 Sep 2026" and the audience is an Indian university. Also produces the three-format stacking of UIA-021.
- **Severity:** Medium · **Frequency:** repeated
- **Evidence:** ✔ runtime all surfaces.
- **Recommended direction:** Keep native inputs (keyboard/mobile-friendly) but pair with a visible formatted date, or adopt a styled picker. Global component.

**UIA-026 — History row metadata noise: "Logged 2:09 AM"**
- **Page/route:** `/history` · **Component:** `history/page.tsx:89`
- **Category:** Information hierarchy / UX copy
- **Problem:** Every row shows "🕒 03:00 PM · **Logged 2:09 AM**" — the record-creation timestamp. It invites misreading (2:09 AM looks like the class time) and is operational metadata, not student value.
- **Severity:** Medium · **Frequency:** repeated (every row)
- **Recommended direction:** Drop, or move behind an expandable detail. Local.

**UIA-027 — History/Events filter labels and empty-filter copy use vague "state" terminology**
- **Pages:** `/history`, `/tools/events` · **Components:** filter selects (`"All states"`, label "STATE")
- **Category:** UX copy / Interaction consistency
- **Problem:** Options are Present/Absent/Pending/Cancelled but the label/group is "state" ("Try adjusting the subject, state, dates, or search query."). "Status" is the obvious word. (History's `STATE` select is at `history/page.tsx:27`.)
- **Severity:** Medium (low) · **Frequency:** repeated
- **Recommended direction:** Rename to "Status"/"All statuses". Local ×2.

**UIA-028 — Quiz page shows FAIL / NOT ELIGIBLE for students with zero recorded data**
- **Page/route:** `/tools/quiz-schedule` · **Component:** `QuizEligibilityCard` (PASS/FAIL badges, Final Result)
- **Category:** UX copy / Status design
- **Problem:** A brand-new student (0 attended, all pending) sees red "✕ FAIL" per criterion and a red "NOT ELIGIBLE" result badge. Arithmetically true, emotionally wrong: the state is "no data yet", not "failed". The dashboard handles the same case with "N/A".
- **Severity:** Medium · **Frequency:** repeated (new/early-semester students)
- **Evidence:** ✔ runtime.
- **Recommended direction:** Map "no recorded data" to a neutral "Not enough data" badge; reserve FAIL for ≥1 recorded session. Local (needs backend signal or frontend guard).

**UIA-029 — Two near-duplicate Profile surfaces with different content**
- **Routes/components:** user-menu "Profile" → `ProfileModal` (identity + academic context) vs `/profile` page (`profile/page.tsx`, identity + UUID + sign out)
- **Category:** IA / Mental model
- **Problem:** Two read-only surfaces with the same job, reached from the same menu, with divergent content (modal shows semester/quiz dates; page shows UUID + Sign Out). Users can't predict which "Profile" does what.
- **Severity:** Medium · **Frequency:** isolated
- **Recommended direction:** Merge (menu opens the page, or the modal absorbs the page's content). Local.

**UIA-030 — Small controls below recommended touch-target sizes (systemic)**
- **Components:** user-menu items (`MobileBottomNav` sheet aside: dropdown items measured **26.6px** tall at runtime ✔); desktop buttons `sm:h-8` = **32px** (`ui/button.tsx:24`); icon buttons `sm:size-8`; notification bell hit area ~36px; settings Switch 44×**24**.
- **Category:** Accessibility / Touch targets
- **Problem:** Mobile sizes are correct (h-10 = 40px+); the *desktop/tablet pointer* sizes shrink to 26–32px. WCAG 2.5.8 minimum is 24px (these pass) but 44px is the comfortable standard the app's own UI-024 comments cite.
- **Severity:** Medium · **Frequency:** systemic
- **Recommended direction:** Decide one floor (32px pointer / 44px touch already half-done) and encode in the button/menu primitives. Global tokens.

**UIA-031 — Bottom-nav labels are 10.4px (`text-[0.65rem]`)**
- **Component:** `MobileBottomNav.tsx:53`
- **Category:** Accessibility / Typography
- **Problem:** Sub-11px labels are below common readability floors for primary navigation; no other surface uses type this small except 11px uppercase micro-labels.
- **Severity:** Medium (low) · **Frequency:** isolated (mobile nav)
- **Recommended direction:** 12px minimum for nav labels. Local.

---

### LOW

**UIA-032 — Redundant date tile + text date in Events rows** — "OCT 5" tile *and* "📅 5 Oct 2026" text on every row (`/tools/events`) ✔. Drop one. *Isolated.*

**UIA-033 — Events page tri-redundancy of explanation** — amber banner + "Manage events" card + button label all explain the same concept; the banner alone would do ✔. *Isolated.*

**UIA-034 — History search placeholder truncates mid-word** ("Code, name, type, c…") at desktop width ✔. Shorten placeholder. *Isolated.*

**UIA-035 — Calendar mobile abbreviation "6 cl."** is cryptic ✔; consider dots/counts-only with legend. *Isolated.*

**UIA-036 — Weekly card past weeks read "0/0 · 27 pending"** — "pending" for long-past weeks is semantically odd ("unmarked" is what it means) ✔▤. Also uses a `Badge` as a paragraph-level empty state ("No subjects with recorded attendance") — an odd component choice ▤. *Repeated.*

**UIA-037 — Detail rows say "missed"** while canonical vocabulary is "Absent" (`SubjectAttendanceCard.tsx:244`) ▤. *Repeated.*

**UIA-038 — Feedback success state has no explicit "Done" CTA and no auto-close** (verified: the success branch renders icon + text only; closing is via header ✕) ▤. *Isolated.*

**UIA-039 — `font-heading` utility used by `CardTitle` has no `--font-heading` token defined** (`globals.css` defines only sans/mono) — silently falls back; latent drift ▤. *Systemic (latent).*

**UIA-040 — Signup helper text reads as implementation** — "Elective options reflect the current semester's catalog; the server verifies your selection against it." ✔ (fold into UIA-003 copy pass). *Isolated.*

**UIA-041 — "Recoverable" badge lacks an on-ramp explanation** — first-time quiz-page visitors get an amber badge with no definition (defined only inside expanded calculation) ✔. Tooltip/one-liner would fix. *Isolated.*

**UIA-042 — User-menu trigger renders near-white when open** (observed in one runtime screenshot while the code specifies `data-popup-open:bg-accent` = #262626) ⚠ **unverified** — possibly a capture artifact; verify on real hardware. *Isolated, unverified.*

**UIA-043 — Lab Experiments page is very sparse at desktop** — content ends ~500px with ~400px empty below (single stats card + mid-sem card) ✔. Consider richer default tab or centered layout. *Isolated.*

**UIA-044 — Mid-Sem Practical "Not scheduled" row repeated on all three lab cards** with no action or explanation of when it will be scheduled ✔. *Repeated.*

**UIA-045 — Roll number appears twice in Profile modal** (avatar block + UNIVERSITY ROLL NUMBER field) ✔. *Isolated.*

---

## A. EXECUTIVE SUMMARY

The application is **structurally sound and visually coherent for a student tool**: a single dark token set, a disciplined nav IA generated from one source (`navItems.ts`), real loading/empty/error states on data surfaces, honest confirmations before destructive/bulk mutations, well-built toasts with proper ARIA roles, good safe-area handling, and unusually thoughtful calendar a11y labeling. The fundamentals that usually rot first (buttons, inputs, dialogs) are centralized and consistent.

The audit found **45 distinct issues (2 Critical, 10 High, 19 Medium, 14 Low)**, and the problems cluster into five systemic patterns rather than scattered nitpicks:

1. **The most important number in the product is mislabeled.** "83% overall" (History) and "83% Healthy" (Dashboard) are *recorded-only* percentages presented without qualification, next to "280 pending" — the recorded-only policy is real and intentional, but only `/subjects`' expanded detail ever explains it. This is the single largest comprehension risk (UIA-001, UIA-014, UIA-028).
2. **Internal engineering language leaks into student copy** on at least eight surfaces ("backend-derived from the canonical attendance pipeline", "evaluated by the backend", "The server enforces…", "Phase 1 design tokens", raw UUIDs) — the strongest "unfinished" signal in the product (UIA-003, UIA-007).
3. **Status vocabulary has drifted into seven dialects** (Healthy/Watch/At Risk/Critical, Eligible/Recoverable/Not Eligible/Unresolved, PASS/FAIL, Attention, Present/Absent/Pending/missed/state) — a design-system-level gap, not per-page sloppiness (UIA-006).
4. **Mobile IA deprioritizes the core daily action** (Mark Attendance sits in the More sheet) while the "Attendance" tab name promises exactly that action (UIA-005).
5. **The same concepts are implemented two or three times** (progress bars ×3, cards ×2-3, date formats ×3, profile surfaces ×2, formula phrasings ×3) — mechanical drift that inflates maintenance and produces subtle visual differences (UIA-004, UIA-011, UIA-018, UIA-023, UIA-029).

Interaction quality is generally good: bulk actions confirm first, errors recover with retry, filters work, Escape/focus behavior on dialogs checks out, and the mobile bottom-sheet pattern is proper. The two Critical defects (Settings' false dirty state with a no-op Save; the misleading History headline) are both narrow, high-leverage fixes.

---

## B. SEVERITY BREAKDOWN

| Severity | Count | Issue IDs |
|---|---|---|
| Critical | 2 | UIA-001, UIA-002 |
| High | 10 | UIA-003 … UIA-012 |
| Medium | 19 | UIA-013 … UIA-031 |
| Low | 14 | UIA-032 … UIA-045 |
| **Total** | **45** | |

(Counts de-duplicate systemic patterns; each ID is a distinct defect with its own evidence.)

---

## C. SYSTEMIC DESIGN PROBLEMS (solve at design-system level)

1. **Percentage-basis labeling** (UIA-001, UIA-014, UIA-028) — one shared "recorded-only" caption/badge pattern across History, Dashboard, Lab, Quiz.
2. **Status vocabulary** (UIA-006) — canonical label+color+icon map in one module; delete the 7 local maps.
3. **Progress bars** (UIA-018, UIA-014) — one primitive, visible track token, N/A state designed.
4. **Date formatting** (UIA-011, UIA-021, UIA-025) — route all dates through `lib/date.ts`; ban raw ISO in JSX.
5. **Card component** (UIA-023) — one Card; remove GlassCard; unify border/ring treatment.
6. **Copy register** (UIA-003, UIA-040, ShellField tooltip) — banned-terms list (backend/server/pipeline/tokens/surface/enforce) + one copy pass.
7. **Dialog/action color semantics** (UIA-016) — ConfirmDialog variants aligned with success/destructive page CTAs.
8. **Touch-target floor** (UIA-030, UIA-031) — encode minimum sizes in primitives instead of per-component overrides.
9. **Form error announcements** (UIA-015) — standard `role="alert"` error-banner component used by both auth forms (the Mark Attendance inline error is the in-repo reference pattern).

---

## D. PAGE-BY-PAGE AUDIT

### `/login`
- **Works:** Clean centered card; show/hide password with aria-label; session-expired notice; network vs HTTP error distinction in copy; disabled loading state on submit. ✔
- **Problems:** Error banner not announced (UIA-015). Native-only validation styling for empty submit (browser bubble — acceptable). "Min 8 characters" placeholder is a rule-as-placeholder (minor).
- **Responsive:** ✔ 1440 & 375 fine (single column card).
- **Missing states:** None.

### `/signup`
- **Works:** Full client validation (name, 13-digit roll, password complexity, confirm match, electives required); per-field errors clear on edit; honest 422/409 server error surfacing; password toggles; elective helper note. ✔
- **Problems:** Summary banner shows only the first error while field errors also show (redundant); helper copy reads as implementation (UIA-040); elective catalogs hardcoded client-side (known, documented in code — flagged, not re-litigated).
- **Responsive:** ✔ fine.
- **Interaction note:** Both password toggles share the label "Show password" (ambiguous for SR users — fold into UIA-015 fix pass).

### `/dashboard`
- **Works:** Strong card set (Today, Overall, This Week, Quiz Snapshot, Attention Required, Upcoming Events); status badges with icons; dismissible onboarding hint with working persistence; skeleton loading for greeting. ✔
- **Problems:** Greeting name bug (UIA-009); recorded-only "83%" + "Healthy" without basis (UIA-001 family); N/A dead card (UIA-014); card voids (UIA-024); ISO week range (UIA-011); "LIVE" semantics (UIA-019); weekly rows "pending" phrasing (UIA-036); hint ✕ placement (UIA-022).
- **Responsive:** ✔ desktop 2-col grid, tablet/mobile single column; bottom padding reserves nav space correctly.
- **Missing states:** Overall Attendance empty state under-designed (UIA-014).

### `/tools/laboratory` (Mark Attendance)
- **Works:** The core flow is excellent: date navigation with semester clamping, honest future-date view-only state, per-class Present/Absent with inline status + Change, count/progress updates, "Mark all present" gated by a real confirm dialog with pending-lock, accurate result toast ("Marked 4 classes present"), inline `aria-live` mutation errors, proper skeleton and empty ("No classes scheduled") states. ✔
- **Problems:** Triple date display + double title (UIA-021); native date input (UIA-025); "29 SEP" orphan caption.
- **Responsive:** ✔ mobile layout is comfortable; targets adequate.
- **Missing states:** None observed.

### `/subjects` (Attendance overview)
- **Works:** Clear per-subject cards with health badges, Lecture/Tutorial breakdown, expandable verified details, LAB/THEORY differentiation, recorded-only explainer in details. ✔
- **Problems:** Formula text on every card (UIA-004); "missed" terminology (UIA-037); lab cards' "Not scheduled" noise (UIA-044); mobile header title "Attendance" vs h1 "Subjects Overview" (IA naming).
- **Responsive:** ✔ 3→2→1 column flow fine; progress bar renders correctly at 100% (green, full width).
- **Missing states:** Zero-data state relies on em-dashes (ties to UIA-014).

### `/tools/quiz-schedule` (Quiz Eligibility)
- **Works:** Quiz cycle tabs with date-aware default; per-subject cards with windows, averages, expandable full calculation; guidance ("Must attend / Safe skip") only when reachable; unknown-state defensive fallback; per-card error + retry. ✔
- **Problems:** Dense policy wall before content (worst on mobile — the info box pushes the first subject card below the fold); uppercase formula per card (UIA-004); contradictory must-attend numbers (UIA-012); FAIL/NOT ELIGIBLE for zero-data students (UIA-028); "Recoverable" unexplained (UIA-041); "evaluated by the backend" (UIA-003); raw-palette error card (UIA-017).
- **Responsive:** ✔ tabs wrap; cards stack.
- **Missing states:** Unresolved state is handled (text explainer) — good.

### `/history`
- **Works:** Stat tiles, working Subject/Status/Date/Search filters (runtime-verified: Status=Absent → "Showing 1 of 1 sessions"), Load-more pagination with count, clean rows with date tiles and status pills, empty-filter guidance. ✔
- **Problems:** **"83% overall" (UIA-001, Critical)**; "Logged" noise (UIA-026); "state" terminology (UIA-027); placeholder truncation (UIA-034); subtitle date format (UIA-011); past rows forever "Pending" (UIA-036 family).
- **Responsive:** ✔ stat tiles wrap 3+2; filters stack full-width and push content (consider collapsible filters on mobile — polish note).
- **Missing states:** None.

### `/calendar`
- **Works:** Excellent accessible day cells (rich aria-labels: "Tuesday · 29 Sep 2026, working day, 6 classes, no events"); month navigation with working Today; selected/today/event dot legend; day-detail panel with working/teaching chips and event listing; mobile "N cl." compaction. ✔
- **Problems:** Right panel dead space on eventless days; subtitle format (UIA-011); abbreviation "cl." (UIA-035).
- **Responsive:** ✔ grid stays usable at 375; panel stacks below.
- **Missing states:** None.

### `/tools/events`
- **Works:** Grouped upcoming/past lists, filters, role-aware Add Event dialog (compact 4-field form with disabled-until-valid Create), per-row Calendar deep link. ✔
- **Problems:** Banner + manage-card redundancy (UIA-033); "The server enforces…" copy (UIA-003); date tile redundancy (UIA-032); native date inputs (UIA-025).
- **Responsive:** ✔ rows stack fine.
- **Missing states:** None observed (empty state exists via shared component).

### `/laboratory` (Lab Experiments)
- **Works:** Subject switcher + three tabs; honest stats with an explicit basis caption ("cancelled sessions excluded, pending not counted as absent") — the *correct* pattern the other surfaces should copy; mid-sem state from backend only. ✔
- **Problems:** Worst jargon subtitle in the app (UIA-003); sparse page with large void (UIA-043).
- **Responsive:** ✔.
- **Missing states:** Experiments/Activity tabs not deep-audited (runtime-verified rendering only).

### `/profile`
- **Works:** Read-only honesty banner ("Profile editing isn't available yet"), clear identity card, sign-out placement. ✔
- **Problems:** Raw UUID (UIA-007); parallel Profile modal (UIA-029).
- **Responsive:** ✔.
- **Missing states:** Error state exists with retry + sign-out.

### `/tools/feedback`
- **Problems:** Student-reachable admin surface rendering a raw authorization error (UIA-008, High). This page's *admin* rendering was not audited (admin account unavailable) — code-inspected only.

### Shell (nav, bell, user menu, modals, toasts)
- **Works:** Single-source nav; md–lg "More" dropdown; proper mobile More sheet with safe-area padding; bell badge with count + aria-label + 99+ cap; user menu with keyboard support and correct focus restoration after close (verified settled); Profile/Appearance/Install/Feedback/Settings dialogs share one foundation (ShellDialog) with consistent header/backdrop/Escape/scroll-lock; toasts are positioned above the bottom nav on mobile, carry role/aria-live, cap at 3, and support actions. ✔
- **Problems:** Settings dirty-state bug (UIA-002, Critical); browser-notifications row layout (UIA-010); Appearance modal dev-jargon (UIA-003); menu item target heights (UIA-030); user-menu trigger open-state color ⚠ (UIA-042); Install App copy is long and hedged (fold into copy pass).

### Global error/404 (▤ code-inspected)
- `app/error.tsx` and `app/not-found.tsx` are branded, token-consistent, recovery-oriented (Try again / Go to Dashboard), and leak no internals. **Good.** Flash-of-shell issue noted separately (UIA-013).

---

## E. CROSS-APPLICATION CONSISTENCY AUDIT

| Concept | State | Verdict |
|---|---|---|
| **Typography** | Tailwind scale; h1 `text-2xl bold` everywhere ✔; but bottom-nav 10.4px outlier, 11px uppercase micro-labels used widely, `font-heading` token undefined (UIA-039) | Mostly consistent, 2 outliers |
| **Colors** | Semantic tokens (success/warning/destructive/primary) used consistently; **1 raw-palette violation** (UIA-017); muted==card makes tracks/empty zones invisible | Good, 1 fix + 1 token decision |
| **Buttons** | One primitive with cva variants ✔; confirm-dialog vs page-CTA color mismatch (UIA-016); desktop 32px height small (UIA-030) | Consistent structurally |
| **Cards** | Three authoring styles (Card / GlassCard / inline overrides); radius consistent (rounded-xl); spacing via `--card-spacing` ✔ | Drift (UIA-023) |
| **Inputs** | One Input/Select ✔; native date inputs everywhere (UIA-025) | Consistent |
| **Modals** | ShellDialog foundation for all shell modals ✔ (widths sm/md/lg defined); ConfirmDialog for confirmations ✔; EventFormDialog separate but similar; consistent uppercase label rows | Good |
| **Navigation** | One navItems source across 3 responsive bands ✔; **label≠page-h1 mismatches** ("Attendance" vs "Subjects Overview", "Events" vs "Academic Events") | Structurally excellent, naming drift |
| **Status indicators** | Badge variants comprehensive ✔; **7 vocabularies** for overlapping states (UIA-006) | The biggest inconsistency |
| **Spacing** | 4px rhythm from `--spacing(4)` card spacing; pages use max-w-5xl/max-w-2xl/max-w-4xl inconsistently (dashboard 5xl, mark-attendance 2xl, profile 4xl) | Minor drift |
| **Icons** | Lucide throughout, `size-4/size-5` norms ✔ | Consistent |
| **Loading states** | Skeletons on dashboard cards, Mark page, profile ✔; skeleton shapes occasionally generic blocks vs final layout (Mark page) | Good |
| **Error states** | Shared ErrorState + per-card retry + inline aria-live + toasts ✔; auth forms not announced (UIA-015); feedback route's error misused for authorization (UIA-008) | Strong with 2 gaps |
| **Empty states** | Shared EmptyState used broadly ✔; Overall Attendance under-designed (UIA-014); Badge-as-empty-text oddity (UIA-036) | Good, 2 gaps |
| **Toasts** | One toast system, correct ARIA, semantic variants ✔ | Excellent |

---

## F. RESPONSIVE AUDIT

### Desktop (1440×900)
- No horizontal overflow anywhere (verified `scrollWidth == clientWidth` on auth pages; content capped at max-w-5xl).
- Content column (~960px) floats in generous margins while the nav spans full width — acceptable but the Lab page's sparseness (UIA-043) and dashboard voids (UIA-024) read as unfinished at this width.
- Buttons/menu items shrink to 26–32px (UIA-030).

### Tablet (768×1024)
- Adaptive nav (primary + More dropdown) works and never overflows ✔.
- Dashboard stacks to single column; stat tiles wrap cleanly ✔.
- Same 32px control heights; nothing else tablet-specific observed.

### Mobile (375×812)
- Bottom nav + More sheet ✔ with `env(safe-area-inset-bottom)` padding ✔; toasts clear the nav ✔; dialogs become bottom sheets where enabled ✔.
- **Priority inversion:** Mark Attendance not a tab (UIA-005).
- Quiz page policy wall pushes data below fold (UIA-004/012 family).
- History filters (~450px) push the list down (polish).
- Mark Attendance triple-date + double title (UIA-021).
- No horizontal overflow or clipped content observed; calendar usable.

---

## G. ACCESSIBILITY AUDIT

**Strengths (verified at runtime or in code):**
- Calendar day cells expose complete aria-labels including events and working-day state (best-in-app).
- Toasts: `role="status"/"alert"` + `aria-live` matched to severity; `motion-reduce` respected.
- Dialogs (Base UI): focus trap, Escape close, focus restored to trigger after close (verified after settle); `aria-label` close buttons.
- Nav: `aria-current="page"` on all three bands; mobile More marked `aria-expanded`/`aria-current`.
- Feedback-type toggles expose `aria-pressed`.
- Status never communicated by color alone: Present/Absent/PASS/FAIL include icons; all badges include text.
- Color contrast: foreground/muted-foreground/success/warning/destructive on dark all comfortably exceed 4.5:1 (token values verified).
- Form controls: label associations (`htmlFor`), `aria-label` on unlabeled icon controls (bell, date nav, password toggles).

**Gaps:**
- Login/signup error banners lack `role="alert"` (UIA-015).
- No skip-to-content link; the inner scroll container (`main.flex-1.overflow-y-auto`) is not focusable, so keyboard scrolling depends on clicking inside content first (standard but worth a `tabindex="0"` + label or a skip link).
- Touch/pointer target sizes: dropdown items 26.6px, desktop buttons 32px, switch 24px tall (UIA-030); bottom-nav labels 10.4px (UIA-031).
- "Healthy/At Risk/Critical" badges distinguish two danger levels only by fill intensity (color+contrast only) — text differs, so this passes, but the *solid vs soft red* distinction carries no text meaning.
- Password-visibility toggles in signup share the same accessible name ("Show password" ×2) — ambiguous to SR users.
- The native date inputs are accessible but render US field order (locale mismatch, UIA-025).
- Unverified: real screen-reader pass and full keyboard-only walkthrough were not performed (automation-assisted audit).

---

## H. UX FLOW AUDIT

1. **Registration → first dashboard** (✔ walked end-to-end): smooth; validation is strict but clear; the app lands on a dashboard that immediately explains next steps ("Getting started"). Good onboarding. Friction: the recorded-only "N/A everywhere" first-run state is under-explained on dashboard (UIA-014) while quiz page says FAIL (UIA-028) — mixed messages on day one.
2. **Marking today's attendance** (✔): desktop path is excellent (nav → per-class buttons → confirm for bulk). Mobile path adds a More-sheet hop for the core action (UIA-005).
3. **Correcting a mistake**: "Change" link on marked rows works; no undo on bulk actions (toast informs but the row-by-row Change is the recovery path — acceptable, worth an "Undo" toast action for bulk).
4. **Checking eligibility**: two hops deep (Quiz tab → View Calculation) for the headline answer; the pre-expanded card gives the verdict but the *actionable* number ("attend next N") is inside the expansion and contradictory when shown (UIA-012).
5. **Finding why a subject is at its %**: subjects → View Details explains recorded-only basis — good, but this explanation is absent exactly where the misleading numbers live (History/Dashboard, UIA-001).
6. **Settings**: broken trust loop on open (UIA-002) and the push-notification row is broken at default width (UIA-010).
7. **Event creation** (dialog opened, not submitted ✔): compact, validated, honest enrollment errors — good.
8. **Feedback**: excellent modal flow (type toggle → char-gated submit → success); feedback *viewing* is admin-only and leaks an error to students (UIA-008).

---

## I. DESIGN SYSTEM RECOMMENDATIONS (not implemented — direction only)

- **Tokens to add:** `--font-heading` (or remove the utility); a `--track` color for progress tracks that contrasts with `--card`; success/danger pair for confirm actions; optional `--text-2xs` floor (12px) to eliminate `text-[0.65rem]`/`text-[11px]` ad-hoc sizing.
- **Typography scale:** codify h1 `text-2xl`, card title `text-base`, body `text-sm`, meta `text-xs`, micro-label `text-[11px] uppercase tracking-wider` (already de-facto standard — write it down; ban <12px for interactive labels).
- **Spacing:** unify page container widths (max-w-5xl everywhere or a documented 2-tier system); keep `--card-spacing`.
- **Radius/shadows:** current scale (radius 0.5rem base; cards rounded-xl, buttons rounded-lg) is consistent — freeze it.
- **Status system:** one module exporting `{label, badgeVariant, icon}` for: session status (Present/Absent/Pending/Cancelled), subject health (Healthy/At Risk/Critical), quiz state (Eligible/Recoverable/Not eligible/Unscheduled). Nothing renders a status outside this map.
- **Progress:** single `<Progress>` with `size="sm|md"`, `variant` incl. `neutral`, and a designed `null` (N/A) rendering.
- **Buttons:** add `success` variant; document the 40px mobile / ≥32px desktop floor; ConfirmDialog gains `variant="success"`.
- **Dialogs:** keep ShellDialog; add `role="alert"` error banner + recorded-only caption components to the shared kit.
- **Dates:** `lib/date.ts` becomes the only date formatter (add `formatDateRangeMedium`); add ESLint ban on raw `{...week_start}`-style ISO interpolation if feasible.
- **Navigation:** navItems.ts stays the source; add a `pageH1` field so nav label and page heading can't diverge.
- **Copy register:** a one-page banned-terms list (backend, server, pipeline, tokens, surface, enforce, state) with approved replacements.

---

## J. PRIORITIZED REMEDIATION BACKLOG

### P0 — severe usability / broken UX (fix first)
1. **UIA-002** Settings false dirty state + no-op Save (one-line logic fix + disabled-Save guard).
2. **UIA-001** History "83% overall" relabeling (recorded-only basis made explicit; align Dashboard Overall card caption).
3. **UIA-008** Guard `/tools/feedback` for students (redirect/403 state).
4. **UIA-010** Settings browser-notifications row layout.

### P1 — major inconsistency / significant UX degradation
5. **UIA-003** Global de-jargonization copy pass (8 surfaces).
6. **UIA-005** Mobile tab restructure (Mark Attendance as tab or equivalent CTA).
7. **UIA-009** Greeting name handling.
8. **UIA-006** Canonical status vocabulary module; retire local maps.
9. **UIA-012** Quiz "must attend" actionable-number redesign.
10. **UIA-011** Date-format sweep (weekly card, view-only banner, subtitles).
11. **UIA-014** Overall Attendance N/A state + invisible progress track token.
12. **UIA-028** Neutral "no data" state for zero-record quiz eligibility.
13. **UIA-007** Remove the UUID card from `/profile`.

### P2 — polish / consistency
14. **UIA-004** Formula-caption consolidation (per-page ⓘ, never uppercase).
15. **UIA-018** Single progress primitive + sizes.
16. **UIA-023** Card/GlassCard unification.
17. **UIA-016** ConfirmDialog success variant (mark-all flow color).
18. **UIA-015** `role="alert"` on auth error banners (+ signup toggle labels).
19. **UIA-013** Auth-gate the shell to kill the pre-login flash.
20. **UIA-021** Mark Attendance date/title de-duplication.
21. **UIA-024/043** Dashboard card voids + Lab page density.
22. **UIA-025** Date-input strategy (formatted companion display).
23. **UIA-017** Quiz error card token swap.
24. **UIA-019** "LIVE" badge wording.
25. **UIA-026/027** History "Logged" metadata + "state"→"Status" labels.
26. **UIA-029** Profile modal/page merge decision.
27. **UIA-030/031** Touch-target floor in primitives; bottom-nav label size.
28. **UIA-022** Getting-started dismiss placement.

### P3 — minor refinements
29. **UIA-032…038** Events row date tile, events tri-explanation, search placeholder truncation, calendar "cl." abbreviation, weekly "pending"/Badge-as-empty-state, "missed"→"Absent", Feedback success "Done" button.
30. **UIA-039…045** `font-heading` token decision, signup helper copy, "Recoverable" tooltip, user-menu open-state color (verify first), Lab page layout, mid-sem "Not scheduled" noise, Profile modal roll-number duplication.

---

## APPENDIX — VERIFICATION NOTES

- **Runtime-verified (✔):** all student routes at 1440/768/375; signup validation + successful registration; login failure path; empty-submit native validation; mark present/absent/bulk-confirm flows incl. success toast; future-date view-only state; history filters + pagination; calendar day selection/month navigation/aria labels; all five shell modals + notification center; notification badge count behavior; dialog Escape/focus restore (settled).
- **Code-inspected only (▤):** admin portal surfaces; `/tools/feedback` admin rendering; `error.tsx`/`not-found.tsx`; PWA service-worker/install internals (registration, install-prompt hook — present and wired, not exercised at runtime); Unenrolled/Zero-record seeded accounts (credentials unavailable).
- **Unverified (⚠):** UIA-042 (user-menu trigger open-state color).
- **Automation artifacts excluded from findings:** fullPage screenshot duplication (verified DOM contains single instance); a "More sheet at desktop" scare (automation clicked a hidden button; the sheet is correctly `lg:hidden`); transient post-Escape focus sampling.
