from datetime import date
from uuid import UUID
from typing import Optional, Dict, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.attendance_repo import AttendanceRepository
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

    async def get_history(self, user_id: UUID, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        records, total = await self.repo.get_history(user_id, limit, offset)
        
        # Convert raw records dicts to AttendanceHistoryItem compatible
        items = []
        for r in records:
            items.append({
                "id": str(r["id"]),
                "date": r["date"],
                "subject_code": r["subject_code"],
                "class_type": r["class_type"],
                "status": r["status"],
                "marked_at": r["marked_at"]
            })
            
        return {
            "items": items,
            "total_count": total
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
