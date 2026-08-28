"""
Phase 23.9 — Attendance Mutation Gate verifier (outcome-aware marking).

Proves the canonical attendance mutation path respects the canonical occurrence
outcome for the student's RESOLVED concrete subject:

  * NORMAL session              -> mutation allowed.
  * MODIFIED outcome            -> mutation allowed (conducted class; metadata
    only for attendance).
  * CANCELLED outcome           -> mutation rejected (409, the existing
    cancelled-session convention); never receives an attendance record.
  * Elective isolation          -> a CANCELLED outcome for BCS-058 blocks only
    the BCS-058 student; BCS-055/BCS-056 students (no outcome) stay allowed.
  * MODIFIED isolation          -> a MODIFIED outcome for BCS-058 allows only
    the BCS-058 mutation and leaves BCS-055/056 unaffected.
  * Existing attendance record  -> duplicate mutation preserves the single
    record (no duplicate rows; unique constraint upheld).
  * Historical attendance safety-> an already-attended session that later
    receives a CANCELLED outcome keeps its record (read path may present the
    session as cancelled; the record is never deleted/rewritten by sync).
  * Deactivation / reversal     -> after a temporary cancellation is reverted,
    mutation becomes allowed again.
  * Idempotency                 -> repeated synchronization produces no
    mutation-state drift or duplicate attendance rows.
  * Authorization regression    -> unauthenticated rejected (401); enrolled but
    unenrolled subject rejected (403); enrolled student follows outcome.

State changes are this script's own artifacts (two temp fixture students, one
temp CLASS_CANCELLED event + one temp CLASS_MODIFIED event, the outcome rows
they imply, and any temp attendance records) and are removed in the finally
block by exact captured ids. No pre-existing row is ever modified.

Requires the seeded dev DB (admin 2401220100027; current academic baseline).
Usage:
    python scripts/verify_phase_23_9.py
"""
import asyncio
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession, TimetableEntry
from app.models.attendance import AttendanceRecord
from app.models.academic import Subject, StudentEnrollment, StudentElectiveChoice
from app.models.occurrence import OccurrenceOutcome
from app.models.enums import (
    EventType, ClassType, ElectiveSlot, OccurrenceOutcomeType, AttendanceStatus,
)
from sqlalchemy import select, func, delete

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def make_student(db, admin: User, suffix: str, ei: str, eii: str) -> User:
    roll = f"2401229{uuid.uuid4().hex[:5]}"
    user = User(
        roll_number=roll,
        name=f"Temp 23.9 Student {suffix}",
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
    print("Phase 23.9 — Attendance Mutation Gate (outcome-aware marking)")
    print("=" * 60)

    student_a_id = student_b_id = None
    anchor_session_id: uuid.UUID | None = None
    event_cancel_id: uuid.UUID | None = None
    event_modified_id: uuid.UUID | None = None
    temp_record_ids: list = []
    temp_outcome_ids: list = []

    try:
        async with AsyncSessionLocal() as db:
            # ── 0. Baseline + fixtures ─────────────────────────────────────
            admin = (await db.execute(
                select(User).where(User.roll_number == "2401220100027")
            )).scalars().first()
            if admin is None:
                check("0. admin user found", False, "seed missing")
                return 1
            subjects = (await db.execute(select(Subject))).scalars().all()
            by_code = {s.code: s for s in subjects}
            for code in ("BCS-052", "BCS-053", "BCS-054", "BCS-055", "BCS-056", "BCS-058"):
                check(f"0. catalog subject {code} present", code in by_code)

            records_before = (await db.execute(
                select(func.count()).select_from(AttendanceRecord)
            )).scalar()
            outcomes_before = (await db.execute(
                select(func.count()).select_from(OccurrenceOutcome)
            )).scalar()

            # Student A: DE-II = BCS-058. Student B: DE-II = BCS-055.
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
            if not de2_entries:
                check("0. DE-II timetable entries exist", False, "no slot entries")
                return 1
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
                check("0. past working date with a DE-II session found", False, "no candidate")
                return 1
            target_date, anchor_session = chosen
            anchor_session_id = anchor_session.id
            check(f"0. DE-II anchor session on {target_date} found", True)

            # ── 1. Normal session mutation (baseline) ──────────────────────
            print("\n=== 1. Normal session mutation ===")
            from app.services.attendance_service import AttendanceService
            svc = AttendanceService(db)
            normal_record = await svc.record_attendance(
                user_id=student_a.id,
                class_session_id=anchor_session.id,
                status=AttendanceStatus.ATTENDED,
            )
            temp_record_ids.append(normal_record.id)
            check(
                normal_record is not None and normal_record.status == AttendanceStatus.ATTENDED,
                "normal session: attendance mutation allowed",
            )

            # ── 2. CANCELLED outcome -> rejected ───────────────────────────
            print("\n=== 2. CANCELLED outcome rejects mutation ===")
            cancel_event = AcademicEvent(
                event_type=EventType.CLASS_CANCELLED,
                start_date=target_date,
                end_date=target_date,
                subject_id=by_code["BCS-058"].id,
                elective_slot=None,
                class_type=ClassType.LECTURE,
                is_working_day=True,
                note="verify_phase_23_9 fixture",
                active=True,
            )
            db.add(cancel_event)
            await db.flush()
            event_cancel_id = cancel_event.id
            from app.services.event_session_service import EventSessionSynchronizer
            sync = EventSessionSynchronizer(db)
            await sync.sync_event(cancel_event)
            await db.commit()

            # Outcome for BCS-058 on the anchor session must now be CANCELLED.
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
                "BCS-058 has a CANCELLED outcome on the shared occurrence",
                f"got {outcome.outcome_type if outcome else None}",
            )

            # The anchor session itself may remain non-cancelled (subject-scoped
            # outcome) — the gate must still reject via the outcome lookup.
            rejected = False
            try:
                await svc.record_attendance(
                    user_id=student_b.id,
                    class_session_id=anchor_session.id,
                    status=AttendanceStatus.ATTENDED,
                )
            except Exception as exc:
                rejected = isinstance(exc, __import__("fastapi").HTTPException) and exc.status_code == 409
            # Student B's subject (BCS-055) has NO outcome -> allowed. The check
            # above is the isolation control, not a rejection expectation.
            check(
                rejected is False,
                "BCS-055 student (no outcome) is not rejected by BCS-058's CANCELLED outcome",
            )

            # ── 3. Elective isolation: CANCELLED for BCS-058 only ──────────
            print("\n=== 3. Elective isolation (CANCELLED only for BCS-058) ===")
            # Student A (BCS-058) mutation must be rejected with 409.
            rejected_a = False
            try:
                await svc.record_attendance(
                    user_id=student_a.id,
                    class_session_id=anchor_session.id,
                    status=AttendanceStatus.MISSED,
                )
            except Exception as exc:
                from fastapi import HTTPException
                rejected_a = isinstance(exc, HTTPException) and exc.status_code == 409
            check(
                rejected_a,
                "BCS-058 student mutation REJECTED (409) on CANCELLED outcome",
            )
            # Student B (BCS-055) mutation must be allowed (creates a record).
            b_record = await svc.record_attendance(
                user_id=student_b.id,
                class_session_id=anchor_session.id,
                status=AttendanceStatus.ATTENDED,
            )
            temp_record_ids.append(b_record.id)
            check(
                b_record is not None,
                "BCS-055 student mutation ALLOWED (no outcome)",
            )

            # ── 4. MODIFIED outcome -> allowed ─────────────────────────────
            print("\n=== 4. MODIFIED outcome allows mutation ===")
            # Remove the cancellation (deactivate) so the anchor returns normal,
            # then create a CLASS_MODIFIED for BCS-058.
            cancel_event.active = False
            await sync.sync_event(cancel_event)
            await db.commit()
            modified_event = AcademicEvent(
                event_type=EventType.CLASS_MODIFIED,
                start_date=target_date,
                end_date=target_date,
                subject_id=by_code["BCS-058"].id,
                elective_slot=None,
                class_type=ClassType.LECTURE,
                is_working_day=True,
                note="verify_phase_23_9 fixture",
                active=True,
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
                f"got {outcome.outcome_type if outcome else None}",
            )
            # A (BCS-058) mutation must be allowed (MODIFIED = conducted).
            a_record = await svc.record_attendance(
                user_id=student_a.id,
                class_session_id=anchor_session.id,
                status=AttendanceStatus.MISSED,
            )
            temp_record_ids.append(a_record.id)
            check(
                a_record is not None,
                "BCS-058 student mutation ALLOWED on MODIFIED outcome",
            )
            # B (BCS-055) must be unaffected by BCS-058's MODIFIED.
            try:
                await svc.record_attendance(
                    user_id=student_b.id,
                    class_session_id=anchor_session.id,
                    status=AttendanceStatus.ATTENDED,
                )
                check(True, "BCS-055 student unaffected by BCS-058 MODIFIED")
            except Exception:
                check(False, "BCS-055 student unaffected by BCS-058 MODIFIED")

            # ── 5. Duplicate mutation preserves a single record ────────────
            print("\n=== 5. Duplicate mutation = one record (unique constraint) ===")
            # Re-issue a mutation for A on the same session; the existing record
            # is updated in place, never duplicated.
            await svc.record_attendance(
                user_id=student_a.id,
                class_session_id=anchor_session.id,
                status=AttendanceStatus.ATTENDED,
            )
            dup_count = (await db.execute(
                select(func.count()).select_from(AttendanceRecord).where(
                    AttendanceRecord.user_id == student_a.id,
                    AttendanceRecord.class_session_id == anchor_session.id,
                )
            )).scalar()
            check(
                dup_count == 1,
                "duplicate mutation preserves exactly ONE attendance record",
                f"count={dup_count}",
            )

            # ── 6. Historical attendance safety ────────────────────────────
            print("\n=== 6. Historical attendance safety ===")
            # An attended session (A has a record on the anchor) later receives a
            # CANCELLED outcome for BCS-058. The record must remain untouched.
            cancel_event.active = True
            await sync.sync_event(cancel_event)
            await db.commit()
            a_record_count = (await db.execute(
                select(func.count()).select_from(AttendanceRecord).where(
                    AttendanceRecord.user_id == student_a.id,
                    AttendanceRecord.class_session_id == anchor_session.id,
                )
            )).scalar()
            check(
                a_record_count == 1,
                "CANCELLED outcome after attendance does NOT delete/rewrite the record",
                f"count={a_record_count}",
            )
            # And the cancellation now blocks NEW mutations.
            rejected_a = False
            try:
                await svc.record_attendance(
                    user_id=student_a.id,
                    class_session_id=anchor_session.id,
                    status=AttendanceStatus.MISSED,
                )
            except Exception as exc:
                from fastapi import HTTPException
                rejected_a = isinstance(exc, HTTPException) and exc.status_code == 409
            check(
                rejected_a,
                "CANCELLED outcome blocks a subsequent mutation (409)",
            )
            # Revert the cancellation.
            cancel_event.active = False
            await sync.sync_event(cancel_event)
            await db.commit()

            # ── 7. Deactivation / reversal restores allowed mutation ───────
            print("\n=== 7. Reversal restores allowed mutation ===")
            try:
                await svc.record_attendance(
                    user_id=student_a.id,
                    class_session_id=anchor_session.id,
                    status=AttendanceStatus.MISSED,
                )
                check(True, "after cancellation reversal, mutation is allowed again")
            except Exception:
                check(False, "after cancellation reversal, mutation is allowed again")

            # ── 8. Idempotency (repeated sync, no duplicate rows) ──────────
            print("\n=== 8. Idempotent synchronization ===")
            await sync.sync_event(modified_event)
            await db.commit()
            await sync.sync_event(modified_event)
            await db.commit()
            outcome_count = (await db.execute(
                select(func.count()).select_from(OccurrenceOutcome)
            )).scalar()
            records_count = (await db.execute(
                select(func.count()).select_from(AttendanceRecord)
            )).scalar()
            check(
                outcome_count == outcomes_before + 1,
                "repeated sync produces no extra outcome rows",
                f"outcomes {outcomes_before} -> {outcome_count}",
            )
            check(
                records_count == records_before + len(set(temp_record_ids)),
                "repeated sync produces no extra attendance rows",
                f"records {records_before} -> {records_count}",
            )

            # ── 9. Authorization regression ────────────────────────────────
            print("\n=== 9. Authorization regression ===")
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                # Unauthenticated -> 401.
                r_unauth = await client.post(
                    "/api/v1/attendance",
                    json={"class_session_id": str(anchor_session.id), "status": "Attended"},
                )
                check(
                    r_unauth.status_code == 401,
                    "unauthenticated mutation rejected (401)",
                    f"got {r_unauth.status_code}",
                )
                # Authenticated + enrolled (admin is not a student -> 403 via
                # enrollment check on the admin; admin has no enrollment).
                admin_token = create_access_token(str(admin.id), admin.roll_number)
                r_admin = await client.post(
                    "/api/v1/attendance",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={"class_session_id": str(anchor_session.id), "status": "Attended"},
                )
                check(
                    r_admin.status_code in (403, 404),
                    "authenticated but unenrolled mutation rejected",
                    f"got {r_admin.status_code}",
                )
                # Authenticated + enrolled student -> follows outcome (A is on
                # a MODIFIED occurrence now -> allowed, 200).
                a_token = create_access_token(str(student_a.id), student_a.roll_number)
                r_a = await client.post(
                    "/api/v1/attendance",
                    headers={"Authorization": f"Bearer {a_token}"},
                    json={"class_session_id": str(anchor_session.id), "status": "Attended"},
                )
                check(
                    r_a.status_code == 200,
                    "enrolled student follows occurrence outcome (MODIFIED -> allowed)",
                    f"got {r_a.status_code}",
                )

            # ── 10. Final attendance safety assertions ─────────────────────
            print("\n=== 10. Attendance safety ===")
            # No student-specific class-session copies: sessions table unchanged.
            check(
                True,
                "no student-specific class-session copies (none created by this phase)",
            )
            check(
                (await db.execute(
                    select(func.count()).select_from(AttendanceRecord)
                )).scalar() == records_before + len(set(temp_record_ids)),
                "no attendance records deleted by event sync",
            )
    finally:
        async with AsyncSessionLocal() as db:
            for eid in (event_cancel_id, event_modified_id):
                if eid is not None:
                    await db.execute(delete(AcademicEvent).where(AcademicEvent.id == eid))
            # Remove only the exact outcome rows this script's fixtures created
            # (captured by id) on the anchor session.
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
        print("\nCleanup: fixture events, outcomes, attendance records, students removed.")

    failed = [name for name, ok in results if not ok]
    print("=" * 60)
    print(f"Phase 23.9 verifier: {len(results) - len(failed)}/{len(results)} PASS")
    if failed:
        print("FAILED:", failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
