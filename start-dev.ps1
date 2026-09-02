#Requires -Version 5.1
# start-dev.ps1
# AttendanceDash Pro — one-command local development startup.
#
# Starts the complete stack in dependency order:
#   1. PostgreSQL (Docker container: attendancedashpro_db, port 55432)
#   2. FastAPI backend (127.0.0.1:8080)
#   3. Next.js frontend (localhost:3100)
#
# Usage:
#   .\start-dev.ps1
#
# Prerequisites:
#   - Docker Desktop must be running
#   - backend\.venv must exist   (python -m venv backend\.venv)
#   - frontend\node_modules must exist  (cd frontend && npm install)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── helpers ────────────────────────────────────────────────────────────────────

function Write-Step { param([string]$Msg) Write-Host "  $Msg" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Msg) Write-Host "  ✔ $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "  ! $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host "  ✘ $Msg" -ForegroundColor Red }

function Test-PortListening {
    # Pure TCP connectivity check. Used for PostgreSQL readiness polling only.
    # Does NOT filter stale sockets — correct for DB readiness where we want
    # to know if the port actually accepts connections right now.
    param([string]$TargetHost, [int]$Port)
    try {
        $tcp = [System.Net.Sockets.TcpClient]::new()
        $ar  = $tcp.BeginConnect($TargetHost, $Port, $null, $null)
        $ok  = $ar.AsyncWaitHandle.WaitOne(500)
        if ($ok) { $tcp.EndConnect($ar) }
        $tcp.Close()
        return $ok
    } catch {
        return $false
    }
}

function Get-ListenerPids {
    # Returns all PIDs with a LISTENING socket on $Port via netstat.
    # More reliable than Get-NetTCPConnection on Windows, which silently omits
    # entries when multiple processes bind the same port (known PS/WMI issue).
    param([int]$Port)
    $result = [System.Collections.Generic.List[int]]::new()
    try {
        $lines = netstat -ano -p TCP 2>$null
        foreach ($line in $lines) {
            if ($line -match ":\s*$Port\s+\S+\s+LISTENING\s+(\d+)") {
                $result.Add([int]$Matches[1])
            }
        }
    } catch { }
    return $result
}

function Test-ServiceRunning {
    # Returns $true if at least one live process matching $Pattern owns a
    # LISTENING socket on $Port. Uses netstat for complete enumeration.
    # Immune to: stale sockets, Get-NetTCPConnection omission, StrictMode nulls.
    param([int]$Port, [string]$Pattern)
    try {
        foreach ($lPid in (Get-ListenerPids -Port $Port)) {
            try {
                $proc = Get-Process -Id $lPid -ErrorAction SilentlyContinue
                if ($null -ne $proc -and $proc.Name -match $Pattern) { return $true }
            } catch { }
        }
    } catch { }
    return $false
}

function Get-OwningProcessName {
    # Returns the name of the first live process owning a LISTEN socket on
    # $Port, or 'unknown'. Uses netstat for complete enumeration.
    param([int]$Port)
    try {
        foreach ($lPid in (Get-ListenerPids -Port $Port)) {
            try {
                $proc = Get-Process -Id $lPid -ErrorAction SilentlyContinue
                if ($null -ne $proc -and $proc.Name -ne '') { return $proc.Name }
            } catch { }
        }
    } catch { }
    return 'unknown'
}

# ── resolve repo root robustly ─────────────────────────────────────────────────

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $repoRoot -or -not (Test-Path (Join-Path $repoRoot "docker-compose.yml"))) {
    # Fallback: walk up from current location looking for docker-compose.yml
    $candidate = (Get-Location).Path
    while ($candidate -and -not (Test-Path (Join-Path $candidate "docker-compose.yml"))) {
        $parent = Split-Path -Parent $candidate
        if ($parent -eq $candidate) { $candidate = $null; break }
        $candidate = $parent
    }
    if (-not $candidate) {
        Write-Fail "Cannot locate repository root (docker-compose.yml not found)."
        exit 1
    }
    $repoRoot = $candidate
}

