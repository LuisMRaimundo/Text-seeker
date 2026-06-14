# text-seeker Windows installer UI (Windows Forms wizard; console fallback).
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'installer_config.ps1')
. (Join-Path $PSScriptRoot 'installer_wizard_logic.ps1')

function Show-ConsoleInstallerWizard {
    Write-Host ''
    Write-Host 'text-seeker Windows Installer (console mode)' -ForegroundColor Cyan
    Write-Host '============================================'
    Write-Host ''
    $choices = Get-DefaultInstallChoices

    Write-Host '--- Python ---'
    $detected = Get-DetectedPythonInstallations
    if ($detected.Count -gt 0) {
        Write-Host 'Detected Python installations:'
        for ($i = 0; $i -lt $detected.Count; $i++) {
            $d = $detected[$i]
            $flag = if ($d.Ready) { 'OK' } else { 'incompatible' }
            Write-Host "  [$i] $($d.Path)  $($d.Version)  [$flag]"
        }
    } else {
        Write-Host '  No compatible system Python detected.'
    }
    Write-Host 'Python mode:'
    Write-Host '  1 = Use detected system Python (venv for packages)'
    Write-Host '  2 = Install private Python (recommended if none detected)'
    Write-Host '  3 = Custom python.exe path'
    $pm = Read-Host 'Choice [1-3] (default 2)'
    switch ($pm) {
        '1' {
            $choices.PythonMode = 'system'
            if ($detected.Count -eq 0) { throw 'No system Python detected.' }
            $idx = Read-Host 'Enter index of Python to use'
            $choices.PythonPath = $detected[[int]$idx].Path
            $choices.UseVenvForSystemPython = $true
        }
        '3' {
            $choices.PythonMode = 'custom'
            $choices.PythonPath = Read-Host 'Full path to python.exe (or the folder containing it)'
        }
        default {
            $choices.PythonMode = 'private'
        }
    }

    Write-Host ''
    Write-Host '--- Python packages ---'
    $pkg = Read-Host 'Install requirements.txt? [Y/n]'
    $choices.InstallPackages = ($pkg -ne 'n' -and $pkg -ne 'N')

    Write-Host ''
    Write-Host '--- Tesseract OCR ---'
    Write-Host '  1 = Install private Tesseract'
    Write-Host '  2 = Use detected Tesseract in PATH'
    Write-Host '  3 = Custom tesseract.exe path'
    Write-Host '  4 = Skip Tesseract'
    $tm = Read-Host 'Choice [1-4] (default 1)'
    switch ($tm) {
        '2' { $choices.TesseractMode = 'detected'; $choices.TesseractPath = Find-TesseractInPath }
        '3' { $choices.TesseractMode = 'custom'; $choices.TesseractPath = Read-Host 'Path to tesseract.exe' }
        '4' { $choices.TesseractMode = 'skip' }
        default { $choices.TesseractMode = 'private' }
    }

    Write-Host ''
    Write-Host '--- Poppler ---'
    Write-Host '  1 = Install private Poppler'
    Write-Host '  2 = Use detected Poppler in PATH'
    Write-Host '  3 = Custom Poppler bin folder'
    Write-Host '  4 = Skip Poppler'
    $pm2 = Read-Host 'Choice [1-4] (default 1)'
    switch ($pm2) {
        '2' { $choices.PopplerMode = 'detected'; $choices.PopplerBin = Find-PopplerBinInPath }
        '3' { $choices.PopplerMode = 'custom'; $choices.PopplerBin = Read-Host 'Path to Poppler bin folder' }
        '4' { $choices.PopplerMode = 'skip' }
        default { $choices.PopplerMode = 'private' }
    }

    Write-Host ''
    Write-Host '--- PATH policy ---'
    Write-Host '  1 = Process-local PATH only (recommended; default)'
    Write-Host '  2 = Also add Tesseract/Poppler to user PATH'
    Write-Host '  3 = Also add Tesseract/Poppler/Python Scripts to user PATH'
    $pp = Read-Host 'Choice [1-3] (default 1)'
    switch ($pp) {
        '2' { $choices.PathPolicy = 'user_tools' }
        '3' { $choices.PathPolicy = 'user_tools_python' }
        default { $choices.PathPolicy = 'process_local' }
    }

    Write-Host ''
    Write-Host 'Private install folders (Enter = defaults):'
    $ppd = Read-Host "Python dir [$($choices.PrivatePythonDir)]"
    if ($ppd) { $choices.PrivatePythonDir = $ppd }
    $ptd = Read-Host "Tesseract dir [$($choices.PrivateTesseractDir)]"
    if ($ptd) { $choices.PrivateTesseractDir = $ptd }
    $pbd = Read-Host "Poppler dir [$($choices.PrivatePopplerDir)]"
    if ($pbd) { $choices.PrivatePopplerDir = $pbd }

    Write-Host ''
    Write-Host 'Summary:'
    Write-Host "  Python mode: $($choices.PythonMode)"
    Write-Host "  Tesseract:   $($choices.TesseractMode)"
    Write-Host "  Poppler:     $($choices.PopplerMode)"
    Write-Host "  PATH policy: $($choices.PathPolicy)"
    $go = Read-Host 'Proceed with install? [Y/n]'
    if ($go -eq 'n' -or $go -eq 'N') { return 1 }

    try {
        Invoke-InstallerRun -Choices $choices | Out-Null
        Write-Host ''
        Write-Host 'Install complete. Log:' $InstallLogPath -ForegroundColor Green
        return 0
    } catch {
        Write-InstallLog $_.Exception.Message 'ERROR'
        Write-Host "INSTALL FAILED: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "See log: $InstallLogPath"
        return 1
    }
}

