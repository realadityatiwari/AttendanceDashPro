"""
Focused Events-tab correction verification (post-Phase 9.2.1 correction).

Verifies the Phase 9.3-scoped correction against the real database (httpx
ASGITransport + real DB + minted JWTs, the established pattern):

  * CLASS_CANCELLED is LECTURE/TUTORIAL-only (PRACTICAL -> 422) and date-aware
    on the frontend (backend already cancelled only what the timetable has);
  * SURPRISE_QUIZ / QUIZ_DAY are theory-only (lab subjects -> 422 via the
    canonical Subject.category; the frontend scopes the dropdown to
    quiz_applicable subjects); QUIZ_DAY is admin-only (student -> 403)
    while SURPRISE_QUIZ stays student-creatable for enrolled subjects
    (frozen STUDENT_CREATABLE_EVENT_TYPES contract);
  * QUIZ_DAY is ONE attendance-bearing occurrence: exactly one quiz-day
    session per (subject, date) (LECTURE, is_extra=false, timetable NULL),
    created only when the subject has no non-cancelled session that date
    (a timetable class, an extra, or an existing quiz-day session all
    cover — never duplicates the seeded quiz-schedule script sessions),
    removed only when the event is deactivated/moved, never when attended;
  * attendance flows through the canonical session pipeline (Track, History,
    subject summary, analytics) and stays recordable after moves;
  * regressions: extra materialization, lab block collapse, lab cancellation,
    duplicate rejection, future view-only, student authorization, eligibility
    byte-identity, exact baseline restoration.

Test dates (no overlap with any frozen verifier's window, no user data):
  past:   2026-07-31 (Fri) 2026-08-01 (Sat, non-working)
  future: 2026-11-23 .. 2026-11-28 (Mon..Sat)
  seeded: 2026-10-23 (Fri, BCS-054 script quiz-day session lives here — the
          seeded-date no-op check must never delete it)

State changes are this script's own artifacts (events titled
"VerifyEventsCorrection ...", their sessions, attendance records, and
cancellation state on the future window) and are removed in the finally
block. No frozen verifier assertion is weakened.

Usage:
    python scripts/verify_events_correction.py
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
from app.models.user import User, Section
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.academic import StudentEnrollment, Subject
from app.models.quiz import QuizSchedule
from app.models.laboratory import LaboratoryExperiment, LaboratoryRecord
from app.models.enums import AttendanceStatus, ClassType, UserRole, SessionDesignation
from app.services.attendance_service import institution_today
from sqlalchemy import select, func, delete

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


# --- test dates ---------------------------------------------------------------
PAST_A = date(2026, 7, 31)   # Friday  — BCS-503/BCS-502 uncovered Friday, BCS-553 lab day
PAST_B = date(2026, 8, 1)    # Saturday — non-working
SEED = date(2026, 10, 23)    # Friday  — BCS-054 script quiz-day session (never delete)
FUT = [date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25),
       date(2026, 11, 26), date(2026, 11, 27), date(2026, 11, 28)]  # Mon..Sat
FUT_ISO = {d.isoformat() for d in FUT}
PAST_ISO = {PAST_A.isoformat(), PAST_B.isoformat()}
MY_WINDOWS = set(FUT) | {PAST_A, PAST_B, SEED}

EVENT_TITLE_PREFIX = "VerifyEventsCorrection"


async def count_sessions(db, *conds):
    stmt = select(func.count()).select_from(ClassSession)
    if conds:
        stmt = stmt.where(*conds)
    return (await db.execute(stmt)).scalar()


async def cleanup_residue(db, subject_ids: dict) -> None:
    """Startup: remove crashed-run residue of THIS script. Residue is matched
    two ways (belt and braces): events carrying my note marker, and events on
    my windows with exactly the (event_type, subject) combos this script
    creates (catches drafts before the note marker existed). Sessions on my
    windows that are extras or quiz-day-shaped are deleted with their records
    (never the seeded script quiz-day session on 10-23), and cancellation
    state on the future window is reset. User data is never touched."""
    note_events = (await db.execute(
        select(AcademicEvent).where(AcademicEvent.note.like(f"{EVENT_TITLE_PREFIX}%"))
    )).scalars().all()
    pattern_events = (await db.execute(
        select(AcademicEvent).where(AcademicEvent.start_date.in_(MY_WINDOWS))
    )).scalars().all()
    combo = {
        ("CLASS_CANCELLED", subject_ids["BCS-501"]),
        ("CLASS_CANCELLED", subject_ids["BCS-502"]),
        ("SURPRISE_QUIZ", subject_ids["BCS-503"]),
        ("SURPRISE_QUIZ", subject_ids["BCS-502"]),
        ("QUIZ_DAY", subject_ids["BCS-503"]),
        ("QUIZ_DAY", subject_ids["BCS-501"]),
        ("EXTRA_LECTURE", subject_ids["BCS-054"]),
        ("EXTRA_PRACTICAL", subject_ids["BCS-551"]),
        ("EXTRA_TUTORIAL", subject_ids["BCS-501"]),
        ("LAB_CANCELLED", subject_ids["BCS-553"]),
    }
    for ev in note_events:
        await db.delete(ev)
    for ev in pattern_events:
        if ((ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)),
                ev.subject_id) in combo:
            await db.delete(ev)

    # Quiz-day-shaped sessions (timetable NULL, not extra, LECTURE) on my
    # windows EXCEPT 10-23 (the script session lives there).
    qd_cond = (
        ClassSession.timetable_entry_id.is_(None),
        ClassSession.is_extra.is_(False),
        ClassSession.class_type == ClassType.LECTURE,
        ClassSession.date.in_(set(FUT) | {PAST_A, PAST_B}),
    )
    extra_cond = (ClassSession.is_extra.is_(True), ClassSession.date.in_(MY_WINDOWS))
    qd_sessions = (await db.execute(select(ClassSession).where(*qd_cond))).scalars().all()
    extra_sessions = (await db.execute(select(ClassSession).where(*extra_cond))).scalars().all()
    doomed = {s.id for s in qd_sessions} | {s.id for s in extra_sessions}
    if doomed:
        await db.execute(delete(AttendanceRecord).where(
            AttendanceRecord.class_session_id.in_(doomed)))
        await db.execute(delete(ClassSession).where(ClassSession.id.in_(doomed)))

    # Cancellation residue on the future window (base rows my events cancelled).
    await db.execute(
        ClassSession.__table__.update()
        .where(ClassSession.date.in_(FUT), ClassSession.is_cancelled.is_(True))
        .values(is_cancelled=False)
    )
    await db.commit()


async def main() -> int:
    async with AsyncSessionLocal() as db:
        section = (await db.execute(select(Section))).scalars().first()
        subject_ids = {s.code: s.id for s in (await db.execute(select(Subject))).scalars().all()}
        await cleanup_residue(db, subject_ids)
        events_before = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
        sessions_before = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
        cancelled_before = (await db.execute(select(func.count()).select_from(ClassSession).where(
            ClassSession.is_cancelled.is_(True)))).scalar()
        extra_before = (await db.execute(select(func.count()).select_from(ClassSession).where(
            ClassSession.is_extra.is_(True)))).scalar()
        records_before = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
        enrollments_before = (await db.execute(select(func.count()).select_from(StudentEnrollment))).scalar()
        subjects_before = (await db.execute(select(func.count()).select_from(Subject))).scalar()
        quizzes_before = (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar()
        users_before = (await db.execute(select(func.count()).select_from(User))).scalar()
        admins_before = (await db.execute(select(func.count()).select_from(User).where(
            User.role == UserRole.ADMIN))).scalar()
        lab_exp_before = (await db.execute(select(func.count()).select_from(LaboratoryExperiment))).scalar()
        lab_rec_before = (await db.execute(select(func.count()).select_from(LaboratoryRecord))).scalar()
        designated_before = (await db.execute(select(func.count()).select_from(ClassSession).where(
            ClassSession.designation.isnot(None)))).scalar()

        admin_user = (await db.execute(select(User).where(User.roll_number == "2401220100027"))).scalars().first()
        student_user = (await db.execute(select(User).where(User.roll_number == "9999999999999"))).scalars().first()
        if admin_user is None or student_user is None:
            print("FATAL: seed users missing")
            return 1
        admin_id = admin_user.id

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    student_token = create_access_token(str(student_user.id), student_user.roll_number)
    student_headers = {"Authorization": f"Bearer {student_token}"}

    transport = httpx.ASGITransport(app=app)
    test_event_ids: list[uuid.UUID] = []

    def ev_payload(event_type: str, subject_code: str, d: date,
                   class_type: str = None, **extra) -> dict:
        payload = {
            "event_type": event_type,
            "start_date": d.isoformat(),
            "end_date": d.isoformat(),
            "subject_id": str(subject_ids[subject_code]),
            "note": f"{EVENT_TITLE_PREFIX} — {event_type} {subject_code} {d.isoformat()}",
        }
        if class_type is not None:
            payload["class_type"] = class_type
        payload.update(extra)
        return payload

    async def sessions_on(d: date, code: str = None, **filters) -> list:
        async with AsyncSessionLocal() as db:
            stmt = select(ClassSession).where(ClassSession.date == d)
            if code is not None:
                stmt = stmt.where(ClassSession.subject_id == subject_ids[code])
            for col, val in filters.items():
                stmt = stmt.where(getattr(ClassSession, col).is_(val))
            return (await db.execute(stmt)).scalars().all()

    async def quiz_day_sessions_on(d: date, code: str = None) -> list:
        async with AsyncSessionLocal() as db:
            stmt = select(ClassSession).where(
                ClassSession.date == d,
                ClassSession.timetable_entry_id.is_(None),
                ClassSession.is_extra.is_(False),
                ClassSession.class_type == ClassType.LECTURE,
            )
            if code is not None:
                stmt = stmt.where(ClassSession.subject_id == subject_ids[code])
            return (await db.execute(stmt)).scalars().all()

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            subjects = (await client.get("/api/v1/subjects", headers=admin_headers)).json()
            bcs501 = next(s for s in subjects if s["code"] == "BCS-501")
            bcs502 = next(s for s in subjects if s["code"] == "BCS-502")
            bcs503 = next(s for s in subjects if s["code"] == "BCS-503")
            bcs551 = next(s for s in subjects if s["code"] == "BCS-551")
            bcs552 = next(s for s in subjects if s["code"] == "BCS-552")
            bcs553 = next(s for s in subjects if s["code"] == "BCS-553")
            bcs054 = next(s for s in subjects if s["code"] == "BCS-054")

            # --- Baseline read values -------------------------------------------
            def summary(code: str):
                return client.get(f"/api/v1/attendance/summary/{code}?as_of_date=2026-11-30",
                                  headers=admin_headers)

            s501 = (await summary("BCS-501")).json()
            s502 = (await summary("BCS-502")).json()
            s503 = (await summary("BCS-503")).json()
            base_501_lec_total = s501["lecture"]["total"]
            base_502_lec_att = s502["lecture"]["attended"]
            base_503_lec_att = s503["lecture"]["attended"]

            def elig(code: str, quarter: int):
                return client.get(f"/api/v1/quiz-eligibility/{code}/{quarter}", headers=admin_headers)

            elig_before = {
                "BCS-501": (await elig("BCS-501", 1)).json(),
                "BCS-503": (await elig("BCS-503", 1)).json(),
                "BCS-058": (await elig("BCS-058", 3)).json(),
            }

            # --- 0. Frontend contract: quiz_applicable / category surface -------
            ok = all("quiz_applicable" in s and "category" in s for s in subjects)
            check("0. /api/v1/subjects exposes quiz_applicable + category "
                  "(frontend dropdown scoping contract)",
                  ok and next(s for s in subjects if s["code"] == "BCS-551")["category"] == "lab"
                  and next(s for s in subjects if s["code"] == "BCS-501")["category"] == "theory"
                  and next(s for s in subjects if s["code"] == "BCS-501")["quiz_applicable"] is True
                  and next(s for s in subjects if s["code"] == "BCS-551")["quiz_applicable"] is False,
                  f"codes={[s['code'] for s in subjects if not all(k in s for k in ('quiz_applicable', 'category'))]}")

            # --- 1. Student authorization (frozen 6.6 re-assert) ----------------
            r = await client.post("/api/v1/events", headers=student_headers, json={
                "event_type": "PUBLIC_HOLIDAY", "start_date": FUT[0].isoformat(),
                "end_date": FUT[0].isoformat()})
            check("1. student POST global closure /events -> 403 (frozen 6.6 re-assert)",
                  r.status_code == 403, f"got {r.status_code}")

            # --- 2. CLASS_CANCELLED: practical rejected -------------------------
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("CLASS_CANCELLED", "BCS-551", FUT[0], class_type="P"))
            check("2. CLASS_CANCELLED practical (BCS-551/P) -> 422 (L/T only)",
                  r.status_code == 422, f"got {r.status_code} {r.text[:200]}")

            # --- 3. CLASS_CANCELLED lecture: cancels the matching occurrence ----
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("CLASS_CANCELLED", "BCS-501", FUT[1], class_type="L"))
            ok = r.status_code == 201
            if ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
            cancelled_sess = None
            if ok:
                async with AsyncSessionLocal() as db:
                    rows = (await db.execute(select(ClassSession).where(
                        ClassSession.date == FUT[1], ClassSession.subject_id == subject_ids["BCS-501"]
                    ))).scalars().all()
                    lec = [s for s in rows if s.class_type == ClassType.LECTURE]
                    tut = [s for s in rows if s.class_type == ClassType.TUTORIAL]
                    cancelled_sess = lec[0] if lec and lec[0].is_cancelled else None
                    ok = (len(rows) == 2 and len(lec) == 1 and lec[0].is_cancelled
                          and len(tut) == 1 and not tut[0].is_cancelled)
            check("3. CLASS_CANCELLED BCS-501/L 11-24 -> 201; lecture cancelled, "
                  "tutorial untouched", ok, f"got {r.status_code} {r.text[:200]}")
            if cancelled_sess is not None:
                r = await client.post("/api/v1/attendance", headers=admin_headers, json={
                    "class_session_id": str(cancelled_sess.id), "status": "Attended"})
                check("3b. cancelled lecture rejects attendance marking (409, cancelled != absent)",
                      r.status_code == 409, f"got {r.status_code} {r.text[:150]}")
            r = await summary("BCS-501")
            check("3c. BCS-501 lecture total drops by exactly 1 (cancelled excluded from totals)",
                  r.json()["lecture"]["total"] == base_501_lec_total - 1,
                  f"baseline={base_501_lec_total} now={r.json()['lecture']['total']}")
            r = await client.get(f"/api/v1/attendance/daily/{FUT[1].isoformat()}", headers=admin_headers)
            occ = [s for s in r.json()["sessions"] if s["subject_code"] == "BCS-501"]
            check("3d. Track daily 11-24: lecture occurrence Cancelled, tutorial Pending",
                  len(occ) == 2 and any(s["class_type"] == "L" and s["is_cancelled"] for s in occ)
                  and any(s["class_type"] == "T" and s["status"] == "Pending" for s in occ),
                  f"got {[(s['class_type'], s['status'], s['is_cancelled']) for s in occ]}")

            # --- 4. CLASS_CANCELLED on a no-class day: graceful no-op -----------
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("CLASS_CANCELLED", "BCS-501", FUT[0], class_type="L"))
            ok = r.status_code == 201
            if ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
            async with AsyncSessionLocal() as db:
                n = await count_sessions(db, ClassSession.date == FUT[0])
                cancelled = await count_sessions(
                    db, (ClassSession.date == FUT[0]) & ClassSession.is_cancelled.is_(True))
            check("4. CLASS_CANCELLED BCS-501/L 11-23 (no Monday class) -> 201, "
                  "nothing cancelled, nothing created", ok and n == 5 and cancelled == 0,
                  f"got {r.status_code} rows={n} cancelled={cancelled}")

            # --- 5. CLASS_CANCELLED tutorial ------------------------------------
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("CLASS_CANCELLED", "BCS-502", FUT[4], class_type="T"))
            ok = r.status_code == 201
            if ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
            async with AsyncSessionLocal() as db:
                rows = (await db.execute(select(ClassSession).where(
                    ClassSession.date == FUT[4], ClassSession.subject_id == subject_ids["BCS-502"]
                ))).scalars().all()
                ok = ok and len(rows) == 2 \
                    and any(s.class_type == ClassType.TUTORIAL and s.is_cancelled for s in rows) \
                    and any(s.class_type == ClassType.LECTURE and not s.is_cancelled for s in rows)
            check("5. CLASS_CANCELLED BCS-502/T 11-27 -> 201; tutorial cancelled, "
                  "lecture untouched", ok, f"got {r.status_code} {r.text[:200]}")

            # --- 6/7. Quiz events reject lab subjects (422) ---------------------
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("SURPRISE_QUIZ", "BCS-551", FUT[1], class_type="L"))
            check("6. SURPRISE_QUIZ on lab subject (BCS-551) -> 422",
                  r.status_code == 422, f"got {r.status_code} {r.text[:200]}")
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("QUIZ_DAY", "BCS-552", FUT[1]))
            check("7. QUIZ_DAY on lab subject (BCS-552) -> 422",
                  r.status_code == 422, f"got {r.status_code} {r.text[:200]}")

            # --- 8. SURPRISE_QUIZ materializes one extra ------------------------
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("SURPRISE_QUIZ", "BCS-503", FUT[0], class_type="L"))
            ok = r.status_code == 201
            if ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
            extras = await sessions_on(FUT[0], "BCS-503", is_extra=True)
            extra_sess = extras[0] if len(extras) == 1 else None
            check("8. SURPRISE_QUIZ BCS-503/L 11-23 -> 201; exactly one extra "
                  "(LECTURE, timetable NULL)",
                  ok and extra_sess is not None and extra_sess.class_type == ClassType.LECTURE
                  and extra_sess.timetable_entry_id is None,
                  f"got {r.status_code} extras={len(extras)}")
            if extra_sess is not None:
                r = await client.post("/api/v1/attendance", headers=admin_headers, json={
                    "class_session_id": str(extra_sess.id), "status": "Attended"})
                check("8b. future surprise-quiz extra is view-only (400)",
                      r.status_code == 400, f"got {r.status_code} {r.text[:150]}")

            # --- 9. QUIZ_DAY never duplicates an existing occurrence -----------
            # The surprise-quiz extra (check 8) already covers BCS-503 on 11-23,
            # so the quiz-day bucket must NOT create a second occurrence — the
            # "one attendance-bearing occurrence per (subject, date)" rule.
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("QUIZ_DAY", "BCS-503", FUT[0]))
            ok = r.status_code == 201
            if ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
                quiz_day_event_id = uuid.UUID(r.json()["id"])
            else:
                quiz_day_event_id = None
            qd = await quiz_day_sessions_on(FUT[0], "BCS-503")
            async with AsyncSessionLocal() as db:
                total = await count_sessions(db, ClassSession.date == FUT[0])
            check("9. QUIZ_DAY BCS-503 11-23 -> 201; no second occurrence "
                  "(surprise-quiz extra covers; 5 + 1 extra = 6, quiz_day=0)",
                  ok and len(qd) == 0 and total == 6,
                  f"got {r.status_code} quiz_day={len(qd)} total={total}")
            r = await client.get(f"/api/v1/attendance/daily/{FUT[0].isoformat()}", headers=admin_headers)
            daily_1123 = r.json()["sessions"]
            qd_occ = [s for s in daily_1123 if s["subject_code"] == "BCS-503"]
            check("9c. Track daily 11-23: 5 occurrences (BCS-551 block counts "
                  "once), the surprise-quiz extra is the single BCS-503 occurrence",
                  len(daily_1123) == 5 and len(qd_occ) == 1 and qd_occ[0]["is_extra"],
                  f"daily={len(daily_1123)} bcs503={[(s['class_type'], s['is_extra']) for s in qd_occ]}")

            # --- 10. Duplicate QUIZ_DAY rejected --------------------------------
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("QUIZ_DAY", "BCS-503", FUT[0]))
            async with AsyncSessionLocal() as db:
                total = await count_sessions(db, ClassSession.date == FUT[0])
            check("10. duplicate QUIZ_DAY BCS-503 11-23 -> 409, no extra occurrence",
                  r.status_code == 409 and total == 6, f"got {r.status_code} total={total}")

            # --- 11. Reschedule to a covered date: no duplicate, old removed ----
            r = await client.patch(f"/api/v1/events/{quiz_day_event_id}", headers=admin_headers,
                                   json={"start_date": FUT[1].isoformat(), "end_date": FUT[1].isoformat()})
            ok = r.status_code == 200
            async with AsyncSessionLocal() as db:
                d23 = await count_sessions(db, ClassSession.date == FUT[0])
                d24 = await count_sessions(db, ClassSession.date == FUT[1])
            qd24 = await quiz_day_sessions_on(FUT[1], "BCS-503")
            qd23 = await quiz_day_sessions_on(FUT[0], "BCS-503")
            check("11. PATCH quiz-day 11-23 -> 11-24: old occurrence removed "
                  "(5 + surprise extra), none on 11-24 (covered by Tue L+T)",
                  ok and d23 == 6 and len(qd23) == 0 and d24 == 6 and len(qd24) == 0,
                  f"11-23={d23}(qd={len(qd23)}) 11-24={d24}(qd={len(qd24)})")

            # --- 12. Reschedule to an uncovered date: occurrence appears --------
            r = await client.patch(f"/api/v1/events/{quiz_day_event_id}", headers=admin_headers,
                                   json={"start_date": FUT[4].isoformat(), "end_date": FUT[4].isoformat()})
            ok = r.status_code == 200
            async with AsyncSessionLocal() as db:
                d27 = await count_sessions(db, ClassSession.date == FUT[4])
            qd27 = await quiz_day_sessions_on(FUT[4], "BCS-503")
            check("12. PATCH quiz-day 11-24 -> 11-27: Friday 5 + 1 quiz-day = 6",
                  ok and d27 == 6 and len(qd27) == 1,
                  f"11-27={d27} quiz_day={len(qd27)}")

            # --- 13. Deactivation removes the unattended occurrence -------------
            r = await client.delete(f"/api/v1/events/{quiz_day_event_id}", headers=admin_headers)
            ok = r.status_code == 200
            async with AsyncSessionLocal() as db:
                d27 = await count_sessions(db, ClassSession.date == FUT[4])
            qd27 = await quiz_day_sessions_on(FUT[4], "BCS-503")
            check("13. DELETE quiz-day event: 11-27 back to 5, no quiz-day session",
                  ok and d27 == 5 and len(qd27) == 0, f"11-27={d27} quiz_day={len(qd27)}")

            # --- 14. Non-working day: zero sessions -----------------------------
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("QUIZ_DAY", "BCS-503", FUT[5]))
            ok = r.status_code == 201
            async with AsyncSessionLocal() as db:
                n = await count_sessions(db, ClassSession.date == FUT[5])
            if ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
                await client.delete(f"/api/v1/events/{test_event_ids[-1]}", headers=admin_headers)
            check("14. QUIZ_DAY BCS-503 11-28 (Saturday): 201, zero sessions",
                  ok and n == 0, f"got {r.status_code} rows={n}")

            # --- 15. Covered-date creation suppression --------------------------
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("QUIZ_DAY", "BCS-501", FUT[1]))
            ok = r.status_code == 201
            qd = await quiz_day_sessions_on(FUT[1], "BCS-501")
            if ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
                await client.delete(f"/api/v1/events/{test_event_ids[-1]}", headers=admin_headers)
            check("15. QUIZ_DAY BCS-501 11-24 (lecture cancelled, tutorial covers): "
                  "201, no quiz-day session created",
                  ok and len(qd) == 0, f"got {r.status_code} quiz_day={len(qd)}")

            # --- 16. Past surprise quiz: attendance through the pipeline --------
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("SURPRISE_QUIZ", "BCS-502", PAST_A, class_type="L"))
            ok = r.status_code == 201
            if ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
                sq_event_id = uuid.UUID(r.json()["id"])
            else:
                sq_event_id = None
            extras = await sessions_on(PAST_A, "BCS-502", is_extra=True)
            ok = ok and len(extras) == 1
            if ok:
                r = await client.post("/api/v1/attendance", headers=admin_headers, json={
                    "class_session_id": str(extras[0].id), "status": "Attended"})
                ok = r.status_code == 200
            check("16. SURPRISE_QUIZ BCS-502/L 07-31 -> 201, exactly one extra, "
                  "attendance recorded (200)", ok, f"got {r.status_code} {r.text[:200]}")
            if ok:
                r = await client.get("/api/v1/attendance/history?date_from=2026-07-31&date_to=2026-07-31",
                                     headers=admin_headers)
                hist = r.json()
                mine = [i for i in hist["items"] if i["id"] == str(extras[0].id)]
                check("16b. History shows the surprise-quiz extra as Attended",
                      len(mine) == 1 and mine[0]["status"] == "Attended"
                      and mine[0]["is_extra"] is True and mine[0]["subject_code"] == "BCS-502",
                      f"items={[(i['subject_code'], i['status']) for i in hist['items']]}")
                r = await summary("BCS-502")
                check("16c. BCS-502 lecture attended +1 (as_of 11-30)",
                      r.json()["lecture"]["attended"] == base_502_lec_att + 1,
                      f"baseline={base_502_lec_att} now={r.json()['lecture']['attended']}")
                r = await client.get("/api/v1/analytics/overview", headers=admin_headers)
                subj = next((s for s in r.json()["subjects"] if s["subject_code"] == "BCS-502"), None)
                check("16d. analytics overview: BCS-502 lecture attended +1",
                      subj is not None and subj["lecture"]["attended"] == base_502_lec_att + 1,
                      f"got {subj['lecture']['attended'] if subj else None}")

            # --- 17. Past quiz day: attendance through the pipeline -------------
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("QUIZ_DAY", "BCS-503", PAST_A))
            ok = r.status_code == 201
            if ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
                qd_event_id = uuid.UUID(r.json()["id"])
            else:
                qd_event_id = None
            qd = await quiz_day_sessions_on(PAST_A, "BCS-503")
            ok = ok and len(qd) == 1
            if ok:
                r = await client.post("/api/v1/attendance", headers=admin_headers, json={
                    "class_session_id": str(qd[0].id), "status": "Attended"})
                ok = r.status_code == 200
            check("17. QUIZ_DAY BCS-503 07-31 -> 201, exactly one quiz-day session, "
                  "attendance recorded (200)", ok, f"got {r.status_code} {r.text[:200]}")
            if ok:
                r = await client.get(f"/api/v1/attendance/daily/{PAST_A.isoformat()}", headers=admin_headers)
                occ = [s for s in r.json()["sessions"]
                       if s["subject_code"] == "BCS-503" and not s["is_extra"]]
                check("17b. Track daily 07-31: quiz-day occurrence Attended",
                      len(occ) == 1 and occ[0]["status"] == "Attended"
                      and occ[0]["class_type"] == "L", f"got {occ}")
                r = await client.get("/api/v1/attendance/history?date_from=2026-07-31&date_to=2026-07-31",
                                     headers=admin_headers)
                mine = [i for i in r.json()["items"] if i["id"] == str(qd[0].id)]
                check("17c. History shows the quiz-day session as Attended",
                      len(mine) == 1 and mine[0]["status"] == "Attended"
                      and mine[0]["is_extra"] is False and mine[0]["subject_code"] == "BCS-503",
                      f"items={[(i['subject_code'], i['status'], i['is_extra']) for i in r.json()['items']]}")
                r = await summary("BCS-503")
                check("17d. BCS-503 lecture attended +1 (as_of 11-30)",
                      r.json()["lecture"]["attended"] == base_503_lec_att + 1,
                      f"baseline={base_503_lec_att} now={r.json()['lecture']['attended']}")

            # --- 18. Move with attendance: attended session is never removed ----
            if qd_event_id is not None:
                r = await client.patch(f"/api/v1/events/{qd_event_id}", headers=admin_headers,
                                       json={"start_date": PAST_B.isoformat(), "end_date": PAST_B.isoformat()})
                ok = r.status_code == 200
            qd31 = await quiz_day_sessions_on(PAST_A, "BCS-503")
            qd01 = await quiz_day_sessions_on(PAST_B, "BCS-503")
            async with AsyncSessionLocal() as db:
                rec = (await db.execute(select(AttendanceRecord).where(
                    AttendanceRecord.class_session_id.in_([s.id for s in qd31])
                ))).scalars().all()
            check("18. PATCH quiz-day 07-31 -> 08-01: attended session preserved "
                  "on 07-31 (record intact), nothing on Saturday",
                  ok and len(qd31) == 1 and len(rec) == 1 and rec[0].status == AttendanceStatus.ATTENDED
                  and len(qd01) == 0, f"07-31={len(qd31)} records={len(rec)} 08-01={len(qd01)}")

            # --- 19. Deactivation with attendance: historical truth stays -------
            r = await client.delete(f"/api/v1/events/{qd_event_id}", headers=admin_headers)
            ok = r.status_code == 200
            qd31 = await quiz_day_sessions_on(PAST_A, "BCS-503")
            check("19. DELETE quiz-day event: attended 07-31 session STAYS",
                  ok and len(qd31) == 1, f"07-31 quiz_day={len(qd31)}")
            if sq_event_id is not None:
                r = await client.delete(f"/api/v1/events/{sq_event_id}", headers=admin_headers)
                ok = r.status_code == 200
            extras = await sessions_on(PAST_A, "BCS-502", is_extra=True)
            check("19b. DELETE surprise-quiz event: attended 07-31 extra STAYS",
                  ok and len(extras) == 1, f"07-31 extras={len(extras)}")

            # --- 20. Seeded quiz date: script session never duplicated ----------
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("EXTRA_LECTURE", "BCS-054", SEED, class_type="L"))
            ok = r.status_code == 201
            if ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
                seed_extra_id = uuid.UUID(r.json()["id"])
            else:
                seed_extra_id = None
            extras = await sessions_on(SEED, "BCS-054", is_extra=True)
            qd_seed = await quiz_day_sessions_on(SEED, "BCS-054")
            async with AsyncSessionLocal() as db:
                total = await count_sessions(db, ClassSession.date == SEED)
            check("20. EXTRA_LECTURE BCS-054 10-23: extra created, script quiz-day "
                  "session intact, no duplicate (7 = 5 + extra + script)",
                  ok and len(extras) == 1 and len(qd_seed) == 1 and total == 7,
                  f"extras={len(extras)} script_qd={len(qd_seed)} total={total}")
            if seed_extra_id is not None:
                r = await client.delete(f"/api/v1/events/{seed_extra_id}", headers=admin_headers)
                ok = r.status_code == 200
            extras = await sessions_on(SEED, "BCS-054", is_extra=True)
            qd_seed = await quiz_day_sessions_on(SEED, "BCS-054")
            check("20b. cleanup of the extra restores 10-23; script session untouched",
                  ok and len(extras) == 0 and len(qd_seed) == 1,
                  f"extras={len(extras)} script_qd={len(qd_seed)}")

            # --- 21. Regression: EXTRA_PRACTICAL + block collapse ---------------
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("EXTRA_PRACTICAL", "BCS-551", FUT[3], class_type="P"))
            ok = r.status_code == 201
            extra_pract_id = uuid.UUID(r.json()["id"]) if ok else None
            extras = await sessions_on(FUT[3], "BCS-551", is_extra=True)
            async with AsyncSessionLocal() as db:
                total = await count_sessions(db, ClassSession.date == FUT[3])
            r = await client.get(f"/api/v1/attendance/daily/{FUT[3].isoformat()}", headers=admin_headers)
            occ551 = [s for s in r.json()["sessions"] if s["subject_code"] == "BCS-551"]
            if extra_pract_id is not None:
                await client.delete(f"/api/v1/events/{extra_pract_id}", headers=admin_headers)
            check("21. EXTRA_PRACTICAL BCS-551/P 11-26 -> one extra P occurrence "
                  "(BCS-552 block still counts once; Thursday 6 + 1 = 7 rows)",
                  ok and len(extras) == 1 and total == 7 and len(occ551) == 1,
                  f"extras={len(extras)} total={total} occ551={len(occ551)}")

            # --- 22. Regression: EXTRA_TUTORIAL ---------------------------------
            # 11-25 (Wednesday) has no BCS-501 class (Wed schedule: BCS-054 L,
            # BCS-503 L, BNC-501 L, BCS-502 L, BCS-058 L, BCS-054 T), so the
            # extra tutorial is the only BCS-501 occurrence that day.
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("EXTRA_TUTORIAL", "BCS-501", FUT[2], class_type="T"))
            ok = r.status_code == 201
            extra_tut_id = uuid.UUID(r.json()["id"]) if ok else None
            extras = await sessions_on(FUT[2], "BCS-501", is_extra=True)
            r = await client.get(f"/api/v1/attendance/daily/{FUT[2].isoformat()}", headers=admin_headers)
            occ501 = [s for s in r.json()["sessions"] if s["subject_code"] == "BCS-501"]
            if extra_tut_id is not None:
                await client.delete(f"/api/v1/events/{extra_tut_id}", headers=admin_headers)
            check("22. EXTRA_TUTORIAL BCS-501/T 11-25 -> one extra, the only "
                  "BCS-501 occurrence in Track (Wed has no BCS-501 class)",
                  ok and len(extras) == 1 and len(occ501) == 1 and occ501[0]["is_extra"],
                  f"extras={len(extras)} occ501={len(occ501)}")

            # --- 23. Regression: LAB_CANCELLED block ----------------------------
            r = await client.post("/api/v1/events", headers=admin_headers,
                                  json=ev_payload("LAB_CANCELLED", "BCS-553", FUT[4], class_type="P"))
            ok = r.status_code == 201
            if ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
                lab_cancel_id = uuid.UUID(r.json()["id"])
            else:
                lab_cancel_id = None
            async with AsyncSessionLocal() as db:
                rows553 = (await db.execute(select(ClassSession).where(
                    ClassSession.date == FUT[4], ClassSession.subject_id == subject_ids["BCS-553"]
                ))).scalars().all()
                cancelled_553 = [s for s in rows553 if s.is_cancelled]
                cancelled_sess = cancelled_553[0] if len(cancelled_553) == 1 else None
            r = await client.get(f"/api/v1/attendance/daily/{FUT[4].isoformat()}", headers=admin_headers)
            occ553 = [s for s in r.json()["sessions"] if s["subject_code"] == "BCS-553"]
            check("23. LAB_CANCELLED BCS-553 11-27 -> block occurrence cancelled "
                  "(exactly one row; one Track occurrence)",
                  ok and len(rows553) == 2 and len(cancelled_553) == 1
                  and len(occ553) == 1 and occ553[0]["is_cancelled"],
                  f"rows={len(rows553)} cancelled={len(cancelled_553)} occ553={len(occ553)}")
            if cancelled_sess is not None:
                r = await client.post("/api/v1/attendance", headers=admin_headers, json={
                    "class_session_id": str(cancelled_sess.id), "status": "Attended"})
                check("23b. cancelled lab block rejects attendance (409)",
                      r.status_code == 409, f"got {r.status_code}")

            # --- 24. Quiz authorization (frozen registry contract) --------------
            # QUIZ_DAY drives the shared quiz schedule -> admin-only. SURPRISE_QUIZ
            # is a flexible class-reality type in STUDENT_CREATABLE_EVENT_TYPES
            # (enrolled-subject semantics, mirroring 9.1 check 1).
            r = await client.post("/api/v1/events", headers=student_headers,
                                  json=ev_payload("QUIZ_DAY", "BCS-503", FUT[5]))
            check("24. student QUIZ_DAY -> 403 (quiz-schedule events are "
                  "admin-restricted)", r.status_code == 403, f"got {r.status_code} {r.text[:200]}")
            r = await client.post("/api/v1/events", headers=student_headers,
                                  json=ev_payload("SURPRISE_QUIZ", "BCS-503", FUT[5], class_type="L"))
            ok = r.status_code == 201
            if ok:
                await client.delete(f"/api/v1/events/{uuid.UUID(r.json()['id'])}", headers=student_headers)
            check("24b. student SURPRISE_QUIZ for enrolled subject -> 201 "
                  "(frozen student-creatable contract)", ok, f"got {r.status_code} {r.text[:200]}")

    finally:
        # --- Cleanup: exact restoration ---------------------------------------
        async with AsyncSessionLocal() as db:
            events = (await db.execute(
                select(AcademicEvent).where(AcademicEvent.note.like(f"{EVENT_TITLE_PREFIX}%"))
            )).scalars().all()
            for ev in events:
                await db.delete(ev)

            qd_cond = (
                ClassSession.timetable_entry_id.is_(None),
                ClassSession.is_extra.is_(False),
                ClassSession.class_type == ClassType.LECTURE,
                ClassSession.date.in_(set(FUT) | {PAST_A, PAST_B}),
            )
            extra_cond = (ClassSession.is_extra.is_(True), ClassSession.date.in_(MY_WINDOWS))
            qd_sessions = (await db.execute(select(ClassSession).where(*qd_cond))).scalars().all()
            extra_sessions = (await db.execute(select(ClassSession).where(*extra_cond))).scalars().all()
            doomed = {s.id for s in qd_sessions} | {s.id for s in extra_sessions}
            if doomed:
                await db.execute(delete(AttendanceRecord).where(
                    AttendanceRecord.class_session_id.in_(doomed)))
                await db.execute(delete(ClassSession).where(ClassSession.id.in_(doomed)))

            await db.execute(
                ClassSession.__table__.update()
                .where(ClassSession.date.in_(FUT), ClassSession.is_cancelled.is_(True))
                .values(is_cancelled=False)
            )
            await db.commit()

            events_after = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
            sessions_after = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
            cancelled_after = (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.is_cancelled.is_(True)))).scalar()
            extra_after = (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.is_extra.is_(True)))).scalar()
            records_after = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
            enrollments_after = (await db.execute(select(func.count()).select_from(StudentEnrollment))).scalar()
            subjects_after = (await db.execute(select(func.count()).select_from(Subject))).scalar()
            quizzes_after = (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar()
            users_after = (await db.execute(select(func.count()).select_from(User))).scalar()
            admins_after = (await db.execute(select(func.count()).select_from(User).where(
                User.role == UserRole.ADMIN))).scalar()
            lab_exp_after = (await db.execute(select(func.count()).select_from(LaboratoryExperiment))).scalar()
            lab_rec_after = (await db.execute(select(func.count()).select_from(LaboratoryRecord))).scalar()
            designated_after = (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.designation.isnot(None)))).scalar()

        check("25. exact baseline restoration (events/sessions/cancelled/extra/"
              "records/enrollments/subjects/quizzes/users/admins/lab/designation)",
              events_before == events_after and sessions_before == sessions_after
              and cancelled_before == cancelled_after and extra_before == extra_after
              and records_before == records_after and enrollments_before == enrollments_after
              and subjects_before == subjects_after and quizzes_before == quizzes_after
              and users_before == users_after and admins_before == admins_after
              and lab_exp_before == lab_exp_after and lab_rec_before == lab_rec_after
              and designated_before == designated_after,
              f"events {events_before}->{events_after} sessions {sessions_before}->{sessions_after} "
              f"cancelled {cancelled_before}->{cancelled_after} extra {extra_before}->{extra_after} "
              f"records {records_before}->{records_after}")

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            elig_after = {
                "BCS-501": (await elig("BCS-501", 1)).json(),
                "BCS-503": (await elig("BCS-503", 1)).json(),
                "BCS-058": (await elig("BCS-058", 3)).json(),
            }
        check("26. quiz eligibility byte-identical (BCS-501 Q1, BCS-503 Q1, BCS-058 Q3)",
              elig_before == elig_after, "")

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:")
        for name in failed:
            print(f"  - {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))