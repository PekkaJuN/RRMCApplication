# API Reference

- **Status:** In Progress (health, catalog and import endpoints, the import with reading; receipt, totals and export
  endpoints are added by their specs)
- **Updated:** 2026-10-28

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
[Catalog error codes](#catalog-error-codes), the import codes under [Import](#import).

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
| `PATCH /api/products/{id}` | any of `name`, `category_id` | 200, the product | 404 `not_found`; 422 as for `POST`; 409 `duplicate_name` |
| `DELETE /api/products/{id}` | | 204, no body | 404 `not_found` |

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
| 409 | `category_has_products` | | `Kategoriaa, jossa on tuotteita, ei voi muuttaa ryhmäksi.` |
| 409 | `category_in_use` | `product_count` | `Kategoriaa käyttää 3 tuotetta.` (`1 tuote` for one) |
| 409 | `group_not_empty` | `category_count` | `Ryhmässä on 3 kategoriaa.` (`1 kategoria` for one) |

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

## Subsystems

- [ui](subsystems/ui/README.md) — the only client of the API
- [categorization](subsystems/categorization/README.md) — the rules behind the catalog
  endpoints
- [import](subsystems/import/README.md) — the rules behind the import endpoints

## Related Documents

- [architecture.md](architecture.md): dependency rules and cross-cutting rules
- [Foundation spec](../specs/features/foundation.md) PC5 and PC8
- [Product management spec](../specs/features/product-management.md): the catalog endpoints
- [Receipt import spec](../specs/features/receipt-import.md): the import endpoints
- [Receipt reading spec](../specs/features/receipt-reading.md): the reading step, its
  failure reasons and the start checks
- [development.md](development.md#troubleshooting): what the health results mean for the user
