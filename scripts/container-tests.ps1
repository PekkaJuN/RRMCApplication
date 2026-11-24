# Container tests of the foundation spec (AC2, AC5, AC7, AC11, AC13, AC27) and the later specs
# named in the check names, among them the run environment (app-container).
#
# Runs against separate Compose projects `rrmc-test` and `rrmc-app-test` with their own settings
# files, ports, image name, folders and volumes, so the real apps, .env, source/ and the real
# databases are never touched. A script of scripts/ runs only when it takes the test parameters.
# The test databases and the files in the test folders are emptied and written; the volumes,
# images, folders and clones are kept, and the cleanup commands are printed.
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
        RRMC_ARCHIVE_DIR  = (Join-Path $WorkDir "archived")
        RRMC_ENGINES      = "real"
        # Nothing listens on this port inside the container, so Ollama is unreachable.
        RRMC_OLLAMA_URL   = "http://127.0.0.1:9"
        RRMC_LOG_LEVEL    = "INFO"
        RRMC_BACKEND_PORT = "$BackendPort"
        RRMC_UI_PORT      = "$UiPort"
    }
    foreach ($key in $Overrides.Keys) { $settings[$key] = $Overrides[$key] }
    $path = Join-Path $WorkDir $Name
    $lines = $settings.Keys | Where-Object { $null -ne $settings[$_] } |
        ForEach-Object { "$_=$($settings[$_])" }
    [System.IO.File]::WriteAllLines($path, [string[]]$lines)
    return $path
}

# Runs `docker compose` for the test project with the given settings file.
function Invoke-Compose([string]$SettingsFile, [string[]]$Arguments) {
    $env:RRMC_ENV_FILE = $SettingsFile
    return Invoke-Docker (@("compose", "-p", $Project, "--env-file", $SettingsFile) + $Arguments)
}

