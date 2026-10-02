# EVT-007 Forensic Audit — Events List Path: Unbounded Reads & Ordering

**Date:** 2026-10-03
**Scope:** EVT-007 ONLY ("`GET /api/v1/events` is unbounded and ordered non-deterministically" — `docs/EVENTS_BACKEND_DEEP_AUDIT_REPORT.md` §14/§18) — audited against the post-remediation tree (EVT-003/001/002/004/005 remediated and committed at `c219202`) and the live dev DB (PostgreSQL 16.15, alembic `b9c0d1e2f3a4`).
**Mode:** READ-ONLY. No code, migration, test, data, config, or frontend change. `EXPLAIN (ANALYZE)` on `SELECT`-only statements. Nothing committed.

---

## A. Complete query/consumer inventory

The shared loader is `CalendarRepository.get_all_events` (`repositories/calendar_repo.py`): `SELECT * FROM academic_events` + optional `active = ?`, optional inclusive overlap (`end_date >= :date_from AND start_date <= :date_to`), optional `upcoming` (`end_date >= institution_today()`), **`ORDER BY start_date`** — no `LIMIT`/`OFFSET` anywhere in the method (verified by inspection).

Backend consumers of the loader — 8 call sites:

| Consumer | Loader arguments | Bound |
|---|---|---|
| `api/v1/endpoints/events.py` `GET /events` | `active` (query, default **True**), optional `date_from`/`date_to`, optional `upcoming` | Bounded **only if** the client sends dates |
| `services/calendar_service.py` `get_month_view` | `active=True, date_from=effective_start, date_to=effective_end` (month ∩ semester) | **Bounded** by date range |
| `services/calendar_service.py` `get_day_schedule` (standalone day path) | `get_all_events()` — **unfiltered**; engine filters `e.active` for the one requested day | Full load, Python-bounded |
| `services/dashboard_service.py` summary | `active=True, date_from=min(semester_start, today)` | Bounded below only |
| `services/eligibility_service.py` (2 sites) | `get_all_events()` — **unfiltered** | Full load (window math filters) |
| `services/notification_service.py` `_academic_events` (sweep) | `get_all_events()` — **unfiltered**; manual `active + end_date >= today` filter; **slices `[:4]`** | Full load, bounded output |
| `services/event_session_service.py` `sync_event` | `get_all_events(active=True)` | Full active set — **required for reconciliation correctness** |
| `services/admin_event_service.py` `list_events` (GET /admin/events) | `active` param, optional `date_from`/`date_to`; then Python-side type/subject/slot/class_type filters | Bounded only if admin passes filters |

Related but NOT this loader (separate, already-bounded query): `admin_dashboard_repo.get_upcoming_events(limit)` (`active AND end_date >= today ORDER BY start_date, id LIMIT :n`).

Frontend consumers (verified in `frontend/src`):

| Consumer | Call | Params actually sent | Assumes full set? |
|---|---|---|---|
| `tools/events/page.tsx` (the ONLY consumer of `GET /api/v1/events`) | `useEvents({active, date_from?, date_to?})` | `active` from the Active/Inactive toggle (default **active**); `date_from`/`date_to` only when the user applies the optional date filter — **default unset**; `upcoming` never sent (dead param confirmed) | **Yes** — the page performs client-side type grouping/filtering over the returned array ("Type grouping is presentation only and happens in the page" — `useApi.ts`); a server-side default limit would silently truncate its list |
| Admin events page | `useAdminEvents(params?)` → `GET /api/v1/admin/events` | Optional filters (none by default) | **Yes** — a management list over all events |
| Calendar page | uses `GET /api/v1/calendar` month (NOT /events) | — | n/a (server-side month-bounded) |

## B. Current API contract — `GET /api/v1/events`

