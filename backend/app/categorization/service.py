"""Rules of the catalog: groups, categories and products (product-management spec)."""

from enum import Enum

from app.categorization.errors import (
    CategoryHasProductsError,
    CategoryInUseError,
    DepositRefundLineError,
    DuplicateNameError,
    GroupNotEmptyError,
    InvalidParentError,
    NotACategoryError,
    NotFoundError,
    UnknownCategoryError,
)
from app.categorization.names import (
    finnish_sort_key,
    normalize_key,
    validate_category_name,
    validate_product_name,
)
from app.storage.catalog_repository import CatalogRepository, CategoryRow, Kind, ProductRow
from app.storage.receipt_repository import LineCategory, ReceiptRepository, StoredLine


class Keep(Enum):
    """Marks a field that an update leaves as it is (unlike `None`, which clears it)."""

    KEEP = "keep"


KEEP = Keep.KEEP


class CategoryService:
    """Groups and categories: at most two levels, one name namespace."""

    def __init__(self, repository: CatalogRepository) -> None:
        self._repository = repository

    def list(self) -> list[CategoryRow]:
        """Groups, each followed by its categories, then the categories without a group;
        Finnish order inside each part."""
        rows = sorted(
            self._repository.list_categories(), key=lambda row: finnish_sort_key(row.name)
        )
        ordered: list[CategoryRow] = []
        for group in (row for row in rows if row.kind == "group"):
            ordered.append(group)
            ordered += [row for row in rows if row.parent_id == group.id]
        ordered += [row for row in rows if row.kind == "category" and row.parent_id is None]
        return ordered

    def create(self, name: str, kind: Kind, parent_id: int | None) -> CategoryRow:
        """Raises: InvalidNameError, DuplicateNameError, InvalidParentError."""
        with self._repository.transaction():
            display = validate_category_name(name)
            key = normalize_key(display)
            if self._repository.get_category_by_key(key) is not None:
                raise DuplicateNameError.for_category()
            self._check_parent(kind, parent_id)
            item_id = self._repository.add_category(display, key, kind, parent_id)
            return self._get(item_id)

    def update(
        self,
        item_id: int,
        *,
        name: str | None = None,
        kind: Kind | None = None,
        parent_id: int | None | Keep = KEEP,
    ) -> CategoryRow:
        """Rename, move or convert. The resulting state is validated as a whole, so a
        category can leave its group and become a group in one update.

        Raises: NotFoundError, InvalidNameError, DuplicateNameError,
        CategoryHasProductsError, GroupNotEmptyError, InvalidParentError.
        """
        with self._repository.transaction():
            item = self._get(item_id)
            display = item.name if name is None else validate_category_name(name)
            key = normalize_key(display)
            same_name = self._repository.get_category_by_key(key)
            if same_name is not None and same_name.id != item.id:
                raise DuplicateNameError.for_category()
            new_kind = kind or item.kind
            if new_kind != item.kind:
                if item.product_count or item.line_count:
                    raise CategoryHasProductsError()
                if item.category_count:
                    raise GroupNotEmptyError(item.category_count)
            new_parent = item.parent_id if isinstance(parent_id, Keep) else parent_id
            # The parent row still has its old kind here, so an item cannot be checked as
            # its own parent.
            if new_parent == item.id:
                raise InvalidParentError()
            self._check_parent(new_kind, new_parent)
            self._repository.update_category(item.id, display, key, new_kind, new_parent)
            return self._get(item.id)

    def delete(self, item_id: int) -> None:
        """Raises: NotFoundError, CategoryInUseError, GroupNotEmptyError."""
        with self._repository.transaction():
            item = self._get(item_id)
            if item.product_count or item.line_count:
                raise CategoryInUseError(item.product_count, item.line_count)
            if item.category_count:
                raise GroupNotEmptyError(item.category_count)
            self._repository.delete_category(item.id)

    def _get(self, item_id: int) -> CategoryRow:
        item = self._repository.get_category(item_id)
        if item is None:
            raise NotFoundError()
        return item

    def _check_parent(self, kind: Kind, parent_id: int | None) -> None:
        if parent_id is None:
            return
        parent = self._repository.get_category(parent_id)
        if kind == "group" or parent is None or parent.kind != "group":
            raise InvalidParentError()


