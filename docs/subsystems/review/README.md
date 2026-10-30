# Review

Navigation: ↑ [Architecture](../../architecture.md) | → [API reference](../../api-reference.md#receipts) | → [Calculation](../calculation/README.md) | → [Categorization](../categorization/README.md) | → [Storage](../storage/README.md) | → [UI](../ui/README.md)

## Overview

Review serves the receipt endpoints the review UI uses: the receipt list, one receipt with
its lines and sums, the receipt image, a line's category choice and the review state
(PRD FR-16–FR-21). It builds what the UI shows from three subsystems and holds no rule of
its own beyond finding the right rows:

- [storage](../storage/README.md) reads the receipts, lines and review state;
- [calculation](../calculation/README.md) computes the line sum, the warning and the
  category subtotals;
- [categorization](../categorization/README.md#line-categorization) stores a user's category
  choice and remembers it for the product (FR-13, FR-36).

It is a separate package because the receipt view combines these and belongs to none of
them. Review does not edit lines, store, date or total: the line editing spec adds that.

## Key Files and Entry Points

- @backend/app/review/routes.py — `create_review_router(settings)`: the five `/api/receipts`
  endpoints, one connection per request
- @backend/app/review/service.py — `ReviewService`: `summaries`, `receipt`,
  `set_line_category`, `set_reviewed`, `image`; the view types `ReceiptSummary`,
  `ReceiptView`, `LineView`, `SubtotalView`
- @backend/app/review/images.py — `read_image(done_dir, file_name)`: the image file and its
  media type
- @backend/app/review/schemas.py — the API shapes; strict request bodies
- @backend/app/review/errors.py — `ImageMissingError` (404 `image_missing`)

## Interfaces

The endpoints, shapes and error codes are in the
[API reference](../../api-reference.md#receipts).

`ReviewService(catalog, receipts)` needs both repositories on one connection, because the
category choice runs `LineCategoryService` in one transaction on the catalog's connection.

| Method | Does | Raises |
|---|---|---|
| `summaries()` | Every receipt in list order with its warning | nothing |
| `receipt(id)` | The receipt, its lines with category and group names, line sum, difference, warning and subtotals | `NotFoundError` |
| `set_line_category(id, line_id, category_id)` | Checks the line is on the receipt, then `LineCategoryService.set_category`; returns the receipt | `NotFoundError`, and the catalog errors of the correction |
| `set_reviewed(id, reviewed=...)` | Sets the review state; always allowed | `NotFoundError` |
| `image(id, done_dir)` | The image bytes and media type | `NotFoundError`, `ImageMissingError` |

Category and group names come from one read of `CategoryService.list()`, whose order is
also the order of the subtotals, so the view needs no join.

### Image lookup

`read_image` uses only the stored `file_name`. It refuses a name that is not a plain file
name (`..`, a separator, an absolute path), a path that resolves anywhere but directly inside
the done folder (also through a link), a file it cannot read, and a file that starts with
neither the JPEG nor the PNG signature. Each gives `image_missing`. The media type comes from
the signature, not the name. The response has `Cache-Control: no-store`, so a replaced file
is not shown from the browser cache.

## Data Flow

A category choice:

```mermaid
sequenceDiagram
  participant U as ReceiptPage
  participant R as review routes
  participant V as ReviewService
  participant L as LineCategoryService
  participant S as storage
  U->>R: PATCH /api/receipts/3/lines/11 {"category_id": 12}
  R->>V: set_line_category(3, 11, 12)
  V->>S: get_line(11): exists, on receipt 3?
  V->>L: set_category(11, 12): one transaction, FR-13 and FR-36
  V->>S: receipt 3 and its lines; catalog list
  V->>V: check_receipt, category_subtotals
  R-->>U: 200 receipt view
```

## Dependencies

- Uses: [storage](../storage/README.md), [calculation](../calculation/README.md),
  [categorization](../categorization/README.md) (`CategoryService`, `LineCategoryService`,
  `NotFoundError`), the settings (the done folder).
- Used by: [UI](../ui/README.md) through the API. No subsystem depends on review.

## Modules

None yet.

## Known Issues and Gotchas

- The JPEG and PNG signatures are written in both @backend/app/review/images.py and
  @backend/app/receipt_import/files.py: review must not import from import.
- Request bodies use `StrictInt` and `StrictBool`, so `"12"` or `true` for a category id and
  `"yes"` for `reviewed` give `invalid_request` instead of being converted.

## Related Documents

- [Receipt review spec](../../../specs/features/receipt-review.md)
- [Data model](../../datamodel.md#receipts): the `reviewed` column
