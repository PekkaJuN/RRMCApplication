import io
import subprocess
from collections.abc import Sequence

import pytest
from PIL import Image

from evaluation.ocr import (
    OcrError,
    TesseractOcr,
    exif_orientation,
    preprocess,
    upright_original,
)

EXIF_ORIENTATION = 0x0112
# How a camera stores an upright picture for each EXIF orientation tag value.
STORED_AS = {
    3: Image.Transpose.ROTATE_180,
    6: Image.Transpose.ROTATE_90,
    8: Image.Transpose.ROTATE_270,
}


def image_bytes(width: int, height: int, color: tuple[int, int, int] = (120, 130, 140)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def open_image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def upright_receipt() -> Image.Image:
    """Taller than wide, with marks that show which way is up."""
    image = Image.new("RGB", (400, 700), "white")
    image.paste((200, 30, 30), (20, 20, 380, 80))
    image.paste((30, 30, 200), (20, 600, 120, 680))
    return image


def png(image: Image.Image, orientation: int | None = None) -> bytes:
    buffer = io.BytesIO()
    if orientation is None:
        image.save(buffer, format="PNG")
    else:
        exif = Image.Exif()
        exif[EXIF_ORIENTATION] = orientation
        image.save(buffer, format="PNG", exif=exif)
    return buffer.getvalue()


@pytest.mark.parametrize("orientation", [3, 6, 8])
def test_ac22_exif_orientation_turns_the_image_upright(orientation: int) -> None:
    upright = upright_receipt()
    stored = png(upright.transpose(STORED_AS[orientation]), orientation)

    result = open_image(preprocess(stored))
    expected = open_image(preprocess(png(upright)))

    assert result.size == expected.size
    assert result.tobytes() == expected.tobytes()


@pytest.mark.parametrize("orientation", [3, 6, 8])
def test_ac22_exif_orientation_is_reported(orientation: int) -> None:
    stored = png(upright_receipt().transpose(STORED_AS[orientation]), orientation)

    assert exif_orientation(stored) == orientation


def jpeg(image: Image.Image, orientation: int | None = None) -> bytes:
    buffer = io.BytesIO()
    exif = Image.Exif()
    if orientation is not None:
        exif[EXIF_ORIENTATION] = orientation
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def test_ac26_vision_jpeg_is_turned_upright_without_the_tag() -> None:
    stored = jpeg(upright_receipt().transpose(STORED_AS[6]), 6)

    result = open_image(upright_original(stored))

    assert result.format == "JPEG"
    assert result.size == (400, 700)
    assert EXIF_ORIENTATION not in result.getexif()


def test_ac26_vision_mpo_is_sent_as_jpeg() -> None:
    # Phones with Ultra HDR store a JPEG with a second picture; Pillow opens it as MPO.
    first = upright_receipt().transpose(STORED_AS[6])
    exif = Image.Exif()
    exif[EXIF_ORIENTATION] = 6
    buffer = io.BytesIO()
    first.save(buffer, format="MPO", exif=exif, save_all=True, append_images=[first])
    assert open_image(buffer.getvalue()).format == "MPO"

    result = open_image(upright_original(buffer.getvalue()))

    assert result.format == "JPEG"
    assert result.size == (400, 700)


def test_ac26_vision_jpeg_keeps_its_colour_profile() -> None:
    profile = b"synthetic icc profile"
    stored = io.BytesIO()
    exif = Image.Exif()
    exif[EXIF_ORIENTATION] = 6
    upright_receipt().transpose(STORED_AS[6]).save(
        stored, format="JPEG", exif=exif, icc_profile=profile
    )

    result = open_image(upright_original(stored.getvalue()))

    assert result.info.get("icc_profile") == profile


def test_ac26_vision_png_keeps_its_format() -> None:
    stored = png(upright_receipt().transpose(STORED_AS[6]), 6)

    result = open_image(upright_original(stored))

    assert result.format == "PNG"
    assert result.tobytes() == upright_receipt().tobytes()


@pytest.mark.parametrize("orientation", [None, 1, 0, 9])
def test_ac26_vision_image_without_a_turn_is_sent_unchanged(orientation: int | None) -> None:
    stored = jpeg(upright_receipt(), orientation)

    assert upright_original(stored) == stored


def red_band_is_on_top(image: Image.Image) -> bool:
    """The red band of `upright_receipt` is darker in grayscale than the white middle."""
    gray = image.convert("L")
    top = gray.getpixel((gray.width // 2, gray.height * 50 // 700))
    middle = gray.getpixel((gray.width // 2, gray.height // 2))
    assert isinstance(top, int) and isinstance(middle, int)
    return top < middle


def test_ac23_image_without_exif_orientation_is_not_turned() -> None:
    data = png(upright_receipt())

    result = open_image(preprocess(data))

    assert exif_orientation(data) is None
    assert result.mode == "L"
    assert result.size == (1500, 2625)
    assert red_band_is_on_top(result)


@pytest.mark.parametrize("orientation", [0, 9])
def test_ac23_exif_value_outside_one_to_eight_counts_as_no_tag(orientation: int) -> None:
    data = png(upright_receipt(), orientation)

    result = open_image(preprocess(data))

    assert exif_orientation(data) is None
    assert red_band_is_on_top(result)


def test_ac22_turned_image_has_its_top_up() -> None:
    stored = png(upright_receipt().transpose(STORED_AS[6]), 6)

    assert red_band_is_on_top(open_image(preprocess(stored)))


def test_ac5_small_image_is_grayscale_and_upscaled() -> None:
    result = open_image(preprocess(image_bytes(600, 900)))

    assert result.mode == "L"
    assert result.size == (1500, 2250)


def test_ac5_wide_image_keeps_its_size() -> None:
    result = open_image(preprocess(image_bytes(2000, 3000)))

    assert result.size == (2000, 3000)


def test_ac5_contrast_is_stretched() -> None:
    source = Image.new("L", (1600, 10), 100)
    source.paste(150, (800, 0, 1600, 10))
    buffer = io.BytesIO()
    source.save(buffer, format="PNG")

    result = open_image(preprocess(buffer.getvalue()))

    assert result.getextrema() == (0, 255)


class FakeRun:
    def __init__(self, result: subprocess.CompletedProcess[bytes] | Exception) -> None:
        self.result = result
        self.calls: list[tuple[list[str], bytes]] = []

    def __call__(self, args: Sequence[str], data: bytes) -> subprocess.CompletedProcess[bytes]:
        self.calls.append((list(args), data))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def done(returncode: int, stdout: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=b"")


def test_ac5_tesseract_reads_with_finnish_and_english() -> None:
    run = FakeRun(done(0, "MAITO 1,25\nYHTEENSÄ 1,25\n".encode()))

    text = TesseractOcr(run=run).read(b"image")

    assert text == "MAITO 1,25\nYHTEENSÄ 1,25\n"
    assert run.calls == [
        (["tesseract", "stdin", "stdout", "-l", "fin+eng", "--psm", "4"], b"image")
    ]


def osd_output(rotate: int, confidence: float) -> bytes:
    return (
        f"Page number: 0\nOrientation in degrees: {(360 - rotate) % 360}\nRotate: {rotate}\n"
        f"Orientation confidence: {confidence}\nScript: Latin\nScript confidence: 1.50\n"
    ).encode()


# Tesseract's `Rotate` is how far the picture must turn clockwise to be upright.
TURNED_BY = {
    90: Image.Transpose.ROTATE_90,
    180: Image.Transpose.ROTATE_180,
    270: Image.Transpose.ROTATE_270,
}


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_ac24_osd_rotation_turns_the_image_upright(rotation: int) -> None:
    upright = upright_receipt()
    run = FakeRun(done(0, osd_output(rotation, 5.0)))

    oriented = TesseractOcr(run=run).orient(png(upright.transpose(TURNED_BY[rotation])))

    assert run.calls[0][0] == ["tesseract", "stdin", "stdout", "--psm", "0"]
    assert open_image(oriented.image).tobytes() == upright.tobytes()
    assert oriented.osd_rotation == rotation
    assert oriented.osd_confidence == 5.0


def test_ac24_confidence_at_the_limit_turns_the_image() -> None:
    upright = upright_receipt()
    run = FakeRun(done(0, osd_output(90, 2.0)))

    oriented = TesseractOcr(run=run).orient(png(upright.transpose(TURNED_BY[90])))

    assert (oriented.osd_rotation, oriented.osd_confidence) == (90, 2.0)
    assert open_image(oriented.image).tobytes() == upright.tobytes()


def test_ac25_confidence_that_is_not_a_number_counts_as_failed_osd() -> None:
    image = png(upright_receipt())
    output = osd_output(90, 5.0).replace(b"5.0", b"nan")

    oriented = TesseractOcr(run=FakeRun(done(0, output))).orient(image)

    assert oriented == type(oriented)(image, 0, None)


@pytest.mark.parametrize(
    ("output", "confidence"),
    [(osd_output(90, 1.5), 1.5), (osd_output(0, 5.0), 5.0)],
)
def test_ac25_low_confidence_or_no_rotation_keeps_the_image(
    output: bytes, confidence: float
) -> None:
    image = png(upright_receipt())

    oriented = TesseractOcr(run=FakeRun(done(0, output))).orient(image)

    assert oriented.image == image
    assert oriented.osd_rotation == 0
    assert oriented.osd_confidence == confidence


@pytest.mark.parametrize(
    "result",
    [
        done(1, b""),
        done(0, b"Page number: 0\n"),
        OSError("no tesseract"),
        subprocess.TimeoutExpired("tesseract", 1),
    ],
)
def test_ac25_failed_osd_keeps_the_image(
    result: subprocess.CompletedProcess[bytes] | Exception,
) -> None:
    image = png(upright_receipt())

    oriented = TesseractOcr(run=FakeRun(result)).orient(image)

    assert oriented.image == image
    assert oriented.osd_rotation == 0
    assert oriented.osd_confidence is None


@pytest.mark.parametrize(
    "result",
    [done(1, b""), OSError("no tesseract"), subprocess.TimeoutExpired("tesseract", 1)],
)
def test_ac5_tesseract_failure_raises_ocr_error(
    result: subprocess.CompletedProcess[bytes] | Exception,
) -> None:
    with pytest.raises(OcrError):
        TesseractOcr(run=FakeRun(result)).read(b"image")
