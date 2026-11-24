# Updates the run environment to the checked-out commit (specs/features/app-container.md, PC7):
# requires a clean working tree, runs the backend and frontend tests, backs up the app
# database, builds the run image, restarts the app and waits for its health check.
#
# A failure before the restart leaves the running app as it was. After a start that is not
# healthy the script prints the commands that bring the previous version and its data back.
#
# Usage, from the project root:
#   powershell -ExecutionPolicy Bypass -File scripts/update-app.ps1
#
# Exit codes: 0 updated, 1 any failure.

# Without CmdletBinding an unknown parameter is ignored, and the script would work on the
# wrong environment.
[CmdletBinding()]
param(
    # Where the backup goes; the default is backup-db.ps1's for -Target app.
    [string]$BackupDir = "",
    [int]$HealthTimeoutSeconds = 120,
    # For the container tests only, and only together: other projects and a settings file.
    [string]$DevProject = "",
    [string]$AppProject = "",
    [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"
$given = @(@($DevProject, $AppProject, $EnvFile) | Where-Object { $_ -ne "" }).Count
if ($given -ne 0 -and $given -ne 3) {
    Write-Host "-DevProject, -AppProject and -EnvFile must be given together." -ForegroundColor Red
    exit 1
}
if ($EnvFile) { $EnvFile = (Resolve-Path $EnvFile).Path }
Set-Location (Split-Path -Parent $PSScriptRoot)

$devCompose = @("compose")
$appCompose = @("compose")
if ($EnvFile) {
    $env:RRMC_ENV_FILE = $EnvFile
    $devCompose += @("-p", $DevProject, "--env-file", $EnvFile)
    $appCompose += @("-p", $AppProject, "--env-file", $EnvFile)
}
$appCompose += @("-f", "compose.app.yaml")
$ErrorActionPreference = "Continue"

function Stop-Update([string]$Message) {
    Write-Host $Message -ForegroundColor Red
    exit 1
}

# 1. The version is the commit, so the working tree must match it.
$changes = (& git status --porcelain | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { Stop-Update "Could not read the Git status; nothing was updated." }
if ($changes) { Stop-Update "Commit or stash your changes first; nothing was updated." }
$commit = (& git rev-parse --short=12 HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $commit) { Stop-Update "Could not read the commit; nothing was updated." }

# 2. The tests.
& docker @devCompose run --rm --interactive=false backend-test pytest
if ($LASTEXITCODE -ne 0) { Stop-Update "Update stopped: backend tests failed; nothing was updated." }
& docker @devCompose run --rm --interactive=false frontend-test npm test
if ($LASTEXITCODE -ne 0) { Stop-Update "Update stopped: frontend tests failed; nothing was updated." }

# 3. The previous version, for the way back. The configuration holds settings values, so it
# is never printed.
$json = (& docker @appCompose config --format json) -join "`n"
if ($LASTEXITCODE -ne 0) { Stop-Update "Could not read the Compose configuration; nothing was updated." }
$app = ($json | ConvertFrom-Json).services.app
$image = "$($app.image)" -replace ":[^:/]*$", ""
$port = "$($app.ports[0].published)"
$previous = ""
$inspected = (& docker image inspect "${image}:latest" 2>$null) -join "`n"
if ($LASTEXITCODE -eq 0) {
    $latest = @($inspected | ConvertFrom-Json)[0]
    $label = $latest.Config.Labels.PSObject.Properties["org.opencontainers.image.revision"]
    # An image built by hand has no revision; its id still finds it.
    $previous = if ($label -and $label.Value) { "${image}:$($label.Value)" } else { $latest.Id }
} else {
    # The backup runs in the image. Built on its own, because a build inside the captured call
    # below fails in a console ("failed to get console").
    & docker @appCompose build app
    if ($LASTEXITCODE -ne 0) { Stop-Update "Update stopped: image build failed; the running app is unchanged." }
}

# 4. The backup.
$backupArgs = @{ Target = "app"; Suffix = "before-update"; BackupDir = $BackupDir }
if ($EnvFile) { $backupArgs.ComposeProject = $AppProject; $backupArgs.EnvFile = $EnvFile }
$backupFile = ""
# 6>&1: Write-Host's lines, which name the file.
& (Join-Path $PSScriptRoot "backup-db.ps1") @backupArgs 6>&1 | ForEach-Object {
    if ("$_" -match "^Backup written: (.+)$") { $backupFile = $Matches[1] }
    if ("$_" -notmatch "nothing to back up") { Write-Host "$_" }
}
$backupExit = $LASTEXITCODE
if ($backupExit -eq 3) {
    Write-Host "No app database yet; nothing to back up."
} elseif ($backupExit -ne 0 -or -not $backupFile) {
    Stop-Update "Update stopped: backup failed; nothing was updated."
}

# 5. The image.
$env:RRMC_APP_TAG = $commit
& docker @appCompose build app
if ($LASTEXITCODE -ne 0) { Stop-Update "Update stopped: image build failed; the running app is unchanged." }
& docker tag "${image}:$commit" "${image}:latest"
if ($LASTEXITCODE -ne 0) { Stop-Update "Update stopped: image tag failed; the running app is unchanged." }

# 6. The restart.
& docker @appCompose up -d --no-build app
$started = $LASTEXITCODE -eq 0

# 7. The health check.
$healthy = $false
$deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
while ($started -and -not $healthy -and (Get-Date) -lt $deadline) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 5
        $healthy = $response.StatusCode -eq 200
    } catch {
        Start-Sleep -Seconds 2
    }
}
if ($healthy) {
    Write-Host "Updated to ${image}:$commit." -ForegroundColor Green
    exit 0
}

Write-Host "The app did not become healthy as ${image}:$commit." -ForegroundColor Red
if ($previous) {
    Write-Host "To start the previous version again:"
    Write-Host "  docker tag $previous ${image}:latest"
    Write-Host "  docker compose -f compose.app.yaml up -d --no-build"
} else {
    Write-Host "There is no previous version."
}
if ($backupFile) {
    Write-Host "To restore the data from before the update:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/restore-db.ps1 -Target app -BackupFile $backupFile"
}
exit 1
