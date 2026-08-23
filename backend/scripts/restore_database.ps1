#Requires -Version 5.1
# restore_database.ps1
# AttendanceDash Pro — PostgreSQL restore procedure.
#
# Restores a full backup (custom format, -Fc) into an existing database.
#
# IMPORTANT:
#   This script targets the LIVE database by default. Data in the target
#   database will be REPLACED. Use the -TestSwitch flag to restore into an
#   isolated temporary container instead.
#
# Usage:
#   .\backend\scripts\restore_database.ps1 -BackupFile <path> [-TestSwitch]

param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile,
    [switch]$TestSwitch
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupFile)) {
    Write-Host "Backup file not found: $BackupFile" -ForegroundColor Red
    exit 1
}

if ($TestSwitch) {
    # Restore into isolated temporary container (never over the working DB).
    Write-Host "Restoring into isolated test container..." -ForegroundColor Cyan
    $containerName = "attendancedash_restore_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    docker run -d --name $containerName -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres `
        -e POSTGRES_DB=attendancedash postgres:16 2>&1 | Out-Null
    Start-Sleep -Seconds 15
    docker cp $BackupFile "${containerName}:/tmp/backup.dump" 2>&1 | Out-Null
    docker exec $containerName pg_restore -U postgres -d attendancedash /tmp/backup.dump 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Restore completed with warnings (expected on fresh container)." -ForegroundColor Yellow
    }
    Write-Host "Restored into temporary container: $containerName" -ForegroundColor Green
    Write-Host "To verify: docker exec -it $containerName psql -U postgres -d attendancedash -c 'SELECT count(*) FROM users'" -ForegroundColor DarkGray
    Write-Host "To clean up: docker stop $containerName; docker rm $containerName" -ForegroundColor DarkGray
} else {
    # Restore into the live development database.
    Write-Host "WARNING: This will REPLACE data in the live database!" -ForegroundColor Red
    Write-Host "Press Ctrl+C to cancel, or Enter to continue..." -ForegroundColor Yellow
    $null = Read-Host
    docker cp $BackupFile attendancedashpro_db:/tmp/backup.dump 2>&1 | Out-Null
    docker exec attendancedashpro_db pg_restore -U postgres -d attendancedash --clean --if-exists /tmp/backup.dump 2>&1
    Write-Host "Restore complete." -ForegroundColor Green
}