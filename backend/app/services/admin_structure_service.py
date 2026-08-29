"""
Phase 24.5 — Admin Structure Service.

Business logic for academic hierarchy CRUD (AcademicSession -> Semester ->
Section -> Subsection). All mutations are HEAD_ADMIN only — this service
trusts that the calling endpoint has already enforced require_head_admin.

Key invariants enforced here:
  - At most one active AcademicSession (Phase 24.5 documented invariant:
    reject 409
    if activating a session while another is already active).  The caller
    must explicitly deactivate the current active session first.
  - Duplicate name detection before DB flush (avoids unhandled IntegrityError).
  - Registration-ambiguity warnings surfaced in mutation responses when
    multiple semesters or sections exist under the active session (new
    student self-registration will fail with 409 until resolved).
  - No destructive deletes (Gate 7 unresolved).
  - No side effects on students / enrollments / elective choices / timetable.
"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicSession, Semester
from app.models.user import Section, Subsection
from app.repositories.admin_structure_repo import AdminStructureRepository
from app.schemas.admin_structure import (
    AcademicSessionResponse,
    CreateSessionRequest,
    UpdateSessionRequest,
    SessionActivationResponse,
    SemesterResponse,
    CreateSemesterRequest,
    UpdateSemesterRequest,
    SemesterMutationResponse,
    SectionResponse,
    CreateSectionRequest,
    UpdateSectionRequest,
    SectionMutationResponse,
    SubsectionAdminResponse,
    CreateSubsectionRequest,
    UpdateSubsectionRequest,
    RegistrationWarning,
)


class AdminStructureService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AdminStructureRepository(db)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _session_response(
        self, session: AcademicSession, semester_count: int
    ) -> AcademicSessionResponse:
        return AcademicSessionResponse(
            id=session.id,
            name=session.name,
            start_date=session.start_date,
            end_date=session.end_date,
            is_active=session.is_active,
            semester_count=semester_count,
        )

    def _semester_response(
        self, semester: Semester, session_name: str, section_count: int
    ) -> SemesterResponse:
        return SemesterResponse(
            id=semester.id,
            name=semester.name,
            session_id=semester.session_id,
            session_name=session_name,
            start_date=semester.start_date,
            end_date=semester.end_date,
            section_count=section_count,
        )

    def _section_response(
        self,
        section: Section,
        semester_name: str,
        subsection_count: int,
        student_count: int,
    ) -> SectionResponse:
        return SectionResponse(
            id=section.id,
            name=section.name,
            program=section.program,
            semester_id=section.semester_id,
            semester_name=semester_name,
            subsection_count=subsection_count,
            student_count=student_count,
        )

    def _subsection_response(
        self, sub: Subsection, section_name: str, student_count: int
    ) -> SubsectionAdminResponse:
        return SubsectionAdminResponse(
            id=sub.id,
            name=sub.name,
            section_id=sub.section_id,
            section_name=section_name,
            max_strength=sub.max_strength,
            student_count=student_count,
        )

    async def _registration_warnings_for_session(
        self, session: AcademicSession
    ) -> List[RegistrationWarning]:
        """Surface registration-ambiguity warnings if this active session
        has multiple semesters."""
        warnings: List[RegistrationWarning] = []
        if not session.is_active:
            return warnings
        semester_count = await self.repo.count_semesters_for_session(session.id)
        if semester_count > 1:
            warnings.append(RegistrationWarning(
                code="MULTI_SEMESTER",
                message=(
                    f"The active session '{session.name}' now has {semester_count} semesters. "
                    "Student self-registration will fail with 409 until only one semester exists."
                ),
            ))
        return warnings

    async def _registration_warnings_for_semester(
        self, semester: Semester, session: AcademicSession
    ) -> List[RegistrationWarning]:
        """Surface registration-ambiguity warnings if the active session's
        semester now has multiple sections."""
        warnings: List[RegistrationWarning] = []
        if not session.is_active:
            return warnings
        # Only the active session's semester is relevant to registration.
        semesters = await self.repo.list_semesters(session.id)
        if len(semesters) > 1:
            warnings.append(RegistrationWarning(
                code="MULTI_SEMESTER",
                message=(
                    f"The active session '{session.name}' now has {len(semesters)} semesters. "
                    "Student self-registration will fail with 409 until only one semester exists."
                ),
            ))
        if any(s.id == semester.id for s in semesters):
            section_count = await self.repo.count_sections_for_semester(semester.id)
            if section_count > 1:
                warnings.append(RegistrationWarning(
                    code="MULTI_SECTION",
                    message=(
                        f"Semester '{semester.name}' now has {section_count} sections. "
                        "Student self-registration will fail with 409 until only one section exists."
                    ),
                ))
        return warnings

    # ------------------------------------------------------------------
    # AcademicSession
    # ------------------------------------------------------------------

    async def list_sessions(self) -> List[AcademicSessionResponse]:
        sessions = await self.repo.list_sessions()
        result = []
        for s in sessions:
            count = await self.repo.count_semesters_for_session(s.id)
            result.append(self._session_response(s, count))
        return result

    async def get_session(self, session_id: UUID) -> AcademicSessionResponse:
        session = await self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        count = await self.repo.count_semesters_for_session(session.id)
        return self._session_response(session, count)

    async def create_session(
        self, request: CreateSessionRequest
    ) -> AcademicSessionResponse:
        if request.end_date <= request.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date must be after start_date",
            )
        if await self.repo.session_name_exists(request.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An academic session named '{request.name}' already exists",
            )
        session = AcademicSession(
            name=request.name,
            start_date=request.start_date,
            end_date=request.end_date,
            is_active=False,  # always starts inactive; explicit activation required
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return self._session_response(session, 0)

    async def update_session(
        self, session_id: UUID, request: UpdateSessionRequest
    ) -> AcademicSessionResponse:
        session = await self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if request.name is not None and request.name != session.name:
            if await self.repo.session_name_exists(request.name, exclude_id=session_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"An academic session named '{request.name}' already exists",
                )
            session.name = request.name
        if request.start_date is not None:
            session.start_date = request.start_date
        if request.end_date is not None:
            session.end_date = request.end_date
        if session.end_date <= session.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date must be after start_date",
            )
        await self.db.commit()
        await self.db.refresh(session)
        count = await self.repo.count_semesters_for_session(session.id)
        return self._session_response(session, count)

    async def activate_session(self, session_id: UUID) -> SessionActivationResponse:
        """Explicitly activate a session.

        Phase 24.5 documented invariant: at most one active session.  If
        another session
        is already active, reject with 409.  The caller must first explicitly
        deactivate the current active session.
        """
        session = await self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if session.is_active:
            return SessionActivationResponse(id=session.id, name=session.name, is_active=True)
        active = await self.repo.get_active_session()
        if active is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Session '{active.name}' is already active. "
                    "Explicitly deactivate it first before activating another session."
                ),
            )
        session.is_active = True
        await self.db.commit()
        await self.db.refresh(session)
        warnings = await self._registration_warnings_for_session(session)
        return SessionActivationResponse(
            id=session.id, name=session.name, is_active=True, warnings=warnings
        )

    async def deactivate_session(self, session_id: UUID) -> SessionActivationResponse:
        session = await self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if not session.is_active:
            return SessionActivationResponse(id=session.id, name=session.name, is_active=False)
        session.is_active = False
        await self.db.commit()
        await self.db.refresh(session)
        return SessionActivationResponse(id=session.id, name=session.name, is_active=False)

    # ------------------------------------------------------------------
    # Semester
    # ------------------------------------------------------------------

    async def list_semesters(self, session_id: UUID) -> List[SemesterResponse]:
        session = await self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        semesters = await self.repo.list_semesters(session_id)
        result = []
        for sem in semesters:
            count = await self.repo.count_sections_for_semester(sem.id)
            result.append(self._semester_response(sem, session.name, count))
        return result

    async def create_semester(
        self, session_id: UUID, request: CreateSemesterRequest
    ) -> SemesterMutationResponse:
        session = await self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if request.end_date <= request.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date must be after start_date",
            )
        semester = Semester(
            name=request.name,
            session_id=session_id,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        self.db.add(semester)
        await self.db.commit()
        await self.db.refresh(semester)
        count = await self.repo.count_sections_for_semester(semester.id)
        sem_response = self._semester_response(semester, session.name, count)
        warnings = await self._registration_warnings_for_session(session)
        return SemesterMutationResponse(semester=sem_response, warnings=warnings)

    async def update_semester(
        self, semester_id: UUID, request: UpdateSemesterRequest
    ) -> SemesterMutationResponse:
        semester = await self.repo.get_semester(semester_id)
        if not semester:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found")
        session = await self.repo.get_session(semester.session_id)
        if request.name is not None:
            semester.name = request.name
        if request.start_date is not None:
            semester.start_date = request.start_date
        if request.end_date is not None:
            semester.end_date = request.end_date
        if semester.end_date <= semester.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date must be after start_date",
            )
        await self.db.commit()
        await self.db.refresh(semester)
        count = await self.repo.count_sections_for_semester(semester.id)
        session_name = session.name if session else ""
        sem_response = self._semester_response(semester, session_name, count)
        warnings = await self._registration_warnings_for_session(session) if session else []
        return SemesterMutationResponse(semester=sem_response, warnings=warnings)

    # ------------------------------------------------------------------
    # Section
    # ------------------------------------------------------------------

    async def list_sections(self, semester_id: UUID) -> List[SectionResponse]:
        semester = await self.repo.get_semester(semester_id)
        if not semester:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found")
        sections = await self.repo.list_sections(semester_id)
        result = []
        for sec in sections:
            sub_count = await self.repo.count_subsections_for_section(sec.id)
            stu_count = await self.repo.count_students_for_section(sec.id)
            result.append(self._section_response(sec, semester.name, sub_count, stu_count))
        return result

    async def create_section(
        self, semester_id: UUID, request: CreateSectionRequest
    ) -> SectionMutationResponse:
        semester = await self.repo.get_semester(semester_id)
        if not semester:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found")
        if await self.repo.section_name_exists(semester_id, request.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A section named '{request.name}' already exists in this semester",
            )
        section = Section(
            name=request.name,
            program=request.program,
            semester_id=semester_id,
        )
        self.db.add(section)
        await self.db.commit()
        await self.db.refresh(section)
        sub_count = await self.repo.count_subsections_for_section(section.id)
        stu_count = await self.repo.count_students_for_section(section.id)
        sec_response = self._section_response(section, semester.name, sub_count, stu_count)
        session = await self.repo.get_session(semester.session_id)
        warnings = await self._registration_warnings_for_semester(semester, session) if session else []
        return SectionMutationResponse(section=sec_response, warnings=warnings)

    async def update_section(
        self, section_id: UUID, request: UpdateSectionRequest
    ) -> SectionMutationResponse:
        section = await self.repo.get_section(section_id)
        if not section:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
        semester = await self.repo.get_semester(section.semester_id)
        if request.name is not None and request.name != section.name:
            if await self.repo.section_name_exists(section.semester_id, request.name, exclude_id=section_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A section named '{request.name}' already exists in this semester",
                )
            section.name = request.name
        if request.program is not None:
            section.program = request.program
        await self.db.commit()
        await self.db.refresh(section)
        sub_count = await self.repo.count_subsections_for_section(section.id)
        stu_count = await self.repo.count_students_for_section(section.id)
        semester_name = semester.name if semester else ""
        sec_response = self._section_response(section, semester_name, sub_count, stu_count)
        if semester:
            session = await self.repo.get_session(semester.session_id)
            warnings = await self._registration_warnings_for_semester(semester, session) if session else []
        else:
            warnings = []
        return SectionMutationResponse(section=sec_response, warnings=warnings)

    # ------------------------------------------------------------------
    # Subsection
    # ------------------------------------------------------------------

    async def list_subsections(self, section_id: UUID) -> List[SubsectionAdminResponse]:
        section = await self.repo.get_section(section_id)
        if not section:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
        subsections = await self.repo.list_subsections(section_id)
        result = []
        for sub in subsections:
            stu_count = await self.repo.count_students_for_subsection(sub.id)
            result.append(self._subsection_response(sub, section.name, stu_count))
        return result

    async def create_subsection(
        self, section_id: UUID, request: CreateSubsectionRequest
    ) -> SubsectionAdminResponse:
        section = await self.repo.get_section(section_id)
        if not section:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
        if await self.repo.subsection_name_exists(section_id, request.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A subsection named '{request.name}' already exists in this section",
            )
        sub = Subsection(
            name=request.name,
            section_id=section_id,
            max_strength=request.max_strength,
        )
        self.db.add(sub)
        await self.db.commit()
        await self.db.refresh(sub)
        stu_count = await self.repo.count_students_for_subsection(sub.id)
        return self._subsection_response(sub, section.name, stu_count)

    async def update_subsection(
        self, subsection_id: UUID, request: UpdateSubsectionRequest
    ) -> SubsectionAdminResponse:
        sub = await self.repo.get_subsection(subsection_id)
        if not sub:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subsection not found")
        section = await self.repo.get_section(sub.section_id)
        if request.name is not None and request.name != sub.name:
            if await self.repo.subsection_name_exists(sub.section_id, request.name, exclude_id=subsection_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A subsection named '{request.name}' already exists in this section",
                )
            sub.name = request.name
        if request.max_strength is not None:
            sub.max_strength = request.max_strength
        await self.db.commit()
        await self.db.refresh(sub)
        stu_count = await self.repo.count_students_for_subsection(sub.id)
        section_name = section.name if section else ""
        return self._subsection_response(sub, section_name, stu_count)
