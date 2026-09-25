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

# Attendance Health (Phase 8.2 product decision, supersedes the legacy
# SAFE/WATCH/CRITICAL presentation on the Attendance surface). This is the
# canonical, backend-owned 4-state classification for a subject's OVERALL
# attendance (the combined average for theory, practical % for labs):
#
#     HEALTHY   >= 75%
#     WATCH      65% .. < 75%
#     AT_RISK    60% .. < 65%
#     CRITICAL  < 60%
#
# Thresholds are documented in docs/phase_8_2_implementation_report.md and
# chosen per the product requirement (75% academic target; AT_RISK band
# between the watch floor and the target). The legacy `classify_attendance_status`
# (SAFE/WATCH/CRITICAL) remains untouched for the frozen dashboard/analytics
# surfaces; Attendance Health is a separate presentation concept emitted
# additively on SubjectAttendanceSummary and never computed in React.
ATTENDANCE_HEALTH_HEALTHY_PCT = 75.0   # HEALTHY floor
ATTENDANCE_HEALTH_WATCH_PCT = 65.0     # WATCH floor
ATTENDANCE_HEALTH_AT_RISK_PCT = 60.0   # AT_RISK floor


def classify_attendance_health(current_pct: Optional[float]) -> Optional[str]:
    """
    Attendance Health classification (HEALTHY | WATCH | AT_RISK | CRITICAL |
    None) for a subject's OVERALL attendance, on CURRENT (recorded-only)
    percentages. None when nothing has been recorded.
    """
    if current_pct is None:
        return None
    if current_pct >= ATTENDANCE_HEALTH_HEALTHY_PCT:
        return "HEALTHY"
    if current_pct >= ATTENDANCE_HEALTH_WATCH_PCT:
        return "WATCH"
    if current_pct >= ATTENDANCE_HEALTH_AT_RISK_PCT:
        return "AT_RISK"
    return "CRITICAL"


