# Events Backend — Deep Audit Report

**Date:** 2026-10-02
**Scope:** The complete student/admin **Events** (AcademicEvent) backend of AttendanceDashPro — model, CRUD, session-synchronizer side effects, calendar/dashboard/notification consumers, authorization, dates, transactions, tests, seeds, scripts.
**Mode:** READ-ONLY INVESTIGATION. No code, schema, migration, test, config, or data was modified. Live DB access was limited to `SELECT`-only probes (§21). No remediation was implemented.
**Source of truth:** the current repository (`main` @ `13a4795`) plus the live dev PostgreSQL database.

---

## 1. Executive Summary

The Events system is a mature, well-documented subsystem built around one invariant: **"ACADEMIC EVENT = EXACT-DATE SCHEDULE MUTATION"** — every active event is reconciled into the canonical `class_sessions` pipeline by a state-based, idempotent `EventSessionSynchronizer` inside the event's own transaction. The core architecture is sound: event + session effects are atomic, attendance records are protected by a frozen contract, deletion is safe soft-deactivation, authorization is DB-resolved per request (Phase 23.11), and dates are deliberately `Date`-only with a single institutional clock (Asia/Kolkata), which eliminates the entire class of time/timezone conversion bugs by construction.

The weaknesses are concentrated in three areas:

1. **The notification lifecycle of an event is incomplete.** ACADEMIC_EVENT inbox rows are created on create/update but are never cleaned up or refreshed when the event is **deactivated** (`deactivate_event` never calls the notification trigger) or **moved into the past** (the trigger early-returns for past events and nothing deletes). Stale announcements persist as *live* inbox rows because the H-4a read-filter only hides rows whose event row **no longer exists** — soft-deleted events still exist. (EVT-001, EVT-002)
2. **A critical product guard is enforced at the wrong layer.** The Phase 24.9 "quiz-schedule-managed QUIZ_DAY" guard (explicitly labeled *critical* in its docstring) exists only in `AdminEventService`, i.e. only on `/api/v1/admin/events`. The canonical `/api/v1/events` POST/PATCH/DELETE endpoints call `EventService` directly with no such guard, so any effective admin can deactivate or re-date a schedule-backed QUIZ_DAY through the public API — and active QUIZ_DAY events are the **authoritative source of quiz dates for eligibility**. A guard-bypassed deactivation silently removes a quiz date from every eligibility computation; a duplicate/misdated QUIZ_DAY shifts chronological cycle numbering. (EVT-003)
3. **Integrity guarantees stop at the application layer.** The duplicate guard is check-then-insert with no DB unique constraint (verified live: `academic_events` has only a PK and the subject FK, and **zero indexes**), `class_sessions` has no natural-key unique constraint, and no locks are taken — concurrent mutations can produce duplicate active events and duplicate sessions. (EVT-004, EVT-006)

Live-DB evidence also confirms the two standing notification findings: **452 orphaned ACADEMIC_EVENT rows are still present** (H-4a purge script was never run with `--confirm`; they are hidden by the read filter, not deleted), and the inbox grows without retention (182 ACADEMIC_EVENT rows for a single user; 482 total unread). H-4d is re-confirmed at the current tree: **CLASS_REMINDER generation is unreachable in production** — there is no scheduler anywhere and the regeneration sweep has no production caller.

**No CRITICAL finding.** Three findings are HIGH/MEDIUM-worthy of near-term remediation (EVT-003 HIGH; EVT-001/002/EVT-004/EVT-005 MEDIUM). Several long-standing ambiguities (event ownership, inactive-event visibility, retention) are product decisions, not bugs, and are labeled as such.

---

## 2. Event Architecture / Dependency Map

### 2.1 Write path (student/admin event mutation)

```
Frontend EventFormDialog / Admin dialogs
  ↓  POST|PATCH|DELETE /api/v1/events[/{id}]      (events.py — get_current_user)
  ↓  POST|PATCH|DELETE /api/v1/admin/events[/{id}] (admin.py — require_any_admin)
AdminEventService          (quiz-managed guard — /admin routes ONLY)
  ↓
EventService.create_event / update_event / deactivate_event   (event_service.py)
  ├→ AuthorizationService.assert/can_mutate_event (DB-resolved roles/scopes)
  ├→ event_registry.validate_event                (per-type business rules)
  ├→ EventRepository.exists_active_duplicate      (app-level 409 guard)
  ├→ EventSessionSynchronizer.sync_event          (SAME transaction)
  │    ├→ CalendarRepository.get_all_events(active=True)   ← loads ALL active events
  │    ├→ SessionRepository (span, sessions-in-range, attended-ids)
  │    └→ per-date _desired_schedule (calendar_engine.get_academic_day) → _reconcile_date
  │         ├→ class_sessions  (create/restore/cancel/delete reversible projections)
  │         ├→ occurrence_outcomes (Phase 23.6 per-subject overrides)
  │         └→ ClassSession.designation (MID_SEM_PRACTICAL only)
  ├→ db.commit()  ← event + session effect atomic
  └→ NotificationService.after_event_mutation(event)   ← POST-commit, best-effort,
       create/update ONLY — NOT called by deactivate_event (EVT-001)
```

### 2.2 Read paths (event consumers)

| Consumer | Query | Active filter | Date bound |
|---|---|---|---|
| `GET /api/v1/events` (events.py:21) | `CalendarRepository.get_all_events` | param (`default true`) | optional `date_from`/`date_to`, `upcoming` |
| `GET /api/v1/calendar` month (calendar_service.get_month_view) | same repo | `active=True` | effective month∩semester |
| `GET /api/v1/calendar/today`, `/{date}` (calendar.py) | `get_all_events()` **no filter** | engine filters `e.active` | single day |
| Dashboard summary (dashboard_service.py:108) | `get_all_events(active=True, date_from=min(semester_start, today))` | `active=True` | floor bound |
| Eligibility quiz dates (`QuizRepository.get_effective_quiz_dates_for_subjects`) | **active QUIZ_DAY events are the authority** | `active=True` | none |
| Notification sweep `_academic_events` (notification_service.py:560) | `get_all_events()` | manual `e.active` | none (filters `end_date >= today` in memory) |
| `EventSessionSynchronizer.sync_event` (event_session_service.py:178) | `get_all_events(active=True)` | `active=True` | none (loads ALL active events every mutation) |
| `AdminEventService.list_events` (admin_event_service.py:217) | `get_all_events` + Python-side filters | param | optional |
| `expand_baseline` / scripts | direct | — | — |

### 2.3 Event → notification pipeline

```
EventService.create_event / update_event ──(post-commit)──▶ after_event_mutation(event)
AdminQuizService (quiz manager) ──▶ _retire/_ensure QUIZ_DAY event (NO ACADEMIC_EVENT emission)
                                   └─(post-commit)─▶ _notify_quiz_users → after_quiz_mutation (QUIZ_APPROACHING)
AttendanceService ──(post-commit)──▶ after_attendance_mutation (THRESHOLD/MUST_ATTEND/SAFE_SKIP)
regenerate_user_notifications  ── ◀ NO production caller (manual/ops sweep only; no scheduler exists)
        │
        ▼
NotificationService.emit()  ──▶ NotificationRepository.try_create
        (INSERT … ON CONFLICT (user_id, kind, occurrence_key) DO NOTHING; commit per row)
        ├─ new row  → Web Push side-channel (best-effort)
        └─ existing → refresh message/subject in place (commit), never re-push
Inbox read: notifications WHERE is_dismissed=false AND (event_id IS NULL OR event EXISTS)
```

### 2.4 Complete EventType branch map (18 values)