# Test isolation (specs/features/test-isolation.md): returns the problems of one service in
# the output of `docker compose config --format json`. Mounts are compared with an allow list
# of "type:source->target" entries; a bind source is relative to the project root.
function Get-IsolationProblems($Config, [string]$Service, [string[]]$AllowedMounts,
        [bool]$ExpectTmpfs, [hashtable]$AllowedEnv) {
    $problems = New-Object System.Collections.Generic.List[string]
    $definition = $Config.services.$Service
    if ($null -eq $definition) {
        $problems.Add("service $Service is missing")
        return $problems
    }
    foreach ($mount in @($definition.volumes | Where-Object { $null -ne $_ })) {
        $source = "$($mount.source)"
        if ($mount.type -eq "bind" -and $source.StartsWith($ProjectRoot)) {
            $source = $source.Substring($ProjectRoot.Length).TrimStart("\", "/") -replace "\\", "/"
        }
        $key = "$($mount.type):$source->$($mount.target)"
        if ($AllowedMounts -notcontains $key) { $problems.Add("mount $key") }
    }
    if ($ExpectTmpfs -and @($definition.tmpfs) -notcontains "/data") {
        $problems.Add("/data is not tmpfs")
    }
    if ($null -ne $definition.environment) {
        foreach ($variable in $definition.environment.PSObject.Properties) {
            $allowed = $AllowedEnv.ContainsKey($variable.Name) -and
                $AllowedEnv[$variable.Name] -eq "$($variable.Value)"
            if (-not $allowed) { $problems.Add("environment $($variable.Name)") }
        }
    }
    return $problems
}

$BackendTestMounts = @("bind:backend->/app")
$FrontendTestMounts = @("bind:frontend->/app", "volume:rrmc-node-modules->/app/node_modules")
$FakeEngines = @{ RRMC_ENGINES = "fake" }

function Wait-Health([int]$Port = $BackendPort) {
    for ($i = 0; $i -lt 60; $i++) {
        try {
            return Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 5
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    return $null
}

foreach ($folder in @("import", "import_done", "import_failed", "archived")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $WorkDir $folder) | Out-Null
}
$Settings = New-SettingsFile "settings.env" @{}

# Archiving AC32: the backend mounts the archive folder from RRMC_ARCHIVE_DIR at /data/archived.
$config = Invoke-Compose $Settings @("config", "--format", "json") | ConvertFrom-Json
$archiveMount = @($config.services.backend.volumes | Where-Object { $_.target -eq "/data/archived" })
$expected = Join-Path $WorkDir "archived"
Write-Result "Archiving AC32 backend mounts RRMC_ARCHIVE_DIR at /data/archived" `
    ($archiveMount.Count -eq 1 -and "$($archiveMount[0].source)" -eq $expected) `
    "got: $($archiveMount | ConvertTo-Json -Compress)"

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

# Test isolation AC1, AC2, AC5: the test containers mount no real data and get no settings
# file values.
$isolationConfig = Invoke-Compose $Settings @("--profile", "test", "--profile", "e2e",
    "config", "--format", "json") | ConvertFrom-Json
$problems = Get-IsolationProblems $isolationConfig "backend-test" $BackendTestMounts $true $FakeEngines
Write-Result "Isolation AC1 AC5 backend-test mounts and environment" ($problems.Count -eq 0) ($problems -join "; ")
$problems = Get-IsolationProblems $isolationConfig "frontend-test" $FrontendTestMounts $false @{}
Write-Result "Isolation AC2 AC5 frontend-test mounts and environment" ($problems.Count -eq 0) ($problems -join "; ")
$problems = Get-IsolationProblems $isolationConfig "backend-e2e" @("bind:backend->/app",
    "volume:rrmc-e2e-import->/data/import", "volume:rrmc-e2e-failed->/data/import_failed") `
    $true $FakeEngines
Write-Result "Isolation AC5 AC10 backend-e2e gets no settings file values" ($problems.Count -eq 0) ($problems -join "; ")

# Isolation AC11: a test container that mounts a data folder is reported.
$override = Join-Path $WorkDir "isolation-broken.yaml"
[System.IO.File]::WriteAllLines($override, [string[]]@(
    "services:", "  backend-test:", "    volumes:",
    "      - $((Join-Path $WorkDir 'import') -replace '\\', '/'):/data/import"))
$env:RRMC_ENV_FILE = $Settings
$brokenConfig = Invoke-Docker @("compose", "-p", $Project, "--env-file", $Settings,
    "-f", "compose.yaml", "-f", $override, "--profile", "test", "config", "--format", "json") |
    ConvertFrom-Json
$problems = Get-IsolationProblems $brokenConfig "backend-test" $BackendTestMounts $true $FakeEngines
Write-Result "Isolation AC11 a mounted data folder is reported" `
    (@($problems | Where-Object { $_ -like "mount bind:*->/data/import" }).Count -eq 1) ($problems -join "; ")

# Isolation AC4: the test containers start without a settings file.
$env:RRMC_ENV_FILE = Join-Path $WorkDir "does-not-exist.env"
$backendOk = Invoke-Docker @("compose", "-p", $Project, "--env-file", $Settings, "run", "--rm",
    "backend-test", "python", "-c", "print('isolation-ok')")
$frontendOk = Invoke-Docker @("compose", "-p", $Project, "--env-file", $Settings, "run", "--rm",
    "frontend-test", "node", "-e", "console.log('isolation-ok')")
Write-Result "Isolation AC4 test containers start without a settings file" `
    ($backendOk -match "isolation-ok" -and $frontendOk -match "isolation-ok")

# Isolation AC3: /data is empty in backend-test, although the test import folder holds a file
# and the test database volume exists (AC11 above).
[System.IO.File]::WriteAllText((Join-Path $WorkDir "import\isolation-check.jpg"), "synthetic")
$listing = "from pathlib import Path; print(sorted(p.name for p in Path('/data').rglob('*')))"
# Compose prints its progress lines into the same output, so take the printed list only.
$listingOutput = Invoke-Compose $Settings @("run", "--rm", "backend-test", "python", "-c", $listing)
$dataFiles = "$($listingOutput -split "`n" | Where-Object { $_ -match "^\s*\[" } |
    Select-Object -Last 1)".Trim()
Write-Result "Isolation AC3 /data is empty in backend-test" ($dataFiles -eq "[]") "got $dataFiles"

# Isolation AC7: pytest refuses to run in the app's backend service, which mounts data.
$refusal = Invoke-Compose $Settings @("run", "--rm", "backend", "pytest", "-q", "-p", "no:cacheprovider")
$exitCode = $LASTEXITCODE
$refusalLines = @($refusal -split "`n" | Where-Object { $_ -match "Refusing to run tests" })
Write-Result "Isolation AC7 pytest refuses next to data" `
    ($exitCode -eq 2 -and $refusalLines.Count -eq 1 -and
        $refusalLines[0] -match "docker compose run --rm backend-test pytest" -and
        $refusal -notmatch "passed") "exit $exitCode"

# AC27: private files are ignored, .env.example is not.
$ignored = @(".env", "source/import/a.jpg", "source/import_failed/a.jpg", "data/rrmc.db",
    "frontend/test-results/x")
foreach ($path in $ignored) {
    & git check-ignore -q $path
    Write-Result "AC27 $path is ignored" ($LASTEXITCODE -eq 0)
}
# App AC33: app data inside the repository, when the user sets RRMC_APP_SOURCE_DIR so.
foreach ($path in @("source/app/import/a.jpg", "source/app/import_done/a.jpg", "backend/static/index.html")) {
    & git check-ignore -q $path
    Write-Result "App AC33 $path is ignored" ($LASTEXITCODE -eq 0)
}
# Model evaluation AC20: receipts, truth files and results under the evaluation folder.
foreach ($path in @("source/eval/a.jpg", "source/eval/a.jpg.truth.json",
        "source/eval/results/x/summary.md")) {
    & git check-ignore -q $path
    Write-Result "Evaluation AC20 $path is ignored" ($LASTEXITCODE -eq 0)
}
& git check-ignore -q ".env.example"
Write-Result "AC27 .env.example is not ignored" ($LASTEXITCODE -eq 1)

# --- Run environment (specs/features/app-container.md) ------------------------------------
# Its own Compose project, image name, port, folders and volume: the real rrmc-app project,
# image and volume are never touched.

$AppProject = "rrmc-app-test"
$AppImage = "rrmc-app-test"
$AppPort = 18080
$AppVolume = "rrmc-app-test-data"
$AppSource = Join-Path $WorkDir "app\source"
$AppFolders = @("import", "import_done", "import_failed", "archived")

# A settings file of the run environment; an override of $null leaves the setting out.
function New-AppSettingsFile([string]$Name, [hashtable]$Overrides) {
    $settings = @{
        RRMC_APP_IMAGE = $AppImage; RRMC_APP_PORT = "$AppPort"
        RRMC_APP_SOURCE_DIR = ($AppSource -replace "\\", "/"); RRMC_APP_DB_VOLUME = $AppVolume
    }
    foreach ($key in $Overrides.Keys) { $settings[$key] = $Overrides[$key] }
    return New-SettingsFile $Name $settings
}

# Runs `docker compose` for the test project of the run environment.
function Invoke-App([string]$SettingsFile, [string[]]$Arguments, [string[]]$MoreFiles = @()) {
    $env:RRMC_ENV_FILE = $SettingsFile
    $files = @("-f", "compose.app.yaml")
    foreach ($file in $MoreFiles) { $files += @("-f", $file) }
    return Invoke-Docker (@("compose", "-p", $AppProject, "--env-file", $SettingsFile) + $files + $Arguments)
}

function Get-AppConfig([string]$SettingsFile, [string[]]$MoreFiles = @()) {
    $output = Invoke-App $SettingsFile @("config", "--format", "json") $MoreFiles
    try { return $output | ConvertFrom-Json } catch { return $null }
}

# The app's mounts must be exactly the four folders and the database volume.
function Get-AppMountProblems($Config, [string]$SourceDir, [string]$VolumeName) {
    $problems = New-Object System.Collections.Generic.List[string]
    if ($null -eq $Config) { $problems.Add("no configuration"); return $problems }
    # Compose keeps the separators of an absolute path as the setting writes them (AC9).
    $root = $SourceDir -replace "\\", "/"
    $allowed = @($AppFolders | ForEach-Object { "bind:$root/$_->/data/$_" })
    $allowed += "volume:app-db->/data/db"
    foreach ($problem in (Get-IsolationProblems $Config "app" $allowed $false @{})) {
        if ($problem -notlike "environment *") { $problems.Add($problem) }
    }
    $count = @($Config.services.app.volumes | Where-Object { $null -ne $_ }).Count
    if ($count -ne $allowed.Count) { $problems.Add("$count mounts") }
    if ("$($Config.volumes.'app-db'.name)" -ne $VolumeName) { $problems.Add("volume name") }
    return $problems
}

foreach ($folder in $AppFolders) {
    New-Item -ItemType Directory -Force -Path (Join-Path $AppSource $folder) | Out-Null
}
$AppSettings = New-AppSettingsFile "app.env" @{}

# App AC7: one port, on 127.0.0.1, from the settings.
foreach ($case in @(@{ Setting = $null; Port = "8080" }, @{ Setting = "8180"; Port = "8180" })) {
    $file = New-AppSettingsFile "app-ports.env" @{ RRMC_APP_PORT = $case.Setting }
    $ports = @((Get-AppConfig $file).services.app.ports | Where-Object { $null -ne $_ })
    Write-Result "App AC7 one port $($case.Port) on 127.0.0.1" `
        ($ports.Count -eq 1 -and $ports[0].host_ip -eq "127.0.0.1" -and
            "$($ports[0].published)" -eq $case.Port -and "$($ports[0].target)" -eq "8000") `
        "got: $($ports | ConvertTo-Json -Compress)"
}

# App AC8, AC9: the mounts with test values and with the defaults.
$problems = @(Get-AppMountProblems (Get-AppConfig $AppSettings) $AppSource $AppVolume)
Write-Result "App AC8 AC32 app mounts only app data" ($problems.Count -eq 0) ($problems -join "; ")
$file = New-AppSettingsFile "app-defaults.env" @{ RRMC_APP_SOURCE_DIR = $null; RRMC_APP_DB_VOLUME = $null }
$problems = @(Get-AppMountProblems (Get-AppConfig $file) "C:\MyApps\RRMCApplication\source" "rrmc-app-data")
Write-Result "App AC9 default app data" ($problems.Count -eq 0) ($problems -join "; ")

# App AC10: the engines are real, whatever the settings file says.
$file = New-AppSettingsFile "app-engines.env" @{ RRMC_ENGINES = "fake" }
$engines = "$((Get-AppConfig $file).services.app.environment.RRMC_ENGINES)"
Write-Result "App AC10 real engines always" ($engines -eq "real") "got $engines"

# App AC11: a missing settings file stops the start before any container is created.
$env:RRMC_ENV_FILE = $missing
$output = Invoke-Docker @("compose", "-p", $AppProject, "--env-file", $AppSettings,
    "-f", "compose.app.yaml", "up", "-d", "--no-build")
$exitCode = $LASTEXITCODE
$containers = Invoke-App $AppSettings @("ps", "-a", "-q")
$psExit = $LASTEXITCODE
Write-Result "App AC11 missing settings file stops start" `
    ($exitCode -ne 0 -and $output -match "does-not-exist\.env" -and
        $psExit -eq 0 -and $containers.Trim() -eq "") "exit $exitCode, output: $output"

# App AC32: source code mounted into the app is reported.
$override = Join-Path $WorkDir "app-broken.yaml"
[System.IO.File]::WriteAllLines($override, [string[]]@(
    "services:", "  app:", "    volumes:", "      - ./backend:/app"))
$problems = @(Get-AppMountProblems (Get-AppConfig $AppSettings @($override)) $AppSource $AppVolume)
Write-Result "App AC32 mounted source code is reported" `
    ($problems -contains "mount bind:backend->/app") ($problems -join "; ")

# Runs a shell command in a new app container as root, so that it can read every folder.
function Invoke-AppShell([string]$Script) {
    return Invoke-App $AppSettings @("run", "--rm", "--no-deps", "--user", "0", "app", "sh", "-c", $Script)
}

# The text after `<marker>:` in output that also holds Compose's progress lines.
function Get-Marked([string]$Output, [string]$Marker) {
    foreach ($line in ($Output -split "`n")) {
        if ($line -match "^${Marker}:(.*)$") { return $Matches[1].Trim() }
    }
    return $null
}