def classify_attendance_status(current_pct: Optional[float]) -> Optional[str]:
    """
    Legacy semantic status classification (SAFE | WATCH | CRITICAL | None) for
    the student's CURRENT standing (frozen dashboard/analytics banding).
    Subjects with no recorded data return None.
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

def pooled_pct(att_l: int, tot_l: int, att_t: int, tot_t: int) -> Optional[float]:
    """
    Canonical pooled L+T percentage — THE single implementation of the
    owner-approved aggregation (Chunks 3-5):

        (att_l + att_t)
        --------------- x 100        (None when tot_l + tot_t == 0)
        (tot_l + tot_t)

    Count-level pooling — NEVER the arithmetic mean of the two per-type
    percentages (the legacy formula). Full precision; no rounding.

    The helper only aggregates; each caller supplies counts with its own
    (unchanged) engine semantics:
      - subject current / optimizer: `tot_*` are the FINAL conducted totals
        (conducted + pending — tot = att + miss + pending by the canonical
        count contract), so the current and candidate scenarios share this
        denominator;
      - subject FORECAST: `att_*` is passed with pending added (pending
        treated as attended);
      - eligibility criterion / best case: `tot_*` include pending
        (eligibility count semantics untouched).

    A missing class type contributes nothing (zero to both sides): a
    lecture-only subject collapses to the lecture percentage and a
    tutorial-only subject to the tutorial percentage, with no special-casing.
    Practical (P) counts are never passed here. Zero total => None
    (established null/undefined semantics).
    """
    final_total = tot_l + tot_t
    if final_total <= 0:
        return None
    return ((att_l + att_t) / final_total) * 100.0


def meets_attendance_target(
    att_l: int, tot_l: int, att_t: int, tot_t: int, target_pct: float
) -> bool:
    """
    Canonical optimizer predicate (CHUNK 3) — is the POOLED L+T attendance at
    or above the target?

        (L_attended + T_attended)
        ------------------------- x 100 >= target
        (L_total    + T_total)

    Delegates to the single pooled implementation (`pooled_pct`, consolidated
    in Chunk 5) — the arithmetic is unchanged and is never an average of
    percentages. `tot_l` / `tot_t` are the FINAL conducted totals for the
    type (conducted + pending; tot = att + miss + pending by the canonical
    count contract), i.e. the optimizer's established final-total
    denominator — pending semantics unchanged. A missing class type
    contributes nothing; a window with no classes at all can never meet a
    positive target (zero denominator -> False). Full precision — no rounding
    before the comparison.
    """
    pct = pooled_pct(att_l, tot_l, att_t, tot_t)
    return pct is not None and pct >= target_pct

def optimize_attendance(
    tot_l: int, att_l: int, miss_l: int, pending_l: int,
    tot_t: int, att_t: int, miss_t: int, pending_t: int,
    target_pct: float
) -> OptimizationResult:
    """
    Must-attend / safe-skip / reachability optimizer under the POOLED L+T
    constraint (CHUNK 3).

    A candidate attends `l_attend` of the pending lectures and `t_attend` of
    the pending tutorials; its final pooled attendance is

        (att_l + l_attend + att_t + t_attend)
        --------------------------------------- x 100 >= target
        (tot_l + tot_t)

    where the denominator is the FINAL conducted total. Every pending class
    becomes attended or missed (tot = att + miss + pending by the canonical
    count contract), so the denominator is candidate-invariant — the same
    established pending model the optimizer has always used.
    [OLD] predicate: ((att_l + l)/tot_l*100 + (att_t + t)/tot_t*100) / 2.

    - Must Attend: the valid combination with the FEWEST total classes to
      attend (exhaustive enumeration — the established architecture).
    - Safe Skip: pending minus the chosen attendance (l_miss / t_miss) under
      the SAME single pooled constraint — never two independent per-type
      percentages.
    - Reachability: whether any valid combination exists at all; with zero
      pending this reduces to "the CURRENT pooled attendance already meets
      the target".
    - Tie-breaking (preserved): minimum total attendance first, then MINIMUM
      lectures attended (maximising safe lecture skips).
    """
    remaining_l = pending_l
    remaining_t = pending_t
    
    if remaining_l == 0 and remaining_t == 0:
        # Nothing left to attend: the target is trivially reachable (with
        # zero additional attendance) when the CURRENT pooled attendance
        # already meets it; otherwise it can never be reached. Pending is
        # zero, so tot == conducted and this is exactly the Chunk 2
        # subject-current pooled percentage.
        # [CHUNK 3] OLD: mean of the current lecture % and tutorial %.
        return OptimizationResult(
            lecture_deficit=0,
            tutorial_deficit=0,
            safe_skip_lecture=0,
            safe_skip_tutorial=0,
            is_reachable=meets_attendance_target(att_l, tot_l, att_t, tot_t, target_pct)
        )
        
    valid_combos = []
    
    for l_attend in range(remaining_l + 1):
        for t_attend in range(remaining_t + 1):
            sim_att_l = att_l + l_attend
            sim_att_t = att_t + t_attend

            # [CHUNK 3] Pooled L+T predicate. The denominator is the FINAL
            # conducted total and is candidate-invariant: every pending class
            # becomes attended or missed under every scenario, so
            # tot_l + tot_t is the total after the remaining classes are
            # resolved. [OLD] mean of the two per-type percentages:
            #   ((sim_att_l/tot_l*100) + (sim_att_t/tot_t*100)) / 2
            if meets_attendance_target(sim_att_l, tot_l, sim_att_t, tot_t, target_pct):
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
        
    # Canonical CURRENT subject attendance (owner-approved pooled L+T formula):
    #
    #     (L_present + T_present) / (L_conducted + T_conducted) x 100
    #
    # where Conducted = Present + Missed per type (pending excluded from the
    # current denominator). This is count-level arithmetic on the raw counts —
    # NEVER an average of the per-type percentages above (they coincide only
    # when L_conducted == T_conducted or L% == T%). Practical counts never
    # enter this denominator (P stays its own bucket). Zero total conducted =>
    # None (existing schema semantics: no recorded attendance, no percentage).
    # A missing class type contributes nothing — no artificial zeroes.
    done_total = done_l + done_t
    if done_total > 0:
        summary.current_avg_pct = (
            (l_data['att'] + t_data['att']) / done_total
        ) * 100.0
        
    # Calculate Forecast % (assumes pending are attended)
    if l_data['tot'] > 0:
        summary.forecast_lecture_pct = ((l_data['att'] + l_data['pending']) / l_data['tot']) * 100.0
    if t_data['tot'] > 0:
        summary.forecast_tutorial_pct = ((t_data['att'] + t_data['pending']) / t_data['tot']) * 100.0
        
    # Canonical FORECAST combined percentage (Chunk 5, owner-approved):
    # pending classes are treated as attended and L+T are POOLED at count
    # level — never the mean of the two forecast percentages:
    #
    #     (L_att + L_pending + T_att + T_pending)
    #     --------------------------------------- x 100
    #     (L_total + T_total)
    #
    # The per-type forecast percentages above stay individual (unchanged).
    # A missing type contributes nothing; practical P never enters this
    # denominator; zero combined total => None (established null semantics).
    # [OLD] (forecast_lecture_pct + forecast_tutorial_pct) / 2.0.
    summary.forecast_avg_pct = pooled_pct(
        l_data['att'] + l_data['pending'], l_data['tot'],
        t_data['att'] + t_data['pending'], t_data['tot'],
    )

    return summary
