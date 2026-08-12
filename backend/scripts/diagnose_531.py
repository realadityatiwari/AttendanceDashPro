import os
import sys
import asyncio
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import AsyncSessionLocal
from app.models.academic import Subject
from app.models.timetable import ClassSession, TimetableEntry
from sqlalchemy import select
from sqlalchemy.orm import selectinload

import firebase_admin
from firebase_admin import credentials, firestore

async def main():
    service_account_path = r"C:\Users\Lenovo\firebase-credentials\attendancedashpro-admin.json"
    cred = credentials.Certificate(service_account_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    print("Connecting to PostgreSQL Baseline (READ-ONLY)...")
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Subject))
        subjects = {s.code: s for s in result.scalars().all()}
        
        result = await session.execute(select(ClassSession).options(selectinload(ClassSession.timetable_entry)))
        class_sessions = result.scalars().all()
        session_map = {}
        for cs in class_sessions:
            key = (cs.date, cs.subject_id, cs.class_type.name)
            if key not in session_map:
                session_map[key] = []
            session_map[key].append(cs)
            
        print("Extracting Firestore Attendance...")
        docs = db.collection('students').stream()
        
        ambiguous_records = []
        missing_records = []
        resolved_count = 0
        
        for doc in docs:
            f_data = doc.to_dict()
            uid = doc.id
            attendance = f_data.get("attendance", {})
            for key, status in attendance.items():
                try:
                    date_str, subj_code, type_str = key.split(":")
                except ValueError:
                    continue
                
                c_type = "LECTURE"
                if type_str.startswith("T"): c_type = "TUTORIAL"
                if type_str.startswith("P"): c_type = "PRACTICAL"

                subject = subjects.get(subj_code)
                if not subject:
                    continue
                
                date_val = datetime.strptime(date_str, "%Y-%m-%d").date()
                c_sessions = session_map.get((date_val, subject.id, c_type), [])
                
                if len(c_sessions) == 0:
                    missing_records.append({
                        "uid": uid,
                        "key": key,
                        "date": date_val,
                        "subject": subj_code,
                        "type": c_type
                    })
                elif len(c_sessions) == 1:
                    resolved_count += 1
                else:
                    ambiguous_records.append({
                        "uid": uid,
                        "key": key,
                        "date": date_val,
                        "subject": subj_code,
                        "type": c_type,
                        "sessions": c_sessions
                    })
        
        print(f"\n--- RESOLVED RECORDS ---")
        print(f"Total resolved: {resolved_count}")
        
        print(f"\n--- AMBIGUOUS RECORDS ({len(ambiguous_records)}) ---")
        for rec in ambiguous_records:
            print(f"UID: {rec['uid'][:5]}... | Key: {rec['key']}")
            print(f"  Matches: {len(rec['sessions'])}")
            for cs in rec['sessions']:
                t_str = f"{cs.timetable_entry.start_time} - {cs.timetable_entry.end_time}" if cs.timetable_entry else "N/A"
                print(f"  - CS ID: {cs.id} | TE ID: {cs.timetable_entry_id} | Times: {t_str}")
        
        print(f"\n--- MISSING RECORDS ({len(missing_records)}) ---")
        # Fetch Timetable entries for the subjects on those days
        stmt_te = select(TimetableEntry)
        all_tes = (await session.execute(stmt_te)).scalars().all()
        
        from app.models.event import AcademicEvent
        events = (await session.execute(select(AcademicEvent))).scalars().all()
        from app.engines.calendar_engine import get_academic_day
        
        for rec in missing_records:
            print(f"UID: {rec['uid'][:5]}... | Key: {rec['key']}")
            
            # Check weekday
            dow = rec['date'].weekday()
            subject = subjects.get(rec['subject'])
            
            matching_te = [te for te in all_tes if te.subject_id == subject.id and te.day_of_week == dow]
            print(f"  - Target weekday ({dow}): TE matches = {len(matching_te)}")
            
            # Check calendar engine
            day_info = get_academic_day(rec['date'], events, [0, 6])
            print(f"  - Is Teaching Day: {day_info.is_teaching_day}")
            if not day_info.is_teaching_day:
                print(f"  - Reason: Not a teaching day (Holiday/Weekend)")
            if day_info.substitution_schedule_override:
                print(f"  - Substitution: {day_info.substitution_schedule_override}")

if __name__ == "__main__":
    asyncio.run(main())
