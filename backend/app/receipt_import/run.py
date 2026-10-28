"""The steps that import one file."""

import logging
import sqlite3
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.receipt_import.files import FileStore, check_format, free_target_name, image_identifier
from app.storage.receipt_repository import ReceiptRepository

logger = logging.getLogger(__name__)

type Outcome = Literal["imported", "duplicate", "failed"]
type FailureReason = Literal[
    "unsupported_format", "read_failed", "save_failed", "move_failed", "internal_error"
]


@dataclass(frozen=True)
class ImportFolders:
    import_dir: Path
    done_dir: Path
    failed_dir: Path


@dataclass(frozen=True)
class FileResult:
    """What happened to one file. `file_name` is the name it had in the import folder."""

    file_name: str
    outcome: Outcome
    reason: FailureReason | None = None


class _FileFailedError(Exception):
    def __init__(self, reason: FailureReason, *, move_to_failed: bool = True) -> None:
        super().__init__(reason)
        self.reason: FailureReason = reason
        self.move_to_failed = move_to_failed


def utc_text(moment: datetime) -> str:
    """A time as UTC ISO 8601 with seconds, e.g. 2026-10-28T10:00:01Z."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_without_message(text: str, error: BaseException) -> None:
    """Log the error's type and traceback frames, but not its message: messages of `OSError`
    and others contain the file path, and file names stay out of the log (NFR-3)."""
    frames = "".join(traceback.format_tb(error.__traceback__))
    logger.error("%s: %s\n%s", text, type(error).__name__, frames)


def process_file(
    path: Path,
    *,
    store: FileStore,
    repository: ReceiptRepository,
    folders: ImportFolders,
    now: datetime,
) -> FileResult:
    """Import one file: store a new receipt, then move the file to the done folder.

    A failed file stores nothing and moves to the failed folder, except when the done folder
    cannot be used: then it stays in the import folder for a later run.
    """
    try:
        return _import(path, store, repository, folders, now)
    except _FileFailedError as failure:
        reason, move_to_failed = failure.reason, failure.move_to_failed
    except Exception as error:
        log_without_message("Unexpected error while importing a file", error)
        reason, move_to_failed = "internal_error", True
    if move_to_failed:
        _move_to_failed(path, store, folders.failed_dir)
    return FileResult(path.name, "failed", reason)


def _import(
    path: Path,
    store: FileStore,
    repository: ReceiptRepository,
    folders: ImportFolders,
    now: datetime,
) -> FileResult:
    try:
        data = store.read_bytes(path)
    except OSError:
        raise _FileFailedError("read_failed") from None
    if not check_format(path.name, data):
        raise _FileFailedError("unsupported_format")
    image_hash = image_identifier(data)
    if repository.get_by_hash(image_hash) is not None:
        return FileResult(path.name, "duplicate")
    # The row stores the final name, so the name is chosen before the commit.
    try:
        target = free_target_name(path.name, store.names_in(folders.done_dir))
    except OSError:
        raise _FileFailedError("move_failed", move_to_failed=False) from None
    try:
        with repository.transaction():
            receipt = repository.add(image_hash, target, utc_text(now))
    except sqlite3.Error:
        raise _FileFailedError("save_failed") from None
    try:
        store.move(path, folders.done_dir / target)
    except OSError:
        _delete_receipt(repository, receipt.id)
        raise _FileFailedError("move_failed", move_to_failed=False) from None
    except Exception:
        # The file is not in the done folder, so its row must not stay either.
        _delete_receipt(repository, receipt.id)
        raise
    return FileResult(path.name, "imported")


def _delete_receipt(repository: ReceiptRepository, receipt_id: int) -> None:
    try:
        with repository.transaction():
            repository.delete(receipt_id)
    except sqlite3.Error as error:
        # The file stays in the import folder, so the next run reports it as a duplicate.
        log_without_message("Could not delete a receipt whose file was not moved", error)


def _move_to_failed(path: Path, store: FileStore, failed_dir: Path) -> None:
    try:
        target = free_target_name(path.name, store.names_in(failed_dir))
        store.move(path, failed_dir / target)
    except OSError:
        # The file stays in the import folder; the result still has its original reason.
        pass
