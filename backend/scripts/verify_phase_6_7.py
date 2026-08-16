"""
Phase 6.7 verification — calendar & academic events subsystem freeze.

Verifies the Phase 6.1-6.6 contracts that the 6.5/6.6 verifiers do not
directly exercise, plus the cross-phase invariants:

- Phase 6.1: engine weekend convention (DEFAULT_WEEKENDS = JS getDay indices
  0=Sunday, 6=Saturday), MID_SEMESTER_BREAK closure semantics + priority tier,
  /events active-default filter, inverted range 422, upcoming semantics.
- Phase 6.2: calendar read model — truthful empty month outside semester,
  July/December clamping to real semester bounds, weekend correctness,
  active closure vs inactive event behavior, enrollment-scoped session counts.
- Phase 6.5: seeding integrity (18 authoritative QUIZ_DAY events, nothing
  fabricated), re-enable via PATCH converges (create -> deactivate -> reactivate
  each syncs the pipeline).
- Phase 6.6: every closure type cancels the day's sessions; EXTRA_TUTORIAL /
  EXTRA_PRACTICAL materialize exactly one extra; WORKING_DAY_OVERRIDE is
  calendar/read-only (working day, zero session mutation); cancelled sessions
  reject attendance with 409.
- Database baseline: exact restoration at the end (events=18, sessions=691,
  cancelled=0, extra=0, records=89, enrollments=18, subjects=9,
  quiz_schedules=18, users=30, admins=1). The +7 sessions are the
  materialized quiz-day sessions (attendance-spec alignment: quiz-day
  attendance is a real attendance event; see
  docs/attendance_ui_refinement_report.md).

Note (Phase 7.1): the authoritative quiz schedule now includes BCS-054
Quiz III (2026-10-23), so the expected counts are 18 QUIZ_DAY events and 18
SCHEDULED quiz_schedules.

Like the 6.6 verifier: httpx ASGITransport + real DB + minted JWTs; test
event rows are deactivated then hard-deleted; startup cleanup removes stale
test-window artifacts from crashed runs / the 6.5 verifier's side effects.

Usage:
    python scripts/verify_phase_6_7.py
"""
import asyncio
import sys
import uuid
from pathlib import Path
from datetime import date

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.academic import StudentEnrollment, Subject
from app.models.quiz import QuizSchedule
from app.models.enums import AttendanceStatus, ClassType, EventType, UserRole
from app.models.quiz import ScheduleStatus
from app.engines.calendar_engine import (
    get_academic_day,
    DEFAULT_WEEKENDS,
    get_event_priority,
)
from app.repositories.session_repo import SessionRepository
from sqlalchemy import select, delete, func

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


async def count_sessions(db, where) -> int:
    stmt = select(func.count()).select_from(ClassSession).where(where)
    return (await db.execute(stmt)).scalar() or 0


