"""Rules on top of the answer schema (receipt-reading spec, Validation)."""

import re
from datetime import date

from app.receipt_reading.prompt import Answer
from app.receipt_reading.receipt import ReadFailedError, ReadLine, ReadReceipt

# ASCII digits only: `\d` would also match other scripts' digits.
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
# SQLite stores signed 64-bit integers; a larger value would fail only when it is saved.
_INTEGER_MIN = -(2**63)
_INTEGER_MAX = 2**63 - 1


def to_read_receipt(answer: Answer, ocr_text: str) -> ReadReceipt:
    """The read receipt of a schema-valid answer.

    A store or date the model got wrong is kept empty for the user to fix; an answer that
    cannot be a receipt fails.

    Raises:
        ReadFailedError: `parse_failed`, the answer breaks a rule.
    """
    if not 0 <= answer.t <= _INTEGER_MAX or not answer.l:
        raise ReadFailedError("parse_failed")
    lines: list[ReadLine] = []
    for line in answer.l:
        name = line.n.strip()
        if not name or not _INTEGER_MIN <= line.a <= _INTEGER_MAX or (line.r and line.a >= 0):
            raise ReadFailedError("parse_failed")
        lines.append(ReadLine(name, line.a, is_deposit_refund=line.r))
    return ReadReceipt(
        store=answer.s.strip(),
        purchase_date=_date(answer.d),
        total_cents=answer.t,
        lines=tuple(lines),
        ocr_text=ocr_text,
    )


def _date(text: str) -> date | None:
    if not _ISO_DATE.fullmatch(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None
