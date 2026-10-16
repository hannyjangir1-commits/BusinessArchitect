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

if not exist "%~dp0client\node_modules" goto :err_no_node_modules

echo [OK] Node.js and frontend dependencies verified.
echo(

:: ----------------------------------------------------------------
:: STEP 2: Start Backend (FastAPI on Port 8000)
:: ----------------------------------------------------------------
echo [2/5] Checking backend service (port 8000)...
"%PYTHON_CMD%" "%~dp0scripts\app_manager.py" check-backend >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo [INFO] Backend is already running and healthy on port 8000.
    goto :frontend_check
)

:: Check if port is occupied by an alien process
netstat -ano -p tcp | findstr /R /C:":8000 .*LISTENING" >nul 2>&1
if !ERRORLEVEL! equ 0 goto :err_port_8000_conflict

echo [INFO] Starting FastAPI backend on http://127.0.0.1:8000...
start "AI Business Architect - Backend" /d "%~dp0server" cmd /k ""%PYTHON_CMD%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

:frontend_check
echo(

:: ----------------------------------------------------------------
:: STEP 3: Start Frontend (Vite on Port 5173)
:: ----------------------------------------------------------------
echo [3/5] Checking frontend service (port 5173)...
"%PYTHON_CMD%" "%~dp0scripts\app_manager.py" check-frontend >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo [INFO] Frontend is already running on port 5173.
    goto :wait_for_ready
)

netstat -ano -p tcp | findstr /R /C:":5173 .*LISTENING" >nul 2>&1
if !ERRORLEVEL! equ 0 goto :err_port_5173_conflict

echo [INFO] Starting Vite frontend on http://127.0.0.1:5173...
start "AI Business Architect - Frontend" /d "%~dp0client" cmd /k "npm run dev -- --host 127.0.0.1 --port 5173"

:wait_for_ready
echo(

:: ----------------------------------------------------------------
:: STEP 4: Wait for Readiness (Health Check Polling)
:: ----------------------------------------------------------------
echo [4/5] Verifying service readiness...
"%PYTHON_CMD%" "%~dp0scripts\app_manager.py" wait-ready
if !ERRORLEVEL! neq 0 goto :err_wait_timeout

echo(

:: ----------------------------------------------------------------
:: STEP 5: Open in Google Chrome
:: ----------------------------------------------------------------
echo [5/5] Launching Google Chrome...

set "CHROME_PATH="
for /f "delims=" %%c in ('"%PYTHON_CMD%" "%~dp0scripts\app_manager.py" find-chrome 2^>nul') do (
    set "CHROME_PATH=%%c"
)

if defined CHROME_PATH if exist "!CHROME_PATH!" (
    echo [INFO] Found Chrome at: "!CHROME_PATH!"
    start "" "!CHROME_PATH!" "http://localhost:5173"
    goto :done_launch
)

start chrome "http://localhost:5173" >nul 2>&1
if !ERRORLEVEL! equ 0 goto :done_launch

echo [NOTICE] Google Chrome was not found at standard installation locations.
echo Opening application in your default browser...
start "http://localhost:5173"
echo(
echo If preferred, open Google Chrome manually and navigate to:
echo   http://localhost:5173

:done_launch
echo(
echo ==============================================================
echo        AI Business Architect - Application is Ready!
echo ==============================================================
echo(
echo   * Main Application:   http://localhost:5173
echo   * Enterprise Admin:   http://localhost:5173/admin/login
echo   * Backend API Docs:   http://127.0.0.1:8000/docs
echo   * Health Endpoint:    http://127.0.0.1:8000/api/health
echo(
echo --------------------------------------------------------------
echo   Initial Super Admin Provisioning:
echo     Configured via ADMIN_BOOTSTRAP_ENABLED in .env
echo     (See .env.example and README.md for instructions)
echo --------------------------------------------------------------
echo   To cleanly shut down the application, double-click:
echo     stop_app.bat
echo ==============================================================
echo(
echo Press any key to close this launcher window (services will stay running)...
pause >nul
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

:err_no_node_modules
echo [ERROR] Frontend node_modules directory was not found.
echo(
echo To install frontend dependencies, open a terminal and run:
echo   cd /d "%~dp0client"
echo   npm install
echo(
pause
exit /b 1

:err_port_8000_conflict
echo [ERROR] Port 8000 is occupied by another process that is not responding as our backend.
echo Please close the conflicting application or run stop_app.bat first.
echo(
pause
exit /b 1

:err_port_5173_conflict
echo [ERROR] Port 5173 is occupied by another process.
echo Please close the conflicting application or run stop_app.bat first.
echo(
pause
exit /b 1

:err_wait_timeout
echo(
echo [ERROR] Services failed to respond within the expected timeframe.
echo(
echo Troubleshooting:
echo   1. Check the "AI Business Architect - Backend" window for tracebacks.
echo   2. Check the "AI Business Architect - Frontend" window for Vite build errors.
echo   3. Run stop_app.bat before trying again.
echo(
pause
exit /b 1
