@echo off
setlocal EnableDelayedExpansion
title Business Architect — Safe Service Shutdown
cd /d "%~dp0"

echo ==============================================================
echo        Business Architect - Safe Service Shutdown
echo ==============================================================
echo(

:: ----------------------------------------------------------------
:: STEP 1: Close Terminal Windows
:: ----------------------------------------------------------------
echo [1/4] Closing backend and frontend service windows...
taskkill /F /T /FI "WINDOWTITLE eq Business Architect - Backend*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq Business Architect - Frontend*" >nul 2>&1

:: ----------------------------------------------------------------
:: STEP 2: Run Application Manager Shutdown
:: ----------------------------------------------------------------
echo [2/4] Terminating registered services...

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

if defined PYTHON_CMD (
    "%PYTHON_CMD%" "%~dp0scripts\app_manager.py" stop
)

:: ----------------------------------------------------------------
:: STEP 3: Backend Port 8000 Process Sweep
:: ----------------------------------------------------------------
echo [3/4] Verifying Backend port 8000...
for /f "tokens=5" %%a in ('netstat -ano -p tcp ^| findstr /R /C:":8000 .*LISTENING"') do (
    set "PID=%%a"
    if defined PID if !PID! gtr 0 (
        taskkill /F /T /PID !PID! >nul 2>&1
        echo [OK] Freed Backend Port 8000 (PID !PID!)
    )
)

:: ----------------------------------------------------------------
:: STEP 4: Frontend Port 5173 Process Sweep
:: ----------------------------------------------------------------
echo [4/4] Verifying Frontend port 5173...
for /f "tokens=5" %%a in ('netstat -ano -p tcp ^| findstr /R /C:":5173 .*LISTENING"') do (
    set "PID=%%a"
    if defined PID if !PID! gtr 0 (
        taskkill /F /T /PID !PID! >nul 2>&1
        echo [OK] Freed Frontend Port 5173 (PID !PID!)
    )
)

:: Clean up PID tracker file
if exist "%~dp0.app_pids" del /q "%~dp0.app_pids" >nul 2>&1

echo(
echo ==============================================================
echo   [SUCCESS] Business Architect services stopped cleanly.
echo             Port 8000 (Backend) and Port 5173 (Frontend) are free.
echo ==============================================================
echo(
echo This window will close automatically in 3 seconds...
ping 127.0.0.1 -n 4 >nul 2>&1
exit /b 0
