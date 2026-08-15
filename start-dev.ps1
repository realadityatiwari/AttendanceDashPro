# start-dev.ps1
Write-Host "Starting AttendanceDash Pro Development Environment..." -ForegroundColor Cyan

$baseDir = Get-Location

# Verify Prerequisites
if (!(Test-Path "backend\.venv")) {
    Write-Host "Error: backend\.venv not found. Please create the Python virtual environment." -ForegroundColor Red
    exit 1
}

if (!(Test-Path "frontend\node_modules")) {
    Write-Host "Error: frontend\node_modules not found. Please run 'npm install' inside frontend/." -ForegroundColor Red
    exit 1
}

# Start Backend
Write-Host "Starting Backend API on 127.0.0.1:8000..." -ForegroundColor Green
$backendProcess = Start-Process -FilePath "$baseDir\backend\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000" -WorkingDirectory "$baseDir\backend" -PassThru

# Start Frontend
Write-Host "Starting Next.js Frontend on localhost:3100..." -ForegroundColor Green
$frontendProcess = Start-Process -FilePath "npm.cmd" -ArgumentList "run dev" -WorkingDirectory "$baseDir\frontend" -PassThru

Write-Host ""
Write-Host "Services started successfully." -ForegroundColor Cyan
Write-Host "=============================="
Write-Host "Frontend: http://localhost:3100"
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "API Base: http://127.0.0.1:8000/api/v1"
Write-Host "=============================="
Write-Host ""
Write-Host "Run .\stop-dev.ps1 to shut down the development servers safely." -ForegroundColor Yellow
