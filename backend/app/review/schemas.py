"""API schemas of /api/receipts (receipt-review spec, API shapes)."""

from typing import Self

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, StrictStr, model_validator

from app.review.service import LineView, ReceiptSummary, ReceiptView, SubtotalView
from app.storage.receipt_repository import CategorySource


class _Body(BaseModel):
    # Unknown fields are refused, so a misspelled field is an error, not a silent no-op
    # (line-editing PC10). Strict types refuse "12" for a number and 1 for a boolean.
    model_config = ConfigDict(extra="forbid")


class _PartialBody(_Body):
    """A partial update: at least one field, and a sent field is never null (PC10). None
    therefore always means "not sent" to the service."""

    @model_validator(mode="after")
    def _sent_fields_have_values(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("no fields")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("null field")
        return self


class LineUpdate(_PartialBody):
    name: StrictStr | None = None
    amount_cents: StrictInt | None = None
    is_deposit_refund: StrictBool | None = None
    category_id: StrictInt | None = None


class NewLine(_Body):
    name: StrictStr
    amount_cents: StrictInt
    is_deposit_refund: StrictBool = False


class ReceiptUpdate(_PartialBody):
    store: StrictStr | None = None
    purchase_date: StrictStr | None = None
    total_cents: StrictInt | None = None
    reviewed: StrictBool | None = None


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
