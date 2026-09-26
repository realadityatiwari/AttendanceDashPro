"""Chunk 16 — centralized new-student enrollment invariant (DB-free).

The single invariant under test (EnrollmentService.plan_new_student_enrollments):

    effective enrollment =
        non-elective subjects (subjects.elective_slot IS NULL, COMPULSORY)
        UNION
        the StudentElectiveChoice-resolved selected subject for each
        configured elective slot (ELECTIVE)

An unselected elective must NEVER appear in the plan. ElectiveResolver is the
only resolution authority (choice first, anchor fallback second, never
fabricated); EnrollmentType is asserted explicit — no elective subject may
fall through to the model's COMPULSORY default, and every non-elective
subject must be COMPULSORY.

CASE A (the tracked-student pattern): I=BCS-054, II=BCS-058 — the plan must
contain exactly BCS-054 + BCS-058 and none of BCS-052/053/055/056.
CASE B (the inverse selection): I=BCS-052, II=BCS-055 — exactly BCS-052 +
BCS-055 and none of BCS-053/054/056/058.

Also covered: mandatory subjects always present, one ELECTIVE per configured
slot, unresolvable selection => atomic rejection (no partial elective set),
empty catalog => empty plan, and the admin-side single-row builder typing.
No database is touched (existing tests/verifiers that DO touch the dev DB are
unaffected; see chunk report for the immutability proof).
"""
from types import SimpleNamespace

import pytest

from app.models.enums import ElectiveSlot, EnrollmentType
from app.services.enrollment_service import (
    apply_new_student_enrollments,
    build_enrollment,
    build_choice_rows,
    configured_elective_slots,
    plan_new_student_enrollments,
)


# ---- fixture catalog (mirrors the canonical semester shape) -----------------

def _subject(code, slot=None):
    return SimpleNamespace(id=code, code=code, elective_slot=slot)


MANDATORY = ["BNC-501", "BCS-501", "BCS-502", "BCS-503", "BCS-551", "BCS-552", "BCS-553"]
POOL_I = ["BCS-052", "BCS-053", "BCS-054"]
POOL_II = ["BCS-055", "BCS-056", "BCS-058"]


def _catalog():
    subjects = [_subject(c) for c in MANDATORY]
    subjects += [_subject(c, ElectiveSlot.ELECTIVE_I) for c in POOL_I]
    subjects += [_subject(c, ElectiveSlot.ELECTIVE_II) for c in POOL_II]
    return subjects


BY_CODE = {s.code: s for s in _catalog()}
ANCHORS = {
    ElectiveSlot.ELECTIVE_I: BY_CODE["BCS-054"],
    ElectiveSlot.ELECTIVE_II: BY_CODE["BCS-058"],
}


def _choices(i_code, ii_code):
    return {
        ElectiveSlot.ELECTIVE_I: SimpleNamespace(
            elective_slot=ElectiveSlot.ELECTIVE_I, subject=BY_CODE[i_code]),
        ElectiveSlot.ELECTIVE_II: SimpleNamespace(
            elective_slot=ElectiveSlot.ELECTIVE_II, subject=BY_CODE[ii_code]),
    }


def _plan_codes(specs, enrollment_type):
    return sorted(s.code for s, t in specs if t == enrollment_type)


# ---- CASE A / CASE B --------------------------------------------------------

def test_case_a_selected_054_058():
    specs, missing = plan_new_student_enrollments(_catalog(), _choices("BCS-054", "BCS-058"))
    assert missing == []
    assert _plan_codes(specs, EnrollmentType.ELECTIVE) == ["BCS-054", "BCS-058"]
    elective_codes = set(_plan_codes(specs, EnrollmentType.ELECTIVE))
    assert not elective_codes & {"BCS-052", "BCS-053", "BCS-055", "BCS-056"}
    # every mandatory subject enrolled, all COMPULSORY
    assert _plan_codes(specs, EnrollmentType.COMPULSORY) == sorted(MANDATORY)
    # exactly one ELECTIVE per configured slot
    slots = sorted(getattr(s.elective_slot, "value", None) for s, t in specs if t == EnrollmentType.ELECTIVE)
    assert slots == ["ELECTIVE_I", "ELECTIVE_II"]


def test_case_b_selected_052_055():
    specs, missing = plan_new_student_enrollments(_catalog(), _choices("BCS-052", "BCS-055"))
    assert missing == []
    assert _plan_codes(specs, EnrollmentType.ELECTIVE) == ["BCS-052", "BCS-055"]
    elective_codes = set(_plan_codes(specs, EnrollmentType.ELECTIVE))
    assert not elective_codes & {"BCS-053", "BCS-054", "BCS-056", "BCS-058"}
    assert _plan_codes(specs, EnrollmentType.COMPULSORY) == sorted(MANDATORY)
    slots = sorted(getattr(s.elective_slot, "value", None) for s, t in specs if t == EnrollmentType.ELECTIVE)
    assert slots == ["ELECTIVE_I", "ELECTIVE_II"]


