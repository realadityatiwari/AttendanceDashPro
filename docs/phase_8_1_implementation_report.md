# Phase 8.1 — Canonical Analytics Read Model

Implementation report (2026-08-15). Authorized by the Phase 8.0 audit
(`docs/phase_8_0_attendance_analytics_audit.md`), which this phase implements
exactly as its contract. Backend infrastructure only: no analytics UI, no
AT-RISK, no trend product semantics, no new attendance/eligibility formulas, no
database mutation, no schema change, no migration.

---

## A. OBJECTIVE

Implement ONLY the backend analytics read-model contract established by Phase
8.0:

1. Extend `SubjectAttendanceSummary` additively with practical attendance % and
   the subject-level 75% optimization (must-attend / safe-skip) — reusing the
   canonical attendance engine's mathematics, never reproducing it.
2. Add `GET /api/v1/analytics/overview` — overall current (ERP recorded-only),
   overall forecast (pending-as-attended), pending count, a weekly read-model
   series, and per-subject analytics — all derived from the canonical
   `class_sessions` + `attendance_records` pipeline.
3. Fix the dashboard N+1/query inefficiencies (quiz snapshot, subject
   summaries, overlapping range scans) without changing the dashboard response
   contract or semantics.
4. Fix the import-time `date.today()` default on `/attendance/summary`.
5. Close the enrollment-scope inconsistency on `/attendance/summary/{code}`.

---

## B. PHASE 8.0 CONTRACT MAPPING

| Phase 8.0 contract | Phase 8.1 implementation |
|---|---|
| §L-1 `GET /api/v1/analytics/overview` | New endpoint + `AnalyticsService` + `app/schemas/analytics.py` |
| §L-2 / §H extend `SubjectAttendanceSummary` (practical %, subject-level 75% optimization) | Additive schema fields + `_build_subject_summary` in `AttendanceService` (engine untouched) |
| §7 ERP overall current = Σatt/Σrecorded | `AnalyticsService._overall` over one enrollment-scoped range scan |
| §8 overall forecast = Σ(att+pending)/Σtotal | Same method (canonical forecast semantics, no mutation) |
| §I weekly read-model (Monday-start weeks, recorded-only, null gaps) | `AnalyticsService._weekly_series` |
| §N.1 dashboard quiz-snapshot N+1 | `EligibilityService.get_quiz_eligibility_for_subjects` (shared `_evaluate_subject`, single canonical engine path) |
| §N.2 subject-summaries N+1 | `AttendanceRepository.get_subject_counts_for_user` + `AttendanceService.get_subject_summaries` (one grouped query) |
| §N.3 overlapping range scans | One shared scan in `DashboardService.get_summary` feeding Today/Overall/Weekly |
| §N.7 import-time `date.today()` default | `as_of_date: Optional[date] = None` resolved per request |
| §O-1 enrollment scope on `/attendance/summary` | 404 via `AttendanceRepository.is_enrolled` (same pattern as quiz endpoint) |
| §13 React duplications / §14 AT-RISK / §15 trend semantics | **NOT implemented** (documented non-goals, §R) |

---

## C. FILES CHANGED

| Layer | Files |
|---|---|
| Schemas | `app/schemas/attendance.py` (`OptimizationResult` moved above; `SubjectAttendanceSummary` gains `current_practical_pct`, `forecast_practical_pct`, `optimization`) · `app/schemas/analytics.py` **NEW** (`OverallAnalytics`, `WeeklyAnalyticsItem`, `AnalyticsSubjectItem`, `AnalyticsOverviewResponse`) |
| Services | `app/services/attendance_service.py` (`_build_subject_summary`, `_aggregate_counts`, `get_subject_summaries`) · `app/services/analytics_service.py` **NEW** · `app/services/eligibility_service.py` (`_evaluate_subject` extraction + `get_quiz_eligibility_for_subjects`) · `app/services/dashboard_service.py` (shared scan + batched summaries + batched quiz snapshot) |
| Repositories | `app/repositories/attendance_repo.py` (`get_subject_counts_for_user`) · `app/repositories/quiz_repo.py` (`get_quiz_schedules_for_subjects`) |
| Endpoints | `app/api/v1/endpoints/analytics.py` **NEW** (`GET /overview`) · `app/api/v1/endpoints/attendance.py` (runtime date + enrollment scope) · `app/api/api.py` (analytics router) |
| Scripts | `scripts/verify_phase_8_1.py` **NEW** |
| Docs | `docs/phase_8_1_implementation_report.md` **NEW** · `MASTER_ROADMAP.md` · `implementation_plan.md` · `task.md` · `walkthrough.md` |

