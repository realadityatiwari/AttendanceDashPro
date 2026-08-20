# Phase 11B — Notification Persistence + Read-State: Implementation Report

> **PHASE 11B COMPLETE (2026-08-20).** Phase 11 — Notifications & Reminders: **IN PROGRESS** (11.0 audit ✅ · 11A ✅ · 11B ✅ · 11C–11F NOT STARTED; 11C decision-gated). No commit made.

## 1. Objective

Implement the second authorized Phase 11 slice (per `docs/phase_11/phase_11_architecture_audit.md` §9-11B): **persist the Phase 11A notification projection without creating duplicate notifications on repeated projection/refresh**, and add the audit-named **read-state API** (`GET` inbox with unread count, `PATCH read/dismiss`). The implementation is fully additive: one new migration, a `Notification` model, an owner-scoped repository, an extended `NotificationService`, additive schema fields, one new endpoint, and `backend/scripts/verify_phase_11b.py`. No push/email/SMS/scheduling/Celery/Redis/cron/browser-notification/service-worker/PWA/channels/delivery-providers were introduced — the 11C delivery model remains decision-gated and deferred. No frozen system was modified; no frontend file changed; the Phase 11A projection semantics are authoritative and unchanged.

## 2. Exact Files Changed

| File | Change |
|---|---|
| `backend/alembic/versions/d1e2f3a4b5c6_add_notifications.py` | **New.** Additive migration (single head, `down_revision = c1d2e3f4a5b6`) creating `notifications` + `notificationkind` enum. Applied and current. |
| `backend/app/models/notification.py` | **New.** `Notification` model — owner FK, Phase 11A `kind` enum, `occurrence_key`, `date`, nullable presentation refs, `message`, nullable typed source refs, `is_read`/`is_dismissed`, Base-mixin id/timestamps, `UNIQUE(user_id, kind, occurrence_key)`. No relationships to any frozen domain table. |
| `backend/app/models/__init__.py` | Imports `Notification`. |
| `backend/app/repositories/notification_repo.py` | **New.** Owner-scoped repository: `upsert` (PostgreSQL `ON CONFLICT DO UPDATE`; refreshes only message/subject refs/`updated_at`; preserves `date`/`is_read`/`is_dismissed`/`created_at`), `get_inbox` (newest first, dismissed excluded), `get_by_id`, `count_unread`, `count_for_user`, `update_state` (idempotent), `delete`. |
| `backend/app/services/notification_service.py` | Extended (11A preserved): snapshot-on-read generation into persisted rows via deterministic `_occurrence_key`; `get_notifications` serves the persisted inbox newest-first + `unread_count`; `update_state` backs the PATCH. |
| `backend/app/schemas/notification.py` | Additive: `notification_id` + `is_read` on `NotificationItem`; `unread_count` on `NotificationsResponse`; `NotificationUpdate` (at least one of `is_read`/`is_dismissed`; empty body → 422). |
| `backend/app/api/v1/endpoints/notifications.py` | Added `PATCH /api/v1/notifications/{notification_id}` (read/dismiss; owner-scoped; idempotent). `GET /api/v1/notifications` contract preserved (now the persisted inbox). |
| `backend/scripts/verify_phase_11b.py` | **New.** 23-check end-to-end verifier (house pattern: httpx ASGITransport + real DB + minted JWTs). |
| `backend/scripts/verify_phase_11a.py` | Re-scoped checks 13/14/18/19 for the 11B surface: the notifications table now exists and GET persists rows, so the verifier proves the table exists (11B surface) and restores it to its pre-run state. Phase 11A projection assertions unchanged. |

No engine, no attendance/quiz/calendar/lab repository, no dashboard/analytics/history read model, no auth file, no frontend file was touched.

## 3. API Contract

