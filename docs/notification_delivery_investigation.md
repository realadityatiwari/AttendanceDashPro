# Notification Delivery Investigation — "No Notifications Dropping"

**AttendanceDash Pro · 2026-09-02 · INVESTIGATION ONLY — NO IMPLEMENTATION**

> This is a static, read-only investigation of the complete notification
> architecture (frontend → backend → database → browser/PWA). Nothing was
> implemented, migrated, deployed, committed, or mutated. Findings are
> **proven from source code**, not inferred from UI labels.

---

## 1. Current notification architecture (text diagram)

```text
                         ┌────────────────────────────────────────────────────┐
                         │              NOTIFICATION DOMAIN                   │
                         │                                                   │
 EVENT/DATA SOURCES      │  GENERATION (ON-READ, pull-based)                  │
 ─────────────────       │                                                   │
 class_sessions      ──► │ NotificationService.get_notifications()  ←── GET  │
 quiz_schedules      ──► │   _class_reminders      (gated by preference)     │
 attendance_engine   ──► │   _quiz_approaching     (next-upcoming cycle)     │
 eligibility_engine  ──► │   _attendance_items     (WATCH/CRITICAL/optimizer)│
 academic_events     ──► │   _academic_events      (active, end>=today, cap4)│
 (via repositories/       │        │                                          │
  services)               │        ▼ upsert_many (ONE multi-row txn)         │
                         │  notifications table  (UNIQUE user_id,kind,key)   │
                         │        │ 60s per-user TTL in-memory cache         │
                         │        ▼                                           │
                         │  GET /api/v1/notifications  →  items + unread_count│
                         │  PATCH /api/v1/notifications/{id} (read/dismiss)  │
                         └────────────────────────────────────────────────────┘
                                              │
                                              ▼  (REST over HTTPS/JWT)
                         ┌────────────────────────────────────────────────────┐
                         │  FRONTEND (Next.js, SWR)                           │
                         │  NotificationBell  ── useNotifications(!!token)    │
                         │    · fetches at shell mount (STANDARD_CACHE)       │
                         │    · revalidates on window focus only (no polling) │
                         │    · manual mutate() on bell click                 │
                         │  NotificationCenter ── useNotifications(open)      │
                         │    · fetches when dialog opens                     │
                         │    · PATCH read/dismiss → SWR cache update         │
                         └────────────────────────────────────────────────────┘
                                              │  ✗ NOTHING BELOW THIS LINE
                         ┌────────────────────────────────────────────────────┐
                         │  BROWSER / PWA LAYER (ABSENT)                      │
                         │  · Notification.requestPermission()      — never  │
                         │  · navigator.serviceWorker.register()   — never  │
                         │  · PushManager / pushManager.subscribe() — never  │
                         │  · service-worker "push" listener        — never  │
                         │  · showNotification()                    — never  │
                         │  · VAPID keys                            — never  │
                         │  · push subscription storage (DB/model)  — never  │
                         │  · backend web-push send path            — never  │
                         └────────────────────────────────────────────────────┘
```

**The pipeline ends at the REST response.** There is no code path from
`GET /api/v1/notifications` (or from any event) to an OS/browser notification.

---

## 2. What "notification" currently means (Investigation Section 1)

The production code implements **exactly one** of the five possibilities:

| Capability | Implemented? | Evidence |
|---|---|---|
| 1. In-app notifications (bell + center, REST-driven) | **YES — complete** | `NotificationBell.tsx`, `NotificationCenter.tsx`, `useNotifications`, backend 11A/11B endpoint+service+repo |
| 2. Browser Web Notifications while page is open (`new Notification()`/`showNotification`) | **NO** | zero matches for `Notification.requestPermission`, `new Notification`, `showNotification` in `frontend/src` |
| 3. Full Web Push via service worker | **NO** | zero matches for `PushManager`, `pushManager`, `pushSubscription`, `applicationServerKey`, VAPID anywhere; `service-worker.js` has no `push` listener |
| 4. Installed-PWA background push | **NO** | same as 3; manifest has no push config |
| 5. Incomplete combination | **Partially** | in-app (1) complete; the PWA layer (SW file + manifest) exists but the registration hook `useServiceWorker()` is **defined but never mounted**, so the SW never registers at runtime |

**Permission is never requested.** There is no code path that calls
`Notification.requestPermission()`, so the user-observed "browser/PWA
notification permission allowed" state must have been granted for the origin
in the browser settings — but **permission alone produces nothing**, because:

