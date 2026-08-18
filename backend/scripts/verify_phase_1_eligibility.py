"""
Phase 1 verification — Quiz Eligibility Mathematics Correction.

Verifies the corrected eligibility contract end-to-end against the real
database (Phase 1 of the multi-phase eligibility correction; events, quiz-day
lifecycle, ClassSession materialization and attendance formulas are NOT
touched — this script never creates or mutates them except inside rollback
transactions):

  A.  Cycle I:   Criterion I and Criterion II BOTH = (Lecture % + Tutorial %) / 2,
                 threshold 70% (BCS-501 with tutorials; BNC-501 without).
  B.  Cycle II:  Criterion I window = QT-I -> day before QT-II;
                 Criterion II window = commencement -> day before QT-II;
                 both use the same average formula; threshold 75%.
  C.  Cycle III: Criterion I window = QT-II -> day before QT-III;
                 Criterion II window = commencement -> day before QT-III;
                 both use the same average formula; threshold 75%.
  D.  Must Attend follows the corrected calculation (per-criterion optimizer
                 on that criterion's own window counts).
  E.  Safe Skip  follows the corrected calculation (same optimizer output).
  F.  Final eligibility = Criterion I OR Criterion II (incl. a rollback
                 scenario where the routes disagree: Criterion II alone grants
                 eligibility).
  G.  Quiz-Day-shaped ClassSession rows remain excluded from eligibility L/T
                 counts (Option-A rule preserved; exclude_quiz_day=True).
  H.  Normal timetable lecture/tutorial sessions remain included.
  25. Database restored to the exact baseline (no residue).

Like the other verifiers: httpx ASGITransport + real DB + minted JWTs. State
mutations happen only inside rollback transactions.

Usage:
    python scripts/verify_phase_1_eligibility.py
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
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.academic import StudentEnrollment, Subject, Semester
from app.models.quiz import QuizSchedule, QuizCycle
from app.models.enums import AttendanceStatus, UserRole, ClassType
from app.engines.attendance_engine import optimize_attendance, normalize_class_type
from app.services.eligibility_service import EligibilityService
from app.schemas.attendance import EligibilityState
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.session_repo import SessionRepository
from sqlalchemy import select, func

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def combined_pct(lec_pct, tut_pct):
    """Official formula: (Lecture % + Tutorial %) / 2; no-tutorial subjects
    collapse to the lecture percentage."""
    if tut_pct is None:
        return lec_pct
    if lec_pct is None:
        return None
    return (lec_pct + tut_pct) / 2.0


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


def expected_avg(counts: dict):
    l, t = counts['L'], counts['T']
    lec_pct = (l['att'] / l['tot'] * 100.0) if l['tot'] > 0 else None
    tut_pct = (t['att'] / t['tot'] * 100.0) if t['tot'] > 0 else None
    return combined_pct(lec_pct, tut_pct)


def expected_opt(counts: dict, threshold: float):
    l, t = counts['L'], counts['T']
    return optimize_attendance(
        l['tot'], l['att'], l['miss'], l['pending'],
        t['tot'], t['att'], t['miss'], t['pending'],
        threshold,
    )


def total_deficit(opt) -> int:
    return opt['lecture_deficit'] + opt['tutorial_deficit']


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

        quiz_dates = {}
        for code, sid in (("BCS-501", bcs501_id), ("BNC-501", bnc501_id)):
            rows = (await db.execute(
                select(QuizCycle.cycle_number, QuizSchedule.date)
                .join(QuizSchedule, QuizSchedule.quiz_cycle_id == QuizCycle.id)
                .where(QuizSchedule.subject_id == sid)
            )).all()
            quiz_dates[code] = {cyc: dt for cyc, dt in rows}

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    q1, q2, q3 = quiz_dates["BCS-501"][1], quiz_dates["BCS-501"][2], quiz_dates["BCS-501"][3]

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # ---------------------------------------------------------------- A. Cycle I
        r = await client.get("/api/v1/quiz-eligibility/BCS-501/1", headers=admin_headers)
        q1_body = r.json()
        check("A1. Cycle I: Criterion I and Criterion II both = (Lecture % + Tutorial %) / 2, threshold 70",
              r.status_code == 200
              and q1_body["criterion_i"]["value"] == q1_body["average_pct"]
              and q1_body["criterion_ii"]["value"] == q1_body["average_pct"]
              and q1_body["criterion_i"]["threshold"] == 70.0
              and q1_body["criterion_ii"]["threshold"] == 70.0
              and q1_body["required_percentage"] == 70.0
              and "Lecture + Tutorial Average" in q1_body["criterion_i"]["name"]
              and "Lecture + Tutorial Average" in q1_body["criterion_ii"]["name"],
              f"cI={q1_body.get('criterion_i', {}).get('value')} "
              f"cII={q1_body.get('criterion_ii', {}).get('value')} avg={q1_body.get('average_pct')}")

        r = await client.get("/api/v1/quiz-eligibility/BNC-501/1", headers=admin_headers)
        bnc_q1 = r.json()
        check("A2. Cycle I no-tutorial subject: average collapses to lecture %, criteria equal, threshold 70",
              r.status_code == 200
              and bnc_q1["tutorial"]["total"] == 0
              and bnc_q1["average_pct"] == bnc_q1["lecture_pct"]
              and bnc_q1["criterion_i"]["value"] == bnc_q1["criterion_ii"]["value"] == bnc_q1["lecture_pct"]
              and bnc_q1["criterion_i"]["threshold"] == 70.0
              and bnc_q1["criterion_ii"]["threshold"] == 70.0,
              f"tut_tot={bnc_q1.get('tutorial', {}).get('total')} avg={bnc_q1.get('average_pct')} "
              f"lec={bnc_q1.get('lecture_pct')}")

        # ------------------------------------------------ B. Cycle II windows + formula
        r = await client.get("/api/v1/quiz-eligibility/BCS-501/2", headers=admin_headers)
        q2_body = r.json()
        w_i_2 = (q2_body["window_start"], q2_body["window_end"])
        check("B1. Cycle II Criterion I window = QT-I -> day before QT-II",
              date.fromisoformat(q2_body["window_start"]) == q1
              and date.fromisoformat(q2_body["window_end"]) == q2 - timedelta(days=1),
              f"got {w_i_2} expected ({q1}, {q2 - timedelta(days=1)})")

        async with AsyncSessionLocal() as db:
            repo = AttendanceRepository(db)
            counts_i2 = aggregate(await repo.get_subject_counts_between(
                admin_user.id, bcs501_id, q1, q2 - timedelta(days=1), exclude_quiz_day=True))
            counts_ii2 = aggregate(await repo.get_subject_counts_between(
                admin_user.id, bcs501_id, semester_start, q2 - timedelta(days=1), exclude_quiz_day=True))

        exp_i2, exp_ii2 = expected_avg(counts_i2), expected_avg(counts_ii2)
        check("B2. Cycle II both criteria use the same average formula; "
              "Criterion I = cycle-window average, Criterion II = cumulative-window average",
              q2_body["criterion_i"]["value"] == exp_i2
              and q2_body["criterion_ii"]["value"] == exp_ii2
              and q2_body["criterion_i"]["threshold"] == 75.0
              and q2_body["criterion_ii"]["threshold"] == 75.0
              and q2_body["required_percentage"] == 75.0,
              f"cI={q2_body['criterion_i']['value']} exp={exp_i2} "
              f"cII={q2_body['criterion_ii']['value']} exp={exp_ii2}")

        # ----------------------------------------------- C. Cycle III windows + formula
        r = await client.get("/api/v1/quiz-eligibility/BCS-501/3", headers=admin_headers)
        q3_body = r.json()
        check("C1. Cycle III Criterion I window = QT-II -> day before QT-III",
              date.fromisoformat(q3_body["window_start"]) == q2
              and date.fromisoformat(q3_body["window_end"]) == q3 - timedelta(days=1),
              f"got ({q3_body['window_start']}, {q3_body['window_end']}) "
              f"expected ({q2}, {q3 - timedelta(days=1)})")

        async with AsyncSessionLocal() as db:
            repo = AttendanceRepository(db)
            counts_i3 = aggregate(await repo.get_subject_counts_between(
                admin_user.id, bcs501_id, q2, q3 - timedelta(days=1), exclude_quiz_day=True))
            counts_ii3 = aggregate(await repo.get_subject_counts_between(
                admin_user.id, bcs501_id, semester_start, q3 - timedelta(days=1), exclude_quiz_day=True))

        exp_i3, exp_ii3 = expected_avg(counts_i3), expected_avg(counts_ii3)
        check("C2. Cycle III both criteria use the same average formula; "
              "Criterion I = cycle-window average, Criterion II = cumulative-window average",
              q3_body["criterion_i"]["value"] == exp_i3
              and q3_body["criterion_ii"]["value"] == exp_ii3
              and q3_body["criterion_i"]["threshold"] == 75.0
              and q3_body["criterion_ii"]["threshold"] == 75.0
              and q3_body["required_percentage"] == 75.0,
              f"cI={q3_body['criterion_i']['value']} exp={exp_i3} "
              f"cII={q3_body['criterion_ii']['value']} exp={exp_ii3}")

        # ----------------------------------- D/E. Must Attend / Safe Skip per criterion
        opt_i2 = expected_opt(counts_i2, 75.0)
        opt_ii2 = expected_opt(counts_ii2, 75.0)
        resp_i2, resp_ii2 = q2_body["criterion_i"]["optimization"], q2_body["criterion_ii"]["optimization"]
        check("D. Must Attend follows the corrected calculation (per-criterion optimizer "
              "on that criterion's own window counts)",
              resp_i2["lecture_deficit"] == opt_i2.lecture_deficit
              and resp_i2["tutorial_deficit"] == opt_i2.tutorial_deficit
              and resp_ii2["lecture_deficit"] == opt_ii2.lecture_deficit
              and resp_ii2["tutorial_deficit"] == opt_ii2.tutorial_deficit,
              f"cI got={resp_i2} exp=({opt_i2.lecture_deficit},{opt_i2.tutorial_deficit}) "
              f"cII got={resp_ii2} exp=({opt_ii2.lecture_deficit},{opt_ii2.tutorial_deficit})")

        check("E. Safe Skip follows the corrected calculation (per-criterion optimizer "
              "on that criterion's own window counts)",
              resp_i2["safe_skip_lecture"] == opt_i2.safe_skip_lecture
              and resp_i2["safe_skip_tutorial"] == opt_i2.safe_skip_tutorial
              and resp_ii2["safe_skip_lecture"] == opt_ii2.safe_skip_lecture
              and resp_ii2["safe_skip_tutorial"] == opt_ii2.safe_skip_tutorial,
              f"cI got=({resp_i2['safe_skip_lecture']},{resp_i2['safe_skip_tutorial']}) "
              f"exp=({opt_i2.safe_skip_lecture},{opt_i2.safe_skip_tutorial}) "
              f"cII got=({resp_ii2['safe_skip_lecture']},{resp_ii2['safe_skip_tutorial']}) "
              f"exp=({opt_ii2.safe_skip_lecture},{opt_ii2.safe_skip_tutorial})")

        best_total = min(total_deficit(resp_i2), total_deficit(resp_ii2))
        top_pick = resp_i2 if total_deficit(resp_i2) <= total_deficit(resp_ii2) else resp_ii2
        check("D2. Top-level Must Attend / Safe Skip = best route (min-deficit criterion)",
              q2_body["optimization"]["lecture_deficit"] == top_pick["lecture_deficit"]
              and q2_body["optimization"]["tutorial_deficit"] == top_pick["tutorial_deficit"]
              and q2_body["optimization"]["safe_skip_lecture"] == top_pick["safe_skip_lecture"]
              and q2_body["optimization"]["safe_skip_tutorial"] == top_pick["safe_skip_tutorial"]
              and q2_body["optimization"]["is_reachable"] == top_pick["is_reachable"],
              f"top={q2_body['optimization']} expected pick={top_pick} min_total={best_total}")

        # ------------------------------------------------------- F. Final = OR (live data)
        final = q2_body["final_criterion"]
        check("F1. Final eligibility = Criterion I OR Criterion II (live data)",
              final["combination"] == "Criterion I OR Criterion II"
              and final["passed"] == (q2_body["criterion_i"]["passed"] or q2_body["criterion_ii"]["passed"])
              and q2_body["is_eligible"] == (q2_body["state"] == "ELIGIBLE")
              and q2_body["is_eligible"] == final["passed"],
              f"combination={final.get('combination')} passed={final.get('passed')} "
              f"cI={q2_body['criterion_i']['passed']} cII={q2_body['criterion_ii']['passed']}")

        # F2. Rollback scenario where the routes DISAGREE: Criterion I fails on the
        #     cycle window while Criterion II passes on the cumulative window.
        async with AsyncSessionLocal() as db:
            service = EligibilityService(db)
            session_ids = (await db.execute(
                select(ClassSession.id).where(
                    ClassSession.subject_id == bcs501_id,
                    ClassSession.date.between(semester_start, q2 - timedelta(days=1)),
                ))).scalars().all()
            cycle_ids = (await db.execute(
                select(ClassSession.id).where(
                    ClassSession.subject_id == bcs501_id,
                    ClassSession.date.between(q1, q2 - timedelta(days=1)),
                ))).scalars().all()
            existing = (await db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.user_id == admin_user.id,
                    AttendanceRecord.class_session_id.in_(session_ids)))).scalars().all()
            for rec in existing:
                await db.delete(rec)
            await db.flush()

            # Attend everything except 4 cycle-window lectures and 1 cycle-window tutorial:
            # cycle-window avg ~61% (< 75, Criterion I fails); cumulative avg ~87% (>= 75,
            # Criterion II passes).
            skip = sorted(cycle_ids)[:5]  # arbitrary 4 L + 1 T mix from the cycle window
            for sid in session_ids:
                if sid in skip:
                    continue
                db.add(AttendanceRecord(user_id=admin_user.id, class_session_id=sid,
                                        status=AttendanceStatus.ATTENDED))
            result = await service.get_quiz_eligibility(admin_user.id, bcs501_id, 2, semester_start=semester_start)
            check("F2. Final eligibility = OR: Criterion I fails, Criterion II passes -> ELIGIBLE",
                  result.criterion_i.passed is False
                  and result.criterion_ii.passed is True
                  and result.final_criterion.passed is True
                  and result.is_eligible is True
                  and result.state == EligibilityState.ELIGIBLE
                  and result.optimization.lecture_deficit == 0
                  and result.optimization.tutorial_deficit == 0,
                  f"cI={result.criterion_i.passed} cII={result.criterion_ii.passed} "
                  f"eligible={result.is_eligible} state={result.state.value} "
                  f"opt=({result.optimization.lecture_deficit},{result.optimization.tutorial_deficit})")
            await db.rollback()

        # ------------------------- G. Quiz-Day-shaped sessions excluded from L/T counts
        async with AsyncSessionLocal() as db:
            repo = AttendanceRepository(db)
            excluded = await repo.get_subject_counts_between(
                admin_user.id, bcs501_id, q1, q2 - timedelta(days=1), exclude_quiz_day=True)
            included = await repo.get_subject_counts_between(
                admin_user.id, bcs501_id, q1, q2 - timedelta(days=1), exclude_quiz_day=False)
            agg_excluded = aggregate(excluded)
            agg_included = aggregate(included)
            quiz_day_shaped = (await db.execute(
                select(ClassSession).where(
                    ClassSession.subject_id == bcs501_id,
                    ClassSession.date == q1,
                    ClassSession.timetable_entry_id.is_(None),
                    ClassSession.is_extra.is_(False),
                    ClassSession.class_type == ClassType.LECTURE,
                ))).scalars().all()
        check("G. Quiz-Day-shaped sessions remain excluded from eligibility L/T counts "
              "(QT-I day inside the Cycle II window start)",
              len(quiz_day_shaped) == 1
              and agg_excluded['L']['tot'] == agg_included['L']['tot'] - 1
              and agg_excluded['T']['tot'] == agg_included['T']['tot'],
              f"quiz_day_shaped={len(quiz_day_shaped)} "
              f"excluded_L={agg_excluded['L']['tot']} included_L={agg_included['L']['tot']} "
              f"excluded_T={agg_excluded['T']['tot']} included_T={agg_included['T']['tot']}")

        # H. Normal timetable sessions remain included (rollback mutation)
        async with AsyncSessionLocal() as db:
            repo = AttendanceRepository(db)
            normal_sessions = (await db.execute(
                select(ClassSession).where(
                    ClassSession.subject_id == bcs501_id,
                    ClassSession.date.between(semester_start, q1 - timedelta(days=1)),
                    ClassSession.timetable_entry_id.is_not(None),
                    ClassSession.class_type == ClassType.LECTURE,
                ).order_by(ClassSession.date).limit(20))).scalars().all()
            with_attendance = set(await SessionRepository(db).get_session_ids_with_attendance(
                [s.id for s in normal_sessions]))
            target = next((s for s in normal_sessions if s.id not in with_attendance), None)
            delete_first = None
            if target is None:
                # Fall back to a session whose existing record is MISSED (flipping
                # it to ATTENDED still changes attended by exactly +1).
                for s in normal_sessions:
                    rec = (await db.execute(
                        select(AttendanceRecord).where(
                            AttendanceRecord.user_id == admin_user.id,
                            AttendanceRecord.class_session_id == s.id))).scalars().first()
                    if rec is not None and rec.status == AttendanceStatus.MISSED:
                        target, delete_first = s, rec
                        break
                if target is None:
                    target = normal_sessions[0]
                    delete_first = (await db.execute(
                        select(AttendanceRecord).where(
                            AttendanceRecord.user_id == admin_user.id,
                            AttendanceRecord.class_session_id == target.id))).scalars().first()
                    if delete_first is not None and delete_first.status == AttendanceStatus.ATTENDED:
                        raise RuntimeError("no neutral normal lecture available for check H")

            raw_before = await repo.get_subject_counts_between(
                admin_user.id, bcs501_id, semester_start, q1 - timedelta(days=1), exclude_quiz_day=True)
            expected_att = aggregate(raw_before)['L']['att'] + 1

            if delete_first is not None:
                await db.delete(delete_first)
                await db.flush()
            db.add(AttendanceRecord(user_id=admin_user.id, class_session_id=target.id,
                                    status=AttendanceStatus.ATTENDED))
            service = EligibilityService(db)
            result = await service.get_quiz_eligibility(admin_user.id, bcs501_id, 1, semester_start=semester_start)
            check("H. Normal timetable lecture/tutorial sessions remain included "
                  "(recording attendance on a normal lecture moves the count)",
                  result.lecture.attended == expected_att
                  and result.lecture.total == aggregate(raw_before)['L']['tot']
                  and result.lecture.total > 0
                  and result.tutorial.total > 0,
                  f"attended={result.lecture.attended} expected={expected_att} "
                  f"L_tot={result.lecture.total} T_tot={result.tutorial.total}")
            await db.rollback()

        # ------------- J. F2 regression: top-level optimization must be consistent
        # with the canonical state (rollback transaction; BCS-501 cycle II).
        # The F2 defect: a criterion with ZERO pending classes gets the engine's
        # 0/0 "nothing left to decide" optimization (is_reachable=False) and then
        # wins the old min-deficit top-level pick over a genuinely recoverable
        # Criterion II, leaving state=RECOVERABLE with a contradictory
        # top-level is_reachable=False. The fix (1) makes the zero-pending
        # early return target-aware (reachable when the current average already
        # meets the threshold) and (2) picks the best REACHABLE route at the
        # top level. This section shapes BCS-501 cycle-II attendance records so
        # that Criterion I (cycle window) is zero-pending and below threshold
        # while Criterion II (cumulative window) is recoverable, then asserts
        # the full reachability contract.
        async with AsyncSessionLocal() as db:
            service = EligibilityService(db)
            repo = AttendanceRepository(db)
            w_cyc = (q1, q2 - timedelta(days=1))
            w_cum = (semester_start, q2 - timedelta(days=1))

            async def lt_sessions(start, end):
                return (await db.execute(
                    select(ClassSession).where(
                        ClassSession.subject_id == bcs501_id,
                        ClassSession.date.between(start, end),
                        ClassSession.is_cancelled.is_(False),
                        ~(ClassSession.timetable_entry_id.is_(None)
                          & ~ClassSession.is_extra
                          & (ClassSession.class_type == ClassType.LECTURE)),
                    ).order_by(ClassSession.date, ClassSession.id))).scalars().all()

            cyc_sessions = await lt_sessions(*w_cyc)
            cum_sessions = await lt_sessions(*w_cum)
            pre_sessions = [s for s in cum_sessions if s.date < q1]
            cyc_L = [s for s in cyc_sessions if s.class_type == ClassType.LECTURE]
            cyc_T = [s for s in cyc_sessions if s.class_type == ClassType.TUTORIAL]
            pre_L = [s for s in pre_sessions if s.class_type == ClassType.LECTURE]
            pre_T = [s for s in pre_sessions if s.class_type == ClassType.TUTORIAL]
            CL, CT = len(cyc_L), len(cyc_T)
            PL, PT = len(pre_L), len(pre_T)

            # Deterministic bounded search for a shaping (cycle misses, pending
            # pre-q1 sessions, pre-q1 misses) satisfying, on the SERVICE-visible
            # counts (same L/T average formula as the engine):
            #   Criterion I:   zero pending, avg < 75  -> unreachable (0/0, False)
            #   Criterion II:  current < 75 <= best     -> not passed yet, recoverable
            def find_shape():
                for mL in range(0, CL + 1):
                    for mT in range(0, CT + 1):
                        if mL + mT == 0:
                            continue
                        lec_i = (CL - mL) / CL * 100.0 if CL else 0.0
                        tut_i = (CT - mT) / CT * 100.0 if CT else None
                        avg_i = (lec_i + tut_i) / 2.0 if tut_i is not None else lec_i
                        if avg_i >= 75.0:
                            continue
                        for pendL in (0, 1):
                            for pendT in (0, 1):
                                if pendL + pendT == 0:
                                    continue
                                for pmL in range(0, PL - pendL + 1):
                                    for pmT in range(0, PT - pendT + 1):
                                        paL, paT = PL - pmL - pendL, PT - pmT - pendT
                                        lec_ii = (paL + CL - mL) / (PL + CL) * 100.0
                                        tut_ii = ((paT + CT - mT) / (PT + CT) * 100.0
                                                  if (PT + CT) else None)
                                        cur_ii = (lec_ii + tut_ii) / 2.0 if tut_ii is not None else lec_ii
                                        lec_ii_best = (paL + pendL + CL - mL) / (PL + CL) * 100.0
                                        tut_ii_best = ((paT + pendT + CT - mT) / (PT + CT) * 100.0
                                                       if (PT + CT) else None)
                                        best_ii = (lec_ii_best + tut_ii_best) / 2.0 if tut_ii_best is not None else lec_ii_best
                                        if cur_ii < 75.0 <= best_ii:
                                            return (mL, mT, pendL, pendT, pmL, pmT)
                return None

            shape = find_shape()
            check("J0. F2 regression constructible on live BCS-501 cycle-II windows "
                  "(zero-pending unreachable Criterion I + recoverable Criterion II)",
                  shape is not None and CL > 0 and CT > 0 and PL > 0 and PT > 0,
                  f"CL={CL} CT={CT} PL={PL} PT={PT} shape={shape}")
            if shape is not None:
                mL, mT, pendL, pendT, pmL, pmT = shape

                # Shape the records (deterministic order: date, id).
                def mark(sessions, n_att, n_miss, n_pend):
                    for s in sessions[:n_att]:
                        db.add(AttendanceRecord(user_id=admin_user.id, class_session_id=s.id,
                                                status=AttendanceStatus.ATTENDED))
                    for s in sessions[n_att:n_att + n_miss]:
                        db.add(AttendanceRecord(user_id=admin_user.id, class_session_id=s.id,
                                                status=AttendanceStatus.MISSED))
                    # the trailing n_pend sessions stay unrecorded (pending)

                existing = (await db.execute(
                    select(AttendanceRecord).where(
                        AttendanceRecord.user_id == admin_user.id,
                        AttendanceRecord.class_session_id.in_([s.id for s in cum_sessions])))).scalars().all()
                for rec in existing:
                    await db.delete(rec)
                await db.flush()

                mark(cyc_L, CL - mL, mL, 0)
                mark(cyc_T, CT - mT, mT, 0)
                mark(pre_L, PL - pmL - pendL, pmL, pendL)
                mark(pre_T, PT - pmT - pendT, pmT, pendT)
                await db.flush()

                counts_i = aggregate(await repo.get_subject_counts_between(
                    admin_user.id, bcs501_id, *w_cyc, exclude_quiz_day=True))
                counts_ii = aggregate(await repo.get_subject_counts_between(
                    admin_user.id, bcs501_id, *w_cum, exclude_quiz_day=True))
                opt_i = optimize_attendance(
                    counts_i['L']['tot'], counts_i['L']['att'], counts_i['L']['miss'], counts_i['L']['pending'],
                    counts_i['T']['tot'], counts_i['T']['att'], counts_i['T']['miss'], counts_i['T']['pending'],
                    75.0)
                opt_ii = optimize_attendance(
                    counts_ii['L']['tot'], counts_ii['L']['att'], counts_ii['L']['miss'], counts_ii['L']['pending'],
                    counts_ii['T']['tot'], counts_ii['T']['att'], counts_ii['T']['miss'], counts_ii['T']['pending'],
                    75.0)

                result = await service.get_quiz_eligibility(admin_user.id, bcs501_id, 2, semester_start=semester_start)
                check("J1. F2: RECOVERABLE with zero-pending unreachable Criterion I + "
                      "recoverable Criterion II -> top-level picks the reachable route "
                      "(is_reachable=True, Criterion II's own optimization)",
                      result.state == EligibilityState.RECOVERABLE
                      and result.is_eligible is False
                      and result.recoverable is True
                      and result.criterion_i.passed is False
                      and result.criterion_i.optimization.is_reachable is False
                      and result.criterion_i.optimization.lecture_deficit == 0
                      and result.criterion_i.optimization.tutorial_deficit == 0
                      and result.criterion_ii.passed is False
                      and result.criterion_ii.optimization.is_reachable is True
                      and result.optimization.is_reachable is True
                      and result.optimization.lecture_deficit == opt_ii.lecture_deficit
                      and result.optimization.tutorial_deficit == opt_ii.tutorial_deficit
                      and result.optimization.safe_skip_lecture == opt_ii.safe_skip_lecture
                      and result.optimization.safe_skip_tutorial == opt_ii.safe_skip_tutorial
                      and (result.optimization.lecture_deficit + result.optimization.tutorial_deficit) >= 1,
                      f"state={result.state.value} top={result.optimization.model_dump()} "
                      f"opt_i={result.criterion_i.optimization.model_dump()} "
                      f"opt_ii={result.criterion_ii.optimization.model_dump()} "
                      f"counts_i={counts_i} counts_ii={counts_ii}")

                # J2. Converse: both criteria zero-pending and unreachable.
                for rec in (await db.execute(
                        select(AttendanceRecord).where(
                            AttendanceRecord.user_id == admin_user.id,
                            AttendanceRecord.class_session_id.in_([s.id for s in cum_sessions])))).scalars().all():
                    await db.delete(rec)
                await db.flush()
                for s in cum_sessions:
                    db.add(AttendanceRecord(user_id=admin_user.id, class_session_id=s.id,
                                            status=AttendanceStatus.MISSED))
                result = await service.get_quiz_eligibility(admin_user.id, bcs501_id, 2, semester_start=semester_start)
                check("J2. Converse: both criteria zero-pending and unreachable -> "
                      "NOT_ELIGIBLE with accurate unreachable top-level",
                      result.state == EligibilityState.NOT_ELIGIBLE
                      and result.criterion_i.optimization.is_reachable is False
                      and result.criterion_ii.optimization.is_reachable is False
                      and result.optimization.is_reachable is False
                      and result.optimization.lecture_deficit == 0
                      and result.optimization.tutorial_deficit == 0,
                      f"state={result.state.value} top={result.optimization.model_dump()}")

                # J3. Already eligible with zero pending: per-criterion and
                # top-level optimizations must be reachable (no contradictory
                # unreachable top-level state on an ELIGIBLE result).
                for rec in (await db.execute(
                        select(AttendanceRecord).where(
                            AttendanceRecord.user_id == admin_user.id,
                            AttendanceRecord.class_session_id.in_([s.id for s in cum_sessions])))).scalars().all():
                    await db.delete(rec)
                await db.flush()
                for s in cum_sessions:
                    db.add(AttendanceRecord(user_id=admin_user.id, class_session_id=s.id,
                                            status=AttendanceStatus.ATTENDED))
                result = await service.get_quiz_eligibility(admin_user.id, bcs501_id, 2, semester_start=semester_start)
                check("J3. Already eligible with zero pending: per-criterion + top-level "
                      "optimizations reachable with zero deficits",
                      result.state == EligibilityState.ELIGIBLE
                      and result.criterion_i.passed is True
                      and result.criterion_ii.passed is True
                      and result.criterion_i.optimization.is_reachable is True
                      and result.criterion_ii.optimization.is_reachable is True
                      and result.optimization.is_reachable is True
                      and result.optimization.lecture_deficit == 0
                      and result.optimization.tutorial_deficit == 0,
                      f"state={result.state.value} top={result.optimization.model_dump()} "
                      f"opt_i={result.criterion_i.optimization.model_dump()} "
                      f"opt_ii={result.criterion_ii.optimization.model_dump()}")

            await db.rollback()

        # -------------------------------------------------------------- Restoration
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

        check("I. database restored to the exact baseline "
              "(events/sessions/cancelled/extra/records/enrollments/subjects/quizzes/users)",
              (events_after, sessions_after, cancelled_after, extra_after, records_after,
               enrollments_after, subjects_after, quizzes_after, users_after)
              == (events_before, sessions_before, cancelled_before, extra_before, records_before,
                  enrollments_before, subjects_before, quizzes_before, users_before),
              f"events={events_before}->{events_after} sessions={sessions_before}->{sessions_after} "
              f"cancelled={cancelled_before}->{cancelled_after} extra={extra_before}->{extra_after} "
              f"records={records_before}->{records_after} enrollments={enrollments_before}->{enrollments_after} "
              f"subjects={subjects_before}->{subjects_after} quizzes={quizzes_before}->{quizzes_after} "
              f"users={users_before}->{users_after}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\nPhase 1 eligibility correction: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))