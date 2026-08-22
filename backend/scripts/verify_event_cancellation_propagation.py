"""
Event cancellation propagation verification (bugfix regression).

Guards the canonical invariant: an ACTIVE CLASS_CANCELLED event matching a
scheduled class must propagate through EventSessionSynchronizer so the
canonical class session is cancelled — even when the session already holds an
attendance record (e.g. Absent entered before the cancellation was known).
Track must then present it as Cancelled (never absent), the attendance
mutation endpoint must reject it (409), and every consumer must exclude it
from attendance math. Edit/deactivation restores everything exactly.

Root cause this locks in (2026-08 bugfix): the synchronizer previously skipped
ANY session holding an attendance record, which made CLASS_CANCELLED a silent
no-op precisely for historical classes — the common real-world case.
Day-wide closures / working-Saturday replays (Phase 6.6 checks 5/31) and
LAB_CANCELLED (Phase 9.1 check 18) KEEP their frozen attendance-safety
contracts — re-verified here as explicit boundary guards.

Runs against the real api_router and the real database (httpx ASGITransport,
JWTs minted for two temp students created/removed by captured IDs), plus
rollback-transaction synchronizer checks on REAL sessions. The verifier
toggles the cancellation state of two recorded BCS-502 LECTURE sessions via
the canonical event pipeline and restores the exact pre-run state in cleanup;
owner attendance records are never touched. No browser automation.

Usage:
    python scripts/verify_event_cancellation_propagation.py
"""
import asyncio
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx
from sqlalchemy import delete, func, select, text

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User, Section
from app.models.academic import StudentEnrollment, Subject
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.enums import AttendanceStatus, ClassType, EventType, UserRole
from app.services.event_session_service import EventSessionSynchronizer

# Fixture dates (BCS-502 LECTURE, both recorded, no other active events on them).
D_SOURCE = date(2026, 8, 5)   # primary cancellation target
D_TARGET = date(2026, 8, 11)  # PATCH-move destination
WINDOW_START, WINDOW_END = D_SOURCE, D_TARGET
AS_OF = "2026-12-31"

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


async def count(db, stmt) -> int:
    return (await db.execute(stmt)).scalar()


async def baseline_counts(db) -> dict:
    out = {}
    for label, stmt in [
        ("users", select(func.count()).select_from(User)),
        ("events", select(func.count()).select_from(AcademicEvent)),
        ("sessions", select(func.count()).select_from(ClassSession)),
        ("cancelled", select(func.count()).select_from(ClassSession).where(ClassSession.is_cancelled.is_(True))),
        ("extra", select(func.count()).select_from(ClassSession).where(ClassSession.is_extra.is_(True))),
        ("records", select(func.count()).select_from(AttendanceRecord)),
        ("enrollments", select(func.count()).select_from(StudentEnrollment)),
    ]:
        out[label] = await count(db, stmt)
    return out


async def get_session(db, session_id) -> ClassSession:
    return (await db.execute(
        select(ClassSession).where(ClassSession.id == session_id))).scalars().one()


