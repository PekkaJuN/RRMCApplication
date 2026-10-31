"""API schemas of /api/receipts (receipt-review spec, API shapes)."""

from pydantic import BaseModel, StrictBool, StrictInt

from app.review.service import LineView, ReceiptSummary, ReceiptView, SubtotalView
from app.storage.receipt_repository import CategorySource


class LineCategoryUpdate(BaseModel):
    # Strict, so "12" or true is refused instead of read as a number (AC15).
    category_id: StrictInt


class ReviewUpdate(BaseModel):
    reviewed: StrictBool


class ReceiptSummaryOut(BaseModel):
    id: int
    purchase_date: str | None
    store: str | None
    total_cents: int | None
    warning: bool
    reviewed: bool

    @classmethod
    def from_summary(cls, summary: ReceiptSummary) -> "ReceiptSummaryOut":
        return cls(
            id=summary.id,
            purchase_date=summary.purchase_date,
            store=summary.store,
            total_cents=summary.total_cents,
            warning=summary.warning,
            reviewed=summary.reviewed,
        )


class LineOut(BaseModel):
    id: int
    position: int
    name: str
    amount_cents: int
    is_deposit_refund: bool
    category_id: int | None
    category_name: str | None
    group_name: str | None
    category_source: CategorySource | None

    @classmethod
    def from_view(cls, line: LineView) -> "LineOut":
        return cls(
            id=line.id,
            position=line.position,
            name=line.name,
            amount_cents=line.amount_cents,
            is_deposit_refund=line.is_deposit_refund,
            category_id=line.category_id,
            category_name=line.category_name,
            group_name=line.group_name,
            category_source=line.category_source,
        )


class SubtotalOut(BaseModel):
    category_id: int | None
    category_name: str | None
    group_name: str | None
    amount_cents: int

    @classmethod
    def from_view(cls, subtotal: SubtotalView) -> "SubtotalOut":
        return cls(
            category_id=subtotal.category_id,
            category_name=subtotal.category_name,
            group_name=subtotal.group_name,
            amount_cents=subtotal.amount_cents,
        )


class ReceiptOut(BaseModel):
    """A receipt with its lines and sums. The OCR text is left out: no view shows it."""

    id: int
    file_name: str
    imported_at: str
    store: str | None
    purchase_date: str | None
    total_cents: int | None
    reviewed: bool
    lines: list[LineOut]
    line_sum_cents: int
    difference_cents: int | None
    warning: bool
    subtotals: list[SubtotalOut]

    @classmethod
    def from_view(cls, view: ReceiptView) -> "ReceiptOut":
        return cls(
            id=view.id,
            file_name=view.file_name,
            imported_at=view.imported_at,
            store=view.store,
            purchase_date=view.purchase_date,
            total_cents=view.total_cents,
            reviewed=view.reviewed,
            lines=[LineOut.from_view(line) for line in view.lines],
            line_sum_cents=view.line_sum_cents,
            difference_cents=view.difference_cents,
            warning=view.warning,
            subtotals=[SubtotalOut.from_view(subtotal) for subtotal in view.subtotals],
        )
