# Totals

Navigation: ↑ [Architecture](../../architecture.md) | → [API reference](../../api-reference.md#totals) | → [Calculation](../calculation/README.md#period-totals) | → [Categorization](../categorization/README.md) | → [Storage](../storage/README.md) | → [Export](../export/README.md) | → [UI](../ui/README.md)

## Overview

Totals serves `GET /api/totals`: spending per category and group, per ISO week and per
calendar month, by purchase date, for a period the user chooses (PRD FR-22–FR-25, FR-44, FR-49).
It reads the data and hands it to calculation; it holds no sum rule of its own:

- [calculation](../calculation/README.md#period-totals) checks the period, builds the week
  and month columns and computes every total;
- [storage](../storage/README.md#interfaces) reads the dated lines and the two counts;
- [categorization](../categorization/README.md) gives the category list order
  (`CategoryService.list()`), which is the row order.

It is a separate package because the totals span receipts and are also used by the CSV
export (FR-26), so they are computed in one place. Totals are never stored: every request
computes them from the database, so they always reflect the latest edits (FR-24).

## Key Files and Entry Points

- @backend/app/totals/routes.py — `create_totals_router(settings)`: `GET /api/totals`, one
  connection per request
- @backend/app/totals/service.py — `TotalsService.totals(unit, first, last)` →
  `TotalsView(totals, unreviewed_receipts, undated_receipts)`
- @backend/app/totals/schemas.py — the API shape; `from_` is sent as `from`
- @backend/app/totals/errors.py — `InvalidPeriodError` (422 `invalid_period`)

## Interfaces

The endpoint, its shape and its error code are in the
[API reference](../../api-reference.md#totals).

| Method | Does | Raises |
|---|---|---|
| `TotalsService(catalog, receipts).totals(unit, first, last)` | Parses the period, reads the lines dated in it, the unreviewed count of the period, the undated count and the category list in one transaction, and returns the period totals | `InvalidPeriodError` |
| `TotalsService.period(unit, first, last)` | Parses the period | `InvalidPeriodError` |
| `TotalsService.read(period)` | Reads the dated lines and the category list and returns `period_totals`; opens no transaction, so the caller holds one ([export](../export/README.md)) | nothing |

## Data Flow

1. The route passes `unit`, `from` and `to` as plain optional strings. FastAPI validates
   nothing, so every missing or malformed value reaches `parse_period` and becomes
   `invalid_period`, not the generic `invalid_request`.
2. The service reads, in one transaction, `dated_lines(start, end)`,
   `count_unreviewed(start, end)`, `count_undated()` and `CategoryService.list()`.
3. `period_totals(period, lines, catalog)` computes the columns, rows and column totals.
4. The answer holds category and group names and cents only; no product name is read
   (NFR-3). The request log has no query string (@backend/app/logging_setup.py).

## Dependencies

- Uses: [calculation](../calculation/README.md),
  [categorization](../categorization/README.md) (the category list order),
  [storage](../storage/README.md).
- Used by: the [UI](../ui/README.md) Yhteenveto page; [export](../export/README.md) for
  the totals file and the totals PDF; [budget](../budget/README.md) for `ColumnOut` and `InvalidPeriodError`.

## Modules

None yet.

## Known Issues and Gotchas

- Every receipt counts, reviewed or not; `unreviewed_receipts` tells the user which totals
  may still change. A receipt without a purchase date is in no period; `undated_receipts`
  counts them over all receipts, whatever the period.
- `purchase_date` has no index. A full scan of one user's receipts is fast; add an index by
  migration if that changes.

## Related Documents

- [Category totals spec](../../../specs/features/totals.md)
- [Architecture](../../architecture.md#component-map)
