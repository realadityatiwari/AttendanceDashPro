from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.services.eligibility_service import EligibilityService
from app.schemas.attendance import EligibilityResult
from app.repositories.subject_repo import SubjectRepository

router = APIRouter()

@router.get("/{subject_code}/{quiz_cycle}", response_model=EligibilityResult)
async def get_quiz_eligibility(
    subject_code: str,
    quiz_cycle: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the quiz eligibility status computed by the eligibility engine.
    """
    subject_repo = SubjectRepository(db)
    subject = await subject_repo.get_by_code(subject_code)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
        
    service = EligibilityService(db)
    result = await service.get_quiz_eligibility(
        user_id=current_user.id,
        subject_id=subject.id,
        quiz_cycle=quiz_cycle
    )
    return result
