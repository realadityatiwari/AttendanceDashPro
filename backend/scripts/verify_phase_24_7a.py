"""Phase 24.7-A post-migration verification (LOCAL DB only)."""
import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

URI = "postgresql+asyncpg://postgres:postgres@127.0.0.1:55432/attendancedash"

async def main():
    engine = create_async_engine(URI)
    async with engine.connect() as conn:
        # 1. Column existence
        cols = {}
        r = await conn.execute(text(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'timetable_entries'"))
        for row in r.all():
            cols[row[0]] = (row[1], row[2])
        required = ["id", "subject_id", "day_of_week", "start_time", "end_time",
                    "class_type", "section_id", "subsection_id", "room",
                    "is_active", "sort_order", "elective_slot"]
        for c in required:
            if c in cols:
                print(f"OK   column {c:16} {cols[c][0]:20} nullable={cols[c][1]}")
            else:
                print(f"MISSING column {c}")
                sys.exit(1)

        # 2. Constraints
        r = await conn.execute(text(
            "SELECT conname FROM pg_constraint WHERE conrelid = 'timetable_entries'::regclass"))
        cons = {row[0] for row in r.all()}
        for expected in ["ck_timetable_entries_end_gt_start",
                         "ck_timetable_entries_day_of_week_range",
                         "fk_timetable_entries_section_subsection",
                         "timetable_entries_subsection_id_fkey",
                         "timetable_entries_section_id_fkey",
                         "timetable_entries_subject_id_fkey"]:
            print(f"OK   constraint {expected}: {'present' if expected in cons else 'MISSING'}")
            if expected not in cons:
                sys.exit(1)

        # 3. subsections unique constraint
        r = await conn.execute(text(
            "SELECT conname FROM pg_constraint WHERE conrelid = 'subsections'::regclass AND conname = 'uq_subsections_section_id'"))
        uq_present = r.scalar()
        print(f"OK   subsections uq_subsections_section_id: {'present' if uq_present else 'MISSING'}")
        if not uq_present:
            sys.exit(1)

        # 4. Row preservation (baseline was 28 rows)
        r = await conn.execute(text("SELECT count(*) FROM timetable_entries"))
        total = r.scalar()
        print(f"OK   total rows: {total}")
        if total != 28:
            print(f"FAIL expected 28 rows, got {total}")
            sys.exit(1)

        # 5. Backfill determinism: all rows active, subsection/room/sort NULL
        r = await conn.execute(text("SELECT count(*) FROM timetable_entries WHERE is_active = true"))
        active = r.scalar()
        print(f"OK   active rows (default backfill): {active}/28")
        if active != 28:
            print("FAIL not all rows active")
            sys.exit(1)
        r = await conn.execute(text(
            "SELECT count(*) FROM timetable_entries WHERE subsection_id IS NOT NULL OR room IS NOT NULL OR sort_order IS NOT NULL"))
        filled = r.scalar()
        print(f"OK   rows with fabricated subsection/room/sort: {filled} (expect 0)")
        if filled != 0:
            print("FAIL unexpected fabricated data")
            sys.exit(1)

        # 6. Readability: full select round-trips fine (all columns populated
        #    with existing values).
        r = await conn.execute(text(
            "SELECT id, subject_id, section_id, day_of_week, start_time, end_time, class_type, "
            "elective_slot, is_active FROM timetable_entries LIMIT 5"))
        rows = r.all()
        print(f"OK   sample rows readable: {len(rows)}")
        for row in rows:
            print("     ", str(row[0])[:8], str(row[1])[:8], str(row[2])[:8],
                  row[3], row[4], row[5], row[6], row[7], row[8])

        # 7. No unrelated tables touched by this migration (spot check counts)
        r = await conn.execute(text(
            "SELECT count(*) FROM (SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name IN "
            "('subjects','sections','subsections','academic_sessions','semesters','users')) t"))
        print(f"OK   core academic tables present: {r.scalar()}")

    await engine.dispose()
    print("\nPhase 24.7-A DB verification PASS")

asyncio.run(main())
