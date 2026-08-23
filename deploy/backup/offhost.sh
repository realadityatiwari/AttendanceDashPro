#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────
# AttendanceDash Pro — Off-host backup copy contract (Phase 18C)
#
# Copies the just-created backup artifact to an off-host destination.
#
# The architecture supports multiple destination types through the
# OFFHOST_TYPE variable (default: none = local staging only). The
# off-host step is executed ONLY after a verified local backup exists.
#
# Supported OFFHOST_TYPE values:
#   "none"     — no off-host copy (local persistent volume only). This is
#                the default until production infrastructure exists.
#   "mount"    — copy to a host-mounted/object-mounted directory
#                (OFFHOST_DEST is a directory path).
#   "sftp"     — copy via SFTP/SCP (OFFHOST_DEST = user@host:path;
#                authentication via SSH keys mounted by the operator).
#   "s3"       — copy via the aws CLI (OFFHOST_DEST = s3://bucket/path;
#                AWS_* credentials provided at runtime by the operator).
#   "custom"   — OFFHOST_CMD is an arbitrary command; the artifact path is
#                appended as the final argument.
#
# Failure behavior: if OFFHOST_TYPE is configured but the copy fails, the
# script exits non-zero so the scheduler records a failure. Local backup
# retention is NOT pruned on off-host failure (see run.sh ordering).
#
# No real credentials are embedded here. All values come from the runtime
# environment (deploy/.env.prod), which is gitignored.
# ────────────────────────────────────────────────────────────────────────
set -euo pipefail

BACKUP_FILE="${1:?backup file path required}"
OFFHOST_TYPE="${OFFHOST_TYPE:-none}"

case "${OFFHOST_TYPE}" in
  none)
    echo "[offhost] OFFHOST_TYPE=none — local staging only (no off-host copy)"
    exit 0
    ;;
  mount)
    : "${OFFHOST_DEST:?OFFHOST_DEST required when OFFHOST_TYPE=mount}"
    mkdir -p "${OFFHOST_DEST}"
    cp -v "${BACKUP_FILE}" "${OFFHOST_DEST}/"
    ;;
  sftp)
    : "${OFFHOST_DEST:?OFFHOST_DEST required when OFFHOST_TYPE=sftp}"
    scp -q "${BACKUP_FILE}" "${OFFHOST_DEST}" || {
        echo "[offhost] FAILED sftp copy" >&2; exit 1; }
    ;;
  s3)
    : "${OFFHOST_DEST:?OFFHOST_DEST required when OFFHOST_TYPE=s3}"
    : "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID required when OFFHOST_TYPE=s3}"
    : "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY required when OFFHOST_TYPE=s3}"
    aws s3 cp "${BACKUP_FILE}" "${OFFHOST_DEST}/" || {
        echo "[offhost] FAILED s3 copy" >&2; exit 1; }
    ;;
  custom)
    : "${OFFHOST_CMD:?OFFHOST_CMD required when OFFHOST_TYPE=custom}"
    ${OFFHOST_CMD} "${BACKUP_FILE}" || {
        echo "[offhost] FAILED custom copy" >&2; exit 1; }
    ;;
  *)
    echo "[offhost] ERROR unknown OFFHOST_TYPE='${OFFHOST_TYPE}'" >&2
    exit 1
    ;;
esac

echo "[offhost] copied ${BACKUP_FILE} (type=${OFFHOST_TYPE})"