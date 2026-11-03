"""Rules for receipt image files, shared by import and review (receipt-management Plan P3).

Import reads the import folder and review the failed folder; neither may depend on the
other, so the rules both need live here.
"""

import hashlib
import os
import shutil
from collections.abc import Set
from pathlib import Path, PurePath

_SIGNATURES = {
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png": b"\x89PNG\r\n\x1a\n",
}
_MEDIA_TYPES = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


def image_identifier(data: bytes) -> str:
    """The image identifier: SHA-256 of the file's bytes as lowercase hex (FR-3)."""
    return hashlib.sha256(data).hexdigest()


def check_format(name: str, data: bytes) -> bool:
    """Tell whether the file is a JPEG or PNG: the extension and the content must agree."""
    signature = _SIGNATURES.get(PurePath(name).suffix.casefold())
    return signature is not None and data.startswith(signature)


def media_type(data: bytes) -> str | None:
    """The media type of a JPEG or PNG from its signature; None for anything else."""
    for signature, media in _MEDIA_TYPES:
        if data.startswith(signature):
            return media
    return None


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


def move_file(source: Path, target: Path) -> None:
    """Move `source` to `target`, which must not exist. Raises `OSError` on failure.

    The image folders are separate mounts in the container, so `os.rename` between them
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
