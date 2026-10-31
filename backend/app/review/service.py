"""The receipt list and the receipt view (receipt-review PC1, PC2)."""

from dataclasses import dataclass
from pathlib import Path

from app.calculation.receipt_check import SubtotalLine, category_subtotals, check_receipt
from app.categorization.errors import NotFoundError
from app.categorization.service import CategoryService, LineCategoryService
from app.review.images import read_image
from app.storage.catalog_repository import CatalogRepository, CategoryRow
from app.storage.receipt_repository import CategorySource, ReceiptRepository


@dataclass(frozen=True)
class ReceiptSummary:
    id: int
    purchase_date: str | None
    store: str | None
    total_cents: int | None
    warning: bool
    reviewed: bool


@dataclass(frozen=True)
class LineView:
    id: int
    position: int
    name: str
    amount_cents: int
    is_deposit_refund: bool
    category_id: int | None
    category_name: str | None
    group_name: str | None
    category_source: CategorySource | None


@dataclass(frozen=True)
class SubtotalView:
    category_id: int | None
    category_name: str | None
    group_name: str | None
    amount_cents: int


@dataclass(frozen=True)
class ReceiptView:
    id: int
    file_name: str
    imported_at: str
    store: str | None
    purchase_date: str | None
    total_cents: int | None
    reviewed: bool
    lines: list[LineView]
    line_sum_cents: int
    difference_cents: int | None
    warning: bool
    subtotals: list[SubtotalView]


class ReviewService:
    """Builds what the review UI shows. The sums come from calculation, so the UI holds no
    rule. Both repositories must be on one connection, as `LineCategoryService` requires."""

    def __init__(self, catalog: CatalogRepository, receipts: ReceiptRepository) -> None:
        self._catalog = catalog
        self._receipts = receipts

    def summaries(self) -> list[ReceiptSummary]:
        """Every receipt in list order (PC1), with the warning of FR-20."""
        return [
            ReceiptSummary(
                id=row.id,
                purchase_date=row.purchase_date,
                store=row.store,
                total_cents=row.total_cents,
                warning=check_receipt(row.total_cents, [row.line_sum_cents]).warning,
                reviewed=row.reviewed,
            )
            for row in self._receipts.summaries()
        ]

    def set_line_category(self, receipt_id: int, line_id: int, category_id: int) -> ReceiptView:
        """The user's choice for a line, remembered for its product (FR-13). The answer is the
        whole receipt, because the choice can move other lines of the same product (FR-36).

        Raises: NotFoundError (also for a line on another receipt), UnknownCategoryError,
        NotACategoryError, DepositRefundLineError, InvalidNameError.
        """
        line = self._receipts.get_line(line_id)
        if line is None or line.receipt_id != receipt_id:
            raise NotFoundError()
        LineCategoryService(self._catalog, self._receipts).set_category(line_id, category_id)
        return self.receipt(receipt_id)

    def set_reviewed(self, receipt_id: int, *, reviewed: bool) -> ReceiptView:
        """Confirm the receipt or make it unreviewed again; always allowed (PC5).

        Raises: NotFoundError.
        """
        if not self._receipts.set_reviewed(receipt_id, reviewed=reviewed):
            raise NotFoundError()
        return self.receipt(receipt_id)

    def image(self, receipt_id: int, done_dir: Path) -> tuple[bytes, str]:
        """The receipt's image and media type. Raises: NotFoundError, ImageMissingError."""
        row = self._receipts.get(receipt_id)
        if row is None:
            raise NotFoundError()
        return read_image(done_dir, row.file_name)

    def receipt(self, receipt_id: int) -> ReceiptView:
        """Raises: NotFoundError."""
        row = self._receipts.get(receipt_id)
        if row is None:
            raise NotFoundError()
        lines = self._receipts.lines(receipt_id)
        names = _CategoryNames(CategoryService(self._catalog).list())
        check = check_receipt(row.total_cents, (line.amount_cents for line in lines))
        subtotals = category_subtotals(
            (
                SubtotalLine(line.category_id, line.amount_cents, line.is_deposit_refund)
                for line in lines
            ),
            names.order,
        )
        return ReceiptView(
            id=row.id,
            file_name=row.file_name,
            imported_at=row.imported_at,
            store=row.store,
            purchase_date=row.purchase_date,
            total_cents=row.total_cents,
            reviewed=row.reviewed,
            lines=[
                LineView(
                    line.id,
                    line.position,
                    line.name,
                    line.amount_cents,
                    line.is_deposit_refund,
                    line.category_id,
                    *names.of(line.category_id),
                    line.category_source,
                )
                for line in lines
            ],
            line_sum_cents=check.line_sum_cents,
            difference_cents=check.difference_cents,
            warning=check.warning,
            subtotals=[
                SubtotalView(
                    subtotal.category_id, *names.of(subtotal.category_id), subtotal.amount_cents
                )
                for subtotal in subtotals
            ],
        )


class _CategoryNames:
    """Category and group names from one read of the catalog, so the view needs no join."""

    def __init__(self, items: list[CategoryRow]) -> None:
        self._items = {item.id: item for item in items}
        self.order = [item.id for item in items if item.kind == "category"]

    def of(self, category_id: int | None) -> tuple[str | None, str | None]:
        item = self._items.get(category_id) if category_id is not None else None
        if item is None:
            return None, None
        group = self._items.get(item.parent_id) if item.parent_id is not None else None
        return item.name, group.name if group else None
