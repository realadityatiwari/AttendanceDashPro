# Phase 1 — P0 UI/UX Remediation Report

**Date:** 2026-09-30
**Scope:** The four P0 issues from `docs/UI_UX_AUDIT_REPORT.md` (UIA-001, UIA-002, UIA-008, UIA-010). No P1/P2/P3 work was performed.
**Discipline:** All changes are frontend-only. Backend files that appear modified in the working tree (notifications/quiz services, verify scripts, new `docs/*AUDIT*.md` files) belong to a **separate, concurrent workstream and were not touched by this phase**.

---

## 1. Issues Fixed

| ID | Summary | Status |
|---|---|---|
| UIA-002 | Settings false dirty state + no-op Save on open | FIXED |
| UIA-001 | Recorded-only percentage presented as "83% overall" | FIXED |
| UIA-008 | Students could deep-link into the admin feedback surface and get a misleading error | FIXED |
| UIA-010 | Settings "Browser notifications" row collapsed to one-word lines | FIXED |

---

## 2. UIA-002 — Settings False Dirty State

**ISSUE:** The Settings modal showed "You have unsaved changes" with enabled Discard and Save buttons the moment it opened, before any user edit. Save was enabled but silently no-opped.

**ROOT CAUSE:** `frontend/src/components/shell/SettingsModal.tsx` computed:

```ts
const dirty = !!preferences && (draft?.x !== preferences.x || ...)
```

With no edit yet, `draft` is `null`, so every `draft?.field` is `undefined` and `undefined !== value` is true for all three fields → `dirty === true` on open. `handleSave` early-returns when `draft === null`, making the enabled Save a no-op.

**FIX:** Dirty now requires a draft to exist:

```ts
const dirty = !!draft && !!preferences && (draft.class_reminders !== ...)
```

Behavior now: opens clean ("All changes saved", Save/Discard disabled) → dirty only after a real change → reverting to persisted values clears dirty → Save persists the draft and returns to clean ("Saved" confirmation) → Discard resets the draft → close/reopen resets. Save/Discard remain disabled when clean, so the no-op path is unreachable.

**Other controls inspected for the same pattern:** `base` (display values) correctly falls back to persisted values; `updateDraft` builds the draft from persisted values, so a draft always exists once a control is touched; controls are disabled while preferences load, so a draft cannot be created pre-load. No other false-dirty path exists. The two toggle switches had no accessible names (found while writing tests); `aria-label` was added — a one-attribute accessibility fix inside the same component, noted here for transparency.

**FILES:** `frontend/src/components/shell/SettingsModal.tsx`

**TESTS:** `frontend/src/components/shell/SettingsModal.test.tsx` — 11 tests covering the required matrix: opens clean; shows persisted values; dirty after modification; reversion clears dirty; save persists the exact draft and returns to clean; Save cannot invoke the API with no draft; Discard resets; close/reopen resets.

**RUNTIME VERIFICATION:** Full interactive verification of the modal was **blocked by the test automation environment**: Base UI menu items inside the user-menu dropdown cannot be activated by synthetic input (trusted clicks dismiss the menu before item activation; untrusted events are rejected by the popup layer), across a dev-server restart and multiple strategies. The modal opened and was visually verified repeatedly during the audit phase (same code path); after this phase the state machine is verified by the 11 component tests above. **A 10-second manual check is recommended:** open user menu → Settings → confirm "All changes saved" + disabled Save on open.

**REGRESSION RISK:** Low. The change is a boolean guard; the save path (`savePreferences(draft)`) is untouched and the existing disabled-state logic now correctly reflects it.

---

## 3. UIA-001 — Recorded-Only Percentage Labeling

**ISSUE:** `/history` rendered "83% overall" beside "286 total / 280 pending"; the Dashboard "Overall Attendance" and "This Week" cards rendered bare "83%". The figure is *recorded-only* (present ÷ (present+absent)); pending is never treated as absent, but no headline surface said so.

**ROOT CAUSE (presentation only — calculation untouched):** `history/page.tsx` interpolated `${formatPct(summary.pct)} overall`; the dashboard cards rendered `formatPct(...)` with no basis qualifier, even though `lib/date.ts` already owns all formatting and `/subjects` documents the recorded-only semantics in its detail view.

**FIX:** New shared presentation component `frontend/src/components/shared/RecordedPct.tsx`:

- Renders the backend percentage **unchanged** (same `formatPct` rounding as before) followed by an explicit "**of recorded**" qualifier.
- Renders an em dash with **no** qualifier when the value is `null` (zero-record) — a student with nothing recorded can never see a percentage at all.

Consumers:

1. `/history` summary header — "83% of recorded"; plus a caption when `attended + missed === 0`: "No sessions recorded yet — mark classes to build your history."
2. Dashboard `OverallAttendanceCard` — big value + "of recorded"; zero-record caption "No sessions recorded yet" replaces "0 attended · 0 recorded" (pending still shown when recorded > 0). N/A badge unchanged.
3. Dashboard `WeeklyAttendanceCard` — same qualifier on the weekly headline so it can never diverge from the Overall card.

