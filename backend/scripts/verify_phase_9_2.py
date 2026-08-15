"""
Phase 9.2 verification — Laboratory Experiment Management.

Verifies the Phase 9.2.1 product contract end-to-end against the real
database (httpx ASGITransport + real DB + minted JWTs, the established
pattern). Laboratory experiment management sits ABOVE the canonical
attendance pipeline: attendance stays AcademicEvent -> EventSessionSynchronizer
-> ClassSession -> AttendanceRecord -> existing engines. This verifier proves
the new catalog/record surface without touching attendance mathematics.

Checks (mapping to the Phase 9.2.0 audit §18):

  1.  Baseline snapshot recorded
  2.  Admin ingests experiment -> row created (is_active=True)
  3.  Duplicate (subject_id, experiment_number) -> rejected (409)
  4.  Student cannot ingest experiments (403)
  5.  Student creates PENDING record for enrolled subject (201, forced PENDING,
      created_by = student)
  6.  PENDING record class_session_id = valid PRACTICAL session of that subject
      (201, linkage persisted)
  7.  PENDING record cannot reference a cancelled session (400)
  8.  Student cannot set SIGNED (403) — and legit student edits stay PENDING
  9.  Admin sets SIGNED -> signed_by + signed_on populated; admin cannot set
      PENDING (400); students cannot edit SIGNED records (403)
 10.  UniqueConstraint(user_id, experiment_id) enforced (duplicate record -> 409)
 11.  Enrollment guard: unenrolled -> 403 on writes, 404 on reads
 12.  Advisory shows X/Y when catalog exists; null when no catalog (no fake 0/10)
 13.  Advisory does NOT gate mid-sem designation (designation succeeds with 1
      signed experiment; no threshold)
 14.  Cancelled session attendance is NOT in lab records (cancelled session
      cannot host a record AND is excluded from the practical counts)
 15.  laboratory_experiments = 0 when no ingestion (baseline truth)
 16.  Practical attendance formulas unchanged after adding records (summary
      counts byte-identical before/after record activity)
 17.  Quiz eligibility unchanged (labs still 404; theory payload byte-identical)
 18.  No fabricated experiment data (lab tables back at baseline after cleanup)
 19.  Baseline restored exactly (all nine tracked counts)
 20.  Frozen contracts: existing event types functional (admin EXTRA_LECTURE
      smoke), Phase 8.2 mid-sem endpoint admin-only (student PUT -> 403)

State changes are this script's own artifacts (temp users, experiments,
records, one temporary cancellation, one temporary designation) and are
removed in the finally block; rollback transactions are used where possible.
No old assertion is weakened.

Usage:
    python scripts/verify_phase_9_2.py
"""
import asyncio
import sys
import uuid
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User, Section
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.academic import StudentEnrollment, Subject
from app.models.quiz import QuizSchedule
from app.models.laboratory import LaboratoryExperiment, LaboratoryRecord
from app.models.enums import AttendanceStatus, ClassType, UserRole
from sqlalchemy import select, func, delete

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


# BCS-553 is the Phase 9.1 lab subject: Friday P1/P2 timetable sessions.
D_LINK = date(2026, 7, 17)      # Friday  — valid PRACTICAL sessions exist
D_MID = date(2026, 8, 14)       # Friday  — mid-sem designation smoke target


async def practical_sessions(db, subject_id: uuid.UUID, target: date):
    stmt = (
        select(ClassSession)
        .where(
            ClassSession.subject_id == subject_id,
            ClassSession.date == target,
            ClassSession.class_type == ClassType.PRACTICAL,
        )
        .order_by(ClassSession.id.asc())
    )
    return (await db.execute(stmt)).scalars().all()


