import sqlite3

import pytest


def add_category(db: sqlite3.Connection, name: str) -> int:
    cursor = db.execute(
        "INSERT INTO categories (name, name_key, kind) VALUES (?, ?, 'category')",
        (name, name.casefold()),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def test_ac16_migration_creates_the_budgets_table(db: sqlite3.Connection) -> None:
    columns = [row["name"] for row in db.execute("PRAGMA table_info(budgets)")]

    assert columns == ["category_id", "amount_cents"]
    assert db.execute("SELECT 1 FROM schema_version WHERE version = 7").fetchone() is not None


def test_ac4_a_negative_budget_is_refused(db: sqlite3.Connection) -> None:
    item = add_category(db, "Testi")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO budgets (category_id, amount_cents) VALUES (?, -1)", (item,))


def test_ac16_deleting_a_category_deletes_its_budget(db: sqlite3.Connection) -> None:
    item = add_category(db, "Testi")
    db.execute("INSERT INTO budgets (category_id, amount_cents) VALUES (?, 1000)", (item,))

    db.execute("DELETE FROM categories WHERE id = ?", (item,))

    assert db.execute("SELECT count(*) FROM budgets").fetchone()[0] == 0
