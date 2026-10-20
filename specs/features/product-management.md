# Feature: Product management

## Overview
- **Status:** Draft
- **Created:** 2026-10-20
- **Implements:** PRD FR-11, FR-33, FR-34, FR-35, FR-36 (rule only), FR-37, and the basic
  part of FR-14 (name normalization without OCR mix-ups)
- **Affected subsystems:** storage, categorization, ui (docs not written yet:
  `docs/subsystems/storage/README.md`, `docs/subsystems/categorization/README.md`,
  `docs/subsystems/ui/README.md`)

## Problem Statement
The app must remember which category each product belongs to, so that a correction is made
once and reused on every later receipt (PRD G3). That memory is the product list. Before
receipts can be imported and categorized, the categories and the product list must exist,
and the user must be able to see and fix them directly: add a product ahead of time, move a
product to another category, remove a wrong entry, and keep the category list tidy.

## Current Behavior
None (new). There is no source code yet.

## Proposed Change

- **PC1 Categories.** The user can list, add, rename and delete categories. Each category
  shows how many products use it.
- **PC2 Default categories.** On first start, when there are no categories, the app creates a
  default list once. Deleting categories later does not bring the defaults back.
- **PC3 Products.** The user can list, add, rename, recategorize and delete products. Every
  product has exactly one category.
- **PC4 Search and filter.** The product list can be searched by name and filtered by
  category.
- **PC5 Normalization and uniqueness.** Names are normalized for comparison. Two products
  cannot have the same normalized name. Two categories cannot have the same normalized name.
  The display name keeps what the user typed (trimmed, with inner spaces collapsed).
- **PC6 Delete protection.** A category used by any product cannot be deleted. The user is
  told how many products use it.
- **PC7 Persistence.** Categories and products are stored in SQLite and survive a restart.
  The database location comes from the settings file (PRD FR-32); the default is a file
  outside version control.
- **PC8 Products page.** The UI has a Products page: a category panel (list, add, rename,
  delete, product counts) and a product table (name, category dropdown, search box,
  category filter, add, rename, delete). Errors from the backend are shown next to the
  field or action that caused them. Delete actions ask for confirmation in the page (no
  browser dialog).

### Normalization rule (PC5)

1. Unicode NFC.
2. Trim leading and trailing whitespace.
3. Collapse every run of inner whitespace to one space.
4. Case-fold (lowercase), keeping å, ä and ö as letters.

The **display name** is the result of steps 1–3. The **normalized name** is the result of
steps 1–4. Example: `"  Kevytmaito   1L "` → display `"Kevytmaito 1L"`, normalized
`"kevytmaito 1l"`.

### Validation

| Field | Rule |
|---|---|
| Category name | 1–50 characters after display normalization |
| Product name | 1–100 characters after display normalization |
| Product category | Must be an existing category id |

### API (local REST, JSON)

| Method and path | Purpose | Success | Errors |
|---|---|---|---|
| `GET /api/categories` | All categories, sorted by normalized name, each with `id`, `name`, `product_count` | 200 | |
| `POST /api/categories` `{name}` | Add | 201 + category | 422 invalid name; 409 duplicate |
| `PATCH /api/categories/{id}` `{name}` | Rename | 200 + category | 404; 422; 409 duplicate of another category |
| `DELETE /api/categories/{id}` | Delete | 204 | 404; 409 in use, body includes `product_count` |
| `GET /api/products?q=&category_id=` | Products sorted by normalized name, each with `id`, `name`, `category_id`, `category_name`; `q` matches a substring of the normalized name (the query is normalized the same way); filters combine with AND | 200 | 422 invalid `category_id` |
| `POST /api/products` `{name, category_id}` | Add | 201 + product | 422 invalid name or unknown category; 409 duplicate |
| `PATCH /api/products/{id}` `{name?, category_id?}` | Rename and/or recategorize | 200 + product | 404; 422; 409 duplicate of another product |
| `DELETE /api/products/{id}` | Delete | 204 | 404 |

Error bodies have the form `{"error": "<code>", "message": "<text for the user>"}` plus any
extra fields listed above. Codes: `invalid_name`, `duplicate_name`, `unknown_category`,
`category_in_use`, `not_found`.

### Out of Scope
- Receipts, receipt lines and applying products to them (FR-12, FR-13, FR-15): later specs.
  FR-36 is recorded here as a rule; it is tested when receipt lines exist.
- OCR mix-up handling and fuzzy matching in normalization (rest of FR-14).
- Merging products and product aliases.
- Import and export of the product list.
- Pagination: the product list is expected to stay in the low thousands.
- Undo.

