"""The current year totals reader (year with products spec T2, PC1–PC4)."""

import sqlite3
from datetime import date

from app.calculation.archive_totals import ArchiveLine, ArchiveRow, archive_totals
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import LineCategory, ReceiptRepository
from app.totals.year import YearTotals, read_year_totals

TIME = "2026-06-15T09:00:00Z"


class Data:
    """Builds reviewed receipts with one line each in a small synthetic catalog."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.catalog = CatalogRepository(db)
        self.receipts = ReceiptRepository(db)
        self.number = 0
        self.categories: dict[str, int] = {}
        self.products: dict[str, int] = {}

    def category(self, name: str, group: str | None = None) -> int:
        if name not in self.categories:
            parent = None
            if group is not None:
                if group not in self.categories:
                    self.categories[group] = self.catalog.add_category(
                        group, group.lower(), "group", None
                    )
                parent = self.categories[group]
            self.categories[name] = self.catalog.add_category(
                name, name.lower(), "category", parent
            )
        return self.categories[name]

    def line(
        self,
        day: str,
        amount: int,
        name: str,
        category: str | None = None,
        group: str | None = None,
        *,
        reviewed: bool = True,
        deposit: bool = False,
    ) -> None:
        self.number += 1
        receipt = self.receipts.add(f"{self.number:064d}", "a.jpg", TIME, purchase_date=day)
        line_category = None
        if category is not None:
            category_id = self.category(category, group)
            key = (name, category)
            if f"{key}" not in self.products:
                self.products[f"{key}"] = self.catalog.add_product(name, name.lower(), category_id)
            line_category = LineCategory(category_id, "user", self.products[f"{key}"])
        self.receipts.add_line(
            receipt.id, 1, name, amount, is_deposit_refund=deposit, category=line_category
        )
        if reviewed:
            self.receipts.set_reviewed(receipt.id, reviewed=True)

    def unreviewed(self, day: str) -> None:
        self.number += 1
        self.receipts.add(f"{self.number:064d}", "a.jpg", TIME, purchase_date=day)


def ac1_data(db: sqlite3.Connection) -> Data:
    data = Data(db)
    data.line("2026-01-10", 250, "Maito 1l", "Maito", "Maitotuotteet")
    data.line("2026-01-25", 250, "Maito 1l", "Maito", "Maitotuotteet")
    data.line("2026-01-20", 400, "Edam", "Juusto", "Maitotuotteet")
    data.line("2026-03-05", 500, "Kahvi 500g", "Kahvi")
    data.line("2026-03-06", 100, "TUNTEMATON")
    data.line("2026-03-06", -40, "Panttipalautus", deposit=True)
    return data


def months(**amounts: int) -> list[int]:
    return [amounts.get(f"m{number}", 0) for number in range(1, 13)]


def product(name: str, sums: list[int]) -> ArchiveRow:
    return ArchiveRow("product", name, sums, sum(sums))


def category(name: str, sums: list[int], *children: ArchiveRow) -> ArchiveRow:
    return ArchiveRow("category", name, sums, sum(sums), list(children))


def test_year_ac1_tree_and_totals(db: sqlite3.Connection) -> None:
    data = ac1_data(db)

    result = read_year_totals(data.receipts, 2026)

    totals = result.totals
    assert totals.year == 2026
    assert totals.months == [f"2026-{number:02d}" for number in range(1, 13)]
    assert totals.rows == [
        category("Kahvi", months(m3=500), product("Kahvi 500g", months(m3=500))),
        ArchiveRow(
            "group",
            "Maitotuotteet",
            months(m1=900),
            900,
            [
                category("Juusto", months(m1=400), product("Edam", months(m1=400))),
                category("Maito", months(m1=500), product("Maito 1l", months(m1=500))),
            ],
        ),
        ArchiveRow("none", None, months(m3=100), 100, [product("TUNTEMATON", months(m3=100))]),
    ]
    assert totals.month_totals == months(m1=900, m3=600)
    assert totals.total == 1500
    assert result.unreviewed == 0


def test_year_ac2_unreviewed_receipts_are_counted_not_summed(db: sqlite3.Connection) -> None:
    data = ac1_data(db)
    data.line("2026-02-01", 300, "Maito 1l", "Maito", "Maitotuotteet", reviewed=False)
    data.unreviewed("2026-04-01")

    result = read_year_totals(data.receipts, 2026)

    assert result.totals.month_totals == months(m1=900, m3=600)
    assert result.totals.total == 1500
    assert result.unreviewed == 2


def test_year_ac6_same_product_name_in_two_categories(db: sqlite3.Connection) -> None:
    data = Data(db)
    data.line("2026-02-01", 100, "Ale", "Kahvi")
    data.line("2026-02-02", 200, "Ale")

    rows = read_year_totals(data.receipts, 2026).totals.rows

    assert [(row.name, [(child.name, child.total) for child in row.children]) for row in rows] == [
        ("Kahvi", [("Ale", 100)]),
        (None, [("Ale", 200)]),
    ]


def test_year_ac7_finnish_name_order(db: sqlite3.Connection) -> None:
    data = Data(db)
    for number, name in enumerate(["Öljyt", "omenat", "Äyriäiset", "Banaanit"], start=1):
        data.line(f"2026-02-0{number}", 100, f"Tuote {number}", name)

    rows = read_year_totals(data.receipts, 2026).totals.rows

    assert [row.name for row in rows] == ["Banaanit", "omenat", "Äyriäiset", "Öljyt"]


def test_year_ac9_empty_year(db: sqlite3.Connection) -> None:
    data = Data(db)
    data.unreviewed("2026-05-01")
    data.line("2025-12-31", 100, "Kahvi 500g", "Kahvi")

    result = read_year_totals(data.receipts, 2026)

    assert result == YearTotals(archive_totals(2026, list[ArchiveLine]()), unreviewed=1)
    assert result.totals.rows == []
    assert result.totals.month_totals == [0] * 12
    assert result.totals.total == 0


def test_year_lines_become_archive_lines(db: sqlite3.Connection) -> None:
    data = Data(db)
    data.line("2026-07-04", 120, "Edam", "Juusto", "Maitotuotteet")

    totals = read_year_totals(data.receipts, 2026).totals

    assert totals == archive_totals(
        2026,
        [ArchiveLine(date(2026, 7, 4), 120, "Edam", "Juusto", "Maitotuotteet", False)],
    )
