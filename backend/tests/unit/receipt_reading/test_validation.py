from datetime import date

import pytest

from app.receipt_reading.prompt import Answer, AnswerLine
from app.receipt_reading.receipt import ReadFailedError, ReadLine, ReadReceipt
from app.receipt_reading.validation import to_read_receipt

OCR_TEXT = "K-MARKET TESTI\nMAITO 1L 1,25\n"
AC6_LINES = [
    AnswerLine(n="Maito 1l", a=125, r=False),
    AnswerLine(n="Limu 1,5l", a=264, r=False),
    AnswerLine(n="Panttipalautus", a=-40, r=True),
]


def answer(
    s: str = " K-Market Testi ",
    d: str = "2026-10-05",
    t: int = 349,
    lines: list[AnswerLine] | None = None,
) -> Answer:
    return Answer(s=s, d=d, t=t, l=AC6_LINES if lines is None else lines)


AC6_RECEIPT = ReadReceipt(
    store="K-Market Testi",
    purchase_date=date(2026, 10, 5),
    total_cents=349,
    lines=(
        ReadLine("Maito 1l", 125, is_deposit_refund=False),
        ReadLine("Limu 1,5l", 264, is_deposit_refund=False),
        ReadLine("Panttipalautus", -40, is_deposit_refund=True),
    ),
    ocr_text=OCR_TEXT,
)


def test_ac6_valid_answer_becomes_a_read_receipt() -> None:
    assert to_read_receipt(answer(), OCR_TEXT) == AC6_RECEIPT


@pytest.mark.parametrize(
    "bad",
    [
        answer(lines=[]),
        answer(lines=[AnswerLine(n="  ", a=125, r=False)]),
        answer(t=-1),
        answer(lines=[AnswerLine(n="Panttipalautus", a=40, r=True)]),
        answer(lines=[AnswerLine(n="Panttipalautus", a=0, r=True)]),
        answer(t=2**63),
        answer(lines=[AnswerLine(n="Maito 1l", a=-(2**63) - 1, r=False)]),
    ],
    ids=[
        "no lines",
        "blank name",
        "negative total",
        "refund with positive amount",
        "zero",
        "total above integer limit",
        "amount below integer limit",
    ],
)
def test_ac9_rule_breaks_are_parse_failed(bad: Answer) -> None:
    with pytest.raises(ReadFailedError) as error:
        to_read_receipt(bad, OCR_TEXT)

    assert error.value.reason == "parse_failed"


@pytest.mark.parametrize("text", ["2026-02-30", "05.10.2026", "", "2026-10-5", "２０２６-10-05"])
def test_ac10_not_a_real_date_is_none(text: str) -> None:
    result = to_read_receipt(answer(d=text), OCR_TEXT)

    assert result.purchase_date is None
    assert result.store == AC6_RECEIPT.store
    assert result.total_cents == AC6_RECEIPT.total_cents
    assert result.lines == AC6_RECEIPT.lines


def test_ac9_values_at_the_integer_limits_are_kept() -> None:
    result = to_read_receipt(
        answer(t=2**63 - 1, lines=[AnswerLine(n="Maito 1l", a=-(2**63), r=False)]), OCR_TEXT
    )

    assert result.total_cents == 2**63 - 1
    assert result.lines == (ReadLine("Maito 1l", -(2**63), is_deposit_refund=False),)


def test_ac10b_blank_store_is_empty() -> None:
    assert to_read_receipt(answer(s="  "), OCR_TEXT).store == ""


def test_line_names_are_trimmed() -> None:
    result = to_read_receipt(answer(lines=[AnswerLine(n=" Maito ", a=125, r=False)]), OCR_TEXT)

    assert result.lines == (ReadLine("Maito", 125, is_deposit_refund=False),)
