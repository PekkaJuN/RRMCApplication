# Glossary

## Overview

Domain terms used across the docs, specs and code. The UI is in Finnish, so each term also
gives the Finnish word the user sees.

## Terms

| Term | Finnish | Meaning |
|---|---|---|
| Catalog | — | The groups, categories and products together; owned by [categorization](subsystems/categorization/README.md) |
| Category | kategoria | Holds products. Belongs to one group or to none. Every product has exactly one category |
| Group | ryhmä, yläryhmä | Holds categories, never products. Cannot be nested, so the hierarchy has at most two levels |
| Product | tuote | A named item with one category; the app's memory of where a purchase belongs |
| Default list | oletuskategoriat | The groups and categories created once on the first start ([PRD 6.9](../specs/PRD.md#69-default-categories)) |
| Display name | — | A name as shown: Unicode NFC, trimmed, inner whitespace collapsed to one space |
| Normalized name | — | The display name, case-folded; stored as `name_key` and used for every comparison ([names](subsystems/categorization/README.md#names)) |
| Receipt | kuitti | One purchase, recorded from one image or typed in by hand: the image identifier, the file name, the import time and the read data with its lines ([datamodel](datamodel.md#receipts)) |
| Manual receipt | käsin luotu kuitti | A receipt the user types in on the Kuitit page instead of importing it: store, date and total, and optionally a failed image. Without an image it has no image identifier and no file name (FR-47, [review](subsystems/review/README.md#deleting-and-creating-a-receipt)) |
| Read receipt | — | What reading one image gives: store, purchase date, total in cents, lines and the raw OCR text ([receipt-reading](subsystems/receipt-reading/README.md)) |
| Receipt reader | — | The one interface import uses to read an image; today the OCR reader (Tesseract, then the text model) |
| Receipt line | kuittirivi | One item of a receipt in printed order: name as read, amount in cents after any discount and including any deposit, and whether it is a deposit refund ([datamodel](datamodel.md#receipt_lines)) |
| Category source | — | Where a line's category came from: `remembered` (the line's product), `model` (the model's suggestion) or `user` (the user chose it); none when the line has no category (FR-15, [categorization](subsystems/categorization/README.md#line-categorization)) |
| Linked line | — | A line that follows a product: its category came from the product or from the user's correction. When the product's category changes, the line moves with it (FR-36). A model suggestion never links a line |
| Suggestion | — | The category the model chose for a line whose name matches no product; it is not remembered as a product |
| Line sum | rivien summa | The sum of a receipt's line amounts, deposit refunds included; compared with the receipt total (FR-20, [calculation](subsystems/calculation/README.md#rules)) |
| Difference | erotus | The receipt total minus the line sum; unknown without a total |
| Sum warning | summavaroitus | Shown when the difference is not 0 or the receipt has no total (FR-20) |
| Category subtotal | välisumma | The sum of a receipt's lines in one category; deposit refunds are in none, lines without a category form their own subtotal (FR-19, FR-44) |
| Review state | tarkistustila | `unreviewed` (tarkistamaton) or `confirmed` (vahvistettu); the user confirms a receipt after checking it and can cancel the confirmation (FR-21) |
| Name match | — | The product whose normalized name equals a line's normalized name ([categorization](subsystems/categorization/README.md#line-categorization)) |
| Resolving a line | — | Giving a new line, or a line that stops being a deposit refund, its name match's category (source `remembered`) or none; never the model (FR-43, NFR-9). Not `LineCategorizer.resolve`, the import step of the same name |
| OCR text | — | The raw text Tesseract read from the image; stored with the receipt so a later release can re-parse it (FR-10); a manual receipt has none |
| Import run | tuonti, tuontiajo | One press of "Tuo kuitit": the files in the import folder at that moment are processed in the background ([import](subsystems/import/README.md)) |
| Import, done and failed folders | tuontikansio, valmiiden kansio, epäonnistuneiden kansio | Where the user puts images, where imported images move, and where files that fail move (settings `RRMC_IMPORT_DIR`, `RRMC_DONE_DIR`, `RRMC_FAILED_DIR`) |
| Image identifier | — | SHA-256 of an image file's bytes, 64 lowercase hex characters; stored as `image_hash` |
| Failed image | epäonnistunut kuva | A `.jpg`, `.jpeg` or `.png` file in the failed folder; offered for a manual receipt, which moves it to the done folder (FR-47) |
| Duplicate | kaksoiskappale | A file whose image identifier is already stored for a receipt; it is not imported again and stays in the import folder |
| Evaluation folder | — | Where the user keeps receipts for the model evaluation tool, with their truth files and run results (setting `RRMC_EVAL_DIR`; [development.md](development.md#model-evaluation)) |
| Truth file | — | `<image>.truth.json`: the values the user reads from a paper receipt, against which the evaluation scores a variant |
| Variant | — | One way of reading a receipt in the evaluation: `ocr:<model>` (Tesseract, then a text model) or `vision:<model>` (the image to a vision model) |
| Full subset | — | The evaluated receipts whose truth file lists the lines; only they get line scores |
| Date range | aikaväli | A period of free days, from a first to a last day, both included; at most 731 days |
| Period | jakso | Whole calendar months, whole ISO weeks or a date range, from a first to a last unit, that the totals cover ([calculation](subsystems/calculation/README.md#period-totals)) |
| Date field | päivämääräkenttä | A text field for one day, shown as `dd.mm.yyyy`, with a calendar button; the API and the database keep `YYYY-MM-DD` ([date field spec](../specs/features/date-field.md)) |
| ISO week | viikko | ISO 8601 week, Monday to Sunday; week 1 holds the year's first Thursday, so it can start in December. Named by its ISO year: `2026-W01`, `vk 1/2026` |
| Column | sarake | One ISO week or month with a day in the period, clipped to the period's days |
| Partial column | osittainen | A column clipped by the period, e.g. week 40 of 2026 shown for October 2026 holds only 1–4 October |
| Group total | ryhmän summa | The sum of a group's category totals in a column |
| Unreviewed count | — | The unreviewed receipts dated in the period; their totals may still change |
| Undated count | — | All receipts without a purchase date; they are in no period |
| Lines file | kuittirivit | The CSV export of every line of the receipts dated in a period, deposit refunds included ([export](subsystems/export/README.md)) |
| Totals file | summat | The CSV export of a period's category totals by week (`summat_viikot`) or by month (`summat_kuukaudet`), in long format |
| Long format | pitkä muoto | One row per column and category, with the period column's key in a cell, instead of one column per week or month; suited to a pivot table |
| Budget row | budjettirivi | A group or a category without a group; a category inside a group is not one ([budget](subsystems/budget/README.md)) |
| Monthly budget | kuukausibudjetti | The amount of one budget row in integer cents; the same for every month, without history |
| Total budget | kokonaisbudjetti | The sum of the monthly budgets of all budget rows; computed, never entered |
| Comparison period | jakso | A calendar month, or a 15–14 period, that the Vertailu page compares with the budget |
| 15–14 period | 15.–14. | From the 15th of a month to the 14th of the next, named after the month it starts in: `2026-10` is 15.10.2026–14.11.2026 |
| Weekly budget | viikkobudjetti | A row's monthly budget divided by the period's days, times the week's days in the period; the weeks add up to the monthly budget |
| Actual spending | toteutunut | The spending of reviewed receipts, by the totals' rules |
| Remaining | jäljellä | The budget minus the actual spending; negative when the row is over budget |
| Exporter | — | The interface that turns a period's lines or totals into a file; CSV now, Google Sheets later (FR-27) |

## Subsystems

- [categorization](subsystems/categorization/README.md) — catalog and line categorization terms
- [import](subsystems/import/README.md) — import terms

## Related Documents

- [projectdescription.md](projectdescription.md)
- [datamodel.md](datamodel.md)
