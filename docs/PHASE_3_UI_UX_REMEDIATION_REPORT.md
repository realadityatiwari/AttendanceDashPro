# Phase 3 — P2 UI/UX Remediation Report

**Date:** 2026-10-02
**Scope:** The eighteen P2 issues from `docs/UI_UX_AUDIT_REPORT.md` — UIA-004, UIA-013, UIA-015, UIA-016, UIA-017, UIA-018, UIA-019, UIA-021, UIA-022, UIA-023, UIA-024, UIA-025, UIA-026, UIA-027, UIA-029, UIA-030, UIA-031, UIA-043.
**Discipline:** Strictly frontend-only remediation. Zero changes to backend APIs, schemas, migrations, calculation engines, or notification pipelines. Zero modifications to Phase 1 P0 fixes or Phase 2 P1 behavior beyond the shared primitives those fixes already use. No P3 issues were addressed.

**Prerequisite note (working-tree state):** At the start of this phase the working tree contained the P1 regression tests but only **partial** P1 source changes (28/76 tests failing). Because P2 work necessarily rewrites the same files (`QuizEligibilityCard`, `OverallAttendanceCard`, status/canonical modules, nav, profile, de-jargon copy), the missing P1 behavior was **restored inside P2-touched files as a prerequisite**, not re-implemented as new P2 work. Section 9 lists exactly what was restored; all P1 tests are green and no P1 behavior was reinterpreted.

---

## 1. Executive Summary & Remediation Matrix

