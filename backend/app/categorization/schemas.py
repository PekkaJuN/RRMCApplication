"""API schemas of /api/categories and /api/products."""

from pydantic import BaseModel

from app.storage.catalog_repository import CategoryRow, Kind, ProductRow


class CategoryCreate(BaseModel):
    name: str
    kind: Kind
    parent_id: int | None = None


class CategoryUpdate(BaseModel):
    """Fields left out stay as they are; `"parent_id": null` takes a category out of its
    group, so the route tells the two apart with `model_fields_set`."""

    name: str | None = None
    kind: Kind | None = None
    parent_id: int | None = None


class CategoryOut(BaseModel):
    """A group or a category. Only the count that fits its kind is set."""

    id: int
    name: str
    kind: Kind
    parent_id: int | None
    product_count: int | None
    category_count: int | None

    @classmethod
    def from_row(cls, row: CategoryRow) -> "CategoryOut":
        is_group = row.kind == "group"
        return cls(
            id=row.id,
            name=row.name,
            kind=row.kind,
            parent_id=row.parent_id,
            product_count=None if is_group else row.product_count,
            category_count=row.category_count if is_group else None,
        )


class ProductCreate(BaseModel):
    name: str
    category_id: int


class ProductUpdate(BaseModel):
    name: str | None = None
    category_id: int | None = None


class ProductOut(BaseModel):
    id: int
    name: str
    category_id: int
    category_name: str
    group_name: str | None

    @classmethod
    def from_row(cls, row: ProductRow) -> "ProductOut":
        return cls(
            id=row.id,
            name=row.name,
            category_id=row.category_id,
            category_name=row.category_name,
            group_name=row.group_name,
        )
