# Unit tests for text-seeker Windows installer wizard navigation.
#Requires -Version 5.1

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$windowsDir = Split-Path -Parent $here
. (Join-Path $windowsDir 'installer_wizard_logic.ps1')

$failed = 0
$passed = 0

function Assert-True {
    param([bool]$Condition, [string]$Name)
    if ($Condition) {
        Write-Host "[OK] $Name" -ForegroundColor Green
        $script:passed++
    } else {
        Write-Host "[FAIL] $Name" -ForegroundColor Red
        $script:failed++
    }
}

function Assert-Equals {
    param($Expected, $Actual, [string]$Name)
    if ($Expected -eq $Actual) {
        Write-Host "[OK] $Name" -ForegroundColor Green
        $script:passed++
    } else {
        Write-Host "[FAIL] $Name (expected '$Expected', got '$Actual')" -ForegroundColor Red
        $script:failed++
    }
}

Write-Host ''
Write-Host 'InstallWizard.Tests.ps1' -ForegroundColor Cyan
Write-Host '=======================' -ForegroundColor Cyan

Assert-Equals 6 (Get-InstallerWizardMaxStep) 'Max step is 6 (Review)'

$welcome = Get-InstallerWizardNavigationState -Step 0
Assert-True (-not $welcome.BackEnabled) 'Step 0: Back disabled'
Assert-True $welcome.NextEnabled 'Step 0: Next enabled'
Assert-True (-not $welcome.InstallEnabled) 'Step 0: Install disabled'

$review = Get-InstallerWizardNavigationState -Step 6
Assert-True $review.BackEnabled 'Step 6: Back enabled'
Assert-True (-not $review.NextEnabled) 'Step 6: Next disabled'
Assert-True $review.InstallEnabled 'Step 6: Install enabled'

Assert-True (Test-InstallerWizardCanReachInstall) 'Can reach Install step from Welcome via Next'

$step = 0
for ($i = 0; $i -lt 6; $i++) {
    $nav = Move-InstallerWizardStep -CurrentStep $step -Direction 'Next'
    $step = $nav.Step
}
Assert-Equals 6 $step 'Six Next clicks land on Review step'

$back = Move-InstallerWizardStep -CurrentStep 6 -Direction 'Back'
Assert-Equals 5 $back.Step 'Back from Review goes to PATH step'

$choices = @{
    PythonMode = 'private'
    PythonPath = 'C:\test\python.exe'
    InstallPackages = $true
    TesseractMode = 'skip'
    PopplerMode = 'private'
    PathPolicy = 'process_local'
    PrivatePythonDir = 'C:\test\python'
}
$summary = New-InstallerWizardSummaryText -Choices $choices -LogPath 'C:\test\install.log'
Assert-True ($summary -match 'Python mode: private') 'Summary includes Python mode'
Assert-True ($summary -match 'PATH policy: process_local') 'Summary includes PATH policy'

# Guard: installer_ui.ps1 must use script-scoped WizardStep (regression for stuck Next button)
$uiText = Get-Content -LiteralPath (Join-Path $windowsDir 'installer_ui.ps1') -Raw
Assert-True ($uiText -match '\$script:WizardStep') 'UI uses $script:WizardStep'
Assert-True ($uiText -match 'Move-InstallerWizardStep') 'UI uses Move-InstallerWizardStep'
Assert-True ($uiText -notmatch '\$script:step\+\+') 'UI does not use broken $script:step++'

# Guard: installer .ps1 files must be pure ASCII so Windows PowerShell 5.1
# (which reads BOM-less scripts as Windows-1252) cannot corrupt characters.
foreach ($psName in @('installer_ui.ps1', 'installer_config.ps1', 'installer_wizard_logic.ps1')) {
    $psPath = Join-Path $windowsDir $psName
    $bytes = [System.IO.File]::ReadAllBytes($psPath)
    $nonAscii = @($bytes | Where-Object { $_ -gt 127 })
    Assert-Equals 0 $nonAscii.Count "$psName is pure ASCII (no non-ASCII bytes)"
}

# Python path resolution: a directory containing python.exe must resolve to the exe.
. (Join-Path $windowsDir 'installer_config.ps1')

$tmpRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ts-pytest-" + [System.Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tmpRoot | Out-Null
$fakeExe = Join-Path $tmpRoot 'python.exe'
Set-Content -LiteralPath $fakeExe -Value '' -Encoding ASCII
try {
    Assert-Equals $fakeExe (Resolve-PythonExePath -InputPath $tmpRoot) 'Resolve-PythonExePath: directory resolves to python.exe'
    Assert-Equals $fakeExe (Resolve-PythonExePath -InputPath $fakeExe) 'Resolve-PythonExePath: file path returned as-is'
    Assert-Equals $fakeExe (Resolve-PythonExePath -InputPath ('"' + $tmpRoot + '"')) 'Resolve-PythonExePath: trims surrounding quotes'

    $bad = Test-PythonCandidate -ExePath 'C:\NoSuchPythonFolderXYZ'
    Assert-True (-not $bad.Ready) 'Test-PythonCandidate: missing path is not ready'
    Assert-True ($bad.Reason -match 'not found') 'Test-PythonCandidate: missing path reason mentions not found'

    # Default choices must never default Python to a bare 'C:\Python'.
    $defaults = Get-DefaultInstallChoices
    Assert-True ($defaults.PythonPath -ne 'C:\Python') 'Default PythonPath is not C:\Python'
    Assert-True ($defaults.PythonMode -in @('system', 'private')) 'Default PythonMode is system or private'
    if ($defaults.PythonMode -eq 'private') {
        Assert-True ($defaults.PythonPath -like '*runtime*windows*python*') 'Private default Python is under the private runtime'
    }
} finally {
    Remove-Item -LiteralPath $tmpRoot -Recurse -Force -ErrorAction SilentlyContinue
}

