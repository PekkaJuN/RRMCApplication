"""Archiving, overview and permanent delete through /api/archive (archiving spec PC2–PC4,
PC7, PC8; AC1, AC5–AC14, AC17, AC18, AC20, AC42)."""

import logging
import sqlite3
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.archive.service import ArchiveFiles, LocalArchiveFiles
from app.main import create_app
from app.receipt_import.schemas import ImportStateOut
from app.receipt_import.service import ImportService
from app.settings import Settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from app.storage.receipt_repository import LineCategory, ReceiptRepository
from tests.integration.conftest import BASE_URL

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=UTC)
TIME = "2025-03-10T10:00:00Z"


class RunningImport(ImportService):
    """An import service whose run is in progress."""

    def state(self) -> ImportStateOut:
        return ImportStateOut(
            state="running",
            total=1,
            processed=0,
            imported=0,
            duplicates=[],
            failures=[],
            started_at=TIME,
            finished_at=None,
        )


class FailingMove(LocalArchiveFiles):
    """Moving `a.jpg` fails; everything else works."""

    def move(self, source: Path, target: Path) -> None:
        if source.name == "a.jpg":
            raise OSError("simulated")
        super().move(source, target)


@pytest.fixture
def folders(settings: Settings) -> Settings:
    for folder in (
        settings.import_dir,
        settings.done_dir,
        settings.failed_dir,
        settings.archive_dir,
    ):
        folder.mkdir()
    return settings


ClientFactory = Callable[..., TestClient]


@pytest.fixture
def open_client(folders: Settings) -> Iterator[ClientFactory]:
    clients: list[TestClient] = []

    def open_one(
        *,
        clock: Callable[[], datetime] = lambda: NOW,
        import_service: ImportService | None = None,
        archive_files: ArchiveFiles | None = None,
    ) -> TestClient:
        app = create_app(
            folders, clock=clock, import_service=import_service, archive_files=archive_files
        )
        client = TestClient(app, raise_server_exceptions=False, base_url=BASE_URL)
        client.__enter__()
        clients.append(client)
        return client

    yield open_one
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def api(open_client: ClientFactory) -> TestClient:
    return open_client()


@pytest.fixture
def db(api: TestClient, folders: Settings) -> Iterator[sqlite3.Connection]:
    connection = connect(folders.db_path)
    yield connection
    connection.close()


class Seed:
    def __init__(self, db: sqlite3.Connection, settings: Settings) -> None:
        self.receipts = ReceiptRepository(db)
        self.catalog = CatalogRepository(db)
        self.settings = settings
        self.count = 0

    def receipt(
        self,
        purchase_date: str | None,
        *,
        reviewed: bool = True,
        image: str | None = None,
        lines: int = 0,
        store: str = "Kauppa",
    ) -> int:
        self.count += 1
        image_hash = f"{self.count:064x}" if image else None
        with self.receipts.transaction():
            row = self.receipts.add(
                image_hash, image, TIME, store=store, purchase_date=purchase_date, total_cents=100
            )
            self.receipts.set_reviewed(row.id, reviewed=reviewed)
            for position in range(1, lines + 1):
                self.receipts.add_line(row.id, position, "MAITO", 100, is_deposit_refund=False)
        if image:
            (self.settings.done_dir / image).write_bytes(b"\xff\xd8\xff" + image.encode())
        return row.id


@pytest.fixture
def seed(db: sqlite3.Connection, folders: Settings) -> Seed:
    return Seed(db, folders)


def count(db: sqlite3.Connection, table: str) -> int:
    return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]  # noqa: S608


