# API Reference

- **Status:** Done (health, catalog, import, receipt, line editing, totals, budget, export
  and archive endpoints)
- **Updated:** 2026-11-13

## Overview

The backend serves a JSON REST API under `/api`. It listens only on `127.0.0.1` (default
port `8000`). There is no login: the app is local and single-user.

The UI calls the API on its own origin (`http://127.0.0.1:5173/api/...`); the Vite dev
server forwards these requests to the backend. CORS allows only
`http://127.0.0.1:<RRMC_UI_PORT>`.

Each request is logged as one line with method, path, status and duration. Query strings and
bodies are never logged.

## Error format

Every error response from the app has this body (a 405 for a wrong method is FastAPI's
default `{"detail": ...}`):

```json
{"error": "<code>", "message": "<Finnish text for the user>"}
```

Some codes add fields next to these two, for example `product_count`; the endpoint lists
them.

`error` is a stable `snake_case` code for programs; `message` is shown to the user as is.
Messages come from @backend/app/texts.py and never contain receipt content.

| Status | `error` | `message` | When |
|---|---|---|---|
| 400 | `invalid_host` | `Pyyntö hylättiin: tuntematon osoite.` | The `Host` header is not a known name of the app ([security](security.md#network)) |
| 404 | `not_found` | `Pyydettyä kohdetta ei löydy.` | Unknown `/api/...` path, or an id that does not exist, also one outside SQLite's integer range |
| 422 | `invalid_request` | `Pyyntö on virheellinen.` | Body or parameters not valid, including a body that is not JSON |
| 500 | `internal_error` | `Odottamaton virhe. Katso lisätiedot palvelimen lokista.` | Unexpected error; the stack trace is in the backend log |

Feature specs add their own codes in the same format, raised as `AppError`
(@backend/app/errors.py). The catalog codes are listed under
[Catalog error codes](#catalog-error-codes), the import codes under [Import](#import), the
receipt codes under [Receipts](#receipts).

## Endpoints

### GET /api/health

Reports whether the backend's dependencies are available. The checks run on every request,
so a service started later (for example Ollama) is noticed without a restart. The answer
comes within 3 seconds even when Ollama does not answer. The status is always 200; problems
are reported in the body.

Response `200`:

```json
{
  "status": "ok",
  "model_name": "qwen3:30b-a3b-instruct-2507-q4_K_M",
  "checks": {"database": "ok", "folders": "ok", "ocr": "ok", "model": "ok"}
}
```

| Field | Values | Meaning |
|---|---|---|
| `status` | `ok`, `degraded` | `ok` when every check is `ok` |
| `model_name` | text | The `RRMC_MODEL` setting |
| `checks.database` | `ok`, `unavailable` | The database file exists and can be read |
| `checks.folders` | `ok`, `unavailable` | The import, done and failed folders exist and can be written to |
| `checks.ocr` | `ok`, `unavailable` | Tesseract runs and has the `fin` and `eng` language data |
| `checks.model` | `ok`, `unavailable`, `missing_model` | `unavailable`: Ollama does not answer; `missing_model`: Ollama answers but has not pulled `RRMC_MODEL` |

A model listed by Ollama as `name:latest` matches `RRMC_MODEL=name`. When a health check
finds the model available and it has not been loaded yet, the backend asks Ollama to load it
and keep it loaded (FR-30). With `RRMC_ENGINES=fake`, `ocr` and `model` are always `ok` and
neither Tesseract nor Ollama is called.

Implemented in @backend/app/health/.

### Catalog: groups, categories and products

Implemented in @backend/app/categorization/routes.py. The rules behind each code are in
[categorization](subsystems/categorization/README.md#rules). Names are compared by their
normalized form, so `"  JUOMAT "` and `"Juomat"` are the same name.

A **catalog item** (group or category):

```json
{"id": 4, "name": "Liha", "kind": "category", "parent_id": 1, "product_count": 0, "category_count": null}
```

`product_count` is set for categories and `category_count` for groups; the other one is
`null`. `parent_id` is the group of a category, or `null`.

A **product**:

```json
{"id": 7, "name": "Kevytmaito 1L", "category_id": 11, "category_name": "Maitotuotteet", "group_name": "Ruoka"}
```

| Method and path | Body or query | Success | Errors |
|---|---|---|---|
| `GET /api/categories` | | 200, list of items: groups, each followed by its categories, then the categories without a group; Finnish alphabetical order inside each part | |
| `POST /api/categories` | `{"name", "kind", "parent_id"?}` | 201, the item | 422 `invalid_name`, `invalid_parent`; 409 `duplicate_name` |
| `PATCH /api/categories/{id}` | any of `name`, `kind`, `parent_id`; a left-out field is kept, `"parent_id": null` takes a category out of its group; a budget row moved into a group adds its budget to the group's ([budget](subsystems/budget/README.md#catalog-changes)) | 200, the item | 404 `not_found`; 422 `invalid_name`, `invalid_parent`; 409 `duplicate_name`, `category_has_products`, `group_not_empty` |
| `DELETE /api/categories/{id}` | | 204, no body; the item's budget is deleted with it | 404 `not_found`; 409 `category_in_use`, `group_not_empty` |
| `GET /api/products` | `q` (part of the name, any case), `category_id` (a category, or a group for all its categories); both combine | 200, list of products sorted by name | 422 `unknown_category` |
| `POST /api/products` | `{"name", "category_id"}` | 201, the product | 422 `invalid_name`, `unknown_category`, `not_a_category`; 409 `duplicate_name` |
| `PATCH /api/products/{id}` | any of `name`, `category_id`; a new `category_id` also moves every receipt line linked to the product (FR-36) | 200, the product | 404 `not_found`; 422 as for `POST`; 409 `duplicate_name` |
| `DELETE /api/products/{id}` | | 204, no body; its receipt lines keep their category and lose the link | 404 `not_found` |

A body with a missing field, a wrong JSON type, or a `kind` other than `group` or `category`
gives the foundation's `invalid_request` (422).

#### Catalog error codes

| Status | `error` | Extra field | `message` |
|---|---|---|---|
| 422 | `invalid_name` | | `Nimen pituuden on oltava 1–50 merkkiä.` (groups and categories) or `1–100` (products) |
| 409 | `duplicate_name` | | `Samanniminen ryhmä tai kategoria on jo olemassa.` / `Samanniminen tuote on jo olemassa.` |
| 422 | `invalid_parent` | | `Kategorian voi lisätä vain ryhmään, eikä ryhmä voi kuulua toiseen ryhmään.` |
| 422 | `unknown_category` | | `Kategoriaa ei löydy.` |
| 422 | `not_a_category` | | `Tuotteen voi lisätä vain kategoriaan, ei ryhmään.` |
| 409 | `category_has_products` | | `Kategoriaa, jossa on tuotteita tai kuittirivejä, ei voi muuttaa ryhmäksi.` (products or receipt lines use it) |
| 409 | `category_in_use` | `product_count`; `line_count` when receipt lines use it | `Kategoriaa käyttää 3 tuotetta.`, `Kategoriaa käyttää 2 tuotetta ja 3 kuittiriviä.` or `Kategoriaa käyttää 1 kuittirivi.`: only the counts above 0 (`1 tuote`, `1 kuittirivi` for one) |
| 409 | `group_not_empty` | `category_count` | `Ryhmässä on 3 kategoriaa.` (`1 kategoria` for one) |

`deposit_refund_line` (422, `Pantinpalautusriville ei voi valita kategoriaa.`) comes from
the line correction service, through
[`PATCH /api/receipts/{id}/lines/{line_id}`](#receipts)
([categorization](subsystems/categorization/README.md#line-categorization)).

The texts live in @backend/app/texts.py.

### Import

Implemented in @backend/app/receipt_import/routes.py. The rules are in
[import](subsystems/import/README.md). A run works in the background: `POST` starts it and
returns at once, and the UI polls `GET` while the state is `running`.

| Method and path | Success | Errors |
|---|---|---|
| `GET /api/import` | 200, the state of the current or latest run | |
| `POST /api/import` | 202, the state of the new run (`running`, `total` set, `processed` 0) | 409 `import_running`; 503 `folders_unavailable`, `ocr_unavailable`, `model_unavailable` |

The **run state**:

```json
{
  "state": "finished",
  "total": 4,
  "processed": 4,
  "imported": 1,
  "duplicates": ["b.jpg"],
  "failures": [
    {"file_name": "notes.txt", "reason": "unsupported_format", "message": "Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa."}
  ],
  "started_at": "2026-10-28T10:00:00Z",
  "finished_at": "2026-10-28T10:00:02Z",
  "stopped": null
}
```

| Field | Meaning |
|---|---|
| `state` | `idle` (no run since the backend started), `running`, `finished` |
| `total` | Files found when the run started; ignored entries are not counted |
| `processed` | Files handled so far: imported + duplicates + failed |
| `imported` | Files stored as new receipts and moved to the done folder |
| `duplicates` | Names of files whose image was imported before; they stay in the import folder |
| `failures` | One item per failed file, in processing order: its name in the import folder, the reason and the Finnish message |
| `started_at`, `finished_at` | UTC ISO 8601, or `null` when not reached |
| `stopped` | `null` when the run went through all its files; `{"reason": "model_unavailable", "message": "Kielimalli ei vastaa. Tuonti pysäytettiin; jäljellä olevat kuvat jäivät tuontikansioon."}` when Ollama or the model was lost during the run. Then `processed` is less than `total`, and the files not handled stay in the import folder |

In state `idle` the counts are 0, the lists empty and both times and `stopped` `null`. The state is kept in
memory, so it is `idle` again after a backend restart.

#### Import error codes

| Status | `error` | `message` | When |
|---|---|---|---|
| 409 | `import_running` | `Tuonti on jo käynnissä.` | A run is active |
| 503 | `folders_unavailable` | `Kuvakansioita ei löydy tai niihin ei voi kirjoittaa.` | The import, done or failed folder is missing, cannot be written to, or cannot be listed |
| 503 | `ocr_unavailable` | `Tekstintunnistus ei ole käytettävissä.` | Tesseract with `fin` and `eng` cannot run |
| 503 | `model_unavailable` | `Kielimalli ei ole käytettävissä. Käynnistä Ollama ja tarkista mallin nimi.` | Ollama does not answer, does not have `RRMC_MODEL`, or `RRMC_MODEL` is a cloud model |

The checks run in that order: folders, OCR, model. The import folder is then listed, which
can also give `folders_unavailable`. A start refused by any of them processes nothing.

#### Failure reasons

| `reason` | `message` | When |
|---|---|---|
| `unsupported_format` | `Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa.` | Not `.jpg`, `.jpeg` or `.png` with the matching signature, or an empty file |
| `read_failed` | `Tiedostoa ei voitu lukea.` | The file cannot be read |
| `unreadable_image` | `Kuvaa ei voitu avata.` | The file has an image signature but cannot be decoded |
| `ocr_failed` | `Tekstin tunnistus epäonnistui.` | Tesseract fails or exceeds its time limit |
| `no_text` | `Kuvasta ei löytynyt tekstiä.` | The OCR text is empty or only whitespace |
| `parse_failed` | `Kuittia ei voitu tulkita.` | The model's answer is not a valid receipt, or does not arrive within 300 s |
| `save_failed` | `Kuitin tallennus epäonnistui.` | Writing the receipt or its lines fails |
| `move_failed` | `Tiedostoa ei voitu siirtää valmiiden kansioon.` | The file cannot be moved to the done folder; it stays in the import folder |
| `internal_error` | `Odottamaton virhe. Katso lisätiedot palvelimen lokista.` | Any other error |

### Receipts

Implemented in @backend/app/review/routes.py. The rules are in
[review](subsystems/review/README.md) and the sums in
[calculation](subsystems/calculation/README.md#rules).

| Method and path | Body | Success | Errors |
|---|---|---|---|
| `GET /api/receipts` | | 200, list of receipt summaries: receipts without a purchase date first, then the newest date first; the newest import first within a date | |
| `GET /api/receipts/{id}` | | 200, the receipt | 404 `not_found` |
| `GET /api/receipts/{id}/image` | | 200, the image bytes as `image/jpeg` or `image/png`, `Cache-Control: no-store` | 404 `not_found`, `image_missing`, `no_image` |
| `POST /api/receipts` | `store`, `purchase_date`, `total_cents`, optional `image_file_name` (a failed image; leave it out for no image) | 201, the new receipt: unreviewed, no lines, `imported_at` the creation time | 409 `duplicate_image`; 422 `invalid_store`, `invalid_date`, `invalid_amount`, `image_not_found`, `unsupported_format`, `invalid_request`; 503 `image_move_failed` |
| `DELETE /api/receipts/{id}` | | 204, no body; the receipt and its lines are deleted; products, categories and the image file stay | 404 `not_found`; 409 `receipt_reviewed` |
| `PATCH /api/receipts/{id}` | One or more of `store`, `purchase_date`, `total_cents`, `reviewed`; `reviewed` `true` confirms, `false` makes it unreviewed again, always allowed | 200, the receipt | 404 `not_found`; 422 `invalid_store`, `invalid_date`, `invalid_amount`, `invalid_request` |
| `PATCH /api/receipts/{id}/lines/{line_id}` | One or more of `name`, `amount_cents`, `is_deposit_refund`, `category_id` | 200, the receipt | 404 `not_found` (also a line on another receipt); 422 `invalid_name`, `invalid_amount`, `deposit_refund_amount`, `unknown_category`, `not_a_category`, `deposit_refund_line`, `invalid_request` |
| `POST /api/receipts/{id}/lines` | `name`, `amount_cents`, optional `is_deposit_refund` (default `false`) | 201, the receipt; the line is added after the last one | 404 `not_found`; 422 `invalid_name`, `invalid_amount`, `deposit_refund_amount`, `invalid_request` |
| `DELETE /api/receipts/{id}/lines/{line_id}` | | 200, the receipt; the other lines keep their positions | 404 `not_found` (also a line on another receipt) |

Every edit answers with the whole receipt, because a change can move other lines of the
same product (FR-36) and changes the sums. No edit changes the review state.

**Creating a receipt by hand** (FR-47) checks `store`, `purchase_date` and `total_cents` by
the rules in the table below before any file is touched. With `image_file_name`, the file
must be a failed image (see [Failed images](#failed-images)) with a JPEG or PNG signature;
an image already in a receipt is refused. Its name in the done folder is chosen as at import
(the first free numbered suffix). The receipt is committed first, then the file moves from
the failed folder to the done folder; if the move fails, the receipt is deleted again and
the file stays in the failed folder. The image is not read by OCR or the model. A receipt
without an image has `file_name` `null`, and any number of them may have the same fields.

**Deleting a receipt** (FR-46) is allowed only while it is unreviewed; make it unreviewed
first with `PATCH` and `{"reviewed": false}`. Its file stays in the done folder and is no
longer a duplicate, so the next import of the same image creates a new receipt. Receipt ids
are never reused.

A line edit runs in one transaction in this order: the deposit refund flag and amount, then
the name, then the category; if any rule fails, nothing changes. The rules are in
[review](subsystems/review/README.md#line-edits):

| Field | Rule |
|---|---|
| `name` | Trimmed, inner spaces collapsed; 1–100 characters (`invalid_name`). A new name follows its product (FR-43) |
| `amount_cents` | -99 999 999 to 99 999 999 (`invalid_amount`); any sign on a normal line |
| `is_deposit_refund` | A refund's resulting amount must be below 0 (`deposit_refund_amount`); it has no category (FR-44) |
| `category_id` | The user's category, remembered for its product (FR-13); other lines of the product move with it (FR-36). `deposit_refund_line` for a line that is or becomes a refund |
| `store` | Trimmed, inner spaces collapsed; 0–100 characters (`invalid_store`); `""` is no store |
| `purchase_date` | A real date as `YYYY-MM-DD` (`invalid_date`) |
| `total_cents` | 0 to 99 999 999 (`invalid_amount`) |

Only the sent values are checked against these rules, so a long name read from a receipt
does not stop an amount edit. None of the fields can be set back to `null`.

The bodies are strict: an empty body, a field the endpoint does not know, `null`, and a
value of the wrong JSON type (`"12"` or `1.5` for a number, `1` or `"yes"` for a boolean)
give `invalid_request`. A `category_id` outside SQLite's integer range gives
`unknown_category`, and such a `parent_id` gives `invalid_parent`.

A **receipt summary**:

```json
{"id": 3, "purchase_date": "2026-10-05", "store": "Testikauppa", "total_cents": 349, "warning": false, "reviewed": false}
```

A **receipt**:

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

| Field | Meaning |
|---|---|
| `file_name` | The image's name in the done folder; `null` for a receipt typed in without an image |
| `store`, `purchase_date`, `total_cents` | `null` for a receipt imported before reading existed; `purchase_date` is also `null` when the model's date is not a real date; `store` is `""` when the model found none |
| `lines` | In printed order. `category_source` is `remembered`, `model`, `user` or `null` (FR-15); `group_name` is `null` for a category without a group |
| `line_sum_cents` | Sum of every line amount, deposit refunds included |
| `difference_cents` | `total_cents` minus `line_sum_cents`; `null` without a total |
| `warning` | `true` when the difference is not 0 or the total is missing (FR-20) |
| `subtotals` | One item per category with lines, in catalog order, then the lines without a category (`category_id` `null`) last; deposit refunds are in none (FR-44) |

The OCR text is not returned.

| Status | `error` | `message` | When |
|---|---|---|---|
| 404 | `image_missing` | `Kuvaa ei löydy valmiiden kansiosta.` | The receipt exists, but its file is missing from the done folder, cannot be read, is not JPEG or PNG, or its stored name points outside the folder |
| 404 | `no_image` | `Kuitilla ei ole kuvaa.` | The image of a receipt typed in without one |
| 409 | `receipt_reviewed` | `Vahvistettua kuittia ei voi poistaa. Peru vahvistus ensin.` | Delete of a reviewed receipt |
| 409 | `duplicate_image` | `Kuva on jo tuotu toiseen kuittiin.` | The chosen image is already some receipt's image |
| 422 | `image_not_found` | `Kuvaa ei löydy epäonnistuneiden kansiosta.` | The chosen name is not a failed image: missing, a path, a folder, another suffix, or unreadable |
| 422 | `unsupported_format` | `Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa.` | The chosen file is not a JPEG or PNG: its extension and its signature must agree |
| 503 | `image_move_failed` | `Kuvaa ei voitu siirtää valmiiden kansioon. Kuittia ei luotu.` | The file could not move to the done folder, or the done folder cannot be listed; no receipt was created |
| 422 | `invalid_amount` | `Summa ei kelpaa.` | A line amount or total outside its range |
| 422 | `deposit_refund_amount` | `Pantinpalautuksen summan on oltava negatiivinen.` | A deposit refund whose resulting amount is 0 or more |
| 422 | `invalid_date` | `Päivämäärä ei kelpaa.` | Not a real date as `YYYY-MM-DD` |
| 422 | `invalid_store` | `Kaupan nimi saa olla enintään 100 merkkiä.` | A store longer than 100 characters |

### Failed images

Implemented in @backend/app/review/routes.py and @backend/app/review/failed_images.py. They
serve the new receipt form (receipt-management spec). A **failed image** is a regular file
directly in the failed folder whose name ends in `.jpg`, `.jpeg` or `.png` (any case).

| Method and path | Success | Errors |
|---|---|---|
| `GET /api/failed-images` | 200, `{"file_names": ["a.png", "IMG_2.jpg"]}`, sorted by name ignoring case | 503 `folders_unavailable` |
| `GET /api/failed-images/image?name=<file name>` | 200, the image bytes as `image/jpeg` or `image/png` (from the signature), `Cache-Control: no-store` | 404 `image_not_found` (not a failed image, a path, unreadable, or no JPEG or PNG signature); 422 `invalid_request` without `name` |

The name is a query parameter, because the request log writes the path only; file names stay
out of the log (NFR-3).

### Totals

Implemented in @backend/app/totals/routes.py. The rules are in
[calculation](subsystems/calculation/README.md#period-totals); the package is
[totals](subsystems/totals/README.md).

| Method and path | Query | Success | Errors |
|---|---|---|---|
| `GET /api/totals` | `unit` `month`, `week` or `range`; `from` and `to` as `2026-10`, `2026-W40` or `2026-10-15`, inclusive; at most 24 months, 104 weeks or 731 days | 200, the totals of the period | 422 `invalid_period` |

```json
{
  "unit": "month", "from": "2026-10", "to": "2026-10",
  "start_date": "2026-10-01", "end_date": "2026-10-31",
  "weeks": [
    {"key": "2026-W40", "start_date": "2026-10-01", "end_date": "2026-10-04", "partial": true}
  ],
  "months": [
    {"key": "2026-10", "start_date": "2026-10-01", "end_date": "2026-10-31", "partial": false}
  ],
  "rows": [
    {"kind": "group", "id": 1, "name": "Ruoka", "weeks": [125], "months": [125],
     "categories": [
       {"kind": "category", "id": 2, "name": "Maitotuotteet", "weeks": [125], "months": [125], "categories": []}
     ]},
    {"kind": "none", "id": null, "name": null, "weeks": [199], "months": [199], "categories": []}
  ],
  "week_totals": [324],
  "month_totals": [324],
  "unreviewed_receipts": 1,
  "undated_receipts": 0,
  "archived_years": []
}
```

The example shows one week column of five. A column's dates are its days inside the period;
`partial` is true when that is not the whole week or month. A row's `weeks` and `months` are
cents in column order. `rows` is `[]` when the period has no lines. `unreviewed_receipts`
counts the unreviewed receipts dated in the period; `undated_receipts` counts all receipts
without a purchase date, which are in no period. `archived_years` lists, ascending, the
[archived](#archive) years that overlap the period's dates; their receipts are not in the
totals.

| Status | `error` | `message` | When |
|---|---|---|---|
| 422 | `invalid_period` | `Jakso on virheellinen.` | A missing or malformed `unit`, `from` or `to`; a week or a day that does not exist; `from` after `to`; a longer period |

### Budget

Implemented in @backend/app/budget/routes.py. The rules are in
[calculation](subsystems/calculation/README.md#budget-comparison); the package is
[budget](subsystems/budget/README.md).

| Method and path | Input | Success | Errors |
|---|---|---|---|
| `GET /api/budget` | — | 200, the budget rows and the total | — |
| `PUT /api/budget/{id}` | `{"amount_cents": 40000}`, an integer from 0 to 99999999 | 200, the same shape as `GET` | 404 `not_found`, 422 `not_a_budget_row`, 422 `invalid_amount` |
| `GET /api/budget/comparison` | `month` as `2026-10`; `period` `calendar` (default) or `mid` | 200, the comparison of the period | 422 `invalid_period` |

```json
{
  "rows": [
    {"kind": "group", "id": 1, "name": "Ruoka", "amount_cents": 40000},
    {"kind": "category", "id": 30, "name": "Juomat", "amount_cents": 5000}
  ],
  "total_cents": 45000
}
```

A budget row is a group or a category without a group; a row without a saved amount has 0.
The comparison answers:

```json
{
  "month": "2026-10", "period": "mid",
  "start_date": "2026-10-15", "end_date": "2026-11-14",
  "weeks": [
    {"key": "2026-W42", "start_date": "2026-10-15", "end_date": "2026-10-18", "partial": true}
  ],
  "rows": [
    {"kind": "group", "id": 1, "name": "Ruoka", "budget_cents": 40000,
     "actual_cents": 12500, "remaining_cents": 27500,
     "weeks": [{"budget_cents": 5161, "actual_cents": 12500}]},
    {"kind": "none", "id": null, "name": null, "budget_cents": 0,
     "actual_cents": 199, "remaining_cents": -199,
     "weeks": [{"budget_cents": 0, "actual_cents": 199}]}
  ],
  "total": {"budget_cents": 40000, "actual_cents": 12699, "remaining_cents": 27301,
            "weeks": [{"budget_cents": 5161, "actual_cents": 12699}]},
  "unreviewed_receipts": 1,
  "undated_receipts": 0,
  "archived_years": []
}
```

The example shows one week of five. Only reviewed receipts count as spending. With `mid`,
`month` names the month the period starts in. Every budget row is listed; the `none` row
exists only when reviewed lines have no category. A row's `weeks` follow the order of
`weeks` and add up to its budget. `unreviewed_receipts` counts the unreviewed receipts dated
in the period; `undated_receipts` counts all receipts without a purchase date.
`archived_years` is as in `GET /api/totals`.

| Status | `error` | `message` | When |
|---|---|---|---|
| 404 | `not_found` | `Pyydettyä kohdetta ei löydy.` | `PUT` with an unknown id |
| 422 | `not_a_budget_row` | `Budjetin voi asettaa vain ryhmälle tai ryhmättömälle kategorialle.` | `PUT` for a category inside a group |
| 422 | `invalid_amount` | `Summa ei kelpaa.` | `PUT` with a negative or too large amount |
| 422 | `invalid_period` | `Jakso on virheellinen.` | A missing or malformed `month`, or an unknown `period` |

A float or a string as `amount_cents` answers 422 `invalid_request`.

### Export

Implemented in @backend/app/export/routes.py; the package is
[export](subsystems/export/README.md). The CSV endpoints take the period as
`GET /api/totals` does and answer a CSV download for Finnish Excel (PRD FR-26). The PDF
endpoints answer a PDF download of the totals or of the budget comparison (PRD FR-48).
`GET /api/export/comparison` answers a CSV file of the budget comparison (PRD FR-52).
`GET /api/export/archive/{year}` answers a CSV file of an archived year's totals (PRD FR-53).
The other files read active data only.

| Method and path | Query | Success | Errors |
|---|---|---|---|
| `GET /api/export/lines` | `unit`, `from`, `to` as in `GET /api/totals` | 200, the lines file `kuittirivit_<from>_<to>.csv` | 422 `invalid_period` |
| `GET /api/export/totals` | the same, and `by` `week` or `month` | 200, the totals file `summat_viikot_<from>_<to>.csv` or `summat_kuukaudet_<from>_<to>.csv` | 422 `invalid_period`, then 422 `invalid_request` |
| `GET /api/export/totals/pdf` | the same as `GET /api/export/totals` | 200, `summat_viikot_<from>_<to>.pdf` (A4 landscape) or `summat_kuukaudet_<from>_<to>.pdf` (A4 portrait) | 422 `invalid_period`, then `invalid_request`, then `period_too_long` |
| `GET /api/export/comparison` | `month` and `period` as in `GET /api/budget/comparison`; `weeks` `true`, or `false` (the default) | 200, `vertailu_<month>.csv`, `vertailu_15-14_<month>.csv`, or with `weeks=true` `vertailu_viikot_<month>.csv`, `vertailu_viikot_15-14_<month>.csv` | 422 `invalid_period`, then `invalid_request` |
| `GET /api/export/comparison/pdf` | `month` and `period` as in `GET /api/budget/comparison` | 200, `vertailu_<month>.pdf` or `vertailu_15-14_<month>.pdf` (A4 portrait) | 422 `invalid_period` |
| `GET /api/export/archive/{year}` | — | 200, `arkisto_<year>.csv` | 422 `invalid_year`, 404 `not_found` |

Every 200 answer has `Content-Type: text/csv; charset=utf-8`, `Content-Disposition:
attachment; filename="<name>"` and `Cache-Control: no-store`. The content is UTF-8 with a
byte order mark, `;` between fields and `\r\n` after every row; a period without lines
gives the header row only. The cell rules (quoting, the `'` before a formula-like text) are
in [export](subsystems/export/README.md#csv-format).

The lines file has one row per line of the receipts dated in the period, deposit refunds
included, in purchase date order, then import order, then position:

```text
Päivä;Viikko;Kuukausi;Kauppa;Tuote;Summa;Ryhmä;Kategoria;Pantinpalautus;Kuitin tila
06.10.2026;2026-W41;2026-10;Testikauppa;Ruisleipä;3,00;Ruoka;Leivät;ei;Vahvistettu
06.10.2026;2026-W41;2026-10;Testikauppa;Panttipalautus;-0,40;;;kyllä;Vahvistettu
```

The totals file is in long format: one row per week or month column (`by`) and category
with counted lines in that column, as in `GET /api/totals` (deposit refunds left out;
`Ei kategoriaa` for lines without a category; no group rows, no rows for columns without
lines):

```text
Jakso;Alkaa;Päättyy;Osittainen;Ryhmä;Kategoria;Summa
2026-W40;01.10.2026;04.10.2026;kyllä;Ruoka;Maitotuotteet;1,25
2026-W41;05.10.2026;11.10.2026;ei;;Juomat;2,50
```

The comparison file lists the budget comparison of the Vertailu page (reviewed receipts
only) in long format: the `Koko jakso` rows, then with `weeks=true` one block per week
column. Dates are `dd.mm.yyyy`; there is no total row:

```text
Jakso;Alkaa;Päättyy;Osittainen;Tyyppi;Nimi;Budjetti;Toteutunut;Jäljellä
Koko jakso;01.10.2026;31.10.2026;ei;ryhmä;Ruoka;400,00;125,00;275,00
Koko jakso;01.10.2026;31.10.2026;ei;kategoria;Ei kategoriaa;0,00;1,99;-1,99
2026-W40;01.10.2026;04.10.2026;kyllä;ryhmä;Ruoka;51,61;125,00;-73,39
```

The archive file lists the product totals of an archived year in long format: a block per
month with lines, then the year block. Inside a block the rows follow the order of
[the year totals](#archive); there are no group or category sum rows:

```text
Jakso;Alkaa;Päättyy;Ryhmä;Kategoria;Tuote;Summa
2025-01;01.01.2025;31.01.2025;Maitotuotteet;Maito;Maito 1l;5,00
2025;01.01.2025;31.12.2025;Maitotuotteet;Maito;Maito 1l;5,00
```

| Status | `error` | `message` | When |
|---|---|---|---|
| 422 | `invalid_period` | `Jakso on virheellinen.` | As in `GET /api/totals`, or as in `GET /api/budget/comparison` for the comparison files; checked first |
| 422 | `invalid_request` | `Pyyntö on virheellinen.` | `by` of the totals file is missing or not `week` or `month`; `weeks` of the comparison file is not `true` or `false` |
| 422 | `period_too_long` | `Jakso on liian pitkä PDF-tiedostoon.` | A totals PDF over 31 days (`by` `week`) or 366 days (`by` `month`); checked last |
| 422 | `invalid_year` | `Vuosi on virheellinen.` | The archive file's year is not four digits from 2000 to 9999 |
| 404 | `not_found` | `Pyydettyä kohdetta ei löydy.` | The archive file's year is not archived |

A PDF answer has `Content-Type: application/pdf` and the same `Content-Disposition` and
`Cache-Control` as a CSV answer. The weekly PDF is one table of the week columns; the
monthly PDF stacks a block per month, then `Koko jakso` for a period over 31 days; the
comparison PDF is the Vertailu month table. A period without counted lines shows
`Ei ostoksia valitulla jaksolla.` instead of a table. The layout is in
[export](subsystems/export/README.md#pdf-layout). The totals PDF and the comparison PDF add
the `archived_years` sentence to their notes.

### Archive

Implemented in @backend/app/archive/routes.py; the package is
[archive](subsystems/archive/README.md). Archiving moves the reviewed receipts of a finished
year out of the active data (PRD FR-40–FR-42, FR-53). `{year}` is four digits from 2000 to
9999.

| Method and path | Success | Errors |
|---|---|---|
| `GET /api/archive` | 200, the archived years and the years that can be archived | — |
| `POST /api/archive/{year}` | 200, the counts and the images that were not moved | 422 `invalid_year`; 409 `year_not_finished`, `import_running`, `unreviewed_receipts`; 404 `nothing_to_archive` |
| `DELETE /api/archive/{year}` | 200, the deleted counts | 422 `invalid_year`, 404 `not_found` |
| `GET /api/archive/{year}/totals` | 200, the year's totals per group, category and product | 422 `invalid_year`, 404 `not_found` |

`GET /api/archive` answers both lists sorted by year, newest first. A candidate is a year
before the current one (Finnish time) with active dated receipts; `images` counts receipts
with an image:

```json
{
  "archived": [{"year": 2025, "receipts": 12, "lines": 140, "images": 11}],
  "candidates": [{"year": 2024, "receipts": 3, "lines": 20, "images": 3, "unreviewed": 1}]
}
```

`POST` checks in the order of the error table, then moves the year in one transaction and
the images after the commit. A year already in the archive gets the new receipts added. An
image that could not be moved stays in the done folder and is named in the answer:

```json
{"year": 2025, "receipts": 12, "lines": 140, "images_moved": 10, "images_not_moved": ["a.jpg"]}
```

`DELETE` deletes the year's archived receipts and lines and answers
`{"year": 2025, "receipts": 12, "lines": 140}`. Image files are not touched; after the
delete the year's images are no longer duplicates.

`GET /api/archive/{year}/totals` answers a tree of rows: a group sums its categories, a
category its products, a product the lines with its name in that category. Lines without a
category form a `none` row (`name` `null`) with their products. At each level rows are
sorted by name in Finnish order, `none` last; deposit refunds are left out. `months` has 12
entries, January first, in cents. The example shortens the lists:

```json
{
  "year": 2025,
  "months": ["2025-01", "2025-02", "2025-12"],
  "rows": [
    {"kind": "group", "name": "Maitotuotteet", "months": [900, 0, 0], "total": 900,
     "children": [
       {"kind": "category", "name": "Maito", "months": [500, 0, 0], "total": 500,
        "children": [{"kind": "product", "name": "Maito 1l", "months": [500, 0, 0],
                      "total": 500, "children": []}]}
     ]}
  ],
  "month_totals": [900, 0, 0],
  "total": 900
}
```

| Status | `error` | `message` | When |
|---|---|---|---|
| 422 | `invalid_year` | `Vuosi on virheellinen.` | The year is not four digits from 2000 to 9999 |
| 409 | `year_not_finished` | `Vain päättyneen vuoden voi arkistoida.` | The year is the current year (Finnish time) or later |
| 409 | `import_running` | `Tuonti on käynnissä. Arkistoi vuosi, kun tuonti on valmis.` | An import run is running |
| 404 | `nothing_to_archive` | `Vuodelta ei ole arkistoitavia kuitteja.` | The year has no active receipts |
| 409 | `unreviewed_receipts` | `Vuotta ei voi arkistoida: vuodella on 1 tarkistamaton kuitti.` | The year has unreviewed receipts; adds `count` |
| 404 | `not_found` | `Pyydettyä kohdetta ei löydy.` | `DELETE` or totals of a year that is not archived |

Archived receipts are not served one by one: an archived receipt's old id answers 404 in
`/api/receipts/{id}`. An archived image is still a duplicate for the import and for
`POST /api/receipts`.

## Subsystems

- [ui](subsystems/ui/README.md) — the only client of the API
- [categorization](subsystems/categorization/README.md) — the rules behind the catalog
  endpoints
- [import](subsystems/import/README.md) — the rules behind the import endpoints
- [review](subsystems/review/README.md) — the receipt endpoints
- [totals](subsystems/totals/README.md) — the totals endpoint
- [budget](subsystems/budget/README.md) — the budget and comparison endpoints
- [export](subsystems/export/README.md) — the CSV and PDF export endpoints
- [archive](subsystems/archive/README.md) — the archive endpoints

## Related Documents

- [architecture.md](architecture.md): dependency rules and cross-cutting rules
- [Foundation spec](../specs/features/foundation.md) PC5 and PC8
- [Product management spec](../specs/features/product-management.md): the catalog endpoints
- [Receipt import spec](../specs/features/receipt-import.md): the import endpoints
- [Receipt reading spec](../specs/features/receipt-reading.md): the reading step, its
  failure reasons and the start checks
- [Receipt review spec](../specs/features/receipt-review.md): the receipt endpoints
- [Line editing spec](../specs/features/line-editing.md): line and receipt edits
- [Category totals spec](../specs/features/totals.md): the totals endpoint
- [Archiving spec](../specs/features/archiving.md): the archive endpoints
- [development.md](development.md#troubleshooting): what the health results mean for the user
