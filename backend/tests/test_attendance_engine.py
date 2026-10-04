"""Attendance-engine optimizer regression coverage (Safe Skip / Must Attend).

The original module was an empty placeholder ("Placeholder for Domain Parity
Tests", body ``pass``) meant to mirror the legacy JavaScript engine. That JS
engine is retired, the Python engine is canonical (owner-approved pooled L+T
model, Chunks 2-5), and consumer-level coverage lives in
``test_pooled_formula_end_to_end.py`` — so the placeholder served no purpose.
This module now carries the focused ENGINE-level invariants the 2026-10
Safe Skip / Must Attend audit identified as unpinned:

  - fractional-threshold boundaries (74.99 / 75.00 / 75.01 and exact-count
    equivalents): decisions are exact-count based and must never agree or
    disagree because of a ROUNDED displayed percentage;
  - the documented L/T tie-break (minimum total attendance first, then
    fewest lectures attended) under forced splits;
  - the audit's hand-derived boundary cases (skip-N-safe vs skip-(N+1)-unsafe,
    the at-threshold dilution case, unreachable states);
  - structural invariants: must + skip == pending per type when reachable,
    deficits never exceed pending, skips never negative, unreachable =>
    zero skips + full-pending deficits, zero-pending reachability == current
    pooled meets target.

Every expected value below is hand-derived (see the audit report); none is
copied from engine output. The optimizer mathematics itself is verified
correct and MUST NOT be changed to satisfy these tests — they pin it.
"""

import pytest

from app.engines.attendance_engine import (
    meets_attendance_target,
    optimize_attendance,
    pooled_pct,
)


def opt(tot_l, att_l, miss_l, pend_l, tot_t, att_t, miss_t, pend_t, target=75.0):
    r = optimize_attendance(tot_l, att_l, miss_l, pend_l, tot_t, att_t, miss_t, pend_t, target)
    return (r.lecture_deficit, r.tutorial_deficit, r.safe_skip_lecture, r.safe_skip_tutorial, r.is_reachable)


# ---------------------------------------------------------------------------
# Fractional threshold boundaries — exact counts, never rounded display %
# ---------------------------------------------------------------------------

def test_pooled_exactly_75_passes_74_99_and_75_but_not_75_01():
    # 9/12 = exactly 75.0 (dyadic: exact in binary floating point).
    assert pooled_pct(9, 12, 0, 0) == pytest.approx(75.0)
    assert meets_attendance_target(9, 12, 0, 0, 74.99) is True
    assert meets_attendance_target(9, 12, 0, 0, 75.0) is True
    assert meets_attendance_target(9, 12, 0, 0, 75.01) is False


def test_decision_is_count_based_not_display_rounded():
    # 2999/4000 = 74.975% and 3001/4000 = 75.025% BOTH display as "75.0%"
    # at one decimal, yet the exact-count decisions must differ.
    below = pooled_pct(2999, 4000, 0, 0)
    above = pooled_pct(3001, 4000, 0, 0)
    assert round(below, 1) == round(above, 1) == 75.0  # indistinguishable when displayed
    assert meets_attendance_target(2999, 4000, 0, 0, 75.0) is False
    assert meets_attendance_target(3001, 4000, 0, 0, 75.0) is True


def test_optimizer_flips_on_hundredth_of_a_percent():
    # tot 40 (att 6 / miss 4 / pend 30), L-only. Required additional attendances:
    #   74.99% -> 0.7499*40 - 6 = 23.996 -> ceil 24
    #   75.00% -> 30 - 6                 = 24     -> 24
    #   75.01% -> 0.7501*40 - 6 = 24.004 -> ceil 25
    assert opt(40, 6, 4, 30, 0, 0, 0, 0, 74.99) == (24, 0, 6, 0, True)
    assert opt(40, 6, 4, 30, 0, 0, 0, 0, 75.0) == (24, 0, 6, 0, True)
    assert opt(40, 6, 4, 30, 0, 0, 0, 0, 75.01) == (25, 0, 5, 0, True)


def test_quiz_i_70_percent_boundary_is_exact():
    # True 70% rationals (non-dyadic) must still pass >= 70: 7/10, 21/30.
    for att, tot in ((7, 10), (21, 30), (35, 50)):
        assert pooled_pct(att, tot, 0, 0) == pytest.approx(70.0)
        assert meets_attendance_target(att, tot, 0, 0, 70.0) is True
        assert meets_attendance_target(att, tot, 0, 0, 70.01) is False
        assert meets_attendance_target(att, tot, 0, 0, 69.99) is True


# ---------------------------------------------------------------------------
# L/T forced split — the documented tie-break (fewest lectures attended)
# ---------------------------------------------------------------------------

