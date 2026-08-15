# Phase 8.0 — Attendance Analytics & Intelligence: Audit / Contract Design

Read-only audit (2026-08-15). **No implementation.** No business-logic change. No
database mutation. No analytics endpoint or UI created. This document establishes
the exact architectural and mathematical contract for Phase 8 (Attendance
Analytics / Intelligence) before any implementation begins.

---

## A. PHASE RESULT

**PASS** — the audit completed against the live repository and database without
modifying either. All read-only/static verification is green and the database is
at the exact Phase 7.2 baseline (see §U and §V). Phase 8.1 (implementation) is
**NOT started** (HARD STOP, §W).

---

## B. CURRENT ANALYTICS ARCHITECTURE

There is **no dedicated "analytics" layer** in the current system. What exists is
a set of *read models* that aggregate the canonical engines:

```
class_sessions
    ↓ (outer-join, per student)
attendance_records
    ↓
canonical attendance engine (compute_subject_stats, optimize_attendance)
        └─ attendance_service.get_summary            → /attendance/summary/{code}
        └─ eligibility_engine.evaluate_quiz_eligibility (window-bounded)
                └─ eligibility_service.get_quiz_eligibility → /quiz-eligibility/{code}/{cycle}
    ↓
dashboard_service (aggregation read model)            → /dashboard/summary
    ↓
API read models (Pydantic schemas)
    ↓
React presentation (cards render the read models)
```

Key property: every percentage shown today originates in one of the canonical
engines or in a service-level aggregation over the same raw `class_sessions` +
`attendance_records` rows the engines consume (verified byte-identical in
Phase 7.2 checks 5–9). The dashboard service is the de-facto analytics
aggregation point, but it performs no per-subject percentage mathematics of its
own — it delegates subject percentages to `AttendanceService.get_summary`
(`attendance_engine.compute_subject_stats`) and quiz state to
`EligibilityService` (verified: `dashboard_service.py`).

### Where each surface gets its numbers (current, live)

| Surface | Backend source | Engine |
|---|---|---|
| Overall % (Home) | `dashboard_service._build_overall` — Σatt/Σrecorded over [semester_start, today] | service-level sum over canonical rows (ERP formula) |
| Weekly % (Home) | `dashboard_service._build_weekly` — Σatt/Σrecorded over [week_start, week_end] + prev-week delta | service-level sum |
| Today (Home) | `dashboard_service._build_today` — per-day statuses + attended/total | canonical rows |
| Subject cards (Subjects) | `attendance_service.get_summary` → `compute_subject_stats` | attendance engine |
| Quiz snapshot (Home) | `dashboard_service._build_quiz_snapshot` → `eligibility_service.get_quiz_eligibility` per subject | eligibility engine |
| Quiz Eligibility page | `eligibility_service.get_quiz_eligibility` | eligibility engine |
| History summary | `attendance_service.get_history` summary (aggregate FILTER query) | service-level sum |
| Track daily | `attendance_service.get_daily_sessions` | canonical rows |
| Calendar month session counts | `calendar_service.get_month_view` (`get_sessions_with_status`) | canonical rows |

---

## C. CANONICAL SOURCE-OF-TRUTH CHAIN

The architecture is frozen and must remain:

```
class_sessions
    ↓
attendance_records
    ↓
canonical attendance/counting engines
    (attendance_engine.compute_subject_stats · optimize_attendance ·
     meets_attendance_target · eligibility_engine.evaluate_quiz_eligibility)
    ↓
analytics/intelligence layer            ← Phase 8.1 consumer (additive read model)
    ↓
API read model
    ↓
React presentation
```

Rules confirmed by inspection:

1. **No second attendance engine exists or may be created.** Every current
   consumer (dashboard, subjects, quiz, history, track, calendar) reads counts
   or engine outputs; none re-derives `compute_subject_stats` mathematics.
2. **No second calendar enumeration exists.** `class_sessions` IS the
   teaching-day-resolved effective schedule (Phase 7.2 Q-D6 decision — the
   session table is materialized only on engine teaching days; closures cancel;
   extras exist only on working days). A Phase 8 analytics layer must count
   sessions/records through the same repositories (`attendance_repo`), never a
   fresh weekday enumeration.
3. **No second eligibility calculation exists.** Quiz eligibility is computed
   exclusively by `eligibility_engine.evaluate_quiz_eligibility` (window
   bounded via `calendar_engine.get_attendance_window`).
4. **React performs no business math today.** `WeeklyAttendanceCard` computes a
   display percentage per day bar (attended/recorded) and `SubjectAttendanceCard`
   applies its own color thresholds — these are *presentation* transforms over
   backend-provided counts, flagged in §N as duplication to remove, not as a
   second engine. No React component recomputes current/forecast/eligibility
   percentages from raw session data.

---

## D. EXISTING ANALYTICS INVENTORY

Full inventory of every place attendance analytics are currently computed or
displayed (metric × definition × semantics):

