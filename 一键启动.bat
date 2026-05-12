@echo off
setlocal

set "ROOT=%~dp0"
set "FRONTEND=%ROOT%ad-workbench"

echo Starting backend at http://127.0.0.1:8797 ...
start "RPA Backend 8797" powershell -NoExit -ExecutionPolicy Bypass -File "%ROOT%run_server.ps1"

echo Starting frontend at http://127.0.0.1:5173 ...
start "AD Workbench Frontend 5173" /D "%FRONTEND%" cmd /k "if not exist node_modules npm install && npm run dev -- --host 0.0.0.0 --port 5173"

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:5173"

echo.
echo Started. Use 一键停止.bat to stop backend and frontend.
pause
