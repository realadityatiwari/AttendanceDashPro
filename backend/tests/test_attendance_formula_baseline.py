# Chunk 1 regression baseline: the CURRENT (pre-change) subject attendance
# mathematics, captured verbatim so the upcoming pooled-formula change
# FAILS LOUDLY here instead of silently changing behavior.
#
# Owner-approved post-change formula (Chunk 2+, NOT implemented in this chunk):
#
#     current% = (L_present + T_present) / (L_conducted + T_conducted) x 100
#
# CHUNK 2 UPDATE: the subject-CURRENT formula is now the owner-approved
# POOLED form (implemented in compute_subject_stats):
#
#     current% = (L_present + T_present) / (L_conducted + T_conducted) x 100
#
# so the subject-current tests below assert the POOLED values.
#
# CHUNK 3 UPDATE: the OPTIMIZER now uses the same owner-approved POOLED
# constraint, applied to the FINAL conducted totals (pending classes become
# attended or missed):
#
#     (L_attended + T_attended) / (L_total + T_total) x 100 >= target
#
# so the Task-3 optimizer tests below assert the POOLED must-attend /
# safe-skip / reachability behavior.
#
# CHUNK 4 UPDATE: the quiz-eligibility CURRENT criterion percentage (Criterion
# I and Criterion II) is now the same pooled count-level form:
#
#     (L attended + T attended) / (L total + T total) x 100
#
# so the Task-4 eligibility tests below assert POOLED criterion values and
# verdicts.
#
# CHUNK 5 UPDATE: the subject FORECAST and the eligibility BEST CASE
# (RECOVERABLE projection) are now pooled too — pending classes treated as
# attended, L+T aggregated at count level:
#
#     (L present + L pending + T present + T pending)
#     ------------------------------------------------ x 100
#     (L total + T total)
#
# so the Task-5 forecast tests and the best-case eligibility tests assert
# POOLED values. NO mean-of-percentages arithmetic remains in the live path
# (the legacy helper is kept only as a documented historical reference).
#
# Conventions captured here (confirmed against production code):
#   - Conducted ("done") = attended + missed. Pending is NEVER in the current
#     denominator; pending IS in the eligibility window denominator and is
#     treated as attended in forecast / best-case.
#   - Cancelled sessions are excluded upstream by
#     practical_occurrence.collapse_count_rows before counts reach the engine;
#     cancellation therefore never becomes absence.
#   - Practical (P) counts are carried on the summary but NEVER enter L+T math.
#
# Markers:
#   [MUST FAIL AFTER CHANGE] — pins the OLD formula value/verdict on purpose.
#   [INVARIANT]              — must hold before AND after the change.
#   [VALUE-INVARIANT]        — same expected number before and after, but the
#                              implementation path differs (documented for Chunk 2).
#   [CHUNK 3: POOLED]        — optimizer expectation updated to the pooled
#                              constraint; the OLD value/verdict stays in the
#                              docstring so the divergence remains visible.

from datetime import date

import pytest

from app.engines.attendance_engine import (
    ATTENDANCE_TARGET_PCT,
    compute_subject_stats,
    normalize_class_type,
    meets_attendance_target,
    optimize_attendance,
)
from app.engines.eligibility_engine import (
    _combined_pct,
    _evaluate_criterion,
    _pct,
    _pooled_pct,
    determine_quiz_threshold,
    evaluate_quiz_eligibility,
)
from app.schemas.attendance import EligibilityState
from app.engines.calendar_engine import (
    DEFAULT_WEEKENDS,
    get_attendance_window,
    get_cumulative_attendance_window,
)
from app.schemas.academic import Milestone, Subject, SubjectCategory, Timeline

# NOTE: eligibility_engine._best_avg is a nested function inside
# evaluate_quiz_eligibility; its best-case semantics are pinned end-to-end via
# the RECOVERABLE tests below (test_eligibility_recoverable_*, the mandatory
# best-case cases and the hybrid regression flip).
# CHUNK 5: the best case is now the POOLED count-level form — pending treated
# as attended — exactly the quantity the Chunk 3 optimizer tests for
# reachability.


def _counts(tot=0, att=0, miss=0, pending=0):
    return {"tot": tot, "att": att, "miss": miss, "pending": pending}


# ---------------------------------------------------------------------------
# Task 2 — subject current attendance (attendance_engine.compute_subject_stats)
# ---------------------------------------------------------------------------


def test_subject_no_conducted_classes_current_pct_is_none():
    """Case F: nothing conducted (only pending).

    Current behavior: all current_*_pct are None — pending never invents a
    current percentage. [INVARIANT — holds under both formulas.]
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(tot=3, att=0, miss=0, pending=3),
            "T": _counts(tot=2, att=0, miss=0, pending=2),
        }},
    )
    assert summary.current_lecture_pct is None
    assert summary.current_tutorial_pct is None
    assert summary.current_avg_pct is None


def test_subject_unequal_counts_pooled_l_t_formula():
    """Chunk 2 spec case 2: unequal denominators — THE divergence case.

    L 2/5 conducted, T 7/7 conducted.
    OLD mean-of-% was 70.0; POOLED (count-level) = (2+7)/(5+7)*100 = 75.0.
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(tot=5, att=2, miss=3),
            "T": _counts(tot=7, att=7, miss=0),
        }},
    )
    assert summary.current_lecture_pct == pytest.approx(40.0)
    assert summary.current_tutorial_pct == pytest.approx(100.0)
    assert summary.current_avg_pct == pytest.approx(75.0)  # pooled (2+7)/(5+7)


def test_subject_unequal_counts_pooled_opposite_direction():
    """Chunk 2 spec case 3: opposite divergence direction.

    L 1/2, T 4/10: pooled = (1+4)/(2+10)*100 = 5/12*100 = 41.666...
    (OLD mean-of-% was 45.0.)
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(tot=2, att=1, miss=1),
            "T": _counts(tot=10, att=4, miss=6),
        }},
    )
    assert summary.current_avg_pct == pytest.approx(5 / 12 * 100.0)  # pooled


def test_subject_equal_counts_pooled_matches_mean():
    """Chunk 2 spec case 1: equal conducted counts — pooled == old mean here.

    L 4/5, T 4/5: pooled (4+4)/(5+5)*100 = 80.0 (old mean also 80.0).
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(tot=5, att=4, miss=1),
            "T": _counts(tot=5, att=4, miss=1),
        }},
    )
    assert summary.current_avg_pct == pytest.approx(80.0)


def test_subject_lecture_only_collapses_to_lecture_pct():
    """Case D: lecture-only (no tutorials at all).

    L 8 att / 2 miss => current_avg_pct == current_lecture_pct == 80.0.
    [INVARIANT — the collapse is identical under both formulas.]
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(tot=10, att=8, miss=2),
            "T": _counts(),
        }},
    )
    assert summary.current_lecture_pct == pytest.approx(80.0)
    assert summary.current_tutorial_pct is None
    assert summary.current_avg_pct == pytest.approx(80.0)


def test_subject_tutorial_only_summary_uses_tutorial_pct():
    """Case E: tutorial-only (L 0/0, T 6 att / 2 miss => 6/8 = 75%).

    Chunk 2 spec case 5: tutorial-only subjects now produce a pooled value.

    OLD behavior (pre-Chunk 2): current_avg_pct was None (the combined value
    was only computed inside the lecture-pct branch). Owner-approved pooled
    semantics: (0 + 6) / (0 + 8) * 100 = 75.0 — no artificial zeroes, the
    absent lecture type simply contributes nothing.
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(),
            "T": _counts(tot=8, att=6, miss=2),
        }},
    )
    assert summary.current_lecture_pct is None
    assert summary.current_tutorial_pct == pytest.approx(75.0)
    assert summary.current_avg_pct == pytest.approx(75.0)  # pooled (0+6)/(0+8)


def test_subject_pending_excluded_from_current_denominator():
    """Case G: pending classes are excluded from CURRENT attendance.

    L 8 att / 2 miss / 5 pending, T 5 att / 1 miss / 2 pending:
    conducted L = 10 (80%), conducted T = 6 (83.333%).
    POOLED current = (8+5)/(10+6)*100 = 13/16*100 = 81.25 — pending adds
    NOTHING to the current denominator (forecast, which includes pending, is
    covered by the forecast tests below and still pins OLD semantics).
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(tot=15, att=8, miss=2, pending=5),
            "T": _counts(tot=8, att=5, miss=1, pending=2),
        }},
    )
    assert summary.lecture.total == 15
    assert summary.lecture.pending == 5
    assert summary.current_lecture_pct == pytest.approx(80.0)
    assert summary.current_tutorial_pct == pytest.approx(5 / 6 * 100.0)
    assert summary.current_avg_pct == pytest.approx(13 / 16 * 100.0)  # pooled


def test_subject_missed_classes_count_in_denominator():
    """Case H: missed classes are conducted and count in the denominator.

    L 7 att / 3 miss => 70.0 lecture %.
    [INVARIANT — denominator convention identical under both formulas.]
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(tot=10, att=7, miss=3),
            "T": _counts(),
        }},
    )
    assert summary.current_lecture_pct == pytest.approx(70.0)
    assert summary.current_avg_pct == pytest.approx(70.0)


