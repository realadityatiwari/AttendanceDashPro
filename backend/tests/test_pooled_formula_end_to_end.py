"""Chunk 8 — pooled-formula end-to-end divergence matrix (DB-free).

Every test here constructs cases where the OLD formula

    (lecture_percentage + tutorial_percentage) / 2

and the NEW canonical pooled formula

    (lecture_present + tutorial_present)
    ------------------------------------ x 100
    (lecture_conducted + tutorial_conducted)

DISAGREE, and asserts that production (engine -> service consumers) follows the
POOLED model. The OLD arithmetic mean is computed inline ONLY as a regression
reference — production helpers are never reimplemented for assertions; the
canonical `pooled_pct` / `optimize_attendance` / `evaluate_quiz_eligibility`
are exercised directly (the same call path the services use).

Categories covered (Task 4 matrix): A lecture-heavy denominator, B
tutorial-heavy, C lecture pass / tutorial fail, D lecture fail / tutorial pass,
E exact 75% boundary, F just below 75, G just above 75, H lecture-only,
I tutorial-only, J zero conducted, K pending forecast, L pending + missed,
M both L/T zero, N same arithmetic mean but different pooled result.

Task 5 (subject pipeline), Task 6 (eligibility pipeline incl. window
boundaries for quiz-day semantics) and Task 7 (optimizer divergence + consumer
agreement) are covered below.
"""
from datetime import date

import pytest

from app.engines.attendance_engine import (
    compute_subject_stats,
    meets_attendance_target,
    optimize_attendance,
    pooled_pct,
)
from app.engines.calendar_engine import (
    get_attendance_window,
    get_cumulative_attendance_window,
)
from app.engines.eligibility_engine import evaluate_quiz_eligibility
from app.schemas.academic import Milestone, Subject, SubjectCategory, Timeline
from app.schemas.attendance import EligibilityState
from app.services.attendance_service import _build_subject_summary

TARGET = 75.0


# ---------------------------------------------------------------------------
# Reference-only OLD model (NEVER production code — used solely to prove that
# production does NOT follow it).
# ---------------------------------------------------------------------------
def old_mean(lec_pct, tut_pct):
    """OLD formula: arithmetic mean of the two per-type percentages, with the
    historical no-tutorial collapse and the tutorial-only None quirk."""
    if tut_pct is None:
        return lec_pct
    if lec_pct is None:
        return None
    return (lec_pct + tut_pct) / 2.0


def pct(att, tot):
    return (att / tot * 100.0) if tot else None


def c(tot=0, att=0, miss=0, pending=0):
    return {"tot": tot, "att": att, "miss": miss, "pending": pending}


def counts(l, t):
    return {"L": l, "T": t}


def merge_counts(base, extra):
    """Cumulative window counts = pre-window + cycle-window (canonical count
    contract: every field sums)."""
    out = {}
    for key in ("L", "T"):
        b, e = base.get(key, c()), extra.get(key, c())
        out[key] = c(
            tot=b["tot"] + e["tot"],
            att=b["att"] + e["att"],
            miss=b["miss"] + e["miss"],
            pending=b["pending"] + e["pending"],
        )
    return out


def _subject(milestones):
    return Subject(
        code="BCS-501",
        name="DBMS",
        category=SubjectCategory.THEORY,
        quiz_applicable=True,
        attendance_applicable=True,
        timeline=Timeline(commencement_date=date(2026, 7, 15), milestones=milestones),
    )


_Q1 = Milestone(milestone_id="q1", date=date(2026, 8, 24), type="QUIZ", metadata={"quizCycle": 1})
_Q2 = Milestone(milestone_id="q2", date=date(2026, 9, 14), type="QUIZ", metadata={"quizCycle": 2})


def evaluate(counts_i, pre_counts=None, cycle=2, threshold=75.0):
    """Run the canonical eligibility engine on constructed window counts.
    The cumulative (Criterion II) window is the pre-window + cycle window."""
    cumulative = (
        merge_counts(pre_counts, counts_i) if pre_counts is not None else counts_i
    )
    return evaluate_quiz_eligibility(
        _subject([_Q1, _Q2]),
        cycle,
        counts_i,
        events=[],
        default_weekends=[0, 6],
        policy_thresholds={"lecture_threshold": threshold},
        cumulative_counts=cumulative,
    )


# ===========================================================================
# Task 4 — divergence matrix (subject-current semantics via pooled_pct /
# meets_attendance_target). Each case: OLD != NEW.
# ===========================================================================

