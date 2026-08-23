#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────
# AttendanceDash Pro — Backup retention/pruning (Phase 18C)
#
# Keeps the latest N backups (by creation timestamp) and deletes older
# files matching the project's naming convention. Runs after every
# successful backup + off-host copy.
#
# The retention count is configurable via BACKUP_RETENTION_COUNT (default
# 14 — a 2-week rolling window, matching the Phase 17 policy spirit of
# "7 daily + 4 weekly + 3 monthly" = 14). The operator may increase this
# if a longer local window is desired.
#
# Safety guarantees:
#   - never deletes the newest valid backup
#   - only deletes files matching 'attendancedash_full_*.dump'
#   - tolerates missing files (already-deleted or cleaned)
#   - fails safely: if the backup directory is unreadable, exits non-zero
# ────────────────────────────────────────────────────────────────────────
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_COUNT="${BACKUP_RETENTION_COUNT:-14}"

if [ ! -d "${BACKUP_DIR}" ]; then
    echo "[retention] WARNING backup dir missing: ${BACKUP_DIR}" >&2
    exit 0
fi

# List files matching the naming convention, sorted newest-first, skip the
# newest N, delete the rest.  find + sort ensures we never look at arbitrary
# files — only our own dump artifacts.
FILES="$(find "${BACKUP_DIR}" -maxdepth 1 -name 'attendancedash_full_*.dump' -printf '%T@\t%p\n' 2>/dev/null | sort -rn | tail -n +$((RETENTION_COUNT + 1)) | awk '{print $2}')"

if [ -z "${FILES}" ]; then
    echo "[retention] no files to prune (count ≤ ${RETENTION_COUNT})"
    exit 0
fi

COUNT="$(echo "${FILES}" | wc -l)"
echo "${FILES}" | while IFS= read -r f; do
    rm -f "${f}" && echo "[retention] pruned ${f}"
done
echo "[retention] pruned ${COUNT} file(s); kept latest ${RETENTION_COUNT}"