def test_cancelled_never_becomes_absence_at_engine_level():
    """Case I: cancelled occurrences never reach the engine as absences.

    collapse_count_rows (the canonical read-model gate, exercised in
    test_practical_occurrence_safety.py) drops cancelled occurrences
    entirely, so the engine only ever sees att/miss/pending of REAL conducted
    classes. This pins the engine-side contract: with 5 conducted lectures
    (4 attended, 1 missed) and 1 cancelled lecture already dropped upstream,
    the percentage is 4/5 = 80% — NOT 4/6 = 66.7% (cancelled-as-absent).
    [INVARIANT]
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(tot=5, att=4, miss=1),
            "T": _counts(),
        }},
    )
    assert summary.current_lecture_pct == pytest.approx(80.0)
    assert summary.current_avg_pct == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# Task 2/7 — practical/lab isolation
# ---------------------------------------------------------------------------


def test_practical_counts_carried_but_excluded_from_l_t_math():
    """Task 7: P counts exist on the summary but never enter L+T math.

    A terrible practical % must not move current_avg_pct, and
    normalize_class_type must keep merging P1/P2/extra variants into P.
    [INVARIANT — required by spec item 6; must hold after the change too.]
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(tot=10, att=8, miss=2),
            "T": _counts(),
            "P": _counts(tot=6, att=1, miss=5),  # deliberately bad lab %
        }},
    )
    assert summary.practical.total == 6
    assert summary.current_avg_pct == pytest.approx(80.0)  # L-only; P ignored


def test_normalize_class_type_buckets():
    """P1/P2/extras normalize into P; extras keep L/T. [INVARIANT]"""
    assert normalize_class_type("P1") == "P"
    assert normalize_class_type("P2") == "P"
    assert normalize_class_type("P1_extra_E1") == "P"
    assert normalize_class_type("P_extra_E2") == "P"
    assert normalize_class_type("L_extra_E1") == "L"
    assert normalize_class_type("T_extra_E2") == "T"
    assert normalize_class_type("L") == "L"
    assert normalize_class_type("T") == "T"


# ---------------------------------------------------------------------------
# Task 5 — subject forecast (attendance_engine.compute_subject_stats)
#
# CHUNK 5: the combined forecast is the pooled count-level form — pending
# classes are treated as attended:
#
#     (L_att + L_pending + T_att + T_pending) / (L_total + T_total) x 100
#
# [OLD] the mean of forecast_lecture_pct and forecast_tutorial_pct. The
# per-type forecast percentages themselves are unchanged.
# ---------------------------------------------------------------------------


def test_forecast_case_1_no_pending_pooled():
    """MANDATORY FORECAST TEST 1: L 4/5 att, T 5/10 att, NO pending.

    forecast L = 80.0 and forecast T = 50.0 (per-type unchanged).
    OLD forecast_avg = (80 + 50)/2 = 65.0.
    NEW pooled = (4 + 5)/(5 + 10)*100 = 9/15 = 60.0.
    [CHUNK 5: POOLED]
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(tot=5, att=4, miss=1),
            "T": _counts(tot=10, att=5, miss=5),
        }},
    )
    assert summary.forecast_lecture_pct == pytest.approx(80.0)    # unchanged
    assert summary.forecast_tutorial_pct == pytest.approx(50.0)   # unchanged
    assert summary.forecast_avg_pct == pytest.approx(60.0)        # pooled; OLD 65.0


def test_forecast_case_2_pending_treated_as_attended_pooled():
    """MANDATORY FORECAST TEST 2: pending treated as attended, pooled combo.

    L: 4 att / 1 pending / 5 total           -> forecast L = 5/5*100  = 100.0
    T: 5 att / 3 miss / 2 pending / 10 total -> forecast T = 7/10     = 70.0
    OLD forecast_avg = (100 + 70)/2 = 85.0.
    NEW pooled = (4+1 + 5+2)/(5 + 10)*100 = 12/15 = 80.0.
    [CHUNK 5: POOLED]
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(tot=5, att=4, miss=0, pending=1),
            "T": _counts(tot=10, att=5, miss=3, pending=2),
        }},
    )
    assert summary.forecast_lecture_pct == pytest.approx(100.0)
    assert summary.forecast_tutorial_pct == pytest.approx(70.0)
    assert summary.forecast_avg_pct == pytest.approx(80.0)  # pooled; OLD 85.0


def test_forecast_pooled_with_misses_and_pending():
    """Previous baseline case (misses + pending), now asserted pooled.

    L: 4 att / 1 miss / 1 pending of 6  -> forecast L = 5/6*100 = 83.333
    T: 5 att / 3 miss / 2 pending of 10 -> forecast T = 7/10    = 70.0
    OLD forecast_avg = (83.333... + 70)/2 = 76.666...
    NEW pooled = (5 + 7)/(6 + 10)*100 = 12/16 = 75.0.
    [CHUNK 5: POOLED] — misses never enter the forecast numerator; only the
    totals and (att + pending) do.
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(tot=6, att=4, miss=1, pending=1),
            "T": _counts(tot=10, att=5, miss=3, pending=2),
        }},
    )
    assert summary.forecast_lecture_pct == pytest.approx(5 / 6 * 100.0)
    assert summary.forecast_tutorial_pct == pytest.approx(70.0)
    assert summary.forecast_avg_pct == pytest.approx(75.0)  # pooled; OLD 76.6667


def test_forecast_lecture_only_collapses():
    """Lecture-only forecast collapse: pooled = the lecture forecast %.

    L: 4 att + 4 pending / 10 total -> 80.0; the missing tutorial bucket adds
    nothing to either side of the pooled fraction. [INVARIANT — the OLD
    collapse also produced 80.0.]
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(tot=10, att=4, miss=2, pending=4),
            "T": _counts(),
        }},
    )
    assert summary.forecast_lecture_pct == pytest.approx(80.0)
    assert summary.forecast_tutorial_pct is None
    assert summary.forecast_avg_pct == pytest.approx(80.0)


def test_forecast_case_3_tutorial_only_pooled_and_p_never_enters():
    """MANDATORY FORECAST TEST 3: tutorial-only forecast — L 0/0, T 6+2/8.

    Pooled = (0 + 6+2)/(0 + 8)*100 = 8/8 = 100.0 — NO artificial lecture zero
    (the OLD combined path returned None for a missing L percentage).
    A practical (P) bucket is present and must never enter the L+T forecast.
    [CHUNK 5: POOLED]
    """
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(),
            "T": _counts(tot=8, att=6, miss=0, pending=2),
            "P": _counts(tot=6, att=1, miss=4, pending=1),
        }},
    )
    assert summary.forecast_lecture_pct is None
    assert summary.forecast_tutorial_pct == pytest.approx(100.0)
    assert summary.forecast_avg_pct == pytest.approx(100.0)  # pooled; OLD None
    assert summary.practical.total == 6  # carried, never merged into L+T math


def test_forecast_none_when_no_classes():
    """No classes at all => forecast None. [INVARIANT]"""
    summary = compute_subject_stats("X", {"counts": {"L": _counts(), "T": _counts()}})
    assert summary.forecast_lecture_pct is None
    assert summary.forecast_avg_pct is None


def test_forecast_case_4_zero_denominator_is_none_even_with_practicals():
    """MANDATORY FORECAST TEST 4: zero L+T denominator => combined forecast
    stays None (established null semantics) even when practical counts exist —
    practicals never create an L+T denominator."""
    summary = compute_subject_stats(
        "X",
        {"counts": {
            "L": _counts(),
            "T": _counts(),
            "P": _counts(tot=6, att=2, miss=1, pending=3),
        }},
    )
    assert summary.forecast_lecture_pct is None
    assert summary.forecast_tutorial_pct is None
    assert summary.forecast_avg_pct is None


# ---------------------------------------------------------------------------
# Task 3 — optimizer regression cases (optimize_attendance / meets target)
#
# CHUNK 3: the constraint is the POOLED L+T predicate, evaluated on the FINAL
# conducted totals (pending classes become attended or missed):
#
#     (L_attended + T_attended) / (L_total + T_total) x 100 >= target
#
# [OLD] arithmetic mean of the lecture % and the tutorial % — kept in the
# docstrings as the OLD marker so the divergence stays visible.
# ---------------------------------------------------------------------------


