param(
    [switch]$BuildBundle
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$bundleDir = Join-Path $repoRoot "installer\windows\dist\RoleThreadLauncher"
$bundleExe = Join-Path $bundleDir "RoleThreadLauncher.exe"
$innoScript = Join-Path $repoRoot "installer\windows\inno\rolethread_lite.iss"
$outputDir = Join-Path $repoRoot "installer\windows\output"
$versionFile = Join-Path $repoRoot "core\version.py"

function Get-RoleThreadVersion {
    $versionText = Get-Content -LiteralPath $versionFile -Raw
    if ($versionText -match 'ROLETHREAD_VERSION\s*=\s*"([^"]+)"') {
        return $Matches[1]
    }
    throw "Could not read ROLETHREAD_VERSION from $versionFile"
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

$version = Get-RoleThreadVersion
$expectedSetup = Join-Path $outputDir "RoleThreadLiteSetup-v$version.exe"

Write-Host "RoleThread Lite Inno Setup installer prototype"
Write-Host "Repository root: $repoRoot"
Write-Host "Version: $version"
Write-Host "Bundle folder: $bundleDir"
Write-Host "Inno script: $innoScript"
Write-Host ""

if ($BuildBundle) {
    Write-Host "Building PyInstaller bundle first..."
    & (Join-Path $PSScriptRoot "build_bundle.ps1")
    Write-Host ""
}

if (-not (Test-Path -LiteralPath $bundleExe)) {
    throw @"
PyInstaller bundle was not found:
$bundleExe

Build it first:
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\build_bundle.ps1

Or run this script with -BuildBundle.
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