| Issue ID | Description | File(s) Changed | Test Status | Runtime Verification Status |
|---|---|---|---|---|
| **UIA-004** | Consolidate duplicated formula captions; no uppercase formulas | `src/lib/formula.ts` (new)<br>`src/app/(authenticated)/subjects/page.tsx`<br>`src/app/(authenticated)/tools/quiz-schedule/page.tsx`<br>`src/components/dashboard/SubjectAttendanceCard.tsx`<br>`src/components/quiz/QuizEligibilityCard.tsx` | ✅ `src/lib/designSystem.test.ts` (2), `src/components/dashboard/SubjectAttendanceCard.test.tsx` (3) | ✅ Formula appears exactly once per page, sentence case; zero "Formula:" rows; quiz eyebrow sentence-cased |
| **UIA-013** | Eliminate pre-login authenticated-shell flash | `src/components/layout/AuthGate.tsx` (new)<br>`src/app/(authenticated)/layout.tsx`<br>`src/contexts/AuthContext.tsx` | ✅ `src/components/layout/AuthGate.test.tsx` (3) | ✅ SSR `/dashboard` contains only "Loading your session…", 0 shell markers |
| **UIA-015** | Auth error `role="alert"` + signup visibility-toggle labels | `src/app/(auth)/login/page.tsx`<br>`src/app/(auth)/signup/page.tsx` | ✅ `src/app/(auth)/login/page.test.tsx` (2), `src/app/(auth)/signup/page.test.tsx` (3) | ✅ Login shows labelled "Show password"; signup toggles Show/Hide + `aria-pressed` |
| **UIA-016** | ConfirmDialog success variant for positive confirmations | `src/components/feedback/ConfirmDialog.tsx`<br>`src/components/ui/button.tsx`<br>`src/app/(authenticated)/tools/laboratory/page.tsx` | ✅ `src/components/feedback/ConfirmDialog.test.tsx` (3) | ✅ "Mark all present" CTA and its confirmation render `bg-success` |
| **UIA-017** | Quiz error card token swap (no raw palette) | `src/components/quiz/QuizEligibilityCard.tsx` | ✅ `src/lib/designSystem.test.ts` (1), `src/components/quiz/QuizEligibilityCard.test.tsx` (5) | ✅ Error card uses `border-destructive/40 bg-destructive/10 text-destructive`; no `-red-` classes in DOM |
| **UIA-018** | One progress primitive with documented sizes/variants | `src/components/ui/progress.tsx`<br>6 consumers: `dashboard/SubjectAttendanceCard`, `dashboard/home/{OverallAttendanceCard,WeeklyAttendanceCard}`, `quiz/QuizEligibilityCard`, `app/(authenticated)/laboratory/page`, `app/(authenticated)/tools/laboratory/page` | ✅ `src/components/ui/progress.test.tsx` (5) | ✅ 9 tracks measured on `/subjects` all 6px (md); indicator variants map to semantic tokens |
| **UIA-019** | Replace misleading "LIVE" badge wording | `src/components/dashboard/home/TodayAttendanceCard.tsx` | ✅ `src/components/dashboard/home/TodayAttendanceCard.test.tsx` (3) | ✅ "Teaching day" badge renders; "LIVE" absent at all three viewports |
| **UIA-021** | Mark Attendance date/title de-duplication | `src/app/(authenticated)/tools/laboratory/page.tsx`<br>`src/components/layout/navItems.ts` | ✅ `src/components/layout/navItems.test.ts` (title absent) + runtime | ✅ Exactly one `h1`, one date line, native value `2026-10-02`, `aria-describedby="mark-attendance-date"`; "29 SEP" caption gone |
| **UIA-022** | Getting Started dismiss placement | `src/app/(authenticated)/dashboard/page.tsx` | ✅ `src/app/(authenticated)/dashboard/page.test.tsx` (3, new) | ✅ Dismiss pinned top-right of the hint card (`flex-row justify-between`, `shrink-0`), dismissible and remembered |
| **UIA-023** | Card/GlassCard unification | `src/components/shared/GlassCard.tsx` (deleted)<br>22 consuming files migrated to `Card` | ✅ `src/lib/designSystem.test.ts` (2) | ✅ No `GlassCard` references remain; migrated surfaces render on the single Card primitive |
| **UIA-024** | Dashboard card voids | `src/app/(authenticated)/dashboard/page.tsx`<br>`dashboard/home/{OverallAttendanceCard,AttentionRequiredCard,QuizSnapshotCard}.tsx` | ✅ `src/components/dashboard/home/dashboardDensity.test.tsx` (3), `OverallAttendanceCard.test.tsx` (4) | ✅ Sparse cards distribute the shared row height, content centered; no dead void measured at 1440 |
| **UIA-025** | Date-input strategy + formatted companion | `src/components/shared/DateInput.tsx` (new)<br>`app/(authenticated)/history/page.tsx`<br>`app/(authenticated)/tools/events/page.tsx`<br>`src/components/events/EventFormDialog.tsx` | ✅ `src/components/shared/DateInput.test.tsx` (5) | ✅ History/Events use native `type="date"` (machine value preserved) + `formatDateMedium` companion, `Any date` empty hint |
| **UIA-026** | History "Logged 2:09 AM" metadata noise | `src/app/(authenticated)/history/page.tsx` | ✅ `src/app/(authenticated)/history/page.test.tsx` (4) | ✅ Zero "Logged" occurrences in the rendered History page |
| **UIA-027** | History/Events "state" → "Status" vocabulary | `src/app/(authenticated)/history/page.tsx`<br>`src/app/(authenticated)/tools/events/page.tsx` | ✅ `src/app/(authenticated)/history/page.test.tsx` (4) | ✅ Filter reads "Status"/"All statuses" (and Events "All statuses"), one taxonomy (canonical P1 labels) |
| **UIA-029** | Profile modal/page duplication | `src/components/shell/ProfileModal.tsx` (deleted)<br>`src/app/(authenticated)/profile/page.tsx`<br>`src/components/layout/UserMenu.tsx`<br>`src/components/layout/TopNav.tsx`<br>`src/lib/shellModal.ts` (`profile` id removed) | ✅ `src/lib/designSystem.test.ts` (3, new), `src/app/(authenticated)/profile/page.test.tsx` (1) | ✅ Single `/profile` surface (identity + academic context + sign out); user-menu Profile is an `<a href="/profile">` |
| **UIA-030** | Interactive touch-target floor in primitives | `src/components/ui/button.tsx`<br>`src/components/ui/dropdown-menu.tsx` | ✅ `src/components/ui/touchTargets.test.tsx` (2) | ✅ 40px rows at 375px, 32px pointer floor at desktop (was 26.6px); no desktop layout breakage |
| **UIA-031** | Bottom-nav label size | `src/components/layout/MobileBottomNav.tsx` | ✅ `src/components/ui/touchTargets.test.tsx` (1) | ✅ 12px labels measured at 375px, tab height retained (76px rows) |
| **UIA-043** | Laboratory desktop sparsity | `src/app/(authenticated)/laboratory/page.tsx`<br>`src/components/dashboard/SubjectLaboratoryView.tsx` | ✅ `src/app/(authenticated)/laboratory/page.test.tsx` (3) | ✅ Default tab renders full-width Experiment Progress block; page fills the viewport (`scrollHeight == clientHeight == 900`) |

