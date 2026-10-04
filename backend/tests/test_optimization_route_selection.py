"""Top-level Must Attend / Safe Skip ROUTE SELECTION under OR semantics.

Phase 27 (QC-II remediation) made the two top-level routes independent:
Must Attend = the REACHABLE criterion requiring the fewest future attendances
(ties prefer Criterion I, stable min); Safe Skip = among REACHABLE criteria,
the route permitting the most total skipped pending classes (strictly-greater
replacement over the C-I-first candidate order). Under OR semantics the two
selections MAY legitimately name different criteria, and an unreachable
criterion can never win either selection while a reachable one exists.

The 2026-10 audit found this selection logic untested. Every case below was
hand-derived before running the engine (derivations inline); the eligibility
engine consumes constructed window counts exactly as the service layer feeds
them (same call path as test_pooled_formula_end_to_end.py).

Threshold is 75 throughout. Counts are L-only except where noted.
"""

from datetime import date

from app.engines.eligibility_engine import evaluate_quiz_eligibility
from app.schemas.academic import Milestone, Subject, SubjectCategory, Timeline
from app.schemas.attendance import EligibilityState


def _c(tot=0, att=0, miss=0, pending=0):
    return {"tot": tot, "att": att, "miss": miss, "pending": pending}


def _counts(l, t=None):
    return {"L": l, "T": t or _c()}


def _subject():
    return Subject(
        code="BCS-501",
        name="DBMS",
        category=SubjectCategory.THEORY,
        quiz_applicable=True,
        attendance_applicable=True,
        timeline=Timeline(
            commencement_date=date(2026, 7, 15),
            milestones=[
                Milestone(milestone_id="q1", date=date(2026, 8, 24), type="QUIZ", metadata={"quizCycle": 1}),
                Milestone(milestone_id="q2", date=date(2026, 9, 14), type="QUIZ", metadata={"quizCycle": 2}),
            ],
        ),
    )


def _evaluate(counts_i, pre=None, threshold=75.0):
    """Criterion II counts = pre-window + cycle window (canonical count contract)."""
    cumulative = counts_i
    if pre is not None:
        cumulative = {
            k: _c(
                tot=counts_i[k]["tot"] + pre[k]["tot"],
                att=counts_i[k]["att"] + pre[k]["att"],
                miss=counts_i[k]["miss"] + pre[k]["miss"],
                pending=counts_i[k]["pending"] + pre[k]["pending"],
            )
            for k in ("L", "T")
        }
    return evaluate_quiz_eligibility(
        _subject(), 2, counts_i, events=[], default_weekends=[0, 6],
        policy_thresholds={"lecture_threshold": threshold},
        cumulative_counts=cumulative,
    )


def _must(result):
    return (result.optimization.lecture_deficit, result.optimization.tutorial_deficit)


def _skip(result):
    opt = result.safe_skip_optimization
    return None if opt is None else (opt.safe_skip_lecture, opt.safe_skip_tutorial)


def test_criterion_i_passed_criterion_ii_unreachable():
    # I: 3/4 = 75% exactly, no pending -> PASSED, reachable, must 0, skip 0.
    # II: 3/14 = 21.4%, no pending -> UNREACHABLE.
    # Expected: ELIGIBLE; both routes come from Criterion I (the only
    # reachable one); the dead route never surfaces.
    r = _evaluate(_counts(_c(tot=4, att=3, miss=1)), pre=_counts(_c(tot=10, att=0, miss=10)))
    assert r.state == EligibilityState.ELIGIBLE
    assert r.must_attend_criterion == "Criterion I"
    assert _must(r) == (0, 0)
    assert r.optimization.is_reachable is True
    assert r.safe_skip_criterion == "Criterion I"
    assert _skip(r) == (0, 0)


def test_criterion_i_unreachable_criterion_ii_passed():
    # I: 3/5 done + 1 pending: best (3+1)/6 = 66.7% < 75 -> UNREACHABLE
    #    (deficit would be its full pending, but it must not win).
    # II: 13/16 = 81.25% already PASSED, 1 cumulative pending lecture: that
    #     lecture is skippable (13/16 stays >= 75 without it) -> skip (1, 0).
    # Expected: ELIGIBLE; Must Attend (0) from Criterion II (reachable, deficit
    # 0 beats I's unreachable full-pending deficit); Safe Skip from II too
    # (I is excluded from skip candidates entirely).
    r = _evaluate(
        _counts(_c(tot=6, att=3, miss=2, pending=1)),
        pre=_counts(_c(tot=10, att=10)),
    )
    assert r.state == EligibilityState.ELIGIBLE
    assert r.must_attend_criterion == "Criterion II"
    assert _must(r) == (0, 0)
    assert r.safe_skip_criterion == "Criterion II"
    assert _skip(r) == (1, 0)