| # | Metric | Location | Mathematical definition | Pending | Cancelled | Extras | Practicals | L/T separation | Semester-bounded | Quiz-window-bounded | Legacy parity | Canonical engine | React duplication |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Overall % (Home) | `dashboard_service._build_overall` | Σ attended / Σ recorded × 100 over [semester_start, today] | excluded from denom., counted separately | excluded | included | included | no | yes (start → today) | no | = `computeCurrentOverallAttendance` (ERP) | service-level sum over canonical rows | no (renders value) |
| 2 | Weekly % (Home) | `dashboard_service._build_weekly` | Σ att / Σ recorded over [week_start, week_end] | excluded from denom. | excluded | included | included | no | week-bounded | no | = ERP formula over a range | service-level sum | day-bar % recomputed in `WeeklyAttendanceCard` (display) |
| 3 | Weekly delta | `_build_weekly.delta_pct` | weekly_pct − previous_week_pct | — | — | — | — | — | — | — | legacy `getSubjectStatus` had no delta (new) | service-level | no |
| 4 | Today attended/total | `dashboard_service._build_today` | Σ ATTENDED / Σ non-cancelled sessions for today | separate | excluded | included | included | no | day | no | legacy today classes | canonical rows | no |
| 5 | Subject current L/T % | `attendance_service.get_summary` | att / (att+miss) × 100 per type | excluded | excluded | included | counts only (no pct) | yes | yes (≤ today) | no | = `calcCurrentPct` / `computeSubjectStats` | attendance engine | no |
| 6 | Subject current avg % | `compute_subject_stats` | (L% + T%) / 2 (L-only when no T) | excluded | excluded | included (via counts) | excluded from avg | yes | yes | no | = `calcAvgPct` | attendance engine | no |
| 7 | Subject forecast L/T % | `compute_subject_stats` | (att + pending) / total × 100 | **included as attended** | excluded | included | counts only | yes | yes | no | = `calcForecastPct` | attendance engine | no |
| 8 | Subject forecast avg % | `compute_subject_stats` | (forecast L% + forecast T%) / 2 | included | excluded | included | excluded | yes | yes | no | = `calcAvgPct` | attendance engine | no |
| 9 | Practical counts | `compute_subject_stats.practical` | ClassCounts total/att/miss/pending | separate | excluded | included | **counts only — no practical % exposed** | — | yes | no | legacy exposed `current.practical`/`forecast.practical` | attendance engine | no |
| 10 | Quiz window L/T % | `eligibility_engine` | att / total × 100 within window (pending in denominator) | **included in denom.** | excluded | included | excluded (labs 404) | yes | window | **yes (ADR-010)** | = legacy window semantics | eligibility engine | no |
| 11 | Quiz state | `eligibility_engine` | ELIGIBLE / RECOVERABLE / NOT_ELIGIBLE / UNRESOLVED from criteria OR | — | — | — | — | yes | — | yes | = legacy Quiz Engine | eligibility engine | no |
| 12 | Must-attend / safe-skip (quiz window) | `eligibility_engine.optimization` | `optimize_attendance` deficit/safe-skip within window | pending are the lever | excluded | included | excluded | yes | window | yes | = `optimizeLive` | attendance engine | no |
| 13 | History summary | `attendance_service.get_history` summary | total/att/miss/pending/cancelled + pct (Σatt/Σrecorded) | separate | separate state | included | included | no | yes | no | = ERP range sum | service-level | no |
| 14 | Status banding (Home) | `dashboard_service.classify_attendance_status` | SAFE ≥ 80 · WATCH ≥ 60 · CRITICAL < 60 on **current** avg | — | — | — | — | — | — | — | legacy `getSubjectStatus` used **forecast**; S4.1 reconciled to current | service-level (documented S4.1) | `status.ts` maps colors only |
| 15 | Quiz snapshot counts | `dashboard_service._build_quiz_snapshot` | eligible/attention/not_eligible counts over quiz-applicable subjects | via engine | via engine | via engine | excluded | yes | — | yes | = legacy quiz dashboard summary | eligibility engine | no |
| 16 | Attention required | `dashboard_service._build_attention_required` | subjects with WATCH/CRITICAL + current/forecast pct | via summary | via summary | via summary | included | via summary | yes | no | legacy attention list | attendance engine | no |
| 17 | Best / needs-attention subject (week) | `_build_weekly` | max/min current_avg_pct | via summary | via summary | via summary | included | via summary | week | no | legacy subject sort | attendance engine | no |
| 18 | Overall forecast % | **NOT EXPOSED** | legacy `computeForecastOverallAttendance` (Σ(att+pending)/Σtot) | — | — | — | — | — | — | — | **legacy-defined; missing in Python** | — | — |
| 19 | Subject-level 75% must-attend/safe-skip (non-quiz) | **NOT EXPOSED** | legacy `optimizeLive` with `policies.attendance` target (75%) | — | — | — | — | — | — | — | **legacy-defined; missing in Python** | — | — |
| 20 | Practical % (current/forecast) | **NOT EXPOSED** | legacy `current.practical` / `forecast.practical` | — | — | — | — | — | — | — | **legacy-defined; missing in Python** | — | — |
| 21 | Forecast-impact tooltip ("if you attend this…") | **NOT EXPOSED** | legacy `calcForecastImpact` | — | — | — | — | — | — | — | **legacy-defined; missing in Python** | — | — |
| 22 | Time-series / trend series | **DOES NOT EXIST** | none anywhere (only weekly delta) | — | — | — | — | — | — | — | none in legacy either | — | — |
| 23 | Risk states SAFE/WATCH/**AT-RISK**/CRITICAL | **DOES NOT EXIST** | roadmap §8 names AT-RISK; no definition anywhere | — | — | — | — | — | — | — | legacy 3-state `getSubjectStatus` (SAFE/WARNING/CRITICAL) | — | — |

