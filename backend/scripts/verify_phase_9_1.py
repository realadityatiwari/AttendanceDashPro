"""
Phase 9.1 verification — Laboratory Attendance & Event Integration.

Verifies the Phase 9.1 product contract end-to-end against the real database
(httpx ASGITransport + real DB + minted JWTs, the established pattern). The
Mid-Sem Practical and Lab Cancelled events are NOT separate attendance
systems: they are AcademicEvents the canonical EventSessionSynchronizer
resolves into ClassSession state (AcademicEvent -> synchronizer ->
ClassSession -> AttendanceRecord -> existing engines).

Checks (mapping to the Phase 9.1 brief §17):

  1.  Student can create MID_SEM_PRACTICAL for an enrolled practical subject.
  2.  Student cannot create it for an unenrolled subject (403).
  3.  Student can create LAB_CANCELLED for an enrolled practical subject.
  4.  Student cannot create it for an unenrolled subject (403).
  5.  Mid-sem produces exactly ONE relevant practical attendance occurrence
      (existing timetable session reused, not duplicated; designation visible
      on the daily/Track read model).
  6.  No duplicate session on repeated synchronization (idempotent PATCH).
  7.  The existing practical occurrence is reused/overridden, not duplicated
      (designated session is timetable-bound and pre-existed the event).
  8.  Lab cancellation makes the matching practical occurrence cancelled.
  9.  A cancelled occurrence rejects attendance marking (409).
 10.  Mid-sem Present becomes an AttendanceRecord (canonical mutation).
 11.  Mid-sem Absent becomes an AttendanceRecord (canonical mutation).
 12.  Practical percentage changes correctly (summary, recorded-only).
 13.  Overall analytics changes correctly per canonical rules (cancelled
      excluded; pending stays pending; current recorded-only).
 14.  Quiz eligibility does NOT include practical attendance (labs 404;
      theory eligibility byte-identical before/after).
 15.  Event deactivation reconciles the schedule (designation cleared, lab
      un-cancelled, attendance records preserved).
 16.  Event date movement reconciles old and new dates.
 17.  Duplicate/conflicting events handled deterministically (duplicate 409;
      LAB_CANCELLED + MID_SEM on the same date -> cancellation wins, one
      session, no conflicting attendance opportunities).
 18.  Attended sessions are protected (never cancelled/silently rewritten).
 19.  No fake experiment data appears (laboratory tables stay empty).
 20.  Existing event types remain functional (admin EXTRA_LECTURE smoke).
 21.  Existing Phase 8.2 behavior remains intact (admin-only mid-sem endpoint,
      summary health + mid-sem fields).
 22.  Database baseline is restored exactly after the verifier runs.

State changes are this script's own artifacts (a temp user, events, records,
designations, session state) and are removed in the finally block; rollback
transactions are used where possible. No old assertion is weakened.

Usage:
    python scripts/verify_phase_9_1.py
"""
import asyncio
import json
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


# --- test dates (all past relative to 2026-08-15, within the semester) -----
D_MID = date(2026, 7, 17)       # Friday  — BCS-553 lab day (2 P sessions)
D_MID2 = date(2026, 7, 24)      # Friday  — mid-sem move target
D_EXTRA = date(2026, 7, 20)     # Monday  — BCS-553 has NO timetable practical
D_CANCEL = date(2026, 7, 31)    # Friday  — lab cancellation
D_CONFLICT = date(2026, 8, 7)   # Friday  — mid-sem + lab-cancelled conflict
D_EXTRA_LEC = date(2026, 7, 28) # Tuesday — existing-type smoke (EXTRA_LECTURE)
WINDOW_START = date(2026, 7, 17)
WINDOW_END = date(2026, 8, 14)


