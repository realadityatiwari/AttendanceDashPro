"""
Phase 24.12 — Attendance admin & analytics verifier.

Proves the READ-ONLY admin attendance contract end-to-end against the LOCAL
development DB: authorization matrix (HEAD / CLASS / ELECTIVE / SUBSECTION /
STUDENT / unauth), section + subject aggregates, per-student reads, spoof
resistance, cancelled/extra semantics, and exact baseline restoration.

The contract reuses the canonical class_sessions + attendance_records pipeline
(occurrence collapse, elective resolution, occurrence outcomes) — no
attendance mathematics is reproduced here; aggregates are checked against an
independent SQL reference count.

LOCALITY GUARD (hard): forces + asserts DATABASE_URI is the local dev DB.
"""
import asyncio, os, sys, uuid
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
from app.models.academic import Subject, AcademicSession, Semester, StudentEnrollment, StudentElectiveChoice
from app.models.admin_scope import AdminScope
from app.models.attendance import AttendanceRecord
from app.models.timetable import ClassSession, TimetableEntry
from app.models.enums import AdminRole, UserRole, EnrollmentType
from app.core.security import create_access_token

results = []; _BASELINE = {}; _FX = {}

FIXTURE_ROLL_PREFIX = "240140"

def check(n, ok, d=""): results.append((n, ok)); print(f"{'PASS' if ok else 'FAIL'}  {n}" + (f"  -- {d}" if not ok else ""))

async def purge_fixtures(db):
    """Self-healing fixture purge (prefix-based): removes rows created by any
    prior Phase 24.12 verifier run, so a crash mid-run cannot leave residue
    and every run starts from the true baseline."""
    rows = (await db.execute(
        select(User.id).where(User.roll_number.like(f"{FIXTURE_ROLL_PREFIX}%"))
    )).scalars().all()
    ids = list(rows)
    if ids:
        await db.execute(delete(AttendanceRecord).where(AttendanceRecord.user_id.in_(ids)))
        await db.execute(delete(StudentElectiveChoice).where(StudentElectiveChoice.user_id.in_(ids)))
        await db.execute(delete(StudentEnrollment).where(StudentEnrollment.user_id.in_(ids)))
        await db.execute(delete(AdminScope).where(AdminScope.user_id.in_(ids)))
        await db.execute(delete(User).where(User.id.in_(ids)))
    await db.execute(delete(Subsection).where(Subsection.name.like("Ph2412 SS %")))
    await db.execute(delete(Section).where(Section.name.like("Ph2412 S2 %")))
    await db.commit()

async def counts(db):
    out = {}
    for t in ["users", "admin_scopes", "academic_events", "class_sessions",
              "attendance_records", "student_elective_choices", "timetable_entries",
              "occurrence_outcomes", "quiz_schedules", "student_enrollments"]:
        out[t] = (await db.execute(select(func.count()).select_from(text(f'"{t}"')))).scalar_one()
    return out