### Conflicting / duplicated calculation paths (flagged, NOT fixed)

1. **Two banding schemes in React.** `dashboard_service` banding: SAFE ≥ 80 /
   WATCH ≥ 60 / CRITICAL < 60 (documented S4.1 + legacy `pctColor` target±15/±5).
   `SubjectAttendanceCard.tsx` applies its own: ≥75 green / ≥65 amber / <65 red
   for the progress bar. These disagree at e.g. 70% (dashboard = WATCH, card =
   amber/red boundary differs) and are both presentation thresholds — but the
   divergence should be resolved in Phase 8.1 by consuming the backend status
   field rather than duplicating bands in React.
2. **`WeeklyAttendanceCard` recomputes the day percentage** (`day.attended /
   day.recorded * 100`) from counts the backend already aggregated. Display-only,
   but it is React-side division of backend counts — candidate to be replaced by
   a backend-provided per-day pct in the analytics read model.
3. **`SubjectAttendanceCard` hardcodes `cycle = 1`** for its quiz-eligibility
   fetch — it will always show Quiz I eligibility regardless of the
   date-aware current cycle (Phase 7.2 behavior). Presentation inconsistency,
   not a math conflict; the page is a candidate to consume
   `GET /quiz-eligibility/current-cycle` like the Quiz Eligibility page does.
4. **Dead components** `TodayClassesCard.tsx` (uses `toISOString()` — UTC "today"
   defect) and `FormulaCard.tsx` are unreferenced (only self-matches). No
   consumer; not part of any analytics path.

---

## E. METRIC DEFINITIONS (canonical, current, frozen)

The following are the authoritative formulas as implemented and verified. Phase
8.1 may consume or extend them — it may not silently change them.

- **Current % (per type)** = `attended / (attended + missed) × 100`; `null` when
  nothing recorded. Pending excluded from the denominator; **pending is never
  treated as absent** (Phase 7.2 Q-D8; legacy `calcCurrentPct`; S4 §10).
- **Forecast % (per type)** = `(attended + pending) / total × 100`; best case,
  all pending attended (legacy `calcForecastPct`).
- **Combined average** = `(L% + T%) / 2`; single-type subjects collapse to the
  available type (`calcAvgPct` / `_combined_pct`).
- **Overall (ERP)** = `Σ attended / Σ recorded × 100` across all
  attendance-applicable subjects and types (incl. practicals), over
  [semester_start, today]. **Not** the mean of subject percentages — it is
  class-weighted (Phase 7.2 check 5 verified 71.43% vs the explicitly-other
  46.51% pending-inclusive figure).
- **Overall forecast (legacy, not exposed)** = `Σ (att + pending) / Σ tot × 100`.
- **Quiz window %** = `attended / total × 100` within the ADR-010 window
  (pending **is** in the denominator — the eligibility formula's frozen
  semantics; Phase 7.2 made the pending count explicit on the card).
- **Must-attend / safe-skip** = `optimize_attendance` exhaustive optimum with
  the legacy tie-break (fewest total, then fewest lectures attended). Within a
  quiz window: how many more *pending* L/T classes must be attended (deficit),
  and how many can be skipped, to satisfy the target.

---

## F. PENDING / RECORDED-ONLY SEMANTICS (locked rule, non-negotiable)

- **Current attendance is recorded-only.** Denominator = attended + missed.
- **Pending must never silently become Absent.** It is excluded from the current
  denominator only; it is always counted and surfaced separately.
- A metric that intentionally includes pending (forecast %, quiz-window %) must
  explicitly say so — the Phase 8.1 analytics contract must declare, per field,
  whether pending is in the numerator/denominator/excluded.
- Cancelled sessions are **their own state** (never pending, never absent,
  never counted in any denominator).
- Extras are genuine classes and are counted (except cancelled).
- Labs/practicals: counted in overall/history/subject counts; **excluded from
  quiz eligibility** (`subjects.quiz_applicable` authoritative → 404).

---