def test_no_elective_falls_through_to_compulsory():
    for specs, _ in (
        plan_new_student_enrollments(_catalog(), _choices("BCS-054", "BCS-058")),
        plan_new_student_enrollments(_catalog(), _choices("BCS-052", "BCS-055")),
    ):
        for subject, enrollment_type in specs:
            if subject.elective_slot is not None:
                assert enrollment_type == EnrollmentType.ELECTIVE
            else:
                assert enrollment_type == EnrollmentType.COMPULSORY


# ---- resolver semantics ------------------------------------------------------

def test_missing_choice_falls_back_to_anchor_never_fabricates():
    # Only the ELECTIVE_I choice is recorded; ELECTIVE_II resolves to the
    # slot's anchor subject (ElectiveResolver semantics) — never another pool
    # subject and never a missing slot.
    choices = {ElectiveSlot.ELECTIVE_I: _choices("BCS-052", "BCS-055")[ElectiveSlot.ELECTIVE_I]}
    specs, missing = plan_new_student_enrollments(_catalog(), choices, ANCHORS)
    assert missing == []
    assert _plan_codes(specs, EnrollmentType.ELECTIVE) == ["BCS-052", "BCS-058"]


def test_unresolvable_slot_is_reported_as_missing():
    # No choice and no anchor for ELECTIVE_II -> missing slot. The PLAN keeps
    # the resolvable slot's elective (it is the resolved selection for that
    # slot) and the missing slot is reported; the APPLY gate is the all-or-
    # nothing boundary (it adds NOTHING while any slot is missing), so
    # callers reject the whole transaction instead of enrolling a partial
    # elective set.
    choices = {ElectiveSlot.ELECTIVE_I: _choices("BCS-054", "BCS-058")[ElectiveSlot.ELECTIVE_I]}
    specs, missing = plan_new_student_enrollments(_catalog(), choices, {ElectiveSlot.ELECTIVE_I: ANCHORS[ElectiveSlot.ELECTIVE_I]})
    assert missing == [ElectiveSlot.ELECTIVE_II]
    assert _plan_codes(specs, EnrollmentType.ELECTIVE) == ["BCS-054"]
    assert _plan_codes(specs, EnrollmentType.COMPULSORY) == sorted(MANDATORY)


def test_apply_adds_nothing_when_a_slot_is_unresolvable():
    added = []

    class _DB:
        def add(self, row):
            added.append(row)

    choices = {ElectiveSlot.ELECTIVE_I: _choices("BCS-054", "BCS-058")[ElectiveSlot.ELECTIVE_I]}
    specs, missing = apply_new_student_enrollments(
        _DB(), "user-1", _catalog(), choices,
        fallback_subjects={ElectiveSlot.ELECTIVE_I: ANCHORS[ElectiveSlot.ELECTIVE_I]},
    )
    assert missing == [ElectiveSlot.ELECTIVE_II]
    assert added == []  # atomic no-op


def test_apply_adds_invariant_rows_and_choice_rows():
    added = []

    class _DB:
        def add(self, row):
            added.append(row)

    specs, missing = apply_new_student_enrollments(
        _DB(), "user-1", _catalog(), _choices("BCS-054", "BCS-058"),
        include_choice_rows=True,
    )
    assert missing == []
    enrollments = [r for r in added if not hasattr(r, "elective_slot")]
    choices = [r for r in added if hasattr(r, "elective_slot")]
    assert len(enrollments) == len(specs) == 9
    assert {getattr(r.enrollment_type, "value", r.enrollment_type) for r in enrollments} \
        == {"COMPULSORY", "ELECTIVE"}
    assert sorted(getattr(r.elective_slot, "value", r.elective_slot) for r in choices) \
        == ["ELECTIVE_I", "ELECTIVE_II"]


def test_empty_catalog_plans_nothing():
    specs, missing = plan_new_student_enrollments([], _choices("BCS-054", "BCS-058"))
    assert specs == [] and missing == []
    assert configured_elective_slots([]) == []


def test_choice_rows_builder_types():
    rows = build_choice_rows("user-1", {
        ElectiveSlot.ELECTIVE_I: BY_CODE["BCS-054"],
        ElectiveSlot.ELECTIVE_II: BY_CODE["BCS-058"],
    })
    assert [(getattr(r.elective_slot, "value", r.elective_slot), r.subject_id) for r in rows] \
        == [("ELECTIVE_I", "BCS-054"), ("ELECTIVE_II", "BCS-058")]
    assert all(r.user_id == "user-1" for r in rows)


def test_builder_sets_explicit_enrollment_type():
    row_c = build_enrollment("user-1", BY_CODE["BCS-501"], EnrollmentType.COMPULSORY)
    row_e = build_enrollment("user-1", BY_CODE["BCS-054"], EnrollmentType.ELECTIVE)
    assert getattr(row_c.enrollment_type, "value", row_c.enrollment_type) == "COMPULSORY"
    assert getattr(row_e.enrollment_type, "value", row_e.enrollment_type) == "ELECTIVE"
    assert row_c.subject_id == "BCS-501" and row_e.subject_id == "BCS-054"
    assert row_c.user_id == row_e.user_id == "user-1"
