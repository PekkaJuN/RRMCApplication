"""Error codes of the budget (budget spec, Error codes)."""

from app import texts
from app.errors import AppError


class NotABudgetRowError(AppError):
    def __init__(self) -> None:
        super().__init__("not_a_budget_row", texts.NOT_A_BUDGET_ROW, 422)


class InvalidBudgetAmountError(AppError):
    def __init__(self) -> None:
        super().__init__("invalid_amount", texts.INVALID_AMOUNT, 422)
