$ErrorActionPreference = "Stop"

$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$root = $root.Path
$requirements = Join-Path $root "requirements-runtime.txt"
$venvPy = Join-Path $root ".venv\Scripts\python.exe"

function Has-Command {
  param([string]$Name)
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Install-WithWinget {
  param(
    [string]$Id,
    [string]$Name
  )

  if (-not (Has-Command "winget")) {
    Write-Host "winget was not found. Please install $Name manually, then rerun this script." -ForegroundColor Yellow
    return $false
  }

  Write-Host "Installing $Name with winget ..."
  winget install --id $Id -e --accept-package-agreements --accept-source-agreements
  return $LASTEXITCODE -eq 0
}

function Invoke-PythonCommand {
  param(
    [string]$PythonCommand,
    [string[]]$Arguments
  )

  if ($PythonCommand -eq "py -3") {
    & py -3 @Arguments
    return $LASTEXITCODE
  }

  & $PythonCommand @Arguments
  return $LASTEXITCODE
}

Write-Host "Package root: $root"

$chromeCandidates = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
)

$chrome = $chromeCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if ($chrome) {
  Write-Host "Chrome found: $chrome"
} else {
  [void](Install-WithWinget -Id "Google.Chrome" -Name "Google Chrome")
}

$pythonCommand = $null
if (Test-Path -LiteralPath $venvPy) {
  $pythonCommand = $venvPy
} elseif (Has-Command "py") {
  $pythonCommand = "py -3"
} elseif (Has-Command "python") {
  $pythonCommand = "python"
}

if (-not $pythonCommand) {
  if (Install-WithWinget -Id "Python.Python.3.12" -Name "Python 3.12") {
    $pythonCommand = "py -3"
  }
}

if (-not $pythonCommand) {
  throw "Python is not installed, and automatic installation failed."
}

if (-not (Test-Path -LiteralPath $venvPy)) {
  Write-Host "Creating local Python virtual environment: .venv ..."
  $exitCode = Invoke-PythonCommand -PythonCommand $pythonCommand -Arguments @("-m", "venv", (Join-Path $root ".venv"))
  if ($exitCode -ne 0) {
    throw "Failed to create Python virtual environment."
  }
}

if (-not (Test-Path -LiteralPath $requirements)) {
  throw "Missing dependency list: $requirements"
}

Write-Host "Installing Python runtime dependencies ..."
& $venvPy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
  throw "pip upgrade failed."
}

& $venvPy -m pip install -r $requirements
if ($LASTEXITCODE -ne 0) {
  throw "Python dependency installation failed."
}

Write-Host ""
Write-Host "Environment setup completed. You can now run the start .bat file." -ForegroundColor Green
