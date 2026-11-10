# Content Plan

The index of all project documentation. It tracks what exists, what is missing, and the order in which docs should be generated. **Read this file first**, then follow the links down into the tiers (see [AGENTS.md](../AGENTS.md#documentation)).

Navigation: ↓ Tier 1 [architecture](architecture.md) | ↓ Tier 2 [subsystems](subsystems/)

## How to use this file

- **Status values:** `Not Started` (needs to be written) · `In Progress` (draft exists, may be incomplete or outdated) · `Done` (written, reviewed, up to date with the code) · `Outdated` (exists but no longer matches the code).
- **Order** is the sequence in which Not Started docs should be generated. Lower numbers first. A doc must not be generated before the docs it depends on.
- Update this file in the same change that adds, renames, removes or changes the status of a doc.
- Link the Path column to a doc only once it exists. Until then, show the path as plain code.
- Tier 3 rows are added only when the code they describe exists. Do not plan modules in advance.

Last reviewed: 2026-11-09

## Summary

| Tier | Total | Done | In Progress | Outdated | Not Started |
|------|------:|-----:|------------:|---------:|------------:|
| 1 Architecture | 10 | 6 | 4 | 0 | 0 |
| 2 Subsystems | 10 | 10 | 0 | 0 | 0 |
| 3 Modules | 0 | 0 | 0 | 0 | 0 |

## Tier 1: Architecture & High-Level (`docs/`)

| Order | Doc | Path | Purpose | Depends on | Status |
|------:|-----|------|---------|------------|--------|
| 1 | Docs index | [docs/README.md](README.md) | Entry point; links to every Tier 1 doc and subsystem | none | Done |
| 2 | Project Description (required) | [docs/projectdescription.md](projectdescription.md) | Purpose, target users, key features, business domain | 1 | Done |
| 3 | System Architecture (required) | [docs/architecture.md](architecture.md) | Tech stack, folder structure, component map, deployment | 2 | Done |
| 4 | Data Model (required) | [docs/datamodel.md](datamodel.md) | Core entities, schema overview, relationships | 3 | Done |
| 5 | Development Guide (required) | [docs/development.md](development.md) | Setup, commands, code standards, testing, local dev | 3 | In Progress |
| 6 | API Reference (required) | [docs/api-reference.md](api-reference.md) | REST endpoints, auth, request/response formats | 3, 4 | Done |
| 7 | Glossary | [docs/glossary.md](glossary.md) | Domain terms used across all tiers: catalog, import, reading, line categorization, review, line editing and totals terms | 2 | In Progress |
| 8 | ADRs | [docs/adr/](adr/) | One file per significant decision; created as decisions are made. 0001: [technology stack](adr/0001-tech-stack.md); 0002: [Docker](adr/0002-docker.md); 0003: [receipt-reading model](adr/0003-receipt-reading-model.md); 0004: [line categorization](adr/0004-line-categorization.md); 0005: [PDF library](adr/0005-pdf-library.md); 0006: [agent guardrails](adr/0006-agent-guardrails.md) | 3 | In Progress |
| 16 | Learnings | [docs/learnings.md](learnings.md) | Log of fixed errors and their solutions, newest first | 5 | In Progress |
| 19 | Security | [docs/security.md](security.md) | Stored data, protection and known limits | 3, 5, 6 | Done |

### Optional Tier 1 docs (not yet planned)

Create only when the trigger applies. When one is started, move it into the table above with an order number and dependencies.

| Doc | Path | Purpose | Create when |
|-----|------|---------|-------------|
| Deployment | `docs/deployment.md` | Environments, CI/CD, infrastructure | The app is deployed or CI exists |
| Integration Guide | `docs/integration.md` | External services, third-party APIs | The app calls an external service |
| Features & Use Cases | `docs/features.md` | Feature inventory, use case documentation | Features outgrow `projectdescription.md` |

## Tier 2: Subsystems (`docs/subsystems/<name>/README.md`)

Generate after Tier 1 `architecture.md` and `datamodel.md` are at least `In Progress`.

| Order | Subsystem | Path | Purpose | Depends on | Status |
|------:|-----------|------|---------|------------|--------|
| 9 | Storage | [docs/subsystems/storage/README.md](subsystems/storage/README.md) | SQLite schema access: categories, product mappings, receipts, lines | 3, 4 | Done |
| 10 | Import | [docs/subsystems/import/README.md](subsystems/import/README.md) | Import runs: read images from the import folder, detect duplicates by image hash, move files to the done or failed folder, with the reading step | 4, 9 | Done |
| 11 | Receipt reading | [docs/subsystems/receipt-reading/README.md](subsystems/receipt-reading/README.md) | Image preprocessing, Tesseract OCR, parsing to line items with the local Ollama model | 4, 10 | Done |
| 12 | Categorization | [docs/subsystems/categorization/README.md](subsystems/categorization/README.md) | The catalog (groups, categories, products, names, default list); line categories at import (remembered products first, then the model); user corrections and FR-36 | 4, 9 | Done |
| 13 | Calculation | [docs/subsystems/calculation/README.md](subsystems/calculation/README.md) | Category totals per ISO week and month in integer cents; line-sum vs receipt-total check and receipt subtotals; periods and their columns | 4, 12 | Done |
| 14 | Export | [docs/subsystems/export/README.md](subsystems/export/README.md) | `GET /api/export/lines`, `/totals`, `/totals/pdf` and `/comparison/pdf`: CSV and PDF files of a period behind the exporter interfaces; Google Sheets later | 4, 13, 18 | Done |
| 15 | UI | [docs/subsystems/ui/README.md](subsystems/ui/README.md) | React UI: receipt image beside an editable table, category dropdowns, live totals, mismatch warning; the stylesheet and the accessibility check | 6, 12, 13 | Done |
| 17 | Review | [docs/subsystems/review/README.md](subsystems/review/README.md) | Receipt endpoints of the review UI: list, receipt view with sums, image, category choice, line and receipt edits, review state, deleting and creating a receipt | 6, 9, 12, 13 | Done |
| 18 | Totals | [docs/subsystems/totals/README.md](subsystems/totals/README.md) | `GET /api/totals`: category totals per ISO week and month of a period, with the unreviewed and undated counts | 6, 9, 12, 13 | Done |
| 20 | Budget | [docs/subsystems/budget/README.md](subsystems/budget/README.md) | `/api/budget`: monthly budgets and their comparison with reviewed spending of a calendar month or a 15–14 period | 6, 9, 12, 13, 18 | Done |

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
  subsystem; it uses the app's reading code.
- The receipt-reading spec is Done (audited 2026-10-30): the reading step in
  the import run, the read data and `receipt_lines`, the start checks and the stopped run.
  The receipt-reading, import, storage and UI docs describe it.
- The categorization spec is Done (audited 2026-10-30): line
  categories at import, the correction service, FR-36 and the catalog rules with lines. The
  categorization, import, storage, receipt-reading and data model docs and ADR 0004
  describe it.
- The receipt review spec is Done (audited 2026-10-31): the receipt
  endpoints, the receipt check and subtotals, the review state, and the Kuitit and receipt
  pages. The review, calculation, UI, storage, categorization, data model, API and
  architecture docs describe it.
- The line editing spec is Done (audited 2026-10-31): line edits,
  added and deleted lines, the store, date and total, FR-43, strict bodies and id bounds.
  The review, categorization, storage, UI, data model, API and architecture docs describe
  it.
- The category totals spec is Done (audited 2026-11-02): the period,
  its columns and totals in calculation, the totals package and `GET /api/totals`, and the
  Yhteenveto page. The totals, calculation, storage, UI, API, architecture and glossary docs
  describe it.
- The CSV export spec is Done (audited 2026-11-02): the export package and the export
  links on the Yhteenveto page. The export, totals, UI, API and glossary docs describe it.
- The visual style and accessibility spec is Done (audited 2026-11-02): the stylesheet and
  the axe check. The UI and development docs describe it.
- The receipt deletion and manual receipts spec is Done (audited 2026-11-03): delete an
  unreviewed receipt, type in a receipt with an optional failed image, migration 0006. The
  API, data model, architecture, review, storage, import, UI, development and glossary docs
  describe it.
- The monthly budget spec is Done (audited 2026-11-06): the budget package, migration 0007, the comparison
  in calculation, and the Budjetti and Vertailu pages. The budget, calculation, storage,
  categorization, UI, API, data model, architecture and glossary docs describe it.
- The Finnish date field spec is Done (audited 2026-11-06): date fields as `dd.mm.yyyy` with a
  calendar button. The UI and glossary docs describe it.
- The free date range spec is Done (audited 2026-11-06): the `range` period in calculation, its
  use in totals and the CSV export, and `Aikaväli` on the Yhteenveto page. The calculation,
  totals, export, UI, API and glossary docs describe it.
- The PDF export spec is Done (audited 2026-11-09): the weekly, monthly and
  comparison PDF files, the PDF links on the Yhteenveto and Vertailu pages and ADR 0005.
  The export, totals, budget, UI, API, architecture, security and glossary docs describe it.
- The test container isolation spec is Done (audited 2026-11-10): the `backend-test` and
  `frontend-test` services, `backend-e2e` without `.env`, and pytest's refusal next to real
  data. The development, security and architecture docs, the UI README and AGENTS.md
  describe it.
- The agent guardrails spec is In Progress (2026-11-10): the guard G1-G8 for Claude Code
  and Codex, the autonomy rule and ADR 0006. AGENTS.md, the spec, tdd and review-audit skills,
  security.md and development.md describe it.
- The glossary has the catalog, import, reading, line categorization, review, line
  editing, totals, budget and export terms.
- [security.md](security.md) lists three known limits. The user accepted the unexpected error's message in the log as an exception to NFR-3.
- Subsystem boundaries are defined in [architecture.md](architecture.md#component-map). The Google Sheets export is the only target design left there.
- Docs scanned against the code on 2026-11-06. Two stay In Progress: `development.md` (code standards only partly checked) and `glossary.md` (period and totals terms not traced rule by rule).

## Related documents

- ↓ Tier 1: [projectdescription.md](projectdescription.md), [architecture.md](architecture.md), [datamodel.md](datamodel.md), [development.md](development.md), [api-reference.md](api-reference.md), [glossary.md](glossary.md), [learnings.md](learnings.md), [security.md](security.md), [README.md](README.md)
- ↓ Tier 2: [storage](subsystems/storage/README.md), [import](subsystems/import/README.md), [categorization](subsystems/categorization/README.md), [receipt-reading](subsystems/receipt-reading/README.md), [calculation](subsystems/calculation/README.md), [review](subsystems/review/README.md), [totals](subsystems/totals/README.md), [budget](subsystems/budget/README.md), [export](subsystems/export/README.md), [ui](subsystems/ui/README.md)
- Specs: `specs/` describe intended behavior; this plan indexes docs of what exists. See [AGENTS.md](../AGENTS.md#workflows).
