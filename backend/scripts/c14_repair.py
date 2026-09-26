"""
Chunk 14 — elective-enrollment data repair (idempotent, choice-aware).

Canonical invariant: ALL non-elective subjects + selected Elective-I subject
+ selected Elective-II subject. The selected subject per slot is defined by
StudentElectiveChoice resolved through ElectiveResolver.resolve_subject
(fallback: the slot's anchor subject when no choice is recorded).

For the two affected users only, removes StudentEnrollment rows where:
  - subject.elective_slot IS NOT NULL, AND
  - the subject is NOT the student's selected subject for that slot
    (ElectiveResolver semantics).

Preserves: all non-elective enrollments, selected elective enrollments,
enrollment_type of legitimate rows, all attendance records, all other data.

Safety (Task 8): before deleting a candidate enrollment the script counts the
user's AttendanceRecords on that subject's sessions and enumerates FKs that
reference student_enrollments. Any dependency => STOP, no deletion, full report.

Modes:
  python scripts/c14_repair.py            # apply (idempotent)
  python scripts/c14_repair.py --dry-run  # report only
  python scripts/c14_repair.py --selftest # in-memory decision-matrix test
"""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.academic import StudentEnrollment, StudentElectiveChoice, Subject
from app.models.attendance import AttendanceRecord
from app.models.timetable import ClassSession
from app.models.enums import ElectiveSlot
from app.services.elective_resolver import ElectiveResolver
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

AFFECTED_ROLLS = ["2401220100027", "9999999999999"]
ALL_SLOTS = [ElectiveSlot.ELECTIVE_I, ElectiveSlot.ELECTIVE_II]


def deletion_decision(enrollments, subjects_by_id, choice_map, anchors):
    """Pure decision core (shared by apply and self-test).

    Returns (keep, delete) lists of (subject_code, slot, enrollment_type).
    """
    keep, delete = [], []
    for e in enrollments:
        s = subjects_by_id[e.subject_id]
        slot = s.elective_slot
        code = s.code
        etype = getattr(e.enrollment_type, "value", e.enrollment_type)
        if slot is None:
            keep.append((code, None, etype))
            continue
        resolved = ElectiveResolver.resolve_subject(choice_map, slot, anchors[slot])
        if resolved.id == e.subject_id:
            keep.append((code, getattr(slot, "value", slot), etype))
        else:
            delete.append((code, getattr(slot, "value", slot), etype))
    return keep, delete


async def dependency_report(db, user_id, subject_id) -> dict:
    """Task 8: every FK-ish dependency of one enrollment row."""
    rec_n = len((await db.execute(
        select(AttendanceRecord.id).where(
            AttendanceRecord.user_id == user_id,
            AttendanceRecord.class_session_id.in_(
                select(ClassSession.id).where(ClassSession.subject_id == subject_id)
            ),
        ))).scalars().all())
    return {"attendance_records": rec_n}


async def fks_referencing_enrollments(db) -> list:
    rows = (await db.execute(text(
        "SELECT tc.table_name AS referencing_table, kcu.column_name AS col "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "  ON kcu.constraint_name = tc.constraint_name "
        "JOIN information_schema.constraint_column_usage ccu "
        "  ON ccu.constraint_name = tc.constraint_name "
        "WHERE tc.constraint_type = 'FOREIGN KEY' "
        "  AND ccu.table_name = 'student_enrollments'"
    ))).all()
    return sorted({(r.referencing_table, r.col) for r in rows})


def selftest(subjects_by_code):
    """Decision-matrix test with fabricated rows (no DB writes)."""
    anchor_i = subjects_by_code["BCS-054"]
    anchor_ii = subjects_by_code["BCS-058"]

    class _C:
        def __init__(self, slot, subject):
            self.elective_slot = slot
            self.subject = subject

    class _E:
        def __init__(self, subject):
            self.subject_id = subject.id
            self.enrollment_type = "ELECTIVE"

    class _EC:
        def __init__(self, subject):
            self.subject_id = subject.id
            self.enrollment_type = "ELECTIVE"

    # Both affected users: choices = BCS-054 / BCS-058
    choice_map = {
        ElectiveSlot.ELECTIVE_I: _C(ElectiveSlot.ELECTIVE_I, anchor_i),
        ElectiveSlot.ELECTIVE_II: _C(ElectiveSlot.ELECTIVE_II, anchor_ii),
    }
    anchors = {ElectiveSlot.ELECTIVE_I: anchor_i, ElectiveSlot.ELECTIVE_II: anchor_ii}
    phantom = [subjects_by_code[c] for c in ("BCS-052", "BCS-053", "BCS-055", "BCS-056")]
    enrolled = [_E(subjects_by_code[c]) for c in
                ("BCS-054", "BCS-058", "BCS-052", "BCS-053", "BCS-055", "BCS-056")]
    keep, delete = deletion_decision([_EC(subjects_by_code[c]) for c in
                                      ("BCS-054", "BCS-058")], subjects_by_code, choice_map, anchors)
    assert [k[0] for k in keep] == ["BCS-054", "BCS-058"], keep
    assert delete == [], delete
    keep, delete = deletion_decision(
        [_EC(subjects_by_code[c]) for c in ("BCS-052", "BCS-053", "BCS-055", "BCS-056")],
        subjects_by_code, choice_map, anchors)
    assert keep == [], keep
    assert sorted(d[0] for d in delete) == ["BCS-052", "BCS-053", "BCS-055", "BCS-056"], delete
    print("selftest OK: selected electives kept; 052/053/055/056 flagged for deletion")


