# Phase 2 — P1 UI/UX Remediation Report

**Date:** 2026-10-01  
**Scope:** The nine P1 issues from `docs/UI_UX_AUDIT_REPORT.md` (UIA-003, UIA-005, UIA-006, UIA-007, UIA-009, UIA-011, UIA-012, UIA-014, UIA-028).  
**Discipline:** Strictly frontend-only remediation. Zero changes to backend APIs, schemas, database migrations, calculation engines, or notification pipelines. Zero modifications to Phase 1 P0 fixes. No P2 or P3 issues were addressed in this phase.

---

## 1. Executive Summary & Remediation Matrix

| Issue ID | Description | File(s) Changed | Test Status | Runtime Verification Status |
|---|---|---|---|---|
| **UIA-003** | Global de-jargonization of student-facing copy | `src/app/(authenticated)/laboratory/page.tsx`<br>`src/app/(authenticated)/tools/quiz-schedule/page.tsx`<br>`src/app/(authenticated)/tools/events/page.tsx`<br>`src/components/events/EventFormDialog.tsx`<br>`src/components/shell/AppearanceModal.tsx`<br>`src/app/(auth)/signup/page.tsx`<br>`src/components/shell/ShellDialog.tsx`<br>`src/components/shell/SettingsModal.tsx`<br>`src/components/shell/FeedbackModal.tsx`<br>`src/components/shared/ErrorState.tsx`<br>`src/app/(authenticated)/calendar/page.tsx`<br>`src/components/shell/InstallAppModal.tsx`<br>`src/lib/api.ts`, `login/page.tsx`, `signup/page.tsx` | ✅ PASSED (`src/lib/dejargon.test.ts` 11 tests) | ✅ Student-facing UI free of engineering jargon across all listed routes |
| **UIA-005** | Mobile Attendance navigation IA overhaul | `src/components/layout/navItems.ts` | ✅ PASSED (`src/components/layout/navItems.test.ts` 4 tests, `src/components/layout/MobileBottomNav.test.tsx` 3 tests) | ✅ Verified at 375px & 768px: direct bottom tab access, zero duplicate links, safe areas preserved |
| **UIA-006** | Canonical status vocabulary consolidation | `src/lib/canonicalStatus.ts` (new)<br>`src/lib/statusLabels.ts`<br>`src/components/dashboard/home/status.ts`<br>`src/components/dashboard/SubjectAttendanceCard.tsx`<br>`src/app/(authenticated)/history/page.tsx`<br>`src/components/dashboard/home/QuizSnapshotCard.tsx`<br>`src/app/(authenticated)/laboratory/page.tsx` | ✅ PASSED (`src/lib/canonicalStatus.test.ts` 13 tests) | ✅ Normalized labels and badges across Sessions, Subject Health, and Quiz statuses |
| **UIA-007** | Remove raw UUID / internal ID from Profile | `src/app/(authenticated)/profile/page.tsx` | ✅ PASSED (`src/app/(authenticated)/profile/page.test.tsx` 1 test) | ✅ Profile displays student details, roll number, and sign-out without exposing internal UUID |
| **UIA-009** | Student greeting name natural presentation | `src/components/dashboard/home/GreetingHeader.tsx` | ✅ PASSED (`src/components/dashboard/home/GreetingHeader.test.tsx` 8 tests) | ✅ Full name preserved, whitespace cleaned, break-words wrapping on 375px mobile |
| **UIA-011** | Date format standardization sweep | `src/lib/date.ts`<br>`src/components/dashboard/home/WeeklyAttendanceCard.tsx`<br>`src/app/(authenticated)/tools/laboratory/page.tsx`<br>`src/app/(authenticated)/history/page.tsx`<br>`src/app/(authenticated)/calendar/page.tsx`<br>`src/app/(authenticated)/laboratory/page.tsx` | ✅ PASSED (`src/lib/date.test.ts` 4 tests) | ✅ Replaced raw ISO dates and concatenated weekdays with human-readable formatting |
| **UIA-012** | Quiz "Must Attend" redesign & action clarity | `src/components/quiz/QuizEligibilityCard.tsx` | ✅ PASSED (`src/components/quiz/QuizEligibilityCard.test.tsx` 5 tests) | ✅ Direct actionable guidance ("You need to attend next N lectures") with contradictory numbers removed |
| **UIA-014** | Overall Attendance zero-record N/A state | `src/components/dashboard/home/OverallAttendanceCard.tsx`<br>`src/components/ui/progress.tsx` | ✅ PASSED (`src/components/dashboard/home/OverallAttendanceCard.test.tsx` 4 tests) | ✅ Clean em dash percentage, neutral N/A badge, neutral progress indicator, informative pending classes count |
| **UIA-028** | Zero-data Quiz Eligibility neutral state | `src/components/quiz/QuizEligibilityCard.tsx`<br>`src/lib/canonicalStatus.ts` | ✅ PASSED (`src/components/quiz/QuizEligibilityCard.test.tsx` 5 tests, `src/lib/canonicalStatus.test.ts`) | ✅ Renders "No data yet", neutral badges, never shows misleading "FAIL" or "NOT ELIGIBLE" |

