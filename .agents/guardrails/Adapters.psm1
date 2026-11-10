# Adapters between each tool's hook input and output and the guard's normalized calls
# (specs/features/agent-guardrails.md, Plan P1). Field names are in Plan P1 "Hook input".

Set-StrictMode -Version 2
Import-Module (Join-Path $PSScriptRoot "Guard.psm1")

function Get-Field($Object, [string]$Name) {
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Get-StringValues($Object) {
    if ($null -eq $Object) { return @() }
    if ($Object -is [string]) { return @($Object) }
    if ($Object -is [System.Collections.IEnumerable]) { return @($Object | ForEach-Object { Get-StringValues $_ }) }
    if ($Object -is [psobject]) { return @($Object.PSObject.Properties | ForEach-Object { Get-StringValues $_.Value }) }
    return @()
}

# A tool the guard does not know, such as a browser or other MCP tool: every string that
# looks like an address is checked against G2, and every `*path*` field against G1 and G4.
function ConvertFrom-OtherTool($ToolInput, [string]$SessionId) {
    $strings = @(Get-StringValues $ToolInput)
    $urls = @($strings | Where-Object { $_ -match '://|^(localhost|127\.|0\.0\.0\.0|\[::1\])' })
    $paths = @()
    if ($null -ne $ToolInput -and $ToolInput -is [psobject]) {
        $paths = @($ToolInput.PSObject.Properties | Where-Object { $_.Name -match '(?i)path' -and $_.Value -is [string] } |
            ForEach-Object { $_.Value })
    }
    New-GuardCall -Kind other -Paths $paths -Urls $urls -SessionId $SessionId
}

function Get-SessionId($HookInput) {
    $id = [string](Get-Field $HookInput "session_id")
    if (-not $id) { $id = "default" }
    return ($id -replace '[^A-Za-z0-9_-]', '')
}

function ConvertFrom-ClaudeCall($HookInput) {
    $session = Get-SessionId $HookInput
    $tool = [string](Get-Field $HookInput "tool_name")
    $in = Get-Field $HookInput "tool_input"
    $event = [string](Get-Field $HookInput "hook_event_name")
    $exitOk = $null
    if ($event -eq "PostToolUse") { $exitOk = $true }
    if ($event -eq "PostToolUseFailure") { $exitOk = $false }
    switch ($tool) {
        "Read" { return New-GuardCall -Kind read -Paths @(Get-Field $in "file_path") -SessionId $session }
        { $_ -in @("Edit", "Write", "MultiEdit") } {
            return New-GuardCall -Kind write -Paths @(Get-Field $in "file_path") -SessionId $session
        }
        "NotebookEdit" { return New-GuardCall -Kind write -Paths @(Get-Field $in "notebook_path") -SessionId $session }
        { $_ -in @("Grep", "Glob") } {
            $paths = @((Get-Field $in "path"), (Get-Field $in "glob")) | Where-Object { $_ }
            if ($tool -eq "Glob") { $paths = @($paths) + @(Get-Field $in "pattern") }
            return New-GuardCall -Kind search -Paths @($paths | Where-Object { $_ }) -SessionId $session
        }
        { $_ -in @("Bash", "PowerShell") } {
            return New-GuardCall -Kind shell -Command ([string](Get-Field $in "command")) -ExitOk $exitOk -SessionId $session
        }
        "WebFetch" { return New-GuardCall -Kind web -Urls @(Get-Field $in "url") -SessionId $session }
    }
    return ConvertFrom-OtherTool $in $session
}

# Codex reports a failed shell command in `tool_response`. The field is not documented
# (Plan P1), so known forms are tried; $null means "unknown, do not count".
function Get-CodexExitOk($Response) {
    if ($null -eq $Response) { return $null }
    foreach ($name in @("exit_code", "exitCode")) {
        $code = Get-Field $Response $name
        if ($null -ne $code) { return ([int]$code -eq 0) }
    }
    $text = ($Response | Out-String)
    if ($Response -isnot [string]) { $text = $Response | ConvertTo-Json -Depth 4 -Compress }
    if ($text -match '(?i)exit[ _]?code"?\s*[:=]\s*(-?\d+)') { return ([int]$Matches[1] -eq 0) }
    return $null
}

function Get-PatchPaths([string]$Patch) {
    $paths = [regex]::Matches($Patch, '(?m)^\*\*\* (?:Add File|Update File|Delete File|Move to):\s*(.+?)\s*$') |
        ForEach-Object { $_.Groups[1].Value }
    return @($paths)
}

function ConvertFrom-CodexCall($HookInput) {
    $session = Get-SessionId $HookInput
    $tool = [string](Get-Field $HookInput "tool_name")
    $in = Get-Field $HookInput "tool_input"
    $command = Get-Field $in "command"
    if ($command -is [System.Array]) { $command = ($command | ForEach-Object { [string]$_ }) -join " " }
    switch ($tool) {
        "Bash" {
            $exitOk = Get-CodexExitOk (Get-Field $HookInput "tool_response")
            return New-GuardCall -Kind shell -Command ([string]$command) -ExitOk $exitOk -SessionId $session
        }
        "apply_patch" {
            return New-GuardCall -Kind write -Paths @(Get-PatchPaths ([string]$command)) -SessionId $session
        }
    }
    return ConvertFrom-OtherTool $in $session
}

# Turns a decision into what each tool expects: @{ Exit; Stdout; Stderr }.
function ConvertTo-HookOutput([string]$Tool, [string]$Event, $Decision) {
    $none = @{ Exit = 0; Stdout = ""; Stderr = "" }
    if ($null -eq $Decision -or $Decision.Action -eq "Allow") { return $none }
    $line = Format-GuardLine $Decision
    if ($Decision.Action -eq "Block") { return @{ Exit = 2; Stdout = ""; Stderr = $line } }
    if ($Event -eq "Stop") {
        if ($Tool -eq "codex") {
            return @{ Exit = 0; Stdout = (@{ decision = "block"; reason = $line } | ConvertTo-Json -Compress); Stderr = "" }
        }
        return @{ Exit = 2; Stdout = ""; Stderr = $line }
    }
    $context = @{ hookSpecificOutput = @{ hookEventName = $Event; additionalContext = $line } }
    return @{ Exit = 0; Stdout = ($context | ConvertTo-Json -Compress); Stderr = "" }
}

Export-ModuleMember -Function ConvertFrom-ClaudeCall, ConvertFrom-CodexCall, ConvertTo-HookOutput, Get-SessionId, Get-Field