def snapshot(db: sqlite3.Connection) -> list[list[tuple[Any, ...]]]:
    tables = ("receipts", "receipt_lines", "archived_receipts", "archived_lines")
    return [
        [tuple(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY 1")]  # noqa: S608
        for table in tables
    ]


def test_ac1_archive_a_year(api: TestClient, db: sqlite3.Connection, seed: Seed) -> None:
    a = seed.receipt("2025-03-10", lines=2)
    b = seed.receipt("2025-12-31", lines=1)
    c = seed.receipt("2026-01-01")
    d = seed.receipt(None)

    response = api.post("/api/archive/2025")

    assert response.status_code == 200
    assert response.json() == {
        "year": 2025,
        "receipts": 2,
        "lines": 3,
        "images_moved": 0,
        "images_not_moved": [],
    }
    assert [row[0] for row in db.execute("SELECT id FROM receipts ORDER BY id")] == [c, d]
    archived = [row[0] for row in db.execute("SELECT id FROM archived_receipts ORDER BY id")]
    assert archived == [a, b]
    assert count(db, "archived_lines") == 3


def test_ac2_ac3_later_catalog_changes_do_not_touch_the_archive(
    api: TestClient, db: sqlite3.Connection, seed: Seed
) -> None:
    # Names outside the default list, so they do not collide with it.
    group = api.post("/api/categories", json={"name": "Testiryhmä", "kind": "group"}).json()
    milk = api.post(
        "/api/categories",
        json={"name": "Testimaito", "kind": "category", "parent_id": group["id"]},
    ).json()
    coffee = api.post("/api/categories", json={"name": "Testikahvi", "kind": "category"}).json()
    product = api.post("/api/products", json={"name": "Testituote", "category_id": milk["id"]})
    receipt = seed.receipt("2025-03-10")
    with seed.receipts.transaction():
        seed.receipts.add_line(
            receipt,
            1,
            "MAITO",
            250,
            is_deposit_refund=False,
            category=LineCategory(milk["id"], "user", product.json()["id"]),
        )
    assert api.post("/api/archive/2025").status_code == 200

    renamed = api.patch(f"/api/categories/{milk['id']}", json={"name": "Testimaidot"})
    moved = api.patch(f"/api/products/{product.json()['id']}", json={"category_id": coffee["id"]})
    deleted = api.delete(f"/api/categories/{milk['id']}")

    assert (renamed.status_code, moved.status_code, deleted.status_code) == (200, 200, 204)
    row = db.execute("SELECT group_name, category_name, product_name FROM archived_lines")
    assert tuple(row.fetchone()) == ("Testiryhmä", "Testimaito", "Testituote")


def test_ac5_current_and_future_years_are_refused(
    api: TestClient, db: sqlite3.Connection, seed: Seed
) -> None:
    seed.receipt("2026-05-01")
    seed.receipt("2027-05-01")
    before = snapshot(db)

    for year in ("2026", "2027"):
        response = api.post(f"/api/archive/{year}")
        assert response.status_code == 409
        assert response.json()["error"] == "year_not_finished"
    assert snapshot(db) == before


def test_ac6_finnish_time_decides_the_current_year(
    open_client: ClientFactory, folders: Settings
) -> None:
    client = open_client(clock=lambda: datetime(2025, 12, 31, 22, 30, tzinfo=UTC))
    connection = connect(folders.db_path)
    try:
        Seed(connection, folders).receipt("2025-06-01")
    finally:
        connection.close()

    assert client.post("/api/archive/2025").status_code == 200


def test_ac7_unreviewed_receipts_block_archiving(
    api: TestClient, db: sqlite3.Connection, seed: Seed
) -> None:
    seed.receipt("2025-01-01")
    seed.receipt("2025-02-01", reviewed=False)
    seed.receipt("2025-03-01", reviewed=False)
    before = snapshot(db)

    response = api.post("/api/archive/2025")

    assert response.status_code == 409
    body = response.json()
    assert (body["error"], body["count"]) == ("unreviewed_receipts", 2)
    assert body["message"]
    assert snapshot(db) == before


def test_ac8_nothing_to_archive(api: TestClient, seed: Seed) -> None:
    seed.receipt(None)

    response = api.post("/api/archive/2024")

    assert response.status_code == 404
    assert response.json()["error"] == "nothing_to_archive"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/archive/abcd"),
        ("post", "/api/archive/1999"),
        ("delete", "/api/archive/10000"),
        ("post", "/api/archive/02025"),
    ],
)
def test_ac9_bad_year(api: TestClient, method: str, path: str) -> None:
    response = api.request(method.upper(), path)

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_year"


def test_ac10_refused_while_an_import_runs(open_client: ClientFactory, folders: Settings) -> None:
    client = open_client(import_service=RunningImport(folders))
    connection = connect(folders.db_path)
    try:
        Seed(connection, folders).receipt("2025-06-01")
        before = snapshot(connection)

        response = client.post("/api/archive/2025")

        assert response.status_code == 409
        assert response.json()["error"] == "import_running"
        assert snapshot(connection) == before
    finally:
        connection.close()


def test_ac11_archiving_again_adds_to_the_year(api: TestClient, seed: Seed) -> None:
    seed.receipt("2025-01-01")
    seed.receipt("2025-02-01")
    api.post("/api/archive/2025")
    seed.receipt("2025-06-01")

    response = api.post("/api/archive/2025")

    assert response.json()["receipts"] == 1
    assert api.get("/api/archive").json()["archived"][0]["receipts"] == 3


