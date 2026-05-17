param(
    [switch]$BuildBundle,
    [switch]$UseExistingBundle
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$bundleDir = Join-Path $repoRoot "installer\windows\dist\RoleThreadLauncher"
$bundleExe = Join-Path $bundleDir "RoleThreadLauncher.exe"
$innoScript = Join-Path $repoRoot "installer\windows\inno\rolethread_lite.iss"
$outputDir = Join-Path $repoRoot "installer\windows\output"
$versionFile = Join-Path $repoRoot "core\version.py"
$bundleVersionFile = Join-Path $bundleDir "_internal\core\version.py"

function Get-RoleThreadVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Could not find RoleThread version file: $Path"
    }

    $versionText = Get-Content -LiteralPath $Path -Raw
    if ($versionText -match 'ROLETHREAD_VERSION\s*=\s*"([^"]+)"') {
        return $Matches[1]
    }
    throw "Could not read ROLETHREAD_VERSION from $Path"
}

function Resolve-InnoCompiler {
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $programFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    $programFiles = [Environment]::GetEnvironmentVariable("ProgramFiles")
    $localAppData = [Environment]::GetEnvironmentVariable("LOCALAPPDATA")
    $candidates = @()

    if ($localAppData) {
        $candidates += Join-Path $localAppData "Programs\Inno Setup 6\ISCC.exe"
    }

    if ($programFilesX86) {
        $candidates += Join-Path $programFilesX86 "Inno Setup 6\ISCC.exe"
    }

    if ($programFiles) {
        $candidates += Join-Path $programFiles "Inno Setup 6\ISCC.exe"
    }

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    throw @"
Inno Setup compiler was not found.

Install Inno Setup 6, or add ISCC.exe to PATH.
Recommended install command:
winget install --id JRSoftware.InnoSetup -e

Expected common locations:
- $localAppData\Programs\Inno Setup 6\ISCC.exe
- $programFilesX86\Inno Setup 6\ISCC.exe
- $programFiles\Inno Setup 6\ISCC.exe
"@
}

$version = Get-RoleThreadVersion -Path $versionFile
$expectedSetup = Join-Path $outputDir "RoleThreadLiteSetup-v$version.exe"
$bundleWasRebuilt = -not $UseExistingBundle

Write-Host "RoleThread Lite Inno Setup installer prototype"
Write-Host "Repository root: $repoRoot"
Write-Host "Repo version: $version"
Write-Host "Setup output version: $version"
Write-Host "Bundle folder: $bundleDir"
Write-Host "Inno script: $innoScript"
Write-Host ""

if ($BuildBundle -and $UseExistingBundle) {
    throw "Use either -BuildBundle or -UseExistingBundle, not both."
}

if (-not $UseExistingBundle) {
    Write-Host "Building fresh PyInstaller bundle before installer packaging..."
    & (Join-Path $PSScriptRoot "build_bundle.ps1")
    Write-Host ""
} else {
    Write-Host "Using existing PyInstaller bundle by explicit request."
    Write-Host "Version validation will still run before packaging."
    Write-Host ""
}

if (-not (Test-Path -LiteralPath $bundleExe)) {
    throw @"
PyInstaller bundle was not found:
$bundleExe

Build it first:
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\build_bundle.ps1

Then rerun this installer build. By default, build_installer.ps1 rebuilds the
bundle unless -UseExistingBundle is explicitly passed.
"@
}

if (-not (Test-Path -LiteralPath $bundleVersionFile)) {
    throw @"
Bundled RoleThread version file was not found:
$bundleVersionFile

The bundle is incomplete or stale. Rebuild it with:
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\build_bundle.ps1
"@
}

$bundleVersion = Get-RoleThreadVersion -Path $bundleVersionFile
Write-Host "Bundle version: $bundleVersion"
Write-Host "Bundle rebuilt this run: $bundleWasRebuilt"
Write-Host ""

if ($bundleVersion -ne $version) {
    throw @"
Refusing to build installer from a stale PyInstaller bundle.

Repo version:   $version
Bundle version: $bundleVersion

Rebuild the bundle before packaging:
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\build_installer.ps1

If you intentionally reuse an existing bundle, it must still match the repo version.
"@
}

if (-not (Test-Path -LiteralPath $innoScript)) {
    throw "Inno Setup script was not found: $innoScript"
}

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$iscc = Resolve-InnoCompiler
Write-Host "Using Inno compiler: $iscc"
Write-Host "Running Inno Setup..."

& $iscc "/DAppVersion=$version" $innoScript

if (-not (Test-Path -LiteralPath $expectedSetup)) {
    throw "Inno Setup finished but expected setup executable was not found: $expectedSetup"
}

Write-Host ""
Write-Host "Installer created:"
Write-Host $expectedSetup