## G. FORECAST / MUST-ATTEND / SAFE-SKIP / RECOVERY AUDIT

**What already exists (canonical):**
- `optimize_attendance` (attendance engine) — exhaustive minimum-attendance
  optimizer; exposed via `EligibilityResult.optimization` for each quiz window:
  `lecture_deficit`, `tutorial_deficit`, `safe_skip_lecture`, `safe_skip_tutorial`,
  `is_reachable`. Byte-identical to legacy `optimizeLive` (Phase 7.0 audit
  verified parity).
- Recovery states: `RECOVERABLE` (below target now, reachable by attending
  pending) / `NOT_ELIGIBLE` (unreachable) / `ELIGIBLE` / `UNRESOLVED` — all in
  `eligibility_engine`, window-bounded.
- Attention list + subject-level current/forecast avg on the Home dashboard.

**What is legacy-compatible but NOT currently exposed by the Python API:**
- **Subject-level (non-quiz-window) 75% optimization** — legacy
  `computeSubjectStats` always produced an `optResult` against
  `policies.attendance.targetPercentage` (75) for the dashboard ("need N more
  classes to reach 75%", "can safely skip N"). The Python
  `SubjectAttendanceSummary` schema has **no** optimization fields — this is the
  single largest gap between the roadmap's Phase 8 "Forecasting" examples and
  the current API. It is *legacy-defined*, so exposing it is an extension of the
  canonical engine output, not a new business rule.
- **Overall forecast** — legacy `computeForecastOverallAttendance`; no Python
  equivalent exists anywhere.
- **Forecast-impact delta** ("if you attend this class → X%") — legacy
  `calcForecastImpact` tooltip; no Python equivalent.

**What would constitute a NEW business rule (do NOT implement without approval):**
- Any probability / risk / momentum / "attendance health" score (e.g. a
  "trajectory to 75%" numeric or grade) — no such concept is defined in any
  repository document. Roadmap §8 "Risk states" and "Forecasting" examples are
  intent, not formulas.
- The 4-state taxonomy `SAFE / WATCH / AT-RISK / CRITICAL` (roadmap §8): the
  current system implements a documented 3-state band (SAFE ≥ 80 / WATCH ≥ 60 /
  CRITICAL < 60). **AT-RISK has no definition anywhere.** Candidate band
  definitions must be decided by the product owner before implementation
  (§T-1).

---

## H. SUBJECT-LEVEL ANALYTICS CONTRACT

Classification per roadmap candidate (DEFINED / LEGACY / DERIVED / UNDEFINED):

| Candidate | Classification | Current status |
|---|---|---|
| Lecture attendance (attended/total) | **DEFINED** | `SubjectAttendanceSummary.lecture` (ClassCounts) |
| Tutorial attendance | **DEFINED** | `.tutorial` |
| Practical attendance | **DEFINED** (counts) | `.practical` ClassCounts; **no practical % field** |
| Combined attendance (L+T avg) | **DEFINED** | `current_avg_pct` / `forecast_avg_pct` |
| Attended / total | **DEFINED** | ClassCounts |
| Recorded percentage | **DEFINED** | `current_lecture_pct`/`current_tutorial_pct` |
| Pending count | **DEFINED** | ClassCounts.pending |
| Current percentage | **DEFINED** | `current_*_pct` |
| Forecast percentage | **DEFINED** | `forecast_*_pct` |
| Classes needed to reach 75% | **LEGACY** | legacy `optResult.lectureDeficit`/`tutorialDeficit`; **not exposed in Python** |
| Classes that can be safely skipped | **LEGACY** | legacy `safeSkipLecture`/`safeSkipTutorial`; **not exposed in Python** |
| Trend / change | **UNDEFINED** | only weekly delta exists (dashboard-level) |

Phase 8.1 additive contract (proposed, extends the frozen engine output — no
formula change):

```
SubjectAttendanceSummary (extend additively):
  + current_practical_pct      (att/(att+miss) over practicals — legacy parity)
  + forecast_practical_pct     ((att+pending)/total over practicals)
  + optimization:              subject-level 75% optimizer (legacy parity:
                               lecture_deficit, tutorial_deficit,
                               safe_skip_lecture, safe_skip_tutorial,
                               is_reachable) — reuses attendance_engine
                               optimize_attendance against the subject's full
                               semester-to-date counts (same counting as
                               get_summary), NOT a new formula.
```

---

## I. OVERALL ANALYTICS CONTRACT

Preserve the documented distinctions (S4 §10 + Phase 7.2 Q-D8):

- **Recorded attendance** — the set of class opportunities with a definitive
  outcome (attended + missed).
- **Pending attendance** — unmarked class opportunities (no record row); never
  converted to absent; always surfaced separately.
- **Overall attendance (current)** = Σatt/Σrecorded, class-weighted, over
  [semester_start, today], practicals included, cancelled excluded, extras
  included. **Not** an average of subject percentages.
- **Overall forecast** — the only missing piece: `Σ(att+pending)/Σtot` per
  legacy `computeForecastOverallAttendance`. Proposed additive field on the
  analytics read model, computed by the same service-level sum over canonical
  rows (not a new engine).

No conflicting definition exists in the repository — the single definition is
the ERP/recorded-only one (verified in §D #1 and Phase 7.2).

---

## J. TREND ANALYTICS FINDINGS

**Nothing is defined** for daily/weekly/rolling trend series, subject trend, or
semester progress in the legacy project or the current architecture. The only
temporal comparison that exists is `weekly.delta_pct` (this week − last week,
recorded-only) on the Home dashboard.

Candidate definitions (for product approval, §T-2) — none implemented:

- **Weekly series**: bucket recorded-only Σatt/Σrecorded per ISO week from
  semester start to today; `null` weeks (no recorded classes) shown as gaps.
- **Subject weekly series**: same bucketing per subject.
- **Semester progress**: days elapsed / semester days, plus current overall %
  against the 75% line — display-only, computed from the canonical overall.
- **Change metric**: absolute pct-point delta between two points (already
  exists as weekly delta).

Constraints the contract must respect: sparse records (null-safe weeks), pending
days excluded from current buckets (never counted absent), cancelled excluded,
extras included, semester start bound, **current-date clamp** (never forecast
buckets beyond today), future sessions excluded from current series.

---

## K. UNDEFINED / NEW PRODUCT METRICS (not to be invented in Phase 8.1)

Category D candidates that **require explicit product approval**:

1. **AT-RISK risk state** (roadmap §8 names a 4-state taxonomy; only 3 states
   are defined anywhere).
2. **Forecast-impact tooltip deltas** ("if you attend the next N classes…" /
   per-class impact) — legacy-defined (`calcForecastImpact`) but the roadmap's
   *phrasing* (multi-class scenarios) is new.
3. **Weekly / semester trend series** (§J) — roadmap §8 lists "Weekly trend /
   Semester trend" with no formula.
4. **Any probability / AI / "attendance health" / momentum score** — explicitly
   forbidden unless a product document defines it first.
5. **Subject-level 75% optimization & overall forecast** — these are
   **LEGACY-defined** (not new): they should be classified as reuse, not new
   product metrics.

---

## L. PROPOSED API CONTRACTS (contract only — NOT implemented)

Design principle: **one coherent read model** for analytics, additive to the
existing services, consuming the canonical engines. Avoid multiple competing
analytics endpoints.

### L-1. `GET /api/v1/analytics/overview` (proposed, new)

- **Purpose**: the Home-level analytics payload (replaces/extends the dashboard
  read model's analytic sections; the dashboard may switch to it in Phase 8.1
  without changing its UI contract).
- **Method**: GET. **Auth**: `get_current_user`; enrollment-scoped internally
  (StudentEnrollment join), never client-provided user IDs.
- **Query params**: none required (`as_of` optional, clamped to today).
- **Response shape (proposed)**:
  ```json
  {
    "as_of": "2026-08-15",
    "semester_start": "2026-07-15",
    "overall": { "current_pct": 71.4, "forecast_pct": 80.2,
                 "attended": 55, "recorded": 77, "pending": 16, "cancelled": 0,
                 "status": "WATCH" },
    "weekly": [ { "week_start": "2026-07-13", "current_pct": 66.7,
                  "recorded": 6, "pending": 0 } ],
    "subjects": [ { "subject_code": "BCS-501", "current_avg_pct": 61.2,
                    "forecast_avg_pct": 74.5, "practical_current_pct": null,
                    "must_attend": { "lecture": 3, "tutorial": 1 },
                    "safe_skip": { "lecture": 2, "tutorial": 0 } } ]
  }
  ```
- **Canonical source**: `AttendanceService.get_summary` (per subject, engine) +
  a single enrollment-scoped range scan for overall/weekly sums
  (`get_sessions_with_status`) + `optimize_attendance` (engine) for must-attend.
- **Error behavior**: 401 unauthenticated; truthful empty arrays (no invented
  dates); `pct: null` (not 0) when nothing recorded.
- **Pagination**: not required (9 subjects; bounded by semester). Document a
  `limit` if the semester grows.

### L-2. Extend `GET /api/v1/attendance/summary/{subject_code}` (proposed, additive)

Add to `SubjectAttendanceSummary`: `current_practical_pct`,
`forecast_practical_pct`, `optimization` (subject-level 75%). Backwards
compatible — existing fields unchanged. **Also (security §O-1):** add the
enrollment-scope check this endpoint currently lacks (parity with the quiz
endpoint's 404).

### L-3. No separate trend endpoint (recommended)

Trend series belongs inside `/analytics/overview.weekly` (bounded, ≤ ~28
buckets). A dedicated `/analytics/trend` endpoint would duplicate the read model.

### L-4. Existing endpoints reused (no change)

`/dashboard/summary`, `/quiz-eligibility/...`, `/attendance/history`,
`/calendar`, `/attendance/daily/{date}` — unchanged. The dashboard service stays
the consumer; an analytics service may supersede its analytic sections in 8.1.

---

## M. PROPOSED FRONTEND PLACEMENT (contract only — no UI changes)

- **Dashboard (Home)**: overall current + forecast + pending + status band +
  weekly delta (already present). Add overall forecast to the Overall card;
  per-day pct via backend (remove React-side division). Keep the quiz snapshot
  and attention list as-is (they already consume canonical results).
- **Subject-level surfaces (`/subjects`)**: subject cards gain practical % and
  must-attend/safe-skip from the backend fields; **replace the hardcoded
  cycle=1** with the current-cycle endpoint; **remove the duplicated 75/65
  banding** in favor of the backend `status` field.
- **Dedicated Analytics page**: `GET /analytics/overview` → weekly series +
  subject optimization table. New route only if the product owner wants it
  (roadmap §8 implies it); otherwise the dashboard can host it. **No redesign
  of the visual language** — reuse the existing card/badge/progress primitives.
- **Quiz Eligibility**: unchanged — its cards are the frozen Phase 7.1/7.2
  reference design; analytics must not restyle or duplicate them.
- **Not duplicated across screens**: overall %, per-subject current/forecast %,
  must-attend/safe-skip must appear in exactly one canonical read model and be
  rendered by each surface — never recomputed per surface.

---

## N. PERFORMANCE / DATA-ACCESS AUDIT

Findings (all latent; **no fix in this phase**):

1. **Dashboard quiz snapshot is N+1.** `_build_quiz_snapshot` calls
   `eligibility_service.get_quiz_eligibility` once per quiz-applicable subject
   (6 subjects); each call performs its own subject fetch, schedule fetch,
   cycle+policy fetch, **events fetch** (`get_all_events()` per call), and a
   window counts query. The events list is identical across calls.
   **Recommendation (8.1):** fetch events once and pass them in; batch the
   per-subject window counts (one query over all subjects in the window); or
   add a `get_eligibility_batch` service method.
2. **Dashboard subject summaries are N+1.** `_subject_summaries` calls
   `attendance_service.get_summary` per subject → `get_subject_counts_up_to_date`
   per subject (9 queries). **Recommendation:** one grouped range scan
   (subject × class_type × status) feeding `compute_subject_stats` for each
   subject — same engine, one query.
3. **Overlapping range scans.** `_build_overall`, `_build_weekly` (2 calls), and
   `_build_today` each call `get_sessions_with_status` over overlapping ranges —
   up to 4 scans of the same rows per dashboard load. **Recommendation:** one
   [semester_start, today] scan + in-memory bucketing (the function is already
   range-agnostic).
4. **History is well-shaped.** One aggregate FILTER summary query + one paged
   query; no N+1.
5. **Calendar month is well-shaped.** One bounded events query + one
   enrollment-scoped session scan.
6. **React aggregation**: only the two display transforms flagged in §D
   (`WeeklyAttendanceCard` day pct, `SubjectAttendanceCard` bands) — no
   client-side business math, no large client aggregation.
7. **Latent import-time default**: `GET /attendance/summary` has
   `as_of_date: date = date.today()` evaluated at import time — the default
   freezes at server start. Not exercised by any current caller (the Subjects
   page passes no as_of), but the analytics contract must use an explicit
   server-side `today` (as the dashboard service already does).

---

## O. SECURITY / AUTHORIZATION FINDINGS

- **Every analytics read today is authenticated** (`get_current_user`) and
  internally user-scoped (queries filter by `user_id` and join
  `StudentEnrollment` for the authenticated user). No endpoint accepts a client
  user ID; no cross-user exposure path found.
- **O-1 (gap): `GET /attendance/summary/{subject_code}` lacks an enrollment
  check.** It resolves the subject by code and computes counts filtered only by
  `user_id` + `subject_id` — a student requesting a subject they are not
  enrolled in receives a 200 with zero counts (no other student's data — the
  record join is on the caller's user_id — but the endpoint diverges from the
  quiz endpoint, which 404s non-enrolled subjects). **Recommendation (8.1):**
  add the same `StudentEnrollment` scope/404 as `GET /quiz-eligibility/...`.
- **O-2 (good):** the quiz endpoint, history, calendar month, and dashboard are
  all enrollment-scoped (404/empty for foreign subjects). `get_sessions_with_status`
  joins `StudentEnrollment` on `user_id` — the shared read path for analytics.
- **Phase 8.1 must preserve:** authenticated-only analytics, user-scoped +
  enrollment-scoped reads, no client-provided user IDs, no new admin surface for
  student analytics, and the frozen admin-only event mutations.

---

## P. LEGACY PARITY FINDINGS

| Legacy (js/attendance-engine.js) | Python today | Parity |
|---|---|---|
| `calcCurrentPct` | `compute_subject_stats` current pct | ✅ identical |
| `calcForecastPct` | forecast pct | ✅ identical |
| `calcAvgPct` | `_combined_pct` | ✅ identical |
| `meetsAttendanceTarget` | `meets_attendance_target` | ✅ identical (Phase 7.0 verified) |
| `optimizeLive` | `optimize_attendance` | ✅ identical (tie-break verified) |
| `computeCurrentOverallAttendance` (ERP) | `_build_overall` | ✅ identical (Phase 7.2 verified 71.43%) |
| `computeSubjectStats.current.practical` | ❌ absent | **Gap — practical % not exposed** |
| `computeSubjectStats.optResult` (75%) | ❌ absent | **Gap — subject-level must-attend/safe-skip not exposed** |
| `computeForecastOverallAttendance` | ❌ absent | **Gap — overall forecast not exposed** |
| `calcForecastImpact` (tooltip) | ❌ absent | **Gap — forecast-impact deltas not exposed** |
| `getSubjectStatus` (SAFE/WARNING/CRITICAL on **forecast**) | `classify_attendance_status` (SAFE/WATCH/CRITICAL on **current**) | ✅ reconciled intentionally (S4.1: current standing, not forecast) — documented divergence |

The four legacy gaps are all *additive* extensions of existing engine outputs —
none requires a new formula.

---

## Q. ARCHITECTURAL RISKS

1. **Risk of a second analytics engine.** If Phase 8.1 computes subject/overall
   percentages in a new module instead of consuming `attendance_service` +
   `optimize_attendance`, the single-source-of-truth rule breaks. Mitigation:
   the analytics service must be a pure consumer (repository counts +
   engine outputs), verified against the frozen verifiers.
2. **Risk of React-side analytics.** Any new trend/optimization math in React
   would duplicate the engines. Mitigation: backend-only computation; React
   renders fields.
3. **Risk of re-deriving banding.** A second threshold scheme (like the existing
   75/65 card bands) drifts from the canonical 80/60/current band. Mitigation:
   single backend `status` field consumed everywhere.
4. **Risk of endpoint sprawl.** Competing `/analytics/*` endpoints fragment the
   read model. Mitigation: one `/analytics/overview` + additive summary fields.
5. **Risk of denormalizing quiz semantics.** Reusing quiz-window numbers as
   "subject analytics" would conflate window % (pending in denominator) with
   current % (recorded-only). Mitigation: keep the two domains explicitly
   separate in the contract (§F).
6. **Data-size latent risk.** Per-subject count queries are O(9) but fine at the
   current scale (684 sessions); the N+1 findings matter only if the app grows
   to many subjects/students. Documented, not urgent.

---

## R. RECOMMENDED PHASE 8 IMPLEMENTATION ORDER (for Phase 8.1+)

1. **8.1** — Backend additive analytics read model:
   a. Extend `SubjectAttendanceSummary` with practical %, subject-level
      75% `optimization`, and add the missing enrollment scope (O-1).
   b. Add `GET /api/v1/analytics/overview` (overall current+forecast+pending,
      weekly series, per-subject current/forecast/optimization) as a pure
      consumer of `attendance_service`/engine + one range scan.
   c. Fix the N+1 in the dashboard (batch counts, single events fetch) while
      keeping `DashboardSummaryResponse` byte-identical.
   d. New verifier `verify_phase_8_1.py` + full frozen regression
      (6.5/6.6/6.7/7.1/7.2).
2. **8.2** — Frontend: consume the analytics read model (overall forecast on the
   Home card, subject practical % + must-attend/safe-skip on subject cards,
   current-cycle default, remove duplicated card banding); no redesign.
3. **8.3** (only if product-approved): dedicated Analytics page (weekly series +
   subject strategy table) using the existing design system.

---

## S. EXPLICITLY FROZEN AREAS

- All attendance/eligibility **mathematics** (engines byte-identical).
- `class_sessions` / `attendance_records` **schema**.
- **Calendar engine semantics** and the event→session synchronizer.
- **Admin-only event mutations** (Phase 6.5/6.6 frozen).
- Quiz Eligibility **reference UI** (Phase 7.1/7.2 baseline) and its API contract.
- Dashboard `DashboardSummaryResponse` **shape** (may gain fields, not break).
- Auth architecture (JWT, role resolution from DB).
- Phase 6 frozen behavior and verifiers.
- Database: **zero mutation** (this phase and Phase 8.1 unless separately
  approved — no migration is needed for the additive analytics contract).

---

## T. OPEN PRODUCT DECISIONS

1. **T-1 — AT-RISK band.** Does the product want a 4-state risk taxonomy
   (SAFE/WATCH/AT-RISK/CRITICAL)? If so, the product owner must define the bands
   (e.g., distance-to-75% cutoffs). Until then the frozen 3-state band stands.
2. **T-2 — Trend scope.** Which trend series ship in 8.1: weekly only, subject
   weekly, semester progress? (Candidates in §J; none implemented.)
3. **T-3 — Dedicated Analytics page vs dashboard-only.** Roadmap §8 implies an
   analytics experience; the product owner decides whether a new route is
   warranted in 8.2/8.3.
4. **T-4 — Multi-class forecast scenarios.** "If you attend the next 3 classes…"
   phrasing (roadmap) is a new derived display; approve the exact wording and
   numbers (deficit-based, from `optimize_attendance`).
5. **T-5 — Q-D9 (quiz-day attendance without a session)** and **rule G (student
   event mutations)** remain open from Phase 7.0 — unchanged, out of Phase 8
   scope (they belong to their own decisions/phases).

---

## U. VERIFICATION RESULTS

- `python -m compileall app scripts` — **PASS**.
- `npx tsc --noEmit` — **PASS** (0 errors).
- `verify_phase_7_2.py` — **26/26 PASS** (frozen verifier, rollback-transaction
  based, re-asserts the exact baseline; run read-only against the live DB).
- DB baseline query (read-only SELECT) — exact Phase 7.2 match (see §V).
- No browser/E2E automation run (per policy).

---

## V. DATABASE MUTATION STATUS

**ZERO.** Only `SELECT` statements were executed. Verified live counts:

| Table | Count | Phase 7.2 baseline |
|---|---|---|
| academic_events | 18 | 18 ✅ |
| class_sessions | 684 | 684 ✅ |
| class_sessions (cancelled) | 0 | 0 ✅ |
| class_sessions (extra) | 0 | 0 ✅ |
| attendance_records | 89 | 89 ✅ |
| student_enrollments | 18 | 18 ✅ |
| subjects | 9 | 9 ✅ |
| quiz_schedules | 18 | 18 ✅ (18 SCHEDULED) |
| users | 30 | 30 ✅ |
| admins | 1 | 1 ✅ |
| eligibility_policies | 3 | — (reference) |
| quiz_cycles | 3 | — (reference) |

BCS-054 Quiz III = **2026-10-23** (verified). No INSERT/UPDATE/DELETE/migration/
seed executed.

---

## W. RECOMMENDED PHASE 8.1 SCOPE (not started)

Backend-only additive analytics read model: extend `SubjectAttendanceSummary`
(practical %, subject-level 75% optimization, enrollment scope), add
`GET /api/v1/analytics/overview` (overall current + forecast + pending + weekly
series + per-subject optimization) as a pure consumer of the canonical engines,
eliminate the dashboard N+1 without changing its response shape, and add
`verify_phase_8_1.py` + full frozen regression. No UI, no schema change, no new
engine, no new formula.

---

## PHASE 8.0 — FINAL REPORT

**Result:** **PASS** (read-only audit + contract design; zero code, zero DB change).

**Key findings:**
- No analytics layer exists yet; the dashboard service is the de-facto
  aggregator and already consumes the canonical engines (no second engine).
- Current metrics are all recorded-only current %, forecast %, ERP overall
  (class-weighted), quiz-window eligibility, and a documented 3-state band.
- **4 legacy gaps**: practical %, subject-level 75% must-attend/safe-skip,
  overall forecast, forecast-impact deltas — all additive, none a new formula.
- **2 React duplications** flagged (day-bar % division, card banding) plus a
  hardcoded cycle=1 on subject cards — to be removed in 8.2 by consuming the
  backend read model.
- **N+1s** in the dashboard quiz snapshot and subject summaries; one
  import-time `date.today()` default; one missing enrollment scope on the
  subject summary endpoint — all documented, none fixed.
- AT-RISK state and trend series are roadmap intent with **no definition** —
  explicitly withheld pending product decisions.

**Canonical metrics:** current % (recorded-only), forecast % (pending-as-
attended), combined average (L+T)/2, ERP overall (class-weighted), quiz-window
% + eligibility states + optimizer deficits (frozen, unchanged).

**New metrics requiring product approval:** AT-RISK band definition (T-1);
trend series scope (T-2); dedicated analytics page (T-3); multi-class forecast
phrasing (T-4).

**Recommended Phase 8.1:** backend additive analytics read model only (§R-1,
§W). No UI, no schema change, no new engine/formula.

**Files changed:** `docs/phase_8_0_attendance_analytics_audit.md` (new) ·
`MASTER_ROADMAP.md` · `implementation_plan.md` · `task.md` · `walkthrough.md`
(tracking updates only).

**Database mutation status:** **ZERO** (SELECT only; exact Phase 7.2 baseline
verified).

**Verification:** compileall PASS · tsc --noEmit PASS · verify_phase_7_2.py
26/26 PASS · baseline counts exact.

**HARD STOP:** Phase 8.1 **NOT STARTED**. No analytics API, no analytics UI, no
migration, no engine change, no attendance/eligibility math change. The next
implementation phase begins only after the product owner reviews these findings
and explicitly authorizes Phase 8.1.
