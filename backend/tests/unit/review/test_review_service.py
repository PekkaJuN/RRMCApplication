import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.categorization.defaults import seed_defaults
from app.categorization.errors import NotFoundError
from app.categorization.names import normalize_key
from app.review.service import (
    LineView,
    ReceiptSummary,
    ReceiptView,
    ReviewService,
    SubtotalView,
)
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import LineCategory, ReceiptRepository

TIME = "2026-10-28T10:00:01Z"


@pytest.fixture
def catalog(db: sqlite3.Connection) -> CatalogRepository:
    repository = CatalogRepository(db)
    seed_defaults(repository, datetime(2026, 10, 30, tzinfo=UTC))
    return repository


@pytest.fixture
def receipts(db: sqlite3.Connection) -> ReceiptRepository:
    return ReceiptRepository(db)


@pytest.fixture
def service(catalog: CatalogRepository, receipts: ReceiptRepository) -> ReviewService:
    return ReviewService(catalog, receipts)


def category_id(catalog: CatalogRepository, name: str) -> int:
    row = catalog.get_category_by_key(normalize_key(name))
    assert row is not None
    return row.id


def add_receipt(
    receipts: ReceiptRepository,
    lines: list[tuple[str, int, LineCategory | None]],
    *,
    total: int | None = 349,
    number: int = 1,
    purchase_date: str | None = "2026-10-05",
    store: str | None = "Testikauppa",
) -> tuple[int, list[int]]:
    """A receipt with lines (name, amount, category); a name `Panttipalautus` is a refund."""
    row = receipts.add(
        f"{number:064d}",
        "kuitti.jpg",
        TIME,
        store=store,
        purchase_date=purchase_date,
        total_cents=total,
        ocr_text="SYNTHETIC",
    )
    ids = [
        receipts.add_line(
            row.id,
            position,
            name,
            amount,
            is_deposit_refund=name == "Panttipalautus",
            category=category,
        )
        for position, (name, amount, category) in enumerate(lines, start=1)
    ]
    return row.id, ids


def receipt_a(catalog: CatalogRepository, receipts: ReceiptRepository) -> tuple[int, list[int]]:
    """Receipt A of the spec: Maito remembered, Limu suggested by the model."""
    dairy = category_id(catalog, "Maitotuotteet")
    milk = catalog.add_product("Maito", "maito", dairy)
    return add_receipt(
        receipts,
        [
            ("Maito", 125, LineCategory(dairy, "remembered", milk)),
            ("Limu", 224, LineCategory(category_id(catalog, "Juomat"), "model", None)),
        ],
    )


