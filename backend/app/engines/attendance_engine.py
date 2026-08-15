from typing import Dict, List, Any, Optional
from app.models.enums import ClassType, AttendanceStatus
from app.schemas.attendance import SubjectAttendanceSummary, ClassCounts, OptimizationResult
import math

# Canonical attendance banding (docs/11_UI_ARCHITECTURE.md legacy pctColor /
# getSubjectStatus, reconciled in S4.1). Single definition: dashboard overall,
# analytics overall, and the per-subject summary status all consume this.
# SAFE >= target+5, WATCH >= target-15, CRITICAL below — on CURRENT (recorded-
# only) percentages. AT-RISK is NOT defined and is never emitted.
ATTENDANCE_TARGET_PCT = 75.0
WATCH_BAND_PCT = ATTENDANCE_TARGET_PCT - 15.0  # amber band lower bound
SAFE_BAND_PCT = ATTENDANCE_TARGET_PCT + 5.0    # legacy SAFE band (target + 5)


def classify_attendance_status(current_pct: Optional[float]) -> Optional[str]:
    """
    Semantic status classification (SAFE | WATCH | CRITICAL | None) for the
    student's CURRENT standing. Subjects with no recorded data return None.
    """
    if current_pct is None:
        return None
    if current_pct >= SAFE_BAND_PCT:
        return "SAFE"
    if current_pct >= WATCH_BAND_PCT:
        return "WATCH"
    return "CRITICAL"


def normalize_class_type(t: str) -> str:
    if t in ('P1', 'P2'):
        return 'P'
    if t.startswith('L_extra_'): return 'L'
    if t.startswith('T_extra_'): return 'T'
    if t.startswith('P1_extra_') or t.startswith('P2_extra_') or t.startswith('P_extra_'): return 'P'
    return t

def meets_attendance_target(lec_pct: float, tut_pct: Optional[float], target_pct: float) -> bool:
    if tut_pct is None:
        return lec_pct >= target_pct
    return ((lec_pct + tut_pct) / 2.0) >= target_pct

def optimize_attendance(
    tot_l: int, att_l: int, miss_l: int, pending_l: int,
    tot_t: int, att_t: int, miss_t: int, pending_t: int,
    target_pct: float
) -> OptimizationResult:
    
    remaining_l = pending_l
    remaining_t = pending_t
    
    if remaining_l == 0 and remaining_t == 0:
        return OptimizationResult(
            lecture_deficit=0,
            tutorial_deficit=0,
            safe_skip_lecture=0,
            safe_skip_tutorial=0,
            is_reachable=False # Technically already determined by current pct
        )
        
    valid_combos = []
    
    for l_attend in range(remaining_l + 1):
        for t_attend in range(remaining_t + 1):
            sim_att_l = att_l + l_attend
            sim_att_t = att_t + t_attend
            
            sim_lec_pct = (sim_att_l / tot_l * 100.0) if tot_l > 0 else 0.0
            
            sim_tut_pct = None
            if tot_t > 0:
                sim_tut_pct = (sim_att_t / tot_t * 100.0)
                
            if meets_attendance_target(sim_lec_pct, sim_tut_pct, target_pct):
                l_miss = remaining_l - l_attend
                t_miss = remaining_t - t_attend
                valid_combos.append({
                    "l_attend": l_attend,
                    "t_attend": t_attend,
                    "l_miss": l_miss,
                    "t_miss": t_miss,
                    "total_attend": l_attend + t_attend
                })
                
    if not valid_combos:
        # Not reachable even if they attend everything
        return OptimizationResult(
            lecture_deficit=remaining_l,
            tutorial_deficit=remaining_t,
            safe_skip_lecture=0,
            safe_skip_tutorial=0,
            is_reachable=False
        )
        
    # Sort by minimum total classes to attend, breaking ties by MINIMUM lectures attended (maximizing safe lecture skips)
    valid_combos.sort(key=lambda x: (x["total_attend"], x["l_attend"]))
    
    best = valid_combos[0]
    
    return OptimizationResult(
        lecture_deficit=best["l_attend"],
        tutorial_deficit=best["t_attend"],
        safe_skip_lecture=best["l_miss"],
        safe_skip_tutorial=best["t_miss"],
        is_reachable=True
    )

def compute_subject_stats(
    subject_code: str, 
    attendance_data: Dict[str, Any], 
    target_pct: float = 75.0
) -> SubjectAttendanceSummary:
    # A thin wrapper to map data to the schemas and calculate the percentages
    summary = SubjectAttendanceSummary(subject_code=subject_code)
    
    # In a real scenario, attendance_data is aggregated from the ClassSessions and AttendanceRecords
    counts = attendance_data.get('counts', {})
    
    l_data = counts.get('L', {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0})
    t_data = counts.get('T', {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0})
    p_data = counts.get('P', {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0})
    
    summary.lecture = ClassCounts(total=l_data['tot'], attended=l_data['att'], missed=l_data['miss'], pending=l_data['pending'])
    summary.tutorial = ClassCounts(total=t_data['tot'], attended=t_data['att'], missed=t_data['miss'], pending=t_data['pending'])
    summary.practical = ClassCounts(total=p_data['tot'], attended=p_data['att'], missed=p_data['miss'], pending=p_data['pending'])
    
    # Calculate Current % (excludes pending)
    done_l = l_data['att'] + l_data['miss']
    if done_l > 0:
        summary.current_lecture_pct = (l_data['att'] / done_l) * 100.0
        
    done_t = t_data['att'] + t_data['miss']
    if done_t > 0:
        summary.current_tutorial_pct = (t_data['att'] / done_t) * 100.0
        
    if summary.current_lecture_pct is not None:
        if summary.current_tutorial_pct is not None:
            summary.current_avg_pct = (summary.current_lecture_pct + summary.current_tutorial_pct) / 2.0
        else:
            summary.current_avg_pct = summary.current_lecture_pct
            
    # Calculate Forecast % (assumes pending are attended)
    if l_data['tot'] > 0:
        summary.forecast_lecture_pct = ((l_data['att'] + l_data['pending']) / l_data['tot']) * 100.0
    if t_data['tot'] > 0:
        summary.forecast_tutorial_pct = ((t_data['att'] + t_data['pending']) / t_data['tot']) * 100.0
        
    if summary.forecast_lecture_pct is not None:
        if summary.forecast_tutorial_pct is not None:
            summary.forecast_avg_pct = (summary.forecast_lecture_pct + summary.forecast_tutorial_pct) / 2.0
        else:
            summary.forecast_avg_pct = summary.forecast_lecture_pct

    return summary
