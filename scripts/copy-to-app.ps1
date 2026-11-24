# Copies the development data into the run environment, once: the database and the images of
# the four receipt folders (specs/features/app-container.md, PC5).
#
# The development data is only read. The script refuses when the run environment already has a
# database or a file in its folders, or when the app runs, so it never overwrites app data.
# The database is copied first, with SQLite's backup API, and checked with
# `PRAGMA integrity_check`; a failed copy leaves no database and copies no image.
#
# Usage, from the project root, with the app stopped:
#   powershell -ExecutionPolicy Bypass -File scripts/copy-to-app.ps1
#
# Exit codes: 0 copied, 3 no development database, 1 any other failure.

# Without CmdletBinding an unknown parameter is ignored, and the script would work on the
# wrong environment.
[CmdletBinding()]
param(
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
$folders = @("import", "import_done", "import_failed", "archived")
$ErrorActionPreference = "Continue"

function Stop-Copy([string]$Message, [int]$Code = 1) {
    Write-Host $Message -ForegroundColor Red
    exit $Code
}

# The resolved configuration. It holds settings values, so it is never printed.
function Get-ComposeConfig([string[]]$Compose) {
    $json = (& docker @Compose config --format json) -join "`n"
    if ($LASTEXITCODE -ne 0) { Stop-Copy "Could not read the Compose configuration; nothing was copied." }
    return $json | ConvertFrom-Json
}

function Get-FolderSource($Config, [string]$Service, [string]$Folder) {
    $mount = @($Config.services.$Service.volumes | Where-Object { $_.target -eq "/data/$Folder" })
    if ($mount.Count -ne 1) { Stop-Copy "Could not find the folder $Folder; nothing was copied." }
    return "$($mount[0].source)" -replace "/", "\"
}

# 1. Where the data is.
$devConfig = Get-ComposeConfig $devCompose
$appConfig = Get-ComposeConfig $appCompose
$appVolume = "$($appConfig.volumes.'app-db'.name)"
if (-not $appVolume) { Stop-Copy "Could not find the app volume; nothing was copied." }
$sources = @{}
$targets = @{}
foreach ($folder in $folders) {
    $sources[$folder] = Get-FolderSource $devConfig "backend" $folder
    $targets[$folder] = Get-FolderSource $appConfig "app" $folder
}

# 2. The app must not run.
$running = (& docker @appCompose ps --status running -q app | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { Stop-Copy "Could not check the app; nothing was copied." }
if ($running) { Stop-Copy "Stop the app first: nothing was copied." }

# 3. The app data must be empty. Running the app's image also creates its volume and folders.
# Python code in single quotes only: Windows PowerShell 5.1 drops double quotes from arguments.
$checkCode = @'
import os, pathlib
print('DB:%d' % os.path.exists('/data/db/rrmc.db'))
folders = ('import', 'import_done', 'import_failed', 'archived')
print('FILES:%d' % sum(1 for f in folders for p in pathlib.Path('/data', f).rglob('*') if not p.is_dir()))
'@
$state = @(& docker @appCompose run --rm --no-deps --interactive=false app python -c $checkCode)
if ($LASTEXITCODE -ne 0 -or @($state | Where-Object { $_ -match "^(DB|FILES):\d+$" }).Count -ne 2) {
    Stop-Copy "Could not check the app data; nothing was copied."
}
if ($state -notcontains "DB:0") { Stop-Copy "The app database already exists; nothing was copied." }
if ($state -notcontains "FILES:0") { Stop-Copy "The app folders are not empty; nothing was copied." }

# 4. The database. 10001 is the app's user in the run image. Error texts are not printed,
# because they can hold data.
$copyCode = @'
import os, pathlib, sqlite3, sys
db, tmp, target = '/data/db/rrmc.db', '/to/rrmc.db.tmp', '/to/rrmc.db'
if not os.path.exists(db):
    sys.exit(3)
if os.path.exists(target):
    sys.exit(1)
try:
    src = sqlite3.connect('file:' + db + '?mode=ro', uri=True)
    dst = sqlite3.connect(tmp)
    src.backup(dst)
    dst.execute('PRAGMA journal_mode=DELETE')
    if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise ValueError('integrity check')
    version = dst.execute('SELECT max(version) FROM schema_version').fetchone()[0]
    receipts = dst.execute('SELECT count(*) FROM receipts').fetchone()[0]
    src.close()
    dst.close()
    os.chown(tmp, 10001, 10001)
    os.rename(tmp, target)
except Exception as error:
    for left in pathlib.Path('/to').glob('rrmc.db.tmp*'):
        left.unlink()
    print('Copy failed:', type(error).__name__)
    sys.exit(1)
print('Database copied, integrity ok: schema version %d, %d receipts' % (version, receipts))
'@
& docker @devCompose run --rm --no-deps --interactive=false -v "${appVolume}:/to" backend python -c $copyCode
$copyExit = $LASTEXITCODE
if ($copyExit -eq 3) { Stop-Copy "No development database; nothing was copied." 3 }
if ($copyExit -ne 0) { Stop-Copy "The database copy failed; nothing was copied." }

# 5. The images. The targets were checked empty, so nothing is overwritten.
foreach ($folder in $folders) {
    $count = 0
    try {
        $source = $sources[$folder].TrimEnd("\")
        if (Test-Path -LiteralPath $source) {
            foreach ($file in @(Get-ChildItem -LiteralPath $source -Recurse -File -Force -ErrorAction Stop)) {
                $target = Join-Path $targets[$folder] $file.FullName.Substring($source.Length + 1)
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) -ErrorAction Stop | Out-Null
                Copy-Item -LiteralPath $file.FullName -Destination $target -ErrorAction Stop
                $count++
            }
        }
    } catch {
        # The exception's text names the file.
        Stop-Copy ("Copying the images of $folder failed after $count files. The database is copied; " +
            "finish by hand (docs/development.md).")
    }
    Write-Host "${folder}: $count files"
}
Write-Host "The development data is copied to the run environment." -ForegroundColor Green
exit 0
