# Phase 11 — Notifications & Reminders: Architecture & Discovery Audit

**AttendanceDash Pro · 2026-08-20 · READ-ONLY AUDIT — NO IMPLEMENTATION**

> This document is the Phase 11 architecture baseline. It was produced
> without modifying application code, creating migrations, mutating the
> database, running browser tests, or creating a commit. Phase 11 has **not
> started**; no implementation sub-phase may begin from this document alone.

---

## 1. Purpose and scope

- Determine exactly what Phase 11 is supposed to accomplish according to the
  repository (no invented requirements).
- Trace every piece of existing infrastructure relevant to notifications and
  reminders.
- Explicitly enumerate what does **not** exist.
- Analyze the three Phase 10D preference fields as potential Phase 11 inputs.
- Resolve the notification-architecture question (UI-only / in-app / browser /
  PWA push / scheduled) **from repository evidence only**.
- Identify risks, produce a concrete sub-phased implementation plan, a
  decision list, a dependency graph, a DO-NOT-TOUCH list, and a final
  recommendation.
- **HARD STOP after this document is written.**

## 2. What Phase 11 is, per the repository

### 2.1 Authoritative spec: `MASTER_ROADMAP.md` (Phase 11 section, marked NEXT)

```
# 🟢 Phase 11 — Notifications & Reminders (NEXT)

Only after the academic/event architecture is stable.

Potential features:

- Upcoming class reminder
- Quiz approaching
- Attendance-below-threshold warning
- Must-attend warning
- Safe-skip information
- Academic event notification

### Architectural rule

Notifications consume engine outputs.

They do **not** independently calculate attendance.
```

The only normative constraints are:

1. **Notifications consume engine outputs.** Every notification value must
   come from the canonical engines (`attendance_engine`,
   `eligibility_engine`, `calendar_engine`, the event→session synchronizer) —
   never from duplicate math in a notification service.
2. **No independent attendance calculation.** Notifications must not
   recompute percentages, windows, or eligibility.
3. Phase 11 may start only because the academic/event architecture is stable
   (Phases 6–9 frozen; Phase 10 frozen).

### 2.2 Secondary evidence

- **`implementation_plan.md`** and **`task.md`** contain **no Phase 11
  sections** — they only reference Phase 11 as the future consumer of the
  Phase 10D preference fields. No additional requirements exist there.
- **`docs/16_ROADMAP.md` (legacy static app) "Phase F7 — Notifications":**
  "Push notifications (via Web Push API) when: Attendance falls below
  threshold; Quiz date is approaching; An extra class is scheduled. Requires a
  notification service and permission handling." This is the **legacy**
  roadmap of the retired static app; it is informative prior art, not the
  governing spec of the Next.js rewrite.
- **`docs/S4_PRODUCT_SPEC.md`**: contains **zero** references to reminders,
  notifications, alerts, push, or toasts — the product/UI spec does not
  define any notification surface.
- **Phase 10 reports** (`docs/phase_10d_implementation_report.md`,
  `docs/phase_10_completion_audit_report.md`,
  `docs/phase_10e_implementation_report.md`): the Phase 10D contract
  explicitly labels `class_reminders`, `auto_mark_present`, `week_starts_on`
  as STORAGE/PREFERENCE DATA ONLY, "Phase 11 consumes them later". The audit
  report states the three fields "are precisely the inputs Phase 11
  (Notifications & Reminders) needs".

### 2.3 Conclusion — what Phase 11 is

Phase 11 = a notification/reminder capability that:

- surfaces **upcoming classes**, **approaching quizzes**, **attendance-below-
  threshold**, **must-attend**, **safe-skip**, and **academic-event**
  information;
- is **derived exclusively from canonical engine outputs**;
- is the **designated consumer of `class_reminders`** (and, pending a product
  decision, the other two preference fields).

Phase 11 does **not**, by any document, promise: auto-writing attendance,
browser push, offline delivery, email/SMS, or a server-side scheduler.

## 3. Existing infrastructure inventory (trace)

