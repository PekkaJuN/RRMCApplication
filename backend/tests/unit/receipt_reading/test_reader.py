import io
from datetime import date
from typing import Any

import pytest
from PIL import Image

from app.engines.model import (
    ModelAnswerError,
    ModelCheckResult,
    ModelTimeoutError,
    ModelUnavailableError,
)
from app.engines.ocr import OcrCheckResult, OcrError, Oriented
from app.receipt_reading.prompt import ANSWER_SCHEMA
from app.receipt_reading.reader import OcrReceiptReader
from app.receipt_reading.receipt import ReadFailedError, ReadLine

OCR_TEXT = "  K-MARKET TESTI\nMAITO 1,25\n"
VALID = (
    '{"s": "K-Market Testi", "d": "2026-10-05", "t": 125, '
    '"l": [{"n": "Maito", "a": 125, "r": false}]}'
)


def jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (300, 400), "white").save(buffer, format="JPEG")
    return buffer.getvalue()


class StubOcr:
    def __init__(self, text: str | Exception = OCR_TEXT) -> None:
        self.text = text
        self.read_images: list[bytes] = []

    def check(self) -> OcrCheckResult:
        return "ok"

    def orient(self, image: bytes) -> Oriented:
        return Oriented(b"oriented:" + image[:4], 90, 3.0)

    def read(self, image: bytes) -> str:
        self.read_images.append(image)
        if isinstance(self.text, Exception):
            raise self.text
        return self.text


class StubModel:
    def __init__(self, answer: str | Exception = VALID) -> None:
        self.answer = answer
        self.prompts: list[tuple[str, dict[str, Any]]] = []

    def check(self) -> ModelCheckResult:
        return "ok"

    def load(self) -> None:
        return None

    def generate(self, prompt: str, schema: dict[str, Any]) -> str:
        self.prompts.append((prompt, schema))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def reader(ocr: StubOcr, model: StubModel) -> OcrReceiptReader:
    return OcrReceiptReader(ocr=ocr, model=model)


def test_ac6_image_is_read_into_a_receipt() -> None:
    # Given OCR reads the text and the model gives a valid answer
    ocr, model = StubOcr(), StubModel()

    # When an image is read
    result = reader(ocr, model).read(jpeg())

    # Then OCR got the oriented image, the model got the text, and the receipt keeps the
    # OCR text as Tesseract returned it
    assert ocr.read_images[0].startswith(b"oriented:")
    assert model.prompts[0][1] == ANSWER_SCHEMA
    assert OCR_TEXT in model.prompts[0][0]
    assert result.store == "K-Market Testi"
    assert result.purchase_date == date(2026, 10, 5)
    assert result.lines == (ReadLine("Maito", 125, is_deposit_refund=False),)
    assert result.ocr_text == OCR_TEXT


def failure(ocr: StubOcr, model: StubModel, image: bytes | None = None) -> str:
    with pytest.raises(ReadFailedError) as error:
        reader(ocr, model).read(jpeg() if image is None else image)
    return error.value.reason


def test_ac11_undecodable_image_is_unreadable_image() -> None:
    ocr, model = StubOcr(), StubModel()

    assert failure(ocr, model, b"\xff\xd8\xff\xe0 not an image") == "unreadable_image"
    assert ocr.read_images == []


def test_ac12_ocr_error_is_ocr_failed() -> None:
    model = StubModel()

    assert failure(StubOcr(OcrError("exit 1")), model) == "ocr_failed"
    assert model.prompts == []


@pytest.mark.parametrize("text", ["", " \n ", "\t"])
def test_ac12_blank_text_is_no_text_and_the_model_is_not_called(text: str) -> None:
    model = StubModel()

    assert failure(StubOcr(text), model) == "no_text"
    assert model.prompts == []


@pytest.mark.parametrize(
    "answer",
    [ModelTimeoutError("slow"), ModelAnswerError("500"), "not json", '{"s": "x"}'],
    ids=["timeout", "answer error", "not json", "schema"],
)
def test_ac8_ac11b_bad_or_missing_answer_is_parse_failed(answer: str | Exception) -> None:
    assert failure(StubOcr(), StubModel(answer)) == "parse_failed"


def test_ac9_answer_breaking_a_rule_is_parse_failed() -> None:
    no_lines = '{"s": "x", "d": "2026-10-05", "t": 0, "l": []}'

    assert failure(StubOcr(), StubModel(no_lines)) == "parse_failed"


def test_ac20_unavailable_model_passes_through() -> None:
    with pytest.raises(ModelUnavailableError):
        reader(StubOcr(), StubModel(ModelUnavailableError("refused"))).read(jpeg())
