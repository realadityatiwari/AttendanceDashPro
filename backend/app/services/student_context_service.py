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

from sqlalchemy import func, select, text
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
from app.services.read_concurrency import run_independent_reads


class StudentContextService:
    """Authoritative, read-only student academic context resolver (Phase 23.4)."""

    def __init__(self, db: AsyncSession):
        self._db = db

    # ------------------------------------------------------------------
    # Placement
    # ------------------------------------------------------------------
    async def get_placement(self, user: User) -> StudentContext:
        """Resolve placement only (section -> semester -> academic session,
        subsection, program). Bounded query set; never fabricated.

        Phase 27 Batch 3C: the section -> semester -> academic-session FK
        chain (plus the user's independently-keyed subsection) resolves in
        ONE parameterized LEFT-JOIN query instead of up to four sequential
        ``db.get`` round trips — the single SQL-level batching strategy for a
        dependent chain. Row-for-row identical outcomes: a missing section or
        any missing chain link nullifies everything downstream exactly like
        the sequential path, and the subsection resolves solely from the
        user's own subsection_id (never from the chain). The previous
        sequential implementation is retained as
        ``_get_placement_sequential`` — the documented comparison reference
        for the equivalence tests and verify harness."""
        ctx = StudentContext(
            user_id=user.id,
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
        )
        await self._load_placement(user, self._db, ctx)
        return ctx

    async def _load_placement(self, user: User, session: AsyncSession, ctx: StudentContext) -> None:
        """Resolve the placement fields of ``ctx`` in ONE round trip (Batch
        3C). Parameterized LEFT JOINs preserve the exact chain semantics: a
        missing section (unplaced user) or any missing chain link yields
        NULLs exactly like the sequential ``db.get`` path, and the subsection
        resolves solely from the user's own subsection_id (independent of the
        chain, exactly as before)."""
        if user.section_id is None and user.subsection_id is None:
            # Sequential fast path preserved: nothing can resolve — no query.
            return
        stmt = text(
            """
            SELECT
                s.id            AS section_id,
                s.name          AS section_name,
                s.program       AS program,
                sem.id          AS semester_id,
                sem.name        AS semester_name,
                sem.start_date  AS semester_start,
                sem.end_date    AS semester_end,
                acs.id          AS academic_session_id,
                acs.name        AS academic_session_name,
                sub.id          AS subsection_id,
                sub.name        AS subsection_name
            FROM (SELECT 1) AS one
            LEFT JOIN sections s
                ON s.id = :section_id
            LEFT JOIN semesters sem
                ON sem.id = s.semester_id
            LEFT JOIN academic_sessions acs
                ON acs.id = sem.session_id
            LEFT JOIN subsections sub
                ON sub.id = :subsection_id
            """
        )
        row = (
            await session.execute(
                stmt, {"section_id": user.section_id, "subsection_id": user.subsection_id}
            )
        ).first()

        ctx.section_id = row.section_id
        ctx.section_name = row.section_name
        ctx.program = row.program
        ctx.semester_id = row.semester_id
        ctx.semester_name = row.semester_name
        ctx.semester_start = row.semester_start
        ctx.semester_end = row.semester_end
        ctx.academic_session_id = row.academic_session_id
        ctx.academic_session_name = row.academic_session_name
        ctx.subsection_id = row.subsection_id
        ctx.subsection_name = row.subsection_name
        ctx.is_placed = (
            row.section_id is not None
            and row.semester_id is not None
            and row.academic_session_id is not None
        )

    async def _get_placement_sequential(self, user: User) -> StudentContext:
        """Pre-Batch-3C reference implementation (comparison harness only —
        never called by production code): the original per-entity ``db.get``
        chain, kept so tests and the verify harness can prove the single-join
        placement returns identical results for every user and for both
        subsection-present and subsection-NULL cases."""
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
    async def _load_enrollments(self, session: AsyncSession, user_id: UUID, ctx: StudentContext) -> None:
        """One query: every enrolled subject with its Phase 23.3 enrollment
        type. Never duplicated and never multiplied."""
        result = await session.execute(
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
    async def _load_elective_choices(self, session: AsyncSession, user_id: UUID, ctx: StudentContext) -> None:
        """One query: the student's recorded elective choices (slot -> concrete
        subject code). A choice whose subject contradicts the authoritative
        DB-backed catalog is recorded in ``inconsistencies`` and NOT repaired."""
        result = await session.execute(
            select(StudentElectiveChoice.elective_slot, Subject.code)
            .join(Subject, Subject.id == StudentElectiveChoice.subject_id)
            .where(StudentElectiveChoice.user_id == user_id)
        )
        resolver = ElectiveResolver(session)
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
    async def _load_first_quiz_date(self, session: AsyncSession, user_id: UUID, ctx: StudentContext) -> None:
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
        ctx.first_quiz_date = (await session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Full context
    # ------------------------------------------------------------------
    async def get_context(self, user: User) -> StudentContext:
        """Full authoritative context: placement + enrollments + elective
        choices + first quiz date. Bounded query set (no N+1).

        Phase 27 Batch 3C: the four groups are mutually independent (each
        needs only the user's id/keys, never another group's result), so they
        run concurrently on separate short-lived read sessions via the bounded
        `run_independent_reads` helper instead of back-to-back round trips.
        The composed StudentContext is field-for-field identical to the
        previous sequential composition (the loaders are unchanged; only
        their scheduling and session binding moved)."""
        ctx = StudentContext(
            user_id=user.id,
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
        )
        await run_independent_reads([
            lambda s: self._load_placement(user, s, ctx),
            lambda s: self._load_enrollments(s, user.id, ctx),
            lambda s: self._load_elective_choices(s, user.id, ctx),
            lambda s: self._load_first_quiz_date(s, user.id, ctx),
        ])
        return ctx
