@echo off
setlocal EnableExtensions
title text-seeker - optional user PATH helper
echo.
echo  OPTIONAL: add private text-seeker tools to your USER PATH
echo  ========================================================
echo.
echo  The installer wizard already offers PATH choices.
echo  This helper is NOT required and does NOT run automatically.
echo.
echo  Only continue if you want tesseract/pdftotext available
echo  in new Command Prompt windows without the launcher.
echo.
pause

cd /d "%~dp0..\.." || exit /b 1
set "ROOT=%CD%"
set "RUN=%ROOT%\installers\runtime\windows"
set "PY=%RUN%\python"
set "TESS=%RUN%\tesseract"
set "POP=%RUN%\poppler\bin"

if not exist "%PY%\python.exe" (
  echo ERROR: Private runtime not installed. Run INSTALL.bat first.
  pause
  exit /b 1
)

for /f "tokens=2*" %%A in ('reg query HKCU\Environment /v PATH 2^>nul') do set "USERPATH=%%B"
if not defined USERPATH set "USERPATH="

echo Adding to user PATH:
echo   %PY%
echo   %PY%\Scripts
echo   %TESS%
echo   %POP%

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$parts = @('%PY%','%PY%\\Scripts','%TESS%','%POP%');" ^
  "$cur = [Environment]::GetEnvironmentVariable('PATH','User');" ^
  "foreach ($p in $parts) { if ($p -and (Test-Path $p) -and ($cur -notlike ('*' + $p + '*'))) { $cur = $p + ';' + $cur } };" ^
  "[Environment]::SetEnvironmentVariable('PATH', $cur, 'User');" ^
  "Write-Host 'User PATH updated. Open a new terminal to use.'"

pause
