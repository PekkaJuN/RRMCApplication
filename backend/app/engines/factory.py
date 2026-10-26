"""Chooses the real engines or the fakes from the settings."""

from dataclasses import dataclass

from app.engines.model import FakeReceiptModel, OllamaReceiptModel, ReceiptModel
from app.engines.ocr import FakeOcrEngine, OcrEngine, TesseractOcrEngine
from app.settings import Settings


@dataclass(frozen=True)
class Engines:
    ocr: OcrEngine
    model: ReceiptModel


def create_engines(settings: Settings) -> Engines:
    if settings.engines == "fake":
        return Engines(ocr=FakeOcrEngine(), model=FakeReceiptModel())
    return Engines(
        ocr=TesseractOcrEngine(),
        model=OllamaReceiptModel(str(settings.ollama_url), settings.model),
    )
