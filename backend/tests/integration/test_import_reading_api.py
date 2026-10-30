"""Import runs with the reading step (receipt-reading spec)."""

import io
import logging
import sqlite3
import threading
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.engines.factory import Engines
from app.engines.model import (
    FakeReceiptModel,
    ModelCheckResult,
    ModelTimeoutError,
    ModelUnavailableError,
    ReceiptModel,
)
from app.engines.ocr import FakeOcrEngine, OcrCheckResult, OcrEngine, OcrError
from app.receipt_import.files import image_identifier
from app.receipt_import.service import ImportService
from app.receipt_reading.fake import FAKE_PARSE_FAILED_IMAGE
from app.receipt_reading.reader import OcrReceiptReader
from app.receipt_reading.receipt import ReadFailedError, ReadLine, ReadReceipt
from app.settings import Settings
from app.storage.db import connect
from app.storage.receipt_repository import ReceiptRepository
from tests.integration.conftest import make_client
from tests.receipt_import_data import FailingRepository, FailingStore, jpeg, png

type Client = Callable[[ImportService], TestClient]

AC6_RECEIPT = ReadReceipt(
    store="K-Market Testi",
    purchase_date=date(2026, 10, 5),
    total_cents=349,
    lines=(
        ReadLine("Maito 1l", 125, is_deposit_refund=False),
        ReadLine("Limu 1,5l", 264, is_deposit_refund=False),
        ReadLine("Panttipalautus", -40, is_deposit_refund=True),
    ),
    ocr_text="K-MARKET TESTI\nMAITO 1L 1,25\n",
)


class ScriptedReader:
    """Reads each image as scripted by its bytes; unscripted images give the AC6 receipt."""

    def __init__(self, script: dict[bytes, ReadReceipt | Exception] | None = None) -> None:
        self.script = script or {}
        self.read_images: list[bytes] = []

    def read(self, image: bytes) -> ReadReceipt:
        self.read_images.append(image)
        result = self.script.get(image, AC6_RECEIPT)
        if isinstance(result, Exception):
            raise result
        return result


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


def service(settings: Settings, reader: Any, **options: Any) -> ImportService:
    engines = Engines(ocr=FakeOcrEngine(), model=FakeReceiptModel())
    return ImportService(settings, engines=engines, reader=reader, **options)


def put(folder: Path, name: str, data: bytes) -> None:
    (folder / name).write_bytes(data)


