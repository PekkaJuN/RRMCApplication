"""Import runs with the categorization step (categorization spec)."""

import logging
import sqlite3
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.categorization.suggester import CategorySuggester, ModelSuggester
from app.engines.factory import Engines
from app.engines.model import FakeReceiptModel, ModelCheckResult, ModelUnavailableError
from app.engines.ocr import FakeOcrEngine
from app.receipt_import.service import ImportService
from app.receipt_reading.receipt import ReadLine, ReadReceipt
from app.settings import Settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from tests.integration.conftest import make_client
from tests.receipt_import_data import jpeg

type Client = Callable[[ImportService], TestClient]


def line(name: str, amount: int = 100, *, refund: bool = False) -> ReadLine:
    return ReadLine(name, amount, refund)


def receipt(*lines: ReadLine) -> ReadReceipt:
    return ReadReceipt("Testikauppa", date(2026, 10, 29), 1000, lines, "TESTIKAUPPA\n")


MIXED = receipt(line("Ruisleipä", 189), line("Banaani", 99), line("Tomaatti", 250))


class OneReceiptReader:
    def __init__(self, read: ReadReceipt) -> None:
        self._read = read

    def read(self, image: bytes) -> ReadReceipt:
        return self._read


class ScriptedSuggester:
    """Suggests the option named in `answers` per name; runs `after_answer` when asked."""

    def __init__(
        self,
        answers: Mapping[str, str] | None = None,
        after_answer: Callable[[], None] | None = None,
    ) -> None:
        self.answers = answers or {}
        self.after_answer = after_answer
        self.calls: list[list[str]] = []

    def suggest(self, names: Sequence[str], options: Sequence[str]) -> list[int | None]:
        self.calls.append(list(names))
        if self.after_answer is not None:
            self.after_answer()
        return [options.index(self.answers[n]) if n in self.answers else None for n in names]


class AnsweringModel:
    def __init__(self, answer: str = "", error: Exception | None = None) -> None:
        self.answer = answer
        self.error = error

    def check(self) -> ModelCheckResult:
        return "ok"

    def load(self) -> None:
        return None

    def generate(self, prompt: str, schema: dict[str, Any]) -> str:
        if self.error is not None:
            raise self.error
        return self.answer


@pytest.fixture
def folders(settings: Settings) -> Settings:
    for folder in (settings.import_dir, settings.done_dir, settings.failed_dir):
        folder.mkdir()
    return settings


@pytest.fixture
def open_client(folders: Settings) -> Iterator[Client]:
    clients: list[TestClient] = []

    def open_one(service: ImportService) -> TestClient:
        client = make_client(folders, service)
        client.__enter__()
        clients.append(client)
        return client

    yield open_one
    for client in clients:
        client.__exit__(None, None, None)


def service(settings: Settings, read: ReadReceipt, suggester: CategorySuggester) -> ImportService:
    engines = Engines(ocr=FakeOcrEngine(), model=FakeReceiptModel())
    return ImportService(
        settings, engines=engines, reader=OneReceiptReader(read), suggester=suggester
    )


def run_import(client: TestClient) -> dict[str, Any]:
    assert client.post("/api/import").status_code == 202
    for _ in range(500):
        state = client.get("/api/import").json()
        if state["state"] == "finished":
            return state
        threading.Event().wait(0.01)
    raise AssertionError("the run did not finish")


def query(settings: Settings, sql: str) -> list[sqlite3.Row]:
    connection = connect(settings.db_path)
    try:
        return connection.execute(sql).fetchall()
    finally:
        connection.close()


def stored_lines(settings: Settings) -> list[tuple[str, str | None, str | None, str | None]]:
    """(line name, category name, source, product name) in import and printed order."""
    rows = query(
        settings,
        "SELECT l.name, c.name AS category, l.category_source, p.name AS product"
        " FROM receipt_lines l LEFT JOIN categories c ON c.id = l.category_id"
        " LEFT JOIN products p ON p.id = l.product_id ORDER BY l.receipt_id, l.position",
    )
    return [(r["name"], r["category"], r["category_source"], r["product"]) for r in rows]


def category_id(client: TestClient, name: str) -> int:
    return next(item["id"] for item in client.get("/api/categories").json() if item["name"] == name)


def add_product(client: TestClient, name: str, category: str) -> None:
    response = client.post(
        "/api/products", json={"name": name, "category_id": category_id(client, category)}
    )
    assert response.status_code == 201


def put(folder: Path, name: str, data: bytes) -> None:
    (folder / name).write_bytes(data)