def test_both_recoverable_must_and_skip_from_different_criteria():
    # I:  6/10 done, 2 pending: (6+a)/10 >= .75 -> a >= 2 -> must 2, skip 0.
    # II: 14/22 cumulative, 5 pending: (14+b)/22 >= .75 -> 14+b >= 16.5 ->
    #     b >= 3 (exact ceil of 2.5) -> must 3, skip 2.
    # Expected: RECOVERABLE; Must Attend from Criterion I (fewest required:
    # 2 < 3); Safe Skip from Criterion II (most skippable: 2 > 0) — the two
    # routes legitimately name DIFFERENT criteria under OR semantics.
    r = _evaluate(
        _counts(_c(tot=10, att=6, miss=2, pending=2)),
        pre=_counts(_c(tot=12, att=8, miss=1, pending=3)),
    )
    assert r.state == EligibilityState.RECOVERABLE
    assert r.recoverable is True
    assert r.must_attend_criterion == "Criterion I"
    assert _must(r) == (2, 0)
    assert r.safe_skip_criterion == "Criterion II"
    assert _skip(r) == (2, 0)


def test_passed_route_wins_must_attend_but_loses_safe_skip():
    # I:  5/8 done, 2 pending: (5+a)/8 >= .75 -> a >= 1 -> must 1, skip 1.
    # II: 15/18 cumulative, 2 pending: already 83.3% -> must 0, skip 2.
    # Expected: ELIGIBLE; Must Attend from Criterion II (0 required);
    # Safe Skip from Criterion II as well (2 > 1).
    r = _evaluate(
        _counts(_c(tot=8, att=5, miss=1, pending=2)),
        pre=_counts(_c(tot=10, att=10)),
    )
    assert r.state == EligibilityState.ELIGIBLE
    assert r.must_attend_criterion == "Criterion II"
    assert _must(r) == (0, 0)
    assert r.safe_skip_criterion == "Criterion II"
    assert _skip(r) == (2, 0)


def test_equal_safe_skips_prefer_criterion_i():
    # I:  5/8 done, 2 pending: (5+a)/8 >= .75 -> a >= 1 -> must 1, skip 1.
    # II: 7/10 cumulative, 2 pending: (7+a)/10 >= .75 -> a >= 1 -> must 1, skip 1.
    # Equal deficits AND equal skips -> both tie-breaks prefer Criterion I
    # (stable min for must; strictly-greater replacement for skip).
    r = _evaluate(
        _counts(_c(tot=8, att=5, miss=1, pending=2)),
        pre=_counts(_c(tot=2, att=2)),
    )
    assert r.state == EligibilityState.RECOVERABLE
    assert r.must_attend_criterion == "Criterion I"
    assert _must(r) == (1, 0)
    assert r.safe_skip_criterion == "Criterion I"
    assert _skip(r) == (1, 0)


def test_both_unreachable_no_safe_skip_route():
    # I: 0/10, II: 0/20 — nothing reachable. Expected: NOT_ELIGIBLE, no Safe
    # Skip route at all (None), must-attend falls back to the stable-min
    # candidate (Criterion I) with is_reachable False; the UI withholds
    # guidance for unreachable routes.
    r = _evaluate(_counts(_c(tot=10, att=0, miss=10)), pre=_counts(_c(tot=10, att=0, miss=10)))
    assert r.state == EligibilityState.NOT_ELIGIBLE
    assert r.recoverable is False
    assert r.must_attend_criterion == "Criterion I"
    assert _must(r) == (0, 0)
    assert r.optimization.is_reachable is False
    assert r.safe_skip_criterion is None
    assert r.safe_skip_optimization is None


def test_selected_routes_are_criteria_own_optimizations_never_merges():
    # Structural pin: both top-level routes are ALWAYS one of the two
    # criteria's own OptimizationResult objects (never a cross-criteria merge
    # or a recomputation), and Safe Skip is the max-skip REACHABLE criterion.
    r = _evaluate(
        _counts(_c(tot=10, att=6, miss=2, pending=2)),
        pre=_counts(_c(tot=12, att=8, miss=1, pending=3)),
    )
    assert r.optimization is r.criterion_i.optimization or r.optimization is r.criterion_ii.optimization
    assert r.safe_skip_optimization is r.criterion_i.optimization or r.safe_skip_optimization is r.criterion_ii.optimization

    reachable = [
        o for o in (r.criterion_i.optimization, r.criterion_ii.optimization) if o.is_reachable
    ]
    best = max(reachable, key=lambda o: o.safe_skip_lecture + o.safe_skip_tutorial)
    assert r.safe_skip_optimization is best
    # Skips are per-criterion facts: pending minus that route's own attendance.
    for opt in (r.criterion_i.optimization, r.criterion_ii.optimization):
        assert opt.safe_skip_lecture >= 0 and opt.safe_skip_tutorial >= 0
    assert r.safe_skip_criterion in ("Criterion I", "Criterion II")
    assert r.must_attend_criterion in ("Criterion I", "Criterion II")
