@echo off
setlocal EnableDelayedExpansion

:: Anchor working directory to project root
cd /d "%~dp0"
title IDX Financial Statement and Ready-to-Forecast Model Launcher

:: -----------------------------------------------------------------------------
:: Step 1: Detect Python & Virtual Environment
:: -----------------------------------------------------------------------------
set "PYTHON_EXEC="

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXEC=%~dp0.venv\Scripts\python.exe"
    goto :python_found
)

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo ========================================================================
    echo  [ERROR] Python is not detected on your system.
    echo  Please install Python 3.10+ from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    echo ========================================================================
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================================================
echo  [NOTICE] Virtual environment not found.
echo  Creating virtual environment and installing dependencies automatically...
echo ========================================================================
echo.
python -m venv "%~dp0.venv"
if %errorlevel% neq 0 (
    echo [!] Failed to create virtual environment. Falling back to system Python...
    set "PYTHON_EXEC=python"
    goto :python_found
)

echo [*] Installing dependencies from requirements.txt...
"%~dp0.venv\Scripts\pip.exe" install -r "%~dp0requirements.txt"
set "PYTHON_EXEC=%~dp0.venv\Scripts\python.exe"

:python_found

:: -----------------------------------------------------------------------------
:: Step 2: Main Interactive Loop
:: -----------------------------------------------------------------------------
:main_loop
cls
echo ========================================================================
echo      IDX FINANCIAL STATEMENT AND READY-TO-FORECAST MODEL LAUNCHER
echo            PT Bursa Efek Indonesia (idx.co.id) Automation
echo ========================================================================
echo.

:ask_ticker
set "TICKER="
set /p "TICKER=Enter Stock Ticker (e.g. BBCA, TLKM, ASII, BBRI) or 'Q' to quit: "

if "!TICKER!"=="" (
    echo [!] Ticker cannot be empty. Please try again.
    goto :ask_ticker
)

if /i "!TICKER!"=="Q" goto :exit_app
if /i "!TICKER!"=="QUIT" goto :exit_app
if /i "!TICKER!"=="EXIT" goto :exit_app

:: Strip any spaces
set "TICKER=!TICKER: =!"

echo.
set "START_YEAR="
set /p "START_YEAR=Enter Start Year (e.g. 2020) [Default: 2020]: "
if "!START_YEAR!"=="" set "START_YEAR=2020"

set "END_YEAR="
set /p "END_YEAR=Enter End Year   (e.g. 2024) [Default: 2024]: "
if "!END_YEAR!"=="" set "END_YEAR=2024"

echo.
echo ========================================================================
echo  Target: !TICKER! ^| Horizon: !START_YEAR! - !END_YEAR!
echo  Generating 3-Statement Normalized Financial Model and Forecast Drivers...
echo ========================================================================
echo.

"%PYTHON_EXEC%" "%~dp0main.py" --ticker "!TICKER!" --start-year !START_YEAR! --end-year !END_YEAR! --ready-to-forecast

if %errorlevel% neq 0 (
    echo.
    echo [!] Process completed with warnings or errors. Check output above.
)

:: -----------------------------------------------------------------------------
:: Step 3: Post-Execution Menu
:: -----------------------------------------------------------------------------
:post_menu
echo.
echo ------------------------------------------------------------------------
echo What would you like to do next?
echo   [1] Open Output Folder in Windows Explorer
echo   [2] Open Generated Excel Model (.xlsx)
echo   [3] Run another company
echo   [4] Exit
echo ------------------------------------------------------------------------
set "CHOICE="
set /p "CHOICE=Choice [1-4, Default: 1]: "
if "!CHOICE!"=="" set "CHOICE=1"

if "!CHOICE!"=="1" (
    if exist "%~dp0downloads\!TICKER!" (
        start "" explorer.exe "%~dp0downloads\!TICKER!"
    ) else (
        start "" explorer.exe "%~dp0downloads"
    )
    echo [*] Output folder opened.
    goto :post_menu
)

if "!CHOICE!"=="2" (
    set "LATEST_EXCEL="
    for /f "delims=" %%F in ('dir "%~dp0downloads\!TICKER!\*ReadyToForecast*.xlsx" /b /o-d 2^>nul') do (
        if not defined LATEST_EXCEL set "LATEST_EXCEL=%~dp0downloads\!TICKER!\%%F"
    )
    if defined LATEST_EXCEL (
        echo [*] Opening: !LATEST_EXCEL!
        start "" "!LATEST_EXCEL!"
    ) else (
        echo [!] No ReadyToForecast Excel file found for !TICKER!. Opening folder instead...
        start "" explorer.exe "%~dp0downloads\!TICKER!"
    )
    goto :post_menu
)

if "!CHOICE!"=="3" (
    goto :main_loop
)

if "!CHOICE!"=="4" (
    goto :exit_app
)
if /i "!CHOICE!"=="Q" (
    goto :exit_app
)

echo [!] Invalid selection, please enter 1, 2, 3, or 4.
goto :post_menu

:exit_app
echo.
echo Thank you for using IDX Financial Statement and Modeling Engine!
ping 127.0.0.1 -n 2 >nul
exit /b 0
