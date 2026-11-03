"""The receipt image in the done folder (receipt-review PC3)."""

from pathlib import Path, PurePath

from app.image_files import media_type
from app.review.errors import ImageMissingError


def read_image(done_dir: Path, file_name: str) -> tuple[bytes, str]:
    """The image's bytes and media type, found by the stored file name only.

    Raises ImageMissingError when the name is not a plain file name, the file resolves to
    anywhere but directly inside the done folder, cannot be read, or is not JPEG or PNG.
    """
    if file_name in ("", ".", "..") or PurePath(file_name).name != file_name:
        raise ImageMissingError()
    try:
        folder = done_dir.resolve()
        path = (folder / file_name).resolve()
        if path.parent != folder:
            raise ImageMissingError()
        data = path.read_bytes()
    except OSError as error:
        raise ImageMissingError() from error
    media = media_type(data)
    if media is None:
        raise ImageMissingError()
    return data, media
