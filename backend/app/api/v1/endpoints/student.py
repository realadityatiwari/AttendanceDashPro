from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.student import StudentProfile, StudentSyncRequest
from app.repositories.user_repo import UserRepository

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
    academic context resolved from the section -> semester -> session
    chain, the student's quiz schedules, and the student's authoritative
    academic assignment (subsection, elective choices — Phase 23.3).
    """
    repo = UserRepository(db)
    academic_context = await repo.get_academic_context(current_user)
    elective_codes = await repo.get_elective_codes(current_user.id)
    section_name = current_user.section.name if current_user.section else None
    subsection_name = current_user.subsection.name if current_user.subsection else None
    return StudentProfile(
        id=current_user.id,
        role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        display_name=current_user.name,
        roll_number=current_user.roll_number,
        section_name=section_name,
        subsection_name=subsection_name,
        **academic_context,
        **elective_codes,
    )