def _old_mean_optimizer(*, tot_l, att_l, pending_l, tot_t, att_t, pending_t, target_pct):
    """REFERENCE-ONLY implementation of the OLD (pre-Chunk-3) optimizer
    predicate: the arithmetic mean of the two per-type percentages, with the
    same zero-pending early return, unreachable report and (total, lectures)
    tie-break as the old production code. It exists purely so the divergence
    test below can prove the pooled optimizer no longer matches it — it is
    NOT production code and is never imported by the application."""
    def old_meets(lec_pct, tut_pct):
        if tut_pct is None:
            return lec_pct >= target_pct
        return ((lec_pct + tut_pct) / 2.0) >= target_pct

    if pending_l == 0 and pending_t == 0:
        lec_pct = (att_l / tot_l * 100.0) if tot_l > 0 else 0.0
        tut_pct = (att_t / tot_t * 100.0) if tot_t > 0 else None
        return old_meets(lec_pct, tut_pct), 0, 0

    valid = []
    for l in range(pending_l + 1):
        for t in range(pending_t + 1):
            lec_pct = ((att_l + l) / tot_l * 100.0) if tot_l > 0 else 0.0
            tut_pct = ((att_t + t) / tot_t * 100.0) if tot_t > 0 else None
            if old_meets(lec_pct, tut_pct):
                valid.append((l + t, l, t))
    if not valid:
        return False, pending_l, pending_t
    valid.sort()
    return True, valid[0][1], valid[0][2]


def test_optimizer_pooled_diverges_from_old_mean_reference():
    """CHUNK 3 divergence proof: same inputs and the same tie-break, but the
    pooled optimizer returns different must-attend / reachability answers
    than the OLD mean-of-% optimizer."""
    # Case 2/E: OLD minimum 3 lectures; pooled requires 4.
    old = _old_mean_optimizer(
        tot_l=10, att_l=2, pending_l=5, tot_t=7, att_t=7, pending_t=0,
        target_pct=75.0,
    )
    new = optimize_attendance(
        tot_l=10, att_l=2, miss_l=3, pending_l=5,
        tot_t=7, att_t=7, miss_t=0, pending_t=0,
        target_pct=75.0,
    )
    assert old == (True, 3, 0)                                    # OLD min: 3 L
    assert (new.is_reachable, new.lecture_deficit,
            new.tutorial_deficit) == (True, 4, 0)                 # pooled: 4 L

    # Case 3: OLD reachable (best case 85 >= 80); pooled unreachable (75 < 80).
    old2 = _old_mean_optimizer(
        tot_l=4, att_l=0, pending_l=4, tot_t=20, att_t=12, pending_t=2,
        target_pct=80.0,
    )
    new2 = optimize_attendance(
        tot_l=4, att_l=0, miss_l=0, pending_l=4,
        tot_t=20, att_t=12, miss_t=6, pending_t=2,
        target_pct=80.0,
    )
    assert old2[0] is True
    assert new2.is_reachable is False

    # All-pending boundary: OLD (2L, 1T) leaves 1 tutorial skippable; pooled
    # needs every pending class (2L, 2T) to reach exactly 12/16 = 75.
    old3 = _old_mean_optimizer(
        tot_l=6, att_l=4, pending_l=2, tot_t=10, att_t=4, pending_t=2,
        target_pct=75.0,
    )
    new3 = optimize_attendance(
        tot_l=6, att_l=4, miss_l=0, pending_l=2,
        tot_t=10, att_t=4, miss_t=4, pending_t=2,
        target_pct=75.0,
    )
    assert old3 == (True, 2, 1)
    assert (new3.is_reachable, new3.lecture_deficit,
            new3.tutorial_deficit) == (True, 2, 2)
    assert new3.safe_skip_tutorial == 0                           # OLD skipped 1


def test_optimizer_equal_denominators_current_already_passes():
    """Case 1: equal L/T denominators, current avg already >= target.

    L 4/5 att (1 pending), T 4/5 att (1 pending), target 75:
    OLD mean-of-% = 80; POOLED (4+4)/(5+5) = 80 — identical because the
    denominators are equal. Attending ZERO classes is optimal and both
    pending classes are safe to skip. [INVARIANT]
    """
    result = optimize_attendance(
        tot_l=5, att_l=4, miss_l=0, pending_l=1,
        tot_t=5, att_t=4, miss_t=0, pending_t=1,
        target_pct=75.0,
    )
    assert result.is_reachable is True
    assert result.lecture_deficit == 0
    assert result.tutorial_deficit == 0
    assert result.safe_skip_lecture == 1
    assert result.safe_skip_tutorial == 1


def test_optimizer_unequal_denominators_pooled_minimum_attendance():
    """Case 2 / Case E: unequal denominators — the pooled minimum differs
    from the OLD mean-of-% minimum (must-attend count changes).

    L 2/10 att (3 missed, 5 pending), T 7/7 att, target 75.
    Final pooled denominator = 10 + 7 = 17.
      OLD: attend 3 L -> (50 + 100)/2 = 75 >= 75 -> minimum 3.
      NEW: (2 + 7 + l)/17 >= 0.75 -> 9 + l >= 12.75 -> l >= 4, i.e.
           (2+4+7)/17 = 13/17 = 76.47 >= 75; 3 L gives 12/17 = 70.59 FAIL.
    Case E (constructed divergence): the same scenario needs 3 classes under
    the OLD mean formula and 4 under the pooled formula — the pooled answer
    is verified explicitly below. [CHUNK 3: POOLED]
    """
    result = optimize_attendance(
        tot_l=10, att_l=2, miss_l=3, pending_l=5,
        tot_t=7, att_t=7, miss_t=0, pending_t=0,
        target_pct=75.0,
    )
    assert result.is_reachable is True
    assert result.lecture_deficit == 4       # pooled; OLD was 3
    assert result.tutorial_deficit == 0
    assert result.safe_skip_lecture == 1     # 5 pending - 4 attended; OLD was 2
    assert result.safe_skip_tutorial == 0


def test_optimizer_old_formula_reaches_target_pooled_does_not():
    """Case 3: OLD says REACHABLE, pooled says NOT reachable.

    L 0/4 att (4 pending), T 12/20 att (6 missed, 2 pending), target 80.
    OLD best case: attend all -> (100 + 70)/2 = 85 >= 80 -> REACHABLE, with
      qualifying minimum 4 L (t=0): (100+60)/2 = 80 >= 80.
    NEW pooled best case (edge case 10 — all pending attended):
      (0+4+12+2)/(4+20) = 18/24 = 75 < 80 -> NOT reachable. The unreachable
      report is unchanged (full pending as deficits, zero safe skips).
    [CHUNK 3: POOLED] — is_reachable flips to False.
    """
    result = optimize_attendance(
        tot_l=4, att_l=0, miss_l=0, pending_l=4,
        tot_t=20, att_t=12, miss_t=6, pending_t=2,
        target_pct=80.0,
    )
    assert result.is_reachable is False         # pooled; OLD was True
    assert result.lecture_deficit == 4          # full pending (unreachable report)
    assert result.tutorial_deficit == 2
    assert result.safe_skip_lecture == 0
    assert result.safe_skip_tutorial == 0


def test_optimizer_pooled_reaches_target_old_does_not():
    """Case 4: pooled PASSES where the OLD mean-of-% FAILS (zero pending).

    L 2/5 att (3 missed), T 7/7 att, target 75:
      OLD avg = (40 + 100)/2 = 70 < 75             -> FAIL
      NEW     = (2 + 7)/(5 + 7) = 9/12 = 75 >= 75  -> PASS
    [CHUNK 3: POOLED] — the predicate flips to True and the zero-pending
    reachability flips with it.
    """
    assert meets_attendance_target(2, 5, 7, 7, 75.0) is True  # pooled predicate
    # Zero-pending path of the same counts:
    result = optimize_attendance(
        tot_l=5, att_l=2, miss_l=3, pending_l=0,
        tot_t=7, att_t=7, miss_t=0, pending_t=0,
        target_pct=75.0,
    )
    assert result.is_reachable is True   # pooled; OLD was False
    assert result.lecture_deficit == 0
    assert result.tutorial_deficit == 0
    assert result.safe_skip_lecture == 0
    assert result.safe_skip_tutorial == 0


def test_optimizer_zero_pending_below_target_is_unreachable():
    """Edge case 6: zero pending — reachable iff the CURRENT pooled
    attendance already meets the target.

    Case C counts: L 6/10 (60%), T 2/3 (66.667%), target 75.
    Pooled = (6 + 2)/(10 + 3) = 8/13 = 61.5384... < 75 -> NOT reachable with
    nothing left to attend. Full precision — no rounding before comparison.
    (The spec sheet's illustrative Case C figures — old 76.6667 / pooled 64 —
    do not reproduce from these counts; the exact OLD mean is
    (60 + 66.6667)/2 = 63.3333. The required FAIL verdict is unchanged.)
    [CHUNK 3: POOLED]
    """
    result = optimize_attendance(
        tot_l=10, att_l=6, miss_l=4, pending_l=0,
        tot_t=3, att_t=2, miss_t=1, pending_t=0,
        target_pct=75.0,
    )
    assert meets_attendance_target(6, 10, 2, 3, 75.0) is False  # full precision
    assert result.is_reachable is False
    assert result.lecture_deficit == 0
    assert result.tutorial_deficit == 0
    assert result.safe_skip_lecture == 0
    assert result.safe_skip_tutorial == 0


