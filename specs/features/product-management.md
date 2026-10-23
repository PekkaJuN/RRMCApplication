# Feature: Product management

## Overview
- **Status:** Draft
- **Created:** 2026-10-20
- **Updated:** 2026-10-20: groups, default list from PRD 6.9, Finnish UI, FR-36 rule;
  2026-10-21: FR-43 and FR-44 noted as out of scope;
  2026-10-23: project setup moved to the foundation spec
- **Depends on:** [Project foundation](foundation.md)
- **Implements:** PRD FR-11, FR-33, FR-34, FR-35, FR-37, FR-38, FR-39, the default list in
  PRD 6.9, NFR-15 for this page, and the basic part of FR-14 (name normalization without OCR
  mix-ups). FR-36 is recorded as a rule; it is implemented with receipt lines (see Out of Scope).
- **Affected subsystems:** storage, categorization, ui (docs not written yet:
  `docs/subsystems/storage/README.md`, `docs/subsystems/categorization/README.md`,
  `docs/subsystems/ui/README.md`)

## Problem Statement
The app must remember which category each product belongs to, so that a correction is made
once and reused on every later receipt (PRD G3). That memory is the product list. Before
receipts can be imported and categorized, the categories and the product list must exist,
and the user must be able to see and fix them directly: add a product ahead of time, move a
product to another category, remove a wrong entry, and organize categories into groups such
as Ruoka and Auto.

## Current Behavior
None (new). There is no source code yet.

## Proposed Change

### Concepts

- A **group** (yläryhmä) holds categories. It has no parent and never holds products.
  A group can be empty, e.g. right after the user creates it.
- A **category** (kategoria) holds products. It belongs to one group or to none.
- Groups cannot be nested: the hierarchy has at most two levels.
- Groups and categories are stored in one table with a `kind` field (`group` or `category`)
  and an optional `parent_id`. They share one name namespace.

### Parts

- **PC1 Groups and categories.** The user can list, add, rename and delete groups and
  categories. A group shows how many categories it has; a category shows how many products
  it has.
- **PC2 Default list.** On first start, when there are no groups or categories, the app
  creates the default list of PRD 6.9 once: groups Ruoka (10 categories) and Auto
  (3 categories), and 8 categories without a group. Deleting them later does not bring them
  back.
- **PC3 Organizing.** The user can create a new group, add new or existing categories to it,
  move a category to another group, and take a category out of its group. An empty category
  without a group can be turned into a group; a group without categories can be turned into
  a category.
- **PC4 Products.** The user can list, add, rename, recategorize and delete products. Every
  product has exactly one category, never a group.
- **PC5 Search and filter.** The product list can be searched by name and filtered by a
  category or by a group (a group filter shows the products of all its categories).
- **PC6 Normalization and uniqueness.** Names are normalized for comparison. Two products
  cannot have the same normalized name. No two groups or categories can have the same
  normalized name. The display name keeps what the user typed (trimmed, with inner spaces
  collapsed).
- **PC7 Delete protection.** A category used by any product cannot be deleted; a group that
  has categories cannot be deleted. The user is told how many products or categories are
  in the way.
- **PC8 Persistence.** Groups, categories and products are stored in SQLite and survive a
  restart. The database, its location and the migration mechanism come from the
  [foundation spec](foundation.md); this feature adds its tables as a migration.
- **PC9 Products page (Finnish UI).** The UI has a page "Tuotteet" with:
  - a category panel showing the groups with their categories, then the categories without
    a group; actions to add, rename, move, convert and delete, with counts;
  - a product table: name, category dropdown, search box, filter, add, rename, delete.
  Category dropdowns list categories under their group headings; groups are headings only
  and cannot be chosen. All visible text is in Finnish. Errors from the backend are shown
  next to the field or action that caused them. Delete actions ask for confirmation in the
  page (no browser dialog).

### Normalization rule (PC6)

1. Unicode NFC.
2. Trim leading and trailing whitespace.
3. Collapse every run of inner whitespace to one space.
4. Case-fold (lowercase), keeping å, ä and ö as letters.