**Result: 18/18 P2 issues complete.** Full frontend suite: **26 files / 127 tests passed**; `tsc --noEmit` clean; `next build` passes; changed-file ESLint has **4 pre-existing errors, 0 warnings** (all baseline `react-hooks/set-state-in-effect`, none introduced by this phase).

---

## 2. Design-System Changes

**One progress primitive (`src/components/ui/progress.tsx`) — UIA-018**
- Variants: `default` (primary), `success`, `warning`, `danger` (destructive) and `neutral` (`bg-muted-foreground/30`) for the P1 zero-record "N/A" state.
- Sizes on `Progress`/`ProgressTrack`: `sm` = 4px (`h-1`), `md` = 6px (`h-1.5`, default for subject/criterion bars), `lg` = 8px (`h-2`, page-level bars).
- Track is `bg-muted-foreground/20`, documented because `--muted` equals `--card` in this token set (a `bg-muted` track is invisible on cards).
- Replaced the three prior implementations (subject block bars, weekly bars, Mark Attendance/Lab bars); all values remain backend-provided.

**One card primitive (`src/components/ui/card.tsx` + deletion of `GlassCard`) — UIA-023**
- `GlassCard` was a pass-through wrapper around `Card`; it was deleted and all **22 consuming files** (admin + student surfaces) now render `Card` directly. Intentional special surfaces (e.g. the primary-tinted Getting Started hint) keep their own class overrides; no elevated surface was flattened.
- Card remains column-by-default with `--card-spacing`; the Getting Started hint uses `flex-row` (see UIA-022).

**Touch floor in primitives — UIA-030**
- `Button`: every size is `h-10` / `size-10` at touch widths with `sm:h-8` / `sm:size-8` pointer overrides (including all icon sizes); the `success` variant (`bg-success text-success-foreground hover:bg-success/90`) was added for UIA-016.
- `dropdown-menu.tsx` exports `MENU_ITEM_TOUCH_FLOOR = "min-h-10 sm:min-h-8"`, applied to `Item`, `SubTrigger`, `CheckboxItem`, `RadioItem`. Measured: 26.6px baseline → 40px at 375px, 32px at desktop.
- `MobileBottomNav`: labels `text-xs` (12px, up from 10.4px) with `min-h-14` tabs retained — readability improved without growing the navigation footprint (UIA-031).

**Semantic success treatment — UIA-016**
- `ConfirmDialog` accepts `variant: "destructive" | "default" | "success"` and passes it to the action `Button`; destructive/default behavior is unchanged.

**Single date-input strategy — UIA-025**
- `src/components/shared/DateInput.tsx` wraps a native `type="date"` input (machine-readable value untouched) and adds a formatted human companion (`formatDateMedium`, e.g. "5 Sep 2026"), with an `emptyHint` ("Any date" by default) and `aria-hidden` on the decorative companion.
- Adopted by History filters, Events filters, and `EventFormDialog`; replaced the raw `mm/dd/yyyy`-style presentation the audit flagged.