### 3.1 Preference storage (Phase 10D) — the intended input

| Layer | Location | Notes |
|---|---|---|
| Endpoints | `backend/app/api/v1/endpoints/preferences.py` | `GET`/`PUT /api/v1/student/preferences`; JWT-only identity via `get_current_user`; no client user selector |
| Schemas | `backend/app/schemas/preference.py` | `PreferenceUpdate` (all 3 fields required), `PreferenceResponse` (+ `created_at`/`updated_at`); no `user_id` exposed |
| Service | `backend/app/services/preference_service.py` | Lazy-create defaults false/false/MONDAY; full-object replace; race-safe via IntegrityError re-read |
| Repository | `backend/app/repositories/preference_repo.py` | `get`/`create_default`/`replace`; repo never commits |
| Model | `backend/app/models/preference.py` | `userpreferences`; `user_id` UUID PK/FK → `users.id`; `class_reminders`, `auto_mark_present` bool NOT NULL DEFAULT false; `week_starts_on` enum `weekstartson` NOT NULL DEFAULT MONDAY |
| Migration | `backend/alembic/versions/c1d2e3f4a5b6_add_user_preferences.py` | Additive; head of a linear chain (down_revision `b1c2d3e4f5a7`); no relationships to other tables |
| Verifier | `backend/scripts/verify_phase_10d.py` | 18/18, including "storing the three preferences changed NO attendance/event/session/record data" and exact baseline restore |
| Frontend | `frontend/src/components/shell/SettingsModal.tsx` | Three real controls (two switches + week select), SWR `usePreferences(open)`, full-object PUT via `usePreferenceMutation`; info box states "these are preferences only… will be used by future features" |
| Frontend types | `frontend/src/types/api.ts` | `UserPreferences`, `UserPreferencesUpdate`, `WeekStart` ("STORAGE/PREFERENCE DATA ONLY… Phase 11 wires them into features") |
| Frontend hook | `frontend/src/hooks/useApi.ts` | `usePreferences(enabled)` on `/api/v1/student/preferences`; `usePreferenceMutation().savePreferences` PUT |

**Dead / storage-only fields today:** all three. No consumer exists anywhere
in the codebase (verified by repository-wide grep — the only mentions are the
preference files, the migration, the SettingsModal, and the docs above).

### 3.2 Data sources a notification read model would consume

| Domain | Canonical source | Existing read surfaces |
|---|---|---|
| Upcoming classes | `class_sessions` (materialized by `EventSessionSynchronizer` + timetable) with `date`, `start_time`, `end_time`, `is_cancelled`, `is_extra`, `designation`; practical blocks collapsed by `practical_occurrence.py` | `GET /attendance/today` (Track), dashboard Today section, history |
| Quiz approaching | `quiz_schedules` (per-cycle `quiz_date`), `quiz_cycles`, `eligibility_policies` | `GET /quiz-eligibility`, dashboard `quiz_snapshot`, `CurrentQuizCycle` (`basis: next_upcoming/latest_resolved/fallback`) |
| Attendance below threshold / must-attend / safe-skip | `attendance_engine.py`: `classify_attendance_health`, `classify_attendance_status`, `optimize_attendance` (deficits/safe-skips), `meets_attendance_target`; `AttendanceService.get_summary` / `get_subject_summaries` | `GET /attendance/summary/{code}`, `GET /analytics/overview` (overall + per-subject health, optimization), dashboard `attention_required` (WATCH/CRITICAL) |
| Academic events | `academic_events` (active flags, event types incl. EXTRA_*, CLASS_CANCELLED, QUIZ_DAY, HOLIDAY family, MID_SEM_PRACTICAL, LAB_CANCELLED); `calendar_engine.get_academic_day`/`get_teaching_days_between`; `EventSessionSynchronizer.sync_event` | `GET /events`, calendar month read model, dashboard `upcoming_events` |
| Academic context | `sections → semesters → academic_sessions`, enrollments, `student_profile` (program, semester_start/end, first_quiz_date) | `GET /student/me`, `GET /student/profile` |

