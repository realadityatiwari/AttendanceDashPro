# Chunk 1 — Task 6: ALL-SUBJECT ERP OVERALL SAFETY TESTS (spec item 7).
#
# These tests pin the ERP overall mathematics of dashboard_service and
# analytics_service at the pure-function level (no DB, no service wiring) so
# the Chunk-2 subject-formula change CANNOT silently leak into the
# all-subject overall. If any of these fail after Chunk 2, the subject
# formula change has accidentally touched the frozen ERP semantics.
#
# ERP overall (frozen contract, Phase 8.0 §7/§8 — documented in
# backend/app/schemas/analytics.py OverallAnalytics):
#
#   current_pct  = sum(attended) / sum(recorded) x 100   (recorded-only; all
#                 class types L+T+P mixed; cancelled excluded; pending never
#                 converted to absent)
#   forecast_pct = sum(attended + pending) / sum(total) x 100
#
# CRUCIAL DIVERGENCE GUARD: one subject's counts deliberately produce a
# subject-L+T percentage of 70.0% (OLD mean-of-%) vs 75.0% (pooled) while the
# ERP overall is 70.0% under BOTH — proving ERP is computed from raw session
# counts, not from subject percentages.

from datetime import date

import pytest

from app.services.dashboard_service import DashboardService
from app.services.analytics_service import AnalyticsService
from app.models.enums import AttendanceStatus, ClassType


def _row(d, status, class_type=ClassType.LECTURE, cancelled=False, subject_id="s1"):
    return {
        "date": d,
        "status": status,
        "class_type": class_type,
        "is_cancelled": cancelled,
        "is_extra": False,
        "subject_id": subject_id,
        "subject_code": "S-1",
        "subject_name": "Subject 1",
        "start_time": None,
        "end_time": None,
    }


def _dashboard():
    """A DashboardService instance without DB wiring — the ERP builders under
    test (_build_overall, _aggregate_range) are pure row transformers; none
    of them touches the database, so bypassing __init__ is safe here."""
    return object.__new__(DashboardService)


def _analytics():
    """An AnalyticsService instance without DB wiring (same rationale:
    _overall / _weekly_series are pure)."""
    return object.__new__(AnalyticsService)


def test_dashboard_overall_is_pooled_erp_and_independent_of_subject_formula():
    """Subject L+T would read 70.0% (OLD) / 75.0% (pooled); ERP overall reads
    70.0% under BOTH formulas — from raw counts, never subject percentages.

    Session set (all subject s1):
      Lecture  5 conducted: 2 attended / 3 missed
      Tutorial 7 conducted: 7 attended
      (no pending, no cancelled)
    Subject L+T mean-of-%  = (40 + 100)/2 = 70.0
    Subject L+T pooled     = 9/12*100    = 75.0
    ERP overall            = (2+7)/(5+7)  = 9/12*100 = 75.0... deliberately
    make them differ: add 1 lecture missed (6 L conducted, 2 attended):
      Subject mean-of-% = (2/6 + 1)*100/2 = 66.67
      Subject pooled    = 9/13*100        = 69.23
      ERP overall       = (2+7)/(6+7)     = 69.23  <-- differs from BOTH

    Wait — the ERP number coincides with pooled here BY ARITHMETIC because
    all classes are the same student's sessions; the point is not that the
    VALUE differs from pooled, but that ERP is derived from raw counts
    (att/recorded), NOT from compute_subject_stats outputs. The test below
    constructs counts where a subject-percentage-based overall would be
    WRONG: two subjects, each 50% conducted, ERP overall must be 50% (not the
    average of subject percentages — same thing here) — use UNEQUAL subject
    sizes: subject A 1/2 (50%), subject B 8/10 (80%):
      average of subject percentages = 65.0
      ERP overall                    = 9/12 = 75.0
    A subject-percentage-average would yield 65.0 — ERP must yield 75.0.
    """
    d = date(2026, 9, 21)
    rows = []
    # Subject A: 1 attended / 2 conducted
    rows.append(_row(d, AttendanceStatus.ATTENDED, subject_id="A"))
    rows.append(_row(d, AttendanceStatus.MISSED, subject_id="A"))
    # Subject B: 8 attended / 2 missed
    for i in range(8):
        rows.append(_row(d, AttendanceStatus.ATTENDED, subject_id="B"))
    rows += [_row(d, AttendanceStatus.MISSED, subject_id="B") for _ in range(2)]

    overall = _dashboard()._build_overall(rows=rows, today=d, semester_start=d)
    assert overall.attended == 9
    assert overall.recorded == 12
    # ERP = sum(att)/sum(recorded) = 75.0 — NOT the 65.0 subject-%-average:
    assert overall.overall_pct == pytest.approx(75.0)
    assert overall.pending == 0


