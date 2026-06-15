# Shared Windows installer logic for text-seeker (dot-source from installer_ui.ps1).
#Requires -Version 5.1

$script:InstallerVersion = '3'
$script:PythonVersion = '3.11.9'
$script:PythonMinMajor = 3
$script:PythonMinMinor = 10
$script:TesseractVersion = '5.4.0.20240606'
$script:PopplerVersion = '24.08.0-0'

$script:Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$script:RuntimeRoot = Join-Path $Root 'installers\runtime\windows'
$script:DefaultPrivatePythonDir = Join-Path $RuntimeRoot 'python'
$script:DefaultPrivateTesseractDir = Join-Path $RuntimeRoot 'tesseract'
$script:DefaultPrivatePopplerDir = Join-Path $RuntimeRoot 'poppler'
$script:DefaultVenvDir = Join-Path $RuntimeRoot 'venv'
$script:InstallStateFile = Join-Path $RuntimeRoot 'install_state.json'
$script:InstallLogPath = Join-Path $RuntimeRoot 'install.log'
$script:Requirements = Join-Path $Root 'requirements.txt'
$script:Temp = Join-Path $env:TEMP 'text-seeker-setup'

$script:PythonInstallerUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
# Managed Python uses a self-contained, relocatable build (python-build-standalone):
# download + extract = a ready python.exe (no installer, admin, registry, or repair mode).
$script:PbsTag = '20240415'
$script:PbsUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/$PbsTag/cpython-$PythonVersion+$PbsTag-x86_64-pc-windows-msvc-install_only.tar.gz"
$script:TesseractInstallerUrls = @(
    "https://github.com/UB-Mannheim/tesseract/releases/download/v$TesseractVersion/tesseract-ocr-w64-setup-$TesseractVersion.exe"
    "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-$TesseractVersion.exe"
)
$script:PopplerZipUrl = "https://github.com/oschwartz10612/poppler-windows/releases/download/v$PopplerVersion/Release-$PopplerVersion.zip"

function Write-InstallLog {
    param([string]$Message, [string]$Level = 'INFO')
    if (-not (Test-Path -LiteralPath $RuntimeRoot)) {
        New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
    }
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Level] $Message"
    Add-Content -LiteralPath $script:InstallLogPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Test-WindowsAmd64 {
    $arch = $env:PROCESSOR_ARCHITECTURE
    $wow = $env:PROCESSOR_ARCHITEW6432
    if ($arch -eq 'ARM64') { return $false }
    return ($arch -eq 'AMD64' -or $wow -eq 'AMD64')
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

function Invoke-DownloadWithFallback {
    param([string[]]$Urls, [string]$Dest, [int]$Retries = 2)
    $lastError = $null
    foreach ($Url in $Urls) {
        for ($i = 0; $i -lt $Retries; $i++) {
            try {
                Write-InstallLog "Trying download (attempt $($i+1)): $Url"
                Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing -ErrorAction Stop
                Write-InstallLog "Download succeeded: $Url"
                return $true
            } catch {
                $lastError = $_.Exception.Message
                Write-InstallLog "Download failed ($Url): $lastError" 'WARN'
                Start-Sleep -Seconds 2
            }
        }
    }
    if ($lastError) { Write-InstallLog "All download URLs failed. Last error: $lastError" 'WARN' }
    return $false
}

function Invoke-DownloadOptional {
    param([string]$Url, [string]$Dest)
    try {
        Write-InstallLog "Downloading: $Url"
        Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing -ErrorAction Stop
        return $true
    } catch {
        Write-InstallLog "Download failed ($Url): $($_.Exception.Message)" 'WARN'
        return $false
    }
}

function Resolve-PythonExePath {
    param([string]$InputPath)
    if (-not $InputPath) { return $null }
    $p = $InputPath.Trim().Trim('"')
    if (-not $p) { return $null }
    # If a directory was given, look for python.exe inside it (and common subfolders).
    if (Test-Path -LiteralPath $p -PathType Container) {
        foreach ($candidate in @(
            (Join-Path $p 'python.exe'),
            (Join-Path $p 'Scripts\python.exe')
        )) {
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
        }
        # Fall back to a recursive search (first match) for unusual layouts.
        $found = Get-ChildItem -LiteralPath $p -Filter 'python.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { return $found.FullName }
        return $p  # let caller report "not found"
    }
    return $p
}

function Test-PythonCandidate {
    param([string]$ExePath)
    $resolved = Resolve-PythonExePath -InputPath $ExePath
    $result = [ordered]@{
        Path = $resolved
        Exists = $false
        Version = $null
        VersionOk = $false
        PipOk = $false
        TkOk = $false
        Ready = $false
        Reason = $null
    }
    if (-not $resolved -or -not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        $result.Reason = "python.exe not found at '$ExePath'. Enter the full path to python.exe (or its folder)."
        return $result
    }
    # Windows Store execution-alias stubs are not real interpreters; they print an
    # error and open the Store. Reject them explicitly instead of probing.
    if ($resolved -match '\\WindowsApps\\') {
        $result.Reason = "'$resolved' is a Microsoft Store alias, not a real Python. Install Python or choose 'Install private Python'."
        return $result
    }
    $result.Exists = $true
    # Probe defensively: native stderr must never terminate detection, even when the
    # caller set $ErrorActionPreference = 'Stop'.
    $savedEap = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        $verOut = & $resolved --version 2>&1
        if ($verOut) { $result.Version = ($verOut | Select-Object -First 1 | ForEach-Object { "$_" }) }
        if ($result.Version -and $result.Version -match 'Python (\d+)\.(\d+)') {
            $maj = [int]$Matches[1]; $min = [int]$Matches[2]
            $result.VersionOk = ($maj -gt $script:PythonMinMajor) -or ($maj -eq $script:PythonMinMajor -and $min -ge $script:PythonMinMinor)
        }
        & $resolved -m pip --version 2>$null 1>$null
        $result.PipOk = ($LASTEXITCODE -eq 0)
        & $resolved -c "import tkinter" 2>$null 1>$null
        $result.TkOk = ($LASTEXITCODE -eq 0)
    } catch {
        # Any probe failure leaves the corresponding flag false.
    } finally {
        $ErrorActionPreference = $savedEap
    }
    $result.Ready = $result.VersionOk -and $result.PipOk -and $result.TkOk
    if (-not $result.Ready) {
        $missing = @()
        if (-not $result.VersionOk) { $missing += "Python 3.$($script:PythonMinMinor)+ (found '$($result.Version)')" }
        if (-not $result.PipOk) { $missing += 'pip' }
        if (-not $result.TkOk) { $missing += 'tkinter' }
        $result.Reason = "Missing/incompatible: " + ($missing -join ', ')
    }
    return $result
}

