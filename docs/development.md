# Development Guide

- **Status:** In Progress (setup, commands and code standards written; the manual checks of
  the foundation spec passed on a fresh clone on 2026-10-27)
- **Updated:** 2026-10-27

## Overview

How to install, run and work on RRMCApplication: setup, commands and code standards. The
system's structure and boundaries are in [architecture.md](architecture.md); development
rules, SDD and TDD are in [AGENTS.md](../AGENTS.md). Why everything runs in Docker is in
[ADR 0002](adr/0002-docker.md).

## Setup

Prerequisites on Windows: **Docker Desktop** (WSL 2 backend), **Git** and **Ollama**.
Python, Node.js and Tesseract run in the containers; do not install them for this project.

1. Turn off Ollama's cloud features so receipts never leave the computer. Set the user
   environment variable `OLLAMA_NO_CLOUD=1`, then restart Ollama:

   ```powershell
   [Environment]::SetEnvironmentVariable("OLLAMA_NO_CLOUD", "1", "User")
   ```

2. Pull the model named in `RRMC_MODEL` (default `qwen2.5:7b`):

   ```powershell
   ollama pull qwen2.5:7b
   ```

3. Create the settings file from the example. Change values in `.env` only; it is not
   committed. Every setting is explained in [.env.example](../.env.example).

   ```powershell
   Copy-Item .env.example .env
   ```

4. Build and start the app. The first build downloads several gigabytes and takes minutes.

   ```powershell
   docker compose up --build
   ```

Open the UI at <http://127.0.0.1:5173>. The status line under the heading tells whether
the database, the image folders, Tesseract and the model are available. The backend API is
at <http://127.0.0.1:8000/api/health>.

## Running the app

| Task | Command |
|---|---|
| Start (after the first build) | `docker compose up` |
| Start in the background | `docker compose up -d` |
| Stop | `docker compose down` |
| Follow the backend log | `docker compose logs -f backend` |

- Source changes in `backend/` and `frontend/` are picked up without a restart. The
  containers poll for changes, because file events from Windows folders do not reach them.
- The backend runs `python -m app.prestart` before Uvicorn. It validates the settings and
  applies database migrations; on failure it logs one line and the container stops.
- The database is in the Docker volume `rrmc_rrmc-data`, not in a Windows folder. It survives
  `down`, `up` and rebuilds. Only `docker compose down -v` deletes it: never run that unless
  you mean to delete all receipt data.
- The import folders are the Windows folders in `RRMC_IMPORT_DIR`, `RRMC_DONE_DIR` and
  `RRMC_FAILED_DIR`, mounted into the backend container as `/data/import`,
  `/data/import_done` and `/data/import_failed`.

## Commands

