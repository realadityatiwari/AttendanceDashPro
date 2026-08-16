"""
Phase 6.6 verification — event -> engine session integration.

Runs against the real api_router and the real database (httpx ASGITransport,
minted JWTs for the admin 2401220100027 and the registration-verification
student 9999999999999), plus direct in-process synchronizer checks inside a
transaction that is rolled back. No browser automation, no E2E suite.

Design:
- API-level tests persist real event rows through the admin API (the service
  commits), verify their session effects via SQL and via the frozen student
  read contracts (calendar / daily / history / attendance summary /
  eligibility), then deactivate + hard-delete ONLY this script's event rows.
  Deactivation is itself a reversal test: sessions restored, extras removed.
- Rollback-level tests exercise attendance-bound protection and range events
  inside one transaction that is never committed.
- The script starts by removing orphan extra sessions left behind by the
  Phase 6.5 verifier's EXTRA_LECTURE test (its cleanup deletes event rows but
  Phase 6.6 session effects are new) — only unattended extras on the 6.5
  test date 2026-11-02.

Usage:
    python scripts/verify_phase_6_6.py
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
from app.models.enums import AttendanceStatus, ClassType, EventType
from app.services.event_session_service import EventSessionSynchronizer
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
    async with AsyncSessionLocal() as db:
        admin_user = (await db.execute(select(User).where(User.roll_number == "2401220100027"))).scalars().first()
        student_user = (await db.execute(select(User).where(User.roll_number == "9999999999999"))).scalars().first()
        if admin_user is None or student_user is None:
            print("ERROR: required users not found")
            return 1

        events_before = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()

        # Orphan artifacts from earlier crashed/buggy runs of this verifier on
        # the test window (2026-11-02 .. 2026-11-07): Phase 6.5's EXTRA_LECTURE
        # test now creates sessions (its cleanup deletes only event rows), and
        # earlier 6.6 runs left extras / weekend projections / cancelled rows
        # behind. Restore the known baseline: delete unattended extras and
        # weekend projections, un-cancel unattended cancelled sessions.
        window_start, window_end = date(2026, 11, 2), date(2026, 11, 7)
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

        # Baseline is recorded AFTER cleanup: the assertion at the end compares
        # against this clean state.
        sessions_before = await count_sessions(db, ClassSession.id.is_not(None))
        cancelled_before = await count_sessions(db, ClassSession.is_cancelled.is_(True))
        extra_before = await count_sessions(db, ClassSession.is_extra.is_(True))
        records_before = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
        print(f"baseline: events={events_before} sessions={sessions_before} cancelled={cancelled_before} "
              f"extra={extra_before} records={records_before}")

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    student_token = create_access_token(str(student_user.id), student_user.roll_number)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    transport = httpx.ASGITransport(app=app)
    test_event_ids: list[uuid.UUID] = []

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            subjects = (await client.get("/api/v1/subjects", headers=admin_headers)).json()
            bcs501 = next(s for s in subjects if s["code"] == "BCS-501")
            bcs502 = next(s for s in subjects if s["code"] == "BCS-502")
            bcs503 = next(s for s in subjects if s["code"] == "BCS-503")
            bcs551 = next(s for s in subjects if s["code"] == "BCS-551")

            # --- Baseline read values -------------------------------------------
            r = await client.get("/api/v1/attendance/summary/BCS-501?as_of_date=2026-11-30", headers=student_headers)
            baseline_lec_total = r.json()["lecture"]["total"]
            r = await client.get("/api/v1/quiz-eligibility/BCS-501/1", headers=student_headers)
            baseline_eligibility = r.json()
            check("0. eligibility BCS-501 Q1 resolves (pre-event)", r.status_code == 200, r.text[:200])

            # --- 1. Authorization unchanged (Phase 6.5 frozen) ------------------
            r = await client.post("/api/v1/events", headers=student_headers, json={
                "event_type": "PUBLIC_HOLIDAY", "start_date": "2026-11-02", "end_date": "2026-11-02"})
            check("1. student POST /events -> 403", r.status_code == 403, f"got {r.status_code}")

            # --- 2. Closure cancels the scheduled classes on the date -----------
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "PUBLIC_HOLIDAY", "start_date": "2026-11-02", "end_date": "2026-11-02"})
            check("2. admin closure on 2026-11-02 -> 201", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
            closure_id = uuid.UUID(r.json()["id"])
            test_event_ids.append(closure_id)

            async with AsyncSessionLocal() as db:
                total = await count_sessions(db, ClassSession.date == date(2026, 11, 2))
                cancelled = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 2)) & ClassSession.is_cancelled.is_(True))
            check("3. all 5 sessions on 11-02 cancelled, none deleted", total == 5 and cancelled == 5,
                  f"total={total} cancelled={cancelled}")

            # --- 3. Attendance-bound sessions are never touched -----------------
            # 2026-07-15 has 6 sessions, all with attendance records.
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "PUBLIC_HOLIDAY", "start_date": "2026-07-15", "end_date": "2026-07-15"})
            check("4. closure on fully-attended 2026-07-15 -> 201", r.status_code == 201, f"got {r.status_code}")
            attended_closure_id = uuid.UUID(r.json()["id"])
            test_event_ids.append(attended_closure_id)
            async with AsyncSessionLocal() as db:
                cancelled = await count_sessions(
                    db, (ClassSession.date == date(2026, 7, 15)) & ClassSession.is_cancelled.is_(True))
            check("5. attended sessions on 07-15 remain active (no history mutation)", cancelled == 0,
                  f"cancelled={cancelled}")

            # --- 4. CLASS_CANCELLED affects exactly the intended session --------
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "CLASS_CANCELLED", "start_date": "2026-11-03", "end_date": "2026-11-03",
                "subject_id": bcs501["id"], "class_type": "L"})
            check("6. admin CLASS_CANCELLED BCS-501/L on 11-03 -> 201", r.status_code == 201,
                  f"got {r.status_code} {r.text[:200]}")
            cancelled_event_id = uuid.UUID(r.json()["id"])
            test_event_ids.append(cancelled_event_id)
            async with AsyncSessionLocal() as db:
                total = await count_sessions(db, ClassSession.date == date(2026, 11, 3))
                cancelled = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 3)) & ClassSession.is_cancelled.is_(True))
                cancelled_bcs501 = await count_sessions(
                    db, ((ClassSession.date == date(2026, 11, 3)) & ClassSession.is_cancelled.is_(True))
                    & (ClassSession.subject_id == bcs501["id"]) & (ClassSession.class_type == ClassType.LECTURE))
                cancelled_bcs551 = await count_sessions(
                    db, ((ClassSession.date == date(2026, 11, 3)) & ClassSession.is_cancelled.is_(True))
                    & (ClassSession.subject_id == bcs551["id"]))
            check("7. exactly one BCS-501/L session cancelled on 11-03",
                  total == 6 and cancelled == 1 and cancelled_bcs501 == 1 and cancelled_bcs551 == 0,
                  f"total={total} cancelled={cancelled} bcs501_L={cancelled_bcs501} bcs551={cancelled_bcs551}")

            r = await client.get("/api/v1/attendance/summary/BCS-501?as_of_date=2026-11-30", headers=student_headers)
            lec_total_after_cancel = r.json()["lecture"]["total"]
            check("8. BCS-501 lecture total drops by exactly 1 (cancelled != pending)",
                  lec_total_after_cancel == baseline_lec_total - 1,
                  f"baseline={baseline_lec_total} now={lec_total_after_cancel}")

            # --- 5. EXTRA_LECTURE generates the session --------------------------
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "EXTRA_LECTURE", "start_date": "2026-11-04", "end_date": "2026-11-04",
                "subject_id": bcs501["id"], "class_type": "L"})
            check("9. admin EXTRA_LECTURE BCS-501/L on 11-04 -> 201", r.status_code == 201,
                  f"got {r.status_code} {r.text[:200]}")
            extra_event_id = uuid.UUID(r.json()["id"])
            test_event_ids.append(extra_event_id)
            async with AsyncSessionLocal() as db:
                total = await count_sessions(db, ClassSession.date == date(2026, 11, 4))
                extras = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.date == date(2026, 11, 4), ClassSession.is_extra.is_(True)))).scalars().all()
            check("10. one is_extra session created on 11-04 (no timetable entry)",
                  total == 7 and len(extras) == 1 and extras[0].timetable_entry_id is None
                  and str(extras[0].subject_id) == bcs501["id"] and extras[0].class_type == ClassType.LECTURE,
                  f"total={total} extras={len(extras)}")

            r = await client.get("/api/v1/attendance/summary/BCS-501?as_of_date=2026-11-30", headers=student_headers)
            lec_total_after_extra = r.json()["lecture"]["total"]
            check("11. BCS-501 lecture total restored to baseline (cancelled -1, extra +1)",
                  lec_total_after_extra == baseline_lec_total, f"baseline={baseline_lec_total} now={lec_total_after_extra}")

            # --- 6. Idempotency: re-running the sync changes nothing -------------
            async with AsyncSessionLocal() as db:
                sync = EventSessionSynchronizer(db)
                evt = (await db.execute(select(AcademicEvent).where(AcademicEvent.id == extra_event_id))).scalars().first()
                await sync.sync_event(evt)
                await db.commit()
                n1 = await count_sessions(db, ClassSession.date == date(2026, 11, 4))
                await sync.sync_event(evt)
                await db.commit()
                n2 = await count_sessions(db, ClassSession.date == date(2026, 11, 4))
            check("12. double sync produces no duplicate sessions", n1 == n2 == 7, f"n1={n1} n2={n2}")

            # --- 7. SURPRISE_QUIZ injects an extra occurrence (legacy delta +1) --
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "SURPRISE_QUIZ", "start_date": "2026-11-06", "end_date": "2026-11-06",
                "subject_id": bcs502["id"], "class_type": "L"})
            check("13. admin SURPRISE_QUIZ BCS-502/L on 11-06 -> 201", r.status_code == 201,
                  f"got {r.status_code} {r.text[:200]}")
            surprise_id = uuid.UUID(r.json()["id"])
            test_event_ids.append(surprise_id)

            # --- 8. QUIZ_DAY is calendar-only: no session effect -----------------
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "QUIZ_DAY", "start_date": "2026-11-06", "end_date": "2026-11-06",
                "subject_id": bcs503["id"]})
            check("14. admin QUIZ_DAY BCS-503 on 11-06 -> 201", r.status_code == 201,
                  f"got {r.status_code} {r.text[:200]}")
            quiz_day_id = uuid.UUID(r.json()["id"])
            test_event_ids.append(quiz_day_id)
            async with AsyncSessionLocal() as db:
                total = await count_sessions(db, ClassSession.date == date(2026, 11, 6))
                extras = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 6)) & ClassSession.is_extra.is_(True))
            check("15. QUIZ_DAY adds no sessions (5 + 1 surprise-extra only)",
                  total == 6 and extras == 1, f"total={total} extras={extras}")

            # --- 9. Working Saturday materializes the substituted schedule -------
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "WORKING_SATURDAY", "start_date": "2026-11-07", "end_date": "2026-11-07",
                "is_working_day": True, "substitution_schedule_override": "MONDAY"})
            check("16. admin WORKING_SATURDAY 11-07 (Mon schedule) -> 201", r.status_code == 201,
                  f"got {r.status_code} {r.text[:200]}")
            work_sat_id = uuid.UUID(r.json()["id"])
            test_event_ids.append(work_sat_id)
            async with AsyncSessionLocal() as db:
                total = await count_sessions(db, ClassSession.date == date(2026, 11, 7))
                with_entry = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 7)) & ClassSession.timetable_entry_id.is_not(None))
                monday_count = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 2)) & ClassSession.timetable_entry_id.is_not(None))
            check("17. Monday's 5-session schedule materialized on the Saturday",
                  total == 5 and with_entry == 5 and total == monday_count,
                  f"sat_total={total} with_timetable={with_entry} monday_sessions={monday_count}")

            # --- 10. Moving an event reverts the old date and applies the new one
            r = await client.patch(f"/api/v1/events/{extra_event_id}", headers=admin_headers,
                                    json={"start_date": "2026-11-05", "end_date": "2026-11-05"})
            check("18. PATCH moves the extra event 11-04 -> 11-05", r.status_code == 200,
                  f"got {r.status_code} {r.text[:200]}")
            async with AsyncSessionLocal() as db:
                d4 = await count_sessions(db, ClassSession.date == date(2026, 11, 4))
                d4_extra = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 4)) & ClassSession.is_extra.is_(True))
                d5 = await count_sessions(db, ClassSession.date == date(2026, 11, 5))
                d5_extra = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 5)) & ClassSession.is_extra.is_(True))
            check("19. old date restored (6 sessions, no extra), new date has the extra",
                  d4 == 6 and d4_extra == 0 and d5 == 7 and d5_extra == 1,
                  f"11-04={d4}({d4_extra}) 11-05={d5}({d5_extra})")

            # --- 11. Student read contracts reflect the session state ------------
            r = await client.get("/api/v1/calendar?year=2026&month=11", headers=student_headers)
            body = r.json()
            nov02 = next((d for d in body["days"] if d["date"] == "2026-11-02"), None)
            nov03 = next((d for d in body["days"] if d["date"] == "2026-11-03"), None)
            nov07 = next((d for d in body["days"] if d["date"] == "2026-11-07"), None)
            check("20. calendar 11-02 non-working with 0 counted sessions",
                  nov02 is not None and nov02["is_working_day"] is False and nov02["session_count"] == 0,
                  f"{nov02}")
            check("21. calendar 11-03 working, sessions = 5 (cancelled one not counted)",
                  nov03 is not None and nov03["is_working_day"] is True and nov03["session_count"] == 5,
                  f"{nov03}")
            # Track lab correction: 11-07 replays the MONDAY schedule, whose
            # 2-period BCS-551 lab block is ONE occurrence (3 lectures + 1 lab).
            check("22. calendar 11-07 working Saturday with 4 sessions (Monday "
                  "schedule; 2-hour lab counts once)",
                  nov07 is not None and nov07["is_working_day"] is True and nov07["session_count"] == 4,
                  f"{nov07}")

            r = await client.get("/api/v1/attendance/daily/2026-11-02", headers=student_headers)
            daily = r.json()["sessions"]
            # Track lab correction: 11-02 (Monday) has 3 lectures + one 2-hour
            # BCS-551 lab block = 4 occurrences, all cancelled by the closure.
            check("23. daily 11-02: all 4 session occurrences Cancelled "
                  "(distinguishable, not Pending; lab block is one occurrence)",
                  len(daily) == 4 and all(s["is_cancelled"] for s in daily),
                  f"got {len(daily)} sessions")

            r = await client.get("/api/v1/attendance/daily/2026-11-05", headers=student_headers)
            daily = r.json()["sessions"]
            # Track lab correction: 11-05 (Thursday) = 4 lectures + one 2-hour
            # BCS-552 lab block + 1 extra = 6 occurrences.
            check("24. daily 11-05: 5 classes + 1 extra (lab block counts once; "
                  "extra visible in Track pipeline)",
                  len(daily) == 6 and sum(1 for s in daily if s["is_extra"] and s["subject_code"] == "BCS-501") == 1,
                  f"got {len(daily)} sessions")

            r = await client.get("/api/v1/attendance/history?date_from=2026-11-02&date_to=2026-11-03&status=Cancelled",
                                 headers=student_headers)
            hist = r.json()
            check("25. history endpoint clamped to today: future cancelled sessions never leak into it",
                  hist["total_count"] == 0 and hist["summary"]["cancelled"] == 0,
                  f"total={hist['total_count']} cancelled={hist['summary']['cancelled']}")

            # --- 12. Eligibility for unaffected subjects/dates is unchanged ------
            r = await client.get("/api/v1/quiz-eligibility/BCS-501/1", headers=student_headers)
            check("26. BCS-501 Q1 eligibility byte-identical (window untouched by Nov events)",
                  r.status_code == 200 and r.json() == baseline_eligibility,
                  f"{r.json()}")

            # --- 13. Deactivation reversal: events stop affecting the pipeline ---
            for event_id in [closure_id, attended_closure_id, cancelled_event_id,
                             extra_event_id, surprise_id, quiz_day_id, work_sat_id]:
                r = await client.delete(f"/api/v1/events/{event_id}", headers=admin_headers)
                if r.status_code != 200:
                    check(f"deactivate {event_id}", False, r.text[:200])

            async with AsyncSessionLocal() as db:
                d2 = await count_sessions(db, ClassSession.date == date(2026, 11, 2))
                d2_c = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 2)) & ClassSession.is_cancelled.is_(True))
                d3 = await count_sessions(db, ClassSession.date == date(2026, 11, 3))
                d3_c = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 3)) & ClassSession.is_cancelled.is_(True))
                d5 = await count_sessions(db, ClassSession.date == date(2026, 11, 5))
                d5_x = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 5)) & ClassSession.is_extra.is_(True))
                d6 = await count_sessions(db, ClassSession.date == date(2026, 11, 6))
                d6_x = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 6)) & ClassSession.is_extra.is_(True))
                d7 = await count_sessions(db, ClassSession.date == date(2026, 11, 7))
                d7_c = await count_sessions(
                    db, (ClassSession.date == date(2026, 11, 7)) & ClassSession.is_cancelled.is_(True))
                d15 = await count_sessions(
                    db, (ClassSession.date == date(2026, 7, 15)) & ClassSession.is_cancelled.is_(True))
            check("27. closure reversal: 11-02 restored (5 active, 0 cancelled)", d2 == 5 and d2_c == 0, f"{d2}/{d2_c}")
            check("28. CLASS_CANCELLED reversal: 11-03 restored (6 active, 0 cancelled)", d3 == 6 and d3_c == 0,
                  f"{d3}/{d3_c}")
            check("29. extras removed on deactivation (11-05, 11-06)", d5 == 6 and d5_x == 0 and d6 == 5 and d6_x == 0,
                  f"11-05={d5}({d5_x}) 11-06={d6}({d6_x})")
            check("30. working-Saturday projection fully reverted (11-07 back to 0 sessions)",
                  d7 == 0 and d7_c == 0, f"11-07={d7}({d7_c})")
            check("31. fully-attended closure left zero residue", d15 == 0, f"{d15}")

        # --- 14. Rollback-transaction checks (never committed) -------------------
        async with AsyncSessionLocal() as db:
            extra_session = ClassSession(
                subject_id=bcs501["id"], date=date(2026, 11, 12),
                class_type=ClassType.LECTURE, is_extra=True, is_cancelled=False, timetable_entry_id=None)
            db.add(extra_session)
            await db.flush()
            db.add(AttendanceRecord(user_id=student_user.id, class_session_id=extra_session.id,
                                    status=AttendanceStatus.ATTENDED))
            await db.flush()

            # A different extra on the same date: desired = BCS-502/L, so the
            # attended BCS-501 extra is not desired -> must be PRESERVED.
            decoy = AcademicEvent(
                event_type=EventType.EXTRA_LECTURE,
                start_date=date(2026, 11, 12), end_date=date(2026, 11, 12),
                subject_id=bcs502["id"], class_type=ClassType.LECTURE, active=True)
            db.add(decoy)
            await EventSessionSynchronizer(db).sync_event(decoy)
            await db.flush()
            kept = (await db.execute(select(ClassSession).where(ClassSession.id == extra_session.id))).scalars().first()
            check("32. attended extra session survives reconciliation (history protected)",
                  kept is not None and not kept.is_cancelled, f"kept={kept is not None}")

            # Range event: one extra per date in the range.
            rng = AcademicEvent(
                event_type=EventType.EXTRA_TUTORIAL,
                start_date=date(2026, 11, 16), end_date=date(2026, 11, 18),
                subject_id=bcs501["id"], class_type=ClassType.TUTORIAL, active=True)
            db.add(rng)
            await EventSessionSynchronizer(db).sync_event(rng)
            await db.flush()
            n = await count_sessions(
                db, ((ClassSession.date >= date(2026, 11, 16)) & (ClassSession.date <= date(2026, 11, 18)))
                & ClassSession.is_extra.is_(True))
            check("33. 3-day range event materializes exactly 3 extra sessions", n == 3, f"n={n}")

            # Deactivation convergence: second sync after removing the event is a no-op.
            rng.active = False
            await EventSessionSynchronizer(db).sync_event(rng)
            await db.flush()
            n1 = await count_sessions(
                db, ((ClassSession.date >= date(2026, 11, 16)) & (ClassSession.date <= date(2026, 11, 18)))
                & ClassSession.is_extra.is_(True))
            await EventSessionSynchronizer(db).sync_event(rng)
            await db.flush()
            n2 = await count_sessions(
                db, ((ClassSession.date >= date(2026, 11, 16)) & (ClassSession.date <= date(2026, 11, 18)))
                & ClassSession.is_extra.is_(True))
            check("34. deactivated range event removes extras; second sync is a no-op", n1 == n2 == 0,
                  f"n1={n1} n2={n2}")
            await db.rollback()
            print("rollback: transaction discarded — no test rows persisted")
    finally:
        # Hard-delete this script's own event rows. Deactivation already
        # reverted every session effect, so the DB returns to baseline.
        async with AsyncSessionLocal() as db:
            if test_event_ids:
                await db.execute(delete(AcademicEvent).where(AcademicEvent.id.in_(test_event_ids)))
                await db.commit()
                print(f"cleanup: removed {len(test_event_ids)} verification event row(s)")

    # --- 15. Final baseline assertion ------------------------------------------
    async with AsyncSessionLocal() as db:
        events_after = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
        sessions_after = await count_sessions(db, ClassSession.id.is_not(None))
        cancelled_after = await count_sessions(db, ClassSession.is_cancelled.is_(True))
        extra_after = await count_sessions(db, ClassSession.is_extra.is_(True))
        records_after = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
    check("35. database returned to exact baseline (events/sessions/cancelled/extra/records)",
          events_after == events_before and sessions_after == sessions_before
          and cancelled_after == cancelled_before and extra_after == extra_before
          and records_after == records_before,
          f"events {events_before}->{events_after}, sessions {sessions_before}->{sessions_after}, "
          f"cancelled {cancelled_before}->{cancelled_after}, extra {extra_before}->{extra_after}, "
          f"records {records_before}->{records_after}")

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))