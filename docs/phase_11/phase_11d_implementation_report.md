# Phase 11D — Notification Center UX: Implementation Report

> **PHASE 11D COMPLETE (2026-08-20).** Phase 11 — Notifications & Reminders: **IN PROGRESS** (11.0 audit ✅ · 11A ✅ · 11B ✅ · 11D ✅ · 11C decision-gated/deferred · 11E/11F NOT STARTED). No commit made.

## 1. Objective

Implement the frontend notification center UX that consumes the live Phase 11A/11B backend contract (`GET /api/v1/notifications` + `PATCH /api/v1/notifications/{notification_id}`): a notification bell with an unread badge in the authenticated shell, and a notification center dialog with a chronological inbox, unread/read visual state, mark-read and dismiss actions, and honest loading/empty/error/retry states — following the project's existing `apiFetch`/SWR conventions, shell components and design language. Frontend-only; no backend change; no second notification data model; no Phase 11C behavior.

## 2. Exact Files Changed

| File | Change |
|---|---|
| `frontend/src/types/api.ts` | Additive notification contract types mirroring the backend: `NotificationKind` enum (the six 11A kinds), `NotificationItem` (natural-key `id`, `kind`, `date`, `subject_code`/`subject_name`, `message`, `session_id`/`quiz_cycle`/`event_id`, `notification_id`, `is_read`), `NotificationsResponse` (`items`, `as_of`, `unread_count`), `NotificationUpdate` (`is_read`/`is_dismissed`). |
| `frontend/src/hooks/useApi.ts` | `useNotifications(enabled)` — SWR on `GET /api/v1/notifications`, key gated on `enabled`, `STANDARD_CACHE` (focus revalidation only, no polling). `useNotificationMutation()` — `PATCH /api/v1/notifications/{id}`, returns the server's updated item. |
| `frontend/src/components/notifications/NotificationBell.tsx` | **New.** Bell button for the authenticated `TopNav`; unread badge from the backend `unread_count` (hidden at zero, capped at "99+"); opening the center revalidates once. |
| `frontend/src/components/notifications/NotificationCenter.tsx` | **New.** `ShellDialog` "Notifications": loading skeletons, error + Retry, honest empty state, newest-first persisted inbox; per-row kind badge/icon, message, subject + occurrence date, unread emphasis; "Mark as read" (unread rows) + dismiss actions. Cache updated only from genuine PATCH responses; failures surface in an inline banner and leave the list unchanged. |
| `frontend/src/components/layout/TopNav.tsx` | Bell mounted in the right cluster (before `UserMenu`); `NotificationCenter` rendered via the existing `activeModal` state machine. |
| `frontend/src/components/layout/UserMenu.tsx` | `"notifications"` added to the exported `ShellModalId` union. |

No other file was touched: no backend file, no migration, no engine, no shell rebuild, no other page/component.

## 3. UX Surface

- **Bell:** icon-only button in the `TopNav` right cluster. Badge shows the backend `unread_count` only when > 0, capped at "99+". Accessible label announces the unread count ("Notifications (3 unread)").
- **Center:** modal with the unread count in the description; list scrolls (`max-h`), rows in backend order (newest first).
  - Each row: kind badge + kind icon (CLASS_REMINDER → primary/BookOpen, QUIZ_APPROACHING → warning/CalendarClock, ATTENDANCE_THRESHOLD → danger/AlertTriangle, MUST_ATTEND → danger/Target, SAFE_SKIP → success/CheckCircle2, ACADEMIC_EVENT → neutral/CalendarDays), the backend message, subject code + occurrence date (`formatLongDate`), and an unread dot.
  - Unread rows are visually emphasized (muted background, medium-weight message) and expose "Mark as read" (`Check`); every row exposes a dismiss action (`X`).
- **States:** loading (skeleton rows), API error (destructive banner + Retry via SWR `mutate`), empty ("No notifications yet"), populated, and per-action pending (spinner, all actions disabled while one is in flight) / per-action error banner.

## 4. Behavior Guarantees

- **No faked success.** Mutations update the SWR cache only after a genuine 2xx PATCH response. On failure the actual backend error detail is shown and the list remains unchanged.
- **Idempotent actions.** Repeating "Mark as read" on an already-read row is a no-op success (backend idempotency); the "Read" action is not rendered for read rows.
- **Dismiss semantics.** Dismiss removes the row from the inbox; the backend persists `is_dismissed` (a dismissed occurrence cannot resurrect on regeneration). `unread_count` is recomputed from the resulting inbox, matching the backend definition (unread + non-dismissed).
- **SWR correctness.** The bell and the center subscribe to the same SWR key (`/api/v1/notifications`), so there is one logical request per revalidation (SWR dedupe) and the badge stays in sync with read/dismiss updates without extra round-trips. The key is null when unauthenticated (token gate) or when the center is closed — no unconditional/global fetches. `STANDARD_CACHE` only: focus revalidation + 1-minute deduping; no polling loops, no N+1 item requests.
- **Authorization.** The client never sends `user_id` — ownership is derived from the JWT by the backend.

## 5. Backend Contract Preservation

No backend file was modified. The frontend consumes `GET /api/v1/notifications` (inbox newest-first + `unread_count`) and `PATCH /api/v1/notifications/{notification_id}` (`NotificationUpdate`: at least one of `is_read`/`is_dismissed`; empty body → 422) exactly as implemented in 11B. `as_of` is not displayed (not part of the required UX surface); `notification_id` is used as the PATCH target only.

## 6. Scope Discipline (NOT done)

- No push / browser `Notification` API / service worker / PWA / email / SMS / scheduled jobs / cron / Celery / Redis / delivery providers / reminder scheduling — 11C remains decision-gated and deferred.
- No automatic attendance marking, no analytics/week-start/`auto_mark_present` behavior changes, no new notification generation logic, no client-side notification computation.
- No backend change was necessary; none was made.

## 7. Verification

- `npx tsc --noEmit` — PASS (0 errors).
- `npx eslint` on the changed files (`types/api.ts`, `hooks/useApi.ts`, `components/notifications/NotificationCenter.tsx`, `components/notifications/NotificationBell.tsx`, `components/layout/TopNav.tsx`, `components/layout/UserMenu.tsx`) — PASS (0 errors/warnings).
- `npm run build` — PASS; all 12 routes prerendered successfully.
- Backend verification unchanged from 11B (`verify_phase_11b.py` 23/23, `verify_phase_11a.py` 19/19 — not re-run because no backend file changed).
- No browser/manual tests run — the user performs manual/browser testing.

## 8. What Was NOT Done (deferred)

- **11C** delivery model — decision-gated (in-app only vs scheduled sweep); may be omitted from Phase 11 entirely.
- **11E** remaining preference wiring — not started.
- **11F** phase completion (consolidated verifier + governance reconciliation + COMPLETE & FROZEN) — not started.
- `auto_mark_present` semantics — owner product decision, unchanged.

## 9. Next Authorized Slice

**11E** (remaining preference wiring) followed by **11F** (phase completion), pending explicit authorization. 11C remains decision-gated/deferred.

**PHASE 11D COMPLETE — HARD STOP.** No commit was made. 11C remains decision-gated/deferred · 11E NOT STARTED · 11F NOT STARTED. Browser/manual testing remains the user's responsibility. Phase 11 remains **IN PROGRESS** (not COMPLETE/FROZEN).