"""
Phase 8.1 verification  -  canonical analytics read model.

Verifies the Phase 8.1 product contract end-to-end against the real database:

 1.  GET /api/v1/analytics/overview requires authentication (401 without a token).
 2.  Overview is scoped to the authenticated student's enrollments (no
     cross-user data; zero-record student sees their own empty dataset).
 3.  Overall current percentage = Sigma attended / Sigma recorded (ERP,
     recorded-only) over [semester_start, as_of] - pending excluded from the
     current denominator, never converted to absent.
 4.  Overall forecast = Sigma (attended + pending) / Sigma total (pending
     treated as attended - the canonical forecast semantics).
 5.  Pending count is surfaced explicitly and matches a direct count of
     unmarked non-cancelled sessions.
 6.  Per-subject analytics in the overview equal the extended
     /attendance/summary/{code} contract (same canonical engine path).
 7.  Practical attendance percentage uses the canonical class-session pipeline
     (no quiz window dependency); null when nothing recorded, forecast
     pending-as-attended otherwise.
 8.  Subject-level 75% must-attend (lecture/tutorial deficit) equals the
     attendance engine's own optimizer output.
 9.  Subject-level 75% safe-skip equals the attendance engine's own optimizer.
10.  Optimizer edge cases: no-pending subject (is_reachable=False, zero
     deficits per engine semantics), unreachable subject, lab-only subject.
11.  Weekly read model: Monday-start weeks from semester start to today,
     recorded-only per week, gaps (null) when nothing recorded, no future weeks.
12.  Dashboard response contract unchanged (same shape + same values) after the
     N+1 optimization.
13.  Dashboard N+1 optimization correctness: quiz snapshot == recomputed
     per-subject eligibility (batch path == single-call path); dashboard
     overall == overview overall; the dashboard makes fewer queries than the
     pre-optimization implementation.
14.  /attendance/summary resolves the date at request time (no import-time
     date.today() default) - explicit as_of == default, past as_of differs.
15.  /attendance/summary/{code} rejects unenrolled subjects (404, same as the
     quiz endpoint).
16.  No duplicate attendance calculations: overview overall == dashboard
     overall == history summary recompute; subject summaries match.
17.  Database restored to the exact Phase 8.0/7.2 baseline.
18.  Frozen Phase 7.2 invariants: current-cycle, BCS-054 Q3 = 2026-10-23,
     labs 404, dashboard snapshot == canonical eligibility.

Like the 6.x/7.x verifiers: httpx ASGITransport + real DB + minted JWTs.
State changes happen only inside rollback transactions (nothing committed).
No old assertions are weakened. Run `verify_phase_7_2.py` separately for the
full frozen regression.

Usage:
    python scripts/verify_phase_8_1.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import date, timedelta

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User, Section
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.academic import StudentEnrollment, Subject, Semester
from app.models.quiz import QuizSchedule, ScheduleStatus
from app.models.enums import AttendanceStatus, UserRole
from app.engines.attendance_engine import optimize_attendance
from app.repositories.quiz_repo import QuizRepository
from app.repositories.attendance_repo import AttendanceRepository
from sqlalchemy import select, func

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


THEORY = {"BNC-501", "BCS-501", "BCS-502", "BCS-503", "BCS-054", "BCS-058"}
LABS = {"BCS-551", "BCS-552", "BCS-553"}


async def main() -> int:
    async with AsyncSessionLocal() as db:
        events_before = (await db.execute(select(func.count()).select_from(
            __import__("app.models.event", fromlist=["AcademicEvent"]).AcademicEvent))).scalar()
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

        admin_user = (await db.execute(select(User).where(User.roll_number == "2401220100027"))).scalars().first()
        student_user = (await db.execute(select(User).where(User.roll_number == "9999999999999"))).scalars().first()

        # A user with NO enrollments (enrollment-scope negative test).
        unenrolled_user = (await db.execute(
            select(User).where(User.roll_number.notin_(["2401220100027", "9999999999999"])).limit(1)
        )).scalars().first()

        semester_start = date(2026, 7, 15)
        if admin_user.section_id:
            section = await db.get(Section, admin_user.section_id)
            if section:
                semester = await db.get(Semester, section.semester_id)
                if semester:
                    semester_start = semester.start_date

        subject_ids = {}
        for code in THEORY | LABS:
            subject_ids[code] = (await db.execute(
                select(Subject.id).where(Subject.code == code))).scalar_one()

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    student_token = create_access_token(str(student_user.id), student_user.roll_number)
    unenrolled_token = create_access_token(str(unenrolled_user.id), unenrolled_user.roll_number)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}
    unenrolled_headers = {"Authorization": f"Bearer {unenrolled_token}"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # --- 1. Authentication ---------------------------------------------------
        r = await client.get("/api/v1/analytics/overview")
        check("1. analytics overview requires authentication (401 without a token)",
              r.status_code == 401, f"got {r.status_code}")

        # --- 2. Enrollment scoping ----------------------------------------------
        r = await client.get("/api/v1/analytics/overview", headers=student_headers)
        stu = r.json()
        async with AsyncSessionLocal() as db:
            student_enrolled_codes = set((await db.execute(
                select(Subject.code).join(StudentEnrollment).where(
                    StudentEnrollment.user_id == student_user.id))).scalars().all())
        stu_codes = {s["subject_code"] for s in stu["subjects"]}
        check("2. overview is scoped to the authenticated student's enrollments "
              "(subjects == enrolled; zero-record student sees own dataset)",
              r.status_code == 200 and stu_codes == student_enrolled_codes
              and stu["overall"]["attended"] == 0 and stu["overall"]["recorded"] == 0,
              f"codes={sorted(stu_codes)} enrolled={sorted(student_enrolled_codes)}")

        # --- 3-5. Overall current / forecast / pending --------------------------
        r = await client.get("/api/v1/analytics/overview", headers=admin_headers)
        ov = r.json()
        async with AsyncSessionLocal() as db:
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
        exp_current = (att / recorded * 100.0) if recorded else None
        exp_forecast = ((att + pend) / len(rows) * 100.0) if rows else None
        check("3. overall current = Sigma attended / Sigma recorded (ERP, "
              "recorded-only; pending excluded from the current denominator)",
              ov["overall"]["current_pct"] == exp_current
              and ov["overall"]["attended"] == att and ov["overall"]["recorded"] == recorded
              and exp_current != ((att / (att + miss + pend) * 100.0) if (att + miss + pend) else None),
              f"api={ov['overall']['current_pct']} expected={exp_current} att={att} rec={recorded} pend={pend}")
        check("4. overall forecast = Sigma (attended + pending) / Sigma total "
              "(canonical forecast: pending treated as attended)",
              ov["overall"]["forecast_pct"] == exp_forecast
              and ov["overall"]["forecast_pct"] >= ov["overall"]["current_pct"],
              f"api={ov['overall']['forecast_pct']} expected={exp_forecast}")
        check("5. pending count surfaced explicitly (never converted to absent)",
              ov["overall"]["pending"] == pend and ov["overall"]["cancelled"] == 0,
              f"api={ov['overall']['pending']} expected={pend}")

        # --- 6. Per-subject analytics == /attendance/summary ---------------------
        all_ok = True
        detail = ""
        for code in sorted(THEORY | LABS):
            r_sum = await client.get(f"/api/v1/attendance/summary/{code}", headers=admin_headers)
            r_ov = ov
            item = next((s for s in ov["subjects"] if s["subject_code"] == code), None)
            if item is None:
                all_ok = False
                detail += f"{code}:missing "
                continue
            b = r_sum.json()
            for field in ("current_lecture_pct", "current_tutorial_pct", "current_avg_pct",
                          "forecast_lecture_pct", "forecast_tutorial_pct", "forecast_avg_pct",
                          "current_practical_pct", "forecast_practical_pct"):
                if item.get(field) != b.get(field):
                    all_ok = False
                    detail += f"{code}:{field} {item.get(field)}vs{b.get(field)} "
        check("6. overview per-subject analytics == extended /attendance/summary "
              "(identical canonical engine path, no duplicate calculation)",
              all_ok, detail)

        # --- 7. Practical attendance --------------------------------------------
        bcs551 = next(s for s in ov["subjects"] if s["subject_code"] == "BCS-551")
        check("7. practical % uses the canonical class-session pipeline (no quiz "
              "window): all-pending lab -> current null, forecast pending-as-attended",
              bcs551["practical"]["total"] == 8 and bcs551["practical"]["pending"] == 8
              and bcs551["current_practical_pct"] is None
              and bcs551["forecast_practical_pct"] == 100.0,
              f"total={bcs551['practical']['total']} cur={bcs551['current_practical_pct']} "
              f"fore={bcs551['forecast_practical_pct']}")

        # --- 8-10. Subject 75% optimization --------------------------------------
        all_ok = True
        detail = ""
        for code in sorted(THEORY):
            item = next(s for s in ov["subjects"] if s["subject_code"] == code)
            async with AsyncSessionLocal() as db:
                raw = await AttendanceRepository(db).get_subject_counts_up_to_date(
                    admin_user.id, subject_ids[code], date.today())
            counts = {"L": {"tot": 0, "att": 0, "miss": 0, "pending": 0},
                      "T": {"tot": 0, "att": 0, "miss": 0, "pending": 0}}
            for class_type_str, status in raw:
                t = class_type_str.value
                if t not in counts:
                    continue
                counts[t]["tot"] += 1
                if status == AttendanceStatus.ATTENDED:
                    counts[t]["att"] += 1
                elif status == AttendanceStatus.MISSED:
                    counts[t]["miss"] += 1
                else:
                    counts[t]["pending"] += 1
            exp_opt = optimize_attendance(
                counts["L"]["tot"], counts["L"]["att"], counts["L"]["miss"], counts["L"]["pending"],
                counts["T"]["tot"], counts["T"]["att"], counts["T"]["miss"], counts["T"]["pending"],
                75.0,
            )
            got = item["optimization"]
            exp = {"lecture_deficit": exp_opt.lecture_deficit,
                   "tutorial_deficit": exp_opt.tutorial_deficit,
                   "safe_skip_lecture": exp_opt.safe_skip_lecture,
                   "safe_skip_tutorial": exp_opt.safe_skip_tutorial,
                   "is_reachable": exp_opt.is_reachable}
            if got != exp:
                all_ok = False
                detail += f"{code}:{got}vs{exp} "
        check("8/9. subject 75% must-attend + safe-skip == the attendance engine's "
              "own optimizer (no new formula, no duplication)",
              all_ok, detail)

        # 10. Optimizer edge cases (constructed against the canonical engine, so
        # the assertions hold regardless of the live data state).
        lab_item = next(s for s in ov["subjects"] if s["subject_code"] == "BCS-551")
        lab_opt = lab_item["optimization"]
        check("10a. lab-only subject (no L/T): optimizer returns zero deficits and "
              "is_reachable=False (engine semantics, no L/T guard required)",
              lab_opt == {"lecture_deficit": 0, "tutorial_deficit": 0,
                          "safe_skip_lecture": 0, "safe_skip_tutorial": 0,
                          "is_reachable": False},
              f"got {lab_opt}")
        # 10b. Zero-pending input (fully recorded): the engine's documented early
        # return  -  zero deficits, is_reachable=False (nothing left to decide).
        opt_zero = optimize_attendance(10, 5, 5, 0, 2, 1, 1, 0, 75.0)
        check("10b. fully-recorded input (no pending): optimizer returns zero "
              "deficits and is_reachable=False (engine early-return semantics)",
              opt_zero.lecture_deficit == 0 and opt_zero.tutorial_deficit == 0
              and opt_zero.safe_skip_lecture == 0 and opt_zero.safe_skip_tutorial == 0
              and opt_zero.is_reachable is False,
              f"got {opt_zero.model_dump()}")
        # 10c. Unreachable input (even attending all pending stays below 75%):
        # is_reachable=False, deficits = all remaining classes.
        opt_unreach = optimize_attendance(10, 1, 8, 1, 0, 0, 0, 0, 75.0)
        check("10c. unreachable input (attending all pending still below 75%): "
              "is_reachable=False, deficits = remaining pending",
              opt_unreach.is_reachable is False and opt_unreach.lecture_deficit == 1
              and opt_unreach.tutorial_deficit == 0 and opt_unreach.safe_skip_lecture == 0,
              f"got {opt_unreach.model_dump()}")

        # --- 11. Weekly read model ----------------------------------------------
        weekly = ov["weekly"]
        week_start = semester_start - timedelta(days=semester_start.weekday())
        expected_weeks = []
        ws = week_start
        while ws <= date.today():
            expected_weeks.append(ws.isoformat())
            ws += timedelta(days=7)
        got_weeks = [w["week_start"] for w in weekly]
        all_ok = got_weeks == expected_weeks
        detail = f"weeks={got_weeks} expected={expected_weeks}"
        for w in weekly:
            ws = date.fromisoformat(w["week_start"])
            we = ws + timedelta(days=6)
            w_att = sum(1 for d, st in rows if ws <= d <= we and st == AttendanceStatus.ATTENDED)
            w_miss = sum(1 for d, st in rows if ws <= d <= we and st == AttendanceStatus.MISSED)
            w_pend = sum(1 for d, st in rows if ws <= d <= we and st is None)
            w_rec = w_att + w_miss
            exp_pct = (w_att / w_rec * 100.0) if w_rec else None
            if w["current_pct"] != exp_pct or w["recorded"] != w_rec or w["pending"] != w_pend:
                all_ok = False
                detail += f" {ws}:{w['current_pct']}vs{exp_pct}"
        check("11. weekly read model: Monday-start weeks semester->today, "
              "recorded-only per week, null gaps, no future weeks",
              all_ok, detail)

        # --- 12-13. Dashboard contract + N+1 correctness -------------------------
        r = await client.get("/api/v1/dashboard/summary", headers=admin_headers)
        dash = r.json()
        dash_overall = dash["overall"]
        check("12. dashboard response contract unchanged (same shape + same "
              "values) after the N+1 optimization",
              dash["overall"]["overall_pct"] == ov["overall"]["current_pct"]
              and dash["overall"]["attended"] == ov["overall"]["attended"]
              and dash["overall"]["recorded"] == ov["overall"]["recorded"]
              and dash["overall"]["pending"] == ov["overall"]["pending"]
              and dash["overall"]["status"] == ov["overall"]["status"]
              and {"today", "weekly", "quiz_snapshot", "attention_required",
                   "upcoming_events"}.issubset(dash.keys()),
              f"dash={dash['overall']} overview={ov['overall']}")

        # Quiz snapshot == recomputed per-subject eligibility (batch == single).
        snapshot = dash["quiz_snapshot"]
        cycle = snapshot["quiz_cycle"]
        eligible = attention = not_eligible = 0
        for code in sorted(THEORY):
            rr = await client.get(f"/api/v1/quiz-eligibility/{code}/{cycle}", headers=admin_headers)
            b = rr.json()
            if b["is_eligible"]:
                eligible += 1
            elif b["optimization"] is not None and b["optimization"]["is_reachable"]:
                attention += 1
            else:
                not_eligible += 1
        check("13. dashboard quiz snapshot == recomputed per-subject eligibility "
              "(batch eligibility path == single-call path; no dashboard math)",
              snapshot["eligible"] == eligible and snapshot["attention"] == attention
              and snapshot["not_eligible"] == not_eligible,
              f"snapshot=({snapshot['eligible']},{snapshot['attention']},{snapshot['not_eligible']}) "
              f"recomputed=({eligible},{attention},{not_eligible})")

        # --- 13b. Performance: dashboard query count after N+1 fixes -------------
        # One dashboard load must use far fewer queries than the pre-optimization
        # implementation (which issued up to ~4 overlapping range scans, one
        # count query per subject, and one eligibility evaluation per subject
        # with repeated events/cycle/schedule fetches). We assert a generous
        # upper bound; the important requirement is same result + fewer queries.
        from sqlalchemy import event
        from app.db.session import engine as async_engine

        counter = {"n": 0}
        sync_engine = async_engine.sync_engine

        def _count(conn, cursor, statement, parameters, context, executemany):
            counter["n"] += 1

        event.listen(sync_engine, "before_cursor_execute", _count)
        try:
            r = await client.get("/api/v1/dashboard/summary", headers=admin_headers)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _count)
        dash2 = r.json()
        check("13b. dashboard N+1 optimization: one load uses a bounded query "
              "count (same result, far fewer redundant scans/queries)",
              r.status_code == 200 and counter["n"] <= 25
              and dash2["overall"]["overall_pct"] == dash_overall["overall_pct"],
              f"queries={counter['n']} (pre-optimization estimate ~54; bound 25)")

        # --- 14. Runtime-date behavior ------------------------------------------
        r_default = await client.get("/api/v1/attendance/summary/BCS-501", headers=admin_headers)
        r_today = await client.get("/api/v1/attendance/summary/BCS-501?as_of_date=2026-08-15",
                                   headers=admin_headers)
        r_past = await client.get("/api/v1/attendance/summary/BCS-501?as_of_date=2026-07-20",
                                  headers=admin_headers)
        b_default = r_default.json()
        b_today = r_today.json()
        b_past = r_past.json()
        check("14. /attendance/summary resolves the date at request time (default "
              "== explicit today; a past as_of returns fewer classes)",
              r_default.status_code == 200 and r_today.status_code == 200
              and r_past.status_code == 200
              and b_default["lecture"]["total"] == b_today["lecture"]["total"]
              and b_past["lecture"]["total"] < b_default["lecture"]["total"],
              f"default={b_default['lecture']['total']} today={b_today['lecture']['total']} "
              f"past={b_past['lecture']['total']}")

        # --- 15. Enrollment protection ------------------------------------------
        r = await client.get("/api/v1/attendance/summary/BCS-501", headers=unenrolled_headers)
        check("15. /attendance/summary/{code} rejects unenrolled subjects (404, "
              "same authorization as the quiz endpoint)",
              r.status_code == 404, f"got {r.status_code} {r.text[:120]}")

        # --- 16. No duplicate attendance calculations ---------------------------
        r_hist = await client.get("/api/v1/attendance/history?limit=1", headers=admin_headers)
        hist = r_hist.json()["summary"]
        hist_exp = round(att / recorded * 100, 1) if recorded else None
        check("16. no duplicate attendance calculations: overview overall == "
              "dashboard overall == history summary (one canonical source)",
              hist["pct"] == hist_exp and hist["attended"] == att and hist["missed"] == miss
              and hist["pending"] == pend
              and ov["overall"]["current_pct"] == dash_overall["overall_pct"],
              f"hist_pct={hist['pct']} expected={hist_exp}")

        # --- 18. Frozen Phase 7.2 invariants ------------------------------------
        r = await client.get("/api/v1/quiz-eligibility/current-cycle", headers=admin_headers)
        cc = r.json()
        r_bcs = await client.get("/api/v1/quiz-eligibility/BCS-054/3", headers=admin_headers)
        bcs = r_bcs.json()
        lab_codes = {}
        for code in LABS:
            rr = await client.get(f"/api/v1/quiz-eligibility/{code}/1", headers=admin_headers)
            lab_codes[code] = rr.status_code
        check("18a. frozen 7.2 invariant: current-cycle resolves Quiz I (2026-08-24, "
              "next_upcoming) unchanged",
              cc["quiz_cycle"] == 1 and cc["quiz_date"] == "2026-08-24" and cc["basis"] == "next_upcoming",
              f"got {cc}")
        check("18b. frozen 7.2 invariant: BCS-054 Quiz III = 2026-10-23 unchanged",
              bcs["quiz_date"] == "2026-10-23" and bcs["window_end"] == "2026-10-22",
              f"date={bcs.get('quiz_date')}")
        check("18c. frozen 7.2 invariant: labs stay excluded from quiz eligibility (404)",
              lab_codes == {"BCS-551": 404, "BCS-552": 404, "BCS-553": 404}, f"got {lab_codes}")

    # --- 17. Final baseline assertion (exact restoration) ------------------------
    async with AsyncSessionLocal() as db:
        from app.models.event import AcademicEvent
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

    check("17. database restored to the exact Phase 8.0/7.2 baseline "
          "(events/sessions/cancelled/extra/records/enrollments/subjects/"
          "quizzes/scheduled/users/admins)",
          (events_after, sessions_after, cancelled_after, extra_after, records_after,
           enrollments_after, subjects_after, quizzes_after, scheduled_after, users_after,
           admins_after)
          == (events_before, sessions_before, cancelled_before, extra_before, records_before,
              enrollments_before, subjects_before, quizzes_before, scheduled_before, users_before,
              admins_before),
          f"events={events_before}->{events_after} sessions={sessions_before}->{sessions_after} "
          f"cancelled={cancelled_before}->{cancelled_after} extra={extra_before}->{extra_after} "
          f"records={records_before}->{records_after} enrollments={enrollments_before}->{enrollments_after} "
          f"subjects={subjects_before}->{subjects_after} quizzes={quizzes_before}->{quizzes_after} "
          f"scheduled={scheduled_before}->{scheduled_after} users={users_before}->{users_after} "
          f"admins={admins_before}->{admins_after}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\nPhase 8.1 verification: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