def test_optimizer_zero_pending_reachable_when_current_meets_target():
    """Edge case 5: zero pending, current pooled passes => reachable.

    L 6/10 (60%), T 9/9 (100%): OLD mean 80; pooled (6+9)/(10+9) = 15/19 =
    78.947... >= 75 — same verdict, different value. [INVARIANT]
    """
    result = optimize_attendance(
        tot_l=10, att_l=6, miss_l=4, pending_l=0,
        tot_t=9, att_t=9, miss_t=0, pending_t=0,
        target_pct=75.0,
    )
    assert result.is_reachable is True
    assert result.lecture_deficit == 0
    assert result.tutorial_deficit == 0


def test_optimizer_pending_on_both_types_minimum_total():
    """Edge case 9: pending on both types — minimum total attendance wins.

    L 1/9 att (8 pending), T 1/3 att (1 missed, 1 pending), target 70.
    (miss_t = 1 keeps the canonical invariant tot = att + miss + pending; the
    optimizer predicate never reads miss_*.)
    POOLED denominator 9 + 3 = 12; need (1 + 1 + l + t)/12 >= 0.70 ->
    l + t >= 7. The total-7 tie ((6L,1T) vs (7L,0T)) is broken by the
    preserved rule (fewest lectures attended) -> 6 L + 1 T, i.e. 2 safe
    lecture skips.
    The OLD mean enumeration independently lands on the same minimum (t = 0
    can never pass; t = 1 forces lec >= 73.33 -> 6 L) and the same tie
    outcome, so the expectations are unchanged — this is edge case 2
    (unequal denominators where both formulas agree). [INVARIANT]
    """
    result = optimize_attendance(
        tot_l=9, att_l=1, miss_l=0, pending_l=8,
        tot_t=3, att_t=1, miss_t=1, pending_t=1,
        target_pct=70.0,
    )
    assert result.is_reachable is True
    assert result.lecture_deficit == 6
    assert result.tutorial_deficit == 1
    assert result.safe_skip_lecture == 2
    assert result.safe_skip_tutorial == 0


def test_optimizer_unreachable_when_window_closed_below_target():
    """Edge case 6 (contrast): reachability — closed window below target.

    L 0/6 conducted (all missed), T 0/2 conducted (all missed), 0 pending,
    target 75: pooled 0/8 = 0 < 75 and nothing left to attend => unreachable.
    [INVARIANT — same verdict under both formulas.]
    """
    result = optimize_attendance(
        tot_l=6, att_l=0, miss_l=6, pending_l=0,
        tot_t=2, att_t=0, miss_t=2, pending_t=0,
        target_pct=75.0,
    )
    assert result.is_reachable is False
    assert result.lecture_deficit == 0
    assert result.tutorial_deficit == 0


def test_optimizer_safe_skip_tie_prefers_fewer_lectures():
    """Edge cases 1/11: safe-skip tie-break — min total, then MIN lectures.

    L 2/4 att (1 pending), T 2/4 att (1 pending), target 60.
    Pooled denominator 4 + 4 = 8; both single-attendance combos pass
    symmetrically:
      (1L, 0T): (2+1+2+0)/8 = 62.5 >= 60
      (0L, 1T): (2+0+2+1)/8 = 62.5 >= 60
    (Equal denominators => POOLED == OLD mean here: 62.5 for both combos.)
    Tie at total=1 -> sort key (total, l_attend) prefers l_attend=0, so the
    TUTORIAL is the must-attend and the LECTURE is safe to skip.
    [INVARIANT — tie-breaking preserved.]
    """
    result = optimize_attendance(
        tot_l=4, att_l=2, miss_l=1, pending_l=1,
        tot_t=4, att_t=2, miss_t=1, pending_t=1,
        target_pct=60.0,
    )
    assert result.is_reachable is True
    assert result.lecture_deficit == 0
    assert result.tutorial_deficit == 1
    assert result.safe_skip_lecture == 1
    assert result.safe_skip_tutorial == 0


def test_optimizer_lecture_only_unreachable_best_case():
    """Edge case 7: lecture-only (no tutorials), best case below target.

    L 2/10 att (3 missed, 5 pending), T 0/0, target 75: the pooled form
    collapses to the lecture percentage; attending ALL 5 pending gives
    7/10 = 70 < 75 => unreachable, deficits report the full pending.
    [INVARIANT — the missing type adds nothing to either side.]
    """
    result = optimize_attendance(
        tot_l=10, att_l=2, miss_l=3, pending_l=5,
        tot_t=0, att_t=0, miss_t=0, pending_t=0,
        target_pct=75.0,
    )
    assert result.is_reachable is False
    assert result.lecture_deficit == 5
    assert result.tutorial_deficit == 0
    assert result.safe_skip_lecture == 0


def test_optimizer_pending_tutorial_only_pooled_minimum():
    """Edge case 8: pending tutorials only — the pooled minimum differs from
    the OLD mean minimum.

    L 2/5 att (3 missed, 0 pending), T 1/4 att (1 missed, 2 pending),
    target 45.
    Final pooled denominator 5 + 4 = 9; current attended total 3.
      OLD: lec 40%, tut (1+t)/4*100 -> mean >= 45 at t = 1
           ((40 + 50)/2 = 45 >= 45).
      NEW: (3 + t)/9 >= 0.45 -> 3 + t >= 4.05 -> t = 2
           ((3+2)/9 = 55.56 >= 45; t = 1 gives 4/9 = 44.44 FAIL).
    [CHUNK 3: POOLED]
    """
    result = optimize_attendance(
        tot_l=5, att_l=2, miss_l=3, pending_l=0,
        tot_t=4, att_t=1, miss_t=1, pending_t=2,
        target_pct=45.0,
    )
    assert result.is_reachable is True
    assert result.lecture_deficit == 0
    assert result.tutorial_deficit == 2        # pooled; OLD was 1
    assert result.safe_skip_lecture == 0
    assert result.safe_skip_tutorial == 0


def test_optimizer_all_pending_attended_pooled_minimum():
    """Edge case 10: all pending attended — boundary reachability and a
    pooled minimum that differs from the OLD mean minimum.

    L 4/6 att (2 pending), T 4/10 att (4 missed, 2 pending), target 75.
    Best case (all pending attended) pooled = (4+2+4+2)/(6+10) = 12/16 = 75
    >= 75 -> REACHABLE — and it is the only combination that gets there
    (pending totals 4, so l + t = 4 is the maximum).
      OLD minimum: 3 total, (2L, 1T) -> (100 + 50)/2 = 75, leaving 1
      tutorial safe to skip.
      NEW minimum: 4 total, (2L, 2T) -> (4+2+4+2)/16 = 75 — no safe skips.
    [CHUNK 3: POOLED] — different must-attend / safe-skip answer.
    """
    result = optimize_attendance(
        tot_l=6, att_l=4, miss_l=0, pending_l=2,
        tot_t=10, att_t=4, miss_t=4, pending_t=2,
        target_pct=75.0,
    )
    assert result.is_reachable is True
    assert result.lecture_deficit == 2         # pooled: 2L + 2T; OLD was 2L + 1T
    assert result.tutorial_deficit == 2        # pooled; OLD was 1
    assert result.safe_skip_lecture == 0
    assert result.safe_skip_tutorial == 0      # OLD left 1 tutorial skippable


