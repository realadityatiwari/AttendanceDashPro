"""
Phase 24.7-C — Admin Timetable CRUD API verifier.

Proves the Phase 24.7-C endpoint contract via in-process HTTP testing
(ASGITransport) against the LOCAL development DB.

LOCALITY GUARD (hard): forces + asserts DATABASE_URI is the local dev DB.
"""
import asyncio, os, sys, datetime, uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

LOCAL_URI = "postgresql+asyncpg://postgres:postgres@127.0.0.1:55432/attendancedash"
os.environ["DATABASE_URI"] = LOCAL_URI
from app.core.config import settings
_effective = settings.DATABASE_URI
if "127.0.0.1:55432" not in _effective and "localhost:55432" not in _effective:
    print(f"LOCALITY GUARD ABORT ({_effective})"); sys.exit(2)
if "attendancedash" not in _effective:
    print(f"LOCALITY GUARD ABORT: not attendancedash ({_effective})"); sys.exit(2)

from sqlalchemy import delete, func, select, text, update
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.db.session import AsyncSessionLocal
from app.models.user import User, Section, Subsection
from app.models.academic import AcademicSession, Semester, Subject, StudentElectiveChoice
from app.models.admin_scope import AdminScope
from app.models.enums import AdminRole, ClassType, ElectiveSlot, SubjectCategory, UserRole
from app.models.timetable import TimetableEntry
from app.core.security import create_access_token

results = []; _BASELINE = {}; _ACTIVE_SESSION_ID = None

def check(n, ok, d=""): results.append((n, ok)); print(f"{'PASS' if ok else 'FAIL'}  {n}" + (f"  -- {d}" if not ok else ""))

async def counts(db):
    out = {}
    for t in ["users", "admin_scopes", "academic_sessions", "semesters",
              "sections", "subsections", "subjects", "timetable_entries"]:
        out[t] = (await db.execute(select(func.count()).select_from(text(f'"{t}"')))).scalar_one()
    return out

