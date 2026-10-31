# Feature: Receipt review

## Overview
- **Status:** Done
- **Created:** 2026-10-30
- **Updated:** 2026-10-30: user answers: the review UI is split into two specs, this one
  (list, receipt view, category choice, subtotals, warning, confirmation) first and line
  editing (FR-18, FR-43) second; a receipt can always be confirmed, also with a warning, and
  stays confirmed when it changes, until the user cancels the confirmation; only model
  suggestions are marked on the lines; the list shows the newest purchase date first, with
  receipts without a date at the top. Specify approved by the user; Plan added (the sums go
  to the planned **calculation** subsystem, see [Plan](#plan)). Plan approved by the user; Tasks added; spec approved by the user; implementation started; Files to Modify updated during T1, T2, T18 and T19 (tests pinned to migration 4 and to two navigation links, the test repository's `add_line`, the E2E test moved into `import.spec.ts`). Audited (PASS), see [Audit](#audit).
- **Depends on:** [Receipt import](receipt-import.md), [Receipt reading](receipt-reading.md),
  [Line categorization](categorization.md)
- **Implements:** PRD FR-16, FR-17, FR-19, FR-20, FR-21, FR-13 (UI part), FR-15 (shown for
  model suggestions); NFR-1, NFR-3, NFR-14, NFR-15 for the review UI.
- **Affected subsystems:** [ui](../../docs/subsystems/ui/README.md),
  [categorization](../../docs/subsystems/categorization/README.md) (the correction
  endpoint), [storage](../../docs/subsystems/storage/README.md), **calculation** (planned,
  started here: the receipt check), a new **review** backend
  package for the receipt endpoints (see [Files to Modify](#files-to-modify))

## Problem Statement
Imported receipts are stored with their lines and categories, but the user cannot see them.
The model's category suggestions cannot be checked or corrected, so wrong suggestions would
go straight into the totals, and the corrections that make categorization learn (FR-13) never
happen. This spec gives the user a list of receipts and a receipt view: the image beside its
lines, a category dropdown on each line, category subtotals, the warning when the lines do
not add up to the total, and a way to mark the receipt as checked (PRD section 5, step 5).

## Current Behavior
- An import run stores each receipt with its store, purchase date, total, OCR text and lines,
  and moves the image to the done folder under `receipts.file_name`
  ([import](../../docs/subsystems/import/README.md), [datamodel](../../docs/datamodel.md#receipts)).
  Receipts imported before reading existed have no read fields and no lines.
- Each line has a category, a category source (`remembered`, `model`, `user`) and a product
  link, or none of them; a deposit refund never has a category
  ([categorization](../../docs/subsystems/categorization/README.md#line-categorization)).
- `LineCategoryService.set_category` stores a user's choice for a line and remembers it for
  the product (FR-13, FR-36), but no endpoint calls it
  ([API reference](../../docs/api-reference.md#catalog-error-codes)).
- The UI has two pages, Tuotteet and Tuonti ([ui](../../docs/subsystems/ui/README.md)). There
  is no receipt endpoint and no receipt page.

## Proposed Change

### Concepts

- The **line sum** of a receipt is the sum of the amounts of all its lines, deposit refunds
  included (FR-20).
- The **difference** is the receipt total minus the line sum. It is unknown when the receipt
  has no total.
- A receipt has a **warning** when its difference is not 0, or when it has no total.
- A receipt's **review state** is `unreviewed` or `confirmed` (FR-21). A new receipt is
  `unreviewed`.
- A **category subtotal** is the sum of the amounts of a receipt's lines in one category.
  Deposit refunds are in no subtotal (FR-44). Lines that are not deposit refunds and have no
  category are summed into one "no category" subtotal.

### Parts

- **PC1 Receipt list endpoint (FR-21).** `GET /api/receipts` returns every receipt with its
  id, purchase date, store, total, warning and review state. Order: receipts without a
  purchase date first, then by purchase date, newest first; receipts with the same date (or
  both without one) newest import first (larger id first). No paging.
- **PC2 Receipt endpoint (FR-16, FR-19, FR-20).** `GET /api/receipts/{id}` returns the
  receipt's fields, its review state, its lines in printed order (each with its category,
  group and category source), the line sum, the difference, the warning and the category
  subtotals. The backend computes the sums, so the UI holds no rule (UI README). Subtotals
  follow the order of the category list (`GET /api/categories`), with "no category" last, and
  include only categories that have lines on the receipt.
- **PC3 Receipt image endpoint (FR-16).** `GET /api/receipts/{id}/image` returns the image
  file from the done folder with the content type of its signature (`image/jpeg` or
  `image/png`). The file is found by the stored `file_name` only; nothing from the request
  becomes part of the path. A missing or unreadable file gives `404 image_missing`.
- **PC4 Category choice endpoint (FR-13, FR-17).** `PATCH /api/receipts/{id}/lines/{line_id}`
  with `{"category_id": n}` calls `LineCategoryService.set_category` and returns the whole
  receipt as in PC2, because the choice can also move other lines of the same receipt that
  follow the same product (FR-36). A line that belongs to another receipt is `not_found`.
- **PC5 Confirmation endpoint (FR-21).** `PATCH /api/receipts/{id}` with
  `{"reviewed": true}` confirms the receipt, and `{"reviewed": false}` makes it unreviewed
  again. Confirming is always allowed, also with a warning or lines without category. Other
  changes (a category choice, later the line editing spec) do not change the review state.
  The answer is the whole receipt as in PC2.
- **PC6 Review state stored.** A new migration adds the review state to receipts. Existing
  receipts become `unreviewed`.
- **PC7 Kuitit page (FR-21).** A new navigation link **Kuitit** (`/kuitit`) after Tuonti
  opens the list as a table: date, store, total, warning, state. Each row opens its receipt.
  The app still opens on Tuotteet.
- **PC8 Receipt page (FR-16, FR-17, FR-19, FR-20).** `/kuitit/{id}` shows a back link to the
  list, the store, date and total, the review state with its button, the warning, the image
  and, beside it, the line table: name, amount, category dropdown. The image is a link that
  opens the full-size image in a new tab. Below the table are the line sum and the category
  subtotals.
  - The dropdown is `CategorySelect` (groups are headings that cannot be chosen, FR-17). A
    line without a category shows `Valitse kategoria`.
  - A line whose category source is `model` shows the mark `ehdotus` next to its dropdown.
    `remembered` and `user` show no mark.
  - A deposit refund has no dropdown; its category cell shows `Pantinpalautus`.
  - Choosing a category saves it at once (PC4). The page then shows the receipt from the
    answer, so subtotals, marks and other moved lines update without a reload (FR-19).
- **PC9 Errors on the receipt page.** A failed category choice shows the backend's
  `message` next to that line with `role="alert"`, and the line keeps its previous category.
  A failed confirmation shows its message next to the button. A receipt that does not exist
  shows `Kuittia ei löydy.` and the back link. A failed load shows the error message and the
  back link.
- **PC10 Money and dates in the UI.** Amounts are shown as euros with a decimal comma and two
  decimals, a hyphen-minus for negative amounts and a space before `€`, without thousands
  separators: `125` → `1,25 €`, `-40` → `-0,40 €`, `123456` → `1234,56 €`. Dates are shown
  as `5.10.2026` (no leading zeros).
- **PC11 Privacy (NFR-1, NFR-3).** Receipt content and images are served only by the local
  backend. Logs carry method, path and status only, as today; the paths hold ids, never
  names. Error messages hold no receipt content.

### UI texts

| Place | Text |
|---|---|
| Navigation link and list heading | `Kuitit` |
| List table name (`aria-label`) | `Kuittilista` |
| List columns | `Päivä`, `Kauppa`, `Summa`, `Varoitus`, `Tila` |
| Empty list | `Ei kuitteja. Tuo kuitit Tuonti-sivulla.` |
| Missing date, store or total (list and receipt page) | `–` |
| Warning cell in the list | `Summa ei täsmää` (empty without a warning) |
| Review states | `Tarkistamaton`, `Vahvistettu` |
| Back link | `Takaisin kuittilistaan` |
| Receipt page heading | `Kuitti` |
| Field labels | `Kauppa`, `Päivä`, `Loppusumma` |
| Confirm / cancel button | `Vahvista` (unreviewed), `Peru vahvistus` (confirmed) |
| Image link and image `alt` | `Kuitin kuva` |
| Image missing (shown instead of the image) | `Kuvaa ei löydy valmiiden kansiosta.` |
| Line table name (`aria-label`) | `Kuittirivit` |
| Line columns | `Tuote`, `Summa`, `Kategoria` |
| Dropdown label (`aria-label`) | `Kategoria: <line name>` |
| Model mark | `ehdotus` |
| Deposit refund category cell | `Pantinpalautus` |
| No lines | `Kuitilta ei luettu rivejä.` |
| Warning with a total (`role="status"`) | `Rivien summa <line sum> poikkeaa loppusummasta <total>. Erotus <difference>.` |
| Warning without a total (`role="status"`) | `Loppusumma puuttuu.` |
| Line sum | `Rivien summa` |
| Subtotal heading | `Kategoriat` |
| No-category subtotal | `Ei kategoriaa` |
| Receipt not found | `Kuittia ei löydy.` |

A subtotal shows the category as `Ryhmä > Kategoria`, or the name alone for a category
without a group.

### API shapes

A **receipt summary** (PC1):

```json
{"id": 3, "purchase_date": "2026-10-05", "store": "Testikauppa", "total_cents": 349, "warning": false, "reviewed": false}
```

A **receipt** (PC2):

```json
{
  "id": 3,
  "file_name": "kuitti.jpg",
  "imported_at": "2026-10-28T10:00:01Z",
  "store": "Testikauppa",
  "purchase_date": "2026-10-05",
  "total_cents": 349,
  "reviewed": false,
  "lines": [
    {"id": 10, "position": 1, "name": "Maito", "amount_cents": 125, "is_deposit_refund": false,
     "category_id": 12, "category_name": "Maitotuotteet", "group_name": "Ruoka", "category_source": "remembered"},
    {"id": 11, "position": 2, "name": "Panttipalautus", "amount_cents": -40, "is_deposit_refund": true,
     "category_id": null, "category_name": null, "group_name": null, "category_source": null}
  ],
  "line_sum_cents": 85,
  "difference_cents": 264,
  "warning": true,
  "subtotals": [
    {"category_id": 12, "category_name": "Maitotuotteet", "group_name": "Ruoka", "amount_cents": 125}
  ]
}
```

`store`, `purchase_date` and `total_cents` are `null` for a receipt imported before reading
existed; `store` is `""` when the model found none, and the UI shows both as `–`.
`difference_cents` is `null` without a total. `group_name` is `null` for a category without
a group. The no-category subtotal has `category_id`, `category_name` and `group_name` `null`.
The OCR text is not returned: nothing in the UI shows it.

### Error codes

| Status | `error` | `message` | When |
|---|---|---|---|
| 404 | `not_found` | `Pyydettyä kohdetta ei löydy.` | Receipt or line id does not exist, or the line is on another receipt |
| 404 | `image_missing` | `Kuvaa ei löydy valmiiden kansiosta.` | The receipt exists but its file is missing from the done folder or cannot be read |
| 422 | `unknown_category`, `not_a_category`, `deposit_refund_line`, `invalid_name` | as in the [API reference](../../docs/api-reference.md#catalog-error-codes) | From `LineCategoryService` (PC4) |
| 422 | `invalid_request` | `Pyyntö on virheellinen.` | Missing field, wrong JSON type, or `category_id: null` |

### Out of Scope
- Editing a line's name or amount, adding and deleting lines, and editing store, date and
  total (FR-18), and a renamed line following a matching product (FR-43): the **line
  editing** spec, which comes next and extends PC4 and PC5. Quantity and unit price are not
  read (FR-8 note), so that spec decides how FR-18 treats them.
- Clearing a line's category back to none.
- Deleting a receipt, and re-reading or re-categorizing a receipt.
- Showing the OCR text.
- Zooming or rotating the image inside the page; the image opens full size in a new tab.
- Filtering, searching or paging the list.
- Links from the Tuonti report to the imported receipts.
- Totals (FR-22–FR-25) and export (FR-26–FR-28).

## Acceptance Criteria

The examples use the default catalog: `Maitotuotteet` is in the group `Ruoka`, `Juomat`
has no group, and the list order is the groups (`Auto`, `Ruoka`) with their categories, then
the categories without a group. Receipt A: store `Testikauppa`, date 2026-10-05, total 349
cents, lines 1 `Maito` 125 (`Maitotuotteet`, `remembered`), 2 `Limu` 224 (`Juomat`,
`model`). Its line sum is 349 and its difference 0.

### AC1: List shows every receipt with its summary
**Given** receipt A, confirmed, and receipt B: store `Kauppa B`, date 2026-10-06, total 500,
one line of 450, unreviewed
**When** the client calls `GET /api/receipts`
**Then** the status is 200 and the body is
`[{"id": <B>, "purchase_date": "2026-10-06", "store": "Kauppa B", "total_cents": 500, "warning": true, "reviewed": false}, {"id": <A>, "purchase_date": "2026-10-05", "store": "Testikauppa", "total_cents": 349, "warning": false, "reviewed": true}]`

### AC2: List order
**Given** receipts imported in this order: R1 date 2026-10-05, R2 no date, R3 date
2026-10-07, R4 date 2026-10-05, R5 no date
**When** the client calls `GET /api/receipts`
**Then** the ids come in the order R5, R2, R3, R4, R1

### AC3: Empty list
**Given** no receipts
**When** the client calls `GET /api/receipts`
**Then** the status is 200 and the body is `[]`

### AC4: Receipt with its lines
**Given** receipt A, unreviewed
**When** the client calls `GET /api/receipts/<A>`
**Then** the status is 200; `lines` has two items in position order with
`category_name` `Maitotuotteet` and `Juomat`, `group_name` `Ruoka` and `null`,
`category_source` `remembered` and `model`; `line_sum_cents` is 349, `difference_cents` 0, `warning` false,
`reviewed` false; the body has no `ocr_text` field

### AC5: Line sum includes deposit refunds; warning with the difference
**Given** a receipt with total 300 and lines `Olut` 340 (`Juomat`) and `Panttipalautus`
-40 (deposit refund)
**When** the client calls `GET /api/receipts/<id>`
**Then** `line_sum_cents` is 300, `difference_cents` 0, `warning` false

### AC6: Warning when the lines do not add up
**Given** receipt B (total 500, one line of 450)
**When** the client calls `GET /api/receipts/<B>`
**Then** `line_sum_cents` is 450, `difference_cents` 50, `warning` true

### AC7: Warning without a total; receipt imported before reading
**Given** a receipt imported before reading existed: no store, date or total, no lines
**When** the client calls `GET /api/receipts/<id>` and `GET /api/receipts`
**Then** the receipt has `store`, `purchase_date`, `total_cents` and `difference_cents`
`null`, `lines` `[]`, `line_sum_cents` 0, `subtotals` `[]`, `warning` true; its list item
has `warning` true

### AC8: Category subtotals
**Given** a receipt with lines `Maito` 125 (`Maitotuotteet`), `Limu` 224 (`Juomat`),
`Jogurtti` 99 (`Maitotuotteet`), `Outo` 50 (no category), `Panttipalautus` -40 (deposit
refund)
**When** the client calls `GET /api/receipts/<id>`
**Then** `subtotals` is, in this order: `Maitotuotteet` (`group_name` `Ruoka`) 224, `Juomat`
(`group_name` `null`) 224, no category (`category_id` `null`) 50; there is no item for the
deposit refund

### AC9: Unknown receipt
**Given** no receipt with id 999
**When** the client calls `GET /api/receipts/999`, `GET /api/receipts/999/image` or
`PATCH /api/receipts/999` with `{"reviewed": true}`
**Then** each status is 404 with `error` `not_found`

### AC10: Receipt image
**Given** receipt A whose file `kuitti.jpg` in the done folder holds synthetic JPEG bytes
**When** the client calls `GET /api/receipts/<A>/image`
**Then** the status is 200, the content type `image/jpeg`, and the body is the file's bytes;
for a PNG file the content type is `image/png`

### AC11: Image missing from the done folder
**Given** receipt A, and its file was removed from the done folder
**When** the client calls `GET /api/receipts/<A>/image`
**Then** the status is 404 with `error` `image_missing` and the message
`Kuvaa ei löydy valmiiden kansiosta.`

### AC12: Image path cannot leave the done folder
**Given** a receipt whose stored `file_name` is `../secret.jpg`, and that file exists next to
the done folder
**When** the client calls `GET /api/receipts/<id>/image`
**Then** the status is 404 with `error` `image_missing`, and the file is not returned

### AC13: Choosing a category for a line
**Given** receipt A, and no product named `Limu`
**When** the client calls `PATCH /api/receipts/<A>/lines/<Limu line>` with
`{"category_id": <Maitotuotteet>}`
**Then** the status is 200; in the returned receipt the `Limu` line has `category_name`
`Maitotuotteet` and `category_source` `user`; `subtotals` is `Maitotuotteet` 349; a product
`Limu` with category `Maitotuotteet` exists (FR-13)

### AC14: The choice moves other lines of the same product on the receipt
**Given** a receipt with lines 1 `Maito` and 2 `Maito`, both linked to the product `Maito`
(`Maitotuotteet`, `remembered`)
**When** the client sets line 1's category to `Juomat`
**Then** the returned receipt has line 1 `Juomat` `user` and line 2 `Juomat` `remembered`

### AC15: Category choice errors
**Given** receipt A with a deposit refund line added, the group `Ruoka`, and no category 999
**When** the client patches a line with each of these bodies
**Then** the status and `error` are:
- `{"category_id": 999}` → 422 `unknown_category`
- `{"category_id": <Ruoka>}` → 422 `not_a_category`
- the deposit refund line with `{"category_id": <Juomat>}` → 422 `deposit_refund_line`
- `{"category_id": null}`, `{}` or `{"category_id": "12"}` → 422 `invalid_request`

and the lines keep their categories

### AC16: Line on another receipt
**Given** receipts A and B
**When** the client calls `PATCH /api/receipts/<A>/lines/<a line of B>` with a valid
category, or uses a line id that does not exist
**Then** the status is 404 with `error` `not_found`, and no line changes

### AC17: Confirming and cancelling
**Given** receipt B (with a warning), unreviewed
**When** the client calls `PATCH /api/receipts/<B>` with `{"reviewed": true}`, then
`GET /api/receipts`, then `PATCH` with `{"reviewed": false}`
**Then** the first answer is 200 with `reviewed` true; the list item of B has `reviewed`
true; the last answer has `reviewed` false

### AC18: Confirmation survives a category choice; bad confirmation body
**Given** receipt A, confirmed
**When** the client chooses a category for one of its lines, and then calls
`PATCH /api/receipts/<A>` with `{}` and with `{"reviewed": "yes"}`
**Then** the category answer has `reviewed` true; both later calls give 422
`invalid_request` and A stays confirmed

### AC19: Migration keeps existing receipts
**Given** a database at schema version 4 with two receipts
**When** the backend starts
**Then** the schema version is 5 and both receipts are `reviewed` false in `GET /api/receipts`

### AC20: Kuitit page lists the receipts
**Given** the API returns receipts A (confirmed) and B (unreviewed, warning)
**When** the user clicks the navigation link `Kuitit`
**Then** the address is `/kuitit`, the heading `Kuitit` and the table `Kuittilista` show
the rows `6.10.2026 | Kauppa B | 5,00 € | Summa ei täsmää | Tarkistamaton` and
`5.10.2026 | Testikauppa | 3,49 € |  | Vahvistettu`; the link has `aria-current="page"`

### AC21: Empty and incomplete rows in the list
**Given** the API returns no receipts, and then (after a reload) one receipt with
`purchase_date`, `total_cents` `null` and `store` `""`
**When** the Kuitit page opens
**Then** it first shows `Ei kuitteja. Tuo kuitit Tuonti-sivulla.`; then the row shows
`– | – | – | Summa ei täsmää | Tarkistamaton`

### AC22: Opening a receipt
**Given** the Kuitit page with receipt A
**When** the user clicks A's row
**Then** the address is `/kuitit/<A>` and the page shows the heading `Kuitti`, `Testikauppa`,
`5.10.2026`, `3,49 €`, `Tarkistamaton`, the button `Vahvista`, an image `Kuitin kuva` whose
source is `/api/receipts/<A>/image` inside a link to the same address with
`target="_blank"`, and the table `Kuittirivit` with the rows `Maito | 1,25 €` and
`Limu | 2,24 €`; the back link `Takaisin kuittilistaan` returns to `/kuitit`. Reloading
`/kuitit/<A>` shows the same receipt.

### AC23: Line categories in the receipt view
**Given** receipt A, plus a line `Outo` 50 without category and a deposit refund line
`Panttipalautus` -40
**When** the receipt page opens
**Then** the dropdown `Kategoria: Maito` has `Maitotuotteet` selected and no mark; `Kategoria:
Limu` has `Juomat` selected and the mark `ehdotus`; `Kategoria: Outo` shows
`Valitse kategoria`; the `Panttipalautus` row has no dropdown and shows `Pantinpalautus` and
`-0,40 €`; group names are headings that cannot be chosen

### AC24: Choosing a category updates the page
**Given** receipt A on the receipt page
**When** the user chooses `Maitotuotteet` in `Kategoria: Limu`
**Then** the UI sends `PATCH /api/receipts/<A>/lines/<Limu line>` with
`{"category_id": <Maitotuotteet>}`; after the answer the `ehdotus` mark is gone and the
subtotals show `Ruoka > Maitotuotteet 3,49 €` only, without reloading the page

### AC25: Line sum, subtotals and warning in the view
**Given** the receipt of AC8 with total 500 (line sum 458)
**When** the receipt page opens
**Then** it shows `Rivien summa 4,58 €`, the subtotals `Ruoka > Maitotuotteet 2,24 €`,
`Juomat 2,24 €`, `Ei kategoriaa 0,50 €` in this order, and with
`role="status"` the text `Rivien summa 4,58 € poikkeaa loppusummasta 5,00 €. Erotus 0,42 €.`;
receipt A shows no warning

### AC26: Warning without a total; no lines
**Given** the receipt of AC7
**When** the receipt page opens
**Then** it shows `–` for store, date and total, `Loppusumma puuttuu.` with
`role="status"`, and `Kuitilta ei luettu rivejä.` instead of the line table

### AC27: Confirming in the view
**Given** receipt A, unreviewed, on the receipt page
**When** the user clicks `Vahvista`, and then `Peru vahvistus`
**Then** the UI sends `PATCH /api/receipts/<A>` with `{"reviewed": true}` and the page shows
`Vahvistettu` and the button `Peru vahvistus`; after the second click it sends
`{"reviewed": false}` and shows `Tarkistamaton` and `Vahvista`

### AC28: Errors in the view
**Given** receipt A on the receipt page
**When** the category choice for `Limu` is answered with 422 `deposit_refund_line`, or the
confirmation with a network error
**Then** the backend's message (`Pantinpalautusriville ei voi valita kategoriaa.`), or
`Taustapalveluun ei saada yhteyttä.`, is shown with `role="alert"` next to the `Limu` line or
next to the button; `Limu` keeps `Juomat` selected and the state stays `Tarkistamaton`

### AC29: Receipt not found, image missing, load failure
**Given** the API answers `/api/receipts/999` with 404 `not_found`, the image of receipt A
with 404, and the list with a network error
**When** the user opens `/kuitit/999`, receipt A, and the Kuitit page
**Then** `/kuitit/999` shows `Kuittia ei löydy.` and the back link; receipt A shows
`Kuvaa ei löydy valmiiden kansiosta.` in place of the image and still shows its lines; the
Kuitit page shows `Taustapalveluun ei saada yhteyttä.` with `role="alert"`

### AC30: Money and date formatting
**Given** the formatting functions of PC10
**When** they format the amounts 0, 5, 125, -40, -125, 123456 and the dates `2026-10-05`,
`2026-01-15`
**Then** the results are `0,00 €`, `0,05 €`, `1,25 €`, `-0,40 €`, `-1,25 €`, `1234,56 €`,
`5.10.2026`, `15.1.2026`

### AC31: Review journey end to end
**Given** the E2E stack with fake engines and one new synthetic image imported from the
Tuonti page (the fake reader gives `Testikauppa`, 2026-10-05, `Maito` 1,25 €, `Limu` 2,24 €,
total 3,49 €). The E2E database lives as long as the `backend-e2e` container, so an earlier
run may already have stored the product `Maito`
**When** the user opens Kuitit, opens the newest receipt (the first row dated `5.10.2026`;
same-date receipts list the newest import first), chooses for `Maito` the category `Maitotuotteet`, or `Juomat`
when `Maitotuotteet` is already selected, and clicks `Vahvista`
**Then** `Maito` shows the chosen category without the mark `ehdotus`, the page shows no
warning, and back on Kuitit the receipt's row shows `Vahvistettu`; the Tuotteet page lists
the product `Maito` in the chosen category

## Files to Modify
| File | Change |
|---|---|
| `backend/app/storage/migrations/0005_receipt_review.sql` | Review state column on `receipts` (PC6) |
| `backend/app/storage/receipt_repository.py` | List receipts, get one, set review state; review state and line ids in the rows |
| `backend/app/calculation/__init__.py`, `backend/app/calculation/receipt_check.py` (new) | Line sum, difference, warning and category subtotals as pure functions (Plan P2) |
| `backend/app/review/` (new package: `routes.py`, `schemas.py`, `service.py`, `images.py`, `errors.py`) | Receipt list, receipt, image, line category and confirmation endpoints (PC1–PC5) |
| `backend/app/main.py` | Register the review routes |
| `backend/app/texts.py` | `image_missing` message |
| `backend/tests/unit/review/`, `backend/tests/unit/calculation/`, `backend/tests/unit/storage/` | Unit tests (see Testing Strategy); the existing repository tests that build `LineRow` get its new `id` field |
| `backend/tests/receipt_import_data.py` | The test repository's `add_line` override returns the new line id, as the base method now does |
| `backend/tests/integration/test_receipts_api.py` | Integration tests |
| `backend/tests/unit/storage/test_receipt_lines_schema.py` | Two tests pinned migration 4 as the newest, which migration 0005 changes by design: `test_ac22_existing_lines_have_no_category` (`== [4]`) checks that 4 is the first migration applied, and `test_ac13_migration_3_adds_read_fields_and_lines` compares the first eight `receipts` columns and allows the columns of later migrations, as it already does for the lines. The categorization spec made the same change for migration 3. What they verify stays the same |
| `frontend/src/navigation.ts` | Pages `receipts` and `receipt` with its id; `/kuitit` and `/kuitit/{id}` |
| `frontend/src/App.tsx` | `Kuitit` link and the two new pages |
| `frontend/src/api/receipts.ts` (+ test) | Typed receipt client |
| `frontend/src/format.ts` (+ test) | Money and date formatting (PC10) |
| `frontend/src/components/ReceiptsPage.tsx` (+ test) | Kuitit page |
| `frontend/src/components/ReceiptPage.tsx` (+ test) | Receipt page |
| `frontend/src/i18n/fi.ts` | Texts of the UI texts table |
| `frontend/src/test/receipts.ts` | MSW fixtures for receipts |
| `frontend/src/navigation.test.ts`, `frontend/src/App.test.tsx` | New cases for the receipt paths and the `Kuitit` link. One existing assertion changes by design: `AC31, AC26: the navigation opens the Tuotteet page` lists the navigation links, and PC7 adds `Kuitit` after `Tuonti`, as the receipt import spec added `Tuonti`. What it verifies (the links, Tuotteet current) stays the same |
| `frontend/e2e/import.spec.ts` | AC31, as a new test after the import tests in the same file: it imports through the shared test import folder, which the file's `beforeAll` empties, and only one import runs at a time, so a separate file running in parallel could break both |
| `docs/api-reference.md` | Receipt endpoints and `image_missing`; remove the note that no endpoint returns `deposit_refund_line` |
| `docs/datamodel.md` | Review state column, migration 0005, schema version 5 |
| `docs/subsystems/review/README.md` (new) | The review backend package: endpoints, view building, image lookup |
| `docs/subsystems/calculation/README.md` (new, In Progress) | The receipt check and subtotals; weekly and monthly totals come with the totals spec |
| `docs/subsystems/ui/README.md` | Kuitit and receipt pages, navigation with an id, formatting |
| `docs/subsystems/categorization/README.md` | The correction service now has an endpoint |
| `docs/subsystems/storage/README.md` | The new repository methods, migration 0005 and review as a user of storage |
| `docs/architecture.md` | The review package and its dependencies |
| `docs/content-plan.md` | The review README; the calculation README to In Progress |
| `docs/glossary.md` | Line sum, difference, review state, category subtotal |
| `specs/README.md` | Row for this spec |


## Risk
- **What could break:** startup (migration 0005 on a database with receipts); the category
  correction, which writes products and other lines (FR-36) and is now reachable from the
  UI; navigation, which gains a path with an id.
- **Security:** the image endpoint reads files from disk. It uses only the stored file name,
  and checks that the resolved path is inside the done folder (AC12).
- **Data:** a wrong category choice changes a product's remembered category; the user fixes
  it with another choice or on the Tuotteet page.
- **Rollback:** revert the change. Migration 0005 only adds a column with a default, so the
  old code still reads the database; the review state is ignored.
- **Dependencies:** none new.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC5 | `check_receipt` | refund in the line sum | 340 and -40, total 300 | compute | sum 300, difference 0, no warning | none |
| AC6 | `check_receipt` | difference | total 500, line 450 | compute | 450, 50, warning | none |
| AC7 | `check_receipt` | no total, no lines | total `None`, `[]` | compute | 0, `None`, warning | none |
| AC8 | `category_subtotals` | order and no-category | AC8 lines | compute | `Maitotuotteet`, `Juomat`, no category; no refund | catalog order given |
| AC2 | `ReceiptRepository.list` | order | AC2 receipts | list | R5, R2, R3, R4, R1 | real SQLite |
| AC17 | `ReceiptRepository.set_reviewed` | both ways | a receipt | set true, false | read back true, false | real SQLite |
| AC19 | migration 0005 | existing rows | version 4 with receipts | migrate | version 5, not reviewed | real SQLite |
| AC10 | image lookup | JPEG and PNG | files in a temp done folder | look up | bytes and content type | none |
| AC11 | image lookup | missing file, unreadable file | no file; a directory with the name | look up | `ImageMissingError` | none |
| AC12 | image lookup | path outside | `../secret.jpg`, absolute path | look up | `ImageMissingError` | none |
| AC30 | `formatCents`, `formatDate` | all values | AC30 values | format | AC30 results | none |
| AC20, AC21 | `ReceiptsPage` | rows, empty, missing fields | MSW lists | render | AC20, AC21 texts | MSW |
| AC29 | `ReceiptsPage` | load error | network error | render | alert | MSW |
| AC22 | `ReceiptPage` | header, image, lines | receipt A | render | AC22 texts and attributes | MSW |
| AC23 | `ReceiptPage` | dropdowns, mark, refund | AC23 receipt | render | AC23 | MSW |
| AC24 | `ReceiptPage` | choice | receipt A | choose | request body; page from answer | MSW |
| AC25, AC26 | `ReceiptPage` | sums and warnings | AC8 and AC7 receipts | render | AC25, AC26 texts | MSW |
| AC27 | `ReceiptPage` | confirm and cancel | receipt A | click twice | bodies and texts | MSW |
| AC28 | `ReceiptPage` | choice and confirm errors | 422; network error | act | alerts, old values kept | MSW |
| AC29 | `ReceiptPage` | not found; image missing | 404s | render; image `error` event | texts | MSW |
| AC20, AC22 | `pageFromPath`, `App` | paths | `/kuitit`, `/kuitit/7`, `/kuitit/x`, `/` | map; click | `receipts`, `receipt` 7, `receipts`, `products`; `aria-current` | MSW |

### Integration tests
Real SQLite (temporary file), real FastAPI app, temporary done folder; engines faked.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | list | `GET /api/receipts` | AC1 body | 200 |
| AC2 | order | `GET /api/receipts` | AC2 ids | 200 |
| AC3 | empty | `GET /api/receipts` | `[]` | 200 |
| AC4 | receipt | `GET /api/receipts/<A>` | AC4 fields, no `ocr_text` | 200 |
| AC5, AC6, AC8 | sums | `GET /api/receipts/<id>` | AC values | 200 |
| AC7 | old receipt | `GET` receipt and list | AC7 values | 200 |
| AC9 | unknown id | three calls | `not_found` | 404 |
| AC10 | image | `GET /api/receipts/<A>/image` | bytes, `image/jpeg`; PNG `image/png` | 200 |
| AC11 | missing image | file removed | `image_missing` | 404 |
| AC12 | path outside | stored `../secret.jpg` | `image_missing` | 404 |
| AC13 | choice | `PATCH .../lines/<id>` | AC13 receipt; product exists | 200 |
| AC14 | same product twice | `PATCH` line 1 | AC14 lines | 200 |
| AC15 | choice errors | AC15 bodies | AC15 codes; lines unchanged | 422 |
| AC16 | line elsewhere | `PATCH` | `not_found`; nothing changed | 404 |
| AC17 | confirm, cancel | `PATCH /api/receipts/<B>` | AC17 | 200 |
| AC18 | confirmation kept; bad body | choice, then `PATCH` | AC18 | 200, 422 |
| AC19 | migration at start | version 4 database | version 5, `reviewed` false | 200 |
| PC11 | no names in logs | AC13 request with captured logs | no line, product or category name in the log | 200 |

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC31 | Import, review, correct, confirm | AC31 steps | AC31 outcome |

### Coverage target
- Backend: 90 % lines for the new review code; every branch of the sums, the warning and the
  image lookup.
- Frontend: every component state in the UI texts table is rendered by a test.

### Test data
- Synthetic fixtures only: invented stores and product names (`Testikauppa`, `Kauppa B`,
  `Maito`, `Limu`, `Jogurtti`, `Olut`, `Outo`, `Panttipalautus`), the default catalog,
  synthetic JPEG and PNG bytes (signatures followed by text, not real images).
- Mocks: MSW for component tests; fake engines (`RRMC_ENGINES=fake`) for integration and
  E2E.

## Related Documentation (MANDATORY)
- Tier 1: [PRD](../PRD.md) sections 5, 6.4 and 9; [architecture](../../docs/architecture.md);
  [datamodel](../../docs/datamodel.md); [API reference](../../docs/api-reference.md);
  [development](../../docs/development.md#code-standards)
- Tier 2: [ui](../../docs/subsystems/ui/README.md),
  [categorization](../../docs/subsystems/categorization/README.md),
  [import](../../docs/subsystems/import/README.md),
  [storage](../../docs/subsystems/storage/README.md)
- ADRs: [0004 line categorization](../../docs/adr/0004-line-categorization.md)
- Specs: [Line categorization](categorization.md), [Receipt reading](receipt-reading.md),
  [Receipt import](receipt-import.md)

## Plan

### P1 Where the code goes

| Package | Holds | Depends on |
|---|---|---|
| `storage` | SQL: receipt list with line sums, one receipt, review state; line ids | SQLite |
| `calculation` (new) | `check_receipt`, `category_subtotals`: pure functions on integer cents, no I/O | nothing |
| `categorization` | `LineCategoryService.set_category` and `CategoryService.list` (both exist) | `storage` |
| `review` (new) | Routes, schemas, `ReviewService` that builds the receipt view, image lookup | `storage`, `calculation`, `categorization`, `settings` |

The architecture already plans **calculation** for "receipt subtotals; line-sum vs receipt
total check" (FR-19, FR-20), so the receipt sums start it now; the totals spec adds the
weekly and monthly totals there. **review** is a new backend package because the receipt
view combines three subsystems and belongs to none of them: `import` is about runs, and
`categorization` must not calculate. The line editing spec extends it. Nothing depends on
`review`. The component map and dependency rules in `docs/architecture.md` get both
packages. No ADR: this follows the subsystem split the architecture already plans.

### P2 calculation: `app/calculation/receipt_check.py`

```python
@dataclass(frozen=True)
class ReceiptCheck:
    line_sum_cents: int
    difference_cents: int | None  # None without a total
    warning: bool


def check_receipt(total_cents: int | None, amounts: Iterable[int]) -> ReceiptCheck: ...


@dataclass(frozen=True)
class SubtotalLine:  # what the subtotals need from a line
    category_id: int | None
    amount_cents: int
    is_deposit_refund: bool


@dataclass(frozen=True)
class Subtotal:
    category_id: int | None  # None: lines without a category
    amount_cents: int


def category_subtotals(lines: Iterable[SubtotalLine], order: Sequence[int]) -> list[Subtotal]: ...
```

`check_receipt` sums every amount, refunds included; the warning is on when the total is
`None` or the difference is not 0. `category_subtotals` skips refunds, sums per category,
sorts by the position of the category id in `order` (the ids of `CategoryService.list()`),
and adds the no-category subtotal last when it has lines. A category id missing from
`order` cannot happen (`ON DELETE RESTRICT`); such a subtotal would sort after the known
ones and before no-category instead of raising.

### P3 storage

- **Migration `0005_receipt_review.sql`:**
  `ALTER TABLE receipts ADD COLUMN reviewed INTEGER NOT NULL DEFAULT 0 CHECK (reviewed IN (0, 1));`
  A flag like `is_deposit_refund`; no requirement needs the time of the confirmation.
- **`ReceiptRow`** gets `reviewed: bool = False`, read by `_receipt`. Import never sets it,
  so `add` keeps its signature.
- **`LineRow`** gets `id: int` as its first field, and `lines()` selects it. The tests that
  build a `LineRow` add the id (a field added to a type, not a change of what they verify).
- **New `ReceiptRepository` methods:**
  - `summaries() -> list[ReceiptSummaryRow]` (`id`, `store`, `purchase_date`,
    `total_cents`, `reviewed`, `line_sum_cents`): one query with
    `LEFT JOIN receipt_lines ... GROUP BY receipts.id`, `COALESCE(SUM(amount_cents), 0)`
    and `ORDER BY purchase_date IS NOT NULL, purchase_date DESC, id DESC` (PC1, AC2). The
    sum is taken in SQL so the list needs no query per receipt; `check_receipt` then gets
    it as a one-item list.
  - `get(receipt_id) -> ReceiptRow | None`.
  - `set_reviewed(receipt_id, reviewed: bool) -> bool`: `False` when no row changed (the
    id does not exist).

### P4 review backend

- **`images.py`:** `read_image(done_dir: Path, file_name: str) -> tuple[bytes, str]`
  returns the bytes and `image/jpeg` or `image/png`. It raises `ImageMissingError` (404
  `image_missing`) when the name is not a plain file name (`PurePath(file_name).name !=
  file_name`, which catches `..`, separators and absolute paths), when the resolved path's
  parent is not `done_dir.resolve()`, on any `OSError` (missing file, a directory, no
  permission), or when the bytes start with neither signature. The type comes from the
  signature, not the name (spec PC3). The two signatures are written again here with a
  comment pointing to @backend/app/receipt_import/files.py: `review` must not import from
  `import`, and two constants do not justify a shared module.
- **`service.py`, `ReviewService(catalog: CatalogRepository, receipts: ReceiptRepository)`**,
  both on one connection, as `LineCategoryService` requires:
  - `summaries() -> list[ReceiptSummary]`: the rows with `check_receipt(...).warning`.
  - `receipt(receipt_id) -> ReceiptView`: the row, its lines, and `CategoryService.list()`
    once. Each line's `category_name` and `group_name` come from that list (a map from id to
    row, and the parent's name), so no new join is needed. Then `check_receipt` and
    `category_subtotals`. Raises `NotFoundError`.
  - `set_line_category(receipt_id, line_id, category_id) -> ReceiptView`: `get_line`; a
    missing line or one with another `receipt_id` raises `NotFoundError` before
    `LineCategoryService.set_category` runs (AC16); then returns `receipt(receipt_id)`.
  - `set_reviewed(receipt_id, reviewed) -> ReceiptView`: `NotFoundError` when no row
    changed.
  - `image(receipt_id, done_dir) -> tuple[bytes, str]`: `NotFoundError` for an unknown
    receipt (AC9), else `read_image`.

  `NotFoundError` is the catalog's (@backend/app/categorization/errors.py), already 404
  `not_found`.
- **`schemas.py`:** `ReceiptSummaryOut`, `ReceiptOut`, `LineOut`, `SubtotalOut` as in the
  spec's API shapes, each with a `from_*` constructor; `LineCategoryUpdate(category_id:
  StrictInt)` and `ReviewUpdate(reviewed: StrictBool)`. The strict types reject `"12"` and
  `"yes"`, which Pydantic's lax mode would accept (AC15, AC18). A missing field or `null`
  fails because the fields are required and not optional. All give `invalid_request`.
- **`routes.py`, `create_review_router(settings)`:** one connection per request, as in
  `create_catalog_router`. `GET /api/receipts`, `GET /api/receipts/{receipt_id}`,
  `GET /api/receipts/{receipt_id}/image` (a `Response` with the bytes, the media type and
  `Cache-Control: no-store`, so a replaced file is not shown from the browser cache),
  `PATCH /api/receipts/{receipt_id}`, `PATCH /api/receipts/{receipt_id}/lines/{line_id}`.
- **`errors.py`:** `ImageMissingError`; its text `IMAGE_MISSING` in @backend/app/texts.py.
- **`main.py`:** `app.include_router(create_review_router(settings))`.

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
  U->>U: show the answer (FR-19)
```

### P5 frontend

- **`navigation.ts`:** `Page` gains `"receipts"` and `"receipt"`. `PAGE_PATHS` gains
  `receipts: "/kuitit"` and becomes `Record<Exclude<Page, "receipt">, string>`, because a
  receipt has no fixed path. `pageFromPath` maps `/kuitit` to `receipts`,
  `/kuitit/<positive integer without leading zeros>` to `receipt`, and any other
  `/kuitit/...` to `receipts`. New `receiptIdFromPath(pathname): number | null` and
  `receiptPath(id)`. `usePage()` returns `[page, go, receiptId]` with
  `go(page, receiptId?)`; existing callers that take `[page, go]` keep working.
- **`App.tsx`:** link `Kuitit` after `Tuonti`. `ReceiptsPage` gets `onOpen(id)`,
  `ReceiptPage` gets `id` and `onBack()`. The left-click check of the navigation links
  becomes a small helper that the list links and the back link use too.
- **`api/receipts.ts`:** types `ReceiptSummary`, `Receipt`, `ReceiptLine`, `Subtotal`,
  `CategorySource`; `listReceipts()`, `getReceipt(id)`,
  `setLineCategory(receiptId, lineId, categoryId)`, `setReviewed(id, reviewed)`,
  `receiptImageUrl(id)`, all on the shared client.
- **`format.ts`:** `formatCents(cents)` with integer arithmetic only (sign, division,
  `padStart`); no `Intl`, whose minus sign and spaces differ from PC10.
  `formatDate("YYYY-MM-DD")` splits the string, so no time zone can move the date.
- **`ReceiptsPage`:** loads the list on mount and shows the table `Kuittilista`. The date
  cell holds a real link to `/kuitit/<id>` (its text is the date or `–`), handled like the
  navigation links.
- **`ReceiptPage`:** loads the receipt and `GET /api/categories` in parallel. Layout: a
  flex container that wraps on narrow windows, the image (`max-width: 100%`) in one column
  and the table in the other, with inline styles: the app has no stylesheet yet, and one
  layout rule does not justify one. The image's `onError` replaces it with the
  `image_missing` text, because an `img` cannot read the 404 body. While a category or
  confirmation request is waiting, every dropdown and the button are disabled, so answers
  cannot arrive out of order. Each line keeps its own error; its next choice clears it. A
  categories load error is shown at the top with `role="alert"`, and the dropdowns stay
  disabled.
- **`test/receipts.ts`:** fixtures for receipt A, receipt B and the AC7 and AC8 receipts,
  and MSW handlers that answer a `PATCH` with a fixture the test gives (no backend rules).

### P6 Plan against the ACs

| ACs | Covered by |
|---|---|
| AC1–AC3; AC7 in the list | P3 `summaries`, P4 `ReviewService.summaries` |
| AC4–AC8 | P2; P4 `receipt` |
| AC9 | P4 `NotFoundError` in `receipt`, `image`, `set_reviewed` |
| AC10–AC12 | P4 `read_image` |
| AC13–AC16 | P4 `set_line_category`, then the existing `LineCategoryService` |
| AC17, AC18 | P3 `set_reviewed`; P4 strict schemas |
| AC19 | P3 migration 0005 |
| AC20–AC30 | P5 |
| AC31 | P5 against the real backend with fake engines |
| PC11 | the existing request logging; no new log lines |

### Dependencies

None to add.

## Tasks

Each task is one Red → Green → Refactor cycle unless it says otherwise. Backend unit tests go
to `backend/tests/unit/calculation/`, `backend/tests/unit/review/` or next to the existing
ones in `unit/storage/`; API tests go to the new
`backend/tests/integration/test_receipts_api.py`. Frontend tests sit next to their files.
Test names start with the AC ID. After every task the tests, lint, format check and type
check of the changed part pass. Existing assertions are never edited; the only change to
existing tests is the new `id` argument of `LineRow` (T2).

### Storage

- [x] **T1 Migration 0005 (AC19, PC6).** Tests in `unit/storage/test_receipts_schema.py`:
  `test_ac19_existing_receipts_are_unreviewed` (a version 4 database with two receipts,
  migrated: version 5, `reviewed` 0); `reviewed` 2 raises `sqlite3.IntegrityError`. Green:
  P3 migration.
- [x] **T2 Line ids and review state in the rows (P3).** Tests in
  `test_receipt_repository.py`: `lines()` returns each line's id; `get()` returns the row
  with `reviewed` False, and `None` for a missing id; `set_reviewed` both ways, and `False`
  for a missing id. Green: `LineRow.id`, `ReceiptRow.reviewed`, `get`, `set_reviewed`; the
  existing `LineRow(...)` calls in the tests get the id.
- [x] **T3 Receipt summaries (AC2, AC3).** `test_ac2_summaries_order` (R1–R5 of AC2),
  `summaries()` on an empty database is `[]`, and `line_sum_cents` sums lines including a
  refund and is 0 without lines. Green: `summaries`, `ReceiptSummaryRow`.

### Calculation

- [x] **T4 Receipt check (AC5–AC7).** Tests in `unit/calculation/test_receipt_check.py`:
  `test_ac5_refund_is_in_the_line_sum`, `test_ac6_difference_gives_a_warning`,
  `test_ac7_no_total_gives_a_warning` (also with no lines: sum 0), and a negative
  difference (total 400, lines 450: -50, warning). Green: `check_receipt`.
- [x] **T5 Category subtotals (AC8).** `test_ac8_subtotals_in_catalog_order` (AC8 lines,
  order with `Maitotuotteet` before `Juomat`); no no-category subtotal when every line has
  a category; only refunds gives `[]`; a category missing from `order` sorts before
  no-category. Green: `category_subtotals`.

### Review backend

- [x] **T6 Image lookup (AC10–AC12).** Tests in `unit/review/test_images.py` with a
  temporary done folder: `test_ac10_jpeg_and_png` (bytes and type);
  `test_ac11_missing_or_unreadable` (no file, a directory with the name, a file with a text
  signature); `test_ac12_name_outside_the_done_folder` (`../secret.jpg`, an absolute path,
  `sub/kuitti.jpg`) each raise `ImageMissingError`, and the outside file is never read.
  Green: `read_image`, `ImageMissingError`, `texts.IMAGE_MISSING`.
- [x] **T7 Receipt view (AC4–AC8).** Tests in `unit/review/test_review_service.py` on real
  SQLite with the default catalog: `test_ac4_lines_with_category_names` (group `Ruoka`
  and `null`, sources), `test_ac8_view_subtotals`, `test_ac7_receipt_before_reading`,
  unknown id raises `NotFoundError`. Green: `ReviewService.receipt`, `ReceiptView`.
- [x] **T8 Summaries with warning (AC1, AC7).** `test_ac1_summaries_with_warning`,
  `test_ac7_old_receipt_has_a_warning`. Green: `ReviewService.summaries`.
- [x] **T9 Category choice through the view (AC13, AC14, AC16).**
  `test_ac13_choice_creates_the_product`, `test_ac14_choice_moves_the_same_product`,
  `test_ac16_line_on_another_receipt_is_not_found` (and a missing line id): nothing
  changes. Green: `ReviewService.set_line_category`.
- [x] **T10 Confirmation and image through the service (AC9, AC17).**
  `set_reviewed` both ways; unknown id raises `NotFoundError` for `set_reviewed` and
  `image`. Green: `ReviewService.set_reviewed`, `ReviewService.image`.
- [x] **T11 Endpoints (AC1–AC19, PC11).** Integration tests in `test_receipts_api.py`, one
  per row of the Testing Strategy's integration table, including AC15's strict-body cases,
  AC18, AC19 (start on a version 4 database) and the log check of PC11. Green: schemas,
  `create_review_router`, `main.py`. This task may need several Red → Green rounds, one per
  endpoint.

### Frontend

- [x] **T12 Formatting (AC30).** `format.test.ts`: every value of AC30. Green: `format.ts`.
- [x] **T13 Receipt client (P5).** `api/receipts.test.ts`: each function calls the right
  method, path and body, and returns the shared client's result; `receiptImageUrl(3)` is
  `/api/receipts/3/image`. Green: `api/receipts.ts`.
- [x] **T14 Navigation (AC20, AC22).** New cases in `navigation.test.ts`: `/kuitit`,
  `/kuitit/7`, `/kuitit/07`, `/kuitit/x`, `/kuitit/7/x`; `receiptIdFromPath`;
  `go("receipt", 7)` pushes `/kuitit/7`; back button. Green: `navigation.ts`.
- [x] **T15 Kuitit page (AC20, AC21, AC29).** `ReceiptsPage.test.tsx` with
  `test/receipts.ts`: rows of AC20, empty and incomplete rows of AC21, the load error of
  AC29, a click on the date link calls `onOpen` with the id. Green: `ReceiptsPage`, texts in
  `fi.ts`.
- [x] **T16 Receipt page: showing (AC22, AC23, AC25, AC26, AC29).** `ReceiptPage.test.tsx`:
  header, image and link attributes, line rows, dropdown values, the `ehdotus` mark, the
  refund row, line sum, subtotals, both warnings, no lines, not found, image `error` event,
  categories load error. Green: `ReceiptPage` without actions.
- [x] **T17 Receipt page: actions (AC24, AC27, AC28).** Choice request body and the page
  from the answer; controls disabled while waiting; confirm and cancel; choice and
  confirmation errors keep the old values. Green: the actions.
- [x] **T18 App shell (AC20, AC22).** New cases in `App.test.tsx`: the `Kuitit` link with
  `aria-current`, opening a receipt from the list, the back link, a reload at
  `/kuitit/<id>`. Green: `App.tsx` and the click helper.

### End to end and docs

- [x] **T19 E2E journey (AC31).** A new test in `frontend/e2e/import.spec.ts` (see Files to Modify). Green: fixes found by the
  run, if any (each through a failing unit or component test first).
- [x] **T20 Docs (no AC).** Update the docs listed in Files to Modify: API reference,
  datamodel, architecture, ui, categorization, the new review and calculation READMEs,
  content plan, glossary, `specs/README.md`. Check every command and link.
- [x] **T21 Full check.** All commands of the AGENTS.md table: backend tests, lint, format,
  type check; frontend tests, lint, format, type check; E2E; container tests. Then hand over
  to `review-audit`.

## Audit

Audited 2026-10-31 by an independent review against this spec: **PASS**.

- Acceptance criteria 31/31 and PC1–PC11 met; every Testing Strategy row has a test.
- Tests: backend 753 passed, frontend 117 passed, E2E 7 passed (twice, on a kept database),
  container tests passed; ruff, pyright, ESLint and tsc clean. Coverage of `app.review` and
  `app.calculation`: 100 % lines (target 90 %).
- Security: no findings. `npm audit`: 0 vulnerabilities. `pip-audit`, added to the backend's
  dev dependencies at the user's request after the audit: no known vulnerabilities.
- Format check: `frontend/e2e/products.spec.ts`, not touched by this spec, fails
  `npm run format:check` because its working copy has CRLF line endings; the content in Git
  is fine.
- Fixed during the audit: the storage README row added to Files to Modify; two component
  tests added (the receipt page's field labels and column headers; a line's error clears on
  its next choice).
- Later (proposed for the line editing spec):
  - AC15's integration test puts the deposit refund line on its own receipt, not on receipt
    A; the behavior checked is the same.
  - While the categories load, or after they fail, each dropdown shows `Valitse kategoria`;
    showing the category name as text would mislead less.
  - An id above SQLite's integer range gives 500 instead of 404 or 422 (as in the catalog
    routes).
  - Extra fields in a request body are ignored; the line editing spec could forbid them.

<!-- The Plan phase appends "## Plan" and the Tasks phase appends "## Tasks" below. -->
