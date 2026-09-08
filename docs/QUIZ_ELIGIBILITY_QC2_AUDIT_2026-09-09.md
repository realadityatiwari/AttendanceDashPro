# Quiz Eligibility QC-II Investigation Report

**Date:** 2026-09-09
**Mode:** INVESTIGATION ONLY — read-only. No application code, no migrations, no data mutations, no browser testing. All database access ran inside read-only transactions (rolled back); the application calculation path was executed in-process against the local dev database only.
**Audited user:** roll `2401220100027` (section CSE-51, V Semester 2026-07-15 → 2026-12-31), 170 attendance records, sessions materialized 2026-07-15 → 2026-12-31 (721 class_sessions), 0 `occurrence_outcomes` rows, no elective choices.
**Verification method:** the entire eligibility mathematics (windows, counts, percentages, thresholds, per-criterion pass/fail, per-criterion exhaustive Must-Attend/Safe-Skip enumeration, OR-route selection, canonical state) was **independently recomputed from raw tables with raw asyncpg + plain Python** (zero imports of the application's engines) and compared field-by-field against the application's real calculation path (`EligibilityService.get_quiz_eligibility_for_subjects` batch and the single-subject path) executed in-process inside a rolled-back read-only transaction. Scratch scripts live outside the repository (temp dir).

---

## 1. Executive Verdict

**NEEDS FIXES (guidance optimality) — the core mathematics are CORRECT.**

All **18 subject/cycle combinations** (6 quiz-applicable theory subjects × Quiz I/II/III) match the independent recomputation **exactly** — Criterion I windows, Criterion II windows, lecture/tutorial counts (total/attended/missed/pending), percentages (full precision), 70/75/75 thresholds, per-criterion pass/fail, per-criterion Must Attend / Safe Skip (exhaustive enumeration), the top-level OR-route selection, the `Criterion I OR Criterion II` decision, and the canonical state (ELIGIBLE / RECOVERABLE / NOT_ELIGIBLE). Never once does the engine mix C-I and C-II inputs: each criterion is evaluated on its own window with its own counts.

Two deviations from the investigation brief's optimization rules and several interpretation gaps were found:

1. **[HIGH] Safe Skip is not independently optimized.** The UI's top-level "Safe Skip (best route)" shows the skip count of the *minimum-Must-Attend* route, not the *maximum* skip across reachable routes. Must Attend **is** optimal under the OR rule (verified); Safe Skip **is not**: in 4 of 18 windows (all Quiz III windows) the other criterion permits strictly more skips (BCS-503 Q3: displayed 5, actual max 17; BCS-058 Q3: 4 vs 7; BCS-501 Q3: 5 vs 8; BCS-502 Q3: 5 vs 6). The displayed value is always *achievable* (it is a real qualifying combination — verified by enumeration) but understates the true maximum. For **QC-II (Quiz II) windows specifically there is no divergence in the current dataset** — but the deviation is structural and will appear in Q2 windows as data evolves.
2. **[MEDIUM] The selected criterion is not explicitly traceable.** The API response contains `criterion_i`, `criterion_ii`, and a top-level `optimization`, but **no field naming which criterion the top-level optimization came from**; the UI labels it only "(best route)". Traceability today is inferential (compare numbers), not explicit.
3. **[MEDIUM] "Must Attend" counts past-unmarked sessions as attendable.** Unmarked sessions — including dates already past — remain "Pending" forever and enter the optimizer's attendable set (e.g., BCS-058 Q1 "Must attend 6L+2T" includes 4 lectures + 2 tutorials dated before 2026-09-09). Achievable only by back-marking attendance in Track, never by physically attending. Documented product decision ("pending never silently treated as absent"), but the guidance does not distinguish "attend" from "must have attended / back-mark".
4. **The observed UI values quoted in the investigation brief cannot be reproduced from the audited database** (neither the 2026-09-07 audit snapshot nor the 2026-09-09 snapshot). See §5/§9 — this points to a different data state (most likely production or an earlier unlogged state), not to a calculation error.

No CRITICAL logic error. No cross-criterion contamination. The formula, windows, thresholds, and OR semantics are internally consistent and match the project's frozen contract.

---

## 2. Architecture / Data-Flow Findings

```
React QuizEligibilityCard (presentation only — renders backend fields; toFixed(1) display rounding)
  ↑ GET /api/v1/quiz-eligibility/{subject_code}/{quiz_cycle}   (single)
  ↑ dashboard_service._build_quiz_snapshot → get_quiz_eligibility_for_subjects (batch)
        │  both paths converge on EligibilityService._evaluate_subject  ← ONE canonical path
        ↓
EligibilityService._evaluate_subject
  ├─ _build_domain_subject (milestones from effective quiz dates)
  ├─ quiz_repo.get_effective_quiz_dates_for_subject(s)      ← active QUIZ_DAY events only,
  │                                                            chronological rank = cycle, per-date dedup
  ├─ calendar_engine.get_attendance_window          (C-I: prev quiz date → quiz−1)
  ├─ calendar_engine.get_cumulative_attendance_window (C-II: semester commencement → quiz−1)
  ├─ attendance_repo.get_subject_counts_between[_for_subjects] (exclude_quiz_day=True)
  │     └─ practical_occurrence.collapse_count_rows (cancelled excluded; P collapsed; L/T kept)
  ├─ _build_counts → {L,T} × {tot, att, miss, pending}     (status None = Pending)
  └─ eligibility_engine.evaluate_quiz_eligibility
        ├─ _evaluate_criterion("Criterion I", window_i, counts)      → (L%+T%)/2, optimize_attendance
        ├─ _evaluate_criterion("Criterion II", window_ii, cumulative) → (L%+T%)/2, optimize_attendance
        ├─ final.passed = criterion_i.passed OR criterion_ii.passed
        ├─ state: ELIGIBLE | RECOVERABLE (best-case ≥ required) | NOT_ELIGIBLE
        └─ best_opt = min(optI, optII, key=(not is_reachable, total deficit))  ← ties prefer C-I
```

**Single mathematics path confirmed.** The batch path (`Phase 26.3` one-scan bucketing + `_bucket_window_counts` + same `collapse_count_rows`) and the single-subject path produced **identical results** in this audit (all 18 batch results match the independent recomputation; BCS-501 Q2 single-path spot check identical to batch). The frontend performs **no** eligibility arithmetic.

**Exact files/functions responsible:**

| Responsibility | Location |
|---|---|
| Criterion I / II windows | `backend/app/engines/calendar_engine.py` — `_resolve_attendance_window` (`from_commencement=False/True`), `get_attendance_window` (C-I), `get_cumulative_attendance_window` (C-II) |
| Criterion evaluation + OR + state | `backend/app/engines/eligibility_engine.py` — `_evaluate_criterion`, `evaluate_quiz_eligibility`, `_combined_pct`, `_best_avg` |
| Formula `(L%+T%)/2` | `eligibility_engine._combined_pct`; `attendance_engine.meets_attendance_target` |
| Must Attend / Safe Skip | `backend/app/engines/attendance_engine.py` — `optimize_attendance` (exhaustive L×T enumeration, sort key `(total_attend, l_attend)`) |
| Top-level route selection | `eligibility_engine.evaluate_quiz_eligibility` — `best_opt = min(…, key=(not o.is_reachable, o.lecture_deficit + o.tutorial_deficit))` |
| Attendance aggregation / date filtering | `backend/app/repositories/attendance_repo.py` — `get_subject_counts_between` (single), `get_subject_counts_between_for_subjects` + `EligibilityService._bucket_window_counts` (batch); `practical_occurrence.collapse_count_rows` |
| Pending counts | `EligibilityService._build_counts` (status None → pending; pending included in `tot`) |
| Quiz dates (authoritative) | `backend/app/repositories/quiz_repo.py` — `get_effective_quiz_dates_for_subjects` (active QUIZ_DAY events, chronological ranking, dedup) |
| Thresholds | `eligibility_policies.lecture_threshold` via `quiz_repo.get_quiz_cycle_with_policy` (persisted 70/75/75; engine fallback `determine_quiz_threshold` is dead code in practice) |
| Service orchestration | `backend/app/services/eligibility_service.py` — `get_quiz_eligibility`, `get_quiz_eligibility_for_subjects`, `_evaluate_subject`, `_build_domain_subject` |
| Dashboard snapshot | `backend/app/services/dashboard_service.py` — `_build_quiz_snapshot`; `get_current_quiz_cycle` |
| UI | `frontend/src/components/quiz/QuizEligibilityCard.tsx` (renders `criterion_i`/`criterion_ii`/`final_criterion`/`optimization` verbatim; `CriterionRow.showGuidance` gates on `is_reachable`); `frontend/src/app/(authenticated)/tools/quiz-schedule/page.tsx` |

**Consistency:** the same calculation logic is reused everywhere; no competing eligibility implementation exists in the app. (The Track/History surfaces use `get_subject_counts_up_to_date`/`…_for_user` with deliberately different semantics — through-today, quiz-day sessions included — a documented design difference, not a divergence bug.)

---

## 3. Institutional-Rule Comparison

Authoritative in-repo sources: ADR-010 (`docs/18_ARCHITECTURE_DECISION_RECORDS.md:133`, summarizing the SRMCEM Attendance Criteria notice of 14 July 2026), `docs/S4_PRODUCT_SPEC.md` §5, `timetable.json`, MASTER_ROADMAP Phase 7.3 contract (per the 2026-09-07 audit), persisted `eligibility_policies`.

| Rule | Documents specify | Implementation | Verdict |
|---|---|---|---|
| Thresholds Q1/Q2/Q3 = 70/75/75 | ADR-010 explicitly | persisted `eligibility_policies.lecture_threshold` = 70.0/75.0/75.0 | ✅ matches |
| Final = C-I OR C-II | S4 spec §5 explicitly | `final.passed = ci.passed or cii.passed` | ✅ matches |
| C-I window: "QT-I date through one day before QT-II" | ADR-010: "Quiz II begins counting strictly from the Quiz I boundary"; the investigation brief's own wording says "QT-I date through…" (inclusive) | `window_start = prev_quiz.date` (inclusive), `window_end = quiz − 1` | ✅ matches the brief; ⚠️ inclusive-vs-exclusive reading of the notice remains an interpretation (unchanged since the 2026-09-07 audit, §10.1 there) |
| C-II window: subject's first class → day before quiz | Not stated in ADR-010 summary; brief says "subject's first class/lecture" | semester commencement (2026-07-15) for every subject | ✅ **equivalent for this dataset** — semester start ≤ every subject's first materialized session, and counting only includes real sessions, so the counted set is identical. Would differ only if a subject met before semester start (impossible here). Note `timetable.json` still carries a legacy BNC-501 `commencementDate` 2026-07-20 which the backend deliberately does not use. |
| Per-criterion formula | **NOT specified anywhere in the repo** — ADR-010 records thresholds + windows only; S4 §5 defines the OR but no formula | both criteria = `(Lecture % + Tutorial %) / 2` (no-tutorial subjects collapse to Lecture %) frozen in Phase 7.3 (superseded the Phase 7.1 "C-I = Lecture %" design on 2026-08-18, commit `ed6c3e2`) | ⚠️ **cannot be verified against the official notice** — the notice itself is not committed. The UI's "Average = (Lecture % + Tutorial %)/2" is a project decision, consistent app-wide, but not document-supported. Requires institutional confirmation. |
| Activity / co-curricular / sports / NCC attendance provisions | **No trace anywhere in the repository** (grep across docs/, MASTER_ROADMAP: zero hits for NCC/NSS/sports/co-curricular) | The eligibility engine has **no concept** of activity/exempted attendance; every eligibility percentage is computed purely from class-session marks | ⚠️ If the official notice grants deemed-attendance for sports/NCC/activities toward quiz eligibility, the engine does **not** model it and Quiz II eligibility would be understated for affected students. Cannot be established from repo material — needs the notice. |
| Quiz dates vs official Quiz Schedule | No official schedule document in repo; `timetable.json` milestones == DB active QUIZ_DAY events for all six subjects (verified); inactive event residue shows user edits (BCS-502 08-17→08-31, BNC-501 08-17→08-24, BCS-501 09-18→09-17, duplicate inactive BNC-501 08-24) | active events are authoritative (Phase 2) | ⚠️ internally consistent; **cannot be verified against the uploaded official schedule** (not committed). |
| Quiz-day sessions excluded from L/T counts | Project decision ("Option A", Phase 7.3) | shape filter `timetable_entry_id IS NULL AND NOT is_extra AND class_type=LECTURE` excluded | ✅ implemented as documented; regular timetable classes on quiz dates remain counted |

**What the documents definitively specify:** thresholds 70/75/75; two independent criteria combined by OR; Q2+ windows anchored at the previous quiz boundary; C-II cumulative.
**What the application assumes:** the (L%+T%)/2 formula for both criteria; inclusive previous-quiz-date start; semester start as C-II anchor; pending-in-denominator window formula; quiz-day session exclusion.
**What cannot be established from the documents:** the official per-criterion formula; whether activity/NCC/sports attendance counts; the official quiz schedule dates; inclusive vs exclusive previous-quiz boundary.
**Contradictions with the documents:** none found.

---

## 4. Formula Audit

- **Average = (Lecture % + Tutorial %) / 2** — implemented in `_combined_pct` (`eligibility_engine.py:27`) and `meets_attendance_target` (`attendance_engine.py:76`). Identical for C-I and C-II. Supported by the project's frozen Phase 7.3 contract, **not** verifiable against the institutional notice (absent from repo). The two prior audit layers (2026-09-07 and this one) both confirm internal consistency.
- **Rounding:** comparisons use **full float precision** (`avg >= required`); no rounding before any decision. Display-only rounding: backend explanation strings `f"{pct:.1f}%"`, frontend `toFixed(1)`. Independent recomputation matched to < 1e-9 on every float.
- **Percentage precision:** exact division, no truncation; boundary case **exactly 75% passes** (verified live: BCS-501 Q2 C-I reaches exactly (50.0 + 100.0)/2 = 75.0 with 3L+3T and `75.0 >= 75.0` → True; float-exact because 0.5 and 1.0 are binary-exact).
- **Denominator handling:** `tot` = all non-cancelled sessions in the window **including pending** (window-based formula). `_pct` guards `total == 0` → None. Tutorial absent → average collapses to lecture % (BNC-501 all cycles verified: avg = lecture %, tutorial shown as N/A).
- **Subjects with no lectures (latent edge):** `_combined_pct(None, tut_pct)` returns `None` → criterion can **never pass** while `optimize_attendance` (which defaults `sim_lec_pct = 0.0`) may report `is_reachable = True` for a tutorial-only subject → state NOT_ELIGIBLE with reachable optimizer (dashboard "attention" vs state mismatch). **No current subject triggers this** (every theory subject has lectures). Latent only.
- **Pending calculation:** status `None` → pending, regardless of date (see §9 edge case E3). `missed` only when explicitly marked MISSED. Cancelled sessions drop from numerator AND denominator (verified in data: cancelled BCS-058 07-29/30 sessions with stale marks excluded).
- **Already missed / future classes:** missed classes stay in `tot` forever (correct); future sessions are pending and enter both the denominator and the optimizer's attendable set.
- **Impossible routes / insufficient remaining classes:** best-case average (attend all pending) < required → `is_reachable = False`, deficit reported as full pending, state NOT_ELIGIBLE, UI withholds guidance (verified: BCS-054 Q1/Q2-C-II, BCS-501 Q1, BCS-502 Q1).
- **Already eligible:** must = 0, safe skip = all pending of the selected route (verified: BCS-503 Q1 skip 3L+1T; BNC-501 Q1 zero pending, skip 0).
- **Recoverable vs unrecoverable:** state machine correct in all 18 cases (ELIGIBLE ×2, NOT_ELIGIBLE ×3, RECOVERABLE ×13).

---

## 5. Complete Six-Subject Verification Table (data as of 2026-09-09)

Format per criterion: `L att/tot (miss, pend) · T att/tot (miss, pend) · avg% · pass · must L+T · skip L+T · reachable`. All values independently recomputed **and** matched against the application path (18/18 MATCH). Percentages rounded to 2 dp here; comparisons used full precision.

### Quiz I (threshold 70%) — C-I ≡ C-II window by definition

| Subject | Quiz date | Window | Criterion | Counts | Avg | Pass | Must Attend | Safe Skip | Reach | State |
|---|---|---|---|---|---|---|---|---|---|---|
| BCS-054 | 09-07 | 07-15→09-06 | I=II | L 9/22 (9m,4p) · T 3/7 (3m,1p) | 41.88 | FAIL | 4L+1T | 0 | **no** | NOT_ELIGIBLE |
| BCS-058 | 09-11 | 07-15→09-10 | I=II | L 8/25 (11m,6p) · T 5/8 (1m,2p) | 47.25 | FAIL | 6L+2T | 0 | yes | RECOVERABLE |
| BCS-501 | 08-27 | 07-15→08-26 | I=II | L 15/24 (9m,0p) · T 3/4 (1m,0p) | 68.75 | FAIL | 0 (window closed) | 0 | **no** | NOT_ELIGIBLE |
| BCS-502 | 08-31 | 07-15→08-30 | I=II | L 12/19 (7m,0p) · T 4/6 (2m,0p) | 64.91 | FAIL | 0 (window closed) | 0 | **no** | NOT_ELIGIBLE |
| BCS-503 | 09-03 | 07-15→09-02 | I=II | L 17/26 (6m,3p) · T 6/7 (0m,1p) | 75.55 | **PASS** | 0 | 3L+1T | yes | **ELIGIBLE** |
| BNC-501 | 08-24 | 07-15→08-23 | I=II | L 10/14 (4m,0p) · T — | 71.43 | **PASS** | 0 | 0 | yes | **ELIGIBLE** |

### Quiz II (threshold 75%) — the QC-II focus

| Subject | Quiz date | C-I window | C-II window | Criterion | Counts | Avg | Pass | Must | Safe Skip | Reach |
|---|---|---|---|---|---|---|---|---|---|---|
| BCS-054 | 09-28 | 09-07→09-27 | 07-15→09-27 | I | L 0/9 (0m,9p) · T 0/3 (0m,3p) | 0.00 | FAIL | **5L+3T** | 4L | yes |
| | | | | II | L 9/31 (9m,13p) · T 3/10 (3m,4p) | 29.52 | FAIL | 13L+4T (all pending) | 0 | **no** |
| BCS-058 | 10-05 | 09-11→10-04 | 07-15→10-04 | I | L 0/9 (0m,9p) · T 0/3 (0m,3p) | 0.00 | FAIL | **5L+3T** | 4L | yes |
| | | | | II | L 8/34 (11m,15p) · T 5/11 (1m,5p) | 34.49 | FAIL | 13L+5T | 2L | yes |
| BCS-501 | 09-17 | 08-27→09-16 | 07-15→09-16 | I | L 1/8 (0m,7p) · T 0/3 (0m,3p) | 6.25 | FAIL | **3L+3T** | 4L | yes |
| | | | | II | L 16/32 (9m,7p) · T 3/7 (1m,3p) | 46.43 | FAIL | 5L+3T | 2L | yes |
| BCS-502 | 09-21 | 08-31→09-20 | 07-15→09-20 | I | L 1/9 (0m,8p) · T 0/3 (0m,3p) | 5.56 | FAIL | **4L+3T** | 4L | yes |
| | | | | II | L 13/28 (7m,8p) · T 4/9 (2m,3p) | 45.44 | FAIL | 8L+3T | 0 | yes |
| BCS-503 | 09-24 | 09-03→09-23 | 07-15→09-23 | I | L 0/9 (0m,9p) · T 0/3 (0m,3p) | 0.00 | FAIL | 5L+3T | 4L | yes |
| | | | | II | L 17/35 (6m,12p) · T 6/10 (0m,4p) | 54.29 | FAIL | **1L+4T** | 11L | yes |
| BNC-501 | 09-14 | 08-24→09-13 | 07-15→09-13 | I | L 1/5 (0m,4p) · T — | 20.00 | FAIL | **3L** | 1L | yes |
| | | | | II | L 11/19 (4m,4p) · T — | 57.89 | FAIL | 4L | 0 | yes |

(All six Q2 results: state RECOVERABLE, final not eligible yet, route selection below.)

### Quiz III (threshold 75%)

| Subject | Quiz date | Criterion | Counts | Avg | Pass | Must | Safe Skip | Reach |
|---|---|---|---|---|---|---|---|---|
| BCS-054 | 10-23 | I | L 0/12 · T 0/4 (all pending) | 0.00 | FAIL | **6L+4T** | 6L | yes |
| | | II | L 9/43 (9m,25p) · T 3/14 (3m,8p) | 21.18 | FAIL | 22L+8T | 3L | yes |
| BCS-058 | 10-26 | I | L 0/9 · T 0/3 (all pending) | 0.00 | FAIL | **5L+3T** | 4L | yes |
| | | II | L 8/43 (11m,24p) · T 5/14 (1m,8p) | 27.16 | FAIL | 17L+8T | 7L | yes |
| BCS-501 | 10-12 | I | L 0/11 · T 0/3 (all pending) | 0.00 | FAIL | **6L+3T** | 5L | yes |
| | | II | L 16/43 (9m,18p) · T 3/10 (1m,6p) | 33.60 | FAIL | 10L+6T | 8L | yes |
| BCS-502 | 10-16 | I | L 0/11 · T 0/3 (all pending) | 0.00 | FAIL | **6L+3T** | 5L | yes |
| | | II | L 13/39 (7m,19p) · T 4/12 (2m,6p) | 33.33 | FAIL | 13L+6T | 6L | yes |
| BCS-503 | 10-21 | I | L 0/11 · T 0/4 (all pending) | 0.00 | FAIL | **6L+4T** | 5L | yes |
| | | II | L 17/46 (6m,23p) · T 6/14 (0m,8p) | 39.91 | FAIL | 6L+8T | 17L | yes |
| BNC-501 | 10-09 | I | L 0/8 (all pending) | 0.00 | FAIL | **6L** | 2L | yes |
| | | II | L 11/27 (4m,12p) | 40.74 | FAIL | 10L | 2L | yes |

---

## 6. Criterion I vs Criterion II Comparison + Route Selection (Q2 focus)

Top-level selection rule in code: `min(optI, optII, key=(not is_reachable, deficit_total))`, ties → Criterion I. Must Attend = minimum over **reachable** routes (never mixes criteria; each route's counts come solely from its own window).

| Subject | Q2 C-I must (total) | Q2 C-II must (total) | C-I reachable | C-II reachable | Selected route | Correct? (independent enumeration) |
|---|---|---|---|---|---|---|
| BCS-054 | 5L+3T (8) | 13L+4T (17) | yes | **no** (best 70.48 < 75) | **C-I** | ✅ unreachable C-II correctly loses despite smaller-key semantics; lexicographic `(not reachable, …)` prevents an unreachable route from ever winning while a reachable one exists |
| BCS-058 | 5L+3T (8) | 13L+5T (18) | yes | yes | **C-I** | ✅ 8 < 18 |
| BCS-501 | 3L+3T (6) | 5L+3T (8) | yes | yes | **C-I** | ✅ 6 < 8 |
| BCS-502 | 4L+3T (7) | 8L+3T (11) | yes | yes | **C-I** | ✅ 7 < 11 |
| BCS-503 | 5L+3T (8) | 1L+4T (5) | yes | yes | **C-II** | ✅ 5 < 8 — **the OR rule correctly switches to Criterion II when it is cheaper** (independently enumerated: C-II min total is 5; e.g. attend 1L+4T → L 18/35=51.43%, T 10/10=100% → 75.71% ≥ 75) |
| BNC-501 | 3L (3) | 4L (4) | yes | yes | **C-I** | ✅ 3 < 4 (3/5 lectures = exactly 60%+… (1+3)/5 = 80% ≥ 75; attending 2 → 60% ✗) |

**No mixing ever occurs:** `best_opt` is one criterion's own `OptimizationResult`; the final summary's Must Attend/Skip pair always comes from a single route. Verified structurally and numerically in all 18 combinations.

---

## 7. Must Attend Audit

Definition per brief: *minimum future classes that must be attended for at least ONE criterion to reach ≥ 75%* (70% for Q1).

**Verdict: CORRECT and optimal in all 18 combinations.** The top-level optimizer takes the minimum total deficit among **reachable** criteria; when both are unreachable the smaller deficit is reported with `is_reachable=false` (UI suppresses it). Exhaustive enumeration reproduces every value:

- tie-break `(total_attend, l_attend)` → among equal-total combos prefer fewer lectures (more lecture skips) — documented product choice, mathematically valid; reproduced independently everywhere (e.g., BCS-503 Q2 C-II picks 1L+4T, total 5).
- zero-pending semantics: window closed and below threshold → `0/0, is_reachable=false` → NOT_ELIGIBLE (BCS-501 Q1 68.75 < 70; BCS-502 Q1 64.91 < 70). Window closed and above → eligible, nothing to attend (BNC-501 Q1).
- **Caveat [MEDIUM]:** "future classes" in the optimizer means "pending sessions", and pending includes **past-unmarked** sessions (see §9 E3) — BCS-058 Q1's "Must attend 6L+2T" includes 4 lectures and 2 tutorials whose dates (08-31 → 09-08) are already past as of 09-09. The number is only achievable by back-marking those dates as attended in Track.

## 8. Safe Skip Audit

Definition per brief: *maximum future classes that can be skipped while still retaining at least ONE complete qualifying route* — explicitly allowed to select a **different** criterion than Must Attend.

**Verdict: the displayed value is always ACHIEVABLE, but it is NOT always the MAXIMUM.** The UI shows the skip of the min-Must-Attend route (`best_opt.safe_skip_*`), i.e., Must Attend and Safe Skip are forced onto the same criterion. Within one criterion the min-total combo does maximize that criterion's skips (skips = pending − attended), so the true optimum is `max over reachable criteria of per-criterion skips` — computable but not computed.

Divergences in the current dataset (displayed → true max):

| Combination | Displayed (route) | True max (route) | Understates by |
|---|---|---|---|
| BCS-503 Q3 | 5 (C-I: attend 10, skip 5) | **17** (C-II: attend 14, skip 17) | 12 |
| BCS-058 Q3 | 4 (C-I: attend 8) | **7** (C-II: attend 25) | 3 |
| BCS-501 Q3 | 5 (C-I: attend 9) | **8** (C-II: attend 16) | 3 |
| BCS-502 Q3 | 5 (C-I: attend 9) | **6** (C-II: attend 19) | 1 |

No Quiz I or Quiz II window diverges **today** (for every Q2 combination the selected route also has the max skips — e.g., BCS-503 Q2: displayed 11 = max 11 via C-II). The deviation is structural, not data-dependent: any future state where the non-selected criterion has more pending classes can surface it. Note the trade-off is real: the max-skip route requires *attending more classes in total* (BCS-503 Q3: attend 14 to skip 17, vs attend 10 to skip 5) — surfacing both routes (or a "max safe skip" line) is a product decision, but under the brief's stated rule the current single-route display is not the optimum.

**On the brief's specific question** — "BCS-503 … displayed Safe Skip of 8 lectures is mathematically achievable?": the quoted observation (C-I 16.7%, C-II 65.0%, must 0L+2T, skip 8) **cannot be reproduced** on the audited database at either 2026-09-07 (prior audit tables) or 2026-09-09 (this audit: C-I 0.00%, C-II 54.29%, must 5 vs 1L+4T, skip 11). Structurally, every skip count the engine ever displays belongs to a enumerated qualifying combination, so displayed skips are always achievable — but the specific "8" cannot be re-verified against this dataset (see §9 E6).

---

## 9. Edge Cases Found

1. **Quiz-day sessions (Option A):** excluded from all eligibility L/T counts by shape (`timetable_entry_id IS NULL AND NOT is_extra AND LECTURE`); regular timetable classes on quiz dates count in the *next* window. Verified in data: BCS-501 08-27 has both a counted ATTENDED lecture and an excluded MISSED quiz-day session; same for BNC-501 08-24, BCS-503 09-03.
2. **Inclusive previous-quiz boundary:** BCS-501 Q2 C-I includes the 08-27 lecture (the "1 attended" in L 1/8); BNC-501 Q2 C-I includes the 08-24 lecture. Matches the brief's wording ("QT-I date through one day before QT-II"); remains an interpretation of ADR-010's "strictly from the Quiz I boundary". If the notice meant exclusive, BCS-501 Q2 C-I would be L 0/7 → must attend 4L+3T (7 total, 78.57%) instead of 3L+3T (6, exactly 75.0).
3. **Past-unmarked sessions are "Pending" forever** (BCS-058 Q1: 6 of 8 pending are dated before 09-09; BCS-503 Q1: all 4 pending are past). They stay in the denominator and the optimizer's attendable set — guidance is satisfiable only by back-marking. Documented product decision; flagged because "Must Attend" reads as future action.
4. **Cancelled ≠ absent:** cancelled sessions (17 in DB) drop from numerator and denominator even when stale attendance records exist (BCS-058 07-29/07-30).
5. **Rescheduled quizzes:** inactive QUIZ_DAY residue (BCS-502 08-17, BNC-501 08-17 + duplicate 08-24, BCS-501 09-18) correctly ignored; the 09-18 abandoned-date lecture lands in Q3's window as a normal class.
6. **Observed UI values not reproducible:** the brief's quoted observations (BCS-503 C-I 16.7%/C-II 65.0%; BCS-058 C-II 47.5% must 10L+3T; BCS-501 C-I must 1L+1T / C-II 3L+1T) match **neither** the 2026-09-07 audit snapshot **nor** the 2026-09-09 snapshot of the local dev DB. BCS-058's quoted C-I row (0.0%, 5L+3T, skip 4) matches Q2/Q3 C-I exactly, while its quoted C-II row matches no cycle — suggesting the observations come from a different data state or environment (production?) or mixed dates. **The local database is the only environment audited; production was never accessed.**
7. **Zero-pending passing** (BNC-501 Q1): reachable with 0/0/0/0; UI hides the guidance line (`hasOpt` false) — correct, nothing remains to skip.
8. **No tutorials:** average collapses to lecture % (BNC-501, all cycles). UI hides the tutorial bar and shows "N/A".
9. **Latent tutorial-only subject inconsistency** (§4): avg None (never passes) while optimizer may claim reachable. No current subject.
10. **Degenerate window** (quiz on/before its own boundary): returns an empty window → zero counts → NOT_ELIGIBLE path; not triggered in current data.
11. **`current-cycle` endpoint** returns Quiz 1 (basis `next_upcoming`, BCS-058 09-11) — correct given BCS-058 Q1 is the next quiz ≥ today; the Quiz page's default tab follows it. QC-II analysis above is tab-independent.
12. **Batch ≡ single path** (Phase 26.3 bucketing): byte-identical results (all 18 batch results verified against independent recomputation; BCS-501 Q2 single-path spot check identical).
13. **`combined_threshold` column** unread by design (equals `lecture_threshold` in all rows) — latent data-model observation only.

---

## 10. Bugs / Inconsistencies (ranked)

### CRITICAL — none

### HIGH

**H-1. Safe Skip is not independently optimized across criteria.**
- **Current behavior:** top-level Safe Skip = the skip pair of the min-Must-Attend route (`eligibility_engine.py:233-236` `best_opt = min(...)`; `QuizEligibilityCard.tsx:228-244` renders both boxes from `eligibility.optimization`).
- **Expected behavior (per the brief's optimization rules):** Safe Skip = `max over reachable criteria of that criterion's safe skips`, explicitly allowed to select a different criterion than Must Attend.
- **Mathematical reasoning:** within a criterion, min-total attendance maximizes that criterion's skips; across criteria the max can belong to the *other* route. BCS-503 Q3: C-I attend 10/skip 5 vs C-II attend 14/skip 17 — the engine displays 5 though 17 skips retain a full qualifying route (attend 6L+8T → L 23/46=50%, T 14/14=100% → 75.0% exactly).
- **Affected subjects:** BCS-503, BCS-058, BCS-501, BCS-502 (all Quiz III windows today; structural for any future state).
- **Code location:** `backend/app/engines/eligibility_engine.py:233-236` + `frontend/src/components/quiz/QuizEligibilityCard.tsx:237-243`.
- **Confidence:** High (independent enumeration; 4 live divergences). Note: never overstates; never affects eligibility/state — guidance optimality only.

### MEDIUM

**M-1. Selected criterion for the top-level guidance is not exposed.**
- **Current:** `EligibilityResult` has no "selected_criterion" field; UI labels the boxes only "(best route)". The user must diff C-I vs C-II rows to infer the source.
- **Expected:** an explicit traceable field (e.g., `optimization.source = "Criterion II"`) rendered in the UI.
- **Reasoning:** the brief's requirement 17 ("the selected criterion is explicitly traceable") is not met; traceability is currently inferential.
- **Location:** `backend/app/schemas/attendance.py` (`EligibilityResult`), `eligibility_engine.evaluate_quiz_eligibility` (return), `QuizEligibilityCard.tsx:231,238`.
- **Confidence:** High (structural).

**M-2. Must Attend / Safe Skip include past-unmarked sessions as attendable.**
- **Current:** pending = every unmarked session in the window regardless of date; optimizer treats all as attendable (BCS-058 Q1 must 6L+2T includes 4L+2T already past on 09-09).
- **Expected:** guidance that distinguishes future classes from past-unlogged classes (or a documented "back-markable" semantics surfaced in the UI).
- **Reasoning:** a student who did not attend the past dates cannot satisfy the guidance by attendance alone; the current number conflates "attend" with "have attended + logged".
- **Affected:** every window with past-unmarked sessions (BCS-058 Q1, BCS-503 Q1 today; shrinks as marks are entered).
- **Location:** `attendance_engine.optimize_attendance` (attendable = pending), `EligibilityService._build_counts` (None → pending).
- **Confidence:** High on the behavior; the *policy* (back-marking allowed) is a documented product decision — the gap is presentational honesty, not arithmetic.

**M-3. Observed UI values unreproducible against the audited database.**
- **Current:** the brief's quoted observations match no snapshot of the local dev DB (09-07 or 09-09).
- **Expected:** quoted UI numbers should be reproducible from the authoritative data source.
- **Reasoning:** both audit layers agree with each other and differ from the quotes; the quotes likely come from production (never accessed by this audit) or a mixed-date reading.
- **Action:** clarify environment/data date before treating quoted values as regression evidence. **Confidence:** High that a discrepancy exists; Low on its cause.

### LOW

**L-1. Latent tutorial-only subject inconsistency** — `_combined_pct(None, tut)` → None (criterion can never pass) while `optimize_attendance` may report reachable (defaults `sim_lec_pct=0.0`); dashboard would count "attention" while state is NOT_ELIGIBLE. No current subject. `eligibility_engine.py:27-34` vs `attendance_engine.py:111`. Confidence: High (code path), no live impact.

**L-2. Unreachable-criterion guidance hidden** (`CriterionRow.showGuidance` requires `is_reachable === true`) — BCS-054 Q2 C-II shows counts/percentage but no recovery line. Correct per the D1 product decision (its "deficit" = full pending is not actionable), but this is why the UI "does not expose complete Criterion-II recovery information" for such rows. The backend *does* compute and return C-II's full optimization (`criterion_ii.optimization` present in every response — verified). `QuizEligibilityCard.tsx:49-53`. Confidence: High.

**L-3. Dead `combined_threshold` plumbing** (by design since Phase 7.3). Latent divergence risk if the columns ever differ. Confidence: High.

**L-4. Event-residue hygiene** — inactive/duplicate QUIZ_DAY rows accumulate (BCN-501 double 08-24; abandoned 08-17/09-18 dates). Ignored by the active-only query; cosmetic. Confidence: High.

**L-5. Guidance lines omit zero-valued tutorial parts** ("Safe skip: 4 lectures" when tutorial skip is 0) — cosmetic asymmetry, values correct. `QuizEligibilityCard.tsx:74-77`. Confidence: High.

---

## 11. Exact Files / Functions Involved

See the table in §2. All eligibility mathematics lives in exactly two engines (`eligibility_engine.py`, `attendance_engine.py`) fed by exactly one counting pipeline (`attendance_repo` + `collapse_count_rows`); the service layer orchestrates and the React card is presentation-only. No duplicate/divergent calculation path exists in the application.

## 12. Recommended Fixes (NOT implemented — awaiting authorization)

1. **H-1:** compute Safe Skip independently — `safe_skip = max((optI, optII), key=skips_total)` over reachable criteria — and either (a) render a separate "Max Safe Skip (route X)" line, or (b) keep the pair but relabel honestly. One engine change + one UI change; no schema change strictly required if derived client-side from the existing per-criterion `optimization` fields (both are already in the response).
2. **M-1:** add `selected_criterion` (and optionally `safe_skip_criterion`) to `EligibilityResult`; render it in the Must Attend / Safe Skip boxes.
3. **M-2:** split pending into `pending_future` / `pending_past_unmarked` in `ClassCounts` (additive, backward-compatible) and surface "of which N are past dates (back-markable)" in the guidance; or document the back-marking semantics in the UI copy.
4. **M-3:** confirm which environment produced the quoted observations; if production, schedule a read-only production parity check before treating them as regression evidence.
5. **L-1:** make `optimize_attendance` return `is_reachable=False` when `tot_l == 0 and tot_t == 0`-style degenerate inputs would let the 0.0-default lecture percentage mask a `None` average (or make `_combined_pct`/optimizer agree on the None semantics).
6. **L-4:** one-time cleanup of inactive QUIZ_DAY residue (owner action).
7. Policy confirmations (§13) before any change to formula/windows.

## 13. Assumptions Requiring Institutional Clarification

1. **Per-criterion formula:** does the official notice define Criterion I/II as (Lecture% + Tutorial%)/2, lecture-only, or something else? The repo's ADR-010 summary records only thresholds + windows. The current formula is a frozen project decision (Phase 7.3), not document-derived.
2. **Previous-quiz boundary inclusivity:** "from the Quiz I boundary" — inclusive of the QT-I date (current, matches the brief's wording) or the day after? Material to BCS-501 Q2 (must attend 6 vs 7 classes) and BNC-501 Q2.
3. **Activity / co-curricular / sports / NCC provisions:** if the notice grants deemed/exempted attendance (e.g., for sports or NCC participation) toward quiz eligibility, the engine has no support and eligibility is understated for affected students. No trace of such a provision exists in the repo.
4. **Pending/unmarked semantics:** may past-unattended classes be back-marked (current model), or should unmarked past classes count as missed for eligibility?
5. **Quiz schedule authority:** the official Quiz Schedule document is not in the repo; DB active events (user-editable) are the sole authority and have been edited at least four times.
6. **Safe Skip product semantics:** should the UI surface the true maximum skips (possibly on a different criterion with a larger attendance requirement), or keep the single best-route pair?

---

## Data & Safety

Read-only throughout: raw-SQL runs inside `readonly` transactions (rolled back); the app path ran inside a `SET TRANSACTION READ ONLY` transaction that was rolled back. No production access. No code, config, migration, or data changes. The only repository changes are this report and the governance-document entries. Scratch scripts live in the Windows temp dir (outside the repo). No browser automation or test suites were run.

**AUDIT COMPLETE — verdict: NEEDS FIXES** (mathematics correct and independently verified; Safe Skip optimization and traceability require attention; several policy points need institutional confirmation).
