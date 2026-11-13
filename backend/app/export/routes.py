"""Routes of /api/export. The files are built by the exporter; service.py reads the data."""

from collections.abc import Callable, Generator
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.export.exporter import Exporter, ExportFile, ReportExporter
from app.export.service import ExportService
from app.local_time import local_today
from app.settings import Settings
from app.storage.archive_repository import ArchiveRepository
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from app.storage.receipt_repository import ReceiptRepository


def create_export_router(
    settings: Settings,
    exporter: Exporter,
    report_exporter: ReportExporter,
    clock: Callable[[], datetime],
) -> APIRouter:
    """`clock` gives the creation day of a PDF file, in Finnish time (PDF export spec P7)."""
    router = APIRouter(prefix="/api/export")

    def today() -> date:
        return local_today(clock)

    def export_service() -> Generator[ExportService]:
        connection = connect(settings.db_path)
        try:
            yield ExportService(
                CatalogRepository(connection),
                ReceiptRepository(connection),
                exporter,
                report_exporter,
                today,
                ArchiveRepository(connection),
            )
        finally:
            connection.close()

    # Plain optional strings, as in GET /api/totals: the service gives invalid_period for a
    # bad period first, then invalid_request for a bad `by` (export spec P5, AC17).
    @router.get("/lines")
    def get_lines(
        service: Annotated[ExportService, Depends(export_service)],
        unit: str | None = None,
        first: Annotated[str | None, Query(alias="from")] = None,
        last: Annotated[str | None, Query(alias="to")] = None,
    ) -> Response:
        return _download(service.lines_file(unit, first, last))

    @router.get("/totals")
    def get_totals(
        service: Annotated[ExportService, Depends(export_service)],
        unit: str | None = None,
        first: Annotated[str | None, Query(alias="from")] = None,
        last: Annotated[str | None, Query(alias="to")] = None,
        by: str | None = None,
    ) -> Response:
        return _download(service.totals_file(unit, first, last, by))

    @router.get("/totals/pdf")
    def get_totals_pdf(
        service: Annotated[ExportService, Depends(export_service)],
        unit: str | None = None,
        first: Annotated[str | None, Query(alias="from")] = None,
        last: Annotated[str | None, Query(alias="to")] = None,
        by: str | None = None,
    ) -> Response:
        return _download(service.totals_pdf(unit, first, last, by))

    # As GET /api/budget/comparison: every bad value is invalid_period.
    @router.get("/comparison/pdf")
    def get_comparison_pdf(
        service: Annotated[ExportService, Depends(export_service)],
        month: str | None = None,
        period: str | None = None,
    ) -> Response:
        return _download(service.comparison_pdf(month, period))

    # As the PDF route; a bad `weeks` is invalid_request after the period (comparison CSV
    # export spec PC8).
    @router.get("/comparison")
    def get_comparison(
        service: Annotated[ExportService, Depends(export_service)],
        month: str | None = None,
        period: str | None = None,
        weeks: str | None = None,
    ) -> Response:
        return _download(service.comparison_file(month, period, weeks))

    # A plain string, so a bad year is invalid_year, as in /api/archive (archiving spec P4).
    @router.get("/archive/{year}")
    def get_archive(
        service: Annotated[ExportService, Depends(export_service)], year: str
    ) -> Response:
        return _download(service.archive_file(year))

    return router


def _download(file: ExportFile) -> Response:
    # The name comes from the exporter, which builds it from a checked period only.
    return Response(
        file.content,
        media_type=file.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file.name}"',
            "Cache-Control": "no-store",
        },
    )
