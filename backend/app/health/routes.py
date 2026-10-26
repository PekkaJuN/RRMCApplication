"""GET /api/health."""

from fastapi import APIRouter

from app.health.schemas import HealthResponse
from app.health.service import HealthService


def create_health_router(service: HealthService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/health")
    def get_health() -> HealthResponse:
        return service.check()

    return router
