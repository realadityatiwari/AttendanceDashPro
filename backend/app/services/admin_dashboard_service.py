"""
HEAD_ADMIN operational dashboard service (Phase 24.2).

Read-only composition of the AdminDashboardRepository's bounded aggregate
queries into the AdminDashboardResponse read model. This service adds no
attendance/eligibility/elective mathematics — every count reads the
authoritative tables, and quiz dates remain the active QUIZ_DAY events.

Authorization is NOT decided here: the endpoint gate (require_head_admin)
is the boundary.
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.admin_dashboard_repo import AdminDashboardRepository
from app.schemas.admin_dashboard import (
    AcademicOverview,
    AdminDashboardResponse,
    AdminDashboardWarning,
    AttendanceOverview,
    CurriculumOverview,
    EventsOverview,
    QuizOverview,
    ScheduleOverview,
    StudentOverview,
    UpcomingEventItem,
)
from app.models.enums import (
    AttendanceStatus,
    EnrollmentType,
    SubjectCategory,
    ElectiveSlot,
)
from app.models.quiz import ScheduleStatus


class AdminDashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AdminDashboardRepository(db)

    async def get_dashboard(self) -> AdminDashboardResponse:
        today = date.today()
        warnings: list[AdminDashboardWarning] = []

        academic = await self._academic(today, warnings)
        curriculum = await self._curriculum()
        students = await self._students(warnings)
        schedule = await self._schedule(warnings)
        events = await self._events()
        quizzes = await self._quizzes()
        attendance = await self._attendance(warnings)

        return AdminDashboardResponse(
            generated_at=today,
            academic=academic,
            curriculum=curriculum,
            students=students,
            schedule=schedule,
            events=events,
            quizzes=quizzes,
            attendance=attendance,
            warnings=warnings,
        )

    async def _academic(self, today: date, warnings: list) -> AcademicOverview:
        active_session_count = await self.repo.count_active_sessions()
        if active_session_count == 0:
            warnings.append(AdminDashboardWarning(
                code="NO_ACTIVE_SESSION",
                severity="warning",
                message="No active academic session is configured. Registration "
                        "and academic reads depend on an active session.",
            ))
        elif active_session_count > 1:
            warnings.append(AdminDashboardWarning(
                code="MULTIPLE_ACTIVE_SESSIONS",
                severity="warning",
                message=f"{active_session_count} academic sessions are marked "
                        "active; exactly one is expected.",
            ))

        session = await self.repo.get_active_session()
        semesters = (
            await self.repo.get_semesters_of_session(session.id)
            if session is not None
            else []
        )
        if session is not None and not semesters:
            warnings.append(AdminDashboardWarning(
                code="NO_SEMESTERS",
                severity="warning",
                message=f"Active session \"{session.name}\" has no semesters.",
            ))

        subject_count = await self.repo.count_subjects()
        if subject_count == 0:
            warnings.append(AdminDashboardWarning(
                code="NO_SUBJECTS",
                severity="warning",
                message="No subjects are registered in the system.",
            ))

        single = semesters[0] if len(semesters) == 1 else None

        return AcademicOverview(
            active_session=session.name if session is not None else None,
            session_start=session.start_date if session is not None else None,
            session_end=session.end_date if session is not None else None,
            active_session_count=active_session_count,
            semester_count=len(semesters),
            semester_name=single.name if single is not None else None,
            semester_start=single.start_date if single is not None else None,
            semester_end=single.end_date if single is not None else None,
            section_count=await self.repo.count_sections(),
            program_count=await self.repo.count_programs(),
            subject_count=subject_count,
            student_count=await self.repo.count_students(),
        )

    async def _curriculum(self) -> CurriculumOverview:
        by_category = dict(await self.repo.count_subjects_by_category())
        by_slot = dict(await self.repo.count_subjects_by_elective_slot())
        by_type = dict(await self.repo.count_enrollments_by_type())

        return CurriculumOverview(
            theory_subjects=int(by_category.get(SubjectCategory.THEORY, 0)),
            lab_subjects=int(by_category.get(SubjectCategory.LAB, 0)),
            elective_i_subjects=int(by_slot.get(ElectiveSlot.ELECTIVE_I, 0)),
            elective_ii_subjects=int(by_slot.get(ElectiveSlot.ELECTIVE_II, 0)),
            compulsory_enrollments=int(by_type.get(EnrollmentType.COMPULSORY, 0)),
            elective_enrollments=int(by_type.get(EnrollmentType.ELECTIVE, 0)),
        )

    async def _students(self, warnings: list) -> StudentOverview:
        total = await self.repo.count_students()
        placed = await self.repo.count_students_placed()
        unplaced = await self.repo.count_students_unplaced()
        subsection_assigned = await self.repo.count_students_subsection_assigned()
        subsection_unassigned = await self.repo.count_students_subsection_unassigned()
        choice_holders = await self.repo.count_elective_choice_holders()
        choices_total = await self.repo.count_elective_choices()
        unresolved = await self.repo.count_placed_students_without_elective_choices()

        if total == 0:
            warnings.append(AdminDashboardWarning(
                code="NO_STUDENTS",
                severity="warning",
                message="No student accounts are registered.",
            ))
        if unplaced > 0:
            warnings.append(AdminDashboardWarning(
                code="UNPLACED_STUDENTS",
                severity="warning",
                message=f"{unplaced} student(s) have no academic placement "
                        "(no section assigned).",
            ))
        if subsection_unassigned > 0:
            warnings.append(AdminDashboardWarning(
                code="SUBSECTION_UNASSIGNED",
                severity="info",
                message=f"{subsection_unassigned} student(s) have no subsection "
                        "assignment (NULL = UNKNOWN/UNASSIGNED).",
            ))
        if unresolved > 0:
            warnings.append(AdminDashboardWarning(
                code="UNRESOLVED_ELECTIVES",
                severity="warning",
                message=f"{unresolved} placed student(s) have no Department "
                        "Elective selection recorded.",
            ))

        return StudentOverview(
            total=total,
            placed=placed,
            unplaced=unplaced,
            subsection_assigned=subsection_assigned,
            subsection_unassigned=subsection_unassigned,
            elective_choice_holders=choice_holders,
            elective_choices_total=choices_total,
        )

    async def _schedule(self, warnings: list) -> ScheduleOverview:
        today = date.today()
        timetable_count = await self.repo.count_timetable_entries()
        if timetable_count == 0:
            warnings.append(AdminDashboardWarning(
                code="NO_TIMETABLE",
                severity="warning",
                message="No timetable entries are configured.",
            ))

        return ScheduleOverview(
            timetable_entry_count=timetable_count,
            class_session_total=await self.repo.count_class_sessions(),
            class_sessions_cancelled=await self.repo.count_class_sessions_cancelled(),
            class_sessions_extra=await self.repo.count_class_sessions_extra(),
            sessions_today=await self.repo.count_class_sessions_on(today),
            upcoming_sessions=await self.repo.count_class_sessions_from(today),
            occurrence_outcomes=await self.repo.count_occurrence_outcomes(),
        )

    async def _events(self) -> EventsOverview:
        upcoming_rows = await self.repo.get_upcoming_events(limit=5)
        upcoming = [
            UpcomingEventItem(
                id=e.id,
                event_type=e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                start_date=e.start_date,
                end_date=e.end_date,
                subject_code=subject_code,
                elective_slot=e.elective_slot.value if e.elective_slot is not None and hasattr(e.elective_slot, "value") else (str(e.elective_slot) if e.elective_slot is not None else None),
            )
            for e, subject_code in upcoming_rows
        ]
        return EventsOverview(
            total_active=await self.repo.count_active_events(),
            upcoming_active=await self.repo.count_upcoming_active_events(),
            upcoming=upcoming,
        )

    async def _quizzes(self) -> QuizOverview:
        today = date.today()
        by_status = dict(await self.repo.count_quiz_schedules_by_status())
        return QuizOverview(
            cycle_count=await self.repo.count_quiz_cycles(),
            schedule_total=await self.repo.count_quiz_schedules(),
            scheduled_dated=await self.repo.count_quiz_schedules_dated(),
            unresolved=int(by_status.get(ScheduleStatus.UNRESOLVED, 0)),
            cancelled=int(by_status.get(ScheduleStatus.CANCELLED, 0)),
            next_quiz_date=await self.repo.get_next_quiz_date(today),
        )

    async def _attendance(self, warnings: list) -> AttendanceOverview:
        by_status = dict(await self.repo.count_attendance_by_status())
        attended = int(by_status.get(AttendanceStatus.ATTENDED, 0))
        missed = int(by_status.get(AttendanceStatus.MISSED, 0))
        recorded = attended + missed
        recorded_pct = (attended / recorded * 100.0) if recorded > 0 else None

        if recorded == 0:
            warnings.append(AdminDashboardWarning(
                code="NO_ATTENDANCE",
                severity="info",
                message="No attendance records exist yet.",
            ))

        return AttendanceOverview(
            total_records=recorded,
            attended=attended,
            missed=missed,
            recorded_pct=recorded_pct,
            participants=await self.repo.count_attendance_participants(),
        )
