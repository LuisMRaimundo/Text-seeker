# First-time private runtime setup for text-seeker (Windows x64).
# Installs: Python (with Tcl/Tk + pip), pip packages, Tesseract OCR, Poppler.
# Does not modify system PATH or require administrator rights.
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

# Keep in sync with installers/common/config.py
$PythonVersion = '3.11.9'
$TesseractVersion = '5.4.0.20240606'
$PopplerVersion = '24.08.0-0'
$PythonInstallerUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
$TesseractInstallerUrls = @(
    "https://github.com/UB-Mannheim/tesseract/releases/download/v$TesseractVersion/tesseract-ocr-w64-setup-$TesseractVersion.exe"
    "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-$TesseractVersion.exe"
)
$PopplerZipUrl = "https://github.com/oschwartz10612/poppler-windows/releases/download/v$PopplerVersion/Release-$PopplerVersion.zip"

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$RuntimeRoot = Join-Path $Root 'installers\runtime\windows'
$RuntimePy = Join-Path $RuntimeRoot 'python'
$PyExe = Join-Path $RuntimePy 'python.exe'
$TesseractDir = Join-Path $RuntimeRoot 'tesseract'
$TesseractExe = Join-Path $TesseractDir 'tesseract.exe'
$PopplerRoot = Join-Path $RuntimeRoot 'poppler'
$PopplerBin = Join-Path $PopplerRoot 'bin'
$LogDir = $RuntimeRoot
$script:InstallLogPath = Join-Path $LogDir 'install.log'
$Requirements = Join-Path $Root 'requirements.txt'
$StampFile = Join-Path $Root 'installers\runtime\.install_ok'
$Temp = Join-Path $env:TEMP 'text-seeker-setup'

$script:TesseractOk = $false
$script:PopplerOk = $false
$script:PythonOk = $false

function Write-InstallLog {
    param([string]$Message, [string]$Level = 'INFO')
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    }
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Level] $Message"
    Add-Content -LiteralPath $script:InstallLogPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Test-WindowsAmd64 {
    $arch = $env:PROCESSOR_ARCHITECTURE
    $wow = $env:PROCESSOR_ARCHITEW6432
    if ($arch -eq 'ARM64') {
        return $false
    }
    if ($arch -eq 'AMD64' -or $wow -eq 'AMD64') {
        return $true
    }
    return $false
}

function Get-StampPayload {
    param([bool]$TesseractOk, [bool]$PopplerOk)
    $reqTicks = 0
    if (Test-Path -LiteralPath $Requirements) {
        $reqTicks = (Get-Item -LiteralPath $Requirements).LastWriteTimeUtc.Ticks
    }
    $tessTag = if ($TesseractOk) { $TesseractVersion } else { 'missing' }
    $popTag = if ($PopplerOk) { $PopplerVersion } else { 'missing' }
    return @(
        'v=2'
        "root=$Root"
        "requirements=$reqTicks"
        "python=$PythonVersion"
        "tesseract=$tessTag"
        "poppler=$popTag"
    ) -join "`n"
}

function Test-StampCurrent {
    if (-not (Test-Path -LiteralPath $StampFile)) { return $false }
    $expected = Get-StampPayload -TesseractOk $script:TesseractOk -PopplerOk $script:PopplerOk
    $actual = (Get-Content -LiteralPath $StampFile -Raw).Trim()
    return ($actual -eq $expected)
}

function Write-InstallStamp {
    $payload = Get-StampPayload -TesseractOk $script:TesseractOk -PopplerOk $script:PopplerOk
    $stampParent = Split-Path -Parent $StampFile
    if (-not (Test-Path $stampParent)) {
        New-Item -ItemType Directory -Force -Path $stampParent | Out-Null
    }
    Set-Content -LiteralPath $StampFile -Value $payload -Encoding UTF8 -NoNewline
    Write-InstallLog "Wrote install stamp: $StampFile"
}

function Invoke-Download {
    param([string]$Url, [string]$Dest)
    Write-InstallLog "Downloading: $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing -ErrorAction Stop
}

function Invoke-DownloadWithFallback {
    param([string[]]$Urls, [string]$Dest)
    $lastError = $null
    foreach ($Url in $Urls) {
        try {
            Write-InstallLog "Trying download: $Url"
            Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing -ErrorAction Stop
            Write-InstallLog "Download succeeded: $Url"
            return $true
        } catch {
            $lastError = $_.Exception.Message
            Write-InstallLog "Download failed ($Url): $lastError" 'WARN'
        }
    }
    if ($lastError) {
        Write-InstallLog "All download URLs failed. Last error: $lastError" 'WARN'
    }
    return $false
}

