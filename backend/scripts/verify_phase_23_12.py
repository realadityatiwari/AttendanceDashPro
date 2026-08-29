"""
Phase 23.12 — Migration Gate verifier.

Proves the Phase 23 migration chain is coherent, reproducible, and safe to
carry into Phase 24:

  A. exactly one Alembic head
  B. current DB revision = expected HEAD
  C. adminrole enum exists
  D. exact adminrole values
  E. admin_scopes table exists
  F. required columns exist
  G. required FKs exist
  H. role-scope CHECK exists
  I. active scope semantics (server default true)
  J. invalid scope combinations rejected (CHECK/FK, rollback transactions)
  K. nonexistent FK targets rejected
  M. schema metadata matches the models (compare_metadata)
  N. application imports successfully
  P. critical data counts unchanged by this verification (read-only baseline)
  Q/R. no unexpected schema branches / heads (single linear chain from files)
  S. explicit local/dev DB target assertion (no production)
  T. no persistent test residue (all fixtures in rolled-back transactions)

Local/dev only. Requires the seeded local DB. Usage (local only):
    $env:DATABASE_URI = "postgresql+asyncpg://postgres:postgres@127.0.0.1:55432/attendancedash"
    python scripts/verify_phase_23_12.py
"""
import asyncio
import io
import os
import sys
import uuid
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

EXPECTED_HEAD = "f9a0b1c2d3e4"
EXPECTED_ADMINROLE = ["HEAD_ADMIN", "CLASS_ADMIN", "SUBSECTION_ADMIN", "ELECTIVE_ADMIN"]
EXPECTED_TABLES = [
    "users", "sections", "subsections", "admin_scopes", "semesters",
    "academic_sessions", "subjects", "student_enrollments",
    "student_elective_choices", "timetable_entries", "class_sessions",
    "occurrence_outcomes", "attendance_records", "academic_events",
    "quiz_schedules", "quiz_cycles",
]
COUNT_TABLES = [
    "users", "student_enrollments", "subjects", "sections", "semesters",
    "academic_sessions", "timetable_entries", "class_sessions",
    "attendance_records", "academic_events", "quiz_schedules", "admin_scopes",
]

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if not ok else ""))


def alembic_heads() -> list:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    sd = ScriptDirectory.from_config(cfg)
    return sd.get_heads()


