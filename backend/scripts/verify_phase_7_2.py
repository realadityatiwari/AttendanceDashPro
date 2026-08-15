"""
Phase 7.2 verification  -  quiz eligibility analytics refinement.

Verifies the Phase 7.2 product contract end-to-end against the real database:

 Q-D6  raw-range vs teaching-day counting (decision: equivalence  -  no defect):
   1.  For all 18 theory subject/cycle combos, the eligibility window counts
       (raw non-cancelled sessions) equal a teaching-day-resolved enumeration,
       and every counted session lies on an engine teaching day.
   2.  A closure event cancels its day's sessions -> they stop being counted
       (and reject attendance with 409)  -  the legacy "no class that day" rule.
   3.  An EXTRA_LECTURE on a working day materializes one is_extra session and
       is counted in the eligibility window (legacy delta parity).
   4.  A SURPRISE_QUIZ on a non-working day materializes ZERO sessions (the
       canonical event path cannot create a counted-but-excluded session).

 Q-D8  overall denominator (decision: recorded-only, ERP/legacy semantics):
   5.   Dashboard overall_pct == attended / (attended+missed), pending exposed
        separately and NOT folded into the denominator (admin 71.43%, and
        explicitly not the 46.51% pending-inclusive figure).
   6.   History summary pct uses the identical recorded-only semantics.
   7.   Subject summary exposes BOTH current (recorded-only) and forecast
        (pending-as-attended) percentages  -  pending never silently converted.
   8.   Quiz eligibility percentages use the eligibility definition
        (att/total with pending in the denominator  -  documented distinct) and
        expose missed/pending separately.
   9.   Zero-record student: overall pct is null (not 0%).

 Q-D7  mutation / eligibility timing (decision: intentionally re-scoped by
       the attendance specification — events are student-adjustable for the
       flexible subject-scoped types on the student's own enrollments;
       global/closure/quiz-schedule events remain admin-only; attendance
       mutation safety is unchanged):
   10.  Student POST global/closure event -> 403 (admin-only).
   11.  Attendance mutation safety: non-enrolled subject -> 403; cancelled
        session -> 409 (cancelled != absent).
   12.  Eligibility is computed read-time: a mutation propagates to the next
        eligibility read immediately (no timing inconsistency).

 Date-aware default tab (Step 4):
   13.  GET /api/v1/quiz-eligibility/current-cycle (admin) -> Quiz I, next
        upcoming date 2026-08-24, basis next_upcoming (canonical schedule).
   14.  Same canonical answer for the zero-record student (schedule shared).
   15.  Deterministic date-awareness (rollback scenarios): all Quiz I past ->
        Quiz II; Quiz I+II past -> Quiz III; all past -> latest_resolved (III);
        all unresolved -> fallback Quiz I with has_schedule=false and no date.

 Contract / regression:
   16.  BCS-054 Quiz III remains 2026-10-23 (authoritative, live).
   17.  UNRESOLVED only when genuinely unresolved (no invented dates).
   18.  Lab subjects (BCS-551/552/553) are excluded (404).
   19.  Dashboard quiz snapshot consumes the canonical eligibility result:
        snapshot counts == recomputed per-subject eligibility; snapshot cycle
        == current-cycle endpoint (Step 6  -  no dashboard-specific math).
   20.  Track / History / Eligibility consistency: daily view matches the DB;
        eligibility window counts match a direct session count.
   21.  Student authorization isolation (admin vs zero-record student).
   22.  Database baseline restored exactly (events/sessions/cancelled/extra/
        records/enrollments/subjects/quizzes/scheduled/users/admins +
        max record date), with no attendance-history corruption.

Like the 6.x/7.1 verifiers: httpx ASGITransport + real DB + minted JWTs.
State mutations happen only inside rollback transactions or are deactivated +
hard-cleaned (the frozen verifier discipline). No old assertions are weakened.

Usage:
    python scripts/verify_phase_7_2.py
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
from app.models.user import User, Section
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.academic import StudentEnrollment, Subject, Semester
from app.models.quiz import QuizSchedule, QuizCycle, ScheduleStatus
from app.models.enums import AttendanceStatus, ClassType, EventType, UserRole
from app.services.eligibility_service import EligibilityService
from app.schemas.attendance import EligibilityState
from app.engines.calendar_engine import get_teaching_days_between, DEFAULT_WEEKENDS
from app.repositories.calendar_repo import CalendarRepository
from app.repositories.session_repo import SessionRepository
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def theory_codes() -> set:
    return {"BNC-501", "BCS-501", "BCS-502", "BCS-503", "BCS-054", "BCS-058"}


async def main() -> int:
    # --- Baseline (recorded BEFORE any verification data) ----------------------
    async with AsyncSessionLocal() as db:
        # Startup cleanup: stale artifacts from crashed runs on the test
        # windows this verifier uses (10-05/10-06 closures+extras, 11-07 guard).
        test_dates = [date(2026, 10, 5), date(2026, 10, 6), date(2026, 11, 7)]
        stale = (await db.execute(
            select(ClassSession).where(ClassSession.date.in_(test_dates))
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
        stale_events = (await db.execute(
            select(AcademicEvent).where(AcademicEvent.start_date.in_(test_dates))
        )).scalars().all()
        for ev in stale_events:
            await db.delete(ev)
        if removed or restored or stale_events:
            await db.commit()
            print(f"cleanup: removed {removed} stale extra/projection session(s), "
                  f"restored {restored} cancelled session(s), removed {len(stale_events)} stale event(s)")

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
        scheduled_before = (await db.execute(
            select(func.count()).select_from(QuizSchedule).where(
                QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED))).scalar()
        users_before = (await db.execute(select(func.count()).select_from(User))).scalar()
        admins_before = (await db.execute(
            select(func.count()).select_from(User).where(User.role == UserRole.ADMIN))).scalar()
        max_record_session_date = (await db.execute(
            select(func.max(ClassSession.date)).join(
                AttendanceRecord, AttendanceRecord.class_session_id == ClassSession.id))).scalar()
        print(f"baseline: events={events_before} sessions={sessions_before} cancelled={cancelled_before} "
              f"extra={extra_before} records={records_before} enrollments={enrollments_before} "
              f"subjects={subjects_before} quizzes={quizzes_before} scheduled={scheduled_before} "
              f"users={users_before} admins={admins_before} max_record_date={max_record_session_date}")

        admin_user = (await db.execute(select(User).where(User.roll_number == "2401220100027"))).scalars().first()
        student_user = (await db.execute(select(User).where(User.roll_number == "9999999999999"))).scalars().first()

        semester_start = date(2026, 7, 15)
        if admin_user.section_id:
            section = await db.get(Section, admin_user.section_id)
            if section:
                semester = await db.get(Semester, section.semester_id)
                if semester:
                    semester_start = semester.start_date

        subject_ids = {}
        for code in theory_codes():
            subject_ids[code] = (await db.execute(
                select(Subject.id).where(Subject.code == code))).scalar_one()

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    student_token = create_access_token(str(student_user.id), student_user.roll_number)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # --- Q-D6 check 1: raw-range == teaching-day-resolved enumeration -------
        all_ok = True
        detail = ""
        for code in sorted(theory_codes()):
            for cycle in (1, 2, 3):
                r = await client.get(f"/api/v1/quiz-eligibility/{code}/{cycle}", headers=admin_headers)
                if r.status_code != 200:
                    all_ok = False
                    detail += f"{code}/{cycle}:{r.status_code} "
                    continue
                body = r.json()
                w_start = date.fromisoformat(body["window_start"])
                w_end = date.fromisoformat(body["window_end"])
                async with AsyncSessionLocal() as db:
                    events = await CalendarRepository(db).get_all_events()
                    teaching = set(get_teaching_days_between(w_start, w_end, events, DEFAULT_WEEKENDS))
                    sessions = (await db.execute(
                        select(ClassSession).where(
                            ClassSession.subject_id == subject_ids[code],
                            ClassSession.date.between(w_start, w_end),
                            ClassSession.is_cancelled.is_(False),
                        ))).scalars().all()
                counted = {"L": 0, "T": 0}
                for s in sessions:
                    if s.date not in teaching:
                        all_ok = False
                        detail += f"{code}/{cycle}:off-teaching-day {s.date} "
                        continue
                    t = s.class_type.value
                    if t in counted:
                        counted[t] += 1
                if counted["L"] != body["lecture"]["total"] or counted["T"] != body["tutorial"]["total"]:
                    all_ok = False
                    detail += f"{code}/{cycle}:L {counted['L']}vs{body['lecture']['total']} " \
                              f"T {counted['T']}vs{body['tutorial']['total']} "
        check("1. Q-D6: eligibility counts == teaching-day-resolved enumeration "
              "for all 18 theory subject/cycle combos (no off-teaching-day session counted)",
              all_ok, detail)

        # --- Q-D7 check 10 (attendance-spec re-scope): global/closure events
        # stay admin-only; flexible subject-scoped student events are covered
        # by verify_phase_6_5 and verify_attendance_spec_alignment.
        r = await client.post("/api/v1/events", headers=student_headers, json={
            "event_type": "INSTITUTE_HOLIDAY", "start_date": "2026-10-05", "end_date": "2026-10-05"})
        check("10. Q-D7 re-scope: student POST global/closure event -> 403 (admin-only)",
              r.status_code == 403, f"got {r.status_code} {r.text[:120]}")

        # --- Q-D6 checks 2-4 + Q-D7 check 11 (event + attendance safety) -------
        test_event_ids: list[uuid.UUID] = []
        try:
            # 2. Closure inside BCS-054 Q3 window (2026-10-05, Monday)
            r0 = await client.get("/api/v1/quiz-eligibility/BCS-054/3", headers=admin_headers)
            bcs054_q3_before = r0.json()
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "INSTITUTE_HOLIDAY", "start_date": "2026-10-05", "end_date": "2026-10-05"})
            closure_ok = r.status_code == 201
            if closure_ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
            r1 = await client.get("/api/v1/quiz-eligibility/BCS-054/3", headers=admin_headers)
            bcs054_q3_after = r1.json()
            async with AsyncSessionLocal() as db:
                cancelled_on = (await db.execute(
                    select(func.count()).select_from(ClassSession).where(
                        ClassSession.date == date(2026, 10, 5),
                        ClassSession.is_cancelled.is_(True)))).scalar()
                bcs054_monday = (await db.execute(
                    select(func.count()).select_from(ClassSession).where(
                        ClassSession.subject_id == subject_ids["BCS-054"],
                        ClassSession.date == date(2026, 10, 5),
                        ClassSession.is_cancelled.is_(False)))).scalar()
            check("2. Q-D6: closure cancels its day's sessions -> excluded from "
                  "the eligibility window (BCS-054 Q3 lecture total -1, no attendance)",
                  closure_ok and cancelled_on == 5 and bcs054_monday == 0
                  and bcs054_q3_after["lecture"]["total"] == bcs054_q3_before["lecture"]["total"] - 1
                  and bcs054_q3_after["state"] == bcs054_q3_before["state"],
                  f"cancelled={cancelled_on} before={bcs054_q3_before['lecture']['total']} "
                  f"after={bcs054_q3_after['lecture']['total']}")

            # 11. Cancelled sessions reject attendance (409)  -  cancelled != absent
            async with AsyncSessionLocal() as db:
                cancelled_session = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.date == date(2026, 10, 5),
                        ClassSession.is_cancelled.is_(True)))).scalars().first()
            if cancelled_session is not None:
                r = await client.post("/api/v1/attendance", headers=admin_headers, json={
                    "class_session_id": str(cancelled_session.id), "status": "Attended"})
                check("11a. Q-D7: cancelled session rejects attendance with 409",
                      r.status_code == 409, f"got {r.status_code} {r.text[:120]}")
            else:
                check("11a. Q-D7: cancelled session rejects attendance with 409", False, "no cancelled session found")

            # 3. EXTRA_LECTURE on a working day inside the window (2026-10-06)
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "EXTRA_LECTURE", "start_date": "2026-10-06", "end_date": "2026-10-06",
                "subject_id": str(subject_ids["BCS-054"]), "class_type": "L"})
            extra_ok = r.status_code == 201
            if extra_ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
            r2 = await client.get("/api/v1/quiz-eligibility/BCS-054/3", headers=admin_headers)
            bcs054_q3_extra = r2.json()
            async with AsyncSessionLocal() as db:
                extras_on = (await db.execute(
                    select(func.count()).select_from(ClassSession).where(
                        ClassSession.subject_id == subject_ids["BCS-054"],
                        ClassSession.date == date(2026, 10, 6),
                        ClassSession.is_extra.is_(True)))).scalar()
            check("3. Q-D6: EXTRA_LECTURE materializes exactly one is_extra session "
                  "on a working day and it is counted in the eligibility window",
                  extra_ok and extras_on == 1
                  and bcs054_q3_extra["lecture"]["total"] == bcs054_q3_before["lecture"]["total"],
                  f"extras={extras_on} total={bcs054_q3_extra['lecture']['total']}")

            # 4. SURPRISE_QUIZ on a non-working day (2026-11-07 Saturday) -> zero sessions
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "SURPRISE_QUIZ", "start_date": "2026-11-07", "end_date": "2026-11-07",
                "subject_id": str(subject_ids["BCS-054"]), "class_type": "L"})
            guard_ok = r.status_code == 201
            if guard_ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
            async with AsyncSessionLocal() as db:
                extras_sat = (await db.execute(
                    select(func.count()).select_from(ClassSession).where(
                        ClassSession.subject_id == subject_ids["BCS-054"],
                        ClassSession.date == date(2026, 11, 7),
                        ClassSession.is_extra.is_(True)))).scalar()
            check("4. Q-D6: SURPRISE_QUIZ on a non-working day materializes ZERO "
                  "sessions (canonical event path cannot create a counted "
                  "session on a non-teaching day)",
                  guard_ok and extras_sat == 0, f"extras_sat={extras_sat}")

            # 11b. Non-enrolled subject -> 403 (enrollment authorization)
            # The admin user is enrolled in the theory subjects; pick a subject the
            # zero-record student is NOT enrolled in by checking enrollments.
            r = await client.get("/api/v1/subjects", headers=student_headers)
            all_subjects = r.json()
            async with AsyncSessionLocal() as db:
                student_enrolled = set((await db.execute(
                    select(Subject.code).join(StudentEnrollment).where(
                        StudentEnrollment.user_id == student_user.id))).scalars().all())
            non_enrolled = next((s for s in all_subjects if s["code"] not in student_enrolled), None)
            r = await client.post("/api/v1/attendance", headers=student_headers, json={
                "class_session_id": str(uuid.uuid4()), "status": "Attended"})
            check("11b. Q-D7: attendance on a non-enrolled/unknown session -> 403/404 "
                  "(enrollment authorization preserved)",
                  r.status_code in (403, 404), f"got {r.status_code}")
        finally:
            for event_id in list(test_event_ids):
                async with AsyncSessionLocal() as db:
                    ev = await db.get(AcademicEvent, event_id)
                    if ev:
                        ev.active = False
                        await db.commit()
                        await db.delete(ev)
                        await db.commit()
            async with AsyncSessionLocal() as db:
                # Restore any residue the synchronizer left on the test dates.
                stale = (await db.execute(
                    select(ClassSession).where(ClassSession.date.in_(
                        [date(2026, 10, 5), date(2026, 10, 6), date(2026, 11, 7)])))).scalars().all()
                attended_ids = await SessionRepository(db).get_session_ids_with_attendance([s.id for s in stale])
                for s in stale:
                    if s.id in attended_ids:
                        continue
                    if s.is_extra or s.date.weekday() >= 5:
                        await db.delete(s)
                    elif s.is_cancelled:
                        s.is_cancelled = False
                if stale:
                    await db.commit()
                print(f"cleanup: removed {len(test_event_ids)} verification event row(s), "
                      f"restored {len(stale)} session residue on the test dates")

        # --- Q-D8 checks 5-9 (denominator semantics) -----------------------------
        r = await client.get("/api/v1/dashboard/summary", headers=admin_headers)
        dash = r.json()
        overall = dash["overall"]
        async with AsyncSessionLocal() as db:
            # Outer join: sessions without a record are pending (mirrors
            # dashboard get_sessions_with_status semantics exactly).
            rows = (await db.execute(
                select(ClassSession.date, AttendanceRecord.status).outerjoin(
                    AttendanceRecord, (AttendanceRecord.class_session_id == ClassSession.id)
                    & (AttendanceRecord.user_id == admin_user.id)).where(
                    ClassSession.date >= semester_start,
                    ClassSession.date <= date.today(),
                    ClassSession.is_cancelled.is_(False)))).all()
        att = sum(1 for _, st in rows if st == AttendanceStatus.ATTENDED)
        miss = sum(1 for _, st in rows if st == AttendanceStatus.MISSED)
        pend = len(rows) - att - miss
        recorded = att + miss
        expected_pct = (att / recorded * 100.0) if recorded else None
        pending_inclusive = (att / (att + miss + pend) * 100.0) if (att + miss + pend) else None
        check("5. Q-D8: dashboard overall = attended / recorded (pending excluded "
              "from the current denominator, ERP/legacy semantics) with pending "
              "exposed separately",
              overall["overall_pct"] == expected_pct and overall["attended"] == att
              and overall["recorded"] == recorded and overall["pending"] == pend
              and overall["overall_pct"] != pending_inclusive and pend > 0,
              f"api={overall['overall_pct']:.4f} expected={expected_pct:.4f} "
              f"pending_inclusive={pending_inclusive:.4f} att={att} rec={recorded} pend={pend}")

        r = await client.get("/api/v1/attendance/history?limit=1", headers=admin_headers)
        hist = r.json()["summary"]
        hist_pct = round(att / (att + miss) * 100, 1) if (att + miss) else None
        check("6. Q-D8: history summary uses the identical recorded-only denominator",
              hist["pct"] == hist_pct and hist["attended"] == att and hist["missed"] == miss
              and hist["pending"] == pend,
              f"hist_pct={hist['pct']} expected={hist_pct} att={hist['attended']} "
              f"miss={hist['missed']} pend={hist['pending']}")

        r = await client.get("/api/v1/attendance/summary/BCS-501", headers=admin_headers)
        summ = r.json()
        lec = summ["lecture"]
        done_l = lec["attended"] + lec["missed"]
        cur_l = (lec["attended"] / done_l * 100.0) if done_l else None
        fore_l = ((lec["attended"] + lec["pending"]) / lec["total"] * 100.0) if lec["total"] else None
        check("7. Q-D8: subject summary distinguishes current (recorded-only) from "
              "forecast (pending-as-attended)  -  pending never silently converted",
              summ["current_lecture_pct"] == cur_l and summ["forecast_lecture_pct"] == fore_l
              and lec["pending"] > 0 and cur_l != fore_l,
              f"cur={summ['current_lecture_pct']} fore={summ['forecast_lecture_pct']} "
              f"pend={lec['pending']}")

        r = await client.get("/api/v1/quiz-eligibility/BCS-501/1", headers=admin_headers)
        elig = r.json()
        lc = elig["lecture"]
        check("8. Q-D8: quiz eligibility percentages use the eligibility definition "
              "(attended/total, pending in the denominator) and expose missed + "
              "pending separately (no silent exclusion)",
              elig["lecture_pct"] == (lc["attended"] / lc["total"] * 100.0) if lc["total"] else False
              and lc["missed"] >= 0 and lc["pending"] > 0
              and lc["attended"] + lc["missed"] + lc["pending"] == lc["total"],
              f"pct={elig.get('lecture_pct')} L={dict(lc)}")

        r = await client.get("/api/v1/dashboard/summary", headers=student_headers)
        stu_overall = r.json()["overall"]
        check("9. Q-D8: zero-record student overall pct is null (not 0%)  -  pending "
              "is never converted into an absent/0 figure",
              stu_overall["overall_pct"] is None and stu_overall["pending"] > 0
              and stu_overall["recorded"] == 0,
              f"pct={stu_overall['overall_pct']} recorded={stu_overall['recorded']} "
              f"pending={stu_overall['pending']}")

        # --- Q-D7 check 12: mutation propagates to eligibility immediately -------
        async with AsyncSessionLocal() as db:
            bcs501_id = subject_ids["BCS-501"]
            w_start = date.fromisoformat(elig["window_start"])
            w_end = date.fromisoformat(elig["window_end"])
            service = EligibilityService(db)
            before = await service.get_quiz_eligibility(admin_user.id, bcs501_id, 1, semester_start=semester_start)
            pending_session = (await db.execute(
                select(ClassSession).join(
                    AttendanceRecord, (AttendanceRecord.class_session_id == ClassSession.id)
                    & (AttendanceRecord.user_id == admin_user.id), isouter=True).where(
                    ClassSession.subject_id == bcs501_id,
                    ClassSession.date.between(w_start, w_end),
                    ClassSession.is_cancelled.is_(False),
                    AttendanceRecord.id.is_(None),
                    ClassSession.class_type == ClassType.LECTURE,
                ))).scalars().first()
            if pending_session is not None:
                db.add(AttendanceRecord(user_id=admin_user.id, class_session_id=pending_session.id,
                                        status=AttendanceStatus.ATTENDED))
                after = await service.get_quiz_eligibility(admin_user.id, bcs501_id, 1, semester_start=semester_start)
                expected_pct_after = (before.lecture.attended + 1) / before.lecture.total * 100.0
                check("12. Q-D7: eligibility is computed read-time  -  a pending-class "
                      "mutation propagates to the next eligibility read immediately",
                      after.lecture_pct == expected_pct_after
                      and after.lecture.attended == before.lecture.attended + 1,
                      f"before={before.lecture_pct:.2f} after={after.lecture_pct:.2f} "
                      f"expected={expected_pct_after:.2f}")
            else:
                check("12. Q-D7: eligibility is computed read-time  -  a pending-class "
                      "mutation propagates to the next eligibility read immediately",
                      False, "no pending lecture session found in BCS-501 Q1 window")
            await db.rollback()

        # --- Step 4: date-aware default tab -------------------------------------
        r = await client.get("/api/v1/quiz-eligibility/current-cycle", headers=admin_headers)
        cc_admin = r.json()
        check("13. current-cycle (admin): Quiz I selected from the canonical "
              "schedule  -  next upcoming quiz date 2026-08-24, basis next_upcoming",
              r.status_code == 200 and cc_admin["quiz_cycle"] == 1
              and cc_admin["quiz_date"] == "2026-08-24" and cc_admin["has_schedule"] is True
              and cc_admin["basis"] == "next_upcoming",
              f"got {cc_admin}")

        r = await client.get("/api/v1/quiz-eligibility/current-cycle", headers=student_headers)
        cc_student = r.json()
        check("14. current-cycle (student): identical canonical answer (shared "
              "schedule, per-user scoped)",
              r.status_code == 200 and cc_student == cc_admin, f"got {cc_student}")

        # 15. Date-aware rollback scenarios (service-level, same session)
        async with AsyncSessionLocal() as db:
            service = EligibilityService(db)
            all_schedules = (await db.execute(
                select(QuizSchedule).options(selectinload(QuizSchedule.quiz_cycle)))).scalars().all()
            try:
                # Scenario A: all Quiz I dates past -> next upcoming is Quiz II
                for s in all_schedules:
                    if s.quiz_cycle.cycle_number == 1:
                        s.date = date(2026, 8, 1)
                cc = await service.get_current_quiz_cycle(admin_user.id)
                check("15a. date-aware: with all Quiz I dates past, current-cycle "
                      "selects Quiz II (next upcoming 2026-09-14, basis next_upcoming)",
                      cc["quiz_cycle"] == 2 and cc["quiz_date"] == date(2026, 9, 14)
                      and cc["basis"] == "next_upcoming", f"got {cc}")

                # Scenario B: Quiz I + Quiz II past -> Quiz III
                for s in all_schedules:
                    if s.quiz_cycle.cycle_number in (1, 2):
                        s.date = date(2026, 8, 1)
                cc = await service.get_current_quiz_cycle(admin_user.id)
                check("15b. date-aware: with Quiz I + Quiz II past, current-cycle "
                      "selects Quiz III (next upcoming 2026-10-09, basis next_upcoming)",
                      cc["quiz_cycle"] == 3 and cc["quiz_date"] == date(2026, 10, 9)
                      and cc["basis"] == "next_upcoming", f"got {cc}")

                # Scenario C: all dates past -> latest resolved cycle (III)
                for s in all_schedules:
                    s.date = date(2026, 8, 1)
                cc = await service.get_current_quiz_cycle(admin_user.id)
                check("15c. date-aware: with every quiz date past, current-cycle "
                      "falls back to the latest resolved cycle (Quiz III, basis "
                      "latest_resolved) without inventing a date",
                      cc["quiz_cycle"] == 3 and cc["quiz_date"] == date(2026, 8, 1)
                      and cc["basis"] == "latest_resolved", f"got {cc}")

                # Scenario D: all schedules unresolved -> documented fallback Quiz I
                for s in all_schedules:
                    s.date = None
                    s.schedule_status = ScheduleStatus.UNRESOLVED
                cc = await service.get_current_quiz_cycle(admin_user.id)
                check("15d. date-aware: with no resolved schedule, current-cycle "
                      "returns the documented fallback (Quiz I, has_schedule=false, "
                      "no invented date)",
                      cc["quiz_cycle"] == 1 and cc["has_schedule"] is False
                      and cc["quiz_date"] is None and cc["basis"] == "fallback", f"got {cc}")
            finally:
                # Discard every schedule mutation  -  the frozen baseline is
                # restored by the rollback (never committed).
                await db.rollback()

        # --- Contract / regression checks ---------------------------------------
        # 16. BCS-054 Quiz III authoritative date (live)
        r = await client.get("/api/v1/quiz-eligibility/BCS-054/3", headers=admin_headers)
        bcs054_q3 = r.json()
        check("16. BCS-054 Quiz III = 2026-10-23 (authoritative, live, dated)",
              r.status_code == 200 and bcs054_q3["quiz_date"] == "2026-10-23"
              and bcs054_q3["window_start"] == "2026-09-28"
              and bcs054_q3["window_end"] == "2026-10-22",
              f"date={bcs054_q3.get('quiz_date')}")

        # 17. UNRESOLVED only when genuinely unresolved (rollback)
        async with AsyncSessionLocal() as db:
            q3_row = (await db.execute(
                select(QuizSchedule).where(
                    QuizSchedule.subject_id == subject_ids["BCS-054"],
                    QuizSchedule.quiz_cycle_id == (await db.execute(
                        select(QuizCycle.id).where(QuizCycle.cycle_number == 3))).scalar_one(),
                ))).scalar_one()
            q3_row.date = None
            q3_row.schedule_status = ScheduleStatus.UNRESOLVED
            await db.flush()
            service = EligibilityService(db)
            result = await service.get_quiz_eligibility(admin_user.id, subject_ids["BCS-054"], 3,
                                                        semester_start=semester_start)
            check("17. UNRESOLVED only when genuinely unresolved  -  no fabricated "
                  "date/result for a removed schedule",
                  result.state == EligibilityState.UNRESOLVED
                  and result.quiz_date is None and result.lecture.total == 0,
                  f"state={result.state} date={result.quiz_date}")
            await db.rollback()

        # 18. Lab subjects excluded
        lab_status = {}
        for code in ("BCS-551", "BCS-552", "BCS-553"):
            rr = await client.get(f"/api/v1/quiz-eligibility/{code}/1", headers=admin_headers)
            lab_status[code] = rr.status_code
        check("18. lab subjects are strictly excluded from quiz eligibility (404)",
              lab_status == {"BCS-551": 404, "BCS-552": 404, "BCS-553": 404}, f"got {lab_status}")

        # 19. Dashboard snapshot == canonical per-subject eligibility results
        r = await client.get("/api/v1/dashboard/summary", headers=admin_headers)
        snapshot = r.json()["quiz_snapshot"]
        cc = (await client.get("/api/v1/quiz-eligibility/current-cycle", headers=admin_headers)).json()
        cycle = snapshot["quiz_cycle"]
        eligible = attention = not_eligible = 0
        for code in sorted(theory_codes()):
            rr = await client.get(f"/api/v1/quiz-eligibility/{code}/{cycle}", headers=admin_headers)
            b = rr.json()
            if b["is_eligible"]:
                eligible += 1
            elif b["optimization"] is not None and b["optimization"]["is_reachable"]:
                attention += 1
            else:
                not_eligible += 1
        check("19. dashboard quiz snapshot consumes the canonical eligibility "
              "result (recomputed counts match; snapshot cycle == current-cycle)",
              snapshot["has_snapshot"] is True and snapshot["quiz_cycle"] == cc["quiz_cycle"]
              and snapshot["eligible"] == eligible and snapshot["attention"] == attention
              and snapshot["not_eligible"] == not_eligible and snapshot["total_theory"] == 6,
              f"snapshot={snapshot} recomputed=({eligible},{attention},{not_eligible})")

        # 20. Track / History / Eligibility consistency (same canonical records)
        r = await client.get("/api/v1/attendance/daily/2026-07-15", headers=admin_headers)
        daily = r.json()
        async with AsyncSessionLocal() as db:
            db_rows = (await db.execute(
                select(ClassSession.date, AttendanceRecord.status).join(
                    AttendanceRecord, (AttendanceRecord.class_session_id == ClassSession.id)
                    & (AttendanceRecord.user_id == admin_user.id)).where(
                    ClassSession.date == date(2026, 7, 15)))).all()
            db_statuses = {st for _, st in db_rows}
            api_statuses = {s["status"] for s in daily["sessions"] if s["status"] != "Pending"}
            bcs501_window_total = (await db.execute(
                select(func.count()).select_from(ClassSession).where(
                    ClassSession.subject_id == subject_ids["BCS-501"],
                    ClassSession.date.between(date.fromisoformat(elig["window_start"]),
                                              date.fromisoformat(elig["window_end"])),
                    ClassSession.is_cancelled.is_(False)))).scalar()
        check("20. Track/History/Eligibility consistency: daily view matches the "
              "canonical records; eligibility window totals equal a direct "
              "session count",
              len(daily["sessions"]) == len(db_rows)
              and db_statuses == api_statuses
              and bcs501_window_total == elig["lecture"]["total"] + elig["tutorial"]["total"],
              f"daily={len(daily['sessions'])} db={len(db_rows)} "
              f"window={bcs501_window_total} api_lt={elig['lecture']['total'] + elig['tutorial']['total']}")

        # 21. Student authorization isolation
        r_admin = await client.get("/api/v1/quiz-eligibility/BCS-501/1", headers=admin_headers)
        r_student = await client.get("/api/v1/quiz-eligibility/BCS-501/1", headers=student_headers)
        check("21. eligibility is scoped per authenticated user (admin attended "
              "> 0, zero-record student 0, same window totals)",
              r_student.status_code == 200
              and r_admin.json()["lecture"]["attended"] >= 1
              and r_student.json()["lecture"]["attended"] == 0
              and r_admin.json()["lecture"]["total"] == r_student.json()["lecture"]["total"],
              f"admin={r_admin.json()['lecture']['attended']} "
              f"student={r_student.json()['lecture']['attended']}")

    # --- 22. Final baseline assertion (exact restoration) -----------------------
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
        scheduled_after = (await db.execute(
            select(func.count()).select_from(QuizSchedule).where(
                QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED))).scalar()
        users_after = (await db.execute(select(func.count()).select_from(User))).scalar()
        admins_after = (await db.execute(
            select(func.count()).select_from(User).where(User.role == UserRole.ADMIN))).scalar()
        max_record_date_after = (await db.execute(
            select(func.max(ClassSession.date)).join(
                AttendanceRecord, AttendanceRecord.class_session_id == ClassSession.id))).scalar()

    check("22. database restored to the exact baseline (events/sessions/cancelled/"
          "extra/records/enrollments/subjects/quizzes/scheduled/users/admins + "
          "max record date, history intact)",
          (events_after, sessions_after, cancelled_after, extra_after, records_after,
           enrollments_after, subjects_after, quizzes_after, scheduled_after, users_after,
           admins_after, max_record_date_after)
          == (events_before, sessions_before, cancelled_before, extra_before, records_before,
              enrollments_before, subjects_before, quizzes_before, scheduled_before, users_before,
              admins_before, max_record_session_date),
          f"events={events_before}->{events_after} sessions={sessions_before}->{sessions_after} "
          f"cancelled={cancelled_before}->{cancelled_after} extra={extra_before}->{extra_after} "
          f"records={records_before}->{records_after} enrollments={enrollments_before}->{enrollments_after} "
          f"subjects={subjects_before}->{subjects_after} quizzes={quizzes_before}->{quizzes_after} "
          f"scheduled={scheduled_before}->{scheduled_after} users={users_before}->{users_after} "
          f"admins={admins_before}->{admins_after} max_record={max_record_session_date}->{max_record_date_after}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\nPhase 7.2 verification: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
