import io

import pytest
from PIL import Image

from app.receipt_reading.preprocess import UnreadableImageError, exif_orientation, preprocess

EXIF_ORIENTATION = 0x0112


def upright_receipt(width: int = 300, height: int = 400) -> Image.Image:
    """Taller than wide, with a dark band at the top that shows which way is up."""
    image = Image.new("RGB", (width, height), "white")
    image.paste((20, 20, 20), (0, 0, width, height // 10))
    return image


def jpeg(image: Image.Image, orientation: int | None = None) -> bytes:
    buffer = io.BytesIO()
    exif = Image.Exif()
    if orientation is not None:
        exif[EXIF_ORIENTATION] = orientation
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def opened(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def top_is_dark(image: Image.Image) -> bool:
    width, height = image.size
    top = image.getpixel((width // 2, height // 40))
    bottom = image.getpixel((width // 2, height - height // 40))
    assert isinstance(top, int) and isinstance(bottom, int)
    return top < 100 < bottom


def test_ac1_exif_6_turns_the_image_upright_and_scales_it() -> None:
    # Given a 400 x 300 JPEG that a phone stored on its side, with EXIF orientation 6
    stored = jpeg(upright_receipt().transpose(Image.Transpose.ROTATE_90), orientation=6)
    assert opened(stored).size == (400, 300)

    # When it is preprocessed
    result = opened(preprocess(stored))

    # Then it is a grayscale, upright receipt 1 500 x 2 000 px
    assert result.mode == "L"
    assert result.size == (1500, 2000)
    assert top_is_dark(result)


@pytest.mark.parametrize("orientation", [None, 1, 9])
def test_ac2_missing_or_broken_tag_is_not_turned(orientation: int | None) -> None:
    stored = jpeg(upright_receipt(), orientation=orientation)

    result = opened(preprocess(stored))

    assert result.mode == "L"
    assert result.size == (1500, 2000)
    assert top_is_dark(result)


def test_ac5_wide_image_is_not_downscaled() -> None:
    stored = jpeg(upright_receipt(2400, 3200))

    assert opened(preprocess(stored)).size == (2400, 3200)


@pytest.mark.parametrize("data", [b"\xff\xd8\xff\xe0 not an image", b"", b"\x89PNG\r\n\x1a\n"])
def test_ac11_undecodable_bytes_are_an_unreadable_image(data: bytes) -> None:
    with pytest.raises(UnreadableImageError):
        preprocess(data)


def test_exif_orientation_is_reported() -> None:
    assert exif_orientation(jpeg(upright_receipt(), orientation=6)) == 6
    assert exif_orientation(jpeg(upright_receipt())) is None
