# Calculation

Navigation: ↑ [Architecture](../../architecture.md) | → [Review](../review/README.md) | → [Totals](../totals/README.md) | → [Budget](../budget/README.md) | → [Archive](../archive/README.md) | → [Storage](../storage/README.md)

## Overview

Calculation computes sums in integer cents (NFR-6). It changes no data and does no I/O.

It has the receipt check (FR-20) and the category subtotals of one receipt (FR-19, FR-44),
used by [review](../review/README.md), and the period totals: per category and group, per
ISO week and per month of a period (FR-22–FR-25, FR-44), used by
[totals](../totals/README.md). It also compares the monthly budget with spending (FR-50), used
by [budget](../budget/README.md), and the totals of an archived year per group, category
and product (FR-53), used by [archive](../archive/README.md).

## Key Files and Entry Points

- @backend/app/calculation/receipt_check.py — `check_receipt`, `category_subtotals`
- @backend/app/calculation/period.py — `parse_period`, `comparison_period`, `Period`,
  `Column`, `PeriodError`
- @backend/app/calculation/period_totals.py — `period_totals`, `TotalLine`, `RowCategory`,
  `TotalsRow`, `PeriodTotals`
- @backend/app/calculation/budget_comparison.py — `budget_rows`, `weekly_budget`,
  `budget_comparison`
- @backend/app/calculation/money.py — `AMOUNT_LIMIT`, the limit of a typed amount
- @backend/app/calculation/archive_totals.py — `archive_totals`, `ArchiveLine`,
  `ArchiveRow`, `ArchiveTotals`
- @backend/app/calculation/names.py — `finnish_key`, the Finnish order of names

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
- A **date range** (`range`, bounds `2026-10-15`) is a period of free days, both ends
  included. One day is valid, and the longest is 731 days, the longest possible 24 months.
  A day that is not real or not `YYYY-MM-DD`, the years outside 1–9998, `first` after
  `last`, or a longer range raises `PeriodError`.
- A **column** is each ISO week and each month with a day in the period, clipped to the
  period's days; it is **partial** when it was clipped. October 2026 has the week columns
  `2026-W40` (1–4 Oct, partial) to `2026-W44` (26–31 Oct, partial). A week's key uses its
  ISO year: 29 Dec 2025 – 4 Jan 2026 is `2026-W01`.
- `period_totals` skips deposit refunds (FR-44) and lines outside the period, and sums the
  rest per category and column. Rows follow `catalog` (the category list order): a group
  when one of its categories has a line, with those categories as its `categories` and
  their column sums as its amounts; a category without a group when it has a line; last a
  `none` row for lines without a category. A category whose lines sum to 0 is listed.
  Each row also has `week_counts` and `month_counts`, the number of counted lines per
  column (a group's are its categories' sums), so the [export](../export/README.md) can
  tell a sum of 0 with lines from no lines; they are not part of a row's equality. The
  column totals sum the top-level rows, so the `none` row is in them and a group is not
  counted twice. A category id missing from `catalog` cannot happen (`ON DELETE
  RESTRICT`); its lines would be in no row.

### Budget comparison

| Function | Returns | Raises |
|---|---|---|
| `comparison_period(month, kind)` | `Period` | `PeriodError` |
| `budget_rows(catalog, budgets)` | `list[BudgetRow(kind, id, name, amount_cents)]` | nothing |
| `weekly_budget(amount_cents, period, weeks)` | `list[int]`, one amount per week | nothing |
| `budget_comparison(period, lines, catalog, budgets)` | `Comparison(period, weeks, rows, total)` | nothing |
| `WeekFigures.remaining_cents` | a week's budget minus its spending, as a row's `remaining_cents`; a property, so the API answer of a week keeps its two fields | nothing |

- A **comparison period** is named by a month. With `kind` `None` or `calendar` it is that
  calendar month. With `mid` it runs from the 15th of that month to the 14th of the next, so
  `2026-10` is 15.10.2026–14.11.2026. Any other `kind`, or a month `parse_period` refuses,
  raises `PeriodError`. Week columns clip to the period as in the totals.
- `budget_rows` lists the groups and the categories without a group in catalog order; a
  missing amount is 0. `GET /api/budget` and the comparison both use it.
- `weekly_budget` gives a week the difference of two cumulative shares, each rounded half up
  in integers: `share(k) = (2 × M × k + D) // (2 × D)`, with `M` the monthly budget and `D`
  the days of the period. A week of the days `s`–`e` has `share(e) − share(s − 1)`, so rounding
  cannot change the sum: a row's weeks always add up to `M`.
- `budget_comparison` calls `period_totals`, so deposit refunds, group membership and the
  `none` row follow its rules. A budget row without lines has zeros. The `none` row is last,
  has budget 0, and exists only when `period_totals` has it. `total` sums the rows column by
  column. The caller decides which lines count: [budget](../budget/README.md) passes only
  those of reviewed receipts.

### Archived year totals

| Function | Returns | Raises |
|---|---|---|
| `archive_totals(year, lines)` | `ArchiveTotals(year, months, rows, month_totals, total)` | nothing |
| `finnish_key(name)` | a sort key | nothing |

- The archive keeps names, not ids ([ADR 0007](../../adr/0007-archive-tables.md)), so the
  rows are built from `ArchiveLine(purchase_date, amount_cents, product_name,
  category_name, group_name, is_deposit_refund)`.
- `rows` is a three-level tree: a **group** sums its categories, a **category** (in a group
  or at the top without one) sums its products, a **product** sums the lines with its name
  in that category. The same product name in two categories gives two product rows. Lines
  without a category form a top-level `none` row with their products.
- Deposit refunds and lines outside the year are left out. Rows without lines are left out.
- `months` holds 12 keys, `2025-01` to `2025-12`; a row's `months` are its cents per month
  and `total` their sum. `month_totals` and `total` sum the top-level rows.
- At each level rows sort by `finnish_key`: case-insensitive, with `å`, `ä` and `ö` after
  `z`, ties broken by the exact name. A category without a group sorts among the groups;
  `none` is last.
- Each row also has `line_counts`, the lines per month, so the
  [export](../export/README.md) can tell a sum of 0 with lines from no lines; they are not
  part of a row's equality.

## Data Flow

Callers pass plain values: `check_receipt` takes the amounts, `category_subtotals` takes
`SubtotalLine(category_id, amount_cents, is_deposit_refund)` items. The receipt list passes
the line sum that storage computed in SQL as a one-item list.

## Dependencies

- Uses: nothing.
- Used by: [review](../review/README.md), [totals](../totals/README.md),
  [budget](../budget/README.md), [archive](../archive/README.md),
  [export](../export/README.md) (the period, totals and archive totals types).

## Modules

None yet.

## Known Issues and Gotchas

- A category id missing from `order` cannot happen (`ON DELETE RESTRICT` keeps every used
  category); such a subtotal would sort after the known ones and before the lines without a
  category instead of raising.

## Related Documents

- [Receipt review spec](../../../specs/features/receipt-review.md) PC2, Plan P2
- [Category totals spec](../../../specs/features/totals.md) PC1, Plan P1–P2
- [CSV export spec](../../../specs/features/csv-export.md) Plan P3 (line counts)
- [Architecture](../../architecture.md#component-map)