```text
Notification.permission === "granted"        ← user/browser state only
serviceWorkerRegistration.pushManager.getSubscription() !== null  ← NEVER
```

There is no `pushManager` call of any kind in the codebase (verified by
repository-wide grep; the only match is a historical audit table row in
`docs/phase_11/phase_11_architecture_audit.md:168` documenting the absence).

---

## 3. Service worker (Investigation Section 2)

- **Where defined:** `frontend/src/components/pwa/useServiceWorker.ts` — registers `/service-worker.js` with default scope (`/`), guards against double-registration, adds update-found/state-change handlers, focus + hourly `registration.update()` checks.
- **Is it mounted?** **NO.** Repository-wide grep for `useServiceWorker` finds only the definition (line 24). It is not imported by `AppShell.tsx`, `TopNav.tsx`, either layout, or any page. `git log -S "useServiceWorker"` shows it was introduced in commit `0454c9e` ("PWA infrastructure") and **never wired to any component in any commit**. It is dead code today.
- **Does `navigator.serviceWorker.register()` run?** **NO** — it exists inside the unmounted hook, so it never executes. No registration, no install, no activation, no control. `navigator.serviceWorker.controller` is never set.
- **Registration path/scope:** would be `/service-worker.js`, scope `/` (default from the public root) — never reached.
- **Production build includes the worker?** The file lives in `frontend/public/service-worker.js`, so it is served as a static asset by Vercel/`next start` (public dir passes through unchanged). The *file* is deployable; the *registration* is not performed.
- **Browser vs installed PWA:** identical — registration never happens in either mode.
- **Service-worker contents** (`frontend/public/service-worker.js`, 119 lines): install (precache `STATIC_ASSETS`, no `skipWaiting`), activate (`clients.claim()`), fetch (API network-only; navigation network-first). It has **NO**:
  - `push` event listener
  - `notificationclick` listener
  - `notificationclose` listener
  - `showNotification` call
  - payload parsing
  - deep-link handling

---

## 4. Web Push subscription (Investigation Section 3)

Repository-wide searches (frontend, backend, docs, configs):

- `PushManager` / `pushManager` / `pushSubscription` / `applicationServerKey`: **zero matches**
- VAPID / vapid (any casing): **zero matches** (source + `.env`/`.env.example`/`deploy/.env.prod.example`)
- web-push / pywebpush / push library: **zero matches**; `backend/requirements.txt` has 10 packages, none push-related
- subscription POST/DELETE endpoints: **none** (`backend/app/api/api.py` mounts 14 routers — auth, student, preferences, subjects, timetable, attendance, quiz-eligibility, calendar, events, laboratory, dashboard, analytics, feedback, notifications, admin)
- PostgreSQL push-subscription table/model/migration: **none** (only the `notifications` table from Phase 11B)
- per-user/device subscription records: **none**

**A browser with permission does NOT create or persist a push subscription.**
There is no code that could.

---

## 5. Backend push delivery (Investigation Section 4)

**Nothing exists:**

- No pywebpush / webpush / equivalent import or usage
- No VAPID private/public configuration (no env vars, no settings, no .env keys)
- No endpoint-URL + p256dh + auth-key storage
- No delivery jobs, notification dispatch service, push-failure cleanup, 404/410 invalidation, retry logic, or background/scheduled jobs (no APScheduler/Celery/cron/worker anywhere; single uvicorn process; `UVICORN_WORKERS=1`)
- **No trigger exists either.** Who would push? There are zero calls into any push path because the path does not exist. `NotificationService.get_notifications` is invoked only by `GET /api/v1/notifications` (bell/center); `update_state` only by PATCH. Nothing in attendance recording, quiz scheduling, event creation, or any other mutation touches the notification service (verified: `NotificationService` referenced only from `notifications.py` endpoint).

**The backend only writes notification rows and serves them on GET.** It never calls a push provider or speaks the Web Push protocol — there is nothing to speak it with.

---

## 6. In-app notification pipeline (Investigation Section 5)

The in-app pipeline is **intact and works by design** (pull-based, on-read generation):

```
data changes (attendance marks, quiz dates, events…)
  → GET /api/v1/notifications (only when called)
  → NotificationService.get_notifications (cache miss after 60s TTL)
  → projections from engines/services (class, quiz, attendance, events)
  → upsert_many → notifications table (idempotent by UNIQUE(user_id, kind, occurrence_key))
  → get_inbox + count_unread
  → NotificationsResponse (items + unread_count), cached 60s per user
  → SWR cache → NotificationBell badge / NotificationCenter list
```

