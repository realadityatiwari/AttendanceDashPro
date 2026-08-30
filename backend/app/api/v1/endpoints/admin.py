from typing import List, Optional
from uuid import UUID
import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
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
from app.schemas.admin_structure import (
    AcademicSessionResponse,
    CreateSessionRequest,
    UpdateSessionRequest,
    SessionActivationResponse,
    SemesterResponse,
    CreateSemesterRequest,
    UpdateSemesterRequest,
    SemesterMutationResponse,
    SectionResponse,
    CreateSectionRequest,
    UpdateSectionRequest,
    SectionMutationResponse,
    SubsectionAdminResponse,
    CreateSubsectionRequest,
    UpdateSubsectionRequest,
)
from app.schemas.admin_subjects import (
    AdminSubjectListResponse,
    AdminSubjectDetail,
    CreateSubjectRequest,
    UpdateSubjectRequest,
    SubjectMutationResponse,
)
from app.models.enums import ElectiveSlot, EventType, ClassType
from app.schemas.calendar import AcademicEventCreate, AcademicEventUpdate
from app.schemas.admin_timetable import (
    TimetableEntryAdminListResponse,
    TimetableEntryAdminResponse,
    TimetableEntryMutationResponse,
    CreateTimetableEntryRequest,
    UpdateTimetableEntryRequest,
    DuplicateTimetableEntryRequest,
)
from app.schemas.admin_quizzes import (
    AdminQuizCycleListResponse,
    AdminQuizCycleResponse,
    AdminQuizScheduleListResponse,
    AdminQuizScheduleMutationResponse,
    AdminQuizScheduleResponse,
    CreateQuizScheduleRequest,
    UpdateQuizScheduleRequest,
)
from app.schemas.admin_events import (
    AdminEventListResponse,
    AdminEventMutationResponse,
    AdminEventResponse,
)
from app.services.admin_quiz_service import (
    AdminQuizService,
    AdminQuizError,
    AdminQuizNotFoundError,
    AdminQuizInvalidScopeError,
    AdminQuizValidationError,
    AdminQuizConflictError,
)
from app.services.admin_event_service import (
    AdminEventService,
    AdminEventDomainError,
    AdminEventQuizManagedError,
)
from app.services.authorization_service import AuthorizationService
from app.services.admin_dashboard_service import AdminDashboardService
from app.services.admin_student_service import AdminStudentService
from app.services.admin_structure_service import AdminStructureService
from app.services.admin_subject_service import AdminSubjectService
from app.services.admin_timetable_service import (
    AdminTimetableService,
    TimetableDomainError,
    TimetableNotFoundError,
    TimetableInvalidScopeError,
    TimetableInvalidSubjectError,
    TimetableInvalidSubsectionError,
    TimetableInvalidElectiveSlotError,
    TimetableInvalidTimeRangeError,
    TimetableTimeConflictError,
    TimetableInactiveParentError,
)
from app.models.user import Subsection
from app.models.academic import Subject
from sqlalchemy import select, func

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


# ===========================================================================
# Phase 24.5 — Academic Structure Management (HEAD_ADMIN only)
# ===========================================================================

