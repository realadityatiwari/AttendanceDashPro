#Requires -Version 5.1
# backup_database.ps1
# AttendanceDash Pro — PostgreSQL backup procedure.
#
# Creates a full backup of the development database using pg_dump inside the
# Docker container. The backup file is written to the host filesystem.
#
# Usage:
#   .\backend\scripts\backup_database.ps1 [-OutputDir <path>]
#
# Default output directory: ./backups (relative to repo root)
#
# Production backup strategy:
#   1. Use the same pg_dump command but with production credentials/connection.
#   2. Store backups in a secure, off-host location.
#   3. Test restore periodically (see: restore_database.ps1).
#   4. For schema-only backup: add --schema-only flag in the pg_dump command.
#   5. For data-only backup: add --data-only flag.
#   6. Full backup (default): includes schema + data + custom format (compressed).
#   7. Never use the -c (clean) flag on a production restore targeting a
#      production database unless you intend to drop pre-existing objects.
#
# Retention policy (Phase 17):
#   - Location:       backups/ directory (gitignored); local/server filesystem.
#   - Format:         PostgreSQL custom format (-Fc), compressed, single file.
#   - Daily:          retain the latest 7 (backups/attendancedash_full_<date>*.dump).
#   - Weekly:         retain the latest 4 (manual copy to a weekly archive dir).
#   - Monthly:        retain the latest 3 (manual copy to a monthly archive dir).
#   - Older backups:  may be removed once the retention window is satisfied.
#   - Security:       backups contain the full database; do not commit to Git.
#                     Production backups should be stored in protected/encrypted
#                     storage — handled at the production infrastructure layer.
#   - Verification:   periodically run restore_database.ps1 -TestSwitch against
#                     an isolated container to verify backup integrity.
#   - Automated rotation: not implemented in Phase 17 — a future infrastructure
#                     phase (Phase 18+) may add scheduled rotation.

param(
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

# ── resolve repo root ──────────────────────────────────────────────────
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
if (-not (Test-Path (Join-Path $repoRoot "docker-compose.yml"))) {
    $repoRoot = (Get-Location).Path
    while ($repoRoot -and -not (Test-Path (Join-Path $repoRoot "docker-compose.yml"))) {
        $parent = Split-Path -Parent $repoRoot
        if ($parent -eq $repoRoot) { $repoRoot = $null; break }
        $repoRoot = $parent
    }
}
if (-not $repoRoot) { Write-Host "Cannot locate repo root." -ForegroundColor Red; exit 1 }

if (-not $OutputDir) { $OutputDir = Join-Path $repoRoot "backups" }
if (-not (Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null }

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$filename  = "attendancedash_full_${timestamp}.dump"
$outPath   = Join-Path $OutputDir $filename

Write-Host "Backing up attendancedash to: $outPath" -ForegroundColor Cyan

# pg_dump via docker exec — read-only, no impact on the running database.
# Custom format (-Fc): compressed, supports parallel restore, schema + data.
docker exec attendancedashpro_db pg_dump -U postgres -d attendancedash -Fc -f /tmp/backup_temp.dump
if ($LASTEXITCODE -ne 0) { Write-Host "pg_dump failed." -ForegroundColor Red; exit 1 }

docker cp attendancedashpro_db:/tmp/backup_temp.dump $outPath
if ($LASTEXITCODE -ne 0) { Write-Host "Copy failed." -ForegroundColor Red; exit 1 }

docker exec attendancedashpro_db rm /tmp/backup_temp.dump

$size = (Get-Item $outPath).Length
Write-Host "Backup complete: $outPath ($([math]::Round($size/1KB)) KB)" -ForegroundColor Green