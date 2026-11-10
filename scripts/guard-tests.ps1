# Tests of the agent guardrails (specs/features/agent-guardrails.md).
#
# Every input is synthetic: tool calls and command strings written here. No test reads .env,
# source/ or a database. State files go to a temporary folder that is printed at the end.
#
# Usage, from the project root:
#   powershell -ExecutionPolicy Bypass -File scripts/guard-tests.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$GuardDir = Join-Path $ProjectRoot ".agents\guardrails"
Import-Module (Join-Path $GuardDir "Guard.psm1") -Force

# A made-up project root, so that absolute paths in the tests never point at real files.
$Root = "C:\Work\Project"
$Failures = New-Object System.Collections.Generic.List[string]
$script:Passed = 0

function Write-Check([string]$Name, [bool]$Ok, [string]$Detail = "") {
    if ($Ok) {
        $script:Passed++
    } else {
        Write-Host "FAIL $Name $Detail" -ForegroundColor Red
        $Failures.Add($Name)
    }
}

function Get-Id($Decision) {
    if ($Decision.Action -eq "Allow") { return "" }
    return $Decision.Id
}

# Expected is a guardrail ID such as "G1", or "" for an allowed call.
function Assert-Call([string]$Name, $Call, [string]$Expected, $State = $null) {
    if ($null -eq $State) { $State = New-GuardState }
    $decision = Get-GuardDecision -Call $Call -State $State -ProjectRoot $Root
    $got = Get-Id $decision
    Write-Check $Name ($got -eq $Expected) "expected '$Expected', got '$got'"
}

function Assert-Shell([string]$Command, [string]$Expected) {
    Assert-Call "shell [$Command]" (New-GuardCall -Kind shell -Command $Command) $Expected
}

function Assert-File([string]$Kind, [string]$Path, [string]$Expected) {
    Assert-Call "$Kind [$Path]" (New-GuardCall -Kind $Kind -Paths @($Path)) $Expected
}

# --- G1 protected data (AC1-AC4, AC25) ---------------------------------------------------
# AC1: .env through the file tool and the shell.
Assert-File read "$Root\.env" "G1"
Assert-File read ".env" "G1"
Assert-File write "$Root\.env.local" "G1"
foreach ($c in @("cat .env", "Get-Content .env", "type .env", "cat ./.env", "Get-Content -Path .\.env")) {
    Assert-Shell $c "G1"
}
# AC2: .env.example stays readable.
Assert-File read "$Root\.env.example" ""
Assert-Shell "cat .env.example" ""
Assert-Shell "Copy-Item .env.example C:\Temp\settings.env" ""
# AC3: source/, database and key files.
Assert-File read "$Root\source\import\a.jpg" "G1"
Assert-File search "source/**" "G1"
Assert-File write "$Root\source\import_done\x.png" "G1"
Assert-File read "$Root\backend\rrmc.db" "G1"
Assert-File read "data/rrmc.sqlite3-wal" "G1"
Assert-File read "C:\Keys\service_account_rrmc.json" "G1"
foreach ($c in @("ls source", "Get-ChildItem source/import", "grep -r x source", "dir source\import_failed",
        "cat backend/data/rrmc.db", "cp service_account.json C:\Temp")) {
    Assert-Shell $c "G1"
}
# AC4: a path inside a longer command.
Assert-Shell "cd backend && cat ../.env" "G1"
Assert-Shell "echo x; ls ./source/import" "G1"
Assert-Shell "git status | Select-String x; Get-Content (Join-Path . .env)" "G1"
# The shell builtin `source` is not the folder.
Assert-Shell "source ~/.bashrc" ""
# Ordinary files and folders stay usable.
Assert-File read "$Root\backend\app\settings.py" ""
Assert-File write "$Root\docs\security.md" ""
Assert-Shell "cat backend/app/settings.py" ""
Assert-Shell "git diff --stat" ""
# AC25: recursive search from the project root reads source/, so it is blocked.
foreach ($c in @("grep -r x .", "grep -rn x", "find . -name x", "Get-ChildItem -Recurse",
        "Select-String -Path * -Pattern x -Recurse", "ls -R", "dir /s", "rg --no-ignore x",
        "Get-ChildItem -Path . -Recurse -Filter *.md")) {
    Assert-Shell $c "G1"
}
foreach ($c in @("grep -r x backend", "Get-ChildItem -Recurse docs", "find backend -name x",
        "grep -rn x docs specs", "rg x", "Get-ChildItem -Recurse -Path frontend/src -Filter *.tsx")) {
    Assert-Shell $c ""
}

