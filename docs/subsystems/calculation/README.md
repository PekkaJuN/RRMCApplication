# Calculation

Navigation: ↑ [Architecture](../../architecture.md) | → [Review](../review/README.md) | → [Storage](../storage/README.md)

## Overview

Calculation computes sums in integer cents (NFR-6). It changes no data and does no I/O.

Today it has the receipt check (FR-20) and the category subtotals of one receipt (FR-19,
FR-44), used by [review](../review/README.md). The totals per category and group per ISO
week and per month (FR-22–FR-25) come with the totals spec.

## Key Files and Entry Points

- @backend/app/calculation/receipt_check.py — `check_receipt`, `category_subtotals`

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

## Data Flow

Callers pass plain values: `check_receipt` takes the amounts, `category_subtotals` takes
`SubtotalLine(category_id, amount_cents, is_deposit_refund)` items. The receipt list passes
the line sum that storage computed in SQL as a one-item list.

## Dependencies

- Uses: nothing.
- Used by: [review](../review/README.md).

## Modules

None yet.

## Known Issues and Gotchas

- A category id missing from `order` cannot happen (`ON DELETE RESTRICT` keeps every used
  category); such a subtotal would sort after the known ones and before the lines without a
  category instead of raising.

## Related Documents

- [Receipt review spec](../../../specs/features/receipt-review.md) PC2, Plan P2
- [Architecture](../../architecture.md#component-map)