---

## 2. Detailed Remediation Summaries

### UIA-003 — Global De-jargonization

- **Problem:** Student-facing copy contained internal architecture and engineering jargon (e.g., "backend", "canonical attendance pipeline", "server enforces", "tokens", "surface", "offline shell", "evaluated by the backend"), confusing students and exposing technical implementation details.
- **Root Cause:** Placeholder and developer comments had been written directly into student UI text without an editorial pass for student-centered phrasing.
- **Implementation Details:**
  - Audited and updated strings across 14 components/pages:
    - `laboratory/page.tsx`: Changed "Mark your attendance through the canonical attendance pipeline" to "Mark your attendance for current and upcoming laboratory sessions." Changed "View only mode" pipeline wording to "View-only mode: historical dates cannot be edited."
    - `tools/quiz-schedule/page.tsx`: Replaced "Schedule and window dates are evaluated by the backend against your current semester" with "Schedule and window dates are updated for your current semester."
    - `tools/events/page.tsx` & `EventFormDialog.tsx`: Replaced "server enforces date ordering" and "Event duration in days (server enforces end >= start)" with clear academic calendar descriptions: "Event dates must be chronological."
    - `AppearanceModal.tsx`: Replaced "Theme preference is saved to your account and synced across sessions" without mentions of internal preference caches or tokens.
    - `signup/page.tsx`: Changed "Requires valid institutional roll number recognized by the server" to "Enter your institutional roll number (e.g. 240122001)."
    - `ShellDialog.tsx`: Replaced "surface" with "window".
    - `SettingsModal.tsx`: Replaced "browser surface" with "browser".
    - `FeedbackModal.tsx`: Replaced "feedback pipeline" and "admin review surface" with "feedback system" and "review team".
    - `ErrorState.tsx`: Replaced "backend error" with "Something went wrong while loading this page."
    - `calendar/page.tsx`: Replaced "Calendar surface synchronized" with "Academic schedule synchronized."
    - `InstallAppModal.tsx`: Replaced "offline shell" with "offline access".
    - `lib/api.ts`, `login/page.tsx`, `signup/page.tsx`: Replaced "Backend unreachable" and "Failed to reach backend server" with "Unable to reach the server. Please check your internet connection and try again."
- **Tests Added:** `frontend/src/lib/dejargon.test.ts` (11 tests asserting student-facing copy is free of banned keywords).
- **Runtime Verification:** Verified student surfaces in browser. No engineering jargon found in user-facing dialogs or text.
- **Remaining Limitations:** None.
- **Regression Risk:** Low (pure string presentation changes).

---

### UIA-005 — Mobile Attendance Navigation

