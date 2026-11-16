# Feature: Year with products

## Overview
- **Status:** Done
- **Created:** 2026-11-16
- **Updated:** 2026-11-16: research decisions by the user: the current year only, reviewed
  receipts only, Finnish name order as on the archived year page, a CSV export, the page
  name `Vuosi tuotteineen` between `Yhteenveto` and `Budjetti` in the navigation. Decided by
  the agent for review: see [Agent decisions for review](#agent-decisions-for-review). The
  user approved Specify with these decisions on 2026-11-16. Plan approved 2026-11-16; Tasks approved 2026-11-16. Implementation notes (2026-11-16), for the audit: the T1 tests
  are in the existing `tests/unit/storage/test_receipt_repository.py` (P6 allowed either);
  AC4 (Finnish new year) is tested through the endpoint in T3, because the year comes from
  the route's clock, not from `read_year_totals`; the test helper `frontend/src/test/year.ts`
  is new; `docs/architecture.md` also changed (the totals and export lines and the totals
  and export section). G7 record: existing tests changed for this spec, none after a red run
  of its own: `App.test.tsx` (the navigation list gets `Vuosi tuotteineen`, AC11) and
  `test_export_api.py` (`FixedExporter.year_totals_file`, the new `Exporter` method, P6); no
  expectation changed. The archive CSV tests passed unchanged before and after T4. The E2E
  run first failed on a stale Docker network of `rrmc-backend-e2e-1`; the user recreated
  the container (G2 blocked the agent), then all 45 E2E tests passed. Audited 2026-11-16:
  AC1–AC18 covered, all checks green.
- **Affected subsystems:** [calculation](../../docs/subsystems/calculation/README.md),
  [storage](../../docs/subsystems/storage/README.md),
  [export](../../docs/subsystems/export/README.md), [ui](../../docs/subsystems/ui/README.md),
  [archive](../../docs/subsystems/archive/README.md) (reused, not changed in behavior)

## Problem Statement
The user can see the totals of an archived year per month, group, category and product
(FR-53), but not those of the current year. The Yhteenveto page shows categories for a
chosen period, never products and never the whole year by month. To see what the money
went on this year, product by product, the user needs the same view for the current year.

## Current Behavior
- Yhteenveto (`GET /api/totals`) shows category and group totals per ISO week and month of a
  chosen period. It counts unreviewed receipts too and shows their count; it reads no
  product names ([totals](../../docs/subsystems/totals/README.md)).
- The archived year page `/arkisto/<year>` shows an archived year's totals per group,
  category and product with 12 month columns and a `Vuosi` column, and exports them as CSV
  ([archive](../../docs/subsystems/archive/README.md),
  [calculation](../../docs/subsystems/calculation/README.md#archived-year-totals)).
- No view shows the active data per product.

## Proposed Change
New requirement **FR-54** in the PRD (from the "Later (candidates)" list): *The user can view
the current calendar year on its own page: the totals of the whole year and of each month,
per group, category and product, counted from reviewed receipts. These totals can be
exported as CSV.*

- **PC1 Current year totals (FR-54).** `GET /api/year/totals` answers 200 with the totals of
  the current year in Finnish time (`Europe/Helsinki`), in the same shape as the archived
  year totals (archiving PC11): `year`, 12 month columns (`2026-01` … `2026-12`), a
  three-level tree of rows (group → category → product), the month totals and the year
  total. Rows follow the archive rules: a group sums its categories, a category (in a group,
  or at the top without one) sums its products, a product sums the lines with that product
  name in that category; lines without a category form a top-level `Ei kategoriaa` row,
  last; at each level rows are sorted by name in Finnish order; deposit refunds (FR-44) and
  rows without lines are left out. Totals are computed on each request, so an edit shows at
  once (FR-24).
- **PC2 What is counted.** Only lines of **reviewed** receipts whose purchase date is in the
  current year. Unreviewed receipts, receipts without a purchase date and receipts dated in
  another year are not counted.
- **PC3 Names.** Group and category names are the current catalog names. The product name
  is the linked product's current name, else the line's own name (the same rule as
  archiving, archiving AC28).
- **PC4 Unreviewed count.** The answer also has `unreviewed`: the number of unreviewed
  receipts dated in the current year. The page shows it when it is not 0:
  `Tarkistamattomia kuitteja: 3. Ne eivät ole mukana summissa.`
- **PC5 CSV export (FR-54).** `GET /api/export/year` gives one CSV file `vuosi_2026.csv` in
  the format of the archive CSV (archiving PC13): `;`, UTF-8 with BOM, CRLF, decimal comma,
  `dd.mm.yyyy`, the columns Jakso, Alkaa, Päättyy, Ryhmä, Kategoria, Tuote, Summa; first the
  month rows of every product with lines in that month, then the whole-year rows; inside a
  period the order of PC1. It is built from the same reader as `GET /api/year/totals`, so
  the file and the page agree.
- **PC6 Vuosi tuotteineen page (UI).** A new navigation item `Vuosi tuotteineen`, between
  `Yhteenveto` and `Budjetti`, opens `/vuosi`. The page has the heading
  `Vuosi tuotteineen 2026`, a `Vie CSV` button (PC5) and the totals table of the archived
  year page: 12 month columns and `Vuosi`, groups and categories expand and collapse (on
  opening, groups show their categories and categories hide their products), and the wide
  table rules of archiving PC15 (box spans the window, sticky name column, names wrap at
  250 px). Nothing on the page can be edited.
- **PC7 Empty year.** When the current year has no counted lines, the page shows
  `Vuodelta 2026 ei ole vielä tarkistettuja kuitteja.` instead of the table, without the
  `Vie CSV` button. The CSV endpoint then gives a file with the header row only.
- **PC8 Privacy (NFR-3).** Product, store and category names do not appear in logs or error
  messages.

### Agent decisions for review
1. The path is `/vuosi`; the heading adds the year: `Vuosi tuotteineen 2026`.
2. The unreviewed count is shown (PC4), so a missing receipt is not a surprise. It is a
   note, not a warning with `role="alert"`.
3. The CSV file name is `vuosi_2026.csv`.
4. An empty year shows a sentence instead of an empty table (PC7).
5. The endpoints are `GET /api/year/totals` and `GET /api/export/year` without a year
   parameter, because only the current year is shown. The current year can never be
   archived (FR-40), so no archived-year warning is needed.

### Out of Scope
- Other years than the current one, a year selector, or comparing years.
- Unreviewed receipts in the sums (they are only counted, PC4).
- ISO weeks, PDF export, budget figures and receipt lines on this page.
- Editing anything on the page; links from a product row to its receipts.
- Changes to the archived year page or the archive CSV.

## Acceptance Criteria

The examples use a clock at 2026-06-15 12:00 Finnish time unless an AC says otherwise.

### AC1: Current year totals
**Given** these lines of reviewed receipts (group / category / product, amount in cents):
2026-01-10 `Maitotuotteet`/`Maito`/`Maito 1l` 250; 2026-01-25 `Maitotuotteet`/`Maito`/`Maito 1l`
250; 2026-01-20 `Maitotuotteet`/`Juusto`/`Edam` 400; 2026-03-05 no group/`Kahvi`/`Kahvi 500g`
500; 2026-03-06 no category, line `TUNTEMATON` without a product 100; 2026-03-06 a deposit
refund −40
**When** the client sends `GET /api/year/totals`
**Then** `year` is 2026, the month columns are `2026-01`…`2026-12`, and the rows are, in
this order:
- category `Kahvi`: March 500, year 500
  - product `Kahvi 500g`: March 500, year 500
- group `Maitotuotteet`: January 900, year 900
  - category `Juusto`: January 400, year 400; product `Edam`: January 400, year 400
  - category `Maito`: January 500, year 500; product `Maito 1l`: January 500, year 500
- `Ei kategoriaa`: March 100, year 100
  - product `TUNTEMATON`: March 100, year 100

Month totals: January 900, March 600, other months 0; year total 1500; `unreviewed` 0. The
deposit refund is not counted

### AC2: Only reviewed receipts are counted
**Given** the lines of AC1, and an unreviewed receipt dated 2026-02-01 with a line
`Maitotuotteet`/`Maito`/`Maito 1l` 300, and another unreviewed receipt dated 2026-04-01
**When** the client sends `GET /api/year/totals`
**Then** the totals are exactly those of AC1 (February 0, year 1500) and `unreviewed` is 2

### AC3: Only the current year is counted
**Given** reviewed receipts dated 2025-12-31 (100), 2026-01-01 (200), 2026-12-31 (300) and
2027-01-01 (400), each with one line in category `Kahvi`, and a reviewed receipt without a
purchase date (500)
**When** the client sends `GET /api/year/totals`
**Then** `Kahvi` has January 200, December 300 and year 500; nothing else is counted

### AC4: Finnish time decides the current year
**Given** the clock at 2025-12-31 22:30 UTC (2026-01-01 00:30 in Finnish time) and reviewed
lines dated 2025-12-31 (100) and 2026-01-01 (200) in category `Kahvi`
**When** the client sends `GET /api/year/totals`
**Then** `year` is 2026 and `Kahvi` has year 200

### AC5: Current names are used
**Given** a reviewed 2026 line `MAITO 1L VALIO` linked to product `Maito 1l` in category
`Maito` (100), then the product is renamed `Maito 1 l` and the category `Maidot`
**When** the client sends `GET /api/year/totals`
**Then** the row is category `Maidot` with product `Maito 1 l`, year 100

### AC6: Same product name in two categories
**Given** reviewed 2026 lines of product name `Ale` in category `Kahvi` (100) and without a
category (200)
**When** the client sends `GET /api/year/totals`
**Then** `Kahvi` has a product row `Ale` with year 100, and `Ei kategoriaa` has a product row
`Ale` with year 200

### AC7: Finnish name order
**Given** reviewed 2026 lines in categories without a group named `Öljyt`, `omenat`,
`Äyriäiset` and `Banaanit`, one line each
**When** the client sends `GET /api/year/totals`
**Then** the top-level rows are in the order `Banaanit`, `omenat`, `Äyriäiset`, `Öljyt`

### AC8: An edit shows at once
**Given** the data of AC1
**When** the line `Edam` is changed to 600 cents, then the client sends
`GET /api/year/totals`
**Then** `Juusto` has January 600 and the year total is 1700

### AC9: Empty year
**Given** no reviewed receipt dated in 2026 and one unreviewed 2026 receipt
**When** the client sends `GET /api/year/totals` and `GET /api/export/year`
**Then** the totals have no rows, month totals all 0, year total 0 and `unreviewed` 1; the
file `vuosi_2026.csv` has the header row only

### AC10: Year CSV
**Given** the data of AC1
**When** the client sends `GET /api/export/year`
**Then** the file is `vuosi_2026.csv` (UTF-8 with BOM, `;`, CRLF) with the header row
`Jakso;Alkaa;Päättyy;Ryhmä;Kategoria;Tuote;Summa` and then exactly these rows:
```text
2026-01;01.01.2026;31.01.2026;Maitotuotteet;Juusto;Edam;4,00
2026-01;01.01.2026;31.01.2026;Maitotuotteet;Maito;Maito 1l;5,00
2026-03;01.03.2026;31.03.2026;;Kahvi;Kahvi 500g;5,00
2026-03;01.03.2026;31.03.2026;;Ei kategoriaa;TUNTEMATON;1,00
2026;01.01.2026;31.12.2026;;Kahvi;Kahvi 500g;5,00
2026;01.01.2026;31.12.2026;Maitotuotteet;Juusto;Edam;4,00
2026;01.01.2026;31.12.2026;Maitotuotteet;Maito;Maito 1l;5,00
2026;01.01.2026;31.12.2026;;Ei kategoriaa;TUNTEMATON;1,00
```

### AC11: Navigation
**Given** the app open on any page
**When** the user looks at the navigation
**Then** the items are, in this order: `Tuotteet`, `Tuonti`, `Kuitit`, `Yhteenveto`,
`Vuosi tuotteineen`, `Budjetti`, `Vertailu`, `Arkisto`; clicking `Vuosi tuotteineen` opens
`/vuosi` and marks the item as the current page; opening `/vuosi` directly shows the same
page

### AC12: Vuosi tuotteineen page
**Given** the data of AC1 and AC2
**When** the user opens `/vuosi`
**Then** the page shows the heading `Vuosi tuotteineen 2026`, the note
`Tarkistamattomia kuitteja: 2. Ne eivät ole mukana summissa.`, a `Vie CSV` button that
downloads `vuosi_2026.csv`, and the table with 12 month columns and `Vuosi`, with the totals
of AC1; no input, select or edit button is on the page

### AC13: Expand and collapse
**Given** the page of AC12 just opened
**When** the user looks at the table, then opens category `Maito`, then closes group
`Maitotuotteet`
**Then** at first `Juusto` and `Maito` are shown but `Maito 1l` is not; after opening `Maito`
the row `Maito 1l` (5,00 € in January) is shown; after closing `Maitotuotteet` none of its
categories or products are shown. Each toggle is a button with `aria-expanded`

### AC14: Empty year on the page
**Given** the data of AC9
**When** the user opens `/vuosi`
**Then** the page shows `Vuodelta 2026 ei ole vielä tarkistettuja kuitteja.` and the note
`Tarkistamattomia kuitteja: 1. Ne eivät ole mukana summissa.`; there is no table and no
`Vie CSV` button

### AC15: No note without unreviewed receipts
**Given** the data of AC1 only
**When** the user opens `/vuosi`
**Then** no `Tarkistamattomia kuitteja` text is shown

### AC16: Failed request
**Given** the backend answers `GET /api/year/totals` with an error
**When** the user opens `/vuosi`
**Then** the page shows the backend's `message` with `role="alert"` and no table

### AC17: Wide year table
**Given** the page of AC12 with a product named with 100 characters, in a window 1000 px wide
**When** the user scrolls the table box sideways to `2026-12`
**Then** the page itself has no horizontal scroll bar, the name column stays visible, the
table box is wider than `main` in a 1600 px window, and the long name wraps within 250 px

### AC18: Accessibility and privacy
**Given** the Vuosi tuotteineen page with the data of AC1 and AC2
**When** axe runs on it, and both endpoints are called with logging at `DEBUG`
**Then** axe finds no WCAG 2.1 AA violation, and the log has no product, category or store
name

## Files to Modify
| File | Change |
|---|---|
| `backend/app/storage/receipt_repository.py` | `year_lines(start, end)`: reviewed lines with product, category and group names (PC1–PC3) |
| `backend/app/calculation/archive_totals.py` | Reused unchanged (PC1) |
| `backend/app/totals/year.py` (new) | `read_year_totals`, `YearTotals` (PC1–PC4) |
| `backend/app/totals/routes.py`, `backend/app/totals/schemas.py` | `GET /api/year/totals`, `YearTotalsOut`; clock argument |
| `backend/app/export/service.py`, `routes.py`, `exporter.py`, `csv_exporter.py` | `GET /api/export/year`, `year_totals_file`, shared CSV helper (PC5) |
| `backend/app/main.py`, `backend/app/texts.py` | Clock for the totals router; `YEAR_FILE_PREFIX` |
| `frontend/src/navigation.ts`, `frontend/src/App.tsx` | Page `year`, path `/vuosi`, navigation item (PC6, AC11) |
| `frontend/src/api/totals.ts` | `getYearTotals`, `yearCsvUrl` |
| `frontend/src/components/YearPage.tsx` (new) | New page reusing `ArchiveTotalsTable` (PC6, PC7) |
| `frontend/src/test/year.ts` (new) | Test answers of `GET /api/year/totals` |
| `frontend/src/i18n/fi.ts` | Page texts (PC4, PC6, PC7) |
| `frontend/e2e/year.spec.ts` (new) | Year page journey, wide table, axe |
| Backend and frontend tests | New tests (P6); `App.test.tsx` and `Exporter` fakes changed for the new interface (P6) |
| `docs/subsystems/totals/README.md`, `calculation`, `export`, `storage`, `ui` READMEs | Current year totals section, reuse of the tree, export, new read, new page |
| `docs/api-reference.md`, `docs/glossary.md`, `docs/content-plan.md`, `docs/architecture.md` | Endpoints, term `Vuosi tuotteineen`, review date, the totals and export lines |
| `specs/PRD.md`, `specs/README.md` | FR-54 (from the candidates list); spec row 22 |

## Risk
- **What could break:** the shared tree code of the archived year page; a change for this
  page could change archived year totals or the archive CSV. The navigation order test of
  the app changes (`App.test.tsx`) because a new item is added.
- **Rollback:** the change only adds read endpoints and a page; no migration and no data
  change. Reverting the commits removes it.
- **Dependencies:** none new. No Tesseract or Ollama calls.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | year totals service | happy path | lines of AC1 | totals | tree, month and year totals of AC1 | clock |
| AC2 | repository read | reviewed only | AC2 data | read year lines and count | AC1 lines only; unreviewed 2 | none (temporary SQLite) |
| AC3 | repository read | year edges | AC3 data | read 2026 | lines of 2026-01-01 and 2026-12-31 only | none |
| AC4 | year totals service | Finnish new year | clock 2025-12-31 22:30 UTC | totals | year 2026, `Kahvi` 200 | clock |
| AC5 | repository read | current names | renamed product and category | read | `Maidot`, `Maito 1 l` | none |
| AC6, AC7 | tree builder | names and order | AC6, AC7 lines | build | rows of AC6; order of AC7 | none |
| AC9 | year totals service | empty | no reviewed lines | totals | no rows, zeros, unreviewed 1 | clock |
| AC10 | CSV exporter | year file | totals of AC1 | build file | name, header and rows of AC10 | none |
| AC9 | CSV exporter | empty | empty totals | build file | header row only | none |
| AC12, AC15 | `YearPage` | note | `unreviewed` 2 / 0 | render | note shown / not shown | API |
| AC13 | `YearPage` | toggles | AC1 totals | click | rows of AC13; `aria-expanded` | API |
| AC14 | `YearPage` | empty | AC9 totals | render | sentence, no table, no button | API |
| AC16 | `YearPage` | error | API error | render | `role="alert"` message | API |
| AC11 | `App`, navigation | order and path | app | render, click | items in AC11 order; `/vuosi` | API |

### Integration tests
Real SQLite (temporary file) and real FastAPI app; the clock is fixed.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | year totals | `GET /api/year/totals` with AC1 data | AC1 answer | 200 |
| AC2 | unreviewed left out | AC2 data | AC1 totals, `unreviewed` 2 | 200 |
| AC3 | year edges | AC3 data | `Kahvi` 200 + 300 | 200 |
| AC5 | renamed catalog | AC5 data | `Maidot` / `Maito 1 l` | 200 |
| AC8 | edit then read | `PATCH` line, then `GET /api/year/totals` | `Juusto` 600, year 1700 | 200 |
| AC9 | empty year | both endpoints | empty totals; header-only file | 200 |
| AC10 | CSV | `GET /api/export/year` with AC1 data | file of AC10 | 200 |
| AC18 | privacy | both endpoints, logging `DEBUG` | no product, category or store name in the log | 200 |

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC11, AC12 | open the page | open the app, click `Vuosi tuotteineen` | `/vuosi`, heading, table, `Vie CSV` downloads `vuosi_<year>.csv` |
| AC13 | expand and collapse | open a category, close a group | rows shown and hidden |
| AC17 | wide table | 1000 px and 1600 px windows | no page scroll bar, sticky names, wrap at 250 px |
| AC18 | accessibility | axe on `/vuosi` | no WCAG 2.1 AA violation |

### Coverage target
- Backend: 90 % lines for the new code; every branch of what is counted (PC2) and of the
  empty year (PC7).
- Frontend: every new component has tests for each AC it shows.

### Test data
- Synthetic fixtures only: made-up stores (`Kauppa`), products (`Maito 1l`, `Edam`,
  `Kahvi 500g`), categories and groups. No real receipts.
- Mocks: clock (Finnish time); the API client in component tests.

## Related Documentation (MANDATORY)
- Tier 1: [PRD](../PRD.md#9-releases), [API reference](../../docs/api-reference.md),
  [architecture](../../docs/architecture.md), [glossary](../../docs/glossary.md),
  [security](../../docs/security.md)
- Tier 2: [calculation](../../docs/subsystems/calculation/README.md#archived-year-totals),
  [archive](../../docs/subsystems/archive/README.md),
  [totals](../../docs/subsystems/totals/README.md),
  [export](../../docs/subsystems/export/README.md),
  [storage](../../docs/subsystems/storage/README.md), [ui](../../docs/subsystems/ui/README.md)
- Specs: [Archiving](archiving.md) (PC11, PC13, PC15 are the model of this page)
- ADRs: [0007 archive tables](../../docs/adr/0007-archive-tables.md)

<!-- The Plan phase appends "## Plan" and the Tasks phase appends "## Tasks" below. -->

## Plan

### P1 Components
No new subsystem and no new package. The year totals are totals of active data, so they
belong to the [totals](../../docs/subsystems/totals/README.md) subsystem; the tree and the
CSV format are reused from archiving unchanged.

| Part | Where | What |
|---|---|---|
| Storage | `ReceiptRepository.year_lines(start, end)` in @backend/app/storage/receipt_repository.py | New read: the lines of **reviewed** receipts dated `start`–`end`, with `purchase_date`, `amount_cents`, product name `coalesce(products.name, receipt_lines.name)`, category name, group name and `is_deposit_refund` (PC2, PC3). The unreviewed count reuses `count_unreviewed(start, end)` (PC4) |
| Calculation | @backend/app/calculation/archive_totals.py | Reused as is: `archive_totals(year, lines)` with `ArchiveLine` rows (PC1). No rename, so the archive code does not change |
| Totals service | `read_year_totals(receipts, year)` and `YearTotals(totals, unreviewed)` in a new module @backend/app/totals/year.py | Reads the lines and the count in one transaction and builds the tree. Shared by the page endpoint and the CSV export, so they agree (PC5) |
| Totals route | @backend/app/totals/routes.py | `GET /api/year/totals` (the router's prefix is already `/api`). `create_totals_router(settings, clock)` gets the clock; the year is `local_today(clock).year` (PC1, AC4) |
| Totals schema | @backend/app/totals/schemas.py | `YearTotalsOut`: the fields of `ArchiveTotalsOut` (reused from @backend/app/archive/schemas.py) plus `unreviewed` |
| Export | @backend/app/export/service.py, @backend/app/export/routes.py | `ExportService.year_file()` reads `read_year_totals` for the year of its existing `today()`; `GET /api/export/year` (PC5) |
| Exporter | @backend/app/export/exporter.py, @backend/app/export/csv_exporter.py | New protocol method `year_totals_file(totals)`. The body of `archive_totals_file` moves into a private helper that takes the file prefix; both methods call it, so the archive CSV stays byte for byte the same |
| Texts | @backend/app/texts.py | `YEAR_FILE_PREFIX = "vuosi"` |
| Wiring | @backend/app/main.py | Pass the clock to `create_totals_router` |
| Navigation | @frontend/src/navigation.ts, @frontend/src/App.tsx | Page `year`, path `/vuosi`; link between `totals` and `budget` (AC11) |
| API client | @frontend/src/api/totals.ts | `getYearTotals()` and `yearCsvUrl()`; the type reuses `ArchiveTotals` from @frontend/src/api/archive.ts plus `unreviewed` |
| Page | new @frontend/src/components/YearPage.tsx | Loading, shown, empty and failed states as in `ArchiveYearPage`; the note (PC4), the empty sentence (PC7), `Vie CSV`, and `ArchiveTotalsTable` reused as is (PC6) |
| Texts | @frontend/src/i18n/fi.ts | A `year` section: `heading` `Vuosi tuotteineen`, `title(year)`, `unreviewed(n)`, `empty(year)` |

### P2 Data flow
1. `GET /api/year/totals` → route → `read_year_totals(ReceiptRepository(connection), year)`
   with `year = local_today(clock).year`.
2. In one transaction: `year_lines("2026-01-01", "2026-12-31")` and
   `count_unreviewed("2026-01-01", "2026-12-31")`. Text order is date order (the column's
   `CHECK`), so `BETWEEN` covers the year and excludes undated receipts (AC3).
3. The rows become `ArchiveLine`s; `archive_totals(year, lines)` builds the tree, drops
   deposit refunds and sorts in Finnish order (AC1, AC6, AC7).
4. The schema answers the tree and `unreviewed`. Nothing is logged except the request line,
   which has no query string and no names (PC8).
5. `GET /api/export/year` runs steps 1–3 and hands the tree to the exporter.

### P3 Storage query
```sql
SELECT r.purchase_date, l.amount_cents, coalesce(p.name, l.name) AS product_name,
       c.name AS category_name, g.name AS group_name, l.is_deposit_refund
FROM receipt_lines AS l
JOIN receipts AS r ON r.id = l.receipt_id
LEFT JOIN products AS p ON p.id = l.product_id
LEFT JOIN categories AS c ON c.id = l.category_id
LEFT JOIN categories AS g ON g.id = c.parent_id
WHERE r.reviewed = 1 AND r.purchase_date BETWEEN ? AND ?
ORDER BY r.purchase_date, r.id, l.position
```
Parameters only, no string building. A category without a group gives `group_name` NULL; a
line without a category gives both NULL, which is the tree's `Ei kategoriaa`.

### P4 Data model
No change: no migration, no new column.

### P5 API
| Method and path | Answer | Errors |
|---|---|---|
| `GET /api/year/totals` | 200 `{year, months, rows, month_totals, total, unreviewed}`; `rows` as in `GET /api/archive/{year}/totals` | none of its own; a database error is the generic 500 |
| `GET /api/export/year` | 200 `text/csv`, `Content-Disposition` file name `vuosi_<year>.csv` | as above |

### P6 Tests and existing test changes
- New backend tests: `tests/unit/test_year_totals.py` (service with a fixed clock),
  repository rows in the existing repository test module or a new
  `tests/integration/test_year_lines.py`, `tests/integration/test_year_totals_api.py`,
  `tests/unit/test_csv_year.py`.
- New frontend tests: `YearPage.test.tsx`, client tests in `api/totals` tests, navigation
  tests; e2e `frontend/e2e/year.spec.ts` with axe.
- Existing tests that must change, backed by this spec (G7 record): `App.test.tsx` (the
  navigation list gets `Vuosi tuotteineen`, AC11); fakes that implement the `Exporter`
  protocol in the export tests get `year_totals_file` (an interface change, no expectation
  changes); tests that call `create_totals_router` or build the app get the clock argument
  if they pass the factory arguments explicitly.
- The existing archive CSV and archive totals tests must pass unchanged; they guard the
  shared helper.

### P7 Documentation
- [totals](../../docs/subsystems/totals/README.md): a section "Current year totals" with the
  endpoint, what is counted and the shared reader.
- [calculation](../../docs/subsystems/calculation/README.md#archived-year-totals): the tree
  serves both the archived year and the current year.
- [export](../../docs/subsystems/export/README.md), [storage](../../docs/subsystems/storage/README.md),
  [ui](../../docs/subsystems/ui/README.md), [API reference](../../docs/api-reference.md),
  [glossary](../../docs/glossary.md) (`Vuosi tuotteineen`),
  [content-plan](../../docs/content-plan.md) (review date and purposes).
- [PRD](../PRD.md): FR-54 in the requirements, the candidate removed from "Later
  (candidates)" and added to "Later".
- No ADR: no hard-to-infer decision; the user's choices are recorded in this spec.

### P8 Check against the ACs
| AC | Covered by |
|---|---|
| AC1, AC6, AC7 | P3 query + reused `archive_totals` |
| AC2, AC3 | P3 `reviewed = 1` and `BETWEEN`; `count_unreviewed` |
| AC4 | year from `local_today(clock)` |
| AC5 | P3 joins read current names |
| AC8 | computed per request |
| AC9 | empty line list gives an empty tree; exporter writes the header only |
| AC10 | shared CSV helper with prefix `vuosi` |
| AC11–AC17 | P1 navigation, page and reused table |
| AC18 | no names logged; axe in e2e |

## Tasks

Each task is Red → Green → Refactor: write the named test, see it fail for the right
reason, then the code. Run the backend or frontend checks of the changed part after each
task.

- [x] **T1 Storage read (AC2, AC3, AC5).** `ReceiptRepository.year_lines(start, end)` with
  the P3 query. Test: `tests/integration/test_year_lines.py`: reviewed lines only; the edges
  2025-12-31, 2026-01-01, 2026-12-31, 2027-01-01 and an undated receipt; the linked
  product's current name and the renamed category; a line without a category gives NULL
  names; a category without a group gives a NULL group.
- [x] **T2 Year totals reader (AC1, AC2, AC4, AC6, AC7, AC9).** `read_year_totals` and
  `YearTotals` in `backend/app/totals/year.py`. Test: `tests/unit/test_year_totals.py` with
  a temporary database: the AC1 tree and totals, `unreviewed` 2 for AC2, the AC6 and AC7
  rows, the empty year of AC9, and the year from a clock at 2025-12-31 22:30 UTC (AC4).
- [x] **T3 Endpoint (AC1, AC2, AC3, AC5, AC8, AC9).** `GET /api/year/totals`,
  `YearTotalsOut`, the clock argument of `create_totals_router` and its wiring in
  `main.py`. Test: `tests/integration/test_year_totals_api.py`: the AC1 answer, AC2
  `unreviewed`, AC3 edges, AC5 names, AC8 a line edit through the review API then a read,
  AC9 empty. Update callers of `create_totals_router` in the tests if they need the clock
  (P6).
- [x] **T4 CSV helper refactor (guards the archive CSV).** Move the body of
  `archive_totals_file` into a private helper that takes the file prefix. Test: the
  existing archive CSV tests pass unchanged, before and after (no new Red: this is a
  Refactor step with all tests green).
- [x] **T5 Year CSV (AC9, AC10).** `Exporter.year_totals_file`, `CsvExporter.year_totals_file`,
  `YEAR_FILE_PREFIX`, `ExportService.year_file`, `GET /api/export/year`. Tests:
  `tests/unit/test_csv_year.py` (the AC10 rows and file name; header only for an empty
  tree) and a row in `tests/integration/test_year_totals_api.py` or the export API tests
  for the download and its file name. `Exporter` fakes get the new method (P6).
- [x] **T6 Privacy (AC18, backend).** Test in `tests/integration/test_year_totals_api.py`:
  both endpoints with logging at `DEBUG`; the log has no product, category or store name.
- [x] **T7 Navigation (AC11).** Page `year`, path `/vuosi`, link between `Yhteenveto` and
  `Budjetti`. Tests: `navigation.test.ts` (`/vuosi` ↔ `year`) and `App.test.tsx` (the
  navigation order of AC11; the existing list gets the new item, P6).
- [x] **T8 API client.** `getYearTotals()` and `yearCsvUrl()` in `frontend/src/api/totals.ts`.
  Test: `frontend/src/api/totals.test.ts` (new): the request path, the answer, an error
  answer.
- [x] **T9 Year page (AC12–AC16).** `YearPage.tsx` and the `year` texts in `fi.ts`. Test:
  `YearPage.test.tsx`: heading `Vuosi tuotteineen 2026`, the note with 2 and none with 0,
  `Vie CSV` link to `vuosi_2026.csv`, the AC1 table, the AC13 toggles with `aria-expanded`,
  the AC14 empty year, the AC16 `role="alert"`, no input, select or edit button.
- [x] **T10 E2E (AC11, AC12, AC13, AC17, AC18).** `frontend/e2e/year.spec.ts`: open the page
  from the navigation, download the CSV, toggle rows, the wide table at 1000 px and 1600 px,
  axe with no WCAG 2.1 AA violation. The e2e data is synthetic and reviewed through the API.
- [x] **T11 Documentation (P7).** Totals, calculation, export, storage and UI READMEs; API
  reference; glossary; content plan; PRD FR-54 and the release table; `specs/README.md`.
  Run the `document` skill in scan-only mode.
- [x] **T12 Audit.** All checks of the backend and frontend, e2e, and the `review-audit`
  skill; set the status to `Done` in this spec and in `specs/README.md` when it passes.
