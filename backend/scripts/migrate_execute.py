import os
import sys
import json
import argparse
import asyncio
from datetime import datetime
from pathlib import Path

# Setup paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import AsyncSessionLocal
from app.models.academic import Subject
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.user import User
from app.models.enums import AttendanceStatus
from app.models.quiz import QuizSchedule, QuizCycle
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

def print_blocked_and_exit(reason):
    print(f"BLOCKED — {reason}")
    sys.exit(0)

try:
    import firebase_admin
    from firebase_admin import credentials, auth, firestore
except ImportError:
    print_blocked_and_exit("firebase-admin package not installed")

EXPECTED_COUNTS = {
    "auth_users": 29,
    "firestore_matching": 27,
    "attendance_total": 92,
    "attendance_resolved": 83,
    "attendance_ambiguous": 7,
    "attendance_missing": 2,
    "laboratory_total": 1,
    "laboratory_resolved": 0,
    "laboratory_unknown": 1
}

async def run_migration(execute_mode):
    print(f"Starting Migration. Mode: {'EXECUTE' if execute_mode else 'DRY RUN'}")
    
    # 1. Credential Check
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if not service_account_path:
        service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not service_account_path or not os.path.exists(service_account_path):
        print_blocked_and_exit("Firebase Admin credentials not configured")

    # Initialize Firebase
    cred = credentials.Certificate(service_account_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    report = {
        "timestamp": datetime.now().isoformat(),
        "mode": "EXECUTE" if execute_mode else "DRY RUN",
        "source_counts": {
            "auth_users": 0, "firestore_users": 0,
            "attendance_total": 0, "laboratory_total": 0
        },
        "resolved_counts": {
            "attendance_migratable": 0, "attendance_quarantined": 0,
            "laboratory_migratable": 0, "laboratory_quarantined": 0
        },
        "transactions": {
            "successful_users": 0, "failed_users": 0
        },
        "postgresql_writes": 0,
        "quarantine": {
            "attendance": [],
            "laboratory": [],
            "conflicts": []
        },
        "errors": []
    }

    print("Extracting Auth Users...")
    auth_users_map = {}
    auth_uid_map = {}
    try:
        page = auth.list_users()
        while page:
            for user in page.users:
                report["source_counts"]["auth_users"] += 1
                if user.disabled:
                    report["errors"].append(f"User {user.uid} is disabled")
                    continue
                email = user.email
                if not email or not email.endswith("@student.app"):
                    continue
                roll_number = email.split("@")[0].strip()
                if roll_number in auth_users_map:
                    report["quarantine"]["conflicts"].append(f"Duplicate roll number {roll_number} for UID {user.uid}")
                    continue
                auth_users_map[roll_number] = user.uid
                auth_uid_map[user.uid] = {
                    "uid": user.uid,
                    "roll_number": roll_number,
                    "email": email
                }
            page = page.get_next_page()
    except Exception as e:
        print_blocked_and_exit(f"Failed to extract Auth users: {e}")

    print("Extracting Firestore Documents...")
    firestore_users = {}
    try:
        docs = db.collection('students').stream()
        for doc in docs:
            firestore_users[doc.id] = doc.to_dict()
            report["source_counts"]["firestore_users"] += 1
    except Exception as e:
        print_blocked_and_exit(f"Failed to extract Firestore documents: {e}")

    # Validate Counts against Expectations
    if report["source_counts"]["auth_users"] != EXPECTED_COUNTS["auth_users"]:
        print_blocked_and_exit(f"Auth users count {report['source_counts']['auth_users']} != expected {EXPECTED_COUNTS['auth_users']}")
    
    print("Connecting to PostgreSQL Baseline...")
    async with AsyncSessionLocal() as session:
        # Check BCS-054 Invariant
        result = await session.execute(select(Subject).where(Subject.code == "BCS-054"))
        bcs_054_subject = result.scalars().first()
        if not bcs_054_subject:
            print_blocked_and_exit("Subject BCS-054 not found in baseline")
            
        result = await session.execute(
            select(QuizSchedule).join(QuizCycle)
            .where(QuizSchedule.subject_id == bcs_054_subject.id)
            .where(QuizCycle.cycle_number == 3)
        )
        q3 = result.scalars().first()
        if not q3 or q3.date is not None or q3.schedule_status.value != "UNRESOLVED":
            print_blocked_and_exit("CRITICAL BASELINE DISCREPANCY: BCS-054 Quiz III is not UNRESOLVED/NULL.")

        # Load lookup data
        result = await session.execute(select(Subject))
        subjects = {s.code: s for s in result.scalars().all()}
        
        result = await session.execute(select(ClassSession))
        class_sessions = result.scalars().all()
        session_map = {}
        for cs in class_sessions:
            key = (cs.date, cs.subject_id, cs.class_type.name)
            if key not in session_map:
                session_map[key] = []
            session_map[key].append(cs)

        # Pre-process legacy data to calculate exact counts
        migratable_attendance = [] # list of (uid, cs_id, status)
        
        for uid, f_data in firestore_users.items():
            if not isinstance(f_data, dict):
                continue
                
            attendance = f_data.get("attendance", {})
            for key, status in attendance.items():
                report["source_counts"]["attendance_total"] += 1
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
                    report["resolved_counts"]["attendance_quarantined"] += 1
                    report["quarantine"]["attendance"].append({
                        "uid": uid, "key": key, "classification": "MISSING_SESSION", "reason": "No ClassSession found"
                    })
                elif len(c_sessions) == 1:
                    if status in ["Attended", "Missed", "Pending"]:
                        report["resolved_counts"]["attendance_migratable"] += 1
                        migratable_attendance.append((uid, c_sessions[0].id, status))
                else:
                    report["resolved_counts"]["attendance_quarantined"] += 1
                    report["quarantine"]["attendance"].append({
                        "uid": uid, "key": key, "classification": "AMBIGUOUS",
                        "reason": f"Found {len(c_sessions)} candidate ClassSessions"
                    })
            
            laboratory = f_data.get("laboratory", {})
            for subj_code, experiments in laboratory.items():
                for exp in experiments:
                    report["source_counts"]["laboratory_total"] += 1
                    report["resolved_counts"]["laboratory_quarantined"] += 1
                    report["quarantine"]["laboratory"].append({
                        "uid": uid, "subject": subj_code, "classification": "UNKNOWN_EXPERIMENT", "reason": "Missing curriculum data"
                    })

        # Validate Pre-processed counts
        if report["resolved_counts"]["attendance_migratable"] != EXPECTED_COUNTS["attendance_resolved"]:
            print_blocked_and_exit(f"Attendance migratable count {report['resolved_counts']['attendance_migratable']} != expected {EXPECTED_COUNTS['attendance_resolved']}")

        if report["resolved_counts"]["attendance_quarantined"] != (EXPECTED_COUNTS["attendance_ambiguous"] + EXPECTED_COUNTS["attendance_missing"]):
            print_blocked_and_exit("Attendance quarantined count mismatch")

        print("Executing User Transactions...")
        
        # Group migratable attendance by uid
        user_attendance_map = {}
        for uid, cs_id, status in migratable_attendance:
            if uid not in user_attendance_map:
                user_attendance_map[uid] = []
            user_attendance_map[uid].append((cs_id, status))

        for uid, auth_info in auth_uid_map.items():
            f_data = firestore_users.get(uid, {})
            name = f_data.get("profile", {}).get("name", auth_info["roll_number"])
            
            # Start transaction for user
            async with session.begin_nested() as tx:
                try:
                    # 1. Upsert User
                    stmt_user = insert(User).values(
                        firebase_uid=uid,
                        roll_number=auth_info["roll_number"],
                        name=name
                    ).on_conflict_do_update(
                        index_elements=['firebase_uid'],
                        set_=dict(name=name, roll_number=auth_info["roll_number"])
                    ).returning(User.id)
                    
                    result_user = await session.execute(stmt_user)
                    user_pg_id = result_user.scalars().first()
                    
                    if execute_mode:
                        report["postgresql_writes"] += 1
                    
                    # 2. Upsert Attendance
                    records_to_insert = user_attendance_map.get(uid, [])
                    for cs_id, status_str in records_to_insert:
                        enum_status = AttendanceStatus.PENDING
                        if status_str == "Attended": enum_status = AttendanceStatus.ATTENDED
                        elif status_str == "Missed": enum_status = AttendanceStatus.MISSED
                        
                        stmt_att = insert(AttendanceRecord).values(
                            user_id=user_pg_id,
                            class_session_id=cs_id,
                            status=enum_status
                        ).on_conflict_do_update(
                            constraint='uq_user_class_session',
                            set_=dict(status=enum_status)
                        )
                        await session.execute(stmt_att)
                        if execute_mode:
                            report["postgresql_writes"] += 1
                            
                    report["transactions"]["successful_users"] += 1
                    
                except Exception as e:
                    await tx.rollback()
                    report["transactions"]["failed_users"] += 1
                    report["errors"].append(f"Failed to migrate user {uid}: {e}")

        # Post-migration check BCS-054 invariant
        result = await session.execute(
            select(QuizSchedule).join(QuizCycle)
            .where(QuizSchedule.subject_id == bcs_054_subject.id)
            .where(QuizCycle.cycle_number == 3)
        )
        q3_after = result.scalars().first()
        if not q3_after or q3_after.date is not None or q3_after.schedule_status.value != "UNRESOLVED":
            await session.rollback()
            print_blocked_and_exit("CRITICAL BASELINE DISCREPANCY: BCS-054 Quiz III invariant violated after migration loop. Rolling back everything.")

        if not execute_mode:
            print("DRY RUN mode: Rolling back all writes.")
            await session.rollback()
            report["postgresql_writes"] = 0
        else:
            print("EXECUTE mode: Committing all writes.")
            await session.commit()
            
    # Save Report
    REPORT_DIR = BACKEND_DIR / "migration_reports"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"migration_{ts}.json"
    md_path = REPORT_DIR / f"migration_{ts}.md"
    
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    
    with open(md_path, "w") as f:
        f.write(f"# Migration Execution Report\n\nGenerated: {report['timestamp']}\nMode: {report['mode']}\n\n")
        f.write(f"## Source Counts\n- Auth Users: {report['source_counts']['auth_users']}\n- Firestore Users: {report['source_counts']['firestore_users']}\n- Attendance Facts: {report['source_counts']['attendance_total']}\n- Laboratory Facts: {report['source_counts']['laboratory_total']}\n\n")
        f.write(f"## Target Pre-Validation\n- Attendance Migratable: {report['resolved_counts']['attendance_migratable']}\n- Attendance Quarantined: {report['resolved_counts']['attendance_quarantined']}\n- Laboratory Migratable: {report['resolved_counts']['laboratory_migratable']}\n- Laboratory Quarantined: {report['resolved_counts']['laboratory_quarantined']}\n\n")
        f.write(f"## Execution\n- Successful User Transactions: {report['transactions']['successful_users']}\n- Failed User Transactions: {report['transactions']['failed_users']}\n- PostgreSQL Writes: {report['postgresql_writes']}\n\n")
        f.write(f"## BCS-054 Invariant\n- Preserved: YES\n")

    print(f"Migration complete. Reports saved to {REPORT_DIR}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AttendanceDashPro Migration Execution")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Execute without committing writes")
    group.add_argument("--execute", action="store_true", help="Execute and COMMIT live writes")
    args = parser.parse_args()
    
    asyncio.run(run_migration(args.execute))