# Empties the test volume; refuses any other volume.
function Reset-AppDatabase {
    if ("$((Get-AppConfig $AppSettings).volumes.'app-db'.name)" -ne "rrmc-app-test-data") {
        throw "not the test volume"
    }
    Invoke-AppShell "rm -f /data/db/rrmc.db*" | Out-Null
}

# Returns @{ Status; Type; Body } of a GET to the test app.
function Get-AppPage([string]$Path) {
    $lines = @(& curl.exe -s --path-as-is -w "\n%{http_code} %{content_type}" "http://127.0.0.1:$AppPort$Path")
    $status = "$($lines[-1])" -split " ", 2
    return @{ Status = $status[0]; Type = "$($status[1])"; Body = ($lines[0..($lines.Count - 2)] -join "`n") }
}

$buildOutput = Invoke-App $AppSettings @("build")
Write-Result "App image builds" ($LASTEXITCODE -eq 0) $buildOutput
Reset-AppDatabase

# App AC1-AC2: the image holds the app and no development tools, settings or data.
$output = Invoke-AppShell ('echo TOOLS: $(command -v pytest ruff pyright pip-audit node npm); ' +
    'command -v pytest ruff pyright pip-audit node npm > /dev/null; echo CODE: $?; ' +
    'echo LANGS: $(tesseract --list-langs 2>&1 | tail -n +2)')
$langs = "$(Get-Marked $output 'LANGS')" -split " "
$code = Get-Marked $output "CODE"
Write-Result "App AC1 no development tools; Tesseract languages" `
    ((Get-Marked $output "TOOLS") -eq "" -and $null -ne $code -and $code -ne "0" -and
        $langs -contains "eng" -and $langs -contains "fin") $output
$output = Invoke-AppShell ('echo LIST: $(ls -A /app); ' +
    'echo ENV: $(find / -path /proc -prune -o -name .env -print)')
Write-Result "App AC2 the image holds only the app" `
    ((Get-Marked $output "LIST") -eq "app pyproject.toml static uv.lock" -and
        (Get-Marked $output "ENV") -eq "") $output