The Lab page already states its basis explicitly and Quiz Eligibility is out of scope; neither was modified. No second calculation was introduced; quiz eligibility math and backend logic are untouched.

**FILES:** `frontend/src/components/shared/RecordedPct.tsx` (new), `frontend/src/app/(authenticated)/history/page.tsx`, `frontend/src/components/dashboard/home/OverallAttendanceCard.tsx`, `frontend/src/components/dashboard/home/WeeklyAttendanceCard.tsx`

**TESTS:** `frontend/src/components/shared/RecordedPct.test.tsx` — 6 tests: 83.333 → "83% of recorded" (5 present / 1 absent case), rounding preserved, 100% recorded, 0% recorded, `null` → em dash with no qualifier, `undefined` → em dash.

**RUNTIME VERIFICATION (✔ browser, screenshots):**

- **1440×900** — History: "**83% of recorded**" with 297/5/1/291/0 stat tiles; Dashboard: "83% of recorded" on both Overall Attendance and This Week.
- **768×1024** — Dashboard: both cards render the qualifier correctly.
- **375×812** — History: "83% of recorded" fits on one line in the summary header.
- **Zero-record (fresh account, runtime)** — History: em dash + "No sessions recorded yet…" with 0/0/0/297/0 tiles; Dashboard: N/A badge, em dash, "No sessions recorded yet", no percentage anywhere.
- **100% / 0% recorded:** covered by unit tests (would require mutating attendance records to observe; the presentation path is identical to the runtime-verified 83% case).

**REGRESSION RISK:** Low — display-only; the value, its rounding, and all underlying semantics are unchanged.

---

## 4. UIA-008 — Route Guard for `/tools/feedback`

**ISSUE:** Students who deep-linked or refreshed `/tools/feedback` (an admin surface inside the student route group) got "Failed to load data — You do not have access to the feedback admin surface." — an error that looked like a data failure, with internal terminology, on a dead-end page.

**ROOT CAUSE:** The page's non-admin guard rendered an `ErrorState` in place; the route itself was unguarded for students. (The backend was and remains the authorization boundary — `GET /api/v1/feedback/admin` 403s non-admins; nothing was weakened.)

**FIX:** `frontend/src/app/(authenticated)/tools/feedback/page.tsx` now guards the route following the established `(admin)/layout.tsx` state machine:

- `authLoading` → neutral skeletons (no admin content).
- `!user` → render **nothing**; AuthContext owns the redirect to `/login` (unchanged behavior for unauthenticated access).
- `profileLoading` / `profileError` / no profile → neutral skeletons; the old misleading error is never shown.
- Confirmed non-admin → `router.replace("/dashboard")` and render **nothing** — no part of the admin surface (not even its header) appears, and `replace` keeps the admin route out of history.
- Admin → the review surface renders exactly as before.

**FILES:** `frontend/src/app/(authenticated)/tools/feedback/page.tsx`

**TESTS:** `frontend/src/app/(authenticated)/tools/feedback/page.test.tsx` — 6 tests: student deep-link → `router.replace("/dashboard")` + zero admin content + neither the old "Failed to load data" nor "feedback admin surface" copy; renders nothing while redirecting; admin keeps the working list; loading → skeletons with no redirect; unauthenticated → renders nothing; profile failure → no admin surface.

**RUNTIME VERIFICATION (✔ browser, student account):**

- Direct navigation to `/tools/feedback` → lands on `/dashboard` (dashboard content confirmed, no error copy, no admin content).
- Refresh while on `/tools/feedback` → `/dashboard`.
- Browser **Back** after the redirect → `/dashboard` (the admin route is not in history); **Forward** → `/dashboard`. The admin surface is never exposed.
- **Admin access intact:** verified by the component test (admin renders the list, no redirect). Interactive admin verification was not possible at runtime because no admin credentials are available in the dev database (documented limitation); the admin render path is unchanged apart from the guard placed *before* it.

**REGRESSION RISK:** Low. The admin branch renders identical markup; the guard only adds earlier exits. Backend authorization untouched.

---

## 5. UIA-010 — Settings Browser-Notifications Row

**ISSUE:** The row paired long copy with a `shrink-0` wide button inside the fixed-width (≈384 px) dialog; the text column collapsed to one word per line.

**ROOT CAUSE:** `min-w-0` on the text block allowed unbounded shrink, so the flex line always "fit" and `flex-wrap` was absent — the button starved the text.

**FIX (same file as UIA-002, layout only):**

- Row container: `flex items-start justify-between gap-3` → `flex flex-wrap items-start justify-between gap-x-3 gap-y-2.5`.
- Text block: `min-w-0` → `min-w-48` (+ `flex-1`), so when the two children no longer fit side by side, the action wraps to its own line instead of crushing the copy; the text block always keeps ≥192 px.
- Action container: `ml-auto` so it right-aligns on the shared line *and* on its own wrapped line.
- No font shrinking; existing tokens/primitives only. The short-action states (e.g. "Disable") still fit horizontally; the wide "Enable push notifications"/"Enable browser notifications" states wrap gracefully.