### 3.3 Architecture of the backend (where a notification service would live)

- Strict layering: **engines** (pure) → **services** (orchestration) →
  **repositories** (SQL) → **endpoints** (auth + mapping). Repos never
  commit; services own transactions.
- `get_current_user` (`backend/app/api/dependencies/deps.py`) — JWT `sub` →
  DB user; `require_admin` for admin mutations. This is the existing
  identity boundary a notification endpoint must reuse.
- `institution_today()` (`attendance_service.py:30`, Asia/Kolkata) is the
  canonical institutional date; several read models still use `date.today()`
  (server-local) — a real consistency risk for any time-bound generation.
- Route registration: `backend/app/api/api.py` (flat include; preferences
  router is mounted under `/student`).

### 3.4 Frontend shell (where a notification UX would attach)

- `TopNav` + `UserMenu` (Profile / Appearance / Install App / Send Feedback /
  Settings / Sign Out). No bell, no notification entry point, no badge.
- SWR-based hooks + `apiFetch` with Bearer JWT; dialogs via `ShellDialog`;
  Base UI primitives available (`@base-ui/react` — has Menu/Dialog/Switch).
- `types/api.ts` is the single typed contract file; every value is
  backend-derived by convention ("React never computes attendance").

### 3.5 Deployment topology (what can host scheduled work today)

- `docker-compose.yml`: **PostgreSQL 16 only**. The backend runs as a single
  `uvicorn app.main:app` process (no supervisor, no worker container, no
  queue). Frontend: Next.js 16 dev/build/start. No production infra, no
  CI/CD, no process manager (Phase 17/18 scope).

## 4. Explicitly missing infrastructure (verified)

| Capability | Exists? | Evidence |
|---|---|---|
| Notification persistence (table/model) | **NO** | `backend/app/models/` has no notification model; the 17-table schema has no notification table |
| Reminder records | **NO** | none |
| Notification API | **NO** | `api/api.py` mounts 12 routers; no notifications router |
| Notification center / inbox UI | **NO** | grep for `Notification`/`toast` in `frontend/src` → only the Settings section header string |
| Browser Notification API usage | **NO** | no `Notification`/`pushManager`/`serviceWorker` in frontend source |
| Service worker | **NO** (in the Next.js app) | `frontend/public/` has only default SVGs; no `manifest.json`/`sw.js`. (A legacy static-app SW exists only in history: `docs/12_PWA_AND_DEPLOYMENT.md`, retired with the old app) |
| Web push subscription storage | **NO** | — |
| Scheduled jobs / cron / worker | **NO** | no APScheduler/Celery/Redis/cron anywhere; `requirements.txt` has 10 packages, none scheduled-execution; `scripts/` are all one-shot maintenance/verification tools |
| Email / SMS / push providers | **NO** | no provider SDKs or config |
| Server-side reminder scheduler | **NO** | — |
| Frontend notification-permission flow | **NO** | — |
| Notification abstractions in engines | **NO** | engines expose pure compute only (health/status/optimize/eligibility/day classification) — correct inputs, no notification layer |

**Summary:** the project has the complete **data + engine** substrate and
**zero** notification/delivery substrate. Phase 11 must therefore build the
domain side (read model, persistence, API, UX) and either defer delivery or
pick a delivery model deployable on the current single-process architecture.
---

## 5. The three preference consumers, analyzed separately

### A. `class_reminders` (boolean)

- **Documented intent:** reminder of upcoming classes (roadmap feature list "Upcoming class reminder"); the field name and Phase 10 reports confirm the only plausible consumer is a class-reminder feature.
- **Authoritative data source:** `class_sessions` (enrollment-scoped, future dates, non-cancelled, occurrence-collapsed) — the exact read surface the Track/dashboard/history read models already use.
- **Where behavior lives:** a new backend notification/reminder service that READS sessions (never writes them); the frontend renders only. Gating: when `class_reminders = false`, no class reminder is generated for that user.
- **Dependencies/blockers:** none on the data side. Delivery mechanism is the only dependency (see section 7).
- **Phase placement:** **IN Phase 11.** This is the clearest, safest consumer — read-only, preference-gated, no mutation.

