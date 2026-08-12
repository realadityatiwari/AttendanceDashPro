from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.repositories.calendar_repo import CalendarRepository
from app.schemas.calendar import AcademicEventResponse

router = APIRouter()

@router.get("", response_model=List[AcademicEventResponse])
async def get_all_events(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all academic events.
    Mutation is explicitly out of scope for students.
    """
    repo = CalendarRepository(db)
    events = await repo.get_all_events()
    return events
