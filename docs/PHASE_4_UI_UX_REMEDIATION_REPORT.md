# Phase 4 — P3 UI/UX Remediation Report

**Date:** 2026-10-02
**Scope:** The audit's LOW-severity issues `UIA-032 … UIA-045` from `docs/UI_UX_AUDIT_REPORT.md` — the final 14 issues in the audit (UIA-043 was already remediated in Phase 3). No Medium/High/Critical issues were touched, and no P0/P1/P2 work was redone or reinterpreted.
**Discipline:** Strictly frontend-only. Zero changes to backend APIs, schemas, database migrations, calculation engines, or notification pipelines. Zero route/API contract changes. No new dependencies.

**Baseline:** clean committed tree on `main`; suite healthy at **26 files / 127 tests** before edits (Phase 3 close).

---

## 1. Executive Summary & Remediation Matrix

| Issue ID | Audit finding | Status | File(s) Changed | Test coverage | Runtime verification |
|---|---|---|---|---|---|
| **UIA-032** | Redundant date tile + text date in Events rows | ✅ Fixed | `src/components/events/EventRow.tsx` | `EventRow.test.tsx` (3, new) | ✅ 18 rows at 1440 show only the date tile; ranges keep text |
| **UIA-033** | Events tri-redundancy (banner + manage card + button) | ✅ Fixed | `src/app/(authenticated)/tools/events/page.tsx` | `designSystem.test.ts` guard | ✅ Manage row is heading + Add Event; banner is the only explanation |
| **UIA-034** | History search placeholder truncates mid-word | ✅ Fixed | `src/app/(authenticated)/history/page.tsx` | `history/page.test.tsx` (+1) | ✅ "e.g. BCS-501" measures 82px in 136px available — fully rendered |
| **UIA-035** | Calendar mobile abbreviation "6 cl." | ✅ Already resolved (guard added) | `src/lib/designSystem.test.ts` (guard) | `designSystem.test.ts` guard | ✅ Cells read "5 classes"; aria-label spells out "5 classes, no events" |
| **UIA-036** | Past weeks read "0/0 · 27 pending"; Badge as empty state | ✅ Fixed | `src/components/dashboard/home/WeeklyAttendanceCard.tsx` | `WeeklyAttendanceCard.test.tsx` (3, new) | ✅ 5 past weeks "unmarked"; current week "21 pending" |
| **UIA-037** | Detail rows say "missed" vs canonical "Absent" | ✅ Fixed | `src/components/dashboard/SubjectAttendanceCard.tsx` | `SubjectAttendanceCard.test.tsx` (+1) | ✅ Component test; dev data has no absences to render live (documented) |
| **UIA-038** | Feedback success state has no Done CTA | ✅ Fixed | `src/components/shell/FeedbackModal.tsx` | `FeedbackModal.test.tsx` (2, new) | ✅ Done button closes dialog (component test; not submitted live to avoid junk data) |
| **UIA-039** | `font-heading` utility has no token defined | ✅ Fixed | `src/app/globals.css` | `designSystem.test.ts` guard | ✅ CardTitle computes `Geist, "Geist Fallback"` |
| **UIA-040** | Signup helper text reads as implementation | ✅ Already resolved in Phase 2 | — | `dejargon.test.ts` (existing) | ✅ Copy is "Elective options reflect the courses offered this semester." |
| **UIA-041** | "Recoverable" badge lacks a definition | ✅ Fixed | `src/app/(authenticated)/tools/quiz-schedule/page.tsx` | `quiz-schedule/page.test.tsx` (2, new) | ✅ Definition line renders once on the page (375) |
| **UIA-042** | User-menu trigger near-white when open (⚠ unverified) | ✅ Not reproducible | — | — | ✅ With the menu open the trigger computes `rgb(38,38,38)` = `--accent` (#262626) |
| **UIA-043** | Lab page sparse at desktop | ✅ Already remediated in Phase 3 | — | `laboratory/page.test.tsx` (existing) | ✅ Re-verified: `scrollHeight == clientHeight == 900` |
| **UIA-044** | "Not scheduled" row repeated on all three lab cards | ✅ Fixed | `src/components/dashboard/SubjectAttendanceCard.tsx` | `SubjectAttendanceCard.test.tsx` (+2) | ✅ 3 lab cards, 0 "Not scheduled"/mid-sem rows while undesignated |
| **UIA-045** | Roll number twice in Profile modal | ✅ Already resolved by Phase 3 single-profile work | — | `profile/page.test.tsx` (+1) | ✅ Roll number renders exactly once on `/profile` |

**Result: every remaining P3 finding is addressed or verified as no longer applicable — 9 fixed in this phase, 5 verified resolved / not reproducible with evidence. No unresolved P3 items.**

---

## 2. Detailed Changes

### UIA-032 — Events row date redundancy
The round date tile (`OCT / 5`) and the full date text (`5 Oct 2026`) both rendered on every single-day row. The tile remains as the visual date anchor (matching the dashboard's Upcoming Events); the full date text now renders **only for multi-day ranges**, where the tile cannot express the end date. No information is lost.

### UIA-033 — Events explanation tri-redundancy
The amber banner already explains what students can record and who manages holidays. The "Manage events" card no longer restates it: it is now the action row (heading + `Add Event`). A source-level guard prevents the long duplicate sentence from returning.

### UIA-034 — History search placeholder
`"Code, name, type, date..."` clipped mid-word in the narrow five-column filter grid. Replaced with `"e.g. BCS-501"`; measured at 1440: placeholder text 82px vs 136px available — no clipping. The label above the field remains "Search".

### UIA-035 — Calendar "cl." abbreviation
The audit's finding was already resolved by the earlier date/vocabulary work: cells render `N classes` (with the full reason/counts in the cell's aria-label, e.g. "Thursday · 1 Oct 2026, working day, 5 classes, no events"). A guard now locks the wording (`CalendarGrid.tsx` must contain `classLabel` and must not contain `cl.`).

### UIA-036 — Weekly card wording and empty state
- Weeks that have fully passed can no longer be marked, so their unrecorded sessions now read `· 27 unmarked`; the current week keeps `· 21 pending`. This is a descriptive count in one card, not a new status taxonomy — canonical status labels (badges: Present/Absent/Pending/Cancelled) are unchanged everywhere.
- The best/needs empty line is now plain paragraph text ("No subjects with recorded attendance yet.") instead of a status Badge used as a sentence.

### UIA-037 — Detail-row vocabulary
Expanded subject details now say `· 2 absent` instead of `· 2 missed`, matching the canonical P1 vocabulary. (The live dev account currently has only attended records, so this was verified by the component test.)

### UIA-038 — Feedback success CTA
The success state now renders an explicit **Done** button that closes the dialog through the existing `handleOpenChange(false)` path (which also resets the form). The header ✕ remains. Auto-close was deliberately not added (a success confirmation should not disappear on its own).

### UIA-039 — `font-heading` token
`CardTitle`, `DialogTitle`, and `SheetTitle` use the `font-heading` utility, but no `--font-heading` theme token existed. Added `--font-heading: var(--font-geist-sans)` to the `@theme inline` block (mirroring `--font-sans`); the utility now resolves explicitly instead of relying on inheritance. Verified live: CardTitle computes `Geist, "Geist Fallback"`.

### UIA-040 — Signup helper copy
Resolved during Phase 2 (de-jargon pass); the banned phrase "the server verifies your selection" is covered by `dejargon.test.ts`. No further change.

### UIA-041 — "Recoverable" definition
The card's guidance callout already provides the actionable on-ramp ("You need to attend the next 5 lectures and 3 tutorials to qualify (Criterion I)."). Added the missing *definition* once per page in the info card: "A subject below the required percentage that can still reach it before the quiz is labeled **Recoverable**." No per-card repetition.

### UIA-042 — User-menu open state
Could not reproduce. With the menu open (keyboard), the trigger carries `data-popup-open` and computes `background-color: rgb(38, 38, 38)` = `--accent` (#262626) — exactly the intended dark open-state. The audit itself flagged this as ⚠ unverified / possibly a capture artifact; no code change was warranted.

### UIA-043 — Laboratory density
Remediated in Phase 3 (full-width Experiment Progress block). Re-verified this phase: at 1440 the page fills the viewport (`scrollHeight == clientHeight == 900`) and the default tab shows Practical Attendance / Mid-Semester Practical / Experiment Progress. The dedicated lab page keeps its explanatory "Not yet designated…" copy (one per selected subject) — only the inert repeated row on the three `/subjects` lab cards was removed (UIA-044).

### UIA-044 — Mid-sem "Not scheduled" noise
The lab-only subject card on `/subjects` now renders the Mid-Sem Practical row **only when a session is actually designated** (backend `mid_sem_session_date`). While unscheduled, the inert "Not scheduled" line is gone; the dedicated Lab page remains the place that explains designation. Verified: 3 lab cards, 0 such rows.

### UIA-045 — Duplicate roll number
Resolved by the Phase 3 single-profile-surface work (modal deleted). Verified live: the roll number renders exactly once on `/profile`; a test now asserts it.

---

## 3. Files Changed

**Modified (12):** `src/app/(authenticated)/history/page.tsx`, `history/page.test.tsx`, `profile/page.test.tsx`, `src/app/(authenticated)/tools/events/page.tsx`, `src/app/(authenticated)/tools/quiz-schedule/page.tsx`, `src/app/globals.css`, `src/components/dashboard/SubjectAttendanceCard.tsx`, `SubjectAttendanceCard.test.tsx`, `src/components/dashboard/home/WeeklyAttendanceCard.tsx`, `src/components/events/EventRow.tsx`, `src/components/shell/FeedbackModal.tsx`, `src/lib/designSystem.test.ts`.
**Added (4 test files):** `src/components/events/EventRow.test.tsx`, `src/components/dashboard/home/WeeklyAttendanceCard.test.tsx`, `src/components/shell/FeedbackModal.test.tsx`, `src/app/(authenticated)/tools/quiz-schedule/page.test.tsx`.

---

## 4. Tests Added / Updated

| File | Change | Tests |
|---|---|---|
| `src/components/events/EventRow.test.tsx` | New | 3 |
| `src/components/dashboard/home/WeeklyAttendanceCard.test.tsx` | New | 3 |
| `src/components/shell/FeedbackModal.test.tsx` | New | 2 |
| `src/app/(authenticated)/tools/quiz-schedule/page.test.tsx` | New | 2 |
| `src/components/dashboard/SubjectAttendanceCard.test.tsx` | +3 (absent wording, mid-sem hidden/shown) | 6 total |
| `src/app/(authenticated)/history/page.test.tsx` | +1 (placeholder) | 5 total |
| `src/app/(authenticated)/profile/page.test.tsx` | +1 (roll number once) | 2 total |
| `src/lib/designSystem.test.ts` | +3 (UIA-033, UIA-035, UIA-039 guards) | 11 total |

P3-focused: **18 new/changed tests**; suite grew from 26 files / 127 tests to **30 files / 145 tests**.

---

## 5. Validation Results

| Check | Command | Result |
|---|---|---|
| Targeted P3 tests | `npx vitest run <8 P3 files>` | ✅ 8 files / 34 tests |
| Full frontend suite | `npx vitest run` | ✅ **30 files / 145 tests passed** |
| Typecheck | `npx tsc --noEmit` | ✅ clean |
| ESLint (all 16 changed/added files) | `npx eslint <files>` | ✅ 2 errors, 0 warnings — both pre-existing `react-hooks/set-state-in-effect` baseline in `history/page.tsx:142,154`; all new/changed P3 files clean |
| Production build | `NEXT_PUBLIC_API_URL=https://… npx next build` | ✅ compiled, TypeScript passed, 25/25 routes prerendered |
| Backend untouched | `git status --short -- backend` | ✅ empty |
| API/type/route files | `git status` filter | ✅ none changed |

---

## 6. Runtime Verification (375 / 768 / 1440)

Servers: backend `:8300`, frontend `localhost:3100`; logged in with the existing dev account.

- **Dashboard 1440:** "Teaching day" (no LIVE), "Healthy", "100% of recorded" (recorded-only semantics intact), 7 progress tracks all 6px; no overflow.
- **Weekly card (dashboard):** 5 past weeks read "unmarked", current week "21 pending" (UIA-036).
- **CardTitle font:** `Geist, "Geist Fallback"` — `font-heading` resolves (UIA-039).
- **Events 1440:** 18 rows, single-day rows show only the tile; manage row is "Manage events / Add Event"; `Add extras, cancellations…` absent (UIA-032/033). No range events in current data — range rendering covered by test.
- **History 1440:** placeholder "e.g. BCS-501" fits (82px/136px); "All statuses" present; zero "Logged" (UIA-034 regression of P2 invariants).
- **Calendar 375:** no "cl."; cells read "N classes"; aria-labels spell out counts; no overflow (UIA-035).
- **Subjects 375/1440:** 3 lab cards with **zero** "Not scheduled"/mid-sem rows while undesignated; formula exactly once; 9 progress tracks (md) (UIA-044 + P2 invariants).
- **Quiz Eligibility 375:** Recoverable definition line renders once; formula once; no "Formula:" rows; no uppercase formula; zero-data "No data yet" badges intact (UIA-041 + P2 invariants).
- **Profile 375:** roll number exactly once; single surface; no UUID (UIA-045).
- **Lab Experiments 1440:** viewport filled (`scrollHeight == clientHeight == 900`); Experiment Progress present (UIA-043 re-verified).
- **Tablet 768:** nav Home / Mark Attendance / History / More; no overflow.
- **SSR auth gate:** `/dashboard` (no session) returns "Loading your session…" with 0 shell markers.

---

## 7. Accessibility Verification

- **Keyboard:** user menu opens with Enter (not just pointer), items are standard menu items, Escape closes; the calendar day cells are real buttons with `aria-pressed` and spelled-out aria-labels; the Feedback Done button is reachable and labelled.
- **Touch floor:** user-menu rows measure 40px at 375 (primitive `min-h-10 sm:min-h-8`); bottom-nav and buttons unchanged from P2.
- **Accessible names:** "Open the calendar", "Open user menu", "Dismiss getting started hint" etc. remain; new Done button has an explicit name.
- **No color-only information:** weekly wording ("unmarked"/"pending"), badges (text), and progress variants all carry text.
- **Dialogs/popovers on mobile:** user menu and bottom-sheet patterns verified at 375; Feedback dialog open/close semantics unchanged (test-covered).
- **Visible focus:** unchanged P2 primitives (`focus-visible:ring`/`outline-none` with ring); no focus styles removed.

---

## 8. P0/P1/P2 Regression Verification

- **Canonical status vocabulary:** `canonicalStatus.test.ts` (13) green; badges unchanged; the only new word ("unmarked") is a weekly descriptive count, not a status label.
- **Recorded-only semantics:** dashboard still renders "% of recorded" + pending counts; `OverallAttendanceCard.test.tsx` green.
- **Zero-data Quiz state:** runtime shows neutral "No data yet" badges and the recorded-first guidance; `QuizEligibilityCard.test.tsx` green.
- **Mobile Attendance navigation:** bottom nav Home / Mark Attendance / History / More; `navItems.test.ts` + `MobileBottomNav.test.tsx` green; 768 nav verified.
- **Single Profile surface:** `/profile` only; `designSystem.test.ts` UIA-029 guards green.
- **Single Card / Progress primitives:** GlassCard guards green; all measured tracks 6px/8px per size; `progress.test.tsx` green.
- **Date-input strategy:** `DateInput.test.tsx` green; history "Any date" companions still render.
- **Touch-target floor:** `touchTargets.test.tsx` green; 375 measurements unchanged.
- **Auth-gate behavior:** SSR check passed; `AuthGate.test.tsx` green.
- **Formula consolidation:** formula once per page on `/subjects` and `/tools/quiz-schedule`; `designSystem.test.ts` UIA-004 guards green.
- **No backend changes:** verified (empty backend diff, no API/type/route files).

---

## 9. Unresolved Items

1. **Pre-existing ESLint baseline (not P3):** the two `react-hooks/set-state-in-effect` errors in `history/page.tsx:142,154` remain from before this phase; fixing them would restructure the pagination accumulator effect outside P3 scope. No new lint errors or warnings were introduced.
2. **UIA-037 live rendering:** the dev account has no absent records, so the "absent" wording was verified by the component test rather than live data; the string path is identical to the previously rendered one.
3. **UIA-038 live submission:** the Done flow is test-covered; no real feedback row was written to the dev database to exercise it live.

**Stop condition:** all P3 audit issues (UIA-032 … UIA-045) are addressed and verified. No further UX phase was started.
