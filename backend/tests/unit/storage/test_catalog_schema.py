import sqlite3

import pytest


def add_item(db: sqlite3.Connection, name: str, kind: str, parent_id: int | None = None) -> int:
    cursor = db.execute(
        "INSERT INTO categories (name, name_key, kind, parent_id) VALUES (?, ?, ?, ?)",
        (name, name.lower(), kind, parent_id),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def table_names(db: sqlite3.Connection) -> set[str]:
    rows = db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row["name"] for row in rows}


def test_ac1_migration_creates_the_catalog_tables(db: sqlite3.Connection) -> None:
    assert {"categories", "products", "app_state"} <= table_names(db)
    # Later migrations raise the newest version; 1 must still be the catalog migration.
    assert db.execute("SELECT 1 FROM schema_version WHERE version = 1").fetchone() is not None


def test_ac4_name_key_is_unique_across_kinds(db: sqlite3.Connection) -> None:
    add_item(db, "Ruoka", "group")

    with pytest.raises(sqlite3.IntegrityError):
        add_item(db, "ruoka", "category")


def test_ac10_group_with_a_parent_is_refused(db: sqlite3.Connection) -> None:
    ruoka = add_item(db, "Ruoka", "group")

    with pytest.raises(sqlite3.IntegrityError):
        add_item(db, "Auto", "group", parent_id=ruoka)


def test_ac13_category_used_by_a_product_cannot_be_deleted(db: sqlite3.Connection) -> None:
    juomat = add_item(db, "Juomat", "category")
    db.execute(
        "INSERT INTO products (name, name_key, category_id) VALUES (?, ?, ?)",
        ("Mehu", "mehu", juomat),
    )

    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM categories WHERE id = ?", (juomat,))