The **display name** is the result of steps 1–3. The **normalized name** is the result of
steps 1–4. Example: `"  Kevytmaito   1L "` → display `"Kevytmaito 1L"`, normalized
`"kevytmaito 1l"`.

### Sorting

Lists are sorted by normalized name in Finnish alphabetical order (å, ä, ö after z).
In the category panel and dropdowns, groups come first, each followed by its categories,
then the categories without a group.

### Validation

| Field | Rule | Error |
|---|---|---|
| Group or category name | 1–50 characters after display normalization | `invalid_name` (422) |
| Product name | 1–100 characters after display normalization | `invalid_name` (422) |
| Category `parent_id` | Empty, or the id of a group | `invalid_parent` (422) |
| Group `parent_id` | Always empty | `invalid_parent` (422) |
| Product `category_id` | The id of an existing category, not a group | `unknown_category` / `not_a_category` (422) |

### API (local REST, JSON)

Items in `/api/categories` have `id`, `name`, `kind` (`group` | `category`), `parent_id`
(null or a group id), `product_count` (categories) and `category_count` (groups).

| Method and path | Purpose | Success | Errors |
|---|---|---|---|
| `GET /api/categories` | All groups and categories, in the sort order above | 200 | |
| `POST /api/categories` `{name, kind, parent_id?}` | Add a group or a category | 201 + item | 422 `invalid_name`, `invalid_parent`; 409 `duplicate_name` |
| `PATCH /api/categories/{id}` `{name?, parent_id?, kind?}` | Rename, move, or convert | 200 + item | 404; 422 `invalid_name`, `invalid_parent`; 409 `duplicate_name`, `category_has_products` (category → group), `group_not_empty` (group → category) |
| `DELETE /api/categories/{id}` | Delete | 204 | 404; 409 `category_in_use` with `product_count`, `group_not_empty` with `category_count` |
| `GET /api/products?q=&category_id=` | Products sorted by name, each with `id`, `name`, `category_id`, `category_name`, `group_name`; `q` matches a substring of the normalized name (the query is normalized the same way); `category_id` may be a category or a group; filters combine with AND | 200 | 422 unknown `category_id` |
| `POST /api/products` `{name, category_id}` | Add | 201 + product | 422 `invalid_name`, `unknown_category`, `not_a_category`; 409 `duplicate_name` |
| `PATCH /api/products/{id}` `{name?, category_id?}` | Rename and/or recategorize | 200 + product | 404; 422 as above; 409 `duplicate_name` |
| `DELETE /api/products/{id}` | Delete | 204 | 404 |

Error bodies have the form `{"error": "<code>", "message": "<Finnish text for the user>"}`
plus any extra fields listed above. `not_found` (404) is used for missing ids.

### Out of Scope
- Receipts and receipt lines (FR-12, FR-13, FR-15). **FR-36** (changing a product's category
  also moves its saved receipt lines; deleting a product leaves them as they are) is
  implemented and tested in the receipt specs, because there are no receipt lines yet. The
  product and category schema here must allow it: a receipt line will reference its product.
- **FR-43** (renaming a receipt line links it to a matching product, or stores the new name
  as a new product) is implemented in the receipt specs. It will reuse this spec's product
  lookup by normalized name and product creation, so those must be callable from other
  backend modules, not only through the API.
- **FR-44** (deposit refund lines have no category and are not counted in totals) is
  implemented in the receipt and totals specs. It needs no category or product of its own,
  so the default list in PRD 6.9 stays unchanged.
- OCR mix-up handling and fuzzy matching in normalization (rest of FR-14).
- Merging products and product aliases.
- Import and export of the product list.
- Archiving (FR-40 to FR-42).
- Pagination: the product list is expected to stay in the low thousands.
- Undo.

## Acceptance Criteria

### Default list

