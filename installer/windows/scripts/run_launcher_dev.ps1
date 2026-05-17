$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$pythonExe = Join-Path $repoRoot "trainer\Scripts\python.exe"
$launcher = Join-Path $repoRoot "installer\windows\launcher\loreforge_launcher.py"

if (-not (Test-Path $pythonExe)) {
    throw "Developer Python runtime not found: $pythonExe"
}

if (-not (Test-Path (Join-Path $repoRoot "app.py"))) {
    throw "LoreForge app.py was not found under repository root: $repoRoot"
}

Write-Host "Starting LoreForge through the Windows launcher prototype..."
Write-Host "Repository root: $repoRoot"
Write-Host "Launcher: $launcher"
Write-Host "Python: $pythonExe"
Write-Host ""
Write-Host "Logs will be written under %LOCALAPPDATA%\LoreForge\logs\launcher.log"
Write-Host ""

Push-Location $repoRoot
try {
    & $pythonExe $launcher
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

