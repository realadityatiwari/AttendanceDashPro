from datetime import date
from typing import Optional, Dict, Any
from app.schemas.academic import Subject, QuizCycle
from app.schemas.attendance import EligibilityResult, OptimizationResult
from app.engines.attendance_engine import optimize_attendance
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

def evaluate_quiz_eligibility(
    subject: Subject,
    quiz_cycle: int,
    attendance_counts: Dict[str, Any], # Aggregated up to window_end
    events: list,
    default_weekends: list
) -> EligibilityResult:
    """
    Evaluates quiz eligibility incorporating the full official policy.
    Conceptual Flow:
    1. Determine applicable attendance window
    2. Determine applicable eligibility policy (thresholds)
    3. Evaluate lecture/tutorial requirements via exhaustive optimization
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
            is_eligible=False,
            policy_ambiguity_notes=f"Quiz cycle {quiz_cycle} is unresolved/unavailable for subject {subject.code}."
        )

    window = get_attendance_window(subject, milestone_id, events, default_weekends)
    
    # 2. Determine Policy
    target_pct = determine_quiz_threshold(quiz_cycle)
    
    # 3. Evaluate Requirements
    l_data = attendance_counts.get('L', {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0})
    t_data = attendance_counts.get('T', {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0})
    
    opt_result = optimize_attendance(
        l_data['tot'], l_data['att'], l_data['miss'], l_data['pending'],
        t_data['tot'], t_data['att'], t_data['miss'], t_data['pending'],
        target_pct
    )
    
    # For eligibility at exactly the boundary (no pending classes left), 
    # if deficit > 0, they are not eligible.
    is_eligible = opt_result.lecture_deficit == 0 and opt_result.tutorial_deficit == 0
    if l_data['pending'] > 0 or t_data['pending'] > 0:
        is_eligible = opt_result.is_reachable
    
    return EligibilityResult(
        quiz_cycle=quiz_cycle,
        subject_code=subject.code,
        window_start=window['window_start'],
        window_end=window['window_end'],
        lecture_threshold=target_pct,
        combined_threshold=target_pct if t_data['tot'] > 0 else None,
        is_eligible=is_eligible,
        optimization=opt_result
    )
