@echo off
setlocal EnableExtensions
title text-seeker

cd /d "%~dp0..\.."
set "ROOT=%CD%"
set "PY=%ROOT%\installers\runtime\windows\python\python.exe"
set "BOOT=%ROOT%\installers\common\bootstrap.py"

echo.
echo  text-seeker
echo  ===========
echo.

if not exist "%PY%" (
  echo First run: installing portable Python and libraries...
  echo Internet connection required. This may take several minutes.
  echo.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\installers\windows\setup.ps1"
  if errorlevel 1 (
    echo.
    echo Setup failed. Check your internet connection and try again.
    pause
    exit /b 1
  )
)

if not exist "%PY%" (
  echo ERROR: Portable Python was not installed.
  pause
  exit /b 1
)

"%PY%" "%BOOT%" launch
set "EXITCODE=%ERRORLEVEL%"
echo.
if not "%EXITCODE%"=="0" echo The app exited with code %EXITCODE%.
echo You can close this window.
pause
exit /b %EXITCODE%
