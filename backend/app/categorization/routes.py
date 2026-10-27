"""Routes of /api/categories and /api/products. The rules are in service.py."""

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.categorization.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)
from app.categorization.service import KEEP, CategoryService, ProductService
from app.settings import Settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect


def create_catalog_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api")

    def repository() -> Generator[CatalogRepository]:
        connection = connect(settings.db_path)
        try:
            yield CatalogRepository(connection)
        finally:
            connection.close()

    def category_service(
        repo: Annotated[CatalogRepository, Depends(repository)],
    ) -> CategoryService:
        return CategoryService(repo)

    def product_service(repo: Annotated[CatalogRepository, Depends(repository)]) -> ProductService:
        return ProductService(repo)

    @router.get("/categories")
    def list_categories(
        service: Annotated[CategoryService, Depends(category_service)],
    ) -> list[CategoryOut]:
        return [CategoryOut.from_row(row) for row in service.list()]

    @router.post("/categories", status_code=201)
    def create_category(
        body: CategoryCreate, service: Annotated[CategoryService, Depends(category_service)]
    ) -> CategoryOut:
        return CategoryOut.from_row(service.create(body.name, body.kind, body.parent_id))

    @router.patch("/categories/{item_id}")
    def update_category(
        item_id: int,
        body: CategoryUpdate,
        service: Annotated[CategoryService, Depends(category_service)],
    ) -> CategoryOut:
        parent_id = body.parent_id if "parent_id" in body.model_fields_set else KEEP
        row = service.update(item_id, name=body.name, kind=body.kind, parent_id=parent_id)
        return CategoryOut.from_row(row)

    @router.delete("/categories/{item_id}", status_code=204)
    def delete_category(
        item_id: int, service: Annotated[CategoryService, Depends(category_service)]
    ) -> Response:
        service.delete(item_id)
        return Response(status_code=204)

    @router.get("/products")
    def list_products(
        service: Annotated[ProductService, Depends(product_service)],
        q: str = "",
        category_id: int | None = None,
    ) -> list[ProductOut]:
        return [ProductOut.from_row(row) for row in service.list(q, category_id)]

    @router.post("/products", status_code=201)
    def create_product(
        body: ProductCreate, service: Annotated[ProductService, Depends(product_service)]
    ) -> ProductOut:
        return ProductOut.from_row(service.create(body.name, body.category_id))

    @router.patch("/products/{product_id}")
    def update_product(
        product_id: int,
        body: ProductUpdate,
        service: Annotated[ProductService, Depends(product_service)],
    ) -> ProductOut:
        row = service.update(product_id, name=body.name, category_id=body.category_id)
        return ProductOut.from_row(row)

    @router.delete("/products/{product_id}", status_code=204)
    def delete_product(
        product_id: int, service: Annotated[ProductService, Depends(product_service)]
    ) -> Response:
        service.delete(product_id)
        return Response(status_code=204)

    return router
