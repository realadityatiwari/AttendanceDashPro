#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────
# AttendanceDash Pro — Backup scheduler entrypoint (Phase 18C)
#
# Runs on a fixed interval (BACKUP_INTERVAL seconds, default 86400 = daily)
# and orchestrates the backup workflow with strict ordering and locking:
#
#   1. acquire a lock (prevents overlapping backups)
#   2. wait for PostgreSQL to be reachable
#   3. backup.sh            — pg_dump -Fc + verification
#   4. offhost.sh           — off-host copy (only if OFFHOST_TYPE set)
#   5. retention.sh         — prune old backups (after successful off-host)
#
# Locking: a lockfile with the scheduler PID. If a previous run is still
# in progress, this run skips (never stacks overlapping backups).
#
# The container lifecycle is defined by Docker Compose (`restart:
# unless-stopped`); the scheduler itself runs in the foreground.
# ────────────────────────────────────────────────────────────────────────
set -euo pipefail

# Required configuration (fail fast — never silently run without a target)
: "${POSTGRES_HOST:?POSTGRES_HOST is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"

BACKUP_INTERVAL="${BACKUP_INTERVAL:-86400}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
LOCK_FILE="${BACKUP_DIR}/.backup.lock"

mkdir -p "${BACKUP_DIR}"

echo "[scheduler] starting (interval=${BACKUP_INTERVAL}s, offhost=${OFFHOST_TYPE:-none})"

while true; do
    # Wait for PostgreSQL to become reachable before attempting a backup.
    until pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER}" >/dev/null 2>&1; do
        echo "[scheduler] PostgreSQL not ready; retrying in 10s..."
        sleep 10
    done

    # Locking: skip if a previous backup is still running.
    if [ -f "${LOCK_FILE}" ]; then
        echo "[scheduler] previous backup still in progress; skipping this cycle"
        sleep "${BACKUP_INTERVAL}"
        continue
    fi
    trap 'rm -f "${LOCK_FILE}"' EXIT
    echo "$$" > "${LOCK_FILE}"

    echo "[scheduler] backup cycle start $(date -u +%Y-%m-%dT%H:%M:%SZ)"

    if /usr/local/bin/backup/backup.sh; then
        # Only run off-host + retention after a verified local backup.
        BACKUP_FILE="$(ls -t ${BACKUP_DIR}/attendancedash_full_*.dump 2>/dev/null | head -1)"
        if [ -n "${BACKUP_FILE}" ]; then
            if /usr/local/bin/backup/offhost.sh "${BACKUP_FILE}"; then
                # Prune only after a successful off-host copy (retention
                # after a failed off-host copy could hide backup loss).
                /usr/local/bin/backup/retention.sh || {
                    echo "[scheduler] retention FAILED — investigate" >&2; }
            else
                echo "[scheduler] off-host copy FAILED — local backup retained, retention skipped" >&2
            fi
        fi
    else
        echo "[scheduler] backup FAILED — no retention run" >&2
    fi

    rm -f "${LOCK_FILE}"
    trap - EXIT
    echo "[scheduler] backup cycle end $(date -u +%Y-%m-%dT%H:%M:%SZ)"

    sleep "${BACKUP_INTERVAL}"
done