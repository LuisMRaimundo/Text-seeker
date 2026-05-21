@echo off
REM text-seeker — run unit tests
cd /d "%~dp0"
python -m unittest discover -s tests -v
if errorlevel 1 exit /b 1
echo.
echo All tests passed.