def test_A_lecture_heavy_denominator():
    # L 2/5 (40%), T 7/7 (100%): pooled (2+7)/12 = 75.0; OLD (40+100)/2 = 70.
    new = pooled_pct(2, 5, 7, 7)
    old = old_mean(pct(2, 5), pct(7, 7))
    assert new == pytest.approx(75.0)
    assert old == pytest.approx(70.0)
    assert meets_attendance_target(2, 5, 7, 7, TARGET) is True   # OLD would fail
    assert meets_attendance_target(2, 5, 7, 7, TARGET) != (old >= TARGET)


def test_B_tutorial_heavy_denominator():
    # L 10/10 (100%), T 8/20 (40%): pooled 18/30 = 60; OLD (100+40)/2 = 70.
    new = pooled_pct(10, 10, 8, 20)
    old = old_mean(pct(10, 10), pct(8, 20))
    assert new == pytest.approx(60.0)
    assert old == pytest.approx(70.0)
    assert meets_attendance_target(10, 10, 8, 20, TARGET) is False


def test_C_lecture_pass_tutorial_fail():
    # L 5/5 (100%), T 10/20 (50%): pooled 15/25 = 60; OLD exactly 75 (would
    # pass the boundary). Production FAILS where the old model passed.
    new = pooled_pct(5, 5, 10, 20)
    old = old_mean(pct(5, 5), pct(10, 20))
    assert new == pytest.approx(60.0)
    assert old == pytest.approx(75.0)
    assert meets_attendance_target(5, 5, 10, 20, TARGET) is False
    assert (old >= TARGET) is True


def test_D_lecture_fail_tutorial_pass():
    # L 5/20 (25%), T 5/5 (100%): pooled 10/25 = 40; OLD 62.5.
    new = pooled_pct(5, 20, 5, 5)
    old = old_mean(pct(5, 20), pct(5, 5))
    assert new == pytest.approx(40.0)
    assert old == pytest.approx(62.5)


def test_E_exact_75_boundary_passes():
    # L 2/5, T 7/7: pooled exactly 75 -> >= target passes (full precision).
    assert pooled_pct(2, 5, 7, 7) == pytest.approx(75.0)
    assert meets_attendance_target(2, 5, 7, 7, 75.0) is True
    assert meets_attendance_target(2, 5, 7, 7, 75.0001) is False


def test_F_just_below_75():
    # L 3/4 (75%), T 5/7 (71.43%): pooled 8/11 = 72.73 < 75; OLD 73.21 < 75.
    new = pooled_pct(3, 4, 5, 7)
    old = old_mean(pct(3, 4), pct(5, 7))
    assert new < 75.0 and old < 75.0
    assert meets_attendance_target(3, 4, 5, 7, TARGET) is False


def test_G_just_above_75():
    # L 3/4 (75%), T 11/14 (78.57%): pooled 14/18 = 77.78 > 75; OLD 76.79.
    new = pooled_pct(3, 4, 11, 14)
    old = old_mean(pct(3, 4), pct(11, 14))
    assert new == pytest.approx(14 / 18 * 100.0)
    assert new > 75.0 and old > 75.0
    assert meets_attendance_target(3, 4, 11, 14, TARGET) is True


def test_H_lecture_only_collapses():
    # L 8/10, no tutorials: pooled == lecture % (80). OLD mean produced the
    # same VALUE here via its special case — same number, different model.
    new = pooled_pct(8, 10, 0, 0)
    old = old_mean(pct(8, 10), None)
    assert new == pytest.approx(80.0)
    assert old == pytest.approx(80.0)
    assert meets_attendance_target(8, 10, 0, 0, TARGET) is True


def test_I_tutorial_only_definedness_divergence():
    # L 0/0, T 6/8 (75%): pooled returns 75 (a missing type contributes
    # nothing). The OLD mean returned None for tutorial-only subjects — the
    # production result is now DEFINED where the old model was not.
    new = pooled_pct(0, 0, 6, 8)
    old = old_mean(None, pct(6, 8))
    assert new == pytest.approx(75.0)
    assert old is None
    assert meets_attendance_target(0, 0, 6, 8, TARGET) is True


def test_J_zero_conducted_is_none():
    assert pooled_pct(0, 0, 0, 0) is None
    assert meets_attendance_target(0, 0, 0, 0, TARGET) is False


