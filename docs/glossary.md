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
| Receipt | kuitti | One purchase, recorded from one image: the image identifier, the file name, the import time and the read data with its lines ([datamodel](datamodel.md#receipts)) |
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
| OCR text | — | The raw text Tesseract read from the image; stored with the receipt so it can be re-parsed (FR-10) |
| Import run | tuonti, tuontiajo | One press of "Tuo kuitit": the files in the import folder at that moment are processed in the background ([import](subsystems/import/README.md)) |
| Import, done and failed folders | tuontikansio, valmiiden kansio, epäonnistuneiden kansio | Where the user puts images, where imported images move, and where files that fail move (settings `RRMC_IMPORT_DIR`, `RRMC_DONE_DIR`, `RRMC_FAILED_DIR`) |
| Image identifier | — | SHA-256 of an image file's bytes, 64 lowercase hex characters; stored as `image_hash` |
| Duplicate | kaksoiskappale | A file whose image identifier is already stored for a receipt; it is not imported again and stays in the import folder |
| Evaluation folder | — | Where the user keeps receipts for the model evaluation tool, with their truth files and run results (setting `RRMC_EVAL_DIR`; [development.md](development.md#model-evaluation)) |
| Truth file | — | `<image>.truth.json`: the values the user reads from a paper receipt, against which the evaluation scores a variant |
| Variant | — | One way of reading a receipt in the evaluation: `ocr:<model>` (Tesseract, then a text model) or `vision:<model>` (the image to a vision model) |
| Full subset | — | The evaluated receipts whose truth file lists the lines; only they get line scores |

## Subsystems

- [categorization](subsystems/categorization/README.md) — catalog and line categorization terms
- [import](subsystems/import/README.md) — import terms

## Related Documents

- [projectdescription.md](projectdescription.md)
- [datamodel.md](datamodel.md)
