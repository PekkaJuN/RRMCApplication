"""Synthetic receipts and fakes for OCR, Ollama and the clock, shared by evaluation tests."""

import datetime
import io
import json
from collections.abc import Sequence
from pathlib import Path

from PIL import Image

from evaluation.ocr import OcrError, Oriented
from evaluation.ollama import ReadResult
from evaluation.truth import Receipt, Truth, TruthLine

TRUTH = Truth(store="Kauppa", date=datetime.date(2026, 1, 2), total_cents=125, line_count=1)
RIGHT_ANSWER = json.dumps(
    {"s": "Kauppa", "d": "2026-01-02", "t": 125, "l": [{"n": "MAITO", "a": 125, "r": False}]}
)


def image_bytes(width: int = 600) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, 100), (200, 100, 50)).save(buffer, format="JPEG")
    return buffer.getvalue()


def make_receipts(folder: Path, count: int, full: Sequence[int] = ()) -> list[Receipt]:
    receipts: list[Receipt] = []
    for index in range(1, count + 1):
        image = folder / f"r{index}.jpg"
        image.write_bytes(image_bytes())
        lines = [TruthLine(name="MAITO", amount_cents=125)] if index in full else None
        receipts.append(Receipt(index, image, TRUTH.model_copy(update={"lines": lines})))
    return receipts


class FakeOcr:
    # What `orient` hands on when it turns an image, so tests can see OCR got the turned one.
    TURNED = b"turned image"

    def __init__(
        self,
        text: str = "MAITO 1,25",
        fail: bool = False,
        osd_rotation: int = 0,
        osd_confidence: float | None = None,
    ) -> None:
        self.text = text
        self.fail = fail
        self.osd_rotation = osd_rotation
        self.osd_confidence = osd_confidence
        self.oriented: list[bytes] = []
        self.images: list[bytes] = []

    def orient(self, image: bytes) -> Oriented:
        self.oriented.append(image)
        turned = self.TURNED if self.osd_rotation else image
        return Oriented(turned, self.osd_rotation, self.osd_confidence)

    def read(self, image: bytes) -> str:
        self.images.append(image)
        if self.fail:
            raise OcrError("fake failure")
        return self.text


class FakeReader:
    def __init__(
        self,
        results: Sequence[ReadResult] = (),
        problems: Sequence[str] = (),
    ) -> None:
        self._results = list(results)
        self._problems = list(problems)
        self.events: list[str] = []
        self.reads: list[tuple[str, str, bytes | None]] = []
        self.checked: list[str] = []

    def check(self, models: Sequence[str]) -> list[str]:
        self.checked = list(models)
        self.events.append("check")
        return self._problems

    def warm_up(self, model: str) -> None:
        self.events.append(f"warm_up {model}")

    def read(self, model: str, prompt: str, image: bytes | None) -> ReadResult:
        self.events.append(f"read {model}")
        self.reads.append((model, prompt, image))
        if self._results:
            return self._results.pop(0)
        return ReadResult(text=RIGHT_ANSWER, stats={"eval_count": 30})


class FakeClock:
    """Each call is `step` seconds after the previous one."""

    def __init__(self, step: float = 5.0) -> None:
        self._now = 0.0
        self._step = step

    def __call__(self) -> float:
        self._now += self._step
        return self._now
