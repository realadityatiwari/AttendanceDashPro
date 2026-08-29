"""
Phase 24.7-G — Student Timetable Resolution verifier.

Proves the student-facing timetable endpoint correctly resolves the
authoritative timetable against each student's academic context and
locked elective choices — with no anchor leakage, no subsection leakage,
and no cross-student elective leakage.

Fixture schedule (section REV-G):
  day 0 09:00  BCS-501 (common, section-wide, LECTURE)
  day 1 09:00  BCS-054 anchor, DE-I slot (LECTURE)
  day 1 10:00  BCS-058 anchor, DE-II slot (LECTURE)
  day 2 09:00  BCS-501 subsection A1 only (TUTORIAL)
  day 2 10:00  BCS-501 subsection A2 only (TUTORIAL)
  day 3 09:00  BCS-501 (common, INACTIVE — must never appear)

Students:
  Student A (subsection A1): DE-I -> BCS-054, DE-II -> BCS-058
  Student B (subsection A2): DE-I -> BCS-052, DE-II -> BCS-055
  Student C (subsection A1): no locked choices

Expected resolved output:
  A: {BCS-501 d0, BCS-054 d1 (DE-I), BCS-058 d1 (DE-II), BCS-501 d2 (A1)}  = 4 items
  B: {BCS-501 d0, BCS-052 d1 (DE-I), BCS-055 d1 (DE-II), BCS-501 d2 (A2)}  = 4 items
  C: {BCS-501 d0, BCS-501 d2 (A1)}                                         = 2 items
     (DE-I/DE-II omitted — NO anchor leakage without a locked choice)

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
from app.models.enums import ElectiveSlot, UserRole
from app.models.timetable import TimetableEntry
from app.core.security import create_access_token

results = []; _BASELINE = {}; _ACTIVE_SESSION_ID = None

def check(n, ok, d=""): results.append((n, ok)); print(f"{'PASS' if ok else 'FAIL'}  {n}" + (f"  -- {d}" if not ok else ""))

async def counts(db):
    out = {}
    for t in ["users", "academic_sessions", "semesters", "sections", "subsections",
              "subjects", "timetable_entries", "student_elective_choices"]:
        out[t] = (await db.execute(select(func.count()).select_from(text(f'"{t}"')))).scalar_one()
    return out

async def main() -> int:
    global _BASELINE, _ACTIVE_SESSION_ID
    print("=" * 64)
    print("Phase 24.7-G — Student Timetable Resolution")
    print(f"Locality guard: {settings.DATABASE_URI}")
    print("=" * 64)
    fx = {}
    try:
        async with AsyncSessionLocal() as db:
            active = (await db.execute(select(AcademicSession).where(AcademicSession.is_active.is_(True)))).scalars().first()
            if active is None: check("0. active session", False); return 1
            _ACTIVE_SESSION_ID = active.id
            _BASELINE = await counts(db)
            print(f"baseline: {_BASELINE}")

            bcs54 = (await db.execute(select(Subject).where(Subject.code == "BCS-054"))).scalars().first()
            bcs58 = (await db.execute(select(Subject).where(Subject.code == "BCS-058"))).scalars().first()
            bcs52 = (await db.execute(select(Subject).where(Subject.code == "BCS-052"))).scalars().first()
            bcs55 = (await db.execute(select(Subject).where(Subject.code == "BCS-055"))).scalars().first()
            bcs51 = (await db.execute(select(Subject).where(Subject.code == "BCS-501"))).scalars().first()
            if not all([bcs54, bcs58, bcs52, bcs55, bcs51]):
                check("0. real subjects found", False); return 1

            fs = AcademicSession(name="REVIEW 24.7G", start_date=datetime.date(2028,1,1), end_date=datetime.date(2028,12,31), is_active=False)
            db.add(fs); await db.flush(); fx["session"] = fs.id
            fsem = Semester(name="Review Sem 24.7G", session_id=fs.id, start_date=datetime.date(2028,1,15), end_date=datetime.date(2028,6,30))
            db.add(fsem); await db.flush(); fx["semester"] = fsem.id
            sec = Section(name="REV-G", program="BTech CSE", semester_id=fsem.id)
            db.add(sec); await db.flush(); fx["section"] = sec.id
            subA = Subsection(name="REV-G-A1", section_id=sec.id)
            subB = Subsection(name="REV-G-A2", section_id=sec.id)
            db.add_all([subA, subB]); await db.flush()
            fx["subsection_a"] = subA.id; fx["subsection_b"] = subB.id

            T = lambda **kw: TimetableEntry(section_id=sec.id, **kw)
            db.add_all([
                T(subject_id=bcs51.id, day_of_week=0, start_time=datetime.time(9,0), end_time=datetime.time(10,0), class_type="L"),
                T(subject_id=bcs54.id, day_of_week=1, start_time=datetime.time(9,0), end_time=datetime.time(10,0), class_type="L", elective_slot=ElectiveSlot.ELECTIVE_I),
                T(subject_id=bcs58.id, day_of_week=1, start_time=datetime.time(10,0), end_time=datetime.time(11,0), class_type="L", elective_slot=ElectiveSlot.ELECTIVE_II),
                T(subject_id=bcs51.id, day_of_week=2, start_time=datetime.time(9,0), end_time=datetime.time(10,0), class_type="T", subsection_id=subA.id),
                T(subject_id=bcs51.id, day_of_week=2, start_time=datetime.time(10,0), end_time=datetime.time(11,0), class_type="T", subsection_id=subB.id),
                T(subject_id=bcs51.id, day_of_week=3, start_time=datetime.time(9,0), end_time=datetime.time(10,0), class_type="L", is_active=False),
            ])
            await db.flush(); fx["entries"] = True

            stuA = User(roll_number=f"2401300{uuid.uuid4().hex[:6]}", name="StuA 24.7G", hashed_password="x", section_id=sec.id, subsection_id=subA.id)
            stuB = User(roll_number=f"2401301{uuid.uuid4().hex[:6]}", name="StuB 24.7G", hashed_password="x", section_id=sec.id, subsection_id=subB.id)
            stuC = User(roll_number=f"2401302{uuid.uuid4().hex[:6]}", name="StuC 24.7G", hashed_password="x", section_id=sec.id, subsection_id=subA.id)
            db.add_all([stuA, stuB, stuC]); await db.flush()
            fx["stuA"] = stuA.id; fx["stuB"] = stuB.id; fx["stuC"] = stuC.id

            db.add_all([
                StudentElectiveChoice(user_id=stuA.id, elective_slot=ElectiveSlot.ELECTIVE_I, subject_id=bcs54.id),
                StudentElectiveChoice(user_id=stuA.id, elective_slot=ElectiveSlot.ELECTIVE_II, subject_id=bcs58.id),
                StudentElectiveChoice(user_id=stuB.id, elective_slot=ElectiveSlot.ELECTIVE_I, subject_id=bcs52.id),
                StudentElectiveChoice(user_id=stuB.id, elective_slot=ElectiveSlot.ELECTIVE_II, subject_id=bcs55.id),
            ])
            await db.commit()

        S = "/api/v1/timetable"
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            # Expected: (label, user_key, expected (code, day) set, expected count, banned codes)
            cases = [
                ("Student A", "stuA",
                 {("BCS-501", 0), ("BCS-054", 1), ("BCS-058", 1), ("BCS-501", 2)},
                 4, ["BCS-052", "BCS-055"]),
                ("Student B", "stuB",
                 {("BCS-501", 0), ("BCS-052", 1), ("BCS-055", 1), ("BCS-501", 2)},
                 4, ["BCS-054", "BCS-058"]),
                ("Student C (no choices)", "stuC",
                 {("BCS-501", 0), ("BCS-501", 2)},
                 2, ["BCS-054", "BCS-058", "BCS-052", "BCS-055"]),
            ]
            for label, ukey, expected_set, expected_count, banned in cases:
                stu = (await db.execute(select(User).where(User.id == fx[ukey]))).scalars().first()
                tok = create_access_token(subject=str(stu.id), roll_number=stu.roll_number)
                r = await c.get(S, headers={"Authorization": f"Bearer {tok}"})
                check(f"{label} -> 200", r.status_code == 200, str(r.status_code))
                items = r.json()
                got = {(i["subject"]["code"], i["day_of_week"]) for i in items}
                codes = [i["subject"]["code"] for i in items]
                days = [i["day_of_week"] for i in items]

                check(f"{label}: resolved set matches exactly",
                      got == expected_set, f"got={sorted(got)} expected={sorted(expected_set)}")
                check(f"{label}: item count = {expected_count}",
                      len(items) == expected_count, f"got {len(items)}")

                # No cross-student / anchor leakage
                for banned_code in banned:
                    check(f"{label}: no leakage of {banned_code}",
                          banned_code not in codes, f"codes={codes}")

                # Subsection isolation: exactly ONE day-2 entry (their own)
                day2 = [i for i in items if i["day_of_week"] == 2]
                check(f"{label}: exactly one own-subsection entry (day 2)",
                      len(day2) == 1, f"day2={len(day2)}")

                # Inactive entry (day 3) never appears
                check(f"{label}: inactive entry excluded",
                      3 not in days, f"days={days}")

        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.7-G verifier (core): {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1

    finally:
        async with AsyncSessionLocal() as db:
            try:
                if fx.get("entries"):
                    await db.execute(delete(TimetableEntry).where(TimetableEntry.section_id == fx["section"]))
                    await db.execute(delete(StudentElectiveChoice).where(
                        StudentElectiveChoice.user_id.in_([fx["stuA"], fx["stuB"], fx["stuC"]])))
                    for k in ("stuA","stuB","stuC"):
                        await db.execute(delete(User).where(User.id == fx[k]))
                    await db.execute(delete(Subsection).where(Subsection.section_id == fx["section"]))
                    await db.execute(delete(Section).where(Section.id == fx["section"]))
                    await db.execute(delete(Semester).where(Semester.id == fx["semester"]))
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
        print(f"\nPhase 24.7-G verifier: {p}/{len(results)} PASS")
        return 0 if p == len(results) else 1
    sys.exit(asyncio.run(_run()))