**Untouched (hard boundaries):** attendance engines, eligibility engine,
calendar engine, event synchronizer, all schemas' existing fields, Track,
History, Quiz Eligibility, Calendar contracts, database schema, migrations,
auth architecture, and all frozen verifiers.

---

## D. SUBJECT ANALYTICS CONTRACT

`GET /api/v1/attendance/summary/{subject_code}` now returns the extended
`SubjectAttendanceSummary` (existing fields unchanged, all additive):

```jsonc
{
  "subject_code": "BCS-501",
  "lecture":   { "total": 18, "attended": 10, "missed": 0, "pending": 8 },
  "tutorial":  { "total": 6,  "attended": 1,  "missed": 0, "pending": 5 },
  "practical": { "total": 8,  "attended": 0,  "missed": 0, "pending": 8 },
  "current_lecture_pct": 55.6,
  "current_tutorial_pct": 16.7,
  "current_avg_pct": 36.1,
  "forecast_lecture_pct": 100.0,
  "forecast_tutorial_pct": 100.0,
  "forecast_avg_pct": 100.0,
  // NEW (Phase 8.1):
  "current_practical_pct": null,        // recorded-only; null when nothing recorded
  "forecast_practical_pct": 100.0,      // pending treated as attended
  "optimization": {
    "lecture_deficit": 0,               // must-attend (lectures)
    "tutorial_deficit": 3,              // must-attend (tutorials)
    "safe_skip_lecture": 3,             // safe-skip (lectures)
    "safe_skip_tutorial": 0,            // safe-skip (tutorials)
    "is_reachable": true
  }
}
```

- **Practical %** uses the canonical class-session/attendance-record pipeline
  (`get_subject_counts_up_to_date`), the same counting as lecture/tutorial —
  no quiz-window dependency, no separate lab engine. Current = att/(att+miss)
  (null when nothing recorded); forecast = (att+pending)/total. Pending stays
  Pending; cancelled sessions stay excluded per the frozen counting rules.
- **Subject 75% optimization** = `optimize_attendance` (the attendance engine's
  own exhaustive optimizer, byte-identical to legacy `optimizeLive`), invoked
  against the subject's semester-to-date L/T counts with the documented 75%
  academic target. `lecture_deficit`/`tutorial_deficit` = must-attend;
  `safe_skip_lecture`/`safe_skip_tutorial` = safe-skip. No probability, no risk
  score, no AI, no arbitrary threshold.
- **Backwards compatible**: all pre-existing fields and values are unchanged;
  the new fields are additive.

---

## E. ANALYTICS OVERVIEW API CONTRACT

`GET /api/v1/analytics/overview` (authenticated, enrollment-scoped, read-only,
deterministic; no raw ORM objects):

```jsonc
{
  "as_of": "2026-08-15",
  "semester_start": "2026-07-15",
  "semester_end": "2026-12-31",
  "overall": {
    "current_pct": 71.43,               // ERP: Σatt / Σrecorded (recorded-only)
    "forecast_pct": 81.4,               // Σ(att+pend) / Σtotal (pending attended)
    "attended": 60, "recorded": 84, "pending": 45, "cancelled": 0,
    "status": "WATCH"                   // canonical 3-state current banding
  },
  "weekly": [
    { "week_start": "2026-07-13", "current_pct": null, "attended": 0, "recorded": 0, "pending": 6 },
    { "week_start": "2026-07-20", "current_pct": 66.7, "attended": 8, "recorded": 12, "pending": 0 },
    // ... Monday-start weeks from semester start through today
  ],
  "subjects": [
    {
      "subject_code": "BCS-501", "subject_name": "...",
      "lecture": { ... }, "tutorial": { ... }, "practical": { ... },
      "current_avg_pct": ..., "forecast_avg_pct": ...,
      "current_practical_pct": ..., "forecast_practical_pct": ...,
      "optimization": { "lecture_deficit": ..., "tutorial_deficit": ...,
                        "safe_skip_lecture": ..., "safe_skip_tutorial": ...,
                        "is_reachable": ... }
    }
  ]
}
```

