from datetime import date
from typing import Optional, Dict, Any
from app.schemas.academic import Subject, QuizCycle
from app.schemas.attendance import (
    EligibilityResult, EligibilityState, OptimizationResult,
    CriterionResult, FinalCriterionResult, ClassCounts,
)
from app.engines.attendance_engine import optimize_attendance, meets_attendance_target
from app.engines.calendar_engine import get_attendance_window

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

def evaluate_quiz_eligibility(
    subject: Subject,
    quiz_cycle: int,
    attendance_counts: Dict[str, Any], # Aggregated up to window_end
    events: list,
    default_weekends: list,
    policy_thresholds: Optional[Dict[str, float]] = None,
) -> EligibilityResult:
    """
    Evaluates quiz eligibility incorporating the full official policy.
    Conceptual Flow:
    1. Determine applicable attendance window
    2. Determine applicable eligibility policy (thresholds)
    3. Evaluate lecture/tutorial requirements via exhaustive optimization
    4. Evaluate the official qualifying routes (S4 PRODUCT SPEC §5):
       (Criterion I qualifies) OR (Criterion II qualifies) = Eligible, where
       Criterion I = lecture attendance %, Criterion II = combined average %.
    5. Derive the canonical state: ELIGIBLE / RECOVERABLE / NOT_ELIGIBLE /
       UNRESOLVED (current pass, best-case pass, neither, no confirmed date).

    Optimization math is delegated unchanged to the attendance engine; this
    function only re-uses the same counts to derive criteria and state.
    """
    
    # 1. Determine Window
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

    window = get_attendance_window(subject, milestone_id, events, default_weekends)
    
    # 2. Determine Policy (persisted configuration wins; engine fallback otherwise)
    if policy_thresholds:
        req_lecture = policy_thresholds.get('lecture_threshold')
        req_combined = policy_thresholds.get('combined_threshold') or req_lecture
    else:
        req_lecture = determine_quiz_threshold(quiz_cycle)
        req_combined = req_lecture
    
    # 3. Evaluate Requirements
    l_data = attendance_counts.get('L', {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0})
    t_data = attendance_counts.get('T', {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0})
    
    opt_result = optimize_attendance(
        l_data['tot'], l_data['att'], l_data['miss'], l_data['pending'],
        t_data['tot'], t_data['att'], t_data['miss'], t_data['pending'],
        req_lecture
    )
    
    # 4. Window analytics (same canonical counting as Track).
    #    Current: pending classes have not yet occurred (treated as not
    #    attended, exactly like the legacy percentages). Best case: every
    #    remaining pending class is attended (the optimizer's model).
    lec_pct = _pct(l_data['att'], l_data['tot'])
    tut_pct = _pct(t_data['att'], t_data['tot'])
    avg_pct = _combined_pct(lec_pct, tut_pct)
    
    best_lec_pct = _pct(l_data['att'] + l_data['pending'], l_data['tot'])
    best_tut_pct = _pct(t_data['att'] + t_data['pending'], t_data['tot'])
    best_avg_pct = _combined_pct(best_lec_pct, best_tut_pct)
    
    # 5. Official qualifying routes
    criterion_i = CriterionResult(
        name="Criterion I — Lecture Attendance",
        value=lec_pct,
        threshold=req_lecture,
        passed=lec_pct is not None and lec_pct >= req_lecture,
        explanation=f"Lecture attendance {_fmt(lec_pct)} vs required {req_lecture:.0f}%.",
    )
    if t_data['tot'] > 0:
        criterion_ii = CriterionResult(
            name="Criterion II — Combined (Lecture + Tutorial) Average",
            value=avg_pct,
            threshold=req_combined,
            passed=avg_pct is not None and avg_pct >= req_combined,
            explanation=f"Average of lecture + tutorial attendance {_fmt(avg_pct)} vs required {req_combined:.0f}%.",
        )
    else:
        criterion_ii = CriterionResult(
            name="Criterion II — Combined (Lecture + Tutorial) Average",
            value=lec_pct,
            threshold=req_combined,
            passed=lec_pct is not None and lec_pct >= req_combined,
            explanation=(
                f"No tutorials in this attendance window — the average equals "
                f"lecture attendance {_fmt(lec_pct)} vs required {req_combined:.0f}%."
            ),
        )
    
    final_criterion = FinalCriterionResult(
        combination="Criterion I OR Criterion II",
        passed=criterion_i.passed or criterion_ii.passed,
        explanation=(
            "Eligible when either route meets its required percentage "
            "((Criterion I qualifies) OR (Criterion II qualifies))."
        ),
    )
    
    # 6. Canonical state derivation
    #    Best case reuses the same percentages the optimizer reasons about, so
    #    RECOVERABLE is exactly "below the target but reachable" (the average
    #    route via the optimizer, plus the lecture-only route via Criterion I).
    if criterion_i.passed or criterion_ii.passed:
        state = EligibilityState.ELIGIBLE
        explanation = (
            f"Currently satisfies the attendance requirement for "
            f"Quiz {quiz_cycle} ({final_criterion.combination})."
        )
    elif (best_lec_pct is not None and best_lec_pct >= req_lecture) or (
            best_avg_pct is not None and best_avg_pct >= req_combined):
        state = EligibilityState.RECOVERABLE
        explanation = (
            f"Below the required {req_lecture:.0f}% now, but reachable by "
            "attending the pending classes listed under Must Attend."
        )
    else:
        state = EligibilityState.NOT_ELIGIBLE
        explanation = (
            f"The required {req_lecture:.0f}% cannot be reached within the "
            "remaining attendance window."
        )
    
    return EligibilityResult(
        quiz_cycle=quiz_cycle,
        subject_code=subject.code,
        window_start=window['window_start'],
        window_end=window['window_end'],
        lecture_threshold=req_lecture,
        combined_threshold=req_combined if t_data['tot'] > 0 else None,
        required_percentage=req_lecture,
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
        optimization=opt_result,
        explanation=explanation,
    )