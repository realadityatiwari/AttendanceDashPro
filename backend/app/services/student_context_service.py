"""
Authoritative Student Context Service (Phase 23.4).

One reusable backend authority for resolving a student's current academic
context, so downstream services do NOT independently reconstruct:

    User
     -> Section
     -> Semester
     -> Academic Session
     -> Branch/Program
     -> Subsection
     -> Enrollments
     -> Elective choices

The service is READ-ONLY: it never creates enrollments, assigns electives,
creates subsections, or repairs users. Incomplete context is represented
honestly (NULL / empty / inconsistencies), never fabricated.

It consumes the existing authoritative components:
  - placement:  users.section_id / users.subsection_id -> Section -> Semester
                -> AcademicSession (Section.program = branch);
  - enrollment: student_enrollments with the Phase 23.3 enrollment_type
                discriminator (COMPULSORY / ELECTIVE);
  - electives:  student_elective_choices + the Phase 22.3/22.4 authoritative
                elective catalog (ElectiveResolver.slot_for_code). No second
                resolver, no inference from timetable/attendance/enrollment.

Query efficiency: bounded query set (no N+1). ``get_placement`` issues a small
fixed set (section/semester/session/subsection lookups). ``get_context`` adds
exactly one query for enrollments, one for elective choices, and one for the
first quiz date.
"""

from uuid import UUID
from typing import Optional
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, Section, Subsection
from app.models.academic import (
    AcademicSession,
    Semester,
    StudentEnrollment,
    StudentElectiveChoice,
    Subject,
)
from app.models.event import AcademicEvent
from app.models.enums import EventType, ElectiveSlot, EnrollmentType
from app.schemas.student_context import StudentContext, ContextSubject
from app.services.elective_resolver import ElectiveResolver


class StudentContextService:
    """Authoritative, read-only student academic context resolver (Phase 23.4)."""

    def __init__(self, db: AsyncSession):
        self._db = db

    # ------------------------------------------------------------------
    # Placement
    # ------------------------------------------------------------------
    async def get_placement(self, user: User) -> StudentContext:
        """Resolve placement only (section -> semester -> academic session,
        subsection, program). Bounded query set; never fabricated."""
        section: Optional[Section] = None
        semester: Optional[Semester] = None
        academic_session: Optional[AcademicSession] = None
        subsection: Optional[Subsection] = None

        if user.section_id is not None:
            section = await self._db.get(Section, user.section_id)
        if section is not None and section.semester_id is not None:
            semester = await self._db.get(Semester, section.semester_id)
        if semester is not None:
            academic_session = await self._db.get(AcademicSession, semester.session_id)
        if user.subsection_id is not None:
            subsection = await self._db.get(Subsection, user.subsection_id)

        is_placed = section is not None and semester is not None and academic_session is not None

        return StudentContext(
            user_id=user.id,
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
            section_id=section.id if section is not None else None,
            section_name=section.name if section is not None else None,
            program=section.program if section is not None else None,
            semester_id=semester.id if semester is not None else None,
            semester_name=semester.name if semester is not None else None,
            semester_start=semester.start_date if semester is not None else None,
            semester_end=semester.end_date if semester is not None else None,
            academic_session_id=academic_session.id if academic_session is not None else None,
            academic_session_name=academic_session.name if academic_session is not None else None,
            subsection_id=subsection.id if subsection is not None else None,
            subsection_name=subsection.name if subsection is not None else None,
            is_placed=is_placed,
        )

    # ------------------------------------------------------------------
    # Enrollments
    # ------------------------------------------------------------------
    async def _load_enrollments(self, user_id: UUID, ctx: StudentContext) -> None:
        """One query: every enrolled subject with its Phase 23.3 enrollment
        type. Never duplicated and never multiplied."""
        result = await self._db.execute(
            select(Subject, StudentEnrollment.enrollment_type)
            .join(StudentEnrollment, StudentEnrollment.subject_id == Subject.id)
            .where(StudentEnrollment.user_id == user_id)
        )
        for subject, enrollment_type in result.all():
            item = ContextSubject(
                id=subject.id,
                code=subject.code,
                name=subject.name,
                enrollment_type=enrollment_type,
            )
            ctx.enrollments.append(item)
            if enrollment_type == EnrollmentType.ELECTIVE:
                ctx.elective_subjects.append(item)
            else:
                ctx.compulsory_subjects.append(item)

    # ------------------------------------------------------------------
    # Elective choices
    # ------------------------------------------------------------------
    async def _load_elective_choices(self, user_id: UUID, ctx: StudentContext) -> None:
        """One query: the student's recorded elective choices (slot -> concrete
        subject code). A choice whose subject contradicts the authoritative
        DB-backed catalog is recorded in ``inconsistencies`` and NOT repaired."""
        result = await self._db.execute(
            select(StudentElectiveChoice.elective_slot, Subject.code)
            .join(Subject, Subject.id == StudentElectiveChoice.subject_id)
            .where(StudentElectiveChoice.user_id == user_id)
        )
        resolver = ElectiveResolver(self._db)
        for slot, code in result.all():
            expected_slot = await resolver.slot_for_code(code)
            if expected_slot is None or expected_slot != slot:
                ctx.inconsistencies.append(
                    f"elective {slot.value}: stored subject {code} is not a valid "
                    f"{slot.value} subject in the authoritative elective catalog"
                )
                continue
            ctx.elective_choices[slot] = code

    # ------------------------------------------------------------------
    # First quiz date
    # ------------------------------------------------------------------
    async def _load_first_quiz_date(self, user_id: UUID, ctx: StudentContext) -> None:
        """One query: earliest active QUIZ_DAY AcademicEvent across the
        student's enrolled subjects (same authoritative source the Profile UI
        has always used)."""
        stmt = (
            select(func.min(AcademicEvent.start_date))
            .join(
                StudentEnrollment,
                StudentEnrollment.subject_id == AcademicEvent.subject_id,
            )
            .where(
                StudentEnrollment.user_id == user_id,
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.active.is_(True),
            )
        )
        ctx.first_quiz_date = (await self._db.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Full context
    # ------------------------------------------------------------------
    async def get_context(self, user: User) -> StudentContext:
        """Full authoritative context: placement + enrollments + elective
        choices + first quiz date. Bounded query set (no N+1)."""
        ctx = await self.get_placement(user)
        await self._load_enrollments(user.id, ctx)
        await self._load_elective_choices(user.id, ctx)
        await self._load_first_quiz_date(user.id, ctx)
        return ctx