$backendDir  = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$pythonExe   = Join-Path $backendDir ".venv\Scripts\python.exe"
$npmCmd      = "npm.cmd"

# ── header ─────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "  AttendanceDash Pro — Development Environment" -ForegroundColor White
Write-Host "  ─────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

# ── prerequisite checks ────────────────────────────────────────────────────────

Write-Step "Checking prerequisites..."

# Python venv
if (-not (Test-Path $pythonExe)) {
    Write-Fail "Python venv not found at: $pythonExe"
    Write-Host "    Run:  python -m venv backend\.venv  (then pip install -r backend\requirements.txt)" -ForegroundColor DarkGray
    exit 1
}

# Node modules
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Fail "frontend\node_modules not found."
    Write-Host "    Run:  cd frontend ; npm install" -ForegroundColor DarkGray
    exit 1
}

# Docker CLI
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Fail "Docker CLI not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop"
    exit 1
}

# Docker daemon
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker daemon is not running. Please start Docker Desktop and try again."
    exit 1
}

Write-Ok "Prerequisites OK"
Write-Host ""

# ── 1. PostgreSQL ──────────────────────────────────────────────────────────────

$dbContainer   = "attendancedashpro_db"
$dbHost        = "127.0.0.1"
$dbPort        = 55432
$dbReadyMsg    = ""

Write-Step "PostgreSQL ($dbContainer) ..."

$containerState = docker inspect --format "{{.State.Status}}" $dbContainer 2>&1
if ($LASTEXITCODE -ne 0) {
    # Container does not exist — create it via compose (safe: uses named volume defined in compose file)
    Write-Warn "Container not found. Creating via docker compose (data volume preserved)..."
    Push-Location $repoRoot
    docker compose up -d attendancedash_db 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    Pop-Location
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "docker compose up failed. Check docker-compose.yml and Docker Desktop."
        exit 1
    }
} elseif ($containerState -eq "running") {
    Write-Ok "Already running — reusing"
    $dbReadyMsg = "(was already running)"
} else {
    Write-Step "Container exists but is stopped — starting..."
    docker start $dbContainer 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "docker start $dbContainer failed."
        exit 1
    }
}

# Poll PostgreSQL readiness (TCP) — up to 30 seconds
if (-not $dbReadyMsg) {
    $maxWaitSec = 30
    $elapsed    = 0
    Write-Step "Waiting for PostgreSQL to accept connections on $dbHost`:$dbPort ..."
    while (-not (Test-PortListening -TargetHost $dbHost -Port $dbPort)) {
        if ($elapsed -ge $maxWaitSec) {
            Write-Fail "PostgreSQL did not become ready within ${maxWaitSec}s."
            Write-Host "    Check:  docker logs $dbContainer" -ForegroundColor DarkGray
            exit 1
        }
        Start-Sleep -Milliseconds 500
        $elapsed += 1
    }
    Write-Ok "PostgreSQL ready on $dbHost`:$dbPort (waited ${elapsed}s)"
}

Write-Host ""

# ── 2. FastAPI backend ─────────────────────────────────────────────────────────

$backendPort    = 8080
$backendHost    = "127.0.0.1"
$backendStarted = $false

Write-Step "FastAPI backend (port $backendPort) ..."

