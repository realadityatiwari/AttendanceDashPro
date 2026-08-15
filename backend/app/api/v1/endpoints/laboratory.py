from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.api.dependencies.deps import get_db, get_current_user, require_admin
from app.models.user import User
from app.models.academic import StudentEnrollment
from app.repositories.subject_repo import SubjectRepository
from app.services.laboratory_service import LaboratoryService
from app.schemas.laboratory import (
    LaboratoryExperimentResponse,
    LaboratoryExperimentCreate,
    LaboratoryExperimentUpdate,
    LaboratoryRecordResponse,
    LaboratoryRecordCreate,
    LaboratoryRecordUpdate,
    LaboratorySummaryResponse,
    LaboratoryActivityResponse,
    MidSemDesignationPayload,
    MidSemDesignationResponse,
)

router = APIRouter()


async def _get_enrolled_subject(subject_code: str, user_id, db: AsyncSession):
    """Frozen Phase 8.2 guard for the mid-sem GET: enrollment-scoped 404
    (never reveals whether a subject exists)."""
    subject_repo = SubjectRepository(db)
    subject = await subject_repo.get_by_code(subject_code)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    enrollment = await db.execute(select(StudentEnrollment).filter_by(
        user_id=user_id, subject_id=subject.id
    ))
    if not enrollment.scalars().first():
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


