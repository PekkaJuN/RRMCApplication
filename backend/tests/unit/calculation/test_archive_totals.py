"""Totals of an archived year (archiving spec PC11, AC26, AC29, AC30)."""

from datetime import date

from app.calculation.archive_totals import ArchiveLine, ArchiveRow, archive_totals


def line(
    day: str,
    amount: int,
    product: str,
    category: str | None = None,
    group: str | None = None,
    *,
    deposit: bool = False,
) -> ArchiveLine:
    return ArchiveLine(date.fromisoformat(day), amount, product, category, group, deposit)


def months(**amounts: int) -> list[int]:
    """Twelve month sums; keywords m1 … m12 set the non-zero ones."""
    return [amounts.get(f"m{number}", 0) for number in range(1, 13)]


AC26_LINES = [
    line("2025-01-10", 250, "Maito 1l", "Maito", "Maitotuotteet"),
    line("2025-01-25", 250, "Maito 1l", "Maito", "Maitotuotteet"),
    line("2025-01-20", 400, "Edam", "Juusto", "Maitotuotteet"),
    line("2025-03-05", 500, "Kahvi 500g", "Kahvi"),
    line("2025-03-06", 100, "TUNTEMATON"),
    line("2025-03-06", -40, "PANTTI", deposit=True),
]


def product(name: str, sums: list[int]) -> ArchiveRow:
    return ArchiveRow("product", name, sums, sum(sums), [])


def test_ac26_tree_order_and_sums() -> None:
    totals = archive_totals(2025, AC26_LINES)

    assert totals.months == [f"2025-{number:02d}" for number in range(1, 13)]
    assert totals.rows == [
        ArchiveRow(
            "category", "Kahvi", months(m3=500), 500, [product("Kahvi 500g", months(m3=500))]
        ),
        ArchiveRow(
            "group",
            "Maitotuotteet",
            months(m1=900),
            900,
            [
                ArchiveRow(
                    "category", "Juusto", months(m1=400), 400, [product("Edam", months(m1=400))]
                ),
                ArchiveRow(
                    "category",
                    "Maito",
                    months(m1=500),
                    500,
                    [product("Maito 1l", months(m1=500))],
                ),
            ],
        ),
        ArchiveRow("none", None, months(m3=100), 100, [product("TUNTEMATON", months(m3=100))]),
    ]
    assert totals.month_totals == months(m1=900, m3=600)
    assert totals.total == 1500


def test_ac26_deposit_refunds_are_left_out() -> None:
    totals = archive_totals(2025, [line("2025-03-06", -40, "PANTTI", deposit=True)])

    assert totals.rows == []
    assert totals.total == 0


def test_ac29_the_same_product_name_in_two_categories_gives_two_rows() -> None:
    totals = archive_totals(
        2025, [line("2025-05-01", 100, "Ale", "Kahvi"), line("2025-05-02", 200, "Ale")]
    )

    assert totals.rows == [
        ArchiveRow("category", "Kahvi", months(m5=100), 100, [product("Ale", months(m5=100))]),
        ArchiveRow("none", None, months(m5=200), 200, [product("Ale", months(m5=200))]),
    ]


def test_ac30_top_level_rows_follow_finnish_order_with_no_category_last() -> None:
    names = ["Öljyt", "omenat", "Äyriäiset", "Banaanit"]
    lines = [line("2025-02-01", 100, "x")] + [
        line("2025-02-01", 100, f"{name} tuote", name) for name in names
    ]

    totals = archive_totals(2025, lines)

    assert [row.name for row in totals.rows] == [
        "Banaanit",
        "omenat",
        "Äyriäiset",
        "Öljyt",
        None,
    ]


def test_pc11_a_category_without_a_group_sorts_among_the_groups() -> None:
    totals = archive_totals(
        2025,
        [
            line("2025-01-01", 100, "a", "Maito", "Maitotuotteet"),
            line("2025-01-01", 100, "b", "Leipä", "Vilja"),
            line("2025-01-01", 100, "c", "Kahvi"),
        ],
    )

    assert [(row.kind, row.name) for row in totals.rows] == [
        ("category", "Kahvi"),
        ("group", "Maitotuotteet"),
        ("group", "Vilja"),
    ]


def test_pc11_products_sort_by_finnish_order_inside_a_category() -> None:
    totals = archive_totals(
        2025,
        [
            line("2025-01-01", 100, "Ömppu", "Hedelmät"),
            line("2025-01-01", 100, "appelsiini", "Hedelmät"),
            line("2025-01-01", 100, "Banaani", "Hedelmät"),
        ],
    )

    assert [row.name for row in totals.rows[0].children] == ["appelsiini", "Banaani", "Ömppu"]


def test_pc11_no_lines_give_no_rows_and_twelve_zero_months() -> None:
    totals = archive_totals(2024, [])

    assert totals.rows == []
    assert totals.month_totals == [0] * 12
    assert totals.months[0] == "2024-01"
    assert totals.months[-1] == "2024-12"
