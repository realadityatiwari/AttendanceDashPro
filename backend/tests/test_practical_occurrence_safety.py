# Chunk 1 — Task 7: PRACTICAL/LAB SAFETY TESTS (spec item 6).
#
# Purpose: guarantee the Chunk-2 L+T formula change can never accidentally
# pull practical attendance into subject attendance or quiz eligibility.
#
# Pinned here (all INVARIANT — must hold before AND after the change):
#   - contiguous same-subject PRACTICAL periods collapse into ONE occurrence
#     (one lab = one attendance decision, counted once in every denominator);
#   - a recorded lab block is counted by its record status (record-wins);
#   - a record-less cancelled lab block is dropped (never absent/pending);
#   - a cancelled LECTURE/TUTORIAL is ALWAYS dropped, even with a stale mark
#     (cancellation propagates over class reality);
#   - the eligibility count builder (_build_counts) keeps ONLY L and T —
#     practical rows are structurally excluded from quiz eligibility.

from datetime import date, time

import pytest

from app.engines.practical_occurrence import (
    collapse_count_rows,
    group_practical_occurrences,
    occurrence_is_cancelled,
)
from app.models.enums import AttendanceStatus, ClassType
from app.services.eligibility_service import EligibilityService


def _p_row(**overrides):
    row = {
        "subject_id": "S-1",
        "subject_code": "BCS-551",
        "class_type": ClassType.PRACTICAL,
        "status": None,
        "date": date(2026, 9, 21),
        "is_cancelled": False,
        "is_extra": False,
        "start_time": time(13, 0),
        "end_time": time(14, 0),
        "id": "sess-1",
        "designation": None,
    }
    row.update(overrides)
    return row


def test_contiguous_practical_periods_collapse_to_one_occurrence():
    """A 13:00-14:00 + 14:00-15:00 lab block is ONE occurrence. [INVARIANT]"""
    rows = [
        _p_row(id="a", start_time=time(13, 0), end_time=time(14, 0)),
        _p_row(id="b", start_time=time(14, 0), end_time=time(15, 0)),
    ]
    occ = group_practical_occurrences(rows)
    assert len(occ) == 1
    assert occ[0]["member_ids"] == ["a", "b"]
    assert occ[0]["start_time"] == time(13, 0)
    assert occ[0]["end_time"] == time(15, 0)


def test_non_contiguous_practicals_stay_separate():
    """A gap (13-14 then 15-16) means two separate lab occurrences. [INVARIANT]"""
    rows = [
        _p_row(id="a", start_time=time(13, 0), end_time=time(14, 0)),
        _p_row(id="b", start_time=time(15, 0), end_time=time(16, 0)),
    ]
    assert len(group_practical_occurrences(rows)) == 2


def test_recorded_lab_block_counts_once_with_record_status():
    """Record-wins: a block with ANY member record counts once with its block
    status — ATTENDED takes precedence over MISSED (block status precedence).
    The counting projection therefore emits ONE row, not one per period.
    [INVARIANT]"""
    rows = [
        _p_row(id="a", start_time=time(13, 0), end_time=time(14, 0), status=AttendanceStatus.MISSED),
        _p_row(id="b", start_time=time(14, 0), end_time=time(15, 0), status=AttendanceStatus.ATTENDED),
    ]
    counted = collapse_count_rows(rows)
    assert len(counted) == 1
    assert counted[0] == (ClassType.PRACTICAL, AttendanceStatus.ATTENDED)


def test_recorded_lab_block_missed_only_counts_once_as_missed():
    """A block with only MISSED records is ONE MISSED occurrence (one lab =
    one decision, one denominator unit). [INVARIANT]"""
    rows = [
        _p_row(id="a", start_time=time(13, 0), end_time=time(14, 0), status=AttendanceStatus.MISSED),
        _p_row(id="b", start_time=time(14, 0), end_time=time(15, 0), status=AttendanceStatus.MISSED),
    ]
    counted = collapse_count_rows(rows)
    assert counted == [(ClassType.PRACTICAL, AttendanceStatus.MISSED)]