- **Problem:** On mobile screens (<768px), "Mark Attendance" was buried inside the "More" overflow sheet, even though marking attendance is the primary daily action students perform. Meanwhile, redundant links existed or competed with Attendance overview.
- **Root Cause:** `MOBILE_TAB_HREFS` in `src/components/layout/navItems.ts` routed directly to `/subjects` ("Attendance") instead of `/tools/laboratory` ("Mark Attendance").
- **Implementation Details:**
  - Modified `src/components/layout/navItems.ts`:
    - Updated `MOBILE_TAB_HREFS = ["/dashboard", "/tools/laboratory", "/history"]`.
    - Placed `/subjects` ("Attendance") into `MORE_HREFS` along with Calendar, Quiz Schedule, Events, and Lab Tracking.
    - Tablet layout (md to lg) maintains prominent direct access to Home, Mark Attendance, and History.
    - Desktop layout (lg+) preserves all canonical navigation links without regressions.
    - Zero conflicting or duplicate links across desktop, tablet, and mobile navigation bars.
- **Tests Added:**
  - `src/components/layout/navItems.test.ts` (4 unit tests verifying desktop list, mobile tab items, role-based items, and absence of duplicate links).
  - `src/components/layout/MobileBottomNav.test.tsx` (3 component tests asserting bottom bar renders "Mark Attendance", maps to `/tools/laboratory`, and indicates active state).
- **Runtime Verification:** Verified navigation at 375px (mobile) and 768px (tablet) viewports. Bottom bar renders 4 items: Home, Mark Attendance, History, More.
- **Remaining Limitations:** None.
- **Regression Risk:** Low (route mappings strictly preserved, safe areas respected).

---

### UIA-006 — Canonical Status Vocabulary

- **Problem:** The frontend had seven overlapping status vocabularies (e.g., "SAFE", "WATCH", "CRITICAL", "ELIGIBLE", "RECOVERABLE", "NOT_ELIGIBLE", "ATTENTION", "Present", "Absent", "Missed"). In some places "Missed" was used for Absent; in others "Attention" was used for Recoverable.
- **Root Cause:** Lack of a centralized frontend status registry, leading component authors to create ad-hoc status dictionaries with disparate color tokens and terminology.
- **Implementation Details:**
  - Created `frontend/src/lib/canonicalStatus.ts` establishing the single source of truth for:
    - **Session Status:** `Present` (success), `Absent` (danger), `Pending` (neutral), `Cancelled` (outline).
    - **Subject Health Status:** `Healthy` (success), `At Risk` (warning), `Critical` (danger), `N/A` (neutral).
    - **Quiz Status:** `Eligible` (success), `Recoverable` (warning), `Not eligible` (danger), `Unscheduled` (outline), `No data yet` (neutral).
  - Centralized label, badge variant (`BadgeVariant`), and Lucide icon metadata for each status.
  - Refactored consumers to use canonical mappings:
    - `src/lib/statusLabels.ts`
    - `src/components/dashboard/home/status.ts`
    - `src/components/dashboard/SubjectAttendanceCard.tsx` (standardized on "N absent" instead of "N missed")
    - `src/app/(authenticated)/history/page.tsx` (`StatusBadge`)
    - `src/components/dashboard/home/QuizSnapshotCard.tsx` (mapped `RECOVERABLE` to "Recoverable" with warning variant)
    - `src/app/(authenticated)/laboratory/page.tsx` (`ActivityRow`)
- **Tests Added:** `frontend/src/lib/canonicalStatus.test.ts` (13 unit tests verifying canonical mappings for all three domains, case insensitivity, and fallback behavior).
- **Runtime Verification:** Verified badge colors and labels on Dashboard, Subject Attendance, Quiz, History, and Lab pages.
- **Remaining Limitations:** None.
- **Regression Risk:** Low (normalized presentation layer without altering API status values).

---

### UIA-007 — Remove Profile UUID

- **Problem:** The student Profile page exposed the internal database authentication UUID under "Account Identifier", creating technical clutter and privacy concerns for students.
- **Root Cause:** The profile page rendered `user?.id` directly inside a card alongside student details.
- **Implementation Details:**
  - Updated `frontend/src/app/(authenticated)/profile/page.tsx`:
    - Removed `user?.id` ("Account Identifier") from the rendered DOM.
    - Renamed the section to "Account Session".
    - Preserved student Full Name, Email, Institutional Roll Number, Role, and Sign Out action.
    - Left backend user object, API types, and authentication context untouched.
