# Feature: Receipt deletion and manual receipts

## Overview
- **Status:** Done
- **Created:** 2026-11-02
- **Updated:** 2026-11-02: user answers: a deleted receipt's image stays in the done folder;
  a manual receipt is created with a small form (store, date, total) and its lines are added
  on the receipt page; only an unreviewed receipt can be deleted. Second round: a manual
  receipt may have an image, chosen from the failed folder, only when it is created.
  Decided by the agent for review: the form shows a preview of the chosen image (file names
  such as `IMG_1234.jpg` do not tell receipts apart); the preview's file name goes in the
  query string, which is never logged. 2026-11-03: the user approved the spec (Specify);
  Plan added for review. Plan approved; Tasks added; AC24's tests simulate the unwritable
  done folder with a failing move. Tasks approved; status Approved by the user on
  2026-11-03, then In Progress. T7: AC6 showed that SQLite reuses a deleted receipt's id;
  user decision: `AUTOINCREMENT` in migration 0006 (P2), checked in AC15. T26: the audit
  found that a double click could create two manual receipts; user decision: `Luo kuitti`
  and `Poista kuitti` are disabled while their request runs (AC36, AC37, T27). The audit
  also fixed a 500 for a failed image name with a NUL character (`docs/learnings.md`).
  Audit passed 2026-11-03; status Done. Left for later (not spec violations): with a done
  folder that cannot be listed, a duplicate image answers 503 `image_move_failed` before
  the duplicate check; an import that takes the chosen done name between `take` and the
  move answers 503 instead of retrying with a new name; `npm audit` reports a moderate
  `minimatch` advisory in the ESLint dev tools, unchanged by this feature.
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
  network message) next to the button with `role="alert"`. From the confirmation until the
  answer arrives, `Poista kuitti` is disabled, so a second delete cannot be sent; after a
  failed delete it is enabled again (AC37).
- **PC11 New receipt form on the receipt list.** The Kuitit page has a `Uusi kuitti` button
  above the list. It opens a form with `Kauppa`, `Päivä` (date input), `Loppusumma`, `Kuva`
  (a select) and the buttons `Luo kuitti` and `Peruuta`. `Peruuta` closes the form without
  sending. While the create request runs, `Luo kuitti` is disabled, so a double click sends
  one request; after a failed create it is enabled again (AC36).
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
**Then** migration 6 is applied first (later migrations may follow it); A and R and every
line read back with the same ids and
values; `PRAGMA foreign_key_check` returns no rows; inserting a receipt with `image_hash`
set and `file_name` `NULL` (or the other way round) fails with a constraint error; inserting
a second receipt with hash H fails with a constraint error; after the receipt with the
largest id is deleted, the next receipt gets a larger id (ids are never reused, so an old
link to a deleted receipt cannot open another one)

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

### AC36: One create per click
**Given** the open form with valid values, and the backend has not answered yet
**When** the user clicks `Luo kuitti` twice
**Then** one `POST /api/receipts` was sent and `Luo kuitti` is disabled; after a failed
answer it is enabled again

### AC37: One delete per confirmation
**Given** the receipt page of A, and the backend has not answered the delete yet
**When** the user confirms the delete
**Then** `Poista kuitti` is disabled and one `DELETE` was sent; after a failed answer it is
enabled again

