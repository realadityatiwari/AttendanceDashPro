"""
Phase 8.2 verification  -  Attendance page correction + laboratory domain.

Verifies the Phase 8.2 product contract end-to-end against the real database
(httpx ASGITransport + real DB + minted JWTs, the established pattern):

  1.  Attendance summary uses ACTUAL current-to-date session counts (every
      summary total == direct count of non-cancelled class_sessions <= today).
  2.  No fixed "14-lecture" denominator: totals are derived from the session
      table (a rollback-transaction extra lecture changes the total) and never
      from a constant.
  3.  Quiz-window changes do NOT change Attendance page totals (a rollback-
      transaction quiz-date change leaves the attendance summary identical).
  4.  Tutorial formula: Overall = (Lecture % + Tutorial %) / 2 (theory with
      tutorials), matching the attendance engine.
  5.  Lecture-only fallback: theory without tutorials -> Overall = Lecture %,
      no fabricated Tutorial 0/0 block.
  6.  Cancelled practical sessions are excluded from the attendance
      denominator (rollback-transaction cancellation drops total + pending by
      exactly 1, never creating Absent).
  7.  Practical attendance remains canonical class-session attendance (P
      counts == session table; laboratory_experiments is empty, so attendance
      cannot be experiment-derived).
  8.  Experiment completion is NOT inferred from attendance (lab summaries
      carry no experiment fields; nothing auto-designates mid-sem).
  9.  No fabricated experiment data (laboratory_experiments == 0 AND
      laboratory_records == 0, before and after).
 10.  Existing Quiz Eligibility results remain unchanged (labs 404, BCS-054
      Q3 = 2026-10-23, current-cycle invariants, payload shape).
 11.  Existing Phase 6 frozen behavior unchanged (exact baseline restoration:
      events/sessions/cancelled/extra/records/enrollments/subjects/quizzes/
      users/admins/lab tables + zero designations).
 12.  Attendance Health: summary.health == the engine's canonical
      classification; boundary values (75/65/60) verified in-process.
 13.  Mid-sem designation is session-bound (admin-only, tied to an actual
      PRACTICAL session, one per subject, replaced/cleared, never inferred
      from experiment counts) and attendance against the designated session
      flows through the normal attendance mutation.

State changes are this script's own artifacts (a designation + one attendance
record) and are removed in the finally block; rollback transactions never
commit. No old assertion is weakened. Run the frozen verifiers separately for
the full regression.

Usage:
    python scripts/verify_phase_8_2.py
"""
import asyncio
import sys
import uuid
from datetime import date
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
from app.models.academic import StudentEnrollment, Subject
from app.models.quiz import QuizSchedule, ScheduleStatus
from app.models.laboratory import LaboratoryExperiment, LaboratoryRecord
from app.models.enums import AttendanceStatus, ClassType, UserRole
from app.engines.attendance_engine import (
    compute_subject_stats,
    classify_attendance_health,
)
from app.engines.practical_occurrence import collapse_count_rows, group_practical_occurrences
from app.services.attendance_service import AttendanceService
from app.repositories.attendance_repo import AttendanceRepository
from sqlalchemy import select, func, delete

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


