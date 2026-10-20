# Feature: <name>

## Overview
- **Status:** Draft | Review | Approved | In Progress | Done
- **Created:** YYYY-MM-DD
- **Affected subsystems:** <links to docs/subsystems/<name>/README.md>

## Problem Statement
What problem this solves and why it is needed.

## Current Behavior
What the system does now. Link the Tier 2/3 docs. In greenfield: "None (new)".

## Proposed Change
What the system should do after implementation. Number the parts (PC1, PC2, ...).

### Out of Scope
What this spec deliberately does not cover.

## Acceptance Criteria
One AC per observable behavior. This is what "done" means.

### AC1: <descriptive name>
**Given** <precondition: system state before>
**When** <action: what the user or system does>
**Then** <observable outcome, with the precise expected value>

### AC2: <error or edge case>
**Given** ...
**When** ...
**Then** ...

## Files to Modify
| File | Change |
|---|---|
| `backend/<path>` | <what and why> |
| `docs/<path>` | <doc to create or update> |

## Risk
- **What could break:** ...
- **Rollback:** ...
- **Dependencies:** external tools or services (Tesseract, Ollama, ...)

## Testing Strategy (MANDATORY)
Each row traces to an AC. Expect more rows than ACs: each AC needs a happy path and at least
one error case. If a row contradicts its AC, the AC is the one that is wrong.

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | `fn` | happy path | ... | ... | ... | ... |
| AC2 | `fn` | error | ... | ... | ... | ... |

### Integration tests
Real SQLite (temporary file) and real FastAPI app; Tesseract and Ollama mocked unless the row
says otherwise.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | ... | `POST /api/...` | ... | 200 |

### E2E tests
One row per user journey through the UI, or write why none apply.
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|

### Coverage target
- Backend: <e.g. 80 %> lines. Money, totals and duplicate detection: every branch tested.
- Frontend: <target>

### Test data
- Synthetic fixtures only (no real receipts): <describe>
- Mocks: <list>

## Related Documentation (MANDATORY)
- Tier 1: <links>
- Tier 2: <links>
- ADRs: <links>

<!-- The Plan phase appends "## Plan" and the Tasks phase appends "## Tasks" below. -->
