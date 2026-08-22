# Phase 12B — Track / Dashboard / Calendar Responsive Experience: Implementation Report

- **Phase:** 12B (Phase 12 — Mobile / Responsive Experience)
- **Date:** 2026-08-21
- **Base:** working tree clean at `b39d1b0` (Phase 12A, user-committed)
- **Prior art:** `docs/phase_12/phase_12_architecture_audit.md` (12.0), `docs/phase_12/phase_12a_implementation_report.md` (12A — frozen, not reopened)

---

## 1. Scope

Responsive-experience slice for the three core surfaces — Track Attendance (`/tools/laboratory`), Dashboard (`/dashboard`), Calendar (`/calendar`) — including their child components. **No business logic, API contracts, calculations, or calendar semantics changed. No backend/DB/migration/API/PWA surface touched. Phase 12A files untouched.**

## 2. Architecture / readiness findings

| Surface | Finding |
|---|---|
| Track | Nav row fits at 320px but all controls were 32px tall (input `h-8 w-40`, Today `h-8` override); center column was fixed-width. Session card: time + badges (Badge = `whitespace-nowrap shrink-0`) could collide at 320 (card inner ≈256px); actions row had a fixed `h-9` box that the 12A `h-10` mobile buttons exceed; Change buttons carried explicit `h-7` overrides (28px — recorded as 12B residual in the 12A report). Summary + bottom cards already fit. |
| Dashboard | Already mobile-first (`grid-cols-1 lg:grid-cols-2`, `min-w-0`, `truncate`, `flex-wrap` patterns everywhere). Residuals: Today rows' badge row had no wrap; Overall delta row (`items-end justify-between`, no wrap) cramped the meta line at 320; Weekly rows used `gap-3` making 64+56+64+36+progress = exactly 256px (zero slack at 320 content). Greeting/Quiz/Attention/Upcoming cards verified fine. |
| Calendar | **Real overflow found:** month nav row ≈310px vs 288px content at 320 (fixed `w-36` label + 40px arrows + Today) — would clip in the shell. Grid cells ≈31px at 320 (GlassCard `p-4` + `gap-1.5`) — usable but unnecessarily small. DayDetail, legend (`flex-wrap`), loading/error/empty states already responsive. |
| Shared primitives | PageHeader, Badge, Card, GlassCard, lib/date, all 12A files: **NOT changed** (page-local fixes only). |

## 3. Actual problems discovered (and fixes)

1. **Calendar month nav overflow at 320px** → nav row `flex flex-wrap`, label `min-w-0 w-28 sm:w-36` (single row now ≈276px < 288; wraps gracefully beyond that).
2. **Calendar grid cells 31px at 320** → grid card `p-2 sm:p-4` + grid gaps `gap-1 sm:gap-1.5` (cells ≈35px; desktop byte-identical).
3. **Track nav controls 32px tall** → input `h-10 sm:h-8 w-full sm:w-40`; Today `sm:h-8` (mobile 40px via 12A foundation, desktop 32px identical). Center column `flex-1 min-w-0` so the input stretches between arrows on mobile.
4. **Track session card header collision** → left column `min-w-0 flex-1`; badge container `flex-wrap justify-end` (long labels like MID-SEM PRACTICAL drop to their own line instead of colliding).
5. **Track actions row clips 12A buttons** → fixed `h-9` box dropped; buttons size themselves (40px mobile).
6. **Track Change buttons 28px on mobile** → removed the explicit `h-7` override (mobile 40px from the foundation; desktop stays `sm:h-7` = 28px, identical).
7. **Dashboard: Today badge row / Overall delta row / Weekly row slack** → `flex-wrap` on the first two; `gap-2 sm:gap-3` on weekly rows (progress bar keeps room at 320).

## 4. Files changed

| File | Change |
|---|---|
| `frontend/src/app/(authenticated)/calendar/page.tsx` | Nav row `flex-wrap` + label `min-w-0 w-28 sm:w-36`; grid card `p-2 sm:p-4`; skeleton card + gaps matched |
| `frontend/src/components/calendar/CalendarGrid.tsx` | Grid gaps `gap-1 sm:gap-1.5` (weekday + cell grids) |
| `frontend/src/app/(authenticated)/tools/laboratory/page.tsx` | Date nav: fluid center column, input `h-10 w-full sm:h-8 sm:w-40`, Today `sm:h-8` |
| `frontend/src/components/dashboard/TrackSessionCard.tsx` | Header: fluid left column + wrapping badges; actions row auto-height; Change buttons lose `h-7` override |
| `frontend/src/components/dashboard/home/TodayAttendanceCard.tsx` | Badge row `flex-wrap` |
| `frontend/src/components/dashboard/home/OverallAttendanceCard.tsx` | Delta row `flex-wrap` |
| `frontend/src/components/dashboard/home/WeeklyAttendanceCard.tsx` | Weekly rows `gap-2 sm:gap-3` |

## 5. Responsive behavior implemented

