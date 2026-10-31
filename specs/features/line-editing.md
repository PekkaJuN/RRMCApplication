# Feature: Line editing

## Overview
- **Status:** Done
- **Created:** 2026-10-31
- **Updated:** 2026-10-31: user answers: quantity and unit price are left out (a PRD note
  on FR-18, as the FR-8 note); fields are edited inline and saved when the field is left or
  on Enter; the deposit refund flag is editable; the four items the receipt review audit
  proposed are included (extra body fields refused, ids out of range give 404, category
  names as text while the categories load, the AC15 test on receipt A). Specify approved
  by the user; Plan added. Plan approved by the user; Tasks added; spec approved by the user; implementation started; Files to Modify updated during T8 (the receipt-review service tests that call the replaced methods); PC1 clarified during T10 (only sent values are checked), with a regression test under AC7; Files to Modify updated during T19 (two `App.test.tsx` tests that read the store as text) and T22 (the receipt-review E2E test finds the `Maito` row by its input).
- **Depends on:** [Receipt review](receipt-review.md), [Line categorization](categorization.md)
- **Implements:** PRD FR-18 (without quantity and unit price, see [Out of Scope](#out-of-scope)),
  FR-43, FR-19 (after every edit), FR-44 (for edited and added lines); NFR-1, NFR-3, NFR-9,
  NFR-15 for the edits.
- **Affected subsystems:** [review](../../docs/subsystems/review/README.md),
  [categorization](../../docs/subsystems/categorization/README.md) (FR-43 and the product
  match of a new line), [storage](../../docs/subsystems/storage/README.md),
  [ui](../../docs/subsystems/ui/README.md)

## Problem Statement
OCR and the model make mistakes: a product name is misspelled, an amount is wrong, a line is
missing or doubled, a deposit refund is read as a normal line, or the store, date or total is
wrong or empty. Today the user can only choose a line's category and confirm the receipt, so
these mistakes go into the totals unchanged, and a receipt with a wrong line keeps its
warning. A misspelled name also never matches the product the user already has, so the
category is not remembered (FR-43). This spec lets the user fix the receipt in the receipt
view (PRD section 5, step 5).

## Current Behavior
- The receipt page shows the store, date and total as text, and each line's name and amount
  as text with a category dropdown ([ui](../../docs/subsystems/ui/README.md)).
- `PATCH /api/receipts/{id}` takes only `{"reviewed": bool}`, and
  `PATCH /api/receipts/{id}/lines/{line_id}` takes only `{"category_id": n}`
  ([API reference](../../docs/api-reference.md#receipts)). Extra body fields are ignored.
- A receipt line has a name, an amount, the deposit refund flag, a category, its source and a
  product link ([datamodel](../../docs/datamodel.md#receipt_lines)). Quantity and unit price
  are not stored (PRD FR-8 note).
- A line gets its category at import: a matching product first, else a model suggestion
  ([categorization](../../docs/subsystems/categorization/README.md#line-categorization)).
- The review state does not change when a line's category changes (receipt-review PC5).
- This spec changes three receipt-review UI details: the store, date, total, line names and
  amounts become inputs (receipt-review AC22, AC23, AC26 showed them as text, with `–` when
  missing); controls are no longer disabled while a save waits (AC24); and a dropdown is no
  longer shown disabled while the categories load or after they fail (AC29).
- An id above SQLite's integer range gives 500 on the receipt routes.

## Proposed Change

### Concepts

- A line's **name match** is the product whose normalized name equals the line's normalized
  name ([names](../../docs/subsystems/categorization/README.md#names)).
- A **normal line** is a line that is not a deposit refund.
- A line is **resolved** when it gets its category from its name match alone: the product's
  category, source `remembered`, linked to the product; with no name match it has no
  category, no source and no link. Resolving never calls the model (NFR-9).
- An **edit** is any change this spec adds: a line's name, amount or deposit refund flag, a
  new line, a deleted line, or the store, date or total.

### Parts

- **PC1 Line edit endpoint (FR-18, FR-43).** `PATCH /api/receipts/{id}/lines/{line_id}`
  takes any non-empty set of the fields `name`, `amount_cents`, `is_deposit_refund` and
  `category_id`. The request is applied in one transaction in this order: the deposit
  refund flag and amount, then the name, then the category; if any rule fails, nothing
  changes. Only the sent values are checked against PC2 and PC3, so a name read from a
  receipt that is longer than 100 characters does not stop an amount edit; the refund rule
  of PC3 and PC4 is checked on the resulting line. The answer is the whole receipt as today (receipt-review PC2).
- **PC2 Line name (FR-43).** The name is stored as display form (trimmed, inner spaces
  collapsed, NFC) and must be 1–100 characters, as a product name. For a normal line whose
  normalized name changes:
  - with a name match, the line takes the product's category, source `remembered`, and is
    linked to it;
  - without a name match, a line with a category keeps it, a new product with the new name
    and that category is created, and the line is linked to it with source `user` (as in
    FR-13); a line without a category stays without one and no product is created.

  The product the line followed before is not changed, and neither are the other lines that
  follow it. A name whose normalized form does not change (case or spacing only) changes the
  name alone. A deposit refund's name changes the name alone.
- **PC3 Line amount (FR-18).** `amount_cents` is an integer from -99 999 999 to 99 999 999
  (±999 999,99 €). Any value is allowed on a normal line, also 0 and negative values. A
  deposit refund's amount must be below 0. Changing the amount changes nothing else on the
  line.
- **PC4 Deposit refund flag (FR-44).** `is_deposit_refund: true` makes the line a deposit
  refund: its category, source and link are cleared. The resulting amount must be below 0
  (the amount in the same request, else the stored one). `is_deposit_refund: false` makes a
  refund a normal line, which is then resolved. Sending the flag the line already has
  changes nothing. A `category_id` in the same request as `is_deposit_refund: true`, or for a
  line that stays a refund, is `deposit_refund_line`.
- **PC5 Category in the same request.** `category_id` works as today (FR-13, FR-36) and is
  applied last, so a request with `name` and `category_id` stores the chosen category for the
  new name.
- **PC6 Add a line (FR-18).** `POST /api/receipts/{id}/lines` with `name`, `amount_cents` and
  optionally `is_deposit_refund` (default `false`) adds a line after the last one (position:
  the largest position plus 1, or 1 on a receipt without lines). The name and amount follow
  PC2–PC4. A normal line is resolved. The answer is 201 with the whole receipt.
- **PC7 Delete a line (FR-18).** `DELETE /api/receipts/{id}/lines/{line_id}` deletes the
  line. The other lines keep their positions, and products are not changed. The answer is
  200 with the whole receipt.
- **PC8 Receipt fields (FR-18).** `PATCH /api/receipts/{id}` takes any non-empty set of
  `store`, `purchase_date`, `total_cents` and `reviewed`:
  - `store`: display form as for names, 0–100 characters; `""` means no store;
  - `purchase_date`: a real calendar date as `YYYY-MM-DD`;
  - `total_cents`: an integer from 0 to 99 999 999.

  None of them can be set back to `null`. The answer is the whole receipt.
- **PC9 Review state.** An edit never changes the review state (as receipt-review PC5
  states for category choices). `reviewed` in the same request as receipt fields is applied
  as well.
- **PC10 Strict request bodies.** Every receipt request body refuses fields it does not
  know, `null` values, and values of the wrong JSON type (`"12"` for a number, `1` for a
  boolean) with `invalid_request`. An empty body `{}` is `invalid_request`.
- **PC11 Ids out of range.** On every `/api/receipts` route, a receipt id or line id outside
  SQLite's integer range (-2^63 to 2^63-1) gives 404 `not_found`, and a `category_id`
  outside it gives 422 `unknown_category`, instead of 500.
- **PC12 Inline editing on the receipt page (FR-16, FR-18, FR-19).** The store, the date (a
  date input) and the total are inputs under their labels. Each line has a name input, an
  amount input, a deposit refund checkbox, the category dropdown (or `Pantinpalautus` for a
  refund) and a delete button.
  - A missing store, date or total (`null`, or `""` for the store) is an empty input; the
    `–` of receipt-review AC26 is no longer shown for them. A line amount shows as in PC13.
  - A text or date field saves when it loses focus or on Enter, and only if its value
    changed. Esc puts back the saved value without saving.
  - The checkbox saves when it is clicked.
  - Delete asks for confirmation in place (`ConfirmDelete`, as on Tuotteet).
  - Below the line table, a form adds a line: name, amount, deposit refund checkbox and the
    button `Lisää rivi`. After a successful add the form is empty again.
  - After every answer the page shows the receipt from the answer, so sums, subtotals,
    warning and marks update without a reload (FR-19).
  - The user can go on to the next field while a save waits for its answer. Saves are sent
    one at a time, in the order they were made.
- **PC13 Amount input.** An amount field accepts an optional minus sign, digits, and
  optionally a comma or a dot followed by one or two digits, with spaces around it ignored:
  `1,25`, `1.25`, `-0,40`, `3`, `3,5`. Anything else (also an empty field and thousands
  separators like `1 234,00`) is not sent and shows `Anna summa muodossa 1,25.` with
  `role="alert"` next to the field. An amount field shows its value with a decimal comma and
  two decimals and no `€` (`125` → `1,25`, `-40` → `-0,40`).
- **PC14 Errors on the receipt page.** A failed save shows the backend's `message` (or the
  network message) next to its field with `role="alert"`. A text field keeps the typed value
  so the user can fix it; Esc puts back the saved value and clears the message. The checkbox
  goes back to the saved state. A failed add keeps the form's values. The message clears on
  the field's next successful save.
- **PC15 Categories while they load.** While the categories load, or after the load failed,
  a normal line's category cell shows its category as text (`Ryhmä > Kategoria`, or the
  name alone for a category without a group, or `–` without a category) instead of a
  dropdown.
- **PC16 Privacy (NFR-1, NFR-3).** As today: logs carry method, path and status only; error
  messages hold no receipt content; new products are stored only in the local database.

### UI texts

New texts; the receipt-review texts stay as they are.

| Place | Text |
|---|---|
| Store, date and total inputs (`<label>`) | `Kauppa`, `Päivä`, `Loppusumma` (as today) |
| Line name input (`aria-label`) | `Tuote: <line name>` |
| Line amount input (`aria-label`) | `Summa: <line name>` |
| Line deposit refund checkbox (`aria-label`) | `Pantinpalautus: <line name>` |
| Line table columns | `Tuote`, `Summa`, `Pantinpalautus`, `Kategoria`, (empty for the delete column) |
| Delete button and confirmation | `Poista`, then `Poistetaanko?` with `Poista` and `Peruuta` (`ConfirmDelete`, as on Tuotteet) |
| Add form heading | `Uusi rivi` |
| Add form inputs (`<label>`) | `Tuote`, `Summa`, `Pantinpalautus` |
| Add button | `Lisää rivi` |
| Amount that cannot be read | `Anna summa muodossa 1,25.` |

`<line name>` is the saved name, so a label does not change while the user types.

### API shapes

Line edit (PC1), any non-empty subset:

```json
{"name": "Kivennäisvesi", "amount_cents": 199, "is_deposit_refund": false, "category_id": 12}
```

New line (PC6):

```json
{"name": "Banaani", "amount_cents": 99, "is_deposit_refund": false}
```

Receipt fields (PC8), any non-empty subset:

```json
{"store": "Testikauppa", "purchase_date": "2026-10-05", "total_cents": 349, "reviewed": true}
```

Every answer is the receipt of the receipt-review spec, unchanged.

### Error codes

| Status | `error` | `message` | When |
|---|---|---|---|
| 404 | `not_found` | `Pyydettyä kohdetta ei löydy.` | Receipt or line does not exist, the line is on another receipt, or the id is out of range (PC11) |
| 422 | `invalid_name` | `Nimen pituuden on oltava 1–100 merkkiä.` | Line name empty or too long (PC2) |
| 422 | `invalid_amount` (new) | `Summa ei kelpaa.` | Line amount or total outside its range (PC3, PC8) |
| 422 | `deposit_refund_amount` (new) | `Pantinpalautuksen summan on oltava negatiivinen.` | A deposit refund whose resulting amount is 0 or more (PC3, PC4) |
| 422 | `invalid_date` (new) | `Päivämäärä ei kelpaa.` | Not a real date as `YYYY-MM-DD` (PC8) |
| 422 | `invalid_store` (new) | `Kaupan nimi saa olla enintään 100 merkkiä.` | Store longer than 100 characters (PC8) |
| 422 | `unknown_category`, `not_a_category`, `deposit_refund_line` | as today | The category part (PC4, PC5, PC11) |
| 422 | `invalid_request` | `Pyyntö on virheellinen.` | PC10 |

### Out of Scope
- Quantity and unit price (FR-18): not read and not stored (FR-8 note). A PRD note on FR-18
  records this; a later spec adds them if the user wants them.
- Moving lines to another position, and splitting or merging lines.
- Asking the model for a category for a renamed or added line: resolving uses the name
  match only (NFR-9, the model takes seconds on the CPU).
- Renaming a product from a line: the product is renamed on the Tuotteet page.
- Clearing a line's category back to none, and setting the store, date or total back to
  empty (`null`).
- Undo of an edit or a deletion; deleting a whole receipt.
- Weekly and monthly totals (FR-22–FR-25): the totals spec. They will read the edited data.
- Fuzzy name matching (FR-14 note).

## Acceptance Criteria

The examples use the default catalog (`Maitotuotteet` in the group `Ruoka`, `Juomat` without
a group) and two products: `Maito` and `Jogurtti`, both in `Maitotuotteet`. Receipt A: store
`Testikauppa`, date 2026-10-05, total 349, unreviewed, lines 1 `Maito` 125 (`Maitotuotteet`,
`remembered`, linked to `Maito`) and 2 `Limu` 224 (`Juomat`, `model`, not linked). Receipt B
has one line `Maito` 125 linked to `Maito`. "Nothing changes" means the receipt, its lines
and the products read back the same as before the request.

### AC1: Renamed line without a name match becomes a new product
**Given** receipt A, and no product `Kivennäisvesi`
**When** the client calls `PATCH /api/receipts/<A>/lines/<Limu>` with
`{"name": "  Kivennäisvesi  "}`
**Then** the status is 200; the line has `name` `Kivennäisvesi`, `category_name` `Juomat`,
`category_source` `user`; a product `Kivennäisvesi` in `Juomat` exists and the line is
linked to it

### AC2: Renamed line with a name match follows the product
**Given** receipt A
**When** the client renames `Limu` to `JOGURTTI`
**Then** the line has `name` `JOGURTTI`, `category_name` `Maitotuotteet`, `group_name`
`Ruoka`, `category_source` `remembered` and is linked to `Jogurtti`; `subtotals` is
`Maitotuotteet` 349 only; no product was created

### AC3: Renaming a linked line leaves the old product alone
**Given** receipts A and B, and no product `Kaurajuoma`
**When** the client renames A's `Maito` line to `Kaurajuoma`
**Then** A's line is linked to a new product `Kaurajuoma` in `Maitotuotteet` with source
`user`; the product `Maito` still exists with its name and category; B's `Maito` line is
still linked to `Maito` with source `remembered`

### AC4: Case or spacing change renames only
**Given** receipt A
**When** the client renames `Maito` to `MAITO`
**Then** the line has `name` `MAITO`, and its category, source and link are unchanged; no
product was created and `Maito` keeps its name

### AC5: Renamed line without a category stays without one
**Given** receipt A with a third line `Outo` 50 without a category
**When** the client renames it to `Outo tuote`
**Then** the line has `name` `Outo tuote`, `category_id` and `category_source` `null`; no
product `Outo tuote` exists

### AC6: Renamed deposit refund keeps no category
**Given** receipt A with a line `Panttipalautus` -40 (deposit refund)
**When** the client renames it to `Maito`
**Then** the line has `name` `Maito`, `is_deposit_refund` true, `category_id` `null`, no
link

### AC7: Amount change
**Given** receipt A
**When** the client calls `PATCH .../lines/<Limu>` with `{"amount_cents": 300}`
**Then** the line has `amount_cents` 300 and still `Juomat` with source `model`;
`line_sum_cents` is 425, `difference_cents` -76, `warning` true; `subtotals` are
`Maitotuotteet` 125 and `Juomat` 300

### AC8: Zero and negative amounts on a normal line
**Given** receipt A
**When** the client sets `Limu`'s amount to 0, and then to -50
**Then** both answers are 200 with `amount_cents` 0 and -50; the line keeps its category;
the last `subtotals` has `Juomat` -50

### AC9: Marking a line as a deposit refund
**Given** receipt A
**When** the client calls `PATCH .../lines/<Limu>` with
`{"is_deposit_refund": true, "amount_cents": -40}`
**Then** the line has `is_deposit_refund` true, `amount_cents` -40, `category_id`,
`category_name` and `category_source` `null`; `line_sum_cents` is 85; `subtotals` is
`Maitotuotteet` 125 only

### AC10: A deposit refund must be negative
**Given** receipt A with a line `Panttipalautus` -40 (deposit refund)
**When** the client sends `{"is_deposit_refund": true}` for `Limu` (224), `{"amount_cents": 0}`
and `{"amount_cents": 40}` for `Panttipalautus`, and
`{"is_deposit_refund": true, "amount_cents": 10}` for `Limu`
**Then** each status is 422 with `error` `deposit_refund_amount` and the message
`Pantinpalautuksen summan on oltava negatiivinen.`; nothing changes

### AC11: Unmarking a deposit refund resolves the line
**Given** receipt A with lines `Panttipalautus` -40 and `maito` -40, both deposit refunds
**When** the client sends `{"is_deposit_refund": false}` for each
**Then** `Panttipalautus` is a normal line with -40 and no category; `maito` is a normal line
with `Maitotuotteet`, source `remembered`, linked to `Maito`; `subtotals` include
`Maitotuotteet` 85 and the no-category subtotal -40

### AC12: Name and category in one request
**Given** receipt A, and no product `Kivennäisvesi`
**When** the client sends `{"name": "Kivennäisvesi", "category_id": <Maitotuotteet>}` for
`Limu`
**Then** the line has `name` `Kivennäisvesi`, `Maitotuotteet`, source `user`; exactly one
product `Kivennäisvesi` exists, in `Maitotuotteet`

### AC13: Deposit refund with a category in the same request
**Given** receipt A with a line `Panttipalautus` -40 (deposit refund)
**When** the client sends `{"is_deposit_refund": true, "amount_cents": -40, "category_id":
<Juomat>}` for `Limu`, and `{"name": "Pullot", "category_id": <Juomat>}` for
`Panttipalautus`
**Then** both give 422 `deposit_refund_line`; nothing changes

### AC14: Line edit errors
**Given** receipt A
**When** the client patches `Limu` with each of these bodies
**Then** the status and `error` are:
- `{"name": ""}`, `{"name": "   "}`, `{"name": "<101 × a>"}` → 422 `invalid_name`
- `{"amount_cents": 100000000}`, `{"amount_cents": -100000000}` → 422 `invalid_amount`
- `{}`, `{"name": null}`, `{"amount_cents": "1"}`, `{"amount_cents": 1.5}`,
  `{"is_deposit_refund": 1}`, `{"name": "Limu", "color": "red"}` → 422 `invalid_request`

and nothing changes. `{"name": "<100 × a>"}` and `{"amount_cents": 99999999}` give 200.

### AC15: Adding a line
**Given** receipt A, and a receipt C without lines
**When** the client calls `POST /api/receipts/<A>/lines` with
`{"name": "Banaani", "amount_cents": 99}`, then with `{"name": " maito ", "amount_cents": 125}`,
then with `{"name": "Panttipalautus", "amount_cents": -40, "is_deposit_refund": true}`, and
`POST /api/receipts/<C>/lines` with `{"name": "Banaani", "amount_cents": 99}`
**Then** each status is 201; A's lines are, in order, `Maito`, `Limu`, `Banaani` (position 3,
no category), `maito` (position 4, `Maitotuotteet`, `remembered`, linked to `Maito`),
`Panttipalautus` (position 5, deposit refund, no category); A's last `line_sum_cents` is 533;
C's line has position 1; no product `Banaani` exists

### AC16: Adding a line: errors
**Given** receipt A, and no receipt 999
**When** the client posts to A's lines `{"amount_cents": 99}`, `{"name": "Banaani"}`,
`{"name": "", "amount_cents": 99}`, `{"name": "Pullot", "amount_cents": 40,
"is_deposit_refund": true}`, `{"name": "Banaani", "amount_cents": 99, "category_id": 12}`,
and to receipt 999 a valid line
**Then** the answers are 422 `invalid_request`, 422 `invalid_request`, 422 `invalid_name`,
422 `deposit_refund_amount`, 422 `invalid_request` and 404 `not_found`; A still has two lines

### AC17: Deleting a line
**Given** receipts A and B
**When** the client calls `DELETE /api/receipts/<A>/lines/<Limu>`, then the same call again,
then `DELETE /api/receipts/<A>/lines/<B's line>`, then adds a line to A
**Then** the first answer is 200 with `lines` `Maito` only and `line_sum_cents` 125; the
second and third are 404 `not_found`; B's line still exists; the products are unchanged;
the added line has position 2

### AC18: Deleting a line keeps the other positions
**Given** a receipt with lines at positions 1, 2 and 3
**When** the client deletes the line at position 2 and then adds a line
**Then** the lines have positions 1, 3 and 4, in that order

### AC19: Editing store, date and total
**Given** receipt A
**When** the client calls `PATCH /api/receipts/<A>` with
`{"store": "  Uusi   kauppa ", "purchase_date": "2026-10-06", "total_cents": 400}`, and then
`{"store": ""}`
**Then** the first answer has `store` `Uusi kauppa`, `purchase_date` `2026-10-06`,
`total_cents` 400, `difference_cents` 51, `warning` true, and A's list item shows the same
date, store and total; the second answer has `store` `""`

### AC20: Filling the fields of a receipt imported before reading
**Given** a receipt imported before reading existed (store, date and total `null`, no lines)
**When** the client sets `{"purchase_date": "2026-01-15", "total_cents": 0}`
**Then** the receipt has that date and total 0, `store` still `null`, `line_sum_cents` 0,
`difference_cents` 0 and `warning` false

### AC21: Receipt field errors
**Given** receipt A
**When** the client patches A with each of these bodies
**Then** the status and `error` are:
- `{"store": "<101 × a>"}` → 422 `invalid_store` (`{"store": "<100 × a>"}` gives 200)
- `{"purchase_date": "2026-02-30"}`, `{"purchase_date": "5.10.2026"}`,
  `{"purchase_date": ""}` → 422 `invalid_date`
- `{"total_cents": -1}`, `{"total_cents": 100000000}` → 422 `invalid_amount`
- `{}`, `{"store": null}`, `{"purchase_date": null}`, `{"total_cents": null}`,
  `{"total_cents": "349"}`, `{"reviewed": true, "note": "x"}` → 422 `invalid_request`

and nothing changes, also when one field of a body is valid (`{"store": "X", "total_cents": -1}`)

### AC22: Edits keep the review state
**Given** receipt A, confirmed
**When** the client renames a line, changes an amount, adds a line, deletes a line and sets
the total, and then sends `{"total_cents": 349, "reviewed": false}`
**Then** every answer but the last has `reviewed` true; the last has `total_cents` 349 and
`reviewed` false

### AC23: Ids out of range
**Given** receipt A
**When** the client calls `GET /api/receipts/9223372036854775808`,
`PATCH /api/receipts/<A>/lines/9223372036854775808` with `{"name": "X"}`,
`DELETE /api/receipts/<A>/lines/-9223372036854775809`, and
`PATCH /api/receipts/<A>/lines/<Limu>` with `{"category_id": 9223372036854775808}`
**Then** the first three are 404 `not_found` and the last is 422 `unknown_category`; nothing
changes

### AC24: Receipt page shows editable fields
**Given** the API returns receipt A with a deposit refund line `Panttipalautus` -40
**When** the receipt page opens
**Then** the inputs `Kauppa`, `Päivä` and `Loppusumma` hold `Testikauppa`, `2026-10-05` and
`3,49`; the input `Tuote: Maito` holds `Maito`, `Summa: Maito` holds `1,25`,
`Pantinpalautus: Maito` is unchecked; `Pantinpalautus: Panttipalautus` is checked,
`Summa: Panttipalautus` holds `-0,40`, and its category cell shows `Pantinpalautus`; each
line row has a `Poista` button; below the table are the heading `Uusi rivi` and the button
`Lisää rivi`

### AC25: Saving a name on leaving the field or on Enter
**Given** receipt A on the receipt page
**When** the user types `Kivennäisvesi` in `Tuote: Limu` and presses Tab; then types
`Vesi` in the same field and presses Enter; then types `X` and presses Esc; then focuses and
leaves `Tuote: Maito` without changing it
**Then** the UI sends `PATCH /api/receipts/<A>/lines/<Limu>` with `{"name": "Kivennäisvesi"}`
and then with `{"name": "Vesi"}`; after each answer the page shows the receipt from the
answer (the `ehdotus` mark of `Limu` is gone after the first one); Esc puts back `Vesi` and
sends nothing; leaving `Tuote: Maito` sends nothing

### AC26: Amount input
**Given** receipt A on the receipt page
**When** the user enters in `Summa: Limu` each of `3,00`, `3.5`, ` -0,40 `, `3`, and leaves
the field each time; then enters `abc`, `1,234`, `1 234,00` and an empty field
**Then** the UI sends `{"amount_cents": 300}`, `{"amount_cents": 350}`, `{"amount_cents": -40}`,
`{"amount_cents": 300}`; each of the last four sends nothing and shows
`Anna summa muodossa 1,25.` with `role="alert"` next to the field

### AC27: Amount parsing and formatting
**Given** the amount functions of PC13
**When** they parse `1,25`, `1.25`, `-0,40`, `3`, `3,5`, ` 2,00 `, `0`, `-0`, `abc`, `1,234`,
`1 234,00`, `,5`, `1,`, `--1`, `` and format 125, -40, 0, 5
**Then** the parsed values are 125, 125, -40, 300, 350, 200, 0, 0 and no value for the last
seven; the formatted values are `1,25`, `-0,40`, `0,00`, `0,05`

### AC28: Deposit refund checkbox
**Given** receipt A on the receipt page
**When** the user sets `Summa: Limu` to `-0,40` and leaves the field, then checks
`Pantinpalautus: Limu`
**Then** the UI sends `{"amount_cents": -40}` and then `{"is_deposit_refund": true}`; after
the answer `Limu`'s category cell shows `Pantinpalautus` and has no dropdown

### AC29: Editing store, date and total in the view
**Given** receipt A on the receipt page
**When** the user sets `Loppusumma` to `4,00` and presses Enter, sets `Päivä` to
`2026-10-06` and leaves it, and sets `Kauppa` to `Uusi kauppa` and leaves it
**Then** the UI sends `PATCH /api/receipts/<A>` with `{"total_cents": 400}`, then
`{"purchase_date": "2026-10-06"}`, then `{"store": "Uusi kauppa"}`; after the first answer
the page shows `Rivien summa 3,49 € poikkeaa loppusummasta 4,00 €. Erotus 0,51 €.` with
`role="status"`

### AC30: Adding a line in the view
**Given** receipt A on the receipt page
**When** the user fills the `Uusi rivi` form with `Banaani` and `0,99` and clicks
`Lisää rivi`
**Then** the UI sends `POST /api/receipts/<A>/lines` with
`{"name": "Banaani", "amount_cents": 99, "is_deposit_refund": false}`; after the answer the
table has a row `Banaani` with `0,99`, and the form's fields are empty and unchecked; with
the amount `x` nothing is sent and `Anna summa muodossa 1,25.` is shown next to the form's
amount field

### AC31: Deleting a line in the view
**Given** receipt A on the receipt page
**When** the user clicks `Poista` on the `Limu` row, then `Peruuta`, then `Poista` and the
confirming `Poista`
**Then** `Peruuta` sends nothing and keeps the row; the confirmation sends
`DELETE /api/receipts/<A>/lines/<Limu>`; after the answer the table has only `Maito` and
the page shows `Rivien summa 1,25 €`

### AC32: Saves are sent one at a time
**Given** receipt A on the receipt page, and the answer to a name save is delayed
**When** the user renames `Limu` and leaves the field, then sets `Summa: Maito` to `2,00` and
leaves that field before the first answer arrives
**Then** the focus is in the field the user moved to; the amount request is sent only after
the name answer arrived; the page then shows both changes

### AC33: Errors in the view
**Given** receipt A on the receipt page
**When** the name save of `Limu` with an empty name is answered with 422 `invalid_name`, the
checkbox of `Limu` with 422 `deposit_refund_amount`, a `Lisää rivi` with a network error,
and a delete with a network error
**Then** `Nimen pituuden on oltava 1–100 merkkiä.` is shown with `role="alert"` next to
`Tuote: Limu`, which stays empty until the user presses Esc (then it shows `Limu` and the
message is gone); `Pantinpalautuksen summan on oltava negatiivinen.` is shown next to the
checkbox, which is unchecked again; `Taustapalveluun ei saada yhteyttä.` is shown next to the
add button, with the form's values kept, and next to the `Limu` row's delete button, with the
row kept

### AC34: Category names as text while the categories load
**Given** receipt A with a line `Outo` 50 without a category, and the categories request
waits for its answer, or fails
**When** the receipt page opens
**Then** the category cells show `Ruoka > Maitotuotteet`, `Juomat` and `–` as text, with no
dropdown; once the categories arrive, the dropdowns are shown

### AC35: A receipt without lines can get lines
**Given** the receipt of receipt-review AC7 (no lines)
**When** the receipt page opens
**Then** the inputs `Kauppa`, `Päivä` and `Loppusumma` are empty; it shows `Kuitilta ei
luettu rivejä.` and the `Uusi rivi` form; after adding a line the line table is shown instead
of the text

### AC36: Editing journey end to end
**Given** the E2E stack with fake engines and one new synthetic image imported from the
Tuonti page (fake reader: `Testikauppa`, 2026-10-05, `Maito` 1,25 €, `Limu` 2,24 €, total
3,49 €). The E2E database lives as long as the `backend-e2e` container, so earlier runs may
have stored products
**When** the user opens Kuitit, opens the newest receipt, sets `Summa: Limu` to `2,00`,
adds a line `E2E-pantti` `-0,40` with `Pantinpalautus` checked, sets `Loppusumma` to `2,85`,
renames `Maito` to `E2E-maito`, deletes nothing else, and reloads the page
**Then** the page shows the lines `E2E-maito 1,25`, `Limu 2,00` and `E2E-pantti -0,40` (a
deposit refund), `Rivien summa 2,85 €`, no warning, and `Loppusumma` `2,85`; the review
state is still `Tarkistamaton`

## Files to Modify
Refined by the Plan (see [P1](#p1-where-the-code-goes)–[P5](#p5-frontend)).

| File | Change |
|---|---|
| `backend/app/storage/db.py` | `INTEGER_MIN`, `INTEGER_MAX`, `fits_integer` (P2) |
| `backend/app/storage/receipt_repository.py` | `StoredLine.amount_cents`; `update_line`, `next_position`, `delete_line`, `set_fields` (P2) |
| `backend/app/categorization/service.py` | `LineCategoryService.choose`, `follow_name`, `resolve` in the caller's transaction; `set_category` removed (P3) |
| `backend/app/review/errors.py`, `backend/app/texts.py` | Four new error codes and their messages (P4) |
| `backend/app/review/fields.py` (new) | Amount, total, store and date checks (P4) |
| `backend/app/review/service.py` | `edit_line`, `add_line`, `delete_line`, `update_receipt`, id bounds (P4) |
| `backend/app/review/schemas.py`, `backend/app/review/routes.py` | Strict partial bodies; the new and changed routes (P4) |
| `backend/tests/unit/storage/test_receipt_repository.py`, `test_db.py` | New repository methods and `fits_integer`; the `StoredLine` built in one test gets `amount_cents` |
| `backend/tests/unit/categorization/test_line_category_service.py` | New tests for `follow_name` and `resolve`; the existing tests call `choose` through a local helper that opens the transaction (P3), checking the same behavior |
| `backend/tests/unit/review/test_fields.py` (new), `test_review_service.py`, `test_schemas.py` (new) | Unit tests of the Testing Strategy. In `test_review_service.py` the receipt-review tests that call `set_line_category` (AC13, AC14, AC16) call `edit_line` with `LineEdit(category_id=...)` (T8), and those that call `set_reviewed` (AC17, AC9) call `update_receipt` with `ReceiptEdit(reviewed=...)` (T11): an interface change by design (P4), checking the same behavior |
| `backend/tests/integration/test_receipts_api.py` | Integration tests; receipt-review AC15's refund line moves onto receipt A, as that AC says (the carried-over audit item) |
| `frontend/src/api/client.ts` (+ test) | `apiDelete` generic (P5) |
| `frontend/src/api/receipts.ts` (+ test) | `editLine`, `addLine`, `deleteLine`, `editReceipt` |
| `frontend/src/format.ts` (+ test) | `parseCents`, `formatCentsInput` |
| `frontend/src/components/EditableField.tsx` (+ test, new) | Save on leaving or Enter, Esc, own error |
| `frontend/src/components/AddLineForm.tsx` (+ test, new) | The `Uusi rivi` form |
| `frontend/src/components/ReceiptPage.tsx` (+ test) | Inline editing, save queue, delete, categories as text. Existing receipt-review tests change by design, because this spec replaces the text cells with inputs (PC12, PC13), shows categories as text while they load (PC15, the carried-over audit item) and replaces disabling with the save queue (PC12): both `AC22` tests (store, date, total and line amounts are input values; the columns and the `<label>`s of the UI texts table), `AC23` (the refund amount `-0,40` is an input value), `AC24: choosing a category saves it and shows the answer` (no disabled controls while the answer waits), `AC26: no total and no lines` (empty inputs instead of `–`) and `AC29: categories that cannot be loaded disable the dropdowns` (text instead of a disabled dropdown). What they verify (the values shown, the refund row, the answer applied, the load error) stays |
| `frontend/src/i18n/fi.ts`, `frontend/src/test/receipts.ts` | Texts; MSW handlers |
| `frontend/src/App.test.tsx` | The receipt-review tests `AC22: a receipt opens from the list and the back link returns` and `AC22: a reload at /kuitit/<id> shows the receipt` find the store as text on the receipt page; it is now the value of the `Kauppa` input (PC12). What they verify (the receipt opens) stays |
| `frontend/e2e/import.spec.ts` | AC36 after the receipt-review test. The receipt-review AC31 test finds the `Maito` row by its text, which is now the value of the `Tuote: Maito` input (PC12); it finds the row by that input instead, and checks the same |
| `specs/PRD.md` | Note on FR-18: quantity and unit price are not editable in the first release |
| `docs/api-reference.md` | New and changed receipt endpoints, strict bodies, new error codes |
| `docs/subsystems/review/README.md` | Edits, `fields.py`, the line edit order; remove "does not edit lines" |
| `docs/subsystems/categorization/README.md` | `choose`, `follow_name`, `resolve`; FR-43; the caller holds the transaction |
| `docs/subsystems/storage/README.md` | New repository methods, `fits_integer` |
| `docs/subsystems/ui/README.md` | Inline editing, `EditableField`, the save queue |
| `docs/datamodel.md` | Positions can have gaps after a delete; no schema change |
| `docs/architecture.md`, `docs/content-plan.md` | Line editing implemented; the next spec |
| `docs/glossary.md` | Name match, resolving a line |
| `specs/README.md` | Status of this spec |

## Risk
- **What could break:** the receipt view, which turns every field into an input; the
  category correction, which now runs together with renames (FR-43 creates products);
  existing clients of the receipt endpoints, which now get 422 for extra body fields (only
  this app's UI calls them).
- **Data:** a rename of a line with a model suggestion stores that suggestion as a product's
  category without a separate choice (FR-43). The user sees the category beside the name
  and corrects it with the dropdown, which moves the product (FR-36). A deleted line cannot
  be brought back; the user adds it again, and the OCR text stays stored (FR-10).
- **Rollback:** revert the change. There is no migration, so the old code reads the edited
  data; products created by renames stay as ordinary products.
- **Dependencies:** none new. No model call.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | rename (categorization) | no match, with category | `Limu` `Juomat` `model` | rename | new product, `user`, linked | real SQLite |
| AC2 | rename | name match | `Limu`, product `Jogurtti` | rename `JOGURTTI` | `remembered`, linked | real SQLite |
| AC3 | rename | linked line | A and B `Maito` | rename A's | new product; `Maito` and B unchanged | real SQLite |
| AC4 | rename | same key | `Maito` | `MAITO` | name only | real SQLite |
| AC5, AC6 | rename | no category; refund | `Outo`; refund | rename | no product, no category | real SQLite |
| AC9–AC11 | refund flag | mark, refuse, unmark | AC lines | set flag | AC values; `DepositRefundAmountError` | real SQLite |
| AC12, AC13 | line edit order | name then category; refund with category | AC bodies | edit | AC values; `DepositRefundLineError`, nothing changed | real SQLite |
| AC14 | line validation | bounds | names 0, 100, 101; amounts ±99 999 999, ±100 000 000 | edit | ok or `InvalidNameError`, `InvalidAmountError` | none |
| AC15, AC18 | `ReceiptRepository` add line | next position | 0 lines; positions 1, 3 | add | 1; 4 | real SQLite |
| AC17 | `ReceiptRepository` delete line | exists, missing | a line | delete twice | `True`, `False` | real SQLite |
| AC19–AC21 | receipt field validation | store, date, total | AC values | validate | display store; errors | none |
| AC14, AC16, AC21 | schemas | strict bodies | AC bodies | parse | `ValidationError` | none |
| AC23 | id bounds | out of range | ±2^63 values | route | `NotFoundError`, `UnknownCategoryError` | none |
| AC27 | `parseCents`, `formatCentsInput` | all values | AC27 values | parse, format | AC27 results | none |
| AC24, AC34, AC35 | `ReceiptPage` | inputs; categories loading and failed; no lines | MSW receipts | render | AC texts and values | MSW |
| AC25, AC26 | `ReceiptPage` | save on Tab, Enter; Esc; unchanged; amount input | receipt A | type | request bodies; alerts | MSW |
| AC28–AC31 | `ReceiptPage` | checkbox, fields, add, delete | receipt A | act | bodies; page from answer | MSW |
| AC32 | `ReceiptPage` | ordered saves | delayed answer | two saves | second sent after first answer; focus kept | MSW |
| AC33 | `ReceiptPage` | errors | 422s, network errors | act | alerts; values kept or restored | MSW |

### Integration tests
Real SQLite (temporary file), real FastAPI app; engines faked.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1–AC6 | renames | `PATCH .../lines/<id>` `{"name": ...}` | AC lines and products | 200 |
| AC7, AC8 | amounts | `PATCH` `{"amount_cents": ...}` | AC sums | 200 |
| AC9, AC11 | refund flag | `PATCH` | AC lines and subtotals | 200 |
| AC10 | refund not negative | AC bodies | `deposit_refund_amount`; nothing changed | 422 |
| AC12, AC13 | combined bodies | `PATCH` | AC values; `deposit_refund_line` | 200, 422 |
| AC14 | line errors | AC bodies | AC codes; nothing changed | 422, 200 |
| AC15 | add | `POST .../lines` | AC lines and positions; no product `Banaani` | 201 |
| AC16 | add errors | AC bodies | AC codes | 422, 404 |
| AC17, AC18 | delete | `DELETE .../lines/<id>` | AC lines and positions | 200, 404 |
| AC19, AC20 | receipt fields | `PATCH /api/receipts/<id>` | AC fields, sums, list item | 200 |
| AC21 | receipt field errors | AC bodies | AC codes; nothing changed | 422 |
| AC22 | review state kept | edits, then `reviewed` false | AC22 | 200, 201 |
| AC23 | ids out of range | AC calls | `not_found`, `unknown_category` | 404, 422 |
| PC16 | no names in logs | AC1 and AC15 requests with captured logs | no line, product or store name in the log | 200, 201 |

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC36 | Import, edit lines and total, reload | AC36 steps | AC36 outcome |

### Coverage target
- Backend: 90 % lines for the changed review and categorization code; every branch of the
  rename rules (PC2), the refund flag (PC4), the amount and date checks and the id bounds.
- Frontend: every amount input case of AC27 and every component state in the UI texts table
  is rendered by a test.

### Test data
- Synthetic fixtures only: invented stores and product names (`Testikauppa`, `Uusi kauppa`,
  `Maito`, `Limu`, `Jogurtti`, `Kivennäisvesi`, `Kaurajuoma`, `Outo`, `Banaani`,
  `Panttipalautus`, `Pullot`, `E2E-maito`, `E2E-pantti`), the default catalog.
- Mocks: MSW for component tests; fake engines (`RRMC_ENGINES=fake`) for integration and E2E.

## Related Documentation (MANDATORY)
- Tier 1: [PRD](../PRD.md) sections 5 and 6.4, FR-9, FR-13, FR-36, FR-44, NFR-9;
  [architecture](../../docs/architecture.md); [datamodel](../../docs/datamodel.md#receipt_lines);
  [API reference](../../docs/api-reference.md#receipts);
  [development](../../docs/development.md#code-standards)
- Tier 2: [review](../../docs/subsystems/review/README.md),
  [categorization](../../docs/subsystems/categorization/README.md),
  [storage](../../docs/subsystems/storage/README.md), [ui](../../docs/subsystems/ui/README.md)
- ADRs: [0004 line categorization](../../docs/adr/0004-line-categorization.md)
- Specs: [Receipt review](receipt-review.md), [Line categorization](categorization.md)

<!-- The Plan phase appends "## Plan" and the Tasks phase appends "## Tasks" below. -->

## Plan

### P1 Where the code goes

| Package | Holds | Depends on |
|---|---|---|
| `storage` | SQL: write a line's fields, next position, delete a line, write the receipt fields; the integer range of SQLite | SQLite |
| `categorization` | The product rules of a line, run inside the caller's transaction: the category choice (FR-13, FR-36), following a new name (FR-43), resolving a line | `storage` |
| `review` | Request bodies, the order of a line edit (PC1), the field checks (PC3, PC8), id bounds (PC11), the transaction | `storage`, `categorization`, `calculation` |

The product rules stay in categorization, which owns products; review only decides the order
of the steps and owns the transaction, because one request may touch the amount, the name and
the category together and must commit or fail as one (PC1). No new package, no migration, no
new dependency. No ADR: this extends the split the receipt review spec made.

### P2 storage: `receipt_repository.py`

- **`StoredLine`** gets `amount_cents: int` (after `name`), read by `get_line`. PC4 needs the
  stored amount when a request sets only the flag. The repository test that builds a
  `StoredLine` gets the field (a field added to a type).
- **`update_line(line_id, *, name, amount_cents, is_deposit_refund, category: LineCategory | None)`**:
  writes all six columns in one `UPDATE`. The caller passes the resulting state, so the
  `CHECK`s (a refund is negative and has no category) see one consistent row.
- **`next_position(receipt_id) -> int`**: `SELECT COALESCE(MAX(position), 0) + 1` (PC6,
  AC18). It runs in the add's `BEGIN IMMEDIATE` transaction, so two adds cannot get the same
  position.
- **`delete_line(line_id) -> bool`**: `False` when no row was deleted.
- **`set_fields(receipt_id, *, store, purchase_date, total_cents) -> bool`**: writes the three
  columns; `False` when the receipt does not exist.
- **`db.py`** gets `INTEGER_MIN = -(2**63)`, `INTEGER_MAX = 2**63 - 1` and
  `fits_integer(value: int) -> bool`, so an out-of-range id is caught before SQLite raises
  `OverflowError` (PC11). @backend/app/receipt_reading/validation.py keeps its own copy;
  changing it is not part of this spec.

### P3 categorization: `LineCategoryService`

Its methods no longer open a transaction; the caller holds it (as `LineCategorizer.resolve`
already does at import). `set_category` is replaced by `choose`, because a category choice
must be able to share one transaction with a rename (PC5):

```python
class LineCategoryService:
    """The product rules of receipt lines. The caller holds the transaction, on the catalog's
    connection, which both repositories share."""

    def choose(self, line: StoredLine, category_id: int) -> None:
        """FR-13, FR-36: today's `set_category` body after the line lookup.
        Raises: UnknownCategoryError, NotACategoryError, DepositRefundLineError, InvalidNameError."""

    def follow_name(self, line: StoredLine, name: str) -> LineCategory | None:
        """FR-43 (PC2): the category of the normal line `line` after it is renamed to the
        display name `name`. Same key: the line's category. Name match: the product's,
        `remembered`. Else, with a category: a new product, `user`. Else None."""

    def resolve(self, name: str) -> LineCategory | None:
        """PC6, PC4: the name match's category, `remembered`, linked; None without one."""
```

`follow_name` and `resolve` only read, except that `follow_name` may add the product; the
caller writes the line. The tests in @backend/tests/unit/categorization/test_line_category_service.py
call `set_category`; they get a local helper that opens the transaction, reads the line and
calls `choose`, so each test checks the same behavior (an interface change by design).

### P4 review backend

- **`errors.py`:** `InvalidAmountError` (`invalid_amount`), `DepositRefundAmountError`
  (`deposit_refund_amount`), `InvalidDateError` (`invalid_date`), `InvalidStoreError`
  (`invalid_store`), all 422, with their texts in @backend/app/texts.py.
- **`fields.py` (new):** pure checks, no I/O.
  - `AMOUNT_LIMIT = 99_999_999`; `check_amount(cents) -> int` (±limit) and
    `check_total(cents) -> int` (0…limit) raise `InvalidAmountError`.
  - `check_store(text) -> str`: `normalize_display`, at most 100 characters, else
    `InvalidStoreError`.
  - `check_date(text) -> str`: ASCII `[0-9]{4}-[0-9]{2}-[0-9]{2}` and `date.fromisoformat`,
    else `InvalidDateError`. The pattern comes first because `fromisoformat` also accepts
    `20261005`.
- **`service.py`:** `LineEdit` and `ReceiptEdit` dataclasses whose fields are `None` when not
  sent (the schemas refuse `null`, so `None` always means "not sent"). `ReviewService` gets:
  - `edit_line(receipt_id, line_id, edit) -> ReceiptView`, replacing `set_line_category`.
    In one transaction:
    1. ids in range and the line on the receipt, else `NotFoundError`; a `category_id` out
       of range raises `UnknownCategoryError`;
    2. `name = validate_product_name(edit.name)` if sent, `check_amount` if sent;
    3. resulting flag and amount; a refund with an amount ≥ 0 raises
       `DepositRefundAmountError`;
    4. the line's category: cleared for a refund; `resolve(name)` for a line that stops being
       a refund; `follow_name` when the name's key changed; else unchanged;
    5. `update_line` with the resulting state;
    6. if `category_id` was sent, `choose` on the line as written, which raises
       `DepositRefundLineError` for a refund (AC13).

    Any error rolls the whole request back. With several errors in one body the first in
    this order is returned.
  - `add_line(receipt_id, name, amount_cents, *, is_deposit_refund) -> ReceiptView`: the same
    checks as steps 2–3, `resolve` for a normal line, `add_line` at `next_position`.
  - `delete_line(receipt_id, line_id) -> ReceiptView`.
  - `update_receipt(receipt_id, edit) -> ReceiptView`, replacing `set_reviewed`: reads the
    row, checks the sent fields, writes `set_fields` with the sent values over the stored
    ones, then `set_reviewed` if sent; one transaction.
  - Every method that takes an id checks `fits_integer` first and raises `NotFoundError`
    (PC11), also `receipt` and `image`.
- **`schemas.py`:** a base `_Body` with `ConfigDict(extra="forbid")`. `LineUpdate` (`name:
  StrictStr | None = None`, `amount_cents: StrictInt | None`, `is_deposit_refund:
  StrictBool | None`, `category_id: StrictInt | None`) and `ReceiptUpdate` (`store`,
  `purchase_date`, `total_cents`, `reviewed`) share an `after` validator that refuses an
  empty `model_fields_set` and any sent field whose value is `None` (PC10). `NewLine`
  (`name: StrictStr`, `amount_cents: StrictInt`, `is_deposit_refund: StrictBool = False`).
  `StrictInt` also refuses `true` and `1.5`. All failures go through the existing handler
  to `invalid_request`. `LineCategoryUpdate` and `ReviewUpdate` are removed.
- **`routes.py`:** `PATCH /api/receipts/{id}` takes `ReceiptUpdate`;
  `PATCH .../lines/{line_id}` takes `LineUpdate`; new `POST /api/receipts/{id}/lines`
  (`status_code=201`) and `DELETE /api/receipts/{id}/lines/{line_id}`, each answering
  `ReceiptOut`.

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
  V->>V: validate name, amount, refund flag
  V->>L: follow_name(line, "Kivennäisvesi")
  L->>S: product by key? else add_product
  V->>S: update_line(11, ...); COMMIT
  V->>V: receipt(3): check_receipt, category_subtotals
  R-->>U: 200 receipt view
```

### P5 frontend

- **`api/client.ts`:** `apiDelete<T = undefined>(path)`, so the line delete gets the receipt
  back; the catalog's callers do not change.
- **`api/receipts.ts`:** `editLine(receiptId, lineId, changes: LineChanges)` (one or more
  of `name`, `amount_cents`, `is_deposit_refund`, `category_id`), `addLine(receiptId,
  line: NewLine)`, `deleteLine(receiptId, lineId)`, `editReceipt(id, changes:
  ReceiptChanges)`. `setLineCategory` and `setReviewed` stay as one-line wrappers over
  `editLine` and `editReceipt`, so their callers and tests do not change.
- **`format.ts`:** `parseCents(text): number | null` with
  `/^\s*(-?)([0-9]+)(?:[.,]([0-9]{1,2}))?\s*$/`, integer arithmetic only (no `parseFloat`),
  and `-0` returned as `0`; `formatCentsInput(cents)`: `formatCents` without ` €` (PC13).
- **`components/EditableField.tsx` (new):** one input that saves on leaving or Enter (PC12,
  PC14). Props: `label`, `value` (the saved text), `type` (`text` or `date`),
  `onSave(text): Promise<string | null>` (the error message, or `null`). It keeps a draft
  while the user types or after a failed save, shows its own error with `role="alert"`, and
  goes back to `value` on Esc or after a successful save. Leaving with the draft equal to
  `value` saves nothing. Used for the store, date, total, line names and amounts; the
  amount callers parse with `parseCents` and return `Anna summa muodossa 1,25.` without a
  request.
- **`components/AddLineForm.tsx` (new):** the `Uusi rivi` form (PC6, AC30). Its `onAdd`
  returns the error message or `null`; the form clears only on `null`.
- **`components/ReceiptPage.tsx`:**
  - Saves go through one queue: a promise chain in a `useRef`, so each request starts after
    the previous answer (PC12, AC32). Each answer replaces the receipt state. The `busy` flag
    and the disabled controls go away, so the focus is never taken from the field the user
    moved to.
  - The `dl` of store, date and total becomes three `EditableField`s.
  - A line row: name and amount `EditableField`s, the refund checkbox (checked from the saved
    line, so a failed save leaves it as it was), the category cell, and `ConfirmDelete`.
    The checkbox and delete errors are kept per line, as the category errors are today.
  - The category cell shows the text of PC15 while `items` is `null`.
  - A receipt without lines shows `Kuitilta ei luettu rivejä.` and the form.
- **`i18n/fi.ts`:** `fi.receipt.nameOf`, `amountOf`, `refundOf` (label functions as
  `categoryOf`), `newLine`, `addLine`, `amountFormat`; the `Pantinpalautus` column uses
  `depositRefund`.
- **`test/receipts.ts`:** MSW handlers for the new calls that record the request bodies.

### P6 Check against the ACs

| AC | Covered by |
|---|---|
| AC1–AC6 | P3 `follow_name`; P4 step 4 |
| AC7, AC8 | P4 step 2 and 5; sums by the existing `receipt` |
| AC9–AC11, AC13 | P4 steps 3, 4 and 6 |
| AC12 | P4 step 6 after step 4 |
| AC14, AC16, AC21 | P4 `fields.py` and schemas |
| AC15, AC17, AC18 | P2 `next_position`, `delete_line`; P4 `add_line`, `delete_line` |
| AC19, AC20, AC22 | P4 `update_receipt`; edits never call `set_reviewed` |
| AC23 | P2 `fits_integer`; P4 id checks |
| AC24–AC35 | P5 |
| AC36 | P5, E2E in `import.spec.ts` |

## Tasks

Each task is one Red → Green → Refactor cycle unless it says otherwise. Backend unit tests go
next to the existing ones (`unit/storage/`, `unit/categorization/`, `unit/review/`); API
tests go to `backend/tests/integration/test_receipts_api.py`. Frontend tests sit next to
their files. Test names start with the AC ID. After every task the tests, lint, format check
and type check of the changed part pass. Existing tests change only where
[Files to Modify](#files-to-modify) names them, and only as it says there; each such change
is made in the task that names it, before its Green step.

### Storage

- [x] **T1 Integer range (P2, PC11).** Tests in `unit/storage/test_db.py`: `fits_integer` is
  true for `INTEGER_MIN`, 0 and `INTEGER_MAX`, false one beyond each. Green: the constants
  and `fits_integer`.
- [x] **T2 Line writes (P2; AC17, AC18).** Tests in `test_receipt_repository.py`:
  `get_line` returns `amount_cents`; `update_line` writes name, amount, flag and category
  together, and a refund with a category or an amount ≥ 0 raises `sqlite3.IntegrityError`;
  `next_position` is 1 without lines and 4 after positions 1 and 3
  (`test_ac18_next_position_after_a_gap`); `delete_line` is `True`, then `False`. Green:
  `StoredLine.amount_cents` (the existing `StoredLine(...)` in the test gets the field),
  `update_line`, `next_position`, `delete_line`.
- [x] **T3 Receipt fields (P2; AC19).** `set_fields` writes store, date and total and
  returns `True`; `False` for a missing id; a date of the wrong shape raises
  `sqlite3.IntegrityError`. Green: `set_fields`.

### Categorization

- [x] **T4 `choose` in the caller's transaction (P3).** Change
  `test_line_category_service.py` to call `choose` through a local helper that opens
  `catalog.transaction()`, reads the line and calls `choose`; see it fail (no `choose`).
  Green: `choose` from the body of `set_category`; remove `set_category`; review's
  `set_line_category` uses the same sequence until T8 replaces it. The tests check the same
  behavior as before, including the rollback test.
- [x] **T5 Following a new name (P3; AC1–AC5).** Tests: `test_ac1_no_match_makes_a_product`
  (`user`, linked, product in `Juomat`); `test_ac2_name_match_is_remembered`;
  `test_ac3_old_product_untouched` (product `Maito` and B's line unchanged);
  `test_ac4_same_key_keeps_the_category`; `test_ac5_no_category_no_product`. Green:
  `follow_name`.
- [x] **T6 Resolving (P3; AC11, AC15).** `resolve(" maito ")` gives `Maitotuotteet`,
  `remembered`, linked to `Maito`; an unknown name gives `None`; no product is created.
  Green: `resolve`.

### Review backend

- [x] **T7 Field checks (P4; AC14, AC21).** Tests in `unit/review/test_fields.py`:
  `check_amount` at ±99 999 999 passes and at ±100 000 000 raises `InvalidAmountError`;
  `check_total` at 0 and 99 999 999 passes, -1 and 100 000 000 raise; `check_store`
  `"  Uusi   kauppa "` → `Uusi kauppa`, `""` → `""`, 100 × `a` passes, 101 raises
  `InvalidStoreError`; `check_date` passes `2026-10-06` and raises `InvalidDateError` for
  `2026-02-30`, `5.10.2026`, `""`, `20261005` and a date with full-width digits. Green:
  `fields.py`, the four error classes, their texts.
- [x] **T8 Line edit: name and amount (P4; AC1–AC8, AC14).** Tests in
  `test_review_service.py`, real SQLite with the AC catalog: each of AC1–AC8 through
  `edit_line`, and the AC14 name and amount errors with nothing changed. Green: `LineEdit`,
  `edit_line` steps 1, 2, 4 (name), 5 and 6 (the category, as `set_line_category` did); it
  replaces `set_line_category`, and the receipt-review tests that called it call `edit_line`
  (Files to Modify).
- [x] **T9 Line edit: refund flag and category (P4; AC9–AC13).** Tests for AC9, AC10 (all
  four bodies, nothing changed), AC11, AC12 (exactly one product) and AC13 (both bodies,
  nothing changed). Green: steps 3 and 4 (flag).
- [x] **T10 Add and delete (P4; AC15–AC18).** Tests for AC15 (positions, categories, no
  product `Banaani`, receipt C), AC16's service errors (`invalid_name`,
  `deposit_refund_amount`, `NotFoundError`), AC17 and AC18. Green: `add_line`,
  `delete_line`.
- [x] **T11 Receipt fields (P4; AC19–AC22).** Tests for AC19, AC20, AC21's service errors
  (also the mixed valid and invalid body, nothing changed) and AC22 (the review state is
  kept by every edit; `reviewed` sent with `total_cents` applies both). Green: `ReceiptEdit`,
  `update_receipt`; it replaces `set_reviewed`, and the receipt-review tests that called it
  call `update_receipt` (Files to Modify).
- [x] **T12 Ids out of range (P4; AC23).** Tests: every `ReviewService` method with a
  receipt or line id of 2^63 or -2^63-1 raises `NotFoundError`; `edit_line` with
  `category_id` 2^63 raises `UnknownCategoryError`; nothing changes. Green: the id checks.
- [x] **T13 Strict bodies (P4; PC10, AC14, AC16, AC21).** Tests in
  `unit/review/test_schemas.py`: each `invalid_request` body of AC14, AC16 and AC21 raises
  `ValidationError`; `{"name": "Limu"}`, `{"reviewed": true}` and a full `NewLine` parse;
  `NewLine` without `is_deposit_refund` gives `False`. Green: `_Body`, `LineUpdate`,
  `ReceiptUpdate`, `NewLine`; remove `LineCategoryUpdate` and `ReviewUpdate`.
- [x] **T14 Endpoints (AC1–AC23, PC16).** Integration tests, one per row of the Testing
  Strategy's integration table, including the PC16 log check and `POST` answering 201.
  Move receipt-review AC15's refund line onto receipt A (Files to Modify). Green: the routes
  of P4.

### Frontend

- [x] **T15 Amount parsing (P5; AC27).** Tests in `format.test.ts`: every AC27 value, and
  `parseCents("-0")` is `0`, not `-0`. Green: `parseCents`, `formatCentsInput`.
- [x] **T16 API calls (P5).** Tests in `client.test.ts` (`apiDelete` returns the body when
  there is one, `undefined` for 204) and `receipts.test.ts` (method, path and body of
  `editLine`, `addLine`, `deleteLine`, `editReceipt`; `setLineCategory` and `setReviewed`
  send what they sent before). Green: the P5 API changes; MSW handlers in
  `test/receipts.ts`.
- [x] **T17 `EditableField` (P5; AC25, AC33).** Tests in `EditableField.test.tsx`: saves on
  Tab and on Enter only when changed; Esc restores and does not save; a returned message
  shows with `role="alert"` and keeps the draft; Esc then clears it; the next successful
  save clears it; a new `value` shows when there is no draft. Green: the component.
- [x] **T18 `AddLineForm` (P5; AC30, AC33).** Tests: the body of AC30; the form clears after
  success; `x` as amount shows `Anna summa muodossa 1,25.` and calls nothing; a returned
  message shows next to the button and the values are kept. Green: the component.
- [x] **T19 Editable receipt page (P5; AC24, AC34, AC35).** Tests in `ReceiptPage.test.tsx`
  for AC24, AC34 (loading and failed) and AC35. First change the receipt-review tests named
  in Files to Modify (AC22 ×2, AC23, AC26, AC29). Green: `EditableField`s for the fields and
  lines, the refund checkbox, `ConfirmDelete`, the category text, the form, the new texts in
  `fi.ts`.
- [x] **T20 Saving from the page (P5; AC25, AC26, AC28–AC31).** Tests for each AC's request
  bodies and the page shown from the answer. Green: the save handlers.
- [x] **T21 Save queue and errors (P5; AC32, AC33).** Tests for AC32 (held answer: the focus
  stays in the next field; the second request starts after the first answer) and AC33 (each
  error by its field; checkbox back; form and row kept). First change receipt-review
  `AC24: choosing a category saves it and shows the answer` (Files to Modify). Green: the
  queue; remove `busy`.

### End to end and docs

- [x] **T22 E2E journey (AC36).** A new test in `frontend/e2e/import.spec.ts` after the
  receipt-review test. Green: fix only what the journey shows; the unit tests already cover
  each step.
- [x] **T23 Docs (Files to Modify).** The PRD note on FR-18, the API reference, the review,
  categorization, storage and UI READMEs, the data model, architecture, content plan,
  glossary and `specs/README.md`. Then run every command of the
  [Commands](../../AGENTS.md#commands) table for the backend, the frontend and E2E. Not a
  TDD cycle.