# Python step gating: private never blocks; invalid custom/system blocks with a clear message.
Assert-True ($null -eq (Get-PythonStepBlockReason -Mode 'private' -CandidateReady $false)) 'Private mode never blocks Next'
Assert-True ($null -eq (Get-PythonStepBlockReason -Mode 'custom' -CandidateReady $true)) 'Ready custom Python does not block Next'
$blk = Get-PythonStepBlockReason -Mode 'custom' -CandidateReady $false -CandidateReason 'Missing/incompatible: tkinter'
Assert-True ($blk -match 'not valid') 'Invalid custom Python blocks with clear message'
Assert-True ($blk -match 'Install private Python') 'Block message guides to private Python'
Assert-True ($blk -match 'tkinter') 'Block message includes the failing check detail'
$blkSys = Get-PythonStepBlockReason -Mode 'system' -CandidateReady $false -CandidateReason 'no pip'
Assert-True ($blkSys -match 'not valid') 'Invalid system Python also blocks'

# Windows Store alias stubs must be rejected, not probed.
$storeStub = 'C:\Users\x\AppData\Local\Microsoft\WindowsApps\python3.exe'
$storeResult = Test-PythonCandidate -ExePath $storeStub
Assert-True (-not $storeResult.Ready) 'WindowsApps Store alias is not ready'

# Detection must never throw, even under $ErrorActionPreference = Stop.
$threw = $false
try { $null = Get-DetectedPythonInstallations } catch { $threw = $true }
Assert-True (-not $threw) 'Get-DetectedPythonInstallations does not throw under Stop'

# Private-install helpers: locate python.exe (incl. nested) and wait for a file.
$tmp2 = Join-Path ([System.IO.Path]::GetTempPath()) ("ts-pyfind-" + [System.Guid]::NewGuid().ToString('N'))
$nested = Join-Path $tmp2 'tools'
New-Item -ItemType Directory -Force -Path $nested | Out-Null
$nestedExe = Join-Path $nested 'python.exe'
Set-Content -LiteralPath $nestedExe -Value '' -Encoding ASCII
try {
    Assert-Equals $nestedExe (Find-PythonExeUnder -Root $tmp2) 'Find-PythonExeUnder locates nested python.exe'
    Assert-True (Wait-ForFile -Path $nestedExe -TimeoutSeconds 2) 'Wait-ForFile returns true for existing file'
    Assert-True (-not (Wait-ForFile -Path (Join-Path $tmp2 'nope.exe') -TimeoutSeconds 1)) 'Wait-ForFile returns false for missing file'
} finally {
    Remove-Item -LiteralPath $tmp2 -Recurse -Force -ErrorAction SilentlyContinue
}

# Regression: do not use the PowerShell automatic variable $args for installer args.
$cfgText = Get-Content -LiteralPath (Join-Path $windowsDir 'installer_config.ps1') -Raw
Assert-True ($cfgText -notmatch '\$args\s*=') 'installer_config.ps1 does not assign to automatic $args'
Assert-True ($cfgText -match 'Find-PythonExeUnder') 'installer_config.ps1 has python.exe locate fallback'

# Private Python installer argument strategy.
Assert-True ($cfgText -match '\$pyArgs = @\(') 'Python installer uses an argument array'
foreach ($tok in @('TargetDir=$TargetDir','Include_exe=1','Include_lib=1','Include_pip=1','Include_tcltk=1','PrependPath=0','InstallAllUsers=0','/log')) {
    Assert-True ($cfgText -match [regex]::Escape($tok)) "Python installer args include $tok"
}

# Per-user location is diagnostic-only; private search scoped to runtime root.
Assert-True ($cfgText -match 'DIAGNOSTIC') 'Per-user Python location is logged as diagnostic'
Assert-True ($cfgText -match 'Find-PythonExeUnder -Root \$RuntimeRoot') 'Private search is scoped to the runtime root'
Assert-True ($cfgText -match 'import sys, pip, tkinter') 'Private Python validated end to end'

# Validation must run end to end and not silently accept a per-user interpreter.
$tmp3 = Join-Path ([System.IO.Path]::GetTempPath()) ("ts-validpy-" + [System.Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tmp3 | Out-Null
try {
    Assert-True (-not (Test-PrivatePythonValid -PyExe (Join-Path $tmp3 'python.exe'))) 'Test-PrivatePythonValid false for missing python.exe'
} finally {
    Remove-Item -LiteralPath $tmp3 -Recurse -Force -ErrorAction SilentlyContinue
}

# UI must gate Next on the Python step.
Assert-True ($uiText -match 'Test-CanLeaveCurrentStep') 'UI gates Next with Test-CanLeaveCurrentStep'
Assert-True ($uiText -match 'Get-PythonStepBlockReason') 'UI uses Get-PythonStepBlockReason'

Write-Host ''
Write-Host "Results: $passed passed, $failed failed" -ForegroundColor $(if ($failed -eq 0) { 'Green' } else { 'Red' })
if ($failed -gt 0) { exit 1 }
exit 0
