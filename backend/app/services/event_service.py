from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import AcademicEvent
from app.models.enums import EventType, ClassType
from app.repositories.event_repo import EventRepository, EventNotFound, EventConflict
from app.schemas.calendar import AcademicEventCreate, AcademicEventUpdate
from app.services.event_registry import (
    EventValidationError,
    validate_event,
    get_rule,
)
from app.services.event_session_service import EventSessionSynchronizer


class EventService:
    """
    Business layer for academic-event mutations (Phase 6.5).

    Endpoint -> Service -> Validation Registry -> Repository -> SQLAlchemy.
    The service validates, enforces business rules, coordinates the
    transaction (single commit; no partial event writes), and calls the
    repository for persistence.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = EventRepository(db)
        self.sync = EventSessionSynchronizer(db)

    async def _ensure_subject(self, subject_id: UUID) -> None:
        if not await self.repo.subject_exists(subject_id):
            raise EventValidationError("Unknown subject_id")

    async def _check_duplicate(
        self,
        event_type: EventType,
        start_date,
        end_date,
        subject_id: Optional[UUID],
        class_type: Optional[ClassType],
        exclude_id: Optional[UUID] = None,
    ) -> None:
        if await self.repo.exists_active_duplicate(
            event_type, start_date, end_date, subject_id, class_type, exclude_id
        ):
            raise EventConflict(
                "An identical active event already exists "
                "(same type, subject, class type, and date range)"
            )

    async def create_event(self, data: AcademicEventCreate) -> AcademicEvent:
        # Structural fields arrive validated by the Pydantic schema.
        if data.subject_id is not None:
            await self._ensure_subject(data.subject_id)
        validate_event(
            event_type=data.event_type,
            start_date=data.start_date,
            end_date=data.end_date,
            subject_id=data.subject_id,
            class_type=data.class_type,
            substitution_schedule_override=data.substitution_schedule_override,
            is_working_day=data.is_working_day,
        )
        await self._check_duplicate(
            data.event_type,
            data.start_date,
            data.end_date,
            data.subject_id,
            data.class_type,
        )

        event = AcademicEvent(
            event_type=data.event_type,
            start_date=data.start_date,
            end_date=data.end_date,
            subject_id=data.subject_id,
            class_type=data.class_type,
            is_working_day=data.is_working_day,
            substitution_schedule_override=data.substitution_schedule_override,
            active=data.active,
        )
        self.repo.add(event)
        try:
            await self.repo.flush()
            # Phase 6.6: reconcile class_sessions to the engine's effective
            # schedule for the event's dates — same transaction, so the event
            # and its session effect commit (or roll back) together.
            await self.sync.sync_event(event)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        await self.db.refresh(event)
        return event

    async def update_event(self, event_id: UUID, data: AcademicEventUpdate) -> AcademicEvent:
        event = await self.repo.get_by_id(event_id)
        if event is None:
            raise EventNotFound("Event not found")

        # Phase 6.6: remember the pre-update span so sessions affected by the
        # old configuration are reconciled back even when the event moves.
        old_start = event.start_date
        old_end = event.end_date

        # Partial update: absent fields keep their current values. `subject_id`
        # and friends can be explicitly nulled to convert scoping.
        fields = data.model_fields_set
        if "event_type" in fields:
            event.event_type = data.event_type
        if "start_date" in fields:
            event.start_date = data.start_date
        if "end_date" in fields:
            event.end_date = data.end_date
        if "subject_id" in fields:
            event.subject_id = data.subject_id
        if "class_type" in fields:
            event.class_type = data.class_type
        if "is_working_day" in fields:
            event.is_working_day = data.is_working_day
        if "substitution_schedule_override" in fields:
            event.substitution_schedule_override = data.substitution_schedule_override
        if "active" in fields:
            event.active = data.active

        if event.subject_id is not None:
            await self._ensure_subject(event.subject_id)
        validate_event(
            event_type=event.event_type,
            start_date=event.start_date,
            end_date=event.end_date,
            subject_id=event.subject_id,
            class_type=event.class_type,
            substitution_schedule_override=event.substitution_schedule_override,
            is_working_day=event.is_working_day,
        )
        await self._check_duplicate(
            event.event_type,
            event.start_date,
            event.end_date,
            event.subject_id,
            event.class_type,
            exclude_id=event.id,
        )

        try:
            # Reconcile the union of the old and new spans: dates the event
            # stopped covering are restored, dates it now covers are applied.
            await self.repo.flush()
            await self.sync.sync_event(
                event,
                span_override=(min(old_start, event.start_date), max(old_end, event.end_date)),
            )
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        await self.db.refresh(event)
        return event

    async def deactivate_event(self, event_id: UUID) -> AcademicEvent:
        """
        Deletion is safe deactivation: `active` is the event lifecycle flag
        (legacy ADR 004 soft-delete semantics; the schema has no hard-delete
        requirement). The row is preserved; the engine and read APIs stop
        considering it. The event can be re-enabled via PATCH.
        """
        event = await self.repo.get_by_id(event_id)
        if event is None:
            raise EventNotFound("Event not found")
        if not event.active:
            return event
        event.active = False
        try:
            # Phase 6.6: reconcile the event's dates back to what the remaining
            # active events imply — sessions it cancelled are restored, extras
            # it created are removed (attendance-bound ones are preserved).
            await self.repo.flush()
            await self.sync.sync_event(event)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        await self.db.refresh(event)
        return event