"""Error codes of the import (receipt-import spec, API errors)."""

from app import texts
from app.errors import AppError


class ImportRunningError(AppError):
    def __init__(self) -> None:
        super().__init__("import_running", texts.IMPORT_RUNNING, 409)


class FoldersUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__("folders_unavailable", texts.FOLDERS_UNAVAILABLE, 503)


class OcrNotReadyError(AppError):
    def __init__(self) -> None:
        super().__init__("ocr_unavailable", texts.OCR_UNAVAILABLE, 503)


class ModelNotReadyError(AppError):
    def __init__(self) -> None:
        super().__init__("model_unavailable", texts.MODEL_UNAVAILABLE, 503)