# App AC3-AC6: one port for the UI and the API, not run as root.
Invoke-App $AppSettings @("up", "-d", "--no-build") | Out-Null
$health = Wait-Health $AppPort
$user = "$(Get-Marked (Invoke-App $AppSettings @("exec", "-T", "app", "sh", "-c", 'echo UID: $(id -u)')) 'UID')"
Write-Result "App AC3 not run as root" ($user -match "^\d+$" -and $user -ne "0") "uid $user"
foreach ($path in @("/", "/tuonti", "/kuitit/12")) {
    $page = Get-AppPage $path
    Write-Result "App AC4 $path answers the UI" `
        ($page.Status -eq "200" -and $page.Type -like "text/html*" -and
            $page.Body.Contains('<div id="root"></div>')) "$($page.Status) $($page.Type)"
}
Write-Result "App AC4 /api/health answers on the same port" `
    ($null -ne $health -and $health.checks.ocr -eq "ok") "health: $($health | ConvertTo-Json -Compress)"
$scriptPath = if ((Get-AppPage "/").Body -match '<script type="module"[^>]* src="([^"]+)"') { $Matches[1] } else { "" }
$page = Get-AppPage $scriptPath
Write-Result "App AC5 the UI's script is served" `
    ($scriptPath -ne "" -and $page.Status -eq "200" -and $page.Type -match "javascript") `
    "$scriptPath $($page.Status) $($page.Type)"
$page = Get-AppPage "/api/does-not-exist"
Write-Result "App AC6 an unknown API path is a JSON 404" `
    ($page.Status -eq "404" -and $page.Type -like "application/json*") "$($page.Status) $($page.Type)"

# App AC13: a row survives `down` and `up --build`.
Invoke-App $AppSettings @("exec", "-T", "app", "python", "-c", $write) | Out-Null
Invoke-App $AppSettings @("down") | Out-Null
Invoke-App $AppSettings @("up", "-d", "--build") | Out-Null
Wait-Health $AppPort | Out-Null
$count = (Invoke-App $AppSettings @("exec", "-T", "app", "python", "-c", $read)).Trim()
Write-Result "App AC13 data survives down and up --build" ($count -eq "1") "count: $count"
Invoke-App $AppSettings @("down") | Out-Null

# App AC12: an invalid setting stops the app with one log line naming it.
$file = New-AppSettingsFile "app-invalid.env" @{ RRMC_LOG_LEVEL = "LOUD" }
Invoke-App $file @("up", "-d", "--no-build") | Out-Null
# Compose prints a sentence that ends with the status code.
$waitOutput = (Invoke-App $file @("wait", "app")).Trim()
$exitCode = if ($waitOutput -match "(\d+)$") { $Matches[1] } else { "unknown: $waitOutput" }
$logs = Invoke-App $file @("logs", "app")
Write-Result "App AC12 invalid setting stops the app" `
    ($exitCode -match "^\d+$" -and $exitCode -ne "0" -and
        $logs -match "Invalid setting RRMC_LOG_LEVEL: expected DEBUG, INFO, WARNING or ERROR") `
    "exit $exitCode"
Invoke-App $file @("down") | Out-Null

# Runs a script of scripts/ in its own process. Returns @{ Exit; Output }.
function Invoke-Script([string]$Path, [string[]]$Arguments, [string]$InputText = "") {
    # A script without the test parameters would ignore them and work on the real data.
    $parameters = @((Get-Command $Path -ErrorAction SilentlyContinue).Parameters.Keys)
    $advanced = (Test-Path $Path) -and (Get-Content -Raw $Path) -match "(?m)^\[CmdletBinding\("
    if (-not $advanced -or $parameters -notcontains "EnvFile") {
        return @{ Exit = -1; Output = "not run: $Path does not take the test parameters" }
    }
    Remove-Item env:RRMC_ENV_FILE -ErrorAction SilentlyContinue
    $output = $InputText | & powershell -NoProfile -ExecutionPolicy Bypass -File $Path @Arguments 2>&1 |
        ForEach-Object { "$_" }
    return @{ Exit = $LASTEXITCODE; Output = ($output -join "`n") }
}

function Get-InsertCode([string]$Value) {
    return "import sqlite3; c = sqlite3.connect('/data/db/rrmc.db'); " +
        "c.execute('CREATE TABLE IF NOT EXISTS container_test (value TEXT)'); " +
        "c.execute('INSERT INTO container_test VALUES (?)', ('$Value',)); c.commit(); c.close()"
}

# Prints COUNT:<rows with the value> and CHECK:<integrity> of a database file.
function Get-CountCode([string]$Path, [string]$Value) {
    return "import shutil, sqlite3; shutil.copyfile('$Path', '/tmp/check.db'); " +
        "c = sqlite3.connect('/tmp/check.db'); " +
        "print('COUNT:%d' % c.execute('SELECT count(*) FROM container_test WHERE value = ?', ('$Value',)).fetchone()[0]); " +
        "print('CHECK:' + c.execute('PRAGMA integrity_check').fetchone()[0])"
}

# The rows with the value in a backup file, or -1 when the file is not sound.
function Get-BackupCount([string]$Folder, [string]$Name, [string]$Value) {
    $output = Invoke-App $AppSettings @("run", "--rm", "--no-deps", "-v", "${Folder}:/check:ro", "app",
        "python", "-c", (Get-CountCode "/check/$Name" $Value))
    if ((Get-Marked $output "CHECK") -ne "ok") { return -1 }
    return [int](Get-Marked $output "COUNT")
}

$hashCode = "import hashlib, pathlib; " +
    "print('HASH:' + hashlib.sha256(pathlib.Path('/data/db/rrmc.db').read_bytes()).hexdigest())"
function Get-DevHash {
    return Get-Marked (Invoke-Compose $Settings @("run", "--rm", "--no-deps", "backend", "python", "-c", $hashCode)) "HASH"
}

$BackupScript = Join-Path $PSScriptRoot "backup-db.ps1"
$RestoreScript = Join-Path $PSScriptRoot "restore-db.ps1"
$BackupDir = Join-Path $WorkDir ("app\backup-" + (Get-Date -Format "yyyyMMddHHmmss"))
$AppTestArgs = @("-ComposeProject", $AppProject, "-EnvFile", $AppSettings)
$DevTestArgs = @("-ComposeProject", $Project, "-EnvFile", $Settings)
$appRow = "app-" + [guid]::NewGuid().ToString()
$devRow = "dev-" + [guid]::NewGuid().ToString()
$lateRow = "late-" + [guid]::NewGuid().ToString()
Invoke-App $AppSettings @("run", "--rm", "--no-deps", "app", "python", "-c", (Get-InsertCode $appRow)) | Out-Null
Invoke-Compose $Settings @("run", "--rm", "--no-deps", "backend", "python", "-c", (Get-InsertCode $devRow)) | Out-Null
$devHash = Get-DevHash

