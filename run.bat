@echo off
setlocal EnableDelayedExpansion

:: Anchor working directory to project root
cd /d "%~dp0"
title IDX Financial Statement and Ready-to-Forecast Model Launcher - by abas YP74A

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
echo                        Created by: abas YP74A
echo ========================================================================
echo.
echo Select Mode:
echo   [1] Auto-Fetch Latest 5 Years + Interim Quarters (Recommended)
echo   [2] Custom Online Ticker Search (Enter Specific Years / Range)
echo   [3] Process Local Folder (Offline - Drag & Drop Folder with .xlsx/.zip)
echo   [4] Launch Interactive Web UI (Browser Dashboard & Excel Downloader)
echo   [Q] Quit
echo.
set "MODE="
set /p "MODE=Enter choice [1, 2, 3, 4, or Q, Default: 1]: "
if "!MODE!"=="" set "MODE=1"

if /i "!MODE!"=="Q" goto :exit_app
if /i "!MODE!"=="QUIT" goto :exit_app
if /i "!MODE!"=="EXIT" goto :exit_app

if "!MODE!"=="1" goto :auto_latest_mode
if "!MODE!"=="2" goto :ask_ticker
if "!MODE!"=="3" goto :offline_folder_mode
if "!MODE!"=="4" goto :web_ui_mode
if /i "!MODE!"=="W" goto :web_ui_mode

:web_ui_mode
cls
echo ========================================================================
echo  Launching Interactive Web UI at http://127.0.0.1:8000 ...
echo  Created by: abas YP74A
echo ========================================================================
echo.
"%PYTHON_EXEC%" "%~dp0web_app.py"
goto :main_loop

:auto_latest_mode
echo.
set "TICKER="
set /p "TICKER=Enter Stock Ticker (e.g. BBCA, TLKM, ASII, BBRI) or 'Q' to return: "

if "!TICKER!"=="" (
    echo [!] Ticker cannot be empty. Please try again.
    goto :auto_latest_mode
)

if /i "!TICKER!"=="Q" goto :main_loop
if /i "!TICKER!"=="QUIT" goto :main_loop
if /i "!TICKER!"=="EXIT" goto :main_loop

set "TICKER=!TICKER: =!"
set "LAST_TARGET_DIR=%~dp0downloads\!TICKER!"

echo.
echo ========================================================================
echo  Target: !TICKER! ^| Dynamic Horizon Case A
echo  Probing Latest 5 Completed Annual Years + Available Interim Quarters...
echo ========================================================================
echo.

"%PYTHON_EXEC%" "%~dp0main.py" --ticker "!TICKER!" --latest-interim --ready-to-forecast

if %errorlevel% neq 0 (
    echo.
    echo [!] Process completed with warnings or errors. Check output above.
)
goto :post_menu

:ask_ticker
echo.
set "TICKER="
set /p "TICKER=Enter Stock Ticker (e.g. BBCA, TLKM, ASII, BBRI) or 'Q' to return: "

if "!TICKER!"=="" (
    echo [!] Ticker cannot be empty. Please try again.
    goto :ask_ticker
)

if /i "!TICKER!"=="Q" goto :main_loop
if /i "!TICKER!"=="QUIT" goto :main_loop
if /i "!TICKER!"=="EXIT" goto :main_loop

:: Strip any spaces
set "TICKER=!TICKER: =!"
set "LAST_TARGET_DIR=%~dp0downloads\!TICKER!"

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
goto :post_menu

:offline_folder_mode
echo.
echo ------------------------------------------------------------------------
echo Provide the folder path containing your downloaded financial statements.
echo TIP: You can DRAG AND DROP the folder directly into this window!
echo ------------------------------------------------------------------------
set "FOLDER_PATH="
set /p "FOLDER_PATH=Enter Folder Path (or 'Q' to return): "

if "!FOLDER_PATH!"=="" (
    echo [!] Folder path cannot be empty.
    goto :offline_folder_mode
)

if /i "!FOLDER_PATH!"=="Q" goto :main_loop

