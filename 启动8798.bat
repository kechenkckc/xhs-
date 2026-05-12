@echo off
setlocal

set "ROOT=%~dp0"

echo Checking port 8798 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$connections = Get-NetTCPConnection -LocalPort 8798 -State Listen -ErrorAction SilentlyContinue; foreach ($pidToStop in ($connections.OwningProcess | Sort-Object -Unique)) { if ($pidToStop) { Write-Host ('Stopping existing PID {0} on port 8798' -f $pidToStop); Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue } }"

echo Starting app at http://127.0.0.1:8798 ...
cd /d "%ROOT%"
python -m uvicorn rpa_mcp_sync.web:app --host 127.0.0.1 --port 8798

echo.
echo App stopped.
pause
