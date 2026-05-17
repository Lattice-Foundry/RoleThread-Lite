param(
    [switch]$WhatIfPlan
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")

Write-Host "LoreForge Lite Windows bundle scaffold"
Write-Host "Repository root: $repoRoot"
Write-Host ""
Write-Host "Planned bundle strategy:"
Write-Host "- Build a PyInstaller one-folder bundle from a release snapshot."
Write-Host "- Include the bundled Python runtime and application dependencies."
Write-Host "- Write generated files under installer/windows/dist or installer/windows/build."
Write-Host "- Do not commit generated bundle output."
Write-Host ""
Write-Host "This scaffold pass does not run PyInstaller yet."

if ($WhatIfPlan) {
    Write-Host ""
    Write-Host "Next pass candidate command shape:"
    Write-Host "trainer\Scripts\python.exe -m PyInstaller <future-loreforge.spec>"
}

