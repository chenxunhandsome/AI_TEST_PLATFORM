param(
    [string]$MainRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path,
    [string]$TestRoot = (Join-Path (Split-Path (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path -Parent) "testhub_platform-test"),
    [switch]$Push,
    [switch]$Fetch,
    [switch]$SkipMigrate,
    [switch]$AllowDirtyMain,
    [switch]$AllowDirtyTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Git {
    param(
        [string]$RepoRoot,
        [string[]]$Arguments
    )

    & git -C $RepoRoot @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed in $RepoRoot"
    }
}

function Get-GitOutput {
    param(
        [string]$RepoRoot,
        [string[]]$Arguments
    )

    $output = & git -C $RepoRoot @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed in $RepoRoot"
    }
    return @($output)
}

function Assert-RepoExists {
    param(
        [string]$RepoRoot,
        [string]$Name
    )

    if (-not (Test-Path $RepoRoot)) {
        throw "$Name repo not found: $RepoRoot"
    }
}

function Assert-Branch {
    param(
        [string]$RepoRoot,
        [string]$ExpectedBranch
    )

    $currentBranch = (Get-GitOutput -RepoRoot $RepoRoot -Arguments @('branch', '--show-current') | Select-Object -First 1).Trim()
    if ($currentBranch -ne $ExpectedBranch) {
        throw "Expected branch '$ExpectedBranch' in $RepoRoot but found '$currentBranch'"
    }
}

function Assert-CleanWorktree {
    param(
        [string]$RepoRoot,
        [string]$Name,
        [bool]$AllowDirty
    )

    $status = Get-GitOutput -RepoRoot $RepoRoot -Arguments @('status', '--short', '--untracked-files=all')
    if (-not $AllowDirty -and $status.Count -gt 0) {
        throw "$Name worktree is not clean:`n$($status -join [Environment]::NewLine)"
    }
}

function Get-PythonExe {
    param(
        [string]$RepoRoot
    )

    $candidates = @(
        (Join-Path $RepoRoot 'venv\\Scripts\\python.exe'),
        (Join-Path $MainRoot 'venv\\Scripts\\python.exe'),
        (Join-Path (Split-Path $RepoRoot -Parent) 'testhub_platform-main\\venv\\Scripts\\python.exe')
    )

    $pythonExe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $pythonExe) {
        throw "python.exe not found. Tried: $($candidates -join ', ')"
    }
    return $pythonExe
}

Assert-RepoExists -RepoRoot $MainRoot -Name 'main'
Assert-RepoExists -RepoRoot $TestRoot -Name 'test'

Assert-Branch -RepoRoot $MainRoot -ExpectedBranch 'main'
Assert-Branch -RepoRoot $TestRoot -ExpectedBranch 'test'

Assert-CleanWorktree -RepoRoot $MainRoot -Name 'main' -AllowDirty:$AllowDirtyMain.IsPresent
Assert-CleanWorktree -RepoRoot $TestRoot -Name 'test' -AllowDirty:$AllowDirtyTest.IsPresent

if ($Fetch) {
    Write-Host "Fetching remote branches..."
    Invoke-Git -RepoRoot $MainRoot -Arguments @('fetch', 'origin', '--prune')
}

Write-Host "Merging test into main with fast-forward only..."
Invoke-Git -RepoRoot $MainRoot -Arguments @('merge', '--ff-only', 'test')

if (-not $SkipMigrate) {
    $pythonExe = Get-PythonExe -RepoRoot $MainRoot
    Write-Host "Running migrations in main..."
    & $pythonExe (Join-Path $MainRoot 'manage.py') migrate
    if ($LASTEXITCODE -ne 0) {
        throw "manage.py migrate failed in $MainRoot"
    }
}

if ($Push) {
    Write-Host "Pushing test and main to origin..."
    Invoke-Git -RepoRoot $TestRoot -Arguments @('push', 'origin', 'test')
    Invoke-Git -RepoRoot $MainRoot -Arguments @('push', 'origin', 'main')
}

Write-Host "Publish completed."
Write-Host "main: $MainRoot"
Write-Host "test: $TestRoot"
