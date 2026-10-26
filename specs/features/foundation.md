# Feature: Project foundation

## Overview
- **Status:** Review
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

Exact paths are fixed in the Plan phase.

| File | Change |
|---|---|
| `compose.yaml` | New: `backend` and `frontend` services, ports on `127.0.0.1`, mounts, database volume (PC1, PC2, PC4) |
| `backend/Dockerfile` | New: Python, Tesseract with `fin` and `eng`, Node.js for pyright |
| `frontend/Dockerfile` | New: Node.js for Vite, Vitest and Playwright |
| `.env.example` | New: every PC3 setting with its default and a comment |
| `.gitignore` | Update: test output, anything else PC12 needs |
| `backend/pyproject.toml` | New: dependencies (FastAPI, Uvicorn, settings library, HTTP client, pytest, ruff, pyright); ruff and pyright settings per `docs/development.md#code-standards` |
| `backend/app/main.py` | New: app factory, CORS, error handlers, request logging, startup (settings, migrations, model load) |
| `backend/app/settings.py` | New: settings and validation (PC3) |
| `backend/app/db.py`, `backend/app/migrations/` | New: SQLite connection and migration runner (PC4) |
| `backend/app/health.py` | New: health endpoint and checks (PC5) |
| `backend/app/engines/` | New: `OcrEngine`, `ReceiptModel`, real and fake implementations with availability checks (PC6, PC7) |
| `backend/tests/` | New: unit and integration tests |
| `frontend/` (Vite scaffold) | New: React + TypeScript (strict), ESLint, Prettier, `eslint-config-prettier`, Vitest, Testing Library, MSW, Playwright; settings per `docs/development.md#code-standards` |
| `frontend/src/api/client.ts`, `frontend/src/api/health.ts` | New: shared API client and health client |
| `frontend/src/App.tsx`, `frontend/src/components/StatusLine.tsx` | New: app shell and status line (PC10) |
| `frontend/src/i18n/fi.ts` | New: Finnish UI texts |
| `frontend/e2e/` | New: E2E test of the shell |
| `docs/development.md` | New: prerequisites (Docker Desktop, Git, Ollama with cloud features off, `ollama pull`), setup, commands, troubleshooting |
| `docs/adr/0002-docker.md` | New: Docker for running and developing; Ollama on Windows |
| `docs/architecture.md` | Update: folder structure and file names as fixed in the plan |
| `docs/datamodel.md` | New: schema version table; entities are added by feature specs |
| `docs/api-reference.md` | New: `GET /api/health`, error format |
| `docs/subsystems/storage/README.md`, `docs/subsystems/receipt-reading/README.md`, `docs/subsystems/ui/README.md` | New |
| `docs/content-plan.md` | Update statuses |
| `AGENTS.md` | Update: stack (Docker), planned layout, Commands table |
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