Verified behaviors:

- **Generation happens only on GET /notifications.** There is no event-driven generation: notification rows exist only after a GET regenerates them (at most once per 60 s TTL per user). Nothing else writes rows.
- **Qualifying rules today** (`notification_service.py`):
  - `CLASS_REMINDER`: gated by `pref.class_reminders`; **default is OFF** when no preference row exists (`_class_reminders`: `if pref is None or not pref.class_reminders: return []`). A user who never toggled "Class reminders" in Settings gets **zero** class reminders by design.
  - `QUIZ_APPROACHING`: needs ≥1 `quiz_applicable` subject AND a next-upcoming cycle with a confirmed `quiz_date`.
  - `ATTENDANCE_THRESHOLD`/`MUST_ATTEND`/`SAFE_SKIP`: needs attendance-applicable subjects; threshold only when band WATCH/CRITICAL; must-attend/safe-skip only when optimizer is reachable with a nonzero deficit/skip.
  - `ACADEMIC_EVENT`: active events with `end_date >= today`, enrollment-scoped, capped at 4 (17 seeded QUIZ_DAY events exist, so qualifying users should receive these).
- **Hidden/read/filtered:** dismissed rows are excluded from the inbox; read rows stay in the inbox. Regeneration upsert preserves `date`, `is_read`, `is_dismissed`, `created_at` — dismissed/read never resurface.
- **60-second cache:** `_notification_cache` (per-user UUID key, monotonic clock, 60 s TTL). A fresh record generated by one request is served for up to 60 s; new records can appear only after TTL expiry + next GET. **This cannot hide records forever** — at most 60 s + one revalidation.
- **Cache invalidation:** read/dismiss PATCH removes the user's entry (`_cache_invalidate`), so the next GET is fresh. Complete for the only mutating path.
- **User-specific filtering:** all queries scoped by `user_id` from JWT (`get_by_id`/`get_inbox`/`count_unread`/`update_state`); no client identity.
- **Timezone/date boundaries:** generation uses `institution_today()` (Asia/Kolkata via `app/core/timezone.py`) consistently; week scoping Monday–Sunday; quiz cycle canonical. No obvious boundary defect.
- **Idempotency:** `UNIQUE(user_id, kind, occurrence_key)` — same occurrence upserts in place, never duplicates; distinct occurrences stay distinct.

**Conclusion: in-app generation is not broken.** Records are generated when a qualifying condition holds, persisted, and served with an unread badge. If the user sees nothing in the bell, the likely reasons are (a) no qualifying event for their data/preferences, or (b) they are expecting OS-level "dropping" notifications, which this pipeline never produces.

---

## 7. "New notification dropping" (Investigation Section 6)

The current UI has **no mechanism for receiving newly generated notifications in real time**:

| Mechanism | Present? | Evidence |
|---|---|---|
| Polling / `refreshInterval` | **NO** | zero `refreshInterval` in `frontend/src`; Phase 11D report explicitly removed polling ("no polling") |
| SWR focus revalidation | **YES (only)** | `STANDARD_CACHE` (`revalidateOnFocus: true`, `dedupingInterval: 60000`) on `useNotifications` |
| WebSocket | **NO** | no WebSocket/SSE/EventSource in backend or frontend |
| SSE | **NO** | same |
| Push event | **NO** | no SW push listener |
| Manual revalidation | **YES** | bell click → `mutate()`; center open → `useNotifications(open)` fetch |
| Notification-center-open revalidation | **YES** | `useNotifications(open)` gated key |

**This is the critical distinction.** With the app open and focused:

```text
Backend record exists (created by a GET after TTL expiry)
BUT
client never fetches again (no focus change, no bell click, no center open)
→ no badge update, no notification of any kind
```

A new notification appears in the bell **only** after: window focus revalidation, opening the center, or page reload. While the user sits in the app without focus changes, nothing drops, nothing appears, and (without browser Notification support) nothing can.

---

## 8. Installed PWA (Investigation Section 7)

| Scenario | Supported? | What actually happens |
|---|---|---|
| A. Website open + focused | **Partial (in-app only)** | Bell badge may update on focus revalidation; nothing is "dropped" (no Notification API) |
| B. Website open but backgrounded | **No** | No SW push, no polling, no SSE. Notification rows may be generated server-side only if a GET occurs (it does not in the background); badge stays stale |
| C. Installed PWA open | **Same as A** | Identical code path; `display-mode: standalone` is only read for the Install modal (`useInstallPrompt`); no notification behavior differs |
| D. Installed PWA closed | **No** | Nothing can run: no push subscription, no SW registration, no service worker event |
| E. Browser completely closed | **No** | Same |

