# Phase 12A — Responsive Foundation & Mobile Navigation: Implementation Report

- **Phase:** 12A (Phase 12 — Mobile / Responsive Experience)
- **Date:** 2026-08-21
- **Base:** working tree clean at `591fbb1` (Phase 11F, user-committed)
- **Prior art:** `docs/phase_12/phase_12_architecture_audit.md` (12.0), `docs/17_AI_HANDOFF.md:41-43` (S4 navigation contract)

---

## 1. Objective

Restore a genuine mobile navigation experience and make the shared application shell mobile-safe (touch targets, dialog scrolling, safe-area clearance) — the smallest safe slice of Phase 12 — while keeping desktop (≥768px) behavior byte-identical and touching zero backend/DB/migration/API/PWA surface.

## 2. Authorized scope

Explicitly authorized slice only: mobile bottom navigation (exactly 4 tabs + "More" surface), AppShell integration, touch-target foundation in `ui/button.tsx`, shell dialog scroll safety, notification hit areas, governance updates, and a static verification report. **No browser/manual testing was performed — that is the user's responsibility** (checklist in §8).

## 3. Architecture decision

**Hybrid D (from audit §4): 4-tab bottom nav + Profile-tab "More" sheet**, per the S4 prior art:

- Primary tabs (exactly 4, never a 5th): **Home** `/dashboard` · **Attendance** `/subjects` · **History** `/history` · **Profile** `/profile`.
- The **Profile tab is the S4-compatible profile/menu anchor** — it opens a controlled bottom sheet (existing `ui/sheet.tsx`, `side="bottom"`, safe-area padding, `rounded-t-2xl`) hosting Profile + the 5 Academic Tools: Track `/tools/laboratory`, Laboratory `/laboratory`, Quiz Eligibility `/tools/quiz-schedule`, Calendar `/calendar`, Events `/tools/events`. Every destination stays one tap away; no new routes; no 5th tab.
- Bottom nav is `md:hidden`; desktop keeps the 8-item TopNav (`hidden md:flex`, untouched). Desktop shell padding remains `md:p-6 lg:p-8` (verified byte-identical via diff review).
- Touch-target policy: **mobile base sizes + `sm:` desktop restores inside `ui/button.tsx`** — NOT a global `h-10`/`h-11` replacement. All size variants move to ≥36–44px on mobile and return to their exact previous classes at ≥640px, so every existing consumer (dialogs, sheets, calendar arrows, notification actions, card buttons) inherits adequate mobile hit areas automatically.
- Scroll safety: ShellDialog content capped at `max-h-[90dvh] overflow-y-auto` (same pattern as `EventFormDialog.tsx:337`), fixing all 6 shell modals on short screens; NotificationCenter list capped at `max-h-[50dvh] md:max-h-[26rem]` to avoid nested scrolling.
- `app/layout.tsx` NOT modified: the Next.js default viewport meta is already correct; `viewport-fit=cover` would require header safe-area handling (scope creep); `env(safe-area-inset-bottom)` is a harmless no-op without it.

## 4. Files changed / created

| File | Change |
|---|---|
| `frontend/src/components/layout/MobileBottomNav.tsx` | **NEW** — fixed bottom nav (`md:hidden`, `z-40`, border, backdrop-blur, `pb-[env(safe-area-inset-bottom)]`), 4 tabs (min-h-14 ≈ 56px targets), controlled More bottom sheet (rows h-12 ≈ 48px), `usePathname` exact-match active states, lucide icons mirroring TopNav |
| `frontend/src/components/layout/AppShell.tsx` | Renders `<MobileBottomNav />`; container `p-4 pb-28 md:p-6 lg:p-8` (bottom clearance only below `md`) |
| `frontend/src/components/ui/button.tsx` | Size variants: default `h-10 sm:h-8` · xs `h-9 sm:h-6` · sm `h-10 sm:h-7` · lg `h-11 sm:h-9` · icon `size-10 sm:size-8` · icon-xs `size-9 sm:size-6` · icon-sm `size-10 sm:size-7` · icon-lg `size-11 sm:size-9` |
| `frontend/src/components/shell/ShellDialog.tsx` | DialogContent adds `max-h-[90dvh] overflow-y-auto` (EventFormDialog pattern) |
| `frontend/src/components/notifications/NotificationBell.tsx` | `-m-2.5 p-2.5 sm:-m-1.5 sm:p-1.5` → ≈40px mobile hit area (desktop unchanged) |
| `frontend/src/components/notifications/NotificationCenter.tsx` | List `max-h-[50dvh] md:max-h-[26rem]` (no nested scroll) |

Intentionally **NOT** modified (documented rationale): `TopNav.tsx` / `UserMenu.tsx` (avatar hit area already ≈44px; brand + bell + avatar ≈292px fits 320px), `ui/dialog.tsx` / `ui/sheet.tsx` (close buttons inherit the `icon-sm` upgrade automatically), `app/layout.tsx` (see §3), all page components (12B–12F scope), all backend files.

## 5. Verification & gates (all PASS)

| Gate | Result |
|---|---|
| `npx tsc --noEmit` (frontend) | PASS |
| `npx eslint` (6 changed files) | PASS |
| `npm run build` | PASS — all 15 routes prerendered |
| `git diff --check` | PASS (only pre-existing LF→CRLF normalization warnings) |
| `git status --short` / `git diff --stat` | Scope = 5 modified frontend files + 1 new component + `docs/phase_12/`; **zero backend changes, zero migrations, zero DB mutation, zero generated artifacts** |

## 6. Desktop preservation

