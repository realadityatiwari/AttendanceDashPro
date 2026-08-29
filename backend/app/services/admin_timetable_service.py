"""
Phase 24.7-B — Admin Timetable Service.

The authoritative backend timetable management layer.  Owns ALL timetable
validation and conflict detection; the HTTP layer (Phase 24.7-C) will sit on
top of these methods and map domain errors to the project's API conventions.

DOMAIN ERRORS (raised here, mapped to HTTP in 24.7-C):
  - ``TimetableNotFoundError``         -> NOT_FOUND (404)
  - ``TimetableInvalidScopeError``     -> INVALID_SCOPE (403)
  - ``TimetableInvalidSubjectError``   -> INVALID_SUBJECT (400/422)
  - ``TimetableInvalidSubsectionError``-> INVALID_SUBSECTION (400/422)
  - ``TimetableInvalidElectiveSlotError`` -> INVALID_ELECTIVE_SLOT (400/422)
  - ``TimetableInvalidTimeRangeError`` -> INVALID_TIME_RANGE (400/422)
  - ``TimetableTimeConflictError``     -> TIME_CONFLICT (409)
  - ``TimetableInactiveParentError``   -> INACTIVE_PARENT (409/422)

CONFLICT SEMANTICS (deterministic — recorded verbatim in governance docs):

  Two timetable entries CONFLICT when ALL of the following hold:
    (1) both are ACTIVE (``is_active = true``); inactive entries never block;
    (2) SAME day of week;
    (3) SAME section;
    (4) their [start, end) time ranges OVERLAP:
            existing.start_time < new.end_time
        AND existing.end_time   > new.start_time
        (adjacent entries — 09:00-10:00 and 10:00-11:00 — are NOT a conflict);
    (5) they share the SAME EFFECTIVE SCHEDULING SCOPE:
          - section-wide (subsection_id NULL) vs section-wide       -> CONFLICT
          - section-wide  vs subsection-specific (same section)     -> CONFLICT
            (a section-wide entry covers the same students who are in
             the subsection — the subsection is a partition of the section;
             overlap is a double-booking "when appropriate" -> rejected)
          - subsection-specific vs same subsection                  -> CONFLICT
          - subsection-specific vs DIFFERENT subsection             -> NO CONFLICT
            (parallel schedules for disjoint student groups are allowed)
          - DIFFERENT sections                                      -> NO CONFLICT

  ELECTIVE-SLOT RULE:
    A logical elective slot resolves to DIFFERENT concrete subjects for
    different students.  Two entries BOTH carrying the SAME ``elective_slot``
    (both ELECTIVE_I or both ELECTIVE_II) therefore do NOT conflict merely
    because they share the slot — each student follows only the one concrete
    subject their choice resolves to.  Different slots (ELECTIVE_I vs
    ELECTIVE_II) DO conflict, as does an elective-slot entry vs a regular
    (non-elective) entry — a student attends both.

  This is compatible with the existing ``ElectiveResolver`` anchor model and
  never creates student-specific timetable rows.
"""

from datetime import time as dt_time
from typing import List, Optional, Set
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AdminRole, ClassType, ElectiveSlot
from app.models.timetable import TimetableEntry
from app.models.user import Section, Subsection, User
from app.models.academic import Subject
from app.repositories.admin_timetable_repo import AdminTimetableRepository
from app.services.authorization_service import AuthorizationService
from app.schemas.admin_timetable import (
    CreateTimetableEntryRequest,
    TimetableEntryAdminResponse,
    TimetableEntryAdminListResponse,
    UpdateTimetableEntryRequest,
)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class TimetableDomainError(Exception):
    """Base class for timetable domain errors.  ``code`` is the stable machine
    key; 24.7-C maps it to the project's HTTP error conventions."""

    code = "TIMETABLE_DOMAIN_ERROR"

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class TimetableNotFoundError(TimetableDomainError):
    code = "NOT_FOUND"


class TimetableInvalidScopeError(TimetableDomainError):
    code = "INVALID_SCOPE"