## Acceptance Criteria

### AC1: Default categories are created on first start
**Given** an empty database
**When** the backend starts
**Then** `GET /api/categories` returns exactly the default categories
[NEEDS CLARIFICATION: default list and its language], each with `product_count` 0

### AC2: Defaults are not recreated
**Given** the defaults were created and the user deleted all categories
**When** the backend restarts
**Then** `GET /api/categories` returns an empty list

### AC3: Add a category
**Given** no category named "Lemmikit"
**When** the user adds a category named `"  Lemmikit  "`
**Then** the response is 201 with name `"Lemmikit"`, and the category appears in the list with `product_count` 0

### AC4: Duplicate category names are rejected
**Given** a category "Lemmikit"
**When** the user adds a category named `"lemmikit"`
**Then** the response is 409 with error `duplicate_name`, and the list still has one "Lemmikit"

### AC5: Invalid category names are rejected
**Given** any state
**When** the user adds or renames a category to `""`, `"   "`, or a 51-character name
**Then** the response is 422 with error `invalid_name`, and nothing changes

### AC6: Rename a category
**Given** a category "Juomat" used by 2 products
**When** the user renames it to "Virvoitusjuomat"
**Then** the response is 200, both products now show category name "Virvoitusjuomat", and `product_count` is still 2

### AC7: Renaming a category to a case variant of its own name is allowed
**Given** a category "juomat"
**When** the user renames it to "Juomat"
**Then** the response is 200 and the name is "Juomat"

### AC8: A category in use cannot be deleted
**Given** a category "Juomat" used by 3 products
**When** the user deletes it
**Then** the response is 409 with error `category_in_use` and `product_count` 3, the category still exists, and the UI shows a message that 3 products use it

### AC9: An unused category can be deleted
**Given** a category "Lemmikit" with no products
**When** the user deletes it and confirms
**Then** the response is 204 and the category is no longer listed

### AC10: Add a product
**Given** a category "Maitotuotteet" and no product "kevytmaito 1l"
**When** the user adds product `"  Kevytmaito   1L "` in "Maitotuotteet"
**Then** the response is 201 with name `"Kevytmaito 1L"` and category "Maitotuotteet", and the category's `product_count` increases by 1

### AC11: Duplicate product names are rejected after normalization
**Given** a product "Kevytmaito 1L"
**When** the user adds product `"KEVYTMAITO  1l"`
**Then** the response is 409 with error `duplicate_name`, and there is still one such product

### AC12: Invalid product input is rejected
**Given** any state
**When** the user adds a product with an empty or 101-character name, or with a category id that does not exist
**Then** the response is 422 with error `invalid_name` or `unknown_category` respectively, and nothing changes

### AC13: Change a product's category
**Given** product "Kevytmaito 1L" in "Maitotuotteet" (count 1) and a category "Juomat" (count 0)
**When** the user selects "Juomat" in the product's category dropdown
**Then** the response is 200, the product shows "Juomat", and the counts become "Maitotuotteet" 0 and "Juomat" 1

### AC14: Rename a product
**Given** product "Kevytmaito 1L" and product "Rasvaton maito 1L"
**When** the user renames "Kevytmaito 1L" to "Kevytmaito 1,5L"
**Then** the response is 200 with the new name; renaming it instead to "rasvaton maito 1l" returns 409 `duplicate_name` and leaves the name unchanged

### AC15: Delete a product
**Given** product "Kevytmaito 1L" in "Maitotuotteet" (count 1)
**When** the user deletes it and confirms
**Then** the response is 204, the product is no longer listed, and the count becomes 0

### AC16: Search products
**Given** products "Kevytmaito 1L", "Rasvaton maito 1L" and "Ruisleipä"
**When** the user types `"MAITO"` in the search box
**Then** exactly "Kevytmaito 1L" and "Rasvaton maito 1L" are shown, sorted by name

### AC17: Filter products by category
**Given** "Kevytmaito 1L" in "Maitotuotteet" and "Ruisleipä" in "Leivät"
**When** the user filters by "Leivät", then also types `"maito"`
**Then** first only "Ruisleipä" is shown, then no products and an empty-state message

### AC18: Data survives a restart
**Given** a category and a product were added
**When** the backend is stopped and started again with the same settings
**Then** both are listed unchanged

### AC19: Missing items return 404
**Given** no category or product with id 9999
**When** the user renames or deletes id 9999
**Then** the response is 404 with error `not_found`