def test_tie_break_attends_tutorials_before_lectures():
    # Zero history, 4 pending lectures + 4 pending tutorials, 75%:
    # (a + b)/8 >= 0.75 -> a + b >= 6; the tie-break minimizes lectures
    # attended, so a = 2, b = 4 (lecture skips maximized).
    # This is the DOCUMENTED behavior (attendance_engine docstring +
    # docs/06_ATTENDANCE_ENGINE.md) — pinned here, not changed.
    assert opt(4, 0, 0, 4, 4, 0, 0, 4) == (2, 4, 2, 0, True)


def test_forced_all_tutorial_split():
    # No lectures pending; 5 pending tutorials from zero: b/5 >= 0.75 -> b >= 4.
    assert opt(0, 0, 0, 0, 5, 0, 0, 5) == (0, 4, 0, 1, True)


def test_forced_all_lecture_split():
    # No tutorials pending; 5 pending lectures from zero: a/5 >= 0.75 -> a >= 4.
    assert opt(5, 0, 0, 5, 0, 0, 0, 0) == (4, 0, 1, 0, True)


# ---------------------------------------------------------------------------
# Hand-derived audit boundary cases
# ---------------------------------------------------------------------------

def test_audit_hand_case_skip_boundary_8_of_10_plus_6():
    # 8/10 attended (80% now), 6 pending, 75%: (8 + a)/16 >= 0.75 -> a >= 4.
    # Must attend 4, safe skip 2. Skipping 2 ends at 12/16 = 75% (safe);
    # skipping 3 ends at 11/16 = 68.75% (unsafe).
    assert opt(16, 8, 2, 6, 0, 0, 0, 0) == (4, 0, 2, 0, True)
    assert meets_attendance_target(12, 16, 0, 0, 75.0) is True   # skip 2
    assert meets_attendance_target(11, 16, 0, 0, 75.0) is False  # skip 3


def test_at_threshold_must_attend_all_pending_dilution():
    # 12/16 = exactly 75% now, 3 pending: pending dilutes the denominator, so
    # the student must attend ALL of them (12+3)/19 = 78.95%; attending 2 gives
    # 14/19 = 73.68%. Safe skip is ZERO even though the student is at target.
    assert opt(19, 12, 4, 3, 0, 0, 0, 0) == (3, 0, 0, 0, True)


def test_unrecoverable_state_returns_full_pending_deficits_and_zero_skips():
    # 4/10 (40%), 2 pending, 75%: best possible (4+2)/12 = 50% < 75%.
    assert opt(12, 4, 6, 2, 0, 0, 0, 0) == (2, 0, 0, 0, False)
    # 1/8 attended, 2 pending, 70%: best possible 3/10 = 30% < 70%.
    assert opt(10, 1, 7, 2, 0, 0, 0, 0, 70.0) == (2, 0, 0, 0, False)


def test_zero_pending_reachable_iff_current_pooled_meets_target():
    assert opt(12, 9, 3, 0, 0, 0, 0, 0) == (0, 0, 0, 0, True)    # 9/12 = 75
    assert opt(12, 8, 4, 0, 0, 0, 0, 0) == (0, 0, 0, 0, False)   # 8/12 = 66.7
    # Zero pending AND zero total: nothing recorded, nothing schedulable.
    assert opt(0, 0, 0, 0, 0, 0, 0, 0) == (0, 0, 0, 0, False)


def test_one_future_session_at_80_percent_still_requires_attendance():
    # 8/10 (80% now), 1 pending, 75%: 8/11 = 72.7% < 75% -> must attend it.
    assert opt(11, 8, 2, 1, 0, 0, 0, 0) == (1, 0, 0, 0, True)


# ---------------------------------------------------------------------------
# Structural invariants over a deterministic state grid
# ---------------------------------------------------------------------------

def test_optimizer_invariants_hold_across_state_grid():
    for tot_l in range(0, 9):
        for miss_l in range(0, tot_l + 1):
            att_l = tot_l - miss_l
            for pend_l in range(0, 5):
                for target in (70.0, 75.0):
                    ld, td, sl, st, reachable = opt(
                        tot_l, att_l, miss_l, pend_l, 0, 0, 0, 0, target
                    )
                    # Per type: must + skip == pending.
                    assert ld + sl == pend_l
                    assert td + st == 0  # no tutorials in this grid
                    # Never negative, never beyond pending.
                    assert min(ld, td, sl, st) >= 0
                    assert ld <= pend_l and sl <= pend_l
                    if not reachable:
                        # unreachable: full-pending deficits, zero skips
                        assert (ld, td) == (pend_l, 0)
                        assert (sl, st) == (0, 0)


def test_optimizer_invariants_hold_mixed_l_and_t():
    for tot in range(1, 9):
        for att in range(0, tot + 1):
            miss = tot - att
            for pend in range(0, 5):
                ld, td, sl, st, reachable = opt(
                    tot, att, miss, pend, tot, att, miss, pend, 75.0
                )
                assert ld + sl == pend and td + st == pend
                assert min(ld, td, sl, st) >= 0
                assert ld + td <= 2 * pend
                if not reachable:
                    assert (sl, st) == (0, 0)
                    assert ld + td == 2 * pend
