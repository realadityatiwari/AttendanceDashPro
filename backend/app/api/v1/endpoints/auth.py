import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, field_validator

from app.models.user import User, Section
from app.models.enums import UserRole, ElectiveSlot, EnrollmentType
from app.models.academic import AcademicSession, Semester, Subject, StudentEnrollment, StudentElectiveChoice
from app.core.security import verify_password, create_access_token, hash_password, DUMMY_PASSWORD_HASH
from app.core.logging import get_logger
from app.core.rate_limit import rate_limit
from app.api.dependencies.deps import get_db

router = APIRouter()
logger = get_logger(__name__)

class LoginRequest(BaseModel):
    roll_number: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    roll_number: str
    password: str
    # Phase 22.3: Department Elective selection (subject codes). Required for
    # every new student account. Validation is backend-authoritative against
    # the DB catalog (Phase 23.5 — subjects.elective_slot). The Pydantic model
    # accepts any non-empty string; the async endpoint validates against the
    # active semester's catalog.
    elective_i: str
    elective_ii: str

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Backend-authoritative password policy:
        - Minimum 8 characters
        - Maximum 128 characters (PBKDF2 DoS protection)
        - At least one letter and one digit
        Existing accounts are NOT invalidated; this policy applies at registration.
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must not exceed 128 characters")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit(10, 900, "login")),
):
    # 1. Find user by roll_number
    result = await db.execute(select(User).filter_by(roll_number=credentials.roll_number))
    user = result.scalars().first()
    
    # 2. Verify password (constant time comparison prevents timing attacks).
    # To prevent user enumeration through timing, always run a PBKDF2
    # verification even when the user does not exist (dummy hash). This
    # equalizes the response time for existing vs. nonexistent accounts.
    if not user or not user.hashed_password:
        verify_password(credentials.password, DUMMY_PASSWORD_HASH)
        logger.warning("Login failed: roll_number not found or no password set")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect roll number or password",
        )
        
    if not verify_password(credentials.password, user.hashed_password):
        logger.warning("Login failed: incorrect password for roll_number=%s", credentials.roll_number)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect roll number or password",
        )
        
    # 3. Generate JWT
    access_token = create_access_token(subject=str(user.id), roll_number=user.roll_number)
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit(5, 3600, "register")),
):
    """
    Creates a PostgreSQL-native student account and provisions its academic
    enrollment in a single transaction.
    ...
    """
    name = request.name.strip()
    roll_number = request.roll_number.strip()
    elective_i_code = request.elective_i.strip()
    elective_ii_code = request.elective_ii.strip()

    # --- Validation (backend is authoritative) ---
    if not name:
        raise HTTPException(status_code=422, detail="Full name is required")
    if not re.fullmatch(r"\d{13}", roll_number):
        raise HTTPException(status_code=422, detail="Roll number must be 13 digits")
    # Password validation is enforced by the Pydantic model (RegisterRequest)

    # --- Resolve authoritative academic context ---
    result = await db.execute(select(AcademicSession).where(AcademicSession.is_active == True))  # noqa: E712
    acad_session = result.scalars().first()
    if not acad_session:
        raise HTTPException(status_code=503, detail="No active academic session is configured")

    result = await db.execute(select(Semester).where(Semester.session_id == acad_session.id))
    semesters = list(result.scalars().all())
    if len(semesters) != 1:
        raise HTTPException(
            status_code=409,
            detail="Academic configuration is ambiguous (multiple semesters). Registration cannot auto-assign.",
        )
    semester = semesters[0]

    result = await db.execute(select(Section).where(Section.semester_id == semester.id))
    sections = list(result.scalars().all())
    if len(sections) == 0:
        raise HTTPException(status_code=503, detail="No section is configured for the active semester")
    if len(sections) > 1:
        raise HTTPException(
            status_code=409,
            detail="Multiple sections exist. Section selection is not implemented; registration cannot auto-assign.",
        )
    section = sections[0]

    result = await db.execute(select(Subject).where(Subject.semester_id == semester.id))
    subjects = list(result.scalars().all())

    # --- Validate elective selection against the authoritative DB catalog ---
    # Phase 23.5: the catalog is subjects.elective_slot, scoped to the active
    # semester. An invalid selection is rejected 422 (same contract the old
    # Pydantic catalog validators produced).
    catalog_i = [s.code for s in subjects if s.elective_slot == ElectiveSlot.ELECTIVE_I]
    catalog_ii = [s.code for s in subjects if s.elective_slot == ElectiveSlot.ELECTIVE_II]
    if elective_i_code not in catalog_i:
        raise HTTPException(status_code=422, detail="Invalid Department Elective-I selection")
    if elective_ii_code not in catalog_ii:
        raise HTTPException(status_code=422, detail="Invalid Department Elective-II selection")

    # --- Create user + enrollments transactionally ---
    user = User(
        roll_number=roll_number,
        name=name,
        hashed_password=hash_password(request.password),
        section_id=section.id,
    )
    db.add(user)

    try:
        await db.flush()  # materialize user.id; duplicate roll_number surfaces here
        # Phase 22.3: enroll in every non-elective subject PLUS the student's
        # chosen Department Elective-I / Elective-II subjects. The other
        # elective options are NOT enrolled (each student has their own
        # selections; the shared timetable resolves the slot per student).
        # Phase 23.5: slot membership comes from subjects.elective_slot (the
        # authoritative catalog), not the legacy free-form tag.
        elective_i_subject = None
        elective_ii_subject = None
        for subject in subjects:
            if subject.elective_slot == ElectiveSlot.ELECTIVE_I:
                if subject.code == elective_i_code:
                    elective_i_subject = subject
            elif subject.elective_slot == ElectiveSlot.ELECTIVE_II:
                if subject.code == elective_ii_code:
                    elective_ii_subject = subject
            else:
                db.add(StudentEnrollment(
                    user_id=user.id,
                    subject_id=subject.id,
                    enrollment_type=EnrollmentType.COMPULSORY,
                ))

        if elective_i_subject is None or elective_ii_subject is None:
            # The codes passed the catalog validation above, so a missing
            # subject row here means the semester configuration is broken.
            await db.rollback()
            raise HTTPException(
                status_code=503,
                detail="The selected elective subjects are not configured for the active semester",
            )

        db.add(StudentEnrollment(user_id=user.id, subject_id=elective_i_subject.id, enrollment_type=EnrollmentType.ELECTIVE))
        db.add(StudentEnrollment(user_id=user.id, subject_id=elective_ii_subject.id, enrollment_type=EnrollmentType.ELECTIVE))
        db.add(StudentElectiveChoice(
            user_id=user.id,
            elective_slot=ElectiveSlot.ELECTIVE_I,
            subject_id=elective_i_subject.id,
        ))
        db.add(StudentElectiveChoice(
            user_id=user.id,
            elective_slot=ElectiveSlot.ELECTIVE_II,
            subject_id=elective_ii_subject.id,
        ))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="An account with this roll number already exists")
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=503, detail="Unable to create account. Please try again.")

    await db.refresh(user)

    # --- Issue the same JWT used by login ---
    access_token = create_access_token(subject=str(user.id), roll_number=user.roll_number)
    return {"access_token": access_token, "token_type": "bearer"}