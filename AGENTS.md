# AGENTS.md

Instructions for AI coding agents working in **RRMCApplication** (Receipt Reader Mapper Calculator).

The file has three independent domains: [Documentation](#1-documentation), [Spec-Driven Development](#part-2-spec-driven-development), and [Skills & Tools](#part-3-skills--tools). Each can be followed on its own. Where one relies on another, it links to it.

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

## Request Processing Steps
For every user request:

1. **Read the request:** identify the goal, affected subsystems, and complexity.
2. **Navigate documentation:** use both strategies (top-down + feature-wise) and consult all 3 tiers. See [Documentation Navigation](#documentation-navigation).
3. **Determine complexity**
   - **Complex** (new feature, refactor, multi-file) → run the [`spec`](#workflow-spec) workflow first.
   - **Simple** (bug fix, config, single-file) → proceed to [`develop`](#workflow-develop) directly.
   - If the request is unclear, run [`research`](#workflow-research) first. Where it is unclear whether a spec is needed, "When required" and "When optional" in the `spec` workflow decide.
4. **Present analysis**

````text
Request type: [type]
Complexity: [Complex | Simple]
Spec required: [Yes | No]
Workflow: [spec → develop → tdd | develop → tdd | fix | research]
Affected subsystems: [list with Tier 2 doc links]
Documentation refs: [Tier 1, 2, 3 docs consulted]
````

5. **Execute workflow:** follow the steps of the chosen workflow.
6. **Record and audit:** update docs, log changes, and audit if a spec existed (see [`audit`](#workflow-audit)).

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
  learnings.md                          log of fixed errors and their solutions (created by the fix workflow)
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

  - Supporting Tier 1 files, also indexed in the content plan: `docs/README.md` (entry point), `docs/content-plan.md`, `docs/glossary.md`, `docs/adr/`, and `docs/learnings.md` (created by the first run of the fix workflow).
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

1. `docs/features.md` (if it exists; otherwise the key features in `docs/projectdescription.md`) and any spec in `specs/features/<feature>.md` (its "Files to Modify" and "Related Documentation" list what to read): what the feature must do and its acceptance criteria.
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
| 1 | **Document**: [`document`](#workflow-document) | Create or update the three-tier docs so they match the code | `docs/content-plan.md`, source code | Tier 1/2/3 docs, updated content plan |
| 2 | **Spec**: [`spec`](#workflow-spec) | Define what a feature must do, and how and in what order to build it | Request, docs from step 1 | Approved `specs/features/<feature>.md` (spec, plan, tasks) |
| 3 | **Develop**: [`develop`](#workflow-develop), using [`tdd`](#workflow-tdd) | Implement the approved spec task by task | Approved spec | Code, tests, updated docs |
| 4 | **Audit**: [`audit`](#workflow-audit), which runs [`review`](#workflow-review) | Check that code, spec and docs agree | Implemented code, spec, docs | Audit findings, content plan statuses |

Two more workflows support the chain: [`research`](#workflow-research) (understand a task before planning) and [`fix`](#workflow-fix) (diagnose and resolve errors).

- **Chaining:** the output of one step is the input of the next. Audit findings feed back into Document (Outdated docs) or Spec (gaps and deviations).
- **Standalone use:** each workflow can be run on its own. Before starting, check its "Needs". If something is missing, stop and say what, rather than guessing or silently running the earlier step. For example, Develop does not start without an approved spec.
- **Research:** [Workflow: research](#workflow-research) is a read-only step that comes before planning. It can precede any of the four steps, and is not one of them. [Workflow: fix](#workflow-fix) can be used at any point, including during Develop.
- **Where the details are:** each workflow is defined in its own section below. The Specify, Plan and Tasks phases belong to the Spec step, Implement belongs to the Develop step, and Verify belongs to the Audit step. The Document step also follows the rules in [Documentation](#1-documentation).

The spec is the source of truth. Code implements a spec; it does not define one. When a change falls under "When required" in [Workflow: spec](#workflow-spec), write or update the spec **before** writing code.

A spec is optional for changes listed under "When optional". Changes that are trivial (a typo, formatting, a comment, a dependency bump without behavior change, or a refactor with no observable change) need no spec. If unsure whether a change needs one, write a short spec.

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

### Workflow: spec
**Goal:** Create a specification before implementation.

**When required:** new features, major refactorings, API changes, architectural changes, multi-subsystem changes.

**When optional:** bug fixes, minor refactorings, documentation updates, config changes, single-file changes.

**Steps:**

1. **Study documentation (grounding)**
   - Read relevant docs from all 3 tiers using both navigation strategies. See [Documentation Navigation](#documentation-navigation); [Workflow: research](#workflow-research) findings can serve as the starting point.
   - Understand existing patterns, business rules, and data flow.
   - Ground the spec in documentation: reference actual files and patterns.
2. **Create spec:** `specs/features/<feature-name>.md`
   - Write it using the phases below (Specify, Plan, Tasks), the [Layout](#layout), the [Rules](#rules) and the [Spec template](#spec-template).
   - Fill in "Files to Modify" and "Related Documentation" from the files and docs found in step 1.

An approved spec is the input to the Develop step.

### Layout
```
specs/
  README.md                 index of specs and their status
  features/
    <feature>.md            one file per feature: spec, plan and tasks
```
Each feature has one file. It starts with the spec (see the [Spec template](#spec-template)). The `## Plan` and `## Tasks` sections are added at the end of the same file in later phases. Use a short kebab-case name for `<feature>`, e.g. `receipt-upload.md`. Create this structure on first use. Do not scaffold empty specs.

### Workflow
Work through the phases in order. Do not start a phase until the previous one is agreed.

1. **Specify** (the spec sections of `specs/features/<feature>.md`). Describe *what* and *why*, never *how*. Include:
   - Problem statement, current behavior (referencing Tier 2/3 docs) and the proposed change. State what is out of scope in the proposed change.
   - Acceptance criteria in Given/When/Then form (`AC1`, `AC2`, ...), including edge cases and error behavior (for this project: unreadable or partial receipts, unknown items, multiple currencies, tax and rounding, duplicate receipts).
   - **Files to Modify:** the source files and docs expected to change, and why. Find them with the Feature-Wise strategy (see [Documentation Navigation](#documentation-navigation)). List docs that need updating as rows too. If a subsystem involved is not documented, list it and ask the user to document it first.
   - Risk assessment, a comprehensive testing strategy, and related documentation (the last two are mandatory).
   - **Ambiguity.** Mark it where it occurs as `[NEEDS CLARIFICATION: ...]`. Do not resolve it by guessing. Ask the user.
2. **Plan** (the `## Plan` section). Describe *how*: components, data flow, data model, interfaces and dependencies. Record significant decisions as ADRs (see [Documentation](#1-documentation)). Check the plan against every acceptance criterion, and refine "Files to Modify".
3. **Tasks** (the `## Tasks` section). Break the plan into small, ordered, independently verifiable tasks. Each task names the acceptance criteria (AC IDs) it satisfies and its test. Use `- [ ]` checkboxes.
4. **Implement.** Take tasks in order. Write the test for a task first when practical, then the code. Tick the checkbox when the task's test passes.
5. **Verify.** Run the full test suite and walk through each acceptance criterion. Report any criterion not met.

### Rules
- Every acceptance criterion needs at least one test in the Testing Strategy, and every part of the proposed change needs at least one acceptance criterion.
- "Testing Strategy" and "Related Documentation" are mandatory. A spec that does not pass the [Spec Readiness Checklist](#spec-readiness-checklist) is not ready for Review or approval.
- Keep traceability: tests and commits reference acceptance criteria IDs where useful (e.g. `AC3`).
- If implementation reveals the spec is wrong or incomplete, **stop and update the spec first**, then continue. Never let code and spec drift.
- Do not add behavior that is not in the spec. Propose it as a spec change instead.
- Keep specs small and focused: one feature per spec file. Split large features.
- Keep "Files to Modify" current. If implementation touches a file that is not listed, add it to the spec. When the work is done, update the docs listed there (see [Agent workflow](#agent-workflow)).
- Spec status is `Draft` → `Review` → `Approved` → `In Progress` → `Done`. Record it in the spec's Overview and in `specs/README.md`. Only the user approves a spec. Set `In Progress` when the Develop step starts and `Done` when its "Update docs" step is complete.
- Ask for approval before moving from Specify to Plan, and from Plan to Implement, unless the user said to proceed autonomously.

### Spec template
````markdown
# Feature: [Name]

## Overview
- **Status:** Draft | Review | Approved | In Progress | Done
- **Created:** [Date]
- **Affected Subsystems:** [List — with links to Tier 2 docs]

## Problem Statement
[What problem does this solve? Why is it needed?]

## Current Behavior
[What the system does now — reference Tier 2/3 docs]

## Proposed Change
[What it should do after implementation]

## Acceptance Criteria

### AC1: [Descriptive name]
**Given** [precondition — system state before]
**When** [action — what the user/system does]
**Then** [expected result — observable outcome]

### AC2: [Descriptive name]
**Given** [precondition]
**When** [action]
**Then** [result]

## Files to Modify

| File | Change Description |
|------|--------------------|
| `src/[path]/file.ts` | [What changes and why] |

## Risk Assessment
- **What could break:** [List affected subsystems]
- **Rollback plan:** [How to undo]
- **Dependencies:** [External services, other teams]

## Testing Strategy (MANDATORY — must be comprehensive)

### Unit Tests
For each function/component, define specific test cases:
| Function | Test Case | Given | When | Then | Mocks |
|----------|-----------|-------|------|------|-------|
| `functionA` | happy path | [setup] | [action] | [result] | [deps] |
| `functionA` | edge case | [setup] | [action] | [result] | [deps] |
| `functionA` | error | [setup] | [action] | [error] | [deps] |

### Integration Tests
API endpoint or service layer tests with real dependencies:
| Scenario | Method | Input | Expected Output | Status Code |
|----------|--------|-------|----------------|-------------|
| [happy path] | POST /api/x | {...} | {...} | 200 |
| [error case] | POST /api/x | {...} | {...} | 400 |

### E2E Tests (if applicable)
User flow scenarios from start to finish:
| User Journey | Steps | Expected Outcome |
|-------------|-------|-----------------|
| [happy path] | 1. ... 2. ... 3. ... | [result] |
| [error flow] | 1. ... 2. ... | [error handled] |

### Coverage Target
- Minimum: [X]% (e.g., 80%)
- Critical paths: 100%

### Test Data
- Fixtures: [describe test data needed]
- Mocks: [list external dependencies to mock]

## Related Documentation (MANDATORY)
- **Tier 1:** [Link to architecture/data model docs]
- **Tier 2:** [Link to subsystem docs]
- **Tier 3:** [Link to module docs]
- **Patterns:** [Link to relevant patterns]
````

The Plan and Tasks phases append `## Plan` and `## Tasks` sections to the end of this file.

### Spec Readiness Checklist
- [ ] Every AC has Given/When/Then format
- [ ] Files to modify are listed with specific changes
- [ ] Risk assessment identifies what could break
- [ ] Testing strategy is comprehensive (unit + integration + E2E)
- [ ] Every functional requirement has corresponding test case(s)
- [ ] Every user story has corresponding E2E scenario(s)
- [ ] Error conditions and edge cases are covered in tests
- [ ] Coverage target is defined
- [ ] Related Documentation links all 3 tiers
- [ ] Spec is grounded in existing docs (not invented from scratch)

**Validation:** If the testing strategy is incomplete (missing test cases for requirements, no edge cases, no coverage target), the spec is NOT ready for approval. Complete the testing strategy before proceeding.

- In this template, the functional requirements are the parts of "Proposed Change" and the acceptance criteria. User stories are the user journeys they describe.
- Where the template marks a test type "if applicable" (E2E), write why it does not apply instead of leaving it empty.

### Workflow: tdd
**Goal:** Implement a feature using Test-Driven Development: Red → Green → Refactor.

**When to use:** new features with clear requirements, business logic, API endpoints, utility functions, bug fixes (write a test that reproduces the bug first).

**Prerequisites:** a spec with a comprehensive Testing Strategy section (run the [`spec` workflow](#workflow-spec) first).

**TDD principles**
- **Red:** write a failing test first (test what doesn't exist yet).
- **Green:** write minimal code to make the test pass (simplest implementation).
- **Refactor:** improve code quality while keeping all tests passing.
- **Iterate:** repeat for each requirement until the feature is complete.

**Steps**

1. **Preparation**
   - Read the specification file (`specs/features/<feature-name>.md`).
   - Extract all functional requirements and acceptance criteria. In this template the requirements are the parts of "Proposed Change".
   - Review the Testing Strategy section. This is your roadmap.
   - Prioritize: start with core logic, then edge cases, then integrations.
   - Set up test infrastructure (test files, fixtures, mocks).
   - Verify the test framework runs with an empty test.
2. **TDD cycle**: for EACH requirement:

````text
Phase 1: RED (Write Failing Test)
├── Pick the next unimplemented requirement from spec
├── Write a test that describes the desired behavior
│   ├── Test name describes the requirement
│   ├── Given: set up test data and mocks
│   ├── When: call the function/method that doesn't exist yet
│   └── Then: define expected outcome
├── Write ONLY the test — NO implementation code
└── Run test → confirm it FAILS for the right reason

Phase 2: GREEN (Make Test Pass)
├── Write the SIMPLEST code that makes the test pass
├── Implement ONLY what's needed for THIS test
├── Do not over-engineer or optimize
├── Run test → confirm it PASSES
└── Run ALL tests → confirm no regressions

Phase 3: REFACTOR (Improve Code)
├── Review implementation for improvements:
│   ├── Remove duplication (DRY)
│   ├── Improve naming
│   ├── Extract reusable functions
│   └── Improve readability
├── Run ALL tests after EACH refactoring
└── CRITICAL: Tests must stay green throughout
````

3. **Edge cases and error conditions**: after core functionality works, repeat the TDD cycle for:
   - Invalid inputs (null, empty, wrong type).
   - Boundary conditions (min/max values, empty arrays).
   - Error scenarios (network failures, database errors).
   - Each edge case: RED → GREEN → REFACTOR.
4. **Integration tests (if applicable)**: once unit tests pass, apply the same TDD cycle for integration:
   - Test interactions between modules, API endpoints, database.
   - RED: write an integration test that fails.
   - GREEN: wire up components to make it pass.
   - REFACTOR: improve integration code.
5. **E2E tests (if applicable)**: once integration works, apply the TDD cycle for user flows:
   - RED: write an E2E test for the complete user journey.
   - GREEN: complete the implementation to make the flow work.
   - REFACTOR: improve UX/code.
6. **Continuous validation**
   - Run the full test suite frequently.
   - Check test coverage against the spec's target.
   - If coverage is below target, identify untested paths and write tests.
7. **Verify against spec**
   - Review every requirement in the spec: does it have tests?
   - Review every AC: is it met?
   - All tests pass? Coverage target met?
8. **Final refactoring pass**
   - Review ALL implementation code for final improvements.
   - Run the full test suite after each change.
   - All tests must remain green.

**Test template**

````typescript
describe('[FunctionName]', () => {
  it('should [expected behavior] when [condition]', () => {
    // Given: [setup — preconditions]
    // When: [action — call the function]
    // Then: [assertion — verify result]
  });

  it('should [handle edge case] when [boundary condition]', () => {
    // Given / When / Then
  });

  it('should [error behavior] when [invalid input]', () => {
    // Given / When / Then
  });
});
````

The template is shown in TypeScript. Use the test framework and language chosen for this project (see `docs/development.md`).

**TDD best practices**
- **Baby steps:** smallest possible test, then smallest code to pass it.
- **Test first, always:** never write implementation before writing the test.
- **One test at a time:** focus on one test before writing the next.
- **Refactor fearlessly:** with tests as a safety net, refactor aggressively.
- **Keep tests fast:** unit tests should run in milliseconds.
- **Meaningful names:** test names should describe what they verify.
- **Test behavior, not implementation:** test what code does, not how.
- **No skipping RED:** always verify the test actually fails first.

**TDD progress tracking**

Track requirement status: `❌ No test → 🔴 RED → 🟢 GREEN → ✅ Refactored`

**In this project**
- The failing tests come from the spec's Testing Strategy, and each one traces to an acceptance criterion (see Rules). Take the tasks in the spec's `## Tasks` section in order, and tick each one when its tests pass.
- For a bug fix with no spec, the test that reproduces the bug is the Red step. Keep it as the regression test.
- This is the Implement phase of the spec workflow, and the way to run the Develop step.

### Workflow: develop
**Goal:** Implement code following the spec and project patterns.

**Steps:**

1. **Check for spec:** if it is a complex task, read `specs/features/<name>.md`. If none exists, ask whether to create one first. (A spec is required for the changes listed under "When required" in [Workflow: spec](#workflow-spec).)
2. **Research patterns:** navigate Tier 2 and Tier 3 docs for the affected subsystem. Read `patterns.md` for reusable patterns.
3. **Implement:** follow documented patterns. Match existing code style. Update only files listed in the spec. If a file that is not listed needs to change, update the spec first (see Rules).
4. **TDD:** use the acceptance criteria from the spec as test cases. Run the [`tdd` workflow](#workflow-tdd).
5. **Update docs:** update the affected Tier 2/3 docs. Mark the spec status as "In Progress" → "Done".

### Workflow: review
**Goal:** Comprehensive multi-pass review of an implementation against its specification, including security, architecture, performance, and testing audits.

**When to use:** after feature implementation is complete, before marking as production-ready, or when reviewing changes for correctness.

Review can run during development. The final gate before merging is [Workflow: audit](#workflow-audit), which runs this workflow for depth.

**Steps:**

1. **Preparation**
   - Identify the specification file (`specs/features/<feature-name>.md`).
   - Read the complete specification.
   - Identify all files created/modified for this feature.
   - Read all implementation files.
   - Locate test files.

2. **Spec compliance audit**
   - **a. Requirements verification:** for each functional requirement in the spec, mark it:
     - ✅ Fully implemented and working
     - ⚠️ Partially implemented or has limitations
     - ❌ Not implemented

     Document evidence (file names, line numbers, test results).
   - **b. Acceptance criteria:** for each AC in the spec, mark it as met ✅ or unmet ❌. Calculate: X/Y acceptance criteria met.
   - **c. Files verification:** compare "Files to Modify" in the spec with the actual files changed. Document any missing or unexpected files.
   - **d. API contract verification (if applicable):** for each endpoint specified, verify the implementation exists. Check that request/response formats match the spec.

3. **Test coverage audit**

   | Category | Spec Requires | Actually Written | Coverage |
   |---|---|---|---|
   | Unit tests | [count] | [count] | [X]% |
   | Integration tests | [count] | [count] | [X]% |
   | E2E tests | [count] | [count] | [X]% |

   - Compare the spec's test cases with the implemented tests.
   - Run the test coverage tool and compare it to the spec's target.
   - List missing tests explicitly.
   - Identify tests that are specified but not written.

4. **Security audit**
   - **a. Input validation:**
     - All user inputs validated?
     - SQL injection vulnerabilities (raw queries, string concatenation)?
     - XSS vulnerabilities (`innerHTML`, `dangerouslySetInnerHTML`, `eval`)?
   - **b. Authentication and authorization:**
     - Auth mechanisms correct?
     - Hardcoded credentials?
     - API endpoints properly protected?
   - **c. Data protection:**
     - Secrets in code (API keys, passwords, tokens)?
     - Sensitive data in logs?
     - Environment variables used for secrets?
   - **d. Dependencies:**
     - Run a security audit (`npm audit`, `pip-audit`, etc.).
     - Known vulnerabilities in dependencies?

5. **Architecture audit**
   - **a. Code organization:**
     - Separation of concerns (UI, business logic, data access)?
     - Circular dependencies?
     - Code smells (God classes, duplicated code)?
   - **b. Design patterns:**
     - Consistent with the project architecture (`docs/architecture.md`)?
     - Patterns applied correctly?
   - **c. Data flow:**
     - Trace data flow end-to-end.
     - Error propagation correct?
     - Proper async/await usage?
   - **d. Scalability:**
     - N+1 query problems?
     - Pagination implemented?
     - Memory leaks (unclosed connections, event listeners)?
     - Algorithmic complexity acceptable?

6. **Performance audit**
   - Database query efficiency.
   - API response times.
   - Caching opportunities.
   - Bundle sizes (frontend).
   - Unnecessary re-renders or watchers.
   - Asset optimization.

**Output format:**

````markdown
## Review Report: [Feature Name]

### Executive Summary
- Spec compliance: [X]%
- Test coverage: [X]% (target: [Y]%)
- Security issues: [X] critical, [Y] high, [Z] medium
- Production ready: Yes / No / Partial

### Spec Compliance
| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| FR-1 | [desc] | ✅/⚠️/❌ | [file:line] |

### Security Findings
| # | Severity | File:Line | Issue | Recommendation |
|---|----------|-----------|-------|----------------|

### Architecture Findings
| # | Severity | File:Line | Issue | Recommendation |
|---|----------|-----------|-------|----------------|

### Performance Findings
| # | Severity | File:Line | Issue | Recommendation |
|---|----------|-----------|-------|----------------|

### Missing Tests
[List of tests specified but not written]

### Verdict: APPROVE | REQUEST CHANGES | BLOCK
[1-2 sentence recommendation for what to do next]
````

The spec template has no numbered functional requirements. In the "Requirement" column, list the numbered parts of "Proposed Change" or the acceptance criteria (AC1, AC2, ...) and use their IDs in the "#" column.

**Review principles**
- **Be honest:** don't claim 100% if it's 78%. Identify real gaps.
- **Be specific:** cite line numbers, file names, test names.
- **Be critical but constructive:** for each issue, suggest a fix.
- **Be thorough:** check everything the spec requires.
- **Be practical:** distinguish "must fix before production" from "nice to have later".

### Workflow: audit
**Goal:** Post-implementation audit: verify completeness, then run [`review`](#workflow-review) for depth.

**When to use:** after a feature is "done", before merging or marking complete. Unlike `review` (which can run during development), `audit` is the final gate.

This is the Audit step of the [spec-driven workflow](#part-2-spec-driven-development).

**Steps:**

1. **Completeness check**
   - Read the spec (`specs/features/<feature-name>.md`).
   - Verify every acceptance criterion is met (✅ / ❌).
   - Verify every file listed in the spec was created/modified.
   - Verify documentation was updated (Tier 2/3 docs, `content-plan.md`).
   - Verify the spec status is updated to "Done".
2. **Run review**
   - Execute the [`review` workflow](#workflow-review) (above) for a full multi-pass audit.
   - This covers: spec compliance, tests, security, architecture, performance.
3. **Documentation audit**
   - Run the [`document` workflow](#workflow-document) in scan-only mode. In scan-only mode, run steps 1 and 2 and produce the Documentation Scan Report, but do not change any files.
   - Verify new code has corresponding documentation.
   - Verify cross-tier references are intact.
4. **Final test run**
   - Run the complete test suite.
   - Verify coverage meets the spec target.
   - No skipped or TODO tests.
5. **Produce audit summary**

````markdown
## Audit Summary: [Feature Name]

### Completeness
- Acceptance criteria: [X/Y] met
- Files: [all present / missing: ...]
- Docs updated: Yes / No
- Spec status: Done / Not updated

### Review Results
[Link to or embed review report]

### Verdict: PASS | FAIL | REQUIRES ADJUSTMENT
[What must be fixed before this can ship]
````

**Max retries:** if the audit fails, fix the issues and re-audit. Maximum 3 cycles before escalating to human review.

### Workflow: fix
**Goal:** Diagnose and resolve errors systematically.

**Steps:**

1. **Gather context:** check [Learnings](#learnings) (`docs/learnings.md`), affected Tier 2/3 docs, error messages.
2. **Hypothesize:** identify 1-2 likely causes.
3. **Validate:** add temporary logging, run tests.
4. **Fix:** smallest change that resolves the issue.
5. **Verify:** all tests pass, no regressions.
6. **Document:** record the solution in `docs/learnings.md`.

Do not loop more than 3 times without asking for help.

**Notes**
- For a bug in behavior, write the test that reproduces it first (see [Workflow: tdd](#workflow-tdd)), and keep it as the regression test.
- Remove the temporary logging from step 3 before step 5.
- `docs/learnings.md` is a log, newest entry first. Create it on the first fix. Write each entry with the [Learnings entry template](#entry-template), add the date, and link to the Tier 2/3 doc it relates to.
- If the fix shows that a doc is wrong or missing, update it, or mark it `Outdated` in `docs/content-plan.md`.

---

### PART 3: Skills & Tools
Register CLI tools, define sub-agents, and configure verification hooks. This section makes custom tools discoverable and usable by AI agents.

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

### Custom Skills
Each skill is documented in `.agents/skills/<name>/SKILL.md` following the [OpenAI Codex skills convention](https://developers.openai.com/codex/skills/). Each SKILL.md has YAML frontmatter with `name` and `description` (trigger conditions), followed by command, options, requirements, and examples.

A skill is a reusable, self-contained instruction set for a recurring task.

- Store project skills in `.agents/skills/<name>/SKILL.md` (plus any helper scripts or templates in the same folder).
- Template for a `SKILL.md`:
  ````markdown
  ---
  name: skill-name
  description: One sentence on what it does and when to use it (the trigger conditions).
  ---

  ## Command
  [How to run it]

  ## Options
  [Flags and arguments]

  ## Requirements
  [Tools, access or setup it needs]

  ## Examples
  [One or more worked examples]
  ````
- Before starting a task, check whether a matching skill exists and follow it. If a skill conflicts with this file, this file wins; tell the user.
- Create a new skill only when a procedure has recurred or the user asks. Keep it short and specific, with one task per skill.
- Candidate skills for this project, to be created when needed:
  - `new-spec`: scaffold `specs/features/<feature>.md` from the template in [Spec-Driven Development](#part-2-spec-driven-development).
  - `add-adr`: create the next numbered ADR (see [Documentation](#1-documentation)).
  - `receipt-fixture`: generate a synthetic receipt fixture for tests. It must never use real data.

#### Skill Inventory
| Skill | Command | Description |
|---|---|---|
| `gemini` | `npm run gemini` | Text generation, vision, document analysis, grounded search via Gemini API |
| `html-to-md` | `npm run html-to-md` | Scrape webpage to Markdown |
| `github-cli` | `npm run github` | GitHub PRs, issues, releases, repos, workflows |
| `google-search` | `npm run google-search` | Real-time Google Search via Gemini grounding |
| `datetime` | `npm run datetime` | Current date/time in various formats and timezones |
| `coding-preferences` | `npm run coding-preferences` | Store and retrieve personal coding preferences (SQLite in skill folder) |

- Each skill listed here must have a `.agents/skills/<name>/SKILL.md`. Add a row when a skill is created and remove it when the skill is removed.
- `gemini` sends its input to an external API. Follow the network rule in Principles: do not send repository contents or receipt data to it without the user's approval. Keep the API key in an environment variable, never in code or docs.

### Project tools
Register any project-specific scripts or MCP/tool integrations here so agents can discover them. Remove this note when the first one is added.

| Tool | Purpose | How to run | Notes |
|---|---|---|---|
| _none yet_ | | | |

### Sub-Agent Definitions
Define specialized agents with non-overlapping responsibilities.

#### Agent template
````markdown
### [Agent Name]
**Role:** [1 sentence — what this agent does]
**Skills:** [List of registered skills this agent can use]

**Process:**
1. [Step]
2. [Step]
3. [Step]

**Can:** [Permitted actions]
**Cannot:** [Forbidden actions — prevents overlap with other agents]

**Output Format:**
[Define structured output this agent produces]
````

#### Principles
- **Single Responsibility:** each agent has ONE job, no overlap.
- **Skills Bridge:** agents use registered skills (see [Skill Inventory](#skill-inventory)) to invoke tools.
- **Constraints Prevent Drift:** "Cannot" is as important as "Can".
- **Structured Output:** every agent produces a defined format.
- **Chain Results:** each agent's output feeds the next agent's input.

#### Defined agents
| Agent | Role |
|---|---|
| _none yet_ | |

Add each new agent as a `###` section below this table using the template, and list it in the table. An agent may only list skills that are in the Skill Inventory.

### Hooks & Verification
Hooks are quality gates that run at defined points in the pipeline.

| Hook | When | Purpose |
|---|---|---|
| `PreToolUse` | Before a tool executes | Approve dangerous operations |
| `PostToolUse` | After a tool completes | Validate output format and quality |
| `Stop` | Agent marks task complete | Final verification before "done" |

#### Hook configuration template
````markdown
## Hooks

### PreToolUse
- Require approval for: [list dangerous operations]
- Block: operations outside the agent's "Can" list

### PostToolUse
- Validate: output matches agent's defined format
- Check: all required sections present
- Log: action for audit trail

### Stop (Completion Gate)
- Verify: [acceptance criteria met / coverage threshold / all agents ran]
- Max retries: [N] cycles before escalating to human
````

#### Hooks for this project
These follow rules already in this file. Add hooks for each sub-agent in its own section when it is defined.

- **PreToolUse**
  - Require approval for: deleting files, force-pushing or rewriting history, dropping data, changing remotes, installing global packages, creating or merging PRs and releases, and sending repository contents or receipt data to an external service (see Principles).
  - Block: reading or modifying files outside the repository, and any operation outside the agent's "Can" list.
- **PostToolUse**
  - Validate: output matches the format the agent or workflow defines (for example the review report or the audit summary).
  - Check: all required sections are present.
  - Log: the action taken, for the audit trail.
- **Stop (completion gate)**
  - Verify: the spec's acceptance criteria are met, the tests pass, the coverage target is met, and docs and `docs/content-plan.md` are updated (see [Workflow: audit](#workflow-audit)).
  - Max retries: 3 cycles before escalating to human review.

Hooks are rules for the agent unless they are also configured in the tool the agent runs in. Where a hook can be enforced by tooling, register it there and record it in the table above as enforced.

### Learnings
Check this section FIRST when encountering errors. Add solutions here so the same problem is never debugged twice.

The entries are kept in `docs/learnings.md` (newest first), so that this file stays short. Read that file before debugging, and add an entry after every fix (see [Workflow: fix](#workflow-fix)).

#### Entry template
````markdown
### [Short description]
**Context:** [When/where this occurs]
**Symptom:** [What you see]
**Root cause:** [Why it happens]
**Solution:** [How to fix]
**Prevention:** [How to avoid in future]
````

### Reporting
When you finish, state in a few lines: what changed, how you verified it (commands and results), and anything left open or uncertain. If spec or doc updates were needed, say which files.
