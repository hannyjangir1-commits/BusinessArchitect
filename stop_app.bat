@echo off
setlocal EnableDelayedExpansion
title AI Business Architect — Stop Services
cd /d "%~dp0"

echo ==============================================================
echo        AI Business Architect - Safe Service Shutdown
echo ==============================================================
echo(

set "PYTHON_CMD="
if exist "%~dp0server\venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0server\venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%~dp0server\.venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0server\.venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
if not defined PYTHON_CMD (
    where python >nul 2>&1
    if !ERRORLEVEL! equ 0 set "PYTHON_CMD=python"
)

if defined PYTHON_CMD goto :use_python
goto :use_native

:use_python
"%PYTHON_CMD%" "%~dp0scripts\app_manager.py" stop
goto :end_shutdown

:use_native
echo [INFO] Performing native port-targeted process termination...
set /a STOPPED=0

:: Backend Port 8000
for /f "tokens=5" %%a in ('netstat -ano -p tcp ^| findstr /R /C:":8000 .*LISTENING"') do (
    set "PID=%%a"
    if defined PID if !PID! gtr 0 (
        taskkill /FI "PID eq !PID!" /FI "IMAGENAME eq python.exe" /F /T >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            echo [OK] Stopped backend service (PID !PID!)
            set /a STOPPED+=1
        )
    )
)

:: Frontend Port 5173
for /f "tokens=5" %%a in ('netstat -ano -p tcp ^| findstr /R /C:":5173 .*LISTENING"') do (
    set "PID=%%a"
    if defined PID if !PID! gtr 0 (
        taskkill /FI "PID eq !PID!" /FI "IMAGENAME eq node.exe" /F /T >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            echo [OK] Stopped frontend service (PID !PID!)
            set /a STOPPED+=1
        )
    )
)

if exist "%~dp0.app_pids" del /q "%~dp0.app_pids" >nul 2>&1

if %STOPPED% equ 0 (
    echo [INFO] AI Business Architect is not currently running.
    echo        No active services found on port 8000 or 5173.
) else (
    echo(
    echo [SUCCESS] Successfully stopped %STOPPED% AI Business Architect process(es).
)

:end_shutdown
echo(
echo ==============================================================
echo Press any key to close this window...
pause >nul
