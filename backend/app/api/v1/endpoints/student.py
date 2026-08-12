from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.api.dependencies.deps import get_db, get_current_user, get_firebase_identity
from app.models.user import User
from app.schemas.student import StudentProfile, StudentSyncRequest

router = APIRouter()

@router.post("/sync", response_model=StudentProfile)
async def sync_student_profile(
    request: StudentSyncRequest,
    firebase_identity: dict = Depends(get_firebase_identity),
    db: AsyncSession = Depends(get_db)
):
    """
    Synchronizes the Firebase Auth profile with the PostgreSQL database.
    Performs a get-or-create operation based on the firebase_uid.
    Requires a valid Firebase ID token but does not require the user to already exist in DB.
    The firebase_uid is sourced exclusively from the verified token; it cannot be
    supplied or spoofed by the request body.
    """
    uid = firebase_identity.get("uid")
    # Email comes from the verified Firebase token only — not from the request body.
    # It is not stored in PostgreSQL (the User model has no email column).
    # Firebase Auth is the single source of truth for email.
    
    result = await db.execute(select(User).filter_by(firebase_uid=uid))
    user = result.scalars().first()
    
    if user:
        # Update mutable profile fields only — firebase_uid is immutable.
        user.name = request.display_name
        user.roll_number = request.roll_number
    else:
        user = User(
            firebase_uid=uid,
            name=request.display_name,
            roll_number=request.roll_number
        )
        db.add(user)
    
    await db.commit()
    await db.refresh(user)
    
    section_name = user.section.name if user.section else None
    return StudentProfile(
        id=user.id,
        firebase_uid=user.firebase_uid,
        display_name=user.name,
        roll_number=user.roll_number,
        section_name=section_name
    )

@router.get("/me", response_model=StudentProfile)
async def get_student_profile(current_user: User = Depends(get_current_user)):
    """
    Returns the authenticated student's profile.
    """
    section_name = current_user.section.name if current_user.section else None
    return StudentProfile(
        id=current_user.id,
        firebase_uid=current_user.firebase_uid,
        display_name=current_user.name,
        roll_number=current_user.roll_number,
        section_name=section_name
    )
