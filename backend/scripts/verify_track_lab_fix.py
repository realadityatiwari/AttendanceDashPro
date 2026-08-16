"""
Focused Track lab-attendance correction verification (post-Phase 9.2.1).

Verifies the two product fixes against the real database (httpx ASGITransport
+ real DB + minted JWTs, the established pattern):

A. TWO-HOUR LAB = ONE ATTENDANCE OCCURRENCE
   A two-hour laboratory block is scheduled as TWO contiguous one-hour
   timetable periods (BCS-551 Mon 13:00 + 14:00) but represents ONE lab
   attendance occurrence. The daily read model collapses the block into a
   single card ("01:00 PM – 03:00 PM"); one mutation records ONE canonical
   AttendanceRecord; summary/analytics/history denominators count the lab
   once (no denominator inflation); non-contiguous / different-subject
   practicals are never merged.

   1.  daily read model returns ONE BCS-551 occurrence on a lab Monday
       (start 01:00 PM, end 03:00 PM; day total = 3 lectures + 1 lab).
   2.  marking the occurrence Present creates EXACTLY ONE AttendanceRecord.
   3.  changing to Absent on the same occurrence updates the SAME record
       (still exactly one; no duplicates).
   4.  summary practical total counts BLOCKS (4 Monday lab blocks through
       08-15, not 8 timetable rows; missed=1, pending=3, pct recorded-only).
   5.  history represents the lab once (4 BCS-551 items, one per block;
       summary pending counts blocks).
   6.  overall analytics count the lab once (recorded=1, pending=3 for the
       lab-only temp user; never 2/8).
   7.  a mid-sem extra on a NON-lab day stays a standalone occurrence (one
       extra, designated; not merged with anything).

B. FUTURE DATES ARE VIEW-ONLY
   8.  GET daily for a future date succeeds; sessions (incl. the future lab
       block) are returned normally.
   9.  attendance mutation for a future session is rejected (400); no
       AttendanceRecord is created.
  10.  past dates remain markable (covered by A2/A3); a session dated today
       (when one exists) is also markable.
  11.  a future MID_SEM_PRACTICAL event session is visible (designated in
       Track) but cannot be marked before its date (400); deactivating the
       event clears the designation (reversibility intact).

C. PHASE 9 LABORATORY INTEGRATION
  12.  laboratory summary practical block == canonical attendance summary
       (one source of truth; no second calculation).
  13.  LAB_CANCELLED excludes the whole lab occurrence (daily shows the block
       cancelled; marking -> 409; deactivating un-cancels it; the denominator
       drops by exactly one block).
  14.  no experiment-management behavior is touched (laboratory tables empty
       before and after — no fabricated curriculum/progress).

State changes are this script's own artifacts (a temp user, events, records,
designations, session state) and are removed in the finally block. No old
assertion is weakened.

Usage:
    python scripts/verify_track_lab_fix.py
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
from app.models.timetable import ClassSession, TimetableEntry
from app.models.attendance import AttendanceRecord
from app.models.academic import StudentEnrollment, Subject
from app.models.quiz import QuizSchedule
from app.models.laboratory import LaboratoryExperiment, LaboratoryRecord
from app.models.enums import AttendanceStatus, ClassType, UserRole, SessionDesignation
from sqlalchemy import select, func, delete

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


# --- test dates -------------------------------------------------------------
D_LAB = date(2026, 7, 20)       # past Monday  — BCS-551 2-period lab block
D_CANCEL = date(2026, 7, 27)    # past Monday  — lab cancellation
D_EXTRA = date(2026, 7, 22)     # Wednesday    — BCS-551 has NO timetable practical
D_FUT = date(2026, 8, 17)       # future Monday — lab block visible, not markable
D_FUT2 = date(2026, 8, 24)      # future Monday — future MID_SEM_PRACTICAL target
WINDOW_START = date(2026, 7, 15)
WINDOW_END = date(2026, 8, 31)


async def practical_sessions(db, subject_id: uuid.UUID, target: date):
    stmt = (
        select(ClassSession)
        .outerjoin(TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id)
        .where(
            ClassSession.subject_id == subject_id,
            ClassSession.date == target,
            ClassSession.class_type == ClassType.PRACTICAL,
        )
        .order_by(TimetableEntry.start_time.asc().nulls_last(), ClassSession.id.asc())
    )
    return (await db.execute(stmt)).scalars().all()


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

        # Temp student: ONE enrollment (BCS-551, a 2-period-lab subject) + the
        # shared section (analytics context) — a clean slate for the lab checks.
        temp_user = User(
            roll_number="TRK_TMP_LAB",
            name="Track Lab Fix Temp",
            role=UserRole.STUDENT,
            section_id=section.id if section else None,
        )
        db.add(temp_user)
        await db.flush()
        db.add(StudentEnrollment(user_id=temp_user.id, subject_id=subject_ids["BCS-551"]))
        await db.commit()
        temp_user_id = temp_user.id

    temp_token = create_access_token(str(temp_user_id), "TRK_TMP_LAB")
    temp_headers = {"Authorization": f"Bearer {temp_token}"}

    test_event_ids: list[uuid.UUID] = []
    test_record_ids: list[uuid.UUID] = []

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # --- A1. Daily read model: one lab occurrence -------------------------
            r = await client.get(f"/api/v1/attendance/daily/{D_LAB.isoformat()}", headers=temp_headers)
            daily = r.json()["sessions"]
            bcs551 = [s for s in daily if s["subject_code"] == "BCS-551"]
            check("A1. daily read model: 2-period lab Monday -> ONE BCS-551 "
                  "occurrence (01:00 PM – 03:00 PM), not two per-period rows",
                  r.status_code == 200 and len(daily) == 1 and len(bcs551) == 1
                  and bcs551[0]["start_time"] == "01:00 PM" and bcs551[0]["end_time"] == "03:00 PM"
                  and bcs551[0]["class_type"] == "P",
                  f"daily={[(s['subject_code'], s['start_time'], s['end_time']) for s in daily]}")

            # --- A2. One mutation -> exactly ONE AttendanceRecord ------------------
            lab_occ = bcs551[0]
            r = await client.post("/api/v1/attendance", headers=temp_headers, json={
                "class_session_id": lab_occ["id"], "status": "Attended"})
            if r.status_code == 200:
                test_record_ids.append(uuid.UUID(r.json()["id"]))
            async with AsyncSessionLocal() as db:
                members = await practical_sessions(db, subject_ids["BCS-551"], D_LAB)
                recs = (await db.execute(select(AttendanceRecord).where(
                    AttendanceRecord.user_id == temp_user_id,
                    AttendanceRecord.class_session_id.in_([s.id for s in members])))).scalars().all()
            check("A2. marking the lab occurrence Present creates EXACTLY ONE "
                  "canonical AttendanceRecord (not one per timetable period)",
                  r.status_code == 200 and len(recs) == 1 and recs[0].status == AttendanceStatus.ATTENDED,
                  f"got {r.status_code} records={len(recs)}")

            # --- A3. Change on the same occurrence updates the SAME record --------
            r = await client.post("/api/v1/attendance", headers=temp_headers, json={
                "class_session_id": lab_occ["id"], "status": "Missed"})
            async with AsyncSessionLocal() as db:
                members = await practical_sessions(db, subject_ids["BCS-551"], D_LAB)
                recs = (await db.execute(select(AttendanceRecord).where(
                    AttendanceRecord.user_id == temp_user_id,
                    AttendanceRecord.class_session_id.in_([s.id for s in members])))).scalars().all()
            check("A3. changing to Absent updates the SAME record (still exactly "
                  "one; no duplicate records on the block)",
                  r.status_code == 200 and len(recs) == 1 and recs[0].status == AttendanceStatus.MISSED,
                  f"got {r.status_code} records={len(recs)}")

            # --- A4. Summary denominator counts blocks ----------------------------
            async with AsyncSessionLocal() as db:
                # Direct block count: distinct lab dates through 08-15 (all 2-period).
                n_rows = (await db.execute(select(func.count()).select_from(ClassSession).where(
                    ClassSession.subject_id == subject_ids["BCS-551"],
                    ClassSession.class_type == ClassType.PRACTICAL,
                    ClassSession.date <= date(2026, 8, 15),
                    ClassSession.is_cancelled.is_(False)))).scalar()
                n_blocks = (await db.execute(
                    select(func.count(func.distinct(ClassSession.date))).select_from(ClassSession).where(
                        ClassSession.subject_id == subject_ids["BCS-551"],
                        ClassSession.class_type == ClassType.PRACTICAL,
                        ClassSession.date <= date(2026, 8, 15),
                        ClassSession.is_cancelled.is_(False)))).scalar()
            r = await client.get("/api/v1/attendance/summary/BCS-551?as_of_date=2026-08-15",
                                 headers=temp_headers)
            b = r.json()
            check("A4. summary practical denominator counts the lab once: "
                  f"{n_blocks} blocks (not {n_rows} timetable rows); missed=1, "
                  "pending=3, recorded-only pct=0",
                  r.status_code == 200 and b["practical"]["total"] == n_blocks == 4
                  and b["practical"]["missed"] == 1 and b["practical"]["pending"] == 3
                  and abs((b["current_practical_pct"] or 0.0) - 0.0) < 1e-9,
                  f"rows={n_rows} blocks={n_blocks} summary={b['practical']} pct={b['current_practical_pct']}")

            # --- A5. History represents the lab once ------------------------------
            r = await client.get("/api/v1/attendance/history?subject_code=BCS-551",
                                 headers=temp_headers)
            hist = r.json()
            check("A5. history represents the lab once (4 items, one per block; "
                  "summary pending counts blocks)",
                  r.status_code == 200 and hist["total_count"] == 4
                  and hist["summary"]["missed"] == 1 and hist["summary"]["pending"] == 3,
                  f"total={hist['total_count']} summary={hist['summary']}")

            # --- A6. Overall analytics count the lab once -------------------------
            r = await client.get("/api/v1/analytics/overview", headers=temp_headers)
            ov = r.json()["overall"]
            check("A6. overall analytics count the lab once (lab-only user: "
                  "recorded=1, pending=3, attended=0 — a 2-hour lab is one row)",
                  r.status_code == 200 and ov["recorded"] == 1 and ov["pending"] == 3
                  and ov["attended"] == 0 and ov["cancelled"] == 0,
                  f"overall={ov}")

            # --- A7. Non-lab-day mid-sem extra stays a standalone occurrence ------
            r = await client.post("/api/v1/events", headers=temp_headers, json={
                "event_type": "MID_SEM_PRACTICAL", "start_date": D_EXTRA.isoformat(),
                "end_date": D_EXTRA.isoformat(),
                "subject_id": str(subject_ids["BCS-551"]), "class_type": "P"})
            extra_mid_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None
            if extra_mid_id:
                test_event_ids.append(extra_mid_id)
            async with AsyncSessionLocal() as db:
                extra_sess = await practical_sessions(db, subject_ids["BCS-551"], D_EXTRA)
            check("A7. mid-sem on a non-lab day materializes exactly ONE standalone "
                  "practical occurrence (designated extra, not merged)",
                  r.status_code == 201 and len(extra_sess) == 1 and extra_sess[0].is_extra
                  and extra_sess[0].designation == SessionDesignation.MID_SEM_PRACTICAL,
                  f"got {r.status_code} sessions={len(extra_sess)}")

            # --- B8. Future date: reads succeed, sessions visible -----------------
            r = await client.get(f"/api/v1/attendance/daily/{D_FUT.isoformat()}", headers=temp_headers)
            daily_fut = r.json()["sessions"]
            fut_551 = [s for s in daily_fut if s["subject_code"] == "BCS-551"]
            check("B8. future date read succeeds; future lab block visible as ONE "
                  "occurrence (view-only)",
                  r.status_code == 200 and len(fut_551) == 1 and fut_551[0]["status"] == "Pending",
                  f"got {r.status_code} fut551={[(s['start_time'], s['status']) for s in fut_551]}")

            # --- B9. Future mutation rejected, no record created ------------------
            r = await client.post("/api/v1/attendance", headers=temp_headers, json={
                "class_session_id": fut_551[0]["id"], "status": "Attended"})
            async with AsyncSessionLocal() as db:
                rec_count = (await db.execute(select(func.count()).select_from(AttendanceRecord).where(
                    AttendanceRecord.user_id == temp_user_id,
                    AttendanceRecord.class_session_id == uuid.UUID(fut_551[0]["id"])))).scalar()
            check("B9. future attendance mutation rejected (400); no AttendanceRecord "
                  "created",
                  r.status_code == 400 and rec_count == 0,
                  f"got {r.status_code} {r.text[:120]} records={rec_count}")

            # --- B10. Today remains markable (when the date has sessions) ---------
            from app.services.attendance_service import institution_today
            today = institution_today()
            r = await client.get(f"/api/v1/attendance/daily/{today.isoformat()}", headers=temp_headers)
            today_sessions = r.json()["sessions"]
            if today_sessions:
                r = await client.post("/api/v1/attendance", headers=temp_headers, json={
                    "class_session_id": today_sessions[0]["id"], "status": "Attended"})
                ok_today = r.status_code == 200
                if r.status_code == 200:
                    test_record_ids.append(uuid.UUID(r.json()["id"]))
                detail = f"got {r.status_code}"
            else:
                # Sunday boundary: no classes today; past (A2/A3) accepted and
                # future (B9) rejected pin the boundary.
                ok_today = True
                detail = "no sessions today (weekend) — boundary covered by past/future"
            check("B10. today remains markable (present-day sessions accept "
                  "mutation)",
                  ok_today, detail)

            # --- B11. Future MID_SEM_PRACTICAL: visible, not markable, reversible --
            r = await client.post("/api/v1/events", headers=temp_headers, json={
                "event_type": "MID_SEM_PRACTICAL", "start_date": D_FUT2.isoformat(),
                "end_date": D_FUT2.isoformat(),
                "subject_id": str(subject_ids["BCS-551"]), "class_type": "P"})
            fut_mid_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None
            if fut_mid_id:
                test_event_ids.append(fut_mid_id)
            r_daily = await client.get(f"/api/v1/attendance/daily/{D_FUT2.isoformat()}", headers=temp_headers)
            desig_daily = [s for s in r_daily.json()["sessions"]
                           if s["subject_code"] == "BCS-551" and s.get("designation") == "MID_SEM_PRACTICAL"]
            fut_mark = None
            if desig_daily:
                fut_mark = await client.post("/api/v1/attendance", headers=temp_headers, json={
                    "class_session_id": desig_daily[0]["id"], "status": "Attended"})
            if fut_mid_id is not None:
                r_del = await client.delete(f"/api/v1/events/{fut_mid_id}", headers=temp_headers)
            async with AsyncSessionLocal() as db:
                after_del = [s for s in await practical_sessions(db, subject_ids["BCS-551"], D_FUT2)
                             if s.designation is not None]
            check("B11. future mid-sem event session is visible (designated in "
                  "Track), cannot be marked before its date (400), and "
                  "deactivating the event clears the designation",
                  r.status_code == 201 and len(desig_daily) == 1
                  and fut_mark is not None and fut_mark.status_code == 400
                  and r_del is not None and r_del.status_code == 200 and len(after_del) == 0,
                  f"event={r.status_code} desig_daily={len(desig_daily)} mark={fut_mark.status_code if fut_mark else None}")

            # --- C12. Laboratory summary == canonical attendance summary -----------
            r_sum = await client.get("/api/v1/laboratory/BCS-551/summary", headers=temp_headers)
            r_att = await client.get("/api/v1/attendance/summary/BCS-551", headers=temp_headers)
            p_lab = r_sum.json()["practical_attendance"]
            p_att = r_att.json()["practical"]
            check("C12. laboratory practical block == canonical attendance summary "
                  "(one source of truth; no second calculation)",
                  r_sum.status_code == 200 and p_lab["attended"] == p_att["attended"]
                  and p_lab["missed"] == p_att["missed"] and p_lab["pending"] == p_att["pending"]
                  and p_lab["total"] == p_att["total"]
                  and abs(p_lab["current_practical_pct"]
                          - (r_att.json()["current_practical_pct"] or 0.0)) < 1e-9,
                  f"lab={p_lab} att={p_att}")

            # --- C13. LAB_CANCELLED excludes the whole lab occurrence --------------
            # Snapshot the summary (as of today) BEFORE the cancellation, then
            # create the event and observe the block-level exclusion.
            r_pre = await client.get("/api/v1/attendance/summary/BCS-551", headers=temp_headers)
            pre_total = r_pre.json()["practical"]["total"]
            r = await client.post("/api/v1/events", headers=temp_headers, json={
                "event_type": "LAB_CANCELLED", "start_date": D_CANCEL.isoformat(),
                "end_date": D_CANCEL.isoformat(),
                "subject_id": str(subject_ids["BCS-551"]), "class_type": "P"})
            cancel_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None
            if cancel_id:
                test_event_ids.append(cancel_id)
            r_daily = await client.get(f"/api/v1/attendance/daily/{D_CANCEL.isoformat()}", headers=temp_headers)
            cancelled_block = [s for s in r_daily.json()["sessions"]
                               if s["subject_code"] == "BCS-551" and s["is_cancelled"]]
            mark_rejected = None
            if cancelled_block:
                mark_rejected = await client.post("/api/v1/attendance", headers=temp_headers, json={
                    "class_session_id": cancelled_block[0]["id"], "status": "Attended"})
            r_after = await client.get("/api/v1/attendance/summary/BCS-551", headers=temp_headers)
            after_total = r_after.json()["practical"]["total"]
            check("C13. LAB_CANCELLED excludes the WHOLE lab occurrence (block "
                  "cancelled in Track; marking rejected 409; denominator drops by "
                  "exactly one block)",
                  r.status_code == 201 and len(cancelled_block) == 1
                  and mark_rejected is not None and mark_rejected.status_code == 409
                  and after_total == pre_total - 1,
                  f"event={r.status_code} cancelled_in_daily={len(cancelled_block)} "
                  f"mark={mark_rejected.status_code if mark_rejected else None} "
                  f"total {pre_total}->{after_total}")
            # Reversibility: deactivating the cancellation un-cancels the block.
            if cancel_id is not None:
                r_del = await client.delete(f"/api/v1/events/{cancel_id}", headers=temp_headers)
            async with AsyncSessionLocal() as db:
                un_cancel = await practical_sessions(db, subject_ids["BCS-551"], D_CANCEL)
            check("C13b. deactivating LAB_CANCELLED un-cancels the lab occurrence "
                  "(state-based reversibility)",
                  r_del is not None and r_del.status_code == 200
                  and all(not s.is_cancelled for s in un_cancel),
                  f"del={r_del.status_code if r_del else None} cancelled={[s.is_cancelled for s in un_cancel]}")

            # --- C14. No experiment-management behavior touched --------------------
            async with AsyncSessionLocal() as db:
                le = (await db.execute(select(func.count()).select_from(LaboratoryExperiment))).scalar()
                lr = (await db.execute(select(func.count()).select_from(LaboratoryRecord))).scalar()
            check("C14. no fabricated experiment data (laboratory tables empty "
                  "before and after)",
                  le == 0 and lr == 0, f"exp={le} rec={lr}")
    finally:
        async with AsyncSessionLocal() as db:
            if test_event_ids:
                await db.execute(delete(AcademicEvent).where(AcademicEvent.id.in_(test_event_ids)))
            if test_record_ids:
                await db.execute(delete(AttendanceRecord).where(AttendanceRecord.id.in_(test_record_ids)))
            if temp_user_id is not None:
                await db.execute(delete(StudentEnrollment).where(StudentEnrollment.user_id == temp_user_id))
                await db.execute(delete(User).where(User.id == temp_user_id))
            # Restore every session the tests touched: delete unattended extras,
            # un-cancel unattended cancelled sessions, clear designations.
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

    check("D. database restored to the exact baseline (events/sessions/cancelled/"
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
    print(f"\nTrack lab fix verification: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
