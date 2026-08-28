"""
Phase 23.10 — Student-Facing Read Model verifier (effective occurrence state +
student isolation).

Proves the canonical student-facing schedule read layer:

  * A shared Departmental Elective occurrence resolves to EACH student's own
    concrete subject (Student A DE-II=BCS-058, Student B DE-II=BCS-055) — the
    read model never exposes the logical slot as the concrete subject and never
    leaks one student's subject into another's rows.
  * The effective occurrence state is exposed on the read model:
    - outcome_type (MODIFIED / SURPRISE_QUIZ / EXTRA_* / CANCELLED / None);
    - elective_slot (the shared slot marker).
  * Subject-specific CANCELLED affects ONLY the intended concrete subject
    (BCS-058 -> A blocked, B unaffected).
  * Subject-specific MODIFIED affects ONLY the intended concrete subject
    (BCS-058 -> A sees MODIFIED, B sees normal/anchor).
  * Common subjects and practicals are identical for both students and never
    treated as electives.
  * Historical attendance is never created/altered by the read model.

State changes are this script's own artifacts (two temp fixture students, one
temp CLASS_CANCELLED event + one temp CLASS_MODIFIED event, the outcome rows
they imply, and any temp attendance records) and are removed in the finally
block by exact captured ids. No pre-existing row is ever modified.

Requires the local dev DB (admin 2401220100027; academic baseline present).
Usage (local only):
    $env:DATABASE_URI = "postgresql+asyncpg://postgres:postgres@127.0.0.1:55432/attendancedash"
    python scripts/verify_phase_23_10.py
"""
import asyncio
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession, TimetableEntry
from app.models.attendance import AttendanceRecord
from app.models.academic import Subject, StudentEnrollment, StudentElectiveChoice
from app.models.occurrence import OccurrenceOutcome
from app.models.enums import EventType, ClassType, ElectiveSlot, OccurrenceOutcomeType
from app.services.attendance_service import AttendanceService
from sqlalchemy import select, func, delete

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def make_student(db, admin: User, suffix: str, ei: str, eii: str) -> User:
    user = User(
        roll_number=f"2401229{uuid.uuid4().hex[:5]}",
        name=f"Temp 23.10 Student {suffix}",
        hashed_password="pbkdf2_sha256$unused",
        section_id=admin.section_id,
    )
    db.add(user)
    return user


async def enroll_and_choose(db, user: User, subjects_by_code, ei: str, eii: str) -> None:
    for subject in subjects_by_code.values():
        db.add(StudentEnrollment(user_id=user.id, subject_id=subject.id))
    db.add(StudentElectiveChoice(
        user_id=user.id, elective_slot=ElectiveSlot.ELECTIVE_I,
        subject_id=subjects_by_code[ei].id,
    ))
    db.add(StudentElectiveChoice(
        user_id=user.id, elective_slot=ElectiveSlot.ELECTIVE_II,
        subject_id=subjects_by_code[eii].id,
    ))