function Get-DetectedPythonInstallations {
    $found = @()
    $seen = @{}
    $candidates = @()
    foreach ($name in @('python.exe', 'python3.exe')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { $candidates += $cmd.Source }
    }
    # py launcher: enumerate installed interpreters (handles per-user installs not on PATH).
    $pyLauncher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $savedEap = $ErrorActionPreference
            $ErrorActionPreference = 'SilentlyContinue'
            $launcherOut = & $pyLauncher.Source '-0p' 2>$null
            $ErrorActionPreference = $savedEap
            foreach ($line in $launcherOut) {
                if ("$line" -match '([A-Za-z]:\\[^\r\n]*python\.exe)') {
                    $candidates += $Matches[1]
                }
            }
        } catch { }
    }
    $regPaths = @(
        'HKLM:\SOFTWARE\Python\PythonCore',
        'HKCU:\SOFTWARE\Python\PythonCore'
    )
    foreach ($reg in $regPaths) {
        if (Test-Path $reg) {
            Get-ChildItem $reg -ErrorAction SilentlyContinue | ForEach-Object {
                $installPath = (Get-ItemProperty -Path "$($_.PSPath)\InstallPath" -ErrorAction SilentlyContinue).'(default)'
                if ($installPath) {
                    $candidates += (Join-Path $installPath 'python.exe')
                }
            }
        }
    }
    # Standard per-user install locations (official python.org per-user installer target).
    foreach ($base in @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python'),
        (Join-Path $env:ProgramFiles 'Python311'),
        'C:\Python311','C:\Python312','C:\Python310'
    )) {
        if ($base -and (Test-Path -LiteralPath $base)) {
            Get-ChildItem -LiteralPath $base -Filter 'python.exe' -Recurse -ErrorAction SilentlyContinue |
                Select-Object -First 8 | ForEach-Object { $candidates += $_.FullName }
        }
    }
    $private = Join-Path $DefaultPrivatePythonDir 'python.exe'
    if (Test-Path -LiteralPath $private) { $candidates += $private }

    foreach ($path in $candidates) {
        try {
            $resolved = (Resolve-Path -LiteralPath $path -ErrorAction Stop).Path
        } catch { continue }
        # Skip Windows Store execution-alias stubs (not real interpreters).
        if ($resolved -match '\\WindowsApps\\') { continue }
        if ($seen.ContainsKey($resolved)) { continue }
        $seen[$resolved] = $true
        $info = Test-PythonCandidate -ExePath $resolved
        $found += [pscustomobject]$info
    }
    return $found
}

