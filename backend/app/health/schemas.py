"""API schema of GET /api/health."""

from typing import Literal

from pydantic import BaseModel

from app.engines.model import ModelCheckResult
from app.engines.ocr import OcrCheckResult

type Availability = Literal["ok", "unavailable"]


class HealthChecks(BaseModel):
    database: Availability
    folders: Availability
    ocr: OcrCheckResult
    model: ModelCheckResult


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    model_name: str
    checks: HealthChecks