async def apply(dry_run: bool) -> int:
    async with AsyncSessionLocal() as db:
        subjects = (await db.execute(select(Subject))).scalars().all()
        subjects_by_id = {s.id: s for s in subjects}
        subjects_by_code = {s.code: s for s in subjects}
        anchors = {}
        for slot in ALL_SLOTS:
            anchor = next((s for s in subjects if s.elective_slot == slot), None)
            if anchor is None:
                print(f"FATAL: no anchor subject for {slot}")
                return 2
            anchors[slot] = anchor

        fks = await fks_referencing_enrollments(db)
        print(f"FKs referencing student_enrollments: {fks or 'none'}")

        total_deleted = 0
        for roll in AFFECTED_ROLLS:
            u = (await db.execute(select(User).where(User.roll_number == roll))).scalars().first()
            if u is None:
                print(f"FATAL: user {roll} not found")
                return 2
            choices = (await db.execute(
                select(StudentElectiveChoice)
                .options(selectinload(StudentElectiveChoice.subject))
                .where(StudentElectiveChoice.user_id == u.id)
            )).scalars().all()
            for c in choices:
                if not hasattr(c, "subject") or c.subject is None:
                    print("FATAL: choice rows must be loaded with their subject relationship")
                    return 2
            choice_map = {c.elective_slot: c for c in choices}
            enrollments = (await db.execute(select(StudentEnrollment).where(
                StudentEnrollment.user_id == u.id))).scalars().all()

            keep, delete = deletion_decision(enrollments, subjects_by_id, choice_map, anchors)
            print(f"\n=== {roll} ===")
            print(f"  choices: {[(getattr(c.elective_slot, 'value', c.elective_slot), subjects_by_id[c.subject_id].code) for c in choices]}")
            print(f"  keep ({len(keep)}): {[k[0] for k in keep]}")
            print(f"  delete candidates ({len(delete)}): {delete}")
            for code, slot, etype in delete:
                s = subjects_by_code[code]
                dep = await dependency_report(db, u.id, s.id)
                if dep["attendance_records"] > 0 or fks:
                    print(f"  STOP: enrollment {roll} -> {code} ({slot}, {etype}) has dependencies "
                          f"{dep} / referencing FKs {fks} — nothing deleted")
                    return 3
                if dry_run:
                    print(f"  [dry-run] would delete enrollment {roll} -> {code} ({slot}, {etype})")
                    continue
                row = (await db.execute(select(StudentEnrollment).where(
                    StudentEnrollment.user_id == u.id,
                    StudentEnrollment.subject_id == s.id))).scalars().first()
                if row is not None:
                    await db.delete(row)
                    total_deleted += 1
                    print(f"  deleted enrollment {roll} -> {code} ({slot}, {etype})")
        if not dry_run and total_deleted:
            await db.commit()
        print(f"\n{'[dry-run] ' if dry_run else ''}total enrollments deleted: {total_deleted}")
        return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        from app.db.base_class import Base  # noqa: F401  (ensure models imported)
        # Minimal subject stubs sufficient for the decision test:
        class _S:
            def __init__(self, code, slot):
                self.id = code
                self.code = code
                self.elective_slot = slot
        subs = {
            "BCS-054": _S("BCS-054", ElectiveSlot.ELECTIVE_I),
            "BCS-058": _S("BCS-058", ElectiveSlot.ELECTIVE_II),
            "BCS-052": _S("BCS-052", ElectiveSlot.ELECTIVE_I),
            "BCS-053": _S("BCS-053", ElectiveSlot.ELECTIVE_I),
            "BCS-055": _S("BCS-055", ElectiveSlot.ELECTIVE_II),
            "BCS-056": _S("BCS-056", ElectiveSlot.ELECTIVE_II),
        }
        selftest(subs)
        sys.exit(0)
    rc = asyncio.run(apply("--dry-run" in sys.argv))
    sys.exit(rc)