@router.get("/structure/sessions", response_model=List[AcademicSessionResponse])
async def list_sessions(
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.5: list all academic sessions ordered by start date descending.
    Authorization: require_head_admin — unauthenticated → 401, non-HEAD → 403.
    """
    return await AdminStructureService(db).list_sessions()


@router.post("/structure/sessions", response_model=AcademicSessionResponse, status_code=201)
async def create_session(
    request: CreateSessionRequest,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.5: create a new academic session.
    New sessions are always inactive — use the /activate endpoint to activate.
    Authorization: require_head_admin.
    """
    return await AdminStructureService(db).create_session(request)


@router.patch("/structure/sessions/{session_id}", response_model=AcademicSessionResponse)
async def update_session(
    session_id: UUID,
    request: UpdateSessionRequest,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.5: update session name / dates.  is_active is NOT a valid field
    here — use /activate or /deactivate instead.
    Authorization: require_head_admin.
    """
    return await AdminStructureService(db).update_session(session_id, request)


@router.post("/structure/sessions/{session_id}/activate", response_model=SessionActivationResponse)
async def activate_session(
    session_id: UUID,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.5: explicitly activate an academic session.

    Phase 24.5 documented invariant: at most one session may be active.
    If another session is already active, returns 409 — do NOT automatically
    deactivate the existing active session.  The administrator must first
    explicitly deactivate the current active session.
    Authorization: require_head_admin.
    """
    return await AdminStructureService(db).activate_session(session_id)


@router.post("/structure/sessions/{session_id}/deactivate", response_model=SessionActivationResponse)
async def deactivate_session(
    session_id: UUID,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.5: explicitly deactivate an academic session.
    Authorization: require_head_admin.
    """
    return await AdminStructureService(db).deactivate_session(session_id)


@router.get("/structure/sessions/{session_id}/semesters", response_model=List[SemesterResponse])
async def list_semesters(
    session_id: UUID,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """Phase 24.5: list semesters for a session. Authorization: require_head_admin."""
    return await AdminStructureService(db).list_semesters(session_id)


@router.post("/structure/sessions/{session_id}/semesters", response_model=SemesterMutationResponse, status_code=201)
async def create_semester(
    session_id: UUID,
    request: CreateSemesterRequest,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.5: create a semester under an academic session.
    Response includes registration-ambiguity warnings if multiple semesters now
    exist under the active session (new student registration will fail 409).
    Authorization: require_head_admin.
    """
    return await AdminStructureService(db).create_semester(session_id, request)


@router.patch("/structure/semesters/{semester_id}", response_model=SemesterMutationResponse)
async def update_semester(
    semester_id: UUID,
    request: UpdateSemesterRequest,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """Phase 24.5: update semester name / dates. Authorization: require_head_admin."""
    return await AdminStructureService(db).update_semester(semester_id, request)


@router.get("/structure/semesters/{semester_id}/sections", response_model=List[SectionResponse])
async def list_sections(
    semester_id: UUID,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """Phase 24.5: list sections for a semester. Authorization: require_head_admin."""
    return await AdminStructureService(db).list_sections(semester_id)


@router.post("/structure/semesters/{semester_id}/sections", response_model=SectionMutationResponse, status_code=201)
async def create_section(
    semester_id: UUID,
    request: CreateSectionRequest,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.5: create a section under a semester.
    Response includes registration-ambiguity warnings if multiple sections now
    exist under the active session's semester (new student registration 409).
    Authorization: require_head_admin.
    """
    return await AdminStructureService(db).create_section(semester_id, request)


@router.patch("/structure/sections/{section_id}", response_model=SectionMutationResponse)
async def update_section(
    section_id: UUID,
    request: UpdateSectionRequest,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """Phase 24.5: update section name / program. Authorization: require_head_admin."""
    return await AdminStructureService(db).update_section(section_id, request)


@router.get("/structure/sections/{section_id}/subsections", response_model=List[SubsectionAdminResponse])
async def list_subsections_structure(
    section_id: UUID,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.5: list subsections for a section (richer structure view).
    Authorization: require_head_admin.
    Note: the Phase 24.4 /sections/{id}/subsections dropdown endpoint
    (require_any_admin, lightweight) remains available for student assignment.
    """
    return await AdminStructureService(db).list_subsections(section_id)


@router.post("/structure/sections/{section_id}/subsections", response_model=SubsectionAdminResponse, status_code=201)
async def create_subsection(
    section_id: UUID,
    request: CreateSubsectionRequest,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.5: create a subsection under a section.
    Subsection scheduling remains inert (SUBSECTION_ADMIN still not operational).
    Authorization: require_head_admin.
    """
    return await AdminStructureService(db).create_subsection(section_id, request)


@router.patch("/structure/subsections/{subsection_id}", response_model=SubsectionAdminResponse)
async def update_subsection(
    subsection_id: UUID,
    request: UpdateSubsectionRequest,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """Phase 24.5: update subsection name / max_strength. Authorization: require_head_admin."""
    return await AdminStructureService(db).update_subsection(subsection_id, request)


# ===========================================================================
# Phase 24.6 — Curriculum & Subject Management
# ===========================================================================

@router.get("/subjects", response_model=AdminSubjectListResponse)
async def list_admin_subjects(
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.6: scoped, read-only curriculum subject list.

    Authorization: ``require_any_admin`` (Phase 23.11, DB-resolved per
    request). The visible subjects are derived server-side from the acting
    admin's ACTIVE scopes:
      - HEAD_ADMIN        -> all subjects;
      - CLASS_ADMIN       -> subjects belonging to the assigned section's
                             semester (frozen semester-wide semantic);
      - ELECTIVE_ADMIN    -> the exact concrete subject(s) assigned (never
                             slot-collapsed);
      - SUBSECTION_ADMIN  -> inert: conservative empty result.
    An admin holding several scopes sees the union.  NO client-supplied scope
    parameters are accepted. Read-only — no subject data is mutated.
    """
    return await AdminSubjectService(db).list_subjects(current_user)


@router.get("/subjects/{subject_id}", response_model=AdminSubjectDetail)
async def get_admin_subject(
    subject_id: UUID,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.6: scoped, read-only curriculum subject detail.

    Authorization: ``require_any_admin`` + per-subject scope check in
    ``AdminSubjectService`` (DB-resolved per request). The target must be
    INSIDE the acting admin's effective scope — an out-of-scope or nonexistent
    subject is surfaced as 404 (no existence leak; no cross-section /
    cross-subject elective access). Read-only.
    """
    return await AdminSubjectService(db).get_subject(current_user, subject_id)


@router.post("/subjects", response_model=SubjectMutationResponse, status_code=201)
async def create_admin_subject(
    request: CreateSubjectRequest,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.6: create a new subject.

    Authorization: ``require_head_admin`` — non-HEAD (CLASS/ELECTIVE/STUDENT)
    receive 403. No client-supplied scope parameters are accepted.
    New subjects in the active session's semester surface a registration-impact
    warning (future registrations auto-enroll; existing students NOT affected).
    """
    return await AdminSubjectService(db).create_subject(request)


@router.patch("/subjects/{subject_id}", response_model=SubjectMutationResponse)
async def update_admin_subject(
    subject_id: UUID,
    request: UpdateSubjectRequest,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.6: update a subject's metadata.

    ``code`` and ``semester_id`` are immutable — the service rejects attempted
    changes with 409.  Anchor subjects (BCS-054 / BCS-058) have frozen
    elective-slot assignments.  Changing a slot that existing student elective
    choices reference is also refused with 409.
    Authorization: ``require_head_admin``.
    """
    return await AdminSubjectService(db).update_subject(subject_id, request)


# ===========================================================================
# Phase 24.7-C — Admin Timetable CRUD API
# ===========================================================================

def _raise_timetable_error(exc: TimetableDomainError) -> None:
    """Map the 24.7-B domain-error hierarchy to the project's HTTP
    conventions: 404 not-found, 403 insufficient scope, 409 conflict /
    inactive-parent, 422 malformed/invalid data.

    409 conflicts additionally carry the structured conflicting-entry list
    (``detail.conflicts`` — only backend-resolved fields) so the UI can
    render each conflicting day/time/subject/scope without inferring from
    stale client state. The human-readable message stays in
    ``detail.message``.
    """
    if isinstance(exc, TimetableNotFoundError):
        raise HTTPException(status_code=404, detail=exc.detail)
    if isinstance(exc, TimetableInvalidScopeError):
        raise HTTPException(status_code=403, detail=exc.detail)
    if isinstance(exc, TimetableTimeConflictError):
        raise HTTPException(
            status_code=409,
            detail={"message": exc.detail, "conflicts": exc.conflicts},
        )
    if isinstance(exc, TimetableInactiveParentError):
        raise HTTPException(status_code=409, detail=exc.detail)
    if isinstance(exc, (TimetableInvalidSubjectError, TimetableInvalidSubsectionError,
                        TimetableInvalidElectiveSlotError, TimetableInvalidTimeRangeError)):
        raise HTTPException(status_code=422, detail=exc.detail)
    raise HTTPException(status_code=400, detail=exc.detail)


@router.get("/timetable", response_model=TimetableEntryAdminListResponse)
async def list_admin_timetable(
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
    session_id: Optional[UUID] = Query(None, description="Filter by academic session"),
    semester_id: Optional[UUID] = Query(None, description="Filter by semester"),
    section_id: Optional[UUID] = Query(None, description="Filter by section"),
    subsection_id: Optional[UUID] = Query(None, description="Filter by subsection"),
    day_of_week: Optional[int] = Query(None, ge=0, le=6, description="0=Monday .. 6=Sunday"),
    is_active: Optional[bool] = Query(None, description="True=active only; False=inactive only; omitted=active only"),
    subject_id: Optional[UUID] = Query(None, description="Filter by subject"),
    elective_slot: Optional[ElectiveSlot] = Query(None, description="Filter by elective slot"),
):
    """
    Phase 24.7-C: scoped timetable entry list.

    Authorization: ``require_any_admin`` (Phase 23.11, DB-resolved per
    request) + server-side scope filtering in ``AdminTimetableService``:
      - HEAD_ADMIN       -> all sections;
      - CLASS_ADMIN      -> assigned section(s) only;
      - SUBSECTION_ADMIN -> sections of assigned subsection(s) (inert);
      - ELECTIVE_ADMIN   -> entries of the exact assigned concrete subject.
    User-supplied filters (session/semester/section/subsection/day/subject/
    elective/active) only NARROW the scope-derived set — they never expand it,
    so a scoped admin cannot see unrelated sections by passing query params.
    No client-supplied role/scope is trusted. Read-only.
    """
    try:
        return await AdminTimetableService(db).list_entries(
            current_user,
            session_id=session_id,
            semester_id=semester_id,
            section_id=section_id,
            subsection_id=subsection_id,
            day_of_week=day_of_week,
            is_active=is_active,
            subject_id=subject_id,
            elective_slot=elective_slot,
        )
    except TimetableDomainError as exc:
        _raise_timetable_error(exc)


@router.get("/timetable/{entry_id}", response_model=TimetableEntryAdminResponse)
async def get_admin_timetable_entry(
    entry_id: UUID,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.7-C: scoped timetable entry detail.

    Authorization: ``require_any_admin`` + per-entry scope check in
    ``AdminTimetableService`` (DB-resolved per request).  An out-of-scope or
    nonexistent entry is surfaced as 404 (no existence leak).
    """
    try:
        return await AdminTimetableService(db).get_entry(current_user, entry_id)
    except TimetableDomainError as exc:
        _raise_timetable_error(exc)


@router.post("/timetable", response_model=TimetableEntryMutationResponse, status_code=201)
async def create_admin_timetable_entry(
    request: CreateTimetableEntryRequest,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.7-C: create a timetable entry.

    Authorization: ``require_any_admin`` + STRICT write gate in the service —
    only HEAD_ADMIN (any section) and CLASS_ADMIN (assigned section) may
    create timetable entries.  ELECTIVE_ADMIN / SUBSECTION_ADMIN receive 403
    even though they hold an admin identity (the Phase 24.0 matrix reserves
    timetable writes to HEAD + CLASS).  All validation (academic context,
    subject, subsection, elective slot, time range) and conflict detection run
    on the backend; the entry is never persisted on conflict (409).
    """
    try:
        entry = await AdminTimetableService(db).create_entry(current_user, request)
        return TimetableEntryMutationResponse(entry=entry)
    except TimetableDomainError as exc:
        _raise_timetable_error(exc)


@router.patch("/timetable/{entry_id}", response_model=TimetableEntryMutationResponse)
async def update_admin_timetable_entry(
    entry_id: UUID,
    request: UpdateTimetableEntryRequest,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.7-C: partial update of a timetable entry.

    Explicit-PATCH semantics: omitted field = unchanged; explicit null clears
    only when the field is nullable.  The resulting COMPLETE entry is
    revalidated (academic context, elective slot, time range) and conflict
    detection runs ignoring the row being updated (same-row edit never
    self-conflicts).  Write gate: HEAD_ADMIN (any) / CLASS_ADMIN (assigned
    section) only; others 403.  Conflict -> 409.
    """
    try:
        entry = await AdminTimetableService(db).update_entry(current_user, entry_id, request)
        return TimetableEntryMutationResponse(entry=entry)
    except TimetableDomainError as exc:
        _raise_timetable_error(exc)


@router.post("/timetable/{entry_id}/deactivate", response_model=TimetableEntryMutationResponse)
async def deactivate_admin_timetable_entry(
    entry_id: UUID,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.7-C: deactivate a timetable entry (soft).

    Sets ``is_active = false`` — historical preservation over hard delete (no
    DELETE route; Gate 7 destructive-action policy unresolved).  Idempotent:
    deactivating an already-inactive entry returns it unchanged.  Write gate:
    HEAD_ADMIN (any) / CLASS_ADMIN (assigned section) only.
    """
    try:
        entry = await AdminTimetableService(db).deactivate_entry(current_user, entry_id)
        return TimetableEntryMutationResponse(entry=entry)
    except TimetableDomainError as exc:
        _raise_timetable_error(exc)


@router.post("/timetable/{entry_id}/duplicate", response_model=TimetableEntryMutationResponse, status_code=201)
async def duplicate_admin_timetable_entry(
    entry_id: UUID,
    request: DuplicateTimetableEntryRequest,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.7-C: server-side duplication of a timetable entry.

    The client does NOT rebuild the full payload: absent override fields are
    copied from the source entry.  The FULL resulting entry is validated and
    conflict detection runs — a duplicate never silently overwrites another
    entry (409 on conflict).  Write gate: HEAD_ADMIN (any) / CLASS_ADMIN
    (assigned section) only.
    """
    try:
        entry = await AdminTimetableService(db).duplicate_entry(current_user, entry_id, request)
        return TimetableEntryMutationResponse(entry=entry)
    except TimetableDomainError as exc:
        _raise_timetable_error(exc)

# ===========================================================================
# Phase 24.8 — Admin Quiz Schedule Manager
# ===========================================================================

def _raise_quiz_error(exc: AdminQuizError) -> None:
    """Map the admin-quiz domain errors to the project's HTTP conventions:
    404 not-found, 403 insufficient scope, 409 conflict, 422 invalid data."""
    if isinstance(exc, AdminQuizNotFoundError):
        raise HTTPException(status_code=404, detail=exc.detail)
    if isinstance(exc, AdminQuizInvalidScopeError):
        raise HTTPException(status_code=403, detail=exc.detail)
    if isinstance(exc, AdminQuizConflictError):
        raise HTTPException(status_code=409, detail=exc.detail)
    if isinstance(exc, AdminQuizValidationError):
        raise HTTPException(status_code=422, detail=exc.detail)
    raise HTTPException(status_code=400, detail=exc.detail)


@router.get("/quizzes", response_model=AdminQuizScheduleListResponse)
async def list_admin_quiz_schedules(
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
    cycle_number: Optional[int] = Query(None, description="Filter by quiz cycle number"),
    semester_id: Optional[UUID] = Query(None, description="Filter by semester"),
    session_id: Optional[UUID] = Query(None, description="Filter by academic session"),
):
    """
    Phase 24.8: scoped quiz schedule list (the admin configuration/plan).

    Authorization: ``require_any_admin`` + server-side subject scope — HEAD
    all, CLASS assigned section's semester, ELECTIVE exact subject,
    SUBSECTION inert. Read-only. Filters only NARROW the scope-derived set.
    """
    try:
        return await AdminQuizService(db).list_quiz_schedules(
            current_user,
            cycle_number=cycle_number,
            semester_id=semester_id,
            session_id=session_id,
        )
    except AdminQuizError as exc:
        _raise_quiz_error(exc)


@router.get("/quizzes/{schedule_id}", response_model=AdminQuizScheduleResponse)
async def get_admin_quiz_schedule(
    schedule_id: UUID,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.8: scoped quiz schedule detail.  Out-of-scope/nonexistent -> 404
    (no existence leak).
    """
    try:
        return await AdminQuizService(db).get_quiz_schedule(current_user, schedule_id)
    except AdminQuizError as exc:
        _raise_quiz_error(exc)


@router.get("/quiz-cycles", response_model=AdminQuizCycleListResponse)
async def list_admin_quiz_cycles(
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.8: quiz cycle + policy read model (thresholds shown as the
    persisted configuration; no mutation of eligibility policy here).
    """
    try:
        return await AdminQuizService(db).list_quiz_cycles(current_user)
    except AdminQuizError as exc:
        _raise_quiz_error(exc)


@router.post("/quizzes", response_model=AdminQuizScheduleMutationResponse, status_code=201)
async def create_admin_quiz_schedule(
    request: CreateQuizScheduleRequest,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.8: create a quiz schedule (HEAD_ADMIN only).

    Validates subject/cycle/elective relationship/date, rejects duplicate
    (subject, cycle) with 409, and synchronizes the derived QUIZ_DAY
    AcademicEvent atomically — the schedule and its event reality commit
    together (or roll back together).
    """
    try:
        return await AdminQuizService(db).create_quiz_schedule(_admin, request)
    except AdminQuizError as exc:
        _raise_quiz_error(exc)


@router.patch("/quizzes/{schedule_id}", response_model=AdminQuizScheduleMutationResponse)
async def update_admin_quiz_schedule(
    schedule_id: UUID,
    request: UpdateQuizScheduleRequest,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.8: update a quiz schedule (HEAD_ADMIN only).

    Explicit-PATCH: omitted fields unchanged; explicit null clears the date
    (→ UNRESOLVED). The resulting state is validated and the QUIZ_DAY event
    reality is synchronized atomically (old event retired when the date moves
    or the schedule is cancelled; new event created when scheduled+dated).
    Idempotent — no duplicate events.
    """
    try:
        return await AdminQuizService(db).update_quiz_schedule(_admin, schedule_id, request)
    except AdminQuizError as exc:
        _raise_quiz_error(exc)

# ===========================================================================
# Phase 24.9 — Admin Event Manager
# ===========================================================================

def _raise_event_admin_error(exc: AdminEventDomainError) -> None:
    """Map admin-event domain failures to HTTP: 403/404/409/422 (401 handled
    by the dependency layer)."""
    raise HTTPException(status_code=exc.http_status, detail=exc.detail)


@router.get("/events", response_model=AdminEventListResponse)
async def list_admin_events(
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
    active: Optional[bool] = Query(None, description="True=active only; False=inactive only; omitted=all"),
    event_type: Optional[EventType] = Query(None, description="Filter by event type"),
    subject_id: Optional[UUID] = Query(None, description="Filter by subject"),
    elective_slot: Optional[ElectiveSlot] = Query(None, description="Filter by elective slot"),
    class_type: Optional[ClassType] = Query(None, description="Filter by class type"),
    date_from: Optional[datetime.date] = Query(None, description="Inclusive lower bound"),
    date_to: Optional[datetime.date] = Query(None, description="Inclusive upper bound"),
):
    """
    Phase 24.9: scoped admin event list over the EXISTING AcademicEvent
    architecture.  Reads are server-scoped (HEAD all, CLASS own semester,
    ELECTIVE exact subject, global events HEAD-only, SUBSECTION inert).
    QUIZ_DAY events backed by a quiz schedule are labeled
    ``quiz_schedule_managed`` and must be edited through /admin/quizzes.
    """
    try:
        return await AdminEventService(db).list_events(
            current_user,
            active=active,
            event_type=event_type,
            subject_id=subject_id,
            elective_slot=elective_slot,
            class_type=class_type,
            date_from=date_from,
            date_to=date_to,
        )
    except AdminEventDomainError as exc:
        _raise_event_admin_error(exc)


@router.get("/events/{event_id}", response_model=AdminEventResponse)
async def get_admin_event(
    event_id: UUID,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """Phase 24.9: scoped admin event detail.  Out-of-scope/nonexistent -> 404."""
    try:
        return await AdminEventService(db).get_event(current_user, event_id)
    except AdminEventDomainError as exc:
        _raise_event_admin_error(exc)


@router.post("/events", response_model=AdminEventMutationResponse, status_code=201)
async def create_admin_event(
    payload: AcademicEventCreate,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.9: create an event through the canonical EventService (registry
    validation + duplicate guard + EventSessionSynchronizer + one transaction).
    QUIZ_DAY events that would be quiz-schedule managed are refused (409) —
    quiz dates belong to /admin/quizzes.
    """
    try:
        return await AdminEventService(db).create_event(current_user, payload)
    except AdminEventDomainError as exc:
        _raise_event_admin_error(exc)


@router.patch("/events/{event_id}", response_model=AdminEventMutationResponse)
async def update_admin_event(
    event_id: UUID,
    payload: AcademicEventUpdate,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.9: partial event update through EventService (PATCH semantics;
    absent = unchanged; canonical revalidation + session reconciliation).
    A quiz-schedule-managed QUIZ_DAY event is refused (409).
    """
    try:
        return await AdminEventService(db).update_event(current_user, event_id, payload)
    except AdminEventDomainError as exc:
        _raise_event_admin_error(exc)


@router.delete("/events/{event_id}", response_model=AdminEventMutationResponse)
async def deactivate_admin_event(
    event_id: UUID,
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.9: safe event deactivation (reversible lifecycle — no physical
    deletion; the row is preserved and the engine stops considering it).
    A quiz-schedule-managed QUIZ_DAY event is refused (409).
    """
    try:
        return await AdminEventService(db).deactivate_event(current_user, event_id)
    except AdminEventDomainError as exc:
        _raise_event_admin_error(exc)
