"""An archived image is a duplicate until its year is deleted (archiving spec PC6, AC15,
AC16, AC19)."""

import sqlite3
import threading
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.image_files import image_identifier
from app.settings import Settings
from app.storage.archive_repository import ArchiveRepository
from app.storage.db import connect
from app.storage.receipt_repository import ReceiptRepository
from tests.integration.conftest import make_client
from tests.receipt_import_data import jpeg

TIME = "2025-03-10T10:00:00Z"
ARCHIVED_AT = "2026-11-13T10:00:00Z"
NEW_BODY = {"store": "Testikauppa", "purchase_date": "2026-10-05", "total_cents": 349}


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    for folder in (settings.import_dir, settings.done_dir, settings.failed_dir):
        folder.mkdir()
    with make_client(settings) as started:
        yield started


@pytest.fixture
def db(client: TestClient, settings: Settings) -> Iterator[sqlite3.Connection]:
    connection = connect(settings.db_path)
    yield connection
    connection.close()


def archive_image(db: sqlite3.Connection, data: bytes) -> None:
    """A reviewed 2025 receipt with the image's hash, archived."""
    receipts = ReceiptRepository(db)
    archive = ArchiveRepository(db)
    with receipts.transaction():
        row = receipts.add(image_identifier(data), "a.jpg", TIME, purchase_date="2025-03-10")
        receipts.set_reviewed(row.id, reviewed=True)
        archive.archive_year(2025, ARCHIVED_AT)


def run_import(client: TestClient) -> dict[str, Any]:
    assert client.post("/api/import").status_code == 202
    for _ in range(500):
        state = client.get("/api/import").json()
        if state["state"] == "finished":
            return state
        threading.Event().wait(0.01)
    raise AssertionError("the run did not finish")


def active_receipts(db: sqlite3.Connection) -> int:
    return db.execute("SELECT count(*) FROM receipts").fetchone()[0]


def test_pc6_image_known_looks_in_both_tables(db: sqlite3.Connection) -> None:
    archive_image(db, jpeg("archived"))
    receipts = ReceiptRepository(db)
    with receipts.transaction():
        receipts.add(image_identifier(jpeg("active")), "b.jpg", TIME)

    assert receipts.image_known(image_identifier(jpeg("archived")))
    assert receipts.image_known(image_identifier(jpeg("active")))
    assert not receipts.image_known(image_identifier(jpeg("new")))


def test_ac15_an_archived_image_is_a_duplicate_for_import(
    client: TestClient, db: sqlite3.Connection, settings: Settings
) -> None:
    archive_image(db, jpeg("a"))
    (settings.import_dir / "x.jpg").write_bytes(jpeg("a"))

    state = run_import(client)

    assert (state["imported"], state["duplicates"], state["failures"]) == (0, ["x.jpg"], [])
    assert active_receipts(db) == 0


def test_ac16_an_archived_image_is_a_duplicate_for_a_manual_receipt(
    client: TestClient, db: sqlite3.Connection, settings: Settings
) -> None:
    archive_image(db, jpeg("a"))
    (settings.failed_dir / "y.jpg").write_bytes(jpeg("a"))

    response = client.post("/api/receipts", json={**NEW_BODY, "image_file_name": "y.jpg"})

    assert response.status_code == 409
    assert response.json()["error"] == "duplicate_image"
    assert (settings.failed_dir / "y.jpg").read_bytes() == jpeg("a")
    assert active_receipts(db) == 0


def test_ac19_after_a_permanent_delete_the_image_imports_again(
    client: TestClient, db: sqlite3.Connection, settings: Settings
) -> None:
    archive_image(db, jpeg("a"))
    archive = ArchiveRepository(db)
    with archive.transaction():
        archive.delete_year(2025)
    (settings.import_dir / "x.jpg").write_bytes(jpeg("a"))

    state = run_import(client)

    assert (state["imported"], state["duplicates"]) == (1, [])
    assert active_receipts(db) == 1


def test_ac19_delete_through_the_api_frees_the_image(
    client: TestClient, db: sqlite3.Connection, settings: Settings
) -> None:
    # Audit addition: the delete of AC19 through DELETE /api/archive/2025.
    archive_image(db, jpeg("a"))
    assert client.delete("/api/archive/2025").status_code == 200
    (settings.import_dir / "x.jpg").write_bytes(jpeg("a"))

    state = run_import(client)

    assert (state["imported"], state["duplicates"]) == (1, [])