Manifest + service worker exist, but **background notification support must not be inferred from them**: the SW never registers, and even if it did, it contains no `push` handler.

---

## 9. Permission UI (Investigation Section 8)

**There is no notification-permission UI in the codebase.** The only notification-adjacent control is the **"Class reminders" switch** in `SettingsModal.tsx`, which performs `PUT /api/v1/student/preferences` (a database preference row) — nothing else. It does **not**:

- call `Notification.requestPermission()`
- register a service worker
- create a PushSubscription
- send a subscription to the backend
- implement any disable/unsubscribe flow

There is no UI that says "notifications enabled" in the browser-permission sense. If the user granted permission via the browser's site settings, no application code ever acted on that permission — nothing reads `Notification.permission`, nothing requests it. **Classification: the "allow notifications" state the user granted is completely inert** — not misleading UI, but an unimplemented capability (Phase 11C was explicitly decision-gated/deferred, and the Phase 11 audit's §4 "missing infrastructure" table documented exactly this).

---

## 10. Production-specific configuration (Investigation Section 9)

- **HTTPS:** yes — Render + Vercel serve HTTPS (HSTS env-gated). Web Push would be permitted by the platform.
- **Service-worker path/scope:** `/service-worker.js` under scope `/` — file present in `public/` (ships with the build), registration absent.
- **Frontend origin:** Vercel (`NEXT_PUBLIC_API_URL` points at the Render backend; `api.ts` fails the build if unset/localhost in production).
- **Backend origin:** Render Free web service, 1 uvicorn worker (`UVICORN_WORKERS=1`), `APP_ENV=production`.
- **Environment variables:** no VAPID, no push-related variables anywhere (`.env`, `.env.example`, `deploy/.env.prod.example`, `render.yaml`).
- **CORS:** `BACKEND_CORS_ORIGINS` env-driven; no push-subscription endpoints exist to be covered.
- **Render worker/process behavior:** single web service; no background process, no scheduler slot (documented in the Phase 11 audit §3.5/§7).
- **Vercel:** static/SSR Next.js; SW file would be served, but nothing registers it.

---

## 11. Root-cause classification (Investigation Section 10)

Ranked by impact:

| # | Classification | Severity | Confirmed by |
|---|---|---|---|
| 1 | **D — Missing Web Push subscription** (nothing ever subscribes; `PushManager` absent) | Blocker for any OS-level delivery | grep zero matches |
| 2 | **E — Missing backend Web Push delivery** (no send path, no dispatch, no trigger) | Blocker | requirements.txt, api.py, zero references |
| 3 | **F — Missing VAPID/configuration** | Blocker | env files, settings, zero matches |
| 4 | **C — Service worker not registered** (`useServiceWorker` defined, never mounted; `navigator.serviceWorker.register()` never runs) | Blocker | grep + git history |
| 5 | **G — Missing background trigger/job** (generation is on-read; no event hook, no scheduler; nothing "pushes" even in-app) | High | `NotificationService` callers |
| 6 | **B — Notification cache/revalidation gap** (no polling/SSE/push; bell updates only on focus/open; 60 s TTL adds latency) | Medium | useApi.ts, Phase 11D report |
| 7 | **H — Misleading permission state** (granted browser permission is inert; the only "notification" setting toggles a preference row) | Medium | SettingsModal, no Notification API usage |
| 8 | **I — Browser/PWA platform limitation** (background delivery impossible without items 1–5) | Consequence | — |
| 9 | **A — In-app notification generation bug** | **NOT CONFIRMED** — pipeline verified intact | §6 |

**Bottom line:** this is **not a regression**. Full Web Push was never
implemented in AttendanceDash Pro — the Phase 11 architecture audit
(2026-08-20) explicitly documented zero push substrate and Phase 11C was
deferred as decision-gated ("delivery model"). The user's expectation of
"notifications dropping" corresponds to browser/PWA delivery, which is a
**missing/incomplete capability** (items D/E/F/C/G), compounded by a
revalidation design that intentionally removed polling (item B) and by an
inert permission state (item H). The in-app notification domain itself is
**functional by design** (item A not confirmed; generation + cache +
invalidation all verified).

---

## 12. Files involved