function Invoke-DownloadOptional {
    param([string]$Url, [string]$Dest, [string]$ToolName)
    try {
        Invoke-Download -Url $Url -Dest $Dest
        return $true
    } catch {
        Write-InstallLog "Download failed ($Url): $($_.Exception.Message)" 'WARN'
        return $false
    }
}

function Assert-OfficialPythonInstallerUrl {
    param([string]$Url)
    $forbidden = @('embed-amd64', 'embed-win32', 'embed-arm64', 'get-pip.py')
    foreach ($part in $forbidden) {
        if ($Url.ToLower().Contains($part)) {
            throw "Forbidden Windows Python URL (embed/get-pip not allowed): $Url"
        }
    }
    if (-not $Url.ToLower().EndsWith('-amd64.exe')) {
        throw "Windows Python URL must be official amd64 .exe installer: $Url"
    }
}

function Remove-LegacyEmbedRuntime {
    $legacy = $false
    if (Test-Path -LiteralPath $RuntimePy) {
        $pthFiles = Get-ChildItem -LiteralPath $RuntimePy -Filter 'python*._pth' -ErrorAction SilentlyContinue
        $embedZip = Get-ChildItem -LiteralPath $RuntimePy -Filter 'python*.zip' -ErrorAction SilentlyContinue
        $getPip = Join-Path $RuntimePy 'get-pip.py'
        if ($pthFiles -or $embedZip -or (Test-Path -LiteralPath $getPip)) {
            $legacy = $true
        }
        if ($legacy) {
            Write-InstallLog 'Removing legacy embeddable Python runtime (python*._pth / python*.zip / get-pip.py detected).' 'WARN'
            Remove-Item -LiteralPath $RuntimePy -Recurse -Force
        }
    }
    if (Test-Path -LiteralPath $StampFile) {
        $stampText = Get-Content -LiteralPath $StampFile -Raw -ErrorAction SilentlyContinue
        if ($stampText -match 'v=1' -or $legacy) {
            Write-InstallLog 'Removing outdated install stamp from previous embed-based setup.' 'WARN'
            Remove-Item -LiteralPath $StampFile -Force
        }
    }
}

function Install-PrivatePython {
    Assert-OfficialPythonInstallerUrl -Url $PythonInstallerUrl
    if (Test-Path -LiteralPath $PyExe) {
        Write-InstallLog "Private Python already present: $PyExe"
        return
    }
    Write-InstallLog "Installing private Python $PythonVersion (official amd64 installer with Tcl/Tk and pip)..."
    New-Item -ItemType Directory -Force -Path $Temp | Out-Null
    $installerPath = Join-Path $Temp 'python-installer.exe'
    Invoke-Download -Url $PythonInstallerUrl -Dest $installerPath

    if (Test-Path -LiteralPath $RuntimePy) {
        Remove-Item -LiteralPath $RuntimePy -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $RuntimePy | Out-Null

    $installArgs = @(
        '/quiet'
        'InstallAllUsers=0'
        'PrependPath=0'
        'Include_test=0'
        'Include_launcher=0'
        'Include_pip=1'
        'Include_tcltk=1'
        'SimpleInstall=1'
        "TargetDir=$RuntimePy"
    )
    Write-InstallLog ("Running Python installer -> " + $RuntimePy)
    $proc = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        throw "Python installer failed (exit $($proc.ExitCode))."
    }
    if (-not (Test-Path -LiteralPath $PyExe)) {
        throw "Python installer finished but python.exe was not found at $PyExe"
    }
    Write-InstallLog "Private Python installed at $PyExe"
}

function Test-PythonTkinter {
    & $PyExe -c "import tkinter; tkinter.Tk().destroy()"
    if ($LASTEXITCODE -ne 0) {
        throw "Tkinter is not available in the private Python runtime."
    }
}

function Install-PythonPackages {
    if (-not (Test-Path -LiteralPath $Requirements)) {
        throw "Missing requirements.txt at $Requirements"
    }
    Write-InstallLog 'Installing Python packages (first run may take 10-20 minutes)...'
    & $PyExe -m pip install --upgrade pip wheel setuptools
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed (exit $LASTEXITCODE)." }
    & $PyExe -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt failed (exit $LASTEXITCODE)." }
    Write-InstallLog 'Python packages installed.'
}