```
GET /api/v1/notifications                        (JWT required)
→ 200 {
    "items": [ {                                  // persisted inbox, newest first
        "id": "<natural key: KIND:<occurrence_key>>",
        "notification_id": "<row uuid>",          // 11B: PATCH target
        "kind": "CLASS_REMINDER" | "QUIZ_APPROACHING" | "ATTENDANCE_THRESHOLD"
                | "MUST_ATTEND" | "SAFE_SKIP" | "ACADEMIC_EVENT",
        "date": "YYYY-MM-DD",                     // first-generation occurrence date
        "subject_code": "BCS-502" | null,
        "subject_name": "..." | null,
        "message": "...",
        "session_id": "<uuid> | null",
        "quiz_cycle": 1 | null,
        "event_id": "<uuid> | null",
        "is_read": false
    } ],
    "as_of": "YYYY-MM-DD",                        // institution_today(), server-generated
    "unread_count": 2                             // 11B: unread + non-dismissed badge
  }
→ 401 unauthenticated / invalid token

PATCH /api/v1/notifications/{notification_id}     (JWT required)
body { "is_read"?: bool, "is_dismissed"?: bool }  // at least one required
→ 200 { ...the updated NotificationItem... }
→ 404  not owned by the caller / nonexistent      // indistinguishable by design
→ 401  unauthenticated
→ 422  empty body
```

- Owner is always the authenticated JWT identity (`get_current_user()` → `user.id`); client-supplied `user_id` in query or body is never accepted (byte-identical response proven for `?user_id=` spoof; no such body field exists).
- Dismissed notifications are excluded from `items` but remain in the table (persisted flag, not a physical delete) so a regenerated occurrence cannot resurrect them while the source condition still holds.

## 4. Deterministic Identity / Idempotency

`occurrence_key` mirrors the Phase 11A natural-key `id` suffix, derived from the actual 11A projection source reference:

| Kind | `occurrence_key` |
|---|---|
| `CLASS_REMINDER` | session id (`item.session_id`) |
| `QUIZ_APPROACHING` | quiz cycle (`item.quiz_cycle`) |
| `ACADEMIC_EVENT` | event id (`item.event_id`) |
| `ATTENDANCE_THRESHOLD` / `MUST_ATTEND` / `SAFE_SKIP` | subject code (`item.subject_code`) |

- Database backstop: `UNIQUE(user_id, kind, occurrence_key)` — repeated generation of the same logical occurrence can never insert a duplicate row.
- Application behavior: `upsert` runs `ON CONFLICT DO UPDATE` refreshing only `message`, `subject_code`, `subject_name`, `updated_at`; it **preserves** `date` (first-generation occurrence date), `is_read`, `is_dismissed`, `created_at`.
- Distinct occurrences (different session ids, quiz cycles, event ids, subject codes) keep distinct rows — proven by verifier checks 6/7.
- The persisted `id` returned to the client stays the 11A natural key (`KIND:<occurrence_key>`), so the client's stable React key is unchanged and the same rows / same `notification_id`s are returned across repeated GETs (verifier check 5).

## 5. Read / Unread / Dismiss Behavior

Read/unread persistence **is** part of the authoritative 11B contract (audit §9-11B: "read-state API", "PATCH read/dismiss", "inbox, newest first, unread count"). Implemented minimally and scope-locked to `current_user`:

- New rows default to unread (`is_read = false`), non-dismissed.
- `PATCH {is_read: true}` lowers `unread_count` by one; repeating the same transition is an idempotent no-op success.
- `PATCH {is_dismissed: true}` removes the row from the inbox; the flag survives regeneration.
- `unread_count` counts unread + non-dismissed rows only.
- Cross-user mutation is impossible: PATCH on another user's (or a nonexistent) row → 404; verified.
- Not implemented (deferred, not invented): any broader dismissal system, retention pruning, per-kind daily caps, delivery providers, scheduling, admin surfaces.

## 6. Security / Authorization

- Identity flows exclusively through `JWT → get_current_user() → current_user.id`; the repository scopes every read, write and mutation by `user_id`.
- There is no client-controlled `user_id` anywhere: GET ignores a spoofed `?user_id=` (verified identical response); the PATCH body carries only state booleans; the mutation target is the row `notification_id` returned by the owner's own inbox.
- Unauthenticated GET and PATCH → 401; empty PATCH body → 422.
- No admin notification management added.