# --- G2 app services (AC5-AC7) -----------------------------------------------------------
foreach ($c in @("docker compose up", "docker compose up -d backend", "docker compose up --build",
        "docker compose run --rm backend pytest", "docker compose exec backend sh",
        "docker compose logs backend", "docker compose logs -f", "docker compose config",
        "docker compose config backend-test", "docker compose --profile eval run --rm eval",
        "docker compose --profile e2e up", "docker compose start", "docker compose restart backend",
        "docker compose cp backend:/data/db .", "docker-compose up", "docker.exe compose up",
        "docker inspect rrmc-backend-1", "docker cp rrmc-backend-1:/data/db .",
        "docker run --rm -v C:\Data:/x alpine ls /x", "docker exec rrmc-backend-1 ls",
        "docker logs rrmc-backend-1", "docker container inspect rrmc-backend-1",
        "docker compose run --rm -e X=1 backend python -c print(1)")) {
    Assert-Shell $c "G2"
}
# AC6: the Commands table and the other test-service commands run.
foreach ($c in @("docker compose run --rm backend-test pytest",
        'docker compose run --rm backend-test sh -c "ruff check . && ruff format --check ."',
        "docker compose run --rm backend-test pyright", "docker compose run --rm backend-test pip-audit",
        "docker compose run --rm frontend-test npm test", "docker compose run --rm frontend-test npm run lint",
        "docker compose run --rm frontend-test npm run format:check",
        "docker compose run --rm frontend-test npm run typecheck", "docker compose --profile e2e run --rm e2e",
        "docker compose --profile e2e down", "docker compose restart backend-e2e",
        "docker compose build backend", "docker compose ps", "docker compose config --services",
        "docker compose -p rrmc-test up -d --build backend", "docker compose -p rrmc-test logs backend",
        "docker compose --profile e2e up -d --force-recreate --no-deps backend-e2e",
        "docker ps", "docker images", "docker volume ls",
        "powershell -ExecutionPolicy Bypass -File scripts/container-tests.ps1")) {
    Assert-Shell $c ""
}
# AC7: the running app's ports, through the shell, web fetch and a browser tool.
foreach ($c in @("curl http://127.0.0.1:8000/api/receipts", "curl -s localhost:5173/",
        "Invoke-WebRequest http://localhost:5173/", "Invoke-RestMethod -Uri http://127.0.0.1:8000/api/health",
        "wget http://0.0.0.0:8000/", "curl http://[::1]:5173/")) {
    Assert-Shell $c "G2"
}
Assert-Call "web [127.0.0.1:8000]" (New-GuardCall -Kind web -Urls @("http://127.0.0.1:8000/api/receipts")) "G2"
Assert-Call "browser [localhost:5173]" (New-GuardCall -Kind other -Urls @("http://localhost:5173/")) "G2"
Assert-Shell "Invoke-RestMethod -Uri http://127.0.0.1:18000/api/health" ""
Assert-Shell "curl http://127.0.0.1:18000/api/health" ""
Assert-Call "web [example.org]" (New-GuardCall -Kind web -Urls @("https://example.org/docs")) ""

# --- G3 deletion and hard-to-reverse Git (AC8, AC9) --------------------------------------
foreach ($c in @("docker compose down -v", "docker compose down --volumes",
        "docker compose -p rrmc-test down -v --rmi local", "docker volume rm rrmc_rrmc-data",
        "docker volume prune -f", "docker system prune", "docker image prune -a",
        "rm -rf backend", "rm -r docs", "rm -f compose.yaml", "rm --recursive x",
        "Remove-Item -Recurse frontend", "Remove-Item frontend -Recurse -Force", "ri -rec x",
        "rmdir /s /q x", "rd /s x", "powershell -File scripts/restore-db.ps1",
        "powershell -ExecutionPolicy Bypass -File .\scripts\restore-db.ps1 -Backup x",
        "git push", "git push --force", "git push origin main", "git reset --hard",
        "git reset --hard HEAD~1", "git clean -fd", "git checkout -- compose.yaml",
        "git checkout main -- compose.yaml", "git restore compose.yaml", "git restore --worktree x",
        "git branch -D x", "git commit --amend", "git commit --amend -m x", "git rebase main",
        "git filter-branch --tree-filter x", "git remote set-url origin x", "git remote add x y",
        "git remote remove origin", "git -C backend push", "git update-ref -d refs/heads/x",
        "git reflog expire --all")) {
    Assert-Shell $c "G3"
}
foreach ($c in @("git status", "git diff", "git log --oneline -5", "git add -A", "git commit -m x",
        "git checkout -b x", "git checkout main", "git restore --staged x", "git branch",
        "git branch -d x", "git remote -v", "git show HEAD", "docker compose down",
        "docker compose --profile e2e down", "Remove-Item C:\Temp\probe.txt", "rm notes.txt",
        "powershell -File scripts/backup-db.ps1", "git stash list")) {
    Assert-Shell $c ""
}

