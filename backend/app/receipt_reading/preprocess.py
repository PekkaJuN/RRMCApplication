"""Turn a receipt photo upright and prepare it for OCR (FR-6)."""

import io

from PIL import Image, ImageOps

MIN_WIDTH = 1500
EXIF_ORIENTATION = 0x0112


class UnreadableImageError(OSError):
    """The bytes are not an image Pillow can decode.

    An `OSError`, like Pillow's own error for an image it cannot open, so callers that catch
    `OSError` (the evaluation tool) keep working.
    """


def exif_orientation(image: bytes) -> int | None:
    """The EXIF orientation tag (1–8), or None when the image has none."""
    with Image.open(io.BytesIO(image)) as source:
        return orientation_of(source)


def orientation_of(source: Image.Image) -> int | None:
    # Pillow skips broken EXIF; a value outside 1–8 counts as no tag.
    value = source.getexif().get(EXIF_ORIENTATION)
    return value if isinstance(value, int) and 1 <= value <= 8 else None


def preprocess(image: bytes) -> bytes:
    """Upright from EXIF, grayscale, at least 1 500 px wide, automatic contrast; as PNG.

    Raises:
        UnreadableImageError: the bytes cannot be decoded as an image.
    """
    try:
        with Image.open(io.BytesIO(image)) as source:
            # Phones store photos on their side and record the turn in EXIF (learnings
            # 2026-10-29).
            result = ImageOps.exif_transpose(source).convert("L")
    # Pillow raises SyntaxError for some broken PNG files.
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise UnreadableImageError("The image cannot be decoded") from None
    if result.width < MIN_WIDTH:
        result = ImageOps.scale(result, MIN_WIDTH / result.width, Image.Resampling.LANCZOS)
    return encode(ImageOps.autocontrast(result), "PNG")


def encode(image: Image.Image, image_format: str, **options: int) -> bytes:
    """The image in `image_format`, keeping its color profile."""
    buffer = io.BytesIO()
    icc_profile = image.info.get("icc_profile")
    if icc_profile:
        image.save(buffer, format=image_format, icc_profile=icc_profile, **options)
    else:
        image.save(buffer, format=image_format, **options)
    return buffer.getvalue()
