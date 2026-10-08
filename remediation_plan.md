# Production Incident Remediation Plan

## 1. Proven Root Cause
The deployed backend code (FastAPI) expects the `timetable_entry_id` column to exist on the `academic_events` table (introduced for occurrence-specific cancellation handling). However, the production PostgreSQL database does not have this column because the corresponding Alembic database migration was not executed during deployment. When any endpoint queries `AcademicEvent` (e.g., Dashboard summary, Calendar, Quiz Eligibility, Events), SQLAlchemy throws a `ProgrammingError: column academic_events.timetable_entry_id does not exist`.

## 2. Exact Migration Responsible
Alembic migration: `c7d8e9f0a1b2_add_event_timetable_entry_ref.py`

## 3. Exact Schema Change Required
- Add column `timetable_entry_id` of type `UUID` (nullable) to the `academic_events` table.
- Add foreign key constraint `fk_academic_events_timetable_entry` from `academic_events.timetable_entry_id` to `timetable_entries.id`.

## 4. Why Multiple Pages Failed
The Dashboard (summary), Calendar, Quiz Schedule (eligibility), and Events pages all share a dependency on the backend event-fetching logic. They all eventually query `AcademicEvent` records. Because SQLAlchemy's ORM model for `AcademicEvent` now maps `timetable_entry_id`, every `SELECT` query against that table includes the missing column, causing a fatal database error across all dependent endpoints, while the rest of the app (like frontend shells and `/student/me`) remains functional.

## 5. Why this is related to the Events occurrence-specific work
The recent Events occurrence-specific work added the `timetable_entry_id` field to strictly link event cancellations (like `CLASS_CANCELLED`) to their exact scheduled timetable occurrence. This code was merged and deployed, but its accompanying database schema change was not applied to production.

## 6. Why reverting frontend/backend code is NOT the correct fix
The code deployment itself is correct and fully verified. The issue is purely operational: a missed database schema migration. Reverting the code would undo validated business logic, require complex git reversions, and simply delay the inevitable need to run the migration. Applying the safe, additive migration is the correct forward-moving fix.

## 7. Why c7d8e9f0a1b2 is safe/unsafe based on actual migration contents
The migration is **100% safe** to run against existing production rows. 
- It adds a new column with `nullable=True`, meaning existing `academic_events` rows will simply default to `NULL` without violating any constraints.
- The business logic explicitly handles `NULL` values for legacy cancellations.
- No data is modified or deleted. 

## 8. Current production migration state
The production database is currently stuck at revision `b9c0d1e2f3a4_add_evt004_unique_natural_keys.py`, which is the immediate parent of `c7d8e9f0a1b2`.

## 9. Exact safe production migration procedure
**Important: Do not skip the backup.**
1. **Take a Pre-Migration Backup**: Trigger a manual PostgreSQL database backup/snapshot via the Supabase dashboard (or Render, depending on the DB host).
2. **Verify Current State**: Connect to the production database and run `SELECT * FROM alembic_version;` to confirm the current head is `b9c0d1e2f3a4`.
3. **Execute Migration**: Use the Render CLI, Render dashboard shell, or SSH access to run the migration command against the production database:
   ```bash
   alembic upgrade head
   ```
   *(This will apply `c7d8e9f0a1b2`)*
4. **Verify Schema**: Check that the column exists: 
   ```sql
   SELECT timetable_entry_id FROM academic_events LIMIT 1;
   ```
5. **Restart Backend**: Since the backend failed continuously, restart the Render web service to clear any poisoned connection pools or cached schema states.

## 10. Permanent Deployment-Process Fix
The root cause of the missing migration is that Render deployments pull new code and restart the container, but do not automatically run Alembic. The `backend/Dockerfile` explicitly avoids running migrations at startup. 
To fix this permanently, the `render.yaml` must be updated to include a `preDeployCommand` that runs migrations *before* the new code is swapped in:
```yaml
services:
  - type: web
    name: attendancedash-api
    # ...
    preDeployCommand: "alembic upgrade head"
```

## 11. Verification Checklist (Post-Remediation)
- [ ] Backend `/health` returns 200 OK.
- [ ] Backend `/api/v1/student/me` returns 200 OK.
- [ ] Backend `/api/v1/events` returns 200 OK (No 500 error).
- [ ] Backend `/api/v1/calendar` returns 200 OK.
- [ ] Backend `/api/v1/dashboard/summary` returns 200 OK.
- [ ] Frontend Dashboard loads without "Failed to load dashboard" error.
- [ ] Frontend Calendar displays correctly.
- [ ] Frontend Quiz Schedule resolves eligibility without errors.
- [ ] Frontend Events page loads the event list.

