# Garmin Connect for Claude -- Windows installer
#
# Sets up an isolated Python environment, installs the server, signs you in to
# Garmin and configures Claude Desktop. Safe to run again to update.
#
#   irm https://raw.githubusercontent.com/jharkebusch/garmin-connect-mcp/main/install.ps1 | iex

$ErrorActionPreference = 'Stop'

$RepoUrl       = 'https://github.com/jharkebusch/garmin-connect-mcp'
$AppDir        = Join-Path $env:USERPROFILE '.garmin-mcp'
$PythonVersion = '3.12'

function Write-Step { param($Message) Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Write-Note { param($Message) Write-Host "    $Message" }
function Stop-WithError {
    param($Message)
    Write-Host "`nError: $Message" -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host '----------------------------------------------------'
Write-Host '  Garmin Connect for Claude -- installer'
Write-Host '----------------------------------------------------'

# --- 1. uv, which brings its own Python so the system one is left alone ------
Write-Step 'Checking for the uv package manager'

$UvBin = $null
foreach ($candidate in @(
    (Get-Command uv -ErrorAction SilentlyContinue).Source,
    (Join-Path $env:USERPROFILE '.local\bin\uv.exe'),
    (Join-Path $env:USERPROFILE '.cargo\bin\uv.exe')
)) {
    if ($candidate -and (Test-Path $candidate)) { $UvBin = $candidate; break }
}

if (-not $UvBin) {
    Write-Note 'Not found. Installing uv (this is a small, standard tool)...'
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    } catch {
        Stop-WithError 'Could not install uv. Check your internet connection and try again.'
    }
    foreach ($candidate in @(
        (Join-Path $env:USERPROFILE '.local\bin\uv.exe'),
        (Join-Path $env:USERPROFILE '.cargo\bin\uv.exe')
    )) {
        if (Test-Path $candidate) { $UvBin = $candidate; break }
    }
    if (-not $UvBin) {
        Stop-WithError 'uv installed but could not be found. Close this window, open a new one and run this again.'
    }
    Write-Note 'Installed uv.'
} else {
    Write-Note "Found uv at $UvBin"
}

# --- 2. Isolated environment -------------------------------------------------
Write-Step "Setting up a private Python environment in $AppDir"
& $UvBin venv --python $PythonVersion $AppDir 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "Could not create the Python environment. Try running: $UvBin python install $PythonVersion"
}
Write-Note 'Ready.'

Write-Step 'Installing the Garmin server (this can take a minute)'
$env:VIRTUAL_ENV = $AppDir
& $UvBin pip install --upgrade "git+$RepoUrl.git" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Stop-WithError 'Could not install the server. Check your internet connection and try again.'
}
Write-Note 'Installed.'

# --- 3. Sign in and configure Claude ----------------------------------------
Write-Step 'Connecting your Garmin account'

$SetupExe = Join-Path $AppDir 'Scripts\garmin-mcp-setup.exe'
if (-not (Test-Path $SetupExe)) {
    Stop-WithError "The setup program was not found at $SetupExe"
}

# Read-Host reads from the console even when this script arrived through a
# pipe, so the interactive prompts below work under `irm ... | iex`.
& $SetupExe
