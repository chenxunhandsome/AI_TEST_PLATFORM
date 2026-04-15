param()

$mainRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$testRoot = Join-Path (Split-Path $mainRoot -Parent) "testhub_platform-test"
$stackScript = Join-Path $PSScriptRoot "start-stack.ps1"

if (-not (Test-Path $testRoot)) {
    throw "Missing test worktree: $testRoot"
}

& $stackScript -RepoRoot $testRoot