- **Tests Added:** `frontend/src/app/(authenticated)/profile/page.test.tsx` (test asserting that roll number and name are displayed while `user.id` UUID never appears in the document).
- **Runtime Verification:** Navigated to `/profile` in browser; confirmed that student name and roll number render clearly with no UUID present.
- **Remaining Limitations:** None.
- **Regression Risk:** Minimal (presentation-only omission).

---

### UIA-009 — Greeting Name Handling

- **Problem:** The dashboard greeting truncated multi-word names (e.g. "UI Audit Runner" rendered only as "Welcome back, UI!"). In addition, unusually long names risked overflow or awkward layout wrapping.
- **Root Cause:** `GreetingHeader.tsx` executed `user?.full_name?.split(" ")[0]`, stripping all subsequent words and failing on irregular whitespace.
- **Implementation Details:**
  - Updated `frontend/src/components/dashboard/home/GreetingHeader.tsx`:
    - Added `formatGreetingName(fullName)` helper that trims leading/trailing whitespace, collapses internal whitespace, and preserves the full student name naturally.
    - Falls back to `Student` if full name is missing or empty.
    - Added CSS utility `break-words max-w-full` on the greeting heading to gracefully wrap extremely long continuous tokens.
- **Tests Added:** `frontend/src/components/dashboard/home/GreetingHeader.test.tsx` (8 unit and component tests covering normal names, multi-word names, whitespace normalization, long names, and missing/empty fallbacks).
- **Runtime Verification:** Tested with single-word, multi-word ("UI Audit Runner"), and long names across desktop, tablet, and 375px mobile screens.
- **Remaining Limitations:** None.
- **Regression Risk:** Minimal.

---

### UIA-011 — Date Format Sweep

- **Problem:** Multiple student surfaces displayed raw ISO date strings (e.g. `2026-08-01 to 2026-12-15`, `2026-10-05`) or awkward concatenated strings (e.g. `Mon · Oct 5, 2026`).
- **Root Cause:** Components formatted dates locally with `.toISOString()` or raw template interpolation rather than using the centralized `lib/date.ts` formatters.
- **Implementation Details:**
  - Extended `frontend/src/lib/date.ts` with `formatDateRange(start, end)`.
  - Replaced raw date displays across:
    - `WeeklyAttendanceCard.tsx`: Replaced raw date range with `formatDateRange`.
    - `tools/laboratory/page.tsx`: Standardized future-date/view-only banner with `formatDate(selectedDate, "PPP")`.
    - `history/page.tsx`: Standardized subtitle date range with `formatDateRange`.
    - `calendar/page.tsx`: Standardized semester date display with `formatDateRange`.
    - `laboratory/page.tsx`: Standardized `ActivityRow` date formatting with `formatDate(session.date, "PP")`.
- **Tests Added:** `frontend/src/lib/date.test.ts` (4 unit tests verifying date range formatting and edge cases).
- **Runtime Verification:** Verified consistent date formats across Dashboard, History, Calendar, and Laboratory views.
- **Remaining Limitations:** Machine-readable dates in HTML input attributes (`<input type="date">`) remain in ISO format (`YYYY-MM-DD`) as required by the HTML standard.
- **Regression Risk:** Low.

---

### UIA-012 — Quiz "Must Attend" Redesign

