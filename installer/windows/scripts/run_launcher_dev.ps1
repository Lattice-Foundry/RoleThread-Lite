$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$launcher = Join-Path $repoRoot "installer\windows\launcher\rolethread_launcher.py"

if (-not (Test-Path $pythonExe)) {
    throw "Developer Python runtime not found: $pythonExe"
}

if (-not (Test-Path (Join-Path $repoRoot "app.py"))) {
    throw "RoleThread app.py was not found under repository root: $repoRoot"
}

Write-Host "Starting RoleThread through the Windows launcher prototype..."
Write-Host "Repository root: $repoRoot"
Write-Host "Launcher: $launcher"
Write-Host "Python: $pythonExe"
Write-Host ""
Write-Host "Logs will be written under %LOCALAPPDATA%\RoleThread\logs\launcher.log"
Write-Host ""

Push-Location $repoRoot
try {
    & $pythonExe $launcher
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