def test_meets_attendance_target_pooled_predicate():
    """meets_attendance_target is now the count-level POOLED predicate.

    Signature (CHUNK 3): meets_attendance_target(att_l, tot_l, att_t, tot_t,
    target) — pooling needs the raw counts, so the OLD
    (lec_pct, tut_pct, target) percentage signature is gone.

    [OLD] ((lec_pct + tut_pct) / 2.0) >= target, with a lecture-only
    collapse when tut_pct was None.
    """
    # Lecture-only window collapses to the lecture percentage (a missing type
    # adds zero to both sides of the pooled fraction). [INVARIANT]
    assert meets_attendance_target(80, 100, 0, 0, 75.0) is True
    assert meets_attendance_target(74, 100, 0, 0, 75.0) is False
    # Tutorial-only window is symmetric — no special-casing needed (the OLD
    # mean branch would have averaged the tutorial % against 0.0).
    assert meets_attendance_target(0, 0, 6, 8, 75.0) is True
    # Equal denominators: pooled == OLD mean (7/10 = 70). [INVARIANT]
    assert meets_attendance_target(3, 5, 4, 5, 70.0) is True
    assert meets_attendance_target(3, 5, 4, 5, 70.0001) is False  # full precision
    # Case A: L 2/5, T 7/7, target 75 -> pooled 9/12 = 75 >= 75 PASS
    # (OLD mean 70 FAILs).
    assert meets_attendance_target(2, 5, 7, 7, 75.0) is True
    # Case B: L 1/2, T 4/10, target 50 -> pooled 5/12 = 41.6667 < 50 FAIL
    # (OLD mean 45 also FAILs).
    assert meets_attendance_target(1, 2, 4, 10, 50.0) is False
    # Case C: L 6/10, T 2/3, target 75 -> pooled 8/13 = 61.5384 < 75 FAIL.
    assert meets_attendance_target(6, 10, 2, 3, 75.0) is False
    # OLD-PASS / pooled-FAIL anchor with unequal denominators (the worse
    # percentage sits on the LARGER denominator): L 2/10 (20%), T 7/7 (100%)
    # -> OLD mean 60 >= 55 PASS; pooled 9/17 = 52.94 < 55 FAIL.
    assert meets_attendance_target(2, 10, 7, 7, 55.0) is False
    # No classes in the window: no percentage can meet a positive target.
    assert meets_attendance_target(0, 0, 0, 0, 75.0) is False


def test_subject_optimization_target_is_75():
    """The subject-level optimizer target stays the frozen 75 (consumed by
    attendance_service.SUBJECT_OPTIMIZATION_TARGET_PCT). [INVARIANT]"""
    assert ATTENDANCE_TARGET_PCT == 75.0


# ---------------------------------------------------------------------------
# Task 4 — quiz eligibility criteria (eligibility_engine._evaluate_criterion)
#
# CHUNK 4: the CURRENT criterion percentage is the pooled count-level form
# (L att + T att) / (L total + T total) x 100 on that criterion's window
# counts — pending included in the totals, exactly as _build_counts produces
# them. [OLD] arithmetic mean of the lecture % and the tutorial %.
# ---------------------------------------------------------------------------


def _eval_criterion(counts, required):
    """Minimal harness for the private _evaluate_criterion (window dict is
    display-only input)."""
    return _evaluate_criterion(
        name="Criterion (test)",
        window={"window_start": date(2026, 7, 15), "window_end": date(2026, 9, 1)},
        counts=counts,
        required=required,
    )


def test_criterion_equal_denominators_passes_under_both_formulas():
    """MANDATORY TEST 5 / invariance: equal counts — L 4/5, T 4/5.

    Pooled = (4 + 4)/(5 + 5) = 8/10 = 80.0 and the OLD mean is also 80.0 —
    equal denominators make the two formulas coincide. Required 70 => PASS.
    [INVARIANT]
    """
    result = _eval_criterion(
        {"L": _counts(tot=5, att=4, miss=1), "T": _counts(tot=5, att=4, miss=1)},
        70.0,
    )
    assert result.value == pytest.approx(80.0)
    assert result.passed is True


def test_criterion_unequal_denominators_pooled_value_pass():
    """Unequal denominators, required 70: the pooled VALUE replaces the mean.

    L 2/5, T 7/7: OLD mean = (40 + 100)/2 = 70.0;
    POOLED = (2 + 7)/(5 + 7) = 9/12 = 75.0.
    Both verdicts PASS at 70 — same verdict, different value.
    [CHUNK 4: POOLED]
    """
    result = _eval_criterion(
        {"L": _counts(tot=5, att=2, miss=3), "T": _counts(tot=7, att=7, miss=0)},
        70.0,
    )
    assert result.value == pytest.approx(75.0)  # pooled; OLD formula value 70.0
    assert result.passed is True


def test_criterion_case_a_pooled_boundary_pass_old_verdict_fail():
    """MANDATORY TEST 1 (Case A): L 2/5, T 7/7, threshold 75.

    OLD mean = (40 + 100)/2 = 70.0 < 75 -> FAIL.
    NEW pooled = (2 + 7)/(5 + 7) = 9/12 = 75.0 >= 75 -> PASS (exact boundary;
    full precision — no rounding before the comparison).
    [CHUNK 4: POOLED] — the criterion-verdict flip.
    """
    result = _eval_criterion(
        {"L": _counts(tot=5, att=2, miss=3), "T": _counts(tot=7, att=7, miss=0)},
        75.0,
    )
    assert result.value == pytest.approx(75.0)  # pooled; OLD value was 70.0
    assert result.passed is True                # pooled; OLD verdict was FAIL


def test_criterion_no_tutorials_collapses_to_lecture_pct():
    """No tutorials in window: value == lecture %, optimizer present.
    [INVARIANT]"""
    result = _eval_criterion(
        {"L": _counts(tot=10, att=8, miss=2), "T": _counts()},
        70.0,
    )
    assert result.value == pytest.approx(80.0)
    assert result.passed is True
    assert result.optimization is not None


def test_criterion_tutorial_only_pooled_value_pass():
    """MANDATORY TEST 4: tutorial-only window — L 0/0, T 6/8.

    NEW pooled = (0 + 6)/(0 + 8) = 75.0 >= 70 -> PASS.
    The missing lecture bucket contributes NO denominator and NO numerator —
    explicitly NOT (0 + 75)/2 = 37.5.
    OLD behavior: _combined_pct(None, 75.0) returned None -> always FAIL,
    even though the summary-side tutorial-only subject showed 75%.
    [CHUNK 4: POOLED]
    """
    result = _eval_criterion(
        {"L": _counts(), "T": _counts(tot=8, att=6, miss=2)},
        70.0,
    )
    assert result.value == pytest.approx(75.0)  # pooled; OLD was None
    assert result.passed is True                # pooled; OLD was False
    assert result.optimization is not None
    # Exact boundary at the threshold: 75.0 >= 75 as well.
    boundary = _eval_criterion(
        {"L": _counts(), "T": _counts(tot=8, att=6, miss=2)},
        75.0,
    )
    assert boundary.passed is True


def test_criterion_pending_in_window_denominator_and_optimizer():
    """Pending classes count in the eligibility window denominator (unlike
    the SUBJECT summary, whose current denominator is done = att + miss) and
    are attendable by the optimizer.

    SEMANTIC DISCOVERY pinned here: eligibility percentages divide by `tot`
    INCLUDING pending. L 1 att / 1 miss / 7 pending (tot 9), T 0/0/3 (tot 3):
    lec% = 1/9*100 = 11.111, tut% = 0/3 = 0. CURRENT criterion value
    (CHUNK 4: POOLED) = (1 + 0)/(9 + 3) = 8.3333 < 75 FAIL — pending stays in
    the window denominator (9 = 1 att + 1 miss + 7 pending). [OLD] mean-of-%
    value was 5.5556.
    Optimizer (CHUNK 3: POOLED): denominator 9 + 3 = 12; need
    (1 + l + t)/12 >= 0.75 -> 1 + l + t >= 9 -> l + t >= 8. Minimum total 8,
    tie broken to fewest lectures -> 5 L + 3 T (OLD said 4 L + 3 T = 7);
    safe skip 2 lectures. Best case attend all: 11/12 = 91.67 >= 75 =>
    reachable. [INVARIANT for the denominator convention; the criterion math
    is CHUNK 4: POOLED and the optimizer is CHUNK 3: POOLED.]
    """
    result = _eval_criterion(
        {
            "L": _counts(tot=9, att=1, miss=1, pending=7),
            "T": _counts(tot=3, att=0, miss=0, pending=3),
        },
        75.0,
    )
    assert result.value == pytest.approx((1 + 0) / (9 + 3) * 100.0)  # pooled counts
    assert result.passed is False
    assert result.optimization.is_reachable is True
    assert result.optimization.lecture_deficit == 5     # pooled; OLD was 4
    assert result.optimization.tutorial_deficit == 3
    assert result.optimization.safe_skip_lecture == 2   # pooled; OLD was 3
    assert result.optimization.safe_skip_tutorial == 0


def test_criterion_case_b_pooled_fail():
    """MANDATORY TEST 2 (Case B): L 1/2, T 4/10, threshold 50.

    OLD mean = (50 + 40)/2 = 45.0 < 50 -> FAIL.
    NEW pooled = (1 + 4)/(2 + 10) = 5/12 = 41.6667 < 50 -> FAIL.
    Same verdict, different value — the pool weights the larger (weaker)
    tutorial bucket instead of averaging the two percentages equally.
    [CHUNK 4: POOLED]
    """
    result = _eval_criterion(
        {"L": _counts(tot=2, att=1, miss=1), "T": _counts(tot=10, att=4, miss=6)},
        50.0,
    )
    assert result.value == pytest.approx(5 / 12 * 100.0)
    assert result.passed is False


