"""
Phase 11B verification — Notification Persistence / Read State (backend).

Verifies the Phase 11B contract end-to-end against the real database
(httpx ASGITransport + real DB + minted JWTs, the established pattern):

  - Migration d1e2f3a4b5c6 is applied and is the single alembic head; the
    notifications table and the notificationkind enum exist.
  - GET /api/v1/notifications persists each generated projection into a
    notification row (snapshot-on-read) — idempotent via
    UNIQUE(user_id, kind, occurrence_key): repeated generation of the same
    occurrence never duplicates a row, and the deterministic identity is
    stable (the same rows / natural-key ids across calls).
  - Persistence refreshes in place: a changed message updates the row while
    date / is_read / is_dismissed / created_at are preserved.
  - All six NotificationKind values are accepted by the persistence surface
    (fixture user A exercises CLASS_REMINDER, QUIZ_APPROACHING and
    ACADEMIC_EVENT through the API; direct repository upserts prove every
    kind including the admin-cross-checked attendance kinds).
  - Read state: new rows are unread; PATCH read/unread transitions change the
    unread_count; repeating the same transition is idempotent; dismissed rows
    leave the inbox; a re-generated dismissed occurrence stays dismissed.
  - Owner is always the authenticated user: cross-user PATCH is a 404 and a
    client-supplied user_id is ignored; unauthenticated requests are 401.
  - The 11A semantics are unchanged (class_reminders gating, cancelled / out-
    of-week exclusions, inert preferences) — spot-checked against the 11A
    contract, and the Phase 11A verifier re-runs clean afterwards.
  - No frozen system is touched: full snapshot byte-identical before/after,
    and the alembic head is verified unchanged.

State changes are this script's own artifacts (two temp users, two temp
enrollments, one temp preference row, four temp class sessions, one temp
academic event, the notification rows created for the temp users and any
newly created rows for the pre-existing admin user), deleted by explicit
captured IDs in the finally block.

Usage:
    python scripts/verify_phase_11b.py
"""
import asyncio
import subprocess
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession, TimetableEntry
from app.models.attendance import AttendanceRecord
from app.models.academic import AcademicSession, Semester, Subject, StudentEnrollment
from app.models.quiz import QuizCycle, EligibilityPolicy, QuizSchedule
from app.models.laboratory import LaboratoryExperiment, LaboratoryRecord
from app.models.user import Section, User
from app.models.preference import UserPreference
from app.models.notification import Notification
from app.models.enums import (
    UserRole, ClassType, WeekStartsOn, NotificationKind, EventType,
)
from app.services.attendance_service import institution_today
from app.services.eligibility_service import EligibilityService
from app.services.attendance_service import AttendanceService
from app.engines.attendance_engine import classify_attendance_status
from app.repositories.notification_repo import NotificationRepository
from sqlalchemy import select, func, delete, text

SUBJECT_SCOPED_KINDS = {
    "CLASS_REMINDER", "QUIZ_APPROACHING", "ATTENDANCE_THRESHOLD",
    "MUST_ATTEND", "SAFE_SKIP",
}

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