### AC20: Backend errors are shown in the UI
**Given** the Products page is open
**When** an action returns 409, 422 or 404, or the backend cannot be reached
**Then** the page shows the `message` (or a "backend not reachable" message) next to the action, and the lists stay as they were

### AC21: Deletion needs confirmation
**Given** the Products page is open
**When** the user clicks delete on a product or category and then cancels
**Then** no request is sent and nothing changes

## Files to Modify

The project has no code yet. This spec includes the minimal backend and frontend setup that
this feature needs. Exact paths are fixed in the Plan phase.

| File | Change |
|---|---|
| `backend/pyproject.toml` | New: backend project, dependencies (FastAPI, Uvicorn, pytest, ruff) |
| `backend/app/main.py` | New: FastAPI app, routers, startup seeding (PC2) |
| `backend/app/settings.py` | New: settings file loading, database path (PC7) |
| `backend/app/db.py` | New: SQLite connection and schema for category and product |
| `backend/app/catalog/` | New: normalization, category and product services and API routes |
| `backend/tests/` | New: unit and integration tests |
| `config.example.toml` | New: example settings file (database path) |
| `frontend/` (Vite scaffold) | New: React + TypeScript project, Vitest, Testing Library, MSW, Playwright |
| `frontend/src/api/catalog.ts` | New: API client for categories and products |
| `frontend/src/pages/ProductsPage.tsx` | New: Products page (PC8) |
| `frontend/src/**/*.test.tsx`, `frontend/e2e/` | New: component and E2E tests |
| `docs/datamodel.md` | New: category and product entities |
| `docs/api-reference.md` | New: the endpoints above |
| `docs/development.md` | New: setup and commands, then sync the Commands table in `AGENTS.md` |
| `docs/subsystems/storage/README.md`, `docs/subsystems/categorization/README.md`, `docs/subsystems/ui/README.md` | New |
| `docs/content-plan.md` | Update statuses |
| `docs/adr/0001-...` | New: record the decided stack |
| `specs/README.md` | New: spec index |

## Risk
- **What could break:** nothing existing (greenfield). Later specs depend on the category and
  product schema; a schema change after receipts exist needs a migration.
- **Rollback:** delete the database file and revert the commit.
- **Dependencies:** Python, Node.js; no Tesseract or Ollama needed for this feature.
- **Privacy:** product names describe purchases. They stay in the local database and are not
  logged.

## Testing Strategy (MANDATORY)

### Unit tests (backend, pytest)
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC3, AC10 | `normalize_display` | trims and collapses | `"  Kevytmaito   1L "` | normalize | `"Kevytmaito 1L"` | none |
| AC11 | `normalize_key` | case-folds | `"KEVYTMAITO  1l"` | normalize | `"kevytmaito 1l"` | none |
| AC11 | `normalize_key` | Nordic letters kept | `"RUISLEIPÄ"` | normalize | `"ruisleipä"` | none |
| AC11 | `normalize_key` | NFC | decomposed `"a"+"̈"` | normalize | `"ä"` (one code point) | none |
| AC5 | `validate_category_name` | empty / spaces | `""`, `"   "` | validate | `invalid_name` | none |
| AC5 | `validate_category_name` | boundary | 50 and 51 characters | validate | 50 ok, 51 `invalid_name` | none |
| AC12 | `validate_product_name` | boundary | 100 and 101 characters | validate | 100 ok, 101 `invalid_name` | none |
| AC1, AC2 | `seed_defaults` | first start | empty DB, not seeded | seed | default list created, seeded flag set | temp SQLite |
| AC2 | `seed_defaults` | already seeded | seeded flag set, no categories | seed | nothing created | temp SQLite |
| AC4, AC7 | `CategoryService.rename` | own case variant vs other duplicate | "juomat" and "Lemmikit" | rename "juomat"→"Juomat"; "juomat"→"lemmikit" | ok; `duplicate_name` | temp SQLite |
| AC8, AC9 | `CategoryService.delete` | in use / unused | counts 3 / 0 | delete | `category_in_use` with 3 / deleted | temp SQLite |
| AC16, AC17 | `ProductService.list` | search + filter | three products in two categories | `q="MAITO"`; `category_id` + `q` | two products sorted; AND result | temp SQLite |

