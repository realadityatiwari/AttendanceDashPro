from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from uuid import UUID
from datetime import date

from app.models.enums import ElectiveSlot, EnrollmentType


class ContextSubject(BaseModel):
    """A subject the student is enrolled in (Phase 23.4).

    Read-only, service-level subject reference. ``enrollment_type`` keeps the
    Phase 23.3 COMPULSORY / ELECTIVE distinction explicit. This is NOT the ORM
    ``Subject`` model — downstream services consume this stable representation.
    """

    id: UUID
    code: str
    name: str
    enrollment_type: EnrollmentType


class StudentContext(BaseModel):
    """Authoritative read-only student academic context (Phase 23.4).

    The single service-level representation of a student's current academic
    context. It preserves the three distinct assignment concepts and never
    collapses them:

      - placement        — where the student belongs (section / semester /
                            academic session / subsection / program);
      - enrollments      — which concrete subjects the student is enrolled in
                            (compulsory + elective), each tagged with its
                            Phase 23.3 enrollment type;
      - elective_choices — why a particular elective subject is enrolled
                            (DE-I / DE-II logical slot -> concrete subject code).

    Honest incompleteness: a missing subsection / elective / enrollment is
    represented as NULL / empty — never fabricated. ``is_placed`` is True only
    when the full section -> semester -> academic-session chain resolves.
    ``inconsistencies`` records (without repairing) any stored elective choice
    that contradicts the authoritative elective catalog.
    """

    # --- Identity ---
    user_id: UUID
    role: str = "STUDENT"

    # --- Placement ---
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    program: Optional[str] = None
    semester_id: Optional[UUID] = None
    semester_name: Optional[str] = None
    semester_start: Optional[date] = None
    semester_end: Optional[date] = None
    academic_session_id: Optional[UUID] = None
    academic_session_name: Optional[str] = None
    subsection_id: Optional[UUID] = None
    subsection_name: Optional[str] = None

    # --- Enrollments ---
    enrollments: List[ContextSubject] = Field(default_factory=list)
    compulsory_subjects: List[ContextSubject] = Field(default_factory=list)
    elective_subjects: List[ContextSubject] = Field(default_factory=list)

    # --- Elective choices (logical slot -> concrete subject code) ---
    elective_choices: Dict[ElectiveSlot, str] = Field(default_factory=dict)

    # --- Validity / consistency ---
    is_placed: bool = False
    inconsistencies: List[str] = Field(default_factory=list)

    # --- Quiz context (read-only; earliest active QUIZ_DAY date) ---
    first_quiz_date: Optional[date] = None
