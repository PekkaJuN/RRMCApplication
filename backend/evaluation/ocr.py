"""Preprocessing and Tesseract OCR for `ocr:` variants (PC4)."""

import io
import subprocess
from collections.abc import Callable, Sequence
from typing import Protocol

from PIL import Image, ImageOps

type RunCommand = Callable[[Sequence[str], bytes], subprocess.CompletedProcess[bytes]]

MIN_WIDTH = 1500
# --psm 4: one column of text of varying sizes, the layout of a receipt.
TESSERACT_ARGS = ("tesseract", "stdin", "stdout", "-l", "fin+eng", "--psm", "4")
OCR_TIMEOUT_SECONDS = 120.0


class OcrError(Exception):
    """Tesseract did not read the image."""


class Ocr(Protocol):
    def read(self, image: bytes) -> str:
        """The text of an image.

        Raises:
            OcrError: the image was not read.
        """
        ...


def preprocess(image: bytes) -> bytes:
    """Grayscale, at least 1 500 pixels wide, with automatic contrast; as PNG."""
    with Image.open(io.BytesIO(image)) as source:
        result = source.convert("L")
    if result.width < MIN_WIDTH:
        result = ImageOps.scale(result, MIN_WIDTH / result.width, Image.Resampling.LANCZOS)
    result = ImageOps.autocontrast(result)
    buffer = io.BytesIO()
    result.save(buffer, format="PNG")
    return buffer.getvalue()


def _run(args: Sequence[str], data: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603 - fixed command, the image goes to stdin
        args, input=data, capture_output=True, timeout=OCR_TIMEOUT_SECONDS, check=False
    )


class TesseractOcr:
    def __init__(self, run: RunCommand = _run) -> None:
        self._run = run

    def read(self, image: bytes) -> str:
        try:
            result = self._run(TESSERACT_ARGS, image)
        except (OSError, subprocess.TimeoutExpired):
            raise OcrError("Tesseract did not run") from None
        if result.returncode != 0:
            raise OcrError(f"Tesseract exited with code {result.returncode}")
        return result.stdout.decode("utf-8", errors="replace")
