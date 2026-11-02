# Calculation

Navigation: ↑ [Architecture](../../architecture.md) | → [Review](../review/README.md) | → [Totals](../totals/README.md) | → [Storage](../storage/README.md)

## Overview

Calculation computes sums in integer cents (NFR-6). It changes no data and does no I/O.

It has the receipt check (FR-20) and the category subtotals of one receipt (FR-19, FR-44),
used by [review](../review/README.md), and the period totals: per category and group, per
ISO week and per month of a period (FR-22–FR-25, FR-44), used by
[totals](../totals/README.md).

## Key Files and Entry Points

- @backend/app/calculation/receipt_check.py — `check_receipt`, `category_subtotals`
- @backend/app/calculation/period.py — `parse_period`, `Period`, `Column`, `PeriodError`
- @backend/app/calculation/period_totals.py — `period_totals`, `TotalLine`, `RowCategory`,
  `TotalsRow`, `PeriodTotals`

## Interfaces

| Function | Returns |
|---|---|
| `check_receipt(total_cents, amounts)` | `ReceiptCheck(line_sum_cents, difference_cents, warning)` |
| `category_subtotals(lines, order)` | `list[Subtotal(category_id, amount_cents)]` |

### Rules

- The **line sum** is the sum of every line amount, deposit refunds included: the printed
  total already has the refunds deducted (FR-20).
- The **difference** is the total minus the line sum; `None` without a total.
- The **warning** is on when the difference is not 0 or the receipt has no total.
- A **category subtotal** sums the lines of one category. Deposit refunds are in no subtotal
  (FR-44). Lines without a category that are not refunds form one subtotal with
  `category_id` `None`, listed last. The others follow `order`, the category ids in catalog
  order; only categories with lines are listed.

### Period totals

| Function | Returns | Raises |
|---|---|---|
| `parse_period(unit, first, last)` | `Period(unit, first, last, start, end)` | `PeriodError` |
| `Period.week_columns()`, `Period.month_columns()` | `list[Column(key, start, end, partial)]` in date order | nothing |
| `period_totals(period, lines, catalog)` | `PeriodTotals(period, weeks, months, rows, week_totals, month_totals)` | nothing |

- A **period** is whole calendar months (`unit` `month`, bounds `2026-10`) or whole ISO
  weeks (`week`, bounds `2026-W40`), from `first` to `last` inclusive. `start` is the first
  day of the first unit, `end` the last day of the last. It is at most 24 months or 104
  weeks, in the years 1–9998 (the columns of 9999 would run past `date.max`). A malformed bound, a week that does not exist (`2027-W53`), a missing value, an
  unknown unit, `first` after `last`, or a longer period raises `PeriodError`.
- A **column** is each ISO week and each month with a day in the period, clipped to the
  period's days; it is **partial** when it was clipped. October 2026 has the week columns
  `2026-W40` (1–4 Oct, partial) to `2026-W44` (26–31 Oct, partial). A week's key uses its
  ISO year: 29 Dec 2025 – 4 Jan 2026 is `2026-W01`.
- `period_totals` skips deposit refunds (FR-44) and lines outside the period, and sums the
  rest per category and column. Rows follow `catalog` (the category list order): a group
  when one of its categories has a line, with those categories as its `categories` and
  their column sums as its amounts; a category without a group when it has a line; last a
  `none` row for lines without a category. A category whose lines sum to 0 is listed. The
  column totals sum the top-level rows, so the `none` row is in them and a group is not
  counted twice. A category id missing from `catalog` cannot happen (`ON DELETE
  RESTRICT`); its lines would be in no row.

## Data Flow

Callers pass plain values: `check_receipt` takes the amounts, `category_subtotals` takes
`SubtotalLine(category_id, amount_cents, is_deposit_refund)` items. The receipt list passes
the line sum that storage computed in SQL as a one-item list.

## Dependencies

- Uses: nothing.
- Used by: [review](../review/README.md), [totals](../totals/README.md).

## Modules

None yet.

## Known Issues and Gotchas

- A category id missing from `order` cannot happen (`ON DELETE RESTRICT` keeps every used
  category); such a subtotal would sort after the known ones and before the lines without a
  category instead of raising.

## Related Documents

- [Receipt review spec](../../../specs/features/receipt-review.md) PC2, Plan P2
- [Category totals spec](../../../specs/features/totals.md) PC1, Plan P1–P2
- [Architecture](../../architecture.md#component-map)