:: Strip surrounding quotes and whitespace
set "FOLDER_PATH=!FOLDER_PATH:"=!"
for /f "tokens=* delims= " %%a in ("!FOLDER_PATH!") do set "FOLDER_PATH=%%a"

if not exist "!FOLDER_PATH!" (
    echo.
    echo [!] Directory or file does not exist: "!FOLDER_PATH!"
    echo Please check the path and try again.
    echo.
    pause
    goto :offline_folder_mode
)

set "LAST_TARGET_DIR=!FOLDER_PATH!"

echo.
echo ========================================================================
echo  Scanning and Processing Local Files: "!FOLDER_PATH!"
echo  Generating 3-Statement Normalized Financial Model and Forecast Drivers...
echo ========================================================================
echo.

"%PYTHON_EXEC%" "%~dp0main.py" --input-dir "!FOLDER_PATH!" --ready-to-forecast

if %errorlevel% neq 0 (
    echo.
    echo [!] Process completed with warnings or errors. Check output above.
)
goto :post_menu

:: -----------------------------------------------------------------------------
:: Step 3: Post-Execution Menu
:: -----------------------------------------------------------------------------
:post_menu
echo.
echo ------------------------------------------------------------------------
echo What would you like to do next?
echo   [1] Open Output Folder in Windows Explorer
echo   [2] Open Generated Excel Model (.xlsx)
echo   [3] Run another company or folder
echo   [4] Exit
echo ------------------------------------------------------------------------
set "CHOICE="
set /p "CHOICE=Choice [1-4, Default: 1]: "
if "!CHOICE!"=="" set "CHOICE=1"

if "!CHOICE!"=="1" (
    if defined LAST_TARGET_DIR (
        if exist "!LAST_TARGET_DIR!" (
            start "" explorer.exe "!LAST_TARGET_DIR!"
            echo [*] Output folder opened.
            goto :post_menu
        )
    )
    if defined TICKER (
        if exist "%~dp0downloads\!TICKER!" (
            start "" explorer.exe "%~dp0downloads\!TICKER!"
            echo [*] Output folder opened.
            goto :post_menu
        )
    )
    start "" explorer.exe "%~dp0downloads"
    echo [*] Output folder opened.
    goto :post_menu
)

if "!CHOICE!"=="2" (
    set "LATEST_EXCEL="
    if defined LAST_TARGET_DIR (
        for /f "delims=" %%F in ('dir "!LAST_TARGET_DIR!\*ReadyToForecast*.xlsx" /b /o-d 2^>nul') do (
            if not defined LATEST_EXCEL set "LATEST_EXCEL=!LAST_TARGET_DIR!\%%F"
        )
    )
    if not defined LATEST_EXCEL (
        if defined TICKER (
            for /f "delims=" %%F in ('dir "%~dp0downloads\!TICKER!\*ReadyToForecast*.xlsx" /b /o-d 2^>nul') do (
                if not defined LATEST_EXCEL set "LATEST_EXCEL=%~dp0downloads\!TICKER!\%%F"
            )
        )
    )
    if not defined LATEST_EXCEL (
        for /f "delims=" %%F in ('dir "%~dp0downloads\*ReadyToForecast*.xlsx" /s /b /o-d 2^>nul') do (
            if not defined LATEST_EXCEL set "LATEST_EXCEL=%%F"
        )
    )
    if defined LATEST_EXCEL (
        echo [*] Opening: !LATEST_EXCEL!
        start "" "!LATEST_EXCEL!"
    ) else (
        echo [!] No ReadyToForecast Excel file found. Opening output folder instead...
        if defined LAST_TARGET_DIR (
            start "" explorer.exe "!LAST_TARGET_DIR!"
        ) else (
            start "" explorer.exe "%~dp0downloads"
        )
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
echo ========================================================================
echo  Thank you for using IDX Financial Statement & Modeling Engine!
echo  Created by: abas YP74A
echo ========================================================================
ping 127.0.0.1 -n 2 >nul
exit /b 0
