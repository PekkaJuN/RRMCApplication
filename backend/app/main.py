"""FastAPI application factory."""

from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.engines.factory import Engines, create_engines
from app.errors import add_error_handlers
from app.health.routes import create_health_router
from app.health.service import HealthService, ModelLoader
from app.logging_setup import add_request_logging, configure_logging
from app.settings import Settings, load_settings
from app.storage.migrate import MIGRATIONS_DIR, migrate_database


def create_app(
    settings: Settings | None = None,
    extra_routers: Sequence[APIRouter] = (),
    engines: Engines | None = None,
    migrations_dir: Path = MIGRATIONS_DIR,
) -> FastAPI:
    """Build the application.

    `extra_routers`, `engines` and `migrations_dir` let tests add test-only endpoints, fake
    servers and throwaway migrations; production passes none of them, and the engines then
    follow `settings.engines`.
    """
    settings = settings or load_settings()
    engines = engines or create_engines(settings)
    configure_logging(settings.log_level)
    model_loader = ModelLoader(engines.model)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        migrate_database(settings.db_path, migrations_dir)
        model_loader.start()
        yield

    app = FastAPI(title="RRMCApplication", lifespan=lifespan)
    add_error_handlers(app)
    add_request_logging(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[f"http://127.0.0.1:{settings.ui_port}"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(create_health_router(HealthService(settings, engines, model_loader)))
    for router in extra_routers:
        app.include_router(router)
    return app
