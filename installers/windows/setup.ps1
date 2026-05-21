# First-time portable Python setup for text-seeker (Windows).
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$RuntimePy = Join-Path $Root 'installers\runtime\windows\python'
$PyExe = Join-Path $RuntimePy 'python.exe'
$LogDir = Join-Path $Root 'installers\runtime\windows'
$script:InstallLogPath = Join-Path $LogDir 'install.log'
$Requirements = Join-Path $Root 'requirements.txt'

function Write-InstallLog {
    param([string]$Message, [string]$Level = 'INFO')
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    }
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Level] $Message"
    Add-Content -LiteralPath $script:InstallLogPath -Value $line -Encoding UTF8
    Write-Host $line
}

if (Test-Path $PyExe) {
    Write-InstallLog "Portable Python already installed: $PyExe"
    exit 0
}

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch { }

$Version = '3.11.9'
$ZipUrl = "https://www.python.org/ftp/python/$Version/python-$Version-embed-amd64.zip"
$GetPipUrl = 'https://bootstrap.pypa.io/get-pip.py'
$Temp = Join-Path $env:TEMP 'text-seeker-python-setup'
New-Item -ItemType Directory -Force -Path $Temp | Out-Null
$ZipPath = Join-Path $Temp 'python-embed.zip'

try {
    Write-InstallLog "Downloading portable Python $Version (one-time, ~25 MB)..."
    Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath -UseBasicParsing

    if (Test-Path $RuntimePy) { Remove-Item -Recurse -Force $RuntimePy }
    New-Item -ItemType Directory -Force -Path $RuntimePy | Out-Null
    Expand-Archive -Path $ZipPath -DestinationPath $RuntimePy -Force

    Get-ChildItem $RuntimePy -Filter 'python*._pth' | ForEach-Object {
        $lines = Get-Content $_.FullName | Where-Object { $_ -notmatch '^\s*#import site\s*$' }
        if ($lines -notcontains 'import site') { $lines += 'import site' }
        Set-Content -Path $_.FullName -Value ($lines -join "`n") -Encoding utf8
    }

    $GetPip = Join-Path $RuntimePy 'get-pip.py'
    Write-InstallLog 'Downloading pip...'
    Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPip -UseBasicParsing

    Write-InstallLog 'Installing pip...'
    & $PyExe $GetPip
    if ($LASTEXITCODE -ne 0) { throw "get-pip.py failed (exit $LASTEXITCODE)." }

    if (-not (Test-Path $Requirements)) {
        throw "Missing requirements.txt at $Requirements"
    }

    Write-InstallLog 'Installing Python packages (may take 10-20 minutes on first run)...'
    & $PyExe -m pip install --upgrade pip wheel setuptools
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed (exit $LASTEXITCODE)." }

    & $PyExe -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt failed (exit $LASTEXITCODE)." }

    Write-InstallLog "Portable Python ready at $PyExe"
    exit 0
}
catch {
    Write-InstallLog $_.Exception.Message 'ERROR'
    if ($_.ScriptStackTrace) { Write-InstallLog $_.ScriptStackTrace 'ERROR' }
    Write-Host ''
    Write-Host 'SETUP FAILED.' -ForegroundColor Red
    Write-Host $_.Exception.Message
    Write-Host "Log: $script:InstallLogPath"
    exit 1
}