- Authorization: `get_current_user`; queries join `StudentEnrollment` on the
  authenticated user id. No client-provided user IDs. 401 unauthenticated.
- `overall.status` reuses the canonical `classify_attendance_status` (the
  frozen 3-state SAFE/WATCH/CRITICAL current banding) — AT-RISK is never
  emitted.
- `weekly` is a backend read-model structure only: Monday-start ISO weeks from
  the week of `semester_start` through the week of `as_of`, recorded-only
  current pct per week, `null` gaps when nothing recorded, pending surfaced
  separately, no future weeks, no trend/rolling/momentum semantics.

---

## F. PRACTICAL ATTENDANCE IMPLEMENTATION

- `AttendanceService._build_subject_summary` applies the engine's own
  percentage pattern to the canonical `P` bucket from
  `get_subject_counts_up_to_date` / `get_subject_counts_for_user`:
  `current_practical_pct = att/(att+miss)` (null when nothing recorded),
  `forecast_practical_pct = (att+pending)/total`.
- Verified live: BCS-551 (8 practical sessions, all pending) →
  `current_practical_pct: null`, `forecast_practical_pct: 100.0` — pending
  never converted to absent; cancelled excluded by the canonical counting
  rules; no quiz-window dependency (practical counts span the whole semester).

---

## G. 75% OPTIMIZATION IMPLEMENTATION

- The subject-level optimizer calls the attendance engine's `optimize_attendance`
  with the documented 75.0 target over the subject's L/T semester-to-date
  counts. The engine is untouched; the service composes its output.
- Edge semantics verified (check 10): lab-only subject (no L/T) → zero
  deficits, `is_reachable: false` (the engine's degenerate-total path, matching
  legacy); fully-recorded input (no pending) → zero deficits,
  `is_reachable: false` (engine early return — nothing left to decide); an
  unreachable input (attending all pending still below 75%) → deficits = all
  remaining, `is_reachable: false`.

---

## H. OVERALL CURRENT / FORECAST IMPLEMENTATION

- One enrollment-scoped range scan
  (`AttendanceRepository.get_sessions_with_status`, [semester_start, as_of])
  feeds `AnalyticsService._overall`:
  - `current_pct = Σatt / Σrecorded × 100` — pending excluded from the current
    denominator but counted and surfaced separately (`pending` field); never
    converted to absent.
  - `forecast_pct = Σ(att+pend) / Σtotal × 100` — the canonical forecast
    semantics (pending treated as attended); no records are mutated.
  - Cancelled sessions excluded per the frozen counting rules.
- **Not** an average of subject percentages — class-weighted (ERP), verified
  equal to the dashboard overall and the history summary (check 16).

---

## I. WEEKLY READ-MODEL DEFINITION (ACTUALLY IMPLEMENTED)

- Buckets: Monday-start weeks (`week_start = date - weekday()`) from the week
  containing `semester_start` through the week containing `as_of` (today).
- Each bucket: `attended`, `recorded`, `pending` counts over the canonical
  scan; `current_pct = att/recorded × 100`, or `null` when nothing recorded in
  that week (an explicit gap).
- No rolling windows, no semester-trend semantics, no percentage-change
  windows, no momentum, no AT-RISK (Phase 8.0 §15 respected).

---

## J. DASHBOARD N+1 FIXES

