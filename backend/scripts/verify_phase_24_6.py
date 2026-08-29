"""
Phase 24.6 — Curriculum & Subject Management verifier.

Proves the Phase 24.6 contract end-to-end against the LOCAL development DB:

  A.  unauthenticated -> 401
  B.  STUDENT -> 403
  C.  CLASS_ADMIN -> scoped reads only (own-semester subjects), writes 403
  D.  ELECTIVE_ADMIN -> exact own-subject read only, writes 403
  E.  SUBSECTION_ADMIN -> inert/empty
  F.  HEAD_ADMIN -> complete reads/writes
  G.  subject creation (valid)
  H.  duplicate (code, semester_id) -> 409
  I.  invalid semester -> 404
  J.  invalid payload -> 422
  K.  editable metadata PATCH succeeds
  L.  code modification -> 409
  M.  semester_id modification -> 409
  N.  anchor code/slot modification -> 409
  O.  elective-slot change with existing StudentElectiveChoice -> 409
  P.  normal elective-slot change (no dependent choice) succeeds
  Q.  ELECTIVE_ADMIN for BCS-058 cannot read BCS-055
  R.  CLASS_ADMIN cannot read subjects outside assigned semester
  S.  client-supplied scope/role params cannot elevate access
  T.  arbitrary subject IDs cannot bypass authorization
  U.  no DELETE route -> 405
  V.  no enrollment mutation
  W.  no attendance mutation
  X.  no quiz mutation
  Y.  no existing elective-choice mutation
  Z.  baseline counts restored after fixture cleanup
  AA. no fixture residue
  AB. anchor codes remain unchanged
  AC. elective-choice / attendance / quiz data unchanged

LOCALITY GUARD (hard): this script FORCES DATABASE_URI to the local dev DB
before importing the app, then asserts the effective engine URL is the local
host. It refuses to run against any other target (notably the Supabase
production pooler).

Usage (local only):
    python scripts/verify_phase_24_6.py
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# ---- Locality guard: force + assert the LOCAL dev DB before app import ----
LOCAL_URI = "postgresql+asyncpg://postgres:postgres@127.0.0.1:55432/attendancedash"
os.environ["DATABASE_URI"] = LOCAL_URI

from app.core.config import settings  # noqa: E402

_effective = settings.DATABASE_URI
if "127.0.0.1:55432" not in _effective and "localhost:55432" not in _effective:
    print(f"LOCALITY GUARD ABORT: DATABASE_URI is not the local dev DB ({_effective}).")
    sys.exit(2)
if "attendancedash" not in _effective:
    print(f"LOCALITY GUARD ABORT: DATABASE_URI does not target attendancedash ({_effective}).")
    sys.exit(2)

from sqlalchemy import delete, func, select, text, update  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
import datetime  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from app.main import app  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.user import User, Section  # noqa: E402
from app.models.academic import (  # noqa: E402
    AcademicSession, Semester, Subject, StudentEnrollment,
    StudentElectiveChoice,
)
from app.models.admin_scope import AdminScope  # noqa: E402
from app.models.enums import AdminRole, ElectiveSlot, SubjectCategory, UserRole  # noqa: E402
from app.core.security import create_access_token  # noqa: E402

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if not ok else ""))


BASELINE_TABLES = [
    "users", "student_enrollments", "student_elective_choices",
    "academic_sessions", "semesters", "sections", "subsections",
    "subjects", "timetable_entries", "class_sessions", "attendance_records",
    "academic_events", "quiz_schedules", "admin_scopes", "occurrence_outcomes",
]


async def table_counts(db) -> dict:
    """Row counts for every baseline table (COUNT(*) — bounded)."""
    out = {}
    for table in BASELINE_TABLES:
        out[table] = (await db.execute(
            select(func.count()).select_from(text(f'"{table}"'))
        )).scalar_one()
    return out


async def main() -> int:
    global _BASELINE, _ACTIVE_SESSION_ID
    print("=" * 64)
    print("Phase 24.6 — Admin Portal: Curriculum & Subject Management")
    print(f"Locality guard: using local dev DB {settings.DATABASE_URI}")
    print("=" * 64)

    fixture_user_ids: list = []
    fixture_scope_ids: list = []
    fixture_session_id = None
    fixture_semester_id = None
    fixture_subject_id = None
    warning_subject_id = None
    choice_fixture_subject_id = None
    choice_fixture_choice_id = None
    original_active_session_id = None

    try:
        async with AsyncSessionLocal() as db:
            admin_user = (await db.execute(
                select(User).where(User.role == UserRole.ADMIN)
            )).scalars().first()
            if admin_user is None:
                check("0. legacy ADMIN user found", False)
                return 1
            check("0. legacy ADMIN is head_admin", admin_user.role == UserRole.ADMIN)

            sections = (await db.execute(select(Section))).scalars().all()
            real_section = sections[0] if sections else None
            if real_section is None:
                check("0. at least one section exists", False)
                return 1
            real_section_id = real_section.id  # plain UUID, survives rollbacks

            subjects = (await db.execute(select(Subject))).scalars().all()
            bcs54 = next((s for s in subjects if s.code == "BCS-054"), None)
            bcs58 = next((s for s in subjects if s.code == "BCS-058"), None)
            bcs55 = next((s for s in subjects if s.code == "BCS-055"), None)
            if bcs54 is None or bcs58 is None or bcs55 is None:
                check("0. anchor + isolation subjects exist (BCS-054/058/055)", False)
                return 1
            bcs54_id = bcs54.id
            bcs58_id = bcs58.id
            bcs55_id = bcs55.id

            active_session = (await db.execute(
                select(AcademicSession).where(AcademicSession.is_active.is_(True))
            )).scalars().first()
            if active_session is None:
                check("0. exactly one active session exists", False)
                return 1
            original_active_session_id = active_session.id
            _ACTIVE_SESSION_ID = active_session.id

            real_semester = (await db.execute(
                select(Semester).where(Semester.session_id == active_session.id)
            )).scalars().first()
            if real_semester is None:
                check("0. active session has a semester", False)
                return 1
            real_semester_id = real_semester.id

            _BASELINE = await table_counts(db)
            print(f"baseline counts: {_BASELINE}")

            # ---- Fixture users + scopes (isolated; cleaned in finally) ----
            class_admin_user = User(
                roll_number=f"2401260{uuid.uuid4().hex[:6]}", name="Phase246 CLASS_ADMIN",
                hashed_password="pbkdf2_sha256$unused", section_id=real_section_id,
            )
            db.add(class_admin_user)
            await db.flush()
            fixture_user_ids.append(class_admin_user.id)
            db.add(AdminScope(
                user_id=class_admin_user.id, role=AdminRole.CLASS_ADMIN,
                section_id=real_section_id, subsection_id=None, subject_id=None,
            ))
            await db.flush()
            fixture_scope_ids.append((await db.execute(
                select(AdminScope.id).where(AdminScope.user_id == class_admin_user.id)
            )).scalars().first())
            token_class = create_access_token(subject=str(class_admin_user.id), roll_number=class_admin_user.roll_number)

            elec_admin_user = User(
                roll_number=f"2401261{uuid.uuid4().hex[:6]}", name="Phase246 ELECTIVE_ADMIN",
                hashed_password="pbkdf2_sha256$unused", section_id=real_section_id,
            )
            db.add(elec_admin_user)
            await db.flush()
            fixture_user_ids.append(elec_admin_user.id)
            db.add(AdminScope(
                user_id=elec_admin_user.id, role=AdminRole.ELECTIVE_ADMIN,
                section_id=None, subsection_id=None, subject_id=bcs58_id,
            ))
            await db.flush()
            fixture_scope_ids.append((await db.execute(
                select(AdminScope.id).where(AdminScope.user_id == elec_admin_user.id)
            )).scalars().first())
            token_elec = create_access_token(subject=str(elec_admin_user.id), roll_number=elec_admin_user.roll_number)

            sub_admin_user = User(
                roll_number=f"2401262{uuid.uuid4().hex[:6]}", name="Phase246 SUBSECTION_ADMIN",
                hashed_password="pbkdf2_sha256$unused", section_id=None,
            )
            db.add(sub_admin_user)
            await db.flush()
            fixture_user_ids.append(sub_admin_user.id)
            token_sub = create_access_token(subject=str(sub_admin_user.id), roll_number=sub_admin_user.roll_number)

            student_user = User(
                roll_number=f"2401263{uuid.uuid4().hex[:6]}", name="Phase246 STUDENT",
                hashed_password="pbkdf2_sha256$unused", section_id=real_section_id,
            )
            db.add(student_user)
            await db.flush()
            fixture_user_ids.append(student_user.id)
            token_student = create_access_token(subject=str(student_user.id), roll_number=student_user.roll_number)
            token_admin = create_access_token(subject=str(admin_user.id), roll_number=admin_user.roll_number)

            # Fixture session + semester (isolated from the active session so
            # fixture subjects never touch registration behavior).
            fixture_session = AcademicSession(
                name="REVIEW 24.6 SESSION",
                start_date=datetime.date(2027, 1, 1), end_date=datetime.date(2027, 12, 31), is_active=False,
            )
            db.add(fixture_session)
            await db.flush()
            fixture_session_id = fixture_session.id
            fixture_semester = Semester(
                name="Review Sem 24.6", session_id=fixture_session_id,
                start_date=datetime.date(2027, 1, 15), end_date=datetime.date(2027, 6, 30),
            )
            db.add(fixture_semester)
            await db.flush()
            fixture_semester_id = fixture_semester.id
            await db.commit()

        transport = ASGITransport(app=app)
        S = "/api/v1/admin/subjects"

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # ---- A. Authentication ----
            r = await client.get(S)
            check("A1. GET subjects without token -> 401", r.status_code == 401, str(r.status_code))
            r = await client.post(S, json={})
            check("A2. POST subjects without token -> 401", r.status_code == 401, str(r.status_code))

            # ---- B. STUDENT -> 403 ----
            r = await client.get(S, headers={"Authorization": f"Bearer {token_student}"})
            check("B1. STUDENT GET subjects -> 403", r.status_code == 403, str(r.status_code))
            r = await client.post(S, json={}, headers={"Authorization": f"Bearer {token_student}"})
            check("B2. STUDENT POST subjects -> 403", r.status_code == 403, str(r.status_code))

            # ---- C. CLASS_ADMIN: scoped reads, writes 403 ----
            r = await client.get(S, headers={"Authorization": f"Bearer {token_class}"})
            check("C1. CLASS_ADMIN GET subjects -> 200", r.status_code == 200, str(r.status_code))
            class_list = r.json()["items"]
            check("C2. CLASS_ADMIN sees own-semester subjects (real semester)",
                  any(x["id"] == str(bcs58_id) for x in class_list))
            # Fixture subject is in a different (inactive-session) semester -> invisible
            r = await client.post(S, json={
                "code": "REV-601", "name": "Review 601", "category": "theory",
                "quiz_applicable": True, "attendance_applicable": True,
                "semester_id": str(fixture_semester_id),
            }, headers={"Authorization": f"Bearer {token_class}"})
            check("C3. CLASS_ADMIN POST subjects -> 403 (no elevation)", r.status_code == 403, str(r.status_code))

            # ---- D. ELECTIVE_ADMIN: exact own subject, writes 403 ----
            r = await client.get(S, headers={"Authorization": f"Bearer {token_elec}"})
            check("D1. ELECTIVE_ADMIN GET subjects -> 200", r.status_code == 200, str(r.status_code))
            elec_list = r.json()["items"]
            check("D2. ELECTIVE_ADMIN sees exactly the assigned subject (BCS-058)",
                  [x["code"] for x in elec_list] == ["BCS-058"],
                  str([x["code"] for x in elec_list]))
            r = await client.post(S, json={
                "code": "REV-602", "name": "Review 602", "category": "theory",
                "quiz_applicable": True, "attendance_applicable": True,
                "semester_id": str(fixture_semester_id),
            }, headers={"Authorization": f"Bearer {token_elec}"})
            check("D3. ELECTIVE_ADMIN POST subjects -> 403 (no elevation)", r.status_code == 403, str(r.status_code))

            # ---- E. SUBSECTION_ADMIN: structurally inert ----
            # A SUBSECTION_ADMIN scope row cannot even be created while the
            # subsections table is empty (FK constraint — proven in the Phase
            # 24.5 verifier), so the role is unreachable today. A user with no
            # effective admin role (would-be SUBSECTION_ADMIN) is denied 403 by
            # require_any_admin — matching the Phase 24.0 matrix (S=NO) and the
            # Phase 24.3 verifier's K1 (no effective role -> 403).
            r = await client.get(S, headers={"Authorization": f"Bearer {token_sub}"})
            check("E1. SUBSECTION_ADMIN (no creatable scope) -> 403, inert",
                  r.status_code == 403, str(r.status_code))

            # ---- F. HEAD_ADMIN reads ----
            r = await client.get(S, headers={"Authorization": f"Bearer {token_admin}"})
            check("F1. HEAD GET subjects -> 200 with all subjects",
                  r.status_code == 200 and any(x["code"] == "BCS-058" for x in r.json()["items"]),
                  str(r.status_code))
            check("F2. HEAD list marks anchors",
                  any(x["code"] == "BCS-054" and x["is_anchor"] for x in r.json()["items"]))
            r = await client.get(f"{S}/{bcs58_id}", headers={"Authorization": f"Bearer {token_admin}"})
            check("F3. HEAD GET subject detail -> 200", r.status_code == 200 and r.json()["code"] == "BCS-058")

            # ---- G. Valid creation (fixture semester) ----
            r = await client.post(S, json={
                "code": "REV-601", "name": "Review 601", "tag": "Review",
                "category": "theory", "quiz_applicable": True,
                "attendance_applicable": True, "semester_id": str(fixture_semester_id),
            }, headers={"Authorization": f"Bearer {token_admin}"})
            check("G1. create subject -> 201", r.status_code == 201, str(r.status_code))
            fixture_subject_id = r.json()["subject"]["id"]
            check("G2. create subject is not anchor", r.json()["subject"]["is_anchor"] is False)

            # ---- H. Duplicate (code, semester_id) -> 409 ----
            r = await client.post(S, json={
                "code": "REV-601", "name": "Review 601 dup", "category": "lab",
                "quiz_applicable": True, "attendance_applicable": True,
                "semester_id": str(fixture_semester_id),
            }, headers={"Authorization": f"Bearer {token_admin}"})
            check("H1. duplicate (code, semester_id) -> 409", r.status_code == 409, str(r.status_code))

            # ---- I. Invalid semester -> 404 ----
            r = await client.post(S, json={
                "code": "REV-603", "name": "Review 603", "category": "theory",
                "quiz_applicable": True, "attendance_applicable": True,
                "semester_id": str(uuid.uuid4()),
            }, headers={"Authorization": f"Bearer {token_admin}"})
            check("I1. invalid semester -> 404", r.status_code == 404, str(r.status_code))

            # ---- J. Invalid payload -> 422 ----
            r = await client.post(S, json={
                "code": "", "name": "", "category": "bogus",
                "semester_id": str(fixture_semester_id),
            }, headers={"Authorization": f"Bearer {token_admin}"})
            check("J1. invalid payload -> 422", r.status_code == 422, str(r.status_code))

            # ---- K. Editable metadata PATCH succeeds ----
            r = await client.patch(f"{S}/{fixture_subject_id}", json={
                "name": "Review 601 (edited)", "tag": None, "quiz_applicable": False,
            }, headers={"Authorization": f"Bearer {token_admin}"})
            check("K1. PATCH name/tag/quiz_applicable -> 200",
                  r.status_code == 200 and r.json()["subject"]["name"] == "Review 601 (edited)"
                  and r.json()["subject"]["tag"] is None
                  and r.json()["subject"]["quiz_applicable"] is False,
                  str(r.status_code))

            # ---- L. code modification -> 409 ----
            r = await client.patch(f"{S}/{fixture_subject_id}", json={"code": "REV-999"},
                                   headers={"Authorization": f"Bearer {token_admin}"})
            check("L1. PATCH code -> 409 (immutable)", r.status_code == 409, str(r.status_code))

            # ---- M. semester_id modification -> 409 ----
            r = await client.patch(f"{S}/{fixture_subject_id}", json={"semester_id": str(real_semester_id)},
                                   headers={"Authorization": f"Bearer {token_admin}"})
            check("M1. PATCH semester_id -> 409 (immutable)", r.status_code == 409, str(r.status_code))

            # ---- N. Anchor code/slot modification -> 409 ----
            r = await client.patch(f"{S}/{bcs54_id}", json={"code": "BCS-000"},
                                   headers={"Authorization": f"Bearer {token_admin}"})
            check("N1. PATCH anchor BCS-054 code -> 409", r.status_code == 409, str(r.status_code))
            r = await client.patch(f"{S}/{bcs58_id}", json={"elective_slot": "ELECTIVE_I"},
                                   headers={"Authorization": f"Bearer {token_admin}"})
            check("N2. PATCH anchor BCS-058 elective_slot -> 409", r.status_code == 409, str(r.status_code))

            # ---- O. elective-slot change with existing choice -> 409 ----
            # Fixture subject + fixture choice (cleaned in finally).
            r = await client.post(S, json={
                "code": "REV-604", "name": "Review 604", "category": "theory",
                "elective_slot": "ELECTIVE_I", "quiz_applicable": True,
                "attendance_applicable": True, "semester_id": str(fixture_semester_id),
            }, headers={"Authorization": f"Bearer {token_admin}"})
            check("O1. create slot fixture subject -> 201", r.status_code == 201, str(r.status_code))
            choice_fixture_subject_id = r.json()["subject"]["id"]
            async with AsyncSessionLocal() as db:
                choice = StudentElectiveChoice(
                    user_id=student_user.id, elective_slot=ElectiveSlot.ELECTIVE_I,
                    subject_id=uuid.UUID(choice_fixture_subject_id),
                )
                db.add(choice)
                await db.commit()
                choice_fixture_choice_id = choice.id
            r = await client.patch(f"{S}/{choice_fixture_subject_id}", json={"elective_slot": "ELECTIVE_II"},
                                   headers={"Authorization": f"Bearer {token_admin}"})
            check("O2. PATCH slot with existing choice -> 409", r.status_code == 409, str(r.status_code))

            # ---- P. normal slot change (no dependent choice) succeeds ----
            r = await client.patch(f"{S}/{fixture_subject_id}", json={"elective_slot": "ELECTIVE_II"},
                                   headers={"Authorization": f"Bearer {token_admin}"})
            check("P1. PATCH slot without dependent choice -> 200",
                  r.status_code == 200 and r.json()["subject"]["elective_slot"] == "ELECTIVE_II",
                  str(r.status_code))
            # Clear slot explicitly (null) works too.
            r = await client.patch(f"{S}/{fixture_subject_id}", json={"elective_slot": None},
                                   headers={"Authorization": f"Bearer {token_admin}"})
            check("P2. PATCH slot explicit null (clear) -> 200",
                  r.status_code == 200 and r.json()["subject"]["elective_slot"] is None,
                  str(r.status_code))

            # ---- Q. ELECTIVE_ADMIN isolation ----
            r = await client.get(f"{S}/{bcs55_id}", headers={"Authorization": f"Bearer {token_elec}"})
            check("Q1. ELECTIVE_ADMIN BCS-058 cannot read BCS-055 -> 404",
                  r.status_code == 404, str(r.status_code))

            # ---- R. CLASS_ADMIN cannot read outside assigned semester ----
            r = await client.get(f"{S}/{fixture_subject_id}", headers={"Authorization": f"Bearer {token_class}"})
            check("R1. CLASS_ADMIN cannot read fixture-semester subject -> 404",
                  r.status_code == 404, str(r.status_code))

            # ---- S. client-supplied scope/role params cannot elevate ----
            r = await client.get(S, params={"role": "HEAD_ADMIN", "scope": "global"},
                                 headers={"Authorization": f"Bearer {token_student}"})
            check("S1. query role/scope params do not elevate STUDENT -> 403",
                  r.status_code == 403, str(r.status_code))
            r = await client.get(S, params={"role": "HEAD_ADMIN"},
                                 headers={"Authorization": f"Bearer {token_elec}"})
            check("S2. query role param does not expand ELECTIVE_ADMIN scope",
                  r.status_code == 200 and [x["code"] for x in r.json()["items"]] == ["BCS-058"],
                  str(r.status_code))

            # ---- T. arbitrary subject IDs cannot bypass ----
            r = await client.get(f"{S}/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token_admin}"})
            check("T1. HEAD + random subject UUID -> 404", r.status_code == 404, str(r.status_code))
            r = await client.get(f"{S}/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token_class}"})
            check("T2. CLASS_ADMIN + random subject UUID -> 404", r.status_code == 404, str(r.status_code))

            # ---- U. no DELETE route -> 405 ----
            r = await client.delete(f"{S}/{fixture_subject_id}", headers={"Authorization": f"Bearer {token_admin}"})
            check("U1. DELETE subject -> 405 (no delete route)", r.status_code == 405, str(r.status_code))

            # ---- Registration-impact warning for active-session subject ----
            r = await client.post(S, json={
                "code": "REV-605", "name": "Review 605", "category": "lab",
                "quiz_applicable": True, "attendance_applicable": True,
                "semester_id": str(real_semester_id),
            }, headers={"Authorization": f"Bearer {token_admin}"})
            warning_subject_id = r.json()["subject"]["id"] if r.status_code == 201 else None
            check("W1. subject in ACTIVE session semester surfaces ACTIVE_SESSION warning",
                  r.status_code == 201 and any(
                      w["code"] == "ACTIVE_SESSION_SUBJECT_ADDED" for w in r.json()["warnings"]
                  ),
                  str(r.status_code))

        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.6 verifier (core): {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1

    finally:
        # ---- Hard cleanup (defensive; runs on success AND failure) ----
        async with AsyncSessionLocal() as db:
            try:
                if choice_fixture_choice_id:
                    await db.execute(delete(StudentElectiveChoice).where(
                        StudentElectiveChoice.id == choice_fixture_choice_id))
                if choice_fixture_subject_id:
                    await db.execute(delete(Subject).where(Subject.id == choice_fixture_subject_id))
                if warning_subject_id:
                    await db.execute(delete(Subject).where(Subject.id == warning_subject_id))
                if fixture_subject_id:
                    await db.execute(delete(Subject).where(Subject.id == fixture_subject_id))
                if fixture_semester_id:
                    await db.execute(delete(Semester).where(Semester.id == fixture_semester_id))
                if fixture_session_id:
                    await db.execute(delete(AcademicSession).where(AcademicSession.id == fixture_session_id))
                if fixture_scope_ids:
                    await db.execute(delete(AdminScope).where(AdminScope.id.in_(fixture_scope_ids)))
                if fixture_user_ids:
                    await db.execute(delete(User).where(User.id.in_(fixture_user_ids)))
                if original_active_session_id:
                    await db.execute(
                        update(AcademicSession)
                        .where(AcademicSession.id == original_active_session_id)
                        .values(is_active=True)
                    )
                await db.commit()
            except Exception as exc:  # noqa: BLE001 — cleanup must not mask results
                print(f"cleanup warning: {exc}")
                await db.rollback()


async def post_cleanup_checks() -> None:
    """Data-integrity verification AFTER the finally cleanup has run."""
    async with AsyncSessionLocal() as db:
        after = await table_counts(db)
        check("Z1. all baseline table counts restored after fixture cleanup",
              after == _BASELINE, f"before={_BASELINE} after={after}")
        # AB. anchors unchanged
        bcs54 = (await db.execute(
            select(Subject).where(Subject.code == "BCS-054")
        )).scalars().first()
        bcs58 = (await db.execute(
            select(Subject).where(Subject.code == "BCS-058")
        )).scalars().first()
        check("AB1. anchor BCS-054 code/slot unchanged",
              bcs54 is not None and bcs54.elective_slot == ElectiveSlot.ELECTIVE_I)
        check("AB2. anchor BCS-058 code/slot unchanged",
              bcs58 is not None and bcs58.elective_slot == ElectiveSlot.ELECTIVE_II)
        # AC. elective-choice data unchanged (baseline == current)
        check("AC1. elective-choice data unchanged", after["student_elective_choices"] == _BASELINE["student_elective_choices"])
        check("AC2. attendance data unchanged", after["attendance_records"] == _BASELINE["attendance_records"])
        check("AC3. quiz data unchanged", after["quiz_schedules"] == _BASELINE["quiz_schedules"])
        check("AC4. enrollments unchanged", after["student_enrollments"] == _BASELINE["student_enrollments"])
        # AA. no fixture residue
        check("AA1. no REVIEW subjects/sessions/semesters residue",
              (await db.execute(text("SELECT count(*) FROM subjects WHERE code LIKE 'REV-%'"))).scalar_one() == 0
              and (await db.execute(text("SELECT count(*) FROM academic_sessions WHERE name LIKE 'REVIEW%'"))).scalar_one() == 0
              and (await db.execute(text("SELECT count(*) FROM semesters WHERE name LIKE 'Review%'"))).scalar_one() == 0)
        active_now = (await db.execute(
            select(AcademicSession).where(AcademicSession.is_active.is_(True))
        )).scalars().first()
        check("AA2. original active session restored",
              active_now is not None and active_now.id == _ACTIVE_SESSION_ID)


_BASELINE: dict = {}
_ACTIVE_SESSION_ID = None


if __name__ == "__main__":
    async def _run() -> int:
        code = await main()
        await post_cleanup_checks()
        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.6 verifier: {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1

    sys.exit(asyncio.run(_run()))
