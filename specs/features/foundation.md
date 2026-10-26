# Feature: Project foundation

## Overview
- **Status:** Approved (2026-10-26); Plan approved (2026-10-26); Tasks in review
- **Created:** 2026-10-23
- **Implements:** PRD FR-29 (model name as one setting), FR-30 (model loaded at start),
  FR-31 (clear message when Ollama or the model is unavailable; the import part is in the
  import spec), FR-32 (settings file), NFR-2, NFR-3, NFR-4, NFR-10, NFR-11, NFR-13, NFR-14
  (tooling only), NFR-15 (app shell).
- **Affected subsystems:** storage, receipt-reading (interfaces only), ui
  (docs not written yet: `docs/subsystems/storage/README.md`,
  `docs/subsystems/receipt-reading/README.md`, `docs/subsystems/ui/README.md`)

## Problem Statement
There is no code yet. Every feature spec needs the same base: a backend and a frontend that
start, a settings file, a database with schema migrations, a common error format, the OCR
and model interfaces with fakes for tests, and working test and lint commands. Building this
inside the first feature spec (product management) would mix setup with feature behavior.

Setting up Python, Node.js and Tesseract by hand on Windows is slow and easy to get wrong.
The app is installed and developed with **Docker**, so the only prerequisites on the
computer are Docker Desktop, Git and Ollama.

## Current Behavior
None (new). The stack is in [ADR 0001](../../docs/adr/0001-tech-stack.md) and the target
design in [architecture.md](../../docs/architecture.md).

## Proposed Change

### Decisions behind this spec
- Docker is used both to run the app and to develop it: tests, lint and dev servers run in
  containers, and code changes on the computer are picked up without rebuilding.
- **Ollama runs on Windows, not in a container.** The containers reach it at
  `http://host.docker.internal:11434`. This keeps GPU support simple.
- Tesseract with `fin` and `eng` is installed in the backend container image, so it is not
  installed on Windows.
- All settings are in **one `.env` file** in the project root, read both by Docker Compose
  and by the backend. `.env.example` is committed; `.env` is not (FR-32). This replaces the
  `config.example.toml` planned earlier.
- **One way of running** for normal use and development: `docker compose up` starts the
  backend and the Vite dev server, and the user opens the UI at `http://127.0.0.1:5173`.
  There is no separate production build or mode.

### Parts

- **PC1 Containers.** One Docker Compose project with two services:
  - `backend`: FastAPI with Tesseract (`fin` + `eng`).
  - `frontend`: the React + Vite + TypeScript UI.
  `docker compose up` from the project root starts both. Source code is mounted into the
  containers, and a change to a backend or frontend source file is picked up without
  restarting the containers.
- **PC2 Local-only network.** Every published port is bound to `127.0.0.1` on the computer:
  backend `127.0.0.1:8000`, UI `127.0.0.1:5173` (ports configurable). Nothing listens on
  other interfaces (NFR-2). The backend allows CORS only from the UI origin.
- **PC3 Settings.** The settings below are read from `.env`. A missing optional setting uses
  its default. An invalid value stops the backend at start with a log line that names the
  setting and the allowed values, and a non-zero exit code.

  | Setting | Meaning | Default |
  |---|---|---|
  | `RRMC_IMPORT_DIR` | Folder on the computer for incoming images | `./source/import` |
  | `RRMC_DONE_DIR` | Folder on the computer for imported images | `./source/import_done` |
  | `RRMC_FAILED_DIR` | Folder on the computer for failed images | `./source/import_failed` |
  | `RRMC_ENGINES` | `real` (Tesseract and Ollama) or `fake` (deterministic fakes) | `real` |
  | `RRMC_OLLAMA_URL` | Ollama address seen from the container | `http://host.docker.internal:11434` |
  | `RRMC_MODEL` | Ollama model name (FR-29) | `qwen2.5:7b` (example; the model is chosen in the receipt-reading spec) |
  | `RRMC_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` or `ERROR` | `INFO` |
  | `RRMC_BACKEND_PORT` | Backend port on `127.0.0.1` | `8000` |
  | `RRMC_UI_PORT` | UI port on `127.0.0.1` | `5173` |

  Inside the backend container the three folders are always `/data/import`,
  `/data/import_done` and `/data/import_failed`; the settings choose which folders on the
  computer are mounted there.
- **PC4 Database.** The backend uses one SQLite database. It survives `docker compose down`,
  `docker compose up` and rebuilding the images, and is removed only by deleting its volume
  on purpose. On start, the backend creates the database if it does not exist and applies
  pending schema migrations in order, each in its own transaction, and records the applied
  version. If a migration fails, the backend does not start and the database stays at the
  last successful version. This spec adds the migration mechanism only, with no domain
  tables; feature specs add their tables as migrations.
- **PC5 Health endpoint.** `GET /api/health` returns 200 and:

  ```json
  {
    "status": "ok",
    "model_name": "qwen2.5:7b",
    "checks": {"database": "ok", "folders": "ok", "ocr": "ok", "model": "ok"}
  }
  ```

  | Check | Values |
  |---|---|
  | `database` | `ok`, `unavailable` |
  | `folders` | `ok`, `unavailable` (one of the three folders is missing or not writable) |
  | `ocr` | `ok`, `unavailable` (Tesseract cannot run, or `fin` or `eng` is missing) |
  | `model` | `ok`, `unavailable` (Ollama cannot be reached), `missing_model` (Ollama runs but `RRMC_MODEL` is not pulled) |

  `status` is `ok` when every check is `ok`, otherwise `degraded`. Checks run on each
  request, so starting Ollama later is noticed without restarting the backend. The response
  arrives within 3 seconds even when Ollama does not answer.
- **PC6 Model loading (FR-30).** With `RRMC_ENGINES=real`, the backend asks Ollama to load
  `RRMC_MODEL` and keep it loaded when the backend starts. If Ollama or the model is not
  available then, the backend still starts, and it asks again on the first health check
  that finds the model available.
