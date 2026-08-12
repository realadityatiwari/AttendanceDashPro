import os
import sys
import json
import asyncio
from datetime import datetime
from pathlib import Path

# Setup paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
from app.db.session import AsyncSessionLocal
from app.models.academic import Subject, AcademicSession, Semester, StudentEnrollment
from app.models.timetable import TimetableEntry, ClassSession
from app.models.attendance import AttendanceRecord
from app.models.laboratory import LaboratoryExperiment, LaboratoryRecord
from app.models.user import User
from app.models.quiz import QuizSchedule, QuizCycle, ScheduleStatus
from sqlalchemy import select

def print_blocked_and_exit(reason):
    print(f"BLOCKED — {reason}")
    sys.exit(0)

try:
    import firebase_admin
    from firebase_admin import credentials, auth, firestore
except ImportError:
    print_blocked_and_exit("firebase-admin package not installed")

# 1. Credential Check
service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
if not service_account_path:
    service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

if not service_account_path or not os.path.exists(service_account_path):
    print_blocked_and_exit("Firebase Admin credentials not configured")

# We have credentials, initialize Firebase (READ-ONLY)
print("Initializing Firebase Admin SDK (READ-ONLY)...")
cred = credentials.Certificate(service_account_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

REPORT_DIR = BACKEND_DIR / "migration_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

async def run_extraction():
    print("Starting READ-ONLY extraction...")
    report = {
        "timestamp": datetime.now().isoformat(),
        "auth_users": {
            "total": 0, "resolved": 0, "malformed": 0, "duplicate_roll_numbers": 0, "disabled": 0
        },
        "firestore": {
            "matching_documents": 0, "missing_documents": 0, "orphan_documents": 0, "malformed_documents": 0
        },
        "attendance": {
            "total_source_records": 0, "resolved": 0, "ambiguous": 0, 
            "missing_class_sessions": 0, "unknown_subjects": 0, "unknown_statuses": 0
        },
        "laboratory": {
            "total_source_records": 0, "resolved": 0, "unknown_subjects": 0, 
            "unknown_experiments": 0, "ambiguous_records": 0
        },
        "events": {
            "total_legacy_events": 0, "classified_as_student_created": 0, "requires_product_decision": 0
        },
        "users": {
            "resolved": 0, "conflicts": 0, "missing_profiles": 0
        },
        "bcs_054": {
            "quiz_iii_date": "UNKNOWN", "quiz_iii_status": "UNKNOWN"
        }
    }

    # 2. Extract Auth Users
    print("Extracting Auth Users...")
    auth_users_map = {} # roll_number -> uid
    auth_uid_map = {} # uid -> user_data
    try:
        page = auth.list_users()
        while page:
            for user in page.users:
                report["auth_users"]["total"] += 1
                if user.disabled:
                    report["auth_users"]["disabled"] += 1
                
                email = user.email
                if not email or not email.endswith("@student.app"):
                    report["auth_users"]["malformed"] += 1
                    continue
                
                roll_number = email.split("@")[0].strip()
                if roll_number in auth_users_map:
                    report["auth_users"]["duplicate_roll_numbers"] += 1
                    continue
                
                auth_users_map[roll_number] = user.uid
                auth_uid_map[user.uid] = {
                    "uid": user.uid,
                    "roll_number": roll_number,
                    "email": email,
                    "disabled": user.disabled
                }
                report["auth_users"]["resolved"] += 1
            page = page.get_next_page()
    except Exception as e:
        print_blocked_and_exit(f"Failed to extract Auth users: {e}")

    # 3. Extract Firestore Students
    print("Extracting Firestore Documents...")
    firestore_users = {}
    try:
        docs = db.collection('students').stream()
        for doc in docs:
            firestore_users[doc.id] = doc.to_dict()
    except Exception as e:
        print_blocked_and_exit(f"Failed to extract Firestore documents: {e}")

    # Identity Reconciliation
    for uid, f_data in firestore_users.items():
        if uid in auth_uid_map:
            report["firestore"]["matching_documents"] += 1
        else:
            report["firestore"]["orphan_documents"] += 1
    
    for uid in auth_uid_map:
        if uid not in firestore_users:
            report["firestore"]["missing_documents"] += 1
            report["users"]["missing_profiles"] += 1

    # Open a Read-Only Postgres Session
    print("Connecting to PostgreSQL Baseline (READ-ONLY)...")
    async with AsyncSessionLocal() as session:
        # Load Baseline Data
        result = await session.execute(select(Subject))
        subjects = {s.code: s for s in result.scalars().all()}
        
        result = await session.execute(select(ClassSession))
        class_sessions = result.scalars().all()
        # Group class sessions by (date, subject_id, type)
        session_map = {}
        for cs in class_sessions:
            key = (cs.date, cs.subject_id, cs.class_type.name)
            if key not in session_map:
                session_map[key] = []
            session_map[key].append(cs)

        result = await session.execute(select(LaboratoryExperiment))
        lab_experiments = result.scalars().all()
        lab_exp_map = {} # (subject_id, experiment_number) -> experiment
        for exp in lab_experiments:
            key = (exp.subject_id, exp.experiment_number)
            lab_exp_map[key] = exp

        # 4. Check BCS-054 Invariant
        bcs_054_subject = subjects.get("BCS-054")
        if bcs_054_subject:
            result = await session.execute(
                select(QuizSchedule)
                .join(QuizCycle)
                .where(QuizSchedule.subject_id == bcs_054_subject.id)
                .where(QuizCycle.cycle_number == 3)
            )
            q3 = result.scalars().first()
            if q3:
                report["bcs_054"]["quiz_iii_date"] = str(q3.date) if q3.date else "NULL"
                report["bcs_054"]["quiz_iii_status"] = q3.schedule_status.value
                
                if q3.date is not None or q3.schedule_status.value != "unresolved":
                    print("CRITICAL BASELINE DISCREPANCY: BCS-054 Quiz III is not UNRESOLVED/NULL.")
                    sys.exit(1)
            else:
                print("CRITICAL BASELINE DISCREPANCY: BCS-054 Quiz III schedule not found.")
                sys.exit(1)

        # 5. Attendance & Laboratory Resolution
        for uid, f_data in firestore_users.items():
            if not isinstance(f_data, dict):
                report["firestore"]["malformed_documents"] += 1
                continue
            
            # Events
            academic_events = f_data.get("academicEvents", {})
            for date_str, events in academic_events.items():
                if isinstance(events, list):
                    report["events"]["total_legacy_events"] += len(events)
                    report["events"]["classified_as_student_created"] += len(events)
                    report["events"]["requires_product_decision"] += len(events)
            
            # Attendance
            attendance = f_data.get("attendance", {})
            for key, status in attendance.items():
                report["attendance"]["total_source_records"] += 1
                try:
                    date_str, subj_code, type_str = key.split(":")
                except ValueError:
                    report["attendance"]["unknown_subjects"] += 1
                    continue
                
                # Normalize type_str
                c_type = "LECTURE"
                if type_str.startswith("T"): c_type = "TUTORIAL"
                if type_str.startswith("P"): c_type = "PRACTICAL"

                subject = subjects.get(subj_code)
                if not subject:
                    report["attendance"]["unknown_subjects"] += 1
                    continue
                
                date_val = datetime.strptime(date_str, "%Y-%m-%d").date()
                c_sessions = session_map.get((date_val, subject.id, c_type), [])
                
                if len(c_sessions) == 0:
                    report["attendance"]["missing_class_sessions"] += 1
                elif len(c_sessions) == 1:
                    if status not in ["Attended", "Missed", "Pending"]:
                        report["attendance"]["unknown_statuses"] += 1
                    else:
                        report["attendance"]["resolved"] += 1
                else:
                    report["attendance"]["ambiguous"] += 1
            
            # Laboratory
            laboratory = f_data.get("laboratory", {})
            for subj_code, experiments in laboratory.items():
                for exp in experiments:
                    report["laboratory"]["total_source_records"] += 1
                    subject = subjects.get(subj_code)
                    if not subject:
                        report["laboratory"]["unknown_subjects"] += 1
                        continue
                    
                    exp_num = exp.get("experimentNumber")
                    if not exp_num:
                        report["laboratory"]["unknown_experiments"] += 1
                        continue
                        
                    exp_db = lab_exp_map.get((subject.id, int(exp_num)))
                    if not exp_db:
                        report["laboratory"]["unknown_experiments"] += 1
                    else:
                        report["laboratory"]["resolved"] += 1
    
    # Save Report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"reconciliation_{ts}.json"
    md_path = REPORT_DIR / f"reconciliation_{ts}.md"
    
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    
    with open(md_path, "w") as f:
        f.write(f"# Migration Reconciliation Report\n\nGenerated: {report['timestamp']}\n\n")
        f.write(f"## Auth Users\n- Total: {report['auth_users']['total']}\n- Resolved: {report['auth_users']['resolved']}\n- Malformed: {report['auth_users']['malformed']}\n")
        f.write(f"## Firestore\n- Matching: {report['firestore']['matching_documents']}\n- Missing Auth: {report['firestore']['missing_documents']}\n- Orphan Firestore: {report['firestore']['orphan_documents']}\n")
        f.write(f"## Attendance\n- Total: {report['attendance']['total_source_records']}\n- Resolved: {report['attendance']['resolved']}\n- Ambiguous: {report['attendance']['ambiguous']}\n- Missing Sessions: {report['attendance']['missing_class_sessions']}\n")
        f.write(f"## Laboratory\n- Total: {report['laboratory']['total_source_records']}\n- Resolved: {report['laboratory']['resolved']}\n- Unknown Experiments: {report['laboratory']['unknown_experiments']}\n")
        f.write(f"## BCS-054\n- Quiz III Date: {report['bcs_054']['quiz_iii_date']}\n- Quiz III Status: {report['bcs_054']['quiz_iii_status']}\n")

    print(f"Reconciliation complete. Reports saved to {REPORT_DIR}")

if __name__ == "__main__":
    asyncio.run(run_extraction())
