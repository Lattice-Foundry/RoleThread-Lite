param(
    [switch]$WhatIfPlan
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")

Write-Host "LoreForge Lite Windows installer scaffold"
Write-Host "Repository root: $repoRoot"
Write-Host ""
Write-Host "Planned installer strategy:"
Write-Host "- Use Inno Setup to package the PyInstaller one-folder bundle."
Write-Host "- Install app/runtime files under Program Files."
Write-Host "- Preserve user data under LOCALAPPDATA and USERPROFILE on default uninstall."
Write-Host "- Publish final setup executables through GitHub Releases."
Write-Host ""
Write-Host "This scaffold pass does not run Inno Setup yet."

if ($WhatIfPlan) {
    Write-Host ""
    Write-Host "Next pass candidate command shape:"
    Write-Host "ISCC.exe installer\windows\inno\<future-loreforge-lite.iss>"
}

