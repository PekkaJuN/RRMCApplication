# Container tests of the foundation spec (AC2, AC5, AC7, AC11, AC13, AC27).
#
# Runs against a separate Compose project `rrmc-test` with its own settings file, ports and
# folders, so the real app, .env, source/ and the real database are never touched.
# Nothing is deleted: the test volume and folders are kept, and the cleanup command is printed.
#
# Usage, from the project root:
#   powershell -ExecutionPolicy Bypass -File scripts/container-tests.ps1

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Project = "rrmc-test"
$BackendPort = 18000
$UiPort = 15173
$WorkDir = Join-Path $env:TEMP "rrmc-container-tests"
$Failures = New-Object System.Collections.Generic.List[string]

# Settings in the caller's shell would override the test settings files.
Get-ChildItem env: | Where-Object { $_.Name -like "RRMC_*" } |
    ForEach-Object { Remove-Item "env:$($_.Name)" }

function Write-Result([string]$Name, [bool]$Passed, [string]$Detail = "") {
    if ($Passed) {
        Write-Host "PASS $Name" -ForegroundColor Green
    } else {
        Write-Host "FAIL $Name $Detail" -ForegroundColor Red
        $Failures.Add($Name)
    }
}

# Runs docker with the given arguments; returns the combined output as one string.
function Invoke-Docker([string[]]$Arguments) {
    $output = & docker @Arguments 2>&1 | ForEach-Object { "$_" }
    return ($output -join "`n")
}

function New-SettingsFile([string]$Name, [hashtable]$Overrides) {
    $settings = [ordered]@{
        RRMC_IMPORT_DIR   = (Join-Path $WorkDir "import")
        RRMC_DONE_DIR     = (Join-Path $WorkDir "import_done")
        RRMC_FAILED_DIR   = (Join-Path $WorkDir "import_failed")
        RRMC_ENGINES      = "real"
        # Nothing listens on this port inside the container, so Ollama is unreachable.
        RRMC_OLLAMA_URL   = "http://127.0.0.1:9"
        RRMC_LOG_LEVEL    = "INFO"
        RRMC_BACKEND_PORT = "$BackendPort"
        RRMC_UI_PORT      = "$UiPort"
    }
    foreach ($key in $Overrides.Keys) { $settings[$key] = $Overrides[$key] }
    $path = Join-Path $WorkDir $Name
    $lines = $settings.Keys | ForEach-Object { "$_=$($settings[$_])" }
    [System.IO.File]::WriteAllLines($path, [string[]]$lines)
    return $path
}

# Runs `docker compose` for the test project with the given settings file.
function Invoke-Compose([string]$SettingsFile, [string[]]$Arguments) {
    $env:RRMC_ENV_FILE = $SettingsFile
    return Invoke-Docker (@("compose", "-p", $Project, "--env-file", $SettingsFile) + $Arguments)
}