#### AC1: Default list is created on first start
**Given** an empty database
**When** the backend starts
**Then** `GET /api/categories` returns exactly:
group Ruoka with categories Maitotuotteet, Liha, Kala, Hedelmät, Vihannekset, Kananmunat,
Lihan korvaajat, Leivät, Kuivatuotteet, Pakasteet;
group Auto with categories Polttoaineet, Autotarvikkeet, Autohuolto;
and categories without a group Juomat, Alkoholi, Herkut, Hygienia, Kodin tarvikkeet,
Lemmikit, Ulkona syöminen, Muut.
That is 2 groups (category counts 10 and 3) and 21 categories, all with `product_count` 0.

#### AC2: Default list is not recreated
**Given** the default list was created and the user deleted all products, categories and groups
**When** the backend restarts
**Then** `GET /api/categories` returns an empty list

### Groups and categories

#### AC3: Add a category without a group
**Given** no item named "Harrastukset"
**When** the user adds a category named `"  Harrastukset  "` without a group
**Then** the response is 201 with name `"Harrastukset"`, kind `category`, `parent_id` null, `product_count` 0

#### AC4: Names are unique across groups and categories
**Given** the group "Ruoka" and the category "Juomat"
**When** the user adds a category named `"ruoka"`, or a group named `"JUOMAT"`
**Then** each response is 409 with error `duplicate_name`, and nothing is added

#### AC5: Invalid names are rejected
**Given** any state
**When** the user adds or renames a group or category to `""`, `"   "`, or a 51-character name
**Then** the response is 422 with error `invalid_name`, and nothing changes

#### AC6: Rename a category
**Given** the category "Juomat" used by 2 products
**When** the user renames it to "Virvoitusjuomat"
**Then** the response is 200, both products now show category name "Virvoitusjuomat", and `product_count` is still 2

#### AC7: Renaming to a case variant of the own name is allowed
**Given** a category "juomat"
**When** the user renames it to "Juomat"
**Then** the response is 200 and the name is "Juomat"

#### AC8: Create a group and add a new category to it
**Given** no items named "Koti" or "Sisustus"
**When** the user adds a group "Koti", then a category "Sisustus" with the group "Koti"
**Then** both responses are 201, and "Koti" is listed with `category_count` 1 and "Sisustus" under it

#### AC9: Move a category between groups and out of a group
**Given** the group "Koti" (no categories), the group "Ruoka" with 10 categories, and the category "Kodin tarvikkeet" without a group
**When** the user moves "Kodin tarvikkeet" into "Koti", then moves "Pakasteet" from "Ruoka" to no group
**Then** "Koti" has `category_count` 1, "Ruoka" has `category_count` 9, and "Pakasteet" has `parent_id` null; the products of both categories are unchanged

#### AC10: Groups cannot be nested
**Given** the groups "Ruoka" and "Auto" and the category "Juomat"
**When** the user sets the parent of "Auto" to "Ruoka", or the parent of a category to "Juomat", or creates a group with a parent
**Then** each response is 422 with error `invalid_parent`, and nothing changes

#### AC11: Convert an empty category into a group, and an empty group into a category
**Given** the category "Harrastukset" without a group and without products, and an empty group "Koti"
**When** the user converts "Harrastukset" into a group, and "Koti" into a category
**Then** both responses are 200 with kind `group` and kind `category` respectively

#### AC12: Conversion is refused when it would break the hierarchy
**Given** the category "Juomat" with 2 products, the category "Liha" in group "Ruoka", and the group "Auto" with 3 categories
**When** the user converts "Juomat" into a group, "Liha" into a group, or "Auto" into a category
**Then** the responses are 409 `category_has_products`, 422 `invalid_parent` (a group cannot have a parent), and 409 `group_not_empty` with `category_count` 3; nothing changes

#### AC13: A category in use cannot be deleted
**Given** the category "Juomat" used by 3 products
**When** the user deletes it
**Then** the response is 409 with error `category_in_use` and `product_count` 3, the category still exists, and the page shows "Kategoriaa käyttää 3 tuotetta" (or equivalent Finnish text with the number)

