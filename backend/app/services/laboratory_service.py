from uuid import UUID
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.enums import ClassType, SessionDesignation
from app.models.timetable import ClassSession
from app.repositories.subject_repo import SubjectRepository
from app.repositories.laboratory_repo import LaboratoryRepository


class LaboratoryService:
    """
    Phase 8.2 laboratory domain service (smallest safe foundation).

    Laboratory concerns stay separated (per docs/phase_8_2_implementation_
    report.md "LAB DOMAIN SEPARATION"):

      1. Practical attendance  -> canonical ClassSession(PRACTICAL) +
                                 AttendanceRecord pipeline (attendance service).
      2. Experiment curriculum -> LaboratoryExperiment (authoritative data only;
                                 none exists yet - never fabricated).
      3. Student experiment progress -> LaboratoryRecord.
      4. Mid-sem designation   -> this service: an ADMIN-controlled session-
                                 level fact on a REAL scheduled practical
                                 session (ClassSession.designation), never
                                 inferred from experiment counts or a computed
                                 date.

    This service only implements the smallest safe foundation for (4): the
    designation mutation + read. There is deliberately no faculty role, no
    auto-designation rule (e.g. "experiments >= 5 => next practical is mid-
    sem"), and no fake mid-sem date - the product architecture has no faculty
    scheduling authority, so the boundary is documented rather than invented.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.subject_repo = SubjectRepository(db)
        self.lab_repo = LaboratoryRepository(db)

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
