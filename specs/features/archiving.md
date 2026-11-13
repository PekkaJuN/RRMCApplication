# Feature: Archiving

## Overview
- **Status:** Done
- **Created:** 2026-11-13
- **Updated:** 2026-11-13: research decisions of 2026-11-12 and the four defaults confirmed by
  the user (no undo, archived images stay duplicates, period warnings, confirmations with
  counts and a backup hint). Decided by the agent for review: see
  [Agent decisions for review](#agent-decisions-for-review). User changes: no receipt view
  for archived years; totals per group, category and product; the wide year table (PC15,
  AC43). The user approved Specify with decisions 1–7 on 2026-11-13. Plan approved
  2026-11-13; Tasks approved 2026-11-13. Implementation notes (2026-11-13), for the audit:
  P1 and P6 changed to match the code (see the notes there). G7 record: after red runs,
  existing tests were changed to the new interfaces, not to new expectations:
  `test_review_service.py` (`RacingRepository` overrides `image_known`, the user approved),
  `test_health.py` (the archive folder in `make_folders`), `test_export_api.py`
  (`FixedExporter.archive_totals_file`), `test_totals_service.py` (the `ArchiveRepository`
  argument), and `App.test.tsx` (`Arkisto` added to the navigation list of PC14). New tests
  were fixed in their first Red before the code passed them: `test_archive_api.py` (AC3
  data), the waiting helpers of `ArchivePage.test.tsx`, the row helper of
  `ArchiveYearPage.test.tsx`, and the status lookup of `e2e/archive.spec.ts` (the status
  line is also a `status`). T4's test and code were written together, without a separate
  Red run. The guard's test-edit log also lists new archive tests changed during their own
  Red and Green: `test_archive_settings.py` (a test path off `/tmp` for the linter),
  `test_csv_archive.py` (an added PC13 test) and `test_archive_totals_api.py`; none changes
  an expectation of this spec. Audited 2026-11-13: AC1–AC43 covered, all checks green.
  After the audit the user chose the app's wording "tarkistamaton" over "tarkastamaton"
  (PC14, AC34 and the `unreviewed_receipts` message; 2026-11-13). A full audit
  (2026-11-13) checked each AC's assertions and added tests, without changing an existing
  expectation: AC28 and AC19 through the API, AC18 lines deleted, AC31 `not_found`, AC13
  unreadable archive folder and failed name update, AC42 log counts on a failed move, AC36
  delete cancel and double click, AC37 load and delete errors, AC39 no receipt list, and
  axe on the archived list, an open confirmation and the AC41 page. Coverage: backend 99 %,
  `app/archive/service.py` 99 %; frontend 98 %.
- **Depends on:** [Receipt import](receipt-import.md), [Receipt review](receipt-review.md),
  [Receipt deletion and manual receipts](receipt-management.md), [Category totals](totals.md),
  [CSV export](csv-export.md), [PDF export](pdf-export.md), [Monthly budget](budget.md),
  [Finnish dates in the CSV files](finnish-csv-dates.md)
- **Implements:** PRD FR-40, FR-41, FR-42 and FR-53 (new); FR-32 for the archive folder;
  NFR-1, NFR-3, NFR-6, NFR-7, NFR-15 for archiving.
- **Affected subsystems:** new **archive** subsystem,
  [storage](../../docs/subsystems/storage/README.md),
  [import](../../docs/subsystems/import/README.md) (duplicate check),
  [review](../../docs/subsystems/review/README.md) (duplicate check of a manual receipt's
  image), [totals](../../docs/subsystems/totals/README.md),
  [budget](../../docs/subsystems/budget/README.md),
  [export](../../docs/subsystems/export/README.md), [ui](../../docs/subsystems/ui/README.md)

## Problem Statement
All receipts ever imported stay in the active tables. Over the years the receipt list grows,
and the active data holds years the user no longer edits. The user wants a smaller active
dataset, but still wants to look at an old year and compare years by their totals.

## Current Behavior
- Receipts and their lines live in `receipts` and `receipt_lines`. A line refers to its
  category and product by id ([datamodel](../../docs/datamodel.md#receipt_lines)).
- Every receipt appears in the receipt list, the totals, the budget comparison and the
  exports when its purchase date is in the chosen period
  ([totals](../../docs/subsystems/totals/README.md),
  [export](../../docs/subsystems/export/README.md)).
- An image's SHA-256 (`receipts.image_hash`) is the duplicate lookup for import (FR-3) and for
  a manual receipt's image (FR-47) ([import](../../docs/subsystems/import/README.md)).
- Imported images stay in the done folder. The app never deletes image files.
- Changing a product's category moves its saved lines (FR-36); a category used by a line
  cannot be deleted (FR-37).
- The database is backed up and restored with `scripts/backup-db.ps1` and
  `scripts/restore-db.ps1` ([development](../../docs/development.md)).
- There is no archive.

## Proposed Change

### Concepts

- An **archived year** (arkistoitu vuosi) is a calendar year whose receipts were moved to the
  archive tables. It is read-only.
- A **finished year** is a year before the current year in Finnish time (`Europe/Helsinki`).
- An **archive candidate** is a finished year that has at least one receipt in active data
  with a purchase date in that year.

### Parts

- **PC1 Archive tables (FR-40).** A new migration `0008_archive.sql` adds
  `archived_receipts` and `archived_lines` to the same database. An archived receipt keeps
  store, purchase date, total, review state (always reviewed), import time, image hash and
  file name, and records the archiving time. An archived line keeps position, name, amount
  and the deposit refund mark, and stores its product, category and group **as names**
  (text). The product name is the display name of the line's linked product, or the line's
  own name when it has no product. Category and group are `NULL` when the line has none.
  Archived rows have no foreign keys to `categories`, `products` or the active receipts.
  OCR text, category source and product link are not archived.
- **PC2 Archive a year (FR-40).** `POST /api/archive/{year}` moves all active receipts with a
  purchase date in `year`, and their lines, to the archive tables in one transaction, and
  answers 200 with the counts (PC4). Category and group names are copied as they are at that
  moment. Products, categories, remembered categories and budgets are not changed.
  Receipts without a purchase date are never archived. Archiving a year that already has
  archived receipts adds the new ones to it.
- **PC3 Refusals.** The year is checked before anything changes, in this order:
  1. `year` not a four-digit year 2000–9999: 422 `invalid_year`.
  2. Not a finished year: 409 `year_not_finished`.
  3. An import is running: 409 `import_running`.
  4. No active receipt has a purchase date in the year: 404 `nothing_to_archive`.
  5. One or more of them are unreviewed: 409 `unreviewed_receipts`, with the count in
     `count` at the top level of the error body, as `category_count` of `category_in_use`.

  On a refusal no row and no file changes.
- **PC4 Images (FR-40, NFR-7).** After the commit, each archived receipt's image moves from
  the done folder to the archive folder. The name there is chosen as in import (the same
  name, or the first free numbered suffix), and the archived row's `file_name` is updated to
  it. A missing file or a failed move leaves the file where it is and is reported; the data
  stays archived. A receipt without an image has nothing to move. The answer is
  `{"year": 2025, "receipts": 12, "lines": 140, "images_moved": 11, "images_not_moved":
  ["IMG_0007.jpg"]}`.
- **PC5 Archive folder setting (FR-32).** The archive folder is `/data/archived` in the
  backend container, mounted from `RRMC_ARCHIVE_DIR` (default `./source/archived`), as the
  other folders. It is in `.env.example`, `compose.yaml` and the folder check of the backend
  start. It lies under the real-data folder that `.gitignore` already ignores, and test
  containers do not mount it.
- **PC6 Archived image is a duplicate (FR-42).** Import (FR-3) and a manual receipt's image
  (FR-47) treat an image whose hash is in `archived_receipts` as a duplicate, exactly as an
  active one: the import run lists it under duplicates, and `POST /api/receipts` answers 409
  `duplicate_image`.
- **PC7 Archive overview.** `GET /api/archive` answers 200 with
  `{"archived": [{"year": 2025, "receipts": 12, "lines": 140, "images": 11}],
  "candidates": [{"year": 2024, "receipts": 3, "lines": 20, "images": 3,
  "unreviewed": 1}]}`, both sorted by year descending. `images` counts receipts with an
  image.
- **PC8 Permanent delete (FR-41).** `DELETE /api/archive/{year}` deletes every archived
  receipt and line of the year in one transaction and answers 200 with
  `{"year": 2025, "receipts": 12, "lines": 140}`. Image files are not touched. A year with no
  archived receipts gives 404 `not_found`; a bad year gives 422 `invalid_year`. After the
  delete, the year's images are no longer duplicates.
- **PC9 Archived data stays out of active views (FR-42).** The receipt list, receipt
  endpoints, totals, budget comparison and all exports of active data read only the active
  tables. An archived receipt's old id gives 404 `not_found` in `/api/receipts/{id}`.
- **PC10 Period warning (FR-42).** `GET /api/totals` and `GET /api/budget/comparison` add
  `archived_years`: the archived years that overlap the period's dates, ascending
  (`[]` when none). The Yhteenveto and Vertailu pages show
  `Arkistoitu vuosi 2025 ei ole mukana.` (several years: `Arkistoidut vuodet 2024, 2025 eivät
  ole mukana.`) with the other period notes. The totals PDF and the comparison PDF print the
  same sentence in their notes. CSV files do not change.
- **PC11 Archived year totals (FR-53).** `GET /api/archive/{year}/totals` answers 200 with
  12 month columns (`2025-01` … `2025-12`) and a year column, and a three-level tree of
  rows built from the stored names:
  - a **group** row sums its categories;
  - a **category** row (in a group, or at the top without a group) sums its products;
  - a **product** row sums the lines with that product name in that category.

  Lines without a category form a top-level `Ei kategoriaa` row with their product rows.
  At each level rows are sorted by name (Finnish case-insensitive order); a category
  without a group sorts among the groups, and `Ei kategoriaa` is last. Deposit refunds are
  left out (FR-44). Rows without lines are left out. A grand total row sums the columns.
  Unknown year: 404 `not_found`.
- **PC12 No receipt view.** Archived receipts are not listed or shown one by one, and their
  images are not served. The receipt rows stay in the archive only for the year, the counts
  and the duplicate check (PC6).
- **PC13 Archived totals export (FR-53).** `GET /api/export/archive/{year}` gives one CSV file
  `arkisto_2025.csv`, for Finnish Excel as in FR-26 (`;`, UTF-8 with BOM, CRLF, decimal
  comma, `dd.mm.yyyy`), with the columns Jakso, Alkaa, Päättyy, Ryhmä, Kategoria, Tuote,
  Summa. It is in long format with one row per product: first the month rows (Jakso
  `2025-01`, Alkaa `01.01.2025`, Päättyy `31.01.2025`) of every product with lines in that
  month, then the whole-year rows (Jakso `2025`, Alkaa `01.01.2025`, Päättyy `31.12.2025`).
  Inside a period the rows follow the order of PC11. There are no rows for group or category
  sums; Excel sums them from the product rows, as in the totals CSV. Ryhmä is empty for a
  category without a group; Kategoria is `Ei kategoriaa` for lines without one. Unknown
  year: 404 `not_found`.
- **PC14 Arkisto page (UI).** A new navigation item `Arkisto` opens `/arkisto`:
  - **Archive a year:** a list of candidates with their counts. A candidate with unreviewed
    receipts shows `Tarkistamattomia kuitteja: N` and has no archive button. Otherwise
    `Arkistoi` opens a confirmation in place: `Arkistoidaan vuosi 2025: 12 kuittia, 140
    riviä ja 11 kuvaa. Arkistointia ei voi perua. Ota varmuuskopio ennen arkistointia.` with
    `Arkistoi` and `Peruuta`. After success the page shows the counts and lists any image
    that was not moved with `Kuvaa ei voitu siirtää arkistokansioon: <name>`.
  - **Archived years:** a list of archived years with their counts, a link `Näytä` to the
    year page and `Poista pysyvästi`, which opens a confirmation: `Poistetaan vuoden 2025
    arkisto pysyvästi: 12 kuittia ja 140 riviä. Kuvat jäävät arkistokansioon. Poistoa ei voi
    perua. Ota varmuuskopio ennen poistoa.`
  - Buttons are disabled while their request runs. A failed request shows the backend's
    `message` with `role="alert"`.
- **PC15 Archived year page (UI).** `/arkisto/2025` shows the year totals (PC11) as a table
  with the 12 month columns and a `Vuosi` column, and a `Vie CSV` button (PC13). Groups and
  categories can be expanded and collapsed; on opening, groups show their categories and
  categories hide their products. Nothing on the page can be edited. An address of a year
  that is not archived shows `Vuotta 2023 ei ole arkistossa.` The table has about 13 amount
  columns, wider than `main` (1200 px), so:
  - its box spans the window, as the Vertailu week table (`table-box-wide`), and the table
    scrolls sideways inside the box when the window is narrower than the table;
  - the name column stays in place (sticky) while the amounts scroll;
  - a name wraps at 250 px, so a long product name does not widen the table.

### Agent decisions for review

These are not in the research notes. Accept or change them when approving the spec.

1. **Archived again adds:** a receipt dated in an archived year (typed in or imported later)
   stays active, the period warning applies, and archiving the year again adds it (PC2).
2. **No OCR text in the archive** (PC1): it is the largest column and the archive is not
   re-read. Re-parsing an archived receipt is impossible.
3. **Archived year totals sort groups and categories by name** (PC11): the archive has no
   catalog order.
4. **Archive export is one CSV of product totals** (PC13); no PDF and no lines CSV of the
   archive.
5. **Archiving is refused while an import runs** (PC3), so the done folder does not change
   under the image moves.
6. **Product name** (PC1): the linked product's display name, or the line's own name when
   the line has no product (for example a line without a category). Lines with the same
   name in the same category form one product row.
7. **Expand and collapse** on the year page (PC15): with products, the table of a year can
   have hundreds of rows, so products are hidden until their category is opened.

### Out of Scope
- Undoing an archiving (a backup is the safety net).
- Automatic archiving, archiving a part of a year, or the current year.
- Editing archived data, or applying later category changes (FR-36, FR-37) to it.
- Weekly totals, budget comparison and a side-by-side comparison of archived years.
- Deleting image files; the user deletes them from the archive folder by hand.
- Viewing archived receipts one by one, their lines or images (PC12).
- Weekly or product-level totals of active data; products appear only in the archive totals.
  The same year view (months, year, groups, categories and products) for active data is a
  later feature with its own spec (PRD release candidates).
- A PDF or a lines CSV of an archived year.
- Moving an image that was not moved; the user moves it by hand.

## Acceptance Criteria

### AC1: Archiving moves a year's receipts and lines
**Given** active receipts A (2025-03-10, 2 lines, reviewed), B (2025-12-31, 1 line,
reviewed), C (2026-01-01, reviewed) and D (no purchase date), today 2026-11-13
**When** the client sends `POST /api/archive/2025`
**Then** the answer is 200 with `receipts` 2 and `lines` 3; `archived_receipts` holds A and B,
`archived_lines` holds their 3 lines in their positions; `receipts` holds only C and D

### AC2: Categories are stored as names
**Given** a reviewed 2025 receipt with line 1 in category `Maito` of group `Maitotuotteet`,
line 2 in `Kahvi` without a group, line 3 without a category, and line 4 a deposit refund of
−40 cents
**When** the year 2025 is archived
**Then** the archived lines have (group, category) `("Maitotuotteet", "Maito")`,
`(NULL, "Kahvi")`, `(NULL, NULL)` and `(NULL, NULL)` with `is_deposit_refund` 1 and amount −40;
each keeps a product name (AC28)

### AC3: Later catalog changes do not touch the archive
**Given** the archive of AC2
**When** the user renames `Maito` to `Maidot`, moves its product to `Kahvi` (FR-36) and then
deletes `Maito` (FR-37, now unused)
**Then** the archived line 1 still has `("Maitotuotteet", "Maito")`, and the delete succeeds
(the archived line does not count as use)

### AC4: Catalog and budget are unchanged by archiving
**Given** products, categories and budgets, and a reviewed 2025 receipt whose line is linked
to product `Maito 1l`
**When** the year 2025 is archived
**Then** the `categories`, `products` and `budgets` tables are exactly as before

### AC5: Current and future years are refused
**Given** today is 2026-11-13 (Finnish time) and receipts in 2026 and 2027
**When** the client sends `POST /api/archive/2026` and `POST /api/archive/2027`
**Then** both answer 409 `year_not_finished`, and no row changes

### AC6: Finnish time decides the current year
**Given** the clock is 2025-12-31T22:30:00Z (2026-01-01 00:30 in Finland) and a reviewed 2025
receipt
**When** the client sends `POST /api/archive/2025`
**Then** the answer is 200

### AC7: An unreviewed receipt blocks archiving
**Given** three 2025 receipts, two of them unreviewed
**When** the client sends `POST /api/archive/2025`
**Then** the answer is 409 `unreviewed_receipts` with `"count": 2` at the top level of the body, and no row changes

### AC8: Nothing to archive
**Given** no active receipt dated in 2024 (an undated receipt exists)
**When** the client sends `POST /api/archive/2024`
**Then** the answer is 404 `nothing_to_archive`

### AC9: Bad year
**Given** any state
**When** the client sends `POST /api/archive/abcd`, `/api/archive/1999` and `DELETE
/api/archive/10000`
**Then** each answers 422 `invalid_year`

### AC10: Refused while an import runs
**Given** an import run is in progress and a reviewed 2025 receipt
**When** the client sends `POST /api/archive/2025`
**Then** the answer is 409 `import_running`, and no row changes

### AC11: Archiving again adds to the year
**Given** the year 2025 is archived with 2 receipts, and later a reviewed manual receipt dated
2025-06-01 is created
**When** the client sends `POST /api/archive/2025`
**Then** the answer has `receipts` 1, and `GET /api/archive` shows 2025 with `receipts` 3

### AC12: Images move after the commit
**Given** reviewed 2025 receipts with images `a.jpg` and `b.jpg` in the done folder, and the
archive folder holds a file `a.jpg`
**When** the year 2025 is archived
**Then** the answer has `images_moved` 2 and `images_not_moved` `[]`; the archive folder holds
`a.jpg`, `a (2).jpg` and `b.jpg`; the done folder no longer holds them; the archived
receipts' `file_name` are `a (2).jpg` and `b.jpg`

### AC13: A failed move keeps the data archived
**Given** reviewed 2025 receipts with images `a.jpg` (move fails) and `c.jpg` (file missing
from the done folder), and a manual receipt without an image
**When** the year 2025 is archived
**Then** the answer is 200 with `receipts` 3, `images_moved` 0 and `images_not_moved`
`["a.jpg", "c.jpg"]`; `a.jpg` is still in the done folder; all 3 receipts are archived

### AC14: A database error moves no image
**Given** reviewed 2025 receipts with images, and the archive transaction fails
**When** the year 2025 is archived
**Then** the answer is 500, the active tables are unchanged, the archive tables are empty,
and every image is still in the done folder

### AC15: An archived image is a duplicate for import
**Given** the year 2025 is archived with image `a.jpg`, and the same bytes are copied to the
import folder as `x.jpg`
**When** an import runs
**Then** the run lists `x.jpg` under duplicates, and no receipt is created

### AC16: An archived image is a duplicate for a manual receipt
**Given** the same bytes as an archived image are in the failed folder as `y.jpg`
**When** the client sends `POST /api/receipts` with `image_file_name` `y.jpg`
**Then** the answer is 409 `duplicate_image`, and `y.jpg` is still in the failed folder

### AC17: Archive overview
**Given** 2025 archived (12 receipts, 140 lines, 11 with an image), active receipts in 2024
(3, of which 1 unreviewed, 20 lines, 3 images) and 2026, today 2026-11-13
**When** the client sends `GET /api/archive`
**Then** the answer is `{"archived": [{"year": 2025, "receipts": 12, "lines": 140,
"images": 11}], "candidates": [{"year": 2024, "receipts": 3, "lines": 20, "images": 3,
"unreviewed": 1}]}`

### AC18: Permanent delete
**Given** 2025 archived with 12 receipts and 140 lines, and their images in the archive folder
**When** the client sends `DELETE /api/archive/2025`
**Then** the answer is `{"year": 2025, "receipts": 12, "lines": 140}`; the archive tables hold
no 2025 rows; every image file is still in the archive folder

### AC19: After permanent delete the image can be imported again
**Given** the delete of AC18, and an archived image's bytes copied to the import folder
**When** an import runs
**Then** the image is imported as a new receipt

### AC20: Permanent delete of an unknown year
**Given** no archived receipts in 2023
**When** the client sends `DELETE /api/archive/2023`
**Then** the answer is 404 `not_found`

### AC21: Archived data is not in active views
**Given** 2025 is archived, and a receipt that had id 5 before archiving
**When** the client reads `GET /api/receipts`, `GET /api/receipts/5`, `GET /api/totals` for
`2025-01`…`2025-12`, and `GET /api/export/lines` for the same period
**Then** the list has no 2025 receipt, receipt 5 gives 404 `not_found`, all totals are 0 with
no rows, and the lines file has only its header row

### AC22: Totals warn about an archived year
**Given** 2025 is archived
**When** the client reads `GET /api/totals` for the free range `2025-12-15`…`2026-01-14`, for
ISO week `2026-W01` (29.12.2025–4.1.2026), and for month `2026-02`
**Then** `archived_years` is `[2025]`, `[2025]` and `[]`; the Yhteenveto page shows
`Arkistoitu vuosi 2025 ei ole mukana.` for the first two

### AC23: Several archived years
**Given** 2024 and 2025 are archived
**When** the client reads `GET /api/totals` for `2024-12-01`…`2025-01-31`
**Then** `archived_years` is `[2024, 2025]`; the page shows
`Arkistoidut vuodet 2024, 2025 eivät ole mukana.`

### AC24: Budget comparison warns about an archived year
**Given** 2025 is archived
**When** the client reads `GET /api/budget/comparison` for the period 15.12.2025–14.1.2026
**Then** `archived_years` is `[2025]`; the Vertailu page shows
`Arkistoitu vuosi 2025 ei ole mukana.`

### AC25: PDF files carry the warning
**Given** 2025 is archived
**When** the user exports the totals PDF for `2025-12-15`…`2026-01-14` and the comparison PDF
for 15.12.2025–14.1.2026
**Then** both PDF files contain the text `Arkistoitu vuosi 2025 ei ole mukana.`; a PDF for
`2026-02` does not

### AC26: Archived year totals
**Given** 2025 archived with these lines (group / category / product, amount in cents):
2025-01-10 `Maitotuotteet`/`Maito`/`Maito 1l` 250; 2025-01-25 `Maitotuotteet`/`Maito`/`Maito 1l`
250; 2025-01-20 `Maitotuotteet`/`Juusto`/`Edam` 400; 2025-03-05 no group/`Kahvi`/`Kahvi 500g`
500; 2025-03-06 no category, product `TUNTEMATON` 100; 2025-03-06 a deposit refund −40
**When** the client sends `GET /api/archive/2025/totals`
**Then** the month columns are `2025-01`…`2025-12`, and the rows are, in this order:
- category `Kahvi`: March 500, year 500
  - product `Kahvi 500g`: March 500, year 500
- group `Maitotuotteet`: January 900, year 900
  - category `Juusto`: January 400, year 400; product `Edam`: January 400, year 400
  - category `Maito`: January 500, year 500; product `Maito 1l`: January 500, year 500
- `Ei kategoriaa`: March 100, year 100
  - product `TUNTEMATON`: March 100, year 100

Grand totals: January 900, March 600, year 1500, other months 0. The deposit refund is not
counted

### AC27: Totals of an unknown archived year
**Given** no archived 2023
**When** the client sends `GET /api/archive/2023/totals`
**Then** the answer is 404 `not_found`

### AC28: Product name comes from the linked product
**Given** a reviewed 2025 receipt with line `MAITO 1L VALIO` linked to product `Maito 1l`, and
line `TUNTEMATON` without a product
**When** the year 2025 is archived
**Then** the archived lines have the product names `Maito 1l` and `TUNTEMATON`

### AC29: Same product name in two categories
**Given** 2025 archived with a line of product name `Ale` in category `Kahvi` (100) and one
without a category (200)
**When** the client sends `GET /api/archive/2025/totals`
**Then** `Kahvi` has a product row `Ale` with year 100, and `Ei kategoriaa` has a product row
`Ale` with year 200

### AC30: Finnish name order
**Given** 2025 archived with categories without a group named `Öljyt`, `omenat`,
`Äyriäiset` and `Banaanit`, each with one line
**When** the client sends `GET /api/archive/2025/totals`
**Then** the top-level rows are in the order `Banaanit`, `omenat`, `Äyriäiset`, `Öljyt`

### AC31: Archived totals CSV
**Given** the archive of AC26
**When** the client sends `GET /api/export/archive/2025`
**Then** the file is `arkisto_2025.csv` (UTF-8 with BOM, `;`, CRLF as the other CSV files)
with the header row `Jakso;Alkaa;Päättyy;Ryhmä;Kategoria;Tuote;Summa` and then exactly these
rows:
```text
2025-01;01.01.2025;31.01.2025;Maitotuotteet;Juusto;Edam;4,00
2025-01;01.01.2025;31.01.2025;Maitotuotteet;Maito;Maito 1l;5,00
2025-03;01.03.2025;31.03.2025;;Kahvi;Kahvi 500g;5,00
2025-03;01.03.2025;31.03.2025;;Ei kategoriaa;TUNTEMATON;1,00
2025;01.01.2025;31.12.2025;;Kahvi;Kahvi 500g;5,00
2025;01.01.2025;31.12.2025;Maitotuotteet;Juusto;Edam;4,00
2025;01.01.2025;31.12.2025;Maitotuotteet;Maito;Maito 1l;5,00
2025;01.01.2025;31.12.2025;;Ei kategoriaa;TUNTEMATON;1,00
```
`GET /api/export/archive/2023` for a year not archived answers 404 `not_found`

### AC32: Archive folder setting
**Given** `RRMC_ARCHIVE_DIR` is unset
**When** Compose starts the backend
**Then** `./source/archived` is mounted at `/data/archived`; `.env.example` documents
`RRMC_ARCHIVE_DIR=./source/archived`; the backend-test and e2e services do not mount it

### AC33: Arkisto page archives a year
**Given** candidate 2025 with 12 receipts, 140 lines and 11 images, all reviewed
**When** the user opens `Arkisto`, clicks `Arkistoi` for 2025, reads the confirmation and
clicks `Arkistoi`
**Then** the confirmation shows `Arkistoidaan vuosi 2025: 12 kuittia, 140 riviä ja 11 kuvaa.
Arkistointia ei voi perua. Ota varmuuskopio ennen arkistointia.`; after success 2025 is in
the archived list and not in the candidates

### AC34: Arkisto page blocks a year with unreviewed receipts
**Given** candidate 2024 with 1 unreviewed receipt
**When** the user opens `Arkisto`
**Then** 2024 shows `Tarkistamattomia kuitteja: 1` and has no `Arkistoi` button

### AC35: Arkisto page reports images that were not moved
**Given** archiving 2025 answers `images_not_moved: ["a.jpg"]`
**When** the archiving finishes
**Then** the page shows `Kuvaa ei voitu siirtää arkistokansioon: a.jpg`

### AC36: Cancel and double click
**Given** the archive or delete confirmation is open
**When** the user clicks `Peruuta`, or clicks the confirming button twice quickly
**Then** `Peruuta` sends nothing; a double click sends one request, the button being
disabled until the answer

### AC37: Failed request on the Arkisto page
**Given** the backend answers 409 `unreviewed_receipts` (the data changed after loading)
**When** the user confirms archiving
**Then** the page shows the backend's `message` with `role="alert"`, and the lists reload

### AC38: Arkisto page deletes an archived year
**Given** archived 2025 with 12 receipts and 140 lines
**When** the user clicks `Poista pysyvästi` and confirms
**Then** the confirmation showed `Poistetaan vuoden 2025 arkisto pysyvästi: 12 kuittia ja
140 riviä. Kuvat jäävät arkistokansioon. Poistoa ei voi perua. Ota varmuuskopio ennen
poistoa.`; after success 2025 is not in the archived list

### AC39: Archived year page
**Given** the archive of AC26
**When** the user clicks `Näytä` for 2025
**Then** `/arkisto/2025` shows the totals table with 12 month columns and `Vuosi`, and a
`Vie CSV` button that downloads `arkisto_2025.csv`; no input, select or edit button is on
the page, and there is no receipt list

### AC40: Expand and collapse
**Given** the year page of AC39 just opened
**When** the user looks at the table, then opens category `Maito`, then closes group
`Maitotuotteet`
**Then** at first `Juusto` and `Maito` are shown but `Maito 1l` is not; after opening `Maito`
the row `Maito 1l` (5,00 € in January) is shown; after closing `Maitotuotteet` none of its
categories or products are shown. Each toggle is a button with `aria-expanded`

### AC43: Wide year table
**Given** the year page of AC39 with a product named with 100 characters, opened, in a window
1000 px wide
**When** the user scrolls the table box sideways to `2025-12`
**Then** the page itself has no horizontal scroll bar, the name column stays visible, the
table box is wider than `main` in a 1600 px window, and the long name wraps within 250 px

### AC41: Year not in the archive
**Given** no archived 2023
**When** the user opens `/arkisto/2023`
**Then** the page shows `Vuotta 2023 ei ole arkistossa.`

### AC42: Accessibility and privacy
**Given** the Arkisto page and the archived year page
**When** axe runs on them, and archiving runs with logging at `DEBUG`
**Then** axe finds no WCAG 2.1 AA violation, and the log has no store, product or file name
(only the year and counts)

## Files to Modify
| File | Change |
|---|---|
| `backend/app/storage/migrations/0008_archive.sql` | New tables `archived_receipts`, `archived_lines` (PC1) |
| `backend/app/storage/archive_repository.py` | New: SQL of archiving, overview, delete, archived reads |
| `backend/app/storage/receipt_repository.py` | Duplicate lookup also in the archive; overlapping archived years |
| `backend/app/archive/` | New subsystem: service, routes, schemas, errors (PC2–PC4, PC7, PC8, PC11) |
| `backend/app/receipt_import/run.py`, `backend/app/review/service.py` | Archived hash is a duplicate (PC6) |
| `backend/app/receipt_import/files.py` | Reuse the free-name rule for the archive folder |
| `backend/app/totals/`, `backend/app/budget/` | `archived_years` in the answers (PC10) |
| `backend/app/export/` | Archive CSV route and exporter method; PDF notes (PC10, PC13) |
| `backend/app/settings.py`, `backend/app/main.py`, `backend/app/texts.py` | Archive folder, router, messages |
| `compose.yaml`, `.env.example` | `RRMC_ARCHIVE_DIR` mount; the e2e backend creates `/data/archived` (PC5). `.gitignore` needs no change |
| `backend/app/local_time.py`, `backend/app/export/routes.py` | Shared Finnish time zone and today (P1) |
| `backend/app/calculation/archive_totals.py`, `backend/app/calculation/names.py` | Year totals tree and Finnish name order (PC11) |
| `backend/app/health/service.py` | Folder check includes the archive folder (PC5) |
| `scripts/container-tests.ps1` | Test settings get their own archive folder; AC32 checks the backend's archive mount |
| `frontend/src/navigation.ts` | `Arkisto` pages and paths |
| `frontend/src/api/archive.ts` | New API client |
| `frontend/src/components/ArchivePage.tsx`, `ArchiveYearPage.tsx` | New pages (PC14, PC15) |
| `frontend/src/components/` totals and comparison pages, `frontend/src/i18n/` | Period warning, texts |
| `frontend/e2e/` | Archive journeys |
| `docs/subsystems/archive/README.md` | New Tier 2 doc |
| `docs/datamodel.md`, `docs/api-reference.md`, `docs/architecture.md`, `docs/glossary.md`, `docs/development.md`, `docs/content-plan.md` | New tables, endpoints, subsystem, terms, folder |
| `docs/subsystems/{import,review,totals,budget,export,ui,storage}/README.md` | Duplicate check, warnings, export, pages |
| `docs/adr/0007-archive-tables.md` | Separate tables in the same database, categories as names |
| `specs/PRD.md`, `specs/README.md` | FR-40–FR-42, FR-53 (done); spec row 21 |

## Risk
- **What could break:** archiving deletes active rows; a bug could lose data or archive the
  wrong year. Image moves could leave files in the wrong folder. Duplicate detection could
  miss archived hashes and let an archived receipt be imported twice. Totals could change if
  the warning query interferes.
- **Rollback:** before archiving the UI asks the user to take a backup
  (`scripts/backup-db.ps1`); `scripts/restore-db.ps1` restores it, and images are moved back
  by hand. The migration only adds tables, so older code ignores them.
- **Dependencies:** none new. No Tesseract or Ollama calls.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC5, AC6 | `finished_year` check | current, future, past, around midnight | clock values | check | refused / allowed | clock |
| AC9 | `parse_year` | `abcd`, `1999`, `10000`, `2025` | strings | parse | `invalid_year` / 2025 | none |
| AC26 | `archive_totals` | groups, categories, products, no category, deposit refund | lines with names | compute | tree, order and sums of AC26 | none |
| AC29 | `archive_totals` | same product name in two categories | AC29 lines | compute | two product rows | none |
| AC30 | `archive_totals` | Finnish order | AC30 names | compute | `Banaanit`, `omenat`, `Äyriäiset`, `Öljyt` | none |
| AC31 | CSV exporter `archive_totals_file` | month and year blocks | AC26 totals | export | rows and name of AC31 | none |
| AC22, AC23 | `archived_years_text` | 1 and 2 years | years | format | the two sentences | none |
| AC12 | free name in archive folder | taken name | `a.jpg` exists | choose | `a (2).jpg` | file ops fake |

### Integration tests
Real SQLite (temporary file) and real FastAPI app; files in a temporary folder.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | archive year | `POST /api/archive/2025` | counts, rows moved | 200 |
| AC2 | names stored | archive | archived line names | 200 |
| AC3 | catalog change after | rename, FR-36, delete | archive unchanged; delete succeeds | 200/204 |
| AC4 | catalog untouched | archive | tables equal | 200 |
| AC5 | current/future year | `POST /api/archive/2026`, `/2027` | `year_not_finished` | 409 |
| AC6 | Finnish midnight | clock 2025-12-31T22:30Z | archived | 200 |
| AC7 | unreviewed | 2 unreviewed | `unreviewed_receipts`, count 2 | 409 |
| AC8 | nothing | no 2024 receipts | `nothing_to_archive` | 404 |
| AC9 | bad year | `abcd`, `1999`, `10000` | `invalid_year` | 422 |
| AC10 | import running | blocked import service | `import_running` | 409 |
| AC11 | archive again | second archive | adds 1 | 200 |
| AC12 | image moves | done folder files | names and folders | 200 |
| AC13 | failed and missing move | failing move fake | `images_not_moved` | 200 |
| AC14 | DB failure | failing insert | nothing changed, no move | 500 |
| AC15 | import duplicate | archived bytes | listed as duplicate | 200 |
| AC16 | manual receipt duplicate | `POST /api/receipts` | `duplicate_image` | 409 |
| AC17 | overview | `GET /api/archive` | exact body | 200 |
| AC18 | delete | `DELETE /api/archive/2025` | counts; files kept | 200 |
| AC19 | reimport after delete | import | imported | 200 |
| AC20 | delete unknown | `DELETE /api/archive/2023` | `not_found` | 404 |
| AC21 | active views | list, receipt, totals, lines CSV | no 2025 data | 200/404 |
| AC22, AC23 | totals warning | `GET /api/totals` | `archived_years` | 200 |
| AC24 | comparison warning | `GET /api/budget/comparison` | `archived_years` | 200 |
| AC25 | PDF notes | totals and comparison PDF | text present / absent | 200 |
| AC26, AC27 | year totals | `GET /api/archive/{year}/totals` | rows; unknown 404 | 200/404 |
| AC28 | product names | archive linked and unlinked lines | `Maito 1l`, `TUNTEMATON` | 200 |
| AC31 | CSV | `GET /api/export/archive/2025` | file of AC31; unknown 404 | 200/404 |
| AC32 | Compose | `scripts/container-tests.ps1` checks mount and test isolation | mount present, absent in test services | — |
| AC42 | log privacy | archive at DEBUG | no names in log | 200 |

Frontend component tests (Vitest) cover AC33–AC41 and AC43's wrapping class with a mocked API: texts, disabled
buttons, cancel, alerts, the read-only year page, expand and collapse, and the
`/arkisto/2023` message, and AC22–AC24 on
the Yhteenveto and Vertailu pages.

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC33, AC39, AC40 | Archive and view a year | seed a reviewed receipt dated last year; open Arkisto; archive; open the year; open a category | the year in archived list; totals shown read-only; product row shown |
| AC34 | Blocked year | seed an unreviewed receipt dated last year | no `Arkistoi`; count shown |
| AC38 | Permanent delete | archive then delete | the year is gone |
| AC22 | Warning on Yhteenveto | after archiving, choose a range over the year boundary | warning shown |
| AC42 | Accessibility | axe on the two pages | no violations |
| AC43 | Wide year table | open the year page at 1000 px and 1600 px wide; scroll the box | no page scroll; name column visible; box wider than `main`; long name wraps |

### Coverage target
- Backend: 90 % lines for the archive subsystem; every branch of the refusals (PC3), the image
  moves (PC4), the duplicate check (PC6) and the archive totals (PC11).
- Frontend: every new component has tests for each AC it shows.

### Test data
- Synthetic fixtures only: made-up stores (`Kauppa`), products (`Maito 1l`), categories and
  small generated JPEG and PNG files. No real receipts.
- Mocks: clock (Finnish time), file operations (failing move), import service state.

## Related Documentation (MANDATORY)
- Tier 1: [PRD](../PRD.md#610-archiving-later-release), [datamodel](../../docs/datamodel.md),
  [architecture](../../docs/architecture.md), [API reference](../../docs/api-reference.md),
  [development](../../docs/development.md), [security](../../docs/security.md),
  [glossary](../../docs/glossary.md)
- Tier 2: [storage](../../docs/subsystems/storage/README.md),
  [import](../../docs/subsystems/import/README.md),
  [review](../../docs/subsystems/review/README.md),
  [totals](../../docs/subsystems/totals/README.md),
  [budget](../../docs/subsystems/budget/README.md),
  [export](../../docs/subsystems/export/README.md), [ui](../../docs/subsystems/ui/README.md)
- ADRs: [0001 tech stack](../../docs/adr/0001-tech-stack.md),
  [0002 Docker](../../docs/adr/0002-docker.md); new 0007 (P8)

## Plan

### P1 Components

| Part | Where | Role |
|---|---|---|
| Migration | `backend/app/storage/migrations/0008_archive.sql` | The two archive tables (P2) |
| Repository | `backend/app/storage/archive_repository.py` (new) | All archive SQL: candidates, copy and delete, overview, permanent delete, lines for totals, overlapping years |
| Duplicate lookup | `ReceiptRepository.image_known(hash)` (new) | `EXISTS` in `receipts` or `archived_receipts`; replaces `get_by_hash` in `receipt_import/run.py` and `review/service.py` (PC6) |
| Service | `backend/app/archive/service.py` (new) | Year checks, the transaction, image moves, overview, delete, year totals |
| Routes, schemas, errors | `backend/app/archive/routes.py`, `schemas.py`, `errors.py` (new) | `/api/archive` endpoints (P4) |
| Calculation | `backend/app/calculation/archive_totals.py` (new) | Pure function: lines with names → three-level tree, month and year sums (PC11) |
| Name order | `backend/app/calculation/names.py` (new) `finnish_key` | Case-insensitive key with `å`, `ä`, `ö` after `z` (AC30) |
| Local time | `backend/app/local_time.py` (new) | `LOCAL_TIME` and `local_today(clock)`, moved from `export/routes.py` and shared with archive |
| Export | `CsvExporter.archive_totals_file`, `ExportService.archive_file`, route `GET /api/export/archive/{year}` | PC13 |
| Warnings | `TotalsView`, the budget comparison view, `TotalsOut`, the comparison schema, `TotalsReport`, `ComparisonReport`, `pdf_exporter` notes, `texts.archived_years_note` | PC10 |
| Settings | `Settings.archive_dir` (`/data/archived`); the health folder check includes it | PC5 |
| Wiring | `main.py`: `create_archive_router(settings, import_service, clock, archive_files)` | `archive_files` lets tests fail a move (AC13) |
| UI | `navigation.ts` pages `archive` (`/arkisto`) and `archiveYear` (`/arkisto/<year>`); `api/archive.ts`; `ArchivePage.tsx`; `ArchiveYearPage.tsx` with `ArchiveTotalsTable.tsx`; the note on `TotalsPage` and `ComparisonPage`; texts in `i18n/fi.ts`; CSS for the sticky name column and wrapping | PC10, PC14, PC15 |

Dependency rules ([architecture](../../docs/architecture.md#dependency-rules)): `archive`
depends on `storage`, `calculation`, `image_files` and the import service's state.
`totals` and `budget` read archived data through `ArchiveRepository`, not through the
archive service. `export` uses archive's `parse_year` and `read_year_totals`, so the CSV
file is built from the same reader as the year page (changed 2026-11-13 from "nothing
depends on `archive`").

### P2 Data model (migration 0008)

```sql
CREATE TABLE archived_receipts (
    id            INTEGER PRIMARY KEY,   -- the active receipt's id, copied (P3)
    year          INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 9999),
    purchase_date TEXT NOT NULL
        CHECK (purchase_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    store         TEXT,
    total_cents   INTEGER,
    image_hash    TEXT UNIQUE CHECK (image_hash IS NULL OR length(image_hash) = 64),
    file_name     TEXT,                  -- name in the archive folder after the move
    imported_at   TEXT NOT NULL,
    archived_at   TEXT NOT NULL,         -- UTC ISO 8601 with seconds
    CHECK ((image_hash IS NULL) = (file_name IS NULL)),
    CHECK (CAST(substr(purchase_date, 1, 4) AS INTEGER) = year)
);
CREATE INDEX archived_receipts_year ON archived_receipts (year);

CREATE TABLE archived_lines (
    id                INTEGER PRIMARY KEY,  -- the active line's id, copied
    receipt_id        INTEGER NOT NULL REFERENCES archived_receipts (id) ON DELETE CASCADE,
    position          INTEGER NOT NULL CHECK (position >= 1),
    name              TEXT NOT NULL,
    product_name      TEXT NOT NULL,
    amount_cents      INTEGER NOT NULL,
    is_deposit_refund INTEGER NOT NULL CHECK (is_deposit_refund IN (0, 1)),
    category_name     TEXT,
    group_name        TEXT,
    UNIQUE (receipt_id, position),
    CHECK (group_name IS NULL OR category_name IS NOT NULL),
    CHECK (is_deposit_refund = 0 OR category_name IS NULL)
);
```

No column refers to the active tables, so archiving deletes no catalog row, and FR-36 and
FR-37 never see archived lines. The review state is not stored: every archived receipt was
reviewed (PC3).

### P3 Archiving flow (PC2–PC4)

1. Parse `year` (`^[0-9]{4}$`, 2000–9999) → `invalid_year`.
2. `year >= local_today(clock).year` → `year_not_finished`.
3. The import service's state is `running` → `import_running`.
4. In one `BEGIN IMMEDIATE` transaction:
   1. count the year's active receipts (`purchase_date BETWEEN 'YYYY-01-01' AND
      'YYYY-12-31'`): 0 gives `nothing_to_archive`; count the unreviewed: more than 0 gives
      `unreviewed_receipts` with the count. A refusal rolls back, and nothing has changed.
   2. `INSERT INTO archived_receipts SELECT ...` with the active ids and `archived_at`.
   3. `INSERT INTO archived_lines SELECT ...` joining the line's category (`c`), its group
      (`g` on `c.parent_id`) and its product (`p`): `product_name = COALESCE(p.name,
      l.name)`, `category_name = c.name`, `group_name = g.name`.
   4. `DELETE FROM receipts WHERE ...`; the lines go by `ON DELETE CASCADE`.
   5. Read this run's archived (id, file_name) pairs for step 5.
5. After the commit, for each pair with a file: choose `free_target_name` against the archive
   folder's names and move with `move_file`. On success remember the new name; on `OSError`
   or a missing source add the old name to `images_not_moved`. Then update the moved rows'
   `file_name` in one short transaction. An error there is logged (type only) and does not
   fail the answer, because the files are already moved.
6. Log `archive year=%d receipts=%d lines=%d moved=%d not_moved=%d`, without names (AC42).

Ids are copied because active ids are `AUTOINCREMENT` and never reused, so an id is unique
across both tables, and archiving again (AC11) cannot collide.

A race with an import that starts after step 3 is accepted: an import only adds new,
unreviewed receipts and moves other files into the done folder, so it cannot change what
this transaction archives.

### P4 API

| Method and path | Answer |
|---|---|
| `GET /api/archive` | 200 overview (PC7) |
| `POST /api/archive/{year}` | 200 result (PC4); 422 `invalid_year`; 409 `year_not_finished`, `import_running`, `unreviewed_receipts` (`count`); 404 `nothing_to_archive` |
| `DELETE /api/archive/{year}` | 200 counts (PC8); 422 `invalid_year`; 404 `not_found` |
| `GET /api/archive/{year}/totals` | 200 tree (PC11); 422 `invalid_year`; 404 `not_found` |
| `GET /api/export/archive/{year}` | 200 CSV (PC13); 422 `invalid_year`; 404 `not_found` |
| `GET /api/totals`, `GET /api/budget/comparison` | add `archived_years: number[]` |

`year` is a plain string path parameter, so a bad value reaches the service and gives
`invalid_year`, not FastAPI's generic error (as `parse_period` in totals P4).

The year totals body:

```json
{
  "year": 2025,
  "months": ["2025-01", "2025-02", "...", "2025-12"],
  "rows": [
    {"kind": "category", "name": "Kahvi", "months": [0, 0, 500, 0], "total": 500,
     "children": [{"kind": "product", "name": "Kahvi 500g", "months": [0, 0, 500, 0],
                   "total": 500, "children": []}]},
    {"kind": "group", "name": "Maitotuotteet", "months": [900, 0, 0, 0], "total": 900,
     "children": []},
    {"kind": "none", "name": null, "months": [0, 0, 100, 0], "total": 100, "children": []}
  ],
  "month_totals": [900, 0, 600, 0],
  "total": 1500
}
```

The example shortens `months` and leaves children out; the real lists have 12 entries and
every child row.

### P5 Period warning (PC10)

`ArchiveRepository.archived_years(first_year, last_year)` returns the distinct archived years
between the period's start and end years. The totals and budget services read it in their
existing transaction. `texts.archived_years_note(years)` gives the singular or the plural
sentence; the frontend has the same two texts in `fi.ts`. The PDF reports add the sentence
to their notes after the unreviewed and undated counts.

### P6 UI

- `ArchivePage` loads `GET /api/archive`, renders the two lists and the in-place
  confirmations (the `ConfirmDelete` pattern), disables the confirming button while its
  request runs, shows `images_not_moved` and backend messages, and reloads after every
  answer.
- `ArchiveYearPage` loads the year totals; a 404 shows `Vuotta 2023 ei ole arkistossa.`
  `ArchiveTotalsTable` renders the tree with toggle buttons (`aria-expanded`) per group and
  category, using the existing totals row classes. Its state is a set of opened keys
  (`group:Maitotuotteet`, `category:Maitotuotteet/Maito`); groups start open, categories
  closed.
- CSS: `table-box-wide` for the box; the first column `position: sticky; left: 0` with the
  page background. The 250 px limit is on the name's `span` (`display: inline-block`,
  `overflow-wrap: break-word`), because browsers do not apply `max-width` to table cells
  reliably, and amounts do not wrap; with `overflow-wrap: anywhere` on the cell the E2E
  run showed the table squeezing the names instead of scrolling (changed 2026-11-13).
- `Vie CSV` is a plain `download` link to `archiveCsvUrl(year)` in `api/archive.ts`
  (changed 2026-11-13: the archive client holds its own URL).

### P7 Tests and fakes

- The clock is injected into the archive service (AC5, AC6), and the import service's state
  comes through a fake (AC10).
- An `ArchiveFiles` protocol (`names_in`, `move`, `exists`) with a local implementation;
  tests pass a failing move (AC13).
- A failing transaction for AC14: a test-only trigger on `archived_lines` that raises, added
  through a throwaway migration as in earlier specs.
- E2E: `backend-e2e` creates `/data/archived` in its tmpfs. A reviewed receipt of last year
  is seeded through the existing manual receipt and review endpoints.

### P8 Documentation

A new `docs/subsystems/archive/README.md` and ADR 0007 (separate tables in the same
database, names instead of ids, copied ids); the other updates are listed in Files to
Modify.

### P9 Check against the ACs

| ACs | Covered by |
|---|---|
| AC1–AC4, AC11, AC28 | P2, P3 step 4 |
| AC5–AC10 | P3 steps 1–4 |
| AC12–AC14 | P3 step 5, P7 |
| AC15, AC16, AC19 | `image_known` (P1) |
| AC17, AC18, AC20 | P4, the archive repository |
| AC21 | active queries unchanged; the rows are deleted in P3 |
| AC22–AC25 | P5 |
| AC26, AC27, AC29, AC30 | `archive_totals`, `finnish_key` |
| AC31 | P1 export |
| AC32 | P1 settings, compose |
| AC33–AC43 | P6 |

## Tasks

Each task runs Red → Green → Refactor; the tests named are written first. Backend tasks end
with `pytest`, `ruff check`, `ruff format --check` and `pyright` green in `backend-test`;
frontend tasks with `npm test`, lint, format check and typecheck green in `frontend-test`.

- [x] **T1 Migration (P2; AC1, AC2, AC28).** `0008_archive.sql`. Integration tests on a
  temporary database: schema version 8; the `CHECK`s refuse a year that differs from the
  purchase date, an image hash without a file name, a group without a category and a
  deposit refund with a category; deleting an archived receipt deletes its lines; existing
  rows are unchanged by the migration.
- [x] **T2 Finnish name order (P1; AC30).** `finnish_key` in `app/calculation/names.py`. Unit
  tests: `Banaanit`, `omenat`, `Äyriäiset`, `Öljyt`; `å` before `ä` before `ö`, all after
  `z`; case-insensitive with a stable tie-break.
- [x] **T3 Year totals (P1, P4; AC26, AC29, AC30).** `archive_totals` in
  `app/calculation/archive_totals.py`. Unit tests: the tree, order and sums of AC26; deposit
  refunds left out; the same product name in two categories (AC29); a category without a
  group among the groups and `Ei kategoriaa` last; 12 month columns; empty input gives no
  rows.
- [x] **T4 Local time (P1; AC6).** Move `LOCAL_TIME` to `app/local_time.py` with
  `local_today(clock)`; `export/routes.py` uses it. Unit test: 2025-12-31T22:30:00Z gives
  2026-01-01. The existing PDF export tests stay green.
- [x] **T5 Archive repository (P1, P3 step 4; AC1–AC4, AC11, AC17, AC18, AC28).**
  `app/storage/archive_repository.py`: counts, copy and delete, overview, permanent delete,
  lines of a year, `archived_years`. Integration tests with real SQLite: the rows of AC1,
  the names of AC2 and AC28, catalog, products and budgets unchanged (AC4), archiving again
  (AC11), the overview of AC17, delete counts (AC18), `archived_years` for 2024–2026.
- [x] **T6 Duplicate lookup (P1; AC15, AC16, AC19).** `ReceiptRepository.image_known`; replace
  `get_by_hash` in `receipt_import/run.py` and `review/service.py`. Integration tests: an
  archived hash is a duplicate for an import run and for `POST /api/receipts` (409, file
  still in the failed folder); after a permanent delete the image imports again. The
  existing duplicate tests stay green.
- [x] **T7 Settings and folders (P1; AC32).** `Settings.archive_dir`; health folder check;
  `compose.yaml` mount `RRMC_ARCHIVE_DIR` on `backend` only; `backend-e2e` creates
  `/data/archived`; `.env.example`. Tests: settings unit test; health reports `folders`
  not ok without the archive folder; `scripts/container-tests.ps1` checks the mount in
  `backend` and its absence in the test services.
- [x] **T8 Archive service and routes (P3, P4; AC1, AC5–AC14, AC17, AC18, AC20, AC42).**
  `app/archive/` (service, routes, schemas, errors, `ArchiveFiles`); texts; wiring in
  `main.py`. Unit tests of `parse_year`. Integration tests: every row of the Integration
  tests table for these ACs, with a fixed clock, a fake import state, a failing move, a
  missing file, a test-only failing trigger (AC14) and a `DEBUG` log without names (AC42).
- [x] **T9 Year totals endpoint (P4; AC26, AC27).** `GET /api/archive/{year}/totals`.
  Integration tests: the body of AC26; 404 for 2023; 422 for `abcd`.
- [x] **T10 Archive CSV (P1; AC31).** `Exporter.archive_totals_file`,
  `CsvExporter.archive_totals_file`, `ExportService.archive_file`,
  `GET /api/export/archive/{year}`; the `FixedExporter` method in the export tests. Unit
  test: the exact file of AC31 with BOM and `\r\n`, and the file name. Integration tests:
  200 with the file; 404 for 2023; 422 for `abcd`.
- [x] **T11 Period warning (P5; AC21–AC25).** `archived_years` in the totals and budget views
  and schemas; `texts.archived_years_note`; PDF notes. Unit tests of the singular and plural
  sentence. Integration tests: AC21's active views; the periods of AC22–AC24; PDF text
  present for the boundary periods and absent for `2026-02` (AC25).
- [x] **T12 Frontend API and navigation (P6; AC39, AC41).** `api/archive.ts`; pages
  `archive` and `archiveYear` in `navigation.ts`; the `Arkisto` item in the header. Tests:
  the request URLs and parsing; `/arkisto` and `/arkisto/2025` give their pages, a bad year
  path gives the archive page.
- [x] **T13 Period warning in the UI (P5; AC22–AC24).** `TotalsPage` and `ComparisonPage`,
  texts in `fi.ts`. Tests: no note for `[]`, the singular and plural sentence.
- [x] **T14 Arkisto page (P6; AC33–AC38).** `ArchivePage.tsx`. Tests with a mocked API: the
  two lists; the confirmation texts of AC33 and AC38; no `Arkistoi` for a year with
  unreviewed receipts (AC34); `images_not_moved` (AC35); `Peruuta` sends nothing and a
  double click sends one request (AC36); an error message with `role="alert"` and a reload
  (AC37).
- [x] **T15 Year page and table (P6; AC39–AC41, AC43).** `ArchiveYearPage.tsx`,
  `ArchiveTotalsTable.tsx`, CSS. Tests: the 12 month columns and `Vuosi`; the CSV link;
  no input, select or edit button; groups open and categories closed; toggles with
  `aria-expanded` (AC40); the 404 text (AC41); the wide box, sticky and wrapping classes
  (AC43).
- [x] **T16 E2E (P7; AC22, AC33, AC34, AC38–AC40, AC42, AC43).** `frontend/e2e/archive.spec.ts`:
  the journeys of the E2E table, axe on both pages, and the 1000 px and 1600 px widths.
  Proof: `docker compose --profile e2e run --rm e2e` green, the existing journeys included.
- [x] **T17 Documentation (P8).** `docs/subsystems/archive/README.md`, ADR 0007, and the
  updates in Files to Modify (datamodel, API reference, architecture, glossary, development,
  content plan, subsystem READMEs); `specs/README.md` row 21. Proof: the `document` skill's
  doc scan finds no gap; the container and guard tests are green.
- [x] **T18 Audit.** `review-audit` skill: every AC has a passing test, all checks green, docs
  match the code. Then status Done.
