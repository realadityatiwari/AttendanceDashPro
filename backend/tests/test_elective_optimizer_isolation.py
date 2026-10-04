"""Elective isolation for the Must Attend / Safe Skip inputs (DB-free).

The 2026-10 audit verified the elective path by code review only. This module
pins the PURE, DB-free layers that elective isolation rests on:

  1. ``ElectiveResolver.resolve_subject`` — a slot-scoped item resolves to the
     student's chosen concrete subject; a missing choice falls back to the
     shared anchor (never fabricated, never borrowed from another student).
  2. ``EligibilityService._bucket_window_counts`` — the (subject, window)
     attribution predicate the quiz-window optimizer's counts are built from:
     a row belongs to subject X only when the session's own subject IS X or
     the row is an elective-slot row the student resolved to X. This is where
     anchor-subject leakage and cross-student leakage would (or would not)
     happen.

Scope honesty: the SQL joins that PRODUCE the rows
(``get_subject_counts_between`` / ``get_subject_counts_between_for_subjects``
— per-user StudentElectiveChoice resolution, occurrence-outcome join) and the
elective-scoped effective-quiz-date query are DB-backed and covered by the
live-database verifiers (backend/scripts/verify_*.py) and the enrollment
invariant tests; they are deliberately NOT re-tested here.
"""

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from app.models.enums import AttendanceStatus, ClassType, ElectiveSlot
from app.services.eligibility_service import EligibilityService
from app.services.elective_resolver import ElectiveResolver

# Concrete subjects: Student A chose BCS-052 for DE-I; Student B chose BCS-055
# for DE-II. The shared schedule anchors are BCS-054 (DE-I) / BCS-058 (DE-II).
X_ID, Y_ID = uuid4(), uuid4()          # the students' chosen concrete subjects
ANCHOR_DE1_ID, ANCHOR_DE2_ID = uuid4(), uuid4()

STUDENT_A_CHOICE = {
    ElectiveSlot.ELECTIVE_I: SimpleNamespace(elective_slot=ElectiveSlot.ELECTIVE_I,
                                             subject=SimpleNamespace(id=X_ID, code="BCS-052")),
}
STUDENT_B_CHOICE = {
    ElectiveSlot.ELECTIVE_II: SimpleNamespace(elective_slot=ElectiveSlot.ELECTIVE_II,
                                              subject=SimpleNamespace(id=Y_ID, code="BCS-055")),
}
ANCHORS = {
    ElectiveSlot.ELECTIVE_I: SimpleNamespace(id=ANCHOR_DE1_ID, code="BCS-054"),
    ElectiveSlot.ELECTIVE_II: SimpleNamespace(id=ANCHOR_DE2_ID, code="BCS-058"),
}


def _row(**over):
    row = {
        "class_type": ClassType.LECTURE,
        "status": None,
        "date": date(2026, 9, 1),
        "is_cancelled": False,
        "is_deactivated": False,
        "start_time": None,
        "end_time": None,
        "outcome_type": None,
        "session_subject_id": ANCHOR_DE1_ID,   # slot session anchored on BCS-054
        "slot": ElectiveSlot.ELECTIVE_I,
        "choice_subject_id": X_ID,             # THIS student's resolution
    }
    row.update(over)
    return row


_WINDOW = {"window_start": date(2026, 8, 24), "window_end": date(2026, 9, 13)}


# ---------------------------------------------------------------------------
# resolve_subject — slot -> the student's concrete subject
# ---------------------------------------------------------------------------

def test_slot_resolves_to_students_chosen_subject():
    resolved = ElectiveResolver.resolve_subject(STUDENT_A_CHOICE, ElectiveSlot.ELECTIVE_I, ANCHORS[ElectiveSlot.ELECTIVE_I])
    assert resolved.code == "BCS-052" and resolved.id == X_ID


def test_missing_choice_falls_back_to_anchor_never_fabricated():
    # Student B has NO DE-I choice: the shared DE-I anchor is the fallback.
    resolved = ElectiveResolver.resolve_subject(STUDENT_B_CHOICE, ElectiveSlot.ELECTIVE_I, ANCHORS[ElectiveSlot.ELECTIVE_I])
    assert resolved.code == "BCS-054" and resolved.id == ANCHOR_DE1_ID


def test_non_elective_item_resolves_to_its_own_subject():
    own = SimpleNamespace(id=uuid4(), code="BCS-501")
    assert ElectiveResolver.resolve_subject(STUDENT_A_CHOICE, None, own) is own


def test_choice_is_never_borrowed_across_slots():
    # Student A chose only DE-I; a DE-II item must NOT resolve to BCS-052.
    resolved = ElectiveResolver.resolve_subject(STUDENT_A_CHOICE, ElectiveSlot.ELECTIVE_II, ANCHORS[ElectiveSlot.ELECTIVE_II])
    assert resolved.id == ANCHOR_DE2_ID


# ---------------------------------------------------------------------------
# _bucket_window_counts — the optimizer's per-(subject, window) attribution
# ---------------------------------------------------------------------------