**Consolidated formula copy — UIA-004**
- `src/lib/formula.ts` holds `POOLED_ATTENDANCE_FORMULA` and `POOLED_ATTENDANCE_EXPLANATION` (copy only — no arithmetic).
- Rendered once on `/subjects` (page description) and once on `/tools/quiz-schedule` (info box). Removed from every subject/quiz card, the uppercase "CRITERION I WINDOW COUNTS · COMBINED ATTENDANCE = …" caption, and the per-criterion "Formula:" rows.
- The one formula-like uppercase eyebrow that remained ("Criterion I window counts") was **sentence-cased** in this session; section/badge micro-labels that remain uppercase are the pre-existing design language and contain no formula text.

---

## 3. Issue-by-Issue Details (abridged)

### UIA-004 — Formula-caption consolidation
Removed three phrasings of the pooled formula from per-card surfaces; one authoritative explanation per page. Cards now carry only their own data. Uppercase formula text is gone; the phrase "Combined attendance" no longer appears on `SubjectAttendanceCard`/`QuizEligibilityCard`. Guarded by source-level tests so per-card formula copy cannot quietly return.

### UIA-013 — Auth-gate shell flash
New `AuthGate` wraps `AppShell` in the authenticated layout and renders a single centered loader (`role="status"`, sr-only "Loading your session…") until `!loading && hasSession`. `AuthContext` exposes `hasSession` (token status === "present") without changing auth semantics. SSR curl of `/dashboard` (no session) returns "Loading your session…" and **0** shell/nav/greeting markers.

### UIA-015 — Auth accessibility
Login and signup error banners use `role="alert"` so failures are announced. Signup's password fields gained "Show/Hide password" and "Show/Hide confirm password" toggles with `aria-pressed` and accessible names; login already had the toggle and is now test-covered. No authentication behavior changed.

