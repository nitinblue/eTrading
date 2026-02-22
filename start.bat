@echo off
echo ============================================================
echo   Trading CoTrader — Startup
echo ============================================================
echo.

cd /d "%~dp0"

REM Step 1: Check Python venv exists
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python venv not found at .venv\Scripts\python.exe
    echo.
    echo To fix: You need Python 3.12 (NOT 3.13 or 3.14 — hmmlearn won't build).
    echo   1. Download Python 3.12 from https://www.python.org/downloads/release/python-3127/
    echo   2. Install it (check "Add to PATH" is optional, just note the install path)
    echo   3. Open a terminal here and run:
    echo        "C:\Path\To\Python312\python.exe" -m venv .venv
    echo        .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Step 2: Verify Python version is 3.12.x (hmmlearn won't build on 3.13+)
for /f "tokens=2 delims= " %%v in ('".venv\Scripts\python.exe" --version 2^>^&1') do set PYVER=%%v
echo Python version: %PYVER%
echo %PYVER% | findstr /b "3.12" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python %PYVER% detected — this project requires Python 3.12.x
    echo         Python 3.13+ and 3.14+ cannot build hmmlearn (C extension wheels missing).
    echo.
    echo To fix:
    echo   1. Download Python 3.12.7 from https://www.python.org/downloads/release/python-3127/
    echo   2. Delete the .venv folder:  rmdir /s /q .venv
    echo   3. Recreate:  "C:\Path\To\Python312\python.exe" -m venv .venv
    echo   4. Install:   .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo [OK] Python %PYVER%

REM Step 3: Quick dependency check (hmmlearn is the usual failure point)
".venv\Scripts\python.exe" -c "import hmmlearn; import tastytrade; import fastapi; print('[OK] Key dependencies verified')" 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Missing dependencies. Installing from requirements.txt...
    ".venv\Scripts\pip.exe" install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Install failed. Check errors above.
        echo         If hmmlearn fails, you need Python 3.12 (see above).
        pause
        exit /b 1
    )
)

REM Step 4: Check .env file
if not exist ".env" (
    echo [ERROR] .env file not found.
    echo         Copy .env.example to .env and fill in broker credentials.
    echo         (Not needed if running with --no-broker)
    pause
    exit /b 1
)
echo [OK] .env file found

REM Step 5: Check database
if not exist "trading_cotrader.db" (
    echo [WARN] Database not found. Creating...
    ".venv\Scripts\python.exe" -m trading_cotrader.scripts.setup_database
    if errorlevel 1 (
        echo [ERROR] Database setup failed
        pause
        exit /b 1
    )
)
echo [OK] Database exists

REM Step 6: Check if port 8080 is in use
netstat -aon | findstr ":8080.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARN] Port 8080 already in use. Kill the process or use --port 8081
)

echo.
echo ============================================================
echo   All checks passed. Starting server...
echo ============================================================
echo   Backend API: http://localhost:8080
echo   Frontend:    run start-frontend.bat in another terminal
echo.
echo   Press Ctrl+C to stop.
echo ============================================================
echo.

".venv\Scripts\python.exe" -m trading_cotrader.runners.run_workflow --paper --no-broker --web --port 8080
pause