#### AC14: A group with categories cannot be deleted
**Given** the group "Auto" with 3 categories
**When** the user deletes it
**Then** the response is 409 with error `group_not_empty` and `category_count` 3, and the group still exists with its categories

#### AC15: An unused category and an empty group can be deleted
**Given** the category "Harrastukset" with no products and the group "Koti" with no categories
**When** the user deletes each and confirms
**Then** each response is 204 and neither is listed any more

### Products

#### AC16: Add a product
**Given** the category "Maitotuotteet" and no product "kevytmaito 1l"
**When** the user adds product `"  Kevytmaito   1L "` in "Maitotuotteet"
**Then** the response is 201 with name `"Kevytmaito 1L"`, category "Maitotuotteet" and group "Ruoka", and the category's `product_count` increases by 1

#### AC17: Duplicate product names are rejected after normalization
**Given** a product "Kevytmaito 1L"
**When** the user adds product `"KEVYTMAITO  1l"`
**Then** the response is 409 with error `duplicate_name`, and there is still one such product

#### AC18: Invalid product input is rejected
**Given** any state
**When** the user adds a product with an empty or 101-character name, or with a category id that does not exist
**Then** the response is 422 with error `invalid_name` or `unknown_category` respectively, and nothing changes

#### AC19: A product cannot belong to a group
**Given** the group "Ruoka" and a product "Ruisleipä" in "Leivät"
**When** the user adds a product with `category_id` of "Ruoka", or changes "Ruisleipä" to "Ruoka"
**Then** each response is 422 with error `not_a_category`, and nothing changes

#### AC20: Change a product's category
**Given** product "Kevytmaito 1L" in "Maitotuotteet" (count 1) and the category "Juomat" (count 0)
**When** the user selects "Juomat" in the product's category dropdown
**Then** the response is 200, the product shows "Juomat" with no group, and the counts become "Maitotuotteet" 0 and "Juomat" 1

#### AC21: Rename a product
**Given** products "Kevytmaito 1L" and "Rasvaton maito 1L"
**When** the user renames "Kevytmaito 1L" to "Kevytmaito 1,5L"
**Then** the response is 200 with the new name; renaming it instead to "rasvaton maito 1l" returns 409 `duplicate_name` and leaves the name unchanged

#### AC22: Delete a product
**Given** product "Kevytmaito 1L" in "Maitotuotteet" (count 1)
**When** the user deletes it and confirms
**Then** the response is 204, the product is no longer listed, and the count becomes 0

#### AC23: Search products
**Given** products "Kevytmaito 1L", "Rasvaton maito 1L" and "Ruisleipä"
**When** the user types `"MAITO"` in the search box
**Then** exactly "Kevytmaito 1L" and "Rasvaton maito 1L" are shown, sorted by name

#### AC24: Filter products by category or group
**Given** "Kevytmaito 1L" in "Maitotuotteet", "Ruisleipä" in "Leivät" and "Moottoriöljy" in "Autotarvikkeet"
**When** the user filters by "Leivät"; then by the group "Ruoka"; then by "Ruoka" and types `"öljy"`
**Then** first only "Ruisleipä" is shown; then "Kevytmaito 1L" and "Ruisleipä"; then no products and an empty-state message

### Persistence, errors and UI

#### AC25: Data survives a restart
**Given** a group, a category and a product were added
**When** the backend is stopped and started again with the same settings
**Then** all three are listed unchanged

#### AC26: Missing items return 404
**Given** no item with id 9999
**When** the user renames or deletes category, group or product id 9999
**Then** the response is 404 with error `not_found`

#### AC27: Backend errors are shown in the UI
**Given** the Tuotteet page is open
**When** an action returns 409, 422 or 404, or the backend cannot be reached
**Then** the page shows the Finnish `message` (or "Taustapalveluun ei saada yhteyttä") next to the action, and the lists stay as they were

#### AC28: Deletion needs confirmation
**Given** the Tuotteet page is open
**When** the user clicks delete on a product, category or group and then cancels
**Then** no request is sent and nothing changes

