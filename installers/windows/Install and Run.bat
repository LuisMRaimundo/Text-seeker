@echo off
setlocal EnableExtensions
title text-seeker

cd /d "%~dp0..\.." || (
  echo ERROR: Cannot find project root.
  pause
  exit /b 1
)
set "ROOT=%CD%"
set "PY=%ROOT%\installers\runtime\windows\python\python.exe"
set "BOOT=%ROOT%\installers\common\bootstrap.py"
set "SETUP=%ROOT%\installers\windows\setup.ps1"
set "LOG=%ROOT%\installers\runtime\windows\install.log"

echo.
echo  *** USE THIS FILE FOR NORMAL INSTALL ***
echo.
echo  text-seeker
echo  ===========
echo.
echo  Project: https://github.com/LuisMRaimundo/Text-seeker
echo.

if not exist "%BOOT%" (
  echo ERROR: bootstrap.py not found at:
  echo   %BOOT%
  echo Download a fresh ZIP from GitHub and run INSTALL.bat from installers\windows
  pause
  exit /b 1
)

if not exist "%PY%" (
  echo First run: installing portable Python and libraries...
  echo Internet connection required. This may take several minutes.
  echo Log: %LOG%
  echo.
  if not exist "%SETUP%" (
    echo ERROR: setup.ps1 not found at:
    echo   %SETUP%
    pause
    exit /b 1
  )
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SETUP%"
  if errorlevel 1 (
    echo.
    echo Setup failed. See log:
    echo   %LOG%
    pause
    exit /b 1
  )
)

if not exist "%PY%" (
  echo ERROR: Portable Python was not installed.
  echo See log: %LOG%
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
