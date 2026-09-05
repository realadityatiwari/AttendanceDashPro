# AttendanceDashPro — UI/UX Remediation Blueprint

**Date:** 2026-09-05
**Status:** PLANNING ONLY — nothing in this blueprint has been implemented.
**Source of truth:** `docs/UI_UX_AUDIT_STUDENT_APP_2026-09-05.md` (40 findings, UI-001…UI-040, plus six systemic root patterns S1–S6).
**Method:** The audit's static inspection was re-validated against the repository during planning, including backend contract boundaries (`backend/app/api/v1/endpoints/*`, `backend/app/engines/attendance_engine.py`), to determine dependencies, frontend-only feasibility, and risk. No application code, CSS, routes, copy, backend, or configuration was modified.

---

## 1. Executive Summary

**Scope of remediation:** all 40 audited findings across the student-facing Next.js app, grouped into 11 remediation units executed as 12 dependency-ordered phases (Phase 0 is a decision gate, not code).

**Systemic root causes being attacked** (from the audit):
- S1 dead `surface`/`surface2`/`text2` tokens (invisible loading states, lost surface hierarchy) → Phase 1.
- S2 `--accent` (#262626) consumed as a visible color (invisible calendar indicators/links) → Phase 1.
- S3 shared primitives bypassed by hand-rolled variants (errors, empties, headers, selects, inputs, helpers) → Phases 2 and 6.
- S4 no layout contract between AppShell and pages (double padding, inconsistent widths/rhythm) → Phase 5.
- S5 vocabulary not centralized (status labels, attendance verbs, dates, percentages) → Phase 7.
- S6 feedback model improvised per feature (retry, confirmations, success, alerts) → Phases 2 and 3.

**Recommended remediation strategy:** foundation-first. Tokens → feedback primitives → destructive-action safety → navigation IA (after decisions) → layout contract → primitive consolidation → vocabulary → feature-level UX (notifications, settings) → accessibility → polish → verification. Each phase is independently reviewable with a hard stop.

**Highest-risk areas:**
1. Phase 1 token migration touches ~14 files but is mechanically safe (class-for-class swaps) — regression risk is visual, not behavioral.
2. Phase 4 navigation/IA changes touch `TopNav`, `MobileBottomNav`, `AppShell` and every nav consumer — behavior-preserving only if route set is unchanged (decision-gated).
3. Phase 5 layout contract touches every page's root container — visual regression risk across all surfaces; must be one mechanical pass with a diff review.
4. Phase 7 vocabulary centralization changes visible text on many cards — low code risk, highest review burden (every label swap must be checked against the canonical standard).

**Product decisions required before implementation:** 13 decisions (D-01…D-13, Section 4). Four are blocking for Phase 4 (navigation IA), two for Phase 7 (terminology), one each for Phases 8, 9, 3, and 11. None require backend changes except where explicitly noted (D-06 `auto_mark_present`, D-12 optional bulk endpoint).

**Backend sensitivity:** the plan is deliberately frontend-only. Every finding is remediable without API contract, schema, migration, auth, or notification-generation changes. Two findings touch *adjacent* frozen systems and carry explicit guardrails: the service-worker **update banner** (Phase 2 — UI layer only; caching strategy untouched) and session-expiry messaging (Phase 2 — adds a notice to the existing redirect; token lifecycle untouched).

---

## 2. Finding → Remediation Matrix

Every finding UI-001…UI-040, its remediation unit, phase, dependency, and decision gate.

| Finding | Remediation Unit | Phase | Dependency | Decision Required |
|---|---|---|---|---|
| UI-001 dead tokens (`surface`/`surface2`/`text2`) | RU-1 Token foundation | 1.1 | None | No (add tokens, mechanical) |
| UI-002 accent used as visible color | RU-1 Token foundation | 1.2 | None | No (repoint to `primary`) |
| UI-003 desktop nav overflow at md | RU-4 Navigation & IA | 4 | Phase 0 | **D-03** |
| UI-004 Track vs Laboratory IA; dead-end "View Strategy" | RU-4 Navigation & IA | 4 | Phase 0 | **D-01, D-02** |
| UI-005 error states without Retry | RU-2 Feedback architecture | 2.1 | None | No |
| UI-006 unconfirmed bulk "Mark all present" | RU-3 Destructive safety | 3 | None | **D-11** |
| UI-007 missing 404/error UI | RU-1 Token foundation | 1.3 | 1.1 (tokens exist) | No |
| UI-008 mobile wayfinding (active state, page title) | RU-4 Navigation & IA | 4 | Phase 0 | **D-04** |
| UI-009 `window.alert` + inconsistent confirmations | RU-3 Destructive safety | 3 | None | No |
| UI-010 dev/internal copy leaks | RU-7 Vocabulary & content | 7.3 | None | No |
| UI-011 nested layout containers | RU-5 Layout contract | 5 | None | No (shell owns container) |
| UI-012 status label/color inconsistency | RU-7 Vocabulary & formatting | 7.1 | Phase 0 | **D-07, D-08** |
| UI-013 hard-coded weekly thresholds | RU-7 Vocabulary & formatting | 7.1 | None (values verified vs backend) | No (centralize constants) |
| UI-014 notification center pending lock / no bulk / no undo | RU-8 Notification UX | 8 | Phase 2 (toast for undo) | **D-12**, undo part of **D-11** |
| UI-015 unconfirmed lab deletes | RU-3 Destructive safety | 3 | None | **D-11** |
| UI-016 four control-height systems | RU-6 Primitive consolidation | 6.1 | Phase 1 | No |
| UI-017 date format inconsistency | RU-7 Vocabulary & formatting | 7.2 | None | **D-09** |
| UI-018 percentage precision inconsistency | RU-7 Vocabulary & formatting | 7.2 | None | **D-10** |
| UI-019 inert settings (week start, auto-mark) | RU-9 Settings honesty | 9 | Phase 0 | **D-05, D-06** |
| UI-020 quiz tabs ARIA misuse | RU-10 Accessibility | 10 | None | No |
| UI-021 duplicated component implementations | RU-6 Primitive consolidation | 6.2 (errors/empties partial in 2.1) | Phases 1–2 | No (retain-with-reason list in §5) |
| UI-022 dashboard ignores analytics failure | RU-2 Feedback architecture | 2.2 | None | No |
| UI-023 SW update only in console | RU-2 Feedback architecture | 2.4 | None | No |
| UI-024 touch targets below 44px guidance | RU-10 Accessibility (+6.1 primitives) | 10 (primitive parts in 6.1) | Phase 1 | No |
| UI-025 no success-feedback layer | RU-2 Feedback architecture | 2.3 | None | No |
| UI-026 silent session-expiry redirect | RU-2 Feedback architecture | 2.4 | None | No |
| UI-027 no first-use guidance; empty-state CTA gaps | RU-11 Screen-specific | 11 | Phase 2 | No |
| UI-028 signup hard-coded electives; auth off design system | RU-11 Screen-specific | 11 | Phase 6 (primitives) | No (electives dynamic = backend, out of scope) |
| UI-029 login identity/copy mismatch | RU-7 Vocabulary & content | 7.3 | None | No |
| UI-030 Track duplicate summaries | RU-11 Screen-specific | 11 | None | No |
| UI-031 greeting empty-name fallback | RU-11 Screen-specific | 11 | None | No |
| UI-032 `text-[10px]` micro-type | RU-6 Primitive consolidation | 6.3 | Phase 1 | No |
| UI-033 lab tabs `aria-current` misuse | RU-10 Accessibility | 10 | None | No |
| UI-034 `90vh` vs `90dvh` modal caps | RU-11 Screen-specific | 11 | None | No |
| UI-035 student event form jargon | RU-11 Screen-specific | 11 | Phase 0 | **D-13** |
| UI-036 quiz intro wall of text | RU-7 Vocabulary & content | 7.3 | None | No |
| UI-037 manifest splash color mismatch | RU-11 Screen-specific | 11 | None | No |
| UI-038 "Np" pending abbreviation | RU-7 Vocabulary & content | 7.3 | None | No |
| UI-039 notification empty-state icon | RU-8 Notification UX | 8 | None | No |
| UI-040 dashboard grid ragged bottoms | RU-11 Screen-specific | 11 | None | No |

**Coverage check:** 40/40 findings mapped. Partial-resolve relationships: Phase 1.1 resolves the loading-state symptoms of UI-001 across all surfaces; Phase 2.1 resolves the *Retry* half of UI-005 and migrates the worst inline error variants (UI-021 subset); Phase 3 resolves UI-009's alert half, with the confirmation-pattern unification completing in Phase 6.2. No finding is silently dropped.

---

## 3. Proposed Phase Structure

### Phase 0 — Product Decision Gate (no code)

**Objective:** obtain explicit user approval for D-01…D-13 before any code changes.
**Why first:** Phases 3, 4, 7, 8, 9, and 11 contain behavior choices that must not be made silently (audit rule: "do not over-design"; blueprint rule: "do not make irreversible product decisions silently").
**Output:** a decision record (answers to Section 4). No files modified.
**STOP CONDITION:** decisions recorded; no implementation started.

---

### Phase 1 — Visual Foundation (RU-1)

**Objective:** make the design-token layer real and add the missing global error surfaces.
**Why here:** every later phase renders through these tokens; migrating components before tokens exist would double-touch files.

Findings addressed: UI-001, UI-002, UI-007.
Root causes addressed: S1, S2.

**Sub-phases:**

**1.1 Repair token vocabulary** — Add the missing tokens to `globals.css` `:root` so existing class names become real, with values chosen to preserve *intended* hierarchy: `--surface` (between background #0a0a0a and card #171717 — recommended `#111113`), `--surface2` (`#1c1c1f`), and a secondary text token for `text-text2` (recommended `--text2: #a3adc2`, mapping to the muted-foreground family), registered in `@theme inline` as `--color-surface`, `--color-surface2`, `--color-text2`. No component classNames change in this sub-phase. *Boundary: CSS only.*
**1.2 Correct accent semantics** — Repoint the eight accent-as-visible-color usages to `primary` (or a new `--highlight` alias of primary): calendar event dot + count, selection ring + legend swatch, DayDetail substitution line and left border, EventRow "Calendar" link, DayDetail/Profile section icons, quiz intro icon. Intentionally **not** touching `hover:bg-accent` hover-surface usages (UserMenu trigger, dropdowns) — those are correct accent usage.
**1.3 Global 404/error/loading UI** — Add `app/not-found.tsx` (dark, on-brand, link to dashboard), `app/error.tsx` (client boundary, "Something went wrong" + Retry via `reset()`), and optionally `app/(authenticated)/loading.tsx` skeleton. Uses tokens from 1.1.
**1.4 Visual-state verification** — Static sweep: grep for remaining dead tokens, confirm compiled CSS now contains the utilities; eyeball-level screenshot diff is deferred to the user's manual pass.

Files/components likely affected: `app/globals.css`, `app/not-found.tsx` (new), `app/error.tsx` (new), `components/calendar/CalendarGrid.tsx`, `components/calendar/DayDetail.tsx`, `components/events/EventRow.tsx`, `app/(authenticated)/profile/page.tsx`, `app/(authenticated)/tools/quiz-schedule/page.tsx`.
Expected behavior after: skeletons and nested surfaces visibly render; calendar event/selection indicators visible; unknown URLs and render errors show on-brand pages.
Acceptance criteria: zero `bg-surface*`/`text-text2` classes absent from compiled CSS; zero `accent` used as text/dot/ring color on dark backgrounds; `/nonexistent` renders the branded 404.
Regression risks: token values change subtle backgrounds (verify contrast); accent→primary changes link hue (intended).
Dependencies: none. Out of scope: any component restructuring, light theme.
Manual testing required: skeleton visibility on Laboratory/Quiz/Subjects; calendar legend/dot/selection visibility; 404 + error pages.
Static verification allowed: `npx tsc --noEmit`, `npm run build`, grep sweeps, compiled-CSS grep.
**STOP CONDITION:** sub-phases 1.1–1.4 complete and verified; nothing else.

---

### Phase 2 — Feedback Architecture (RU-2)

**Objective:** one coherent failure/success/partial-data model with shared primitives.
Findings addressed: UI-005, UI-022, UI-023, UI-025, UI-026. Root causes: S3, S6.

**Sub-phases:**

**2.1 ErrorState upgrade + adoption** — Extend `components/shared/ErrorState.tsx` with optional `onRetry`/`retryLabel` (renders a Retry button) while remaining backward-compatible. Migrate the four no-recovery surfaces: Dashboard (`dashboard/page.tsx`), History, Track error branch, Subjects grid (replace its inline red box with `ErrorState`). Leave surface-specific variants (Calendar/Events/NotificationCenter/Quiz card) intact in this sub-phase — their Phase 6.2 migration unifies styling, not behavior.
**2.2 Partial-data honesty (dashboard)** — When `useAnalyticsOverview()` errors, render a small inline "Analytics temporarily unavailable — forecast and weekly trend hidden" note inside the affected cards (or an app-level dismissible banner). No new requests; uses the existing `isError` already returned by the hook.
**2.3 Toast foundation** — Add a minimal toast provider (no new dependency; small context + portal component consistent with existing dialog patterns). Adopt at: settings save ("Preferences saved" / errors keep the inline banner), attendance mutations (Track card: "Marked present/absent"), event save/deactivate success, lab record mutations. Toast is *supplementary* — inline state remains the primary indicator.
**2.4 Session expiry + SW update notice** — (a) In `lib/api.ts`, before the hard 401 redirect, stash a flag (e.g., `sessionStorage['session_expired']=1`); login page (and shell mount) reads it and shows "Your session expired. Please sign in again." Token/refresh lifecycle untouched. (b) In `useServiceWorker.ts`, surface the existing "new content available" state via a small dismissible banner ("Update available — reload to get the latest version") instead of `console.log`. Registration/caching logic unchanged.

Files: `components/shared/ErrorState.tsx`, `app/(authenticated)/dashboard/page.tsx`, `app/(authenticated)/history/page.tsx`, `app/(authenticated)/tools/laboratory/page.tsx`, `components/dashboard/SubjectAttendanceGrid.tsx`, new `components/feedback/Toast*`, `lib/api.ts` (additive), `app/(auth)/login/page.tsx` (read flag), `components/pwa/useServiceWorker.ts` + new banner component.
Acceptance criteria: every data surface's error offers Retry or explicit guidance; analytics failure visible; mutations produce consistent feedback; expired session explains itself; SW update visible.
Regression risks: toast provider mounting (must not break SSR/hydration); `lib/api.ts` edit is in the frozen auth-adjacent file — additive `sessionStorage` write only, no change to refresh/redirect flow.
Dependencies: none strictly; toast adoption in Phase 3 (undo) comes after this.
Out of scope: optimistic mutations, global retry-queue.
**STOP CONDITION:** sub-phases 2.1–2.4 complete.

---

### Phase 3 — Destructive-Action Safety (RU-3)

**Objective:** one confirmation policy, one confirmation primitive.
Findings addressed: UI-006, UI-015, UI-009. Root cause: S6. Decision gate: **D-11**.

Scope: Add a small `ConfirmDialog` (built on the existing `Dialog` primitive) with `title/description/confirmLabel/variant`. Apply per D-11 outcomes: (a) "Mark all present" → ConfirmDialog summarizing "N pending classes will be marked present" + clearer partial-failure message; (b) lab delete-record and deactivate-experiment icon buttons → ConfirmDialog (retain icon trigger); (c) events deactivation error path → replace `window.alert` with an inline destructive banner (same component family as NotificationCenter's action error); (d) keep EventRow's inline Confirm/Cancel swap (audited as acceptable) or migrate to ConfirmDialog for consistency — per D-11.
Files: `app/(authenticated)/tools/laboratory/page.tsx`, `app/(authenticated)/laboratory/page.tsx`, `app/(authenticated)/tools/events/page.tsx`, `components/events/EventRow.tsx`, new `components/feedback/ConfirmDialog.tsx`.
Acceptance criteria: no irreversible mutation fires from a single unconfirmed tap; no `window.alert` anywhere in `frontend/src` (grep-verifiable).
Dependencies: Phase 0 (D-11). Independent of Phase 2 except undo decisions.
**STOP CONDITION:** scope above complete.

---

### Phase 4 — Navigation & Information Architecture (RU-4)

**Objective:** resolve the Track/Laboratory confusion, desktop density, and mobile wayfinding — after decisions.
Findings addressed: UI-003, UI-004, UI-008. Decision gates: **D-01, D-02, D-03, D-04**. Route set is unchanged in every option (deep-link safety).

Scope per decision outcomes (see §6 for the full IA proposal): relabel/retarget nav entries; retarget or relabel "View Strategy"; implement the chosen md-band strategy (options in D-03); implement mobile active-state inheritance for secondary destinations (More tab shows active state while a secondary route is open) + a mobile page title in the header (from a small route→title map); both `TopNav` and `MobileBottomNav` share one `NAV_ITEMS` source module so labels can never drift again.
Files: `components/layout/TopNav.tsx`, `components/layout/MobileBottomNav.tsx`, `components/layout/AppShell.tsx` (title slot), new `components/layout/navItems.ts`, `components/dashboard/home/AttentionRequiredCard.tsx`.
Acceptance criteria: one nav source of truth; secondary destinations visibly indicated on mobile; no horizontal overflow at 768/1024 (manual check); "View Strategy" lands on a page containing strategy content.
Regression risks: header layout on md band (manual verify); mobile grid spacing when the More tab carries an active indicator.
Dependencies: Phase 0 (D-01…D-04); benefits from Phase 1 tokens but not blocked.
**STOP CONDITION:** chosen IA implemented; route set unchanged.

---

### Phase 5 — Layout Contract (RU-5)

**Objective:** the shell owns width and padding; pages own content only.
Findings addressed: UI-011. Root cause: S4.

Scope: `AppShell` keeps `max-w-5xl p-4 pb-28 md:p-6 lg:p-8` as the single container. Remove every page-level `max-w-*`/`px-*`/`py-*` root wrapper (11 surfaces) and replace with `flex flex-col gap-6` (gap values standardized once). If any surface genuinely needs a narrower reading column (Track at `max-w-2xl`), express it as an inner `max-w-*` on the content, never as padding. `PageHeader`'s `mb-8` is removed in favor of the container's gap (one spacing authority).
Files: `AppShell.tsx` + root wrappers of: dashboard, subjects, both laboratory pages, quiz-schedule, events, calendar, history, profile, feedback, plus `components/shared/PageHeader.tsx`.
Acceptance criteria: no page file contains `px-4 py-6|8 sm:px-6 lg:px-8 max-w-` root classes (grep-verifiable); consistent gutters measured at 375/768/1440.
Regression risks: highest visual-diff phase; every page's spacing shifts slightly. Mitigation: single mechanical pass, one commit-sized review.
Dependencies: none; ideally after Phase 4 so nav/header changes land first.
**STOP CONDITION:** all page roots migrated; grep clean.

---

### Phase 6 — Design-System Primitive Consolidation (RU-6)

**Objective:** one primitive per concept; duplicates either migrated or documented as intentional.
Findings addressed: UI-016, UI-021, UI-032. Root cause: S3.

**Sub-phases:**
**6.1 Control heights** — Standardize on the `Input` primitive's `h-8` desktop default + `h-10` mobile override (`h-10 sm:h-8`) as the canonical height for text inputs and selects; create a small `Select` wrapper so the 6 hand-styled `<select>`s share one implementation. Update: Settings (`h-9 sm:h-7`), History/Events filter classes, EventFormDialog, Laboratory, and migrate login/signup raw inputs to the primitive (part of UI-028). Touch-target floor for shared primitives raised here (UI-024 primitive half: `icon-sm` stays desktop-only, mobile min 40px — the button foundation already does this).
**6.2 Error/empty/header consolidation** — Migrate the remaining inline error variants (Calendar, Events, Lab tabs, QuizEligibilityCard, NotificationCenter, SubjectLaboratoryView) onto `ErrorState` (with their existing Retry); migrate inline empty states onto `EmptyState` where the variant adds nothing (dashboard cards keep their compact in-card empties — documented as intentional contextual variation, per the audit's rule against flagging intentional differences). Deduplicate helpers: single `humanizeEventType`/`classTypeLabel` module (events/calendar), single date-chip component (EventRow, UpcomingEventsCard, HistoryRow, DayDetail). Decide QuizSnapshotCard's `QUIZ_LABELS` vs the quiz page's cycle labels → one label source.
**6.3 Typography floor** — Replace `text-[10px]` micro-labels with a two-step caption scale (`text-[11px]`/`text-xs`) via a documented token note; do not redesign the type scale.

Files: `components/ui/input.tsx` (wrapper only), new `components/ui/select.tsx`, `components/shared/ErrorState.tsx`/`EmptyState.tsx` consumers, `components/events/EventRow.tsx`, `components/calendar/DayDetail.tsx`, dashboard cards, `app/(auth)/*`, laboratory/quiz pages.
Acceptance criteria: one `Select` implementation; no duplicated `humanizeEventType`; inline error boxes reduced to `ErrorState` (+ documented exceptions list).
Regression risks: moderate — visual only; dialog-embedded forms reflow slightly.
Dependencies: Phase 1 (tokens), Phase 2.1 (ErrorState API).
**STOP CONDITION:** sub-phases 6.1–6.3 complete with the §5 retain/migrate table satisfied.

---

### Phase 7 — Vocabulary, Formatting & Content (RU-7)

**Objective:** one language for the same fact.
Findings addressed: UI-012, UI-013, UI-017, UI-018, UI-010, UI-029, UI-036, UI-038. Decision gates: **D-07, D-08, D-09, D-10**.

**Sub-phases:**
**7.1 Status vocabulary module** — Create `lib/statusLabels.ts`: canonical label + badge variant per backend enum (`SAFE/WATCH/CRITICAL`, `HEALTHY/WATCH/AT_RISK/CRITICAL`, class status, class type), consumed by OverallAttendanceCard, AttentionRequiredCard, SubjectAttendanceCard, NotificationCenter badge meta, History. Centralize band thresholds for WeeklyAttendanceCard: **verified against backend** — the current hard-coded 80/60 coincidentally matches the engine's legacy bands (`SAFE_BAND_PCT = target+5 = 80`, `WATCH_BAND_PCT = target−15 = 60`, `backend/app/engines/attendance_engine.py:11-13`); replace the magic numbers with named constants imported from one frontend module documenting their backend source (no backend change; a backend-emitted per-week status would be additive and is explicitly out of scope).
**7.2 Formatting module** — Extend `lib/date.ts` as the only date formatter set (per D-09) and add `lib/format.ts` percentage formatters (per D-10); migrate all `toLocaleDateString(undefined)` / inline `Intl` / `toFixed(1)` call sites.
**7.3 Content cleanup** — Remove dev copy: "Student Identity (PostgreSQL)", InstallAppModal stale duplicated paragraphs + "Tracked in task.md", VAPID "configured in a later phase", FeedbackModal "fake confirmation" rationale, ProfileModal data-lineage footnote, "Ingest" → "Add experiment". Fix login identity ("AttendanceDash Pro" heading, "Sign in" button), quiz intro rewritten to a scannable 2–3 bullet structure, "Np" → "· 3 pending".
Files: `lib/date.ts`, new `lib/statusLabels.ts`/`lib/format.ts`, ~12 consumer components, `app/(auth)/login/page.tsx`, `components/shell/*`, quiz page.
Acceptance criteria: no raw enum badge without a label map (grep `overall.status ??`); one date formatter per canonical format; no dev-internal phrases (grep list in §10).
Regression risks: text length changes may reflow rows (verify truncated lines).
Dependencies: Phase 0 (D-07…D-10); Phase 6.2 (consumers consolidated first avoids double migration).
**STOP CONDITION:** sub-phases 7.1–7.3 complete.

---

### Phase 8 — Notification UX (RU-8)

**Objective:** presentation-layer fixes only. **Notification generation architecture (backend `notification_service.py`, dispatch, Web Push, SW signal) is explicitly out of scope and untouched.**
Findings addressed: UI-014, UI-039. Decision gates: **D-11 (undo), D-12 (bulk)**.

Scope: per-row pending state (`pendingId` → per-item set) instead of the global lock; "Mark all read" per D-12 (recommended: sequential PATCH loop reusing the existing idempotent per-notification endpoint — no backend change; loading state on the button; honest partial-failure message); optional dismiss-undo per D-11 (recommended: defer — dismissal is low-stakes and the row can be recovered by reopening since the backend only sets a flag; note: `is_dismissed` rows are filtered server-side, so a true undo requires re-PATCH with `is_dismissed: false` which the existing endpoint already supports — implement only if D-11 approves); empty-state icon → bell.
Files: `components/notifications/NotificationCenter.tsx` only.
Acceptance criteria: only the acted row is disabled during its request; bulk action exists per decision; no change to badge update path (same SWR key).
Dependencies: Phase 2.3 (toast) for feedback; Phase 0.
**STOP CONDITION:** center behaves per decisions; generation architecture untouched (verifiable: zero diffs outside `NotificationCenter.tsx`).

---

### Phase 9 — Settings Honesty (RU-9)

**Objective:** every visible control either works or is visibly not-yet.
Findings addressed: UI-019. Decision gates: **D-05, D-06**.

Analysis (verified): `week_starts_on` — stored (GET/PUT `/api/v1/student/preferences`), **never consumed**; implementing it is **frontend-only** (CalendarGrid builds its own grid from dates and can rotate the leading-blanks/weekday-header arrays). `auto_mark_present` — stored, never consumed; meaningful implementation is a **backend semantic** (auto-marking attendance is an attendance-engine behavior = frozen system) → recommend relabel/defer, not frontend fakery. `class_reminders` — consumed (gates bell rendering); no change.
Scope per decisions: D-05 approve → CalendarGrid + Calendar page consume the preference (SWR preferences fetch on calendar mount) and the Settings info-box copy is updated; D-06 → chosen outcome (remove control / move under a "Coming soon" group / keep with explicit "no effect yet" label).
Files: `components/calendar/CalendarGrid.tsx`, `app/(authenticated)/calendar/page.tsx`, `components/shell/SettingsModal.tsx`.
Acceptance criteria: no control exists that silently does nothing without disclosure.
Dependencies: Phase 0.
**STOP CONDITION:** per decisions; preferences API contract unchanged (still full-object PUT).

---

### Phase 10 — Accessibility Remediation (RU-10)

**Objective:** fix the concrete ARIA/keyboard/target findings; verify, don't claim compliance.
Findings addressed: UI-020, UI-024 (page-level), UI-033, plus contrast verification. Root cause: S3 (shared-primitive half already in 6.1).

Scope: Quiz cycle selector → correct semantics (either a real `tablist` with `aria-controls` panels + arrow-key handling, or — recommended for simplicity — plain buttons with `aria-pressed`, dropping the false tab semantics); Laboratory tabs → same treatment; touch-target pass on page-level controls (History filter row selects/inputs inherit 6.1's mobile height; Settings switch enlarged to h-6 w-11 with same visual language; NotificationCenter icon button `size="icon-sm"` is 40px mobile — verify only); contrast spot-check of `text-muted-foreground` (#94a3b8) on chip backgrounds and the new caption scale (static calculation + manual); dynamic announcements: add `aria-live="polite"` to the Track mutation error region and toast container.
Files: quiz page, laboratory page, SettingsModal, NotificationCenter, toast provider (from 2.3), Track page.
Acceptance criteria: no `role="tab"` without a panel/keyboard contract; no `aria-current` on buttons; interactive targets ≥24px minimum, ≥40px on mobile controls; live regions on async feedback.
Dependencies: Phases 6.1/2.3 for primitives; otherwise independent.
**STOP CONDITION:** listed fixes done; a11y verification is manual (user) — no compliance claim in code or docs.

---

### Phase 11 — Screen-Specific UX & Polish (RU-11)

**Objective:** the remaining local findings, batched by screen.
Findings addressed: UI-027, UI-028, UI-030, UI-031, UI-034, UI-035 (D-13), UI-037, UI-040.

Scope: QuizSnapshot empty state gets the footer CTA rendered in both states; greeting fallback ("Good Morning" / skeleton keeps comma-safe layout); Track bottom summary removed (per D-11-adjacent simplicity — no decision needed, audit found pure duplication; keep top card); EventFormDialog `90vh`→`90dvh`; student event form simplification per D-13 (recommended: hide "Working day state" and "Substitution schedule" from students entirely — they are admin-engine concerns; students get type/date/subject/note); manifest `background_color` → `#0a0a0a`; dashboard grid: apply `h-full` consistently or switch rows to `items-stretch`; auth pages: adopt `Input`/`Button` primitives (completed in 6.1) + add password toggle to login; empty-dataset first-use: dashboard empty cards already carry guidance — add a single "Getting started" hint line under the greeting when `summary.overall.recorded === 0` (conditional, no new endpoint).
Files: dashboard cards/page, Track page, EventFormDialog, manifest.json, login/signup, profile greeting.
Acceptance criteria: each listed finding's acceptance line met; no cross-screen changes.
Dependencies: 6.1 (auth primitives), Phase 0 (D-13).
**STOP CONDITION:** all Phase 11 findings closed.

---

### Phase 12 — Verification & Close-out (no new features)

**Objective:** execute the manual verification plan (Section 13) and the static sweep (Section 14), reconcile governance docs, produce a remediation completion report. No code changes except defects found.
**STOP CONDITION:** checklist executed; report written; hard stop.

---

## 4. Product Decisions Required

### Decision D-01 — Track vs Laboratory naming/IA
**Question:** How should the two lab-related surfaces be named and related?
**Current behavior:** Nav "Track" → `/tools/laboratory` ("Track Attendance" — daily attendance marking); nav "Laboratory" → `/laboratory` (practical attendance/experiments/activity).
**Option A:** Rename to task-based labels: "Mark Attendance" (Track) and "Laboratory" — minimal change, keeps routes.
**Option B (recommended):** Keep routes, rename to "Today's Classes"→ no; recommended concrete: rename Track → "Mark Attendance", Laboratory → "Lab Experiments", and update page titles/descriptions to match; URLs unchanged.
**Option C:** Merge Laboratory tabs into one surface with Track (larger IA change; not recommended now).
**Recommended:** B.
**Reason:** labels currently mix verbs/nouns and both say "lab" via URL; task-based names predict content without route changes (deep links safe).
**UX consequences:** predictable nav; dashboard CTA wording can align.
**Implementation consequences:** label map + page titles/descriptions only; one nav source module (Phase 4).

### Decision D-02 — "View Strategy" destination
**Question:** Where should the Attention card CTA lead?
**Current behavior:** links to Track (`/tools/laboratory`), which has no strategy content.
**Option A (recommended):** `/tools/quiz-schedule` (must-attend/safe-skip lives there).
**Option B:** keep Track but relabel to "Mark attendance now".
**Recommended:** A, with button label "View plan" aligned to D-07 vocabulary.
**Reason:** the card promises strategy; Quiz Eligibility is the strategy surface.
**UX consequences:** attention→action loop closes.
**Implementation consequences:** one `href` + label.

### Decision D-03 — Desktop nav md-band overflow strategy
**Question:** How should 8–9 labeled items fit 768–1023px?
**Current behavior:** full label set from `md` up, no shrink/truncate.
**Option A (recommended):** show the full set only at `lg`; between `md`–`lg` collapse secondary items into a header "More" dropdown (reuses the mobile More list; no route change).
**Option B:** icon+label at `lg`, icon-only with tooltips at `md`.
**Option C:** shorten labels ("Quiz", "Labs") at all sizes.
**Recommended:** A (icon-only hides meaning; shortened labels lose clarity).
**UX consequences:** one nav model per band; no clipping.
**Implementation consequences:** responsive grouping in TopNav only; MobileBottomNav untouched.

### Decision D-04 — Mobile wayfinding model
**Question:** How should secondary destinations indicate location on mobile?
**Current behavior:** only 3 primary tabs show active state; header shows no title.
**Option A (recommended):** More tab inherits active state while any secondary route is open (aria-current + tint) AND the header shows the current page title (from a route map, hidden on dashboard where greeting serves).
**Option B:** expand to 5 tabs (adds Calendar + Quiz) — crowded at 320px, touches More concept.
**Recommended:** A.
**UX consequences:** location always visible; no grid crowding.
**Implementation consequences:** small nav module + title slot in AppShell.

### Decision D-05 — `week_starts_on`
**Question:** implement, remove, or keep disclosed-only?
**Current behavior:** stored; calendar hard-codes Sunday-first; disclosed in Settings fine print.
**Option A (recommended):** implement — CalendarGrid rotates header/leading-blanks from the preference (frontend-only, verified).
**Option B:** remove the control until implemented.
**Option C:** keep as-is.
**Recommended:** A (small, honest, high-trust win).
**UX consequences:** calendar matches stated preference.
**Implementation consequences:** CalendarGrid + calendar page fetch; no backend change.

### Decision D-06 — `auto_mark_present`
**Question:** implement, remove, or defer?
**Current behavior:** stored; consumed by nothing.
**Option A (recommended):** defer with honest label — move under "Coming soon" group (pattern already exists in AppearanceModal) or add explicit "no effect yet" note; keep storage.
**Option B:** remove control and preference usage.
**Option C:** implement — **requires backend attendance-engine behavior (frozen system); explicitly not recommended in this remediation.**
**Recommended:** A.
**Reason:** auto-marking attendance is an engine semantics change; frontend fakery would violate the app's own "never fake" rule.
**UX consequences:** no silent dead control.
**Implementation consequences:** Settings copy only.

### Decision D-07 — Attendance verbs
**Question:** Present/Absent or Attended/Missed as canonical user-facing terms?
**Current behavior:** both, mixed.
**Option A (recommended):** **Present / Absent** for record states and actions (History, Track, Today card); "attended N of M" remains valid as a verb phrase in footers.
**Option B:** Attended/Missed everywhere.
**Recommended:** A (matches History/Track majority and student intuition).
**UX consequences:** single pair everywhere.
**Implementation consequences:** statusLabels module; ~4 components reword.

### Decision D-08 — Status vocabulary
**Question:** raw enums or mapped labels for SAFE/WATCH/CRITICAL and the Health set?
**Current behavior:** mixed (dashboard raw; subject cards mapped).
**Option A (recommended):** mapped labels everywhere — dashboard overall/attention cards adopt `Healthy/Watch/At Risk/Critical`-style mapping (legacy SAFE→"On track" or "Healthy" per the backend's own Phase 8.2 note that Health supersedes legacy presentation); CRITICAL solid-red treatment retained.
**Option B:** raw enums everywhere (dev-facing).
**Recommended:** A.
**Implementation consequences:** `lib/statusLabels.ts`; dashboard card badge lines.

### Decision D-09 — Canonical date formats
**Question:** one formatter set?
**Current behavior:** device-locale and hard-coded formats mixed.
**Option A (recommended):** locale-independent English: long `Saturday · 5 Sep 2026` (existing `formatLongDate`), medium `5 Sep 2026`, short `5 SEP` (chips); times `9:30 AM`.
**Option B:** fully `Intl`-based device-locale formatting everywhere.
**Recommended:** A (deterministic across the PWA; matches current dominant style).
**Implementation consequences:** `lib/date.ts` extension; migrate ~8 call sites.

### Decision D-10 — Percentage precision
**Question:** whole numbers or 1-decimal?
**Current behavior:** mixed (`Math.round` vs `toFixed(1)`).
**Option A (recommended):** whole numbers for display; 1-decimal only in the Quiz "View Calculation" detail (where precision is the point).
**Option B:** 1-decimal everywhere.
**Recommended:** A.
**Implementation consequences:** `lib/format.ts`; 3 modules.

### Decision D-11 — Destructive-action policy
**Question:** what confirms, what undoes?
**Current behavior:** inconsistent (bulk mark-all unconfirmed; lab deletes unconfirmed; event deactivate inline-confirms; errors via `window.alert`).
**Option A (recommended):** confirm for: bulk "Mark all present", lab delete-record, deactivate-experiment; keep inline confirm for event deactivate; notification dismiss immediate (recoverable semantics exist; optional undo via re-PATCH only if desired); replace `window.alert` with inline banner.
**Option B:** confirm everything destructive (more friction).
**Recommended:** A.
**Implementation consequences:** ConfirmDialog primitive; 3 surfaces adopt; events error path reworked.

### Decision D-12 — Notification bulk read
**Question:** how to offer "mark all read"?
**Current behavior:** none; per-item PATCH only.
**Option A (recommended):** frontend sequential PATCH loop over unread ids (endpoint is idempotent per backend comments); button shows progress; partial failures surfaced honestly. No backend change.
**Option B:** new backend bulk endpoint (touches notification API contract — frozen; not recommended).
**Option C:** omit bulk entirely.
**Recommended:** A.
**Implementation consequences:** NotificationCenter only.

### Decision D-13 — Student event-form scope
**Question:** simplify the student-facing event form?
**Current behavior:** students see engine fields (working-day state, substitution schedule, duration radios).
**Option A (recommended):** student mode shows only: type, date(s), subject, class type (where required), reason/note; working-day and substitution fields admin-only (backend validation unchanged; fields default as today).
**Option B:** keep all fields with better explanations.
**Recommended:** A.
**Implementation consequences:** conditional rendering in EventFormDialog; payload unchanged.

---

## 5. Design-System Consolidation Plan

Principle: **consistency, not a new theme.** The existing dark identity (near-black bg, charcoal cards, blue primary, restrained radius) is retained; nothing below changes hue or brand.

| Concept | Canonical primitive (keep) | Duplicated implementations | Action | Expected effect |
|---|---|---|---|---|
| Color tokens | `globals.css` `:root` set | missing `surface/surface2/text2` used in 25+ places | **Define tokens (1.1)** | intended elevation hierarchy appears |
| Accent/visible color | `primary` (#3B82F6) | `accent` used as visible color in 8 places | **Migrate to primary (1.2)** | calendar/links visible |
| Accent as hover surface | `bg-accent` in menus | — | **Retain** | correct today |
| Error states | `shared/ErrorState.tsx` + `destructive` token | 6 inline variants using raw `red-*` | **Migrate (2.1, 6.2)** | one failure look |
| Empty states | `shared/EmptyState.tsx` | 5 inline variants | **Migrate large ones (6.2); retain compact in-card empties as documented contextual variation** | consistent, less code |
| Loading states | `Skeleton` (`bg-muted` pulse) | raw `animate-pulse bg-surface` divs | **Migrate to Skeleton (1.1 fixes visibility)** | skeletons actually visible |
| Page headers | `shared/PageHeader.tsx` | `GreetingHeader`, Track/Quiz inline headers | **Retain GreetingHeader (dashboard identity); migrate Track/Quiz inline headers to PageHeader (Phase 4/5)** | one header pattern + greeting |
| Buttons | `ui/button.tsx` (cva) | raw `<button>` on login/signup; custom styled buttons (feedback-type chips, quiz tabs) | **Migrate auth pages (6.1); retain chip-style selection buttons as intentional pattern** | one button language |
| Inputs | `ui/input.tsx` | 4 height systems; raw auth inputs | **Migrate (6.1)** | uniform heights, mobile 40px |
| Selects | new `ui/select.tsx` wrapper | 6 hand-styled `<select>`s | **Create + migrate (6.1)** | uniform selects, `color-scheme` handled once |
| Cards | `ui/card.tsx` + `GlassCard` | both in use | **Retain both: Card for structured cards, GlassCard for flat panels — documented; no merge** | no churn |
| Badges | `ui/badge.tsx` (has success/warning/danger/neutral/primary) | ad-hoc `bg-x/15 text-x border-x/30` triplets | **Migrate ad-hoc triplets to variants (7.1)** | one badge language |
| Dialogs/Sheets | `ui/dialog.tsx`, `ui/sheet.tsx`, `ShellDialog` | EventFormDialog uses raw Dialog (fine), `window.alert` | **Retain; kill alert (3)** | consistent modals |
| Icon buttons | `Button size="icon-*"` | bare icon links with custom classes | **Verify only (Phase 10)** | touch targets |
| Focus states | `focus-visible:ring-*` conventions | consistent today | **Retain** | — |
| Touch targets | button foundation's mobile `h-10` | History filters `h-8`, switch `h-5` | **Lift via 6.1 + 10** | fewer mis-taps |
| Typography | token-based sizes | `text-[10px]` (~20 sites) | **Two-step caption scale (6.3)** | legibility |
| Spacing | shell container (Phase 5) + card `--card-spacing` | page-level padding variance | **Phase 5 contract** | uniform rhythm |

---

## 6. Navigation / IA Proposal

**Canonical inventory (routes unchanged in all options):**

| Destination | Route | Canonical label (proposed, per D-01) | Tier |
|---|---|---|---|
| Dashboard | `/dashboard` | Home | Primary |
| Daily marking | `/tools/laboratory` | Mark Attendance (was "Track") | Primary (mobile) / Secondary (desktop per D-03) |
| Lab experiments | `/laboratory` | Lab Experiments (was "Laboratory") | Secondary |
| Quiz eligibility | `/tools/quiz-schedule` | Quiz Eligibility | Secondary |
| Subject attendance | `/subjects` | Attendance (page title → "Attendance Overview" to match nav; per D-01 alignment) | Primary (mobile) |
| History | `/history` | History | Primary (mobile) |
| Calendar | `/calendar` | Calendar | Secondary |
| Events | `/tools/events` | Events | Secondary |
| Feedback (admin) | `/tools/feedback` | Feedback | Secondary, role-gated |
| Profile / Appearance / Settings / Install | modals | via avatar menu (unchanged) | Utility |

**Primary vs secondary:** keep the audited 3-tab mobile structure (Home/Attendance/History + More) — it is a deliberate Phase-12A design, not accidental; fix its *wayfinding* (D-04) rather than its structure. Desktop keeps the flat bar at `lg+`, collapses secondaries into a More dropdown at `md` (D-03 Option A).

**Active-state behavior:** exact-path match stays; More tab/entry inherits active when any secondary route is open; `aria-current="page"` only on the matching link.

**Mobile page title:** AppShell gains a centered title slot (route→title map) shown on `md:hidden` when the route has a title; dashboard suppresses it (greeting).

**Deep links:** no route changes anywhere in this plan; More-sheet links close the sheet before navigation (already correct); the EventRow "Calendar" link currently always opens the current month — proposed enhancement (additional finding A-3): link to `/calendar?date=<event.start>` and have the calendar page read a `date` param to set month/selection. Frontend-only; listed as optional polish in Phase 11.

---

## 7. Feedback / Error Architecture Proposal

| Situation | Mechanism | Notes |
|---|---|---|
| Initial page load | Skeleton matching final layout | fixed visibility via Phase 1 tokens |
| Component/slot load | Skeleton or inline spinner row | consistent via primitives |
| Mutation loading | Button spinner + disabled (existing pattern) | keep |
| Recoverable API error (view) | `ErrorState` with Retry | all surfaces, Phase 2.1/6.2 |
| Recoverable API error (mutation) | inline destructive banner near action | replaces alerts; NotificationCenter pattern is the model |
| Non-recoverable error | `ErrorState` without Retry + guidance | e.g., 403 surfaces |
| Global render error | `app/error.tsx` with reset | Phase 1.3 |
| 404 | `app/not-found.tsx` | Phase 1.3 |
| Session expiry | redirect + one-time explanatory notice on login | Phase 2.4; token flow untouched |
| Partial data failure | card-level note ("temporarily unavailable") | Phase 2.2 |
| Attendance mutation success | card state flip + toast | toast supplementary |
| Settings save | inline "Saved" + toast | existing inline retained |
| Notification read/dismiss | row state + per-row pending | Phase 8 |
| Event/lab mutation success | toast + list revalidate | Phase 2.3 |
| Single deletion / deactivation | ConfirmDialog → toast | Phase 3 |
| Bulk attendance marking | ConfirmDialog with count → progress → honest partial-failure summary | Phase 3 |
| Notification dismiss | immediate (low stakes; optional undo via re-PATCH per D-11) | Phase 8 |
| SW update available | dismissible banner with Reload | Phase 2.4 |

Rules: no optimistic mutations for attendance/notifications (existing "never fake persistence" policy); destructive = confirm when irreversible or bulk; toasts never carry the only error signal.

---

## 8. Responsive / Mobile Strategy

| Band | Header | Nav | Containers | Key behaviors |
|---|---|---|---|---|
| <768 (mobile) | Brand + page title (D-04) + bell + avatar | Bottom 3 tabs + More; More shows active; sheet for secondaries | Shell-only padding (`p-4 pb-28`) | 40px controls (6.1); sheets for NotificationCenter; calendar compact cells; filters stack 1-col; dialog→sheet pattern via `mobileSheet` retained |
| 768–1023 (md) | Brand + **collapsed secondary "More" dropdown** (D-03 A) + bell + avatar | Full primary labels only | Shell-only padding | This band is the audit's overflow risk — the collapse is the fix; verify at 768 exactly |
| 1024–1439 (lg) | Full nav (8–9 items) | Flat labeled bar | Shell `p-6` | Dashboard 2-col grid |
| ≥1440 (xl) | unchanged | unchanged | Shell `max-w-5xl` centered (retained deliberately — reading measure) | calendar 2-col with sticky detail |

Touch targets: mobile controls ≥40px (button foundation already; filters/switch lifted in 6.1/10). Safe areas: existing `pb-[env(safe-area-inset-bottom)]` retained. Viewport height: switch shell audit item `h-screen`→`h-dvh` evaluated in Phase 11 polish (small, low risk; verify iOS). No tablet-specific duplicated UI — bands adapt one layout.

---

## 9. Accessibility Strategy

Grouped fixes; verification is manual (user) — no compliance claims in code/docs.

| Group | Fix | Phase | Level |
|---|---|---|---|
| ARIA | Quiz selector: drop false `tablist` → `aria-pressed` buttons (or full tabs w/ panels+arrows) | 10 | page |
| ARIA | Lab tabs: `aria-current` → `aria-pressed` | 10 | page |
| Touch targets | filter controls h-10 mobile; switch 24px min height; verify icon buttons ≥40px mobile | 6.1, 10 | shared + page |
| Contrast | verify #94a3b8 on chips/muted backgrounds; caption scale floor 11px | 6.3, 10, manual | shared |
| Dynamic announcements | `aria-live="polite"` on toasts + Track mutation errors | 2.3, 10 | shared + page |
| Semantic structure | heading hierarchy audit (PageHeader h1, card titles h3 — verify no skips after Phase 5/6 migrations) | 5/6 review | shared |
| Keyboard | ConfirmDialog traps focus via existing Dialog primitive (free); More-sheet Escape via Sheet (free) | 3 | shared |
| Forms | label associations already present; verify after 6.1 Select wrapper | 6.1 | shared |

---

## 10. Terminology / Content Standard

| Term | Current variants | Canonical (per D-07…D-10 defaults) | Affected surfaces |
|---|---|---|---|
| Attendance record states | Present/Absent vs Attended/Missed | **Present / Absent** (records & actions); "attended" as verb in footers only | Track, History, Today card, subject cards |
| Subject health | SAFE/WATCH/CRITICAL raw vs Healthy/Watch/At Risk/Critical | **Mapped labels** (Health set for subjects; legacy SAFE/WATCH/CRITICAL → mapped via statusLabels) | Overall card, Attention card, subject cards, notifications |
| Filter heading | "State" vs "Status" | **Status** | History, Events |
| Track/Laboratory | "Track", "Laboratory" (+URL collision) | **Mark Attendance / Lab Experiments** (D-01) | nav, page titles, dashboard CTA |
| Dates | 3+ formats, device-locale dependent | Long `Saturday · 5 Sep 2026`; medium `5 Sep 2026`; chip `5 SEP`; time `9:30 AM` | app-wide |
| Percentages | rounded vs 1-decimal | whole numbers; 1-decimal only inside "View Calculation" | dashboard, quiz, subjects |
| Pending | "pending", "Np", "N remaining" | "pending" spelled out (`· 3 pending`) | weekly card, Track, history |
| Lab experiment creation | "Ingest" | "Add experiment" | laboratory (admin) |
| Login | "Student Portal", "Login securely", "V2" | "AttendanceDash Pro", "Sign in" | login |

**Dev/internal copy to eliminate (grep list):** `PostgreSQL`, `Tracked in task.md`, `VAPID`, `fake confirmation`, `resolved from your section`, `Ingest`, `Phase \d` in user-visible strings, `endpoint`, `backend` in student-facing sentences (allowed only in admin event-manager card where it explains enforcement — review in 7.3).

**Additional findings discovered during remediation planning** (reported separately per instructions; not merged into the 40):
- **A-1 — Orphaned component:** `components/dashboard/SubjectLaboratoryView.tsx` is imported by nothing (grep-verified). Propose deletion or explicit retention in Phase 6.2 cleanup. (Housekeeping; no user impact.)
- **A-2 — Dead hooks:** `useCalendarDay` and `useSubjectSummary` in `hooks/useApi.ts` have no consumers (grep-verified). Propose removal in Phase 6.2. (Housekeeping.)
- **A-3 — EventRow "Calendar" link lacks date deep-linking:** it navigates to `/calendar`, which always opens the current month — the event may be months away. Proposed optional fix in Phase 11 (`/calendar?date=…` handling). (UX friction; small.)

---

## 11. File Impact Map

| File | Findings | Phase | Change type | Risk |
|---|---|---|---|---|
| `app/globals.css` | UI-001 | 1.1 | systemic (tokens) | LOW |
| `app/layout.tsx` | — | 1.3 (error boundary mount is automatic) | none expected | LOW |
| `app/not-found.tsx`, `app/error.tsx` (new) | UI-007 | 1.3 | new | LOW |
| `components/calendar/CalendarGrid.tsx` | UI-002, UI-019, UI-037-adjacent | 1.2, 9 | local | MEDIUM |
| `components/calendar/DayDetail.tsx` | UI-002, UI-021 | 1.2, 6.2 | local | LOW |
| `components/events/EventRow.tsx` | UI-002, UI-009, UI-021 | 1.2, 3, 6.2 | local | LOW |
| `app/(authenticated)/profile/page.tsx` | UI-002, UI-010, UI-028 | 1.2, 7.3, 11 | local | LOW |
| `app/(authenticated)/tools/quiz-schedule/page.tsx` | UI-001, UI-002, UI-020, UI-036 | 1.1, 1.2, 10, 7.3 | local | MEDIUM |
| `components/quiz/QuizEligibilityCard.tsx` | UI-001, UI-017/018, UI-021 | 1.1, 7.2, 6.2 | local | LOW |
| `app/(authenticated)/laboratory/page.tsx` | UI-001, UI-015, UI-016, UI-010, UI-033 | 1.1, 3, 6.1, 7.3, 10 | local | MEDIUM |
| `app/(authenticated)/tools/laboratory/page.tsx` | UI-005, UI-006, UI-030, UI-031-adjacent | 2.1, 3, 11 | local | MEDIUM |
| `components/dashboard/TrackSessionCard.tsx` | UI-012 (verb), UI-025 | 7.1, 2.3 | local | LOW |
| `app/(authenticated)/subjects/page.tsx` + `SubjectAttendanceGrid.tsx` | UI-005, UI-001, UI-011 | 2.1, 1.1, 5 | local | LOW |
| `components/dashboard/SubjectAttendanceCard.tsx` | UI-012 (keep as canonical), UI-017/018 | 7.1, 7.2 | local | LOW |
| `components/dashboard/home/OverallAttendanceCard.tsx` | UI-001, UI-012 | 1.1, 7.1 | local | LOW |
| `components/dashboard/home/AttentionRequiredCard.tsx` | UI-004, UI-012 | 4, 7.1 | local | LOW |
| `components/dashboard/home/WeeklyAttendanceCard.tsx` | UI-013, UI-038, UI-040 | 7.1, 7.3, 11 | local | LOW |
| `components/dashboard/home/QuizSnapshotCard.tsx` | UI-027, UI-021 | 11, 6.2 | local | LOW |
| `components/dashboard/home/UpcomingEventsCard.tsx` | UI-021 | 6.2 | local | LOW |
| `components/dashboard/home/GreetingHeader.tsx` | UI-031 | 11 | local | LOW |
| `app/(authenticated)/dashboard/page.tsx` | UI-005, UI-022, UI-040 | 2.1, 2.2, 11 | local | LOW |
| `app/(authenticated)/history/page.tsx` | UI-005, UI-011, UI-016, UI-024 | 2.1, 5, 6.1, 10 | local | MEDIUM |
| `app/(authenticated)/calendar/page.tsx` | UI-011, UI-019, UI-021, A-3 | 5, 9, 6.2, 11 | local | MEDIUM |
| `app/(authenticated)/tools/events/page.tsx` | UI-009, UI-011, UI-021 | 3, 5, 6.2 | local | LOW |
| `components/events/EventFormDialog.tsx` | UI-016, UI-034, UI-035 | 6.1, 11 | local | MEDIUM |
| `components/notifications/NotificationCenter.tsx` | UI-014, UI-039, UI-021 | 8, 6.2 | local | MEDIUM |
| `components/notifications/NotificationBell.tsx` | — (badge path stays) | — | none | — |
| `components/shell/SettingsModal.tsx` | UI-016, UI-019, UI-010, UI-024 | 6.1, 9, 7.3, 10 | local | MEDIUM |
| `components/shell/InstallAppModal.tsx`, `FeedbackModal.tsx`, `ProfileModal.tsx` | UI-010 | 7.3 | copy | LOW |
| `components/layout/TopNav.tsx`, `MobileBottomNav.tsx`, `AppShell.tsx`, `navItems.ts` (new) | UI-003, UI-004, UI-008, UI-011 | 4, 5 | systemic | HIGH |
| `components/shared/ErrorState.tsx`, `EmptyState.tsx`, `PageHeader.tsx` | UI-005, UI-021, UI-011 | 2.1, 6.2, 5 | shared | MEDIUM |
| `components/ui/input.tsx`, `ui/select.tsx` (new) | UI-016, UI-024 | 6.1 | shared | MEDIUM |
| `components/feedback/Toast*`, `ConfirmDialog.tsx` (new) | UI-025, UI-006/009/015 | 2.3, 3 | new shared | MEDIUM |
| `lib/api.ts` | UI-026 | 2.4 | additive only | HIGH (frozen-adjacent; guardrail below) |
| `components/pwa/useServiceWorker.ts` + banner (new) | UI-023 | 2.4 | additive UI | MEDIUM |
| `lib/date.ts`, `lib/statusLabels.ts` (new), `lib/format.ts` (new) | UI-012/017/018 | 7.1–7.2 | shared | LOW |
| `app/(auth)/login/page.tsx`, `signup/page.tsx` | UI-028, UI-029, UI-026 | 6.1, 7.3, 2.4 | local | LOW |
| `public/manifest.json` | UI-037 | 11 | config | LOW |
| `hooks/useApi.ts` | A-2 | 6.2 | deletion | LOW |
| `components/dashboard/SubjectLaboratoryView.tsx` | A-1 | 6.2 | deletion | LOW |

**Guardrail for `lib/api.ts` (Phase 2.4):** additive `sessionStorage.setItem("session_expired","1")` immediately before the existing redirect; no change to refresh logic, token lifecycle, or redirect targets. Any reviewer must diff this file in isolation.

---

## 12. Risk Matrix

| Change | Regression probability | Impact | Affected surfaces | Rollback | Manual verification burden |
|---|---|---|---|---|---|
| 1.1 token definitions | LOW | LOW (visual) | 14 files | trivial (CSS revert) | Medium (visual pass) |
| 1.2 accent→primary | LOW | LOW | calendar/events/profile/quiz | trivial | Low |
| 1.3 404/error UI | LOW | LOW | global | trivial (delete files) | Low |
| 2.1 ErrorState + adoption | LOW | LOW | 4 surfaces | easy | Low |
| 2.3 toast provider | MEDIUM | MEDIUM (global mount) | app-wide | easy (unmount) | Medium |
| 2.4 `lib/api.ts` additive | LOW | **HIGH** (auth-adjacent) | session flow | easy but sensitive | Medium (login/expiry flow) |
| 2.4 SW banner | LOW | LOW | PWA | easy | Medium (SW lifecycle) |
| 3 ConfirmDialog adoptions | LOW | MEDIUM (mutation flows) | track/labs/events | easy | Medium |
| 4 navigation IA | MEDIUM | MEDIUM | header/nav app-wide | easy | **High** (all bands) |
| 5 layout contract | MEDIUM | MEDIUM (visual everywhere) | all 11 routes | easy | **High** (all viewports) |
| 6.1 control heights/Select | MEDIUM | LOW–MEDIUM | forms everywhere | easy | Medium |
| 7.x vocabulary/formatting | LOW | LOW (text) | ~15 files | easy | Medium (copy review) |
| 8 notification UX | LOW | MEDIUM | center + badge sync | easy | Medium |
| 9 settings honesty | LOW | LOW | settings/calendar | easy | Low |
| 10 a11y fixes | LOW | LOW | 3–4 surfaces | easy | Medium (SR/keyboard) |
| 11 polish batch | LOW | LOW | 6 surfaces | easy | Medium |

Overall: no VERY HIGH items; the two HIGH-consequence cells (2.4 api.ts, 4 nav) are contained by additive-only edits and decision gating respectively.

---

## 13. Manual Verification Plan (for the user, after implementation)

**Viewport matrix:** 320, 375, 414 (mobile) · 768, 834, 1024 (tablet band) · 1440, 1920 (desktop). Test on at least one real iOS and one Android device/Chrome.

1. **Tokens/visual (Phase 1):** Laboratory + Quiz + Subjects show visible skeletons while loading; calendar event dots, today ring, selection highlight, and all four legend swatches are visible; links tinted blue; `/nonexistent` shows branded 404; force a render error (or use error boundary test hook) to see `error.tsx`.
2. **Navigation (Phase 4):** at 768px confirm no wrap/clip (admin account too — 9th item); More dropdown at md; mobile: navigate to Calendar/Quiz/Events — More tab shows active tint; header shows page title; deep links to each route open the correct tab state.
3. **Layout (Phase 5):** gutters uniform at 375 (16px) and 1440 (centered 5xl); no page shows double padding; PageHeader spacing consistent.
4. **Errors (Phase 2):** kill the backend → Dashboard, History, Track, Subjects each show Retry; with backend up but analytics blocked, dashboard shows the partial-data note; log out server-side / expire token → next API failure lands on login with the expiry message.
5. **Destructive (Phase 3):** Mark-all shows a count confirmation; lab delete asks; event deactivate error appears inline (no native alert).
6. **Notifications (Phase 8):** act on one row — only that row's buttons disable; Mark all read works and the badge empties; push arrives → badge updates (existing behavior must not regress).
7. **Settings (Phase 9):** week-start choice reflected in calendar (if D-05 A); auto-mark shows deferred labeling.
8. **Accessibility (Phase 10):** keyboard-only pass: tab through quiz selector and lab tabs, operate with arrows/Enter as designed; screen-reader smoke test on the notification center and Track; verify focus visible in dialogs; check 320px tap ergonomics on History filters.
9. **PWA (Phase 2.4/11):** installed app launch — splash color matches; after a deploy, update banner appears and Reload applies the new shell; iOS: bottom nav never covers the last control; address-bar collapse does not clip the shell.
10. **Session/404:** hard-reload on a deep link while logged out → login → sign in → returns to the deep link (existing behavior must not regress).

## 14. Static Verification Plan (per phase; no browser automation)

- Always: `npx tsc --noEmit`; `npm run lint`; `npm run build` (with `NEXT_PUBLIC_API_URL` CI placeholder as in prior phases); `git diff --check`.
- Phase 1: `grep -rE "bg-surface2?|text-text2" frontend/src` returns only mapped token classes; compiled `.next/static/chunks/*.css` contains `.bg-surface` utilities after build; `grep -rn "text-accent\|bg-accent\|ring-accent"` shows only hover-surface usages.
- Phase 3: `grep -rn "window.alert" frontend/src` → 0.
- Phase 4: `grep` confirms single `NAV_ITEMS` source imported by both navs; `npm run build` route list unchanged (25/25 pages).
- Phase 5: `grep -rn "max-w-7xl\|max-w-4xl\|max-w-2xl" frontend/src/app` only inner-content hits, zero root wrappers.
- Phase 7: `grep -rnE "PostgreSQL|Tracked in task.md|Ingest|toFixed\(1\)" frontend/src` → only allowed sites (calculation detail); label map imported by dashboard cards.
- Phase 8: `git diff --stat` shows only `NotificationCenter.tsx` (+ tests/none); `node --check` N/A (TS); tsc covers.
- Backend untouched: `git diff --stat backend/` → empty for Phases 1–11 (except none planned at all); `alembic heads` unchanged; no migration files created.
- Backend touched by nothing in this blueprint; therefore no `compileall` is required except as a sanity check after Phase 12 if any backend file was accidentally modified (it should read zero diffs).

---

## 15. Out-of-Scope / Protected Systems

Untouched unless explicitly and separately authorized:
- **Authentication/session internals:** token storage, refresh single-flight, multi-tab storage events, logout revocation (Phase 2.4 adds a user-facing notice only, adjacent to the redirect).
- **Attendance calculation** (`backend/app/engines/attendance_engine.py`, repos): thresholds are *referenced* for a frontend constant, never modified.
- **Eligibility logic** (quiz engine, criterion evaluation): frontend renders only.
- **Notification generation & Web Push architecture** (`notification_service.py`, `push_dispatch_service.py`, SW push handlers, VAPID config): Phase 8 is presentation-only; Phase 2.4's banner does not touch SW caching/strategy.
- **Backend API contracts**: no new, changed, or removed endpoints in this plan (D-12 Option A reuses the idempotent per-item PATCH).
- **Database schema / Alembic migrations / production configuration / deploy configs**: zero changes.
- **Frozen prior-phase files with pre-existing ESLint errors** (noted in governance): avoid gratuitous reformatting beyond the findings' scope.

---

## 16. Recommended Implementation Sequence

Exact order, with rationale:

1. **Phase 0 — Decision gate** (D-01…D-13). Everything downstream is gated on explicit choices; no silent product decisions.
2. **Phase 1 — Visual foundation** (1.1 tokens → 1.2 accent → 1.3 404/error → 1.4 verify). Foundational: every later phase renders through these tokens; cheapest phase with the largest visible repair.
3. **Phase 2 — Feedback architecture** (2.1 ErrorState+Retry → 2.2 partial data → 2.3 toast → 2.4 expiry+SW banner). Establishes the primitives that Phases 3, 8, and 11 consume; page adoption here is small (4 surfaces) by design.
4. **Phase 3 — Destructive-action safety.** Independent of navigation/layout; needs only D-11 and (optionally) 2.3's toast. Doing it before the big structural phases keeps mutation flows stable while structure changes around them.
5. **Phase 4 — Navigation & IA.** Decisions D-01…D-04 approved in Phase 0; structural changes to the shell should precede Phase 5 so layout verification happens once, after the header/nav are final.
6. **Phase 5 — Layout contract.** One mechanical pass over 11 page roots; after nav so header height/title slot are already final.
7. **Phase 6 — Primitive consolidation** (6.1 controls → 6.2 migrate duplicates → 6.3 type floor). Requires 1.x tokens and 2.1's ErrorState API; consolidating consumers before Phase 7 prevents double-migrating labels.
8. **Phase 7 — Vocabulary, formatting & content** (7.1 status module → 7.2 formatters → 7.3 copy). Terminology decisions are already approved; primitives are consolidated so each label swap happens once.
9. **Phase 8 — Notification UX.** Needs 2.3 (toast) and D-11/D-12; isolated to one component.
10. **Phase 9 — Settings honesty.** Needs D-05/D-06; touches calendar which is stable after Phases 5/6.
11. **Phase 10 — Accessibility.** Fixes page-level ARIA/targets after their host surfaces are structurally final; primitive-level a11y already landed in 6.1.
12. **Phase 11 — Screen-specific polish.** All remaining local findings once nothing above them will move.
13. **Phase 12 — Verification & close-out.** Full manual checklist (§13) + static sweep (§14) + governance reconciliation + completion report.

Each phase ends at its STOP CONDITION; no phase may begin until its stated dependencies and decision gates are satisfied.

---

*Blueprint only. No code, CSS, routes, copy, backend, schema, or configuration was modified in producing this document. The audit at `docs/UI_UX_AUDIT_STUDENT_APP_2026-09-05.md` remains unchanged and authoritative.*
