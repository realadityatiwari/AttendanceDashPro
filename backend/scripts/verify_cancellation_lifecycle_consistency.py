"""
Cancellation lifecycle consistency verification (Phase 12C bugfix regression).

Guards the FULL cancellation state lifecycle on canonical class_sessions:

    active CLASS_CANCELLED matching a scheduled occurrence
        -> ClassSession.is_cancelled = True
    no active matching cancellation event (deactivated / re-deactivated /
        moved away)
        -> is_cancelled = False (original attendance state restored)

and the ONE canonical attendance-applicability rule: a cancelled occurrence
contributes NOTHING to any denominator/numerator/count while its attendance
records remain byte-preserved; restoration returns it to every applicable
count automatically.

Core regression locked here: deactivation reconciliation runs EVEN when the
event is already inactive ("event removed" is never "nothing to do"), so a
stale-cancelled session is repaired by removing its source event again.
(Live defect 2026-08-22: stale server code left recorded BCS-058 lectures
cancelled after their events were deactivated.)

Runs against the real api_router + real database (httpx ASGITransport, JWTs,
temp students created/removed by captured IDs) plus rollback-level unit checks
of the eligibility-consumed counting pipeline. Owner attendance records are
never touched; all artifacts cleaned by captured IDs; exact baseline proof.

Usage:
    python scripts/verify_cancellation_lifecycle_consistency.py
"""
import asyncio
import sys
import uuid
from datetime import date
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
from app.engines.practical_occurrence import collapse_count_rows

# Fixture dates: clean past BCS-502 LECTURE days (no active events touch
# BCS-502 on them; owner records exist on each — preserved untouched).
D_A, D_B, D_C, D_D, D_E, D_F = (date(2026, 7, 22), date(2026, 7, 24),
                                date(2026, 7, 28), date(2026, 7, 29),
                                date(2026, 7, 31), date(2026, 8, 4))
D_G, D_H, D_I = date(2026, 8, 7), date(2026, 8, 12), date(2026, 8, 14)
WINDOW_START, WINDOW_END = D_A, D_I
AS_OF = "2026-12-31"
HIST_FROM, HIST_TO = "2026-07-15", "2026-08-31"

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


async def counts(db):
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
        out[label] = (await db.execute(stmt)).scalar()
    return out


async def sess(db, sid):
    return (await db.execute(select(ClassSession).where(ClassSession.id == sid))).scalars().one()


async def fps(db, sid):
    rows = (await db.execute(select(AttendanceRecord).where(
        AttendanceRecord.class_session_id == sid))).scalars().all()
    return {(r.user_id, r.status, r.created_at) for r in rows}


