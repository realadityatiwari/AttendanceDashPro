#Requires -Version 5.1
# stop-dev.ps1
# AttendanceDash Pro — one-command development environment shutdown.
#
# Stops (in reverse order):
#   1. Next.js frontend   (port 3100 — node process)
#   2. FastAPI backend    (port 8080 — python process)
#
# PostgreSQL behaviour:
#   The database container (attendancedashpro_db) is LEFT RUNNING.
#   Stopping it is optional and rarely necessary for development.
#   To also stop PostgreSQL, run:  docker stop attendancedashpro_db
#   Your data is safe — it lives in the named Docker volume
#   attendancedashpro_attendancedash_data and is never removed by this script.
#
# Safety guarantees:
#   - Only processes whose name matches the expected pattern are stopped.
#   - Unrelated Node/Python processes on other ports are never touched.
#   - No 'docker rm', 'docker compose down -v', or volume removal is issued.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

function Write-Step { param([string]$Msg) Write-Host "  $Msg" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Msg) Write-Host "  ✔ $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "  ! $Msg" -ForegroundColor Yellow }

function Stop-DevPort {
    param(
        [int]    $Port,
        [string] $ExpectedProcessPattern,
        [string] $ServiceName
    )

    Write-Step "Stopping $ServiceName (port $Port)..."
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
        Write-Warn "$ServiceName — nothing listening on port $Port"
        return
    }

    foreach ($conn in $conns) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if (-not $proc) { continue }

        if ($proc.Name -match $ExpectedProcessPattern) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            Write-Ok "Stopped $($proc.Name) (PID $($proc.Id)) on port $Port"
        } else {
            Write-Warn "Port $Port is owned by '$($proc.Name)' (PID $($proc.Id)) — not an AttendanceDash process. Skipping."
        }
    }
}

Write-Host ""
Write-Host "  AttendanceDash Pro — Stopping Development Services" -ForegroundColor Yellow
Write-Host "  ────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

# Stop frontend first (Next.js / Node)
Stop-DevPort -Port 3100 -ExpectedProcessPattern "node" -ServiceName "Next.js frontend"

Write-Host ""

# Stop backend (Uvicorn / Python)
Stop-DevPort -Port 8080 -ExpectedProcessPattern "python" -ServiceName "FastAPI backend"

Write-Host ""
Write-Host "  ────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  PostgreSQL : LEFT RUNNING (data preserved in Docker volume)" -ForegroundColor DarkGray
Write-Host "               To stop it: docker stop attendancedashpro_db" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Done. Run .\start-dev.ps1 to start again." -ForegroundColor Green
Write-Host ""
