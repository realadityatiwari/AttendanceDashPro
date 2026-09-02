"""
Phase 24.8 — Admin Quiz Management service.

Manages the canonical quiz configuration (QuizSchedule rows + cycle/policy
reads) and keeps the QUIZ_DAY AcademicEvent reality synchronized with the
admin plan.

CANONICAL SOURCE-OF-TRUTH RELATIONSHIP (repository evidence):
    Admin configuration (QuizSchedule plan)  --this service-->
        QUIZ_DAY AcademicEvent (canonical runtime quiz-date authority)
            --EventSessionSynchronizer (Phase 6.6)-->
                class_sessions quiz-day occurrence
            --EligibilityService-->
                student eligibility read model
    Runtime quiz dates are read by eligibility from ACTIVE QUIZ_DAY
    AcademicEvents (QuizRepository.get_effective_quiz_dates_for_subjects);
    QuizSchedule is the derived projection/plan this service manages.

A quiz configuration mutation and its required QUIZ_DAY synchronization are
atomic: the schedule row, the derived event, and the session reconciliation
all commit (or roll back) in ONE transaction.  No multi-commit workflow can
leave schedule reality stale.

Authorization:
  - Reads: `require_any_admin` + server-side subject scope (HEAD all,
    CLASS assigned section's semester, ELECTIVE exact subject, SUBSECTION
    inert).
  - Writes: `require_head_admin` only (Phase 24.0 matrix: Manage quiz
    schedules = FULL | NO | NO | NO).
"""

from datetime import date
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ElectiveSlot, EventType, SubjectCategory
from app.models.quiz import QuizSchedule, ScheduleStatus
from app.models.event import AcademicEvent
from app.models.user import User
from app.repositories.admin_quiz_repo import AdminQuizRepository
from app.repositories.event_repo import EventRepository
from app.services.authorization_service import AuthorizationService
from app.services.event_registry import validate_event
from app.services.event_session_service import EventSessionSynchronizer
from app.schemas.admin_quizzes import (
    AdminQuizCycleListResponse,
    AdminQuizCycleResponse,
    AdminQuizScheduleListResponse,
    AdminQuizScheduleMutationResponse,
    AdminQuizScheduleResponse,
    CreateQuizScheduleRequest,
    UpdateQuizScheduleRequest,
)


# ---------------------------------------------------------------------------
# Domain errors (mapped to HTTP in the endpoint layer)
# ---------------------------------------------------------------------------

class AdminQuizError(Exception):
    code = "QUIZ_ADMIN_ERROR"

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class AdminQuizNotFoundError(AdminQuizError):
    code = "NOT_FOUND"


class AdminQuizInvalidScopeError(AdminQuizError):
    code = "INVALID_SCOPE"


class AdminQuizValidationError(AdminQuizError):
    code = "INVALID"


