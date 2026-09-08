# AttendanceDash Pro — Design System & Redesign Specification

> **Purpose of this document.** This is a design specification for **AttendanceDash Pro**, a
> student-focused academic command center (attendance, quiz eligibility, schedule, academic
> calendar). It describes the product **as it actually exists today** — its visual identity,
> component language, screens and interaction patterns — and then defines the **redesign
> direction**: a calmer, better-hierarchized, more premium evolution of the same product.
>
> Throughout, sections are labeled:
> - **CURRENT STATE** — verified against the existing codebase (colors, typography, components,
>   layouts and behaviors described here are real, not aspirational).
> - **REDESIGN DIRECTION** — what the next version should change or evolve. The redesign must
>   feel like *the next polished version of AttendanceDash Pro*, never a generic SaaS template.
>
> This document is self-contained: a design tool can use it without access to the repository.

---

## 1. Product Overview

### 1.1 What AttendanceDash Pro is

AttendanceDash Pro is a **personal academic command center for university students**. It lets a
single student track and manage:

- **Attendance** — overall and per-subject (Lecture, Tutorial, Practical), with health bands.
- **Daily marking** — the student records Present/Absent for each of their actual scheduled
  classes, day by day (the product's core write action).
- **Quiz eligibility** — institutional quiz-cycle eligibility (Quiz I / II / III) evaluated
  against attendance criteria, with "must attend / safe skip" guidance.
- **Academic calendar** — working days, teaching days, holidays, substitutions, events.
- **Academic events** — extra classes, cancellations, surprise quizzes, holidays.
- **Attendance history** — a complete filterable record of every session in the semester.
- **Lab experiments** — practical attendance, experiment progress and activity for lab subjects.
- **Notifications** — class reminders, quiz-approaching, attendance-threshold and must-attend /
  safe-skip alerts (push + in-app inbox).

It ships as an installable **PWA** (manifest, service worker, offline shell, push notifications,
update banner, "Install App" flow) because students check it between classes, often on phones.

There is also a separate **Admin Portal** inside the same product — the authoritative control
plane where administrators configure curriculum, subjects, timetable entries, quiz schedules,
academic events, students (sections, subsections, elective corrections) and view attendance
analytics. The Admin Portal shares the design system but is a distinct, workbench-style surface.
This document focuses on the **student application**; the Admin Portal is summarized for context.

### 1.2 Who uses it

One primary persona: **a student** (engineering program, semester-based) who:

- checks attendance health and "am I safe?" many times per week, often **on a phone between
  classes**;
- marks attendance daily (Present/Absent per class);
- plans attendance around **quiz cycles** (eligibility thresholds at 70%/75%);
- occasionally checks the calendar, history and events.

A secondary persona: an **administrator**, who uses the Admin Portal to configure the academic
model. Admin configuration is what makes each student's data resolve correctly — students never
configure anything themselves.

### 1.3 Platform and product framing (CURRENT STATE)

- Web app, dark-themed, installable PWA; "standalone" display on mobile.
- Product name: **AttendanceDash Pro** (wordmark renders as "AttendanceDash **Pro**", with
  "Pro" visually de-emphasized in the navigation bar).
- Tagline in metadata: "Advanced Academic Management System"; the student-facing auth card says
  "**Student Portal**".
- Core principle baked into the product: **the backend is authoritative** — the UI never
  recomputes attendance, eligibility, banding or dates; it renders backend-derived values and
  exposes retry/error states honestly. The design should not imply manual number editing.

---

## 2. Design Goals (REDESIGN DIRECTION)

The redesign has one central principle:

> **Show the right information at the right time — not everything at once.**

Concretely, the next version of AttendanceDash Pro must:

1. **Fix dashboard information hierarchy.** The Home screen currently renders six dense cards in
   a two-column grid; every card carries full detail. The redesigned Home must be a calm
   *overview / command center* that answers four questions at a glance:
   1. *How is my attendance?* (one hero answer)
   2. *Am I eligible / at risk?* (eligibility + attention summary)
   3. *What is happening today?* (next class + today's schedule)
   4. *Is there anything important I need to know?* (alerts/notifications)
   All detail moves to dedicated pages. Do **not** fill space just because it exists.
2. **Keep and refine the top navigation.** The app already uses a compact top bar on desktop and
   a bottom navigation on mobile (there is no left sidebar) — the redesign polishes this into a
   lighter, more premium top bar and a modern mobile pattern.
3. **Evolve, don't replace, the visual identity.** Preserve the near-black dark theme, the blue
   primary, Geist typography, rounded dark cards, pill badges and the semantic status colors —
   and make them more refined, consistent and spacious.
4. **Introduce glassmorphism tastefully** on navigation and elevated layers only (see §12).
5. **Design mobile deliberately.** Phones are the primary device for quick checks: big touch
   targets, scannable schedule, legible percentages, thumb-reachable actions.
6. **Stay honest and calm.** Status colors are semantic, always paired with text + icon; no
   neon, no glow, no decorative noise. Production-ready and professional.

---

## 3. Current Product Structure

### 3.1 CURRENT STATE — route map (student app)

| Destination | Route | Nav label | Purpose |
|---|---|---|---|
| Home / Dashboard | `/dashboard` | Home | Overview cards (see §7) |
| Mark Attendance | `/tools/laboratory` | Mark Attendance | Daily Present/Absent marking per scheduled session, date navigation, bulk "mark all present" |
| Lab Experiments | `/laboratory` | Lab Experiments | Practical attendance, experiments, activity (tabbed, per lab subject) |
| Quiz Eligibility | `/tools/quiz-schedule` | Quiz Eligibility | Per-subject quiz-cycle eligibility with criteria breakdown |
| Attendance (Subjects) | `/subjects` | Attendance | Subject-wise attendance cards ("Subjects Overview") |
| Attendance History | `/history` | History | Filterable semester session log |
| Calendar | `/calendar` | Calendar | Month grid of academic days + day detail panel |
| Academic Events | `/tools/events` | Events | Event list; students may add/remove extra classes, cancellations, surprise quizzes |
| Feedback | `/tools/feedback` | (admins only) | Feedback review (head-admin) |
| Profile | `/profile` | (via user menu) | Profile settings, identity, academic context |
| Auth | `/login`, `/signup` | — | Sign in / create account |
| Admin Portal | `/admin/*` | (separate shell) | Admin control plane |

Root `/` redirects to `/dashboard`. Unknown routes get a branded 404 with a "Go to Dashboard"
action. A global error boundary provides "Something went wrong" + Retry.

### 3.2 CURRENT STATE — application shell

- Full-height column: top bar (h-14, bottom border) → scrollable main → fixed mobile bottom nav.
- Main content is centered, `max-w-5xl`, padded `p-4 / md:p-6 / lg:p-8`; mobile reserves bottom
  padding (`pb-28`) so the fixed bottom nav never covers content.
- Page content width varies by task: `max-w-2xl` (Mark Attendance), `max-w-4xl` (Quiz
  Eligibility, Profile), full `max-w-5xl` (Dashboard, Subjects, History).
- Global shell modals: Profile, Appearance, Settings, Send Feedback, Install App, Notification
  Center — all opened from the top bar's user menu / bell.

### 3.3 CURRENT STATE — Admin Portal (context only)

Separate shell, same tokens: header with logo + horizontally scrollable nav of sections
(Overview, Students, Curriculum, Timetable, Quiz Schedules, Events, Admins, Attendance analytics,
Academic Structure, Feedback Review), metric-card overview grids, dense tables, create/edit
dialogs. It is a utilitarian workbench — the redesign should keep it visually consistent with the
student app but it is not the focus.

---

## 4. Information Architecture

### 4.1 CURRENT STATE — IA summary

- Navigation is **flat**: eight top-level destinations, no nesting, no sub-sidebars. Sections
  that are "tools" (Mark Attendance, Quiz Eligibility, Events) sit at the same level as
  "surfaces" (Attendance, History, Calendar).
- On mobile, only three tabs are fixed (Home, Attendance, History); everything else lives under a
  "More" bottom sheet. On tablet widths (md–lg) the desktop bar shows primary items plus a
  "More" dropdown.
- Detailed data lives *within* dashboard cards rather than in dedicated pages — e.g., weekly
  trend, quiz counters and upcoming events are all fully rendered on Home, with "View …" links
  to the detail pages.

### 4.2 REDESIGN DIRECTION — target IA

Restructure the student app around **surfaces, not tools**, so every major noun has one home:

| Redesigned destination | Content | Status vs today |
|---|---|---|
| **Dashboard** (Home) | Command-center overview: attendance hero, today strip, eligibility snapshot, alerts | Slim down drastically (see §7) |
| **Attendance** | Detailed subject-wise attendance (current per-subject cards, health bands) | Exists (`/subjects`); becomes the depth target for the dashboard hero |
| **Timetable** | Complete weekly timetable view — the full recurring week with the student's resolved subjects | **New destination**; today only today's schedule is visible (via Mark Attendance / Calendar). Data exists (admin-managed timetable resolves into each student's sessions) |
| **Track** | Actual sessions & occurrences: day-by-day marking, extra classes, cancellations, quiz-day occurrences, mid-sem practicals | Exists as "Mark Attendance" (`/tools/laboratory`) + Events; consolidate naming as "Track" |
| **Quizzes** | Quiz cycles (I/II/III) and full eligibility detail per subject, criteria windows, must-attend / safe-skip planning | Exists (`/tools/quiz-schedule`); becomes the depth target for the dashboard eligibility snapshot |
| **Calendar** | Academic dates, events, substitutions, day detail | Exists; keep |
| **History** | Historical session records with filters | Exists; keep |
| **Analytics** | Deeper attendance trends & insights: weekly series, deltas, per-subject forecasts | **New destination**; today analytics are backend-computed but only rendered inside dashboard cards. The weekly trend bar treatment (§5) is the seed of this page |

Secondary utilities (Search, Notifications, Sync/PWA status, Profile) stay in the top bar — not
as top-level destinations. Lab Experiments folds conceptually under the Attendance/Track cluster
(it remains a distinct page in the redesign IA).

**Dashboard rule:** the Dashboard links out; it does not duplicate. Each card shows a *summary*
(a number, a status, the next item) plus one clear "View …" affordance to its surface.

---

## 5. Navigation

### 5.1 CURRENT STATE — desktop top bar (h-14)

- Left: brand mark (28px logo image) + wordmark "AttendanceDash **Pro**" (0.95rem, semibold,
  tight tracking; "Pro" in muted color, normal weight).
- Center-left: inline nav links — small icon (16px) + label (`text-sm font-medium`), rounded-md
  pills with `px-2.5 py-1.5`; **active** = solid secondary surface (`bg-secondary`) with full
  foreground text; **inactive** = muted text, hover = faint muted fill. Items never wrap or
  shrink; at md–lg a "More ▾" dropdown holds secondary destinations.
- Right: notification bell (with red unread count badge, capped "99+") and the user menu
  (avatar with the student's initial; dropdown: name + roll number, Profile, Appearance, Install
  App, Send Feedback, Settings, Sign Out).
- On small screens the top bar shows logo + current page title (the wordmark and inline nav are
  hidden; mobile uses the bottom bar).

### 5.2 CURRENT STATE — mobile bottom navigation

- Fixed bottom bar: frosted dark (`bg-background/95` + `backdrop-blur-md`), top border, safe-area
  padding. Four equal columns: **Home, Attendance, History** tabs + **More**.
- Tab anatomy: icon (20px) over a 0.65rem label, min-height 56px, active = primary blue text;
  inactive = muted. "More" opens a bottom sheet listing the secondary destinations with icons
  and active highlighting.

### 5.3 REDESIGN DIRECTION — navigation

- **Keep the top-bar pattern** on desktop/laptop and the bottom-bar pattern on mobile — do not
  introduce a persistent left sidebar.
- Make the top bar **visually lighter and premium**: consider a subtle glass treatment
  (translucent dark surface + soft blur + hairline bottom border, see §12) so content scrolls
  beneath it; keep it compact (56–64px), quiet, and consistent.
- Reorganize top-level items to the redesigned IA: **Dashboard, Attendance, Timetable, Track,
  Quizzes, Calendar, History, Analytics** — short single-word labels; icons remain; active state
  stays a filled pill (evolve it: subtle primary-tinted pill or underlined emphasis).
- Keep utilities on the right: **Search** (new — global jump-to-subject/day), **Notifications**
  (bell + count), **Sync/PWA status** (install/update state), **Profile** avatar menu.
- Mobile: retain bottom navigation; consider four fixed tabs + More sheet (e.g. Home, Track,
  Attendance, Quizzes + More), with active tabs using the primary accent and a small filled
  indicator; keep 56px+ touch height and safe-area handling.

---

## 6. Visual Language

### 6.1 Branding (CURRENT STATE)

- **Logo mark**: an abstract glyph — a blue (#3B82F6) upward peak/chevron stroke with a white
  check-mark stroke crossing it (an "A"-like peak + verification check), drawn on a rounded dark
  slate (#0F172A) tile for app icons; the in-app mark uses the transparent version.
- **Wordmark**: "AttendanceDash Pro" in Geist Sans semibold, tight tracking, with "Pro" de-emphasized.
- App icons exist at 192/512 (any + maskable), plus apple-touch icon.
- PWA theme color: `#3B82F6`; background color: `#0a0a0a`.
- The redesign must preserve this mark and wordmark. It may refine their surroundings (nav,
  auth cards, splash) but not reinvent the identity.

### 6.2 Color system (CURRENT STATE)

The product is **dark-only** (dark theme is hard-coded; an Appearance modal exposes Dark as the
only supported option, with Light/System visibly disabled). All colors are CSS custom-property
tokens consumed by Tailwind v4:

| Token | Value | Usage |
|---|---|---|
| `background` | `#0a0a0a` (near-black) | App background |
| `card` | `#171717` (dark charcoal) | Cards, elevated flat surfaces |
| `popover` / `secondary` / `accent` | `#262626` (lighter charcoal) | Dialogs, popovers, active nav pills, secondary buttons |
| `muted` | `#171717` | Muted fills, tracks, hover washes (often at /30–/60 opacity) |
| `foreground` | `#f8fafc` (high-contrast white) | Primary text |
| `muted-foreground` | `#94a3b8` (blue-gray) | Secondary text, metadata, icons |
| `primary` | `#3B82F6` (blue) | Primary buttons, links, active accents, progress, today marker, event dots |
| `primary-foreground` | `#ffffff` | Text on primary |
| `success` | `#22c55e` (green) | Present, Healthy, Eligible, Safe skip |
| `warning` | `#f59e0b` (amber) | Watch, Recoverable, Pending emphasis |
| `destructive` | `#ef4444` (red) | Absent, Critical, Not Eligible, errors, unread badge |
| `border` / `input` | `#27272a` (subtle dark gray) | Hairline borders, input borders |
| `ring` | `#3B82F6` | Focus rings |

Two notable secondary treatments (CURRENT STATE, to be reconciled in the redesign):

- **Error glass surfaces**: load-failure cards use a deep red wash — `bg-red-950/20`,
  `border-red-900/50`, with `red-500` icon and `red-400` text (softer than solid destructive).
- **Lab stat accents** use Tailwind's `emerald-400` / `red-400` / `amber-400` rather than the
  semantic tokens — an inconsistency the redesign should normalize onto the token set.

**REDESIGN DIRECTION:** keep this exact palette as the base (it is the product's identity).
Refine it by: defining consistent tint rules (`color/15` fills with `color/30` borders for all
semantic badges — already the badge convention), normalizing the error-glass and lab-accent
outliers onto tokens, and optionally introducing one or two neutral elevation steps between
`card` and `popover` for layered surfaces (glass layers, sticky headers).

### 6.3 Typography (CURRENT STATE)

- **Family**: Geist Sans (via `next/font`) for everything; **Geist Mono** for subject codes and
  roll numbers (a deliberate, characterful pattern — codes always read as monospace).
  (Primitives reference a `font-heading` class but no heading font token is defined, so headings
  render in Geist Sans too — one family system in practice.)
- **Scale in use**:

| Role | Spec |
|---|---|
| Page title / greeting | 24px (text-2xl), bold, tight tracking |
| Card title | 16px (text-base), medium |
| Large stat (percentages, counters) | 30px (text-3xl), bold, `tabular-nums`, tight tracking |
| Medium stat | 20–24px bold `tabular-nums` |
| Body / list primary | 14px (text-sm); semibold for subject codes & names |
| Secondary / metadata | 12px (text-xs), `muted-foreground` |
| Micro overline labels | 11px, uppercase, wide tracking (e.g. "ELIGIBLE", "LECTURE") |
| Mobile nav label | 10.4px (0.65rem) |

- **REDESIGN DIRECTION:** keep Geist Sans + Geist Mono and this scale; formalize it as
  Display (32–40px, for a redesigned hero stat), Title (24), Card title (16), Body (14), Meta
  (12), Overline (11 uppercase). All numerals stay `tabular-nums`. Subject codes always mono.

### 6.4 Spacing, radius, borders, shadows (CURRENT STATE)

- **Radius**: base token `0.5rem`; scale: sm = 0.6×, md = 0.8×, lg = 1×, **xl = 1.4× (≈11px —
  used by cards, dialogs, large inputs)**. Buttons/inputs/badges: rounded-lg / rounded-full.
  Overall feel: softly rounded but restrained — not pill-shaped cards, not sharp corners.
- **Borders**: hairline `1px` in `#27272a`; cards use a **ring** (`ring-1 ring-border`) instead
  of box-shadows. Inner separators use `divide-y` at ~60% border opacity. Card footers have a
  top border + `bg-muted/50` wash.
- **Shadows**: essentially none in the current design (`shadow-none` on cards; dialogs pop via
  a ring + backdrop). The only strong shadow is the PWA update banner (`shadow-lg`).
- **Spacing**: 4px base; card padding 16px (`--card-spacing: 16px`); dashboard card grid gaps
  24px; card grids gap 16px; page-level vertical rhythm 24–32px; PageHeader bottom margin 32px.
- **REDESIGN DIRECTION:** keep the radius scale and hairline-ring language. Introduce a *soft,
  restrained elevation ladder* for glass/elevated layers: e.g. `0 1px 2px rgba(0,0,0,.4)` for
  cards, `0 8px 24px rgba(0,0,0,.45)` for dialogs/popovers/floating elements — subtle, never
  glowy. Increase whitespace on the Dashboard (see §7) while keeping dense work surfaces
  (History, Admin) compact.

### 6.5 Iconography (CURRENT STATE)

- **Lucide icons throughout** (stroke style, currentColor): nav (16px), bottom bar (20px),
  inline (14–16px), empty-state heroes (40px), status icons in badges (12px: CheckCircle2, X,
  Clock, AlertTriangle, Check, Calendar, Calculator, Sparkles, etc.).
- Icons are always **supporting**: every status icon is paired with a text label.
- **REDESIGN DIRECTION:** keep Lucide. Standardize sizes (16 inline / 20 nav / 24 feature) and
  keep icons monochrome `currentColor`; do not introduce multicolor or filled icon styles.

### 6.6 Motion (CURRENT STATE)

- Very restrained: `transition-colors` on interactive elements; dialogs animate in/out with
  ~100ms fade + 95% zoom (tw-animate-css); `Loader2` spinner for in-flight actions; skeletons
  pulse; buttons depress 1px on press; the update banner deliberately has no animation.
- **REDESIGN DIRECTION:** keep motion functional and short (100–200ms, ease-out). Acceptable
  additions: gentle fade/slide for page content, number transitions on hero stats, subtle
  blur-in for glass layers. Never: parallax, glow pulses, bouncing badges.

---

## 7. Dashboard Philosophy

### 7.1 CURRENT STATE — what Home shows today

`/dashboard` renders a greeting header ("Good Morning/Afternoon/Evening, {FirstName}" + long
date) and, in a
two-column grid (lg+), **six equally-weighted cards** (each with skeleton loaders):

1. **Today's Attendance** — date, LIVE/TEACHING DAY badge, list of every class today (code,
   type badge, name, Present/Absent/Cancelled/Pending badge), footer counts ("3 of 5 classes
   attended · 2 pending").
2. **Overall Attendance** — 30px percentage, status badge (Healthy/Watch/Critical), attended ·
   recorded · pending counts, forecast-if-all-pending, week-over-week delta (green/red with
   arrow), full progress bar.
3. **This Week** — week range, weekly % + delta, up to six weekly rows (date, colored mini-bar,
   %, attended/recorded/pending) with current week highlighted, "Best this week" / "Needs
   attention" subjects.
4. **Quiz Snapshot** — next quiz date + eligibility threshold, three counters (Eligible /
   Attention / Not eligible in green/amber/red), "View Quiz Eligibility" link.
5. **Attention Required** — list of subjects below target (code, status badge, %, forecast) or
   an "All subjects on track" empty state, "View plan" link.
6. **Upcoming Events** — list with date chips (month/day in a bordered tile), event name, type
   badge, subject code, "View All Events" link.

Plus: a dismissible "Getting started" hint for first-use accounts, and a non-blocking warning
banner when analytics fail.

**Diagnosis (agreed redesign problem):** every card renders *full* detail, so Home competes with
the detail pages and reads like a data warehouse. All six cards are visually equal — nothing
tells the student what matters *right now*. Information density is high; whitespace is minimal.

### 7.2 REDESIGN DIRECTION — the command-center Home

The redesigned Dashboard must answer four questions in strict visual priority:

1. **"How is my attendance?"** → A single **hero status block** (largest element on the page):
   overall percentage as a large display number + one unambiguous status word (Healthy / Watch /
   Critical) with its semantic color + tiny context (attended/recorded, delta vs last week) and
   a slim progress bar. One prominent CTA: **"View Attendance"** (→ Attendance page).
2. **"Am I eligible or at risk?"** → One compact **eligibility snapshot**: next quiz (label +
   date + threshold) and a simple three-part summary (Eligible / Attention / Not eligible
   counts); if any subject needs attention, surface the worst one or two codes inline. CTA:
   **"View Quizzes"**. This replaces both the current Quiz Snapshot and Attention Required cards
   as a single calm unit (detail lives on the Quizzes page).
3. **"What is happening today?"** → A **today strip**: the *next class* (time + subject) given
   visual prominence, followed by a compact, scannable list of today's remaining classes with
   their marking state; quick entry to **Track** (Mark Attendance) — ideally a one-tap
   "Mark attendance" affordance. Today's full detail belongs to Track/Timetable.
4. **"Anything important?"** → A short **alerts feed** (unread notification highlights, academic
   events in the next few days, threshold warnings), each with icon + one line + time; CTA to
   Notifications/Calendar/Events.

**Layout guidance:** desktop uses a asymmetric grid — hero spanning prominently, today strip
beside or below it, snapshot and alerts as quieter supporting units; generous outer margins and
24–32px gaps; at most ~4 visible units, each visually *ranked*, not six equal cards. Mobile
stacks them in the same priority order, hero first, thumb-reachable Track action.

**Explicitly remove from Home:** the six-week weekly trend table (→ Analytics), per-subject
attention rows with forecasts (→ Quizzes/Attendance), the full event list (→ Calendar/Events,
keep only 2–3 alert lines), counts duplicated in multiple cards. A first-run "Getting started"
hint may remain.

---

## 8. Page-by-Page Experience

> Each subsection: **CURRENT STATE** (what exists) then **REDESIGN DIRECTION** (what changes).

### 8.1 Attendance (Subjects Overview) — `/subjects`

**CURRENT:** page title + one-line description; responsive grid (1/2/3 columns) of
**SubjectAttendanceCards**: header = subject code (mono, bold) + THEORY/LAB badge + health badge
(Healthy/Watch/At Risk/Critical — Critical solid red, others tinted); 30px percentage
("Overall" = (Lecture%+Tutorial%)/2, or "Practical" for lab-only subjects); thin progress bar
colored by health; two sub-blocks for Lecture and Tutorial (small tinted panels with % and
attended counts, or "No tutorials"); a formula caption; an expandable **View Details** panel
with per-category rows and a "pending never counted as absent" note. Lab-only cards show
practical sessions attended and the mid-sem practical date.

**REDESIGN:** keep the card grid as the depth surface. Improve scannability: consistent health
color + progress in every card, clearer hierarchy between code/name/percentage, and a
subject-detail affordance (per-subject drill-down or richer expansion) including recent trend.
This page is the landing target for the dashboard's hero CTA.

### 8.2 Timetable — new destination

**CURRENT:** no student-facing weekly timetable page exists. The timetable is admin-configured;
students only see **today's resolved schedule** (via Mark Attendance and the Calendar's day
detail). Class types are Lecture/Tutorial/Practical; sessions can be extras, cancelled,
quiz-day occurrences, or substitutions.

**REDESIGN DIRECTION:** add a **weekly Timetable page**: a week grid (time slots × days,
Monday-start respecting the week-start preference) showing the student's *resolved* subjects
(their concrete electives, not slot labels) per slot, with compact badges for type, and
state-aware rendering for today (highlight) and cancelled days. It must read at a glance on
mobile (vertical day-list fallback or horizontal day switcher). This page explains the student's
week; Track explains their day.

### 8.3 Track / Mark Attendance — `/tools/laboratory`

**CURRENT:** the daily marking surface, centered at `max-w-2xl`: date navigation (prev/next
arrows, jump-to-date input, Today button, clamped to semester bounds); a summary card (total
classes, recorded/total, progress bar, remaining/absent counts) with a full-width green **Mark
all present** button (guarded by a confirmation dialog showing the real pending count); then one
**session card per class**: time range (or "Extra Class"/"TBD"), subject code (mono), full
subject name, type badges (LECTURE/TUTORIAL/PRACTICAL, plus QUIZ DAY, MID-SEM PRACTICAL, EXTRA),
and state-dependent actions — pending ⇒ Present/Absent outline buttons (green/red tinted hover);
marked ⇒ status icon+text with a ghost "Change" toggle; cancelled ⇒ grayscale 50% opacity card;
future dates ⇒ "Upcoming" badge and **view-only** (no mutation controls). Failures surface as
inline error banners + toasts.

**REDESIGN:** keep this focused, single-column, thumb-friendly pattern — it is the product's
core write moment. Refinements: make the "next unmarked class" visually primary; larger Present/
Absent targets with icon + label; a subtle "streak today" progress (e.g. 3 of 5 marked); keep
explicit confirmation for bulk actions; keep future/cancelled semantics exactly as they are.

### 8.4 Quizzes (Quiz Eligibility) — `/tools/quiz-schedule`

**CURRENT:** centered `max-w-4xl`: an info card explaining the criteria (Criterion I/II, both
(Lecture%+Tutorial%)/2, thresholds 70% Quiz I / 75% Quiz II & III, counting windows); a row of
**cycle pills** (Quiz I / II / III, `aria-pressed`, active = solid primary); then one
**QuizEligibilityCard per theory subject**: header (code mono + THEORY badge + name + quiz date
+ window range + state badge Eligible/Recoverable/Not Eligible/Unresolved); three progress rows
(Lecture, Tutorial, Average — each with attended/total/pending and % vs required); an expandable
**View Calculation** panel: Criterion I and II rows with PASS/FAIL badges (Check/X icons),
average/required/formula text, explanation sentences, a Final Result row (ELIGIBLE / NOT
ELIGIBLE), and **Must Attend / Safe Skip** optimization tiles (deficits per category, only when
reachable) or an "cannot be recovered" note.

**REDESIGN:** this is already a strong depth surface — keep its structure. Improve the cycle
switcher into a segmented control, tighten the criterion rows into a cleaner table-like layout,
and make Must-attend/Safe-skip the visual hero of each card (it is the actionable payoff).
The dashboard eligibility snapshot links here.

### 8.5 Calendar — `/calendar`

**CURRENT:** PageHeader with month navigation (prev/next icon buttons, month label, Today
button; navigation gated by semester bounds). Main area: a **month grid** (7 columns,
Monday/Sunday start per preference) inside a card — working-day cells are card-colored with the
day number in a circle (today = solid primary circle; selected = primary/10 fill + 2px primary
ring; events = small primary dot + count; working cells show a green "N classes" line;
non-working cells are muted with reason text on wider cells, a dot on mobile); a legend row
(Event / Today / Selected / Non-working). Right rail (340px, sticky on lg): **DayDetail** card —
long date, Working/Non-working + Teaching day badges, substitution note ("Follows sunday
schedule"), reason text, a "Scheduled classes" count panel, and the day's events with a "View
all" link. Loading = grid skeleton; month switches keep the previous grid at 70% opacity with a
"Loading …" note.

**REDESIGN:** keep the grid + detail rail layout (it works). Refine cell states, increase cell
tap size on mobile, and consider a mobile day-switcher strip beneath the grid. Keep every
state reachable by more than color (dots + counts + text).

### 8.6 History — `/history`

**CURRENT:** PageHeader with semester context line ("Semester · date range"); a **summary card**
(tinted muted) with overall filtered % and a 3×/5-column grid of stat tiles (Total / Present /
Absent / Pending / Cancelled, colored); a **filters card** — subject select, state select
(Present/Absent/Pending/Cancelled), from/to date inputs (dark color-scheme), debounced search
input — with a Reset button when active; then the **session log**: one card per session (date
in a circular tile, subject code mono + type badge + EXTRA badge, subject name, time + "Logged
HH:MM", status badge right-aligned; cancelled rows grayscale/50%); "Load more (N remaining)"
pagination (50/page); "Showing X of Y sessions" caption. Empty and error states included.

**REDESIGN:** keep the summary + filters + log structure. Consider grouping by date with sticky
day headers on mobile, replacing per-row cards with a denser list/row style on desktop, and
harmonizing the stat tiles with the redesigned stat language.

### 8.7 Analytics — new destination

**CURRENT:** no dedicated analytics page. The backend computes an analytics overview (overall +
per-subject current/forecast percentages, weekly series with deltas, weekly best/needs-attention
subjects) and the frontend renders pieces of it inside dashboard cards. There is **no chart
library** — the only "chart" is the hand-rolled weekly mini-bar row (6px-high rounded bars,
green ≥80% / amber ≥60% / red below, "—" for gap weeks, current week ringed).

**REDESIGN DIRECTION:** add an **Analytics page** as the home of trends: overall weekly trend
(bar or line chart), per-subject trend and forecast-vs-current comparisons, safe-skip capacity
over time, and semester progress. Keep charts **simple, token-colored and calm**: thin rounded
bars/lines using success/warning/destructive + primary, gridlines in border color, `tabular-nums`
labels, generous spacing — a quiet analytical surface, not a BI dashboard. It absorbs the weekly
trend detail currently duplicated on Home.

### 8.8 Lab Experiments — `/laboratory`

**CURRENT:** subject selector + segmented tab group (Practical Attendance / Experiments /
Activity) in a muted pill container; Practical Attendance tab = two cards (stat tiles
Present/Absent/Pending/Attendance with emerald/red/amber accents + primary progress bar;
Mid-Semester Practical designation card with date/status); Experiments tab = experiment
checklist with status badges and progress; Activity tab = recent lab activity feed.

**REDESIGN:** keep the tabbed structure; normalize stat colors to semantic tokens; align card
styles with the refined surface language.

### 8.9 Academic Events — `/tools/events`

**CURRENT:** filter bar (Active/Inactive toggle, type select, date range) + "Add Event" button;
event list rows with type badges (Extra/WARNING-tinted, Cancelled/neutral, Holiday/success,
Today/primary), subject context and dates; students may add/edit/deactivate the flexible
subject-scoped types (extra class, cancellation, surprise quiz) via dialogs; global/closure
events are admin-only and render read-only for students.

**REDESIGN:** keep the student-adjustable event model visible and simple; the redesigned Home
alerts feed should deep-link here.

### 8.10 Notifications

**CURRENT STATE:** a bell in the top bar with a red unread count (capped "99+"); the
**Notification Center** opens as a shell dialog (bottom-sheet on mobile): a persisted inbox,
newest first, unread rows emphasized; each row has a kind chip + tinted icon tile — Class
reminder (primary/blue, BookOpen), Quiz (warning/amber, CalendarClock), Attendance threshold &
Must attend (danger/red, AlertTriangle/Target), Safe skip (success/green, CheckCircle2), Event
(neutral, CalendarDays) — plus message, subject context, occurrence date, per-row "Mark as
read" and dismiss actions with an Undo toast, a mark-all action, explicit error banners (no
fake optimistic updates), and skeleton loading. Push notifications are wired via service
worker; a settings toggle (class reminders) gates them.

**REDESIGN:** keep this model. In the redesigned Home, surface the 2–3 most important unread
notifications as the alerts feed. Keep the sheet-on-mobile pattern.

### 8.11 Profile, Settings & shell utilities

**CURRENT STATE:**
- **Profile modal & `/profile` page**: avatar with initial, display name, roll number (mono);
  field list (divide-y rows) for University Roll Number, Program, Semester, Academic Session,
  Semester Start, First Quiz Date. Page variant adds Sign Out.
- **Settings modal**: three API-backed preferences — Class reminders toggle, Auto-mark-present
  toggle (storage-only), Week starts on (Sunday/Monday) — with explicit save states.
- **Appearance modal**: Dark / Light / System radio group where only Dark is enabled, with an
  explanatory note (light palette doesn't exist yet).
- **Install App modal** (PWA install) and **Send Feedback** modal.
- **ConfirmDialog** guards meaningful/destructive actions; confirm labels describe the actual
  operation ("Mark 3 classes present?"), stay open while the mutation runs, and prevent
  double-submission.

**REDESIGN:** keep these utilities; visually refresh as glass dialogs (§12). A light theme
remains optional future work — the redesign is dark-first.

### 8.12 Authentication — `/login`, `/signup`

**CURRENT STATE:** centered `max-w-md` card on the app background: wordmark heading +
"Student Portal" subtitle; labeled inputs (Roll Number with 13-digit placeholder, Password with
show/hide eye toggle); session-expired notice (amber tinted) and error banner (red tinted);
full-width primary "Sign in" button; link to the other auth page. Signup mirrors it ("Create
Account") with registration fields. No imagery, no marketing content — pure focused utility.

**REDESIGN:** this is the place for a touch of brand presence: keep the centered card but
consider a subtle glass card, the logo mark above the wordmark, and a soft ambient background
treatment (very low-contrast blue-tinted radial glow or layered dark gradient) — restrained, no
illustration overload.

---

## 9. Academic Context & Personalization

### 9.1 The resolved academic model (CURRENT STATE)

Every student belongs to an academic context — program, semester, academic session, **section,
subsection**, and two **department-elective slots (DE-I, DE-II)** from which they have concrete
selected subjects. The backend resolves this context into the student's actual subjects and
class sessions. The profile carries: `display_name`, `roll_number`, `program`, `semester_name`,
`academic_session`, `section_name`, `subsection_name`, `elective_i`, `elective_ii`, semester
start/end, first quiz date. Administrators correct electives and assign subsections.

### 9.2 Elective display rules (CURRENT STATE + binding for redesign)

- Subjects carry an `elective_slot` marker (ELECTIVE_I / ELECTIVE_II) or none. Sessions and
  events can be scoped to an elective slot; the API resolves them per student.
- **The UI always shows the concrete resolved subject** — e.g. **BCS-058 · Data Warehousing &
  Data Mining** — never a bare "Department Elective-II" slot label as the student's subject
  name. Slot labels exist only as admin-facing categorization; students with different
  electives correctly see different subjects/sessions for the same slot.
- Attendance, eligibility, marking, calendar and events are all **enrollment-scoped**: the
  student only ever sees their own resolved reality. No screen may imply that all students share
  identical classes (e.g., never phrase copy like "your section's DE-II class" in a way that
  assumes one shared subject).
- Practical implication for design: where a timetable or session list could contain an elective
  slot, render the resolved subject code + name; if a resolution is genuinely unresolved, show
  an explicit neutral state (e.g. "Unresolved" badge, explanatory line) rather than inventing a
  subject.

### 9.3 Personalization surfaces

- Greeting uses the student's first name; avatar shows the initial; roll number is always mono.
- Week-start preference rotates the calendar grid; class-reminder preference gates reminders.
- First-use accounts get a dismissible "Getting started" hint with real links.
- **REDESIGN DIRECTION:** the Dashboard greeting row may also carry quiet context chips
  (semester name, section) — context the student can verify at a glance without exposing
  backend structure.

---

## 10. Surfaces & Glassmorphism

### 10.1 CURRENT STATE — surface hierarchy

| Layer | Treatment |
|---|---|
| App background | `#0a0a0a` flat |
| Cards / panels | `#171717`, 1px ring `#27272a`, radius ~11px, no shadow |
| Popovers / dialogs | `#262626`, ring `foreground/10`, radius-xl, `bg-black/10` backdrop with slight blur |
| Card footers / inset panels | `bg-muted/50` or `bg-muted/30` washes with hairline borders |
| Mobile bottom bar | `bg-background/95` + `backdrop-blur-md` (the only real glass today) |
| Error surfaces | `bg-red-950/20` + `border-red-900/50` deep-red glass |

Note: a shared `GlassCard` component exists but currently renders as an ordinary opaque card —
the "glass" language is aspirational in the code, not yet expressed.

### 10.2 REDESIGN DIRECTION — glass, used sparingly

Introduce a consistent **glass recipe** (one recipe, reused):

- Surface: `rgba(23,23,23,0.6–0.75)` fill + `backdrop-blur(12–16px)` + 1px border
  `rgba(255,255,255,0.08)` + a soft shadow (`0 8px 24px rgba(0,0,0,.35–.45)`).
- **Apply to:** the top navigation bar (content scrolls beneath), dialogs and popovers, the
  mobile bottom bar and More sheet, floating contextual elements (toasts, update banner),
  and at most **one** emphasized dashboard unit (the hero status block) if it aids hierarchy.
- **Never** apply glass to: dense data lists, tables, calendar cells, forms, or everything on
  screen. Opaque `card` remains the default surface; glass marks *elevation and float*, not
  style.
- Ambient background (optional, dashboard/auth only): an extremely subtle blue-tinted radial
  glow or two layered dark shapes at low opacity behind the content — always below 6–8%
  perceived contrast so text contrast is untouched.
- Readability rule: any text on glass must keep the token contrast; if blur is unsupported,
  surfaces degrade to opaque token colors.

---

## 11. Components

### 11.1 CURRENT STATE — component inventory & specs

**Buttons** (`rounded-lg`, medium weight, 40px height on mobile / 32px on `sm+` — a deliberate
touch-first foundation; focus = 3px primary/50 ring):

| Variant | Look |
|---|---|
| default (primary) | solid `#3B82F6`, white text, hover 80% opacity |
| outline | 1px border, transparent/dark bg, hover muted fill |
| secondary | solid `#262626` |
| ghost | no chrome, hover muted fill |
| destructive | **soft** — `destructive/10` fill, red text (never solid red) |
| link | primary text, underline on hover |

Sizes include icon-only squares (40/36/28px). One context-specific override exists: a solid
green "Mark all present" (bg-success) — the redesign should promote this to a proper success
button variant. Buttons depress 1px on press.

**Inputs & selects:** 40px mobile / 32px desktop, rounded-lg, transparent bg with dark input
tint, hairline border, focus ring; date inputs use native dark color-scheme; labels are
11px uppercase micro-labels above fields (History) or 14px medium (auth).

**Cards:** flex-column, radius-xl (~11px), ring border, 16px internal padding; header rows with
title + right-aligned badge/action; footers with top border + muted wash; `data-size="sm"`
variant with tighter spacing. Lists inside cards use `divide-y` rows with 12px vertical padding.

**Badges:** 20px-tall pill (fully rounded via the `rounded-4xl` token), 12px medium text, variants: tinted semantics —
`success` / `warning` / `danger` / `primary` / `neutral` (all `bg-x/15` + `text-x` +
`border-x/30`) plus `outline` (hairline) and solid `default`. Frequently downsized to
`text-[11px]` uppercase tracking-wider chips for types (LECTURE, THEORY, EXTRA). Status badges
often embed 12px icons (Check, X, Clock).

**Progress bars:** 4px (or 6px) full-width rounded track in `bg-muted`; solid color fill by
variant (primary/success/warning/destructive); used for overall attendance, weekly bars,
eligibility rows, marking progress.

**Dialogs & sheets:** centered rounded-xl popover-colored dialog with header (16px medium
title + 14px muted description), body, footer with border-top + muted wash and right-aligned
actions; close icon top-right; ~100ms fade/zoom animation; **mobileSheet** variant docks
bottom with rounded top (used for notifications). Sheets slide from the bottom with rounded-t
corners.

**Toasts:** custom lightweight layer (max 3 visible, bottom of viewport above the mobile nav):
icon (CheckCircle2/XCircle/AlertTriangle/Info) + title + optional description, semantic colors,
auto-dismiss 5s (8s for errors/warnings), optional action (Undo), politely/assertively
announced.

**Skeletons:** `animate-pulse` muted blocks shaped like the target content (per-card skeleton
components exist for every dashboard card, the calendar grid, history rows).

**Empty states:** centered 40px muted icon, 16px semibold title, 14px muted one-liner, inside a
card (shared `EmptyState`); every list has one (no classes today, no events, no quizzes, no
matching history, all subjects on track with a green-tinted icon).

**Error states:** shared `ErrorState` card in the deep-red glass treatment with icon, title,
message and a Retry button; smaller inline red-tinted banners for per-card failures;
route-level error boundary and branded 404.

**Tables:** no true data tables exist in the student app — structured rows are card lists or
divide-y lists (the Admin Portal has dense table grids). If the redesign adds tables
(e.g. Analytics), keep hairline rows, uppercase micro-headers, `tabular-nums` right-aligned
numbers.

**Avatars:** initial-letter fallback in a muted bordered circle (28–40px).

**Charts:** none (library-free); only the weekly mini-bars described in §8.7.

### 11.2 REDESIGN DIRECTION — component evolution

- Keep this exact component vocabulary; refine consistency rather than replacing parts.
- Normalize: one success button variant; one error-surface recipe; lab accent colors → tokens.
- Add only what the redesigned IA needs: segmented controls (cycle/tab switchers), a search
  field/command palette, simple chart primitives (bars/lines/sparklines), a weekly timetable
  grid, and a hero status block pattern.
- Every new component must ship its loading (skeleton), empty, and error variants — this is an
  existing, enforced product convention.

---

## 12. States & Status Semantics

### 12.1 CURRENT STATE — canonical status vocabulary

Student-facing words are canonical (the codebase documents this mapping; the UI never invents
labels):

| Domain | Values (label → color treatment) |
|---|---|
| Class marking | **Present** (success, CheckCircle2) · **Absent** (danger, XCircle) · **Pending** (outline badge) · **Cancelled** (neutral; row grayscale/50%) · **Upcoming** (neutral, Clock, future dates, view-only) |
| Attendance health | **Healthy** (success) · **Watch** (warning) · **At Risk** (danger tinted) · **Critical** (danger **solid**) — dashboards also use legacy bands SAFE→Healthy, WATCH→Watch, CRITICAL→Critical; weekly bars: green ≥80%, amber ≥60%, red below |
| Quiz eligibility | **Eligible** (success) · **Recoverable** (warning) · **Not Eligible** (danger) · **Unresolved** (neutral) · per-criterion **PASS/FAIL** badges (Check/X) |
| Subject category | **THEORY** (primary tint) · **LAB** (neutral) |
| Class type | **Lecture / Tutorial / Practical** (outline micro-chips) |
| Session designation | **Extra**, **Quiz Day** (primary), **Mid-sem Practical** (outline) |
| Notification kinds | Class reminder (primary) · Quiz (warning) · Attendance threshold / Must attend (danger) · Safe skip (success) · Event (neutral) |
| Calendar day | Working day (success badge) · Non-working day (neutral + reason) · Teaching day (primary) · substitution note (primary text) |

### 12.2 Rules (binding for redesign)

1. **Never color alone**: every status pairs a color with a text label, and where possible an
   icon (Present ✓, Absent ✕, Upcoming ⏱, PASS ✓). Toasts, badges and progress all follow this.
2. Semantic colors mean exactly one thing each (green = good/present/eligible/safe; amber =
   watch/pending/recoverable; red = absent/critical/ineligible/error; blue = primary action /
   informational / today / selected). Do not repurpose them decoratively.
3. UI states beyond status: **Loading** (skeletons shaped like content; per-row spinners;
   disabled + spinner on submitting buttons; dimmed grid during month switches), **Empty**
   (icon + title + guidance), **Error** (honest failure + Retry; never silent, never fake
   success), **Success** (toast with real counts), **Updated/Info** (update banner, session
   expired notice). Bulk/destructive actions always confirm explicitly first.

---

## 13. Responsive Design

### 13.1 CURRENT STATE

- Breakpoints are Tailwind defaults; the shell switches at **md (768px)** (bottom nav → top-bar
  inline nav with "More") and **lg (1024px)** (full inline nav; two-column dashboard grid;
  340px calendar detail rail; 3-column subject grid).
- Touch-first controls: 40px control heights on mobile, shrinking to 32px on `sm+` — the inverse
  of most desktop-first systems, and a convention to keep.
- The mobile bottom bar is fixed with safe-area padding and content reserves clearance.
- Long content truncates (`truncate`/`line-clamp`) with `title` tooltips; badge rows wrap;
  calendar cells grow (min-height 48→64px) and hide reason text on small cells; the calendar
  month-nav row wraps at 320px; dialogs become bottom sheets on mobile where appropriate.
- Dashboard/subject/history layouts reflow 1-col → 2/3-col; Mark Attendance stays single-column
  centered at all sizes (a deliberate focus mode).

### 13.2 REDESIGN DIRECTION

- **Mobile is a first-class primary device** (between-class checks): the Home hero, today strip
  and Track actions must be perfect at 360–430px; bottom navigation remains; keep ≥44px targets.
- **Tablet (768–1024):** two-pane layouts where they help (calendar, timetable, analytics);
  navigation must never overflow (retain the "More" overflow strategy).
- **Desktop (≥1280):** the command-center dashboard with generous margins; content max-width
  ~1150px; avoid stretched full-bleed data rows.
- Tables/lists on mobile must become cards or grouped lists; charts must remain legible at
  small sizes (fewer series, direct labels).

---

## 14. Accessibility

### 14.1 CURRENT STATE — patterns already in place (keep & extend)

- Semantic `aria-current="page"` on nav links; `aria-pressed` on toggle groups (quiz cycles,
  lab tabs, calendar cells); named `role="group"` containers; icon-only buttons carry
  `aria-label`s; calendar cells expose full descriptive `aria-label`s (date, working state,
  classes, events, selected).
- Focus visibility: 2–3px `ring` focus styles on all interactive elements (token `ring`).
- Live regions: polite for row-level async errors, assertive for error/warning toasts;
  `role="status"` banners for session-expired and PWA updates.
- Color-independence (§12), 40px touch targets, truncation with tooltips, dark color-scheme
  inputs, reduced decorative motion.

### 14.2 REDESIGN DIRECTION

- Hold WCAG AA contrast on the dark palette (body text `#f8fafc` on `#0a0a0a`/`#171717` easily
  passes; watch `muted-foreground` on tinted washes and any text placed over glass).
- Full keyboard paths through the top bar, command palette (if added), dialogs (focus trap,
  Escape — already via Base UI) and the calendar grid.
- Respect `prefers-reduced-motion` for any new motion; screen-reader text for chart trends.

---

## 15. UX Principles (product-specific)

1. **Backend is truth; UI renders honestly.** Percentages, statuses, forecasts, windows and
   dates arrive computed. The UI formats and reveals — it never recomputes or fabricates. Show
   real counts in confirmations and results ("Marked 3 of 4 classes present — 1 failed").
2. **Pending ≠ Absent.** Pending sessions are visually distinct and explicitly not counted as
   absences; copy says so where percentages are shown.
3. **Confirm meaningful writes.** Bulk and destructive actions open a dialog describing the real
   effect; in-flight locks prevent double-submission; the dialog closes only when the mutation
   settles.
4. **Future is view-only.** Upcoming days show schedule but no marking controls; the calendar
   cannot leave the semester range; Mark Attendance clamps navigation to semester bounds.
5. **Cancelled is visible but receded.** Grayscale + 50% opacity + neutral badge — never hidden
   (students must know a class was cancelled).
6. **One canonical vocabulary.** Present/Absent/Pending/Cancelled; Healthy/Watch/At Risk/
   Critical; Eligible/Recoverable/Not Eligible; Quiz I/II/III; Lecture/Tutorial/Practical;
   Theory/Lab. Do not introduce synonyms.
7. **Resolved context only.** Show concrete subjects (§9.2); never expose slot labels or
   backend structure to students.
8. **Depth by navigation, not by density.** Every dashboard unit summarizes and links out;
   detail pages may be dense; the dashboard may not.
9. **Progressive disclosure for math.** Eligibility criteria, formulas and calculations hide
   behind "View Calculation"/"View Details" expanders; headlines stay simple.
10. **PWA is part of the UX.** Install prompts, update banner and sync/notification states are
    first-class, calm, and dismissible — never modal nagware.

---

## 16. Redesign Priorities (ordered)

1. **Dashboard re-architecture** (§7.2): hero attendance status → eligibility snapshot → today
   strip → alerts; remove duplicated detail; generous spacing. Highest-impact change.
2. **Navigation polish** (§5.3): glass top bar, IA renamed to Dashboard / Attendance / Timetable
   / Track / Quizzes / Calendar / History / Analytics; search + sync status in the utility
   cluster; refined mobile bottom bar.
3. **New surfaces**: Timetable (weekly grid) and Analytics (trends) — seeded by existing data
   and the weekly-bar visual language.
4. **Surface & glass system** (§10): one glass recipe for nav/dialogs/floating layers; a soft
   elevation ladder; normalized error-glass and lab accents; success button variant.
5. **Component consistency pass** (§11.2): segmented controls, unified badge sizing rules,
   chart primitives, subject-detail drill-down.
6. **Mobile excellence pass** (§13.2): 360px-first checks on Home, Track, Calendar, Timetable.
7. **Auth & shell refresh** (§8.12): branded, subtly ambient, glass auth cards; refresh shell
   modals.

---

## 17. Things to Avoid

- **Do not** reintroduce a persistent left sidebar; navigation is top-bar + mobile bottom bar.
- **Do not** restyle the existing dashboard as-is — the redesign must re-prioritize information,
  not just reskin six equal cards.
- **Do not** duplicate detail across pages: no weekly trend tables on Home, no full subject
  lists on Quizzes, no full event lists on Home.
- **Do not** glassmorphism-everything: no translucent data tables, forms, or calendar cells; no
  glow, neon, heavy gradients, animated backgrounds, or dark-UI "cyberpunk" styling.
- **Do not** switch to a light theme or dual-theme layouts (dark-only product today; light is a
  separate future effort).
- **Do not** invent features: no ERP/finance/BI/project-management/AI-chat/cryptocurrency
  framing, no gradebooks, no fee data, no social feeds, no generic SaaS marketing sections.
- **Do not** replace the brand: keep the blue peak-and-check mark, the wordmark treatment,
  Geist, the near-black + `#3B82F6` identity, and the pill-badge language.
- **Do not** break the honesty rules: no optimistic fake successes, no fabricated numbers, no
  hiding errors, no auto-reloading over the user, no marking attendance for future dates.
- **Do not** convey status with color alone or introduce new status colors outside the token
  set.
- **Do not** show elective slot labels ("DE-II") where a concrete subject should appear, and
  never imply all students share the same sessions.

---

## 18. Appendix — Current-vs-Redesign quick reference

| Aspect | Current state (verified) | Redesign direction |
|---|---|---|
| Theme | Dark-only tokens (`#0a0a0a`/`#171717`/`#262626`, blue `#3B82F6`) | Same palette, refined elevation + subtle glass layers |
| Typography | Geist Sans + Geist Mono (codes), 11–30px scale, tabular numerals | Same + formalized display size for hero stats |
| Nav | Top bar (h-14) + mobile bottom bar + More sheet/dropdown | Same patterns, premium glass top bar, IA renamed/extended |
| Dashboard | 6 equal detail-dense cards in 2-col grid | Ranked command center: hero, snapshot, today strip, alerts |
| Attendance | Subject card grid w/ health bands | Kept as depth surface; improved scannability + drill-down |
| Timetable | Not visible to students | New weekly resolved-timetable page |
| Track | "Mark Attendance" daily surface | Kept; clearer next-action emphasis |
| Quizzes | Cycle pills + per-subject eligibility cards | Kept; must-attend/safe-skip promoted, segmented control |
| Calendar | Month grid + sticky detail rail | Kept; refined cells + mobile day strip |
| History | Summary + filters + session card log | Kept; denser grouping, harmonized tiles |
| Analytics | Backend-computed, only shown in dashboard cards | New dedicated trends page, simple token-colored charts |
| Glass | Only the mobile bottom bar blurs; "GlassCard" is opaque | Defined recipe on nav/dialogs/floating + hero only |
| Status | Full semantic vocabulary + icons + labels (color never alone) | Preserved exactly; normalized inconsistencies |
| Admin Portal | Same tokens, workbench shell, tables + dialogs | Visually consistent, out of scope for student redesign |

### Documented assumptions & ambiguities

1. The repo already implements top navigation + mobile bottom navigation (a prior redesign
   phase); no left sidebar exists. The redesign brief's nav guidance is therefore treated as
   "keep and refine."
2. "Track" in the brief maps to the existing **Mark Attendance** page (`/tools/laboratory`);
   the component vocabulary (`TrackSessionCard`) uses this name already.
3. **Timetable** and **Analytics** student pages do not exist today; both are specified as new
   destinations built from data the backend already provides (timetable-derived sessions;
   analytics overview endpoints). No chart library currently exists — charts must be simple.
4. `GlassCard` exists in code but renders opaque today; glassmorphism guidance describes the
   target state, clearly labeled as redesign.
5. The student-facing full **weekly** timetable is not rendered anywhere today (only resolved
   daily sessions); the Timetable page spec is the redesign's addition, consistent with how
   admin timetable data resolves into student sessions.
6. Light mode is explicitly unsupported (Appearance modal disables Light/System with an
   explanatory note).
7. Minor token inconsistencies exist in the current code (lab page uses `emerald-400`-style
   accents; error surfaces use a red-glass recipe); both are documented and slated for
   normalization rather than treated as identity.
