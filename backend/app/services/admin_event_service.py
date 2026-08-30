"""
Phase 24.9 — Admin Event Manager service.

Additive admin control-plane over the EXISTING event architecture:
  - reads: scoped admin event list/detail with subject + quiz-management
    classification;
  - writes: reuse `EventService` (canonical registry validation + duplicate
    guard + EventSessionSynchronizer + single-transaction semantics).

QUIZ_DAY OWNERSHIP GUARD (critical):
  Phase 24.8 owns QuizSchedule <-> QUIZ_DAY synchronization.  A QUIZ_DAY
  AcademicEvent that is backed by a SCHEDULED QuizSchedule row (same subject,
  elective_slot, date) is "quiz-schedule managed" and must NOT be created,
  edited, or deactivated through the generic Event Manager — doing so would
  desynchronize quiz schedule reality.  The generic manager refuses such
  mutations with 409 and directs the admin to /admin/quizzes.  Standalone
  QUIZ_DAY events NOT backed by a QuizSchedule remain editable.  There are no
  circular calls between AdminQuizService and this service.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EventType
from app.models.event import AcademicEvent
from app.models.quiz import QuizSchedule, ScheduleStatus
from app.models.user import User
from app.repositories.event_repo import EventRepository
from app.repositories.calendar_repo import CalendarRepository
from app.schemas.calendar import AcademicEventCreate, AcademicEventUpdate
from app.schemas.admin_events import (
    AdminEventListResponse,
    AdminEventMutationResponse,
    AdminEventResponse,
)
from app.services.authorization_service import AuthorizationService
from app.services.event_service import EventService, EventForbidden
from app.services.event_registry import EventValidationError, get_rule
from app.repositories.event_repo import EventNotFound, EventConflict


class AdminEventDomainError(Exception):
    code = "ADMIN_EVENT_ERROR"

    def __init__(self, detail: str, http_status: int = 422):
        self.detail = detail
        self.http_status = http_status
        super().__init__(detail)


class AdminEventQuizManagedError(AdminEventDomainError):
    def __init__(self, detail: str):
        super().__init__(detail, http_status=409)


class AdminEventService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.event_repo = EventRepository(db)
        self.calendar_repo = CalendarRepository(db)
        self.authz = AuthorizationService(db)
        self.event_service = EventService(db)

    # ------------------------------------------------------------------
    # QUIZ_DAY ownership (Phase 24.9 guard)
    # ------------------------------------------------------------------

    async def _is_quiz_schedule_managed(
        self,
        event_type: EventType,
        subject_id: Optional[UUID],
        elective_slot,
        quiz_date,
    ) -> bool:
        """True when a SCHEDULED QuizSchedule row backs this QUIZ_DAY event
        (same subject, elective_slot, and date)."""
        if event_type != EventType.QUIZ_DAY or subject_id is None or quiz_date is None:
            return False
        stmt = select(QuizSchedule.id).where(
            QuizSchedule.subject_id == subject_id,
            QuizSchedule.date == quiz_date,
            QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED,
        )
        if elective_slot is None:
            stmt = stmt.where(QuizSchedule.elective_slot.is_(None))
        else:
            stmt = stmt.where(QuizSchedule.elective_slot == elective_slot)
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None

    async def _assert_not_quiz_managed(self, event: AcademicEvent) -> None:
        """Reject mutation of a quiz-schedule-managed QUIZ_DAY event."""
        if await self._is_quiz_schedule_managed(
            event.event_type, event.subject_id, event.elective_slot, event.start_date
        ):
            raise AdminEventQuizManagedError(
                "This QUIZ_DAY event is managed by the Quiz Schedule Manager "
                "(it is backed by a scheduled quiz). Changing its date, "
                "subject, or active state here would desynchronize the quiz "
                "schedule. Use /admin/quizzes to manage quiz dates and status."
            )

    async def _assert_prospective_not_quiz_managed(
        self,
        event_type: EventType,
        subject_id: Optional[UUID],
        elective_slot,
        start_date,
    ) -> None:
        """Reject creating a QUIZ_DAY that would be quiz-schedule managed, or
        updating an event so it becomes quiz-schedule managed."""
        if await self._is_quiz_schedule_managed(
            event_type, subject_id, elective_slot, start_date
        ):
            raise AdminEventQuizManagedError(
                "This QUIZ_DAY configuration is managed by the Quiz Schedule "
                "Manager (a scheduled quiz backs the same subject/date). "
                "Manage quiz dates and status in /admin/quizzes instead."
            )

    # ------------------------------------------------------------------
    # Read model composition
    # ------------------------------------------------------------------

    async def _subject_info(self, subject_id: Optional[UUID]):
        if subject_id is None:
            return None, None
        subject = await self.event_repo.get_subject(subject_id)
        if subject is None:
            return None, None
        return subject.code, subject.name

    async def _to_response(self, event: AcademicEvent) -> AdminEventResponse:
        subject_code, subject_name = await self._subject_info(event.subject_id)
        managed = await self._is_quiz_schedule_managed(
            event.event_type, event.subject_id, event.elective_slot, event.start_date
        )
        rule = get_rule(event.event_type)
        if event.subject_id is not None and subject_code:
            if event.elective_slot is not None:
                summary = f"{event.elective_slot.value.replace('_','-')} slot"
            else:
                summary = subject_code
        else:
            summary = rule.display_name
        return AdminEventResponse(
            id=event.id,
            event_type=event.event_type,
            active=event.active,
            start_date=event.start_date,
            end_date=event.end_date,
            subject_id=event.subject_id,
            subject_code=subject_code,
            subject_name=subject_name,
            elective_slot=event.elective_slot,
            class_type=event.class_type,
            is_working_day=event.is_working_day,
            substitution_schedule_override=event.substitution_schedule_override,
            note=event.note,
            quiz_schedule_managed=managed,
            target_summary=summary,
        )

    async def _visible(self, user: User, event: AcademicEvent) -> bool:
        """Admin read-scope filter.  HEAD any; subject events: CLASS
        own-semester / ELECTIVE exact subject; global events: HEAD only
        (SUBSECTION_ADMIN stays inert)."""
        if await self.authz.is_head_admin(user):
            return True
        if event.subject_id is None:
            return False  # global events are HEAD-only
        return await self.authz.can_access_subject(user, event.subject_id)

    # ------------------------------------------------------------------
    # Reads (endpoint: require_any_admin)
    # ------------------------------------------------------------------

    async def list_events(
        self,
        user: User,
        *,
        active: Optional[bool] = None,
        event_type: Optional[EventType] = None,
        subject_id: Optional[UUID] = None,
        elective_slot=None,
        class_type=None,
        date_from=None,
        date_to=None,
    ) -> AdminEventListResponse:
        events = await self.calendar_repo.get_all_events(
            active=active,
            date_from=date_from,
            date_to=date_to,
        )
        items = []
        for event in events:
            if event_type is not None and event.event_type != event_type:
                continue
            if subject_id is not None and event.subject_id != subject_id:
                continue
            if elective_slot is not None and event.elective_slot != elective_slot:
                continue
            if class_type is not None and event.class_type != class_type:
                continue
            if await self._visible(user, event):
                items.append(await self._to_response(event))
        items.sort(key=lambda e: (e.start_date, e.event_type.value))
        return AdminEventListResponse(items=items, total=len(items))

    async def get_event(self, user: User, event_id: UUID) -> AdminEventResponse:
        event = await self.event_repo.get_by_id(event_id)
        if event is None or not await self._visible(user, event):
            raise AdminEventDomainError("Event not found", http_status=404)
        return await self._to_response(event)

    # ------------------------------------------------------------------
    # Writes (endpoint: require_any_admin; EventService enforces scope)
    # ------------------------------------------------------------------

    async def create_event(self, user: User, payload: AcademicEventCreate) -> AdminEventMutationResponse:
        if payload.event_type == EventType.QUIZ_DAY:
            await self._assert_prospective_not_quiz_managed(
                payload.event_type, payload.subject_id, payload.elective_slot,
                payload.start_date,
            )
        try:
            event = await self.event_service.create_event(user, payload)
        except EventForbidden as exc:
            raise AdminEventDomainError(str(exc), http_status=403)
        except EventNotFound as exc:
            raise AdminEventDomainError(str(exc), http_status=404)
        except EventConflict as exc:
            raise AdminEventDomainError(str(exc), http_status=409)
        except EventValidationError as exc:
            raise AdminEventDomainError(str(exc), http_status=422)
        return AdminEventMutationResponse(event=await self._to_response(event))

    async def update_event(self, user: User, event_id: UUID, payload: AcademicEventUpdate) -> AdminEventMutationResponse:
        event = await self.event_repo.get_by_id(event_id)
        if event is None:
            raise AdminEventDomainError("Event not found", http_status=404)
        await self._assert_not_quiz_managed(event)
        # A PATCH could move a QUIZ_DAY onto a schedule-managed date, or turn
        # an unmanaged event into a schedule-managed one.
        if event.event_type == EventType.QUIZ_DAY:
            new_start = payload.start_date if "start_date" in payload.model_fields_set else event.start_date
            new_subject = payload.subject_id if "subject_id" in payload.model_fields_set else event.subject_id
            new_slot = payload.elective_slot if "elective_slot" in payload.model_fields_set else event.elective_slot
            await self._assert_prospective_not_quiz_managed(
                EventType.QUIZ_DAY, new_subject, new_slot, new_start,
            )
        try:
            updated = await self.event_service.update_event(user, event_id, payload)
        except EventForbidden as exc:
            raise AdminEventDomainError(str(exc), http_status=403)
        except EventNotFound as exc:
            raise AdminEventDomainError(str(exc), http_status=404)
        except EventConflict as exc:
            raise AdminEventDomainError(str(exc), http_status=409)
        except EventValidationError as exc:
            raise AdminEventDomainError(str(exc), http_status=422)
        return AdminEventMutationResponse(event=await self._to_response(updated))

    async def deactivate_event(self, user: User, event_id: UUID) -> AdminEventMutationResponse:
        event = await self.event_repo.get_by_id(event_id)
        if event is None:
            raise AdminEventDomainError("Event not found", http_status=404)
        await self._assert_not_quiz_managed(event)
        try:
            deactivated = await self.event_service.deactivate_event(user, event_id)
        except EventForbidden as exc:
            raise AdminEventDomainError(str(exc), http_status=403)
        except EventNotFound as exc:
            raise AdminEventDomainError(str(exc), http_status=404)
        return AdminEventMutationResponse(event=await self._to_response(deactivated))
