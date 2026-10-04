"""
Authoritative departmental-elective resolution (Phase 22.4, Phase 23.5).

Frozen semantics — Phase 22.4 established the per-student resolution
architecture. Phase 23.5 made the elective catalog DB-backed
(``subjects.elective_slot``) instead of hardcoded code constants.

Departmental Elective-I / Elective-II are LOGICAL SLOTS, not user-facing
subjects. The shared institutional schedule (timetable, class sessions, quiz
schedules, academic events) keeps concrete anchor subjects (BCS-054 for
Elective-I, BCS-058 for Elective-II) and marks the slot. This module is the
single source of truth for:

  - the elective catalog (which subject codes belong to which slot — DB-backed
    via ``subjects.elective_slot``, scoped to the active academic session),
  - the shared slot anchors (the concrete subjects the schedule uses to
    represent each slot — still ``ANCHOR_CODES`` constants),
  - per-student resolution: logical slot -> the student's selected concrete
    subject via their ``StudentElectiveChoice``.

Every consumer (registration, timetable, attendance, quiz, events, calendar,
dashboard, notifications) resolves through this module instead of embedding
its own lookup logic. Resolution NEVER fabricates a student's elective:
a missing choice falls back to the shared anchor (ADMIN / pre-selection
users keep the anchor behavior), and a choice is never borrowed from another
student.
"""

from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import StudentElectiveChoice, Subject
from app.models.enums import ElectiveSlot
from app.repositories.subject_repo import SubjectRepository

# ---------------------------------------------------------------------------
# Shared schedule anchors (Phase 22.3).
# These are the concrete subjects the institutional SCHEDULE uses to represent
# each logical slot (timetable anchors, session anchors, quiz/event anchors).
# They are NOT the catalog — the catalog is DB-backed via subjects.elective_slot.
# ---------------------------------------------------------------------------
ANCHOR_CODES: Dict[ElectiveSlot, str] = {
    ElectiveSlot.ELECTIVE_I: "BCS-054",
    ElectiveSlot.ELECTIVE_II: "BCS-058",
}