#### AC29: Category dropdown shows groups as headings only
**Given** the default list
**When** the user opens a product's category dropdown
**Then** the options are the 21 categories; "Ruoka" and "Auto" appear only as non-selectable headings above their categories; categories without a group follow after them

#### AC30: The page is in Finnish
**Given** the Tuotteet page is open
**When** it is rendered
**Then** the page heading is "Tuotteet", the category panel heading is "Kategoriat", and the buttons and fields use Finnish labels ("Lisää", "Hae", "Poista", "Tallenna", "Peruuta"); no English text is visible

## Files to Modify

This feature builds on the [foundation spec](foundation.md), which provides the containers,
settings, database and migrations, error format, API client and app shell. Exact paths are
fixed in the Plan phase.

| File | Change |
|---|---|
| `backend/app/migrations/` | New migration: tables for categories (kind, parent) and products |
| `backend/app/catalog/` | New: normalization, hierarchy rules, category and product services, API routes, default list and startup seeding (PC2) |
| `backend/app/main.py` | Update: register the catalog routes and seeding |
| `backend/tests/` | New: unit and integration tests for the catalog |
| `frontend/src/api/catalog.ts` | New: API client for categories and products |
| `frontend/src/pages/ProductsPage.tsx` | New: Tuotteet page (PC9) |
| `frontend/src/App.tsx` | Update: add `Tuotteet` to the navigation |
| `frontend/src/i18n/fi.ts` | Update: texts of the Tuotteet page |
| `frontend/src/**/*.test.tsx`, `frontend/e2e/` | New: component and E2E tests |
| `docs/datamodel.md` | Update: category (kind, parent) and product entities |
| `docs/api-reference.md` | Update: the endpoints above |
| `docs/subsystems/storage/README.md`, `docs/subsystems/ui/README.md` | Update |
| `docs/subsystems/categorization/README.md` | New |
| `docs/glossary.md` | New: group, category, product, normalized name |
| `docs/content-plan.md` | Update statuses |
| `specs/README.md` | Update status |

## Risk
- **What could break:** nothing existing (greenfield). Later specs depend on the category and
  product schema; a schema change after receipts exist needs a migration. The schema must
  let receipt lines reference products (FR-36).
- **Rollback:** revert the commit and remove the database volume (see `docs/development.md`).
- **Dependencies:** the foundation spec (Docker); runs with `RRMC_ENGINES=fake`, so no
  Tesseract or Ollama is needed for this feature.
- **Privacy:** product names describe purchases. They stay in the local database and are not
  logged.

## Testing Strategy (MANDATORY)

### Unit tests (backend, pytest)
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC3, AC16 | `normalize_display` | trims and collapses | `"  Kevytmaito   1L "` | normalize | `"Kevytmaito 1L"` | none |
| AC17 | `normalize_key` | case-folds | `"KEVYTMAITO  1l"` | normalize | `"kevytmaito 1l"` | none |
| AC17 | `normalize_key` | Nordic letters kept | `"RUISLEIPÄ"` | normalize | `"ruisleipä"` | none |
| AC17 | `normalize_key` | NFC | decomposed `"a"+"̈"` | normalize | `"ä"` (one code point) | none |
| AC23 | `finnish_sort_key` | å, ä, ö after z | "Öljy", "Ananas", "Zucchini", "Äyriäiset" | sort | Ananas, Zucchini, Äyriäiset, Öljy | none |
| AC5 | `validate_category_name` | empty / spaces | `""`, `"   "` | validate | `invalid_name` | none |
| AC5 | `validate_category_name` | boundary | 50 and 51 characters | validate | 50 ok, 51 `invalid_name` | none |
| AC18 | `validate_product_name` | boundary | 100 and 101 characters | validate | 100 ok, 101 `invalid_name` | none |
| AC1 | `DEFAULT_CATEGORIES` | content | constant | read | 2 groups, 21 categories, structure as in AC1 | none |
| AC1, AC2 | `seed_defaults` | first start | empty DB, not seeded | seed | default list created, seeded flag set | temp SQLite |
| AC2 | `seed_defaults` | already seeded | seeded flag set, no items | seed | nothing created | temp SQLite |
| AC4, AC7 | `CategoryService.rename` | own case variant vs other duplicate | "juomat", group "Ruoka" | rename "juomat"→"Juomat"; "juomat"→"ruoka" | ok; `duplicate_name` | temp SQLite |
| AC10 | `CategoryService.set_parent` | nesting refused | groups and categories | parent = group for group; parent = category | `invalid_parent` | temp SQLite |
| AC11, AC12 | `CategoryService.convert` | allowed and refused | empty category, used category, child category, non-empty group | convert | ok / `category_has_products` / `invalid_parent` / `group_not_empty` | temp SQLite |
| AC13, AC14, AC15 | `CategoryService.delete` | in use / not empty / empty | counts 3 / 3 categories / 0 | delete | `category_in_use` / `group_not_empty` / deleted | temp SQLite |
| AC19 | `ProductService.create`, `update` | group as category | group id | create; update | `not_a_category` | temp SQLite |
| AC23, AC24 | `ProductService.list` | search + category + group filter | products in three categories, two groups | `q`; category; group; group + `q` | as in AC23, AC24 | temp SQLite |

