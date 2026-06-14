@echo off
setlocal EnableExtensions
title text-seeker

cd /d "%~dp0..\.." || (
  echo ERROR: Cannot find project root.
  pause
  exit /b 1
)
set "ROOT=%CD%"
set "BOOT=%ROOT%\installers\common\bootstrap.py"
set "SETUP=%ROOT%\installers\windows\setup.ps1"
set "STATE=%ROOT%\installers\runtime\windows\install_state.json"
set "LOG=%ROOT%\installers\runtime\windows\install.log"

echo.
echo  text-seeker Windows Installer / Launcher
echo  ========================================
echo.

if not exist "%BOOT%" (
  echo ERROR: bootstrap.py not found.
  pause
  exit /b 1
)

if not exist "%STATE%" (
  echo No installation configuration found.
  echo Opening the text-seeker installer...
  echo You can choose Python, OCR tools, and PATH options.
  echo Log: %LOG%
  echo.
  if not exist "%SETUP%" (
    echo ERROR: setup.ps1 not found at %SETUP%
    pause
    exit /b 1
  )
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SETUP%"
  if errorlevel 1 (
    echo.
    echo Installer failed or was cancelled.
    echo See log: %LOG%
    pause
    exit /b 1
  )
)

if not exist "%STATE%" (
  echo ERROR: install_state.json was not created.
  echo See log: %LOG%
  pause
  exit /b 1
)

for /f "delims=" %%P in ('powershell.exe -NoProfile -Command "(Get-Content -Raw '%STATE%' | ConvertFrom-Json).python_path"') do set "PY=%%P"

if not exist "%PY%" (
  echo ERROR: Configured Python not found: %PY%
  echo Re-run the installer: %SETUP%
  pause
  exit /b 1
)

"%PY%" "%BOOT%" launch
set "EXITCODE=%ERRORLEVEL%"
echo.
if not "%EXITCODE%"=="0" (
  echo The app exited with code %EXITCODE%.
  echo See log: %LOG%
  echo Run diagnostics: "%PY%" "%BOOT%" doctor
)
echo You can close this window.
pause
exit /b %EXITCODE%
