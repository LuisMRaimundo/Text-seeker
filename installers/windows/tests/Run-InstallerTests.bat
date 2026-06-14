@echo off
setlocal EnableExtensions
title text-seeker installer tests
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0InstallWizard.Tests.ps1"
exit /b %ERRORLEVEL%