- Auth: JWT (`get_current_user`), any active user.
- Query parameters: `active: bool = True` (pass `false` for inactive-only), `date_from`/`date_to: date` (inclusive range-overlap on `[start_date, end_date]`; `422` when inverted), `upcoming: bool = False` (restricts to `end_date >= institution_today()`).
- Filters: applied in SQL by `get_all_events`; ordering `ORDER BY start_date` **only** — same-`start_date` rows have no deterministic tiebreak (heap-order dependent).
- Response: **`List[AcademicEventResponse]`** — a bare JSON array of 15 fields (`id, event_type, start_date, end_date, subject_id, elective_slot, resolved_subject_id/code/name, class_type, is_working_day, substitution_schedule_override, note, active`); `resolved_subject_*` is computed per-user by `ElectiveResolver.resolve_events` **after** the query.
- **No limit/offset/cursor/pagination of any kind exists on this path** (verified: no `.limit(` in `calendar_repo.py` or `admin_event_service.py`).
- Indirect boundedness that DOES exist elsewhere (for precision): the month view bounds by month ∩ semester; the dashboard bounds by `date_from` floor; the notification sweep bounds its *output* to 4 after a full load; `admin_dashboard.get_upcoming_events` is a separate `LIMIT`ed query. `GET /events` and `GET /admin/events` themselves are unbounded in both directions.

## C. Current scale + EXPLAIN evidence (live dev DB, 18 rows)