### B. `auto_mark_present` (boolean) — special attention

- **Documented intent:** NONE. No repository document defines what "auto-mark present" means. The name is the only clue. The roadmap feature list does NOT include auto-marking. `implementation_plan.md` explicitly says: "auto-marking is not in the roadmap". Phase 10 reports consistently state the field is storage-only and that nothing may "mark attendance".
- **Critical constraint:** attendance records are written ONLY through the canonical mutation path (Track page mutation API, `AttendanceMutationRequest {class_session_id, status}`). That path rejects future-dated sessions and cancelled sessions (400), and is a deliberate user-action surface. Any consumer that writes records without an explicit user action — especially retroactively ("whenever a class time passes") — would: (1) bypass the canonical mutation service and its invariants, (2) risk duplicate or double-writes, (3) create attendance truth the user never confirmed, (4) violate "Notifications do not independently calculate attendance" in spirit by fabricating records.
- **Conclusion:** `auto_mark_present` must **NOT be implemented in Phase 11** without an explicit product-owner decision. If ever implemented, the only acceptable shape is an explicit, per-session, user-confirmed interaction that invokes the CANONICAL mutation API (e.g., a "mark all my pending sessions as present" confirmation limited to already-past, non-cancelled sessions) — never an unattended background write. For Phase 11 the field remains storage-only; the Settings UI text stays honest.
- **Phase placement:** **Deferred (product decision required).**

### C. `week_starts_on` (enum SUNDAY/MONDAY)

- **Documented intent:** the user's preferred calendar week-start. NOT a notification input — it is a display/read-model preference.
- **Authoritative data source:** none today; the dashboard weekly series and analytics weekly series are hardcoded Monday-start (`today.weekday()`), and the calendar/analytics read models are frozen. Consuming it would change frozen read-model output semantics — an unrelated scope.
- **Phase placement:** **NOT a Phase 11 concern.** It belongs to a future UI/analytics phase (after the frozen read models are reopened deliberately). Keep storage-only.

## 6. Notification architecture — determined from evidence

The question: does Phase 11 mean UI-only indicators, persisted in-app notifications, browser notifications, PWA push, scheduled server-side reminders, or a combination?

Evidence:

1. The roadmap lists only INFORMATION features (upcoming class, quiz approaching, threshold warning, must-attend, safe-skip, event notification) — all **read-model content**, not delivery infrastructure.
2. The architectural rule mandates engine-consumption — consistent with a backend **read model** service, exactly like `DashboardService`/`AnalyticsService` (both compose engines without re-implementing math and are the house pattern).
3. **PWA/installability (manifest, service worker, install prompt) is Phase 13.** Browser push requires a service worker; offline capability is explicitly not claimed. Therefore Web Push is NOT available in Phase 11 — evidence rules it out.
4. `S4_PRODUCT_SPEC.md` defines no notification UI at all — no design constraint exists, so the UI must be honest and minimal (bell + panel, no invented patterns).
5. There is no scheduler/worker/cron and no deployment slot for one (docker-compose runs only Postgres; backend is a single uvicorn). A server-side scheduled reminder sweep cannot be reliably deployed on the current architecture without new infrastructure.

**Conclusion (evidence-based):** Phase 11 = a **backend notification read model + in-app notification records (persisted, with read/dismiss state) + frontend notification center UX**. Generation happens **on-read** (like every existing read model: each request computes the current state from engine outputs as of now) and optionally snapshots into a notifications table for an inbox/history + unread state. Delivery is **in-app only** (bell badge + panel); browser/push delivery is deferred to Phase 13 (PWA) with an infrastructure decision.

## 7. Scheduled execution — does the architecture have a place for it?

**No.** The current architecture has no scheduled-execution host:

