"""
Quiz-day boundary regression verifier (official SRMCEM rule).

The Criterion I window for quiz cycle N > 1 starts ON the previous
quiz date (inclusive) and ends the day before the current quiz:

    Criterion I, QT-I:   commencement  -> day before QT-I
    Criterion I, QT-II:  QT-I date     -> day before QT-II
    Criterion I, QT-III: QT-II date    -> day before QT-III

Therefore the SAME date is:
  - EXCLUDED from the current quiz's Criterion I (it is one day
    past that window's end), and
  - INCLUDED in the next quiz's Criterion I (it is the inclusive
    window start) — including the quiz-day-shaped occurrence
    (class_type=LECTURE, is_extra=false, timetable_entry_id IS
    NULL) materialized on it. The current quiz day is excluded
    purely by the window end (quiz date - 1); no shape-based
    filter is applied anywhere in the eligibility path.

Mandatory scenario — BCS-058 "Data Warehousing & Data Mining", a
Department Elective-II subject whose seeded schedule is exactly
these dates (so the DE-II elective case is covered as well):

    QT-I   = 2026-09-11
    QT-II  = 2026-10-05
    QT-III = 2026-10-26

Fixture (created, then exactly cleaned up in the finally block):
  On 2026-09-11 (QT-I date = inclusive start of the QT-II window):
    A. a normal timetable lecture (LECTURE, timetable-bound)
    B. a quiz-day-shaped lecture (LECTURE, is_extra=false,
       timetable_entry_id=NULL, elective_slot=ELECTIVE_II — the
       exact shape materialize_quiz_day_sessions.py produces)
    both marked ATTENDED for the zero-record student.
  On 2026-10-05 (QT-II day):
    C. a quiz-day-shaped lecture, marked ATTENDED.

Expected (post-fix):
  1. QT-II Criterion I counts BOTH 09-11 sessions (L.total +2,
     L.attended +2) — single-subject path AND batch path.
  2. QT-I (cycle-1) counts are UNCHANGED by the fixture (09-11 is
     outside [commencement, 09-10]): the same date is excluded
     from QT-I but included in QT-II.
  3. Session C on the QT-II day does NOT affect QT-II Criterion I
     (window stays [09-11, 10-04]) but IS counted in QT-III
     Criterion I (window [10-05, 10-25]) — the QT-II date is the
     inclusive start of QT-III's window.
  4. Criterion II (cumulative [commencement, 10-04]) includes the
     09-11 sessions: repo decomposition full == before + q1 + after,
     and the criterion II percentage equals the pooled reference.
  5. Common subject BCS-501 (QT-I 2026-08-27): its cycle-2 window
     [08-27, 09-16] includes the 08-27 sessions (decomposition
     full == after + q1) — the materialized quiz-day occurrence on
     the previous quiz date counts toward the next cycle.
  6. HTTP end-to-end: the /api/v1/quiz-eligibility/BCS-058/2
     response matches the service result for the same user.

Usage:
    python scripts/verify_quiz_day_boundary_fix.py
"""
import asyncio
import sys
from datetime import date, time, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User, Section
from app.models.timetable import ClassSession, TimetableEntry
from app.models.attendance import AttendanceRecord
from app.models.academic import Subject, StudentElectiveChoice, StudentEnrollment
from app.models.enums import AttendanceStatus, ClassType, ElectiveSlot
from app.models.quiz import QuizSchedule
from app.repositories.quiz_repo import QuizRepository
from app.repositories.attendance_repo import AttendanceRepository
from app.services.eligibility_service import EligibilityService
from app.services.student_context_service import StudentContextService
from app.engines.attendance_engine import (
    normalize_class_type,
    pooled_pct as _pooled_pct,
)
from sqlalchemy import select

