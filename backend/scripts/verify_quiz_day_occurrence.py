"""
Quiz-Day separate-occurrence verification (Option A — Phases 8/9 of the
semantic-correction task).

Pins the LOCKED product semantics against the real database (httpx
ASGITransport + real DB + minted JWTs, the established pattern):

  * A Quiz Day is an INDEPENDENT attendance occurrence: for a covered past
    date, an active QUIZ_DAY event produces a SECOND BCS-502 occurrence in
    Track (the normal lecture AND the quiz-day session) with distinct ids.
  * Scenario A (lecture Present + quiz Present) -> subject lecture
    attended +2 / total +2.
  * Scenario B (lecture Present + quiz Absent) -> attended +1 / total +2.
  * Scenario C (lecture Absent + quiz Present) -> attended +1 / total +2.
  * Subject scoping: only the quiz subject's summary changes (no
    cross-subject leakage).
  * ERP: the overall aggregate counts the quiz-day record exactly once
    (attended +2 / recorded +2 in scenario A).
  * Eligibility isolation (the critical invariant): the quiz-day session is
    EXCLUDED from the eligibility L/T window counts while the normal lecture
    remains included — under events-authoritative quiz dates (Phase 2/3) the
    new event on D is itself Quiz I, and the eligibility totals must equal
    the quiz-day-excluded DB reference for its window, even though subject
    attendance and ERP both include the quiz-day occurrence.

State changes are this script's own artifacts (one "VerifyQuizDayOccurrence"
QUIZ_DAY event on a runtime-picked past covered date, the quiz-day session it
materializes, and the attendance records created on the lecture + quiz-day
sessions) and are removed in the finally block by exact captured ids. The
pre-existing lecture session is NEVER deleted — only this run's records on
it are removed.

Usage:
    python scripts/verify_quiz_day_occurrence.py
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
from app.models.user import User, Section
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.academic import Subject, Semester
from app.repositories.attendance_repo import AttendanceRepository
from app.engines.attendance_engine import normalize_class_type
from app.models.enums import AttendanceStatus
from sqlalchemy import select, func, delete

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


EVENT_TITLE_PREFIX = "VerifyQuizDayOccurrence"
SUBJECT_CODE = "BCS-502"

# Past working dates available for the covered-date checks (no overlap with any
# frozen verifier's mutation window: 07-31/08-01 belong to events-correction,
# 11-02..12 to 7.1, 10-23 is the seeded canonical session). D starts the day
# AFTER the subject's semester start so the Quiz I eligibility window
# [semester_start, D-1] is non-empty under events-authoritative quiz dates
# (Phase 2/3: the new event on D IS Quiz I) — making check 8 a real proof.
PAST_CANDIDATES = [date(2026, 7, 16) + timedelta(days=i) for i in range(31)]  # 07-16..08-15


async def main() -> int:
    async with AsyncSessionLocal() as db:
        subject_ids = {s.code: s.id for s in (await db.execute(select(Subject))).scalars().all()}
        events_before = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
        sessions_before = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
        records_before = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
        admin_user = (await db.execute(select(User).where(User.roll_number == "2401220100027"))).scalars().first()
        # The zero-record student drives all attendance/scenario checks (every
        # session is Pending for them, so the +2/+2 scenario math is clean and
        # the only records this run creates belong to this verifier).
        student_user = (await db.execute(select(User).where(User.roll_number == "9999999999999"))).scalars().first()
        if admin_user is None or student_user is None:
            print("FATAL: seed users missing")
            return 1

        semester_start = date(2026, 7, 15)
        if admin_user.section_id:
            section = await db.get(Section, admin_user.section_id)
            if section:
                semester = await db.get(Semester, section.semester_id)
                if semester:
                    semester_start = semester.start_date

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    student_token = create_access_token(str(student_user.id), student_user.roll_number)
    student_headers = {"Authorization": f"Bearer {student_token}"}

    transport = httpx.ASGITransport(app=app)
    test_event_id: uuid.UUID | None = None
    quiz_session_id: uuid.UUID | None = None
    lecture_id: uuid.UUID | None = None
    record_ids: list = []

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # --- pick a past covered date inside the Quiz I window ------------
            chosen = None
            for d in PAST_CANDIDATES:
                if d < semester_start or d.weekday() >= 5:
                    continue
                if d in (date(2026, 7, 31), date(2026, 8, 1)):
                    continue
                daily = await client.get(f"/api/v1/attendance/daily/{d.isoformat()}", headers=student_headers)
                if daily.status_code != 200:
                    continue
                occ = [s for s in daily.json()["sessions"] if s["subject_code"] == SUBJECT_CODE]
                if (len(occ) == 1 and occ[0]["start_time"] and not occ[0]["is_extra"]
                        and occ[0]["status"] == "Pending" and not occ[0]["is_cancelled"]):
                    er = await client.get(
                        f"/api/v1/events?date_from={d.isoformat()}&date_to={d.isoformat()}", headers=admin_headers)
                    if er.status_code == 200 and not any(
                        e["event_type"] == "QUIZ_DAY" and e["subject_id"] == str(subject_ids[SUBJECT_CODE])
                        and e["active"] for e in er.json()):
                        chosen = (d, occ[0])
                        break
            if chosen is None:
                check("0. found a past covered date for BCS-502 inside the Quiz I window",
                      False, "no candidate")
                return 1
            d, lecture = chosen
            lecture_id = uuid.UUID(lecture["id"])

            # --- baseline values (student = zero-record) ----------------------
            s_base = (await client.get(f"/api/v1/attendance/summary/{SUBJECT_CODE}", headers=student_headers)).json()
            base_lec_att = s_base["lecture"]["attended"]
            base_lec_tot = s_base["lecture"]["total"]
            other_base = (await client.get("/api/v1/attendance/summary/BCS-501", headers=student_headers)).json()
            base_501_lec = (other_base["lecture"]["attended"], other_base["lecture"]["total"])
            ov_base = (await client.get("/api/v1/analytics/overview", headers=student_headers)).json()["overall"]
            base_ov_att = ov_base["attended"]
            base_ov_rec = ov_base["recorded"]
            elig_base = (await client.get(f"/api/v1/quiz-eligibility/{SUBJECT_CODE}/1", headers=student_headers)).json()
            base_elig_lec_tot = elig_base["lecture"]["total"]
            w_start = date.fromisoformat(elig_base["window_start"])
            w_end = date.fromisoformat(elig_base["window_end"])

            # --- 1. Create the QUIZ_DAY event on the covered past date --------
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "QUIZ_DAY",
                "start_date": d.isoformat(),
                "end_date": d.isoformat(),
                "subject_id": str(subject_ids[SUBJECT_CODE]),
                "note": f"{EVENT_TITLE_PREFIX} — QUIZ_DAY {SUBJECT_CODE} {d.isoformat()}",
            })
            ok = r.status_code == 201
            if ok:
                test_event_id = uuid.UUID(r.json()["id"])
            check("1. QUIZ_DAY (BCS-502) on covered past date -> 201",
                  ok, f"got {r.status_code} {r.text[:200]}")

            # --- 2. Two distinct occurrences in Track -------------------------
            daily = await client.get(f"/api/v1/attendance/daily/{d.isoformat()}", headers=student_headers)
            occ = [s for s in daily.json()["sessions"] if s["subject_code"] == SUBJECT_CODE]
            quiz_sessions = [s for s in occ if s["start_time"] is None and not s["is_extra"]]
            lecture_again = [s for s in occ if s["start_time"] and not s["is_extra"]]
            two_distinct = (len(occ) == 2 and len(quiz_sessions) == 1 and len(lecture_again) == 1
                            and quiz_sessions[0]["id"] != lecture_again[0]["id"])
            if len(quiz_sessions) == 1:
                quiz_session_id = uuid.UUID(quiz_sessions[0]["id"])
            check("2. Track shows the normal lecture AND the independent quiz-day "
                  "occurrence (distinct session ids)",
                  two_distinct,
                  f"occ={[(s['class_type'], s['start_time'], s['is_extra'], s['id']) for s in occ]}")

            if quiz_session_id is None or test_event_id is None:
                return 1

            # The lecture on D was already part of the baseline applicable total
            # (it is a normal session up to as_of), so the independent quiz-day
            # occurrence adds exactly +1 to the applicable total and each mark
            # is its own record: two marks -> attended +2.
            s_ev = (await client.get(f"/api/v1/attendance/summary/{SUBJECT_CODE}", headers=student_headers)).json()
            tot_after_event = s_ev["lecture"]["total"]
            check("2b. quiz-day occurrence adds exactly +1 applicable session "
                  "(the normal lecture was already applicable)",
                  tot_after_event == base_lec_tot + 1,
                  f"tot={tot_after_event}(base {base_lec_tot})")

            # --- 3. Scenario A: lecture Present + quiz Present ----------------
            ra = await client.post("/api/v1/attendance", headers=student_headers, json={
                "class_session_id": lecture["id"], "status": "Attended"})
            rb = await client.post("/api/v1/attendance", headers=student_headers, json={
                "class_session_id": str(quiz_session_id), "status": "Attended"})
            s_a = (await client.get(f"/api/v1/attendance/summary/{SUBJECT_CODE}", headers=student_headers)).json()
            check("3. Scenario A (lecture Present + quiz Present): subject "
                  "lecture attended +2 / applicable +1 (two independent records)",
                  ra.status_code == 200 and rb.status_code == 200
                  and s_a["lecture"]["attended"] == base_lec_att + 2
                  and s_a["lecture"]["total"] == tot_after_event,
                  f"marks={ra.status_code},{rb.status_code} "
                  f"att={s_a['lecture']['attended']}(base {base_lec_att}) "
                  f"tot={s_a['lecture']['total']}(after-event {tot_after_event})")

            # --- 4. ERP includes both exactly once ----------------------------
            ov_a = (await client.get("/api/v1/analytics/overview", headers=student_headers)).json()["overall"]
            check("4. ERP: overall attended +2 / recorded +2 (both quiz-day "
                  "records count exactly once)",
                  ov_a["attended"] == base_ov_att + 2 and ov_a["recorded"] == base_ov_rec + 2,
                  f"att={ov_a['attended']}(base {base_ov_att}) rec={ov_a['recorded']}(base {base_ov_rec})")

            # --- 5. Scenario B: lecture Present + quiz Absent ----------------
            rb = await client.post("/api/v1/attendance", headers=student_headers, json={
                "class_session_id": str(quiz_session_id), "status": "Missed"})
            s_b = (await client.get(f"/api/v1/attendance/summary/{SUBJECT_CODE}", headers=student_headers)).json()
            check("5. Scenario B (lecture Present + quiz Absent): subject "
                  "lecture attended +1 / applicable +1 (quiz counts as recorded "
                  "absence)",
                  rb.status_code == 200
                  and s_b["lecture"]["attended"] == base_lec_att + 1
                  and s_b["lecture"]["total"] == tot_after_event,
                  f"att={s_b['lecture']['attended']} tot={s_b['lecture']['total']}")

            # --- 6. Scenario C: lecture Absent + quiz Present ----------------
            ra = await client.post("/api/v1/attendance", headers=student_headers, json={
                "class_session_id": lecture["id"], "status": "Missed"})
            rb = await client.post("/api/v1/attendance", headers=student_headers, json={
                "class_session_id": str(quiz_session_id), "status": "Attended"})
            s_c = (await client.get(f"/api/v1/attendance/summary/{SUBJECT_CODE}", headers=student_headers)).json()
            check("6. Scenario C (lecture Absent + quiz Present): subject "
                  "lecture attended +1 / applicable +1 (independent records)",
                  ra.status_code == 200 and rb.status_code == 200
                  and s_c["lecture"]["attended"] == base_lec_att + 1
                  and s_c["lecture"]["total"] == tot_after_event,
                  f"att={s_c['lecture']['attended']} tot={s_c['lecture']['total']}")

            # --- 7. Subject scoping: other subjects unchanged -----------------
            other_now = (await client.get("/api/v1/attendance/summary/BCS-501", headers=student_headers)).json()
            check("7. Quiz attendance belongs ONLY to BCS-502 (BCS-501 summary "
                  "unchanged)",
                  (other_now["lecture"]["attended"], other_now["lecture"]["total"]) == base_501_lec,
                  f"501={other_now['lecture']['attended']}/{other_now['lecture']['total']}")

            # --- 8. Eligibility isolation (the critical invariant) ------------
            # Under events-authoritative quiz dates (Phase 2/3) the new event
            # on D IS Quiz I, so its window is [semester_start, D-1] and D is
            # its own quiz date. The quiz-day occurrence must NOT enter the
            # eligibility L/T counts: lecture/tutorial totals must equal the
            # DB reference for that window with quiz-day-shaped sessions
            # excluded (Rule 5 — the three-way separation rule), even though
            # subject attendance (+2) and ERP include the quiz-day record.
            elig_after = (await client.get(
                f"/api/v1/quiz-eligibility/{SUBJECT_CODE}/1", headers=student_headers)).json()
            w_start = date.fromisoformat(elig_after["window_start"])
            w_end = date.fromisoformat(elig_after["window_end"])
            async with AsyncSessionLocal() as db:
                ref_counts = aggregate(await AttendanceRepository(db).get_subject_counts_between(
                    student_user.id, subject_ids[SUBJECT_CODE], w_start, w_end,
                    exclude_quiz_day=True))
            check("8. Eligibility isolation (Rule 5): quiz-day occurrence does "
                  "NOT enter the L/T window counts (totals == quiz-day-excluded "
                  "DB reference) while subject attendance and ERP include it",
                  elig_after["quiz_date"] == d.isoformat()
                  and w_start == semester_start and w_end == d - timedelta(days=1)
                  and elig_after["lecture"]["total"] == ref_counts["L"]["tot"]
                  and elig_after["tutorial"]["total"] == ref_counts["T"]["tot"],
                  f"quiz_date={elig_after.get('quiz_date')} window=[{w_start},{w_end}] "
                  f"elig L tot={elig_after['lecture']['total']}(ref {ref_counts['L']['tot']}) "
                  f"T tot={elig_after['tutorial']['total']}(ref {ref_counts['T']['tot']}) "
                  f"subject L tot={s_c['lecture']['total']}(base {base_lec_tot})")

            # capture this run's attendance records for exact cleanup
            async with AsyncSessionLocal() as db:
                recs = (await db.execute(
                    select(AttendanceRecord.id).where(
                        AttendanceRecord.user_id == student_user.id,
                        AttendanceRecord.class_session_id.in_([lecture_id, quiz_session_id]),
                    ))).scalars().all()
                record_ids = list(recs)

    finally:
        async with AsyncSessionLocal() as db:
            # Exact captured ids; fall back to a fresh query when any check
            # failed before the capture ran (prevents an FK crash on the
            # session delete and leaves zero residue).
            ids = list(record_ids)
            if not ids:
                ids = (await db.execute(
                    select(AttendanceRecord.id).where(
                        AttendanceRecord.user_id == student_user.id,
                        AttendanceRecord.class_session_id.in_(
                            [s for s in (lecture_id, quiz_session_id) if s is not None])))).scalars().all()
            if ids:
                await db.execute(delete(AttendanceRecord).where(AttendanceRecord.id.in_(ids)))
            if quiz_session_id is not None:
                await db.execute(delete(ClassSession).where(ClassSession.id == quiz_session_id))
            if test_event_id is not None:
                ev = await db.get(AcademicEvent, test_event_id)
                if ev is not None:
                    await db.delete(ev)
            await db.commit()

            events_after = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
            sessions_after = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
            records_after = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()

        check("9. exact baseline restoration (events/sessions/records)",
              events_before == events_after and sessions_before == sessions_after
              and records_before == records_after,
              f"events {events_before}->{events_after} sessions {sessions_before}->{sessions_after} "
              f"records {records_before}->{records_after}")

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:")
        for name in failed:
            print(f"  - {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