- Row counts: **18 active / 0 inactive** events; total relation ≈ 5.4 KB; per-event JSON response ≈ a few hundred bytes (15 fields).
- `EXPLAIN (ANALYZE)` for the exact loader shapes: default full read `Seq Scan → Sort(start_date)` — **0.033 ms**; upcoming shape (`active AND end_date >= today`) — **0.023 ms** (7 of 18 rows); overlap/month shape — 0.015 ms (measured in the EVT-006 audit, same queries re-verified). All well under any latency concern.
- Ordering-tie reality: `SELECT start_date … GROUP BY 1 HAVING count(*) > 1` → **0 ties in current data** (seeded events are one-per-subject-per-week). Ties become possible the moment two subjects share a start date (two quiz days on one date, an extra + a quiz, etc.).
- Growth characteristics: the **default contract reads only active rows**, so its size tracks concurrent active events (≈ tens per semester, not history). The **unfiltered internal callers** (`sync_event` is `active=True`; the day path, eligibility, and the sweep load *unfiltered*) scan total accumulated history including soft-deleted rows — that is the actual growth vector (rows never hard-deleted), still hundreds at a decade scale. `active=false` requests (the events page's inactive view, admin lists) also grow with history.

## D. Full-data consumers vs bounded-data consumers

**Genuinely require the full set (pagination would be WRONG):**
1. `EventSessionSynchronizer.sync_event` — the desired schedule for a date is computed from **all** active events (closures, cancellations, extras, quiz days); a truncated active set silently produces wrong `class_sessions` reality.
2. `eligibility_service` — quiz windows derive from the complete event set's interaction with cycle boundaries.
3. Notification sweep `_academic_events` — must see all active future events to pick the soonest 4.
4. `GET /events` events page — client-side type grouping over the complete list is the page's contract.
5. `GET /admin/events` — a management/audit list over all events; its Python-side filters need the full set.

**Bounded (already fine):** month view (month ∩ semester), dashboard summary (floor bound), admin dashboard upcoming (LIMIT), notification output (top-4).

## E. Risk analysis

- **Blind pagination would break correctness**: truncating the loader's output corrupts the synchronizer (wrong sessions), eligibility windows, the sweep's soonest-4, and truncates the events/admin pages. The loader is shared by consumers with incompatible requirements — pagination must never be added to the loader's defaults.
- **Offset/limit on GET /events**: safe only as an *opt-in* additive parameter; a *default* limit changes the response of every existing consumer (breaking). Offset paging is also unstable under concurrent inserts.
- **Keyset/cursor**: requires a response-envelope change (`List` → object with `next_cursor`) — a breaking API/contract change for the single frontend consumer; unjustified at current scale.
- **Mandatory date bounding**: breaks the events page (full active set by design) and the inactive-history view (no meaningful date bound).
- **Ordering nondeterminism**: real but latent — 0 ties today, frontend re-sorts client-side, and the synchronizer's desired-schedule ordering is its own deterministic comparator (priority, then event id — NOT the SQL order), so no correctness surface depends on the SQL tie order today.

## F. Candidate remediation options (with trade-offs)

| Option | Trade-off |
|---|---|
| 1. Optional `limit`/`offset` query params, **default unbounded**, clamped when present (inbox-style `clamp_inbox_page_size` convention) | Additive, backward-compatible, zero risk to internal consumers (they pass no limit); but useless until a client opts in — pure contract pre-provisioning |
| 2. Keyset cursor `(start_date, id)` | Breaking envelope change; strongest scalability shape; unjustified now |
| 3. Mandatory/default date bounding | Breaking for the events page + inactive view; reject |
| 4. Deterministic tiebreak `ORDER BY start_date, id` in the loader | One-line, zero contract change, removes the only genuine (latent) defect in EVT-007; safe for every consumer; pairs naturally with option 1 |
| 5. Separate bounded internal queries (e.g. sync loads only the span) | Code-level optimization already noted under EVT-006; out of EVT-007 scope |

## G. Verdict: **DEFER UNTIL TRIGGER**

No pagination is implemented now — and none is recommended until a measurable trigger fires. The unbounded behavior is **not an operational problem today** (18 active rows, ~few-KB responses, 0.02–0.03 ms plans, single frontend consumer that *wants* the full set, all correctness-critical internal consumers requiring completeness). The deep audit's LOW classification stands. When the trigger fires, implement Options **4 + 1 together** (deterministic tiebreak first, opt-in clamped limit/offset second) — nothing else.

## H. Measurable trigger conditions (any one)

1. `SELECT count(*) FROM academic_events WHERE active` exceeds **1,000** (default events-page payload would grow past ~100–200 KB and stop being a single cheap read), **or** total table rows exceed **10,000** (unfiltered internal loaders + inactive views scan history).
2. Measured p95 latency of `GET /events` (or `/admin/events`) exceeds **100 ms** attributable to serialization/transfer (not DB — plans stay sub-ms far beyond this).
3. A product requirement for windowed/infinite-scroll event lists (client-driven paging need).
4. The synchronizer's whole-active-set load shows up in profiling at scale (this is the EVT-006-adjacent code bounding, listed here only as a co-trigger signal).

## I. Implementation plan IF triggered (precise; NOT executed)

1. `calendar_repo.get_all_events`: change ordering to `.order_by(AcademicEvent.start_date, AcademicEvent.id)`; add optional `limit: Optional[int] = None, offset: int = 0` parameters applied only when `limit is not None` (`.limit(limit).offset(offset)`).
2. `events.py GET /events`: add optional query params `limit: Optional[int] = Query(None)` / `offset: int = Query(0, ge=0)`; when provided, clamp limit into `[1, 200]` reusing the inbox-clamp convention; pass through to the repo only when not `None`. **Response shape stays `List[AcademicEventResponse]`** — no envelope change, no default limit.
3. Internal consumers: **zero changes** — none pass `limit`, so the synchronizer/eligibility/sweep keep full-set semantics by construction.
4. Frontend: **zero changes** (sends no new params; behavior identical).
5. Tests: (a) pin backward compatibility — default `GET /events` returns ALL active events (count + ordering) exactly as before; (b) clamp bounds test (0/501 → clamped, non-int → 422 per FastAPI typing or clamp semantics, matching the inbox convention); (c) deterministic-tiebreak test (two events seeded with the same `start_date` come back ordered by `id`); (d) re-run the four EVT suites + `verify_post_remediation_flows.py` (27 checks) as the regression net — the synchronizer is untouched by construction, but the flow matrix proves it anyway.
6. Admin path (`GET /admin/events`): apply the same additive params only if the admin UI grows a paging need (no evidence today).

---

## Scope boundary

Strictly EVT-007. The synchronizer's whole-active-set load was noted only as a co-trigger signal (its bounding is the EVT-006 audit's code-level note); EVT-008+ untouched; no DB, code, contract, or frontend change made.