async def main() -> int:
    global _BASELINE, _ACTIVE_SESSION_ID
    print("=" * 64)
    print("Phase 24.7-C — Admin Timetable CRUD API")
    print(f"Locality guard: {settings.DATABASE_URI}")
    print("=" * 64)
    fx = {}
    try:
        async with AsyncSessionLocal() as db:
            admin = (await db.execute(select(User).where(User.role == UserRole.ADMIN))).scalars().first()
            if admin is None: check("0. admin user", False); return 1
            fx["admin"] = admin.id
            active = (await db.execute(select(AcademicSession).where(AcademicSession.is_active.is_(True)))).scalars().first()
            if active is None: check("0. active session", False); return 1
            _ACTIVE_SESSION_ID = active.id
            _BASELINE = await counts(db)
            print(f"baseline: {_BASELINE}")
            # Fixtures
            fs = AcademicSession(name="REVIEW 24.7C", start_date=datetime.date(2028,1,1), end_date=datetime.date(2028,12,31), is_active=False)
            db.add(fs); await db.flush(); fx["session"] = fs.id
            fsem = Semester(name="Review Sem 24.7C", session_id=fs.id, start_date=datetime.date(2028,1,15), end_date=datetime.date(2028,6,30))
            db.add(fsem); await db.flush(); fx["semester"] = fsem.id
            secA = Section(name="REV-CA", program="BTech CSE", semester_id=fsem.id)
            secB = Section(name="REV-CB", program="BTech CSE", semester_id=fsem.id)
            db.add_all([secA, secB]); await db.flush()
            fx["section_a"] = secA.id; fx["section_b"] = secB.id
            subA1 = Subsection(name="REV-CA1", section_id=secA.id)
            db.add(subA1); await db.flush(); fx["subsection_a1"] = subA1.id
            common = Subject(code="REV-CC", name="Rev Common", category=SubjectCategory.THEORY, quiz_applicable=True, attendance_applicable=True, semester_id=fsem.id)
            elecI = Subject(code="REV-CE1", name="Rev Elec-I", category=SubjectCategory.THEORY, elective_slot=ElectiveSlot.ELECTIVE_I, quiz_applicable=True, attendance_applicable=True, semester_id=fsem.id)
            db.add_all([common, elecI]); await db.flush()
            fx["common"] = common.id; fx["elec_i"] = elecI.id
            # Users
            ca = User(roll_number=f"2401290{uuid.uuid4().hex[:6]}", name="Ph247C CLASS_ADMIN", hashed_password="x", section_id=secA.id)
            db.add(ca); await db.flush(); fx["class_admin"] = ca.id
            db.add(AdminScope(user_id=ca.id, role=AdminRole.CLASS_ADMIN, section_id=secA.id))
            ea = User(roll_number=f"2401291{uuid.uuid4().hex[:6]}", name="Ph247C ELECTIVE_ADMIN", hashed_password="x", section_id=secA.id)
            db.add(ea); await db.flush(); fx["elec_admin"] = ea.id
            db.add(AdminScope(user_id=ea.id, role=AdminRole.ELECTIVE_ADMIN, subject_id=elecI.id))
            sa = User(roll_number=f"2401292{uuid.uuid4().hex[:6]}", name="Ph247C SUBSECTION_ADMIN", hashed_password="x", section_id=secA.id)
            db.add(sa); await db.flush(); fx["sub_admin"] = sa.id
            db.add(AdminScope(user_id=sa.id, role=AdminRole.SUBSECTION_ADMIN, subsection_id=subA1.id))
            st = User(roll_number=f"2401293{uuid.uuid4().hex[:6]}", name="Ph247C STUDENT", hashed_password="x", section_id=secA.id)
            db.add(st); await db.flush(); fx["student"] = st.id
            await db.commit()
        # Tokens
        tokens = {}
        async with AsyncSessionLocal() as db:
            for r in ["admin", "class_admin", "elec_admin", "sub_admin", "student"]:
                u = await db.execute(select(User).where(User.id == fx[r])); u = u.scalars().first()
                tokens[r] = create_access_token(subject=str(u.id), roll_number=u.roll_number)
        # === HTTP TESTS ===
        transport = ASGITransport(app=app)
        S = "/api/v1/admin/timetable"
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            # A. unauthenticated -> 401
            r = await c.get(S); check("A1. unauth GET -> 401", r.status_code == 401)
            r = await c.post(S, json={}); check("A2. unauth POST -> 401", r.status_code == 401)
            # B. STUDENT -> 403
            r = await c.get(S, headers={"Authorization": f"Bearer {tokens['student']}"})
            check("B1. STUDENT GET -> 403", r.status_code == 403)
            r = await c.post(S, json={}, headers={"Authorization": f"Bearer {tokens['student']}"})
            check("B2. STUDENT POST -> 403", r.status_code == 403)
            # C. HEAD reads
            h = {"Authorization": f"Bearer {tokens['admin']}"}
            r = await c.get(S, headers=h)
            check("C1. HEAD GET -> 200", r.status_code == 200)
            # D. Create as HEAD
            payload = {"section_id": str(fx["section_a"]), "subject_id": str(fx["common"]),
                       "day_of_week": 0, "start_time": "09:00", "end_time": "10:00", "class_type": "L"}
            r = await c.post(S, json=payload, headers=h)
            check("D1. HEAD create -> 201", r.status_code == 201, str(r.status_code))
            e1 = r.json()["entry"]
            # E. Create duplicate (conflict)
            r = await c.post(S, json=payload, headers=h)
            check("E1. conflict -> 409", r.status_code == 409, str(r.status_code))
            # F. Create adjacent (allowed)
            p2 = payload.copy(); p2["start_time"] = "10:00"; p2["end_time"] = "11:00"
            r = await c.post(S, json=p2, headers=h)
            check("F1. adjacent allowed -> 201", r.status_code == 201, str(r.status_code))
            # G. Get detail
            r = await c.get(f"{S}/{e1['id']}", headers=h)
            check("G1. GET detail -> 200", r.status_code == 200 and r.json()["id"] == e1["id"])
            # H. Update
            r = await c.patch(f"{S}/{e1['id']}", json={"room": "Room 101"}, headers=h)
            check("H1. PATCH room -> 200", r.status_code == 200 and r.json()["entry"]["room"] == "Room 101")
            # I. Deactivate
            r = await c.post(f"{S}/{e1['id']}/deactivate", headers=h)
            check("I1. deactivate -> 200", r.status_code == 200 and r.json()["entry"]["is_active"] is False)
            # J. Reactivate (PATCH is_active)
            r = await c.patch(f"{S}/{e1['id']}", json={"is_active": True}, headers=h)
            check("J1. reactivate -> 200", r.status_code == 200 and r.json()["entry"]["is_active"] is True)
            # K. Duplicate
            r = await c.post(f"{S}/{e1['id']}/duplicate", json={"day_of_week": 1}, headers=h)
            check("K1. duplicate -> 201", r.status_code == 201, str(r.status_code))
            dup = r.json()["entry"]
            check("K2. duplicate day changed", dup["day_of_week"] == 1, str(dup["day_of_week"]))
            # L. CLASS_ADMIN own section create -> allowed
            ch = {"Authorization": f"Bearer {tokens['class_admin']}"}
            p3 = {"section_id": str(fx["section_a"]), "subject_id": str(fx["common"]),
                  "day_of_week": 2, "start_time": "09:00", "end_time": "10:00", "class_type": "L"}
            r = await c.post(S, json=p3, headers=ch)
            check("L1. CLASS_ADMIN own section -> 201", r.status_code == 201, str(r.status_code))
            # L2. CLASS_ADMIN other section -> 403
            p4 = p3.copy(); p4["section_id"] = str(fx["section_b"])
            r = await c.post(S, json=p4, headers=ch)
            check("L2. CLASS_ADMIN other section -> 403", r.status_code == 403, str(r.status_code))
            # M. ELECTIVE_ADMIN create -> 403 (write gate)
            eh = {"Authorization": f"Bearer {tokens['elec_admin']}"}
            r = await c.post(S, json=payload, headers=eh)
            check("M1. ELECTIVE_ADMIN create -> 403", r.status_code == 403, str(r.status_code))
            # N. SUBSECTION_ADMIN create -> 403
            sh = {"Authorization": f"Bearer {tokens['sub_admin']}"}
            r = await c.post(S, json=payload, headers=sh)
            check("N1. SUBSECTION_ADMIN create -> 403", r.status_code == 403, str(r.status_code))
            # O. CLASS_ADMIN list -> own section only
            r = await c.get(S, headers=ch)
            check("O1. CLASS_ADMIN list -> own section", r.status_code == 200)
            own = all(x["section_id"] == str(fx["section_a"]) for x in r.json()["items"])
            check("O2. CLASS_ADMIN only own section entries", own, str([x["section_id"][:6] for x in r.json()["items"]]))
            # P. ELECTIVE_ADMIN list -> own subject only
            r = await c.get(S, headers=eh)
            check("P1. ELECTIVE_ADMIN list -> own subject", r.status_code == 200)
            own_subj = all(x["subject_code"] == "REV-CE1" for x in r.json()["items"])
            check("P2. ELECTIVE_ADMIN only own subject entries", own_subj, str([x["subject_code"] for x in r.json()["items"]]))
            # Q. SUBSECTION_ADMIN list -> own section
            r = await c.get(S, headers=sh)
            check("Q1. SUBSECTION_ADMIN list -> own section", r.status_code == 200)
            # R. List with filters
            r = await c.get(S, params={"section_id": str(fx["section_a"]), "day_of_week": 0}, headers=h)
            check("R1. filtered list day=0", r.status_code == 200 and all(x["day_of_week"] == 0 for x in r.json()["items"]))
            # S. GET nonexistent -> 404
            r = await c.get(f"{S}/{uuid.uuid4()}", headers=h)
            check("S1. GET nonexistent -> 404", r.status_code == 404)
            # T. PATCH nonexistent -> 404
            r = await c.patch(f"{S}/{uuid.uuid4()}", json={"room": "X"}, headers=h)
            check("T1. PATCH nonexistent -> 404", r.status_code == 404)
            # U. Deactivate nonexistent -> 404
            r = await c.post(f"{S}/{uuid.uuid4()}/deactivate", headers=h)
            check("U1. deactivate nonexistent -> 404", r.status_code == 404)
            # W. Duplicate nonexistent -> 404
            r = await c.post(f"{S}/{uuid.uuid4()}/duplicate", json={}, headers=h)
            check("W1. duplicate nonexistent -> 404", r.status_code == 404)
        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.7-C verifier (core): {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1
    finally:
        async with AsyncSessionLocal() as db:
            try:
                if fx.get("session"):
                    await db.execute(delete(TimetableEntry).where(TimetableEntry.section_id.in_([fx.get("section_a"), fx.get("section_b")])))
                    await db.execute(delete(AdminScope).where(AdminScope.user_id.in_([fx.get("class_admin"), fx.get("elec_admin"), fx.get("sub_admin")])))
                    for k in ("class_admin","elec_admin","sub_admin","student"):
                        if fx.get(k): await db.execute(delete(User).where(User.id == fx[k]))
                    await db.execute(delete(Subject).where(Subject.semester_id == fx["semester"]))
                    await db.execute(delete(Subsection).where(Subsection.section_id.in_([fx.get("section_a"), fx.get("section_b")])))
                    await db.execute(delete(Section).where(Section.semester_id == fx["semester"]))
                    await db.execute(delete(Semester).where(Semester.session_id == fx["session"]))
                    await db.execute(delete(AcademicSession).where(AcademicSession.id == fx["session"]))
                if _ACTIVE_SESSION_ID:
                    await db.execute(update(AcademicSession).where(AcademicSession.id == _ACTIVE_SESSION_ID).values(is_active=True))
                await db.commit()
            except Exception as e: print(f"cleanup: {e}"); await db.rollback()

async def post_cleanup():
    async with AsyncSessionLocal() as db:
        after = await counts(db)
        check("Z1. baseline restored", after == _BASELINE, f"before={_BASELINE} after={after}")
        a = (await db.execute(select(AcademicSession).where(AcademicSession.is_active.is_(True)))).scalars().first()
        check("Z2. active session unchanged", a is not None and a.id == _ACTIVE_SESSION_ID)

if __name__ == "__main__":
    async def _run():
        c = await main()
        await post_cleanup()
        p = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.7-C verifier: {p}/{len(results)} PASS")
        return 0 if p == len(results) else 1
    sys.exit(asyncio.run(_run()))