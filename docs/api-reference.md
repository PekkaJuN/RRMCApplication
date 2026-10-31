# API Reference

- **Status:** In Progress (health, catalog, import and receipt endpoints; line editing, totals
  and export endpoints are added by their specs)
- **Updated:** 2026-10-31

## Overview

The backend serves a JSON REST API under `/api`. It listens only on `127.0.0.1` (default
port `8000`). There is no login: the app is local and single-user.

The UI calls the API on its own origin (`http://127.0.0.1:5173/api/...`); the Vite dev
server forwards these requests to the backend. CORS allows only
`http://127.0.0.1:<RRMC_UI_PORT>`.

Each request is logged as one line with method, path, status and duration. Query strings and
bodies are never logged.

## Error format

Every error response has this body:

```json
{"error": "<code>", "message": "<Finnish text for the user>"}
```

Some codes add fields next to these two, for example `product_count`; the endpoint lists
them.

`error` is a stable `snake_case` code for programs; `message` is shown to the user as is.
Messages come from @backend/app/texts.py and never contain receipt content.

| Status | `error` | `message` | When |
|---|---|---|---|
| 404 | `not_found` | `Pyydettyä kohdetta ei löydy.` | Unknown `/api/...` path, or an id that does not exist |
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
| `PATCH /api/categories/{id}` | any of `name`, `kind`, `parent_id`; a left-out field is kept, `"parent_id": null` takes a category out of its group | 200, the item | 404 `not_found`; 422 `invalid_name`, `invalid_parent`; 409 `duplicate_name`, `category_has_products`, `group_not_empty` |
| `DELETE /api/categories/{id}` | | 204, no body | 404 `not_found`; 409 `category_in_use`, `group_not_empty` |
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

The checks run in that order: folders, OCR, model. A start refused by any of them processes
nothing.

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
| `GET /api/receipts/{id}/image` | | 200, the image bytes as `image/jpeg` or `image/png`, `Cache-Control: no-store` | 404 `not_found`, `image_missing` |
| `PATCH /api/receipts/{id}` | `{"reviewed": true}` confirms, `false` makes it unreviewed again; always allowed | 200, the receipt | 404 `not_found`; 422 `invalid_request` |
| `PATCH /api/receipts/{id}/lines/{line_id}` | `{"category_id": n}`: the user's category for the line, remembered for its product (FR-13); other lines of the product move with it (FR-36) | 200, the receipt | 404 `not_found` (also a line on another receipt); 422 `unknown_category`, `not_a_category`, `deposit_refund_line`, `invalid_name`, `invalid_request` |

The bodies are strict: a missing field, `null`, `"12"` or `true` for `category_id`, and
anything but `true` or `false` for `reviewed` give `invalid_request`. A category choice does
not change the review state.

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
| `store`, `purchase_date`, `total_cents` | `null` for a receipt imported before reading existed; `store` is `""` when the model found none |
| `lines` | In printed order. `category_source` is `remembered`, `model`, `user` or `null` (FR-15); `group_name` is `null` for a category without a group |
| `line_sum_cents` | Sum of every line amount, deposit refunds included |
| `difference_cents` | `total_cents` minus `line_sum_cents`; `null` without a total |
| `warning` | `true` when the difference is not 0 or the total is missing (FR-20) |
| `subtotals` | One item per category with lines, in catalog order, then the lines without a category (`category_id` `null`) last; deposit refunds are in none (FR-44) |

The OCR text is not returned.

| Status | `error` | `message` | When |
|---|---|---|---|
| 404 | `image_missing` | `Kuvaa ei löydy valmiiden kansiosta.` | The receipt exists, but its file is missing from the done folder, cannot be read, is not JPEG or PNG, or its stored name points outside the folder |

## Subsystems

- [ui](subsystems/ui/README.md) — the only client of the API
- [categorization](subsystems/categorization/README.md) — the rules behind the catalog
  endpoints
- [import](subsystems/import/README.md) — the rules behind the import endpoints
- [review](subsystems/review/README.md) — the receipt endpoints

## Related Documents

- [architecture.md](architecture.md): dependency rules and cross-cutting rules
- [Foundation spec](../specs/features/foundation.md) PC5 and PC8
- [Product management spec](../specs/features/product-management.md): the catalog endpoints
- [Receipt import spec](../specs/features/receipt-import.md): the import endpoints
- [Receipt reading spec](../specs/features/receipt-reading.md): the reading step, its
  failure reasons and the start checks
- [Receipt review spec](../specs/features/receipt-review.md): the receipt endpoints
- [development.md](development.md#troubleshooting): what the health results mean for the user