| Prior implementation | After Phase 8.1 |
|---|---|
| `_build_quiz_snapshot`: per-subject `get_quiz_schedules_for_subject` + per-subject `get_quiz_eligibility` (each re-fetching events, cycle policy, schedules) | One `get_quiz_schedules_for_subjects` + one `get_quiz_eligibility_for_subjects` (events/cycle/schedules fetched once; each subject evaluated by the same canonical `_evaluate_subject` → `evaluate_quiz_eligibility`) |
| `_subject_summaries`: one `get_subject_counts_up_to_date` query per subject (9 queries) | One `get_subject_counts_for_user` grouped query → `get_subject_summaries` (identical per-subject summaries) |
| `_build_today`/`_build_overall`/`_build_weekly`: up to 4 overlapping `get_sessions_with_status` range scans | One shared scan in `get_summary`; each builder slices its own date window (bounds re-applied exactly) |
| Query count: ~54 per dashboard load | **23 per dashboard load** (measured with a SQLAlchemy cursor counter); `/analytics/overview` itself = 8 queries |

- Response contract unchanged: `DashboardSummaryResponse` shape and values are
  byte-identical (verified: check 12 compares every overall field; check 13
  recomputes the quiz snapshot from per-subject single-call endpoints; the
  frozen 7.2 verifier's dashboard consistency checks 19–22 all pass).

---

## K. RUNTIME DATE FIX

- `GET /attendance/summary/{code}`: `as_of_date` default changed from the
  import-time `date.today()` to `Optional[date] = None`, resolved per request
  (`as_of_date or date.today()`). Explicit `as_of_date` behavior unchanged.
- Verified (check 14): default call == explicit-today call; a past `as_of_date`
  returns fewer classes; endpoint semantics otherwise identical.

---

## L. ENROLLMENT-SCOPE FIX

- `GET /attendance/summary/{code}` now rejects unenrolled subjects with 404
  ("Subject not found") via `AttendanceRepository.is_enrolled` — the same
  authorization pattern the quiz-eligibility endpoint uses (no parallel
  mechanism). A student can no longer obtain analytics for a subject they are
  not enrolled in.
- Verified (check 15): an unenrolled user's request → 404.

---

## M. PERFORMANCE FINDINGS

- Dashboard load: **~54 → 23 queries** (one scan instead of four; one grouped
  subject-count query instead of nine; one batched eligibility pass instead of
  per-subject evaluations each re-fetching events/policy/schedules). Same
  logical result (verified against single-call recomputation + the frozen
  verifiers).
- `/analytics/overview`: 8 queries total (academic context, one range scan, one
  grouped subject-count query, one enrolled-subjects query, plus the async
  session overhead) — no N+1.
- No new indexes/migrations; no blind optimization — the batched paths reuse
  the exact repository/service boundaries.

---

## N. SECURITY FINDINGS

- All analytics reads are authenticated (`get_current_user`) and scoped to the
  authenticated student's enrollments (SQL `StudentEnrollment` join on
  `user_id`); no endpoint accepts a client user ID.
- `/attendance/summary/{code}` enrollment scope closed (404 for unenrolled),
  matching the quiz endpoint.
- Verified (check 2): the zero-record student sees only their own dataset;
  cross-user isolation is unchanged.

---

## O. VERIFICATION RESULTS

`backend/scripts/verify_phase_8_1.py` — **22/22 PASS**:

1. analytics overview authentication (401) ✓
2. enrollment scoping (subjects == enrolled; zero-record student own dataset) ✓
3. overall current = Σatt/Σrecorded (recorded-only) ✓
4. overall forecast = Σ(att+pend)/Σtotal ✓
5. pending count explicit ✓
6. overview per-subject == extended /attendance/summary (no duplicate calc) ✓
7. practical % (all-pending lab → current null, forecast 100) ✓
8/9. subject 75% must-attend + safe-skip == engine optimizer ✓
10a. lab-only optimizer zeros ✓ · 10b. fully-recorded early-return ✓ ·
    10c. unreachable deficits ✓
