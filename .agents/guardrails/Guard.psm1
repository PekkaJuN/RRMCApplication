# Rules of the agent guardrails (specs/features/agent-guardrails.md, Plan P1-P3).
# Pure functions: a normalized call and the state in, a decision out. No input or output.
# Reasons name a kind of target and never repeat the call's text, so no file content or
# receipt data can reach the agent through a block line (AC19).

Set-StrictMode -Version 2

# --- Calls and decisions ----------------------------------------------------------------

function New-GuardCall {
    param([string]$Kind = "other", [string[]]$Paths = @(), [string]$Command = "",
        [string[]]$Urls = @(), $ExitOk = $null, [string]$SessionId = "session")
    [pscustomobject]@{ Kind = $Kind; Paths = @($Paths); Command = $Command; Urls = @($Urls)
        ExitOk = $ExitOk; SessionId = $SessionId }
}

function New-Decision([string]$Action, [string]$Id = "", [string]$Reason = "") {
    [pscustomobject]@{ Action = $Action; Id = $Id; Reason = $Reason }
}

function New-Block([string]$Id, [string]$Reason) { New-Decision "Block" $Id $Reason }

$script:Allow = New-Decision "Allow"

function Format-GuardLine($Decision) {
    if ($Decision.Action -eq "Block") {
        return "Blocked by guardrail $($Decision.Id): $($Decision.Reason). Stop and ask the user if you need this."
    }
    return "Guardrail $($Decision.Id): $($Decision.Reason)"
}

# --- Paths ------------------------------------------------------------------------------

# Makes a path relative to the project root when it is inside it, with `/` separators and
# without quotes or a leading `./`. Comparison is case-insensitive, as on Windows.
function ConvertTo-GuardPath([string]$Path, [string]$ProjectRoot) {
    $p = $Path.Trim().Trim('"', "'", '`') -replace '\\', '/'
    $root = ($ProjectRoot -replace '\\', '/').TrimEnd('/')
    if ($root -and $p.StartsWith("$root/", [StringComparison]::OrdinalIgnoreCase)) {
        $p = $p.Substring($root.Length + 1)
    } elseif ($root -and $p -ieq $root) {
        $p = "."
    }
    while ($p.StartsWith("./")) { $p = $p.Substring(2) }
    return $p
}

function Get-Segments([string]$Path) { @($Path -split '/' | Where-Object { $_ -ne "" }) }

# G1: .env and .env.<x> except .env.example; a `source` folder; SQLite files; service keys.
function Test-ProtectedPath([string]$Path) {
    $segments = @(Get-Segments $Path)
    if ($segments.Count -eq 0) { return $false }
    $name = $segments[-1]
    if ($name -ieq ".env") { return $true }
    if ($name -like ".env.*" -and $name -ine ".env.example") { return $true }
    if ($name -match '(?i)\.(db|sqlite|sqlite3)(-journal|-wal|-shm)?$') { return $true }
    if ($name -like "service_account*.json") { return $true }
    foreach ($segment in $segments) {
        if ($segment -ieq "node_modules") { return $false }
        if ($segment -ieq "source") { return $true }
    }
    return $false
}

# --- Shell text -------------------------------------------------------------------------

