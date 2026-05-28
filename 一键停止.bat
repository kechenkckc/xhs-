@echo off
setlocal

echo Stopping services on ports 8797, 8798, 5173 and 9222 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$chrome = Get-NetTCPConnection -LocalPort 9222 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if ($chrome) { try { Write-Host 'Closing Chrome debug browser gracefully via CDP'; $version = Invoke-RestMethod -Uri 'http://127.0.0.1:9222/json/version' -TimeoutSec 2; if ($version.webSocketDebuggerUrl) { $ws = [System.Net.WebSockets.ClientWebSocket]::new(); $uri = [Uri]$version.webSocketDebuggerUrl; $ws.ConnectAsync($uri, [Threading.CancellationToken]::None).Wait(2000) | Out-Null; $message = @{id=1; method='Browser.close'} | ConvertTo-Json -Compress; $payload = [Text.Encoding]::UTF8.GetBytes($message); $seg = [ArraySegment[byte]]::new($payload); $ws.SendAsync($seg, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, [Threading.CancellationToken]::None).Wait(2000) | Out-Null; $ws.Dispose() } } catch {}; Start-Sleep -Seconds 2 }; $ports = 8797,8798,5173,9222; foreach ($port in $ports) { $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; foreach ($pidToStop in ($connections.OwningProcess | Sort-Object -Unique)) { if ($pidToStop) { $process = Get-Process -Id $pidToStop -ErrorAction SilentlyContinue; $name = if ($process) { $process.ProcessName } else { 'unknown' }; Write-Host ('Stopping PID {0} ({1}) on port {2}' -f $pidToStop, $name, $port); Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue } } }; Start-Sleep -Seconds 1"

echo.
echo Stopped.
pause