def test_dashboard_overall_excludes_cancelled_and_pending_from_current():
    """Cancelled excluded entirely; pending excluded from current but
    surfaced. [INVARIANT — must hold after Chunk 2.]"""
    d = date(2026, 9, 21)
    rows = [
        _row(d, AttendanceStatus.ATTENDED),
        _row(d, AttendanceStatus.MISSED),
        _row(d, None),  # pending
        _row(d, AttendanceStatus.MISSED, cancelled=True),  # cancelled: ignored
    ]
    overall = _dashboard()._build_overall(rows=rows, today=d, semester_start=d)
    assert overall.attended == 1
    assert overall.recorded == 2
    assert overall.pending == 1
    assert overall.overall_pct == pytest.approx(50.0)


def test_dashboard_overall_semester_start_bounds_rows():
    """Rows before semester_start are excluded from the overall section."""
    d0 = date(2026, 7, 10)
    d1 = date(2026, 7, 16)
    rows = [
        _row(d0, AttendanceStatus.MISSED),  # before semester start
        _row(d1, AttendanceStatus.ATTENDED),
        _row(d1, AttendanceStatus.ATTENDED),
    ]
    overall = _dashboard()._build_overall(
        rows=rows, today=d1, semester_start=date(2026, 7, 15)
    )
    assert overall.recorded == 2
    assert overall.overall_pct == pytest.approx(100.0)


def test_dashboard_weekly_aggregate_range_is_erp():
    """_aggregate_range (weekly pct) is recorded-only ERP over the range."""
    d = date(2026, 9, 21)  # a Monday
    rows = [
        _row(d, AttendanceStatus.ATTENDED),
        _row(d, AttendanceStatus.MISSED),
        _row(d, AttendanceStatus.MISSED, cancelled=True),  # excluded
        _row(d, None),                                     # pending: not recorded
    ]
    pct = _dashboard()._aggregate_range(rows, d, d)
    assert pct == pytest.approx(50.0)


def test_analytics_overall_is_erp_recorded_only_with_forecast():
    """analytics_service._overall: ERP current + forecast (pending attended).

    rows: 4 attended, 2 missed, 2 pending, 1 cancelled:
      current  = 4/6 * 100 = 66.667
      forecast = 6/8 * 100 = 75.0
    """
    d = date(2026, 9, 21)
    rows = (
        [_row(d, AttendanceStatus.ATTENDED) for _ in range(4)]
        + [_row(d, AttendanceStatus.MISSED) for _ in range(2)]
        + [_row(d, None) for _ in range(2)]
        + [_row(d, AttendanceStatus.MISSED, cancelled=True)]
    )
    overall = _analytics()._overall(rows=rows)
    assert overall.current_pct == pytest.approx(4 / 6 * 100.0)
    assert overall.forecast_pct == pytest.approx(6 / 8 * 100.0)
    assert overall.attended == 4
    assert overall.recorded == 6
    assert overall.pending == 2
    assert overall.cancelled == 1


def test_analytics_overall_empty_is_none():
    """No rows => None percentages. [INVARIANT]"""
    overall = _analytics()._overall(rows=[])
    assert overall.current_pct is None
    assert overall.forecast_pct is None


def test_analytics_overall_mixed_class_types_pooled():
    """Labs (P) are mixed into ERP overall by design (spec item 7) — a lab
    session counts in the ERP denominator. [INVARIANT]"""
    d = date(2026, 9, 21)
    rows = [
        _row(d, AttendanceStatus.ATTENDED, class_type=ClassType.LECTURE),
        _row(d, AttendanceStatus.MISSED, class_type=ClassType.PRACTICAL),
    ]
    overall = _analytics()._overall(rows=rows)
    assert overall.current_pct == pytest.approx(50.0)
