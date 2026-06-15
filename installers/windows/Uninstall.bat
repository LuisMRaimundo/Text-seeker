@echo off
setlocal EnableExtensions
title text-seeker - Uninstall
cd /d "%~dp0..\.." || (
  echo ERROR: Cannot find project root.
  pause
  exit /b 1
)
set "UNINSTALL=%~dp0uninstall.ps1"

echo.
echo  text-seeker uninstaller
echo  =======================
echo.
echo  Removes the private runtime (Python venv, standalone Python, Tesseract,
echo  Poppler, install state and logs). App source files are NOT modified.
echo.

if not exist "%UNINSTALL%" (
  echo ERROR: uninstall.ps1 not found at %UNINSTALL%
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%UNINSTALL%"
set "EXITCODE=%ERRORLEVEL%"
echo.
echo You can close this window.
pause
exit /b %EXITCODE%
