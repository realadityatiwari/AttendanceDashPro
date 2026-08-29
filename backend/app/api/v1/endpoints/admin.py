from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, require_any_admin, require_head_admin
from app.models.user import User
from app.schemas.admin import AdminIdentity, AdminScopeDescriptor
from app.schemas.admin_dashboard import AdminDashboardResponse
from app.schemas.admin_students import (
    AdminStudentDetail, AdminStudentListResponse,
    AssignSubsectionRequest, CorrectElectiveRequest, SetStudentStatusRequest,
    SubsectionDropdownResponse, ElectiveDropdownResponse
)
from app.services.authorization_service import AuthorizationService
from app.services.admin_dashboard_service import AdminDashboardService
from app.services.admin_student_service import AdminStudentService
from app.models.user import Subsection
from app.models.academic import Subject
from sqlalchemy import select, func
from typing import List

router = APIRouter()


@router.get("/me", response_model=AdminIdentity)
async def get_admin_identity(
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.1: DB-authoritative administrative identity for the Admin Portal
    shell. Read-only — no write behavior, no academic data beyond the scope
    descriptors the shell needs.

    Authorization: ``require_any_admin`` (Phase 23.11 AuthorizationService,
    DB-resolved per request) — unauthenticated → 401, STUDENT with no
    effective admin role → 403. The returned roles/scopes are PRESENTATION
    data for the shell/navigation only; the frontend is never an
    authorization boundary and every admin endpoint stays server-gated.
    """
    identity = await AuthorizationService(db).get_admin_identity(current_user)
    return AdminIdentity(
        id=current_user.id,
        display_name=current_user.name,
        roll_number=current_user.roll_number,
        roles=identity["roles"],
        is_global=identity["is_global"],
        scopes=[AdminScopeDescriptor(**s) for s in identity["scopes"]],
    )


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def get_admin_dashboard(
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.2: HEAD_ADMIN operational dashboard — read-only, current-state
    overview of the authoritative academic data (session/semester, structure,
    curriculum, students, schedule, events, quizzes, attendance aggregates,
    and factual data-quality warnings).

    Authorization: ``require_head_admin`` (Phase 23.11, DB-resolved per
    request) — unauthenticated → 401, STUDENT → 403, and scoped admins
    (CLASS/SUBSECTION/ELECTIVE) are NOT silently elevated to the global
    dashboard: they receive 403 here. No client-supplied scope parameters are
    accepted; every number is derived server-side with bounded aggregate
    queries. Read-only — no mutation of timetable/session/event/quiz state.
    """
    return await AdminDashboardService(db).get_dashboard()


@router.get("/students", response_model=AdminStudentListResponse)
async def list_admin_students(
    q: Optional[str] = Query(
        None,
        max_length=100,
        description="Case-insensitive search on roll number or name.",
    ),
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="items per page"),
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.3: scoped, read-only student list/search for the Admin Portal.

    Authorization: ``require_any_admin`` (Phase 23.11/24.1, DB-resolved per
    request) — unauthenticated → 401, STUDENT → 403. The visible students are
    derived server-side from the acting admin's ACTIVE scopes:
      - HEAD_ADMIN        -> all students;
      - CLASS_ADMIN       -> students of the assigned section(s) only;
      - ELECTIVE_ADMIN    -> students whose StudentElectiveChoice resolves to
                             an assigned concrete subject (never slot-collapsed);
      - SUBSECTION_ADMIN  -> inert: conservative empty result (no authoritative
                             subsection data exists).
    An admin holding several scopes sees the union. NO client-supplied scope
    parameters are accepted. Read-only — no student data is mutated.
    """
    return await AdminStudentService(db).list_students(
        current_user,
        q=q,
        page=page,
        page_size=page_size,
    )


@router.get("/students/{student_id}", response_model=AdminStudentDetail)
async def get_admin_student_detail(
    student_id: UUID,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.3: scoped, read-only student detail (academic context) for the
    Admin Portal.

    Authorization: ``require_any_admin`` + per-student scope check in
    ``AdminStudentService`` (DB-resolved per request). The target must be a
    STUDENT-role account INSIDE the acting admin's effective scope — an
    out-of-scope or nonexistent student is surfaced as 404 (no existence leak;
    no cross-section / cross-subject elective access). The response is the
    authoritative academic context (placement, enrollments with their
    COMPULSORY/ELECTIVE types, elective choices, inconsistencies) composed by
    ``StudentContextService``. Read-only.
    """
    return await AdminStudentService(db).get_student_detail(current_user, student_id)

@router.patch("/students/{student_id}/subsection", response_model=AdminStudentDetail)
async def assign_student_subsection(
    student_id: UUID,
    request: AssignSubsectionRequest,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """Assign a student to a subsection."""
    return await AdminStudentService(db).assign_subsection(current_user, student_id, request.subsection_id)

@router.patch("/students/{student_id}/electives", response_model=AdminStudentDetail)
async def correct_student_elective(
    student_id: UUID,
    request: CorrectElectiveRequest,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """Correct a student's elective choice."""
    return await AdminStudentService(db).correct_elective(current_user, student_id, request.slot, request.subject_id)

@router.patch("/students/{student_id}/status", response_model=AdminStudentDetail)
async def set_student_status(
    student_id: UUID,
    request: SetStudentStatusRequest,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """Activate or deactivate a student account."""
    return await AdminStudentService(db).set_student_status(current_user, student_id, request.is_active)

@router.get("/sections/{section_id}/subsections", response_model=List[SubsectionDropdownResponse])
async def list_section_subsections(
    section_id: UUID,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """List available subsections for a section."""
    stmt = select(Subsection).where(Subsection.section_id == section_id)
    result = await db.execute(stmt)
    subsections = result.scalars().all()
    
    count_stmt = select(User.subsection_id, func.count(User.id)).where(
        User.section_id == section_id, User.subsection_id.isnot(None)
    ).group_by(User.subsection_id)
    count_result = await db.execute(count_stmt)
    counts = dict(count_result.all())

    return [
        SubsectionDropdownResponse(
            id=s.id,
            name=s.name,
            max_strength=s.max_strength,
            current_strength=counts.get(s.id, 0)
        )
        for s in subsections
    ]

@router.get("/semesters/{semester_id}/electives", response_model=List[ElectiveDropdownResponse])
async def list_semester_electives(
    semester_id: UUID,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """List available elective subjects for a semester."""
    stmt = select(Subject).where(Subject.semester_id == semester_id, Subject.elective_slot.isnot(None))
    result = await db.execute(stmt)
    subjects = result.scalars().all()
    return [
        ElectiveDropdownResponse(
            id=s.id,
            code=s.code,
            name=s.name,
            elective_slot=s.elective_slot
        )
        for s in subjects
    ]
