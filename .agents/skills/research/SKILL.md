---
name: research
description: Use when a request is unclear, and before any spec. Read-only. Finds out what the request touches in the docs, specs and code, checks library facts from official sources, and presents findings and open questions for the user. Its findings are the input to the spec skill.
---

# research

The first step of SDD: understand the request before anything is specified. Research reads;
it does not decide or build. The findings feed the `spec` skill, or show that no spec is
needed.

## Needs

- The user's request. If it is too vague to say which subsystem it touches, ask one or two
  questions before starting.

## Rules

- **Read-only.** Do not change code, docs, specs or configuration. The one exception: list
  missing docs as gaps in `docs/content-plan.md`.
- **Receipt data stays local.** Never read `source/` or the database. Never put receipt
  content (images, OCR text, product names from real receipts) into a web search, a fetched
  URL or a prompt to an external service.
- **Repository contents stay local** unless the user approves sending them. Web searches use
  generic terms (library, version, feature), not code or file contents from this project.
- Do not use skills marked *planned* in [AGENTS.md](../../../AGENTS.md#skills) (for example
  `html-to-md` and `gemini`).
- Do not guess. Mark unknowns as `[NEEDS CLARIFICATION: ...]` and list them as open questions.

## Steps

1. **Docs and specs.** Read `docs/content-plan.md` first, then the Tier 1 and Tier 2 docs of
   the affected subsystems, the related requirements in `specs/PRD.md` and the related specs
   in `specs/features/`. Note which requirements (FR, NFR) and release the request belongs to.
2. **Code.** Search the code for existing patterns the change should follow or reuse (for
   example the exporter interface for a new export). Note the files and modules involved.
3. **External facts.** For libraries and services, use official documentation. Note the
   version the facts apply to and the version the project uses (`backend/pyproject.toml`,
   `frontend/package.json`). Cite each web source with its URL.
4. **Delegate bounded lookups** (finding a fact in docs, listing ACs, checking links) to the
   `checker` subagent ([model routing](../../../AGENTS.md#model-routing)). Draw the
   conclusions yourself.
5. **Present** the findings in the format below, then stop. Do not start the spec until the
   user says so.

## Output

```markdown
## Research: <topic>
- Request type: feature | change | bug | docs | config | question
- Complexity: small | medium | large — <one sentence why>
- Spec needed: yes | no — <reason, per the SDD rules in AGENTS.md>
- Requirements: <FR/NFR IDs and release, or "none yet">
- Affected subsystems: <names>

### Docs and specs read
- <path> — <what it says that matters>

### Existing code and patterns
- <path> — <pattern to follow or reuse>

### External facts
- <fact> — <library and version> — <source URL>

### Draft outline
<For a spec: the problem, the proposed scope, what is out of scope, candidate ACs.
For no spec: the smallest change.>

### Risks and trade-offs
- <privacy, security, data migration, performance>

### Open questions
1. <question for the user>
```

Keep it short. Give a recommendation where there is a choice, not only the options.
