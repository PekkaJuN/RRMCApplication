# Hook entry point of the agent guardrails for Claude Code and Codex
# (specs/features/agent-guardrails.md). Reads the tool's hook input from standard input,
# decides with Guard.psm1 and answers the way the tool expects.
#
# Any error makes the script exit with code 1. Claude Code's PreToolUse hook is set to
# onFailure "block", so an error blocks the call there; Codex lets it run (known limit).

param(
    [Parameter(Mandatory = $true)][ValidateSet("claude", "codex")][string]$Tool,
    [Parameter(Mandatory = $true)][string]$Event,
    [string]$StateDir = "",
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2
Import-Module (Join-Path $PSScriptRoot "Guard.psm1")
Import-Module (Join-Path $PSScriptRoot "Adapters.psm1")

if (-not $ProjectRoot) {
    $ProjectRoot = if ($env:CLAUDE_PROJECT_DIR) { $env:CLAUDE_PROJECT_DIR } else { Split-Path (Split-Path $PSScriptRoot) }
}
if (-not $StateDir) { $StateDir = Join-Path $PSScriptRoot "state" }

function Read-State([string]$Path) {
    $state = New-GuardState
    if (-not (Test-Path $Path)) { return $state }
    $saved = Get-Content -Raw -Path $Path | ConvertFrom-Json
    foreach ($property in $state.PSObject.Properties) {
        $value = Get-Field $saved $property.Name
        if ($null -ne $value) { $state.($property.Name) = $value }
    }
    $state.editsSinceRun = @($state.editsSinceRun)
    return $state
}

# Windows PowerShell 5.1 turns a native command's standard error into a terminating error
# under ErrorActionPreference Stop, so git runs with Continue.
function Get-Branch {
    $ErrorActionPreference = "Continue"
    $branch = & git -C $ProjectRoot rev-parse --abbrev-ref HEAD 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $branch) { return "unknown" }
    return "$branch".Trim()
}

# The changed files of the repository with their write times, from `git status` (ignored
# files excluded). Deleted files have no write time and are left out.
function Get-ChangedFiles {
    $files = New-Object System.Collections.Generic.List[object]
    $ErrorActionPreference = "Continue"
    $lines = & git -C $ProjectRoot status --porcelain --untracked-files=all 2>$null
    if ($LASTEXITCODE -ne 0) { return @() }
    foreach ($line in @($lines)) {
        if ("$line".Length -lt 4) { continue }
        $path = "$line".Substring(3).Trim('"')
        if ($path -match ' -> (.+)$') { $path = $Matches[1].Trim('"') }
        $full = Join-Path $ProjectRoot $path
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { continue }
        $files.Add([pscustomobject]@{ Path = $path; Time = (Get-Item -LiteralPath $full).LastWriteTimeUtc })
    }
    # PowerShell 5.1 cannot wrap a List[object] in @(); ToArray() avoids that.
    return $files.ToArray()
}

# The newest write time of the changed files of each part.
function Get-PartChanges {
    $changes = @{ backend = $null; frontend = $null }
    foreach ($file in @(Get-ChangedFiles)) {
        $part = ($file.Path -split '/')[0].ToLowerInvariant()
        if (-not $changes.ContainsKey($part)) { continue }
        if ($null -eq $changes[$part] -or $file.Time -gt $changes[$part]) { $changes[$part] = $file.Time }
    }
    return $changes
}

# The files that changed since the state's scanFrom (AC28); none while scanFrom is empty.
function Get-ShellChanges($State) {
    if (-not $State.scanFrom) { return @() }
    $from = [datetime]::Parse($State.scanFrom, [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
    return @(Get-ChangedFiles | Where-Object { $_.Time -gt $from } | ForEach-Object { $_.Path })
}

[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$hookInput = [Console]::In.ReadToEnd() | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
$statePath = Join-Path $StateDir ((Get-SessionId $hookInput) + ".json")
$state = Read-State $statePath
$call = if ($Tool -eq "claude") { ConvertFrom-ClaudeCall $hookInput } else { ConvertFrom-CodexCall $hookInput }
$decision = $null

switch ($Event) {
    "PreToolUse" {
        $decision = Get-GuardDecision -Call $call -State $state -ProjectRoot $ProjectRoot
    }
    { $_ -in @("PostToolUse", "PostToolUseFailure") } {
        if ($call.Kind -eq "write") {
            $paths = @($call.Paths | ForEach-Object { ConvertTo-GuardPath $_ $ProjectRoot })
            $result = Update-GuardAfterEdit -State $state -Paths $paths
            $decision = $result.Decision
            if (@($result.TestPaths).Count -gt 0) {
                $branch = Get-Branch
                $stamp = [datetime]::UtcNow.ToString("o")
                $lines = @($result.TestPaths | ForEach-Object { "$stamp`t$branch`t$_" })
                Add-Content -Path (Join-Path $StateDir "test-edits.log") -Value $lines -Encoding UTF8
            }
        } elseif ($call.Kind -eq "shell" -and $null -ne $call.ExitOk) {
            $now = [datetime]::UtcNow
            $changed = if ($null -ne (Get-CheckRun $call.Command)) { @(Get-ShellChanges $state) } else { @() }
            Update-GuardAfterRun -State $state -Command $call.Command -ExitOk $call.ExitOk -Now $now -ChangedPaths $changed
        }
    }
    "UserPromptSubmit" { Reset-GuardOnUserMessage -State $state }
    "Stop" {
        $active = [bool](Get-Field $hookInput "stop_hook_active")
        $decision = Get-GuardStopDecision -State $state -Changes (Get-PartChanges) -StopHookActive $active
    }
}

$state | ConvertTo-Json -Depth 5 | Set-Content -Path $statePath -Encoding UTF8
$output = ConvertTo-HookOutput $Tool $Event $decision
if ($output.Stdout) { [Console]::Out.WriteLine($output.Stdout) }
if ($output.Stderr) { [Console]::Error.WriteLine($output.Stderr) }
exit $output.Exit