def test_K_pending_forecast_pooled():
    # Forecast: pending treated as attended, pooled over L+T totals.
    # L 2 att / 1 miss / 2 pend of 5; T 7 att of 7.
    # pooled forecast = (2+2+7)/(5+7) = 11/12 = 91.67; OLD best-mean =
    # ((4/5) + (7/7))/2 = 90.0.
    summary = compute_subject_stats("X", {"counts": counts(
        c(tot=5, att=2, miss=1, pending=2), c(tot=7, att=7))})
    old = old_mean(pct(2 + 2, 5), pct(7 + 0, 7))
    assert summary.forecast_avg_pct == pytest.approx(11 / 12 * 100.0)
    assert old == pytest.approx(90.0)
    assert summary.forecast_avg_pct != pytest.approx(old)


def test_L_pending_plus_missed_forecast_and_current():
    # L 4 att / 2 miss / 4 pend of 10; T 5 att / 3 miss / 2 pend of 10.
    # current pooled = 9/14 = 64.29 (OLD 45); forecast pooled = 15/20 = 75
    # exactly (OLD forecast-mean = (80+70)/2 = 75 — equal value here, but the
    # CURRENT divergence still proves the model switch).
    summary = compute_subject_stats("X", {"counts": counts(
        c(tot=10, att=4, miss=2, pending=4), c(tot=10, att=5, miss=3, pending=2))})
    assert summary.current_avg_pct == pytest.approx(9 / 14 * 100.0)
    assert summary.current_avg_pct != pytest.approx(old_mean(pct(4, 6), pct(5, 8)))
    assert summary.forecast_avg_pct == pytest.approx(75.0)


def test_M_both_zero_current_and_forecast_none():
    summary = compute_subject_stats("X", {"counts": counts(c(), c())})
    assert summary.current_avg_pct is None
    assert summary.forecast_avg_pct is None


def test_N_same_old_mean_different_pooled():
    # Two subjects with the SAME old-mean value (75) but DIFFERENT pooled
    # values: the old model conflates them, the pooled model distinguishes.
    s1 = pooled_pct(5, 5, 5, 10)    # L 100% (5/5), T 50% (5/10)  -> 66.67
    s2 = pooled_pct(10, 10, 5, 10)  # L 100% (10/10), T 50% (5/10) -> 75.0
    m1 = old_mean(pct(5, 5), pct(5, 10))
    m2 = old_mean(pct(10, 10), pct(5, 10))
    assert m1 == pytest.approx(75.0) and m2 == pytest.approx(75.0)
    assert s1 == pytest.approx(200 / 3)
    assert s2 == pytest.approx(75.0)
    assert s1 != pytest.approx(s2)


# ===========================================================================
# Task 5 — subject pipeline: data -> compute_subject_stats -> current/forecast
# (3+ unequal-denominator cases; per-type percentages unchanged).
# ===========================================================================

def test_subject_pipeline_unequal_case_1():
    summary = compute_subject_stats("BCS-501", {"counts": counts(
        c(tot=5, att=2, miss=3), c(tot=7, att=7))})
    assert summary.current_lecture_pct == pytest.approx(40.0)      # unchanged
    assert summary.current_tutorial_pct == pytest.approx(100.0)    # unchanged
    assert summary.current_avg_pct == pytest.approx(75.0)          # pooled 9/12
    assert summary.current_avg_pct != pytest.approx(old_mean(40.0, 100.0))
    assert summary.forecast_avg_pct == pytest.approx(75.0)  # no pending == current


def test_subject_pipeline_unequal_case_2():
    summary = compute_subject_stats("BCS-502", {"counts": counts(
        c(tot=2, att=1, miss=1), c(tot=10, att=4, miss=6))})
    assert summary.current_lecture_pct == pytest.approx(50.0)
    assert summary.current_tutorial_pct == pytest.approx(40.0)
    assert summary.current_avg_pct == pytest.approx(5 / 12 * 100.0)  # pooled 5/12
    assert summary.current_avg_pct != pytest.approx(old_mean(50.0, 40.0))
    assert summary.forecast_avg_pct == pytest.approx(5 / 12 * 100.0)


def test_subject_pipeline_unequal_case_3_forecast_pending():
    summary = compute_subject_stats("BCS-503", {"counts": counts(
        c(tot=10, att=4, miss=2, pending=4), c(tot=4, att=1, miss=1, pending=2))})
    assert summary.current_avg_pct == pytest.approx(5 / 8 * 100.0)   # 5/8 conducted
    assert summary.forecast_avg_pct == pytest.approx(11 / 14 * 100.0)  # +6 pending
    assert summary.forecast_avg_pct > summary.current_avg_pct
    # OLD forecast mean: ((8/10) + (3/4))/2 = 77.5 — production is NOT that.
    assert summary.forecast_avg_pct != pytest.approx(old_mean(80.0, 75.0))


