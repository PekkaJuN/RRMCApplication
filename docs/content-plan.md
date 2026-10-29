# Content Plan

The index of all project documentation. It tracks what exists, what is missing, and the order in which docs should be generated. **Read this file first**, then follow the links down into the tiers (see [AGENTS.md](../AGENTS.md#documentation)).

Navigation: ↓ Tier 1 [architecture](architecture.md) | ↓ Tier 2 [subsystems](subsystems/)

## How to use this file

- **Status values:** `Not Started` (needs to be written) · `In Progress` (draft exists, may be incomplete or outdated) · `Done` (written, reviewed, up to date with the code) · `Outdated` (exists but no longer matches the code).
- **Order** is the sequence in which Not Started docs should be generated. Lower numbers first. A doc must not be generated before the docs it depends on.
- Update this file in the same change that adds, renames, removes or changes the status of a doc.
- Link the Path column to a doc only once it exists. Until then, show the path as plain code.
- Tier 3 rows are added only when the code they describe exists. Do not plan modules in advance.

Last reviewed: 2026-10-28

## Summary

| Tier | Total | Done | In Progress | Outdated | Not Started |
|------|------:|-----:|------------:|---------:|------------:|
| 1 Architecture | 9 | 0 | 8 | 0 | 1 |
| 2 Subsystems | 7 | 0 | 5 | 0 | 2 |
| 3 Modules | 0 | 0 | 0 | 0 | 0 |

## Tier 1: Architecture & High-Level (`docs/`)

| Order | Doc | Path | Purpose | Depends on | Status |
|------:|-----|------|---------|------------|--------|
| 1 | Docs index | `docs/README.md` | Entry point; links to every Tier 1 doc and subsystem | none | Not Started |
| 2 | Project Description (required) | [docs/projectdescription.md](projectdescription.md) | Purpose, target users, key features, business domain | 1 | In Progress |
| 3 | System Architecture (required) | [docs/architecture.md](architecture.md) | Tech stack, folder structure, component map, deployment | 2 | In Progress |
| 4 | Data Model (required) | [docs/datamodel.md](datamodel.md) | Core entities, schema overview, relationships | 3 | In Progress |
| 5 | Development Guide (required) | [docs/development.md](development.md) | Setup, commands, code standards, testing, local dev | 3 | In Progress |
| 6 | API Reference (required) | [docs/api-reference.md](api-reference.md) | REST endpoints, auth, request/response formats | 3, 4 | In Progress |
| 7 | Glossary | [docs/glossary.md](glossary.md) | Domain terms used across all tiers; catalog terms so far | 2 | In Progress |
| 8 | ADRs | [docs/adr/](adr/) | One file per significant decision; created as decisions are made. 0001: [technology stack](adr/0001-tech-stack.md); 0002: [Docker](adr/0002-docker.md) | 3 | In Progress |
| 16 | Learnings | [docs/learnings.md](learnings.md) | Log of fixed errors and their solutions, newest first | 5 | In Progress |

### Optional Tier 1 docs (not yet planned)

Create only when the trigger applies. When one is started, move it into the table above with an order number and dependencies.

| Doc | Path | Purpose | Create when |
|-----|------|---------|-------------|
| Security | `docs/security.md` | Auth flow, authorization, data protection | Auth, accounts or stored personal data exist |
| Deployment | `docs/deployment.md` | Environments, CI/CD, infrastructure | The app is deployed or CI exists |
| Integration Guide | `docs/integration.md` | External services, third-party APIs | The app calls an external service |
| Features & Use Cases | `docs/features.md` | Feature inventory, use case documentation | Features outgrow `projectdescription.md` |

## Tier 2: Subsystems (`docs/subsystems/<name>/README.md`)

Generate after Tier 1 `architecture.md` and `datamodel.md` are at least `In Progress`. Subsystem names are provisional until the architecture is written.

| Order | Subsystem | Path | Purpose | Depends on | Status |
|------:|-----------|------|---------|------------|--------|
| 9 | Storage | [docs/subsystems/storage/README.md](subsystems/storage/README.md) | SQLite schema access: categories, product mappings, receipts, lines | 3, 4 | In Progress |
| 10 | Import | [docs/subsystems/import/README.md](subsystems/import/README.md) | Import runs: read images from the import folder, detect duplicates by image hash, move files to the done or failed folder; the reading step comes with its spec | 4, 9 | In Progress |
| 11 | Receipt reading | [docs/subsystems/receipt-reading/README.md](subsystems/receipt-reading/README.md) | Image preprocessing, Tesseract OCR, parsing to line items with the local Ollama model | 4, 10 | In Progress |
| 12 | Categorization | [docs/subsystems/categorization/README.md](subsystems/categorization/README.md) | The catalog (groups, categories, products, names, default list); later: map line items to categories, remembered products first, then the model | 4, 9 | In Progress |
| 13 | Calculation | `docs/subsystems/calculation/README.md` | Category totals per ISO week and month in integer cents; line-sum vs receipt-total check | 4, 12 | Not Started |
| 14 | Export | `docs/subsystems/export/README.md` | Common exporter interface; CSV first, Google Sheets later | 4, 13 | Not Started |
| 15 | UI | [docs/subsystems/ui/README.md](subsystems/ui/README.md) | React UI: receipt image beside an editable table, category dropdowns, live totals, mismatch warning | 6, 12, 13 | In Progress |

## Tier 3: Modules & Code-Level (`docs/subsystems/<name>/modules/`)

No modules yet: the foundation code is covered by the Tier 1 and Tier 2 docs. Add a row here when a module with non-obvious business rules or patterns is implemented.

| Order | Module | Path | Subsystem | Source (`@file`) | Status |
|------:|--------|------|-----------|------------------|--------|
| | _none yet_ | | | | |

## Gaps and open items

- The foundation spec is Done (audited 2026-10-27): the commands in [development.md](development.md#commands) are verified and its manual checks (fresh clone, reload) passed.
- The product management spec is Done (audited 2026-10-27).
- The receipt import spec is Done (audited 2026-10-28): import runs without the reading step;
  the receipts table; the Tuonti page. The import README describes it.
- The model evaluation spec is Done (audited 2026-10-28; image orientation change audited
  2026-10-29): the tool `backend/evaluation/` and how to run it are in
  [development.md](development.md#model-evaluation). It is a development tool, not a
  subsystem. The receipt-reading spec needs the same orientation step
  ([learnings](learnings.md)).
- Storage, categorization, import and UI docs describe what is implemented; receipt-reading describes only the engine interfaces. Their feature specs complete them.
- `docs/README.md` is not written yet. The glossary has the catalog and import terms.
- `docs/security.md` applies (stored personal data: product names) but is not planned yet.
- Subsystem boundaries are defined in [architecture.md](architecture.md#component-map) (In Progress: target design for the feature subsystems, open points marked `[NEEDS CLARIFICATION]`).

## Related documents

- ↓ Tier 1: [projectdescription.md](projectdescription.md), [architecture.md](architecture.md), [datamodel.md](datamodel.md), [development.md](development.md), [api-reference.md](api-reference.md), [glossary.md](glossary.md), [learnings.md](learnings.md); `docs/README.md` to be created
- ↓ Tier 2: [storage](subsystems/storage/README.md), [import](subsystems/import/README.md), [categorization](subsystems/categorization/README.md), [receipt-reading](subsystems/receipt-reading/README.md), [ui](subsystems/ui/README.md); the others to be created
- Specs: `specs/` describe intended behavior; this plan indexes docs of what exists. See [AGENTS.md](../AGENTS.md#workflows).