function Find-TesseractInPath {
    $cmd = Get-Command tesseract.exe -ErrorAction SilentlyContinue
    if ($cmd -and (Test-Path -LiteralPath $cmd.Source)) { return $cmd.Source }
    $private = Join-Path $DefaultPrivateTesseractDir 'tesseract.exe'
    if (Test-Path -LiteralPath $private) { return $private }
    return $null
}

function Find-PopplerBinInPath {
    $cmds = @('pdftotext.exe', 'pdftoppm.exe')
    foreach ($name in $cmds) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source | Split-Path -Parent }
    }
    $private = Join-Path $DefaultPrivatePopplerDir 'bin'
    if (Test-Path -LiteralPath (Join-Path $private 'pdftotext.exe')) { return $private }
    return $null
}

function Remove-LegacyEmbedRuntime {
    $legacy = $false
    if (Test-Path -LiteralPath $DefaultPrivatePythonDir) {
        $pth = Get-ChildItem -LiteralPath $DefaultPrivatePythonDir -Filter 'python*._pth' -ErrorAction SilentlyContinue
        $zip = Get-ChildItem -LiteralPath $DefaultPrivatePythonDir -Filter 'python*.zip' -ErrorAction SilentlyContinue
        $getPip = Join-Path $DefaultPrivatePythonDir 'get-pip.py'
        if ($pth -or $zip -or (Test-Path -LiteralPath $getPip)) { $legacy = $true }
        if ($legacy) {
            Write-InstallLog 'Removing obsolete embeddable Python runtime (python*._pth / python*.zip / get-pip.py).' 'WARN'
            Remove-Item -LiteralPath $DefaultPrivatePythonDir -Recurse -Force
        }
    }
    return $legacy
}

function Wait-ForFile {
    # The python.org installer can relaunch itself, so python.exe may appear a few
    # seconds after Start-Process -Wait returns. Poll briefly before giving up.
    param([string]$Path, [int]$TimeoutSeconds = 90)
    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        if (Test-Path -LiteralPath $Path -PathType Leaf) { return $true }
        Start-Sleep -Seconds 1
    }
    return (Test-Path -LiteralPath $Path -PathType Leaf)
}

