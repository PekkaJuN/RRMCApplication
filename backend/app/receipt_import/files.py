"""Rules for the files of the import folders."""

import hashlib
import os
import shutil
from collections.abc import Set
from pathlib import Path, PurePath
from typing import Protocol

_SIGNATURES = {
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png": b"\x89PNG\r\n\x1a\n",
}
_IGNORED_NAMES = {"desktop.ini", "thumbs.db"}


def image_identifier(data: bytes) -> str:
    """The image identifier: SHA-256 of the file's bytes as lowercase hex (FR-3)."""
    return hashlib.sha256(data).hexdigest()


def check_format(name: str, data: bytes) -> bool:
    """Tell whether the file is a JPEG or PNG: the extension and the content must agree."""
    signature = _SIGNATURES.get(PurePath(name).suffix.casefold())
    return signature is not None and data.startswith(signature)


def is_ignored(name: str) -> bool:
    """Hidden files and Windows system files are not import candidates."""
    return name.startswith(".") or name.casefold() in _IGNORED_NAMES


def free_target_name(name: str, taken: Set[str]) -> str:
    """The first of `name`, `stem (2).ext`, `stem (3).ext`, ... not in `taken`.

    `taken` holds lower-cased names, because the folders are on Windows, where names differ
    only by case are the same file.
    """
    if name.casefold() not in taken:
        return name
    path = PurePath(name)
    number = 2
    while (candidate := f"{path.stem} ({number}){path.suffix}").casefold() in taken:
        number += 1
    return candidate


class FileStore(Protocol):
    """File access of an import run. Tests replace it to simulate failing disks."""

    def list_files(self, folder: Path) -> list[Path]: ...

    def read_bytes(self, path: Path) -> bytes: ...

    def names_in(self, folder: Path) -> set[str]: ...

    def move(self, source: Path, target: Path) -> None: ...


class LocalFileStore:
    """The files on disk."""

    def list_files(self, folder: Path) -> list[Path]:
        """Regular files directly in `folder`, without ignored names, in name order."""
        with os.scandir(folder) as entries:
            files = [
                Path(entry.path)
                for entry in entries
                if entry.is_file(follow_symlinks=False) and not is_ignored(entry.name)
            ]
        return sorted(files, key=lambda path: (path.name.casefold(), path.name))

    def read_bytes(self, path: Path) -> bytes:
        return path.read_bytes()

    def names_in(self, folder: Path) -> set[str]:
        """Lower-cased names of everything in `folder`."""
        return {name.casefold() for name in os.listdir(folder)}

    def move(self, source: Path, target: Path) -> None:
        """Move `source` to `target`, which must not exist. Raises `OSError` on failure.

        The import folders are separate mounts in the container, so `os.rename` between them
        fails, and on Linux it would overwrite an existing target. Copy, then delete instead;
        on any failure the file is left in exactly one place.
        """
        with target.open("xb") as copy:
            try:
                with source.open("rb") as original:
                    shutil.copyfileobj(original, copy)
                copy.flush()
                os.fsync(copy.fileno())
            except BaseException:
                copy.close()
                target.unlink()
                raise
        try:
            source.unlink()
        except BaseException:
            target.unlink()
            raise
