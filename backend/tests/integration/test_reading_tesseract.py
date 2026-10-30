"""The OCR reader with the real Tesseract of the backend image: `pytest -m tesseract`."""

import io
from typing import Any

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.engines.model import FakeReceiptModel
from app.engines.ocr import TesseractOcrEngine
from app.receipt_reading.reader import OcrReceiptReader

pytestmark = pytest.mark.tesseract

EXIF_ORIENTATION = 0x0112
# OSD needs enough text: two lines are too few for it (model-evaluation spec, PC4).
LINES = [
    "MAITO          1,25",
    "LEIPA          2,49",
    "OMENA          2,12",
    "KAHVI 500G     5,99",
    "JUUSTO         4,35",
    "BANAANI        1,10",
    "VOI            3,20",
    "JOGURTTI       0,99",
    "PANTTI         0,40",
    "TOMAATTI       2,75",
] * 2


class RecordingModel(FakeReceiptModel):
    """Answers like the fake and keeps the prompt, which holds the OCR text."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, schema: dict[str, Any]) -> str:
        self.prompts.append(prompt)
        return super().generate(prompt, schema)


def upright_receipt() -> Image.Image:
    image = Image.new("RGB", (700, 60 + 60 * len(LINES)), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=32)
    for number, line in enumerate(LINES):
        draw.text((30, 30 + 60 * number), line, fill="black", font=font)
    return image


def sideways_jpeg_with_exif_6() -> bytes:
    """As a phone stores it: on its side, with the turn in the EXIF orientation tag."""
    exif = Image.Exif()
    exif[EXIF_ORIENTATION] = 6
    buffer = io.BytesIO()
    upright_receipt().transpose(Image.Transpose.ROTATE_90).save(
        buffer, format="JPEG", quality=95, exif=exif
    )
    return buffer.getvalue()


def sideways_png_without_exif() -> bytes:
    buffer = io.BytesIO()
    upright_receipt().transpose(Image.Transpose.ROTATE_270).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.parametrize(
    "image", [sideways_jpeg_with_exif_6(), sideways_png_without_exif()], ids=["exif 6", "no exif"]
)
def test_ac1_ac3_sideways_receipt_is_read_upright(image: bytes) -> None:
    model = RecordingModel()

    OcrReceiptReader(ocr=TesseractOcrEngine(), model=model).read(image)

    [prompt] = model.prompts
    assert "MAITO" in prompt
    assert "1,25" in prompt
    assert "JUUSTO" in prompt
