import re
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, field_validator

from app.models.user import User, Section
from app.models.enums import UserRole, ElectiveSlot
from app.models.academic import AcademicSession, Semester, Subject
from app.core.security import verify_password, create_access_token, hash_password, DUMMY_PASSWORD_HASH
from app.core.config import settings
from app.core.logging import get_logger
from app.core.rate_limit import rate_limit
from app.api.dependencies.deps import get_db, get_current_user
from app.services.refresh_token_service import RefreshTokenService, RefreshTokenError
from app.services.password_reset_service import PasswordResetService, PasswordResetError
from app.services.enrollment_service import apply_new_student_enrollments
from types import SimpleNamespace

router = APIRouter()
logger = get_logger(__name__)

class LoginRequest(BaseModel):
    roll_number: str
    password: str

def validate_password_policy(v: str) -> str:
    """Backend-authoritative password policy, shared by registration and
    authenticated password change so the rule cannot drift between them:
    - Minimum 8 characters
    - Maximum 128 characters (PBKDF2 DoS protection)
    - At least one letter and one digit
    Existing accounts are NOT invalidated; this policy applies when a password
    is set (registration or an authenticated change).
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
        return validate_password_policy(v)


class ChangePasswordRequest(BaseModel):
    """Authenticated password change. The account is the authenticated
    principal only — no user id or roll number is accepted."""
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_policy(v)


class ResetPasswordRequest(BaseModel):
    """Stage 3A public redemption. Possession of a valid single-use reset
    token is the recovery proof — no login or current password is accepted.
    The reset token is submitted in the request BODY, never a URL."""
    reset_token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_policy(v)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Refresh-token cookie helpers (opaque secret, HttpOnly, never in JSON) ──

def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=settings.REFRESH_COOKIE_PATH,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
    )

@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    response: Response,
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
        
    if not getattr(user, 'is_active', True):
        logger.warning("Login failed: account deactivated for roll_number=%s", credentials.roll_number)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated. Please contact an administrator.",
        )
        
    # 3. Generate JWT
    access_token = create_access_token(subject=str(user.id), roll_number=user.roll_number)

    # 4. Issue the refresh-token session (new family) and deliver it via an
    #    HttpOnly cookie. The response contract is unchanged (additive only).
    raw_refresh, _row = await RefreshTokenService(db).issue(user)
    await db.commit()
    _set_refresh_cookie(response, raw_refresh)

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    response: Response,
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
        # Phase 22.3/23.5: enroll in every non-elective subject PLUS the
        # student's chosen Department Elective-I / Elective-II subjects. The
        # other elective options are NOT enrolled (each student has their own
        # selections; the shared timetable resolves the slot per student).
        # Slot membership comes from subjects.elective_slot (the authoritative
        # catalog).
        #
        # [Chunk 16] The enrollment construction is centralized in
        # EnrollmentService (the single authoritative writer implementing
        # "non-elective subjects UNION the StudentElectiveChoice-resolved
        # selection per configured slot"), so every writer shares one
        # invariant. Registration's own semantics are unchanged: the two
        # selected codes become the per-slot choices below, EnrollmentType is
        # set explicitly by the service, and an unresolvable selection aborts
        # atomically (same 503 as before, nothing enrolled).
        fallback_subjects: dict = {}
        for subject in subjects:
            if subject.elective_slot == ElectiveSlot.ELECTIVE_I and subject.code == elective_i_code:
                fallback_subjects[ElectiveSlot.ELECTIVE_I] = subject
            elif subject.elective_slot == ElectiveSlot.ELECTIVE_II and subject.code == elective_ii_code:
                fallback_subjects[ElectiveSlot.ELECTIVE_II] = subject

        choices_by_slot = {
            ElectiveSlot.ELECTIVE_I: SimpleNamespace(elective_slot=ElectiveSlot.ELECTIVE_I,
                                                     subject=fallback_subjects.get(ElectiveSlot.ELECTIVE_I)),
            ElectiveSlot.ELECTIVE_II: SimpleNamespace(elective_slot=ElectiveSlot.ELECTIVE_II,
                                                      subject=fallback_subjects.get(ElectiveSlot.ELECTIVE_II)),
        }

        specs, missing_slots = apply_new_student_enrollments(
            db,
            user.id,
            subjects,
            choices_by_slot,
            fallback_subjects=fallback_subjects,
            include_choice_rows=True,
        )

        if missing_slots or not fallback_subjects.get(ElectiveSlot.ELECTIVE_I) or not fallback_subjects.get(ElectiveSlot.ELECTIVE_II):
            # The codes passed the catalog validation above, so a missing
            # subject row here means the semester configuration is broken.
            # [Chunk 16] The service added NOTHING when a slot is unresolvable
            # (atomic no-op), so this rollback discards only the user row.
            await db.rollback()
            raise HTTPException(
                status_code=503,
                detail="The selected elective subjects are not configured for the active semester",
            )

        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="An account with this roll number already exists")
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=503, detail="Unable to create account. Please try again.")

    await db.refresh(user)

    # --- Issue the same JWT used by login + a new refresh-token family ---
    access_token = create_access_token(subject=str(user.id), roll_number=user.roll_number)
    raw_refresh, _row = await RefreshTokenService(db).issue(user)
    await db.commit()
    _set_refresh_cookie(response, raw_refresh)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit(30, 900, "refresh")),
):
    """Rotate the refresh-token session presented in the HttpOnly cookie.

    Returns a fresh access token (same TokenResponse contract) and sets a new
    refresh cookie. Reuse/revocation/expiry → 401 with the SAME generic
    detail (no information about token existence is leaked); reuse also
    revokes the whole token family server-side.
    """
    raw = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not raw:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid refresh token"},
        )

    try:
        user, raw_new, _new_row = await RefreshTokenService(db).rotate(raw)
    except RefreshTokenError:
        # 401 with a cleared cookie. The cookie must be cleared on the actual
        # error response, so the 401 is returned directly (cookies set on the
        # injected Response do not survive an HTTPException).
        error_response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid refresh token"},
        )
        _clear_refresh_cookie(error_response)
        return error_response

    access_token = create_access_token(subject=str(user.id), roll_number=user.roll_number)

    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"access_token": access_token, "token_type": "bearer"},
    )
    _set_refresh_cookie(response, raw_new)
    return response


@router.patch("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit(5, 900, "change-password")),
):
    """Change the authenticated user's own password.

    - The account is the authenticated principal (get_current_user); no
      identifier is accepted in the request.
    - The current password is verified with the SAME verifier as login. A
      wrong current password returns 400 and leaves the stored hash untouched.
      (401 is deliberately NOT used: the frontend treats 401 as an expired
      session and would log the user out for a mistyped current password.)
    - On success only ``hashed_password`` is replaced and this user's
      refresh-token families are revoked, in one transaction. Existing
      short-lived access tokens are NOT invalidated (see the walkthrough for
      the documented limitation).
    - The response never includes a password or a hash.
    """
    if not current_user.hashed_password or not verify_password(
        request.current_password, current_user.hashed_password
    ):
        logger.warning("Password change rejected: incorrect current password for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = hash_password(request.new_password)
    await RefreshTokenService(db).revoke_all_for_user(current_user.id)
    await db.commit()
    logger.info("Password changed for user %s; refresh sessions revoked", current_user.id)
    return {"message": "Password updated"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit(10, 900, "reset-password")),
):
    """Stage 3A: redeem an admin-issued, single-use password-reset token.

    No authentication is required — possession of a valid reset token is the
    recovery proof. The token is hashed and looked up; unknown/expired/used/
    revoked tokens all return the SAME generic 400 (no token/account details).
    On success the password hash, token redemption, competing-token revocation
    and refresh-family revocation commit atomically. A raw token/password is
    never logged or returned. No session is created here.
    """
    try:
        await PasswordResetService(db).redeem(request.reset_token, request.new_password)
    except PasswordResetError:
        # Generic failure: never reveal whether the token/account exists.
        await db.rollback()
        logger.warning("Password reset rejected: invalid, expired, or used token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Password reset commit failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to reset password. Please try again.",
        )

    logger.info("Password reset completed via admin-issued reset token")
    return {"message": "Password updated"}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Server-side session revocation. Idempotent: safe when no/invalid
    refresh cookie exists. Revokes the presented token's family and clears
    the cookie; existing frontend logout behavior is unaffected."""
    raw = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if raw:
        await RefreshTokenService(db).revoke_by_token(raw)
    _clear_refresh_cookie(response)
    return {"message": "Logged out"}