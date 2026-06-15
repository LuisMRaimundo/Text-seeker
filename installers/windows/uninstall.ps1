# text-seeker Windows uninstaller.
# Removes the private runtime (Python venv, standalone Python, Tesseract, Poppler,
# install state and logs) created by the installer. Reverses opt-in user PATH
# changes. Optionally removes the app's index/cache. Never touches app source.
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$RuntimeRoot = Join-Path $Root 'installers\runtime'
$StateFile = Join-Path $RuntimeRoot 'windows\install_state.json'

Write-Host ''
Write-Host 'text-seeker uninstaller' -ForegroundColor Cyan
Write-Host '=======================' -ForegroundColor Cyan
Write-Host ''
Write-Host "Project: $Root"
Write-Host "Private runtime: $RuntimeRoot"
Write-Host ''

# Reverse any opt-in user PATH entries recorded at install time.
if (Test-Path -LiteralPath $StateFile) {
    try {
        $state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    } catch {
        $state = $null
    }
    if ($state -and $state.user_path_modified -and $state.user_path_entries_added) {
        $entries = @($state.user_path_entries_added)
        if ($entries.Count -gt 0) {
            Write-Host 'Removing opt-in user PATH entries added by the installer:'
            $cur = [Environment]::GetEnvironmentVariable('PATH', 'User')
            if (-not $cur) { $cur = '' }
            $parts = $cur -split ';' | Where-Object { $_ -ne '' }
            $kept = @()
            foreach ($p in $parts) {
                if ($entries -contains $p) {
                    Write-Host "  removed: $p" -ForegroundColor Yellow
                } else {
                    $kept += $p
                }
            }
            [Environment]::SetEnvironmentVariable('PATH', ($kept -join ';'), 'User')
            Write-Host '  user PATH updated (open a new terminal to see the change).'
        }
    }
}

# Remove the private runtime folder.
if (Test-Path -LiteralPath $RuntimeRoot) {
    Write-Host ''
    Write-Host "This will delete the private runtime folder and everything in it:"
    Write-Host "  $RuntimeRoot"
    $ans = Read-Host 'Proceed? [Y/n]'
    if ($ans -eq 'n' -or $ans -eq 'N') {
        Write-Host 'Aborted. Nothing was removed.'
        exit 1
    }
    Remove-Item -LiteralPath $RuntimeRoot -Recurse -Force
    Write-Host "Removed: $RuntimeRoot" -ForegroundColor Green
} else {
    Write-Host 'No private runtime found (already clean).'
}

# Optionally remove the app's index/cache under the user profile.
$dataDirs = @(
    (Join-Path $env:USERPROFILE '.text-seeker_index'),
    (Join-Path $env:USERPROFILE '.text-seeker_cache'),
    (Join-Path $env:USERPROFILE '.docseeker_index')
) | Where-Object { Test-Path -LiteralPath $_ }

if ($dataDirs.Count -gt 0) {
    Write-Host ''
    Write-Host 'Found text-seeker data folders (search index / OCR cache):'
    $dataDirs | ForEach-Object { Write-Host "  $_" }
    $ans2 = Read-Host 'Also delete these? [y/N]'
    if ($ans2 -eq 'y' -or $ans2 -eq 'Y') {
        foreach ($d in $dataDirs) {
            Remove-Item -LiteralPath $d -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  removed: $d" -ForegroundColor Green
        }
    } else {
        Write-Host '  kept (search index/cache preserved).'
    }
}

Write-Host ''
Write-Host 'Uninstall complete. App source files were not modified.' -ForegroundColor Green
Write-Host 'To reinstall, run: installers\windows\Install and Run.bat'
exit 0