- **PC7 Engine interfaces and fakes (NFR-13).** The backend has an `OcrEngine` interface
  (real: Tesseract) and a `ReceiptModel` interface (real: Ollama). This spec defines only
  their availability checks used by PC5 and PC6. Reading and parsing methods are added by
  the receipt-reading spec. With `RRMC_ENGINES=fake`, the fakes report `ok`, and no request
  is made to Ollama and Tesseract is not run.
- **PC8 Error format.** Every API error is JSON
  `{"error": "<code>", "message": "<Finnish text>"}`. This spec defines:

  | Situation | Status | `error` | `message` |
  |---|---|---|---|
  | Unknown `/api/...` path or missing id | 404 | `not_found` | `Pyydettyä kohdetta ei löydy.` |
  | Body or parameters not valid | 422 | `invalid_request` | `Pyyntö on virheellinen.` |
  | Unexpected error | 500 | `internal_error` | `Odottamaton virhe. Katso lisätiedot palvelimen lokista.` |

  Feature specs add their own codes in the same format.
- **PC9 Logging (NFR-3).** The backend logs to standard output at `RRMC_LOG_LEVEL`. Log lines
  contain the method, path, status and duration of each request, never request or response
  bodies. An unexpected error is logged with its stack trace, without the request body.
- **PC10 App shell (Finnish UI).** The UI shows a page with the heading `Kuittisovellus` and
  a status line that reads `GET /api/health` when the page opens and every 30 seconds:

  | Health result | Status line text |
  |---|---|
  | `status` `ok` | `Kaikki palvelut toiminnassa` |
  | `model` `unavailable` | `Ollamaan ei saada yhteyttä. Käynnistä Ollama.` |
  | `model` `missing_model` | `Mallia <model_name> ei ole ladattu. Lataa se komennolla: ollama pull <model_name>` |
  | `ocr` `unavailable` | `Tekstintunnistus ei ole käytettävissä.` |
  | `folders` `unavailable` | `Kuvakansioita ei löydy tai niihin ei voi kirjoittaa.` |
  | backend does not answer | `Taustapalveluun ei saada yhteyttä.` |

  When several checks fail, each text is shown. The shell has the navigation area where
  feature pages (first: `Tuotteet`) are added by their specs. All UI texts live in one file.
  A shared API client returns either the data or an error with the Finnish `message`, and
  `Taustapalveluun ei saada yhteyttä.` when the backend cannot be reached.
- **PC11 Developer commands.** Each command below runs in containers, needs nothing on the
  computer but Docker, and succeeds on the fresh scaffold:
  backend tests, backend lint and format check, backend type check (pyright, strict),
  frontend tests, frontend lint, frontend format check (Prettier), frontend type check
  (`tsc --noEmit`), E2E tests
  (Playwright, real backend with `RRMC_ENGINES=fake` and a temporary database).
  The exact commands are fixed in the plan and documented in `docs/development.md`;
  the Commands table in `AGENTS.md` is updated to match.
- **PC12 Version control hygiene (NFR-4).** `.env`, the database, `source/` and test output
  are ignored by Git. `.env.example` is committed.

### Out of Scope
- Domain tables, endpoints and pages (product management, receipts, totals, export).
- Import, OCR reading and parsing: only the interfaces' availability checks are here.
  Waiting for Ollama during import (rest of FR-31) is in the import spec.
- Choosing the model; `RRMC_MODEL` has an example value only.
- Running Ollama in a container, and Ollama's own settings (cloud features off is documented
  in `docs/development.md`, not enforced by the app).
- Backups of the database; HTTPS; login.
- CI on a server.

## Acceptance Criteria

### Start and network

#### AC1: The app starts from a fresh clone
**Given** a Windows computer with Docker Desktop, Git and Ollama, a fresh clone, and `.env`
copied from `.env.example` without changes
**When** the user runs `docker compose up` in the project root
**Then** within 5 minutes `http://127.0.0.1:8000/api/health` answers 200, and
`http://127.0.0.1:5173` shows the heading `Kuittisovellus`

#### AC2: Ports are bound to 127.0.0.1 only
**Given** the default `.env`
**When** the resolved Compose configuration is inspected
**Then** every published port of every service has host IP `127.0.0.1`: backend `8000`, UI
`5173`; with `RRMC_BACKEND_PORT=8100` and `RRMC_UI_PORT=5200` the ports are `8100` and `5200`

#### AC3: CORS allows only the UI origin
**Given** the backend runs with the default `.env`
**When** `GET /api/health` is sent with `Origin: http://127.0.0.1:5173`, and again with
`Origin: http://example.com`
**Then** the first response has `Access-Control-Allow-Origin: http://127.0.0.1:5173`; the
second has no `Access-Control-Allow-Origin` header

#### AC4: Source changes are picked up without restart
**Given** the app runs with `docker compose up`
**When** a backend source file and a frontend source file are changed and saved
**Then** within 10 seconds the backend serves the changed code and the browser shows the
changed UI, without `docker compose` commands

### Settings

#### AC5: Missing `.env` stops start
**Given** a fresh clone without `.env`
**When** the user runs `docker compose up`
**Then** no container starts and the output names the missing `.env` file

#### AC6: Defaults are used for missing optional settings
**Given** a `.env` that contains no `RRMC_*` settings
**When** the backend starts
**Then** the effective settings equal the defaults in PC3, and `model_name` in
`GET /api/health` is `qwen2.5:7b`

#### AC7: Invalid settings stop the backend
**Given** `.env` with `RRMC_ENGINES=both`, or with `RRMC_LOG_LEVEL=LOUD`, or with
`RRMC_OLLAMA_URL=not-a-url`
**When** the backend starts
**Then** it exits with a non-zero code, and its log contains one line naming the setting and
its allowed values (for example `Invalid setting RRMC_ENGINES: expected real or fake`)

### Database

#### AC8: The database is created and migrated on first start
**Given** no database
**When** the backend starts
**Then** the database exists, every migration has been applied once in order, and the
recorded schema version equals the newest migration

#### AC9: Migrations run once
**Given** a database at the newest version
**When** the backend restarts
**Then** no migration runs again and the schema version is unchanged