# --- G4 guard config (AC10) --------------------------------------------------------------
foreach ($p in @("$Root\.claude\settings.json", ".claude/settings.local.json", "$Root\.claude\hooks\x.ps1",
        "$Root\.codex\config.toml", ".codex/rules/guardrails.rules", "$Root\.agents\guardrails\Guard.psm1",
        ".agents/guardrails/state/s.json", "$Root\scripts\guard-tests.ps1")) {
    Assert-File write $p "G4"
    Assert-File read $p ""
}
Assert-File write "$Root\.claude\agents\checker.md" ""
Assert-File write "$Root\.agents\skills\tdd\SKILL.md" ""
foreach ($c in @("Set-Content .claude/settings.json x", "sed -i s/a/b/ .codex/config.toml",
        "echo x > .agents/guardrails/Guard.psm1", "echo x>>.codex/hooks.json",
        "Remove-Item .agents\guardrails\state\s.json", "mv scripts/guard-tests.ps1 x.ps1",
        "Copy-Item x.ps1 .agents/guardrails/hook.ps1", "Out-File -FilePath .claude\settings.json")) {
    Assert-Shell $c "G4"
}
foreach ($c in @("cat .claude/settings.json", "Get-Content .codex/config.toml", "git diff .agents/guardrails",
        "git add .agents/guardrails scripts/guard-tests.ps1", "ls .agents/guardrails",
        "powershell -ExecutionPolicy Bypass -File scripts/guard-tests.ps1",
        "Select-String -Path .agents/guardrails/Guard.psm1 -Pattern G4")) {
    Assert-Shell $c ""
}

# --- G5 and G6 counters (AC11-AC14) ------------------------------------------------------
$BackendTests = "docker compose run --rm backend-test pytest"
$Now = [datetime]::new(2026, 11, 10, 12, 0, 0, [DateTimeKind]::Utc)

function Invoke-Edit($State, [string[]]$Paths) { Update-GuardAfterEdit -State $State -Paths $Paths | Out-Null }
function Invoke-Run($State, [bool]$Ok, [string]$Command = $BackendTests) {
    Update-GuardAfterRun -State $State -Command $Command -ExitOk $Ok -Now $Now
}
$readCall = New-GuardCall -Kind read -Paths @("backend/app/x.py")
$editCall = New-GuardCall -Kind write -Paths @("backend/app/x.py")

# AC11: three counted red runs trip G5; reads still run; a user message resets.
$s = New-GuardState
foreach ($file in @("backend/app/a.py", "backend/app/b.py", "backend/app/c.py")) {
    Invoke-Edit $s @($file); Invoke-Run $s $false
}
Assert-Call "AC11 edit after three red rounds" $editCall "G5" $s
Assert-Call "AC11 shell after three red rounds" (New-GuardCall -Kind shell -Command "git status") "G5" $s
Assert-Call "AC11 read after three red rounds" $readCall "" $s
Assert-Call "AC11 read of protected data after three red rounds" (New-GuardCall -Kind read -Paths @(".env")) "G1" $s
$reason = (Get-GuardDecision -Call $editCall -State $s -ProjectRoot $Root).Reason
Write-Check "AC11 reason names three red rounds" ($reason -match "three red rounds") $reason
Reset-GuardOnUserMessage -State $s
Assert-Call "AC11 edit after the user's message" $editCall "" $s
Write-Check "AC11 count is 0 after the user's message" ($s.g5Count -eq 0) "count $($s.g5Count)"
# Red runs without any edit count too.
$s = New-GuardState
1..3 | ForEach-Object { Invoke-Run $s $false }
Assert-Call "AC11 three red runs without edits" $editCall "G5" $s

# AC12: a green run resets the count.
$s = New-GuardState
Invoke-Edit $s @("backend/app/a.py"); Invoke-Run $s $false
Invoke-Edit $s @("backend/app/b.py"); Invoke-Run $s $false
Invoke-Run $s $true
Write-Check "AC12 green run resets the count" ($s.g5Count -eq 0) "count $($s.g5Count)"
Invoke-Edit $s @("backend/app/a.py"); Invoke-Run $s $false
Invoke-Edit $s @("backend/app/b.py"); Invoke-Run $s $false
Assert-Call "AC12 two red runs after green do not trip" $editCall "" $s

