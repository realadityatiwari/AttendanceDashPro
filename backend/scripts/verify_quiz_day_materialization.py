"""
Focused Quiz-Day materialization verification (post-events-correction turn).

Pins the corrected seeded Quiz Day contract against the real database (httpx
ASGITransport + real DB + minted JWTs, the established pattern):

  * BCS-058 quiz dates now match the official "Schedule of Quiz Test Session
    2026-27 (Odd Semester)" PDF: Q1=2026-09-11, Q2=2026-10-05 (corrected from
    2026-10-02), Q3=2026-10-26 — in timetable.json, quiz_schedules, the
    QUIZ_DAY academic events, and the session pipeline. 2026-10-02 is clean
    (no event, no quiz-day session).
  * Every official seeded Quiz Day date has its attendance-bearing occurrence
    in Track: exactly one quiz-day-shaped session per subject/date,
    INDEPENDENT of coverage (Option A) — covered dates keep their regular
    lecture AND gain the quiz-day occurrence; no duplicates.
  * Option A: 2026-10-05 BCS-058 is covered by its Monday lecture AND still
    gets its independent quiz-day session.
  * A newly-created Quiz Day still materializes, is markable exactly once,
    and its attendance flows into History and subject analytics (check G/E/F).
  * Rescheduling a Quiz Day removes the old unattended occurrence and
    materializes the new one per the existing contract (check H).
  * Exact baseline restoration — existing attendance data and owner-created
    events are never touched (check I).

Seeded dates pinned (official):
  first cycle: 08-24 BNC-501, 08-27 BCS-501, 08-31 BCS-502, 09-03 BCS-503,
               09-07 BCS-054, 09-11 BCS-058
  BCS-058:     Q2 2026-10-05 (corrected), Q3 2026-10-26
  negative:    2026-10-02 (the old wrong Q2 date must be clean)

State changes are this script's own artifacts (events titled
"VerifyQuizDayMaterialization ...", their sessions, and attendance records on
the runtime-picked past dates) and are removed in the finally block. The
canonical seeded 10-23 BCS-054 quiz-day session is never touched.

Usage:
    python scripts/verify_quiz_day_materialization.py
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
from app.models.user import User
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.academic import Subject
from app.models.quiz import QuizSchedule
from app.models.enums import ClassType, UserRole
from sqlalchemy import select, func, delete

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


# --- seeded official dates to pin -------------------------------------------------
# (subject_code, official quiz date)
SEEDED = [
    ("BNC-501", date(2026, 8, 24)),
    ("BCS-501", date(2026, 8, 27)),
    ("BCS-502", date(2026, 8, 31)),
    ("BCS-503", date(2026, 9, 3)),
    ("BCS-054", date(2026, 9, 7)),
    ("BCS-058", date(2026, 9, 11)),
    ("BCS-058", date(2026, 10, 5)),   # corrected Q2 (was 2026-10-02)
    ("BCS-058", date(2026, 10, 26)),  # Q3
]
WRONG_Q2 = date(2026, 10, 2)          # must be clean for BCS-058
SEED_054 = date(2026, 10, 23)         # canonical script quiz-day session (never delete)

# Official BCS-058 dates per the authoritative PDF
BCS058_OFFICIAL = {date(2026, 9, 11), date(2026, 10, 5), date(2026, 10, 26)}

# Past working dates available for the new-quiz-day checks (no overlap with any
# frozen verifier's mutation window: 07-31/08-01 and 11-23..28 belong to the
# events-correction verifier, 11-02..12 to 7.1, 10-23 is the seeded session).
PAST_CANDIDATES = [date(2026, 7, 15) + timedelta(days=i) for i in range(32)]  # 07-15..08-15

EVENT_TITLE_PREFIX = "VerifyQuizDayMaterialization"


async def main() -> int:
    async with AsyncSessionLocal() as db:
        subject_ids = {s.code: s.id for s in (await db.execute(select(Subject))).scalars().all()}
        events_before = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
        sessions_before = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
        cancelled_before = (await db.execute(select(func.count()).select_from(ClassSession).where(
            ClassSession.is_cancelled.is_(True)))).scalar()
        extra_before = (await db.execute(select(func.count()).select_from(ClassSession).where(
            ClassSession.is_extra.is_(True)))).scalar()
        records_before = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
        enrollments_before = (await db.execute(select(func.count()).select_from(
            __import__("app.models.academic", fromlist=["StudentEnrollment"]).StudentEnrollment))).scalar()
        subjects_before = (await db.execute(select(func.count()).select_from(Subject))).scalar()
        quizzes_before = (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar()
        users_before = (await db.execute(select(func.count()).select_from(User))).scalar()
        admins_before = (await db.execute(select(func.count()).select_from(User).where(
            User.role == UserRole.ADMIN))).scalar()
        admin_user = (await db.execute(select(User).where(User.roll_number == "2401220100027"))).scalars().first()
        student_user = (await db.execute(select(User).where(User.roll_number == "9999999999999"))).scalars().first()
        if admin_user is None or student_user is None:
            print("FATAL: seed users missing")
            return 1

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    transport = httpx.ASGITransport(app=app)
    test_event_ids: list[uuid.UUID] = []
    my_dates: set = set()

    def ev_payload(event_type: str, subject_code: str, d: date) -> dict:
        return {
            "event_type": event_type,
            "start_date": d.isoformat(),
            "end_date": d.isoformat(),
            "subject_id": str(subject_ids[subject_code]),
            "note": f"{EVENT_TITLE_PREFIX} — {event_type} {subject_code} {d.isoformat()}",
        }

    async def qd_sessions_on(db, d: date, code: str = None) -> list:
        stmt = select(ClassSession).where(
            ClassSession.date == d,
            ClassSession.timetable_entry_id.is_(None),
            ClassSession.is_extra.is_(False),
            ClassSession.class_type == ClassType.LECTURE,
        )
        if code is not None:
            stmt = stmt.where(ClassSession.subject_id == subject_ids[code])
        return (await db.execute(stmt)).scalars().all()

    async def pick_uncovered_past_date(client, code: str) -> date:
        """First past working date where the subject has zero non-cancelled
        sessions and no active event (deterministic runtime selection)."""
        for d in PAST_CANDIDATES:
            if d.weekday() >= 5:
                continue
            if d in (date(2026, 7, 31), date(2026, 8, 1)):
                continue
            r = await client.get(f"/api/v1/attendance/daily/{d.isoformat()}", headers=admin_headers)
            if r.status_code != 200:
                continue
            occ = [s for s in r.json()["sessions"] if s["subject_code"] == code and not s["is_cancelled"]]
            if occ:
                continue
            er = await client.get(
                f"/api/v1/events?date_from={d.isoformat()}&date_to={d.isoformat()}", headers=admin_headers)
            if er.status_code == 200 and not any(
                e["event_type"] == "QUIZ_DAY" and e["subject_id"] == str(subject_ids[code]) for e in er.json()):
                return d
        raise RuntimeError(f"no uncovered past working date found for {code}")

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # --- 1. Schedule source parity: BCS-058 in DB == timetable.json ---
            async with AsyncSessionLocal() as db:
                rows = (await db.execute(
                    select(QuizSchedule.date).join(Subject, Subject.id == QuizSchedule.subject_id)
                    .where(Subject.code == "BCS-058", QuizSchedule.schedule_status == "SCHEDULED")
                    .order_by(QuizSchedule.date)
                )).scalars().all()
                import json
                with open(Path(__file__).resolve().parent.parent.parent / "timetable.json", encoding="utf-8") as f:
                    tt = json.load(f)
                tt_dates = {date.fromisoformat(ms["date"]) for subj in tt["subjects"]
                            if subj["code"] == "BCS-058" for ms in subj["timeline"]["milestones"]}
            check("1. BCS-058 quiz_schedules == timetable.json == official "
                  "(09-11, 10-05, 10-26)",
                  set(rows) == BCS058_OFFICIAL and tt_dates == BCS058_OFFICIAL
                  and set(rows) == tt_dates,
                  f"db={sorted(set(rows))} tt={sorted(tt_dates)}")

            # --- 2/3. Every official seeded date: event + Track occurrence ---
            all_a_ok, all_b_ok, all_qd_ok = True, True, True
            for code, d in SEEDED:
                r = await client.get(
                    f"/api/v1/events?date_from={d.isoformat()}&date_to={d.isoformat()}", headers=admin_headers)
                has_event = r.status_code == 200 and any(
                    e["event_type"] == "QUIZ_DAY" and e["subject_id"] == str(subject_ids[code])
                    and e["active"] for e in r.json())
                all_a_ok &= has_event
                daily = await client.get(f"/api/v1/attendance/daily/{d.isoformat()}", headers=admin_headers)
                occ = [s for s in daily.json()["sessions"]
                       if s["subject_code"] == code and not s["is_cancelled"]]
                all_b_ok &= daily.status_code == 200 and len(occ) >= 1
            async with AsyncSessionLocal() as db:
                for code, d in SEEDED:
                    sess = await qd_sessions_on(db, d, code)
                    all_qd_ok &= len(sess) == 1 and not sess[0].is_cancelled
            check("2. official seeded Quiz Day event exists (A) for all 8 pinned dates",
                  all_a_ok, "missing event for one of " + ", ".join(f"{c} {d}" for c, d in SEEDED))
            check("3. Track/session representation exists on the correct date (B) "
                  "with exactly ONE quiz-day-shaped session per pinned date "
                  "(D, Option A: independent of coverage)",
                  all_b_ok and all_qd_ok)

            # --- 4. Quiz-day-shaped occurrence on the officially uncovered dates ---
            uncovered_qd = {
                ("BCS-502", date(2026, 8, 31)),
                ("BCS-058", date(2026, 9, 11)),
                ("BCS-502", date(2026, 9, 21)),
                ("BNC-501", date(2026, 10, 9)),
                ("BCS-501", date(2026, 10, 12)),
                ("BCS-054", date(2026, 10, 23)),
            }
            async with AsyncSessionLocal() as db:
                ok_shape = True
                for code, d in uncovered_qd:
                    sess = await qd_sessions_on(db, d, code)
                    ok_shape &= len(sess) == 1 and not sess[0].is_cancelled
            check("4. uncovered official dates hold exactly one quiz-day-shaped "
                  "session (no duplicates, not cancelled)", ok_shape)

            # --- 5. 10-02 (old wrong Q2) is clean; 10-05 is Option-B covered ---
            r = await client.get(
                f"/api/v1/events?date_from={WRONG_Q2.isoformat()}&date_to={WRONG_Q2.isoformat()}",
                headers=admin_headers)
            no_event = not any(
                e["event_type"] == "QUIZ_DAY" and e["subject_id"] == str(subject_ids["BCS-058"])
                for e in r.json())
            async with AsyncSessionLocal() as db:
                wrong_sess = await qd_sessions_on(db, WRONG_Q2, "BCS-058")
                daily = await client.get(f"/api/v1/attendance/daily/{WRONG_Q2.isoformat()}", headers=admin_headers)
                bcs058_wrong = [s for s in daily.json()["sessions"] if s["subject_code"] == "BCS-058"]
                daily2 = await client.get(f"/api/v1/attendance/daily/{date(2026, 10, 5).isoformat()}", headers=admin_headers)
                bcs058_correct = [s for s in daily2.json()["sessions"]
                                  if s["subject_code"] == "BCS-058" and not s["is_cancelled"]]
                qd_1005 = await qd_sessions_on(db, date(2026, 10, 5), "BCS-058")
            check("5. 2026-10-02 is clean (no BCS-058 event, no session; the "
                  "corrected Q2 no longer leaks)", no_event and not wrong_sess
                  and not bcs058_wrong, f"event={no_event} sess={len(wrong_sess)} daily={len(bcs058_wrong)}")
            check("5b. 2026-10-05 BCS-058: Monday lecture AND its independent "
                  "quiz-day occurrence (Option A: exactly one quiz-day-shaped "
                  "session, 2 non-cancelled occurrences)",
                  len(bcs058_correct) == 2 and len(qd_1005) == 1,
                  f"occ={len(bcs058_correct)} qd={len(qd_1005)}")

            # --- 6. E: markability — a past quiz-day occurrence marks once ---
            x = await pick_uncovered_past_date(client, "BCS-501")
            my_dates.add(x)
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("QUIZ_DAY", "BCS-501", x))
            check("6. new QUIZ_DAY (BCS-501) on uncovered past date -> 201",
                  r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
            if r.status_code == 201:
                ev_id = uuid.UUID(r.json()["id"])
                test_event_ids.append(ev_id)
                async with AsyncSessionLocal() as db:
                    sess = await qd_sessions_on(db, x, "BCS-501")
                check("6b. quiz-day session materialized on the date (G)",
                      len(sess) == 1 and not sess[0].is_cancelled, f"n={len(sess)}")
                if len(sess) == 1:
                    daily = await client.get(f"/api/v1/attendance/daily/{x.isoformat()}", headers=admin_headers)
                    occ = [s for s in daily.json()["sessions"] if s["subject_code"] == "BCS-501"]
                    mark = await client.post("/api/v1/attendance", headers=admin_headers, json={
                        "class_session_id": str(sess[0].id), "status": "Attended"})
                    check("6c. quiz-day session is attendance-bearing (C) and marks "
                          "exactly once (E)", mark.status_code == 200
                          and occ and occ[0]["start_time"] is None and occ[0]["status"] == "Pending",
                          f"mark={mark.status_code} daily={occ[0] if occ else None}")
                    async with AsyncSessionLocal() as db:
                        n_rec = (await db.execute(select(func.count()).select_from(AttendanceRecord)
                                                  .where(AttendanceRecord.class_session_id == sess[0].id))).scalar()
                    check("6d. exactly ONE attendance record after one mark",
                          n_rec == 1, f"records={n_rec}")
                    daily = await client.get(f"/api/v1/attendance/daily/{x.isoformat()}", headers=admin_headers)
                    occ = [s for s in daily.json()["sessions"] if s["subject_code"] == "BCS-501"]
                    hist = await client.get(
                        f"/api/v1/attendance/history?date_from={x.isoformat()}&date_to={x.isoformat()}",
                        headers=admin_headers)
                    items = [i for i in hist.json()["items"] if i["subject_code"] == "BCS-501"]
                    summary = (await client.get("/api/v1/attendance/summary/BCS-501",
                                                headers=admin_headers)).json()
                    check("6e. attendance appears in Track, History and subject "
                          "analytics (F)", occ and occ[0]["status"] == "Attended"
                          and len(items) == 1 and items[0]["status"] == "Attended"
                          and summary["lecture"]["attended"] >= 1)

            # --- 7. H: rescheduling removes the old unattended occurrence ---
            x2 = await pick_uncovered_past_date(client, "BCS-501")
            while x2 == x:
                x2 = await pick_uncovered_past_date(client, "BCS-501")
            my_dates.add(x2)
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("QUIZ_DAY", "BCS-501", x2))
            if r.status_code == 201:
                ev_id2 = uuid.UUID(r.json()["id"])
                test_event_ids.append(ev_id2)
                async with AsyncSessionLocal() as db:
                    before = await qd_sessions_on(db, x2, "BCS-501")
                y2 = await pick_uncovered_past_date(client, "BCS-501")
                while y2 in (x, x2):
                    y2 = await pick_uncovered_past_date(client, "BCS-501")
                my_dates.add(y2)
                r = await client.patch(f"/api/v1/events/{ev_id2}", headers=admin_headers, json={
                    "start_date": y2.isoformat(), "end_date": y2.isoformat()})
                ok = r.status_code == 200
                async with AsyncSessionLocal() as db:
                    gone = await qd_sessions_on(db, x2, "BCS-501")
                    gained = await qd_sessions_on(db, y2, "BCS-501")
                check("7. reschedule (H): old unattended quiz-day occurrence removed, "
                      "new one materialized", ok and len(before) == 1 and not gone
                      and len(gained) == 1, f"patch={r.status_code} before={len(before)} "
                      f"old={len(gone)} new={len(gained)}")

            # --- 8. I: seeded session on 10-23 untouched by this verifier ---
            async with AsyncSessionLocal() as db:
                seed_sess = await qd_sessions_on(db, SEED_054, "BCS-054")
            check("8. canonical seeded 10-23 BCS-054 quiz-day session intact",
                  len(seed_sess) == 1 and not seed_sess[0].is_cancelled, f"n={len(seed_sess)}")

    finally:
        async with AsyncSessionLocal() as db:
            events = (await db.execute(
                select(AcademicEvent).where(AcademicEvent.note.like(f"{EVENT_TITLE_PREFIX}%"))
            )).scalars().all()
            for ev in events:
                await db.delete(ev)

            qd_sessions = (await db.execute(select(ClassSession).where(
                ClassSession.date.in_(my_dates),
                ClassSession.timetable_entry_id.is_(None),
                ClassSession.is_extra.is_(False),
                ClassSession.class_type == ClassType.LECTURE,
            ))).scalars().all()
            doomed = {s.id for s in qd_sessions}
            if doomed:
                await db.execute(delete(AttendanceRecord).where(
                    AttendanceRecord.class_session_id.in_(doomed)))
                await db.execute(delete(ClassSession).where(ClassSession.id.in_(doomed)))
            await db.commit()

            events_after = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
            sessions_after = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
            cancelled_after = (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.is_cancelled.is_(True)))).scalar()
            extra_after = (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.is_extra.is_(True)))).scalar()
            records_after = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
            enrollments_after = (await db.execute(select(func.count()).select_from(
                __import__("app.models.academic", fromlist=["StudentEnrollment"]).StudentEnrollment))).scalar()
            subjects_after = (await db.execute(select(func.count()).select_from(Subject))).scalar()
            quizzes_after = (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar()
            users_after = (await db.execute(select(func.count()).select_from(User))).scalar()
            admins_after = (await db.execute(select(func.count()).select_from(User).where(
                User.role == UserRole.ADMIN))).scalar()

        check("9. exact baseline restoration (I): events/sessions/cancelled/extra/"
              "records/enrollments/subjects/quizzes/users/admins",
              events_before == events_after and sessions_before == sessions_after
              and cancelled_before == cancelled_after and extra_before == extra_after
              and records_before == records_after and enrollments_before == enrollments_after
              and subjects_before == subjects_after and quizzes_before == quizzes_after
              and users_before == users_after and admins_before == admins_after,
              f"events {events_before}->{events_after} sessions {sessions_before}->{sessions_after} "
              f"cancelled {cancelled_before}->{cancelled_after} extra {extra_before}->{extra_after} "
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