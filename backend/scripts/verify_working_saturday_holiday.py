"""
Working Saturday + Unified Holiday verification (Events system improvement).

Verifies the two event-family improvements against the real database (httpx
ASGITransport + real DB + minted JWTs, the established pattern):

WORKING SATURDAY
  * A WORKING_SATURDAY event (single day or date range) flips ONLY the
    Saturdays inside its inclusive range to working days — weekdays inside the
    range keep their normal working state and Sundays stay non-working
    (engine: get_academic_day gives WORKING_SATURDAY Saturday-only semantics;
    the event's own is_working_day field is implied, never consulted).
  * Working Saturday NEVER fabricates attendance-bearing ClassSessions: the
    Saturday timetable is empty, so no scheduled session is materialized.
    Actual classes on the Saturday are recorded with the existing EXTRA_*
    events, which use the canonical synchronizer and flow through Track /
    History / subject attendance exactly like any other extra.
  * Duplicate creation is rejected (409); repeated sync is idempotent;
    deactivation removes only the working-day semantics and never touches
    attended sessions or attendance records.

UNIFIED HOLIDAY
  * The new HOLIDAY closure type (single day or inclusive range) with an
    optional reason/occasion note. Same closure semantics as the legacy
    PUBLIC_HOLIDAY / INSTITUTE_HOLIDAY / FESTIVAL_HOLIDAY family (which stays
    fully supported): the day becomes non-working and scheduled sessions are
    cancelled through the canonical synchronizer.
  * No attendance records are fabricated; existing records are preserved;
    attended sessions are never cancelled; deactivation restores the exact
    session state.
  * HOLIDAY is admin-only (global closure — frozen 6.5 boundary): students
    get 403, same as every other global/closure type. This is NOT an
    arbitrary restriction: day-state events are architecturally GLOBAL —
    AcademicEvent has no owner column, and every consumer (calendar,
    dashboard, quiz-eligibility teaching days, and the synchronizer) resolves
    days from ALL active events against the SHARED ClassSession table. A
    student-created holiday would cancel every student's sessions and distort
    other students' eligibility windows; a student working Saturday would flip
    the shared day-state. Student-scoped day-state events are therefore NOT
    safely representable in this architecture; students record their own
    Saturday reality through the already-student-creatable EXTRA_* events.
  * A NEW HOLIDAY must carry a reason/occasion note (422 without one).
    Enforced at creation only — legacy holiday events without notes stay
    editable.

State changes are this script's own artifacts (events titled
"VerifyWSHoliday ...", the sessions they create, the attendance record it
marks, and cancellation state it applies) and are removed in the finally
block. Cleanup is STRICTLY ownership-scoped: events by their note marker,
sessions/records/cancellations by the EXACT IDs captured when this run's
mutations created or changed them — never a date/type/shape sweep. No frozen
verifier assertion is weakened.

Usage:
    python scripts/verify_working_saturday_holiday.py
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
from app.models.enums import AttendanceStatus, ClassType, UserRole, SessionDesignation
from sqlalchemy import select, func, delete

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


# --- test dates ---------------------------------------------------------------
WS_RANGE_START = date(2026, 8, 1)     # Saturday
WS_RANGE_END = date(2026, 8, 31)      # Monday
WS_SATURDAYS = [date(2026, 8, 1), date(2026, 8, 8), date(2026, 8, 15),
                date(2026, 8, 22), date(2026, 8, 29)]
WS_WEEKDAY = date(2026, 8, 3)         # Monday inside the range
WS_SUNDAY = date(2026, 8, 2)          # Sunday inside the range
WS_EXTRA_DAY = date(2026, 8, 8)       # past Saturday — attendance markable
HOL_PAST = date(2026, 7, 15)          # past Wednesday with existing records
HOL_SINGLE = date(2026, 9, 1)         # future Tuesday
HOL_MULTI = [date(2026, 9, 2), date(2026, 9, 3), date(2026, 9, 4)]
HOL_LEGACY = date(2026, 9, 7)         # future Monday — legacy PUBLIC_HOLIDAY

EVENT_TITLE_PREFIX = "VerifyWSHoliday"


async def count_sessions(db, *conds):
    stmt = select(func.count()).select_from(ClassSession)
    if conds:
        stmt = stmt.where(*conds)
    return (await db.execute(stmt)).scalar()


async def snapshot_cancelled(db, d):
    """{session_id: is_cancelled} for a date — used to prove exact restore."""
    rows = (await db.execute(select(ClassSession).where(ClassSession.date == d))).scalars().all()
    return {s.id: s.is_cancelled for s in rows}


async def cleanup_residue(db) -> None:
    """Startup: remove crashed-run residue of THIS script (note-marker owned)."""
    note_events = (await db.execute(
        select(AcademicEvent).where(AcademicEvent.note.like(f"{EVENT_TITLE_PREFIX}%"))
    )).scalars().all()
    for ev in note_events:
        await db.delete(ev)
    await db.commit()


async def main() -> int:
    async with AsyncSessionLocal() as db:
        section = (await db.execute(select(Section))).scalars().first()
        subject_ids = {s.code: s.id for s in (await db.execute(select(Subject))).scalars().all()}
        await cleanup_residue(db)
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
        designated_before = (await db.execute(select(func.count()).select_from(ClassSession).where(
            ClassSession.designation.isnot(None)))).scalar()

        admin_user = (await db.execute(select(User).where(User.roll_number == "2401220100027"))).scalars().first()
        student_user = (await db.execute(select(User).where(User.roll_number == "9999999999999"))).scalars().first()
        if admin_user is None or student_user is None:
            print("FATAL: seed users missing")
            return 1

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    student_token = create_access_token(str(student_user.id), student_user.roll_number)
    student_headers = {"Authorization": f"Bearer {student_token}"}

    transport = httpx.ASGITransport(app=app)
    my_session_ids: set = set()
    my_record_ids: set = set()
    my_cancelled_ids: set = set()

    # Pre-event snapshots for the dates this verifier touches.
    async with AsyncSessionLocal() as db:
        sat_sessions_before = {d: await count_sessions(db, ClassSession.date == d) for d in WS_SATURDAYS}
        weekday_before = await count_sessions(db, ClassSession.date == WS_WEEKDAY)
        weekday_cancelled_before = {s.id: s.is_cancelled for s in (
            await db.execute(select(ClassSession).where(ClassSession.date == WS_WEEKDAY))).scalars().all()}
        hol_past_cancelled_before = await snapshot_cancelled(db, HOL_PAST)
        hol_past_rows = (await db.execute(select(ClassSession).where(ClassSession.date == HOL_PAST))).scalars().all()
        hol_past_total_sessions = len(hol_past_rows)
        hol_past_records = (await db.execute(
            select(AttendanceRecord).where(AttendanceRecord.class_session_id.in_(
                [s.id for s in hol_past_rows]),
                AttendanceRecord.user_id == admin_user.id))).scalars().all()
        hol_past_attended = sum(1 for r in hol_past_records if r.status == AttendanceStatus.ATTENDED)
        hol_past_missed = sum(1 for r in hol_past_records if r.status == AttendanceStatus.MISSED)

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # --- WORKING SATURDAY -------------------------------------------------
            # 1. Admin creates a Working Saturday RANGE (Aug 1-31).
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "WORKING_SATURDAY", "start_date": WS_RANGE_START.isoformat(),
                "end_date": WS_RANGE_END.isoformat(),
                "note": f"{EVENT_TITLE_PREFIX} — WS range"})
            ok = r.status_code == 201
            if ok:
                ws_id = uuid.UUID(r.json()["id"])
            check("1. admin WORKING_SATURDAY range 08-01..08-31 -> 201", ok, f"got {r.status_code} {r.text[:200]}")

            # 2. Only Saturdays inside the range become working.
            r = await client.get("/api/v1/calendar?year=2026&month=8", headers=admin_headers)
            body = r.json()
            by_date = {d["date"]: d for d in body["days"]}
            sats_ok = all(by_date.get(d.isoformat(), {}).get("is_working_day") is True for d in WS_SATURDAYS)
            sun_ok = by_date.get(WS_SUNDAY.isoformat(), {}).get("is_working_day") is False
            wk_ok = by_date.get(WS_WEEKDAY.isoformat(), {}).get("is_working_day") is True
            check("2. only Saturdays working (5 Saturdays yes, Sunday no, weekday "
                  "still working)", sats_ok and sun_ok and wk_ok,
                  f"sats={[by_date.get(d.isoformat(), {}).get('is_working_day') for d in WS_SATURDAYS]} "
                  f"sun={by_date.get(WS_SUNDAY.isoformat(), {}).get('is_working_day')} "
                  f"weekday={by_date.get(WS_WEEKDAY.isoformat(), {}).get('is_working_day')}")

            # 3. No attendance-bearing ClassSessions fabricated on Saturdays.
            async with AsyncSessionLocal() as db:
                sat_deltas = {d: await count_sessions(db, ClassSession.date == d) - sat_sessions_before[d]
                              for d in WS_SATURDAYS}
            check("3. Working Saturday fabricates zero sessions on every Saturday "
                  "in the range", all(v == 0 for v in sat_deltas.values()), f"{sat_deltas}")

            # 4. Weekdays inside the range are untouched (same rows, same state).
            async with AsyncSessionLocal() as db:
                weekday_after = await count_sessions(db, ClassSession.date == WS_WEEKDAY)
                weekday_cancelled_after = {s.id: s.is_cancelled for s in (
                    await db.execute(select(ClassSession).where(ClassSession.date == WS_WEEKDAY))).scalars().all()}
            check("4. weekday sessions inside the range unchanged (same count, "
                  "none newly cancelled)", weekday_after == weekday_before
                  and weekday_cancelled_after == weekday_cancelled_before,
                  f"before={weekday_before} after={weekday_after}")

            # 5. Duplicate Working Saturday range -> 409.
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "WORKING_SATURDAY", "start_date": WS_RANGE_START.isoformat(),
                "end_date": WS_RANGE_END.isoformat(),
                "note": f"{EVENT_TITLE_PREFIX} — WS dup"})
            check("5. duplicate WORKING_SATURDAY range -> 409", r.status_code == 409,
                  f"got {r.status_code} {r.text[:200]}")

            # 6. Extra Lecture on the working Saturday -> exactly one occurrence.
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "EXTRA_LECTURE", "start_date": WS_EXTRA_DAY.isoformat(),
                "end_date": WS_EXTRA_DAY.isoformat(), "subject_id": str(subject_ids["BCS-501"]),
                "class_type": "L", "note": f"{EVENT_TITLE_PREFIX} — WS extra"})
            ok = r.status_code == 201
            if ok:
                extra_event_id = uuid.UUID(r.json()["id"])
            async with AsyncSessionLocal() as db:
                extras = (await db.execute(select(ClassSession).where(
                    ClassSession.date == WS_EXTRA_DAY, ClassSession.subject_id == subject_ids["BCS-501"],
                    ClassSession.is_extra.is_(True)))).scalars().all()
                extra_session = extras[0] if len(extras) == 1 else None
                if extra_session is not None:
                    my_session_ids.add(extra_session.id)
            check("6. EXTRA_LECTURE on working Saturday -> exactly one extra "
                  "occurrence, not cancelled", ok and extra_session is not None
                  and not extra_session.is_cancelled,
                  f"got {r.status_code} extras={len(extras) if extras is not None else 'n/a'}")

            # 7. Track daily view shows the extra on the Saturday.
            r = await client.get(f"/api/v1/attendance/daily/{WS_EXTRA_DAY.isoformat()}", headers=admin_headers)
            occ = [s for s in r.json()["sessions"] if s["subject_code"] == "BCS-501"]
            check("7. Track 08-08 shows the BCS-501 extra occurrence",
                  len(occ) == 1 and occ[0]["is_extra"] and not occ[0]["is_cancelled"],
                  f"got {[(s['subject_code'], s['is_extra'], s['is_cancelled']) for s in occ]}")

            # 8. Attendance on the extra flows through the canonical pipeline.
            # The extra session already sits in the lecture bucket as Pending,
            # so marking Present moves pending -> attended (+1 attended, total
            # unchanged) and creates exactly one canonical AttendanceRecord.
            r = await client.get("/api/v1/attendance/summary/BCS-501", headers=admin_headers)
            lec_before = r.json()["lecture"]
            r = await client.post("/api/v1/attendance", headers=admin_headers, json={
                "class_session_id": str(extra_session.id), "status": "Attended"})
            ok = r.status_code == 200
            if ok:
                my_record_ids.add(uuid.UUID(r.json()["id"]))
            r = await client.get("/api/v1/attendance/summary/BCS-501", headers=admin_headers)
            lec_after = r.json()["lecture"]
            check("8. marking the Saturday extra Present -> one record; BCS-501 "
                  "lecture +1 attended (extra was already pending in the bucket)",
                  ok and lec_after["total"] == lec_before["total"]
                  and lec_after["attended"] == lec_before["attended"] + 1,
                  f"got {r.status_code} total {lec_before['total']}->{lec_after['total']} "
                  f"attended {lec_before['attended']}->{lec_after['attended']}")

            # 9. History shows the extra.
            r = await client.get("/api/v1/attendance/history?subject_code=BCS-501"
                                 f"&date_from={WS_EXTRA_DAY.isoformat()}&date_to={WS_EXTRA_DAY.isoformat()}",
                                 headers=admin_headers)
            items = r.json().get("items", [])
            check("9. History shows the Saturday extra as Attended",
                  len(items) == 1 and items[0]["is_extra"] and items[0]["status"] == "Attended",
                  f"got {[(i['subject_code'], i['is_extra'], i['status']) for i in items]}")

            # 10. Idempotency: PATCH the Working Saturday with unchanged values.
            r = await client.patch(f"/api/v1/events/{ws_id}", headers=admin_headers,
                                   json={"active": True, "start_date": WS_RANGE_START.isoformat(),
                                         "end_date": WS_RANGE_END.isoformat()})
            async with AsyncSessionLocal() as db:
                extras_after = (await db.execute(select(ClassSession).where(
                    ClassSession.date == WS_EXTRA_DAY, ClassSession.subject_id == subject_ids["BCS-501"],
                    ClassSession.is_extra.is_(True)))).scalars().all()
                extra_sessions = len(extras_after)
                records_after = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
            # records_before + 1: the check-8 attendance record is this run's
            # own artifact and legitimately exists at this point.
            check("10. idempotent re-sync: no duplicate session, no extra record",
                  r.status_code == 200 and extra_sessions == 1
                  and records_after == records_before + 1,
                  f"PATCH {r.status_code} extras={extra_sessions} records {records_before}->{records_after}")

            # 11. Deactivating the Working Saturday removes only day-state: the
            #     attended extra (owned by the EXTRA event) and its record survive.
            r = await client.delete(f"/api/v1/events/{ws_id}", headers=admin_headers)
            ok = r.status_code == 200
            r = await client.get("/api/v1/calendar?year=2026&month=8", headers=admin_headers)
            day = next(d for d in r.json()["days"] if d["date"] == WS_EXTRA_DAY.isoformat())
            async with AsyncSessionLocal() as db:
                records_on_extra = (await db.execute(select(func.count()).select_from(AttendanceRecord).where(
                    AttendanceRecord.class_session_id == extra_session.id))).scalar()
            check("11. WS deactivation: 08-08 non-working again, attended extra + "
                  "record preserved", ok and day["is_working_day"] is False
                  and extra_sessions == 1 and records_on_extra == 1,
                  f"delete {r.status_code} working={day['is_working_day']} "
                  f"records_on_extra={records_on_extra}")

            # 12. Student authorization: global events stay admin-only (frozen 6.5).
            r = await client.post("/api/v1/events", headers=student_headers, json={
                "event_type": "WORKING_SATURDAY", "start_date": WS_EXTRA_DAY.isoformat(),
                "end_date": WS_EXTRA_DAY.isoformat()})
            check("12. student WORKING_SATURDAY -> 403 (global, admin-only)", r.status_code == 403,
                  f"got {r.status_code} {r.text[:200]}")

            # --- UNIFIED HOLIDAY --------------------------------------------------
            # 13. Single-day Holiday with a reason note.
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "HOLIDAY", "start_date": HOL_SINGLE.isoformat(),
                "end_date": HOL_SINGLE.isoformat(),
                "note": f"{EVENT_TITLE_PREFIX} — Independence Day"})
            ok = r.status_code == 201
            if ok:
                hol_single_id = uuid.UUID(r.json()["id"])
            r = await client.get("/api/v1/events", headers=admin_headers)
            hol = next((e for e in r.json() if e["id"] == str(hol_single_id)), None)
            check("13. admin HOLIDAY single day -> 201; note persisted",
                  ok and hol is not None and hol["note"] == f"{EVENT_TITLE_PREFIX} — Independence Day",
                  f"got {r.status_code}")

            # 13b. A NEW Holiday without a reason/occasion is rejected (422).
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "HOLIDAY", "start_date": HOL_SINGLE.isoformat(),
                "end_date": HOL_SINGLE.isoformat(), "note": None})
            check("13b. HOLIDAY without reason -> 422", r.status_code == 422,
                  f"got {r.status_code} {r.text[:200]}")

            # 14. Calendar day-state + no sessions counted on the holiday.
            r = await client.get("/api/v1/calendar?year=2026&month=9", headers=admin_headers)
            day = next(d for d in r.json()["days"] if d["date"] == HOL_SINGLE.isoformat())
            check("14. calendar 09-01 non-working, reason 'Holiday', 0 counted sessions",
                  day["is_working_day"] is False and day["non_working_reason"] == "Holiday"
                  and day["session_count"] == 0, f"{day}")

            # 15. Track: scheduled sessions cancelled (canonical closure), none deleted.
            async with AsyncSessionLocal() as db:
                sessions_hol = (await db.execute(select(ClassSession).where(
                    ClassSession.date == HOL_SINGLE))).scalars().all()
                for s in sessions_hol:
                    if s.is_cancelled:
                        my_cancelled_ids.add(s.id)
            r = await client.get(f"/api/v1/attendance/daily/{HOL_SINGLE.isoformat()}", headers=admin_headers)
            occ = r.json()["sessions"]
            # History is documented as clamped to the current date, so a FUTURE
            # holiday date legitimately has no history rows yet (they appear
            # once the date passes) — the assertion is on the track/DB state.
            r = await client.get("/api/v1/attendance/history?date_from="
                                 f"{HOL_SINGLE.isoformat()}&date_to={HOL_SINGLE.isoformat()}",
                                 headers=admin_headers)
            history_items = r.json().get("items", [])
            check("15. Track 09-01: all occurrences Cancelled; rows preserved; "
                  "future-date history empty (documented today-clamp)",
                  len(sessions_hol) > 0 and len(occ) == len(sessions_hol)
                  and all(s["is_cancelled"] for s in occ)
                  and len(history_items) == 0,
                  f"rows={len(sessions_hol)} track={len(occ)} history={len(history_items)}")

            # 16. Multi-day Holiday range (inclusive) — every day non-working.
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "HOLIDAY", "start_date": HOL_MULTI[0].isoformat(),
                "end_date": HOL_MULTI[-1].isoformat(),
                "note": f"{EVENT_TITLE_PREFIX} — Diwali break"})
            ok = r.status_code == 201
            if ok:
                hol_multi_id = uuid.UUID(r.json()["id"])
            r = await client.get("/api/v1/calendar?year=2026&month=9", headers=admin_headers)
            by_date = {d["date"]: d for d in r.json()["days"]}
            multi_ok = all(by_date.get(d.isoformat(), {}).get("is_working_day") is False for d in HOL_MULTI)
            check("16. HOLIDAY range 09-02..09-04 -> 201; every day non-working",
                  ok and multi_ok, f"got {r.status_code}")

            # 17. Holiday on a PAST date with existing records: records preserved,
            #     attended sessions never cancelled, unattended cancelled.
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "HOLIDAY", "start_date": HOL_PAST.isoformat(),
                "end_date": HOL_PAST.isoformat(),
                "note": f"{EVENT_TITLE_PREFIX} — past holiday"})
            ok = r.status_code == 201
            if ok:
                hol_past_id = uuid.UUID(r.json()["id"])
            async with AsyncSessionLocal() as db:
                past_sessions = (await db.execute(select(ClassSession).where(
                    ClassSession.date == HOL_PAST))).scalars().all()
                recorded_ids = {s.id for s in past_sessions if s.id in (
                    (await db.execute(select(AttendanceRecord.class_session_id).where(
                        AttendanceRecord.class_session_id.in_([s.id for s in past_sessions])))).scalars().all())}
                recorded_kept = all(not s.is_cancelled for s in past_sessions if s.id in recorded_ids)
                unattended_cancelled = all(s.is_cancelled for s in past_sessions if s.id not in recorded_ids)
                for s in past_sessions:
                    if s.is_cancelled:
                        my_cancelled_ids.add(s.id)
                records_past = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
            # records_before + 1: the check-8 attendance record is this run's own artifact.
            check("17. HOLIDAY on past 07-15: records unchanged, recorded sessions "
                  "never cancelled, unattended cancelled",
                  ok and recorded_kept and unattended_cancelled
                  and records_past == records_before + 1,
                  f"got {r.status_code} recorded_kept={recorded_kept} "
                  f"unattended_cancelled={unattended_cancelled} records {records_before}->{records_past}")

            # 18. History on the PAST holiday date: recorded sessions keep their
            #     exact status (Attended/Missed — never converted to absent), the
            #     unrecorded ones show Cancelled, nothing fabricated.
            hist_att = await client.get("/api/v1/attendance/history?date_from="
                                        f"{HOL_PAST.isoformat()}&date_to={HOL_PAST.isoformat()}"
                                        "&status=Attended", headers=admin_headers)
            hist_miss = await client.get("/api/v1/attendance/history?date_from="
                                         f"{HOL_PAST.isoformat()}&date_to={HOL_PAST.isoformat()}"
                                         "&status=Missed", headers=admin_headers)
            hist_canc = await client.get("/api/v1/attendance/history?date_from="
                                         f"{HOL_PAST.isoformat()}&date_to={HOL_PAST.isoformat()}"
                                         "&status=Cancelled", headers=admin_headers)
            attended_now = hist_att.json().get("total_count", 0)
            missed_now = hist_miss.json().get("total_count", 0)
            cancelled_now = hist_canc.json().get("total_count", 0)
            expected_cancelled = hol_past_total_sessions - hol_past_attended - hol_past_missed
            check("18. history on past holiday: attended/missed intact, "
                  "unrecorded sessions Cancelled",
                  attended_now == hol_past_attended and missed_now == hol_past_missed
                  and cancelled_now == expected_cancelled,
                  f"attended {hol_past_attended}->{attended_now} "
                  f"missed {hol_past_missed}->{missed_now} "
                  f"cancelled expected {expected_cancelled} got {cancelled_now}")

            # 19. Deactivation restores the exact canonical session state.
            r = await client.delete(f"/api/v1/events/{hol_single_id}", headers=admin_headers)
            ok1 = r.status_code == 200
            r = await client.delete(f"/api/v1/events/{hol_multi_id}", headers=admin_headers)
            ok2 = r.status_code == 200
            r = await client.delete(f"/api/v1/events/{hol_past_id}", headers=admin_headers)
            ok3 = r.status_code == 200
            async with AsyncSessionLocal() as db:
                single_state = {s.id: s.is_cancelled for s in (
                    await db.execute(select(ClassSession).where(ClassSession.date == HOL_SINGLE))).scalars().all()}
                multi_state = {s.id: s.is_cancelled for s in (
                    await db.execute(select(ClassSession).where(ClassSession.date.in_(HOL_MULTI)))).scalars().all()}
                past_state = await snapshot_cancelled(db, HOL_PAST)
            check("19. deactivating holidays restores sessions (none cancelled "
                  "on 09-01/09-02..04; 07-15 exactly as before)",
                  ok1 and ok2 and ok3 and all(not v for v in single_state.values())
                  and all(not v for v in multi_state.values())
                  and past_state == hol_past_cancelled_before,
                  f"single cancelled={sum(1 for v in single_state.values() if v)} "
                  f"multi cancelled={sum(1 for v in multi_state.values() if v)}")

            # 20. Legacy holiday family stays fully supported (backward compat).
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "PUBLIC_HOLIDAY", "start_date": HOL_LEGACY.isoformat(),
                "end_date": HOL_LEGACY.isoformat(),
                "note": f"{EVENT_TITLE_PREFIX} — legacy"})
            ok = r.status_code == 201
            if ok:
                legacy_id = uuid.UUID(r.json()["id"])
            r = await client.get("/api/v1/calendar?year=2026&month=9", headers=admin_headers)
            day = next(d for d in r.json()["days"] if d["date"] == HOL_LEGACY.isoformat())
            r = await client.delete(f"/api/v1/events/{legacy_id}", headers=admin_headers)
            check("20. legacy PUBLIC_HOLIDAY still works (201, non-working day)",
                  ok and day["is_working_day"] is False and r.status_code == 200,
                  f"got {r.status_code} working={day['is_working_day']}")

            # 21. Student cannot create a Holiday (global closure).
            r = await client.post("/api/v1/events", headers=student_headers, json={
                "event_type": "HOLIDAY", "start_date": HOL_SINGLE.isoformat(),
                "end_date": HOL_SINGLE.isoformat()})
            check("21. student HOLIDAY -> 403 (global closure, admin-only)",
                  r.status_code == 403, f"got {r.status_code} {r.text[:200]}")

            # 22. Contradictory Working Saturday override is rejected.
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "WORKING_SATURDAY", "start_date": WS_EXTRA_DAY.isoformat(),
                "end_date": WS_EXTRA_DAY.isoformat(), "is_working_day": False,
                "note": f"{EVENT_TITLE_PREFIX} — contradictory"})
            check("22. WORKING_SATURDAY with is_working_day=false -> 422",
                  r.status_code == 422, f"got {r.status_code} {r.text[:200]}")

    finally:
        # --- Cleanup: exact restoration (ownership-scoped) ----------------------
        async with AsyncSessionLocal() as db:
            events = (await db.execute(
                select(AcademicEvent).where(AcademicEvent.note.like(f"{EVENT_TITLE_PREFIX}%"))
            )).scalars().all()
            for ev in events:
                await db.delete(ev)

            if my_record_ids:
                await db.execute(delete(AttendanceRecord).where(
                    AttendanceRecord.id.in_(my_record_ids)))
            if my_session_ids:
                await db.execute(delete(AttendanceRecord).where(
                    AttendanceRecord.class_session_id.in_(my_session_ids)))
                await db.execute(delete(ClassSession).where(ClassSession.id.in_(my_session_ids)))
            if my_cancelled_ids:
                await db.execute(
                    ClassSession.__table__.update()
                    .where(ClassSession.id.in_(my_cancelled_ids),
                           ClassSession.is_cancelled.is_(True))
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
            designated_after = (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.designation.isnot(None)))).scalar()

        check("23. exact baseline restoration (events/sessions/cancelled/extra/"
              "records/enrollments/subjects/quizzes/users/admins/designation)",
              events_before == events_after and sessions_before == sessions_after
              and cancelled_before == cancelled_after and extra_before == extra_after
              and records_before == records_after and enrollments_before == enrollments_after
              and subjects_before == subjects_after and quizzes_before == quizzes_after
              and users_before == users_after and admins_before == admins_after
              and designated_before == designated_after,
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
    raise SystemExit(asyncio.run(main()))