#### AC10: A failing migration leaves the database unchanged
**Given** a database at version N and a migration N+1 that fails
**When** the backend starts
**Then** it exits with a non-zero code, the schema version is still N, and no change made by
migration N+1 remains

#### AC11: Data survives restarts and rebuilds
**Given** a row written to the database
**When** the user runs `docker compose down`, then `docker compose up --build`
**Then** the row is still there

### Health and model

#### AC12: Health with fakes
**Given** `RRMC_ENGINES=fake` and the three folders exist
**When** `GET /api/health` is called
**Then** the response is 200 with `status` `ok` and every check `ok`, and no request is made
to Ollama and Tesseract is not run

#### AC13: Health with Tesseract
**Given** `RRMC_ENGINES=real` in the backend container
**When** `GET /api/health` is called
**Then** `checks.ocr` is `ok`; with the `fin` language data removed it is `unavailable`

#### AC14: Ollama not reachable
**Given** `RRMC_ENGINES=real` and nothing answers at `RRMC_OLLAMA_URL`, or it does not
answer at all
**When** `GET /api/health` is called
**Then** the response is 200 within 3 seconds with `status` `degraded` and `checks.model`
`unavailable`

#### AC15: Model not pulled
**Given** `RRMC_ENGINES=real`, Ollama answers, and its model list does not contain
`RRMC_MODEL`
**When** `GET /api/health` is called
**Then** `status` is `degraded` and `checks.model` is `missing_model`; a model listed as
`qwen2.5:7b` matches `RRMC_MODEL=qwen2.5:7b`, and one listed as `llama3:latest` matches
`RRMC_MODEL=llama3`

#### AC16: Folders missing or read-only
**Given** `/data/import_failed` does not exist, or `/data/import` is not writable
**When** `GET /api/health` is called
**Then** `checks.folders` is `unavailable` and `status` is `degraded`

#### AC17: The model is loaded at start
**Given** `RRMC_ENGINES=real` and Ollama has `RRMC_MODEL`
**When** the backend starts
**Then** exactly one load request for `RRMC_MODEL` that keeps the model loaded is sent to
Ollama before the first health check answers

#### AC18: The model is loaded when Ollama starts later
**Given** `RRMC_ENGINES=real` and Ollama was not reachable when the backend started
**When** Ollama becomes reachable with the model and `GET /api/health` is called twice
**Then** the first of these responses has `checks.model` `ok`, one load request is sent, and
the second response sends no further load request

### Errors and logging

#### AC19: Unknown path
**Given** the backend runs
**When** `GET /api/does-not-exist` is called
**Then** the response is 404 with `{"error": "not_found", "message": "Pyydettyä kohdetta ei löydy."}`

#### AC20: Invalid request
**Given** a test endpoint that expects a JSON body with an integer field
**When** it is called with `{"value": "abc"}`, and with a body that is not JSON
**Then** both responses are 422 with `{"error": "invalid_request", "message": "Pyyntö on virheellinen."}`

#### AC21: Unexpected error without receipt content
**Given** a test endpoint that raises an exception after reading a body containing
`SECRET-LINE-123`
**When** it is called
**Then** the response is 500 with `{"error": "internal_error", "message": "Odottamaton virhe. Katso lisätiedot palvelimen lokista."}`,
the log contains the stack trace, and neither the response nor the log contains
`SECRET-LINE-123`

#### AC22: Request logging
**Given** `RRMC_LOG_LEVEL=INFO`
**When** `GET /api/health` is called
**Then** one log line contains `GET`, `/api/health`, `200` and a duration in milliseconds;
with `RRMC_LOG_LEVEL=WARNING` no such line is written

### UI shell

#### AC23: Status line texts
**Given** the UI is open
**When** `GET /api/health` returns each result in the PC10 table, or the backend does not answer
**Then** the status line shows exactly the text in the table, with `<model_name>` replaced
by the returned model name; when `model` is `unavailable` and `folders` is `unavailable`,
both texts are shown

#### AC24: Status refreshes
**Given** the UI shows `Ollamaan ei saada yhteyttä. Käynnistä Ollama.`
**When** the health result changes to `ok` and 30 seconds pass
**Then** the status line shows `Kaikki palvelut toiminnassa` without reloading the page

#### AC25: The shell is in Finnish
**Given** the UI is open and the backend is healthy
**When** the page is rendered
**Then** the heading is `Kuittisovellus`, the browser tab title is `Kuittisovellus`, and no
English text is visible

### Tooling and hygiene

#### AC26: Developer commands succeed
**Given** a fresh clone with `.env` from `.env.example`, and Ollama not running
**When** each command in PC11 is run as documented in `docs/development.md`
**Then** each exits with code 0

#### AC27: Private files are ignored
**Given** the repository
**When** `git check-ignore` is run for `.env`, `source/import/a.jpg`,
`source/import_failed/a.jpg`, `data/rrmc.db` and `frontend/test-results/x`
**Then** each is ignored, and `.env.example` is not

## Files to Modify