function Find-PythonExeUnder {
    param([string]$Root)
    if (-not (Test-Path -LiteralPath $Root)) { return $null }
    $direct = Join-Path $Root 'python.exe'
    if (Test-Path -LiteralPath $direct -PathType Leaf) { return $direct }
    $found = Get-ChildItem -LiteralPath $Root -Filter 'python.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

function Get-PythonValidationProbe {
    # Validates sys/pip/tkinter end to end. Self-locates the bundled Tcl/Tk relative
    # to the base prefix (works for venvs too) so tkinter.Tk() succeeds without relying
    # on machine TCL_LIBRARY/TK_LIBRARY. Prints VALID OK on success.
    return @'
import os, sys
base = getattr(sys, "base_prefix", sys.prefix)
tcl_root = os.path.join(base, "tcl")
if os.path.isdir(tcl_root):
    for name in os.listdir(tcl_root):
        full = os.path.join(tcl_root, name)
        low = name.lower()
        if not os.path.isdir(full):
            continue
        if low.startswith("tcl8"):
            os.environ.setdefault("TCL_LIBRARY", full)
        elif low.startswith("tk8"):
            os.environ.setdefault("TK_LIBRARY", full)
import pip  # noqa: F401
import tkinter
_root = tkinter.Tk()
_root.destroy()
print(sys.executable)
print("VALID OK")
'@
}

function Test-PrivatePythonValid {
    # End-to-end interpreter validation (sys/pip/tkinter incl. Tk window creation).
    param([string]$PyExe, [switch]$LogOutput)
    $script:LastPythonProbeOutput = ''
    if (-not (Test-Path -LiteralPath $PyExe -PathType Leaf)) {
        $script:LastPythonProbeOutput = "python.exe not found: $PyExe"
        if ($LogOutput) { Write-InstallLog $script:LastPythonProbeOutput 'WARN' }
        return $false
    }
    $probeFile = Join-Path $env:TEMP ("ts-pyprobe-" + [System.Guid]::NewGuid().ToString('N') + '.py')
    Set-Content -LiteralPath $probeFile -Value (Get-PythonValidationProbe) -Encoding ASCII
    $savedEap = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $ok = $false
    $out = ''
    try {
        # Retry once: first execution of freshly-extracted binaries can be delayed by AV.
        for ($attempt = 1; $attempt -le 2; $attempt++) {
            $out = (& $PyExe $probeFile 2>&1 | Out-String)
            if ($LASTEXITCODE -eq 0 -and $out -match 'VALID OK') { $ok = $true; break }
            Start-Sleep -Seconds 2
        }
    } catch {
        $out = "$out`n$($_.Exception.Message)"
    } finally {
        $ErrorActionPreference = $savedEap
        Remove-Item -LiteralPath $probeFile -Force -ErrorAction SilentlyContinue
    }
    $script:LastPythonProbeOutput = ($out -replace '\s+', ' ').Trim()
    if (-not $ok -and $LogOutput) {
        Write-InstallLog ("Python validation probe failed for ${PyExe}: $script:LastPythonProbeOutput") 'WARN'
    }
    return $ok
}

function Install-ManagedPython {
    # Clean-machine route: download a self-contained, relocatable CPython
    # (python-build-standalone) and extract it. No installer .exe, no admin, no
    # registry, no repair-mode, no detection guesswork -- python.exe is just there.
    $managedDir = $DefaultPrivatePythonDir            # installers\runtime\windows\python
    $pyExe = Join-Path $managedDir 'python.exe'

    if ((Test-Path -LiteralPath $pyExe -PathType Leaf) -and (Test-PrivatePythonValid -PyExe $pyExe)) {
        Write-InstallLog "Managed Python already present and valid: $pyExe"
        return $pyExe
    }
    if (Test-Path -LiteralPath $managedDir) {
        Write-InstallLog "Removing stale managed Python: $managedDir" 'WARN'
        Remove-Item -LiteralPath $managedDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    New-Item -ItemType Directory -Force -Path $Temp | Out-Null
    $archive = Join-Path $Temp 'cpython-standalone.tar.gz'
    Write-InstallLog "Downloading standalone Python ${PythonVersion}: $script:PbsUrl"
    Invoke-WebRequest -Uri $script:PbsUrl -OutFile $archive -UseBasicParsing
    if (-not (Test-Path -LiteralPath $archive)) {
        throw "Standalone Python download failed (no file at $archive)."
    }
    $sizeMB = [math]::Round((Get-Item -LiteralPath $archive).Length / 1MB, 1)
    Write-InstallLog "Downloaded standalone Python archive: $archive ($sizeMB MB)"

    # Extract with the built-in bsdtar (handles .tar.gz). Windows 10 1803+ / 11.
    $extractDir = Join-Path $Temp 'cpython-extract'
    if (Test-Path -LiteralPath $extractDir) { Remove-Item -LiteralPath $extractDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $extractDir | Out-Null
    $tarExe = Join-Path $env:SystemRoot 'System32\tar.exe'
    if (-not (Test-Path -LiteralPath $tarExe)) { $tarExe = 'tar' }
    Write-InstallLog "Extracting standalone Python with $tarExe"
    $tarOut = & $tarExe -xf $archive -C $extractDir 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to extract standalone Python (tar exit $LASTEXITCODE). $($tarOut.Trim()) See log: $script:InstallLogPath"
    }

    # python-build-standalone 'install_only' extracts to <extract>\python\python.exe
    $inner = Join-Path $extractDir 'python'
    if (-not (Test-Path -LiteralPath (Join-Path $inner 'python.exe') -PathType Leaf)) {
        $found = Find-PythonExeUnder -Root $extractDir
        if ($found) { $inner = Split-Path -Parent $found }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $inner 'python.exe') -PathType Leaf)) {
        throw "Standalone Python archive did not contain python.exe. See log: $script:InstallLogPath"
    }

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $managedDir) | Out-Null
    Move-Item -LiteralPath $inner -Destination $managedDir -Force
    if (-not (Test-Path -LiteralPath $pyExe -PathType Leaf)) {
        throw "Standalone Python was not placed at $pyExe. See log: $script:InstallLogPath"
    }

    if (-not (Test-PrivatePythonValid -PyExe $pyExe -LogOutput)) {
        throw "Standalone Python failed validation (sys/pip/tkinter): $script:LastPythonProbeOutput See log: $script:InstallLogPath"
    }
    Write-InstallLog "Managed (standalone) Python ready: $pyExe"
    return [string]$pyExe
}

