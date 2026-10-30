# Feature: Line categorization

## Overview
- **Status:** Done
- **Created:** 2026-10-30
- **Updated:** 2026-10-30: user answers: a receipt is categorized per line (a one-line
  receipt therefore gets one category); backend logic only, no UI and no new endpoints;
  categorization done in the most efficient way (see [Why a separate model call](#why-a-separate-model-call));
  receipts imported before this feature stay without categories; deposit refunds get no
  category. Proposals accepted by the user: a category used by lines cannot be deleted
  (PC8); OCR mix-ups (rest of FR-14) move to a later spec. Specify approved by the user;
  Plan added (one correction to PC9's implementation, listed at its start) and approved by
  the user; Tasks added; spec approved by the user; implementation started; AC21 value
  corrected during T13 from `Maitotuotteet` to `Autohuolto`: the rule (first category in
  list order) is unchanged, the value was miscounted (groups sort `Auto` before `Ruoka`).
  PC8 clarified during T17: `line_count` is left out of the error body when it is 0.
  Audited (PASS after one fix cycle), see [Audit](#audit).
- **Depends on:** [Product management](product-management.md), [Receipt reading](receipt-reading.md)
- **Implements:** PRD FR-12, FR-13 (backend), FR-15, FR-36 (moved
  here from product management, which deferred it to the receipt specs), FR-44 (the "no
  category" part); NFR-1, NFR-3, NFR-7, NFR-13 for categorization; PRD open question 6.
- **Affected subsystems:** [categorization](../../docs/subsystems/categorization/README.md),
  [import](../../docs/subsystems/import/README.md),
  [storage](../../docs/subsystems/storage/README.md),
  [receipt-reading](../../docs/subsystems/receipt-reading/README.md) (the model interface)

## Problem Statement
An import run reads each new receipt and stores its lines, but the lines have no category,
so nothing can be totalled per category (PRD section 5, step 4). The app already has a
catalog of groups, categories and products, which is the user's memory of which category
each product belongs to. This spec gives each line a category when the receipt is imported:
the remembered category of a known product first, otherwise a suggestion from the local
model. It also adds the backend rule that stores a user's correction as the product's
remembered category, so the review UI (next spec) only has to call it.

## Current Behavior
- An import run reads the image and stores the receipt with its lines in one transaction
  ([import](../../docs/subsystems/import/README.md#data-flow), @backend/app/receipt_import/run.py).
  Lines have position, name, amount and the deposit refund flag, and no category
  ([datamodel.md](../../docs/datamodel.md#receipt_lines)).
- The catalog (groups, categories, products, normalized names) and its services exist
  ([categorization](../../docs/subsystems/categorization/README.md)). Product names are
  matched by the normalized key: NFC, trimmed, collapsed spaces, case-folded. OCR mix-ups
  are not handled.
- `ReceiptModel.generate(prompt, schema)` sends one prompt to Ollama with structured output
  ([receipt-reading](../../docs/subsystems/receipt-reading/README.md#model-request)). Only
  reading uses it.
- Changing a product's category does not touch receipt lines (FR-36 is not implemented,
  [product management spec](product-management.md#out-of-scope)).

## Proposed Change

### Concepts

- A line's **category source** tells where its category came from (FR-15):
  `remembered` (the line's product), `model` (the model's suggestion) or `user` (the user
  chose it). A line without a category has no source.
- A line is **linked** to a product when its category comes from that product, or when the
  user chose its category. A model suggestion never links a line and never creates a
  product, so a wrong suggestion is not remembered.
- **Categorizable lines** are the lines that are not deposit refunds. Deposit refunds never
  get a category, a source or a product (FR-44).

### Parts

- **PC1 Categories on lines (FR-15).** Each line stores its category, its category source
  and its product link. A line without a category stores none of the three; a line with a
  category always has a source. Lines of receipts imported before this feature keep no
  category.
- **PC2 Remembered category first (FR-12).** At import, each categorizable line whose
  normalized name equals a product's normalized name gets that product's category, source
  `remembered`, and is linked to the product. The model is not asked about it.
- **PC3 Model suggestion (FR-12).** The other categorizable lines are sent to the model in
  **one call per receipt**, after reading and before the commit. The prompt lists every
  category, numbered, with its group as `Ryhmä > Kategoria` (an ungrouped category as its
  name alone); groups are never options. A name that occurs on several lines of the receipt
  (same normalized name) is asked once. The model answers one category number per name.
  Each line gets the suggested category with source `model`. No model call is made when no
  line needs one or when the catalog has no categories.
- **PC4 Suggestion failures do not fail the image.** If the model's answer is not valid
  JSON for the schema, has the wrong number of entries, or times out, or Ollama returns an
  error status, the lines that needed a suggestion are stored without category and the
  image is imported normally. A number that is not in the list leaves only its line(s)
  without category. If the model becomes unavailable, the run stops as in reading (FR-31):
  the image stays in the import folder and nothing is stored for it.
- **PC5 Consistent commit.** Remembered products are matched again inside the commit
  transaction, and each suggested category is checked to still exist there, so a product
  or category that the user changed during the run cannot fail the image. A line whose
  suggested category was deleted is stored without category.
- **PC6 User correction (FR-13).** A backend service sets a line's category chosen by the
  user. The line gets the category and source `user`, and the choice is stored as the
  product's category:
  - a linked line: its product's category changes;
  - an unlinked line whose normalized name matches a product: that product's category
    changes and the line is linked to it;
  - otherwise: a new product with the line's name (display-normalized) and the category is
    created and the line is linked to it.

  When the product's category changes, PC7 applies to the product's other lines.
- **PC7 Product category change moves its lines (FR-36).** When a product's category
  changes (through product management or PC6), every saved line linked to the product gets
  the new category. Those lines get source `remembered`, except the line the user just
  corrected (PC6), which gets `user`. A rename that keeps the category changes no line.
  Deleting a product keeps its lines' categories and sources and removes their link.
- **PC8 Catalog rules with lines.** A category used by a product or by a line cannot be
  deleted, so no line loses its category (extends FR-37): the error `category_in_use` has
  `product_count` and, when lines use the category, a new `line_count` (left out at 0, so
  the product-management body stays as it was). A category used by lines cannot be turned into a
  group, as with products (FR-39).
- **PC9 Fake (NFR-13).** With `RRMC_ENGINES=fake`, the model's suggestion is deterministic:
  every line asked about gets the first category of the list (the order of
  `CategoryService.list()`).
- **PC10 Privacy (NFR-1, NFR-3).** Line names go only to `RRMC_OLLAMA_URL` through the
  existing model client. Logs and error messages carry no line, product or category name.

### Why a separate model call

The user asked for the most efficient way. On this CPU, output tokens are the slow part
(PRD open question 1: about 10 output tokens/s, against about 60 prompt tokens/s). Two
options were compared:

| | Category in the reading answer | Separate call for unknown lines (chosen) |
|---|---|---|
| Output | about 4 more tokens for **every** line (`,"c":12`) | about 2 tokens per **unknown** name, plus a short wrapper |
| Prompt | the category list (about 200 tokens) added to every reading prompt | the list and the unknown names, only when needed |
| Known products | the model categorizes them anyway | not sent; no call when all are known |
| Reading | prompt changes, so the evaluated accuracy of [ADR 0003](../../docs/adr/0003-receipt-reading-model.md) no longer holds | unchanged |

For a first receipt of 15 unknown lines both cost a few seconds. As the product list grows,
the separate call shrinks and disappears, while the combined answer keeps its full cost.
Keeping reading unchanged also keeps the reader swappable for a vision model.

### Out of Scope
- UI and API endpoints: the review UI spec adds the receipt view, the line editing
  endpoints and the category dropdown (FR-16–FR-21). This spec gives it the services.
- FR-43 (renaming a line links it to a matching product): it is part of line editing in
  the review UI spec.
- Re-categorizing saved receipts: receipts imported before this feature keep no category,
  and no button re-runs categorization. Model-suggested lines stay as they are when the
  catalog changes.
- Linking earlier unlinked lines with the same name when the user corrects one line: only
  the corrected line is linked.
- One category for a whole receipt: categorization is per line (PRD open question 6). A
  one-line receipt gets one category through its line.
- Totals (FR-22–FR-25) and export.
- Measuring categorization accuracy with the evaluation tool.
- OCR mix-ups and fuzzy matching in names (the rest of FR-14): looser matching changes the
  FR-35 uniqueness of existing product names, so a later spec decides it from the names in
  real corrections. This spec matches by the existing normalized key only.

## Acceptance Criteria

Unless an AC says otherwise: the catalog is the default list of PRD 6.9; the receipt is
read with store `"Testikauppa"`, date `2026-10-29`, total 1 000 cents; the model's reading
answer comes from a test double; "the categorization call" is the model call made with the
categorization schema.

### AC1: A remembered product gives the category
**Given** the product `Kevytmaito 1L` with category `Maitotuotteet`, and a read line
`"KEVYTMAITO  1L"`, 129 cents
**When** the image is imported
**Then** the stored line has category `Maitotuotteet`, source `remembered` and is linked to
`Kevytmaito 1L`, and no categorization call is made

### AC2: Only unknown lines go to the model, in one call
**Given** the product `Ruisleipä` (`Leivät`), and read lines `"Ruisleipä"`, `"Banaani"`,
`"Tomaatti"`
**When** the image is imported and the model answers the numbers of `Hedelmät` and
`Vihannekset`
**Then** exactly one categorization call is made; its names are `"Banaani"`, `"Tomaatti"`
in this order; the lines get `Leivät` (`remembered`), `Hedelmät` (`model`), `Vihannekset`
(`model`); the two model lines are not linked; the product count is unchanged

### AC3: The prompt offers categories with their groups, never groups
**Given** the default catalog
**When** a categorization call is made
**Then** the prompt lists 21 numbered options, among them `Ruoka > Maitotuotteet`,
`Auto > Polttoaineet` and `Juomat`, and neither `Ruoka` nor `Auto` as an option of its own

### AC4: A repeated name is asked once
**Given** read lines `"Banaani"`, `"BANAANI"`, `"Omena"`, none of them known
**When** the image is imported and the model answers two numbers
**Then** the call has the names `"Banaani"`, `"Omena"`, and both banana lines get the first
answered category

### AC5: Deposit refunds get no category
**Given** read lines `"Kevytmaito 1L"` (known, 129 cents) and `"Panttipalautus"`
(−40 cents, deposit refund)
**When** the image is imported
**Then** the refund line has no category, no source and no product link, no categorization
call is made, and no product `Panttipalautus` exists

### AC6: A one-line receipt gets one category
**Given** one read line `"Bensiini 95E10"`, 6 000 cents, not known
**When** the image is imported and the model answers the number of `Polttoaineet`
**Then** the receipt's only line has category `Polttoaineet`, source `model`

### AC7: An invalid answer leaves lines without category
**Given** read lines `"Ruisleipä"` (known) and `"Banaani"`, `"Tomaatti"` (unknown)
**When** the categorization answer is one of: not JSON; JSON without the answer key; one
number for two names; a decimal number
**Then** the import outcome is `imported`, the file is in the done folder, `"Ruisleipä"`
has `Leivät` (`remembered`), and both unknown lines have no category and no source

### AC8: A number outside the list affects only its line
**Given** read lines `"Banaani"`, `"Tomaatti"`, unknown, and 21 categories
**When** the model answers `[0, 5]`, or `[22, 5]`
**Then** `"Banaani"` has no category and `"Tomaatti"` has the fifth listed category with
source `model`

### AC9: A model timeout or error status leaves lines without category
**Given** an unknown read line
**When** the categorization call raises `ModelTimeoutError` or `ModelAnswerError`
**Then** the outcome is `imported` and the line has no category

### AC10: An unavailable model stops the run
**Given** two images in the import folder, the first with an unknown line
**When** the categorization call for the first raises `ModelUnavailableError`
**Then** the run state is `stopped` (`model_unavailable`), both images stay in the import
folder, and no receipt is stored

### AC11: No categories, no call
**Given** a catalog with no categories (every category deleted) and an unknown read line
**When** the image is imported
**Then** no categorization call is made and the line has no category

### AC12: Catalog changes during the run do not fail the image
**Given** an unknown line `"Banaani"` for which the model answers `Hedelmät`, and a known
line `"Ruisleipä"`
**When** between the categorization call and the commit, `Hedelmät` is deleted and the
product `Ruisleipä` is deleted
**Then** the outcome is `imported`; `"Banaani"` has no category; `"Ruisleipä"` has no
category and no link

### AC13: Correcting an unlinked line creates the product
**Given** a stored line `"Banaani"` with category `Muut` (`model`), not linked, and no
product with that normalized name
**When** the user sets its category to `Hedelmät`
**Then** the line has `Hedelmät`, source `user`, and is linked to a new product `Banaani`
with category `Hedelmät`

### AC14: Correcting an unlinked line uses an existing product
**Given** a stored unlinked line `"BANAANI"` (`model`, `Muut`), the product `Banaani`
(`Herkut`), and another line linked to `Banaani`
**When** the user sets the first line's category to `Hedelmät`
**Then** the product `Banaani` has `Hedelmät`; the first line has `Hedelmät` (`user`) and is
linked to it; the other line has `Hedelmät` (`remembered`); no product is created

### AC15: Correcting a linked line moves the product's other lines
**Given** the product `Kevytmaito 1L` (`Maitotuotteet`) with three linked lines on two
receipts
**When** the user sets one of them to `Juomat`
**Then** the product has `Juomat`; that line has source `user`; the other two have `Juomat`
with source `remembered`

### AC16: Correction errors change nothing
**Given** a stored line
**When** the user sets its category with: a line id that does not exist; a category id
that does not exist; the id of the group `Ruoka`; the line is a deposit refund; or the
line name is longer than 100 characters and no product matches it
**Then** the service raises, in order, `NotFoundError`, `UnknownCategoryError`,
`NotACategoryError`, `DepositRefundLineError`, `InvalidNameError`, and no line or product
changes

### AC17: Product category change moves its lines (FR-36)
**Given** the product `Ruisleipä` (`Leivät`) with two linked lines, one of them with source
`user`, and an unlinked line `"Ruisleipä"` with source `model`
**When** `ProductService.update` sets the product's category to `Kuivatuotteet`
**Then** both linked lines have `Kuivatuotteet` with source `remembered`; the unlinked line
is unchanged

### AC18: A product rename does not move lines
**Given** the product `Ruisleipä` (`Leivät`) with a linked line
**When** `ProductService.update` renames it to `Ruisleipä 500 g` and keeps `Leivät`
**Then** the line is unchanged and still linked

### AC19: Deleting a product keeps line categories
**Given** the product `Ruisleipä` (`Leivät`) with a linked line of source `remembered`
**When** the product is deleted
**Then** the line has `Leivät`, source `remembered`, and no link

### AC20: A category used by lines
**Given** the category `Herkut` used by one line and no product
**When** the user deletes it, or turns it into a group
**Then** the delete fails with `category_in_use`, `product_count` 0 and `line_count` 1;
turning it into a group fails with `category_has_products`; the category and the line are
unchanged

### AC20b: The line count with products
**Given** the category `Herkut` used by 2 products and 3 lines
**When** the user deletes it
**Then** it fails with `category_in_use`, `product_count` 2 and `line_count` 3

### AC21: Fake suggestion is deterministic
**Given** `RRMC_ENGINES=fake`, the default catalog and an unknown line
**When** the line is categorized by the model
**Then** it gets `Autohuolto` (the first category in list order: groups in Finnish order,
so `Auto` before `Ruoka`), source `model`, on every run

### AC22: Existing receipts are not changed
**Given** a database at schema version 3 with a receipt and two lines
**When** the backend starts and migrates
**Then** both lines have no category, no source and no link, and keep their names and
amounts

### AC23: No names in logs or errors
**Given** an import of a receipt with lines `"Banaani"`, `"Tomaatti"` whose categorization
answer is invalid, and a correction that fails with `DepositRefundLineError`
**When** the log and the exception messages are inspected
**Then** neither contains `Banaani`, `Tomaatti`, `Panttipalautus` or a category name

## Files to Modify
| File | Change |
|---|---|
| `backend/app/storage/migrations/0004_line_categories.sql` | New: category, source and product columns on `receipt_lines` |
| `backend/app/storage/receipt_repository.py` | Write and read the new line columns; update lines by product |
| `backend/app/storage/catalog_repository.py` | Line counts for categories (PC8) |
| `backend/app/categorization/line_categorizer.py` | New: PC2–PC5 for one read receipt |
| `backend/app/categorization/prompt.py` | New: categorization prompt, answer schema and parsing |
| `backend/app/categorization/suggester.py`, `factory.py` | New: the model suggester, the fake suggester (PC9) and the choice between them |
| `backend/app/categorization/service.py` | PC6 line correction; PC7 in `ProductService.update` and `delete`; PC8 |
| `backend/app/categorization/errors.py` | `DepositRefundLineError`; `line_count` on `CategoryInUseError` |
| `backend/app/receipt_import/run.py`, `service.py` | Categorize after reading; store the result in the commit |
| `backend/tests/...` | Unit and integration tests below; `tests/receipt_import_data.py` and the run's test call get the categorizer argument |
| `backend/tests/unit/storage/test_receipt_lines_schema.py` | Two receipt-reading tests pinned migration 3 as the newest, which migration 0004 changes by design: `test_ac13_migration_3_adds_read_fields_and_lines` allows the columns of later migrations and checks that version 3 is applied, as the receipts table test does; `test_receipts_imported_before_reading_keep_empty_read_fields` checks that migration 3 is the first one applied instead of the only one. What they verify stays the same |
| `docs/adr/0004-line-categorization.md` | New: remembered first, separate model call, suggestions not remembered |
| `docs/subsystems/categorization/README.md` | Line categorization, correction, FR-36 |
| `docs/subsystems/import/README.md` | The categorization step in the data flow |
| `docs/subsystems/storage/README.md` | New repository methods, migration 0004 |
| `docs/subsystems/receipt-reading/README.md` | Categorization as a user of `generate()` |
| `docs/datamodel.md` | New `receipt_lines` columns and the relationships |
| `docs/architecture.md` | The import flow with categorization |
| `docs/api-reference.md` | `category_in_use` with `line_count` |
| `docs/glossary.md` | Category source, linked line, suggestion |
| `docs/content-plan.md` | Status notes for this spec, ADR 0004 |
| `specs/PRD.md` | Open question 6 resolved; FR-37 extended to lines; FR-14 note that OCR mix-ups come in a later spec |
| `backend/app/texts.py` | The Finnish `category_in_use` message also names the line count (the UI shows the backend's message, so the frontend does not change) |
| `specs/README.md` | Row for this spec |

## Risk
- **What could break:** import (a new step between reading and the commit); product
  updates and deletes now also write lines; the migration on a database with receipts. A
  bug that raises in categorization would fail every image as `internal_error`.
- **Performance:** a receipt with unknown lines takes a few seconds more (NFR-8); a receipt
  with only known lines takes no longer.
- **Data:** PC7 changes many lines with one product update; it runs in the update's
  transaction, so it is all or nothing.
- **Rollback:** revert the change. Migration 0004 only adds nullable columns, so the old
  code still reads the database; the added data is ignored.
- **Dependencies:** Ollama with the model of `RRMC_MODEL`; nothing new to install.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | line categorizer | remembered | product key matches | categorize | `remembered`, linked, no call | fake model counting calls |
| AC2 | line categorizer | mixed | 1 known, 2 unknown | categorize | one call with 2 names in order | fake model |
| AC3 | categorization prompt | options | default catalog | build prompt | 21 options, `Ruoka > Maitotuotteet`, no bare group | none |
| AC4 | line categorizer | repeated name | `Banaani`, `BANAANI` | categorize | one name asked, both lines same category | fake model |
| AC5 | line categorizer | refund | refund line | categorize | no category, not asked | fake model |
| AC6 | line categorizer | one line | one unknown line | categorize | one category, `model` | fake model |
| AC7 | answer parsing | invalid | not JSON, missing key, wrong count, decimal | parse | `None` | none |
| AC8 | answer parsing | out of range | `[0, 5]`, `[22, 5]` | map | first line none, second category 5 | none |
| AC9 | line categorizer | errors | timeout, error status | categorize | lines without category | raising fake model |
| AC10 | line categorizer | unavailable | `ModelUnavailableError` | categorize | error passes through | raising fake model |
| AC11 | line categorizer | empty catalog | no categories | categorize | no call | fake model |
| AC16 | line correction service | each error | see AC16 | set category | the named error, nothing written | real SQLite |
| AC21 | `FakeSuggester`, `create_suggester` | fake engines | 3 names, 21 options | suggest | `[0, 0, 0]`; the factory returns the fake for `fake` and `ModelSuggester` for `real` | none |

### Integration tests
Real SQLite (temporary file), real import service and catalog services; the reader and the
model are test doubles.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1, AC2 | import with known and unknown lines | import run | stored categories, sources and links as in the ACs | — |
| AC5 | import with a refund | import run | refund line without category, no product | — |
| AC7 | import with invalid answer | import run | `imported`, file in done folder, lines without category | — |
| AC10 | model lost in categorization | import run of 2 images | state `stopped`, both files in import folder, 0 receipts | — |
| AC12 | catalog changed before commit | hook between call and commit deletes `Hedelmät` and product | `imported`, lines as in AC12 | — |
| AC13–AC15 | corrections | line correction service | products and lines as in the ACs | — |
| AC17–AC19 | product update and delete | `ProductService.update`, `delete` | lines as in the ACs | — |
| AC20 | category used by a line | `CategoryService.delete`; `update` to a group | `category_in_use` (0, 1); `category_has_products` | — |
| AC20b | category used by products and lines | `DELETE /api/categories/{id}` | `category_in_use`, `product_count` 2, `line_count` 3 | 409 |
| AC21 | fake engines | import with `RRMC_ENGINES=fake` | `FAKE_RECEIPT` lines with `Autohuolto` | — |
| AC22 | migration | version 3 database with lines | lines unchanged, no category | — |
| AC23 | privacy | import with invalid answer; failing correction | log and messages without the names | — |

### E2E tests
None apply: this spec adds no UI. The existing E2E import journey must stay green with the
fake engines.

### Coverage target
- Backend: 90 % lines for the new categorization code; every branch of the answer mapping,
  the correction service and PC7.
- Frontend: no change.

### Test data
- Synthetic fixtures only: invented product names (`Kevytmaito 1L`, `Ruisleipä`,
  `Banaani`, `Tomaatti`, `Bensiini 95E10`, `Panttipalautus`), the default catalog.
- Mocks: the receipt reader and the model (`ReceiptModel` doubles that count calls, return
  a given answer, or raise).

## Related Documentation (MANDATORY)
- Tier 1: [PRD](../PRD.md) sections 6.3, 6.5 (FR-44), 6.8 (FR-36, FR-37, FR-39), 11
  (question 6); [architecture.md](../../docs/architecture.md);
  [datamodel.md](../../docs/datamodel.md); [api-reference.md](../../docs/api-reference.md);
  [glossary.md](../../docs/glossary.md)
- Tier 2: [categorization](../../docs/subsystems/categorization/README.md),
  [import](../../docs/subsystems/import/README.md),
  [storage](../../docs/subsystems/storage/README.md),
  [receipt-reading](../../docs/subsystems/receipt-reading/README.md)
- ADRs: [0001](../../docs/adr/0001-tech-stack.md), [0003](../../docs/adr/0003-receipt-reading-model.md)
- Specs: [product management](product-management.md), [receipt reading](receipt-reading.md)
- ADR to create: [0004](../../docs/adr/0004-line-categorization.md) (Plan)

## Plan

### Corrections to the spec found while planning
- **PC9 fake:** the fake is a fake **suggester** chosen by `RRMC_ENGINES`, like the fake
  reader, not a change to `FakeReceiptModel`. The fake model returns a reading answer for
  any schema, and engines must not depend on categorization. AC21 is unchanged.
- **Files to Modify:** `backend/app/engines/model.py` does not change; new
  `backend/app/categorization/suggester.py` and `factory.py`; ADR 0004 added.

### Components

| ID | File | What | ACs |
|---|---|---|---|
| P1 Migration | `backend/app/storage/migrations/0004_line_categories.sql` | Three nullable columns on `receipt_lines` and two indexes (see [Data model changes](#data-model-changes)) | AC22, PC1 |
| P2 Line columns | `backend/app/storage/receipt_repository.py` | `add_line(..., category=None)` with a `LineCategory`; `LineRow` gets `category_id`, `category_source`, `product_id` (default `None`, so existing callers keep working); new `get_line(line_id) -> StoredLine` and `set_line_category(line_id, category)` | AC1–AC15 |
| P3 Catalog SQL | `backend/app/storage/catalog_repository.py` | `CategoryRow.line_count` (a subquery like `product_count`); `move_product_lines(product_id, category_id)` sets the category and source `remembered` on every line linked to the product | AC14, AC15, AC17, AC20, AC20b |
| P4 Prompt | `backend/app/categorization/prompt.py` | `category_options(rows)` → labels in list order; `category_prompt(options, names)`; `answer_schema(option_count, name_count)`; `parse_answer(raw, option_count, name_count) -> list[int \| None] \| None` | AC3, AC7, AC8 |
| P5 Suggester | `backend/app/categorization/suggester.py` | `CategorySuggester` protocol: `suggest(names, options) -> list[int \| None]` (0-based option index per name); `ModelSuggester(model)`; `FakeSuggester` (index 0 for every name) | AC7–AC10, AC21 |
| P6 Factory | `backend/app/categorization/factory.py` | `create_suggester(settings, engines)`: `FakeSuggester` with `RRMC_ENGINES=fake`, else `ModelSuggester(engines.model)` | AC21 |
| P7 Line categorizer | `backend/app/categorization/line_categorizer.py` | `LineCategorizer(repository, suggester)` with `suggest(lines) -> Suggestions` (before the commit; may call the model) and `resolve(lines, suggestions) -> list[LineCategory \| None]` (inside the commit) | AC1, AC2, AC4–AC6, AC11, AC12 |
| P8 Correction | `backend/app/categorization/service.py` | `LineCategoryService(catalog, receipts).set_category(line_id, category_id)`; FR-36 in `ProductService.update`; `line_count` in `CategoryService.delete` and in the kind check of `update` | AC13–AC20b |
| P9 Errors and texts | `backend/app/categorization/errors.py`, `backend/app/texts.py` | `DepositRefundLineError` (`deposit_refund_line`, 422); `CategoryInUseError(product_count, line_count)`; Finnish texts | AC16, AC20, AC20b |
| P10 Import | `backend/app/receipt_import/run.py`, `service.py` | `process_file(..., categorizer=)`; `ImportService(..., suggester=)` builds a `LineCategorizer` on the run's connection | AC1, AC7, AC10, AC12 |

### Data model changes

```sql
ALTER TABLE receipt_lines ADD COLUMN category_id INTEGER
    REFERENCES categories (id) ON DELETE RESTRICT;
ALTER TABLE receipt_lines ADD COLUMN category_source TEXT
    CHECK (category_source IN ('remembered', 'model', 'user'))
    CHECK ((category_source IS NULL) = (category_id IS NULL))
    CHECK (category_id IS NULL OR is_deposit_refund = 0);
ALTER TABLE receipt_lines ADD COLUMN product_id INTEGER
    REFERENCES products (id) ON DELETE SET NULL
    CHECK (product_id IS NULL OR category_id IS NOT NULL);
CREATE INDEX receipt_lines_category ON receipt_lines (category_id);
CREATE INDEX receipt_lines_product ON receipt_lines (product_id);
```

- `ADD COLUMN` with `REFERENCES` needs a `NULL` default, which these columns have. SQLite
  checks a new column's `CHECK` against existing rows; existing rows are all `NULL`, so they
  pass (AC22).
- `ON DELETE SET NULL` gives AC19 without code: deleting a product removes the links and
  keeps the category and the source. `RESTRICT` on `category_id` is the safety net behind
  PC8.
- The indexes keep FR-36 updates and the category delete check from scanning all lines.

### Interfaces

```python
type CategorySource = Literal["remembered", "model", "user"]

@dataclass(frozen=True)
class LineCategory:                # storage: what a line stores
    category_id: int
    source: CategorySource
    product_id: int | None

class CategorySuggester(Protocol):
    def suggest(self, names: Sequence[str], options: Sequence[str]) -> list[int | None]:
        """One option index per name, None where there is no usable suggestion.
        Raises ModelUnavailableError; never raises for a bad answer."""

class LineCategorizer:
    def suggest(self, lines: Sequence[ReadLine]) -> Suggestions: ...  # name_key -> category id
    def resolve(
        self, lines: Sequence[ReadLine], suggestions: Suggestions
    ) -> list[LineCategory | None]: ...

class LineCategoryService:
    def set_category(self, line_id: int, category_id: int) -> StoredLine:
        """Raises: NotFoundError, UnknownCategoryError, NotACategoryError,
        DepositRefundLineError, InvalidNameError."""
```

`process_file` takes the categorizer through a small protocol with `suggest` and
`resolve`, so the unit tests of the run pass a stub. The test helper in
`tests/receipt_import_data.py` and the run's test call get the new argument. This is an
interface change, as `reader` was in the receipt-reading spec; no assertion changes.

### Data flow

**Import of one file** (new steps in bold):

| Step | What | On error |
|---|---|---|
| 1–3 | Read bytes, check format, duplicate check | unchanged |
| 4 | `reader.read` | unchanged |
| **4b** | `categorizer.suggest(read.lines)`: list the categories (`CategoryService.list()` order, kind `category`); find the categorizable lines whose key matches no product; unique keys in first-seen order; if there are any and the list is not empty, one `suggester.suggest(names, options)`; map indexes to category ids | `ModelUnavailableError` stops the run (AC10); any other exception is `internal_error`, as today |
| 5 | Choose the done-folder name | unchanged |
| 6 | In one transaction: add the receipt, then **`categorizer.resolve`**, then each line with its `LineCategory` | `sqlite3.Error` is `save_failed`, as today |
| 7 | Move the file | unchanged |

`resolve`, per line: a deposit refund gets `None`; a line whose key matches a product gets
the product's category, `remembered`, linked; otherwise a suggested category that still
exists and is still of kind `category` gets `model`, unlinked; otherwise `None` (AC12).
Matching in `resolve` uses the transaction's view, so a product deleted after step 4b is
not used.

**Model call** (`ModelSuggester`):

```text
You choose a shopping category for each product name from a Finnish shop receipt.
Answer with JSON only: {"c": [...]}, one category number per product, in product order.

Categories:
1 Ruoka > Maitotuotteet
...
21 Muut

Products:
1 Banaani
2 Tomaatti
```

- The category list comes before the names, so the prompt's start is the same for every
  receipt and Ollama can reuse it from its prompt cache.
- Schema: `{"type": "object", "properties": {"c": {"type": "array", "items": {"type":
  "integer", "enum": [1, ..., N]}, "minItems": k, "maxItems": k}}, "required": ["c"]}`.
  Ollama turns the schema into a grammar, so the model should not be able to write a wrong
  count or number. `parse_answer` still checks both (AC7, AC8), because the grammar is
  Ollama's behavior, not a guarantee of the interface.
- `ModelTimeoutError` and `ModelAnswerError` give `[None] * k` (AC9). The existing
  `generate` timeout (300 s) and context (8 192 tokens) apply; 21 categories and a long
  receipt stay far below the context.
- Names are sent as read (trimmed), the first line of each key.

**Correction** (`LineCategoryService.set_category`), in one transaction on one connection:

1. Get the line (`NotFoundError`) and the category (`UnknownCategoryError`), check the
   category's kind (`NotACategoryError`) and the line's refund flag
   (`DepositRefundLineError`).
2. Product: the linked one; otherwise `get_product_by_key(normalize_key(line.name))`;
   otherwise `validate_product_name(line.name)` (`InvalidNameError`) and `add_product`.
3. If the product's category differs: `update_product` and `move_product_lines` (FR-36).
4. `set_line_category(line, LineCategory(category_id, "user", product_id))`.

`ProductService.update` calls `move_product_lines` when the category changes (AC17), not
on a rename alone (AC18). The step-3 code is one private helper shared by both, because
`ProductService.update` opens its own transaction and cannot be called inside another.

**Catalog rules:** `CategoryService.delete` raises `CategoryInUseError(product_count,
line_count)` when either count is above 0 (AC20, AC20b); `line_count` is in `extra` only
when it is above 0, so the product-management AC13 body is unchanged. `update` to kind `group` raises
`CategoryHasProductsError` when either count is above 0.

Finnish texts: `category_in_use` names the non-zero counts, e.g. "Kategoriaa käyttää 2
tuotetta ja 3 kuittiriviä." or "Kategoriaa käyttää 1 kuittirivi."; `CATEGORY_HAS_PRODUCTS`
becomes "Kategoriaa, jossa on tuotteita tai kuittirivejä, ei voi muuttaa ryhmäksi.";
`DEPOSIT_REFUND_LINE` is "Pantinpalautusriville ei voi valita kategoriaa." The UI already
shows the backend's message, so the frontend does not change.

### Dependencies
None new.

### ADR
`docs/adr/0004-line-categorization.md`: remembered products first, then one separate model
call per receipt for unknown names only, instead of a category in the reading answer; model
suggestions are not remembered. The reasons are those of
[Why a separate model call](#why-a-separate-model-call).

### Check against the ACs

| AC | Covered by |
|---|---|
| AC1, AC2, AC4–AC6, AC11 | P7 `suggest` and `resolve` |
| AC3 | P4 `category_options`, `category_prompt` |
| AC7, AC8 | P4 `parse_answer`, P5 |
| AC9, AC10 | P5 (`ModelUnavailableError` passes through), P10 (the run stops as today) |
| AC12 | P7 `resolve` inside the P10 commit |
| AC13–AC16 | P8 `LineCategoryService`, P9 |
| AC17–AC19 | P8 `ProductService.update`, P1 `ON DELETE SET NULL` |
| AC20, AC20b | P3 `line_count`, P8, P9 |
| AC21 | P5 `FakeSuggester`, P6 |
| AC22 | P1 |
| AC23 | The messages of P5 and P9 name no content; nothing new is logged |

## Tasks

Each task is one Red → Green → Refactor cycle unless it says otherwise. New backend unit
tests go to `backend/tests/unit/categorization/` or next to the existing ones
(`unit/storage/`, `unit/receipt_import/`); import API tests go to the new
`backend/tests/integration/test_import_categorization_api.py`, catalog API tests to the
existing `test_categories_api.py`. Test names start with the AC ID. After every task the
backend tests, lint, format check and type check pass. Existing assertions are never edited.

### Storage

- [x] **T1 Migration 0004 (AC22, PC1).** Tests in `unit/storage/test_receipt_lines_schema.py`:
  `test_ac22_existing_lines_have_no_category` (a version 3 database with lines, migrated),
  and the constraints: an unknown source, a source without a category, a category without
  a source, a category on a deposit refund, and a product without a category each raise
  `sqlite3.IntegrityError`; deleting a category used by a line raises; deleting a product
  sets `product_id` to `NULL` and keeps the category and source. Green: P1.
- [x] **T2 Line columns in the repository (P2).** Tests in `test_receipt_repository.py`:
  `add_line` with and without a `LineCategory`, `lines` returns the three fields,
  `get_line` (and `None` for a missing id), `set_line_category`. Green: P2.
- [x] **T3 Catalog SQL (P3).** Tests in `test_catalog_repository.py`: `line_count` of a
  category with 0 and 3 lines; `move_product_lines` changes only the product's lines and
  sets source `remembered`. Green: P3.

### Prompt and suggester

- [x] **T4 Options and prompt (AC3).** `test_ac3_options_have_groups_and_no_bare_group` in
  `test_category_prompt.py`: 21 options from the default catalog, `Ruoka > Maitotuotteet`,
  `Auto > Polttoaineet`, `Juomat`, no `Ruoka` or `Auto` option; the prompt has the numbered
  list before the numbered names; the schema has `enum` 1…21 and `minItems`/`maxItems` k.
  Green: `category_options`, `category_prompt`, `answer_schema`.
- [x] **T5 Answer parsing (AC7, AC8).** `test_ac7_invalid_answers_are_none` (not JSON, no
  `c`, wrong count, a decimal, a boolean) and `test_ac8_numbers_outside_the_list_are_none`
  (`[0, 5]`, `[22, 5]` → `[None, 4]`). Green: `parse_answer`.
- [x] **T6 Model suggester (AC7–AC10).** Tests in `test_suggester.py` with a model double:
  one `generate` call with the prompt and schema of T4; an invalid answer gives `[None,
  None]`; `ModelTimeoutError` and `ModelAnswerError` give all `None`;
  `ModelUnavailableError` passes through. Green: `ModelSuggester`.
- [x] **T7 Fake suggester and factory (AC21).** `test_ac21_fake_suggests_the_first_option`;
  `create_suggester` returns `FakeSuggester` for `fake` and `ModelSuggester` for `real`.
  Green: `FakeSuggester`, P6.

### Line categorizer

- [x] **T8 Remembered and unknown lines (AC1, AC2, AC6).** Tests in
  `test_line_categorizer.py` with real SQLite and a suggester double that records calls:
  `test_ac1_remembered_product_gives_category_without_call`,
  `test_ac2_only_unknown_names_in_one_call`, `test_ac6_one_line_receipt`. Green: P7
  `suggest` and `resolve`.
- [x] **T9 Repeated names, refunds, empty catalog (AC4, AC5, AC11).**
  `test_ac4_repeated_name_asked_once`, `test_ac5_refund_has_no_category_and_no_call`,
  `test_ac11_no_categories_no_call`. Green: P7.
- [x] **T10 Catalog changed before resolve (AC12).**
  `test_ac12_deleted_category_and_product_are_not_used`: delete `Hedelmät` and the product
  between `suggest` and `resolve`; also a suggested category turned into a group. Green: P7.

### Import

- [x] **T11 Categorizer in the run (AC1, AC7, AC9, AC10).** In `test_import_run.py`: pass a
  categorizer stub through the helper of `tests/receipt_import_data.py` (interface change
  only); new tests: the lines are stored with the stub's categories in the commit;
  `ModelUnavailableError` from `suggest` leaves the file in the import folder and stores
  nothing; another exception from `suggest` is `internal_error`. Green: P10 `process_file`.
- [x] **T12 Service wiring (AC21).** In `test_import_service.py`: `ImportService` builds the
  suggester with `create_suggester` by default and takes `suggester=`; the run uses a
  `LineCategorizer` on its own connection. Green: P10 `ImportService`.
- [x] **T13 Import API (AC1, AC2, AC5, AC7, AC10, AC12, AC21, AC23).** In
  `test_import_categorization_api.py`, real app and SQLite, reader and suggester doubles:
  known and unknown lines; a refund; an invalid answer (`imported`, file in the done
  folder); model lost (state `stopped`, both files in the import folder, 0 receipts); a
  suggester double that deletes `Hedelmät` and the product after answering; fake engines
  (`FAKE_RECEIPT` lines get `Autohuolto`); `caplog` and error messages without `Banaani`,
  `Tomaatti` or a category name. Green: fixes only if a gap shows.

### Corrections and catalog rules

- [x] **T14 Correction errors (AC16, AC23).** Tests in `test_line_category_service.py`:
  `test_ac16_errors_change_nothing` for each case in AC16, with the row and product counts
  unchanged; the `DepositRefundLineError` message names no line. Green: P8 checks, P9
  `DepositRefundLineError` and `DEPOSIT_REFUND_LINE`.
- [x] **T15 Corrections (AC13–AC15).** `test_ac13_unlinked_line_creates_product`,
  `test_ac14_unlinked_line_uses_existing_product`,
  `test_ac15_linked_line_moves_other_lines`. Green: P8 `set_category` and the shared helper.
- [x] **T16 FR-36 in product updates (AC17–AC19).** In `test_product_service.py`:
  `test_ac17_category_change_moves_linked_lines`, `test_ac18_rename_keeps_lines`,
  `test_ac19_delete_keeps_line_categories`. Green: `ProductService.update` uses the helper.
- [x] **T17 Category used by lines (AC20, AC20b).** In `test_category_service.py`:
  `test_ac20_category_used_by_line_cannot_be_deleted_or_grouped`,
  `test_ac20b_counts_products_and_lines`; in `test_catalog_errors.py` the texts for
  (2, 3), (0, 1), (1, 0); in `test_categories_api.py` `DELETE` gives 409 with
  `product_count` 2 and `line_count` 3. Green: P8 rules, P9 `CategoryInUseError` and texts.

### Docs and checks

- [x] **T18 Docs (no test).** ADR 0004; `docs/datamodel.md` (columns, relationships,
  migration count 4); `docs/subsystems/categorization/README.md`, `import/README.md`,
  `storage/README.md`, `receipt-reading/README.md`; `docs/architecture.md` (import flow);
  `docs/api-reference.md` (`category_in_use` with `line_count`, `deposit_refund_line`);
  `docs/glossary.md` (category source, linked line); `docs/content-plan.md` statuses;
  `specs/PRD.md` (open question 6 resolved, FR-37 extended to lines, FR-14 note).
- [x] **T19 Full check (no test).** Backend tests, lint, format check and type check;
  frontend tests and the E2E tests with the fake engines stay green; coverage of the new
  categorization code at least 90 %. Set this spec to `In Progress` at T1 and leave `Done`
  to the audit.

## Audit

Audited 2026-10-30, verdict PASS after one fix cycle. An independent reviewer read the code
against this spec; its findings were checked in the code (by mutation) before acting on them.

- Acceptance criteria: 24/24 met (AC1–AC23 with AC20b); every AC has a test whose name
  carries its ID.
- Tests: backend 691 passed; 100 % lines and branches in `app/categorization`,
  `receipt_import/run.py` and the two repositories (target 90 %). Frontend 82 passed (no
  frontend change). E2E 6 passed, twice in a row. Container tests passed. Lint, format and
  type checks clean; no skipped or TODO tests.
- Security: no findings. No line, product or category name in logs or error messages
  (AC23 runs at DEBUG); SQL is parameterized and only in `app/storage`; names go only to the
  existing local model client; test data is synthetic. No dependency changed, so
  `pip-audit` and `npm audit` were not needed for this change.
- Architecture: engines, receipt-reading and storage do not depend on categorization;
  import depends on categorization, as `docs/architecture.md` now says.
- Docs: categorization, import, storage and receipt-reading READMEs, `datamodel.md`,
  `architecture.md`, `api-reference.md`, `glossary.md`, `content-plan.md`, PRD and ADR 0004
  updated; links checked; a scan found no undocumented module or stale statement for this
  change.
- Fixed in the audit:
  - The transaction of `LineCategoryService.set_category` was untested (replacing it with
    no transaction passed every test). New test
    `test_ac15_failed_correction_rolls_back_the_product_and_its_lines`; the mutation now fails.
  - The categorizer's guard against an index outside the options was untested (a `-1`
    would have given the last category). New test
    `test_ac8_index_outside_the_options_gives_no_category`; the mutation now fails.
  - `LineCategoryService` documents that both repositories must share one connection.
  - `api-reference.md` notes `deposit_refund_line`; `architecture.md` dependency rules and
    subsystem list, and the categorization README's dependencies, match the code.
- Later:
  - Some Testing Strategy rows are covered at another level than listed: AC9 and AC10 at the
    suggester and run level, not with a raising model in the categorizer; AC13–AC20 as unit
    tests on real SQLite, not integration tests; the import-level AC7 test uses one invalid
    answer (the others are covered by `parse_answer`).
  - `LineCategoryService` could build both repositories from one connection when the review
    UI spec adds its endpoint.
  - How well the real model categorizes is not measured.