### UIA-016 — Success ConfirmDialog
Positive confirmations (starting with Mark Attendance's "Mark all present") now use the shared success treatment, matching the page CTA instead of the destructive red used previously. Destructive confirmations (dismissals, removals) are unchanged.

### UIA-017 — Quiz error card tokens
The per-card error state uses semantic destructive tokens (`border-destructive/40 bg-destructive/10 text-destructive`) instead of raw red palette classes; a source-level guard rejects future `-red-` reintroduction.

### UIA-018 — Single progress primitive
See Section 2. Six consumer files migrated; P1 zero-record/neutral states preserved; no displayed value recomputed.

### UIA-019 — "LIVE" → "Teaching day"
The Today's Attendance badge now says "Teaching day", which is what the state actually represents (a scheduled teaching day), removing the real-time implication. Verified at 375/768/1440.

### UIA-021 — Mark Attendance de-duplication
The page previously stacked the date three times (header title, "29 SEP" caption, input) and the mobile header repeated the page title. Now: one `h1`, one date line ("Friday · 2 Oct 2026") associated with the native date input via `aria-describedby`, and the mobile header title for this route removed (the bottom-tab label still names the destination).

### UIA-022 — Getting Started dismiss placement
The hint card is `flex-row items-start justify-between`, pinning the `aria-label="Dismiss getting started hint"` icon button to the card's top-right, visually associated with the hint and away from primary actions. Dismissal persists (localStorage, frontend-only). Covered by a new page test (placement, dismissal, hidden-after-first-record).

### UIA-023 — Card / GlassCard unification
`GlassCard` was a no-op wrapper; deleted with all 22 consumer files migrated to `Card`. No broad restyle: special card treatments remain at their call sites.

### UIA-024 — Dashboard card voids
Sparse cards now fill their grid row instead of stranding first-line content above empty space: `OverallAttendanceCard` content `flex flex-1 flex-col justify-center`, `AttentionRequiredCard` empty state `flex-1 justify-center`, `QuizSnapshotCard` content centered, and the dashboard grid rows stretch consistently. Preferring flex distribution over fixed heights keeps all viewports honest.

### UIA-025 — Date-input strategy
Native date inputs (keyboard, pickers, machine value) are preserved; a formatted companion and "Any date" hint make the fields human-readable and consistent with `formatDateMedium` used elsewhere. No custom date engine was introduced.

### UIA-026 / UIA-027 — History metadata and vocabulary
Removed the "Logged 2:09 AM" row metadata noise; the filter label is "Status"/"All statuses" (Events too) using the single canonical P1 taxonomy. No second taxonomy was introduced.

### UIA-029 — One profile surface
Smaller consistent resolution chosen: the near-duplicate shell `ProfileModal` was deleted and the `/profile` page became the single canonical surface, carrying the identity block, the academic context that only lived in the modal, and Account/Sign Out. The user menu opens `/profile` (a real link, keyboard accessible) and `ShellModalId` no longer contains `profile`. Nothing was lost: every field shown by the modal now renders on the page, minus the internal UUID (already removed in P1).

### UIA-030 / UIA-031 — Touch targets and nav labels
See Section 2. Desktop layouts were explicitly preserved: the floor is `h-10` on touch widths with `sm:h-8` overrides, so 1440px layouts keep their compact metrics (measured 32px at desktop, 40px at 375px, menu rows 48px in the mobile sheet).

### UIA-043 — Laboratory density
The default lab tab now renders a third full-width block — `Experiment Progress` (`lg:col-span-2`) sourced from the backend-provided experiment progress (advisory text, signed/pending counts, "View experiments" action) — and shows an honest empty state when no catalog exists ("No experiment catalog has been published for this subject yet. Progress appears here as soon as it is available."), never invented data. At 1440 the page fills the viewport (`scrollHeight == clientHeight == 900`) instead of ending ~500px down.

---

## 4. Files / Components Changed (P2 scope)

**New:** `src/lib/formula.ts`, `src/components/layout/AuthGate.tsx`, `src/components/shared/DateInput.tsx`.
**Deleted:** `src/components/shared/GlassCard.tsx`, `src/components/shell/ProfileModal.tsx`.
**Modified (student surfaces):** `app/(authenticated)/{dashboard,history,laboratory,profile,subjects}/page.tsx`, `app/(authenticated)/tools/{laboratory,events,quiz-schedule}/page.tsx`, `app/(auth)/{login,signup}/page.tsx`, `components/dashboard/SubjectAttendanceCard.tsx`, `components/dashboard/home/{OverallAttendanceCard,AttentionRequiredCard,QuizSnapshotCard,TodayAttendanceCard,WeeklyAttendanceCard}.tsx`, `components/quiz/QuizEligibilityCard.tsx`, `components/events/EventFormDialog.tsx`, `components/layout/{MobileBottomNav,TopNav,UserMenu}.tsx`, `components/layout/navItems.ts`, `components/feedback/ConfirmDialog.tsx`.
**Modified (primitives/context/infra):** `components/ui/{progress,button,dropdown-menu,card}.tsx`, `contexts/AuthContext.tsx`, `app/(authenticated)/layout.tsx`, `lib/{formula,shellModal,statusLabels}.ts` (plus P1-carryover files listed in Section 9).
**Admin surfaces touched only by the UIA-023 Card migration** (uniform wrapper removal, no behavior change).

---

## 5. Tests Added (P2-focused)

**14 files / 51 tests**, all passing:

| File | Tests | Covers |
|---|---|---|
| `src/lib/designSystem.test.ts` | 8 | UIA-023 (2), UIA-004 (2), UIA-017 (1), **UIA-029 (3, added this session)** |
| `src/components/ui/progress.test.tsx` | 5 | UIA-018 variants/sizes/track token |
| `src/components/ui/touchTargets.test.tsx` | 3 | UIA-030 floor, UIA-031 label size |
| `src/components/feedback/ConfirmDialog.test.tsx` | 3 | UIA-016 success/default/destructive |
| `src/components/layout/AuthGate.test.tsx` | 3 | UIA-013 gate states |
| `src/components/shared/DateInput.test.tsx` | 5 | UIA-025 native value + companion + hint |
| `src/app/(auth)/login/page.test.tsx` | 2 | UIA-015 `role="alert"`, toggle label |
| `src/app/(auth)/signup/page.test.tsx` | 3 | UIA-015 alerts + both toggles |
| `src/app/(authenticated)/history/page.test.tsx` | 4 | UIA-026/UIA-027 vocabulary + metadata |
| `src/app/(authenticated)/laboratory/page.test.tsx` | 3 | UIA-043 default-tab density |
| `src/app/(authenticated)/dashboard/page.test.tsx` | 3 **(new this session)** | UIA-022 placement/dismissal/first-record guard |
| `src/components/dashboard/SubjectAttendanceCard.test.tsx` | 3 | UIA-004/UIA-018 md progress + explanation retained |
| `src/components/dashboard/home/dashboardDensity.test.tsx` | 3 | UIA-024 card filling |
| `src/components/dashboard/home/TodayAttendanceCard.test.tsx` | 3 | UIA-019 badge wording |

P2 source/copy guards also extended: `src/lib/dejargon.test.ts` now whitespace-normalizes file content before matching (CRLF/JSX-wrapped phrases are caught) and the signup elective helper wording was normalized in this session.

---

## 6. Validation Results

| Check | Command | Result |
|---|---|---|
| Targeted P2 tests | `npx vitest run <P2 files>` | ✅ 21 + 11 passed at the targeted runs |
| Full frontend suite | `npx vitest run` | ✅ **26 files / 127 tests passed** |
| Typecheck | `npx tsc --noEmit` | ✅ clean (exit 0) |
| ESLint (all changed/added frontend files) | `npx eslint <files>` | ✅ 4 errors, 0 warnings — all pre-existing `react-hooks/set-state-in-effect` baseline (`AuthContext.tsx:61,107`, `history/page.tsx:142,154`); zero in files added by this phase |
| Production build | `NEXT_PUBLIC_API_URL=https://… npx next build` | ✅ compiled, TypeScript passed, 25/25 routes prerendered |
| Build without production URL | `npx next build` | ⛔ intentionally aborted by the pre-existing `lib/api.ts:12` production guard (unmodified); not a regression |
| SSR auth gate | `curl /dashboard` (no session) | ✅ "Loading your session…", 0 shell markers |

---

## 7. Runtime Verification (375 / 768 / 1440)

Servers restarted for this session: backend `127.0.0.1:8300`, frontend `localhost:3100` (Next dev blocks dev resources on the `127.0.0.1` hostname — the app is browsed at `localhost`). Logged in through the real UI with the dev account.

**1440×900**
- Dashboard: "Good Afternoon, UI Verify Runner", date line, "Teaching day" badge (no LIVE), Overall Attendance "Healthy · 100% of recorded · 5 attended · 5 recorded · 296 pending · Forecast", This Week range "28 Sep 2026 – 4 Oct 2026", Quiz Snapshot "0 ELIGIBLE / 6 ATTENTION / 0 NOT ELIGIBLE", Attention Required empty state, Upcoming Events list. No horizontal overflow.
- `/tools/quiz-schedule`: formula text exactly once in the page info box; 0 "Formula:" rows; no uppercase formula; "Criterion I window counts" eyebrow renders sentence case (`text-xs font-medium`, `text-transform: none`); 7 cards; no raw red classes.
- `/subjects`: 9 progress tracks all 6px (md) with primary/success indicators; formula once; 0 formula rows; no uppercase formula.
- Mark Attendance (`/tools/laboratory`): exactly one `h1`, one date line; native input value `2026-10-02`; "Mark all present" uses `bg-success`.
- `/laboratory`: headings Practical Attendance / Mid-Semester Practical / Experiment Progress; `scrollHeight == clientHeight == 900` (viewport filled).
- User menu: "Profile" is an `<a href="/profile">`, 40px row; menu rows 40px at 375 / 32px floor at desktop per primitive.

**768×1024**
- Primary nav = Home / Mark Attendance / History + More; no overflow (scrollWidth 768 == innerWidth).

**375×812**
- Dashboard: no horizontal overflow (375 == 375); bottom nav Home / Mark Attendance / History / More with **12px labels** and **76px rows**; More sheet lists Attendance / Lab Experiments / Quiz Eligibility / Calendar / Events at **48px** each; Escape closes it.
- `/history`: no overflow; filter labels Subject/Status/From/To/Search; "All statuses"; zero "Logged" text; native `type="date"` inputs present.
- `/profile`: single page, no UUID, Student Identity + Academic Context + Sign out.
- Quiz zero-data state intact at mobile widths (neutral "No data yet" badges, no FAIL/NOT ELIGIBLE).

**Known tooling limitation:** the preview webview was not compositing this session, so screenshots could not be captured; verification used the accessibility snapshot plus direct DOM/geometry measurements (overflow, computed font sizes, row heights, track heights, text-transform), which are stronger evidence for those specific claims. Screenshots from the previous session's smoke (same code paths) were reviewed before this pass.

---

## 8. Boundary Verification

- **Backend untouched:** `git status --short -- backend` is empty. No API, schema, migration, engine, or notification file was modified.
- **No API contract changes:** no changes to `frontend/src/types/api.ts`, `frontend/src/lib/api.ts`, or any route handler; no new routes.
- **No calculation changes:** `lib/formula.ts` holds presentation strings only; every displayed number continues to render backend-provided fields; no attendance/eligibility/forecast/quiz math exists in the changed frontend code.
- **P1 invariants verified:** canonical status vocabulary (`canonicalStatus.test.ts` 13), recorded-only semantics (dashboard runtime text + `OverallAttendanceCard.test.tsx`), zero-data quiz state (`QuizEligibilityCard.test.tsx`, runtime), mobile attendance navigation (`navItems.test.ts`, `MobileBottomNav.test.tsx`, runtime), profile UUID removal (`profile/page.test.tsx`), de-jargon guard (11).
- **Routes:** `navItems.ts` route mappings unchanged; only labels/titles/grouping.
- **Dependencies:** none added.

---

## 9. P1 Prerequisite Restoration (inside P2-touched files)

The working tree arrived with P1 tests committed but P1 source changes partially missing. The following P1 behavior was restored so the P2 work would not ship on a broken base (all now covered by the green P1 suite): `QuizEligibilityCard` zero-data/guidance/`noData` logic and formula consolidation; `OverallAttendanceCard` designed zero-record state; `canonicalStatus` delegation from `status.ts`/`statusLabels.ts`; `GreetingHeader` full-name rendering; `navItems` mobile IA (Mark Attendance tab, Attendance under More); single profile surface groundwork; de-jargon copy pass. No P1 decision was changed — only restored.

---

## 10. Unresolved Items

1. **Pre-existing ESLint errors (not P2):** two `react-hooks/set-state-in-effect` errors in `AuthContext.tsx` and two in `history/page.tsx` predate this phase. Fixing the AuthContext ones would alter auth effect semantics (out of scope); the History ones are likewise baseline. No new lint errors were introduced.
2. **Uppercase micro-labels elsewhere:** filter labels, badges, and section eyebrows remain uppercase by design (existing design language). UIA-004's requirement is met literally: no formula text is uppercase anywhere, and the formula-like quiz eyebrow was sentence-cased this session.
3. **Screenshots unavailable this session** (preview compositing), documented in Section 7; DOM/geometry evidence was used instead.

**Stop condition:** Phase 3 (P2) is complete. No P3 work has been started, and none of the remaining audit items outside the listed P2 scope were modified.
