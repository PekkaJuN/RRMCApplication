import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.categorization.defaults import seed_defaults
from app.categorization.errors import (
    DepositRefundLineError,
    InvalidNameError,
    NotFoundError,
    UnknownCategoryError,
)
from app.categorization.names import normalize_key
from app.review.errors import (
    DepositRefundAmountError,
    InvalidAmountError,
    InvalidDateError,
    InvalidStoreError,
)
from app.review.service import (
    LineEdit,
    LineView,
    ReceiptEdit,
    ReceiptSummary,
    ReceiptView,
    ReviewService,
    SubtotalView,
)
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import LineCategory, LineRow, ReceiptRepository

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

    view = service.edit_line(receipt_id, soda, LineEdit(category_id=dairy))

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

    view = service.edit_line(
        receipt_id, first, LineEdit(category_id=category_id(catalog, "Juomat"))
    )

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
        service.edit_line(a, line_id, LineEdit(category_id=category_id(catalog, "Juomat")))

    assert snapshot(db) == before


def test_ac17_set_reviewed_both_ways(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    receipt_id, _ = receipt_a(catalog, receipts)

    assert service.update_receipt(receipt_id, ReceiptEdit(reviewed=True)).reviewed is True
    assert service.update_receipt(receipt_id, ReceiptEdit(reviewed=False)).reviewed is False


def test_ac9_unknown_receipt_for_review_state_and_image(
    service: ReviewService, tmp_path: Path
) -> None:
    with pytest.raises(NotFoundError):
        service.update_receipt(999, ReceiptEdit(reviewed=True))
    with pytest.raises(NotFoundError):
        service.image(999, tmp_path)


def test_ac10_image_of_a_receipt(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository, tmp_path: Path
) -> None:
    receipt_id, _ = receipt_a(catalog, receipts)
    (tmp_path / "kuitti.jpg").write_bytes(b"\xff\xd8\xff\xe0synthetic")

    assert service.image(receipt_id, tmp_path) == (b"\xff\xd8\xff\xe0synthetic", "image/jpeg")


# Line editing spec: names and amounts (T8).


def line_row(receipts: ReceiptRepository, receipt_id: int, line_id: int) -> LineRow:
    return next(line for line in receipts.lines(receipt_id) if line.id == line_id)


def test_ac1_rename_without_match_makes_a_product(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)

    view = service.edit_line(a, soda, LineEdit(name="  Kivennäisvesi  "))

    line = view.lines[1]
    assert (line.name, line.category_name, line.category_source) == (
        "Kivennäisvesi",
        "Juomat",
        "user",
    )
    product = catalog.get_product_by_key("kivennäisvesi")
    assert product is not None
    assert product.category_id == category_id(catalog, "Juomat")
    assert line_row(receipts, a, soda).product_id == product.id


def test_ac2_rename_to_a_name_match(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)
    dairy = category_id(catalog, "Maitotuotteet")
    yoghurt = catalog.add_product("Jogurtti", "jogurtti", dairy)

    view = service.edit_line(a, soda, LineEdit(name="JOGURTTI"))

    line = view.lines[1]
    assert (line.name, line.category_name, line.group_name, line.category_source) == (
        "JOGURTTI",
        "Maitotuotteet",
        "Ruoka",
        "remembered",
    )
    assert line_row(receipts, a, soda).product_id == yoghurt
    assert view.subtotals == [SubtotalView(dairy, "Maitotuotteet", "Ruoka", 349)]
    assert len(catalog.list_products()) == 2


def test_ac3_rename_leaves_the_old_product_alone(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, (milk_line, _) = receipt_a(catalog, receipts)
    dairy = category_id(catalog, "Maitotuotteet")
    milk = catalog.get_product_by_key("maito")
    assert milk is not None
    b, (b_line,) = add_receipt(
        receipts, [("Maito", 125, LineCategory(dairy, "remembered", milk.id))], number=2
    )

    view = service.edit_line(a, milk_line, LineEdit(name="Kaurajuoma"))

    oat = catalog.get_product_by_key("kaurajuoma")
    assert oat is not None
    assert (oat.category_id, view.lines[0].category_source) == (dairy, "user")
    assert line_row(receipts, a, milk_line).product_id == oat.id
    assert catalog.get_product(milk.id) == milk
    assert line_row(receipts, b, b_line).product_id == milk.id
    assert line_row(receipts, b, b_line).category_source == "remembered"


def test_ac4_case_change_renames_only(
    db: sqlite3.Connection,
    service: ReviewService,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
) -> None:
    a, (milk_line, _) = receipt_a(catalog, receipts)
    before = line_row(receipts, a, milk_line)
    products = snapshot(db)[1]

    service.edit_line(a, milk_line, LineEdit(name="MAITO"))

    after = line_row(receipts, a, milk_line)
    assert after.name == "MAITO"
    assert (after.category_id, after.category_source, after.product_id) == (
        before.category_id,
        before.category_source,
        before.product_id,
    )
    assert snapshot(db)[1] == products


def test_ac5_rename_without_category(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    receipt_id, (odd,) = add_receipt(receipts, [("Outo", 50, None)])

    view = service.edit_line(receipt_id, odd, LineEdit(name="Outo tuote"))

    assert (view.lines[0].name, view.lines[0].category_id) == ("Outo tuote", None)
    assert catalog.list_products() == []


def test_ac6_rename_a_deposit_refund(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    catalog.add_product("Maito", "maito", category_id(catalog, "Maitotuotteet"))
    receipt_id, (refund,) = add_receipt(receipts, [("Panttipalautus", -40, None)])

    view = service.edit_line(receipt_id, refund, LineEdit(name="Maito"))

    line = view.lines[0]
    assert (line.name, line.is_deposit_refund, line.category_id) == ("Maito", True, None)
    assert line_row(receipts, receipt_id, refund).product_id is None


def test_ac7_amount_change(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)

    view = service.edit_line(a, soda, LineEdit(amount_cents=300))

    line = view.lines[1]
    assert (line.amount_cents, line.category_name, line.category_source) == (300, "Juomat", "model")
    assert (view.line_sum_cents, view.difference_cents, view.warning) == (425, -76, True)
    assert [subtotal.amount_cents for subtotal in view.subtotals] == [125, 300]


def test_ac8_zero_and_negative_amounts(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)

    assert service.edit_line(a, soda, LineEdit(amount_cents=0)).lines[1].amount_cents == 0
    view = service.edit_line(a, soda, LineEdit(amount_cents=-50))

    assert (view.lines[1].amount_cents, view.lines[1].category_name) == (-50, "Juomat")
    assert view.subtotals[-1] == SubtotalView(category_id(catalog, "Juomat"), "Juomat", None, -50)


@pytest.mark.parametrize(
    ("edit", "error"),
    [
        (LineEdit(name=""), InvalidNameError),
        (LineEdit(name="   "), InvalidNameError),
        (LineEdit(name="a" * 101), InvalidNameError),
        (LineEdit(amount_cents=100_000_000), InvalidAmountError),
        (LineEdit(amount_cents=-100_000_000), InvalidAmountError),
        (LineEdit(name="Vesi", amount_cents=100_000_000), InvalidAmountError),
    ],
)
def test_ac14_line_edit_errors_change_nothing(
    db: sqlite3.Connection,
    service: ReviewService,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
    edit: LineEdit,
    error: type[Exception],
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)
    before = snapshot(db)

    with pytest.raises(error):
        service.edit_line(a, soda, edit)

    assert snapshot(db) == before


def test_ac14_longest_name_and_largest_amount(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)

    view = service.edit_line(a, soda, LineEdit(name="a" * 100, amount_cents=99_999_999))

    assert (view.lines[1].name, view.lines[1].amount_cents) == ("a" * 100, 99_999_999)


# Line editing spec: the deposit refund flag and the category in one request (T9).


def test_ac9_mark_as_deposit_refund(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)

    view = service.edit_line(a, soda, LineEdit(is_deposit_refund=True, amount_cents=-40))

    line = view.lines[1]
    assert (line.is_deposit_refund, line.amount_cents) == (True, -40)
    assert (line.category_id, line.category_name, line.category_source) == (None, None, None)
    assert line_row(receipts, a, soda).product_id is None
    assert view.line_sum_cents == 85
    assert view.subtotals == [
        SubtotalView(category_id(catalog, "Maitotuotteet"), "Maitotuotteet", "Ruoka", 125)
    ]


@pytest.mark.parametrize(
    ("target", "edit"),
    [
        ("soda", LineEdit(is_deposit_refund=True)),
        ("refund", LineEdit(amount_cents=0)),
        ("refund", LineEdit(amount_cents=40)),
        ("soda", LineEdit(is_deposit_refund=True, amount_cents=10)),
    ],
)
def test_ac10_deposit_refund_must_be_negative(
    db: sqlite3.Connection,
    service: ReviewService,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
    target: str,
    edit: LineEdit,
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)
    refund = receipts.add_line(a, 3, "Panttipalautus", -40, is_deposit_refund=True)
    before = snapshot(db)

    with pytest.raises(DepositRefundAmountError):
        service.edit_line(a, soda if target == "soda" else refund, edit)

    assert snapshot(db) == before


def test_ac11_unmarking_resolves_the_line(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, _ = receipt_a(catalog, receipts)
    milk = catalog.get_product_by_key("maito")
    assert milk is not None
    bottles = receipts.add_line(a, 3, "Panttipalautus", -40, is_deposit_refund=True)
    small_milk = receipts.add_line(a, 4, "maito", -40, is_deposit_refund=True)

    service.edit_line(a, bottles, LineEdit(is_deposit_refund=False))
    view = service.edit_line(a, small_milk, LineEdit(is_deposit_refund=False))

    assert [(line.is_deposit_refund, line.category_name) for line in view.lines[2:]] == [
        (False, None),
        (False, "Maitotuotteet"),
    ]
    assert line_row(receipts, a, small_milk).category_source == "remembered"
    assert line_row(receipts, a, small_milk).product_id == milk.id
    dairy = category_id(catalog, "Maitotuotteet")
    assert SubtotalView(dairy, "Maitotuotteet", "Ruoka", 85) in view.subtotals
    assert view.subtotals[-1] == SubtotalView(None, None, None, -40)


def test_ac11_sending_the_same_flag_changes_nothing(
    db: sqlite3.Connection,
    service: ReviewService,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)
    before = snapshot(db)

    service.edit_line(a, soda, LineEdit(is_deposit_refund=False))

    assert snapshot(db) == before


def test_ac12_name_and_category_in_one_request(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)
    dairy = category_id(catalog, "Maitotuotteet")

    view = service.edit_line(a, soda, LineEdit(name="Kivennäisvesi", category_id=dairy))

    line = view.lines[1]
    assert (line.name, line.category_name, line.category_source) == (
        "Kivennäisvesi",
        "Maitotuotteet",
        "user",
    )
    water = [p for p in catalog.list_products() if p.name == "Kivennäisvesi"]
    assert [p.category_id for p in water] == [dairy]


@pytest.mark.parametrize("target", ["soda", "refund"])
def test_ac13_deposit_refund_with_a_category(
    db: sqlite3.Connection,
    service: ReviewService,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
    target: str,
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)
    refund = receipts.add_line(a, 3, "Panttipalautus", -40, is_deposit_refund=True)
    drinks = category_id(catalog, "Juomat")
    edit = (
        LineEdit(is_deposit_refund=True, amount_cents=-40, category_id=drinks)
        if target == "soda"
        else LineEdit(name="Pullot", category_id=drinks)
    )
    before = snapshot(db)

    with pytest.raises(DepositRefundLineError):
        service.edit_line(a, soda if target == "soda" else refund, edit)

    assert snapshot(db) == before


# Line editing spec: adding and deleting lines (T10).


def test_ac15_add_lines(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, _ = receipt_a(catalog, receipts)
    c, _ = add_receipt(receipts, [], number=3)
    milk = catalog.get_product_by_key("maito")
    assert milk is not None

    service.add_line(a, "Banaani", 99, is_deposit_refund=False)
    service.add_line(a, " maito ", 125, is_deposit_refund=False)
    view = service.add_line(a, "Panttipalautus", -40, is_deposit_refund=True)
    c_view = service.add_line(c, "Banaani", 99, is_deposit_refund=False)

    assert [
        (line.position, line.name, line.is_deposit_refund, line.category_name)
        for line in view.lines
    ] == [
        (1, "Maito", False, "Maitotuotteet"),
        (2, "Limu", False, "Juomat"),
        (3, "Banaani", False, None),
        (4, "maito", False, "Maitotuotteet"),
        (5, "Panttipalautus", True, None),
    ]
    added_milk = line_row(receipts, a, view.lines[3].id)
    assert (added_milk.category_source, added_milk.product_id) == ("remembered", milk.id)
    assert view.line_sum_cents == 533
    assert [line.position for line in c_view.lines] == [1]
    assert catalog.get_product_by_key("banaani") is None


@pytest.mark.parametrize(
    ("name", "amount", "refund", "error"),
    [
        ("", 99, False, InvalidNameError),
        ("Pullot", 40, True, DepositRefundAmountError),
        ("Banaani", 100_000_000, False, InvalidAmountError),
    ],
)
def test_ac16_add_line_errors(
    db: sqlite3.Connection,
    service: ReviewService,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
    name: str,
    amount: int,
    refund: bool,
    error: type[Exception],
) -> None:
    a, _ = receipt_a(catalog, receipts)
    before = snapshot(db)

    with pytest.raises(error):
        service.add_line(a, name, amount, is_deposit_refund=refund)

    assert snapshot(db) == before


def test_ac16_add_line_to_a_missing_receipt(service: ReviewService) -> None:
    with pytest.raises(NotFoundError):
        service.add_line(999, "Banaani", 99, is_deposit_refund=False)


def test_ac17_delete_a_line(
    db: sqlite3.Connection,
    service: ReviewService,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)
    _, (b_line,) = add_receipt(receipts, [("Kahvi", 450, None)], number=2)
    products = snapshot(db)[1]

    view = service.delete_line(a, soda)

    assert [line.name for line in view.lines] == ["Maito"]
    assert view.line_sum_cents == 125
    with pytest.raises(NotFoundError):
        service.delete_line(a, soda)
    with pytest.raises(NotFoundError):
        service.delete_line(a, b_line)
    assert receipts.get_line(b_line) is not None
    assert snapshot(db)[1] == products
    assert service.add_line(a, "Banaani", 99, is_deposit_refund=False).lines[1].position == 2


def test_ac18_delete_keeps_the_other_positions(
    service: ReviewService, receipts: ReceiptRepository
) -> None:
    receipt_id, (_, second, _) = add_receipt(
        receipts, [("Maito", 125, None), ("Limu", 224, None), ("Outo", 50, None)]
    )

    service.delete_line(receipt_id, second)
    view = service.add_line(receipt_id, "Banaani", 99, is_deposit_refund=False)

    assert [line.position for line in view.lines] == [1, 3, 4]


def test_ac7_amount_change_keeps_a_long_read_name(
    service: ReviewService, receipts: ReceiptRepository
) -> None:
    # A name read from a receipt may be longer than a product name; only a sent name is
    # checked (PC2, PC3).
    long_name = "Banaani " * 13
    receipt_id, (line_id,) = add_receipt(receipts, [(long_name, 99, None)])

    view = service.edit_line(receipt_id, line_id, LineEdit(amount_cents=120))

    assert (view.lines[0].name, view.lines[0].amount_cents) == (long_name, 120)


# Line editing spec: store, date and total (T11).


def test_ac19_edit_store_date_and_total(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, _ = receipt_a(catalog, receipts)

    view = service.update_receipt(
        a, ReceiptEdit(store="  Uusi   kauppa ", purchase_date="2026-10-06", total_cents=400)
    )

    assert (view.store, view.purchase_date, view.total_cents) == ("Uusi kauppa", "2026-10-06", 400)
    assert (view.difference_cents, view.warning) == (51, True)
    summary = service.summaries()[0]
    assert (summary.store, summary.purchase_date, summary.total_cents) == (
        "Uusi kauppa",
        "2026-10-06",
        400,
    )
    assert service.update_receipt(a, ReceiptEdit(store="")).store == ""


def test_ac20_fill_a_receipt_imported_before_reading(
    service: ReviewService, receipts: ReceiptRepository
) -> None:
    receipt_id, _ = add_receipt(receipts, [], total=None, purchase_date=None, store=None)

    view = service.update_receipt(
        receipt_id, ReceiptEdit(purchase_date="2026-01-15", total_cents=0)
    )

    assert (view.purchase_date, view.total_cents, view.store) == ("2026-01-15", 0, None)
    assert (view.line_sum_cents, view.difference_cents, view.warning) == (0, 0, False)


@pytest.mark.parametrize(
    ("edit", "error"),
    [
        (ReceiptEdit(store="a" * 101), InvalidStoreError),
        (ReceiptEdit(purchase_date="2026-02-30"), InvalidDateError),
        (ReceiptEdit(purchase_date="5.10.2026"), InvalidDateError),
        (ReceiptEdit(purchase_date=""), InvalidDateError),
        (ReceiptEdit(total_cents=-1), InvalidAmountError),
        (ReceiptEdit(total_cents=100_000_000), InvalidAmountError),
        (ReceiptEdit(store="X", total_cents=-1), InvalidAmountError),
        (ReceiptEdit(total_cents=-1, reviewed=True), InvalidAmountError),
    ],
)
def test_ac21_receipt_field_errors_change_nothing(
    db: sqlite3.Connection,
    service: ReviewService,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
    edit: ReceiptEdit,
    error: type[Exception],
) -> None:
    a, _ = receipt_a(catalog, receipts)
    before = receipts.get(a)

    with pytest.raises(error):
        service.update_receipt(a, edit)

    assert receipts.get(a) == before


def test_ac21_longest_store(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, _ = receipt_a(catalog, receipts)

    assert service.update_receipt(a, ReceiptEdit(store="a" * 100)).store == "a" * 100


def test_ac22_edits_keep_the_review_state(
    service: ReviewService, catalog: CatalogRepository, receipts: ReceiptRepository
) -> None:
    a, (milk_line, soda) = receipt_a(catalog, receipts)
    service.update_receipt(a, ReceiptEdit(reviewed=True))

    views = [
        service.edit_line(a, soda, LineEdit(name="Vesi")),
        service.edit_line(a, milk_line, LineEdit(amount_cents=130)),
        service.add_line(a, "Banaani", 99, is_deposit_refund=False),
        service.delete_line(a, soda),
        service.update_receipt(a, ReceiptEdit(total_cents=500)),
    ]
    last = service.update_receipt(a, ReceiptEdit(total_cents=349, reviewed=False))

    assert [view.reviewed for view in views] == [True] * 5
    assert (last.total_cents, last.reviewed) == (349, False)


# Line editing spec: ids out of SQLite's integer range (T12, PC11).

OUT_OF_RANGE = [2**63, -(2**63) - 1]


@pytest.mark.parametrize("bad", OUT_OF_RANGE)
def test_ac23_receipt_id_out_of_range_is_not_found(
    db: sqlite3.Connection,
    service: ReviewService,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
    tmp_path: Path,
    bad: int,
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)
    before = snapshot(db)
    calls = [
        lambda: service.receipt(bad),
        lambda: service.image(bad, tmp_path),
        lambda: service.edit_line(bad, soda, LineEdit(name="X")),
        lambda: service.add_line(bad, "X", 1, is_deposit_refund=False),
        lambda: service.delete_line(bad, soda),
        lambda: service.update_receipt(bad, ReceiptEdit(reviewed=True)),
        lambda: service.edit_line(a, bad, LineEdit(name="X")),
        lambda: service.delete_line(a, bad),
    ]

    for call in calls:
        with pytest.raises(NotFoundError):
            call()

    assert snapshot(db) == before


@pytest.mark.parametrize("bad", OUT_OF_RANGE)
def test_ac23_category_id_out_of_range_is_unknown(
    db: sqlite3.Connection,
    service: ReviewService,
    catalog: CatalogRepository,
    receipts: ReceiptRepository,
    bad: int,
) -> None:
    a, (_, soda) = receipt_a(catalog, receipts)
    before = snapshot(db)

    with pytest.raises(UnknownCategoryError):
        service.edit_line(a, soda, LineEdit(name="Vesi", category_id=bad))

    assert snapshot(db) == before
