# Categorization

Navigation: ↑ [Architecture](../../architecture.md) | → [Data model](../../datamodel.md#categories) | → [API reference](../../api-reference.md#catalog-groups-categories-and-products) | → [Storage](../storage/README.md) | → [UI](../ui/README.md)

## Overview

Categorization owns the **catalog**: groups, categories and products, the rules between them,
name normalization and the default category list. It is the app's memory of which category
each product belongs to (PRD 6.8).

It also gives each receipt line its category when a receipt is imported: the remembered
category of a known product first, otherwise a suggestion from the local model
([line categorization](#line-categorization)). A user's correction of a line is stored as
the product's category, and a product's new category moves its lines (FR-13, FR-36). It
does not calculate totals and runs no SQL; storage does that.

The behavior is specified in the
[product management spec](../../../specs/features/product-management.md) and the
[categorization spec](../../../specs/features/categorization.md).

## Key Files and Entry Points

- @backend/app/categorization/names.py — normalization, name validation, Finnish sort key
- @backend/app/categorization/service.py — `CategoryService`, `ProductService`,
  `LineCategoryService`: every rule
- @backend/app/categorization/line_categorizer.py — `LineCategorizer`: a category for each
  line of a read receipt
- @backend/app/categorization/prompt.py — `category_options`, `category_prompt`,
  `answer_schema`, `parse_answer`
- @backend/app/categorization/suggester.py — `CategorySuggester` (the interface),
  `ModelSuggester`, `FakeSuggester`
- @backend/app/categorization/factory.py — `create_suggester(settings, engines)`
- @backend/app/categorization/defaults.py — `DEFAULT_CATEGORIES` (PRD 6.9), `seed_defaults`
- @backend/app/categorization/errors.py — one `AppError` subclass per error code
- @backend/app/categorization/schemas.py, @backend/app/categorization/routes.py — the
  [catalog endpoints](../../api-reference.md#catalog-groups-categories-and-products)

## Interfaces

The services are plain classes that take a `CatalogRepository`, so other subsystems can call
them without the API (import does; the review UI will). Each write runs in one transaction.

| Call | Returns | Raises |
|---|---|---|
| `CategoryService.list()` | groups, each followed by its categories, then ungrouped ones | |
| `CategoryService.create(name, kind, parent_id)` | the new item | `InvalidNameError`, `DuplicateNameError`, `InvalidParentError` |
| `CategoryService.update(id, *, name, kind, parent_id=KEEP)` | the item | `NotFoundError`, `InvalidNameError`, `DuplicateNameError`, `CategoryHasProductsError`, `GroupNotEmptyError`, `InvalidParentError` |
| `CategoryService.delete(id)` | | `NotFoundError`, `CategoryInUseError`, `GroupNotEmptyError` |
| `ProductService.list(query, category_id)` | products sorted by name | `UnknownCategoryError` |
| `ProductService.create(name, category_id)` | the new product | `InvalidNameError`, `UnknownCategoryError`, `NotACategoryError`, `DuplicateNameError` |
| `ProductService.update(id, *, name, category_id)` | the product; a new category moves its linked lines | `NotFoundError` and the errors of `create` |
| `ProductService.delete(id)` | | `NotFoundError` |
| `LineCategoryService(catalog, receipts).set_category(line_id, category_id)` | the line (`StoredLine`) | `NotFoundError`, `UnknownCategoryError`, `NotACategoryError`, `DepositRefundLineError`, `InvalidNameError` |
| `LineCategorizer(repository, suggester).suggest(lines)` | `Suggestions`: normalized name → category id | `ModelUnavailableError` |
| `LineCategorizer.resolve(lines, suggestions)` | one `LineCategory` or `None` per line | |
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

OCR mix-ups and fuzzy matching (the rest of FR-14) are not handled; a later spec decides
them from real corrections (categorization spec, Out of Scope).

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
- A category used by products or receipt lines cannot be deleted (`category_in_use` with
  `product_count`, and `line_count` when lines use it), so no line loses its category; a
  group with categories cannot be deleted (`group_not_empty` with `category_count`).
- A category used by receipt lines cannot become a group either (`category_has_products`).
- The default list is created once, on the first start, and marked in `app_state`. Deleting
  defaults later does not bring them back.

## Line categorization

Each line stores a category, its **category source** and its product link
([datamodel](../../datamodel.md#receipt_lines)). Deposit refunds never get any of them
(FR-44). Why the model gets a separate call is in
[ADR 0004](../../adr/0004-line-categorization.md).

At import ([import data flow](../import/README.md#data-flow)):

| Step | Where | What |
|---|---|---|
| `suggest` | before the commit | Lines whose normalized name matches no product, each name once in first-seen order, go to `CategorySuggester.suggest(names, options)` in one call. No call when there are none, or when the catalog has no categories |
| `resolve` | inside the commit | Per line: a refund gets nothing; a matching product gives its category, `remembered`, linked; else a suggested category that still exists as a category gives `model`, not linked; else nothing |

`resolve` reads products and categories again in the commit's transaction, so a product or
category the user changed during the run cannot fail the image. A suggestion never creates a
product.

The model request (`ModelSuggester`) uses `ReceiptModel.generate`:

- The prompt is the instructions, the numbered options, then the numbered names. An option
  is `Ryhmä > Kategoria`, or the category alone without a group; groups are never options.
  The options come first, so the start of the prompt is the same on every receipt.
- The answer is `{"c": [n, ...]}`: one option number per name. The schema has `enum` 1…N and
  `minItems`/`maxItems` equal to the name count; `parse_answer` checks both again.
- A wrong answer, `ModelTimeoutError` or `ModelAnswerError` gives no suggestion for the
  call; a number outside the list gives none for its name. `ModelUnavailableError` passes
  through and stops the run.
- With `RRMC_ENGINES=fake`, `FakeSuggester` suggests the first option (`Auto > Autohuolto`
  with the default list) for every name.

A user correction (`LineCategoryService.set_category`), in one transaction. The two
repositories must share one connection, because the transaction is opened on the
catalog's:

1. The line must exist, the category must be a category, and the line must not be a deposit
   refund.
2. The product is the linked one, else the one with the line's normalized name, else a new
   product with the line's name (1–100 characters, else `InvalidNameError`).
3. If the product's category changes, the product and every line linked to it get the new
   category with source `remembered` (FR-36).
4. The corrected line gets the category, source `user`, and the link.

Only the corrected line is linked; other unlinked lines with the same name stay as they are.

## Data Flow

1. Start: the lifespan in @backend/app/main.py migrates, then calls `seed_defaults`.
2. Request: the route parses the body (shape errors become `invalid_request`), opens one
   connection for the request, and calls the service.
3. Service: inside one transaction, normalize and validate, check the rules against the
   current rows, write, then read back the item with its counts.

## Dependencies

- Uses: [storage](../storage/README.md) (`CatalogRepository`, `ReceiptRepository`,
  `transaction`), `ReceiptModel` from the engines package and `ReadLine` from
  [receipt-reading](../receipt-reading/README.md#interfaces), the shared error format
  (@backend/app/errors.py) and texts (@backend/app/texts.py).
- Used by: the API, [import](../import/README.md) (`LineCategorizer`, `create_suggester`),
  and later the review UI (`LineCategoryService`).

## Modules

None yet.

## Known Issues and Gotchas

- The services check every rule before writing, although the schema also has `UNIQUE`,
  `CHECK` and `RESTRICT`: the schema alone cannot tell a group from a category in another
  row, and it would give a 500 instead of the right code.
- Product names are personal purchase data. They are not logged; the request log leaves out
  bodies and query strings. The categorization errors name no line, product or category.
- `DepositRefundLineError` (`deposit_refund_line`, 422) has no endpoint yet; the review UI
  spec will expose it.

## Related Documents

- [Product management spec](../../../specs/features/product-management.md)
- [Categorization spec](../../../specs/features/categorization.md)
- [ADR 0004](../../adr/0004-line-categorization.md): remembered first, separate model call
- [datamodel.md](../../datamodel.md#categories): the catalog tables
- [api-reference.md](../../api-reference.md#catalog-groups-categories-and-products)
- [glossary.md](../../glossary.md)
