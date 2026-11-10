# 0006. Agent guardrails as hooks plus native rules, in one PowerShell guard

- Status: accepted
- Date: 2026-11-10

## Context

The user lets AI coding agents (Claude Code and Codex) work on their own from a spec's Tasks
approval to its audit. The guardrails of `AGENTS.md` were written rules only. Receipt data
must not leave this computer (NFR-1), and the model behind an agent is an external service,
so the agent must not read real data, the app's API or its logs, besides not changing or
deleting them. The [agent guardrails spec](../../specs/features/agent-guardrails.md) lists the
rules G1–G8.

The computer runs native Windows. Prerequisites are Docker Desktop, Git and Ollama (NFR-10).

The options were:

1. **Native rules only:** Claude Code deny rules and Codex permission profiles and command
   rules. They cover file tools and command prefixes, but not compound commands, PowerShell
   forms, or counters such as "three red rounds".
2. **Hooks plus native rules:** both tools call a hook before and after each tool call, at a
   user message and at the end of a turn. The hook can split commands, keep state and remind.
3. **A sandbox through WSL2 for Claude Code:** a file-system boundary for shell commands.
   Claude Code would have to run inside WSL2, which changes the repository location, Docker
   Desktop's integration, the PowerShell scripts, NFR-10 and [ADR 0002](0002-docker.md). It
   would not cover Docker either: a `docker` command asks the Docker service, which runs
   outside the sandbox.

## Decision

- Use **hooks plus native rules** (option 2) in both tools. The native rules stop the plain
  forms early; the hook is the layer that sees everything else.
- Write the guard **once**, in **Windows PowerShell 5.1**, the only scripting runtime that
  NFR-10 guarantees: rules as pure functions in `.agents/guardrails/Guard.psm1`, one adapter
  per tool, and one entry point `hook.ps1` that both tools call. Test it with plain PowerShell
  assertions (`scripts/guard-tests.ps1`), because Windows ships only Pester 3.4.
- In Codex, also use the **elevated Windows sandbox** with a permission profile, which needs
  no WSL2.
- Claude Code's PreToolUse hook **fails closed** (`onFailure: "block"`).
- The guard protects its own configuration (G4). Only the user changes it.
- Leave the WSL2 sandbox out for now (decided by the user on 2026-11-10).

## Consequences

- An allowed tool call costs about 0.4 s for the hook (measured 2026-11-10).
- Shell rules match command text. A command written to hide its target gets past them in
  Claude Code; only Codex's sandbox checks file access itself. Docker is outside every
  sandbox, so G2 is a text rule in both tools. The limits are listed in
  [security.md](../security.md#agent-guardrails).
- A Codex hook that fails lets the call run, and project hooks run only after the project
  is trusted and each hook is reviewed.
- Rules that read text block some harmless commands (false positives); the agent then stops
  and asks.
- A later ADR may add the WSL2 sandbox; it would turn G1 for shell commands into a file-system
  boundary.
