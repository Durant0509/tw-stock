@echo off
REM ============================================================
REM  tw-stock war room - Windows one-click setup
REM  Usage: put this .bat in the repo folder, double-click it
REM ============================================================
cd /d "%~dp0"
echo.
echo ============================================================
echo   tw-stock war room - one-click setup
echo ============================================================
echo.

REM --- Detect Python command (py or python) ---
set PYCMD=
py --version >nul 2>&1
if not errorlevel 1 set PYCMD=py
if "%PYCMD%"=="" (
    python --version >nul 2>&1
    if not errorlevel 1 set PYCMD=python
)
if "%PYCMD%"=="" (
    echo [X] Python not found. Install from:
    echo     https://www.python.org/downloads/
    echo     Remember to check "Add Python to PATH"
    pause
    exit /b 1
)
echo [OK] Python found: %PYCMD%
%PYCMD% --version

REM --- Check Git ---
git --version >nul 2>&1
if errorlevel 1 (
    echo [X] Git not found. Install from: https://git-scm.com/download/win
    pause
    exit /b 1
)
echo [OK] Git found
echo.

REM --- Step 1: first full data pull ---
echo ============================================================
echo   Step 1/2: First full data pull (about 1-2 hours, once only)
echo   Data stored locally in data\ folder, NOT uploaded to GitHub
echo ============================================================
echo.
set /p GO="Press Enter to start pulling data (or close window to cancel)... "
%PYCMD% bootstrap.py

echo.
echo ============================================================
echo   Step 2/2: Create daily auto-update schedule (15:30 and 21:30)
echo ============================================================
echo.

REM --- Resolve full path to python exe for scheduler ---
set PYEXE=%PYCMD%
for /f "delims=" %%i in ('where %PYCMD% 2^>nul') do set PYEXE=%%i

set REPO=%~dp0
schtasks /create /tn "tw-stock-update-1530" /tr "\"%PYEXE%\" \"%REPO%update.py\"" /sc daily /st 15:30 /f
schtasks /create /tn "tw-stock-update-2130" /tr "\"%PYEXE%\" \"%REPO%update.py\"" /sc daily /st 21:30 /f

echo.
echo ============================================================
echo   Done! System is set up.
echo.
echo   - Auto-updates every day at 15:30 and 21:30
echo   - Keep the computer on and it runs by itself
echo   - Open the web page to see the latest:
echo     https://durant0509.github.io/tw-stock/warroom.html
echo.
echo   (First auto-update pushes to GitHub and may ask you to
echo    log in - enter your account and token once.)
echo ============================================================
pause
