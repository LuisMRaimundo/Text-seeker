# text-seeker Windows installer entry point.
# Opens the explicit installer UI (Windows Forms wizard; console fallback).
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'installer_ui.ps1')
exit $LASTEXITCODE