def test_ac4_lines_with_category_names(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    receipt_id, (milk, soda) = receipt_a(catalog, receipts)
    dairy, drinks = category_id(catalog, "Maitotuotteet"), category_id(catalog, "Juomat")

    view = service.receipt(receipt_id)

    assert view == ReceiptView(
        id=receipt_id,
        file_name="kuitti.jpg",
        imported_at=TIME,
        store="Testikauppa",
        purchase_date="2026-10-05",
        total_cents=349,
        reviewed=False,
        lines=[
            LineView(milk, 1, "Maito", 125, False, dairy, "Maitotuotteet", "Ruoka", "remembered"),
            LineView(soda, 2, "Limu", 224, False, drinks, "Juomat", None, "model"),
        ],
        line_sum_cents=349,
        difference_cents=0,
        warning=False,
        subtotals=[
            SubtotalView(dairy, "Maitotuotteet", "Ruoka", 125),
            SubtotalView(drinks, "Juomat", None, 224),
        ],
    )


def test_ac8_view_subtotals(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    dairy, drinks = category_id(catalog, "Maitotuotteet"), category_id(catalog, "Juomat")
    receipt_id, _ = add_receipt(
        receipts,
        [
            ("Maito", 125, LineCategory(dairy, "model", None)),
            ("Limu", 224, LineCategory(drinks, "model", None)),
            ("Jogurtti", 99, LineCategory(dairy, "model", None)),
            ("Outo", 50, None),
            ("Panttipalautus", -40, None),
        ],
        total=500,
    )

    view = service.receipt(receipt_id)

    assert view.subtotals == [
        SubtotalView(dairy, "Maitotuotteet", "Ruoka", 224),
        SubtotalView(drinks, "Juomat", None, 224),
        SubtotalView(None, None, None, 50),
    ]
    assert (view.line_sum_cents, view.difference_cents, view.warning) == (458, 42, True)
    refund = view.lines[4]
    assert (refund.is_deposit_refund, refund.category_id, refund.category_name) == (
        True,
        None,
        None,
    )


def test_ac7_receipt_before_reading(service: ReviewService, receipts: ReceiptRepository) -> None:
    row = receipts.add("c" * 64, "vanha.jpg", TIME)

    view = service.receipt(row.id)

    assert (view.store, view.purchase_date, view.total_cents) == (None, None, None)
    assert view.lines == []
    assert view.subtotals == []
    assert (view.line_sum_cents, view.difference_cents, view.warning) == (0, None, True)


def test_ac9_unknown_receipt(service: ReviewService) -> None:
    with pytest.raises(NotFoundError):
        service.receipt(999)


def test_ac1_summaries_with_warning(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, _ = receipt_a(catalog, receipts)
    receipts.set_reviewed(a, reviewed=True)
    b, _ = add_receipt(
        receipts,
        [("Kahvi", 450, None)],
        total=500,
        number=2,
        purchase_date="2026-10-06",
        store="Kauppa B",
    )

    assert service.summaries() == [
        ReceiptSummary(b, "2026-10-06", "Kauppa B", 500, warning=True, reviewed=False),
        ReceiptSummary(a, "2026-10-05", "Testikauppa", 349, warning=False, reviewed=True),
    ]


def test_ac7_old_receipt_has_a_warning(service: ReviewService, receipts: ReceiptRepository) -> None:
    row = receipts.add("c" * 64, "vanha.jpg", TIME)

    assert service.summaries() == [
        ReceiptSummary(row.id, None, None, None, warning=True, reviewed=False)
    ]


def snapshot(db: sqlite3.Connection) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    lines = db.execute("SELECT * FROM receipt_lines ORDER BY id").fetchall()
    products = db.execute("SELECT * FROM products ORDER BY id").fetchall()
    return [tuple(row) for row in lines], [tuple(row) for row in products]


def test_ac13_choice_creates_the_product(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    receipt_id, (_, soda) = receipt_a(catalog, receipts)
    dairy = category_id(catalog, "Maitotuotteet")

    view = service.set_line_category(receipt_id, soda, dairy)

    line = view.lines[1]
    assert (line.category_name, line.category_source) == ("Maitotuotteet", "user")
    assert view.subtotals == [SubtotalView(dairy, "Maitotuotteet", "Ruoka", 349)]
    product = catalog.get_product_by_key("limu")
    assert product is not None
    assert product.category_id == dairy


def test_ac14_choice_moves_the_same_product(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    dairy = category_id(catalog, "Maitotuotteet")
    milk = catalog.add_product("Maito", "maito", dairy)
    remembered = LineCategory(dairy, "remembered", milk)
    receipt_id, (first, _) = add_receipt(
        receipts, [("Maito", 125, remembered), ("Maito", 125, remembered)], total=250
    )

    view = service.set_line_category(receipt_id, first, category_id(catalog, "Juomat"))

    assert [(line.category_name, line.category_source) for line in view.lines] == [
        ("Juomat", "user"),
        ("Juomat", "remembered"),
    ]


@pytest.mark.parametrize("case", ["line on another receipt", "missing line"])
def test_ac16_line_on_another_receipt_is_not_found(
    db: sqlite3.Connection,
    service: ReviewService,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
    case: str,
) -> None:
    a, _ = receipt_a(catalog, receipts)
    _, (b_line,) = add_receipt(receipts, [("Kahvi", 450, None)], number=2)
    line_id = b_line if case == "line on another receipt" else 999
    before = snapshot(db)

    with pytest.raises(NotFoundError):
        service.set_line_category(a, line_id, category_id(catalog, "Juomat"))

    assert snapshot(db) == before


def test_ac17_set_reviewed_both_ways(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    receipt_id, _ = receipt_a(catalog, receipts)

    assert service.set_reviewed(receipt_id, reviewed=True).reviewed is True
    assert service.set_reviewed(receipt_id, reviewed=False).reviewed is False


def test_ac9_unknown_receipt_for_review_state_and_image(
    service: ReviewService, tmp_path: Path
) -> None:
    with pytest.raises(NotFoundError):
        service.set_reviewed(999, reviewed=True)
    with pytest.raises(NotFoundError):
        service.image(999, tmp_path)


def test_ac10_image_of_a_receipt(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository, tmp_path: Path
) -> None:
    receipt_id, _ = receipt_a(catalog, receipts)
    (tmp_path / "kuitti.jpg").write_bytes(b"\xff\xd8\xff\xe0synthetic")

    assert service.image(receipt_id, tmp_path) == (b"\xff\xd8\xff\xe0synthetic", "image/jpeg")
