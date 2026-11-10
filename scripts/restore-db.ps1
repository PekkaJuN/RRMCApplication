# Restores the SQLite database in the Docker volume `rrmc_rrmc-data` from a backup file made
# by scripts/backup-db.ps1.
#
# This replaces ALL data in the database. Steps:
#   1. Check the backup file with `PRAGMA integrity_check` and show its schema version.
#   2. Ask for confirmation (type RESTORE).
#   3. Back up the current database first (suffix "before-restore"), so the restore can be undone.
#   4. Stop the backend, copy the backup in with SQLite's backup API, check the result.
#   5. Start the backend again if it was running. Its prestart applies any newer migrations.
#
# Migrations are forward-only: restoring a backup with a newer schema version than the code
# you run is not supported. Run the version the backup came from.
#
# Usage, from the project root:
#   powershell -ExecutionPolicy Bypass -File scripts/restore-db.ps1 -BackupFile $env:USERPROFILE\rrmc-backup\rrmc-2026-11-10_151500.db

param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

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

# 1. Check the backup file. The folder is mounted read-only.
& docker compose run --rm --no-deps -v "${sourceDir}:/restore:ro" backend `
    python -c $checkCode "/restore/$sourceName"
if ($LASTEXITCODE -ne 0) {
    Write-Host "The backup file is not usable; nothing was changed." -ForegroundColor Red
    exit 1
}

# 2. Confirm.
Write-Host ""
Write-Host "This replaces ALL data in the database with $sourceName." -ForegroundColor Yellow
$answer = Read-Host "Type RESTORE to continue"
if ($answer -cne "RESTORE") {
    Write-Host "Cancelled; nothing was changed."
    exit 1
}

# 3. Back up the current database. Exit 3 means the volume has no database yet.
& (Join-Path $PSScriptRoot "backup-db.ps1") -Suffix "before-restore"
$backupExit = $LASTEXITCODE
if ($backupExit -ne 0 -and $backupExit -ne 3) {
    Write-Host "Could not back up the current database; restore cancelled." -ForegroundColor Red
    exit 1
}

# 4. Stop the backend, so no connection writes while the data is replaced.
$wasRunning = (& docker compose ps --status running --quiet backend | Out-String).Trim() -ne ""
& docker compose stop backend | Out-Null

& docker compose run --rm --no-deps -v "${sourceDir}:/restore:ro" backend `
    python -c $restoreCode "/restore/$sourceName" /data/db/rrmc.db
$restoreExit = $LASTEXITCODE

# 5. Start the backend again if it was running.
if ($wasRunning) {
    & docker compose start backend | Out-Null
    Write-Host "Backend started again."
} else {
    Write-Host "The backend was not running; start the app with: docker compose up"
}

if ($restoreExit -ne 0) {
    Write-Host "Restore failed (exit $restoreExit). The database from before the restore is in the backup folder (suffix before-restore)." -ForegroundColor Red
    exit 1
}
Write-Host "Database restored from $sourceName." -ForegroundColor Green
exit 0
