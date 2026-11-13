"""SQL of archiving (archiving spec P1, P3 step 4)."""

import sqlite3

from app.storage.archive_repository import (
    ArchivedYearRow,
    ArchiveLineRow,
    ArchiveRepository,
    ArchiveRun,
    CandidateRow,
    YearCounts,
)
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import LineCategory, ReceiptRepository

TIME = "2026-01-02T10:00:00Z"
ARCHIVED_AT = "2026-11-13T10:00:00Z"


class Data:
    """Synthetic active data on one connection."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db
        self.catalog = CatalogRepository(db)
        self.receipts = ReceiptRepository(db)
        self.hashes = 0

    def group(self, name: str) -> int:
        return self.catalog.add_category(name, name.casefold(), "group", None)

    def category(self, name: str, group: int | None = None) -> int:
        return self.catalog.add_category(name, name.casefold(), "category", group)

    def product(self, name: str, category: int) -> int:
        return self.catalog.add_product(name, name.casefold(), category)

    def receipt(
        self, purchase_date: str | None, *, reviewed: bool = True, image: str | None = "x.jpg"
    ) -> int:
        self.hashes += 1
        image_hash = f"{self.hashes:064x}" if image else None
        row = self.receipts.add(
            image_hash, image, TIME, store="Kauppa", purchase_date=purchase_date, total_cents=100
        )
        self.receipts.set_reviewed(row.id, reviewed=reviewed)
        return row.id

    def line(
        self,
        receipt: int,
        position: int,
        name: str,
        amount: int,
        *,
        category: int | None = None,
        product: int | None = None,
        deposit: bool = False,
    ) -> int:
        line_category = LineCategory(category, "user", product) if category is not None else None
        return self.receipts.add_line(
            receipt, position, name, amount, is_deposit_refund=deposit, category=line_category
        )

    def count(self, table: str) -> int:
        return self.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]  # noqa: S608


def test_ac1_archive_year_moves_the_years_receipts_and_lines(db: sqlite3.Connection) -> None:
    data = Data(db)
    a = data.receipt("2025-03-10", image="a.jpg")
    data.line(a, 1, "MAITO", 100)
    data.line(a, 2, "LEIPÄ", 200)
    b = data.receipt("2025-12-31", image=None)
    data.line(b, 1, "KAHVI", 300)
    c = data.receipt("2026-01-01")
    d = data.receipt(None)
    repository = ArchiveRepository(db)

    with repository.transaction():
        run = repository.archive_year(2025, ARCHIVED_AT)

    assert run == ArchiveRun(receipts=2, lines=3, images=[(a, "a.jpg")])
    remaining = [row["id"] for row in db.execute("SELECT id FROM receipts ORDER BY id")]
    assert remaining == [c, d]
    archived = db.execute(
        "SELECT id, year, purchase_date, store, total_cents, archived_at"
        " FROM archived_receipts ORDER BY id"
    ).fetchall()
    assert [tuple(row) for row in archived] == [
        (a, 2025, "2025-03-10", "Kauppa", 100, ARCHIVED_AT),
        (b, 2025, "2025-12-31", "Kauppa", 100, ARCHIVED_AT),
    ]
    positions = db.execute(
        "SELECT receipt_id, position, name FROM archived_lines ORDER BY receipt_id, position"
    ).fetchall()
    assert [tuple(row) for row in positions] == [
        (a, 1, "MAITO"),
        (a, 2, "LEIPÄ"),
        (b, 1, "KAHVI"),
    ]
    assert data.count("receipt_lines") == 0


def test_ac2_ac28_lines_keep_product_category_and_group_as_names(db: sqlite3.Connection) -> None:
    data = Data(db)
    dairy = data.group("Maitotuotteet")
    milk = data.category("Maito", dairy)
    coffee = data.category("Kahvi")
    milk_product = data.product("Maito 1l", milk)
    receipt = data.receipt("2025-06-01")
    data.line(receipt, 1, "MAITO 1L VALIO", 250, category=milk, product=milk_product)
    data.line(receipt, 2, "KAHVI", 500, category=coffee)
    data.line(receipt, 3, "TUNTEMATON", 100)
    data.line(receipt, 4, "PANTTI", -40, deposit=True)
    repository = ArchiveRepository(db)

    with repository.transaction():
        repository.archive_year(2025, ARCHIVED_AT)

    rows = db.execute(
        "SELECT product_name, group_name, category_name, is_deposit_refund, amount_cents"
        " FROM archived_lines ORDER BY position"
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("Maito 1l", "Maitotuotteet", "Maito", 0, 250),
        ("KAHVI", None, "Kahvi", 0, 500),
        ("TUNTEMATON", None, None, 0, 100),
        ("PANTTI", None, None, 1, -40),
    ]


def test_ac4_catalog_products_and_budgets_are_unchanged(db: sqlite3.Connection) -> None:
    data = Data(db)
    milk = data.category("Maito")
    product = data.product("Maito 1l", milk)
    data.catalog.set_budget(milk, 5000)
    receipt = data.receipt("2025-06-01")
    data.line(receipt, 1, "MAITO", 250, category=milk, product=product)
    tables = ("categories", "products", "budgets")
    before = {table: db.execute(f"SELECT * FROM {table}").fetchall() for table in tables}  # noqa: S608
    repository = ArchiveRepository(db)

    with repository.transaction():
        repository.archive_year(2025, ARCHIVED_AT)

    after = {table: db.execute(f"SELECT * FROM {table}").fetchall() for table in tables}  # noqa: S608
    assert {key: [tuple(row) for row in rows] for key, rows in after.items()} == {
        key: [tuple(row) for row in rows] for key, rows in before.items()
    }


def test_ac7_year_counts_count_receipts_and_unreviewed(db: sqlite3.Connection) -> None:
    data = Data(db)
    data.receipt("2025-01-01")
    data.receipt("2025-05-05", reviewed=False)
    data.receipt("2025-12-31", reviewed=False)
    data.receipt("2026-01-01", reviewed=False)
    data.receipt(None, reviewed=False)

    assert ArchiveRepository(db).year_counts(2025) == YearCounts(receipts=3, unreviewed=2)
    assert ArchiveRepository(db).year_counts(2024) == YearCounts(receipts=0, unreviewed=0)


def test_ac11_archiving_again_adds_to_the_year(db: sqlite3.Connection) -> None:
    data = Data(db)
    data.receipt("2025-01-01")
    data.receipt("2025-02-01")
    repository = ArchiveRepository(db)
    with repository.transaction():
        repository.archive_year(2025, ARCHIVED_AT)
    data.receipt("2025-06-01", image=None)

    with repository.transaction():
        run = repository.archive_year(2025, ARCHIVED_AT)

    assert run.receipts == 1
    assert repository.archived() == [ArchivedYearRow(2025, receipts=3, lines=0, images=2)]


def test_ac12_set_file_names_updates_the_moved_names(db: sqlite3.Connection) -> None:
    data = Data(db)
    receipt = data.receipt("2025-01-01", image="a.jpg")
    repository = ArchiveRepository(db)
    with repository.transaction():
        repository.archive_year(2025, ARCHIVED_AT)

    with repository.transaction():
        repository.set_file_names([(receipt, "a (2).jpg")])

    name = db.execute("SELECT file_name FROM archived_receipts").fetchone()[0]
    assert name == "a (2).jpg"


def test_ac17_overview_of_archived_years_and_candidates(db: sqlite3.Connection) -> None:
    data = Data(db)
    old = data.receipt("2025-03-01")
    data.line(old, 1, "A", 100)
    data.line(old, 2, "B", 100)
    data.receipt("2025-04-01", image=None)
    repository = ArchiveRepository(db)
    with repository.transaction():
        repository.archive_year(2025, ARCHIVED_AT)
    first = data.receipt("2024-01-01")
    data.line(first, 1, "C", 100)
    data.receipt("2024-02-01", reviewed=False)
    data.receipt("2023-02-01", image=None)
    data.receipt("2026-02-01")
    data.receipt(None)

    assert repository.archived() == [ArchivedYearRow(2025, receipts=2, lines=2, images=1)]
    assert repository.candidates(before_year=2026) == [
        CandidateRow(2024, receipts=2, lines=1, images=2, unreviewed=1),
        CandidateRow(2023, receipts=1, lines=0, images=0, unreviewed=0),
    ]


def test_ac18_delete_year_removes_its_rows_and_counts_them(db: sqlite3.Connection) -> None:
    data = Data(db)
    receipt = data.receipt("2025-03-01")
    data.line(receipt, 1, "A", 100)
    data.line(receipt, 2, "B", 100)
    data.receipt("2024-03-01")
    repository = ArchiveRepository(db)
    with repository.transaction():
        repository.archive_year(2025, ARCHIVED_AT)
        repository.archive_year(2024, ARCHIVED_AT)

    with repository.transaction():
        deleted = repository.delete_year(2025)

    assert deleted == (1, 2)
    assert repository.archived() == [ArchivedYearRow(2024, receipts=1, lines=0, images=1)]
    assert data.count("archived_lines") == 0


def test_ac20_delete_of_a_year_not_archived_counts_nothing(db: sqlite3.Connection) -> None:
    repository = ArchiveRepository(db)

    with repository.transaction():
        assert repository.delete_year(2023) == (0, 0)


def test_ac26_year_lines_give_the_names_and_dates(db: sqlite3.Connection) -> None:
    data = Data(db)
    milk = data.category("Maito", data.group("Maitotuotteet"))
    receipt = data.receipt("2025-01-10")
    data.line(receipt, 1, "MAITO", 250, category=milk)
    data.line(receipt, 2, "PANTTI", -40, deposit=True)
    data.receipt("2024-01-10")
    repository = ArchiveRepository(db)
    with repository.transaction():
        repository.archive_year(2025, ARCHIVED_AT)
        repository.archive_year(2024, ARCHIVED_AT)

    assert repository.has_year(2025)
    assert not repository.has_year(2023)
    assert repository.year_lines(2025) == [
        ArchiveLineRow("2025-01-10", 250, "MAITO", "Maito", "Maitotuotteet", False),
        ArchiveLineRow("2025-01-10", -40, "PANTTI", None, None, True),
    ]


def test_ac22_archived_years_in_a_range(db: sqlite3.Connection) -> None:
    data = Data(db)
    data.receipt("2024-05-01")
    data.receipt("2025-05-01")
    repository = ArchiveRepository(db)
    with repository.transaction():
        repository.archive_year(2024, ARCHIVED_AT)
        repository.archive_year(2025, ARCHIVED_AT)

    assert repository.archived_years(2024, 2026) == [2024, 2025]
    assert repository.archived_years(2025, 2026) == [2025]
    assert repository.archived_years(2026, 2026) == []
