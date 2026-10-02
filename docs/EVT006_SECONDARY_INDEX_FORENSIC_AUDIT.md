# EVT-006 Forensic Audit — `academic_events` Secondary Indexes

**Date:** 2026-10-03
**Scope:** EVT-006 ONLY ("`academic_events` has zero secondary indexes", `docs/EVENTS_BACKEND_DEEP_AUDIT_REPORT.md` §14) — re-audited against the post-remediation tree (EVT-003/001/002/004/005 in the working tree) and the live dev DB (PostgreSQL 16.15, alembic `b9c0d1e2f3a4`).
**Mode:** READ-ONLY. No code, migration, test, data, config, or frontend change. `EXPLAIN`/`EXPLAIN ANALYZE` on `SELECT`-only statements; one session-local `SET enable_seqscan = off` used purely to reveal which index plans the planner *could* choose (connection-local, discarded).

---

## 1. Query inventory (every reader of `academic_events`)

Application code — 12 distinct query sites (all ORM unless noted):

| # | Site | Access pattern (exact predicates / order) | Frequency |
|---|------|-------------------------------------------|-----------|
| Q1 | `repositories/calendar_repo.py` `get_all_events()` (central loader) | `SELECT *` — optional `active = ?`; optional overlap `end_date >= :from AND start_date <= :to`; optional `upcoming` → `end_date >= today`; **`ORDER BY start_date`** (no LIMIT) | Every events read: GET /events, calendar month/today/day, dashboard, notification sweep `_academic_events`, **`EventSessionSynchronizer.sync_event` on EVERY event mutation (`active=true`)**, admin event list |
| Q2 | `repositories/event_repo.py` `get_by_id` | PK `id = ?` | Every by-id mutation/read |
| Q3 | `repositories/event_repo.py` `exists_active_duplicate` | `event_type = ? AND start_date = ? AND end_date = ? AND active AND (subject_id = ? OR IS NULL) AND (class_type = ? OR IS NULL) [AND id <> :self]` | Every event create/update |
| Q4 | `repositories/admin_quiz_repo.py` `find_quiz_day_event` | `event_type='QUIZ_DAY' AND subject_id = ? AND start_date = ? AND end_date = ? [AND elective_slot = ? / IS NULL] [AND active]` | Quiz-manager ensure/retire, admin read model `has_active_event` |
| Q5 | `repositories/admin_quiz_repo.py` `count_active_quiz_day_events` | `event_type='QUIZ_DAY' AND active` | Ops/verifier |
| Q6 | `repositories/quiz_repo.py` `get_effective_quiz_dates_for_subjects` | `event_type='QUIZ_DAY' AND active AND (subject_id IN (...) OR elective_slot IN (...)) ORDER BY start_date, id` | Every quiz-eligibility read (dashboard/eligibility) |
| Q7 | `repositories/user_repo.py` (`first_quiz_date`) | `SELECT min(start_date) FROM academic_events JOIN student_enrollments ON enrollments.subject_id = academic_events.subject_id WHERE enrollments.user_id = ? AND event_type='QUIZ_DAY' AND active` | Student profile/context |
| Q8 | `services/student_context_service.py` `_load_first_quiz_date` | identical shape to Q7 | Per student-context load |
| Q9 | `services/attendance_service.py` `quiz_day_subjects` | `SELECT subjects.id JOIN academic_events ON subject_id WHERE event_type='QUIZ_DAY' AND active AND start_date <= :d AND end_date >= :d` | Attendance marking (per mutation, as a subquery) |
| Q10 | `repositories/admin_dashboard_repo.py` `count_active_events` | `active` (count) | Admin dashboard |
| Q11 | `repositories/admin_dashboard_repo.py` `count_upcoming_active_events` / `get_upcoming_events` | `active AND end_date >= today` (+ `LEFT JOIN subjects`, `ORDER BY start_date, id LIMIT :n`) | Admin dashboard |
| Q12 | `repositories/notification_repo.py` `_live_event_ref_clause` / `orphaned_event_ref_clause` | `EXISTS (SELECT 1 FROM academic_events WHERE id = notifications.event_id)` — **PK** | Every inbox read/badge count/reconcile |

Schema-level (not a query but a real access path): the FK `academic_events_subject_id_fkey` — **PostgreSQL does not auto-index FK sides**, so every hard-`DELETE` of a `subjects` row performs a `subject_id = ?` scan of `academic_events` (Q13).

Scripts/migrations (operational, not request paths): seed scripts (full-table baseline writes), read-only audit forensics (PK joins / full scans, deliberate), `restore_dev_baseline.py` (counts), and migration `b9c0d1e2f3a4`'s duplicate-audit SQL (3 GROUP BY checks over `active`-predicated subsets — pre-deploy only). `materialize_quiz_day_sessions.py` reads `quiz_schedules`, not `academic_events`.