# AC13: a red run after a test edit does not count for G5.
$s = New-GuardState
Invoke-Edit $s @("backend/app/a.py"); Invoke-Run $s $false
Invoke-Edit $s @("backend/tests/unit/test_x.py"); Invoke-Run $s $false
Write-Check "AC13 red run after a test edit keeps the count" ($s.g5Count -eq 1) "count $($s.g5Count)"
Invoke-Edit $s @("backend/app/x.py"); Invoke-Run $s $false
Write-Check "AC13 red run after a code edit counts" ($s.g5Count -eq 2) "count $($s.g5Count)"
foreach ($testFile in @("frontend/src/components/A.test.tsx", "frontend/e2e/import.spec.ts")) {
    $s = New-GuardState
    Invoke-Edit $s @($testFile); Invoke-Run $s $false
    Write-Check "AC13 $testFile is a test file" ($s.g5Count -eq 0) "count $($s.g5Count)"
}

# AC14: the same file in three red runs in a row trips G6.
$s = New-GuardState
1..3 | ForEach-Object { Invoke-Edit $s @("backend/app/x.py"); Invoke-Run $s $false }
Assert-Call "AC14 same file three times" (New-GuardCall -Kind write -Paths @("backend/app/y.py")) "G6" $s
Assert-Call "AC14 read while G6 is tripped" $readCall "" $s
Reset-GuardOnUserMessage -State $s
Assert-Call "AC14 calls run after the user's message" $editCall "" $s
$s = New-GuardState
Invoke-Edit $s @("backend/app/x.py"); Invoke-Run $s $false
Invoke-Edit $s @("backend/app/x.py"); Invoke-Edit $s @("backend/app/x.py"); Invoke-Run $s $false
Invoke-Edit $s @("backend/app/y.py"); Invoke-Run $s $false
Write-Check "AC14 another file starts the count again" ($s.g6Count -eq 1) "count $($s.g6Count)"
Write-Check "AC14 another file does not trip G6" ($s.tripped -ne "G6") "tripped $($s.tripped)"
$s = New-GuardState
1..3 | ForEach-Object { Invoke-Edit $s @("backend/tests/unit/test_x.py"); Invoke-Run $s $false }
Assert-Call "AC14 a test file three times trips G6" $editCall "G6" $s
Write-Check "AC14 G5 does not count those runs" ($s.g5Count -eq 0) "count $($s.g5Count)"
$s = New-GuardState
1..3 | ForEach-Object { Invoke-Edit $s @("backend/app/x.py"); Invoke-Run $s $true }
Assert-Call "AC14 same file with green runs" $editCall "" $s
$s = New-GuardState
1..3 | ForEach-Object { Invoke-Edit $s @("backend/app/x.py", "backend/app/y.py"); Invoke-Run $s $false }
Write-Check "AC14 several files reset the same-file count" ($s.g6Count -eq 0) "count $($s.g6Count)"

# Check runs are recognized; other commands do not change the counts.
$s = New-GuardState
Invoke-Run $s $false "git status"
Write-Check "a command that is not a check run is not counted" ($s.g5Count -eq 0) "count $($s.g5Count)"
foreach ($c in @($BackendTests, "docker compose run --rm backend-test pyright",
        'docker compose run --rm backend-test sh -c "ruff check . && ruff format --check ."',
        "docker compose run --rm frontend-test npm test", "docker compose run --rm frontend-test npm run lint",
        "docker compose run --rm frontend-test npm run format:check",
        "docker compose run --rm frontend-test npx prettier --check . --end-of-line auto",
        "docker compose run --rm frontend-test npm run typecheck", "docker compose --profile e2e run --rm e2e",
        "powershell -ExecutionPolicy Bypass -File scripts/container-tests.ps1",
        "powershell -ExecutionPolicy Bypass -File scripts/guard-tests.ps1",
        "docker compose run --rm backend-test pytest -q tests/unit/test_x.py")) {
    Write-Check "check run [$c]" ($null -ne (Get-CheckRun $c))
}

# --- G7 test edits after a red run (AC15) ------------------------------------------------
$G7Line = "Guardrail G7: a failing test may not be fixed by editing it; change the test only if the spec says it is wrong."
$s = New-GuardState
Invoke-Run $s $false
$result = Update-GuardAfterEdit -State $s -Paths @("backend/tests/unit/test_x.py")
Write-Check "AC15 G7 line after a red run" ((Format-GuardLine $result.Decision) -eq $G7Line) (Format-GuardLine $result.Decision)
Write-Check "AC15 the test file is to be recorded" (@($result.TestPaths) -contains "backend/tests/unit/test_x.py")
$result = Update-GuardAfterEdit -State $s -Paths @("backend/app/x.py")
Write-Check "AC15 no reminder for a code file" ($result.Decision.Action -eq "Allow")
$s = New-GuardState
Invoke-Run $s $true
$result = Update-GuardAfterEdit -State $s -Paths @("frontend/src/components/A.test.tsx")
Write-Check "AC15 no reminder after a green run" ($result.Decision.Action -eq "Allow" -and @($result.TestPaths).Count -eq 0)