function Install-Tesseract {
    if (Test-Path -LiteralPath $TesseractExe) {
        Write-InstallLog "Tesseract already present: $TesseractExe"
        $script:TesseractOk = $true
        return
    }
    Write-InstallLog "Installing private Tesseract OCR $TesseractVersion (UB Mannheim build)..."
    New-Item -ItemType Directory -Force -Path $Temp | Out-Null
    $tessInstaller = Join-Path $Temp 'tesseract-setup.exe'

    $downloaded = Invoke-DownloadWithFallback -Urls $TesseractInstallerUrls -Dest $tessInstaller
    if (-not $downloaded) {
        Write-InstallLog 'Tesseract download failed; OCR for scanned images may be unavailable, but text search and GUI can still run.' 'WARN'
        Write-Host ''
        Write-Host 'WARNING: Tesseract download failed (403/404/timeout on all mirrors).' -ForegroundColor Yellow
        Write-Host 'Text search and GUI still work; OCR/scanned PDF features are disabled.' -ForegroundColor Yellow
        $script:TesseractOk = $false
        return
    }

    if (Test-Path -LiteralPath $TesseractDir) {
        Remove-Item -LiteralPath $TesseractDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $TesseractDir | Out-Null

    # Inno Setup silent install into private folder (no admin, no system PATH).
    $tessArgs = @(
        '/VERYSILENT'
        '/SUPPRESSMSGBOXES'
        '/NORESTART'
        "/DIR=$TesseractDir"
    )
    Write-InstallLog ("Running Tesseract installer -> " + $TesseractDir)
    try {
        $proc = Start-Process -FilePath $tessInstaller -ArgumentList $tessArgs -Wait -PassThru
        if ($proc.ExitCode -ne 0) {
            Write-InstallLog "Tesseract installer exit code $($proc.ExitCode)" 'WARN'
        }
    } catch {
        Write-InstallLog "Tesseract installer failed: $($_.Exception.Message)" 'WARN'
        Write-InstallLog 'Tesseract download failed; OCR for scanned images may be unavailable, but text search and GUI can still run.' 'WARN'
        $script:TesseractOk = $false
        return
    }

    if (-not (Test-Path -LiteralPath $TesseractExe)) {
        $found = Get-ChildItem -Path $TesseractDir -Filter 'tesseract.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            Write-InstallLog "Normalizing Tesseract layout from $($found.DirectoryName)"
            Copy-Item -Path (Join-Path $found.DirectoryName '*') -Destination $TesseractDir -Recurse -Force
        }
    }

    if (-not (Test-Path -LiteralPath $TesseractExe)) {
        Write-InstallLog "Tesseract was not installed; OCR/scanned-PDF features will be unavailable." 'WARN'
        Write-InstallLog 'Tesseract download failed; OCR for scanned images may be unavailable, but text search and GUI can still run.' 'WARN'
        $script:TesseractOk = $false
        return
    }

    $verOut = & $TesseractExe --version 2>&1
    Write-InstallLog ("Tesseract version: " + ($verOut | Select-Object -First 1))
    $script:TesseractOk = $true
}

