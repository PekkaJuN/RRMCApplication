# Feature: PDF export

## Overview
- **Status:** Done
- **Created:** 2026-11-09
- **Updated:** 2026-11-09: user answers before Specify: weekly and monthly totals are
  separate PDF files; groups are shown expanded by category; no receipt lines; the budget
  comparison gets its own PDF from the Vertailu page; the monthly and comparison PDFs are
  portrait, the weekly PDF is landscape, and the text must be easy to read; the weekly PDF
  covers at most one month, the monthly PDF at most one year. In the monthly PDF the months
  are stacked: one two-column table per month, continuing down the pages, then a table of
  the whole period; a month's table is never split over two pages, except one taller than
  a page, which continues with the mark `(jatkuu)`. Specify approved by the user. The user
  also wants a CSV export of the budget comparison, as a later spec. Plan added. User
  change: no `Koko jakso` block when the period is at most one month long (31 days), such
  as 15.10.–14.11. (PC4, AC4). Plan approved by the user; Tasks added. Spec approved by the user;
  implementation started. During implementation: `types-reportlab` added as a dev
  dependency for pyright (P1); four existing frontend tests that counted three links on
  the Yhteenveto page now count the CSV links only, or five links, because PC9 adds two
  PDF links; the budget and totals READMEs name the export as a user.
- **Depends on:** [Category totals](totals.md), [CSV export](csv-export.md),
  [Free date range for totals](date-range-totals.md), [Monthly budget](budget.md)
- **Implements:** PRD FR-48 (Next release); NFR-1, NFR-3, NFR-6, NFR-15 for the export.
- **Affected subsystems:** [export](../../docs/subsystems/export/README.md),
  [totals](../../docs/subsystems/totals/README.md),
  [budget](../../docs/subsystems/budget/README.md),
  [ui](../../docs/subsystems/ui/README.md)

## Problem Statement
The user can see the totals and the budget comparison on screen and export the totals as
CSV, but cannot keep or print a readable summary of a period (PRD FR-48). This spec adds
three PDF files: the weekly totals, the monthly totals and the budget comparison, each laid
out to print on one A4 sheet width without shrinking the text.

## Current Behavior
- The Yhteenveto page shows the weekly and monthly totals of a chosen period (month, week
  or date range), with groups that expand to their categories
  ([totals](../../docs/subsystems/totals/README.md), [ui](../../docs/subsystems/ui/README.md)).
- `GET /api/export/totals` and `GET /api/export/lines` return CSV files through the exporter
  interface ([export](../../docs/subsystems/export/README.md)).
- The Vertailu page shows the budget comparison of a calendar month or a 15–14 period, with
  a month table and a week table shown on request
  ([budget](../../docs/subsystems/budget/README.md)).
- There is no PDF export.

## Proposed Change

### Concepts