def names(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


def run_import(client: TestClient) -> dict[str, Any]:
    assert client.post("/api/import").status_code == 202
    for _ in range(500):
        state = client.get("/api/import").json()
        if state["state"] == "finished":
            return state
        threading.Event().wait(0.01)
    raise AssertionError("the run did not finish")


def rows(settings: Settings, sql: str) -> list[sqlite3.Row]:
    connection = connect(settings.db_path)
    try:
        return connection.execute(sql).fetchall()
    finally:
        connection.close()


def failures(state: dict[str, Any]) -> list[tuple[str, str]]:
    return [(item["file_name"], item["reason"]) for item in state["failures"]]


def test_ac13_imported_receipt_has_read_data_and_lines(
    folders: Settings, open_client: Client
) -> None:
    # Given the import folder holds a.jpg and the reader returns the AC6 receipt
    put(folders.import_dir, "a.jpg", jpeg("a"))

    # When the run finishes
    state = run_import(open_client(service(folders, ScriptedReader())))

    # Then the receipt row has the read data and three lines reference it
    assert state["imported"] == 1
    [receipt] = rows(folders, "SELECT * FROM receipts")
    assert (receipt["image_hash"], receipt["file_name"]) == (image_identifier(jpeg("a")), "a.jpg")
    assert receipt["store"] == "K-Market Testi"
    assert receipt["purchase_date"] == "2026-10-05"
    assert receipt["total_cents"] == 349
    assert receipt["ocr_text"] == "K-MARKET TESTI\nMAITO 1L 1,25\n"
    lines = rows(
        folders,
        "SELECT receipt_id, position, name, amount_cents, is_deposit_refund"
        " FROM receipt_lines ORDER BY position",
    )
    assert [tuple(line) for line in lines] == [
        (receipt["id"], 1, "Maito 1l", 125, 0),
        (receipt["id"], 2, "Limu 1,5l", 264, 0),
        (receipt["id"], 3, "Panttipalautus", -40, 1),
    ]
    assert names(folders.done_dir) == ["a.jpg"]


def test_ac14_reading_failure_stores_nothing_and_run_goes_on(
    folders: Settings, open_client: Client
) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    put(folders.import_dir, "b.jpg", jpeg("b"))
    reader = ScriptedReader({jpeg("a"): ReadFailedError("parse_failed")})

    state = run_import(open_client(service(folders, reader)))

    assert state["imported"] == 1
    assert state["failures"] == [
        {"file_name": "a.jpg", "reason": "parse_failed", "message": "Kuittia ei voitu tulkita."}
    ]
    assert names(folders.failed_dir) == ["a.jpg"]
    [receipt] = rows(folders, "SELECT id, file_name FROM receipts")
    assert receipt["file_name"] == "b.jpg"
    line_receipts = {row[0] for row in rows(folders, "SELECT receipt_id FROM receipt_lines")}
    assert line_receipts == {receipt["id"]}


def test_ac15_duplicates_are_not_read(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    reader = ScriptedReader()
    client = open_client(service(folders, reader))
    run_import(client)
    put(folders.import_dir, "again.jpg", jpeg("a"))
    reader.read_images.clear()

    state = run_import(client)

    assert state["duplicates"] == ["again.jpg"]
    assert reader.read_images == []


def test_ac11_unreadable_image(folders: Settings, open_client: Client) -> None:
    # A real OCR reader: the bytes have a JPEG signature but are not an image
    put(folders.import_dir, "bad.jpg", jpeg("bad"))
    reader = OcrReceiptReader(ocr=FakeOcrEngine(), model=FakeReceiptModel())

    state = run_import(open_client(service(folders, reader)))

    assert state["failures"] == [
        {"file_name": "bad.jpg", "reason": "unreadable_image", "message": "Kuvaa ei voitu avata."}
    ]
    assert names(folders.failed_dir) == ["bad.jpg"]
    assert rows(folders, "SELECT id FROM receipts") == []


def test_ac12_ocr_failure_and_no_text(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    put(folders.import_dir, "b.jpg", jpeg("b"))
    reader = ScriptedReader(
        {jpeg("a"): ReadFailedError("ocr_failed"), jpeg("b"): ReadFailedError("no_text")}
    )

    state = run_import(open_client(service(folders, reader)))

    assert state["failures"] == [
        {"file_name": "a.jpg", "reason": "ocr_failed", "message": "Tekstin tunnistus epäonnistui."},
        {"file_name": "b.jpg", "reason": "no_text", "message": "Kuvasta ei löytynyt tekstiä."},
    ]
    assert names(folders.failed_dir) == ["a.jpg", "b.jpg"]
    assert rows(folders, "SELECT id FROM receipts") == []


class SlowFirstModel(FakeReceiptModel):
    """Times out on the first receipt and answers the others."""

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, schema: dict[str, Any]) -> str:
        self.calls += 1
        if self.calls == 1:
            raise ModelTimeoutError("slow")
        return super().generate(prompt, schema)


def test_ac11b_model_timeout_fails_only_that_image(folders: Settings, open_client: Client) -> None:
    # Given two readable images; the model gives no answer in time for the first
    put(folders.import_dir, "a.jpg", real_jpeg(100))
    put(folders.import_dir, "b.jpg", real_jpeg(200))
    reader = OcrReceiptReader(ocr=FakeOcrEngine(), model=SlowFirstModel())

    # When the run finishes
    state = run_import(open_client(service(folders, reader)))

    # Then only a.jpg fails, and the run did not stop
    assert failures(state) == [("a.jpg", "parse_failed")]
    assert state["imported"] == 1
    assert state["stopped"] is None
    assert names(folders.failed_dir) == ["a.jpg"]
    assert names(folders.done_dir) == ["b.jpg"]


def test_ac10_date_stored_empty(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    undated = ReadReceipt(
        store="",
        purchase_date=None,
        total_cents=125,
        lines=(ReadLine("Maito", 125, is_deposit_refund=False),),
        ocr_text="MAITO 1,25",
    )

    run_import(open_client(service(folders, ScriptedReader({jpeg("a"): undated}))))

    [receipt] = rows(folders, "SELECT store, purchase_date FROM receipts")
    assert (receipt["store"], receipt["purchase_date"]) == ("", None)


def test_ac16_failed_line_save_rolls_back(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))

    def repository(connection: sqlite3.Connection) -> ReceiptRepository:
        return FailingRepository(connection, line_fails_at=2)

    state = run_import(open_client(service(folders, ScriptedReader(), repository=repository)))

    assert failures(state) == [("a.jpg", "save_failed")]
    assert rows(folders, "SELECT id FROM receipts") == []
    assert rows(folders, "SELECT id FROM receipt_lines") == []
    assert names(folders.failed_dir) == ["a.jpg"]


def test_ac17_failed_move_removes_receipt_and_lines(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    store = FailingStore(move_fails=folders.done_dir)

    state = run_import(open_client(service(folders, ScriptedReader(), store=store)))

    assert failures(state) == [("a.jpg", "move_failed")]
    assert rows(folders, "SELECT id FROM receipts") == []
    assert rows(folders, "SELECT id FROM receipt_lines") == []
    assert names(folders.import_dir) == ["a.jpg"]


class CheckedOcr(FakeOcrEngine):
    def __init__(
        self, result: OcrCheckResult = "ok", on_check: Callable[[], None] | None = None
    ) -> None:
        self.result: OcrCheckResult = result
        self.on_check = on_check

    def check(self) -> OcrCheckResult:
        if self.on_check is not None:
            on_check, self.on_check = self.on_check, None
            on_check()
        return self.result


class CheckedModel(FakeReceiptModel):
    def __init__(self, result: ModelCheckResult = "ok") -> None:
        self.result: ModelCheckResult = result
        self.generated = 0

    def check(self) -> ModelCheckResult:
        return self.result

    def generate(self, prompt: str, schema: dict[str, Any]) -> str:
        self.generated += 1
        return super().generate(prompt, schema)


def checked_service(
    settings: Settings, ocr: OcrEngine | None = None, model: ReceiptModel | None = None
) -> ImportService:
    engines = Engines(ocr=ocr or CheckedOcr(), model=model or CheckedModel())
    return ImportService(settings, engines=engines, reader=ScriptedReader())


@pytest.mark.parametrize("result", ["unavailable", "missing_model"])
def test_ac18_start_refused_when_model_unavailable(
    folders: Settings, open_client: Client, result: ModelCheckResult
) -> None:
    # Given the model check fails and the import folder holds a.jpg
    put(folders.import_dir, "a.jpg", jpeg("a"))
    client = open_client(checked_service(folders, model=CheckedModel(result)))

    # When the user starts an import
    response = client.post("/api/import")

    # Then the start is refused, the file stays and the state is unchanged
    assert response.status_code == 503
    assert response.json() == {
        "error": "model_unavailable",
        "message": "Kielimalli ei ole käytettävissä. Käynnistä Ollama ja tarkista mallin nimi.",
    }
    assert names(folders.import_dir) == ["a.jpg"]
    assert client.get("/api/import").json()["state"] == "idle"


def test_ac19_start_refused_when_ocr_unavailable(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    client = open_client(checked_service(folders, ocr=CheckedOcr("unavailable")))

    response = client.post("/api/import")

    assert response.status_code == 503
    assert response.json() == {
        "error": "ocr_unavailable",
        "message": "Tekstintunnistus ei ole käytettävissä.",
    }
    assert names(folders.import_dir) == ["a.jpg"]
    assert client.get("/api/import").json()["state"] == "idle"


@pytest.mark.parametrize("model_name", ["qwen3:cloud", "gpt-oss:120b-cloud"])
def test_ac21_cloud_model_refused(folders: Settings, open_client: Client, model_name: str) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    cloud = folders.model_copy(update={"model": model_name})
    model = CheckedModel()
    client = open_client(checked_service(cloud, model=model))

    response = client.post("/api/import")

    assert response.status_code == 503
    assert response.json()["error"] == "model_unavailable"
    assert model.generated == 0
    assert names(folders.import_dir) == ["a.jpg"]


def test_folders_are_checked_before_the_engines(folders: Settings, open_client: Client) -> None:
    folders.failed_dir.rmdir()
    client = open_client(checked_service(folders, ocr=CheckedOcr("unavailable")))

    assert client.post("/api/import").json()["error"] == "folders_unavailable"


def test_run_started_during_the_checks_is_refused(folders: Settings, open_client: Client) -> None:
    # Given another start gets in while the first one waits for the engine checks
    put(folders.import_dir, "a.jpg", jpeg("a"))
    inner: list[int] = []
    ocr = CheckedOcr()
    service_under_test = checked_service(folders, ocr=ocr)

    def start_another() -> None:
        service_under_test.start()
        inner.append(1)

    ocr.on_check = start_another
    client = open_client(service_under_test)

    # When the first start continues
    response = client.post("/api/import")

    # Then it is refused because a run is active
    assert inner == [1]
    assert response.status_code == 409
    assert response.json()["error"] == "import_running"


def test_ac20_model_lost_stops_the_run(folders: Settings, open_client: Client) -> None:
    # Given a.jpg is read, and the model cannot be reached for b.jpg
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        put(folders.import_dir, name, jpeg(name))
    reader = ScriptedReader({jpeg("b.jpg"): ModelUnavailableError("refused")})

    # When the run finishes
    state = run_import(open_client(service(folders, reader)))

    # Then the run stopped at b.jpg; b.jpg and c.jpg wait in the import folder
    assert (state["total"], state["processed"], state["imported"]) == (3, 1, 1)
    assert state["failures"] == []
    assert state["stopped"] == {
        "reason": "model_unavailable",
        "message": (
            "Kielimalli ei vastaa. Tuonti pysäytettiin; jäljellä olevat kuvat jäivät"
            " tuontikansioon."
        ),
    }
    assert names(folders.done_dir) == ["a.jpg"]
    assert names(folders.import_dir) == ["b.jpg", "c.jpg"]
    assert names(folders.failed_dir) == []
    assert [row["file_name"] for row in rows(folders, "SELECT file_name FROM receipts")] == [
        "a.jpg"
    ]
    assert reader.read_images == [jpeg("a.jpg"), jpeg("b.jpg")]


def test_stopped_is_null_when_idle_and_after_a_whole_run(
    folders: Settings, open_client: Client
) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    client = open_client(service(folders, ScriptedReader()))

    assert client.get("/api/import").json()["stopped"] is None
    assert run_import(client)["stopped"] is None


def test_ac22_stop_log_line_has_counts_only(
    folders: Settings, open_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    put(folders.import_dir, "NAME-91c2.jpg", jpeg("a"))
    reader = ScriptedReader({jpeg("a"): ModelUnavailableError("refused")})

    with caplog.at_level(logging.DEBUG):
        run_import(open_client(service(folders, reader)))

    assert "Import stopped: model unavailable, imported=0 duplicates=0 failed=0" in caplog.text
    assert "NAME-91c2" not in caplog.text


MARKER = "SECRET-7f3a"


def real_jpeg(height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (100, height), "white").save(buffer, format="JPEG")
    return buffer.getvalue()


class MarkedOcr(FakeOcrEngine):
    """Reads text full of the marker; fails for the image that is three times as tall."""

    def read(self, image: bytes) -> str:
        height = Image.open(io.BytesIO(image)).height
        if height == 4500:
            raise OcrError("exit 1")
        kind = "parse" if height == 3000 else "ok"
        return f"{MARKER} {kind}\nMAITO {MARKER} 1,25\n"


class MarkedModel(FakeReceiptModel):
    def generate(self, prompt: str, schema: dict[str, Any]) -> str:
        if f"{MARKER} parse" in prompt:
            return f"not json {MARKER}"
        return (
            f'{{"s": "{MARKER}", "d": "2026-10-05", "t": 125,'
            f' "l": [{{"n": "Maito {MARKER}", "a": 125, "r": false}}]}}'
        )


def test_ac22_no_receipt_content_in_the_log(
    folders: Settings, open_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    # Given one image that is read, one the model cannot parse and one OCR cannot read, with
    # the marker in their text, answers and names, and another marker in the file names
    put(folders.import_dir, "NAME-91c2-a.jpg", real_jpeg(100))
    put(folders.import_dir, "NAME-91c2-b.jpg", real_jpeg(200))
    put(folders.import_dir, "NAME-91c2-c.jpg", real_jpeg(300))
    reader = OcrReceiptReader(ocr=MarkedOcr(), model=MarkedModel())

    # When the run finishes, logging everything
    with caplog.at_level(logging.DEBUG):
        state = run_import(open_client(service(folders, reader)))

    # Then the outcomes are as planned and the log holds neither marker
    assert state["imported"] == 1
    assert failures(state) == [
        ("NAME-91c2-b.jpg", "parse_failed"),
        ("NAME-91c2-c.jpg", "ocr_failed"),
    ]
    [receipt] = rows(folders, "SELECT store FROM receipts")
    assert receipt["store"] == MARKER
    assert MARKER not in caplog.text
    assert "NAME-91c2" not in caplog.text


def test_ac24_fake_engines_store_the_fixed_receipt_twice(
    folders: Settings, open_client: Client
) -> None:
    # Given RRMC_ENGINES=fake and two different images
    client = open_client(ImportService(folders))
    stored: list[list[tuple[Any, ...]]] = []
    for _ in range(2):
        put(folders.import_dir, "a.jpg", jpeg("a"))
        put(folders.import_dir, "b.png", png("b"))

        # When the run finishes
        assert run_import(client)["imported"] == 2
        receipts = rows(
            folders, "SELECT store, purchase_date, total_cents, ocr_text, id FROM receipts"
        )
        lines = rows(folders, "SELECT receipt_id, position, name, amount_cents FROM receipt_lines")
        stored.append([tuple(row)[:4] for row in receipts])
        assert sorted((row[0], row[1], row[2], row[3]) for row in lines) == [
            (receipt["id"], position, name, amount)
            for receipt in receipts
            for position, name, amount in ((1, "Maito", 125), (2, "Limu", 224))
        ]
        # The files and rows go away again, so the second run imports the same images anew.
        for path in folders.done_dir.iterdir():
            path.unlink()
        connection = connect(folders.db_path)
        with connection:
            connection.execute("DELETE FROM receipts")
        connection.close()

    # Then both runs store the fake receipt for each image
    expected = (
        "Testikauppa",
        "2026-10-05",
        349,
        "TESTIKAUPPA\nMAITO 1,25\nLIMU 2,24\nYHTEENSÄ 3,49",
    )
    assert stored == [[expected, expected], [expected, expected]]


def test_ac24b_fake_parse_failed_image(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "parse-failed.png", FAKE_PARSE_FAILED_IMAGE)

    state = run_import(open_client(ImportService(folders)))

    assert failures(state) == [("parse-failed.png", "parse_failed")]
    assert names(folders.failed_dir) == ["parse-failed.png"]
    assert rows(folders, "SELECT id FROM receipts") == []
