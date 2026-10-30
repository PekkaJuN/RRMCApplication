"""Import runs: start checks, the run in the background, and its state in memory."""

import logging
import os
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app import texts
from app.engines.factory import Engines, create_engines
from app.engines.model import ModelUnavailableError, is_cloud_model
from app.health.service import CanWrite, RunInBackground, check_folders
from app.receipt_import.errors import (
    FoldersUnavailableError,
    ImportRunningError,
    ModelNotReadyError,
    OcrNotReadyError,
)
from app.receipt_import.files import FileStore, LocalFileStore
from app.receipt_import.run import (
    FailureReason,
    FileResult,
    ImportFolders,
    log_without_message,
    process_file,
    utc_text,
)
from app.receipt_import.schemas import FailureOut, ImportStateOut, StoppedOut
from app.receipt_reading.factory import create_reader
from app.receipt_reading.reader import ReceiptReader
from app.settings import Settings
from app.storage.db import connect
from app.storage.receipt_repository import ReceiptRepository

logger = logging.getLogger(__name__)

_FAILURE_MESSAGES: dict[FailureReason, str] = {
    "unsupported_format": texts.UNSUPPORTED_FORMAT,
    "read_failed": texts.READ_FAILED,
    "unreadable_image": texts.UNREADABLE_IMAGE,
    "ocr_failed": texts.OCR_FAILED,
    "no_text": texts.NO_TEXT,
    "parse_failed": texts.PARSE_FAILED,
    "save_failed": texts.SAVE_FAILED,
    "move_failed": texts.MOVE_FAILED,
    "internal_error": texts.INTERNAL_ERROR,
}


def _nothing() -> None:
    pass


def _nothing_for(file_name: str) -> None:
    pass


@dataclass(frozen=True)
class RunHooks:
    """Points where tests pause a run. Production code leaves them empty."""

    after_listing: Callable[[], None] = _nothing
    after_file: Callable[[str], None] = _nothing_for


def _can_write(path: Path) -> bool:
    return os.access(path, os.W_OK)


def _run_in_thread(work: Callable[[], None]) -> None:
    threading.Thread(target=work, name="import-run", daemon=True).start()


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class _RunState:
    state: str = "idle"
    total: int = 0
    imported: int = 0
    duplicates: list[str] = field(default_factory=list[str])
    failures: list[FailureOut] = field(default_factory=list[FailureOut])
    started_at: str | None = None
    finished_at: str | None = None
    stopped: StoppedOut | None = None


class ImportService:
    """Runs one import at a time in the background (FR-45, PC8 of the receipt-import spec).

    The state is kept in memory only; after a restart it is `idle`.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        engines: Engines | None = None,
        reader: ReceiptReader | None = None,
        store: FileStore | None = None,
        repository: Callable[[sqlite3.Connection], ReceiptRepository] = ReceiptRepository,
        can_write: CanWrite = _can_write,
        clock: Callable[[], datetime] = _utc_now,
        hooks: RunHooks | None = None,
        run_in_background: RunInBackground = _run_in_thread,
    ) -> None:
        self._settings = settings
        self._engines = engines or create_engines(settings)
        self._reader = reader or create_reader(settings, self._engines)
        self._folders = ImportFolders(settings.import_dir, settings.done_dir, settings.failed_dir)
        self._store = store or LocalFileStore()
        self._repository = repository
        self._can_write = can_write
        self._clock = clock
        self._hooks = hooks or RunHooks()
        self._run_in_background = run_in_background
        self._lock = threading.Lock()
        self._state = _RunState()

    def state(self) -> ImportStateOut:
        with self._lock:
            return self._snapshot()

    def start(self) -> ImportStateOut:
        """Start a run of the files now in the import folder and return its first state.

        Raises:
            ImportRunningError: a run is active.
            FoldersUnavailableError: a folder is missing, cannot be written to or listed.
            OcrNotReadyError: Tesseract cannot run.
            ModelNotReadyError: the model cannot be used, or it is a cloud model (FR-31).
        """
        folders = self._folders
        with self._lock:
            self._refuse_if_running()
            all_folders = [folders.import_dir, folders.done_dir, folders.failed_dir]
            if check_folders(all_folders, self._can_write) != "ok":
                raise FoldersUnavailableError()
        # Outside the lock: the checks can take seconds, and GET /api/import must not wait.
        self._check_engines()
        with self._lock:
            # Another start may have got in during the checks.
            self._refuse_if_running()
            try:
                files = self._store.list_files(folders.import_dir)
            except OSError:
                raise FoldersUnavailableError() from None
            self._state = _RunState(
                state="running", total=len(files), started_at=utc_text(self._clock())
            )
            snapshot = self._snapshot()
        logger.info("Import started: files=%d", len(files))
        self._run_in_background(lambda: self._run(files))
        return snapshot

    def _refuse_if_running(self) -> None:
        if self._state.state == "running":
            raise ImportRunningError()

    def _check_engines(self) -> None:
        if self._engines.ocr.check() != "ok":
            raise OcrNotReadyError()
        # A cloud model would send the receipt off this computer (NFR-1).
        if is_cloud_model(self._settings.model) or self._engines.model.check() != "ok":
            raise ModelNotReadyError()

    def _run(self, files: list[Path]) -> None:
        remaining = list(files)
        try:
            connection = connect(self._settings.db_path)
            try:
                repository = self._repository(connection)
                self._hooks.after_listing()
                while remaining:
                    path = remaining.pop(0)
                    result = process_file(
                        path,
                        store=self._store,
                        repository=repository,
                        reader=self._reader,
                        folders=self._folders,
                        now=self._clock(),
                    )
                    self._record(result)
                    self._hooks.after_file(path.name)
            finally:
                connection.close()
        except ModelUnavailableError:
            # FR-31: the current file and the ones after it wait in the import folder; none
            # of them failed.
            with self._lock:
                self._state.stopped = StoppedOut(
                    reason="model_unavailable", message=texts.MODEL_LOST
                )
        except Exception as error:
            # The files left are not moved; they stay in the import folder for the next run.
            log_without_message("Import run stopped", error)
            for path in remaining:
                self._record(FileResult(path.name, "failed", "internal_error"))
        self._finish()

    def _record(self, result: FileResult) -> None:
        with self._lock:
            if result.outcome == "imported":
                self._state.imported += 1
            elif result.outcome == "duplicate":
                self._state.duplicates.append(result.file_name)
            else:
                assert result.reason is not None  # noqa: S101 - every failure has a reason
                message = _FAILURE_MESSAGES[result.reason]
                self._state.failures.append(
                    FailureOut(file_name=result.file_name, reason=result.reason, message=message)
                )

    def _finish(self) -> None:
        with self._lock:
            state = self._state
            state.state = "finished"
            state.finished_at = utc_text(self._clock())
        text = "Import stopped: model unavailable," if state.stopped else "Import finished:"
        logger.info(
            "%s imported=%d duplicates=%d failed=%d",
            text,
            state.imported,
            len(state.duplicates),
            len(state.failures),
        )

    def _snapshot(self) -> ImportStateOut:
        state = self._state
        return ImportStateOut.model_validate(
            {
                "state": state.state,
                "total": state.total,
                "processed": state.imported + len(state.duplicates) + len(state.failures),
                "imported": state.imported,
                "duplicates": list(state.duplicates),
                "failures": list(state.failures),
                "started_at": state.started_at,
                "finished_at": state.finished_at,
                "stopped": state.stopped,
            }
        )