# --- G8 checks before the end of a turn (AC17, AC18) -------------------------------------
$Before = $Now.AddMinutes(-10)
$After = $Now.AddMinutes(10)
function New-GreenState([string[]]$Checks, [datetime]$At) {
    $state = New-GuardState
    foreach ($check in $Checks) { Set-GuardLastGreen $state $check $At }
    return $state
}
$BackendChecks = @("backend-tests", "backend-lint", "backend-types")
$FrontendChecks = @("frontend-tests", "frontend-lint", "frontend-format", "frontend-types")

# AC17: backend code changed after the last green backend tests: refused once, then allowed.
$s = New-GreenState @("backend-lint", "backend-types") $After
Set-GuardLastGreen $s "backend-tests" $Before
$stop = Get-GuardStopDecision -State $s -Changes @{ backend = $Now; frontend = $null } -StopHookActive $false
$line = Format-GuardLine $stop
Write-Check "AC17 end of turn refused" ($stop.Action -eq "Remind" -and $stop.Id -eq "G8") $line
Write-Check "AC17 line names the backend test command" ($line -like "Guardrail G8: run the backend checks: *docker compose run --rm backend-test pytest*") $line
Write-Check "AC17 line leaves out current checks" ($line -notmatch "pyright") $line
$stop = Get-GuardStopDecision -State $s -Changes @{ backend = $Now; frontend = $null } -StopHookActive $false
Write-Check "AC17 second end of turn allowed" ($stop.Action -eq "Allow")
$s = New-GuardState
$stop = Get-GuardStopDecision -State $s -Changes @{ backend = $null; frontend = $Now } -StopHookActive $true
Write-Check "AC17 allowed while the stop hook is active" ($stop.Action -eq "Allow")
$s = New-GuardState
$s.tripped = "G5"
$stop = Get-GuardStopDecision -State $s -Changes @{ backend = $Now; frontend = $null } -StopHookActive $false
Write-Check "AC17 allowed while G5 is tripped" ($stop.Action -eq "Allow")
$s = New-GuardState
$stop = Get-GuardStopDecision -State $s -Changes @{ backend = $null; frontend = $Now } -StopHookActive $false
Write-Check "AC17 frontend change without checks names four commands" `
    ($stop.Id -eq "G8" -and ([regex]::Matches((Format-GuardLine $stop), "frontend-test")).Count -eq 4) (Format-GuardLine $stop)
# AC18: checks are current, or nothing changed.
$s = New-GreenState ($BackendChecks + $FrontendChecks) $After
$stop = Get-GuardStopDecision -State $s -Changes @{ backend = $Now; frontend = $Now } -StopHookActive $false
Write-Check "AC18 checks green after the change" ($stop.Action -eq "Allow")
$s = New-GuardState
$stop = Get-GuardStopDecision -State $s -Changes @{ backend = $null; frontend = $null } -StopHookActive $false
Write-Check "AC18 no code changed" ($stop.Action -eq "Allow")
# A partial test run is not a green full run.
$s = New-GreenState @("backend-lint", "backend-types") $After
Invoke-Run $s $true "docker compose run --rm backend-test pytest -q tests/unit/test_x.py"
$stop = Get-GuardStopDecision -State $s -Changes @{ backend = $Now; frontend = $null } -StopHookActive $false
Write-Check "AC17 a partial test run does not count as the backend tests" ($stop.Id -eq "G8")

# --- Hook entry point for both tools (AC19, AC20, integration rows) ----------------------
$Hook = Join-Path $GuardDir "hook.ps1"
$StateDir = Join-Path $env:TEMP ("rrmc-guard-tests-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
$LinePattern = '^(Blocked by guardrail|Guardrail) G[1-8]: '

# Runs hook.ps1 as a tool runs it: JSON on standard input. Returns exit code, stdout, stderr.
function Invoke-Hook([string]$Tool, [string]$Event, $Payload, [string]$HookRoot = $Root) {
    $json = $Payload | ConvertTo-Json -Depth 6 -Compress
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = "powershell.exe"
    $info.Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Hook`" -Tool $Tool " +
        "-Event $Event -StateDir `"$StateDir`" -ProjectRoot `"$HookRoot`""
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.UseShellExecute = $false
    $process = [System.Diagnostics.Process]::Start($info)
    $process.StandardInput.Write($json)
    $process.StandardInput.Close()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    return @{ Exit = $process.ExitCode; Stdout = $stdout.Trim(); Stderr = $stderr.Trim() }
}