- **Problem:** The Quiz Eligibility card displayed contradictory "must attend" numbers (e.g., showing both Criterion I and Criterion II deficits simultaneously, or displaying negative/zero classes alongside confusing percentages), leaving students uncertain of what action to take.
- **Root Cause:** The UI attempted to dump raw multi-window calculations without synthesizing an actionable summary or contextualizing the criteria hierarchy.
- **Implementation Details:**
  - Redesigned `frontend/src/components/quiz/QuizEligibilityCard.tsx`:
    - Evaluates the backend eligibility contract cleanly:
      - If `is_eligible`: Renders success status and highlights safe-to-miss allowances if available.
      - If `is_recoverable`: Renders actionable guidance focusing on Criterion I ("You need to attend the next N lectures to qualify (Criterion I)") without contradictory deficits.
      - If `NOT_ELIGIBLE`: Clearly explains that the attendance threshold cannot be mathematically reached before the quiz.
      - If `UNRESOLVED`: Renders "Unscheduled" badge with clarification that the quiz cycle is not yet active.
    - Preserved all 4 states (`ELIGIBLE`, `RECOVERABLE`, `NOT_ELIGIBLE`, `UNRESOLVED`).
    - Calculation logic and backend eligibility payloads were completely untouched.
- **Tests Added:** `frontend/src/components/quiz/QuizEligibilityCard.test.tsx` (5 tests covering eligible, recoverable, not eligible, unscheduled, and zero-data states).
- **Runtime Verification:** Verified card presentation and guidance callout for all quiz states.
- **Remaining Limitations:** None.
- **Regression Risk:** Low.

---

### UIA-014 — Overall Attendance Zero-Record N/A State

- **Problem:** Students with zero recorded attendance (e.g. at the beginning of a semester or on newly registered accounts) were shown a misleading 0% or empty red/danger state implying academic failure.
- **Root Cause:** `OverallAttendanceCard.tsx` did not handle the `overall.recorded === 0` (or `overall.overall_pct === null`) edge case distinctly from an actual failing grade.
- **Implementation Details:**
  - Updated `frontend/src/components/dashboard/home/OverallAttendanceCard.tsx`:
    - When `recorded === 0` (or `overall_pct === null`):
      - Renders an em dash (`—`) via `RecordedPct` with no percentage symbol.
      - Displays a neutral "N/A" badge.
      - Renders the progress bar in a neutral variant (`bg-muted-foreground/30`) instead of red/destructive.
      - Displays clear copy: "No sessions recorded yet · N upcoming scheduled" and "Attendance tracking begins once your first class is marked."
    - Added `neutral` variant to `frontend/src/components/ui/progress.tsx`.
- **Tests Added:** `frontend/src/components/dashboard/home/OverallAttendanceCard.test.tsx` (4 tests asserting N/A badge, em dash, neutral progress bar, and healthy/at-risk/critical rendering).
- **Runtime Verification:** Verified with fresh zero-record student account on desktop and mobile viewports.
- **Remaining Limitations:** None.
- **Regression Risk:** Low.

---

### UIA-028 — Zero-Data Quiz Eligibility Neutral State

- **Problem:** When a student had zero attendance records, the Quiz Eligibility card displayed "FAIL" or "NOT ELIGIBLE", making students believe they were barred from exams before classes had even begun.
- **Root Cause:** Lack of a zero-data check in `QuizEligibilityCard.tsx` prior to displaying criteria thresholds.
- **Implementation Details:**
  - Added zero-recorded data guard to `QuizEligibilityCard.tsx`:
    - Checks `totalRecorded === 0` (sum of attended and missed across criteria).
    - In zero-data state:
      - Renders a neutral "No data yet" badge.
      - Criterion status pills display neutral "NO DATA" instead of "FAIL".
      - Final outcome banner displays "NO DATA YET" with an informative message explaining that attendance records are needed before quiz eligibility can be computed.
      - Never displays "FAIL", "NOT ELIGIBLE", or fabricated deficit requirements.
- **Tests Added:** Integrated into `src/components/quiz/QuizEligibilityCard.test.tsx` and `src/lib/canonicalStatus.test.ts`.
- **Runtime Verification:** Verified with zero-record account; card renders neutral "No data yet" and clear guidance.
- **Remaining Limitations:** None.
- **Regression Risk:** Low.

---

## 3. Test & Verification Summary

### Automated Testing

- **Runner:** Vitest v3.2.7 + React Testing Library + jsdom
- **Result:** **12/12 Test Files Passed (76/76 Tests Green)**

