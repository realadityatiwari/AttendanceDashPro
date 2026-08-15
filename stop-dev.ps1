# stop-dev.ps1
Write-Host "Stopping AttendanceDash Pro Development Environment..." -ForegroundColor Yellow

function Stop-Port {
    param([int]$Port, [string]$ProcessName)
    
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        $connections | ForEach-Object {
            $processId = $_.OwningProcess
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if ($process -and $process.Name -match $ProcessName) {
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
                Write-Host "Stopped process $($process.Name) (PID: $processId) on port $Port." -ForegroundColor Green
            } else {
                if ($process) {
                    Write-Host "Warning: Port $Port is occupied by an unexpected process: $($process.Name) (PID: $processId). Not terminating." -ForegroundColor Red
                }
            }
        }
    } else {
        Write-Host "No process listening on port $Port." -ForegroundColor Gray
    }
}

# Stop Frontend
Write-Host "Checking Next.js (port 3100)..." -ForegroundColor Cyan
Stop-Port -Port 3100 -ProcessName "node"

# Stop Backend
Write-Host "Checking Uvicorn (port 8000)..." -ForegroundColor Cyan
Stop-Port -Port 8000 -ProcessName "python"

Write-Host "Shutdown complete." -ForegroundColor Green
