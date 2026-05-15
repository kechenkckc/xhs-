@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"

echo ========================================
echo AdFlow AI Workbench - environment setup
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\install_environment.ps1"

if errorlevel 1 (
  echo.
  echo Setup failed. Check the messages above, then retry after network access is available.
  if /i not "%CI%"=="true" pause
  exit /b 1
)

echo.
if /i not "%CI%"=="true" pause
