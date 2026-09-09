#!/usr/bin/env pwsh
<#
.SYNOPSIS
    MedGuardian AI - Local Development Startup Script
    Starts Redis (if available), Django backend, and Celery worker.

.DESCRIPTION
    Detects whether Redis is installed and running. 
    If Redis is available  -> runs full async Celery pipeline.
    If Redis is missing    -> runs Django with CELERY_TASK_ALWAYS_EAGER=True
                             (tasks execute synchronously in-process - fully functional).
#>

$ErrorActionPreference = "Continue"
$backendDir = "$PSScriptRoot\backend"

Write-Host ""
Write-Host "+--------------------------------------------------+" -ForegroundColor Cyan
Write-Host "|         MedGuardian AI - Local Dev Startup       |" -ForegroundColor Cyan
Write-Host "+--------------------------------------------------+" -ForegroundColor Cyan
Write-Host ""

# -- 1. Try to start / detect Redis -----------------------------------------

$redisRunning = $false

# Check if redis-server is on PATH (winget or portable install)
$redisPaths = @(
    "redis-server",
    "C:\Program Files\Redis\redis-server.exe",
    "C:\Redis\redis-server.exe",
    "$PSScriptRoot\redis-win\redis-server.exe"
)

$redisExe = $null
foreach ($p in $redisPaths) {
    if (Get-Command $p -ErrorAction SilentlyContinue) {
        $redisExe = $p
        break
    }
    if (Test-Path $p) {
        $redisExe = $p
        break
    }
}

if ($redisExe) {
    Write-Host "[OK] Redis found at: $redisExe" -ForegroundColor Green
    Write-Host "    Starting Redis server on port 6379..." -ForegroundColor Gray
    Start-Process -FilePath $redisExe -ArgumentList "--port 6379" -WindowStyle Minimized
    Start-Sleep -Seconds 2
    $redisRunning = $true
} else {
    Write-Host "[!] Redis not found. Running in EAGER mode (tasks run synchronously)." -ForegroundColor Yellow
    Write-Host "    Install Redis for full async pipeline:" -ForegroundColor Gray
    Write-Host "    > winget install Redis.Redis" -ForegroundColor White
}

# -- 2. Determine Python & Frontend Executables -------------------------------

$pythonExe = "python"
$venvPython = "$PSScriptRoot\.venv\Scripts\python.exe"
$backendVenvPython = "$backendDir\.venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $pythonExe = $venvPython
    Write-Host "[OK] Using virtual environment Python: $venvPython" -ForegroundColor Green
} elseif (Test-Path $backendVenvPython) {
    $pythonExe = $backendVenvPython
    Write-Host "[OK] Using backend virtual environment Python: $backendVenvPython" -ForegroundColor Green
} else {
    Write-Host "[i] Using global Python ($pythonExe)" -ForegroundColor Gray
}

$npmExe = if (Get-Command "npm.cmd" -ErrorAction SilentlyContinue) { "npm.cmd" } else { "npm" }

# -- 3. Start Django backend -------------------------------------------------

Write-Host ""
Write-Host "[*] Starting Django backend on http://localhost:8000 ..." -ForegroundColor Cyan

if ($redisRunning) {
    $env:REDIS_URL = "redis://localhost:6379/0"
    $env:CELERY_TASK_ALWAYS_EAGER = "False"
} else {
    $env:CELERY_TASK_ALWAYS_EAGER = "True"
}

$djangoProcess = Start-Process -FilePath $pythonExe `
    -ArgumentList "manage.py runserver" `
    -WorkingDirectory $backendDir `
    -PassThru -WindowStyle Normal

# -- 4. Start Celery worker (only when Redis is available) -------------------

$celeryProcess = $null
if ($redisRunning) {
    Write-Host "[*] Starting Celery worker..." -ForegroundColor Cyan
    $env:REDIS_URL = "redis://localhost:6379/0"
    $celeryProcess = Start-Process -FilePath $pythonExe `
        -ArgumentList "-m celery -A medguardian worker --loglevel=info -P solo" `
        -WorkingDirectory $backendDir `
        -PassThru -WindowStyle Normal
} else {
    Write-Host "[i] Celery worker skipped (EAGER mode - background tasks run inline)." -ForegroundColor Yellow
}

# -- 5. Start React frontend -------------------------------------------------

Write-Host ""
Write-Host "[*] Starting React frontend on http://localhost:5173 ..." -ForegroundColor Cyan
$frontendProcess = Start-Process -FilePath $npmExe `
    -ArgumentList "run dev" `
    -WorkingDirectory "$PSScriptRoot\frontend" `
    -PassThru -WindowStyle Normal

# -- 6. Summary --------------------------------------------------------------

Write-Host ""
Write-Host "======================================================" -ForegroundColor DarkGray
Write-Host "  Backend  : http://localhost:8000" -ForegroundColor White
Write-Host "  Frontend : http://localhost:5173" -ForegroundColor White
Write-Host "  API Docs : http://localhost:8000/api/health/" -ForegroundColor White
if ($redisRunning) {
    Write-Host "  Mode     : Full async (Redis + Celery)" -ForegroundColor Green
} else {
    Write-Host "  Mode     : Sync fallback (no Redis - install via winget)" -ForegroundColor Yellow
}
Write-Host "======================================================" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Gray

# Keep script alive and monitor processes
try {
    while ($true) {
        if ($djangoProcess.HasExited) {
            Write-Host "[!] Django process exited with code $($djangoProcess.ExitCode)." -ForegroundColor Red
            break
        }
        if ($frontendProcess.HasExited) {
            Write-Host "[!] Frontend process exited with code $($frontendProcess.ExitCode)." -ForegroundColor Red
            break
        }
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host "`nStopping MedGuardian services..." -ForegroundColor Yellow
    if ($djangoProcess -and -not $djangoProcess.HasExited) { Stop-Process -Id $djangoProcess.Id -Force -ErrorAction SilentlyContinue }
    if ($frontendProcess -and -not $frontendProcess.HasExited) { Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue }
    if ($celeryProcess -and -not $celeryProcess.HasExited) { Stop-Process -Id $celeryProcess.Id -Force -ErrorAction SilentlyContinue }
}