**FILES:** `frontend/src/components/shell/SettingsModal.tsx`

**TESTS:** 3 tests in `SettingsModal.test.tsx`: granted state renders title/description/"Disable"; the wide enable action renders with the exact full description sentence intact; structural guard — row has `flex-wrap` and the text block has `min-w-48`.

**RUNTIME VERIFICATION:** Layout verification at the three viewports is part of the same blocked Settings-modal interaction described under UIA-002; the structural classes are unit-asserted. **Manual check recommended:** open Settings and confirm the "Browser notifications" row reads normally with the enable button on its own line.

**REGRESSION RISK:** Low — class-level layout change inside one row; all row states (unsupported / denied / default / working / enabled / error / retry) keep the same JSX branches.

---

## 6. Test & Verification Summary

| Check | Result |
|---|---|
| `npx tsc --noEmit` | ✅ clean |
| `npm test` (vitest, 3 files) | ✅ 23/23 passed |
| `eslint` on all changed files | ✅ clean (2 pre-existing `react-hooks/set-state-in-effect` errors in `history/page.tsx` confirmed present at HEAD; not introduced or modified by this phase) |
| Runtime: History label (3 viewports) | ✅ "83% of recorded" |
| Runtime: Dashboard Overall + Weekly (1440/768) | ✅ "83% of recorded" |
| Runtime: zero-record History + Dashboard | ✅ em dash, no percentage, friendly caption, N/A badge |
| Runtime: `/tools/feedback` student deep-link / refresh / back / forward | ✅ always `/dashboard`, no error copy, no admin content |
| Runtime: Settings modal interactive walk | ⚠ blocked by automation environment (Base UI popup vs synthetic input); state machine covered by 11 component tests; manual check recommended |

**Test infrastructure note:** the frontend had no test runner. `vitest` + `@testing-library/*` + `jsdom` were added as devDependencies (`frontend/package.json`, `frontend/package-lock.json`) with `frontend/vitest.config.ts`, `frontend/src/test/setup.ts`, and an `npm test` script. No runtime dependencies were added.

---

## 7. Files Changed (complete list for this phase)

```
frontend/package.json                                        (test script + dev deps)
frontend/package-lock.json                                   (from npm install -D)
frontend/vitest.config.ts                                    (new)
frontend/src/test/setup.ts                                   (new)
frontend/src/components/shared/RecordedPct.tsx               (new)
frontend/src/components/shared/RecordedPct.test.tsx          (new)
frontend/src/components/shell/SettingsModal.tsx              (UIA-002, UIA-010)
frontend/src/components/shell/SettingsModal.test.tsx         (new, 11 tests)
frontend/src/app/(authenticated)/history/page.tsx            (UIA-001)
frontend/src/app/(authenticated)/tools/feedback/page.tsx     (UIA-008)
frontend/src/app/(authenticated)/tools/feedback/page.test.tsx (new, 6 tests)
frontend/src/components/dashboard/home/OverallAttendanceCard.tsx (UIA-001)
frontend/src/components/dashboard/home/WeeklyAttendanceCard.tsx  (UIA-001)
docs/UI_UX_AUDIT_REPORT.md                                   (prior audit phase)
docs/PHASE_1_UI_UX_REMEDIATION_REPORT.md                     (this file)
```

**Not touched by this phase (present in the working tree from a concurrent workstream):** all `backend/**` modifications and the untracked `backend/scripts/audit_ro_*.py`, `docs/REMEDIATION_READINESS_REPORT.md`, `docs/SYSTEM_FUNCTIONAL_BACKEND_AUDIT_REPORT.md` files.

---

## 8. Remaining Limitations

1. **Settings modal interactive runtime walk** — blocked by the automation environment as described; logic covered by tests; manual check recommended (UIA-002, UIA-010).
2. **Admin-side runtime check of `/tools/feedback`** — no admin credentials available locally; covered by component test and an unchanged render path.
3. **100%/0%-recorded runtime screenshots** — covered by unit tests; observing them live would require mutating attendance data (the 83% and 0% runtime cases exercise the identical rendering path).
4. Test account `2401220999001` ("UI Audit Runner") and `2401220999002` ("Zero Record Check") were created in the local dev database for verification and remain there (dev-only, no production impact).

---

## 9. Intentionally NOT Touched (belong to later phases)

- P1: de-jargonization copy pass; mobile tab restructure; greeting name split; status-vocabulary consolidation; quiz "must attend" redesign; ISO date formats; Lab page density; UUID card removal.
- P2: progress-bar unification; GlassCard/Card consolidation; ConfirmDialog success variant; auth-gate flash fix; Mark Attendance date/title de-duplication; dashboard card voids; date-input strategy; quiz error-card token swap; "LIVE" badge; History "Logged"/"State" copy; Profile modal/page merge; touch-target floors; getting-started ✕ placement.
- P3: all minor refinements from the audit backlog.
- Quiz eligibility UX and all backend attendance/eligibility logic (explicitly out of scope).