function Write-VenvTclSiteCustomize {
    # Drop a sitecustomize.py into the venv so tkinter finds the bundled Tcl/Tk
    # (standalone Python) on every launch, without touching machine env vars.
    param([string]$VenvDir)
    $siteDir = Join-Path $VenvDir 'Lib\site-packages'
    if (-not (Test-Path -LiteralPath $siteDir)) {
        New-Item -ItemType Directory -Force -Path $siteDir | Out-Null
    }
    $body = @'
import os, sys
try:
    base = getattr(sys, "base_prefix", sys.prefix)
    tcl_root = os.path.join(base, "tcl")
    if os.path.isdir(tcl_root):
        for name in os.listdir(tcl_root):
            full = os.path.join(tcl_root, name)
            low = name.lower()
            if os.path.isdir(full):
                if low.startswith("tcl8"):
                    os.environ.setdefault("TCL_LIBRARY", full)
                elif low.startswith("tk8"):
                    os.environ.setdefault("TK_LIBRARY", full)
except Exception:
    pass
'@
    Set-Content -LiteralPath (Join-Path $siteDir 'sitecustomize.py') -Value $body -Encoding ASCII
    Write-InstallLog "Wrote venv sitecustomize for Tcl/Tk resolution: $siteDir\sitecustomize.py"
}

function New-TextSeekerVenv {
    # Always create a project-local venv and install requirements into it.
    param([string]$BasePython, [string]$VenvDir, [bool]$InstallPackages = $true)
    # Function-local: native-command stderr (e.g. pip warnings) must not abort the
    # installer under the caller's 'Stop' preference. Success is gated on $LASTEXITCODE.
    $ErrorActionPreference = 'SilentlyContinue'
    $venvPy = Join-Path $VenvDir 'Scripts\python.exe'

    if ((Test-Path -LiteralPath $venvPy -PathType Leaf) -and (Test-PrivatePythonValid -PyExe $venvPy)) {
        Write-InstallLog "Reusing existing project venv: $venvPy"
    } else {
        if (Test-Path -LiteralPath $VenvDir) {
            Write-InstallLog "Removing stale venv: $VenvDir" 'WARN'
            Remove-Item -LiteralPath $VenvDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        Write-InstallLog "Creating project-local venv at $VenvDir (base: $BasePython)"
        # Capture command output so it does not leak into the function return value.
        $venvOut = & $BasePython -m venv $VenvDir 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPy -PathType Leaf)) {
            throw "Failed to create virtual environment at $VenvDir (base Python: $BasePython). $($venvOut.Trim())"
        }
    }

    # Ensure the GUI can always locate the bundled Tcl/Tk (standalone Python) at runtime.
    Write-VenvTclSiteCustomize -VenvDir $VenvDir

    if (-not (Test-PrivatePythonValid -PyExe $venvPy -LogOutput)) {
        throw "Project venv Python failed validation (sys/pip/tkinter): $venvPy. $script:LastPythonProbeOutput See log: $script:InstallLogPath"
    }

    if ($InstallPackages) {
        if (-not (Test-Path -LiteralPath $Requirements)) { throw "Missing requirements.txt at $Requirements" }
        Write-InstallLog 'Installing Python packages into project venv (may take 10-20 minutes)...'
        $null = & $venvPy -m pip install --upgrade pip wheel setuptools 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed in venv (exit $LASTEXITCODE)." }
        $null = & $venvPy -m pip install -r $Requirements 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt failed in venv (exit $LASTEXITCODE)." }
        Write-InstallLog 'Python packages installed into project venv.'

        # Diagnostic dependency check (must NEVER abort the install).
        $missing = Get-VenvMissingPackages -VenvPy $venvPy
        if ($null -ne $missing -and $missing -ne '') {
            Write-InstallLog "Venv missing packages after install: $missing; reinstalling (no cache)." 'WARN'
            try {
                $null = & $venvPy -m pip install --no-cache-dir --upgrade -r $Requirements 2>&1 | Out-String
            } catch { }
            $missing2 = Get-VenvMissingPackages -VenvPy $venvPy
            if ($null -ne $missing2 -and $missing2 -ne '') {
                Write-InstallLog "Venv STILL missing packages: $missing2 (OCR/DOCX/PDF features may be limited)." 'WARN'
            } else {
                Write-InstallLog 'Venv dependency re-check: all key packages present.'
            }
        } else {
            Write-InstallLog 'Venv dependency check: all key packages present.'
        }
    }
    # Return ONLY the venv python path (avoid leaking command output into the result).
    return [string]$venvPy
}