- No worker process, no queue, no Redis, no Celery, no APScheduler, no cron in or outside the repo.
- The backend is a single stateless uvicorn; a background loop would be process-bound and silently lost on restart/scale.
- Postgres cannot reliably drive time-triggered delivery without an external trigger.

If push-style delivery is ever wanted, the MINIMUM infrastructure options (for a future decision, NOT introduced now):

1. **Read-time generation (recommended for Phase 11, zero new infra):** the frontend polls/refreshes the notifications endpoint (SWR is already the house pattern); "reminders" are computed at request time with an honest `as_of`/`generated_at` timestamp. Identical to how Dashboard/Analytics already behave.
2. **External cron/`at` hitting a generation endpoint** (e.g., a system-token-protected generation endpoint) — no code dependency, but needs an external scheduler and deployable endpoint auth.
3. **In-process scheduler (APScheduler) in the uvicorn process** — deployable today but process-bound, needs single-instance guarantees, adds a dependency.
4. **A separate worker service** — requires new deployment infrastructure (Phase 17 territory).

None of these are introduced by this audit.

## 8. Risks of implementing Phase 11 incorrectly

1. **Duplicate attendance writes** — if any reminder flow ever writes records (auto-mark), double-writes corrupt the canonical counts. Mitigation: notifications NEVER write attendance; `auto_mark_present` deferred.
2. **Bypassing canonical attendance mutation** — writing through anything except the existing mutation API. Mitigation: read-only notification service; any future auto-mark uses the canonical endpoint with explicit confirmation.
3. **Notification spam** — unbounded per-user notification rows or repeated identical reminders. Mitigation: per-kind daily caps, dedup keys (e.g., session_id / quiz cycle / subject per day), retention limits, dismiss/read state.
4. **Timezone/date-boundary errors** — `institution_today()` (Asia/Kolkata) vs `date.today()` (server-local) inconsistency already exists across read models. Any time-bound generation must use ONE institutional clock consistently.
5. **Reminder duplication** — same class reminder regenerated on every poll. Mitigation: dedup by natural key (session_id + date + kind) in the persisted model; read-state prevents re-display.
6. **Stale preferences** — a notification generated before a preference toggle must not resurface. Mitigation: preferences are read at generation time; toggling `class_reminders` off suppresses future rows (and optionally marks existing ones).
7. **Cross-user data leakage** — notification rows scoped to the wrong user. Mitigation: every query scoped by `user_id` from `get_current_user`; no client identity; verifier proves isolation (the Phase 10D/10C pattern).
8. **Coupling notification logic to frozen engines** — importing engine internals or re-deriving thresholds. Mitigation: consume only public engine/service outputs (health, status, optimization, quiz dates, sessions); hard architectural rule.
9. **Second source of truth** — persisting computed attendance values inside notification payloads. Mitigation: notification rows store REFERENCES (session id, subject code, quiz cycle, date) and presentation text, never recomputed statistics that other read models own.
10. **Infrastructure the project cannot reliably deploy** — Redis/Celery/workers/Web Push have no deployment slot (no production infra until Phase 17; PWA until Phase 13). Mitigation: Phase 11 stays in-process and database-only.
11. **Frozen-phase drift** — touching frozen read models (dashboard/analytics week semantics) while building notifications. Mitigation: additive-only notification surface; DO-NOT-TOUCH list (section 14).

---

## 9. Phase 11 implementation plan (sub-phased)

Decomposition is driven by the evidence: data/engine substrate exists, delivery substrate does not. The natural seam is therefore **read model first, persistence second, UX third, scheduling deferred**. The roadmap's "UI-only vs persisted vs push" question is answered as: persisted in-app notifications generated on-read (section 6).

### 11.0 — Audit & architecture (THIS document)

- **Objective:** architecture baseline, decisions list, dependency graph, risk register, DO-NOT-TOUCH list. Read-only.
- **Files:** `docs/phase_11/phase_11_architecture_audit.md` (+ later: `docs/phase_11/phase_11_product_decisions.md` if the owner produces decisions).
- **Impact:** none (documentation only).
- **Dependencies:** none.
- **Frozen:** everything.
- **Verification:** n/a (review by owner).
- **Migration:** none. **External infra:** none. **Deployable:** yes.

