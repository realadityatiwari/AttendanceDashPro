# AttendanceDash Pro — Phase 18C: Backup Automation + Retention + Off-Host Protection

Status: Phase 18C — **COMPLETE** (implementation). Off-host protection is a
**contract with placeholders** — no external destination is configured or
connected yet (production infrastructure does not exist; nothing deployed).

## 1. Backup Architecture

```text
PostgreSQL (data-net, private)
    ↓  pg_dump -Fc (custom format)
Backup container (data-net, scheduled)
    ↓  /backups (persistent named volume `backup_data`)
    ↓  integrity verification (exists + non-empty + pg_restore --list)
    ↓  off-host copy (OFFHOST_TYPE; none by default)
    ↓  retention pruning (BACKUP_RETENTION_COUNT)
```

Components (all under `deploy/backup/`):

| File | Role |
|---|---|
| `Dockerfile` | postgres:16-based scheduler container (pg_dump/pg_restore available) |
| `run.sh` | Entrypoint: lock + wait-for-PostgreSQL + orchestration loop |
| `backup.sh` | pg_dump -Fc + verification (exists, ≥1KB, `pg_restore --list`) |
| `offhost.sh` | Off-host copy contract (none/mount/sftp/s3/custom) |
| `retention.sh` | Prune old backups (keep latest N) |

The backup container lives on `data-net` only, uses the same postgres:16 image
as the database (version-matched pg_dump), and mounts the persistent
`backup_data` volume for staging.

## 2. Configuration Contract

| Variable | Component | Required | Secret? | Default | Purpose |
|---|---|---|---|---|---|
| `POSTGRES_HOST` | backup | yes | no | — | DB service hostname (`postgres`) |
| `POSTGRES_PORT` | backup | no | no | 5432 | DB port |
| `POSTGRES_USER` | backup | yes | no | — | DB user |
| `POSTGRES_PASSWORD` | backup | yes | **yes** | — | DB password (PGPASSWORD env — never argv) |
| `POSTGRES_DB` | backup | yes | no | — | DB name |
| `BACKUP_DIR` | backup | no | no | /backups | Staging dir (volume) |
| `BACKUP_INTERVAL` | backup | no | no | 86400 | Seconds between backups (daily) |
| `BACKUP_RETENTION_COUNT` | backup | no | no | 14 | Local files retained |
| `OFFHOST_TYPE` | backup | no | no | none | none/mount/sftp/s3/custom |
| `OFFHOST_DEST` | backup | when type≠none | maybe | — | Destination (dir, sftp target, s3 URI) |
| `OFFHOST_CMD` | backup | custom only | maybe | — | Custom copy command |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | backup (s3) | s3 only | **yes** | — | Object-storage credentials |

Production values are supplied via `deploy/.env.prod` (gitignored). The compose
file uses `${VAR:?}` for required secrets, so missing values fail fast.

## 3. Retention Policy

- **Policy**: keep the latest **14** backups (`BACKUP_RETENTION_COUNT`),
  delete older ones. At daily frequency this is a ~2-week rolling window
  (matches the Phase 17 "7 daily + 4 weekly + 3 monthly = 14" intent in a
  single simple tier).
- **Naming**: `attendancedash_full_<UTC timestamp>.dump` (only these files are
  ever pruned; arbitrary files in the volume are never touched).
- **Pruning**: runs only after a **successful backup + successful off-host
  copy** (or after a successful backup when OFFHOST_TYPE=none). A failed
  backup or failed off-host copy never triggers pruning (never hides loss).
- **Safety**: the newest backup is always retained; already-missing files are
  tolerated; unreadable backup dir fails loudly.

## 4. Restore Runbook

Tooling: `backend/scripts/restore_database.ps1` (Phase 17, PowerShell; supports
`-TestSwitch` → isolated container). For the production container environment:

1. **Obtain a backup**: newest file in the `backup_data` volume (or off-host
   destination), e.g. `attendancedash_full_20260823_120000.dump`.
2. **Validate**: `pg_restore --list <file>` must succeed (same check backup.sh
   performs).
3. **Isolated target** (recommended): create a throwaway PostgreSQL container,
   restore into it, verify counts, then discard:
   ```powershell
   docker run -d --name restore_test -e POSTGRES_PASSWORD=postgres postgres:16
   docker cp backup.dump restore_test:/tmp/backup.dump
   docker exec restore_test pg_restore -U postgres -d postgres /tmp/backup.dump
   ```
4. **Production restore** (destructive — requires explicit operator action):
   ```bash
   docker compose -f docker-compose.prod.yml exec backup \
     pg_restore -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
     --clean --if-exists /backups/attendancedash_full_<ts>.dump
   ```
   The restore is destructive: existing application data is replaced. Never
   run it against the working database casually. Phase 17's
   `restore_database.ps1 -TestSwitch` provides the same isolation for the
   development database.
5. **Verify**: `SELECT count(*) FROM users;` and spot-check key tables; confirm
   `alembic_version` matches the expected head (`e1f2a3b4c5d6`).
6. **Cleanup**: remove the throwaway container/volume.

## 5. Failure Handling

| Failure | Behavior |
|---|---|
| PostgreSQL unavailable | `run.sh` waits (pg_isready retry every 10s); no backup attempted |
| pg_dump fails | `backup.sh` exits 1, artifact removed, scheduler logs FAILED, no retention |
| Artifact missing / empty / corrupt | `backup.sh` verifies (exists, ≥1KB, `pg_restore --list`); fails loudly |
| Local storage full | pg_dump fails → backup FAILED (no silent success) |
| Off-host destination unavailable | `offhost.sh` exits 1; scheduler logs FAILED; **local backup retained, retention skipped** |
| Retention fails | scheduler logs "retention FAILED — investigate"; backup already safe |
| Lock contention | second cycle skips (never overlapping backups) |

Backups are logged with: start, db/host identity (no secrets), artifact path,
size, validation result, off-host result, retention result, failure reason.
Passwords/credentials are never logged.

## 6. Production Deployment Requirements

**IMPLEMENTED NOW** (this phase):

- Automated scheduled backup (container, interval-based)
- Local persistent staging (`backup_data` volume)
- Integrity verification (pg_restore --list)
- Retention/pruning (latest 14)
- Off-host copy contract (none/mount/sftp/s3/custom)
- Restore tooling + runbook
- Locking, logging, failure exit codes
- Compose wiring (backup service on data-net, healthy-depends on postgres)

**REQUIRES PRODUCTION INFRASTRUCTURE** (not yet deployed — Phase 18D+):

- Actual off-host destination + credentials (set OFFHOST_TYPE/OFFHOST_DEST/
  AWS_* in `deploy/.env.prod`; not configured yet)
- Host/volume provisioning for `backup_data` and any mounted off-host path
- Any monitoring/alerting on backup failure
- Actual restore verification against a production-like environment

No claim of actual off-host protection is made until the destination is
genuinely configured and verified.