function Get-VenvMissingPackages {
    # Returns a comma-separated list of missing key imports (or '' if all present).
    # File-based probe + suppressed errors so it can never abort the installer.
    param([string]$VenvPy)
    $probeFile = Join-Path $env:TEMP ("ts-depcheck-" + [System.Guid]::NewGuid().ToString('N') + '.py')
    $script = @'
import importlib.util as u, sys
mods = ["docx", "PIL", "pytesseract", "fitz", "bs4", "openpyxl", "pdf2image", "pdfminer", "numpy"]
missing = [m for m in mods if u.find_spec(m) is None]
print("VENV_EXE=" + sys.executable)
print("MISSING=" + ",".join(missing))
'@
    Set-Content -LiteralPath $probeFile -Value $script -Encoding ASCII
    $savedEap = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $out = ''
    try {
        $out = (& $VenvPy $probeFile 2>&1 | Out-String)
    } catch {
        $out = "probe error: $($_.Exception.Message)"
    } finally {
        $ErrorActionPreference = $savedEap
        Remove-Item -LiteralPath $probeFile -Force -ErrorAction SilentlyContinue
    }
    Write-InstallLog ("Venv dependency check: " + ($out -replace '\s+', ' ').Trim())
    if ($out -match 'MISSING=([^\r\n]*)') {
        return $Matches[1].Trim()
    }
    return $null
}

function Install-PrivateTesseractTo {
    param([string]$TargetDir)
    $tessExe = Join-Path $TargetDir 'tesseract.exe'
    if (Test-Path -LiteralPath $tessExe) {
        Write-InstallLog "Tesseract already present: $tessExe"
        return $tessExe
    }
    New-Item -ItemType Directory -Force -Path $Temp | Out-Null
    $installer = Join-Path $Temp 'tesseract-setup.exe'
    $ok = Invoke-DownloadWithFallback -Urls $TesseractInstallerUrls -Dest $installer
    if (-not $ok) {
        Write-InstallLog 'Tesseract unavailable; OCR for scanned images may not work.' 'WARN'
        return $null
    }
    if (Test-Path -LiteralPath $TargetDir) { Remove-Item -LiteralPath $TargetDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    $tessArgs = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/DIR=$TargetDir")
    try {
        $proc = Start-Process -FilePath $installer -ArgumentList $tessArgs -Wait -PassThru
        if ($proc.ExitCode -ne 0) { Write-InstallLog "Tesseract installer exit $($proc.ExitCode)" 'WARN' }
    } catch {
        Write-InstallLog "Tesseract installer failed: $($_.Exception.Message)" 'WARN'
        Write-InstallLog 'Tesseract unavailable; OCR for scanned images may not work.' 'WARN'
        return $null
    }
    if (-not (Test-Path -LiteralPath $tessExe)) {
        $found = Get-ChildItem -Path $TargetDir -Filter 'tesseract.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            Copy-Item -Path (Join-Path $found.DirectoryName '*') -Destination $TargetDir -Recurse -Force
        }
    }
    if (-not (Test-Path -LiteralPath $tessExe)) {
        Write-InstallLog 'Tesseract unavailable; OCR for scanned images may not work.' 'WARN'
        return $null
    }
    Write-InstallLog "Tesseract installed: $tessExe"
    return $tessExe
}

function Install-PrivatePopplerTo {
    param([string]$TargetRoot)
    $bin = Join-Path $TargetRoot 'bin'
    $pdftotext = Join-Path $bin 'pdftotext.exe'
    if (Test-Path -LiteralPath $pdftotext) {
        Write-InstallLog "Poppler already present: $bin"
        return $bin
    }
    New-Item -ItemType Directory -Force -Path $Temp | Out-Null
    $zipPath = Join-Path $Temp 'poppler.zip'
    if (-not (Invoke-DownloadOptional -Url $PopplerZipUrl -Dest $zipPath)) {
        Write-InstallLog 'Poppler unavailable; scanned-PDF conversion may not work.' 'WARN'
        return $null
    }
    try {
        if (Test-Path -LiteralPath $TargetRoot) { Remove-Item -LiteralPath $TargetRoot -Recurse -Force }
        New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
        Expand-Archive -LiteralPath $zipPath -DestinationPath $TargetRoot -Force
    } catch {
        Write-InstallLog 'Poppler unavailable; scanned-PDF conversion may not work.' 'WARN'
        return $null
    }
    $found = Get-ChildItem -Path $TargetRoot -Filter 'pdftotext.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $found) {
        Write-InstallLog 'Poppler unavailable; scanned-PDF conversion may not work.' 'WARN'
        return $null
    }
    if ($found.DirectoryName -ne $bin) {
        New-Item -ItemType Directory -Force -Path $bin | Out-Null
        Copy-Item -Path (Join-Path $found.DirectoryName '*') -Destination $bin -Recurse -Force
    }
    Write-InstallLog "Poppler installed: $bin"
    return $bin
}