**Backend (in-app, functional):**
- `backend/app/models/notification.py` — Notification model + `UNIQUE(user_id, kind, occurrence_key)`
- `backend/app/models/enums.py:169` — `NotificationKind`
- `backend/app/schemas/notification.py` — item/response/update contracts
- `backend/app/repositories/notification_repo.py` — inbox/upsert_many/update_state (Phase B batch optimization)
- `backend/app/services/notification_service.py` — projection generation + 60 s TTL cache
- `backend/app/api/v1/endpoints/notifications.py` — GET/PATCH endpoints
- `backend/app/api/api.py:18` — router registration
- `backend/alembic/versions/d1e2f3a4b5c6_add_notifications.py` — notifications table migration

**Frontend (in-app, functional):**
- `frontend/src/components/notifications/NotificationBell.tsx`
- `frontend/src/components/notifications/NotificationCenter.tsx`
- `frontend/src/components/layout/TopNav.tsx:108,134` — mounts bell + center
- `frontend/src/components/layout/UserMenu.tsx` — `"notifications"` modal id
- `frontend/src/hooks/useApi.ts:464-495` — `useNotifications` / `useNotificationMutation`
- `frontend/src/types/api.ts:693-728` — notification types
- `frontend/src/components/shell/SettingsModal.tsx` — "Class reminders" preference toggle (the only notification-adjacent control)

**PWA layer (files exist, functionality absent):**
- `frontend/public/service-worker.js` — install/activate/fetch only; **no push/notificationclick/showNotification**
- `frontend/public/manifest.json` — install manifest; no push config
- `frontend/src/components/pwa/useServiceWorker.ts` — registration hook, **never mounted**
- `frontend/src/components/layout/AppShell.tsx` — does NOT mount the hook
- `frontend/src/hooks/useInstallPrompt.ts`, `frontend/src/components/shell/InstallAppModal.tsx` — install prompt only

**Evidence/docs:**
- `docs/phase_11/phase_11_architecture_audit.md` — §4 missing-infrastructure table (push/SW/permission: NO), §6 conclusion (in-app only), 11C decision-gated
- `docs/phase_11/phase_11d_implementation_report.md` — "no push / browser Notification API / service worker … 11C remains decision-gated and deferred"
- `docs/phase_11/phase_11f_verification_report.md`, `phase_11a/b/e_implementation_report.md`

---

## 13. Recommended implementation phases (ordered by dependency and risk)

Derived from the actual repository state. **Nothing below is implemented.**

### Phase P1 — Frontend PWA registration + permission (low risk, no backend)
1. Mount `useServiceWorker()` once in the authenticated shell (`AppShell` or a provider) so `/service-worker.js` registers on login. Verify install → activated → controlling.
2. Add an honest notification-permission surface (e.g., in Settings "Notifications"): calls `Notification.requestPermission()` when the user opts in; reflects `Notification.permission` state; only then proceeds to subscription. Keep "Class reminders" preference semantics unchanged.
3. Extend `service-worker.js` with `push`, `notificationclick`, `notificationclose` handlers, payload parsing, and deep-link routing (click → `/dashboard` or a `/notifications` route). Bump `CACHE_VERSION`.

### Phase P2 — Push subscription creation + persistence (backend additive)
1. Frontend: after permission, `serviceWorkerRegistration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: <VAPID public key> })`; `getSubscription()` for existing.
2. Backend: new `push_subscriptions` table (migration): `user_id` FK, endpoint, p256dh, auth, created_at/updated_at, per-user-device rows. Model + repository (owner-scoped, JWT-only identity).
3. Endpoints: `POST /api/v1/push-subscriptions` (authenticated; body validated to PushSubscription shape; associates only with the current user — no client user_id), `DELETE /api/v1/push-subscriptions/{id}` (unsubscribe).
4. Frontend `usePushSubscription()` hook: subscribe when permission granted + SW ready; register/refresh on auth; unsubscribe on disable/logout.

### Phase P3 — VAPID configuration + backend Web Push dispatch (backend)
1. VAPID keypair generation script (private key server-side only); `VAPID_PUBLIC_KEY` exposed to frontend (public), `VAPID_PRIVATE_KEY` + `VAPID_SUBJECT` backend-only env.
2. Add `pywebpush` (or equivalent) to requirements; a `PushDispatchService` that takes a canonical notification row + user's subscriptions, encodes the message payload, and sends.
3. Failure handling: 404/410 → delete the dead subscription; other permanent failures → retry policy; transient → leave for next dispatch. Never log `auth`/`p256dh` values.