- A **totals PDF** shows the week columns (`by=week`) or the month columns (`by=month`) of
  the period, computed by the same totals service as the Yhteenveto page, so the figures
  always agree.
  - The **weekly totals PDF** holds one table: the column `Kategoria`, then one column per
    week column.
  - The **monthly totals PDF** holds one **month block** per month column, stacked in date
    order, then a **period block**. A block is a heading and a two-column table `Kategoria`,
    `Summa`. The period block's heading is `Koko jakso` and its sums are each row's total
    over the whole period (the sum of the row's month columns). A period of **at most
    31 days** has **no period block**: it is one month's period, whether it starts on the
    1st or mid-month, such as 15.10.–14.11.
  - A block is **kept whole on one page**: when it does not fit in the space left on a page,
    it starts on the next page. Blocks otherwise follow each other on the same page.
- In a totals PDF **every group is expanded**: the group row with its group total, then each
  of its categories on its own row, indented. Then the standalone categories, the row
  `Ei kategoriaa` and the row `Yhteensä`, in the order of the Yhteenveto page.
- A **comparison PDF** holds the month table of the Vertailu page for one comparison period.
  Its rows are the budget rows, as on the page; groups are not expanded, because budgets
  are set per group.
- **Length limits** keep the tables readable without splitting columns over pages:
  - A weekly totals PDF covers at most **31 days**, so it has at most 6 week columns.
  - A monthly totals PDF covers at most **366 days** (a year, also a leap year or a 15–14
    year with 13 month columns).
- **Page format:** A4. The weekly totals PDF is landscape; the monthly totals PDF and the
  comparison PDF are portrait. Table text is at least 9 pt. When the rows of the weekly
  table or the comparison table do not fit on one page, the table continues on the next
  page and the column headings are repeated.
- A block taller than a whole page (a catalog of about 60 or more rows) cannot be kept
  whole; it then continues on the next page with its heading repeated and the mark
  `(jatkuu)` (approved by the user).

### Parts

- **PC1 Exporter interface (FR-27).** The PDF files are built through the common exporter
  interface, as the CSV files are. The PDF exporter is a second implementation; the CSV
  exporter does not change.
- **PC2 Totals PDF endpoint (FR-48).**
  `GET /api/export/totals/pdf?unit=...&from=...&to=...&by=week|month` takes the period
  parameters of `GET /api/export/totals` (`month`, `week` or `range`) and returns the
  totals PDF of the period.
- **PC3 Comparison PDF endpoint.**
  `GET /api/export/comparison/pdf?month=2026-10&period=calendar|mid` takes the parameters of
  `GET /api/budget/comparison` and returns the comparison PDF.
- **PC4 Page content of a totals PDF.**
  - Top of the first page: the title `Viikkosummat` or `Kuukausisummat`, the line
    `Jakso: 1.10.2026–31.10.2026` with the period's first and last day, and the line
    `Luotu 9.11.2026` with the day the file was made.
  - Under them, when not 0, the counts as on the Yhteenveto page:
    `Tarkistamattomia kuitteja jaksolla: <n>` and `Kuitteja ilman päivää (ei mukana): <n>`.
  - Weekly: the table with the first column `Kategoria`, then one column per week column
    with the heading of the Yhteenveto page (`vk 40/2026`, and for a partial column
    `(osittainen)` and its days).
  - Monthly: the month blocks, each headed as the Yhteenveto month column (`10/2026`, and for
    a partial month `(osittainen)` and its days), then, for a period over 31 days, the
    period block headed `Koko jakso`.
    Every block has the same rows.
  - Rows in every table and block: those of the Yhteenveto page with every group expanded.
    Group rows and `Yhteensä` are bold.
  - A period without counted lines shows `Ei ostoksia valitulla jaksolla.` instead of the
    tables and blocks, as the page does.
  - Bottom of every page: `Sivu <n>/<total>`.
- **PC5 Page content of a comparison PDF.**
  - Top of the first page: the title `Budjettivertailu`, the line
    `Jakso: 15.10.2026–14.11.2026`, the line `Jakson tyyppi: Kalenterikuukausi` or
    `Jakson tyyppi: 15.–14.`, and `Luotu <day>`.
  - Under them, when not 0, the counts as on the Vertailu page:
    `Tarkistamattomia kuitteja, ei mukana: <n>` and `Kuitteja ilman päivää (ei mukana): <n>`.
  - The table: `Kategoria`, `Budjetti`, `Toteutunut`, `Jäljellä`; the rows of the Vertailu
    month table, `Ei kategoriaa` when shown there, and `Yhteensä` in bold. A negative
    `Jäljellä` shows the sign and the text `Ylitetty`, as on the page.
  - Bottom of every page: `Sivu <n>/<total>`.
- **PC6 Money and dates.** As on the pages (totals spec PC7): `123456` → `1234,56 €`,
  `-40` → `-0,40 €`; dates `5.10.2026`. Amounts are right-aligned.
- **PC7 Responses.** `200` with `Content-Type: application/pdf`,
  `Content-Disposition: attachment; filename="<name>"` and `Cache-Control: no-store`. Names:
  `summat_viikot_<from>_<to>.pdf` and `summat_kuukaudet_<from>_<to>.pdf` with `from` and
  `to` as given (as in the CSV names), and `vertailu_<month>.pdf` or
  `vertailu_15-14_<month>.pdf`.
- **PC8 Validation.** The period is checked first, as for the CSV export and the comparison:
  a bad period gives `422 invalid_period`. A missing or other `by` gives
  `422 invalid_request`. A valid period over the limit of its `by` gives
  `422 period_too_long` with the message `Jakso on liian pitkä PDF-tiedostoon.`
- **PC9 Export links on the Yhteenveto page.** After the CSV links, two links that look like
  buttons: `Vie viikkosummat (PDF)` and `Vie kuukausisummat (PDF)`. They follow the CSV
  links' rule: shown when the totals of the period loaded, hidden while the period is
  refused or the totals cannot be loaded. When the period is over a limit, the link of
  that file is replaced by the text `Viikkosummien PDF: jakso enintään 31 päivää.` or
  `Kuukausisummien PDF: jakso enintään 366 päivää.` The page decides this from the
  period's first and last day in the totals answer; the backend still checks (PC8).
- **PC10 Export link on the Vertailu page.** Under the period line, the link
  `Vie vertailu (PDF)` downloads the comparison PDF of the period shown. It is shown when
  the comparison loaded and hidden while the period is refused or cannot be loaded. The
  week table's open or hidden state does not change the file.
- **PC11 Privacy (NFR-1, NFR-3).** The files hold group and category names and sums only, no
  product names or store names. The PDF metadata holds no author or user name. The files go
  only to the user's browser from the local backend. Logs carry method, path and status
  only.

### UI texts

| Place | Text |
|---|---|
| Yhteenveto: weekly totals PDF link | `Vie viikkosummat (PDF)` |
| Yhteenveto: monthly totals PDF link | `Vie kuukausisummat (PDF)` |
| Yhteenveto: weekly PDF over the limit | `Viikkosummien PDF: jakso enintään 31 päivää.` |
| Yhteenveto: monthly PDF over the limit | `Kuukausisummien PDF: jakso enintään 366 päivää.` |
| Monthly PDF: amount column, period block heading, continued block mark | `Summa`, `Koko jakso`, `(jatkuu)` |
| Vertailu: comparison PDF link | `Vie vertailu (PDF)` |
| PDF titles | `Viikkosummat`, `Kuukausisummat`, `Budjettivertailu` |
| PDF period, period kind, creation day | `Jakso: <first>–<last>`, `Jakson tyyppi: <kind>`, `Luotu <day>` |
| PDF page number | `Sivu <n>/<total>` |
| Error `period_too_long` | `Jakso on liian pitkä PDF-tiedostoon.` |

Table headings, row names and counts are those of the [totals spec](totals.md#ui-texts) and
the [budget spec](budget.md#ui-texts).

### Out of Scope
- Receipt lines in a PDF.
- The comparison's week table in a PDF.
- Splitting columns over pages; periods over the limits are refused instead.
- A period total on the Yhteenveto page; `Koko jakso` is in the monthly PDF only.
- Charts, a logo, colors that carry meaning, or a choice of paper size or orientation.
- Printing directly from the app; the user prints the downloaded file.
- Google Sheets (FR-28) and archived data (FR-40–FR-42).
- CSV export of the budget comparison: wanted by the user, a later spec (PRD candidates).

## Acceptance Criteria

Fixture unless the AC says otherwise: the CSV export fixture (the default catalog: Ruoka
holds Leivät and Maitotuotteet; Juomat has no group) with these receipts:

- Receipt A, dated 2026-10-02, unreviewed: `Maito` 125 Maitotuotteet.
- Receipt B, dated 2026-10-06, confirmed: `Ruisleipä` 300 Leivät, `Limu` 250 Juomat,
  `Tuntematon` 199 no category, `Panttipalautus` -40 deposit refund.
- Receipt C, dated 2026-11-01, confirmed: `Ruisleipä` 999 Leivät.
- Budget: Ruoka 40000, Juomat 5000.

"The text of the PDF" means the text extracted from the file, page by page.

### AC1: Weekly totals PDF of a month
**Given** the fixture
**When** the client sends `GET /api/export/totals/pdf?unit=month&from=2026-10&to=2026-10&by=week`
**Then** the answer is 200, `application/pdf`, file name
`summat_viikot_2026-10_2026-10.pdf`; the file has 1 page, A4 landscape (842 × 595 pt); its
text holds `Viikkosummat`, `Jakso: 1.10.2026–31.10.2026`,
`Tarkistamattomia kuitteja jaksolla: 1`, the headings
`vk 40/2026 (osittainen) 1.10.–4.10.2026`, `vk 41/2026`, `vk 42/2026`, `vk 43/2026` and
`vk 44/2026 (osittainen) 26.10.–31.10.2026`, and the values of the Yhteenveto weekly table:
in week 40 `Ruoka` 1,25 €, `Maitotuotteet` 1,25 €; in week 41 `Ruoka` 3,00 €, `Leivät`
3,00 €, `Juomat` 2,50 €, `Ei kategoriaa` 1,99 €, `Yhteensä` 7,49 €

### AC2: Groups are expanded in catalog order
**Given** the fixture
**When** the weekly totals PDF of October 2026 is made
**Then** the row names appear in the order `Ruoka`, `Leivät`, `Maitotuotteet`, `Juomat`,
`Ei kategoriaa`, `Yhteensä`

### AC3: Monthly totals PDF
**Given** the fixture
**When** the client sends `GET /api/export/totals/pdf?unit=month&from=2026-10&to=2026-11&by=month`
**Then** the answer is 200 with file name `summat_kuukaudet_2026-10_2026-11.pdf`; the file
is A4 portrait (595 × 842 pt); its text holds `Kuukausisummat`,
`Jakso: 1.10.2026–30.11.2026`, then in this order the blocks `10/2026`, `11/2026` and
`Koko jakso`, each with the headings `Kategoria` and `Summa`; `Leivät` is 3,00 € in the
October block, 9,99 € in the November block and 12,99 € in `Koko jakso`; `Yhteensä` is
8,74 €, 9,99 € and 18,73 €

### AC4: One month has no period block; deposit refunds are not counted
**Given** the fixture
**When** the monthly totals PDF of October 2026 is made, and the one of
`unit=range&from=2026-10-15&to=2026-11-14`
**Then** the October PDF has the block `10/2026` only, no `Koko jakso`, its text does not
hold `-0,40 €`, and `Yhteensä` is 8,74 €; the range PDF has the blocks
`10/2026 (osittainen) 15.10.–31.10.2026` and `11/2026 (osittainen) 1.11.–14.11.2026` and
no `Koko jakso` (31 days); the PDF of `unit=range&from=2026-10-15&to=2026-11-15`
(32 days) ends with `Koko jakso`

### AC5: Date range and a week crossing the year
**Given** a line of `Leivät` 500 dated 2026-12-30 and one of 700 dated 2027-01-02
**When** the client sends
`GET /api/export/totals/pdf?unit=range&from=2026-12-15&to=2027-01-14&by=week`
**Then** the answer is 200 with file name `summat_viikot_2026-12-15_2027-01-14.pdf`, the text
holds `Jakso: 15.12.2026–14.1.2027`, and the column `vk 53/2026` shows `Leivät` 12,00 €

### AC6: Weekly limit is 31 days
**Given** an empty database
**When** the client asks for the weekly totals PDF of
`unit=range&from=2026-10-01&to=2026-10-31` (31 days) and of
`unit=range&from=2026-10-01&to=2026-11-01` (32 days)
**Then** the first answer is 200, and the second is 422 with `error` `period_too_long` and
the message `Jakso on liian pitkä PDF-tiedostoon.`

### AC7: Weekly limit with week units
**Given** an empty database
**When** the client asks for the weekly totals PDF of `unit=week&from=2026-W40&to=2026-W43`
(28 days) and of `unit=week&from=2026-W40&to=2026-W44` (35 days)
**Then** the first answer is 200 and the second is 422 `period_too_long`

### AC8: Monthly limit is 366 days
**Given** an empty database
**When** the client asks for the monthly totals PDF of `unit=month&from=2026-01&to=2026-12`
(365 days), of `unit=range&from=2026-01-15&to=2027-01-14` (365 days, 13 month blocks), of
`unit=range&from=2026-01-01&to=2027-01-01` (366 days), of
`unit=range&from=2026-01-01&to=2027-01-02` (367 days) and of
`unit=month&from=2026-01&to=2027-01` (396 days)
**Then** the first three answers are 200 and the last two are 422 `period_too_long`

### AC9: Invalid requests
**Given** an empty database
**When** the client asks for the totals PDF with `unit=month&from=2026-13&to=2026-13&by=week`,
with a valid month and no `by`, and with a valid month and `by=day`
**Then** the answers are 422 `invalid_period`, 422 `invalid_request` and
422 `invalid_request`; with both a bad period and a bad `by`, the answer is
`invalid_period`

### AC10: Empty period
**Given** an empty database
**When** the weekly totals PDF of October 2026 is made
**Then** the answer is 200 and the text holds `Ei ostoksia valitulla jaksolla.` and no
`Kategoria` heading

### AC11: Comparison PDF of a calendar month
**Given** the fixture, receipt A unreviewed
**When** the client sends `GET /api/export/comparison/pdf?month=2026-10`
**Then** the answer is 200 with file name `vertailu_2026-10.pdf`; A4 portrait; the text holds
`Budjettivertailu`, `Jakso: 1.10.2026–31.10.2026`,
`Jakson tyyppi: Kalenterikuukausi`, `Tarkistamattomia kuitteja, ei mukana: 1`, the headings
`Kategoria`, `Budjetti`, `Toteutunut`, `Jäljellä`, and the rows `Ruoka` 400,00 € 3,00 €
397,00 €, `Juomat` 50,00 € 2,50 € 47,50 €, `Ei kategoriaa` 0,00 € 1,99 € -1,99 € `Ylitetty`,
and `Yhteensä` 450,00 € 7,49 € 442,51 €

### AC12: Comparison PDF of a 15–14 period
**Given** the fixture
**When** the client sends `GET /api/export/comparison/pdf?month=2026-10&period=mid`
**Then** the answer is 200 with file name `vertailu_15-14_2026-10.pdf`, and the text holds
`Jakso: 15.10.2026–14.11.2026`, `Jakson tyyppi: 15.–14.` and the row `Ruoka` with
`Toteutunut` 9,99 € (receipt C only; receipt B is before the 15th)

### AC13: Comparison PDF errors
**Given** an empty database
**When** the client sends `GET /api/export/comparison/pdf` with `month=2026-13`, with no
`month`, and with `month=2026-10&period=x`
**Then** each answer is 422 `invalid_period`

### AC14: A month block is never split
**Given** a catalog with 30 standalone categories (`Kategoria 01` … `Kategoria 30`), each
with one line in each of October, November and December 2026
**When** the client asks for the monthly totals PDF of
`unit=month&from=2026-10&to=2026-12`
**Then** each of the blocks `10/2026`, `11/2026`, `12/2026` and `Koko jakso` has its
heading, all 30 categories and its `Yhteensä` on one page; a page that holds the end of a
block and does not hold the next block's start has no more table rows after it; and every
page ends with `Sivu <n>/<total>`

### AC15: A block taller than a page
**Given** a catalog with 80 standalone categories, each with one line in October 2026
**When** the monthly totals PDF of October 2026 is made
**Then** the `10/2026` block runs over two pages, the second part starts with the heading
`10/2026 (jatkuu)` and the headings `Kategoria` and `Summa`, and `Yhteensä` of the block is
on the second page only

### AC16: The weekly table continues on the next page
**Given** a catalog with 60 standalone categories, each with one line in October 2026
**When** the weekly totals PDF of October 2026 is made
**Then** the file has 2 or more pages, every page's text holds `Kategoria` and the week
headings, and `Yhteensä` is on the last page only

### AC17: Readable text
**Given** the fixtures of AC1, AC3 and AC11
**When** the PDFs are made
**Then** no text in the tables is smaller than 9 pt and no table runs past the page margins

### AC18: Privacy
**Given** the fixture
**When** each of the three PDFs is made
**Then** their text and metadata do not hold `Maito`, `Ruisleipä`, `Limu`, `Tuntematon`,
`Testikauppa` or any author name, and the request log holds method, path and status only

### AC19: PDF links on the Yhteenveto page
**Given** the Yhteenveto page shows October 2026
**When** the totals have loaded
**Then** the links `Vie viikkosummat (PDF)` and `Vie kuukausisummat (PDF)` point to
`/api/export/totals/pdf?unit=month&from=2026-10&to=2026-10&by=week` and `...&by=month`;
while the totals answer is an error, neither link is shown

### AC20: Over-limit text on the Yhteenveto page
**Given** the Yhteenveto page shows the months 2026-01 to 2027-01
**When** the totals have loaded
**Then** `Vie viikkosummat (PDF)` and `Vie kuukausisummat (PDF)` are not shown, and the texts
`Viikkosummien PDF: jakso enintään 31 päivää.` and
`Kuukausisummien PDF: jakso enintään 366 päivää.` are shown; with a 31-day range, the
weekly link is shown

### AC21: PDF link on the Vertailu page
**Given** the Vertailu page shows `2026-10` with `15.–14.`
**When** the comparison has loaded
**Then** the link `Vie vertailu (PDF)` points to
`/api/export/comparison/pdf?month=2026-10&period=mid`; while the comparison answer is an
error, the link is not shown

## Files to Modify
| File | Change |
|---|---|
| `backend/app/export/` | PDF exporter behind the exporter interface; PDF endpoints; length limits |
| `backend/app/budget/` or `backend/app/export/service.py` | Read the comparison for the comparison PDF (decided in Plan) |
| `backend/app/texts.py` | New messages and PDF texts |
| `backend/pyproject.toml`, `backend/uv.lock` | PDF library and a PDF text reader for tests (decided in Plan, ADR) |
| `backend/tests/` | Unit and integration tests below |
| `frontend/src/api/export.ts` | PDF link addresses |
| `frontend/src/components/` (Yhteenveto page, `ComparisonPage.tsx`) | PDF links and over-limit texts |
| `frontend/e2e/` | E2E journeys below |
| `specs/PRD.md` | FR-48: replace the open question with these answers; comparison PDF |
| `specs/README.md` | Row 16 |
| `docs/subsystems/export/README.md`, `docs/api-reference.md`, `docs/architecture.md`, `docs/subsystems/ui/README.md`, `docs/glossary.md` | PDF export, endpoints, error `period_too_long`, new terms |
| `docs/adr/0005-pdf-library.md` | Choice of the PDF library (Plan) |

## Risk
- **What could break:** the CSV export if the exporter interface changes; a new dependency
  in the backend image; Finnish characters (`ä`, `ö`) and `€` in the PDF font; a long
  category name overflowing its column.
- **Rollback:** the feature is additive: revert its commit. No data model change.
- **Dependencies:** one PDF library in the backend (pure Python preferred, no system
  packages); no external service.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC2 | expanded totals rows | catalog order | fixture totals | build rows | Ruoka, Leivät, Maitotuotteet, Juomat, Ei kategoriaa, Yhteensä | none |
| AC6, AC7 | weekly limit | 31 / 32 days, 4 / 5 weeks | periods | check | ok / too long | none |
| AC8 | monthly limit | 366 / 367 days | periods | check | ok / too long | none |
| AC1, AC3, AC17 | PDF exporter | page size and font size | fixture totals | build file | landscape / portrait A4; table font ≥ 9 pt | none |
| AC5 | PDF exporter | year-crossing heading | range totals | build file | `vk 53/2026` column | none |
| AC10 | PDF exporter | empty period | no lines | build file | `Ei ostoksia valitulla jaksolla.` | none |
| AC11 | PDF exporter | over budget | comparison with negative remaining | build file | `-1,99 €` and `Ylitetty` | none |
| AC14 | PDF exporter | month blocks kept whole | 30 categories, 3 months | build file | no block split; page numbers | none |
| AC15 | PDF exporter | block taller than a page | 80 categories | build file | `10/2026 (jatkuu)`, headings repeated | none |
| AC16 | PDF exporter | weekly table over pages | 60 categories | build file | ≥ 2 pages, headings repeated | none |
| AC3 | period block | sums | two months | build rows | each row's months added | none |
| AC4 | period block | 31 / 32 days | October; 15.10.–14.11.; 15.10.–15.11. | build file | no / no / `Koko jakso` | none |
| AC18 | PDF exporter | metadata | fixture totals | build file | no author or product names | none |

### Integration tests
Real SQLite (temporary file) and real FastAPI app.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1, AC2 | weekly PDF of a month | `GET /api/export/totals/pdf?unit=month&from=2026-10&to=2026-10&by=week` | headers, name, text | 200 |
| AC3, AC4 | monthly PDF | `...&from=2026-10&to=2026-11&by=month` | text and totals | 200 |
| AC5 | year-crossing range | `unit=range&from=2026-12-15&to=2027-01-14&by=week` | `vk 53/2026` 12,00 € | 200 |
| AC6–AC8 | limits | the periods of the ACs | 200 / `period_too_long` | 200 / 422 |
| AC9 | invalid | bad period, no `by`, `by=day` | `invalid_period`, `invalid_request` | 422 |
| AC10 | empty | empty database | empty text | 200 |
| AC11, AC12 | comparison | `month=2026-10`, `&period=mid` | names, text | 200 |
| AC13 | comparison errors | bad month, none, bad period | `invalid_period` | 422 |
| AC18 | log | any PDF request | log line with method, path, status only | 200 |

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC19 | Download totals PDFs | open Yhteenveto for a month, click both PDF links | two downloads with the PDF names, `application/pdf` |
| AC20 | Over-limit period | choose 13 months | over-limit texts shown, no PDF links |
| AC21 | Download comparison PDF | open Vertailu, choose `15.–14.`, click `Vie vertailu (PDF)` | download `vertailu_15-14_<month>.pdf` |

### Coverage target
- Backend: 90 % lines of the new export code; limits and amounts: every branch tested.
- Frontend: every link state of AC19–AC21 has a component test.

### Test data
- Synthetic fixtures only: the CSV export fixture above, the budget above, generated
  category names (`Kategoria 01` …) for AC14–AC16.
- Mocks: none. Tests read the PDF text with a PDF reader library.

## Related Documentation (MANDATORY)
- Tier 1: [PRD](../PRD.md) FR-27, FR-48, FR-49, FR-50; [architecture](../../docs/architecture.md);
  [API reference](../../docs/api-reference.md); [security](../../docs/security.md)
- Tier 2: [export](../../docs/subsystems/export/README.md),
  [totals](../../docs/subsystems/totals/README.md),
  [budget](../../docs/subsystems/budget/README.md),
  [ui](../../docs/subsystems/ui/README.md)
- ADRs: [0001 tech stack](../../docs/adr/0001-tech-stack.md),
  [0005 PDF library](../../docs/adr/0005-pdf-library.md)
- Specs: [totals](totals.md), [CSV export](csv-export.md),
  [date range](date-range-totals.md), [budget](budget.md)

## Plan

### P1 Library (ADR 0005)
- **reportlab** builds the PDF files ([ADR 0005](../../docs/adr/0005-pdf-library.md)). Its
  `platypus` layout gives tables with repeated heading rows (`repeatRows`) and blocks kept
  on one page (`KeepTogether`); a block taller than a page is still split. The standard
  fonts `Helvetica` and `Helvetica-Bold` use WinAnsi encoding, which holds `ä`, `ö`, `å`
  and `€`, so no font file is shipped. BSD licence, pure Python wheels; it uses Pillow,
  which the backend already has.
- **types-reportlab** (development only, typeshed stubs for reportlab 5.1) lets pyright check
  the exporter in strict mode; reportlab ships no type hints.
- **pdfminer.six** (development only) reads the files back in tests: the text of each page,
  the page size, the size and position of every character, and the metadata.
- A spike on 2026-11-09 in a throwaway `python:3.12-slim-bookworm` container (reportlab
  5.1.0, pdfminer.six 20260107) confirmed: `€` and `äö` read back; blocks of 30 rows each
  started on a new page instead of splitting; an 80-row block ran over pages with its
  heading rows repeated; two-pass page numbers `Sivu n/6`; A4 portrait 595 × 842 pt and
  landscape 842 × 595 pt; empty author and creator metadata.

### P2 Exporter interfaces (PC1)
`app/export/exporter.py` keeps `Exporter` (the CSV files) unchanged and adds a second
protocol beside it, `ReportExporter`, for files built from a whole report:

```python
class ReportExporter(Protocol):
    def totals_report(self, report: TotalsReport, by: Unit) -> ExportFile: ...
    def comparison_report(self, report: ComparisonReport) -> ExportFile: ...
```

`PdfExporter` implements it. The later CSV export of the comparison implements
`comparison_report` without changing the endpoints' callers. Two small protocols instead
of one, because the PDF exporter has no lines file and the CSV totals file needs no
counts; the CSV exporter and its tests stay as they are.

### P3 Report data (`app/export/report.py`, pure)
- `TotalsReport`: `PeriodTotals`, `unreviewed_receipts`, `undated_receipts`, `created: date`.
- `ComparisonReport`: `Comparison`, `kind` (`calendar` or `mid`), the two counts, `created`.
- `expanded_rows(totals, by) -> list[ReportRow]`: the rows of PC4 in Yhteenveto order, every
  group followed by its categories (`level` 0 or 1, `bold` for groups), `Ei kategoriaa`,
  then `Yhteensä`; each row holds its amounts per column. `period_amount(row)` adds a
  row's month columns for `Koko jakso`, made only for a period over 31 days (the same
  day count as P5). Integer cents only.
- `has_lines(totals)`: false when no column has a counted line, for the empty text (AC10).

### P4 Finnish text (`app/export/finnish.py`, pure)
The rules of the frontend's `format.ts` and `period.ts`: `money(-40)` → `-0,40 €`,
`day(date)` → `5.10.2026`, `week_label("2026-W40")` → `vk 40/2026`,
`month_label("2027-01")` → `1/2027`, `column_heading(column, by)` with `(osittainen)` and
the days, both years when they differ (date range spec PC7). Fixed texts go to
`app/texts.py`.

### P5 Length limits (`app/export/limits.py`)
`check_pdf_length(period, by)`: days = `end − start + 1`; `week` allows ≤ 31, `month`
≤ 366; otherwise it raises `PeriodTooLongError` (`app/export/errors.py`, an `AppError`
with `period_too_long`, 422, `Jakso on liian pitkä PDF-tiedostoon.`).

### P6 PDF exporter (`app/export/pdf_exporter.py`)
- `SimpleDocTemplate`, A4, margins 15 mm; landscape for `by=week`. Metadata: the title only
  (`Viikkosummat`, `Kuukausisummat`, `Budjettivertailu`); author, creator, producer,
  subject and keywords empty (PC11).
- Header: the title 14 pt bold; `Jakso: …`, `Jakson tyyppi: …` (comparison), `Luotu …`
  and the counts 10 pt.
- Tables: 10 pt, partial week headings 9 pt; amounts right-aligned; group rows and
  `Yhteensä` bold; categories inside a group indented. Text cells are `Paragraph`s, so a
  long category name wraps inside its column and never runs past the margin (AC17).
- Weekly: one `Table`, `repeatRows=1`; `Kategoria` takes 30 % of the width, the week
  columns share the rest equally.
- Monthly: per block a `Table` whose first row is the block heading (spanning both
  columns) and second row `Kategoria` / `Summa`, `repeatRows=2`, wrapped in
  `KeepTogether`. A table subclass `ContinuedTable` adds ` (jatkuu)` to the heading of
  every part after the first when reportlab splits it (AC15).
- Comparison: one `Table` `Kategoria`, `Budjetti`, `Toteutunut`, `Jäljellä`,
  `repeatRows=1`; a negative remaining reads `-1,99 € Ylitetty`.
- Page numbers: a canvas that buffers the pages and writes `Sivu n/total` at the bottom of
  each page on save.
- File names (PC7) from the checked period bounds, as the CSV names; media type
  `application/pdf`.

### P7 Service and endpoints
- `ExportService` also gets the `ReportExporter`, a `BudgetService` and
  `today: Callable[[], date]`.
  - `totals_pdf(unit, first, last, by)`: the period (`invalid_period`), then `by`
    (`invalid_request`), then `check_pdf_length`, then one transaction that reads the
    totals and both counts as `TotalsService.totals` does, then `totals_report`.
  - `comparison_pdf(month, period)`: `BudgetService.comparison` (its `invalid_period`),
    then `comparison_report`.
- `app/export/routes.py`: `GET /api/export/totals/pdf` and `GET /api/export/comparison/pdf`
  through the existing `_download` (PC7 headers).
- `create_app` gets `report_exporter: ReportExporter | None` (default `PdfExporter()`) and
  passes its `clock` to the export router. The creation day is the clock's time in
  `Europe/Helsinki` (the image has the time zone data; checked 2026-11-09), so a file made
  just after midnight in Finland has the right day.

### P8 Frontend
- `api/export.ts`: `ExportKind` gets `weeksPdf` and `monthsPdf` →
  `/api/export/totals/pdf` with `by`; `comparisonPdfUrl(month, period)` →
  `/api/export/comparison/pdf`.
- `api/export.ts`: `pdfLimits(startDate, endDate)` →
  `{ weeks: days <= 31, months: days <= 366 }`, counted from the ISO strings with
  `Date.UTC`, so the time zone cannot move a day.
- `TotalsPage.tsx`: the two PDF links after the CSV links, or the over-limit texts (PC9).
  `ComparisonPage.tsx`: `Vie vertailu (PDF)` under the period line (PC10). Texts in
  `i18n`.

### P9 Data model
No change.

### AC coverage
| AC | Plan |
|---|---|
| AC1, AC2, AC5, AC16 | P3, P4, P6 weekly, P7 |
| AC3, AC4, AC14, AC15 | P3 `period_amount`, P6 monthly blocks |
| AC6–AC9 | P5, P7 order of checks |
| AC10 | P3 `has_lines`, P6 |
| AC11–AC13 | P6 comparison, P7 |
| AC17 | P6 fonts, `Paragraph` cells, margins; tests read char sizes and positions (P1) |
| AC18 | P6 metadata; the existing request log |
| AC19–AC21 | P8 |

### Files to Modify (refined)
| File | Change |
|---|---|
| `backend/app/export/exporter.py` | `ReportExporter`, `TotalsReport`, `ComparisonReport` |
| `backend/app/export/report.py` (new) | Expanded rows, period amounts |
| `backend/app/export/finnish.py` (new) | Money, dates, headings |
| `backend/app/export/limits.py`, `errors.py` (new) | Length limits, `period_too_long` |
| `backend/app/export/pdf_exporter.py` (new) | The PDF files |
| `backend/app/export/service.py`, `routes.py` | PDF methods and endpoints |
| `backend/app/main.py` | `report_exporter`; the clock to the export router |
| `backend/app/texts.py` | PDF texts and the new error message |
| `backend/pyproject.toml`, `backend/uv.lock` | `reportlab`; dev `pdfminer.six` and `types-reportlab` |
| `backend/tests/pdf_reader.py` (new) | Test helper: pages, text, sizes, char boxes, metadata |
| `backend/tests/` | Unit and integration tests of the Testing Strategy |
| `frontend/src/api/export.ts`, `frontend/src/i18n/`, `TotalsPage.tsx`, `ComparisonPage.tsx` | Links and over-limit texts, with tests |
| `frontend/e2e/pdf.spec.ts` (new) | AC19–AC21 journeys |
| `frontend/src/components/TotalsPage.test.tsx` | Existing link counts: CSV links only, or five links (PC9) |
| `docs/adr/0005-pdf-library.md` (new) | reportlab and pdfminer.six |
| `docs/subsystems/export/README.md`, `docs/api-reference.md`, `docs/architecture.md`, `docs/subsystems/ui/README.md`, `docs/glossary.md`, `docs/security.md`, `docs/content-plan.md` | PDF export, endpoints, `period_too_long`, terms (month block, period block), metadata |
| `docs/subsystems/budget/README.md`, `docs/subsystems/totals/README.md` | Export as a user of their services |
| `specs/PRD.md` | FR-48 answered; comparison PDF |

## Tasks

Each task runs Red → Green → Refactor; the tests named are written first. Backend tasks end
with `pytest`, `ruff` and `pyright` green; frontend tasks with `npm test`, lint, format
check and typecheck green.

- [x] **T1 Dependencies (P1).** Add `reportlab` to the dependencies and `pdfminer.six` to the
  dev group in `backend/pyproject.toml`; update `uv.lock` in the backend container; rebuild
  the image. Proof: `docker compose run --rm backend pip-audit` passes, and
  `python -c "import reportlab, pdfminer"` runs in the container.
- [x] **T2 Finnish text (P4; AC1, AC5, AC11).** `app/export/finnish.py`. Unit tests:
  `money` (125, -40, 0, 123456), `day`, `week_label`, `month_label` (`1/2027`),
  `column_heading` for a full column, a partial column (`vk 40/2026 (osittainen)
  1.10.–4.10.2026`) and one crossing a year (`30.12.2026–2.1.2027`).
- [x] **T3 Length limits (P5; AC6–AC8).** `app/export/limits.py`, `app/export/errors.py`,
  the message in `texts.py`. Unit tests: 31 / 32 days for `week`; 28 / 35 days of week
  units; 365, 366, 367 and 396 days for `month`; the error code, status and message.
- [x] **T4 Report rows (P2, P3; AC2–AC4, AC10).** `TotalsReport`, `ComparisonReport` and
  `ReportExporter` in `exporter.py`; `app/export/report.py`. Unit tests: expanded rows in
  the order of AC2 with levels and bold; `period_amount` (Leivät 1299, Yhteensä 1873);
  no period block at 31 days (October; 15.10.–14.11.), a period block at 32 days;
  `has_lines` false for an empty period and true for a period with a 0-sum line.
- [x] **T5 PDF reader helper and weekly PDF (P6; AC1, AC2, AC5, AC10, AC16, AC17, AC18).**
  `tests/pdf_reader.py` (page sizes, text per page, character sizes and boxes, metadata);
  `PdfExporter.totals_report` for `by=week`, header, page numbers, metadata. Unit tests:
  landscape A4; the texts and values of AC1; row order of AC2; the `vk 53/2026` column of
  AC5; the empty text of AC10 without `Kategoria`; 60 categories over ≥ 2 pages with
  repeated headings and `Yhteensä` on the last page only (AC16); no character under 9 pt
  and every character inside the margins (AC17); empty author, creator and producer, no
  product or store names (AC18).
- [x] **T6 Monthly PDF (P6; AC3, AC4, AC14, AC15, AC17).** Month blocks, `KeepTogether`,
  `ContinuedTable`, the period block rule. Unit tests: portrait A4; the blocks and values of
  AC3 in order; AC4's three periods; 30 categories × 3 months: each block whole on one
  page (AC14); 80 categories: the second part headed `10/2026 (jatkuu)` with `Kategoria`
  and `Summa`, `Yhteensä` on the second page only (AC15); font sizes and margins (AC17).
- [x] **T7 Comparison PDF (P6; AC11, AC12, AC17, AC18).** `PdfExporter.comparison_report`.
  Unit tests: portrait A4; the header, period kind, count and rows of AC11 with
  `-1,99 € Ylitetty`; `Jakson tyyppi: 15.–14.` (AC12); font sizes, margins and metadata.
- [x] **T8 Service, endpoints and wiring (P7; AC1–AC13, AC18).** `ExportService.totals_pdf`
  and `comparison_pdf`, the two routes, `create_app(report_exporter=...)` and the clock in
  `Europe/Helsinki`. Integration tests (real SQLite, real app, the real `PdfExporter`):
  every row of the Integration tests table, including the file names and headers of PC7,
  the order of checks of AC9, `Luotu 9.11.2026` with a fixed clock at 2026-11-08T22:30Z,
  and the request log line holding no query string (AC18).
- [x] **T9 Frontend addresses and limits (P8; AC19–AC21).** `api/export.ts`:
  `exportUrl("weeksPdf" | "monthsPdf", period)`, `comparisonPdfUrl(month, period)`,
  `pdfLimits(start, end)`. Unit tests in `export.test.ts`: the addresses of AC19 and AC21;
  limits at 31 / 32 and 366 / 367 days, and across a change to summer time.
- [x] **T10 Yhteenveto links (PC9; AC19, AC20).** `TotalsPage.tsx`, texts in `i18n`.
  Component tests: both PDF links after the CSV links with the addresses of AC19; no links
  while the totals answer is an error; the over-limit texts for 2026-01–2027-01; the weekly
  link shown for a 31-day range.
- [x] **T11 Vertailu link (PC10; AC21).** `ComparisonPage.tsx`. Component tests: the link
  address for `2026-10` with `15.–14.`; no link while the answer is an error; the link
  does not change when the week table is opened.
- [x] **T12 E2E (AC19–AC21).** `frontend/e2e/`: the three journeys of the E2E table, with
  synthetic data. Proof: `docker compose --profile e2e run --rm e2e`.
- [x] **T13 Docs (Files to Modify).** Export README (PDF files, `ReportExporter`, blocks,
  limits), API reference (two endpoints, `period_too_long`), architecture (export row,
  dependencies), UI README (links and texts), glossary (month block, period block),
  security (PDF content and metadata), content plan (ADR 0005), PRD FR-48 (answers,
  comparison PDF). Proof: links checked by the `checker` subagent.
- [x] **T14 Final checks.** Every command of the AGENTS.md table, including the container
  tests; then hand over to `review-audit`.