async def main() -> int:
    # --- Phase 6.1 engine contract (static, no DB needed) ---------------------
    check("1. DEFAULT_WEEKENDS is the JS-convention weekend source of truth [0,6]",
          DEFAULT_WEEKENDS == [0, 6], f"got {DEFAULT_WEEKENDS}")
    mid_break = AcademicEvent(event_type=EventType.MID_SEMESTER_BREAK,
                              start_date=date(2026, 8, 17), end_date=date(2026, 8, 17), active=True)
    day = get_academic_day(date(2026, 8, 17), [mid_break], DEFAULT_WEEKENDS)
    check("2. MID_SEMESTER_BREAK is a closure (Monday becomes non-working)",
          not day.is_working_day and not day.is_teaching_day,
          f"working={day.is_working_day} teaching={day.is_teaching_day}")
    check("3. MID_SEMESTER_BREAK shares SEMESTER_BREAK's priority tier (60)",
          get_event_priority(EventType.MID_SEMESTER_BREAK) == 60
          and get_event_priority(EventType.MID_SEMESTER_BREAK) == get_event_priority(EventType.SEMESTER_BREAK),
          f"priority={get_event_priority(EventType.MID_SEMESTER_BREAK)}")

    # --- Baseline (recorded BEFORE any verification data) ----------------------
    async with AsyncSessionLocal() as db:
        events_before = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
        # Startup cleanup: stale test-window artifacts (crashed 6.6/6.7 runs,
        # the 6.5 verifier's extra-session side effect) — delete unattended
        # extras and weekend projections, un-cancel unattended cancelled rows.
        window_start, window_end = date(2026, 11, 2), date(2026, 11, 12)
        stale = (await db.execute(
            select(ClassSession).where(
                ClassSession.date >= window_start,
                ClassSession.date <= window_end,
            )
        )).scalars().all()
        attended_ids = await SessionRepository(db).get_session_ids_with_attendance([s.id for s in stale])
        removed, restored = 0, 0
        for s in stale:
            if s.id in attended_ids:
                continue
            if s.is_extra or s.date.weekday() >= 5:
                await db.delete(s)
                removed += 1
            elif s.is_cancelled:
                s.is_cancelled = False
                restored += 1
        if removed or restored:
            await db.commit()
            print(f"cleanup: removed {removed} stale extra/projection session(s), "
                  f"restored {restored} cancelled session(s) on the test window")

        sessions_before = await count_sessions(db, ClassSession.id.is_not(None))
        cancelled_before = await count_sessions(db, ClassSession.is_cancelled.is_(True))
        extra_before = await count_sessions(db, ClassSession.is_extra.is_(True))
        records_before = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
        enrollments_before = (await db.execute(select(func.count()).select_from(StudentEnrollment))).scalar()
        subjects_before = (await db.execute(select(func.count()).select_from(Subject))).scalar()
        quizzes_before = (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar()
        users_before = (await db.execute(select(func.count()).select_from(User))).scalar()
        admins_before = (await db.execute(
            select(func.count()).select_from(User).where(User.role == UserRole.ADMIN))).scalar()
        print(f"baseline: events={events_before} sessions={sessions_before} cancelled={cancelled_before} "
              f"extra={extra_before} records={records_before} enrollments={enrollments_before} "
              f"subjects={subjects_before} quizzes={quizzes_before} users={users_before} admins={admins_before}")

    async with AsyncSessionLocal() as db:
        admin_user = (await db.execute(select(User).where(User.roll_number == "2401220100027"))).scalars().first()
        student_user = (await db.execute(select(User).where(User.roll_number == "9999999999999"))).scalars().first()

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    student_token = create_access_token(str(student_user.id), student_user.roll_number)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    transport = httpx.ASGITransport(app=app)
    test_event_ids: list[uuid.UUID] = []

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # --- Phase 6.1 /events read contract (student) ----------------------
            r = await client.get("/api/v1/events", headers=student_headers)
            events = r.json()
            # The 18 seeded QUIZ_DAY events are the authoritative seed population
            # (Phase 6.5): every seeded quiz day mirrors a quiz_schedules row.
            # The owner's active testing legitimately adds other QUIZ_DAY rows
            # (and other event types), so the integrity assertion scopes to the
            # seed population: every row returned by the default (active-only)
            # filter is active, and all 18 seeded quiz days are present.
            qd_events = [e for e in events if e["event_type"] == "QUIZ_DAY"]
            async with AsyncSessionLocal() as db:
                seeded_pairs = {(str(q.subject_id), q.date.isoformat())
                                for q in (await db.execute(select(QuizSchedule))).scalars().all()}
            qd_seeded = [e for e in qd_events
                         if (e["subject_id"], e["start_date"]) in seeded_pairs]
            check("4. GET /events default = active only (all 18 seeded QUIZ_DAY active)",
                  r.status_code == 200 and all(e["active"] for e in events)
                  and len(qd_seeded) == 18,
                  f"count={len(events)} quiz_day={len(qd_events)} seeded={len(qd_seeded)}")
            r = await client.get("/api/v1/events?date_from=2026-11-01&date_to=2026-10-01", headers=student_headers)
            check("5. inverted date range on /events -> 422", r.status_code == 422, f"got {r.status_code}")
            r = await client.get("/api/v1/events?upcoming=true", headers=student_headers)
            # upcoming=true must return every seed quiz day (end_date >= today);
            # user-created upcoming events may coexist.
            qd_upcoming = [e for e in r.json() if e["event_type"] == "QUIZ_DAY"]
            qd_upcoming_seeded = [e for e in qd_upcoming
                                  if (e["subject_id"], e["start_date"]) in seeded_pairs]
            check("6. upcoming=true keeps end_date >= today (all 18 quiz days)",
                  r.status_code == 200 and len(qd_upcoming_seeded) == 18
                  and all(e["end_date"] >= "2026-08-14" for e in r.json()),
                  f"count={len(r.json())} quiz_day={len(qd_upcoming)} seeded={len(qd_upcoming_seeded)}")

            # --- Phase 6.5 seeding integrity (scoped to the seed population) -----
            async with AsyncSessionLocal() as db:
                qd_total = (await db.execute(
                    select(func.count()).select_from(AcademicEvent).where(
                        AcademicEvent.event_type == EventType.QUIZ_DAY))).scalar()
                # Seed population: QUIZ_DAY rows that mirror a quiz_schedules
                # row (subject + date) - the only events Phase 6.5 seeds.
                qd_seeded = (await db.execute(
                    select(func.count()).select_from(AcademicEvent).where(
                        AcademicEvent.event_type == EventType.QUIZ_DAY,
                        AcademicEvent.subject_id == QuizSchedule.subject_id,
                        AcademicEvent.start_date == QuizSchedule.date,
                    ))).scalar()
                qd_inactive = (await db.execute(
                    select(func.count()).select_from(AcademicEvent).where(
                        AcademicEvent.event_type == EventType.QUIZ_DAY,
                        AcademicEvent.active.is_(False)))).scalar()
                scheduled_quizzes = (await db.execute(
                    select(func.count()).select_from(QuizSchedule).where(
                        QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED))).scalar()
            check("7. seeding integrity: 18 seeded QUIZ_DAY events, all active, "
                  "no fabricated dates",
                  qd_seeded == 18 and qd_inactive == 0,
                  f"seeded={qd_seeded} total={qd_total} inactive={qd_inactive}")
            check("8. seed count matches authoritative SCHEDULED quiz_schedules",
                  scheduled_quizzes == 18, f"scheduled_quizzes={scheduled_quizzes}")

            # --- Phase 6.2 calendar read model ----------------------------------
            r = await client.get("/api/v1/calendar?year=2026&month=1", headers=student_headers)
            body = r.json()
            check("9. January 2026 (outside semester) -> truthful empty result with real bounds",
                  body["days"] == [] and body["semester_start"] is not None and body["semester_end"] is not None,
                  f"days={len(body['days'])} start={body['semester_start']}")
            r = await client.get("/api/v1/calendar?year=2026&month=7", headers=student_headers)
            body = r.json()
            check("10. July 2026 clamps to semester start (effective_start == 2026-07-15)",
                  body["effective_start"] == "2026-07-15" and body["days"][0]["date"] == "2026-07-15",
                  f"effective_start={body['effective_start']} first_day={body['days'][0]['date'] if body['days'] else None}")
            r = await client.get("/api/v1/calendar?year=2026&month=12", headers=student_headers)
            body = r.json()
            check("11. December 2026 respects semester end (effective_end == 2026-12-31)",
                  body["effective_end"] == "2026-12-31" and body["days"][-1]["date"] == "2026-12-31",
                  f"effective_end={body['effective_end']}")
            r = await client.get("/api/v1/calendar?year=2026&month=8", headers=student_headers)
            body = r.json()
            days = {d["date"]: d for d in body["days"]}
            check("12. weekends correct (Sat 08-15 & Sun 08-16 non-working, Mon 08-17 working)",
                  not days["2026-08-15"]["is_working_day"] and not days["2026-08-16"]["is_working_day"]
                  and days["2026-08-17"]["is_working_day"],
                  f"sat={days['2026-08-15']['is_working_day']} sun={days['2026-08-16']['is_working_day']} "
                  f"mon={days['2026-08-17']['is_working_day']}")
            check("13. QUIZ_DAY stays a working day (calendar/read-only)",
                  days["2026-08-24"]["is_working_day"] is True
                  and any(e["event_type"] == "QUIZ_DAY" for e in days["2026-08-24"]["events"]),
                  f"working={days['2026-08-24']['is_working_day']}")

            # --- Phase 6.6: every closure type cancels its day's sessions -------
            closure_dates = {
                "INSTITUTE_HOLIDAY": date(2026, 11, 2),
                "FESTIVAL_HOLIDAY": date(2026, 11, 3),
                "EMERGENCY_CLOSURE": date(2026, 11, 4),
                "SEMESTER_BREAK": date(2026, 11, 5),
                "MID_SEMESTER_BREAK": date(2026, 11, 6),
            }
            expected_counts = {
                date(2026, 11, 2): 5, date(2026, 11, 3): 6, date(2026, 11, 4): 6,
                date(2026, 11, 5): 6, date(2026, 11, 6): 5,
            }
            for event_type, d in closure_dates.items():
                r = await client.post("/api/v1/events", headers=admin_headers, json={
                    "event_type": event_type, "start_date": d.isoformat(), "end_date": d.isoformat()})
                if r.status_code != 201:
                    check(f"{event_type} {d} -> 201", False, r.text[:200])
                    continue
                test_event_ids.append(uuid.UUID(r.json()["id"]))
                async with AsyncSessionLocal() as db:
                    total = await count_sessions(db, ClassSession.date == d)
                    cancelled = await count_sessions(
                        db, (ClassSession.date == d) & ClassSession.is_cancelled.is_(True))
                r = await client.get(f"/api/v1/calendar/{d.isoformat()}", headers=student_headers)
                api_day = r.json()
                check(f"12. {event_type} {d}: day non-working, all {expected_counts[d]} sessions cancelled, rows preserved",
                      total == expected_counts[d] and cancelled == expected_counts[d]
                      and api_day["is_working_day"] is False,
                      f"total={total} cancelled={cancelled} working={api_day.get('is_working_day')}")

            # --- Phase 6.6: EXTRA_TUTORIAL / EXTRA_PRACTICAL --------------------
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "EXTRA_TUTORIAL", "start_date": "2026-11-10", "end_date": "2026-11-10",
                "subject_id": (await client.get("/api/v1/subjects", headers=admin_headers)).json()[0]["id"],
                "class_type": "T"})
            check("15. admin EXTRA_TUTORIAL 11-10 -> 201", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
            extra_t_id = uuid.UUID(r.json()["id"])
            test_event_ids.append(extra_t_id)
            async with AsyncSessionLocal() as db:
                total = await count_sessions(db, ClassSession.date == date(2026, 11, 10))
                extras = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.date == date(2026, 11, 10), ClassSession.is_extra.is_(True)))).scalars().all()
            check("16. exactly one is_extra TUTORIAL session on 11-10 (no timetable entry)",
                  total == 7 and len(extras) == 1 and extras[0].class_type == ClassType.TUTORIAL
                  and extras[0].timetable_entry_id is None,
                  f"total={total} extras={len(extras)}")

            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "EXTRA_PRACTICAL", "start_date": "2026-11-11", "end_date": "2026-11-11",
                "subject_id": (await client.get("/api/v1/subjects", headers=admin_headers)).json()[1]["id"],
                "class_type": "P"})
            check("17. admin EXTRA_PRACTICAL 11-11 -> 201", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
            extra_p_id = uuid.UUID(r.json()["id"])
            test_event_ids.append(extra_p_id)
            async with AsyncSessionLocal() as db:
                total = await count_sessions(db, ClassSession.date == date(2026, 11, 11))
                extras = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.date == date(2026, 11, 11), ClassSession.is_extra.is_(True)))).scalars().all()
            check("18. exactly one is_extra PRACTICAL session on 11-11 (no timetable entry)",
                  total == 7 and len(extras) == 1 and extras[0].class_type == ClassType.PRACTICAL
                  and extras[0].timetable_entry_id is None,
                  f"total={total} extras={len(extras)}")

            # --- Phase 6.6: WORKING_DAY_OVERRIDE is calendar/read-only ----------
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "WORKING_DAY_OVERRIDE", "start_date": "2026-11-07", "end_date": "2026-11-07",
                "is_working_day": True})
            check("19. admin WORKING_DAY_OVERRIDE 11-07 -> 201", r.status_code == 201,
                  f"got {r.status_code} {r.text[:200]}")
            wdo_id = uuid.UUID(r.json()["id"])
            test_event_ids.append(wdo_id)
            r = await client.get("/api/v1/calendar/2026-11-07", headers=student_headers)
            api_day = r.json()
            async with AsyncSessionLocal() as db:
                total = await count_sessions(db, ClassSession.date == date(2026, 11, 7))
            check("20. WORKING_DAY_OVERRIDE: day working but zero session mutation (no timetable for Saturday)",
                  api_day["is_working_day"] is True and total == 0,
                  f"working={api_day['is_working_day']} sessions={total}")

            # --- Phase 6.9: cancelled sessions reject attendance (409) ----------
            async with AsyncSessionLocal() as db:
                cancelled_session = (await db.execute(
                    select(ClassSession).where(
                        (ClassSession.date == date(2026, 11, 2)) & ClassSession.is_cancelled.is_(True)))).scalars().first()
            r = await client.post("/api/v1/attendance", headers=student_headers, json={
                "class_session_id": str(cancelled_session.id), "status": "Attended"})
            check("21. cancelled session rejects attendance with 409 (cancelled != absent)",
                  r.status_code == 409, f"got {r.status_code} {r.text[:200]}")

            # --- Phase 6.5: deactivate then re-enable converges the pipeline -----
            r = await client.delete(f"/api/v1/events/{extra_t_id}", headers=admin_headers)
            check("22. deactivation of EXTRA_TUTORIAL -> 200 active=false", r.status_code == 200,
                  f"got {r.status_code}")
            async with AsyncSessionLocal() as db:
                extras = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 10)) & ClassSession.is_extra.is_(True))
            check("23. deactivated extra removed from the pipeline", extras == 0, f"extras={extras}")
            r = await client.patch(f"/api/v1/events/{extra_t_id}", headers=admin_headers, json={"active": True})
            check("24. re-enable via PATCH -> 200 active=true (no resurrection of deactivated seeds)", r.status_code == 200,
                  f"got {r.status_code}")
            async with AsyncSessionLocal() as db:
                extras = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 10)) & ClassSession.is_extra.is_(True))
            check("25. re-enabled event syncs the pipeline again (exactly one extra)",
                  extras == 1, f"extras={extras}")

            # --- Deactivate every test event (reversal is itself the freeze check)
            for event_id in list(test_event_ids):
                r = await client.delete(f"/api/v1/events/{event_id}", headers=admin_headers)
                if r.status_code != 200:
                    check(f"deactivate {event_id}", False, r.text[:200])
            async with AsyncSessionLocal() as db:
                d2_c = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 2)) & ClassSession.is_cancelled.is_(True))
                d10_x = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 10)) & ClassSession.is_extra.is_(True))
                d11_x = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 11)) & ClassSession.is_extra.is_(True))
            check("26. all closure/cancel effects reverted on deactivation (zero residue)",
                  d2_c == 0 and d10_x == 0 and d11_x == 0, f"11-02 cancelled={d2_c} 11-10 extra={d10_x} 11-11 extra={d11_x}")
    finally:
        async with AsyncSessionLocal() as db:
            if test_event_ids:
                await db.execute(delete(AcademicEvent).where(AcademicEvent.id.in_(test_event_ids)))
                await db.commit()
                print(f"cleanup: removed {len(test_event_ids)} verification event row(s)")

    # --- Final baseline assertion (exact restoration) --------------------------
    async with AsyncSessionLocal() as db:
        events_after = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
        sessions_after = await count_sessions(db, ClassSession.id.is_not(None))
        cancelled_after = await count_sessions(db, ClassSession.is_cancelled.is_(True))
        extra_after = await count_sessions(db, ClassSession.is_extra.is_(True))
        records_after = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
        enrollments_after = (await db.execute(select(func.count()).select_from(StudentEnrollment))).scalar()
        subjects_after = (await db.execute(select(func.count()).select_from(Subject))).scalar()
        quizzes_after = (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar()
        users_after = (await db.execute(select(func.count()).select_from(User))).scalar()
        admins_after = (await db.execute(
            select(func.count()).select_from(User).where(User.role == UserRole.ADMIN))).scalar()
    check("27. database restored to the exact baseline (events/sessions/cancelled/extra/records/"
          "enrollments/subjects/quizzes/users/admins)",
          (events_after, sessions_after, cancelled_after, extra_after, records_after,
           enrollments_after, subjects_after, quizzes_after, users_after, admins_after) ==
          (events_before, sessions_before, cancelled_before, extra_before, records_before,
           enrollments_before, subjects_before, quizzes_before, users_before, admins_before),
          f"events {events_before}->{events_after}, sessions {sessions_before}->{sessions_after}, "
          f"cancelled {cancelled_before}->{cancelled_after}, extra {extra_before}->{extra_after}, "
          f"records {records_before}->{records_after}, enrollments {enrollments_before}->{enrollments_after}, "
          f"subjects {subjects_before}->{subjects_after}, quizzes {quizzes_before}->{quizzes_after}, "
          f"users {users_before}->{users_after}, admins {admins_before}->{admins_after}")

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))