## Files to Modify
| File | Change |
|---|---|
| `backend/app/storage/migrations/0006_manual_receipts.sql` | New: rebuilds `receipts` with `image_hash` and `file_name` nullable, both or neither (PC9, Plan P2) |
| `backend/app/storage/migrate.py` | Foreign keys off around each migration, `foreign_key_check` before the commit (Plan P2) |
| `backend/app/storage/receipt_repository.py` | `add` takes `None` hash and name; `ReceiptRow` fields nullable |
| `backend/app/image_files.py` | New shared module: signatures, `media_type`, `check_format`, `image_identifier`, `free_target_name`, `move_file` (Plan P3) |
| `backend/app/receipt_import/files.py` | Uses `app/image_files.py` instead of its own copies (Plan P3) |
| `backend/app/review/images.py` | Uses `media_type` from the shared module |
| `backend/app/review/failed_images.py` | New: `FailedFolder` (list, preview, take an image) (Plan P4) |
| `backend/app/review/service.py` | `create_receipt`, `delete_receipt`; `image` raises `NoImageError`; nullable `file_name` |
| `backend/app/review/routes.py`, `schemas.py`, `errors.py` | `POST /api/receipts`, `DELETE /api/receipts/{id}`, `GET /api/failed-images`, `GET /api/failed-images/image`; new codes; nullable `file_name` |
| `backend/app/main.py` | `create_app` takes an optional `failed_folder` for tests (Plan P5) |
| `backend/app/texts.py` | The new messages |
| `backend/tests/...` | Unit and integration tests below |
| `backend/tests/receipt_import_data.py`, `unit/receipt_import/test_import_files.py`, `test_import_run.py`, `integration/test_import_api.py`, `integration/test_import_reading_api.py` | Only the import lines of the moved names (`image_identifier`, `check_format`, `free_target_name`) change to `app.image_files`, and the `add` override in `receipt_import_data.py` takes `str | None` for hash and name (T3); the moved tests of `test_import_files.py` go to `unit/test_image_files.py` unchanged (Plan P3) |
| `backend/tests/integration/test_receipts_api.py` (`test_ac19_migration_keeps_existing_receipts`) | Checks that migration 5 is applied instead of that 5 is the newest version, as `test_ac1_migration_creates_the_receipts_table` already does; migration 6 broke the exact check (user decision 2026-11-03, T2) |
| `compose.yaml` | Test-only failed folder volume shared by `backend-e2e` and `e2e` (Plan P7) |
| `frontend/src/api/receipts.ts` | `createReceipt`, `deleteReceipt`, `failedImages`, `failedImageUrl`; `file_name: string \| null` |
| `frontend/src/components/ReceiptPage.tsx` | Delete button (PC10), image column without an image (PC12) |
| `frontend/src/components/ReceiptsPage.tsx`, new `NewReceiptForm.tsx` | `Uusi kuitti` form (PC11) |
| `frontend/src/components/ConfirmDelete.tsx` | A label prop for `Poista kuitti`; a disabled prop (AC37) |
| `frontend/src/i18n/fi.ts` | New texts |
| `frontend/src/styles.css` | The preview's size in the form |
| `frontend/src/test/receipts.ts` | Fixtures: a receipt without an image, failed image names |
| `frontend/src/**/*.test.tsx`, `frontend/e2e/` | Tests below |
| `specs/PRD.md` | New FR-46 and FR-47 |
| `specs/README.md` | This spec's row |
| `docs/architecture.md` | The shared `image_files` module in the folder structure and dependency rules |
| `docs/api-reference.md` | New endpoints, codes, nullable `file_name` |
| `docs/datamodel.md` | `receipts` columns, migration 0006 |
| `docs/subsystems/review/README.md` | New service methods and endpoints; the signature gotcha removed |
| `docs/subsystems/storage/README.md` | Migrations run with foreign keys off and a key check |
| `docs/subsystems/import/README.md` | A deleted receipt's image is no longer a duplicate; a failed image can leave the failed folder through a manual receipt |
| `docs/subsystems/ui/README.md` | Delete button, new receipt form, image column without an image |
| `docs/development.md` | How to copy the database out of the volume before the upgrade |
| `docs/glossary.md` | Manual receipt (käsin luotu kuitti), failed image |
| `docs/learnings.md` | Audit fix: a failed image name with a NUL character |

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
| AC15 | `migrate` | data kept | version 5 with A, R, lines | migrate | migration 6 applied first, same rows, FK check empty, both-or-neither and unique checks | none |
| AC16 | failed images list | names | F | list | `b.png`, `fake.jpg`, `IMG_2.jpg` | temp folder |
| AC17 | failed images list | empty, missing | — | list | `[]`; `FoldersUnavailableError` | temp folder |
| AC19 | failed image preview | refused names | F | each name | `ImageNotFoundError` | temp folder |
| AC20 | `create_receipt` | with image | F, empty done | `IMG_2.jpg` | row with hash, file moved | clock, temp folders |
| AC21 | `create_receipt` | free name | `b.png` in done | `b.png` | `b (2).png` | temp folders |
| AC22 | `create_receipt` | duplicate | A, `copy.jpg` | create | `DuplicateImageError`; nothing changes | temp folders |
| AC23 | `create_receipt` | unusable image | F | each name | `ImageNotFoundError`, `UnsupportedFormatError` | temp folders |
| AC24 | `create_receipt` | move fails | a move that fails | `b.png` | `ImageMoveFailedError`; no row; file in F | move raises `OSError` |
| AC26 | `ReceiptPage` | cancel delete | A | `Poista kuitti`, `Peruuta` | no fetch | fetch |
| AC27 | `ReceiptPage` | reviewed | R | render, then unconfirm | no button, then button | fetch |
| AC28 | `ReceiptPage` | failed delete | 409, network error | confirm | alert, stays | fetch |
| AC30 | `NewReceiptForm` | image options and preview | list of three | choose `IMG_2.jpg` | options in order; preview `src` | fetch |
| AC31 | `NewReceiptForm` | preview and list errors | preview error; 503 | — | texts; only `Ei kuvaa` | fetch |
| AC32 | `NewReceiptForm` | client checks | open form | empty date, `abc` | two alerts, no fetch | fetch |
| AC33 | `NewReceiptForm` | failed create | 409, network error | submit | alert, values and image kept | fetch |
| AC34 | `NewReceiptForm` | cancel | typed values, image | `Peruuta` | closed, no fetch, empty on reopen | fetch |
| AC36 | `NewReceiptForm` | double click | valid values, answer held back | two clicks | one fetch, button disabled; enabled after a 409 | fetch |
| AC37 | `ReceiptPage` | delete running | A, answer held back | confirm | button disabled, one fetch; enabled after a 409 | fetch |
| AC37 | `ConfirmDelete` | disabled | `disabled` | render | first button disabled | none |

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
| AC24 | move fails | `POST` with a `FailedFolder` whose move raises `OSError` (tests run as root, so a read-only folder would not fail) | `image_move_failed`; no row; file in F | 503 |
| AC25 | delete in UI | `ReceiptPage` + `App` with mocked fetch | `DELETE` sent, list shown | — |
| AC29 | create in UI | `ReceiptsPage` + `App` with mocked fetch | `POST` body, receipt page, no image request | — |