### 11A — Backend notification read model + contracts (no persistence yet)

- **Objective:** a `NotificationService`/`NotificationRepository`-free read model that derives per-user notification candidates EXCLUSIVELY from engine outputs; endpoint `GET /api/v1/notifications` (JWT, enrollment-scoped); Pydantic schemas (`NotificationItem`, kinds enum); no DB table yet — the endpoint returns computed candidates with `as_of`.
- **Kinds (all engine-derived):** `CLASS_REMINDER` (future `class_sessions`, gated by `class_reminders`, occurrence-collapsed, cancelled excluded, time from session start_time), `QUIZ_APPROACHING` (next `quiz_schedules` date within a horizon), `ATTENDANCE_THRESHOLD` / `MUST_ATTEND` / `SAFE_SKIP` (from `attendance_engine` health/status/`optimize_attendance` via `AttendanceService.get_subject_summaries`), `ACADEMIC_EVENT` (active events within horizon from calendar read model).
- **Files likely changed:** `backend/app/schemas/notification.py`, `backend/app/services/notification_service.py`, `backend/app/api/v1/endpoints/notifications.py`, `backend/app/api/api.py`, `backend/app/models/enums.py` (additive `NotificationKind` enum only), verifier `backend/scripts/verify_phase_11a.py`.
- **Backend/frontend impact:** additive API; frontend unchanged (or a minimal honest "coming" hook). No DB change.
- **Dependencies:** frozen engines/services (read-only consumption). No new packages.
- **Frozen:** all engines, all read models, preferences contract, DB schema.
- **Verification strategy:** in-process verifier (house pattern): kind presence/absence under controlled fixture data, preference gating (`class_reminders` false → no CLASS_REMINDER), enrollment scoping, no cross-user leakage, 401 unauthenticated, `as_of` honesty, frozen-table baselines byte-identical before/after.
- **Migration:** none. **External infra:** none. **Deployable:** yes (single uvicorn, no new process).

### 11B — Notification persistence + read-state API

- **Objective:** `notifications` table + model/repo/service; generation snapshots candidates into rows with dedup by natural key; `GET /api/v1/notifications` (inbox, newest first, unread count), `PATCH /api/v1/notifications/{id}` (read/dismiss), optional `DELETE` (dismiss). Retention/dedup policy per section 8 mitigations.
- **Files likely changed:** `backend/alembic/versions/<new>_add_notifications.py`, `backend/app/models/notification.py`, `backend/app/repositories/notification_repo.py`, `backend/app/services/notification_service.py` (extends 11A), endpoint/schema updates, `backend/app/models/__init__.py`, verifier `verify_phase_11b.py`.
- **Backend/frontend impact:** additive table + endpoints; contract additive.
- **Dependencies:** 11A. **Frozen:** all pre-Phase-11 tables/engines; `userpreferences` unchanged.
- **Verification:** baseline snapshot → generate → dedup (second run adds no rows) → read/dismiss state transitions → retention cap → isolation (user A never sees B) → exact cleanup of verifier rows → frozen tables identical; `alembic heads == current`.
- **Migration:** YES — one additive migration (new head). **External infra:** none. **Deployable:** yes.

### 11C — Scheduling/delivery (deferred — decision-gated)

- **Objective:** deliver notifications without user opening the app (browser Notification, push, email). NOT implementable on current architecture (no SW until Phase 13, no worker until Phase 17, no provider).
- **Recommended Phase 11 scope:** NONE beyond read-time generation (11A) + SWR refresh (11D). If the owner wants server-side sweeps, the minimum safe option is an external cron hitting a system-token-protected `POST /api/v1/notifications/generate` endpoint (option 2 in section 7) — still no new in-repo infrastructure.
- **Migration:** none. **External infra:** only if the owner chooses the cron option.

### 11D — Frontend notification UX