function Assert-HookBlock([string]$Name, $Result, [string]$Id) {
    Write-Check "$Name exits 2" ($Result.Exit -eq 2) "exit $($Result.Exit), stderr $($Result.Stderr)"
    Write-Check "$Name names $Id" ($Result.Stderr -like "Blocked by guardrail ${Id}: *") $Result.Stderr
    Write-Check "$Name line matches AC19" ($Result.Stderr -match $LinePattern -and
        @($Result.Stderr -split "`n").Count -eq 1) $Result.Stderr
}

function New-ClaudeInput([string]$Event, [string]$ToolName, $ToolInput, [string]$Session = "claude-a") {
    @{ session_id = $Session; hook_event_name = $Event; cwd = $Root; tool_name = $ToolName; tool_input = $ToolInput }
}

function New-CodexInput([string]$Event, [string]$ToolName, $ToolInput, [string]$Session = "codex-a") {
    @{ session_id = $Session; hook_event_name = $Event; cwd = $Root; turn_id = "t1"; tool_name = $ToolName
        tool_input = $ToolInput }
}

# AC1 (Claude Code): Read of .env is blocked.
$r = Invoke-Hook claude PreToolUse (New-ClaudeInput PreToolUse Read @{ file_path = "$Root\.env" })
Assert-HookBlock "claude Read .env" $r "G1"
Write-Check "claude block line names no file content" ($r.Stderr -notmatch "RRMC_") $r.Stderr
# AC5 (Codex): docker compose up is blocked.
$r = Invoke-Hook codex PreToolUse (New-CodexInput PreToolUse Bash @{ command = "docker compose up" })
Assert-HookBlock "codex Bash docker compose up" $r "G2"
# Codex can send the command as a list of arguments.
$r = Invoke-Hook codex PreToolUse (New-CodexInput PreToolUse Bash @{ command = @("bash", "-lc", "cat .env") })
Assert-HookBlock "codex Bash argument list" $r "G1"
# Codex apply_patch of guard config and of a protected file.
$patch = "*** Begin Patch`n*** Update File: .codex/config.toml`n@@`n-a`n+b`n*** End Patch"
$r = Invoke-Hook codex PreToolUse (New-CodexInput PreToolUse apply_patch @{ command = $patch })
Assert-HookBlock "codex apply_patch guard config" $r "G4"
$patch = "*** Begin Patch`n*** Add File: source/import/x.txt`n+x`n*** End Patch"
$r = Invoke-Hook codex PreToolUse (New-CodexInput PreToolUse apply_patch @{ command = $patch })
Assert-HookBlock "codex apply_patch protected data" $r "G1"
# Claude Code: other tools.
$r = Invoke-Hook claude PreToolUse (New-ClaudeInput PreToolUse Edit @{ file_path = "$Root\.claude\settings.json"; old_string = "a"; new_string = "b" })
Assert-HookBlock "claude Edit settings.json" $r "G4"
$r = Invoke-Hook claude PreToolUse (New-ClaudeInput PreToolUse PowerShell @{ command = "Remove-Item -Recurse docs" })
Assert-HookBlock "claude PowerShell Remove-Item -Recurse" $r "G3"
$r = Invoke-Hook claude PreToolUse (New-ClaudeInput PreToolUse Glob @{ pattern = "source/**/*.jpg" })
Assert-HookBlock "claude Glob source" $r "G1"
$r = Invoke-Hook claude PreToolUse (New-ClaudeInput PreToolUse WebFetch @{ url = "http://127.0.0.1:8000/api/receipts"; prompt = "x" })
Assert-HookBlock "claude WebFetch app port" $r "G2"
$r = Invoke-Hook claude PreToolUse (New-ClaudeInput PreToolUse "mcp__claude-in-chrome__navigate" @{ url = "http://localhost:5173/"; tabId = 1 })
Assert-HookBlock "claude browser app port" $r "G2"
# Allowed calls exit 0 without output.
$r = Invoke-Hook claude PreToolUse (New-ClaudeInput PreToolUse Read @{ file_path = "$Root\backend\app\settings.py" })
Write-Check "claude Read of code runs" ($r.Exit -eq 0 -and $r.Stdout -eq "" -and $r.Stderr -eq "") "exit $($r.Exit) $($r.Stderr)"
$r = Invoke-Hook codex PreToolUse (New-CodexInput PreToolUse Bash @{ command = "git status" })
Write-Check "codex git status runs" ($r.Exit -eq 0 -and $r.Stderr -eq "") "exit $($r.Exit) $($r.Stderr)"

