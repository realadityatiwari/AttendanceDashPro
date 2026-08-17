"""
Phase 2 verification — Active QUIZ_DAY AcademicEvents are the authoritative
source of quiz dates used by Quiz Eligibility.

Verifies the events-authoritative contract end-to-end against the real
database (rollback transactions only — the frozen baseline is restored on
every exit; identical to the other verifiers):

  1.  Authority: effective quiz dates for a subject == its ACTIVE QUIZ_DAY
      event dates (positional cycles: earliest event = cycle 1). The
      eligibility API resolves quiz_date/windows from those events.
  2.  Create: a new active QUIZ_DAY event becomes the effective quiz date;
      the corresponding cycle is recalculated; windows use the new quiz;
      only the affected subject changes.
  3.  Dedup: multiple active events for the same subject/date collapse to ONE
      effective quiz date; an identical duplicate is rejected (409).
  4.  Reschedule: moving an event's date removes the stale date and the new
      date drives eligibility; no duplicate effective quiz dates.
  5.  Deactivate: an inactive quiz event no longer participates in Quiz
      Eligibility (remaining cycles shift; a missing cycle is UNRESOLVED).
  6.  Reactivate: the quiz participates again, exactly as before.
  7.  Option-A intact: the quiz-day-shaped session remains excluded from
      L/T counts (cumulative-window exclusion); normal timetable sessions
      remain included.
  8.  Database restored to the exact baseline (no residue); the
      quiz_schedules projection (18 SCHEDULED) still matches the 18 active
      QUIZ_DAY events 1:1.

Usage:
    python scripts/verify_phase_2_quiz_events.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import date

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User, Section
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.academic import StudentEnrollment, Subject, Semester
from app.models.quiz import QuizSchedule, ScheduleStatus
from app.models.enums import AttendanceStatus, ClassType, EventType
from app.engines.attendance_engine import normalize_class_type
from app.engines.calendar_engine import (
    get_attendance_window, get_cumulative_attendance_window, DEFAULT_WEEKENDS,
)
from app.repositories.quiz_repo import QuizRepository
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.calendar_repo import CalendarRepository
from app.services.eligibility_service import EligibilityService
from app.schemas.attendance import EligibilityState
from app.schemas.academic import Subject as SubjectSchema, Milestone, Timeline
from sqlalchemy import select, func

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def aggregate(raw_counts) -> dict:
    """Raw repo (class_type, status) rows -> canonical L/T count shape."""
    out = {
        'L': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
        'T': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
    }
    for class_type_str, status in raw_counts:
        t = normalize_class_type(class_type_str.value)
        if t not in out:
            continue
        out[t]['tot'] += 1
        if status == AttendanceStatus.ATTENDED:
            out[t]['att'] += 1
        elif status == AttendanceStatus.MISSED:
            out[t]['miss'] += 1
        else:
            out[t]['pending'] += 1
    return out


async def main() -> int:
    async with AsyncSessionLocal() as db:
        events_before = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
        sessions_before = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
        cancelled_before = (await db.execute(
            select(func.count()).select_from(ClassSession).where(ClassSession.is_cancelled.is_(True)))).scalar()
        extra_before = (await db.execute(
            select(func.count()).select_from(ClassSession).where(ClassSession.is_extra.is_(True)))).scalar()
        records_before = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
        enrollments_before = (await db.execute(select(func.count()).select_from(StudentEnrollment))).scalar()
        subjects_before = (await db.execute(select(func.count()).select_from(Subject))).scalar()
        quizzes_before = (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar()
        users_before = (await db.execute(select(func.count()).select_from(User))).scalar()
        quiz_events_before = (await db.execute(
            select(func.count()).select_from(AcademicEvent).where(
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.active.is_(True)))).scalar()
        scheduled_before = (await db.execute(
            select(func.count()).select_from(QuizSchedule).where(
                QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED))).scalar()

        admin_user = (await db.execute(select(User).where(User.roll_number == "2401220100027"))).scalars().first()
        semester_start = date(2026, 7, 15)
        if admin_user.section_id:
            section = await db.get(Section, admin_user.section_id)
            if section:
                semester = await db.get(Semester, section.semester_id)
                if semester:
                    semester_start = semester.start_date

        bcs501_id = (await db.execute(select(Subject.id).where(Subject.code == "BCS-501"))).scalar_one()
        bnc501_id = (await db.execute(select(Subject.id).where(Subject.code == "BNC-501"))).scalar_one()
        theory_ids = (await db.execute(
            select(Subject.id).where(Subject.quiz_applicable.is_(True)))).scalars().all()

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # ------------------------------------------------------- 1. Authority (read-only)
    async with AsyncSessionLocal() as db:
        repo = QuizRepository(db)
        service = EligibilityService(db)

        bcs501_effective = await repo.get_effective_quiz_dates_for_subject(bcs501_id)
        bcs501_event_dates = sorted(
            (await db.execute(
                select(AcademicEvent.start_date).where(
                    AcademicEvent.event_type == EventType.QUIZ_DAY,
                    AcademicEvent.active.is_(True),
                    AcademicEvent.subject_id == bcs501_id,
                ))).scalars().all())
        check("1. effective quiz dates == active QUIZ_DAY event dates (positional "
              "cycles; BCS-501 = 08-27, 09-17, 10-12)",
              bcs501_effective == [(1, date(2026, 8, 27)), (2, date(2026, 9, 17)), (3, date(2026, 10, 12))]
              and [d for _, d in bcs501_effective] == bcs501_event_dates,
              f"effective={bcs501_effective} events={bcs501_event_dates}")

        # Every theory subject: 3 effective cycles from its active events, and
        # the quiz_schedules projection matches the active events 1:1.
        effective_by_subject = await repo.get_effective_quiz_dates_for_subjects(list(theory_ids))
        check("3. every theory subject has exactly 3 effective quiz cycles",
              len(effective_by_subject) == len(theory_ids)
              and all(len(dates) == 3 for dates in effective_by_subject.values()),
              f"subjects={len(effective_by_subject)} theory={len(theory_ids)} "
              f"cycles={ {str(k)[:8]: len(v) for k, v in effective_by_subject.items()} }")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/quiz-eligibility/BCS-501/2", headers=admin_headers)
        body = r.json()
        check("2. eligibility API resolves quiz_date/window from the active event "
              "(BCS-501 Q2 = 09-17; window 08-27..09-16)",
              r.status_code == 200 and body["quiz_date"] == "2026-09-17"
              and body["window_start"] == "2026-08-27" and body["window_end"] == "2026-09-16",
              f"got {body.get('quiz_date')} window={body.get('window_start')}..{body.get('window_end')}")

        r = await client.get("/api/v1/quiz-eligibility/current-cycle", headers=admin_headers)
        cc = r.json()
        check("4. current-cycle unchanged: next upcoming quiz = 08-24 (Quiz I)",
              r.status_code == 200 and cc["quiz_cycle"] == 1
              and cc["quiz_date"] == "2026-08-24" and cc["basis"] == "next_upcoming",
              f"got {cc}")

        # ------------------------------------------------ 8. Duplicate guard (409)
        r = await client.post("/api/v1/events", headers=admin_headers, json={
            "event_type": "QUIZ_DAY",
            "start_date": "2026-09-17",
            "end_date": "2026-09-17",
            "subject_id": str(bcs501_id),
            "active": True,
        })
        check("8. identical duplicate active QUIZ_DAY event rejected (409)",
              r.status_code == 409, f"status={r.status_code}")

    # ---------------------------------------------- 2. Create (rollback transaction)
    async with AsyncSessionLocal() as db:
        service = EligibilityService(db)
        repo = QuizRepository(db)
        db.add(AcademicEvent(
            event_type=EventType.QUIZ_DAY,
            start_date=date(2026, 8, 20),
            end_date=date(2026, 8, 20),
            subject_id=bcs501_id,
            active=True,
        ))
        await db.flush()

        effective = await repo.get_effective_quiz_dates_for_subject(bcs501_id)
        result = await service.get_quiz_eligibility(
            admin_user.id, bcs501_id, 1, semester_start=semester_start)
        cc = await service.get_current_quiz_cycle(admin_user.id)
        check("5. create: the new event becomes the effective quiz date, cycles "
              "recalculated (BCS-501 cycle 1 = 08-20; window ends 08-19; "
              "current-cycle picks 08-20)",
              effective == [(1, date(2026, 8, 20)), (2, date(2026, 8, 27)),
                            (3, date(2026, 9, 17)), (4, date(2026, 10, 12))]
              and result.quiz_date == date(2026, 8, 20)
              and result.window_end == date(2026, 8, 19)
              and cc["quiz_cycle"] == 1 and cc["quiz_date"] == date(2026, 8, 20)
              and cc["basis"] == "next_upcoming",
              f"effective={effective} quiz_date={result.quiz_date} cc={cc}")

        bnc501_effective = await repo.get_effective_quiz_dates_for_subject(bnc501_id)
        bnc501_result = await service.get_quiz_eligibility(
            admin_user.id, bnc501_id, 1, semester_start=semester_start)
        check("6. only the affected subject changes (BNC-501 untouched)",
              bnc501_effective == [(1, date(2026, 8, 24)), (2, date(2026, 9, 14)), (3, date(2026, 10, 9))]
              and bnc501_result.quiz_date == date(2026, 8, 24),
              f"BNC-501={bnc501_effective} quiz_date={bnc501_result.quiz_date}")
        await db.rollback()

    # ---------------------------------------- 3. Dedup (rollback transaction)
    async with AsyncSessionLocal() as db:
        repo = QuizRepository(db)
        db.add(AcademicEvent(
            event_type=EventType.QUIZ_DAY,
            start_date=date(2026, 9, 17),
            end_date=date(2026, 9, 18),
            subject_id=bcs501_id,
            active=True,
        ))
        await db.flush()
        effective = await repo.get_effective_quiz_dates_for_subject(bcs501_id)
        check("7. partial duplicate (same subject/date, wider range) collapses to "
              "ONE effective quiz date (still 08-27, 09-17, 10-12)",
              effective == [(1, date(2026, 8, 27)), (2, date(2026, 9, 17)), (3, date(2026, 10, 12))],
              f"effective={effective}")
        await db.rollback()

    # ---------------------------------------- 4. Reschedule (rollback transaction)
    async with AsyncSessionLocal() as db:
        service = EligibilityService(db)
        repo = QuizRepository(db)
        q2_event = (await db.execute(
            select(AcademicEvent).where(
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.active.is_(True),
                AcademicEvent.subject_id == bcs501_id,
                AcademicEvent.start_date == date(2026, 9, 17),
            ))).scalars().first()
        q2_event.start_date = date(2026, 9, 16)
        q2_event.end_date = date(2026, 9, 16)
        await db.flush()

        effective = await repo.get_effective_quiz_dates_for_subject(bcs501_id)
        result = await service.get_quiz_eligibility(
            admin_user.id, bcs501_id, 2, semester_start=semester_start)
        check("9. reschedule: no stale date remains; eligibility uses the new date "
              "(BCS-501 cycle 2 = 09-16; window 08-27..09-15)",
              effective == [(1, date(2026, 8, 27)), (2, date(2026, 9, 16)), (3, date(2026, 10, 12))]
              and result.quiz_date == date(2026, 9, 16)
              and result.window_start == date(2026, 8, 27)
              and result.window_end == date(2026, 9, 15),
              f"effective={effective} quiz_date={result.quiz_date} "
              f"window={result.window_start}..{result.window_end}")

        bnc501_effective = await repo.get_effective_quiz_dates_for_subject(bnc501_id)
        check("10. only the affected subject changes (BNC-501 untouched)",
              bnc501_effective == [(1, date(2026, 8, 24)), (2, date(2026, 9, 14)), (3, date(2026, 10, 9))],
              f"BNC-501={bnc501_effective}")
        await db.rollback()

    # --------------------------------------- 5. Deactivate (rollback transaction)
    async with AsyncSessionLocal() as db:
        service = EligibilityService(db)
        repo = QuizRepository(db)
        q2_event = (await db.execute(
            select(AcademicEvent).where(
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.active.is_(True),
                AcademicEvent.subject_id == bcs501_id,
                AcademicEvent.start_date == date(2026, 9, 17),
            ))).scalars().first()
        q2_event.active = False
        await db.flush()

        effective = await repo.get_effective_quiz_dates_for_subject(bcs501_id)
        result2 = await service.get_quiz_eligibility(
            admin_user.id, bcs501_id, 2, semester_start=semester_start)
        result3 = await service.get_quiz_eligibility(
            admin_user.id, bcs501_id, 3, semester_start=semester_start)
        check("11. deactivate: the quiz no longer participates (BCS-501 cycle 2 = "
              "10-12; cycle 3 UNRESOLVED; no stale 09-17)",
              effective == [(1, date(2026, 8, 27)), (2, date(2026, 10, 12))]
              and result2.quiz_date == date(2026, 10, 12)
              and result2.window_start == date(2026, 8, 27)
              and result2.window_end == date(2026, 10, 11)
              and result3.state == EligibilityState.UNRESOLVED
              and result3.quiz_date is None,
              f"effective={effective} q2={result2.quiz_date} q3={result3.state}")

        bnc501_effective = await repo.get_effective_quiz_dates_for_subject(bnc501_id)
        check("12. only the affected subject changes (BNC-501 untouched)",
              bnc501_effective == [(1, date(2026, 8, 24)), (2, date(2026, 9, 14)), (3, date(2026, 10, 9))],
              f"BNC-501={bnc501_effective}")
        await db.rollback()

    # ---------------------------------------- 6. Reactivate (rollback transaction)
    async with AsyncSessionLocal() as db:
        service = EligibilityService(db)
        repo = QuizRepository(db)
        q2_event = (await db.execute(
            select(AcademicEvent).where(
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.subject_id == bcs501_id,
                AcademicEvent.start_date == date(2026, 9, 17),
            ))).scalars().first()
        q2_event.active = True
        await db.flush()

        effective = await repo.get_effective_quiz_dates_for_subject(bcs501_id)
        result2 = await service.get_quiz_eligibility(
            admin_user.id, bcs501_id, 2, semester_start=semester_start)
        result3 = await service.get_quiz_eligibility(
            admin_user.id, bcs501_id, 3, semester_start=semester_start)
        check("13. reactivate: the quiz participates again, exactly as before "
              "(cycle 2 = 09-17, cycle 3 = 10-12)",
              effective == [(1, date(2026, 8, 27)), (2, date(2026, 9, 17)), (3, date(2026, 10, 12))]
              and result2.quiz_date == date(2026, 9, 17)
              and result3.quiz_date == date(2026, 10, 12),
              f"effective={effective} q2={result2.quiz_date} q3={result3.quiz_date}")
        await db.rollback()

    # ------------------------------- 7. Option-A intact + 8. Baseline restore
    async with AsyncSessionLocal() as db:
        service = EligibilityService(db)
        repo = QuizRepository(db)
        attendance_repo = AttendanceRepository(db)
        calendar_repo = CalendarRepository(db)
        events = await calendar_repo.get_all_events()

        # Quiz-day-shaped session for BCS-501 Quiz I day (08-27): exactly one,
        # LECTURE, not extra, no timetable linkage, not cancelled.
        quiz_day_sessions = (await db.execute(
            select(ClassSession).where(
                ClassSession.subject_id == bcs501_id,
                ClassSession.date == date(2026, 8, 27),
            ))).scalars().all()
        shaped = [s for s in quiz_day_sessions
                  if s.class_type == ClassType.LECTURE and not s.is_extra
                  and s.timetable_entry_id is None and not s.is_cancelled]
        normal_on_quiz_day = [s for s in quiz_day_sessions if s.timetable_entry_id is not None]

        # Cumulative cycle-2 window contains the 08-27 quiz day: the exclusion
        # must remove exactly the shaped session(s), nothing else. The
        # eligibility result's lecture counts cover the CYCLE window (the
        # cumulative counts are criterion-II-only), so compare against the
        # cycle-window excluded query.
        effective = await repo.get_effective_quiz_dates_for_subject(bcs501_id)
        domain_subject = SubjectSchema(
            code="BCS-501", name="", category="theory",
            quiz_applicable=True, attendance_applicable=True,
            timeline=Timeline(
                commencement_date=semester_start,
                milestones=[Milestone(milestone_id=f"q{cyc}", date=d, type="QUIZ",
                                      metadata={"quizCycle": cyc}) for cyc, d in effective],
            ),
        )
        cycle_window = get_attendance_window(domain_subject, "q2", events, DEFAULT_WEEKENDS)
        cum_window = get_cumulative_attendance_window(domain_subject, "q2", events, DEFAULT_WEEKENDS)
        raw_all = await attendance_repo.get_subject_counts_between(
            admin_user.id, bcs501_id, cum_window["window_start"], cum_window["window_end"],
            exclude_quiz_day=False)
        raw_excl = await attendance_repo.get_subject_counts_between(
            admin_user.id, bcs501_id, cum_window["window_start"], cum_window["window_end"],
            exclude_quiz_day=True)
        raw_cycle_excl = await attendance_repo.get_subject_counts_between(
            admin_user.id, bcs501_id, cycle_window["window_start"], cycle_window["window_end"],
            exclude_quiz_day=True)
        diff_lecture = aggregate(raw_all)['L']['tot'] - aggregate(raw_excl)['L']['tot']
        result2 = await service.get_quiz_eligibility(
            admin_user.id, bcs501_id, 2, semester_start=semester_start)
        check("14. Option-A intact: the quiz-day-shaped session exists and is "
              "excluded from L/T counts; normal timetable sessions stay included",
              len(shaped) == 1 and len(normal_on_quiz_day) == 1
              and diff_lecture == 1
              and result2.lecture.total == aggregate(raw_cycle_excl)['L']['tot']
              and result2.lecture.total > 0,
              f"shaped={len(shaped)} normal={len(normal_on_quiz_day)} "
              f"diff_L={diff_lecture} cycle_excl_L={aggregate(raw_cycle_excl)['L']['tot']} "
              f"elig_L={result2.lecture.total}")

    async with AsyncSessionLocal() as db:
        events_after = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
        sessions_after = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
        cancelled_after = (await db.execute(
            select(func.count()).select_from(ClassSession).where(ClassSession.is_cancelled.is_(True)))).scalar()
        extra_after = (await db.execute(
            select(func.count()).select_from(ClassSession).where(ClassSession.is_extra.is_(True)))).scalar()
        records_after = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
        enrollments_after = (await db.execute(select(func.count()).select_from(StudentEnrollment))).scalar()
        subjects_after = (await db.execute(select(func.count()).select_from(Subject))).scalar()
        quizzes_after = (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar()
        users_after = (await db.execute(select(func.count()).select_from(User))).scalar()
        quiz_events_after = (await db.execute(
            select(func.count()).select_from(AcademicEvent).where(
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.active.is_(True)))).scalar()
        scheduled_after = (await db.execute(
            select(func.count()).select_from(QuizSchedule).where(
                QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED))).scalar()
        event_pairs = {(e.subject_id, e.start_date) for e in (
            await db.execute(select(AcademicEvent).where(
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.active.is_(True)))).scalars().all()}
        schedule_pairs = {(s.subject_id, s.date) for s in (
            await db.execute(select(QuizSchedule).where(
                QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED,
                QuizSchedule.date.is_not(None)))).scalars().all()}

    check("15. database restored to the exact baseline (no residue; projection "
          "still matches the 18 active quiz events 1:1)",
          (events_before, sessions_before, cancelled_before, extra_before,
           records_before, enrollments_before, subjects_before,
           quizzes_before, users_before)
          == (events_after, sessions_after, cancelled_after, extra_after,
              records_after, enrollments_after, subjects_after,
              quizzes_after, users_after)
          and quiz_events_before == quiz_events_after == scheduled_before == scheduled_after
          and quiz_events_before == 18
          and event_pairs == schedule_pairs,
          f"events {events_before}->{events_after}, sessions {sessions_before}->{sessions_after}, "
          f"records {records_before}->{records_after}, quizzes {quizzes_before}->{quizzes_after}, "
          f"users {users_before}->{users_after}, quiz_events {quiz_events_before}->{quiz_events_after}, "
          f"scheduled {scheduled_before}->{scheduled_after}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))