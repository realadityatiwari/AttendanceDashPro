# Phase 11A — Backend Notification Read Model & Contracts: Implementation Report

> **PHASE 11A COMPLETE (2026-08-20).** Phase 11 — Notifications & Reminders: **IN PROGRESS** (11.0 audit ✅ · 11A ✅ · 11B–11F NOT STARTED). No commit made.

## 1. Objective

Implement the smallest safe slice of Phase 11 (per `docs/phase_11/phase_11_architecture_audit.md`): a **backend notification read model + contracts** — additive `NotificationKind` enum, notification schemas, a read-only `NotificationService`, `GET /api/v1/notifications`, router registration, and `backend/scripts/verify_phase_11a.py`. Zero DB change, zero migration, zero new infrastructure, zero frontend, zero scheduler. Notifications are generated **on-read** (like every existing read model), and the architectural rule is enforced: **notifications consume engine outputs; they do not independently calculate attendance.**

## 2. Exact Files Changed

| File | Change |
|---|---|
| `backend/app/models/enums.py` | Additive `NotificationKind` enum (CLASS_REMINDER, QUIZ_APPROACHING, ATTENDANCE_THRESHOLD, MUST_ATTEND, SAFE_SKIP, ACADEMIC_EVENT). No existing value touched. |
| `backend/app/schemas/notification.py` | **New.** `NotificationItem` (deterministic natural-key `id`, `kind`, `date`, optional `subject_code`/`subject_name`, `message`, canonical reference fields `session_id`/`quiz_cycle`/`event_id`) + `NotificationsResponse` (items + server-generated `as_of`). |
| `backend/app/services/notification_service.py` | **New.** Read-only projection service composing existing engines/services (see §5); no persistence. |
| `backend/app/api/v1/endpoints/notifications.py` | **New.** `GET /api/v1/notifications`, JWT owner only (`get_current_user`), `get_db` dependency. |
| `backend/app/api/api.py` | Registered `notifications.router` under prefix `/notifications` (the real registration path; the dead `app/api/v1/router.py` scaffolding was not used). |
| `backend/scripts/verify_phase_11a.py` | **New.** 19-check end-to-end verifier (house pattern: httpx ASGITransport + real DB + minted JWTs). |

No other file was touched: no migration, no `__init__.py` model change, no engine, no repository, no frozen verifier, no frontend file.

## 3. API Contract

```
GET /api/v1/notifications        (JWT required)
→ 200 {
    "items": [
      {
        "id": "<natural key: KIND:<reference>>",
        "kind": "CLASS_REMINDER" | "QUIZ_APPROACHING" | "ATTENDANCE_THRESHOLD"
                | "MUST_ATTEND" | "SAFE_SKIP" | "ACADEMIC_EVENT",
        "date": "YYYY-MM-DD",
        "subject_code": "BCS-502" | null,
        "subject_name": "..." | null,
        "message": "...",
        "session_id": "<uuid> | null",   // CLASS_REMINDER reference
        "quiz_cycle": 1 | null,           // QUIZ_APPROACHING reference
        "event_id": "<uuid> | null"       // ACADEMIC_EVENT reference
      }
    ],
    "as_of": "YYYY-MM-DD"                 // institution_today(), server-generated
  }
→ 401 unauthenticated / invalid token
```

- The owner is always the authenticated JWT identity; a client-supplied `?user_id=` query parameter is ignored (FastAPI never binds it; verified byte-identical responses).
- `as_of` is the canonical `institution_today()` (Asia/Kolkata) — never the client clock.
- The natural-key `id` (`KIND:<reference>`) is deterministic and stable, giving 11B persistence a ready-made dedup key and the client a stable React key.
- Items are sorted by `(date, kind, id)`; ACADEMIC_EVENT is additionally capped at 4 (identical to the dashboard upcoming-events cap).

## 4. Notification Kinds Implemented

| Kind | Trigger (canonical source) | Message shape |
|---|---|---|
| `CLASS_REMINDER` | Unmarked, non-cancelled class sessions in the current institutional week, gated by the `class_reminders` preference | `BCS-502 Lecture today at 09:00 AM` / `BCS-551 Practical Friday, 21 Aug at 01:00 PM` |
| `QUIZ_APPROACHING` | `get_current_quiz_cycle` with basis `next_upcoming` (a confirmed quiz date at/after today exists) | `Quiz I approaching on 23 Oct 2026` |
| `ATTENDANCE_THRESHOLD` | `classify_attendance_status` ∈ {WATCH, CRITICAL} (the same attention concept the dashboard surfaces) | `BCS-054 attendance is critical (62.5%)` |
| `MUST_ATTEND` | `optimize_attendance` output: reachable AND lecture+tutorial deficit > 0 | `BCS-502: attend 2 lectures + 1 tutorial to reach 75%` |
| `SAFE_SKIP` | `optimize_attendance` output: reachable AND safe-skip lectures+tutorials > 0 | `BCS-502: safe to skip 1 lecture` |
| `ACADEMIC_EVENT` | Active events with `end_date >= today`, enrollment-scoped, sorted, capped at 4 (identical selection to the dashboard upcoming-events section) | `BCS-054 Quiz Day on 23 Oct 2026` / `Semester Break on 15 Nov - 22 Nov 2026` |