### Integration tests (FastAPI TestClient, temporary SQLite file)
| AC | Scenario | Request | Expected output | Status |
|---|---|---|---|---|
| AC1 | defaults on first start | `GET /api/categories` | default list, counts 0 | 200 |
| AC3 | add category | `POST /api/categories {"name":"  Lemmikit  "}` | name "Lemmikit" | 201 |
| AC4 | duplicate category | `POST /api/categories {"name":"lemmikit"}` | `duplicate_name` | 409 |
| AC5 | invalid category | `POST` with `"   "` | `invalid_name` | 422 |
| AC6 | rename used category | `PATCH /api/categories/{id}` | products show new name | 200 |
| AC8 | delete used category | `DELETE /api/categories/{id}` | `category_in_use`, `product_count` 3 | 409 |
| AC9 | delete unused category | `DELETE /api/categories/{id}` | empty body | 204 |
| AC10 | add product | `POST /api/products` | display name, category, count +1 | 201 |
| AC11 | duplicate product | `POST /api/products {"name":"KEVYTMAITO  1l",...}` | `duplicate_name` | 409 |
| AC12 | unknown category | `POST /api/products {"category_id":9999,...}` | `unknown_category` | 422 |
| AC13 | recategorize | `PATCH /api/products/{id} {"category_id":...}` | new category; counts updated | 200 |
| AC14 | rename to duplicate | `PATCH /api/products/{id} {"name":"rasvaton maito 1l"}` | `duplicate_name`, unchanged | 409 |
| AC15 | delete product | `DELETE /api/products/{id}` | count −1 | 204 |
| AC16 | search | `GET /api/products?q=MAITO` | two products, sorted | 200 |
| AC17 | filter + search | `GET /api/products?category_id=..&q=maito` | empty list | 200 |
| AC18 | restart | add, recreate app with same DB file, `GET` | data unchanged | 200 |
| AC19 | missing id | `PATCH`/`DELETE` id 9999 | `not_found` | 404 |

### Component tests (Vitest + React Testing Library, API mocked with MSW)
| AC | Component | Case | Given | When | Then |
|---|---|---|---|---|---|
| AC13 | ProductsPage | recategorize | two categories, one product | choose other category in the row's dropdown | PATCH sent; row and counts updated |
| AC16 | ProductsPage | search | three products | type "MAITO" | list request with `q`; two rows shown |
| AC17 | ProductsPage | empty state | filter returns [] | apply filter | empty-state message shown |
| AC8, AC20 | ProductsPage | category in use | DELETE returns 409 with count 3 | delete and confirm | message about 3 products next to the category; category still listed |
| AC11, AC20 | ProductsPage | duplicate product | POST returns 409 | add product | message next to the add form; list unchanged |
| AC20 | ProductsPage | backend down | network error | load page | "backend not reachable" message |
| AC21 | ProductsPage | cancel delete | one product | click delete, then cancel | no DELETE request; row still shown |

### E2E tests (Playwright, real backend, temporary database)
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC3, AC10, AC13, AC15, AC9 | manage catalog | 1. open Products 2. add category "Testikategoria" 3. add product "Testituote" in it 4. move it to a default category 5. delete the product 6. delete "Testikategoria" | each step visible in the UI; final state has neither item |
| AC8 | protected delete | 1. add product in a category 2. try to delete that category | message shown; category remains |

### Coverage target
- Backend: 90 % lines for this feature; normalization, validation and delete protection:
  every branch.
- Frontend: 80 % lines for the Products page and API client.

### Test data
- Synthetic product and category names only (as in the ACs).
- Each backend test uses its own temporary SQLite file.
- MSW handlers return fixed JSON for categories and products.

## Related Documentation (MANDATORY)
- PRD: `specs/PRD.md` sections 6.3, 6.7 (FR-32), 6.8, 7.2, 7.5
- Tier 1: `docs/datamodel.md`, `docs/api-reference.md`, `docs/development.md` (to be written
  in this feature)
- Tier 2: storage, categorization and ui subsystem READMEs (to be written in this feature)
- Development rules: `AGENTS.md`; workflows: `.agents/skills/spec/SKILL.md`,
  `.agents/skills/tdd/SKILL.md`

## Open Questions
1. [NEEDS CLARIFICATION] Default category list, and UI language (Finnish or English). This
   decides AC1. A proposal for review: Maitotuotteet, Liha ja kala, Hedelmät ja vihannekset,
   Leivät, Kuivatuotteet, Pakasteet, Juomat, Alkoholi, Herkut, Hygienia, Kodin tarvikkeet,
   Lemmikit, Muut.
2. [NEEDS CLARIFICATION] Confirm that the minimal backend and frontend setup belongs in this
   spec rather than in a separate setup spec.