# Splits a shell command into its simple commands, so that each part is checked on its own:
# on &&, ||, ;, |, newlines, the brackets of ( ), $( ) and backticks, and a single `&`
# (background in Bash, the call operator in PowerShell) that is not part of a redirection
# such as `2>&1` or `&>`.
function Split-ShellParts([string]$Command) {
    @($Command -split '&&|\|\||;|\||\r?\n|\$\(|\(|\)|`|(?<![>&\d])&(?![&>\d])' |
        ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
}

# Splits one simple command into words, keeping quoted text together and removing quotes.
function Split-ShellWords([string]$Part) {
    # Only the outer pair of quotes goes, so `"sh -c 'x'"` keeps the inner quotes (AC31).
    $words = [regex]::Matches($Part, '"[^"]*"|''[^'']*''|[^\s"'']+') | ForEach-Object {
        $value = $_.Value
        if ($value.Length -ge 2 -and $value[0] -in @('"', "'") -and $value[-1] -eq $value[0]) {
            $value.Substring(1, $value.Length - 2)
        } else { $value }
    }
    return @($words)
}

# Words before a command that only change how it runs (spec change 3, AC31). An assignment
# `NAME=value` is dropped too; the whole text is still checked for COMPOSE_FILE (AC30).
$script:PrefixWords = @("env", "command", "builtin", "exec", "sudo", "nohup", "time")
$script:PrefixValueOptions = @("-u", "--unset", "-C", "--chdir", "-g", "--group", "--user")
$script:PrefixPattern = '^\s*(?<word>[A-Za-z_][A-Za-z0-9_]*=("[^"]*"|''[^'']*''|\S*)|-\S+|\S+)(\s+|$)'

# Drops the prefix words of a part, keeping the rest of its text (and its quotes) unchanged.
function Remove-CommandPrefix([string]$Part) {
    $rest = $Part
    $inPrefix = $false
    while ($rest -match $script:PrefixPattern) {
        $word = $Matches.word
        $length = $Matches[0].Length
        $isAssignment = $word -match '^[A-Za-z_][A-Za-z0-9_]*='
        $isPrefix = $script:PrefixWords -contains $word.ToLowerInvariant()
        $isOption = $inPrefix -and $word.StartsWith("-")
        if (-not ($isAssignment -or $isPrefix -or $isOption)) { break }
        $rest = $rest.Substring($length)
        if ($isOption -and $script:PrefixValueOptions -ccontains $word -and $rest -match $script:PrefixPattern) {
            $rest = $rest.Substring($Matches[0].Length)
        }
        if ($isPrefix) { $inPrefix = $true }
    }
    return $rest.Trim()
}

# The command text that a shell wrapper runs, or $null: `bash -c "..."`, `pwsh -Command ...`,
# `cmd /c ...`, `Invoke-Expression ...` (AC31).
function Get-WrappedCommand([string[]]$Words) {
    $command = Get-CommandName $Words
    for ($i = 1; $i -lt $Words.Count; $i++) {
        $word = $Words[$i]
        if ($command -in @("bash", "sh", "zsh", "dash") -and $word -cmatch '^-[a-zA-Z]*c$') {
            if ($i + 1 -lt $Words.Count) { return $Words[$i + 1] }
            return $null
        }
        if ($command -in @("powershell", "pwsh") -and $word -match '^(?i)-c(o(m(m(a(n(d)?)?)?)?)?)?$') {
            return (@($Words | Select-Object -Skip ($i + 1)) -join " ")
        }
        if ($command -eq "cmd" -and $word -match '^(?i)/[ck]$') {
            return (@($Words | Select-Object -Skip ($i + 1)) -join " ")
        }
    }
    if ($command -in @("invoke-expression", "iex")) {
        return (@($Words | Select-Object -Skip 1 | Where-Object { $_ -notmatch '^(?i)-command$' }) -join " ")
    }
    return $null
}

# The parts every rule checks: each simple command without its prefix words, and, for a shell
# wrapper, the wrapper itself and the parts of the command it runs, unwrapped again.
function Get-ShellParts([string]$Command, [int]$Depth = 0) {
    $result = New-Object System.Collections.Generic.List[string]
    foreach ($part in @(Split-ShellParts $Command)) {
        $stripped = Remove-CommandPrefix $part
        if ($stripped -eq "") { continue }
        $result.Add($stripped)
        $inner = Get-WrappedCommand @(Split-ShellWords $stripped)
        if ($inner -and $Depth -lt 5) {
            foreach ($innerPart in @(Get-ShellParts $inner ($Depth + 1))) { $result.Add($innerPart) }
        }
    }
    return @($result)
}

# The words of a part that may name a file: each word, its value after `=`, and the parts
# around redirection signs.
function Get-PathWords([string[]]$Words) {
    $result = New-Object System.Collections.Generic.List[string]
    foreach ($word in $Words) {
        foreach ($piece in ($word -split '[<>]')) {
            if ($piece -eq "") { continue }
            $result.Add($piece)
            if ($piece -match '^-{1,2}[^=]+=(.+)$') { $result.Add($Matches[1]) }
        }
    }
    return $result
}

# Separates a part's redirections from its other words. Targets are the files written to;
# a stream (`2>&1`) or a null device (`/dev/null`, `$null`, `NUL`) is no target, and an
# input redirection (`< file`) stays a plain word, because it only reads.
function Split-Redirections([string[]]$Words) {
    $plain = New-Object System.Collections.Generic.List[string]
    $targets = New-Object System.Collections.Generic.List[string]
    for ($i = 0; $i -lt $Words.Count; $i++) {
        $rest = $Words[$i]
        while ($rest -match '^(?<pre>[^<>]*?)(?<fd>[0-9&*]?)(?<op>>>?|<)(?<post>.*)$') {
            $pre = $Matches.pre; $op = $Matches.op; $post = $Matches.post
            if ($pre -ne "") { $plain.Add($pre) }
            $target = $post
            $next = ""
            if ($target -match '^(?<t>[^<>]*)(?<more>[0-9&*]?(>>?|<).*)$') {
                $target = $Matches.t; $next = $Matches.more
            }
            if ($target -eq "" -and $next -eq "" -and $i + 1 -lt $Words.Count) { $i++; $target = $Words[$i] }
            if ($op -eq "<") { if ($target -ne "") { $plain.Add($target) } }
            elseif ($target -ne "" -and $target -notmatch '^&\d*-?$' -and
                    $target -notmatch '^(?i)(/dev/null|\$null|nul)$') {
                $targets.Add($target)
            }
            $rest = $next
        }
        if ($rest -ne "") { $plain.Add($rest) }
    }
    return @{ Words = @($plain); Targets = @($targets) }
}

function Get-CommandName([string[]]$Words) {
    if ($Words.Count -eq 0) { return "" }
    $name = ($Words[0] -replace '\\', '/').Split('/')[-1]
    return ($name -replace '(?i)\.exe$', '').ToLowerInvariant()
}

# --- G1 ---------------------------------------------------------------------------------

# A recursive search or listing whose root is the project root (or unknown) reads source/.
$script:SearchValueOptions = @{
    "grep" = @("-e", "-f", "--include", "--exclude", "--exclude-dir", "-m", "-A", "-B", "-C")
    "rg" = @("-e", "-g", "--glob", "-t", "--type", "-m", "-A", "-B", "-C")
    "find" = @()
    "ls" = @()
    "dir" = @()
    "get-childitem" = @("-filter", "-include", "-exclude", "-depth", "-attributes")
    "gci" = @("-filter", "-include", "-exclude", "-depth", "-attributes")
    "select-string" = @("-pattern", "-include", "-exclude", "-encoding", "-context")
    "sls" = @("-pattern", "-include", "-exclude", "-encoding", "-context")
    "tree" = @()
}

# grep and rg options are case-sensitive (`-c` counts, `-C` takes a value); PowerShell
# parameters are not.
function Test-ValueOption([string]$Command, [string[]]$Options, [string]$Word) {
    if ($Command -in @("grep", "egrep", "fgrep", "rg")) { return $Options -ccontains $Word }
    return $Options -contains $Word
}

function Test-RecursiveFlag([string]$Command, [string[]]$Arguments) {
    switch ($Command) {
        "grep" { return [bool]($Arguments | Where-Object { $_ -match '^-[A-Za-z]*[rR]' -or $_ -eq "--recursive" }) }
        "rg" { return [bool]($Arguments | Where-Object { $_ -in @("--no-ignore", "-u", "-uu", "-uuu") }) }
        "find" { return $true }
        "tree" { return $true }
        "ls" { return [bool]($Arguments | Where-Object { $_ -cmatch '^-[A-Za-z]*R' -or $_ -eq "--recursive" }) }
        "dir" { return [bool]($Arguments | Where-Object { $_ -ieq "/s" -or $_ -match '^(?i)-rec' -or $_ -ieq "-r" }) }
        default { return [bool]($Arguments | Where-Object { $_ -match '^(?i)-rec' -or $_ -ieq "-r" }) }
    }
}

function Get-SearchRoots([string]$Command, [string[]]$Arguments) {
    $valueOptions = $script:SearchValueOptions[$Command]
    $roots = New-Object System.Collections.Generic.List[string]
    $patternSeen = $Command -notin @("grep", "rg")
    for ($i = 0; $i -lt $Arguments.Count; $i++) {
        $word = $Arguments[$i]
        if ($word -match '^(?i)-path$|^(?i)-literalpath$') {
            if ($i + 1 -lt $Arguments.Count) { $roots.Add($Arguments[$i + 1]); $i++ }
            continue
        }
        if (Test-ValueOption $Command $valueOptions $word) {
            if ($word -cin @("-e", "-f") -or $word -ieq "-pattern") { $patternSeen = $true }
            $i++
            continue
        }
        if ($word.StartsWith("-") -or ($Command -eq "dir" -and $word.StartsWith("/"))) { continue }
        if ($Command -eq "find" -and $roots.Count -gt 0 -and $word.StartsWith("(")) { break }
        if (-not $patternSeen) { $patternSeen = $true; continue }
        $roots.Add($word)
    }
    return @($roots)
}

function Test-RootSearch([string]$Command, [string[]]$Arguments, [string]$ProjectRoot) {
    if (-not $script:SearchValueOptions.ContainsKey($Command)) { return $false }
    if (-not (Test-RecursiveFlag $Command $Arguments)) { return $false }
    $roots = @(Get-SearchRoots $Command $Arguments)
    if ($roots.Count -eq 0) { return $true }
    foreach ($root in $roots) {
        $relative = ConvertTo-GuardPath $root $ProjectRoot
        if ($relative -in @(".", "", "*", "/", "~") -or $relative.StartsWith("..") -or
                $relative -match '^[A-Za-z]:') {
            return $true
        }
    }
    return $false
}

# The indexes of a search command's arguments that are patterns, not files. A pattern file
# (`-f`, `--file`) and the files searched are not patterns, so they are still checked.
function Get-PatternIndexes([string]$Command, [string[]]$Arguments) {
    $indexes = New-Object System.Collections.Generic.List[int]
    $isGrep = $Command -in @("grep", "egrep", "fgrep", "rg")
    $isSls = $Command -in @("select-string", "sls")
    if (-not ($isGrep -or $isSls)) { return @() }
    $patternSeen = $false
    $optionsEnd = $false
    $valueOptions = if ($isGrep) { @($script:SearchValueOptions["grep"]) + @($script:SearchValueOptions["rg"]) + @("--file") }
        else { @($script:SearchValueOptions["select-string"]) + @("-path", "-literalpath") }
    for ($i = 0; $i -lt $Arguments.Count; $i++) {
        $word = $Arguments[$i]
        $lower = $word.ToLowerInvariant()
        if (-not $optionsEnd) {
            if ($isGrep -and $word -eq "--") { $optionsEnd = $true; continue }
            if (($isGrep -and $word -cin @("-e", "--regexp")) -or ($isSls -and $lower -eq "-pattern")) {
                if ($i + 1 -lt $Arguments.Count) { $indexes.Add($i + 1) }
                $patternSeen = $true; $i++; continue
            }
            if (($isGrep -and $word -match '^--regexp=') -or ($isSls -and $lower -match '^-pattern:')) {
                $indexes.Add($i); $patternSeen = $true; continue
            }
            if ($isGrep -and $word -cin @("-f", "--file")) { $patternSeen = $true; $i++; continue }
            if (Test-ValueOption $Command $valueOptions $(if ($isGrep) { $word } else { $lower })) { $i++; continue }
            if ($word.StartsWith("-")) { continue }
        }
        if (-not $patternSeen) { $indexes.Add($i); $patternSeen = $true }
    }
    return @($indexes)
}

function Test-ShellProtectedData([string[]]$Parts, [string]$ProjectRoot) {
    foreach ($part in $Parts) {
        $words = @(Split-ShellWords $part)
        if ($words.Count -eq 0) { continue }
        $command = Get-CommandName $words
        $arguments = @($words | Select-Object -Skip 1)
        $patterns = @(Get-PatternIndexes $command $arguments)
        $files = @(for ($i = 0; $i -lt $arguments.Count; $i++) { if ($patterns -notcontains $i) { $arguments[$i] } })
        $candidates = if ($command -in @("source", ".")) { @(Get-PathWords $arguments) }
            else { @(Get-PathWords (@($words[0]) + $files)) }
        foreach ($word in $candidates) {
            if (Test-ProtectedPath (ConvertTo-GuardPath $word $ProjectRoot)) { return $true }
        }
        if (Test-RootSearch $command $arguments $ProjectRoot) { return $true }
    }
    return $false
}

function Test-ProtectedData($Call, [string]$ProjectRoot) {
    foreach ($path in $Call.Paths) {
        if (Test-ProtectedPath (ConvertTo-GuardPath $path $ProjectRoot)) { return $true }
    }
    if ($Call.Kind -eq "shell") {
        return Test-ShellProtectedData @(Get-ShellParts $Call.Command) $ProjectRoot
    }
    return $false
}

# --- G2 ---------------------------------------------------------------------------------

$script:TestServices = @("backend-test", "frontend-test", "backend-e2e", "e2e")
# Compose subcommands that start, enter or show an app service.
$script:ServiceCommands = @("up", "start", "restart", "run", "exec", "logs", "cp", "attach",
    "top", "create", "config", "port", "events", "watch", "pause", "unpause", "kill", "rm")
# Plain docker subcommands that reach a container's files, environment or output.
$script:ContainerCommands = @("run", "exec", "cp", "logs", "inspect", "attach", "container",
    "commit", "export", "diff", "top", "stats", "debug")
$script:ComposeGlobalValues = @("-p", "--project-name", "-f", "--file", "--profile", "--env-file",
    "--project-directory", "--ansi", "--progress", "--parallel")
$script:SubcommandValues = @("-e", "--env", "-v", "--volume", "-w", "--workdir", "-u", "--user",
    "--name", "--entrypoint", "-l", "--label", "--index", "--tail", "--since", "--until",
    "--scale", "-t", "--timeout", "--wait-timeout", "--pull", "--env-from-file", "--cap-add",
    "--cap-drop", "--format")
# Subcommands whose first service name is followed by a command, not by more services.
$script:OneServiceCommands = @("run", "exec")
# Setting COMPOSE_FILE points Compose at another service definition (AC30).
$script:ComposeFileSetting = '(?i)(^|[^A-Za-z0-9_])COMPOSE_FILE\s*=|env:COMPOSE_FILE([^A-Za-z0-9_]|$)'
$script:AppUrl = '(?i)(127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\]|host\.docker\.internal):(8000|5173)(?!\d)'

# Returns @{ Globals; Subcommand; Arguments } for a `docker compose` or `docker-compose` part,
# or $null for any other part. Globals are the words before the subcommand.
function Get-ComposeCall([string[]]$Words) {
    $command = Get-CommandName $Words
    $start = -1
    if ($command -eq "docker-compose") { $start = 1 }
    elseif ($command -eq "docker" -and $Words.Count -gt 1 -and $Words[1] -eq "compose") { $start = 2 }
    if ($start -lt 0) { return $null }
    for ($i = $start; $i -lt $Words.Count; $i++) {
        $word = $Words[$i]
        if ($script:ComposeGlobalValues -contains $word) { $i++; continue }
        if ($word.StartsWith("-")) { continue }
        return @{ Globals = @($Words | Select-Object -Skip $start -First ($i - $start)); Subcommand = $word
            Arguments = @($Words | Select-Object -Skip ($i + 1)) }
    }
    return @{ Globals = @($Words | Select-Object -Skip $start); Subcommand = ""; Arguments = @() }
}

# A compose file or project folder other than this project's `compose.yaml` (AC30).
function Test-OtherComposeFile([string[]]$Globals) {
    return [bool]($Globals | Where-Object { $_ -cin @("-f", "--file", "--project-directory") -or
        $_ -match '^(--file|--project-directory)=' -or $_ -cmatch '^-f.' })
}

# An extra mount for `run` or `create`, given before the service name (AC30).
function Test-ExtraMount([string]$Subcommand, [string[]]$Arguments) {
    if ($Subcommand -notin @("run", "create")) { return $false }
    for ($i = 0; $i -lt $Arguments.Count; $i++) {
        $word = $Arguments[$i]
        if ($word -cin @("-v", "--volume", "--mount") -or $word -match '^(--volume|--mount)=' -or
                $word -cmatch '^-v.') {
            return $true
        }
        if ($script:SubcommandValues -contains $word) { $i++; continue }
        if (-not $word.StartsWith("-")) { return $false }
    }
    return $false
}

# The services a compose subcommand names. `cp` names them as `service:path`.
function Get-ComposeServices([string]$Subcommand, [string[]]$Arguments) {
    $services = New-Object System.Collections.Generic.List[string]
    for ($i = 0; $i -lt $Arguments.Count; $i++) {
        $word = $Arguments[$i]
        if ($script:SubcommandValues -contains $word) { $i++; continue }
        if ($word.StartsWith("-")) { continue }
        if ($Subcommand -eq "cp") {
            if ($word -match '^([A-Za-z0-9_.-]+):') { $services.Add($Matches[1]) }
            continue
        }
        $services.Add($word)
        if ($script:OneServiceCommands -contains $Subcommand) { break }
    }
    return @($services)
}

function Test-AppServiceCall([string[]]$Words) {
    $compose = Get-ComposeCall $Words
    if ($null -ne $compose) {
        # The test project is no exemption (AC29): its app services read .env and mount the real
        # import folders unless the container tests script passes its own settings file.
        if (Test-OtherComposeFile $compose.Globals) { return $true }
        if (Test-ExtraMount $compose.Subcommand $compose.Arguments) { return $true }
        if ($script:ServiceCommands -notcontains $compose.Subcommand) { return $false }
        if ($compose.Subcommand -eq "config" -and
                ($compose.Arguments -contains "--services" -or $compose.Arguments -contains "--profiles")) {
            return $false
        }
        $services = @(Get-ComposeServices $compose.Subcommand $compose.Arguments)
        if ($compose.Subcommand -eq "config" -or $services.Count -eq 0) { return $true }
        foreach ($service in $services) {
            if ($script:TestServices -notcontains $service) { return $true }
        }
        return $false
    }
    $command = Get-CommandName $Words
    if ($command -eq "docker" -and $Words.Count -gt 1) {
        return $script:ContainerCommands -contains $Words[1].ToLowerInvariant()
    }
    return $false
}

function Test-AppService($Call) {
    foreach ($url in $Call.Urls) {
        if ($url -match $script:AppUrl) { return $true }
    }
    if ($Call.Kind -ne "shell") { return $false }
    if ($Call.Command -match $script:AppUrl) { return $true }
    if ($Call.Command -match $script:ComposeFileSetting) { return $true }
    foreach ($part in @(Get-ShellParts $Call.Command)) {
        if (Test-AppServiceCall @(Split-ShellWords $part)) { return $true }
    }
    return $false
}

# --- G3 ---------------------------------------------------------------------------------

$script:GitGlobalValues = @("-C", "-c", "--git-dir", "--work-tree", "--namespace")
$script:DeleteCommands = @("remove-item", "ri", "del", "erase", "rm", "rmdir", "rd")

function Get-GitCall([string[]]$Words) {
    if ((Get-CommandName $Words) -ne "git") { return $null }
    for ($i = 1; $i -lt $Words.Count; $i++) {
        $word = $Words[$i]
        if ($script:GitGlobalValues -contains $word) { $i++; continue }
        if ($word.StartsWith("-")) { continue }
        return @{ Subcommand = $word.ToLowerInvariant(); Arguments = @($Words | Select-Object -Skip ($i + 1)) }
    }
    return $null
}

function Test-HardGitCall($Git) {
    $a = $Git.Arguments
    switch ($Git.Subcommand) {
        { $_ -in @("push", "clean", "rebase", "filter-branch", "filter-repo") } { return $true }
        "reset" { return $a -contains "--hard" }
        # `.`, `-f` and `--force` throw away uncommitted changes as `--` does (AC32).
        "checkout" { return [bool]($a | Where-Object { $_ -in @("--", ".", "--force") -or $_ -ceq "-f" }) }
        "switch" { return [bool]($a | Where-Object { $_ -in @("--force", "--discard-changes") -or $_ -ceq "-f" }) }
        "stash" { return $a.Count -gt 0 -and $a[0] -in @("drop", "clear") }
        "rm" { return [bool]($a | Where-Object { $_ -eq "--force" -or $_ -cmatch '^-[a-zA-Z]*f[a-zA-Z]*$' }) }
        "restore" { return -not ($a -contains "--staged") -or ($a -contains "--worktree") -or ($a -contains "-W") }
        "branch" { return [bool]($a | Where-Object { $_ -ceq "-D" -or $_ -eq "--force" }) }
        "commit" { return $a -contains "--amend" }
        "remote" { return [bool]($a | Where-Object { $_ -in @("add", "remove", "rm", "rename", "set-url") }) }
        "update-ref" { return $a -contains "-d" }
        "reflog" { return [bool]($a | Where-Object { $_ -in @("expire", "delete") }) }
    }
    return $false
}

function Test-DeletionCall([string[]]$Words) {
    $command = Get-CommandName $Words
    $arguments = @($Words | Select-Object -Skip 1)
    if ([bool]($Words | Where-Object { $_ -match '(?i)restore-db\.ps1' })) { return $true }
    $compose = Get-ComposeCall $Words
    if ($null -ne $compose) {
        return $compose.Subcommand -eq "down" -and
            [bool]($compose.Arguments | Where-Object { $_ -in @("-v", "--volumes") })
    }
    if ($command -eq "docker" -and $arguments.Count -ge 2) {
        $object = $arguments[0].ToLowerInvariant()
        $action = $arguments[1].ToLowerInvariant()
        if ($object -eq "volume" -and $action -in @("rm", "remove", "prune")) { return $true }
        if ($object -in @("system", "image", "builder") -and $action -eq "prune") { return $true }
    }
    $git = Get-GitCall $Words
    if ($null -ne $git) { return Test-HardGitCall $git }
    if ($script:DeleteCommands -contains $command) {
        foreach ($word in $arguments) {
            if ($word -match '^-[A-Za-z]+$' -and $word -cmatch '[rRf]' -and $word.Length -le 4) { return $true }
            if ($word -in @("--recursive", "--force")) { return $true }
            if ($word -match '^(?i)-rec') { return $true }
            if ($word -ieq "/s") { return $true }
        }
    }
    return $false
}

function Test-Deletion($Call) {
    if ($Call.Kind -ne "shell") { return $false }
    foreach ($part in @(Get-ShellParts $Call.Command)) {
        if (Test-DeletionCall @(Split-ShellWords $part)) { return $true }
    }
    return $false
}

# --- G4 ---------------------------------------------------------------------------------

$script:GuardFiles = @(".claude/settings.json", ".claude/settings.local.json", "scripts/guard-tests.ps1")
$script:GuardFolders = @(".claude/hooks", ".codex", ".agents/guardrails")
$script:ReadCommands = @("cat", "type", "get-content", "gc", "head", "tail", "less", "more",
    "select-string", "sls", "grep", "rg", "ls", "dir", "get-childitem", "gci", "wc", "test-path",
    "get-item", "get-filehash", "import-module", "test", "[")
$script:ReadGitCommands = @("diff", "log", "show", "status", "add", "blame", "ls-files")

function Test-GuardConfigPath([string]$Path) {
    $p = $Path.TrimEnd('/')
    foreach ($file in $script:GuardFiles) { if ($p -ieq $file) { return $true } }
    foreach ($folder in $script:GuardFolders) {
        if ($p -ieq $folder -or $p.StartsWith("$folder/", [StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

# A part that names guard config may only read it, list it, stage it or run a script in it.
function Test-ReadOnlyPart([string[]]$Words) {
    $command = Get-CommandName $Words
    if ($script:ReadCommands -contains $command) { return $true }
    $git = Get-GitCall $Words
    if ($null -ne $git) { return $script:ReadGitCommands -contains $git.Subcommand }
    if ($command -in @("powershell", "pwsh")) {
        return [bool]($Words | Where-Object { $_ -ieq "-file" })
    }
    return $false
}

function Test-GuardConfigWrite($Call, [string]$ProjectRoot) {
    if ($Call.Kind -eq "write") {
        foreach ($path in $Call.Paths) {
            if (Test-GuardConfigPath (ConvertTo-GuardPath $path $ProjectRoot)) { return $true }
        }
        return $false
    }
    if ($Call.Kind -ne "shell") { return $false }
    foreach ($part in @(Get-ShellParts $Call.Command)) {
        $split = Split-Redirections @(Split-ShellWords $part)
        foreach ($target in $split.Targets) {
            if (Test-GuardConfigPath (ConvertTo-GuardPath $target $ProjectRoot)) { return $true }
        }
        $words = @($split.Words)
        $named = $false
        foreach ($word in @(Get-PathWords $words)) {
            if (Test-GuardConfigPath (ConvertTo-GuardPath $word $ProjectRoot)) { $named = $true }
        }
        if ($named -and -not (Test-ReadOnlyPart $words)) { return $true }
    }
    return $false
}

# --- State ------------------------------------------------------------------------------

function New-GuardState {
    [pscustomobject]@{ editsSinceRun = @(); g5Count = 0; g6Path = ""; g6Count = 0
        lastRunRed = $false; lastGreen = [pscustomobject]@{}; stopReminded = $false; tripped = ""
        scanFrom = "" }
}

# Check runs: the Commands table of AGENTS.md and its documented variants. `full` is false
# for a run that covers only part of a check (named test files, a marker, extra arguments).
$script:CheckPatterns = [ordered]@{
    "backend-tests" = 'backend-test\s+pytest(?<rest>.*)$'
    "backend-lint" = 'backend-test\s+sh\s+-c\s+.*ruff check.*ruff format --check'
    "backend-types" = 'backend-test\s+pyright\s*$'
    "backend-audit" = 'backend-test\s+pip-audit'
    "frontend-tests" = 'frontend-test\s+npm\s+(test|run test:coverage)(?<rest>.*)$'
    "frontend-lint" = 'frontend-test\s+npm\s+run\s+lint\s*$'
    "frontend-format" = 'frontend-test\s+(npm\s+run\s+format:check\s*$|npx\s+prettier\s+--check\s.*--end-of-line\s+auto)'
    "frontend-types" = 'frontend-test\s+npm\s+run\s+typecheck\s*$'
    "e2e" = '--profile\s+e2e\s+run\s+--rm\s+e2e'
    "container-tests" = 'container-tests\.ps1'
    "guard-tests" = 'guard-tests\.ps1'
}

function Test-FullRest([string]$Rest) {
    $words = @(Split-ShellWords $Rest)
    for ($i = 0; $i -lt $words.Count; $i++) {
        if ($words[$i] -in @("-p", "--cov-report")) { $i++; continue }
        if ($words[$i].StartsWith("-") -and $words[$i] -notin @("-m", "-k", "--")) { continue }
        return $false
    }
    return $true
}

# Returns @{ Checks = names of the checks the command runs; Full = names it runs in full },
# or $null when the command runs no check.
function Get-CheckRun([string]$Command) {
    $checks = New-Object System.Collections.Generic.List[string]
    $full = New-Object System.Collections.Generic.List[string]
    $text = ($Command -replace '\s+', ' ').Trim()
    foreach ($name in $script:CheckPatterns.Keys) {
        if ($text -match $script:CheckPatterns[$name]) {
            $checks.Add($name)
            $isFull = $true
            if ($Matches.ContainsKey("rest")) { $isFull = Test-FullRest $Matches["rest"] }
            if ($isFull) { $full.Add($name) }
        }
    }
    if ($checks.Count -eq 0) { return $null }
    return @{ Checks = @($checks); Full = @($full) }
}

function Test-TestFile([string]$Path) {
    $p = $Path -replace '\\', '/'
    return $p -match '(?i)^backend/tests/' -or $p -match '(?i)^frontend/e2e/' -or
        $p -match '(?i)^frontend/src/.*\.test\.tsx?$'
}

# After a file edit. Returns @{ Decision; TestPaths }: a G7 reminder and the test files to
# record when the last check run was red.
function Update-GuardAfterEdit {
    param($State, [string[]]$Paths)
    $State.editsSinceRun = @($State.editsSinceRun) + @($Paths)
    $testPaths = @($Paths | Where-Object { Test-TestFile $_ })
    if ($State.lastRunRed -and $testPaths.Count -gt 0) {
        $reminder = New-Decision "Remind" "G7" ("a failing test may not be fixed by editing it; " +
            "change the test only if the spec says it is wrong.")
        return @{ Decision = $reminder; TestPaths = $testPaths }
    }
    return @{ Decision = $script:Allow; TestPaths = @() }
}

function Set-LastGreen($State, [string]$Check, [datetime]$Now) {
    $value = $Now.ToUniversalTime().ToString("o")
    if ($State.lastGreen.PSObject.Properties[$Check]) { $State.lastGreen.$Check = $value }
    else { $State.lastGreen | Add-Member -NotePropertyName $Check -NotePropertyValue $value }
}

# After a shell call. Only check runs change the counts (Plan P3). ChangedPaths are the files
# that shell commands changed since scanFrom, found by the hook through Git.
function Update-GuardAfterRun {
    param($State, [string]$Command, [bool]$ExitOk, [datetime]$Now, [string[]]$ChangedPaths = @())
    $run = Get-CheckRun $Command
    if ($null -eq $run) { return }
    $edits = @(@($State.editsSinceRun) + @($ChangedPaths) | Where-Object { $_ } |
        ForEach-Object { $_ -replace '\\', '/' } | Sort-Object -Unique)
    $State.editsSinceRun = @()
    $State.scanFrom = $Now.ToUniversalTime().ToString("o")
    if ($ExitOk) {
        $State.g5Count = 0; $State.g6Count = 0; $State.g6Path = ""; $State.lastRunRed = $false
        foreach ($check in $run.Full) { Set-LastGreen $State $check $Now }
        return
    }
    $State.lastRunRed = $true
    if (-not ($edits | Where-Object { Test-TestFile $_ })) { $State.g5Count++ }
    if ($edits.Count -eq 1) {
        if ($edits[0] -ieq $State.g6Path) { $State.g6Count++ }
        else { $State.g6Path = $edits[0]; $State.g6Count = 1 }
    } else {
        $State.g6Path = ""; $State.g6Count = 0
    }
    # G6 is the narrower finding, so it wins when both reach three on the same run.
    if ($State.g6Count -ge 3) { $State.tripped = "G6" }
    elseif ($State.g5Count -ge 3) { $State.tripped = "G5" }
}

function Set-GuardLastGreen($State, [string]$Check, [datetime]$At) { Set-LastGreen $State $Check $At }

# G8: the checks each part needs after a code change, with the command that runs each.
$script:PartChecks = [ordered]@{
    "backend" = [ordered]@{
        "backend-tests" = "docker compose run --rm backend-test pytest"
        "backend-lint" = 'docker compose run --rm backend-test sh -c "ruff check . && ruff format --check ."'
        "backend-types" = "docker compose run --rm backend-test pyright"
    }
    "frontend" = [ordered]@{
        "frontend-tests" = "docker compose run --rm frontend-test npm test"
        "frontend-lint" = "docker compose run --rm frontend-test npm run lint"
        "frontend-format" = "docker compose run --rm frontend-test npm run format:check"
        "frontend-types" = "docker compose run --rm frontend-test npm run typecheck"
    }
}

# At the end of a turn. `Changes` maps each part to the newest write time of its changed
# files, or $null. Refuses once when a part changed after one of its checks was last green.
function Get-GuardStopDecision {
    param($State, [hashtable]$Changes, [bool]$StopHookActive)
    if ($StopHookActive -or $State.stopReminded -or $State.tripped) { return $script:Allow }
    $missing = New-Object System.Collections.Generic.List[string]
    $parts = New-Object System.Collections.Generic.List[string]
    foreach ($part in $script:PartChecks.Keys) {
        $changed = $Changes[$part]
        if ($null -eq $changed) { continue }
        $partMissing = @()
        foreach ($check in $script:PartChecks[$part].Keys) {
            $green = $State.lastGreen.PSObject.Properties[$check]
            if ($null -eq $green -or [datetime]::Parse($green.Value, $null,
                    [Globalization.DateTimeStyles]::RoundtripKind) -lt $changed.ToUniversalTime()) {
                $partMissing += $script:PartChecks[$part][$check]
            }
        }
        if ($partMissing.Count -gt 0) { $parts.Add($part); $missing.AddRange([string[]]$partMissing) }
    }
    if ($missing.Count -eq 0) { return $script:Allow }
    $State.stopReminded = $true
    return New-Decision "Remind" "G8" ("run the $($parts -join ' and ') checks: " + ($missing -join "; ") + ".")
}

function Reset-GuardOnUserMessage {
    param($State, [datetime]$Now = [datetime]::UtcNow)
    $State.tripped = ""; $State.g5Count = 0; $State.g6Count = 0; $State.g6Path = ""
    $State.stopReminded = $false
    # Before the first check run, shell changes count from the session's first message.
    if (-not $State.scanFrom) { $State.scanFrom = $Now.ToUniversalTime().ToString("o") }
}

function Get-TrippedBlock($Call, $State, [string]$ProjectRoot) {
    if (-not $State.PSObject.Properties["tripped"] -or -not $State.tripped) { return $null }
    if ($Call.Kind -eq "read") { return $null }
    if ($State.tripped -eq "G6") {
        return New-Block "G6" "the same file changed in three red rounds in a row; wait for the user"
    }
    return New-Block "G5" "three red rounds in a row were reached; wait for the user"
}

# --- Decision ---------------------------------------------------------------------------

function Get-GuardDecision {
    param($Call, $State, [string]$ProjectRoot)
    if (Test-GuardConfigWrite $Call $ProjectRoot) {
        return New-Block "G4" "the call changes the guardrails' own configuration, which only the user changes"
    }
    if (Test-Deletion $Call) {
        return New-Block "G3" "the call deletes data or cannot easily be undone"
    }
    if (Test-ProtectedData $Call $ProjectRoot) {
        return New-Block "G1" "the call reaches protected data (.env, source/, database or key files)"
    }
    if (Test-AppService $Call) {
        return New-Block "G2" "the call reaches an app service or the running app, which hold real data; use the test services"
    }
    $tripped = Get-TrippedBlock $Call $State $ProjectRoot
    if ($null -ne $tripped) { return $tripped }
    return $script:Allow
}

Export-ModuleMember -Function New-GuardCall, New-GuardState, Get-GuardDecision, Format-GuardLine, `
    Get-CheckRun, Update-GuardAfterEdit, Update-GuardAfterRun, Reset-GuardOnUserMessage, `
    Set-GuardLastGreen, Get-GuardStopDecision, ConvertTo-GuardPath
