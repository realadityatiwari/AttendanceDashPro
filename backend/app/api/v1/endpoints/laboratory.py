from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.api.dependencies.deps import get_db, get_current_user, require_admin
from app.models.user import User
from app.models.academic import StudentEnrollment
from app.repositories.laboratory_repo import LaboratoryRepository
from app.repositories.subject_repo import SubjectRepository
from app.services.laboratory_service import LaboratoryService
from app.schemas.laboratory import (
    LaboratoryExperimentResponse,
    LaboratoryRecordResponse,
    MidSemDesignationPayload,
    MidSemDesignationResponse,
)

router = APIRouter()

async def _get_enrolled_subject(subject_code: str, user_id, db: AsyncSession):
    subject_repo = SubjectRepository(db)
    subject = await subject_repo.get_by_code(subject_code)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    enrollment = await db.execute(select(StudentEnrollment).filter_by(
        user_id=user_id, subject_id=subject.id
    ))
    if not enrollment.scalars().first():
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject

@router.get("/{subject_code}/experiments", response_model=List[LaboratoryExperimentResponse])
async def get_lab_experiments(
    subject_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the experiments defined for a specific lab subject.
    """
    subject = await _get_enrolled_subject(subject_code, current_user.id, db)
    repo = LaboratoryRepository(db)
    experiments = await repo.get_experiments_for_subject(subject.id)
    return experiments

@router.get("/{subject_code}/records", response_model=List[LaboratoryRecordResponse])
async def get_lab_records(
    subject_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the student's progress and signatures for a specific lab subject.
    """
    subject = await _get_enrolled_subject(subject_code, current_user.id, db)
    repo = LaboratoryRepository(db)
    records = await repo.get_student_records(current_user.id, subject.id)
    return records

@router.get("/{subject_code}/mid-sem", response_model=Optional[MidSemDesignationResponse])
async def get_mid_sem_designation(
    subject_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the designated mid-semester practical session for a lab subject
    (the actual scheduled PRACTICAL session, or 200 null when none is
    designated). Read-only; the same value is exposed on the attendance
    summary. The designation is a session-level fact - never inferred from
    experiment counts or a computed date.
    """
    await _get_enrolled_subject(subject_code, current_user.id, db)
    session = await LaboratoryService(db).get_mid_sem(subject_code)
    if session is None:
        return None
    return MidSemDesignationResponse(
        subject_code=subject_code,
        session_id=session.id,
        session_date=session.date,
        designated=True,
    )

@router.put("/{subject_code}/mid-sem", response_model=MidSemDesignationResponse)
async def designate_mid_sem(
    subject_code: str,
    payload: MidSemDesignationPayload,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    ADMIN-ONLY: designates an actual scheduled PRACTICAL class session of the
    subject as its mid-semester practical. The date comes from the real
    scheduled session - a mid-sem date is never computed. Designation replaces
    any prior one for the subject and does not alter attendance counting (the
    normal attendance mutation records attendance against the session).
    """
    session = await LaboratoryService(db).designate_mid_sem(subject_code, payload.class_session_id)
    return MidSemDesignationResponse(
        subject_code=subject_code,
        session_id=session.id,
        session_date=session.date,
        designated=True,
    )

@router.delete("/{subject_code}/mid-sem", response_model=MidSemDesignationResponse)
async def clear_mid_sem(
    subject_code: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    ADMIN-ONLY: clears the subject's mid-semester practical designation.
    Attendance records on the session are untouched (attendance is never
    deleted by a designation change).
    """
    await LaboratoryService(db).clear_mid_sem(subject_code)
    return MidSemDesignationResponse(
        subject_code=subject_code,
        session_id=None,
        session_date=None,
        designated=False,
    )