### E2E tests
Fake engines, as the existing E2E tests. The failed folder of the E2E backend is filled
through a test-only volume, as the import folder is today (decided in Plan).
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC29, AC11 | Type in a receipt without an image | Kuitit → `Uusi kuitti` → fill → `Luo kuitti` → add a line `Maito 1,25` | Receipt page shows `Ei kuvaa.` and the line; the list shows the receipt |
| AC30 | Type in a failed receipt with its image | Put a synthetic PNG in the failed folder → Kuitit → `Uusi kuitti` → choose it → see the preview → fill → `Luo kuitti` | Receipt page shows the image; the form no longer offers it |
| AC25 | Delete a receipt | Type in a receipt → `Poista kuitti` → `Poista` | The list opens and no longer shows it (a typed-in receipt, not an import: the import journeys empty the shared import folder in parallel; deleting an imported receipt is covered by the API tests of AC1 and AC6) |
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

## Plan

### P1 Where the code goes

| Package | Holds | Depends on |
|---|---|---|
| `storage` | Migration 0006; the migration runner turns foreign keys off around each migration; nullable `image_hash` and `file_name` | SQLite |
| `app/image_files.py` (new, cross-cutting) | The JPEG and PNG signatures, `media_type`, `check_format`, `image_identifier`, `free_target_name`, `move_file` | nothing |
| `receipt_import` | Unchanged behavior; uses the shared module instead of its own copies | `image_files` |
| `review` | Create and delete a receipt, the failed folder (list, preview, take an image), the new routes | `storage`, `categorization`, `calculation`, `image_files` |
| `ui` | Delete button, new receipt form, image column without an image | REST API |

