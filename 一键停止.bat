@echo off
setlocal

echo Stopping services on ports 8797, 8798, 5173 and 9222 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = 8797,8798,5173,9222; foreach ($port in $ports) { $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; foreach ($pidToStop in ($connections.OwningProcess | Sort-Object -Unique)) { if ($pidToStop) { $process = Get-Process -Id $pidToStop -ErrorAction SilentlyContinue; $name = if ($process) { $process.ProcessName } else { 'unknown' }; Write-Host ('Stopping PID {0} ({1}) on port {2}' -f $pidToStop, $name, $port); Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue } } }; Start-Sleep -Seconds 1"

echo.
echo Stopped.
pause