function Show-WinFormsInstallerWizard {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    $choices = Get-DefaultInstallChoices
    $script:WizardStep = 0
    $maxStep = Get-InstallerWizardMaxStep

    $form = New-Object System.Windows.Forms.Form
    $form.Text = 'text-seeker Windows Installer'
    $form.Size = New-Object System.Drawing.Size(640, 520)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false

    $panel = New-Object System.Windows.Forms.Panel
    $panel.Location = New-Object System.Drawing.Point(12, 12)
    $panel.Size = New-Object System.Drawing.Size(600, 400)
    $panel.AutoScroll = $true
    $form.Controls.Add($panel)

    $btnBack = New-Object System.Windows.Forms.Button
    $btnBack.Text = '< Back'
    $btnBack.Location = New-Object System.Drawing.Point(12, 430)
    $btnBack.Size = New-Object System.Drawing.Size(90, 30)
    $form.Controls.Add($btnBack)

    $btnNext = New-Object System.Windows.Forms.Button
    $btnNext.Text = 'Next >'
    $btnNext.Location = New-Object System.Drawing.Point(420, 430)
    $btnNext.Size = New-Object System.Drawing.Size(90, 30)
    $form.Controls.Add($btnNext)

    $btnInstall = New-Object System.Windows.Forms.Button
    $btnInstall.Text = 'Install'
    $btnInstall.Location = New-Object System.Drawing.Point(520, 430)
    $btnInstall.Size = New-Object System.Drawing.Size(90, 30)
    $btnInstall.Enabled = $false
    $form.Controls.Add($btnInstall)

    $btnCancel = New-Object System.Windows.Forms.Button
    $btnCancel.Text = 'Cancel'
    $btnCancel.Location = New-Object System.Drawing.Point(320, 430)
    $btnCancel.Size = New-Object System.Drawing.Size(90, 30)
    $form.Controls.Add($btnCancel)

    $lblStatus = New-Object System.Windows.Forms.Label
    $lblStatus.Location = New-Object System.Drawing.Point(12, 470)
    $lblStatus.Size = New-Object System.Drawing.Size(600, 20)
    $lblStatus.Text = "Log: $InstallLogPath"
    $form.Controls.Add($lblStatus)

    function Clear-Panel {
        $panel.Controls.Clear()
    }

    function Update-WizardButtons {
        $nav = Get-InstallerWizardNavigationState -Step $script:WizardStep -MaxStep $maxStep
        $btnBack.Enabled = $nav.BackEnabled
        $btnNext.Enabled = $nav.NextEnabled
        $btnInstall.Enabled = $nav.InstallEnabled
        if ($nav.StepTitle) {
            $form.Text = "text-seeker Windows Installer - $($nav.StepTitle) ($($script:WizardStep + 1)/$($maxStep + 1))"
        }
    }

    function Show-Step {
        Clear-Panel
        Update-WizardButtons

        switch ($script:WizardStep) {
            0 {
                $y = 10
                Add-Label 'Welcome to text-seeker setup' 10 $y 560 24 $true
                $y += 35
                Add-Label 'This installer lets you choose Python, OCR tools, and PATH handling.' 10 $y 560 40
                $y += 50
                Add-Label 'Default: private Python + optional Tesseract/Poppler; process-local PATH only.' 10 $y 560 40
                $y += 50
                $legacy = Remove-LegacyEmbedRuntime
                if ($legacy) {
                    Add-Label 'Obsolete embeddable Python runtime was removed from the project folder.' 10 $y 560 40 $false ([System.Drawing.Color]::DarkOrange)
                }
            }
            1 {
                $y = 10
                Add-Label 'Python environment' 10 $y 560 24 $true
                $y += 35
                $script:rbPrivate = Add-Radio 'Install private Python (official installer, Tcl/Tk + pip)' 10 $y ($choices.PythonMode -eq 'private'); $y += 28
                $script:rbSystem = Add-Radio 'Use detected system Python (packages into local venv)' 10 $y ($choices.PythonMode -eq 'system'); $y += 28
                $script:rbCustom = Add-Radio 'Use custom python.exe path' 10 $y ($choices.PythonMode -eq 'custom'); $y += 35
                $script:lstPython = New-Object System.Windows.Forms.ListBox
                $script:lstPython.Location = New-Object System.Drawing.Point(10, $y)
                $script:lstPython.Size = New-Object System.Drawing.Size(560, 100)
                foreach ($d in (Get-DetectedPythonInstallations)) {
                    $tag = if ($d.Ready) { 'OK' } else { 'needs 3.10+/pip/tkinter' }
                    [void]$script:lstPython.Items.Add("$($d.Path)  [$tag]")
                }
                $panel.Controls.Add($script:lstPython)
                $y += 110
                Add-Label 'Custom python.exe (or its folder):' 10 $y 240 20; $y += 22
                $customDefault = ''
                if ($choices.PythonMode -eq 'custom') { $customDefault = $choices.PythonPath }
                elseif ($choices.PythonMode -eq 'system') { $customDefault = $choices.PythonPath }
                $script:txtCustomPy = Add-TextBox $customDefault 10 $y 560; $y += 35
                Add-Label 'Private Python folder:' 10 $y 160 20; $y += 22
                $script:txtPrivatePyDir = Add-TextBox $choices.PrivatePythonDir 170 $y 400
            }
            2 {
                $y = 10
                Add-Label 'Python packages (requirements.txt)' 10 $y 560 24 $true
                $y += 35
                $script:chkPackages = New-Object System.Windows.Forms.CheckBox
                $script:chkPackages.Text = 'Install text-seeker Python dependencies'
                $script:chkPackages.Checked = $choices.InstallPackages
                $script:chkPackages.Location = New-Object System.Drawing.Point(10, $y)
                $script:chkPackages.Size = New-Object System.Drawing.Size(560, 24)
                $panel.Controls.Add($script:chkPackages)
                $y += 40
                Add-Label 'When using system Python, packages install into a project-local venv (not globally).' 10 $y 560 40
            }
            3 {
                $y = 10
                Add-Label 'Tesseract OCR (optional - needed for image OCR / scanned PDFs)' 10 $y 560 40 $true
                $y += 45
                $script:rbTessPrivate = Add-Radio 'Install private Tesseract' 10 $y ($choices.TesseractMode -eq 'private'); $y += 28
                $script:rbTessDetected = Add-Radio 'Use Tesseract found in PATH' 10 $y ($choices.TesseractMode -eq 'detected'); $y += 28
                $script:rbTessCustom = Add-Radio 'Custom tesseract.exe path' 10 $y ($choices.TesseractMode -eq 'custom'); $y += 28
                $script:rbTessSkip = Add-Radio 'Skip Tesseract for now' 10 $y ($choices.TesseractMode -eq 'skip'); $y += 35
                $script:txtTessPath = Add-TextBox $choices.TesseractPath 10 $y 560; $y += 35
                $script:txtTessDir = Add-TextBox $choices.PrivateTesseractDir 10 $y 560
                Add-Label 'Private Tesseract folder (above path used for custom):' 10 ($y - 55) 560 20
            }
            4 {
                $y = 10
                Add-Label 'Poppler (optional - needed for scanned-PDF page rendering)' 10 $y 560 40 $true
                $y += 45
                $script:rbPopPrivate = Add-Radio 'Install private Poppler' 10 $y ($choices.PopplerMode -eq 'private'); $y += 28
                $script:rbPopDetected = Add-Radio 'Use Poppler found in PATH' 10 $y ($choices.PopplerMode -eq 'detected'); $y += 28
                $script:rbPopCustom = Add-Radio 'Custom Poppler bin folder' 10 $y ($choices.PopplerMode -eq 'custom'); $y += 28
                $script:rbPopSkip = Add-Radio 'Skip Poppler for now' 10 $y ($choices.PopplerMode -eq 'skip'); $y += 35
                $script:txtPopBin = Add-TextBox $choices.PopplerBin 10 $y 560; $y += 35
                $script:txtPopDir = Add-TextBox $choices.PrivatePopplerDir 10 $y 560
            }
            5 {
                $y = 10
                Add-Label 'PATH handling' 10 $y 560 24 $true
                $y += 35
                $script:rbPathProcess = Add-Radio 'Process-local PATH only (recommended) - Text-seeker works without changing Windows PATH' 10 $y ($choices.PathPolicy -eq 'process_local'); $y += 40
                $script:rbPathTools = Add-Radio 'Also add Tesseract and Poppler to user PATH (optional)' 10 $y ($choices.PathPolicy -eq 'user_tools'); $y += 28
                $script:rbPathAll = Add-Radio 'Also add Tesseract, Poppler, and Python Scripts to user PATH (advanced)' 10 $y ($choices.PathPolicy -eq 'user_tools_python'); $y += 40
                Add-Label 'System PATH is never modified. User PATH changes only if you select an option above.' 10 $y 560 40
            }
            6 {
                $y = 10
                Add-Label 'Review and install' 10 $y 560 24 $true
                $y += 35
                $summary = New-InstallerWizardSummaryText -Choices $choices -LogPath $InstallLogPath
                $script:txtSummary = New-Object System.Windows.Forms.TextBox
                $script:txtSummary.Multiline = $true
                $script:txtSummary.ReadOnly = $true
                $script:txtSummary.Text = $summary
                $script:txtSummary.Location = New-Object System.Drawing.Point(10, $y)
                $script:txtSummary.Size = New-Object System.Drawing.Size(560, 320)
                $panel.Controls.Add($script:txtSummary)
            }
        }
    }

    function Add-Label {
        param($Text, $X, $Y, $W, $H, [bool]$Bold = $false, $Color = $null)
        $l = New-Object System.Windows.Forms.Label
        $l.Text = $Text
        $l.Location = New-Object System.Drawing.Point($X, $Y)
        $l.Size = New-Object System.Drawing.Size($W, $H)
        if ($Bold) { $l.Font = New-Object System.Drawing.Font($l.Font, [System.Drawing.FontStyle]::Bold) }
        if ($Color) { $l.ForeColor = $Color }
        $panel.Controls.Add($l)
        return $l
    }

    function Add-Radio {
        param($Text, $X, $Y, [bool]$Checked)
        $r = New-Object System.Windows.Forms.RadioButton
        $r.Text = $Text
        $r.Location = New-Object System.Drawing.Point($X, $Y)
        $r.Size = New-Object System.Drawing.Size(560, 24)
        $r.Checked = $Checked
        $panel.Controls.Add($r)
        return $r
    }

    function Add-TextBox {
        param($Text, $X, $Y, $W)
        $t = New-Object System.Windows.Forms.TextBox
        $t.Text = $Text
        $t.Location = New-Object System.Drawing.Point($X, $Y)
        $t.Size = New-Object System.Drawing.Size($W, 22)
        $panel.Controls.Add($t)
        return $t
    }

    function Save-StepChoices {
        switch ($script:WizardStep) {
            1 {
                if ($script:rbSystem.Checked) {
                    $choices.PythonMode = 'system'
                    if ($script:lstPython.SelectedIndex -ge 0) {
                        $choices.PythonPath = (Get-DetectedPythonInstallations)[$script:lstPython.SelectedIndex].Path
                    }
                    $choices.UseVenvForSystemPython = $true
                } elseif ($script:rbCustom.Checked) {
                    $choices.PythonMode = 'custom'
                    $choices.PythonPath = $script:txtCustomPy.Text.Trim()
                } else {
                    $choices.PythonMode = 'private'
                }
                $choices.PrivatePythonDir = $script:txtPrivatePyDir.Text.Trim()
            }
            2 { $choices.InstallPackages = $script:chkPackages.Checked }
            3 {
                if ($script:rbTessDetected.Checked) { $choices.TesseractMode = 'detected' }
                elseif ($script:rbTessCustom.Checked) { $choices.TesseractMode = 'custom' }
                elseif ($script:rbTessSkip.Checked) { $choices.TesseractMode = 'skip' }
                else { $choices.TesseractMode = 'private' }
                $choices.TesseractPath = $script:txtTessPath.Text.Trim()
                $choices.PrivateTesseractDir = $script:txtTessDir.Text.Trim()
            }
            4 {
                if ($script:rbPopDetected.Checked) { $choices.PopplerMode = 'detected' }
                elseif ($script:rbPopCustom.Checked) { $choices.PopplerMode = 'custom' }
                elseif ($script:rbPopSkip.Checked) { $choices.PopplerMode = 'skip' }
                else { $choices.PopplerMode = 'private' }
                $choices.PopplerBin = $script:txtPopBin.Text.Trim()
                $choices.PrivatePopplerDir = $script:txtPopDir.Text.Trim()
            }
            5 {
                if ($script:rbPathTools.Checked) { $choices.PathPolicy = 'user_tools' }
                elseif ($script:rbPathAll.Checked) { $choices.PathPolicy = 'user_tools_python' }
                else { $choices.PathPolicy = 'process_local' }
            }
        }
    }

    function Test-CanLeaveCurrentStep {
        # Validate the Python step before advancing. Private mode is never blocked here.
        if ($script:WizardStep -ne 1) { return $true }
        if ($choices.PythonMode -eq 'private') { return $true }

        $check = Test-PythonCandidate -ExePath $choices.PythonPath
        $reason = Get-PythonStepBlockReason -Mode $choices.PythonMode -CandidateReady $check.Ready -CandidateReason $check.Reason
        if (-not $reason) {
            # Persist the normalized python.exe path so later steps use it.
            if ($check.Path) { $choices.PythonPath = $check.Path }
            return $true
        }
        [System.Windows.Forms.MessageBox]::Show(
            $reason,
            'text-seeker - Python selection',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
        return $false
    }

    $btnNext.Add_Click({
        Save-StepChoices
        if (-not (Test-CanLeaveCurrentStep)) { return }
        $nav = Move-InstallerWizardStep -CurrentStep $script:WizardStep -Direction 'Next' -MaxStep $maxStep
        $script:WizardStep = $nav.Step
        Show-Step
    })
    $btnBack.Add_Click({
        Save-StepChoices
        $nav = Move-InstallerWizardStep -CurrentStep $script:WizardStep -Direction 'Back' -MaxStep $maxStep
        $script:WizardStep = $nav.Step
        Show-Step
    })
    $btnCancel.Add_Click({ $form.Close() })
    $btnInstall.Add_Click({
        Save-StepChoices
        $btnInstall.Enabled = $false
        $lblStatus.Text = 'Installing... see log for details.'
        $form.Refresh()
        try {
            Invoke-InstallerRun -Choices $choices | Out-Null
            [System.Windows.Forms.MessageBox]::Show(
                "Installation complete.`n`nLog: $InstallLogPath",
                'text-seeker',
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
            $form.Tag = 0
            $form.Close()
        } catch {
            Write-InstallLog $_.Exception.Message 'ERROR'
            [System.Windows.Forms.MessageBox]::Show(
                "Installation failed:`n$($_.Exception.Message)`n`nLog: $InstallLogPath",
                'text-seeker',
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
            $btnInstall.Enabled = $true
        }
    })

    Show-Step
    $form.Tag = 1
    [void]$form.ShowDialog()
    if ($form.Tag -eq 0) { return 0 }
    return 1
}

if (-not (Test-WindowsAmd64)) {
    Write-InstallLog 'Unsupported CPU architecture (Windows x64 only).' 'ERROR'
    Write-Host 'This installer supports Windows 10/11 x64 only.' -ForegroundColor Red
    exit 2
}

try {
    $exitCode = Show-WinFormsInstallerWizard
    exit $exitCode
} catch {
    Write-InstallLog "WinForms UI unavailable: $($_.Exception.Message)" 'WARN'
    Write-Host 'Opening console installer (WinForms unavailable)...' -ForegroundColor Yellow
    exit (Show-ConsoleInstallerWizard)
}
