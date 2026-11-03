# Feature: Receipt deletion and manual receipts

## Overview
- **Status:** Review
- **Created:** 2026-11-02
- **Updated:** 2026-11-02: user answers: a deleted receipt's image stays in the done folder;
  a manual receipt is created with a small form (store, date, total) and its lines are added
  on the receipt page; only an unreviewed receipt can be deleted. Second round: a manual
  receipt may have an image, chosen from the failed folder, only when it is created.
  Decided by the agent for review: the form shows a preview of the chosen image (file names
  such as `IMG_1234.jpg` do not tell receipts apart); the preview's file name goes in the
  query string, which is never logged.
- **Depends on:** [Receipt review](receipt-review.md), [Line editing](line-editing.md),
  [Receipt import](receipt-import.md)
- **Implements:** new PRD FR-46 (delete a receipt) and FR-47 (create a receipt by hand,
  optionally with an image from the failed folder); NFR-1, NFR-3, NFR-7, NFR-15 for both.
- **Affected subsystems:** [review](../../docs/subsystems/review/README.md),
  [storage](../../docs/subsystems/storage/README.md),
  [import](../../docs/subsystems/import/README.md) (the failed folder, duplicate check, the
  free name in the done folder), [ui](../../docs/subsystems/ui/README.md)

## Problem Statement
Two gaps block the user today:

1. A receipt that was imported by mistake, or read so badly that fixing it line by line is
   not worth it, cannot be removed. It stays in the receipt list and in the totals.
2. When an import fails (a blurred photo, a long receipt, a model error), the purchase never
   gets into the app. The image lies in the failed folder, and the user has no way to type
   the receipt in, so the totals miss it.

