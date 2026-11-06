# Documentation

The entry point to the RRMCApplication docs. RRMCApplication (Receipt Reader Mapper
Calculator) is a local, single-user app that reads receipt photos, categorizes the purchases
and totals each category per week and per month.

To see the status of every doc and what is missing, read the
[content plan](content-plan.md).

## Start here

| I want to | Read |
|---|---|
| Understand what the app does and why | [Project description](projectdescription.md) |
| Set up, run and test the app | [Development guide](development.md) |
| See how the parts fit together | [Architecture](architecture.md) |
| Fix or understand an error | [Learnings](learnings.md) |

## Reference

- [Project description](projectdescription.md): purpose, users, key features
- [Architecture](architecture.md): stack, folder structure, component map, data flow
- [Data model](datamodel.md): tables, relationships, migrations
- [API reference](api-reference.md): endpoints, requests, responses, errors
- [Development guide](development.md): setup, commands, code standards, testing
- [Security](security.md): what data the app holds, how it is protected, known limits
- [Glossary](glossary.md): domain terms in English and Finnish
- [ADRs](adr/): significant decisions
  - [0001: Technology stack](adr/0001-tech-stack.md)
  - [0002: Docker](adr/0002-docker.md)
  - [0003: Receipt reading model](adr/0003-receipt-reading-model.md)
  - [0004: Line categorization](adr/0004-line-categorization.md)
- [Learnings](learnings.md): fixed errors and their solutions, newest first

## Subsystems

- [Storage](subsystems/storage/README.md): SQLite connection, migrations and all SQL
- [Import](subsystems/import/README.md): import runs, duplicates and moving files
- [Receipt reading](subsystems/receipt-reading/README.md): preprocessing, OCR and parsing
- [Categorization](subsystems/categorization/README.md): the catalog, line categories and
  user corrections
- [Calculation](subsystems/calculation/README.md): the receipt check, subtotals, periods and
  period totals
- [Review](subsystems/review/README.md): the receipt endpoints of the review UI
- [Totals](subsystems/totals/README.md): the totals endpoint
- [Budget](subsystems/budget/README.md): monthly budgets and their comparison
- [Export](subsystems/export/README.md): CSV export and the exporter interface
- [UI](subsystems/ui/README.md): the React UI, stylesheet and accessibility check

## Requirements and specs

Docs describe what exists. Requirements and intended behavior are in `specs/`:

- [PRD](../specs/PRD.md): product requirements and releases
- [Feature specs](../specs/README.md): the index of all specs

## Rules for agents

[AGENTS.md](../AGENTS.md) holds the development rules, guardrails and workflows.
