# Security

- **Status:** Done
- **Updated:** 2026-11-13

## Overview

Receipts are personal financial data. This document describes what data the app holds, how
it is protected, and what it does not protect against. The requirements are PRD
[NFR-1 to NFR-5](../specs/PRD.md#71-privacy-and-security). The working rules for developers
and agents are in [AGENTS.md](../AGENTS.md#privacy-and-security).

The app runs on one person's own computer. It protects receipt data from leaving that
computer. It does not protect data from someone who can already use the computer.

## Data the app holds

| Data | Where | Default location |
|---|---|---|
| Receipt images | Import, done, failed and archive folders on this computer | `source/import`, `source/import_done`, `source/import_failed`, `source/archived` |
| Receipts, lines, products, raw OCR text, archived receipts and lines | SQLite database | Docker volume `rrmc_rrmc-data` |
| Evaluation images and results | Evaluation folder (development tool) | `source/eval` |
| CSV and PDF exports | Wherever the browser saves them | The user's download folder |
| Logs | Standard output of the containers | Docker's log of each container |
| Settings | `.env` file | Project root |

The app does not encrypt any of this. Protection at rest comes from the computer: its user
account and disk encryption.

## Network

- **Ports:** Compose publishes the backend and the UI on `127.0.0.1` only (`compose.yaml`), so
  other computers cannot reach them. Inside their containers they listen on `0.0.0.0`,
  because Docker's port mapping needs that.
- **Outgoing:** the backend's only external call is to Ollama at `RRMC_OLLAMA_URL`, on this
  computer. The call carries OCR text and product names over plain HTTP between the container
  and Windows.
- **Cloud models:** Ollama runs with `OLLAMA_NO_CLOUD=1`
  ([setup](development.md#setup)). The backend also refuses a model name that Ollama would
  run in its cloud service (`is_cloud_model` in @backend/app/engines/model.py), both when
  loading it and when an import starts.
- **Browser:** the UI loads nothing from another host. CORS allows only
  `http://127.0.0.1:<RRMC_UI_PORT>` (@backend/app/main.py).
- **Host header:** the backend answers 400 `invalid_host` unless the name is `127.0.0.1`,
  `localhost` or a Compose service name (@backend/app/host_check.py). This stops DNS
  rebinding, where a malicious site points its own name at `127.0.0.1` to read the answers.
- **Login:** there is none, by design ([PRD non-goals](../specs/PRD.md#3-non-goals)).

## Input handling

| Input | Protection |
|---|---|
| Request bodies | Strict: unknown fields, `null` and wrong types give `invalid_request` ([API reference](api-reference.md)) |
| Ids | An id outside SQLite's integer range counts as not existing |
| SQL | Values are bound as parameters; all SQL is in the storage package |
| File names of failed images | Only a plain name directly in the failed folder is accepted: no paths, no links out of the folder (@backend/app/review/failed_images.py) |
| Image files | The file's signature must match a JPEG or PNG; the images are served with `Cache-Control: no-store` |
| Model output | Validated against a schema; invalid output is a failure, not stored data (FR-8) |
| CSV cells | User text that Excel could run as a formula gets a leading `'` (@backend/app/export/csv_exporter.py) |
| PDF files | Group and category names and sums only, no product or store names; names are escaped before layout; the metadata holds the title only, no author or user name (@backend/app/export/pdf_exporter.py) |

## Logs and errors

- A request logs its method, path, status and duration. The query string and the bodies are
  never logged (@backend/app/logging_setup.py). Uvicorn's own access log is off.
- Import errors log the error type and traceback frames, not the message, because a message
  can hold a file path (`log_without_message` in @backend/app/receipt_import/run.py).
- API errors return a fixed Finnish text and never the details of the exception.

See [known limits](#known-limits) for the one accepted exception.

## Version control

`.gitignore` keeps `.env`, `source/`, SQLite files and `service_account*.json` out of the
repository. Tests use synthetic receipts only (NFR-12). The test, lint, type check and audit
commands run in test containers that mount no receipt folder, no database volume and no
`.env`, and pytest refuses to run where anything is mounted under `/data`
([test containers](development.md#test-containers)). The app has no secrets today. The
Google Sheets export will need a service-account key, stored outside the repository and
outside cloud-synced folders (NFR-5).

## Dependencies

Check the backend and frontend dependencies for known vulnerabilities:

```powershell
docker compose run --rm backend-test pip-audit
docker compose run --rm frontend-test npm audit --omit=dev
```

Both reported no known vulnerabilities on 2026-11-04.

## Agent guardrails

AI coding agents (Claude Code, Codex) may work on their own from a spec's Tasks approval to
its audit ([AGENTS.md](../AGENTS.md#non-negotiable-sdd-and-tdd-rules)). The model behind an
agent is an external service, so anything the agent reads leaves this computer. The
guardrails therefore keep the agent away from real data, not only from changing it
([spec](../specs/features/agent-guardrails.md), [ADR 0006](adr/0006-agent-guardrails.md)).

| ID | Blocks | Does not stop |
|---|---|---|
| G1 | File tools and shell commands that name `.env` or `.env.<x>` (not `.env.example`), `source/`, SQLite files or `service_account*.json`; recursive searches from the project root | A path built at run time (variables, string joins, encodings); a program that opens the files itself |
| G2 | `docker compose` commands that start, enter, show the logs or configuration of, or copy from `backend`, `frontend` or `eval`, in any project, `rrmc-test` too (only the container tests script starts those); an extra mount for `run` or `create` (`-v`, `--volume`, `--mount`); another compose file or project folder (`-f`, `--file`, `--project-directory`, setting `COMPOSE_FILE`); plain `docker run`, `exec`, `cp`, `logs`, `inspect`; calls to ports `8000` and `5173` | Other ports set in `.env` (the guard cannot read it); a script file that runs such commands; `COMPOSE_FILE` inside a settings file |
| G3 | Volume removal and pruning, recursive or forced deletes, `restore-db.ps1`, `git push`, hard resets, `clean`, discarding changes (`checkout --`, `checkout .`, `checkout -f`, `restore`, `switch -f` and `--discard-changes`, `stash drop` and `clear`, `rm -f`), history rewrites, remote changes | Deletes through other programs or scripts |
| G4 | Writes to `.claude/settings.json`, `.claude/hooks/`, `.codex/`, `.agents/guardrails/`, `scripts/guard-tests.ps1` | Writes through a script file the guard cannot see into |
| G5 | Every call but reading files after three red check runs in a row, until the user writes | Failures of commands that are not in the Commands table |
| G6 | The same, when the edits between those runs touched one and the same file, through file tools or shell commands (shell changes are found through `git status` and write times at each check run) | Changes to files Git ignores; a change outside a Git repository |
| G7 | Nothing: a test edit after a red run gets a reminder and is recorded for the audit | Test edits made through shell commands (no reminder, not recorded) |
| G8 | Ending a turn once, when a changed part's checks were not green since the change | — |

Layers:

- **Claude Code:** deny rules for the file tools and the plainest commands; the hooks for every
  call. `.claude/` is also a protected path that the agent cannot write to without approval.
  A hook that fails blocks the call (`onFailure: "block"`).
- **Codex:** the elevated Windows sandbox with a permission profile that denies the G1 paths
  and makes the guard configuration read-only; command rules for the plain G2 and G3
  commands; the same hooks. A Codex hook that fails lets the call run.

Known limits of the guardrails:

- **Shell rules match text.** On native Windows, Claude Code runs shell commands without a
  sandbox, and both the deny rules and the hook read the command text. A command written to
  hide its target gets past them. Only Codex's sandbox checks file access itself.
- **Wrappers.** The hook drops prefix words (`&`, `NAME=value`, `env`, `command`, `sudo`,
  `nohup`, `time`) and checks the command given to another shell (`bash -c`, `sh -c`,
  `powershell -Command`, `pwsh -c`, `cmd /c`, `Invoke-Expression`) with every rule. It does not
  see a command in `-EncodedCommand`, in a variable, built at run time, passed through `xargs`
  or `Start-Process`, or written to a script file.
- **Docker is outside every sandbox.** A `docker` command asks the Docker service, which has
  full access. G2 is the only layer for it.
- **The hooks must be on.** Claude Code runs them after the workspace trust dialog; Codex
  after the project is trusted and each hook is reviewed.
- **Codex exit codes.** The Codex docs do not name the exit code field of a shell result. The
  guard reads `exit_code`, `exitCode` or an `Exit code: N` line; otherwise Codex check runs do
  not count for G5, G6 and G8.
- **False positives.** A search pattern (`grep`, `rg`, `Select-String`) and a redirection
  to a stream, a null device or another file are not read as a path. A guard path in the
  text of any command that is not a read, such as a heredoc body, still counts as a write
  (G4), so that a script given on the command line cannot write guard config; edit such
  files with the file tools. The agent stops and asks; the user may run the command.
- **Not covered:** a WSL2 sandbox for Claude Code (left out on 2026-11-10; see the ADR).

## Known limits

Each limit was checked against the running code on 2026-11-04.

- **Anything on this computer can call the API.** There is no login, so any program running
  on the computer can read and change the data.
- **CORS does not stop every request.** It stops another site from reading answers, and it
  refuses the preflight of JSON, `PATCH` and `DELETE` requests. A request without a preflight
  still reaches the backend: a page on any site can start an import with `POST /api/import`.
  It cannot read the result, and it can only start what the button in the UI starts.
- **An unexpected error logs its message.** `_handle_unexpected_error` in
  @backend/app/errors.py logs the full exception, unlike the import errors above. The API
  answer stays clean, but a message that holds receipt content or a file name would reach
  the log. The message helps to find the cause, so the user accepted this exception to
  NFR-3 on 2026-11-04. The log stays on this computer.

## Related Documents

- [PRD](../specs/PRD.md): NFR-1 to NFR-5
- [Architecture](architecture.md): runtime and deployment, cross-cutting rules
- [API reference](api-reference.md): error format and request rules
- [Development guide](development.md): setup and commands
- [AGENTS.md](../AGENTS.md): guardrails, privacy and security rules
- [Content plan](content-plan.md): documentation index
