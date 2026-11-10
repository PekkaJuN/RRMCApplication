# Backs up the SQLite database from the Docker volume `rrmc_rrmc-data` to a Windows folder.
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
#
# Exit codes: 0 backup written, 3 no database in the volume, 1 any other failure.

param(
    [string]$BackupDir = (Join-Path $env:USERPROFILE "rrmc-backup"),
    # Added to the file name, e.g. "before-restore".
    [string]$Suffix = ""
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$BackupDir = (Resolve-Path $BackupDir).Path

$name = "rrmc-" + (Get-Date -Format "yyyy-MM-dd_HHmmss")
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
& docker compose run --rm --no-deps -v "${BackupDir}:/backup" backend `
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