@router.get("/{subject_code}/summary", response_model=LaboratorySummaryResponse)
async def get_lab_summary(
    subject_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 9.2.1: practical attendance (canonical attendance math), the
    designated mid-semester practical status, and the experiment advisory.
    The advisory is null when no experiment catalog exists — there is no
    fabricated "0/10". Enrollment-scoped (404 for unenrolled students).
    """
    return await LaboratoryService(db).get_summary(current_user, subject_code)


@router.get("/{subject_code}/experiments", response_model=List[LaboratoryExperimentResponse])
async def get_lab_experiments(
    subject_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    The ACTIVE experiment curriculum for a lab subject (empty array when no
    catalog exists). Enrollment-scoped (404 for unenrolled students).
    """
    return await LaboratoryService(db).get_curriculum(current_user, subject_code)


@router.get("/{subject_code}/records", response_model=List[LaboratoryRecordResponse])
async def get_lab_records(
    subject_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    The student's own experiment progress records for a lab subject.
    Enrollment-scoped (404 for unenrolled students).
    """
    return await LaboratoryService(db).get_records(current_user, subject_code)


@router.get("/{subject_code}/activity", response_model=LaboratoryActivityResponse)
async def get_lab_activity(
    subject_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 9.2.1: truthful chronological list of the subject's PRACTICAL
    sessions — cancelled and extra included — with the user's attendance
    state and any experiment record linked to the session. A session without
    an experiment stays a plain practical session; nothing is inferred.
    """
    return await LaboratoryService(db).get_activity(current_user, subject_code)


@router.post("/{subject_code}/records", response_model=LaboratoryRecordResponse, status_code=201)
async def create_lab_record(
    subject_code: str,
    payload: LaboratoryRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Student self-tracking (Phase 9.2.1): creates a PENDING record for an
    ACTIVE experiment of the subject. The signature status is forced to
    PENDING server-side — a record can never be created as SIGNED. Optional
    class_session_id must be a non-cancelled PRACTICAL session of the subject.
    Unenrolled students get 403; duplicate (user, experiment) → 409.
    """
    return await LaboratoryService(db).create_record(current_user, subject_code, payload)


@router.patch("/{subject_code}/records/{record_id}", response_model=LaboratoryRecordResponse)
async def update_lab_record(
    subject_code: str,
    record_id: UUID,
    payload: LaboratoryRecordUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 9.2.1 record update:
    - Student: edit an OWN PENDING record (date/session/remarks). Signed
      records are off-limits (403); signature status can never be set (403).
    - ADMIN: sign a record with {"signature_status": "signed"} — the backend
      sets signed_by = current admin and signed_on = now. Admins may also
      correct date/session/remarks of SIGNED records.
    """
    return await LaboratoryService(db).update_record(current_user, subject_code, record_id, payload)


@router.delete("/{subject_code}/records/{record_id}", status_code=204)
async def delete_lab_record(
    subject_code: str,
    record_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 9.2.1: deletes an own PENDING record (students) or any record
    (admin). Signed records cannot be deleted by students (403).
    """
    await LaboratoryService(db).delete_record(current_user, subject_code, record_id)


@router.post("/{subject_code}/experiments", response_model=LaboratoryExperimentResponse, status_code=201)
async def create_lab_experiment(
    subject_code: str,
    payload: LaboratoryExperimentCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    ADMIN-ONLY: ingests one curriculum experiment. Duplicate experiment
    numbers for the subject are rejected (409); the database-level
    UNIQUE(subject_id, experiment_number) is the backstop.
    """
    return await LaboratoryService(db).create_experiment(subject_code, payload)


@router.patch("/{subject_code}/experiments/{experiment_id}", response_model=LaboratoryExperimentResponse)
async def update_lab_experiment(
    subject_code: str,
    experiment_id: UUID,
    payload: LaboratoryExperimentUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    ADMIN-ONLY: corrects an experiment's title/description.
    """
    return await LaboratoryService(db).update_experiment(subject_code, experiment_id, payload)


@router.delete("/{subject_code}/experiments/{experiment_id}", response_model=LaboratoryExperimentResponse)
async def deactivate_lab_experiment(
    subject_code: str,
    experiment_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    ADMIN-ONLY: deactivates an experiment (is_active = False). Deactivation
    replaces hard deletion so historical records keep their FK intact; the
    curriculum endpoint simply stops exposing the experiment.
    """
    return await LaboratoryService(db).deactivate_experiment(subject_code, experiment_id)


# ----------------------------------------------------------------------
# Mid-sem designation (Phase 8.2 — FROZEN, unchanged)
# ----------------------------------------------------------------------

@router.get("/{subject_code}/mid-sem", response_model=Optional[MidSemDesignationResponse])
async def get_mid_sem_designation(
    subject_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the designated mid-semester practical session for a lab subject
    (the actual scheduled PRACTICAL session, or 200 null when none is
    designated). Read-only; the same value is exposed on the attendance
    summary. The designation is a session-level fact - never inferred from
    experiment counts or a computed date.
    """
    await _get_enrolled_subject(subject_code, current_user.id, db)
    session = await LaboratoryService(db).get_mid_sem(subject_code)
    if session is None:
        return None
    return MidSemDesignationResponse(
        subject_code=subject_code,
        session_id=session.id,
        session_date=session.date,
        designated=True,
    )


@router.put("/{subject_code}/mid-sem", response_model=MidSemDesignationResponse)
async def designate_mid_sem(
    subject_code: str,
    payload: MidSemDesignationPayload,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    ADMIN-ONLY: designates an actual scheduled PRACTICAL class session of the
    subject as its mid-semester practical. The date comes from the real
    scheduled session - a mid-sem date is never computed. Designation replaces
    any prior one for the subject and does not alter attendance counting (the
    normal attendance mutation records attendance against the session).
    """
    session = await LaboratoryService(db).designate_mid_sem(subject_code, payload.class_session_id)
    return MidSemDesignationResponse(
        subject_code=subject_code,
        session_id=session.id,
        session_date=session.date,
        designated=True,
    )


@router.delete("/{subject_code}/mid-sem", response_model=MidSemDesignationResponse)
async def clear_mid_sem(
    subject_code: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    ADMIN-ONLY: clears the subject's mid-semester practical designation.
    Attendance records on the session are untouched (attendance is never
    deleted by a designation change).
    """
    await LaboratoryService(db).clear_mid_sem(subject_code)
    return MidSemDesignationResponse(
        subject_code=subject_code,
        session_id=None,
        session_date=None,
        designated=False,
    )