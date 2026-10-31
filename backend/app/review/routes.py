"""Routes of /api/receipts. The rules are in service.py and the sums in calculation."""

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.review.schemas import LineUpdate, NewLine, ReceiptOut, ReceiptSummaryOut, ReceiptUpdate
from app.review.service import LineEdit, ReceiptEdit, ReviewService
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
        body: ReceiptUpdate,
        service: Annotated[ReviewService, Depends(review_service)],
    ) -> ReceiptOut:
        edit = ReceiptEdit(
            store=body.store,
            purchase_date=body.purchase_date,
            total_cents=body.total_cents,
            reviewed=body.reviewed,
        )
        view = service.update_receipt(receipt_id, edit)
        return ReceiptOut.from_view(view)

    @router.patch("/receipts/{receipt_id}/lines/{line_id}")
    def update_line(
        receipt_id: int,
        line_id: int,
        body: LineUpdate,
        service: Annotated[ReviewService, Depends(review_service)],
    ) -> ReceiptOut:
        edit = LineEdit(
            name=body.name,
            amount_cents=body.amount_cents,
            is_deposit_refund=body.is_deposit_refund,
            category_id=body.category_id,
        )
        view = service.edit_line(receipt_id, line_id, edit)
        return ReceiptOut.from_view(view)

    @router.post("/receipts/{receipt_id}/lines", status_code=201)
    def add_line(
        receipt_id: int,
        body: NewLine,
        service: Annotated[ReviewService, Depends(review_service)],
    ) -> ReceiptOut:
        view = service.add_line(
            receipt_id, body.name, body.amount_cents, is_deposit_refund=body.is_deposit_refund
        )
        return ReceiptOut.from_view(view)

    @router.delete("/receipts/{receipt_id}/lines/{line_id}")
    def delete_line(
        receipt_id: int, line_id: int, service: Annotated[ReviewService, Depends(review_service)]
    ) -> ReceiptOut:
        return ReceiptOut.from_view(service.delete_line(receipt_id, line_id))

    return router
