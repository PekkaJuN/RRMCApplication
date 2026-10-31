from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.review.schemas import LineUpdate, NewLine, ReceiptUpdate


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": None},
        {"amount_cents": "1"},
        {"amount_cents": 1.5},
        {"amount_cents": True},
        {"is_deposit_refund": 1},
        {"category_id": None},
        {"category_id": "12"},
        {"name": "Limu", "color": "red"},
    ],
)
def test_ac14_line_update_refuses(body: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        LineUpdate.model_validate(body)


@pytest.mark.parametrize(
    "body",
    [
        {"amount_cents": 99},
        {"name": "Banaani"},
        {"name": "", "amount_cents": 99, "is_deposit_refund": None},
        {"name": "Banaani", "amount_cents": 99, "category_id": 12},
        {"name": "Banaani", "amount_cents": "99"},
    ],
)
def test_ac16_new_line_refuses(body: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        NewLine.model_validate(body)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"store": None},
        {"purchase_date": None},
        {"total_cents": None},
        {"total_cents": "349"},
        {"reviewed": None},
        {"reviewed": "yes"},
        {"reviewed": True, "note": "x"},
    ],
)
def test_ac21_receipt_update_refuses(body: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ReceiptUpdate.model_validate(body)


@pytest.mark.parametrize(
    ("model", "body"),
    [
        (LineUpdate, {"name": "Limu"}),
        (LineUpdate, {"name": "Vesi", "amount_cents": -40, "is_deposit_refund": True}),
        (LineUpdate, {"category_id": 12}),
        (ReceiptUpdate, {"reviewed": True}),
        (ReceiptUpdate, {"store": "", "purchase_date": "2026-10-06", "total_cents": 0}),
        (NewLine, {"name": "Panttipalautus", "amount_cents": -40, "is_deposit_refund": True}),
    ],
)
def test_valid_bodies_parse(model: type[BaseModel], body: dict[str, Any]) -> None:
    assert model.model_validate(body).model_dump(exclude_unset=True) == body


def test_new_line_is_not_a_refund_by_default() -> None:
    assert (
        NewLine.model_validate({"name": "Banaani", "amount_cents": 99}).is_deposit_refund is False
    )
