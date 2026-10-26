"""OCR engine interface, the Tesseract implementation and a fake for tests."""

import subprocess
from collections.abc import Callable, Sequence
from typing import Literal, Protocol

type OcrCheckResult = Literal["ok", "unavailable"]
type RunCommand = Callable[[Sequence[str], float], subprocess.CompletedProcess[str]]

REQUIRED_LANGUAGES = frozenset({"fin", "eng"})
CHECK_TIMEOUT_SECONDS = 5.0


class OcrEngine(Protocol):
    def check(self) -> OcrCheckResult:
        """Tell whether OCR can run."""
        ...


def _run(args: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed command, no user input
        args, capture_output=True, text=True, timeout=timeout, check=False
    )


class TesseractOcrEngine:
    def __init__(self, run: RunCommand = _run) -> None:
        self._run = run

    def check(self) -> OcrCheckResult:
        """`ok` when Tesseract runs and has the Finnish and English language data."""
        try:
            result = self._run(["tesseract", "--list-langs"], CHECK_TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            return "unavailable"
        if result.returncode != 0:
            return "unavailable"
        # The first line is a header naming the tessdata folder; one language per line follows.
        languages = set(result.stdout.splitlines()[1:])
        return "ok" if languages.issuperset(REQUIRED_LANGUAGES) else "unavailable"


class FakeOcrEngine:
    """Deterministic OCR for tests and E2E runs; never starts Tesseract."""

    def check(self) -> OcrCheckResult:
        return "ok"
