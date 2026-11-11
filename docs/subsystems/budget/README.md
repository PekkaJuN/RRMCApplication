# Budget

Navigation: ↑ [Architecture](../../architecture.md) | → [API reference](../../api-reference.md#budget) | → [Calculation](../calculation/README.md#budget-comparison) | → [Categorization](../categorization/README.md) | → [Storage](../storage/README.md) | → [UI](../ui/README.md)

## Overview

Budget serves the monthly budget and its comparison with spending (PRD FR-50). The user sets
one amount per **budget row**: a group, or a category without a group. The Vertailu page
compares those amounts with the spending of one period and its ISO weeks.

The package reads the data and hands it to calculation; it holds no sum rule of its own:

- [calculation](../calculation/README.md#budget-comparison) builds the comparison period and
  computes the rows, the weekly budgets and the totals;
- [storage](../storage/README.md#interfaces) reads and writes the budgets, and reads the
  lines of reviewed receipts and the two counts;
- [categorization](../categorization/README.md) gives the category list order
  (`CategoryService.list()`), which is the row order, and moves a budget when its category
  moves into a group.

It is a separate package because a budget is not a catalog rule, and the comparison counts
other lines than the totals: only reviewed receipts. Figures are never stored: every
request computes them, so they follow the latest edits. The budget has no history, so a
change also changes the comparison of earlier months.

## Key Files and Entry Points

- @backend/app/budget/routes.py — `create_budget_router(settings)`: `GET /api/budget`,
  `PUT /api/budget/{id}` and `GET /api/budget/comparison`, one connection per request
- @backend/app/budget/service.py — `BudgetService`: `rows()`, `save()`, `comparison()`
- @backend/app/budget/schemas.py — the API shape; a body refuses a float or a string
- @backend/app/budget/errors.py — `NotABudgetRowError`, `InvalidBudgetAmountError`

## Interfaces

The endpoints, their shape and error codes are in the
[API reference](../../api-reference.md#budget).

| Method | Does | Raises |
|---|---|---|
| `BudgetService(catalog, receipts).rows()` | Reads the budget rows and the total budget | nothing |
| `BudgetService.save(item_id, amount_cents)` | Checks the id, that it is a budget row and the amount from 0 to `AMOUNT_LIMIT`, in that order, then saves | `NotFoundError`, `NotABudgetRowError`, `InvalidBudgetAmountError` |
| `BudgetService.comparison(month, kind)` | Parses the period, reads the reviewed lines, the catalog, the budgets, the unreviewed count of the period and the undated count in one transaction, and returns the comparison | `InvalidPeriodError` |

## Data Flow

1. The comparison route passes `month` and `period` as plain optional strings. FastAPI
   validates nothing, so every missing or malformed value reaches `comparison_period` and
   becomes `invalid_period`, not the generic `invalid_request`.
2. The service reads, in one transaction, `dated_lines(start, end, reviewed_only=True)`,
   `CategoryService.list()`, `budgets()`, `count_unreviewed(start, end)` and `count_undated()`.
3. `budget_comparison(period, lines, catalog, budgets)` computes the figures.
4. The answer holds category and group names and cents only; no product name is read
   (NFR-3). The request log has no query string (@backend/app/logging_setup.py).

### Catalog changes

A budget belongs to a `categories` row by its id, so a rename keeps it and a delete removes
it (`ON DELETE CASCADE`). When `CategoryService.update` puts a budget row into a group, it
adds the row's budget to the group's and removes the row's own, in the update's transaction,
so the total budget does not change. The sum may exceed `AMOUNT_LIMIT`, which applies only
to amounts the user types. An item that leaves a group starts at 0, and the group keeps its
budget.

## Dependencies

- Uses: [calculation](../calculation/README.md),
  [categorization](../categorization/README.md) (the category list order, `NotFoundError`),
  [storage](../storage/README.md), [totals](../totals/README.md) (`ColumnOut`,
  `InvalidPeriodError`).
- Used by: the [UI](../ui/README.md) Budjetti and Vertailu pages;
  [export](../export/README.md) for the comparison PDF and CSV files
  (`BudgetService.comparison`).

## Modules

None yet.

## Known Issues and Gotchas

- Vertailu and Yhteenveto can show different spending for one month: only Vertailu leaves
  out unreviewed receipts. The page shows how many it left out.
- The same month name means different dates in the two kinds of period, so the page always
  shows the covered dates.
- The 15–14 period is a ready choice only here. The Yhteenveto page and its exports reach
  the same days as a free date range (PRD FR-49).

## Related Documents

- [Monthly budget spec](../../../specs/features/budget.md)
- [Architecture](../../architecture.md#component-map)