11. weekly read model (Monday-start weeks, null gaps, no future weeks) ✓
12. dashboard contract unchanged (same shape + values) ✓
13. quiz snapshot == recomputed per-subject eligibility (batch == single-call) ✓
13b. dashboard query count bounded (≤ 25; measured 23) ✓
14. runtime-date behavior ✓
15. enrollment protection (404) ✓
16. no duplicate attendance calculations (overview == dashboard == history) ✓
17. exact database baseline restored ✓
18. frozen 7.2 invariants (current-cycle, BCS-054 Q3 = 2026-10-23, labs 404) ✓

Static: `python -m compileall app scripts` PASS · `npx tsc --noEmit` PASS
(0 errors, frontend untouched).

---

## P. DATABASE BASELINE BEFORE / AFTER

| Table | Before | After |
|---|---|---|
| academic_events | 18 | 18 |
| class_sessions | 684 (0 cancelled, 0 extra) | 684 (0 cancelled, 0 extra) |
| attendance_records | 89 | 89 |
| student_enrollments | 18 | 18 |
| subjects | 9 | 9 |
| quiz_schedules | 18 (18 SCHEDULED) | 18 (18 SCHEDULED) |
| users | 30 | 30 |
| admins | 1 | 1 |

BCS-054 Quiz III = **2026-10-23** (unchanged, verified). **Zero mutation** —
SELECT-only throughout (the verifier's only state changes are in-memory/rollback
or, for the frozen 7.2 regression run, its own documented cleanup discipline).

---

## Q. FROZEN REGRESSION RESULTS

- `verify_phase_6_5.py` — **23/23** PASS
- `verify_phase_6_6.py` — **36/36** PASS
- `verify_phase_6_7.py` — **31/31** PASS
- `verify_phase_7_1.py` — **26/26** PASS
- `verify_phase_7_2.py` — **26/26** PASS

No old assertion weakened. The Phase 8.1 changes (service refactors + batched
paths) preserve every frozen contract — the batch eligibility path returns
results identical to the single-call path (proven in check 13 and by the 7.2
verifier's dashboard consistency checks).

---

## R. EXPLICIT NON-GOALS (NOT implemented in Phase 8.1)

- Analytics UI / dedicated analytics page / any frontend change (the new
  backend contract will support future frontend consumption; the Phase 8.0
  React duplications — `WeeklyAttendanceCard` day-bar %, `SubjectAttendanceCard`
  banding/cycle=1, dead `TodayClassesCard`/`FormulaCard` — are left for the
  later frontend phase).
- AT-RISK (no approved definition; the 3-state current banding stays
  authoritative).
- Trend product semantics (rolling, semester trend, momentum, weekly risk,
  percentage-change windows) — the weekly series is a read-model structure only.
- New attendance/eligibility formulas, probability/risk/AI scores, forecast-
  impact deltas (legacy `calcForecastImpact` is not ported — not in the Phase
  8.1 contract; documented in Phase 8.0 as a legacy gap for later).
- Any DB migration, schema change, seed, or data mutation.

---

## S. DEFERRED PRODUCT DECISIONS

- **T-1 AT-RISK band** — needs a product-approved definition before any 4-state
  taxonomy can ship.
- **T-2 Trend scope** — which (if any) trend series become product features.
- **T-3 Dedicated Analytics page** — whether the overview deserves a route in a
  later frontend phase.
- **T-4 Multi-class forecast scenarios** ("if you attend the next N classes…")
  — new derived display, needs approved wording/numbers.
- **Q-D9** (quiz-day attendance without a session) and **rule G** (student
  event capability) — unchanged, separate product decisions.

---

## T. PHASE 8.2 RECOMMENDATION

Frontend consumption of the Phase 8.1 read model: render the extended subject
summary (practical %, must-attend/safe-skip) on the Subjects page, surface
overall forecast + weekly series from `/analytics/overview`, replace the
duplicated card banding and hardcoded cycle with backend fields, and remove the
dead components — all within the existing design system. A dedicated Analytics
page (T-3) and AT-RISK (T-1) only after their product decisions.

---

**HARD STOP — Phase 8.1 complete. No commit made. Phase 8.2 NOT STARTED.**
