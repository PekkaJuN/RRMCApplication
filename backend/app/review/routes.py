"""Routes of /api/receipts. The rules are in service.py and the sums in calculation."""

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.review.schemas import LineCategoryUpdate, ReceiptOut, ReceiptSummaryOut, ReviewUpdate
from app.review.service import ReviewService
from app.settings import Settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from app.storage.receipt_repository import ReceiptRepository


def create_review_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api")

    def review_service() -> Generator[ReviewService]:
        # One connection for both repositories: the category choice needs one transaction.
        connection = connect(settings.db_path)
        try:
            yield ReviewService(CatalogRepository(connection), ReceiptRepository(connection))
        finally:
            connection.close()

    @router.get("/receipts")
    def list_receipts(
        service: Annotated[ReviewService, Depends(review_service)],
    ) -> list[ReceiptSummaryOut]:
        return [ReceiptSummaryOut.from_summary(summary) for summary in service.summaries()]

    @router.get("/receipts/{receipt_id}")
    def get_receipt(
        receipt_id: int, service: Annotated[ReviewService, Depends(review_service)]
    ) -> ReceiptOut:
        return ReceiptOut.from_view(service.receipt(receipt_id))

    @router.get("/receipts/{receipt_id}/image")
    def get_image(
        receipt_id: int, service: Annotated[ReviewService, Depends(review_service)]
    ) -> Response:
        data, media_type = service.image(receipt_id, settings.done_dir)
        # A file replaced in the done folder must not be shown from the browser's cache.
        return Response(data, media_type=media_type, headers={"Cache-Control": "no-store"})

    @router.patch("/receipts/{receipt_id}")
    def update_receipt(
        receipt_id: int,
        body: ReviewUpdate,
        service: Annotated[ReviewService, Depends(review_service)],
    ) -> ReceiptOut:
        return ReceiptOut.from_view(service.set_reviewed(receipt_id, reviewed=body.reviewed))

    @router.patch("/receipts/{receipt_id}/lines/{line_id}")
    def update_line(
        receipt_id: int,
        line_id: int,
        body: LineCategoryUpdate,
        service: Annotated[ReviewService, Depends(review_service)],
    ) -> ReceiptOut:
        view = service.set_line_category(receipt_id, line_id, body.category_id)
        return ReceiptOut.from_view(view)

    return router
