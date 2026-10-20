---
name: tdd
description: Use to implement an approved spec, or to fix a bug, with test-driven development (Red, Green, Refactor). Works through the spec's Tasks in order and keeps code, tests and docs in sync.
---

# tdd

Develop step of SDD. Implements `specs/features/<feature>.md` task by task, test first.

## Needs

- A spec with status **Approved**, a complete Testing Strategy and a `## Tasks` section.
  If any is missing, stop and say what. Do not start without approval.
- For a bug fix without a spec: the error report.

## Tools

| Part | Test framework | Notes |
|---|---|---|
| Backend | pytest (+ pytest-cov) | FastAPI `TestClient`; SQLite in a temp file; Tesseract and Ollama behind interfaces and faked in unit tests |
| Frontend | Vitest + Testing Library | API mocked at the fetch layer |
| E2E | Playwright | Only for journeys listed in the spec |

Tests that need a real Ollama or Tesseract are marked (e.g. `@pytest.mark.ollama`) and are not
part of the default run. Commands are in `AGENTS.md` → Commands.

## Steps

1. **Prepare.** Read the spec. Set its status to `In Progress` (spec and `specs/README.md`).
   Read the docs listed under Related Documentation. Make sure the test runner runs an
   empty test.
2. **For each task, in order:**
   - **Red:** write the test from the Testing Strategy row. Name it after the behavior and
     reference the AC (e.g. `test_ac3_line_sum_mismatch_warns`). Run it and confirm it fails
     *for the right reason* (not an import error or typo).
   - **Green:** write the simplest code that makes it pass. Run the whole suite.
   - **Refactor:** remove duplication, improve names. Run the whole suite after each change.
   - Tick the task's checkbox only when its tests pass.
3. **Edge and error cases:** repeat the cycle for every error AC (invalid input, empty input,
   model unavailable, invalid model output, database errors).
4. **Integration, then E2E,** as listed in the spec, with the same cycle.
5. **Coverage:** compare with the spec's target. Write tests for untested paths.
6. **Verify:** every AC has a passing test; full suite, lint and type checks pass.
7. **Update docs** listed in Files to Modify and `docs/content-plan.md`.
   Then run the `review-audit` skill.

## Rules

- Never write production code before a failing test for it. Never skip Red.
- One test at a time. Baby steps.
- Test behavior, not implementation. Unit tests run in milliseconds.
- Change only files in the spec's Files to Modify. If another file must change, update the
  spec first.
- If the spec turns out wrong or incomplete, stop and update it (and ask the user if an AC
  changes).
- Test data is synthetic. Never add a real receipt as a fixture.

## Bug fix

Write a test that reproduces the bug (Red), fix it (Green), refactor, keep the test as a
regression test, and record the fix in `docs/learnings.md`.

## Progress tracking

Per AC: `❌ no test → 🔴 red → 🟢 green → ✅ refactored`.

## Example (pytest)

```python
def test_ac2_line_sum_mismatch_sets_warning():
    # Given a receipt whose lines sum to 1250 cents and whose total is 1300 cents
    receipt = make_receipt(lines=[1000, 250], total=1300)
    # When it is validated
    result = validate_totals(receipt)
    # Then a mismatch of 50 cents is reported
    assert result.mismatch_cents == 50
```
