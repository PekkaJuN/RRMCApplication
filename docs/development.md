# Development Guide

- **Status:** In Progress (code standards written; setup and local development are added
  with the foundation spec)
- **Updated:** 2026-10-26

## Overview

How to work on RRMCApplication: commands and code standards. The system's structure and
boundaries are in [architecture.md](architecture.md); development rules, SDD and TDD are in
[AGENTS.md](../AGENTS.md).

## Commands

This table is the source of truth; the Commands table in [AGENTS.md](../AGENTS.md#commands)
mirrors it. All commands run inside the containers. The exact `docker compose` form is fixed
in the [foundation spec](../specs/features/foundation.md) plan (PC11). Commands marked
*planned* are not verified until the project is scaffolded.

| Task | Command | Status |
|---|---|---|
| Backend tests | `cd backend && pytest` | planned |
| Backend lint | `cd backend && ruff check . && ruff format --check .` | planned |
| Backend type check | `cd backend && pyright` | planned |
| Frontend tests | `cd frontend && npm test` | planned |
| Frontend lint | `cd frontend && npm run lint` | planned |
| Frontend format check | `cd frontend && npx prettier --check .` | planned |
| Frontend type check | `cd frontend && npx tsc --noEmit` | planned |
| E2E tests | `cd frontend && npx playwright test` | planned |
| Run backend | `cd backend && uvicorn app.main:app --host 127.0.0.1` | planned |
| Run frontend | `cd frontend && npm run dev` | planned |

Before declaring work done, run the tests, lint, format check and type check for every part
you changed.

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
- Backend error messages come from one backend text module (fixed in the foundation plan).
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
- Versions are pinned and lock files are committed (`package-lock.json`; the backend lock
  file is chosen in the foundation plan).
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
