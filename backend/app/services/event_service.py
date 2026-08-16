from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import AcademicEvent
from app.models.enums import EventType, ClassType, UserRole
from app.models.user import User
from app.repositories.event_repo import EventRepository, EventNotFound, EventConflict
from app.schemas.calendar import AcademicEventCreate, AcademicEventUpdate
from app.services.event_registry import (
    EventValidationError,
    validate_event,
    get_rule,
)
from app.services.event_session_service import EventSessionSynchronizer


class EventForbidden(Exception):
    """
    The authenticated user is not authorized for this event mutation (mapped
    to 403 by the endpoint). Per the product specification, events are
    student-adjustable for the flexible, subject-scoped types; global/
    closure/quiz-schedule events remain admin-only, and subject-scoped
    student events are limited to the student's own enrollments.
    """


# Event types students may create/update/deactivate for their OWN enrolled
# subjects (spec: "Students must be able to add/remove events according to
# what actually happened"). These are exactly the flexible, class-reality
# event types; everything else (holidays, closures, breaks, working-day
# overrides, QUIZ_DAY) stays admin-only because it drives the shared calendar
# structure / quiz schedule.
STUDENT_CREATABLE_EVENT_TYPES = {
    EventType.EXTRA_LECTURE,
    EventType.EXTRA_TUTORIAL,
    EventType.EXTRA_PRACTICAL,
    EventType.CLASS_CANCELLED,
    EventType.SURPRISE_QUIZ,
    # Phase 9.1: students may record laboratory reality for their own enrolled
    # practical subjects — a mid-sem practical on a date, or a cancelled lab.
    # Both are subject-scoped, enrollment-checked, and resolved by the same
    # canonical synchronizer (no separate lab attendance system).
    EventType.MID_SEM_PRACTICAL,
    EventType.LAB_CANCELLED,
}


class EventService:
    """
    Business layer for academic-event mutations (Phase 6.5).

    Endpoint -> Service -> Validation Registry -> Repository -> SQLAlchemy.
    The service validates, enforces business rules, coordinates the
    transaction (single commit; no partial event writes), and calls the
    repository for persistence.

    Since the product specification makes events student-adjustable,
    authorization is enforced here (single place): students may mutate only
    STUDENT_CREATABLE_EVENT_TYPES scoped to subjects they are enrolled in;
    admins may mutate anything. The endpoint only translates EventForbidden
    into a 403.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = EventRepository(db)
        self.sync = EventSessionSynchronizer(db)

    async def assert_mutation_allowed(
        self,
        user: User,
        *,
        event_type: EventType,
        subject_id: Optional[UUID],
    ) -> None:
        """
        Authorization gate for event mutations. Admins pass unconditionally.
        Students may only mutate flexible subject-scoped types for subjects
        they are enrolled in (enrollment authorization mirrors the attendance
        mutation path — a student can never touch another student's or an
        unrelated subject's schedule).
        """
        if user.role == UserRole.ADMIN:
            return
        if event_type not in STUDENT_CREATABLE_EVENT_TYPES:
            raise EventForbidden(
                "This event type is restricted to administrators "
                "(global / closure / quiz-schedule events)."
            )
        if subject_id is None:
            raise EventForbidden(
                "Subject-scoped event mutations require a subject."
            )
        if not await self.repo.is_enrolled(user.id, subject_id):
            raise EventForbidden(
                "You can only add or remove events for subjects you are "
                "enrolled in."
            )

    async def _ensure_subject(self, subject_id: UUID):
        subject = await self.repo.get_subject(subject_id)
        if subject is None:
            raise EventValidationError("Unknown subject_id")
        return subject

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

    async def create_event(self, user: User, data: AcademicEventCreate) -> AcademicEvent:
        # Student-adjustable events: authorize before any side effect.
        await self.assert_mutation_allowed(
            user, event_type=data.event_type, subject_id=data.subject_id
        )
        # Structural fields arrive validated by the Pydantic schema.
        subject_category = None
        if data.subject_id is not None:
            subject = await self._ensure_subject(data.subject_id)
            subject_category = subject.category
        validate_event(
            event_type=data.event_type,
            start_date=data.start_date,
            end_date=data.end_date,
            subject_id=data.subject_id,
            class_type=data.class_type,
            subject_category=subject_category,
            substitution_schedule_override=data.substitution_schedule_override,
            is_working_day=data.is_working_day,
        )
        # Unified holiday product rule: a NEW HOLIDAY must carry a
        # reason/occasion (the note). Enforced at creation only — editing an
        # existing holiday (including legacy holiday types that predate the
        # note column) never requires it, so old events stay editable.
        if data.event_type == EventType.HOLIDAY and (
            data.note is None or not data.note.strip()
        ):
            raise EventValidationError(
                "A Holiday requires a reason/occasion (note)."
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
            note=data.note,
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

    async def update_event(self, user: User, event_id: UUID, data: AcademicEventUpdate) -> AcademicEvent:
        event = await self.repo.get_by_id(event_id)
        if event is None:
            raise EventNotFound("Event not found")

        # Authorize on the existing state first (a student may not touch a
        # global/closure event even to "fix" it).
        await self.assert_mutation_allowed(
            user, event_type=event.event_type, subject_id=event.subject_id
        )

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
        if "note" in fields:
            event.note = data.note
        if "active" in fields:
            event.active = data.active

        # Re-authorize on the FINAL state: a student changing the subject or
        # type must still land on a flexible, enrolled-subject event.
        await self.assert_mutation_allowed(
            user, event_type=event.event_type, subject_id=event.subject_id
        )

        subject_category = None
        if event.subject_id is not None:
            subject = await self._ensure_subject(event.subject_id)
            subject_category = subject.category
        validate_event(
            event_type=event.event_type,
            start_date=event.start_date,
            end_date=event.end_date,
            subject_id=event.subject_id,
            class_type=event.class_type,
            subject_category=subject_category,
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

    async def deactivate_event(self, user: User, event_id: UUID) -> AcademicEvent:
        """
        Deletion is safe deactivation: `active` is the event lifecycle flag
        (legacy ADR 004 soft-delete semantics; the schema has no hard-delete
        requirement). The row is preserved; the engine and read APIs stop
        considering it. The event can be re-enabled via PATCH.
        """
        event = await self.repo.get_by_id(event_id)
        if event is None:
            raise EventNotFound("Event not found")
        # Students may remove (deactivate) flexible subject-scoped events for
        # their enrolled subjects only.
        await self.assert_mutation_allowed(
            user, event_type=event.event_type, subject_id=event.subject_id
        )
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