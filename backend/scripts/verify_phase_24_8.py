"""
Phase 24.8 — Quiz Schedule Manager verifier.

Proves the admin quiz schedule management contract end-to-end against the
LOCAL development DB: auth, CRUD, QUIZ_DAY event synchronization, elective
isolation, and data integrity.

Fixture dates use the REAL active semester bounds (2026-07-15..2026-12-31)
so the date-in-semester validation accepts them, and are distinct from the
existing seeded quiz dates (2026-08-24..2026-10-26).

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
from app.models.user import User, Section
from app.models.admin_scope import AdminScope
from app.models.academic import AcademicSession, Semester, Subject, StudentElectiveChoice, StudentEnrollment
from app.models.enums import AdminRole, ElectiveSlot, UserRole
from app.models.quiz import QuizCycle, QuizSchedule, EligibilityPolicy
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession
from app.core.security import create_access_token

results = []; _BASELINE = {}; _ACTIVE_SESSION_ID = None

def check(n, ok, d=""): results.append((n, ok)); print(f"{'PASS' if ok else 'FAIL'}  {n}" + (f"  -- {d}" if not ok else ""))

async def counts(db):
    out = {}
    for t in ["users", "admin_scopes", "academic_sessions", "semesters", "sections",
              "subjects", "quiz_schedules", "academic_events", "class_sessions",
              "attendance_records", "student_elective_choices", "timetable_entries"]:
        out[t] = (await db.execute(select(func.count()).select_from(text(f'"{t}"')))).scalar_one()
    return out

async def main() -> int:
    global _BASELINE, _ACTIVE_SESSION_ID
    print("=" * 64)
    print("Phase 24.8 — Quiz Schedule Manager")
    print(f"Locality guard: {settings.DATABASE_URI}")
    print("=" * 64)
    fx = {}
    try:
        async with AsyncSessionLocal() as db:
            active = (await db.execute(select(AcademicSession).where(AcademicSession.is_active.is_(True)))).scalars().first()
            if active is None: check("0. active session", False); return 1
            _ACTIVE_SESSION_ID = active.id
            admin = (await db.execute(select(User).where(User.role == UserRole.ADMIN))).scalars().first()
            if admin is None: check("0. admin user", False); return 1
            _BASELINE = await counts(db)
            print(f"baseline: {_BASELINE}")

            bcs54 = (await db.execute(select(Subject).where(Subject.code == "BCS-054"))).scalars().first()
            bcs58 = (await db.execute(select(Subject).where(Subject.code == "BCS-058"))).scalars().first()
            bcs501 = (await db.execute(select(Subject).where(Subject.code == "BCS-501"))).scalars().first()
            bcs52 = (await db.execute(select(Subject).where(Subject.code == "BCS-052"))).scalars().first()
            bcs55 = (await db.execute(select(Subject).where(Subject.code == "BCS-055"))).scalars().first()
            if not all([bcs54, bcs58, bcs501, bcs52, bcs55]):
                check("0. real subjects found", False); return 1
            fx["bcs54"] = bcs54.id; fx["bcs58"] = bcs58.id; fx["bcs501"] = bcs501.id
            fx["bcs52"] = bcs52.id; fx["bcs55"] = bcs55.id

            # Fixture quiz cycle (for new schedule creation)
            fcycle = QuizCycle(cycle_number=99, label="Review 24.8 Cycle")
            db.add(fcycle); await db.flush(); fx["cycle"] = fcycle.id
            db.add(EligibilityPolicy(quiz_cycle_id=fcycle.id, lecture_threshold=70.0))
            await db.flush(); fx["policy"] = True

            # Fixture section (in the real active semester) + users
            fsem = (await db.execute(select(Semester).where(Semester.id == bcs501.semester_id))).scalars().first()
            fsec = Section(name="REV-24.8-SEC", program="BTech", semester_id=fsem.id)
            db.add(fsec); await db.flush(); fx["section"] = fsec.id

            classA = User(roll_number=f"2401320{uuid.uuid4().hex[:6]}", name="Ph248 CLASS", hashed_password="x", section_id=fsec.id)
            elecA = User(roll_number=f"2401321{uuid.uuid4().hex[:6]}", name="Ph248 ELECTIVE", hashed_password="x", section_id=fsec.id)
            subA = User(roll_number=f"2401322{uuid.uuid4().hex[:6]}", name="Ph248 SUBSEC", hashed_password="x", section_id=fsec.id)
            stu = User(roll_number=f"2401323{uuid.uuid4().hex[:6]}", name="Ph248 STU", hashed_password="x", section_id=fsec.id)
            stuA = User(roll_number=f"2401324{uuid.uuid4().hex[:6]}", name="StuA 248", hashed_password="x", section_id=fsec.id)
            stuB = User(roll_number=f"2401325{uuid.uuid4().hex[:6]}", name="StuB 248", hashed_password="x", section_id=fsec.id)
            db.add_all([classA, elecA, subA, stu, stuA, stuB]); await db.flush()
            fx["classA"] = classA.id; fx["elecA"] = elecA.id; fx["subA"] = subA.id
            fx["stu"] = stu.id; fx["stuA"] = stuA.id; fx["stuB"] = stuB.id

            db.add_all([
                AdminScope(user_id=classA.id, role=AdminRole.CLASS_ADMIN, section_id=fsec.id),
                AdminScope(user_id=elecA.id, role=AdminRole.ELECTIVE_ADMIN, subject_id=bcs58.id),
            ])
            db.add_all([
                StudentElectiveChoice(user_id=stuA.id, elective_slot=ElectiveSlot.ELECTIVE_I, subject_id=bcs54.id),
                StudentElectiveChoice(user_id=stuA.id, elective_slot=ElectiveSlot.ELECTIVE_II, subject_id=bcs58.id),
                StudentElectiveChoice(user_id=stuB.id, elective_slot=ElectiveSlot.ELECTIVE_I, subject_id=bcs52.id),
                StudentElectiveChoice(user_id=stuB.id, elective_slot=ElectiveSlot.ELECTIVE_II, subject_id=bcs55.id),
            ])
            # Enroll the fixture students so the eligibility endpoint
            # can find them.  Student A gets BCS-058 (concrete DE-II);
            # Student B gets BCS-055 (concrete DE-II) — NOT BCS-058.
            db.add_all([
                StudentEnrollment(user_id=stuA.id, subject_id=bcs58.id, enrollment_type="ELECTIVE"),
                StudentEnrollment(user_id=stuB.id, subject_id=bcs55.id, enrollment_type="ELECTIVE"),
            ])
            await db.commit()

        # In-semester fixture dates (distinct from seeded quiz dates)
        D1 = datetime.date(2026, 11, 10)   # BCS-501 common
        D1b = datetime.date(2026, 11, 11)  # moved date
        D2 = datetime.date(2026, 11, 12)   # BCS-058 elective DE-II
        fx["D1"] = D1; fx["D1b"] = D1b; fx["D2"] = D2

        # ============ HTTP TESTS ============
        transport = ASGITransport(app=app)
        P = "/api/v1/admin/quizzes"
        PC = "/api/v1/admin/quiz-cycles"
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            async def tok(uid):
                u = (await db.execute(select(User).where(User.id == uid))).scalars().first()
                return create_access_token(subject=str(u.id), roll_number=u.roll_number)
            async with AsyncSessionLocal() as db:
                t_head = await tok(admin.id)
                t_class = await tok(fx["classA"])
                t_elec = await tok(fx["elecA"])
                t_sub = await tok(fx["subA"])
                t_stu = await tok(fx["stu"])
                t_stuA = await tok(fx["stuA"])
                t_stuB = await tok(fx["stuB"])
            h = {"Authorization": f"Bearer {t_head}"}

            # A. 401 unauth
            r = await c.get(P); check("A1. unauth GET -> 401", r.status_code == 401)
            r = await c.post(P, json={}); check("A2. unauth POST -> 401", r.status_code == 401)

            # B. STUDENT -> 403
            r = await c.get(P, headers={"Authorization": f"Bearer {t_stu}"})
            check("B1. STUDENT GET -> 403", r.status_code == 403)

            # C. HEAD reads
            r = await c.get(P, headers=h)
            check("C1. HEAD list -> 200", r.status_code == 200)
            r = await c.get(PC, headers=h)
            check("C2. cycles -> 200 with policies", r.status_code == 200 and r.json()["total"] >= 3,
                  str(r.status_code))

            # D. Scoped reads
            r = await c.get(P, headers={"Authorization": f"Bearer {t_class}"})
            check("D1. CLASS list -> 200", r.status_code == 200)
            r = await c.get(P, headers={"Authorization": f"Bearer {t_elec}"})
            check("D2. ELECTIVE list -> 200", r.status_code == 200)
            r = await c.get(P, headers={"Authorization": f"Bearer {t_sub}"})
            check("D3. no-scope user (would-be SUBSECTION_ADMIN) -> 403 (inert)",
                  r.status_code == 403, str(r.status_code))

            # E. Unauthorized writes -> 403
            for user, label in [(t_class, "CLASS"), (t_elec, "ELECTIVE"), (t_sub, "SUBSECTION"), (t_stu, "STUDENT")]:
                r = await c.post(P, json={"subject_id": str(fx["bcs501"]), "quiz_cycle_id": str(fx["cycle"])},
                                 headers={"Authorization": f"Bearer {user}"})
                check(f"E1. {label} POST -> 403", r.status_code == 403, str(r.status_code))

            # F. Existing schedules load (baseline 18)
            r = await c.get(P, headers=h)
            check("F1. baseline 18 schedules load", r.status_code == 200 and r.json()["total"] == 18,
                  str(r.json()["total"]))

            # G. Create valid common schedule
            r = await c.post(P, json={
                "subject_id": str(fx["bcs501"]), "quiz_cycle_id": str(fx["cycle"]),
                "date": fx["D1"].isoformat(), "schedule_status": "SCHEDULED",
            }, headers=h)
            check("G1. create common schedule -> 201", r.status_code == 201, str(r.status_code))
            fx["schedule1"] = r.json()["schedule"]["id"]
            check("G2. event created indicator", r.json()["event_created"] is True, str(r.json()["event_created"]))

            # H. Duplicate identity -> 409
            r = await c.post(P, json={
                "subject_id": str(fx["bcs501"]), "quiz_cycle_id": str(fx["cycle"]),
                "date": fx["D2"].isoformat(), "schedule_status": "SCHEDULED",
            }, headers=h)
            check("H1. duplicate (subject, cycle) -> 409", r.status_code == 409, str(r.status_code))

            # I. Invalid subject -> 404
            r = await c.post(P, json={"subject_id": str(uuid.uuid4()), "quiz_cycle_id": str(fx["cycle"])}, headers=h)
            check("I1. invalid subject -> 404", r.status_code == 404, str(r.status_code))

            # J. Common subject cannot masquerade as a logical elective -> 422
            r = await c.post(P, json={
                "subject_id": str(fx["bcs501"]), "quiz_cycle_id": str(fx["cycle"]),
                "elective_slot": "ELECTIVE_I",
            }, headers=h)
            check("J1. common subject with elective slot -> 422", r.status_code == 422, str(r.status_code))

            # J2. DE-I subject cannot use DE-II slot -> 422
            r = await c.post(P, json={
                "subject_id": str(fx["bcs54"]), "quiz_cycle_id": str(fx["cycle"]),
                "elective_slot": "ELECTIVE_II",
            }, headers=h)
            check("J2. DE-I subject with DE-II slot -> 422", r.status_code == 422, str(r.status_code))

            # K. Create valid elective schedule (DE-II, BCS-058)
            r = await c.post(P, json={
                "subject_id": str(fx["bcs58"]), "quiz_cycle_id": str(fx["cycle"]),
                "date": fx["D2"].isoformat(), "schedule_status": "SCHEDULED",
                "elective_slot": "ELECTIVE_II",
            }, headers=h)
            check("K1. create elective schedule -> 201", r.status_code == 201, str(r.status_code))
            fx["schedule2"] = r.json()["schedule"]["id"]
            check("K2. elective schedule is_elective", r.json()["schedule"]["is_elective"] is True)

            # L. Update date -> old event retired, new event created
            r = await c.patch(f"{P}/{fx['schedule1']}", json={"date": fx["D1b"].isoformat()}, headers=h)
            check("L1. update date -> 200", r.status_code == 200, str(r.status_code))
            check("L2. old event deactivated", r.json()["event_deactivated"] is True, str(r.json()))
            check("L3. new event created", r.json()["event_created"] is True, str(r.json()))

            # M. Cancel -> event deactivated
            r = await c.patch(f"{P}/{fx['schedule1']}", json={"schedule_status": "CANCELLED"}, headers=h)
            check("M1. cancel -> 200", r.status_code == 200, str(r.status_code))
            check("M2. event deactivated on cancel", r.json()["event_deactivated"] is True, str(r.json()))

            # N. Idempotent no-change update -> no event churn
            r = await c.patch(f"{P}/{fx['schedule1']}", json={"schedule_status": "CANCELLED"}, headers=h)
            check("N1. idempotent cancel -> 200, no event churn",
                  r.status_code == 200 and r.json()["event_created"] is False and r.json()["event_deactivated"] is False,
                  str(r.json()))

            # O. Reactivate (SCHEDULED + date) -> event recreated
            r = await c.patch(f"{P}/{fx['schedule1']}", json={"schedule_status": "SCHEDULED", "date": fx["D1"].isoformat()}, headers=h)
            check("O1. reactivate -> 200", r.status_code == 200, str(r.status_code))
            check("O2. event created on reactivate", r.json()["event_created"] is True, str(r.json()))

            # P. Elective schedule (schedule2) is isolated from schedule1 changes
            r = await c.get(f"{P}/{fx['schedule2']}", headers=h)
            check("P1. elective schedule event isolation (date unchanged)",
                  r.status_code == 200 and r.json()["date"] == fx["D2"].isoformat(),
                  str(r.json()))

        # ============ ELECTIVE ISOLATION (student quiz resolution) ============
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/quiz-eligibility/BCS-058/1",
                            headers={"Authorization": f"Bearer {t_stuA}"})
            check("Q1. Student A (DE-II BCS-058) /quiz-eligibility/BCS-058 -> 200",
                  r.status_code == 200, str(r.status_code))
            r = await c.get("/api/v1/quiz-eligibility/BCS-058/1",
                            headers={"Authorization": f"Bearer {t_stuB}"})
            check("Q2. Student B (DE-II BCS-055) /quiz-eligibility/BCS-058 -> 404 (no cross-leakage)",
                  r.status_code == 404, str(r.status_code))

        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.8 verifier (core): {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1

    finally:
        async with AsyncSessionLocal() as db:
            try:
                # Remove materialized quiz-day sessions for fixture subjects/dates,
                # then fixture events, schedules, cycle, users, section.
                fx_dates = []
                for k in ("D1", "D1b", "D2"):
                    if fx.get(k): fx_dates.append(fx[k])
                if fx_dates:
                    await db.execute(delete(ClassSession).where(
                        ClassSession.date.in_(fx_dates),
                        ClassSession.timetable_entry_id.is_(None),
                        ClassSession.is_extra.is_(False),
                    ))
                if fx.get("bcs501"):
                    await db.execute(delete(AcademicEvent).where(
                        AcademicEvent.event_type == "QUIZ_DAY",
                        AcademicEvent.subject_id == fx["bcs501"],
                        AcademicEvent.start_date.in_(fx_dates),
                    ))
                if fx.get("bcs58"):
                    await db.execute(delete(AcademicEvent).where(
                        AcademicEvent.event_type == "QUIZ_DAY",
                        AcademicEvent.subject_id == fx["bcs58"],
                        AcademicEvent.start_date.in_(fx_dates),
                    ))
                for k in ("schedule1", "schedule2"):
                    if fx.get(k):
                        await db.execute(delete(QuizSchedule).where(QuizSchedule.id == fx[k]))
                if fx.get("cycle"):
                    await db.execute(delete(EligibilityPolicy).where(EligibilityPolicy.quiz_cycle_id == fx["cycle"]))
                    await db.execute(delete(QuizCycle).where(QuizCycle.id == fx["cycle"]))
                if fx.get("section"):
                    await db.execute(delete(AdminScope).where(
                        AdminScope.user_id.in_([fx["classA"], fx["elecA"], fx["subA"]])))
                    await db.execute(delete(StudentElectiveChoice).where(
                        StudentElectiveChoice.user_id.in_([fx["stuA"], fx["stuB"]])))
                    await db.execute(delete(StudentEnrollment).where(
                        StudentEnrollment.user_id.in_([fx["stuA"], fx["stuB"]])))
                    for k in ("classA", "elecA", "subA", "stu", "stuA", "stuB"):
                        await db.execute(delete(User).where(User.id == fx[k]))
                    await db.execute(delete(Section).where(Section.id == fx["section"]))
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
        print(f"\nPhase 24.8 verifier: {p}/{len(results)} PASS")
        return 0 if p == len(results) else 1
    sys.exit(asyncio.run(_run()))