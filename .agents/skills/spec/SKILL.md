---
name: spec
description: Use before implementing a new feature, an API change, an architectural change or a change across several subsystems. Writes specs/features/<feature>.md in three phases (Specify, Plan, Tasks) with user approval between phases.
---

# spec

Spec-driven development: define *what* and *why* first, then *how*, then ordered tasks.
The approved spec is the input to the `tdd` skill.

## Needs

- The user's request, and research findings if a research step was run.
- `docs/content-plan.md` and the Tier 1/Tier 2 docs relevant to the feature.
  In greenfield, missing docs are listed in the spec's "Files to Modify" instead of blocking.

## Layout

```
specs/
  README.md            index: one row per spec with status
  TEMPLATE.md          the spec template (single source)
  features/
    <feature>.md       spec, then ## Plan, then ## Tasks, in one file
```

Use a short kebab-case name, e.g. `receipt-import.md`. One feature per file; split large features.
Create folders on first use. Do not scaffold empty specs.

## Phases

Do not start a phase until the user agrees to the previous one, unless they said to proceed
autonomously.

### 1. Specify (what and why, never how)

Copy `specs/TEMPLATE.md` to `specs/features/<feature>.md` and fill in:

- Problem statement, current behavior (with doc links), proposed change, and **out of scope**.
- Acceptance criteria `AC1`, `AC2`, ... in Given/When/Then with **precise expected values**.
  Include error and edge cases as their own ACs. For this project consider:
  unreadable or partial receipts, OCR noise in product names, unknown products,
  line sum not matching the receipt total, discounts and deposits (pantti), weighed items,
  duplicate images, unsupported file types, a model that is not running or returns invalid JSON,
  ISO week boundaries across months and years.
- Files to Modify, including docs to create or update.
- Risk, Testing Strategy, Related Documentation (both mandatory).
- Mark ambiguity in place as `[NEEDS CLARIFICATION: ...]` and ask. Do not guess.

Set status `Review` when the Readiness checklist passes, and ask the user to approve.

### 2. Plan (how)

Append `## Plan`: components, data flow, data model changes, interfaces, dependencies to add
and why. Record significant decisions as ADRs. Check the plan against every AC and refine
Files to Modify. Ask for approval.

### 3. Tasks

Append `## Tasks`: small, ordered, independently verifiable tasks as `- [ ]` checkboxes.
Each task names the AC IDs it satisfies and the test that proves it. Ask for approval, then
hand over to the `tdd` skill.

## Status

`Draft` → `Review` → `Approved` → `In Progress` → `Done`.
Record it in the spec's Overview and in `specs/README.md`. Only the user sets `Approved`.
`tdd` sets `In Progress`; `review-audit` confirms `Done`.

## Rules

- Every AC has at least one test row; every part of the proposed change has at least one AC.
- If an AC cannot fail, it proves nothing. Rewrite it.
- If implementation shows the spec is wrong, stop and update the spec first.
- Keep Files to Modify current during implementation.

## Readiness checklist

- [ ] Every AC is Given/When/Then with a precise expected value
- [ ] Another person could write a test from each AC without asking
- [ ] Error and edge cases have their own ACs
- [ ] Every AC maps to at least one test row; unit and integration rows exist
- [ ] E2E rows exist for each user journey through the UI, or the spec says why none apply
- [ ] Coverage target is stated
- [ ] Files to Modify lists code and docs
- [ ] Risk names what could break and how to roll back
- [ ] Related Documentation links the relevant docs
- [ ] No `[NEEDS CLARIFICATION]` remains
