@echo off
setlocal

set "ROOT=%~dp0"

echo Starting AdFlow AI workbench...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%start_lan.ps1"

echo.
echo App stopped.
pause
