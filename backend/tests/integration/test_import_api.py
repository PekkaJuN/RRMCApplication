import logging
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.receipt_import.files import LocalFileStore, image_identifier
from app.receipt_import.service import ImportService, RunHooks
from app.settings import Settings
from app.storage.db import connect
from tests.integration.conftest import make_client
from tests.receipt_import_data import FailingRepository, FailingStore, jpeg, png

type Client = Callable[..., TestClient]


@pytest.fixture
def folders(settings: Settings) -> Settings:
    for folder in (settings.import_dir, settings.done_dir, settings.failed_dir):
        folder.mkdir()
    return settings


@pytest.fixture
def open_client(folders: Settings) -> Iterator[Client]:
    """Opens clients whose app has run its startup; closes them at the end of the test."""
    clients: list[TestClient] = []

    def open_one(service: ImportService | None = None) -> TestClient:
        client = make_client(folders, service)
        client.__enter__()
        clients.append(client)
        return client

    yield open_one
    for client in clients:
        client.__exit__(None, None, None)


def put(folder: Path, name: str, data: bytes) -> None:
    (folder / name).write_bytes(data)


def names(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


def finished(client: TestClient) -> dict[str, Any]:
    """Poll the state until the run has finished (5 s limit)."""
    for _ in range(500):
        state = client.get("/api/import").json()
        if state["state"] == "finished":
            return state
        threading.Event().wait(0.01)
    raise AssertionError("the run did not finish")


def run_import(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/import")
    assert response.status_code == 202
    return finished(client)


def receipts(settings: Settings) -> list[tuple[str, str]]:
    connection = connect(settings.db_path)
    try:
        rows = connection.execute("SELECT image_hash, file_name FROM receipts ORDER BY id")
        return [(row["image_hash"], row["file_name"]) for row in rows]
    finally:
        connection.close()


def failure(name: str, reason: str) -> tuple[str, str]:
    return (name, reason)


def failures(state: dict[str, Any]) -> list[tuple[str, str]]:
    return [(item["file_name"], item["reason"]) for item in state["failures"]]


class Pause:
    """Hooks that stop a run at one point until `resume()`."""

    def __init__(self) -> None:
        self.reached = threading.Event()
        self._resume = threading.Event()

    def __call__(self, *args: object) -> None:
        self.reached.set()
        assert self._resume.wait(5)

    def resume(self) -> None:
        self._resume.set()


def test_ac22_idle_before_the_first_run(open_client: Client) -> None:
    response = open_client().get("/api/import")

    assert response.status_code == 200
    assert response.json() == {
        "state": "idle",
        "total": 0,
        "processed": 0,
        "imported": 0,
        "duplicates": [],
        "failures": [],
        "started_at": None,
        "finished_at": None,
    }


def test_ac19_start_returns_202_at_once(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    pause = Pause()
    client = open_client(ImportService(folders, hooks=RunHooks(after_listing=pause)))

    response = client.post("/api/import")
    pause.resume()

    assert response.status_code == 202
    body = response.json()
    assert (body["state"], body["total"], body["processed"]) == ("running", 1, 0)
    assert body["started_at"] is not None
    assert body["finished_at"] is None
    assert finished(client)["imported"] == 1


def test_ac1_new_jpeg_is_imported(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))

    state = run_import(open_client())

    assert (state["total"], state["processed"], state["imported"]) == (1, 1, 1)
    assert (state["duplicates"], state["failures"]) == ([], [])
    assert receipts(folders) == [(image_identifier(jpeg("a")), "a.jpg")]
    connection = connect(folders.db_path)
    imported_at = connection.execute("SELECT imported_at FROM receipts").fetchone()[0]
    connection.close()
    assert state["started_at"] <= imported_at <= state["finished_at"]
    assert (folders.done_dir / "a.jpg").read_bytes() == jpeg("a")
    assert names(folders.import_dir) == []


def test_ac2_ac3_extensions_in_any_case_in_name_order(
    folders: Settings, open_client: Client
) -> None:
    put(folders.import_dir, "d.JPG", jpeg("d"))
    put(folders.import_dir, "c.jpeg", jpeg("c"))
    put(folders.import_dir, "B.PNG", png("b"))
    put(folders.import_dir, "A.jpg", jpeg("a"))

    state = run_import(open_client())

    assert state["imported"] == 4
    assert [name for _, name in receipts(folders)] == ["A.jpg", "B.PNG", "c.jpeg", "d.JPG"]
    assert names(folders.done_dir) == ["A.jpg", "B.PNG", "c.jpeg", "d.JPG"]


def test_ac4_image_imported_before_is_a_duplicate(folders: Settings, open_client: Client) -> None:
    client = open_client()
    put(folders.import_dir, "a.jpg", jpeg("a"))
    run_import(client)
    put(folders.import_dir, "again.jpg", jpeg("a"))

    state = run_import(client)

    assert (state["imported"], state["duplicates"], state["failures"]) == (0, ["again.jpg"], [])
    assert len(receipts(folders)) == 1
    assert (folders.import_dir / "again.jpg").read_bytes() == jpeg("a")


def test_ac5_identical_files_in_one_run(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("same"))
    put(folders.import_dir, "b.jpg", jpeg("same"))

    state = run_import(open_client())

    assert (state["imported"], state["duplicates"]) == (1, ["b.jpg"])
    assert [name for _, name in receipts(folders)] == ["a.jpg"]
    assert names(folders.done_dir) == ["a.jpg"]
    assert names(folders.import_dir) == ["b.jpg"]


def test_ac6_ac7_unsupported_files_move_to_failed_folder(
    folders: Settings, open_client: Client
) -> None:
    put(folders.import_dir, "notes.txt", b"hello")
    put(folders.import_dir, "photo.heic", b"heic")
    put(folders.import_dir, "text.jpg", b"hello")
    put(folders.import_dir, "empty.png", b"")
    put(folders.import_dir, "png-as.jpg", png("p"))

    state = run_import(open_client())

    assert state["imported"] == 0
    assert failures(state) == [
        failure("empty.png", "unsupported_format"),
        failure("notes.txt", "unsupported_format"),
        failure("photo.heic", "unsupported_format"),
        failure("png-as.jpg", "unsupported_format"),
        failure("text.jpg", "unsupported_format"),
    ]
    assert {item["message"] for item in state["failures"]} == {
        "Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa."
    }
    assert names(folders.failed_dir) == [
        "empty.png",
        "notes.txt",
        "photo.heic",
        "png-as.jpg",
        "text.jpg",
    ]
    assert receipts(folders) == []


def test_ac8_ignored_entries_are_not_counted_or_moved(
    folders: Settings, open_client: Client
) -> None:
    (folders.import_dir / "vanhat").mkdir()
    put(folders.import_dir / "vanhat", "x.jpg", jpeg("x"))
    put(folders.import_dir, ".hidden.jpg", jpeg("h"))
    put(folders.import_dir, "desktop.ini", b"[x]")
    put(folders.import_dir, "THUMBS.DB", b"db")

    state = run_import(open_client())

    assert state["total"] == 0
    assert names(folders.import_dir) == [".hidden.jpg", "THUMBS.DB", "desktop.ini", "vanhat"]
    assert names(folders.import_dir / "vanhat") == ["x.jpg"]


def test_ac9_empty_import_folder(open_client: Client) -> None:
    state = run_import(open_client())

    assert (state["total"], state["processed"], state["imported"]) == (0, 0, 0)
    assert (state["duplicates"], state["failures"]) == ([], [])
    assert state["finished_at"] is not None


def test_ac10_name_collision_in_done_folder(folders: Settings, open_client: Client) -> None:
    put(folders.done_dir, "kuitti.jpg", jpeg("old 1"))
    put(folders.done_dir, "KUITTI (2).jpg", jpeg("old 2"))
    put(folders.import_dir, "kuitti.jpg", jpeg("new"))

    run_import(open_client())

    assert (folders.done_dir / "kuitti (3).jpg").read_bytes() == jpeg("new")
    assert (folders.done_dir / "kuitti.jpg").read_bytes() == jpeg("old 1")
    assert (folders.done_dir / "KUITTI (2).jpg").read_bytes() == jpeg("old 2")
    assert [name for _, name in receipts(folders)] == ["kuitti (3).jpg"]


def test_ac11_name_collision_in_failed_folder(folders: Settings, open_client: Client) -> None:
    put(folders.failed_dir, "notes.txt", b"old")
    put(folders.import_dir, "notes.txt", b"new")

    state = run_import(open_client())

    assert failures(state) == [failure("notes.txt", "unsupported_format")]
    assert (folders.failed_dir / "notes.txt").read_bytes() == b"old"
    assert (folders.failed_dir / "notes (2).txt").read_bytes() == b"new"


class SwitchableStore(LocalFileStore):
    """Moving into `done_dir` fails while `failing` is true."""

    def __init__(self, done_dir: Path) -> None:
        self.failing = True
        self._done_dir = done_dir

    def move(self, source: Path, target: Path) -> None:
        if self.failing and target.parent == self._done_dir:
            raise OSError("simulated")
        super().move(source, target)


def test_ac12_ac13_failed_move_then_retry(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    store = SwitchableStore(folders.done_dir)
    client = open_client(ImportService(folders, store=store))

    first = run_import(client)

    assert first["imported"] == 0
    assert first["failures"] == [
        {
            "file_name": "a.jpg",
            "reason": "move_failed",
            "message": "Tiedostoa ei voitu siirtää valmiiden kansioon.",
        }
    ]
    assert receipts(folders) == []
    assert names(folders.import_dir) == ["a.jpg"]

    store.failing = False
    second = run_import(client)

    assert (second["imported"], second["duplicates"]) == (1, [])
    assert names(folders.done_dir) == ["a.jpg"]


def test_ac14_failed_save(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    service = ImportService(
        folders, repository=lambda connection: FailingRepository(connection, add_fails=True)
    )

    state = run_import(open_client(service))

    assert failures(state) == [failure("a.jpg", "save_failed")]
    assert state["failures"][0]["message"] == "Kuitin tallennus epäonnistui."
    assert receipts(folders) == []
    assert names(folders.failed_dir) == ["a.jpg"]


def test_ac15_one_failure_does_not_stop_the_run(folders: Settings, open_client: Client) -> None:
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        put(folders.import_dir, name, jpeg(name))
    service = ImportService(folders, store=FailingStore(read_fails="b.jpg"))

    state = run_import(open_client(service))

    assert state["imported"] == 2
    assert failures(state) == [failure("b.jpg", "read_failed")]
    assert state["failures"][0]["message"] == "Tiedostoa ei voitu lukea."
    assert names(folders.failed_dir) == ["b.jpg"]


def test_ac16_file_stays_when_failed_folder_move_fails(
    folders: Settings, open_client: Client
) -> None:
    put(folders.import_dir, "notes.txt", b"hello")
    service = ImportService(folders, store=FailingStore(move_fails=folders.failed_dir))

    state = run_import(open_client(service))

    assert failures(state) == [failure("notes.txt", "unsupported_format")]
    assert names(folders.import_dir) == ["notes.txt"]


def test_ac17_unexpected_error(
    folders: Settings, open_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    put(folders.import_dir, "b.jpg", jpeg("b"))
    store = FailingStore(read_fails="a.jpg", error=RuntimeError("/data/import/a.jpg"))

    state = run_import(open_client(ImportService(folders, store=store)))

    assert failures(state) == [failure("a.jpg", "internal_error")]
    assert state["imported"] == 1
    assert names(folders.failed_dir) == ["a.jpg"]
    assert names(folders.done_dir) == ["b.jpg"]
    assert "RuntimeError" in caplog.text
    assert "a.jpg" not in caplog.text
    assert "b.jpg" not in caplog.text


def test_ac18_progress_while_running(folders: Settings, open_client: Client) -> None:
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        put(folders.import_dir, name, jpeg(name))
    pause = Pause()

    def after_file(file_name: str) -> None:
        if file_name == "a.jpg":
            pause()

    client = open_client(ImportService(folders, hooks=RunHooks(after_file=after_file)))
    client.post("/api/import")
    assert pause.reached.wait(5)

    response = client.get("/api/import")
    pause.resume()

    assert response.status_code == 200
    body = response.json()
    assert (body["state"], body["total"], body["processed"], body["imported"]) == (
        "running",
        3,
        1,
        1,
    )
    assert body["finished_at"] is None
    assert finished(client)["imported"] == 3


def test_ac20_second_start_while_running(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    pause = Pause()
    client = open_client(ImportService(folders, hooks=RunHooks(after_listing=pause)))
    client.post("/api/import")
    assert pause.reached.wait(5)

    response = client.post("/api/import")
    pause.resume()

    assert response.status_code == 409
    assert response.json() == {"error": "import_running", "message": "Tuonti on jo käynnissä."}
    state = finished(client)
    assert (state["total"], state["imported"]) == (1, 1)


def test_ac21_missing_folder(folders: Settings, open_client: Client) -> None:
    client = open_client()
    put(folders.import_dir, "a.jpg", jpeg("a"))
    folders.done_dir.rmdir()
    before = client.get("/api/import").json()

    response = client.post("/api/import")

    assert response.status_code == 503
    assert response.json() == {
        "error": "folders_unavailable",
        "message": "Kuvakansioita ei löydy tai niihin ei voi kirjoittaa.",
    }
    assert names(folders.import_dir) == ["a.jpg"]
    assert client.get("/api/import").json() == before


def test_ac23_file_added_during_a_run(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    pause = Pause()
    client = open_client(ImportService(folders, hooks=RunHooks(after_listing=pause)))
    client.post("/api/import")
    assert pause.reached.wait(5)

    put(folders.import_dir, "b.jpg", jpeg("b"))
    pause.resume()
    state = finished(client)

    assert (state["total"], state["imported"]) == (1, 1)
    assert names(folders.import_dir) == ["b.jpg"]


def test_ac24_receipts_survive_a_restart(folders: Settings, open_client: Client) -> None:
    put(folders.import_dir, "a.jpg", jpeg("a"))
    run_import(open_client())
    put(folders.import_dir, "copy.jpg", jpeg("a"))

    state = run_import(open_client())

    assert state["duplicates"] == ["copy.jpg"]


def test_ac25_log_has_counts_only(
    folders: Settings, open_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    put(folders.import_dir, "secret-name.jpg", jpeg("secret bytes"))
    put(folders.import_dir, "other-secret.txt", b"secret text")

    run_import(open_client())

    import_lines = [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("app.receipt_import")
    ]
    assert import_lines == [
        "Import started: files=2",
        "Import finished: imported=1 duplicates=0 failed=1",
    ]
    assert "secret" not in caplog.text
