"""
Session persistence for the event->engine integration (Phase 6.6).

Read/write access to `class_sessions` and `timetable_entries` needed by the
EventSessionSynchronizer. Session rows remain owned by the canonical baseline
expansion pipeline (expand_baseline.py); this repository only reconciles
existing rows against the engine's effective schedule and creates the sessions
that events legitimately produce (extras, working-Saturday/substitution
replays). No session is ever deleted while it has attendance records — the
attendance-safety rule lives here.

Layering (per the Phase 6.6 spec):
    EventService -> EventSessionSynchronizer -> this repository -> SQLAlchemy
"""

from typing import List, Optional, Tuple
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.models.attendance import AttendanceRecord
from app.models.timetable import ClassSession, TimetableEntry
from app.models.enums import ClassType, ElectiveSlot


class SessionRepository:
    """Read/write access to the canonical class_sessions pipeline."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_timetable_entries(self) -> List[TimetableEntry]:
        """All recurring timetable entries (the schedule base for expansion)."""
        result = await self.db.execute(select(TimetableEntry))
        return list(result.scalars().all())

    async def get_session_date_span(self) -> Optional[Tuple[date, date]]:
        """
        The [min, max] date span of *scheduled* (non-extra) sessions — the
        canonical baseline window. Reconciliation never creates sessions
        outside this span: events still affect the calendar engine there, but
        the session pipeline is bounded to the expanded academic window.
        """
        result = await self.db.execute(
            select(
                func.min(ClassSession.date),
                func.max(ClassSession.date),
            ).where(
                ClassSession.timetable_entry_id.is_not(None)
            )
        )
        row = result.one()
        if row[0] is None or row[1] is None:
            return None
        return row[0], row[1]

    async def get_sessions_in_range(
        self, start: date, end: date
    ) -> List[ClassSession]:
        """Every class session within [start, end] (cancelled included)."""
        result = await self.db.execute(
            select(ClassSession).where(
                ClassSession.date >= start,
                ClassSession.date <= end,
            )
        )
        return list(result.scalars().all())

    async def get_session_ids_with_attendance(self, session_ids: List[UUID]) -> set:
        """
        The subset of session ids that already have at least one attendance
        record. Sessions with attendance records are historical and are never
        modified or deleted by the synchronizer.
        """
        if not session_ids:
            return set()
        result = await self.db.execute(
            select(AttendanceRecord.class_session_id).where(
                AttendanceRecord.class_session_id.in_(session_ids)
            )
        )
        return set(result.scalars().all())

    def add_session(
        self,
        *,
        subject_id: UUID,
        date: date,
        class_type: ClassType,
        is_extra: bool,
        timetable_entry_id: Optional[UUID],
        elective_slot: Optional[ElectiveSlot] = None,
    ) -> ClassSession:
        session = ClassSession(
            subject_id=subject_id,
            date=date,
            class_type=class_type,
            is_extra=is_extra,
            is_cancelled=False,
            timetable_entry_id=timetable_entry_id,
            elective_slot=elective_slot,
        )
        self.db.add(session)
        return session

    async def delete_session(self, session: ClassSession) -> None:
        await self.db.delete(session)

    async def flush(self) -> None:
        await self.db.flush()