# First-time portable Python setup for text-seeker (Windows).
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$RuntimePy = Join-Path $Root "installers\runtime\windows\python"
$PyExe = Join-Path $RuntimePy "python.exe"

if (Test-Path $PyExe) { exit 0 }

$Version = "3.11.9"
$ZipUrl = "https://www.python.org/ftp/python/$Version/python-$Version-embed-amd64.zip"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$Temp = Join-Path $env:TEMP "text-seeker-python-setup"
New-Item -ItemType Directory -Force -Path $Temp | Out-Null
$ZipPath = Join-Path $Temp "python-embed.zip"

Write-Host "Downloading portable Python $Version (one-time, ~25 MB) ..."
Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath -UseBasicParsing

if (Test-Path $RuntimePy) { Remove-Item -Recurse -Force $RuntimePy }
New-Item -ItemType Directory -Force -Path $RuntimePy | Out-Null
Expand-Archive -Path $ZipPath -DestinationPath $RuntimePy -Force

Get-ChildItem $RuntimePy -Filter "python*._pth" | ForEach-Object {
  $lines = Get-Content $_.FullName | Where-Object { $_ -notmatch '^\s*#import site\s*$' }
  if ($lines -notcontains "import site") { $lines += "import site" }
  Set-Content -Path $_.FullName -Value ($lines -join "`n") -Encoding utf8
}

$GetPip = Join-Path $RuntimePy "get-pip.py"
Write-Host "Downloading pip ..."
Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPip -UseBasicParsing
Write-Host "Installing pip ..."
& $PyExe $GetPip

Write-Host "Portable Python ready at $PyExe"