async def main() -> int:
    async with AsyncSessionLocal() as db:
        counts_before = await baseline_counts(db)
        alembic_before = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar()

        admin_user = (await db.execute(
            select(User).where(User.role == UserRole.ADMIN))).scalars().first()
        section = (await db.execute(select(Section))).scalars().first()
        bcs502 = (await db.execute(
            select(Subject).where(Subject.code == "BCS-502"))).scalars().one()

        src = (await db.execute(select(ClassSession).where(
            ClassSession.subject_id == bcs502.id,
            ClassSession.date == D_SOURCE,
            ClassSession.class_type == ClassType.LECTURE,
            ClassSession.is_extra.is_(False),
        ))).scalars().one()
        tgt = (await db.execute(select(ClassSession).where(
            ClassSession.subject_id == bcs502.id,
            ClassSession.date == D_TARGET,
            ClassSession.class_type == ClassType.LECTURE,
            ClassSession.is_extra.is_(False),
        ))).scalars().one()

        check("0a. fixtures resolve: recorded BCS-502 lectures on 08-05 / 08-11, both active",
              bool(admin_user) and bool(bcs502)
              and src.date == D_SOURCE and tgt.date == D_TARGET
              and src.is_cancelled is False and tgt.is_cancelled is False,
              f"src={src.id}/{src.is_cancelled} tgt={tgt.id}/{tgt.is_cancelled}")

        # Pre-run cancellation state of every window session (defensive restore map).
        window_rows = (await db.execute(select(ClassSession).where(
            ClassSession.date >= WINDOW_START, ClassSession.date <= WINDOW_END))).scalars().all()
        window_pre = {s.id: s.is_cancelled for s in window_rows}
        source_date_count = sum(1 for s in window_rows if s.date == D_SOURCE)

        # Owner record fingerprints on the fixture sessions (never mutated).
        async def fingerprints(session_id):
            rows = (await db.execute(select(AttendanceRecord).where(
                AttendanceRecord.class_session_id == session_id))).scalars().all()
            return {(r.user_id, r.status, r.created_at) for r in rows}

        owner_src_fp = await fingerprints(src.id)
        owner_tgt_fp = await fingerprints(tgt.id)
        check("0b. fixture sessions hold pre-existing (owner) attendance",
              len(owner_src_fp) >= 1 and len(owner_tgt_fp) >= 1,
              f"src={len(owner_src_fp)} tgt={len(owner_tgt_fp)}")

        # Temp students: clean slates, shared section (semester context).
        tmp1 = User(roll_number="ECF_TMP1", name="ECP Temp One",
                    role=UserRole.STUDENT, section_id=section.id if section else None)
        tmp2 = User(roll_number="ECF_TMP2", name="ECP Temp Two",
                    role=UserRole.STUDENT, section_id=section.id if section else None)
        db.add(tmp1)
        db.add(tmp2)
        await db.flush()
        tmp1_id, tmp2_id = tmp1.id, tmp2.id
        await db.commit()

    t1 = {"Authorization": f"Bearer {create_access_token(str(tmp1_id), 'ECF_TMP1')}"}
    t2 = {"Authorization": f"Bearer {create_access_token(str(tmp2_id), 'ECF_TMP2')}"}
    test_event_ids: list[uuid.UUID] = []
    test_record_ids: list[uuid.UUID] = []

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            src_id, tgt_id = str(src.id), str(tgt.id)

            # --- isolation ---------------------------------------------------
            r = await c.post("/api/v1/attendance", headers=t1,
                             json={"class_session_id": src_id, "status": "Missed"})
            check("1. unenrolled temp student mutation -> 403 (user isolation intact)",
                  r.status_code == 403, f"got {r.status_code} {r.text[:120]}")

            async with AsyncSessionLocal() as db:
                db.add(StudentEnrollment(user_id=tmp1_id, subject_id=bcs502.id))
                db.add(StudentEnrollment(user_id=tmp2_id, subject_id=bcs502.id))
                await db.commit()

            # --- stale absence via the canonical mutation path -----------------
            r = await c.post("/api/v1/attendance", headers=t2,
                             json={"class_session_id": src_id, "status": "Missed"})
            ok_mark = r.status_code == 200
            check("2. enrolled temp student marks MISSED -> 200 (canonical path)",
                  ok_mark, f"got {r.status_code} {r.text[:120]}")
            rec_id = uuid.UUID(r.json()["id"]) if ok_mark else None
            if ok_mark:
                test_record_ids.append(rec_id)
            if not ok_mark:
                raise SystemExit("fixture mark failed; aborting before event tests")

            base_sum = (await c.get(
                f"/api/v1/attendance/summary/BCS-502?as_of_date={AS_OF}", headers=t2)).json()
            check("3. baseline summary counts the stale absence "
                  "(lecture missed == 1, total includes the session)",
                  base_sum["lecture"]["missed"] == 1 and base_sum["lecture"]["total"] >= 2,
                  f"{base_sum['lecture']}")

            # --- the bugfix under test -----------------------------------------
            r = await c.post("/api/v1/events", headers=t2, json={
                "event_type": "CLASS_CANCELLED", "start_date": D_SOURCE.isoformat(),
                "end_date": D_SOURCE.isoformat(),
                "subject_id": str(bcs502.id), "class_type": "L"})
            ok_ev = r.status_code == 201
            check("4. student CLASS_CANCELLED BCS-502/L 08-05 -> 201",
                  ok_ev, f"got {r.status_code} {r.text[:160]}")
            ev_id = uuid.UUID(r.json()["id"]) if ok_ev else None
            if ok_ev:
                test_event_ids.append(ev_id)

            async with AsyncSessionLocal() as db:
                sess = await get_session(db, src.id)
                date_total = len((await db.execute(select(ClassSession).where(
                    ClassSession.date == D_SOURCE))).scalars().all())
                date_cancelled = len((await db.execute(select(ClassSession).where(
                    ClassSession.date == D_SOURCE,
                    ClassSession.is_cancelled.is_(True)))).scalars().all())

                check("5. RECORDED session cancelled by the active matching event",
                      sess.is_cancelled is True, f"is_cancelled={sess.is_cancelled}")
                check("6. exactly one occurrence cancelled; session count unchanged "
                      "(no duplicates created)",
                      date_cancelled == 1 and date_total == source_date_count,
                      f"date_total={date_total} (pre={source_date_count}) cancelled={date_cancelled}")

                siblings_ok = all(
                    s.is_cancelled == window_pre[s.id]
                    for s in (await db.execute(select(ClassSession).where(
                        ClassSession.date == D_SOURCE))).scalars().all()
                    if s.id != src.id)
                check("7. unrelated same-date sessions untouched (subject/class-type isolation)",
                      siblings_ok)
                check("8. unrelated date untouched (08-11 still active)",
                      (await get_session(db, tgt.id)).is_cancelled is False)

                evt = (await db.execute(select(AcademicEvent).where(
                    AcademicEvent.id == ev_id))).scalars().one()
                n1 = len((await db.execute(select(ClassSession).where(
                    ClassSession.date == D_SOURCE))).scalars().all())
                await EventSessionSynchronizer(db).sync_event(evt)
                await db.commit()
                n2 = len((await db.execute(select(ClassSession).where(
                    ClassSession.date == D_SOURCE))).scalars().all())
                await EventSessionSynchronizer(db).sync_event(evt)
                await db.commit()
                n3 = len((await db.execute(select(ClassSession).where(
                    ClassSession.date == D_SOURCE))).scalars().all())
                still = (await get_session(db, src.id)).is_cancelled
                check("9. repeated synchronization idempotent (count stable, state stable)",
                      n1 == n2 == n3 and still is True,
                      f"n {n1}->{n2}->{n3} cancelled={still}")

            # --- Track/API surfaces ---------------------------------------------
            daily = (await c.get(f"/api/v1/attendance/daily/{D_SOURCE.isoformat()}",
                                 headers=t2)).json()["sessions"]
            mine = next(s for s in daily if s["id"] == str(src.id))
            check("10. Track daily exposes the session as Cancelled (is_cancelled=true)",
                  mine["is_cancelled"] is True, f"{mine}")

            r = await c.post("/api/v1/attendance", headers=t2,
                             json={"class_session_id": src_id, "status": "Attended"})
            check("11. attendance mutation on the cancelled session -> 409",
                  r.status_code == 409, f"got {r.status_code}")

            after_sum = (await c.get(
                f"/api/v1/attendance/summary/BCS-502?as_of_date={AS_OF}", headers=t2)).json()
            check("12. subject summary excludes the cancelled occurrence from math "
                  "(lecture total -1 AND missed -1)",
                  after_sum["lecture"]["total"] == base_sum["lecture"]["total"] - 1
                  and after_sum["lecture"]["missed"] == base_sum["lecture"]["missed"] - 1,
                  f"base={base_sum['lecture']} now={after_sum['lecture']}")

            rng = (f"date_from={(D_SOURCE - timedelta(days=1)).isoformat()}"
                   f"&date_to={(D_TARGET + timedelta(days=1)).isoformat()}")
            h = (await c.get(f"/api/v1/attendance/history?{rng}", headers=t2)).json()
            item = next(i for i in h["items"] if i["id"] == str(src.id))
            check("13. history row presented as Cancelled (is_cancelled wins over the stale mark)",
                  item["is_cancelled"] is True, f"{item}")
            hm = (await c.get(f"/api/v1/attendance/history?{rng}&status=Missed", headers=t2)).json()
            hc = (await c.get(f"/api/v1/attendance/history?{rng}&status=Cancelled", headers=t2)).json()
            check("14. history filters: Missed excludes it, Cancelled includes it",
                  all(i["id"] != str(src.id) for i in hm["items"])
                  and any(i["id"] == str(src.id) for i in hc["items"]),
                  f"missed={hm['summary']} cancelled={hc['summary']}")

            # --- edit semantics: moving the event reconciles BOTH dates ----------
            r = await c.patch(f"/api/v1/events/{ev_id}", headers=t2,
                              json={"start_date": D_TARGET.isoformat(),
                                    "end_date": D_TARGET.isoformat()})
            check("15. PATCH moves the cancellation 08-05 -> 08-11 -> 200",
                  r.status_code == 200, f"got {r.status_code} {r.text[:160]}")
            async with AsyncSessionLocal() as db:
                s_now = await get_session(db, src.id)
                t_now = await get_session(db, tgt.id)
                check("16. move reconciles both directions: old recorded session "
                      "restored, new recorded session cancelled",
                      s_now.is_cancelled is False and t_now.is_cancelled is True,
                      f"src={s_now.is_cancelled} tgt={t_now.is_cancelled}")

            # --- deactivation reversal -------------------------------------------
            r = await c.delete(f"/api/v1/events/{ev_id}", headers=t2)
            check("17. DELETE deactivates -> 200", r.status_code == 200,
                  f"got {r.status_code}")
            async with AsyncSessionLocal() as db:
                s_now = await get_session(db, src.id)
                t_now = await get_session(db, tgt.id)
                rec_after = (await db.execute(select(AttendanceRecord).where(
                    AttendanceRecord.id == rec_id))).scalars().one()
                check("18. reversal exact: both sessions active again; stale record "
                      "preserved (never deleted)",
                      s_now.is_cancelled is False and t_now.is_cancelled is False
                      and rec_after.status == AttendanceStatus.MISSED,
                      f"src={s_now.is_cancelled} tgt={t_now.is_cancelled}")
            restored_sum = (await c.get(
                f"/api/v1/attendance/summary/BCS-502?as_of_date={AS_OF}", headers=t2)).json()
            check("19. summary returns to exact pre-test values after reversal",
                  restored_sum["lecture"]["total"] == base_sum["lecture"]["total"]
                  and restored_sum["lecture"]["missed"] == base_sum["lecture"]["missed"],
                  f"base={base_sum['lecture']} now={restored_sum['lecture']}")
            r = await c.post("/api/v1/attendance", headers=t2,
                             json={"class_session_id": tgt_id, "status": "Missed"})
            check("20. mutation allowed again on a restored session -> 200",
                  r.status_code == 200, f"got {r.status_code}")
            if r.status_code == 200:
                test_record_ids.append(uuid.UUID(r.json()["id"]))

        # --- frozen boundaries (rollback transactions on REAL sessions) ----------
        async with AsyncSessionLocal() as db:
            probe = (await db.execute(
                select(ClassSession).where(
                    ClassSession.class_type == ClassType.LECTURE,
                    ClassSession.timetable_entry_id.is_not(None),
                    ClassSession.date > date.today(),
                    ClassSession.is_cancelled.is_(False),
                    ~ClassSession.id.in_(select(AttendanceRecord.class_session_id)),
                ).order_by(ClassSession.date).limit(1))).scalars().one()
            db.add(AttendanceRecord(user_id=tmp2_id, class_session_id=probe.id,
                                    status=AttendanceStatus.MISSED))
            closure = AcademicEvent(event_type=EventType.PUBLIC_HOLIDAY,
                                    start_date=probe.date, end_date=probe.date, active=True)
            db.add(closure)
            await EventSessionSynchronizer(db).sync_event(closure)
            await db.flush()
            check("21. frozen boundary: day-wide closure does NOT cancel a RECORDED "
                  "session (Phase 6.6 contract preserved)",
                  (await get_session(db, probe.id)).is_cancelled is False)
            await db.rollback()

        async with AsyncSessionLocal() as db:
            probe = (await db.execute(
                select(ClassSession).where(
                    ClassSession.class_type == ClassType.PRACTICAL,
                    ClassSession.timetable_entry_id.is_not(None),
                    ClassSession.date > date.today(),
                    ClassSession.is_cancelled.is_(False),
                    ~ClassSession.id.in_(select(AttendanceRecord.class_session_id)),
                ).order_by(ClassSession.date).limit(1))).scalars().one()
            db.add(AttendanceRecord(user_id=tmp2_id, class_session_id=probe.id,
                                    status=AttendanceStatus.MISSED))
            labcan = AcademicEvent(event_type=EventType.LAB_CANCELLED,
                                   start_date=probe.date, end_date=probe.date,
                                   subject_id=probe.subject_id,
                                   class_type=ClassType.PRACTICAL, active=True)
            db.add(labcan)
            await EventSessionSynchronizer(db).sync_event(labcan)
            await db.flush()
            check("22. frozen boundary: LAB_CANCELLED does NOT cancel a RECORDED "
                  "practical (Phase 9.1 contract preserved)",
                  (await get_session(db, probe.id)).is_cancelled is False)
            await db.rollback()
            print("rollback: boundary-check transactions discarded")
    finally:
        # ---- cleanup: ONLY this script's artifacts, by captured ID --------------
        async with AsyncSessionLocal() as db:
            if test_record_ids:
                await db.execute(delete(AttendanceRecord).where(
                    AttendanceRecord.id.in_(test_record_ids)))
            if test_event_ids:
                await db.execute(delete(AcademicEvent).where(
                    AcademicEvent.id.in_(test_event_ids)))
            await db.execute(delete(StudentEnrollment).where(
                StudentEnrollment.user_id.in_([tmp1_id, tmp2_id])))
            await db.execute(delete(User).where(User.id.in_([tmp1_id, tmp2_id])))
            drifted = []
            for sid, was_cancelled in window_pre.items():
                s = (await db.execute(select(ClassSession).where(
                    ClassSession.id == sid))).scalars().first()
                if s is not None and s.is_cancelled != was_cancelled:
                    s.is_cancelled = was_cancelled
                    drifted.append(str(sid))
            await db.commit()
            if drifted:
                print(f"cleanup: restored {len(drifted)} drifted window session state(s)")

    # ---- final baseline proof -------------------------------------------------
    async with AsyncSessionLocal() as db:
        counts_after = await baseline_counts(db)
        alembic_after = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar()

        async def fp_of(session_id):
            rows = (await db.execute(select(AttendanceRecord).where(
                AttendanceRecord.class_session_id == session_id))).scalars().all()
            return {(r.user_id, r.status, r.created_at) for r in rows}

        check("23. owner attendance records untouched (fingerprints identical)",
              await fp_of(src.id) == owner_src_fp and await fp_of(tgt.id) == owner_tgt_fp)
        check("24. database returned to exact baseline (counts; single alembic head unchanged)",
              counts_after == counts_before and alembic_after == alembic_before,
              f"before={counts_before} after={counts_after} "
              f"alembic {alembic_before}->{alembic_after}")

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