| Type | Scope | Session effect | Priority | Who can create |
|---|---|---|---|---|
| EXTRA_LECTURE/TUTORIAL/PRACTICAL | subject + class type | +1 extra occurrence (provenance `source_event_id`) | 30 | enrolled student / scoped admin |
| CLASS_CANCELLED | subject + L/T | removes 1 matching occurrence; attended session may be cancelled (the ONE exception) | 30 | enrolled student / scoped admin |
| LAB_CANCELLED | subject + P | removes matching practical; attended labs NEVER cancelled | 30 | enrolled student / scoped admin |
| MID_SEM_PRACTICAL | subject + P | designates occurrence (or materializes 1 extra); "one mid-sem per subject" | 30 | enrolled student / scoped admin |
| SURPRISE_QUIZ | subject + L/T (theory only) | +1 extra occurrence | 30 | enrolled student / scoped admin |
| CLASS_MODIFIED | subject only | `OccurrenceOutcomeType.MODIFIED` outcome on anchor session | 30 | enrolled student / scoped admin |
| QUIZ_DAY | subject | +1 attendance-bearing LECTURE session (Option A) | 30 | admin; quiz-manager events auto-synced |
| HOLIDAY / PUBLIC/INSTITUTE/FESTIVAL_HOLIDAY / EMERGENCY_CLOSURE / SEMESTER_BREAK / MID_SEMESTER_BREAK | global | day → non-working (closure) | 70/50/40/100/60 | HEAD_ADMIN only |
| WORKING_DAY_OVERRIDE | global | `is_working_day` honored when dominant | 90 | HEAD_ADMIN only |
| WORKING_SATURDAY | global | Saturday → working | 80 | HEAD_ADMIN only |

---

## 3. Database / Data Model

### 3.1 `academic_events` (ORM `backend/app/models/event.py`; DDL `alembic/versions/7117a007a0da_initial_schema.py:89-101` + later revisions)

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | UUID PK | no | `uuid4` (ORM) | from `Base` |
| event_type | ENUM eventtype (14→18 values via ALTER TYPE) | no | — | values added by `a1b2c3d4e5f6`, `a7b8c9d0e1f2`, `f8a9b0c1d2e3` |
| start_date / end_date | Date | no | — | **date-only; no time component anywhere** |
| subject_id | UUID FK → subjects.id | yes | — | **no ondelete** |
| elective_slot | ENUM electiveslot | yes | NULL | added by `b7c8d9e0f1a2` (+anchor backfill) |
| class_type | ENUM classtype | yes | — | L/T/P |
| is_working_day | Boolean | yes | — | dominant-event override |
| substitution_schedule_override | String | yes | — | day name, registry-validated |
| note | String (unbounded) | yes | — | added by `a1b2c3d4e5f6` |
| active | Boolean | no | **no server default** (ORM `default=True`) | soft-delete flag |
| created_at/updated_at | timestamptz | no | ORM-side `datetime.now(IST)`; `onupdate` is ORM-only | raw-SQL updates don't bump `updated_at` |

**Live-verified constraints** (§21): only `academic_events_pkey` and `academic_events_subject_id_fkey`. **No unique constraint, no CHECK (`start_date <= end_date`), no index on `start_date`, `subject_id`, `active`, or `event_type`** — the `pg_indexes` probe returned only the PK index. The registry's `start_date > end_date` rule (event_registry.py:230) is application-only.

Related: `class_sessions.source_event_id` FK → `academic_events.id`, **no ondelete**, indexed (`e2f3a4b5c6d7:48-56`) — provenance survives; the FK only blocks hard-deletes of events that still have session provenance (verifiers hard-delete events and must clean sessions first).

### 3.2 `notifications` (`d1e2f3a4b5c6`)

- `event_id UUID NULL` — **deliberately NO FK** (audit trail: `purge_orphaned_event_notifications.py:5`; repo comment `notification_repo.py:34-39`). This is the structural origin of orphaned ACADEMIC_EVENT projections (H-4a).
- Idempotency: `UNIQUE(user_id, kind, occurrence_key)` — DB-enforced; ACADEMIC_EVENT keys on `occurrence_key = str(event.id)`.
- No index beyond the unique constraint's implicit btree; reads always filter by `user_id` (leftmost column — usable).

### 3.3 Model-vs-migration consistency

ORM and migrations agree on all columns/nullability for `academic_events` and `notifications`. Two cosmetic drifts: `Base` declares ORM-side defaults that have no `server_default` (relevant only to raw-SQL writers), and migration `e2f3a4b5c6d7`'s docstring carries a stale revision id. No functional drift found.

### 3.4 Integrity posture vs. service-layer assumptions

| Service assumption | DB enforcement | Verdict |
|---|---|---|
| No duplicate active events (409 guard) | none | **gap** (EVT-004) |
| `start_date <= end_date` | none | gap (validated app-side; low risk) |
| One session per (timetable_entry, date) / one extra per (event, date) | none on `class_sessions` | **gap** (EVT-004) |
| Event row never hard-deleted | soft-delete convention only; scripts CAN hard-delete | held by convention + verifier harness cleanup |
| Notifications reference existing events | none (no FK) | read-filter mitigation only; 452 orphans present (EVT-008) |

---

## 4. Create Flow (`POST /api/v1/events`, `POST /api/v1/admin/events`)

1. **Who:** any authenticated user; authorization inside `EventService.assert_mutation_allowed` (event_service.py:77-119). Admins (legacy `role=ADMIN` → HEAD_ADMIN, or active `admin_scopes`) must pass `can_mutate_event` (authorization_service.py:209-245): global/slot events → HEAD_ADMIN only; subject events → `can_access_subject`. Students: type ∈ `STUDENT_CREATABLE_EVENT_TYPES` (8 flexible types) **and** enrolled in the subject (`EventRepository.is_enrolled`).
2. **Elective-slot resolution first** (event_service.py:127-161): slot events are HEAD_ADMIN-only, mutually exclusive with `subject_id`, and resolve to the shared anchor (BCS-054/BCS-058).
3. **Validation:** `event_registry.validate_event` — start≤end, per-type subject/class-type requirements, allowed class types, substitution day names, quiz types theory-only, closures reject `is_working_day`, WORKING_SATURDAY rejects `is_working_day=false`, HOLIDAY requires a non-blank note (create only — legacy rows stay editable).
4. **Client-trusted fields:** the whole payload shape (`event_type, start_date, end_date, subject_id, elective_slot, class_type, is_working_day, substitution_schedule_override, note, active`). Server-generated: `id`, timestamps. **`active` is client-settable at creation, including `false`** (EVT-010).
5. **Dates normalized?** No transformation — Pydantic `date` parsing of `YYYY-MM-DD`; dates are institution-local by definition (date-only design). No `institution_today()` check → **past-dated events are creatable** (intentional: students record class reality after the fact; see §13 matrix row P3).
6. **Duplicate guard:** `exists_active_duplicate` on (type, subject, class_type, start, end) among ACTIVE rows → 409. Check-then-insert; no DB constraint/lock (EVT-004).
7. **Transaction:** `flush → sync_event → commit` with rollback on any exception (event_service.py:243-252) — event + session effects atomic.
8. **Notifications:** post-commit `after_event_mutation` — best-effort, fully isolated; failures are logged and never affect the event result (event_service.py:255-263). Recipients: enrolled users (subject event), slot-choosers + anchor-enrolled (slot event), **all users** (global event — `get_all_user_ids`, user_repo.py:127-131). Past/inactive events emit nothing.
9. **Retry behavior:** retried create with identical payload → 409 (duplicate guard). Notification emission is idempotent per (user, kind, event-id); retries never duplicate rows or pushes (emit → try_create ON CONFLICT DO NOTHING).

Admin portal adds the **quiz-managed guard** (409 for QUIZ_DAY configurations backed by a SCHEDULED QuizSchedule). **This guard does not exist on the canonical `/api/v1/events` endpoints** (EVT-003).

## 5. Read / Visibility Flow

