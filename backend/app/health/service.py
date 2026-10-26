"""Health checks (database, folders, OCR and model) and loading the model (FR-30)."""

import logging
import os
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

from app.engines.factory import Engines
from app.engines.model import ModelLoadError, ReceiptModel
from app.health.schemas import Availability, HealthChecks, HealthResponse
from app.settings import Settings
from app.storage.db import is_available

logger = logging.getLogger(__name__)

type CanWrite = Callable[[Path], bool]
type RunInBackground = Callable[[Callable[[], None]], None]


def _can_write(path: Path) -> bool:
    return os.access(path, os.W_OK)


def check_folders(folders: Sequence[Path], can_write: CanWrite = _can_write) -> Availability:
    """`ok` when every folder exists and can be written to."""
    if all(folder.is_dir() and can_write(folder) for folder in folders):
        return "ok"
    return "unavailable"


def overall_status(checks: HealthChecks) -> Literal["ok", "degraded"]:
    values = (checks.database, checks.folders, checks.ocr, checks.model)
    return "ok" if all(value == "ok" for value in values) else "degraded"


def _run_in_thread(work: Callable[[], None]) -> None:
    threading.Thread(target=work, name="model-loader", daemon=True).start()


class ModelLoader:
    """Loads the model once: at start when it is available, otherwise on the first health
    check that finds it available. Loading runs in the background because it can take
    minutes; a failed load is retried on the next such health check.
    """

    def __init__(
        self, model: ReceiptModel, run_in_background: RunInBackground = _run_in_thread
    ) -> None:
        self._model = model
        self._run_in_background = run_in_background
        self._lock = threading.Lock()
        self._state: Literal["not_loaded", "loading", "loaded"] = "not_loaded"

    def start(self) -> None:
        # Checking first keeps an unreachable Ollama from starting a load that would race
        # with the first health check.
        if self._model.check() == "ok":
            self.on_model_ok()

    def on_model_ok(self) -> None:
        with self._lock:
            if self._state != "not_loaded":
                return
            self._state = "loading"
        self._run_in_background(self._load)

    def _load(self) -> None:
        try:
            self._model.load()
        except ModelLoadError as error:
            logger.warning("%s; retrying on the next health check", error)
            new_state = "not_loaded"
        else:
            new_state = "loaded"
        with self._lock:
            self._state = new_state


class HealthService:
    def __init__(self, settings: Settings, engines: Engines, model_loader: ModelLoader) -> None:
        self._settings = settings
        self._engines = engines
        self._model_loader = model_loader

    def check(self) -> HealthResponse:
        """Run every check now, so a service started later is noticed without a restart."""
        settings = self._settings
        checks = HealthChecks(
            database="ok" if is_available(settings.db_path) else "unavailable",
            folders=check_folders([settings.import_dir, settings.done_dir, settings.failed_dir]),
            ocr=self._engines.ocr.check(),
            model=self._engines.model.check(),
        )
        if checks.model == "ok":
            self._model_loader.on_model_ok()
        return HealthResponse(
            status=overall_status(checks), model_name=settings.model, checks=checks
        )