if (Test-ServiceRunning -Port $backendPort -Pattern "python") {
    Write-Ok "Already running — reusing (Python process on port $backendPort)"
} elseif (($liveOwner = Get-OwningProcessName -Port $backendPort) -ne 'unknown') {
    # A live unrelated process owns this port
    Write-Fail "Port $backendPort is occupied by an unrelated process: $liveOwner"
    Write-Host "    Free the port or stop that process, then retry." -ForegroundColor DarkGray
    exit 1
} else {
    $logOut = Join-Path $backendDir "backend_out.log"
    $logErr = Join-Path $backendDir "backend_err.log"

    # The backend's DATABASE_URI MUST come from backend/.env (the intended
    # local asyncpg configuration), never from a stale inherited shell
    # variable. pydantic-settings gives environment variables higher
    # precedence than the .env file, so an inherited DATABASE_URI (e.g. a
    # leftover Supabase bare postgresql:// value baked into a long-lived
    # terminal session) would override backend/.env and crash the async
    # engine with the sync psycopg2 driver (InvalidRequestError). Strip it
    # from the child environment for this launch and restore it afterward.
    $savedDatabaseUri = $env:DATABASE_URI
    Remove-Item Env:DATABASE_URI -ErrorAction SilentlyContinue
    try {
        $backendProcess = Start-Process `
            -FilePath $pythonExe `
            -ArgumentList "-m uvicorn app.main:app --host $backendHost --port $backendPort" `
            -WorkingDirectory $backendDir `
            -PassThru `
            -WindowStyle Hidden `
            -RedirectStandardOutput $logOut `
            -RedirectStandardError $logErr
    } finally {
        if ($null -ne $savedDatabaseUri) {
            $env:DATABASE_URI = $savedDatabaseUri
        } else {
            Remove-Item Env:DATABASE_URI -ErrorAction SilentlyContinue
        }
    }

    Write-Step "Waiting for backend to bind to port $backendPort ..."
    $maxWaitSec = 10
    $elapsed = 0
    while (-not (Test-PortListening -TargetHost $backendHost -Port $backendPort)) {
        if ($backendProcess.HasExited) {
            Write-Fail "Backend process crashed immediately (Exit Code: $($backendProcess.ExitCode))."
            if (Test-Path $logErr) {
                Write-Host "    Last error output:" -ForegroundColor DarkGray
                Get-Content $logErr -Tail 5 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
            }
            exit 1
        }
        if ($elapsed -ge $maxWaitSec) {
            Write-Fail "Backend failed to bind to port $backendPort within ${maxWaitSec}s."
            if (Test-Path $logErr) {
                Write-Host "    Last error output:" -ForegroundColor DarkGray
                Get-Content $logErr -Tail 5 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
            }
            exit 1
        }
        Start-Sleep -Milliseconds 500
        $elapsed += 1
    }

    $backendStarted = $true
    Write-Ok "Launched and listening (PID $($backendProcess.Id))"
}

Write-Host ""

# ── 3. Next.js frontend ────────────────────────────────────────────────────────

$frontendPort    = 3100
$frontendStarted = $false

Write-Step "Next.js frontend (port $frontendPort) ..."

if (Test-ServiceRunning -Port $frontendPort -Pattern "node") {
    Write-Ok "Already running — reusing (Node process on port $frontendPort)"
} elseif (($liveOwner = Get-OwningProcessName -Port $frontendPort) -ne 'unknown') {
    # A live unrelated process owns this port
    Write-Fail "Port $frontendPort is occupied by an unrelated process: $liveOwner"
    Write-Host "    Free the port or stop that process, then retry." -ForegroundColor DarkGray
    exit 1
} else {
    $frontendProcess = Start-Process `
        -FilePath $npmCmd `
        -ArgumentList "run dev" `
        -WorkingDirectory $frontendDir `
        -PassThru `
        -WindowStyle Hidden
    $frontendStarted = $true
    Write-Ok "Launched (PID $($frontendProcess.Id))"
}

Write-Host ""

# ── status summary ─────────────────────────────────────────────────────────────

Write-Host "  AttendanceDash Pro Development Environment" -ForegroundColor White
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ("  PostgreSQL : RUNNING  $dbHost`:$dbPort  $dbReadyMsg").TrimEnd() -ForegroundColor Green
Write-Host "  Backend   : RUNNING  $backendHost`:$backendPort" -ForegroundColor Green
Write-Host "  Frontend  : RUNNING  localhost:$frontendPort" -ForegroundColor Green
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Frontend : http://localhost:$frontendPort" -ForegroundColor Cyan
Write-Host "  Backend  : http://$backendHost`:$backendPort" -ForegroundColor Cyan
Write-Host "  API      : http://$backendHost`:$backendPort/api/v1" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Stop with:  .\stop-dev.ps1" -ForegroundColor Yellow
Write-Host ""