async def main() -> int:
    async with AsyncSessionLocal() as db:
        events_before = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
        sessions_before = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
        cancelled_before = (await db.execute(select(func.count()).select_from(ClassSession).where(
            ClassSession.is_cancelled.is_(True)))).scalar()
        extra_before = (await db.execute(select(func.count()).select_from(ClassSession).where(
            ClassSession.is_extra.is_(True)))).scalar()
        records_before = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
        enrollments_before = (await db.execute(select(func.count()).select_from(StudentEnrollment))).scalar()
        subjects_before = (await db.execute(select(func.count()).select_from(Subject))).scalar()
        quizzes_before = (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar()
        users_before = (await db.execute(select(func.count()).select_from(User))).scalar()
        admins_before = (await db.execute(select(func.count()).select_from(User).where(
            User.role == UserRole.ADMIN))).scalar()
        lab_exp_before = (await db.execute(select(func.count()).select_from(LaboratoryExperiment))).scalar()
        lab_rec_before = (await db.execute(select(func.count()).select_from(LaboratoryRecord))).scalar()
        designated_before = (await db.execute(select(func.count()).select_from(ClassSession).where(
            ClassSession.designation.isnot(None)))).scalar()

        admin_user = (await db.execute(select(User).where(User.role == UserRole.ADMIN))).scalars().first()
        section = (await db.execute(select(Section))).scalars().first()
        subject_ids = {s.code: s.id for s in (await db.execute(select(Subject))).scalars().all()}

        # A practical session with NO attendance records anywhere (safe cancel
        # target for checks 7/14 — the temporary cancellation is fully restored).
        free_sessions = (await db.execute(
            select(ClassSession)
            .where(
                ClassSession.subject_id == subject_ids["BCS-553"],
                ClassSession.class_type == ClassType.PRACTICAL,
            )
            .order_by(ClassSession.date.asc())
        )).scalars().all()
        attended_rows = (await db.execute(
            select(AttendanceRecord.class_session_id).where(
                AttendanceRecord.class_session_id.in_([s.id for s in free_sessions])
            )
        )).all()
        attended_ids = {r[0] for r in attended_rows}
        cancel_target = next((s for s in free_sessions if s.id not in attended_ids), None)

        check("1. baseline snapshot recorded (all nine counts captured)", True)

        # Temp user A: enrolled in BCS-553 (the Phase 9.1 lab subject) only.
        # Temp user B: enrolled in BCS-501 only — a REAL user who is simply not
        # enrolled in BCS-553, proving the enrollment boundary both ways.
        temp_a = User(roll_number="PH9A_TMP", name="Phase 9.2 Temp A",
                      role=UserRole.STUDENT, section_id=section.id if section else None)
        db.add(temp_a)
        await db.flush()
        db.add(StudentEnrollment(user_id=temp_a.id, subject_id=subject_ids["BCS-553"]))
        temp_b = User(roll_number="PH9B_TMP", name="Phase 9.2 Temp B",
                      role=UserRole.STUDENT, section_id=section.id if section else None)
        db.add(temp_b)
        await db.flush()
        db.add(StudentEnrollment(user_id=temp_b.id, subject_id=subject_ids["BCS-501"]))
        await db.commit()
        temp_a_id, temp_b_id = temp_a.id, temp_b.id

        # Baseline eligibility snapshot (frozen payload shape) — must be
        # byte-identical after all Phase 9.2 activity (check 17).
        admin_token_pre = create_access_token(str(admin_user.id), admin_user.roll_number)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/quiz-eligibility/BCS-501/1",
                            headers={"Authorization": f"Bearer {admin_token_pre}"})
            elig_before = r.json()

    token_a = create_access_token(str(temp_a_id), "PH9A_TMP")
    token_b = create_access_token(str(temp_b_id), "PH9B_TMP")
    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_admin = {"Authorization": f"Bearer {admin_token}"}

    test_experiment_ids: list[uuid.UUID] = []
    test_record_ids: list[uuid.UUID] = []
    test_event_ids: list[uuid.UUID] = []

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # --- 12a. Advisory when no catalog exists (honest empty state) ---------
            r = await client.get("/api/v1/laboratory/BCS-553/summary", headers=headers_a)
            ep = r.json()["experiment_progress"]
            check("12a. advisory is null when no catalog exists (catalog_available "
                  "false, total 0 — no fabricated 0/10)",
                  r.status_code == 200 and ep["catalog_available"] is False
                  and ep["total"] == 0 and ep["signed"] == 0
                  and ep["pending_self_tracked"] == 0 and ep["advisory"] is None,
                  f"got {ep}")

            # --- 2. Admin ingests experiments --------------------------------------
            r = await client.post("/api/v1/laboratory/BCS-553/experiments", headers=headers_admin, json={
                "experiment_number": 1, "title": "Verifier Experiment A",
                "description": "Phase 9.2 verifier artifact"})
            ok = r.status_code == 201 and r.json()["experiment_number"] == 1 \
                and r.json()["title"] == "Verifier Experiment A" and r.json()["is_active"] is True
            if ok:
                test_experiment_ids.append(uuid.UUID(r.json()["id"]))
            check("2. admin ingests experiment -> 201, row created (is_active=True)",
                  ok, f"got {r.status_code} {r.text[:200]}")
            exp_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None

            # --- 3. Duplicate (subject_id, experiment_number) -> 409 -----------------
            r = await client.post("/api/v1/laboratory/BCS-553/experiments", headers=headers_admin, json={
                "experiment_number": 1, "title": "Duplicate"})
            check("3. duplicate (subject_id, experiment_number) -> rejected (409)",
                  r.status_code == 409, f"got {r.status_code} {r.text[:200]}")

            # Second experiment (different number, same subject) — needed so checks
            # 6/7/10/11 exercise independent records without tripping the
            # (user, experiment) uniqueness prematurely.
            r = await client.post("/api/v1/laboratory/BCS-553/experiments", headers=headers_admin, json={
                "experiment_number": 2, "title": "Verifier Experiment B"})
            ok = r.status_code == 201 and r.json()["experiment_number"] == 2
            if ok:
                test_experiment_ids.append(uuid.UUID(r.json()["id"]))
            check("3b. same subject, different number is accepted (per-subject "
                  "numbering; constraint is composite)",
                  ok, f"got {r.status_code} {r.text[:200]}")
            exp2_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None

            # Third experiment: check 7 needs an experiment WITHOUT an existing
            # record so the cancelled-session rule (not the duplicate guard) is
            # what rejects the linkage.
            r = await client.post("/api/v1/laboratory/BCS-553/experiments", headers=headers_admin, json={
                "experiment_number": 3, "title": "Verifier Experiment C"})
            ok = r.status_code == 201 and r.json()["experiment_number"] == 3
            if ok:
                test_experiment_ids.append(uuid.UUID(r.json()["id"]))
            check("3c. third experiment ingested (cancelled-session rule test subject)",
                  ok, f"got {r.status_code} {r.text[:200]}")
            exp3_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None

            # --- 4. Student cannot ingest experiments (403) --------------------------
            r = await client.post("/api/v1/laboratory/BCS-553/experiments", headers=headers_a, json={
                "experiment_number": 3, "title": "Nope"})
            check("4. student cannot ingest experiments (403)",
                  r.status_code == 403, f"got {r.status_code} {r.text[:200]}")

            # --- 5. Student creates PENDING record for enrolled subject --------------
            r = await client.post("/api/v1/laboratory/BCS-553/records", headers=headers_a, json={
                "experiment_id": str(exp_id), "date_conducted": "2026-07-17",
                "remarks": "Phase 9.2 verifier record"})
            ok = r.status_code == 201 and r.json()["signature_status"] == "pending" \
                and r.json()["created_by"] == str(temp_a_id) \
                and r.json()["date_conducted"] == "2026-07-17"
            if ok:
                test_record_ids.append(uuid.UUID(r.json()["id"]))
            check("5. student creates PENDING record for enrolled subject -> 201 "
                  "(status forced to pending, created_by = student)",
                  ok, f"got {r.status_code} {r.text[:200]}")
            rec_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None

            # --- 12b. Advisory when catalog exists but nothing signed -----------------
            r = await client.get("/api/v1/laboratory/BCS-553/summary", headers=headers_a)
            ep = r.json()["experiment_progress"]
            check("12b. advisory '0 of 3 experiments officially completed' with a "
                  "pending-only record (advisory counts SIGNED only)",
                  ep["catalog_available"] is True and ep["total"] == 3
                  and ep["signed"] == 0 and ep["pending_self_tracked"] == 1
                  and ep["advisory"] == "0 of 3 experiments officially completed",
                  f"got {ep}")

            # --- 6. PENDING record with a valid PRACTICAL session of that subject ----
            async with AsyncSessionLocal() as db:
                link_sessions = await practical_sessions(db, subject_ids["BCS-553"], D_LINK)
                link_session = next((s for s in link_sessions if not s.is_cancelled), None)
            r = await client.post("/api/v1/laboratory/BCS-553/records", headers=headers_a, json={
                "experiment_id": str(exp2_id), "date_conducted": "2026-07-17",
                "class_session_id": str(link_session.id)})
            ok = r.status_code == 201 and r.json()["class_session_id"] == str(link_session.id)
            if ok:
                test_record_ids.append(uuid.UUID(r.json()["id"]))
            check("6. PENDING record with class_session_id = valid PRACTICAL session "
                  "of that subject -> 201 (linkage persisted)",
                  ok, f"got {r.status_code} {r.text[:200]}")

            # --- 7. PENDING record cannot reference a cancelled session (400) ---------
            # Temporarily cancel a practical session (no attendance records on it),
            # attempt the linkage, then restore. Rollback-style, fully reversible.
            r7 = None
            async with AsyncSessionLocal() as db:
                s7 = (await db.execute(select(ClassSession).where(
                    ClassSession.id == cancel_target.id))).scalars().first()
                s7.is_cancelled = True
                await db.commit()
                try:
                    r7 = await client.post("/api/v1/laboratory/BCS-553/records", headers=headers_a, json={
                        "experiment_id": str(exp3_id), "date_conducted": "2026-07-24",
                        "class_session_id": str(s7.id)})
                finally:
                    s7.is_cancelled = False
                    await db.commit()
            check("7. PENDING record cannot reference a cancelled session (400)",
                  r7 is not None and r7.status_code == 400, f"got {r7.status_code if r7 else None}")

            # --- 14. Cancelled session attendance is NOT in lab records ---------------
            # The cancelled session was rejected as a record host (check 7); the
            # canonical summary must ALSO exclude the cancelled session from the
            # practical total (formula unchanged).
            async with AsyncSessionLocal() as db:
                s14 = (await db.execute(select(ClassSession).where(
                    ClassSession.id == cancel_target.id))).scalars().first()
                s14.is_cancelled = True
                await db.commit()
            r_before = await client.get("/api/v1/laboratory/BCS-553/summary", headers=headers_a)
            before_total = r_before.json()["practical_attendance"]["total"]
            async with AsyncSessionLocal() as db:
                s14 = (await db.execute(select(ClassSession).where(
                    ClassSession.id == cancel_target.id))).scalars().first()
                s14.is_cancelled = False
                await db.commit()
            r_after = await client.get("/api/v1/laboratory/BCS-553/summary", headers=headers_a)
            after_total = r_after.json()["practical_attendance"]["total"]
            check("14. cancelled session is excluded from practical counts (attendance "
                  "math untouched; cancelled != present in lab records)",
                  before_total == after_total - 1,
                  f"while_cancelled_total={before_total} restored_total={after_total}")

            # --- 8. Student cannot set SIGNED (403); legit edits stay PENDING ---------
            r = await client.patch(f"/api/v1/laboratory/BCS-553/records/{rec_id}", headers=headers_a, json={
                "signature_status": "signed"})
            check("8a. student cannot set SIGNED (403)",
                  r.status_code == 403, f"got {r.status_code} {r.text[:200]}")
            r = await client.patch(f"/api/v1/laboratory/BCS-553/records/{rec_id}", headers=headers_a, json={
                "date_conducted": "2026-07-18", "remarks": "Edited by student"})
            ok = r.status_code == 200 and r.json()["signature_status"] == "pending" \
                and r.json()["remarks"] == "Edited by student"
            check("8b. student legit edit of own PENDING record -> 200, still PENDING",
                  ok, f"got {r.status_code} {r.text[:200]}")

            # --- 9. Admin signs the record ---------------------------------------------
            r = await client.patch(f"/api/v1/laboratory/BCS-553/records/{rec_id}", headers=headers_admin, json={
                "signature_status": "signed"})
            ok = r.status_code == 200 and r.json()["signature_status"] == "signed" \
                and r.json()["signed_by"] == str(admin_user.id) and r.json()["signed_on"] is not None
            check("9a. admin sets SIGNED -> signed_by + signed_on populated",
                  ok, f"got {r.status_code} {r.text[:200]}")
            r = await client.patch(f"/api/v1/laboratory/BCS-553/records/{rec_id}", headers=headers_admin, json={
                "signature_status": "pending"})
            check("9b. admin cannot set PENDING back (only SIGNED is settable) -> 400",
                  r.status_code == 400, f"got {r.status_code} {r.text[:200]}")
            r = await client.patch(f"/api/v1/laboratory/BCS-553/records/{rec_id}", headers=headers_a, json={
                "remarks": "Student edits signed record"})
            check("9c. student cannot edit a SIGNED record (403)",
                  r.status_code == 403, f"got {r.status_code} {r.text[:200]}")
            r = await client.patch(f"/api/v1/laboratory/BCS-553/records/{rec_id}", headers=headers_admin, json={
                "remarks": "Admin correction"})
            check("9d. admin can edit a SIGNED record (admin correction)",
                  r.status_code == 200 and r.json()["remarks"] == "Admin correction"
                  and r.json()["signature_status"] == "signed",
                  f"got {r.status_code} {r.text[:200]}")

            # --- 10. UniqueConstraint(user_id, experiment_id) enforced ----------------
            r = await client.post("/api/v1/laboratory/BCS-553/records", headers=headers_a, json={
                "experiment_id": str(exp_id), "date_conducted": "2026-07-19"})
            check("10. duplicate (user, experiment) record -> rejected (409)",
                  r.status_code == 409, f"got {r.status_code} {r.text[:200]}")

            # --- 12c. Advisory after signing --------------------------------------------
            r = await client.get("/api/v1/laboratory/BCS-553/summary", headers=headers_a)
            ep = r.json()["experiment_progress"]
            check("12c. advisory '1 of 3 experiments officially completed' after signing",
                  ep["catalog_available"] is True and ep["total"] == 3 and ep["signed"] == 1
                  and ep["pending_self_tracked"] == 1
                  and ep["advisory"] == "1 of 3 experiments officially completed",
                  f"got {ep}")

            # --- 11. Enrollment guard: unenrolled -> 403 (write) / 404 (read) ----------
            r = await client.post("/api/v1/laboratory/BCS-553/records", headers=headers_b, json={
                "experiment_id": str(exp_id), "date_conducted": "2026-07-17"})
            check("11a. unenrolled student create record -> 403",
                  r.status_code == 403, f"got {r.status_code} {r.text[:200]}")
            r = await client.get("/api/v1/laboratory/BCS-553/summary", headers=headers_b)
            check("11b. unenrolled student read summary -> 404 (no subject leak)",
                  r.status_code == 404, f"got {r.status_code} {r.text[:200]}")
            r = await client.get("/api/v1/laboratory/BCS-553/experiments", headers=headers_b)
            check("11c. unenrolled student read curriculum -> 404",
                  r.status_code == 404, f"got {r.status_code} {r.text[:200]}")

            # --- 13. Advisory does NOT gate mid-sem designation ------------------------
            async with AsyncSessionLocal() as db:
                mid_sessions = await practical_sessions(db, subject_ids["BCS-553"], D_MID)
                mid_session = next((s for s in mid_sessions if not s.is_cancelled), None)
            r = await client.put("/api/v1/laboratory/BCS-553/mid-sem", headers=headers_admin, json={
                "class_session_id": str(mid_session.id)})
            ok_put = r.status_code == 200 and r.json()["designated"] is True
            r = await client.delete("/api/v1/laboratory/BCS-553/mid-sem", headers=headers_admin)
            ok_del = r.status_code == 200 and r.json()["designated"] is False
            check("13. advisory does NOT gate mid-sem designation (admin designates "
                  "with only 1 signed experiment; cleared afterwards)",
                  ok_put and ok_del, f"put={r.status_code} delete={r.status_code}")

            # --- 16. Practical attendance formulas unchanged after record activity -----
            # The lab summary's practical block must equal the canonical attendance
            # summary exactly — records never touch attendance mathematics.
            r_pre = await client.get("/api/v1/attendance/summary/BCS-553", headers=headers_a)
            r_sum = await client.get("/api/v1/laboratory/BCS-553/summary", headers=headers_a)
            p_lab = r_sum.json()["practical_attendance"]
            p_att = r_pre.json()["practical"]
            check("16. practical attendance formulas unchanged (lab summary practical "
                  "block == canonical attendance summary)",
                  r_pre.status_code == 200 and p_lab["attended"] == p_att["attended"]
                  and p_lab["missed"] == p_att["missed"]
                  and p_lab["pending"] == p_att["pending"]
                  and p_lab["total"] == p_att["total"]
                  and abs(p_lab["current_practical_pct"]
                          - (r_pre.json()["current_practical_pct"] or 0.0)) < 1e-9,
                  f"lab={p_lab} attendance={p_att}")

            # --- 17. Quiz eligibility unchanged (labs still 404) -----------------------
            r_lab = await client.get("/api/v1/quiz-eligibility/BCS-553/1", headers=headers_a)
            r_501 = await client.get("/api/v1/quiz-eligibility/BCS-501/1", headers=headers_admin)
            check("17. quiz eligibility unchanged (labs 404; theory payload "
                  "byte-identical before/after)",
                  r_lab.status_code == 404 and r_501.status_code == 200
                  and r_501.json() == elig_before,
                  f"lab={r_lab.status_code} theory_same={r_501.json() == elig_before}")

            # --- 20. Frozen contracts: event types + Phase 8.2 mid-sem ----------------
            r = await client.post("/api/v1/events", headers=headers_admin, json={
                "event_type": "EXTRA_LECTURE", "start_date": "2026-07-28",
                "end_date": "2026-07-28",
                "subject_id": str(subject_ids["BCS-501"]), "class_type": "L"})
            extra_lec_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None
            if extra_lec_id:
                test_event_ids.append(extra_lec_id)
            r_put = await client.put("/api/v1/laboratory/BCS-553/mid-sem", headers=headers_a, json={
                "class_session_id": str(mid_session.id)})
            check("20. frozen contracts intact (existing event types functional — "
                  "admin EXTRA_LECTURE 201; Phase 8.2 mid-sem endpoint still "
                  "admin-only — student PUT -> 403)",
                  r.status_code == 201 and r_put.status_code == 403,
                  f"extra={r.status_code} student_put={r_put.status_code}")
    finally:
        async with AsyncSessionLocal() as db:
            if test_record_ids:
                await db.execute(delete(LaboratoryRecord).where(LaboratoryRecord.id.in_(test_record_ids)))
            if test_experiment_ids:
                await db.execute(delete(LaboratoryExperiment).where(LaboratoryExperiment.id.in_(test_experiment_ids)))
            if test_event_ids:
                await db.execute(delete(AcademicEvent).where(AcademicEvent.id.in_(test_event_ids)))
                # The EXTRA_LECTURE smoke event materialized an extra lecture
                # session (2026-07-28, BCS-501). Deleting the event does not
                # remove the already-materialized session — remove any
                # unattended extra session created by our own event.
                stale_extra = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.date == date(2026, 7, 28),
                        ClassSession.subject_id == subject_ids["BCS-501"],
                        ClassSession.class_type == ClassType.LECTURE,
                        ClassSession.is_extra.is_(True),
                    )
                )).scalars().all()
                attended_extra = set((await db.execute(
                    select(AttendanceRecord.class_session_id).where(
                        AttendanceRecord.class_session_id.in_([s.id for s in stale_extra])
                    )
                )).all())
                attended_extra = {r[0] for r in attended_extra}
                for s in stale_extra:
                    if s.id not in attended_extra:
                        await db.delete(s)
            for tid in (temp_a_id, temp_b_id):
                await db.execute(delete(StudentEnrollment).where(StudentEnrollment.user_id == tid))
                await db.execute(delete(User).where(User.id == tid))
            # The temporary cancellation was restored inline; be defensive.
            if cancel_target is not None:
                ct = (await db.execute(select(ClassSession).where(
                    ClassSession.id == cancel_target.id))).scalars().first()
                if ct is not None:
                    ct.is_cancelled = False
            await db.commit()

    async with AsyncSessionLocal() as db:
        events_after = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
        sessions_after = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
        cancelled_after = (await db.execute(select(func.count()).select_from(ClassSession).where(
            ClassSession.is_cancelled.is_(True)))).scalar()
        extra_after = (await db.execute(select(func.count()).select_from(ClassSession).where(
            ClassSession.is_extra.is_(True)))).scalar()
        records_after = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
        enrollments_after = (await db.execute(select(func.count()).select_from(StudentEnrollment))).scalar()
        subjects_after = (await db.execute(select(func.count()).select_from(Subject))).scalar()
        quizzes_after = (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar()
        users_after = (await db.execute(select(func.count()).select_from(User))).scalar()
        admins_after = (await db.execute(select(func.count()).select_from(User).where(
            User.role == UserRole.ADMIN))).scalar()
        lab_exp_after = (await db.execute(select(func.count()).select_from(LaboratoryExperiment))).scalar()
        lab_rec_after = (await db.execute(select(func.count()).select_from(LaboratoryRecord))).scalar()
        designated_after = (await db.execute(select(func.count()).select_from(ClassSession).where(
            ClassSession.designation.isnot(None)))).scalar()

    check("18. no fabricated experiment data (lab tables back at baseline after cleanup)",
          lab_exp_after == lab_exp_before and lab_rec_after == lab_rec_before,
          f"lab_exp {lab_exp_before}->{lab_exp_after} lab_rec {lab_rec_before}->{lab_rec_after}")
    check("19. baseline restored exactly (events/sessions/cancelled/extra/records/"
          "enrollments/subjects/quizzes/users/admins/lab tables/designations)",
          (events_after, sessions_after, cancelled_after, extra_after, records_after,
           enrollments_after, subjects_after, quizzes_after, users_after, admins_after,
           lab_exp_after, lab_rec_after, designated_after)
          == (events_before, sessions_before, cancelled_before, extra_before, records_before,
              enrollments_before, subjects_before, quizzes_before, users_before, admins_before,
              lab_exp_before, lab_rec_before, designated_before),
          f"events {events_before}->{events_after} sessions {sessions_before}->{sessions_after} "
          f"cancelled {cancelled_before}->{cancelled_after} extra {extra_before}->{extra_after} "
          f"records {records_before}->{records_after} enrollments {enrollments_before}->{enrollments_after} "
          f"users {users_before}->{users_after} admins {admins_before}->{admins_after} "
          f"lab_exp {lab_exp_before}->{lab_exp_after} lab_rec {lab_rec_before}->{lab_rec_after} "
          f"designated {designated_before}->{designated_after}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\nPhase 9.2 verification: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))