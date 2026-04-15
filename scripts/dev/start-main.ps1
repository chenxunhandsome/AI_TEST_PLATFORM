param()

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$stackScript = Join-Path $PSScriptRoot "start-stack.ps1"

& $stackScript -RepoRoot $repoRoot
