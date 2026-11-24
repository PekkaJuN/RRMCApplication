# Feature: Run container

## Overview
- **Status:** Done
- **Created:** 2026-11-24
- **Updated:** 2026-11-24: Specify approved by the user; Plan added
  ([P10](#p10-spec-changes) refines Files to Modify). The user moved the run environment's
  default folders to `C:\MyApps\RRMCApplication` (PC3, PC6, AC9, AC23 changed).
  Plan approved by the user; ADR 0008 accepted; Tasks added.
  Tasks approved by the user; T0 (guard port 8080) done by the user.
- **Depends on:** [Project foundation](foundation.md), [Test container isolation](test-isolation.md),
  [Agent guardrails](agent-guardrails.md)
- **Implements:** NFR-11 (changed), NFR-1, NFR-2, NFR-4 for the run environment
- **Affected subsystems:** [ui](../../docs/subsystems/ui/README.md) (built UI served by the
  backend), [storage](../../docs/subsystems/storage/README.md) (a second database volume).
  Runtime and tooling: a new Compose file, a new image, scripts and their docs. The app's
  features, the API and the database schema do not change.

## Problem Statement
The app has one way of running ([ADR 0002](../../docs/adr/0002-docker.md)): the development
containers. Normal use and development share everything:

- The UI comes from the Vite dev server and the backend runs Uvicorn with `--reload`, both
  from the source folders. A half-finished change in `backend/` or `frontend/` is live in the
  app the family uses, and a broken edit stops it.
- The images hold every development tool (pytest, ruff, pyright, pip-audit, Node.js, the
  Playwright browsers).
- Development and use share one database (`rrmc_rrmc-data`) and one set of receipt folders.
  Trying out a change, for example an import, changes the real data.

The user wants a separate run environment: an app built from a known version of the code,
without development tools, with its own database and its own receipt folders. The current
development data is copied into it once. After that, the run environment is updated with new
versions of the code, and its schema follows through the existing migrations. Data is never
copied again.

## Current Behavior
- `docker compose up` starts `backend` (FastAPI, Tesseract, `--reload`, source mounted) and
  `frontend` (Vite dev server) ([Running the app](../../docs/development.md#running-the-app),
  [Runtime and deployment](../../docs/architecture.md#runtime-and-deployment)).
- The backend serves only `/api/...`. A request to `/` answers 404.
- The UI uses client-side paths (`/tuonti`, `/kuitit/<id>`, `/arkisto/<year>`, ...;
  @frontend/src/navigation.ts). Vite answers every such path with `index.html`.
- The database is in the volume `rrmc_rrmc-data`; the receipt folders come from
  `RRMC_IMPORT_DIR`, `RRMC_DONE_DIR`, `RRMC_FAILED_DIR` and `RRMC_ARCHIVE_DIR` (defaults under
  `./source/`).
- `scripts/backup-db.ps1` and `scripts/restore-db.ps1` work on the development database only.
- `frontend/package.json` has no build script.

## Proposed Change

### Concepts
- **Development environment:** the Compose project `rrmc` from `compose.yaml`, unchanged.
- **Run environment:** a new Compose project `rrmc-app` from a new file `compose.app.yaml`,
  with one service `app`.
- **Run image:** the image of `app`, tagged `rrmc-app:<tag>`.
- **Run folder:** `C:\MyApps\RRMCApplication`, outside the repository. It holds the run
  environment's receipt folders and its database backups by default.
- **App data:** the run environment's receipt folders under `RRMC_APP_SOURCE_DIR`
  (default `C:\MyApps\RRMCApplication\source`; subfolders `import`, `import_done`,
  `import_failed`, `archived`) and its database volume named by `RRMC_APP_DB_VOLUME` (default
  `rrmc-app-data`). The database stays in a Docker volume ([ADR 0002](../../docs/adr/0002-docker.md)).
  The compose file, the scripts and the image are built and run from the repository.

### Parts
- **PC1 Run image without development tools.** The run image holds the backend code, the
  built UI, the runtime Python dependencies and Tesseract with `fin` and `eng`. It holds no
  test, lint, type check or audit tools, no Node.js and no npm. Nothing is mounted over the
  code, and Uvicorn runs without `--reload`. The app runs as a user other than root. The image
  holds no `.env`, no receipt data and no tests.
- **PC2 One container, one port.** `app` serves the UI and the API from one origin on
  `127.0.0.1:${RRMC_APP_PORT}` (default `8080`): the API under `/api/`, the UI's files, and
  `index.html` for every other path, so the UI's client-side paths work on reload. An unknown
  path under `/api/` still answers with the API's JSON 404.
- **PC3 Own data.** `app` mounts only the app data: the four folders under
  `RRMC_APP_SOURCE_DIR` and the volume `RRMC_APP_DB_VOLUME`. It never mounts the development
  folders, `rrmc_rrmc-data` or the source folders. It reads the other settings (model, Ollama
  address, log level) from `.env`, and always runs with `RRMC_ENGINES=real`. The settings
  check and migrations run at start, as in the development environment.
- **PC4 Development environment unchanged.** `compose.yaml`, `docker compose up`, the check
  commands and their results do not change. Without a built UI the backend answers `/` with
  404, as today.
- **PC5 One-time copy.** A new script `scripts/copy-to-app.ps1` copies the development data
  into empty app data: the database (through SQLite's backup API, checked with
  `PRAGMA integrity_check`) and every file of the four development folders. It never changes
  the development data. It refuses when the app database exists, when any app folder holds a
  file, or when `app` is running, so the copy happens once and never overwrites app data.
- **PC6 Backup and restore of the run environment.** `backup-db.ps1` and `restore-db.ps1` get
  a parameter `-Target dev|app` (default `dev`, today's behavior). With `app` they work on the
  run environment's database and service, backup files are named `rrmc-app-<time>.db`, and
  the default backup folder is `C:\MyApps\RRMCApplication\backup`. `-BackupDir` still
  overrides it.
- **PC7 Update.** A new script `scripts/update-app.ps1` updates the run environment to the
  checked-out commit: it refuses a working tree with uncommitted changes, runs the backend and
  frontend tests, backs up the app database, builds the run image tagged with the short commit
  id and `latest`, restarts `app` and waits for its health check. On failure it stops at that
  step and prints how to go back to the previous image and backup.
- **PC8 Container tests.** @scripts/container-tests.ps1 checks PC1–PC3 and PC5–PC7 against a
  separate test project and test folders. A later change that mounts development data or
  source code into `app` fails a test.
- **PC9 Docs and decision.** A new ADR supersedes the "one way of running" part of ADR 0002.
  The PRD's NFR-11, the development guide, the architecture, the security doc and `AGENTS.md`
  describe both environments.

### User task (G4)
The agent guardrails block calls to ports `8000` and `5173` only. Port `8080` (or the value
of `RRMC_APP_PORT`) serves real data too. Only the user changes the guardrails'
configuration: before implementation starts, the user adds the run port to the guard and to
@scripts/guard-tests.ps1. The guard already blocks another compose file (`-f`), plain
`docker run` and extra mounts, so `compose.app.yaml` and the app volume are out of reach for
agents. Agents never run `copy-to-app.ps1`, `update-app.ps1` or `-Target app` against the
real projects; the container tests run them against test projects only.

### Out of Scope
- Ollama in a container, HTTPS, access from other devices, starting with Windows.
- Copying data again in either direction, or merging databases. Copying app data into the
  development environment.
- Any change to app features, the API or the database schema.
- Changing the development environment's folders or `.env` (the user's own data, G1).
- Removing old run images (the user removes them by hand).

## Acceptance Criteria

### AC1: Run image has no development tools
**Given** the run image built from `compose.app.yaml`
**When** `sh -c "command -v pytest ruff pyright pip-audit node npm"` runs in it
**Then** it prints nothing and exits with a non-zero code, and `tesseract --list-langs`
lists `eng` and `fin`.

### AC2: Run image holds only the app
**Given** the project root holds `.env`, files under `source/`, `backend/tests/` and
`frontend/node_modules/`
**When** the run image is built and `ls -A /app` runs in it
**Then** it prints exactly `app`, `pyproject.toml`, `static` and `uv.lock`, and
`find / -name .env -not -path '/proc/*'` prints nothing.

### AC3: App runs as a user other than root
**Given** the run image
**When** `id -u` runs in a started `app` container
**Then** it prints a number other than `0`.

### AC4: UI and API on one port
**Given** `app` started with a test settings file and an empty test database
**When** `GET /`, `GET /tuonti`, `GET /kuitit/12` and `GET /api/health` are requested on the
app port
**Then** the first three answer 200 with `content-type: text/html` and a body containing
`<div id="root"></div>`; `/api/health` answers 200 JSON with `checks.ocr` = `ok`.

### AC5: UI files are served
**Given** `app` started as in AC4
**When** the script file named in the `<script type="module" src="...">` of `index.html` is
requested
**Then** it answers 200 with a JavaScript content type.

### AC6: Unknown API path stays an API error
**Given** `app` started as in AC4
**When** `GET /api/does-not-exist` is requested
**Then** it answers 404 with a JSON body, not `index.html`.

### AC7: Port from the settings, on 127.0.0.1 only
**Given** a settings file without `RRMC_APP_PORT`, and one with `RRMC_APP_PORT=8180`
**When** `compose.app.yaml` is resolved with `docker compose config --format json`
**Then** `app` publishes exactly one port, with `host_ip` `127.0.0.1` and `published` `8080`
and `8180` respectively, to container port `8000`.

### AC8: App mounts only app data
**Given** a settings file with `RRMC_APP_SOURCE_DIR=<test folder>` and
`RRMC_APP_DB_VOLUME=<test volume>`
**When** `compose.app.yaml` is resolved
**Then** the mounts of `app` are exactly: `<test folder>/import` at `/data/import`,
`<test folder>/import_done` at `/data/import_done`, `<test folder>/import_failed` at
`/data/import_failed`, `<test folder>/archived` at `/data/archived` and the volume
`<test volume>` at `/data/db`; no mount has a source under `backend/` or `frontend/`, equal to
a value of `RRMC_IMPORT_DIR`, `RRMC_DONE_DIR`, `RRMC_FAILED_DIR` or `RRMC_ARCHIVE_DIR`, or
the volume `rrmc_rrmc-data`.

### AC9: Default app data
**Given** a settings file without `RRMC_APP_SOURCE_DIR` and `RRMC_APP_DB_VOLUME`
**When** `compose.app.yaml` is resolved
**Then** the folder mounts have sources `C:\MyApps\RRMCApplication\source\import`,
`...\import_done`, `...\import_failed` and `...\archived` (as Compose prints them on
Windows), and the database volume is named `rrmc-app-data`.

### AC10: Real engines always
**Given** a settings file with `RRMC_ENGINES=fake`
**When** `compose.app.yaml` is resolved
**Then** the environment of `app` has `RRMC_ENGINES` = `real`.

### AC11: Missing settings file stops the start
**Given** `RRMC_ENV_FILE` names a file that does not exist
**When** `docker compose -f compose.app.yaml up -d --no-build` runs
**Then** it exits with a non-zero code, its output names the missing file, and no container
is created.

### AC12: Invalid setting stops the app
**Given** a settings file with `RRMC_LOG_LEVEL=LOUD`
**When** `app` starts
**Then** the container stops with a non-zero exit code, and its log has the line
`Invalid setting RRMC_LOG_LEVEL: expected DEBUG, INFO, WARNING or ERROR`.

### AC13: Data survives a rebuild
**Given** a row written to the app database
**When** `app` is stopped with `down` and started again with `up -d --build`
**Then** the row is still there.

### AC14: Development backend unchanged without a built UI
**Given** the backend code with no `static` folder next to `app/` (the development container)
**When** `GET /` is requested
**Then** it answers 404, as before this change; `GET /api/health` answers as before.

### AC15: Static serving does not shadow the API
**Given** the backend started with a `static` folder holding `index.html`
**When** every route of the API is listed
**Then** each still answers its own handler: for example `GET /api/health` returns the health
JSON, not `index.html`.

### AC16: Development environment unchanged
**Given** the change is implemented
**When** `compose.yaml` is resolved and every check command of the Commands table runs
**Then** the resolved `compose.yaml` equals the one before the change, and every check
command exits 0 with the same number of passed tests as before plus the new tests.

### AC17: One-time copy, happy path
**Given** the development database holds 3 receipts at schema version V, each development
folder holds 2 synthetic files, the app database volume holds no database, the app folders
are empty or missing, and `app` is not running
**When** `copy-to-app.ps1` runs
**Then** it exits 0; the app database passes `PRAGMA integrity_check`, has schema version V
and 3 rows in `receipts`; each app folder holds the 2 files of the matching development
folder with equal SHA-256 hashes; the development database and folders are unchanged
(same hashes); and the output names counts and the schema version but no file name.

### AC18: Copy refuses when the app database exists
**Given** the app database volume holds a database
**When** `copy-to-app.ps1` runs
**Then** it exits 1 with the line `The app database already exists; nothing was copied.`,
and the app database and app folders are unchanged.

### AC19: Copy refuses when an app folder holds a file
**Given** the app database is missing and `<app folder>/import_done` holds one file
**When** `copy-to-app.ps1` runs
**Then** it exits 1 with the line `The app folders are not empty; nothing was copied.`, and
no database is created in the app volume.

### AC20: Copy refuses while the app runs
**Given** `app` is running
**When** `copy-to-app.ps1` runs
**Then** it exits 1 with the line `Stop the app first: nothing was copied.`

### AC21: Copy with no development database
**Given** the development volume holds no database
**When** `copy-to-app.ps1` runs
**Then** it exits 3 with the line `No development database; nothing was copied.`, and the
app data is unchanged.

### AC22: Failed copy leaves no app database
**Given** the database copy fails its integrity check
**When** `copy-to-app.ps1` runs
**Then** it exits 1, the app volume holds no database file, and no image file was copied.

### AC23: Backup of the run environment
**Given** the app database exists
**When** `backup-db.ps1 -Target app` runs
**Then** it exits 0 and writes `rrmc-app-<yyyy-MM-dd_HHmmss>.db` to
`C:\MyApps\RRMCApplication\backup` (created if missing), or to `-BackupDir` when given, which
passes `PRAGMA integrity_check` and holds the app database's rows; the development database
is not read.

### AC24: Backup and restore default to the development environment
**Given** no `-Target`
**When** `backup-db.ps1` runs
**Then** it behaves as before: the file is `rrmc-<yyyy-MM-dd_HHmmss>.db`, taken from the
development database.

### AC25: Restore of the run environment
**Given** an app backup file and a running `app`
**When** `restore-db.ps1 -Target app -BackupFile <file>` runs and the user types `RESTORE`
**Then** a `rrmc-app-<time>-before-restore.db` backup is written first, the app database
holds the restored rows, `app` runs again afterwards, and the development database and
services are not touched.

### AC26: Invalid target
**Given** `-Target prod`
**When** either script runs
**Then** PowerShell rejects the value before any Docker command runs, and the exit code is
non-zero.

### AC27: Update, happy path
**Given** a clean working tree at commit `C`, passing tests, an existing app database and a
running `app`
**When** `update-app.ps1` runs
**Then** it exits 0; the backup folder holds a new `rrmc-app-<time>-before-update.db`; images
`rrmc-app:<short C>` and `rrmc-app:latest` exist and are the same image; `app` runs that
image; `/api/health` answered 200 within 120 seconds; the output names the tag.

### AC28: Update refuses a dirty working tree
**Given** a tracked file is modified, or an untracked file that is not ignored exists
**When** `update-app.ps1` runs
**Then** it exits 1 with the line `Commit or stash your changes first; nothing was updated.`,
runs no test, writes no backup, builds no image, and the running `app` is unchanged.

### AC29: Update stops on a failing test
**Given** a clean working tree where a backend or frontend test fails
**When** `update-app.ps1` runs
**Then** it exits 1 with a line naming the failed step (`backend tests` or `frontend tests`),
writes no backup, builds no image, and the running `app` is unchanged.

### AC30: Update reports an unhealthy start
**Given** the new image starts but `/api/health` does not answer 200 within 120 seconds
**When** `update-app.ps1` runs
**Then** it exits 1 and prints the commands to start the previous tag again and to restore
the backup it wrote, naming that tag and that backup file.

### AC31: First update without an app database
**Given** the app database volume holds no database
**When** `update-app.ps1` runs
**Then** the backup step prints `No app database yet; nothing to back up.` and the update
continues to AC27's outcome without a backup file.

### AC32: Container tests guard the run environment
**Given** a copy of `compose.app.yaml` in which `app` also mounts `./backend` at `/app`
**When** the run environment checks of @scripts/container-tests.ps1 run against it
**Then** the mount check prints `FAIL`. With the real `compose.app.yaml` every run
environment check prints `PASS`.

### AC33: App data inside the repository is ignored by Git
**Given** `.gitignore`, and a user who sets `RRMC_APP_SOURCE_DIR=./source/app` instead of the
default outside the repository
**When** `git check-ignore` is asked about `source/app/import/a.jpg` and
`source/app/import_done/a.jpg`
**Then** both are ignored.

### AC34: Docs describe both environments
**Given** `docs/development.md`, `docs/architecture.md`, `docs/security.md`, `AGENTS.md`,
`specs/PRD.md` and `.env.example`
**When** they are read
**Then** they describe how to start, update, back up and restore the run environment and how
to copy the data once; `.env.example` lists `RRMC_APP_PORT`, `RRMC_APP_SOURCE_DIR` and
`RRMC_APP_DB_VOLUME` with their defaults; NFR-11 no longer says there is one way of running;
a new ADR records the decision, and ADR 0002 links to it.

## Files to Modify
| File | Change |
|---|---|
| `compose.app.yaml` | New: run environment, service `app` (PC1–PC3) |
| `docker/app.Dockerfile` | New: multi-stage build, UI build then run image (PC1) |
| `docker/app.Dockerfile.dockerignore` | New: allow list of the build context; keeps `.env`, `source/`, `node_modules`, tests and outputs out (AC2, [P10](#p10-spec-changes)) |
| `backend/app/main.py` | Serve the built UI when a `static` folder exists (PC2, PC4) |
| `backend/app/static_ui.py` | New: static files and the `index.html` fallback (PC2) |
| `backend/tests/unit/test_static_ui.py` | New: tests of the static serving (AC4–AC6, AC14, AC15) |
| `frontend/package.json` | `build` script |
| `scripts/copy-to-app.ps1` | New: one-time copy (PC5) |
| `scripts/backup-db.ps1`, `scripts/restore-db.ps1` | `-Target dev|app` (PC6) |
| `scripts/update-app.ps1` | New: update (PC7) |
| `scripts/container-tests.ps1` | Run environment checks (PC8) |
| `.env.example` | `RRMC_APP_PORT`, `RRMC_APP_SOURCE_DIR`, `RRMC_APP_DB_VOLUME` |
| `.gitignore` | Checked: `source/` already covers `source/app/` (AC33); `backend/static/` added ([P2](#p2-the-backend-serves-the-built-ui-pc2-pc4)) |
| `docs/adr/0008-run-container.md` | New ADR (PC9) |
| `docs/adr/0002-docker.md` | Status: superseded in part by ADR 0008 |
| `docs/development.md` | Running the app: both environments, copy, update, backup and restore |
| `docs/architecture.md` | Runtime and deployment; folder structure |
| `docs/security.md` | Run port, app data, which scripts agents never run against real projects |
| `docs/subsystems/ui/README.md` | The built UI and how the backend serves it |
| `docs/subsystems/storage/README.md` | The second database volume |
| `docs/learnings.md` | Entry for the T6 incident ([P10](#p10-spec-changes)) |
| `docs/content-plan.md` | Gap note for this spec |
| `AGENTS.md` | Runtime row, layout, database location |
| `specs/PRD.md` | NFR-11 changed |
| `specs/README.md` | Row 28 for this spec |

## Risk
- **What could break:** the development environment, if the backend change touches routing;
  AC14–AC16 guard it. The UI's client-side paths on reload in the run environment; AC4 guards
  it. A wrong `RRMC_APP_DB_VOLUME` (for example `rrmc_rrmc-data`) would share the database;
  the docs warn, and AC9 fixes the default. The one-time copy writes into the app data; it
  refuses whenever app data exists (AC18–AC20). An agent could run the new scripts against the
  real projects; the guard does not see inside scripts, so `AGENTS.md` and `security.md` forbid
  it, and the user adds the run port to the guard (User task).
- **Rollback:** revert the change. The development environment, its database and folders are
  not changed by any part of it. The run environment is removed by the user with
  `docker compose -f compose.app.yaml down`; its volume and `C:\MyApps\RRMCApplication` stay
  until the user deletes them.
- **Dependencies:** Docker Compose; the existing images' base images (`python:3.12-slim-bookworm`,
  a Node.js image for the UI build). No new Python or npm packages.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC14 | static UI setup | no folder | no `static` folder | the app is created | no route for `/`; `GET /` answers 404 | none |
| AC4 | static UI setup | index | a temp `static` folder with `index.html` | `GET /` | 200 `text/html`, the file's body | none |
| AC4 | static UI setup | client path | same | `GET /kuitit/12`, `GET /tuonti` | 200, `index.html` | none |
| AC5 | static UI setup | asset | `static/assets/a.js` | `GET /assets/a.js` | 200, JavaScript content type | none |
| AC6 | static UI setup | API 404 | same | `GET /api/does-not-exist` | 404 JSON | none |
| AC15 | static UI setup | API first | same | `GET /api/health` | the health JSON | fake engines |
| AC4 | static UI setup | path outside | same | `GET /../pyproject.toml` (encoded) | not the file: 404 or `index.html` | none |

### Integration tests
Run by @scripts/container-tests.ps1 against Compose project `rrmc-app-test` (and `rrmc-test`
for the development side of the copy), with settings files, folders and volumes of their own
under `%TEMP%`. The real `.env`, `source/`, `rrmc_rrmc-data` and `rrmc-app-data` are never
read or changed. The scripts take parameters for the projects, settings file and backup folder
for this.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | tools | `command -v ...`, `tesseract --list-langs` in the run image | nothing found; `eng`, `fin` | PASS |
| AC2 | image content | `ls -A /app`, `find / -name .env` | exact list; nothing | PASS |
| AC3 | user | `id -u` | not `0` | PASS |
| AC4–AC6 | one port | HTTP requests to the test port | as in the ACs | PASS |
| AC7 | ports | `config --format json`, default and `8180` | `127.0.0.1:8080`, `127.0.0.1:8180` | PASS |
| AC8, AC9 | mounts | `config --format json`, test and default values | exact mounts | PASS |
| AC10 | engines | `config` with `RRMC_ENGINES=fake` | `real` | PASS |
| AC11 | missing settings | `up -d --no-build` | non-zero, file named, no container | PASS |
| AC12 | invalid setting | `up -d`, `wait`, `logs` | non-zero, the line | PASS |
| AC13 | rebuild | write row, `down`, `up -d --build`, read row | row found | PASS |
| AC16 | dev config | `config` of `compose.yaml` before and after | equal (existing checks pass) | PASS |
| AC17–AC22 | copy | `copy-to-app.ps1` with test projects and synthetic data | as in the ACs | PASS |
| AC23–AC26 | backup and restore | scripts with `-Target app` and none, test projects | as in the ACs | PASS |
| AC27–AC31 | update | `update-app.ps1` with test project, a temporary clone at a test commit; a failing test injected in the clone; a health URL that never answers | as in the ACs | PASS |
| AC32 | guard | an override that mounts `./backend` into `app` | `FAIL` reported | PASS |
| AC33 | ignore | `git check-ignore` | ignored | PASS |

### E2E tests
None new. The UI does not change; the E2E journeys keep running against the development
containers. The run image's UI is checked by AC4–AC6 in the container tests.

### Manual checks
| AC | Check | Expected outcome |
|---|---|---|
| AC16 | run every check command | all exit 0, counts as before plus new tests |
| AC34 | read the listed docs | as in the AC |
| User | after the user's copy and first start | the UI at `http://127.0.0.1:8080` shows the copied receipts and their images |

### Coverage target
- Backend: the static serving module has every branch tested. Overall backend coverage does
  not drop.
- Frontend: unchanged.
- Scripts: every exit path of `copy-to-app.ps1` and `update-app.ps1` has a container test.

### Test data
- Synthetic only: synthetic image files and receipt rows written by the tests into test
  volumes and test folders under `%TEMP%`.
- Mocks: none in the container tests; the backend unit tests use the fake engines.

## Related Documentation (MANDATORY)
- Tier 1: [development.md](../../docs/development.md#running-the-app),
  [architecture.md](../../docs/architecture.md#runtime-and-deployment),
  [security.md](../../docs/security.md), [PRD NFR-11](../PRD.md), [AGENTS.md](../../AGENTS.md)
- Tier 2: [ui](../../docs/subsystems/ui/README.md), [storage](../../docs/subsystems/storage/README.md)
- ADRs: [0002 Docker](../../docs/adr/0002-docker.md)
- Specs: [foundation](foundation.md), [test isolation](test-isolation.md),
  [agent guardrails](agent-guardrails.md)

<!-- The Plan phase appends "## Plan" and the Tasks phase appends "## Tasks" below. -->

## Plan

### Findings that shape the plan
Read from the code on 2026-11-24. The items marked *to confirm* are checked with Docker in
Task 1, before any other task; if one does not hold, the plan is updated first.

- The backend's 404 handler answers every `StarletteHTTPException(404)` with the API's JSON
  error `not_found` (@backend/app/errors.py). Raising it from a catch-all route gives AC6
  for free.
- The host check allows `127.0.0.1` and `localhost` (@backend/app/host_check.py), the Host a
  browser sends to `127.0.0.1:8080`. CORS is not involved: the UI and the API share one
  origin.
- The UI builds with `vite build` into `frontend/dist`: `index.html` plus hashed files in
  `dist/assets/`. The built `index.html` refers to `/assets/<name>.js`.
- Client-side paths are `/`, `/tuonti`, `/kuitit`, `/kuitit/<id>`, `/yhteenveto`, `/vuosi`,
  `/budjetti`, `/vertailu`, `/arkisto`, `/arkisto/<year>` (@frontend/src/navigation.ts). None
  starts with `/api` or `/assets`.
- `docker compose config --format json` resolves mount sources and named volume names, so
  the scripts take the real folder and volume names from Compose instead of parsing `.env`
  (used the same way by @scripts/container-tests.ps1 today).
- The agent guard blocks another compose file, plain `docker run`, `exec`, `cp`, extra mounts
  and the services `backend`, `frontend` and `eval` ([security.md](../../docs/security.md)).
  It does not look inside script files.
- *To confirm:* BuildKit reads `docker/app.Dockerfile.dockerignore` for a build with
  `dockerfile: docker/app.Dockerfile` and ignores the root (there is none) and the
  development contexts are unaffected.
- *To confirm:* on Docker Desktop, a non-root container user can write to bind-mounted
  Windows folders, and a named volume mounted at `/data/db` takes the owner of that folder
  in the image on first use.
- *To confirm:* `uv sync --frozen --no-dev` installs no package of the `dev` group, and
  `vite build` runs on `node:22-bookworm-slim` with the current lock file.
- *To confirm:* `Read-Host` in `restore-db.ps1` reads `RESTORE` from piped input, so the
  container tests can drive it.

T1 probe results (2026-11-24; the user ran the probe script, with synthetic files and the
code of `HEAD` in `%TEMP%`):

| Item | Result | Proof |
|---|---|---|
| Per-Dockerfile ignore list | holds | Build context: `backend` (`app`, `pyproject.toml`, `uv.lock`) and `frontend` only; no `.env`, `source`, `node_modules` or `__pycache__`. Another Dockerfile with the same context saw `.env` and `source`, so the list does not apply to it. The probe used a synthetic context, not the development builds |
| Non-root writes | holds | uid `10001` wrote, moved and deleted in an existing Windows folder, wrote in one Docker created, and wrote a SQLite file in a new volume (`/data/db` owner `10001:10001`) |
| `uv sync --frozen --no-dev`, `vite build` | holds | `command -v` found no tool (exit 127), no `dev` package in the venv; `static/index.html` refers to `/assets/index-<hash>.js` |
| Piped `RESTORE` into `Read-Host` | **does not hold** after `docker compose run` | `Read-Host` alone read `RESTORE`; after a `docker compose run` in the same script it read an empty text, because Compose takes the script's standard input. `restore-db.ps1` makes such a call before it asks |

A second probe (2026-11-24, also run by the user) showed that `docker compose run
--interactive=false` leaves the input for `Read-Host`: `RESTORE` was read. P5 uses it.

### P1 Run image (PC1)
New `docker/app.Dockerfile`, build context the project root, three stages:

| Stage | Base | Does |
|---|---|---|
| `ui` | `node:22-bookworm-slim` | `npm ci`, then `npm run build` (new script `"build": "vite build"`) |
| `deps` | `python:3.12-slim-bookworm` + `uv` copied from `ghcr.io/astral-sh/uv:0.9.5` | `uv sync --frozen --no-dev` into `/opt/venv` |
| final | `python:3.12-slim-bookworm` | `tesseract-ocr`, `tesseract-ocr-fin`, `tesseract-ocr-eng`; copies `/opt/venv`, `backend/app` to `/app/app`, `backend/pyproject.toml` and `backend/uv.lock` to `/app`, `ui`'s `dist` to `/app/static` |

- Final stage: no `uv`, no Node.js. The same Python base in `deps` and final keeps the venv's
  interpreter link valid. `PYTHONDONTWRITEBYTECODE=1` keeps `__pycache__` out of `/app`
  (AC2).
- User `rrmc` (uid and gid `10001`). `/data/db`, `/data/import`, `/data/import_done`,
  `/data/import_failed` and `/data/archived` are created and owned by it, so a new volume at
  `/data/db` is writable.
- `ARG RRMC_REVISION` becomes the label `org.opencontainers.image.revision`; the update script
  reads it to name the previous version (P6).
- `CMD`: `python -m app.prestart && exec uvicorn --factory app.main:create_app --host 0.0.0.0
  --port 8000 --no-access-log`, without `--reload` (AC12 through prestart).
- `docker/app.Dockerfile.dockerignore` is an allow list: `*`, then `!backend/app`,
  `!backend/pyproject.toml`, `!backend/uv.lock`, `!frontend`, then excluded again
  `frontend/node_modules`, `frontend/dist`, `frontend/coverage`, `frontend/test-results`,
  `frontend/playwright-report`, `**/__pycache__`. `.env` and `source/` can never enter the
  context. The development images keep their own contexts (`./backend`, `./frontend`).

### P2 The backend serves the built UI (PC2, PC4)
New module @backend/app/static_ui.py:

- `STATIC_DIR = Path(__file__).resolve().parent.parent / "static"` (`/app/static` in the run
  image; does not exist in the development container, whose `/app` is `./backend`).
- `add_static_ui(app: FastAPI, static_dir: Path) -> None`. If `static_dir / "index.html"` does
  not exist it does nothing (AC14). Otherwise it adds one route, `GET /{path:path}`:
  - `path` is `api` or starts with `api/`: raise `StarletteHTTPException(404)`, which the
    existing handler turns into the JSON `not_found` (AC6).
  - `path` is one of the files listed under `static_dir` at start: `FileResponse` (AC5). The
    content type comes from the file name.
  - anything else, including a path that points outside `static_dir`: `index.html` (AC4).
- `create_app` gets `static_dir: Path | None = None` (tests pass a temporary folder) and calls
  `add_static_ui(app, static_dir or STATIC_DIR)` after the last `include_router`. Routes are
  matched in order, so every API route wins over the catch-all (AC15).
- `backend/static/` goes into `.gitignore`, so a stray build output in the development folder
  is never committed.

### P3 `compose.app.yaml` (PC2, PC3)
```yaml
name: rrmc-app

services:
  app:
    build:
      context: .
      dockerfile: docker/app.Dockerfile
    image: ${RRMC_APP_IMAGE:-rrmc-app}:${RRMC_APP_TAG:-latest}
    env_file:
      - path: ${RRMC_ENV_FILE:-.env}
        required: true
    environment:
      RRMC_ENGINES: real
    ports:
      - "127.0.0.1:${RRMC_APP_PORT:-8080}:8000"
    volumes:
      - ${RRMC_APP_SOURCE_DIR:-C:/MyApps/RRMCApplication/source}/import:/data/import
      - ${RRMC_APP_SOURCE_DIR:-C:/MyApps/RRMCApplication/source}/import_done:/data/import_done
      - ${RRMC_APP_SOURCE_DIR:-C:/MyApps/RRMCApplication/source}/import_failed:/data/import_failed
      - ${RRMC_APP_SOURCE_DIR:-C:/MyApps/RRMCApplication/source}/archived:/data/archived
      - app-db:/data/db
    extra_hosts:
      - "host.docker.internal:host-gateway"
    healthcheck: (same Python urllib check as backend-e2e)

volumes:
  app-db:
    name: ${RRMC_APP_DB_VOLUME:-rrmc-app-data}
```
- `environment` overrides `env_file`, so `RRMC_ENGINES` is `real` (AC10).
- `name:` on the volume drops the project prefix, so the name is exactly
  `RRMC_APP_DB_VOLUME` (AC8, AC9).
- Compose reads `.env` in the project folder for `${...}`, so `RRMC_APP_PORT`,
  `RRMC_APP_SOURCE_DIR` and `RRMC_APP_DB_VOLUME` are set there like the other settings.
- The default run folder is an absolute Windows path, because the app has one user on one
  computer and the folder must stay outside the repository. Docker Desktop creates a missing
  bind folder; the copy script creates them too (P4). The guard's G1 rule already blocks any
  path with a `source` segment, so the default folders are protected for agents.
- `RRMC_APP_TAG` picks the image to run; it is unset in normal use (`latest`) and set by the
  update script and for a rollback (P6).
- Commands for the user: `docker compose -f compose.app.yaml up -d`, `... down`,
  `... logs -f app`.

### P4 One-time copy: `scripts/copy-to-app.ps1` (PC5)
Parameters for the container tests only: `-DevProject` (default `rrmc`), `-AppProject`
(default `rrmc-app`), `-EnvFile` (default `.env`). Steps, each stopping the script on failure:

1. Resolve both configurations with `docker compose config --format json`: the development
   `backend` folder sources, the app folder sources and the app volume name.
2. `app` running (`ps --status running -q app`) → AC20 line, exit 1.
3. `docker compose -f compose.app.yaml run --rm --no-deps app python -c <check>`: prints the
   state of `/data/db/rrmc.db` and the file count of the four folders. This also builds the
   image if needed and creates the app volume through Compose, with its labels. Database
   present → AC18 line, exit 1; any file → AC19 line, exit 1.
4. Database: `docker compose -p <dev> run --rm --no-deps -v <app volume>:/to backend python -c
   <copy>`. The copy opens `/data/db/rrmc.db` read-only (missing → exit 3, AC21), writes
   `/to/rrmc.db.tmp` with the backup API, sets `journal_mode=DELETE`, runs
   `PRAGMA integrity_check`, reads the schema version and the `receipts` count. On any
   failure it deletes the temporary file and exits 1 (AC22). On success it renames it to
   `/to/rrmc.db` and gives it owner `10001:10001`. The development `backend` service is
   used only through `run` with its own image; the running development app is not stopped.
5. Images: on Windows, every file under each development folder is copied with its relative
   path to the matching app folder (`Copy-Item`; the target was checked empty, so nothing is
   overwritten). The development folders are only read.
6. Output: schema version, receipt count and file count per folder, no file names (AC17).

Images are copied after the database, so a failed database copy copies no image (AC22). If an
image copy fails after the database was written, the script stops and says which step
failed; a second run then refuses (AC18), and the docs say how to finish by hand.

### P5 Backup and restore with `-Target` (PC6)
Both scripts get `[ValidateSet("dev", "app")] [string]$Target = "dev"` (AC26: PowerShell
rejects another value before the script body runs), and, for the container tests only,
`-ComposeProject` and `-EnvFile`.

| Target | Compose call | Service | File name | Default `-BackupDir` |
|---|---|---|---|---|
| `dev` | `docker compose` (project `rrmc`) | `backend` | `rrmc-<time>[-suffix].db` (unchanged, AC24) | `%USERPROFILE%\rrmc-backup` (unchanged) |
| `app` | `docker compose -f compose.app.yaml` (project `rrmc-app`) | `app` | `rrmc-app-<time>[-suffix].db` | `C:\MyApps\RRMCApplication\backup` |

The Python one-liners and the steps stay as they are; only the Compose call, the service and
the file prefix depend on the target. The restore's own backup passes the same target. Every
`docker compose run` in `restore-db.ps1` gets `--interactive=false`, so that it does not take
the input of `Read-Host` (T1 probe); the container tests can then pipe `RESTORE` in (AC25).

### P6 Update: `scripts/update-app.ps1` (PC7)
Parameters for the container tests only: `-AppProject`, `-DevProject`, `-EnvFile`,
`-BackupDir`, `-HealthTimeoutSeconds` (default `120`). Steps:

1. `git status --porcelain` not empty → AC28 line, exit 1.
2. `docker compose -p <dev> run --rm backend-test pytest`, then
   `docker compose -p <dev> run --rm frontend-test npm test`; a failure → `Update stopped:
   backend tests failed; nothing was updated.` (or `frontend tests`), exit 1 (AC29).
3. Previous version: the `org.opencontainers.image.revision` label of `rrmc-app:latest`, if
   the image exists.
4. `backup-db.ps1 -Target app -Suffix before-update`; exit 3 → AC31 line and continue; other
   failure → exit 1 before any build.
5. `C = git rev-parse --short=12 HEAD`. Build with `RRMC_APP_TAG=C` and
   `--build-arg RRMC_REVISION=C`, then `docker tag rrmc-app:C rrmc-app:latest`.
6. `up -d --no-build app` with `RRMC_APP_TAG=C`.
7. Poll `http://127.0.0.1:<published port>/api/health` (port from `config`) every 2 seconds
   up to the timeout. 200 → `Updated to rrmc-app:C.`, exit 0 (AC27). Otherwise print the
   rollback commands with the previous tag and the backup file of step 4, exit 1 (AC30):
   ```powershell
   docker tag rrmc-app:<previous> rrmc-app:latest
   docker compose -f compose.app.yaml up -d --no-build
   powershell -ExecutionPolicy Bypass -File scripts/restore-db.ps1 -Target app -BackupFile <file>
   ```

### P7 Container tests (PC8)
A new section in @scripts/container-tests.ps1 with project `rrmc-app-test`, port `18080`,
folders under `%TEMP%\rrmc-container-tests\app\` and volume `rrmc-app-test-data`; the copy
uses the existing `rrmc-test` project as the development side. Every check prints
`PASS`/`FAIL` with its AC IDs.

| Check | ACs | How |
|---|---|---|
| configuration | AC7–AC10 | `config --format json` with test settings files: default and `8180` port, test and default app data, `RRMC_ENGINES=fake` |
| missing settings | AC11 | `up -d --no-build` with a missing `RRMC_ENV_FILE` |
| image | AC1–AC3 | `run --rm --no-deps app sh -c ...` (`command -v`, `tesseract --list-langs`, `ls -A /app`, `find`, `id -u`). The project root holds `.env` and `source/` when the image is built; `ls` and `find` prove neither entered it. The tests never read them |
| one port | AC4–AC6 | `up -d`, wait for health, `Invoke-WebRequest` on `/`, `/tuonti`, `/kuitit/12`, the script file from `index.html`, `/api/does-not-exist` |
| invalid setting | AC12 | as the foundation's AC7 check, with `RRMC_LOG_LEVEL=LOUD` |
| rebuild | AC13 | as the foundation's AC11 check |
| guard | AC32 | `Get-IsolationProblems` on `compose.app.yaml` plus an override mounting `./backend` |
| copy | AC17–AC22 | synthetic rows written in `rrmc-test`'s volume, synthetic files in its folders; the script with the test projects; the failing integrity case uses a development database file that is not SQLite |
| backup, restore | AC23–AC26 | the scripts with `-Target app` and the test project; `RESTORE` piped in |
| update | AC27–AC31 | a `git clone --local` of the repository into `%TEMP%`; its own script with the test projects; a dirty file, an added failing test committed in the clone, and `RRMC_LOG_LEVEL=LOUD` for the unhealthy start, with a 20-second timeout |
| ignore | AC33 | `git check-ignore` |

The existing checks of `compose.yaml` stay; they and `git diff` of `compose.yaml` cover AC16.
The section prints the cleanup commands for the test volume, images and clone, as today.

### P8 Decision record (PC9)
New [ADR 0008](../../docs/adr/0008-run-container.md): a run environment beside the
development environment. It supersedes ADR 0002's "one way of running" and "no production
build"; the rest of ADR 0002 stands. ADR 0002 gets the status line
`accepted; superseded in part by ADR 0008`.

### P9 Docs (PC9)
- `docs/development.md`: "Running the app" splits into "Run environment" (start, stop, logs,
  update, backup and restore with `-Target app`, the one-time copy and how to finish it by
  hand) and "Development environment" (today's text). A warning: never set
  `RRMC_APP_DB_VOLUME` to `rrmc_rrmc-data`.
- `docs/architecture.md`: Runtime and deployment, folder structure (`compose.app.yaml`,
  `docker/`).
- `docs/security.md`: the run port, the run folder `C:\MyApps\RRMCApplication` (real data:
  keep it out of cloud-synced folders), app data locations, that agents never run the new
  scripts or `-Target app` against the real projects, and the user task for the guard.
- `docs/subsystems/ui/README.md`: the built UI and the catch-all route.
- `docs/subsystems/storage/README.md`: the second volume.
- `AGENTS.md`: Runtime row, layout (`compose.app.yaml`, `docker/`), the run folder, the
  database locations; Commands unchanged.
- `specs/PRD.md`: NFR-11 reworded; a decision log line.
- `.env.example`: the three new settings with their defaults.
- `docs/content-plan.md`: gap note while the spec is in progress.

### P10 Spec changes
- `.dockerignore` at the root became `docker/app.Dockerfile.dockerignore` (P1), so the
  ignore list applies to the run image only and cannot change the development builds.
- `backend/tests/...` became @backend/tests/unit/test_static_ui.py.
- `.gitignore` gets `backend/static/` (P2).
- T2 (2026-11-24): P2 looks a path up in the file list read at start instead of resolving it
  on each request, so a malformed path cannot fail or leave the folder.
- T4 (2026-11-24): P3 takes the image name from `RRMC_APP_IMAGE` (default `rrmc-app`). The
  container tests use `rrmc-app-test`, so they never replace the real `rrmc-app:latest`. It is
  for the tests only and not listed in `.env.example`.
- T4 check edit after a red run (G7): the AC8/AC9 mount check compared paths with `\`; Compose
  prints the app folders with `/`, which AC9 allows ("as Compose prints them on Windows"). The
  check now expects `/`. The expected folders are the same.
- T5 (2026-11-24): P3 loses `restart: unless-stopped`. It would restart the app again and again
  after an invalid setting, while AC12 says the container stops, and it would start the app
  with Docker Desktop, which is out of scope ("starting with Windows").
- T5 check edit after a red run (G7): the AC12 check expected a bare number from
  `docker compose wait`, which prints a sentence ending with the status code. It now reads the
  number at the end and still requires it to be non-zero.
- T6 (2026-11-24): the test parameters of every script (`-ComposeProject` or the project
  parameters, and `-EnvFile`) are accepted only together, so a test can never reach the real
  data because one of them is missing.
- T8 (2026-11-24): P7's clone gets the working tree's uncommitted files in a commit of its own,
  so the checks test the code at hand, and a shortened test suite to keep the run short. P6
  names the previous image by its id when `latest` has no revision label.
- Bug fix after T11 (2026-11-24): P4 builds the image before its first `run`, and P6 builds it
  before the backup when there is none. Built inside a captured call in a console, the build
  failed with `failed to get console`. Two container checks run the scripts in a console.
- T6 incident (2026-11-24, G1 and G2): the Red run called the old `backup-db.ps1`, which ignored
  the unknown test parameters and backed up the real development database four times into
  `%TEMP%`. The database was opened read-only and nothing left the computer; the user was told
  and asked to delete the copies. Since then every script has `[CmdletBinding()]`, and the
  container tests run no script without the test parameters.
- T1 (2026-11-24): P5 adds `--interactive=false` to the restore's `docker compose run` calls.

No AC changes.

### Data flow and data model
No change to the schema, the API or the data flow inside the app. The run environment has its
own copy of the data; nothing flows between the environments after the one-time copy.

### Dependencies
No new Python or npm package. New base image `node:22-bookworm-slim` for the UI build stage
only; it is not in the run image.

### AC check
| AC | Covered by |
|---|---|
| AC1–AC3 | P1; P7 image check |
| AC4–AC6, AC14, AC15 | P2; unit tests; P7 one-port check |
| AC7–AC10 | P3; P7 configuration check |
| AC11, AC12 | P3 (`required: true`), P1 (`CMD` with prestart); P7 |
| AC13 | P3 volume; P7 rebuild check |
| AC16 | P2 (no-op without `static`), P3 (a new file); existing container tests, `git diff` |
| AC17–AC22 | P4; P7 copy checks |
| AC23–AC26 | P5; P7 |
| AC27–AC31 | P6; P7 update checks |
| AC32 | P7 guard check |
| AC33 | P7 ignore check |
| AC34 | P8, P9; manual read |

## Tasks
Every task ends with the tests, lint, format check and type check of the parts it changed
(G8). Container checks run only through @scripts/container-tests.ps1, against the test
projects `rrmc-test` and `rrmc-app-test`; no task runs a new script against `rrmc` or
`rrmc-app`.

- [x] **T0 (user) Guard the run port.** The user adds port `8080` to the guard's app port
  pattern and a case to @scripts/guard-tests.ps1, and runs the guard tests (G4: agents may not
  change the guard). *Proof:* guard tests pass and a call to `127.0.0.1:8080` is blocked.
  Implementation starts after this.
- [x] **T1 Confirm the findings.** Probe the four *to confirm* items of the Plan with
  throwaway files under `%TEMP%` only (no project file changes). Record the results in
  [Findings](#findings-that-shape-the-plan). If one does not hold, stop and update the Plan
  first. *Proof:* the recorded probe output.
- [x] **T2 Static UI in the backend.** AC4, AC5, AC6, AC14, AC15. Red: new
  @backend/tests/unit/test_static_ui.py with the unit rows of the Testing Strategy (a
  temporary `static` folder; no folder; `/api/does-not-exist`; `/api/health`; an encoded
  path outside the folder). Green: @backend/app/static_ui.py, `create_app(static_dir=...)`,
  `backend/static/` in `.gitignore`. *Proof:* backend tests, lint, format check, pyright.
- [x] **T3 UI build script.** Part of AC4, AC5. Add `"build": "vite build"` to
  `frontend/package.json`. *Proof:* `docker compose run --rm frontend-test npm run build`
  writes `dist/index.html` (ignored by Git); frontend tests, lint, format check, type check.
- [x] **T4 Compose file and configuration checks.** AC7, AC8, AC9, AC10, AC11, AC32. Red:
  the run environment section of @scripts/container-tests.ps1 with its configuration,
  missing-settings and guard checks (they fail: no `compose.app.yaml`). Green:
  `compose.app.yaml` as in P3 (the build part may point to a Dockerfile added in T5; the
  checks of this task do not build). *Proof:* those checks print `PASS`; the existing
  container checks still pass.
- [x] **T5 Run image and its checks.** AC1, AC2, AC3, AC4, AC5, AC6, AC12, AC13. Red: image,
  one-port, invalid-setting and rebuild checks. Green: `docker/app.Dockerfile` and
  `docker/app.Dockerfile.dockerignore` as in P1. *Proof:* those checks print `PASS`.
- [x] **T6 Backup and restore with `-Target`.** AC23, AC24, AC25, AC26. Red: backup and
  restore checks against the test projects, including the unchanged `dev` default. Green:
  `-Target`, `-ComposeProject`, `-EnvFile` in both scripts as in P5. *Proof:* those checks
  print `PASS`.
- [x] **T7 One-time copy.** AC17, AC18, AC19, AC20, AC21, AC22. Red: copy checks with
  synthetic rows and files. Green: `scripts/copy-to-app.ps1` as in P4. *Proof:* those checks
  print `PASS`, including unchanged development hashes.
- [x] **T8 Update.** AC27, AC28, AC29, AC30, AC31. Red: update checks in a temporary clone
  (dirty tree, failing test, unhealthy start, first run, happy path). Green:
  `scripts/update-app.ps1` as in P6. *Proof:* those checks print `PASS`.
- [x] **T9 Ignore and unchanged development environment.** AC16, AC33. Add the
  `git check-ignore` check. Run every command of the Commands table and compare the counts
  with the baseline taken before T2; `git diff --stat` shows no change to `compose.yaml`.
  *Proof:* all commands exit 0; the counts are the baseline plus the new tests.
- [x] **T10 Docs.** AC34. P8 and P9: `docs/development.md`, `docs/architecture.md`,
  `docs/security.md`, both subsystem READMEs, `AGENTS.md`, `specs/PRD.md` (NFR-11, decision
  log), `.env.example`, ADR 0002 status line, `docs/content-plan.md`, `specs/README.md`.
  *Proof:* the AC34 read-through, and every command shown in the new docs was run in a test
  project or appears in a passing container check.
- [x] **T11 Audit.** Run `.agents/skills/review-audit/SKILL.md` against this spec. *Proof:*
  audit verdict PASS, recorded under `## Audit`.

## Audit

### Audit: Run container (2026-11-24)
- Acceptance criteria: 33/34 met with passing checks; AC16 met except for the E2E baseline
  (finding 2)
- Tests: backend 1661 passed (baseline 1642 + 19 new), frontend 466 (baseline 466), E2E 53,
  container checks 77 (baseline 23), guard 458. Lint, format check and type check pass.
  `static_ui.py` coverage 100 % lines and branches; overall coverage was not measured
- Security: `pip-audit` and `npm audit --omit=dev` found nothing; ports on `127.0.0.1`; one
  incident during the work (finding 3)
- `compose.yaml` unchanged (`git diff`)
- Docs updated: yes; spec status: Done

| # | Severity | File | Finding | Recommendation |
|---|---|---|---|---|
| 1 | Medium | `copy-to-app.ps1`, `update-app.ps1` | The coverage target asks for a container test of every exit path. Five checks were added; the paths where Git, `docker ps`, `docker tag`, the app data check or a mount lookup fails have none, because they need a broken Docker or Git | Accepted by the user 2026-11-24 |
| 2 | Low | — | T9's E2E baseline was not taken before T2 (stale container). No E2E test file changed, and 53 pass | Accepted by the user 2026-11-24 |
| 3 | High, fixed | `container-tests.ps1` | The T6 Red run copied the real development database into `%TEMP%` (P10, `docs/learnings.md`) | User: delete the copies, if not done |
| 4 | Low, later | `static_ui.py` | `index.html` has no `Cache-Control`; after an update a browser may show the old one until a reload | Propose `no-cache` as a spec change |
| 5 | Low, later | `compose.app.yaml` | When the image is missing, Compose asks Docker Hub for `rrmc-app` before building | Propose a `pull_policy` as a spec change |
| 6 | High, fixed | `copy-to-app.ps1`, `update-app.ps1` | Found by the user after the first verdict: the copy failed in a console when no run image existed, and the update had the same fault (P10, `docs/learnings.md`) | Fixed, with two console checks |

G7: the test edits log has no line for this work. Edits to the checks in
`container-tests.ps1` after a red run are in [P10](#p10-spec-changes) (T4, T5), backed by AC9
and AC12; in T7 the unneeded `-DevEnvFile` argument was dropped to match P4. In
`test_static_ui.py` one constant was renamed for lint (S105).

Verdict: PASS — first REQUEST CHANGES; the user accepted findings 1 and 2, and finding 6 was
fixed. Findings 4 and 5 are left for later spec changes.
