"""Synthetic image files and failing doubles for import tests.

The images have a valid signature but are not real images.
"""

import sqlite3
from pathlib import Path

from app.receipt_import.files import LocalFileStore
from app.storage.receipt_repository import ReceiptRepository, ReceiptRow

JPEG_SIGNATURE = b"\xff\xd8\xff"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def jpeg(tag: str) -> bytes:
    """JPEG-signed bytes; a different `tag` gives different bytes and so a different hash."""
    return JPEG_SIGNATURE + b"\xe0synthetic " + tag.encode()


def png(tag: str) -> bytes:
    """PNG-signed bytes; a different `tag` gives different bytes and so a different hash."""
    return PNG_SIGNATURE + b"synthetic " + tag.encode()


class FailingStore(LocalFileStore):
    """Raises `error` on reading `read_fails`, or on moving into a folder in `move_fails`."""

    def __init__(
        self,
        *,
        read_fails: str = "",
        move_fails: Path | None = None,
        names_fail: bool = False,
        error: Exception | None = None,
    ) -> None:
        self._read_fails = read_fails
        self._move_fails = move_fails
        self._names_fail = names_fail
        self._error = error or OSError("simulated")

    def read_bytes(self, path: Path) -> bytes:
        if path.name == self._read_fails:
            raise self._error
        return super().read_bytes(path)

    def names_in(self, folder: Path) -> set[str]:
        if self._names_fail:
            raise OSError("simulated")
        return super().names_in(folder)

    def move(self, source: Path, target: Path) -> None:
        if target.parent == self._move_fails:
            raise OSError("simulated")
        super().move(source, target)


class FailingRepository(ReceiptRepository):
    def __init__(
        self, connection: sqlite3.Connection, *, add_fails: bool = False, delete_fails: bool = False
    ) -> None:
        super().__init__(connection)
        self._add_fails = add_fails
        self._delete_fails = delete_fails

    def add(self, image_hash: str, file_name: str, imported_at: str) -> ReceiptRow:
        if self._add_fails:
            raise sqlite3.OperationalError("simulated")
        return super().add(image_hash, file_name, imported_at)

    def delete(self, receipt_id: int) -> None:
        if self._delete_fails:
            raise sqlite3.OperationalError("simulated")
        super().delete(receipt_id)
