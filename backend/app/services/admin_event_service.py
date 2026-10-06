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

from datetime import date
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.calendar_engine import (
    DEFAULT_WEEKENDS,
    DAY_NAMES,
    get_academic_day,
)
from app.models.enums import ClassType, ElectiveSlot, EventType
from app.models.event import AcademicEvent
from app.models.user import User
from app.repositories.admin_timetable_repo import AdminTimetableRepository
from app.repositories.event_repo import EventRepository
from app.repositories.calendar_repo import CalendarRepository
from app.schemas.calendar import AcademicEventCreate, AcademicEventUpdate
from app.schemas.admin_events import (
    AdminEventListResponse,
    AdminEventMutationResponse,
    AdminEventResponse,
    AdminOccurrenceElectiveSubject,
    AdminOccurrenceOption,
    AdminOccurrenceOptionsResponse,
)
from app.services.authorization_service import AuthorizationService
from app.services.elective_resolver import ElectiveResolver
from app.services.event_service import EventService, EventForbidden
from app.services.event_registry import EventValidationError, get_rule
from app.repositories.event_repo import EventNotFound, EventConflict

# ClassType -> display label for occurrence read models.
CLASS_TYPE_LABELS: Dict[ClassType, str] = {
    ClassType.LECTURE: "Lecture",
    ClassType.TUTORIAL: "Tutorial",
    ClassType.PRACTICAL: "Practical",
}