def test_criterion_case_c_pooled_fail():
    """MANDATORY TEST 3 (Case C): L 6/10, T 2/3, threshold 75.

    Exact values: OLD mean = (60 + 66.6667)/2 = 63.3333;
    NEW pooled = (6 + 2)/(10 + 3) = 8/13 = 61.5385 < 75 -> FAIL.
    (The audit's illustrative 64% is NOT used — 8/13 is the exact value.)
    [CHUNK 4: POOLED]
    """
    result = _eval_criterion(
        {"L": _counts(tot=10, att=6, miss=4), "T": _counts(tot=3, att=2, miss=1)},
        75.0,
    )
    assert result.value == pytest.approx(8 / 13 * 100.0)
    assert result.passed is False


def test_criterion_old_pass_pooled_fail_on_unequal_denominators():
    """Divergence direction 3: pooled FAILs where the OLD mean PASSed (the
    weaker percentage sits on the LARGER denominator).

    L 2/10 (20%), T 7/7 (100%), threshold 60:
      OLD mean = (20 + 100)/2 = 60.0 >= 60 -> PASS
      NEW pooled = (2 + 7)/(10 + 7) = 9/17 = 52.9412 < 60 -> FAIL
    [CHUNK 4: POOLED]
    """
    result = _eval_criterion(
        {"L": _counts(tot=10, att=2, miss=8), "T": _counts(tot=7, att=7, miss=0)},
        60.0,
    )
    assert result.value == pytest.approx(9 / 17 * 100.0)
    assert result.passed is False


def test_quiz_threshold_fallback_70_75_75():
    """Spec item 8: thresholds 70/75/75. The engine fallback is pinned; the
    persisted eligibility_policies (authoritative in eligibility_service)
    must keep matching it. [INVARIANT]"""
    assert determine_quiz_threshold(1) == 70.0
    assert determine_quiz_threshold(2) == 75.0
    assert determine_quiz_threshold(3) == 75.0
    assert determine_quiz_threshold(4) == 75.0


def _eligibility(counts, cumulative, quiz_cycle=1, required=75.0):
    """End-to-end engine harness (pure; no DB). Both criteria share the
    counts passed for each window; thresholds come from policy_thresholds."""
    subject = _subject([
        Milestone(milestone_id="q1", date=date(2026, 8, 24), type="QUIZ", metadata={"quizCycle": 1}),
        Milestone(milestone_id="q2", date=date(2026, 9, 14), type="QUIZ", metadata={"quizCycle": 2}),
    ])
    return evaluate_quiz_eligibility(
        subject,
        quiz_cycle,
        counts,
        events=[],
        default_weekends=DEFAULT_WEEKENDS,
        policy_thresholds={"lecture_threshold": required},
        cumulative_counts=cumulative,
    )


def _state_for(counts, required):
    """Eligibility state for a single canonical counts dict applied to BOTH
    windows (Quiz I => identical windows), at an arbitrary threshold."""
    return _eligibility(counts, counts, quiz_cycle=1, required=required).state


def test_eligibility_recoverable_best_case_uses_pooled_counts():
    """RECOVERABLE state now comes from the POOLED best case (Chunk 5).

    Both windows: L tot 8 (2 att / 2 miss / 4 pending), T tot 3 (1/1/1),
    required 70. Eligibility totals include pending (see the
    pending-denominator test):
      CURRENT criterion value (Chunk 4 pooled) = (2 + 1)/(8 + 3) = 27.2727
      < 70 FAIL. [OLD] mean-of-% value was 29.1667.
      BEST CASE (Chunk 5 pooled, all pending attended) =
      (2+4 + 1+1)/(8 + 3) = 8/11 = 72.7273 >= 70 => RECOVERABLE.
      [OLD] mean-of-% best case = (75 + 66.667)/2 = 70.833 — also >= 70, so
      this state does not flip; the boundary below pins the exact pooled
      value instead.
    The live eligibility evaluator no longer calls the legacy mean helper
    (source anchor).
    """
    import inspect

    from app.engines.eligibility_engine import evaluate_quiz_eligibility

    counts = {
        "L": _counts(tot=8, att=2, miss=2, pending=4),
        "T": _counts(tot=3, att=1, miss=1, pending=1),
    }
    result = _eligibility(counts, counts, quiz_cycle=1, required=70.0)
    assert result.state == EligibilityState.RECOVERABLE
    assert result.criterion_i.value == pytest.approx((2 + 1) / (8 + 3) * 100.0)  # pooled
    assert result.criterion_i.optimization.is_reachable is True
    # Pooled best-case boundary: RECOVERABLE exactly at 8/11, NOT above it.
    best = 8 / 11 * 100.0
    assert _state_for(counts, best) == EligibilityState.RECOVERABLE
    assert _state_for(counts, best + 0.0001) == EligibilityState.NOT_ELIGIBLE
    # No mean-of-percentages arithmetic remains in the live best-case path.
    assert "_combined_pct(" not in inspect.getsource(evaluate_quiz_eligibility)


def test_hybrid_recoverable_regression_now_not_eligible():
    """MANDATORY HYBRID REGRESSION (the exact Chunk 4 case): the pooled best
    case now governs RECOVERABLE.

    L tot 5 (1 att / 1 miss / 3 pending), T tot 6 (3 att / 3 miss / 0 pending),
    required 64:
      current pooled criterion = (1 + 3)/(5 + 6) = 4/11 = 36.3636 < 64 FAIL.
      BEST CASE (Chunk 5 pooled) = (1+3 + 3+0)/(5 + 6) = 7/11 = 63.6363 < 64
      => NOT_ELIGIBLE / not recoverable — the OLD mean-of-% best case
      (80 + 50)/2 = 65.0 used to (incorrectly) make this RECOVERABLE.
      The Chunk 3 pooled optimizer already reported is_reachable False with
      the full pending as deficits — state and optimizer now agree.
    [CHUNK 5: POOLED] — the hybrid state is gone.
    """
    counts = {
        "L": _counts(tot=5, att=1, miss=1, pending=3),
        "T": _counts(tot=6, att=3, miss=3, pending=0),
    }
    result = _eligibility(counts, counts, quiz_cycle=1, required=64.0)
    assert result.criterion_i.value == pytest.approx(4 / 11 * 100.0)  # pooled
    assert result.criterion_i.passed is False
    assert result.criterion_ii.passed is False
    assert result.state == EligibilityState.NOT_ELIGIBLE    # pooled best < 64
    assert result.is_eligible is False
    assert result.recoverable is False
    assert result.optimization.is_reachable is False        # pooled optimizer
    assert result.optimization.lecture_deficit == 3         # full pending
    assert result.optimization.tutorial_deficit == 0


# Mandatory best-case cases (CHUNK 5). `_best_avg` is a nested projection, so
# each case is pinned through the RECOVERABLE boundary: the state must be
# RECOVERABLE at exactly the pooled best-case value and NOT_ELIGIBLE just
# above it (higher thresholds can never be reached).


def test_best_case_case_1_no_pending_equals_current_pooled():
    """MANDATORY BEST-CASE CASE 1: no pending => best == current pooled.

    L 4/5 att, T 5/10 att (no pending): current = best = 9/15 = 60.0
    (the OLD mean would be 65.0).
    Boundary: 60.0 -> the criterion itself PASSES (ELIGIBLE); 60.0001 ->
    NOT_ELIGIBLE; 62.0 -> NOT_ELIGIBLE under pooled (the OLD criterion 65.0
    would still have passed).
    """
    counts = {
        "L": _counts(tot=5, att=4, miss=1),
        "T": _counts(tot=10, att=5, miss=5),
    }
    assert _state_for(counts, 60.0) == EligibilityState.ELIGIBLE
    assert _state_for(counts, 60.0001) == EligibilityState.NOT_ELIGIBLE
    assert _state_for(counts, 62.0) == EligibilityState.NOT_ELIGIBLE


def test_best_case_case_2_pending_lecture_only():
    """MANDATORY BEST-CASE CASE 2: pending lectures only.

    L tot 6 (2 att / 2 miss / 2 pending), T tot 5 (4 att / 1 miss / 0 pending).
    current pooled = (2 + 4)/11 = 54.5455;
    best pooled = (2+2 + 4+0)/11 = 8/11 = 72.7273.
    [OLD] mean-of-% best = (66.667 + 80)/2 = 73.333 — the divergence shows at
    73.0: pooled NOT_ELIGIBLE, the OLD formula would have been RECOVERABLE.
    """
    counts = {
        "L": _counts(tot=6, att=2, miss=2, pending=2),
        "T": _counts(tot=5, att=4, miss=1, pending=0),
    }
    assert _state_for(counts, 8 / 11 * 100.0) == EligibilityState.RECOVERABLE
    assert _state_for(counts, 8 / 11 * 100.0 + 0.0001) == EligibilityState.NOT_ELIGIBLE
    assert _state_for(counts, 73.0) == EligibilityState.NOT_ELIGIBLE


