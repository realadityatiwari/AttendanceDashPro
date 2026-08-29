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
    Returns the weekly recurring timetable entries applicable to the student.

    Phase 24.7-G: the student timetable is DERIVED from the student's academic
    context (section + subsection), their LOCKED elective choices, and the
    authoritative timetable — never from hardcoded current-semester
    assumptions.

      - Section: entries scoped to the student's section.
      - Subsection: section-wide entries PLUS entries for the student's own
        subsection (when assigned); subsection-private entries for OTHER
        subsections are excluded (no schedule leakage). A student with no
        subsection sees section-wide entries only.
      - Active only: deactivated (``is_active=false``) entries are excluded —
        the timetable is the EXPECTED schedule; actual occurrences
        (class_sessions) remain a separate concept and are NOT collapsed here.
      - Electives: a shared Department Elective-I / Elective-II slot resolves
        to the student's LOCKED concrete subject (their StudentElectiveChoice).
        A slot entry with NO recorded choice is OMITTED — the anchor subject
        (BCS-054 / BCS-058) is never exposed merely because it exists in the
        timetable configuration.
      - Common subjects: returned unchanged for applicable students.
    """
    if not current_user.section_id:
        raise HTTPException(status_code=400, detail="User is not assigned to a section")

    repo = TimetableRepository(db)
    entries = await repo.get_weekly_entries_for_student(
        current_user.section_id, current_user.subsection_id
    )

    # Load the student's locked elective choices once (row per elective slot).
    resolver = ElectiveResolver(db)
    choices = await resolver.load_choices(current_user.id)

    resolved = []
    for entry in entries:
        if entry.elective_slot is not None:
            chosen = choices.get(entry.elective_slot)
            if chosen is None:
                # No locked choice for this slot: omit the entry rather than
                # expose the shared anchor subject as if it were the
                # student's elective.
                continue
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
