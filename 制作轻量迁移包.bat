@echo off
setlocal

set "ROOT=%~dp0"

echo Building lightweight migration package...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\build_migration_package.ps1"

if errorlevel 1 (
  echo.
  echo 打包失败，请检查上方错误信息。
  pause
  exit /b 1
)

echo.
pause
