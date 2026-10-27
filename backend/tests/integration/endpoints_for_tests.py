"""Test-only endpoints, added through create_app's extra_routers. Production has none."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.errors import AppError

router = APIRouter(prefix="/api/test")


class ValueBody(BaseModel):
    value: int


class TextBody(BaseModel):
    text: str


@router.post("/value")
def accept_value(body: ValueBody) -> dict[str, int]:
    return {"value": body.value}


@router.post("/fail")
def fail_after_reading(body: TextBody) -> None:
    raise RuntimeError("Test endpoint failure")


@router.get("/app-error")
def raise_app_error() -> None:
    raise AppError("test_conflict", "Testiristiriita.", 409)


@router.get("/app-error-extra")
def raise_app_error_with_extra() -> None:
    raise AppError("test_in_use", "Testi käytössä.", 409, extra={"product_count": 3})
