from uuid import UUID
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.timetable import TimetableEntry, ClassSession

class TimetableRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_weekly_entries_for_section(self, section_id: UUID) -> List[TimetableEntry]:
        """All timetable entries for a section (used by resolution)."""
        stmt = select(TimetableEntry).where(
            TimetableEntry.section_id == section_id
        ).options(
            selectinload(TimetableEntry.subject)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_weekly_entries_for_student(
        self, section_id: UUID, subsection_id: Optional[UUID] = None
    ) -> List[TimetableEntry]:
        """Student-scoped timetable (Phase 24.7-G).

        Returns only entries that are applicable to the student:
          - ACTIVE entries only (``is_active = true``);
          - section-wide entries (``subsection_id IS NULL``), OR
          - entries for the student's own subsection (when assigned).
        Subsection-private entries for OTHER subsections are excluded —
        no subsection schedule leakage.
        """
        stmt = (
            select(TimetableEntry)
            .where(
                TimetableEntry.section_id == section_id,
                TimetableEntry.is_active.is_(True),
            )
            .options(selectinload(TimetableEntry.subject))
        )
        if subsection_id is not None:
            stmt = stmt.where(
                (TimetableEntry.subsection_id.is_(None))
                | (TimetableEntry.subsection_id == subsection_id)
            )
        else:
            stmt = stmt.where(TimetableEntry.subsection_id.is_(None))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_class_sessions_for_subject(self, subject_id: UUID) -> List[ClassSession]:
        stmt = select(ClassSession).filter(ClassSession.subject_id == subject_id).order_by(ClassSession.date)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