# ===========================================================================
# Task 6 — eligibility pipeline: windows -> criteria -> best case -> state ->
# optimizer, through the canonical evaluate_quiz_eligibility.
# ===========================================================================

def test_elig_1_pooled_fails_old_mean_passes():
    # L 100% (2/2), T 60% (6/10): pooled 8/12 = 66.67 < 75 (FAIL);
    # OLD mean (100+60)/2 = 80 would have PASSED Criterion I.
    res = evaluate(counts(c(tot=2, att=2), c(tot=10, att=6)))
    old = old_mean(pct(2, 2), pct(6, 10))
    assert old >= 75.0
    assert res.criterion_i.value == pytest.approx(8 / 12 * 100.0)
    assert res.criterion_i.passed is False
    assert res.state == EligibilityState.NOT_ELIGIBLE


def test_elig_2_pooled_passes_old_mean_fails():
    # L 2/5, T 7/7: pooled 75 passes; OLD mean 70 would have failed.
    res = evaluate(counts(c(tot=5, att=2, miss=3), c(tot=7, att=7)))
    old = old_mean(pct(2, 5), pct(7, 7))
    assert old < 75.0
    assert res.criterion_i.value == pytest.approx(75.0)
    assert res.criterion_i.passed is True
    assert res.state == EligibilityState.ELIGIBLE


def test_elig_3_best_case_pooled_fails_old_best_passes():
    # L 5/10 (50%, 0 pending), T 0/2 with 2 pending: pooled best = 7/12 =
    # 58.33 < 75 -> NOT_ELIGIBLE. OLD mean-based best = (50+100)/2 = 75 would
    # have declared RECOVERABLE.
    res = evaluate(counts(c(tot=10, att=5, miss=5), c(tot=2, att=0, miss=0, pending=2)))
    old_best = old_mean(pct(5 + 0, 10), pct(0 + 2, 2))
    assert old_best >= 75.0
    assert res.criterion_i.value == pytest.approx(5 / 12 * 100.0)
    assert res.criterion_ii.value == pytest.approx(5 / 12 * 100.0)
    assert res.state == EligibilityState.NOT_ELIGIBLE
    assert res.recoverable is False


def test_elig_4_best_case_pooled_passes_recoverable():
    # L 6/10 (60%), T 5/10 with 5 pending: current pooled 55 fails, best
    # pooled 16/20 = 80 passes -> RECOVERABLE.
    res = evaluate(counts(c(tot=10, att=6, miss=4), c(tot=10, att=5, miss=0, pending=5)))
    assert res.state == EligibilityState.RECOVERABLE
    assert res.recoverable is True
    assert res.is_eligible is False


def test_elig_5_criterion_i_eligible_criterion_ii_not():
    # Cycle window L 7/8 (87.5); pre-window L 0/10 -> cumulative 7/18 (38.9).
    res = evaluate(counts(c(tot=8, att=7, miss=1), c()), pre_counts=counts(c(tot=10, att=0, miss=10), c()))
    assert res.criterion_i.passed is True
    assert res.criterion_i.value == pytest.approx(87.5)
    assert res.criterion_ii.passed is False
    assert res.criterion_ii.value == pytest.approx(7 / 18 * 100.0)
    assert res.state == EligibilityState.ELIGIBLE          # OR semantics
    assert res.final_criterion.passed is True


def test_elig_6_criterion_ii_eligible_criterion_i_not():
    # Cycle 0/8; pre 24/24 -> cumulative 24/32 = exactly 75 passes.
    res = evaluate(counts(c(tot=8, att=0, miss=8), c()), pre_counts=counts(c(tot=24, att=24), c()))
    assert res.criterion_i.passed is False
    assert res.criterion_ii.passed is True
    assert res.criterion_ii.value == pytest.approx(75.0)
    assert res.state == EligibilityState.ELIGIBLE
    # Route selection unchanged: the reachable route (Criterion II) wins.
    assert res.must_attend_criterion == "Criterion II"
    assert res.optimization.lecture_deficit == 0 and res.optimization.tutorial_deficit == 0


def test_elig_7_both_eligible():
    res = evaluate(counts(c(tot=8, att=7, miss=1), c()), pre_counts=counts(c(tot=20, att=20), c()))
    assert res.criterion_i.passed is True and res.criterion_ii.passed is True
    assert res.state == EligibilityState.ELIGIBLE


