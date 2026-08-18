from datetime import date
from typing import Optional, Dict, Any
from app.schemas.academic import Subject
from app.schemas.attendance import (
    EligibilityResult, EligibilityState, OptimizationResult,
    CriterionResult, FinalCriterionResult, ClassCounts,
)
from app.engines.attendance_engine import optimize_attendance
from app.engines.calendar_engine import get_attendance_window, get_cumulative_attendance_window

def determine_quiz_threshold(quiz_cycle: int) -> float:
    """
    Returns the official target percentage threshold for a given quiz cycle.
    Based on the SRMCEM Attendance Criteria notice of 14 July 2026.
    """
    if quiz_cycle == 1:
        return 70.0
    elif quiz_cycle == 2:
        return 75.0
    elif quiz_cycle == 3:
        return 75.0
    return 75.0 # fallback

def _pct(attended: int, total: int) -> Optional[float]:
    return (attended / total * 100.0) if total > 0 else None

def _combined_pct(lec_pct: Optional[float], tut_pct: Optional[float]) -> Optional[float]:
    """Official combined formula: (Lecture % + Tutorial %) / 2.
    Subjects without tutorials collapse to the lecture percentage."""
    if tut_pct is None:
        return lec_pct
    if lec_pct is None:
        return None
    return (lec_pct + tut_pct) / 2.0

def _fmt(pct: Optional[float]) -> str:
    return "N/A" if pct is None else f"{pct:.1f}%"

