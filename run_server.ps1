$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
python -m uvicorn rpa_mcp_sync.web:app --host 127.0.0.1 --port 8797