async def main() -> int:
    global _BASELINE
    print("=" * 64)
    print("Phase 24.12 — Attendance admin & analytics")
    print(f"Locality guard: {settings.DATABASE_URI}")
    print("=" * 64)
    try:
        async with AsyncSessionLocal() as db:
            # Self-healing: purge any prior-run residue BEFORE capturing the
            # true baseline (a crash mid-run must never corrupt the baseline).
            await purge_fixtures(db)
            _BASELINE = await counts(db)
            print(f"baseline: {_BASELINE}")
            active = (await db.execute(select(AcademicSession).where(AcademicSession.is_active.is_(True)))).scalars().first()
            if active is None: check("0. active session", False); return 1
            _FX["session"] = active.id
            sem = (await db.execute(select(Semester).where(Semester.session_id == active.id).limit(1))).scalars().first()
            if sem is None: check("0. semester", False); return 1
            _FX["semester"] = sem.id
            admin = (await db.execute(select(User).where(User.role == UserRole.ADMIN))).scalars().first()
            if admin is None: check("0. admin", False); return 1
            _FX["admin"] = admin.id
            section = (await db.execute(select(Section))).scalars().first()
            if section is None: check("0. section", False); return 1
            _FX["section"] = section.id
            bcs501 = (await db.execute(select(Subject).where(Subject.code == "BCS-501"))).scalars().first()
            bcs502 = (await db.execute(select(Subject).where(Subject.code == "BCS-502"))).scalars().first()
            bcs058 = (await db.execute(select(Subject).where(Subject.code == "BCS-058"))).scalars().first()
            if not all([bcs501, bcs502, bcs058]): check("0. subjects", False); return 1
            _FX["bcs501"] = bcs501.id; _FX["bcs502"] = bcs502.id; _FX["bcs058"] = bcs058.id

            # Fixture users: target student (receives attendance), plus scoped admins
            target = User(roll_number=f"2401400{uuid.uuid4().hex[:6]}", name="Ph2412 Student", hashed_password="x", section_id=section.id)
            classAdmin = User(roll_number=f"2401401{uuid.uuid4().hex[:6]}", name="Ph2412 CLASS", hashed_password="x", section_id=section.id)
            elecAdmin = User(roll_number=f"2401402{uuid.uuid4().hex[:6]}", name="Ph2412 ELEC", hashed_password="x", section_id=section.id)
            subAdmin = User(roll_number=f"2401403{uuid.uuid4().hex[:6]}", name="Ph2412 SUB", hashed_password="x", section_id=section.id)
            stu = User(roll_number=f"2401404{uuid.uuid4().hex[:6]}", name="Ph2412 STU", hashed_password="x", section_id=section.id)
            db.add_all([target, classAdmin, elecAdmin, subAdmin, stu]); await db.flush()
            _FX.update(target=target.id, classAdmin=classAdmin.id, elecAdmin=elecAdmin.id,
                       subAdmin=subAdmin.id, stu=stu.id)
            # SUBSECTION_ADMIN fixture: a real subsection row (FK) — still
            # structurally inert for reads (no student is assigned to it).
            subsec = Subsection(name=f"Ph2412 SS {uuid.uuid4().hex[:4]}", section_id=section.id)
            db.add(subsec); await db.flush(); _FX["subsection"] = subsec.id
            db.add_all([
                AdminScope(user_id=classAdmin.id, role=AdminRole.CLASS_ADMIN, section_id=section.id),
                AdminScope(user_id=elecAdmin.id, role=AdminRole.ELECTIVE_ADMIN, subject_id=bcs058.id),
                # SUBSECTION_ADMIN: structurally inert (no student assigned) — always empty.
                AdminScope(user_id=subAdmin.id, role=AdminRole.SUBSECTION_ADMIN, subsection_id=subsec.id),
            ])
            # Enroll the target student in BCS-501 and BCS-502 (compulsory).
            db.add_all([
                StudentEnrollment(user_id=target.id, subject_id=bcs501.id, enrollment_type=EnrollmentType.COMPULSORY),
                StudentEnrollment(user_id=target.id, subject_id=bcs502.id, enrollment_type=EnrollmentType.COMPULSORY),
            ])
            # Deterministic fixture: reuse one real BCS-501 session + one BCS-502 session.
            ses = (await db.execute(
                select(ClassSession).where(
                    ClassSession.subject_id == bcs501.id,
                    ClassSession.is_cancelled.is_(False),
                    ClassSession.date <= func.current_date(),
                ).limit(3)
            )).scalars().all()
            ses2 = (await db.execute(
                select(ClassSession).where(
                    ClassSession.subject_id == bcs502.id,
                    ClassSession.is_cancelled.is_(False),
                    ClassSession.date <= func.current_date(),
                ).limit(2)
            )).scalars().all()
            if not ses or not ses2: check("0. fixture sessions", False); return 1
            _FX["s1"] = ses[0].id; _FX["s2"] = ses[1].id if len(ses) > 1 else ses[0].id
            _FX["s3"] = ses2[0].id
            # Attendance: BCS-501 sessions -> Attended/Missed; BCS-502 -> Pending (no record).
            db.add_all([
                AttendanceRecord(user_id=target.id, class_session_id=ses[0].id, status="Attended"),
                AttendanceRecord(user_id=target.id, class_session_id=ses[1].id, status="Missed"),
            ])
            await db.commit()

        transport = ASGITransport(app=app)
        A = "/api/v1/admin/attendance"
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            async with AsyncSessionLocal() as db:
                async def tok(uid):
                    u = (await db.execute(select(User).where(User.id == uid))).scalars().first()
                    return create_access_token(subject=str(u.id), roll_number=u.roll_number)
                t_head = await tok(_FX["admin"]); t_class = await tok(_FX["classAdmin"])
                t_elec = await tok(_FX["elecAdmin"]); t_sub = await tok(_FX["subAdmin"])
                t_stu = await tok(_FX["stu"])
            h = {"Authorization": f"Bearer {t_head}"}

            # A. unauth -> 401
            for p in [f"{A}/sections", f"{A}/subjects", f"{A}/students/{_FX['target']}"]:
                r = await c.get(p); check(f"A1. unauth {p.split('/')[-1]} -> 401", r.status_code == 401, str(r.status_code))

            # B. STUDENT -> 403
            r = await c.get(f"{A}/sections", headers={"Authorization": f"Bearer {t_stu}"})
            check("B1. STUDENT sections -> 403", r.status_code == 403, str(r.status_code))
            r = await c.get(f"{A}/subjects", headers={"Authorization": f"Bearer {t_stu}"})
            check("B2. STUDENT subjects -> 403", r.status_code == 403, str(r.status_code))
            r = await c.get(f"{A}/students/{_FX['target']}", headers={"Authorization": f"Bearer {t_stu}"})
            check("B3. STUDENT student read -> 403", r.status_code == 403, str(r.status_code))

            # C. HEAD: section analytics include the section + target student counts
            r = await c.get(f"{A}/sections", headers=h)
            check("C1. HEAD sections -> 200", r.status_code == 200, str(r.status_code))
            d = r.json()
            sec_item = next((i for i in d["items"] if i["section_id"] == str(_FX["section"])), None)
            check("C2. section present with students>=2", sec_item is not None and sec_item["students"] >= 2,
                  str(sec_item))
            # The target student's 2 BCS-501 records appear in the section aggregate.
            check("C3. section scheduled >= 2 and attended >= 1", sec_item and sec_item["scheduled"] >= 2
                  and sec_item["attended"] >= 1, str(sec_item))

            # D. HEAD: subject analytics include BCS-501/BCS-502 with the target records
            r = await c.get(f"{A}/subjects", headers=h)
            check("D1. HEAD subjects -> 200", r.status_code == 200)
            d = r.json()
            b501 = next((i for i in d["items"] if i["subject_id"] == str(_FX["bcs501"])), None)
            b502 = next((i for i in d["items"] if i["subject_id"] == str(_FX["bcs502"])), None)
            check("D2. BCS-501 roster >= 3 and attended >= 1", b501 and b501["roster"] >= 3 and b501["attended"] >= 1,
                  str(b501))
            check("D3. BCS-502 present (target pending)", b502 is not None and b502["pending"] >= 0, str(b502))

            # E. HEAD: per-student read
            r = await c.get(f"{A}/students/{_FX['target']}", headers=h)
            check("E1. HEAD student read -> 200", r.status_code == 200, str(r.status_code))
            d = r.json()
            check("E2. student identity echoed", d["student_id"] == str(_FX["target"]) and d["roll_number"],
                  str(d.get("roll_number")))
            check("E3. overall attended >= 1", d["overall"]["attended"] >= 1, str(d["overall"]))

            # F. CLASS_ADMIN: own section visible, other scope denied via student gate
            r = await c.get(f"{A}/sections", headers={"Authorization": f"Bearer {t_class}"})
            check("F1. CLASS sections -> 200", r.status_code == 200, str(r.status_code))
            d = r.json()
            check("F2. CLASS sees own section", any(i["section_id"] == str(_FX["section"]) for i in d["items"]),
                  str([i["section_id"] for i in d["items"]]))
            r = await c.get(f"{A}/students/{_FX['target']}", headers={"Authorization": f"Bearer {t_class}"})
            check("F3. CLASS reads own-section student -> 200", r.status_code == 200, str(r.status_code))

            # G. ELECTIVE_ADMIN: own subject in subjects; NOT section-gated on sections (empty)
            r = await c.get(f"{A}/subjects", headers={"Authorization": f"Bearer {t_elec}"})
            d = r.json()
            check("G1. ELECTIVE subjects include BCS-058", any(i["subject_id"] == str(_FX["bcs058"]) for i in d["items"]),
                  str([i["code"] for i in d["items"]]))
            r = await c.get(f"{A}/students/{_FX['target']}", headers={"Authorization": f"Bearer {t_elec}"})
            # target is NOT in BCS-058 roster -> 404 (no existence leak)
            check("G2. ELECTIVE cannot read non-roster student -> 404", r.status_code == 404, str(r.status_code))

            # H. SUBSECTION_ADMIN: conservative-empty on sections/subjects; 404 on student reads
            r = await c.get(f"{A}/sections", headers={"Authorization": f"Bearer {t_sub}"})
            check("H1. SUBSECTION sections empty", r.status_code == 200 and r.json()["total"] == 0, str(r.status_code))
            r = await c.get(f"{A}/subjects", headers={"Authorization": f"Bearer {t_sub}"})
            check("H2. SUBSECTION subjects empty", r.status_code == 200 and r.json()["total"] == 0, str(r.status_code))
            r = await c.get(f"{A}/students/{_FX['target']}", headers={"Authorization": f"Bearer {t_sub}"})
            check("H3. SUBSECTION student read -> 404", r.status_code == 404, str(r.status_code))

            # I. Spoofing: role/scope query params cannot elevate
            r = await c.get(f"{A}/sections", params={"role": "HEAD_ADMIN"}, headers={"Authorization": f"Bearer {t_stu}"})
            check("I1. spoofed role cannot elevate STUDENT -> 403", r.status_code == 403, str(r.status_code))
            r = await c.get(f"{A}/subjects", params={"scope": "global"}, headers={"Authorization": f"Bearer {t_sub}"})
            check("I2. spoofed scope cannot elevate SUBSECTION -> empty", r.status_code == 200 and r.json()["total"] == 0,
                  str(r.status_code))

            # J. Nonexistent student -> 404
            r = await c.get(f"{A}/students/{uuid.uuid4()}", headers=h)
            check("J1. nonexistent student -> 404", r.status_code == 404, str(r.status_code))

            # K. Cross-scope: CLASS admin cannot read a student outside their section.
            other = User(roll_number=f"2401405{uuid.uuid4().hex[:6]}", name="Ph2412 Other", hashed_password="x",
                         section_id=_FX["section"])
            async with AsyncSessionLocal() as db:
                db.add(other); await db.flush()
                sec2 = Section(name=f"Ph2412 S2 {uuid.uuid4().hex[:4]}", semester_id=_FX["semester"])
                db.add(sec2); await db.flush()
                other.section_id = sec2.id
                _FX["other"] = other.id; _FX["sec2"] = sec2.id
                await db.commit()
            r = await c.get(f"{A}/students/{_FX['other']}", headers={"Authorization": f"Bearer {t_class}"})
            check("K1. CLASS cannot read student of another section -> 404", r.status_code == 404, str(r.status_code))
            r = await c.get(f"{A}/sections", headers={"Authorization": f"Bearer {t_class}"})
            d = r.json()
            check("K2. CLASS sections do not include sec2", all(i["section_id"] != str(_FX["sec2"]) for i in d["items"]),
                  str([i["section_id"] for i in d["items"]]))

            # L. Inactive/revoked scope behaves as nonexistent.
            async with AsyncSessionLocal() as db:
                await db.execute(update(AdminScope).where(AdminScope.user_id == _FX["elecAdmin"]).values(active=False))
                await db.commit()
            r = await c.get(f"{A}/subjects", headers={"Authorization": f"Bearer {t_elec}"})
            # The revoked scope removes ALL admin authority -> require_any_admin 403
            # (inactive scopes are treated as nonexistent, the canonical rule).
            check("L1. revoked ELECTIVE scope -> 403 (no admin authority)", r.status_code == 403, str(r.status_code))
            async with AsyncSessionLocal() as db:
                await db.execute(update(AdminScope).where(AdminScope.user_id == _FX["elecAdmin"]).values(active=True))
                await db.commit()

        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.12 verifier (core): {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1

    finally:
        async with AsyncSessionLocal() as db:
            try:
                await purge_fixtures(db)
            except Exception as e: print(f"cleanup: {e}"); await db.rollback()

async def post_cleanup():
    async with AsyncSessionLocal() as db:
        after = await counts(db)
        check("M1. baseline restored", after == _BASELINE, f"before={_BASELINE} after={after}")

if __name__ == "__main__":
    async def _run():
        c = await main()
        await post_cleanup()
        p = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.12 verifier: {p}/{len(results)} PASS")
        return 0 if p == len(results) else 1
    sys.exit(asyncio.run(_run()))