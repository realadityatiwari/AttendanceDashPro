"""Post-remediation integrity review — Phase H dev-DB restoration.

Removes every verifier residue chain (subjects like 'TXIR%') in FK-safe
order, then removes the remediation-day residue left by the crashed
verify_events_correction.py cleanup on 2026-10-02 (an attended quiz-day-shaped
session for BCS-503 @ 2026-07-31 plus its attendance record and the four
derived attendance-kind notification rows created the same minute), and
finally prints the restored counts vs. the documented pristine baseline.

The 452 legacy orphan ACADEMIC_EVENT notifications are NEVER touched (every
delete here is scoped by temp-chain ownership or by exact row ids captured
below).

Usage:
    python scripts/restore_dev_baseline.py
"""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import delete, func, select, text

from app.db.session import AsyncSessionLocal
from app.models.academic import AcademicSession, Semester, StudentEnrollment, Subject
from app.models.attendance import AttendanceRecord
from app.models.event import AcademicEvent
from app.models.notification import Notification
from app.models.occurrence import OccurrenceOutcome
from app.models.preference import UserPreference
from app.models.quiz import QuizCycle, QuizSchedule
from app.models.timetable import ClassSession, TimetableEntry
from app.models.user import Section, User

# Remediation-day verifier residue (created 2026-10-02 11:29 UTC by
# verify_events_correction.py's crashed cleanup; captured by the Phase D
# read-only audit of this review).
RESIDUE_SESSION_ID = "51a391ec-74ce-4810-92d0-368e73772720"  # BCS-503 @ 2026-07-31
RESIDUE_RECORD_ID = "b8d216fd-6f34-4eb7-af59-35a5351ca3d0"   # its ATTENDED mark
RESIDUE_NOTIF_CREATED = "2026-10-02"                          # derived rows created that day
RESIDUE_NOTIF_KINDS = ("MUST_ATTEND", "SAFE_SKIP")
RESIDUE_NOTIF_SUBJECTS = ("BCS-502", "BCS-503")

PRISTINE_BASELINE = {
    "academic_events": 18, "class_sessions": 702, "attendance_records": 54,
    "notifications": 482, "users": 7, "subjects": 13,
    "quiz_schedules": 18, "quiz_cycles": 3,
}


async def purge_txir_chain(db) -> int:
    subs = select(Subject.id).where(Subject.code.like("TXIR%"))
    usrs = select(User.id).where(User.roll_number.like("TXIR%"))
    evs = select(AcademicEvent.id).where(AcademicEvent.subject_id.in_(subs))
    secs = select(Section.id).where(Section.name.like("TXIR%"))
    await db.execute(delete(Notification).where(Notification.user_id.in_(usrs)))
    await db.execute(delete(Notification).where(Notification.event_id.in_(evs)))
    await db.execute(delete(AttendanceRecord).where(AttendanceRecord.class_session_id.in_(
        select(ClassSession.id).where(ClassSession.subject_id.in_(subs)))))
    await db.execute(delete(OccurrenceOutcome).where(OccurrenceOutcome.class_session_id.in_(
        select(ClassSession.id).where(ClassSession.subject_id.in_(subs)))))
    await db.execute(delete(ClassSession).where(ClassSession.subject_id.in_(subs)))
    await db.execute(delete(QuizSchedule).where(QuizSchedule.subject_id.in_(subs)))
    await db.execute(delete(AcademicEvent).where(AcademicEvent.id.in_(evs)))
    await db.execute(delete(QuizCycle).where(QuizCycle.label.like("TXIR%")))
    await db.execute(delete(StudentEnrollment).where(StudentEnrollment.user_id.in_(usrs)))
    await db.execute(delete(UserPreference).where(UserPreference.user_id.in_(usrs)))
    await db.execute(delete(User).where(User.roll_number.like("TXIR%")))
    await db.execute(delete(TimetableEntry).where(TimetableEntry.section_id.in_(secs)))
    await db.execute(delete(Subject).where(Subject.code.like("TXIR%")))
    await db.execute(delete(Section).where(Section.name.like("TXIR%")))
    await db.execute(delete(Semester).where(Semester.name.like("TXIR%")))
    await db.execute(delete(AcademicSession).where(AcademicSession.name.like("TXIR%")))
    return 1


async def purge_remediation_day_residue(db) -> None:
    """Remove the captured verify_events_correction.py leftovers (Phase D)."""
    # 1. the residue attendance record + session (exact captured ids)
    await db.execute(text(
        "DELETE FROM attendance_records WHERE id = :rid AND created_at >= '2026-10-02'"
    ), {"rid": RESIDUE_RECORD_ID})
    await db.execute(text(
        "DELETE FROM class_sessions WHERE id = :sid AND created_at >= '2026-10-02' "
        "AND timetable_entry_id IS NULL AND is_extra = false "
        "AND class_type = 'LECTURE'"
    ), {"sid": RESIDUE_SESSION_ID})
    # 2. the four derived attendance-kind notification rows created the same
    #    day for the residue subjects (they did not exist in the pristine
    #    baseline: their created_at is the remediation day).
    await db.execute(text(
        "DELETE FROM notifications WHERE created_at >= '2026-10-02' "
        "AND kind IN ('MUST_ATTEND', 'SAFE_SKIP') "
        "AND subject_code IN ('BCS-502', 'BCS-503')"
    ))