def _norm_counts(counts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Canonical L/T count shape with all four fields present."""
    if counts is None:
        counts = {}
    return {
        'tot': counts.get('tot', 0),
        'att': counts.get('att', 0),
        'miss': counts.get('miss', 0),
        'pending': counts.get('pending', 0),
    }

def _evaluate_criterion(
    name: str,
    window: Dict[str, Any],
    counts: Dict[str, Any],
    required: float,
) -> CriterionResult:
    """One qualifying route of the official policy. Both criteria use the SAME
    lecture/tutorial average formula; they differ only in the counting window:
      - Criterion I  = cycle window (previous quiz boundary -> day before quiz)
      - Criterion II = cumulative window (commencement -> day before quiz)
    Must Attend / Safe Skip are derived from the same window counts and the
    same average formula via the attendance engine's optimizer (no separate
    frontend mathematics)."""
    l = _norm_counts(counts.get('L'))
    t = _norm_counts(counts.get('T'))

    lec_pct = _pct(l['att'], l['tot'])
    tut_pct = _pct(t['att'], t['tot'])
    avg_pct = _combined_pct(lec_pct, tut_pct)

    opt = optimize_attendance(
        l['tot'], l['att'], l['miss'], l['pending'],
        t['tot'], t['att'], t['miss'], t['pending'],
        required,
    )

    if tut_pct is None:
        explanation = (
            f"Average of lecture + tutorial attendance {_fmt(avg_pct)} vs "
            f"required {required:.0f}% (no tutorials in the window "
            f"{window['window_start']} to {window['window_end']} — the average "
            f"equals lecture attendance)."
        )
    else:
        explanation = (
            f"Average of lecture + tutorial attendance {_fmt(avg_pct)} vs "
            f"required {required:.0f}% (window {window['window_start']} to "
            f"{window['window_end']})."
        )

    return CriterionResult(
        name=name,
        value=avg_pct,
        threshold=required,
        passed=avg_pct is not None and avg_pct >= required,
        optimization=opt,
        explanation=explanation,
    )

def _total_deficit(opt: OptimizationResult) -> int:
    return opt.lecture_deficit + opt.tutorial_deficit

def evaluate_quiz_eligibility(
    subject: Subject,
    quiz_cycle: int,
    attendance_counts: Dict[str, Any], # Aggregated up to window_end (Criterion I window)
    events: list,
    default_weekends: list,
    policy_thresholds: Optional[Dict[str, float]] = None,
    cumulative_counts: Optional[Dict[str, Any]] = None, # Criterion II window (commencement -> day before quiz)
) -> EligibilityResult:
    """
    Evaluates quiz eligibility incorporating the full official policy.
    Conceptual Flow:
    1. Determine both applicable attendance windows (Criterion I = cycle
       window; Criterion II = cumulative window from commencement)
    2. Determine applicable eligibility policy (thresholds)
    3. Evaluate lecture/tutorial requirements via exhaustive optimization
    4. Evaluate the official qualifying routes (S4 PRODUCT SPEC §5):
       (Criterion I qualifies) OR (Criterion II qualifies) = Eligible, where
       BOTH Criterion I and Criterion II use the same lecture/tutorial average
       formula — (Lecture % + Tutorial %) / 2 — and differ only in the
       counting window.
    5. Derive the canonical state: ELIGIBLE / RECOVERABLE / NOT_ELIGIBLE /
       UNRESOLVED (current pass, best-case pass, neither, no confirmed date).

    Optimization math is delegated unchanged to the attendance engine; this
    function only re-uses the same counts to derive criteria and state.
    """

    # 1. Determine Windows
    milestone_id = f"q{quiz_cycle}"
    
    # Conflict/Anomaly Resolution: BCS-054 Q3
    milestone = next((m for m in subject.timeline.milestones if m.milestone_id == milestone_id), None) if subject.timeline else None
    
    if not subject.quiz_applicable or not subject.timeline or not milestone:
        return EligibilityResult(
            quiz_cycle=quiz_cycle,
            subject_code=subject.code,
            window_start=date.today(), # Placeholder as window is invalid
            window_end=date.today(),
            state=EligibilityState.UNRESOLVED,
            is_eligible=False,
            explanation=(
                f"Quiz cycle {quiz_cycle} for {subject.code} has no confirmed "
                "schedule yet, so no eligibility result can be determined."
            ),
            policy_ambiguity_notes=f"Quiz cycle {quiz_cycle} is unresolved/unavailable for subject {subject.code}."
        )

    window_i = get_attendance_window(subject, milestone_id, events, default_weekends)
    window_ii = get_cumulative_attendance_window(subject, milestone_id, events, default_weekends)
    
    # 2. Determine Policy (persisted configuration wins; engine fallback otherwise).
    #    Both criteria share the SAME required percentage and the SAME formula;
    #    the difference between them is purely the counting window.
    if policy_thresholds and policy_thresholds.get('lecture_threshold') is not None:
        required = policy_thresholds['lecture_threshold']
    else:
        required = determine_quiz_threshold(quiz_cycle)

    # 3. Evaluate Requirements (per criterion, on that criterion's own window)
    criterion_i = _evaluate_criterion(
        "Criterion I — Lecture + Tutorial Average",
        window_i, attendance_counts, required,
    )
    criterion_ii = _evaluate_criterion(
        "Criterion II — Lecture + Tutorial Average",
        window_ii, cumulative_counts if cumulative_counts is not None else attendance_counts,
        required,
    )

    # 4. Window analytics (same canonical counting as Track) for the displayed
    #    Criterion I (cycle) window.
    l_data = _norm_counts(attendance_counts.get('L'))
    t_data = _norm_counts(attendance_counts.get('T'))
    lec_pct = _pct(l_data['att'], l_data['tot'])
    tut_pct = _pct(t_data['att'], t_data['tot'])
    avg_pct = _combined_pct(lec_pct, tut_pct)

    # 5. Official qualifying routes
    final_criterion = FinalCriterionResult(
        combination="Criterion I OR Criterion II",
        passed=criterion_i.passed or criterion_ii.passed,
        explanation=(
            "Eligible when either route meets its required percentage "
            "((Criterion I qualifies) OR (Criterion II qualifies)); both "
            "routes use the lecture/tutorial average and differ only in the "
            "counting window."
        ),
    )

    # Best case per criterion: every pending class in that criterion's window
    # is attended (the optimizer's model).
    def _best_avg(counts: Dict[str, Any]) -> Optional[float]:
        l = _norm_counts(counts.get('L'))
        t = _norm_counts(counts.get('T'))
        return _combined_pct(
            _pct(l['att'] + l['pending'], l['tot']),
            _pct(t['att'] + t['pending'], t['tot']),
        )

    best_i = _best_avg(attendance_counts)
    best_ii = _best_avg(cumulative_counts if cumulative_counts is not None else attendance_counts)

    # 6. Canonical state derivation. The top-level Must Attend / Safe Skip is
    #    the best REACHABLE route: among criteria whose own optimization can
    #    actually reach the threshold, the fewest classes still required wins
    #    (ties prefer Criterion I), so guidance never requires more attendance
    #    than the OR semantics demand and never surfaces an unreachable route
    #    for a RECOVERABLE state (a zero-pending criterion's 0/0 early return
    #    would otherwise win the min-deficit tie while being unreachable).
    if criterion_i.passed or criterion_ii.passed:
        state = EligibilityState.ELIGIBLE
        explanation = (
            f"Currently satisfies the attendance requirement for "
            f"Quiz {quiz_cycle} ({final_criterion.combination})."
        )
    elif (best_i is not None and best_i >= required) or (
            best_ii is not None and best_ii >= required):
        state = EligibilityState.RECOVERABLE
        explanation = (
            f"Below the required {required:.0f}% now, but reachable by "
            "attending the pending classes listed under Must Attend."
        )
    else:
        state = EligibilityState.NOT_ELIGIBLE
        explanation = (
            f"The required {required:.0f}% cannot be reached within the "
            "remaining attendance window."
        )

    best_opt = min(
        (criterion_i.optimization, criterion_ii.optimization),
        key=lambda o: (not o.is_reachable, _total_deficit(o)),
    )

    return EligibilityResult(
        quiz_cycle=quiz_cycle,
        subject_code=subject.code,
        window_start=window_i['window_start'],
        window_end=window_i['window_end'],
        lecture_threshold=required,
        combined_threshold=required if t_data['tot'] > 0 else None,
        required_percentage=required,
        lecture=ClassCounts(
            total=l_data['tot'], attended=l_data['att'],
            missed=l_data['miss'], pending=l_data['pending'],
        ),
        tutorial=ClassCounts(
            total=t_data['tot'], attended=t_data['att'],
            missed=t_data['miss'], pending=t_data['pending'],
        ),
        lecture_pct=lec_pct,
        tutorial_pct=tut_pct,
        average_pct=avg_pct,
        state=state,
        recoverable=state == EligibilityState.RECOVERABLE,
        criterion_i=criterion_i,
        criterion_ii=criterion_ii,
        final_criterion=final_criterion,
        is_eligible=state == EligibilityState.ELIGIBLE,
        optimization=best_opt,
        explanation=explanation,
    )