- **`GET /api/v1/events`** (events.py:21-74): any authenticated user; **every event in the DB matching the filters is returned — there is no enrollment/section scoping at the DB or service layer** (students see other subjects'/sections' extras; see Decision D3). `active` defaults true; `active=false` exposes **inactive (soft-deleted) events to any user** (Decision D2). Range-overlap filters are inclusive on both bounds (`end_date >= date_from AND start_date <= date_to` — calendar_repo.py:34-37). `upcoming=true` = `end_date >= institution_today()` (institutional clock, not per-user browser time — correct).
- **Ordering:** `ORDER BY start_date` only — **ties are non-deterministic** (Postgres heap order). Frontend re-sorts client-side, so user impact is nil today; API consumers must not assume stable order (folded into EVT-007).
- **Pagination:** none. Whole-table reads on every events-page load and every event mutation (`sync_event` re-loads all active events) (EVT-007 / EVT-006).
- **No single-event GET exists on `/api/v1/events`** — there is no IDOR read surface. `GET /api/v1/admin/events/{id}` is admin-gated and scope-checked (`_visible`, admin_event_service.py:191-199; out-of-scope → 404, no existence leak).
- **Elective resolution** (ElectiveResolver.resolve_events) is non-mutating and per-user; `resolved_subject_*` is computed for every response. Slot events resolve to the student's chosen subject, else the anchor — never another student's choice.
- **IDOR/BOLA reasoning:** mutations are the only by-ID surface. A student mutating an event by ID is authorized by (event_type, subject enrollment) — not by ownership, because **no ownership exists** (Decision D1). A student cannot reach global/slot events (authorization on existing state first — event_service.py:271-275). Admin detail/list are scope-filtered. No cross-user read of private data exists because events have no private data — they are globally shared academic facts by design.
- **Deleted events:** inactive events are excluded from engine day resolution (`get_academic_day` filters `e.active`, calendar_engine.py:80), from dashboard/calendar/notification projections, and from the duplicate guard; they remain readable via `?active=false` (D2) and remain the target of `PATCH {"active": true}` reactivation (D1/EVT-014).
- **Month boundaries:** `CalendarService._month_bounds` computes real month ends (incl. leap years via `date` arithmetic); the month is clamped to the semester with a truthful empty result when disjoint. No off-by-one observed.

## 6. Update Flow (`PATCH /api/v1/events/{id}`, `PATCH /api/v1/admin/events/{id}`)

- Authorization runs **twice**: on the existing state (a student may not touch a global event even to "fix" it) and on the final state after fields are applied (a student cannot move an event to an un-enrolled subject or to a non-creatable type) — event_service.py:271-330. Both checks pass before any flush/commit; exceptions leave nothing persisted.
- Partial semantics via `model_fields_set` — absent = unchanged; explicit nulls re-scope. This tolerates both the student dialog's full-object PATCH and the admin dialog's sparse-diff PATCH (frontend contract verified).
- Slot-state invariants re-enforced on update (anchor resolution, HEAD_ADMIN gate, subject/slot mismatch rejected).
- Span-union reconciliation: `sync_event(span_override=(min(old,new), max(old,new)))` — dates the event left are restored, dates it newly covers are reconciled (event_service.py:356-364). Verified convergent by `verify_cancellation_lifecycle_consistency.py`.
- **Type changes are unrestricted for admins** (registry-validated, duplicate-checked): e.g. EXTRA_LECTURE → HOLIDAY, or → QUIZ_DAY. On the admin portal the QUIZ_DAY prospective guard only runs when the **old** type is QUIZ_DAY (admin_event_service.py:272) — a type-change into a quiz-managed configuration is not prospectively blocked there either, and on `/api/v1/events` nothing blocks it at all (EVT-003).
- **Notification side effects:** `after_event_mutation` runs post-commit, but (a) it early-returns when the event is now past (`end_date < institution_today`, notification_service.py:311) — so moving future→past leaves the old "…on &lt;future date&gt;" row untouched (EVT-002); (b) it never deletes rows for events that stopped being notify-worthy; (c) when it does run, the row is refreshed in place (message/date-of-row semantics preserved: `date` stays the **first-generation** value per the upsert contract — an event re-dated later keeps its original row `date` while the message text updates).
- Moving future→future correctly refreshes the message. Only title-like state exists (type/note); a note-only change does not emit anything (message contains no note — cosmetic).

## 7. Delete Flow (`DELETE /api/v1/events/{id}`)

