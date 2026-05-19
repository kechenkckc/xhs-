@echo off
setlocal

set "ROOT=%~dp0"

chcp 65001 >nul
echo Starting AdFlow AI workbench...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%start_lan.ps1"

echo.
echo Launcher finished. The service keeps running in the background.
pause
