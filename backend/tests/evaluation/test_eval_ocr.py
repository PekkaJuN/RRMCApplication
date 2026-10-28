import io
import subprocess
from collections.abc import Sequence

import pytest
from PIL import Image

from evaluation.ocr import OcrError, TesseractOcr, preprocess


def image_bytes(width: int, height: int, color: tuple[int, int, int] = (120, 130, 140)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def open_image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


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


@pytest.mark.parametrize(
    "result",
    [done(1, b""), OSError("no tesseract"), subprocess.TimeoutExpired("tesseract", 1)],
)
def test_ac5_tesseract_failure_raises_ocr_error(
    result: subprocess.CompletedProcess[bytes] | Exception,
) -> None:
    with pytest.raises(OcrError):
        TesseractOcr(run=FakeRun(result)).read(b"image")
