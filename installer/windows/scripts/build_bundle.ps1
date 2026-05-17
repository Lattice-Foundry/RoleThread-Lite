param(
    [switch]$Clean = $true
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$pythonExe = Join-Path $repoRoot "trainer\Scripts\python.exe"
$specPath = Join-Path $repoRoot "installer\windows\loreforge_launcher.spec"
$distPath = Join-Path $repoRoot "installer\windows\dist"
$buildPath = Join-Path $repoRoot "installer\windows\build"
$bundlePath = Join-Path $distPath "LoreForgeLauncher"

Write-Host "LoreForge Lite PyInstaller bundle prototype"
Write-Host "Repository root: $repoRoot"
Write-Host "Spec file: $specPath"

if (-not (Test-Path $pythonExe)) {
    throw "Could not find dev Python runtime: $pythonExe"
}

if (-not (Test-Path $specPath)) {
    throw "Could not find PyInstaller spec file: $specPath"
}

$pyinstallerCheck = & $pythonExe -m pip show pyinstaller 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed in trainer. Run: trainer\Scripts\python.exe -m pip install -r requirements-dev.txt"
}

if ($Clean) {
    Write-Host "Cleaning old bundle output..."
    Remove-Item -Recurse -Force -LiteralPath $distPath -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force -LiteralPath $buildPath -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $distPath | Out-Null
New-Item -ItemType Directory -Force -Path $buildPath | Out-Null

Write-Host "Running PyInstaller..."
& $pythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $distPath `
    --workpath $buildPath `
    $specPath

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

if (-not (Test-Path (Join-Path $bundlePath "LoreForgeLauncher.exe"))) {
    throw "Bundle did not produce LoreForgeLauncher.exe under: $bundlePath"
}

Write-Host ""
Write-Host "Bundle created:"
Write-Host $bundlePath
Write-Host ""
Write-Host "Run bundled prototype:"
Write-Host (Join-Path $bundlePath "LoreForgeLauncher.exe")