- All mobile classes are gated by `sm:`/`md:` prefixes; desktop (≥768px) receives the exact previous classes: `md:p-6 lg:p-8` container, `sm:h-8`/`sm:h-7`/`sm:size-7`… button sizes, `-m-1.5 p-1.5` bell padding, `max-h-[26rem]` notification list, `max-h-[90dvh]` dialog cap (only engages above 90% of viewport height), `md:hidden` nav.
- Diff review confirms the only desktop-visible change is the ShellDialog scroll cap (engagement threshold: content taller than 90dvh — nothing currently reaches it at 768px+) and the TopNav area (unmodified).
- The 640–767px band is unaffected: it had no top nav before and has none now (nav visibility logic unchanged); bottom nav appears below `md` per the contract.

## 7. Known residuals / deferred to later sub-phases (NOT defects)

- Page-level explicit height overrides (`size="sm"` + `className="h-7"` on history Reset, events admin actions) stay 28px on mobile — **12B/12C scope** (page files), documented here per the "do not weaken or hide" rule.
- Calendar month nav row at exactly 320px is tight (40px arrows + fixed `w-36` label + Today); flex-shrink absorbs it, but a `w-32 sm:w-36` label and the track `w-40` date input are **12B scope**.
- Laboratory tab bar (~380px nowrap) remains clipped on small screens — **12C scope** (highest residual overflow risk, unchanged from the audit).
- `viewport-fit=cover` + header safe-area handling — deferred (scope creep; see §3).

## 8. Manual testing checklist (user's responsibility — NOT performed by the agent)

At **320px**: bottom nav shows 4 tabs, no clipping; Profile opens the More sheet; all 6 More destinations navigate and the sheet closes; Tap "Today" on Calendar and the card actions (unread target ≥36px); bell + avatar fully tappable; History Reset remains its documented 28px (12B); top nav brand + bell + avatar fit.

At **360–412px**: track date navigation row not clipped; notification dialog (bell → notification center) scrolls to the last item (single scroll region, no nested scroll); Settings modal scrolls to Discard/Save; Laboratory tab bar status accepted (12C); bottom nav does not cover the last card's buttons (pb-28 clearance).

At **768px+ (desktop)**: **byte-identical layout to before 12A** — no bottom nav, 8-item top nav, original paddings, button sizes, dialog and notification center dimensions unchanged.

## 9. Frozen systems protection

No changes to: backend code, DB schema/data, alembic migrations (single head `d1e2f3a4b5c6` untouched), API contracts, SWR/auth/engine code, PWA surface, Phase 1–11 components. Diff scope verified (§5). Phase 11 verifiers unaffected (no backend or notification behavior changed).

## 10. Governance updates

- `MASTER_ROADMAP.md` — line 9 "Next phase" + table row 12 + Phase 12 section: **label fixed** ("PWA & Offline" → "Mobile / Responsive Experience"), 12.0/12A COMPLETE, 12B NEXT, Phase 13 stays PWA.
- `implementation_plan.md` — "BLOCKED / BACKEND REQUIRED" line 39 marked DONE by 12A; new Phase 12 / 12A section appended (scope, decisions, gates, HARD STOP).
- `task.md` — line 28 marked resolved by 12A; Phase 12A checklist complete; 12B–12F deferred list added.
- `walkthrough.md` — line 1069 label fixed; chronological 12A walkthrough entry appended; browser/manual testing explicitly marked as not performed.

## 11. Compliance with the audit & prompt constraints

4 tabs only ✅ · no 5th tab ✅ · Profile-tab anchor per S4 ✅ · existing `ui/sheet.tsx` reused ✅ · no new routes ✅ · `md:hidden` nav ✅ · desktop byte-identical ✅ · touch foundation not a global replacement ✅ · ShellDialog scroll safety ✅ · no backend/DB/migration/API/PWA ✅ · `app/layout.tsx` untouched ✅ · all 15 report sections ✅ · no commit ✅.

## 12. Deviations

None. (One pre-commit decision documented rather than deviated: the 640–767px tablet band keeps its pre-existing no-top-nav behavior — unchanged by 12A by design.)

## 13. Risk assessment & acceptance

| Risk | Level | Mitigation |
|---|---|---|
| Layout regression on desktop | Low | Diff-verified; `sm:`/`md:` gates; build PASS |
| Bottom nav covering content | Low | `pb-28` clearance + safe-area padding |
| Short-screen dialog clipping | Removed | ShellDialog 90dvh cap (all 6 modals) |
| Mobile touch targets | Reduced | ≥36px buttons everywhere via foundation; residual 28px overrides are explicit page-level classes (12B) |
| Tablet band (640–767) nav gap | Accepted (pre-existing) | Bottom nav now present there; top nav unchanged |

## 14. Summary

Phase 12A delivered the responsive foundation exactly per the audit and the S4 contract: 4-tab bottom nav + More sheet, AppShell clearance, touch-target foundation, shell/dialog scroll safety, and notification hit areas — with zero backend/DB/API/PWA changes, desktop behavior preserved, all static gates passing, and governance reconciled (including the Phase 12 label fix). Page-level work (Track/Dashboard/Calendar ⇒ 12B, data-heavy pages ⇒ 12C, dialogs/notifications ⇒ 12D, polish/verification ⇒ 12E, freeze ⇒ 12F) remains future slices. Browser/manual testing is the user's responsibility per §8.

**HARD STOP.** Phase 12: 12.0 ✅ + 12A ✅ COMPLETE. Next slice: 12B. No commit made — working tree carries only the 12A changes; `docs/phase_12/` is untracked pending the user's review.