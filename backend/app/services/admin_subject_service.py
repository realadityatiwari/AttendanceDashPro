"""
Phase 24.6 — Admin Subject / Curriculum Service.

Business logic for curriculum management:
  - scoped subject reads (HEAD all / CLASS own-semester / ELECTIVE own subject
    / SUBSECTION inert-empty)
  - create subject (HEAD_ADMIN only — the endpoint enforces require_head_admin)
  - update subject (HEAD_ADMIN only)

Rules enforced here:
  - duplicate (code, semester_id) -> 409 (UNIQUE backstop uq_subjects_code_semester)
  - invalid semester -> 404
  - code immutable after creation -> 409
  - semester_id immutable after creation -> 409
  - anchor code/slot protected (BCS-054 / BCS-058) -> 409
  - elective-slot change with existing StudentElectiveChoice rows -> 409
  - no deletion/deactivation (no DELETE endpoint; Gate 7 unresolved)
  - invalid combinations rejected rather than silently repaired
  - operational warnings: adding a subject to the active session's semester
    affects future registrations only; existing students are NOT auto-enrolled

Authorization is DB-authoritative via AuthorizationService/require_* deps at
the endpoint layer; this service resolves per-request scope for reads from the
acting admin's ACTIVE admin_scopes (never from the JWT/body/query/frontend).
"""

from typing import List, Optional, Set
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicSession, Semester, Subject
from app.models.enums import AdminRole
from app.models.user import Section, User
from app.repositories.admin_subject_repo import AdminSubjectRepository
from app.schemas.admin_structure import RegistrationWarning
from app.schemas.admin_subjects import (
    AdminSubjectDetail,
    AdminSubjectListResponse,
    AdminSubjectSummary,
    CreateSubjectRequest,
    SubjectMutationResponse,
    UpdateSubjectRequest,
)
from app.services.authorization_service import AuthorizationService
from app.services.elective_resolver import ANCHOR_CODES


