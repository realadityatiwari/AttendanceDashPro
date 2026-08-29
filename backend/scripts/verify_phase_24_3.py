"""
Phase 24.3 — Admin Portal: scoped student management (READ) verifier.

Proves the Phase 24.3 contract end-to-end against the LOCAL development DB:

  A. unauthenticated access -> 401
  B. STUDENT (no effective admin role) -> 403
  C. HEAD_ADMIN (legacy ADMIN) -> 200, all STUDENT-role accounts visible
  D. HEAD_ADMIN search (q) filters roll/name, pagination consistent
  E. HEAD_ADMIN detail -> 200 with authoritative academic context
  F. HEAD_ADMIN detail for nonexistent student -> 404
  G. CLASS_ADMIN -> only students of the assigned section
  H. CLASS_ADMIN -> out-of-section student detail is 404 (no existence leak)
  I. ELECTIVE_ADMIN -> only students whose choice resolves to the assigned subject
  J. ELECTIVE_ADMIN -> out-of-roster student detail is 404 (no cross-subject access)
  K. SUBSECTION_ADMIN -> conservative empty list (no authoritative subsection data)
  L. no client-supplied scope parameter exists in the contract
  M. data unchanged (student/choice counts before/after)
  N. scope union: admin holding CLASS + ELECTIVE sees the union

LOCALITY GUARD (hard): this script FORCES DATABASE_URI to the local dev DB
before importing the app, then asserts the effective engine URL is the local
host. It refuses to run against any other target (notably the Supabase
production pooler that the ambient backend .env points at).

Usage (local only):
    python scripts/verify_phase_24_3.py
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

from sqlalchemy import delete, func, select  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from app.main import app  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.user import User, Section, Subsection  # noqa: E402
from app.models.academic import Subject, StudentEnrollment, StudentElectiveChoice  # noqa: E402
from app.models.admin_scope import AdminScope  # noqa: E402
from app.models.enums import AdminRole, ElectiveSlot  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.services.authorization_service import AuthorizationService  # noqa: E402

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if not ok else ""))


async def main() -> int:
    print("=" * 60)
    print("Phase 24.3 — Admin Portal: scoped student management (READ)")
    print(f"Locality guard: using local dev DB {settings.DATABASE_URI}")
    print("=" * 60)

    fixture_user_ids: list = []
    fixture_scope_ids: list = []
    fixture_choice_ids: list = []

    try:
        async with AsyncSessionLocal() as db:
            admin_user = (await db.execute(
                select(User).where(User.roll_number == "2401220100027")
            )).scalars().first()
            if admin_user is None:
                check("0. legacy ADMIN user found", False)
                return 1

            sections = (await db.execute(select(Section))).scalars().all()
            if not sections:
                check("0. at least one section exists", False)
                return 1
            section = sections[0]
            subjects = (await db.execute(select(Subject))).scalars().all()
            by_code = {s.code: s for s in subjects}
            bcs58 = by_code.get("BCS-058")
            bcs55 = by_code.get("BCS-055")

            users_before = (await db.execute(
                select(func.count()).select_from(User)
            )).scalar()
            choices_before = (await db.execute(
                select(func.count()).select_from(StudentElectiveChoice)
            )).scalar()

            authz = AuthorizationService(db)
            check("0. legacy ADMIN is head_admin", await authz.is_head_admin(admin_user))
            token_admin = create_access_token(subject=str(admin_user.id), roll_number=admin_user.roll_number)

            # ---- Fixtures: two students (one in `section`, one out-of-scope
            # with an unrelated section-less state), one CLASS_ADMIN scope on
            # `section`, one ELECTIVE_ADMIN scope on BCS-058. ----
            student_a = User(
                roll_number=f"2401250{uuid.uuid4().hex[:6]}", name="Phase243 Student A",
                hashed_password="pbkdf2_sha256$unused", section_id=section.id,
            )
            db.add(student_a)
            await db.flush()
            fixture_user_ids.append(student_a.id)
            student_b = User(
                roll_number=f"2401250{uuid.uuid4().hex[:6]}", name="Phase243 Student B",
                hashed_password="pbkdf2_sha256$unused", section_id=None,
            )
            db.add(student_b)
            await db.flush()
            fixture_user_ids.append(student_b.id)

            class_admin = User(
                roll_number=f"2401271{uuid.uuid4().hex[:6]}", name="Phase243 CLASS_ADMIN",
                hashed_password="pbkdf2_sha256$unused", section_id=section.id,
            )
            db.add(class_admin)
            await db.flush()
            fixture_user_ids.append(class_admin.id)
            class_scope = AdminScope(
                user_id=class_admin.id, role=AdminRole.CLASS_ADMIN,
                section_id=section.id, subsection_id=None, subject_id=None,
            )
            db.add(class_scope)
            await db.flush()
            fixture_scope_ids.append(class_scope.id)
            token_class = create_access_token(subject=str(class_admin.id), roll_number=class_admin.roll_number)

            elec_admin = User(
                roll_number=f"2401272{uuid.uuid4().hex[:6]}", name="Phase243 ELECTIVE_ADMIN",
                hashed_password="pbkdf2_sha256$unused", section_id=section.id,
            )
            db.add(elec_admin)
            await db.flush()
            fixture_user_ids.append(elec_admin.id)
            elec_scope = AdminScope(
                user_id=elec_admin.id, role=AdminRole.ELECTIVE_ADMIN,
                section_id=None, subsection_id=None, subject_id=bcs58.id if bcs58 else None,
            )
            db.add(elec_scope)
            await db.flush()
            fixture_scope_ids.append(elec_scope.id)
            token_elec = create_access_token(subject=str(elec_admin.id), roll_number=elec_admin.roll_number)

            # Union-scope admin: holds BOTH a CLASS_ADMIN scope on `section` AND
            # an ELECTIVE_ADMIN scope on BCS-058. Visible set = section members
            # (student_a, student_no_role, student_c if created) UNION roster
            # members (student_a via BCS-058 choice).
            union_admin = User(
                roll_number=f"2401276{uuid.uuid4().hex[:6]}", name="Phase243 UNION_ADMIN",
                hashed_password="pbkdf2_sha256$unused", section_id=section.id,
            )
            db.add(union_admin)
            await db.flush()
            fixture_user_ids.append(union_admin.id)
            union_scope_class = AdminScope(
                user_id=union_admin.id, role=AdminRole.CLASS_ADMIN,
                section_id=section.id, subsection_id=None, subject_id=None,
            )
            db.add(union_scope_class)
            await db.flush()
            fixture_scope_ids.append(union_scope_class.id)
            union_scope_elec = AdminScope(
                user_id=union_admin.id, role=AdminRole.ELECTIVE_ADMIN,
                section_id=None, subsection_id=None, subject_id=bcs58.id if bcs58 else None,
            )
            db.add(union_scope_elec)
            await db.flush()
            fixture_scope_ids.append(union_scope_elec.id)
            token_union = create_access_token(subject=str(union_admin.id), roll_number=union_admin.roll_number)

            sub_admin = User(
                roll_number=f"2401273{uuid.uuid4().hex[:6]}", name="Phase243 SUBSECTION_ADMIN",
                hashed_password="pbkdf2_sha256$unused", section_id=None,
            )
            db.add(sub_admin)
            await db.flush()
            fixture_user_ids.append(sub_admin.id)
            token_sub = create_access_token(subject=str(sub_admin.id), roll_number=sub_admin.roll_number)

            student_no_role = User(
                roll_number=f"2401274{uuid.uuid4().hex[:6]}", name="Phase243 STUDENT",
                hashed_password="pbkdf2_sha256$unused", section_id=section.id,
            )
            db.add(student_no_role)
            await db.flush()
            fixture_user_ids.append(student_no_role.id)
            token_student = create_access_token(subject=str(student_no_role.id), roll_number=student_no_role.roll_number)

            # A holds a BCS-058 choice (in the ELECTIVE roster). B has no choice
            # and no section (out of every scope). C holds a BCS-055 choice
            # (different elective subject — cross-subject isolation).
            student_c = None
            if bcs58 is not None:
                choice_a = StudentElectiveChoice(
                    user_id=student_a.id, elective_slot=ElectiveSlot.ELECTIVE_II, subject_id=bcs58.id,
                )
                db.add(choice_a)
                await db.flush()
                fixture_choice_ids.append(choice_a.id)
                db.add(StudentEnrollment(
                    user_id=student_a.id, subject_id=bcs58.id,
                ))
                await db.flush()
            if bcs55 is not None:
                student_c = User(
                    roll_number=f"2401251{uuid.uuid4().hex[:6]}", name="Phase243 Student C",
                    hashed_password="pbkdf2_sha256$unused", section_id=section.id,
                )
                db.add(student_c)
                await db.flush()
                fixture_user_ids.append(student_c.id)
                choice_c = StudentElectiveChoice(
                    user_id=student_c.id, elective_slot=ElectiveSlot.ELECTIVE_II, subject_id=bcs55.id,
                )
                db.add(choice_c)
                await db.flush()
                fixture_choice_ids.append(choice_c.id)
            await db.commit()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # ---- A. Unauthenticated -> 401 ----
                r = await client.get("/api/v1/admin/students")
                check("A1. GET /admin/students without token -> 401", r.status_code == 401, f"got {r.status_code}")
                r = await client.get(f"/api/v1/admin/students/{student_a.id}")
                check("A2. GET /admin/students/{id} without token -> 401", r.status_code == 401, f"got {r.status_code}")

                # ---- B. STUDENT (no effective role) -> 403 ----
                r = await client.get("/api/v1/admin/students", headers={"Authorization": f"Bearer {token_student}"})
                check("B1. STUDENT list -> 403", r.status_code == 403, f"got {r.status_code}")
                r = await client.get(f"/api/v1/admin/students/{student_a.id}", headers={"Authorization": f"Bearer {token_student}"})
                check("B2. STUDENT detail -> 403", r.status_code == 403, f"got {r.status_code}")

                # ---- C. HEAD_ADMIN list = all STUDENT-role accounts ----
                r = await client.get("/api/v1/admin/students", headers={"Authorization": f"Bearer {token_admin}"})
                check("C1. HEAD list -> 200", r.status_code == 200, f"got {r.status_code}")
                body = r.json()
                ids = {item["id"] for item in body["items"]}
                check("C2. HEAD sees fixture student A", str(student_a.id) in ids)
                check("C3. HEAD sees fixture student B", str(student_b.id) in ids)
                check("C4. list exposes total/pages/page_size", body["total"] > 0 and body["pages"] >= 1 and body["page_size"] == 20)

                # ---- D. HEAD search + pagination ----
                r = await client.get("/api/v1/admin/students", params={"q": "Phase243"}, headers={"Authorization": f"Bearer {token_admin}"})
                body = r.json()
                check("D1. q filters by name (fixture matches only)", all("Phase243" in i["name"] for i in body["items"]) and body["total"] >= 1)
                r = await client.get("/api/v1/admin/students", params={"q": student_a.roll_number}, headers={"Authorization": f"Bearer {token_admin}"})
                body = r.json()
                check("D2. q filters by roll_number", body["total"] == 1 and body["items"][0]["id"] == str(student_a.id))
                r = await client.get("/api/v1/admin/students", params={"q": "no_such_roll_xyz"}, headers={"Authorization": f"Bearer {token_admin}"})
                body = r.json()
                check("D3. unmatched q -> empty items, total 0", body["total"] == 0 and body["items"] == [])
                r = await client.get("/api/v1/admin/students", params={"page_size": 1, "page": 1}, headers={"Authorization": f"Bearer {token_admin}"})
                body = r.json()
                check("D4. page_size=1 yields exactly 1 item and page metadata", len(body["items"]) == 1 and body["page"] == 1 and body["page_size"] == 1)

                # ---- E. HEAD detail ----
                r = await client.get(f"/api/v1/admin/students/{student_a.id}", headers={"Authorization": f"Bearer {token_admin}"})
                check("E1. HEAD detail -> 200", r.status_code == 200, f"got {r.status_code}")
                detail = r.json()
                check("E2. detail carries placement + enrollments + choices", detail["section_name"] is not None and detail["is_placed"] is True and detail["elective_choices"] != {})

                # ---- F. HEAD nonexistent -> 404 ----
                r = await client.get(f"/api/v1/admin/students/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token_admin}"})
                check("F1. HEAD nonexistent student -> 404", r.status_code == 404, f"got {r.status_code}")

                # ---- G/H. CLASS_ADMIN scoping ----
                r = await client.get("/api/v1/admin/students", headers={"Authorization": f"Bearer {token_class}"})
                body = r.json()
                ids = {item["id"] for item in body["items"]}
                check("G1. CLASS list -> 200", r.status_code == 200, f"got {r.status_code}")
                check("G2. CLASS sees only students of its section (A yes)", str(student_a.id) in ids)
                check("G3. CLASS does NOT see out-of-section student B", str(student_b.id) not in ids)
                r = await client.get(f"/api/v1/admin/students/{student_a.id}", headers={"Authorization": f"Bearer {token_class}"})
                check("G4. CLASS detail in-section -> 200", r.status_code == 200, f"got {r.status_code}")
                r = await client.get(f"/api/v1/admin/students/{student_b.id}", headers={"Authorization": f"Bearer {token_class}"})
                check("H1. CLASS detail out-of-section -> 404", r.status_code == 404, f"got {r.status_code}")

                # ---- I/J. ELECTIVE_ADMIN scoping ----
                r = await client.get("/api/v1/admin/students", headers={"Authorization": f"Bearer {token_elec}"})
                body = r.json()
                ids = {item["id"] for item in body["items"]}
                check("I1. ELECTIVE list -> 200", r.status_code == 200, f"got {r.status_code}")
                check("I2. ELECTIVE sees roster student A (BCS-058 choice)", str(student_a.id) in ids)
                check("I3. ELECTIVE does NOT see non-roster student B", str(student_b.id) not in ids)
                r = await client.get(f"/api/v1/admin/students/{student_a.id}", headers={"Authorization": f"Bearer {token_elec}"})
                check("I4. ELECTIVE detail roster -> 200", r.status_code == 200, f"got {r.status_code}")
                r = await client.get(f"/api/v1/admin/students/{student_b.id}", headers={"Authorization": f"Bearer {token_elec}"})
                check("J1. ELECTIVE detail non-roster -> 404", r.status_code == 404, f"got {r.status_code}")
                if bcs55 is not None and student_c is not None:
                    check("J2. ELECTIVE (BCS-058) does NOT see BCS-055 student C in the list",
                          str(student_c.id) not in ids)
                    r = await client.get(f"/api/v1/admin/students/{student_c.id}", headers={"Authorization": f"Bearer {token_elec}"})
                    check("J3. ELECTIVE (BCS-058) detail for BCS-055 student C -> 404 (cross-subject isolation)",
                          r.status_code == 404, f"got {r.status_code}")

                # ---- K. SUBSECTION_ADMIN inert / conservative ----
                # Structural limitation (mirrors Phase 23.11): the subsections
                # table is EMPTY, so no SUBSECTION_ADMIN scope can be created
                # (the admin_scopes FK rejects a nonexistent subsection_id). We
                # prove the limitation and the inert code path without fabricating
                # subsection rows.
                from app.repositories.admin_student_repo import AdminStudentRepository, StudentScopeFilter  # noqa: E402
                from app.services.admin_student_service import AdminStudentService  # noqa: E402
                inert_scope = StudentScopeFilter(is_global=False, section_ids=set(), subject_ids=set())
                inert_total = await AdminStudentRepository(db).count_students(inert_scope)
                inert_rows = await AdminStudentRepository(db).search_students(inert_scope, limit=20, offset=0)
                check("K2. restricted scope with no section/subject matches -> empty (inert code path)",
                      inert_total == 0 and inert_rows == [])
                # A non-HEAD admin resolving only SUBSECTION_ADMIN-role scopes
                # (if one existed) would resolve to exactly that empty filter.
                empty_filter = await AdminStudentService(db)._resolve_scope(sub_admin)
                check("K3. scope with no active scope rows resolves to empty (no fabrication)",
                      not empty_filter.is_global and not empty_filter.section_ids and not empty_filter.subject_ids)
                r = await client.get("/api/v1/admin/students", headers={"Authorization": f"Bearer {token_sub}"})
                check("K1. account with NO effective admin role -> 403 (require_any_admin)", r.status_code == 403, f"got {r.status_code}")

                # ---- L. No client-supplied scope parameter ----
                r = await client.get("/api/v1/admin/students", params={"section_id": str(section.id)}, headers={"Authorization": f"Bearer {token_class}"})
                check("L1. unknown query params are ignored (no client scope accepted)", r.status_code == 200, f"got {r.status_code}")

                # ---- N. Scope union: CLASS + ELECTIVE admin sees more than either alone ----
                r = await client.get("/api/v1/admin/students", headers={"Authorization": f"Bearer {token_union}"})
                body = r.json()
                ids = {item["id"] for item in body["items"]}
                check("N1. UNION list -> 200", r.status_code == 200, f"got {r.status_code}")
                check("N2. UNION sees student A (in section + roster)", str(student_a.id) in ids)
                check("N3. UNION sees student_no_role (in section, no choice -> via class scope)", str(student_no_role.id) in ids)
                check("N4. UNION does NOT see student B (unplaced, no choice)", str(student_b.id) not in ids)
                # The union sees strictly more than the pure ELECTIVE scope.
                pure_elec_ids = None
                r = await client.get("/api/v1/admin/students", headers={"Authorization": f"Bearer {token_elec}"})
                pure_elec_ids = {item["id"] for item in r.json()["items"]}
                check("N5. UNION sees at least everything the pure ELECTIVE scope sees",
                      pure_elec_ids.issubset(ids))
                check("N6. UNION sees MORE than the pure ELECTIVE scope (student_no_role via class scope)",
                      str(student_no_role.id) in ids and str(student_no_role.id) not in pure_elec_ids)

                # ---- M. Data unchanged (verified AFTER the finally cleanup) ----

    finally:
        async with AsyncSessionLocal() as db:
            for cid in fixture_choice_ids:
                await db.execute(delete(StudentElectiveChoice).where(StudentElectiveChoice.id == cid))
            for sid in fixture_scope_ids:
                await db.execute(delete(AdminScope).where(AdminScope.id == sid))
            for uid in fixture_user_ids:
                await db.execute(delete(StudentElectiveChoice).where(StudentElectiveChoice.user_id == uid))
                await db.execute(delete(StudentEnrollment).where(StudentEnrollment.user_id == uid))
                await db.execute(delete(User).where(User.id == uid))
            await db.commit()
        print("\nCleanup: fixture users, scopes, choices and enrollments removed.")

    # ---- M. Data unchanged (checked AFTER cleanup so fixture rows are gone) ----
    async with AsyncSessionLocal() as db:
        users_after = (await db.execute(
            select(func.count()).select_from(User)
        )).scalar()
        choices_after = (await db.execute(
            select(func.count()).select_from(StudentElectiveChoice)
        )).scalar()
        check("M1. user count unchanged after verification",
              users_after == users_before, f"{users_before} -> {users_after}")
        check("M2. elective-choice count unchanged after verification",
              choices_after == choices_before, f"{choices_before} -> {choices_after}")

    failed = [name for name, ok in results if not ok]
    print("=" * 60)
    print(f"Phase 24.3 verifier: {len(results) - len(failed)}/{len(results)} PASS")
    if failed:
        print("FAILED:", failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
