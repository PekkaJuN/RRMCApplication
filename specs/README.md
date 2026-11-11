# Specs

Feature specs for RRMCApplication. Requirements are in [PRD.md](PRD.md); new specs start
from [TEMPLATE.md](TEMPLATE.md). The workflow is in `.agents/skills/spec/SKILL.md`.

| Order | Spec | Status | Implements |
|---:|---|---|---|
| 1 | [Project foundation](features/foundation.md) | Done | FR-29–FR-32, NFRs for runtime, tooling and app shell |
| 2 | [Product management](features/product-management.md) | Done | FR-11, FR-33–FR-39, PRD 6.9 |
| 3 | [Receipt import](features/receipt-import.md) | Done | FR-1–FR-5, FR-45; receipt record with image identifier |
| 4 | [Model evaluation](features/model-evaluation.md) | Done | PRD open question 4; NFR-8 (development tool) |
| 5 | [Receipt reading](features/receipt-reading.md) | Done | FR-6–FR-10, FR-31; PRD open question 4 |
| 6 | [Line categorization](features/categorization.md) | Done | FR-12–FR-15 (backend), FR-36, FR-44; PRD open question 6 |
| 7 | [Receipt review](features/receipt-review.md) | Done | FR-16, FR-17, FR-19–FR-21, FR-13 (UI) |
| 8 | [Line editing](features/line-editing.md) | Done | FR-18 (without quantity and unit price), FR-43, FR-19, FR-44 for edits |
| 9 | [Category totals](features/totals.md) | Done | FR-22–FR-25, FR-44 for totals |
| 10 | [CSV export](features/csv-export.md) | Done | FR-26, FR-27, FR-44 for exported totals |
| 11 | [Visual style and accessibility](features/styling.md) | Done | NFR-16, NFR-1 for UI resources |
| 12 | [Receipt deletion and manual receipts](features/receipt-management.md) | Done | FR-46, FR-47 (new) |
| 13 | [Monthly budget](features/budget.md) | Done | FR-50 (new) |
| 14 | [Finnish date field](features/date-field.md) | Done | FR-51 (new) |
| 15 | [Free date range for totals](features/date-range-totals.md) | Done | FR-49 |
| 16 | [PDF export](features/pdf-export.md) | Done | FR-48 |
| 17 | [Test container isolation](features/test-isolation.md) | Done | NFR-1, NFR-4, NFR-12 for development commands |
| 18 | [Agent guardrails](features/agent-guardrails.md) | Done (AC24 deferred) | NFR-1, NFR-4, AGENTS.md Guardrails for agents |
| 19 | [Budget comparison CSV export](features/comparison-csv-export.md) | Done | FR-52 (new), FR-27 |
| 20 | [Finnish dates in the CSV files](features/finnish-csv-dates.md) | Done | FR-26 (changed) |
