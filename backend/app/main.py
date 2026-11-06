"""FastAPI application factory."""

from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.budget.routes import create_budget_router
from app.categorization.defaults import seed_defaults
from app.categorization.routes import create_catalog_router
from app.engines.factory import Engines, create_engines
from app.errors import add_error_handlers
from app.export.csv_exporter import CsvExporter
from app.export.exporter import Exporter
from app.export.routes import create_export_router
from app.health.routes import create_health_router
from app.health.service import HealthService, ModelLoader
from app.host_check import add_host_check
from app.logging_setup import add_request_logging, configure_logging
from app.receipt_import.routes import create_import_router
from app.receipt_import.service import ImportService
from app.receipt_reading.factory import create_reader
from app.review.failed_images import FailedFolder
from app.review.routes import create_review_router
from app.settings import Settings, load_settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from app.storage.migrate import MIGRATIONS_DIR, migrate_database
from app.totals.routes import create_totals_router


def create_app(
    settings: Settings | None = None,
    extra_routers: Sequence[APIRouter] = (),
    engines: Engines | None = None,
    migrations_dir: Path = MIGRATIONS_DIR,
    import_service: ImportService | None = None,
    exporter: Exporter | None = None,
    clock: Callable[[], datetime] | None = None,
    failed_folder: FailedFolder | None = None,
) -> FastAPI:
    """Build the application.

    `extra_routers`, `engines`, `migrations_dir`, `import_service`, `exporter`, `clock` and
    `failed_folder` let tests add test-only endpoints, fake servers, throwaway migrations,
    simulated file failures, a fixed exporter, a fixed time for new receipts and a failing
    move of a failed image; production passes none of them, and the engines then follow
    `settings.engines`.
    """
    settings = settings or load_settings()
    engines = engines or create_engines(settings)
    configure_logging(settings.log_level)
    model_loader = ModelLoader(engines.model)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        migrate_database(settings.db_path, migrations_dir)
        _seed_catalog(settings)
        model_loader.start()
        yield

    app = FastAPI(title="RRMCApplication", lifespan=lifespan)
    add_error_handlers(app)
    add_host_check(app)
    add_request_logging(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[f"http://127.0.0.1:{settings.ui_port}"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(create_health_router(HealthService(settings, engines, model_loader)))
    app.include_router(create_catalog_router(settings))
    import_service = import_service or ImportService(
        settings, engines=engines, reader=create_reader(settings, engines)
    )
    app.include_router(create_import_router(import_service))
    app.include_router(create_review_router(settings, clock, failed_folder))
    app.include_router(create_totals_router(settings))
    app.include_router(create_budget_router(settings))
    app.include_router(create_export_router(settings, exporter or CsvExporter()))
    for router in extra_routers:
        app.include_router(router)
    return app


def _seed_catalog(settings: Settings) -> None:
    connection = connect(settings.db_path)
    try:
        seed_defaults(CatalogRepository(connection), datetime.now(UTC))
    finally:
        connection.close()