- **Soft delete only**: `active=False`, row preserved (ADR 004; no hard-delete requirement anywhere in the app). Re-enable via `PATCH {"active": true}`.
- Authorization identical to other mutations (existing-state check; students limited to their enrolled subjects' flexible events).
- Reconciliation **always runs — even when the event was already inactive** (self-healing; verified by `verify_cancellation_lifecycle_consistency.py`).
- Session effects of deactivation: unattended extras deleted; attended extras preserved with `is_deactivated=True`; cancellation-restores; quiz-day unattended sessions deleted; outcomes removed; designation cleared. All state-based and idempotent.
- **What does NOT happen: notification cleanup.** `deactivate_event` (event_service.py:381-414) is the only mutation with no `after_event_mutation` call and no compensating delete of ACADEMIC_EVENT rows → every recipient keeps a live inbox row announcing a withdrawn event (EVT-001). The H-4a read-filter does not help: the event row still EXISTS, so `_live_event_ref_clause` (notification_repo.py:48-60) still passes.
- Orphan notifications from *hard* deletion cannot be produced by the app (no hard-delete path exists in `EventRepository`/service layer). They were produced historically by verifier scripts hard-deleting events; the shared harness now cleans fixture notifications (`_verifier_harness.py:49-104`) — but the **452 legacy rows remain in the dev DB** (EVT-008; purge script unrun).

## 8. Date / Timezone Analysis

**Design: events are `Date`-only.** There is no time-of-day, no datetime, and therefore no UTC/local conversion anywhere in the event pipeline (model → Pydantic `date` → SQLAlchemy `Date` → PostgreSQL `date` → JSON `YYYY-MM-DD` → frontend `input[type=date]`).

- **Clock:** the single authoritative "today" is `institution_today()` = `datetime.now(ZoneInfo(settings.INSTITUTION_TIMEZONE))` with `INSTITUTION_TIMEZONE=Asia/Kolkata` (app/core/timezone.py). Used by `upcoming`, notification `as_of`, and emission windows. Server TZ and browser TZ are irrelevant to event semantics — correct and deliberate.
- **Frontend:** parses `value + "T00:00:00"` at **local** midnight explicitly "so the displayed calendar date can never shift by a day" (frontend/src/lib/date.ts:8-12); all comparisons are lexicographic `YYYY-MM-DD` strings. **No `toISOString()` anywhere** in the frontend date path — the classic UTC-shift off-by-one is structurally excluded.
- **DST:** Asia/Kolkata has no DST; no DST handling is needed or present. Not a risk.
- **Midnight/IST boundary:** `upcoming` and notification windows flip at IST midnight, uniformly for all users (institution clock). A user in any other TZ sees identical semantics — consistent, not buggy.
- **Inclusive/exclusive:** event ranges are inclusive on both ends everywhere (engine filter `start <= d <= end`, repo overlap filters, frontend grouping).
- **All-day semantics:** every event is all-day by construction; `session_count` and engine resolution are date-granular.
- **Timestamps:** `created_at/updated_at` are `timestamptz` written with IST-aware values; notification row `date` = event `start_date` (institution-local). No naive/aware mixing found in the event paths.
- **Conclusion: no off-by-one-day bug exists in the Events date pipeline.** The only date-boundary sensitivity is *which date is "today"* — answered by the institution clock everywhere (verified in calendar_repo, notification_service, dashboard_service, attendance_service).

## 9. Notification / Reminder Integration

Established causal relationships with the prior audit findings (per instructions, derived from code, not assumed):

| Prior finding | Current-truth relationship to Events |
|---|---|
| **H-4a** 452 orphaned ACADEMIC_EVENT rows | **Not created by app paths.** The app never hard-deletes events; orphans came from legacy verifier runs hard-deleting events. Verifier harness now deletes fixture notifications (`_verifier_harness.py:3-11, 49-104`) and asserts zero orphans after cleanup. **The 452 legacy rows are still in the dev DB** — `purge_orphaned_event_notifications.py` (dry-run default, refuses production) has never been run with `--confirm`. Read layers hide them (inbox/badge use `_live_event_ref_clause`). **The Events system can still produce *soft-stale* live rows** (EVT-001/002) which no filter removes. |
| **H-4b** verifier cleanup | Fixed (harness). Confirmed in code and by live orphans matching exactly the pre-harness baseline (452). |
| **H-4c** retention/pagination | Pagination fixed (clamped 1..200, bounded SQL, additive metadata — notification_repo.py:14-30, get_inbox/count_inbox/count_unread all bounded and orphan-filtered). **Retention deliberately NOT implemented** (comment notification_repo.py:16-19 — no documented policy; product decision D5). Growth is real: 182 ACADEMIC_EVENT rows for a single dev user; 482 total unread. |
| **H-4d** CLASS_REMINDER unreachable | **Still true; not an Events defect.** No scheduler/background infra exists at all (no APScheduler/Celery/startup task; `app/main.py` has no lifespan — verified by grep and full read). CLASS_REMINDER is computed only in `_class_reminders` (notification_service.py:453-479), reachable only via `regenerate_user_notifications`, whose only caller is `scripts/verify_phase_11c_p4.py` (P8 regression). Production triggers emit QUIZ_APPROACHING / THRESHOLD / MUST_ATTEND / SAFE_SKIP / ACADEMIC_EVENT — never CLASS_REMINDER (EVT-005). |
| **H-5** quiz chronology | Fixed in the quiz-manager path (`_validate_cycle_chronology` before any side effect, admin_quiz_service.py:466-473). The quiz-date *authority* is active QUIZ_DAY events ranked chronologically (quiz_repo.py:48-68) — which is exactly what the EVT-003 guard bypass corrupts. |
| **H-2** deactivated-user tokens | All events endpoints authenticate via `get_current_user`, which enforces the `is_active` kill switch (deps.py, H-2 comment block). Events system is covered. |

**Emission mechanics:** `emit()` → `try_create` (INSERT … ON CONFLICT DO NOTHING, per-row commit) → push only for genuinely new rows; existing rows refreshed in place without re-push. Duplicate prevention is DB-enforced and race-free **per (user, kind, occurrence_key)**. A global event broadcast commits once per recipient (~N commits, sequential); a failure mid-broadcast leaves partial delivery (best-effort by design; EVT-012).

**Reconciliation between trigger and sweep:** the trigger message has no subject prefix; the sweep projection adds one (`_event_message`). Since upserts refresh the message, a row's text flips depending on which path last ran (EVT-I1).

## 10. Authorization / Security

Per endpoint:

| Endpoint | Auth | Role | Object-level check |
|---|---|---|---|
| `GET /events` | JWT + `is_active` | any user | none (global read — D3) |
| `POST /events` | JWT | service-enforced (admin matrix / student enrollment) | `assert_mutation_allowed` ×1 (+ slot HEAD gate) |
| `PATCH /events/{id}` | JWT | service-enforced ×2 (existing + final state) | type+enrollment on both states |
| `DELETE /events/{id}` | JWT | service-enforced | type+enrollment |
| `GET/PATCH/DELETE /admin/events/{id}` | `require_any_admin` (DB-resolved) | scope matrix (`_visible`, `can_mutate_event`) | per-object scope; 404 for out-of-scope |
| `POST /admin/events` | `require_any_admin` + EventService matrix | HEAD for global; scoped admins per subject | quiz-managed 409 guard |

- **No client-supplied identity anywhere**: owner/actor is always the JWT-resolved user; `subject_id` is scope-checked, never trusted (Phase 23.11 doctrine, verified in code).
- **Mass assignment:** the create schema accepts `active` (incl. `false`) and every optional field from students — bounded impact (an inactive event is inert), but it is client-trusted state with no need to be (EVT-010).
- **Privilege escalation:** none found. Scoped admins (CLASS/ELECTIVE) are denied global events and slot events (`can_mutate_event` requires HEAD_ADMIN when `subject_id is None` or slot set; `is_head_admin` re-checked on the slot path). SUBSECTION_ADMIN is conservatively inert (denies).
- **The one substantive hole is EVT-003** (quiz-managed guard not enforced in `EventService`) — it is a *policy* bypass by an authenticated admin, not an authentication failure.
- No injection surface: all queries are parameterized SQLAlchemy/`pg_insert`; the raw-SQL forensics scripts are SELECT-only.

## 11. Transactions / Concurrency

- **Event + session effect are atomic**: single `commit()` in each service mutation with rollback-on-exception; the synchronizer only flushes, never commits (verified: no `commit` in event_session_service.py / session_repo.py).
- **Notifications are intentionally outside the transaction** (post-commit, isolated, never raise). Consequence: an event can persist with zero notifications if the trigger fails (logged only) — accepted design; the reverse (notification without event) cannot happen because emission happens after commit.
- **Quiz-manager mutations are atomic** too: schedule changes + `_retire_quiz_event` + `_ensure_quiz_event` + `sync_event` commit once (admin_quiz_service.py:474-478), notifications after.
- **Missing concurrency controls (EVT-004):**
  - duplicate guard = check-then-insert, no `SELECT … FOR UPDATE`, no unique index → two concurrent identical POSTs both succeed;
  - `_reconcile_date` decides creations from a pre-loaded snapshot; `class_sessions` has **no** unique constraint on (timetable_entry_id, date) or (subject_id, date, class_type, is_extra) → two concurrent event mutations overlapping the same date can both create the same scheduled/extra/quiz-day session;
  - no version/locking on event rows → last-writer-wins on concurrent PATCHes (state-based reconciliation is self-healing for session state, but the event row itself is not);
  - `find_quiz_day_event`/`_retire_quiz_event` take no lock and use `.first()` without ORDER BY (EVT-009) — under duplicates the retire path deactivates an arbitrary one.
  - Mitigating context: single-process dev deployment, low write concurrency, and the reconciler's idempotency makes most races *eventually* converge on the next mutation touching the same date. Severity stays MEDIUM (integrity guard absent), not HIGH.

## 12. Frontend / Backend Contract

Verified field-by-field (frontend map in §Appendix source: agent report with file:line evidence):

- **Types match.** `AcademicEventResponse` (TS) has exactly the backend response fields; `resolved_subject_*`/`elective_slot` always emitted by the resolver. `EventType`/`ClassType`/`ElectiveSlot` unions match the Python enums (TS carries legacy `PRACTICAL2="P2"` that the backend never returns; no rule can emit it).
- **Date contract:** both sides use bare `YYYY-MM-DD`; single-day = `start_date === end_date` on both sides. Backend PATCH accepts both full-object (student dialog) and sparse-diff (admin dialog) payloads via `model_fields_set` — correct.
- **Frontend sends fields the backend ignores:** none — every sent field is consumed. Backend returns fields the frontend ignores: `is_working_day` (list row), `subject_id`, `elective_slot`, `resolved_subject_id` (guard-present but unused), day-level `day_type`, `original_day_of_week`, `effective_start/effective_end`; `EventsParams.upcoming` is dead (never sent); `useCalendarDay` (`GET /calendar/{date}`, incl. `/today`) has **zero frontend consumers**; `NotificationItem.event_id` never consumed (no deep link possible — INFO).
- **Enum drift:** none.
- **Admin manager contract:** `AdminEventResponse.quiz_schedule_managed / target_summary / subject_slot / can_mutate` are all server-computed and all consumed by the admin UI (including the Edit-button gate on `can_mutate`).
- **Cache/refresh asymmetry:** the tools page invalidates only the current month's `/calendar` key after a mutation; other months can be stale up to the 5-min SWR dedupe window. A push notification refresh updates only the inbox key — the events/calendar views are not refreshed by event pushes. (Frontend behavior; noted for completeness.)
- **Error contract:** backend raises `HTTPException(detail=str)` for 403/404/409/422; frontend `apiFetch` surfaces `detail` directly and preserves `error.status`. Matches (the structured `{message, conflicts}` parsing path is unused by events).

## 13. Edge-Case Matrix

| # | Case | Current behavior | Intentional? | Defect |
|---|---|---|---|---|
| N1 | Normal future event | created; sessions reconciled; notifications emitted to recipients | yes | — |
| N2 | Today's event | `upcoming` includes it (`end >= today`); notification emitted (end_date == today) | yes | — |
| P1 | Past event (start<end<today) | creatable (no past check); appears in lists/engine; **no session materialization if outside baseline span**; no notifications | yes (creation) / documented (span) | see EVT-011 |
| P2 | All-day / date-only | every event is all-day; no time fields exist | yes | — |
| P3 | Event created in the past | allowed by design (students record reality; admins correct history) | yes (decision) | — |
| E1 | start == end | valid single-day; frontend treats as single-day | yes | — |
| E2 | end < start | 422 (registry line 230); no DB CHECK | yes (app-level) | low |
| E3 | start > end via PATCH | same 422 (final-state validation) | yes | — |
| D1 | Duplicate event (same natural key) | 409 via app guard; **race can double-create** | guard intentional | EVT-004 |
| D2 | Duplicate active QUIZ_DAY same subject/date | quiz-day bucket dedupes to ONE session; eligibility dedupes per (subject,date) | partially | harmless for sessions; shifts nothing |
| D3 | Duplicate QUIZ_DAY **different dates** | eligibility cycles shift chronologically (authority = events) | by design, dangerous via bypass | EVT-003 |
| U1 | Event edited after reminders created | row refreshed in place (future→future); no re-push | yes | — |
| U2 | Event edited future→past | trigger skips; stale future-dated row stays live | no | **EVT-002** |
| U3 | Only note/type changed | no notification refresh (message has no note); type change re-validated; sessions re-reconciled over span union | yes | — |
| X1 | Event deleted after reminders | notifications stay live (event row exists) | no | **EVT-001** |
| X2 | Event deactivated already-inactive | reconciliation still runs (self-healing) | yes | — |
| M1 | Future→past move | as U2 | no | EVT-002 |
| M2 | Past→future move | trigger emits (event now future); new notifications; old none existed | yes | — |
| A1 | Admin-created global event | broadcast to **all users** (docstring says "ADMIN-only" — ambiguous) | behavior plausible, doc wrong | EVT-I2 / D4 |
| S1 | Student mutates another's subject event | allowed (no ownership) | decision | D1 |
| S2 | Unauthorized user (not enrolled / wrong type) | 403 on both existing and final state | yes | — |
| S3 | Nonexistent event | 404 (no existence leak on admin detail; 404 on student paths) | yes | — |
| S4 | Deleted (inactive) event mutation | PATCH/DELETE still authorized by type+enrollment; reactivation allowed | decision | EVT-014 |
| NF1 | Notification creation fails | event persists; failure logged; no push; partial broadcast possible per-row | yes (best-effort) | EVT-012 |
| NF2 | Duplicate notification attempt | ON CONFLICT → refresh, no duplicate row, no re-push | yes | — |
| TZ1 | IST midnight boundary | institution clock flips uniformly; date-only fields unaffected | yes | — |
| TZ2 | Browser TZ ≠ IST | no effect anywhere (date-only + institution clock) | yes | — |
| L1 | Empty title/description | no title field exists; `note` may be empty (except HOLIDAY create → 422) | yes | — |
| L2 | Very long note/override | no backend cap (frontend 200 chars advisory) | no | EVT-010 |
| PG1 | Pagination boundary | **no pagination on /events**; inbox clamped 1..200 with metadata | inbox yes; events no | EVT-007 |
| O1 | Multiple events, same timestamp | date-only: same-day events coexist; day dominance = priority sort with input-order tiebreak (engine) vs id tiebreak (synchronizer) | partially | EVT-013 |

## 14. Confirmed Findings

### EVT-001 — Deactivating an event leaves stale **live** ACADEMIC_EVENT notifications
- **Severity:** MEDIUM · **Category:** Notification lifecycle / data integrity · **Status:** Confirmed
- **Location:** `backend/app/services/event_service.py:381-414` (`deactivate_event` — no notification call) vs `:255-263` and `:369-378` (create/update both call `after_event_mutation`); `backend/app/repositories/notification_repo.py:48-60` (read filter checks existence only, not `active`); `backend/app/services/notification_service.py:294-350` (no deletion path exists for ACADEMIC_EVENT rows).
- **Explanation:** the only lifecycle hooks that touch ACADEMIC_EVENT rows are create/update emissions. Deactivation triggers neither a refresh nor a delete, and no sweep deletes stale rows (the sweep only upserts). Because events are soft-deleted, the event row still exists, so the read-layer guard keeps the rows visible forever.
- **Evidence:** code paths above; live DB shows `notif_event_refs_inactive = 0` only because the dev dataset currently has no deactivated events carrying notifications (all 18 events are active) — the class of rows the audit script `notif_event_refs_inactive` was written to look for is exactly this defect's output.
- **User impact:** after a student/admin withdraws an extra class or a date change, every recipient's inbox (and unread badge) continues to announce the event. Only manual dismissal removes it.
- **Reproduction:** create future EXTRA_LECTURE (recipients get notifications) → DELETE the event → `GET /notifications` still returns "Extra Lecture on …" as live/unread.
- **Remediation (recommended, not implemented):** call a compensating notification hook in `deactivate_event` (and on future→past moves) that either deletes the (kind=ACADEMIC_EVENT, occurrence_key=event.id) rows or marks them dismissed; alternatively extend `_live_event_ref_clause` to also require `event.active`. Code-only; no migration required (an index on `notifications.event_id` would make either path cheap — the unique constraint's index cannot serve `event_id IS NOT NULL` lookups efficiently).
- **Dependencies:** none; pairs with EVT-002 (same remediation site).

### EVT-002 — Event moved future→past leaves a stale future-dated notification
- **Severity:** MEDIUM · **Category:** Notification lifecycle · **Status:** Confirmed
- **Location:** `backend/app/services/notification_service.py:309-312` (`after_event_mutation` early-returns when `event.end_date < institution_today()`); `backend/app/services/event_service.py:369-378` (update path calls it unconditionally, but the trigger self-skips).
- **Explanation:** an event created for a future date emits "…on &lt;date&gt;". A later PATCH moving it into the past (e.g. a correction) makes the trigger return before emitting/refreshing, so the original row keeps announcing the old future date. `date` on the row is first-generation anyway (upsert contract), so even a refresh could not fix the displayed semantics — deletion/dismissal is the only correct outcome.
- **Evidence:** code paths; same class as EVT-001 (shared remediation).
- **Impact:** inbox announces an event on a date it did not (or no longer) occurs; quiz-day variants can mislead students about quiz dates (though eligibility itself reads events, not notifications).
- **Remediation:** same hook site as EVT-001: on update, when the event became past/inactive, remove or dismiss its ACADEMIC_EVENT rows. No migration.

### EVT-003 — Quiz-schedule-managed QUIZ_DAY guard is endpoint-scoped and bypassable; quiz-date authority can be desynchronized
- **Severity:** HIGH · **Category:** Authorization / data integrity (guard bypass) · **Status:** Confirmed
- **Location:** guard exists only in `backend/app/services/admin_event_service.py:95-123, 247-302` (used by `/api/v1/admin/events` routes, admin.py:885-990). The canonical endpoints `backend/app/api/v1/endpoints/events.py:77-156` call `EventService` directly with **no quiz-managed check**; `EventService` itself has none. Additional admin-portal gap: the prospective PATCH check runs only when the *old* type is QUIZ_DAY (`admin_event_service.py:272`), so a type-change into a managed configuration is not blocked there either.
- **Explanation:** Phase 24.9 declares quiz-schedule-backed QUIZ_DAY events untouchable through the event manager ("must NOT be created, edited, or deactivated … would desynchronize quiz schedule reality" — admin_event_service.py:10-18). The enforcement lives at one consumer, not in the domain service, so the identical mutation performed through the documented `/api/v1/events` PATCH/DELETE succeeds:
  - `DELETE /api/v1/events/{quiz_managed_id}` → `active=false`. Quiz dates are read from **active** QUIZ_DAY events (`quiz_repo.get_effective_quiz_dates_for_subjects`, quiz_repo.py:48-68) → the quiz date silently disappears from every eligibility computation while the SCHEDULED QuizSchedule row still exists (the quiz manager believes the event is live; `_retire_quiz_event` identity now matches nothing active).
  - `PATCH /api/v1/events/{id}` setting `event_type=QUIZ_DAY`, `subject_id`, `start_date` onto a schedule-backed configuration → creates a *second* event at the schedule's identity (the duplicate guard does not compare elective slot/managed state, and `find_quiz_day_event` uses `.first()`), or shifts chronological cycle numbering when dated elsewhere — both corrupt eligibility windows (Criterion I/II boundaries derive from ranked quiz dates).
- **Evidence:** code paths above; H-5 chronology protection exists only in `AdminQuizService.update_quiz_schedule` (admin_quiz_service.py:466-473), i.e. the same one-layer pattern.
- **Impact:** silent corruption of quiz eligibility (core product feature) through API calls the frontend never makes but the contract allows; recoverable by reactivating/correcting events but with no detection mechanism.
- **Reproduction (conceptual, non-destructive):** as an admin, `DELETE /api/v1/events/{id}` on a `quiz_schedule_managed=true` event → 200 (while `/api/v1/admin/events/{id}` DELETE → 409 for the same row).
- **Remediation:** move the guard into `EventService` (check `QuizSchedule` backing inside `create_event/update_event/deactivate_event`) or into shared service-level validation so **every** endpoint inherits it; add the type-change prospective check. Code-only; no migration.
- **Dependencies:** none. Recommended order: first (highest impact per effort).

### EVT-004 — Duplicate/integrity guards are application-only: no unique constraints, no locks
- **Severity:** MEDIUM · **Category:** Concurrency / data integrity · **Status:** Confirmed (guard absence verified in code + live catalog)
- **Location:** `backend/app/repositories/event_repo.py:66-98` (check-then-insert guard, no FOR UPDATE); `backend/app/services/event_session_service.py:523-806` (snapshot-based reconciliation, no locking); DDL: `7117a007a0da_initial_schema.py` (`academic_events` — no unique/index; `class_sessions` — no natural-key unique); live `pg_constraint`/`pg_indexes` probes (§21).
- **Explanation & trigger:** two concurrent identical POSTs both pass `exists_active_duplicate` → duplicate active events (which then materialize **two** extra occurrences for the same (subject, class_type, date) — the reconciler counts both events as desired). Two concurrent event mutations overlapping one date can both create the same `class_sessions` row shape (no unique constraint blocks it). Concurrent PATCHes last-writer-wins.
- **Impact:** duplicate occurrences inflate attendance opportunities (a student could be marked present twice for one real class) until the next reconciling mutation collapses them; duplicate QUIZ_DAY events shift eligibility ranking.
- **Remediation (recommended):** partial unique index on `academic_events (event_type, subject_id, class_type, start_date, end_date) WHERE active` (NULLs already compare distinctly in PG — matches the guard's null handling) + unique index on `class_sessions (timetable_entry_id, date)` (partial `WHERE timetable_entry_id IS NOT NULL`) and on `(source_event_id, date) WHERE source_event_id IS NOT NULL`; treat constraint violations as 409. **Migration required** (the only finding needing one); also the only one with a real deadlock/perf review step.

### EVT-005 — CLASS_REMINDER generation is unreachable in production (H-4d re-confirmed; not an Events defect)
- **Severity:** MEDIUM · **Category:** Notification architecture · **Status:** Confirmed
- **Location:** no scheduler anywhere (verified: `app/main.py` has no lifespan/background tasks; grep for `APScheduler|celery|cron|create_task|repeat_every` across `app/` = 0 hits; requirements.txt has neither). Sweep `regenerate_user_notifications` (notification_service.py:376-403) has **no production caller** — only `scripts/verify_phase_11c_p4.py`. `_class_reminders` is reachable solely through the sweep.
- **Impact:** the class-reminder preference (user preference exists, `pref.class_reminders`) silently does nothing; users never receive class reminders.
- **Causal relationship to Events:** none — events neither generate nor block CLASS_REMINDER. The Events-triggered kinds (ACADEMIC_EVENT) and the other mutation-triggered kinds work; CLASS_REMINDER is the only kind with **no** mutation trigger, hence dead.
- **Remediation (decision + code):** either add a daily startup/async task calling the sweep for opted-in users, or add a request-time trigger near the day boundary; else remove the dead preference to stop advertising a non-feature. Product decision first (D7-adjacent).

### EVT-006 — `academic_events` has zero secondary indexes
- **Severity:** LOW (current data volumes are tiny — one semester) · **Category:** Performance / schema · **Status:** Confirmed (live `pg_indexes` probe: only the PK)
- **Location:** initial schema + all revisions (no `create_index` targets `academic_events`); hot paths: `get_all_events` (every dashboard/calendar/notification/eval read — full scan + in-memory date filtering), `exists_active_duplicate` (per mutation), `sync_event` (loads ALL active events on every mutation, then filters dates in Python).
- **Impact:** none measurable today (18 rows); linear degradation with data growth. The `sync_event` whole-table load is the one worth revisiting first (it needs only events overlapping the span — a `date_to` bound exists in the repo API already).
- **Remediation:** index `(start_date)`, `(subject_id)`, and optionally `(event_type) WHERE active`; bound the synchronizer's event fetch to the span. Code + optional migration.

### EVT-007 — `GET /api/v1/events` is unbounded and unordered deterministically
- **Severity:** LOW · **Category:** API robustness · **Status:** Confirmed
- **Location:** `backend/app/repositories/calendar_repo.py:31-41` (`ORDER BY start_date` only; no LIMIT), `backend/app/api/v1/endpoints/events.py:21-74` (no pagination params; frontend always fetches all).
- **Impact:** response grows with the event table; ordering ties are non-deterministic. Same query is re-issued by `sync_event` on every mutation.
- **Remediation:** add optional `limit/offset` (mirror inbox clamping) and a deterministic tiebreak (`ORDER BY start_date, id`); keep backward compatibility by defaulting to unbounded.

### EVT-008 — 452 orphaned ACADEMIC_EVENT rows remain in the dev DB (H-4a cleanup pending)
- **Severity:** LOW (read-mitigated) · **Category:** Data hygiene · **Status:** Confirmed (live probe)
- **Location:** DB state; purge tooling exists: `backend/scripts/purge_orphaned_event_notifications.py` (dry-run default; refuses `APP_ENV=production`; deletes exactly `orphaned_event_ref_clause()` rows).
- **Evidence:** `notif_event_refs_missing = 452`; `ACADEMIC_EVENT` total = 452 with 18 events in the table and 0 inactive refs → **100% of ACADEMIC_EVENT rows are orphans**; per-user distribution 182/182/88; row dates 2026-10-05..2026-11-26 (stale quiz-date projections).
- **Impact:** none user-visible (filtered everywhere: inbox, badge, total); dead rows and misleading forensics until purged.
- **Remediation:** run the existing script with `--confirm` on dev; decide the production story (it refuses there by design). Ops action, no code.

### EVT-009 — Quiz-event identity lookup is non-deterministic under duplicates
- **Severity:** LOW · **Category:** Correctness under anomaly · **Status:** Confirmed (code), latent (requires EVT-004 to matter)
- **Location:** `backend/app/repositories/admin_quiz_repo.py:161-184` (`.first()` without ORDER BY) used by `_retire_quiz_event`/`_ensure_quiz_event` (admin_quiz_service.py:305-361).
- **Impact:** with duplicate active QUIZ_DAY events at one identity, retire/ensure act on an arbitrary row; the schedule can end up "retired" while a duplicate stays active (eligibility still counts it).
- **Remediation:** deterministic `ORDER BY id` + rely on the EVT-004 unique index; optionally assert uniqueness here.

### EVT-010 — Unbounded client-trusted fields; `active` accepted at creation
- **Severity:** LOW · **Category:** Input hardening / mass assignment · **Status:** Confirmed
- **Location:** `backend/app/schemas/calendar.py:31-48` (`note`, `substitution_schedule_override` unbounded strings; `active: bool = True` client-settable); frontend caps note at 200 chars (`EventFormDialog.tsx:524-534`) — advisory only.
- **Impact:** oversized notes stored/served verbatim to every enrolled user's client (including into notification-adjacent surfaces? No — notifications compose from type/date only); `active=false` on create creates an invisible-but-real event.
- **Remediation:** `max_length` on the schema fields (Pydantic), server-side clamp or reject; consider ignoring `active` on create (or admin-only).

## 15. Potential Risks

### EVT-011 — Out-of-span events: calendar-visible, session-less (quiz-day variant is eligibility-visible but unmarkable)
- **Severity:** MEDIUM (potential) · **Status:** Potential (requires ops action to trigger; currently no such rows — live span 2026-07-15..2026-12-31 vs events 2026-08-24..2026-10-26)
- **Location:** `backend/app/services/event_session_service.py:173-206` (reconciliation bounded to `get_session_date_span()`; `start > end → return`); `backend/app/repositories/quiz_repo.py:48-68` (eligibility reads ALL active QUIZ_DAY events regardless of span).
- **Explanation:** an event dated outside the baseline session span (e.g. a QUIZ_DAY after `max(class_sessions.date)`, or before its min) affects calendar/day resolution but materializes **no** session. For QUIZ_DAY that means: eligibility counts the quiz date (windows derive from it) while no attendance-bearing quiz-day session exists — students cannot mark quiz attendance for it, and "expected vs actual" counts diverge.
- **Trigger:** admin schedules a quiz beyond the expanded baseline window (plausible near semester end when `expand_baseline` hasn't been re-run).
- **Remediation direction:** validate quiz/event dates against the session span at mutation time (422 or explicit warning), or re-expand the baseline automatically. Decision + code.

### EVT-012 — Per-row notification commits → partial broadcast; refresh path commits the shared session
- **Severity:** LOW (potential) · **Status:** Potential
- **Location:** `notification_repo.try_create/upsert` (commit per row, notification_repo.py:124-127, 317-322); `NotificationService.emit` refresh path `await self.db.commit()` (notification_service.py:203-208).
- **Explanation:** a global-event broadcast loops `emit` per user — a failure mid-loop leaves some users notified, others not (logged only; acceptable for best-effort but undocumented). The refresh-path `commit()` would prematurely commit any in-transaction caller's work — safe today because every caller is post-commit, fragile for future callers.
- **Remediation:** batch `upsert_many` for broadcasts (it exists and commits once — `upsert_many` is currently used by the old generation path only); document/avoid mid-transaction `emit`.

### EVT-013 — Two different same-priority tiebreak rules (engine vs synchronizer)
- **Severity:** LOW (potential) · **Status:** Potential
- **Location:** `calendar_engine.get_academic_day:81` (dominant event = `sorted_events[0]` by priority only — input-order tiebreak; input is `get_all_events` ordered by `start_date`, ties unresolved) vs `event_session_service._desired_schedule:359-363` (priority + `str(event.id)` tiebreak).
- **Impact:** when two same-priority events overlap a day (e.g. two holidays, or a WORKING_SATURDAY range overlapping another range event), which one is "dominant" (carries `is_working_day`/substitution) is not guaranteed consistent between the day-resolution layer and the session reconciler, nor across runs. No current data exhibits this; frontend shows `day.events[0]` reason labels that could flicker.
- **Remediation:** single shared comparator (priority, then id) in the engine.

### EVT-014 — Student reactivation of admin-deactivated subject events (incl. attended-extra revival)
- **Severity:** LOW (potential) · **Status:** Potential / product question
- **Location:** `PATCH /api/v1/events/{id}` with `{"active": true}` — student authorization passes for flexible types on enrolled subjects regardless of who deactivated it (no ownership; D1). On reactivation the synchronizer's identity pass flips preserved `is_deactivated` attended extras back to active (event_session_service.py:645-647) — their attendance records count again.
- **Impact:** an admin's withdrawal of a wrong extra can be undone by any enrolled student; attended-but-withdrawn occurrences return to the denominator.
- **Remediation/decision:** if admin-deactivation should be sticky for non-admins, record the actor (needs an ownership/audit column — related to D1) or restrict `active=true` transitions to admins.

## 16. Product / Design Decisions Required

- **D1 — Event ownership.** `academic_events` has **no `created_by`/owner column** (verified model + migration). Any enrolled student may edit/deactivate/reactivate any flexible-type event for their enrolled subjects, including ones created by other students or by admins. This matches the "students record class reality" spec but has no audit trail. Decide: keep shared-reality model (document it) vs. add ownership/actor tracking (overlaps EVT-014).
- **D2 — Visibility of inactive events.** `GET /events?active=false` returns soft-deleted events to **any** authenticated user (any subject). Decide whether inactive events are public history or admin-only.
- **D3 — Enrollment scoping of `/events`.** All events (all subjects/sections) are returned to every user; the calendar is enrollment-scoped but the events page is not. Decide whether the list should filter to the user's subjects (or stay institutional).
- **D4 — Global-event broadcast audience.** Code broadcasts global events to **every user** (`get_all_user_ids`, user_repo.py:127-131); the trigger docstring says "ADMIN-only, broadcast" (notification_service.py:306) — ambiguous. If all-students broadcast is intended (likely: holidays matter to everyone), fix the docstring; if not, fix the recipient query.
- **D5 — Notification retention.** Explicitly deferred as a product decision (notification_repo.py:16-19). Evidence of unbounded growth: 182 ACADEMIC_EVENT rows/user, 482 unread total in a dev DB populated within ~1 week (oldest row 2026-09-25). Decide policy (age-based, kind-based, read-based) — interacts with EVT-001/002 (lifecycle cleanup would shrink most of it).
- **D6 — Should quiz-manager QUIZ_DAY events emit ACADEMIC_EVENT rows?** Today they silently do not (the quiz service inserts events directly and only calls `after_quiz_mutation`), while the *same* event created via `/events` emits to all enrolled users. Decide which is canonical and align (probably: quiz awareness = QUIZ_APPROACHING only; document it).
- **D7 — Past-dated event creation.** Currently allowed for everyone (students and admins, all types). Confirm this is intended policy (it is consistent with "record what happened"), and consider a distinct guard only for global closures far in the past.

## 17. Missing Tests (test-gap list; no tests were added)

Existing coverage reality: pytest (`backend/tests/`, `pytest.ini` testpaths) covers pure functions and a handful of savepoint-rollback service tests; **all HTTP-level event verification lives in out-of-band `scripts/verify_*.py` files that require a live DB and are not run by pytest/CI** (agent-verified inventory, §Appendix).

- **EVT-T1 — HTTP-level event CRUD + authorization matrix** (403 for non-enrolled student, wrong type, global type; scoped-admin matrix; 409 duplicate; 422 registry; 404s). Exists only as `verify_phase_6_5.py` (live DB, not CI).
- **EVT-T2 — Event→notification lifecycle**: emission on create/update; **no cleanup on deactivation / future→past move** (would have caught EVT-001/002); no duplicate-push regression at HTTP level.
- **EVT-T3 — Quiz-managed guard on the canonical `/events` endpoints** (would catch EVT-003) and the admin type-change-into-managed gap.
- **EVT-T4 — Concurrency/duplicate suppression** (two parallel creates; reconciler races) — needs the EVT-004 constraints to test meaningfully.
- **EVT-T5 — Out-of-span event behavior** (EVT-011), esp. QUIZ_DAY beyond `max(class_sessions.date)`.
- **EVT-T6 — Date-boundary semantics**: `upcoming` at IST midnight, inclusive overlap filters, month-clamp edges (month disjoint from semester).
- **EVT-T7 — Reactivation identity pass** at API level (attended-extra preservation on deactivate→reactivate) — covered partially by `test_extra_lifecycle_foundation.py` (service level).
- **EVT-T8 — Ordering/pagination contract** of `GET /events` once EVT-007 lands.

## 18. Recommended Remediation Order

1. **EVT-003** (HIGH) — move the quiz-managed guard into `EventService`; add the prospective type-change check. Small, contained, protects the core feature.
2. **EVT-001 + EVT-002** (MEDIUM) — one compensating notification hook in `deactivate_event` and in the future→past branch of `update_event` (delete/dismiss ACADEMIC_EVENT rows for the event).
3. **EVT-004** (MEDIUM) — partial unique indexes + 409-on-conflict mapping (the only migration in the list; run when a maintenance window is acceptable).
4. **EVT-005** (MEDIUM) — product decision first (scheduler vs remove preference), then code.
5. **EVT-011** (potential) — span validation on quiz/event dates.
6. **EVT-006/007/009/010** (LOW) — batch as a hardening pass (indexes, bounded reads, deterministic order, field limits).
7. **EVT-008** — run the existing purge script on dev (ops).
8. Decisions D1-D7 — record outcomes in docs; several block nothing.

## 19. Exact Files Inspected

**Backend core:** `app/models/event.py`, `app/models/notification.py`, `app/models/enums.py`, `app/models/timetable.py`, `app/models/occurrence.py`, `app/models/academic.py` (StudentEnrollment), `app/db/base_class.py`, `app/core/timezone.py`, `app/core/config.py` (prod guard), `app/db/session.py`;
`app/repositories/event_repo.py`, `calendar_repo.py`, `session_repo.py`, `notification_repo.py`, `user_repo.py` (recipient queries), `admin_quiz_repo.py` (find_quiz_day_event), `quiz_repo.py` (effective quiz dates);
`app/services/event_service.py`, `event_registry.py`, `event_session_service.py`, `admin_event_service.py`, `notification_service.py`, `calendar_service.py`, `authorization_service.py`, `admin_quiz_service.py` (quiz-event sync + notify), `dashboard_service.py` (event consumers), `elective_resolver.py`, `attendance_service.py` (409-on-cancelled, trigger site);
`app/api/v1/endpoints/events.py`, `calendar.py`, `notifications.py`, `admin.py` (events section), `app/api/dependencies/deps.py`, `app/api/v1/router.py`, `app/engines/calendar_engine.py`;
`alembic/versions/`: `7117a007a0da_initial_schema.py`, `a1b2c3d4e5f6`, `a7b8c9d0e1f2`, `b7c8d9e0f1a2`, `f8a9b0c1d2e3`, `e2f3a4b5c6d7`, `d1e2f3a4b5c6` (agent-verified DDL cross-check).

**Scripts/tests:** `scripts/purge_orphaned_event_notifications.py`, `audit_ro_notifications.py`, `audit_ro_db.py`, `audit_ro_reconcile.py`, `seed_academic_events.py`, `seed_academic_baseline.py`, `_verifier_harness.py`, `verify_event_cancellation_propagation.py`, `verify_cancellation_lifecycle_consistency.py`, `verify_events_correction.py`, `verify_phase_6_5/6_6/6_7/22_4/11c_p4/2_quiz_events.py`, `backend/tests/*` (inventory), `pytest.ini`, `backend/verify_openapi.py`, `verify_phase_25_4.py`, `verify_phase_26_5.py`.

**Frontend (contract only):** `src/types/api.ts`, `src/lib/api.ts`, `src/lib/date.ts`, `src/hooks/useApi.ts`, `src/components/events/EventFormDialog.tsx`, `eventRules.ts`, `EventRow.tsx`, `src/app/(authenticated)/tools/events/page.tsx`, calendar page/grid/day-detail, admin events dialogs, NotificationCenter, PWA refresh listener (agent-mapped with file:line evidence; key claims spot-verified).

## 20. (merged into §21)

## 21. Exact DB Evidence / Queries Used

All live access was **SELECT-only** against the local dev database (`DATABASE_URI` → `localhost`, per `backend/.env`), via the repo's own read-only forensics script and two inline probe batches. Nothing was written.

1. `scripts/audit_ro_notifications.py` (repo-owned, documented read-only): `notif_event_refs_missing = 452`; `notif_event_refs_inactive = 0`; per-user counts (ACADEMIC_EVENT 182 / 182 / 88); `notif_session_refs_missing = 0`; oldest notification created 2026-09-25; `unread_total = 482`.
2. Inline probes (results in §3.1, §14 EVT-006/008):
   - `SELECT count(*), count(*) FILTER (WHERE active) … FROM academic_events` → **18 total, 18 active, 0 inactive**;
   - per-type counts → **QUIZ_DAY ×18** only;
   - duplicate natural-key / inverted-range / duplicate same-subject-date extras probes → **all empty**;
   - span probe → sessions `2026-07-15..2026-12-31`, events `2026-08-24..2026-10-26` (all in span);
   - `SELECT indexname FROM pg_indexes WHERE tablename='academic_events'` → **only `academic_events_pkey`**;
   - `SELECT conname, contype FROM pg_constraint WHERE conrelid='academic_events'::regclass` → **PK + subject FK only**;
   - `notifications LEFT JOIN academic_events` by kind → **ACADEMIC_EVENT total 452, inactive refs 0, past refs 0** (⇒ all 452 reference non-existent events); ACADEMIC_EVENT row dates 2026-10-05..2026-11-26.

## 22. Final Scope / Boundary Verification

- No code, tests, schemas, migrations, configuration, or frontend files were modified (working tree contained only this new report file at delivery).
- No database mutation: every live statement was a `SELECT` (the two repo scripts used are documented read-only; the purge script was **not** executed).
- No remediation implemented; no commits made beyond the pre-existing state.
- The investigation covered every event producer/consumer found by exhaustive grep (`-i event` across `backend/app`, `backend/scripts`, `backend/alembic`, `backend/tests`) and the frontend contract surface; consumers outside the named files (dashboard, eligibility, attendance, calendar, notifications, quiz manager, elective resolver, seed/verify scripts) were traced to their event queries (§2.2).

---

### Final Assessment

- **Confirmed Critical:** 0
- **Confirmed High:** 1 — EVT-003 (quiz-managed QUIZ_DAY guard bypassable via canonical `/api/v1/events`; quiz-date authority can be desynchronized)
- **Confirmed Medium:** 4 — EVT-001 (stale live notifications on deactivation), EVT-002 (stale notification on future→past move), EVT-004 (no DB unique constraints/locks behind duplicate & session reconciliation), EVT-005 (CLASS_REMINDER unreachable — H-4d, not Events-caused)
- **Confirmed Low:** 5 — EVT-006 (no indexes), EVT-007 (unbounded, non-deterministically ordered `/events`), EVT-008 (452 orphan rows still present; purge unrun), EVT-009 (non-deterministic quiz-event identity lookup), EVT-010 (unbounded note/override; client-settable `active` on create)
- **Potential risks:** 4 — EVT-011 (out-of-span QUIZ_DAY: eligibility-visible but unmarkable), EVT-012 (partial notification broadcast / mid-transaction commit hazard), EVT-013 (inconsistent same-priority tiebreak engine vs synchronizer), EVT-014 (student reactivation revives admin-withdrawn attended extras)
- **Product decisions:** 7 — D1 ownership model (no `created_by`), D2 inactive-event visibility, D3 enrollment scoping of `/events`, D4 global-event broadcast audience vs docstring, D5 notification retention, D6 QUIZ_DAY emission asymmetry (quiz-manager vs `/events`), D7 past-dated creation policy
- **Test gaps:** 8 — EVT-T1..T8 (HTTP-level CRUD/authz matrix, notification lifecycle, guard-on-canonical-endpoints, concurrency, out-of-span, date boundaries, reactivation identity pass, ordering/pagination)
- **Data integrity concerns:** duplicate-event/session races possible (no constraints); 452 orphan notification rows persist in dev; soft-stale live notification rows accumulate by design
- **Security concerns:** no authentication/IDOR defects found; one authorization-policy bypass (EVT-003) by authenticated admins; minor mass-assignment surface (EVT-010)
- **Notification concerns:** incomplete event lifecycle (EVT-001/002); no scheduler ⇒ CLASS_REMINDER dead (EVT-005); retention deferred (D5); per-row commits (EVT-012); H-4a read-mitigation verified working, rows not purged
- **Date/timezone concerns:** none found — the date-only, institution-clock design is verified clean end-to-end (no naive/aware mixing, no off-by-one surface, no DST exposure)

### STOP CONDITION

Investigation complete; report delivered. Nothing was fixed, committed, or migrated; no remediation has begun.
