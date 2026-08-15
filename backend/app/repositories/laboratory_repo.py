from uuid import UUID
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from app.models.laboratory import LaboratoryExperiment, LaboratoryRecord, SignatureStatus
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.enums import ClassType


class LaboratoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Experiment catalog (Phase 9.2.1)
    # ------------------------------------------------------------------

    async def get_experiments_for_subject(
        self, subject_id: UUID, active_only: bool = True
    ) -> List[LaboratoryExperiment]:
        """Curriculum experiments for a subject. The curriculum endpoint
        exposes ACTIVE experiments only (deactivated = correction removed
        from the catalog; historical records keep their FK)."""
        stmt = select(LaboratoryExperiment).filter(
            LaboratoryExperiment.subject_id == subject_id
        )
        if active_only:
            stmt = stmt.filter(LaboratoryExperiment.is_active.is_(True))
        stmt = stmt.order_by(LaboratoryExperiment.experiment_number)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_experiment_by_id(self, experiment_id: UUID) -> Optional[LaboratoryExperiment]:
        stmt = select(LaboratoryExperiment).filter(LaboratoryExperiment.id == experiment_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_record_for_user_and_experiment(self, user_id: UUID, experiment_id: UUID) -> Optional[LaboratoryRecord]:
        stmt = select(LaboratoryRecord).filter(
            LaboratoryRecord.user_id == user_id,
            LaboratoryRecord.experiment_id == experiment_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    # ------------------------------------------------------------------
    # Records (Phase 9.2.1)
    # ------------------------------------------------------------------

    async def get_student_records(self, user_id: UUID, subject_id: UUID) -> List[LaboratoryRecord]:
        stmt = select(LaboratoryRecord).join(LaboratoryExperiment).filter(
            LaboratoryRecord.user_id == user_id,
            LaboratoryExperiment.subject_id == subject_id
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_record_by_id(self, record_id: UUID) -> Optional[LaboratoryRecord]:
        # selectinload: the service reads record.experiment.subject_id for the
        # subject-belonging rule — async lazy loading would raise MissingGreenlet.
        stmt = (
            select(LaboratoryRecord)
            .options(selectinload(LaboratoryRecord.experiment))
            .filter(LaboratoryRecord.id == record_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_record_counts(self, user_id: UUID, subject_id: UUID) -> Tuple[int, int]:
        """(signed, pending_self_tracked) counts over the user's records for a subject."""
        stmt = (
            select(
                func.count(LaboratoryRecord.id).filter(
                    LaboratoryRecord.signature_status == SignatureStatus.SIGNED
                ),
                func.count(LaboratoryRecord.id).filter(
                    LaboratoryRecord.signature_status == SignatureStatus.PENDING
                ),
            )
            .join(LaboratoryExperiment)
            .filter(
                LaboratoryRecord.user_id == user_id,
                LaboratoryExperiment.subject_id == subject_id,
            )
        )
        result = await self.db.execute(stmt)
        row = result.one()
        return (row[0] or 0), (row[1] or 0)

    # ------------------------------------------------------------------
    # Activity (Phase 9.2.1) — truthful session-level chronology
    # ------------------------------------------------------------------

    async def get_activity_rows(
        self, user_id: UUID, subject_id: UUID
    ) -> List[dict]:
        """
        Every PRACTICAL ClassSession of the subject (cancelled and extra
        included) joined with the user's attendance status and the user's
        laboratory records linked to that session. Cancelled sessions simply
        carry no attendance status — nothing is inferred from absence of a
        session row.
        """
        stmt = (
            select(
                ClassSession.id,
                ClassSession.date,
                ClassSession.class_type,
                ClassSession.is_cancelled,
                ClassSession.is_extra,
                ClassSession.designation,
                AttendanceRecord.status.label("attendance_status"),
                LaboratoryRecord.id.label("record_id"),
                LaboratoryRecord.experiment_id,
                LaboratoryExperiment.experiment_number,
                LaboratoryRecord.signature_status,
            )
            .outerjoin(
                AttendanceRecord,
                (AttendanceRecord.class_session_id == ClassSession.id)
                & (AttendanceRecord.user_id == user_id),
            )
            .outerjoin(
                LaboratoryRecord,
                (LaboratoryRecord.class_session_id == ClassSession.id)
                & (LaboratoryRecord.user_id == user_id),
            )
            .outerjoin(
                LaboratoryExperiment,
                LaboratoryRecord.experiment_id == LaboratoryExperiment.id,
            )
            .filter(
                ClassSession.subject_id == subject_id,
                ClassSession.class_type == ClassType.PRACTICAL,
            )
            .order_by(ClassSession.date.desc(), ClassSession.id)
        )
        result = await self.db.execute(stmt)
        return [dict(row._mapping) for row in result.all()]