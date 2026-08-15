from datetime import date
from uuid import UUID
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.models.enums import AttendanceStatus
from app.services.attendance_service import AttendanceService
from app.schemas.attendance import (
    SubjectAttendanceSummary, 
    AttendanceHistoryResponse,
    DailySessionsResponse
)
from app.repositories.subject_repo import SubjectRepository
from app.repositories.attendance_repo import AttendanceRepository

router = APIRouter()

@router.get("/history", response_model=AttendanceHistoryResponse)
async def get_attendance_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    subject_code: Optional[str] = Query(None, description="Restrict to an enrolled subject code"),
    status: Optional[str] = Query(
        None,
        pattern="^(Attended|Missed|Pending|Cancelled)$",
        description="Restrict to an attendance state; Cancelled is a session state, not a record value",
    ),
    date_from: Optional[date] = Query(None, description="Inclusive range start (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Inclusive range end (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, max_length=100, description="Search subject code/name, class type, or date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns every scheduled class session of the authenticated student's
    enrolled subjects from the semester start through the current date
    (clamped to their real academic context), with their canonical attendance
    state: Attended / Missed / Pending (no record) / Cancelled. Same records
    Track consumes. Supports filtering and limit/offset pagination.
    """
    service = AttendanceService(db)
    return await service.get_history(
        user=current_user,
        limit=limit,
        offset=offset,
        subject_code=subject_code,
        status=status,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )

@router.get("/daily/{target_date}", response_model=DailySessionsResponse)
async def get_daily_sessions(
    target_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all class sessions scheduled for a given date along with 
    their current attendance state for the authenticated student.
    """
    service = AttendanceService(db)
    return await service.get_daily_sessions(
        user_id=current_user.id,
        target_date=target_date
    )

class AttendanceMutationRequest(BaseModel):
    class_session_id: UUID
    status: AttendanceStatus

class AttendanceMutationResponse(BaseModel):
    id: UUID
    student_id: UUID
    class_session_id: UUID
    status: AttendanceStatus

    class Config:
        from_attributes = True

@router.get("/summary/{subject_code}", response_model=SubjectAttendanceSummary)
async def get_attendance_summary(
    subject_code: str,
    as_of_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns aggregated attendance statistics and engine-optimized projections
    for a subject. `as_of_date` defaults to the request-time current date (the
    import-time `date.today()` default was removed — the date is resolved per
    request). The subject must be one of the authenticated student's
    enrollments (Phase 8.1 enrollment scope, mirroring the quiz endpoint).
    """
    subject_repo = SubjectRepository(db)
    subject = await subject_repo.get_by_code(subject_code)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Enrollment scope: a student must not obtain analytics for a subject they
    # are not enrolled in (established repository authorization pattern).
    enrolled = await AttendanceRepository(db).is_enrolled(current_user.id, subject.id)
    if not enrolled:
        raise HTTPException(status_code=404, detail="Subject not found")

    effective_date = as_of_date if as_of_date is not None else date.today()
    service = AttendanceService(db)
    summary = await service.get_summary(
        user_id=current_user.id,
        subject_id=subject.id,
        subject_code=subject.code,
        as_of_date=effective_date
    )
    return summary

@router.post("", response_model=AttendanceMutationResponse, status_code=status.HTTP_200_OK)
async def mutate_attendance(
    request: AttendanceMutationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Marks attendance for a specific class session.
    """
    service = AttendanceService(db)
    try:
        record = await service.record_attendance(
            user_id=current_user.id,
            class_session_id=request.class_session_id,
            status=request.status
        )
        return record
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
