param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8797
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Get-PortListeners {
  param([int]$Port)

  return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
}

$connections = Get-PortListeners -Port $Port
foreach ($pidToStop in ($connections.OwningProcess | Sort-Object -Unique)) {
  if ($pidToStop -and $pidToStop -ne $PID) {
    Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
  }
}

$deadline = (Get-Date).AddSeconds(10)
do {
  $connections = Get-PortListeners -Port $Port
  if (-not $connections) {
    python -m uvicorn rpa_mcp_sync.web:app --host $BindHost --port $Port
    exit $LASTEXITCODE
  }
  Start-Sleep -Milliseconds 250
} while ((Get-Date) -lt $deadline)

$owners = foreach ($connection in $connections) {
  $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
  $processName = if ($process) { $process.ProcessName } else { "unknown" }
  "{0} ({1})" -f $connection.OwningProcess, $processName
}

throw "Port $Port is still occupied by: $($owners -join ', ')."