def test_elig_8_neither_eligible():
    res = evaluate(counts(c(tot=8, att=0, miss=8), c()), pre_counts=counts(c(tot=10, att=0, miss=10), c()))
    assert res.criterion_i.passed is False and res.criterion_ii.passed is False
    assert res.state == EligibilityState.NOT_ELIGIBLE


def test_elig_9_10_window_boundaries_previous_quiz_date_and_quiz_day():
    # Quiz-day semantics at the calendar-engine level (DB-free): the cycle-2
    # window STARTS on the previous quiz date (regular L/T classes on that
    # date remain inside the eligibility window) and ENDS the day before the
    # quiz (the quiz-day session itself is excluded from the counts window).
    subject = _subject([_Q1, _Q2])
    w_i = get_attendance_window(subject, "q2", [], [0, 6])
    w_ii = get_cumulative_attendance_window(subject, "q2", [], [0, 6])
    assert w_i["window_start"] == date(2026, 8, 24)   # previous quiz date included
    assert w_i["window_end"] == date(2026, 9, 13)     # quiz day itself excluded
    assert w_ii["window_start"] == date(2026, 7, 15)  # commencement
    assert w_ii["window_end"] == date(2026, 9, 13)


# ===========================================================================
# Task 7 — optimizer divergence + consumer agreement (no second optimizer).
# ===========================================================================

def test_optimizer_must_attend_pooled_divergence():
    # L tot 10 att 2 pend 5; T 7/7 pend 0, target 75:
    # pooled needs (9 + a)/17 >= .75 -> a = 4 lectures; OLD mean needed 3.
    opt = optimize_attendance(10, 2, 3, 5, 7, 7, 0, 0, TARGET)
    assert (opt.lecture_deficit, opt.tutorial_deficit) == (4, 0)
    assert opt.is_reachable is True
    assert (opt.safe_skip_lecture, opt.safe_skip_tutorial) == (1, 0)
    # OLD reference: minimum 3 lectures, safe skip 2.
    assert (3, 2) != (opt.lecture_deficit, opt.safe_skip_lecture)


def test_optimizer_reachability_pooled_divergence_zero_pending():
    # Zero pending: reachable iff the CURRENT pooled attendance meets 75.
    # L 2/5, T 7/7 -> pooled 75 reachable; OLD mean 70 unreachable.
    opt = optimize_attendance(5, 2, 3, 0, 7, 7, 0, 0, TARGET)
    assert opt.is_reachable is True
    assert opt.lecture_deficit == 0 and opt.tutorial_deficit == 0


def test_optimizer_unreachable_reports_full_pending():
    opt = optimize_attendance(10, 2, 3, 5, 7, 1, 6, 0, TARGET)
    assert opt.is_reachable is False
    assert (opt.lecture_deficit, opt.tutorial_deficit) == (5, 0)
    assert (opt.safe_skip_lecture, opt.safe_skip_tutorial) == (0, 0)


def test_subject_summary_consumer_matches_canonical_optimizer():
    # The subject-summary consumer (used by /attendance/summary and the
    # dashboard) must expose EXACTLY the canonical engine output — the pooled
    # optimizer — with no second implementation in between.
    l, t = c(tot=10, att=2, miss=3, pending=5), c(tot=7, att=7)
    summary = _build_subject_summary("BCS-501", counts(l, t))
    canonical = optimize_attendance(
        l["tot"], l["att"], l["miss"], l["pending"],
        t["tot"], t["att"], t["miss"], t["pending"], TARGET,
    )
    assert summary.optimization == canonical
    assert summary.current_avg_pct == pytest.approx(pooled_pct(2, 10 - 5, 7, 7))
    # 75.0 pooled: HEALTHY floor is >= 75 (band hit exactly); legacy status
    # band: SAFE floor is 80, so 75 lands in WATCH.
    assert summary.health == "HEALTHY"
    assert summary.status == "WATCH"


def test_subject_summary_consumer_uses_pooled_status():
    # A subject whose pooled value crosses 75 while the OLD mean would not:
    # L 2/5, T 7/7 -> pooled 75 (SAFE band floor is 80, so WATCH; the old mean
    # 70 would also be WATCH — but the canonical VALUE equality is the point).
    summary = _build_subject_summary("BCS-501", counts(c(tot=5, att=2, miss=3), c(tot=7, att=7)))
    assert summary.current_avg_pct == pytest.approx(75.0)
    assert summary.optimization.is_reachable is True
