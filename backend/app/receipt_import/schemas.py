"""API schema of /api/import."""

from typing import Literal

from pydantic import BaseModel

from app.receipt_import.run import FailureReason


class FailureOut(BaseModel):
    file_name: str
    reason: FailureReason
    message: str


class StoppedOut(BaseModel):
    """Why a run stopped before its last file (receipt-reading PC7)."""

    reason: Literal["model_unavailable"]
    message: str


class ImportStateOut(BaseModel):
    """The current or latest import run (receipt-import spec, Run state)."""

    state: Literal["idle", "running", "finished"]
    total: int
    processed: int
    imported: int
    duplicates: list[str]
    failures: list[FailureOut]
    started_at: str | None
    finished_at: str | None
    stopped: StoppedOut | None = None
