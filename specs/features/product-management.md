# Feature: Product management

## Overview
- **Status:** Done
- **Created:** 2026-10-20
- **Updated:** 2026-10-20: groups, default list from PRD 6.9, Finnish UI, FR-36 rule;
  2026-10-21: FR-43 and FR-44 noted as out of scope;
  2026-10-23: project setup moved to the foundation spec;
  2026-10-27: aligned with the implemented foundation (paths, error format, API client,
  navigation), added AC31–AC34, ready for review; approved by the user; Plan added and approved; Tasks added;
  2026-10-27: implemented and audited (PASS), see Audit
- **Depends on:** [Project foundation](foundation.md)
- **Implements:** PRD FR-11, FR-33, FR-34, FR-35, FR-37, FR-38, FR-39, the default list in
  PRD 6.9, NFR-15 for this page, and the basic part of FR-14 (name normalization without OCR
  mix-ups). FR-36 is recorded as a rule; it is implemented with receipt lines (see Out of Scope).
- **Affected subsystems:** [storage](../../docs/subsystems/storage/README.md),
  categorization (`docs/subsystems/categorization/README.md`, created by this feature),
  [ui](../../docs/subsystems/ui/README.md)

## Problem Statement
The app must remember which category each product belongs to, so that a correction is made
once and reused on every later receipt (PRD G3). That memory is the product list. Before
receipts can be imported and categorized, the categories and the product list must exist,
and the user must be able to see and fix them directly: add a product ahead of time, move a
product to another category, remove a wrong entry, and organize categories into groups such
as Ruoka and Auto.

## Current Behavior
None (new). The [foundation](foundation.md) is in place and this feature builds on it:

- SQLite with numbered SQL migrations; the schema version is 0 and there are no domain
  tables ([datamodel.md](../../docs/datamodel.md#migrations),
  [storage](../../docs/subsystems/storage/README.md)).
- The API error format `{"error", "message"}` with `not_found` (404), `invalid_request`
  (422) and `internal_error` (500); feature codes are raised as `AppError`
  ([api-reference.md](../../docs/api-reference.md#error-format)).
- The UI app shell with an empty navigation, a status line and a shared API client that
  only has `apiGet` ([ui](../../docs/subsystems/ui/README.md)).

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
- **PC9 Products page (Finnish UI).** The navigation of the app shell gets its first item,
  "Tuotteet", which opens the Tuotteet page. As the only page so far, it is also shown
  when the app opens. The page has:
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
| Filter `category_id` | The id of an existing category or group | `unknown_category` (422) |
| Body shape | Required fields present, correct JSON types, `kind` is `group` or `category` | `invalid_request` (422, from the foundation) |

Name rules are checked after display normalization, so they give `invalid_name`, not
`invalid_request`. All Finnish messages of these codes live with the other backend texts
(see the foundation's [error format](../../docs/api-reference.md#error-format)).

### API (local REST, JSON)

Items in `/api/categories` have `id`, `name`, `kind` (`group` | `category`), `parent_id`
(null or a group id), `product_count` (categories) and `category_count` (groups).

| Method and path | Purpose | Success | Errors |
|---|---|---|---|
| `GET /api/categories` | All groups and categories, in the sort order above | 200 | |
| `POST /api/categories` `{name, kind, parent_id?}` | Add a group or a category | 201 + item | 422 `invalid_name`, `invalid_parent`; 409 `duplicate_name` |
| `PATCH /api/categories/{id}` `{name?, parent_id?, kind?}` | Rename, move, or convert | 200 + item | 404; 422 `invalid_name`, `invalid_parent`; 409 `duplicate_name`, `category_has_products` (category → group), `group_not_empty` (group → category) |
| `DELETE /api/categories/{id}` | Delete | 204 | 404; 409 `category_in_use` with `product_count`, `group_not_empty` with `category_count` |
| `GET /api/products?q=&category_id=` | Products sorted by name, each with `id`, `name`, `category_id`, `category_name`, `group_name` (null without a group); `q` matches a substring of the normalized name (the query is normalized the same way; empty `q` matches all); `category_id` may be a category or a group; filters combine with AND | 200 | 422 `unknown_category` |
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
**Then** each response is 422 with error `invalid_parent`, and nothing changes; the same holds when a category's parent is set to id 9999, which does not exist

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

#### AC31: Navigation opens the Tuotteet page
**Given** the app is opened at its start address
**When** it is rendered
**Then** the navigation "Päävalikko" contains one link "Tuotteet", marked as the current page, and the Tuotteet page is shown below the header with the status line still visible

#### AC32: Malformed requests are rejected
**Given** any state
**When** a client sends `POST /api/categories` without `name`, with `kind` `"folder"`, or with `name` 123; or `POST /api/products` without `category_id`
**Then** each response is 422 with error `invalid_request` and message "Pyyntö on virheellinen.", and nothing changes

#### AC33: Filtering by an unknown category is rejected
**Given** no item with id 9999
**When** a client requests `GET /api/products?category_id=9999`
**Then** the response is 422 with error `unknown_category`

#### AC34: Empty states
**Given** a database where all products were deleted
**When** the Tuotteet page is opened without search or filter
**Then** the product table shows a Finnish empty-state message instead of rows, and the add form is still available; when there are also no categories, the add form says that a category must be added first and sends no request

## Files to Modify

This feature builds on the [foundation spec](foundation.md), which provides the containers,
settings, database and migrations, error format, API client and app shell. Paths follow
[architecture.md](../../docs/architecture.md#folder-structure): the catalog belongs to the
categorization subsystem, and only storage runs SQL. File names inside the packages are
fixed in the Plan phase.

| File | Change |
|---|---|
| `backend/app/storage/migrations/0001_catalog.sql` | New migration: tables for groups and categories (kind, parent) and products |
| `backend/app/storage/` | New: repository for categories and products (all catalog SQL) |
| `backend/app/categorization/` | New package: normalization, validation, hierarchy rules, category and product services, default list and seeding (PC2), API routes and schemas |
| `backend/app/texts.py` | Update: Finnish messages of the new error codes |
| `backend/app/main.py` | Update: register the catalog routes; seed the default list at start |
| `backend/tests/unit/categorization/`, `backend/tests/unit/storage/` | New: unit tests |
| `backend/tests/integration/` | New: API tests for categories and products |
| `frontend/src/api/client.ts` | Update: `apiPost`, `apiPatch`, `apiDelete` with the same result type as `apiGet` |
| `frontend/src/api/catalog.ts` | New: typed client for categories and products |
| `frontend/src/components/ProductsPage.tsx`, `CategoryPanel.tsx`, `CategorySelect.tsx` | New: Tuotteet page (PC9) |
| `frontend/src/App.tsx` | Update: `Tuotteet` in the navigation, page in `<main>` |
| `frontend/src/i18n/fi.ts` | Update: texts of the Tuotteet page |
| `frontend/src/**/*.test.ts(x)` | New and updated component and client tests (including `App.test.tsx`) |
| `frontend/e2e/products.spec.ts` | New: E2E journeys |
| `docs/datamodel.md` | Update: category (kind, parent) and product entities, migration 0001 |
| `docs/api-reference.md` | Update: the endpoints and error codes above |
| `docs/architecture.md` | Update: categorization moves from target design to implemented (catalog part) |
| `docs/subsystems/storage/README.md`, `docs/subsystems/ui/README.md` | Update |
| `docs/subsystems/categorization/README.md` | New |
| `docs/glossary.md` | New: group, category, product, display name, normalized name |
| `docs/content-plan.md` | Update statuses |
| `specs/README.md` | Update status |

## Risk
- **What could break:** the app shell and its tests (`App.tsx` gets a navigation item and a
  page; the status line must keep working), and the shared API client (new methods next to
  `apiGet`, whose behavior must not change). Later specs depend on the category and product
  schema; a schema change after receipts exist needs a new migration. The schema must let
  receipt lines reference products (FR-36).
- **Rollback:** revert the commit. Migration 0001 stays applied in the database; the
  reverted code does not read its tables, so the app still starts. Removing the tables by
  deleting the database volume deletes all data and is done only by the user, never by an
  agent.
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
| AC5, AC18 | `validate_*_name` | length after normalization | 50 / 100 characters plus surrounding spaces | validate | ok (the display name is measured) | none |
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
| AC10 | unknown parent | `PATCH {"parent_id":9999}` on a category | `invalid_parent` | 422 |
| AC26 | missing id | `PATCH`/`DELETE` id 9999 on both resources | `not_found` | 404 |
| AC32 | malformed body | `POST /api/categories` without `name`; `kind` `"folder"`; `name` 123; `POST /api/products` without `category_id` | `invalid_request` | 422 |
| AC33 | unknown filter | `GET /api/products?category_id=9999` | `unknown_category` | 422 |

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
| AC31 | App | navigation | health and catalog mocked | render | link "Tuotteet" in "Päävalikko" with `aria-current="page"`; Tuotteet page and status line shown |
| AC34 | ProductsPage | no products | products `[]` | render | empty-state message; add form shown |
| AC34 | ProductsPage | no categories | categories `[]`, products `[]` | try to add a product | message that a category is needed; no POST sent |
| AC27 | API client | write methods | POST/PATCH/DELETE answer 409 in the error format; network error; 204 | call | `{ok:false}` with code and message; `network_error`; `{ok:true}` for 204 without a body |

### E2E tests (Playwright, real backend, temporary database)
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC8, AC16, AC20, AC22, AC15 | manage catalog | 1. open Tuotteet 2. add group "Testiryhmä" and category "Testikategoria" in it 3. add product "Testituote" in it 4. move the product to "Juomat" 5. delete the product 6. delete "Testikategoria", then "Testiryhmä" | each step visible in the UI; final state has none of the test items |
| AC13, AC14 | protected delete | 1. add a product in "Juomat" 2. try to delete "Juomat" 3. try to delete "Auto" | Finnish messages shown; both remain |
| AC23, AC31 | open and search | 1. open the app 2. check that Tuotteet is shown 3. add two products 4. search by part of one name | Tuotteet page shown at start; only the matching product listed |

The E2E backend starts with an empty temporary database on every run, so the default list
exists at the start of a run. The journeys share that database: each uses its own item
names and does not depend on the order of the others.

### Coverage target
- Backend: 90 % lines for this feature; normalization, validation, hierarchy rules and
  delete protection: every branch.
- Frontend: 80 % lines for the Tuotteet page, category panel, category select and API client.

### Test data
- Synthetic product, group and category names only (as in the ACs).
- Each backend test uses its own temporary SQLite file.
- MSW handlers return fixed JSON for categories and products.

## Related Documentation (MANDATORY)
- PRD: [specs/PRD.md](../PRD.md) sections 6.3, 6.4 (FR-17), 6.8, 6.9, 7.2, 7.4 (NFR-15), 7.5
- Spec: [Project foundation](foundation.md)
- Tier 1: [architecture.md](../../docs/architecture.md), [datamodel.md](../../docs/datamodel.md),
  [api-reference.md](../../docs/api-reference.md), [development.md](../../docs/development.md)
- Tier 2: [storage](../../docs/subsystems/storage/README.md),
  [ui](../../docs/subsystems/ui/README.md); categorization README (created by this feature)
- ADRs: [0001 technology stack](../../docs/adr/0001-tech-stack.md),
  [0002 Docker](../../docs/adr/0002-docker.md)
- Development rules: `AGENTS.md`; workflows: `.agents/skills/spec/SKILL.md`,
  `.agents/skills/tdd/SKILL.md`

## Open Questions
None. The project setup is in the [foundation spec](foundation.md) (resolved 2026-10-23).

## Plan

Spec approved: 2026-10-27. The plan follows [architecture.md](../../docs/architecture.md)
and the [code standards](../../docs/development.md#code-standards). No new dependencies are
needed on either side.

### Components

| Part | File | Contents | ACs |
|---|---|---|---|
| P1 Schema | `backend/app/storage/migrations/0001_catalog.sql` | Tables `categories`, `products`, `app_state` (see [Data model](#data-model)) | AC1, AC25 |
| P2 Transactions | `backend/app/storage/db.py` | `transaction(connection)` context manager: `BEGIN IMMEDIATE`, `COMMIT`, `ROLLBACK` on any exception | all writes |
| P3 Repository | `backend/app/storage/catalog_repository.py` | `CatalogRepository(connection)`: all catalog SQL. Rows as frozen dataclasses `CategoryRow`, `ProductRow`. Counts by subquery. Search with `instr(name_key, ?)`, so `%` and `_` in a query need no escaping. Seed marker get/set | AC1–AC26, AC33 |
| P4 Names | `backend/app/categorization/names.py` | `normalize_display`, `normalize_key`, `finnish_sort_key`, `validate_category_name`, `validate_product_name` (PC6, Sorting, Validation) | AC3–AC5, AC7, AC16–AC18, AC21, AC23 |
| P5 Default list | `backend/app/categorization/defaults.py` | `DEFAULT_CATEGORIES` (PRD 6.9), `seed_defaults(repository)` | AC1, AC2 |
| P6 Errors | `backend/app/categorization/errors.py`, `backend/app/errors.py`, `backend/app/texts.py` | One `AppError` subclass per code; `AppError` gets optional `extra` fields merged into the body; Finnish messages, with the count in `category_in_use` and `group_not_empty` | AC4, AC5, AC10, AC12–AC14, AC17–AC19, AC21, AC26, AC33 |
| P7 Services | `backend/app/categorization/service.py` | `CategoryService`, `ProductService` (rules below). Plain classes taking a repository, so other subsystems (FR-36, FR-43) can call them | AC3–AC24, AC26, AC33 |
| P8 API | `backend/app/categorization/schemas.py`, `routes.py`, `backend/app/main.py` | Pydantic input and output models; `create_catalog_router(settings)`; one connection per request through `Depends`; seeding in the lifespan after migrations | AC1–AC26, AC32, AC33 |
| P9 API client | `frontend/src/api/client.ts`, `frontend/src/api/catalog.ts` | One private `request(method, path, body?)` behind `apiGet` (unchanged behavior), `apiPost`, `apiPatch`, `apiDelete`; 204 gives `{ok: true, data: undefined}`. Typed catalog functions and types `CatalogItem`, `Product` | AC27 |
| P10 Components | `frontend/src/components/ProductsPage.tsx`, `CategoryPanel.tsx`, `CategorySelect.tsx`, `ConfirmDelete.tsx` | Tuotteet page (PC9); see [UI](#ui) | AC6–AC30, AC34 |
| P11 Shell | `frontend/src/App.tsx`, `frontend/src/i18n/fi.ts` | Link "Tuotteet" in the navigation; `ProductsPage` in `<main>`; all page texts under `fi.products` | AC30, AC31 |

### Data model

```sql
CREATE TABLE categories (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,              -- display name
    name_key  TEXT NOT NULL UNIQUE,       -- normalized name; one namespace for both kinds
    kind      TEXT NOT NULL CHECK (kind IN ('group', 'category')),
    parent_id INTEGER REFERENCES categories (id) ON DELETE RESTRICT,
    CHECK (kind = 'category' OR parent_id IS NULL)
);
CREATE INDEX categories_parent_id ON categories (parent_id);

CREATE TABLE products (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    name_key    TEXT NOT NULL UNIQUE,
    category_id INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT
);
CREATE INDEX products_category_id ON products (category_id);

-- One-time facts about the database; key 'catalog_seeded_at' marks that PC2 ran.
CREATE TABLE app_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

- `UNIQUE` and `ON DELETE RESTRICT` are a safety net; the services check first, so the user
  gets the right error code and count. SQLite `CHECK` cannot look at another row, so "parent
  is a group" and "a product's category is not a group" are enforced only in the services.
- Product ids are stable integers, so receipt lines can reference `products.id` later
  (FR-36). No receipt columns are added now.
- Why a seed marker and not an empty-table check: after the user deletes everything, an empty
  table must not bring the defaults back (AC2). Why not insert the defaults in the migration:
  the list then lives in SQL and Python tests could not use `DEFAULT_CATEGORIES` as the one
  source; with the marker, `seed_defaults` is the single place.

### Data flow

1. Start: `prestart` migrates (as today). The lifespan migrates, then opens a connection and
   calls `seed_defaults`: if `app_state` has no `catalog_seeded_at`, it inserts the default
   list and the marker in one transaction. Otherwise it does nothing.
2. Request: the route parses the body with Pydantic (shape errors become `invalid_request`
   through the foundation handler), gets a service bound to a per-request connection, and
   returns the result. The connection is closed after the response.
3. Service write: inside `transaction()`, normalize and validate, check uniqueness and the
   hierarchy against the current rows, write, read back the item with its counts.
4. List: the repository returns unordered rows with counts; the service sorts them in
   Python with `finnish_sort_key`, because SQLite has no Finnish collation.

### Service rules

| Operation | Checks, in this order | Error |
|---|---|---|
| Create category or group | name valid → name key free → group has no parent; category parent exists and is a group | `invalid_name`, `duplicate_name`, `invalid_parent` |
| Update category or group | item exists → compute the **resulting** name, kind and parent, then validate that state: name valid and free (own key allowed, AC7); a category with products cannot become a group; a group with categories cannot become a category; a group has no parent; a category's parent exists and is a group | `not_found`, `invalid_name`, `duplicate_name`, `category_has_products`, `group_not_empty`, `invalid_parent` |
| Delete category or group | item exists → category has no products; group has no categories | `not_found`, `category_in_use` + `product_count`, `group_not_empty` + `category_count` |
| Create product | name valid → category exists → it is a category → name key free | `invalid_name`, `unknown_category`, `not_a_category`, `duplicate_name` |
| Update product | product exists → same checks for the fields sent | `not_found`, as above |
| Delete product | product exists | `not_found` |
| List products | filter id, when given, exists | `unknown_category` |

Validating the resulting state means that converting "Liha" (in "Ruoka") into a group fails
with `invalid_parent` (AC12), while the same request with `"parent_id": null` succeeds.
PATCH bodies tell "field not sent" from `"parent_id": null` by Pydantic's
`model_fields_set`.

Finnish sort key: `normalize_key(name)` with `å`, `ä`, `ö` mapped to characters that sort
after `z` (AC23 unit row). A group filter matches the products of every category in that
group; a category filter matches that category only.

### API wiring

- `create_app` adds `create_catalog_router(settings)` next to the health router. The lifespan
  calls `seed_defaults` after `migrate_database`.
- Routes are plain `def` (SQLite blocks). Status codes: `POST` 201, `DELETE` 204 with no
  body, others 200.
- Output models: `CatalogItemOut` (`id`, `name`, `kind`, `parent_id`, `product_count` for
  categories, `category_count` for groups, the other one `null`), `ProductOut` (`id`, `name`,
  `category_id`, `category_name`, `group_name`).
- `AppError(code, message, status, extra=None)`: `extra` (e.g. `{"product_count": 3}`) is
  merged into the error body. Existing callers do not change.
- Product names are not logged; the foundation request log already leaves out bodies and
  query strings.

### UI

- **No router library.** There is one page; `App` renders the navigation link
  `<a href="/" aria-current="page">Tuotteet</a>` and the page in `<main>`. A router is added
  by the first spec with a second page.
- **ProductsPage** owns the state: categories, products, search text, filter. It loads both
  lists on mount and after every successful write (so counts are always the backend's), and
  reloads products when the search text or filter changes. Shows the empty states of AC24
  and AC34.
- **CategoryPanel** shows the tree built from `parent_id`, in the backend's order. Per item:
  rename, move (a select of the groups plus "Ei ryhmää"), convert, delete. Forms to add a
  group and a category.
- **CategorySelect** is a native `<select>`: one `<optgroup>` per group (headings cannot be
  chosen, AC29), then the ungrouped categories as plain options. Used in the product rows,
  the add form and the filter (the filter variant also offers the groups and "Kaikki").
- **ConfirmDelete** is a delete button that turns into "Poista" / "Peruuta" in place; no
  request until confirmed (AC28), no browser dialog.
- Errors: each action keeps its own error and shows the backend `message` beside it with
  `role="alert"`; lists stay unchanged (AC27).

### Change to an existing test

The foundation test `App.test.tsx` "AC25: shows no English text" compares the shell's whole
text with `"KuittisovellusKaikki palvelut toiminnassa"`. This spec adds a link and a page to
the shell (AC31), so that exact value changes. Foundation AC25 itself still holds (Finnish
heading and title, no English text). The test is updated **before** the shell is changed, as
part of the AC31 task: it then checks the shell texts with the Tuotteet page mocked, and still
fails if any English text appears. This is a test change required by the spec, not a fix of a
failing test.

Found in T13 (decided by the user, 2026-10-27): the foundation test
`test_startup_migrations.py` "AC8, AC9: startup migrates once" starts the app with throwaway
migrations only. Startup now also seeds the default list (PC2), which needs the real schema,
so the app cannot start on throwaway migrations alone. The test now copies the real
migrations into its folder and adds its two throwaway ones after them. It still proves
foundation AC8 and AC9: every migration is applied once, in order, and the version is the
newest. Production code does not change for this.

### Testing approach

- Unit tests for storage and services use a migrated temporary SQLite file
  (`tests/unit/categorization/conftest.py`, `tests/unit/storage/`).
- Integration tests open `TestClient` as a context manager, so the lifespan (migrations and
  seeding) runs. AC2 and AC25 create a second app on the same database file.
- Component tests mock `/api/categories` and `/api/products` with MSW; fixtures build the
  default list from one typed constant in the test folder.
- E2E: `frontend/e2e/products.spec.ts` against `backend-e2e` (fresh database per run).
- Coverage: `pytest --cov=app.categorization --cov=app.storage` and
  `npm run test:coverage`, against the targets in the Testing Strategy.

### Decisions

No ADR: the choices here (one table for groups and categories, seed marker, sorting in
Python, no router yet) are local to this feature and are recorded in the categorization
README and in [datamodel.md](../../docs/datamodel.md).

### Files to Modify (refined)

Adds to the table above: `backend/app/storage/db.py` (`transaction`), `backend/app/errors.py`
(`extra` fields), `backend/app/categorization/names.py`, `defaults.py`, `errors.py`,
`frontend/src/components/ConfirmDelete.tsx`, `frontend/src/App.test.tsx` (see
[Change to an existing test](#change-to-an-existing-test)),
`backend/tests/unit/conftest.py` (a migrated temporary database for the storage and
categorization unit tests; it replaces the planned `tests/unit/categorization/conftest.py`).

Added during implementation (2026-10-27):

- `backend/tests/integration/conftest.py` (`api` fixture that runs the startup),
  `backend/tests/integration/endpoints_for_tests.py` (an `AppError` with `extra`),
  `backend/tests/integration/test_startup_migrations.py` (see
  [Change to an existing test](#change-to-an-existing-test)).
- `frontend/src/test/catalog.ts`: the default list as test data and `fakeCatalog`, an
  in-memory catalog behind MSW.
- `backend/app/storage/db.py` again: `check_same_thread=False`, a bug found by the E2E run,
  fixed with the fix workflow; recorded in the new `docs/learnings.md`.

### AC coverage

| AC | Parts |
|---|---|
| AC1, AC2 | P1, P3, P5, P8 |
| AC3–AC15 | P3, P4, P6, P7, P8; UI: P10 |
| AC16–AC24 | P3, P4, P6, P7, P8; UI: P10 |
| AC25 | P1, P8 |
| AC26 | P6, P7 |
| AC27 | P9, P10 |
| AC28, AC29 | P10 |
| AC30, AC31 | P10, P11 |
| AC32 | P8 (foundation handler) |
| AC33 | P3, P6, P7 |
| AC34 | P10 |

## Tasks

Plan approved: 2026-10-27. Each task follows Red → Green → Refactor (`.agents/skills/tdd/SKILL.md`)
and ends with the tests, lint, format and type checks of the part it touched passing. Test
names start with the AC IDs they prove. Backend tasks come first, so the UI tasks build on a
working API.

### Backend: storage

- [x] **T1 Catalog schema** (AC1, AC25). `backend/app/storage/migrations/0001_catalog.sql`.
  Proof: `tests/unit/storage/test_catalog_schema.py`: a migrated database has the three
  tables and schema version 1; a duplicate `name_key` is refused; a group with a parent is
  refused by the `CHECK`; deleting a category that a product references is refused.
- [x] **T2 Transactions** (all writes). `backend/app/storage/db.py` `transaction()`.
  Proof: `tests/unit/storage/test_db.py`: a write inside the block is committed; an exception
  inside the block rolls the write back and is raised again.
- [x] **T3 Category repository** (AC1–AC15 storage part). `backend/app/storage/catalog_repository.py`:
  insert, get, get by key, list with `product_count` and `category_count`, update, delete,
  seed marker. Proof: `tests/unit/storage/test_catalog_repository.py` on a temporary file:
  each function, counts after adding products and child categories, marker absent then set.
- [x] **T4 Product repository** (AC16–AC24, AC33 storage part). Same file: insert, get, get
  by key, update, delete, list with category and group names, `q` by `instr`, category
  filter, group filter, both combined. Proof: same test file, including a query containing
  `%` and `_` that matches only literally.

### Backend: categorization

- [x] **T5 Names** (AC3, AC5, AC7, AC16–AC18, AC21, AC23). `backend/app/categorization/names.py`.
  Proof: `tests/unit/categorization/test_names.py`: every unit row of the Testing Strategy for
  `normalize_display`, `normalize_key`, `finnish_sort_key`, `validate_category_name`,
  `validate_product_name`, including the 50/51 and 100/101 boundaries and surrounding spaces.
- [x] **T6 Error extras and codes** (AC4, AC5, AC10, AC12–AC14, AC17–AC19, AC21, AC26, AC33).
  `backend/app/errors.py` (`extra`), `backend/app/categorization/errors.py`,
  `backend/app/texts.py`. Proof: `tests/integration/test_errors.py`: an `AppError` with
  `extra` returns those fields next to `error` and `message`; existing error tests stay green;
  `tests/unit/categorization/test_errors.py`: the count messages read correctly for 1 and 3
  ("1 tuote" / "3 tuotetta", "1 kategoria" / "3 kategoriaa").
- [x] **T7 Default list and seeding** (AC1, AC2). `backend/app/categorization/defaults.py`.
  Proof: `tests/unit/categorization/test_defaults.py`: `DEFAULT_CATEGORIES` has 2 groups
  (10 and 3 categories) and 21 categories with the names of AC1; `seed_defaults` on an empty
  database creates them and the marker; with the marker set and no items it creates nothing.
- [x] **T8 Create and rename groups and categories** (AC3–AC5, AC7, AC8).
  `backend/app/categorization/service.py` `CategoryService.create`, `update` (name).
  Proof: `tests/unit/categorization/test_category_service.py`: display name stored; duplicate
  across kinds refused; invalid names refused; own case variant allowed; category created in a
  group.
- [x] **T9 Move, nesting and conversion** (AC9–AC12). `CategoryService.update` (parent, kind)
  validating the resulting state. Proof: same file: move between groups and out of a group;
  every `invalid_parent` case of AC10 including parent 9999; conversions allowed and refused as
  in AC11 and AC12; "Liha" to a group with `parent_id` null succeeds.
- [x] **T10 Delete and list categories** (AC13–AC15, AC26). `CategoryService.delete`, `list`.
  Proof: same file: `category_in_use` with 3, `group_not_empty` with 3, empty ones deleted,
  missing id `not_found`; list order is groups each followed by their categories, then
  ungrouped, Finnish order inside each.
- [x] **T11 Product writes** (AC16–AC22, AC26). `ProductService.create`, `update`, `delete`.
  Proof: `tests/unit/categorization/test_product_service.py`: add with group name returned;
  duplicate after normalization; invalid name; `unknown_category`; `not_a_category` on create
  and update; recategorize; rename and rename to a duplicate; delete; missing id.
- [x] **T12 Product list** (AC23, AC24, AC33). `ProductService.list`. Proof: same file:
  `q="MAITO"` gives two sorted products; category filter; group filter; group plus `q`
  gives none; empty `q` gives all; unknown filter id gives `unknown_category`.

### Backend: API

- [x] **T13 Category API and seeding at start** (AC1–AC15, AC25, AC26, AC32).
  `backend/app/categorization/schemas.py`, `routes.py`, `backend/app/main.py`.
  Proof: `tests/integration/test_categories_api.py`: every category row of the integration
  table, with `TestClient` used as a context manager; AC2 and AC25 with a second app on the
  same database file; the AC32 bodies for categories.
- [x] **T14 Product API** (AC16–AC24, AC26, AC32, AC33). Same modules.
  Proof: `tests/integration/test_products_api.py`: every product row of the integration
  table, the AC32 body for products and the AC33 filter.

### Frontend

- [x] **T15 Write methods in the API client** (AC27). `frontend/src/api/client.ts`.
  Proof: `client.test.ts`: `apiPost`, `apiPatch`, `apiDelete` send the method and JSON body;
  409 in the error format gives `{ok: false}` with code and message; network error gives
  `network_error`; 204 gives `{ok: true}`; the existing `apiGet` tests stay green.
- [x] **T16 Catalog client** (AC27). `frontend/src/api/catalog.ts`. Proof: `catalog.test.ts`:
  each function calls the right method and path; `listProducts` builds `q` and `category_id`
  only when given.
- [x] **T17 CategorySelect** (AC29). `frontend/src/components/CategorySelect.tsx`.
  Proof: `CategorySelect.test.tsx`: with the default list, 21 selectable options, "Ruoka" and
  "Auto" as `optgroup` labels, ungrouped categories after them; the filter variant also offers
  the groups and "Kaikki".
- [x] **T18 ConfirmDelete** (AC28). `frontend/src/components/ConfirmDelete.tsx`.
  Proof: `ConfirmDelete.test.tsx`: first click shows "Poista" and "Peruuta"; cancel calls
  nothing; confirm calls the handler once.
- [x] **T19 CategoryPanel** (AC1, AC8, AC9, AC12–AC15, AC27). `frontend/src/components/CategoryPanel.tsx`.
  Proof: `CategoryPanel.test.tsx`: the CategoryPanel rows of the component table, plus delete
  of an empty category after confirmation.
- [x] **T20 ProductsPage** (AC17, AC20, AC22–AC24, AC27, AC28, AC30, AC34).
  `frontend/src/components/ProductsPage.tsx`, `frontend/src/i18n/fi.ts`.
  Proof: `ProductsPage.test.tsx`: the ProductsPage rows of the component table, including
  both AC34 rows.
- [x] **T21 Shell navigation** (AC30, AC31). First update `frontend/src/App.test.tsx` as
  described in [Change to an existing test](#change-to-an-existing-test) and add the AC31
  test; see both fail; then `frontend/src/App.tsx`. Proof: `App.test.tsx`: link "Tuotteet" in
  "Päävalikko" with `aria-current="page"`, Tuotteet page and status line shown, no English
  text; foundation AC25 checks still pass.
- [x] **T22 E2E journeys** (AC8, AC13–AC16, AC20, AC22, AC23, AC31).
  `frontend/e2e/products.spec.ts`. Proof: the three journeys of the E2E table pass with
  `docker compose --profile e2e run --rm e2e`, together with the existing `app.spec.ts`.

### Docs and final checks

- [x] **T23 Documentation** (all). Following `.agents/skills/document/SKILL.md`: update
  `docs/datamodel.md`, `docs/api-reference.md`, `docs/architecture.md`,
  `docs/subsystems/storage/README.md`, `docs/subsystems/ui/README.md`; create
  `docs/subsystems/categorization/README.md` and `docs/glossary.md`; update
  `docs/content-plan.md`. Proof: every endpoint, error code, table and term of this spec
  appears in exactly one doc and is linked from the others; links resolve.
- [x] **T24 Final verification** (all). Run every command in
  [development.md](../../docs/development.md#commands), and coverage
  (`docker compose run --rm backend pytest --cov=app.categorization --cov=app.storage`,
  `docker compose run --rm frontend npm run test:coverage`). Proof: all green; coverage meets
  the targets in the Testing Strategy; every AC has a test whose name carries its ID. Then hand
  over to `review-audit`.

## Audit

Audited 2026-10-27, verdict PASS after one fix cycle.

- Acceptance criteria: 34/34 met; every AC has a test that carries its ID.
- Tests: backend 212 passed, 100 % lines in `app.categorization` and `app.storage`;
  frontend 61 passed, 99 % lines; E2E 4 passed; container tests passed. Lint, format and
  type checks clean.
- Security: no findings. `npm audit` 0 vulnerabilities. `pip-audit` is not installed in the
  backend image and was not run.
- Fixed in the audit: an item could be its own parent (AC10, see
  [learnings](../../docs/learnings.md)); the page hid a failed category load and showed
  "Lisää ensin kategoria." while loading (AC27, AC34); a filter or add-form choice on a
  deleted or converted item stayed selected. Tests for AC5, AC9, AC10 and AC28 were made
  stricter.
- Later: an explicit `null` for `name`, `kind` or `category_id` in a PATCH body is treated as
  "not sent" (200, no change) instead of `invalid_request`.
