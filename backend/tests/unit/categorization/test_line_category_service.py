import sqlite3
from datetime import UTC, datetime

import pytest

from app.categorization.defaults import seed_defaults
from app.categorization.errors import (
    DepositRefundLineError,
    InvalidNameError,
    NotACategoryError,
    NotFoundError,
    UnknownCategoryError,
)
from app.categorization.names import normalize_key
from app.categorization.service import LineCategoryService
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import LineCategory, ReceiptRepository

LONG_NAME = "Banaani " * 13  # 104 characters, over the 100 of a product name


@pytest.fixture
def catalog(db: sqlite3.Connection) -> CatalogRepository:
    repository = CatalogRepository(db)
    seed_defaults(repository, datetime(2026, 10, 30, tzinfo=UTC))
    return repository


@pytest.fixture
def receipts(db: sqlite3.Connection) -> ReceiptRepository:
    return ReceiptRepository(db)


@pytest.fixture
def service(catalog: CatalogRepository, receipts: ReceiptRepository) -> LineCategoryService:
    return LineCategoryService(catalog, receipts)


class LineWriteFails(ReceiptRepository):
    """The last write of a correction fails, after the product and its lines changed."""

    def set_line_category(self, line_id: int, category: LineCategory | None) -> None:
        raise sqlite3.OperationalError("simulated")


def test_ac15_failed_correction_rolls_back_the_product_and_its_lines(
    db: sqlite3.Connection, catalog: CatalogRepository
) -> None:
    dairy = category_id(catalog, "Maitotuotteet")
    product_id = catalog.add_product("Kevytmaito 1L", "kevytmaito 1l", dairy)
    first = add_line(db, "Kevytmaito 1L", LineCategory(dairy, "remembered", product_id))
    add_line(db, "Kevytmaito 1L", LineCategory(dairy, "remembered", product_id))
    before = snapshot(db)

    with pytest.raises(sqlite3.OperationalError):
        LineCategoryService(catalog, LineWriteFails(db)).set_category(
            first, category_id(catalog, "Juomat")
        )

    assert snapshot(db) == before


def category_id(catalog: CatalogRepository, name: str) -> int:
    row = catalog.get_category_by_key(normalize_key(name))
    assert row is not None
    return row.id


def add_line(
    db: sqlite3.Connection,
    name: str,
    category: LineCategory | None = None,
    *,
    amount: int = 99,
    refund: bool = False,
    receipt: str = "a",
) -> int:
    receipts = ReceiptRepository(db)
    row = receipts.get_by_hash(receipt * 64) or receipts.add(
        receipt * 64, f"{receipt}.jpg", "2026-10-30T10:00:00Z"
    )
    position = len(receipts.lines(row.id)) + 1
    receipts.add_line(row.id, position, name, amount, is_deposit_refund=refund, category=category)
    return db.execute("SELECT max(id) FROM receipt_lines").fetchone()[0]


def snapshot(db: sqlite3.Connection) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    lines = db.execute("SELECT * FROM receipt_lines ORDER BY id").fetchall()
    products = db.execute("SELECT * FROM products ORDER BY id").fetchall()
    return [tuple(row) for row in lines], [tuple(row) for row in products]


# AC16


@pytest.mark.parametrize(
    ("case", "error"),
    [
        ("missing line", NotFoundError),
        ("missing category", UnknownCategoryError),
        ("group", NotACategoryError),
        ("deposit refund", DepositRefundLineError),
        ("long name", InvalidNameError),
    ],
)
def test_ac16_errors_change_nothing(
    db: sqlite3.Connection,
    catalog: CatalogRepository,
    service: LineCategoryService,
    case: str,
    error: type[Exception],
) -> None:
    muut = LineCategory(category_id(catalog, "Muut"), "model", None)
    line_id = add_line(db, "Banaani", muut)
    refund_id = add_line(db, "Panttipalautus", amount=-40, refund=True)
    long_id = add_line(db, LONG_NAME, muut)
    target, chosen = {
        "missing line": (9999, category_id(catalog, "Hedelmät")),
        "missing category": (line_id, 9999),
        "group": (line_id, category_id(catalog, "Ruoka")),
        "deposit refund": (refund_id, category_id(catalog, "Muut")),
        "long name": (long_id, category_id(catalog, "Hedelmät")),
    }[case]
    before = snapshot(db)

    with pytest.raises(error):
        service.set_category(target, chosen)

    assert snapshot(db) == before


