param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8797
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
foreach ($pidToStop in ($connections.OwningProcess | Sort-Object -Unique)) {
  if ($pidToStop -and $pidToStop -ne $PID) {
    Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
  }
}
python -m uvicorn rpa_mcp_sync.web:app --host $BindHost --port $Port