async def main() -> int:
    print("=" * 60)
    print("Phase 23.10 — Student-Facing Read Model (isolation + effective state)")
    print("=" * 60)

    student_a_id = student_b_id = None
    anchor_session_id: uuid.UUID | None = None
    event_cancel_id: uuid.UUID | None = None
    event_modified_id: uuid.UUID | None = None
    temp_outcome_ids: list = []
    temp_record_ids: list = []

    try:
        async with AsyncSessionLocal() as db:
            admin = (await db.execute(
                select(User).where(User.roll_number == "2401220100027")
            )).scalars().first()
            if admin is None:
                check("0. admin user found", False, "seed missing")
                return 1
            subjects = (await db.execute(select(Subject))).scalars().all()
            by_code = {s.code: s for s in subjects}
            for code in ("BCS-052", "BCS-053", "BCS-054", "BCS-055", "BCS-056",
                         "BCS-058", "BCS-501", "BCS-551"):
                check(f"0. subject {code} present", code in by_code)

            records_before = (await db.execute(
                select(func.count()).select_from(AttendanceRecord)
            )).scalar()

            student_a = make_student(db, admin, "A", "BCS-054", "BCS-058")
            student_b = make_student(db, admin, "B", "BCS-052", "BCS-055")
            await db.flush()
            student_a_id = student_a.id
            student_b_id = student_b.id
            await enroll_and_choose(db, student_a, by_code, "BCS-054", "BCS-058")
            await enroll_and_choose(db, student_b, by_code, "BCS-052", "BCS-055")
            await db.commit()

            # Pick a past working date with a DE-II timetable session.
            chosen = None
            de2_entries = (await db.execute(
                select(TimetableEntry).where(TimetableEntry.elective_slot == ElectiveSlot.ELECTIVE_II)
            )).scalars().all()
            for offset in range(10, 40):
                d = date.today() - timedelta(days=offset)
                if d.weekday() >= 5:
                    continue
                if any(e.day_of_week == d.weekday() for e in de2_entries):
                    sessions = (await db.execute(
                        select(ClassSession).where(
                            ClassSession.date == d,
                            ClassSession.timetable_entry_id.in_([e.id for e in de2_entries]),
                        )
                    )).scalars().all()
                    if sessions:
                        chosen = (d, sessions[0])
                        break
            if chosen is None:
                check("0. past DE-II session found", False, "no candidate")
                return 1
            target_date, anchor_session = chosen
            anchor_session_id = anchor_session.id
            check(f"0. DE-II anchor session on {target_date} found", True)

            svc = AttendanceService(db)

            # ── 1. Shared occurrence resolves per student (concrete subject) ──
            print("\n=== 1. Shared elective occurrence resolves per student ===")
            day_a = await svc.get_daily_sessions(student_a.id, target_date)
            day_b = await svc.get_daily_sessions(student_b.id, target_date)
            s_a = next((s for s in day_a.sessions if s.id == str(anchor_session.id)), None)
            s_b = next((s for s in day_b.sessions if s.id == str(anchor_session.id)), None)
            check(
                s_a is not None and s_a.subject_code == "BCS-058",
                "Student A (DE-II=BCS-058) sees BCS-058 for the shared occurrence",
                f"got {s_a.subject_code if s_a else None}",
            )
            check(
                s_b is not None and s_b.subject_code == "BCS-055",
                "Student B (DE-II=BCS-055) sees BCS-055 for the shared occurrence",
                f"got {s_b.subject_code if s_b else None}",
            )
            check(
                s_a is not None and s_a.elective_slot == ElectiveSlot.ELECTIVE_II,
                "elective_slot marker exposed on the read model (DE-II)",
            )
            check(
                s_a is not None and s_a.outcome_type is None,
                "no outcome -> outcome_type None (normal anchor)",
            )
            check(
                "BCS-058" not in {s.subject_code for s in day_b.sessions},
                "A's concrete subject never appears in B's rows",
            )
            check(
                "BCS-055" not in {s.subject_code for s in day_a.sessions},
                "B's concrete subject never appears in A's rows",
            )
            # Common + practical subjects identical for both.
            common_a = {s.subject_code for s in day_a.sessions if s.elective_slot is None}
            common_b = {s.subject_code for s in day_b.sessions if s.elective_slot is None}
            check(
                "BCS-501" in common_a and "BCS-501" in common_b,
                "common subject (BCS-501) appears identically for both",
            )
            practical_a = {s.subject_code for s in day_a.sessions if s.class_type == ClassType.PRACTICAL}
            practical_b = {s.subject_code for s in day_b.sessions if s.class_type == ClassType.PRACTICAL}
            check(
                practical_a == practical_b,
                "practical sessions identical for both students (never elective)",
            )

            # ── 2. Subject-specific CANCELLED affects only BCS-058 ──────────
            print("\n=== 2. Subject-specific CANCELLED (BCS-058 only) ===")
            from app.services.event_session_service import EventSessionSynchronizer
            sync = EventSessionSynchronizer(db)
            cancel_event = AcademicEvent(
                event_type=EventType.CLASS_CANCELLED,
                start_date=target_date, end_date=target_date,
                subject_id=by_code["BCS-058"].id, elective_slot=None,
                class_type=ClassType.LECTURE, is_working_day=True,
                note="verify_phase_23_10 fixture", active=True,
            )
            db.add(cancel_event)
            await db.flush()
            event_cancel_id = cancel_event.id
            await sync.sync_event(cancel_event)
            await db.commit()
            outcome = (await db.execute(
                select(OccurrenceOutcome).where(
                    OccurrenceOutcome.class_session_id == anchor_session.id,
                    OccurrenceOutcome.subject_id == by_code["BCS-058"].id,
                )
            )).scalars().first()
            if outcome is not None:
                temp_outcome_ids.append(outcome.id)
            check(
                outcome is not None and outcome.outcome_type == OccurrenceOutcomeType.CANCELLED,
                "BCS-058 has a CANCELLED outcome",
            )
            day_a = await svc.get_daily_sessions(student_a.id, target_date)
            day_b = await svc.get_daily_sessions(student_b.id, target_date)
            s_a = next((s for s in day_a.sessions if s.id == str(anchor_session.id)), None)
            s_b = next((s for s in day_b.sessions if s.id == str(anchor_session.id)), None)
            check(
                s_a is not None and s_a.outcome_type == OccurrenceOutcomeType.CANCELLED and s_a.is_cancelled is True,
                "read model: Student A sees CANCELLED (outcome_type + is_cancelled)",
            )
            check(
                s_b is not None and s_b.outcome_type is None and s_b.is_cancelled is False,
                "read model: Student B unaffected (anchor)",
            )

            # ── 3. Revert cancellation, then subject-specific MODIFIED ───────
            print("\n=== 3. Subject-specific MODIFIED (BCS-058 only) ===")
            cancel_event.active = False
            await sync.sync_event(cancel_event)
            await db.commit()
            modified_event = AcademicEvent(
                event_type=EventType.CLASS_MODIFIED,
                start_date=target_date, end_date=target_date,
                subject_id=by_code["BCS-058"].id, elective_slot=None,
                class_type=ClassType.LECTURE, is_working_day=True,
                note="verify_phase_23_10 fixture", active=True,
            )
            db.add(modified_event)
            await db.flush()
            event_modified_id = modified_event.id
            await sync.sync_event(modified_event)
            await db.commit()
            outcome = (await db.execute(
                select(OccurrenceOutcome).where(
                    OccurrenceOutcome.class_session_id == anchor_session.id,
                    OccurrenceOutcome.subject_id == by_code["BCS-058"].id,
                )
            )).scalars().first()
            if outcome is not None:
                temp_outcome_ids.append(outcome.id)
            check(
                outcome is not None and outcome.outcome_type == OccurrenceOutcomeType.MODIFIED,
                "BCS-058 has a MODIFIED outcome after reversal + CLASS_MODIFIED",
            )
            day_a = await svc.get_daily_sessions(student_a.id, target_date)
            day_b = await svc.get_daily_sessions(student_b.id, target_date)
            s_a = next((s for s in day_a.sessions if s.id == str(anchor_session.id)), None)
            s_b = next((s for s in day_b.sessions if s.id == str(anchor_session.id)), None)
            check(
                s_a is not None and s_a.outcome_type == OccurrenceOutcomeType.MODIFIED
                and s_a.is_cancelled is False and s_a.is_extra is False,
                "read model: Student A sees MODIFIED (not cancelled/extra — still conducted)",
            )
            check(
                s_b is not None and s_b.outcome_type is None,
                "read model: Student B unaffected by BCS-058's MODIFIED",
            )

            # ── 4. History read model exposes effective state ───────────────
            print("\n=== 4. History read model exposes effective state ===")
            hist_a = await svc.get_history(student_a, limit=200)
            h_a = next((h for h in hist_a["items"] if h["id"] == str(anchor_session.id)), None)
            check(
                h_a is not None and h_a.get("outcome_type") == OccurrenceOutcomeType.MODIFIED,
                "history item exposes outcome_type=MODIFIED for A",
                f"got {h_a.get('outcome_type') if h_a else None}",
            )
            hist_b = await svc.get_history(student_b, limit=200)
            h_b = next((h for h in hist_b["items"] if h["id"] == str(anchor_session.id)), None)
            check(
                h_b is not None and h_b.get("outcome_type") is None,
                "history item for B has no outcome_type (unaffected)",
            )

            # ── 5. Historical attendance untouched ──────────────────────────
            print("\n=== 5. Historical attendance safety ===")
            check(
                (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
                == records_before,
                "no attendance records created/altered by the read-model layer",
            )
    finally:
        async with AsyncSessionLocal() as db:
            for eid in (event_cancel_id, event_modified_id):
                if eid is not None:
                    await db.execute(delete(AcademicEvent).where(AcademicEvent.id == eid))
            for oid in temp_outcome_ids:
                if oid is not None:
                    await db.execute(delete(OccurrenceOutcome).where(OccurrenceOutcome.id == oid))
            for rid in temp_record_ids:
                if rid is not None:
                    await db.execute(delete(AttendanceRecord).where(AttendanceRecord.id == rid))
            for uid in (student_a_id, student_b_id):
                if uid is not None:
                    await db.execute(delete(StudentElectiveChoice).where(StudentElectiveChoice.user_id == uid))
                    await db.execute(delete(StudentEnrollment).where(StudentEnrollment.user_id == uid))
                    await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        print("\nCleanup: fixture events, outcomes, students removed.")

    failed = [name for name, ok in results if not ok]
    print("=" * 60)
    print(f"Phase 23.10 verifier: {len(results) - len(failed)}/{len(results)} PASS")
    if failed:
        print("FAILED:", failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