## 2. Current index inventory on `academic_events`

| Index | Definition | Origin |
|---|---|---|
| `academic_events_pkey` | unique btree `(id)` | initial schema |
| `uq_academic_events_quiz_day_identity` | unique btree `(subject_id, elective_slot, start_date)` `NULLS NOT DISTINCT` **WHERE `active AND event_type='QUIZ_DAY'`** | EVT-004 |
| `uq_academic_events_global_range` | unique btree `(event_type, start_date, end_date)` `NULLS NOT DISTINCT` **WHERE `active AND subject_id IS NULL`** | EVT-004 |

That is all. Consequences: **no general index on `subject_id`** (the FK is unindexed — only the QUIZ_DAY subset is covered, via the partial index's leading column), **none on `start_date`/`end_date`**, none on `active`/`event_type` outside the two partial predicates. `pg_stat_user_tables`: 22,164 seq scans / 615 index scans lifetime — consistent with a tiny table where seq scans are optimal.

## 3. Query-plan evidence (live dev DB, 18 rows, all read-only)

`EXPLAIN (ANALYZE)` at current volume — **every Q1–Q13 shape is a Seq Scan**; execution 0.008–0.121 ms; the largest plan (Q7/Q8 hash join across enrollments) costs ~0.12 ms. Representative plans:

- Q1/Q2/Q3(calendar): `Sort (start_date) → Seq Scan` — 0.027–0.084 ms.
- Q11 upcoming (with LEFT JOIN subjects): `Limit → Sort → Seq Scan + Memoize → subjects_pkey` — the subject side is already PK-served.
- Q12 notification EXISTS: PK hash join — 0 for live rows, as designed.

`SET enable_seqscan = off` (session-local; reveals the best *available* index plan per shape — i.e. what the planner could do at scale with today's indexes):

- **Q3 duplicate check, QUIZ_DAY shape** → `Index Scan using uq_academic_events_quiz_day_identity` (Index Cond `subject_id + start_date`; `end_date/class_type/id` heap-filtered). ✅ EVT-004 already serves it.
- **Q4 `find_quiz_day_event`** → same index (identical leading columns). ✅
- **Q6 effective quiz dates** → same partial index (whole-index scan under its predicate, pre-ordered by `start_date` within the index). ✅
- **Global duplicate shape** (`HOLIDAY`, subject NULL) → `Index Scan using uq_academic_events_global_range`. ✅
- **Calendar/upcoming family** (`active AND end_date >= ? ORDER BY start_date`) → **still a Seq Scan even with seqscan disabled** — no existing index can serve the sort or the range. ⚠️ This is the one family with zero index coverage.
- **`WHERE subject_id = ?` (FK-delete / extra-family duplicate checks)** → **still a Seq Scan with seqscan disabled** — no index covers non-QUIZ_DAY subject lookups. ⚠️

## 4. Volume assessment (is EVT-006 operational now?)

No. 18 rows; every query ≤ 0.12 ms; the whole-table load that runs on every event mutation (`sync_event`) reads 18 narrow rows in ~0.03 ms. Growth is bounded by institutional reality (≈ 18 events/semester; even a decade of history is hundreds of rows). Seq scans of a thousand narrow rows remain sub-millisecond. **EVT-006 is a scalability/hardening concern, exactly as the deep audit classified it (LOW, "none measurable today").** The audit's synchronizer note ("loads ALL active events on every mutation") is a *code-bounding* opportunity (`get_all_events` already accepts `date_from`/`date_to`), not an index problem — and is out of scope here.

## 5. Interaction with EVT-004 (would candidates duplicate or undermine them?)

- The EVT-004 partial indexes **already own** the highest-value shapes: QUIZ_DAY identity/authority lookups (Q3/Q4/Q6) and global duplicate checks. Any new general index on `(event_type…)` or a composite leading with `subject_id, start_date` would be **redundant for those subsets**.
- Adding ordinary (non-unique) indexes can never undermine unique enforcement — it only adds planner options and write amplification.
- If added later, the candidates must be the **narrow general complements** (`(start_date)`, `(subject_id)`), which overlap the partial indexes only trivially (a few heap tuples share leading-column values) and never conflict.
- The deliberately-unconstrained extra family (multiple same-key extras are a pinned contract) must NOT gain a unique index — none is proposed.

## 6. Candidate indexes (with justification evidence)

| Candidate | Columns | Would serve (evidence) | Justified **now**? | Justified at scale? |
|---|---|---|---|---|
| A | `(start_date)` | The calendar/upcoming/dashboard/sweep family (Q1/Q10/Q11) and overlap reads — the only uncovered family; enables index-ordered reads (sort elimination) and the `start_date <= :to` bound. Proved uncovered by seqscan-off plans. | **No** — 18 rows; sort is a 25 kB quicksort (~0.02 ms); zero measured benefit. | **Yes, conditionally** — when the events list/dashboard sits on hot request paths at meaningful volume. Recommend `(start_date)` **INCLUDE nothing** (narrow rows; heap fetch needed for payload anyway). |
| B | `(subject_id)` | The unindexed FK side (Q13 subject hard-delete scan); extra-family duplicate checks (Q3 non-quiz shapes); build-side of the enrollment joins (Q7/Q8) and `attendance_service` quiz-day subquery (Q9) at scale. | **No** — FK deletes of subjects are not an app path (soft-delete convention); duplicate checks are once-per-mutation. | **Yes, conditionally** — standard FK-side hardening once volume (or subject-deletion tooling) makes the scan real. |
| C | `(event_type) WHERE active` | Counts (Q5/Q10) — but the QUIZ_DAY subset is already index-only-servable via the quiz identity partial index; HOLIDAY-family counts are trivial. | **No** — no evidence of a plan that needs it beyond what EVT-004 provides. | **No** — retain as "not recommended" unless a real count-heavy workload appears. |

**Recommendation: NO CHANGE.** Do not add indexes today. Neither A nor B is justified by measured evidence at the current data volume; the planner is *correct* to seq-scan 18 rows, and both existing EVT-004 partial indexes already cover the integrity-critical and quiz-authority paths. EVT-006 should remain open as a **conditional hardening item** with pre-approved candidates A and B, to be implemented when a trigger fires — see the verification plan in §8. The trigger should be evidence-based (either of): `academic_events` exceeding ~5,000 rows, or measured per-request latency attribution showing the events-list/calendar reads dominating, or a feature that hard-deletes subjects.

## 7. Risk / cost analysis (of implementing now vs. later)

- Cost of adding now: two extra indexes to maintain on every event write (trivial at this volume), migration + deployment + test surface (the EVT-004 tests assert exact index *names* — a new migration is additive, but every index must be re-audited against predicates), and planner-behavior churn in every EVT-00x verifier for zero measured gain.
- Risk of deferring: none today (plans are optimal); at scale, the uncovered families degrade linearly — bounded by the trigger.
- The one hard requirement captured for the future migration: `CREATE INDEX CONCURRENTLY` in production (see §8) so the events table never takes an ACCESS EXCLUSIVE lock while serving reads.

## 8. Implementation plan IF the trigger fires (not now)

1. Migration (new revision, parent `b9c0d1e2f3a4`): `op.create_index("ix_academic_events_start_date", "academic_events", ["start_date"], postgresql_concurrently=True)` and `op.create_index("ix_academic_events_subject_id", "academic_events", ["subject_id"], postgresql_concurrently=True)` inside a `transaction_per_migration`/`autocommit_block` context (CONCURRENTLY cannot run in a transaction) — plain `create_index` is acceptable for dev where the table is tiny.
2. Do NOT touch the EVT-004 indexes; assert in the migration's docstring that the new indexes are non-unique complements.
3. Focused verification: (a) `test_evt004_uniqueness_constraints.py::test_t13` extended (or a sibling) asserting the new index names exist *and* the five EVT-004 names still exist with unchanged predicates (`pg_get_indexdef`); (b) `EXPLAIN` snapshot test that the duplicate-guard shapes still prefer the EVT-004 partial indexes (they remain the better selectivity); (c) re-run EVT-003/001/002/004 suites + `verify_post_remediation_flows.py` (index-only additions cannot change semantics, so the full flow matrix is the regression net); (d) `pg_stat_user_tables` before/after to confirm `idx_scan` uptake on the hot paths.
4. Deployment: run the migration via `scripts/apply_lifecycle_migration_prod.py` during low traffic; `CONCURRENTLY` keeps reads/writes serving (one failed build leaves an `INVALID` index — check `pg_index.indisvalid` and `DROP INDEX CONCURRENTLY` + retry on failure).

---

## 9. Scope boundary

Everything above is confined to `academic_events`. Adjacent observations explicitly **out of scope** (noted, not audited): `notifications.event_id` has no index (the reconcile delete filters `kind + occurrence_key` without the leading `user_id`, and the read filters do an `EXISTS` per row — a notifications-side question, unrelated to EVT-006); the synchronizer's whole-active-set load is a code-bounding opportunity (`date_from`/`date_to` already exist on the repo API). Neither was changed, per the audit boundary.

**Final verdict for EVT-006: evidence-based NO-CHANGE.** The finding is real (two uncovered access-path families) but operationally meaningless at the current and realistically projected volume; the EVT-004 indexes already serve every integrity-critical path; candidates A/B are pre-approved and documented for the day the trigger fires.
