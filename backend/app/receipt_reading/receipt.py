"""A read receipt: what reading one image gives."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

type ReadFailure = Literal["unreadable_image", "ocr_failed", "no_text", "parse_failed"]


class ReadFailedError(Exception):
    """The image was not read. `reason` is the import failure reason; it holds no content."""

    def __init__(self, reason: ReadFailure) -> None:
        super().__init__(reason)
        self.reason: ReadFailure = reason


@dataclass(frozen=True)
class ReadLine:
    """One item line: amount after any discount and including any deposit (FR-9)."""

    name: str
    amount_cents: int
    is_deposit_refund: bool


@dataclass(frozen=True)
class ReadReceipt:
    store: str
    purchase_date: date | None
    total_cents: int
    lines: tuple[ReadLine, ...]
    ocr_text: str
