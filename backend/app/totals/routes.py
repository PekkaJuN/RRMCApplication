"""Route of /api/totals. The rules are in calculation; service.py reads the data."""

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.settings import Settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from app.storage.receipt_repository import ReceiptRepository
from app.totals.schemas import TotalsOut
from app.totals.service import TotalsService


def create_totals_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api")

    def totals_service() -> Generator[TotalsService]:
        connection = connect(settings.db_path)
        try:
            yield TotalsService(CatalogRepository(connection), ReceiptRepository(connection))
        finally:
            connection.close()

    # Plain optional strings: every missing or bad value reaches parse_period and becomes
    # invalid_period, not FastAPI's generic invalid_request (totals spec P4).
    @router.get("/totals")
    def get_totals(
        service: Annotated[TotalsService, Depends(totals_service)],
        unit: str | None = None,
        first: Annotated[str | None, Query(alias="from")] = None,
        last: Annotated[str | None, Query(alias="to")] = None,
    ) -> TotalsOut:
        return TotalsOut.from_view(service.totals(unit, first, last))

    return router
