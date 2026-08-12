from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.repositories.timetable_repo import TimetableRepository
from app.schemas.timetable import TimetableEntryResponse

router = APIRouter()

@router.get("", response_model=List[TimetableEntryResponse])
async def get_timetable(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the weekly recurring timetable entries for the student's section.
    """
    if not current_user.section_id:
        raise HTTPException(status_code=400, detail="User is not assigned to a section")
        
    repo = TimetableRepository(db)
    entries = await repo.get_weekly_entries_for_section(current_user.section_id)
    return entries
