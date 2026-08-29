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

from app.models.user import User
from app.models.enums import AdminRole, UserRole
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
