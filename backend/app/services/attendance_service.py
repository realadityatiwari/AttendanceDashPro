from datetime import date
from uuid import UUID
from typing import Optional, Dict, Any, List
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.user_repo import UserRepository
from app.models.user import User
from app.models.attendance import AttendanceRecord
from app.models.enums import AttendanceStatus
from app.engines.attendance_engine import (
    compute_subject_stats,
    normalize_class_type,
    optimize_attendance,
    classify_attendance_status,
    classify_attendance_health,
)
from app.schemas.attendance import SubjectAttendanceSummary, DailySessionsResponse, DailySessionResponse

# Subject-level optimizer target (Phase 8.0 contract): the documented academic
# attendance requirement for the general (non-quiz-window) subject optimizer.
# This is the legacy `policies.attendance.targetPercentage` default (75) and the
# attendance engine's own default (`compute_subject_stats(target_pct=75.0)`).
SUBJECT_OPTIMIZATION_TARGET_PCT = 75.0


def _build_subject_summary(subject_code: str, counts: Dict[str, Any], mid_sem=None) -> SubjectAttendanceSummary:
    """
    Composes the canonical per-subject summary (attendance engine) with the
    Phase 8.1 additive analytics fields, all derived from the same counts:

      - practical attendance % (current recorded-only, forecast pending-as-
        attended) - canonical class-session/attendance-record pipeline, no quiz
        window dependency (Phase 8.0 contract 4);
      - subject-level 75% optimization (must-attend / safe-skip) via the
        attendance engine's own optimizer (Phase 8.0 contract 5).

    The engine's `compute_subject_stats` is reused unchanged; no attendance
    mathematics is reproduced here.
    """
    summary = compute_subject_stats(subject_code, {'counts': counts})

    # Additive Attendance-UI-refinement fields: the required target and the
    # canonical current status band (engine-owned; never computed in React).
    summary.required_pct = SUBJECT_OPTIMIZATION_TARGET_PCT
    summary.status = classify_attendance_status(summary.current_avg_pct)

    # Phase 8.2 Attendance Health: the canonical 4-state classification of the
    # subject's OVERALL attendance, emitted by the backend (React never bands).
    summary.health = classify_attendance_health(summary.current_avg_pct)

    # Phase 8.2 mid-semester practical designation: the actual scheduled
    # PRACTICAL session designated by admin/faculty (None until designated).
    if mid_sem:
        summary.mid_sem_session_id = mid_sem[0]
        summary.mid_sem_session_date = mid_sem[1]

    p = counts.get('P', {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0})
    done_p = p['att'] + p['miss']
    if done_p > 0:
        summary.current_practical_pct = (p['att'] / done_p) * 100.0
    if p['tot'] > 0:
        summary.forecast_practical_pct = ((p['att'] + p['pending']) / p['tot']) * 100.0

    l = counts.get('L', {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0})
    t = counts.get('T', {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0})
    summary.optimization = optimize_attendance(
        l['tot'], l['att'], l['miss'], l['pending'],
        t['tot'], t['att'], t['miss'], t['pending'],
        SUBJECT_OPTIMIZATION_TARGET_PCT,
    )
    return summary


class AttendanceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AttendanceRepository(db)
        
    async def get_summary(self, user_id: UUID, subject_id: UUID, subject_code: str, as_of_date: date) -> SubjectAttendanceSummary:
        raw_counts = await self.repo.get_subject_counts_up_to_date(user_id, subject_id, as_of_date)
        counts = self._aggregate_counts(raw_counts)
        mid_sem = (await self.repo.get_mid_sem_sessions([subject_id])).get(subject_id)
        return _build_subject_summary(subject_code, counts, mid_sem=mid_sem)

    @staticmethod
    def _aggregate_counts(raw_counts) -> Dict[str, Any]:
        """Canonical (subject_id, class_type, status) rows -> L/T/P count buckets.
        Shared by get_summary and get_subject_summaries so the batched path
        produces byte-identical buckets to the per-subject path."""
        counts: Dict[str, Any] = {
            'L': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
            'T': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
            'P': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
        }
        for row in raw_counts:
            # Row shape: (subject_id, class_type, status) or (class_type, status).
            class_type_str = row[-2]
            status = row[-1]
            t = normalize_class_type(class_type_str.value)
            if t not in counts:
                continue
            counts[t]['tot'] += 1
            if status == AttendanceStatus.ATTENDED:
                counts[t]['att'] += 1
            elif status == AttendanceStatus.MISSED:
                counts[t]['miss'] += 1
            else:
                counts[t]['pending'] += 1
        return counts

    async def get_subject_summaries(self, user_id: UUID, subjects, as_of_date: date) -> Dict[UUID, SubjectAttendanceSummary]:
        """
        Batched per-subject summaries for an enrolled subject list (dashboard
        N+1 fix). ONE grouped count query replaces N per-subject queries; every
        summary is built by the same `_build_subject_summary` path as
        `get_summary`, so results are byte-identical.
        """
        raw_counts = await self.repo.get_subject_counts_for_user(user_id, as_of_date)
        grouped: Dict[UUID, Dict[str, Any]] = {}
        for subject in subjects:
            grouped[subject.id] = {
                'L': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
                'T': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
                'P': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
            }
        for subject_id, class_type_str, status in raw_counts:
            if subject_id not in grouped:
                continue
            bucket = grouped[subject_id]
            t = normalize_class_type(class_type_str.value)
            if t not in bucket:
                continue
            bucket[t]['tot'] += 1
            if status == AttendanceStatus.ATTENDED:
                bucket[t]['att'] += 1
            elif status == AttendanceStatus.MISSED:
                bucket[t]['miss'] += 1
            else:
                bucket[t]['pending'] += 1
        mid_sems = await self.repo.get_mid_sem_sessions(list(grouped.keys()))
        return {
            s.id: _build_subject_summary(s.code, grouped[s.id], mid_sem=mid_sems.get(s.id))
            for s in subjects
        }

    async def record_attendance(self, user_id: UUID, class_session_id: UUID, status: AttendanceStatus) -> AttendanceRecord:
        session = await self.repo.get_session_by_id(class_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Class session not found")

        if session.is_cancelled:
            raise HTTPException(status_code=409, detail="Cannot mark attendance for a cancelled class session")

        enrolled = await self.repo.is_enrolled(user_id, session.subject_id)
        if not enrolled:
            raise HTTPException(status_code=403, detail="Not enrolled in this subject")
            
        record = await self.repo.get_attendance_for_session(user_id, class_session_id)
        if record:
            record.status = status
        else:
            record = AttendanceRecord(
                user_id=user_id,
                class_session_id=class_session_id,
                status=status
            )
            await self.repo.save_attendance(record)
            
        await self.db.commit()
        return record

    async def get_history(
        self,
        user: User,
        limit: int = 50,
        offset: int = 0,
        subject_code: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Session-based attendance history for the authenticated student,
        bounded by their real academic semester (semester_start -> today).
        Same canonical records Track consumes; no attendance rows created.
        """
        context = await UserRepository(self.db).get_academic_context(user)
        semester_start = context.get("semester_start")
        semester_end = context.get("semester_end")
        today = date.today()

        # Effective query range: clamped to the student's semester and today.
        if semester_start is not None:
            range_start = date_from if date_from is not None else semester_start
            if range_start < semester_start:
                range_start = semester_start
        else:
            range_start = date_from

        range_end = today
        if date_to is not None and date_to < range_end:
            range_end = date_to
        if semester_end is not None and semester_end < range_end:
            range_end = semester_end

        if search:
            search = search.strip()

        records, total_count = await self.repo.get_history(
            user_id=user.id,
            limit=limit,
            offset=offset,
            subject_code=subject_code,
            status=status,
            date_from=range_start,
            date_to=range_end,
            search=search or None,
        )

        items: List[Dict[str, Any]] = []
        for r in records:
            resolved_status = r["status"] if r["status"] else AttendanceStatus.PENDING
            items.append({
                "id": str(r["id"]),
                "date": r["date"],
                "start_time": r["start_time"].strftime("%I:%M %p") if r["start_time"] else None,
                "end_time": r["end_time"].strftime("%I:%M %p") if r["end_time"] else None,
                "subject_code": r["subject_code"],
                "subject_name": r["subject_name"],
                "class_type": r["class_type"],
                "status": resolved_status,
                "is_cancelled": r["is_cancelled"],
                "is_extra": r["is_extra"],
                "designation": r["designation"].value if r["designation"] else None,
                "marked_at": r["marked_at"],
            })

        # Summary over the FULL filtered result set (not the loaded page).
        # Cancelled sessions are their own state (never counted absent),
        # mirroring Track's daily counts.
        summary_counts = await self.repo.get_history_summary(
            user_id=user.id,
            subject_code=subject_code,
            status=status,
            date_from=range_start,
            date_to=range_end,
            search=search or None,
        )

        cancelled = summary_counts["cancelled"]
        attended = summary_counts["attended"]
        missed = summary_counts["missed"]
        pending = summary_counts["pending"]
        recorded = attended + missed
        pct = round(attended / recorded * 100, 1) if recorded > 0 else None

        return {
            "semester_start": semester_start,
            "semester_end": semester_end,
            "range_start": range_start,
            "range_end": range_end,
            "items": items,
            "total_count": total_count,
            "summary": {
                "total": attended + missed + pending,
                "attended": attended,
                "missed": missed,
                "pending": pending,
                "cancelled": cancelled,
                "pct": pct,
            },
        }

    async def get_daily_sessions(self, user_id: UUID, target_date: date) -> DailySessionsResponse:
        records = await self.repo.get_daily_sessions(user_id, target_date)
        
        sessions = []
        for r in records:
            # Format time if available
            start_time = r["start_time"].strftime("%I:%M %p") if r["start_time"] else None
            end_time = r["end_time"].strftime("%I:%M %p") if r["end_time"] else None
            
            # Resolve status (None becomes Pending)
            status = r["status"] if r["status"] else AttendanceStatus.PENDING
            
            sessions.append(DailySessionResponse(
                id=str(r["id"]),
                date=r["date"],
                start_time=start_time,
                end_time=end_time,
                subject_code=r["subject_code"],
                subject_name=r["subject_name"],
                class_type=r["class_type"],
                status=status,
                is_cancelled=r["is_cancelled"],
                is_extra=r["is_extra"],
                designation=r["designation"].value if r["designation"] else None,
            ))
            
        return DailySessionsResponse(date=target_date, sessions=sessions)