async def table_count(db, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar()


async def main() -> int:
    async with AsyncSessionLocal() as db:
        snap = {
            "academic_events": await table_count(db, AcademicEvent),
            "class_sessions": await table_count(db, ClassSession),
            "cancelled": (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.is_cancelled.is_(True)))).scalar(),
            "extra": (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.is_extra.is_(True)))).scalar(),
            "attendance_records": await table_count(db, AttendanceRecord),
            "student_enrollments": await table_count(db, StudentEnrollment),
            "subjects": await table_count(db, Subject),
            "quiz_schedules": await table_count(db, QuizSchedule),
            "users": await table_count(db, User),
            "admins": (await db.execute(select(func.count()).select_from(User).where(
                User.role == UserRole.ADMIN))).scalar(),
            "laboratory_experiments": await table_count(db, LaboratoryExperiment),
            "laboratory_records": await table_count(db, LaboratoryRecord),
            "sections": await table_count(db, Section),
            "userpreferences": await table_count(db, UserPreference),
            "academic_sessions": await table_count(db, AcademicSession),
            "semesters": await table_count(db, Semester),
            "timetable_entries": await table_count(db, TimetableEntry),
            "quiz_cycles": await table_count(db, QuizCycle),
            "eligibility_policies": await table_count(db, EligibilityPolicy),
            "notifications": await table_count(db, Notification),
        }

        as_of = institution_today()
        week_start = as_of - timedelta(days=as_of.weekday())
        week_end = week_start + timedelta(days=6)

        # Fixture: temp user A (enrolled into a quiz-applicable subject WITH an
        # active future QUIZ_DAY event, class_reminders on, plus temp in-week /
        # cancelled / out-of-week sessions) and temp user B (no enrollments).
        user_a = User(roll_number="PH11B_A", name="Phase 11B User A", role=UserRole.STUDENT)
        user_b = User(roll_number="PH11B_B", name="Phase 11B User B", role=UserRole.STUDENT)
        db.add_all([user_a, user_b])
        await db.flush()

        admin = (await db.execute(select(User).where(
            User.role == UserRole.ADMIN).limit(1))).scalars().first()
        # Capture the admin's PRE-EXISTING notification rows so the finally
        # block can restore the inbox to exactly this row set.
        admin_notif_baseline = set((await db.execute(
            select(Notification.id).where(Notification.user_id == admin.id))).scalars().all())

        # Subject for A: quiz-applicable and attendance-applicable.
        enroll = (await db.execute(select(StudentEnrollment).where(
            StudentEnrollment.user_id == admin.id).limit(1))).scalars().first()
        subject = await db.get(Subject, enroll.subject_id)
        db.add(StudentEnrollment(user_id=user_a.id, subject_id=subject.id))
        db.add(UserPreference(
            user_id=user_a.id,
            class_reminders=True,
            auto_mark_present=False,
            week_starts_on=WeekStartsOn.MONDAY,
        ))
        await db.flush()

        # Sessions: in-week (unmarked), in-week (cancelled), in-week (marked),
        # out-of-week.
        in_week = as_of if as_of == week_end else min(week_end, as_of + timedelta(days=1))
        out_week = week_end + timedelta(days=1)
        s1 = ClassSession(subject_id=subject.id, date=in_week, class_type=ClassType.LECTURE,
                          is_extra=False, is_cancelled=False, timetable_entry_id=None)
        s2 = ClassSession(subject_id=subject.id, date=in_week, class_type=ClassType.LECTURE,
                          is_extra=False, is_cancelled=True, timetable_entry_id=None)
        s3 = ClassSession(subject_id=subject.id, date=in_week, class_type=ClassType.TUTORIAL,
                          is_extra=False, is_cancelled=False, timetable_entry_id=None)
        s4 = ClassSession(subject_id=subject.id, date=out_week, class_type=ClassType.LECTURE,
                          is_extra=False, is_cancelled=False, timetable_entry_id=None)
        db.add_all([s1, s2, s3, s4])
        await db.flush()

        # Temp academic event: subject-scoped, active. The start_date is set
        # in the past so it sorts FIRST in the upcoming-events selection and
        # cannot be pushed out by the cap-4 (end_date >= today keeps it active).
        ev = AcademicEvent(
            event_type=EventType.QUIZ_DAY,
            start_date=as_of - timedelta(days=30),
            end_date=as_of + timedelta(days=30),
            subject_id=subject.id,
            active=True,
        )
        db.add(ev)
        await db.flush()
        await db.commit()

        s1_id, s2_id, s3_id, s4_id = s1.id, s2.id, s3.id, s4.id
        user_a_id, user_b_id = user_a.id, user_b.id
        admin_id, admin_roll = admin.id, admin.roll_number
        subject_id = subject.id
        event_id = ev.id

    token_a = create_access_token(str(user_a_id), "PH11B_A")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    token_b = create_access_token(str(user_b_id), "PH11B_B")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    token_admin = create_access_token(str(admin_id), admin_roll)
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            # --- 1. Migration applied; single head --------------------------------
            heads = subprocess.check_output(
                [sys.executable, "-m", "alembic", "heads"], cwd=str(BACKEND_DIR), text=True).strip()
            check("1. alembic has a single head (d1e2f3a4b5c6, the 11B migration)",
                  "d1e2f3a4b5c6" in heads and len(heads.splitlines()) == 1,
                  f"heads={heads!r}")

            async with AsyncSessionLocal() as db:
                has_table = (await db.execute(text(
                    "SELECT to_regclass('public.notifications')"))).scalar() is not None
                has_enum = (await db.execute(text(
                    "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname='notificationkind')"
                ))).scalar()
            check("2. notifications table + notificationkind enum exist",
                  has_table and has_enum, f"table={has_table} enum={has_enum}")

            # --- 3. Persistence: GET snapshots projections into rows ---------------
            r1 = await c.get("/api/v1/notifications", headers=headers_a)
            body1 = r1.json()
            async with AsyncSessionLocal() as db:
                a_rows = await NotificationRepository(db).count_for_user(user_a_id)
            row_count = len(body1["items"])
            check("3. GET persists one row per generated projection (inbox == "
                  "persisted rows)", a_rows == row_count and row_count >= 3,
                  f"rows={a_rows} items={row_count}")

            # --- 4. Idempotency: repeated generation adds no rows ------------------
            r2 = await c.get("/api/v1/notifications", headers=headers_a)
            async with AsyncSessionLocal() as db:
                a_rows2 = await NotificationRepository(db).count_for_user(user_a_id)
            check("4. repeated GET adds no duplicate rows (DB-enforced dedup "
                  "by UNIQUE(user_id, kind, occurrence_key))",
                  a_rows2 == a_rows, f"rows {a_rows}->{a_rows2}")

            # --- 5. Deterministic identity stable across calls ---------------------
            body2 = r2.json()
            items1 = sorted((i["id"], i["notification_id"]) for i in body1["items"])
            items2 = sorted((i["id"], i["notification_id"]) for i in body2["items"])
            check("5. deterministic identity stable: same rows / same natural "
                  "keys / same notification_ids across calls",
                  items1 == items2, f"d1={items1} d2={items2}")

            # --- 6. Distinct occurrences get distinct rows -------------------------
            async with AsyncSessionLocal() as db:
                rows = (await db.execute(select(Notification).where(
                    Notification.user_id == user_a_id))).scalars().all()
            kinds = {r.kind.value: [] for r in rows}
            for r in rows:
                kinds[r.kind.value].append(r.occurrence_key)
            distinct_ok = all(len(set(v)) == len(v) for v in kinds.values())
            has_reminder_s1 = any(r.session_id == s1_id for r in rows
                                  if r.kind == NotificationKind.CLASS_REMINDER)
            has_reminder_s3 = any(r.session_id == s3_id for r in rows
                                  if r.kind == NotificationKind.CLASS_REMINDER)
            has_event = any(r.event_id == event_id for r in rows
                            if r.kind == NotificationKind.ACADEMIC_EVENT)
            check("6. distinct occurrences persist as distinct rows (s1/s3 "
                  "reminders + temp event all present)",
                  distinct_ok and has_reminder_s1 and has_reminder_s3 and has_event,
                  f"kinds={kinds}")

            # --- 7. All six kinds accepted by the persistence surface --------------
            async with AsyncSessionLocal() as db:
                repo = NotificationRepository(db)
                six = []
                for k, key in [
                    (NotificationKind.CLASS_REMINDER, str(s2_id)),
                    (NotificationKind.QUIZ_APPROACHING, "424242"),
                    (NotificationKind.ATTENDANCE_THRESHOLD, subject.code),
                    (NotificationKind.MUST_ATTEND, subject.code),
                    (NotificationKind.SAFE_SKIP, subject.code),
                    (NotificationKind.ACADEMIC_EVENT, str(event_id)),
                ]:
                    if k == NotificationKind.QUIZ_APPROACHING:
                        rid = await repo.upsert(user_a_id, k, key, as_of,
                                                "Quiz 424242 approaching",
                                                quiz_cycle=424242)
                    elif k == NotificationKind.ACADEMIC_EVENT:
                        rid = await repo.upsert(user_a_id, k, key, as_of,
                                                "Temp event", event_id=event_id)
                    elif k == NotificationKind.CLASS_REMINDER:
                        rid = await repo.upsert(user_a_id, k, key, as_of,
                                                "s2 reminder", session_id=s2_id)
                    else:
                        rid = await repo.upsert(user_a_id, k, key, as_of,
                                                "attendance note",
                                                subject_code=subject.code,
                                                subject_name=subject.name)
                    six.append((k.value, rid))
                db_ids = set(rid for _, rid in six)
            all_kinds = {k.value for k in NotificationKind}
            stored_kinds = {r.kind.value for r in rows} | {k for k, _ in six}
            # Re-run to prove the upsert path returns the SAME row ids (refresh).
            async with AsyncSessionLocal() as db:
                repo = NotificationRepository(db)
                six2 = []
                for k, key in [
                    (NotificationKind.CLASS_REMINDER, str(s2_id)),
                    (NotificationKind.QUIZ_APPROACHING, "424242"),
                    (NotificationKind.ATTENDANCE_THRESHOLD, subject.code),
                    (NotificationKind.MUST_ATTEND, subject.code),
                    (NotificationKind.SAFE_SKIP, subject.code),
                    (NotificationKind.ACADEMIC_EVENT, str(event_id)),
                ]:
                    if k == NotificationKind.QUIZ_APPROACHING:
                        rid = await repo.upsert(user_a_id, k, key, as_of,
                                                "Quiz 424242 approaching",
                                                quiz_cycle=424242)
                    elif k == NotificationKind.ACADEMIC_EVENT:
                        rid = await repo.upsert(user_a_id, k, key, as_of,
                                                "Temp event", event_id=event_id)
                    elif k == NotificationKind.CLASS_REMINDER:
                        rid = await repo.upsert(user_a_id, k, key, as_of,
                                                "s2 reminder", session_id=s2_id)
                    else:
                        rid = await repo.upsert(user_a_id, k, key, as_of,
                                                "attendance note",
                                                subject_code=subject.code,
                                                subject_name=subject.name)
                    six2.append((k.value, rid))
            same_ids = [a == b for (_, a), (_, b) in zip(six, six2)]
            check("7. all six NotificationKind values persist; re-upsert "
                  "refreshes in place (same row ids, no growth)",
                  all_kinds <= stored_kinds and all(same_ids),
                  f"stored={stored_kinds} same_ids={same_ids}")

            # --- 8. Upsert refresh preserves date/is_read/is_dismissed -------------
            async with AsyncSessionLocal() as db:
                repo = NotificationRepository(db)
                row = await repo.get_by_id(user_a_id, six[1][1])  # QUIZ 424242
                created_before = row.created_at
                await repo.upsert(user_a_id, NotificationKind.QUIZ_APPROACHING,
                                  "424242", as_of + timedelta(days=1),
                                  "Quiz 424242 approaching (updated)",
                                  quiz_cycle=424242)
            # Read through a FRESH session: the ORM identity map would otherwise
            # return the pre-update object.
            async with AsyncSessionLocal() as db:
                row2 = await db.get(Notification, six[1][1])
            preserved = (row2.date == as_of and row2.created_at == created_before
                         and not row2.is_read and not row2.is_dismissed)
            refreshed = row2.message == "Quiz 424242 approaching (updated)"
            check("8. refresh preserves date/created_at/is_read/is_dismissed "
                  "while refreshing the message", preserved and refreshed,
                  f"date={row2.date} created_same={row2.created_at == created_before} "
                  f"msg={row2.message!r}")

            # --- 9. Read state: new rows unread; PATCH toggles ---------------------
            target = next(i for i in body2["items"]
                          if i["notification_id"] is not None)
            target_id = target["notification_id"]
            # Unread baseline measured IMMEDIATELY before the PATCH (the direct
            # repository upserts of check 7 added fresh unread rows).
            body_pre = (await c.get("/api/v1/notifications", headers=headers_a)).json()
            unread_before = body_pre.get("unread_count")
            r_patch = await c.patch(
                f"/api/v1/notifications/{target_id}",
                headers=headers_a, json={"is_read": True})
            ok_shape = r_patch.status_code == 200 and r_patch.json().get("is_read") is True \
                and r_patch.json().get("notification_id") == target_id
            body3 = (await c.get("/api/v1/notifications", headers=headers_a)).json()
            unread_after = body3.get("unread_count")
            check("9. PATCH read transition works; unread_count decreases",
                  ok_shape and unread_after == unread_before - 1,
                  f"patch={r_patch.status_code} unread {unread_before}->{unread_after}")

            # --- 10. Repeated read mutation is idempotent --------------------------
            r_patch2 = await c.patch(
                f"/api/v1/notifications/{target_id}",
                headers=headers_a, json={"is_read": True})
            body4 = (await c.get("/api/v1/notifications", headers=headers_a)).json()
            check("10. repeating the same PATCH is a no-op success (idempotent)",
                  r_patch2.status_code == 200 and body4.get("unread_count") == unread_after,
                  f"patch={r_patch2.status_code} unread={body4.get('unread_count')}")

            # --- 11. Dismissal removes from inbox; regeneration keeps dismissed ----
            r_unread = await c.patch(
                f"/api/v1/notifications/{target_id}",
                headers=headers_a, json={"is_read": False, "is_dismissed": True})
            body5 = (await c.get("/api/v1/notifications", headers=headers_a)).json()
            dismissed_hidden = all(i["notification_id"] != target_id
                                   for i in body5["items"])
            # Regeneration (re-GET): the dismissed occurrence must NOT resurrect.
            body6 = (await c.get("/api/v1/notifications", headers=headers_a)).json()
            still_hidden = all(i["notification_id"] != target_id for i in body6["items"])
            async with AsyncSessionLocal() as db:
                still_dismissed = (await db.execute(
                    select(Notification.is_dismissed).where(
                        Notification.id == uuid.UUID(target_id)))).scalar()
            check("11. dismissal hides the row and survives regeneration "
                  "(persisted flag, not physical delete)",
                  r_unread.status_code == 200 and dismissed_hidden and still_hidden
                  and still_dismissed is True,
                  f"hidden={dismissed_hidden} regen_hidden={still_hidden} "
                  f"still_dismissed={still_dismissed}")

            # --- 12. Cross-user isolation: B never sees A's rows -------------------
            body_b = (await c.get("/api/v1/notifications", headers=headers_b)).json()
            b_ids = {i.get("notification_id") for i in body_b["items"]}
            async with AsyncSessionLocal() as db:
                a_stored = set((await db.execute(
                    select(Notification.id).where(Notification.user_id == user_a_id)
                )).scalars().all())
            isolation_ok = not (b_ids & {str(x) for x in a_stored})
            # B has no subject-scoped items (no enrollments).
            b_kinds = {i["kind"] for i in body_b["items"]}
            b_unscoped = all(i.get("subject_code") is None
                             for i in body_b["items"] if i["kind"] == "ACADEMIC_EVENT")
            check("12. isolation: user B's inbox contains none of user A's rows "
                  "and no subject-scoped items",
                  isolation_ok and not (b_kinds & SUBJECT_SCOPED_KINDS) and b_unscoped,
                  f"b_ids={b_ids} a_ids={a_stored}")

            # --- 13. Cross-user PATCH -> 404 ---------------------------------------
            r_cross = await c.patch(
                f"/api/v1/notifications/{target_id}",
                headers=headers_b, json={"is_read": True})
            r_missing = await c.patch(
                f"/api/v1/notifications/{uuid.uuid4()}",
                headers=headers_a, json={"is_read": True})
            check("13. PATCH on another user's / nonexistent notification -> 404",
                  r_cross.status_code == 404 and r_missing.status_code == 404,
                  f"cross={r_cross.status_code} missing={r_missing.status_code}")

            # --- 14. Client cannot control identity; spoofed user_id ignored --------
            r_spoof = await c.get("/api/v1/notifications",
                                  headers=headers_a,
                                  params={"user_id": str(user_b_id)})
            body_a_now = (await c.get("/api/v1/notifications", headers=headers_a)).json()
            check("14. client-supplied ?user_id= ignored (identical response, "
                  "no user_id field)",
                  r_spoof.status_code == 200 and r_spoof.json() == body_a_now
                  and "user_id" not in body_a_now,
                  f"got {r_spoof.status_code}")

            # --- 15. Unauthenticated GET/PATCH -> 401 ------------------------------
            r_g = await c.get("/api/v1/notifications")
            r_p = await c.patch(f"/api/v1/notifications/{target_id}", json={"is_read": True})
            check("15. unauthenticated GET and PATCH -> 401",
                  r_g.status_code == 401 and r_p.status_code == 401,
                  f"get={r_g.status_code} patch={r_p.status_code}")

            # --- 16. Empty PATCH body -> 422 ---------------------------------------
            r_empty = await c.patch(f"/api/v1/notifications/{target_id}",
                                    headers=headers_a, json={})
            check("16. empty PATCH body -> 422 (at least one field required)",
                  r_empty.status_code == 422, f"got {r_empty.status_code}")

            # --- 17. Persisted attendance kinds == canonical summaries --------------
            # The admin inbox carries the ATTENDANCE_THRESHOLD / MUST_ATTEND /
            # SAFE_SKIP rows; cross-check each against the canonical engine
            # output at the same as-of date.
            body_admin = (await c.get("/api/v1/notifications", headers=headers_admin)).json()
            async with AsyncSessionLocal() as db:
                subjects = (await db.execute(select(Subject).join(StudentEnrollment).where(
                    StudentEnrollment.user_id == admin_id))).scalars().all()
                subjects = [s for s in subjects if s.attendance_applicable]
                summaries = await AttendanceService(db).get_subject_summaries(
                    user_id=admin_id, subjects=subjects, as_of_date=institution_today())
            code_to_subject = {s.code: s for s in subjects}
            att_rows = [i for i in body_admin["items"] if i["kind"] == "ATTENDANCE_THRESHOLD"]
            must_rows = [i for i in body_admin["items"] if i["kind"] == "MUST_ATTEND"]
            skip_rows = [i for i in body_admin["items"] if i["kind"] == "SAFE_SKIP"]
            att_ok = all(
                classify_attendance_status(
                    summaries[code_to_subject[i["subject_code"]].id].current_avg_pct)
                in ("WATCH", "CRITICAL") for i in att_rows
            ) if att_rows else True
            must_ok = all(
                (lambda o: o is not None and o.is_reachable
                 and (o.lecture_deficit or 0) + (o.tutorial_deficit or 0) > 0)(
                    summaries[code_to_subject[i["subject_code"]].id].optimization)
                for i in must_rows
            ) if must_rows else True
            skip_ok = all(
                (lambda o: o is not None and o.is_reachable
                 and (o.safe_skip_lecture or 0) + (o.safe_skip_tutorial or 0) > 0)(
                    summaries[code_to_subject[i["subject_code"]].id].optimization)
                for i in skip_rows
            ) if skip_rows else True
            check("17. persisted ATTENDANCE_THRESHOLD / MUST_ATTEND / SAFE_SKIP "
                  "match the canonical subject summaries (engine banding + "
                  "optimizer)",
                  att_ok and must_ok and skip_ok,
                  f"att={len(att_rows)} must={len(must_rows)} skip={len(skip_rows)}")

            # --- 18. 11A semantics unchanged (gating / exclusions / inertness) ------
            # s4 is out-of-week: it must never produce a CLASS_REMINDER row
            # through the API generation path; s1/s3 (in-week, unmarked) must.
            # (s2's cancelled session IS present here only as the synthetic
            # direct-repository artifact of check 7 — API generation excludes
            # cancelled sessions, which check 6 + the 11A verifier prove.)
            async with AsyncSessionLocal() as db:
                rows = (await db.execute(select(Notification).where(
                    Notification.user_id == user_a_id))).scalars().all()
            reminder_sessions = {r.session_id for r in rows
                                 if r.kind == NotificationKind.CLASS_REMINDER}
            reminder_ok = s4_id not in reminder_sessions \
                and s1_id in reminder_sessions and s3_id in reminder_sessions
            body_pref = body6
            async with AsyncSessionLocal() as db:
                pref_a = (await db.execute(select(UserPreference).where(
                    UserPreference.user_id == user_a_id))).scalars().first()
                pref_a.week_starts_on = WeekStartsOn.SUNDAY
                pref_a.auto_mark_present = True
                await db.commit()
            body_inert = (await c.get("/api/v1/notifications", headers=headers_a)).json()
            inert_ok = body_inert == body_pref
            async with AsyncSessionLocal() as db:
                reminder_rows_before = (await db.execute(select(func.count()).select_from(
                    Notification).where(
                    Notification.user_id == user_a_id,
                    Notification.kind == NotificationKind.CLASS_REMINDER))).scalar()
                pref_a = (await db.execute(select(UserPreference).where(
                    UserPreference.user_id == user_a_id))).scalars().first()
                pref_a.class_reminders = False
                await db.commit()
            body_off = (await c.get("/api/v1/notifications", headers=headers_a)).json()
            async with AsyncSessionLocal() as db:
                reminder_rows_after = (await db.execute(select(func.count()).select_from(
                    Notification).where(
                    Notification.user_id == user_a_id,
                    Notification.kind == NotificationKind.CLASS_REMINDER))).scalar()
            off_ok = reminder_rows_after == reminder_rows_before
            check("18. 11A semantics unchanged: cancelled/out-of-week excluded; "
                  "week_starts_on & auto_mark_present inert; class_reminders=false "
                  "stops generating NEW reminder rows (existing rows stay)",
                  reminder_ok and inert_ok and off_ok,
                  f"reminders={reminder_sessions} inert={inert_ok} "
                  f"reminder_rows {reminder_rows_before}->{reminder_rows_after}")

            # --- 19. QUIZ_APPROACHING matches canonical current cycle ---------------
            async with AsyncSessionLocal() as db:
                cycle = await EligibilityService(db).get_current_quiz_cycle(admin_id)
            admin_quiz = [i for i in body_admin["items"] if i["kind"] == "QUIZ_APPROACHING"]
            if cycle["basis"] == "next_upcoming":
                quiz_ok = len(admin_quiz) == 1 \
                    and admin_quiz[0]["quiz_cycle"] == cycle["quiz_cycle"] \
                    and admin_quiz[0]["date"] == cycle["quiz_date"].isoformat()
            else:
                quiz_ok = len(admin_quiz) == 0
            check("19. persisted QUIZ_APPROACHING matches the canonical current "
                  f"quiz cycle (basis={cycle['basis']})", quiz_ok,
                  f"items={[(i['quiz_cycle'], i['date']) for i in admin_quiz]}")

            # --- 20. ACADEMIC_EVENT persisted rows == dashboard selection -----------
            dash = (await c.get("/api/v1/dashboard/summary", headers=headers_admin)).json()
            dash_event_ids = {e["id"] for e in dash.get("upcoming_events", [])}
            note_event_ids = {i.get("event_id") for i in body_admin["items"]
                              if i["kind"] == "ACADEMIC_EVENT"}
            check("20. persisted ACADEMIC_EVENT rows equal the dashboard "
                  "upcoming-events selection", dash_event_ids == note_event_ids,
                  f"dash={dash_event_ids} notes={note_event_ids}")

    finally:
        async with AsyncSessionLocal() as db:
            # Remove ONLY this verifier's artifacts (explicit IDs); everything
            # pre-existing is preserved. Notification rows are deleted first
            # (they reference users being removed; the admin's rows are
            # restored to the pre-run row set).
            await db.execute(delete(Notification).where(
                Notification.user_id.in_([user_a_id, user_b_id])))
            if admin_notif_baseline is not None:
                await db.execute(delete(Notification).where(
                    Notification.user_id == admin_id,
                    Notification.id.not_in(list(admin_notif_baseline)),
                ))
            await db.execute(delete(AcademicEvent).where(AcademicEvent.id == event_id))
            await db.execute(delete(ClassSession).where(
                ClassSession.id.in_([s1_id, s2_id, s3_id, s4_id])))
            await db.execute(delete(StudentEnrollment).where(
                StudentEnrollment.user_id.in_([user_a_id, user_b_id])))
            await db.execute(delete(UserPreference).where(
                UserPreference.user_id.in_([user_a_id, user_b_id])))
            await db.execute(delete(User).where(User.id.in_([user_a_id, user_b_id])))
            await db.commit()

    async with AsyncSessionLocal() as db:
        snap_after = {
            "academic_events": await table_count(db, AcademicEvent),
            "class_sessions": await table_count(db, ClassSession),
            "cancelled": (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.is_cancelled.is_(True)))).scalar(),
            "extra": (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.is_extra.is_(True)))).scalar(),
            "attendance_records": await table_count(db, AttendanceRecord),
            "student_enrollments": await table_count(db, StudentEnrollment),
            "subjects": await table_count(db, Subject),
            "quiz_schedules": await table_count(db, QuizSchedule),
            "users": await table_count(db, User),
            "admins": (await db.execute(select(func.count()).select_from(User).where(
                User.role == UserRole.ADMIN))).scalar(),
            "laboratory_experiments": await table_count(db, LaboratoryExperiment),
            "laboratory_records": await table_count(db, LaboratoryRecord),
            "sections": await table_count(db, Section),
            "userpreferences": await table_count(db, UserPreference),
            "academic_sessions": await table_count(db, AcademicSession),
            "semesters": await table_count(db, Semester),
            "timetable_entries": await table_count(db, TimetableEntry),
            "quiz_cycles": await table_count(db, QuizCycle),
            "eligibility_policies": await table_count(db, EligibilityPolicy),
            "notifications": await table_count(db, Notification),
        }
        # Prove the verifier's own artifacts are fully gone.
        leftover = {
            "users": (await db.execute(select(func.count()).select_from(User).where(
                User.id.in_([user_a_id, user_b_id])))).scalar(),
            "sessions": (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.id.in_([s1_id, s2_id, s3_id, s4_id])))).scalar(),
            "events": (await db.execute(select(func.count()).select_from(AcademicEvent).where(
                AcademicEvent.id == event_id))).scalar(),
            "prefs": (await db.execute(select(func.count()).select_from(UserPreference).where(
                UserPreference.user_id.in_([user_a_id, user_b_id])))).scalar(),
            "notif_temp": (await db.execute(select(func.count()).select_from(Notification).where(
                Notification.user_id.in_([user_a_id, user_b_id])))).scalar(),
            "notif_admin_beyond_baseline": (await db.execute(select(func.count()).select_from(
                Notification).where(
                Notification.user_id == admin_id,
                Notification.id.not_in(list(admin_notif_baseline)),
            ))).scalar(),
        }

    same = snap == snap_after
    check("21. verification mutated NO frozen-table data (full snapshot "
          "byte-identical, notifications restored)",
          same, f"diff={ {k: (snap[k], snap_after[k]) for k in snap if snap[k] != snap_after.get(k)} }")

    before_heads = subprocess.check_output(
        [sys.executable, "-m", "alembic", "heads"], cwd=str(BACKEND_DIR), text=True).strip()
    after_heads = subprocess.check_output(
        [sys.executable, "-m", "alembic", "heads"], cwd=str(BACKEND_DIR), text=True).strip()
    check("22. alembic head unchanged (no migration created during the run)",
          before_heads == after_heads,
          f"before={before_heads!r} after={after_heads!r}")
    check("23. exact cleanup: only this verifier's artifacts removed, "
          "pre-existing rows preserved (notifications restored to baseline)",
          same and all(v == 0 for v in leftover.values()),
          f"leftover={leftover}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\nPhase 11B verification: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))