# Mandatory scenario dates (BCS-058 seeded schedule).
QT_I = date(2026, 9, 11)
QT_II = date(2026, 10, 5)
QT_III = date(2026, 10, 26)
ELECTIVE_SUBJECT_CODE = "BCS-058"   # Department Elective-II
COMMON_SUBJECT_CODE = "BCS-501"     # common (non-elective) theory subject

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def aggregate(raw_counts) -> dict:
    """Raw repo (class_type, status) rows -> canonical L/T count shape."""
    out = {
        "L": {"tot": 0, "att": 0, "miss": 0, "pending": 0},
        "T": {"tot": 0, "att": 0, "miss": 0, "pending": 0},
    }
    for class_type_str, status in raw_counts:
        t = normalize_class_type(class_type_str.value)
        if t not in out:
            continue
        out[t]["tot"] += 1
        if status == AttendanceStatus.ATTENDED:
            out[t]["att"] += 1
        elif status == AttendanceStatus.MISSED:
            out[t]["miss"] += 1
        else:
            out[t]["pending"] += 1
    return out


def counts_equal(a: dict, b: dict) -> bool:
    return all(a[k][m] == b[k][m] for k in ("L", "T") for m in ("tot", "att", "miss", "pending"))


def counts_add(*dicts) -> dict:
    out = {
        "L": {"tot": 0, "att": 0, "miss": 0, "pending": 0},
        "T": {"tot": 0, "att": 0, "miss": 0, "pending": 0},
    }
    for d in dicts:
        for k in ("L", "T"):
            for m in ("tot", "att", "miss", "pending"):
                out[k][m] += d[k][m]
    return out


def pooled_from(counts: dict):
    l, t = counts["L"], counts["T"]
    return _pooled_pct(l["att"], l["tot"], t["att"], t["tot"])


