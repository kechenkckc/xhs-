$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$port = 8797
$chromeDebugPort = 9222
$frontend = Join-Path $PSScriptRoot "ad-workbench"
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
  $python = "python"
}

function Get-PortListeners {
  param([int]$Port)

  return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
}

function Stop-PortListeners {
  param([int]$Port)

  $connections = Get-PortListeners -Port $Port
  foreach ($pidToStop in ($connections.OwningProcess | Sort-Object -Unique)) {
    if ($pidToStop -and $pidToStop -ne $PID) {
      $process = Get-Process -Id $pidToStop -ErrorAction SilentlyContinue
      $processName = if ($process) { $process.ProcessName } else { "unknown" }
      Write-Host ("Stopping existing PID {0} ({1}) on port {2}" -f $pidToStop, $processName, $Port)
      Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
    }
  }
}

function Wait-PortFree {
  param(
    [int]$Port,
    [int]$TimeoutSeconds = 10
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    $connections = Get-PortListeners -Port $Port
    if (-not $connections) {
      return $true
    }
    Start-Sleep -Milliseconds 250
  } while ((Get-Date) -lt $deadline)

  return $false
}

function Ensure-PortFree {
  param([int]$Port)

  Stop-PortListeners -Port $Port
  if (Wait-PortFree -Port $Port -TimeoutSeconds 10) {
    return
  }

  $connections = Get-PortListeners -Port $Port
  $owners = foreach ($connection in $connections) {
    $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
    $processName = if ($process) { $process.ProcessName } else { "unknown" }
    "{0} ({1})" -f $connection.OwningProcess, $processName
  }

  throw "Port $Port is still occupied by: $($owners -join ', '). Run 一键停止.bat, close the listed process, or restart the computer."
}

function Get-LanIPv4 {
  $addresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
      $_.IPAddress -notlike "127.*" -and
      $_.IPAddress -notlike "169.254.*" -and
      $_.PrefixOrigin -ne "WellKnown" -and
      $_.AddressState -eq "Preferred"
    } |
    Sort-Object InterfaceMetric, InterfaceIndex

  if ($addresses) {
    return $addresses[0].IPAddress
  }

  return $null
}

function Try-OpenFirewallPort {
  $ruleName = "Ad Workbench LAN $port"
  try {
    $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if (-not $existing) {
      New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $port `
        -Profile Private `
        | Out-Null
    }
    Write-Host "Firewall rule ready: TCP $port (Private network)."
  } catch {
    Write-Host "Could not add firewall rule automatically. If other devices cannot open the page, allow TCP port $port in Windows Defender Firewall." -ForegroundColor Yellow
  }
}

function Test-ChromeDebugPort {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$chromeDebugPort/json/version" -TimeoutSec 2
    return $response.StatusCode -eq 200
  } catch {
    return $false
  }
}

function Find-ChromeExe {
  $candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
  )

  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
      return $candidate
    }
  }

  return $null
}

function Start-PgyChrome {
  if (Test-ChromeDebugPort) {
    Write-Host "Chrome debug port $chromeDebugPort is already connected."
    return
  }

  $chrome = Find-ChromeExe
  if (-not $chrome) {
    Write-Host "Chrome was not found. Click the browser start button in the app, or install Google Chrome." -ForegroundColor Yellow
    return
  }

  $profile = Join-Path $PSScriptRoot "runtime\chrome-pgy-profile"
  New-Item -ItemType Directory -Force -Path $profile | Out-Null

  Write-Host "Starting Chrome debug browser on port $chromeDebugPort ..."
  Start-Process -FilePath $chrome -ArgumentList @(
    "--remote-debugging-port=$chromeDebugPort",
    "--user-data-dir=$profile",
    "https://pgy.xiaohongshu.com/solar/pre-trade/note/kol"
  )

  for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-ChromeDebugPort) {
      Write-Host "Chrome debug browser is ready."
      return
    }
  }

  Write-Host "Chrome was opened, but the debug port is not ready yet. Wait a moment, then refresh the app or click start browser in the app." -ForegroundColor Yellow
}

Write-Host "Checking port $port ..."
Ensure-PortFree -Port $port

if (Test-Path -LiteralPath $frontend) {
  Push-Location -LiteralPath $frontend
  try {
    if (-not (Test-Path -LiteralPath "node_modules")) {
      Write-Host "Installing frontend dependencies..."
      npm install
    }

    Write-Host "Building frontend..."
    npm run build
  } finally {
    Pop-Location
  }
} else {
  Write-Host "Frontend folder not found: $frontend" -ForegroundColor Yellow
}

Try-OpenFirewallPort
Start-PgyChrome

$lanIp = Get-LanIPv4
Write-Host ""
Write-Host "LAN mode is starting."
Write-Host "Local:   http://127.0.0.1:$port/workbench"
if ($lanIp) {
  Write-Host "LAN:     http://$lanIp`:$port/workbench" -ForegroundColor Green
  Write-Host "Devices on the same network can open the LAN address above."
} else {
  Write-Host "LAN IP was not detected. Run ipconfig and use your IPv4 address with port $port." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Keep this window open while others are using the app."
Write-Host "Keep the Chrome window open and log in to Pgy if prompted."

Ensure-PortFree -Port $port

Start-Job -ScriptBlock {
  param($url)
  for ($i = 0; $i -lt 30; $i++) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2
      if ($response.StatusCode -eq 200) {
        Start-Process $url
        return
      }
    } catch {
      Start-Sleep -Seconds 1
    }
  }
} -ArgumentList "http://127.0.0.1:$port/workbench" | Out-Null

& $python -m uvicorn rpa_mcp_sync.web:app --host 0.0.0.0 --port $port
