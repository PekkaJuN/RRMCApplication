# AGENTS.md

Instructions for AI coding agents working in **RRMCApplication** (Receipt Reader Mapper Calculator).

The file has three independent domains: [Documentation](#1-documentation), [Spec-Driven Development](#part-2-spec-driven-development), and [Skills & Tools](#3-skills--tools). Each can be followed on its own. Where one relies on another, it links to it.

## Project overview

- **Purpose:** read receipts, map their line items to categories, and calculate totals from the result.
- **Status:** early stage. The repository contains only a README. No language, framework or build tooling has been chosen yet.
- **When the stack is chosen:** add the build, test and lint commands under "Commands" below. Until then, do not invent commands or assume a stack.

### Commands

<!-- Fill in once the stack exists. Agents must run these before declaring work done. Keep in sync with docs/development.md. -->
| Task  | Command |
|-------|---------|
| Build | _TBD_   |
| Test  | _TBD_   |
| Lint  | _TBD_   |

## General rules (apply to all domains)

- Prefer the smallest change that satisfies the request. Do not refactor unrelated code.
- Never commit secrets, API keys, or real receipt data. Use synthetic fixtures only.
- Treat receipts as personal financial data: keep it out of logs, docs and commit messages.
- Do not commit, push or open PRs unless asked. When asked, use short imperative commit messages.
- If a request conflicts with a spec or this file, say so and ask instead of silently choosing.
- When something is unknown (stack, requirement, intent), ask or record it as an open question. Do not guess.

---

## 1. Documentation

### Goals
Documentation should let a new contributor (human or agent) understand what the project does, how to run it, and why key decisions were made.

### Where things live
| Content | Location |
|---|---|
| Project intro, quick start | `README.md` |
| Agent instructions | `AGENTS.md` (this file) |
| Content plan (index of all docs) | `docs/content-plan.md` |
| Tier 1: project description, architecture, data model, development guide, API reference, ADRs, glossary | `docs/` |
| Tier 2: subsystems | `docs/subsystems/<name>/` |
| Tier 3: modules and code-level rules | `docs/subsystems/<name>/modules/` |
| Feature specifications | `specs/` (see [Spec-Driven Development](#part-2-spec-driven-development)) |
| User-facing guides | `docs/guides/` |

Create folders only when there is content for them.

### PART 1: Documentation Plan

Documentation uses a **3-tier structure** with explicit cross-references between tiers. Agents navigate from high-level architecture down to specific implementations and back. Start at `docs/content-plan.md`, then Tier 1, and drill down only as far as the task needs, and follow links instead of searching blindly.

```
docs/                                   TIER 1: Architecture & high-level
  content-plan.md                       index of ALL docs: status and generation order
  README.md                             entry point and index of subsystems
  projectdescription.md                 REQUIRED: purpose, users, features, domain
  architecture.md                       REQUIRED: tech stack, folders, components, deployment
  datamodel.md                          REQUIRED: entities, schema, relationships
  development.md                        REQUIRED: setup, commands, standards, testing
  api-reference.md                      REQUIRED: REST endpoints, auth, formats
  glossary.md
  security.md                           optional: auth flow, authorization, data protection
  deployment.md                         optional: environments, CI/CD, infrastructure
  integration.md                        optional: external services, third-party APIs
  features.md                           optional: feature inventory, use cases
  adr/NNNN-title.md
  subsystems/
    <name>/                             TIER 2: Subsystem
      README.md                         domain, interfaces, data flow
      patterns.md                       optional: recurring implementation patterns
      modules/
        <module>.md                     TIER 3: Module / code level
```

#### Tier 1: Architecture & High-Level
- **Contains:** purpose, tech stack, system boundaries, data model.
- **Location:** `docs/`
- **Navigation:** Tier 1 → Tier 2, via subsystem references. `docs/README.md` and `docs/architecture.md` must link to every `docs/subsystems/<name>/README.md`.
- **Related documents:** end each Tier 1 doc with a `## Related Documents` section. It links down to the Tier 2 subsystem docs that implement or depend on it, and to Tier 3 module docs when a rule is important enough to surface at the top level (for example, a data-model entity linking to the module that owns its validation).

- **Required documents.** All five must exist. Generate them in the order shown, and list each in `docs/content-plan.md`.

  | # | Document | Path | Must cover |
  |--:|---|---|---|
  | 1 | Project Description | `docs/projectdescription.md` | Purpose, target users, key features, business domain |
  | 2 | System Architecture | `docs/architecture.md` | Tech stack, folder structure, component map, deployment |
  | 3 | Data Model | `docs/datamodel.md` | Core entities, schema overview, relationships |
  | 4 | Development Guide | `docs/development.md` | Setup, commands, code standards, testing, local dev |
  | 5 | API Reference | `docs/api-reference.md` | REST endpoints, auth, request/response formats |

  - Supporting Tier 1 files, also indexed in the content plan: `docs/README.md` (entry point), `docs/content-plan.md`, `docs/glossary.md`, and `docs/adr/`.
  - `docs/development.md` is the source of truth for build, test and lint commands. Keep the [Commands](#commands) table in this file in sync with it.
  - If the project has no REST API (yet), still create `docs/api-reference.md` and state that plainly, so the gap is explicit rather than a missing file. Fill it in once endpoints exist.
- **Optional documents.** Add these as the project grows. Create one only when its trigger applies, not in advance. Never create an empty placeholder.

  | Document | Path | Must cover | Create when |
  |---|---|---|---|
  | Security | `docs/security.md` | Auth flow, authorization, data protection | Auth, user accounts or stored personal data (receipts are personal financial data) exist |
  | Deployment | `docs/deployment.md` | Environments, CI/CD, infrastructure | The app is deployed anywhere, or a CI pipeline exists |
  | Integration Guide | `docs/integration.md` | External services, third-party APIs | The app calls an external service (for example OCR or currency rates) |
  | Features & Use Cases | `docs/features.md` | Feature inventory, use case documentation | There are enough features that `projectdescription.md` can no longer list them |

  - When an optional document is created, add it to `docs/content-plan.md` with an order number and dependencies, and link it from the Tier 1 docs that relate to it (for example `security.md` ↔ `api-reference.md`).

##### Tier 1 document template
Use this for every Tier 1 doc.

````markdown
# [Document Title]

<!-- @tier: 1 -->
<!-- @see-also: docs/subsystems/[relevant]/ -->

## Overview
[What this document covers and why it matters]

## [Main Content]
[Architecture diagrams, data model, API overview, etc.]

## Subsystem References
Navigate to Tier 2 for subsystem details:
- [Subsystem A](docs/subsystems/subsystem-a/) — [1-line description]
- [Subsystem B](docs/subsystems/subsystem-b/) — [1-line description]

## Related Documents
- **Tier 1:** [links to other Tier 1 docs]
- **Tier 2:** [links to relevant subsystem docs]
````

- `@tier` and `@see-also` are machine-readable markers. Keep `@tier: 1` as is, and list the most relevant Tier 2 folders in `@see-also`.
- Paths in the template are written from the repository root. In a real doc, use links relative to the file (for example `subsystems/subsystem-a/` from `docs/architecture.md`), as required in [Cross-reference conventions](#cross-reference-conventions). The `@see-also` marker keeps the repo-root path.
- Replace the subsystem placeholders with the real ones, and remove the "Subsystem References" section content only if no subsystems exist yet (state "None yet" instead of deleting the heading).
- This section is the "Related Documents" section required for each Tier 1 doc. Do not add a second one.

#### Tier 2: Subsystems
- **Contains:** domain-specific subsystems, their interfaces, and data flow.
- **Location:** `docs/subsystems/<name>/`
- **Navigation:** ↑ Tier 1 | ↓ Tier 3 | → other subsystems. Link to the architecture doc, to each module doc beneath it, and to any subsystem it exchanges data with.
- **Related documents:** end each Tier 2 doc with a `## Related Documents` section. It links up to the specific Tier 1 sections that define its boundaries and data model (not just the file), and down to every Tier 3 module doc.
- **Expected subsystems for this project** (create each only when work on it begins): receipt reading, mapping, calculation.

##### Subsystem README template
Use this for every `docs/subsystems/<name>/README.md`.

````markdown
# [Subsystem Name]

<!-- @tier: 2 -->
<!-- @see-also: docs/architecture.md, docs/subsystems/[related]/ -->

Navigation: ↑ [Architecture](../../architecture.md) | ↓ [Modules](modules/) | → [Other Subsystem](../other-subsystem/README.md)

## Overview
[Purpose and scope: what this subsystem does and what it does not do]

## Key Files and Entry Points
- `@src/path/to/entry-point.ext` — [role]

## Interfaces
[What other parts of the system call or consume: inputs, outputs, events, APIs]

## Data Flow
[How data moves through the subsystem and to or from other subsystems]

## Dependencies
- **Uses:** [Other Subsystem](../other-subsystem/README.md) — [what for]
- **Used by:** [Other Subsystem](../other-subsystem/README.md) — [what for]

## Modules
Navigate to Tier 3 for implementation details:
- [Module A](modules/module-a.md) — [1-line description]
- [Module B](modules/module-b.md) — [1-line description]

## Known Issues and Gotchas
[Tech debt, limitations, surprising behavior]

## Related Documents
- **Tier 1:** [links to the specific Tier 1 sections that define its boundaries and data model, e.g. `../../datamodel.md#receipt`]
- **Tier 2:** [links to other subsystem docs]
- **Tier 3:** [links to every module doc listed above]
````

- Keep the `Navigation:` line directly under the `@` markers, as required in [Cross-reference conventions](#cross-reference-conventions).
- Every module listed under "Modules" must link back to this README, and every Tier 1 doc linked under "Related Documents" must list this subsystem in its "Subsystem References".
- If the subsystem has no modules yet, write "None yet" under "Modules" instead of deleting the heading.

##### Subsystem patterns template
Use this for `docs/subsystems/<name>/patterns.md`. It is optional: create it when the subsystem has implementation patterns that are used in more than one module and are worth following consistently.

````markdown
# [Subsystem Name] — Patterns

<!-- @tier: 2 -->
<!-- @parent: docs/subsystems/[name]/README.md -->

## Pattern: [Pattern Name]
**When to use:** [Trigger condition]
**Implementation:**
[Code example or step-by-step description]
**Example files:** `@file src/[path]/example.ts`

## Pattern: [Pattern Name]
...
````

- `@parent` points to the subsystem README. Under the markers, add the `Navigation:` line required for every Tier 2 doc (for example `Navigation: ↑ [Subsystem](README.md) | ↓ [Modules](modules/)`).
- Add one `## Pattern:` section per pattern. Point to real files in "Example files", and keep the example current when that code changes.
- Link `patterns.md` from the subsystem README ("Related Documents") and link back to the README. Tier 3 module docs link to the patterns they apply, so patterns are not repeated in each module.
- When created, list it in `docs/content-plan.md` under Tier 2.

#### Tier 3: Modules & Code-Level
- **Contains:** implementation patterns, business rules, inline docs.
- **Location:** `docs/subsystems/<name>/modules/`
- **Navigation:** ↑ Tier 2 | → source code, via `@file` references.
- **Related documents:** end each Tier 3 doc with a `## Related Documents` section. It links up to its Tier 2 subsystem doc and to any Tier 1 section it implements (data-model entity, boundary, ADR), and sideways to neighboring modules it calls or depends on.

Tier 3 documents describe specific modules or components within a subsystem. They are the bridge between documentation and source code.




##### Module document template
Use this for every `docs/subsystems/<name>/modules/<module>.md`.

````markdown
# [Module Name]

<!-- @tier: 3 -->
<!-- @parent: docs/subsystems/[name]/README.md -->
<!-- @source: src/[subsystem]/[module]/ -->

## Purpose
[What this module does — 1 sentence]

## Key Files
| File | Purpose | Complexity |
|------|---------|------------|
| `src/[path]/handler.ts` | Request handling | Medium |
| `src/[path]/validator.ts` | Input validation | Low |
| `src/[path]/transformer.ts` | Data transformation | High |

## Business Rules
- [Rule 1: describe the business logic this module enforces]
- [Rule 2: configuration or settings that affect behavior]

## Data Lineage
[How data flows through this module — map inputs to outputs]

API field → validation → transformation → database column

## Dependencies
- **Internal:** [Other modules in same subsystem]
- **External:** [Modules in other subsystems, with Tier 2 links]

## Complex Functions
Document functions where behavior isn't obvious from reading the code:

### `functionName(params)` — @file src/[path]/file.ts
**Purpose:** [What it does]
**Implicit behavior:** [Side effects, assumptions, gotchas]
**Called by:** [What invokes this function]

## Configuration
| Setting | Effect | Default |
|---------|--------|---------|
| `FEATURE_FLAG_X` | Enables [behavior] | `false` |

## Related Documents
- **Tier 2:** [../README.md](../README.md) — Subsystem overview
- **Tier 1:** [../../architecture.md](../../architecture.md) — System architecture
- **Patterns:** [../patterns.md](../patterns.md) — Subsystem patterns
````

- `@parent` points to the subsystem README. `@source` points to the module's source folder. Keep both accurate when files move.
- Under the markers, add the `Navigation:` line required for every Tier 3 doc (for example `Navigation: ↑ [Subsystem](../README.md) | → @src/[path]/`).
- The template ends with the `## Related Documents` section required for every Tier 3 doc. Link up to the subsystem README, to the specific Tier 1 sections the module implements (for example a datamodel entity, not just `architecture.md`), and to `patterns.md`. Add links to neighboring modules where relevant.
- Under "Dependencies", link every module listed, so the dependency can be followed in both directions. "Complex Functions" covers only functions whose behavior is not obvious from the code; do not list every function. Reference the file without a line number. If the function name alone is ambiguous, add the class or enclosing function to the heading (for example `` `Validator.checkTotal(receipt)` ``).
- In "Key Files", rate Complexity as Low, Medium or High. List files by their real paths, and update the table when files are added, renamed or removed.
- Record business rules as rules the code enforces, not as a description of the code. Link to the pattern in `patterns.md` instead of repeating it (see the Subsystem patterns template).
- Create a module doc only when the module has business rules or patterns that are not obvious from the code. List it in `docs/content-plan.md` under Tier 3.

#### Cross-reference conventions
- Every Tier 2 and Tier 3 doc starts with a navigation line directly under the title:
  - Tier 2: `Navigation: ↑ [Architecture](../../architecture.md) | ↓ [modules](modules/) | → [other-subsystem](../other-subsystem/README.md)`
  - Tier 3: `Navigation: ↑ [Subsystem](../README.md) | → @src/path/to/file.ext`
- Use relative links between docs. Use `@path/from/repo/root` for source files, e.g. `@src/mapping/rules.ext`. Reference the file, not a line number, because line numbers go stale.
- **Every tier references related documents in the other tiers, so an agent can move in both directions:**
  - **Drill-down (Tier 1 → 2 → 3):** a higher-tier doc links to each lower-tier doc that elaborates it.
  - **Bubble-up (Tier 3 → 2 → 1):** a lower-tier doc links to the higher-tier docs that give its context, constraints and rationale.
  - A link in one direction requires the matching link in the other. If Tier 1 links to a subsystem, that subsystem links back to the same Tier 1 section. If a Tier 2 doc lists a module, that module links back to the subsystem.
  - Link to the most specific target available (a heading anchor such as `../../datamodel.md#receipt`), not just the top of a file.
  - Add a short label saying why the link matters, e.g. `[Receipt entity](../../datamodel.md#receipt) — fields this module validates`.
- Put each fact in one tier only, then link to it from elsewhere. Do not repeat it.
  - Tier 1: why and boundaries.
  - Tier 2: how parts interact.
  - Tier 3: how it works and the rules it enforces.

#### Content Plan (`docs/content-plan.md`)
The content plan is the **index of all project documentation**. It tracks what exists, what is missing, and in what order docs should be generated. **Agents read it first** to understand the documentation landscape, before opening any other doc.

- **Location:** `docs/content-plan.md`. It sits beside Tier 1 and indexes all three tiers.
- **Contains:**
  - A status summary per tier (total, Done, In Progress, Outdated, Not Started).
  - One table per tier. Each row has: generation order, doc name, path, purpose, dependencies, and status.
  - Tier 3 rows also give the subsystem and the `@file` source the doc describes.
  - A "Gaps and open items" list for blockers and unresolved questions.
- **Status values:** `Not Started` → `In Progress` → `Done` → `Outdated` (when the code changes and the doc has not caught up).
  - **Done:** written, reviewed, up to date with the current code.
  - **In Progress:** a draft exists, may be incomplete or outdated.
  - **Not Started:** needs to be written.
  - **Outdated:** exists but does not match the current code.
- **Generation order:** docs are written in dependency order. Tier 1 first (architecture, data model, development guide: everything depends on these), then core Tier 2 subsystems that others depend on, then feature Tier 2 subsystems by priority, then Tier 3 modules by complexity. Within a tier, follow the order column. Never generate a doc before the docs it depends on.
- **Agent rules:**
  1. Read it first. Pick the next `Not Started` doc whose dependencies are `In Progress` or `Done`, or fix the `Outdated` docs related to your task.
  2. Update it in the same change that adds, renames, removes, or changes the status of a doc. Update the summary counts and the "Last reviewed" date.
  3. Link a doc's path only once the file exists. Add Tier 3 rows only for code that exists.
  4. If you find a doc that is not listed, add it. If a listed doc does not exist and is not marked `Not Started`, correct the status.
  5. Mark docs `Outdated` when you change code in a way that affects them but cannot update the doc now.
- **Navigation:** it links down to Tier 1 and Tier 2 docs. Each of those docs is listed in it, which gives the reverse link.

##### Content plan template
The rows below are examples. Replace them with this project's docs.

````markdown
# Documentation Content Plan
The content plan is the index of all project documentation. It tracks what exists, what's missing, and in what order docs should be generated. AI agents read this first to understand the documentation landscape.

## Overview
[1-2 sentence project description. What does this system do?]

## Documentation Index

| # | Module / Area | Tier | Status | Path | Priority | Last Updated |
|---|---------------|------|--------|------|----------|--------------|
| 1 | Architecture Overview | T1 | Done | docs/architecture.md | Critical | 2025-01-15 |
| 2 | Data Model | T1 | Done | docs/datamodel.md | Critical | 2025-01-15 |
| 3 | Auth Subsystem | T2 | Done | docs/subsystems/auth/ | Critical | 2025-01-20 |
| 4 | Auth — Session Module | T3 | In Progress | docs/subsystems/auth/modules/session.md | High | — |
| 5 | Payments Subsystem | T2 | Not Started | docs/subsystems/payments/ | High | — |
| 6 | Notifications Subsystem | T2 | Not Started | docs/subsystems/notifications/ | Medium | — |

## Status Legend
- **Done** — Written, reviewed, up-to-date with current code
- **In Progress** — Draft exists, may be incomplete or outdated
- **Not Started** — Needs to be written
- **Outdated** — Exists but doesn't match current code

## Generation Order
Generate documentation in dependency order:
1. **Tier 1 first** — Architecture, data model, development guide (everything depends on these)
2. **Core Tier 2 next** — Subsystems that other subsystems depend on (auth, database, shared libraries)
3. **Feature Tier 2** — Business logic subsystems (ordered by developer priority)
4. **Tier 3 last** — Module docs within each subsystem (ordered by complexity)

## What Each Document Must Include
- Purpose and scope
- Key files and entry points (with `@file` references to source code)
- Data flow (how data moves through the module)
- Dependencies on other modules (with links to their Tier 2/3 docs)
- Cross-tier references ("See also" links up and down the tiers)
- Known issues, tech debt, or gotchas
````

#### Documentation Navigation
AI agents navigate documentation using two complementary strategies. Always use both together when planning or implementing.

##### Strategy 1: Top-Down (Architecture-Level)
Navigate from system overview down to specific code:

```
Tier 1: docs/architecture.md                    → System overview
  ↓
Tier 2: docs/subsystems/<name>/README.md         → Subsystem details
  ↓
Tier 3: docs/subsystems/<name>/modules/<mod>.md  → Module specifics
  ↓
Code:   src/<subsystem>/<module>/                → Source files
```

Files to read along the way, in order:

1. `docs/content-plan.md`: which docs exist, and which are Not Started or Outdated.
2. `docs/README.md` and `docs/projectdescription.md`: what the system is for, who uses it, and its key features.
3. `docs/architecture.md`: tech stack, folder structure, component map, system boundaries.
4. `docs/datamodel.md`: core entities and relationships.
5. `docs/subsystems/<name>/README.md`: the subsystem's interfaces, data flow and dependencies.
6. `docs/subsystems/<name>/patterns.md`: the patterns the subsystem expects (if it exists).
7. `docs/subsystems/<name>/modules/<module>.md`: business rules, key files, complex functions.
8. Source code: the `@source` folder and `@file` references in the module doc.

For commands, setup and testing, also read `docs/development.md`. For endpoints and auth, read `docs/api-reference.md`.

**Use when:** understanding structure, planning architectural changes, onboarding.

##### Strategy 2: Feature-Wise (Use-Case Driven)
Navigate from a feature or use case to its implementation:

```
content-plan.md                          → Find the feature area
  ↓
specs/features/<feature>.md              → Read the spec (ACs, files)
  ↓
docs/subsystems/<affected>/README.md     → Understand affected subsystems
  ↓
docs/subsystems/<affected>/modules/*.md  → Module implementation details
  ↓
src/                                     → Source code
```

Files to read along the way, in order:

1. `docs/features.md` (if it exists; otherwise the key features in `docs/projectdescription.md`) and any spec in `specs/features/<feature>.md` (its "Affected files" lists the files to read): what the feature must do and its acceptance criteria.
2. `docs/api-reference.md`: the endpoints the feature uses or exposes.
3. `docs/datamodel.md`: the entities the feature reads or writes.
4. `docs/subsystems/<name>/README.md` of **each** subsystem the feature touches, following "Data Flow" and "Dependencies" links to trace the flow from entry point to storage.
5. `docs/subsystems/<name>/modules/<module>.md` for each step in that flow: Business Rules, Data Lineage, Complex Functions, Configuration.
6. Source code: the `@file` references and `@source` folders in those module docs.

If a subsystem or module in the chain is Not Started, list it in `docs/content-plan.md` and do not explore it further. Ask the user to have it documented first (see Navigation Rules, rule 6).

**Use when:** implementing features, fixing bugs, tracing end-to-end flows.

##### Using both together
- **Planning:** start Top-Down to learn the boundaries, data model and patterns, then go Feature-Wise to find exactly which subsystems and modules the change touches. Do not plan from a single doc.
- **Implementing or fixing a bug:** start Feature-Wise to find the modules involved, then go bottom-up from the module doc (`@parent`, "Related Documents") to the subsystem patterns and Tier 1 constraints the change must respect.
- **Finding docs from code:** search the markers (`@tier`, `@parent`, `@see-also`, `@source`) and `@file` references by file path or symbol name to find the doc for a file. After the change, update every doc that references the files you changed (see [Agent workflow](#agent-workflow)).
- If the two paths disagree (a link leads to a missing file, a marker points to the wrong place), fix the link, or mark the doc `Outdated`, and report it.

##### Navigation Rules

1. **Start with `content-plan.md`**: understand what's documented, what's missing.
2. **Use both strategies together**: feature context + architecture context.
3. **Follow cross-tier references**: every doc links up and down the tiers.
4. **Follow `@file` references**: docs link to specific source files.
5. **Update docs when code changes**: documentation is a living artifact.
6. **Only work within documented subsystems**: if a subsystem isn't documented, list it but do not explore further.

#### Agent workflow
1. **Read down.** Start at `docs/content-plan.md` to see which docs exist, are Not Started or are Outdated. Then read `docs/README.md`, then the relevant subsystem, then the relevant module, then the source files it references.
2. **Write up.** After a change, update the lowest tier it affects. Update higher tiers if interfaces, data flow, boundaries, or the tech stack changed.
3. **Keep links healthy.** When adding, renaming, or deleting a doc or source file, fix the navigation lines, `## Related Documents` entries and `@file` references that point to it, in both directions. Before finishing, confirm that every new or changed link has its reverse link and that no link is broken.
4. **Split or merge.** Add a Tier 3 doc when a module has business rules or patterns that are not obvious from the code. Do not create empty tier docs.
5. Specs live in `specs/` and describe intent. Tier 3 docs describe what exists. Link between them (see [Spec-Driven Development](#part-2-spec-driven-development)).

### When to update docs
Update documentation **in the same change** as the code when you:
- add, remove or rename a user-visible feature, command, flag or config option;
- change setup, build or run steps;
- make a design decision that would be hard to infer from the code (write an ADR);
- introduce a new domain term (add it to `docs/glossary.md`).

Do not leave docs describing behavior that no longer exists.

### Writing style
- Plain, direct English. Short sentences. Active voice.
- Lead with what the reader needs to do or know; put background after.
- Use headings, lists and tables for scanning. Keep paragraphs short.
- Use fenced code blocks with a language tag for commands and code. Commands must be copy-pasteable and tested.
- Use relative links between docs. Prefer linking to a single source of truth over duplicating content.
- Use the glossary terms consistently.
- Do not document the obvious or restate what the code says. Explain intent, constraints and trade-offs.

### Code comments
- Comment *why*, not *what*. Remove comments that restate the code.
- Public APIs get doc comments in the language's idiomatic format (parameters, return value, errors, an example when non-obvious).
- Tag unfinished work as `TODO(name-or-issue): ...`. Do not leave bare TODOs.

### ADR format
Each ADR is short and immutable once accepted. Supersede it with a new ADR rather than editing history.

```markdown
# NNNN. Title
- Status: proposed | accepted | superseded by NNNN
- Date: YYYY-MM-DD

## Context
## Decision
## Consequences
```

### Quality checks before finishing
- `docs/content-plan.md` lists every doc you added, renamed, removed or re-statused, with correct counts.
- Every link resolves and has its reverse link in the adjacent tier; every command was run or is clearly marked as unverified.
- No placeholder text (`_TBD_`) was left behind in sections you were asked to complete.
- The README quick start still works from a clean checkout.

---

### PART 2: Spec-Driven Development
The spec-driven workflow follows a 4-step process: **Document → Spec → Develop → Audit**

This section defines each workflow independently. They chain together but can also be used standalone.

```
Document → Spec → Develop → Audit
   ↑                          |
   └──────── findings ────────┘
```

| Step | Workflow | Purpose | Needs | Produces |
|---|---|---|---|---|
| 1 | **Document** | Create or update the three-tier docs so they match the code | `docs/content-plan.md`, source code | Tier 1/2/3 docs, updated content plan |
| 2 | **Spec** | Define what a feature must do, and how and in what order to build it | Request, docs from step 1 | Approved `specs/features/<feature>.md` (spec, plan, tasks) |
| 3 | **Develop** | Implement the approved spec task by task | Approved spec | Code, tests, updated docs |
| 4 | **Audit** | Check that code, spec and docs agree | Implemented code, spec, docs | Audit findings, content plan statuses |

- **Chaining:** the output of one step is the input of the next. Audit findings feed back into Document (Outdated docs) or Spec (gaps and deviations).
- **Standalone use:** each workflow can be run on its own. Before starting, check its "Needs". If something is missing, stop and say what, rather than guessing or silently running the earlier step. For example, Develop does not start without an approved spec.
- **Research:** [Workflow: research](#workflow-research) is a read-only step that comes before planning. It can precede any of the four steps, and is not one of them.
- **Where the details are:** the phases below map to the steps: Specify, Plan and Tasks are the Spec step, Implement is the Develop step, and Verify is part of the Audit step. The Document step follows the rules in [Documentation](#1-documentation).

The spec is the source of truth. Code implements a spec; it does not define one. For any non-trivial feature, bug fix with behavior change, or new module, write or update the spec **before** writing code.

A change is *trivial* (no spec needed) if it is a typo, formatting, comment, dependency bump without behavior change, or a refactor with no observable change. If unsure, write a short spec.

### Workflow: research
**Goal:** Understand a task thoroughly before planning.

**Steps:**

1. **Gather context**
   - Navigate documentation using both strategies (top-down + feature-wise). See [Documentation Navigation](#documentation-navigation).
   - Start at Tier 1 for high-level context.
   - Dive to Tier 2 for affected subsystem details.
   - Check Tier 3 for module implementation patterns.
   - Search the codebase for existing code patterns.
   - Search the web for external API and library documentation.
2. **Identify scope**
   - Which subsystems are affected?
   - What business rules apply?
   - What configuration controls the behavior?
   - What cross-subsystem dependencies exist?
3. **Analyze and plan**
   - Synthesize information from all documentation tiers.
   - Outline what needs to be done.
   - Identify missing information.
4. **Present findings**
   - State the analysis, plan, and referenced documentation.
   - Ask clarifying questions if needed.

**Rules**
- Research is read-only. Do not change code or docs. The one exception is listing gaps in `docs/content-plan.md`.
- If a subsystem is not documented, list it and do not explore it further (Navigation Rules, rule 6).
- For web research, prefer official documentation, note the version, and cite the sources.
- The outline in step 3 is a draft for discussion. The formal plan is written in the spec (Spec step).
- Stop after presenting the findings. Do not start the Spec or Develop steps until the user says so.

### Workflow: document
**Goal:** Scan the filesystem against the documentation plan and update documentation.

**Steps:**

1. **Read the content plan**
   - Read `content-plan.md` to understand what exists and what's missing.
   - Note the status of each entry (Done, In Progress, Not Started, Outdated).
   - Identify the generation order and priorities.
2. **Scan the filesystem**
   - Recursively scan all source directories.
   - For each file: identify exports, classes, functions, public APIs.
   - Map import/export relationships between modules.
   - Compare discovered modules against the content plan:
     - **Undocumented:** source code exists, no corresponding docs.
     - **Outdated:** docs exist but don't match the current code structure.
     - **Orphaned:** docs reference files that no longer exist.
     - **Complete:** docs exist and match the current code.
3. **Generate / update documentation**
   - Follow the tier structure and templates from [PART 1](#part-1-documentation-plan).
   - Tier 1 first: architecture, data model, development guide.
   - Tier 2 next: subsystem READMEs for each major area.
   - Tier 3 last: module docs for complex or critical modules.
   - Every document must include cross-tier references (up, down, sideways).
   - Use `@file` references to link docs to specific source files.
4. **Update the content plan**
   - Update `content-plan.md` with new statuses and dates.
   - Add newly discovered modules that need documentation.
   - Remove entries for deleted source files.

**Output:**

````markdown
## Documentation Scan Report
| Area | Tier | Status Before | Status After | Path |
|------|------|---------------|--------------|------|
| [module] | T1/T2/T3 | Not Started | Done | docs/... |

## Summary
- Documented: [X] modules
- Undocumented remaining: [Y] modules
- Outdated: [Z] documents
- Coverage: [X/(X+Y)]% of source modules have documentation
````

**Rules**
- **Status mapping:** Undocumented = `Not Started`, Outdated and Orphaned = `Outdated`, Complete = `Done`. A doc that is written but not yet reviewed against the code is `In Progress`.
- **Orphaned docs:** fix the references or remove the doc, and say which in the report. Do not delete a doc without the user's approval.
- **Scope:** this workflow may read undocumented subsystems, since documenting them is its purpose. The "only work within documented subsystems" rule (Navigation Rules, rule 6) applies to the other workflows.
- **Changes:** this workflow writes docs and the content plan only. It does not change source code.
- **Before finishing:** run the checks in [Quality checks before finishing](#quality-checks-before-finishing), and give the scan report as the final output.
- If `docs/content-plan.md` does not exist, create it first, using the content plan template, and then continue.

### Layout
```
specs/
  README.md                 index of specs and their status
  features/
    <feature>.md            one file per feature: spec, plan and tasks
```
Each feature has one file. It starts with the spec (what and why: requirements, acceptance criteria, affected files). The `## Plan` and `## Tasks` sections are added to the same file in later phases. Use a short kebab-case name for `<feature>`, e.g. `receipt-upload.md`. Create this structure on first use. Do not scaffold empty specs.

### Workflow
Work through the phases in order. Do not start a phase until the previous one is agreed.

1. **Specify** (the spec sections of `specs/features/<feature>.md`). Describe *what* and *why*, never *how*. Include:
   - Problem and goal; who it is for.
   - Functional requirements, each with an ID (`FR-1`, `FR-2`, ...).
   - Acceptance criteria in Given/When/Then form, each tied to requirement IDs.
   - Edge cases and error behavior (for this project: unreadable or partial receipts, unknown items, multiple currencies, tax and rounding, duplicate receipts).
   - Out of scope.
   - **Affected files:** the source files and docs expected to change, and why. Find them with the Feature-Wise strategy (see [Documentation Navigation](#documentation-navigation)). If a subsystem involved is not documented, list it and ask the user to document it first.
   - **Open questions.** Mark ambiguity as `[NEEDS CLARIFICATION: ...]`. Do not resolve it by guessing. Ask the user.
2. **Plan** (the `## Plan` section). Describe *how*: components, data flow, data model, interfaces, dependencies, test strategy, risks. Record significant decisions as ADRs (see [Documentation](#1-documentation)). Check the plan against every requirement, and refine "Affected files".
3. **Tasks** (the `## Tasks` section). Break the plan into small, ordered, independently verifiable tasks. Each task names the requirement IDs it satisfies and its test. Use `- [ ]` checkboxes.
4. **Implement.** Take tasks in order. Write the test for a task first when practical, then the code. Tick the checkbox when the task's test passes.
5. **Verify.** Run the full test suite and walk through each acceptance criterion. Report any criterion not met.

### Rules
- Every requirement needs at least one acceptance criterion; every acceptance criterion needs at least one test.
- Keep traceability: tests and commits reference requirement IDs where useful (e.g. `FR-3`).
- If implementation reveals the spec is wrong or incomplete, **stop and update the spec first**, then continue. Never let code and spec drift.
- Do not add behavior that is not in the spec. Propose it as a spec change instead.
- Keep specs small and focused: one feature per spec file. Split large features.
- Keep "Affected files" current. If implementation touches a file that is not listed, add it to the spec. When the work is done, update the docs listed under "Docs to update" (see [Agent workflow](#agent-workflow)).
- Mark spec status in `specs/README.md`: `draft` → `approved` → `implemented` → `superseded`. Only the user approves a spec.
- Ask for approval before moving from Specify to Plan, and from Plan to Implement, unless the user said to proceed autonomously.

### Spec template
```markdown
# Feature name
Status: draft

## Summary
## Problem and goals
## Requirements
- FR-1: ...
## Acceptance criteria
- AC-1 (FR-1): Given ... When ... Then ...
## Edge cases
## Out of scope
## Affected files
| File | Change | Why |
|------|--------|-----|
| `src/[path]/file.ts` | modify / add / remove | [reason] |

**Docs to update:** [e.g. `docs/subsystems/[name]/modules/[module].md`, `docs/datamodel.md`, `docs/api-reference.md`]
## Open questions
- [NEEDS CLARIFICATION: ...]
## Plan
(added in the Plan phase)
## Tasks
(added in the Tasks phase)
```

---

## 3. Skills & Tools

### Principles
- Use the least powerful tool that does the job. Prefer reading and searching over editing, and editing over running arbitrary commands.
- Read before you write. Look at existing code, docs and specs before proposing changes, and follow existing conventions.
- Verify your work with real output (tests, build, lint, running the code). Do not report success from reasoning alone.
- Destructive or hard-to-reverse actions (deleting files, force-pushing, rewriting history, dropping data, changing remotes) require explicit user approval each time.
- Stay inside the repository. Do not read or modify files elsewhere on the machine unless the user asked.
- Do not install global packages or change system configuration. Add project dependencies only when the plan calls for them, and record why.
- Network access: only to fetch documentation or packages the task needs. Never send repository contents or receipt data to third-party services without approval.

### Tool selection
| Need | Use |
|---|---|
| Find files or text | Glob / Grep or the shell's search tools |
| Understand a file | Read the relevant part, not necessarily the whole file |
| Change code or docs | Edit in place with minimal diffs; avoid whole-file rewrites |
| Build, test, lint | The commands in [Commands](#commands) |
| Look up library or API behavior | Official documentation first; cite the version |
| Parallel or large searches | Delegate to a sub-agent only when the work is independent and broad |

### Skills
A skill is a reusable, self-contained instruction set for a recurring task.

- Store project skills in `.agents/skills/<skill-name>/SKILL.md` (plus any helper scripts or templates in the same folder).
- Each `SKILL.md` starts with front matter:
  ```markdown
  ---
  name: skill-name
  description: One sentence on what it does and when to use it.
  ---
  ```
  Follow with numbered steps, inputs, expected outputs and a checklist for done.
- Before starting a task, check whether a matching skill exists and follow it. If a skill conflicts with this file, this file wins; tell the user.
- Create a new skill only when a procedure has recurred or the user asks. Keep it short and specific, with one task per skill.
- Candidate skills for this project, to be created when needed:
  - `new-spec`: scaffold `specs/features/<feature>.md` from the template in [Spec-Driven Development](#part-2-spec-driven-development).
  - `add-adr`: create the next numbered ADR (see [Documentation](#1-documentation)).
  - `receipt-fixture`: generate a synthetic receipt fixture for tests. It must never use real data.

### Project tools
Register any project-specific scripts or MCP/tool integrations here so agents can discover them. Remove this note when the first one is added.

| Tool | Purpose | How to run | Notes |
|---|---|---|---|
| _none yet_ | | | |

### Reporting
When you finish, state in a few lines: what changed, how you verified it (commands and results), and anything left open or uncertain. If spec or doc updates were needed, say which files.