async def main() -> int:
    async with AsyncSessionLocal() as db:
        # ---------------- resolve the fixture targets ----------------
        repo = QuizRepository(db)
        bcs058 = (await db.execute(
            select(Subject).where(Subject.code == ELECTIVE_SUBJECT_CODE)
        )).scalars().first()
        bcs501 = (await db.execute(
            select(Subject).where(Subject.code == COMMON_SUBJECT_CODE)
        )).scalars().first()
        student = (await db.execute(
            select(User).where(User.roll_number == "9999999999999")
        )).scalars().first()
        admin = (await db.execute(
            select(User).where(User.roll_number == "2401220100027")
        )).scalars().first()
        any_section = (await db.execute(select(Section).limit(1))).scalars().first()
        # A non-elective timetable entry to bind the fixture's normal
        # lecture (elective_slot NULL -> plain first-branch attribution).
        anchor_entry = (await db.execute(
            select(TimetableEntry).where(TimetableEntry.elective_slot.is_(None)).limit(1)
        )).scalars().first()

        if None in (bcs058, bcs501, student, admin, any_section):
            print("FATAL: seed baseline missing (subjects / test users / section)")
            return 1

        # Canonical semester start for the student (same resolution as the API).
        ctx = await StudentContextService(db).get_placement(student)
        semester_start = ctx.semester_start if ctx.semester_start is not None else date.today()

        # ---------------- 0. Preconditions ----------------
        effective = await repo.get_effective_quiz_dates_for_subject(bcs058.id)
        check("0. BCS-058 effective quiz dates are the mandatory scenario "
              "(QT-I 2026-09-11, QT-II 2026-10-05, QT-III 2026-10-26)",
              effective == [(1, QT_I), (2, QT_II), (3, QT_III)],
              f"got {effective}")
        if effective != [(1, QT_I), (2, QT_II), (3, QT_III)]:
            print("FATAL: seeded BCS-058 schedule does not match the mandatory "
                  "scenario; run the academic baseline seed first.")
            return 1

        service = EligibilityService(db)
        att_repo = AttendanceRepository(db)

        # Pre-existing quiz-day-shaped session on the QT-I date (created by
        # materialize_quiz_day_sessions.py), if present.
        preexisting_shaped = (await db.execute(
            select(ClassSession).where(
                ClassSession.subject_id == bcs058.id,
                ClassSession.date == QT_I,
                ClassSession.timetable_entry_id.is_(None),
                ClassSession.is_extra.is_(False),
                ClassSession.class_type == ClassType.LECTURE,
            )
        )).scalars().all()
        print(f"  [info] pre-existing quiz-day-shaped session(s) on {QT_I}: "
              f"{len(preexisting_shaped)}")

        # ---------------- baselines (before fixture) ----------------
        base_c1 = aggregate(await att_repo.get_subject_counts_between(
            student.id, bcs058.id, semester_start, QT_I - timedelta(days=1)))
        base_c2 = aggregate(await att_repo.get_subject_counts_between(
            student.id, bcs058.id, QT_I, QT_II - timedelta(days=1)))
        base_c2_after = aggregate(await att_repo.get_subject_counts_between(
            student.id, bcs058.id, QT_I + timedelta(days=1), QT_II - timedelta(days=1)))
        base_c2_q1 = aggregate(await att_repo.get_subject_counts_between(
            student.id, bcs058.id, QT_I, QT_I))
        base_cum = aggregate(await att_repo.get_subject_counts_between(
            student.id, bcs058.id, semester_start, QT_II - timedelta(days=1)))
        base_c3 = aggregate(await att_repo.get_subject_counts_between(
            student.id, bcs058.id, QT_II, QT_III - timedelta(days=1)))

        # Elective-II chooser of BCS-058 (if any) for the elective-path delta.
        chooser = (await db.execute(
            select(User).join(StudentElectiveChoice,
                              StudentElectiveChoice.user_id == User.id).where(
                StudentElectiveChoice.subject_id == bcs058.id).limit(1)
        )).scalars().first()
        chooser_base_c2 = None
        if chooser is not None:
            chooser_base_c2 = aggregate(await att_repo.get_subject_counts_between(
                chooser.id, bcs058.id, QT_I, QT_II - timedelta(days=1)))

        # ---------------- fixture: sessions A, B on the QT-I date ----
        # A. normal timetable lecture (timetable-bound)
        fixture_entry = TimetableEntry(
            subject_id=bcs058.id,
            day_of_week=QT_I.weekday(),          # 0=Monday..6=Sunday
            start_time=time(9, 0),
            end_time=time(10, 0),
            class_type=ClassType.LECTURE,
            section_id=any_section.id,
            elective_slot=None,                  # non-elective entry
        )
        db.add(fixture_entry)
        await db.flush()
        session_a = ClassSession(
            subject_id=bcs058.id,
            date=QT_I,
            class_type=ClassType.LECTURE,
            is_extra=False,
            is_cancelled=False,
            timetable_entry_id=fixture_entry.id,
            elective_slot=None,
        )
        # B. quiz-day-shaped lecture (the exact materialized shape)
        session_b = ClassSession(
            subject_id=bcs058.id,
            date=QT_I,
            class_type=ClassType.LECTURE,
            is_extra=False,
            is_cancelled=False,
            timetable_entry_id=None,
            elective_slot=ElectiveSlot.ELECTIVE_II,
        )
        db.add(session_a)
        db.add(session_b)
        await db.flush()
        rec_a = AttendanceRecord(user_id=student.id, class_session_id=session_a.id,
                                 status=AttendanceStatus.ATTENDED)
        rec_b = AttendanceRecord(user_id=student.id, class_session_id=session_b.id,
                                 status=AttendanceStatus.ATTENDED)
        db.add(rec_a)
        db.add(rec_b)
        await db.flush()

        fixture_session_ids = [session_a.id, session_b.id]
        fixture_record_ids = [rec_a.id, rec_b.id]
        session_c_id = None
        rec_c_id = None

        try:
            # ---------------- 1. QT-II Criterion I includes BOTH ----
            r2 = await service.get_quiz_eligibility(
                student.id, bcs058.id, 2, semester_start=semester_start)
            check("1. QT-II Criterion I window = [QT-I 2026-09-11, 2026-10-04] "
                  "(previous quiz date inclusive, quiz day - 1)",
                  r2.window_start == QT_I and r2.window_end == QT_II - timedelta(days=1),
                  f"got [{r2.window_start}, {r2.window_end}]")
            check("2. QT-II Criterion I counts BOTH 2026-09-11 sessions "
                  "(normal lecture + quiz-day-shaped lecture): "
                  "L.total +2 and L.attended +2",
                  r2.lecture.total == base_c2["L"]["tot"] + 2
                  and r2.lecture.attended == base_c2["L"]["att"] + 2,
                  f"L tot={r2.lecture.total} (base {base_c2['L']['tot']} + 2), "
                  f"att={r2.lecture.attended} (base {base_c2['L']['att']} + 2)")

            # ---------------- 2. QT-I (cycle 1) UNCHANGED -----------
            r1 = await service.get_quiz_eligibility(
                student.id, bcs058.id, 1, semester_start=semester_start)
            check("3. QT-I Criterion I UNCHANGED by the 09-11 fixture "
                  "(same date excluded from QT-I, included in QT-II): "
                  "window [commencement, 2026-09-10]",
                  r1.window_start == semester_start
                  and r1.window_end == QT_I - timedelta(days=1)
                  and r1.lecture.total == base_c1["L"]["tot"]
                  and r1.lecture.attended == base_c1["L"]["att"],
                  f"window=[{r1.window_start}, {r1.window_end}] "
                  f"L tot={r1.lecture.total} (base {base_c1['L']['tot']})")

            # ---------------- 3. repo decomposition of the QT-II window
            full = aggregate(await att_repo.get_subject_counts_between(
                student.id, bcs058.id, QT_I, QT_II - timedelta(days=1)))
            check("4. QT-II window decomposes as [09-11] + [09-12..10-04] "
                  "(every session on the inclusive start date counts)",
                  counts_equal(full, counts_add(base_c2_q1, base_c2_after)),
                  f"full_L={full['L']['tot']} q1_L={base_c2_q1['L']['tot']} "
                  f"after_L={base_c2_after['L']['tot']}")

            # ---------------- 4. batch path (single scan + bucketing) --
            subjects = [bcs058, bcs501]
            batch = await service.get_quiz_eligibility_for_subjects(
                student.id, subjects, 2, semester_start=semester_start)
            batch_058 = next((r for r in batch if r.subject_code == ELECTIVE_SUBJECT_CODE), None)
            check("5. BATCH path (get_quiz_eligibility_for_subjects, one scan "
                  "+ in-memory bucketing) returns the same QT-II counts "
                  "as the single-subject path",
                  batch_058 is not None
                  and batch_058.lecture.total == r2.lecture.total
                  and batch_058.lecture.attended == r2.lecture.attended
                  and batch_058.window_start == r2.window_start
                  and batch_058.window_end == r2.window_end,
                  f"batch L tot={batch_058.lecture.total if batch_058 else None} "
                  f"vs single L tot={r2.lecture.total}")

            # ---------------- 5. elective-II chooser path ---------------
            if chooser is not None and chooser_base_c2 is not None:
                r2_chooser = await service.get_quiz_eligibility(
                    chooser.id, bcs058.id, 2, semester_start=semester_start)
                check("6. DE-II elective chooser: QT-II Criterion I also "
                      "counts both 09-11 sessions (L.total +2, L.attended +2)",
                      r2_chooser.lecture.total == chooser_base_c2["L"]["tot"] + 2
                      and r2_chooser.lecture.attended == chooser_base_c2["L"]["att"] + 2,
                      f"chooser L tot={r2_chooser.lecture.total} "
                      f"(base {chooser_base_c2['L']['tot']} + 2)")
            else:
                print("  [info] no student with an Elective-II choice of BCS-058 "
                      "found; elective-chooser delta check skipped "
                      "(attribution branch is identical for every student)")

            # ---------------- 6. Criterion II (cumulative) -------------
            cum_full = aggregate(await att_repo.get_subject_counts_between(
                student.id, bcs058.id, semester_start, QT_II - timedelta(days=1)))
            cum_before = aggregate(await att_repo.get_subject_counts_between(
                student.id, bcs058.id, semester_start, QT_I - timedelta(days=1)))
            cum_after = aggregate(await att_repo.get_subject_counts_between(
                student.id, bcs058.id, QT_I + timedelta(days=1), QT_II - timedelta(days=1)))
            check("7. Criterion II cumulative window [commencement, 2026-10-04] "
                  "INCLUDES the 09-11 sessions (decomposition "
                  "full == before + q1 + after)",
                  counts_equal(cum_full, counts_add(cum_before, base_c2_q1, cum_after)),
                  f"cum_full_L={cum_full['L']['tot']} before_L={cum_before['L']['tot']} "
                  f"q1_L={base_c2_q1['L']['tot']} after_L={cum_after['L']['tot']}")
            ref_cum_avg = pooled_from(cum_full)
            check("8. Criterion II percentage equals the pooled reference over "
                  "the cumulative window (previous-quiz-day occurrence not "
                  "stripped from Criterion II)",
                  (r2.criterion_ii.value is None and ref_cum_avg is None)
                  or (r2.criterion_ii.value is not None
                      and ref_cum_avg is not None
                      and abs(r2.criterion_ii.value - ref_cum_avg) < 1e-9),
                  f"criterion_ii.value={r2.criterion_ii.value} "
                  f"reference={ref_cum_avg}")

            # ---------------- 7. common subject BCS-501 ----------------
            bcs501_eff = await repo.get_effective_quiz_dates_for_subject(bcs501.id)
            if len(bcs501_eff) >= 2:
                (_, bcs501_q1), (_, bcs501_q2) = bcs501_eff[0], bcs501_eff[1]
                f501 = aggregate(await att_repo.get_subject_counts_between(
                    student.id, bcs501.id, bcs501_q1, bcs501_q2 - timedelta(days=1)))
                a501 = aggregate(await att_repo.get_subject_counts_between(
                    student.id, bcs501.id, bcs501_q1 + timedelta(days=1),
                    bcs501_q2 - timedelta(days=1)))
                q501 = aggregate(await att_repo.get_subject_counts_between(
                    student.id, bcs501.id, bcs501_q1, bcs501_q1))
                shaped_501 = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.subject_id == bcs501.id,
                        ClassSession.date == bcs501_q1,
                        ClassSession.timetable_entry_id.is_(None),
                        ClassSession.is_extra.is_(False),
                        ClassSession.class_type == ClassType.LECTURE,
                    )
                )).scalars().all()
                check("9. COMMON subject BCS-501: cycle-2 window "
                      f"[{bcs501_q1}, {bcs501_q2 - timedelta(days=1)}] includes "
                      "the QT-I date sessions (decomposition full == q1 + after); "
                      "the materialized quiz-day occurrence on the previous "
                      "quiz date counts toward the next cycle",
                      counts_equal(f501, counts_add(q501, a501))
                      and q501["L"]["tot"] >= 1
                      and len(shaped_501) >= 1,
                      f"full_L={f501['L']['tot']} q1_L={q501['L']['tot']} "
                      f"after_L={a501['L']['tot']} shaped_on_q1={len(shaped_501)}")
            else:
                check("9. COMMON subject BCS-501: cycle-2 window includes the "
                      "QT-I date sessions", False, "BCS-501 has < 2 effective quiz dates")

            # ---------------- 8. HTTP end-to-end -----------------------
            enrolled = None
            for candidate in (student, admin):
                enr = (await db.execute(
                    select(StudentEnrollment).where(
                        StudentEnrollment.user_id == candidate.id,
                        StudentEnrollment.subject_id == bcs058.id)
                )).scalars().first()
                if enr is not None:
                    enrolled = candidate
                    break
            if enrolled is not None:
                token = create_access_token(str(enrolled.id), enrolled.roll_number)
                headers = {"Authorization": f"Bearer {token}"}
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get(
                        f"/api/v1/quiz-eligibility/{ELECTIVE_SUBJECT_CODE}/2",
                        headers=headers)
                if resp.status_code == 200:
                    body = resp.json()
                    api_r2 = await service.get_quiz_eligibility(
                        enrolled.id, bcs058.id, 2, semester_start=semester_start)
                    check("10. HTTP /api/v1/quiz-eligibility/BCS-058/2 matches "
                          "the service result (both 09-11 sessions counted)",
                          body["window_start"] == QT_I.isoformat()
                          and body["window_end"] == (QT_II - timedelta(days=1)).isoformat()
                          and body["lecture"]["total"] == api_r2.lecture.total
                          and body["lecture"]["attended"] == api_r2.lecture.attended,
                          f"HTTP L tot={body['lecture']['total']} "
                          f"att={body['lecture']['attended']} "
                          f"vs service L tot={api_r2.lecture.total}")
                else:
                    check("10. HTTP /api/v1/quiz-eligibility/BCS-058/2 matches "
                          "the service result", False,
                          f"HTTP {resp.status_code}: {resp.text[:200]}")
            else:
                print("  [info] no user enrolled in BCS-058 found; HTTP "
                      "end-to-end cross-check skipped (service path is the "
                      "same calculation the endpoint performs)")

            # ---------------- 9. fixture session C on the QT-II day ----
            session_c = ClassSession(
                subject_id=bcs058.id,
                date=QT_II,
                class_type=ClassType.LECTURE,
                is_extra=False,
                is_cancelled=False,
                timetable_entry_id=None,
                elective_slot=ElectiveSlot.ELECTIVE_II,
            )
            db.add(session_c)
            await db.flush()
            rec_c = AttendanceRecord(user_id=student.id, class_session_id=session_c.id,
                                     status=AttendanceStatus.ATTENDED)
            db.add(rec_c)
            await db.flush()
            session_c_id = session_c.id
            rec_c_id = rec_c.id

            r2_after_c = await service.get_quiz_eligibility(
                student.id, bcs058.id, 2, semester_start=semester_start)
            check("11. QT-II DAY (2026-10-05) session does NOT affect QT-II "
                  "Criterion I (excluded purely by the window end): "
                  "counts and window unchanged",
                  r2_after_c.lecture.total == r2.lecture.total
                  and r2_after_c.lecture.attended == r2.lecture.attended
                  and r2_after_c.window_start == QT_I
                  and r2_after_c.window_end == QT_II - timedelta(days=1),
                  f"L tot={r2_after_c.lecture.total} (was {r2.lecture.total}), "
                  f"window=[{r2_after_c.window_start}, {r2_after_c.window_end}]")

            r3 = await service.get_quiz_eligibility(
                student.id, bcs058.id, 3, semester_start=semester_start)
            check("12. QT-III Criterion I window = [QT-II 2026-10-05, "
                  "2026-10-25] and COUNTS the 10-05 session "
                  "(QT-II date is the inclusive start of QT-III's window)",
                  r3.window_start == QT_II
                  and r3.window_end == QT_III - timedelta(days=1)
                  and r3.lecture.total == base_c3["L"]["tot"] + 1
                  and r3.lecture.attended == base_c3["L"]["att"] + 1,
                  f"window=[{r3.window_start}, {r3.window_end}] "
                  f"L tot={r3.lecture.total} (base {base_c3['L']['tot']} + 1), "
                  f"att={r3.lecture.attended} (base {base_c3['L']['att']} + 1)")

        finally:
            # ---------------- exact cleanup ----------------------------
            async with AsyncSessionLocal() as db:
                if fixture_record_ids or rec_c_id is not None:
                    all_rec_ids = list(fixture_record_ids)
                    if rec_c_id is not None:
                        all_rec_ids.append(rec_c_id)
                    await db.execute(
                        AttendanceRecord.__table__.delete().where(
                            AttendanceRecord.id.in_(all_rec_ids)))
                if fixture_session_ids or session_c_id is not None:
                    all_sess_ids = list(fixture_session_ids)
                    if session_c_id is not None:
                        all_sess_ids.append(session_c_id)
                    await db.execute(
                        ClassSession.__table__.delete().where(
                            ClassSession.id.in_(all_sess_ids)))
                # the fixture timetable entry (captured via its session)
                await db.execute(
                    TimetableEntry.__table__.delete().where(
                        TimetableEntry.subject_id == bcs058.id,
                        TimetableEntry.day_of_week == QT_I.weekday(),
                        TimetableEntry.start_time == time(9, 0),
                        TimetableEntry.end_time == time(10, 0),
                        TimetableEntry.elective_slot.is_(None),
                        ~TimetableEntry.id.in_(
                            select(ClassSession.timetable_entry_id).where(
                                ClassSession.timetable_entry_id.isnot(None)))))
                await db.commit()

            # restoration check
            async with AsyncSessionLocal() as db:
                att_repo2 = AttendanceRepository(db)
                restored = aggregate(await att_repo2.get_subject_counts_between(
                    student.id, bcs058.id, QT_I, QT_II - timedelta(days=1)))
                check("13. Exact baseline restoration (no fixture residue)",
                      counts_equal(restored, base_c2),
                      f"restored_L={restored['L']['tot']} base_L={base_c2['L']['tot']}")

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:")
        for name in failed:
            print(f"  - {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
