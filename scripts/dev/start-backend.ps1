param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
)

$envFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $envFile)) {
    throw "Missing .env file: $envFile"
}

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$DefaultValue = ""
    )

    $line = Get-Content $Path | Where-Object { $_ -match "^$Key=" } | Select-Object -First 1
    if (-not $line) {
        return $DefaultValue
    }

    return ($line -replace "^$Key=", "").Trim()
}

$pythonCandidates = @(
    (Join-Path $RepoRoot "venv\\Scripts\\python.exe"),
    (Join-Path (Split-Path $RepoRoot -Parent) "testhub_platform-main\\venv\\Scripts\\python.exe")
)
$pythonExe = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $pythonExe) {
    throw "python.exe not found. Expected one of: $($pythonCandidates -join ', ')"
}

$backendPort = Get-EnvValue -Path $envFile -Key "BACKEND_PORT" -DefaultValue "8000"
Write-Host "Starting backend from $RepoRoot on port $backendPort"
& $pythonExe (Join-Path $RepoRoot "manage.py") runserver ("0.0.0.0:{0}" -f $backendPort) --noreload
