@echo off
setlocal EnableDelayedExpansion
title Business Architect — Launcher
cd /d "%~dp0"

echo ==============================================================
echo   Business Architect - Enterprise Blueprint Launcher
echo ==============================================================
echo(

:: ----------------------------------------------------------------
:: STEP 1: Detect Python & Virtual Environment
:: ----------------------------------------------------------------
echo [1/5] Checking prerequisites...

set "PYTHON_CMD="
if exist "%~dp0server\venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0server\venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%~dp0server\.venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0server\.venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
if not defined PYTHON_CMD (
    where python >nul 2>&1
    if !ERRORLEVEL! equ 0 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    where py >nul 2>&1
    if !ERRORLEVEL! equ 0 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD goto :err_no_python

:: Validate Python backend dependencies and environment
"%PYTHON_CMD%" "%~dp0scripts\app_manager.py" check-prereqs
if !ERRORLEVEL! neq 0 goto :err_backend_deps

:: ----------------------------------------------------------------
:: Check Node.js and npm
:: ----------------------------------------------------------------
where node >nul 2>&1
if !ERRORLEVEL! neq 0 goto :err_no_node

where npm >nul 2>&1
if !ERRORLEVEL! neq 0 goto :err_no_npm

if not exist "%~dp0client\node_modules" (
    echo [NOTICE] Client node_modules missing. Installing frontend dependencies...
    cd /d "%~dp0client"
    call npm install
    cd /d "%~dp0"
)

echo [OK] Node.js and frontend dependencies verified.
echo(

:: ----------------------------------------------------------------
:: FAST PATH: If both backend & frontend are already running healthy,
:: open the landing page immediately and skip startup steps.
:: ----------------------------------------------------------------
"%PYTHON_CMD%" "%~dp0scripts\app_manager.py" check-backend >nul 2>&1
set "B_HEALTHY=!ERRORLEVEL!"
"%PYTHON_CMD%" "%~dp0scripts\app_manager.py" check-frontend >nul 2>&1
set "F_HEALTHY=!ERRORLEVEL!"

if !B_HEALTHY! equ 0 if !F_HEALTHY! equ 0 (
    echo [INFO] Business Architect is already running and healthy.
    goto :open_browser_step
)

:: ----------------------------------------------------------------
:: STEP 2: Start Backend (FastAPI on Port 8000)
:: ----------------------------------------------------------------
echo [2/5] Checking backend service (port 8000)...
if !B_HEALTHY! equ 0 (
    echo [INFO] Backend is already running and healthy on http://127.0.0.1:8000.
    goto :frontend_check
)

:: If port 8000 is occupied by an unresponsive process, clean it up
netstat -ano -p tcp | findstr /R /C:":8000 .*LISTENING" >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo [NOTICE] Port 8000 is occupied by an inactive process. Cleaning up...
    for /f "tokens=5" %%a in ('netstat -ano -p tcp ^| findstr /R /C:":8000 .*LISTENING"') do (
        taskkill /F /T /PID %%a >nul 2>&1
    )
    timeout /t 1 /nobreak >nul
)

echo [INFO] Starting FastAPI backend on http://127.0.0.1:8000...
start "Business Architect - Backend" /d "%~dp0server" cmd /k ""%PYTHON_CMD%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

:frontend_check
echo(

:: ----------------------------------------------------------------
:: STEP 3: Start Frontend (Vite on Port 5173)
:: ----------------------------------------------------------------
echo [3/5] Checking frontend service (port 5173)...
if !F_HEALTHY! equ 0 (
    echo [INFO] Frontend is already running and ready on http://127.0.0.1:5173.
    goto :wait_for_ready
)

:: If port 5173 is occupied by an inactive process, clean it up
netstat -ano -p tcp | findstr /R /C:":5173 .*LISTENING" >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo [NOTICE] Port 5173 is occupied by an inactive process. Cleaning up...
    for /f "tokens=5" %%a in ('netstat -ano -p tcp ^| findstr /R /C:":5173 .*LISTENING"') do (
        taskkill /F /T /PID %%a >nul 2>&1
    )
    timeout /t 1 /nobreak >nul
)

echo [INFO] Starting Vite frontend on http://127.0.0.1:5173...
start "Business Architect - Frontend" /d "%~dp0client" cmd /k "npm run dev -- --host 127.0.0.1 --port 5173"

:wait_for_ready
echo(

:: ----------------------------------------------------------------
:: STEP 4: Wait for Readiness (Health Check Polling)
:: ----------------------------------------------------------------
echo [4/5] Verifying service readiness...
"%PYTHON_CMD%" "%~dp0scripts\app_manager.py" wait-ready
if !ERRORLEVEL! neq 0 goto :err_wait_timeout

:open_browser_step
echo(

:: ----------------------------------------------------------------
:: STEP 5: Always Open Landing Page in Browser Every Time Clicked
:: ----------------------------------------------------------------
echo [5/5] Opening Business Architect Landing Page in your browser...

set "BROWSER_LAUNCHED="

:: 1. Primary launcher via helper (system default browser / Chrome)
"%PYTHON_CMD%" "%~dp0scripts\app_manager.py" open-browser "http://localhost:5173"
if !ERRORLEVEL! equ 0 set "BROWSER_LAUNCHED=1"

:: 2. Fallback via PowerShell Start-Process
if not defined BROWSER_LAUNCHED (
    powershell -NoProfile -Command "Start-Process 'http://localhost:5173'" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo [OK] Opened landing page in browser: http://localhost:5173
        set "BROWSER_LAUNCHED=1"
    )
)

:: 3. Native Windows Shell fallback
if not defined BROWSER_LAUNCHED (
    start "" "http://localhost:5173"
    echo [OK] Opened landing page in browser: http://localhost:5173
    set "BROWSER_LAUNCHED=1"
)

:done_launch
echo(
echo ==============================================================
echo        Business Architect - Application is Ready!
echo ==============================================================
echo(
echo   * Landing Page:       http://localhost:5173
echo   * Enterprise Admin:   http://localhost:5173/admin
echo   * Backend API Docs:   http://127.0.0.1:8000/docs
echo   * Health Endpoint:    http://127.0.0.1:8000/api/health
echo(
echo --------------------------------------------------------------
echo   Initial Super Admin Credentials (Local Dev):
echo     Username: HannyAdmin
echo     Password: HannyAdmin
echo --------------------------------------------------------------
echo   To cleanly shut down all services, double-click:
echo     stop_app.bat
echo ==============================================================
echo(
echo Services remain active in the background.
echo This launcher window will close automatically in 3 seconds...
ping 127.0.0.1 -n 4 >nul 2>&1
exit /b 0

:: ----------------------------------------------------------------
:: Error Handlers
:: ----------------------------------------------------------------
:err_no_python
echo [ERROR] Python was not found on your system PATH or in a virtual environment.
echo(
echo Please install Python 3.10 or higher from:
echo   https://www.python.org/downloads/
echo During installation, be sure to check "Add Python to PATH".
echo(
pause
exit /b 1

:err_backend_deps
echo(
echo [ERROR] Backend dependency validation failed.
echo Please review the instructions above to resolve missing requirements.
echo(
pause
exit /b 1

:err_no_node
echo [ERROR] Node.js is not installed or not in your system PATH.
echo(
echo Please install Node.js (version 18 or higher) from:
echo   https://nodejs.org/
echo(
pause
exit /b 1

:err_no_npm
echo [ERROR] npm was not found on your system PATH.
echo Please ensure Node.js and npm are installed correctly.
echo(
pause
exit /b 1

:err_wait_timeout
echo(
echo [ERROR] Services failed to respond within the expected timeframe.
echo(
echo Troubleshooting:
echo   1. Check the "Business Architect - Backend" window for tracebacks.
echo   2. Check the "Business Architect - Frontend" window for Vite build errors.
echo   3. Run stop_app.bat before trying again.
echo(
pause
exit /b 1
