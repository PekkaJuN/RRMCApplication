# Review

Navigation: ↑ [Architecture](../../architecture.md) | → [API reference](../../api-reference.md#receipts) | → [Calculation](../calculation/README.md) | → [Categorization](../categorization/README.md) | → [Storage](../storage/README.md) | → [UI](../ui/README.md)

## Overview

Review serves the receipt endpoints the review UI uses: the receipt list, one receipt with
its lines and sums, the receipt image, line edits (name, amount, deposit refund flag,
category), added and deleted lines, the store, date and total, the review state, deleting a
receipt, and creating one by hand with an optional image from the failed folder (PRD
FR-16–FR-21, FR-18, FR-43, FR-46, FR-47). It builds what the UI shows from three subsystems and holds few rules of
its own (a reviewed receipt cannot be deleted; a deposit refund's amount sign):

- [storage](../storage/README.md) reads and writes the receipts, lines and review state;
- [calculation](../calculation/README.md) computes the line sum, the warning and the
  category subtotals;
- [categorization](../categorization/README.md#line-categorization) owns the product rules
  of a line: a user's category choice (FR-13, FR-36), a renamed line following its product
  (FR-43), and the category of a new line.

It is a separate package because the receipt view combines these and belongs to none of
them. Review owns the order of the steps of an edit, the checks of the edited values and the
transaction.

## Key Files and Entry Points

- @backend/app/review/routes.py — `create_review_router(settings, clock, failed_folder)`: the
  nine `/api/receipts` endpoints and the two `/api/failed-images` endpoints, one connection
  per request. `clock` and `failed_folder` are for tests (a fixed time, a failing move)
- @backend/app/review/service.py — `ReviewService`: `summaries`, `receipt`, `edit_line`,
  `add_line`, `delete_line`, `update_receipt`, `create_receipt`, `delete_receipt`, `image`;
  the input types `LineEdit`, `ReceiptEdit` and `NewReceipt`; the view types
  `ReceiptSummary`, `ReceiptView`, `LineView`, `SubtotalView`
- @backend/app/review/failed_images.py — `FailedFolder`: the failed images' names, a
  preview, and `take` and `move_to_done` for a new receipt's image (`TakenImage`)
- @backend/app/review/fields.py — `check_amount`, `check_total`, `check_store`, `check_date`:
  the edited values, no I/O
- @backend/app/review/images.py — `read_image(done_dir, file_name)`: the image file and its
  media type
- @backend/app/review/schemas.py — the API shapes; strict request bodies
- @backend/app/review/errors.py — `ImageMissingError` (404 `image_missing`),
  `InvalidAmountError`, `DepositRefundAmountError`, `InvalidDateError`, `InvalidStoreError`
  (422), and for receipt management `NoImageError`, `ReceiptReviewedError`,
  `ImageNotFoundError`, `UnsupportedFormatError`, `DuplicateImageError`,
  `ImageMoveFailedError`, `FoldersUnavailableError` (the import's code and text; review must
  not import from import)

## Interfaces

The endpoints, shapes and error codes are in the
[API reference](../../api-reference.md#receipts).

`ReviewService(catalog, receipts)` needs both repositories on one connection, because a
line edit runs `LineCategoryService` inside its own transaction on the catalog's connection.

| Method | Does | Raises |
|---|---|---|
| `summaries()` | Every receipt in list order with its warning | nothing |
| `receipt(id)` | The receipt, its lines with category and group names, line sum, difference, warning and subtotals | `NotFoundError` |
| `edit_line(id, line_id, LineEdit)` | Applies the sent fields to a line on the receipt ([line edits](#line-edits)); returns the receipt | `NotFoundError`, `InvalidNameError`, `InvalidAmountError`, `DepositRefundAmountError`, and the catalog errors of the category choice |
| `add_line(id, name, amount_cents, is_deposit_refund=...)` | Adds a line after the last one; a normal line gets its name match's category | `NotFoundError`, `InvalidNameError`, `InvalidAmountError`, `DepositRefundAmountError` |
| `delete_line(id, line_id)` | Deletes a line on the receipt; products and other positions stay | `NotFoundError` |
| `update_receipt(id, ReceiptEdit)` | Sets the sent store, date, total and review state; confirming is always allowed | `NotFoundError`, `InvalidStoreError`, `InvalidDateError`, `InvalidAmountError` |
| `create_receipt(NewReceipt, now, folder=None)` | Creates an unreviewed receipt without lines, with a failed image when one is named ([deleting and creating](#deleting-and-creating-a-receipt)) | `InvalidStoreError`, `InvalidDateError`, `InvalidAmountError`, `ImageNotFoundError`, `UnsupportedFormatError`, `DuplicateImageError`, `ImageMoveFailedError` |
| `delete_receipt(id)` | Deletes an unreviewed receipt and its lines | `NotFoundError`, `ReceiptReviewedError` |
| `image(id, done_dir)` | The image bytes and media type | `NotFoundError`, `NoImageError`, `ImageMissingError` |

Category and group names come from one read of `CategoryService.list()`, whose order is
also the order of the subtotals, so the view needs no join.

Every method that takes an id raises `NotFoundError` for an id outside SQLite's integer range
(`fits_integer`), and `edit_line` raises `UnknownCategoryError` for such a `category_id`;
SQLite would otherwise raise `OverflowError`, a 500. No edit changes the review state.

### Line edits

`edit_line` runs in one transaction on the catalog's connection; any error rolls it all back:

1. The line must be on the receipt.
2. The sent name is checked as a product name (`validate_product_name`) and the sent amount
   with `check_amount`. Values not sent are not checked, so a long name read from a receipt
   does not stop an amount edit.
3. The resulting refund flag and amount: a deposit refund must be negative
   (`DepositRefundAmountError`).
4. The line's category: none for a refund (FR-44); `LineCategoryService.resolve` for a line
   that stops being a refund; else `LineCategoryService.follow_name` (FR-43), which keeps the
   category when the normalized name did not change.
5. `update_line` writes the resulting name, amount, flag and category at once.
6. A sent `category_id` goes to `LineCategoryService.choose` on the written line, so a request
   with a new name and a category stores the category for the new name; a refund gives
   `DepositRefundLineError`.

`add_line` checks the same way, resolves a normal line by its name match and adds it at
`next_position`. `update_receipt` checks the sent fields with `fields.py` and writes them over
the stored ones. No edit calls the model: resolving uses the name match only (NFR-9).

### Image lookup

`read_image` uses only the stored `file_name`. It refuses a name that is not a plain file
name (`..`, a separator, an absolute path), a path that resolves anywhere but directly inside
the done folder (also through a link), a file it cannot read, and a file that starts with
neither the JPEG nor the PNG signature. Each gives `image_missing`. The media type comes from
the signature, not the name. The response has `Cache-Control: no-store`, so a replaced file
is not shown from the browser cache.

### Deleting and creating a receipt

`delete_receipt` refuses a reviewed receipt (`receipt_reviewed`) and deletes the row in one
transaction; the lines go with it (`ON DELETE CASCADE`). It never touches the image file.

`create_receipt` checks the store, date and total first, so a bad field never moves a file.
With an image it then follows the import's order: `FailedFolder.take` finds and reads the
file, checks its signature, hashes it and chooses the done name; a hash already stored is
`duplicate_image`. The row is committed (a `UNIQUE` failure, from an import that stored the
same image meanwhile, is also `duplicate_image`), then the file moves. If the move fails,
the row is deleted again and the answer is `image_move_failed`; the file is still in the
failed folder. If that delete fails too, only the error type is logged. The answer is also
`image_move_failed`, before any row exists, when the done folder cannot be listed.

`FailedFolder` accepts a plain name only: not `""`, `.` or `..`, no separator, a `.jpg`,
`.jpeg` or `.png` suffix, a regular file whose resolved path is directly in the failed
folder. The same check serves the preview (404) and a create (422).

## Data Flow

A line edit:

```mermaid
sequenceDiagram
  participant U as ReceiptPage
  participant R as review routes
  participant V as ReviewService
  participant L as LineCategoryService
  participant S as storage
  U->>R: PATCH /api/receipts/3/lines/11 {"name": "Kivennäisvesi"}
  R->>V: edit_line(3, 11, LineEdit(name=...))
  V->>S: BEGIN IMMEDIATE; get_line(11): on receipt 3?
  V->>V: check name, amount, refund flag
  V->>L: follow_name(line, "Kivennäisvesi")
  L->>S: product by key? else add_product
  V->>S: update_line(11, ...); COMMIT
  V->>S: receipt 3 and its lines; catalog list
  V->>V: check_receipt, category_subtotals
  R-->>U: 200 receipt view
```

## Dependencies

- Uses: [storage](../storage/README.md), [calculation](../calculation/README.md),
  [categorization](../categorization/README.md) (`CategoryService`, `LineCategoryService`,
  `NotFoundError`), the shared image file rules (@backend/app/image_files.py), the settings
  (the done and failed folders).
- Used by: [UI](../ui/README.md) through the API. No subsystem depends on review.

## Modules

None yet.

## Known Issues and Gotchas

- Request bodies use strict types and `extra="forbid"`, so `"12"` or `true` for a number,
  `"yes"` for a boolean and a misspelled field give `invalid_request` instead of being
  converted or ignored. A partial update refuses an empty body and a sent `null`, so `None`
  in `LineEdit` and `ReceiptEdit` always means "not sent".
- `edit_line` reads the line again after `update_line` before `choose`, because `choose`
  needs the line as written (its new name and link).

## Related Documents

- [Receipt review spec](../../../specs/features/receipt-review.md)
- [Line editing spec](../../../specs/features/line-editing.md)
- [Receipt management spec](../../../specs/features/receipt-management.md)
- [Data model](../../datamodel.md#receipts): the `reviewed` column; nullable `image_hash`
  and `file_name`