All six kinds can coexist for one user (e.g., MUST_ATTEND and SAFE_SKIP for the same subject are independent facts of the optimizer output).

## 5. Canonical Sources Used (No Re-implemented Math)

| Value | Canonical source |
|---|---|
| Current date | `attendance_service.institution_today()` (the single source of truth) |
| Class sessions + status | `AttendanceRepository.get_sessions_with_status(user_id, start, end)` — enrollment-scoped, practical occurrences collapsed, future-safe |
| Week scope | `week_start = as_of - timedelta(days=as_of.weekday())` … `+6` — the same repository-defined weekly scope the dashboard Weekly section uses |
| Per-subject status band | `attendance_engine.classify_attendance_status(summary.current_avg_pct)` via `AttendanceService.get_subject_summaries` |
| Must-attend / safe-skip | `attendance_engine.optimize_attendance` output (`lecture_deficit`, `tutorial_deficit`, `safe_skip_lecture`, `safe_skip_tutorial`, `is_reachable`) at the canonical 75% target (`summary.required_pct`) |
| Next upcoming quiz | `EligibilityService.get_current_quiz_cycle(user_id)` basis `next_upcoming` (itself reads only active QUIZ_DAY AcademicEvents — the authoritative quiz-date source) |
| Academic events | `CalendarRepository.get_all_events()` with the dashboard's exact selection semantics (active, `end_date >= today`, enrolled-scoped, sorted by `(start_date, event_type)`, capped at 4) |
| Enrollment scoping | `UserRepository.get_enrolled_subjects(user_id)` |

The service performs no aggregation or percentage mathematics — it selects, labels, and sorts existing outputs.

## 6. `class_reminders` Behavior

- CLASS_REMINDER is **gated** by the user's `userpreferences.class_reminders` flag.
- A missing preference row is treated as the documented server default (**off**) — the service uses the pure-read `PreferenceRepository.get(user_id)` and never materializes a row (no lazy-create write in a read path).
- When on: reminder scope = current institutional week `[institution_today(), week-end Sunday]`; sessions must be non-cancelled and unmarked (`status is None`) — an already-decided session is not a reminder. Practical blocks collapse to one occurrence via the canonical repo (reminder references the representative session id).
- **Unresolved product decision (documented, not invented):** the multi-day horizon. This implementation uses the repository-defined current-week scope because it is the only horizon with an established meaning in the codebase; a different lookahead (e.g., N days) is a product decision for the owner.

## 7. `auto_mark_present` — Inert Statement

`auto_mark_present` is **completely inert in Phase 11A**. Nothing reads it; nothing writes attendance; no background process exists; the value cannot change any notification output. Verified by `verify_phase_11a.py` check 11: the notifications response is byte-identical with `auto_mark_present=false` and `auto_mark_present=true`. Per the architecture audit, implementing auto-mark is **NOT part of Phase 11** and requires an explicit product-owner decision; the field remains storage/preference data only.

## 8. `week_starts_on` — Inert Statement

`week_starts_on` is **completely inert in Phase 11A**. Nothing consumes it; CLASS_REMINDER uses the repository-defined Monday-start week (the same bound the dashboard Weekly section uses), and the value cannot change any notification output. Verified by `verify_phase_11a.py` check 12: byte-identical response with `week_starts_on=SUNDAY` vs `MONDAY`. Wiring this preference is deliberately deferred (audit: it is not a Phase 11 concern).

## 9. DB Proof — No Migration, No Schema Change

- No migration file was created or modified; `alembic heads` and `alembic current` both report the unchanged head **`c1d2e3f4a5b6`** (verified before and after inside the verifier, check 18).
- No `notifications` (or any other) table exists: `to_regclass('public.notifications')` is NULL (check 14).
- Frozen-table snapshot (users, sections, events, sessions, cancelled/extra counts, records, enrollments, subjects, timetable entries, quizzes, cycles, policies, academic session, semester, laboratory, feedback, userpreferences) is byte-identical before and after the verifier run (check 13).
- Phase 10E freeze baseline: 31 users (1 ADMIN) · 1 section · 47 events · 715 sessions (0 cancelled, 0 extra) · 142 records · 27 enrollments · 9 subjects · 28 timetable entries · 18 quizzes · 3 quiz cycles · 3 eligibility policies · 1 session · 1 semester · feedback 0 · userpreferences 0 · lab 0/0 — unchanged after 11A.

## 10. Verifier Results