This table is the source of truth; the Commands table in [AGENTS.md](../AGENTS.md#commands)
mirrors it. Run the commands from the project root in PowerShell. Each one runs in a
one-off container and needs nothing on the computer but Docker and `.env`. All were run on
2026-10-26 with the result shown.

| Task | Command | Status |
|---|---|---|
| Backend tests | `docker compose run --rm backend pytest` | verified |
| Backend lint and format check | `docker compose run --rm backend sh -c "ruff check . && ruff format --check ."` | verified |
| Backend type check | `docker compose run --rm backend pyright` | verified |
| Frontend tests | `docker compose run --rm frontend npm test` | verified |
| Frontend lint | `docker compose run --rm frontend npm run lint` | verified |
| Frontend format check | `docker compose run --rm frontend npm run format:check` | verified |
| Frontend type check | `docker compose run --rm frontend npm run typecheck` | verified |
| E2E tests | `docker compose --profile e2e run --rm e2e` | verified |
| Container tests | `powershell -ExecutionPolicy Bypass -File scripts/container-tests.ps1` | verified |

Before declaring work done, run the tests, lint, format check and type check for every part
you changed.

Useful variants:

```powershell
# Backend tests with line and branch coverage
docker compose run --rm backend pytest --cov=app --cov=evaluation --cov-branch --cov-report=term-missing
# Tests that need the real Tesseract (left out of the default run)
docker compose run --rm backend pytest -m tesseract
# Frontend tests with coverage
docker compose run --rm frontend npm run test:coverage
# Format the code instead of checking it
docker compose run --rm backend ruff format .
docker compose run --rm frontend npm run format
```

### E2E tests

The E2E tests start `backend-e2e`, a backend with `RRMC_ENGINES=fake` and a temporary `/data`
(new empty database and folders each time the container starts), and run Playwright in the
`e2e` container, which starts its own Vite server. `run --rm` leaves `backend-e2e` running,
so a second run reuses its database; the journeys are written to pass either way. Stop it
with:

```powershell
docker compose --profile e2e down
```

The E2E backend's import folder is the test-only volume `rrmc-e2e-import`, also mounted in
the `e2e` container at `E2E_IMPORT_DIR`. The import journey (@frontend/e2e/import.spec.ts)
empties it and writes synthetic files there. It is never the real import folder.

### Container tests

`scripts/container-tests.ps1` checks what only a running Docker setup can show: ports bound
to `127.0.0.1`, start refused without a settings file, an invalid setting stopping the
backend, data surviving a rebuild, Tesseract in the image, and the Git ignore rules. It uses
a separate Compose project `rrmc-test` with its own settings, ports (`18000`, `15173`) and
folders under `%TEMP%\rrmc-container-tests`, so the real app, `.env` and the real database
are never touched. It deletes nothing; at the end it prints the cleanup command:

```powershell
docker compose -p rrmc-test down -v --rmi local
```

### Manual checks

Run these once on a fresh clone, and again when `compose.yaml` or a Dockerfile changes.

| Check | Steps | Expected outcome |
|---|---|---|
| Fresh start (AC1) | Clone, `Copy-Item .env.example .env`, Ollama running, `docker compose up --build` | Within 5 minutes <http://127.0.0.1:8000/api/health> answers and <http://127.0.0.1:5173> shows `Kuittisovellus` |
| Reload (AC4) | With the app running, change and save a backend source file and a frontend source file | Within 10 seconds the backend serves the change and the browser shows it, without `docker compose` commands |

### Model evaluation

`backend/evaluation/` is a development tool that compares ways of reading receipts on the
user's own receipts ([spec](../specs/features/model-evaluation.md)). It runs in the `eval`
service. The evaluation folder is `RRMC_EVAL_DIR` (default `./source/eval`), mounted as
`/data/eval`; it is ignored by Git.

1. Copy receipt images (JPEG or PNG) into the evaluation folder.
2. Create a truth file template next to each image:

   ```powershell
   docker compose --profile eval run --rm eval python -m evaluation init
   ```

3. Fill in each `<image>.truth.json` from the paper receipt: `store`, `date`
   (`YYYY-MM-DD`), `total_cents` and `line_count`. Optionally fill `lines` with
   `{"name": "...", "amount_cents": 125}` items to put the receipt in the full subset:
   discounts and deposits merged into the item, a deposit refund as its own negative line.
   Images without a filled truth file are skipped.
4. Pull the models (`ollama pull <name>`) and run one or more variants. `--limit N` and
   `--subset full` apply to the variant just before them:

   ```powershell
   docker compose --profile eval run --rm eval python -m evaluation run `
     --variant ocr:qwen2.5:7b `
     --variant vision:qwen2.5vl:7b --limit 5
   ```

The run prints one progress line per receipt and a summary table at the end, and writes it
under `results/<run id>/` in the evaluation folder: `summary.md`, one folder per variant
with a detail file per receipt (`ocr-qwen2.5-7b/1.json`), and `receipts.json`, which maps
the numbers to file names. Images are turned upright before reading: `ocr:` variants
from the EXIF orientation tag and then from Tesseract's orientation detection, which needs
about 20 lines of text to be sure enough; `vision:` variants from the EXIF tag only. Each
detail file records what was applied under `orientation`.

Exit code 1 means Ollama or a model is not available; 2 means invalid input (a variant, a repeated variant, a truth file or an option); 3 means an
unexpected error, printed only as `Evaluation failed: <error type>` so that no receipt
content reaches the screen. A receipt whose image cannot be read, whose OCR fails or whose
model call fails is recorded in its detail file (`image_error`, `ocr_error`, `model_error`,
`timeout`), counts as wrong, and the run goes on.

Privacy rules:

- The detail files and `receipts.json` contain receipt content. They stay on this computer.
- Only `summary.md` may be shared, for example in a conversation with an AI assistant: it
  has aggregate numbers only.
- Cloud models (`-cloud`, `:cloud`) are refused, so no receipt leaves the computer.

## Dependencies and lock files

| Part | Lock file | After changing dependencies |
|---|---|---|
| Backend | `backend/uv.lock` | Rebuild: `docker compose build backend` |
| Frontend | `frontend/package-lock.json` | Rebuild, then refresh the `node_modules` volume: `docker compose build frontend`, then `docker compose run --rm frontend npm ci` |

Change `backend/pyproject.toml`, then update the lock file with the uv version of the image:

```powershell
docker run --rm -v "${PWD}/backend:/app" -w /app ghcr.io/astral-sh/uv:0.9.5-python3.12-bookworm-slim uv lock
```

Change frontend dependencies inside the container, so `package-lock.json` matches Linux:

```powershell
docker compose run --rm frontend npm install --save-exact <package>@<version>
```

Version constraints: TypeScript stays below 6.1 while `typescript-eslint` 8 requires it, and
ESLint stays on 9 while `eslint-plugin-jsx-a11y` does not support ESLint 10. The Playwright
image tag in `frontend/Dockerfile` must match the `@playwright/test` version.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `env file ... .env not found` and nothing starts | `.env` is missing. Run `Copy-Item .env.example .env`. |
| The backend container stops at once; the log has `Invalid setting RRMC_...` | A value in `.env` is not allowed. The line names the setting and the allowed values. |
| The backend log has `Migration NNNN_... failed` | A migration failed; the database stays at the previous version. Fix the migration file and start again. |
| Status line: `Ollamaan ei saada yhteyttä. Käynnistä Ollama.` | Ollama is not running on Windows. Start it; the status line updates within 30 seconds. |
| Status line: `Mallia ... ei ole ladattu.` | Run the `ollama pull` command shown in the status line. |
| Status line: `Kuvakansioita ei löydy tai niihin ei voi kirjoittaa.` | A folder in `RRMC_IMPORT_DIR`, `RRMC_DONE_DIR` or `RRMC_FAILED_DIR` is missing or read-only. |
| Status line: `Taustapalveluun ei saada yhteyttä.` | The backend container is not running. Check `docker compose ps` and `docker compose logs backend`. |
| `port is already allocated` | Another program uses the port. Set `RRMC_BACKEND_PORT` or `RRMC_UI_PORT` in `.env`. |
| Frontend errors about missing packages after a dependency change | The `node_modules` volume is stale. Run `docker compose run --rm frontend npm ci`. |

## Code standards

These rules apply to all code in `backend/` and `frontend/`. The structure and boundaries
they refer to are in [architecture.md](architecture.md). Lint and format tools enforce what
they can; the rest is checked in review (`.agents/skills/review-audit/SKILL.md`).

### General

- Write for the next reader: small functions, clear names, no clever tricks.
- Build only what the spec asks for. No speculative options, hooks or abstractions.
- No dead code and no commented-out code. Delete it; Git keeps the history.
- Names, comments and log messages are in English. Finnish appears only in user-facing
  texts, which live in one module per side (see [UI texts](#ui-texts)).
- Comments explain *why*, not *what*. Unfinished work is `TODO(name-or-issue): ...`.
- One source of truth per rule: a domain rule (e.g. name normalization) is implemented once
  and called from everywhere that needs it.

### Domain values

| Value | Rule |
|---|---|
| Money | `int` cents in Python (`Cents = int`), `number` cents in TypeScript. Never `float` for money. Text from receipts is parsed with `Decimal` and converted to cents once, at the parsing boundary. Formatting with a decimal comma happens only in the UI (`formatEuro(cents)`, `Intl.NumberFormat("fi-FI", { style: "currency", currency: "EUR" })`) and in the CSV exporter. |
| Purchase date | `datetime.date` / ISO `YYYY-MM-DD` string in the API. |
| Timestamps | Timezone-aware, stored as UTC ISO 8601. "Today" and ISO weeks use `Europe/Helsinki`. |
| Current time | Taken from an injected clock, never called directly in business logic, so tests control it. |
| Names | Compared only through the shared normalization functions (product-management spec, PC6). |

### Python (backend)

**Tools**

| Concern | Tool | Rule |
|---|---|---|
| Format | `ruff format` | Line length 100 |
| Lint | `ruff check` | Rule sets `E`, `F`, `I` (imports), `B` (bugbear), `UP`, `SIM`, `S` (security), `N` (naming) |
| Types | `pyright`, strict mode (`[tool.pyright] typeCheckingMode = "strict"` in `pyproject.toml`) | No untyped public functions; `Any` only with a comment saying why. The same engine as VS Code's Pylance, so the editor shows the same errors |
| Tests | `pytest` | See [Tests](#tests) |

**Layout inside a subsystem package** (`backend/app/<subsystem>/`)

| Module | Contains |
|---|---|
| `routes.py` | FastAPI routes only: parse input, call the service, return the response. No rules. |
| `service.py` | The subsystem's rules. Plain functions or classes, callable from other subsystems. |
| `schemas.py` | Pydantic models for API input and output, and for validated model output. |
| `errors.py` | The subsystem's error classes and codes. |
| `repository.py` | Only in **storage**: all SQL. |

Split a module when it grows past about 300 lines or holds two unrelated things.

**Rules**

- Naming: `snake_case` for functions, variables and modules; `PascalCase` for classes;
  `UPPER_SNAKE_CASE` for constants. Booleans read as questions (`is_group`, `has_products`).
- Imports are absolute (`from app.categorization.service import ...`). A subsystem imports
  another subsystem only through its `service.py` and `schemas.py`, and only in the directions
  allowed in [architecture.md](architecture.md#dependency-rules). Names starting with `_`
  are private to their module.
- External engines (`OcrEngine`, `ReceiptModel`, `Exporter`) are `typing.Protocol`s. Real
  implementations and fakes both satisfy the protocol; code depends on the protocol only.
- Services get their dependencies (repositories, engines, clock, settings) as constructor or
  function arguments, wired with FastAPI `Depends` in `main.py` and the routes.
- Settings are read only through the settings object. No `os.environ` elsewhere.
- Routes that call blocking work (SQLite, Tesseract, the Ollama client) are plain `def`, so
  FastAPI runs them in its thread pool. Use `async def` only for truly asynchronous code.
- SQL lives only in storage, always with parameters (`?`), never with f-strings or `%`.
  Writes that belong together run in one transaction (context manager).
- Migrations are numbered files, applied in order, and never edited after they are
  committed. A change is a new migration.
- Pydantic models at the boundaries (API, model output); frozen `dataclass`es for internal
  values. Validate once at the boundary; inside, trust the types.
- Public functions and classes have a short docstring (purpose, arguments, errors raised)
  when the name alone does not say it.

**Errors**

- Expected failures raise an error class derived from `AppError(code, message, status)`.
  One handler in `main.py` turns it into `{"error": code, "message": message}`.
- Error codes are stable `snake_case` strings defined in the spec. Messages are Finnish and
  come from the backend text module.
- Never `except Exception: pass`. Catch the narrowest exception, and either handle it or
  re-raise it as an `AppError` with `from`.
- Error messages and exceptions never contain receipt content (store, product names,
  amounts, OCR text). Use ids and codes.

**Logging**

- `logger = logging.getLogger(__name__)` per module. No `print`.
- Log events with ids, counts, durations and error codes. Never receipt content, OCR text,
  product names or the database path's contents.
- Levels: `DEBUG` for development detail, `INFO` for one line per request or import run,
  `WARNING` for recoverable problems, `ERROR` with stack trace for unexpected ones.

### TypeScript and React (frontend)

**Tools**

| Concern | Tool | Rule |
|---|---|---|
| Types | TypeScript | `"strict": true`, `"noUncheckedIndexedAccess": true`; `tsc --noEmit` passes |
| Lint | ESLint | `typescript-eslint` (type-checked recommended), `react-hooks`, `jsx-a11y` |
| Format | Prettier | Defaults, print width 100; `eslint-config-prettier` turns off ESLint rules that clash with it |
| Tests | Vitest, React Testing Library, MSW; Playwright | See [Tests](#tests) |

**Rules**

- Function components and hooks only. One component per file, file named after it
  (`ProductsPage.tsx`). Hooks start with `use`.
- Naming: `PascalCase` for components and types, `camelCase` for functions and variables,
  `UPPER_SNAKE_CASE` for constants.
- No `any`. Use `unknown` and narrow it. No non-null assertions (`!`) without a comment.
- All server calls go through the typed clients in `src/api/`, one per resource. Response
  types mirror the backend schemas. Components never call `fetch` directly.
- Components show what the API returns. Business rules (totals, normalization, validation
  beyond required fields) stay in the backend.
- No global state library unless a spec's plan adds one. Keep state local; lift it only
  as far as needed.
- No `dangerouslySetInnerHTML`. No `alert`, `confirm` or `prompt`; confirmations are in the page.
- Accessibility: every input has a label, actions are `<button>`s, lists are lists. This is
  also what makes role-based test queries work.

### UI texts

- Every user-facing text in the frontend comes from `src/i18n/fi.ts`; components contain no
  literal UI strings.
- Backend error messages come from one backend text module, @backend/app/texts.py.
- Texts are plain Finnish, short and specific: say what happened and what to do.

### Tests

- **Names reference acceptance criteria.** Python: `test_ac13_category_in_use_cannot_be_deleted`.
  TypeScript: `it("AC13: shows how many products use the category", ...)`.
- **Structure:** Given / When / Then, as comments when the blocks are not obvious.
- **Location:** `backend/tests/unit/<subsystem>/`, `backend/tests/integration/`;
  frontend component tests next to the component (`ProductsPage.test.tsx`); E2E in
  `frontend/e2e/`.
- **Data:** synthetic only, built with small builder functions (`make_receipt(...)`,
  `makeProduct(...)`). No real receipts, ever.
- **Isolation:** each backend test gets its own temporary SQLite file. No test depends on
  another test's state or order.
- **Determinism:** no network, no sleeps, no real clock. OCR and the model use the fakes.
  Tests that need real Tesseract or Ollama are marked `@pytest.mark.tesseract` /
  `@pytest.mark.ollama` and are not in the default run.
- **Queries:** UI tests find elements by role and label (`getByRole`, `getByLabelText`),
  not by CSS class.
- A failing test is never edited to pass; see the Guardrails in [AGENTS.md](../AGENTS.md#guardrails).

### Dependencies

- Add a dependency only when a spec's plan calls for it, and say why in the plan.
- Versions are pinned and lock files are committed (`backend/uv.lock`,
  `frontend/package-lock.json`); see [Dependencies and lock files](#dependencies-and-lock-files).
- Prefer the standard library and the tools already in the stack.

### Commits

- One logical change per commit, short imperative message, AC IDs where useful
  (`Add category delete protection (AC13, AC14)`).
- Tests, lint, format and type checks pass before a commit.
- Never commit generated files, `.env`, the database or anything under `source/`.

## Subsystems

The rules above apply to every subsystem. See the component map in
[architecture.md](architecture.md#component-map).

## Related Documents

- [architecture.md](architecture.md): structure, dependency rules, cross-cutting rules
- [AGENTS.md](../AGENTS.md): development rules, guardrails, SDD and TDD
- [Foundation spec](../specs/features/foundation.md): scaffold and developer commands (PC11)
- [ADR 0001: Technology stack](adr/0001-tech-stack.md)
