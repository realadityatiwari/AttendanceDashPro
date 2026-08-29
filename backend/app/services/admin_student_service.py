"""
Scoped, read-only student management service for the Admin Portal (Phase 24.3).

Authorization is resolved here from ``AuthorizationService`` active scopes
(DB-backed per request — never from JWT claims, body, query, or frontend):

  - HEAD_ADMIN        -> global (all students).
  - CLASS_ADMIN       -> students of the assigned section(s) only.
  - ELECTIVE_ADMIN    -> students whose StudentElectiveChoice resolves to the
                         assigned concrete subject(s) — never slot-collapsed.
  - SUBSECTION_ADMIN  -> inert: no authoritative subsection data exists, so
                         the resolved scope is empty (conservative).
  - STUDENT           -> denied at the endpoint gate (require_any_admin).

The union rule (an admin may hold multiple scopes) is preserved: visible
students = section-membership OR elective-roster-membership for any scope the
caller holds. No client-supplied scope parameters exist in the contract.

Detail reads delegate to ``StudentContextService`` — the single authoritative
context resolver (placement, enrollments with COMPULSORY/ELECTIVE types,
elective choices, inconsistencies). No attendance/eligibility/elective
mathematics are re-implemented here.
"""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.user import User, Subsection
from app.models.academic import StudentEnrollment, StudentElectiveChoice, Subject
from app.models.enums import AdminRole, UserRole, ElectiveSlot, EnrollmentType
from app.schemas.admin_students import (
    AdminStudentDetail,
    AdminStudentEnrollment,
    AdminStudentListResponse,
    AdminStudentSummary,
)
from app.repositories.admin_student_repo import AdminStudentRepository, StudentScopeFilter
from app.services.authorization_service import AuthorizationService
from app.services.student_context_service import StudentContextService


class AdminStudentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AdminStudentRepository(db)

    # ------------------------------------------------------------------
    # Scope resolution (DB-authoritative)
    # ------------------------------------------------------------------
    async def _resolve_scope(self, user: User) -> StudentScopeFilter:
        authz = AuthorizationService(self.db)
        if await authz.is_head_admin(user):
            return StudentScopeFilter(is_global=True)

        scopes = await authz.get_active_scopes(user.id)
        section_ids = {
            s.section_id
            for s in scopes
            if s.role == AdminRole.CLASS_ADMIN and s.section_id is not None
        }
        subject_ids = {
            s.subject_id
            for s in scopes
            if s.role == AdminRole.ELECTIVE_ADMIN and s.subject_id is not None
        }
        return StudentScopeFilter(
            is_global=False,
            section_ids=section_ids,
            subject_ids=subject_ids,
        )

    async def _can_access_student(self, user: User, student: User) -> bool:
        """Detail-scope gate: the acting admin may view this student only when
        the student falls inside the admin's effective scope. Out-of-scope and
        nonexistent students are both surfaced as 404 (no existence leak)."""
        if student is None:
            return False
        if student.role != UserRole.STUDENT:
            return False
        scope = await self._resolve_scope(user)
        if scope.is_global:
            return True
        if scope.section_ids and student.section_id in scope.section_ids:
            return True
        if scope.subject_ids and await self.repo.student_is_in_elective_roster(
            student.id, scope.subject_ids
        ):
            return True
        return False

    # ------------------------------------------------------------------
    # Read contract
    # ------------------------------------------------------------------
    async def list_students(
        self,
        user: User,
        q: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AdminStudentListResponse:
        scope = await self._resolve_scope(user)
        total = await self.repo.count_students(scope, q=q)
        pages = (total + page_size - 1) // page_size if total else 0

        rows = await self.repo.search_students(
            scope,
            q=q,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        items = [
            AdminStudentSummary(**row)
            for row in rows
        ]
        return AdminStudentListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def get_student_detail(self, user: User, student_id: UUID) -> AdminStudentDetail:
        student = await self.repo.get_student(student_id)
        if not await self._can_access_student(user, student):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found",
            )

        ctx = await StudentContextService(self.db).get_context(student)

        enrollments = [
            AdminStudentEnrollment(
                id=e.id,
                code=e.code,
                name=e.name,
                enrollment_type=e.enrollment_type,
            )
            for e in ctx.enrollments
        ]
        compulsory = [
            AdminStudentEnrollment(
                id=e.id, code=e.code, name=e.name, enrollment_type=e.enrollment_type
            )
            for e in ctx.compulsory_subjects
        ]
        elective = [
            AdminStudentEnrollment(
                id=e.id, code=e.code, name=e.name, enrollment_type=e.enrollment_type
            )
            for e in ctx.elective_subjects
        ]

        return AdminStudentDetail(
            id=student.id,
            roll_number=student.roll_number,
            name=student.name,
            is_active=getattr(student, 'is_active', True),
            section_id=ctx.section_id,
            section_name=ctx.section_name,
            program=ctx.program,
            semester_id=ctx.semester_id,
            semester_name=ctx.semester_name,
            semester_start=ctx.semester_start,
            semester_end=ctx.semester_end,
            academic_session_id=ctx.academic_session_id,
            academic_session_name=ctx.academic_session_name,
            subsection_id=ctx.subsection_id,
            subsection_name=ctx.subsection_name,
            is_placed=ctx.is_placed,
            enrollments=enrollments,
            compulsory_subjects=compulsory,
            elective_subjects=elective,
            elective_choices={
                slot.value if hasattr(slot, "value") else str(slot): code
                for slot, code in ctx.elective_choices.items()
            },
            inconsistencies=list(ctx.inconsistencies),
            first_quiz_date=ctx.first_quiz_date,
        )

    # ------------------------------------------------------------------
    # Write contract
    # ------------------------------------------------------------------
    async def assign_subsection(self, user: User, student_id: UUID, subsection_id: UUID) -> AdminStudentDetail:
        student = await self.repo.get_student(student_id)
        if not await self._can_access_student(user, student):
            raise HTTPException(status_code=404, detail="Student not found")

        # Verify subsection belongs to student's section
        stmt = select(Subsection).where(Subsection.id == subsection_id)
        result = await self.db.execute(stmt)
        subsection = result.scalars().first()
        if not subsection:
            raise HTTPException(status_code=404, detail="Subsection not found")
        
        if subsection.section_id != student.section_id:
            raise HTTPException(status_code=409, detail="Subsection does not belong to the student's section")

        # Enforce capacity
        if subsection.max_strength is not None:
            count_stmt = select(func.count()).select_from(User).where(User.subsection_id == subsection_id)
            count_result = await self.db.execute(count_stmt)
            current_count = count_result.scalar_one()
            if current_count >= subsection.max_strength:
                raise HTTPException(status_code=409, detail="Subsection is at maximum capacity")

        student.subsection_id = subsection_id
        await self.db.commit()
        return await self.get_student_detail(user, student_id)

    async def correct_elective(self, user: User, student_id: UUID, slot: ElectiveSlot, new_subject_id: UUID) -> AdminStudentDetail:
        student = await self.repo.get_student(student_id)
        if not await self._can_access_student(user, student):
            raise HTTPException(status_code=404, detail="Student not found")

        # Verify new subject is valid and belongs to the correct slot and semester
        stmt = select(Subject).where(Subject.id == new_subject_id)
        result = await self.db.execute(stmt)
        new_subject = result.scalars().first()
        if not new_subject:
            raise HTTPException(status_code=404, detail="New subject not found")
        
        ctx = await StudentContextService(self.db).get_context(student)
        if new_subject.semester_id != ctx.semester_id:
            raise HTTPException(status_code=409, detail="Subject does not belong to the student's current semester")
        if new_subject.elective_slot != slot:
            raise HTTPException(status_code=409, detail=f"Subject is not configured for {slot.value}")

        # Find existing choice for this slot
        choice_stmt = select(StudentElectiveChoice).where(
            StudentElectiveChoice.user_id == student_id,
            StudentElectiveChoice.elective_slot == slot
        )
        choice_result = await self.db.execute(choice_stmt)
        existing_choice = choice_result.scalars().first()

        old_subject_id = existing_choice.subject_id if existing_choice else None

        if old_subject_id == new_subject_id:
            return await self.get_student_detail(user, student_id)

        # Update or create choice
        if existing_choice:
            existing_choice.subject_id = new_subject_id
        else:
            self.db.add(StudentElectiveChoice(
                user_id=student_id,
                elective_slot=slot,
                subject_id=new_subject_id
            ))

        # Swap enrollment if necessary
        if old_subject_id and old_subject_id != new_subject_id:
            enroll_stmt = select(StudentEnrollment).where(
                StudentEnrollment.user_id == student_id,
                StudentEnrollment.subject_id == old_subject_id,
                StudentEnrollment.enrollment_type == EnrollmentType.ELECTIVE
            )
            enroll_result = await self.db.execute(enroll_stmt)
            old_enrollment = enroll_result.scalars().first()
            if old_enrollment:
                await self.db.delete(old_enrollment)
        
        # Ensure enrollment exists for the new subject
        new_enroll_stmt = select(StudentEnrollment).where(
            StudentEnrollment.user_id == student_id,
            StudentEnrollment.subject_id == new_subject_id
        )
        new_enroll_result = await self.db.execute(new_enroll_stmt)
        if not new_enroll_result.scalars().first():
            self.db.add(StudentEnrollment(
                user_id=student_id,
                subject_id=new_subject_id,
                enrollment_type=EnrollmentType.ELECTIVE
            ))

        await self.db.commit()
        return await self.get_student_detail(user, student_id)

    async def set_student_status(self, user: User, student_id: UUID, is_active: bool) -> AdminStudentDetail:
        student = await self.repo.get_student(student_id)
        if not await self._can_access_student(user, student):
            raise HTTPException(status_code=404, detail="Student not found")

        student.is_active = is_active
        await self.db.commit()
        return await self.get_student_detail(user, student_id)
