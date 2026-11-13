"""Routes of /api/archive (archiving spec P4). The rules are in service.py."""

from collections.abc import Callable, Generator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.archive.schemas import (
    ArchiveOverviewOut,
    ArchiveResultOut,
    ArchiveTotalsOut,
    DeletedYearOut,
)
from app.archive.service import ArchiveFiles, ArchiveService
from app.receipt_import.service import ImportService
from app.settings import Settings
from app.storage.archive_repository import ArchiveRepository
from app.storage.db import connect


def create_archive_router(
    settings: Settings,
    import_service: ImportService,
    clock: Callable[[], datetime],
    files: ArchiveFiles,
) -> APIRouter:
    router = APIRouter(prefix="/api/archive")

    def import_running() -> bool:
        return import_service.state().state == "running"

    def archive_service() -> Generator[ArchiveService]:
        connection = connect(settings.db_path)
        try:
            yield ArchiveService(
                ArchiveRepository(connection),
                settings.done_dir,
                settings.archive_dir,
                import_running=import_running,
                clock=clock,
                files=files,
            )
        finally:
            connection.close()

    @router.get("")
    def get_overview(
        service: Annotated[ArchiveService, Depends(archive_service)],
    ) -> ArchiveOverviewOut:
        return ArchiveOverviewOut.from_overview(service.overview())

    # `year` is a plain string, so a bad value becomes invalid_year in the service, not
    # FastAPI's generic invalid_request (P4).
    @router.post("/{year}")
    def archive_year(
        service: Annotated[ArchiveService, Depends(archive_service)], year: str
    ) -> ArchiveResultOut:
        return ArchiveResultOut.from_result(service.archive(year))

    @router.delete("/{year}")
    def delete_year(
        service: Annotated[ArchiveService, Depends(archive_service)], year: str
    ) -> DeletedYearOut:
        return DeletedYearOut.from_deleted(service.delete(year))

    @router.get("/{year}/totals")
    def get_totals(
        service: Annotated[ArchiveService, Depends(archive_service)], year: str
    ) -> ArchiveTotalsOut:
        return ArchiveTotalsOut.from_totals(service.totals(year))

    return router