async def main() -> int:
    async with AsyncSessionLocal() as db:
        base0 = await counts(db)
        alembic0 = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar()

        section = (await db.execute(select(Section))).scalars().first()
        bcs502 = (await db.execute(select(Subject).where(Subject.code == "BCS-502"))).scalars().one()

        async def by_date(d):
            return (await db.execute(select(ClassSession).where(
                ClassSession.subject_id == bcs502.id,
                ClassSession.date == d,
                ClassSession.class_type == ClassType.LECTURE,
                ClassSession.is_extra.is_(False),
            ))).scalars().one()

        S = {k: await by_date(d) for k, d in
             {"a": D_A, "b": D_B, "c": D_C, "d": D_D, "e": D_E,
              "f": D_F, "g": D_G, "h": D_H, "i": D_I}.items()}
        check("0a. nine fixture lectures resolve (all recorded, none cancelled)",
              all(s.is_cancelled is False for s in S.values()),
              f"{ {k: s.is_cancelled for k, s in S.items()} }")

        window_rows = (await db.execute(select(ClassSession).where(
            ClassSession.date >= WINDOW_START, ClassSession.date <= WINDOW_END))).scalars().all()
        window_pre = {s.id: s.is_cancelled for s in window_rows}
        date_counts_pre = {}
        for d in (D_A, D_B, D_C, D_D, D_E, D_F, D_G, D_H, D_I):
            date_counts_pre[d] = len((await db.execute(select(ClassSession).where(
                ClassSession.date == d))).scalars().all())
        cancelled_ids_before = set((await db.execute(
            select(ClassSession.id).where(ClassSession.is_cancelled.is_(True)))).scalars().all())

        fp_owner = {k: await fps(db, s.id) for k, s in S.items()}
        check("0b. every fixture session holds pre-existing (owner) attendance",
              all(len(v) >= 1 for v in fp_owner.values()))

        t1 = User(roll_number="ECL_TMP1", name="ECL Temp One",
                  role=UserRole.STUDENT, section_id=section.id if section else None)
        t2 = User(roll_number="ECL_TMP2", name="ECL Temp Two",
                  role=UserRole.STUDENT, section_id=section.id if section else None)
        db.add(t1); db.add(t2)
        await db.flush()
        tmp1_id, tmp2_id = t1.id, t2.id
        await db.commit()

    h1 = {"Authorization": f"Bearer {create_access_token(str(tmp1_id), 'ECL_TMP1')}"}
    h2 = {"Authorization": f"Bearer {create_access_token(str(tmp2_id), 'ECL_TMP2')}"}
    ev_ids, rec_ids = [], []

    transport = httpx.ASGITransport(app=app)

    async def summary(c):
        return (await c.get(f"/api/v1/attendance/summary/BCS-502?as_of_date={AS_OF}",
                            headers=h1)).json()

    async def hist(c, status=None):
        url = (f"/api/v1/attendance/history?subject_code=BCS-502"
               f"&date_from={HIST_FROM}&date_to={HIST_TO}")
        if status:
            url += f"&status={status}"
        return (await c.get(url, headers=h1)).json()

    async def dash(c):
        return (await c.get("/api/v1/dashboard/summary", headers=h1)).json()["overall"]

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            # ---- security / isolation --------------------------------------
            r = await c.post("/api/v1/attendance", headers=h2,
                             json={"class_session_id": str(S["a"].id), "status": "Attended"})
            check("1. unenrolled student attendance mutation -> 403", r.status_code == 403,
                  f"got {r.status_code}")
            r = await c.post("/api/v1/events", headers=h2, json={
                "event_type": "CLASS_CANCELLED", "start_date": D_G.isoformat(),
                "end_date": D_G.isoformat(), "subject_id": str(bcs502.id), "class_type": "L"})
            check("2. unenrolled student event mutation -> 403", r.status_code == 403,
                  f"got {r.status_code}")

            # ---- enrollment + six ATTENDED marks + one MISSED mark ----------
            async with AsyncSessionLocal() as db:
                db.add(StudentEnrollment(user_id=tmp1_id, subject_id=bcs502.id))
                await db.commit()
            for k, st in [("a", "Attended"), ("b", "Attended"), ("c", "Attended"),
                          ("d", "Attended"), ("e", "Attended"), ("f", "Attended"),
                          ("i", "Missed")]:
                r = await c.post("/api/v1/attendance", headers=h1, json={
                    "class_session_id": str(S[k].id), "status": st})
                ok = r.status_code == 200
                if ok:
                    rec_ids.append(uuid.UUID(r.json()["id"]))
                check(f"3{chr(96+ord(k)-97)}. mark {k} ({st}) via canonical path -> 200", ok,
                      f"got {r.status_code}")

            s0 = await summary(c)
            X = s0["lecture"]["total"]
            check("4. baseline summary: total=X attended=6 missed=1 pct=6/7",
                  s0["lecture"]["attended"] == 6 and s0["lecture"]["missed"] == 1
                  and abs((s0.get("current_avg_pct") or 0) - round(6 / 7 * 100, 1)) < 0.06
                  and X > 10,
                  f"X={X} {s0['lecture']} pct={s0.get('current_avg_pct')}")
            h0 = await hist(c)
            check("5. baseline history summary matches (cancelled=0)",
                  h0["summary"]["attended"] == 6 and h0["summary"]["missed"] == 1
                  and h0["summary"]["cancelled"] == 0, f"{h0['summary']}")
            o0 = await dash(c)
            check("6. baseline dashboard overall: attended=6 missed=1 recorded=7 "
                  "(enrollment-scoped)",
                  o0["attended"] == 6 and o0["recorded"] == 7,
                  f"{o0}")
            n0 = (await c.get("/api/v1/notifications", headers=h1)).json()
            check("7. notifications read OK before lifecycle", "unread_count" in n0,
                  f"keys={list(n0)[:5]}")

            # ================= LEG A: unmarked session g ====================
            r = await c.post("/api/v1/events", headers=h1, json={
                "event_type": "CLASS_CANCELLED", "start_date": D_G.isoformat(),
                "end_date": D_G.isoformat(), "subject_id": str(bcs502.id), "class_type": "L"})
            check("8. cancel unmarked g -> 201", r.status_code == 201, f"{r.status_code}")
            ev_g = uuid.UUID(r.json()["id"]); ev_ids.append(ev_g)

            async with AsyncSessionLocal() as db:
                g_now = await sess(db, S["g"].id)
                n_dg = len((await db.execute(select(ClassSession).where(
                    ClassSession.date == D_G))).scalars().all())
            daily = (await c.get(f"/api/v1/attendance/daily/{D_G.isoformat()}",
                                 headers=h1)).json()["sessions"]
            g_row = next(s for s in daily if s["id"] == str(S["g"].id))
            hi = next(x for x in (await hist(c))["items"] if x["id"] == str(S["g"].id))
            hp = (await hist(c, "Pending"))["items"]
            sa = await summary(c)
            oa = await dash(c)
            check("9. g cancelled: DB true, Track Cancelled, History Cancelled, "
                  "excluded from Pending filter",
                  g_now.is_cancelled is True and g_row["is_cancelled"] is True
                  and hi["is_cancelled"] is True
                  and all(x["id"] != str(S["g"].id) for x in hp),
                  f"db={g_now.is_cancelled} track={g_row['is_cancelled']}")
            check("10. applicable denominator drops exactly -1 (att/miss unchanged): "
                  f"{X} -> {sa['lecture']['total']}",
                  sa["lecture"]["total"] == X - 1 and sa["lecture"]["attended"] == 6
                  and sa["lecture"]["missed"] == 1,
                  f"{sa['lecture']}")
            check("11. dashboard consistent: pending -1, att/miss/rec unchanged",
                  oa["pending"] == o0["pending"] - 1 and oa["recorded"] == 7
                  and oa["attended"] == 6, f"{oa}")

            # idempotency of repeated synchronization
            async with AsyncSessionLocal() as db:
                evt = (await db.execute(select(AcademicEvent).where(
                    AcademicEvent.id == ev_g))).scalars().one()
                n1 = len((await db.execute(select(ClassSession).where(
                    ClassSession.date == D_G))).scalars().all())
                await EventSessionSynchronizer(db).sync_event(evt)
                await db.commit()
                n2 = len((await db.execute(select(ClassSession).where(
                    ClassSession.date == D_G))).scalars().all())
                still = (await sess(db, S["g"].id)).is_cancelled
                await EventSessionSynchronizer(db).sync_event(evt)
                await db.commit()
                n3 = len((await db.execute(select(ClassSession).where(
                    ClassSession.date == D_G))).scalars().all())
            check("12. repeated synchronization idempotent (count/state stable)",
                  n1 == n2 == n3 and still is True, f"{n1}/{n2}/{n3} cancelled={still}")

            # deactivation restores
            r = await c.delete(f"/api/v1/events/{ev_g}", headers=h1)
            sd = await summary(c)
            od = await dash(c)
            hd = await hist(c)
            async with AsyncSessionLocal() as db:
                g_restored = (await sess(db, S["g"].id)).is_cancelled
            check("13. deactivate -> g restored Pending everywhere; numbers back to baseline",
                  r.status_code == 200 and g_restored is False
                  and sd["lecture"]["total"] == X
                  and next(x for x in hd["items"] if x["id"] == str(S["g"].id))["is_cancelled"] is False
                  and od["pending"] == o0["pending"],
                  f"restored={g_restored} total={sd['lecture']['total']}")

            # CORE REGRESSION: already-inactive event re-deletion must reconcile
            async with AsyncSessionLocal() as db:
                await db.execute(text(
                    "UPDATE class_sessions SET is_cancelled = true WHERE id = :sid"
                ).bindparams(sid=S["g"].id))
                await db.commit()
            stale = (await c.get(f"/api/v1/attendance/daily/{D_G.isoformat()}",
                                 headers=h1)).json()["sessions"]
            stale_g = next(s for s in stale if s["id"] == str(S["g"].id))
            r = await c.delete(f"/api/v1/events/{ev_g}", headers=h1)  # already inactive!
            async with AsyncSessionLocal() as db:
                healed = (await sess(db, S["g"].id)).is_cancelled
            check("14. CORE: stale-cancelled session self-heals when the ALREADY-"
                  "inactive source event is removed again (reconciliation always runs)",
                  stale_g["is_cancelled"] is True and r.status_code == 200 and healed is False,
                  f"stale={stale_g['is_cancelled']} status={r.status_code} healed={healed}")

            # ================= LEG B: MISSED session i ======================
            r = await c.post("/api/v1/events", headers=h1, json={
                "event_type": "CLASS_CANCELLED", "start_date": D_I.isoformat(),
                "end_date": D_I.isoformat(), "subject_id": str(bcs502.id), "class_type": "L"})
            ev_i = uuid.UUID(r.json()["id"]); ev_ids.append(ev_i)
            sb = await summary(c)
            ob = await dash(c)
            hb = await hist(c)
            hm = await hist(c, "Missed")
            hc_ = await hist(c, "Cancelled")
            check("15. MISSED session cancelled: absence excluded from math "
                  f"(missed 1->0, total {X}->{sb['lecture']['total']}, recorded 7->6) "
                  "while record preserved",
                  r.status_code == 201 and sb["lecture"]["total"] == X - 1
                  and sb["lecture"]["missed"] == 0 and sb["lecture"]["attended"] == 6
                  and ob["recorded"] == 6 and ob["attended"] == 6
                  and all(x["id"] != str(S["i"].id) for x in hm["items"])
                  and any(x["id"] == str(S["i"].id) for x in hc_["items"]),
                  f"{sb['lecture']} dash={ob}")
            r = await c.delete(f"/api/v1/events/{ev_i}", headers=h1)
            sc = await summary(c)
            oc = await dash(c)
            async with AsyncSessionLocal() as db:
                i_state = (await sess(db, S["i"].id)).is_cancelled
                i_fp = await fps(db, S["i"].id)
            tmp_i_fp = {fp for fp in i_fp if fp[0] == tmp1_id}
            check("16. deactivate -> MISSED restored exactly (state + own record intact); "
                  "numbers back to baseline",
                  r.status_code == 200 and i_state is False
                  and sc["lecture"]["missed"] == 1 and sc["lecture"]["total"] == X
                  and oc["recorded"] == 7
                  and len(tmp_i_fp) == 1 and next(iter(tmp_i_fp))[1] == AttendanceStatus.MISSED,
                  f"{sc['lecture']} dash={oc}")

            # ================= LEG C: multi-session range ===================
            r = await c.post("/api/v1/events", headers=h1, json={
                "event_type": "CLASS_CANCELLED", "start_date": D_B.isoformat(),
                "end_date": D_C.isoformat(), "subject_id": str(bcs502.id), "class_type": "L"})
            ev_bc = uuid.UUID(r.json()["id"]); ev_ids.append(ev_bc)
            se = await summary(c)
            async with AsyncSessionLocal() as db:
                b_c = (await sess(db, S["b"].id)).is_cancelled
                c_c = (await sess(db, S["c"].id)).is_cancelled
                a_ok = (await sess(db, S["a"].id)).is_cancelled
            check("17. range event cancels BOTH attended occurrences simultaneously; "
                  "sibling untouched; denominator -2",
                  r.status_code == 201 and b_c and c_c and not a_ok
                  and se["lecture"]["total"] == X - 2 and se["lecture"]["attended"] == 4
                  and se["lecture"]["missed"] == 1,
                  f"b={b_c} c={c_c} a={a_ok} {se['lecture']}")
            r = await c.delete(f"/api/v1/events/{ev_bc}", headers=h1)
            sf = await summary(c)
            async with AsyncSessionLocal() as db:
                b_r = (await sess(db, S["b"].id)).is_cancelled
                c_r = (await sess(db, S["c"].id)).is_cancelled
            check("18. deactivate -> both restored (ATTENDED states back); totals back to X",
                  r.status_code == 200 and not b_r and not c_r
                  and sf["lecture"]["total"] == X and sf["lecture"]["attended"] == 6
                  and sf["lecture"]["missed"] == 1, f"{sf['lecture']}")

            # ============ LEG D: PATCH move between recorded sessions =======
            r = await c.post("/api/v1/events", headers=h1, json={
                "event_type": "CLASS_CANCELLED", "start_date": D_D.isoformat(),
                "end_date": D_D.isoformat(), "subject_id": str(bcs502.id), "class_type": "L"})
            ev_d = uuid.UUID(r.json()["id"]); ev_ids.append(ev_d)
            sg = await summary(c)
            r = await c.patch(f"/api/v1/events/{ev_d}", headers=h1, json={
                "start_date": D_E.isoformat(), "end_date": D_E.isoformat()})
            sh = await summary(c)
            dd = (await c.get(f"/api/v1/attendance/daily/{D_D.isoformat()}",
                              headers=h1)).json()["sessions"]
            ee = (await c.get(f"/api/v1/attendance/daily/{D_E.isoformat()}",
                              headers=h1)).json()["sessions"]
            d_row = next(s for s in dd if s["id"] == str(S["d"].id))
            e_row = next(s for s in ee if s["id"] == str(S["e"].id))
            check("19. PATCH move reconciles both directions between RECORDED "
                  "sessions (old Attended restored, new Attended cancelled)",
                  r.status_code == 200 and d_row["is_cancelled"] is False
                  and d_row["status"] == "Attended"
                  and e_row["is_cancelled"] is True
                  and sg["lecture"]["total"] == X - 1 and sg["lecture"]["attended"] == 5
                  and sh["lecture"]["total"] == X - 1 and sh["lecture"]["attended"] == 5,
                  f"d={d_row['is_cancelled']}/{d_row['status']} e={e_row['is_cancelled']}")
            r = await c.delete(f"/api/v1/events/{ev_d}", headers=h1)
            si = await summary(c)
            check("20. delete move-event -> both original; full restoration",
                  r.status_code == 200 and si["lecture"]["total"] == X
                  and si["lecture"]["attended"] == 6 and si["lecture"]["missed"] == 1,
                  f"{si['lecture']}")

            # ============ LEG E: reactivate cycle on persisted row ==========
            r = await c.patch(f"/api/v1/events/{ev_g}", headers=h1, json={"active": True})
            sj = await summary(c)
            async with AsyncSessionLocal() as db:
                g_re = (await sess(db, S["g"].id)).is_cancelled
            r2 = await c.patch(f"/api/v1/events/{ev_g}", headers=h1, json={"active": False})
            sk = await summary(c)
            async with AsyncSessionLocal() as db:
                g_rd = (await sess(db, S["g"].id)).is_cancelled
            check("21. active->inactive->active->inactive cycle converges "
                  "(reactivation cancels again, second deactivation restores)",
                  r.status_code == 200 and r2.status_code == 200 and g_re is True
                  and g_rd is False and sj["lecture"]["total"] == X - 1
                  and sk["lecture"]["total"] == X,
                  f"re={g_re} rd={g_rd}")

            nk = (await c.get("/api/v1/notifications", headers=h1)).json()
            check("22. notifications stable across lifecycle (no cancellation-derived growth)",
                  isinstance(nk.get("unread_count"), int)
                  and nk.get("unread_count") == n0.get("unread_count"),
                  f"{n0.get('unread_count')}->{nk.get('unread_count')}")

            # ---- eligibility-consumed counting core (unit, rollback-free) ---
            rows = [
                {"class_type": ClassType.LECTURE, "status": None, "date": D_A,
                 "is_cancelled": True, "start_time": None, "end_time": None},
                {"class_type": ClassType.LECTURE, "status": AttendanceStatus.MISSED,
                 "date": D_B, "is_cancelled": True, "start_time": None, "end_time": None},
                {"class_type": ClassType.TUTORIAL, "status": AttendanceStatus.ATTENDED,
                 "date": D_C, "is_cancelled": True, "start_time": None, "end_time": None},
                {"class_type": ClassType.PRACTICAL, "status": None, "date": D_D,
                 "is_cancelled": True, "start_time": None, "end_time": None},
                {"class_type": ClassType.PRACTICAL, "status": AttendanceStatus.ATTENDED,
                 "date": D_E, "is_cancelled": True, "start_time": None, "end_time": None},
                {"class_type": ClassType.LECTURE, "status": AttendanceStatus.ATTENDED,
                 "date": D_F, "is_cancelled": False, "start_time": None, "end_time": None},
            ]
            out = collapse_count_rows([dict(r) | {"subject_id": "x"} for r in rows],
                                      include_subject=True)
            kept = [(str(ct), st) for _, ct, st in out]
            check("23. canonical applicability rule (the function eligibility windows, "
                  "subjects and history summaries consume): cancelled theory never "
                  "applicable regardless of record; frozen practical rules preserved",
                  ("ClassType.LECTURE", None) not in kept
                  and ("ClassType.LECTURE", AttendanceStatus.MISSED) not in kept
                  and ("ClassType.TUTORIAL", AttendanceStatus.ATTENDED) not in kept
                  and ("ClassType.PRACTICAL", None) not in kept
                  and ("ClassType.PRACTICAL", AttendanceStatus.ATTENDED) in kept
                  and ("ClassType.LECTURE", AttendanceStatus.ATTENDED) in kept,
                  f"{kept}")

    finally:
        # ---- cleanup: only this script's artifacts, by captured ID -------------
        async with AsyncSessionLocal() as db:
            if rec_ids:
                await db.execute(delete(AttendanceRecord).where(
                    AttendanceRecord.id.in_(rec_ids)))
            if ev_ids:
                await db.execute(delete(AcademicEvent).where(AcademicEvent.id.in_(ev_ids)))
            await db.execute(delete(StudentEnrollment).where(
                StudentEnrollment.user_id.in_([tmp1_id, tmp2_id])))
            await db.execute(text(
                "DELETE FROM notifications WHERE user_id = ANY(:uids)"
            ).bindparams(__import__("sqlalchemy").bindparam(
                "uids", value=[tmp1_id, tmp2_id])))
            await db.execute(delete(User).where(User.id.in_([tmp1_id, tmp2_id])))
            drifted = []
            for sid, was in window_pre.items():
                s = (await db.execute(select(ClassSession).where(
                    ClassSession.id == sid))).scalars().first()
                if s is not None and s.is_cancelled != was:
                    s.is_cancelled = was
                    drifted.append(str(sid))
            await db.commit()
            if drifted:
                print(f"cleanup: restored {len(drifted)} drifted window state(s)")

    # ---- final integrity --------------------------------------------------------
    async with AsyncSessionLocal() as db:
        base1 = await counts(db)
        alembic1 = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar()
        cancelled_after = set((await db.execute(
            select(ClassSession.id).where(ClassSession.is_cancelled.is_(True)))).scalars().all())
        fp_ok = True
        for k, s in S.items():
            if await fps(db, s.id) != fp_owner[k]:
                fp_ok = False
        dc_ok = True
        for d, n in date_counts_pre.items():
            m = len((await db.execute(select(ClassSession).where(
                ClassSession.date == d))).scalars().all())
            if m != n:
                dc_ok = False

    check("24. attendance records byte-preserved on every fixture session "
          "(owner + temp fingerprints identical)", fp_ok)
    check("25. no duplicate/stale sessions on any fixture date", dc_ok)
    check("26. global cancelled-set returned to exact pre-run membership",
          cancelled_after == cancelled_ids_before,
          f"added={len(cancelled_after - cancelled_ids_before)} "
          f"removed={len(cancelled_ids_before - cancelled_after)}")
    check("27. database returned to exact baseline (counts) + alembic head unchanged",
          base1 == base0 and alembic1 == alembic0,
          f"before={base0} after={base1} alembic {alembic0}->{alembic1}")

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
