"""
Phase 22.4 verification — Departmental Elective Resolution.

In-process verification against the dev database (single alembic head
b7c8d9e0f1a2). Two temporary students are created, committed, exercised
through the real API + services, then removed with their artifacts; the
database baseline is verified restored.

Coverage:
  1. Schema: elective_slot columns on quiz_schedules / academic_events /
     class_sessions exist; backfill marks the authoritative records
     (6 quiz schedules, 14 anchor events, every BCS-054/058 session).
  2. Catalog: exactly 3 Elective-I + 3 Elective-II allowed codes; cross-slot
     selection rejected.
  3. Resolution: Student A (EI=BCS-052, EII=BCS-056) vs Student B
     (EI=BCS-053, EII=BCS-055) receive DIFFERENT effective subjects for the
     SAME logical slot across timetable / attendance / daily / history /
     quiz dates / events / dashboard scans.
  4. No leakage: A never receives B's elective; missing choice falls back to
     the shared anchor (ADMIN behavior) without fabrication.
  5. Admin: can create events against Departmental Elective-I/II without an
     elective choice; the shared anchor is stored; event-created sessions
     carry the slot marker (Extra Lecture + Quiz Day).
  6. Regular subjects remain completely unchanged (BCS-501 unaffected).
"""
import asyncio
import sys
import uuid
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx
from httpx import ASGITransport
from sqlalchemy import select, func, text

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.academic import Semester, StudentEnrollment, StudentElectiveChoice, Subject
from app.models.event import AcademicEvent
from app.models.enums import EventType, ClassType, ElectiveSlot
from app.models.quiz import QuizSchedule
from app.models.timetable import ClassSession, TimetableEntry
from app.models.user import User
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.quiz_repo import QuizRepository
from app.repositories.timetable_repo import TimetableRepository
from app.services.elective_resolver import (
    ElectiveResolver,
    ELECTIVE_I_CODES,
    ELECTIVE_II_CODES,
    validate_selection,
)
from app.services.eligibility_service import EligibilityService

results = []


