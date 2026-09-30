"""Apply migration e2f3a4b5c6d7 (class_session lifecycle + provenance) to the
PRODUCTION database — guarded, single-revision, no data writes.

Operational contract (Chunk — apply the existing lifecycle migration):

  - The production DATABASE_URI comes from the environment variable
    ``DATABASE_URI_TARGET`` (the same variable the Supabase migration script
    uses). It is NEVER printed, logged, or echoed by this script.
  - DEFAULT MODE IS VERIFY-ONLY: preflight read-only checks with hard STOP
    conditions. The upgrade runs ONLY with ``--execute`` AND a passing
    preflight.
  - Exactly ONE migration is applied: ``alembic upgrade head`` from THIS
    checkout (must be da4f4a1 or later containing e2f3a4b5c6d7). No downgrade,
    no seed scripts, no repairs, no manual DML.

Preflight STOP conditions (Chunk STEP 1):
  1. revision already at/above e2f3a4b5c6d7  -> nothing to do (report only)
  2. revision is anything other than f0e1d2c3b4a5 (the expected pre-state)
  3. multiple/unknown Alembic heads in the checkout
  4. columns already exist while revision still says f0e1d2c3b4a5 (inconsistent)
  5. DATABASE_URI_TARGET missing or pointing at localhost (locality guard,
     mirrors verify_phase_24_3.py)

Postflight verification (Chunk STEP 3/5):
  - revision == e2f3a4b5c6d7
  - is_deactivated: boolean, NOT NULL, default false
  - source_event_id: uuid, nullable; FK to academic_events(id); index present
  - class_sessions / attendance_records / academic_events row counts unchanged
  - NO backfill: zero rows with is_deactivated <> false, zero rows with
    source_event_id IS NOT NULL
  - July 30 BCS-054 rows untouched (count reported, flags all clean)

Usage (operator terminal, from backend/):
    set DATABASE_URI_TARGET=postgresql://...   (or export ... on POSIX)
    python scripts/apply_lifecycle_migration_prod.py                # verify-only
    python scripts/apply_lifecycle_migration_prod.py --execute      # apply
"""
import argparse
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

EXPECTED_PRE_REVISION = "f0e1d2c3b4a5"
TARGET_REVISION = "e2f3a4b5c6d7"
MIGRATION_MONTH_DATE = date(2026, 7, 30)
BCS054_CODE = "BCS-054"

PASS, FAIL = "[PASS]", "[FAIL]"


def fail(msg: str) -> None:
    print(f"{FAIL} {msg}")


def ok(msg: str) -> None:
    print(f"{PASS} {msg}")


def load_target_uri() -> str:
    """Reads the production URI from the environment. Never prints it."""
    uri = os.environ.get("DATABASE_URI_TARGET", "").strip()
    if not uri:
        fail("DATABASE_URI_TARGET is not set. Export the production "
             "DATABASE_URI in THIS terminal and re-run.")
        raise SystemExit(2)
    lowered = uri.lower()
    if "localhost" in lowered or "127.0.0.1" in lowered or "@[::1]" in lowered:
        fail("Locality guard: DATABASE_URI_TARGET points at localhost — "
             "refusing (this script is production-only).")
        raise SystemExit(2)
    return uri