def test_ac12_images_move_after_the_commit(
    api: TestClient, db: sqlite3.Connection, seed: Seed, folders: Settings
) -> None:
    seed.receipt("2025-01-01", image="a.jpg")
    seed.receipt("2025-02-01", image="b.jpg")
    (folders.archive_dir / "a.jpg").write_bytes(b"older")

    response = api.post("/api/archive/2025")

    assert response.json()["images_moved"] == 2
    assert response.json()["images_not_moved"] == []
    assert sorted(path.name for path in folders.archive_dir.iterdir()) == [
        "a (2).jpg",
        "a.jpg",
        "b.jpg",
    ]
    assert list(folders.done_dir.iterdir()) == []
    names = [row[0] for row in db.execute("SELECT file_name FROM archived_receipts ORDER BY id")]
    assert names == ["a (2).jpg", "b.jpg"]


def test_ac13_a_failed_move_keeps_the_data_archived(
    open_client: ClientFactory, folders: Settings
) -> None:
    client = open_client(archive_files=FailingMove())
    connection = connect(folders.db_path)
    try:
        seed = Seed(connection, folders)
        seed.receipt("2025-01-01", image="a.jpg")
        seed.receipt("2025-02-01", image="c.jpg")
        (folders.done_dir / "c.jpg").unlink()
        seed.receipt("2025-03-01")

        response = client.post("/api/archive/2025")

        assert response.status_code == 200
        body = response.json()
        assert (body["receipts"], body["images_moved"]) == (3, 0)
        assert body["images_not_moved"] == ["a.jpg", "c.jpg"]
        assert (folders.done_dir / "a.jpg").exists()
        assert count(connection, "archived_receipts") == 3
    finally:
        connection.close()


def test_ac14_a_database_error_moves_no_image(
    api: TestClient, db: sqlite3.Connection, seed: Seed, folders: Settings
) -> None:
    seed.receipt("2025-01-01", image="a.jpg", lines=1)
    db.execute(
        "CREATE TRIGGER fail_archive BEFORE INSERT ON archived_lines"
        " BEGIN SELECT RAISE(ABORT, 'simulated'); END"
    )
    before = snapshot(db)

    response = api.post("/api/archive/2025")

    assert response.status_code == 500
    assert snapshot(db) == before
    assert count(db, "archived_receipts") == 0
    assert (folders.done_dir / "a.jpg").exists()


def test_ac17_overview(api: TestClient, seed: Seed) -> None:
    for index in range(12):
        seed.receipt(
            f"2025-01-{index + 1:02d}",
            image=f"r{index}.jpg" if index < 11 else None,
            lines=12 if index < 8 else 11,
        )
    api.post("/api/archive/2025")
    seed.receipt("2024-01-01", image="x.jpg", lines=10)
    seed.receipt("2024-02-01", image="y.jpg", lines=10, reviewed=False)
    seed.receipt("2024-03-01", image="z.jpg")
    seed.receipt("2026-01-01")

    response = api.get("/api/archive")

    assert response.status_code == 200
    assert response.json() == {
        "archived": [{"year": 2025, "receipts": 12, "lines": 140, "images": 11}],
        "candidates": [{"year": 2024, "receipts": 3, "lines": 20, "images": 3, "unreviewed": 1}],
    }


def test_ac18_permanent_delete_keeps_the_files(
    api: TestClient, db: sqlite3.Connection, seed: Seed, folders: Settings
) -> None:
    seed.receipt("2025-01-01", image="a.jpg", lines=2)
    seed.receipt("2025-02-01", lines=1)
    api.post("/api/archive/2025")

    response = api.delete("/api/archive/2025")

    assert response.status_code == 200
    assert response.json() == {"year": 2025, "receipts": 2, "lines": 3}
    assert count(db, "archived_receipts") == 0
    assert (folders.archive_dir / "a.jpg").exists()


def test_ac20_delete_of_a_year_not_archived(api: TestClient) -> None:
    response = api.delete("/api/archive/2023")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_ac42_the_log_names_no_store_product_or_file(
    api: TestClient, seed: Seed, caplog: pytest.LogCaptureFixture
) -> None:
    seed.receipt("2025-01-01", image="salainen.jpg", lines=1, store="Salakauppa")
    caplog.set_level(logging.DEBUG)

    api.post("/api/archive/2025")
    api.delete("/api/archive/2025")

    text = caplog.text
    assert "Salakauppa" not in text
    assert "MAITO" not in text
    assert "salainen" not in text
    assert "year=2025" in text