async def count_sessions(db, *filters) -> int:
    stmt = select(func.count()).select_from(ClassSession)
    for f in filters:
        stmt = stmt.where(f)
    return (await db.execute(stmt)).scalar()


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
        # Window-scoped pre-run snapshot (2026-08-16 quiz-correction audit): the
        # owner actively tests the live app against the same database while this
        # verifier runs (their events/attendance/extras materialize through the
        # reloaded backend). Cleanup must restore ONLY what THIS verifier
        # changed — pre-existing sessions keep their exact pre-run
        # cancellation/designation state, and sessions the verifier created are
        # removed — never the owner's data.
        pre_window_sessions = {}
        pre_window_rows = (await db.execute(select(ClassSession).where(
            ClassSession.date >= WINDOW_START, ClassSession.date <= WINDOW_END))).scalars().all()
        pre_window_sessions = {s.id: (s.is_cancelled, s.designation) for s in pre_window_rows}

        admin_user = (await db.execute(select(User).where(User.role == UserRole.ADMIN))).scalars().first()
        section = (await db.execute(select(Section))).scalars().first()
        subject_ids = {s.code: s.id for s in (await db.execute(select(Subject))).scalars().all()}

        # Baseline eligibility snapshot (Phase 8.2 frozen payload shape) — must
        # be byte-identical after all Phase 9.1 activity.
        elig_before = None
        admin_token_pre = create_access_token(str(admin_user.id), admin_user.roll_number)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/quiz-eligibility/BCS-501/1",
                            headers={"Authorization": f"Bearer {admin_token_pre}"})
            elig_before = r.json()

        # Temp student: ONE enrollment (BCS-553) + the shared section (so the
        # analytics range resolves to the real semester) — proves the
        # enrollment boundary both ways and gives a clean attendance slate.
        temp_user = User(
            roll_number="PH9_TMP",
            name="Phase 9.1 Temp",
            role=UserRole.STUDENT,
            section_id=section.id if section else None,
        )
        db.add(temp_user)
        await db.flush()
        db.add(StudentEnrollment(user_id=temp_user.id, subject_id=subject_ids["BCS-553"]))
        await db.commit()
        temp_user_id = temp_user.id

    temp_token = create_access_token(str(temp_user_id), "PH9_TMP")
    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    temp_headers = {"Authorization": f"Bearer {temp_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    test_event_ids: list[uuid.UUID] = []
    test_record_ids: list[uuid.UUID] = []

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # --- 1-4. Student authorization --------------------------------------
            r = await client.post("/api/v1/events", headers=temp_headers, json={
                "event_type": "MID_SEM_PRACTICAL", "start_date": D_MID.isoformat(), "end_date": D_MID.isoformat(),
                "subject_id": str(subject_ids["BCS-553"]), "class_type": "P", "note": "Mid sem test"})
            ok = r.status_code == 201 and r.json()["event_type"] == "MID_SEM_PRACTICAL" \
                and r.json()["note"] == "Mid sem test"
            if ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
            check("1. student creates MID_SEM_PRACTICAL for enrolled practical subject -> 201 "
                  "(note persisted)", ok, f"got {r.status_code} {r.text[:200]}")
            mid_event_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None

            r = await client.post("/api/v1/events", headers=temp_headers, json={
                "event_type": "MID_SEM_PRACTICAL", "start_date": D_MID.isoformat(), "end_date": D_MID.isoformat(),
                "subject_id": str(subject_ids["BCS-501"]), "class_type": "P"})
            check("2. student MID_SEM_PRACTICAL for UNENROLLED subject -> 403",
                  r.status_code == 403, f"got {r.status_code} {r.text[:200]}")

            # Snapshot the pre-cancellation session state BEFORE the event exists,
            # so check 8 can prove the LAB_CANCELLED event itself flipped the flag.
            async with AsyncSessionLocal() as db:
                pre_c_initial = await practical_sessions(db, subject_ids["BCS-553"], D_CANCEL)
                pre_c_initial_cancelled = [s for s in pre_c_initial if s.is_cancelled]

            r = await client.post("/api/v1/events", headers=temp_headers, json={
                "event_type": "LAB_CANCELLED", "start_date": D_CANCEL.isoformat(), "end_date": D_CANCEL.isoformat(),
                "subject_id": str(subject_ids["BCS-553"]), "class_type": "P", "note": "Technical issue"})
            ok = r.status_code == 201 and r.json()["event_type"] == "LAB_CANCELLED"
            if ok:
                test_event_ids.append(uuid.UUID(r.json()["id"]))
            check("3. student creates LAB_CANCELLED for enrolled practical subject -> 201",
                  ok, f"got {r.status_code} {r.text[:200]}")
            cancel_event_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None

            r = await client.post("/api/v1/events", headers=temp_headers, json={
                "event_type": "LAB_CANCELLED", "start_date": D_CANCEL.isoformat(), "end_date": D_CANCEL.isoformat(),
                "subject_id": str(subject_ids["BCS-501"]), "class_type": "P"})
            check("4. student LAB_CANCELLED for UNENROLLED subject -> 403",
                  r.status_code == 403, f"got {r.status_code} {r.text[:200]}")

            # --- 5-7. Mid-sem session resolution ---------------------------------
            async with AsyncSessionLocal() as db:
                pre = await practical_sessions(db, subject_ids["BCS-553"], D_MID)
                pre_ids = {s.id for s in pre}
                pre_count = len(pre)
            if mid_event_id is not None:
                r = await client.get("/api/v1/attendance/daily/" + D_MID.isoformat(), headers=temp_headers)
                daily = r.json()["sessions"]
                daily_553 = [s for s in daily if s["subject_code"] == "BCS-553"]
                designated_daily = [s for s in daily_553 if s.get("designation") == "MID_SEM_PRACTICAL"]
            else:
                daily_553, designated_daily = [], []
            async with AsyncSessionLocal() as db:
                post = await practical_sessions(db, subject_ids["BCS-553"], D_MID)
                post_ids = [s.id for s in post]
                designated = [s for s in post if s.designation == SessionDesignation.MID_SEM_PRACTICAL]
            check("5. mid-sem produces exactly ONE practical attendance occurrence "
                  "(no duplicate; designation visible on the daily read model)",
                  mid_event_id is not None and len(post) == pre_count == 2
                  and len(designated) == 1 and len(designated_daily) == 1,
                  f"pre={pre_count} post={len(post)} designated={len(designated)} daily553={len(daily_553)}")

            # Idempotency: a second sync (note PATCH) must not duplicate.
            if mid_event_id is not None:
                r = await client.patch(f"/api/v1/events/{mid_event_id}", headers=temp_headers, json={
                    "note": "Mid sem test (edited)"})
                sync_ok = r.status_code == 200
            else:
                sync_ok = False
            async with AsyncSessionLocal() as db:
                post2 = await practical_sessions(db, subject_ids["BCS-553"], D_MID)
                designated2 = [s for s in post2 if s.designation == SessionDesignation.MID_SEM_PRACTICAL]
            check("6. no duplicate session on repeated synchronization "
                  "(note PATCH re-sync keeps one occurrence, one designation)",
                  sync_ok and len(post2) == pre_count == 2 and len(designated2) == 1
                  and designated2[0].id == designated[0].id,
                  f"post2={len(post2)} designated2={len(designated2)}")

            check("7. existing practical occurrence reused/overridden, not duplicated "
                  "(designated session is the pre-existing timetable session)",
                  len(designated) == 1 and designated[0].id in pre_ids
                  and designated[0].timetable_entry_id is not None,
                  f"designated_id={designated[0].id if designated else None} "
                  f"pre_ids={sorted(str(i)[:8] for i in pre_ids)}")

            # --- 8-9. Lab cancellation -------------------------------------------
            async with AsyncSessionLocal() as db:
                post_c = await practical_sessions(db, subject_ids["BCS-553"], D_CANCEL)
                post_c_cancelled = [s for s in post_c if s.is_cancelled]
            if cancel_event_id is not None:
                r = await client.get("/api/v1/attendance/daily/" + D_CANCEL.isoformat(), headers=temp_headers)
                cancelled_in_daily = [s for s in r.json()["sessions"]
                                      if s["subject_code"] == "BCS-553" and s["is_cancelled"]]
            else:
                cancelled_in_daily = []
            check("8. lab cancellation makes the matching practical occurrence cancelled "
                  "(canonical is_cancelled; visible in Track)",
                  len(pre_c_initial) == 2 and len(pre_c_initial_cancelled) == 0
                  and len(post_c) == 2 and len(post_c_cancelled) == 1
                  and len(cancelled_in_daily) == 1,
                  f"pre={len(pre_c_initial)}/{len(pre_c_initial_cancelled)} "
                  f"post={len(post_c)}/{len(post_c_cancelled)} daily_cancelled={len(cancelled_in_daily)}")
            async with AsyncSessionLocal() as db:
                cancelled_sess = next((s for s in post_c if s.is_cancelled), None)
            r = await client.post("/api/v1/attendance", headers=temp_headers, json={
                "class_session_id": str(cancelled_sess.id), "status": "Attended"})
            check("9. cancelled occurrence rejects attendance marking (409, cancelled != absent)",
                  r.status_code == 409, f"got {r.status_code} {r.text[:150]}")

            # --- 10-11. Attendance integration (canonical mutation) --------------
            async with AsyncSessionLocal() as db:
                desig = (await practical_sessions(db, subject_ids["BCS-553"], D_MID))[0]
                designated_session = next(
                    (s for s in await practical_sessions(db, subject_ids["BCS-553"], D_MID)
                     if s.designation == SessionDesignation.MID_SEM_PRACTICAL), None)
            r = await client.post("/api/v1/attendance", headers=temp_headers, json={
                "class_session_id": str(designated_session.id), "status": "Attended"})
            if r.status_code == 200:
                test_record_ids.append(uuid.UUID(r.json()["id"]))
            async with AsyncSessionLocal() as db:
                rec = (await db.execute(select(AttendanceRecord).where(
                    AttendanceRecord.user_id == temp_user_id,
                    AttendanceRecord.class_session_id == designated_session.id))).scalars().first()
            check("10. mid-sem Present becomes an AttendanceRecord (canonical mutation)",
                  r.status_code == 200 and rec is not None and rec.status == AttendanceStatus.ATTENDED,
                  f"got {r.status_code} {r.text[:150]}")

            # Move the mid-sem event to another Friday; the old date is cleared,
            # the new date designated (check 16), then mark Absent (check 11).
            r = await client.patch(f"/api/v1/events/{mid_event_id}", headers=temp_headers, json={
                "start_date": D_MID2.isoformat(), "end_date": D_MID2.isoformat()})
            check("16. event date movement reconciles old and new dates "
                  "(old designation cleared, new date designated)",
                  r.status_code == 200, f"move got {r.status_code} {r.text[:200]}")
            async with AsyncSessionLocal() as db:
                old_desig = [s for s in await practical_sessions(db, subject_ids["BCS-553"], D_MID)
                             if s.designation == SessionDesignation.MID_SEM_PRACTICAL]
                new_desig = [s for s in await practical_sessions(db, subject_ids["BCS-553"], D_MID2)
                             if s.designation == SessionDesignation.MID_SEM_PRACTICAL]
            check("16b. after move: no designation on old date, exactly one on new date",
                  len(old_desig) == 0 and len(new_desig) == 1,
                  f"old={len(old_desig)} new={len(new_desig)}")
            moved_session = new_desig[0] if len(new_desig) == 1 else None
            if moved_session is not None:
                r = await client.post("/api/v1/attendance", headers=temp_headers, json={
                    "class_session_id": str(moved_session.id), "status": "Missed"})
                if r.status_code == 200:
                    test_record_ids.append(uuid.UUID(r.json()["id"]))
                async with AsyncSessionLocal() as db:
                    rec2 = (await db.execute(select(AttendanceRecord).where(
                        AttendanceRecord.user_id == temp_user_id,
                        AttendanceRecord.class_session_id == moved_session.id))).scalars().first()
            else:
                r = httpx.Response(500, request=httpx.Request("POST", "http://test"))
                rec2 = None
            check("11. mid-sem Absent becomes an AttendanceRecord (canonical mutation)",
                  r.status_code == 200 and rec2 is not None and rec2.status == AttendanceStatus.MISSED,
                  f"got {r.status_code} {r.text[:150]}")

            # --- 12-13. Attendance + analytics propagation ------------------------
            # Track lab correction: BCS-553's Friday lab is a TWO-period timetable
            # block (13:00 + 14:00) = ONE attendance occurrence. Through 08-15 there
            # are 5 lab blocks; 07-31 is cancelled (excluded): total 4.
            # attended=1 (07-17 block), missed=1 (07-24 block) -> pct = 50.
            r = await client.get("/api/v1/attendance/summary/BCS-553", headers=temp_headers)
            b = r.json()
            check("12. practical percentage changes correctly through the canonical "
                  "summary (occurrence-based: 2-hour lab counts once, 1/2 = 50%)",
                  b["practical"]["attended"] == 1 and b["practical"]["missed"] == 1
                  and b["practical"]["total"] == 4 and b["practical"]["pending"] == 2
                  and abs(b["current_practical_pct"] - 50.0) < 1e-9,
                  f"summary={b['practical']} pct={b['current_practical_pct']}")

            r = await client.get("/api/v1/analytics/overview", headers=temp_headers)
            ov = r.json()["overall"]
            check("13. overall analytics follow canonical rules (cancelled excluded, "
                  "pending stays pending, lab counted once, current recorded-only: 1/2 = 50%)",
                  ov["attended"] == 1 and ov["recorded"] == 2 and ov["pending"] == 2
                  and ov["cancelled"] == 1 and abs(ov["current_pct"] - 50.0) < 1e-9,
                  f"overall={ov}")

            # --- 14. Quiz eligibility unchanged ------------------------------------
            r_lab = await client.get("/api/v1/quiz-eligibility/BCS-553/1", headers=temp_headers)
            r_501 = await client.get("/api/v1/quiz-eligibility/BCS-501/1", headers=admin_headers)
            check("14. quiz eligibility does NOT include practical attendance "
                  "(labs 404; theory eligibility byte-identical before/after)",
                  r_lab.status_code == 404 and r_501.status_code == 200
                  and r_501.json() == elig_before,
                  f"lab={r_lab.status_code} theory_same={r_501.json() == elig_before}")

            # --- 17a. Duplicate event -> 409 ---------------------------------------
            r = await client.post("/api/v1/events", headers=temp_headers, json={
                "event_type": "MID_SEM_PRACTICAL", "start_date": D_MID2.isoformat(),
                "end_date": D_MID2.isoformat(),
                "subject_id": str(subject_ids["BCS-553"]), "class_type": "P"})
            check("17a. duplicate event creation -> 409 (deterministic duplicate guard)",
                  r.status_code == 409, f"got {r.status_code} {r.text[:200]}")

            # --- 17b. MID_SEM + LAB_CANCELLED on the same date: cancellation wins ---
            r = await client.post("/api/v1/events", headers=temp_headers, json={
                "event_type": "LAB_CANCELLED", "start_date": D_CONFLICT.isoformat(),
                "end_date": D_CONFLICT.isoformat(),
                "subject_id": str(subject_ids["BCS-553"]), "class_type": "P"})
            conflict_cancel_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None
            if conflict_cancel_id:
                test_event_ids.append(conflict_cancel_id)
            r = await client.post("/api/v1/events", headers=temp_headers, json={
                "event_type": "MID_SEM_PRACTICAL", "start_date": D_CONFLICT.isoformat(),
                "end_date": D_CONFLICT.isoformat(),
                "subject_id": str(subject_ids["BCS-553"]), "class_type": "P"})
            conflict_mid_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None
            if conflict_mid_id:
                test_event_ids.append(conflict_mid_id)
            async with AsyncSessionLocal() as db:
                cf = await practical_sessions(db, subject_ids["BCS-553"], D_CONFLICT)
                cf_cancelled = [s for s in cf if s.is_cancelled]
                cf_desig = [s for s in cf if s.designation is not None]
            check("17b. MID_SEM + LAB_CANCELLED on the same date resolved "
                  "deterministically (cancellation wins: cancelled, no designation)",
                  conflict_cancel_id is not None and conflict_mid_id is not None
                  and len(cf) == 2 and len(cf_cancelled) == 1 and len(cf_desig) == 0,
                  f"cancelled={len(cf_cancelled)} designated={len(cf_desig)}")

            # --- 18. Attended sessions are protected -------------------------------
            # A LAB_CANCELLED on the date holding the attended mid-sem session must
            # never cancel it; the record stays intact.
            r = await client.post("/api/v1/events", headers=temp_headers, json={
                "event_type": "LAB_CANCELLED", "start_date": D_MID2.isoformat(),
                "end_date": D_MID2.isoformat(),
                "subject_id": str(subject_ids["BCS-553"]), "class_type": "P"})
            protect_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None
            if protect_id:
                test_event_ids.append(protect_id)
            async with AsyncSessionLocal() as db:
                after_protect = await practical_sessions(db, subject_ids["BCS-553"], D_MID2)
                moved_now = next((s for s in after_protect
                                  if s.designation == SessionDesignation.MID_SEM_PRACTICAL), None)
                moved_cancelled = moved_now.is_cancelled if moved_now else None
                rec_still = (await db.execute(select(AttendanceRecord).where(
                    AttendanceRecord.user_id == temp_user_id,
                    AttendanceRecord.class_session_id == moved_now.id))).scalars().first() if moved_now else None
            check("18. attended sessions are protected (attendance never deleted; "
                  "attended mid-sem session not cancelled by a later LAB_CANCELLED)",
                  protect_id is not None and moved_now is not None
                  and moved_cancelled is False and rec_still is not None
                  and rec_still.status == AttendanceStatus.MISSED,
                  f"cancelled={moved_cancelled} record={bool(rec_still)}")

            # --- 15. Reversibility: deactivate mid-sem (records preserved) ---------
            r = await client.delete(f"/api/v1/events/{mid_event_id}", headers=temp_headers)
            async with AsyncSessionLocal() as db:
                after_deact = [s for s in await practical_sessions(db, subject_ids["BCS-553"], D_MID2)
                               if s.designation is not None]
                recs_kept = (await db.execute(select(func.count()).select_from(AttendanceRecord).where(
                    AttendanceRecord.user_id == temp_user_id))).scalar()
            check("15a. deactivating MID_SEM_PRACTICAL clears the designation "
                  "(attendance records preserved)",
                  r.status_code == 200 and len(after_deact) == 0 and recs_kept == 2,
                  f"desig={len(after_deact)} records={recs_kept}")

            # Reversibility: deactivate the conflict cancellation + protect
            # cancellation + the 07-31 cancellation; sessions un-cancel.
            for ev_id in (conflict_cancel_id, conflict_mid_id, protect_id, cancel_event_id):
                if ev_id is not None:
                    await client.delete(f"/api/v1/events/{ev_id}", headers=temp_headers)
            async with AsyncSessionLocal() as db:
                c31 = await practical_sessions(db, subject_ids["BCS-553"], D_CANCEL)
                c07 = await practical_sessions(db, subject_ids["BCS-553"], D_CONFLICT)
                c24 = await practical_sessions(db, subject_ids["BCS-553"], D_MID2)
            check("15b. deactivating LAB_CANCELLED events un-cancels the occurrences "
                  "(reversible state-based reconciliation)",
                  all(not s.is_cancelled for s in c31 + c07 + c24),
                  f"c31={[s.is_cancelled for s in c31]} c07={[s.is_cancelled for s in c07]} "
                  f"c24={[s.is_cancelled for s in c24]}")

            # --- Mid-sem extra materialization (non-lab day) + removal -------------
            r = await client.post("/api/v1/events", headers=temp_headers, json={
                "event_type": "MID_SEM_PRACTICAL", "start_date": D_EXTRA.isoformat(),
                "end_date": D_EXTRA.isoformat(),
                "subject_id": str(subject_ids["BCS-553"]), "class_type": "P"})
            extra_mid_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None
            if extra_mid_id:
                test_event_ids.append(extra_mid_id)
            async with AsyncSessionLocal() as db:
                extra_sess = await practical_sessions(db, subject_ids["BCS-553"], D_EXTRA)
            check("15c. mid-sem on a non-lab day materializes exactly ONE extra "
                  "practical occurrence (designated, available for attendance)",
                  extra_mid_id is not None and len(extra_sess) == 1
                  and extra_sess[0].is_extra and extra_sess[0].timetable_entry_id is None
                  and extra_sess[0].designation == SessionDesignation.MID_SEM_PRACTICAL,
                  f"extras={[(s.id, s.is_extra, s.designation) for s in extra_sess]}")
            r = await client.delete(f"/api/v1/events/{extra_mid_id}", headers=temp_headers)
            async with AsyncSessionLocal() as db:
                after_extra = await practical_sessions(db, subject_ids["BCS-553"], D_EXTRA)
            check("15d. deactivating the non-lab-day mid-sem removes the unattended "
                  "extra (state-based reconciliation, no residue)",
                  r.status_code == 200 and len(after_extra) == 0,
                  f"remaining={len(after_extra)}")

            # --- 19. No fake experiment data ---------------------------------------
            async with AsyncSessionLocal() as db:
                le = (await db.execute(select(func.count()).select_from(LaboratoryExperiment))).scalar()
                lr = (await db.execute(select(func.count()).select_from(LaboratoryRecord))).scalar()
            check("19. no fabricated experiment data (laboratory tables empty "
                  "before and after)", le == 0 and lr == 0, f"exp={le} rec={lr}")

            # --- 20. Existing event types remain functional ------------------------
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "EXTRA_LECTURE", "start_date": D_EXTRA_LEC.isoformat(),
                "end_date": D_EXTRA_LEC.isoformat(),
                "subject_id": str(subject_ids["BCS-501"]), "class_type": "L"})
            extra_lec_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None
            if extra_lec_id:
                test_event_ids.append(extra_lec_id)
            async with AsyncSessionLocal() as db:
                extra_lec_count = await count_sessions(
                    db, ClassSession.subject_id == subject_ids["BCS-501"],
                    ClassSession.date == D_EXTRA_LEC, ClassSession.class_type == ClassType.LECTURE,
                    ClassSession.is_extra.is_(True))
            check("20. existing event types remain functional (admin EXTRA_LECTURE "
                  "creates exactly one extra lecture)",
                  r.status_code == 201 and extra_lec_count == 1,
                  f"got {r.status_code} extras={extra_lec_count}")

            # --- 21. Phase 8.2 behavior intact --------------------------------------
            async with AsyncSessionLocal() as db:
                s821 = (await practical_sessions(db, subject_ids["BCS-553"], date(2026, 8, 14)))[0]
            r = await client.put("/api/v1/laboratory/BCS-553/mid-sem", headers=temp_headers,
                                 json={"class_session_id": str(s821.id)})
            check("21a. Phase 8.2 mid-sem endpoint remains admin-only (student PUT -> 403)",
                  r.status_code == 403, f"got {r.status_code}")
            r = await client.put("/api/v1/laboratory/BCS-553/mid-sem", headers=admin_headers,
                                 json={"class_session_id": str(s821.id)})
            ok_put = r.status_code == 200 and r.json()["session_id"] == str(s821.id)
            r_sum = await client.get("/api/v1/attendance/summary/BCS-553", headers=admin_headers)
            # health is null when nothing is recorded for the subject — that is
            # the canonical recorded-only semantics, so None is a valid value.
            ok_sum = r_sum.status_code == 200 \
                and r_sum.json()["mid_sem_session_id"] == str(s821.id) \
                and r_sum.json()["mid_sem_session_date"] == s821.date.isoformat() \
                and r_sum.json()["health"] in (None, "HEALTHY", "WATCH", "AT_RISK", "CRITICAL")
            r = await client.delete("/api/v1/laboratory/BCS-553/mid-sem", headers=admin_headers)
            ok_del = r.status_code == 200 and r.json()["designated"] is False
            check("21b. Phase 8.2 admin mid-sem designation + summary fields still work "
                  "(health + mid-sem exposure intact)",
                  ok_put and ok_sum and ok_del, f"put={ok_put} sum={ok_sum} del={ok_del}")

            # --- 22. Baseline restoration (checked after cleanup) ------------------
    finally:
        async with AsyncSessionLocal() as db:
            if test_event_ids:
                await db.execute(delete(AcademicEvent).where(AcademicEvent.id.in_(test_event_ids)))
            if test_record_ids:
                await db.execute(delete(AttendanceRecord).where(AttendanceRecord.id.in_(test_record_ids)))
            if temp_user_id is not None:
                await db.execute(delete(StudentEnrollment).where(StudentEnrollment.user_id == temp_user_id))
                await db.execute(delete(User).where(User.id == temp_user_id))
            # Restore the window to its pre-run snapshot: sessions this verifier
            # created (unattended — its own test records were deleted above) are
            # removed; pre-existing sessions get their exact pre-run
            # cancellation and designation state back. Attended sessions are
            # skipped (the safety rule) — the owner's attended sessions (and
            # the owner's pre-existing extras/designations) are never touched.
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
                pre = pre_window_sessions.get(s.id)
                if pre is None:
                    await db.delete(s)
                    continue
                s.is_cancelled = pre[0]
                s.designation = pre[1]
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

    check("22. database restored to the exact baseline (events/sessions/cancelled/extra/"
          "records/enrollments/subjects/quizzes/users/admins/lab tables/designations)",
          (events_after, sessions_after, cancelled_after, extra_after, records_after,
           enrollments_after, subjects_after, quizzes_after, users_after, admins_after,
           lab_exp_after, lab_rec_after, designated_after)
          == (events_before, sessions_before, cancelled_before, extra_before, records_before,
              enrollments_before, subjects_before, quizzes_before, users_before, admins_before,
              lab_exp_before, lab_rec_before, designated_before),
          f"events {events_before}->{events_after} sessions {sessions_before}->{sessions_after} "
          f"cancelled {cancelled_before}->{cancelled_after} extra {extra_before}->{extra_after} "
          f"records {records_before}->{records_after} enrollments {enrollments_before}->{enrollments_after} "
          f"users {users_before}->{users_after} admins {admins_before}->{admins_after} "
          f"lab_exp {lab_exp_before}->{lab_exp_after} lab_rec {lab_rec_before}->{lab_rec_after} "
          f"designated {designated_before}->{designated_after}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\nPhase 9.1 verification: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
