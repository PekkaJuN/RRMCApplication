# Content Plan

The index of all project documentation. It tracks what exists, what is missing, and the order in which docs should be generated. **Read this file first**, then follow the links down into the tiers (see [AGENTS.md](../AGENTS.md#documentation)).

Navigation: ↓ Tier 1 [architecture](architecture.md) | ↓ Tier 2 [subsystems](subsystems/)

## How to use this file

- **Status values:** `Not Started` (needs to be written) · `In Progress` (draft exists, may be incomplete or outdated) · `Done` (written, reviewed, up to date with the code) · `Outdated` (exists but no longer matches the code).
- **Order** is the sequence in which Not Started docs should be generated. Lower numbers first. A doc must not be generated before the docs it depends on.
- Update this file in the same change that adds, renames, removes or changes the status of a doc.
- Link the Path column to a doc only once it exists. Until then, show the path as plain code.
- Tier 3 rows are added only when the code they describe exists. Do not plan modules in advance.

Last reviewed: 2026-10-20

## Summary

| Tier | Total | Done | In Progress | Outdated | Not Started |
|------|------:|-----:|------------:|---------:|------------:|
| 1 Architecture | 8 | 0 | 0 | 0 | 8 |
| 2 Subsystems | 7 | 0 | 0 | 0 | 7 |
| 3 Modules | 0 | 0 | 0 | 0 | 0 |

## Tier 1: Architecture & High-Level (`docs/`)

| Order | Doc | Path | Purpose | Depends on | Status |
|------:|-----|------|---------|------------|--------|
| 1 | Docs index | `docs/README.md` | Entry point; links to every Tier 1 doc and subsystem | none | Not Started |
| 2 | Project Description (required) | `docs/projectdescription.md` | Purpose, target users, key features, business domain | 1 | Not Started |
| 3 | System Architecture (required) | `docs/architecture.md` | Tech stack, folder structure, component map, deployment | 2 | Not Started |
| 4 | Data Model (required) | `docs/datamodel.md` | Core entities, schema overview, relationships | 3 | Not Started |
| 5 | Development Guide (required) | `docs/development.md` | Setup, commands, code standards, testing, local dev | 3 | Not Started |
| 6 | API Reference (required) | `docs/api-reference.md` | REST endpoints, auth, request/response formats | 3, 4 | Not Started |
| 7 | Glossary | `docs/glossary.md` | Domain terms used across all tiers | 2 | Not Started |
| 8 | ADRs | `docs/adr/` | One file per significant decision; created as decisions are made | 3 | Not Started |

### Optional Tier 1 docs (not yet planned)

Create only when the trigger applies. When one is started, move it into the table above with an order number and dependencies.

| Doc | Path | Purpose | Create when |
|-----|------|---------|-------------|
| Security | `docs/security.md` | Auth flow, authorization, data protection | Auth, accounts or stored personal data exist |
| Deployment | `docs/deployment.md` | Environments, CI/CD, infrastructure | The app is deployed or CI exists |
| Integration Guide | `docs/integration.md` | External services, third-party APIs | The app calls an external service |
| Features & Use Cases | `docs/features.md` | Feature inventory, use case documentation | Features outgrow `projectdescription.md` |
| Learnings | `docs/learnings.md` | Log of fixed errors and their solutions | The first error is fixed with the fix workflow |

## Tier 2: Subsystems (`docs/subsystems/<name>/README.md`)

Generate after Tier 1 `architecture.md` and `datamodel.md` are at least `In Progress`. Subsystem names are provisional until the architecture is written.

| Order | Subsystem | Path | Purpose | Depends on | Status |
|------:|-----------|------|---------|------------|--------|
| 9 | Storage | `docs/subsystems/storage/README.md` | SQLite schema access: categories, product mappings, receipts, lines | 3, 4 | Not Started |
| 10 | Import | `docs/subsystems/import/README.md` | Read images from the import folder, detect duplicates by image hash, move processed images to import_done | 4, 9 | Not Started |
| 11 | Receipt reading | `docs/subsystems/receipt-reading/README.md` | Image preprocessing, Tesseract OCR, parsing to line items with the local Ollama model | 4, 10 | Not Started |
| 12 | Categorization | `docs/subsystems/categorization/README.md` | Map line items to categories; remembered user corrections first, then the model | 4, 9, 11 | Not Started |
| 13 | Calculation | `docs/subsystems/calculation/README.md` | Category totals per ISO week and month in integer cents; line-sum vs receipt-total check | 4, 12 | Not Started |
| 14 | Export | `docs/subsystems/export/README.md` | Common exporter interface; CSV first, Google Sheets later | 4, 13 | Not Started |
| 15 | UI | `docs/subsystems/ui/README.md` | React UI: receipt image beside an editable table, category dropdowns, live totals, mismatch warning | 6, 12, 13 | Not Started |

## Tier 3: Modules & Code-Level (`docs/subsystems/<name>/modules/`)

No modules yet: there is no source code. Add a row here when a module with non-obvious business rules or patterns is implemented.

| Order | Module | Path | Subsystem | Source (`@file`) | Status |
|------:|--------|------|-----------|------------------|--------|
| | _none yet_ | | | | |

## Gaps and open items

- Tech stack decided (see [AGENTS.md](../AGENTS.md#stack-decided)); record the choices as ADRs when `architecture.md` is written. Commands stay unverified until the project is scaffolded.
- The FastAPI backend exposes a local REST API (127.0.0.1 only); endpoints are defined by specs.
- Subsystem boundaries are provisional until `architecture.md` is drafted.

## Related documents

- ↓ Tier 1: `docs/README.md`, `docs/architecture.md` (to be created, see order above)
- ↓ Tier 2: `docs/subsystems/` (to be created)
- Specs: `specs/` describe intended behavior; this plan indexes docs of what exists. See [AGENTS.md](../AGENTS.md#workflows).