## Current Behavior
- A receipt row exists only for an imported image. `image_hash` and `file_name` are
  `NOT NULL`, and `image_hash` is `UNIQUE` and is the duplicate lookup
  ([datamodel](../../docs/datamodel.md#receipts), [import](../../docs/subsystems/import/README.md)).
- A failed import moves the image to the failed folder and stores nothing; the user can move
  it back to the import folder to retry ([import](../../docs/subsystems/import/README.md)).
- An imported image moves to the done folder only after its receipt is committed. Its name
  there gets the first free numbered suffix (`kuitti (2).jpg`) when the name is taken; if the
  move fails, the row is deleted again.
- The receipt endpoints read and edit a receipt, and add, edit and delete its lines. There
  is no endpoint to create or delete a receipt
  ([API reference](../../docs/api-reference.md#receipts)). Deleting a whole receipt is out
  of scope in the [line editing spec](line-editing.md#out-of-scope).
- Deleting a receipt row in SQL deletes its lines (`ON DELETE CASCADE`).
- The receipt page shows the image beside the lines. A missing file shows
  `Kuvaa ei löydy valmiiden kansiosta.` ([ui](../../docs/subsystems/ui/README.md)).
- Requests are logged with method, path, status and duration; query strings and bodies are
  never logged ([API reference](../../docs/api-reference.md#overview)).

## Proposed Change

### Concepts

- A **manual receipt** (käsin luotu kuitti) is a receipt the user creates in the UI instead
  of an import. It has no OCR text. It may have an image from the failed folder (then
  `image_hash` and `file_name` are set as for an imported receipt) or none (both `NULL`).
  Everything else works as for an imported receipt: lines, categories, sums, warning,
  review state, deletion, totals and export.
- A **failed image** is a file directly in the failed folder whose name ends in `.jpg`,
  `.jpeg` or `.png` (any case).

### Parts

- **PC1 Delete a receipt (FR-46).** `DELETE /api/receipts/{id}` deletes an unreviewed
  receipt and its lines in one transaction and answers 204. Products, categories and
  remembered categories are not changed. A reviewed receipt is refused with 409
  `receipt_reviewed`; the user must first make it unreviewed. An unknown or out-of-range id
  gives 404 `not_found`. Imported and manual receipts are deleted the same way.
- **PC2 The image stays.** Deleting a receipt does not touch its file in the done folder.
  Because the row and its `image_hash` are gone, the same image is no longer a duplicate: if
  the user moves it back to the import folder, the next run imports it as a new receipt.
- **PC3 Create a manual receipt (FR-47).** `POST /api/receipts` with `store`,
  `purchase_date`, `total_cents` and optionally `image_file_name` creates a manual receipt
  without lines and answers 201 with the receipt. The fields follow the rules of
  line-editing PC8: `store` 0–100 characters in display form (`""` is no store),
  `purchase_date` a real date as `YYYY-MM-DD`, `total_cents` 0 to 99 999 999. The first
  three fields are required. The body is strict as in line-editing PC10 (`null` for
  `image_file_name` is `invalid_request`; leave it out for no image). `imported_at` is the
  creation time (UTC, seconds), so the receipt sorts in the list as a receipt imported at
  that moment. The receipt is unreviewed. The fields are checked before any file is touched.
- **PC4 Image of a new manual receipt (FR-47, NFR-7).** With `image_file_name`:
  1. The name must be a failed image (a plain file name, no path, the file directly in the
     failed folder); else 422 `image_not_found`.
  2. The file must start with the JPEG or PNG signature (as in import); else 422
     `unsupported_format`.
  3. Its SHA-256 must not be any receipt's `image_hash`; else 409 `duplicate_image`.
  4. Its name in the done folder is chosen as in import (the same name, or the first free
     numbered suffix).
  5. The receipt row is committed with the hash and that name.
  6. The file moves from the failed folder to the done folder. If the move fails, the row is
     deleted again, the file stays in the failed folder, and the answer is 503
     `image_move_failed`.

  On any error no receipt exists afterwards and the file is still in the failed folder.
  The image is not read by OCR or the model.
- **PC5 Lines of a manual receipt.** The existing line endpoints work on a manual receipt
  unchanged (line-editing PC1–PC7): an added normal line is resolved by its name match, and
  no model is called.
- **PC6 No image.** `GET /api/receipts/{id}/image` for a receipt without an image gives 404
  `no_image`. The receipt view has `file_name` `null` for it.
- **PC7 Failed images list.** `GET /api/failed-images` answers 200 with the failed images'
  names, sorted by name case-insensitively: `{"file_names": ["a.png", "IMG_2.jpg"]}`. Other
  files and folders are left out. A missing or unreadable failed folder gives 503
  `folders_unavailable`.
- **PC8 Failed image preview.** `GET /api/failed-images/image?name=<file name>` answers 200
  with the image bytes as `image/jpeg` or `image/png` (from the signature) and
  `Cache-Control: no-store`. A name that is not a failed image, a path, a file that cannot be
  read or that has neither signature gives 404 `image_not_found`. The name is a query
  parameter so it never reaches the request log.
- **PC9 Schema.** A new migration lets `image_hash` and `file_name` be `NULL`, both or
  neither (`CHECK`). `image_hash` stays `UNIQUE` (SQLite allows many `NULL`s) and keeps its
  length check when set. Existing receipts and lines keep their ids and all their values.
- **PC10 Delete on the receipt page.** An unreviewed receipt's page shows a `Poista kuitti`
  button next to the review button, with the confirmation in place (`ConfirmDelete`, as for
  lines). After a successful delete the receipt list opens. A reviewed receipt's page shows
  no delete button. A failed delete keeps the page and shows the backend's `message` (or the
  network message) next to the button with `role="alert"`.
- **PC11 New receipt form on the receipt list.** The Kuitit page has a `Uusi kuitti` button
  above the list. It opens a form with `Kauppa`, `Päivä` (date input), `Loppusumma`, `Kuva`
  (a select) and the buttons `Luo kuitti` and `Peruuta`. `Peruuta` closes the form without
  sending.
  - When the form opens, it loads `GET /api/failed-images`. The `Kuva` select has the first
    option `Ei kuvaa` (selected) and then one option per failed image. While the list loads
    or after it failed, only `Ei kuvaa` is offered; a failed load shows the backend's
    `message` (or the network message) with `role="alert"`, and the receipt can still be
    created without an image.
  - Choosing an image shows its preview (`<img>` with `alt` `Valittu kuva`) from PC8 below
    the select; `Ei kuvaa` hides it. A preview that does not load shows
    `Kuvaa ei voitu näyttää.` instead.
  - The total is read as in line-editing PC13. An empty or unreadable total is not sent and
    shows `Anna summa muodossa 1,25.`; an empty date is not sent and shows
    `Anna päivämäärä.`; both with `role="alert"`.
  - `image_file_name` is sent only when an image is chosen.
  - After a 201 the new receipt's page opens.
  - A failed create keeps the form and its values and shows the backend's `message` (or
    the network message) with `role="alert"`.
- **PC12 Manual receipt page.** A receipt without an image shows
  `Ei kuvaa.` in the image column and the page does not request the image. A manual receipt
  with an image shows it as an imported receipt does.
- **PC13 Privacy (NFR-1, NFR-3).** As today: logs carry method, path and status only; error
  messages hold no receipt content and no file names; a deleted receipt's data is not
  logged. Failed images are served only to the local UI.

### UI texts

| Place | Text |
|---|---|
| Receipt page delete button and confirmation | `Poista kuitti`, then `Poistetaanko?` with `Poista` and `Peruuta` |
| Receipt page image column, receipt without an image | `Ei kuvaa.` |
| Receipt list button | `Uusi kuitti` |
| New receipt form heading | `Uusi kuitti` |
| New receipt form inputs (`<label>`) | `Kauppa`, `Päivä`, `Loppusumma`, `Kuva` |
| `Kuva` select, first option | `Ei kuvaa` |
| Preview `alt` | `Valittu kuva` |
| Preview that does not load | `Kuvaa ei voitu näyttää.` |
| New receipt form buttons | `Luo kuitti`, `Peruuta` |
| Empty date in the form | `Anna päivämäärä.` |
| Empty or unreadable total in the form | `Anna summa muodossa 1,25.` (as today) |

### API shapes

New receipt (PC3); `image_file_name` optional:

```json
{"store": "Testikauppa", "purchase_date": "2026-10-05", "total_cents": 349, "image_file_name": "IMG_2.jpg"}
```

The answer is the receipt of the receipt-review spec with `lines` `[]`, and `file_name`
the name in the done folder, or `null` without an image.

Failed images (PC7):

```json
{"file_names": ["a.png", "IMG_2.jpg"]}
```

### Error codes

| Status | `error` | `message` | When |
|---|---|---|---|
| 404 | `not_found` | `Pyydettyä kohdetta ei löydy.` | Unknown or out-of-range receipt id (PC1, PC6) |
| 409 | `receipt_reviewed` (new) | `Vahvistettua kuittia ei voi poistaa. Peru vahvistus ensin.` | Delete of a reviewed receipt (PC1) |
| 404 | `no_image` (new) | `Kuitilla ei ole kuvaa.` | Image of a receipt without one (PC6) |
| 422 / 404 | `image_not_found` (new) | `Kuvaa ei löydy epäonnistuneiden kansiosta.` | 422 for a create (PC4 step 1), 404 for a preview (PC8) |
| 422 | `unsupported_format` (new for receipts) | `Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa.` | PC4 step 2 |
| 409 | `duplicate_image` (new) | `Kuva on jo tuotu toiseen kuittiin.` | PC4 step 3 |
| 503 | `image_move_failed` (new) | `Kuvaa ei voitu siirtää valmiiden kansioon. Kuittia ei luotu.` | PC4 step 6, or the done name cannot be chosen (step 4) |
| 503 | `folders_unavailable` | as in import | PC7 |
| 422 | `invalid_store`, `invalid_date`, `invalid_amount` | as today | PC3 field rules |
| 422 | `invalid_request` | `Pyyntö on virheellinen.` | PC3 body not strict-valid, or a required field missing |

### Out of Scope
- Deleting a reviewed receipt directly (the user makes it unreviewed first).
- Deleting, moving or restoring the image file of a deleted receipt; undo of a deletion.
- Deleting several receipts at once.
- Attaching, changing or removing the image of an existing receipt; an image from anywhere
  but the failed folder (no upload).
- Reading the chosen image with OCR or the model.
- Creating a receipt with its lines in one request; lines are added on the receipt page.
- A duplicate check for manual receipts without an image (content-based duplicates, see
  Domain rules).
- Marking manual receipts in the receipt list, totals or export: they look like any other
  receipt there.
- Removing files from the failed folder in the UI.

## Acceptance Criteria

The examples use the default catalog and a product `Maito` in `Maitotuotteet` (group
`Ruoka`). Receipt A is imported from `a.jpg` (hash H), unreviewed, store `Testikauppa`, date
2026-10-05, total 349, lines `Maito` 125 (linked to `Maito`) and `Limu` 224 (`Juomat`).
Receipt R is like A but reviewed. The failed folder F holds `b.png` and `IMG_2.jpg` (two
synthetic images whose hashes no receipt has), `notes.txt`, `fake.jpg` (text bytes) and a
folder `sub`. "Nothing changes" means every receipt, line and product reads back the same as
before, and every file is where it was.

### AC1: Delete an unreviewed receipt
**Given** receipt A and receipt R
**When** the client calls `DELETE /api/receipts/<A>`
**Then** the status is 204 with no body; `GET /api/receipts/<A>` is 404 `not_found`;
`GET /api/receipts` lists R only; no `receipt_lines` row has A's id; the product `Maito`
still exists in `Maitotuotteet`; R and its lines are unchanged

### AC2: Deletion changes the totals
**Given** receipts A and R, both dated in 2026-W41
**When** A is deleted and the client calls `GET /api/totals?unit=week&from=2026-W41&to=2026-W41`
**Then** the totals hold R's lines only and `unreviewed_receipts` is 0

### AC3: A reviewed receipt cannot be deleted
**Given** receipt R
**When** the client calls `DELETE /api/receipts/<R>`
**Then** the status is 409 with `error` `receipt_reviewed` and the message
`Vahvistettua kuittia ei voi poistaa. Peru vahvistus ensin.`; nothing changes

### AC4: Delete after cancelling the confirmation
**Given** receipt R
**When** the client sends `PATCH /api/receipts/<R>` with `{"reviewed": false}`, then
`DELETE /api/receipts/<R>`
**Then** the statuses are 200 and 204, and R no longer exists

### AC5: Unknown receipt
**Given** no receipt with id 999
**When** the client calls `DELETE /api/receipts/999` and `DELETE /api/receipts/9223372036854775808`
**Then** both statuses are 404 with `error` `not_found`; nothing changes

### AC6: The image stays and can be imported again
**Given** receipt A, whose file `a.jpg` is in the done folder
**When** A is deleted, `a.jpg` is copied to the import folder and an import run finishes
**Then** the done folder still had `a.jpg` after the delete; the run reports `imported` 1
and `duplicates` `[]`; a new receipt with hash H exists, with a new id

### AC7: Create a manual receipt without an image
**Given** the time 2026-11-02T10:00:00Z
**When** the client calls `POST /api/receipts` with
`{"store": "  Testi   kauppa ", "purchase_date": "2026-10-05", "total_cents": 349}`
**Then** the status is 201; the receipt has `store` `Testi kauppa`, `purchase_date`
`2026-10-05`, `total_cents` 349, `file_name` `null`, `imported_at`
`2026-11-02T10:00:00Z`, `reviewed` false, `lines` `[]`, `line_sum_cents` 0,
`difference_cents` 349, `warning` true; the row has `image_hash` `NULL` and `ocr_text`
`NULL`

### AC8: Store may be empty, total may be 0
**When** the client calls `POST /api/receipts` with
`{"store": "", "purchase_date": "2026-10-05", "total_cents": 0}`
**Then** the status is 201 with `store` `""`, `total_cents` 0 and `warning` false

### AC9: Invalid fields
**Given** folder F
**When** the client sends, one at a time with `"image_file_name": "b.png"`, a store of 101
characters, `purchase_date` `2026-02-30`, `purchase_date` `5.10.2026`, `total_cents` -1
and `total_cents` 100000000
**Then** the statuses are 422 with `error` `invalid_store`, `invalid_date`, `invalid_date`,
`invalid_amount` and `invalid_amount`; nothing changes (`b.png` is still in F)

### AC10: Strict body
**When** the client sends `{}`, a body without `total_cents`, `"total_cents": "349"`,
`"total_cents": null`, `"image_file_name": null`, `"image_file_name": 5`, an extra field
`"reviewed": true`, and a body that is not JSON
**Then** each status is 422 with `error` `invalid_request`; no receipt is created

### AC11: Lines on a manual receipt
**Given** a manual receipt M with total 349
**When** the client adds `Maito` 125 and `Limu` 224 with `POST /api/receipts/<M>/lines`
**Then** both answers are 201; `Maito` has `Maitotuotteet`, source `remembered`, linked to
`Maito`; `Limu` has no category; `line_sum_cents` is 349 and `warning` false; the model was
not called

### AC12: A manual receipt is counted like any other
**Given** M from AC11 dated 2026-10-05, then confirmed with `{"reviewed": true}`
**When** the client calls `GET /api/totals?unit=month&from=2026-10&to=2026-10` and
`GET /api/export/lines?unit=month&from=2026-10&to=2026-10`
**Then** the totals hold `Maitotuotteet` 125 and the no-category row 224; the lines file has
two rows for M with `Kuitin tila` `Vahvistettu`

### AC13: No image for a receipt without one
**Given** manual receipt M without an image
**When** the client calls `GET /api/receipts/<M>/image`
**Then** the status is 404 with `error` `no_image` and the message `Kuitilla ei ole kuvaa.`

### AC14: Manual receipts without an image are not duplicates of each other
**Given** manual receipt M without an image
**When** the client creates a second receipt with the same body
**Then** the status is 201 and the list holds both receipts

### AC15: Migration keeps existing data
**Given** a database at schema version 5 with receipt A (imported, with OCR text), its
lines with their categories, sources and product links, and receipt R
**When** the migrations run
**Then** the schema version is 6; A and R and every line read back with the same ids and
values; `PRAGMA foreign_key_check` returns no rows; inserting a receipt with `image_hash`
set and `file_name` `NULL` (or the other way round) fails with a constraint error; inserting
a second receipt with hash H fails with a constraint error

### AC16: Failed images list
**Given** folder F
**When** the client calls `GET /api/failed-images`
**Then** the status is 200 with `{"file_names": ["b.png", "fake.jpg", "IMG_2.jpg"]}`

### AC17: Empty or missing failed folder
**Given** an empty failed folder, and then no failed folder
**When** the client calls `GET /api/failed-images` each time
**Then** the first answer is 200 with `{"file_names": []}`; the second is 503 with `error`
`folders_unavailable`

### AC18: Failed image preview
**Given** folder F
**When** the client calls `GET /api/failed-images/image?name=b.png`
**Then** the status is 200, `Content-Type` `image/png`, `Cache-Control` `no-store`, and the
body is the bytes of `b.png`; the backend log line for the request holds the path
`/api/failed-images/image` and not `b.png`

### AC19: Preview refused
**Given** folder F, and `a.jpg` in the done folder
**When** the client asks for the preview of `fake.jpg`, `notes.txt`, `missing.png`,
`../import_done/a.jpg`, `sub`, and with no `name`
**Then** the first five are 404 with `error` `image_not_found` and the message
`Kuvaa ei löydy epäonnistuneiden kansiosta.`; without `name` the status is 422
`invalid_request`

### AC20: Create a manual receipt with an image
**Given** folder F, an empty done folder and the time 2026-11-02T10:00:00Z
**When** the client calls `POST /api/receipts` with
`{"store": "Testikauppa", "purchase_date": "2026-10-05", "total_cents": 349, "image_file_name": "IMG_2.jpg"}`
**Then** the status is 201 with `file_name` `IMG_2.jpg`; the row's `image_hash` is the
SHA-256 of the file; `IMG_2.jpg` is in the done folder with the same bytes and no longer in
F; `GET /api/receipts/<id>/image` answers 200 with those bytes; `GET /api/failed-images`
no longer lists it; OCR and the model were not called

### AC21: The done name gets a free suffix
**Given** folder F and a file `b.png` already in the done folder
**When** the client creates a receipt with `"image_file_name": "b.png"`
**Then** the status is 201 with `file_name` `b (2).png`; the done folder holds both files

### AC22: Image already in a receipt
**Given** receipt A with hash H, and a copy of `a.jpg` in F named `copy.jpg`
**When** the client creates a receipt with `"image_file_name": "copy.jpg"`
**Then** the status is 409 with `error` `duplicate_image` and the message
`Kuva on jo tuotu toiseen kuittiin.`; nothing changes

### AC23: Image that cannot be used
**Given** folder F
**When** the client creates a receipt with `"image_file_name"` `missing.png`,
`../import_done/a.jpg`, `sub`, `notes.txt`, and then `fake.jpg`
**Then** the first four are 422 `image_not_found`, the last is 422 `unsupported_format` with
the message `Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa.`; nothing changes

### AC24: Move to the done folder fails
**Given** folder F, and a done folder the backend cannot write to
**When** the client creates a receipt with `"image_file_name": "b.png"`
**Then** the status is 503 with `error` `image_move_failed` and the message
`Kuvaa ei voitu siirtää valmiiden kansioon. Kuittia ei luotu.`; no receipt exists; `b.png`
is still in F

### AC25: Delete on the receipt page
**Given** the receipt page of A
**When** the user clicks `Poista kuitti`, then `Poista`
**Then** the client sent `DELETE /api/receipts/<A>`; the address is `/kuitit` and the list
does not show A

### AC26: Cancel the delete
**Given** the receipt page of A
**When** the user clicks `Poista kuitti`, then `Peruuta`
**Then** no request was sent and the page still shows A with the `Poista kuitti` button

### AC27: No delete button on a reviewed receipt
**Given** the receipt page of R
**Then** there is no `Poista kuitti` button; after the user clicks `Peru vahvistus` and the
answer arrives, the button is shown

### AC28: Failed delete
**Given** the receipt page of A, and the backend answers the delete with 409
`receipt_reviewed` (or the network fails)
**When** the user confirms the delete
**Then** the page stays on A and shows `Vahvistettua kuittia ei voi poistaa. Peru vahvistus
ensin.` (or the network message) with `role="alert"`

### AC29: Create a manual receipt in the UI without an image
**Given** the Kuitit page
**When** the user clicks `Uusi kuitti`, types `Testikauppa`, chooses 2026-10-05, types
`3,49`, leaves `Kuva` at `Ei kuvaa` and clicks `Luo kuitti`
**Then** the client sent `POST /api/receipts` with
`{"store": "Testikauppa", "purchase_date": "2026-10-05", "total_cents": 349}`; the address
is `/kuitit/<new id>`; the page shows `Ei kuvaa.`, no `<img>`, and no request was made to
`/api/receipts/<new id>/image`

### AC30: Choose an image in the UI
**Given** the Kuitit page and folder F
**When** the user opens the form, chooses `IMG_2.jpg` in `Kuva`, fills the other fields as
in AC29 and clicks `Luo kuitti`
**Then** the select offered `Ei kuvaa`, `b.png`, `fake.jpg`, `IMG_2.jpg` in this order; after
the choice an `<img>` with `alt` `Valittu kuva` and `src`
`/api/failed-images/image?name=IMG_2.jpg` was shown; the request body had
`"image_file_name": "IMG_2.jpg"`; the receipt page shows the image `Kuitin kuva`

### AC31: Preview and list errors in the form
**Given** the open form
**When** the preview of the chosen image fails to load; and, in a second case, the list
request fails with 503 `folders_unavailable`
**Then** the first shows `Kuvaa ei voitu näyttää.` instead of the image; the second shows
`Kuvakansioita ei löydy tai niihin ei voi kirjoittaa.` with `role="alert"`, the select
offers only `Ei kuvaa`, and a receipt without an image can still be created

### AC32: Form checks before sending
**Given** the open new receipt form
**When** the user clicks `Luo kuitti` with an empty date and the total `abc`
**Then** nothing is sent; `Anna päivämäärä.` and `Anna summa muodossa 1,25.` are shown with
`role="alert"`

### AC33: Failed create
**Given** the open form with valid values and `IMG_2.jpg` chosen, and the backend answers
409 `duplicate_image` (or the network fails)
**When** the user clicks `Luo kuitti`
**Then** the form stays open with the typed values and the chosen image and shows
`Kuva on jo tuotu toiseen kuittiin.` (or the network message) with `role="alert"`

### AC34: Cancel the form
**Given** the open form with typed values and a chosen image
**When** the user clicks `Peruuta`
**Then** the form closes, nothing is sent, and `Uusi kuitti` opens an empty form with
`Ei kuvaa` again

### AC35: Accessibility
**Given** the Kuitit page with the form open and an image chosen, and the receipt page of a
manual receipt without an image
**When** axe runs on both pages (as in the styling spec)
**Then** it reports no WCAG 2.1 AA violations

## Files to Modify
| File | Change |
|---|---|
| `backend/app/storage/migrations/0006_manual_receipts.sql` | New: `image_hash` and `file_name` nullable, both or neither (PC9) |
| `backend/app/storage/migrate.py` | Possibly: a table rebuild must not cascade-delete lines (see Risk); decided in Plan |
| `backend/app/storage/receipt_repository.py` | Create a manual receipt, delete a receipt; nullable `image_hash`, `file_name` |
| `backend/app/review/service.py` | `create_receipt`, `delete_receipt`; `image` raises `NoImageError` |
| `backend/app/review/routes.py`, `schemas.py`, `errors.py` | `POST /api/receipts`, `DELETE /api/receipts/{id}`; new codes; nullable `file_name` |
| `backend/app/review/images.py` or a shared module | Failed-folder lookup and preview; the image signatures and the free done name, which today live in import (see the review README gotcha); placement decided in Plan |
| `backend/app/receipt_import/...` | Possibly: move the free-name and signature helpers to the shared module; decided in Plan |
| New failed-images routes (package decided in Plan) | `GET /api/failed-images`, `GET /api/failed-images/image` |
| `backend/app/texts.py` | The new messages |
| `backend/tests/...` | Unit and integration tests below |
| `frontend/src/api/receipts.ts` | `createReceipt`, `deleteReceipt`, `failedImages`, `failedImageUrl`; `file_name: string \| null` |
| `frontend/src/components/ReceiptPage.tsx` | Delete button (PC10), image column without an image (PC12) |
| `frontend/src/components/ReceiptsPage.tsx`, new `NewReceiptForm.tsx` | `Uusi kuitti` form (PC11) |
| `frontend/src/components/ConfirmDelete.tsx` | A label prop for `Poista kuitti` |
| `frontend/src/i18n/fi.ts` | New texts |
| `frontend/src/styles.css` | The preview's size in the form, if needed |
| `frontend/src/**/*.test.tsx`, `frontend/e2e/` | Tests below |
| `specs/PRD.md` | New FR-46 and FR-47 |
| `specs/README.md` | This spec's row |
| `docs/api-reference.md` | New endpoints, codes, nullable `file_name` |
| `docs/datamodel.md` | `receipts` columns, migration 0006 |
| `docs/subsystems/review/README.md` | New service methods and endpoints |
| `docs/subsystems/import/README.md` | A deleted receipt's image is no longer a duplicate; a failed image can leave the failed folder through a manual receipt |
| `docs/subsystems/ui/README.md` | Delete button, new receipt form, image column without an image |
| `docs/development.md` | How to copy the database out of the volume before the upgrade |
| `docs/glossary.md` | Manual receipt (käsin luotu kuitti), failed image |

## Risk
- **What could break:**
  - The migration rebuilds the `receipts` table (SQLite cannot drop `NOT NULL` in place).
    With foreign keys on, `DROP TABLE receipts` runs an implicit delete that would
    **cascade-delete every receipt line**. The Plan must prove the migration keeps the lines
    (AC15 with real-shaped synthetic data), for example by turning foreign keys off around
    this migration.
  - Code that assumes `file_name` is a string (image lookup, UI) fails for a receipt
    without an image.
  - A file moved between folders can be lost or end up in two places if the commit and the
    move are ordered wrong. PC4 follows import's order (commit, then move, delete the row if
    the move fails), and AC20, AC24 check both ends.
  - An import run and a manual create may handle the same image at once; the `UNIQUE`
    index on `image_hash` refuses the second (`duplicate_image`).
  - Serving files from the failed folder opens a path from the request to the disk. PC8
    accepts plain names only and checks that the resolved path is directly in the folder
    (AC19).
  - A delete is permanent; a wrong click loses the receipt's lines and the category choices
    on them (products and remembered categories stay). The in-place confirmation and the
    reviewed-receipt block limit this.
- **Rollback:** the migration is forward-only. Before the upgrade, copy the database out of
  the volume (the command goes in `docs/development.md`); to roll back, restore the copy and
  run the previous image. A manual receipt's image moved to the done folder can be moved
  back by hand.
- **Dependencies:** none new. Tesseract and Ollama are not used by these endpoints.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | `ReviewService.delete_receipt` | happy path | A, R | delete A | A and its lines gone; R, products unchanged | none (temp SQLite) |
| AC3 | `ReviewService.delete_receipt` | reviewed | R | delete R | `ReceiptReviewedError`; nothing changes | none |
| AC5 | `ReviewService.delete_receipt` | unknown, out of range | — | 999, 2^63 | `NotFoundError` | none |
| AC7 | `create_receipt` | happy path, no image | fixed clock | store with extra spaces | display-form store, `NULL` hash, name and OCR text, unreviewed | clock |
| AC8 | `create_receipt` | edge | — | `""`, total 0 | created | clock |
| AC9 | `create_receipt` | invalid fields with an image | F | each bad value | the matching error; file not moved | clock, temp folders |
| AC13 | `ReviewService.image` | no image | M | image(M) | `NoImageError` | none |
| AC15 | `migrate` | data kept | version 5 with A, R, lines | migrate | version 6, same rows, FK check empty, both-or-neither and unique checks | none |
| AC16 | failed images list | names | F | list | `b.png`, `fake.jpg`, `IMG_2.jpg` | temp folder |
| AC17 | failed images list | empty, missing | — | list | `[]`; `FoldersUnavailableError` | temp folder |
| AC19 | failed image preview | refused names | F | each name | `ImageNotFoundError` | temp folder |
| AC20 | `create_receipt` | with image | F, empty done | `IMG_2.jpg` | row with hash, file moved | clock, temp folders |
| AC21 | `create_receipt` | free name | `b.png` in done | `b.png` | `b (2).png` | temp folders |
| AC22 | `create_receipt` | duplicate | A, `copy.jpg` | create | `DuplicateImageError`; nothing changes | temp folders |
| AC23 | `create_receipt` | unusable image | F | each name | `ImageNotFoundError`, `UnsupportedFormatError` | temp folders |
| AC24 | `create_receipt` | move fails | read-only done | `b.png` | `ImageMoveFailedError`; no row; file in F | move raises `OSError` |
| AC26 | `ReceiptPage` | cancel delete | A | `Poista kuitti`, `Peruuta` | no fetch | fetch |
| AC27 | `ReceiptPage` | reviewed | R | render, then unconfirm | no button, then button | fetch |
| AC28 | `ReceiptPage` | failed delete | 409, network error | confirm | alert, stays | fetch |
| AC30 | `NewReceiptForm` | image options and preview | list of three | choose `IMG_2.jpg` | options in order; preview `src` | fetch |
| AC31 | `NewReceiptForm` | preview and list errors | preview error; 503 | — | texts; only `Ei kuvaa` | fetch |
| AC32 | `NewReceiptForm` | client checks | open form | empty date, `abc` | two alerts, no fetch | fetch |
| AC33 | `NewReceiptForm` | failed create | 409, network error | submit | alert, values and image kept | fetch |
| AC34 | `NewReceiptForm` | cancel | typed values, image | `Peruuta` | closed, no fetch, empty on reopen | fetch |

### Integration tests
Real SQLite (temporary file), real temporary folders and real FastAPI app; Tesseract and
Ollama fake.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | delete | `DELETE /api/receipts/<A>` | no body; A 404; list R only | 204 |
| AC2 | totals after delete | `GET /api/totals` week | R only, `unreviewed_receipts` 0 | 200 |
| AC3 | reviewed | `DELETE /api/receipts/<R>` | `receipt_reviewed` | 409 |
| AC4 | unconfirm then delete | `PATCH`, `DELETE` | R gone | 200, 204 |
| AC5 | unknown ids | `DELETE /api/receipts/999`, `/9223372036854775808` | `not_found` | 404 |
| AC6 | re-import | delete, copy `a.jpg` to import, `POST /api/import` | done file kept; `imported` 1, no duplicates | 204, 202 |
| AC7 | create without image | `POST /api/receipts` | the receipt as in AC7 | 201 |
| AC8 | empty store, 0 total | `POST /api/receipts` | `warning` false | 201 |
| AC9 | invalid fields | five bodies with an image | the five codes; file in F | 422 |
| AC10 | strict body | eight bodies | `invalid_request` | 422 |
| AC11 | add lines | two `POST .../lines` | categories, sums; fake model call count 0 | 201 |
| AC12 | totals and export | `GET /api/totals`, `GET /api/export/lines` | M counted | 200 |
| AC13 | image | `GET /api/receipts/<M>/image` | `no_image` | 404 |
| AC14 | same body twice | `POST /api/receipts` ×2 | two receipts | 201 |
| AC16 | list | `GET /api/failed-images` | three names | 200 |
| AC17 | empty, missing folder | `GET /api/failed-images` | `[]`; `folders_unavailable` | 200, 503 |
| AC18 | preview | `GET /api/failed-images/image?name=b.png` | bytes, headers; log line without the name | 200 |
| AC19 | preview refused | six requests | `image_not_found`; `invalid_request` | 404, 422 |
| AC20 | create with image | `POST /api/receipts` with `IMG_2.jpg` | file moved, image served; fake OCR and model call counts 0 | 201 |
| AC21 | free name | `POST` with `b.png` | `b (2).png` | 201 |
| AC22 | duplicate | `POST` with `copy.jpg` | `duplicate_image` | 409 |
| AC23 | unusable image | five `POST`s | `image_not_found` ×4, `unsupported_format` | 422 |
| AC24 | move fails | `POST` with read-only done folder | `image_move_failed`; no row; file in F | 503 |
| AC25 | delete in UI | `ReceiptPage` + `App` with mocked fetch | `DELETE` sent, list shown | — |
| AC29 | create in UI | `ReceiptsPage` + `App` with mocked fetch | `POST` body, receipt page, no image request | — |

### E2E tests
Fake engines, as the existing E2E tests. The failed folder of the E2E backend is filled
through a test-only volume, as the import folder is today (decided in Plan).
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC29, AC11 | Type in a receipt without an image | Kuitit → `Uusi kuitti` → fill → `Luo kuitti` → add a line `Maito 1,25` | Receipt page shows `Ei kuvaa.` and the line; the list shows the receipt |
| AC30 | Type in a failed receipt with its image | Put a synthetic PNG in the failed folder → Kuitit → `Uusi kuitti` → choose it → see the preview → fill → `Luo kuitti` | Receipt page shows the image; the form no longer offers it |
| AC25 | Delete an imported receipt | Import a fixture → open it → `Poista kuitti` → `Poista` | The list no longer shows it |
| AC35 | Accessibility | axe on the open form with a preview, and the receipt page without an image | No violations |

### Coverage target
- Backend: 90 % lines for the changed review, storage and folder modules; every branch of
  `delete_receipt`, `create_receipt`, the failed-folder lookup and the migration tested.
- Frontend: every new branch of the form and the delete button tested.

### Test data
- Synthetic fixtures only (no real receipts): synthetic PNG and JPEG images generated in the
  tests, a text file named `.jpg`, and invented store and product names.
- Mocks: fixed clock; fake OCR and model engines; a move that raises `OSError`; mocked
  `fetch` in component tests.

## Related Documentation (MANDATORY)
- Tier 1: [API reference](../../docs/api-reference.md#receipts),
  [data model](../../docs/datamodel.md#receipts), [architecture](../../docs/architecture.md),
  [PRD](../PRD.md)
- Tier 2: [review](../../docs/subsystems/review/README.md),
  [storage](../../docs/subsystems/storage/README.md),
  [import](../../docs/subsystems/import/README.md), [ui](../../docs/subsystems/ui/README.md)
- ADRs: [0002 Docker](../../docs/adr/0002-docker.md) (database in the volume)

<!-- The Plan phase appends "## Plan" and the Tasks phase appends "## Tasks" below. -->