# AC11 (Claude Code): three red check runs, then an Edit is blocked; a user message resets.
foreach ($i in 1..3) {
    Invoke-Hook claude PostToolUse (New-ClaudeInput PostToolUse Edit @{ file_path = "$Root\backend\app\f$i.py" } "claude-red") | Out-Null
    $failed = New-ClaudeInput PostToolUseFailure Bash @{ command = $BackendTests } "claude-red"
    $failed.error = "Exit code 1"
    Invoke-Hook claude PostToolUseFailure $failed | Out-Null
}
$r = Invoke-Hook claude PreToolUse (New-ClaudeInput PreToolUse Edit @{ file_path = "$Root\backend\app\f4.py" } "claude-red")
Assert-HookBlock "claude Edit after three red rounds" $r "G5"
Invoke-Hook claude UserPromptSubmit @{ session_id = "claude-red"; hook_event_name = "UserPromptSubmit"; prompt = "go on" } | Out-Null
$r = Invoke-Hook claude PreToolUse (New-ClaudeInput PreToolUse Edit @{ file_path = "$Root\backend\app\f4.py" } "claude-red")
Write-Check "claude Edit after the user's message runs" ($r.Exit -eq 0) "exit $($r.Exit) $($r.Stderr)"

# AC15 (Claude Code): a test edit after a red run is reminded and recorded.
$failed = New-ClaudeInput PostToolUseFailure Bash @{ command = $BackendTests } "claude-g7"
$failed.error = "Exit code 1"
Invoke-Hook claude PostToolUseFailure $failed | Out-Null
$r = Invoke-Hook claude PostToolUse (New-ClaudeInput PostToolUse Edit @{ file_path = "$Root\backend\tests\unit\test_x.py" } "claude-g7")
$context = ""
try { $context = ($r.Stdout | ConvertFrom-Json).hookSpecificOutput.additionalContext } catch { $context = "" }
Write-Check "claude G7 reminder as additional context" ($r.Exit -eq 0 -and $context -eq $G7Line) "stdout $($r.Stdout)"
$log = Join-Path $StateDir "test-edits.log"
$logLine = if (Test-Path $log) { @(Get-Content $log)[-1] } else { "" }
Write-Check "claude G7 edit recorded" ($logLine -match "`tbackend/tests/unit/test_x\.py$") $logLine

# Codex: red runs are read from tool_response.
$red = New-CodexInput PostToolUse Bash @{ command = $BackendTests } "codex-red"
$red.tool_response = @{ exit_code = 1; output = "1 failed" }
foreach ($i in 1..3) { Invoke-Hook codex PostToolUse $red | Out-Null }
$r = Invoke-Hook codex PreToolUse (New-CodexInput PreToolUse Bash @{ command = "git status" } "codex-red")
Assert-HookBlock "codex call after three red rounds" $r "G5"

# AC17 (Claude Code Stop): changed backend code without green checks, in a temporary repository.
$Repo = Join-Path $StateDir "repo"
New-Item -ItemType Directory -Force -Path (Join-Path $Repo "backend\app") | Out-Null
& git -C $Repo init -q 2>$null
[System.IO.File]::WriteAllText((Join-Path $Repo "backend\app\x.py"), "x = 1`n")
$stopInput = @{ session_id = "claude-stop"; hook_event_name = "Stop"; stop_hook_active = $false }
$r = Invoke-Hook claude Stop $stopInput $Repo
Write-Check "claude Stop refused with G8" ($r.Exit -eq 2 -and $r.Stderr -like "Guardrail G8: run the backend checks: *") "exit $($r.Exit) $($r.Stderr)"
$r = Invoke-Hook claude Stop $stopInput $Repo
Write-Check "claude second Stop allowed" ($r.Exit -eq 0) "exit $($r.Exit) $($r.Stderr)"
$stopInput.session_id = "claude-stop-2"; $stopInput.stop_hook_active = $true
$r = Invoke-Hook claude Stop $stopInput $Repo
Write-Check "claude Stop with stop_hook_active allowed" ($r.Exit -eq 0) "exit $($r.Exit) $($r.Stderr)"
$codexStop = @{ session_id = "codex-stop"; hook_event_name = "Stop"; turn_id = "t1"; stop_hook_active = $false }
$r = Invoke-Hook codex Stop $codexStop $Repo
$decision = $null
try { $decision = $r.Stdout | ConvertFrom-Json } catch { $decision = $null }
Write-Check "codex Stop refused with a block decision" ($r.Exit -eq 0 -and $null -ne $decision -and
    $decision.PSObject.Properties["decision"] -and $decision.decision -eq "block" -and $decision.reason -match $LinePattern) "stdout $($r.Stdout)"

# A hook that cannot parse its input fails, so that onFailure "block" stops the call.
$info = New-Object System.Diagnostics.ProcessStartInfo
$info.FileName = "powershell.exe"
$info.Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Hook`" -Tool claude -Event PreToolUse -StateDir `"$StateDir`""
$info.RedirectStandardInput = $true; $info.RedirectStandardError = $true; $info.UseShellExecute = $false
$process = [System.Diagnostics.Process]::Start($info)
$process.StandardInput.Write("not json"); $process.StandardInput.Close()
$process.StandardError.ReadToEnd() | Out-Null
$process.WaitForExit()
Write-Check "invalid input fails the hook" ($process.ExitCode -ne 0 -and $process.ExitCode -ne 2) "exit $($process.ExitCode)"

