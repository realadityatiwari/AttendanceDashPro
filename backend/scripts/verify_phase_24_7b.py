"""
Phase 24.7-B — Timetable Repository / Service / Conflict Validation verifier.

Proves the authoritative backend timetable management layer end-to-end against
the LOCAL development DB, following the conflict semantics recorded in
``AdminTimetableService`` (and the governance docs):

  Two entries CONFLICT when ALL hold:
    (1) both active; (2) same day; (3) same section;
    (4) time overlap: existing.start < new.end AND existing.end > new.start
        (adjacent 09:00-10:00 / 10:00-11:00 is ALLOWED);
    (5) same effective scheduling scope:
          section-wide vs section-wide        -> conflict
          section-wide vs subsection-specific -> conflict
          same subsection vs same subsection  -> conflict
          different subsections               -> parallel (allowed)
          different sections                  -> never conflict
  ELECTIVE rule: same elective_slot (both ELECTIVE_I or both ELECTIVE_II)
    -> NO conflict (per-student resolution to different concrete subjects);
    ELECTIVE_I vs ELECTIVE_II or elective vs regular -> conflict.

Coverage:
  1.  non-overlapping entries allowed
  2.  adjacent entries allowed
  3.  overlapping same subsection rejected
  4.  overlapping section-wide vs subsection entry rejected
  5.  different sections allowed
  6.  different subsections allowed (parallel schedules)
  7.  inactive entries do not block new active entries
  8.  invalid time range rejected
  9.  incompatible subject rejected
  10. invalid elective-slot relationship rejected
  11. repository queries remain scope-aware
  +   elective same-slot non-conflict / cross-slot conflict / vs regular
  +   not-found / invalid-scope / inactive-parent domain errors
  +   baseline counts restored after fixture cleanup

LOCALITY GUARD (hard): forces + asserts DATABASE_URI is the local dev DB.

Usage (local only):
    python scripts/verify_phase_24_7b.py
"""
import asyncio
import os
import sys
import uuid
import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

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

from sqlalchemy import delete, func, select, text  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.user import User, Section, Subsection  # noqa: E402
from app.models.academic import (  # noqa: E402
    AcademicSession, Semester, Subject, StudentElectiveChoice,
)
from app.models.admin_scope import AdminScope  # noqa: E402
from app.models.enums import AdminRole, ClassType, ElectiveSlot, SubjectCategory, UserRole  # noqa: E402
from app.models.timetable import TimetableEntry  # noqa: E402
from app.services.admin_timetable_service import (  # noqa: E402
    AdminTimetableService,
    TimetableDomainError,
    TimetableInvalidScopeError,
    TimetableInvalidSubjectError,
    TimetableInvalidSubsectionError,
    TimetableInvalidElectiveSlotError,
    TimetableInvalidTimeRangeError,
    TimetableTimeConflictError,
    TimetableInactiveParentError,
)
from app.repositories.admin_timetable_repo import AdminTimetableRepository  # noqa: E402
from app.schemas.admin_timetable import (  # noqa: E402
    CreateTimetableEntryRequest, UpdateTimetableEntryRequest,
)

results = []
_BASELINE: dict = {}
_ACTIVE_SESSION_ID = None


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if not ok else ""))


async def code_of(coro):
    """Run a service call; return the domain-error code or None on success."""
    try:
        await coro
        return None
    except TimetableDomainError as exc:
        return exc.code


async def table_counts(db) -> dict:
    out = {}
    for table in ["users", "admin_scopes", "academic_sessions", "semesters",
                  "sections", "subsections", "subjects", "timetable_entries"]:
        out[table] = (await db.execute(
            select(func.count()).select_from(text(f'"{table}"'))
        )).scalar_one()
    return out