def test_cancelled_lab_without_records_is_dropped():
    """A record-less cancelled lab never becomes absent/pending. [INVARIANT]"""
    rows = [
        _p_row(id="a", is_cancelled=True),
        _p_row(id="b", is_cancelled=True),
    ]
    assert collapse_count_rows(rows) == []


def test_cancelled_lecture_with_stale_mark_is_dropped():
    """A cancelled LECTURE is ALWAYS dropped — even with a stale MISSED mark
    (CLASS_CANCELLED propagates over class reality). [INVARIANT]"""
    rows = [
        {
            "subject_id": "S-1", "subject_code": "BCS-501",
            "class_type": ClassType.LECTURE,
            "status": AttendanceStatus.MISSED,
            "date": date(2026, 9, 21), "is_cancelled": True, "is_extra": False,
            "start_time": time(9, 0), "end_time": time(10, 0), "id": "x",
            "designation": None,
        }
    ]
    assert collapse_count_rows(rows) == []
    assert occurrence_is_cancelled(rows[0]) is True


def test_attended_lab_block_survives_member_cancellation():
    """A recorded lab block keeps its record status even if a different
    member was later cancelled (frozen record-wins contract). [INVARIANT]"""
    rows = [
        _p_row(id="a", status=AttendanceStatus.ATTENDED),
        _p_row(id="b", is_cancelled=True),
    ]
    counted = collapse_count_rows(rows)
    assert counted == [(ClassType.PRACTICAL, AttendanceStatus.ATTENDED)]


def test_eligibility_count_builder_excludes_practicals_structurally():
    """The eligibility count builder keeps ONLY L and T — practical rows
    (including the P1/P2 raw variants) in the raw input are ignored entirely,
    so quiz eligibility can never see lab attendance regardless of the
    formula used above it.

    SEMANTIC NOTE (pinned): _build_counts expects rows shaped
    (class_type_enum, status) — it reads `.value` off the class type and
    normalizes P1/P2/extras into P before dropping them. Any non-ATTENDED/
    MISSED status (incl. None) counts as pending. [INVARIANT]"""
    from app.models.enums import AttendanceStatus as AS

    raw = [
        (ClassType.LECTURE, AS.ATTENDED),
        (ClassType.LECTURE, AS.MISSED),
        (ClassType.TUTORIAL, AS.ATTENDED),
        (ClassType.PRACTICAL, AS.ATTENDED),   # must be dropped
        (ClassType.PRACTICAL, AS.MISSED),     # dropped
        (ClassType.LECTURE, None),            # pending lecture kept
    ]
    counts = EligibilityService._build_counts(raw)
    assert set(counts.keys()) == {"L", "T"}
    assert counts["L"] == {"tot": 3, "att": 1, "miss": 1, "pending": 1}
    assert counts["T"] == {"tot": 1, "att": 1, "miss": 0, "pending": 0}


def test_eligibility_count_builder_normalizes_p1_p2_out_of_l_t():
    """P1/P2 raw slot variants normalize to P and are dropped from the
    eligibility L/T buckets (defense-in-depth against the formula change
    ever reaching lab rows). [INVARIANT]"""
    from app.models.enums import AttendanceStatus as AS
    from app.models.enums import ClassType as CT

    class _P1:  # minimal str-enum stand-in exposing .value
        value = "P1"

    class _P2:
        value = "P2"

    class _L:
        value = "L"

    counts = EligibilityService._build_counts(
        [(_L(), AS.ATTENDED), (_P1(), AS.ATTENDED), (_P2(), AS.MISSED)]
    )
    assert counts["L"] == {"tot": 1, "att": 1, "miss": 0, "pending": 0}
    assert counts["T"] == {"tot": 0, "att": 0, "miss": 0, "pending": 0}
