"""
Phase 7.1 verification — canonical quiz eligibility contract & reference UI data.

Verifies the Phase 7.1 product contract end-to-end against the real database:

 1.  Complete canonical quiz schedule (18 SCHEDULED dates) matches timetable.json
 2.  BCS-054 Quiz III resolved to the authoritative date (2026-10-23)
 3.  All theory subjects x 3 cycles present; labs have no quiz schedules
 4.  Practicals excluded via the authoritative subjects.quiz_applicable flag
 5.  BCS-054 Q3 QUIZ_DAY event is calendar/read-only (zero session mutation)
 6.  /events upcoming surfaces all 18 quiz days
 7-9. BCS-054 Q1/Q2 windows unchanged; Q3 window follows the resolved schedule
10.  Lecture-only formula (BNC-501: average collapses to lecture %)
11.  Lecture+tutorial combined average formula (BCS-501)
12.  RECOVERABLE  = below target but reachable (real admin data)
13.  ELIGIBLE     = currently satisfies the requirement (rollback scenario)
14.  NOT_ELIGIBLE = unreachable (rollback scenario)
15.  UNRESOLVED only when genuinely unresolved (rollback scenario)
16.  Criterion I contract (value/threshold/passed vs policy)
17.  Criterion II contract (combined average vs policy)
18.  Final combination: (Criterion I qualifies) OR (Criterion II qualifies)
19.  Must-Attend / Safe-Skip match the attendance engine's optimizer output
20.  API exposes the reference-card UI analytics
21.  /quiz-eligibility for practical subjects -> 404
22.  No cross-user leakage (admin vs zero-record student)
23.  No attendance-history corruption (89 records, none future-dated)
24.  Quiz-day attendance + surprise-quiz materialization are canonical
25.  Database baseline restored/verified after all checks (incl. rollback + cleanup)

Like the 6.x verifiers: httpx ASGITransport + real DB + minted JWTs. State
mutations happen only inside rollback transactions or are hard-cleaned up.

Usage:
    python scripts/verify_phase_7_1.py
"""
import asyncio
import json
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
from app.models.enums import AttendanceStatus, EventType, UserRole
from app.engines.attendance_engine import optimize_attendance
from app.services.eligibility_service import EligibilityService
from app.schemas.attendance import EligibilityState
from app.repositories.session_repo import SessionRepository
from sqlalchemy import select, func

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def load_authoritative_schedule() -> dict:
    """Parses timetable.json into {subject_code: {qN: date}} — the single
    authoritative institutional source for quiz dates."""
    path = Path(__file__).resolve().parent.parent.parent / "timetable.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for subj in data["subjects"]:
        if "timeline" not in subj or not subj["timeline"].get("milestones"):
            out[subj["code"]] = {}
            continue
        dates = {}
        for ms in subj["timeline"]["milestones"]:
            if ms.get("date") and ms.get("milestoneId", "").startswith("q"):
                dates[ms["milestoneId"]] = date.fromisoformat(ms["date"])
        out[subj["code"]] = dates
    return out


