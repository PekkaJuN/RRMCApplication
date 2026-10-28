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
| Receipt | kuitti | One purchase, recorded from one image. Today it holds the image identifier, the file name and the import time ([datamodel](datamodel.md#receipts)) |
| Import run | tuonti, tuontiajo | One press of "Tuo kuitit": the files in the import folder at that moment are processed in the background ([import](subsystems/import/README.md)) |
| Import, done and failed folders | tuontikansio, valmiiden kansio, epäonnistuneiden kansio | Where the user puts images, where imported images move, and where files that fail move (settings `RRMC_IMPORT_DIR`, `RRMC_DONE_DIR`, `RRMC_FAILED_DIR`) |
| Image identifier | — | SHA-256 of an image file's bytes, 64 lowercase hex characters; stored as `image_hash` |
| Duplicate | kaksoiskappale | A file whose image identifier is already stored for a receipt; it is not imported again and stays in the import folder |
| Evaluation folder | — | Where the user keeps receipts for the model evaluation tool, with their truth files and run results (setting `RRMC_EVAL_DIR`; [development.md](development.md#model-evaluation)) |
| Truth file | — | `<image>.truth.json`: the values the user reads from a paper receipt, against which the evaluation scores a variant |
| Variant | — | One way of reading a receipt in the evaluation: `ocr:<model>` (Tesseract, then a text model) or `vision:<model>` (the image to a vision model) |
| Full subset | — | The evaluated receipts whose truth file lists the lines; only they get line scores |

## Subsystems

- [categorization](subsystems/categorization/README.md) — catalog terms
- [import](subsystems/import/README.md) — import terms

## Related Documents

- [projectdescription.md](projectdescription.md)
- [datamodel.md](datamodel.md)