class TimetableInvalidSubjectError(TimetableDomainError):
    code = "INVALID_SUBJECT"


class TimetableInvalidSubsectionError(TimetableDomainError):
    code = "INVALID_SUBSECTION"


class TimetableInvalidElectiveSlotError(TimetableDomainError):
    code = "INVALID_ELECTIVE_SLOT"


class TimetableInvalidTimeRangeError(TimetableDomainError):
    code = "INVALID_TIME_RANGE"


class TimetableTimeConflictError(TimetableDomainError):
    code = "TIME_CONFLICT"


class TimetableInactiveParentError(TimetableDomainError):
    code = "INACTIVE_PARENT"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AdminTimetableService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AdminTimetableRepository(db)

    # ------------------------------------------------------------------
    # Scope resolution (server-side, DB-authoritative — Phase 23.11 reuse)
    # ------------------------------------------------------------------

    async def _resolve_scope(
        self, user: User
    ) -> tuple[Optional[Set[UUID]], Optional[Set[UUID]]]:
        """Return (allowed_section_ids, allowed_subject_ids).  None means
        UNRESTRICTED on that dimension; empty set means nothing visible.

        - HEAD_ADMIN       -> (None, None) — everything
        - CLASS_ADMIN      -> assigned section(s); subjects unrestricted
        - SUBSECTION_ADMIN -> section(s) of the assigned subsection(s)
                              (inert today — no authoritative subsection
                              data, so the section set is empty => nothing)
        - ELECTIVE_ADMIN   -> sections unrestricted; subjects restricted to
                              the exact assigned concrete subject(s)
        An admin holding several scopes gets the union.  A user with NO
        effective admin role -> (empty, empty) — nothing visible (the HTTP
        layer additionally 403s in 24.7-C).
        """
        authz = AuthorizationService(self.db)
        if await authz.is_head_admin(user):
            return None, None
        scopes = await authz.get_active_scopes(user.id)
        if not scopes:
            return set(), set()

        section_ids: Set[UUID] = set()
        subject_ids: Set[UUID] = set()
        for s in scopes:
            if s.role == AdminRole.CLASS_ADMIN and s.section_id:
                section_ids.add(s.section_id)
            elif s.role == AdminRole.SUBSECTION_ADMIN and s.subsection_id:
                sub = await self.repo.get_subsection(s.subsection_id)
                if sub is not None:
                    section_ids.add(sub.section_id)
            elif s.role == AdminRole.ELECTIVE_ADMIN and s.subject_id:
                subject_ids.add(s.subject_id)

        return (
            section_ids if section_ids else None,
            subject_ids if subject_ids else None,
        )

    async def _assert_section_in_scope(
        self,
        section_id: UUID,
        section_ids: Optional[Set[UUID]],
        subject_ids: Optional[Set[UUID]],
        subject_id: Optional[UUID] = None,
    ) -> None:
        """Raise INVALID_SCOPE when the acting user cannot see the section.
        None (unrestricted) passes.  ELECTIVE_ADMIN scope is subject-based:
        an entry is in scope when its subject is the assigned concrete subject
        (even if the section is not in the assigned set)."""
        if section_ids is None and subject_ids is None:
            return
        if section_ids is not None and section_id in section_ids:
            return
        if subject_ids is not None and subject_id is not None and subject_id in subject_ids:
            return
        raise TimetableInvalidScopeError(
            "The target section is outside your administrative scope"
        )

    # ------------------------------------------------------------------
    # Deterministic conflict predicate (recorded in governance docs)
    # ------------------------------------------------------------------

    @staticmethod
    def _time_overlaps(a_start: dt_time, a_end: dt_time, b_start: dt_time, b_end: dt_time) -> bool:
        return a_start < b_end and a_end > b_start

    @classmethod
    def _entries_conflict(cls, a: TimetableEntry, b: TimetableEntry) -> bool:
        """Deterministic conflict test between two entries (see module
        docstring for the exact recorded semantics)."""
        # (1) both active — inactive entries never block.
        if not a.is_active or not b.is_active:
            return False
        # (2) same day.
        if a.day_of_week != b.day_of_week:
            return False
        # (3) same section.
        if a.section_id != b.section_id:
            return False
        # (4) overlapping time ranges (adjacent is allowed).
        if not cls._time_overlaps(a.start_time, a.end_time, b.start_time, b.end_time):
            return False
        # (5) effective scheduling scope.
        # ELECTIVE rule: same slot -> no conflict (per-student resolution).
        if (
            a.elective_slot is not None
            and b.elective_slot is not None
            and a.elective_slot == b.elective_slot
        ):
            return False
        # Section-wide vs section-wide -> conflict.
        if a.subsection_id is None and b.subsection_id is None:
            return True
        # Section-wide vs subsection-specific -> conflict (same students).
        if a.subsection_id is None or b.subsection_id is None:
            return True
        # Subsection-specific vs different subsection -> parallel, allowed.
        if a.subsection_id != b.subsection_id:
            return False
        # Subsection-specific vs same subsection -> conflict.
        return True

    async def _find_conflicts(
        self, entry: TimetableEntry, exclude_id: Optional[UUID] = None
    ) -> List[dict]:
        """Return conflicting entries (deterministic) for a prospective
        entry.  Bounded: only active same-section/same-day candidates."""
        candidates = await self.repo.list_active_conflict_candidates(
            entry.section_id, entry.day_of_week, exclude_id=exclude_id
        )
        conflicts = []
        for cand in candidates:
            if self._entries_conflict(entry, cand):
                conflicts.append({
                    "id": cand.id,
                    "subject_code": cand.subject.code if cand.subject else "?",
                    "day_of_week": cand.day_of_week,
                    "start_time": cand.start_time.isoformat(),
                    "end_time": cand.end_time.isoformat(),
                    "subsection_id": cand.subsection_id,
                    "elective_slot": cand.elective_slot.value if cand.elective_slot else None,
                })
        return conflicts

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    async def _validate_common(
        self,
        section_id: UUID,
        subject_id: UUID,
        subsection_id: Optional[UUID],
        elective_slot: Optional[ElectiveSlot],
        class_type: ClassType,
        start_time: dt_time,
        end_time: dt_time,
    ) -> tuple[Section, Subject, Optional[Subsection]]:
        """Academic-context validation shared by create/update.  Raises the
        appropriate domain error."""
        # Section exists.
        section = await self.repo.get_section(section_id)
        if section is None:
            raise TimetableNotFoundError("Section not found")
        # Subject exists.
        subject = await self.repo.get_subject(subject_id)
        if subject is None:
            raise TimetableInvalidSubjectError("Subject not found")
        # Subject compatible with the section's academic context: the subject
        # must belong to the SAME semester as the section.
        if subject.semester_id != section.semester_id:
            raise TimetableInvalidSubjectError(
                f"Subject '{subject.code}' belongs to a different semester "
                "than the section's semester and cannot be scheduled for it"
            )
        # Subsection, when provided, must exist AND belong to the section.
        resolved_subsection: Optional[Subsection] = None
        if subsection_id is not None:
            resolved_subsection = await self.repo.get_subsection(subsection_id)
            if resolved_subsection is None:
                raise TimetableInvalidSubsectionError("Subsection not found")
            if resolved_subsection.section_id != section_id:
                raise TimetableInvalidSubsectionError(
                    "Subsection does not belong to the entry's section"
                )
        # Time range.
        if end_time <= start_time:
            raise TimetableInvalidTimeRangeError(
                "end_time must be after start_time"
            )
        # Elective-slot relationship: an entry with an elective slot must use a
        # subject that is in that same slot's catalog; a non-elective entry
        # must not carry an elective slot; an elective-catalog subject must
        # keep its slot marker consistent with its catalog slot.
        if elective_slot is not None and subject.elective_slot != elective_slot:
            raise TimetableInvalidElectiveSlotError(
                f"Subject '{subject.code}' is in the "
                f"{(subject.elective_slot.value if subject.elective_slot else 'common')} "
                f"catalog, not slot '{elective_slot.value}'; elective-slot marker "
                "must match the subject's catalog slot"
            )
        if elective_slot is None and subject.elective_slot is not None:
            raise TimetableInvalidElectiveSlotError(
                f"Subject '{subject.code}' is an elective-catalog subject "
                f"({subject.elective_slot.value}); the timetable entry must carry "
                "that same elective_slot marker"
            )
        return section, subject, resolved_subsection

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def list_entries(
        self, user: User, *, day_of_week: Optional[int] = None, include_inactive: bool = False
    ) -> TimetableEntryAdminListResponse:
        section_ids, subject_ids = await self._resolve_scope(user)
        entries = await self.repo.list_entries(
            section_ids=list(section_ids) if section_ids is not None else None,
            subject_ids=list(subject_ids) if subject_ids is not None else None,
            day_of_week=day_of_week,
            include_inactive=include_inactive,
        )
        items = [self._to_response(e) for e in entries]
        return TimetableEntryAdminListResponse(items=items, total=len(items))

    async def get_entry(self, user: User, entry_id: UUID) -> TimetableEntryAdminResponse:
        entry = await self.repo.get_entry(entry_id)
        if entry is None:
            raise TimetableNotFoundError("Timetable entry not found")
        section_ids, subject_ids = await self._resolve_scope(user)
        await self._assert_section_in_scope(
            entry.section_id, section_ids, subject_ids, subject_id=entry.subject_id
        )
        return self._to_response(entry)

    # ------------------------------------------------------------------
    # Writes (authorization per-scope here; HEAD gate is 24.7-C)
    # ------------------------------------------------------------------

    async def create_entry(
        self, user: User, request: CreateTimetableEntryRequest
    ) -> TimetableEntryAdminResponse:
        section_ids, subject_ids = await self._resolve_scope(user)
        await self._assert_section_in_scope(
            request.section_id, section_ids, subject_ids, subject_id=request.subject_id
        )
        section, subject, subsection = await self._validate_common(
            request.section_id,
            request.subject_id,
            request.subsection_id,
            request.elective_slot,
            request.class_type,
            request.start_time,
            request.end_time,
        )

        entry = TimetableEntry(
            section_id=request.section_id,
            subject_id=request.subject_id,
            subsection_id=request.subsection_id,
            day_of_week=request.day_of_week,
            start_time=request.start_time,
            end_time=request.end_time,
            class_type=request.class_type,
            room=request.room,
            elective_slot=request.elective_slot,
            is_active=request.is_active,
            sort_order=request.sort_order,
        )
        conflicts = await self._find_conflicts(entry)
        if conflicts:
            raise TimetableTimeConflictError(
                "Timetable entry conflicts with an existing active entry: "
                + "; ".join(
                    f"{c['subject_code']} day {c['day_of_week']} "
                    f"{c['start_time']}-{c['end_time']}"
                    for c in conflicts
                )
            )
        self.db.add(entry)
        await self.db.commit()
        entry = await self.repo.get_entry(entry.id)
        return self._to_response(entry)

    async def update_entry(
        self, user: User, entry_id: UUID, request: UpdateTimetableEntryRequest
    ) -> TimetableEntryAdminResponse:
        entry = await self.repo.get_entry(entry_id)
        if entry is None:
            raise TimetableNotFoundError("Timetable entry not found")
        section_ids, subject_ids = await self._resolve_scope(user)
        await self._assert_section_in_scope(
            entry.section_id, section_ids, subject_ids, subject_id=entry.subject_id
        )

        fields = request.model_fields_set

        # Determine the POST-update values (explicit-PATCH: absent = unchanged).
        new_section_id = request.section_id if "section_id" in fields else entry.section_id
        new_subject_id = request.subject_id if "subject_id" in fields else entry.subject_id
        new_subsection_id = (
            request.subsection_id if "subsection_id" in fields else entry.subsection_id
        )
        new_elective_slot = (
            request.elective_slot if "elective_slot" in fields else entry.elective_slot
        )
        new_day = request.day_of_week if "day_of_week" in fields else entry.day_of_week
        new_start = request.start_time if "start_time" in fields else entry.start_time
        new_end = request.end_time if "end_time" in fields else entry.end_time
        new_class_type = request.class_type if "class_type" in fields else entry.class_type
        new_is_active = request.is_active if "is_active" in fields else entry.is_active

        # A deactivated entry may only be reactivated; scheduling edits on a
        # dormant entry are refused (reactivate first — it re-runs conflict
        # detection).
        if not entry.is_active and not new_is_active:
            scheduling_changed = (
                "section_id" in fields or "subject_id" in fields or "subsection_id" in fields
                or "day_of_week" in fields or "start_time" in fields or "end_time" in fields
                or "elective_slot" in fields or "class_type" in fields
            )
            if scheduling_changed:
                raise TimetableInactiveParentError(
                    "This timetable entry is inactive; scheduling edits require "
                    "reactivation (set is_active=true) so conflict detection re-runs"
                )

        await self._assert_section_in_scope(
            new_section_id, section_ids, subject_ids, subject_id=new_subject_id
        )
        section, subject, subsection = await self._validate_common(
            new_section_id,
            new_subject_id,
            new_subsection_id,
            new_elective_slot,
            new_class_type,
            new_start,
            new_end,
        )

        # Build the prospective entry and run conflict detection against
        # everything EXCEPT itself.
        prospective = TimetableEntry(
            section_id=new_section_id,
            subject_id=new_subject_id,
            subsection_id=new_subsection_id,
            day_of_week=new_day,
            start_time=new_start,
            end_time=new_end,
            class_type=new_class_type,
            elective_slot=new_elective_slot,
            is_active=new_is_active,
        )
        prospective.subject = subject
        conflicts = await self._find_conflicts(prospective, exclude_id=entry.id)
        if conflicts:
            raise TimetableTimeConflictError(
                "Updated timetable entry conflicts with an existing active entry: "
                + "; ".join(
                    f"{c['subject_code']} day {c['day_of_week']} "
                    f"{c['start_time']}-{c['end_time']}"
                    for c in conflicts
                )
            )

        # Apply.
        entry.section_id = new_section_id
        entry.subject_id = new_subject_id
        entry.subsection_id = new_subsection_id
        entry.day_of_week = new_day
        entry.start_time = new_start
        entry.end_time = new_end
        entry.class_type = new_class_type
        entry.elective_slot = new_elective_slot
        entry.is_active = new_is_active
        if "room" in fields:
            entry.room = request.room
        if "sort_order" in fields:
            entry.sort_order = request.sort_order
        await self.db.commit()
        entry = await self.repo.get_entry(entry.id)
        return self._to_response(entry)

    async def deactivate_entry(self, user: User, entry_id: UUID) -> TimetableEntryAdminResponse:
        entry = await self.repo.get_entry(entry_id)
        if entry is None:
            raise TimetableNotFoundError("Timetable entry not found")
        section_ids, subject_ids = await self._resolve_scope(user)
        await self._assert_section_in_scope(
            entry.section_id, section_ids, subject_ids, subject_id=entry.subject_id
        )
        if entry.is_active:
            entry.is_active = False
            await self.db.commit()
            entry = await self.repo.get_entry(entry.id)
        return self._to_response(entry)

    # ------------------------------------------------------------------
    # Response composition
    # ------------------------------------------------------------------

    def _to_response(self, e: TimetableEntry) -> TimetableEntryAdminResponse:
        return TimetableEntryAdminResponse(
            id=e.id,
            section_id=e.section_id,
            section_name=e.section.name if e.section else "",
            subsection_id=e.subsection_id,
            subsection_name=e.subsection.name if e.subsection else None,
            subject_id=e.subject_id,
            subject_code=e.subject.code if e.subject else "",
            subject_name=e.subject.name if e.subject else "",
            day_of_week=e.day_of_week,
            start_time=e.start_time,
            end_time=e.end_time,
            class_type=e.class_type,
            room=e.room,
            elective_slot=e.elective_slot,
            is_active=e.is_active,
            sort_order=e.sort_order,
        )