### Phase P4 — Trigger strategy (decouple push from reads; keep in-app canonical)
The recommended seam — **keep the in-app feed as the source of truth**:

```text
domain event/data change
  → canonical in-app notification generated + persisted (existing 11A/11B path)
  → NEW: post-persist hook dispatches Web Push for the newly created/updated
    notification (per user's subscriptions + preferences)
  → in-app feed unchanged; push is a delivery side-channel only
```

1. Move generation off "on-read only": a `generate_and_persist(user_id)` call invoked after relevant mutations (attendance record, quiz schedule/event changes) and/or a periodic sweep (external cron hitting an authenticated endpoint, or a lightweight loop — the Phase 11 audit §7 options; note the single-worker constraint).
2. Dispatch only on genuinely new rows (or refreshed-with-unread rows) to avoid push spam; honor `class_reminders`-style gates and dismissed/read state.
3. No push without a persisted in-app notification — push must never be the source of truth.

### Phase P5 — Cache/revalidation adjustment (small, parallelizable)
Restore *cheap* freshness for the bell: e.g., a modest `refreshInterval` on `useNotifications` (the 60 s backend TTL makes focus revalidation already cheap; a 60–120 s poll is one tiny request), or keep focus-only but revalidate on `visibilitychange`. This fixes the "app open, nothing appears" gap independently of Web Push.

### Security requirements baked into P2–P4
- Subscription endpoints authenticated (`get_current_user`); subscription rows created only for the current user; cross-user isolation preserved (owner-scoped repo, same pattern as notifications).
- Request body validated to genuine push-subscription shape (endpoint must be https/wss, p256dh/auth base64 length checks) — no arbitrary endpoint injection.
- VAPID private key never in frontend bundles or logs; only the public key is public.
- Dead subscriptions removed on 404/410; retries bounded.
- Auth keys not logged; at rest, treat as sensitive.

### Parallelizable with current performance work
- **P1 (SW mount + permission + SW push handlers)** — frontend-only, zero backend interaction, independent of the Phase 26 query-dedup work.
- **P5 (bell refresh interval)** — frontend-only; interacts only with the existing TTL cache (already validated by Phase B).
- **P2 schema/endpoints** — backend but additive; no engine/read-model changes; can be authored and verified locally in parallel.
- **P3/P4** — touch notification generation triggers; must sequence after P2 (needs subscriptions to exist) and should not be interleaved with frozen-phase verifier runs; lowest parallelism.

### Regression risks
- SW registration changes caching behavior (network-first navigation, network-only API): risk of stale shell if `CACHE_VERSION` not bumped; the SW is already designed with versioned caches.
- Permission UI + Settings: the "Class reminders" preference contract must not change shape (10D frozen); additive UI only.
- New migration: must chain linearly to head `a9b8c7d6e5f4`; keep it additive; don't touch `notifications`/`userpreferences`.
- Push dispatch must never write attendance/eligibility/calendar data; dispatch failures must never fail the generating mutation (fire-and-forget with logging).
- Read-time generation move (P4) must preserve upsert idempotency and the TTL cache invalidation semantics; frozen verifiers (11A/11B/11F, and the phase-26 ones) must remain green.
- VAPID private key handling: env-gated; production guard pattern (like JWT_SECRET_KEY) to prevent a dev default from shipping.
- Admin Portal: out of scope — no admin push surfaces.

---

## 14. Behavior matrix — why nothing "drops" today

| State | What the user sees | Root cause chain |
|---|---|---|
| Browser open, focused | Nothing drops; bell may show a stale/absent badge | No Notification API, no push; bell revalidates only on focus |
| Browser open, backgrounded | Nothing | No polling/SSE/push; generation is on-read and no GET happens |
| Installed PWA open | Same as browser | Same code path; SW never registered |
| Installed PWA closed | Nothing | No push subscription + no registered SW + no backend send path |
| Browser closed | Nothing | Same as above |

---

## 15. Governance reconciliation

This investigation is recorded in:

- `MASTER_ROADMAP.md` — investigation note under Phase 11; Phase 11 stays **COMPLETE & FROZEN** (11C remains deferred; Web Push NOT marked complete)
- `implementation_plan.md` — investigation record
- `task.md` — investigation checklist entry
- `walkthrough.md` — investigation walkthrough entry

**HARD STOP — investigation complete. No implementation, no migration, no
commit, no browser automation.**
