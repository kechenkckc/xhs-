$ErrorActionPreference = "Stop"

try {
  chcp 65001 | Out-Null
} catch {
}
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

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
  $defaultProfile = Join-Path $profile "Default"
  foreach ($sessionFile in @("Last Session", "Last Tabs", "Current Session", "Current Tabs")) {
    $sessionPath = Join-Path $defaultProfile $sessionFile
    if (Test-Path -LiteralPath $sessionPath) {
      Remove-Item -LiteralPath $sessionPath -Force -ErrorAction SilentlyContinue
    }
  }
  $preferencesPath = Join-Path $defaultProfile "Preferences"
  if (Test-Path -LiteralPath $preferencesPath) {
    try {
      $preferences = Get-Content -LiteralPath $preferencesPath -Raw -Encoding UTF8 | ConvertFrom-Json
      if (-not $preferences.profile) {
        $preferences | Add-Member -MemberType NoteProperty -Name profile -Value ([pscustomobject]@{}) -Force
      }
      $preferences.profile | Add-Member -MemberType NoteProperty -Name exit_type -Value "Normal" -Force
      $preferences.profile | Add-Member -MemberType NoteProperty -Name exited_cleanly -Value $true -Force
      if (-not $preferences.session) {
        $preferences | Add-Member -MemberType NoteProperty -Name session -Value ([pscustomobject]@{}) -Force
      }
      $preferences.session | Add-Member -MemberType NoteProperty -Name restore_on_startup -Value 0 -Force
      $preferences | ConvertTo-Json -Depth 64 -Compress | Set-Content -LiteralPath $preferencesPath -Encoding UTF8
    } catch {}
  }

  Write-Host "Starting Chrome debug browser on port $chromeDebugPort ..."
  Start-Process -FilePath $chrome -ArgumentList @(
    "--remote-debugging-port=$chromeDebugPort",
    "--user-data-dir=$profile",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-session-crashed-bubble",
    "--hide-crash-restore-bubble",
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

function Start-DetachedServer {
  param(
    [string]$PythonExe,
    [int]$Port
  )

  $runtimeDir = Join-Path $PSScriptRoot "runtime"
  New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

  $stdoutLog = Join-Path $runtimeDir "lan-server.out.log"
  $stderrLog = Join-Path $runtimeDir "lan-server.err.log"
  $pidFile = Join-Path $runtimeDir "lan-server.pid"

  foreach ($path in @($stdoutLog, $stderrLog)) {
    if (Test-Path -LiteralPath $path) {
      Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
  }

  $process = Start-Process -FilePath $PythonExe -ArgumentList @(
    "-m",
    "uvicorn",
    "rpa_mcp_sync.web:app",
    "--host",
    "0.0.0.0",
    "--port",
    $Port
  ) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog

  Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ASCII
  return $process
}

Write-Host "Checking port $port ..."
Ensure-PortFree -Port $port

$frontendDistIndex = Join-Path $frontend "dist\index.html"
$frontendPackage = Join-Path $frontend "package.json"
if (Test-Path -LiteralPath $frontendPackage) {
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
} elseif (Test-Path -LiteralPath $frontendDistIndex) {
  Write-Host "Using packaged frontend: $frontendDistIndex"
} else {
  Write-Host "Frontend build not found: $frontendDistIndex" -ForegroundColor Yellow
}

Try-OpenFirewallPort
Start-PgyChrome

$lanIp = Get-LanIPv4
Write-Host ""
Write-Host "LAN mode is starting."
Write-Host "本机访问:   http://127.0.0.1:$port/workbench"
if ($lanIp) {
  Write-Host "局域网访问: http://$lanIp`:$port/workbench" -ForegroundColor Green
  Write-Host "同一局域网内的其他电脑可直接访问上面的地址。" -ForegroundColor Green
} else {
  Write-Host "未检测到局域网 IP，请运行 ipconfig 后使用你的 IPv4 地址访问端口 $port。" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Keep this window open while others are using the app."
Write-Host "Keep the Chrome window open and log in to Pgy if prompted."
Write-Host "Server will keep running after this window is closed." -ForegroundColor Green

Start-DetachedServer -PythonExe $python -Port $port | Out-Null

$serverUrl = "http://127.0.0.1:$port/workbench"
$serverReady = $false
for ($i = 0; $i -lt 30; $i++) {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $serverUrl -TimeoutSec 2
    if ($response.StatusCode -eq 200) {
      Start-Process $serverUrl | Out-Null
      $serverReady = $true
      break
    }
  } catch {
    Start-Sleep -Seconds 1
  }
}

if (-not $serverReady) {
  throw "后台服务启动失败，请查看 runtime\\lan-server.err.log 和 runtime\\lan-server.out.log。"
}
