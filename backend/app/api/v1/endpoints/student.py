from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.student import StudentProfile

router = APIRouter()

@router.get("/me", response_model=StudentProfile)
async def get_student_profile(current_user: User = Depends(get_current_user)):
    """
    Returns the authenticated student's profile.
    """
    section_name = current_user.section.name if current_user.section else None
    return StudentProfile(
        id=current_user.id,
        firebase_uid=current_user.firebase_uid,
        email=current_user.email,
        display_name=current_user.display_name,
        roll_number=current_user.roll_number,
        section_name=section_name
    )
