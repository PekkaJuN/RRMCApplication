# Backs up the SQLite database of an environment from its Docker volume to a Windows folder:
# the development environment (-Target dev, the default; volume `rrmc_rrmc-data`) or the run
# environment (-Target app; volume `rrmc-app-data`).
#
# Uses SQLite's backup API, so the copy is consistent even while the app runs, and opens the
# live database read-only. The copy is built inside the container and checked with
# `PRAGMA integrity_check` before it is written out, because SQLite locking is unreliable on
# folders shared from Windows. The copy is a single file (journal mode DELETE).
# An existing backup file is never overwritten.
#
# The copy holds real receipt data: keep the backup folder outside the repository and out of
# cloud-synced folders.
#
# Usage, from the project root:
#   powershell -ExecutionPolicy Bypass -File scripts/backup-db.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/backup-db.ps1 -BackupDir D:\rrmc-backup
#   powershell -ExecutionPolicy Bypass -File scripts/backup-db.ps1 -Target app
#
# Exit codes: 0 backup written, 3 no database in the volume, 1 any other failure.

# Without CmdletBinding an unknown parameter is ignored, and the script would work on the
# wrong environment.
[CmdletBinding()]
param(
    [ValidateSet("dev", "app")]
    [string]$Target = "dev",
    # Default: %USERPROFILE%\rrmc-backup for dev, the run folder for app.
    [string]$BackupDir = "",
    # Added to the file name, e.g. "before-restore".
    [string]$Suffix = "",
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
if ($Target -eq "app") {
    $compose += @("-f", "compose.app.yaml")
    $service = "app"
    $prefix = "rrmc-app-"
    if (-not $BackupDir) { $BackupDir = "C:\MyApps\RRMCApplication\backup" }
} else {
    $service = "backend"
    $prefix = "rrmc-"
    if (-not $BackupDir) { $BackupDir = Join-Path $env:USERPROFILE "rrmc-backup" }
}

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$BackupDir = (Resolve-Path $BackupDir).Path

$name = $prefix + (Get-Date -Format "yyyy-MM-dd_HHmmss")
if ($Suffix) { $name += "-$Suffix" }
$name += ".db"
if (Test-Path (Join-Path $BackupDir $name)) {
    Write-Host "Backup file $name already exists; not overwriting it." -ForegroundColor Red
    exit 1
}

# One line with single quotes only: Windows PowerShell 5.1 drops double quotes from
# arguments passed to native programs.
$code = "import os,shutil,sqlite3,sys; db=sys.argv[1]; out=sys.argv[2]; " +
    "tmp='/tmp/rrmc-backup.db'; " +
    "(print('No database at '+db, file=sys.stderr), sys.exit(3)) if not os.path.exists(db) else None; " +
    "src=sqlite3.connect('file:'+db+'?mode=ro', uri=True); dst=sqlite3.connect(tmp); " +
    "src.backup(dst); src.close(); dst.execute('PRAGMA journal_mode=DELETE'); " +
    "result=dst.execute('PRAGMA integrity_check').fetchone()[0]; " +
    "version=dst.execute('SELECT max(version) FROM schema_version').fetchone()[0]; dst.close(); " +
    "sys.exit('Integrity check failed: '+result) if result!='ok' else None; " +
    "shutil.copyfile(tmp, out); print('Integrity ok, schema version', version)"

$ErrorActionPreference = "Continue"
& docker @compose run --rm --no-deps -v "${BackupDir}:/backup" $service `
    python -c $code /data/db/rrmc.db "/backup/$name"
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "Backup written: $(Join-Path $BackupDir $name)" -ForegroundColor Green
    exit 0
}
if ($exitCode -eq 3) {
    Write-Host "No database in the volume; nothing to back up." -ForegroundColor Yellow
    exit 3
}
Write-Host "Backup failed (exit $exitCode)." -ForegroundColor Red
exit 1