# App AC23: a backup of the run environment, in a new folder.
$result = Invoke-Script $BackupScript (@("-Target", "app", "-BackupDir", $BackupDir) + $AppTestArgs)
$files = @(Get-ChildItem $BackupDir -ErrorAction SilentlyContinue)
$appBackup = if ($files.Count -eq 1) { $files[0].Name } else { "" }
Write-Result "App AC23 backup -Target app" `
    ($result.Exit -eq 0 -and $appBackup -match "^rrmc-app-\d{4}-\d{2}-\d{2}_\d{6}\.db$" -and
        (Get-BackupCount $BackupDir $appBackup $appRow) -eq 1 -and
        (Get-BackupCount $BackupDir $appBackup $devRow) -eq 0) "exit $($result.Exit): $($result.Output)"
Write-Result "App AC23 default backup folder" `
    ((Get-Content -Raw $BackupScript).Contains('"C:\MyApps\RRMCApplication\backup"'))

# App AC24: without -Target the development database is backed up, named as before.
$devBackupDir = "$BackupDir-dev"
$result = Invoke-Script $BackupScript (@("-BackupDir", $devBackupDir) + $DevTestArgs)
$files = @(Get-ChildItem $devBackupDir -ErrorAction SilentlyContinue)
Write-Result "App AC24 backup defaults to development" `
    ($result.Exit -eq 0 -and $files.Count -eq 1 -and
        $files[0].Name -match "^rrmc-\d{4}-\d{2}-\d{2}_\d{6}\.db$" -and
        (Get-BackupCount $devBackupDir $files[0].Name $devRow) -eq 1) "exit $($result.Exit): $($result.Output)"

# App AC25: restore of the run environment while the app runs.
Invoke-App $AppSettings @("run", "--rm", "--no-deps", "app", "python", "-c", (Get-InsertCode $lateRow)) | Out-Null
Invoke-App $AppSettings @("up", "-d", "--no-build") | Out-Null
Wait-Health $AppPort | Out-Null
$result = Invoke-Script $RestoreScript (@("-Target", "app", "-BackupFile", (Join-Path $BackupDir $appBackup),
    "-BackupDir", $BackupDir) + $AppTestArgs) "RESTORE"
$undo = @(Get-ChildItem $BackupDir -Filter "rrmc-app-*-before-restore.db" -ErrorAction SilentlyContinue)
$running = (Invoke-App $AppSettings @("ps", "--status", "running", "-q", "app")).Trim()
$devRunning = (Invoke-Compose $Settings @("ps", "--status", "running", "-q")).Trim()
Wait-Health $AppPort | Out-Null
Invoke-App $AppSettings @("stop") | Out-Null
$late = Invoke-App $AppSettings @("run", "--rm", "--no-deps", "app", "python", "-c", (Get-CountCode "/data/db/rrmc.db" $lateRow))
$kept = Invoke-App $AppSettings @("run", "--rm", "--no-deps", "app", "python", "-c", (Get-CountCode "/data/db/rrmc.db" $appRow))
$undoCount = if ($undo.Count -eq 1) { Get-BackupCount $BackupDir $undo[0].Name $lateRow } else { -1 }
Write-Result "App AC25 restore -Target app" `
    ($result.Exit -eq 0 -and $undoCount -eq 1 -and $running -ne "" -and
        (Get-Marked $late "COUNT") -eq "0" -and (Get-Marked $kept "COUNT") -eq "1") `
    "exit $($result.Exit), undo $undoCount, running '$running': $($result.Output)"
Write-Result "App AC25 restore leaves development untouched" `
    ($null -ne $devHash -and (Get-DevHash) -eq $devHash -and $devRunning -eq "")
Invoke-App $AppSettings @("down") | Out-Null

# App AC26: another target is refused before the script body runs.
$result = Invoke-Script $BackupScript (@("-Target", "prod", "-BackupDir", $BackupDir) + $AppTestArgs)
$result2 = Invoke-Script $RestoreScript (@("-Target", "prod", "-BackupFile", "x") + $AppTestArgs)
Write-Result "App AC26 invalid target is refused" `
    ($result.Exit -ne 0 -and $result.Output -match "ParameterArgumentValidationError" -and
        $result2.Exit -ne 0 -and $result2.Output -match "ParameterArgumentValidationError") `
    "$($result.Output) $($result2.Output)"

