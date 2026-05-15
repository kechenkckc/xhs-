$ErrorActionPreference = "Stop"

$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$root = $root.Path
$frontend = Join-Path $root "ad-workbench"
$dist = Join-Path $frontend "dist"
$outRoot = Join-Path $root "migration-packages"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$packageName = "ad-workbench-light-$stamp"
$stage = Join-Path $outRoot $packageName
$zip = "$stage.zip"

function Copy-File {
  param(
    [string]$Source,
    [string]$Target
  )

  $targetDir = Split-Path -Parent $Target
  if ($targetDir) {
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
  }
  Copy-Item -LiteralPath $Source -Destination $Target -Force
}

function Copy-Directory {
  param(
    [string]$Source,
    [string]$Target
  )

  if (-not (Test-Path -LiteralPath $Source)) {
    return
  }
  New-Item -ItemType Directory -Force -Path $Target | Out-Null
  Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $Target -Recurse -Force
  }
}

function Remove-IfExists {
  param([string]$Path)

  if (Test-Path -LiteralPath $Path) {
    Remove-Item -LiteralPath $Path -Recurse -Force
  }
}

if (-not (Test-Path -LiteralPath $frontend)) {
  throw "Frontend folder not found: $frontend"
}

Push-Location -LiteralPath $frontend
try {
  if (-not (Test-Path -LiteralPath "node_modules")) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
      throw "npm not found. Install Node.js first or run this on the development computer."
    }
    npm ci
  }
  npm run build
} finally {
  Pop-Location
}

Remove-IfExists -Path $stage
New-Item -ItemType Directory -Force -Path $stage | Out-Null

Copy-Directory -Source (Join-Path $root "rpa_mcp_sync") -Target (Join-Path $stage "rpa_mcp_sync")
Remove-IfExists -Path (Join-Path $stage "rpa_mcp_sync\__pycache__")

Copy-Directory -Source $dist -Target (Join-Path $stage "ad-workbench\dist")
Copy-Directory -Source (Join-Path $root "scripts") -Target (Join-Path $stage "scripts")
Get-ChildItem -LiteralPath (Join-Path $stage "scripts") -File |
  Where-Object { $_.Name -ne "install_environment.ps1" } |
  Remove-Item -Force

$files = @(
  "start_lan.ps1",
  "run_server.ps1",
  "requirements-runtime.txt",
  "screening-workbench.html",
  "screening-workbench.css",
  "screening-workbench.js"
)

foreach ($file in $files) {
  $source = Join-Path $root $file
  if (Test-Path -LiteralPath $source) {
    Copy-File -Source $source -Target (Join-Path $stage $file)
  }
}

Get-ChildItem -LiteralPath $root -Filter "*.bat" -File |
  Where-Object {
    -not (Select-String -LiteralPath $_.FullName -Pattern "build_migration_package" -Quiet -ErrorAction SilentlyContinue)
  } |
  ForEach-Object {
    Copy-File -Source $_.FullName -Target (Join-Path $stage $_.Name)
  }

$readme = @(
  "# AdFlow AI Workbench lightweight migration package",
  "",
  "Usage:",
  "1. Extract this zip on the target computer.",
  "2. Run the environment install .bat file. It checks/installs Python dependencies and uses installed Chrome when available.",
  "3. Run the start .bat file, then open http://127.0.0.1:8797/workbench.",
  "",
  "Notes:",
  "- The package excludes node_modules, Python virtualenvs, Chrome cache, and historical test data.",
  "- First-time setup requires internet access.",
  "- For PGY collection, installed Chrome is used first. If Chrome is missing, setup tries to install Google Chrome.",
  "- Local runtime database and private config are not included by default."
) -join [Environment]::NewLine

Set-Content -LiteralPath (Join-Path $stage "README.md") -Value $readme -Encoding UTF8

Remove-IfExists -Path (Join-Path $stage ".venv")
Remove-IfExists -Path (Join-Path $stage "node_modules")
Remove-IfExists -Path (Join-Path $stage "runtime")
Remove-IfExists -Path (Join-Path $stage "config")

if (Test-Path -LiteralPath $zip) {
  Remove-Item -LiteralPath $zip -Force
}

$items = Get-ChildItem -LiteralPath $stage -Force
Compress-Archive -LiteralPath $items.FullName -DestinationPath $zip -CompressionLevel Optimal
$size = [math]::Round((Get-Item -LiteralPath $zip).Length / 1KB, 1)
Remove-IfExists -Path $stage

Write-Host ""
Write-Host "Package ready:" -ForegroundColor Green
Write-Host $zip
Write-Host "Size: $size KB"
