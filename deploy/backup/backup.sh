#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────
# AttendanceDash Pro — PostgreSQL backup (Phase 18C)
#
# Creates a full backup of the application database using PostgreSQL-native
# pg_dump in custom format (-Fc). Custom format is chosen because:
#   - compressed (smaller artifacts)
#   - supports selective/parallel restore
#   - verified by pg_restore --list (structural integrity smoke check)
#   - restore via pg_restore (not psql), matching the Phase 17 restore tooling
#
# Secrets are NEVER passed as CLI arguments. Credentials arrive through
# environment variables (PGPASSWORD is honored by libpq without appearing
# in the process list).
#
# Exit codes:
#   0  success (artifact created + verified)
#   1  any failure (pg_dump, verification, missing required config)
# ────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── required configuration (compose injects these; missing = fail loudly) ──
: "${POSTGRES_HOST:?POSTGRES_HOST is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"

# ── naming convention (also used by retention.sh) ───────────────────────
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/attendancedash_full_${TIMESTAMP}.dump"

echo "[backup] start db=${POSTGRES_DB} host=${POSTGRES_HOST}:${POSTGRES_PORT} dest=${BACKUP_FILE}"

# 1. Create the dump (custom format, compressed). PGPASSWORD is exported so
#    the password never appears in argv/process listings.
export PGPASSWORD="${POSTGRES_PASSWORD}"
if ! pg_dump \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    -Fc \
    -f "${BACKUP_FILE}"; then
    echo "[backup] FAILED pg_dump" >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi
unset PGPASSWORD

# 2. Integrity verification: artifact exists, non-empty, and pg_restore can
#    parse its TOC (a corrupted/truncated dump fails --list).
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "[backup] FAILED artifact missing" >&2
    exit 1
fi
SIZE="$(stat -c %s "${BACKUP_FILE}")"
if [ "${SIZE}" -lt 1024 ]; then
    echo "[backup] FAILED artifact suspiciously small (${SIZE} bytes)" >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi
if ! pg_restore --list "${BACKUP_FILE}" >/dev/null 2>&1; then
    echo "[backup] FAILED pg_restore --list verification" >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi

echo "[backup] complete file=${BACKUP_FILE} size=${SIZE}"