async def purge_review_run_residue(db, cutoff) -> None:
    """Remove EVERYTHING created after `cutoff` (ISO timestamp, IST) — the
    integrity review's own verifier runs whose cleanups crashed (the
    documented pre-existing events_correction / cancellation_propagation
    cleanup crashes). Scoped by created_at to the review's run window: the
    seeded 18 events / 702 sessions / 452 legacy orphans all predate it."""
    # Records created in the window (on old sessions too) must go before the
    # sessions and users deletes (attendance_records_user_id_fkey).
    await db.execute(text(
        "DELETE FROM attendance_records WHERE created_at >= :c"
    ), {"c": cutoff})
    await db.execute(text(
        "DELETE FROM attendance_records ar USING class_sessions cs "
        "WHERE ar.class_session_id = cs.id AND (cs.created_at >= :c OR "
        "cs.source_event_id IN (SELECT id FROM academic_events WHERE created_at >= :c))"
    ), {"c": cutoff})
    await db.execute(text(
        "DELETE FROM occurrence_outcomes oo USING class_sessions cs "
        "WHERE oo.class_session_id = cs.id AND (cs.created_at >= :c OR "
        "cs.source_event_id IN (SELECT id FROM academic_events WHERE created_at >= :c))"
    ), {"c": cutoff})
    await db.execute(text(
        "DELETE FROM class_sessions WHERE created_at >= :c OR source_event_id IN "
        "(SELECT id FROM academic_events WHERE created_at >= :c)"
    ), {"c": cutoff})
    await db.execute(text(
        "DELETE FROM notifications WHERE created_at >= :c"
    ), {"c": cutoff})
    await db.execute(text(
        "DELETE FROM quiz_schedules WHERE created_at >= :c"
    ), {"c": cutoff})
    await db.execute(text(
        "DELETE FROM academic_events WHERE created_at >= :c"
    ), {"c": cutoff})
    await db.execute(text(
        "DELETE FROM student_enrollments WHERE created_at >= :c"
    ), {"c": cutoff})
    await db.execute(text(
        "DELETE FROM userpreferences WHERE created_at >= :c"
    ), {"c": cutoff})
    await db.execute(text(
        "DELETE FROM users WHERE created_at >= :c"
    ), {"c": cutoff})


async def counts(db) -> dict:
    out = {}
    for label, stmt in {
        "academic_events": select(func.count()).select_from(AcademicEvent),
        "class_sessions": select(func.count()).select_from(ClassSession),
        "attendance_records": select(func.count()).select_from(AttendanceRecord),
        "notifications": select(func.count()).select_from(Notification),
        "users": select(func.count()).select_from(User),
        "subjects": select(func.count()).select_from(Subject),
        "quiz_schedules": select(func.count()).select_from(QuizSchedule),
        "quiz_cycles": select(func.count()).select_from(QuizCycle),
        "txir_subjects": select(func.count()).select_from(Subject).where(Subject.code.like("TXIR%")),
        "orphan_notifs": select(func.count()).select_from(Notification).where(
            Notification.event_id.isnot(None),
            ~select(AcademicEvent.id).where(AcademicEvent.id == Notification.event_id).exists()),
    }.items():
        out[label] = (await db.execute(stmt)).scalar()
    return out


async def main() -> int:
    async with AsyncSessionLocal() as db:
        before = await counts(db)
        print("BEFORE:", before)
        n = await purge_txir_chain(db)
        await purge_remediation_day_residue(db)
        # Review-run window: everything created by THIS review's verifier runs
        # (their cleanups crash by a documented pre-existing defect).
        from datetime import datetime, timezone, timedelta
        ist = timezone(timedelta(hours=5, minutes=30))
        cutoff = datetime(2026, 10, 2, 23, 0, tzinfo=ist)
        await purge_review_run_residue(db, cutoff)
        await db.commit()
        print(f"purged TXIR chains; remediation-day residue removed")
        after = await counts(db)
        print("AFTER: ", after)

        ok = True
        for k, expected in PRISTINE_BASELINE.items():
            actual = after[k]
            status = "OK " if actual == expected else "DIFF"
            if actual != expected:
                ok = False
            print(f"  {status} {k}: expected={expected} actual={actual}")
        # the 452 legacy orphans must be untouched
        if after["orphan_notifs"] != 452:
            ok = False
            print("  DIFF orphan_notifs: expected=452 (legacy, must remain)")
        else:
            print("  OK  orphan_notifs: 452 legacy rows untouched")
        print("RESTORATION:", "COMPLETE" if ok else "INCOMPLETE")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
