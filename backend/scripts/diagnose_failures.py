import os
import sys
import asyncio
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import AsyncSessionLocal
from app.models.timetable import ClassSession
from app.models.academic import Subject
from app.models.laboratory import LaboratoryExperiment
from sqlalchemy import select

import firebase_admin
from firebase_admin import credentials, auth, firestore

def main():
    service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    cred = credentials.Certificate(service_account_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    print("--- 1. INVESTIGATE 92 ATTENDANCE FAILURES ---")
    docs = db.collection('students').stream()
    
    unique_dates = set()
    unique_subjects = set()
    unique_class_types = set()
    subject_counts = {}
    date_counts = {}
    type_counts = {}
    
    all_attendance_keys = set()
    
    # Laboratory
    lab_records = []

    # Firestore users
    firestore_uids = set()

    for doc in docs:
        firestore_uids.add(doc.id)
        data = doc.to_dict()
        attendance = data.get("attendance", {})
        for key in attendance.keys():
            all_attendance_keys.add(key)
            try:
                date_str, subj, typ = key.split(":")
                unique_dates.add(date_str)
                unique_subjects.add(subj)
                unique_class_types.add(typ)
                
                subject_counts[subj] = subject_counts.get(subj, 0) + 1
                date_counts[date_str] = date_counts.get(date_str, 0) + 1
                type_counts[typ] = type_counts.get(typ, 0) + 1
            except Exception:
                pass
                
        laboratory = data.get("laboratory", {})
        for subj, exps in laboratory.items():
            for exp in exps:
                lab_records.append((subj, exp))

    print(f"Unique dates: {len(unique_dates)}")
    print(f"Unique subjects: {list(unique_subjects)}")
    print(f"Unique class types: {list(unique_class_types)}")
    print(f"Count by subject: {subject_counts}")
    print(f"Count by date (first 5): {list(date_counts.items())[:5]}")
    print(f"Count by class type: {type_counts}")

    print("\n--- 2. INVESTIGATE THE LABORATORY FAILURE ---")
    print(f"Legacy lab records: {lab_records}")
    
    print("\n--- 3. INVESTIGATE MISSING FIRESTORE DOCUMENTS ---")
    page = auth.list_users()
    for user in page.users:
        if user.uid not in firestore_uids:
            roll = user.email.split('@')[0] if user.email else "UNKNOWN"
            print(f"Missing UID: {user.uid}, Roll: {roll}, Disabled: {user.disabled}")

    print("\n--- BASELINE POSTGRESQL DIAGNOSTICS ---")
    async def check_pg():
        async with AsyncSessionLocal() as session:
            # Check ClassSessions
            result = await session.execute(select(ClassSession, Subject).join(Subject))
            sessions = result.all()
            print(f"Total ClassSessions in PostgreSQL: {len(sessions)}")
            if len(sessions) > 0:
                print("Sample ClassSessions:")
                for cs, subj in sessions[:5]:
                    print(f"  {cs.date} | {subj.code} | {cs.class_type.name}")
            else:
                print("  No ClassSessions found. The baseline likely only contains recurring timetable structures, not historical occurrences.")

            # Check LaboratoryExperiments
            result = await session.execute(select(LaboratoryExperiment, Subject).join(Subject))
            exps = result.all()
            print(f"Total LaboratoryExperiments in PostgreSQL: {len(exps)}")
            if exps:
                print("Sample LaboratoryExperiments:")
                for exp, subj in exps[:5]:
                    print(f"  {subj.code} | Exp No: {exp.experiment_number} | {exp.title}")

    asyncio.run(check_pg())

if __name__ == "__main__":
    main()
