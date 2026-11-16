"""Routes of /api/totals and /api/year/totals. The rules are in calculation; service.py and
year.py read the data."""

from collections.abc import Callable, Generator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.local_time import local_today
from app.settings import Settings
from app.storage.archive_repository import ArchiveRepository
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from app.storage.receipt_repository import ReceiptRepository
from app.totals.schemas import TotalsOut, YearTotalsOut
from app.totals.service import TotalsService
from app.totals.year import read_year_totals


def create_totals_router(settings: Settings, clock: Callable[[], datetime]) -> APIRouter:
    """`clock` gives the current year, in Finnish time (year with products spec PC1)."""
    router = APIRouter(prefix="/api")

    def totals_service() -> Generator[TotalsService]:
        connection = connect(settings.db_path)
        try:
            yield TotalsService(
                CatalogRepository(connection),
                ReceiptRepository(connection),
                ArchiveRepository(connection),
            )
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

    @router.get("/year/totals")
    def get_year_totals() -> YearTotalsOut:
        connection = connect(settings.db_path)
        try:
            totals = read_year_totals(ReceiptRepository(connection), local_today(clock).year)
        finally:
            connection.close()
        return YearTotalsOut.from_year(totals)

    return router