def test_best_case_case_3_pending_tutorial_only():
    """MANDATORY BEST-CASE CASE 3: pending tutorials only.

    L tot 4 (3 att / 1 miss / 0 pending), T tot 5 (1 att / 1 miss / 3 pending).
    current pooled = (3 + 1)/9 = 44.4444;
    best pooled = (3+0 + 1+3)/9 = 7/9 = 77.7778.
    [OLD] mean-of-% best = (75 + 80)/2 = 77.5 — at 77.6 the pooled form is
    RECOVERABLE where the OLD formula would have been NOT_ELIGIBLE.
    """
    counts = {
        "L": _counts(tot=4, att=3, miss=1, pending=0),
        "T": _counts(tot=5, att=1, miss=1, pending=3),
    }
    assert _state_for(counts, 7 / 9 * 100.0) == EligibilityState.RECOVERABLE
    assert _state_for(counts, 7 / 9 * 100.0 + 0.0001) == EligibilityState.NOT_ELIGIBLE
    assert _state_for(counts, 77.6) == EligibilityState.RECOVERABLE


def test_best_case_case_4_pending_on_both_types():
    """MANDATORY BEST-CASE CASE 4: pending on both types.

    L tot 8 (3 att / 1 miss / 4 pending), T tot 4 (1 att / 1 miss / 2 pending).
    current pooled = (3 + 1)/12 = 33.3333;
    best pooled = (3+4 + 1+2)/12 = 10/12 = 83.3333.
    [OLD] mean-of-% best = (87.5 + 75)/2 = 81.25 — at 82.5 the pooled form is
    RECOVERABLE where the OLD formula would have been NOT_ELIGIBLE.
    """
    counts = {
        "L": _counts(tot=8, att=3, miss=1, pending=4),
        "T": _counts(tot=4, att=1, miss=1, pending=2),
    }
    assert _state_for(counts, 10 / 12 * 100.0) == EligibilityState.RECOVERABLE
    assert _state_for(counts, 10 / 12 * 100.0 + 0.0001) == EligibilityState.NOT_ELIGIBLE
    assert _state_for(counts, 82.5) == EligibilityState.RECOVERABLE


def test_best_case_case_5_unequal_denominators():
    """MANDATORY BEST-CASE CASE 5: unequal denominators (10 vs 2).

    L tot 10 (6 att / 0 miss / 4 pending), T tot 2 (1 att / 1 miss / 0 pending).
    current pooled = (6 + 1)/12 = 58.3333;
    best pooled = (6+4 + 1+0)/12 = 11/12 = 91.6667.
    [OLD] mean-of-% best = (100 + 50)/2 = 75 — at 80 the pooled form is
    RECOVERABLE where the OLD formula would have been NOT_ELIGIBLE.
    """
    counts = {
        "L": _counts(tot=10, att=6, miss=0, pending=4),
        "T": _counts(tot=2, att=1, miss=1, pending=0),
    }
    assert _state_for(counts, 11 / 12 * 100.0) == EligibilityState.RECOVERABLE
    assert _state_for(counts, 11 / 12 * 100.0 + 0.0001) == EligibilityState.NOT_ELIGIBLE
    assert _state_for(counts, 80.0) == EligibilityState.RECOVERABLE


def test_best_case_case_7_equal_denominators_agrees_with_old_mean():
    """MANDATORY BEST-CASE CASE 7: equal denominators — pooled == the OLD mean.

    L tot 4 (1 att / 1 miss / 2 pending), T tot 4 (1 att / 1 miss / 2 pending):
    current = 2/8 = 25.0 (== mean 25.0); best = 6/8 = 75.0 (== mean best 75.0).
    Boundary confirms the shared value: RECOVERABLE at 75.0, NOT above it.
    """
    counts = {
        "L": _counts(tot=4, att=1, miss=1, pending=2),
        "T": _counts(tot=4, att=1, miss=1, pending=2),
    }
    assert _state_for(counts, 75.0) == EligibilityState.RECOVERABLE
    assert _state_for(counts, 75.0001) == EligibilityState.NOT_ELIGIBLE


def test_eligibility_not_eligible_when_best_case_below_required():
    """Best case (attend ALL pending) still below required => NOT_ELIGIBLE.

    L 0/10 (6 conducted missed, 4 pending), T 1/3 (1 att, 2 pending),
    required 75:
      pooled best (Chunk 5) = (0+4 + 1+2)/(10 + 3) = 7/13 = 53.846 < 75
      => NOT_ELIGIBLE. [OLD] mean-of-% best = (40 + 100)/2 = 70 < 75 — the
      verdict was already NOT_ELIGIBLE, so this case is [INVARIANT]; the
      boundary below pins the exact pooled value.
    """
    counts = {
        "L": _counts(tot=10, att=0, miss=6, pending=4),
        "T": _counts(tot=3, att=1, miss=0, pending=2),
    }
    result = _eligibility(counts, counts, quiz_cycle=1, required=75.0)
    assert result.state == EligibilityState.NOT_ELIGIBLE
    assert result.is_eligible is False
    assert result.recoverable is False
    assert _state_for(counts, 7 / 13 * 100.0) == EligibilityState.RECOVERABLE
    assert _state_for(counts, 7 / 13 * 100.0 + 0.0001) == EligibilityState.NOT_ELIGIBLE


def test_eligible_when_criterion_passes_either_route():
    """OR semantics: ELIGIBLE when EITHER criterion passes; Criterion I and
    II share the formula and differ only by window (Quiz I: same window).
    L 8/10, T 4/5, required 70: OLD avg (80+80)/2 = 80 => ELIGIBLE.
    [INVARIANT for this case — both formulas give 80 here.]
    """
    counts = {
        "L": _counts(tot=10, att=8, miss=2),
        "T": _counts(tot=5, att=4, miss=1),
    }
    result = _eligibility(counts, counts, quiz_cycle=1, required=70.0)
    assert result.state == EligibilityState.ELIGIBLE
    assert result.is_eligible is True
    assert result.final_criterion.passed is True
    assert result.criterion_i.passed is True
    assert result.criterion_ii.passed is True


def test_eligibility_unequal_counts_criterion_values_are_pooled():
    """Eligibility-level pin of the CHUNK 4 pooled formula on unequal
    denominators (Case A counts, evaluated end-to-end).

    L 2/5, T 7/7, required 70: pooled criterion value = (2 + 7)/(5 + 7) =
    75.0. [OLD] mean-of-% value was 70.0 (also a boundary PASS).
    [CHUNK 4: POOLED]
    """
    counts = {
        "L": _counts(tot=5, att=2, miss=3),
        "T": _counts(tot=7, att=7, miss=0),
    }
    result = _eligibility(counts, counts, quiz_cycle=1, required=70.0)
    assert result.criterion_i.value == pytest.approx(75.0)   # pooled; OLD was 70.0
    assert result.criterion_ii.value == pytest.approx(75.0)
    assert result.average_pct == pytest.approx(75.0)
    assert result.state == EligibilityState.ELIGIBLE  # 75 >= 70


def test_eligibility_case_a_state_flips_to_eligible():
    """End-to-end flip (Case A): L 2/5, T 7/7, required 75.

    OLD: criterion mean 70.0 < 75 FAIL and the (zero-pending) best case was
    also 70.0 < 75 => NOT_ELIGIBLE.
    NEW pooled criterion = 75.0 >= 75 => Criterion I and II PASS =>
    ELIGIBLE. [CHUNK 4: POOLED]
    """
    counts = {
        "L": _counts(tot=5, att=2, miss=3),
        "T": _counts(tot=7, att=7, miss=0),
    }
    result = _eligibility(counts, counts, quiz_cycle=1, required=75.0)
    assert result.criterion_i.value == pytest.approx(75.0)
    assert result.criterion_ii.value == pytest.approx(75.0)
    assert result.average_pct == pytest.approx(75.0)
    assert result.final_criterion.passed is True
    assert result.state == EligibilityState.ELIGIBLE
    assert result.is_eligible is True