`python scripts/verify_phase_11a.py` → **19/19 checks passed**:

1. authenticated `GET /api/v1/notifications` → 200
2. unauthenticated (no header / invalid token) → 401
3. response shape valid (items[] with id/kind/date/message per item)
4. `as_of` is the server-generated institution date (never client-controlled)
5. client-supplied `?user_id=` is ignored (identical response, no `user_id` field)
6. enrollment scoping + isolation: unenrolled user gets no subject-scoped items; owner items reference only enrolled subjects
7. `class_reminders=false` suppresses CLASS_REMINDER (qualifying in-week session present)
8. `class_reminders=true` permits CLASS_REMINDER referencing the qualifying in-week session
9. cancelled sessions never generate CLASS_REMINDER
10. sessions outside the current institutional week are not reminded
11. `auto_mark_present=true` has NO effect on the notification output
12. `week_starts_on=SUNDAY` has NO effect on the notification output
13. notification generation mutated NO frozen-table data (full snapshot byte-identical)
14. no notification persistence table was created (on-read only)
15. QUIZ_APPROACHING matches the canonical current quiz cycle (basis `next_upcoming` cross-checked against `EligibilityService`)
16. ATTENDANCE_THRESHOLD / MUST_ATTEND / SAFE_SKIP match the canonical subject summaries (engine banding + optimizer cross-checked via `AttendanceService`)
17. ACADEMIC_EVENT items equal the dashboard upcoming-events selection (cross-checked via `GET /api/v1/dashboard/summary`)
18. alembic head unchanged (no migration created)
19. exact cleanup: only this verifier's artifacts removed (2 temp users, 1 enrollment, 3 temp sessions, 2 preference rows — all deleted by explicit captured IDs in `finally`), pre-existing rows preserved

`python -m compileall -q app scripts` → PASS. No browser tests (per the 11A brief; verification is in-process end-to-end).

## 11. Security / Ownership Proof

- The endpoint derives the owner exclusively from the JWT (`Depends(get_current_user)`); there is no `user_id` path/query/body parameter to accept.
- Check 5 proves a `?user_id=` spoof attempt yields a byte-identical response.
- Every subject-scoped item is enrollment-scoped: check 6 proves an unenrolled user receives no subject-scoped items and the owner's items reference only their enrolled subject codes.
- The verifier's controlled fixture (temp users/sessions/preferences) is removed by explicit captured IDs; the frozen snapshot proves no leakage into pre-existing data.

## 12. Frozen-System Impact

None. No engine (`attendance_engine`, `eligibility_engine`, `calendar_engine`), no repository, no service beyond the new `NotificationService`, no model beyond the additive enum, no endpoint beyond the new GET, no migration, no DB row, and no frozen verifier was touched. The `class_reminders` preference contract (Phase 10D) is read-only here. The dashboard read model is byte-identical (proven by check 17's cross-comparison).

## 13. Unresolved Product Decisions

1. **Reminder horizon** — current-week scope (repository-defined) vs an explicit N-day lookahead.
2. **Quiz horizon** — "next upcoming quiz" (implemented) vs a T-minus-N days notice window.
3. **Delivery model** — in-app only (recommended) vs scheduled server-side sweep (external cron + system-token endpoint); decides whether 11C exists.
4. **`auto_mark_present` semantics** — recommendation stands: remains storage-only; if ever implemented, only via an explicit user-confirmed interaction invoking the canonical mutation API, never an unattended background write.
5. **`week_starts_on` consumption** — deliberately out of Phase 11 (audit §2.2/§7).

## 14. Remaining Phase 11 Work (NOT STARTED)

- **11B** — notification persistence/read-state: migration + `notifications` table + `NotificationRepository`, extending `NotificationService`; the 11A natural-key `id` is the dedup key. **Next authorized slice.**
- **11C** — delivery model (decision-gated; see §13.3).
- **11D** — frontend notification center UX (bell badge + panel; SWR refresh is the house pattern).
- **11E** — remaining reminder-preferences wiring.
- **11F** — phase completion: consolidated `verify_phase_11.py`, full frozen regression run, governance reconciliation (Phase 11 → COMPLETE & FROZEN), final report.

Governance documents updated for 11A: `MASTER_ROADMAP.md` (header "Current position"/"Next phase", status table row 11 → IN PROGRESS, Phase 11 section rewritten with sub-phase status), `implementation_plan.md` (Phase 11 record section), `task.md` (Phase 11 task-brief record), `walkthrough.md` (Phase 11 walkthrough section).

## 15. HARD STOP

**PHASE 11A COMPLETE — HARD STOP.** No commit was made. 11B is NOT started. No migration, no frontend, no scheduler, no persistence. Browser/manual testing remains the user's responsibility. Phase 11 remains **IN PROGRESS** (not COMPLETE/FROZEN); the next authorized slice is **11B**.