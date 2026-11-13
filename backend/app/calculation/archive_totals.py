"""Month and year totals of an archived year per group, category and product (archiving
spec PC11). The archive keeps names, not catalog ids, so the rows are built from the names
and sorted in Finnish order."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from app.calculation.names import finnish_key

ArchiveRowKind = Literal["group", "category", "product", "none"]


@dataclass(frozen=True)
class ArchiveLine:
    purchase_date: date
    amount_cents: int
    product_name: str
    category_name: str | None
    group_name: str | None
    is_deposit_refund: bool


@dataclass(frozen=True)
class ArchiveRow:
    kind: ArchiveRowKind
    name: str | None
    months: list[int]
    total: int
    children: list["ArchiveRow"] = field(default_factory=lambda: list[ArchiveRow]())
    # Lines per month, so a month whose lines add up to 0 is told from a month without lines
    # (the CSV file has a row for every product with lines, PC13). Not part of equality.
    line_counts: list[int] = field(default_factory=lambda: [0] * 12, compare=False)


@dataclass(frozen=True)
class ArchiveTotals:
    year: int
    months: list[str]
    rows: list[ArchiveRow]
    month_totals: list[int]
    total: int


@dataclass
class _Node:
    """A row being built. Only a product collects sums; the others add up their children."""

    kind: ArchiveRowKind
    name: str | None
    sums: list[int] = field(default_factory=lambda: [0] * 12)
    counts: list[int] = field(default_factory=lambda: [0] * 12)
    children: dict[tuple[ArchiveRowKind, str | None], "_Node"] = field(
        default_factory=lambda: dict[tuple[ArchiveRowKind, str | None], _Node]()
    )

    def child(self, kind: ArchiveRowKind, name: str | None) -> "_Node":
        return self.children.setdefault((kind, name), _Node(kind, name))


def archive_totals(year: int, lines: Iterable[ArchiveLine]) -> ArchiveTotals:
    root = _Node("none", None)
    for line in lines:
        # Deposit refunds are not spending (FR-44).
        if line.is_deposit_refund:
            continue
        if line.category_name is None:
            parent = root.child("none", None)
        elif line.group_name is None:
            parent = root.child("category", line.category_name)
        else:
            parent = root.child("group", line.group_name).child("category", line.category_name)
        leaf = parent.child("product", line.product_name)
        month = line.purchase_date.month - 1
        leaf.sums[month] += line.amount_cents
        leaf.counts[month] += 1
    rows = _rows(root)
    month_totals = [sum(row.months[index] for row in rows) for index in range(12)]
    return ArchiveTotals(
        year=year,
        months=[f"{year:04d}-{month:02d}" for month in range(1, 13)],
        rows=rows,
        month_totals=month_totals,
        total=sum(month_totals),
    )


def _rows(node: _Node) -> list[ArchiveRow]:
    built = [_row(child) for child in node.children.values()]
    # `Ei kategoriaa` is last at the top level; elsewhere every row has a name.
    return sorted(built, key=lambda row: (row.kind == "none", finnish_key(row.name or "")))


def _row(node: _Node) -> ArchiveRow:
    if node.kind == "product":
        return ArchiveRow(
            "product", node.name, list(node.sums), sum(node.sums), line_counts=list(node.counts)
        )
    children = _rows(node)
    sums = [sum(child.months[index] for child in children) for index in range(12)]
    counts = [sum(child.line_counts[index] for child in children) for index in range(12)]
    return ArchiveRow(node.kind, node.name, sums, sum(sums), children, line_counts=counts)