async def main() -> int:
    authoritative = load_authoritative_schedule()

    # --- Baseline (recorded BEFORE any verification data) ----------------------
    async with AsyncSessionLocal() as db:
        # Startup cleanup: stale SURPRISE_QUIZ artifacts (crashed 6.6/7.1 runs).
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

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    student_token = create_access_token(str(student_user.id), student_user.roll_number)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # --- 1-3. Canonical schedule (DB vs authoritative timetable.json) -----------
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Subject.code, QuizCycle.cycle_number, QuizSchedule.date, QuizSchedule.schedule_status)
            .join(QuizSchedule, QuizSchedule.subject_id == Subject.id)
            .join(QuizCycle, QuizCycle.id == QuizSchedule.quiz_cycle_id)
        )).all()
        lab_codes_db = {"BCS-551", "BCS-552", "BCS-553"}
        theory_rows = [(code, cyc, d, st) for code, cyc, d, st in rows if code not in lab_codes_db]
        scheduled_rows = [(code, cyc, d) for code, cyc, d, st in theory_rows
                          if st == ScheduleStatus.SCHEDULED and d]
        expected_pairs = set()
        for code, milestones in authoritative.items():
            for key, dt in milestones.items():
                expected_pairs.add((code, int(key[1:]), dt))
        actual_pairs = {(code, cyc, d) for code, cyc, d in scheduled_rows}
        check("1. complete canonical schedule: 18 SCHEDULED dates match timetable.json",
              len(theory_rows) == 18 and len(scheduled_rows) == 18 and actual_pairs == expected_pairs,
              f"theory_rows={len(theory_rows)} scheduled={len(scheduled_rows)} "
              f"diff={sorted(expected_pairs ^ actual_pairs)}")

        bcs054_id = (await db.execute(select(Subject.id).where(Subject.code == "BCS-054"))).scalar_one()
        bcs501_id = (await db.execute(select(Subject.id).where(Subject.code == "BCS-501"))).scalar_one()
        bcs503_id = (await db.execute(select(Subject.id).where(Subject.code == "BCS-503"))).scalar_one()
        q3 = (await db.execute(
            select(QuizSchedule).where(
                QuizSchedule.subject_id == bcs054_id,
                QuizSchedule.quiz_cycle_id == (await db.execute(
                    select(QuizCycle.id).where(QuizCycle.cycle_number == 3))).scalar_one(),
            ))).scalar_one()
        expected_q3 = authoritative["BCS-054"]["q3"]
        check("2. BCS-054 Quiz III resolved to the authoritative date (2026-10-23)",
              q3.date == expected_q3 and q3.schedule_status == ScheduleStatus.SCHEDULED,
              f"date={q3.date} status={q3.schedule_status.value} expected={expected_q3}")

        per_subject = {}
        for code, cyc, d, st in theory_rows:
            per_subject.setdefault(code, []).append(cyc)
        check("3. every theory subject has all 3 quiz cycles; labs have none",
              all(sorted(cyc) == [1, 2, 3] for cyc in per_subject.values())
              and set(per_subject.keys()) == {"BNC-501", "BCS-501", "BCS-502", "BCS-503", "BCS-054", "BCS-058"}
              and all(len(authoritative[code]) == 0 for code in ("BCS-551", "BCS-552", "BCS-553")),
              f"per_subject={ {k: sorted(v) for k, v in per_subject.items()} }")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # --- 4. Practicals excluded via authoritative quiz_applicable -----------
        r = await client.get("/api/v1/subjects", headers=admin_headers)
        subjects_api = r.json()
        lab_codes = {s["code"] for s in subjects_api if s["category"] == "lab"}
        theory_flags = {s["code"]: s["quiz_applicable"] for s in subjects_api if s["category"] == "theory"}
        check("4. labs are not quiz_applicable; theory subjects are",
              lab_codes == {"BCS-551", "BCS-552", "BCS-553"}
              and all(flag for flag in theory_flags.values())
              and set(theory_flags.keys()) == {"BNC-501", "BCS-501", "BCS-502", "BCS-503", "BCS-054", "BCS-058"},
              f"labs={lab_codes} theory_flags={theory_flags}")

        # --- 5. BCS-054 Q3 QUIZ_DAY event calendar-only -------------------------
        async with AsyncSessionLocal() as db:
            events = (await db.execute(
                select(AcademicEvent).where(
                    AcademicEvent.event_type == EventType.QUIZ_DAY,
                    AcademicEvent.start_date == expected_q3,
                ))).scalars().all()
            q3_event = next((e for e in events if e.subject_id == bcs054_id), None)
            q3_day_sessions = (await db.execute(
                select(func.count()).select_from(ClassSession).where(
                    ClassSession.subject_id == bcs054_id,
                    ClassSession.date == expected_q3,
                ))).scalar()
        check("5. BCS-054 Q3 QUIZ_DAY event exists, active, calendar-only (no sessions)",
              q3_event is not None and q3_event.active and q3_day_sessions == 0,
              f"event={q3_event is not None} active={q3_event.active if q3_event else None} sessions={q3_day_sessions}")

        # --- 6. /events upcoming surfaces all 18 quiz days ----------------------
        r = await client.get("/api/v1/events?upcoming=true", headers=admin_headers)
        upcoming = r.json()
        check("6. /events upcoming = 18 quiz days, all at/after the semester horizon",
              r.status_code == 200 and len(upcoming) == 18 and all(e["end_date"] >= "2026-08-14" for e in upcoming),
              f"count={len(upcoming)}")

        # --- 7-9. BCS-054 windows (Q1/Q2 unchanged, Q3 follows the resolution) --
        expected_windows = {
            1: (date(2026, 7, 15), date(2026, 9, 6), date(2026, 9, 7)),
            2: (date(2026, 9, 7), date(2026, 9, 27), date(2026, 9, 28)),
            3: (date(2026, 9, 28), date(2026, 10, 22), date(2026, 10, 23)),
        }
        for cycle, (w_start, w_end, q_date) in expected_windows.items():
            r = await client.get(f"/api/v1/quiz-eligibility/BCS-054/{cycle}", headers=admin_headers)
            body = r.json()
            ok = (r.status_code == 200
                  and body["window_start"] == w_start.isoformat()
                  and body["window_end"] == w_end.isoformat()
                  and body["quiz_date"] == q_date.isoformat())
            check(f"{6 + cycle}. BCS-054 Q{cycle} window/quiz-date "
                  f"({'unchanged' if cycle < 3 else 'follows resolved schedule'})",
                  ok, f"got start={body.get('window_start')} end={body.get('window_end')} q={body.get('quiz_date')}")

        # --- 10. Lecture-only formula (BNC-501 has no tutorials) ----------------
        r = await client.get("/api/v1/quiz-eligibility/BNC-501/1", headers=admin_headers)
        bnc_q1 = r.json()
        check("10. BNC-501 Q1 lecture-only: average == lecture %, no combined threshold",
              r.status_code == 200
              and bnc_q1["tutorial"]["total"] == 0
              and bnc_q1["combined_threshold"] is None
              and bnc_q1["average_pct"] == bnc_q1["lecture_pct"]
              and bnc_q1["criterion_ii"]["value"] == bnc_q1["criterion_i"]["value"]
              and bnc_q1["criterion_i"]["passed"] == bnc_q1["criterion_ii"]["passed"],
              f"tut_tot={bnc_q1.get('tutorial', {}).get('total')} avg={bnc_q1.get('average_pct')} lec={bnc_q1.get('lecture_pct')}")

        # --- 11. Lecture+tutorial combined formula (BCS-501) --------------------
        r = await client.get("/api/v1/quiz-eligibility/BCS-501/1", headers=admin_headers)
        bcs501_q1 = r.json()
        lec, tut = bcs501_q1["lecture"], bcs501_q1["tutorial"]
        expected_avg = (lec["attended"] / lec["total"] * 100.0 + tut["attended"] / tut["total"] * 100.0) / 2.0
        check("11. BCS-501 Q1 average = (lecture % + tutorial %) / 2 from canonical counts",
              r.status_code == 200
              and lec["total"] > 0 and tut["total"] > 0
              and abs(bcs501_q1["average_pct"] - expected_avg) < 1e-6
              and bcs501_q1["lecture_pct"] == lec["attended"] / lec["total"] * 100.0
              and bcs501_q1["tutorial_pct"] == tut["attended"] / tut["total"] * 100.0,
              f"avg={bcs501_q1.get('average_pct')} expected={expected_avg:.2f}")

        # --- 12. RECOVERABLE on real data (below target, reachable) -------------
        check("12. BCS-501 Q1 (admin): RECOVERABLE = below target but reachable",
              r.status_code == 200
              and bcs501_q1["state"] == EligibilityState.RECOVERABLE.value
              and bcs501_q1["recoverable"] is True
              and bcs501_q1["is_eligible"] is False
              and bcs501_q1["optimization"]["is_reachable"] is True,
              f"state={bcs501_q1.get('state')} reachable={bcs501_q1.get('optimization', {}).get('is_reachable')}")

        # --- 16. Criterion I contract --------------------------------------------
        crit_i = bcs501_q1["criterion_i"]
        check("16. Criterion I = lecture % vs policy lecture threshold (70)",
              crit_i["value"] == bcs501_q1["lecture_pct"]
              and crit_i["threshold"] == 70.0
              and crit_i["passed"] == (crit_i["value"] >= 70.0)
              and bcs501_q1["lecture_threshold"] == 70.0
              and bool(crit_i["explanation"]),
              f"value={crit_i.get('value')} threshold={crit_i.get('threshold')} passed={crit_i.get('passed')}")

        # --- 17. Criterion II contract ---------------------------------------------
        crit_ii = bcs501_q1["criterion_ii"]
        check("17. Criterion II = combined average vs policy combined threshold (70)",
              crit_ii["value"] == bcs501_q1["average_pct"]
              and crit_ii["threshold"] == 70.0
              and crit_ii["passed"] == (crit_ii["value"] >= 70.0)
              and bcs501_q1["combined_threshold"] == 70.0
              and bool(crit_ii["explanation"]),
              f"value={crit_ii.get('value')} threshold={crit_ii.get('threshold')} passed={crit_ii.get('passed')}")

        # --- 18. Final combination ---------------------------------------------------
        final = bcs501_q1["final_criterion"]
        check("18. final = (Criterion I qualifies) OR (Criterion II qualifies)",
              final["combination"] == "Criterion I OR Criterion II"
              and final["passed"] == (crit_i["passed"] or crit_ii["passed"])
              and bool(final["explanation"]),
              f"combination={final.get('combination')} passed={final.get('passed')}")

        # --- 19. Must-Attend / Safe-Skip match the optimizer --------------------------
        opt = optimize_attendance(
            lec["total"], lec["attended"], lec["missed"], lec["pending"],
            tut["total"], tut["attended"], tut["missed"], tut["pending"],
            70.0,
        )
        resp_opt = bcs501_q1["optimization"]
        check("19. must-attend & safe-skip match the attendance engine's optimizer",
              resp_opt["lecture_deficit"] == opt.lecture_deficit
              and resp_opt["tutorial_deficit"] == opt.tutorial_deficit
              and resp_opt["safe_skip_lecture"] == opt.safe_skip_lecture
              and resp_opt["safe_skip_tutorial"] == opt.safe_skip_tutorial
              and resp_opt["is_reachable"] == opt.is_reachable,
              f"got={resp_opt} expected=deficits({opt.lecture_deficit},{opt.tutorial_deficit}) "
              f"safe({opt.safe_skip_lecture},{opt.safe_skip_tutorial}) reachable={opt.is_reachable}")

        # --- 20. API exposes reference-card UI analytics -----------------------------
        r = await client.get("/api/v1/quiz-eligibility/BCS-054/3", headers=admin_headers)
        bcs054_q3 = r.json()
        check("20. API exposes the reference-card UI analytics",
              r.status_code == 200
              and bool(bcs054_q3["subject_name"])
              and bcs054_q3["category"] == "theory"
              and bcs054_q3["quiz_date"] == "2026-10-23"
              and bcs054_q3["required_percentage"] == 75.0
              and bcs054_q3["lecture"]["total"] >= 0
              and bcs054_q3["tutorial"]["total"] >= 0
              and bcs054_q3["lecture_pct"] is not None
              and bcs054_q3["average_pct"] is not None
              and bool(bcs054_q3["explanation"]),
              f"name={bcs054_q3.get('subject_name')} category={bcs054_q3.get('category')} "
              f"state={bcs054_q3.get('state')} req={bcs054_q3.get('required_percentage')}")

        # --- 21. Practical subjects are strictly excluded (404) ----------------------
        lab_status = {}
        for code in ("BCS-551", "BCS-552", "BCS-553"):
            rr = await client.get(f"/api/v1/quiz-eligibility/{code}/1", headers=admin_headers)
            lab_status[code] = rr.status_code
        check("21. practical subjects are not returned as quiz subjects (404)",
              lab_status == {"BCS-551": 404, "BCS-552": 404, "BCS-553": 404},
              f"got {lab_status}")

        # --- 22. No cross-user leakage ------------------------------------------------
        r_admin = await client.get("/api/v1/quiz-eligibility/BCS-501/1", headers=admin_headers)
        r_student = await client.get("/api/v1/quiz-eligibility/BCS-501/1", headers=student_headers)
        admin_att, student_att = r_admin.json()["lecture"]["attended"], r_student.json()["lecture"]["attended"]
        check("22. eligibility is scoped per authenticated user (admin vs zero-record student)",
              r_student.status_code == 200
              and admin_att >= 1 and student_att == 0
              and r_admin.json()["lecture"]["total"] == r_student.json()["lecture"]["total"],
              f"admin_att={admin_att} student_att={student_att}")

        # --- 23. No attendance-history corruption --------------------------------------
        async with AsyncSessionLocal() as db:
            records_now = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
            max_date_now = (await db.execute(
                select(func.max(ClassSession.date)).join(
                    AttendanceRecord, AttendanceRecord.class_session_id == ClassSession.id))).scalar()
        check("23. attendance history intact: 89 records, none future-dated",
              records_now == 89 and max_date_now <= date(2026, 8, 15),
              f"records={records_now} max_date={max_date_now}")

        # --- 13-15. State derivation scenarios (rollback transactions) ----------------
        # BCS-501 Q1 window sessions, from the already-verified API window bounds.
        w_start = date.fromisoformat(bcs501_q1["window_start"])
        w_end = date.fromisoformat(bcs501_q1["window_end"])

        async with AsyncSessionLocal() as db:
            session_ids = (await db.execute(
                select(ClassSession.id).where(
                    ClassSession.subject_id == bcs501_id,
                    ClassSession.date.between(w_start, w_end),
                ))).scalars().all()
            existing_records = (await db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.user_id == admin_user.id,
                    AttendanceRecord.class_session_id.in_(session_ids)))).scalars().all()
            service = EligibilityService(db)

            # 13. All-attended scenario -> ELIGIBLE
            for rec in existing_records:
                await db.delete(rec)
            await db.flush()  # deletes first: uq_user_class_session must be free
            for sid in session_ids:
                db.add(AttendanceRecord(user_id=admin_user.id, class_session_id=sid,
                                        status=AttendanceStatus.ATTENDED))
            result = await service.get_quiz_eligibility(admin_user.id, bcs501_id, 1, semester_start=semester_start)
            check("13. ELIGIBLE = currently satisfies the requirement (all-attended scenario)",
                  result.state == EligibilityState.ELIGIBLE
                  and result.is_eligible is True
                  and result.recoverable is False
                  and result.criterion_i.passed and result.criterion_ii.passed
                  and result.final_criterion.passed
                  and result.optimization.lecture_deficit == 0
                  and result.optimization.tutorial_deficit == 0,
                  f"state={result.state} eligible={result.is_eligible} "
                  f"i={result.criterion_i.passed} ii={result.criterion_ii.passed}")

            # 14. All-missed scenario -> NOT_ELIGIBLE
            for rec in (await db.execute(
                    select(AttendanceRecord).where(
                        AttendanceRecord.user_id == admin_user.id,
                        AttendanceRecord.class_session_id.in_(session_ids)))).scalars().all():
                await db.delete(rec)
            await db.flush()
            for sid in session_ids:
                db.add(AttendanceRecord(user_id=admin_user.id, class_session_id=sid,
                                        status=AttendanceStatus.MISSED))
            result = await service.get_quiz_eligibility(admin_user.id, bcs501_id, 1, semester_start=semester_start)
            check("14. NOT_ELIGIBLE = unreachable (all-missed scenario)",
                  result.state == EligibilityState.NOT_ELIGIBLE
                  and result.is_eligible is False
                  and result.recoverable is False
                  and not result.criterion_i.passed and not result.criterion_ii.passed
                  and result.optimization.is_reachable is False,
                  f"state={result.state} reachable={result.optimization.is_reachable}")

            await db.rollback()

        # 15. UNRESOLVED scenario (rollback): BCS-054 Q3 date removed
        async with AsyncSessionLocal() as db:
            q3_row = (await db.execute(
                select(QuizSchedule).where(
                    QuizSchedule.subject_id == bcs054_id,
                    QuizSchedule.quiz_cycle_id == (await db.execute(
                        select(QuizCycle.id).where(QuizCycle.cycle_number == 3))).scalar_one(),
                ))).scalar_one()
            q3_row.date = None
            q3_row.schedule_status = ScheduleStatus.UNRESOLVED
            await db.flush()
            service = EligibilityService(db)
            result = await service.get_quiz_eligibility(admin_user.id, bcs054_id, 3, semester_start=semester_start)
            check("15. UNRESOLVED only when genuinely unresolved (removed date scenario)",
                  result.state == EligibilityState.UNRESOLVED
                  and result.is_eligible is False
                  and result.quiz_date is None
                  and result.optimization is None
                  and result.lecture.total == 0
                  and bool(result.explanation),
                  f"state={result.state} quiz_date={result.quiz_date}")
            await db.rollback()

    # --- 24. Quiz-day + surprise-quiz canonicality --------------------------------
    # Quiz-day attendance is a plain attendance record; a record on the quiz day
    # itself is outside the window (ADR-010: counts end the day before the quiz).
    async with AsyncSessionLocal() as db:
        bnc501_id = (await db.execute(select(Subject.id).where(Subject.code == "BNC-501"))).scalar_one()
        service = EligibilityService(db)
        baseline = await service.get_quiz_eligibility(admin_user.id, bnc501_id, 1, semester_start=semester_start)
        q1_quiz_day_session = (await db.execute(
            select(ClassSession).where(
                ClassSession.subject_id == bnc501_id,
                ClassSession.date == date(2026, 8, 24)))).scalars().first()
        existing = (await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.user_id == admin_user.id,
                AttendanceRecord.class_session_id == q1_quiz_day_session.id))).scalars().first()
        if existing:
            await db.delete(existing)
        db.add(AttendanceRecord(user_id=admin_user.id, class_session_id=q1_quiz_day_session.id,
                                status=AttendanceStatus.ATTENDED))
        after = await service.get_quiz_eligibility(admin_user.id, bnc501_id, 1, semester_start=semester_start)
        check("24a. quiz-day attendance canonical: plain record, outside the window "
              "(BNC-501 Q1 result byte-identical)",
              q1_quiz_day_session is not None and after == baseline,
              f"same={after == baseline}")
        await db.rollback()

    surprise_event_id = None
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/v1/quiz-eligibility/BCS-503/3", headers=admin_headers)
            eligibility_before = r.json()
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "SURPRISE_QUIZ",
                "subject_id": str(bcs503_id),
                "start_date": "2026-11-06",
                "end_date": "2026-11-06",
                "class_type": "L",
            })
            surprise_event_id = uuid.UUID(r.json()["id"])
            async with AsyncSessionLocal() as db:
                extra_sessions = (await db.execute(
                    select(func.count()).select_from(ClassSession).where(
                        ClassSession.subject_id == bcs503_id,
                        ClassSession.date == date(2026, 11, 6),
                        ClassSession.is_extra.is_(True)))).scalar()
            r = await client.get("/api/v1/quiz-eligibility/BCS-503/3", headers=admin_headers)
            check("24b. surprise quiz materializes exactly one extra session, "
                  "eligibility byte-identical (outside its window)",
                  surprise_event_id is not None
                  and extra_sessions == 1
                  and r.json() == eligibility_before,
                  f"extra_sessions={extra_sessions} same={r.json() == eligibility_before}")
    finally:
        if surprise_event_id is not None:
            async with AsyncSessionLocal() as db:
                ev = await db.get(AcademicEvent, surprise_event_id)
                if ev:
                    ev.active = False
                    await db.commit()
                    await db.delete(ev)
                    await db.commit()
                extra = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.subject_id == bcs503_id,
                        ClassSession.date == date(2026, 11, 6),
                        ClassSession.is_extra.is_(True)))).scalars().all()
                for s in extra:
                    await db.delete(s)
                if extra:
                    await db.commit()

    # --- 25. Final baseline assertion (exact restoration) ---------------------------
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

    check("25. database restored to the exact baseline "
          "(events/sessions/cancelled/extra/records/enrollments/subjects/quizzes/scheduled/users/admins)",
          (events_after, sessions_after, cancelled_after, extra_after, records_after,
           enrollments_after, subjects_after, quizzes_after, scheduled_after, users_after, admins_after)
          == (events_before, sessions_before, cancelled_before, extra_before, records_before,
              enrollments_before, subjects_before, quizzes_before, scheduled_before, users_before, admins_before),
          f"events={events_before}->{events_after} sessions={sessions_before}->{sessions_after} "
          f"cancelled={cancelled_before}->{cancelled_after} extra={extra_before}->{extra_after} "
          f"records={records_before}->{records_after} enrollments={enrollments_before}->{enrollments_after} "
          f"subjects={subjects_before}->{subjects_after} quizzes={quizzes_before}->{quizzes_after} "
          f"scheduled={scheduled_before}->{scheduled_after} users={users_before}->{users_after} "
          f"admins={admins_before}->{admins_after}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\nPhase 7.1 verification: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))