### Integration tests (FastAPI TestClient, temporary SQLite file)
| AC | Scenario | Request | Expected output | Status |
|---|---|---|---|---|
| AC1 | defaults on first start | `GET /api/categories` | structure of AC1, counts 0 | 200 |
| AC2 | not reseeded | delete all, recreate app, `GET` | empty list | 200 |
| AC3 | add category | `POST /api/categories {"name":"  Harrastukset  ","kind":"category"}` | name "Harrastukset" | 201 |
| AC4 | duplicate across kinds | `POST {"name":"ruoka","kind":"category"}` | `duplicate_name` | 409 |
| AC5 | invalid name | `POST` with `"   "` | `invalid_name` | 422 |
| AC6 | rename used category | `PATCH /api/categories/{id} {"name":...}` | products show new name | 200 |
| AC8 | new group + category | `POST` group, `POST` category with `parent_id` | counts and parent | 201 |
| AC9 | move category | `PATCH {"parent_id":...}` and `{"parent_id":null}` | counts updated | 200 |
| AC10 | nesting | `PATCH` group with `parent_id`; `POST` group with `parent_id` | `invalid_parent` | 422 |
| AC11 | convert empty | `PATCH {"kind":"group"}`, `{"kind":"category"}` | new kinds | 200 |
| AC12 | convert refused | `PATCH {"kind":...}` | `category_has_products` / `invalid_parent` / `group_not_empty` | 409 / 422 / 409 |
| AC13 | delete used category | `DELETE /api/categories/{id}` | `category_in_use`, `product_count` 3 | 409 |
| AC14 | delete non-empty group | `DELETE /api/categories/{id}` | `group_not_empty`, `category_count` 3 | 409 |
| AC15 | delete empty | `DELETE` category and group | empty body | 204 |
| AC16 | add product | `POST /api/products` | display name, category, group, count +1 | 201 |
| AC17 | duplicate product | `POST {"name":"KEVYTMAITO  1l",...}` | `duplicate_name` | 409 |
| AC18 | unknown category | `POST {"category_id":9999,...}` | `unknown_category` | 422 |
| AC19 | group as category | `POST` / `PATCH` with group id | `not_a_category` | 422 |
| AC20 | recategorize | `PATCH /api/products/{id} {"category_id":...}` | new category; counts updated | 200 |
| AC21 | rename to duplicate | `PATCH {"name":"rasvaton maito 1l"}` | `duplicate_name`, unchanged | 409 |
| AC22 | delete product | `DELETE /api/products/{id}` | count −1 | 204 |
| AC23 | search | `GET /api/products?q=MAITO` | two products, sorted | 200 |
| AC24 | filters | `GET ?category_id=<Leivät>`; `?category_id=<Ruoka>`; `+&q=öljy` | as in AC24 | 200 |
| AC25 | restart | add, recreate app with same DB file, `GET` | data unchanged | 200 |
| AC26 | missing id | `PATCH`/`DELETE` id 9999 on both resources | `not_found` | 404 |

