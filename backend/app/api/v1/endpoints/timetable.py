from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.models.academic import StudentElectiveChoice
from app.models.enums import ElectiveSlot
from app.repositories.timetable_repo import TimetableRepository
from app.schemas.timetable import TimetableEntryResponse

router = APIRouter()


@router.get("", response_model=List[TimetableEntryResponse])
async def get_timetable(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the weekly recurring timetable entries for the student's section.

    Phase 22.3: the institutional timetable stays SHARED by section. The
    shared Department Elective-I / Elective-II slots are resolved to the
    authenticated student's selected subjects (their StudentElectiveChoice);
    every other entry is returned unchanged. A student with no recorded
    selection keeps the timetable's anchor subject (no fabricated choice).
    """
    if not current_user.section_id:
        raise HTTPException(status_code=400, detail="User is not assigned to a section")

    repo = TimetableRepository(db)
    entries = await repo.get_weekly_entries_for_section(current_user.section_id)

    # Resolve the student's elective choices once (row per elective slot).
    result = await db.execute(
        select(StudentElectiveChoice).where(
            StudentElectiveChoice.user_id == current_user.id
        )
    )
    choices = {
        c.elective_slot: c.subject for c in result.scalars().all()
    }

    resolved = []
    for entry in entries:
        chosen = choices.get(entry.elective_slot) if entry.elective_slot is not None else None
        if chosen is not None:
            resolved.append(
                TimetableEntryResponse(
                    id=entry.id,
                    day_of_week=entry.day_of_week,
                    class_type=entry.class_type,
                    subject=chosen,
                )
            )
        else:
            resolved.append(entry)
    return resolved