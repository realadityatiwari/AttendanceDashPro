from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.models.enums import ElectiveSlot
from app.schemas.student import StudentProfile, StudentSyncRequest
from app.services.student_context_service import StudentContextService

router = APIRouter()

@router.post("/sync", response_model=StudentProfile)
async def sync_student_profile(
    request: StudentSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Local authentication sync endpoint.
    Maintains compatibility with the legacy frontend sync call (JWT-authenticated).
    """
    user = current_user
    
    # Update mutable profile fields ONLY if they are not already set.
    # PostgreSQL remains the authoritative source for identity.
    if not user.name:
        user.name = request.display_name
    if not user.roll_number:
        user.roll_number = request.roll_number
    
    await db.commit()
    await db.refresh(user)
    
    section_name = user.section.name if user.section else None
    return StudentProfile(
        id=user.id,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        display_name=user.name,
        roll_number=user.roll_number,
        section_name=section_name
    )

@router.get("/me", response_model=StudentProfile)
async def get_student_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the authenticated student's profile, including read-only
    academic context resolved from the authoritative student-context service
    (Phase 23.4): placement (section -> semester -> academic session,
    subsection), the student's quiz schedules, and the student's elective
    choices.
    """
    ctx = await StudentContextService(db).get_context(current_user)
    return StudentProfile(
        id=current_user.id,
        role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        display_name=current_user.name,
        roll_number=current_user.roll_number,
        section_name=ctx.section_name,
        subsection_name=ctx.subsection_name,
        program=ctx.program,
        semester_name=ctx.semester_name,
        academic_session=ctx.academic_session_name,
        semester_start=ctx.semester_start,
        semester_end=ctx.semester_end,
        first_quiz_date=ctx.first_quiz_date,
        elective_i=ctx.elective_choices.get(ElectiveSlot.ELECTIVE_I),
        elective_ii=ctx.elective_choices.get(ElectiveSlot.ELECTIVE_II),
    )
