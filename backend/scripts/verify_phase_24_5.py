"""
Phase 24.5 — Academic Structure Management verifier.

Proves the Phase 24.5 contract end-to-end against the LOCAL development DB:

  A. unauthenticated access -> 401
  B. STUDENT (no effective admin role) -> 403
  C. CLASS_ADMIN -> 403 (no accidental HEAD_ADMIN elevation)
  D. ELECTIVE_ADMIN -> 403 (no accidental HEAD_ADMIN elevation)
  E. SUBSECTION_ADMIN remains conservative/inert (no scope row can even be
     created while the subsections table is empty; no elevation otherwise)
  F. HEAD_ADMIN -> allowed on every structure surface
  G. Session list/create/duplicate-409/invalid-date-400/PATCH/activate-409/
     deactivate/activate-cycle with restoration of the original active session
  H. Semester list/create/PATCH/invalid-parent-404/warning surfacing
  I. Section list/create/duplicate-409/PATCH/invalid-parent-404
  J. Subsection list/create/duplicate-409/validation-422/PATCH/
     invalid-parent-404 + truthful empty where baseline has none
  K. PATCH schemas do not permit unauthorized fields (is_active extra ignored;
     activation stays server-gated through the dedicated endpoints)
  L. no client-supplied role/scope controls authorization (query params ignored)
  M. arbitrary IDs cannot bypass HEAD_ADMIN (non-HEAD -> 403; HEAD + random
     UUID -> 404)
  N. data integrity: baseline counts captured before and verified equal after
     fixture cleanup (14 tables)

LOCALITY GUARD (hard): this script FORCES DATABASE_URI to the local dev DB
before importing the app, then asserts the effective engine URL is the local
host. It refuses to run against any other target (notably the Supabase
production pooler).

Usage (local only):
    python scripts/verify_phase_24_5.py
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
from httpx import ASGITransport, AsyncClient  # noqa: E402
from app.main import app  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.user import User, Section, Subsection  # noqa: E402
from app.models.academic import (  # noqa: E402
    AcademicSession, Semester, Subject, StudentEnrollment, StudentElectiveChoice,
)
from app.models.admin_scope import AdminScope  # noqa: E402
from app.models.enums import AdminRole, UserRole  # noqa: E402
from app.core.security import create_access_token  # noqa: E402

results = []
_BASELINE: dict = {}
_ACTIVE_SESSION_ID = None


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if not ok else ""))


BASELINE_TABLES = [
    "users", "student_enrollments", "student_elective_choices",
    "academic_sessions", "semesters", "sections", "subsections",
    "timetable_entries", "class_sessions", "attendance_records",
    "academic_events", "quiz_schedules", "admin_scopes", "occurrence_outcomes",
]


async def table_counts(db) -> dict:
    """Row counts for every baseline table (COUNT(*) — bounded, no materialization)."""
    out = {}
    for table in BASELINE_TABLES:
        out[table] = (await db.execute(
            select(func.count()).select_from(text(f'"{table}"'))
        )).scalar_one()
    return out


async def main() -> int:
    print("=" * 64)
    print("Phase 24.5 — Admin Portal: Academic Structure Management")
    print(f"Locality guard: using local dev DB {settings.DATABASE_URI}")
    print("=" * 64)

    # Fixture tracking (hard-cleaned in finally)
    fixture_user_ids: list = []
    fixture_scope_ids: list = []
    fixture_session_id: str | None = None
    fixture_semester_id: str | None = None
    fixture_section_id: str | None = None
    fixture_subsection_id: str | None = None
    warning_semester_id: str | None = None
    original_active_session_id: uuid.UUID | None = None

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
            if not sections:
                check("0. at least one section exists", False)
                return 1
            real_section = sections[0]
            real_section_id = real_section.id  # plain UUID — survives rollbacks

            subjects = (await db.execute(select(Subject))).scalars().all()
            bcs58 = next((s for s in subjects if s.code == "BCS-058"), None)
            bcs58_id = bcs58.id if bcs58 else None

            active_session = (await db.execute(
                select(AcademicSession).where(AcademicSession.is_active.is_(True))
            )).scalars().first()
            if active_session is None:
                check("0. exactly one active session exists", False)
                return 1
            original_active_session_id = active_session.id

            baseline = await table_counts(db)
            print(f"baseline counts: {baseline}")
            global _BASELINE, _ACTIVE_SESSION_ID
            _BASELINE = baseline
            _ACTIVE_SESSION_ID = original_active_session_id

            # ---- Fixture users + scopes (isolated; cleaned in finally) ----
            class_admin_user = User(
                roll_number=f"2401250{uuid.uuid4().hex[:6]}", name="Phase245 CLASS_ADMIN",
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
                roll_number=f"2401271{uuid.uuid4().hex[:6]}", name="Phase245 ELECTIVE_ADMIN",
                hashed_password="pbkdf2_sha256$unused", section_id=real_section_id,
            )
            db.add(elec_admin_user)
            await db.flush()
            fixture_user_ids.append(elec_admin_user.id)
            db.add(AdminScope(
                user_id=elec_admin_user.id, role=AdminRole.ELECTIVE_ADMIN,
                section_id=None, subsection_id=None,
                subject_id=bcs58_id,
            ))
            await db.flush()
            fixture_scope_ids.append((await db.execute(
                select(AdminScope.id).where(AdminScope.user_id == elec_admin_user.id)
            )).scalars().first())
            token_elec = create_access_token(subject=str(elec_admin_user.id), roll_number=elec_admin_user.roll_number)

            sub_admin_user = User(
                roll_number=f"2401272{uuid.uuid4().hex[:6]}", name="Phase245 SUBSECTION_ADMIN",
                hashed_password="pbkdf2_sha256$unused", section_id=None,
            )
            db.add(sub_admin_user)
            await db.flush()
            fixture_user_ids.append(sub_admin_user.id)
            token_sub = create_access_token(subject=str(sub_admin_user.id), roll_number=sub_admin_user.roll_number)

            student_user = User(
                roll_number=f"2401273{uuid.uuid4().hex[:6]}", name="Phase245 STUDENT",
                hashed_password="pbkdf2_sha256$unused", section_id=real_section_id,
            )
            db.add(student_user)
            await db.flush()
            fixture_user_ids.append(student_user.id)
            token_student = create_access_token(subject=str(student_user.id), roll_number=student_user.roll_number)
            token_admin = create_access_token(subject=str(admin_user.id), roll_number=admin_user.roll_number)
            await db.commit()

            # SUBSECTION_ADMIN: the scope row cannot even be created while the
            # subsections table is empty (FK constraint) — structural inertness.
            # Isolated in its own transaction so the expected failure cannot
            # discard the committed fixtures above.
            sub_scope = AdminScope(
                user_id=sub_admin_user.id, role=AdminRole.SUBSECTION_ADMIN,
                section_id=None, subsection_id=uuid.uuid4(), subject_id=None,
            )
            db.add(sub_scope)
            try:
                await db.flush()
                check("E0. SUBSECTION_ADMIN scope creation rejected by FK (inert)", False,
                      "scope row was persisted despite empty subsections")
                fixture_scope_ids.append(sub_scope.id)
                await db.commit()
            except IntegrityError:
                await db.rollback()
                check("E0. SUBSECTION_ADMIN scope creation rejected by FK (inert)", True)

        transport = ASGITransport(app=app)
        S = "/api/v1/admin/structure"
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # ---- A. Authentication ----
            r = await client.get(f"{S}/sessions")
            check("A1. GET sessions without token -> 401", r.status_code == 401, str(r.status_code))
            r = await client.post(f"{S}/sessions", json={"name": "x", "start_date": "2026-01-01", "end_date": "2026-12-31"})
            check("A2. POST sessions without token -> 401", r.status_code == 401, str(r.status_code))

            # ---- B/C/D. Authorization matrix (all structure endpoints HEAD-only) ----
            for label, token in [("STUDENT", token_student), ("CLASS_ADMIN", token_class), ("ELECTIVE_ADMIN", token_elec), ("SUBSECTION_ADMIN", token_sub)]:
                r = await client.get(f"{S}/sessions", headers={"Authorization": f"Bearer {token}"})
                check(f"B/C/D/E. {label} GET sessions -> 403", r.status_code == 403, str(r.status_code))
                r = await client.post(f"{S}/sessions", json={"name": "x", "start_date": "2026-01-01", "end_date": "2026-12-31"},
                                      headers={"Authorization": f"Bearer {token}"})
                check(f"B/C/D/E. {label} POST sessions -> 403", r.status_code == 403, str(r.status_code))

            # ---- F. HEAD allowed ----
            r = await client.get(f"{S}/sessions", headers={"Authorization": f"Bearer {token_admin}"})
            check("F1. HEAD GET sessions -> 200", r.status_code == 200, str(r.status_code))
            sessions_body = r.json()
            check("F2. real active session present in list",
                  any(s["is_active"] for s in sessions_body), str(sessions_body))

            # ---- G. Session operations ----
            r = await client.post(f"{S}/sessions", json={"name": "REVIEW 24.5 SESSION", "start_date": "2026-01-01", "end_date": "2025-12-31"},
                                  headers={"Authorization": f"Bearer {token_admin}"})
            check("G1. end<=start -> 400", r.status_code == 400, str(r.status_code))
            r = await client.post(f"{S}/sessions", json={"name": "REVIEW 24.5 SESSION", "start_date": "2026-01-01", "end_date": "2026-12-31"},
                                  headers={"Authorization": f"Bearer {token_admin}"})
            check("G2. create session -> 201, starts inactive",
                  r.status_code == 201 and r.json()["is_active"] is False, str(r.status_code))
            fixture_session_id = r.json()["id"]
            r = await client.post(f"{S}/sessions", json={"name": "REVIEW 24.5 SESSION", "start_date": "2026-01-01", "end_date": "2026-12-31"},
                                  headers={"Authorization": f"Bearer {token_admin}"})
            check("G3. duplicate session name -> 409", r.status_code == 409, str(r.status_code))
            r = await client.patch(f"{S}/sessions/{fixture_session_id}", json={"name": "REVIEW 24.5 SESSION (edited)"},
                                   headers={"Authorization": f"Bearer {token_admin}"})
            check("G4. PATCH session name -> 200", r.status_code == 200 and r.json()["name"].endswith("(edited)"), str(r.status_code))
            r = await client.patch(f"{S}/sessions/{fixture_session_id}", json={"is_active": True},
                                   headers={"Authorization": f"Bearer {token_admin}"})
            check("K1. PATCH session is_active extra field ignored (activation server-gated)",
                  r.status_code == 200 and r.json()["is_active"] is False, str(r.status_code))
            r = await client.post(f"{S}/sessions/{fixture_session_id}/activate",
                                  headers={"Authorization": f"Bearer {token_admin}"})
            check("G5. activate while another session is active -> 409 (single-active invariant)",
                  r.status_code == 409, str(r.status_code))

            # ---- H. Semesters ----
            r = await client.get(f"{S}/sessions/{fixture_session_id}/semesters", headers={"Authorization": f"Bearer {token_admin}"})
            check("H1. list semesters for new session -> 200 empty", r.status_code == 200 and r.json() == [], str(r.status_code))
            r = await client.post(f"{S}/sessions/{fixture_session_id}/semesters",
                                  json={"name": "REVIEW SEM", "start_date": "2026-01-15", "end_date": "2026-06-30"},
                                  headers={"Authorization": f"Bearer {token_admin}"})
            check("H2. create semester -> 201", r.status_code == 201 and r.json()["semester"]["name"] == "REVIEW SEM", str(r.status_code))
            fixture_semester_id = r.json()["semester"]["id"]
            r = await client.patch(f"/api/v1/admin/structure/semesters/{fixture_semester_id}",
                                   json={"name": "REVIEW SEM 2"}, headers={"Authorization": f"Bearer {token_admin}"})
            check("H3. PATCH semester -> 200", r.status_code == 200 and r.json()["semester"]["name"] == "REVIEW SEM 2", str(r.status_code))
            r = await client.post(f"{S}/sessions/{uuid.uuid4()}/semesters",
                                  json={"name": "X", "start_date": "2026-01-01", "end_date": "2026-06-30"},
                                  headers={"Authorization": f"Bearer {token_admin}"})
            check("H4. create semester under nonexistent session -> 404", r.status_code == 404, str(r.status_code))

            # ---- I. Sections ----
            r = await client.get(f"{S}/semesters/{fixture_semester_id}/sections", headers={"Authorization": f"Bearer {token_admin}"})
            check("I1. list sections for new semester -> 200 empty", r.status_code == 200 and r.json() == [], str(r.status_code))
            r = await client.post(f"{S}/semesters/{fixture_semester_id}/sections",
                                  json={"name": "REV-51", "program": "BTech CSE"},
                                  headers={"Authorization": f"Bearer {token_admin}"})
            check("I2. create section -> 201 with program", r.status_code == 201 and r.json()["section"]["program"] == "BTech CSE", str(r.status_code))
            fixture_section_id = r.json()["section"]["id"]
            r = await client.post(f"{S}/semesters/{fixture_semester_id}/sections",
                                  json={"name": "REV-51"}, headers={"Authorization": f"Bearer {token_admin}"})
            check("I3. duplicate section name -> 409", r.status_code == 409, str(r.status_code))
            r = await client.patch(f"{S}/sections/{fixture_section_id}", json={"name": "REV-52"},
                                   headers={"Authorization": f"Bearer {token_admin}"})
            check("I4. PATCH section -> 200", r.status_code == 200 and r.json()["section"]["name"] == "REV-52", str(r.status_code))
            r = await client.post(f"{S}/semesters/{uuid.uuid4()}/sections",
                                  json={"name": "REV-53"}, headers={"Authorization": f"Bearer {token_admin}"})
            check("I5. create section under nonexistent semester -> 404", r.status_code == 404, str(r.status_code))

            # ---- J. Subsections ----
            r = await client.get(f"{S}/sections/{fixture_section_id}/subsections", headers={"Authorization": f"Bearer {token_admin}"})
            check("J1. list subsections for new section -> 200 empty", r.status_code == 200 and r.json() == [], str(r.status_code))
            r = await client.post(f"{S}/sections/{fixture_section_id}/subsections",
                                  json={"name": "REV-52-A", "max_strength": 30},
                                  headers={"Authorization": f"Bearer {token_admin}"})
            check("J2. create subsection -> 201 with max_strength",
                  r.status_code == 201 and r.json()["max_strength"] == 30, str(r.status_code))
            fixture_subsection_id = r.json()["id"]
            r = await client.post(f"{S}/sections/{fixture_section_id}/subsections",
                                  json={"name": "REV-52-A"}, headers={"Authorization": f"Bearer {token_admin}"})
            check("J3. duplicate subsection name -> 409", r.status_code == 409, str(r.status_code))
            r = await client.post(f"{S}/sections/{fixture_section_id}/subsections",
                                  json={"name": "REV-52-B", "max_strength": 0},
                                  headers={"Authorization": f"Bearer {token_admin}"})
            check("J4. max_strength 0 -> 422", r.status_code == 422, str(r.status_code))
            r = await client.patch(f"{S}/subsections/{fixture_subsection_id}",
                                   json={"name": "REV-52-A1", "max_strength": 25},
                                   headers={"Authorization": f"Bearer {token_admin}"})
            check("J5. PATCH subsection -> 200", r.status_code == 200 and r.json()["name"] == "REV-52-A1", str(r.status_code))
            r = await client.post(f"{S}/sections/{uuid.uuid4()}/subsections",
                                  json={"name": "REV-52-C"}, headers={"Authorization": f"Bearer {token_admin}"})
            check("J6. create subsection under nonexistent section -> 404", r.status_code == 404, str(r.status_code))

            # ---- L. No client-supplied scope / role params ----
            r = await client.get(f"{S}/sessions", params={"role": "HEAD_ADMIN", "scope": "global"},
                                 headers={"Authorization": f"Bearer {token_student}"})
            check("L1. query role/scope params do not elevate STUDENT -> 403", r.status_code == 403, str(r.status_code))
            r = await client.post(f"{S}/sessions/{original_active_session_id}/activate", params={"role": "HEAD_ADMIN"},
                                  headers={"Authorization": f"Bearer {token_class}"})
            check("L2. query role param does not elevate CLASS_ADMIN -> 403", r.status_code == 403, str(r.status_code))

            # ---- M. Arbitrary IDs cannot bypass ----
            r = await client.get(f"{S}/sessions/{uuid.uuid4()}/semesters", headers={"Authorization": f"Bearer {token_admin}"})
            check("M1. HEAD + random session UUID -> 404", r.status_code == 404, str(r.status_code))
            r = await client.post(f"{S}/sessions/{uuid.uuid4()}/activate", headers={"Authorization": f"Bearer {token_class}"})
            check("M2. CLASS_ADMIN + arbitrary session UUID -> 403 (gate first)", r.status_code == 403, str(r.status_code))

            # ---- G-cont. Activation cycle (restores original active session) ----
            r = await client.post(f"{S}/sessions/{original_active_session_id}/deactivate", headers={"Authorization": f"Bearer {token_admin}"})
            check("G6. deactivate current active session -> 200", r.status_code == 200 and r.json()["is_active"] is False, str(r.status_code))
            r = await client.post(f"{S}/sessions/{fixture_session_id}/activate", headers={"Authorization": f"Bearer {token_admin}"})
            check("G7. activate fixture session -> 200 active", r.status_code == 200 and r.json()["is_active"] is True, str(r.status_code))
            # while the fixture session is active, a second semester must surface a registration warning
            r = await client.post(f"{S}/sessions/{fixture_session_id}/semesters",
                                  json={"name": "REVIEW WARN SEM", "start_date": "2026-02-01", "end_date": "2026-07-31"},
                                  headers={"Authorization": f"Bearer {token_admin}"})
            warning_semester_id = r.json()["semester"]["id"] if r.status_code == 201 else None
            check("H5. MULTI_SEMESTER registration warning surfaced",
                  r.status_code == 201 and any(w["code"] == "MULTI_SEMESTER" for w in r.json()["warnings"]),
                  str(r.json() if r.status_code == 201 else r.status_code))
            r = await client.post(f"{S}/sessions/{fixture_session_id}/deactivate", headers={"Authorization": f"Bearer {token_admin}"})
            check("G8. deactivate fixture session -> 200", r.status_code == 200 and r.json()["is_active"] is False, str(r.status_code))
            r = await client.post(f"{S}/sessions/{original_active_session_id}/activate", headers={"Authorization": f"Bearer {token_admin}"})
            check("G9. reactivate original session -> 200", r.status_code == 200 and r.json()["is_active"] is True, str(r.status_code))

        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.5 verifier (core): {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1

    finally:
        # ---- Hard cleanup (defensive; runs on success AND failure) ----
        async with AsyncSessionLocal() as db:
            try:
                if warning_semester_id:
                    await db.execute(delete(Semester).where(Semester.id == warning_semester_id))
                if fixture_subsection_id:
                    await db.execute(delete(Subsection).where(Subsection.id == fixture_subsection_id))
                if fixture_section_id:
                    await db.execute(delete(Section).where(Section.id == fixture_section_id))
                if fixture_semester_id:
                    await db.execute(delete(Semester).where(Semester.id == fixture_semester_id))
                if fixture_session_id:
                    await db.execute(delete(AcademicSession).where(AcademicSession.id == fixture_session_id))
                if fixture_scope_ids:
                    await db.execute(delete(AdminScope).where(AdminScope.id.in_(fixture_scope_ids)))
                if fixture_user_ids:
                    await db.execute(delete(User).where(User.id.in_(fixture_user_ids)))
                # Restore the original active session regardless of where the
                # activation cycle ended.
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
        check("N1. all baseline table counts restored after fixture cleanup",
              after == _BASELINE, f"before={_BASELINE} after={after}")
        active_now = (await db.execute(
            select(AcademicSession).where(AcademicSession.is_active.is_(True))
        )).scalars().first()
        check("N2. original active session restored",
              active_now is not None and active_now.id == _ACTIVE_SESSION_ID)


if __name__ == "__main__":
    async def _run() -> int:
        code = await main()
        await post_cleanup_checks()
        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.5 verifier: {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1

    sys.exit(asyncio.run(_run()))
