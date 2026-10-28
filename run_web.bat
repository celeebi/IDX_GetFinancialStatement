@echo off
setlocal EnableDelayedExpansion

:: Anchor working directory to project root
cd /d "%~dp0"
title IDX Financial Statement Web Dashboard - by abas YP74A

set "PYTHON_EXEC="
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXEC=%~dp0.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXEC=python"
)

cls
echo ========================================================================
echo      IDX FINANCIAL STATEMENT & READY-TO-FORECAST MODELING ENGINE
echo                    Interactive Web UI Launcher
echo                        Created by: abas YP74A
echo ========================================================================
echo.
echo [*] Starting Web Dashboard at: http://127.0.0.1:8000
echo [*] Auto-launching your default browser...
echo [*] Press Ctrl+C in this window to stop the server when done.
echo.

"%PYTHON_EXEC%" "%~dp0web_app.py"

pause