# --- Codex configuration (PC13, AC24 set-up) ---------------------------------------------
$codexDir = Join-Path $ProjectRoot ".codex"
$codexHooks = Join-Path $codexDir "hooks.json"
$hooksConfig = $null
if (Test-Path $codexHooks) { try { $hooksConfig = Get-Content -Raw $codexHooks | ConvertFrom-Json } catch { } }
Write-Check "codex hooks.json is valid JSON" ($null -ne $hooksConfig)
foreach ($event in @("PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop")) {
    $commands = @()
    if ($null -ne $hooksConfig -and $hooksConfig.hooks.PSObject.Properties[$event]) {
        $commands = @($hooksConfig.hooks.$event | ForEach-Object { $_.hooks } | ForEach-Object { $_.commandWindows })
    }
    Write-Check "codex $event calls hook.ps1 -Tool codex" `
        ([bool]($commands | Where-Object { $_ -like "*.agents/guardrails/hook.ps1 -Tool codex -Event $event" }))
}
$codexConfig = if (Test-Path (Join-Path $codexDir "config.toml")) { Get-Content -Raw (Join-Path $codexDir "config.toml") } else { "" }
Write-Check "codex config sets the elevated Windows sandbox" ($codexConfig -match '(?m)^\[windows\]\s*\r?\nsandbox = "elevated"')
Write-Check "codex config turns hooks on" ($codexConfig -match '(?m)^\[features\]\s*\r?\nhooks = true')
Write-Check "codex config denies .env and source" ($codexConfig -match '"\.env" = "deny"' -and $codexConfig -match '"source/\*\*" = "deny"')
$rules = if (Test-Path (Join-Path $codexDir "rules\guardrails.rules")) { Get-Content -Raw (Join-Path $codexDir "rules\guardrails.rules") } else { "" }
Write-Check "codex rules forbid git push and volume removal" `
    ($rules -match 'pattern = \["git", "push"\]' -and $rules -match '"docker", "volume"')

# --- Claude Code configuration (Plan P4) -------------------------------------------------
$claudeSettings = $null
$claudePath = Join-Path $ProjectRoot ".claude\settings.json"
if (Test-Path $claudePath) { try { $claudeSettings = Get-Content -Raw $claudePath | ConvertFrom-Json } catch { } }
Write-Check "claude settings.json is valid JSON" ($null -ne $claudeSettings)
foreach ($event in @("PreToolUse", "PostToolUse", "PostToolUseFailure", "UserPromptSubmit", "Stop")) {
    $handlers = @()
    if ($null -ne $claudeSettings -and $claudeSettings.hooks.PSObject.Properties[$event]) {
        $handlers = @($claudeSettings.hooks.$event | ForEach-Object { $_.hooks })
    }
    $wired = @($handlers | Where-Object { ($_.args -join " ") -like "*.agents/guardrails/hook.ps1 -Tool claude -Event $event" })
    Write-Check "claude $event calls hook.ps1 -Tool claude" ($wired.Count -eq 1)
    if ($event -eq "PreToolUse") {
        Write-Check "claude PreToolUse blocks when the hook fails" ($wired.Count -eq 1 -and $wired[0].onFailure -eq "block")
    }
}
$deny = if ($null -ne $claudeSettings) { @($claudeSettings.permissions.deny) } else { @() }
foreach ($rule in @("Read(/.env)", "Read(/source/**)", "Edit(/.codex/**)", "Edit(/.agents/guardrails/**)", "Bash(git push:*)")) {
    Write-Check "claude deny rule $rule" ($deny -contains $rule)
}

# AC20: an allowed call costs less than 1 second (median of 20).
$times = foreach ($i in 1..20) {
    (Measure-Command { Invoke-Hook claude PreToolUse (New-ClaudeInput PreToolUse Read @{ file_path = "$Root\docs\x.md" } "claude-time") }).TotalMilliseconds
}
$median = (@($times | Sort-Object))[10]
Write-Check "AC20 median hook time under 1 s" ($median -lt 1000) "median $([int]$median) ms"
Write-Host "Median hook time: $([int]$median) ms"
Write-Host "Hook test state: $StateDir"

Write-Host ""
if ($Failures.Count -gt 0) {
    Write-Host "$($Failures.Count) guard test(s) failed, $script:Passed passed." -ForegroundColor Red
    exit 1
}
Write-Host "All $script:Passed guard tests passed." -ForegroundColor Green
exit 0