function Install-Poppler {
    $pdftotext = Join-Path $PopplerBin 'pdftotext.exe'
    if (Test-Path -LiteralPath $pdftotext) {
        Write-InstallLog "Poppler already present: $PopplerBin"
        $script:PopplerOk = $true
        return
    }
    Write-InstallLog "Installing private Poppler $PopplerVersion..."
    New-Item -ItemType Directory -Force -Path $Temp | Out-Null
    $zipPath = Join-Path $Temp 'poppler.zip'

    $downloaded = Invoke-DownloadOptional -Url $PopplerZipUrl -Dest $zipPath -ToolName 'Poppler'
    if (-not $downloaded) {
        Write-InstallLog 'Poppler download failed; PDF page rendering for OCR may fail, but text search and GUI can still run.' 'WARN'
        Write-Host ''
        Write-Host 'WARNING: Poppler download failed.' -ForegroundColor Yellow
        Write-Host 'Text-based PDF search still works; scanned PDF OCR may fail.' -ForegroundColor Yellow
        $script:PopplerOk = $false
        return
    }

    try {
        if (Test-Path -LiteralPath $PopplerRoot) {
            Remove-Item -LiteralPath $PopplerRoot -Recurse -Force
        }
        New-Item -ItemType Directory -Force -Path $PopplerRoot | Out-Null
        Expand-Archive -LiteralPath $zipPath -DestinationPath $PopplerRoot -Force
    } catch {
        Write-InstallLog "Poppler extract failed: $($_.Exception.Message)" 'WARN'
        Write-InstallLog 'Poppler download failed; PDF page rendering for OCR may fail, but text search and GUI can still run.' 'WARN'
        $script:PopplerOk = $false
        return
    }

    $foundPdftotext = Get-ChildItem -Path $PopplerRoot -Filter 'pdftotext.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $foundPdftotext) {
        Write-InstallLog "Poppler pdftotext.exe not found after extract; PDF OCR rendering may fail." 'WARN'
        $script:PopplerOk = $false
        return
    }

    $sourceBin = $foundPdftotext.DirectoryName
    if ($sourceBin -ne $PopplerBin) {
        Write-InstallLog "Normalizing Poppler bin -> $PopplerBin"
        New-Item -ItemType Directory -Force -Path $PopplerBin | Out-Null
        Copy-Item -Path (Join-Path $sourceBin '*') -Destination $PopplerBin -Recurse -Force
    }

    $pdftotextOut = & (Join-Path $PopplerBin 'pdftotext.exe') -v 2>&1
    $pdftoppmOut = & (Join-Path $PopplerBin 'pdftoppm.exe') -v 2>&1
    Write-InstallLog ("pdftotext: " + ($pdftotextOut | Select-Object -First 1))
    Write-InstallLog ("pdftoppm: " + ($pdftoppmOut | Select-Object -First 1))
    $script:PopplerOk = $true
}

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch { }

Write-InstallLog '=== text-seeker Windows setup started ==='
Write-InstallLog ("Project root: " + $Root)
Write-InstallLog ("OS: " + [Environment]::OSVersion.VersionString)

if (-not (Test-WindowsAmd64)) {
    Write-InstallLog 'Unsupported CPU architecture (only Windows x64 is supported).' 'ERROR'
    Write-Host ''
    Write-Host 'This installer supports Windows 10/11 x64 only.' -ForegroundColor Red
    Write-Host 'ARM64 Windows is not supported yet.' -ForegroundColor Red
    Write-Host "Log: $script:InstallLogPath"
    exit 2
}

try {
    Assert-OfficialPythonInstallerUrl -Url $PythonInstallerUrl
    Remove-LegacyEmbedRuntime

    if (Test-Path -LiteralPath $PyExe) {
        & $PyExe -c "import tkinter" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-InstallLog 'Replacing legacy Python runtime (Tkinter missing — likely old embed build).' 'WARN'
            Remove-Item -LiteralPath $RuntimePy -Recurse -Force
        }
    }

    Install-PrivatePython
    Test-PythonTkinter
    $script:PythonOk = $true

    Install-PythonPackages

    Install-Tesseract
    Install-Poppler

    if (-not $script:TesseractOk) {
        Write-InstallLog 'WARNING: Tesseract OCR unavailable — image OCR and scanned PDFs disabled.' 'WARN'
        Write-Host ''
        Write-Host 'WARNING: Tesseract OCR was not installed.' -ForegroundColor Yellow
        Write-Host 'Text search still works; OCR/scanned PDF features are disabled.' -ForegroundColor Yellow
    }
    if (-not $script:PopplerOk) {
        Write-InstallLog 'WARNING: Poppler unavailable — PDF page rendering for OCR may fail.' 'WARN'
        Write-Host ''
        Write-Host 'WARNING: Poppler was not installed.' -ForegroundColor Yellow
        Write-Host 'Text-based PDF search still works; scanned PDF OCR may fail.' -ForegroundColor Yellow
    }

    Write-InstallStamp
    Write-InstallLog '=== text-seeker Windows setup completed ==='
    exit 0
}
catch {
    Write-InstallLog $_.Exception.Message 'ERROR'
    if ($_.ScriptStackTrace) { Write-InstallLog $_.ScriptStackTrace 'ERROR' }
    Write-Host ''
    Write-Host 'SETUP FAILED.' -ForegroundColor Red
    Write-Host $_.Exception.Message
    Write-Host "See log: $script:InstallLogPath"
    exit 1
}
