import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.receipt_import.errors import FoldersUnavailableError, ImportRunningError
from app.receipt_import.files import LocalFileStore
from app.receipt_import.schemas import FailureOut, ImportStateOut
from app.receipt_import.service import ImportService, RunHooks
from app.settings import Settings
from app.storage.migrate import migrate_database
from tests.receipt_import_data import jpeg

START = datetime(2026, 10, 28, 10, 0, 0, tzinfo=UTC)
IDLE = ImportStateOut(
    state="idle",
    total=0,
    processed=0,
    imported=0,
    duplicates=[],
    failures=[],
    started_at=None,
    finished_at=None,
)


@pytest.fixture
def settings(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    settings = Settings(engines="fake", data_dir=tmp_path)
    for folder in (settings.import_dir, settings.done_dir, settings.failed_dir):
        folder.mkdir()
    settings.db_path.parent.mkdir()
    migrate_database(settings.db_path)
    return settings


def run_now(work: Callable[[], None]) -> None:
    work()


def make_service(
    settings: Settings,
    *,
    run_in_background: Callable[[Callable[[], None]], None] = run_now,
    can_write: Callable[[Path], bool] = lambda path: True,
    hooks: RunHooks | None = None,
) -> ImportService:
    return ImportService(
        settings,
        clock=lambda: START,
        can_write=can_write,
        hooks=hooks or RunHooks(),
        run_in_background=run_in_background,
    )


def test_ac22_state_is_idle_before_the_first_run(settings: Settings) -> None:
    assert make_service(settings).state() == IDLE


def test_ac19_start_returns_running_state_at_once(settings: Settings) -> None:
    (settings.import_dir / "a.jpg").write_bytes(jpeg("a"))
    pending: list[Callable[[], None]] = []
    service = make_service(settings, run_in_background=pending.append)

    state = service.start()

    assert state == IDLE.model_copy(
        update={"state": "running", "total": 1, "started_at": "2026-10-28T10:00:00Z"}
    )
    assert service.state() == state
    assert len(pending) == 1


def test_ac20_second_start_while_running_is_refused(settings: Settings) -> None:
    (settings.import_dir / "a.jpg").write_bytes(jpeg("a"))
    pending: list[Callable[[], None]] = []
    service = make_service(settings, run_in_background=pending.append)
    running = service.start()

    with pytest.raises(ImportRunningError):
        service.start()

    assert service.state() == running
    assert len(pending) == 1


@pytest.mark.parametrize("folder", ["import", "import_done", "import_failed"])
def test_ac21_missing_folder_refuses_the_start(settings: Settings, folder: str) -> None:
    (settings.data_dir / folder).rmdir()
    service = make_service(settings)

    with pytest.raises(FoldersUnavailableError):
        service.start()

    assert service.state() == IDLE


@pytest.mark.parametrize("folder", ["import", "import_done", "import_failed"])
def test_ac21_folder_that_cannot_be_written_refuses_the_start(
    settings: Settings, folder: str
) -> None:
    service = make_service(settings, can_write=lambda path: path.name != folder)

    with pytest.raises(FoldersUnavailableError):
        service.start()

    assert service.state() == IDLE


def test_ac9_empty_folder_finishes_with_zeros(settings: Settings) -> None:
    service = make_service(settings)

    service.start()

    assert service.state() == IDLE.model_copy(
        update={
            "state": "finished",
            "started_at": "2026-10-28T10:00:00Z",
            "finished_at": "2026-10-28T10:00:00Z",
        }
    )


def test_ac1_ac4_ac6_finished_run_reports_every_file(settings: Settings) -> None:
    (settings.import_dir / "a.jpg").write_bytes(jpeg("a"))
    (settings.import_dir / "b.jpg").write_bytes(jpeg("a"))
    (settings.import_dir / "notes.txt").write_bytes(b"hello")
    service = make_service(settings)

    service.start()

    assert service.state() == ImportStateOut(
        state="finished",
        total=3,
        processed=3,
        imported=1,
        duplicates=["b.jpg"],
        failures=[
            FailureOut(
                file_name="notes.txt",
                reason="unsupported_format",
                message="Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa.",
            )
        ],
        started_at="2026-10-28T10:00:00Z",
        finished_at="2026-10-28T10:00:00Z",
    )


def test_ac20_a_new_run_can_start_after_a_finished_one(settings: Settings) -> None:
    service = make_service(settings)
    service.start()
    (settings.import_dir / "a.jpg").write_bytes(jpeg("a"))

    service.start()

    assert service.state().imported == 1
    assert service.state().total == 1


def wait_until_finished(service: ImportService) -> ImportStateOut:
    for _ in range(500):
        state = service.state()
        if state.state == "finished":
            return state
        threading.Event().wait(0.01)
    raise AssertionError("the run did not finish")


def test_ac18_progress_while_the_run_is_paused(settings: Settings) -> None:
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        (settings.import_dir / name).write_bytes(jpeg(name))
    paused, resume = threading.Event(), threading.Event()

    def pause_after_first(file_name: str) -> None:
        if file_name == "a.jpg":
            paused.set()
            resume.wait(5)

    service = ImportService(
        settings, clock=lambda: START, hooks=RunHooks(after_file=pause_after_first)
    )
    service.start()
    assert paused.wait(5)

    state = service.state()
    resume.set()

    assert (state.state, state.total, state.processed, state.imported) == ("running", 3, 1, 1)
    assert state.finished_at is None
    assert wait_until_finished(service).imported == 3


def test_ac23_file_added_after_listing_is_left_for_the_next_run(settings: Settings) -> None:
    (settings.import_dir / "a.jpg").write_bytes(jpeg("a"))

    def add_file() -> None:
        (settings.import_dir / "b.jpg").write_bytes(jpeg("b"))

    service = make_service(settings, hooks=RunHooks(after_listing=add_file))

    service.start()

    state = service.state()
    assert (state.total, state.imported) == (1, 1)
    assert [path.name for path in settings.import_dir.iterdir()] == ["b.jpg"]


def test_ac17_run_without_database_fails_every_file_and_moves_none(settings: Settings) -> None:
    (settings.import_dir / "a.jpg").write_bytes(jpeg("a"))
    (settings.import_dir / "b.jpg").write_bytes(jpeg("b"))
    broken = Settings(engines="fake", data_dir=settings.data_dir)
    for path in broken.db_path.parent.iterdir():
        path.unlink()
    broken.db_path.parent.rmdir()

    service = make_service(broken)
    service.start()

    state = service.state()
    assert state.state == "finished"
    assert [(item.file_name, item.reason) for item in state.failures] == [
        ("a.jpg", "internal_error"),
        ("b.jpg", "internal_error"),
    ]
    assert sorted(path.name for path in settings.import_dir.iterdir()) == ["a.jpg", "b.jpg"]


def test_ac25_log_has_one_start_and_one_finish_line_without_names(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.receipt_import")
    (settings.import_dir / "secret-name.jpg").write_bytes(jpeg("secret"))
    (settings.import_dir / "other-secret.txt").write_bytes(b"secret content")

    make_service(settings).start()

    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "Import started: files=2",
        "Import finished: imported=1 duplicates=0 failed=1",
    ]
    assert "secret" not in caplog.text


class UnlistableStore(LocalFileStore):
    def list_files(self, folder: Path) -> list[Path]:
        raise PermissionError("simulated")


def test_ac21_import_folder_that_cannot_be_listed_refuses_the_start(settings: Settings) -> None:
    service = ImportService(settings, store=UnlistableStore())

    with pytest.raises(FoldersUnavailableError):
        service.start()

    assert service.state() == IDLE
