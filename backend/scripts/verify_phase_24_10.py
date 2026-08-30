"""
Phase 24.10 â€” Subject-Specific Elective Events verifier.

Proves the divergent elective-event capability end-to-end: subject-scoped
events targeting ONE concrete elective subject produce per-subject
occurrence_outcomes on the shared anchor session while other subjects sharing
the same elective slot remain untouched â€” with no per-student event copies,
no anchor leakage, idempotent synchronization, and full baseline restoration.

The divergence pipeline is the CANONICAL one (Phase 23.6/23.7/23.8):
AcademicEvent -> EventService -> event_registry -> EventSessionSynchronizer
->_reconcile_outcomes -> occurrence_outcomes. This verifier proves it through
the Phase 24.9 admin Events API (no new endpoints, no new engine).

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
from app.models.academic import (AcademicSession, Semester, Subject,
                                 StudentElectiveChoice, StudentEnrollment)
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


def next_weekday_date(start: datetime.date, weekday: int) -> datetime.date:
    """First date >= start whose Python weekday() == weekday (0=Mon..4=Fri)."""
    d = start
    while d.weekday() != weekday:
        d += datetime.timedelta(days=1)
    return d


async def main() -> int:
    global _BASELINE, _ACTIVE_SESSION_ID
    print("=" * 64)
    print("Phase 24.10 â€” Subject-Specific Elective Events")
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
            bcs56 = (await db.execute(select(Subject).where(Subject.code == "BCS-056"))).scalars().first()
            bcs501 = (await db.execute(select(Subject).where(Subject.code == "BCS-501"))).scalars().first()
            if not all([bcs58, bcs55, bcs56, bcs501]):
                check("0. DE-II members + common subject found", False); return 1
            fx["bcs58"] = bcs58.id; fx["bcs55"] = bcs55.id
            fx["bcs56"] = bcs56.id; fx["bcs501"] = bcs501.id
            check("0. all three subjects share ELECTIVE_II slot",
                  bcs58.elective_slot == ElectiveSlot.ELECTIVE_II
                  and bcs55.elective_slot == ElectiveSlot.ELECTIVE_II
                  and bcs56.elective_slot == ElectiveSlot.ELECTIVE_II)

            # Find a weekday (Mon-Fri) where the DE-II anchor has a timetable
            # session, then compute a date in the semester with that weekday
            # that has NO existing active events for the three subjects.
            entries = (await db.execute(
                select(TimetableEntry).where(
                    TimetableEntry.subject_id == bcs58.id,
                    TimetableEntry.elective_slot.isnot(None),
                    TimetableEntry.day_of_week.in_([0, 1, 2, 3, 4]),
                )
            )).scalars().all()
            if not entries:
                check("0. DE-II anchor weekday timetable entry", False); return 1
            sem = (await db.execute(select(Semester).where(Semester.id == bcs58.semester_id))).scalars().first()
            target_date = None
            for entry in entries:
                cand = next_weekday_date(datetime.date(2026, 11, 2), entry.day_of_week)
                while cand <= sem.end_date:
                    stmt = select(func.count()).select_from(AcademicEvent).where(
                        AcademicEvent.active.is_(True),
                        AcademicEvent.start_date == cand,
                        AcademicEvent.subject_id.in_([bcs58.id, bcs55.id, bcs56.id]),
                    )
                    n = (await db.execute(stmt)).scalar_one()
                    if n == 0:
                        target_date = cand
                        break
                    cand += datetime.timedelta(days=7)
                if target_date:
                    break
            if target_date is None:
                check("0. clean divergence date found", False); return 1
            fx["D"] = target_date
            print(f"divergence date: {target_date} (DE-II slot has a timetable session)")

            # Fixture section (real active semester) + users
            fsec = Section(name="REV-24.10-SEC", program="BTech", semester_id=sem.id)
            db.add(fsec); await db.flush(); fx["section"] = fsec.id
            classA = User(roll_number=f"2401340{uuid.uuid4().hex[:6]}", name="Ph2410 CLASS", hashed_password="x", section_id=fsec.id)
            elecA = User(roll_number=f"2401341{uuid.uuid4().hex[:6]}", name="Ph2410 ELECTIVE", hashed_password="x", section_id=fsec.id)
            stu = User(roll_number=f"2401342{uuid.uuid4().hex[:6]}", name="Ph2410 STU", hashed_password="x", section_id=fsec.id)
            stuA = User(roll_number=f"2401343{uuid.uuid4().hex[:6]}", name="StuA 2410", hashed_password="x", section_id=fsec.id)
            stuB = User(roll_number=f"2401344{uuid.uuid4().hex[:6]}", name="StuB 2410", hashed_password="x", section_id=fsec.id)
            db.add_all([classA, elecA, subA := User(roll_number=f"2401345{uuid.uuid4().hex[:6]}", name="Ph2410 SUBSEC", hashed_password="x", section_id=fsec.id), stu, stuA, stuB])
            await db.flush()
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
            # Enrollments: Student A -> BCS-058; Student B -> BCS-055 (canonical resolution)
            db.add_all([
                StudentEnrollment(user_id=stuA.id, subject_id=bcs58.id, enrollment_type="ELECTIVE"),
                StudentEnrollment(user_id=stuB.id, subject_id=bcs55.id, enrollment_type="ELECTIVE"),
            ])
            await db.commit()

        transport = ASGITransport(app=app)
        P = "/api/v1/admin/events"
        D = fx["D"].isoformat()
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            async def tok(uid):
                u = (await db.execute(select(User).where(User.id == uid))).scalars().first()
                return create_access_token(subject=str(u.id), roll_number=u.roll_number)
            async with AsyncSessionLocal() as db:
                t_head = await tok(admin.id)
                t_elec = await tok(fx["elecA"])
                t_stu = await tok(fx["stu"])
            h = {"Authorization": f"Bearer {t_head}"}

            # 1. Phase 24.9 behavior intact: unauth + STUDENT 401/403
            r = await c.get(P)
            check("1a. unauth GET -> 401", r.status_code == 401)
            r = await c.get(P, headers={"Authorization": f"Bearer {t_stu}"})
            check("1b. STUDENT GET -> 403", r.status_code == 403, str(r.status_code))

            # 3. ELECTIVE_ADMIN (BCS-058) creates a subject-specific SURPRISE_QUIZ
            r = await c.post(P, json={
                "event_type": "SURPRISE_QUIZ", "start_date": D, "end_date": D,
                "subject_id": str(fx["bcs58"]), "class_type": "L",
            }, headers={"Authorization": f"Bearer {t_elec}"})
            check("3. ELECTIVE_ADMIN creates subject-specific SURPRISE_QUIZ for BCS-058 -> 201",
                  r.status_code == 201, f"{r.status_code} {r.text[:150]}")
            fx["sq58"] = r.json()["event"]["id"] if r.status_code == 201 else None
            check("3b. subject_slot surfaced (ELECTIVE_II member)",
                  r.json()["event"]["subject_slot"] == "ELECTIVE_II", str(r.json()["event"].get("subject_slot")))
            check("3c. can_mutate true for owning ELECTIVE_ADMIN",
                  r.json()["event"]["can_mutate"] is True)

            # 4. Same slot, same date, DIFFERENT subject: CLASS_CANCELLED for BCS-056
            r = await c.post(P, json={
                "event_type": "CLASS_CANCELLED", "start_date": D, "end_date": D,
                "subject_id": str(fx["bcs56"]), "class_type": "L",
            }, headers=h)
            check("4. divergent same-slot/same-date CLASS_CANCELLED for BCS-056 -> 201",
                  r.status_code == 201, f"{r.status_code} {r.text[:150]}")
            fx["cc56"] = r.json()["event"]["id"] if r.status_code == 201 else None

            # 18/19. duplicate protection: same subject/type/date -> 409
            r = await c.post(P, json={
                "event_type": "SURPRISE_QUIZ", "start_date": D, "end_date": D,
                "subject_id": str(fx["bcs58"]), "class_type": "L",
            }, headers=h)
            check("18. duplicate SURPRISE_QUIZ BCS-058 -> 409", r.status_code == 409, str(r.status_code))

            # 5/6/8. outcome composition: BCS-058 SURPRISE_QUIZ + BCS-056 CANCELLED;
            #        BCS-055 has NO outcome (normal lecture); anchor session NOT cancelled.
            async with AsyncSessionLocal() as db:
                anchor_entry = (await db.execute(
                    select(TimetableEntry).where(
                        TimetableEntry.subject_id == fx["bcs58"],
                        TimetableEntry.elective_slot.isnot(None),
                        TimetableEntry.day_of_week == fx["D"].weekday(),
                    )
                )).scalars().first()
                anchor_session = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.timetable_entry_id == anchor_entry.id,
                        ClassSession.date == fx["D"],
                    )
                )).scalars().first()
                check("5. shared anchor session exists for the slot", anchor_session is not None)
                if anchor_session is None:
                    return 1
                fx["anchor_session_id"] = anchor_session.id
                outcomes = (await db.execute(
                    select(OccurrenceOutcome).where(
                        OccurrenceOutcome.class_session_id == anchor_session.id,
                    )
                )).scalars().all()
                by_subject = {str(o.subject_id): o.outcome_type.value for o in outcomes}
                check("6a. BCS-058 outcome = SURPRISE_QUIZ",
                      by_subject.get(str(fx["bcs58"])) == "SURPRISE_QUIZ", str(by_subject))
                check("6b. BCS-056 outcome = CANCELLED",
                      by_subject.get(str(fx["bcs56"])) == "CANCELLED", str(by_subject))
                check("6c. BCS-055 has NO outcome (normal lecture)",
                      str(fx["bcs55"]) not in by_subject, str(by_subject))
                check("6d. anchor session itself NOT cancelled (shared occurrence intact)",
                      anchor_session.is_cancelled is False)
                check("6e. exactly 2 outcome rows (no per-student duplication)", len(outcomes) == 2, f"n={len(outcomes)}")

            # 7. EXTRA_* fallback: an EXTRA_LECTURE for BCS-058 on a weekday the
            #    slot does NOT occupy materializes an extra session for THAT
            #    subject only (the Phase 23.6 fallback path).
            slot_weekdays = set()
            async with AsyncSessionLocal() as db:
                rows = (await db.execute(
                    select(TimetableEntry.day_of_week).where(
                        TimetableEntry.subject_id == fx["bcs58"],
                        TimetableEntry.elective_slot.isnot(None),
                    )
                )).all()
                slot_weekdays = {r[0] for r in rows}
            fb_weekday = next(w for w in range(5) if w not in slot_weekdays)
            ED = next_weekday_date(datetime.date(2026, 11, 2), fb_weekday)
            r = await c.post(P, json={
                "event_type": "EXTRA_LECTURE", "start_date": ED.isoformat(), "end_date": ED.isoformat(),
                "subject_id": str(fx["bcs58"]), "class_type": "L",
            }, headers=h)
            check("7a. EXTRA_LECTURE for BCS-058 (no slot session) -> 201",
                  r.status_code == 201, f"{r.status_code} {r.text[:150]}")
            fx["extra58"] = r.json()["event"]["id"] if r.status_code == 201 else None
            async with AsyncSessionLocal() as db:
                extra_sessions = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.date == ED,
                        ClassSession.is_extra.is_(True),
                    )
                )).scalars().all()
                check("7b. extra session belongs ONLY to BCS-058",
                      len(extra_sessions) == 1 and str(extra_sessions[0].subject_id) == str(fx["bcs58"]),
                      f"subjects={[str(s.subject_id)[:8] for s in extra_sessions]}")

            # 10. Idempotency: no-op PATCH (unchanged fields) -> no outcome churn
            before_n = len((await AsyncSessionLocal().__aenter__()).execute(
                select(OccurrenceOutcome)).scalars().all()) if False else None
            r = await c.patch(f"{P}/{fx['sq58']}", json={}, headers=h)
            check("10a. no-op PATCH -> 200", r.status_code == 200, str(r.status_code))
            async with AsyncSessionLocal() as db:
                n_out = (await db.execute(
                    select(func.count()).select_from(OccurrenceOutcome).where(
                        OccurrenceOutcome.class_session_id == fx["anchor_session_id"])
                )).scalar_one()
            check("10b. outcome count unchanged after no-op PATCH (idempotent)", n_out == 2, f"n={n_out}")

            # 11. PATCH move: move BCS-058 SURPRISE_QUIZ off D -> its outcome removed
            moved = D and (fx["D"] + datetime.timedelta(days=1)).isoformat()
            r = await c.patch(f"{P}/{fx['sq58']}", json={"start_date": moved, "end_date": moved}, headers=h)
            check("11a. PATCH move -> 200", r.status_code == 200, str(r.status_code))
            async with AsyncSessionLocal() as db:
                outcomes = (await db.execute(
                    select(OccurrenceOutcome).where(
                        OccurrenceOutcome.class_session_id == fx["anchor_session_id"])
                )).scalars().all()
                by_subject = {str(o.subject_id): o.outcome_type.value for o in outcomes}
            check("11b. BCS-058 outcome removed after move", str(fx["bcs58"]) not in by_subject, str(by_subject))
            check("11c. BCS-056 outcome untouched by the move",
                  by_subject.get(str(fx["bcs56"])) == "CANCELLED", str(by_subject))
            # Move back for deactivation symmetry
            r = await c.patch(f"{P}/{fx['sq58']}", json={"start_date": D, "end_date": D}, headers=h)
            check("11d. PATCH move back -> 200", r.status_code == 200, str(r.status_code))

            # 12. DELETE = safe deactivation; outcome reversal (state-based)
            r = await c.delete(f"{P}/{fx['sq58']}", headers=h)
            check("12a. DELETE BCS-058 SURPRISE_QUIZ -> 200 (deactivation)", r.status_code == 200, str(r.status_code))
            async with AsyncSessionLocal() as db:
                outcomes = (await db.execute(
                    select(OccurrenceOutcome).where(
                        OccurrenceOutcome.class_session_id == fx["anchor_session_id"])
                )).scalars().all()
                by_subject = {str(o.subject_id): o.outcome_type.value for o in outcomes}
                row = (await db.execute(
                    select(AcademicEvent).where(AcademicEvent.id == fx["sq58"])
                )).scalars().first()
            check("12b. BCS-058 outcome removed after deactivation",
                  str(fx["bcs58"]) not in by_subject, str(by_subject))
            check("12c. row preserved (active=false) â€” not physically deleted",
                  row is not None and row.active is False)
            check("12d. BCS-056 CANCELLED outcome preserved (isolated reversal)",
                  by_subject.get(str(fx["bcs56"])) == "CANCELLED", str(by_subject))

            # 13. Historical attendance untouched (baseline count enforced at Z1)

            # 14. QUIZ_DAY ownership guard still intact (Phase 24.9)
            async with AsyncSessionLocal() as db:
                sm_event = (await db.execute(
                    select(AcademicEvent).where(
                        AcademicEvent.event_type == "QUIZ_DAY",
                        AcademicEvent.active.is_(True),
                        AcademicEvent.subject_id == fx["bcs501"],
                    ).order_by(AcademicEvent.start_date)
                )).scalars().first()
            r = await c.delete(f"{P}/{sm_event.id}", headers=h)
            check("14. schedule-managed QUIZ_DAY DELETE -> 409 (guard intact)",
                  r.status_code == 409, str(r.status_code))

            # 15. Standalone QUIZ_DAY unchanged
            r = await c.post(P, json={
                "event_type": "QUIZ_DAY", "start_date": "2026-11-26", "end_date": "2026-11-26",
                "subject_id": str(fx["bcs501"]),
            }, headers=h)
            check("15. standalone QUIZ_DAY -> 201 (unchanged)", r.status_code == 201, str(r.status_code))
            fx["standalone"] = r.json()["event"]["id"] if r.status_code == 201 else None

            # 2/16/17. Scope isolation: BCS-055 events invisible to ELECTIVE_ADMIN (BCS-058)
            r = await c.post(P, json={
                "event_type": "EXTRA_LECTURE", "start_date": "2026-11-27", "end_date": "2026-11-27",
                "subject_id": str(fx["bcs55"]), "class_type": "L",
            }, headers=h)
            check("17a. HEAD creates BCS-055 event -> 201", r.status_code == 201, str(r.status_code))
            fx["ev55"] = r.json()["event"]["id"] if r.status_code == 201 else None
            r = await c.get(f"{P}/{fx['ev55']}", headers={"Authorization": f"Bearer {t_elec}"})
            check("17b. ELECTIVE_ADMIN (BCS-058) cannot read BCS-055 event -> 404",
                  r.status_code == 404, str(r.status_code))
            r = await c.patch(f"{P}/{fx['ev55']}", json={"active": False},
                              headers={"Authorization": f"Bearer {t_elec}"})
            check("17c. ELECTIVE_ADMIN cannot mutate BCS-055 event -> 403/404",
                  r.status_code in (403, 404), str(r.status_code))
            # 20. Client spoofing cannot bypass
            r = await c.post(P, params={"role": "HEAD_ADMIN"}, json={
                "event_type": "EXTRA_LECTURE", "start_date": "2026-11-27", "end_date": "2026-11-27",
                "subject_id": str(fx["bcs55"]), "class_type": "L",
            }, headers={"Authorization": f"Bearer {t_elec}"})
            check("20. spoofed role param cannot elevate ELECTIVE_ADMIN -> 403",
                  r.status_code == 403, str(r.status_code))

            # 16. ElectiveResolver unchanged: student A resolves BCS-058 (choice intact)
            r = await c.get("/api/v1/quiz-eligibility/BCS-058/1",
                            headers={"Authorization": f"Bearer {t_stuA}"} if False else h)
            # (student A check via enrollment â€” reuse the 24.9 pattern)
            async with AsyncSessionLocal() as db:
                stuA_user = (await db.execute(select(User).where(User.id == fx["stuA"]))).scalars().first()
            tokA = create_access_token(subject=str(stuA_user.id), roll_number=stuA_user.roll_number)
            r = await c.get("/api/v1/quiz-eligibility/BCS-058/1",
                            headers={"Authorization": f"Bearer {tokA}"})
            check("16. ElectiveResolver resolution intact (Student A BCS-058 -> 200)",
                  r.status_code == 200, str(r.status_code))

        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.10 verifier (core): {passed}/{len(results)} PASS")

        # ---- Canonical cleanup: deactivate fixture events through the API so
        # the synchronizer reverses all composed outcomes/sessions ----
        async with AsyncSessionLocal() as db:
            admin2 = (await db.execute(select(User).where(User.role == UserRole.ADMIN))).scalars().first()
        tok_head = create_access_token(subject=str(admin2.id), roll_number=admin2.roll_number)
        async with AsyncClient(transport=transport, base_url="http://test") as cc:
            for k in ("sq58", "cc56", "extra58", "standalone", "ev55"):
                eid = fx.get(k)
                if eid:
                    # Idempotent deactivation via the canonical DELETE path.
                    await cc.delete(f"{P}/{eid}", headers={"Authorization": f"Bearer {tok_head}"})
        return 0 if passed == len(results) else 1

    finally:
        async with AsyncSessionLocal() as db:
            try:
                # Raw-delete fixture event rows (already deactivated via the API
                # above — outcomes/sessions were canonically reversed) plus any
                # residual sync-created sessions on the verifier dates.
                ev_ids = [fx.get(k) for k in ("sq58", "cc56", "extra58", "standalone", "ev55", "class_extra_id", "elec_extra_id")]
                ev_ids = [e for e in ev_ids if e]
                if fx.get("D"):
                    all_dates = [fx["D"], fx["D"] + datetime.timedelta(days=1),
                                 fx["D"] + datetime.timedelta(days=7),
                                 datetime.date(2026, 11, 24), datetime.date(2026, 11, 26),
                                 datetime.date(2026, 11, 27)]
                    # Remove residual outcomes on the real anchor sessions for the
                    # verifier's (session, subject) pairs only.
                    if ev_ids:
                        rows = (await db.execute(
                            select(OccurrenceOutcome).where(
                                OccurrenceOutcome.subject_id.in_([fx["bcs58"], fx["bcs56"], fx["bcs55"]]))
                        )).scalars().all()
                        real_sessions = (await db.execute(
                            select(ClassSession.id).where(
                                ClassSession.date.in_(all_dates),
                                ClassSession.timetable_entry_id.isnot(None))
                        )).scalars().all()
                        real_ids = set(real_sessions)
                        for o in rows:
                            if o.class_session_id in real_ids:
                                await db.execute(delete(OccurrenceOutcome).where(OccurrenceOutcome.id == o.id))
                    await db.execute(delete(ClassSession).where(
                        ClassSession.date.in_(all_dates),
                        ClassSession.timetable_entry_id.is_(None),
                    ))
                if ev_ids:
                    await db.execute(delete(AcademicEvent).where(AcademicEvent.id.in_(ev_ids)))
                if fx.get("section"):
                    await db.execute(delete(AdminScope).where(
                        AdminScope.user_id.in_([fx["classA"], fx["elecA"], fx["subA"]])))
                    await db.execute(delete(StudentElectiveChoice).where(
                        StudentElectiveChoice.user_id.in_([fx["stuA"], fx["stuB"]])))
                    await db.execute(delete(StudentEnrollment).where(
                        StudentEnrollment.user_id.in_([fx["stuA"], fx["stuB"]]))
                    )
                    for k in ("classA", "elecA", "subA", "stu", "stuA", "stuB"):
                        await db.execute(delete(User).where(User.id == fx[k]))
                    await db.execute(delete(Section).where(Section.id == fx["section"]))
                if _ACTIVE_SESSION_ID:
                    await db.execute(update(AcademicSession).where(
                        AcademicSession.id == _ACTIVE_SESSION_ID).values(is_active=True))
                await db.commit()
            except Exception as e: print(f"cleanup: {e}"); await db.rollback()

async def post_cleanup():
    async with AsyncSessionLocal() as db:
        after = await counts(db)
        check("21. baseline restored", after == _BASELINE, f"before={_BASELINE} after={after}")
        a = (await db.execute(select(AcademicSession).where(AcademicSession.is_active.is_(True)))).scalars().first()
        check("21b. active session unchanged", a is not None and a.id == _ACTIVE_SESSION_ID)

if __name__ == "__main__":
    async def _run():
        c = await main()
        await post_cleanup()
        p = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.10 verifier: {p}/{len(results)} PASS")
        return 0 if p == len(results) else 1
    sys.exit(asyncio.run(_run()))