- **Objective:** bell icon with unread badge in `TopNav`/`UserMenu` area; notification center (Base UI Popover/Panel) listing items with read/dismiss actions; honest empty state; SWR hook `useNotifications()` + `useNotificationMutation()` following `usePreferences` conventions; types in `types/api.ts`. No client-side attendance math; no fake push; a settings note in `SettingsModal` may become truthful ("Class reminders are shown in the bell icon when enabled") once 11E lands.
- **Files likely changed:** `frontend/src/components/layout/TopNav.tsx` or a new `frontend/src/components/notifications/NotificationBell.tsx` / `NotificationCenter.tsx`, `frontend/src/hooks/useApi.ts`, `frontend/src/types/api.ts`.
- **Dependencies:** 11A (or 11B for read-state). **Frozen:** design system tokens used as-is; `ShellDialog`/Base UI reused.
- **Verification:** `tsc --noEmit`, targeted ESLint, `npm run build`; no backend changes.
- **Migration:** none. **External infra:** none. **Deployable:** yes.

### 11E — Preference consumers (scoped)

- **Objective:** wire `class_reminders` as the CLASS_REMINDER gate (implemented in 11A). `auto_mark_present` and `week_starts_on` remain storage-only pending owner decisions (sections 5B/5C).
- **Files likely changed:** only inside the 11A/11B notification service (read the preference row at generation time). SettingsModal copy updated to match reality.
- **Dependencies:** 11A. **Migration:** none. **External infra:** none.

### 11F — Verification & freeze

- **Objective:** full Phase 11 verifier (`verify_phase_11.py`, consolidating 11A/11B checks), regression run of ALL frozen verifiers, DB baseline proof, alembic head check, `compileall`, `tsc`, targeted ESLint, `npm run build`, governance reconciliation (MASTER_ROADMAP.md Phase 11 → COMPLETE & FROZEN, implementation_plan.md/task.md Phase 11 records, walkthrough.md entry), final report `docs/phase_11/phase_11_implementation_report.md`.
- **Migration:** none (11B already applied). **External infra:** none. **Deployable:** yes.
- **HARD STOP after 11F** — no commit, Phase 12 not started.

**Ordering note:** 11A → 11B → 11D → 11F is the minimal coherent vertical slice; 11E rides inside 11A; 11C is decision-gated and can be dropped from Phase 11 entirely.

## 10. Decisions required before implementation

### Already answered by repository documentation

- Notifications consume engine outputs; no independent attendance calculation (roadmap rule).
- Phase 13 owns PWA/installability (manifest, SW, offline) — so Web Push/offline is NOT Phase 11.
- `class_reminders` is the class-reminder gate; `auto_mark_present` and `week_starts_on` are storage-only today.
- Institutional date authority: `institution_today()` (Asia/Kolkata) must be the single clock for time-bound generation.
- House architecture pattern: engine → service → repo → endpoint; repos never commit; JWT-only identity via `get_current_user`; verifiers with exact baseline restore.

### Require product-owner input (genuine decisions)

1. **`auto_mark_present` semantics** — does it mean assisted marking (explicit user confirmation invoking the canonical mutation) or nothing? Recommend: remains storage-only in Phase 11.
2. **Delivery model** — in-app only (recommended for Phase 11) vs browser Notification vs server-side sweep (cron) vs Phase 13 push. This decides whether 11C exists at all.
3. **Reminder horizons/thresholds** — how many days ahead for class/quiz/event reminders; which attendance band triggers a warning (WATCH vs AT_RISK vs CRITICAL). Defaults can be picked from existing engine thresholds (75% target, health bands) but the horizon is a product choice.
4. **Retention/dedup policy** — how long notifications persist, daily caps per kind.

### Safely deferrable

- `week_starts_on` consumption (belongs to a read-model/analytics phase).
- `auto_mark_present` (see decision 1).
- Browser/push delivery (Phase 13 + infra).
- Admin-targeted notification surfaces (e.g., faculty-facing) — not in the roadmap list.

