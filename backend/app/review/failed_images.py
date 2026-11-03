"""The failed folder as the new receipt form uses it (receipt-management PC4, PC7, PC8)."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePath

from app.image_files import (
    check_format,
    free_target_name,
    image_identifier,
    media_type,
    move_file,
)
from app.review.errors import (
    FoldersUnavailableError,
    ImageMoveFailedError,
    ImageNotFoundError,
    UnsupportedFormatError,
)

_SUFFIXES = {".jpg", ".jpeg", ".png"}


def _is_failed_image_name(name: str) -> bool:
    return PurePath(name).suffix.casefold() in _SUFFIXES


@dataclass(frozen=True)
class TakenImage:
    """A failed image checked for a new receipt; not moved yet."""

    path: Path
    image_hash: str
    done_name: str


class FailedFolder:
    """The images the import could not read. Only plain names of files directly in the
    folder are accepted, so a request cannot reach any other file. `move` is `move_file`;
    tests pass one that fails (AC24)."""

    def __init__(
        self,
        failed_dir: Path,
        done_dir: Path,
        move: Callable[[Path, Path], None] = move_file,
    ) -> None:
        self._failed_dir = failed_dir
        self._done_dir = done_dir
        self._move = move

    def names(self) -> list[str]:
        """PC7: the failed images' names, sorted by name ignoring case.

        Raises: FoldersUnavailableError.
        """
        try:
            with os.scandir(self._failed_dir) as entries:
                names = [
                    entry.name
                    for entry in entries
                    if entry.is_file(follow_symlinks=False) and _is_failed_image_name(entry.name)
                ]
        except OSError as error:
            raise FoldersUnavailableError() from error
        return sorted(names, key=lambda name: (name.casefold(), name))

    def preview(self, name: str) -> tuple[bytes, str]:
        """PC8: the image's bytes and media type.

        Raises: ImageNotFoundError (404) for a name that is not a failed image, a path, a file
        that cannot be read, or one that is neither JPEG nor PNG.
        """
        data = self._read(self._path(name, status=404), status=404)
        media = media_type(data)
        if media is None:
            raise ImageNotFoundError(404)
        return data, media

    def take(self, name: str) -> TakenImage:
        """PC4 steps 1, 2 and 4: find and read the image, check its format, hash it and
        choose its name in the done folder, as the import does.

        Raises: ImageNotFoundError (422), UnsupportedFormatError, ImageMoveFailedError (the
        done folder cannot be listed).
        """
        path = self._path(name, status=422)
        data = self._read(path, status=422)
        if not check_format(name, data):
            raise UnsupportedFormatError()
        try:
            taken = {entry.casefold() for entry in os.listdir(self._done_dir)}
        except OSError as error:
            raise ImageMoveFailedError() from error
        return TakenImage(path, image_identifier(data), free_target_name(name, taken))

    def move_to_done(self, image: TakenImage) -> None:
        """PC4 step 6. Raises OSError; the file then stays in the failed folder."""
        self._move(image.path, self._done_dir / image.done_name)

    def _path(self, name: str, *, status: int) -> Path:
        """The failed image `name` directly in the folder. Raises: ImageNotFoundError."""
        if (
            name in ("", ".", "..")
            or PurePath(name).name != name
            or not _is_failed_image_name(name)
        ):
            raise ImageNotFoundError(status)
        try:
            folder = self._failed_dir.resolve()
            path = (folder / name).resolve()
        # ValueError: a NUL character in the name, which no file name can hold.
        except (OSError, ValueError) as error:
            raise ImageNotFoundError(status) from error
        # A symbolic link could point out of the folder; is_file() also refuses a folder.
        if path.parent != folder or not path.is_file():
            raise ImageNotFoundError(status)
        return path

    @staticmethod
    def _read(path: Path, *, status: int) -> bytes:
        try:
            return path.read_bytes()
        except OSError as error:
            raise ImageNotFoundError(status) from error
