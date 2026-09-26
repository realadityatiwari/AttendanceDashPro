"""
Centralized enrollment construction (Chunk 16).

Single authoritative writer for NEW student account enrollment. The invariant:

    effective enrollment =
        non-elective subjects (subjects.elective_slot IS NULL)
        UNION
        the StudentElectiveChoice-resolved selected subject for each
        configured elective slot

An unselected elective is NEVER eligible for enrollment. The selected subject
per slot is resolved exclusively through the existing ElectiveResolver
semantics — no second resolver is introduced here.

EnrollmentType is set explicitly by this module (COMPULSORY for non-elective,
ELECTIVE for selected electives); the SQLAlchemy model default is never
relied upon.

Existing students are untouched by design: the apply helper only ADDs rows
for the given user id and is intended for brand-new accounts (callers that
operate on existing users must pre-filter already-enrolled subjects, as
scripts/setup_single_user.py does after the Chunk 16 conversion).
"""
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.models.academic import StudentEnrollment, StudentElectiveChoice, Subject
from app.models.enums import ElectiveSlot, EnrollmentType
from app.services.elective_resolver import ElectiveResolver

# A choice-like object is anything exposing (elective_slot, subject) — a real
# StudentElectiveChoice row, or the registration path's selection record.
ChoiceLike = object


def configured_elective_slots(subjects: Iterable[Subject]) -> List[ElectiveSlot]:
    """Every elective slot present in the candidate subject catalog, in enum order."""
    seen = {s.elective_slot for s in subjects if s.elective_slot is not None}
    return [slot for slot in (ElectiveSlot.ELECTIVE_I, ElectiveSlot.ELECTIVE_II) if slot in seen]


def plan_new_student_enrollments(
    subjects: Sequence[Subject],
    elective_choices: Dict[ElectiveSlot, ChoiceLike],
    fallback_subjects: Optional[Dict[ElectiveSlot, Subject]] = None,
) -> Tuple[List[Tuple[Subject, EnrollmentType]], List[ElectiveSlot]]:
    """Pure invariant core — no DB access, no ORM side effects.

    Returns (specs, missing_slots):

    specs            — list of (subject, EnrollmentType) pairs satisfying the
                       invariant: every non-elective subject (COMPULSORY) plus
                       the resolved selected subject per configured slot
                       (ELECTIVE). One ELECTIVE subject per configured slot.
    missing_slots    — configured slots whose selection cannot be resolved
                       (no recorded choice and no anchor fallback). Callers
                       must treat a non-empty list as a rejection (the
                       registration path answers 503), never enroll a partial
                       elective set on their own.

    ``elective_choices`` maps slot -> choice-like object with ``.subject``;
    resolution delegates to ElectiveResolver.resolve_subject (choice first,
    anchor fallback second, never fabricated).
    """
    fallback_subjects = fallback_subjects or {}
    specs: List[Tuple[Subject, EnrollmentType]] = []
    missing: List[ElectiveSlot] = []

    # Mandatory subjects: elective_slot IS NULL.
    for subject in subjects:
        if subject.elective_slot is None:
            specs.append((subject, EnrollmentType.COMPULSORY))

    # Electives: only the resolved selection per configured slot.
    for slot in configured_elective_slots(subjects):
        fallback = fallback_subjects.get(slot)
        resolved = ElectiveResolver.resolve_subject(elective_choices, slot, fallback)
        if resolved is None:
            missing.append(slot)
            continue
        specs.append((resolved, EnrollmentType.ELECTIVE))

    return specs, missing


def build_enrollment(user_id, subject: Subject, enrollment_type: EnrollmentType) -> StudentEnrollment:
    """One explicitly-typed StudentEnrollment row (shared by every writer)."""
    return StudentEnrollment(
        user_id=user_id,
        subject_id=subject.id,
        enrollment_type=enrollment_type,
    )


def build_choice_rows(
    user_id,
    resolved_by_slot: Dict[ElectiveSlot, Subject],
) -> List[StudentElectiveChoice]:
    """StudentElectiveChoice rows for the resolved selections (new accounts)."""
    return [
        StudentElectiveChoice(user_id=user_id, elective_slot=slot, subject_id=subject.id)
        for slot, subject in resolved_by_slot.items()
    ]


def apply_new_student_enrollments(
    db,
    user_id,
    subjects: Sequence[Subject],
    elective_choices: Dict[ElectiveSlot, ChoiceLike],
    fallback_subjects: Optional[Dict[ElectiveSlot, Subject]] = None,
    include_choice_rows: bool = False,
) -> Tuple[List[Tuple[Subject, EnrollmentType]], List[ElectiveSlot]]:
    """Plan and ADD the enrollment rows for a NEW student account.

    Nothing is committed — the caller owns the transaction (registration
    commits alongside the user row; duplicate handling stays there). When any
    configured slot cannot be resolved, NOTHING is added and the missing
    slots are returned so the caller can reject atomically.
    """
    specs, missing = plan_new_student_enrollments(subjects, elective_choices, fallback_subjects)
    if missing:
        return [], missing
    for subject, enrollment_type in specs:
        db.add(build_enrollment(user_id, subject, enrollment_type))
    if include_choice_rows:
        resolved = {
            slot: subject
            for subject, enrollment_type in specs
            if (slot := subject.elective_slot) is not None
        }
        for row in build_choice_rows(user_id, resolved):
            db.add(row)
    return specs, missing