def test_ac1_ac2_known_and_unknown_lines(folders: Settings, open_client: Client) -> None:
    suggester = ScriptedSuggester(
        {"Banaani": "Ruoka > Hedelmät", "Tomaatti": "Ruoka > Vihannekset"}
    )
    client = open_client(service(folders, MIXED, suggester))
    add_product(client, "Ruisleipä", "Leivät")
    put(folders.import_dir, "a.jpg", jpeg("a"))

    assert run_import(client)["imported"] == 1

    assert suggester.calls == [["Banaani", "Tomaatti"]]
    assert stored_lines(folders) == [
        ("Ruisleipä", "Leivät", "remembered", "Ruisleipä"),
        ("Banaani", "Hedelmät", "model", None),
        ("Tomaatti", "Vihannekset", "model", None),
    ]
    assert len(client.get("/api/products").json()) == 1


def test_ac5_refund_line_has_no_category(folders: Settings, open_client: Client) -> None:
    suggester = ScriptedSuggester()
    read = receipt(line("Kevytmaito 1L", 129), line("Panttipalautus", -40, refund=True))
    client = open_client(service(folders, read, suggester))
    add_product(client, "Kevytmaito 1L", "Maitotuotteet")
    put(folders.import_dir, "a.jpg", jpeg("a"))

    run_import(client)

    assert stored_lines(folders)[1] == ("Panttipalautus", None, None, None)
    assert suggester.calls == []
    assert [p["name"] for p in client.get("/api/products").json()] == ["Kevytmaito 1L"]


def test_ac7_invalid_answer_imports_without_categories(
    folders: Settings, open_client: Client
) -> None:
    client = open_client(service(folders, MIXED, ModelSuggester(AnsweringModel("no json"))))
    add_product(client, "Ruisleipä", "Leivät")
    put(folders.import_dir, "a.jpg", jpeg("a"))

    state = run_import(client)

    assert (state["imported"], state["failures"]) == (1, [])
    assert (folders.done_dir / "a.jpg").exists()
    assert stored_lines(folders) == [
        ("Ruisleipä", "Leivät", "remembered", "Ruisleipä"),
        ("Banaani", None, None, None),
        ("Tomaatti", None, None, None),
    ]


def test_ac10_model_lost_in_categorization_stops_the_run(
    folders: Settings, open_client: Client
) -> None:
    suggester = ModelSuggester(AnsweringModel(error=ModelUnavailableError("gone")))
    client = open_client(service(folders, MIXED, suggester))
    put(folders.import_dir, "a.jpg", jpeg("a"))
    put(folders.import_dir, "b.jpg", jpeg("b"))

    state = run_import(client)

    assert state["stopped"]["reason"] == "model_unavailable"
    assert sorted(p.name for p in folders.import_dir.iterdir()) == ["a.jpg", "b.jpg"]
    assert query(folders, "SELECT count(*) FROM receipts")[0][0] == 0


def test_ac12_catalog_changed_before_the_commit(folders: Settings, open_client: Client) -> None:
    def user_deletes_category_and_product() -> None:
        connection = connect(folders.db_path)
        try:
            catalog = CatalogRepository(connection)
            with catalog.transaction():
                fruit = catalog.get_category_by_key("hedelmät")
                product = catalog.get_product_by_key("ruisleipä")
                assert fruit is not None
                assert product is not None
                catalog.delete_category(fruit.id)
                catalog.delete_product(product.id)
        finally:
            connection.close()

    suggester = ScriptedSuggester(
        {"Banaani": "Ruoka > Hedelmät"}, after_answer=user_deletes_category_and_product
    )
    read = receipt(line("Banaani", 99), line("Ruisleipä", 189))
    client = open_client(service(folders, read, suggester))
    add_product(client, "Ruisleipä", "Leivät")
    put(folders.import_dir, "a.jpg", jpeg("a"))

    assert run_import(client)["imported"] == 1

    assert stored_lines(folders) == [
        ("Banaani", None, None, None),
        ("Ruisleipä", None, None, None),
    ]


def test_ac21_fake_engines_give_the_first_category(folders: Settings, open_client: Client) -> None:
    client = open_client(ImportService(folders))
    put(folders.import_dir, "a.jpg", jpeg("a"))
    put(folders.import_dir, "b.jpg", jpeg("b"))

    run_import(client)

    assert (
        stored_lines(folders)
        == [
            ("Maito", "Autohuolto", "model", None),
            ("Limu", "Autohuolto", "model", None),
        ]
        * 2
    )


def test_ac23_no_names_in_the_log(
    folders: Settings, open_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    client = open_client(service(folders, MIXED, ModelSuggester(AnsweringModel("no json"))))
    put(folders.import_dir, "a.jpg", jpeg("a"))

    with caplog.at_level(logging.DEBUG):
        run_import(client)

    for text in ("Banaani", "Tomaatti", "Ruisleipä", "Hedelmät", "Vihannekset"):
        assert text not in caplog.text