class AdminQuizConflictError(AdminQuizError):
    code = "CONFLICT"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AdminQuizService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AdminQuizRepository(db)
        self.event_repo = EventRepository(db)
        self.sync = EventSessionSynchronizer(db)

    # ------------------------------------------------------------------
    # Scope resolution (reads) — Phase 23.11 reuse
    # ------------------------------------------------------------------

    async def _can_view_subject(self, user: User, subject_id: UUID) -> bool:
        """Whether the acting admin may see a subject's quiz schedules.
        HEAD any; CLASS the assigned section's semester (semester-wide);
        ELECTIVE the exact assigned subject; SUBSECTION inert."""
        return await AuthorizationService(self.db).can_access_subject(user, subject_id)

    # ------------------------------------------------------------------
    # Read model composition
    # ------------------------------------------------------------------

    async def _to_response(self, schedule: QuizSchedule) -> AdminQuizScheduleResponse:
        subject = schedule.subject
        cycle = schedule.quiz_cycle
        has_event = False
        if schedule.date is not None:
            has_event = (
                await self.repo.find_quiz_day_event(
                    schedule.subject_id, schedule.date, schedule.elective_slot,
                    active_only=True,
                )
            ) is not None
        return AdminQuizScheduleResponse(
            id=schedule.id,
            subject_id=schedule.subject_id,
            subject_code=subject.code if subject else "",
            subject_name=subject.name if subject else "",
            cycle_number=cycle.cycle_number if cycle else 0,
            cycle_label=cycle.label if cycle else "",
            elective_slot=schedule.elective_slot,
            date=schedule.date,
            schedule_status=schedule.schedule_status,
            has_active_event=has_event,
            is_elective=schedule.elective_slot is not None,
        )

    async def list_quiz_schedules(
        self,
        user: User,
        *,
        cycle_number: Optional[int] = None,
        semester_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
    ) -> AdminQuizScheduleListResponse:
        schedules = await self.repo.list_quiz_schedules(
            cycle_number=cycle_number,
            semester_id=semester_id,
            session_id=session_id,
        )
        visible = []
        for schedule in schedules:
            if await self._can_view_subject(user, schedule.subject_id):
                visible.append(schedule)
        items = [await self._to_response(s) for s in visible]
        return AdminQuizScheduleListResponse(items=items, total=len(items))

    async def get_quiz_schedule(self, user: User, schedule_id: UUID) -> AdminQuizScheduleResponse:
        schedule = await self.repo.get_quiz_schedule(schedule_id)
        if schedule is None or not await self._can_view_subject(user, schedule.subject_id):
            raise AdminQuizNotFoundError("Quiz schedule not found")
        return await self._to_response(schedule)

    async def list_quiz_cycles(self, user: User) -> AdminQuizCycleListResponse:
        # Cycle/policy reads are scoped the same way as schedules.
        cycles = await self.repo.list_quiz_cycles()
        items = [
            AdminQuizCycleResponse(
                id=c.id,
                cycle_number=c.cycle_number,
                label=c.label,
                lecture_threshold=c.policy.lecture_threshold if c.policy else 0.0,
                combined_threshold=c.policy.combined_threshold if c.policy else None,
            )
            for c in cycles
        ]
        return AdminQuizCycleListResponse(items=items, total=len(items))

    # ------------------------------------------------------------------
    # Validation (HEAD writes only — enforced at the endpoint)
    # ------------------------------------------------------------------

    async def _validate_target(
        self,
        subject_id: UUID,
        elective_slot: Optional[ElectiveSlot],
    ) -> Tuple[object, Optional[ElectiveSlot]]:
        """Validate the subject and its elective relationship.

        - subject must exist and be quiz-applicable theory (not lab);
        - an elective schedule must use an elective-catalog subject whose
          slot matches (anchor BCS-054/BCS-058 carry the marker); a common
          subject cannot masquerade as a logical elective; a DE subject must
          carry its slot marker; DE-I can never use a DE-II subject and vice
          versa.
        Returns (subject, effective_elective_slot).
        """
        subject = await self.repo.get_subject(subject_id)
        if subject is None:
            raise AdminQuizNotFoundError("Subject not found")
        if not subject.quiz_applicable or subject.category == SubjectCategory.LAB:
            raise AdminQuizValidationError(
                "Quizzes can only be scheduled for quiz-applicable theory subjects"
            )
        if elective_slot is not None:
            if subject.elective_slot != elective_slot:
                raise AdminQuizValidationError(
                    f"Subject '{subject.code}' is in the "
                    f"{(subject.elective_slot.value if subject.elective_slot else 'common')} "
                    f"catalog, not slot '{elective_slot.value}'; a quiz schedule "
                    "for a logical elective slot must use the matching elective "
                    "catalog subject"
                )
            return subject, elective_slot
        if subject.elective_slot is not None:
            raise AdminQuizValidationError(
                f"Subject '{subject.code}' is a Departmental Elective catalog "
                f"subject ({subject.elective_slot.value}); its quiz schedule "
                "must carry the matching elective_slot marker (common subjects "
                "cannot be scheduled for a logical elective)"
            )
        return subject, None

    async def _validate_date_in_context(self, subject, quiz_date: date) -> None:
        """Reject a quiz date outside the subject's semester when the semester
        has concrete bounds (established invariant)."""
        # Resolve the semester via a bounded query (avoids async lazy-load).
        from app.models.academic import Semester
        semester = None
        if subject.semester_id is not None:
            semester = (await self.db.execute(
                select(Semester).where(Semester.id == subject.semester_id)
            )).scalars().first()
        if semester is None:
            return
        if semester.start_date is not None and quiz_date < semester.start_date:
            raise AdminQuizValidationError(
                f"Quiz date {quiz_date} is before the semester start "
                f"({semester.start_date})"
            )
        if semester.end_date is not None and quiz_date > semester.end_date:
            raise AdminQuizValidationError(
                f"Quiz date {quiz_date} is after the semester end "
                f"({semester.end_date})"
            )

    # ------------------------------------------------------------------
    # QUIZ_DAY event synchronization (single canonical path, atomic)
    # ------------------------------------------------------------------

    async def _retire_quiz_event(
        self, subject_id: UUID, quiz_date: date, elective_slot: Optional[ElectiveSlot]
    ) -> bool:
        """Deactivate the active QUIZ_DAY event at an exact (subject, date, slot).
        Used when a schedule's date moves, or the schedule is cancelled/
        unresolved — the old date's event must be retired.  Since a subject
        has one schedule per cycle, each with a DISTINCT date, the identity
        (subject, date, slot) uniquely identifies the event belonging to this
        schedule.  Returns True when an event was actually deactivated."""
        if quiz_date is None:
            return False
        event = await self.repo.find_quiz_day_event(
            subject_id, quiz_date, elective_slot, active_only=True
        )
        if event is None:
            return False
        event.active = False
        await self.sync.sync_event(event)
        return True

    async def _ensure_quiz_event(
        self, schedule: QuizSchedule, quiz_date: Optional[date]
    ) -> bool:
        """Create an active QUIZ_DAY event for the schedule if one doesn't
        already exist at (subject, date, slot).  Idempotent — never duplicates.
        The EventSessionSynchronizer reconciles class_sessions.  Returns True
        when a new event was created."""
        if quiz_date is None:
            return False
        existing = await self.repo.find_quiz_day_event(
            schedule.subject_id, quiz_date, schedule.elective_slot, active_only=True
        )
        if existing is not None:
            return False
        subject, effective_slot = await self._validate_target(
            schedule.subject_id, schedule.elective_slot
        )
        validate_event(
            event_type=EventType.QUIZ_DAY,
            start_date=quiz_date,
            end_date=quiz_date,
            subject_id=schedule.subject_id,
            elective_slot=effective_slot,
            subject_category=subject.category,
        )
        event = AcademicEvent(
            event_type=EventType.QUIZ_DAY,
            start_date=quiz_date,
            end_date=quiz_date,
            subject_id=schedule.subject_id,
            elective_slot=effective_slot,
            active=True,
        )
        self.event_repo.add(event)
        await self.event_repo.flush()
        await self.sync.sync_event(event)
        return True

    # ------------------------------------------------------------------
    # Writes (HEAD_ADMIN only)
    # ------------------------------------------------------------------

    async def create_quiz_schedule(
        self, user: User, request: CreateQuizScheduleRequest
    ) -> AdminQuizScheduleMutationResponse:
        subject, effective_slot = await self._validate_target(
            request.subject_id, request.elective_slot
        )
        cycle = await self.repo.get_quiz_cycle(request.quiz_cycle_id)
        if cycle is None:
            raise AdminQuizNotFoundError("Quiz cycle not found")
        if await self.repo.schedule_exists_for_subject_cycle(
            request.subject_id, request.quiz_cycle_id
        ):
            raise AdminQuizConflictError(
                "A quiz schedule already exists for this subject and cycle"
            )
        if request.date is not None:
            await self._validate_date_in_context(subject, request.date)
        if request.schedule_status == ScheduleStatus.SCHEDULED and request.date is None:
            # A SCHEDULED schedule without a date is an unresolved state.
            request.schedule_status = ScheduleStatus.UNRESOLVED

        schedule = QuizSchedule(
            subject_id=request.subject_id,
            quiz_cycle_id=request.quiz_cycle_id,
            elective_slot=effective_slot,
            date=request.date,
            schedule_status=request.schedule_status,
        )
        self.db.add(schedule)
        await self.db.flush()
        created = await self._ensure_quiz_event(schedule, schedule.date)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        refreshed = await self.repo.get_quiz_schedule(schedule.id)
        # Phase 11C-P4: post-commit canonical notification side-channel for the
        # affected users (best-effort, isolated — never affects the mutation).
        await self._notify_quiz_users(schedule)
        return AdminQuizScheduleMutationResponse(
            schedule=await self._to_response(refreshed),
            event_created=created,
            event_deactivated=False,
        )

    async def update_quiz_schedule(
        self, user: User, schedule_id: UUID, request: UpdateQuizScheduleRequest
    ) -> AdminQuizScheduleMutationResponse:
        schedule = await self.repo.get_quiz_schedule(schedule_id)
        if schedule is None:
            raise AdminQuizNotFoundError("Quiz schedule not found")

        fields = request.model_fields_set
        new_status = request.schedule_status if "schedule_status" in fields else schedule.schedule_status
        new_date = request.date if "date" in fields else schedule.date

        if new_status == ScheduleStatus.SCHEDULED and new_date is None:
            new_status = ScheduleStatus.UNRESOLVED
        if new_date is not None:
            subject = await self.repo.get_subject(schedule.subject_id)
            if subject is not None:
                await self._validate_date_in_context(subject, new_date)

        old_date = schedule.date

        # Retire the old-date event when the schedule moves away from it
        # (date moved, cancelled, or unresolved).  Each schedule's event is
        # uniquely identified by (subject, date, slot) — a subject's cycles
        # have DISTINCT dates, so this never touches another cycle's event.
        deactivated = False
        if old_date is not None and (new_date != old_date or new_status != ScheduleStatus.SCHEDULED):
            deactivated = await self._retire_quiz_event(
                schedule.subject_id, old_date, schedule.elective_slot
            )

        schedule.schedule_status = new_status
        schedule.date = new_date

        # Create the new-date event when the schedule is scheduled+dated and
        # no event exists at the new identity yet (idempotent).
        created = False
        if new_status == ScheduleStatus.SCHEDULED:
            created = await self._ensure_quiz_event(schedule, new_date)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        refreshed = await self.repo.get_quiz_schedule(schedule.id)
        # Phase 11C-P4: post-commit canonical notification side-channel for the
        # affected users (best-effort, isolated — never affects the mutation).
        await self._notify_quiz_users(schedule)
        return AdminQuizScheduleMutationResponse(
            schedule=await self._to_response(refreshed),
            event_created=created,
            event_deactivated=deactivated,
        )

    # ── Phase 11C-P4 notification trigger helper ──────────────────────────────

    async def _notify_quiz_users(self, schedule) -> None:
        """Re-evaluate QUIZ_APPROACHING for every user affected by a quiz
        schedule mutation. Best-effort — never raises."""
        try:
            from app.services.notification_service import NotificationService
            from app.repositories.user_repo import UserRepository

            affected: set[UUID] = set()
            affected.update(
                await UserRepository(self.db).get_enrolled_user_ids(schedule.subject_id)
            )
            if schedule.elective_slot is not None:
                for c in await UserRepository(self.db).get_elective_choices_for_slot(
                    schedule.elective_slot
                ):
                    affected.add(c.user_id)

            notif = NotificationService(self.db, push_dispatch=None)
            for uid in affected:
                await notif.after_quiz_mutation(uid)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Quiz schedule notification trigger failed (schedule=%s)", schedule.id
            )