## 7. Frozen-System Impact

None. The 11B surface consumes the same engine/service outputs the 11A projection already consumed (attendance summaries + banding/optimizer, current quiz cycle, session status rows, dashboard upcoming-events selection) and adds no computation. Attendance, eligibility, calendar/event, quiz, laboratory, dashboard, Track, History and authentication behavior are byte-identical before/after the verifier runs (full frozen-table snapshot, notifications included and restored).

## 8. Migration / Schema Summary

- Revision: **`d1e2f3a4b5c6`**, `down_revision = c1d2e3f4a5b6`; applied; `alembic heads == current == d1e2f3a4b5c6` (single head).
- New: table `public.notifications`, type `notificationkind` (the six Phase 11A kind values).
- Additive only; no historical migration modified; no DB reset.

## 9. Verification

- `python -m compileall -q app scripts` — PASS.
- `python scripts/verify_phase_11b.py` — **23/23 PASS**:
  1. single alembic head `d1e2f3a4b5c6`
  2. notifications table + `notificationkind` enum exist
  3. GET persists one row per generated projection
  4. repeated GET adds no duplicate rows (DB-enforced dedup)
  5. deterministic identity stable across calls (same rows / same `notification_id`s)
  6. distinct occurrences persist as distinct rows (s1/s3 reminders + temp event)
  7. all six `NotificationKind` values persist; re-upsert refreshes in place (same row ids)
  8. refresh preserves date/created_at/is_read/is_dismissed while refreshing the message
  9. PATCH read transition works; `unread_count` decreases
  10. repeating the same PATCH is idempotent
  11. dismissal hides the row and survives regeneration (persisted flag)
  12. cross-user isolation (user B never sees A's rows; no subject-scoped items)
  13. cross-user / nonexistent PATCH → 404
  14. client-supplied `?user_id=` ignored
  15. unauthenticated GET / PATCH → 401
  16. empty PATCH body → 422
  17. persisted ATTENDANCE_THRESHOLD / MUST_ATTEND / SAFE_SKIP match canonical subject summaries (engine banding + optimizer)
  18. 11A semantics unchanged (cancelled/out-of-week excluded; `week_starts_on`/`auto_mark_present` inert; `class_reminders=false` stops generating new rows, existing rows stay)
  19. persisted QUIZ_APPROACHING matches the canonical current quiz cycle
  20. persisted ACADEMIC_EVENT rows equal the dashboard upcoming-events selection
  21. verification mutated NO frozen-table data (full snapshot byte-identical, notifications restored)
  22. alembic head unchanged during the run
  23. exact cleanup: only this verifier's artifacts removed; admin inbox restored to its pre-run row set
- `python scripts/verify_phase_11a.py` (regression) — **19/19 PASS** (checks 13/14/18/19 re-scoped to prove the notifications table exists as the 11B surface and that the verifier restores it to its pre-run state; all 11A projection assertions unchanged).
- DB baseline restored: 31 users; notifications 0; frozen-table snapshot byte-identical. No browser tests run.

## 10. What Was NOT Done (deferred)

- **11C** delivery model (scheduling/sweep/push/email) — decision-gated; deferred, not invented.
- **11D** frontend notification center UX — not started.
- **11E** remaining preference wiring — not started.
- **11F** phase completion / freeze — not started.
- `auto_mark_present` semantics — owner product decision, unchanged.
- Retention pruning / per-kind daily caps — outside the 11B contract, deferred.

## 11. Next Authorized Slice

**11D — Frontend notification center UX** (bell + unread badge, notification center with read/dismiss actions, `useNotifications()` / `useNotificationMutation()`, types in `types/api.ts`), pending explicit authorization. 11C remains decision-gated and may be omitted from Phase 11 entirely.

**PHASE 11B COMPLETE — HARD STOP.** No commit was made. 11C NOT STARTED · 11D NOT STARTED. Browser/manual testing remains the user's responsibility. Phase 11 remains **IN PROGRESS** (not COMPLETE/FROZEN).