def test_ac23_refund_error_names_no_line(
    db: sqlite3.Connection, catalog: CatalogRepository, service: LineCategoryService
) -> None:
    refund_id = add_line(db, "Panttipalautus", amount=-40, refund=True)

    with pytest.raises(DepositRefundLineError) as raised:
        service.set_category(refund_id, category_id(catalog, "Muut"))

    assert "Panttipalautus" not in str(raised.value)
    assert "Panttipalautus" not in raised.value.message


# AC13-AC15


def test_ac13_unlinked_line_creates_product(
    db: sqlite3.Connection,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
    service: LineCategoryService,
) -> None:
    line_id = add_line(db, "Banaani", LineCategory(category_id(catalog, "Muut"), "model", None))
    fruit = category_id(catalog, "Hedelmät")

    stored = service.set_category(line_id, fruit)

    product = catalog.get_product_by_key("banaani")
    assert product is not None
    assert (product.name, product.category_id) == ("Banaani", fruit)
    assert stored.category == LineCategory(fruit, "user", product.id)
    assert receipts.get_line(line_id) == stored


def test_ac14_unlinked_line_uses_existing_product(
    db: sqlite3.Connection,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
    service: LineCategoryService,
) -> None:
    product_id = catalog.add_product("Banaani", "banaani", category_id(catalog, "Herkut"))
    muut = LineCategory(category_id(catalog, "Muut"), "model", None)
    line_id = add_line(db, "BANAANI", muut)
    other_id = add_line(
        db, "Banaani", LineCategory(category_id(catalog, "Herkut"), "remembered", product_id)
    )
    fruit = category_id(catalog, "Hedelmät")

    service.set_category(line_id, fruit)

    product = catalog.get_product(product_id)
    assert product is not None
    assert product.category_id == fruit
    assert len(catalog.list_products()) == 1
    first, other = receipts.get_line(line_id), receipts.get_line(other_id)
    assert first is not None
    assert other is not None
    assert first.category == LineCategory(fruit, "user", product_id)
    assert other.category == LineCategory(fruit, "remembered", product_id)


def test_ac15_linked_line_moves_other_lines(
    db: sqlite3.Connection,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
    service: LineCategoryService,
) -> None:
    dairy = category_id(catalog, "Maitotuotteet")
    product_id = catalog.add_product("Kevytmaito 1L", "kevytmaito 1l", dairy)
    remembered = LineCategory(dairy, "remembered", product_id)
    line_ids = [
        add_line(db, "Kevytmaito 1L", remembered, receipt="a"),
        add_line(db, "Kevytmaito 1L", remembered, receipt="a"),
        add_line(db, "Kevytmaito 1L", remembered, receipt="b"),
    ]
    drinks = category_id(catalog, "Juomat")

    service.set_category(line_ids[0], drinks)

    product = catalog.get_product(product_id)
    assert product is not None
    assert product.category_id == drinks
    categories = [receipts.get_line(item) for item in line_ids]
    assert [line.category if line else None for line in categories] == [
        LineCategory(drinks, "user", product_id),
        LineCategory(drinks, "remembered", product_id),
        LineCategory(drinks, "remembered", product_id),
    ]


def test_ac15_confirming_the_same_category_changes_only_the_source(
    db: sqlite3.Connection,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
    service: LineCategoryService,
) -> None:
    dairy = category_id(catalog, "Maitotuotteet")
    product_id = catalog.add_product("Kevytmaito 1L", "kevytmaito 1l", dairy)
    first = add_line(db, "Kevytmaito 1L", LineCategory(dairy, "remembered", product_id))
    other = add_line(db, "Kevytmaito 1L", LineCategory(dairy, "user", product_id))

    service.set_category(first, dairy)

    lines = [receipts.get_line(item) for item in (first, other)]
    assert [line.category if line else None for line in lines] == [
        LineCategory(dairy, "user", product_id),
        LineCategory(dairy, "user", product_id),
    ]
