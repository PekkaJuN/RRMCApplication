"""The receipt list and the receipt view (receipt-review PC1, PC2)."""

from dataclasses import dataclass
from pathlib import Path

from app.calculation.receipt_check import SubtotalLine, category_subtotals, check_receipt
from app.categorization.errors import NotFoundError, UnknownCategoryError
from app.categorization.names import validate_product_name
from app.categorization.service import CategoryService, LineCategoryService
from app.review.errors import DepositRefundAmountError
from app.review.fields import check_amount, check_date, check_store, check_total
from app.review.images import read_image
from app.storage.catalog_repository import CatalogRepository, CategoryRow
from app.storage.db import fits_integer
from app.storage.receipt_repository import CategorySource, ReceiptRepository


@dataclass(frozen=True)
class LineEdit:
    """The fields a request sends for a line; None is a field not sent (the API refuses
    null)."""

    name: str | None = None
    amount_cents: int | None = None
    is_deposit_refund: bool | None = None
    category_id: int | None = None


@dataclass(frozen=True)
class ReceiptEdit:
    """The receipt fields a request sends; None is a field not sent."""

    store: str | None = None
    purchase_date: str | None = None
    total_cents: int | None = None
    reviewed: bool | None = None


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

    def edit_line(self, receipt_id: int, line_id: int, edit: LineEdit) -> ReceiptView:
        """Apply the sent fields to a line in one transaction (line-editing PC1): the refund
        flag and amount, then the name, then the category; any error changes nothing. The
        answer is the whole receipt, because a category choice can move other lines of the
        same product (FR-36).

        Raises: NotFoundError (also for a line on another receipt), InvalidNameError,
        InvalidAmountError, DepositRefundAmountError, UnknownCategoryError,
        NotACategoryError, DepositRefundLineError.
        """
        _require_ids(receipt_id, line_id)
        if edit.category_id is not None and not fits_integer(edit.category_id):
            raise UnknownCategoryError()
        rules = LineCategoryService(self._catalog, self._receipts)
        with self._catalog.transaction():
            line = self._receipts.get_line(line_id)
            if line is None or line.receipt_id != receipt_id:
                raise NotFoundError()
            # Only sent values are checked: a name read from a receipt may be longer than a
            # product name, and an amount edit must not fail on it.
            name = line.name if edit.name is None else validate_product_name(edit.name)
            amount = (
                line.amount_cents if edit.amount_cents is None else check_amount(edit.amount_cents)
            )
            refund = (
                line.is_deposit_refund if edit.is_deposit_refund is None else edit.is_deposit_refund
            )
            _check_refund_amount(amount, refund)
            if refund:
                category = None  # FR-44: a refund has no category
            elif line.is_deposit_refund:
                category = rules.resolve(name)
            else:
                category = rules.follow_name(line, name)
            self._receipts.update_line(
                line.id, name=name, amount_cents=amount, is_deposit_refund=refund, category=category
            )
            if edit.category_id is not None:
                written = self._receipts.get_line(line.id)
                assert written is not None  # noqa: S101 - written in the same transaction
                rules.choose(written, edit.category_id)
        return self.receipt(receipt_id)

    def add_line(
        self, receipt_id: int, name: str, amount_cents: int, *, is_deposit_refund: bool
    ) -> ReceiptView:
        """Add a line after the last one (line-editing PC6). A normal line gets its name
        match's category, or none.

        Raises: NotFoundError, InvalidNameError, InvalidAmountError, DepositRefundAmountError.
        """
        _require_ids(receipt_id)
        rules = LineCategoryService(self._catalog, self._receipts)
        with self._catalog.transaction():
            if self._receipts.get(receipt_id) is None:
                raise NotFoundError()
            display = validate_product_name(name)
            amount = check_amount(amount_cents)
            _check_refund_amount(amount, is_deposit_refund)
            self._receipts.add_line(
                receipt_id,
                self._receipts.next_position(receipt_id),
                display,
                amount,
                is_deposit_refund=is_deposit_refund,
                category=None if is_deposit_refund else rules.resolve(display),
            )
        return self.receipt(receipt_id)

    def delete_line(self, receipt_id: int, line_id: int) -> ReceiptView:
        """Delete a line; products and the other lines' positions stay (PC7).

        Raises: NotFoundError (also for a line on another receipt).
        """
        _require_ids(receipt_id, line_id)
        with self._receipts.transaction():
            line = self._receipts.get_line(line_id)
            if line is None or line.receipt_id != receipt_id:
                raise NotFoundError()
            self._receipts.delete_line(line_id)
        return self.receipt(receipt_id)

    def update_receipt(self, receipt_id: int, edit: ReceiptEdit) -> ReceiptView:
        """Apply the sent store, date, total and review state in one transaction (PC8, PC9).
        Confirming is always allowed (receipt-review PC5).

        Raises: NotFoundError, InvalidStoreError, InvalidDateError, InvalidAmountError.
        """
        _require_ids(receipt_id)
        with self._receipts.transaction():
            row = self._receipts.get(receipt_id)
            if row is None:
                raise NotFoundError()
            self._receipts.set_fields(
                receipt_id,
                store=row.store if edit.store is None else check_store(edit.store),
                purchase_date=(
                    row.purchase_date
                    if edit.purchase_date is None
                    else check_date(edit.purchase_date)
                ),
                total_cents=(
                    row.total_cents if edit.total_cents is None else check_total(edit.total_cents)
                ),
            )
            if edit.reviewed is not None:
                self._receipts.set_reviewed(receipt_id, reviewed=edit.reviewed)
        return self.receipt(receipt_id)

    def image(self, receipt_id: int, done_dir: Path) -> tuple[bytes, str]:
        """The receipt's image and media type. Raises: NotFoundError, ImageMissingError."""
        _require_ids(receipt_id)
        row = self._receipts.get(receipt_id)
        if row is None:
            raise NotFoundError()
        return read_image(done_dir, row.file_name)

    def receipt(self, receipt_id: int) -> ReceiptView:
        """Raises: NotFoundError."""
        _require_ids(receipt_id)
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


def _require_ids(*ids: int) -> None:
    """An id outside SQLite's integer range cannot exist; without this check SQLite raises
    OverflowError, a 500 (line-editing PC11). Raises: NotFoundError."""
    if not all(fits_integer(item) for item in ids):
        raise NotFoundError()


def _check_refund_amount(amount_cents: int, is_deposit_refund: bool) -> None:
    """A deposit refund is negative (PC3, PC4). Raises: DepositRefundAmountError."""
    if is_deposit_refund and amount_cents >= 0:
        raise DepositRefundAmountError()


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
