"""Rules for the files of the import folders."""

import os
from pathlib import Path
from typing import Protocol

from app.image_files import move_file

_IGNORED_NAMES = {"desktop.ini", "thumbs.db"}


def is_ignored(name: str) -> bool:
    """Hidden files and Windows system files are not import candidates."""
    return name.startswith(".") or name.casefold() in _IGNORED_NAMES


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
        """Move `source` to `target`, which must not exist (see `move_file`)."""
        move_file(source, target)