THEORY = {"BNC-501", "BCS-501", "BCS-502", "BCS-503", "BCS-054", "BCS-058"}
LABS = {"BCS-551", "BCS-552", "BCS-553"}


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
        scheduled_before = (await db.execute(
            select(func.count()).select_from(QuizSchedule).where(
                QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED))).scalar()
        users_before = (await db.execute(select(func.count()).select_from(User))).scalar()
        admins_before = (await db.execute(
            select(func.count()).select_from(User).where(User.role == UserRole.ADMIN))).scalar()
        lab_exp_before = (await db.execute(select(func.count()).select_from(LaboratoryExperiment))).scalar()
        lab_rec_before = (await db.execute(select(func.count()).select_from(LaboratoryRecord))).scalar()
        designated_before = (await db.execute(
            select(func.count()).select_from(ClassSession).where(ClassSession.designation.isnot(None)))).scalar()

        admin_user = (await db.execute(select(User).where(User.roll_number == "2401220100027"))).scalars().first()
        student_user = (await db.execute(select(User).where(User.roll_number == "9999999999999"))).scalars().first()
        subject_ids = {s.code: s.id for s in (await db.execute(select(Subject))).scalars().all()}
        today = date.today()

        # Track lab correction: a 2-hour laboratory block (two contiguous
        # timetable periods) is ONE attendance occurrence. Expected per-subject
        # totals are the canonical occurrence collapse of the raw session table
        # (app.engines.practical_occurrence) — never a per-period row count.
        raw = (await db.execute(
            select(ClassSession.subject_id, ClassSession.class_type, ClassSession.date,
                   ClassSession.is_cancelled, TimetableEntry.start_time, TimetableEntry.end_time,
                   AttendanceRecord.status)
            .outerjoin(TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id)
            .outerjoin(AttendanceRecord, (AttendanceRecord.class_session_id == ClassSession.id)
                       & (AttendanceRecord.user_id == admin_user.id))
            .where(ClassSession.date <= today)
            .order_by(ClassSession.date, TimetableEntry.start_time.asc().nulls_last(),
                      ClassSession.id)
        )).all()
        by_subject: dict = {}
        for (sid, ct, d, cancelled, st, et, status) in raw:
            by_subject.setdefault(sid, []).append({
                "subject_id": sid, "class_type": ct, "date": d,
                "is_cancelled": cancelled, "start_time": st, "end_time": et,
                "status": status,
            })
        expected_totals = {}
        for sid, srows in by_subject.items():
            counts = {"LECTURE": 0, "TUTORIAL": 0, "PRACTICAL": 0}
            for _sid, ct, _st in collapse_count_rows(srows, include_subject=True):
                counts[ct.name] += 1
            expected_totals[sid] = counts
        db_totals = {
            code: {
                "lecture": expected_totals[subject_ids[code]]["LECTURE"],
                "tutorial": expected_totals[subject_ids[code]]["TUTORIAL"],
                "practical": expected_totals[subject_ids[code]]["PRACTICAL"],
            }
            for code in THEORY | LABS
        }

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    student_token = create_access_token(str(student_user.id), student_user.roll_number)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    created_record_ids: list[uuid.UUID] = []
    temp_session_id: uuid.UUID | None = None

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # --- 1. Current-to-date session counts --------------------------------
            all_ok = True
            detail = ""
            for code in sorted(THEORY | LABS):
                r = await client.get(f"/api/v1/attendance/summary/{code}", headers=admin_headers)
                b = r.json()
                for key in ("lecture", "tutorial", "practical"):
                    got = b[key]["total"]
                    exp = db_totals[code][key]
                    if got != exp:
                        all_ok = False
                        detail += f"{code}:{key}={got}vs{exp} "
            check("1. summary totals == actual current-to-date session counts "
                  "(non-cancelled sessions <= today per subject/type; a 2-hour "
                  "lab block counts as ONE practical occurrence)",
                  all_ok, detail)

            # --- 2. No fixed denominator (derived from the session table) ---------
            async with AsyncSessionLocal() as db:
                base = await AttendanceService(db).get_summary(
                    admin_user.id, subject_ids["BCS-501"], "BCS-501", today)
                base_total = base.lecture.total
                # Insert one extra lecture INSIDE the transaction; the summary must
                # see it (proving it reads class_sessions, not a fixed constant).
                extra = ClassSession(
                    subject_id=subject_ids["BCS-501"], date=today,
                    class_type=ClassType.LECTURE, is_extra=True, is_cancelled=False,
                )
                db.add(extra)
                await db.flush()
                after = await AttendanceService(db).get_summary(
                    admin_user.id, subject_ids["BCS-501"], "BCS-501", today)
                await db.rollback()
            check("2. no fixed 14-lecture denominator: a rollback-transaction extra "
                  "lecture session changes the summary total (derived, not constant)",
                  after.lecture.total == base_total + 1,
                  f"base={base_total} after={after.lecture.total}")

            # --- 3. Quiz-window changes do not change Attendance totals ------------
            async with AsyncSessionLocal() as db:
                qs = (await db.execute(
                    select(QuizSchedule).where(QuizSchedule.subject_id == subject_ids["BCS-501"])
                )).scalars().first()
                base_summary = await AttendanceService(db).get_summary(
                    admin_user.id, subject_ids["BCS-501"], "BCS-501", today)
                base_counts = (base_summary.lecture.total, base_summary.tutorial.total,
                               base_summary.current_avg_pct)
                # Move the quiz date inside the transaction; the attendance summary
                # (which never reads quiz_schedules) must stay identical.
                qs.date = today
                await db.flush()
                after_summary = await AttendanceService(db).get_summary(
                    admin_user.id, subject_ids["BCS-501"], "BCS-501", today)
                after_counts = (after_summary.lecture.total, after_summary.tutorial.total,
                                after_summary.current_avg_pct)
                await db.rollback()
            check("3. quiz-window changes do NOT change Attendance page totals "
                  "(summary ignores quiz_schedules by construction)",
                  base_counts == after_counts,
                  f"before={base_counts} after={after_counts}")

            # --- 4. Tutorial formula ----------------------------------------------
            r = await client.get("/api/v1/attendance/summary/BCS-501", headers=admin_headers)
            b = r.json()
            lec = b["current_lecture_pct"]
            tut = b["current_tutorial_pct"]
            avg = b["current_avg_pct"]
            exp_avg = (lec + tut) / 2.0 if lec is not None and tut is not None else None
            async with AsyncSessionLocal() as db:
                raw = await AttendanceRepository(db).get_subject_counts_up_to_date(
                    admin_user.id, subject_ids["BCS-501"], today)
                counts = {"L": {"tot": 0, "att": 0, "miss": 0, "pending": 0},
                          "T": {"tot": 0, "att": 0, "miss": 0, "pending": 0},
                          "P": {"tot": 0, "att": 0, "miss": 0, "pending": 0}}
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
                engine_summary = compute_subject_stats("BCS-501", {"counts": counts})
            check("4. tutorial formula: Overall = (Lecture % + Tutorial %) / 2, "
                  "identical to the attendance engine",
                  exp_avg is not None and abs(avg - exp_avg) < 1e-9
                  and abs(avg - engine_summary.current_avg_pct) < 1e-9,
                  f"avg={avg} exp={exp_avg} engine={engine_summary.current_avg_pct}")

            # --- 5. Lecture-only fallback -----------------------------------------
            r = await client.get("/api/v1/attendance/summary/BNC-501", headers=admin_headers)
            b = r.json()
            check("5. lecture-only fallback: no-tutorial theory subject -> Overall = "
                  "Lecture %, no fabricated Tutorial 0/0",
                  b["tutorial"]["total"] == 0
                  and b["current_avg_pct"] == b["current_lecture_pct"],
                  f"tutorial_total={b['tutorial']['total']} avg={b['current_avg_pct']} "
                  f"lec={b['current_lecture_pct']}")

            # --- 6. Cancelled practical sessions excluded -------------------------
            async with AsyncSessionLocal() as db:
                # Cancel an UNATTENDED past practical BLOCK (a 2-hour lab is ONE
                # occurrence; pick a block with no admin record on ANY member) so
                # the exclusion is observable purely on total/pending.
                p_raw = (await db.execute(
                    select(ClassSession.id, ClassSession.date, ClassSession.is_cancelled,
                           TimetableEntry.start_time, TimetableEntry.end_time,
                           AttendanceRecord.status)
                    .outerjoin(TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id)
                    .outerjoin(AttendanceRecord, (AttendanceRecord.class_session_id == ClassSession.id)
                               & (AttendanceRecord.user_id == admin_user.id))
                    .where(ClassSession.subject_id == subject_ids["BCS-553"],
                           ClassSession.class_type == ClassType.PRACTICAL,
                           ClassSession.date <= today)
                    .order_by(ClassSession.date, TimetableEntry.start_time.asc().nulls_last(),
                              ClassSession.id)
                )).all()
                p_rows = [{"id": r.id, "date": r.date, "class_type": ClassType.PRACTICAL,
                           "is_cancelled": r.is_cancelled, "start_time": r.start_time,
                           "end_time": r.end_time, "status": r.status} for r in p_raw]
                occs = group_practical_occurrences(p_rows)
                target_block = next(
                    o for o in occs if not o["is_cancelled"] and o["status"] is None
                )
                past_prac = (await db.execute(
                    select(ClassSession).where(ClassSession.id == target_block["id"])
                )).scalars().first()
                svc = AttendanceService(db)
                before = await svc.get_summary(admin_user.id, subject_ids["BCS-553"], "BCS-553", today)
                b_total, b_att, b_miss, b_pend = (before.practical.total, before.practical.attended,
                                                  before.practical.missed, before.practical.pending)
                past_prac.is_cancelled = True
                await db.flush()
                after_c = await svc.get_summary(admin_user.id, subject_ids["BCS-553"], "BCS-553", today)
                a_total, a_att, a_miss, a_pend = (after_c.practical.total, after_c.practical.attended,
                                                  after_c.practical.missed, after_c.practical.pending)
                await db.rollback()
            check("6. cancelled practical sessions excluded from the attendance "
                  "denominator (never Pending/Absent)",
                  a_total == b_total - 1 and a_pend == b_pend - 1
                  and a_att == b_att and a_miss == b_miss,
                  f"total {b_total}->{a_total} att {b_att}->{a_att} miss {b_miss}->{a_miss} "
                  f"pend {b_pend}->{a_pend}")

            # --- 7. Practical attendance is canonical session attendance ----------
            all_ok = True
            detail = ""
            for code in sorted(LABS):
                r = await client.get(f"/api/v1/attendance/summary/{code}", headers=admin_headers)
                b = r.json()
                if b["practical"]["total"] != db_totals[code]["practical"]:
                    all_ok = False
                    detail += f"{code}:{b['practical']['total']}vs{db_totals[code]['practical']} "
            check("7. practical attendance remains canonical class-session attendance "
                  "(P totals == occurrence collapse of the session table; not "
                  "experiment-derived)",
                  all_ok and lab_exp_before == 0, detail)

            # --- 8. Experiment completion not inferred from attendance -------------
            r = await client.get("/api/v1/attendance/summary/BCS-551", headers=admin_headers)
            b = r.json()
            check("8. experiment completion NOT inferred from attendance: lab summary "
                  "carries no experiment fields and nothing auto-designates mid-sem",
                  "experiment" not in " ".join(b.keys())
                  and b["mid_sem_session_id"] is None and b["mid_sem_session_date"] is None,
                  f"keys={sorted(b.keys())}")

            # --- 9. No fabricated experiment data ----------------------------------
            check("9. no fabricated experiment data (laboratory tables empty)",
                  lab_exp_before == 0 and lab_rec_before == 0,
                  f"experiments={lab_exp_before} records={lab_rec_before}")

            # --- 10. Quiz Eligibility unchanged ------------------------------------
            lab_codes = {}
            for code in LABS:
                rr = await client.get(f"/api/v1/quiz-eligibility/{code}/1", headers=admin_headers)
                lab_codes[code] = rr.status_code
            r_bcs = await client.get("/api/v1/quiz-eligibility/BCS-054/3", headers=admin_headers)
            bcs = r_bcs.json()
            r_cc = await client.get("/api/v1/quiz-eligibility/current-cycle", headers=admin_headers)
            cc = r_cc.json()
            r_501 = await client.get("/api/v1/quiz-eligibility/BCS-501/1", headers=admin_headers)
            b501 = r_501.json()
            check("10. Quiz Eligibility unchanged: labs 404, BCS-054 Q3 = 2026-10-23, "
                  "current-cycle Quiz I 2026-08-24, payload shape intact",
                  lab_codes == {"BCS-551": 404, "BCS-552": 404, "BCS-553": 404}
                  and bcs["quiz_date"] == "2026-10-23" and bcs["window_end"] == "2026-10-22"
                  and cc["quiz_cycle"] == 1 and cc["quiz_date"] == "2026-08-24"
                  and cc["basis"] == "next_upcoming"
                  and all(k in b501 for k in ("state", "is_eligible", "window_start",
                                              "window_end", "criterion_i", "criterion_ii",
                                              "optimization")),
                  f"labs={lab_codes} q3={bcs.get('quiz_date')} cc={cc}")

            # --- 12. Attendance Health classification ------------------------------
            r = await client.get("/api/v1/analytics/overview", headers=admin_headers)
            ov = r.json()
            all_ok = True
            detail = ""
            for item in ov["subjects"]:
                exp = classify_attendance_health(item["current_avg_pct"])
                if item["health"] != exp:
                    all_ok = False
                    detail += f"{item['subject_code']}:{item['health']}vs{exp} "
            bounds = {
                59.9: "CRITICAL", 60.0: "AT_RISK", 64.9: "AT_RISK", 65.0: "WATCH",
                74.9: "WATCH", 75.0: "HEALTHY", None: None,
            }
            all_bounds = all(classify_attendance_health(v) == exp for v, exp in bounds.items())
            check("12. Attendance Health == engine classification (per-subject) with "
                  "canonical boundaries (>=75 HEALTHY, 65-<75 WATCH, 60-<65 AT_RISK, "
                  "<60 CRITICAL)",
                  all_ok and all_bounds, detail)

            # --- 13. Mid-sem designation is session-bound (admin-only) -------------
            async with AsyncSessionLocal() as db:
                target = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.subject_id == subject_ids["BCS-553"],
                        ClassSession.class_type == ClassType.PRACTICAL,
                        ClassSession.date <= today,
                        ClassSession.is_cancelled.is_(False),
                        ~ClassSession.id.in_(select(AttendanceRecord.class_session_id).where(
                            AttendanceRecord.user_id == admin_user.id)),
                    ).order_by(ClassSession.date).limit(1)
                )).scalars().first()
                other = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.subject_id == subject_ids["BCS-553"],
                        ClassSession.class_type == ClassType.PRACTICAL,
                        ClassSession.id != target.id,
                    ).order_by(ClassSession.date.desc()).limit(1)
                )).scalars().first()
                # A session of ANOTHER subject (BCS-501 LECTURE) must be rejected
                # even though it exists: the designation is subject-scoped.
                foreign_sess = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.subject_id == subject_ids["BCS-501"],
                        ClassSession.class_type == ClassType.LECTURE,
                    ).limit(1)
                )).scalars().first()

            # BCS-553 has no LECTURE sessions of its own, so create a temporary
            # one to prove the class-type rule for the same subject (removed in
            # the finally block; a lecture on a lab subject is an academic oddity,
            # but the session-level rule must reject it regardless).
            async with AsyncSessionLocal() as db:
                temp_lec = ClassSession(
                    subject_id=subject_ids["BCS-553"], date=today,
                    class_type=ClassType.LECTURE, is_extra=True, is_cancelled=False,
                )
                db.add(temp_lec)
                await db.commit()
                temp_session_id = temp_lec.id
                lec_sess = temp_lec.id

            # Student cannot designate.
            r = await client.put("/api/v1/laboratory/BCS-553/mid-sem", headers=student_headers,
                                 json={"class_session_id": str(target.id)})
            check("13a. student PUT mid-sem designation -> 403 (admin-only authority)",
                  r.status_code == 403, f"got {r.status_code}")

            # Non-PRACTICAL session and foreign-subject session are rejected.
            r = await client.put("/api/v1/laboratory/BCS-553/mid-sem", headers=admin_headers,
                                 json={"class_session_id": str(lec_sess)})
            check("13b. designating a LECTURE session -> 400 (only PRACTICAL sessions)",
                  r.status_code == 400, f"got {r.status_code} {r.text[:120]}")
            r = await client.put("/api/v1/laboratory/BCS-553/mid-sem", headers=admin_headers,
                                 json={"class_session_id": str(foreign_sess.id)})
            check("13c. designating a session of another subject -> 400",
                  r.status_code == 400, f"got {r.status_code} {r.text[:120]}")

            # Valid designation: tied to the actual session; one per subject; replace.
            r = await client.put("/api/v1/laboratory/BCS-553/mid-sem", headers=admin_headers,
                                 json={"class_session_id": str(other.id)})
            ok_replace_1 = r.status_code == 200 and r.json()["session_id"] == str(other.id)
            r2 = await client.put("/api/v1/laboratory/BCS-553/mid-sem", headers=admin_headers,
                                  json={"class_session_id": str(target.id)})
            ok_replace_2 = r2.status_code == 200 and r2.json()["session_id"] == str(target.id)
            r_get = await client.get("/api/v1/laboratory/BCS-553/mid-sem", headers=admin_headers)
            ok_get = r_get.status_code == 200 and r_get.json()["session_id"] == str(target.id)
            r_sum = await client.get("/api/v1/attendance/summary/BCS-553", headers=admin_headers)
            ok_sum = r_sum.json()["mid_sem_session_id"] == str(target.id) \
                and r_sum.json()["mid_sem_session_date"] == target.date.isoformat()
            check("13d. mid-sem designation is an ADMIN-controlled session-level fact "
                  "(actual PRACTICAL session, replaced/one per subject, exposed on "
                  "the summary with the REAL session date)",
                  ok_replace_1 and ok_replace_2 and ok_get and ok_sum,
                  f"put1={ok_replace_1} put2={ok_replace_2} get={ok_get} sum={ok_sum}")

            # Designation does not gate attendance: normal mutation records against it.
            r = await client.post("/api/v1/attendance", headers=admin_headers, json={
                "class_session_id": str(target.id), "status": "Attended"})
            if r.status_code == 200:
                created_record_ids.append(uuid.UUID(r.json()["id"]))
            check("13e. attendance against the designated session flows through the "
                  "normal attendance mutation (200)",
                  r.status_code == 200, f"got {r.status_code} {r.text[:150]}")

            # Clear designation; summary returns to null; attendance record untouched.
            r = await client.delete("/api/v1/laboratory/BCS-553/mid-sem", headers=admin_headers)
            ok_clear = r.status_code == 200 and r.json()["designated"] is False
            r_sum = await client.get("/api/v1/attendance/summary/BCS-553", headers=admin_headers)
            ok_cleared = r_sum.json()["mid_sem_session_id"] is None
            check("13f. clearing the designation restores null state (attendance "
                  "records on the session untouched)",
                  ok_clear and ok_cleared, f"clear={ok_clear} summary={ok_cleared}")

        # --- 11. Baseline restoration (checked after cleanup) ----------------------
    finally:
        # Remove every artifact this script created: the attendance record, the
        # temporary lecture session, and any leftover designation.
        async with AsyncSessionLocal() as db:
            if created_record_ids:
                await db.execute(delete(AttendanceRecord).where(
                    AttendanceRecord.id.in_(created_record_ids)))
            if temp_session_id is not None:
                await db.execute(delete(ClassSession).where(ClassSession.id == temp_session_id))
            await db.execute(
                ClassSession.__table__.update().where(
                    ClassSession.designation.isnot(None)
                ).values(designation=None)
            )
            await db.commit()

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
        lab_exp_after = (await db.execute(select(func.count()).select_from(LaboratoryExperiment))).scalar()
        lab_rec_after = (await db.execute(select(func.count()).select_from(LaboratoryRecord))).scalar()
        designated_after = (await db.execute(
            select(func.count()).select_from(ClassSession).where(ClassSession.designation.isnot(None)))).scalar()

    check("11. Phase 6 frozen behavior unchanged: exact baseline restored "
          "(events/sessions/cancelled/extra/records/enrollments/subjects/quizzes/"
          "scheduled/users/admins/lab tables + zero designations)",
          (events_after, sessions_after, cancelled_after, extra_after, records_after,
           enrollments_after, subjects_after, quizzes_after, scheduled_after, users_after,
           admins_after, lab_exp_after, lab_rec_after, designated_after)
          == (events_before, sessions_before, cancelled_before, extra_before, records_before,
              enrollments_before, subjects_before, quizzes_before, scheduled_before, users_before,
              admins_before, lab_exp_before, lab_rec_before, designated_before),
          f"events={events_before}->{events_after} sessions={sessions_before}->{sessions_after} "
          f"cancelled={cancelled_before}->{cancelled_after} extra={extra_before}->{extra_after} "
          f"records={records_before}->{records_after} enrollments={enrollments_before}->{enrollments_after} "
          f"subjects={subjects_before}->{subjects_after} quizzes={quizzes_before}->{quizzes_after} "
          f"scheduled={scheduled_before}->{scheduled_after} users={users_before}->{users_after} "
          f"admins={admins_before}->{admins_after} lab_exp={lab_exp_before}->{lab_exp_after} "
          f"lab_rec={lab_rec_before}->{lab_rec_after} designated={designated_before}->{designated_after}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\nPhase 8.2 verification: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