class ElectiveResolver:
    """Domain-level authoritative resolver: logical slot -> student's subject.

    Phase 23.5: the elective catalog is now DB-backed (``subjects.elective_slot``).
    ``catalog_codes()``, ``slot_for_code()``, and ``validate_selection()`` are
    async methods that read from the database — no more hardcoded constants.

    All per-request lookups are loaded once (the student's two choices, the
    catalog, the two anchor subjects) and resolved in memory — never one query
    per timetable/session/event/quiz item.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._subject_repo = SubjectRepository(db)
        self._catalog: Optional[Dict[ElectiveSlot, List[str]]] = None

    # ------------------------------------------------------------------
    # DB-backed catalog (Phase 23.5)
    # ------------------------------------------------------------------
    async def catalog_codes(self) -> Dict[ElectiveSlot, List[str]]:
        """The authoritative elective catalog from the DB: slot -> ordered
        subject codes. Scoped to the active academic session's semester
        (one query, lazily cached per instance)."""
        if self._catalog is not None:
            return self._catalog
        from app.models.academic import AcademicSession, Semester

        catalog: Dict[ElectiveSlot, List[str]] = {
            ElectiveSlot.ELECTIVE_I: [],
            ElectiveSlot.ELECTIVE_II: [],
        }
        result = await self.db.execute(
            select(Subject.code, Subject.elective_slot)
            .join(Semester, Semester.id == Subject.semester_id)
            .join(AcademicSession, AcademicSession.id == Semester.session_id)
            .where(
                AcademicSession.is_active.is_(True),
                Subject.elective_slot.isnot(None),
            )
        )
        for code, slot in result.all():
            if slot in catalog:
                catalog[slot].append(code)
        for slot in catalog.values():
            slot.sort()
        self._catalog = catalog
        return self._catalog

    async def slot_for_code(self, code: str) -> Optional[ElectiveSlot]:
        """The slot a subject code belongs to per the DB catalog, or None
        for non-elective subjects or codes not in the current semester."""
        for slot, codes in (await self.catalog_codes()).items():
            if code in codes:
                return slot
        return None

    async def validate_selection(
        self, elective_i: str, elective_ii: str
    ) -> Optional[str]:
        """Returns an error message when either selection is invalid per the
        DB catalog, else None."""
        catalog = await self.catalog_codes()
        if elective_i not in catalog[ElectiveSlot.ELECTIVE_I]:
            return "Invalid Department Elective-I selection"
        if elective_ii not in catalog[ElectiveSlot.ELECTIVE_II]:
            return "Invalid Department Elective-II selection"
        return None

    # ------------------------------------------------------------------
    # Per-student choice resolution (Phase 22.3/22.4 — unchanged)
    # ------------------------------------------------------------------
    async def load_choices(self, user_id: Optional[UUID]) -> Dict[ElectiveSlot, StudentElectiveChoice]:
        """The student's StudentElectiveChoice rows keyed by slot (empty when
        the user has no recorded selection — ADMIN or a pre-selection user)."""
        if not user_id:
            return {}
        result = await self.db.execute(
            select(StudentElectiveChoice)
            .options(selectinload(StudentElectiveChoice.subject))
            .where(StudentElectiveChoice.user_id == user_id)
        )
        return {c.elective_slot: c for c in result.scalars().all()}

    async def chosen_elective_map(self, user_id: Optional[UUID]) -> Dict[UUID, ElectiveSlot]:
        """subject_id -> the slot the student chose it for (empty for users
        with no recorded choices). Used to resolve quiz dates/eligibility."""
        return {
            choice.subject_id: slot
            for slot, choice in (await self.load_choices(user_id)).items()
        }

    async def anchor_subjects(self) -> Dict[ElectiveSlot, Subject]:
        """The shared anchor subjects for both slots (BCS-054 / BCS-058).

        Perf batch 1: fetched by exact code (two unique-code lookups) instead
        of loading the entire subjects table and filtering in Python — the
        result dict is identical (a slot key is present only when its anchor
        subject exists)."""
        subjects: Dict[ElectiveSlot, Subject] = {}
        for slot, code in ANCHOR_CODES.items():
            subject = await self._subject_repo.get_by_code(code)
            if subject is not None:
                subjects[slot] = subject
        return subjects

    async def anchor_subject_for_slot(self, slot: ElectiveSlot) -> Optional[Subject]:
        return await self._subject_repo.get_by_code(ANCHOR_CODES[slot])

    @staticmethod
    def resolve_subject(
        choice_map: Dict[ElectiveSlot, StudentElectiveChoice],
        slot: Optional[ElectiveSlot],
        fallback_subject: Subject,
    ) -> Subject:
        """The effective subject of a slot-scoped academic item for a student.

        - slot with a recorded choice -> the student's selected subject;
        - otherwise -> the shared anchor fallback (never fabricated).
        """
        if slot is not None:
            choice = choice_map.get(slot)
            if choice is not None:
                return choice.subject
        return fallback_subject

    async def resolve_events(
        self,
        events,
        choice_map: Dict[ElectiveSlot, StudentElectiveChoice],
    ) -> list:
        """Resolve every subject-scoped event's effective subject for a user.

        Returns AcademicEventResponse objects with `resolved_subject_id` /
        `resolved_subject_code` / `resolved_subject_name` attached:
        - elective-slot events resolve to the student's chosen subject (or the
          anchor when no choice exists — ADMIN keeps the anchor behavior);
        - regular subject events resolve to their own subject.
        
        This method is NON-MUTATING: it creates new response objects instead
        of modifying the original ORM event instances. This ensures that
        resolving events for one student does not affect resolution for another.
        
        Two queries total (choices + subjects), independent of event count.
        """
        from app.models.academic import Subject as SubjectModel
        from app.schemas.calendar import AcademicEventResponse

        anchor_map = await self.anchor_subjects()

        subject_ids = {
            e.subject_id
            for e in events
            if e.subject_id is not None
            and (e.elective_slot is None or e.elective_slot not in choice_map)
        }
        subject_by_id: Dict[UUID, SubjectModel] = {}
        if subject_ids:
            result = await self.db.execute(
                select(SubjectModel).where(SubjectModel.id.in_(subject_ids))
            )
            subject_by_id = {s.id: s for s in result.scalars().all()}

        # Build response objects without mutating the original events
        responses = []
        for e in events:
            if e.elective_slot is not None:
                choice = choice_map.get(e.elective_slot)
                subject = choice.subject if choice is not None else anchor_map.get(e.elective_slot)
            else:
                subject = subject_by_id.get(e.subject_id) if e.subject_id is not None else None
            
            # Create a new AcademicEventResponse with resolved fields
            resolved_id = subject.id if subject is not None else None
            resolved_code = subject.code if subject is not None else None
            resolved_name = subject.name if subject is not None else None
            
            response = AcademicEventResponse(
                id=e.id,
                event_type=e.event_type,
                start_date=e.start_date,
                end_date=e.end_date,
                subject_id=e.subject_id,
                elective_slot=e.elective_slot,
                resolved_subject_id=resolved_id,
                resolved_subject_code=resolved_code,
                resolved_subject_name=resolved_name,
                class_type=e.class_type,
                is_working_day=e.is_working_day,
                substitution_schedule_override=e.substitution_schedule_override,
                note=e.note,
                active=e.active,
            )
            responses.append(response)
            
        return responses