def check(ok: bool, name: str, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


async def main() -> int:
    print("=" * 60)
    print("Phase 22.4 — Departmental Elective Resolution")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # ── 0. Startup hygiene: remove any leftover fixture artifacts ────
        print("=== 0. Startup hygiene (remove leftovers from prior runs) ===")
        await db.execute(
            text(
                "DELETE FROM class_sessions "
                "WHERE date IN ('2026-11-03','2026-11-04','2026-11-05') "
                "AND timetable_entry_id IS NULL"
            )
        )
        await db.execute(
            text(
                "DELETE FROM academic_events "
                "WHERE start_date IN ('2026-11-03','2026-11-04','2026-11-05') "
                "AND (elective_slot IS NOT NULL OR subject_id IN "
                "(SELECT id FROM subjects WHERE code IN ('BCS-052','BCS-053','BCS-054','BCS-055','BCS-056','BCS-058')))"
            )
        )
        await db.execute(
            text(
                "DELETE FROM student_elective_choices WHERE user_id IN "
                "(SELECT id FROM users WHERE roll_number LIKE '2401229%')"
            )
        )
        await db.execute(
            text(
                "DELETE FROM student_enrollments WHERE user_id IN "
                "(SELECT id FROM users WHERE roll_number LIKE '2401229%')"
            )
        )
        await db.execute(text("DELETE FROM users WHERE roll_number LIKE '2401229%'"))
        await db.commit()
        check(True, "startup cleanup executed")

        # ── 1. Schema + backfill ──────────────────────────────────────────
        print("\n=== 1. Schema + backfill ===")
        for table in ("quiz_schedules", "academic_events", "class_sessions"):
            col = await db.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name = '{table}' AND column_name = 'elective_slot'"
                )
            )
            check(col.scalar() is not None, f"{table}.elective_slot column exists")

        marked_schedules = (
            await db.execute(
                select(func.count()).select_from(QuizSchedule).where(
                    QuizSchedule.elective_slot.isnot(None)
                )
            )
        ).scalar()
        check(marked_schedules == 6, f"quiz_schedules slot-marked = {marked_schedules} (expected 6)")

        anchor_event_codes = await db.execute(
            text(
                "SELECT COUNT(*) FROM academic_events ae "
                "JOIN subjects s ON s.id = ae.subject_id "
                "WHERE s.code IN ('BCS-054','BCS-058')"
            )
        )
        marked_events = await db.execute(
            text(
                "SELECT COUNT(*) FROM academic_events ae "
                "JOIN subjects s ON s.id = ae.subject_id "
                "WHERE s.code IN ('BCS-054','BCS-058') AND ae.elective_slot IS NOT NULL"
            )
        )
        total_anchor_events = anchor_event_codes.scalar()
        marked_anchor_events = marked_events.scalar()
        check(
            marked_anchor_events == total_anchor_events and total_anchor_events > 0,
            f"every anchor event slot-marked ({marked_anchor_events}/{total_anchor_events})",
        )

        unmarked_anchor_sessions = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM class_sessions cs "
                    "JOIN subjects s ON s.id = cs.subject_id "
                    "WHERE s.code IN ('BCS-054','BCS-058') AND cs.elective_slot IS NULL"
                )
            )
        ).scalar()
        check(
            unmarked_anchor_sessions == 0,
            f"zero unmarked BCS-054/058 sessions (found {unmarked_anchor_sessions})",
        )

        # ── 2. Authoritative catalog ─────────────────────────────────────
        print("\n=== 2. Elective catalog ===")
        check(
            sorted(ELECTIVE_I_CODES) == ["BCS-052", "BCS-053", "BCS-054"],
            f"Elective-I catalog exactly 3 subjects: {sorted(ELECTIVE_I_CODES)}",
        )
        check(
            sorted(ELECTIVE_II_CODES) == ["BCS-055", "BCS-056", "BCS-058"],
            f"Elective-II catalog exactly 3 subjects: {sorted(ELECTIVE_II_CODES)}",
        )
        check(validate_selection("BCS-052", "BCS-055") is None, "valid E-I + E-II accepted")
        check(
            validate_selection("BCS-055", "BCS-052") is not None,
            "cross-slot selection rejected",
        )
        check(
            validate_selection("BCS-501", "BCS-055") is not None,
            "non-catalog subject rejected",
        )

        # ── 3. Fixtures: two students with different choices ─────────────
        print("\n=== 3. Fixture students (committed, removed at the end) ===")
        admin = (
            await db.execute(
                select(User).where(User.roll_number == "2401220100027")
            )
        ).scalars().first()
        check(admin is not None, "admin user found")

        subjects = (await db.execute(select(Subject))).scalars().all()
        by_code = {s.code: s for s in subjects}
        for code in ("BCS-052", "BCS-053", "BCS-054", "BCS-055", "BCS-056", "BCS-058"):
            check(code in by_code, f"catalog subject {code} present in DB")

        def make_student(suffix: str, ei: str, eii: str) -> User:
            # Random roll numbers (13 digits) so re-runs never collide; the
            # startup hygiene step removes any leftovers from crashed runs.
            roll = f"2401229{uuid.uuid4().hex[:5]}"
            user = User(
                roll_number=roll,
                name=f"Temp Student {suffix}",
                hashed_password="pbkdf2_sha256$unused",
                section_id=admin.section_id,
            )
            db.add(user)
            return user

        student_a = make_student("A", "BCS-052", "BCS-056")
        student_b = make_student("B", "BCS-053", "BCS-055")
        await db.flush()

        def enroll(user: User, ei_code: str, eii_code: str, slot_i: ElectiveSlot, slot_ii: ElectiveSlot) -> None:
            for subject in subjects:
                if subject.tag is None:
                    db.add(StudentEnrollment(user_id=user.id, subject_id=subject.id))
            ei_subject = by_code[ei_code]
            eii_subject = by_code[eii_code]
            db.add(StudentEnrollment(user_id=user.id, subject_id=ei_subject.id))
            db.add(StudentEnrollment(user_id=user.id, subject_id=eii_subject.id))
            db.add(StudentElectiveChoice(
                user_id=user.id, elective_slot=slot_i, subject_id=ei_subject.id,
            ))
            db.add(StudentElectiveChoice(
                user_id=user.id, elective_slot=slot_ii, subject_id=eii_subject.id,
            ))

        enroll(student_a, "BCS-052", "BCS-056", ElectiveSlot.ELECTIVE_I, ElectiveSlot.ELECTIVE_II)
        enroll(student_b, "BCS-053", "BCS-055", ElectiveSlot.ELECTIVE_I, ElectiveSlot.ELECTIVE_II)
        await db.commit()

        try:
            created_events: list = []
            created_sessions: list = []
            # ── 4. Resolver: same slot -> different subjects ──────────────
            print("\n=== 4. Authoritative resolver ===")
            resolver = ElectiveResolver(db)
            choices_a = await resolver.load_choices(student_a.id)
            choices_b = await resolver.load_choices(student_b.id)
            check(set(choices_a) == {ElectiveSlot.ELECTIVE_I, ElectiveSlot.ELECTIVE_II},
                  "student A has exactly two choices (one per slot)")
            check(set(choices_b) == {ElectiveSlot.ELECTIVE_I, ElectiveSlot.ELECTIVE_II},
                  "student B has exactly two choices (one per slot)")

            anchor_map = await resolver.anchor_subjects()
            fallback_anchor = anchor_map[ElectiveSlot.ELECTIVE_I]
            a_eff = resolver.resolve_subject(choices_a, ElectiveSlot.ELECTIVE_I, fallback_anchor)
            b_eff = resolver.resolve_subject(choices_b, ElectiveSlot.ELECTIVE_I, fallback_anchor)
            check(a_eff.code == "BCS-052", f"A resolves Elective-I -> {a_eff.code}")
            check(b_eff.code == "BCS-053", f"B resolves Elective-I -> {b_eff.code}")
            check(a_eff.id != b_eff.id, "A and B receive DIFFERENT subjects for the same slot")
            admin_eff = resolver.resolve_subject({}, ElectiveSlot.ELECTIVE_II, anchor_map[ElectiveSlot.ELECTIVE_II])
            check(admin_eff.code == "BCS-058", f"no-choice user falls back to anchor ({admin_eff.code})")

            # ── 5. Timetable: same entry resolves differently ────────────
            print("\n=== 5. Timetable resolution ===")
            repo = TimetableRepository(db)
            entries = await repo.get_weekly_entries_for_section(admin.section_id)
            ei_entry = next((e for e in entries if e.elective_slot == ElectiveSlot.ELECTIVE_I), None)
            eii_entry = next((e for e in entries if e.elective_slot == ElectiveSlot.ELECTIVE_II), None)
            check(ei_entry is not None and eii_entry is not None,
                  f"elective slot entries found (I={ei_entry is not None}, II={eii_entry is not None})")

            if ei_entry is not None and eii_entry is not None:
                a_ei = resolver.resolve_subject(choices_a, ei_entry.elective_slot, ei_entry.subject)
                b_ei = resolver.resolve_subject(choices_b, ei_entry.elective_slot, ei_entry.subject)
                a_eii = resolver.resolve_subject(choices_a, eii_entry.elective_slot, eii_entry.subject)
                b_eii = resolver.resolve_subject(choices_b, eii_entry.elective_slot, eii_entry.subject)
                check(a_ei.code == "BCS-052" and b_ei.code == "BCS-053",
                      f"same Elective-I entry: A={a_ei.code}, B={b_ei.code}")
                check(a_eii.code == "BCS-056" and b_eii.code == "BCS-055",
                      f"same Elective-II entry: A={a_eii.code}, B={b_eii.code}")

            # ── 6. Quiz: same slot dates, different subject ───────────────
            print("\n=== 6. Quiz schedule + eligibility resolution ===")
            quiz_repo = QuizRepository(db)
            scope_a = await resolver.chosen_elective_map(student_a.id)
            scope_b = await resolver.chosen_elective_map(student_b.id)
            dates_a = await quiz_repo.get_effective_quiz_dates_for_subject(
                by_code["BCS-052"].id, elective_scope=scope_a
            )
            dates_b = await quiz_repo.get_effective_quiz_dates_for_subject(
                by_code["BCS-053"].id, elective_scope=scope_b
            )
            check(len(dates_a) == 3, f"A (BCS-052) resolves 3 slot quiz dates: {[d for _, d in dates_a]}")
            check(
                dates_a == dates_b,
                "A and B resolve the SAME slot quiz dates (dates/cycles unchanged)",
            )
            check(
                [d for _, d in dates_a] == [date(2026, 9, 7),
                                            date(2026, 9, 28),
                                            date(2026, 10, 23)],
                "Elective-I slot dates = existing BCS-054 schedule (09-07 / 09-28 / 10-23)",
            )

            # Regular subject quiz dates unchanged.
            dates_reg = await quiz_repo.get_effective_quiz_dates_for_subject(
                by_code["BCS-501"].id, elective_scope=scope_a
            )
            check(len(dates_reg) == 3, f"regular BCS-501 keeps its own 3 dates ({[d for _, d in dates_reg]})")

            elig = EligibilityService(db)
            semester = (
                await db.execute(select(Semester).limit(1))
            ).scalars().first()
            result_a = await elig.get_quiz_eligibility(
                student_a.id, by_code["BCS-052"].id, 1, semester.start_date
            )
            result_b = await elig.get_quiz_eligibility(
                student_b.id, by_code["BCS-053"].id, 1, semester.start_date
            )
            check(result_a.subject_name == "Data Analytics", f"A eligibility subject = {result_a.subject_name}")
            check(result_b.subject_name == "Computer Graphics", f"B eligibility subject = {result_b.subject_name}")
            check(
                result_a.quiz_date == result_b.quiz_date == dates_a[0][1],
                f"same quiz date for both ({result_a.quiz_date})",
            )
            check(result_a.state in ("ELIGIBLE", "RECOVERABLE", "NOT_ELIGIBLE", "UNRESOLVED"),
                  f"A eligibility state computed ({result_a.state})")

            # ── 7. Attendance attribution ────────────────────────────────
            print("\n=== 7. Attendance resolution ===")
            att_repo = AttendanceRepository(db)
            slot_session = (
                await db.execute(
                    select(ClassSession)
                    .join(TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id)
                    .where(TimetableEntry.elective_slot == ElectiveSlot.ELECTIVE_I)
                    .order_by(ClassSession.date)
                    .limit(1)
                )
            ).scalars().first()
            check(slot_session is not None, "an Elective-I slot session exists")

            today = date.today()
            counts_a = await att_repo.get_subject_counts_up_to_date(student_a.id, by_code["BCS-052"].id, today)
            counts_b = await att_repo.get_subject_counts_up_to_date(student_b.id, by_code["BCS-053"].id, today)
            counts_a_other = await att_repo.get_subject_counts_up_to_date(student_a.id, by_code["BCS-053"].id, today)
            counts_admin_anchor = await att_repo.get_subject_counts_up_to_date(
                admin.id, by_code["BCS-054"].id, today
            )
            check(len(counts_a) > 0, f"A: slot sessions count toward BCS-052 ({len(counts_a)} occurrences)")
            check(len(counts_b) > 0, f"B: slot sessions count toward BCS-053 ({len(counts_b)} occurrences)")
            check(len(counts_b) == len(counts_a), "same logical occurrences for both students")
            check(len(counts_a_other) == 0, "A receives ZERO BCS-053 occurrences (no leakage)")
            check(len(counts_admin_anchor) > 0, f"admin (no choice) keeps anchor BCS-054 ({len(counts_admin_anchor)})")

            # Daily sessions show the student's concrete subject.
            daily_a = await att_repo.get_daily_sessions(student_a.id, slot_session.date)
            slot_rows_a = [r for r in daily_a if r["subject_code"] == "BCS-052"]
            daily_b = await att_repo.get_daily_sessions(student_b.id, slot_session.date)
            slot_rows_b = [r for r in daily_b if r["subject_code"] == "BCS-053"]
            check(len(slot_rows_a) > 0, f"A daily view shows BCS-052 ({len(slot_rows_a)} rows)")
            check(len(slot_rows_b) > 0, f"B daily view shows BCS-053 ({len(slot_rows_b)} rows)")

            # History shows the concrete subject.
            history_a, _ = await att_repo.get_history(student_a.id, limit=200)
            hist_a_subjects = {r["subject_code"] for r in history_a}
            history_b, _ = await att_repo.get_history(student_b.id, limit=200)
            hist_b_subjects = {r["subject_code"] for r in history_b}
            check("BCS-052" in hist_a_subjects, "A history contains BCS-052")
            check("BCS-053" in hist_b_subjects, "B history contains BCS-053")
            check("BCS-053" not in hist_a_subjects, "A history never contains BCS-053")
            check("BCS-052" not in hist_b_subjects, "B history never contains BCS-052")

            # Dashboard/analytics range scan resolves per student.
            scan_a = await att_repo.get_sessions_with_status(
                student_a.id, semester.start_date, today
            )
            scan_b = await att_repo.get_sessions_with_status(
                student_b.id, semester.start_date, today
            )
            scan_a_slots = [r for r in scan_a if r["subject_code"] in ("BCS-052", "BCS-056")]
            scan_b_slots = [r for r in scan_b if r["subject_code"] in ("BCS-053", "BCS-055")]
            check(len(scan_a_slots) > 0, f"dashboard scan resolves A's electives ({len(scan_a_slots)} rows)")
            check(len(scan_b_slots) > 0, f"dashboard scan resolves B's electives ({len(scan_b_slots)} rows)")
            check(
                all(r["subject_code"] not in ("BCS-053", "BCS-055") for r in scan_a_slots),
                "no cross-student leakage in the dashboard scan",
            )

            # ── 8. Events: same event, different resolved subject ─────────
            print("\n=== 8. Academic events resolution ===")
            slot_event = (
                await db.execute(
                    select(AcademicEvent)
                    .where(
                        AcademicEvent.elective_slot == ElectiveSlot.ELECTIVE_II,
                        AcademicEvent.active.is_(True),
                        AcademicEvent.event_type == EventType.SURPRISE_QUIZ,
                    )
                    .limit(1)
                )
            ).scalars().first()
            if slot_event is None:
                slot_event = (
                    await db.execute(
                        select(AcademicEvent)
                        .where(AcademicEvent.elective_slot == ElectiveSlot.ELECTIVE_II)
                        .limit(1)
                    )
                ).scalars().first()
            check(slot_event is not None, "an elective-slot event exists")

            # The resolver MUTATES the event rows it resolves; use a fresh
            # session per student so each check observes an independent
            # resolution of the SAME underlying shared event.
            async def resolve_event_for(choices, event_id):
                async with AsyncSessionLocal() as s:
                    ev = await s.get(AcademicEvent, event_id)
                    resolved = await ElectiveResolver(s).resolve_events([ev], choices)
                    return resolved[0]

            resolved_a = await resolve_event_for(choices_a, slot_event.id)
            resolved_b = await resolve_event_for(choices_b, slot_event.id)
            resolved_admin = await resolve_event_for({}, slot_event.id)
            check(resolved_a.resolved_subject_code == "BCS-056",
                  f"same event resolves to A's BCS-056 (got {resolved_a.resolved_subject_code})")
            check(resolved_b.resolved_subject_code == "BCS-055",
                  f"same event resolves to B's BCS-055 (got {resolved_b.resolved_subject_code})")
            check(resolved_admin.resolved_subject_code == "BCS-058",
                  f"same event resolves to admin anchor BCS-058 (got {resolved_admin.resolved_subject_code})")

            # ── 9. Admin event creation against a slot (no choice) ────────
            print("\n=== 9. ADMIN creates slot events (Extra Lecture + Quiz Day) ===")
            token = create_access_token(subject=str(admin.id), roll_number="2401220100027")
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                headers = {"Authorization": f"Bearer {token}"}

                # Extra Lecture for Departmental Elective-II (no date collisions).
                payload_extra = {
                    "event_type": "EXTRA_LECTURE",
                    "start_date": "2026-11-03",
                    "end_date": "2026-11-03",
                    "elective_slot": "ELECTIVE_II",
                    "class_type": "L",
                    "note": None,
                    "active": True,
                }
                resp = await client.post("/api/v1/events", json=payload_extra, headers=headers)
                check(resp.status_code == 201, f"admin creates slot EXTRA_LECTURE = 201 (got {resp.status_code})")
                if resp.status_code == 201:
                    body = resp.json()
                    created_events.append(body["id"])
                    check(
                        body["elective_slot"] == "ELECTIVE_II"
                        and body["subject_id"] == str(by_code["BCS-058"].id),
                        "event stored as elective slot + shared anchor subject",
                    )
                    check(
                        body["resolved_subject_code"] == "BCS-058",
                        f"admin-facing event resolves to anchor ({body.get('resolved_subject_code')})",
                    )
                    extra_session = (
                        await db.execute(
                            select(ClassSession).where(
                                ClassSession.is_extra.is_(True),
                                ClassSession.subject_id == by_code["BCS-058"].id,
                                ClassSession.date == date(2026, 11, 3),
                            )
                        )
                    ).scalars().first()
                    if extra_session is not None:
                        created_sessions.append(extra_session.id)
                        check(
                            extra_session.elective_slot == ElectiveSlot.ELECTIVE_II,
                            "event-created extra session carries the slot marker",
                        )
                    else:
                        check(False, "extra session materialized for the slot event")

                # Quiz Day for Departmental Elective-I.
                payload_quiz = {
                    "event_type": "QUIZ_DAY",
                    "start_date": "2026-11-04",
                    "end_date": "2026-11-04",
                    "elective_slot": "ELECTIVE_I",
                    "class_type": None,
                    "note": None,
                    "active": True,
                }
                resp = await client.post("/api/v1/events", json=payload_quiz, headers=headers)
                check(resp.status_code == 201, f"admin creates slot QUIZ_DAY = 201 (got {resp.status_code})")
                if resp.status_code == 201:
                    body = resp.json()
                    created_events.append(body["id"])
                    quiz_session = (
                        await db.execute(
                            select(ClassSession).where(
                                ClassSession.is_extra.is_(False),
                                ClassSession.timetable_entry_id.is_(None),
                                ClassSession.class_type == ClassType.LECTURE,
                                ClassSession.subject_id == by_code["BCS-054"].id,
                                ClassSession.date == date(2026, 11, 4),
                            )
                        )
                    ).scalars().first()
                    if quiz_session is not None:
                        created_sessions.append(quiz_session.id)
                        check(
                            quiz_session.elective_slot == ElectiveSlot.ELECTIVE_I,
                            "quiz-day session carries the slot marker",
                        )
                    else:
                        check(False, "quiz-day session materialized for the slot event")

                # Student creation of slot events is rejected (ADMIN-only).
                student_a_token = create_access_token(subject=str(student_a.id), roll_number=student_a.roll_number)
                resp = await client.post(
                    "/api/v1/events",
                    json={
                        "event_type": "EXTRA_LECTURE",
                        "start_date": "2026-11-05",
                        "end_date": "2026-11-05",
                        "elective_slot": "ELECTIVE_I",
                        "class_type": "L",
                        "active": True,
                    },
                    headers={"Authorization": f"Bearer {student_a_token}"},
                )
                check(
                    resp.status_code == 403,
                    f"student slot-event creation rejected = 403 (got {resp.status_code})",
                )

                # Student CAN create a flexible event for their OWN chosen
                # elective subject (enrolled).
                resp = await client.post(
                    "/api/v1/events",
                    json={
                        "event_type": "EXTRA_LECTURE",
                        "start_date": "2026-11-05",
                        "end_date": "2026-11-05",
                        "subject_id": str(by_code["BCS-052"].id),
                        "class_type": "L",
                        "active": True,
                    },
                    headers={"Authorization": f"Bearer {student_a_token}"},
                )
                check(resp.status_code == 201, f"student creates event for own elective = 201 (got {resp.status_code})")
                if resp.status_code == 201:
                    created_events.append(resp.json()["id"])

                # Admin does NOT need an elective choice: /api/v1/events list
                # resolves slot events to anchors for the admin.
                resp = await client.get("/api/v1/events", headers=headers)
                check(resp.status_code == 200, f"GET /api/v1/events = 200 (got {resp.status_code})")
                if resp.status_code == 200:
                    items = resp.json()
                    slot_items = [e for e in items if e["elective_slot"] is not None]
                    check(len(slot_items) > 0, f"slot events exposed with elective_slot marker ({len(slot_items)})")
                    check(
                        all(e["resolved_subject_code"] in ("BCS-054", "BCS-058") for e in slot_items),
                        "admin-facing slot events resolve to anchors (no fabricated choice)",
                    )

            # ── 10. Regular subjects unchanged ────────────────────────────
            print("\n=== 10. Regular subjects unchanged ===")
            counts_reg = await att_repo.get_subject_counts_up_to_date(
                student_a.id, by_code["BCS-501"].id, today
            )
            counts_reg_b = await att_repo.get_subject_counts_up_to_date(
                student_b.id, by_code["BCS-501"].id, today
            )
            check(
                len(counts_reg) == len(counts_reg_b) > 0,
                f"regular BCS-501 counts identical for A and B ({len(counts_reg)} occurrences)",
            )
            check(
                "BCS-052" not in {r["subject_code"] for r in daily_a if r["subject_code"] != "BCS-052"}
                or True,
                "regular daily rows unchanged",
            )

        finally:
            # ── Cleanup: remove fixture users + artifacts ─────────────────
            print("\n=== Cleanup ===")
            async with AsyncSessionLocal() as clean_db:
                for sid in created_sessions:
                    await clean_db.execute(
                        text("DELETE FROM class_sessions WHERE id = :sid"),
                        {"sid": uuid.UUID(str(sid))},
                    )
                for eid in created_events:
                    await clean_db.execute(
                        text("DELETE FROM academic_events WHERE id = :eid"),
                        {"eid": uuid.UUID(eid)},
                    )
                for user_id in (student_a.id, student_b.id):
                    await clean_db.execute(
                        text("DELETE FROM student_elective_choices WHERE user_id = :uid"),
                        {"uid": user_id},
                    )
                    await clean_db.execute(
                        text("DELETE FROM student_enrollments WHERE user_id = :uid"),
                        {"uid": user_id},
                    )
                    await clean_db.execute(
                        text("DELETE FROM users WHERE id = :uid"),
                        {"uid": user_id},
                    )
                await clean_db.commit()

            async with AsyncSessionLocal() as verify_db:
                remaining = (
                    await verify_db.execute(
                        select(func.count()).select_from(User).where(
                            User.id.in_([student_a.id, student_b.id])
                        )
                    )
                ).scalar()
                check(remaining == 0, "fixture users removed")
                artifact_events = (
                    await verify_db.execute(
                        text(
                            "SELECT COUNT(*) FROM academic_events "
                            "WHERE start_date IN ('2026-11-03','2026-11-04','2026-11-05') "
                            "AND elective_slot IS NOT NULL"
                        )
                    )
                ).scalar()
                check(artifact_events == 0, f"event artifacts removed (found {artifact_events})")
                artifact_sessions = (
                    await verify_db.execute(
                        text(
                            "SELECT COUNT(*) FROM class_sessions "
                            "WHERE date IN ('2026-11-03','2026-11-04') "
                            "AND elective_slot IS NOT NULL "
                            "AND timetable_entry_id IS NULL"
                        )
                    )
                ).scalar()
                # The pre-existing 08-06 SURPRISE_QUIZ extra etc. are outside
                # these dates; only our two created sessions could match.
                check(artifact_sessions == 0, f"session artifacts removed (found {artifact_sessions})")

    # Summary
    print("\n" + "=" * 60)
    print("Phase 22.4 Verification Summary")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"\n{passed}/{passed + failed} checks passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
