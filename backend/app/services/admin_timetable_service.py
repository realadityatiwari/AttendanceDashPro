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
    DuplicateTimetableEntryRequest,
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

    def __init__(self, detail: str, conflicts: Optional[List[dict]] = None):
        """Conflict error carrying the structured conflicting-entry list.

        ``conflicts`` is a list of dicts with the fields the backend actually
        resolved: ``id``, ``subject_code``, ``day_of_week``, ``start_time``,
        ``end_time``, ``section_name``, ``subsection_name``, ``elective_slot``.
        The UI renders ONLY these backend-returned fields — it never infers
        conflict data from stale client state.
        """
        super().__init__(detail)
        self.conflicts = conflicts or []


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

    async def _assert_write_scope(self, user: User, section_id: UUID) -> None:
        """STRICT write gate (authoritative Phase 24.0 matrix).

        Timetable creation/editing/deactivation/duplication is reserved to:
          - HEAD_ADMIN (any section), and
          - CLASS_ADMIN (only the assigned section(s)).
        ELECTIVE_ADMIN and SUBSECTION_ADMIN may READ (scoped) but NEVER write
        the timetable — an elective admin's write surface is the event path
        (CLASS_CANCELLED / EXTRA_*) — so they are denied 403 here.
        """
        authz = AuthorizationService(self.db)
        if await authz.is_head_admin(user):
            return
        scopes = await authz.get_active_scopes(user.id)
        if any(
            s.role == AdminRole.CLASS_ADMIN
            and s.section_id is not None
            and s.section_id == section_id
            for s in scopes
        ):
            return
        raise TimetableInvalidScopeError(
            "Timetable modifications require global or section-scoped "
            "administrator authority"
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
        entry.  Bounded: only active same-section/same-day candidates.

        Each conflict dict carries ONLY fields the backend resolved — the UI
        renders these verbatim and never infers from stale client state.
        """
        candidates = await self.repo.list_active_conflict_candidates(
            entry.section_id, entry.day_of_week, exclude_id=exclude_id
        )
        conflicts = []
        for cand in candidates:
            if self._entries_conflict(entry, cand):
                conflicts.append({
                    "id": str(cand.id),
                    "subject_code": cand.subject.code if cand.subject else "?",
                    "subject_name": cand.subject.name if cand.subject else "",
                    "section_name": cand.section.name if cand.section else "",
                    "subsection_name": cand.subsection.name if cand.subsection else None,
                    "day_of_week": cand.day_of_week,
                    "start_time": cand.start_time.isoformat(),
                    "end_time": cand.end_time.isoformat(),
                    "subsection_id": str(cand.subsection_id) if cand.subsection_id else None,
                    "elective_slot": cand.elective_slot.value if cand.elective_slot else None,
                })
        return conflicts

    @staticmethod
    def _format_conflicts(conflicts: List[dict]) -> str:
        """Human-readable conflict summary for the 409 detail.

        Scope context included: section, subsection (when set), day label,
        and the conflicting time range + subject — all backend-returned.
        """
        day_labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        parts = []
        for c in conflicts:
            label = day_labels[c["day_of_week"]] if 0 <= c["day_of_week"] <= 6 else f"day {c['day_of_week']}"
            scope = c["section_name"] or ""
            if c.get("subsection_name"):
                scope = f"{scope} / {c['subsection_name']}" if scope else c["subsection_name"]
            desc = f"{c['subject_code']} on {label} {c['start_time'][:5]}-{c['end_time'][:5]}"
            if scope:
                desc = f"{desc} ({scope})"
            parts.append(desc)
        return "; ".join(parts)

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
        self,
        user: User,
        *,
        session_id: Optional[UUID] = None,
        semester_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
        subsection_id: Optional[UUID] = None,
        day_of_week: Optional[int] = None,
        is_active: Optional[bool] = None,
        subject_id: Optional[UUID] = None,
        elective_slot: Optional[ElectiveSlot] = None,
    ) -> TimetableEntryAdminListResponse:
        scope_section_ids, scope_subject_ids = await self._resolve_scope(user)

        # User-provided filters INTERSECT with scope-derived filters — never
        # expand.  This prevents a scoped admin from seeing another section
        # by passing a foreign section_id in the query string.
        section_ids = list(scope_section_ids) if scope_section_ids is not None else None
        if section_id is not None:
            if scope_section_ids is not None and section_id not in scope_section_ids:
                return TimetableEntryAdminListResponse(items=[], total=0)
            section_ids = [section_id]

        subject_ids = list(scope_subject_ids) if scope_subject_ids is not None else None
        if subject_id is not None:
            if scope_subject_ids is not None and subject_id not in scope_subject_ids:
                return TimetableEntryAdminListResponse(items=[], total=0)
            subject_ids = [subject_id]

        # Resolve session/semester to section_ids (bounded join).
        if semester_id is not None or session_id is not None:
            sem_ids = None
            sess_ids = None
            if semester_id is not None:
                sem_ids = [semester_id]
            if session_id is not None:
                sess_ids = [session_id]
            # If the caller already has section-level scope, intersect with
            # the semester/session-resolved section ids.
            from sqlalchemy import select as sel2
            q = sel2(Section.id)
            if sem_ids:
                q = q.where(Section.semester_id.in_(sem_ids))
            if sess_ids:
                from app.models.academic import Semester
                q = (q.join(Semester, Semester.id == Section.semester_id)
                     .where(Semester.session_id.in_(sess_ids)))
            result = await self.db.execute(q)
            resolved_ids = {row[0] for row in result.all()}
            if scope_section_ids is not None:
                resolved_ids &= set(scope_section_ids)
            if not resolved_ids:
                return TimetableEntryAdminListResponse(items=[], total=0)
            section_ids = list(resolved_ids)

        subsection_ids = [subsection_id] if subsection_id is not None else None

        # Default: active entries only (preserves 24.7-B semantics).
        # is_active=True -> active only; is_active=False -> inactive only.
        active_filter = True if is_active is None else is_active

        entries = await self.repo.list_entries(
            section_ids=section_ids,
            subject_ids=subject_ids,
            subsection_ids=subsection_ids,
            day_of_week=day_of_week,
            elective_slot=elective_slot,
            is_active=active_filter,
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
        await self._assert_write_scope(user, request.section_id)
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
                + self._format_conflicts(conflicts),
                conflicts=conflicts,
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
        await self._assert_write_scope(user, entry.section_id)
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

        await self._assert_write_scope(user, new_section_id)
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
                + self._format_conflicts(conflicts),
                conflicts=conflicts,
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
        await self._assert_write_scope(user, entry.section_id)
        await self._assert_section_in_scope(
            entry.section_id, section_ids, subject_ids, subject_id=entry.subject_id
        )
        if entry.is_active:
            entry.is_active = False
            await self.db.commit()
            entry = await self.repo.get_entry(entry.id)
        return self._to_response(entry)

    async def duplicate_entry(
        self, user: User, source_id: UUID, request: DuplicateTimetableEntryRequest
    ) -> TimetableEntryAdminResponse:
        """Server-side duplication of an existing timetable entry.

        Absent override fields are copied from the source entry; the FULL
        resulting entry is validated (academic context, elective slot, time
        range) and conflict detection runs against the prospective entry —
        a duplicate never silently overwrites another timetable entry.
        """
        source = await self.repo.get_entry(source_id)
        if source is None:
            raise TimetableNotFoundError("Timetable entry not found")
        section_ids, subject_ids = await self._resolve_scope(user)
        await self._assert_write_scope(user, source.section_id)
        await self._assert_section_in_scope(
            source.section_id, section_ids, subject_ids, subject_id=source.subject_id
        )

        # Resolve the prospective values: explicit override or source copy.
        new_section_id = request.section_id or source.section_id
        new_subject_id = request.subject_id or source.subject_id
        new_subsection_id = (
            request.subsection_id if request.subsection_id is not None
            else source.subsection_id
        )
        new_elective_slot = (
            request.elective_slot if request.elective_slot is not None
            else source.elective_slot
        )
        new_day = request.day_of_week if request.day_of_week is not None else source.day_of_week
        new_start = request.start_time if request.start_time is not None else source.start_time
        new_end = request.end_time if request.end_time is not None else source.end_time
        new_class_type = request.class_type if request.class_type is not None else source.class_type
        new_room = request.room if request.room is not None else source.room
        new_sort_order = request.sort_order if request.sort_order is not None else source.sort_order

        await self._assert_write_scope(user, new_section_id)
        await self._assert_section_in_scope(
            new_section_id, section_ids, subject_ids, subject_id=new_subject_id
        )
        await self._validate_common(
            new_section_id,
            new_subject_id,
            new_subsection_id,
            new_elective_slot,
            new_class_type,
            new_start,
            new_end,
        )

        entry = TimetableEntry(
            section_id=new_section_id,
            subject_id=new_subject_id,
            subsection_id=new_subsection_id,
            day_of_week=new_day,
            start_time=new_start,
            end_time=new_end,
            class_type=new_class_type,
            room=new_room,
            elective_slot=new_elective_slot,
            is_active=request.is_active,
            sort_order=new_sort_order,
        )
        conflicts = await self._find_conflicts(entry)
        if conflicts:
            raise TimetableTimeConflictError(
                "Duplicated timetable entry conflicts with an existing active entry: "
                + self._format_conflicts(conflicts),
                conflicts=conflicts,
            )
        self.db.add(entry)
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
