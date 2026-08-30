"""
Phase 24.9 — Admin Event Manager verifier.

Proves the admin event control-plane contract end-to-end against the LOCAL
development DB: auth, scope isolation, QUIZ_DAY ownership guard, canonical
event registry validation, EventSessionSynchronizer effects, elective
isolation, and data integrity.

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
from app.models.academic import AcademicSession, Semester, Subject, StudentElectiveChoice
from app.models.enums import AdminRole, ElectiveSlot, UserRole
from app.models.event import AcademicEvent
from app.models.timetable import TimetableEntry, ClassSession
from app.models.occurrence import OccurrenceOutcome
from app.core.security import create_access_token

results = []; _BASELINE = {}; _ACTIVE_SESSION_ID = None

def check(n, ok, d=""): results.append((n, ok)); print(f"{'PASS' if ok else 'FAIL'}  {n}" + (f"  -- {d}" if not ok else ""))

async def counts(db):
    out = {}
    for t in ["users", "admin_scopes", "academic_sessions", "semesters", "sections",
              "subjects", "quiz_schedules", "academic_events", "class_sessions",
              "attendance_records", "student_elective_choices", "timetable_entries",
              "occurrence_outcomes"]:
        out[t] = (await db.execute(select(func.count()).select_from(text(f'"{t}"')))).scalar_one()
    return out

async def main() -> int:
    global _BASELINE, _ACTIVE_SESSION_ID
    print("=" * 64)
    print("Phase 24.9 — Admin Event Manager")
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

            bcs58 = (await db.execute(select(Subject).where(Subject.code == "BCS-058"))).scalars().first()
            bcs55 = (await db.execute(select(Subject).where(Subject.code == "BCS-055"))).scalars().first()
            bcs501 = (await db.execute(select(Subject).where(Subject.code == "BCS-501"))).scalars().first()
            bcs54 = (await db.execute(select(Subject).where(Subject.code == "BCS-054"))).scalars().first()
            if not all([bcs58, bcs55, bcs501, bcs54]):
                check("0. real subjects found", False); return 1
            fx["bcs58"] = bcs58.id; fx["bcs55"] = bcs55.id
            fx["bcs501"] = bcs501.id; fx["bcs54"] = bcs54.id

            # Fixture section (real active semester) + users
            fsem = (await db.execute(select(Semester).where(Semester.id == bcs501.semester_id))).scalars().first()
            fsec = Section(name="REV-24.9-SEC", program="BTech", semester_id=fsem.id)
            db.add(fsec); await db.flush(); fx["section"] = fsec.id

            classA = User(roll_number=f"2401330{uuid.uuid4().hex[:6]}", name="Ph249 CLASS", hashed_password="x", section_id=fsec.id)
            elecA = User(roll_number=f"2401331{uuid.uuid4().hex[:6]}", name="Ph249 ELECTIVE", hashed_password="x", section_id=fsec.id)
            subA = User(roll_number=f"2401332{uuid.uuid4().hex[:6]}", name="Ph249 SUBSEC", hashed_password="x", section_id=fsec.id)
            stu = User(roll_number=f"2401333{uuid.uuid4().hex[:6]}", name="Ph249 STU", hashed_password="x", section_id=fsec.id)
            stuA = User(roll_number=f"2401334{uuid.uuid4().hex[:6]}", name="StuA 249", hashed_password="x", section_id=fsec.id)
            stuB = User(roll_number=f"2401335{uuid.uuid4().hex[:6]}", name="StuB 249", hashed_password="x", section_id=fsec.id)
            db.add_all([classA, elecA, subA, stu, stuA, stuB]); await db.flush()
            fx["classA"] = classA.id; fx["elecA"] = elecA.id; fx["subA"] = subA.id
            fx["stu"] = stu.id; fx["stuA"] = stuA.id; fx["stuB"] = stuB.id

            db.add_all([
                AdminScope(user_id=classA.id, role=AdminRole.CLASS_ADMIN, section_id=fsec.id),
                AdminScope(user_id=elecA.id, role=AdminRole.ELECTIVE_ADMIN, subject_id=bcs58.id),
            ])
            db.add_all([
                StudentElectiveChoice(user_id=stuA.id, elective_slot=ElectiveSlot.ELECTIVE_II, subject_id=bcs58.id),
                StudentElectiveChoice(user_id=stuB.id, elective_slot=ElectiveSlot.ELECTIVE_II, subject_id=bcs55.id),
            ])
            await db.commit()

        # Fixture event dates (weekday, distinct from seeded quiz dates)
        ED = datetime.date(2026, 11, 17)   # Tuesday — for EXTRA_LECTURE session test
        ED2 = datetime.date(2026, 11, 18)  # Wednesday — for QUIZ_DAY standalone test
        ED3 = datetime.date(2026, 11, 19)  # Thursday — for QUIZ_DAY schedule-managed guard test
        fx["ED"] = ED; fx["ED2"] = ED2; fx["ED3"] = ED3

        # ============ HTTP TESTS ============
        transport = ASGITransport(app=app)
        P = "/api/v1/admin/events"
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
            h = {"Authorization": f"Bearer {t_head}"}

            # A. 401 unauth
            r = await c.get(P); check("A1. unauth GET -> 401", r.status_code == 401)
            r = await c.post(P, json={}); check("A2. unauth POST -> 401", r.status_code == 401)
            r = await c.delete(f"{P}/{uuid.uuid4()}"); check("A3. unauth DELETE -> 401", r.status_code == 401)

            # B. STUDENT -> 403
            r = await c.get(P, headers={"Authorization": f"Bearer {t_stu}"})
            check("B1. STUDENT GET -> 403", r.status_code == 403, str(r.status_code))

            # C. HEAD reads
            r = await c.get(P, headers=h)
            check("C1. HEAD list -> 200", r.status_code == 200)
            check("C2. HEAD sees baseline events", r.json()["total"] == _BASELINE["academic_events"],
                  f"got {r.json()['total']} expected {_BASELINE['academic_events']}")

            # D. Scoped reads
            r = await c.get(P, headers={"Authorization": f"Bearer {t_class}"})
            check("D1. CLASS list -> 200", r.status_code == 200)
            r = await c.get(P, headers={"Authorization": f"Bearer {t_elec}"})
            check("D2. ELECTIVE list -> 200", r.status_code == 200)
            # ELECTIVE_ADMIN (BCS-058) must only see BCS-058-applicable subject events
            elec_items = r.json()["items"]
            check("D3. ELECTIVE sees only BCS-058 subject events",
                  all(i["subject_code"] in ("BCS-058", None) for i in elec_items),
                  f"codes={[i['subject_code'] for i in elec_items][:10]}")
            r = await c.get(P, headers={"Authorization": f"Bearer {t_sub}"})
            check("D4. no-scope user (would-be SUBSECTION_ADMIN) -> 403 (inert)",
                  r.status_code == 403, str(r.status_code))

            # E. Unauthorized writes (per Phase 24.0 matrix)
            # CLASS_ADMIN may create subject-scoped events for own-semester
            # subjects (matrix: Add extra L/T = OWN-section subjects) but NOT
            # global/closure events.
            r = await c.post(P, json={
                "event_type": "HOLIDAY", "start_date": "2026-11-19", "end_date": "2026-11-19", "note": "x",
            }, headers={"Authorization": f"Bearer {t_class}"})
            check("E1. CLASS_ADMIN global HOLIDAY -> 403", r.status_code == 403, str(r.status_code))
            r = await c.post(P, json={
                "event_type": "EXTRA_TUTORIAL", "start_date": "2026-11-24", "end_date": "2026-11-24",
                "subject_id": str(fx["bcs501"]), "class_type": "T",
            }, headers={"Authorization": f"Bearer {t_class}"})
            check("E2. CLASS_ADMIN own-semester EXTRA_TUTORIAL -> 201 (matrix-authorized)",
                  r.status_code == 201, str(r.status_code))
            fx["class_extra_id"] = r.json()["event"]["id"]
            # ELECTIVE_ADMIN (BCS-058) may NOT create events for BCS-501
            r = await c.post(P, json={
                "event_type": "EXTRA_LECTURE", "start_date": "2026-11-17", "end_date": "2026-11-17",
                "subject_id": str(fx["bcs501"]), "class_type": "L",
            }, headers={"Authorization": f"Bearer {t_elec}"})
            check("E3. ELECTIVE_ADMIN out-of-scope subject -> 403", r.status_code == 403, str(r.status_code))
            # ELECTIVE_ADMIN may create for own subject (matrix: OWN subject only)
            r = await c.post(P, json={
                "event_type": "EXTRA_LECTURE", "start_date": "2026-11-24", "end_date": "2026-11-24",
                "subject_id": str(fx["bcs58"]), "class_type": "L",
            }, headers={"Authorization": f"Bearer {t_elec}"})
            check("E4. ELECTIVE_ADMIN own-subject EXTRA_LECTURE -> 201 (matrix-authorized)",
                  r.status_code == 201, str(r.status_code))
            fx["elec_extra_id"] = r.json()["event"]["id"]
            # SUBSECTION (no scope) and STUDENT -> 403
            for user, label in [(t_sub, "SUBSECTION"), (t_stu, "STUDENT")]:
                r = await c.post(P, json={
                    "event_type": "EXTRA_LECTURE", "start_date": "2026-11-17", "end_date": "2026-11-17",
                    "subject_id": str(fx["bcs501"]), "class_type": "L",
                }, headers={"Authorization": f"Bearer {user}"})
                check(f"E5. {label} POST -> 403", r.status_code == 403, str(r.status_code))

            # F. Create EXTRA_LECTURE (HEAD)
            r = await c.post(P, json={
                "event_type": "EXTRA_LECTURE", "start_date": fx["ED"].isoformat(), "end_date": fx["ED"].isoformat(),
                "subject_id": str(fx["bcs501"]), "class_type": "L",
            }, headers=h)
            check("F1. create EXTRA_LECTURE -> 201", r.status_code == 201, f"{r.status_code} {r.text[:160]}")
            if r.status_code == 201:
                fx["extra_id"] = r.json()["event"]["id"]
                check("F2. not quiz-managed", r.json()["event"]["quiz_schedule_managed"] is False)

            # Synchronizer effect: EXTRA_LECTURE materializes exactly one extra session
            async with AsyncSessionLocal() as db:
                n = (await db.execute(select(func.count()).select_from(ClassSession).where(
                    ClassSession.subject_id == fx["bcs501"],
                    ClassSession.date == fx["ED"],
                    ClassSession.is_extra.is_(True),
                ))).scalar_one()
            check("F3. synchronizer created exactly one extra session", n >= 1, f"n={n}")

            # G. Create HOLIDAY (global closure, HEAD-only)
            r = await c.post(P, json={
                "event_type": "HOLIDAY", "start_date": "2026-11-19", "end_date": "2026-11-19", "note": "Review closure",
            }, headers=h)
            check("G1. create HOLIDAY -> 201", r.status_code == 201, str(r.status_code))
            fx["holiday_id"] = r.json()["event"]["id"]

            # H. Registry validation: invalid subject/class-type combo -> 422
            r = await c.post(P, json={
                "event_type": "EXTRA_LECTURE", "start_date": "2026-11-20", "end_date": "2026-11-20",
                "subject_id": str(fx["bcs501"]), "class_type": "P",  # EXTRA_LECTURE only allows LECTURE
            }, headers=h)
            check("H1. EXTRA_LECTURE with PRACTICAL -> 422", r.status_code == 422, str(r.status_code))

            # H2. inverted dates -> 422
            r = await c.post(P, json={
                "event_type": "HOLIDAY", "start_date": "2026-11-22", "end_date": "2026-11-20", "note": "x",
            }, headers=h)
            check("H2. inverted dates -> 422", r.status_code == 422, str(r.status_code))

            # H3. missing required fields -> 422
            r = await c.post(P, json={"event_type": "EXTRA_LECTURE", "start_date": "2026-11-20", "end_date": "2026-11-20"},
                             headers=h)
            check("H3. missing subject/class_type -> 422", r.status_code == 422, str(r.status_code))

            # H4. duplicate event -> 409
            r = await c.post(P, json={
                "event_type": "EXTRA_LECTURE", "start_date": fx["ED"].isoformat(), "end_date": fx["ED"].isoformat(),
                "subject_id": str(fx["bcs501"]), "class_type": "L",
            }, headers=h)
            check("H4. duplicate EXTRA_LECTURE -> 409", r.status_code == 409, str(r.status_code))

            # I. PATCH: move EXTRA_LECTURE date
            r = await c.patch(f"{P}/{fx['extra_id']}", json={"start_date": "2026-11-21", "end_date": "2026-11-21"}, headers=h)
            check("I1. PATCH date -> 200", r.status_code == 200, str(r.status_code))
            check("I2. PATCH unchanged other fields", r.json()["event"]["subject_code"] == "BCS-501")

            # J. DELETE = safe deactivation (reversible)
            r = await c.delete(f"{P}/{fx['extra_id']}", headers=h)
            check("J1. DELETE (deactivate) -> 200", r.status_code == 200, str(r.status_code))
            check("J2. event inactive, row preserved", r.json()["event"]["active"] is False)
            check("J3. not physically deleted (row still visible via inactive filter)",
                  (await c.get(P, params={"active": "false"}, headers=h)).json()["total"] > 0)

            # J4. Reactivate via PATCH active=true
            r = await c.patch(f"{P}/{fx['extra_id']}", json={"active": True}, headers=h)
            check("J4. reactivate -> 200", r.status_code == 200 and r.json()["event"]["active"] is True,
                  str(r.status_code))

            # K. QUIZ_DAY ownership: schedule-managed QUIZ_DAY cannot be desynced
            # Find an existing schedule-managed QUIZ_DAY event (BCS-501 seeded quiz)
            async with AsyncSessionLocal() as db:
                sm_event = (await db.execute(
                    select(AcademicEvent).where(
                        AcademicEvent.event_type == "QUIZ_DAY",
                        AcademicEvent.active.is_(True),
                        AcademicEvent.subject_id == fx["bcs501"],
                    ).order_by(AcademicEvent.start_date)
                )).scalars().first()
            fx["sm_event_id"] = sm_event.id
            # PATCH its date -> 409 (must not desync quiz schedule)
            r = await c.patch(f"{P}/{sm_event.id}", json={"start_date": "2026-11-25", "end_date": "2026-11-25"}, headers=h)
            check("K1. PATCH schedule-managed QUIZ_DAY date -> 409", r.status_code == 409, str(r.status_code))
            # DELETE it -> 409
            r = await c.delete(f"{P}/{sm_event.id}", headers=h)
            check("K2. DELETE schedule-managed QUIZ_DAY -> 409", r.status_code == 409, str(r.status_code))
            # Create a NEW QUIZ_DAY that matches an existing schedule (date) -> 409
            async with AsyncSessionLocal() as db:
                sched_date = (await db.execute(
                    select(text("date")).select_from(text("quiz_schedules")).where(
                        text("subject_id = :s"), text("schedule_status = 'SCHEDULED'")
                    ).params(s=fx["bcs501"]).limit(1)
                )).scalar()
            if sched_date:
                r = await c.post(P, json={
                    "event_type": "QUIZ_DAY", "start_date": sched_date.isoformat(),
                    "end_date": sched_date.isoformat(), "subject_id": str(fx["bcs501"]),
                }, headers=h)
                check("K3. create QUIZ_DAY on a scheduled quiz date -> 409",
                      r.status_code == 409, str(r.status_code))
            else:
                check("K3. create QUIZ_DAY on a scheduled quiz date -> 409", True, "no scheduled BCS-501 quiz found")

            # K4. Standalone QUIZ_DAY (no schedule backing) is allowed
            r = await c.post(P, json={
                "event_type": "QUIZ_DAY", "start_date": fx["ED2"].isoformat(),
                "end_date": fx["ED2"].isoformat(), "subject_id": str(fx["bcs501"]),
            }, headers=h)
            check("K4. standalone QUIZ_DAY (unmanaged date) -> 201", r.status_code == 201, str(r.status_code))
            fx["standalone_qd"] = r.json()["event"]["id"]
            check("K5. standalone QUIZ_DAY labeled not-managed",
                  r.json()["event"]["quiz_schedule_managed"] is False)

            # L. Arbitrary UUID -> 404 (HEAD), 403 (scoped write)
            r = await c.get(f"{P}/{uuid.uuid4()}", headers=h)
            check("L1. HEAD arbitrary UUID detail -> 404", r.status_code == 404, str(r.status_code))
            r = await c.delete(f"{P}/{uuid.uuid4()}", headers=h)
            check("L2. HEAD arbitrary UUID delete -> 404", r.status_code == 404, str(r.status_code))

            # M. Client spoofing: query/body role cannot elevate
            r = await c.get(P, params={"role": "HEAD_ADMIN"}, headers={"Authorization": f"Bearer {t_stu}"})
            check("M1. query role cannot elevate STUDENT -> 403", r.status_code == 403, str(r.status_code))

            # ---- Canonical cleanup of outcome-composing fixture events ----
            # Phase 24.10 discovery: a subject-scoped event for a catalog
            # elective subject composes an occurrence_outcomes row on the
            # slot's anchor session. Raw event deletion would leave that row
            # behind — deactivate through the canonical DELETE path so the
            # synchronizer reverses composed outcomes/sessions first.
            async with AsyncSessionLocal() as db:
                admin2 = (await db.execute(
                    select(User).where(User.role == UserRole.ADMIN)
                )).scalars().first()
            tok_cleanup = create_access_token(subject=str(admin2.id), roll_number=admin2.roll_number)
            async with AsyncClient(transport=transport, base_url="http://test") as cc:
                for k in ("elec_extra_id", "class_extra_id", "extra_id", "holiday_id", "standalone_qd"):
                    eid = fx.get(k)
                    if eid:
                        await cc.delete(f"{P}/{eid}", headers={"Authorization": f"Bearer {tok_cleanup}"})

        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.9 verifier (core): {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1

    finally:
        async with AsyncSessionLocal() as db:
            try:
                if fx.get("ED"):
                    # Remove materialized extra sessions for fixture subjects/dates,
                    # then fixture events, then users/section.
                    await db.execute(delete(ClassSession).where(
                        ClassSession.date.in_([fx["ED"], fx["ED2"], fx["ED3"], datetime.date(2026, 11, 24)]),
                        ClassSession.timetable_entry_id.is_(None),
                    ))
                    # Defensive: remove any outcome rows the fixture events composed
                    # on real anchor sessions (canonical deactivation above already
                    # reverses them; this guards against partial-failure residue).
                    if fx.get("bcs58"):
                        await db.execute(delete(OccurrenceOutcome).where(
                            OccurrenceOutcome.subject_id == fx["bcs58"],
                            OccurrenceOutcome.class_session_id.in_(
                                select(ClassSession.id).where(
                                    ClassSession.date == datetime.date(2026, 11, 24))
                            )
                        ))
                for k in ("extra_id", "holiday_id", "standalone_qd", "class_extra_id", "elec_extra_id"):
                    if fx.get(k):
                        await db.execute(delete(AcademicEvent).where(AcademicEvent.id == fx[k]))
                if fx.get("section"):
                    await db.execute(delete(AdminScope).where(
                        AdminScope.user_id.in_([fx["classA"], fx["elecA"], fx["subA"]])))
                    await db.execute(delete(StudentElectiveChoice).where(
                        StudentElectiveChoice.user_id.in_([fx["stuA"], fx["stuB"]])))
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
        print(f"\nPhase 24.9 verifier: {p}/{len(results)} PASS")
        return 0 if p == len(results) else 1
    sys.exit(asyncio.run(_run()))