from uuid import UUID
from typing import Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.timezone import institution_today
from app.models.enums import ClassType, SessionDesignation
from app.models.timetable import ClassSession
from app.models.user import User
from app.models.laboratory import LaboratoryExperiment, LaboratoryRecord, SignatureStatus
from app.repositories.subject_repo import SubjectRepository
from app.repositories.laboratory_repo import LaboratoryRepository
from app.repositories.attendance_repo import AttendanceRepository
from app.services.attendance_service import AttendanceService
from app.schemas.laboratory import (
    LaboratorySummaryResponse,
    PracticalAttendanceSummary,
    MidSemStatusSummary,
    ExperimentProgressSummary,
    LaboratoryActivityItem,
    LaboratoryActivityResponse,
)

IST = ZoneInfo("Asia/Kolkata")


class LaboratoryService:
    """
    Phase 8.2 + Phase 9.2.1 laboratory domain service.

    Laboratory concerns stay separated (per docs/phase_8_2_implementation_
    report.md "LAB DOMAIN SEPARATION"):

      1. Practical attendance  -> canonical ClassSession(PRACTICAL) +
                                 AttendanceRecord pipeline (attendance service;
                                 reused unchanged — no second attendance engine).
      2. Experiment curriculum -> LaboratoryExperiment (authoritative data only;
                                 never fabricated — empty catalog is valid).
      3. Student experiment progress -> LaboratoryRecord (self-tracked PENDING,
                                 ADMIN-signed).
      4. Mid-sem designation   -> ADMIN-controlled session-level fact on a REAL
                                 scheduled practical session (ClassSession.
                                 designation); the experiment advisory is
                                 read-only and never gates designation.

    Authorization matrix (audit §16): enrolled students may self-track PENDING
    records; only ADMIN may sign records, edit SIGNED records, or manage the
    experiment catalog. Unenrolled students get 404 on reads (no subject leak)
    and 403 on writes. Records can never be forged as SIGNED — the service
    forces PENDING on student writes and rejects student attempts to set
    signature_status.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.subject_repo = SubjectRepository(db)
        self.lab_repo = LaboratoryRepository(db)
        self.attendance_repo = AttendanceRepository(db)

    # ------------------------------------------------------------------
    # Shared guards
    # ------------------------------------------------------------------

    async def _get_subject(self, subject_code: str):
        subject = await self.subject_repo.get_by_code(subject_code)
        if subject is None:
            raise HTTPException(status_code=404, detail="Subject not found")
        return subject

    async def _guard_read(self, user: User, subject) -> None:
        """Reads are enrollment-scoped: unenrolled users get 404 (no leak)."""
        if user.role == "ADMIN":
            return
        if not await self.attendance_repo.is_enrolled(user.id, subject.id):
            raise HTTPException(status_code=404, detail="Subject not found")

    async def _guard_write(self, user: User, subject) -> None:
        """Writes require enrollment for students; admins bypass enrollment."""
        if user.role == "ADMIN":
            return
        if not await self.attendance_repo.is_enrolled(user.id, subject.id):
            raise HTTPException(status_code=403, detail="Not enrolled in this subject")

    async def _validate_session_link(self, class_session_id: Optional[UUID], subject) -> Optional[ClassSession]:
        """
        Phase 9.2.1 record-session linkage rules (audit §11): the session must
        exist, belong to the same subject, be a PRACTICAL session, and must NOT
        be cancelled. Returns the session or None when no link requested.
        """
        if class_session_id is None:
            return None
        session = await self.attendance_repo.get_session_by_id(class_session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Class session not found")
        if session.subject_id != subject.id:
            raise HTTPException(status_code=400, detail="Session does not belong to this subject")
        if session.class_type != ClassType.PRACTICAL:
            raise HTTPException(status_code=400, detail="Only a PRACTICAL session can host a laboratory record")
        if session.is_cancelled:
            raise HTTPException(status_code=400, detail="A cancelled session cannot host a laboratory record")
        return session

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_summary(self, user: User, subject_code: str) -> LaboratorySummaryResponse:
        """
        Phase 9.2.1 summary: practical attendance (reused canonical attendance
        service math — React never computes), mid-sem designation status, and
        the experiment advisory. The advisory is null when no catalog exists
        (no fabricated "0/10").
        """
        subject = await self._get_subject(subject_code)
        await self._guard_read(user, subject)

        att_summary = await AttendanceService(self.db).get_summary(
            user.id, subject.id, subject.code, institution_today()
        )
        p = att_summary.practical
        practical = PracticalAttendanceSummary(
            attended=p.attended,
            missed=p.missed,
            pending=p.pending,
            total=p.total,
            current_practical_pct=att_summary.current_practical_pct or 0.0,
        )

        mid_sem_session = await self.get_mid_sem(subject_code)
        attendance_status = None
        if mid_sem_session is not None:
            record = await self.attendance_repo.get_attendance_for_session(
                user.id, mid_sem_session.id
            )
            if record is not None:
                attendance_status = record.status.value

        curriculum = await self.lab_repo.get_experiments_for_subject(subject.id, active_only=True)
        signed, pending = await self.lab_repo.get_record_counts(user.id, subject.id)
        catalog_available = len(curriculum) > 0
        advisory = None
        if catalog_available:
            advisory = f"{signed} of {len(curriculum)} experiments officially completed"

        return LaboratorySummaryResponse(
            subject_code=subject.code,
            practical_attendance=practical,
            mid_sem=MidSemStatusSummary(
                designated=mid_sem_session is not None,
                session_id=mid_sem_session.id if mid_sem_session else None,
                session_date=mid_sem_session.date if mid_sem_session else None,
                attendance_status=attendance_status,
            ),
            experiment_progress=ExperimentProgressSummary(
                catalog_available=catalog_available,
                total=len(curriculum),
                signed=signed,
                pending_self_tracked=pending,
                advisory=advisory,
            ),
        )

    async def get_curriculum(self, user: User, subject_code: str) -> List[LaboratoryExperiment]:
        subject = await self._get_subject(subject_code)
        await self._guard_read(user, subject)
        return await self.lab_repo.get_experiments_for_subject(subject.id, active_only=True)

    async def get_records(self, user: User, subject_code: str) -> List[LaboratoryRecord]:
        subject = await self._get_subject(subject_code)
        await self._guard_read(user, subject)
        return await self.lab_repo.get_student_records(user.id, subject.id)

    async def get_activity(self, user: User, subject_code: str) -> LaboratoryActivityResponse:
        """
        Truthful session-scoped chronology (audit §15 IA): every PRACTICAL
        ClassSession of the subject — cancelled and extra included — with the
        user's attendance state and any experiment record linked to that
        session. A session without an experiment stays a plain practical
        session; nothing is inferred from attendance.
        """
        subject = await self._get_subject(subject_code)
        await self._guard_read(user, subject)

        rows = await self.lab_repo.get_activity_rows(user.id, subject.id)
        items: List[LaboratoryActivityItem] = []
        by_session: dict = {}
        for row in rows:
            session_id = str(row["id"])
            if session_id not in by_session:
                by_session[session_id] = {
                    "id": row["id"],
                    "date": row["date"],
                    "class_type": row["class_type"].value,
                    "is_cancelled": row["is_cancelled"],
                    "is_extra": row["is_extra"],
                    "designation": row["designation"].value if row["designation"] else None,
                    "attendance_status": row["attendance_status"].value if row["attendance_status"] else None,
                    "experiments": [],
                }
            if row["record_id"] is not None:
                by_session[session_id]["experiments"].append(
                    {
                        "id": row["record_id"],
                        "user_id": user.id,
                        "experiment_id": row["experiment_id"],
                        "class_session_id": session_id,
                        "signature_status": row["signature_status"].value,
                        "date_conducted": row["date"],
                        "signed_on": None,
                        "signed_by": None,
                        "created_by": None,
                        "updated_by": None,
                        "marks": None,
                        "remarks": None,
                    }
                )
        for entry in by_session.values():
            items.append(LaboratoryActivityItem(**entry))
        items.sort(key=lambda i: i.date, reverse=True)
        return LaboratoryActivityResponse(subject_code=subject.code, items=items)

    # ------------------------------------------------------------------
    # Student record writes (Phase 9.2.1)
    # ------------------------------------------------------------------

    async def create_record(self, user: User, subject_code: str, payload) -> LaboratoryRecord:
        subject = await self._get_subject(subject_code)
        await self._guard_write(user, subject)

        experiment = await self.lab_repo.get_experiment_by_id(payload.experiment_id)
        if experiment is None:
            raise HTTPException(status_code=404, detail="Experiment not found")
        if experiment.subject_id != subject.id:
            raise HTTPException(status_code=400, detail="Experiment does not belong to this subject")
        if not experiment.is_active:
            raise HTTPException(status_code=400, detail="Experiment is not active")

        duplicate = await self.lab_repo.get_record_for_user_and_experiment(user.id, experiment.id)
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="A record already exists for this experiment")

        await self._validate_session_link(payload.class_session_id, subject)

        # Student-created records are ALWAYS PENDING — signature is not part of
        # the create payload and can never be forged (audit Decision 3).
        record = LaboratoryRecord(
            user_id=user.id,
            experiment_id=experiment.id,
            date_conducted=payload.date_conducted,
            class_session_id=payload.class_session_id,
            remarks=payload.remarks,
            signature_status=SignatureStatus.PENDING,
            created_by=user.id,
            updated_by=user.id,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def update_record(self, user: User, subject_code: str, record_id: UUID, payload) -> LaboratoryRecord:
        subject = await self._get_subject(subject_code)
        await self._guard_write(user, subject)

        record = await self.lab_repo.get_record_by_id(record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")
        if record.experiment.subject_id != subject.id:
            raise HTTPException(status_code=400, detail="Record does not belong to this subject")

        is_admin = user.role == "ADMIN"
        if not is_admin:
            if record.user_id != user.id:
                raise HTTPException(status_code=404, detail="Record not found")
            if record.signature_status == SignatureStatus.SIGNED:
                raise HTTPException(
                    status_code=403,
                    detail="Signed records can only be edited by an administrator",
                )
            if payload.signature_status is not None:
                raise HTTPException(
                    status_code=403,
                    detail="Students cannot set signature status",
                )
        elif payload.signature_status is not None:
            if payload.signature_status == SignatureStatus.SIGNED:
                record.signature_status = SignatureStatus.SIGNED
                record.signed_by = user.id
                record.signed_on = datetime.now(IST)
            else:
                raise HTTPException(status_code=400, detail="Only SIGNED can be set as signature status")

        if payload.date_conducted is not None:
            record.date_conducted = payload.date_conducted
        if payload.class_session_id is not None:
            await self._validate_session_link(payload.class_session_id, subject)
            record.class_session_id = payload.class_session_id
        if payload.remarks is not None:
            record.remarks = payload.remarks
        record.updated_by = user.id

        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def delete_record(self, user: User, subject_code: str, record_id: UUID) -> None:
        subject = await self._get_subject(subject_code)
        await self._guard_write(user, subject)

        record = await self.lab_repo.get_record_by_id(record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")
        if record.experiment.subject_id != subject.id:
            raise HTTPException(status_code=400, detail="Record does not belong to this subject")

        if user.role != "ADMIN":
            if record.user_id != user.id:
                raise HTTPException(status_code=404, detail="Record not found")
            if record.signature_status == SignatureStatus.SIGNED:
                raise HTTPException(
                    status_code=403,
                    detail="Signed records cannot be deleted by students",
                )

        await self.db.delete(record)
        await self.db.commit()

    # ------------------------------------------------------------------
    # Admin experiment catalog (Phase 9.2.1)
    # ------------------------------------------------------------------

    async def create_experiment(self, subject_code: str, payload) -> LaboratoryExperiment:
        subject = await self._get_subject(subject_code)
        existing = await self.lab_repo.get_experiments_for_subject(subject.id, active_only=False)
        if any(e.experiment_number == payload.experiment_number for e in existing):
            raise HTTPException(
                status_code=409,
                detail="Experiment number already exists for this subject",
            )
        experiment = LaboratoryExperiment(
            subject_id=subject.id,
            experiment_number=payload.experiment_number,
            title=payload.title,
            description=payload.description,
            is_active=True,
        )
        self.db.add(experiment)
        await self.db.commit()
        await self.db.refresh(experiment)
        return experiment

    async def update_experiment(self, subject_code: str, experiment_id: UUID, payload) -> LaboratoryExperiment:
        subject = await self._get_subject(subject_code)
        experiment = await self.lab_repo.get_experiment_by_id(experiment_id)
        if experiment is None:
            raise HTTPException(status_code=404, detail="Experiment not found")
        if experiment.subject_id != subject.id:
            raise HTTPException(status_code=400, detail="Experiment does not belong to this subject")
        if payload.title is not None:
            experiment.title = payload.title
        if payload.description is not None:
            experiment.description = payload.description
        await self.db.commit()
        await self.db.refresh(experiment)
        return experiment

    async def deactivate_experiment(self, subject_code: str, experiment_id: UUID) -> LaboratoryExperiment:
        """Deactivation replaces hard deletion (audit §13.1): historical records
        keep their FK; the curriculum endpoint simply stops exposing it."""
        subject = await self._get_subject(subject_code)
        experiment = await self.lab_repo.get_experiment_by_id(experiment_id)
        if experiment is None:
            raise HTTPException(status_code=404, detail="Experiment not found")
        if experiment.subject_id != subject.id:
            raise HTTPException(status_code=400, detail="Experiment does not belong to this subject")
        experiment.is_active = False
        await self.db.commit()
        await self.db.refresh(experiment)
        return experiment

    # ------------------------------------------------------------------
    # Mid-sem designation (Phase 8.2, FROZEN — unchanged)
    # ------------------------------------------------------------------

    async def get_mid_sem(self, subject_code: str) -> Optional[ClassSession]:
        """The designated mid-semester practical session for a subject, or None."""
        subject = await self.subject_repo.get_by_code(subject_code)
        if subject is None:
            raise HTTPException(status_code=404, detail="Subject not found")
        stmt = select(ClassSession).where(
            ClassSession.subject_id == subject.id,
            ClassSession.designation == SessionDesignation.MID_SEM_PRACTICAL,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def designate_mid_sem(self, subject_code: str, class_session_id: UUID) -> ClassSession:
        """
        Designates an ACTUAL scheduled PRACTICAL class session as the subject's
        mid-semester practical (admin-only; enforced by require_admin at the
        endpoint). Idempotent: designating the same session twice is a no-op;
        designating a different session replaces the previous designation (one
        mid-sem per subject). Attendance is recorded against the session through
        the normal attendance mutation - designation never changes counting.
        """
        subject = await self.subject_repo.get_by_code(subject_code)
        if subject is None:
            raise HTTPException(status_code=404, detail="Subject not found")

        stmt = select(ClassSession).where(ClassSession.id == class_session_id)
        result = await self.db.execute(stmt)
        session = result.scalars().first()
        if session is None:
            raise HTTPException(status_code=404, detail="Class session not found")
        if session.subject_id != subject.id:
            raise HTTPException(status_code=400, detail="Session does not belong to this subject")
        if session.class_type != ClassType.PRACTICAL:
            raise HTTPException(
                status_code=400,
                detail="Only a PRACTICAL session can be designated as the mid-semester practical",
            )

        # Replace any previous designation for this subject (one mid-sem per subject).
        stmt_clear = select(ClassSession).where(
            ClassSession.subject_id == subject.id,
            ClassSession.designation == SessionDesignation.MID_SEM_PRACTICAL,
        )
        for other in (await self.db.execute(stmt_clear)).scalars().all():
            if other.id != session.id:
                other.designation = None

        session.designation = SessionDesignation.MID_SEM_PRACTICAL
        await self.db.commit()
        return session

    async def clear_mid_sem(self, subject_code: str) -> bool:
        """Clears the mid-semester practical designation for a subject (admin-only)."""
        subject = await self.subject_repo.get_by_code(subject_code)
        if subject is None:
            raise HTTPException(status_code=404, detail="Subject not found")
        stmt = select(ClassSession).where(
            ClassSession.subject_id == subject.id,
            ClassSession.designation == SessionDesignation.MID_SEM_PRACTICAL,
        )
        changed = False
        for session in (await self.db.execute(stmt)).scalars().all():
            session.designation = None
            changed = True
        await self.db.commit()
        return changed