# ElectiveSlot -> canonical user-facing label (matches the frontend's
# canonicalStatus register).
ELECTIVE_SLOT_LABELS: Dict[ElectiveSlot, str] = {
    ElectiveSlot.ELECTIVE_I: "Department Elective-I",
    ElectiveSlot.ELECTIVE_II: "Department Elective-II",
}


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
        self.timetable_repo = AdminTimetableRepository(db)
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
    # OCC-1 occurrence read helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _occurrence_label(entry) -> str:
        """Ready-to-render description of a scheduled timetable occurrence,
        e.g. "BCS-502 — Web Technology (Lecture) · 10:00–11:00 · Monday".
        Slot entries are marked so an admin can never mistake the shared
        anchor session for a regular subject class."""
        label = (
            f"{entry.subject.code} — {entry.subject.name} "
            f"({CLASS_TYPE_LABELS[entry.class_type]}) · "
            f"{entry.start_time.strftime('%H:%M')}–{entry.end_time.strftime('%H:%M')}"
        )
        if entry.elective_slot is not None:
            slot_label = ELECTIVE_SLOT_LABELS.get(entry.elective_slot)
            if slot_label is not None:
                label += f" · {slot_label} slot"
        label += f" · {DAY_NAMES[entry.day_of_week].title()}"
        return label

    async def _entry_label_map(self, entry_ids: List[UUID]) -> Dict[UUID, str]:
        """Batch timetable-entry labels for a page of events (one query)."""
        ids = [e for e in entry_ids if e is not None]
        if not ids:
            return {}
        entries = await self.timetable_repo.list_entries_by_ids(ids)
        return {entry.id: self._occurrence_label(entry) for entry in entries}

    async def _elective_members_by_slot(self) -> Dict[ElectiveSlot, list]:
        """The DB-backed elective catalog grouped by slot (active academic
        session), anchors EXCLUDED — members are the concrete subjects a
        slot occurrence may be narrowed to. Same session scoping as
        ElectiveResolver.catalog_codes (the resolver returns codes only;
        the read model needs id/code/name)."""
        from app.models.academic import AcademicSession, Semester, Subject as SubjectModel
        result = await self.db.execute(
            select(SubjectModel)
            .join(Semester, Semester.id == SubjectModel.semester_id)
            .join(AcademicSession, AcademicSession.id == Semester.session_id)
            .where(
                AcademicSession.is_active.is_(True),
                SubjectModel.elective_slot.isnot(None),
            )
        )
        anchors = await ElectiveResolver(self.db).anchor_subjects()
        anchor_ids = {a.id for a in anchors.values()}
        members: Dict[ElectiveSlot, list] = {}
        for subject in result.scalars().all():
            if subject.id in anchor_ids:
                continue
            members.setdefault(subject.elective_slot, []).append(subject)
        for subjects in members.values():
            subjects.sort(key=lambda s: s.code)
        return members

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

    async def _to_response(
        self,
        event: AcademicEvent,
        user: Optional[User] = None,
        entry_labels: Optional[Dict[UUID, str]] = None,
    ) -> AdminEventResponse:
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
        # OCC-1: the referenced occurrence's server-computed label (the UI
        # never reconstructs it from the weekly timetable).
        occurrence_label = None
        if event.timetable_entry_id is not None:
            if entry_labels is not None:
                occurrence_label = entry_labels.get(event.timetable_entry_id)
            else:
                entry = await self.timetable_repo.get_entry(event.timetable_entry_id)
                occurrence_label = (
                    self._occurrence_label(entry) if entry is not None else None
                )
        return AdminEventResponse(
            id=event.id,
            event_type=event.event_type,
            active=event.active,
            start_date=event.start_date,
            end_date=event.end_date,
            subject_id=event.subject_id,
            subject_code=subject_code,
            subject_name=subject_name,
            timetable_entry_id=event.timetable_entry_id,
            occurrence_label=occurrence_label,
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
                items.append(event)
        items.sort(key=lambda e: (e.start_date, e.event_type.value))
        # OCC-1: batch the occurrence labels for the visible page (one query).
        entry_labels = await self._entry_label_map(
            [e.timetable_entry_id for e in items]
        )
        responses = [
            await self._to_response(event, user, entry_labels) for event in items
        ]
        return AdminEventListResponse(items=responses, total=len(responses))

    async def get_event(self, user: User, event_id: UUID) -> AdminEventResponse:
        event = await self.event_repo.get_by_id(event_id)
        if event is None or not await self._visible(user, event):
            raise AdminEventDomainError("Event not found", http_status=404)
        return await self._to_response(event, user)

    # ------------------------------------------------------------------
    # OCC-1 — occurrence options read model
    # ------------------------------------------------------------------

    async def list_occurrence_options(
        self,
        user: User,
        *,
        for_date: date,
        event_type: Optional[EventType] = None,
    ) -> AdminOccurrenceOptionsResponse:
        """The selectable timetable occurrences for event creation on one
        date — the exact data the Events UI needs, resolved entirely on the
        backend (the frontend never reconstructs it from the weekly
        timetable):

          - canonical day resolution via the frozen calendar engine (weekend
            default, active closures, working-Saturday override, substitution
            schedule) — on a non-working day the list is empty and
            `non_working_reason` explains why;
          - the effective schedule weekday (substitution applied) picks the
            ACTIVE timetable entries;
          - the acting admin's section/subject scope is applied (HEAD all;
            CLASS sections; ELECTIVE exact subjects — resolved from the DB,
            never from the client);
          - `event_type` narrows to the registry's allowed class types
            (CLASS_CANCELLED -> Lecture/Tutorial, LAB_CANCELLED ->
            Practical);
          - shared elective-slot entries keep their anchor subject and carry
            the concrete catalog members the occurrence may be narrowed to
            (canonical ElectiveResolver anchors — never leaked or guessed).
        """
        section_ids, subject_ids = await self.authz.resolve_admin_scope_filters(user)

        events = await self.calendar_repo.get_all_events(active=True)
        day = get_academic_day(for_date, events, DEFAULT_WEEKENDS)
        non_working_reason: Optional[str] = None
        if not day.is_working_day:
            dominant = day.events[0] if day.events else None
            non_working_reason = (
                get_rule(dominant.event_type).display_name
                if dominant is not None
                else "Weekend"
            )
        # The weekday whose schedule this date follows (substitution-aware) —
        # the same resolution the synchronizer applies.
        schedule_day = day.substitution_schedule_override or day.original_day_of_week
        day_of_week = DAY_NAMES.index(schedule_day)

        items: List[AdminOccurrenceOption] = []
        if day.is_working_day:
            allowed_class_types = None
            if event_type is not None:
                allowed_class_types = get_rule(event_type).allowed_class_types or None
            entries = await self.timetable_repo.list_entries(
                section_ids=(
                    list(section_ids) if section_ids is not None else None
                ),
                subject_ids=(
                    list(subject_ids) if subject_ids is not None else None
                ),
                day_of_week=day_of_week,
                is_active=True,
            )
            members_by_slot = await self._elective_members_by_slot()
            anchors = await ElectiveResolver(self.db).anchor_subjects()
            for entry in entries:
                if (
                    allowed_class_types is not None
                    and entry.class_type not in allowed_class_types
                ):
                    continue
                subject = entry.subject
                slot_members = (
                    members_by_slot.get(entry.elective_slot, [])
                    if entry.elective_slot is not None
                    else []
                )
                is_slot_anchor = (
                    entry.elective_slot is not None
                    and entry.elective_slot in anchors
                    and anchors[entry.elective_slot].id == entry.subject_id
                )
                items.append(
                    AdminOccurrenceOption(
                        timetable_entry_id=entry.id,
                        subject_id=entry.subject_id,
                        subject_code=subject.code,
                        subject_name=subject.name,
                        class_type=entry.class_type,
                        start_time=entry.start_time,
                        end_time=entry.end_time,
                        section_id=entry.section_id,
                        section_name=entry.section.name,
                        subsection_id=entry.subsection_id,
                        subsection_name=(
                            entry.subsection.name if entry.subsection else None
                        ),
                        elective_slot=entry.elective_slot,
                        is_slot_anchor=is_slot_anchor,
                        elective_subjects=[
                            AdminOccurrenceElectiveSubject(
                                id=m.id, code=m.code, name=m.name
                            )
                            for m in slot_members
                        ],
                        display_label=self._occurrence_label(entry),
                    )
                )
        return AdminOccurrenceOptionsResponse(
            date=for_date,
            event_type=event_type,
            is_working_day=day.is_working_day,
            day_type=day.day_type,
            schedule_day=schedule_day,
            non_working_reason=non_working_reason,
            items=items,
            total=len(items),
        )

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