# App T6: half of the test parameters could reach real data, so it is refused.
$result = Invoke-Script $BackupScript @("-Target", "app", "-BackupDir", $BackupDir, "-ComposeProject", $AppProject)
Write-Result "App T6 test parameters only together" `
    ($result.Exit -eq 1 -and $result.Output -match "must be given together") $result.Output

# --- One-time copy: rrmc-test is the development side, with synthetic data only. ---
$CopyScript = Join-Path $PSScriptRoot "copy-to-app.ps1"
# The app's settings file holds the development settings too.
$CopyArgs = @("-DevProject", $Project, "-AppProject", $AppProject, "-EnvFile", $AppSettings)

# Runs Python in the development side's backend; refuses any volume but the test one.
function Invoke-DevPython([string]$Code) {
    $config = Invoke-Compose $Settings @("config", "--format", "json") | ConvertFrom-Json
    if ("$($config.volumes.'rrmc-data'.name)" -ne "rrmc-test_rrmc-data") { throw "not the test volume" }
    return Invoke-Compose $Settings @("run", "--rm", "--no-deps", "backend", "python", "-c", $Code)
}

$clearCode = "import pathlib; [p.unlink() for p in pathlib.Path('/data/db').glob('rrmc.db*')]"
function Reset-DevDatabase { Invoke-DevPython $clearCode | Out-Null }
function New-DevDatabase {
    Reset-DevDatabase
    Invoke-Compose $Settings @("run", "--rm", "--no-deps", "backend", "python", "-m", "app.prestart") | Out-Null
}

function Clear-Files([string]$Folder) {
    if (-not $Folder.StartsWith((Join-Path $env:TEMP "rrmc-container-tests"))) { throw "not a test folder" }
    Get-ChildItem -LiteralPath $Folder -Recurse -File -Force | Remove-Item -Force
}

# "relative path=hash" of every file under a folder.
function Get-FileHashes([string]$Folder) {
    return (@(Get-ChildItem -LiteralPath $Folder -Recurse -File -Force | ForEach-Object {
        "$($_.FullName.Substring($Folder.Length))=$((Get-FileHash -LiteralPath $_.FullName).Hash)"
    } | Sort-Object) -join ";")
}
function Get-DevFileHashes { return (@($AppFolders | ForEach-Object { Get-FileHashes (Join-Path $WorkDir $_) }) -join "|") }
function Get-AppFileHashes { return (@($AppFolders | ForEach-Object { Get-FileHashes (Join-Path $AppSource $_) }) -join "|") }

# The names in the app's database folder, and the hash of its database.
function Get-AppDatabaseFiles { return Get-Marked (Invoke-AppShell 'echo FILES: $(ls -A /data/db)') "FILES" }
function Get-AppHash {
    return Get-Marked (Invoke-App $AppSettings @("run", "--rm", "--no-deps", "app", "python", "-c", $hashCode)) "HASH"
}

Reset-AppDatabase
Clear-Files $AppSource
foreach ($folder in $AppFolders) {
    $dev = Join-Path $WorkDir $folder
    Clear-Files $dev
    New-Item -ItemType Directory -Force -Path (Join-Path $dev "sub") | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $dev "synthetic-1.jpg"), "synthetic 1 $folder")
    [System.IO.File]::WriteAllText((Join-Path $dev "sub\synthetic-2.jpg"), "synthetic 2 $folder")
}
$emptyFiles = Get-AppFileHashes

# App AC21: no development database.
Reset-DevDatabase
$result = Invoke-Script $CopyScript $CopyArgs
Write-Result "App AC21 copy without a development database" `
    ($result.Exit -eq 3 -and $result.Output -match "(?m)^No development database; nothing was copied\." -and
        (Get-AppDatabaseFiles) -eq "" -and (Get-AppFileHashes) -eq $emptyFiles) "exit $($result.Exit): $($result.Output)"

# App AC22: a database that cannot be copied leaves nothing behind.
Invoke-DevPython "import pathlib; pathlib.Path('/data/db/rrmc.db').write_bytes(b'not a database ' * 400)" | Out-Null
$result = Invoke-Script $CopyScript $CopyArgs
Write-Result "App AC22 failed copy leaves no app database" `
    ($result.Exit -eq 1 -and (Get-AppDatabaseFiles) -eq "" -and (Get-AppFileHashes) -eq $emptyFiles) `
    "exit $($result.Exit): $($result.Output)"

# App AC17: the copy.
New-DevDatabase
Invoke-DevPython ("import sqlite3; c = sqlite3.connect('/data/db/rrmc.db'); " +
    "[c.execute('INSERT INTO receipts (imported_at) VALUES (?)', ('2026-01-01T00:00:00Z',)) for _ in range(3)]; " +
    "c.commit(); c.close()") | Out-Null
$devHash = Get-DevHash
$devFiles = Get-DevFileHashes
$result = Invoke-Script $CopyScript $CopyArgs
$stateCode = "import sqlite3; c = sqlite3.connect('/data/db/rrmc.db'); q = lambda s: c.execute(s).fetchone()[0]; " +
    "print('STATE:%s %d %d' % (q('PRAGMA integrity_check'), q('SELECT max(version) FROM schema_version'), q('SELECT count(*) FROM receipts')))"
$devState = Get-Marked (Invoke-DevPython $stateCode) "STATE"
$appState = Get-Marked (Invoke-App $AppSettings @("run", "--rm", "--no-deps", "app", "python", "-c", $stateCode)) "STATE"
Write-Result "App AC17 copy of the database" `
    ($result.Exit -eq 0 -and $appState -match "^ok \d+ 3$" -and $appState -eq $devState) `
    "exit $($result.Exit), dev '$devState', app '$appState': $($result.Output)"
$appFiles = Get-AppFileHashes
Write-Result "App AC17 copy of the images" `
    ($appFiles -eq $devFiles -and $appFiles -match "synthetic-2\.jpg")
$version = "$appState" -split " "
Write-Result "App AC17 the output has counts and no file name" `
    ($result.Output -notmatch "synthetic" -and
        $result.Output -match "schema version $($version[1]), 3 receipts" -and
        @($result.Output -split "`n" | Where-Object { $_ -match "^(import|import_done|import_failed|archived): 2 files" }).Count -eq 4) `
    $result.Output
Write-Result "App AC17 development data is unchanged" `
    ($null -ne $devHash -and (Get-DevHash) -eq $devHash -and (Get-DevFileHashes) -eq $devFiles)

# App AC18: a second copy is refused.
$appHash = Get-AppHash
$result = Invoke-Script $CopyScript $CopyArgs
Write-Result "App AC18 copy refuses an existing app database" `
    ($result.Exit -eq 1 -and $result.Output -match "(?m)^The app database already exists; nothing was copied\." -and
        $null -ne $appHash -and (Get-AppHash) -eq $appHash -and (Get-AppFileHashes) -eq $appFiles) `
    "exit $($result.Exit): $($result.Output)"

# App AC20: refused while the app runs. The copied database works for the app's user.
Invoke-App $AppSettings @("up", "-d", "--no-build") | Out-Null
$health = Wait-Health $AppPort
$result = Invoke-Script $CopyScript $CopyArgs
Write-Result "App AC20 copy refuses while the app runs" `
    ($result.Exit -eq 1 -and $result.Output -match "(?m)^Stop the app first: nothing was copied\." -and
        $health.checks.database -eq "ok") "exit $($result.Exit): $($result.Output)"
Invoke-App $AppSettings @("down") | Out-Null

# App AC19: refused when an app folder holds a file.
Reset-AppDatabase
Clear-Files $AppSource
[System.IO.File]::WriteAllText((Join-Path $AppSource "import_done\synthetic-3.jpg"), "synthetic 3")
$result = Invoke-Script $CopyScript $CopyArgs
Write-Result "App AC19 copy refuses app folders with files" `
    ($result.Exit -eq 1 -and $result.Output -match "(?m)^The app folders are not empty; nothing was copied\." -and
        (Get-AppDatabaseFiles) -eq "") "exit $($result.Exit): $($result.Output)"
