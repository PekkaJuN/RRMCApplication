# Categorization

Navigation: ↑ [Architecture](../../architecture.md) | → [Data model](../../datamodel.md#categories) | → [API reference](../../api-reference.md#catalog-groups-categories-and-products) | → [Storage](../storage/README.md) | → [UI](../ui/README.md)

## Overview

Categorization owns the **catalog**: groups, categories and products, the rules between them,
name normalization and the default category list. It is the app's memory of which category
each product belongs to (PRD 6.8).

Today it has the catalog only. Assigning a category to each receipt line (remembered product
first, then the model) comes with the receipt specs. It does not calculate totals and runs no
SQL; storage does that.

## Key Files and Entry Points

- @backend/app/categorization/names.py — normalization, name validation, Finnish sort key
- @backend/app/categorization/service.py — `CategoryService`, `ProductService`: every rule
- @backend/app/categorization/defaults.py — `DEFAULT_CATEGORIES` (PRD 6.9), `seed_defaults`
- @backend/app/categorization/errors.py — one `AppError` subclass per error code
- @backend/app/categorization/schemas.py, @backend/app/categorization/routes.py — the
  [catalog endpoints](../../api-reference.md#catalog-groups-categories-and-products)

## Interfaces

The services are plain classes that take a `CatalogRepository`, so other subsystems can call
them without the API (FR-36 and FR-43 will). Each write runs in one transaction.

| Call | Returns | Raises |
|---|---|---|
| `CategoryService.list()` | groups, each followed by its categories, then ungrouped ones | |
| `CategoryService.create(name, kind, parent_id)` | the new item | `InvalidNameError`, `DuplicateNameError`, `InvalidParentError` |
| `CategoryService.update(id, *, name, kind, parent_id=KEEP)` | the item | `NotFoundError`, `InvalidNameError`, `DuplicateNameError`, `CategoryHasProductsError`, `GroupNotEmptyError`, `InvalidParentError` |
| `CategoryService.delete(id)` | | `NotFoundError`, `CategoryInUseError`, `GroupNotEmptyError` |
| `ProductService.list(query, category_id)` | products sorted by name | `UnknownCategoryError` |
| `ProductService.create(name, category_id)` | the new product | `InvalidNameError`, `UnknownCategoryError`, `NotACategoryError`, `DuplicateNameError` |
| `ProductService.update(id, *, name, category_id)` | the product | `NotFoundError` and the errors of `create` |
| `ProductService.delete(id)` | | `NotFoundError` |
| `seed_defaults(repository, now)` | | |

`parent_id=KEEP` (the default) leaves the group as it is; `None` takes a category out of its
group. The API maps a left-out `parent_id` to `KEEP`.

### Names

| Step | Display name | Normalized name (`name_key`) |
|---|---|---|
| 1. Unicode NFC | yes | yes |
| 2. Trim, and collapse inner whitespace to one space | yes | yes |
| 3. Case-fold (`casefold`), å, ä and ö stay letters | | yes |

`"  Kevytmaito   1L "` → display `"Kevytmaito 1L"`, key `"kevytmaito 1l"`. Lengths are
measured on the display name: 1–50 characters for groups and categories, 1–100 for
products. Lists are sorted by the key in Finnish order (å, ä, ö after z), done in Python
because SQLite has no Finnish collation. Product search matches any part of the key.

OCR mix-ups and fuzzy matching (the rest of FR-14) are not handled yet.

### Rules

- Groups and categories share one namespace: no two have the same key. Product keys are
  unique among products. Renaming to a case variant of the own name is allowed.
- A group has no parent. A category's parent, if any, is an existing group other than the
  item itself.
- A product's category is a category, never a group.
- An update is checked against its **resulting** state: a category in a group cannot become
  a group, but the same request with `"parent_id": null` can.
- A category with products cannot become a group; a group with categories cannot become a
  category (`group_not_empty` with the count).
- A category with products cannot be deleted (`category_in_use` with `product_count`); a
  group with categories cannot be deleted (`group_not_empty` with `category_count`).
- The default list is created once, on the first start, and marked in `app_state`. Deleting
  defaults later does not bring them back.

## Data Flow

1. Start: the lifespan in @backend/app/main.py migrates, then calls `seed_defaults`.
2. Request: the route parses the body (shape errors become `invalid_request`), opens one
   connection for the request, and calls the service.
3. Service: inside one transaction, normalize and validate, check the rules against the
   current rows, write, then read back the item with its counts.

## Dependencies

- Uses: [storage](../storage/README.md) (`CatalogRepository`, `transaction`), the shared
  error format (@backend/app/errors.py) and texts (@backend/app/texts.py).
- Used by: the API, and later import and receipt editing.

## Modules

None yet.

## Known Issues and Gotchas

- The services check every rule before writing, although the schema also has `UNIQUE`,
  `CHECK` and `RESTRICT`: the schema alone cannot tell a group from a category in another
  row, and it would give a 500 instead of the right code.
- Product names are personal purchase data. They are not logged; the request log leaves out
  bodies and query strings.

## Related Documents

- [Product management spec](../../../specs/features/product-management.md)
- [datamodel.md](../../datamodel.md#categories): the catalog tables
- [api-reference.md](../../api-reference.md#catalog-groups-categories-and-products)
- [glossary.md](../../glossary.md)
