"""
Phase 24.9 â€” Admin Event Manager service.

Additive admin control-plane over the EXISTING event architecture:
  - reads: scoped admin event list/detail with subject + quiz-management
    classification;
  - writes: reuse `EventService` (canonical registry validation + duplicate
    guard + EventSessionSynchronizer + single-transaction semantics).

QUIZ_DAY OWNERSHIP GUARD (critical — enforced in EventService since the
  EVT-003 Phase 1 remediation):
  Phase 24.8 owns QuizSchedule <-> QUIZ_DAY synchronization.  A QUIZ_DAY
  AcademicEvent that is backed by a SCHEDULED QuizSchedule row (same subject,
  elective_slot, date) is "quiz-schedule managed" and must NOT be created,
  edited, or deactivated through the generic Event Manager — doing so would
  desynchronize quiz schedule reality.  The invariant now lives in
  ``EventService`` (create/update/deactivate raise ``EventConflict`` -> 409),
  so the canonical ``/api/v1/events`` endpoints inherit the same protection;
  this service no longer maintains its own copy.  The resolver is delegated
  to ``EventService.is_quiz_schedule_managed`` for the read model's
  ``quiz_schedule_managed`` field.  Standalone QUIZ_DAY events NOT backed by
  a QuizSchedule remain editable.  There are no circular calls between
  AdminQuizService and this service (AdminQuizService mutates its events
  directly and never routes through EventService).
"""

from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EventType
from app.models.event import AcademicEvent
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


class AdminEventService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.event_repo = EventRepository(db)
        self.calendar_repo = CalendarRepository(db)
        self.authz = AuthorizationService(db)
        self.event_service = EventService(db)

    # ------------------------------------------------------------------
    # QUIZ_DAY ownership (delegates to the EventService domain guard)
    # ------------------------------------------------------------------

    async def _is_quiz_schedule_managed(
        self,
        event_type: EventType,
        subject_id: Optional[UUID],
        elective_slot,
        quiz_date,
    ) -> bool:
        """True when a SCHEDULED QuizSchedule row backs this QUIZ_DAY event
        (same subject, elective_slot, and date).

        EVT-003 Phase 1: this delegates to the canonical
        ``EventService.is_quiz_schedule_managed`` resolver — the ownership
        query lives in exactly one place (the mutation guards enforce it in
        EventService), so the read model and the guard can never diverge."""
        return await self.event_service.is_quiz_schedule_managed(
            event_type=event_type,
            subject_id=subject_id,
            elective_slot=elective_slot,
            quiz_date=quiz_date,
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

    async def _to_response(self, event: AcademicEvent, user: Optional[User] = None) -> AdminEventResponse:
        subject_code, subject_name = await self._subject_info(event.subject_id)
        managed = await self._is_quiz_schedule_managed(
            event.event_type, event.subject_id, event.elective_slot, event.start_date
        )
        rule = get_rule(event.event_type)
        # Phase 24.10: the concrete subject's catalog elective slot (None for
        # common subjects and slot-wide events) â€” makes slot-vs-concrete
        # targeting unambiguous in the admin UI.
        subject_slot = None
        if event.subject_id is not None:
            subject = await self.event_repo.get_subject(event.subject_id)
            if subject is not None:
                subject_slot = subject.elective_slot
        # Phase 24.10: server-computed mutation capability for the acting
        # admin (the same can_mutate_event semantics EventService enforces).
        can_mutate = False
        if user is not None:
            decision = await self.authz.can_mutate_event(
                user,
                subject_id=event.subject_id,
                elective_slot_is_set=event.elective_slot is not None,
                student_creatable=False,
            )
            can_mutate = decision == "authorized"
        if event.subject_id is not None and subject_code:
            if event.elective_slot is not None:
                summary = f"{event.elective_slot.value.replace('_','-')} slot"
            elif subject_slot is not None:
                summary = f"{subject_code} ({subject_slot.value.replace('_','-')})"
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
            subject_slot=subject_slot,
            can_mutate=can_mutate,
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
                items.append(await self._to_response(event, user))
        items.sort(key=lambda e: (e.start_date, e.event_type.value))
        return AdminEventListResponse(items=items, total=len(items))

    async def get_event(self, user: User, event_id: UUID) -> AdminEventResponse:
        event = await self.event_repo.get_by_id(event_id)
        if event is None or not await self._visible(user, event):
            raise AdminEventDomainError("Event not found", http_status=404)
        return await self._to_response(event, user)

    # ------------------------------------------------------------------
    # Writes (endpoint: require_any_admin; EventService enforces scope)
    # ------------------------------------------------------------------

    async def create_event(self, user: User, payload: AcademicEventCreate) -> AdminEventMutationResponse:
        # EVT-003 Phase 1: the quiz-manager ownership guard now lives in
        # EventService.create_event (EventConflict -> 409 below), so the
        # canonical /api/v1/events path is protected identically.
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
        return AdminEventMutationResponse(event=await self._to_response(event, user))

    async def update_event(self, user: User, event_id: UUID, payload: AcademicEventUpdate) -> AdminEventMutationResponse:
        # EVT-003 Phase 1: both former pre-checks (old-state managed guard and
        # the prospective managed-QUIZ_DAY check) are enforced inside
        # EventService.update_event — on the OLD state AND the FINAL proposed
        # state, which also closes the type-change-INTO-managed bypass.
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
        return AdminEventMutationResponse(event=await self._to_response(updated, user))

    async def deactivate_event(self, user: User, event_id: UUID) -> AdminEventMutationResponse:
        # EVT-003 Phase 1: the managed-QUIZ_DAY rejection now comes from
        # EventService.deactivate_event as EventConflict (-> 409 below).
        try:
            deactivated = await self.event_service.deactivate_event(user, event_id)
        except EventForbidden as exc:
            raise AdminEventDomainError(str(exc), http_status=403)
        except EventNotFound as exc:
            raise AdminEventDomainError(str(exc), http_status=404)
        except EventConflict as exc:
            raise AdminEventDomainError(str(exc), http_status=409)
        return AdminEventMutationResponse(event=await self._to_response(deactivated, user))
