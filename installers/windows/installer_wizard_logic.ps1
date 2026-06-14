# Testable wizard navigation logic for text-seeker Windows installer.
#Requires -Version 5.1

$script:InstallerWizardMaxStep = 6

$script:InstallerWizardSteps = @(
    'Welcome'
    'Python'
    'Packages'
    'Tesseract'
    'Poppler'
    'PATH'
    'Review'
)

function Get-InstallerWizardMaxStep {
    return $script:InstallerWizardMaxStep
}

function Get-InstallerWizardStepTitle {
    param([int]$Step)
    if ($Step -lt 0 -or $Step -gt $script:InstallerWizardMaxStep) {
        return $null
    }
    return $script:InstallerWizardSteps[$Step]
}

function Get-InstallerWizardNavigationState {
    param(
        [int]$Step,
        [int]$MaxStep = $(Get-InstallerWizardMaxStep)
    )
    if ($Step -lt 0) { $Step = 0 }
    if ($Step -gt $MaxStep) { $Step = $MaxStep }
    return [pscustomobject]@{
        Step           = $Step
        StepTitle      = Get-InstallerWizardStepTitle -Step $Step
        BackEnabled    = ($Step -gt 0)
        NextEnabled    = ($Step -lt $MaxStep)
        InstallEnabled = ($Step -eq $MaxStep)
    }
}

function Move-InstallerWizardStep {
    param(
        [int]$CurrentStep,
        [ValidateSet('Next', 'Back')]
        [string]$Direction,
        [int]$MaxStep = $(Get-InstallerWizardMaxStep)
    )
    $next = $CurrentStep
    if ($Direction -eq 'Next' -and $CurrentStep -lt $MaxStep) {
        $next = $CurrentStep + 1
    }
    elseif ($Direction -eq 'Back' -and $CurrentStep -gt 0) {
        $next = $CurrentStep - 1
    }
    return Get-InstallerWizardNavigationState -Step $next -MaxStep $MaxStep
}

function Test-InstallerWizardCanReachInstall {
    param([int]$MaxStep = $(Get-InstallerWizardMaxStep))
    $step = 0
    for ($i = 0; $i -lt ($MaxStep + 5); $i++) {
        $state = Get-InstallerWizardNavigationState -Step $step -MaxStep $MaxStep
        if ($state.InstallEnabled) {
            return $true
        }
        if (-not $state.NextEnabled) {
            return $false
        }
        $step++
    }
    return $false
}

function Get-PythonStepBlockReason {
    # Returns $null when the wizard may advance past the Python step,
    # or a user-facing message explaining why it must not.
    param(
        [string]$Mode,
        [bool]$CandidateReady = $false,
        [string]$CandidateReason = ''
    )
    # Private mode installs Python later; never validate a path here.
    if ($Mode -eq 'private') { return $null }
    if ($CandidateReady) { return $null }
    $base = "Selected Python is not valid. Choose python.exe or select 'Install private Python'."
    if ($CandidateReason) {
        return "$base`r`n`r`nDetail: $CandidateReason"
    }
    return $base
}

function New-InstallerWizardSummaryText {
    param([hashtable]$Choices, [string]$LogPath = '')
    return @(
        "Python mode: $($Choices.PythonMode)"
        "Python path: $($Choices.PythonPath)"
        "Install packages: $($Choices.InstallPackages)"
        "Tesseract: $($Choices.TesseractMode)"
        "Poppler: $($Choices.PopplerMode)"
        "PATH policy: $($Choices.PathPolicy)"
        "Private Python dir: $($Choices.PrivatePythonDir)"
        "Log file: $LogPath"
    ) -join "`r`n"
}
