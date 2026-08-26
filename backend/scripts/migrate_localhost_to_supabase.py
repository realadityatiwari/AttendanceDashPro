"""
AttendanceDash Pro — Controlled Localhost → Supabase Production Migration (Phase 21D.3)

Reads the audited application state from the LOCALHOST PostgreSQL database and
writes an exact controlled copy to the SUPABASE PRODUCTION database.

SOURCE SAFETY
  - The source connection is READ-ONLY by design: only SELECT statements are
    issued against DATABASE_URI_SOURCE. No INSERT/UPDATE/DELETE/TRUNCATE/ALTER/
    DROP is ever executed on the source.

TARGET SAFETY
  - The target must be EMPTY for every application table (verified in
    preflight). Unexpected rows abort the migration.
  - No ON CONFLICT DO NOTHING is used as a safety mechanism: a conflict means
    a migration problem and aborts the whole transaction.
  - All writes are executed inside ONE transaction; any failure rolls back
    the entire migration.

PRESERVATION POLICY
  - UUID primary keys are copied verbatim (no regeneration, no remapping).
  - created_at / updated_at timestamps are copied verbatim.
  - The owner's hashed_password is copied verbatim (PBKDF2-SHA256, compatible
    with the application verifier). It is never printed.

USAGE
  Requires two environment variables (values are never printed):
    DATABASE_URI_SOURCE   — localhost PostgreSQL asyncpg URL (read-only)
    DATABASE_URI_TARGET   — Supabase production asyncpg URL (write)

  Preflight + source snapshot (no writes):
    python scripts/migrate_localhost_to_supabase.py --verify-only

  Execute (writes to TARGET only, in one transaction):
    python scripts/migrate_localhost_to_supabase.py --execute

  After a successful commit, the script automatically runs post-migration
  verification (counts, UUID sets, content sets, FK integrity).

Exit codes: 0 = success, 1 = any failure (abort / rollback / verification).
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

EXPECTED_HEAD = "e1f2a3b4c5d6"

# FK-safe migration order (from the Phase 21D.2 full-state audit).
# Root tables first; leaf tables last. laboratory_* and feedback are included
# for completeness (currently empty locally) and are skipped when empty.
MIGRATION_TABLES = [
    "academic_sessions",   # root
    "semesters",           # -> academic_sessions
    "sections",            # -> semesters
    "quiz_cycles",         # root
    "subjects",            # -> semesters
    "users",               # -> sections
    "timetable_entries",   # -> subjects
    "class_sessions",      # -> subjects, timetable_entries
    "student_enrollments", # -> users, subjects
    "academic_events",     # -> subjects
    "quiz_schedules",      # -> subjects, quiz_cycles
    "eligibility_policies",# -> quiz_cycles
    "attendance_records",  # -> users, class_sessions
    "notifications",       # -> users
    "userpreferences",     # -> users
    "laboratory_experiments",  # -> subjects (empty locally)
    "laboratory_records",      # -> users, laboratory_experiments, class_sessions (empty locally)
    "feedback",                # -> users (empty locally)
]

# Tables where hashed_password / other secrets may appear and must never be
# printed even in error messages.
SENSITIVE_COLUMNS = {"hashed_password"}


def env_required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: {name} environment variable is not set.", file=sys.stderr)
        print(f"Set {name} before running (its value is never printed).", file=sys.stderr)
        sys.exit(1)
    return value


async def get_columns(engine, table: str) -> list[str]:
    async with engine.connect() as conn:
        r = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t AND table_schema = 'public' ORDER BY ordinal_position"
        ), {"t": table})
        return [row[0] for row in r.fetchall()]


async def table_row_count(engine, table: str) -> int:
    async with engine.connect() as conn:
        r = await conn.execute(text(f'SELECT count(*) FROM "{table}"'))
        return r.scalar()


async def alembic_version(engine) -> str | None:
    async with engine.connect() as conn:
        r = await conn.execute(text("SELECT version_num FROM alembic_version"))
        return r.scalar()


async def preflight_target(engine) -> None:
    """Verify the target schema and emptiness. Aborts on any unexpected state."""
    print("[preflight] verifying target schema and emptiness...")
    head = await alembic_version(engine)
    if head != EXPECTED_HEAD:
        print(f"ERROR: target alembic_version = {head}, expected {EXPECTED_HEAD}.", file=sys.stderr)
        sys.exit(1)
    print(f"[preflight] target alembic head OK: {head}")

    for table in MIGRATION_TABLES:
        cols = await get_columns(engine, table)
        if not cols:
            print(f"ERROR: target table '{table}' does not exist (no columns).", file=sys.stderr)
            sys.exit(1)
        count = await table_row_count(engine, table)
        if count != 0:
            print(f"ERROR: target table '{table}' is NOT empty ({count} rows). "
                  f"Refusing to migrate over existing data.", file=sys.stderr)
            sys.exit(1)
    print("[preflight] all 18 target tables exist and are empty.")


async def capture_source(engine) -> dict[str, list[dict]]:
    """Read the full source state (read-only). Returns {table: [row dicts]}."""
    print("[source] capturing full source state (read-only)...")
    data = {}
    for table in MIGRATION_TABLES:
        cols = await get_columns(engine, table)
        if not cols:
            print(f"ERROR: source table '{table}' does not exist.", file=sys.stderr)
            sys.exit(1)
        async with engine.connect() as conn:
            r = await conn.execute(text(f'SELECT * FROM "{table}"'))
            rows = [dict(zip(cols, row)) for row in r.fetchall()]
        data[table] = rows
        print(f"[source] {table}: {len(rows)} rows")
    return data


def row_key(row: dict, cols: list[str]) -> str:
    """Build a deterministic comparison key excluding secrets and volatile fields."""
    key = []
    for c in cols:
        if c in SENSITIVE_COLUMNS:
            continue
        v = row.get(c)
        key.append(f"{c}={v!r}")
    return "|".join(key)


async def verify_migration(source_data: dict, target_engine) -> bool:
    """Post-migration verification: counts, UUID sets, content sets, FK checks."""
    print("\n[verify] post-migration verification...")
    ok = True

    # 1. Counts + UUID sets + content sets
    for table in MIGRATION_TABLES:
        src_rows = source_data[table]
        src_count = len(src_rows)
        tgt_count = await table_row_count(target_engine, table)
        match = src_count == tgt_count
        print(f"[verify] {table}: source={src_count} target={tgt_count} "
              f"{'OK' if match else 'MISMATCH'}")
        ok = ok and match

        cols = await get_columns(target_engine, table)
        # Compare UUID sets (id column) when the table has an id
        if "id" in cols:
            src_ids = {str(r["id"]) for r in src_rows if r.get("id") is not None}
            async with target_engine.connect() as conn:
                r = await conn.execute(text(f'SELECT id FROM "{table}"'))
                tgt_ids = {str(row[0]) for row in r.fetchall()}
            ids_match = src_ids == tgt_ids
            print(f"[verify] {table}: UUID set {'MATCH' if ids_match else 'MISMATCH'}"
                  f" ({len(src_ids)} vs {len(tgt_ids)})")
            ok = ok and ids_match

        # Compare deterministic content sets (excluding sensitive columns),
        # for tables that actually have rows.
        if src_count > 0:
            src_keys = {row_key(r, cols) for r in src_rows}
            async with target_engine.connect() as conn:
                r = await conn.execute(text(f'SELECT * FROM "{table}"'))
                tgt_keys = {row_key(dict(zip(cols, row)), cols) for row in r.fetchall()}
            content_match = src_keys == tgt_keys
            print(f"[verify] {table}: content set {'MATCH' if content_match else 'MISMATCH'}")
            ok = ok and content_match

    # 2. FK integrity (orphan checks)
    print("\n[verify] FK integrity checks...")
    fk_checks = [
        ("student_enrollments", "user_id", "users"),
        ("student_enrollments", "subject_id", "subjects"),
        ("attendance_records", "user_id", "users"),
        ("attendance_records", "class_session_id", "class_sessions"),
        ("class_sessions", "subject_id", "subjects"),
        ("class_sessions", "timetable_entry_id", "timetable_entries"),
        ("academic_events", "subject_id", "subjects"),
        ("quiz_schedules", "subject_id", "subjects"),
        ("quiz_schedules", "quiz_cycle_id", "quiz_cycles"),
        ("eligibility_policies", "quiz_cycle_id", "quiz_cycles"),
        ("notifications", "user_id", "users"),
        ("userpreferences", "user_id", "users"),
        ("feedback", "user_id", "users"),
        ("laboratory_experiments", "subject_id", "subjects"),
        ("laboratory_records", "user_id", "users"),
        ("laboratory_records", "experiment_id", "laboratory_experiments"),
        ("laboratory_records", "class_session_id", "class_sessions"),
        ("laboratory_records", "signed_by", "users"),
        ("laboratory_records", "created_by", "users"),
        ("laboratory_records", "updated_by", "users"),
        ("sections", "semester_id", "semesters"),
        ("semesters", "session_id", "academic_sessions"),
        ("subjects", "semester_id", "semesters"),
        ("timetable_entries", "subject_id", "subjects"),
        ("users", "section_id", "sections"),
    ]
    async with target_engine.connect() as conn:
        for child, col, parent in fk_checks:
            r = await conn.execute(text(
                f'SELECT count(*) FROM "{child}" c '
                f'LEFT JOIN "{parent}" p ON p.id = c."{col}" '
                f'WHERE c."{col}" IS NOT NULL AND p.id IS NULL'
            ))
            orphans = r.scalar()
            if orphans != 0:
                print(f"[verify] FK ORPHAN: {child}.{col} -> {parent}: {orphans}")
                ok = False
    print("[verify] FK integrity: all checks complete.")

    return ok


async def run_migration(source_engine, target_engine, mode: str) -> None:
    # 1. Preflight target (verify-only also does this)
    await preflight_target(target_engine)

    # 2. Capture full source state (read-only)
    source_data = await capture_source(source_engine)

    # 3. Owner identity assertion (read-only; never prints the hash)
    owner_rows = source_data["users"]
    if len(owner_rows) != 1:
        print(f"ERROR: expected exactly 1 user in source, found {len(owner_rows)}.", file=sys.stderr)
        sys.exit(1)
    owner = owner_rows[0]
    if owner.get("roll_number") != "2401220100027":
        print(f"ERROR: unexpected owner roll_number: {owner.get('roll_number')!r}.", file=sys.stderr)
        sys.exit(1)
    if owner.get("role") != "ADMIN":
        print(f"ERROR: unexpected owner role: {owner.get('role')!r}.", file=sys.stderr)
        sys.exit(1)
    if not owner.get("hashed_password"):
        print("ERROR: owner hashed_password is missing in source.", file=sys.stderr)
        sys.exit(1)
    print("[source] owner identity OK: roll_number=2401220100027 role=ADMIN "
          "(password hash present; not printed)")

    if mode == "verify-only":
        print("\n[verify-only] preflight + source snapshot complete. "
              "No writes performed.")
        print("[verify-only] run with --execute to perform the migration.")
        return

    # 4. Execute: single transaction, no ON CONFLICT DO NOTHING.
    print("\n[execute] starting migration in ONE transaction...")
    async with target_engine.begin() as txn:
        for table in MIGRATION_TABLES:
            rows = source_data[table]
            if not rows:
                print(f"[execute] {table}: 0 rows (skip)")
                continue
            cols = list(rows[0].keys())
            col_list = ", ".join(f'"{c}"' for c in cols)
            placeholders = ", ".join(f":{c}" for c in cols)
            stmt = text(f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})')
            for row in rows:
                # Execute row-by-row so a conflict reports the exact table/key.
                try:
                    await txn.execute(stmt, row)
                except Exception as e:
                    # Report the table and the non-sensitive identifying key
                    # (never the password hash or full row).
                    ident = None
                    for c in ("roll_number", "code", "id", "user_id", "subject_id"):
                        if c in row and c not in SENSITIVE_COLUMNS:
                            ident = f"{c}={row[c]!r}"
                            break
                    print(f"ERROR: insert failed in '{table}' "
                          f"({ident or 'no identifying key'}).", file=sys.stderr)
                    print(f"  Detail: {type(e).__name__}", file=sys.stderr)
                    raise
            print(f"[execute] {table}: {len(rows)} rows inserted")
        # Transaction commits here if no exception; otherwise rolls back fully.

    print("[execute] transaction COMMITTED.")

    # 5. Post-migration verification
    ok = await verify_migration(source_data, target_engine)
    if not ok:
        print("ERROR: post-migration verification FAILED.", file=sys.stderr)
        print("Source of truth (localhost) is untouched. Production is now in a "
              "migrated state that failed verification — report this before any "
              "further action.", file=sys.stderr)
        sys.exit(1)
    print("\n[result] migration SUCCESS — localhost == production for the "
          "audited application state.")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Controlled localhost -> Supabase production migration (Phase 21D.3)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-only", action="store_true",
                       help="preflight target + capture source snapshot; no writes")
    group.add_argument("--execute", action="store_true",
                       help="preflight, capture source, then migrate in one transaction")
    args = parser.parse_args()

    source_uri = env_required("DATABASE_URI_SOURCE")
    target_uri = env_required("DATABASE_URI_TARGET")

    source_engine = create_async_engine(source_uri, echo=False, future=True)
    target_engine = create_async_engine(target_uri, echo=False, future=True)

    try:
        await run_migration(source_engine, target_engine,
                            "execute" if args.execute else "verify-only")
    finally:
        await source_engine.dispose()
        await target_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