function Get-OcrCapabilityTag {
    param([bool]$TessOk, [bool]$PopOk)
    if ($TessOk -and $PopOk) { return 'ok' }
    if ($TessOk -or $PopOk) { return 'partial' }
    return 'missing'
}

function Save-InstallState {
    param([hashtable]$State)
    if (-not (Test-Path -LiteralPath $RuntimeRoot)) {
        New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
    }
    $json = $State | ConvertTo-Json -Depth 6
    Set-Content -LiteralPath $InstallStateFile -Value $json -Encoding UTF8
    Write-InstallLog "Wrote install state: $InstallStateFile"
}

function Get-DefaultInstallChoices {
    # Clean-machine default: managed Python. If a compatible Python is detected,
    # default to using it. Custom is never a default and never points at C:\Python.
    $detectedPy = Get-DetectedPythonInstallations | Where-Object { $_.Ready } | Select-Object -First 1
    $pyMode = if ($detectedPy) { 'detected' } else { 'managed' }
    return [ordered]@{
        PythonMode = $pyMode
        PythonPath = if ($detectedPy) { $detectedPy.Path } else { '' }
        VenvDir = $DefaultVenvDir
        InstallPackages = $true
        TesseractMode = 'private'
        TesseractPath = (Join-Path $DefaultPrivateTesseractDir 'tesseract.exe')
        PrivateTesseractDir = $DefaultPrivateTesseractDir
        PopplerMode = 'private'
        PopplerBin = (Join-Path $DefaultPrivatePopplerDir 'bin')
        PrivatePopplerDir = $DefaultPrivatePopplerDir
        PathPolicy = 'process_local'
        RemoveLegacyEmbed = $true
    }
}

function Apply-UserPathPolicy {
    param([hashtable]$Choices, [string]$PyExe, [string]$TessExe, [string]$PopBin)
    if ($Choices.PathPolicy -eq 'process_local') { return @() }
    $added = @()
    $parts = @()
    if ($Choices.PathPolicy -in @('user_tools','user_tools_python')) {
        if ($TessExe -and (Test-Path -LiteralPath $TessExe)) { $parts += (Split-Path -Parent $TessExe) }
        if ($PopBin -and (Test-Path -LiteralPath $PopBin)) { $parts += $PopBin }
    }
    if ($Choices.PathPolicy -eq 'user_tools_python') {
        $pyDir = Split-Path -Parent $PyExe
        $parts += @($pyDir, (Join-Path $pyDir 'Scripts'))
        $venv = $Choices.VenvDir
        if ($venv -and (Test-Path -LiteralPath (Join-Path $venv 'Scripts'))) {
            $parts += (Join-Path $venv 'Scripts')
        }
    }
    if ($parts.Count -eq 0) { return @() }
    $cur = [Environment]::GetEnvironmentVariable('PATH', 'User')
    if (-not $cur) { $cur = '' }
    foreach ($p in $parts) {
        if ($p -and (Test-Path -LiteralPath $p) -and ($cur -notlike "*$p*")) {
            $cur = "$p;$cur"
            $added += $p
            Write-InstallLog "Added to user PATH: $p"
        }
    }
    if ($added.Count -gt 0) {
        [Environment]::SetEnvironmentVariable('PATH', $cur, 'User')
        Write-InstallLog 'User PATH updated (opt-in choice).'
    }
    return $added
}