The failed folder belongs to import, but its new users are the review routes, and no
subsystem may depend on `import` ([architecture](../../docs/architecture.md#dependency-rules)).
The file rules both need (signatures, hash, free name, the safe move) therefore move to a
cross-cutting module next to `texts.py` and `errors.py`. This removes the duplicated
signatures named in the review README gotcha instead of adding a third copy. The move is a
refactor: the import tests must stay green, changed only in where they import the moved
names from. No ADR: the module follows the existing rule for cross-cutting modules. No new
dependency.

### P2 storage: migration 0006

SQLite cannot drop `NOT NULL` in place, so `0006_manual_receipts.sql` rebuilds the table
with SQLite's documented procedure:

```sql
CREATE TABLE receipts_new (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    image_hash    TEXT UNIQUE CHECK (image_hash IS NULL OR length(image_hash) = 64),
    file_name     TEXT,
    imported_at   TEXT NOT NULL,
    store         TEXT,
    purchase_date TEXT CHECK (purchase_date IS NULL
        OR purchase_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    total_cents   INTEGER,
    ocr_text      TEXT,
    reviewed      INTEGER NOT NULL DEFAULT 0 CHECK (reviewed IN (0, 1)),
    CHECK ((image_hash IS NULL) = (file_name IS NULL))
);
INSERT INTO receipts_new (id, image_hash, file_name, imported_at, store, purchase_date,
    total_cents, ocr_text, reviewed)
  SELECT id, image_hash, file_name, imported_at, store, purchase_date, total_cents, ocr_text,
    reviewed FROM receipts;
DROP TABLE receipts;
ALTER TABLE receipts_new RENAME TO receipts;
```

The ids are copied, so `receipt_lines.receipt_id` still points at the same receipts. The
table has no indexes besides the `UNIQUE` one, no triggers and no views to recreate.
`AUTOINCREMENT` keeps a deleted receipt's id from being given to the next receipt (without
it SQLite reuses the largest id after a delete); the copy with explicit ids sets the
sequence to the largest copied id.

**Lines must survive (Risk).** With foreign keys on, `DROP TABLE receipts` deletes every
line through `ON DELETE CASCADE`. `PRAGMA foreign_keys` cannot change inside a transaction,
and `migrate.py` runs each file inside `BEGIN`, so the file cannot turn them off itself.
`migrate.py._apply` changes as SQLite's
[ALTER TABLE guide](https://www.sqlite.org/lang_altertable.html#otheralter) describes:

1. `PRAGMA foreign_keys = OFF` before `BEGIN`;
2. the script and the version row, as today;
3. `PRAGMA foreign_key_check` before `COMMIT`; any row raises `MigrationError` and rolls
   back;
4. `PRAGMA foreign_keys = ON` in a `finally`, also after a failure.

This applies to every migration. Migrations 0001–0005 only create and add, so turning keys
off changes nothing for them, and step 3 still catches a broken reference. AC15 proves it
with a version-5 database built by running 0001–0005, with lines that have categories and
product links. A unit test of `migrate` also shows that a migration that leaves a dangling
reference fails and is rolled back, and that foreign keys are on again afterwards (a
regression guard for the runner change, beyond AC15).

`ReceiptRow.image_hash` and `file_name` become `str | None`; `ReceiptRepository.add` takes
them as `str | None`. The import still passes both. No other query changes: `get_by_hash`
never matches `NULL`, and the list, totals and export do not read either column.

### P3 Shared module `app/image_files.py`

Moved from @backend/app/receipt_import/files.py without behavior changes:
`image_identifier`, `check_format`, `free_target_name`, and the body of
`LocalFileStore.move` as `move_file(source, target)`. New: `media_type(data) -> str | None`
(`image/jpeg` or `image/png` from the signature, else `None`), which
@backend/app/review/images.py uses instead of its own `_TYPES`. `receipt_import/files.py`
keeps `is_ignored`, `FileStore` and `LocalFileStore` (whose `move` calls `move_file`) and
re-exports nothing; its callers and tests import the moved names from the new module.

### P4 review: the failed folder

New `review/failed_images.py`:

```python
@dataclass(frozen=True)
class TakenImage:
    """A failed image checked for a new receipt; not moved yet."""
    path: Path
    image_hash: str
    done_name: str


class FailedFolder:
    """The failed folder as the new receipt form uses it (PC4, PC7, PC8). `move` is
    `move_file` in production; tests pass one that raises OSError (AC24)."""

    def __init__(self, failed_dir: Path, done_dir: Path,
                 move: Callable[[Path, Path], None] = move_file) -> None: ...

    def names(self) -> list[str]:
        """PC7: regular files directly in the folder whose suffix is .jpg, .jpeg or .png
        (any case), sorted by casefold, then name. Raises FoldersUnavailableError."""

    def preview(self, name: str) -> tuple[bytes, str]:
        """PC8: bytes and media type. Raises ImageNotFoundError (status 404) for a name that
        is not a failed image, a path, an unreadable file or one without a signature."""

    def take(self, name: str) -> TakenImage:
        """PC4 steps 1, 2 and 4: find, read, check the format, hash, choose the done name.
        Raises ImageNotFoundError (422), UnsupportedFormatError, ImageMoveFailedError
        (the done folder cannot be listed)."""

    def move_to_done(self, image: TakenImage) -> None:
        """PC4 step 6. Raises OSError."""
```

`preview` and `take` share one name check: not `""`, `.` or `..`, equal to its own
`PurePath(name).name`, a failed image suffix, a regular file, and the resolved path's parent
is the resolved folder (as `read_image` does today). A folder named `sub` fails as "not a
regular file". `image_not_found` is 404 for a preview and 422 for a create, so
`ImageNotFoundError` takes the status as an argument.

New errors in `review/errors.py`, texts in @backend/app/texts.py: `ReceiptReviewedError`
(409), `NoImageError` (404), `ImageNotFoundError` (422 or 404), `UnsupportedFormatError`
(422, the import's text), `DuplicateImageError` (409), `ImageMoveFailedError` (503), and
`FoldersUnavailableError` (503, the same code and text as import's; review must not import
from import, and the class is three lines).

### P5 review: service and routes

`ReviewService` gets two methods; both check ids with `_require_ids` as today.

- `delete_receipt(receipt_id) -> None` (PC1): in one transaction, `get`; `None` raises
  `NotFoundError`; `reviewed` raises `ReceiptReviewedError`; else `repository.delete`. The
  file is not touched (PC2).
- `create_receipt(new: NewReceipt, now: datetime, folder: FailedFolder | None = None) -> ReceiptView`
  (PC3, PC4), where `NewReceipt` is a dataclass of `store`, `purchase_date`, `total_cents`
  and `image_file_name: str | None`:
  1. `check_store`, `check_date`, `check_total` (the line-editing checks) before any file
     is touched (AC9);
  2. with an image: `image = folder.take(name)`; `get_by_hash(image.image_hash)` raises
     `DuplicateImageError`;
  3. in one transaction, `add(hash or None, done name or None, imported_at, store=...,
     purchase_date=..., total_cents=..., ocr_text=None)`, where `imported_at` is `now` as
     `YYYY-MM-DDTHH:MM:SSZ`. An `IntegrityError` on the hash (an import or another create
     took it meanwhile) raises `DuplicateImageError`;
  4. with an image: `folder.move_to_done(image)`; on `OSError` the row is deleted in a new
     transaction and `ImageMoveFailedError` is raised. If that delete fails too, the error
     is logged without its message (as import's `_delete_receipt` does); the file is still
     in the failed folder;
  5. returns `receipt(id)`.

  The route passes `datetime.now(UTC)`, so tests fix the clock by calling the service.
  Integration tests that check `imported_at` (AC7) fix it through a `clock` argument of
  `create_review_router`, as `failed_folder` below.
- `image(receipt_id, done_dir)` raises `NoImageError` when `file_name` is `None` (PC6).
- `ReceiptView.file_name` becomes `str | None`.

Schemas: a `NewReceipt` body (`_Body`: strict, `extra="forbid"`): `store: StrictStr`,
`purchase_date: StrictStr`, `total_cents: StrictInt`, `image_file_name: StrictStr | None =
None`, with a validator that refuses `image_file_name` when it was sent as `null` (as
`_PartialBody` does). `ReceiptOut.file_name: str | None`.

Routes, all in `create_review_router(settings, failed_folder: FailedFolder | None = None,
clock: Callable[[], datetime] = ...)` (default folder `FailedFolder(settings.failed_dir,
settings.done_dir)`, default clock `datetime.now(UTC)`). `create_app` passes optional
`failed_folder` and `clock` through, as it does `import_service`:

| Route | Calls | Answer |
|---|---|---|
| `POST /api/receipts` (`status_code=201`) | `create_receipt` | `ReceiptOut` |
| `DELETE /api/receipts/{receipt_id}` (`status_code=204`) | `delete_receipt` | no body |
| `GET /api/failed-images` | `folder.names()` | `{"file_names": [...]}` |
| `GET /api/failed-images/image?name=` | `folder.preview(name)` | bytes, `Cache-Control: no-store` |

`name` is a required query parameter; without it FastAPI's validation error goes through the
existing handler to 422 `invalid_request` (AC19). The request log already writes
`request.url.path` only (@backend/app/logging_setup.py), so the preview's name stays out of
it (AC18 checks the log line).

```mermaid
sequenceDiagram
  participant U as NewReceiptForm
  participant R as review routes
  participant V as ReviewService
  participant F as FailedFolder
  participant S as storage
  U->>R: POST /api/receipts {..., "image_file_name": "IMG_2.jpg"}
  R->>V: create_receipt(NewReceipt, now, folder)
  V->>V: check store, date, total
  V->>F: take("IMG_2.jpg"): read, format, hash, done name
  V->>S: get_by_hash: none
  V->>S: BEGIN IMMEDIATE; add(hash, done name, ...); COMMIT
  V->>F: move_to_done: failed -> done
  alt move fails
    V->>S: delete(id)
    R-->>U: 503 image_move_failed
  else moved
    R-->>U: 201 receipt
  end
```

### P6 frontend

- **`api/receipts.ts`:** `Receipt.file_name: string | null`; `createReceipt(body:
  NewReceipt)` (`apiPost`, returns `Receipt`); `deleteReceipt(id)` (`apiDelete`, no data);
  `failedImages()` (`apiGet<{ file_names: string[] }>`); `failedImageUrl(name)` returns
  `/api/failed-images/image?name=` + `encodeURIComponent(name)`.
- **`ConfirmDelete`:** an optional `label` prop (default `fi.actions.delete`) for the first
  button; the confirm and cancel buttons stay `Poista` and `Peruuta`. Existing callers do
  not change.
- **`ReceiptPage`:** after a successful delete it calls its existing `onBack`, which opens
  the receipt list (changed during T19 from a new `onDeleted` prop: same behavior, no change
  to `App` or to the existing tests). An unreviewed receipt shows `ConfirmDelete` with the label
  `Poista kuitti` next to the review button. The delete runs in the page's change queue, so
  an edit still waiting finishes first. A failure sets `deleteError`, shown with
  `role="alert"` next to the button. With `file_name === null` the image column shows
  `Ei kuvaa.` and renders no `<img>`, so no image request is made (AC29).
- **`NewReceiptForm.tsx` (new):** props `onCreated(id)` and `onCancel()`. State: the four
  field drafts, the image names (`null` while loading), a list error, a preview error flag
  (reset when the choice changes), field errors and a submit error. On mount it calls
  `failedImages()`. On submit the total (`parseCents`) and a non-empty date are checked
  first (AC32); then `createReceipt`, sending `image_file_name` only when one is chosen.
  Errors keep every value (AC33). The date input is `type="date"`, whose value is already
  `YYYY-MM-DD`.
- **`ReceiptsPage`:** a `Uusi kuitti` button above the list shows the form; `onCancel`
  unmounts it, so reopening starts empty (AC34); `onCreated` calls the page's `onOpen(id)`.
- **`fi.ts`:** the texts of the UI texts table. **`styles.css`:** the preview at most
  `20rem` wide, so the form stays usable in a narrow window.

### P7 E2E

`compose.yaml` gets a test-only volume `rrmc-e2e-failed`, mounted at `/data/import_failed`
in `backend-e2e` and at `/e2e-failed` in `e2e` (env `E2E_FAILED_DIR`), as the import folder
is today. It is never the real failed folder. The volume outlives a run, so the AC30 test
writes `syntheticPng(<unique tag>)` under a unique name and looks only for that name;
leftovers from earlier runs, or from other tests' failing imports, do not disturb it. The
`mkdir -p` in `backend-e2e`'s command is harmless for a mounted folder.

### P8 Checked against the ACs

| AC | Covered by |
|---|---|
| AC1–AC5 | P5 `delete_receipt`, `DELETE` route |
| AC6 | P5 (file not touched); import unchanged (`get_by_hash` finds no row) |
| AC7, AC8, AC14 | P5 `create_receipt` without an image; P2 allows many `NULL` hashes |
| AC9 | P5 step 1 runs before `take` |
| AC10 | P5 `NewReceipt` schema |
| AC11, AC12 | Existing line, totals and export code; no change needed |
| AC13 | P5 `image` raises `NoImageError` |
| AC15 | P2 migration and runner |
| AC16, AC17 | P4 `names` |
| AC18, AC19 | P4 `preview`, P5 route, request log |
| AC20–AC24 | P4 `take`, `move_to_done`; P5 steps 2–4 |
| AC25–AC28 | P6 `ReceiptPage`, `ConfirmDelete` |
| AC29–AC34 | P6 `NewReceiptForm`, `ReceiptsPage`, `ReceiptPage` image column |
| AC35 | P6 markup with labels; axe in P7 |

### P9 Order of work

1. Migration runner and migration 0006 (AC15); the repository's nullable fields.
2. Shared `image_files` module; import and review switched to it (existing tests green).
3. Backend delete (AC1–AC6).
4. Backend create without an image (AC7–AC14).
5. Failed folder list and preview (AC16–AC19).
6. Backend create with an image (AC20–AC24).
7. Frontend delete and image column (AC25–AC28, the receipt page part of AC29).
8. Frontend new receipt form (AC29–AC34).
9. E2E and accessibility (AC35); docs.

## Tasks

Each task is one Red → Green → Refactor cycle unless it says otherwise. Backend unit tests go
next to the existing ones (`unit/storage/`, `unit/review/`, `unit/`); API tests go to
`backend/tests/integration/test_receipts_api.py`, the failed-folder ones to a new
`integration/test_failed_images_api.py`. Frontend tests sit next to their files. Test names
start with the AC ID. All images are synthetic and generated in the tests. After every task
the tests, lint, format check and type check of the changed part pass. Existing tests change
only where [Files to Modify](#files-to-modify) names them, and only as it says there.

### Storage

- [x] **T1 Migration runner with foreign keys off (P2).** Tests in `test_migrate.py`: a
  throwaway migration 2 that rebuilds a parent table with `ON DELETE CASCADE` children keeps
  the children; a migration that leaves a dangling reference raises `MigrationError`, the
  version stays 1, and the change is rolled back; after both, `PRAGMA foreign_keys` is 1.
  Red: the first test loses the children. Green: `_apply` as in P2 steps 1–4.
- [x] **T2 Migration 0006 (P2; AC15).** Tests in `test_receipts_schema.py`
  (`test_ac15_migration_keeps_existing_data`, `test_ac15_hash_and_name_both_or_neither`,
  `test_ac15_hash_still_unique`, plus many `NULL` hashes allowed): a database migrated to
  version 5 with receipt A (OCR text), R, lines with categories, sources and product links;
  run all migrations; version 6, every row reads back the same, `foreign_key_check` empty.
  Green: `0006_manual_receipts.sql`.
- [x] **T3 Repository nullable fields (P2; AC7).** Test in `test_receipt_repository.py`:
  `add(None, None, ...)` stores and `get` returns `image_hash` and `file_name` `None`.
  Red is the type check (the schema already allows it after T2). Green: the types of
  `ReceiptRow` and `add`, and of the `add` override in `tests/receipt_import_data.py`. The
  nullable type reaches `ReviewService.image` and `ReceiptView`, so T8's unit part moves
  here: test `test_ac13_image_of_a_receipt_without_one` (`NoImageError`); Green:
  `NoImageError`, `ReceiptView.file_name` and `ReceiptOut.file_name` as `str | None`.

### Shared image files

- [x] **T4 Move the file rules (P3).** Refactor, no new behavior: move the tests of
  `image_identifier`, `check_format` and `free_target_name` from `test_import_files.py` to
  `unit/test_image_files.py`, and change the import lines named in Files to Modify; see them
  fail (no module). Green: `app/image_files.py` with the moved functions and `move_file`;
  `LocalFileStore.move` calls `move_file`; `run.py` imports from the new module. Every
  existing import test passes unchanged otherwise.
- [x] **T5 `media_type` (P3).** Tests in `test_image_files.py`: JPEG and PNG bytes give
  `image/jpeg` and `image/png`, text bytes `None`. Green: `media_type`; `review/images.py`
  uses it and drops `_TYPES`; `test_images.py` passes unchanged. Remove the gotcha from the
  review README in this task.

### Backend delete

- [x] **T6 `delete_receipt` (P5; AC1, AC3, AC5).** Unit tests in `test_review_service.py`
  as in the Testing Strategy rows AC1, AC3, AC5. Green: `ReceiptReviewedError`,
  `delete_receipt`.
- [x] **T7 `DELETE /api/receipts/{id}` (P5; AC1–AC6).** Integration tests
  `test_ac1_...` to `test_ac6_deleted_image_imports_again` (AC6 with the fake engines and a
  synthetic JPEG). Green: the route (`status_code=204`).

### Backend create without an image

- [x] **T8 `no_image` through the API (P5; AC13).** Integration test of `GET .../image`
  for a receipt without an image (the unit part and the types are done in T3). May be green
  at once, which is recorded. Done: green at once, as expected.
- [x] **T9 `create_receipt` without an image (P5; AC7, AC8).** Unit tests with a fixed
  `now`. Green: `NewReceipt` dataclass, `create_receipt` steps 1, 3, 5.
- [x] **T10 `POST /api/receipts` (P5; AC7, AC8, AC10, AC11, AC12, AC14).** Integration tests
  with a fixed clock; AC10 with the eight bodies; AC11 counts fake model calls (0); AC12
  reads totals and the lines file. Green: `NewReceipt` schema, the route, the `clock` and
  `failed_folder` arguments of `create_review_router` and `create_app`.

### Failed folder

- [x] **T11 `FailedFolder.names` (P4; AC16, AC17).** Unit tests in
  `unit/review/test_failed_images.py` with folder F built in `tmp_path`. Green: `names`,
  review's `FoldersUnavailableError`.
- [x] **T12 `FailedFolder.preview` (P4; AC18, AC19).** Unit tests for each refused name.
  Green: the shared name check, `preview`, `ImageNotFoundError`.
- [x] **T13 Failed-image routes (P5; AC16–AC19).** Integration tests; AC18 reads the request
  log line with `caplog` and checks it holds the path and not `b.png`. Green: the two routes.

### Backend create with an image

- [x] **T14 `take` and `move_to_done` (P4; AC20, AC21, AC23).** Unit tests: `take`
  returns the hash and the done name (`b (2).png` when taken); `missing.png`,
  `../import_done/a.jpg`, `sub`, `notes.txt` raise `ImageNotFoundError` (422), `fake.jpg`
  `UnsupportedFormatError`. Green: `take`, `move_to_done`, the errors.
- [x] **T15 `create_receipt` with an image (P5; AC9, AC20–AC24).** Unit tests as in the
  Testing Strategy rows; AC24 passes a `move` that raises `OSError`; AC9 checks that `b.png`
  is still in F. Green: steps 2 and 4, `DuplicateImageError` (also from `IntegrityError`),
  `ImageMoveFailedError`.
- [x] **T16 API with an image (P5; AC9, AC20–AC24).** Integration tests; AC20 counts fake
  OCR and model calls (0); AC24 uses a `FailedFolder` whose `move` raises `OSError` (the
  tests run as root, so a read-only folder would not fail). Green: wiring only; this task
  may be green at once, which is recorded in the commit.

### Frontend

- [x] **T17 API functions and fixtures (P6).** Tests in `receipts.test.ts`: `createReceipt`
  posts the body, `deleteReceipt` sends `DELETE`, `failedImages` reads the list,
  `failedImageUrl("IMG_2.jpg")` is `/api/failed-images/image?name=IMG_2.jpg`. Green: the
  functions, `file_name: string | null`, fixtures in `src/test/receipts.ts`.
- [x] **T18 `ConfirmDelete` label (P6).** Test: with `label="Poista kuitti"` the first
  button has that text and the confirmation is unchanged; without it, `Poista`. Green: the
  prop.
- [x] **T19 Delete on the receipt page (P6; AC25–AC28).** Tests in `ReceiptPage.test.tsx`
  (AC26–AC28) and `App.test.tsx` (AC25). Green: the button, the queue, `deleteError`;
  a successful delete calls `onBack`.
- [x] **T20 Image column without an image (P6; PC12, AC29 page part).** Test: a receipt with
  `file_name: null` shows `Ei kuvaa.`, no `<img>`, and no request to `.../image`. Green: the
  branch in `ReceiptPage`.
- [x] **T21 New receipt form (P6; AC30–AC34).** Tests in `NewReceiptForm.test.tsx` as in
  the Testing Strategy rows. Green: `NewReceiptForm`, texts in `fi.ts`, the preview size in
  `styles.css`.
- [x] **T22 Form on the Kuitit page (P6; AC29).** Test in `App.test.tsx`: `Uusi kuitti`,
  fill, `Luo kuitti` sends the body of AC29 and opens `/kuitit/<new id>`. Green:
  `ReceiptsPage` shows the form and calls `onOpen`.

### E2E, docs and audit

- [x] **T23 E2E failed folder (P7).** `compose.yaml` volume `rrmc-e2e-failed` and
  `E2E_FAILED_DIR`; the tests write a uniquely named `syntheticPng` there (no new helper
  was needed). Verified by T24.
- [x] **T24 E2E journeys (AC11, AC25, AC29, AC30, AC35).** New `e2e/receipts.spec.ts` with
  the four journeys of the E2E table; axe as in `style.spec.ts`. Run the E2E command.
- [x] **T25 Docs.** Update every doc in Files to Modify: PRD FR-46 and FR-47, API reference,
  data model, architecture (`image_files`), storage, review, import and ui READMEs,
  development (copy the database out of the volume before the upgrade, a tested command),
  glossary. Then run the container tests and every command of the Commands table.
- [x] **T27 One request per click (AC36, AC37).** Added after the T26 audit. Red: the
  Testing Strategy rows for AC36 and AC37. Green: `NewReceiptForm` keeps a busy state and
  disables `Luo kuitti`; `ConfirmDelete` gets a `disabled` prop; `ReceiptPage` disables
  `Poista kuitti` while the delete runs. Update the ui README.
- [x] **T26 Audit.** Run the `review-audit` skill against this spec; fix findings through
  the spec first.
