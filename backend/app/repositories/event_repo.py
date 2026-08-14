from typing import Optional
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.event import AcademicEvent
from app.models.enums import ClassType, EventType


class EventNotFound(Exception):
    """The requested academic event does not exist (mapped to 404)."""


class EventConflict(Exception):
    """
    A real business conflict: an identical active event already exists
    (same type, subject, class type, and date range) — the legacy duplicate
    guard ported from js/events-controller.js (mapped to 409).
    """


class EventRepository:
    """Persistence layer for academic-event mutations (Phase 6.5)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, event_id: UUID) -> Optional[AcademicEvent]:
        result = await self.db.execute(
            select(AcademicEvent).where(AcademicEvent.id == event_id)
        )
        return result.scalars().first()

    async def subject_exists(self, subject_id: UUID) -> bool:
        from app.models.academic import Subject
        result = await self.db.execute(
            select(Subject.id).where(Subject.id == subject_id)
        )
        return result.scalars().first() is not None

    async def exists_active_duplicate(
        self,
        event_type: EventType,
        start_date: date,
        end_date: date,
        subject_id: Optional[UUID],
        class_type: Optional[ClassType],
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        """
        Legacy duplicate guard: no ACTIVE event may share the same
        (event_type, subject_id, class_type, start_date, end_date).
        Inactive rows do not block anything (they are disabled lifecycle
        records, not live events).
        """
        stmt = select(AcademicEvent.id).where(
            AcademicEvent.event_type == event_type,
            AcademicEvent.start_date == start_date,
            AcademicEvent.end_date == end_date,
            AcademicEvent.active.is_(True),
        )
        if subject_id is None:
            stmt = stmt.where(AcademicEvent.subject_id.is_(None))
        else:
            stmt = stmt.where(AcademicEvent.subject_id == subject_id)
        if class_type is None:
            stmt = stmt.where(AcademicEvent.class_type.is_(None))
        else:
            stmt = stmt.where(AcademicEvent.class_type == class_type)
        if exclude_id is not None:
            stmt = stmt.where(AcademicEvent.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None

    def add(self, event: AcademicEvent) -> None:
        self.db.add(event)

    async def flush(self) -> None:
        await self.db.flush()