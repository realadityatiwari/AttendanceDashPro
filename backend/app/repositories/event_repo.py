from typing import Optional
from datetime import date
from uuid import UUID

from sqlalchemy import or_
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


# EVT-004 (Phase 3): the natural-key unique indexes that make the DATABASE
# the final duplicate authority. A concurrent duplicate insertion surfaces
# as a PostgreSQL unique violation on one of these names; the translation
# helper below turns exactly those violations into EventConflict (409) and
# lets every unrelated integrity failure propagate untouched.
EVT004_UNIQUE_CONSTRAINTS = frozenset({
    "uq_academic_events_quiz_day_identity",
    "uq_academic_events_global_range",
    "uq_class_sessions_entry_date",
    "uq_class_sessions_source_event_date",
    "uq_class_sessions_quiz_day_subject_date",
})

# The class_sessions natural-key indexes: a violation on one of these is a
# SESSION materialization race (the reconciler's canonical identities), not a
# duplicate event row — the translated conflict must say so instead of the
# misleading "identical active event" wording (integrity review).
EVT004_SESSION_CONSTRAINTS = frozenset({
    "uq_class_sessions_entry_date",
    "uq_class_sessions_source_event_date",
    "uq_class_sessions_quiz_day_subject_date",
})


def is_evt004_unique_violation(exc: Exception) -> bool:
    """Whether `exc` is a PostgreSQL unique violation (SQLSTATE 23505) raised
    by one of the EVT-004 natural-key indexes. Deliberately narrow: unique
    violations from ANY other constraint (and every other integrity failure)
    return False and keep propagating as-is."""
    orig = getattr(exc, "orig", exc)
    if getattr(orig, "pgcode", None) != "23505":
        return False
    message = str(exc)
    return any(name in message for name in EVT004_UNIQUE_CONSTRAINTS)


def is_evt004_session_violation(exc: Exception) -> bool:
    """Whether the EVT-004 violation came from one of the class_sessions
    natural-key indexes — i.e. a concurrent reconciliation race rather than a
    duplicate event row (used only to pick the conflict MESSAGE; both map to
    the same 409)."""
    if not is_evt004_unique_violation(exc):
        return False
    message = str(exc)
    return any(name in message for name in EVT004_SESSION_CONSTRAINTS)


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

    async def get_subject(self, subject_id: UUID):
        """The Subject row (category/quiz flags) for a subject-scoped event."""
        from app.models.academic import Subject
        result = await self.db.execute(
            select(Subject).where(Subject.id == subject_id)
        )
        return result.scalars().first()

    async def get_timetable_entry(self, entry_id: UUID):
        """The TimetableEntry row for an occurrence reference (OCC-1)."""
        from app.models.timetable import TimetableEntry
        result = await self.db.execute(
            select(TimetableEntry).where(TimetableEntry.id == entry_id)
        )
        return result.scalars().first()

    async def is_enrolled(self, user_id: UUID, subject_id: UUID) -> bool:
        """
        Whether the user holds an enrollment for the subject (student event
        authorization — the same enrollment pattern the attendance mutation
        path uses).
        """
        from app.models.academic import StudentEnrollment
        result = await self.db.execute(
            select(StudentEnrollment.id).where(
                StudentEnrollment.user_id == user_id,
                StudentEnrollment.subject_id == subject_id,
            )
        )
        return result.scalars().first() is not None

    async def exists_active_duplicate(
        self,
        event_type: EventType,
        start_date: date,
        end_date: date,
        subject_id: Optional[UUID],
        class_type: Optional[ClassType],
        timetable_entry_id: Optional[UUID] = None,
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        """
        Legacy duplicate guard: no ACTIVE event may share the same
        (event_type, subject_id, class_type, start_date, end_date).
        Inactive rows do not block anything (they are disabled lifecycle
        records, not live events).

        OCC-1: for an occurrence-referenced new event the identity includes
        the timetable entry — distinct occurrences of the same subject/class
        on the same dates stay separately cancellable. A legacy NULL-entry
        event with the same key still blocks: it cancels by subject+class on
        those dates, so the referenced occurrence is already covered.
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
        if timetable_entry_id is not None:
            stmt = stmt.where(
                or_(
                    AcademicEvent.timetable_entry_id == timetable_entry_id,
                    AcademicEvent.timetable_entry_id.is_(None),
                )
            )
        if exclude_id is not None:
            stmt = stmt.where(AcademicEvent.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None

    def add(self, event: AcademicEvent) -> None:
        self.db.add(event)

    async def flush(self) -> None:
        await self.db.flush()