def test_slot_session_attributed_to_chosen_subject_and_anchor_own_bucket():
    # The attribution predicate has two legitimate branches: a slot session
    # matches the student's CHOSEN subject via choice_subject_id, and it also
    # belongs to the ANCHOR subject's own bucket via session_subject_id (slot
    # sessions carry the anchor subject in the shared schedule). Leakage
    # would be a THIRD subject's bucket picking the row up.
    student_c_choice_id = uuid4()  # Student C chose BCS-053 (also DE-I)
    rows = [_row(status=AttendanceStatus.ATTENDED)]
    # Chosen subject bucket: attributed via the choice branch.
    got_a = EligibilityService._bucket_window_counts(rows, X_ID, _WINDOW)
    assert len(got_a) == 1 and got_a[0][0] == ClassType.LECTURE
    # Anchor bucket: attributed via the session's own subject (correct — it
    # IS a BCS-054 session in the schedule).
    assert len(EligibilityService._bucket_window_counts(rows, ANCHOR_DE1_ID, _WINDOW)) == 1
    # A different DE-I choice (BCS-053) and the DE-II slot never match:
    assert EligibilityService._bucket_window_counts(rows, student_c_choice_id, _WINDOW) == []
    assert EligibilityService._bucket_window_counts(rows, Y_ID, _WINDOW) == []
    assert EligibilityService._bucket_window_counts(rows, ANCHOR_DE2_ID, _WINDOW) == []


def test_anchor_own_session_not_leaked_into_choice_bucket():
    # The anchor's OWN non-slot session (e.g. an ADMIN's BCS-054 view) never
    # enters the BCS-052 student's bucket: choice_subject_id is None and the
    # session's subject is the anchor.
    rows = [_row(slot=None, choice_subject_id=None, status=AttendanceStatus.MISSED)]
    assert EligibilityService._bucket_window_counts(rows, X_ID, _WINDOW) == []
    assert len(EligibilityService._bucket_window_counts(rows, ANCHOR_DE1_ID, _WINDOW)) == 1


def test_other_students_elective_choice_does_not_leak():
    # Student B (DE-II = BCS-055) resolves the DE-II slot; their rows must not
    # appear in Student A's DE-I bucket nor in the DE-I anchor's bucket.
    rows = [_row(slot=ElectiveSlot.ELECTIVE_II, choice_subject_id=Y_ID,
                 session_subject_id=ANCHOR_DE2_ID, status=AttendanceStatus.ATTENDED)]
    assert EligibilityService._bucket_window_counts(rows, X_ID, _WINDOW) == []
    assert EligibilityService._bucket_window_counts(rows, ANCHOR_DE1_ID, _WINDOW) == []
    assert len(EligibilityService._bucket_window_counts(rows, Y_ID, _WINDOW)) == 1


def test_window_bounds_gate_attribution():
    inside = _row(date=date(2026, 9, 13), status=AttendanceStatus.ATTENDED)   # window_end inclusive
    on_quiz_day = _row(date=date(2026, 9, 14), status=AttendanceStatus.ATTENDED)  # quiz day: excluded
    before_window = _row(date=date(2026, 8, 23), status=AttendanceStatus.ATTENDED)
    rows = [before_window, inside, on_quiz_day]
    got = EligibilityService._bucket_window_counts(rows, X_ID, _WINDOW)
    assert len(got) == 1  # only the inside-window row survives


def test_cancelled_occurrence_dropped_before_counting():
    rows = [
        _row(status=AttendanceStatus.ATTENDED),
        _row(date=date(2026, 9, 2), status=None, is_cancelled=True),  # cancelled lecture: never pending/absent
    ]
    got = EligibilityService._bucket_window_counts(rows, X_ID, _WINDOW)
    assert len(got) == 1
    assert got[0][1] == AttendanceStatus.ATTENDED


def test_two_students_same_slot_session_each_count_own_resolution():
    # The SAME physical DE-I slot session, read once per student (the repo is
    # per-user): Student A's row resolves to BCS-052 via their choice row; a
    # student with NO DE-I choice produces choice_subject_id=None and sees the
    # session only through the ANCHOR bucket (its own session_subject_id).
    row_a = _row(status=AttendanceStatus.ATTENDED, choice_subject_id=X_ID)
    row_no_choice = _row(status=AttendanceStatus.MISSED, choice_subject_id=None)
    bucket_a = EligibilityService._bucket_window_counts([row_a], X_ID, _WINDOW)
    bucket_anchor = EligibilityService._bucket_window_counts([row_no_choice], ANCHOR_DE1_ID, _WINDOW)
    assert len(bucket_a) == 1 and bucket_a[0][1] == AttendanceStatus.ATTENDED
    assert len(bucket_anchor) == 1 and bucket_anchor[0][1] == AttendanceStatus.MISSED
    # A no-choice row never enters a CHOSEN subject's bucket (no choice, no
    # match), and Student A's choice row never enters the anchor's bucket
    # through the choice branch (choice_subject_id is X, not the anchor) —
    # it appears there only as the anchor's own session, never as BCS-052 data.
    assert EligibilityService._bucket_window_counts([row_no_choice], X_ID, _WINDOW) == []
