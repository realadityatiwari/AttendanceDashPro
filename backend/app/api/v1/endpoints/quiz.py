from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import date
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.models.academic import StudentEnrollment
from app.services.eligibility_service import EligibilityService
from app.services.student_context_service import StudentContextService
from app.schemas.attendance import EligibilityResult, CurrentQuizCycle
from app.repositories.subject_repo import SubjectRepository

router = APIRouter()

@router.get("/current-cycle", response_model=CurrentQuizCycle)
async def get_current_quiz_cycle(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the canonical currently-relevant quiz cycle for the authenticated
    student (next upcoming SCHEDULED quiz, else the latest resolved cycle,
    else the documented fallback Quiz I) so the Quiz Eligibility page can
    preselect a deterministic, date-aware default tab. Read-only; the user's
    manual tab selection lives client-side and never mutates state.
    """
    service = EligibilityService(db)
    return await service.get_current_quiz_cycle(current_user.id)

@router.get("/{subject_code}/{quiz_cycle}", response_model=EligibilityResult)
async def get_quiz_eligibility(
    subject_code: str,
    quiz_cycle: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the quiz eligibility status computed by the eligibility engine.
    """
    subject_repo = SubjectRepository(db)
    subject = await subject_repo.get_by_code(subject_code)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
        
    # Scope to the authenticated student's enrollments
    enrollment = await db.execute(select(StudentEnrollment).filter_by(
        user_id=current_user.id, subject_id=subject.id
    ))
    if not enrollment.scalars().first():
        raise HTTPException(status_code=404, detail="Subject not found")
        
    # Resolve the attendance-window start from the authoritative student
    # context (Phase 23.4). Falls back to today when the student has no
    # section/semester placement (identical to the previous behavior).
    ctx = await StudentContextService(db).get_placement(current_user)
    semester_start = ctx.semester_start if ctx.semester_start is not None else date.today()
        
    service = EligibilityService(db)
    result = await service.get_quiz_eligibility(
        user_id=current_user.id,
        subject_id=subject.id,
        quiz_cycle=quiz_cycle,
        semester_start=semester_start,
    )
    return result
