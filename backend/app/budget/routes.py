"""Routes of /api/budget. The rules are in service.py and calculation."""

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends

from app.budget.schemas import BudgetOut, BudgetUpdate, ComparisonOut
from app.budget.service import BudgetService
from app.settings import Settings
from app.storage.archive_repository import ArchiveRepository
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from app.storage.receipt_repository import ReceiptRepository


def create_budget_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api")

    def budget_service() -> Generator[BudgetService]:
        connection = connect(settings.db_path)
        try:
            yield BudgetService(
                CatalogRepository(connection),
                ReceiptRepository(connection),
                ArchiveRepository(connection),
            )
        finally:
            connection.close()

    @router.get("/budget")
    def get_budget(service: Annotated[BudgetService, Depends(budget_service)]) -> BudgetOut:
        return BudgetOut.from_view(service.rows())

    # Plain optional strings: every missing or bad value becomes invalid_period, not the
    # generic invalid_request of FastAPI (budget spec P7).
    @router.get("/budget/comparison")
    def get_comparison(
        service: Annotated[BudgetService, Depends(budget_service)],
        month: str | None = None,
        period: str | None = None,
    ) -> ComparisonOut:
        return ComparisonOut.from_view(service.comparison(month, period))

    @router.put("/budget/{item_id}")
    def save_budget(
        item_id: int,
        body: BudgetUpdate,
        service: Annotated[BudgetService, Depends(budget_service)],
    ) -> BudgetOut:
        return BudgetOut.from_view(service.save(item_id, body.amount_cents))

    return router