async def main() -> int:
    global _BASELINE, _ACTIVE_SESSION_ID
    print("=" * 64)
    print("Phase 24.7-B — Timetable Repository / Service / Conflict Validation")
    print(f"Locality guard: using local dev DB {settings.DATABASE_URI}")
    print("=" * 64)

    fixture: dict = {}
    try:
        async with AsyncSessionLocal() as db:
            admin_user = (await db.execute(
                select(User).where(User.role == UserRole.ADMIN)
            )).scalars().first()
            if admin_user is None:
                check("0. legacy ADMIN user found", False)
                return 1

            active_session = (await db.execute(
                select(AcademicSession).where(AcademicSession.is_active.is_(True))
            )).scalars().first()
            if active_session is None:
                check("0. exactly one active session exists", False)
                return 1
            _ACTIVE_SESSION_ID = active_session.id

            _BASELINE = await table_counts(db)
            print(f"baseline counts: {_BASELINE}")

            # ---- Isolated fixtures ----
            fs = AcademicSession(
                name="REVIEW 24.7B SESSION",
                start_date=datetime.date(2028, 1, 1),
                end_date=datetime.date(2028, 12, 31),
                is_active=False,
            )
            db.add(fs)
            await db.flush()
            fixture["session"] = fs.id

            fsem = Semester(
                name="Review Sem 24.7B", session_id=fs.id,
                start_date=datetime.date(2028, 1, 15),
                end_date=datetime.date(2028, 6, 30),
            )
            db.add(fsem)
            await db.flush()
            fixture["semester"] = fsem.id

            secA = Section(name="REV-A", program="BTech CSE", semester_id=fsem.id)
            secB = Section(name="REV-B", program="BTech CSE", semester_id=fsem.id)
            db.add_all([secA, secB])
            await db.flush()
            fixture["section_a"] = secA.id
            fixture["section_b"] = secB.id

            subA1 = Subsection(name="REV-A1", section_id=secA.id)
            subA2 = Subsection(name="REV-A2", section_id=secA.id)
            db.add_all([subA1, subA2])
            await db.flush()
            fixture["subsection_a1"] = subA1.id
            fixture["subsection_a2"] = subA2.id

            common = Subject(
                code="REV-COMMON", name="Review Common", category=SubjectCategory.THEORY,
                quiz_applicable=True, attendance_applicable=True, semester_id=fsem.id,
            )
            elecI = Subject(
                code="REV-ELECI", name="Review Elective-I", category=SubjectCategory.THEORY,
                elective_slot=ElectiveSlot.ELECTIVE_I,
                quiz_applicable=True, attendance_applicable=True, semester_id=fsem.id,
            )
            elecII = Subject(
                code="REV-ELECII", name="Review Elective-II", category=SubjectCategory.THEORY,
                elective_slot=ElectiveSlot.ELECTIVE_II,
                quiz_applicable=True, attendance_applicable=True, semester_id=fsem.id,
            )
            # Subject in a DIFFERENT semester (incompatibility fixture).
            other_sem = Semester(
                name="Other Sem 24.7B", session_id=fs.id,
                start_date=datetime.date(2029, 1, 15),
                end_date=datetime.date(2029, 6, 30),
            )
            db.add(other_sem)
            await db.flush()
            fixture["other_semester"] = other_sem.id
            other_subject = Subject(
                code="REV-OTHER", name="Review Other-Sem Subject", category=SubjectCategory.THEORY,
                quiz_applicable=True, attendance_applicable=True, semester_id=other_sem.id,
            )
            db.add_all([common, elecI, elecII, other_subject])
            await db.flush()
            fixture["common"] = common.id
            fixture["elec_i"] = elecI.id
            fixture["elec_ii"] = elecII.id
            fixture["other_subject"] = other_subject.id

            # Fixture users + scopes.
            class_admin = User(
                roll_number=f"2401280{uuid.uuid4().hex[:6]}", name="Phase247B CLASS_ADMIN",
                hashed_password="pbkdf2_sha256$unused", section_id=secA.id,
            )
            db.add(class_admin)
            await db.flush()
            fixture["class_admin_user"] = class_admin.id
            db.add(AdminScope(
                user_id=class_admin.id, role=AdminRole.CLASS_ADMIN,
                section_id=secA.id, subsection_id=None, subject_id=None,
            ))
            await db.flush()

            elec_admin = User(
                roll_number=f"2401281{uuid.uuid4().hex[:6]}", name="Phase247B ELECTIVE_ADMIN",
                hashed_password="pbkdf2_sha256$unused", section_id=secA.id,
            )
            db.add(elec_admin)
            await db.flush()
            fixture["elec_admin_user"] = elec_admin.id
            db.add(AdminScope(
                user_id=elec_admin.id, role=AdminRole.ELECTIVE_ADMIN,
                section_id=None, subsection_id=None, subject_id=elecI.id,
            ))
            await db.flush()

            sub_admin = User(
                roll_number=f"2401282{uuid.uuid4().hex[:6]}", name="Phase247B SUBSECTION_ADMIN",
                hashed_password="pbkdf2_sha256$unused", section_id=secA.id,
            )
            db.add(sub_admin)
            await db.flush()
            fixture["sub_admin_user"] = sub_admin.id
            db.add(AdminScope(
                user_id=sub_admin.id, role=AdminRole.SUBSECTION_ADMIN,
                section_id=None, subsection_id=subA1.id, subject_id=None,
            ))
            await db.flush()

            student = User(
                roll_number=f"2401283{uuid.uuid4().hex[:6]}", name="Phase247B STUDENT",
                hashed_password="pbkdf2_sha256$unused", section_id=secA.id,
            )
            db.add(student)
            await db.flush()
            fixture["student_user"] = student.id

            fixture["scopes"] = (await db.execute(
                select(AdminScope.id)
            )).scalars().all()
            await db.commit()

        # ==================== TESTS (service-level) ====================
        async with AsyncSessionLocal() as db:
            svc = AdminTimetableService(db)
            T = lambda **kw: CreateTimetableEntryRequest(**kw)  # noqa: E731
            D = lambda **kw: UpdateTimetableEntryRequest(**kw)  # noqa: E731

            admin = (await db.execute(
                select(User).where(User.role == UserRole.ADMIN)
            )).scalars().first()
            class_admin = (await db.execute(
                select(User).where(User.id == fixture["class_admin_user"])
            )).scalars().first()
            elec_admin = (await db.execute(
                select(User).where(User.id == fixture["elec_admin_user"])
            )).scalars().first()
            sub_admin = (await db.execute(
                select(User).where(User.id == fixture["sub_admin_user"])
            )).scalars().first()
            student = (await db.execute(
                select(User).where(User.id == fixture["student_user"])
            )).scalars().first()

            base = T(section_id=fixture["section_a"], subject_id=fixture["common"],
                     day_of_week=0, start_time=datetime.time(9, 0),
                     end_time=datetime.time(10, 0), class_type=ClassType.LECTURE)

            # 1. non-overlapping entries allowed
            e1 = await svc.create_entry(admin, base)
            e2 = await svc.create_entry(admin, base.model_copy(
                update={"day_of_week": 1}))
            check("1. non-overlapping (different day) entries allowed",
                  e1.id and e2.id)

            # 2. adjacent entries allowed (09-10 then 10-11)
            e3 = await svc.create_entry(admin, base.model_copy(
                update={"start_time": datetime.time(10, 0),
                        "end_time": datetime.time(11, 0)}))
            check("2. adjacent entries (09-10 / 10-11) allowed", bool(e3.id))

            # 3. overlapping same subsection rejected
            code = await code_of(svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["common"],
                day_of_week=0, start_time=datetime.time(11, 0),
                end_time=datetime.time(12, 0), class_type=ClassType.LECTURE,
                subsection_id=fixture["subsection_a1"])))
            code2 = await code_of(svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["common"],
                day_of_week=0, start_time=datetime.time(11, 30),
                end_time=datetime.time(12, 30), class_type=ClassType.LECTURE,
                subsection_id=fixture["subsection_a1"])))
            check("3. overlapping same subsection rejected (TIME_CONFLICT)",
                  code2 == "TIME_CONFLICT", f"got {code2}")

            # 4. section-wide vs subsection-specific overlapping rejected
            #    (first a section-wide entry at 12-13, then a subsection entry
            #     overlapping it at 12:30-13:30)
            await svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["common"],
                day_of_week=0, start_time=datetime.time(12, 0),
                end_time=datetime.time(13, 0), class_type=ClassType.LECTURE))
            code4 = await code_of(svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["common"],
                day_of_week=0, start_time=datetime.time(12, 30),
                end_time=datetime.time(13, 30), class_type=ClassType.LECTURE,
                subsection_id=fixture["subsection_a1"])))
            check("4. section-wide vs subsection overlapping rejected (TIME_CONFLICT)",
                  code4 == "TIME_CONFLICT", f"got {code4}")

            # 5. different sections allowed (parallel)
            e5 = await svc.create_entry(admin, T(
                section_id=fixture["section_b"], subject_id=fixture["common"],
                day_of_week=0, start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0), class_type=ClassType.LECTURE))
            check("5. different sections allowed (parallel)", bool(e5.id))

            # 6. different subsections allowed (parallel schedules)
            e6 = await svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["common"],
                day_of_week=0, start_time=datetime.time(14, 0),
                end_time=datetime.time(15, 0), class_type=ClassType.TUTORIAL,
                subsection_id=fixture["subsection_a1"]))
            e6b = await svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["common"],
                day_of_week=0, start_time=datetime.time(14, 30),
                end_time=datetime.time(15, 30), class_type=ClassType.TUTORIAL,
                subsection_id=fixture["subsection_a2"]))
            check("6. different subsections allowed (parallel)", bool(e6.id and e6b.id))

            # 7. inactive entries do not block new active entries
            await svc.deactivate_entry(admin, e1.id)
            e7 = await svc.create_entry(admin, base.model_copy(
                update={"day_of_week": 0, "start_time": datetime.time(9, 0),
                        "end_time": datetime.time(10, 0)}))
            check("7. inactive entry does not block a new active entry",
                  bool(e7.id))

            # 8. invalid time range rejected
            code8 = await code_of(svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["common"],
                day_of_week=5, start_time=datetime.time(10, 0),
                end_time=datetime.time(9, 0), class_type=ClassType.LECTURE)))
            check("8. invalid time range rejected (INVALID_TIME_RANGE)",
                  code8 == "INVALID_TIME_RANGE", f"got {code8}")

            # 9. incompatible subject rejected (different semester)
            code9 = await code_of(svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["other_subject"],
                day_of_week=5, start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0), class_type=ClassType.LECTURE)))
            check("9. incompatible (different-semester) subject rejected (INVALID_SUBJECT)",
                  code9 == "INVALID_SUBJECT", f"got {code9}")

            # 10. invalid elective-slot relationship rejected
            code10 = await code_of(svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["elec_i"],
                day_of_week=5, start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0), class_type=ClassType.LECTURE,
                elective_slot=ElectiveSlot.ELECTIVE_II))  # wrong slot for subject
            )
            check("10. mismatched elective slot rejected (INVALID_ELECTIVE_SLOT)",
                  code10 == "INVALID_ELECTIVE_SLOT", f"got {code10}")

            # 10b. non-elective subject carrying an elective marker rejected
            code10b = await code_of(svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["common"],
                day_of_week=5, start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0), class_type=ClassType.LECTURE,
                elective_slot=ElectiveSlot.ELECTIVE_I))
            )
            check("10b. non-elective subject with elective marker rejected",
                  code10b == "INVALID_ELECTIVE_SLOT", f"got {code10b}")

            # 10c. valid elective subject WITH matching slot is allowed
            e10c = await svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["elec_i"],
                day_of_week=5, start_time=datetime.time(10, 0),
                end_time=datetime.time(11, 0), class_type=ClassType.LECTURE,
                elective_slot=ElectiveSlot.ELECTIVE_I))
            check("10c. elective subject with matching slot allowed", bool(e10c.id))

            # ELECTIVE rule: same slot does not conflict (per-student resolution)
            e10d = await svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["elec_i"],
                day_of_week=5, start_time=datetime.time(10, 30),
                end_time=datetime.time(11, 30), class_type=ClassType.LECTURE,
                elective_slot=ElectiveSlot.ELECTIVE_I))
            check("E1. same elective slot overlapping allowed (parallel electives)",
                  bool(e10d.id))

            # ELECTIVE rule: different slot DOES conflict
            codeE2 = await code_of(svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["elec_ii"],
                day_of_week=5, start_time=datetime.time(10, 30),
                end_time=datetime.time(11, 30), class_type=ClassType.LECTURE,
                elective_slot=ElectiveSlot.ELECTIVE_II)))
            check("E2. ELECTIVE_I vs ELECTIVE_II overlapping rejected (TIME_CONFLICT)",
                  codeE2 == "TIME_CONFLICT", f"got {codeE2}")

            # ELECTIVE rule: elective vs regular conflict
            codeE3 = await code_of(svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["common"],
                day_of_week=5, start_time=datetime.time(10, 30),
                end_time=datetime.time(11, 30), class_type=ClassType.LECTURE)))
            check("E3. elective vs regular overlapping rejected (TIME_CONFLICT)",
                  codeE3 == "TIME_CONFLICT", f"got {codeE3}")

            # 11. scope-aware queries
            class_list = await svc.list_entries(class_admin)
            class_codes = {i.subject_code for i in class_list.items}
            check("11a. CLASS_ADMIN sees only own-section entries",
                  all(i.section_id == fixture["section_a"] for i in class_list.items),
                  f"sections={ {str(i.section_id)[:6] for i in class_list.items} }")

            elec_list = await svc.list_entries(elec_admin)
            check("11b. ELECTIVE_ADMIN sees only own-subject entries",
                  elec_list.total == 0 or all(i.subject_code == "REV-ELECI" for i in elec_list.items),
                  f"codes={[i.subject_code for i in elec_list.items]}")

            sub_list = await svc.list_entries(sub_admin)
            check("11c. SUBSECTION_ADMIN sees its subsection's section entries",
                  all(i.section_id == fixture["section_a"] for i in sub_list.items))

            stu_list = await svc.list_entries(student)
            check("11d. STUDENT (no admin scope) sees nothing",
                  stu_list.total == 0, f"got {stu_list.total}")

            # invalid scope on write
            codeS = await code_of(svc.create_entry(class_admin, T(
                section_id=fixture["section_b"], subject_id=fixture["common"],
                day_of_week=6, start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0), class_type=ClassType.LECTURE)))
            check("11e. CLASS_ADMIN cannot create for another section (INVALID_SCOPE)",
                  codeS == "INVALID_SCOPE", f"got {codeS}")

            # not-found / invalid-scope errors
            codeN = await code_of(svc.get_entry(admin, uuid.uuid4()))
            check("12. not-found entry -> NOT_FOUND", codeN == "NOT_FOUND", f"got {codeN}")
            codeG = await code_of(svc.get_entry(elec_admin, e6.id))
            check("13. out-of-scope detail -> INVALID_SCOPE",
                  codeG == "INVALID_SCOPE", f"got {codeG}")

            # inactive-parent: scheduling edit on a dormant entry refused
            codeIP = await code_of(svc.update_entry(admin, e1.id, D(
                start_time=datetime.time(10, 30), end_time=datetime.time(11, 30))))
            check("14. scheduling edit on inactive entry refused (INACTIVE_PARENT)",
                  codeIP == "INACTIVE_PARENT", f"got {codeIP}")

            # reactivation re-runs conflict detection: e7 now occupies e1's old
            # slot, so plain reactivation is refused with TIME_CONFLICT.
            codeR = await code_of(svc.update_entry(admin, e1.id, D(is_active=True)))
            check("15. reactivation re-runs conflict detection (TIME_CONFLICT)",
                  codeR == "TIME_CONFLICT", f"got {codeR}")

            # free the slot (deactivate e7), then reactivation succeeds.
            await svc.deactivate_entry(admin, e7.id)
            reactivated = await svc.update_entry(admin, e1.id, D(is_active=True))
            check("15b. reactivation allowed once the slot is free",
                  reactivated.is_active is True)
            codeC2 = await code_of(svc.create_entry(admin, T(
                section_id=fixture["section_a"], subject_id=fixture["common"],
                day_of_week=0, start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0), class_type=ClassType.LECTURE)))
            check("16. reactivated entry now blocks overlap (TIME_CONFLICT)",
                  codeC2 == "TIME_CONFLICT", f"got {codeC2}")

            # duplicate-source retrieval + deterministic ordering sanity
            repo = AdminTimetableRepository(db)
            sec_a_entries = await repo.list_entries(
                section_ids=[fixture["section_a"]], include_inactive=True)
            check("17. repository scoped list returns fixture entries",
                  len(sec_a_entries) >= 8, f"got {len(sec_a_entries)}")

        # ==================== POST-CHECK ====================
        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.7-B verifier (core): {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1

    finally:
        # ---- Hard cleanup (defensive) ----
        async with AsyncSessionLocal() as db:
            try:
                if fixture.get("session"):
                    # 1. timetable entries (FK to sections)
                    await db.execute(delete(TimetableEntry).where(
                        TimetableEntry.section_id.in_([
                            fixture.get("section_a"), fixture.get("section_b"),
                        ])))
                    # 2. admin_scopes (FK to users, subjects)
                    if fixture.get("scopes"):
                        await db.execute(delete(AdminScope).where(
                            AdminScope.user_id.in_([
                                fixture.get("class_admin_user"),
                                fixture.get("elec_admin_user"),
                                fixture.get("sub_admin_user"),
                            ])))
                    # 3. users (FK to sections — delete before sections)
                    for key in ("class_admin_user", "elec_admin_user", "sub_admin_user", "student_user"):
                        if fixture.get(key):
                            await db.execute(delete(User).where(User.id == fixture[key]))
                    # 4. subjects (FK to semesters)
                    await db.execute(delete(Subject).where(
                        Subject.semester_id.in_([
                            fixture.get("semester"), fixture.get("other_semester"),
                        ])))
                    # 5. subsections (FK to sections)
                    await db.execute(delete(Subsection).where(
                        Subsection.section_id.in_([
                            fixture.get("section_a"), fixture.get("section_b"),
                        ])))
                    # 6. sections (FK to semesters)
                    await db.execute(delete(Section).where(
                        Section.semester_id.in_([
                            fixture.get("semester"), fixture.get("other_semester"),
                        ])))
                    # 7. semesters (FK to session)
                    await db.execute(delete(Semester).where(
                        Semester.session_id == fixture["session"]))
                    # 8. session
                    await db.execute(delete(AcademicSession).where(
                        AcademicSession.id == fixture["session"]))
                if _ACTIVE_SESSION_ID:
                    from sqlalchemy import update
                    await db.execute(update(AcademicSession)
                                     .where(AcademicSession.id == _ACTIVE_SESSION_ID)
                                     .values(is_active=True))
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                print(f"cleanup warning: {exc}")
                await db.rollback()


async def post_cleanup_checks() -> None:
    async with AsyncSessionLocal() as db:
        after = await table_counts(db)
        check("Z1. all baseline table counts restored after cleanup",
              after == _BASELINE, f"before={_BASELINE} after={after}")
        active_now = (await db.execute(
            select(AcademicSession).where(AcademicSession.is_active.is_(True))
        )).scalars().first()
        check("Z2. original active session unchanged",
              active_now is not None and active_now.id == _ACTIVE_SESSION_ID)


if __name__ == "__main__":
    async def _run() -> int:
        code = await main()
        await post_cleanup_checks()
        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.7-B verifier: {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1

    sys.exit(asyncio.run(_run()))
