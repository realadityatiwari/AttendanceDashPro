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
from app.engines.attendance_engine import compute_subject_stats, normalize_class_type
from app.schemas.attendance import SubjectAttendanceSummary, DailySessionsResponse, DailySessionResponse

class AttendanceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AttendanceRepository(db)
        
    async def get_summary(self, user_id: UUID, subject_id: UUID, subject_code: str, as_of_date: date) -> SubjectAttendanceSummary:
        raw_counts = await self.repo.get_subject_counts_up_to_date(user_id, subject_id, as_of_date)
        
        counts: Dict[str, Any] = {
            'L': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
            'T': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
            'P': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
        }
        
        for class_type_str, status in raw_counts:
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
                
        attendance_data = {'counts': counts}
        return compute_subject_stats(subject_code, attendance_data)

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
                is_extra=r["is_extra"]
            ))
            
        return DailySessionsResponse(date=target_date, sessions=sessions)
