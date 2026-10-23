# AGENTS.md

Instructions for AI coding agents working in **RRMCApplication** (Receipt Reader Mapper Calculator).
Claude Code reads this file through `CLAUDE.md`. Codex reads it directly.

This file holds the rules that apply to every task. Detailed workflows live in skills under
`.agents/skills/` and are read only when a task needs them (see [Workflows](#workflows)).

## Project overview

- **Purpose:** read receipt images from an import folder, extract line items, categorize them,
  and total the categories per ISO week and per month. The user corrects categories in a UI,
  and corrections are remembered.
- **Users:** one person, on their own computer. Single-user, local-only.
- **Status:** greenfield. Stack decided, no source code yet. See [Greenfield rule](#greenfield-rule).

### Stack (decided)

| Area | Choice |
|---|---|
| OCR | Tesseract 5.x, language packs `fin` + `eng` |
| Parsing and categorization | Local model through Ollama. Model name is one setting (start: Qwen 7–9B class, option 14B). Loaded at app start. |
| Backend | Python + FastAPI: preprocessing, OCR, model calls, totals |
| Frontend | React + Vite + TypeScript: receipt image and editable table side by side |
| Storage | SQLite |
| Export | CSV first, behind a common exporter interface. Google Sheets (gspread) later. |

Significant choices are recorded as ADRs in `docs/adr/`. The stack is
[ADR 0001](docs/adr/0001-tech-stack.md).

### Planned layout

```
backend/            FastAPI app, OCR, parsing, categorization, totals, exporters
frontend/           React + Vite UI
docs/               documentation (see Documentation)
specs/              feature specs (see Workflows)
source/import/      incoming receipt images      (gitignored, real data)
source/import_done/ processed images              (gitignored, real data)
source/import_failed/ images that failed to import (gitignored, real data)
```

The import folders are configurable. Paths above are defaults.

### Commands

`docs/development.md` is the source of truth. Keep this table in sync with it.
Commands marked *planned* are not verified until the project is scaffolded.

| Task | Command | Status |
|---|---|---|
| Backend tests | `cd backend && pytest` | planned |
| Backend lint | `cd backend && ruff check . && ruff format --check .` | planned |
| Frontend tests | `cd frontend && npm test` | planned |
| Frontend lint | `cd frontend && npm run lint` | planned |
| E2E tests | `cd frontend && npx playwright test` | planned |
| Run backend | `cd backend && uvicorn app.main:app --host 127.0.0.1` | planned |
| Run frontend | `cd frontend && npm run dev` | planned |

Run the tests and lint for every part you changed before declaring work done.

## General rules

- Prefer the smallest change that satisfies the request. Do not refactor unrelated code.
- If a request conflicts with a spec or this file, say so and ask. Do not choose silently.
- When something is unknown, ask or record it as `[NEEDS CLARIFICATION: ...]`. Do not guess.
- Do not commit, push or open PRs unless asked. Use short imperative commit messages.
- Verify with real output (tests, lint, running the code). Do not report success from reasoning.
- Destructive or hard-to-reverse actions (deleting files, force-push, rewriting history,
  dropping data, changing remotes) need explicit user approval each time.
- Do not install global packages or change system configuration. Add a project dependency
  only when the spec's plan calls for it.
- All `*.md` files are written in English. Reply to the user in the language they use.

## Privacy and security

Receipts are personal financial data.

- **Never commit** real receipt images, OCR text, the SQLite database, secrets or API keys.
  Tests use synthetic fixtures only.
- Keep receipt content out of logs, docs, specs, commit messages and error messages.
- Images, OCR text and model calls stay on this machine. Ollama runs locally
  (`OLLAMA_NO_CLOUD=1`). The backend listens on `127.0.0.1` only. CORS allows only the
  Vite dev origin.
- Never send repository contents or receipt data to an external service without the user's
  approval. This includes the `gemini` skill: it must not be used for receipt data.
- The Google Sheets service-account key lives outside the repository and outside
  cloud-synced folders. The sheet stays private; request the narrowest scope that works.

## Domain rules

These apply to all code. Specs may add rules but not contradict these.

- Money is stored as integer cents. Never use floats for money.
- Weeks are ISO 8601 weeks (Monday start). Totals group by **purchase date**, not import date.
- A receipt warns when the sum of its lines (including discounts and deposits) differs from
  the receipt total.
- Duplicates are detected by an image hash. A content-based duplicate check may be added by spec.
- An image moves to `import_done` only after its data is committed to the database.
- A user correction of a product's category is stored and reused for that product.

## Greenfield rule

Until code exists, the documentation rules below describe the **target** design.
Working in an undocumented area is allowed when an approved spec covers it.
The spec's "Files to Modify" lists the docs to create alongside the code.

## Workflows

Development is **spec-driven (SDD)** and **test-driven (TDD)**. The chain is:

```
research → spec (Specify → Plan → Tasks) → develop with TDD → audit
                ↑                                              |
                └──────────────── findings ────────────────────┘
```

Before starting a workflow, read its skill file. Each skill states what it needs before it
can start; if something is missing, stop and say what.

| Workflow | When | Skill file |
|---|---|---|
| research | Request is unclear, or before any spec. Read-only. | (below) |
| spec | New feature, API change, architectural or multi-subsystem change | `.agents/skills/spec/SKILL.md` |
| develop + tdd | Implementing an approved spec, or fixing a bug | `.agents/skills/tdd/SKILL.md` |
| review / audit | Feature implemented; final gate before marking Done | `.agents/skills/review-audit/SKILL.md` |
| document | Creating or updating docs, or scanning docs against code | `.agents/skills/document/SKILL.md` |
| fix | An error to diagnose | (below) |

### Non-negotiable SDD and TDD rules

- **The spec is the source of truth.** Code implements a spec. No production code for a
  feature without an approved spec (`specs/features/<feature>.md`, status Approved).
- Only the user approves a spec. Ask for approval between Specify → Plan → Implement,
  unless the user says to proceed autonomously.
- Every acceptance criterion (AC) has at least one test. Tests and commits reference AC IDs.
- **Red → Green → Refactor.** Write the failing test first and see it fail for the right
  reason. Then the simplest code that passes. Then refactor with all tests green.
- If implementation shows the spec is wrong or incomplete, stop and update the spec first.
- Do not add behavior that is not in the spec. Propose it as a spec change.
- A spec is optional for bug fixes, config changes and single-file changes. A bug fix still
  starts with a failing test that reproduces the bug; keep it as a regression test.
- Trivial changes (typo, formatting, comment, dependency bump without behavior change) need
  neither.

### Research (read-only)

1. Read `docs/content-plan.md`, then the relevant Tier 1 and Tier 2 docs and specs.
2. Search the code for existing patterns. For libraries, use official docs and note the version.
3. Present: request type, complexity, whether a spec is needed, affected subsystems, docs read,
   a draft outline, and open questions. Cite web sources.
4. Do not change code or docs (except listing gaps in `docs/content-plan.md`). Stop after
   presenting findings.

### Fix

1. Read `docs/learnings.md` and the affected docs. Note the error message.
2. Form one or two hypotheses. Validate with a test or temporary logging.
3. Write a failing test that reproduces the bug, then the smallest fix.
4. Run all tests. Remove temporary logging.
5. Add an entry to `docs/learnings.md` (newest first): context, symptom, root cause,
   solution, prevention.

Do not loop more than three times without asking the user.

## Documentation

| Content | Location |
|---|---|
| Index of all docs, status and order | `docs/content-plan.md` (read first) |
| Tier 1: project description, architecture, data model, development guide, API reference, glossary, ADRs | `docs/` |
| Tier 2: one README per subsystem | `docs/subsystems/<name>/README.md` |
| Tier 3: module docs, only for non-obvious business rules | `docs/subsystems/<name>/modules/` |
| Feature specs | `specs/features/<feature>.md`, index in `specs/README.md` |
| Fixed errors | `docs/learnings.md` |

Subsystems (provisional until `docs/architecture.md` exists): **import**, **receipt-reading**
(preprocessing, OCR, parsing), **categorization**, **calculation**, **storage**, **export**, **ui**.

Rules:

- Update docs in the same change as the code. Do not leave docs describing behavior that no
  longer exists.
- Put each fact in one place and link to it. Use relative links. Reference source files as
  `@backend/path/file.py`, without line numbers.
- Record hard-to-infer design decisions as ADRs (`docs/adr/NNNN-title.md`; immutable once
  accepted, superseded by a new ADR).
- Add new domain terms to `docs/glossary.md`.
- Templates, status values and the tier linking rules are in `.agents/skills/document/SKILL.md`.

Writing style: plain, direct English, short sentences, active voice. Commands in fenced blocks
with a language tag, copy-pasteable and tested. Explain intent and trade-offs; do not restate code.

Code comments explain *why*, not *what*. Unfinished work is `TODO(name-or-issue): ...`.

## Skills

Skills live in `.agents/skills/<name>/SKILL.md` (frontmatter `name` and `description`, then
command, options, requirements, examples). Check for a matching skill before starting a task.
If a skill conflicts with this file, this file wins; tell the user.

| Skill | Purpose | Status |
|---|---|---|
| `spec` | SDD: write a spec, plan and tasks | ready |
| `tdd` | Develop an approved spec with Red → Green → Refactor | ready |
| `review-audit` | Review an implementation against its spec; final audit gate | ready |
| `document` | Doc tiers, templates, content plan, doc scan | ready |
| `datetime` | Current date and time | planned: script missing |
| `html-to-md` | Fetch a web page as Markdown | planned: script missing |
| `gemini` | Gemini API (external service, never for receipt data) | planned: script missing |

Keep this table in sync with the folders. A skill marked *planned* must not be used until its
script exists.

## Reporting

When you finish, state in a few lines: what changed, how you verified it (commands and
results), which specs and docs you updated, and anything left open.