def test_eligibility_route_selection_prefers_fewer_classes_reachable():
    """Route selection: top-level Must Attend comes from the reachable route
    with the fewest total attendances (ties prefer Criterion I).

    Quiz 2 with C-I window much smaller: give C-II (cumulative) a strictly
    smaller requirement? Both criteria share `required`; divergence comes
    from window sizes. Construct: C-I counts L 0/3 pend, T 0/3 pend
    (min 2L+2T? enumerate: (3/3? ...)) — simpler: C-I zero pending and
    passing (0 deficit), C-II needs 2 -> top-level must pick C-I.
    C-I: L 9/10 att (1 miss), T 4/4 => OLD avg 95 >= 75 ELIGIBLE, 0 deficit.
    C-II: L 6/10 att (4 pend... 1 miss 3 pend), T 4/4: current (60+100)/2=80
    — also eligible; give C-II a pending-heavy state so its optimizer needs
    attendance: L 0/2 att (1 miss 1 pend), T 0/0/2 pend => current avg 0,
    best-case attend 3 (1L+2T): (50+100)/2=75 >= 75 reachable, deficit 3.
    [INVARIANT — route selection is formula-agnostic plumbing.]
    """
    ci_counts = {
        "L": _counts(tot=10, att=9, miss=1),
        "T": _counts(tot=4, att=4, miss=0),
    }
    cii_counts = {
        "L": _counts(tot=2, att=0, miss=1, pending=1),
        "T": _counts(tot=2, att=0, miss=0, pending=2),
    }
    result = _eligibility(ci_counts, cii_counts, quiz_cycle=2, required=75.0)
    assert result.criterion_i.passed is True
    assert result.criterion_ii.passed is False
    assert result.state == EligibilityState.ELIGIBLE
    assert result.must_attend_criterion == "Criterion I"
    assert result.optimization.lecture_deficit == 0
    assert result.optimization.tutorial_deficit == 0


def test_combined_pct_arithmetic_direct():
    """_combined_pct is a HISTORICAL reference only (arithmetic unchanged).

    Chunk 4 moved the CURRENT criterion and Chunk 5 the best-case /
    RECOVERABLE projection to the pooled count-level form; the legacy mean
    helper now has NO production callers and is retained only so this
    baseline file can pin the OLD formula's arithmetic for the record.
    """
    assert _combined_pct(80.0, None) == pytest.approx(80.0)   # no-T collapse
    assert _combined_pct(None, 75.0) is None                  # tutorial-only quirk
    assert _combined_pct(40.0, 100.0) == pytest.approx(70.0)  # legacy mean
    assert _pct(2, 5) == pytest.approx(40.0)
    assert _pct(0, 0) is None


def test_pooled_pct_arithmetic_direct():
    """`_pooled_pct` is the canonical CURRENT eligibility math (count-level)
    and the single source of the pooled percentage used by both criteria."""
    # Mandatory numerical cases 1-5.
    assert _pooled_pct(2, 5, 7, 7) == pytest.approx(75.0)             # Test 1 / Case A
    assert _pooled_pct(1, 2, 4, 10) == pytest.approx(5 / 12 * 100.0)  # Test 2 / Case B
    assert _pooled_pct(6, 10, 2, 3) == pytest.approx(8 / 13 * 100.0)  # Test 3 / Case C
    assert _pooled_pct(0, 0, 6, 8) == pytest.approx(75.0)             # Test 4 tutorial-only
    assert _pooled_pct(4, 5, 4, 5) == pytest.approx(80.0)             # Test 5 equal denom
    # A missing type contributes nothing to either side — never a zero bucket
    # and never (0 + T%)/2.
    assert _pooled_pct(8, 10, 0, 0) == pytest.approx(80.0)            # lecture-only
    assert _pooled_pct(0, 0, 6, 8) != pytest.approx((0.0 + 75.0) / 2.0)
    # Zero total window => None (established undefined semantics preserved).
    assert _pooled_pct(0, 0, 0, 0) is None
    # Equal denominators: pooled == the legacy mean (invariance).
    assert _pooled_pct(4, 5, 4, 5) == pytest.approx(_combined_pct(80.0, 80.0))


def test_eligibility_single_and_batch_paths_share_the_pooled_math():
    """BATCH CONSISTENCY: same counts -> same pooled percentage -> same
    criterion outcome for the single-subject and batch (dashboard) paths.

    Both service entry points delegate to the SAME canonical evaluator
    (`_evaluate_subject` -> `evaluate_quiz_eligibility` ->
    `_evaluate_criterion` -> `_pooled_pct`); the batch path only differs in
    HOW the canonical (class_type, status) rows are fetched and bucketed
    (one union scan). The counts produced by the batch path's aggregation
    (`EligibilityService._build_counts`) therefore feed identical
    mathematics — verified below with the Case A rows.
    """
    import inspect

    from app.models.enums import AttendanceStatus as AS
    from app.models.enums import ClassType as CT
    from app.services.eligibility_service import EligibilityService

    # Case A rows: 2 L attended, 3 L missed, 7 T attended (no pending).
    raw = (
        [(CT.LECTURE, AS.ATTENDED)] * 2
        + [(CT.LECTURE, AS.MISSED)] * 3
        + [(CT.TUTORIAL, AS.ATTENDED)] * 7
    )
    built = EligibilityService._build_counts(raw)  # the batch path's aggregation
    assert built["L"] == {"tot": 5, "att": 2, "miss": 3, "pending": 0}
    assert built["T"] == {"tot": 7, "att": 7, "miss": 0, "pending": 0}

    expected = _pooled_pct(
        built["L"]["att"], built["L"]["tot"], built["T"]["att"], built["T"]["tot"]
    )
    assert expected == pytest.approx(75.0)

    result = _eligibility(built, built, quiz_cycle=1, required=75.0)
    assert result.criterion_i.value == pytest.approx(expected)
    assert result.criterion_ii.value == pytest.approx(expected)
    assert result.criterion_i.passed is True
    assert result.state == EligibilityState.ELIGIBLE

    # Structural proof: both service methods use the one shared evaluator,
    # and the current criterion path calls the pooled helper (no mean-of-%
    # arithmetic left in the current-criterion code path).
    assert "_evaluate_subject" in inspect.getsource(
        EligibilityService.get_quiz_eligibility
    )
    assert "_evaluate_subject" in inspect.getsource(
        EligibilityService.get_quiz_eligibility_for_subjects
    )
    criterion_src = inspect.getsource(_evaluate_criterion)
    assert "_pooled_pct(" in criterion_src
    assert "_combined_pct(" not in criterion_src


# ---------------------------------------------------------------------------
# Task 4 — window semantics (calendar engine; no logic changes in this chunk)
# ---------------------------------------------------------------------------


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


class TestWindowSemantics:
    """Window boundary invariants (spec item 5) — pure calendar-engine checks:
    no DB, no repository, no mutation. These must be untouched by the formula
    change."""

    def test_criterion_i_prev_quiz_date_inclusive_and_quiz_minus_1_end(self):
        window = get_attendance_window(_subject([_Q1, _Q2]), "q2", [], DEFAULT_WEEKENDS)
        assert window["window_start"] == date(2026, 8, 24)  # prev quiz INCLUSIVE
        assert window["window_end"] == date(2026, 9, 13)    # quiz - 1

    def test_criterion_ii_starts_at_commencement(self):
        window = get_cumulative_attendance_window(_subject([_Q1, _Q2]), "q2", [], DEFAULT_WEEKENDS)
        assert window["window_start"] == date(2026, 7, 15)  # commencement
        assert window["window_end"] == date(2026, 9, 13)

    def test_quiz_i_window_starts_at_commencement(self):
        window = get_attendance_window(_subject([_Q1]), "q1", [], DEFAULT_WEEKENDS)
        assert window["window_start"] == date(2026, 7, 15)
        assert window["window_end"] == date(2026, 8, 23)

    def test_degenerate_window_is_empty_not_error(self):
        quiz_on_commencement = Milestone(
            milestone_id="q1", date=date(2026, 7, 15), type="QUIZ", metadata={"quizCycle": 1}
        )
        window = get_attendance_window(_subject([quiz_on_commencement]), "q1", [], DEFAULT_WEEKENDS)
        assert window["teaching_days"] == 0
        assert window["effective_teaching_dates"] == []

    def test_criterion_ii_window_is_superset_of_criterion_i(self):
        """Structural invariant the OR-semantics rely on. [INVARIANT]"""
        wi = get_attendance_window(_subject([_Q1, _Q2]), "q2", [], DEFAULT_WEEKENDS)
        wii = get_cumulative_attendance_window(_subject([_Q1, _Q2]), "q2", [], DEFAULT_WEEKENDS)
        assert wii["window_start"] <= wi["window_start"]
        assert wii["window_end"] >= wi["window_end"]


def test_quiz_day_exclusion_contract_documented():
    """Spec item 5, non-DB half. The date-boundary half is proven by
    TestWindowSemantics (previous quiz date INSIDE the next window). The
    shape half is repository logic that must NOT change in this chunk; its
    contract, verbatim from attendance_repo.get_subject_counts_between
    (exclude_quiz_day=True):

        NOT (timetable_entry_id IS NULL AND NOT is_extra
             AND class_type = LECTURE)

    i.e. ONLY the quiz-day-shaped session is excluded; regular L/T classes on
    the same (previous-quiz) date remain included. The live behavior is
    verified by backend/scripts/verify_quiz_day_occurrence.py.
    """
    predicate_source = "timetable_entry_id.is_(None) & ~is_extra & class_type == LECTURE"
    assert "timetable_entry_id" in predicate_source  # documentation anchor
    assert get_attendance_window is not None
