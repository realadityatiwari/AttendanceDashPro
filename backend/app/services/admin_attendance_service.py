"""
Phase 24.12 — Attendance admin & analytics service (READ-ONLY).

Authorization matrix (capability matrix "View analytics" + discovery §19):

  | Operation                          | unauth | STUDENT | HEAD | CLASS | SUBSECTION | ELECTIVE |
  |------------------------------------|--------|---------|------|-------|------------|----------|
  | Section attendance aggregates      | 401    | 403     | all  | own   | empty      | empty    |
  | Subject attendance aggregates      | 401    | 403     | all  | own sem. | empty | own roster |
  | Per-student attendance read        | 401    | 403     | all  | own section students | 404 | own roster |

Scope is resolved per request from AuthorizationService (DB-derived, never
client-supplied). SUBSECTION_ADMIN is conservative-empty (no authoritative
subsection data). The union rule applies (an admin may hold multiple scopes).

Computation: every occurrence is resolved through the canonical per-user
pipeline (elective resolution, occurrence-outcome application,
practical-block collapse) via `group_practical_occurrences`; ERP current/
forecast semantics match AnalyticsService._overall (cancelled excluded,
pending never absent, not an average). No attendance mathematics is
reproduced here and nothing is computed client-side.
"""
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.enums import AdminRole, AttendanceStatus, UserRole
from app.repositories.admin_attendance_repo import AdminAttendanceRepository
from app.schemas.admin_attendance import (
    AdminSectionAttendanceListResponse,
    AdminSectionAttendanceSummary,
    AdminStudentAttendanceResponse,
    AdminSubjectAttendanceListResponse,
    AdminSubjectAttendanceSummary,
)
from app.schemas.analytics import AnalyticsOverviewResponse
from app.services.authorization_service import AuthorizationService
from app.services.analytics_service import AnalyticsService
from app.services.attendance_service import institution_today
from app.services.student_context_service import StudentContextService
from app.engines.practical_occurrence import (
    group_practical_occurrences,
    occurrence_is_cancelled,
)


class AdminAttendanceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AdminAttendanceRepository(db)
        self.authz = AuthorizationService(db)

    # ------------------------------------------------------------------
    # Scope resolution (DB-authoritative)
    # ------------------------------------------------------------------

    async def _resolve_scope(
        self, user: User
    ) -> Tuple[bool, set, set]:
        """Returns (is_global, section_ids, subject_ids)."""
        if await self.authz.is_head_admin(user):
            return True, set(), set()
        scopes = await self.authz.get_active_scopes(user.id)
        section_ids = {
            s.section_id for s in scopes
            if s.role == AdminRole.CLASS_ADMIN and s.section_id is not None
        }
        subject_ids = {
            s.subject_id for s in scopes
            if s.role == AdminRole.ELECTIVE_ADMIN and s.subject_id is not None
        }
        return False, section_ids, subject_ids

    async def _date_range(self) -> Tuple[date, date]:
        """Bounded analytic window: [active-session start, institution today].
        Derives from the real academic context; never hardcoded. Future dates
        are view-only and excluded from pending (mirrors student reads)."""
        from app.models.academic import AcademicSession
        from sqlalchemy import select as _select
        result = await self.db.execute(
            _select(AcademicSession).where(AcademicSession.is_active.is_(True))
        )
        session = result.scalars().first()
        start = session.start_date if session is not None else date(2000, 1, 1)
        end = institution_today()
        if session is not None and session.end_date < end:
            end = session.end_date
        return start, end

    @staticmethod
    def _classify(row: dict) -> str:
        """Canonical occurrence classification for counting."""
        if occurrence_is_cancelled(row):
            return "cancelled"
        if row.get("status") == AttendanceStatus.ATTENDED:
            return "attended"
        if row.get("status") == AttendanceStatus.MISSED:
            return "missed"
        return "pending"

    def _counts(self, rows: List[dict]) -> dict:
        """ERP-style counts over already-collapsed occurrences:
        cancelled excluded from scheduled/attended/missed/pending; extra
        occurrences count as conducted (attended/missed) and are flagged."""
        counts = {
            "scheduled": 0, "cancelled": 0, "extra": 0,
            "attended": 0, "missed": 0, "pending": 0,
        }
        for row in rows:
            cls = self._classify(row)
            if cls == "cancelled":
                counts["cancelled"] += 1
                continue
            counts["scheduled"] += 1
            if row.get("is_extra"):
                counts["extra"] += 1
            counts[cls] += 1
        return counts

    @staticmethod
    def _pcts(counts: dict) -> Tuple[Optional[float], Optional[float]]:
        recorded = counts["attended"] + counts["missed"]
        total = counts["scheduled"]
        current = (counts["attended"] / recorded * 100.0) if recorded > 0 else None
        forecast = ((counts["attended"] + counts["pending"]) / total * 100.0) if total > 0 else None
        return current, forecast

    # ------------------------------------------------------------------
    # Section aggregates
    # ------------------------------------------------------------------

    async def get_section_analytics(self, user: User) -> AdminSectionAttendanceListResponse:
        is_global, section_ids, _ = await self._resolve_scope(user)
        sections = await self.repo.list_sections()
        if not is_global:
            sections = [s for s in sections if s.id in section_ids]
        if not sections:
            start, end = await self._date_range()
            return AdminSectionAttendanceListResponse(
                items=[], total=0, range_start=start, range_end=end
            )

        # ONE aggregate query for every section's students.
        section_student_ids: Dict[UUID, List[UUID]] = {}
        from app.models.user import User as _U
        from sqlalchemy import select as _select
        result = await self.db.execute(
            _select(_U.id, _U.section_id).where(
                _U.role == UserRole.STUDENT, _U.section_id.in_([s.id for s in sections])
            )
        )
        for uid, sid in result.all():
            section_student_ids.setdefault(sid, []).append(uid)

        all_user_ids = [u for ids in section_student_ids.values() for u in ids]
        start, end = await self._date_range()
        rows = await self.repo.get_sessions_with_status_for_users(all_user_ids, start, end)

        # Collapse per user (canonical), then aggregate per section.
        per_user: Dict[UUID, List[dict]] = {}
        for row in rows:
            per_user.setdefault(row["user_id"], []).append(row)
        section_counts: Dict[UUID, dict] = {s.id: {
            "scheduled": 0, "cancelled": 0, "extra": 0,
            "attended": 0, "missed": 0, "pending": 0,
        } for s in sections}
        for uid, user_rows in per_user.items():
            occ = group_practical_occurrences(user_rows)
            sid = next(
                (s for s, ids in section_student_ids.items() if uid in ids), None
            )
            if sid is None:
                continue
            c = self._counts(occ)
            for k in section_counts[sid]:
                section_counts[sid][k] += c[k]

        items = []
        for s in sections:
            c = section_counts[s.id]
            current, forecast = self._pcts(c)
            items.append(AdminSectionAttendanceSummary(
                section_id=s.id,
                section_name=s.name,
                students=len(section_student_ids.get(s.id, [])),
                **c, current_pct=current, forecast_pct=forecast,
            ))
        return AdminSectionAttendanceListResponse(
            items=items, total=len(items), range_start=start, range_end=end
        )

    # ------------------------------------------------------------------
    # Subject aggregates
    # ------------------------------------------------------------------

    async def get_subject_analytics(self, user: User) -> AdminSubjectAttendanceListResponse:
        is_global, section_ids, subject_ids = await self._resolve_scope(user)
        subjects = await self.repo.list_subjects()
        if not is_global:
            if section_ids:
                # CLASS_ADMIN: subjects of their sections' semesters.
                from app.models.user import Section as _S
                from sqlalchemy import select as _select
                res = await self.db.execute(
                    _select(_S.semester_id).where(_S.id.in_(section_ids))
                )
                sem_ids = {r[0] for r in res.all()}
                subjects = [s for s in subjects if s.semester_id in sem_ids]
            else:
                subjects = [s for s in subjects if s.id in subject_ids]
        if not subjects:
            start, end = await self._date_range()
            return AdminSubjectAttendanceListResponse(
                items=[], total=0, range_start=start, range_end=end
            )

        # Roster user ids per subject (STUDENT role only — the legacy ADMIN
        # account is enrolled but is NOT a student population; Phase 24.13
        # truthfulness fix, mirroring the dashboard's STUDENT-role counts).
        from app.models.academic import StudentEnrollment as _E
        from app.models.user import User as _U
        from sqlalchemy import select as _select
        result = await self.db.execute(
            _select(_E.user_id, _E.subject_id)
            .join(_U, _U.id == _E.user_id)
            .where(
                _E.subject_id.in_([s.id for s in subjects]),
                _U.role == UserRole.STUDENT,
            )
        )
        roster: Dict[UUID, List[UUID]] = {}
        for uid, sid in result.all():
            roster.setdefault(sid, []).append(uid)

        all_user_ids = [u for ids in roster.values() for u in ids]
        start, end = await self._date_range()
        rows = await self.repo.get_sessions_with_status_for_users(all_user_ids, start, end)

        per_user: Dict[UUID, List[dict]] = {}
        for row in rows:
            per_user.setdefault(row["user_id"], []).append(row)
        subject_counts: Dict[UUID, dict] = {s.id: {
            "scheduled": 0, "cancelled": 0, "extra": 0,
            "attended": 0, "missed": 0, "pending": 0,
        } for s in subjects}
        for uid, user_rows in per_user.items():
            occ = group_practical_occurrences(user_rows)
            # attribute each occurrence to its resolved subject
            c = self._counts(occ)
            # Count per subject: an occurrence belongs to its resolved subject.
            by_subject: Dict[UUID, dict] = {}
            for row in occ:
                subj = row.get("subject_id")
                if subj is None:
                    continue
                bucket = by_subject.setdefault(subj, {
                    "scheduled": 0, "cancelled": 0, "extra": 0,
                    "attended": 0, "missed": 0, "pending": 0,
                })
                cls = self._classify(row)
                if cls == "cancelled":
                    bucket["cancelled"] += 1
                    continue
                bucket["scheduled"] += 1
                if row.get("is_extra"):
                    bucket["extra"] += 1
                bucket[cls] += 1
            for subj, bucket in by_subject.items():
                if subj in subject_counts:
                    for k in bucket:
                        subject_counts[subj][k] += bucket[k]

        items = []
        for s in subjects:
            c = subject_counts[s.id]
            current, forecast = self._pcts(c)
            items.append(AdminSubjectAttendanceSummary(
                subject_id=s.id, code=s.code, name=s.name,
                roster=len(set(roster.get(s.id, []))),
                **c, current_pct=current, forecast_pct=forecast,
            ))
        return AdminSubjectAttendanceListResponse(
            items=items, total=len(items), range_start=start, range_end=end
        )

    # ------------------------------------------------------------------
    # Per-student read (scope-checked, canonical analytics)
    # ------------------------------------------------------------------

    async def get_student_attendance(self, user: User, student_id: UUID) -> AdminStudentAttendanceResponse:
        student = await self.db.get(User, student_id)
        if not await self._can_access_student(user, student):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
            )
        overview: AnalyticsOverviewResponse = await AnalyticsService(self.db).get_overview(student)
        ctx = await StudentContextService(self.db).get_placement(student)
        return AdminStudentAttendanceResponse(
            **overview.model_dump(),
            student_id=student.id,
            roll_number=student.roll_number,
            student_name=student.name,
            section_name=ctx.section_name,
        )

    async def _can_access_student(self, user: User, student: Optional[User]) -> bool:
        if student is None or student.role != UserRole.STUDENT:
            return False
        is_global, section_ids, subject_ids = await self._resolve_scope(user)
        if is_global:
            return True
        if section_ids and student.section_id in section_ids:
            return True
        if subject_ids:
            from app.models.academic import StudentElectiveChoice as _C
            from sqlalchemy import select as _select
            result = await self.db.execute(
                _select(_C.id).where(
                    _C.user_id == student.id, _C.subject_id.in_(subject_ids)
                ).limit(1)
            )
            if result.scalars().first() is not None:
                return True
        return False
