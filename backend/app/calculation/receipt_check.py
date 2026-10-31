"""The receipt check (FR-20) and category subtotals (FR-19, FR-44). Integer cents, no I/O."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ReceiptCheck:
    line_sum_cents: int
    difference_cents: int | None  # None without a total
    warning: bool


def check_receipt(total_cents: int | None, amounts: Iterable[int]) -> ReceiptCheck:
    """Compare the sum of every line amount, deposit refunds included, with the total: the
    printed total already has the refunds deducted (FR-20). A missing total is a warning."""
    line_sum = sum(amounts)
    if total_cents is None:
        return ReceiptCheck(line_sum, None, warning=True)
    difference = total_cents - line_sum
    return ReceiptCheck(line_sum, difference, warning=difference != 0)


@dataclass(frozen=True)
class SubtotalLine:
    """What the subtotals need from a receipt line."""

    category_id: int | None
    amount_cents: int
    is_deposit_refund: bool


@dataclass(frozen=True)
class Subtotal:
    category_id: int | None  # None: the lines without a category
    amount_cents: int


def category_subtotals(lines: Iterable[SubtotalLine], order: Sequence[int]) -> list[Subtotal]:
    """Sum the lines per category in the catalog `order`, then the lines without a category.
    Deposit refunds are in no subtotal (FR-44); only categories with lines are listed."""
    sums: dict[int | None, int] = {}
    for line in lines:
        if not line.is_deposit_refund:
            sums[line.category_id] = sums.get(line.category_id, 0) + line.amount_cents
    position = {category_id: index for index, category_id in enumerate(order)}
    # `ON DELETE RESTRICT` keeps every used category in the catalog; an unknown one would
    # still sort after the known ones and before the lines without a category.
    unknown, uncategorized = len(position), len(position) + 1

    def rank(category_id: int | None) -> int:
        return uncategorized if category_id is None else position.get(category_id, unknown)

    return [Subtotal(category_id, sums[category_id]) for category_id in sorted(sums, key=rank)]
