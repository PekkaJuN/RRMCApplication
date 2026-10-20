# Product Requirements Document: RRMCApplication

- **Status:** Draft
- **Created:** 2026-10-20
- **Owner:** Pekka Nissinen

RRMCApplication (Receipt Reader Mapper Calculator) is a local, single-user receipt app. It
reads photos of shopping receipts, categorizes the purchases, and totals each category per
week and per month.

This PRD describes the product: what it does and why. Feature specs in `specs/features/`
turn its requirements into acceptance criteria. When a spec and this PRD disagree, raise it
and update one of them.

## 1. Problem

Tracking where grocery and household money goes needs line-level data, but paper receipts
only give it on paper. Typing receipts in by hand takes too long, and cloud receipt
services send personal purchase data to third parties.

## 2. Goals

| # | Goal |
|---|---|
| G1 | Turn a receipt photo into categorized line items with little manual work. |
| G2 | Show how much was spent per category, per ISO week and per month. |
| G3 | Let the user correct categories quickly, and remember each correction. |
| G4 | Keep all receipt data on the user's own computer. |
| G5 | Export the results for use elsewhere: CSV first, Google Sheets later. |

## 3. Non-goals

- Multiple users, accounts or login.
- Hosting on a server, or a mobile app.
- Budgeting, forecasting or bank-account integration.
- Cloud OCR or cloud language models.
- Reading paper-free e-receipts in the first release (see [Open questions](#11-open-questions)).

## 4. User

One person who photographs their own shopping receipts and wants a category breakdown of
spending. They are comfortable starting a local app, and they correct the results in a UI
rather than in a spreadsheet.

## 5. Main user flow

1. The user saves receipt photos into the import folder (`source/import`).
2. The user starts the import in the app.
3. For each image, the app reads the text (OCR), extracts the store, date, lines and total,
   and suggests a category for each line.
4. The user opens a receipt and sees the image next to an editable table of its lines.
5. The user fixes wrong categories (and, if needed, line text or amounts). Totals update
   immediately. A warning shows if the lines do not add up to the receipt total.
6. The user confirms the receipt. Processed images have already been moved to
   `source/import_done`.
7. The user views category totals per week and per month, and exports them as CSV.

## 6. Functional requirements

IDs are stable. Specs reference them (e.g. "implements FR-12").

### 6.1 Import

| ID | Requirement |
|---|---|
| FR-1 | The app reads receipt images from a configurable import folder (default `source/import`). |
| FR-2 | Supported formats: JPEG and PNG. [NEEDS CLARIFICATION: HEIC from iPhone? PDF?] |
| FR-3 | Each image gets an identifier computed from its content (SHA-256 hash). An image whose identifier already exists is reported as a duplicate and is not imported again. |
| FR-4 | After an image's data is committed to the database, the image moves to a configurable done folder (default `source/import_done`). An image that fails is not lost: it stays in place or moves to a failed folder, with the reason shown to the user. |
| FR-5 | The import reports, per run, how many images were imported, skipped as duplicates and failed. |

### 6.2 Reading and parsing

| ID | Requirement |
|---|---|
| FR-6 | Images are preprocessed for OCR (for example grayscale, deskew, contrast, scaling). |
| FR-7 | Text is read with Tesseract using the Finnish and English language packs (`fin+eng`). |
| FR-8 | A local language model through Ollama turns the OCR text into structured data: store, purchase date (and time if present), line items (name, quantity, unit price, amount) and receipt total. The output is validated against a schema; invalid output is a failure, not silent data. |
| FR-9 | Parsing handles Finnish receipt conventions: decimal comma, discount lines (negative), deposit lines (pantti), weighed items spread over two lines, bonus lines, the VAT summary, and the card payment slip after the total, which is ignored. |
| FR-10 | The raw OCR text is stored with the receipt, so a receipt can be re-parsed without re-running OCR. |

### 6.3 Categorization

| ID | Requirement |
|---|---|
| FR-11 | The user manages categories and groups (add, rename, move, remove when unused). Categories are organized in at most two levels: a **group** holds categories; a category either belongs to one group or stands alone. The app ships with the default list in [section 6.9](#69-default-categories). |
| FR-12 | Each line gets a category. A product name the user has corrected before gets the remembered category first. Otherwise the model suggests one from the category list. The model sees each category with its group (e.g. "Ruoka > Maitotuotteet") and can only choose a category, never a group. |
| FR-13 | When the user changes a line's category, the mapping from that product name to the category is stored and reused for future receipts. |
| FR-14 | Product names are normalized before matching, so small OCR differences (case, spacing, common character mix-ups) still match a remembered product. |
| FR-15 | Each line records where its category came from: remembered mapping, model, or user. |

### 6.4 Review UI

| ID | Requirement |
|---|---|
| FR-16 | A receipt view shows the receipt image and an editable table of its lines side by side. |
| FR-17 | Each line's category is chosen from a dropdown of the categories. Categories are listed under their group headings; groups themselves cannot be chosen. |
| FR-18 | The user can edit line name, quantity and amount, add a missing line and delete a wrong one. Store, date and total are editable too. |
| FR-19 | Category subtotals for the receipt update immediately after any edit. |
| FR-20 | A warning shows when the sum of the lines (including discounts and deposits) differs from the receipt total, with the difference. |
| FR-21 | A list view shows all receipts with date, store, total, warning state and review state (unreviewed / confirmed). |

### 6.5 Totals

| ID | Requirement |
|---|---|
| FR-22 | The app shows the total per category per ISO 8601 week (Monday to Sunday) and per calendar month. A group's total is the sum of its categories; the user can expand a group to see its categories. |
| FR-23 | Totals group by the receipt's purchase date, not by the import date. |
| FR-24 | Totals update when a receipt is edited. |
| FR-25 | The user can choose the period shown (for example a month or a range of weeks). |

### 6.6 Export

| ID | Requirement |
|---|---|
| FR-26 | The user can export to CSV, generated from the database: receipt lines with group, category and date, and the weekly and monthly totals per group and category. [NEEDS CLARIFICATION: exact CSV columns, separator (`;` for Finnish Excel?) and decimal format] |
| FR-27 | Exporters implement one common interface, so new targets can be added without changing the rest of the app. |
| FR-28 | *Later release:* export to a private Google Sheet with gspread and a service account. |

### 6.7 Model and settings

| ID | Requirement |
|---|---|
| FR-29 | The model name is one setting. The default starts in the 7–9B class; switching to a 14B model only needs that setting changed. |
| FR-30 | The model is loaded when the app starts and kept loaded while the app runs. |
| FR-31 | If Ollama or the model is not available, the app says so clearly, and import waits instead of failing images. |
| FR-32 | Settings (folders, model name, Tesseract path) are kept in one configuration file outside version control, with a committed example file. |

### 6.8 Product management

A **product** is a named item with one category. The product list is the app's memory of
which category each product belongs to (FR-12, FR-13). The user can also manage it directly.

| ID | Requirement |
|---|---|
| FR-33 | The user can view all products with their categories, filter them by category and search them by name. |
| FR-34 | The user can add a product with a category, rename a product, change its category and delete it. |
| FR-35 | Product names are unique after normalization (FR-14). Category and group names share one namespace and are unique, ignoring case and surrounding spaces (e.g. only one "Muut"). |
| FR-36 | When the user changes a product's category, every saved receipt line of that product moves to the new category, and all totals reflect the change. Deleting a product does not change saved lines: they keep their current category. |
| FR-37 | A category that is used by a product cannot be deleted; the user is told how many products use it. A group that still has categories cannot be deleted; the user is told how many. |
| FR-38 | A product always belongs to a category, never directly to a group. |
| FR-39 | The user can create a new group and add new or existing categories to it, move a category from one group to another, and take a category out of a group. Groups cannot be nested. A category that has products cannot be turned into a group. |

### 6.9 Default categories

Created once, on first start, when there are no categories. The user can change them freely
afterwards. Names are in Finnish (NFR-15).

| Group | Categories |
|---|---|
| Ruoka | Maitotuotteet, Liha, Kala, Hedelmät, Vihannekset, Kananmunat, Lihan korvaajat, Leivät, Kuivatuotteet, Pakasteet |
| Auto | Polttoaineet, Autotarvikkeet, Autohuolto |
| (no group) | Juomat, Alkoholi, Herkut, Hygienia, Kodin tarvikkeet, Lemmikit, Ulkona syöminen, Muut |

That is 2 groups and 21 categories.

Categorization rule: a product goes by its product type, not by how it is stored. Frozen
fish goes to Kala and frozen vegetables to Vihannekset. Pakasteet is for frozen products
with no type of their own, such as ready meals.

### 6.10 Archiving (later release)

Not part of the MVP. Remaining details are open (see [Open questions](#11-open-questions)).

| ID | Requirement |
|---|---|
| FR-40 | When the user chooses to, they can archive the previous calendar year: all receipts whose purchase date is in that year, and their lines, move to separate archive tables. Archiving is never automatic. |
| FR-41 | The user can permanently delete archived data, after a confirmation. |
| FR-42 | Archived data is not included in the totals or exports of active data, and does not appear in the normal views. |

## 7. Non-functional requirements

### 7.1 Privacy and security

| ID | Requirement |
|---|---|
| NFR-1 | Images, OCR text and parsed data never leave the computer. OCR and the model run locally; Ollama runs with cloud features disabled. |
| NFR-2 | The backend listens on `127.0.0.1` only. CORS allows only the local UI origin. |
| NFR-3 | Receipt content does not appear in logs or error messages. |
| NFR-4 | Receipt images, the database and secrets are never committed to version control. |
| NFR-5 | For Sheets export, the service-account key is stored outside the repository and outside cloud-synced folders; the sheet is private and shared only with the service account; the narrowest working scope is used. |

### 7.2 Correctness

| ID | Requirement |
|---|---|
| NFR-6 | Money is stored and calculated as integer cents. |
| NFR-7 | No data is lost on failure: an image is moved only after its data is committed. |

### 7.3 Performance

| ID | Requirement |
|---|---|
| NFR-8 | One receipt is processed (OCR plus model) in under [NEEDS CLARIFICATION: target, e.g. 30 s] on the user's computer. |
| NFR-9 | UI edits and total updates feel immediate (under 200 ms). |

### 7.4 Platform

| ID | Requirement |
|---|---|
| NFR-10 | Runs on Windows (the user's machine). Prerequisites: Python, Node.js, Tesseract with `fin` and `eng`, and Ollama. |
| NFR-11 | Setup and start are documented in `docs/development.md` and work from a clean checkout. |
| NFR-15 | The user interface is in Finnish. Documentation and code are in English (see `AGENTS.md`). |

### 7.5 Quality

| ID | Requirement |
|---|---|
| NFR-12 | Development is spec-driven and test-driven (see `AGENTS.md`). Tests use synthetic receipts only. |
| NFR-13 | OCR and the model sit behind backend interfaces. A configuration setting selects the real implementation or a deterministic fake, so tests and E2E runs do not need Tesseract or Ollama and give the same result every time. |
| NFR-14 | The UI is tested at three levels: component tests (Vitest + React Testing Library, API mocked with MSW), and a few end-to-end tests of the main journeys (Playwright, real backend with the fakes from NFR-13). |

## 8. Solution outline (decided)

| Area | Choice |
|---|---|
| OCR | Tesseract 5.x, `fin` + `eng` |
| Parsing and categorization | Local model through Ollama; structured JSON output |
| Backend | Python + FastAPI: preprocessing, OCR, model calls, totals, export |
| Frontend | React + Vite + TypeScript |
| Storage | SQLite |
| Export | CSV first; Google Sheets (gspread) later, behind the same interface |
| Testing | Backend: pytest. UI: Vitest + React Testing Library + MSW. E2E: Playwright. |

Main stored entities: **category** (name, optional group; a group is a category without a
parent that holds other categories), **product** (display name, normalized name, category:
the remembered product–category mapping), **receipt** (image hash, file name, store, purchase date, total, raw OCR text,
review state), **receipt line** (name as read, normalized name, quantity, unit price, amount,
category, category source, product). The data model is defined in `docs/datamodel.md`.

## 9. Releases

| Release | Scope |
|---|---|
| MVP | FR-1 to FR-27, FR-29 to FR-39, all NFRs except NFR-5 |
| Next | FR-28 Google Sheets export (with NFR-5) |
| Later | FR-40 to FR-42 archiving (see [section 6.10](#610-archiving-later-release)) |
| Later (candidates) | e-receipt import, content-based duplicate check (same receipt photographed twice), re-parse with a different model |

A suggested order of feature specs for the MVP:

1. Product management: groups, categories and products (`specs/features/product-management.md`),
   including the minimal backend, frontend and SQLite setup it needs
2. Storage and settings for receipts
3. Import with duplicate detection and file moving
4. OCR and parsing
5. Categorization with remembered corrections
6. Review UI
7. Totals
8. CSV export

## 10. Success measures

| Measure | Target |
|---|---|
| Lines needing a manual category correction | Falls over time; under 10 % after the first month of use |
| Receipts with a sum mismatch warning | Under [NEEDS CLARIFICATION] % |
| Time to review one receipt | Under 1 minute |
| Receipt data sent off the machine | None |

## 11. Open questions

1. [NEEDS CLARIFICATION] Hardware: is there a GPU, and how much memory? This decides
   whether 9B or 14B is practical, and the NFR-8 target.
2. [NEEDS CLARIFICATION] Import trigger: a button in the UI, or automatic folder watching?
3. [NEEDS CLARIFICATION] Image source: phone photos or a scanner? HEIC support needed?
4. [NEEDS CLARIFICATION] Should e-receipts (PDF from store apps) be supported, and when?
5. [NEEDS CLARIFICATION] Model choice: compare Tesseract + text model against a vision model
   on 20–30 real receipts before the parsing spec is approved.
6. [NEEDS CLARIFICATION] Is VAT breakdown or any currency other than euro needed? (Assumed no.)
7. [NEEDS CLARIFICATION] Is a receipt categorized per line only, or can a whole receipt get
   one category?
8. [NEEDS CLARIFICATION] CSV format details (FR-26).
9. [NEEDS CLARIFICATION] Archiving (FR-40 to FR-42): can older years than the previous one
   be archived too (e.g. after a long break)? Can archived data be viewed or exported
   separately? Can archiving be undone? Does FR-36 recategorization also update archived
   lines? Are receipt images in `import_done` archived or deleted with the data?

Resolved:

- Default category list: section 6.9 (2026-10-20).
- UI language: Finnish, NFR-15 (2026-10-20).
- Two-level categories with user-created groups: FR-11, FR-38, FR-39 (2026-10-20).
- Changing a product's category also updates saved receipt lines: FR-36 (2026-10-20).
- Archiving is by previous calendar year, started by the user; archived data is excluded from
  active totals and exports: FR-40, FR-42 (2026-10-20).

## 12. Risks

| Risk | Mitigation |
|---|---|
| OCR quality on faded thermal paper or angled photos | Preprocessing; editable lines in the UI; possible vision-model fallback |
| Model returns wrong or invalid structure | Schema-constrained output, validation, temperature 0, clear failure state |
| Product names vary through OCR noise, so corrections are not reused | Name normalization (FR-14), fuzzy matching if needed |
| Model too slow on the user's hardware | Model is one setting; smaller model; load once at start |
| Same receipt imported twice from different photos | Shown to the user; content-based check as a later candidate |
| Recategorizing a product changes past totals that were already exported (FR-36) | The confirmation tells the user how many saved lines will move; exports are regenerated from the database |

## 13. Glossary

| Term | Meaning |
|---|---|
| Receipt | One purchase, read from one image. |
| Line | One item row on a receipt, including discount and deposit rows. |
| Category | What a product belongs to, e.g. "Maitotuotteet". Totals are calculated per category. |
| Group | A category that holds other categories, e.g. "Ruoka". Its total is the sum of its categories. Products cannot belong to a group directly. |
| Product | A named item with one category, stored once per normalized name. The product list is the remembered product–category mapping. |
| Normalized name | A product or category name after normalization, used for matching and uniqueness. |
| ISO week | Week as defined by ISO 8601: Monday start; week 1 contains the first Thursday of the year. |
| Pantti | Bottle and can deposit, shown as its own line on Finnish receipts. |

## Related documents

- `AGENTS.md`: development rules, SDD and TDD
- `docs/content-plan.md`: documentation index
- `specs/TEMPLATE.md`: template for the feature specs that implement this PRD
