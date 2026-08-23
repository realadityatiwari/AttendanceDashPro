# syntax=docker/dockerfile:1

# ────────────────────────────────────────────────────────────────────────
# AttendanceDash Pro — PostgreSQL backup container (Phase 18C)
#
# A small scheduler container that:
#   1. waits for PostgreSQL to be healthy (pg_isready)
#   2. runs `backup.sh` on a fixed interval (BACKUP_INTERVAL seconds)
#   3. verifies the artifact (exists, non-empty, pg_restore --list smoke)
#   4. copies to the configured off-host destination (OFFHOST_TYPE) when set
#   5. prunes old backups (retention) — see retention.sh
#
# Uses the official postgres:16 image so pg_dump/pg_restore versions match
# the database server exactly (PostgreSQL-native tooling, no third-party
# backup software).
#
# Runs as root inside the container so it can manage the mounted backup
# volume; the container itself is isolated on the data-net and holds no
# production credentials beyond what compose injects at runtime.
# ────────────────────────────────────────────────────────────────────────

FROM postgres:16

# Scripts (entrypoint + helpers)
COPY backup.sh retention.sh offhost.sh run.sh /usr/local/bin/backup/
RUN chmod +x /usr/local/bin/backup/*.sh

# Backup staging directory (persistent named volume mounted by compose)
RUN mkdir -p /backups

CMD ["/usr/local/bin/backup/run.sh"]
