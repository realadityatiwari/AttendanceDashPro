"""
Focused History page filter verification (post-Phase 9.2.1).

Verifies the History read model and every filter against the real database
(httpx ASGITransport + real DB + minted JWTs, the established pattern) using a
temp student enrolled in BCS-501 (theory: lectures + tutorials) and BCS-551
(lab: 2-period Monday blocks). Expected counts are derived from the canonical
class_sessions collapse math (a lab block is ONE history occurrence) and pinned
to absolute values so timetable regressions fail loudly.

Checks:
  1.  Unfiltered history: response shape, filtered-set total_count, summary.
  2.  Subject filter — theory subject (BCS-501).
  3.  Subject filter — practical subject (BCS-551); a two-hour lab block is ONE
      history occurrence ("01:00 PM – 03:00 PM"), not two per-period rows.
  4.  From date (inclusive).
  5.  To date (inclusive).
  6.  From + To (inclusive range).
  7.  Search by subject code (case-insensitive).
  8.  Search by subject name (case-insensitive).
  9.  Search by class type (lecture / tutorial / practical).
 10.  State Present — marking the lab block creates exactly ONE canonical
      AttendanceRecord; status=Attended returns exactly that occurrence.
 11.  State Absent — marking a lecture Missed; status=Missed returns it.
 12.  State Pending — remaining unrecorded occurrences.
 13.  State Cancelled — LAB_CANCELLED event; status=Cancelled returns the block;
      marking the cancelled block is rejected (409).
 14.  Combined filters.
 15.  Zero-result filter — same response shape, total_count 0.
 16.  Pagination / Load More — fixed page size, disjoint pages, offset beyond
      the end keeps total_count, full accumulation has no duplicate ids.
 17.  Clearing filters — unfiltered total_count unchanged (22) with the
      corrected end-state summary (attended=1, missed=1, pending=19,
      cancelled=1, pct=50.0).
 18.  Response-shape consistency across every filtered request.
 19.  Database restored to the exact baseline after cleanup.

State changes are this script's own artifacts (a temp user, 2 attendance
records, 1 LAB_CANCELLED event, session cancellation state) and are removed in
the finally block. No old assertion is weakened.

Usage:
    python scripts/verify_history_filters.py
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


# --- test dates (all past; semester 07-15 -> today 08-16) -------------------
D_LAB = date(2026, 7, 20)    # Monday  — BCS-551 2-period lab block
D_CANCEL = date(2026, 7, 27)  # Monday  — BCS-551 lab block -> LAB_CANCELLED
D_LEC = date(2026, 7, 16)    # Thursday — BCS-501 lecture (11:00 AM)
WINDOW_START = date(2026, 7, 15)
WINDOW_END = date(2026, 8, 31)

CANONICAL_KEYS = {"semester_start", "semester_end", "range_start", "range_end",
                  "items", "total_count", "summary"}
SUMMARY_KEYS = {"total", "attended", "missed", "pending", "cancelled", "pct"}


async def occurrence_count(db, subject_ids: list = None, date_lo: date = None,
                           date_hi: date = None, class_type: ClassType = None) -> int:
    """Canonical history occurrence count: class-session rows for the given
    subjects with PRACTICAL rows collapsed to distinct dates (one lab block ==
    one occurrence)."""
    conds = []
    if subject_ids:
        conds.append(ClassSession.subject_id.in_(subject_ids))
    if date_lo is not None:
        conds.append(ClassSession.date >= date_lo)
    if date_hi is not None:
        conds.append(ClassSession.date <= date_hi)
    if class_type is not None:
        conds.append(ClassSession.class_type == class_type)
    rows = (await db.execute(select(func.count()).select_from(ClassSession).where(*conds))).scalar()
    p_conds = conds + [ClassSession.class_type == ClassType.PRACTICAL]
    p_rows = (await db.execute(select(func.count()).select_from(ClassSession).where(*p_conds))).scalar()
    p_dates = (await db.execute(select(func.count(func.distinct(ClassSession.date)))
                                .select_from(ClassSession).where(*p_conds))).scalar()
    return rows - p_rows + p_dates


async def main() -> int:
    async with AsyncSessionLocal() as db:
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

        section = (await db.execute(select(Section))).scalars().first()
        subject_ids = {s.code: s.id for s in (await db.execute(select(Subject))).scalars().all()}

        temp_user = User(
            roll_number="HIST_TMP_FLT",
            name="History Filter Temp",
            role=UserRole.STUDENT,
            section_id=section.id if section else None,
        )
        db.add(temp_user)
        await db.flush()
        db.add(StudentEnrollment(user_id=temp_user.id, subject_id=subject_ids["BCS-501"]))
        db.add(StudentEnrollment(user_id=temp_user.id, subject_id=subject_ids["BCS-551"]))
        await db.commit()
        temp_user_id = temp_user.id

    temp_token = create_access_token(str(temp_user_id), "HIST_TMP_FLT")
    temp_headers = {"Authorization": f"Bearer {temp_token}"}

    test_event_ids: list[uuid.UUID] = []
    test_record_ids: list[uuid.UUID] = []
    shapes_ok = True

    try:
        async with AsyncSessionLocal() as db:
            from app.repositories.user_repo import UserRepository
            from sqlalchemy.orm import selectinload
            fresh_user = (await db.execute(
                select(User).options(selectinload(User.section)).where(User.id == temp_user_id)
            )).scalar_one()
            ctx = await UserRepository(db).get_academic_context(fresh_user)
            sem_start = ctx.get("semester_start")
            sem_end = ctx.get("semester_end")
        today = institution_today()
        range_lo = sem_start if sem_start is not None else WINDOW_START
        range_hi = min(today, sem_end if sem_end is not None else WINDOW_END)
        enrolled_ids = [subject_ids["BCS-501"], subject_ids["BCS-551"]]
        async with AsyncSessionLocal() as db:
            exp_total = await occurrence_count(db, subject_ids=enrolled_ids,
                                               date_lo=range_lo, date_hi=range_hi)
            exp_b501 = await occurrence_count(db, subject_ids=[subject_ids["BCS-501"]],
                                              date_lo=range_lo, date_hi=range_hi)
            exp_b551 = await occurrence_count(db, subject_ids=[subject_ids["BCS-551"]],
                                              date_lo=range_lo, date_hi=range_hi)
            exp_lec = await occurrence_count(db, subject_ids=[subject_ids["BCS-501"]],
                                             date_lo=range_lo, date_hi=range_hi,
                                             class_type=ClassType.LECTURE)
            exp_tut = await occurrence_count(db, subject_ids=[subject_ids["BCS-501"]],
                                             date_lo=range_lo, date_hi=range_hi,
                                             class_type=ClassType.TUTORIAL)
            exp_from = await occurrence_count(db, subject_ids=enrolled_ids,
                                              date_lo=date(2026, 8, 1), date_hi=range_hi)
            exp_to = await occurrence_count(db, subject_ids=enrolled_ids,
                                            date_lo=range_lo, date_hi=date(2026, 7, 25))
            exp_both = await occurrence_count(db, subject_ids=enrolled_ids,
                                              date_lo=D_LAB, date_hi=D_LAB)

        def check_shape(payload) -> bool:
            nonlocal shapes_ok
            ok = set(payload.keys()) == CANONICAL_KEYS and set(payload.get("summary", {}).keys()) == SUMMARY_KEYS
            shapes_ok = shapes_ok and ok
            return ok

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # --- 1. Unfiltered: shape, total_count, summary -----------------------
            r = await client.get("/api/v1/attendance/history", headers=temp_headers)
            h = r.json()
            check("1. unfiltered history: 200, canonical shape, total_count == "
                  f"occurrence count ({exp_total}), pristine summary",
                  r.status_code == 200 and check_shape(h)
                  and h["total_count"] == exp_total == 22
                  and h["summary"] == {"total": 22, "attended": 0, "missed": 0,
                                       "pending": 22, "cancelled": 0, "pct": None},
                  f"total={h['total_count']} exp={exp_total} summary={h['summary']}")

            # --- 2. Subject filter — theory ---------------------------------------
            r = await client.get("/api/v1/attendance/history?subject_code=BCS-501", headers=temp_headers)
            h = r.json()
            check("2. subject filter BCS-501: only BCS-501, total_count == "
                  f"{exp_b501} (18), shape consistent",
                  r.status_code == 200 and check_shape(h) and h["total_count"] == exp_b501 == 18
                  and all(i["subject_code"] == "BCS-501" for i in h["items"]),
                  f"total={h['total_count']} exp={exp_b501}")

            # --- 3. Subject filter — practical; 2-hour block is ONE occurrence ----
            r = await client.get("/api/v1/attendance/history?subject_code=BCS-551", headers=temp_headers)
            h = r.json()
            lab_day = [i for i in h["items"] if i["date"] == D_LAB.isoformat()]
            check(f"3. subject filter BCS-551: total_count == {exp_b551} (4 blocks, "
                  "not 8 rows); the 07-20 two-hour lab is ONE occurrence "
                  "(01:00 PM – 03:00 PM, PRACTICAL)",
                  r.status_code == 200 and check_shape(h) and h["total_count"] == exp_b551 == 4
                  and all(i["subject_code"] == "BCS-551" for i in h["items"])
                  and len(lab_day) == 1 and lab_day[0]["start_time"] == "01:00 PM"
                  and lab_day[0]["end_time"] == "03:00 PM" and lab_day[0]["class_type"] == "P",
                  f"total={h['total_count']} exp={exp_b551} lab_day={[(i['date'], i['start_time'], i['end_time']) for i in lab_day]}")

            # --- 4. From date (inclusive) -----------------------------------------
            r = await client.get("/api/v1/attendance/history?date_from=2026-08-01", headers=temp_headers)
            h = r.json()
            check("4. date_from=2026-08-01: only occurrences >= 08-01, "
                  f"total_count == {exp_from} (10)",
                  r.status_code == 200 and check_shape(h) and h["total_count"] == exp_from == 10
                  and all(i["date"] >= "2026-08-01" for i in h["items"]),
                  f"total={h['total_count']} exp={exp_from}")

            # --- 5. To date (inclusive) -------------------------------------------
            r = await client.get("/api/v1/attendance/history?date_to=2026-07-25", headers=temp_headers)
            h = r.json()
            check("5. date_to=2026-07-25: only occurrences <= 07-25, "
                  f"total_count == {exp_to} (7)",
                  r.status_code == 200 and check_shape(h) and h["total_count"] == exp_to == 7
                  and all(i["date"] <= "2026-07-25" for i in h["items"]),
                  f"total={h['total_count']} exp={exp_to}")

            # --- 6. From + To (inclusive range) -----------------------------------
            r = await client.get("/api/v1/attendance/history?date_from=2026-07-20&date_to=2026-07-20",
                                 headers=temp_headers)
            h = r.json()
            check("6. date_from=date_to=2026-07-20: exactly the BCS-551 lab "
                  f"occurrence (total_count == {exp_both} == 1)",
                  r.status_code == 200 and check_shape(h) and h["total_count"] == exp_both == 1
                  and h["items"][0]["date"] == D_LAB.isoformat()
                  and h["items"][0]["subject_code"] == "BCS-551",
                  f"total={h['total_count']} exp={exp_both} items={[(i['date'], i['subject_code']) for i in h['items']]}")

            # --- 7. Search — subject code (case-insensitive) ----------------------
            r = await client.get("/api/v1/attendance/history?search=551", headers=temp_headers)
            h = r.json()
            r2 = await client.get("/api/v1/attendance/history?search=BCS-551", headers=temp_headers)
            h2 = r2.json()
            check("7. search by code ('551' / 'BCS-551'): only BCS-551, "
                  f"total_count == {exp_b551} (4)",
                  r.status_code == 200 and r2.status_code == 200 and check_shape(h)
                  and h["total_count"] == h2["total_count"] == exp_b551 == 4
                  and all(i["subject_code"] == "BCS-551" for i in h["items"]),
                  f"total={h['total_count']}/{h2['total_count']} exp={exp_b551}")

            # --- 8. Search — subject name (case-insensitive) ----------------------
            r = await client.get("/api/v1/attendance/history?search=lab", headers=temp_headers)
            h = r.json()
            r2 = await client.get("/api/v1/attendance/history?search=LAB", headers=temp_headers)
            h2 = r2.json()
            check("8. search by name ('lab' / 'LAB'): all BCS-551 "
                  "('Database Management System Lab'), total_count == 4",
                  r.status_code == 200 and r2.status_code == 200 and check_shape(h)
                  and h["total_count"] == h2["total_count"] == 4
                  and all(i["subject_code"] == "BCS-551" for i in h["items"]),
                  f"total={h['total_count']}/{h2['total_count']}")

            # --- 9. Search — class type -------------------------------------------
            r = await client.get("/api/v1/attendance/history?search=practical", headers=temp_headers)
            h_p = r.json()
            r = await client.get("/api/v1/attendance/history?search=lecture", headers=temp_headers)
            h_l = r.json()
            r = await client.get("/api/v1/attendance/history?search=tutorial", headers=temp_headers)
            h_t = r.json()
            check(f"9. search by type: practical -> only P ({exp_b551} blocks), "
                  f"lecture -> only L ({exp_lec}), tutorial -> only T ({exp_tut})",
                  r.status_code == 200 and check_shape(h_p) and check_shape(h_l) and check_shape(h_t)
                  and h_p["total_count"] == exp_b551 == 4
                  and all(i["class_type"] == "P" for i in h_p["items"])
                  and h_l["total_count"] == exp_lec == 14
                  and all(i["class_type"] == "L" for i in h_l["items"])
                  and h_t["total_count"] == exp_tut == 4
                  and all(i["class_type"] == "T" for i in h_t["items"]),
                  f"p={h_p['total_count']} l={h_l['total_count']} t={h_t['total_count']} "
                  f"exp p={exp_b551} l={exp_lec} t={exp_tut}")

            # --- 10. State Present: one record, status=Attended -------------------
            r = await client.get("/api/v1/attendance/history?subject_code=BCS-551&date_from=2026-07-20&date_to=2026-07-20",
                                 headers=temp_headers)
            occ_id = r.json()["items"][0]["id"]
            r = await client.post("/api/v1/attendance", headers=temp_headers, json={
                "class_session_id": occ_id, "status": "Attended"})
            if r.status_code == 200:
                test_record_ids.append(uuid.UUID(r.json()["id"]))
            async with AsyncSessionLocal() as db:
                members = (await db.execute(select(ClassSession).where(
                    ClassSession.subject_id == subject_ids["BCS-551"],
                    ClassSession.date == D_LAB))).scalars().all()
                recs = (await db.execute(select(AttendanceRecord).where(
                    AttendanceRecord.user_id == temp_user_id,
                    AttendanceRecord.class_session_id.in_([s.id for s in members])))).scalars().all()
            r = await client.get("/api/v1/attendance/history?status=Attended", headers=temp_headers)
            h = r.json()
            check("10. marking the lab block Present creates EXACTLY ONE canonical "
                  "record; status=Attended returns exactly that occurrence",
                  r.status_code == 200 and len(recs) == 1 and recs[0].status == AttendanceStatus.ATTENDED
                  and h["total_count"] == 1 and h["items"][0]["subject_code"] == "BCS-551"
                  and h["items"][0]["date"] == D_LAB.isoformat(),
                  f"mark={r.status_code} records={len(recs)} total={h['total_count']}")

            # --- 11. State Absent --------------------------------------------------
            r = await client.get("/api/v1/attendance/history?subject_code=BCS-501&date_from=2026-07-16&date_to=2026-07-16",
                                 headers=temp_headers)
            lec_id = r.json()["items"][0]["id"]
            r = await client.post("/api/v1/attendance", headers=temp_headers, json={
                "class_session_id": lec_id, "status": "Missed"})
            if r.status_code == 200:
                test_record_ids.append(uuid.UUID(r.json()["id"]))
            r = await client.get("/api/v1/attendance/history?status=Missed", headers=temp_headers)
            h = r.json()
            check("11. marking the 07-16 BCS-501 lecture Missed; status=Missed "
                  "returns exactly that occurrence",
                  r.status_code == 200 and h["total_count"] == 1
                  and h["items"][0]["subject_code"] == "BCS-501"
                  and h["items"][0]["date"] == D_LEC.isoformat(),
                  f"mark={r.status_code} total={h['total_count']}")

            # --- 12. State Pending -------------------------------------------------
            r = await client.get("/api/v1/attendance/history?status=Pending", headers=temp_headers)
            h = r.json()
            check("12. status=Pending: all unrecorded non-cancelled occurrences "
                  "(22 - 1 attended - 1 missed = 20; the cancellation happens next)",
                  r.status_code == 200 and h["total_count"] == 20
                  and all(i["status"] == "Pending" and not i["is_cancelled"] for i in h["items"]),
                  f"total={h['total_count']}")

            # --- 13. State Cancelled (LAB_CANCELLED event) -------------------------
            r = await client.post("/api/v1/events", headers=temp_headers, json={
                "event_type": "LAB_CANCELLED", "start_date": D_CANCEL.isoformat(),
                "end_date": D_CANCEL.isoformat(),
                "subject_id": str(subject_ids["BCS-551"]), "class_type": "P"})
            cancel_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None
            if cancel_id:
                test_event_ids.append(cancel_id)
            r = await client.get("/api/v1/attendance/history?status=Cancelled", headers=temp_headers)
            h = r.json()
            r_daily = await client.get(f"/api/v1/attendance/daily/{D_CANCEL.isoformat()}", headers=temp_headers)
            cancelled_block = [s for s in r_daily.json()["sessions"]
                               if s["subject_code"] == "BCS-551" and s["is_cancelled"]]
            mark_rejected = None
            if cancelled_block:
                mark_rejected = await client.post("/api/v1/attendance", headers=temp_headers, json={
                    "class_session_id": cancelled_block[0]["id"], "status": "Attended"})
            check("13. LAB_CANCELLED on 07-27: status=Cancelled returns the block "
                  "as one cancelled occurrence; marking it is rejected (409)",
                  r.status_code == 200 and h["total_count"] == 1
                  and h["items"][0]["is_cancelled"] and h["items"][0]["date"] == D_CANCEL.isoformat()
                  and mark_rejected is not None and mark_rejected.status_code == 409,
                  f"event={r.status_code} total={h['total_count']} "
                  f"mark={mark_rejected.status_code if mark_rejected else None}")

            # --- 14. Combined filters ----------------------------------------------
            r = await client.get(
                "/api/v1/attendance/history?subject_code=BCS-501&status=Missed"
                "&date_from=2026-07-15&date_to=2026-07-31&search=501", headers=temp_headers)
            h = r.json()
            check("14. combined subject+state+dates+search: exactly the 07-16 "
                  "missed BCS-501 lecture",
                  r.status_code == 200 and h["total_count"] == 1
                  and h["items"][0]["subject_code"] == "BCS-501"
                  and h["items"][0]["status"] == "Missed",
                  f"total={h['total_count']} items={[(i['subject_code'], i['date'], i['status']) for i in h['items']]}")

            # --- 15. Zero-result filters -------------------------------------------
            r = await client.get("/api/v1/attendance/history?subject_code=BCS-999", headers=temp_headers)
            h = r.json()
            r2 = await client.get("/api/v1/attendance/history?search=zzzzz", headers=temp_headers)
            h2 = r2.json()
            check("15. zero-result filters (unknown subject / nonsense search): "
                  "200, empty items, total_count 0, same shape, zero summary",
                  r.status_code == 200 and r2.status_code == 200 and check_shape(h)
                  and h["total_count"] == 0 and h2["total_count"] == 0
                  and h["items"] == [] and h2["items"] == []
                  and h["summary"] == {"total": 0, "attended": 0, "missed": 0,
                                       "pending": 0, "cancelled": 0, "pct": None},
                  f"h={h['total_count']} h2={h2['total_count']}")

            # --- 16. Pagination / Load More ----------------------------------------
            page_ids: list[str] = []
            r = await client.get("/api/v1/attendance/history?limit=5&offset=0", headers=temp_headers)
            h0 = r.json()
            page_ids += [i["id"] for i in h0["items"]]
            r = await client.get("/api/v1/attendance/history?limit=5&offset=5", headers=temp_headers)
            h1 = r.json()
            page_ids += [i["id"] for i in h1["items"]]
            r = await client.get("/api/v1/attendance/history?limit=5&offset=100", headers=temp_headers)
            hend = r.json()
            check("16. pagination: fixed page size, disjoint pages, total_count "
                  "constant, offset beyond end -> empty with full total_count",
                  r.status_code == 200 and len(h0["items"]) == 5 and len(h1["items"]) == 5
                  and h0["total_count"] == h1["total_count"] == hend["total_count"] == 22
                  and len(set(page_ids)) == 10 and hend["items"] == [],
                  f"p0={len(h0['items'])} p1={len(h1['items'])} dup={10 - len(set(page_ids))} "
                  f"total={h0['total_count']} beyond={hend['total_count']}")
            # Full accumulation (5 pages x 5) must cover exactly 22 unique rows.
            all_ids: list[str] = []
            for off in range(0, 25, 5):
                r = await client.get(f"/api/v1/attendance/history?limit=5&offset={off}", headers=temp_headers)
                all_ids += [i["id"] for i in r.json()["items"]]
            check("16b. Load More accumulation: pages cover every one of the 22 "
                  "occurrences exactly once (no mixing/duplication between pages)",
                  len(all_ids) == 22 and len(set(all_ids)) == 22,
                  f"fetched={len(all_ids)} unique={len(set(all_ids))}")

            # --- 17. Clearing filters (final unfiltered) ---------------------------
            r = await client.get("/api/v1/attendance/history", headers=temp_headers)
            h = r.json()
            check("17. clearing filters: unfiltered total_count unchanged (22) "
                  "with the end-state summary (attended=1, missed=1, pending=19, "
                  "cancelled=1, pct=50.0)",
                  r.status_code == 200 and h["total_count"] == 22
                  and h["summary"] == {"total": 21, "attended": 1, "missed": 1,
                                       "pending": 19, "cancelled": 1, "pct": 50.0},
                  f"total={h['total_count']} summary={h['summary']}")
    finally:
        async with AsyncSessionLocal() as db:
            if test_event_ids:
                await db.execute(delete(AcademicEvent).where(AcademicEvent.id.in_(test_event_ids)))
            if test_record_ids:
                await db.execute(delete(AttendanceRecord).where(AttendanceRecord.id.in_(test_record_ids)))
            if temp_user_id is not None:
                await db.execute(delete(StudentEnrollment).where(StudentEnrollment.user_id == temp_user_id))
                await db.execute(delete(User).where(User.id == temp_user_id))
            # Restore session state the tests touched: un-cancel, clear designations.
            stale = (await db.execute(select(ClassSession).where(
                ClassSession.date >= WINDOW_START, ClassSession.date <= WINDOW_END))).scalars().all()
            attended_ids = set()
            if stale:
                rec_rows = (await db.execute(
                    select(AttendanceRecord.class_session_id).where(
                        AttendanceRecord.class_session_id.in_([s.id for s in stale])))).all()
                attended_ids = {r[0] for r in rec_rows}
            for s in stale:
                if s.id in attended_ids:
                    continue
                if s.is_extra:
                    await db.delete(s)
                elif s.is_cancelled:
                    s.is_cancelled = False
                if s.designation is not None:
                    s.designation = None
            await db.commit()

    check("18. response shape consistent across every filtered request",
          shapes_ok)

    async with AsyncSessionLocal() as db:
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

    check("19. database restored to the exact baseline (events/sessions/cancelled/"
          "extra/records/enrollments/subjects/quizzes/users/admins/lab tables/"
          "designations)",
          (events_after, sessions_after, cancelled_after, extra_after, records_after,
           enrollments_after, subjects_after, quizzes_after, users_after, admins_after,
           lab_exp_after, lab_rec_after, designated_after)
          == (events_before, sessions_before, cancelled_before, extra_before, records_before,
              enrollments_before, subjects_before, quizzes_before, users_before, admins_before,
              lab_exp_before, lab_rec_before, designated_before),
          f"events {events_before}->{events_after} sessions {sessions_before}->{sessions_after} "
          f"cancelled {cancelled_before}->{cancelled_after} extra {extra_before}->{extra_after} "
          f"records {records_before}->{records_after} enrollments {enrollments_before}->{enrollments_after} "
          f"subjects {subjects_before}->{subjects_after} quizzes {quizzes_before}->{quizzes_after} "
          f"users {users_before}->{users_after} admins {admins_before}->{admins_after} "
          f"lab_exp {lab_exp_before}->{lab_exp_after} lab_rec {lab_rec_before}->{lab_rec_after} "
          f"designated {designated_before}->{designated_after}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\nHistory filter verification: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