- **<640px (mobile):** Track date input stretches full width between 40px arrows; Today is full-width 40px; session badges wrap; Present/Absent and Change controls ≥40px. Dashboard cards reflow to a single column (already `grid-cols-1`) with wrapping meta rows. Calendar nav fits on one row (label 112px); grid cells ≈35px at 320px with visible event dots, session counts, and reason text; DayDetail stacks below the grid (already `lg:` two-column).
- **640–767px (tablet):** desktop button/gap sizes return (`sm:` restores) while the bottom nav still provides navigation.
- **≥768px (desktop):** byte-identical — every change is gated by `sm:`/`md:` or only engages on overflow (`flex-wrap` is inert when content fits).

## 6. Desktop-preservation strategy

All changes use the established `sm:` restore convention. The only desktop-visible changes are `flex-wrap` additions (inert unless content overflows — nothing overflows at md+) and the Track header `gap-2` (absorbed by the `flex-1` column; no visual delta). No desktop composition, spacing, or typography values changed.

## 7. Phase 12A compatibility

- **12A files untouched:** MobileBottomNav, AppShell, ShellDialog, NotificationCenter/Bell, `ui/button.tsx` foundation — zero diffs.
- **Foundation reused, not overridden:** all touch-target gains come from the 12A size variants; the only class-level additions are `sm:h-8` restores that re-instate the exact pre-12A desktop sizes where 12A had slightly changed them (Track input/Today: 32px desktop). The Track Change buttons dropped their own `h-7` override (the 12A report listed this as the 12B residual — now resolved).
- No 12B page required any 12A architectural change.

## 8. Intentionally NOT changed

- All backend files, migrations, DB, API schemas/contracts, engines (attendance/quiz/eligibility/calendar/analytics).
- 12A shell/navigation/notification code (see §7).
- PageHeader, Badge, Card, GlassCard, `lib/date`, hooks (`useCalendarMonth`, `useDailySessions`, etc.), types.
- DayDetail (already responsive), calendar grid interaction model (7-column month calendar preserved — no date-picker substitution), legend, empty/loading/error semantics, GreetingHeader, QuizSnapshotCard, AttentionRequiredCard, UpcomingEventsCard (verified fine at 320px).
- `css/responsive.css` remains unimported legacy; no new breakpoints introduced.

## 9. Static verification

| Gate | Result | Status |
|---|---|---|
| `npx tsc --noEmit` | PASS | **VERIFIED** |
| ESLint (7 changed files) | PASS | **VERIFIED** |
| `npm run build` | PASS (15 routes prerendered) | **VERIFIED** |
| `git diff --check` | PASS (only pre-existing LF→CRLF warnings) | **VERIFIED** |
| `git status --short` / `git diff --stat` | 7 frontend files, +35/−23, no backend/12A/artifacts | **VERIFIED** |
| Manual diff review | class-level responsive changes only; no logic, no hardcoded values, no duplicated calculations, no new deps | **VERIFIED** |

## 10. Manual testing checklist (owner)

**NOT PERFORMED BY AGENT** — browser/manual verification is the owner's responsibility.

At **320px**: Calendar — prev/next/Today all visible and tappable, month label not clipped, grid day numbers legible, event dots + counts visible, selected/today rings distinct, non-working days distinguishable; Track — date input stretches between arrows, Today full-width, session cards show time + badges without collision (force a MID-SEM PRACTICAL/Quiz Day session), Present/Absent buttons comfortable, Change button ≥40px, no horizontal scroll anywhere; Dashboard — Today rows wrap, Overall meta lines wrap with delta below, Weekly rows keep a visible progress bar, no overflow.

At **360–412px**: same surfaces re-checked; grid cells ≥40px; Track cards comfortable.

At **768px+ (desktop regression)**: month nav row identical (label w-36), grid gaps 6px, grid card padding 16px, Track input 160×32px + Today 32px in a centered row, session card headers unchanged, Change buttons 28px, dashboard cards identical — byte-identical to `b39d1b0` visually.

## 11. Known limitations

- Grid cells ≈35px at exactly 320px (below the 40px ideal) — inherent to the preserved 7-column month calendar; tap targets remain the full cell, and cell size grows to ≥40px from ≈360px up. Acceptable per audit guidance ("do not blindly shrink"; no date-picker substitution).
- Long class-count strings inside 35px cells truncate with ellipsis (e.g. "3 class…") — counts remain visible; desktop shows full text.
- 640–767px band: bottom nav present, desktop-size controls (pre-existing nav gap unchanged, as in 12A).

## 12. Ready for hard-stop?

Yes. Static gates all **VERIFIED**; scope discipline upheld; 12A intact; desktop preserved by construction. Browser/manual testing remains **NOT VERIFIED / OWNER MANUAL TEST** (checklist in §10). Governance updated. **HARD STOP** — no commit; 12C NOT STARTED.

---

## 12B internal assessment (evidence base, §2 summary)

- Track: nav fits but 32px controls; session card header collision risk at 256px inner width; h-9 actions box vs h-10 buttons; h-7 Change overrides (12A-documented residual).
- Dashboard: minimal residuals — three wrap/gap fixes; all cards otherwise verified at 320px (min-w-0 + truncate + flex-wrap already present).
- Calendar: nav row ≈310px > 288px content at 320 (real overflow, highest-risk item); cells 31px → 35px via padding/gap reduction; DayDetail/legend/states fine.
- Shared: PageHeader/badge/card/date utils not modified; fixes are page-local; no backend interaction required at any point (per the audit's "NO BACKEND CHANGE REQUIRED" verdict).