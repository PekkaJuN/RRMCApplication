"""Preprocessing and Tesseract OCR for `ocr:` variants; upright images for `vision:` (PC4).

Preprocessing, orientation detection and OCR are the app's own, so the evaluation measures
what the app ships (receipt-reading PC11). Only the `vision:` image is the tool's.
"""

import io
import subprocess
from collections.abc import Callable, Sequence
from typing import Protocol

from PIL import Image, ImageOps

from app.engines.ocr import OSD_ARGS as OSD_ARGS
from app.engines.ocr import OSD_MIN_CONFIDENCE as OSD_MIN_CONFIDENCE
from app.engines.ocr import OcrError as OcrError
from app.engines.ocr import Oriented as Oriented
from app.engines.ocr import TesseractOcrEngine
from app.receipt_reading.preprocess import encode as _encode
from app.receipt_reading.preprocess import exif_orientation as exif_orientation
from app.receipt_reading.preprocess import orientation_of as _orientation
from app.receipt_reading.preprocess import preprocess as preprocess

type RunCommand = Callable[[Sequence[str], bytes], subprocess.CompletedProcess[bytes]]


class Ocr(Protocol):
    def orient(self, image: bytes) -> Oriented:
        """The image turned upright by orientation detection; never raises (AC25)."""
        ...

    def read(self, image: bytes) -> str:
        """The text of an image.

        Raises:
            OcrError: the image was not read.
        """
        ...


def upright_original(image: bytes) -> bytes:
    """The image for a `vision:` variant (AC26).

    Upright from EXIF in its own format, or the original bytes when there is nothing to turn.
    """
    with Image.open(io.BytesIO(image)) as source:
        if _orientation(source) in (None, 1):
            return image
        image_format = source.format
        icc_profile = source.info.get("icc_profile")
        turned = ImageOps.exif_transpose(source)
    if icc_profile:
        turned.info["icc_profile"] = icc_profile
    # MPO is a JPEG with more pictures in it (Ultra HDR phone photos).
    if image_format in ("JPEG", "MPO"):
        return _encode(turned, "JPEG", quality=95)
    return _encode(turned, "PNG")


class TesseractOcr:
    """The app's Tesseract engine; `run` replaces the process call in tests."""

    def __init__(self, run: RunCommand | None = None) -> None:
        self._engine = TesseractOcrEngine(run_image=run) if run else TesseractOcrEngine()

    def orient(self, image: bytes) -> Oriented:
        return self._engine.orient(image)

    def read(self, image: bytes) -> str:
        return self._engine.read(image)
