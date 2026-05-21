@echo off
REM Simple GUI launcher for text-seeker
cd /d "%~dp0"

echo Starting text-seeker GUI...
echo.

REM Try pythonw first (no console window), fallback to python
where pythonw >nul 2>nul
if %errorlevel% == 0 (
    pythonw app.py --gui
) else (
    python app.py --gui
)

if errorlevel 1 (
    echo.
    echo Error occurred. Press any key to exit...
    pause >nul
)
