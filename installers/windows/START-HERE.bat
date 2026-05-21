@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0Install and Run.bat"
exit /b %ERRORLEVEL%
