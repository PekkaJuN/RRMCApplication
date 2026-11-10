# Feature: Test container isolation

## Overview
- **Status:** Done
- **Created:** 2026-11-10
- **Updated:** 2026-11-10: Specify approved by the user; Plan added. The Plan found that AC4
  could not pass as written ([P6](#p6-spec-change-ac4)); the user approved the new wording
  and the Plan. Tasks added and approved by the user; implementation started. Audited
  (PASS), see [Audit](#audit).
- **Depends on:** [Project foundation](foundation.md)
- **Implements:** NFR-1, NFR-4 and NFR-12 for the development commands; a precondition for
  enforced agent guardrails and autonomous runs from Tasks to audit (next spec).
- **Affected subsystems:** none. Development tooling only: `compose.yaml`, the test commands
  and their docs. The app's behavior does not change.

## Problem Statement
The test, lint, type check and audit commands run in the `backend` and `frontend` services.
Those are the services of the running app, so the commands get the app's mounts and settings:

- A backend command gets the real import, done and failed folders, the real database volume
  `rrmc-data`, and every value in `.env`.
- The default `data_dir` is `/data` (@backend/app/settings.py). A test that builds settings
  without its own `data_dir` points at the real database `/data/db/rrmc.db`.
- Any command in the container can read real receipts, for example
  `docker compose run --rm backend ls /data/import`. A guardrail that blocks `source/` on the
  computer does not see this.
- The frontend commands also get every value in `.env`, although they need none of them.

A mistake in a test, or an agent running commands without a person watching, could read real
receipt data or change the real database. Agents are going to run the commands on their own,
from Tasks to audit. Before that, the commands must not be able to reach real data.

## Current Behavior
- The commands are listed in [development.md](../../docs/development.md#commands) and mirrored
  in [AGENTS.md](../../AGENTS.md#commands). They use `docker compose run --rm backend ...` and
  `docker compose run --rm frontend ...`.
- `backend` mounts `./backend`, the three folders from `RRMC_IMPORT_DIR`, `RRMC_DONE_DIR`
  and `RRMC_FAILED_DIR`, and `rrmc-data` at `/data/db`. `frontend` mounts `./frontend` and
  `rrmc-node-modules`. Both read `.env` (`env_file`, `required: true`).
- The E2E services `backend-e2e` and `e2e` are already isolated from real data: `/data` is a
  temporary filesystem, and the import and failed folders are test-only volumes
  ([E2E tests](../../docs/development.md#e2e-tests)). `backend-e2e` still reads `.env`.
- The container tests (@scripts/container-tests.ps1) use their own Compose project and
  settings files and never touch real data.
- Backend tests clear `RRMC_*` with the `clean_env` fixture where settings matter
  (@backend/tests/conftest.py). Other tests get whatever Compose set.

## Proposed Change

### Concepts
- **Real data:** the folders named by `RRMC_IMPORT_DIR`, `RRMC_DONE_DIR`, `RRMC_FAILED_DIR`
  and `RRMC_EVAL_DIR`, the whole `source/` folder, and the volume `rrmc-data`.
- **Check commands:** every command in the Commands table except the container tests, plus
  the useful variants listed under it (coverage, `-m tesseract`, format in place,
  `npm audit`).
- **Test containers:** the containers the check commands run in.

### Parts
- **PC1 No real data in test containers.** No test container mounts real data. A test
  container's `/data` is an empty temporary filesystem, so the default `data_dir` points to
  an empty folder that is gone after the run.
- **PC2 No `.env` in test containers.** The check commands do not read `.env` and work when
  it does not exist. The backend test containers get `RRMC_ENGINES=fake`; every other setting
  takes its default.
- **PC3 Same code, same tools.** Test containers use the same images, mount the same source
  folder (`./backend` or `./frontend`) and the same `rrmc-node-modules` volume as today, so
  results, coverage and in-place formatting are unchanged.
- **PC4 New commands.** The Commands table and the useful variants use the test containers.
  The commands stay copy-pasteable from the project root in PowerShell.
- **PC5 Refuse unsafe backend runs.** When pytest starts in a container where `rrmc-data` or a
  real data folder is mounted, it stops before running any test and prints one line that names
  the safe command. This stops the old command, used from memory or old notes, from running
  next to real data.
- **PC6 E2E without `.env`.** `backend-e2e` stops reading `.env`, so the E2E command also
  works without it (PC2). Its other behavior is unchanged.
- **PC7 Container test.** @scripts/container-tests.ps1 checks PC1, PC2 and PC6 from the Compose
  configuration, so a later change to `compose.yaml` that mounts real data fails a test.

### Out of Scope
- The running app (`docker compose up`) and the `eval` profile. They need real data by design.
- Permission deny rules, hooks and the autonomy rule: the next spec (agent guardrails).
- Running several worktrees at the same time.
- Any change to app code, the database schema or the API.

## Acceptance Criteria

### AC1: Backend test containers mount no real data
**Given** `compose.yaml`
**When** the configuration of every backend test container is read with
`docker compose config --format json`
**Then** none of its mounts has a source under `source/`, a source equal to a value of
`RRMC_IMPORT_DIR`, `RRMC_DONE_DIR`, `RRMC_FAILED_DIR` or `RRMC_EVAL_DIR`, or the volume
`rrmc-data`; and `/data` is a `tmpfs`.

### AC2: Frontend test containers mount no real data
**Given** `compose.yaml`
**When** the configuration of every frontend test container is read the same way
**Then** its only mounts are `./frontend` at `/app` and `rrmc-node-modules` at
`/app/node_modules`.

### AC3: The backend's default data folder is empty in a test container
**Given** the real database exists in `rrmc-data` and real images are in `source/import`
**When** `python -c "from pathlib import Path; print(sorted(p.name for p in Path('/data').rglob('*')))"`
runs in a backend test container
**Then** it prints `[]`, and `rrmc-data` and `source/import` are unchanged afterwards.

### AC4: Check commands work without a settings file
**Given** `RRMC_ENV_FILE` names a file that does not exist
**When** a backend and a frontend test container are started with `docker compose run --rm`
**Then** both start and run their command, and AC5 holds (no settings file values reach them).

### AC5: Backend test containers use the fakes
**Given** a backend test container
**When** its environment is read from `docker compose config`
**Then** `RRMC_ENGINES` is `fake`, and no other `RRMC_*` variable is set.

### AC6: The check commands pass
**Given** the code of `main` at the time of implementation
**When** each command of the new Commands table is run once
**Then** each one exits with code 0, and backend tests, frontend tests and E2E report the same
number of passed tests as the old commands did on the same code.

### AC7: Old backend command refuses to run tests
**Given** the app service `backend`, which mounts `rrmc-data`
**When** `docker compose run --rm backend pytest` is run
**Then** pytest exits with a non-zero code before any test runs, and prints exactly one line
naming the safe backend test command from the Commands table. No test result is printed.

### AC8: The refusal does not stop isolated runs
**Given** a backend test container
**When** pytest runs
**Then** the refusal of AC7 does not trigger, and the tests run.

### AC9: The refusal names no receipt content
**Given** a real data folder holds files
**When** the refusal of AC7 prints its line
**Then** the line contains no file names and no paths under `/data` other than the mount
point it found (for example `/data/db`).

### AC10: E2E keeps its behavior
**Given** the E2E services without `.env`
**When** the E2E command runs
**Then** every journey passes as before, `backend-e2e` reports `RRMC_ENGINES=fake`, and its
`/data` is still a temporary filesystem with the test-only import and failed volumes.

### AC11: Container tests guard the isolation
**Given** `compose.yaml` changed so that a backend test container mounts `./source/import`
**When** @scripts/container-tests.ps1 runs
**Then** it prints `FAIL` for the isolation check and exits with code 1. With the real
`compose.yaml` it prints `PASS` for AC1, AC2, AC4 and AC5 checks.

### AC12: Docs list only the safe commands
**Given** `docs/development.md`, `AGENTS.md`, `docs/security.md` and
`docs/subsystems/ui/README.md`
**When** they are searched for `compose run --rm backend` and `compose run --rm frontend`
**Then** no match is a check command. Matches that remain are about the running app and say so.

## Files to Modify
| File | Change |
|---|---|
| `compose.yaml` | Test containers for the backend and the frontend (PC1–PC3); `backend-e2e` without `.env` (PC6) |
| `backend/tests/conftest.py` | The refusal when real data is mounted (PC5) |
| `backend/tests/data_guard.py` | New: mount table check and refusal line (PC5, Plan P3) |
| `backend/tests/unit/test_data_guard.py` | New: unit tests of the check (AC7–AC9) |
| `scripts/container-tests.ps1` | Isolation checks from the Compose configuration (PC7) |
| `docs/development.md` | New Commands table and variants; a section on the test containers and why they exist |
| `AGENTS.md` | Commands table mirrored from `development.md` |
| `docs/security.md` | Test containers do not reach real data; dependency audit commands |
| `docs/subsystems/ui/README.md` | Check commands it names |
| `docs/architecture.md` | Compose services, if it lists them (checked in Plan) |
| `docs/content-plan.md` | Gap note for this spec |
| `specs/README.md` | Row 17 for this spec |

## Risk
- **What could break:** a test that relied on a `.env` value or on the mounted folders fails
  in the test container. A command copied from an old note now refuses to run (AC7), which
  is intended. A Compose mistake could mount real data again; AC11 catches it.
- **Rollback:** revert the change. The app services, the database and the data folders are
  not changed, so nothing needs restoring.
- **Dependencies:** Docker Compose only. No new packages.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC7 | refusal check in `conftest.py` | real data mounted | a fake mount table listing `/data/db` | the check runs | it stops the session with one line naming the safe command | mount table read through a function the test replaces |
| AC7 | refusal check | import folder mounted | a fake mount table listing `/data/import` | the check runs | it stops with the same one line | same |
| AC8 | refusal check | isolated | a fake mount table with `/data` as `tmpfs` only | the check runs | it does not stop | same |
| AC9 | refusal check | message content | a fake mount table listing `/data/db` and file names in the folder | the check runs | the line names `/data/db` and no file name | same |

### Integration tests
Run by @scripts/container-tests.ps1 against the Compose configuration, with its own settings
files; the real `.env` is never read or changed.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | backend test container mounts | `docker compose config --format json` | no real data source, `/data` is `tmpfs` | PASS |
| AC2 | frontend test container mounts | same | only `./frontend` and `rrmc-node-modules` | PASS |
| AC3 | default data folder | the `python -c` command of AC3 in a backend test container | `[]` | PASS |
| AC4 | no settings file | `run --rm backend-test python -c "print('ok')"` and `run --rm frontend-test node -e "console.log('ok')"` with `RRMC_ENV_FILE` pointing to a missing file | both print `ok` | PASS |
| AC5 | environment | `docker compose config --format json` | `RRMC_ENGINES=fake`, no other `RRMC_*` | PASS |
| AC7 | old command | `docker compose -p rrmc-test run --rm backend pytest` with the test project's settings | non-zero exit, one line with the safe command | PASS |
| AC11 | broken configuration | a copy of `compose.yaml` that mounts `./source/import` in the backend test container | the isolation check reports `FAIL` | PASS |

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC10 | all existing journeys | the new E2E command without `.env` | all pass |

### Manual checks
| AC | Check | Expected outcome |
|---|---|---|
| AC6 | run every command of the new Commands table once | each exits 0; test counts equal the old commands' counts |
| AC12 | search the listed docs for the old commands | no check command remains |

### Coverage target
- Backend: the refusal check has every branch tested. Overall backend coverage does not drop.
- Frontend: unchanged.

### Test data
- Synthetic only. The container tests use their own folders under `%TEMP%` and their own
  Compose project `rrmc-test`, as today. No test reads `source/`, `rrmc-data` or `.env`.
- Mocks: the mount table read by the refusal check.

## Related Documentation (MANDATORY)
- Tier 1: [development.md](../../docs/development.md#commands),
  [security.md](../../docs/security.md), [architecture.md](../../docs/architecture.md),
  [AGENTS.md](../../AGENTS.md#guardrails)
- Tier 2: [ui](../../docs/subsystems/ui/README.md) (names check commands)
- ADRs: [0002 Docker](../../docs/adr/0002-docker.md)

<!-- The Plan phase appends "## Plan" and the Tasks phase appends "## Tasks" below. -->

## Plan

### Findings that shape the plan
Checked on 2026-11-10 with Docker Compose on this computer, without `.env`:

- `docker compose run --rm <service>` loads only the target service's `env_file`. A service
  without `env_file` starts when `RRMC_ENV_FILE` names a missing file, and gets only the
  variables in its `environment` (a probe service printed `['RRMC_ENGINES']`).
- `docker compose config <service>` loads every service's `env_file`, so it fails when any
  of them is missing, even for a service that has none. `config --services` does not.
- `docker compose config --format json` merges `env_file` into `environment` and drops the
  key. A test container's resolved `environment` therefore shows whether it reads a settings
  file.
- In a container with `--tmpfs /data`, `/proc/self/mounts` lists `/data` as `tmpfs` and
  nothing under it. In the app's `backend` container, `rrmc-data` is a mount at `/data/db`
  and the folders are mounts at `/data/import`, `/data/import_done` and `/data/import_failed`.
- `pytest.exit(message, returncode=2)` called in `pytest_configure` prints one line,
  `Exit: <message>`, runs no test and exits with code 2.

### P1 Test services in `compose.yaml` (PC1–PC3)
Two services in a new profile `test`. `docker compose run` starts a service of a profile
without `--profile`, and `docker compose up` leaves it out.

| Service | Image | Mounts | Environment | Other |
|---|---|---|---|---|
| `backend-test` | `build: ./backend`, `image: rrmc-backend` | `./backend:/app` | `RRMC_ENGINES: fake` | `tmpfs: /data`; no `env_file`, ports or `extra_hosts` |
| `frontend-test` | `build: ./frontend`, `image: rrmc-frontend` | `./frontend:/app`, `rrmc-node-modules:/app/node_modules` | none | no `env_file` or ports |

- `image:` names the image Compose already gives `backend` and `frontend`. The test services
  use the same image, so `docker compose build backend` after a lock file change also updates
  the tests ([Dependencies](../../docs/development.md#dependencies-and-lock-files)), and no
  second image is built.
- No `extra_hosts`: the test containers cannot reach Ollama on Windows. Tests use the fakes.
- The default network stays, because `pip-audit` and `npm audit` need the internet. They send
  only package names and versions.

### P2 `backend-e2e` without `.env` (PC6)
Remove its `env_file`. `RRMC_ENGINES: fake` stays. Every other setting takes its default.
The E2E UI reaches the backend through the Vite proxy, so `RRMC_UI_PORT` (CORS) does not
matter. The host check allows the service name `backend-e2e`.

### P3 Refusal in pytest (PC5)
- New module @backend/tests/data_guard.py with two pure functions:
  - `find_real_data_mount(mounts: str) -> str | None` parses `/proc/self/mounts` text. It
    returns the first mount point that is under `/data/`, or `/data` itself unless that is
    `tmpfs`. It decodes the octal escapes of the file (`\040` is a space).
  - `refusal_line(mount_point: str) -> str` returns
    `Refusing to run tests: real data may be mounted at <mount point>. Use: docker compose run --rm backend-test pytest`.
    It names only the mount point (AC9).
- @backend/tests/conftest.py adds `pytest_configure`. It reads `/proc/self/mounts` (it is
  missing outside Linux, which means no check) and calls `pytest.exit(line, returncode=2)`
  on a hit. `tests/conftest.py` is loaded for every run under `tests/`, so a single test file
  cannot bypass it.
- Rule: any mount under `/data` counts, not only the names in AC7. An allow rule would have
  to be kept in sync with `compose.yaml`; a deny-all rule under `/data` does not.

### P4 Container tests (PC7)
@scripts/container-tests.ps1 gets one function and these checks. They use the existing
project `rrmc-test` and its settings files, so the real `.env` and data are never read.

- `Get-IsolationProblems($config, $service, $allowedMounts, $expectTmpfs, $allowedEnv)`
  returns a list of problems for one service of `docker compose config --format json`:
  a mount not in the allow list, a missing `tmpfs` at `/data`, or an environment variable
  other than the allowed ones. An allow list is stricter than AC1's deny list and satisfies it.
- AC1, AC2, AC5: no problems for `backend-test`, `frontend-test` and `backend-e2e` (for
  `backend-e2e`: its two test volumes and `./backend` are allowed).
- AC4: `run --rm backend-test python -c "print('ok')"` and
  `run --rm frontend-test node -e "console.log('ok')"` with `RRMC_ENV_FILE` set to a missing
  file print `ok`.
- AC3: with a file in the test project's import folder and the test volume holding the
  database from AC11's earlier check, the AC3 command in `backend-test` prints `[]`.
- AC7: `run --rm backend pytest` in `rrmc-test` (its `backend` mounts the test volume at
  `/data/db`) exits 2 and prints the refusal line.
- AC11: the function finds a problem when the configuration comes from `compose.yaml` plus an
  override file in `%TEMP%\rrmc-container-tests` that mounts the test import folder in
  `backend-test`. The check prints `PASS` when the problem is found.

### P5 Commands and docs (PC4)
New Commands table (development.md first, AGENTS.md mirrors it):

| Task | Command |
|---|---|
| Backend tests | `docker compose run --rm backend-test pytest` |
| Backend lint and format check | `docker compose run --rm backend-test sh -c "ruff check . && ruff format --check ."` |
| Backend type check | `docker compose run --rm backend-test pyright` |
| Backend dependency audit | `docker compose run --rm backend-test pip-audit` |
| Frontend tests | `docker compose run --rm frontend-test npm test` |
| Frontend lint | `docker compose run --rm frontend-test npm run lint` |
| Frontend format check | `docker compose run --rm frontend-test npm run format:check` |
| Frontend type check | `docker compose run --rm frontend-test npm run typecheck` |
| E2E tests | `docker compose --profile e2e run --rm e2e` (unchanged) |
| Container tests | unchanged |

The useful variants, `npm audit` in security.md, and the `npm ci` / `npm install` dependency
commands move to `frontend-test` too. They then need no `.env` either. development.md gets a
short section "Test containers": why they exist, what they do not mount, and the refusal.
architecture.md line on `compose.yaml` names the `test` profile. learnings.md keeps its old
commands: entries are history.

### P6 Spec change: AC4
AC4 first said `docker compose config` resolves each test container without a settings file.
The first finding shows that `config` loads every service's `env_file`, so it could not pass
while `backend`, `frontend` and `eval` need `.env`, and they must (out of scope). Also, the
agent may not remove `.env` to set up "a checkout where `.env` does not exist". AC4 now starts
the test containers with `run` and a missing `RRMC_ENV_FILE` instead (approved 2026-11-10).
Its integration row uses the two `run` commands of P4.

### Files to Modify (refined)
[Files to Modify](#files-to-modify) now lists @backend/tests/data_guard.py and
@backend/tests/unit/test_data_guard.py. `docs/learnings.md` keeps its old commands.

### Data flow and data model
No change. No dependency is added. No ADR: this extends [ADR 0002](../../docs/adr/0002-docker.md)
without changing its decision.

### AC check
| AC | Covered by |
|---|---|
| AC1, AC2, AC5 | P1, P2; P4 `Get-IsolationProblems` |
| AC3 | P1 `tmpfs`; P4 |
| AC4 | P1 (no `env_file`); P4 `run` checks; wording per P6 |
| AC6 | P5; manual run of every command. Baseline: the old commands' counts, taken once before P3 lands |
| AC7, AC8, AC9 | P3; unit tests; P4 AC7 check; every normal run proves AC8 |
| AC10 | P2; E2E run with `RRMC_ENV_FILE` set to a missing file |
| AC11 | P4 override check |
| AC12 | P5; search of the listed docs |

## Tasks

Each task: Red, then Green, then Refactor; tick it only when its tests pass. Commands that
run in a container never read `.env` directly; the container tests use `rrmc-test` and their
own settings files.

- [x] **T1 Baseline (AC6).** Before any change, run the old backend, frontend and E2E test
  commands once and record the passed, failed, skipped and deselected counts in the spec's
  progress notes. No other output is recorded.
- [x] **T2 Test services (AC1, AC2, AC5).** Red: add `Get-IsolationProblems` and the AC1,
  AC2 and AC5 checks to @scripts/container-tests.ps1; run it and see them fail because the
  services do not exist. Green: add `backend-test` and `frontend-test` to `compose.yaml`
  (P1). From here on, every test run uses the test services.
- [x] **T3 Refusal check, unit level (AC7, AC8, AC9).** In
  @backend/tests/unit/test_data_guard.py, write the four unit rows of the Testing Strategy one
  at a time, plus cases for an escaped mount point (`\040`) and for `/data` that is not
  `tmpfs`. Implement `find_real_data_mount` and `refusal_line` in @backend/tests/data_guard.py.
- [x] **T4 `backend-e2e` without `.env` (AC5, AC10).** Red: the `backend-e2e` check of P4
  fails because the settings file values reach it. Green: remove its `env_file` (P2).
- [x] **T5 No settings file (AC4) and empty `/data` (AC3).** Add the P4 checks for AC4 and
  AC3; they should pass at once with T3's services. Confirm they fail for the right reason by
  running the AC3 check against `backend` in `rrmc-test` once (it lists the test database).
- [x] **T6 Refusal wired (AC7, AC8).** Red: add the P4 AC7 check; it fails because the old
  command runs the tests. Green: `pytest_configure` in @backend/tests/conftest.py (P3). Run
  the backend tests with `backend-test` to prove AC8.
- [x] **T7 Broken configuration is caught (AC11).** Add the override check of P4. Confirm it
  fails when `Get-IsolationProblems` is changed to ignore mounts, then restore it.
- [x] **T8 Commands pass (AC6, AC10).** Run every command of the new Commands table, the E2E
  command with `RRMC_ENV_FILE` set to a missing file, and the container tests. Compare the
  counts with T1 (backend: T1 plus the new `test_data_guard.py` tests).
- [x] **T9 Docs (AC12).** Update development.md (Commands, variants, dependency commands, new
  "Test containers" section), AGENTS.md, security.md, ui README, architecture.md,
  content-plan.md and `specs/README.md`. Search the listed docs as in AC12.
- [x] **T10 Checks and audit.** Backend tests, lint, format check and type check with the new
  commands; frontend checks only if a frontend file changed (none planned); container tests.
  Then the `review-audit` skill.

## Progress

- **T1 baseline (2026-11-10, old commands, `main` at 79248b4):** backend 1405 passed,
  4 deselected (`tesseract`), 0 failed, 0 skipped; frontend 341 passed in 29 files; E2E 40
  passed.
- **T8 (2026-11-10, new commands):** backend 1415 passed (T1 plus the 10 tests of
  `test_data_guard.py`), 4 deselected; frontend 341 passed in 29 files; E2E 40 passed with
  `RRMC_ENV_FILE` naming a missing file, and `backend-e2e` had only `RRMC_ENGINES=fake` and
  `/data` as `tmpfs`. Lint, type check and `pip-audit` pass. The frontend format check fails
  on the CRLF working tree, as with the old command; `prettier --check . --end-of-line auto`
  passes. Container tests pass.
- **T10 (2026-11-10):** the audit found one untested branch in `find_real_data_mount`
  (incomplete mount table lines); a test was added. Backend 1416 passed, 4 deselected;
  `tests/data_guard.py` 100 % lines and branches.

## Audit

### Summary
- Acceptance criteria: 12/12 met
- Tests: pass. Backend 1416 passed (T1 1405 plus 11 new), frontend 341, E2E 40, container
  tests all PASS. Coverage of `tests/data_guard.py` 100 % lines and branches; backend
  coverage of `app` unchanged (no app code changed).
- Security: 0 critical, 0 high, 1 medium (later)
- Docs updated: yes; spec status: Done

| AC | Result | Evidence |
|---|---|---|
| AC1, AC2, AC5 | ✅ | container tests `Isolation AC1 AC5`, `Isolation AC2 AC5` |
| AC3 | ✅ | `Isolation AC3`; the same listing in the app service finds 6 entries (T5) |
| AC4 | ✅ | `Isolation AC4` |
| AC6 | ✅ | T1 and T8 counts |
| AC7, AC8, AC9 | ✅ | `test_data_guard.py`; `Isolation AC7`; every `backend-test` run |
| AC10 | ✅ | `Isolation AC5 AC10`; E2E 40 passed with a missing `RRMC_ENV_FILE` |
| AC11 | ✅ | `Isolation AC11`; a mutant that ignores mounts misses the broken file (T7) |
| AC12 | ✅ | search of the five docs finds no old check command |

| # | Severity | File | Finding | Recommendation |
|---|---|---|---|---|
| 1 | Medium (later) | `backend/tests/conftest.py` | The refusal is a safety net, not a boundary: `pytest --noconftest`, or any command other than pytest in the app's `backend` service, still reaches real data. | Block those commands with deny rules and hooks in the agent guardrails spec. |
| 2 | Low (later) | `docs/development.md` | The frontend format check fails on the CRLF working tree, with the old and the new command alike. | Known (see the CRLF note); `prettier --check . --end-of-line auto` passes. Out of scope. |
| 3 | Info | process | T3 wrote its unit tests in one step instead of one at a time; all were seen failing on assertions before the code was written. | None. |

Verdict: PASS. Next: the agent guardrails spec (permission deny rules, hooks, autonomy rule).
