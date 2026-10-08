# Phase 1: Production Readiness Check (Read-Only)

## 1. Migration Verification
**File**: `backend/alembic/versions/c7d8e9f0a1b2_add_event_timetable_entry_ref.py`
- **Revision**: `c7d8e9f0a1b2`
- **Down Revision**: `b9c0d1e2f3a4`
- **Upgrade Operations**:
  1. `op.add_column("academic_events", sa.Column("timetable_entry_id", UUID(as_uuid=True), nullable=True))`
  2. `op.create_foreign_key("fk_academic_events_timetable_entry", "academic_events", "timetable_entries", ["timetable_entry_id"], ["id"])`
- **Downgrade Operations**:
  1. `op.drop_constraint("fk_academic_events_timetable_entry", "academic_events", type_="foreignkey")`
  2. `op.drop_column("academic_events", "timetable_entry_id")`
- **Safety**: Verified. No other operations exist. It is strictly an additive, nullable schema expansion. It safely tolerates existing records (which will default to `NULL`).

## 2. Alembic Chain Verification
- **Local Head**: Running `alembic heads` confirms the repository head is strictly `c7d8e9f0a1b2`.
- **Chain**: The migration securely hooks onto its parent `b9c0d1e2f3a4` (the natural keys migration). There is no branching or missing dependency.

## 3. Deployment Configuration Verification
- **Current Behavior**: `render.yaml` declares a Docker-based web service. The `backend/Dockerfile` builds the image and runs the Uvicorn server (`CMD ["sh", "-c", "exec uvicorn..."]`). Because neither the Dockerfile nor the `render.yaml` specify a migration step, Render simply replaces the running container with the new code, leaving the database untouched.
- **`preDeployCommand` Support**: Yes, Render natively supports the `preDeployCommand` field for `type: web` services (including `runtime: docker`). Render executes this command in a fresh container built from the new Docker image *before* routing traffic to it. This is the exact, intended mechanism for zero-downtime database migrations on Render.

## 4. Operator Instructions: Production Migration Execution
The following steps must be performed by the operator. **Do not proceed to Phase 2 until these are completed.**

**A. Database Snapshot**
1. Log into the database provider (e.g., Supabase dashboard).
2. Trigger a manual backup/snapshot of the production database.

**B. Pre-Migration Verification**
Connect to the production database via `psql` or a SQL client and run:
```sql
SELECT version_num FROM alembic_version;
```
*Expected Output: `b9c0d1e2f3a4`*

**C. Execute Migration**
Run the migration command against the production environment. You can do this via Render's "Shell" tab for the `attendancedash-api` service, or via a remote command:
```bash
alembic upgrade head
```

**D. Post-Migration Schema Verification**
Run the following SQL to confirm the schema change applied correctly:
```sql
-- Check Alembic version
SELECT version_num FROM alembic_version;
-- Expected: c7d8e9f0a1b2

-- Check column existence and type
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'academic_events' 
  AND column_name = 'timetable_entry_id';
-- Expected: timetable_entry_id | uuid | YES
```

**E. Restart Service**
Restart the Render web service to ensure all Uvicorn workers establish fresh connection pools and reload the ORM mapping.

---
**Status**: Ready. Awaiting explicit operator confirmation that the production migration has been executed successfully before proceeding to Phase 2 verification.

