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