Clear-Files $AppSource

# Copy exit paths: an unreadable configuration, and an image that cannot be copied.
$badConfig = New-AppSettingsFile "app-bad-config.env" @{ RRMC_APP_PORT = "abc" }
$result = Invoke-Script $CopyScript @("-DevProject", $Project, "-AppProject", $AppProject, "-EnvFile", $badConfig)
Write-Result "App PC5 copy stops on an unreadable configuration" `
    ($result.Exit -eq 1 -and $result.Output -match "(?m)^Could not read the Compose configuration; nothing was copied\." -and
        (Get-AppDatabaseFiles) -eq "") "exit $($result.Exit): $($result.Output)"
$lock = [System.IO.File]::Open((Join-Path $WorkDir "import_done\synthetic-1.jpg"), "Open", "Read", "None")
try { $result = Invoke-Script $CopyScript $CopyArgs } finally { $lock.Close() }
Write-Result "App PC5 copy names the folder of a failed image copy" `
    ($result.Exit -eq 1 -and $result.Output -match "(?m)^Copying the images of import_done failed after" -and
        $result.Output -notmatch "synthetic") "exit $($result.Exit): $($result.Output)"
Reset-AppDatabase
Clear-Files $AppSource

# App T7: some of the test parameters could reach real data, so they are refused.
$result = Invoke-Script $CopyScript @("-AppProject", $AppProject, "-EnvFile", $AppSettings)
Write-Result "App T7 test parameters only together" `
    ($result.Exit -eq 1 -and $result.Output -match "must be given together") $result.Output

# --- Update: runs in a clone, so that its commits never touch this repository. ---
$Stamp = Get-Date -Format "yyyyMMddHHmmss"
$Clone = Join-Path $WorkDir "app\clone-$Stamp"
$UpdateScript = Join-Path $Clone "scripts\update-app.ps1"
$UpdateBackups = Join-Path $WorkDir "app\update-backup-$Stamp"
New-Item -ItemType Directory -Force -Path $UpdateBackups | Out-Null

function Invoke-CloneGit([string[]]$Arguments) {
    return (& git -C $Clone -c user.name=test -c user.email=test@example.invalid @Arguments 2>&1 |
        ForEach-Object { "$_" }) -join "`n"
}
function Write-CloneFile([string]$Path, [string]$Text) {
    $full = Join-Path $Clone $Path
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $full) | Out-Null
    [System.IO.File]::WriteAllText($full, $Text)
}
# Commits everything in the clone; returns the short commit id.
function Save-Clone([string]$Message) {
    Invoke-CloneGit @("add", "-A") | Out-Null
    Invoke-CloneGit @("commit", "--allow-empty", "-m", $Message) | Out-Null
    return (Invoke-CloneGit @("rev-parse", "--short=12", "HEAD")).Trim()
}

