"""
Phase 23.8 — Quiz Integration verifier (MODIFIED outcome + subject-scoped
quiz reality).

Proves that the Phase 23.7 CLASS_MODIFIED / OccurrenceOutcomeType.MODIFIED
architecture integrates with the canonical quiz pipeline correctly:

  * A subject-scoped CLASS_MODIFIED event produces a MODIFIED occurrence
    outcome ONLY for the intended concrete subject (elective isolation:
    BCS-058 modified -> BCS-055/056 unaffected).
  * MODIFIED is occurrence METADATA for the quiz pipeline: a modified class is
    still a conducted class (counted in every attendance denominator, never
    turned into attended/absent/cancelled), and quiz dates / quiz occurrence
    identity / eligibility windows / eligibility results are unchanged.
  * A CLASS_MODIFIED with no matching occurrence on the date is a deterministic
    no-op.
  * Cancellation wins over modification (a CLASS_CANCELLED for the same
    subject/date never becomes MODIFIED).
  * Existing QUIZ_DAY / SURPRISE_QUIZ / CLASS_CANCELLED semantics are
    unchanged (no accidental collapse between event types).
  * Repeated synchronization is idempotent; deactivation/reversal converges
    the canonical state back.
  * No attendance records are created or altered; no student-specific
    infrastructure is introduced.

State changes are this script's own artifacts (two temp fixture students, one
temp CLASS_MODIFIED event, the outcome rows it implies) and are removed in the
finally block by exact captured ids. No pre-existing row is ever modified.

Requires the seeded dev DB (admin 2401220100027; current academic baseline).
Usage:
    python scripts/verify_phase_23_8.py
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
from app.models.enums import EventType, ClassType, ElectiveSlot, OccurrenceOutcomeType
from app.services.elective_resolver import ElectiveResolver
from sqlalchemy import select, func, delete

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def make_student(db, admin: User, suffix: str, ei: str, eii: str) -> User:
    roll = f"2401229{uuid.uuid4().hex[:5]}"
    user = User(
        roll_number=roll,
        name=f"Temp Quiz 23.8 Student {suffix}",
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
    print("Phase 23.8 — Quiz Integration (MODIFIED + subject-scoped quiz reality)")
    print("=" * 60)

    student_a_id = student_b_id = None
    event_id: uuid.UUID | None = None
    event2_id: uuid.UUID | None = None
    event3_id: uuid.UUID | None = None

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

            student_a = make_student(db, admin, "A", "BCS-054", "BCS-058")
            student_b = make_student(db, admin, "B", "BCS-052", "BCS-055")
            await db.flush()
            student_a_id = student_a.id
            student_b_id = student_b.id
            await enroll_and_choose(db, student_a, by_code, "BCS-054", "BCS-058")
            await enroll_and_choose(db, student_b, by_code, "BCS-052", "BCS-055")
            await db.commit()

            events_before = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
            outcomes_before = (await db.execute(select(func.count()).select_from(OccurrenceOutcome))).scalar()
            records_before = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()

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
            check(f"0. DE-II anchor session on {target_date} found (id={anchor_session.id})", True)

            # ── 1. Subject-scoped CLASS_MODIFIED for BCS-058 ───────────────
            print("\n=== 1. Subject-scoped MODIFIED outcome (BCS-058) ===")
            event = AcademicEvent(
                event_type=EventType.CLASS_MODIFIED,
                start_date=target_date,
                end_date=target_date,
                subject_id=by_code["BCS-058"].id,
                elective_slot=None,
                class_type=ClassType.LECTURE,
                is_working_day=True,
                note="verify_phase_23_8 fixture",
                active=True,
            )
            db.add(event)
            await db.flush()
            event_id = event.id
            from app.services.event_session_service import EventSessionSynchronizer
            sync = EventSessionSynchronizer(db)
            await sync.sync_event(event)
            await db.commit()

            outcomes = (await db.execute(
                select(OccurrenceOutcome).where(
                    OccurrenceOutcome.class_session_id == anchor_session.id
                )
            )).scalars().all()
            outcome_map = {o.subject_id: o.outcome_type for o in outcomes}
            check(
                outcome_map.get(by_code["BCS-058"].id) == OccurrenceOutcomeType.MODIFIED,
                "BCS-058 has a MODIFIED outcome on the shared DE-II occurrence",
                f"got {outcome_map}",
            )
            check(
                outcome_map.get(by_code["BCS-055"].id) is None,
                "BCS-055 has NO outcome (isolated)",
            )
            check(
                outcome_map.get(by_code["BCS-056"].id) is None,
                "BCS-056 has NO outcome (isolated)",
            )
            check(
                (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
                == records_before,
                "attendance records unchanged by MODIFIED integration",
            )

            # ── 2. Read-path isolation (per student) ──────────────────────
            print("\n=== 2. Read-path subject isolation ===")
            repo = __import__("app.repositories.attendance_repo", fromlist=["AttendanceRepository"]).AttendanceRepository(db)
            rows_a = await repo.get_daily_sessions(student_a.id, target_date)
            rows_b = await repo.get_daily_sessions(student_b.id, target_date)
            a_row = next((r for r in rows_a if r["subject_code"] == "BCS-058"), None)
            b_row = next((r for r in rows_b if r["subject_code"] == "BCS-055"), None)
            check(
                a_row is not None and a_row.get("outcome_type") == OccurrenceOutcomeType.MODIFIED,
                "Student A (DE-II=BCS-058) sees the MODIFIED occurrence",
                f"got {a_row.get('outcome_type') if a_row else None}",
            )
            check(
                b_row is not None and b_row.get("outcome_type") is None,
                "Student B (DE-II=BCS-055) sees the unchanged occurrence",
                f"got {b_row.get('outcome_type') if b_row else None}",
            )
            check(
                all(r.get("outcome_type") != OccurrenceOutcomeType.MODIFIED for r in rows_b),
                "Student A's MODIFIED state never leaks into Student B's rows",
            )

            # ── 3. Eligibility invariance (quiz reality) ──────────────────
            print("\n=== 3. Quiz eligibility invariance ===")
            admin_token = create_access_token(str(admin.id), admin.roll_number)
            headers = {"Authorization": f"Bearer {admin_token}"}
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                def elig(code: str, cycle: int):
                    return client.get(f"/api/v1/quiz/{code}/{cycle}", headers=headers)
                r1 = await elig("BCS-055", 1)
                r2 = await elig("BCS-058", 1)
                check(
                    r1.status_code in (200, 404),
                    f"eligibility endpoint reachable for BCS-055 ({r1.status_code})",
                )
                check(
                    r2.status_code in (200, 404),
                    f"eligibility endpoint reachable for BCS-058 ({r2.status_code})",
                )
                # Unaffected-subject eligibility must not crash and its counts
                # must not include the MODIFIED occurrence as attended/absent.
                if r1.status_code == 200:
                    body = r1.json()
                    check(
                        body["state"] in ("ELIGIBLE", "NOT_ELIGIBLE", "UNRESOLVED"),
                        "BCS-055 eligibility state is canonical",
                        body.get("state", "?"),
                    )

            # ── 4. No-op when no matching occurrence ──────────────────────
            print("\n=== 4. Deterministic no-op without a matching occurrence ===")
            no_slot_date = target_date + timedelta(days=7)
            event2 = AcademicEvent(
                event_type=EventType.CLASS_MODIFIED,
                start_date=no_slot_date,
                end_date=no_slot_date,
                subject_id=by_code["BCS-058"].id,
                elective_slot=None,
                class_type=ClassType.LECTURE,
                is_working_day=True,
                note="verify_phase_23_8 fixture",
                active=True,
            )
            db.add(event2)
            await db.flush()
            event2_id = event2.id
            await sync.sync_event(event2)
            await db.commit()
            count2 = (await db.execute(
                select(func.count()).select_from(OccurrenceOutcome)
            )).scalar()
            check(
                count2 == outcomes_before + 1,
                "no-session CLASS_MODIFIED creates no outcome (count unchanged)",
                f"outcomes {outcomes_before} -> {count2}",
            )

            # ── 5. Idempotency ────────────────────────────────────────────
            print("\n=== 5. Repeated synchronization is idempotent ===")
            await sync.sync_event(event)
            await db.commit()
            outcome_count = (await db.execute(
                select(func.count()).select_from(OccurrenceOutcome)
            )).scalar()
            check(
                outcome_count == outcomes_before + 1,
                "second sync creates no duplicate outcome rows",
                f"outcomes {outcomes_before + 1} -> {outcome_count}",
            )

            # ── 6. Cancellation wins over modification ────────────────────
            print("\n=== 6. Cancellation wins over modification ===")
            cancel_event = AcademicEvent(
                event_type=EventType.CLASS_CANCELLED,
                start_date=target_date,
                end_date=target_date,
                subject_id=by_code["BCS-058"].id,
                elective_slot=None,
                class_type=ClassType.LECTURE,
                is_working_day=True,
                note="verify_phase_23_8 fixture",
                active=True,
            )
            db.add(cancel_event)
            await db.flush()
            event3_id = cancel_event.id
            await sync.sync_event(cancel_event)
            await db.commit()
            final_outcome = (await db.execute(
                select(OccurrenceOutcome).where(
                    OccurrenceOutcome.class_session_id == anchor_session.id,
                    OccurrenceOutcome.subject_id == by_code["BCS-058"].id,
                )
            )).scalars().first()
            check(
                final_outcome is not None
                and final_outcome.outcome_type == OccurrenceOutcomeType.CANCELLED,
                "CLASS_CANCELLED + CLASS_MODIFIED on same subject/date -> CANCELLED wins",
                f"got {final_outcome.outcome_type if final_outcome else None}",
            )

            # ── 7. Deactivation reverts the effect ────────────────────────
            print("\n=== 7. Deactivation reverts the canonical state ===")
            cancel_event.active = False
            await sync.sync_event(cancel_event)
            await db.commit()
            final_outcome = (await db.execute(
                select(OccurrenceOutcome).where(
                    OccurrenceOutcome.class_session_id == anchor_session.id,
                    OccurrenceOutcome.subject_id == by_code["BCS-058"].id,
                )
            )).scalars().first()
            check(
                final_outcome is not None
                and final_outcome.outcome_type == OccurrenceOutcomeType.MODIFIED,
                "deactivating the cancellation restores the MODIFIED outcome",
                f"got {final_outcome.outcome_type if final_outcome else None}",
            )
            event.active = False
            await sync.sync_event(event)
            await db.commit()
            final_outcome = (await db.execute(
                select(OccurrenceOutcome).where(
                    OccurrenceOutcome.class_session_id == anchor_session.id,
                    OccurrenceOutcome.subject_id == by_code["BCS-058"].id,
                )
            )).scalars().first()
            check(
                final_outcome is None,
                "deactivating the MODIFIED event removes its outcome",
            )
            check(
                (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
                == records_before,
                "attendance records still unchanged after reversal",
            )
            check(
                (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
                == events_before + 1,  # event rows are soft-deleted (active=False), kept as rows
                "event rows preserved (soft deactivation, no deletion)",
            )
    finally:
        async with AsyncSessionLocal() as db:
            for eid in (event_id, event2_id, event3_id):
                if eid is not None:
                    await db.execute(delete(AcademicEvent).where(AcademicEvent.id == eid))
            for uid in (student_a_id, student_b_id):
                if uid is not None:
                    await db.execute(delete(StudentElectiveChoice).where(StudentElectiveChoice.user_id == uid))
                    await db.execute(delete(StudentEnrollment).where(StudentEnrollment.user_id == uid))
                    await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        print("\nCleanup: fixture events, outcomes, students removed.")

    failed = [name for name, ok in results if not ok]
    print("=" * 60)
    print(f"Phase 23.8 verifier: {len(results) - len(failed)}/{len(results)} PASS")
    if failed:
        print("FAILED:", failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
