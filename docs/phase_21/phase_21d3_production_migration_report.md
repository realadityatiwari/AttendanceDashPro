# AttendanceDash Pro — Phase 21D.3: Controlled Localhost → Supabase Production Migration

Status: **PREFLIGHT PASSED — MIGRATION BLOCKED AT PRODUCTION ACCESS BOUNDARY**

## 1. Preflight Result

| Check | Status |
|---|---|
| Migration tool compiled (299 lines, compile PASS) | ✅ |
| FK order validated against actual schema (parents before children) | ✅ |
| Source snapshot matches Phase 21D.2 audit (all 18 tables) | ✅ |
| Owner identity: 2401220100027, ADMIN, PBKDF2 hash present | ✅ |
| Attendance: 165 total (108 ATTENDED / 57 MISSED) | ✅ |
| Alembic head: e1f2a3b4c5d6 | ✅ |
| Localhost backup created (88 KB, `C:\Users\Lenovo\AppData\Local\Temp\kilo\pre_migration_backup\`) | ✅ |
| Production preflight (`DATABASE_URI_TARGET` env var) | **BLOCKED** |

## 2. Production Access Boundary

The migration tool requires `DATABASE_URI_TARGET` (the Supabase Session Pooler URL with `?ssl=require`). This value exists only in the operator's Render dashboard / environment — **not in the repository** and **not in this session's environment**. Per the phase's hard rule ("Do not attempt to obtain credentials from the user"), no attempt was made to read or ask for this value.

The tool correctly refuses to proceed without it (exit 1, credential never printed).

## 3. Migration Tool

Created: `backend/scripts/migrate_localhost_to_supabase.py` (299 lines)

**Design:**
- Reads `DATABASE_URI_SOURCE` (localhost) and `DATABASE_URI_TARGET` (Supabase) from environment variables — never prints them.
- `--verify-only`: preflight target + capture source snapshot; no writes.
- `--execute`: preflight, capture source, then migrate all 18 tables in ONE transaction (FK-safe order validated against actual schema).
- Conflict policy: no `ON CONFLICT DO NOTHING`. Unexpected rows abort with rollback.
- **Source is READ-ONLY**: only SELECT; no INSERT/UPDATE/DELETE/TRUNCATE/ALTER/DROP on localhost.
- UUID preservation, timestamp preservation, PBKDF2 hash preservation (copied verbatim, never printed).
- Post-migration verification: counts, UUID sets, content sets, FK integrity.

## 4. Operator Execution Command

Run these three commands in **your own PowerShell terminal** (not in this chat — the Supabase URL is never sent here):

```powershell
# 1. Set the source (localhost — read-only) and target (Supabase — write) URIs
$env:DATABASE_URI_SOURCE = "postgresql+asyncpg://postgres:postgres@localhost:55432/attendancedash"
$env:DATABASE_URI_TARGET = "postgresql+asyncpg://postgres.zwkdiervvtjalaazscdv:<URL-ENCODED-PASSWORD>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?ssl=require"

# 2. Verify-only (preflight target + source snapshot; no writes)
cd AttendanceDashPro/backend
python scripts/migrate_localhost_to_supabase.py --verify-only

# 3. If verify-only reports that all 18 target tables are empty: execute
python scripts/migrate_localhost_to_supabase.py --execute
```

The `--verify-only` step will:
1. Check production Alembic head is `e1f2a3b4c5d6`
2. Check all 18 tables exist and are empty
3. Capture the source snapshot (read-only)
4. Verify owner identity

If any table has unexpected rows, the tool exits with an error before any write.

## 5. What to Expect After Successful Execution

If `--execute` exits 0, the verification summary will show:

- All 18 source/target table counts match
- UUID sets match
- Content sets match
- FK integrity has zero violations
- Owner identity preserved (2401220100027, ADMIN, PBKDF2 hash)
- Attendance: 165 total, 108 ATTENDED, 57 MISSED
- Academic: 1 session, 1 semester, 1 section, 9 subjects, 720 sessions, 28 timetable, 3 quiz cycles, 18 quiz schedules, 61 events, 43 notifications, 1 preference

## 6. Post-Migration — Manual Production Login Test

After the migration succeeds, the operator must test login manually:

1. Open https://attendance-dash-pro.vercel.app
2. Enter roll number `2401220100027` and the same password that works on localhost
3. Expected: dashboard loads with profile, attendance, subjects, all data matching localhost

## 7. Files

- Created: `backend/scripts/migrate_localhost_to_supabase.py` (the migration tool)
- No application code, models, migrations, API contracts, or configuration changed.
- No commit/push.