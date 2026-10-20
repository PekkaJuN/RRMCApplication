---
name: review-audit
description: Use after a feature is implemented to review it against its spec (compliance, tests, security, architecture, performance), and as the final audit gate before the spec is marked Done.
---

# review-audit

Audit step of SDD. `review` can run any time during development; `audit` is review plus the
completeness checks, and is the final gate.

## Needs

- The spec `specs/features/<feature>.md` and the list of changed files (`git diff --stat`).

## Review

1. **Spec compliance.** For each part of the Proposed Change and each AC: ✅ met, ⚠️ partial,
   ❌ missing, with evidence (file and test name). Compare Files to Modify with the files
   actually changed. Check API request and response formats against the spec.
2. **Tests.** Every Testing Strategy row has a test; tests pass; coverage meets the target.
   List missing tests.
3. **Security and privacy** (this project's priorities):
   - no real receipt data, OCR text or database in the repository or test fixtures;
   - no receipt content in logs or error messages;
   - backend binds to `127.0.0.1`; CORS limited to the dev origin;
   - no external network calls with receipt data; Ollama is local;
   - SQL uses parameters, never string concatenation; no `dangerouslySetInnerHTML`;
   - uploaded or imported file names and types are validated (path traversal);
   - no secrets in code; Sheets key outside the repository;
   - dependency audit: `pip-audit`, `npm audit`.
4. **Architecture.** Separation of OCR, parsing, categorization, calculation, storage and
   export; exporters behind the common interface; consistent with `docs/architecture.md`.
5. **Correctness hot spots.** Money in integer cents; ISO weeks; grouping by purchase date;
   image moved only after commit; duplicates detected.
6. **Performance.** Model loaded once at start; no per-line model calls where one call per
   receipt works; no N+1 queries for totals.

## Audit (final gate)

Run the review, then also check:

- every AC met; every listed file changed; docs and `docs/content-plan.md` updated;
- the `document` skill in scan-only mode finds no undocumented or orphaned items for this change;
- full test suite, lint and type checks pass; no skipped or TODO tests;
- spec status set to `Done` in the spec and in `specs/README.md`.

If the audit fails: fix, then re-audit. After three failed cycles, stop and ask the user.

## Output

```markdown
## Audit: <feature>
- Acceptance criteria: X/Y met
- Tests: pass/fail, coverage X % (target Y %)
- Security: N critical, N high, N medium
- Docs updated: yes/no; spec status: <status>

| # | Severity | File | Finding | Recommendation |
|---|---|---|---|---|

Verdict: PASS | REQUEST CHANGES | FAIL — <one sentence on what to do next>
```

Be honest and specific. Separate "must fix" from "later".
