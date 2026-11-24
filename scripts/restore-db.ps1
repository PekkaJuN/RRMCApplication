# Restores the SQLite database of an environment from a backup file made by
# scripts/backup-db.ps1: the development environment (-Target dev, the default; volume
# `rrmc_rrmc-data`) or the run environment (-Target app; volume `rrmc-app-data`).
#
# This replaces ALL data in the database. Steps:
#   1. Check the backup file with `PRAGMA integrity_check` and show its schema version.
#   2. Ask for confirmation (type RESTORE).
#   3. Back up the current database first (suffix "before-restore"), so the restore can be undone.
#   4. Stop the service, copy the backup in with SQLite's backup API, check the result.
#   5. Start the service again if it was running. Its prestart applies any newer migrations.
#
# Migrations are forward-only: restoring a backup with a newer schema version than the code
# you run is not supported. Run the version the backup came from.
#
# Usage, from the project root:
#   powershell -ExecutionPolicy Bypass -File scripts/restore-db.ps1 -BackupFile $env:USERPROFILE\rrmc-backup\rrmc-2026-11-10_151500.db

# Without CmdletBinding an unknown parameter could be ignored, and the script would work on
# the wrong environment.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [ValidateSet("dev", "app")]
    [string]$Target = "dev",
    # Where the backup of step 3 goes; the default is backup-db.ps1's.
    [string]$BackupDir = "",
    # For the container tests only, and only together: another project and settings file.
    [string]$ComposeProject = "",
    [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"
if (($ComposeProject -eq "") -ne ($EnvFile -eq "")) {
    Write-Host "-ComposeProject and -EnvFile must be given together." -ForegroundColor Red
    exit 1
}
if ($EnvFile) { $EnvFile = (Resolve-Path $EnvFile).Path }
Set-Location (Split-Path -Parent $PSScriptRoot)

$compose = @("compose")
if ($ComposeProject) {
    $env:RRMC_ENV_FILE = $EnvFile
    $compose += @("-p", $ComposeProject, "--env-file", $EnvFile)
}
$service = "backend"
$startCommand = "docker compose up"
if ($Target -eq "app") {
    $compose += @("-f", "compose.app.yaml")
    $service = "app"
    $startCommand = "docker compose -f compose.app.yaml up -d"
}

if (-not (Test-Path -PathType Leaf $BackupFile)) {
    Write-Host "Backup file not found: $BackupFile" -ForegroundColor Red
    exit 1
}
$BackupFile = (Resolve-Path $BackupFile).Path
$sourceDir = Split-Path -Parent $BackupFile
$sourceName = Split-Path -Leaf $BackupFile
$ErrorActionPreference = "Continue"

# Python one-liners use single quotes only: Windows PowerShell 5.1 drops double quotes from
# arguments passed to native programs. The backup is copied to /tmp in the container first,
# because SQLite locking is unreliable on folders shared from Windows.
$checkCode = "import shutil,sqlite3,sys; tmp='/tmp/rrmc-check.db'; shutil.copyfile(sys.argv[1], tmp); " +
    "c=sqlite3.connect(tmp); result=c.execute('PRAGMA integrity_check').fetchone()[0]; " +
    "version=c.execute('SELECT max(version) FROM schema_version').fetchone()[0]; c.close(); " +
    "sys.exit('Integrity check failed: '+result) if result!='ok' else None; " +
    "print('Backup integrity ok, schema version', version)"

$restoreCode = "import shutil,sqlite3,sys; tmp='/tmp/rrmc-restore.db'; shutil.copyfile(sys.argv[1], tmp); " +
    "src=sqlite3.connect('file:'+tmp+'?mode=ro', uri=True); dst=sqlite3.connect(sys.argv[2]); " +
    "src.backup(dst); src.close(); result=dst.execute('PRAGMA integrity_check').fetchone()[0]; " +
    "version=dst.execute('SELECT max(version) FROM schema_version').fetchone()[0]; dst.close(); " +
    "sys.exit('Integrity check failed after restore: '+result) if result!='ok' else None; " +
    "print('Restored, integrity ok, schema version', version)"

# 1. Check the backup file. The folder is mounted read-only. Without --interactive=false
# Compose would take the standard input that Read-Host reads in step 2.
& docker @compose run --rm --no-deps --interactive=false -v "${sourceDir}:/restore:ro" $service `
    python -c $checkCode "/restore/$sourceName"
if ($LASTEXITCODE -ne 0) {
    Write-Host "The backup file is not usable; nothing was changed." -ForegroundColor Red
    exit 1
}

# 2. Confirm.
Write-Host ""
Write-Host "This replaces ALL data in the '$Target' database with $sourceName." -ForegroundColor Yellow
$answer = Read-Host "Type RESTORE to continue"
if ($answer -cne "RESTORE") {
    Write-Host "Cancelled; nothing was changed."
    exit 1
}

# 3. Back up the current database. Exit 3 means the volume has no database yet.
& (Join-Path $PSScriptRoot "backup-db.ps1") -Suffix "before-restore" -Target $Target `
    -BackupDir $BackupDir -ComposeProject $ComposeProject -EnvFile $EnvFile
$backupExit = $LASTEXITCODE
if ($backupExit -ne 0 -and $backupExit -ne 3) {
    Write-Host "Could not back up the current database; restore cancelled." -ForegroundColor Red
    exit 1
}

# 4. Stop the backend, so no connection writes while the data is replaced.
$wasRunning = (& docker @compose ps --status running --quiet $service | Out-String).Trim() -ne ""
& docker @compose stop $service | Out-Null

& docker @compose run --rm --no-deps --interactive=false -v "${sourceDir}:/restore:ro" $service `
    python -c $restoreCode "/restore/$sourceName" /data/db/rrmc.db
$restoreExit = $LASTEXITCODE

# 5. Start the backend again if it was running.
if ($wasRunning) {
    & docker @compose start $service | Out-Null
    Write-Host "Service $service started again."
} else {
    Write-Host "Service $service was not running; start the app with: $startCommand"
}

if ($restoreExit -ne 0) {
    Write-Host "Restore failed (exit $restoreExit). The database from before the restore is in the backup folder (suffix before-restore)." -ForegroundColor Red
    exit 1
}
Write-Host "Database restored from $sourceName." -ForegroundColor Green
exit 0