Paths as fixed in the [Plan](#plan).

| File | Change |
|---|---|
| `compose.yaml` | New: services `backend`, `frontend`, profile `e2e` (`backend-e2e`, `e2e`); ports on `127.0.0.1`; mounts; volumes `rrmc-data`, `rrmc-node-modules` (P1) |
| `backend/Dockerfile` | New: Python 3.12, Tesseract with `fin` and `eng`, Node.js for pyright, uv (P2) |
| `frontend/Dockerfile` | New: Playwright image with Node.js and browsers (P4) |
| `.env.example` | New: every PC3 setting with its default and a comment |
| `.gitignore` | Update: `frontend/test-results/`, `frontend/playwright-report/`, coverage output, `.ruff_cache/` (PC12) |
| `backend/pyproject.toml`, `backend/uv.lock` | New: dependencies of P2; ruff and pyright settings per `docs/development.md#code-standards` |
| `backend/app/main.py` | New: app factory, CORS, error handlers, request logging, lifespan |
| `backend/app/settings.py`, `backend/app/prestart.py` | New: settings, validation, start checks (PC3, PC4) |
| `backend/app/storage/db.py`, `backend/app/storage/migrate.py`, `backend/app/storage/migrations/` | New: SQLite connection and migration runner (PC4) |
| `backend/app/engines/` | New: `ocr.py`, `model.py`, `factory.py` (PC6, PC7) |
| `backend/app/health/` | New: `routes.py`, `service.py`, `schemas.py` (PC5, PC6) |
| `backend/app/errors.py`, `backend/app/texts.py`, `backend/app/logging_setup.py` | New (PC8, PC9) |
| `backend/tests/unit/`, `backend/tests/integration/` | New: tests of the Testing Strategy |
| `frontend/` (Vite scaffold) | New: `package.json`, `package-lock.json`, `index.html`, `vite.config.ts`, `tsconfig*.json`, `eslint.config.js`, `.prettierrc`, `playwright.config.ts` (P4) |
| `frontend/src/api/client.ts`, `frontend/src/api/health.ts` | New: shared API client and health client |
| `frontend/src/App.tsx`, `frontend/src/components/StatusLine.tsx` | New: app shell and status line (PC10) |
| `frontend/src/i18n/fi.ts` | New: Finnish UI texts |
| `frontend/src/**/*.test.tsx`, `frontend/src/test/` (MSW setup), `frontend/e2e/` | New: component and E2E tests |
| `scripts/container-tests.ps1` | New: container tests (P6) |
| `docs/development.md` | Update: prerequisites (Docker Desktop, Git, Ollama with `OLLAMA_NO_CLOUD=1`, `ollama pull`), setup, the P5 commands in the Commands table, manual checks, troubleshooting; backend lock file `uv.lock`; backend text module `app/texts.py` |
| `docs/adr/0002-docker.md` | New (written in the Plan phase) |
| `docs/architecture.md` | Update: folder structure and file names as fixed in the plan (`storage/`, `engines/`, `health/`, `compose.yaml`) |
| `docs/datamodel.md` | New: `schema_version`; entities are added by feature specs |
| `docs/api-reference.md` | New: `GET /api/health`, error format |
| `docs/subsystems/storage/README.md`, `docs/subsystems/receipt-reading/README.md`, `docs/subsystems/ui/README.md` | New |
| `docs/content-plan.md` | Update statuses |
| `AGENTS.md` | Update: stack (Docker), planned layout, Commands table (mirrors development.md) |
| `specs/README.md` | Update status |

## Risk
- **What could break:** nothing existing (greenfield). Every later spec builds on this one.
- **SQLite on Windows mounts:** SQLite file locking is unreliable on folders shared from
  Windows into Linux containers. The database must therefore live in a Docker volume, not in
  a Windows folder; the plan must confirm this. Consequence: the database file is not visible
  in Windows Explorer, and backup needs a documented command (backups are out of scope).
- **File change detection:** changes on Windows folders mounted into containers may not
  raise file events, so reload may need polling (AC4), which uses some CPU.
- **`host.docker.internal`:** works on Docker Desktop for Windows; it would need extra
  Compose settings on Linux.
- **Image size and first start:** Tesseract, Node.js and Playwright browsers make the images
  large; the first `docker compose up` downloads and builds for several minutes (AC1 allows 5).
- **Rollback:** `docker compose down -v`, delete the images, revert the commit.
- **Dependencies:** Docker Desktop (WSL 2 backend), Git, Ollama on Windows.

## Testing Strategy (MANDATORY)

### Unit tests (backend, pytest)
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC6 | `Settings` | defaults | empty environment | load | values of PC3 | none |
| AC7 | `Settings` | invalid engines | `RRMC_ENGINES=both` | load | error naming `RRMC_ENGINES` and `real or fake` | none |
| AC7 | `Settings` | invalid log level | `RRMC_LOG_LEVEL=LOUD` | load | error naming the setting and the four levels | none |
| AC7 | `Settings` | invalid URL | `RRMC_OLLAMA_URL=not-a-url` | load | error naming the setting | none |
| AC8 | migration runner | first run | empty DB, migrations 1–2 | migrate | both applied in order; version 2 | temp SQLite |
| AC9 | migration runner | idempotent | DB at version 2 | migrate | nothing applied; version 2 | temp SQLite |
| AC10 | migration runner | failure | DB at version 1, migration 2 creates a table then fails | migrate | error raised; version 1; table absent | temp SQLite |
| AC12 | fake engines | availability | `fake` | check | `ok`; no subprocess, no HTTP | spy on subprocess and HTTP |
| AC13 | `TesseractEngine.check` | languages | `tesseract --list-langs` lists / lacks `fin` | check | `ok` / `unavailable` | fake subprocess |
| AC14 | `OllamaModel.check` | not reachable | connection refused; no answer for 10 s | check | `unavailable` within 3 s | fake HTTP |
| AC15 | `OllamaModel.check` | name matching | model list `["qwen2.5:7b", "llama3:latest"]` | check `qwen2.5:7b`, `llama3`, `mistral` | `ok`, `ok`, `missing_model` | fake HTTP |
| AC16 | folder check | missing / read-only | temp folders | check | `unavailable` | temp dirs |
| AC12, AC14 | `overall_status` | combination | checks all `ok`; one not `ok` | compute | `ok`; `degraded` | none |

### Integration tests (FastAPI TestClient, temporary SQLite file)
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC3 | CORS allowed | `GET /api/health`, `Origin: http://127.0.0.1:5173` | `Access-Control-Allow-Origin` echoes origin | 200 |
| AC3 | CORS refused | `GET /api/health`, `Origin: http://example.com` | no `Access-Control-Allow-Origin` | 200 |
| AC12 | health with fakes | `GET /api/health` | `status` `ok`, all checks `ok`, `model_name` | 200 |
| AC14 | Ollama down | `GET /api/health`, fake HTTP refuses | `degraded`, `model` `unavailable`, under 3 s | 200 |
| AC15 | model missing | `GET /api/health`, fake model list without the model | `degraded`, `missing_model` | 200 |
| AC16 | folder missing | `GET /api/health` with `/data/import_failed` absent | `folders` `unavailable` | 200 |
| AC17 | load at start | start app with fake Ollama that has the model | one load request with keep-alive before first health answer | — |
| AC18 | load later | start with Ollama down; then up; two health calls | first `ok`; one load request in total | 200 |
| AC19 | unknown path | `GET /api/does-not-exist` | `not_found` body | 404 |
| AC20 | invalid request | test endpoint, `{"value": "abc"}`; non-JSON body | `invalid_request` body | 422 |
| AC21 | unexpected error | test endpoint raising, body with `SECRET-LINE-123` | `internal_error` body; marker absent from response and captured log; stack trace in log | 500 |
| AC22 | request log | `GET /api/health` at `INFO` and at `WARNING` | one line with method, path, status, ms; none at `WARNING` | 200 |
| AC8, AC9 | startup migration | start app twice on the same temp DB | version newest; second start applies nothing | — |

### Container tests (run on the computer with Docker)
| AC | Scenario | Command / input | Expected output |
|---|---|---|---|
| AC2 | port binding | `docker compose config` with default `.env`; with ports `8100`/`5200` | all published ports `127.0.0.1`; `8000`/`5173`, then `8100`/`5200` |
| AC5 | missing `.env` | `docker compose up` without `.env` | non-zero exit; output names `.env`; no container created |
| AC7 | invalid setting | `docker compose up backend` with `RRMC_ENGINES=both` | backend exits non-zero; log line names the setting |
| AC11 | persistence | write a row; `down`; `up --build`; read | row present |
| AC13 | Tesseract in image | `GET /api/health` with `RRMC_ENGINES=real` and Ollama off | `ocr` `ok`, `model` `unavailable` |
| AC26 | developer commands | run each PC11 command on a fresh clone | each exits 0 |
| AC27 | ignore rules | `git check-ignore` for the AC27 paths and `.env.example` | five ignored; `.env.example` not ignored |

### Component tests (Vitest + React Testing Library, API mocked with MSW)
| AC | Component | Case | Given | When | Then |
|---|---|---|---|---|---|
| AC23 | StatusLine | each result | MSW returns each PC10 result | render | exact text per row; `<model_name>` filled in |
| AC23 | StatusLine | two failures | `model` and `folders` `unavailable` | render | both texts |
| AC23 | StatusLine | backend down | network error | render | `Taustapalveluun ei saada yhteyttä.` |
| AC24 | StatusLine | refresh | first `unavailable`, then `ok` | advance fake timers 30 s | `Kaikki palvelut toiminnassa` |
| AC25 | App | Finnish shell | healthy | render | heading `Kuittisovellus`; no English text |
| AC23 | API client | error mapping | 404 with error body; network error | call | error carries `message`; network error message |

### E2E tests (Playwright, real backend with `RRMC_ENGINES=fake`, temporary database)
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC1, AC25 | open the app | 1. open the UI | heading and tab title `Kuittisovellus`; status `Kaikki palvelut toiminnassa` |

### Manual checks (documented in `docs/development.md`, run once on the user's computer)
| AC | Check | Expected outcome |
|---|---|---|
| AC1 | fresh clone on Windows, `docker compose up` with Ollama running | health 200 and UI heading within 5 minutes |
| AC4 | edit a backend and a frontend file while running | changes visible within 10 seconds |

AC4 is manual because it depends on file events between Windows and the containers, which a
test inside a container cannot reproduce.

### Coverage target
- Backend: 90 % lines for settings, migrations, health, engines' checks and error handling;
  every branch of settings validation, the migration runner and the status calculation.
- Frontend: 80 % lines for the API client, StatusLine and App.

### Test data
- No receipt data. Migration tests use throwaway test migrations.
- Ollama is replaced by a fake HTTP server or client in unit and integration tests; Tesseract
  by a fake subprocess, except in the AC13 container test.
- Each backend test uses its own temporary SQLite file and temporary folders.

## Related Documentation (MANDATORY)
- PRD: [specs/PRD.md](../PRD.md) FR-29–FR-32, sections 7.1, 7.4 and 7.5
- Tier 1: [architecture.md](../../docs/architecture.md),
  [projectdescription.md](../../docs/projectdescription.md); to be written in this feature:
  `docs/development.md`, `docs/datamodel.md`, `docs/api-reference.md`
- Tier 2: storage, receipt-reading and ui subsystem READMEs (to be written in this feature)
- ADRs: [0001 Technology stack](../../docs/adr/0001-tech-stack.md); `0002-docker.md` to be
  written in this feature
- Development rules: [AGENTS.md](../../AGENTS.md); workflows: `.agents/skills/spec/SKILL.md`,
  `.agents/skills/tdd/SKILL.md`

## Open Questions
None. Resolved 2026-10-23:
- One way of running for normal use and development: the UI is served by the Vite dev
  server (see Decisions).
- PRD FR-32, NFR-10 and NFR-11, `docs/architecture.md` and the product management spec were
  updated for Docker and `.env` before review.

## Plan

Approved spec: 2026-10-26. This plan follows the code standards in
[docs/development.md](../../docs/development.md#code-standards) and the Guardrails in
[AGENTS.md](../../AGENTS.md#guardrails).

### P1 Containers and Compose (PC1, PC2, PC4, PC12)

`compose.yaml`, project name `rrmc`:

| Service | Image | Command | Ports | Mounts |
|---|---|---|---|---|
| `backend` | `backend/Dockerfile` | `python -m app.prestart && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --no-access-log` | `127.0.0.1:${RRMC_BACKEND_PORT:-8000}:8000` | `./backend:/app`; `${RRMC_IMPORT_DIR:-./source/import}:/data/import`; same for `import_done`, `import_failed`; named volume `rrmc-data:/data/db` |
| `frontend` | `frontend/Dockerfile` | `npm run dev` (Vite on `0.0.0.0:5173`) | `127.0.0.1:${RRMC_UI_PORT:-5173}:5173` | `./frontend:/app`; named volume `rrmc-node-modules:/app/node_modules` |
| `backend-e2e` (profile `e2e`) | backend image | as `backend`, with `RRMC_ENGINES=fake` and `/data` on `tmpfs` | none | `./backend:/app` |
| `e2e` (profile `e2e`) | frontend image | `npx playwright test` | none | `./frontend:/app`, node modules volume |

- **Settings file:** both app services use `env_file: {path: "${RRMC_ENV_FILE:-.env}", required: true}`.
  A missing file stops Compose before any container starts (AC5). Compose reads the same
  `.env` for the port and folder variables. `RRMC_ENV_FILE` lets container tests use their
  own temporary settings file, so `.env` is never touched (Guardrails).
- **Inside the container the backend listens on `0.0.0.0`;** only the published ports decide
  reachability, and they are bound to `127.0.0.1` (AC2).
- **Ollama:** `extra_hosts: ["host.docker.internal:host-gateway"]` on the backend, so the
  default URL also works outside Docker Desktop.
- **Reload on Windows mounts (AC4):** `WATCHFILES_FORCE_POLLING=true` for Uvicorn; Vite
  `server.watch.usePolling` when `VITE_USE_POLLING=true` (set in Compose).
- **API calls from the UI** go to the same origin `/api`, which Vite proxies to
  `http://backend:8000` (`VITE_API_TARGET`, default `http://backend:8000`; `backend-e2e`
  for E2E). The backend still sends CORS headers only for `http://127.0.0.1:${RRMC_UI_PORT}` (AC3).
- **Database:** `/data/db/rrmc.db` in the `rrmc-data` volume, not a Windows folder (spec Risk).
  `docker compose down` and `up --build` keep it (AC11). Deleting it needs
  `docker compose down -v`, which only the user runs.
- **Why `prestart`:** with `--reload`, Uvicorn's reloader stays alive when the app fails, so
  the container would not exit. `app.prestart` validates settings and runs migrations first
  and exits non-zero on failure, so the container stops (AC7, AC10).

### P2 Backend image and dependencies

`backend/Dockerfile`: `python:3.12-slim-bookworm`; apt `tesseract-ocr`, `tesseract-ocr-fin`,
`tesseract-ocr-eng` (Tesseract 5.3) and `nodejs` (for pyright); `uv` copied from its official
image. Dependencies are installed from `uv.lock` into the image, development tools included,
because there is one way of running.

| Dependency | Why |
|---|---|
| `fastapi`, `uvicorn[standard]` | Stack (ADR 0001); `standard` brings `watchfiles` for reload |
| `pydantic-settings` | Reads `RRMC_*` from the environment with typed validation (PC3) |
| `httpx` | Ollama client and FastAPI `TestClient`; `httpx.MockTransport` fakes Ollama in tests, so no extra mock library |
| dev: `pytest`, `pytest-cov`, `ruff`, `pyright` | Tests, coverage, lint and format, strict type check |

Lock file: **`uv.lock`** (the choice left open in development.md). Migrations use the
standard `sqlite3` module and a small runner, not Alembic: numbered SQL files are enough for
one local database and match the development.md rule.

### P3 Backend modules

| Module | Contents | PC |
|---|---|---|
| `app/settings.py` | `Settings(BaseSettings)`, prefix `RRMC_`: `engines: Literal["real","fake"]`, `ollama_url: HttpUrl`, `model: str` (non-empty), `log_level: Literal[...]`, `ui_port: int`, `data_dir: Path = /data`. Folder paths are derived: `data_dir/import`, `/import_done`, `/import_failed`, `/db/rrmc.db`. `RRMC_IMPORT_DIR` etc. are host paths for Compose and are not read by the backend. `load_settings()` turns a validation error into `SettingsError` with the line `Invalid setting RRMC_<NAME>: expected <allowed>` | PC3 |
| `app/prestart.py` | `python -m app.prestart`: load settings, configure logging, run migrations; on `SettingsError` or migration failure log one line and exit 1 | PC3, PC4 |
| `app/storage/db.py` | `connect(path)`: `sqlite3` connection, `foreign_keys=ON`, `journal_mode=WAL`, row factory | PC4 |
| `app/storage/migrate.py`, `app/storage/migrations/` | Applies `NNNN_name.sql` files with a number above the stored version, each in its own transaction, then records it in `schema_version(version INTEGER PRIMARY KEY, applied_at TEXT)`. The folder is empty in this feature: version 0 | PC4 |
| `app/engines/ocr.py` | `OcrEngine` Protocol with `check() -> CheckResult`; `TesseractOcrEngine` runs `tesseract --list-langs` (timeout 5 s) and requires `fin` and `eng`; `FakeOcrEngine` returns `ok` | PC7 |
| `app/engines/model.py` | `ReceiptModel` Protocol with `check()` and `load()`; `OllamaReceiptModel` uses `GET /api/tags` (timeout 2 s) and `POST /api/generate {"model", "keep_alive": -1}`; a listed `name:latest` matches `name`; `FakeReceiptModel` returns `ok` and makes no calls | PC6, PC7 |
| `app/engines/factory.py` | Builds the real or fake pair from `settings.engines` | PC7 |
| `app/health/service.py`, `schemas.py`, `routes.py` | Checks database (`SELECT 1`), folders (exist and writable, `os.access`), OCR and model; overall `ok`/`degraded`; `ModelLoader` (states `not_loaded`, `loading`, `loaded`) sends `load()` in a background thread at startup and on the first health check that finds the model `ok` while `not_loaded`; a failed load goes back to `not_loaded` with a warning log | PC5, PC6 |
| `app/errors.py` | `AppError(code, message, status)`; handlers for `AppError`, 404, `RequestValidationError` (→ `invalid_request`) and `Exception` (→ `internal_error`, logged with `logger.exception`) | PC8 |
| `app/texts.py` | The backend text module: Finnish error messages | PC8 |
| `app/logging_setup.py` | Standard `logging` to stdout at `RRMC_LOG_LEVEL`; middleware logs `GET /api/health 200 12ms` at `INFO` (method, path without query string, status, duration); no bodies | PC9 |
| `app/main.py` | `create_app(settings=None, extra_routers=())`: settings, logging, CORS (`http://127.0.0.1:{ui_port}` only), error handlers, request logging, routers, lifespan (migrations, `ModelLoader.start()`); `app = create_app()` for Uvicorn. `extra_routers` lets tests add the test-only endpoints of AC20 and AC21; production has no test endpoints | all |

`app/engines/` is a shared adapter package used by receipt-reading and categorization; the
reading and parsing methods are added there by their specs. Health is its own small package
because it reads every check.

### P4 Frontend

`frontend/Dockerfile`: `mcr.microsoft.com/playwright` image (Node.js and browsers in one
image), with the tag matching the `@playwright/test` version in `package-lock.json`.

| Dependency | Why |
|---|---|
| `react`, `react-dom` | Stack |
| dev: `vite`, `@vitejs/plugin-react`, `typescript` | Build tool and language |
| dev: `vitest`, `@vitest/coverage-v8`, `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, `msw` | Component tests (NFR-14) |
| dev: `@playwright/test` | E2E |
| dev: `eslint`, `typescript-eslint`, `eslint-plugin-react-hooks`, `eslint-plugin-jsx-a11y`, `prettier`, `eslint-config-prettier` | Lint and format per development.md |

No router library yet: the shell has one page. The navigation area is a `<nav>` that feature
specs fill; the product management plan decides whether a router is added.

| File | Contents | PC |
|---|---|---|
| `src/api/client.ts` | `apiGet<T>(path)` and friends: return `{ok: true, data}` or `{ok: false, error: {code, message}}`; network failure → code `network_error` with `Taustapalveluun ei saada yhteyttä.` | PC10 |
| `src/api/health.ts` | `getHealth()` and the `Health` type mirroring the backend schema | PC10 |
| `src/components/StatusLine.tsx` | Calls `getHealth()` on mount and every 30 s (`setInterval`, cleared on unmount); maps checks to texts in the PC10 order: model, ocr, folders | PC10 |
| `src/App.tsx` | Heading `Kuittisovellus`, `<nav>`, `StatusLine` | PC10 |
| `src/i18n/fi.ts` | All UI texts, including the template `Mallia {model} ei ole ladattu...` | PC10 |
| `index.html` | `<html lang="fi">`, `<title>Kuittisovellus</title>` | PC10 |
| `vite.config.ts`, `playwright.config.ts`, `eslint.config.js`, `.prettierrc`, `tsconfig*.json` | Proxy, polling, test and lint settings | PC1, PC11 |

### P5 Developer commands (PC11)

Run from the project root on Windows (PowerShell or any shell). `run --rm` starts a
one-off container with the mounts but without published ports.

| Task | Command |
|---|---|
| Start the app | `docker compose up --build` (first time), then `docker compose up` |
| Backend tests | `docker compose run --rm backend pytest` |
| Backend lint and format check | `docker compose run --rm backend sh -c "ruff check . && ruff format --check ."` |
| Backend type check | `docker compose run --rm backend pyright` |
| Frontend tests | `docker compose run --rm frontend npm test` |
| Frontend lint | `docker compose run --rm frontend npm run lint` |
| Frontend format check | `docker compose run --rm frontend npm run format:check` |
| Frontend type check | `docker compose run --rm frontend npm run typecheck` |
| E2E tests | `docker compose --profile e2e run --rm e2e` |
| Container tests | `pwsh ./scripts/container-tests.ps1` (or `powershell -File ...`) |

### P6 Container tests

`scripts/container-tests.ps1` runs the container-level ACs against a separate Compose
project `rrmc-test` with its own temporary settings file (`RRMC_ENV_FILE`) and its own
volume, so the real app, `.env` and the real database are never touched:

| AC | Check |
|---|---|
| AC2 | `docker compose config --format json`: every published port has `host_ip` `127.0.0.1`; default ports, then `8100`/`5200` |
| AC5 | `RRMC_ENV_FILE=does-not-exist.env docker compose up`: non-zero exit, output names the file, `docker compose ps -a` empty |
| AC7 | settings file with `RRMC_ENGINES=both`: `up backend` exits non-zero; log has `Invalid setting RRMC_ENGINES` |
| AC11 | write a row in a test table through `docker compose exec`; `down`; `up --build`; read it back |
| AC13 | `RRMC_ENGINES=real`, Ollama URL pointing to a closed port: health `ocr` `ok`, `model` `unavailable` |
| AC27 | `git check-ignore` for the AC27 paths and `.env.example` |

The script stops the `rrmc-test` containers at the end but does not delete its volume
(Guardrails); it prints the cleanup command for the user.

### P7 Data model

Only `schema_version`. `docs/datamodel.md` describes it and how feature specs add tables.

### P8 Decisions recorded

- [ADR 0002: Docker for running and development](../../docs/adr/0002-docker.md): Docker
  Compose, Ollama on Windows, settings in `.env`, database in a Docker volume, one way of
  running.
- Smaller choices in this plan (uv, own migration runner, no router yet, Playwright image)
  are recorded here, not as ADRs.

### P9 AC coverage

| AC | Covered by |
|---|---|
| AC1 | P1, P4; E2E and manual check |
| AC2, AC5, AC11, AC27 | P1, P6 |
| AC3 | P3 `main.py` CORS |
| AC4 | P1 polling; manual check |
| AC6, AC7 | P3 `settings.py`, `prestart.py`; P6 |
| AC8–AC10 | P3 `storage/migrate.py`, `prestart.py` |
| AC12–AC18 | P3 `engines/`, `health/` |
| AC19–AC21 | P3 `errors.py`, `texts.py`, test-only routers |
| AC22 | P3 `logging_setup.py` |
| AC23–AC25 | P4 |
| AC26 | P5 |

## Tasks

Plan approved: 2026-10-26. Each task follows Red → Green → Refactor (`.agents/skills/tdd/SKILL.md`)
and ends with the tests, lint, format and type checks of the part it touched passing.
Commands are the P5 commands; until Compose exists (T2), backend checks run in the backend
image with `docker build` and `docker run`.

### Repository and backend base

- [ ] **T1 Version control hygiene** (AC27). Update `.gitignore` (P1, PC12) and add
  `.env.example` with every PC3 setting, default and comment.
  Proof: `git check-ignore` lists the five AC27 paths and not `.env.example`.
- [ ] **T2 Backend image and project** (AC26 backend part). `backend/Dockerfile`,
  `pyproject.toml` with ruff and pyright settings, `uv.lock`, empty `app` package, a minimal
  `compose.yaml` with the `backend` service (build, `env_file`, `./backend:/app`).
  Proof: `docker compose run --rm backend pytest` (one placeholder test, removed in T3),
  ruff and pyright pass; `tesseract --list-langs` in the container lists `fin` and `eng`.
- [ ] **T3 Settings** (AC6, AC7). `app/settings.py`, `load_settings()`, `SettingsError`.
  Proof: unit tests `test_ac6_defaults`, `test_ac7_invalid_engines`,
  `test_ac7_invalid_log_level`, `test_ac7_invalid_ollama_url`.
- [ ] **T4 Migration runner** (AC8, AC9, AC10). `app/storage/db.py`, `app/storage/migrate.py`,
  empty `app/storage/migrations/`.
  Proof: unit tests with throwaway migrations: first run, second run, failing migration.
- [ ] **T5 Prestart** (AC7, AC10). `app/prestart.py`: settings, logging, migrations; one log
  line and exit 1 on failure.
  Proof: unit tests calling `main()` with invalid settings and with a failing migration
  assert exit code 1 and the log line.

### Backend API

- [ ] **T6 App factory, errors and texts** (AC19, AC20, AC21). `app/main.py`
  (`create_app`, `extra_routers`), `app/errors.py`, `app/texts.py`; test-only routers in
  `tests/integration/`.
  Proof: integration tests for unknown path, invalid body and non-JSON body, unexpected
  error with `SECRET-LINE-123` absent from response and captured log.
- [ ] **T7 Request logging** (AC22). `app/logging_setup.py`, middleware.
  Proof: integration test with `caplog` at `INFO` and `WARNING`.
- [ ] **T8 CORS** (AC3). CORS for `http://127.0.0.1:{ui_port}` only.
  Proof: integration tests with the allowed and a foreign `Origin`.
- [ ] **T9 Engines** (AC12, AC13, AC14, AC15). `app/engines/ocr.py`, `model.py`,
  `factory.py` with real and fake implementations.
  Proof: unit tests with a fake subprocess (`--list-langs` with and without `fin`), an
  `httpx.MockTransport` (refused, no answer for 10 s → `unavailable` within 3 s, model list
  matching), and spies proving the fakes make no calls.
- [ ] **T10 Health endpoint** (AC12, AC14, AC15, AC16). `app/health/` package: database,
  folders, OCR and model checks, overall status.
  Proof: unit tests of `overall_status` and the folder check; integration tests of
  `GET /api/health` for fakes, Ollama down, model missing and folder missing.
- [ ] **T11 Model loading** (AC17, AC18). `ModelLoader` in `app/health/service.py`, started
  in the lifespan.
  Proof: integration tests with a mock Ollama counting load requests: one at start; with
  Ollama down at start, one after it comes up and none on the second health call.
- [ ] **T12 Startup migrations** (AC8, AC9). Lifespan runs migrations.
  Proof: integration test starting the app twice on one temporary database.

### Containers

- [ ] **T13 Full backend service** (AC1 backend part, AC2, AC11). Complete `compose.yaml`
  for `backend`: `prestart` command, ports on `127.0.0.1`, folder mounts, `rrmc-data` volume,
  `extra_hosts`, `WATCHFILES_FORCE_POLLING`.
  Proof: `docker compose up backend`; `GET http://127.0.0.1:8000/api/health` answers 200.

### Frontend

- [ ] **T14 Frontend scaffold** (AC26 frontend part). `frontend/Dockerfile`, Vite + React +
  TypeScript, ESLint, Prettier, Vitest with MSW setup, Playwright config, `frontend` service
  in Compose with the `/api` proxy, polling and node modules volume.
  Proof: frontend tests (one placeholder, removed in T15), lint, format check and type check
  pass; `http://127.0.0.1:5173` opens.
- [ ] **T15 API client and health client** (AC23 error mapping). `src/api/client.ts`,
  `src/api/health.ts`.
  Proof: component-level tests with MSW: success, 404 error body, network error.
- [ ] **T16 Status line** (AC23, AC24). `src/components/StatusLine.tsx`, texts in
  `src/i18n/fi.ts`.
  Proof: tests for each PC10 row, two failures, backend down, and a 30 s refresh with fake
  timers.
- [ ] **T17 App shell** (AC25). `src/App.tsx`, `index.html` (`lang="fi"`, title).
  Proof: test for the heading, the title and no English text.

### End-to-end and container tests

- [ ] **T18 E2E** (AC1, AC25). Profile `e2e` with `backend-e2e` and `e2e`; test in
  `frontend/e2e/`.
  Proof: `docker compose --profile e2e run --rm e2e` passes.
- [ ] **T19 Container tests** (AC2, AC5, AC7, AC11, AC13, AC27). `scripts/container-tests.ps1`
  with Compose project `rrmc-test` and a temporary settings file.
  Proof: the script passes on the user's computer and prints the cleanup command.

### Documentation and final check

- [ ] **T20 Documentation.** `docs/development.md` (setup, prerequisites with
  `OLLAMA_NO_CLOUD=1` and `ollama pull`, the P5 commands marked verified, manual checks,
  troubleshooting, `uv.lock`, `app/texts.py`), `AGENTS.md` (stack, layout, Commands table),
  `docs/architecture.md`, `docs/datamodel.md`, `docs/api-reference.md`, the storage,
  receipt-reading and ui subsystem READMEs, `docs/content-plan.md`, `specs/README.md`.
  Proof: every link resolves; the Commands tables in `development.md` and `AGENTS.md` match.
- [ ] **T21 Final check** (AC1, AC4, AC26). On the user's computer: fresh clone, `.env` from
  `.env.example`, `docker compose up --build`; the two manual checks; every P5 command exits
  0; coverage targets met.
  Proof: command output recorded in the review; then hand over to `review-audit`.
