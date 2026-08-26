from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.repositories.timetable_repo import TimetableRepository
from app.schemas.timetable import TimetableEntryResponse
from app.services.elective_resolver import ElectiveResolver

router = APIRouter()


@router.get("", response_model=List[TimetableEntryResponse])
async def get_timetable(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the weekly recurring timetable entries for the student's section.

    Phase 22.3/22.4: the institutional timetable stays SHARED by section. The
    shared Department Elective-I / Elective-II slots are resolved to the
    authenticated student's selected subjects (their StudentElectiveChoice);
    every other entry is returned unchanged. A student with no recorded
    selection keeps the timetable's anchor subject (no fabricated choice).
    `elective_slot` marks which shared slot a resolved entry belongs to.
    """
    if not current_user.section_id:
        raise HTTPException(status_code=400, detail="User is not assigned to a section")

    repo = TimetableRepository(db)
    entries = await repo.get_weekly_entries_for_section(current_user.section_id)

    # Load the student's elective choices once (row per elective slot).
    resolver = ElectiveResolver(db)
    choices = await resolver.load_choices(current_user.id)

    resolved = []
    for entry in entries:
        if entry.elective_slot is not None:
            chosen = choices.get(entry.elective_slot)
            if chosen is not None:
                resolved.append(
                    TimetableEntryResponse(
                        id=entry.id,
                        day_of_week=entry.day_of_week,
                        class_type=entry.class_type,
                        subject=chosen.subject,
                        elective_slot=entry.elective_slot,
                    )
                )
                continue
        resolved.append(entry)
    return resolved