class AdminSubjectService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AdminSubjectRepository(db)

    # ------------------------------------------------------------------
    # Scope resolution (server-side, DB-authoritative)
    # ------------------------------------------------------------------

    async def _resolve_visible_subject_ids(self, user: User) -> Optional[Set[UUID]]:
        """The set of subject IDs visible to this admin, or None = ALL.

        - HEAD_ADMIN -> all subjects
        - CLASS_ADMIN -> subjects whose semester is the semester of an
          assigned section (frozen Phase 23.11 semester-wide semantic)
        - ELECTIVE_ADMIN -> the exact concrete subject(s) assigned
        - SUBSECTION_ADMIN -> contributes nothing (inert)
        - a user with no effective admin role -> empty (endpoint 403s earlier)
        """
        authz = AuthorizationService(self.db)
        if await authz.is_head_admin(user):
            return None
        scopes = await authz.get_active_scopes(user.id)

        visible: Set[UUID] = set()
        section_ids = [
            s.section_id for s in scopes
            if s.role == AdminRole.CLASS_ADMIN and s.section_id is not None
        ]
        if section_ids:
            result = await self.db.execute(
                select(Section.semester_id)
                .where(Section.id.in_(section_ids))
            )
            semester_ids = {row[0] for row in result.all()}
            if semester_ids:
                subj_result = await self.db.execute(
                    select(Subject.id).where(Subject.semester_id.in_(semester_ids))
                )
                visible.update(row[0] for row in subj_result.all())

        elective_subject_ids = [
            s.subject_id for s in scopes
            if s.role == AdminRole.ELECTIVE_ADMIN and s.subject_id is not None
        ]
        if elective_subject_ids:
            visible.update(elective_subject_ids)

        return visible

    async def _can_view_subject(self, user: User, subject_id: UUID) -> bool:
        """Per-subject visibility for the detail read.

        Reuses AuthorizationService.can_access_subject (single authority):
        HEAD any, ELECTIVE exact, CLASS own-semester, SUBSECTION denied.
        Out-of-scope/nonexistent -> False (404, no existence leak).
        """
        authz = AuthorizationService(self.db)
        return await authz.can_access_subject(user, subject_id)

    # ------------------------------------------------------------------
    # Read model composition
    # ------------------------------------------------------------------

    @staticmethod
    def _is_anchor(subject: Subject) -> bool:
        return subject.code in set(ANCHOR_CODES.values())

    async def _to_summary(
        self,
        subject: Subject,
        semester: Optional[Semester],
        enrollment_count: int = 0,
        elective_choice_count: int = 0,
    ) -> AdminSubjectSummary:
        semester_name = semester.name if semester else ""
        session_name = ""
        if semester is not None:
            session = (await self.db.execute(
                select(AcademicSession).where(AcademicSession.id == semester.session_id)
            )).scalars().first()
            session_name = session.name if session else ""
        return AdminSubjectSummary(
            id=subject.id,
            code=subject.code,
            name=subject.name,
            tag=subject.tag,
            elective_slot=subject.elective_slot,
            category=subject.category,
            quiz_applicable=subject.quiz_applicable,
            attendance_applicable=subject.attendance_applicable,
            semester_id=subject.semester_id,
            semester_name=semester_name,
            session_name=session_name,
            is_anchor=self._is_anchor(subject),
            enrollment_count=enrollment_count,
            elective_choice_count=elective_choice_count,
        )

    async def _to_detail(
        self, subject: Subject, semester: Optional[Semester]
    ) -> AdminSubjectDetail:
        summary = await self._to_summary(subject, semester)
        return AdminSubjectDetail(
            **summary.model_dump(),
            timetable_entry_count=await self.repo.count_timetable_entries(subject.id),
            class_session_count=await self.repo.count_class_sessions(subject.id),
            quiz_schedule_count=await self.repo.count_quiz_schedules(subject.id),
            lab_experiment_count=await self.repo.count_lab_experiments(subject.id),
            attendance_record_count=await self.repo.count_attendance_records(subject.id),
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def list_subjects(self, user: User) -> AdminSubjectListResponse:
        subjects = await self.repo.list_subjects()
        visible_ids = await self._resolve_visible_subject_ids(user)
        if visible_ids is not None:
            subjects = [s for s in subjects if s.id in visible_ids]

        if not subjects:
            return AdminSubjectListResponse(items=[], total=0)

        subject_ids = [s.id for s in subjects]
        enrollments = await self.repo.count_enrollments_by_subject(subject_ids)
        choices = await self.repo.count_elective_choices_by_subject(subject_ids)

        items = []
        for subject in subjects:
            semester = await self.repo.get_semester(subject.semester_id)
            items.append(await self._to_summary(
                subject,
                semester,
                enrollment_count=enrollments.get(subject.id, 0),
                elective_choice_count=choices.get(subject.id, 0),
            ))
        return AdminSubjectListResponse(items=items, total=len(items))

    async def get_subject(self, user: User, subject_id: UUID) -> AdminSubjectDetail:
        subject = await self.repo.get_subject(subject_id)
        if not subject or not await self._can_view_subject(user, subject_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
        semester = await self.repo.get_semester(subject.semester_id)
        return await self._to_detail(subject, semester)

    # ------------------------------------------------------------------
    # Writes (HEAD_ADMIN only — enforced by the endpoint dependency)
    # ------------------------------------------------------------------

    async def create_subject(
        self, request: CreateSubjectRequest
    ) -> SubjectMutationResponse:
        semester = await self.repo.get_semester(request.semester_id)
        if not semester:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found")

        if await self.repo.subject_code_exists_in_semester(
            request.semester_id, request.code
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A subject with code '{request.code}' already exists "
                    "in this semester"
                ),
            )

        subject = Subject(
            code=request.code,
            name=request.name,
            tag=request.tag,
            elective_slot=request.elective_slot,
            category=request.category,
            quiz_applicable=request.quiz_applicable,
            attendance_applicable=request.attendance_applicable,
            semester_id=request.semester_id,
        )
        self.db.add(subject)
        await self.db.commit()
        await self.db.refresh(subject)

        detail = await self._to_detail(subject, semester)
        warnings = await self._creation_warnings(semester)
        return SubjectMutationResponse(subject=detail, warnings=warnings)

    async def update_subject(
        self, subject_id: UUID, request: UpdateSubjectRequest
    ) -> SubjectMutationResponse:
        subject = await self.repo.get_subject(subject_id)
        if not subject:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
        semester = await self.repo.get_semester(subject.semester_id)

        fields = request.model_fields_set

        # 1. code immutable -> 409
        if "code" in fields and request.code is not None and request.code != subject.code:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Subject code is immutable after creation",
            )

        # 2. semester_id immutable -> 409
        if "semester_id" in fields and request.semester_id is not None and request.semester_id != subject.semester_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Subject semester is immutable after creation",
            )

        is_anchor = self._is_anchor(subject)

        # 3. elective-slot change: anchor protection + choice-dependency guard
        if "elective_slot" in fields and request.elective_slot != subject.elective_slot:
            if is_anchor:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Anchor subject '{subject.code}' has a frozen "
                        "elective-slot assignment and cannot be changed"
                    ),
                )
            choice_count = await self.repo.count_elective_choices(subject.id)
            if choice_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Cannot change elective slot of '{subject.code}': "
                        f"{choice_count} student elective choice(s) reference it. "
                        "Do not modify student elective choices from Phase 24.6."
                    ),
                )

        # 4. name / tag / category / applicability flags (explicit PATCH)
        if "name" in fields and request.name is not None:
            subject.name = request.name
        if "tag" in fields:
            # explicit null clears the tag
            subject.tag = request.tag
        if "elective_slot" in fields:
            subject.elective_slot = request.elective_slot
        if "category" in fields and request.category is not None:
            subject.category = request.category
        if "quiz_applicable" in fields and request.quiz_applicable is not None:
            subject.quiz_applicable = request.quiz_applicable
        if "attendance_applicable" in fields and request.attendance_applicable is not None:
            subject.attendance_applicable = request.attendance_applicable

        await self.db.commit()
        await self.db.refresh(subject)

        detail = await self._to_detail(subject, semester)
        warnings = []
        return SubjectMutationResponse(subject=detail, warnings=warnings)

    # ------------------------------------------------------------------
    # Warnings
    # ------------------------------------------------------------------

    async def _creation_warnings(self, semester: Semester) -> List[RegistrationWarning]:
        """Operational warnings for creating a subject.

        Adding a subject to the ACTIVE session's semester affects FUTURE
        self-registrations (they auto-enroll in every subject of that
        semester); existing students are NOT automatically enrolled.
        """
        warnings: List[RegistrationWarning] = []
        active = await self.repo.get_active_session()
        if active is not None and semester.session_id == active.id:
            warnings.append(RegistrationWarning(
                code="ACTIVE_SESSION_SUBJECT_ADDED",
                message=(
                    f"Subject added to '{active.name}' (active session). "
                    "Future student self-registrations will be enrolled in it. "
                    "Existing students are NOT automatically enrolled."
                ),
            ))
        return warnings
