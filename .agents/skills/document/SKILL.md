---
name: document
description: Use when creating or updating project documentation, or scanning the docs against the code (scan-only mode is used by the audit). Covers the doc tiers, templates, the content plan and linking rules.
---

# document

Documentation describes what exists (and, in greenfield, the target design). Specs describe intent.

## Tiers

| Tier | Location | Contains | Required |
|---|---|---|---|
| 1 | `docs/` | Why and boundaries: project description, architecture, data model, development guide, API reference, glossary, ADRs | yes |
| 2 | `docs/subsystems/<name>/README.md` | How parts interact: purpose, entry points, interfaces, data flow, dependencies, gotchas | one per subsystem with code or an approved spec |
| 3 | `docs/subsystems/<name>/modules/<module>.md` | Business rules and non-obvious functions of one module | only when the rules are not obvious from the code |

Required Tier 1 docs, in order: `README.md` (index), `projectdescription.md`,
`architecture.md`, `datamodel.md`, `development.md`, `api-reference.md`.
Optional, when the trigger applies: `security.md` (stored personal data — applies here),
`integration.md` (Google Sheets), `glossary.md`, `learnings.md`, `adr/`.
Never create empty placeholders.

## Linking

- Each Tier 2 doc has a navigation line under the title:
  `Navigation: ↑ [Architecture](../../architecture.md) | → [other](../other/README.md)`.
- A doc links to its parent tier and to the docs it depends on. A parent lists its children
  (architecture lists all subsystems; a subsystem lists its modules).
- Link to the most specific heading, e.g. `../../datamodel.md#receipt`.
- Each fact lives in one tier; elsewhere, link to it.
- Source files: `@backend/path/file.py`, no line numbers.

## Content plan (`docs/content-plan.md`)

The index of all docs. Read it first. Keep its existing format: a summary table per tier,
one table per tier (order, doc, path, purpose, depends on, status), and "Gaps and open items".

- Status: `Not Started` → `In Progress` → `Done`; `Outdated` when code changed and the doc did not.
- Update it in the same change that adds, renames, removes or re-statuses a doc. Update counts
  and the "Last reviewed" date.
- Link a path only once the file exists.

## Templates

### Tier 1

```markdown
# <Title>

## Overview
<What this covers and why it matters>

## <Main content>

## Subsystems
- [<Subsystem>](subsystems/<name>/README.md) — <one line>   (or "None yet")

## Related Documents
- <links>
```

### Tier 2

```markdown
# <Subsystem>

Navigation: ↑ [Architecture](../../architecture.md) | → [<other>](../<other>/README.md)

## Overview
<Purpose and scope; what it does not do>

## Key Files and Entry Points
- `@backend/<path>` — <role>

## Interfaces
## Data Flow
## Dependencies
- Uses / Used by: <links>

## Modules
- <links>, or "None yet"

## Known Issues and Gotchas

## Related Documents
```

### Tier 3

```markdown
# <Module>

Navigation: ↑ [<Subsystem>](../README.md) | → `@backend/<path>/`

## Purpose
## Key Files
| File | Purpose |
## Business Rules
- <rules the code enforces, e.g. "amounts are integer cents">
## Complex Functions
### `name(params)` — @backend/<path>.py
Purpose, implicit behavior, called by.
## Configuration
| Setting | Effect | Default |
## Related Documents
```

### ADR (`docs/adr/NNNN-title.md`, immutable once accepted)

```markdown
# NNNN. Title
- Status: proposed | accepted | superseded by NNNN
- Date: YYYY-MM-DD

## Context
## Decision
## Consequences
```

## Steps

1. Read `docs/content-plan.md`.
2. Scan the source folders. Classify each area: **undocumented** (→ Not Started),
   **outdated** or **orphaned** (→ Outdated), **complete** (→ Done).
3. Write or update docs in plan order (Tier 1, then Tier 2, then Tier 3), using the templates.
4. Update the content plan.
5. Check: every new link resolves; parents list children; commands were run or are marked
   unverified; no `_TBD_` left in sections you were asked to complete.

Do not delete a doc without the user's approval.

**Scan-only mode** (used by the audit): run steps 1–2 and report; change nothing.

## Output

```markdown
## Documentation Scan Report
| Area | Tier | Before | After | Path |
|---|---|---|---|---|
Undocumented: N · Outdated: N · Orphaned: N
```
