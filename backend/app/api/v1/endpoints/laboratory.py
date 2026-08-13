from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.models.academic import StudentEnrollment
from app.repositories.laboratory_repo import LaboratoryRepository
from app.repositories.subject_repo import SubjectRepository
from app.schemas.laboratory import LaboratoryExperimentResponse, LaboratoryRecordResponse

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