function Wait-Health {
    for ($i = 0; $i -lt 60; $i++) {
        try {
            return Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 5
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    return $null
}

foreach ($folder in @("import", "import_done", "import_failed")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $WorkDir $folder) | Out-Null
}
$Settings = New-SettingsFile "settings.env" @{}

# AC2: every published port is bound to 127.0.0.1, and the port settings are used.
foreach ($case in @(@{ Backend = "8000"; Ui = "5173" }, @{ Backend = "8100"; Ui = "5200" })) {
    $file = New-SettingsFile "ports.env" @{
        RRMC_BACKEND_PORT = $case.Backend; RRMC_UI_PORT = $case.Ui
    }
    $config = Invoke-Compose $file @("config", "--format", "json") | ConvertFrom-Json
    $ports = @($config.services.backend.ports) + @($config.services.frontend.ports)
    $allLocal = @($ports | Where-Object { $_.host_ip -ne "127.0.0.1" }).Count -eq 0
    $published = "$($config.services.backend.ports[0].published)/$($config.services.frontend.ports[0].published)"
    Write-Result "AC2 ports $($case.Backend)/$($case.Ui) on 127.0.0.1" `
        ($allLocal -and $published -eq "$($case.Backend)/$($case.Ui)") "got $published"
}

# AC5: a missing settings file stops Compose before any container is created.
$missing = Join-Path $WorkDir "does-not-exist.env"
$output = Invoke-Compose $missing @("up", "-d", "--no-build")
$exitCode = $LASTEXITCODE
$containers = Invoke-Compose $Settings @("ps", "-a", "-q")
Write-Result "AC5 missing settings file stops start" `
    ($exitCode -ne 0 -and $output -match "does-not-exist\.env" -and $containers.Trim() -eq "") `
    "exit $exitCode, output: $output"

# AC7: an invalid setting stops the backend with one log line naming it.
$invalid = New-SettingsFile "invalid.env" @{ RRMC_ENGINES = "both" }
Invoke-Compose $invalid @("up", "-d", "--build", "backend") | Out-Null
$exitCode = (Invoke-Compose $invalid @("wait", "backend")).Trim()
$logs = Invoke-Compose $invalid @("logs", "backend")
Write-Result "AC7 invalid setting stops the backend" `
    ($exitCode -ne "0" -and $logs -match "Invalid setting RRMC_ENGINES: expected real or fake") `
    "exit $exitCode"
Invoke-Compose $invalid @("down") | Out-Null

# AC13: Tesseract in the image works; Ollama is unreachable.
Invoke-Compose $Settings @("up", "-d", "--build", "backend") | Out-Null
$health = Wait-Health
Write-Result "AC13 health: ocr ok, model unavailable" `
    ($null -ne $health -and $health.checks.ocr -eq "ok" -and $health.checks.model -eq "unavailable") `
    "health: $($health | ConvertTo-Json -Compress)"

# AC11: a row survives `down` and `up --build`.
$marker = [guid]::NewGuid().ToString()
$write = "import sqlite3; c = sqlite3.connect('/data/db/rrmc.db'); " +
    "c.execute('CREATE TABLE IF NOT EXISTS container_test (value TEXT)'); " +
    "c.execute('INSERT INTO container_test VALUES (?)', ('$marker',)); c.commit()"
$read = "import sqlite3; c = sqlite3.connect('/data/db/rrmc.db'); " +
    "print(c.execute('SELECT count(*) FROM container_test WHERE value = ?', ('$marker',)).fetchone()[0])"
Invoke-Compose $Settings @("exec", "-T", "backend", "python", "-c", $write) | Out-Null
Invoke-Compose $Settings @("down") | Out-Null
Invoke-Compose $Settings @("up", "-d", "--build", "backend") | Out-Null
Wait-Health | Out-Null
$count = (Invoke-Compose $Settings @("exec", "-T", "backend", "python", "-c", $read)).Trim()
Write-Result "AC11 data survives down and up --build" ($count -eq "1") "count: $count"
Invoke-Compose $Settings @("down") | Out-Null

# AC27: private files are ignored, .env.example is not.
$ignored = @(".env", "source/import/a.jpg", "source/import_failed/a.jpg", "data/rrmc.db",
    "frontend/test-results/x")
foreach ($path in $ignored) {
    & git check-ignore -q $path
    Write-Result "AC27 $path is ignored" ($LASTEXITCODE -eq 0)
}
# Model evaluation AC20: receipts, truth files and results under the evaluation folder.
foreach ($path in @("source/eval/a.jpg", "source/eval/a.jpg.truth.json",
        "source/eval/results/x/summary.md")) {
    & git check-ignore -q $path
    Write-Result "Evaluation AC20 $path is ignored" ($LASTEXITCODE -eq 0)
}
& git check-ignore -q ".env.example"
Write-Result "AC27 .env.example is not ignored" ($LASTEXITCODE -eq 1)

Remove-Item env:RRMC_ENV_FILE -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "The test containers are stopped. To remove the test volume and images, run:"
Write-Host "  docker compose -p $Project down -v --rmi local"
Write-Host "Test folders and settings files are in $WorkDir"

if ($Failures.Count -gt 0) {
    Write-Host "$($Failures.Count) container test(s) failed." -ForegroundColor Red
    exit 1
}
Write-Host "All container tests passed." -ForegroundColor Green
exit 0