## 11. Dependency graph

```text
11.0 (audit, done)
 ├── 11A (read model, no DB change)          ── needs: frozen engines/services (read-only), preferences row, api.py registration
 │     ├── 11E (class_reminders gate)        ── depends on 11A
 │     └── 11B (persistence + read-state)    ── depends on 11A; needs: alembic (additive migration)
 │           ├── 11D (bell + center UX)      ── depends on 11B (read-state) or 11A (minimal)
 │           └── 11C (scheduling)            ── DECISION-GATED; depends on 11B; may be deferred/omitted
 └── 11F (verification & freeze)             ── depends on 11A + 11B + 11D (+ 11E)
```

No frozen system is a dependency that may be modified — all edges are read-only consumption.

## 12. DO NOT TOUCH list (frozen systems)

Phase 11 must not modify any of the following unless a genuine defect is proven (and even then only via an explicit hotfix authorization):

- **Attendance domain:** `attendance_engine.py`, `AttendanceService`, attendance mutation API (`POST /attendance/...`), `AttendanceRecord`/`ClassSession` tables, `practical_occurrence.py`, `verify_*` attendance verifiers.
- **Eligibility/quiz domain:** `eligibility_engine.py`, `EligibilityService`, `QuizRepository`, `quiz_schedules`/`quiz_cycles`/`eligibility_policies` tables, quiz endpoints.
- **Calendar/events domain:** `calendar_engine.py`, `CalendarService`, `EventSessionSynchronizer`, `event_registry.py`, event endpoints, `academic_events` table.
- **Laboratory domain:** laboratory service/repo/endpoints/tables.
- **Dashboard/analytics/history read models:** `DashboardService`, `AnalyticsService`, history endpoints — output contracts are frozen (weekly Monday-start semantics, health/status bands).
- **Auth:** `deps.py` (`get_current_user`, `require_admin`), `security.py`, `firebase.py`, JWT handling.
- **Feedback (10C) and Preferences (10D) contracts:** `feedback`/`userpreferences` tables and their GET/PUT/POST endpoints; Phase 11E may READ preferences but never change the contract.
- **Frozen verifiers and fixtures:** `verify_phase_*.py` — no assertion changes, no fixture drift acceptance without authorization.
- **Migrations:** no historical migration may be edited; new migrations must chain to head `c1d2e3f4a5b6` linearly.
- **DB state:** no data mutation outside verifier cleanup; baseline (31 users / 1 section / 47 events / 715 sessions / 142 records / 27 enrollments / 9 subjects / 28 timetable / 18 quizzes / 3 cycles / 3 policies / 1 session / 1 semester / 0 feedback / 0 preferences / 0 lab) must be provably restored.

## 13. Final recommendation

- **Readiness verdict:** NOT implementation-ready as one phase. READY for **11A only** (backend notification read model + contracts, zero DB change, zero new infra) — the smallest safe slice. The full Phase 11 is gated on the delivery-model and `auto_mark_present` decisions.
- **Do first:** owner review of this audit (sections 9–10), then 11A with verifier; keep `auto_mark_present`/`week_starts_on` storage-only; do NOT create migrations or infrastructure before 11A is frozen.
- **Smallest safe slice:** 11A (schemas + `NotificationService` read model + `GET /api/v1/notifications` + `verify_phase_11a.py`). No migration, no frontend, no scheduler — fully deployable today, verifiable with the house pattern, and honest (it can return `{"items": [], "as_of": ...}` with a clear scope).
- **Infrastructure blockers:** server-side scheduled delivery (no scheduler/worker slot) and Web Push (Phase 13 PWA). Both can be avoided by read-time generation; if push is required later, an external cron + Phase 13 SW is the minimum path.
- **Product-decision blockers:** `auto_mark_present` semantics (recommend: defer), reminder horizons/thresholds, retention policy, delivery model. None block 11A.

> **HARD STOP:** this audit made no implementation, no migration, no DB mutation, and no commit. Phase 11A (or any sub-phase) must not start without owner authorization.
