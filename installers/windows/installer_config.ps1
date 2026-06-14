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

function Install-PrivatePythonTo {
    param([string]$TargetDir)
    Assert-OfficialPythonInstallerUrl -Url $script:PythonInstallerUrl
    $pyExe = Join-Path $TargetDir 'python.exe'
    if (Test-Path -LiteralPath $pyExe) {
        $check = Test-PythonCandidate -ExePath $pyExe
        if ($check.TkOk) {
            Write-InstallLog "Private Python already present: $pyExe"
            return $pyExe
        }
        Write-InstallLog 'Replacing private Python (Tkinter missing).' 'WARN'
        Remove-Item -LiteralPath $TargetDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Temp | Out-Null
    $installerPath = Join-Path $Temp 'python-installer.exe'
    Write-InstallLog "Installing private Python $PythonVersion to $TargetDir"
    Invoke-WebRequest -Uri $script:PythonInstallerUrl -OutFile $installerPath -UseBasicParsing
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    $args = @('/quiet','InstallAllUsers=0','PrependPath=0','Include_test=0','Include_launcher=0','Include_pip=1','Include_tcltk=1','SimpleInstall=1',"TargetDir=$TargetDir")
    $proc = Start-Process -FilePath $installerPath -ArgumentList $args -Wait -PassThru
    if ($proc.ExitCode -ne 0) { throw "Python installer failed (exit $($proc.ExitCode))." }
    if (-not (Test-Path -LiteralPath $pyExe)) { throw "Python installer finished but python.exe not found at $pyExe" }
    & $pyExe -c "import tkinter; tkinter.Tk().destroy()"
    if ($LASTEXITCODE -ne 0) { throw 'Tkinter is not available in the private Python runtime.' }
    Write-InstallLog "Private Python installed: $pyExe"
    return $pyExe
}

function Install-PythonPackagesTo {
    param([string]$PyExe, [string]$VenvDir = $null)
    if (-not (Test-Path -LiteralPath $Requirements)) { throw "Missing requirements.txt at $Requirements" }
    $pipPy = $PyExe
    if ($VenvDir) {
        Write-InstallLog "Creating virtual environment at $VenvDir"
        if (-not (Test-Path -LiteralPath $VenvDir)) {
            & $PyExe -m venv $VenvDir
            if ($LASTEXITCODE -ne 0) { throw "venv creation failed (exit $LASTEXITCODE)." }
        }
        $pipPy = Join-Path $VenvDir 'Scripts\python.exe'
    }
    Write-InstallLog 'Installing Python packages (may take 10-20 minutes)...'
    & $pipPy -m pip install --upgrade pip wheel setuptools
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed (exit $LASTEXITCODE)." }
    & $pipPy -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt failed (exit $LASTEXITCODE)." }
    Write-InstallLog 'Python packages installed.'
    return $pipPy
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
    $args = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/DIR=$TargetDir")
    try {
        $proc = Start-Process -FilePath $installer -ArgumentList $args -Wait -PassThru
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
    $detectedPy = Get-DetectedPythonInstallations | Where-Object { $_.Ready } | Select-Object -First 1
    $pyMode = if ($detectedPy) { 'system' } else { 'private' }
    return [ordered]@{
        PythonMode = $pyMode
        PythonPath = if ($detectedPy) { $detectedPy.Path } else { (Join-Path $DefaultPrivatePythonDir 'python.exe') }
        UseVenvForSystemPython = $true
        VenvDir = $DefaultVenvDir
        InstallPackages = $true
        PrivatePythonDir = $DefaultPrivatePythonDir
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

    $pyExe = $null
    $venvDir = $null
    switch ($Choices.PythonMode) {
        'system' {
            $check = Test-PythonCandidate -ExePath $Choices.PythonPath
            if (-not $check.Ready) { throw "Selected system Python is not usable. $($check.Reason)" }
            $pyExe = $check.Path
            if ($Choices.UseVenvForSystemPython) { $venvDir = $Choices.VenvDir }
        }
        'custom' {
            $check = Test-PythonCandidate -ExePath $Choices.PythonPath
            if (-not $check.Ready) { throw "Custom Python is not usable. $($check.Reason)" }
            $pyExe = $check.Path
        }
        default {
            $pyExe = Install-PrivatePythonTo -TargetDir $Choices.PrivatePythonDir
        }
    }

    $launchPy = $pyExe
    if ($Choices.InstallPackages) {
        $launchPy = Install-PythonPackagesTo -PyExe $pyExe -VenvDir $venvDir
    }

    $tessExe = $null
    switch ($Choices.TesseractMode) {
        'detected' { $tessExe = Find-TesseractInPath }
        'custom' { $tessExe = $Choices.TesseractPath }
        'private' { $tessExe = Install-PrivateTesseractTo -TargetDir $Choices.PrivateTesseractDir }
        'skip' { $tessExe = $null }
    }
    if ($Choices.TesseractMode -ne 'skip' -and (-not $tessExe -or -not (Test-Path -LiteralPath $tessExe))) {
        Write-InstallLog 'Tesseract unavailable; OCR for scanned images may not work.' 'WARN'
        $tessExe = $null
    }

    $popBin = $null
    switch ($Choices.PopplerMode) {
        'detected' { $popBin = Find-PopplerBinInPath }
        'custom' { $popBin = $Choices.PopplerBin }
        'private' { $popBin = Install-PrivatePopplerTo -TargetRoot $Choices.PrivatePopplerDir }
        'skip' { $popBin = $null }
    }
    if ($Choices.PopplerMode -ne 'skip' -and (-not $popBin -or -not (Test-Path -LiteralPath (Join-Path $popBin 'pdftotext.exe')))) {
        Write-InstallLog 'Poppler unavailable; scanned-PDF conversion may not work.' 'WARN'
        $popBin = $null
    }

    $tessOk = [bool]($tessExe -and (Test-Path -LiteralPath $tessExe))
    $popOk = [bool]($popBin -and (Test-Path -LiteralPath (Join-Path $popBin 'pdftotext.exe')))
    $ocrTag = Get-OcrCapabilityTag -TessOk $tessOk -PopOk $popOk
    $userAdded = Apply-UserPathPolicy -Choices $Choices -PyExe $launchPy -TessExe $tessExe -PopBin $popBin

    $state = [ordered]@{
        installer_version = $script:InstallerVersion
        install_timestamp = (Get-Date).ToUniversalTime().ToString('o')
        python_mode = $Choices.PythonMode
        python_path = $launchPy
        python_scripts_path = if ($venvDir) { Join-Path $venvDir 'Scripts' } else { Join-Path (Split-Path -Parent $launchPy) 'Scripts' }
        venv_path = if ($venvDir) { $venvDir } else { '' }
        packages_installed = [bool]$Choices.InstallPackages
        tesseract_mode = $Choices.TesseractMode
        tesseract_path = if ($tessExe) { $tessExe } else { '' }
        poppler_mode = $Choices.PopplerMode
        poppler_bin = if ($popBin) { $popBin } else { '' }
        path_policy = $Choices.PathPolicy
        user_path_modified = ($userAdded.Count -gt 0)
        user_path_entries_added = @($userAdded)
        private_python_dir = $Choices.PrivatePythonDir
        private_tesseract_dir = $Choices.PrivateTesseractDir
        private_poppler_dir = $Choices.PrivatePopplerDir
        runtime_root = $RuntimeRoot
        ocr_capability = $ocrTag
        gui_can_launch = $true
        text_search_available = $true
    }
    Save-InstallState -State $state
    Write-InstallLog '=== text-seeker Windows installer completed ==='
    return $state
}

try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