def check_migration_graph() -> bool:
    """Offline check of the checkout's migration graph (no DB connection)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if heads != [TARGET_REVISION]:
        fail(f"unexpected Alembic heads in checkout: {heads} — STOP")
        return False
    ok(f"checkout migration graph: single head {heads[0]}")
    return True


async def preflight(uri: str):
    """Read-only STEP 1 (and STEP 3 post-checks reuse this). Returns a dict
    of everything worth reporting; raises SystemExit on STOP conditions."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(uri, connect_args={
        # Supabase session/transaction pooler: asyncpg statement caching must
        # be off behind PgBouncer.
        "statement_cache_size": 0,
        "server_settings": {"application_name": "adp-lifecycle-migration"},
    })
    report = {}
    try:
        async with engine.connect() as conn:
            report["revision"] = (await conn.execute(
                text("SELECT version_num FROM alembic_version"))).scalar_one()

            report["columns"] = {
                r[0]: {"data_type": r[1], "nullable": r[2], "default": r[3]}
                for r in (await conn.execute(text(
                    "SELECT column_name, data_type, is_nullable, column_default "
                    "FROM information_schema.columns "
                    "WHERE table_name = 'class_sessions' "
                    "AND column_name IN ('is_deactivated','source_event_id')"))).all()
            }

            for table in ("class_sessions", "attendance_records", "academic_events"):
                report[f"count_{table}"] = (await conn.execute(
                    text(f'SELECT COUNT(*) FROM "{table}"'))).scalar_one()

            # FK + index presence for source_event_id
            report["fk"] = (await conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.table_constraints "
                "WHERE table_name = 'class_sessions' "
                "AND constraint_type = 'FOREIGN KEY' "
                "AND constraint_name = 'fk_class_sessions_source_event_id'"
            ))).scalar_one()
            report["index"] = (await conn.execute(text(
                "SELECT COUNT(*) FROM pg_indexes "
                "WHERE tablename = 'class_sessions' "
                "AND indexname = 'ix_class_sessions_source_event_id'"
            ))).scalar_one()

            if "is_deactivated" in report["columns"]:
                report["rows_flagged"] = (await conn.execute(text(
                    "SELECT COUNT(*) FROM class_sessions WHERE is_deactivated IS TRUE"
                ))).scalar_one()
                report["rows_with_provenance"] = (await conn.execute(text(
                    "SELECT COUNT(*) FROM class_sessions WHERE source_event_id IS NOT NULL"
                ))).scalar_one()

            # July 30 BCS-054 fingerprint (counts only — no row data printed)
            report["jul30"] = {
                "sessions": (await conn.execute(text(
                    "SELECT COUNT(*) FROM class_sessions cs "
                    "JOIN subjects s ON cs.subject_id = s.id "
                    "WHERE s.code = :code AND cs.date = :d"),
                    {"code": BCS054_CODE, "d": MIGRATION_MONTH_DATE})).scalar_one(),
                "extra_sessions": (await conn.execute(text(
                    "SELECT COUNT(*) FROM class_sessions cs "
                    "JOIN subjects s ON cs.subject_id = s.id "
                    "WHERE s.code = :code AND cs.date = :d AND cs.is_extra"),
                    {"code": BCS054_CODE, "d": MIGRATION_MONTH_DATE})).scalar_one(),
            }
            if "is_deactivated" in report["columns"]:
                # Only answerable once the migration is applied.
                report["jul30"]["flagged"] = (await conn.execute(text(
                    "SELECT COUNT(*) FROM class_sessions cs "
                    "JOIN subjects s ON cs.subject_id = s.id "
                    "WHERE s.code = :code AND cs.date = :d AND cs.is_deactivated"),
                    {"code": BCS054_CODE, "d": MIGRATION_MONTH_DATE})).scalar_one()
    finally:
        await engine.dispose()
    return report


def print_preflight(report: dict) -> None:
    print(f"  alembic revision : {report['revision']}")
    print(f"  class_sessions   : {report['count_class_sessions']} rows")
    print(f"  attendance_recs  : {report['count_attendance_records']} rows")
    print(f"  academic_events  : {report['count_academic_events']} rows")
    cols = report["columns"]
    print(f"  is_deactivated   : {cols['is_deactivated'] if 'is_deactivated' in cols else 'ABSENT'}")
    print(f"  source_event_id  : {cols['source_event_id'] if 'source_event_id' in cols else 'ABSENT'}")
    j = report["jul30"]
    flagged = f", {j['flagged']} flagged" if "flagged" in j else ""
    print(f"  Jul30 {BCS054_CODE}    : {j['sessions']} session(s), "
          f"{j['extra_sessions']} extra{flagged}")


def preflight_stop(report: dict) -> str | None:
    """Returns a STOP reason, or None when safe to upgrade."""
    rev = report["revision"]
    cols = report["columns"]
    if rev == TARGET_REVISION:
        return f"already at {TARGET_REVISION} — nothing to do"
    if rev != EXPECTED_PRE_REVISION:
        return (f"unexpected pre-state revision {rev!r} "
                f"(expected {EXPECTED_PRE_REVISION!r}) — manual review required")
    if "is_deactivated" in cols or "source_event_id" in cols:
        return "columns already exist while revision still says " \
               f"{EXPECTED_PRE_REVISION} — inconsistent state, manual review"
    return None


