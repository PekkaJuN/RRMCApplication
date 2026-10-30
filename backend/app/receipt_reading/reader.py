"""The receipt reader interface and the OCR reader (FR-6–FR-9).

Import calls only the reader, so a vision reader can be added behind the same interface
(ADR 0003).
"""

from typing import Protocol

from app.engines.model import ModelAnswerError, ModelTimeoutError, ReceiptModel
from app.engines.ocr import OcrEngine, OcrError
from app.receipt_reading.preprocess import UnreadableImageError, preprocess
from app.receipt_reading.prompt import ANSWER_SCHEMA, parse_answer, text_prompt
from app.receipt_reading.receipt import ReadFailedError, ReadReceipt
from app.receipt_reading.validation import to_read_receipt


class ReceiptReader(Protocol):
    def read(self, image: bytes) -> ReadReceipt:
        """The receipt in an image.

        Raises:
            ReadFailedError: this image was not read; the next one may be.
            ModelUnavailableError: the model cannot be used now, for any image.
        """
        ...


class OcrReceiptReader:
    """Tesseract reads the text; the text model turns it into a receipt."""

    def __init__(self, ocr: OcrEngine, model: ReceiptModel) -> None:
        self._ocr = ocr
        self._model = model

    def read(self, image: bytes) -> ReadReceipt:
        try:
            prepared = preprocess(image)
        except UnreadableImageError:
            raise ReadFailedError("unreadable_image") from None
        try:
            text = self._ocr.read(self._ocr.orient(prepared).image)
        except OcrError:
            raise ReadFailedError("ocr_failed") from None
        if not text.strip():
            raise ReadFailedError("no_text")
        try:
            raw = self._model.generate(text_prompt(text), ANSWER_SCHEMA)
        except (ModelTimeoutError, ModelAnswerError):
            raise ReadFailedError("parse_failed") from None
        answer = parse_answer(raw)
        if answer is None:
            raise ReadFailedError("parse_failed")
        return to_read_receipt(answer, text)
