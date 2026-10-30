"""SQL for groups, categories and products. Holds no rules; categorization owns those."""

import sqlite3
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Literal, cast

from app.storage.db import transaction

type Kind = Literal["group", "category"]

_CATEGORY_SELECT = """
    SELECT c.id, c.name, c.name_key, c.kind, c.parent_id,
           (SELECT count(*) FROM products p WHERE p.category_id = c.id) AS product_count,
           (SELECT count(*) FROM categories k WHERE k.parent_id = c.id) AS category_count,
           (SELECT count(*) FROM receipt_lines l WHERE l.category_id = c.id) AS line_count
    FROM categories c
"""

_PRODUCT_SELECT = """
    SELECT p.id, p.name, p.name_key, p.category_id,
           c.name AS category_name, g.name AS group_name
    FROM products p
    JOIN categories c ON c.id = p.category_id
    LEFT JOIN categories g ON g.id = c.parent_id
"""


@dataclass(frozen=True)
class CategoryRow:
    """A group or a category with its counts."""

    id: int
    name: str
    name_key: str
    kind: Kind
    parent_id: int | None
    product_count: int
    category_count: int
    line_count: int = 0


def _category(row: sqlite3.Row) -> CategoryRow:
    return CategoryRow(
        id=row["id"],
        name=row["name"],
        name_key=row["name_key"],
        kind=cast(Kind, row["kind"]),
        parent_id=row["parent_id"],
        product_count=row["product_count"],
        category_count=row["category_count"],
        line_count=row["line_count"],
    )


@dataclass(frozen=True)
class ProductRow:
    """A product with the names of its category and the category's group."""

    id: int
    name: str
    name_key: str
    category_id: int
    category_name: str
    group_name: str | None


def _product(row: sqlite3.Row) -> ProductRow:
    return ProductRow(
        id=row["id"],
        name=row["name"],
        name_key=row["name_key"],
        category_id=row["category_id"],
        category_name=row["category_name"],
        group_name=row["group_name"],
    )


class CatalogRepository:
    """Catalog queries on one connection. Callers own the transaction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def transaction(self) -> AbstractContextManager[None]:
        """One transaction on this repository's connection (see `db.transaction`)."""
        return transaction(self._connection)

    def add_category(self, name: str, name_key: str, kind: Kind, parent_id: int | None) -> int:
        cursor = self._connection.execute(
            "INSERT INTO categories (name, name_key, kind, parent_id) VALUES (?, ?, ?, ?)",
            (name, name_key, kind, parent_id),
        )
        return _row_id(cursor)

    def get_category(self, item_id: int) -> CategoryRow | None:
        row = self._connection.execute(_CATEGORY_SELECT + " WHERE c.id = ?", (item_id,)).fetchone()
        return _category(row) if row else None

    def get_category_by_key(self, name_key: str) -> CategoryRow | None:
        row = self._connection.execute(
            _CATEGORY_SELECT + " WHERE c.name_key = ?", (name_key,)
        ).fetchone()
        return _category(row) if row else None

    def list_categories(self) -> list[CategoryRow]:
        return [_category(row) for row in self._connection.execute(_CATEGORY_SELECT)]

    def update_category(
        self, item_id: int, name: str, name_key: str, kind: Kind, parent_id: int | None
    ) -> None:
        self._connection.execute(
            "UPDATE categories SET name = ?, name_key = ?, kind = ?, parent_id = ? WHERE id = ?",
            (name, name_key, kind, parent_id, item_id),
        )

    def delete_category(self, item_id: int) -> None:
        self._connection.execute("DELETE FROM categories WHERE id = ?", (item_id,))

    def add_product(self, name: str, name_key: str, category_id: int) -> int:
        cursor = self._connection.execute(
            "INSERT INTO products (name, name_key, category_id) VALUES (?, ?, ?)",
            (name, name_key, category_id),
        )
        return _row_id(cursor)

    def get_product(self, product_id: int) -> ProductRow | None:
        row = self._connection.execute(
            _PRODUCT_SELECT + " WHERE p.id = ?", (product_id,)
        ).fetchone()
        return _product(row) if row else None

    def get_product_by_key(self, name_key: str) -> ProductRow | None:
        row = self._connection.execute(
            _PRODUCT_SELECT + " WHERE p.name_key = ?", (name_key,)
        ).fetchone()
        return _product(row) if row else None

    def list_products(
        self, query_key: str | None = None, category_or_group_id: int | None = None
    ) -> list[ProductRow]:
        """List products, optionally those whose key contains `query_key` and those in a
        category or in any category of a group. Both filters combine with AND."""
        conditions: list[str] = []
        parameters: list[str | int] = []
        if query_key:
            # instr() matches literally, so % and _ in the query need no escaping.
            conditions.append("instr(p.name_key, ?) > 0")
            parameters.append(query_key)
        if category_or_group_id is not None:
            conditions.append("(c.id = ? OR c.parent_id = ?)")
            parameters += [category_or_group_id, category_or_group_id]
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self._connection.execute(_PRODUCT_SELECT + where, parameters)
        return [_product(row) for row in rows]

    def update_product(self, product_id: int, name: str, name_key: str, category_id: int) -> None:
        self._connection.execute(
            "UPDATE products SET name = ?, name_key = ?, category_id = ? WHERE id = ?",
            (name, name_key, category_id, product_id),
        )

    def move_product_lines(self, product_id: int, category_id: int) -> None:
        """Give every line that follows the product its new category (FR-36)."""
        self._connection.execute(
            "UPDATE receipt_lines SET category_id = ?, category_source = 'remembered'"
            " WHERE product_id = ?",
            (category_id, product_id),
        )

    def delete_product(self, product_id: int) -> None:
        self._connection.execute("DELETE FROM products WHERE id = ?", (product_id,))

    def get_app_state(self, key: str) -> str | None:
        row = self._connection.execute(
            "SELECT value FROM app_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set_app_state(self, key: str, value: str) -> None:
        self._connection.execute(
            "INSERT INTO app_state (key, value) VALUES (?, ?)"
            " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def _row_id(cursor: sqlite3.Cursor) -> int:
    assert cursor.lastrowid is not None  # noqa: S101 - set by every successful INSERT
    return cursor.lastrowid
