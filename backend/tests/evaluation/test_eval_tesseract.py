import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from evaluation.ocr import TesseractOcr, preprocess

pytestmark = pytest.mark.tesseract


def synthetic_receipt() -> bytes:
    image = Image.new("RGB", (700, 260), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=40)
    draw.text((30, 40), "MAITO          1,25", fill="black", font=font)
    draw.text((30, 150), "YHTEENSÄ       1,25", fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_ac5_real_tesseract_reads_a_synthetic_receipt() -> None:
    text = TesseractOcr().read(preprocess(synthetic_receipt()))

    assert "MAITO" in text
    assert "1,25" in text


# OSD needs enough text: two lines are too few for it (see the spec, PC4).
LONG_RECEIPT_LINES = [
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


def long_receipt_on_its_side() -> bytes:
    image = Image.new("RGB", (700, 60 + 60 * len(LONG_RECEIPT_LINES)), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=32)
    for number, line in enumerate(LONG_RECEIPT_LINES):
        draw.text((30, 30 + 60 * number), line, fill="black", font=font)
    buffer = io.BytesIO()
    image.transpose(Image.Transpose.ROTATE_90).save(buffer, format="PNG")
    return buffer.getvalue()


def test_ac24_real_osd_turns_a_receipt_on_its_side_upright() -> None:
    ocr = TesseractOcr()

    oriented = ocr.orient(preprocess(long_receipt_on_its_side()))
    text = ocr.read(oriented.image)

    assert oriented.osd_rotation in (90, 270)
    assert "MAITO" in text
    assert "1,25" in text