function Invoke-InstallerRun {
    param([hashtable]$Choices)
    Write-InstallLog '=== text-seeker Windows installer started ==='
    if ($Choices.RemoveLegacyEmbed) { Remove-LegacyEmbedRuntime | Out-Null }

    # --- Resolve the BASE Python by mode (never validate C:\Python in managed mode) ---
    $basePy = $null
    $pyModeState = 'managed_installed'
    switch ($Choices.PythonMode) {
        'detected' {
            $check = Test-PythonCandidate -ExePath $Choices.PythonPath
            if (-not $check.Ready) {
                throw "Selected Python is not valid. Choose a valid python.exe or select managed Python install. ($($check.Reason))"
            }
            $basePy = $check.Path
            $pyModeState = 'detected_existing'
        }
        'custom' {
            $check = Test-PythonCandidate -ExePath $Choices.PythonPath
            if (-not $check.Ready) {
                throw "Selected Python is not valid. Choose a valid python.exe or select managed Python install. ($($check.Reason))"
            }
            $basePy = $check.Path
            $pyModeState = 'custom'
        }
        default {
            # 'managed' (and any legacy value) -> install/locate a managed base Python.
            $basePy = Install-ManagedPython
            $pyModeState = 'managed_installed'
        }
    }

    # --- Always build a project-local venv and launch from it (hard requirement) ---
    $venvPy = New-TextSeekerVenv -BasePython $basePy -VenvDir $Choices.VenvDir -InstallPackages ([bool]$Choices.InstallPackages)
    $launchPy = $venvPy

    # --- Tesseract (warning-only) ---
    $tessExe = $null
    $tessModeState = 'missing'
    switch ($Choices.TesseractMode) {
        'detected' { $tessExe = Find-TesseractInPath; $tessModeState = 'detected' }
        'custom' { $tessExe = $Choices.TesseractPath; $tessModeState = 'detected' }
        'private' { $tessExe = Install-PrivateTesseractTo -TargetDir $Choices.PrivateTesseractDir; $tessModeState = 'private_installed' }
        'skip' { $tessExe = $null; $tessModeState = 'skipped' }
    }
    if ($Choices.TesseractMode -ne 'skip' -and (-not $tessExe -or -not (Test-Path -LiteralPath $tessExe))) {
        Write-InstallLog 'Tesseract unavailable; OCR for scanned images may not work.' 'WARN'
        $tessExe = $null
        $tessModeState = 'missing'
    }

    # --- Poppler (warning-only) ---
    $popBin = $null
    $popModeState = 'missing'
    switch ($Choices.PopplerMode) {
        'detected' { $popBin = Find-PopplerBinInPath; $popModeState = 'detected' }
        'custom' { $popBin = $Choices.PopplerBin; $popModeState = 'detected' }
        'private' { $popBin = Install-PrivatePopplerTo -TargetRoot $Choices.PrivatePopplerDir; $popModeState = 'private_installed' }
        'skip' { $popBin = $null; $popModeState = 'skipped' }
    }
    if ($Choices.PopplerMode -ne 'skip' -and (-not $popBin -or -not (Test-Path -LiteralPath (Join-Path $popBin 'pdftotext.exe')))) {
        Write-InstallLog 'Poppler unavailable; scanned-PDF conversion may not work.' 'WARN'
        $popBin = $null
        $popModeState = 'missing'
    }

    $tessOk = [bool]($tessExe -and (Test-Path -LiteralPath $tessExe))
    $popOk = [bool]($popBin -and (Test-Path -LiteralPath (Join-Path $popBin 'pdftotext.exe')))
    $ocrTag = Get-OcrCapabilityTag -TessOk $tessOk -PopOk $popOk
    $userAdded = Apply-UserPathPolicy -Choices $Choices -PyExe $launchPy -TessExe $tessExe -PopBin $popBin
    $pathPolicyState = if ($userAdded.Count -gt 0) { 'user_path_opt_in' } else { 'process_local' }

    # gui_ready depends ONLY on Python/venv (tkinter/pip/packages), never on OCR tools.
    $guiReady = [bool](Test-PrivatePythonValid -PyExe $launchPy)

    $state = [ordered]@{
        installer_version = $script:InstallerVersion
        install_timestamp = (Get-Date).ToUniversalTime().ToString('o')
        python_mode = $pyModeState
        base_python_path = $basePy
        venv_python_path = $launchPy
        python_path = $launchPy           # legacy alias = launch python
        python_scripts_path = Split-Path -Parent $launchPy
        venv_path = $Choices.VenvDir
        packages_installed = [bool]$Choices.InstallPackages
        tesseract_mode = $tessModeState
        tesseract_path = if ($tessExe) { $tessExe } else { '' }
        poppler_mode = $popModeState
        poppler_bin_path = if ($popBin) { $popBin } else { '' }
        poppler_bin = if ($popBin) { $popBin } else { '' }   # legacy alias
        path_policy = $pathPolicyState
        user_path_modified = ($userAdded.Count -gt 0)
        user_path_entries_added = @($userAdded)
        private_tesseract_dir = $Choices.PrivateTesseractDir
        private_poppler_dir = $Choices.PrivatePopplerDir
        runtime_root = $RuntimeRoot
        ocr_capability = $ocrTag
        gui_ready = $guiReady
        gui_can_launch = $guiReady        # legacy alias
        text_search_available = $true
    }
    Save-InstallState -State $state
    Write-InstallLog '=== text-seeker Windows installer completed ==='
    return $state
}

try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
