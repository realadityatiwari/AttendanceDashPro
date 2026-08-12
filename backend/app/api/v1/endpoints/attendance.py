from datetime import date
from uuid import UUID
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.models.enums import AttendanceStatus
from app.services.attendance_service import AttendanceService
from app.schemas.attendance import SubjectAttendanceSummary
from app.repositories.subject_repo import SubjectRepository

router = APIRouter()

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
    as_of_date: date = date.today(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns aggregated attendance statistics and engine-optimized projections for a subject.
    """
    subject_repo = SubjectRepository(db)
    subject = await subject_repo.get_by_code(subject_code)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
        
    service = AttendanceService(db)
    summary = await service.get_summary(
        user_id=current_user.id,
        subject_id=subject.id,
        subject_code=subject.code,
        as_of_date=as_of_date
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