& git clone --local --quiet $ProjectRoot $Clone 2>&1 | Out-Null
foreach ($file in @(& git ls-files --modified --others --exclude-standard)) {
    $target = Join-Path $Clone $file
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $file) -Destination $target
}
# One short test file each, so that the checks stay fast.
$passPython = "def test_synthetic() -> None:`n    assert True`n"
$passTypeScript = "import { expect, test } from `"vitest`";`ntest(`"synthetic`", () => expect(1).toBe(1));`n"
Write-CloneFile "backend/tests/clone/test_clone.py" $passPython
Write-CloneFile "frontend/src/clone.test.ts" $passTypeScript
$pyproject = [System.IO.File]::ReadAllText((Join-Path $Clone "backend\pyproject.toml"))
Write-CloneFile "backend/pyproject.toml" $pyproject.Replace('testpaths = ["tests"]', 'testpaths = ["tests/clone"]')
$viteConfig = [System.IO.File]::ReadAllText((Join-Path $Clone "frontend\vite.config.ts"))
Write-CloneFile "frontend/vite.config.ts" $viteConfig.Replace('include: ["src/**/*.test.{ts,tsx}"]', 'include: ["src/clone.test.ts"]')
$firstCommit = Save-Clone "first"

function Invoke-Update([string]$SettingsFile = $AppSettings) {
    return Invoke-Script $UpdateScript @("-DevProject", $Project, "-AppProject", $AppProject,
        "-EnvFile", $SettingsFile, "-BackupDir", $UpdateBackups, "-HealthTimeoutSeconds", "20")
}
function Get-UpdateBackups { return @(Get-ChildItem $UpdateBackups -Filter "rrmc-app-*-before-update.db") }
function Get-ImageId([string]$Tag) {
    $id = (& docker image inspect --format "{{.Id}}" "${AppImage}:$Tag" 2>$null | Out-String).Trim()
    return $id
}
function Get-AppContainer { return (Invoke-App $AppSettings @("ps", "--status", "running", "-q", "app")).Trim() }
function Get-ContainerImage([string]$Id) {
    if ($Id -eq "") { return "none" }
    return (& docker inspect --format "{{.Image}}" $Id | Out-String).Trim()
}

# App AC31: the first update, without an app database.
Reset-AppDatabase
$result = Invoke-Update
Write-Result "App AC31 first update without an app database" `
    ($result.Exit -eq 0 -and $result.Output -match "(?m)^No app database yet; nothing to back up\." -and
        (Get-UpdateBackups).Count -eq 0 -and (Get-AppContainer) -ne "" -and
        $result.Output -match "Updated to ${AppImage}:$firstCommit\.") "exit $($result.Exit): $($result.Output)"

# App AC27: the next version.
$secondCommit = Save-Clone "second"
$result = Invoke-Update
$container = Get-AppContainer
$secondId = Get-ImageId $secondCommit
$backups = Get-UpdateBackups
Write-Result "App AC27 update" `
    ($result.Exit -eq 0 -and $backups.Count -eq 1 -and $secondId -ne "" -and
        (Get-ImageId "latest") -eq $secondId -and (Get-ContainerImage $container) -eq $secondId -and
        (Get-AppPage "/api/health").Status -eq "200" -and
        $result.Output -match "Updated to ${AppImage}:$secondCommit\.") "exit $($result.Exit): $($result.Output)"

# Nothing was updated: same container, backups and image.
function Test-NothingUpdated([string]$Commit) {
    return ($container -ne "" -and (Get-AppContainer) -eq $container -and (Get-UpdateBackups).Count -eq 1 -and
        (Get-ImageId "latest") -eq $secondId -and ($Commit -eq "" -or (Get-ImageId $Commit) -eq ""))
}

# App AC28: an untracked and a modified file.
$dirtyLine = "(?m)^Commit or stash your changes first; nothing was updated\."
Write-CloneFile "untracked.txt" "synthetic"
$result = Invoke-Update
Write-Result "App AC28 update refuses an untracked file" `
    ($result.Exit -eq 1 -and $result.Output -match $dirtyLine -and
        $result.Output -notmatch "test session starts" -and (Test-NothingUpdated "")) "exit $($result.Exit): $($result.Output)"
Save-Clone "untracked" | Out-Null
Write-CloneFile "untracked.txt" "synthetic, changed"
$result = Invoke-Update
Write-Result "App AC28 update refuses a modified file" `
    ($result.Exit -eq 1 -and $result.Output -match $dirtyLine -and
        $result.Output -notmatch "test session starts" -and (Test-NothingUpdated "")) "exit $($result.Exit): $($result.Output)"

# App AC29: a failing backend test, then a failing frontend test.
Write-CloneFile "backend/tests/clone/test_clone.py" $passPython.Replace("True", "False")
$commit = Save-Clone "backend fails"
$result = Invoke-Update
Write-Result "App AC29 update stops on a failing backend test" `
    ($result.Exit -eq 1 -and $result.Output -match "(?m)^Update stopped: backend tests failed; nothing was updated\." -and
        (Test-NothingUpdated $commit)) "exit $($result.Exit): $($result.Output)"
Write-CloneFile "backend/tests/clone/test_clone.py" $passPython
Write-CloneFile "frontend/src/clone.test.ts" $passTypeScript.Replace("toBe(1)", "toBe(2)")
$commit = Save-Clone "frontend fails"
$result = Invoke-Update
Write-Result "App AC29 update stops on a failing frontend test" `
    ($result.Exit -eq 1 -and $result.Output -match "(?m)^Update stopped: frontend tests failed; nothing was updated\." -and
        (Test-NothingUpdated $commit)) "exit $($result.Exit): $($result.Output)"

# App AC30: the new version does not start.
Write-CloneFile "frontend/src/clone.test.ts" $passTypeScript
Save-Clone "unhealthy" | Out-Null
$file = New-AppSettingsFile "app-unhealthy.env" @{ RRMC_LOG_LEVEL = "LOUD" }
$result = Invoke-Update $file
$newBackup = @(Get-UpdateBackups | Sort-Object Name | Select-Object -Last 1)
Write-Result "App AC30 update reports an unhealthy start" `
    ($result.Exit -eq 1 -and (Get-UpdateBackups).Count -eq 2 -and
        $result.Output.Contains("docker tag ${AppImage}:$secondCommit ${AppImage}:latest") -and
        $result.Output.Contains("docker compose -f compose.app.yaml up -d --no-build") -and
        $result.Output -match "restore-db\.ps1 -Target app -BackupFile .*$([regex]::Escape($newBackup[0].Name))") `
    "exit $($result.Exit): $($result.Output)"

# Update exit paths before the restart: configuration, image build and backup.
$latestId = Get-ImageId "latest"
$result = Invoke-Update $badConfig
Write-Result "App PC7 update stops on an unreadable configuration" `
    ($result.Exit -eq 1 -and $result.Output -match "(?m)^Could not read the Compose configuration; nothing was updated\." -and
        (Get-ImageId "latest") -eq $latestId) "exit $($result.Exit): $($result.Output)"
$dockerfile = [System.IO.File]::ReadAllText((Join-Path $Clone "docker\app.Dockerfile"))
Write-CloneFile "docker/app.Dockerfile" "$dockerfile`nRUN exit 1`n"
$commit = Save-Clone "build fails"
$result = Invoke-Update
Write-Result "App PC7 update stops on a failing build" `
    ($result.Exit -eq 1 -and $result.Output -match "(?m)^Update stopped: image build failed; the running app is unchanged\." -and
        (Get-ImageId "latest") -eq $latestId -and (Get-ImageId $commit) -eq "") "exit $($result.Exit): $($result.Output)"
Write-CloneFile "docker/app.Dockerfile" $dockerfile
$commit = Save-Clone "backup fails"
Invoke-App $AppSettings @("down") | Out-Null
Reset-AppDatabase
Invoke-App $AppSettings @("run", "--rm", "--no-deps", "app", "python", "-c",
    "import pathlib; pathlib.Path('/data/db/rrmc.db').write_bytes(b'not a database ' * 400)") | Out-Null
$result = Invoke-Update
Write-Result "App PC7 update stops on a failing backup" `
    ($result.Exit -eq 1 -and $result.Output -match "(?m)^Update stopped: backup failed; nothing was updated\." -and
        (Get-ImageId "latest") -eq $latestId -and (Get-ImageId $commit) -eq "") "exit $($result.Exit): $($result.Output)"
Reset-AppDatabase

# App T8: some of the test parameters could reach real data, so they are refused.
$result = Invoke-Script $UpdateScript @("-AppProject", $AppProject, "-BackupDir", $UpdateBackups)
Write-Result "App T8 test parameters only together" `
    ($result.Exit -eq 1 -and $result.Output -match "must be given together") $result.Output
Invoke-App $AppSettings @("down") | Out-Null

Remove-Item env:RRMC_ENV_FILE -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "The test containers are stopped. To remove the test volume and images, run:"
Write-Host "  docker compose -p $Project down -v --rmi local"
Write-Host "  docker compose -p $AppProject -f compose.app.yaml --env-file $AppSettings down -v --rmi local"
Write-Host "  docker image rm (docker image ls -q $AppImage)"
Write-Host "Test folders and settings files are in $WorkDir"

if ($Failures.Count -gt 0) {
    Write-Host "$($Failures.Count) container test(s) failed." -ForegroundColor Red
    exit 1
}
Write-Host "All container tests passed." -ForegroundColor Green
exit 0
