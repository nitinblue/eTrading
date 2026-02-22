@echo off
echo ============================================================
echo   Trading CoTrader — Frontend
echo ============================================================
echo.

cd /d "%~dp0\frontend"

REM Check node_modules
if not exist "node_modules" (
    echo [WARN] node_modules not found. Installing...
    pnpm install
    if errorlevel 1 (
        echo [ERROR] pnpm install failed. Make sure pnpm is installed: npm install -g pnpm
        pause
        exit /b 1
    )
)
echo [OK] node_modules found

echo.
echo Starting frontend at http://localhost:5173
echo Press Ctrl+C to stop.
echo.

pnpm dev
pause