```
 ✓ src/components/shared/RecordedPct.test.tsx (6 tests)
 ✓ src/lib/dejargon.test.ts (11 tests)
 ✓ src/components/layout/navItems.test.ts (4 tests)
 ✓ src/lib/canonicalStatus.test.ts (13 tests)
 ✓ src/components/dashboard/home/GreetingHeader.test.tsx (8 tests)
 ✓ src/app/(authenticated)/tools/feedback/page.test.tsx (6 tests)
 ✓ src/components/dashboard/home/OverallAttendanceCard.test.tsx (4 tests)
 ✓ src/lib/date.test.ts (4 tests)
 ✓ src/app/(authenticated)/profile/page.test.tsx (1 test)
 ✓ src/components/quiz/QuizEligibilityCard.test.tsx (5 tests)
 ✓ src/components/layout/MobileBottomNav.test.tsx (3 tests)
 ✓ src/components/shell/SettingsModal.test.tsx (11 tests)

Test Files  12 passed (12)
     Tests  76 passed (76)
```

### Static Analysis

- **TypeScript:** `npx tsc --noEmit` exited **0** with **zero errors**.
- **ESLint:** Run on all modified and new files exited **0** with **zero errors and zero warnings**.

---

## 4. Confirmation of Boundaries

1. **Backend Changes:** **ZERO** backend files were touched or modified. Backend services, migrations, and APIs remain strictly untouched.
2. **P0 Issues:** No Phase 1 P0 remediation code was modified or reverted.
3. **P2 / P3 Issues:** No P2 or P3 issues were implemented. Work was strictly confined to the 9 specified P1 items.
4. **Calculations:** No attendance or quiz eligibility formulas were altered.

---

## 5. Files Changed Summary

```
frontend/src/app/(auth)/login/page.tsx
frontend/src/app/(auth)/signup/page.tsx
frontend/src/app/(authenticated)/calendar/page.tsx
frontend/src/app/(authenticated)/history/page.tsx
frontend/src/app/(authenticated)/laboratory/page.tsx
frontend/src/app/(authenticated)/profile/page.tsx
frontend/src/app/(authenticated)/tools/events/page.tsx
frontend/src/app/(authenticated)/tools/laboratory/page.tsx
frontend/src/app/(authenticated)/tools/quiz-schedule/page.tsx
frontend/src/components/dashboard/SubjectAttendanceCard.tsx
frontend/src/components/dashboard/home/GreetingHeader.tsx
frontend/src/components/dashboard/home/OverallAttendanceCard.tsx
frontend/src/components/dashboard/home/QuizSnapshotCard.tsx
frontend/src/components/dashboard/home/WeeklyAttendanceCard.tsx
frontend/src/components/dashboard/home/status.ts
frontend/src/components/events/EventFormDialog.tsx
frontend/src/components/layout/navItems.ts
frontend/src/components/quiz/QuizEligibilityCard.tsx
frontend/src/components/shared/ErrorState.tsx
frontend/src/components/shell/AppearanceModal.tsx
frontend/src/components/shell/FeedbackModal.tsx
frontend/src/components/shell/InstallAppModal.tsx
frontend/src/components/shell/SettingsModal.tsx
frontend/src/components/shell/ShellDialog.tsx
frontend/src/components/ui/progress.tsx
frontend/src/lib/api.ts
frontend/src/lib/date.ts
frontend/src/lib/statusLabels.ts
frontend/src/lib/canonicalStatus.ts (new)
frontend/src/lib/canonicalStatus.test.ts (new)
frontend/src/lib/date.test.ts (new)
frontend/src/lib/dejargon.test.ts (new)
frontend/src/components/layout/navItems.test.ts (new)
frontend/src/components/layout/MobileBottomNav.test.tsx (new)
frontend/src/components/dashboard/home/GreetingHeader.test.tsx (new)
frontend/src/components/dashboard/home/OverallAttendanceCard.test.tsx (new)
frontend/src/components/quiz/QuizEligibilityCard.test.tsx (new)
frontend/src/app/(authenticated)/profile/page.test.tsx (new)
docs/PHASE_2_UI_UX_REMEDIATION_REPORT.md (new)
```
