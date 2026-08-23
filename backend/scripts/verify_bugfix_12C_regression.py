import asyncio
import sys
from pathlib import Path
from datetime import date
from sqlalchemy import select, insert, delete, update

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx
from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.api.dependencies.deps import get_db
from app.models.user import User
from app.models.academic import Subject
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.enums import AttendanceStatus, ClassType
from app.engines.attendance_engine import classify_attendance_status

results = []

def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))

async def main() -> int:
    async with AsyncSessionLocal() as db:
        admin_user = (await db.execute(select(User).where(User.role == "ADMIN"))).scalars().first()
        bcs058_id = (await db.execute(select(Subject.id).where(Subject.code == "BCS-058"))).scalars().first()
        
        # Override get_db to share the transaction
        async def override_get_db():
            yield db
            
        app.dependency_overrides[get_db] = override_get_db
        
        stmt = select(ClassSession).where(ClassSession.subject_id == bcs058_id, ClassSession.class_type == ClassType.LECTURE).order_by(ClassSession.date).limit(18)
        sessions = (await db.execute(stmt)).scalars().all()
        
        session_ids = [s.id for s in sessions]
        await db.execute(delete(AttendanceRecord).where(AttendanceRecord.class_session_id.in_(session_ids), AttendanceRecord.user_id == admin_user.id))
        
        for i, s in enumerate(sessions):
            if i < 2:
                s.is_cancelled = True
                status = AttendanceStatus.MISSED
            elif i < 8:
                s.is_cancelled = False
                status = AttendanceStatus.ATTENDED
            else:
                s.is_cancelled = False
                status = AttendanceStatus.MISSED
                
            db.add(AttendanceRecord(
                user_id=admin_user.id,
                class_session_id=s.id,
                status=status
            ))
        
        await db.flush()
        
        admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/v1/analytics/overview", headers=headers)
            ov = r.json()
            bcs058 = next(s for s in ov["subjects"] if s["subject_code"] == "BCS-058")
            
            check("1. BCS-058 Lecture total drops by exactly 2 cancelled (18 -> 16)", bcs058["lecture"]["total"] == 16, f"total={bcs058['lecture']['total']}")
            check("2. BCS-058 Lecture attended remains exactly 6 (cancelled MISSED records ignored)", bcs058["lecture"]["attended"] == 6, f"attended={bcs058['lecture']['attended']}")
            check("3. BCS-058 Lecture percentage is exactly 37.5%", bcs058["current_lecture_pct"] == 37.5, f"pct={bcs058['current_lecture_pct']}")
            
            # Now we reactivate them
            sessions[0].is_cancelled = False
            sessions[1].is_cancelled = False
            await db.flush()
            
            r2 = await client.get("/api/v1/analytics/overview", headers=headers)
            ov2 = r2.json()
            bcs058_reactivated = next(s for s in ov2["subjects"] if s["subject_code"] == "BCS-058")
            
            check("4. Reactivation restores Lecture total to 18", bcs058_reactivated["lecture"]["total"] == 18, f"total={bcs058_reactivated['lecture']['total']}")
            check("5. Reactivation processes the 2 MISSED records (attended remains 6, total is 18)", bcs058_reactivated["lecture"]["attended"] == 6, f"attended={bcs058_reactivated['lecture']['attended']}")
            check("6. Reactivated Lecture percentage is exactly 33.33%", round(bcs058_reactivated["current_lecture_pct"], 2) == 33.33, f"pct={bcs058_reactivated['current_lecture_pct']}")
            
        await db.rollback() # Never persist test data
        
    failures = sum(1 for _, ok in results if not ok)
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
