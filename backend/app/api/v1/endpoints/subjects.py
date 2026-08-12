from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.subject import SubjectResponse

router = APIRouter()

@router.get("", response_model=List[SubjectResponse])
async def get_enrolled_subjects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the subjects enrolled by the authenticated student.
    """
    repo = UserRepository(db)
    subjects = await repo.get_enrolled_subjects(current_user.id)
    return subjects
