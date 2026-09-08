# Quiz Eligibility Calculation Audit

**Date:** 2026-09-07
**Mode:** READ-ONLY correctness audit. No application code, database data, migrations, API contracts, attendance records, quiz dates, events, or UI were modified. No browser automation, no test suites, no commits.
**Audited user (only user with attendance data):** roll `2401220100027` (ADMIN, section CSE-51), 170 attendance records (112 ATTENDED / 58 MISSED), records span 2026-07-15 → 2026-09-04.
**Verification method:** the eligibility mathematics were **independently recomputed from the raw database tables** (raw asyncpg + pure Python, zero imports of the application's engines) and compared field-by-field against the application's actual calculation path, which was executed in-process (single-subject endpoint path AND dashboard batch path) inside a transaction that was always rolled back. All scratch scripts live outside the repository (Windows temp dir) and are not part of the deliverable.

---

## 1. Executive Verdict

## **PASS**

All 18 audited subject/cycle combinations (6 quiz-applicable theory subjects × Quiz I/II/III) were independently recomputed from raw tables and **match the application exactly** in every checked field: quiz date, Criterion I / Criterion II windows, lecture/tutorial counts (total / attended / missed / pending), percentages (full precision), per-criterion pass/fail, per-criterion Must Attend / Safe Skip / reachability, the top-level optimizer selection, the final `Criterion I OR Criterion II` decision, and the canonical state (ELIGIBLE / RECOVERABLE / NOT_ELIGIBLE / UNRESOLVED). The dashboard batch path is **byte-identical** to the single-subject endpoint path for every checked field on every combination. The Must Attend / Can Skip optimizer was verified by independent exhaustive enumeration of the full pending-attendance combination space, including Lecture×Tutorial cross combinations.

One **policy interpretation** (not a math defect) is documented in §9/§10: Criterion I's window starts **inclusive of the previous quiz date**, so a *regular, timetable-bound* class on a previous quiz date counts toward the next quiz's Criterion I window (quiz-day sessions themselves are excluded by shape). This is the project's frozen, documented interpretation of ADR-010 — it materially affects guidance numbers in two windows (BCS-501 Q2, BNC-501 Q2) and is flagged for awareness only.

The audit prompt asked whether Criterion I is "lecture-only" vs the current "(Lecture % + Tutorial %) / 2" — see §3: the repository's authoritative governance (MASTER_ROADMAP Phase 7.3 "The Authoritative Quiz Eligibility Contract", the SUPERSEDED marker on the Phase 7.1 report, and the Phase 1 eligibility-correction verifier) explicitly froze **both criteria = combined average, differing only in window**. The Phase 7.1 "Criterion I = Lecture %" semantics were superseded on 2026-08-18 (commit `ed6c3e2`) and the supersession is documented in the governance documents themselves. No ambiguity remains *inside the project's own authoritative sources*; only the external official notice's exact wording is not committed to the repo (ADR-010 summarizes it), which is noted but does not contradict anything.

---

## 2. Scope

| Item | Value |
|---|---|
| Database | local dev PostgreSQL `localhost:55432/attendancedash` (value of backend `.env` `DATABASE_URI`; credentials not reproduced here) |
| Alembic revision (DB) | `f0e1d2c3b4a5` (add_push_subscriptions) — verified to be the single head of the repo's linear 29-migration chain; model-vs-DB drift not re-audited (out of scope) |
| Academic session / semester | `2026-27`, **V Semester 2026-07-15 → 2026-12-31** (`semester_start` for eligibility = 2026-07-15, resolved Section CSE-51 → Semester) |
| Institutional "today" | 2026-09-07 (Asia/Kolkata, `institution_today()`) |
| Quiz cycles | Quiz I, II, III (persisted `eligibility_policies`: 70 / 75 / 75) |
| Subjects | 9 enrolled (6 quiz-applicable theory: BCS-054, BCS-058, BCS-501, BCS-502, BCS-503, BNC-501; 3 labs BCS-551/552/553 excluded via `quiz_applicable=False` → 404 path) |
| Audited combinations | 6 subjects × 3 cycles = **18** (all resolved; no UNRESOLVED cycle exists for this user) |
| Quiz-date range covered | 2026-08-24 (BNC-501 Q1) → 2026-10-26 (BCS-058 Q3); windows covered 2026-07-15 → 2026-10-25 |
| Data volumes | 721 class_sessions (2026-07-15 → 2026-12-31; 17 cancelled, 19 extra, 37 quiz-day-shaped), 170 attendance records (single user), **0 occurrence_outcomes rows** |
| Authoritative policy sources | `MASTER_ROADMAP.md` (Phase 7.3 Authoritative Quiz Eligibility Contract), `docs/S4_PRODUCT_SPEC.md` §5/§11, `docs/18_ARCHITECTURE_DECISION_RECORDS.md` ADR-010 (SRMCEM Attendance Criteria notice of 14 July 2026), `docs/phase_7_2_implementation_report.md` §5, Phase 7.1 report (SUPERSEDED marker), `backend/scripts/verify_phase_1_eligibility.py` (contract docstring) |
| Code paths inspected | `backend/app/services/eligibility_service.py` · `backend/app/engines/eligibility_engine.py` · `backend/app/engines/attendance_engine.py` (`optimize_attendance`, `meets_attendance_target`, `normalize_class_type`) · `backend/app/engines/calendar_engine.py` (`get_attendance_window`, `get_cumulative_attendance_window`, `get_academic_day`) · `backend/app/engines/practical_occurrence.py` · `backend/app/repositories/quiz_repo.py` · `backend/app/repositories/attendance_repo.py` (`get_subject_counts_between[_for_subjects]`, `collapse_count_rows` consumption) · `backend/app/repositories/calendar_repo.py` · `backend/app/services/elective_resolver.py` · `backend/app/services/student_context_service.py` · `backend/app/services/dashboard_service.py` (`_build_quiz_snapshot`) · `backend/app/services/attendance_service.py` (Track parity) · `backend/app/api/v1/endpoints/quiz.py` · `backend/app/api/v1/endpoints/events.py` · frontend `src/components/quiz/QuizEligibilityCard.tsx`, `src/app/(authenticated)/tools/quiz-schedule/page.tsx`, `src/lib/date.ts` (presentation only) |
| Not audited | production database (none accessed), other students (no data), notification/push paths, admin analytics |

---

## 3. Authoritative Policy (as documented and as implemented)

| Rule | Authoritative source | Implementation |
|---|---|---|
| Quiz I threshold **70%** | ADR-010 (official notice 14 Jul 2026); MASTER_ROADMAP Phase 7.3 contract | `eligibility_policies.lecture_threshold` = 70.0 (persisted wins; engine fallback `determine_quiz_threshold` = 70/75/75 — dead code in practice) |
| Quiz II threshold **75%** | same | persisted 75.0 |
| Quiz III threshold **75%** | same | persisted 75.0 |
| Criterion I | MASTER_ROADMAP Phase 7.3: **(Lecture % + Tutorial %) / 2** over the **cycle window** (previous quiz boundary → day before quiz; commencement for Quiz I) | `eligibility_engine._evaluate_criterion("Criterion I — Lecture + Tutorial Average", window_i, …)` — matches |
| Criterion II | MASTER_ROADMAP Phase 7.3: same formula over the **cumulative window** (semester commencement → day before quiz) | `…("Criterion II — Lecture + Tutorial Average", window_ii, cumulative_counts)` — matches |
| Final decision | S4_PRODUCT_SPEC §5: "(Criterion 1 qualifies) OR (Criterion 2 qualifies) = Eligible" | `final_criterion.passed = criterion_i.passed or criterion_ii.passed` — matches |
| No-tutorial subjects | Phase 7.3: "collapse naturally to lecture percentage" | `_combined_pct` returns lecture % when `tutorial total == 0` — matches |
| No rounding before comparison | Phase 7.3 + engine code | raw float `avg_pct >= required`; only the frontend rounds for display (`toFixed(1)`) |
| Must Attend / Safe Skip | Phase 7.3: "calculated per criterion using that criterion's own window"; "top-level optimization selects the best reachable route" | `optimize_attendance` exhaustive enumeration per criterion; top-level `min((optI, optII), key=(not reachable, total deficit))` — matches |
| Quiz-date authority | Phase 2 / Phase 7.3: **active QUIZ_DAY AcademicEvents** | `quiz_repo.get_effective_quiz_dates_for_subject(s)` — active events only, chronological ranking, per-(subject,date) dedup |
| Quiz-day sessions | Phase 7.3 "Option A": attendance-bearing for subject attendance, **excluded from eligibility L/T counts** | `exclude_quiz_day=True` shape filter: `timetable_entry_id IS NULL AND NOT is_extra AND class_type = LECTURE` |
| Practicals/labs | S4 §5: "practicals/labs are strictly excluded" | `quiz_applicable` gate (labs 404) + L/T-only counting (`P` never aggregated) |
| Elective attribution | Phase 22.3/22.4: slot events resolve to the student's chosen subject; no choice → anchor fallback | `ElectiveResolver.chosen_elective_map` + slot-scoped event query + `_resolved_subject_match`. **The audited user has no elective choices**, so BCS-054/BCS-058 resolve via their own subject ids (anchor behavior). The only choice in the DB (user `…1058` → BCS-052 for ELECTIVE_I) is unaffected by this audit's user. |

**Criterion-I-vs-II formula question (explicitly resolved):** The audit brief asked whether Criterion I is lecture-only and Criterion II combined-average, or whether both legitimately use the combined average. Findings:

1. **Official source in repo:** `S4_PRODUCT_SPEC.md` §5 mandates the OR of two criteria but does **not** define their formulas. ADR-010 records the official notice's thresholds (70/75/75) and the window rule, but no per-criterion formula distinction.
2. **Superseded design:** Phase 7.1 (2026-08-15) implemented Criterion I = Lecture %, Criterion II = combined average. Its report now carries an explicit **SUPERSEDED (2026-08-19)** banner pointing to the Phase 7.2/7.3 architecture and the Phase 1 eligibility correction.
3. **Current authoritative contract:** commit `ed6c3e2` (2026-08-18, "Phase 1 eligibility correction", verifier `verify_phase_1_eligibility.py` 18/18, later frozen in MASTER_ROADMAP Phase 7.3) redefined **both criteria as (Lecture % + Tutorial %) / 2, differing only in the counting window**, and `docs/phase_23_0_architecture_discovery.md:155` records exactly this as the frozen state ("Criterion I (cycle window) OR Criterion II (cumulative from commencement), both (Lecture%+Tutorial%)/2").
4. **What can be independently verified:** the arithmetic of both routes against their windows (done — all match). Whether the *external* notice's phrasing intended a lecture-only Criterion I cannot be verified from repository material; ADR-010's summary does not say so. **No action possible or required without the original notice; the implementation matches the project's frozen contract.**

Note: `eligibility_policies.combined_threshold` exists in the DB (70/70, 75/75, 75/75) but is intentionally unread since Phase 7.3 ("Removed dead combined_threshold plumbing"). It equals `lecture_threshold` in every row, so no divergence is possible with current data.

---

## 4. Calculation Pipeline (as traced in executable code)

```
academic_events (event_type=QUIZ_DAY, active=true)          ← ONE authoritative quiz-date source
    └─ quiz_repo.get_effective_quiz_dates_for_subject(s)
         scope: subject_id match  OR  elective_slot == student's chosen slot (Phase 22.4)
         order by start_date, id → rank 1..n = cycle 1..n (dedup same subject+date)
    ↓
EligibilityService._build_domain_subject → milestones (q1/q2/q3 = effective dates)
    ↓
calendar_engine.get_attendance_window        (Criterion I:  prev quiz date | commencement  → quiz_date − 1)
calendar_engine.get_cumulative_attendance_window (Criterion II: commencement               → quiz_date − 1)
    (window bounds are plain calendar dates; weekend/holiday semantics enter only through
     which sessions were materialized — closures cancelled, non-working days empty)
    ↓
attendance_repo.get_subject_counts_between(exclude_quiz_day=True)      [single path]
attendance_repo.get_subject_counts_between_for_subjects + in-memory bucketing
                                                             + collapse_count_rows   [batch path]
    both: elective attribution (_resolved_subject_match), occurrence_outcome application,
    cancelled-occurrence exclusion, practical-block collapse, quiz-day-shape exclusion
    ↓
EligibilityService._build_counts → {L,T} × {tot, att, miss, pending}   (status None = Pending)
    ↓
eligibility_engine.evaluate_quiz_eligibility
    per criterion: avg = (L% + T%)/2 (L% alone if no tutorials)  → passed = avg ≥ required (full precision)
    per criterion: optimize_attendance (exhaustive L×T pending combinations; min total attend,
                   tie → min lectures attended; zero-pending early return)
    state: ELIGIBLE (any passed) | RECOVERABLE (best-case avg ≥ required) | NOT_ELIGIBLE
    top-level optimization: min by (not is_reachable, lecture_deficit + tutorial_deficit), ties → I
    final: Criterion I OR Criterion II
    ↓
GET /api/v1/quiz-eligibility/{subject_code}/{quiz_cycle}   (single)
dashboard _build_quiz_snapshot → get_quiz_eligibility_for_subjects (batch; same _evaluate_subject)
    ↓
React QuizEligibilityCard renders backend fields verbatim (toFixed(1) display rounding only;
no eligibility mathematics in the frontend)
```

The batch path (`Phase 26.3` one-scan bucketing) was verified **byte-identical** to the single path (§6/§10), so the dashboard snapshot and the single-subject endpoint share the exact same mathematics.

---

## 5. Subject-by-Subject Audit

Percentages shown rounded to 4 dp for the report only; all comparisons used full precision. App values matched the independent recomputation to ≤1e-9 on every float.

### 5.1 Criterion windows & counts (independent ≡ app in all 36 criterion evaluations)

| Subject | Quiz | Quiz Date | Criterion | Window | L (tot/att/miss/pend) | L % | T (tot/att/miss/pend) | T % | Avg | Required | Pass |
|---|---|---|---|---|---|---:|---|---:|---:|---:|---|
| BCS-054 | I | 2026-09-07 | I | 07-15 → 09-06 | 22/9/9/4 | 40.9091 | 7/3/3/1 | 42.8571 | 41.8831 | 70 | FAIL |
| BCS-054 | I | 2026-09-07 | II | 07-15 → 09-06 | 22/9/9/4 | 40.9091 | 7/3/3/1 | 42.8571 | 41.8831 | 70 | FAIL |
| BCS-054 | II | 2026-09-28 | I | 09-07 → 09-27 | 9/0/0/9 | 0.0000 | 3/0/0/3 | 0.0000 | 0.0000 | 75 | FAIL |
| BCS-054 | II | 2026-09-28 | II | 07-15 → 09-27 | 31/9/9/13 | 29.0323 | 10/3/3/4 | 30.0000 | 29.5161 | 75 | FAIL |
| BCS-054 | III | 2026-10-23 | I | 09-28 → 10-22 | 12/0/0/12 | 0.0000 | 4/0/0/4 | 0.0000 | 0.0000 | 75 | FAIL |
| BCS-054 | III | 2026-10-23 | II | 07-15 → 10-22 | 43/9/9/25 | 20.9302 | 14/3/3/8 | 21.4286 | 21.1794 | 75 | FAIL |
| BCS-058 | I | 2026-09-11 | I | 07-15 → 09-10 | 25/8/11/6 | 32.0000 | 8/5/1/2 | 62.5000 | 47.2500 | 70 | FAIL |
| BCS-058 | I | 2026-09-11 | II | 07-15 → 09-10 | 25/8/11/6 | 32.0000 | 8/5/1/2 | 62.5000 | 47.2500 | 70 | FAIL |
| BCS-058 | II | 2026-10-05 | I | 09-11 → 10-04 | 9/0/0/9 | 0.0000 | 3/0/0/3 | 0.0000 | 0.0000 | 75 | FAIL |
| BCS-058 | II | 2026-10-05 | II | 07-15 → 10-04 | 34/8/11/15 | 23.5294 | 11/5/1/5 | 45.4545 | 34.4920 | 75 | FAIL |
| BCS-058 | III | 2026-10-26 | I | 10-05 → 10-25 | 9/0/0/9 | 0.0000 | 3/0/0/3 | 0.0000 | 0.0000 | 75 | FAIL |
| BCS-058 | III | 2026-10-26 | II | 07-15 → 10-25 | 43/8/11/24 | 18.6047 | 14/5/1/8 | 35.7143 | 27.1595 | 75 | FAIL |
| BCS-501 | I | 2026-08-27 | I | 07-15 → 08-26 | 24/15/9/0 | 62.5000 | 4/3/1/0 | 75.0000 | 68.7500 | 70 | FAIL |
| BCS-501 | I | 2026-08-27 | II | 07-15 → 08-26 | 24/15/9/0 | 62.5000 | 4/3/1/0 | 75.0000 | 68.7500 | 70 | FAIL |
| BCS-501 | II | 2026-09-17 | I | 08-27 → 09-16 | 8/1/0/7 | 12.5000 | 3/0/0/3 | 0.0000 | 6.2500 | 75 | FAIL |
| BCS-501 | II | 2026-09-17 | II | 07-15 → 09-16 | 32/16/9/7 | 50.0000 | 7/3/1/3 | 42.8571 | 46.4286 | 75 | FAIL |
| BCS-501 | III | 2026-10-12 | I | 09-17 → 10-11 | 11/0/0/11 | 0.0000 | 3/0/0/3 | 0.0000 | 0.0000 | 75 | FAIL |
| BCS-501 | III | 2026-10-12 | II | 07-15 → 10-11 | 43/16/9/18 | 37.2093 | 10/3/1/6 | 30.0000 | 33.6047 | 75 | FAIL |
| BCS-502 | I | 2026-08-31 | I | 07-15 → 08-30 | 19/12/7/0 | 63.1579 | 6/4/2/0 | 66.6667 | 64.9123 | 70 | FAIL |
| BCS-502 | I | 2026-08-31 | II | 07-15 → 08-30 | 19/12/7/0 | 63.1579 | 6/4/2/0 | 66.6667 | 64.9123 | 70 | FAIL |
| BCS-502 | II | 2026-09-21 | I | 08-31 → 09-20 | 9/1/0/8 | 11.1111 | 3/0/0/3 | 0.0000 | 5.5556 | 75 | FAIL |
| BCS-502 | II | 2026-09-21 | II | 07-15 → 09-20 | 28/13/7/8 | 46.4286 | 9/4/2/3 | 44.4444 | 45.4365 | 75 | FAIL |
| BCS-502 | III | 2026-10-16 | I | 09-21 → 10-15 | 11/0/0/11 | 0.0000 | 3/0/0/3 | 0.0000 | 0.0000 | 75 | FAIL |
| BCS-502 | III | 2026-10-16 | II | 07-15 → 10-15 | 39/13/7/19 | 33.3333 | 12/4/2/6 | 33.3333 | 33.3333 | 75 | FAIL |
| BCS-503 | I | 2026-09-03 | I | 07-15 → 09-02 | 26/17/6/3 | 65.3846 | 7/6/0/1 | 85.7143 | 75.5495 | 70 | **PASS** |
| BCS-503 | I | 2026-09-03 | II | 07-15 → 09-02 | 26/17/6/3 | 65.3846 | 7/6/0/1 | 85.7143 | 75.5495 | 70 | **PASS** |
| BCS-503 | II | 2026-09-24 | I | 09-03 → 09-23 | 9/0/0/9 | 0.0000 | 3/0/0/3 | 0.0000 | 0.0000 | 75 | FAIL |
| BCS-503 | II | 2026-09-24 | II | 07-15 → 09-23 | 35/17/6/12 | 48.5714 | 10/6/0/4 | 60.0000 | 54.2857 | 75 | FAIL |
| BCS-503 | III | 2026-10-21 | I | 09-24 → 10-20 | 11/0/0/11 | 0.0000 | 4/0/0/4 | 0.0000 | 0.0000 | 75 | FAIL |
| BCS-503 | III | 2026-10-21 | II | 07-15 → 10-20 | 46/17/6/23 | 36.9565 | 14/6/0/8 | 42.8571 | 39.9068 | 75 | FAIL |
| BNC-501 | I | 2026-08-24 | I | 07-15 → 08-23 | 14/10/4/0 | 71.4286 | 0 (none) | N/A | 71.4286 | 70 | **PASS** |
| BNC-501 | I | 2026-08-24 | II | 07-15 → 08-23 | 14/10/4/0 | 71.4286 | 0 (none) | N/A | 71.4286 | 70 | **PASS** |
| BNC-501 | II | 2026-09-14 | I | 08-24 → 09-13 | 5/1/0/4 | 20.0000 | 0 (none) | N/A | 20.0000 | 75 | FAIL |
| BNC-501 | II | 2026-09-14 | II | 07-15 → 09-13 | 19/11/4/4 | 57.8947 | 0 (none) | N/A | 57.8947 | 75 | FAIL |
| BNC-501 | III | 2026-10-09 | I | 09-14 → 10-08 | 8/0/0/8 | 0.0000 | 0 (none) | N/A | 0.0000 | 75 | FAIL |
| BNC-501 | III | 2026-10-09 | II | 07-15 → 10-08 | 27/11/4/12 | 40.7407 | 0 (none) | N/A | 40.7407 | 75 | FAIL |

(For Quiz I, Criteria I and II share the same window by definition — commencement → day before quiz.)

### 5.2 Optimization audit (Must Attend / Can Skip)

Independent exhaustive enumeration over the full pending space (attend 0..pendingL lectures × 0..pendingT tutorials) reproduced the app's optimizer output in **all 36 criterion evaluations**. `Total` = minimal total classes to attend; `Skip` = remaining pending attendable-but-skippable classes in the chosen combination. `Src` = which criterion the top-level recommendation came from.

| Subject | Quiz | Criterion | Current Avg | Required | Must Attend L | Must Attend T | Can Skip L | Can Skip T | Reachable | Top Src | Independent Result | Match |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| BCS-054 | I | I (=II) | 41.8831 | 70 | 4 | 1 | 0 | 0 | no | I | best-case 58.1169 < 70 → NOT_ELIGIBLE | ✔ |
| BCS-054 | II | I | 0.0000 | 75 | 5 | 3 | 4 | 0 | yes | I | min total 8 (5L+3T → 77.7778) | ✔ |
| BCS-054 | II | II | 29.5161 | 75 | 13 | 4 | 0 | 0 | no | — | best-case 70.4839 < 75 | ✔ |
| BCS-054 | III | I | 0.0000 | 75 | 6 | 4 | 6 | 0 | yes | I | min total 10 (6L+4T → 75.0000) | ✔ |
| BCS-054 | III | II | 21.1794 | 75 | 22 | 8 | 3 | 0 | yes | — | (6L+8T = 14 total via II; I is 10) | ✔ |
| BCS-058 | I | I (=II) | 47.2500 | 70 | 6 | 2 | 0 | 0 | yes | I | min total 8 = attend all (71.75) | ✔ |
| BCS-058 | II | I | 0.0000 | 75 | 5 | 3 | 4 | 0 | yes | I | min total 8 | ✔ |
| BCS-058 | II | II | 34.4920 | 75 | 13 | 5 | 2 | 0 | yes | — | 18 total via II vs 8 via I | ✔ |
| BCS-058 | III | I | 0.0000 | 75 | 5 | 3 | 4 | 0 | yes | I | min total 8 | ✔ |
| BCS-058 | III | II | 27.1595 | 75 | 17 | 8 | 7 | 0 | yes | — | 25 total via II vs 8 via I | ✔ |
| BCS-501 | I | I (=II) | 68.7500 | 70 | 0 | 0 | 0 | 0 | **no** | I | zero pending, 68.75 < 70 → NOT_ELIGIBLE | ✔ |
| BCS-501 | II | I | 6.2500 | 75 | 3 | 3 | 4 | 0 | yes | I | min total 6 (3L+3T → exactly 75.0) | ✔ |
| BCS-501 | II | II | 46.4286 | 75 | 5 | 3 | 2 | 0 | yes | — | 8 total via II vs 6 via I | ✔ |
| BCS-501 | III | I | 0.0000 | 75 | 6 | 3 | 5 | 0 | yes | I | min total 9 | ✔ |
| BCS-501 | III | II | 33.6047 | 75 | 10 | 6 | 8 | 0 | yes | — | 16 via II vs 9 via I | ✔ |
| BCS-502 | I | I (=II) | 64.9123 | 70 | 0 | 0 | 0 | 0 | **no** | I | zero pending, 64.9123 < 70 → NOT_ELIGIBLE | ✔ |
| BCS-502 | II | I | 5.5556 | 75 | 4 | 3 | 4 | 0 | yes | I | min total 7 (77.7778) | ✔ |
| BCS-502 | II | II | 45.4365 | 75 | 8 | 3 | 0 | 0 | yes | — | 11 via II vs 7 via I | ✔ |
| BCS-502 | III | I | 0.0000 | 75 | 6 | 3 | 5 | 0 | yes | I | min total 9 | ✔ |
| BCS-502 | III | II | 33.3333 | 75 | 13 | 6 | 6 | 0 | yes | — | 19 via II vs 9 via I | ✔ |
| BCS-503 | I | I (=II) | 75.5495 | 70 | 0 | 0 | 3 | 1 | yes | I | already passing → skip all 4 pending | ✔ |
| BCS-503 | II | I | 0.0000 | 75 | 5 | 3 | 4 | 0 | yes | I | min total 8 | ✔ |
| BCS-503 | II | II | 54.2857 | 75 | 1 | 4 | 11 | 0 | yes | **II** | min total 5 (1L+4T → 75.7143) < 8 via I | ✔ |
| BCS-503 | III | I | 0.0000 | 75 | 6 | 4 | 5 | 0 | yes | I | min total 10 | ✔ |
| BCS-503 | III | II | 39.9068 | 75 | 6 | 8 | 17 | 0 | yes | — | 14 via II vs 10 via I | ✔ |
| BNC-501 | I | I (=II) | 71.4286 | 70 | 0 | 0 | 0 | 0 | yes | I | already passing, zero pending | ✔ |
| BNC-501 | II | I | 20.0000 | 75 | 3 | 0 | 1 | 0 | yes | I | (1+3)/5 = 80 ≥ 75; 2 → 60 ✗ | ✔ |
| BNC-501 | II | II | 57.8947 | 75 | 4 | 0 | 0 | 0 | yes | — | 4 via II vs 3 via I | ✔ |
| BNC-501 | III | I | 0.0000 | 75 | 6 | 0 | 2 | 0 | yes | I | (0+6)/8 = 75 exactly | ✔ |
| BNC-501 | III | II | 40.7407 | 75 | 10 | 0 | 2 | 0 | yes | — | 10 via II vs 6 via I | ✔ |

Key OR-semantics checks (the audit brief's central optimizer concern):

- **Unreachable route never wins by smaller deficit.** BCS-054 Q2: Criterion II's best case (attend everything) tops out at 70.4839% < 75 → unreachable; its "deficit" (13L+4T) is reported as-is with `is_reachable=false` and the top-level recommendation correctly comes from the *reachable* Criterion I (5L+3T). Structurally, an unreachable criterion's deficit equals its full pending count, which can never be smaller than a reachable route's requirement here (Criterion II's window is a superset of Criterion I's), and the lexicographic `(not reachable, total deficit)` key enforces it regardless.
- **Smaller *reachable* total wins across routes.** BCS-503 Q2: Criterion II needs 5 classes (1L+4T) vs Criterion I's 8 → top-level recommendation is Criterion II. App and independent recomputation agree (`Top Src = II`).
- **Tie-break (min total, then min lectures attended → maximize safe lecture skips)** is the documented product decision (attendance_engine comment; Phase 7.3 contract). Independent enumeration reproduced it everywhere. Note this means the optimizer prefers skipping *lectures* over tutorials when both routes cost the same total — a documented presentation choice, mathematically valid for the threshold, and consistent app-wide.
- **Zero-pending edge case** (Phase 7.3 corrected semantics): with nothing left to attend, `is_reachable` = whether the current average already passes (BCS-501 Q1: 68.75 < 70 → reachable=false, NOT_ELIGIBLE; BNC-501 Q1: 71.4286 ≥ 70 → reachable=true). Matches the documented fix and both sides agree.

---

## 6. Final Eligibility Audit

| Subject | Quiz | Criterion I | Criterion II | Expected OR | App Result (state / is_eligible) | Match |
|---|---|---|---|---|---|---|
| BCS-054 | I | FAIL | FAIL | Not eligible | NOT_ELIGIBLE / false | ✔ |
| BCS-054 | II | FAIL | FAIL | Not eligible (reachable via I) | RECOVERABLE / false | ✔ |
| BCS-054 | III | FAIL | FAIL | Not eligible (reachable via I) | RECOVERABLE / false | ✔ |
| BCS-058 | I | FAIL | FAIL | Not eligible (reachable) | RECOVERABLE / false | ✔ |
| BCS-058 | II | FAIL | FAIL | Not eligible (reachable) | RECOVERABLE / false | ✔ |
| BCS-058 | III | FAIL | FAIL | Not eligible (reachable) | RECOVERABLE / false | ✔ |
| BCS-501 | I | FAIL | FAIL | Not eligible (unreachable) | NOT_ELIGIBLE / false | ✔ |
| BCS-501 | II | FAIL | FAIL | Not eligible (reachable) | RECOVERABLE / false | ✔ |
| BCS-501 | III | FAIL | FAIL | Not eligible (reachable) | RECOVERABLE / false | ✔ |
| BCS-502 | I | FAIL | FAIL | Not eligible (unreachable) | NOT_ELIGIBLE / false | ✔ |
| BCS-502 | II | FAIL | FAIL | Not eligible (reachable) | RECOVERABLE / false | ✔ |
| BCS-502 | III | FAIL | FAIL | Not eligible (reachable) | RECOVERABLE / false | ✔ |
| BCS-503 | I | **PASS** | **PASS** | **Eligible** | ELIGIBLE / true | ✔ |
| BCS-503 | II | FAIL | FAIL | Not eligible (reachable) | RECOVERABLE / false | ✔ |
| BCS-503 | III | FAIL | FAIL | Not eligible (reachable) | RECOVERABLE / false | ✔ |
| BNC-501 | I | **PASS** | **PASS** | **Eligible** | ELIGIBLE / true | ✔ |
| BNC-501 | II | FAIL | FAIL | Not eligible (reachable) | RECOVERABLE / false | ✔ |
| BNC-501 | III | FAIL | FAIL | Not eligible (reachable) | RECOVERABLE / false | ✔ |

Dashboard snapshot consistency (cycle 1, picked 2026-09-07 BCS-054): eligible 2 (BCS-503, BNC-501) + attention 1 (BCS-058, reachable) + not_eligible 3 (BCS-054, BCS-501, BCS-502) = 6 theory subjects — exactly the per-subject verdicts above. `GET /quiz-eligibility/current-cycle` returned cycle 1 / 2026-09-07 / `next_upcoming` — consistent with the dashboard pick (min future quiz date ≥ today).

**Batch vs single path:** `get_quiz_eligibility_for_subjects` (dashboard) vs `get_quiz_eligibility` (endpoint) compared on every field (state, is_eligible, final_pass, quiz_date, required, window bounds, all L/T counts, all three percentages, both criterion results, top-level optimization) for all 18 combinations: **identical in every case**. One canonical mathematics path confirmed.

---

## 7. Rescheduled Quiz Audit

The Events tab edits are visible in the data as **inactive (deactivated) QUIZ_DAY events** alongside the corrected active ones. Old dates below are reconstructed from those inactive rows (no other history exists — say-so per the brief; nothing invented):

| Quiz | Old date (from inactive event) | Current active date | Criterion I end | Criterion II end | Correct? | Notes |
|---|---|---|---|---|---|---|
| BCS-501 II | 2026-09-18 | **2026-09-17** | 09-16 (= date − 1) | 09-16 | ✔ | Inactive 09-18 event ignored by the service (active-only query). The regular BCS-501 lecture still materialized on 09-18 now correctly falls in the **Quiz III** window (starts 09-17) as a normal class — moving one quiz did not corrupt another's boundary. 09-17 sessions (tt lecture + quiz-day session) are outside the Q2 window (end 09-16). |
| BCS-502 I | 2026-08-17 | **2026-08-31** | 08-30 | 08-30 | ✔ | Window recomputed from the corrected date; classes 08-31 onward excluded from Q1. |
| BNC-501 I | 2026-08-17 | **2026-08-24** | 08-23 | 08-23 | ✔ | BNC-501's 08-17 lecture is CANCELLED (active CLASS_CANCELLED event) and excluded as cancelled, not as absence. |
| (no edit) BNC-501 | — | 2026-08-24 | — | — | — | BNC-501 has **both an active and an inactive QUIZ_DAY row dated 08-24** (residue of an edit cycle). Harmless: only active rows are read, and same-subject/same-date dedup would collapse duplicates anyway. Data-hygiene observation only. |
| (no edit) BCS-054/058/503, BCS-501 I/III | — | per active events | quiz − 1 (verified each) | quiz − 1 | ✔ | |

Specific rescheduling checks from the brief:

- **(A) corrected date is the active event** — yes, per table above; the service reads active events only (`AcademicEvent.active.is_(True)`).
- **(B) service uses the corrected date** — `quiz_date` in every app response equals the active event date (18/18).
- **(C)/(D) Criterion I and II end = quiz date − 1 day** — verified for all 18 combinations (e.g., BCS-501 Q2: both end 2026-09-16).
- **(E) classes after the quiz date not counted** — verified (e.g., BCS-501 Q1 window's counted session dates end 2026-08-26; the 09-01+ lectures appear only in later windows).
- **(F) classes on the quiz date not counted** — verified (quiz-date sessions are outside [start, quiz−1] by construction; the quiz-day *session* on that date is additionally excluded by shape from the *next* window).
- **(G) classes newly included by a later quiz date are counted** — verified: BCS-502 Q1 (moved 08-17→08-31) counts sessions through 08-30, e.g. the 08-27/08-28 lectures the earlier date would have excluded (08-28's are cancelled and correctly excluded as cancelled).
- **(H) classes newly excluded by an earlier quiz date are not counted** — verified: BCS-501 Q2 (09-18→09-17) excludes 09-17/09-18 sessions from its window.
- **(I) previous-quiz boundaries use the correct previous effective (active) date** — verified: e.g., BCS-501 Q2 Criterion I starts 08-27 (active Q1 date), BCS-054 Q3 starts 09-28 (active Q2 date).
- **(J) rescheduling one quiz does not move another quiz's boundary** — verified: all six subjects' three windows derive solely from their own active event dates; the BCS-501 09-18 residue class landed in Q3's window without shifting Q3's own boundaries.
- **(K) single-subject endpoint == dashboard batch** — verified byte-identical (§6).

---

## 8. Independent Recalculation Evidence (concrete arithmetic from the live DB)

**Example 1 — BCS-503 (Design & Analysis of Algorithm), Quiz I, Criterion I = Criterion II window 2026-07-15 → 2026-09-02**

```
Lecture:  17 attended / 26 total  = 65.384615…%
          (9 missed, 3 pending)
Tutorial:  6 attended / 7 total   = 85.714286…%
          (0 missed, 1 pending)
Combined: (65.384615… + 85.714286…) / 2 = 75.549450…%
Required: 70%  →  75.549450… ≥ 70  →  PASS  (full precision; no rounding)
Must Attend: 0   (already qualifying)
Can Skip: 3 lectures + 1 tutorial = all 4 pending
          verify: skip everything → (17/26 + 6/7)/2 = 75.549450…% ≥ 70 ✔ (nothing more is required)
Application: value 75.549450…, passed True, state ELIGIBLE, opt 0/0/3/1 reachable
Independent: identical          → MATCH
```

**Example 2 — BCS-501 (Database Management System), Quiz I, window 2026-07-15 → 2026-08-26**

```
Lecture:  15/24 = 62.5%   (9 missed, 0 pending)
Tutorial:  3/4  = 75.0%   (1 missed, 0 pending)
Combined: (62.5 + 75.0) / 2 = 68.75%
Required: 70%  →  68.75 < 70  →  FAIL
Window closed with zero pending → unreachable (Phase 7.3 zero-pending semantics):
best-case = current = 68.75 < 70  →  NOT_ELIGIBLE
Must Attend 0 / Safe Skip 0 / reachable=false   (nothing left to attend)
Application: identical          → MATCH
```

**Example 3 — BCS-501, Quiz II, Criterion I window 2026-08-27 → 2026-09-16 (rescheduled quiz date 09-17)**

```
Lecture:  1 attended / 8 total   = 12.5%   (0 missed, 7 pending)
          window includes the 08-27 regular lecture (previous-quiz-date boundary is
          inclusive; that day's quiz-day-shaped session is excluded by shape)
Tutorial: 0 attended / 3 total   = 0%      (3 pending)
Combined now: (12.5 + 0)/2 = 6.25% < 75 → FAIL

Exhaustive enumeration (all 8×4 = 32 lecture/tutorial attend combinations),
qualifying combos (L_att, T_att, total, avg): min is (3, 3, 6, exactly 75.0)
  → (4/8 + 3/3)/2 = (50 + 100)/2 = 75.0 ≥ 75 ✔;  (2,3) → 68.75 ✗;  (3,2) → 62.5 ✗
Must Attend: 3 lectures + 3 tutorials (total 6); Safe Skip: 4 lectures, 0 tutorials
Criterion II (commencement → 09-16): (16/32 + 3/7)/2 = 46.4286% < 75 → FAIL;
  its minimum is 5L+3T (8 classes) — more than Criterion I's 6.
Final: FAIL OR FAIL = not eligible, but reachable (both routes) → RECOVERABLE
Top-level: Criterion I (6 < 8)
Application: identical          → MATCH
```

**Example 4 — BCS-054 (OOS Design with C++), Quiz II (window 09-07 → 09-27; quiz today 09-07)**

```
Criterion I: L 0/9 pending, T 0/3 pending → avg 0% < 75 FAIL
  enumeration minimum: (5L, 3T, total 8): (5/9 + 3/3)/2 = (55.5556 + 100)/2 = 77.7778 ≥ 75 ✔
    (4L,3T) → 72.2222 ✗ ; (5L,2T) → 61.1111 ✗
  Must Attend 5L+3T, Can Skip 4L
Criterion II (07-15 → 09-27): (9/31 + 3/10)/2 = (29.0323 + 30.0)/2 = 29.5161% < 75 FAIL
  best case (attend all 13L + 4T): (22/31 + 7/10)/2 = (70.9677 + 70)/2 = 70.4839 < 75
  → UNREACHABLE (deficit reported 13L+4T, reachable=false)
Final: RECOVERABLE — top-level recommendation from the REACHABLE Criterion I (8 classes),
  never from the unreachable route.  Application: identical  → MATCH
```

**Example 5 — BNC-501 (Constitution of India), Quiz I (no tutorials), window 07-15 → 08-23**

```
Lecture: 10 attended / 14 total = 71.428571…%   (4 missed, 0 pending)
Tutorial: none in window → Average % = Lecture % (documented collapse)
Required: 70%  →  71.428571… ≥ 70  →  PASS → ELIGIBLE
The 08-24 quiz-day-shaped session (marked MISSED on the day) is excluded from this
math by the Option-A shape rule (it is a real absence in Track/overall, not here).
Application: identical          → MATCH
```

**Example 6 — BCS-058 (Data Warehousing & Data Mining), Quiz I, window 07-15 → 09-10**

```
Lecture:  8/25 = 32.0%   (11 missed, 6 pending)
Tutorial: 5/8  = 62.5%   (1 missed, 2 pending)
Combined: 47.25% < 70 FAIL; best case (8L+2T attended): (14/25 + 7/8)/2 = (56 + 87.5)/2 = 71.75 ≥ 70
  → RECOVERABLE. Enumeration minimum = attend ALL 8 pending (6L+2T): smaller totals fail
    ((5L,2T) → 69.75 ✗ ; (6L,1T) → 65.5 ✗).  Must Attend 6L+2T, Safe Skip 0/0.
Application: identical          → MATCH
```

---

## 9. Edge Cases Found

1. **Quiz-day sessions (Option A) behave exactly as documented.** Every active quiz date has exactly one materialized quiz-day-shaped session (`timetable_entry_id IS NULL`, `is_extra=false`, `LECTURE`). Two past ones carry records (BNC-501 08-24 MISSED, BCS-501 08-27 MISSED): they count in Track/overall attendance but are excluded from every eligibility L/T count (verified numerically, §Cross-screen).
2. **Regular classes on quiz dates are real opportunities in the *next* window.** 13 timetable-bound L/T sessions exist on active quiz dates (e.g., BCS-503 09-03 lecture/tutorial, BCS-502 10-16 lecture+tutorial). They are excluded from the *ending* window (date > quiz−1) but included in the *next* quiz's Criterion I window (inclusive boundary). This is the frozen interpretation — see §10 policy note.
3. **Holidays produce no absences.** Eid-e-Milad (08-26) and Rakshabandhan (08-28): 6 and 5 sessions materialized on those dates, **all cancelled** by the event synchronizer and excluded by `occurrence_is_cancelled` — never counted as missed/pending. Holiday days contain zero counted opportunities.
4. **Cancelled ≠ absent, including stale marks.** BCS-058 lectures on 07-29/07-30 are cancelled *and* carry attendance records; the canonical rule drops them from all denominators/numerators (records preserved). 17 cancelled sessions total; every one inside an audit window was excluded on both sides.
5. **Rescheduling residue is inert.** Inactive QUIZ_DAY events (BCS-502 08-17, BNC-501 08-17, BCS-501 09-18) and the duplicate inactive BNC-501 08-24 row are ignored (active-only query + per-date dedup). A regular lecture still materialized on the abandoned 09-18 date correctly belongs to Quiz III's window as a normal class.
6. **No tutorials → average collapses to lecture %.** BNC-501 has zero tutorial sessions; `combined_pct` returns the lecture percentage (N/A tutorial displayed, not 0%). Verified on all three BNC-501 cycles.
7. **Practicals never enter eligibility.** All PRACTICAL sessions (146, including the cancelled mid-sem/lab cancellations) are normalized to `P` and never aggregated; labs themselves are excluded by `quiz_applicable=false` (404 at the endpoint).
8. **`occurrence_outcomes` is empty** in the current dataset, so per-subject outcome application (CANCELLED/EXTRA/MODIFIED) is a no-op here; the logic was still mirrored independently and code-inspected. EXTRA_LECTURE sessions (e.g., BNC-501 07-31 ×2, one from the EXTRA_LECTURE event, one from the SURPRISE_QUIZ event) are genuine counted lectures inside windows, per the frozen Q-D6 decision.
9. **Future sessions count as Pending, not absent.** Windows ending after 2026-09-04 (last record) contain unmarked sessions (e.g., BCS-054 Q1: 4 lectures + 1 tutorial pending; Quiz II/III windows: everything pending). Pending is included in the eligibility denominator (window-based formula) and in the optimizer's attendable set — per the frozen contract ("pending included, never silently treated as absent").
10. **Weekends.** 09-05/09-06 contain no materialized sessions (Sat/Sun non-working); windows ending 09-06 are unaffected. No Working Saturday / Emergency closure / Extra tutorial / Mid-sem break events are active in the audited windows, so their semantics were verified by code inspection only (they are covered by the frozen Phase 6/7 verifiers).
11. **Threshold source.** Persisted `eligibility_policies` (70/75/75) are used; the engine's hardcoded fallback (`determine_quiz_threshold`) is unreachable in practice. `combined_threshold` is deliberately unread (Phase 7.3) and equals `lecture_threshold` in all rows.
12. **Cross-quiz independence.** Each window derives only from its own subject's active event dates; no cross-subject or cross-cycle leakage (elective attribution verified structurally; the audited user resolves BCS-054/BCS-058 via their own subject ids because they have no elective choice on file).

### Cross-screen consistency

- **One quiz date:** Events tab (`/api/v1/events`, active events) = Calendar (`CalendarService` → same `academic_events`) = Quiz Eligibility (`quiz_repo` active QUIZ_DAY query) = dashboard snapshot (same batch inputs). One source, one date per subject/cycle — verified in data and code.
- **One attendance window → one count set:** Track/History/Subjects summaries use `get_subject_counts_up_to_date`/`get_subject_counts_for_user` (same occurrence collapse, *including* quiz-day sessions and dates through today); Quiz Eligibility uses the same collapse *plus* the date-bounded window and the quiz-day shape exclusion. Numeric proof (BCS-054, as of 2026-09-07): Track L 24/9/9/6 vs eligibility cumulative L 22/9/9/4 — the delta is exactly the 09-07 regular lecture + the 09-07 quiz-day session (date bound + shape rule); attended/missed identical (9/9 L, 3/3 T). Semantics differ **by documented design**, arithmetic never diverges within a window.
- **One eligibility calculation:** single endpoint ≡ dashboard batch (byte-identical, 18/18) ≡ independent recomputation (18/18).
- **Frontend is presentation-only:** `QuizEligibilityCard` renders backend `criterion_i` / `criterion_ii` / `final_criterion` / `optimization` / counts verbatim; `formatPct1` (`toFixed(1)`) is display rounding only; the card's color-variant comparisons (`>= required`) mirror the backend verdicts and never recompute eligibility. The quiz page's default tab comes from the backend `current-cycle` endpoint.

---

## 10. Discrepancies

**Mathematical discrepancies: none.** Across 18 subject/cycle combinations × 2 criteria × (windows, counts, percentages, pass/fail, must-attend, can-skip, reachability) × (single path, batch path, independent recomputation), zero mismatches were found.

**Policy-ambiguity notes (no defect; documented for awareness):**

1. **Inclusive previous-quiz-date boundary (interpretation, material to guidance).** Criterion I for Quiz N starts *on* the previous quiz's date; that day's regular classes count toward Quiz N's window (only the quiz-day-shaped session is excluded). This is the project's frozen reading of ADR-010 ("Quiz II begins counting strictly from the Quiz I boundary") and is provably self-consistent, but it is an interpretation: if the official notice intended "the day after the previous quiz", the affected guidance changes — e.g., BCS-501 Q2 Criterion I would exclude the 08-27 attended lecture (L 7/0/0/7 instead of 8/1/0/7) and its minimum attendance would rise from 3L+3T (6 classes, reaching exactly 75.0%) to 4L+3T (7 classes, 78.5714%); BNC-501 Q2's Must Attend would stay 3L (3/4 = 75.0% exactly). **Severity: policy ambiguity, not a math error. No action taken or recommended without the original notice text.**
2. **Optimizer tie-break prefers skipping lectures over tutorials** when multiple combinations reach the threshold with the same total attendance (sort key `(total_attend, l_attend)`). Documented product decision; mathematically valid; worth knowing when presenting "safe skip" to students. **Severity: presentation choice.**
3. **`combined_threshold` column is dead** (by design since Phase 7.3). If the two threshold columns ever diverge in future data, nothing reads the second one. Current data: equal. **Severity: latent data-model observation only.**
4. **Inactive-event / duplicate-event residue** (BNC-501's double 08-24 row; abandoned 09-18/08-17 events) is correctly ignored, but accumulates as data hygiene noise. **Severity: cosmetic/data hygiene.**
5. **External notice wording not in repo.** The audit could not independently verify the official notice's phrasing for Criterion I/II beyond ADR-010's summary and the project's frozen contract (§3). The implementation matches the project's own authoritative documents. **Severity: documentation provenance only.**

---

## 11. Security / Data Safety

- **No data mutations** — all database access used a connection with `default_transaction_read_only=on`; the application-path comparison ran inside a transaction that was explicitly rolled back.
- **No attendance mutations, no event mutations, no quiz-date mutations** — nothing was written by any audit script.
- **No migrations created or applied** (DB revision `f0e1d2c3b4a5` inspected read-only; it is the repo's single head).
- **No secrets exposed** — connection string/credentials never printed or stored in the report; `.env` contents only referenced by variable name.
- **No production access, no production writes** — audit used the local development database only; production was not connected to.
- **No commits, pushes, or deploys**; repository working tree verified clean before and after the audit; the only repository change is this report file. Scratch scripts live outside the repo.
- **No browser automation, no Playwright/Cypress, no test suites** were run; no source code was modified.

---

## 12. Final Recommendation

**PASS — the current Quiz Eligibility calculations are independently verified as mathematically correct for the audited dataset.** Specifically, for the local development database at revision `f0e1d2c3b4a5`, semester 2026-07-15 → 2026-12-31, user `2401220100027`, all six quiz-applicable theory subjects and all three quiz cycles: Criterion I, Criterion II, the final OR decision, and the Must Attend / Can Skip optimizer produce results identical to an independent recomputation built directly from the raw tables, and the single-subject and dashboard batch paths are byte-identical.

Nothing was fixed, because nothing was found to fix. The policy-ambiguity notes in §10 (inclusive previous-quiz-date boundary; lecture-preferring tie-break; dead `combined_threshold` column; inactive-event residue) are documented interpretations or hygiene observations, not calculation defects, and require no code change under the current frozen contract.

**Recommended (not performed) follow-ups, pending explicit authorization:**
1. If desired, archive the original SRMCEM notice (or its exact Criterion wording) into the repo so §10 note 1 can be closed as confirmed rather than interpretation.
2. A one-line governance annotation (MASTER_ROADMAP / changelog) recording this audit — recommended only after review, to preserve the read-only discipline of this pass.
3. Optional data hygiene: hard-delete the deactivated/duplicate QUIZ_DAY event rows noted in §9.5 (owner action through the app or a reviewed script; not done here).

**STOP.** Per the audit brief, this is a correctness audit only: no implementation, no fixes, no governance edits. Awaiting explicit authorization for any follow-up.
