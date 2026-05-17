param(
    [switch]$ConfirmDelete
)

$ErrorActionPreference = "Stop"

function Resolve-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Test-PathIsBelow {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $fullPath = Resolve-FullPath -Path $Path
    $fullParent = (Resolve-FullPath -Path $Parent).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $prefix = $fullParent + [System.IO.Path]::DirectorySeparatorChar
    return $fullPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-SafeCleanupTarget {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedParent
    )

    $fullPath = Resolve-FullPath -Path $Path
    $leaf = Split-Path -Leaf $fullPath

    if ([string]::IsNullOrWhiteSpace($fullPath)) {
        throw "Refusing to delete an empty path."
    }

    if ($leaf -ne "RoleThread") {
        throw "Refusing to delete '$fullPath' because the final folder is not 'RoleThread'."
    }

    if (-not (Test-PathIsBelow -Path $fullPath -Parent $ExpectedParent)) {
        throw "Refusing to delete '$fullPath' because it is not under '$ExpectedParent'."
    }

    if (Test-Path -LiteralPath (Join-Path $fullPath ".git")) {
        throw "Refusing to delete '$fullPath' because it appears to be a Git repository."
    }

    if (Test-Path -LiteralPath (Join-Path $fullPath ".venv")) {
        throw "Refusing to delete '$fullPath' because it contains a Python virtual environment."
    }

    return $fullPath
}

if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    throw "LOCALAPPDATA is not defined. Cannot resolve RoleThread app data."
}

if ([string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
    throw "USERPROFILE is not defined. Cannot resolve RoleThread workspace data."
}

$targets = @(
    [pscustomobject]@{
        Name = "RoleThread local app data"
        Path = Join-Path $env:LOCALAPPDATA "RoleThread"
        Parent = $env:LOCALAPPDATA
        Deletes = @(
            "database and app state",
            "preferences",
            "logs",
            "cache"
        )
    },
    [pscustomobject]@{
        Name = "RoleThread user workspace"
        Path = Join-Path $env:USERPROFILE "RoleThread"
        Parent = $env:USERPROFILE
        Deletes = @(
            "training data",
            "imports",
            "exports",
            "backups",
            "workspace data"
        )
    }
)

Write-Host "RoleThread developer user-data cleanup"
Write-Host ""
Write-Host "WARNING: This deletes local RoleThread app data and workspace folders."
Write-Host "Use only for installer/dev testing when the data can be deleted."
Write-Host ""

if ($ConfirmDelete) {
    Write-Host "Mode: DESTRUCTIVE cleanup enabled by -ConfirmDelete"
} else {
    Write-Host "Mode: dry run. No files or folders will be deleted."
}

Write-Host ""
Write-Host "Targets:"

foreach ($target in $targets) {
    $exists = Test-Path -LiteralPath $target.Path
    Write-Host ""
    Write-Host "- $($target.Name)"
    Write-Host "  Path: $($target.Path)"
    Write-Host "  Exists: $exists"
    Write-Host "  Deletes:"
    foreach ($item in $target.Deletes) {
        Write-Host "    - $item"
    }
}

if (-not $ConfirmDelete) {
    Write-Host ""
    Write-Host "Dry run complete. To delete these folders, run:"
    Write-Host "powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\clean_rolethread_user_data.ps1 -ConfirmDelete"
    exit 0
}

Write-Host ""
Write-Host "Starting destructive cleanup..."

foreach ($target in $targets) {
    if (-not (Test-Path -LiteralPath $target.Path)) {
        Write-Host "Skipping missing target: $($target.Path)"
        continue
    }

    $safePath = Assert-SafeCleanupTarget -Path $target.Path -ExpectedParent $target.Parent
    Write-Host "Deleting: $safePath"
    Remove-Item -LiteralPath $safePath -Recurse -Force
}

Write-Host ""
Write-Host "RoleThread developer cleanup complete."
