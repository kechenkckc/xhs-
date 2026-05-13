@echo off
setlocal

echo Stopping services on ports 8797, 8798, 5173 and 9222 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = 8797,8798,5173,9222; foreach ($port in $ports) { $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; foreach ($pidToStop in ($connections.OwningProcess | Sort-Object -Unique)) { if ($pidToStop) { Write-Host ('Stopping PID {0} on port {1}' -f $pidToStop, $port); Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue } } }"

echo.
echo Stopped.
pause