class ProductService:
    """Products: each belongs to exactly one category, never to a group."""

    def __init__(self, repository: CatalogRepository) -> None:
        self._repository = repository

    def list(self, query: str | None = None, category_id: int | None = None) -> list[ProductRow]:
        """Products sorted by name. `query` matches part of the normalized name;
        `category_id` is a category or a group (all its categories).

        Raises: UnknownCategoryError for a filter id that does not exist.
        """
        if category_id is not None and self._repository.get_category(category_id) is None:
            raise UnknownCategoryError()
        rows = self._repository.list_products(
            query_key=normalize_key(query) if query else None,
            category_or_group_id=category_id,
        )
        return sorted(rows, key=lambda row: finnish_sort_key(row.name))

    def create(self, name: str, category_id: int) -> ProductRow:
        """Raises: InvalidNameError, UnknownCategoryError, NotACategoryError,
        DuplicateNameError."""
        with self._repository.transaction():
            display = validate_product_name(name)
            self._check_category(category_id)
            key = normalize_key(display)
            if self._repository.get_product_by_key(key) is not None:
                raise DuplicateNameError.for_product()
            product_id = self._repository.add_product(display, key, category_id)
            return self._get(product_id)

    def update(
        self, product_id: int, *, name: str | None = None, category_id: int | None = None
    ) -> ProductRow:
        """Rename and/or recategorize. A new category moves the product's lines (FR-36).

        Raises: NotFoundError, InvalidNameError, UnknownCategoryError, NotACategoryError,
        DuplicateNameError.
        """
        with self._repository.transaction():
            product = self._get(product_id)
            display = product.name if name is None else validate_product_name(name)
            if category_id is not None:
                self._check_category(category_id)
            key = normalize_key(display)
            same_name = self._repository.get_product_by_key(key)
            if same_name is not None and same_name.id != product.id:
                raise DuplicateNameError.for_product()
            self._repository.update_product(product.id, display, key, product.category_id)
            if category_id is not None and category_id != product.category_id:
                _change_product_category(self._repository, self._get(product.id), category_id)
            return self._get(product.id)

    def delete(self, product_id: int) -> None:
        """Raises: NotFoundError."""
        with self._repository.transaction():
            self._repository.delete_product(self._get(product_id).id)

    def _get(self, product_id: int) -> ProductRow:
        product = self._repository.get_product(product_id)
        if product is None:
            raise NotFoundError()
        return product

    def _check_category(self, category_id: int) -> None:
        _check_category(self._repository, category_id)


class LineCategoryService:
    """The product rules of receipt lines (FR-13, FR-36, FR-43).

    The caller holds the transaction, on the catalog's connection, which both repositories
    must share; so one request can rename a line and choose its category together.
    """

    def __init__(self, catalog: CatalogRepository, receipts: ReceiptRepository) -> None:
        self._catalog = catalog
        self._receipts = receipts

    def choose(self, line: StoredLine, category_id: int) -> None:
        """Give the line the category with source `user`, and store it as the category of
        the line's product, creating the product when none matches (FR-13).

        Raises: UnknownCategoryError, NotACategoryError, DepositRefundLineError,
        InvalidNameError.
        """
        _check_category(self._catalog, category_id)
        if line.is_deposit_refund:
            raise DepositRefundLineError()
        product = self._product_of(line)
        if product is None:
            display = validate_product_name(line.name)
            product_id = self._catalog.add_product(display, normalize_key(display), category_id)
        else:
            product_id = product.id
            if product.category_id != category_id:
                _change_product_category(self._catalog, product, category_id)
        # After the product's lines moved, so this line keeps the source `user`.
        self._receipts.set_line_category(line.id, LineCategory(category_id, "user", product_id))

    def follow_name(self, line: StoredLine, name: str) -> LineCategory | None:
        """The category of the normal line `line` once it is renamed to the display name
        `name` (FR-43). The caller writes the line.

        A case or spacing change keeps the category. A name match gives the product's
        category. Otherwise a line with a category makes a new product with it, as a
        correction does (FR-13). The product the line followed before is not changed.
        """
        key = normalize_key(name)
        if key == normalize_key(line.name):
            return line.category
        product = self._catalog.get_product_by_key(key)
        if product is not None:
            return LineCategory(product.category_id, "remembered", product.id)
        if line.category is None:
            return None
        product_id = self._catalog.add_product(name, key, line.category.category_id)
        return LineCategory(line.category.category_id, "user", product_id)

    def resolve(self, name: str) -> LineCategory | None:
        """The category of a new normal line, or of a line that stops being a deposit
        refund: its name match's, or none. No model call, so an edit answers at once (NFR-9).
        """
        product = self._catalog.get_product_by_key(normalize_key(name))
        if product is None:
            return None
        return LineCategory(product.category_id, "remembered", product.id)

    def _product_of(self, line: StoredLine) -> ProductRow | None:
        """The line's product: the linked one, else the one with the line's name. A link
        always names an existing product: deleting a product clears it (`ON DELETE SET NULL`).
        """
        if line.category is not None and line.category.product_id is not None:
            return self._catalog.get_product(line.category.product_id)
        return self._catalog.get_product_by_key(normalize_key(line.name))


def _check_category(repository: CatalogRepository, category_id: int) -> None:
    category = repository.get_category(category_id)
    if category is None:
        raise UnknownCategoryError()
    if category.kind != "category":
        raise NotACategoryError()


def _change_product_category(
    repository: CatalogRepository, product: ProductRow, category_id: int
) -> None:
    """Recategorize the product and every line that follows it (FR-36)."""
    repository.update_product(product.id, product.name, product.name_key, category_id)
    repository.move_product_lines(product.id, category_id)
