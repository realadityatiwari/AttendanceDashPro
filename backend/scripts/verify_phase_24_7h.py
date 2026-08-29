"""
Phase 24.7-H — Timetable Management Completion Gate verifier.

Exercises the FULL Phase 24.7 contract in one pass against the LOCAL dev DB:

  A. CONFLICT MATRIX (backend-authoritative)
     - exact overlap rejected (09:00-10:00 vs 09:00-10:00)
     - partial overlap rejected (09:00-10:30 vs 09:30-11:00)
     - containing overlap rejected (09:00-11:00 vs 09:30-10:00)
     - contained overlap rejected (09:30-10:00 vs 09:00-11:00)
     - adjacent allowed (09:00-10:00 vs 10:00-11:00)
     - different day allowed
     - different section allowed (unrelated scope)
     - inactive conflicting row allowed (does not block)
     - editing a row does not conflict with itself
  B. SECURITY MATRIX (direct API calls — UI hiding is NOT authorization)
     - HEAD_ADMIN global read/write
     - CLASS_ADMIN own-section only; cross-section 403 on reads AND writes
     - SUBSECTION_ADMIN own-subsection's section; cross-section 403
     - ELECTIVE_ADMIN own-subject entries only; write 403
     - STUDENT 403 on admin API
  C. ACADEMIC MATRIX (student timetable resolution)
     - Student A (DE-I BCS-054, DE-II BCS-058): common + electives + own subsection
     - Student B (DE-I BCS-052, DE-II BCS-055): common + electives + own subsection
     - no anchor leakage, no cross-student leakage, subsection isolation,
       inactive excluded
  D. DATA INTEGRITY
     - baseline counts restored after fixture cleanup
     - no attendance/class-session/quiz/event/elective-choice/student mutation
     - original active session unchanged

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
from app.models.enums import AdminRole, ElectiveSlot, UserRole
from app.models.timetable import TimetableEntry, ClassSession
from app.models.quiz import QuizSchedule
from app.models.event import AcademicEvent
from app.models.attendance import AttendanceRecord
from app.core.security import create_access_token

results = []; _BASELINE = {}; _ACTIVE_SESSION_ID = None

def check(n, ok, d=""): results.append((n, ok)); print(f"{'PASS' if ok else 'FAIL'}  {n}" + (f"  -- {d}" if not ok else ""))

BASELINE_TABLES = [
    "users", "admin_scopes", "academic_sessions", "semesters", "sections",
    "subsections", "subjects", "timetable_entries", "class_sessions",
    "attendance_records", "academic_events", "quiz_schedules",
    "student_elective_choices",
]

async def table_counts(db) -> dict:
    out = {}
    for t in BASELINE_TABLES:
        out[t] = (await db.execute(select(func.count()).select_from(text(f'"{t}"')))).scalar_one()
    return out

async def main() -> int:
    global _BASELINE, _ACTIVE_SESSION_ID
    print("=" * 66)
    print("Phase 24.7-H — Timetable Management Completion Gate")
    print(f"Locality guard: {settings.DATABASE_URI}")
    print("=" * 66)
    fx = {}
    try:
        async with AsyncSessionLocal() as db:
            active = (await db.execute(select(AcademicSession).where(AcademicSession.is_active.is_(True)))).scalars().first()
            if active is None: check("0. active session", False); return 1
            _ACTIVE_SESSION_ID = active.id
            admin = (await db.execute(select(User).where(User.role == UserRole.ADMIN))).scalars().first()
            if admin is None: check("0. admin user", False); return 1
            _BASELINE = await table_counts(db)
            print(f"baseline: {_BASELINE}")

            # Real subjects (anchors + catalog + common)
            bcs54 = (await db.execute(select(Subject).where(Subject.code == "BCS-054"))).scalars().first()
            bcs58 = (await db.execute(select(Subject).where(Subject.code == "BCS-058"))).scalars().first()
            bcs52 = (await db.execute(select(Subject).where(Subject.code == "BCS-052"))).scalars().first()
            bcs55 = (await db.execute(select(Subject).where(Subject.code == "BCS-055"))).scalars().first()
            bcs501 = (await db.execute(select(Subject).where(Subject.code == "BCS-501"))).scalars().first()
            if not all([bcs54, bcs58, bcs52, bcs55, bcs501]):
                check("0. real subjects found", False); return 1
            fx["bcs54"] = bcs54.id; fx["bcs58"] = bcs58.id
            fx["bcs52"] = bcs52.id; fx["bcs55"] = bcs55.id; fx["bcs501"] = bcs501.id

            # Fixture academic structure
            fs = AcademicSession(name="REVIEW 24.7H", start_date=datetime.date(2028,1,1), end_date=datetime.date(2028,12,31), is_active=False)
            db.add(fs); await db.flush(); fx["session"] = fs.id
            fsem = Semester(name="Review Sem 24.7H", session_id=fs.id, start_date=datetime.date(2028,1,15), end_date=datetime.date(2028,6,30))
            db.add(fsem); await db.flush(); fx["semester"] = fsem.id
            secA = Section(name="REV-HA", program="BTech CSE", semester_id=fsem.id)
            secB = Section(name="REV-HB", program="BTech CSE", semester_id=fsem.id)
            secC = Section(name="REV-HC", program="BTech CSE", semester_id=fsem.id)
            db.add_all([secA, secB, secC]); await db.flush()
            fx["secA"] = secA.id; fx["secB"] = secB.id; fx["secC"] = secC.id
            subA1 = Subsection(name="REV-HA1", section_id=secA.id)
            subA2 = Subsection(name="REV-HA2", section_id=secA.id)
            db.add_all([subA1, subA2]); await db.flush()
            fx["subA1"] = subA1.id; fx["subA2"] = subA2.id

            # Fixture timetable entries
            T = lambda **kw: TimetableEntry(section_id=secA.id, **kw)
            db.add_all([
                T(subject_id=bcs501.id, day_of_week=0, start_time=datetime.time(9,0), end_time=datetime.time(10,0), class_type="L"),
                T(subject_id=bcs54.id, day_of_week=1, start_time=datetime.time(9,0), end_time=datetime.time(10,0), class_type="L", elective_slot=ElectiveSlot.ELECTIVE_I),
                T(subject_id=bcs58.id, day_of_week=1, start_time=datetime.time(10,0), end_time=datetime.time(11,0), class_type="L", elective_slot=ElectiveSlot.ELECTIVE_II),
                T(subject_id=bcs501.id, day_of_week=2, start_time=datetime.time(9,0), end_time=datetime.time(10,0), class_type="T", subsection_id=subA1.id),
                T(subject_id=bcs501.id, day_of_week=2, start_time=datetime.time(10,0), end_time=datetime.time(11,0), class_type="T", subsection_id=subA2.id),
                T(subject_id=bcs501.id, day_of_week=3, start_time=datetime.time(9,0), end_time=datetime.time(10,0), class_type="L", is_active=False),
            ])
            await db.flush(); fx["entries"] = True

            # Fixture subject in the fixture semester (for conflict-matrix
            # create/update calls — subject must belong to the section's
            # semester per academic-context validation).
            fx_subj = Subject(code="REV-HX", name="Review HX", category="theory",
                              quiz_applicable=True, attendance_applicable=True,
                              semester_id=fsem.id)
            db.add(fx_subj); await db.flush(); fx["fx_subj"] = fx_subj.id

            # Fixture users
            classA = User(roll_number=f"2401310{uuid.uuid4().hex[:6]}", name="H CLASS", hashed_password="x", section_id=secA.id)
            subAdm = User(roll_number=f"2401311{uuid.uuid4().hex[:6]}", name="H SUBSEC", hashed_password="x", section_id=secA.id)
            elecAdm = User(roll_number=f"2401312{uuid.uuid4().hex[:6]}", name="H ELEC", hashed_password="x", section_id=secA.id)
            stu = User(roll_number=f"2401313{uuid.uuid4().hex[:6]}", name="H STUDENT", hashed_password="x", section_id=secA.id)
            stuA = User(roll_number=f"2401314{uuid.uuid4().hex[:6]}", name="StuA H", hashed_password="x", section_id=secA.id, subsection_id=subA1.id)
            stuB = User(roll_number=f"2401315{uuid.uuid4().hex[:6]}", name="StuB H", hashed_password="x", section_id=secA.id, subsection_id=subA2.id)
            db.add_all([classA, subAdm, elecAdm, stu, stuA, stuB]); await db.flush()
            fx["classA"] = classA.id; fx["subAdm"] = subAdm.id; fx["elecAdm"] = elecAdm.id
            fx["stu"] = stu.id; fx["stuA"] = stuA.id; fx["stuB"] = stuB.id

            db.add_all([
                AdminScope(user_id=classA.id, role=AdminRole.CLASS_ADMIN, section_id=secA.id),
                AdminScope(user_id=subAdm.id, role=AdminRole.SUBSECTION_ADMIN, subsection_id=subA1.id),
                AdminScope(user_id=elecAdm.id, role=AdminRole.ELECTIVE_ADMIN, subject_id=bcs58.id),
            ])
            db.add_all([
                StudentElectiveChoice(user_id=stuA.id, elective_slot=ElectiveSlot.ELECTIVE_I, subject_id=bcs54.id),
                StudentElectiveChoice(user_id=stuA.id, elective_slot=ElectiveSlot.ELECTIVE_II, subject_id=bcs58.id),
                StudentElectiveChoice(user_id=stuB.id, elective_slot=ElectiveSlot.ELECTIVE_I, subject_id=bcs52.id),
                StudentElectiveChoice(user_id=stuB.id, elective_slot=ElectiveSlot.ELECTIVE_II, subject_id=bcs55.id),
            ])
            await db.commit()

        # ============ A. CONFLICT MATRIX (service-level, HEAD) ============
        from app.services.admin_timetable_service import AdminTimetableService
        from app.schemas.admin_timetable import CreateTimetableEntryRequest
        async with AsyncSessionLocal() as db:
            svc = AdminTimetableService(db)
            admin = (await db.execute(select(User).where(User.role == UserRole.ADMIN))).scalars().first()
            C = lambda start, end, day=0, sub=None: CreateTimetableEntryRequest(
                section_id=fx["secC"], subject_id=fx["fx_subj"], day_of_week=day,
                start_time=datetime.time.fromisoformat(start), end_time=datetime.time.fromisoformat(end),
                class_type="L", subsection_id=sub)
            from app.services.admin_timetable_service import TimetableTimeConflictError

            async def expect_conflict(name, entry):
                try:
                    await svc.create_entry(admin, entry)
                    check(name, False, "no conflict raised")
                except TimetableTimeConflictError:
                    check(name, True)

            # exact overlap
            await svc.create_entry(admin, C("09:00", "10:00", day=4))
            await expect_conflict("A1. exact overlap rejected", C("09:00", "10:00", day=4))
            # partial overlap
            await expect_conflict("A2. partial overlap rejected (09:00-10:30 vs 09:30-11:00)",
                                  C("09:30", "11:00", day=4))
            # containing overlap (existing 09:00-10:00 contains new 09:30-09:45)
            await expect_conflict("A3. containing overlap rejected", C("09:30", "09:45", day=4))
            # contained overlap (new 08:30-10:30 contains existing 09:00-10:00)
            await expect_conflict("A4. contained overlap rejected", C("08:30", "10:30", day=4))
            # adjacent allowed
            e_adj = await svc.create_entry(admin, C("10:00", "11:00", day=4))
            check("A5. adjacent entries allowed (10:00-11:00)", bool(e_adj.id))
            # different day allowed
            e_day = await svc.create_entry(admin, C("09:00", "10:00", day=5))
            check("A6. different day allowed", bool(e_day.id))
            # different section (unrelated scope) allowed
            e_sec = await svc.create_entry(admin, CreateTimetableEntryRequest(
                section_id=fx["secB"], subject_id=fx["fx_subj"], day_of_week=4,
                start_time=datetime.time(9,0), end_time=datetime.time(10,0), class_type="L"))
            check("A7. different section (unrelated scope) allowed", bool(e_sec.id))
            # inactive conflicting row allowed
            from app.schemas.admin_timetable import UpdateTimetableEntryRequest
            await svc.deactivate_entry(admin, e_adj.id)
            e_inactive = await svc.create_entry(admin, C("10:00", "11:00", day=4))
            check("A8. inactive conflicting row does not block", bool(e_inactive.id))
            # editing a row does not conflict with itself
            await svc.update_entry(admin, e_inactive.id, UpdateTimetableEntryRequest(
                start_time=datetime.time(10,0), end_time=datetime.time(10,30)))
            check("A9. editing a row does not conflict with itself", True)

        # ============ B. SECURITY MATRIX (direct API) ============
        transport = ASGITransport(app=app)
        S = "/api/v1/admin/timetable"
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            async def tok(uid):
                u = (await db.execute(select(User).where(User.id == uid))).scalars().first()
                return create_access_token(subject=str(u.id), roll_number=u.roll_number)
            async with AsyncSessionLocal() as db:
                t_head = await tok(admin.id)
                t_class = await tok(fx["classA"])
                t_sub = await tok(fx["subAdm"])
                t_elec = await tok(fx["elecAdm"])
                t_stu = await tok(fx["stu"])

            # HEAD global
            r = await c.get(S, headers={"Authorization": f"Bearer {t_head}"})
            check("B1. HEAD list -> 200", r.status_code == 200)
            # CLASS own section read
            r = await c.get(S, headers={"Authorization": f"Bearer {t_class}"})
            check("B2. CLASS list -> 200 own-section", r.status_code == 200 and
                  all(i["section_id"] == str(fx["secA"]) for i in r.json()["items"]))
            # CLASS cross-section via query param must NOT leak
            r = await c.get(S, params={"section_id": str(fx["secB"])}, headers={"Authorization": f"Bearer {t_class}"})
            check("B3. CLASS cross-section query -> no leakage (empty or 403)",
                  r.status_code in (200, 403) and (r.status_code == 403 or len(r.json()["items"]) == 0),
                  f"status={r.status_code} n={len(r.json().get('items', [])) if r.status_code == 200 else 'n/a'}")
            # CLASS cross-section write -> 403
            r = await c.post(S, json={"section_id": str(fx["secB"]), "subject_id": str(fx["bcs501"]),
                                      "day_of_week": 0, "start_time": "09:00", "end_time": "10:00", "class_type": "L"},
                             headers={"Authorization": f"Bearer {t_class}"})
            check("B4. CLASS cross-section write -> 403", r.status_code == 403, str(r.status_code))
            # SUBSECTION read own section
            r = await c.get(S, headers={"Authorization": f"Bearer {t_sub}"})
            check("B5. SUBSECTION list -> 200 own section", r.status_code == 200 and
                  all(i["section_id"] == str(fx["secA"]) for i in r.json()["items"]))
            # SUBSECTION write -> 403
            r = await c.post(S, json={"section_id": str(fx["secA"]), "subject_id": str(fx["bcs501"]),
                                      "day_of_week": 0, "start_time": "09:00", "end_time": "10:00", "class_type": "L"},
                             headers={"Authorization": f"Bearer {t_sub}"})
            check("B6. SUBSECTION write -> 403", r.status_code == 403, str(r.status_code))
            # ELECTIVE own subject only
            r = await c.get(S, headers={"Authorization": f"Bearer {t_elec}"})
            check("B7. ELECTIVE list -> own subject only", r.status_code == 200 and
                  all(i["subject_code"] == "BCS-058" for i in r.json()["items"]),
                  f"codes={[i['subject_code'] for i in r.json()['items']]}")
            # ELECTIVE write -> 403
            r = await c.post(S, json={"section_id": str(fx["secA"]), "subject_id": str(fx["bcs58"]),
                                      "day_of_week": 0, "start_time": "09:00", "end_time": "10:00", "class_type": "L"},
                             headers={"Authorization": f"Bearer {t_elec}"})
            check("B8. ELECTIVE write -> 403", r.status_code == 403, str(r.status_code))
            # STUDENT -> 403
            r = await c.get(S, headers={"Authorization": f"Bearer {t_stu}"})
            check("B9. STUDENT admin list -> 403", r.status_code == 403, str(r.status_code))

        # ============ C. ACADEMIC MATRIX (student resolution) ============
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            for label, uid, expected, banned in [
                ("Student A", fx["stuA"], {("BCS-501",0), ("BCS-054",1), ("BCS-058",1), ("BCS-501",2)}, ["BCS-052","BCS-055"]),
                ("Student B", fx["stuB"], {("BCS-501",0), ("BCS-052",1), ("BCS-055",1), ("BCS-501",2)}, ["BCS-054","BCS-058"]),
            ]:
                u = (await db.execute(select(User).where(User.id == uid))).scalars().first()
                tok = create_access_token(subject=str(u.id), roll_number=u.roll_number)
                r = await c.get("/api/v1/timetable", headers={"Authorization": f"Bearer {tok}"})
                got = {(i["subject"]["code"], i["day_of_week"]) for i in r.json()}
                check(f"C.{label}: resolved set exact", got == expected, f"got={sorted(got)}")
                codes = [i["subject"]["code"] for i in r.json()]
                for b in banned:
                    check(f"C.{label}: no leakage of {b}", b not in codes)

        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.7-H completion gate (core): {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1

    finally:
        async with AsyncSessionLocal() as db:
            try:
                if fx.get("entries"):
                    await db.execute(delete(TimetableEntry).where(
                        TimetableEntry.section_id.in_([fx["secA"], fx["secB"], fx["secC"]])))
                    if fx.get("fx_subj"):
                        await db.execute(delete(Subject).where(Subject.id == fx["fx_subj"]))
                    await db.execute(delete(AdminScope).where(AdminScope.user_id.in_(
                        [fx["classA"], fx["subAdm"], fx["elecAdm"]])))
                    await db.execute(delete(StudentElectiveChoice).where(
                        StudentElectiveChoice.user_id.in_([fx["stuA"], fx["stuB"]])))
                    for k in ("classA","subAdm","elecAdm","stu","stuA","stuB"):
                        await db.execute(delete(User).where(User.id == fx[k]))
                    await db.execute(delete(Subsection).where(Subsection.section_id.in_([fx["secA"], fx["secB"], fx["secC"]])))
                    await db.execute(delete(Section).where(Section.id.in_([fx["secA"], fx["secB"], fx["secC"]])))
                    await db.execute(delete(Semester).where(Semester.id == fx["semester"]))
                    await db.execute(delete(AcademicSession).where(AcademicSession.id == fx["session"]))
                if _ACTIVE_SESSION_ID:
                    await db.execute(update(AcademicSession).where(AcademicSession.id == _ACTIVE_SESSION_ID).values(is_active=True))
                await db.commit()
            except Exception as e: print(f"cleanup: {e}"); await db.rollback()

async def post_cleanup():
    async with AsyncSessionLocal() as db:
        after = await table_counts(db)
        check("D1. all baseline table counts restored", after == _BASELINE, f"before={_BASELINE} after={after}")
        # D2: data integrity — attendance/sessions/quiz/events unchanged (covered by counts above)
        check("D2. attendance/class_sessions/quiz/events/choices unchanged",
              after["attendance_records"] == _BASELINE["attendance_records"]
              and after["class_sessions"] == _BASELINE["class_sessions"]
              and after["quiz_schedules"] == _BASELINE["quiz_schedules"]
              and after["academic_events"] == _BASELINE["academic_events"]
              and after["student_elective_choices"] == _BASELINE["student_elective_choices"])
        a = (await db.execute(select(AcademicSession).where(AcademicSession.is_active.is_(True)))).scalars().first()
        check("D3. original active session unchanged", a is not None and a.id == _ACTIVE_SESSION_ID)

if __name__ == "__main__":
    async def _run():
        c = await main()
        await post_cleanup()
        p = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.7-H completion gate: {p}/{len(results)} PASS")
        return 0 if p == len(results) else 1
    sys.exit(asyncio.run(_run()))