"""Routes of /api/import. The rules are in service.py."""

from fastapi import APIRouter

from app.receipt_import.schemas import ImportStateOut
from app.receipt_import.service import ImportService


def create_import_router(service: ImportService) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/import")
    def get_import() -> ImportStateOut:
        return service.state()

    @router.post("/import", status_code=202)
    def start_import() -> ImportStateOut:
        return service.start()

    return router
