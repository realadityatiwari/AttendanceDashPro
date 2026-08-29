"""
Phase 22.1 verification — Timetable Data-Scope Correction.

Static + read-only checks against the dev database:
  1. timetable_entries has section_id column (schema check).
  2. All timetable rows have a non-null section_id referencing an existing section.
  3. Timetable row count matches the documented baseline (28).
  4. Repository query scopes by section_id (owner section returns only its own
     entries; a throwaway section's entries are excluded — rolled-back txn).
  5. API response shape is unchanged (GET /api/v1/timetable via httpx
     ASGITransport returns items with the established fields).
  6. Session materialization joins remain compatible (ClassSession ↔
     TimetableEntry join still produces correct results).
"""
import asyncio
import datetime
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx
from httpx import ASGITransport
from sqlalchemy import select, func, text

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.timetable import TimetableEntry, ClassSession
from app.models.user import Section, User
from app.models.enums import ClassType
from app.models.academic import Semester, Subject
from app.repositories.timetable_repo import TimetableRepository

results = []


def check(ok: bool, name: str, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


async def table_count(db, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar()


async def main() -> int:
    print("=" * 60)
    print("Phase 22.1 — Timetable Data-Scope Correction")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # ── 1. Schema check: timetable_entries has section_id column ──
        print("\n=== 1. Schema: section_id column exists ===")
        cols = await db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'timetable_entries' AND column_name = 'section_id'"
            )
        )
        section_id_exists = cols.scalar() is not None
        check(section_id_exists, "section_id column exists on timetable_entries")

        if not section_id_exists:
            print("\n  SKIP: section_id column not found. Run the migration first.")
            print("\n=== Summary ===")
            for name, ok in results:
                print(f"  {'PASS' if ok else 'FAIL'}  {name}")
            return 0 if all(ok for _, ok in results) else 1

        # ── 2. All timetable rows have valid section ──
        print("\n=== 2. All timetable rows have valid section ===")
        null_count = (
            await db.execute(
                text("SELECT COUNT(*) FROM timetable_entries WHERE section_id IS NULL")
            )
        ).scalar()
        check(null_count == 0, f"zero NULL section_id rows (found {null_count})")

        missing_ref = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM timetable_entries te "
                    "LEFT JOIN sections s ON s.id = te.section_id "
                    "WHERE s.id IS NULL"
                )
            )
        ).scalar()
        check(missing_ref == 0, f"zero orphan section_id references (found {missing_ref})")

        # ── 3. Timetable row count baseline ──
        print("\n=== 3. Timetable row count baseline ===")
        tt_count = await table_count(db, TimetableEntry)
        expected = 28
        check(tt_count == expected, f"timetable_entries count = {tt_count} (expected {expected})")

        # ── 4. Repository query scoping ──
        print("\n=== 4. Repository query scopes by section ===")
        admin = (
            await db.execute(
                select(User).where(User.roll_number == "2401220100027")
            )
        ).scalars().first()
        check(admin is not None, "admin user found")

        owner_section_id = admin.section_id if admin else None
        check(owner_section_id is not None, "admin user has section_id")

        repo = TimetableRepository(db)
        if owner_section_id is not None:
            owner_entries = await repo.get_weekly_entries_for_section(owner_section_id)
            check(
                len(owner_entries) == tt_count,
                f"owner section returns exactly {len(owner_entries)}/{tt_count} entries "
                "(single-section production baseline)",
            )
        else:
            check(False, "cannot run scoping check without owner section")

        # ── 5. Throwaway section isolation (rolled-back transaction) ──
        print("\n=== 5. Second-section isolation (rolled-back) ===")
        semester = (
            await db.execute(select(Semester).limit(1))
        ).scalars().first()
        check(semester is not None, "semester found for temp section")

        first_subject = (
            await db.execute(select(Subject).limit(1))
        ).scalars().first()
        check(first_subject is not None, "subject found for temp timetable entry")

        # Copy start/end times from an existing timetable entry of that subject
        # (avoids lazy-loading inside the session) or fall back to a default.
        sample_entry = None
        if first_subject is not None:
            sample_entry = (
                await db.execute(
                    select(TimetableEntry)
                    .where(TimetableEntry.subject_id == first_subject.id)
                    .limit(1)
                )
            ).scalars().first()

        savepoint = await db.begin_nested()
        try:
            temp_section = Section(
                name=f"TEMP_SECTION_{uuid.uuid4().hex[:8]}",
                semester_id=semester.id,
                program="TEMP",
            )
            db.add(temp_section)
            await db.flush()

            temp_entry = TimetableEntry(
                subject_id=first_subject.id,
                day_of_week=0,
                start_time=sample_entry.start_time if sample_entry else datetime.time(9, 0),
                end_time=sample_entry.end_time if sample_entry else datetime.time(10, 0),
                class_type=ClassType.LECTURE,
                section_id=temp_section.id,
            )
            db.add(temp_entry)
            await db.flush()

            # Isolation: owner section query must NOT return the temp entry.
            owner_entries_after = await repo.get_weekly_entries_for_section(owner_section_id)
            leaked = [e.id for e in owner_entries_after if e.id == temp_entry.id]
            check(
                len(leaked) == 0,
                f"owner section query does NOT return temp section entries (leaked: {len(leaked)})",
            )

            # Temp section query returns exactly its own entries.
            temp_entries = await repo.get_weekly_entries_for_section(temp_section.id)
            check(
                temp_entry.id in [e.id for e in temp_entries],
                "temp section query returns its own entry",
            )

            # The temp entry carries a section_id (NOT NULL satisfiable).
            check(
                temp_entry.section_id == temp_section.id,
                "temp timetable entry has section_id set",
            )
        finally:
            await savepoint.rollback()

        tt_count_after_rollback = await table_count(db, TimetableEntry)
        check(
            tt_count_after_rollback == tt_count,
            f"timetable count restored to {tt_count} after rollback",
        )

        # ── 6. API response shape unchanged ──
        print("\n=== 6. API response shape unchanged ===")
        token = create_access_token(
            subject=str(admin.id),
            roll_number="2401220100027",
        )
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/timetable",
                headers={"Authorization": f"Bearer {token}"},
            )
        check(resp.status_code == 200, f"GET /api/v1/timetable = 200 (got {resp.status_code})")

        if resp.status_code == 200:
            items = resp.json()
            if isinstance(items, list) and len(items) > 0:
                first = items[0]
                expected_fields = {"id", "day_of_week", "class_type", "subject", "elective_slot"}
                actual_fields = set(first.keys())
                check(
                    actual_fields == expected_fields,
                    f"response fields match: {actual_fields}",
                )
                check(
                    "section_id" not in actual_fields,
                    "section_id NOT in API response (internal data not leaked)",
                )
            else:
                check(False, "timetable returned non-list or empty list")

        # ── 7. Session materialization join compatibility ──
        print("\n=== 7. Session materialization join compatibility ===")
        session_rows = (
            await db.execute(
                select(ClassSession)
                .where(ClassSession.timetable_entry_id.isnot(None))
                .limit(3)
            )
        ).scalars().all()
        check(
            len(session_rows) > 0,
            f"class sessions with timetable links exist ({len(session_rows)} found)",
        )

        if session_rows:
            first_session = session_rows[0]
            tt = first_session.timetable_entry
            check(tt is not None, f"timetable_entry resolves for session {first_session.id}")
            if tt is not None:
                check(
                    tt.section_id is not None,
                    f"resolved timetable_entry has section_id (id={tt.id})",
                )

    # Summary
    print("\n" + "=" * 60)
    print("Phase 22.1 Verification Summary")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"\n{passed}/{passed + failed} checks passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)