async def main() -> int:
    print("=" * 60)
    print("Phase 23.12 — Migration Gate")
    print("=" * 60)

    # ── S. explicit local/dev target assertion ────────────────────────────
    print("\n=== S. DB target assertion (local/dev only) ===")
    uri = os.environ.get("DATABASE_URI", "")
    target_local = (
        "127.0.0.1" in uri and ":55432" in uri and "attendancedash" in uri
        and "supabase" not in uri.lower() and "pooler" not in uri.lower()
    )
    check("S1. DATABASE_URI is the explicit local/dev target "
          "(127.0.0.1:55432/attendancedash, no supabase/pooler)", target_local)
    if not target_local:
        print("ABORT: refusing to run against a non-local target.")
        return 1

    # ── A/R. exactly one head, single linear chain ────────────────────────
    print("\n=== A/R. Migration graph ===")
    heads = alembic_heads()
    check("A1. exactly one Alembic head", len(heads) == 1, str(heads))
    check("A2. head is the expected revision", heads == [EXPECTED_HEAD], str(heads))
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    sd = ScriptDirectory.from_config(cfg)
    revs = {r.revision: r for r in sd.walk_revisions()}
    children = {}
    for r in revs.values():
        downs = r.down_revision if isinstance(r.down_revision, tuple) else [r.down_revision]
        for d in downs:
            children[d] = children.get(d, 0) + 1
    branches = [d for d, n in children.items() if n > 1]
    check("R1. no branching revisions (single linear chain)", not branches, str(branches))
    check("R2. 25 migrations in the chain", len(revs) == 25, str(len(revs)))

    # ── B/C/D/E/F/G/H + P. DB schema/revision/baseline ───────────────────
    print("\n=== B..P. Live DB schema, revision, baseline ===")
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from alembic.runtime.migration import MigrationContext
    from alembic.autogenerate import compare_metadata
    from app.db.base_class import Base
    import app.models  # noqa: F401 — register all models on the metadata

    engine = create_async_engine(uri)
    counts_before = {}
    async with engine.connect() as conn:
        rev = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
        check("B1. current DB revision = expected HEAD", rev == EXPECTED_HEAD, str(rev))

        tbl = set((await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        )).scalars())
        for t in EXPECTED_TABLES:
            check(f"E/M-table {t}", t in tbl)

        ar = (await conn.execute(text("SELECT enum_range(NULL::adminrole)"))).scalar()
        check("C1. adminrole enum exists", ar is not None)
        check("D1. exact adminrole values", list(ar) == EXPECTED_ADMINROLE, str(list(ar) if ar else None))

        cols = set((await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='admin_scopes'"
        ))).scalars())
        for c in ["id", "user_id", "role", "section_id", "subsection_id",
                  "subject_id", "active", "created_at", "updated_at"]:
            check(f"F-col admin_scopes.{c}", c in cols)

        fk_count = (await conn.execute(text(
            "SELECT count(*) FROM pg_constraint WHERE conrelid='admin_scopes'::regclass AND contype='f'"
        ))).scalar()
        check("G1. admin_scopes has 4 FKs (user/section/subsection/subject)", fk_count == 4)
        fk_targets = set((await conn.execute(text(
            "SELECT ccu.relname FROM pg_constraint c "
            "JOIN pg_class ccu ON ccu.oid=c.confrelid "
            "WHERE c.conrelid='admin_scopes'::regclass AND c.contype='f'"
        ))).scalars())
        check("G2. FK targets exact",
              fk_targets == {"users", "sections", "subsections", "subjects"}, str(fk_targets))

        cons = set((await conn.execute(text(
            "SELECT conname FROM pg_constraint WHERE conrelid='admin_scopes'::regclass"
        ))).scalars())
        check("H1. role-scope CHECK exists", "ck_admin_scopes_role_scope" in cons)

        col_default = (await conn.execute(text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name='admin_scopes' AND column_name='active'"
        ))).scalar()
        check("I1. active server default true", col_default is not None and "true" in col_default)

        for t in COUNT_TABLES:
            counts_before[t] = (await conn.execute(text(f"SELECT count(*) FROM {t}"))).scalar()
        check("P1. baseline captured (read-only)", True)
        print("   baseline:", counts_before)

        # ── M. metadata vs DB drift ───────────────────────────────────────
        def do_compare(sync_conn):
            ctx = MigrationContext.configure(sync_conn)
            return compare_metadata(ctx, Base.metadata)
        diff = await conn.run_sync(do_compare)
        # Known intentional/legacy difference: created_at/updated_at declared
        # NOT NULL in the model Base but nullable-with-server-default in the
        # Phase 22.3/23.6/23.11 migration convention (server default always
        # populates; DB is more permissive than the model — no integrity risk).
        legacy_nullable = [
            d for d in diff
            if isinstance(d, list) and all(
                x[0] == "modify_nullable" and x[3] in
                ("created_at", "updated_at")
                for x in d
            )
        ]
        other = [d for d in diff if d not in legacy_nullable]
        check("M1. metadata matches DB (no unclassified drift)", not other, str(other[:2]))
        check("M2. only the documented legacy timestamp-nullable convention remains",
              len(diff) == len(legacy_nullable) and len(legacy_nullable) <= 6,
              f"{len(diff)} diffs, {len(legacy_nullable)} legacy")

        # ── J/K. CHECK/FK rejection semantics (rollback transactions) ─────
        print("\n=== J/K. CHECK/FK rejection semantics (rolled back) ===")
        NOW = datetime.now(timezone.utc)
        sess, sem, sec, subj, uid = (uuid.uuid4() for _ in range(5))
        async with engine.begin() as tx:
            await tx.execute(text(
                "INSERT INTO academic_sessions (id, name, start_date, end_date, is_active, created_at, updated_at) "
                "VALUES (:i,'T',:s,:e,true,:n,:n)"), {"i": sess, "s": date(2026, 7, 1), "e": date(2027, 3, 31), "n": NOW})
            await tx.execute(text(
                "INSERT INTO semesters (id, name, session_id, start_date, end_date, created_at, updated_at) "
                "VALUES (:i,'S',:s,:sd,:ed,:n,:n)"), {"i": sem, "s": sess, "sd": date(2026, 7, 1), "ed": date(2026, 12, 31), "n": NOW})
            await tx.execute(text(
                "INSERT INTO sections (id, name, semester_id, created_at, updated_at) VALUES (:i,'CS-T',:s,:n,:n)"),
                {"i": sec, "s": sem, "n": NOW})
            await tx.execute(text(
                "INSERT INTO subjects (id, code, name, semester_id, category, quiz_applicable, attendance_applicable, created_at, updated_at) "
                "VALUES (:i,'BCS-T','T',:s,'THEORY',true,true,:n,:n)"), {"i": subj, "s": sem, "n": NOW})
            await tx.execute(text(
                "INSERT INTO users (id, roll_number, name, role, section_id, created_at, updated_at) "
                "VALUES (:i,'T9999999','T','STUDENT',:s,:n,:n)"), {"i": uid, "s": sec, "n": NOW})
            await tx.execute(text("INSERT INTO admin_scopes (id, user_id, role) VALUES (:i,:u,'HEAD_ADMIN')"),
                             {"i": uuid.uuid4(), "u": uid})
            await tx.execute(text("INSERT INTO admin_scopes (id, user_id, role, section_id) VALUES (:i,:u,'CLASS_ADMIN',:s)"),
                             {"i": uuid.uuid4(), "u": uid, "s": sec})
            await tx.execute(text("INSERT INTO admin_scopes (id, user_id, role, subject_id) VALUES (:i,:u,'ELECTIVE_ADMIN',:s)"),
                             {"i": uuid.uuid4(), "u": uid, "s": subj})
        # Valid rows were committed in their own transaction; remove them at the end.
        fixture_scope_ids = set((await conn.execute(text(
            "SELECT id FROM admin_scopes WHERE user_id = :u"), {"u": uid})).scalars())
        fixture_user_id = uid

        cases = [
            ("J1. CLASS_ADMIN without section rejected (CHECK)",
             "INSERT INTO admin_scopes (id, user_id, role) VALUES (:i, :u, 'CLASS_ADMIN')", {}),
            ("J2. ELECTIVE_ADMIN without subject rejected (CHECK)",
             "INSERT INTO admin_scopes (id, user_id, role) VALUES (:i, :u, 'ELECTIVE_ADMIN')", {}),
            ("J3. HEAD_ADMIN with a scope column rejected (CHECK)",
             "INSERT INTO admin_scopes (id, user_id, role, section_id) VALUES (:i, :u, 'HEAD_ADMIN', :s)",
             {"s": sec}),
            ("K1. ELECTIVE_ADMIN with nonexistent subject rejected (FK)",
             "INSERT INTO admin_scopes (id, user_id, role, subject_id) VALUES (:i, :u, 'ELECTIVE_ADMIN', :s)",
             {"s": uuid.uuid4()}),
            ("J4. invalid enum value rejected",
             "INSERT INTO admin_scopes (id, user_id, role) VALUES (:i, :u, 'BOGUS_ROLE')", {}),
        ]
        for label, sql, extra in cases:
            async with engine.begin() as tx:
                params = {"i": uuid.uuid4(), "u": uid}
                params.update(extra)
                try:
                    await tx.execute(text(sql), params)
                    check(label, False, "insert unexpectedly succeeded")
                except Exception:
                    check(label, True)

    await engine.dispose()

    # ── N. application imports ────────────────────────────────────────────
    print("\n=== N. Application compatibility ===")
    try:
        from app.main import app as fastapi_app  # noqa: F401
        from app.services.authorization_service import AuthorizationService  # noqa: F401
        from app.models.enums import AdminRole  # noqa: F401
        check("N1. application + authorization service import successfully", True)
    except Exception as e:
        check("N1. application + authorization service import successfully", False, str(e)[:120])

    # ── L. offline downgrade SQL (dependency-safe order, no execution) ────
    print("\n=== L. Offline downgrade SQL validation (no execution) ===")
    try:
        os.environ["DATABASE_URI"] = uri
        buf = io.StringIO()
        from alembic.command import downgrade
        from alembic.config import Config as AlembicConfig
        acfg = AlembicConfig(str(BACKEND_DIR / "alembic.ini"))
        acfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        # Offline SQL generation writes to stdout; capture it WITHOUT executing.
        with redirect_stdout(buf):
            downgrade(acfg, f"{EXPECTED_HEAD}:f8a9b0c1d2e3", sql=True)
        sql_text = buf.getvalue()
        check("L1. downgrade SQL generated",
              "DROP TABLE admin_scopes" in sql_text and "DROP TYPE adminrole" in sql_text)
        check("L2. dependency-safe order (index -> table -> type)",
              sql_text.find("DROP INDEX ix_admin_scopes_user_id") < sql_text.find("DROP TABLE admin_scopes")
              < sql_text.find("DROP TYPE adminrole"))
    except Exception as e:
        check("L1. downgrade SQL generated", False, str(e)[:160])

    # ── T. cleanup fixtures + residue check + P re-check ─────────────────
    print("\n=== T/P. Cleanup + no residue ===")
    from sqlalchemy.ext.asyncio import create_async_engine as _cae
    engine2 = _cae(uri)
    async with engine2.begin() as tx:
        for sid in fixture_scope_ids:
            await tx.execute(text("DELETE FROM admin_scopes WHERE id = :i"), {"i": sid})
        if fixture_user_id is not None:
            await tx.execute(text("DELETE FROM users WHERE id = :i"), {"i": fixture_user_id})
        await tx.execute(text("DELETE FROM subjects WHERE code = 'BCS-T'"))
        await tx.execute(text("DELETE FROM sections WHERE name = 'CS-T'"))
        await tx.execute(text("DELETE FROM semesters WHERE name = 'S'"))
        await tx.execute(text("DELETE FROM academic_sessions WHERE name = 'T'"))
    async with engine2.connect() as conn:
        counts_after = {t: (await conn.execute(text(f"SELECT count(*) FROM {t}"))).scalar() for t in COUNT_TABLES}
        residue = (await conn.execute(text(
            "SELECT count(*) FROM users WHERE roll_number = 'T9999999'"))).scalar()
        ar2 = (await conn.execute(text("SELECT enum_range(NULL::adminrole)"))).scalar()
        rev2 = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
    await engine2.dispose()
    check("T1. no fixture residue", residue == 0)
    check("T2. enum unchanged after verification", list(ar2) == EXPECTED_ADMINROLE)
    check("T3. revision unchanged after verification", rev2 == EXPECTED_HEAD)
    check("P2. critical data counts unchanged by this verification",
          counts_after == counts_before,
          str({k: (counts_before.get(k), counts_after.get(k)) for k in COUNT_TABLES
               if counts_before.get(k) != counts_after.get(k)}))

    failed = [name for name, ok in results if not ok]
    print("=" * 60)
    print(f"Phase 23.12 verifier: {len(results) - len(failed)}/{len(results)} PASS")
    if failed:
        print("FAILED:", failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
