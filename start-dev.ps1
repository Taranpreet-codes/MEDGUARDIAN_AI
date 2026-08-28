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

# -- 2. Start Django backend -------------------------------------------------

Write-Host ""
Write-Host "[*] Starting Django backend on http://localhost:8000 ..." -ForegroundColor Cyan

if ($redisRunning) {
    $env:REDIS_URL = "redis://localhost:6379/0"
    $env:CELERY_TASK_ALWAYS_EAGER = "False"
} else {
    $env:CELERY_TASK_ALWAYS_EAGER = "True"
}

$djangoProcess = Start-Process -FilePath "python" `
    -ArgumentList "manage.py runserver" `
    -WorkingDirectory $backendDir `
    -PassThru -WindowStyle Normal

# -- 3. Start Celery worker (only when Redis is available) -------------------

if ($redisRunning) {
    Write-Host "[*] Starting Celery worker..." -ForegroundColor Cyan
    $env:REDIS_URL = "redis://localhost:6379/0"
    Start-Process -FilePath "celery" `
        -ArgumentList "-A medguardian worker --loglevel=info -P solo" `
        -WorkingDirectory $backendDir `
        -WindowStyle Normal
} else {
    Write-Host "[i] Celery worker skipped (EAGER mode - background tasks run inline)." -ForegroundColor Yellow
}

# -- 4. Start React frontend -------------------------------------------------

Write-Host ""
Write-Host "[*] Starting React frontend on http://localhost:5173 ..." -ForegroundColor Cyan
Start-Process -FilePath "npm" `
    -ArgumentList "run dev" `
    -WorkingDirectory "$PSScriptRoot\frontend" `
    -WindowStyle Normal

# -- 5. Summary --------------------------------------------------------------

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

# Keep script alive
if ($djangoProcess -and $djangoProcess.Id) {
    Wait-Process -Id $djangoProcess.Id -ErrorAction SilentlyContinue
}
