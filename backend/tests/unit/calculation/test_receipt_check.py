from app.calculation.receipt_check import (
    ReceiptCheck,
    Subtotal,
    SubtotalLine,
    category_subtotals,
    check_receipt,
)


def test_ac5_refund_is_in_the_line_sum() -> None:
    assert check_receipt(300, [340, -40]) == ReceiptCheck(
        line_sum_cents=300, difference_cents=0, warning=False
    )


def test_ac6_difference_gives_a_warning() -> None:
    assert check_receipt(500, [450]) == ReceiptCheck(
        line_sum_cents=450, difference_cents=50, warning=True
    )


def test_ac6_lines_above_the_total_give_a_negative_difference() -> None:
    assert check_receipt(400, [450]) == ReceiptCheck(
        line_sum_cents=450, difference_cents=-50, warning=True
    )


def test_ac7_no_total_gives_a_warning() -> None:
    assert check_receipt(None, [125]) == ReceiptCheck(
        line_sum_cents=125, difference_cents=None, warning=True
    )
    assert check_receipt(None, []) == ReceiptCheck(
        line_sum_cents=0, difference_cents=None, warning=True
    )


MAITO, JUOMAT, LIHA = 12, 30, 13
# Catalog order: the group's categories first, then the categories without a group.
ORDER = [MAITO, LIHA, JUOMAT]


def line(category_id: int | None, amount: int, *, refund: bool = False) -> SubtotalLine:
    return SubtotalLine(category_id=category_id, amount_cents=amount, is_deposit_refund=refund)


def test_ac8_subtotals_in_catalog_order() -> None:
    lines = [
        line(MAITO, 125),
        line(JUOMAT, 224),
        line(MAITO, 99),
        line(None, 50),
        line(None, -40, refund=True),
    ]

    assert category_subtotals(lines, ORDER) == [
        Subtotal(MAITO, 224),
        Subtotal(JUOMAT, 224),
        Subtotal(None, 50),
    ]


def test_ac8_no_uncategorized_subtotal_when_every_line_has_a_category() -> None:
    assert category_subtotals([line(JUOMAT, 224)], ORDER) == [Subtotal(JUOMAT, 224)]


def test_ac8_refunds_only_give_no_subtotals() -> None:
    assert category_subtotals([line(None, -40, refund=True)], ORDER) == []


def test_ac8_category_missing_from_the_order_sorts_before_no_category() -> None:
    lines = [line(None, 50), line(99, 10), line(JUOMAT, 224)]

    assert category_subtotals(lines, ORDER) == [
        Subtotal(JUOMAT, 224),
        Subtotal(99, 10),
        Subtotal(None, 50),
    ]