def run_upgrade() -> None:
    """STEP 2 — exactly `alembic upgrade head`, from this checkout.

    SYNC on purpose: alembic's command API drives env.py, which runs its own
    event loop internally. It must execute on a worker thread (via
    run_in_executor) where no loop is running."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # env.py resolves the URL from settings.DATABASE_URI; the env var was set
    # before app import in main().
    command.upgrade(cfg, "head")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="apply the upgrade (default is verify-only)")
    args = parser.parse_args()

    uri = load_target_uri()
    if not check_migration_graph():
        return 2

    # Inject the target URI for app.settings BEFORE app imports resolve it,
    # so alembic env.py upgrades the production database.
    os.environ["DATABASE_URI"] = uri

    print("=" * 64)
    print("STEP 1 — PREFLIGHT (read-only)")
    print("=" * 64)
    pre = await preflight(uri)
    print_preflight(pre)

    stop = preflight_stop(pre)
    if stop:
        fail(f"STOP: {stop}")
        return 2
    ok(f"preflight clean: {EXPECTED_PRE_REVISION} -> {TARGET_REVISION} is safe")

    if not args.execute:
        print("\nverify-only: no changes made. Re-run with --execute to apply.")
        return 0

    print("\n" + "=" * 64)
    print("STEP 2 — APPLYING alembic upgrade head")
    print("=" * 64)
    await asyncio.get_event_loop().run_in_executor(None, run_upgrade)
    ok("alembic upgrade head completed")

    print("\n" + "=" * 64)
    print("STEP 3 — POSTFLIGHT (read-only)")
    print("=" * 64)
    post = await preflight(uri)
    print_preflight(post)

    problems = []
    if post["revision"] != TARGET_REVISION:
        problems.append(f"revision is {post['revision']}, expected {TARGET_REVISION}")
    c = post["columns"].get("is_deactivated")
    if not c or c["data_type"] != "boolean" or c["nullable"] != "NO":
        problems.append(f"is_deactivated definition unexpected: {c}")
    if c and not (c["default"] or "").startswith("false"):
        problems.append(f"is_deactivated default unexpected: {c['default']}")
    s = post["columns"].get("source_event_id")
    if not s or s["data_type"] != "uuid" or s["nullable"] != "YES":
        problems.append(f"source_event_id definition unexpected: {s}")
    if post["fk"] != 1:
        problems.append("FK fk_class_sessions_source_event_id missing")
    if post["index"] != 1:
        problems.append("index ix_class_sessions_source_event_id missing")
    for table in ("class_sessions", "attendance_records", "academic_events"):
        if post[f"count_{table}"] != pre[f"count_{table}"]:
            problems.append(
                f"{table} row count changed: {pre[f'count_{table}']} -> "
                f"{post[f'count_{table}']}")
    if "is_deactivated" not in post["columns"]:
        problems.append("is_deactivated column missing after upgrade")
    elif post["rows_flagged"] != 0:
        problems.append(f"BACKFILL DETECTED: {post['rows_flagged']} rows flagged")
    if "source_event_id" not in post["columns"]:
        problems.append("source_event_id column missing after upgrade")
    elif post["rows_with_provenance"] != 0:
        problems.append("BACKFILL DETECTED: rows with provenance")
    j_pre, j_post = pre["jul30"], post["jul30"]
    if (j_pre["sessions"], j_pre["extra_sessions"]) != \
            (j_post["sessions"], j_post["extra_sessions"]):
        problems.append("July 30 BCS-054 session count changed")
    if j_post.get("flagged", 0) != 0:
        problems.append("July 30 BCS-054 rows were flagged")

    if problems:
        print()
        for p in problems:
            fail(p)
        return 1

    ok(f"revision is {TARGET_REVISION}")
    ok("both columns present with expected definitions")
    ok("FK + index present")
    ok("row counts unchanged (class_sessions / attendance_records / academic_events)")
    ok("NO backfill: every existing row is_deactivated=false, source_event_id=NULL")
    ok(f"July 30 {BCS054_CODE} untouched: {j_post['sessions']} session(s), "
       f"{j_post['extra_sessions']} extra, 0 flagged")
    print("\nSTEP 4 (manual): confirm the live endpoints with an authenticated "
          "session — GET /api/v1/dashboard/summary, /attendance/history, "
          "/attendance/summary/BCS-054, /calendar, /quiz-eligibility/* — and "
          "the dashboard UI.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
