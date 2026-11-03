"""Routes of /api/receipts. The rules are in service.py and the sums in calculation."""

from collections.abc import Callable, Generator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.review.failed_images import FailedFolder
from app.review.schemas import (
    FailedImagesOut,
    LineUpdate,
    NewLine,
    NewReceiptBody,
    ReceiptOut,
    ReceiptSummaryOut,
    ReceiptUpdate,
)
from app.review.service import LineEdit, NewReceipt, ReceiptEdit, ReviewService
from app.settings import Settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from app.storage.receipt_repository import ReceiptRepository


def _utc_now() -> datetime:
    return datetime.now(UTC)


def create_review_router(
    settings: Settings,
    clock: Callable[[], datetime] | None = None,
    failed_folder: FailedFolder | None = None,
) -> APIRouter:
    """`clock` gives a new receipt's creation time and `failed_folder` the failed images;
    tests replace them to fix the time and to simulate a failing move."""
    router = APIRouter(prefix="/api")
    folder = failed_folder or FailedFolder(settings.failed_dir, settings.done_dir)
    now = clock or _utc_now

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

    @router.get("/failed-images")
    def list_failed_images() -> FailedImagesOut:
        return FailedImagesOut(file_names=folder.names())

    # The name is a query parameter, so it stays out of the request log (PC8).
    @router.get("/failed-images/image")
    def get_failed_image(name: str) -> Response:
        data, media_type = folder.preview(name)
        return Response(data, media_type=media_type, headers={"Cache-Control": "no-store"})

    @router.post("/receipts", status_code=201)
    def create_receipt(
        body: NewReceiptBody, service: Annotated[ReviewService, Depends(review_service)]
    ) -> ReceiptOut:
        new = NewReceipt(
            store=body.store,
            purchase_date=body.purchase_date,
            total_cents=body.total_cents,
            image_file_name=body.image_file_name,
        )
        return ReceiptOut.from_view(service.create_receipt(new, now(), folder))

    @router.delete("/receipts/{receipt_id}", status_code=204)
    def delete_receipt(
        receipt_id: int, service: Annotated[ReviewService, Depends(review_service)]
    ) -> Response:
        service.delete_receipt(receipt_id)
        return Response(status_code=204)

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
