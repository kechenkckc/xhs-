$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$connections = Get-NetTCPConnection -LocalPort 8797 -State Listen -ErrorAction SilentlyContinue
foreach ($pidToStop in ($connections.OwningProcess | Sort-Object -Unique)) {
  if ($pidToStop -and $pidToStop -ne $PID) {
    Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
  }
}
python -m uvicorn rpa_mcp_sync.web:app --host 127.0.0.1 --port 8797