### Component tests (Vitest + React Testing Library, API mocked with MSW)
| AC | Component | Case | Given | When | Then |
|---|---|---|---|---|---|
| AC1, AC9 | CategoryPanel | tree | default list | render; move "Pakasteet" out of "Ruoka" | groups with their categories, then ungrouped; after move "Pakasteet" is ungrouped |
| AC8 | CategoryPanel | new group | default list | add group "Koti", then category "Sisustus" in it | both shown, "Sisustus" under "Koti" |
| AC12, AC27 | CategoryPanel | conversion refused | PATCH returns 409 `category_has_products` | convert "Juomat" to group | Finnish message next to "Juomat"; unchanged |
| AC13, AC27 | CategoryPanel | category in use | DELETE returns 409 with count 3 | delete and confirm | message with the number 3 next to the category; still listed |
| AC14 | CategoryPanel | group not empty | DELETE returns 409 with count 3 | delete "Auto" and confirm | message next to the group; still listed |
| AC20 | ProductsPage | recategorize | one product | choose another category in the row's dropdown | PATCH sent; row and counts updated |
| AC23 | ProductsPage | search | three products | type "MAITO" | list request with `q`; two rows shown |
| AC24 | ProductsPage | group filter and empty state | filter returns [] | filter by "Ruoka", type "öljy" | empty-state message shown |
| AC17, AC27 | ProductsPage | duplicate product | POST returns 409 | add product | message next to the add form; list unchanged |
| AC27 | ProductsPage | backend down | network error | load page | "Taustapalveluun ei saada yhteyttä" |
| AC28 | ProductsPage | cancel delete | one product | click delete, then cancel | no DELETE request; row still shown |
| AC29 | CategorySelect | grouped options | default list | open dropdown | 21 selectable options; "Ruoka" and "Auto" are non-selectable headings |
| AC30 | ProductsPage | Finnish texts | default list | render | headings "Tuotteet" and "Kategoriat"; labels "Lisää", "Hae", "Poista", "Tallenna", "Peruuta" |

### E2E tests (Playwright, real backend, temporary database)
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC8, AC16, AC20, AC22, AC15 | manage catalog | 1. open Tuotteet 2. add group "Testiryhmä" and category "Testikategoria" in it 3. add product "Testituote" in it 4. move the product to "Juomat" 5. delete the product 6. delete "Testikategoria", then "Testiryhmä" | each step visible in the UI; final state has none of the test items |
| AC13, AC14 | protected delete | 1. add a product in "Juomat" 2. try to delete "Juomat" 3. try to delete "Auto" | Finnish messages shown; both remain |

### Coverage target
- Backend: 90 % lines for this feature; normalization, validation, hierarchy rules and
  delete protection: every branch.
- Frontend: 80 % lines for the Tuotteet page, category panel, category select and API client.

### Test data
- Synthetic product, group and category names only (as in the ACs).
- Each backend test uses its own temporary SQLite file.
- MSW handlers return fixed JSON for categories and products.

## Related Documentation (MANDATORY)
- PRD: `specs/PRD.md` sections 6.3, 6.7 (FR-32), 6.8, 6.9, 7.2, 7.4 (NFR-15), 7.5
- Spec: [Project foundation](foundation.md)
- Tier 1: `docs/datamodel.md`, `docs/api-reference.md`, `docs/development.md` (written in the
  foundation feature)
- Tier 2: storage and ui subsystem READMEs (foundation), categorization README (this feature)
- Development rules: `AGENTS.md`; workflows: `.agents/skills/spec/SKILL.md`,
  `.agents/skills/tdd/SKILL.md`

## Open Questions
None. The project setup is in the [foundation spec](foundation.md) (resolved 2026-10-23).
